"""Handlers de Telegram (texto/voz) y webhooks FastAPI de WhatsApp.

Los audios se transcriben localmente y se BORRAN inmediatamente después
de transcribir: la privacidad es un requisito, no una opción.
"""

import asyncio
import base64
import logging
import os
import tempfile

import requests
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ContextTypes

from . import audio, config

logger = logging.getLogger(__name__)

# App FastAPI para los webhooks de WhatsApp.
app = FastAPI(title="Espejo Agudo")


def _telegram_permitido(telegram_user_id: int) -> bool:
    """True si el ID de Telegram está autorizado (o no hay whitelist)."""
    if not config.ALLOWED_TELEGRAM_IDS:
        return True
    return str(telegram_user_id) in config.ALLOWED_TELEGRAM_IDS


def _whatsapp_permitido(remitente: str) -> bool:
    """True si el número de WhatsApp está autorizado (o no hay whitelist)."""
    if not config.ALLOWED_WHATSAPP_NUMBERS:
        return True
    return remitente in config.ALLOWED_WHATSAPP_NUMBERS


async def tg_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensaje de texto de Telegram -> process_message()."""
    # Importación diferida para evitar dependencia circular con main.
    from .main import process_message

    if not _telegram_permitido(update.effective_user.id):
        logger.warning("Telegram no autorizado: %s", update.effective_user.id)
        return

    user_id = f"tg_{update.effective_user.id}"
    chat_id = update.effective_chat.id
    text = update.message.text or ""
    try:
        respuesta = await process_message(user_id, text, "telegram", chat_id)
        if respuesta:
            await update.message.reply_text(respuesta)
    except Exception:
        logger.exception("Error procesando texto de Telegram de %s", user_id)


async def tg_voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Nota de voz de Telegram: descargar .ogg, transcribir, borrar, procesar."""
    from .main import process_message

    if not _telegram_permitido(update.effective_user.id):
        logger.warning("Telegram no autorizado (voz): %s", update.effective_user.id)
        return

    user_id = f"tg_{update.effective_user.id}"
    chat_id = update.effective_chat.id
    tmp_path = None
    try:
        voice = update.message.voice or update.message.audio
        archivo = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await archivo.download_to_drive(tmp_path)
        texto = await asyncio.to_thread(audio.transcribe, tmp_path)
        if not texto:
            await update.message.reply_text("No pude transcribir el audio.")
            return
        respuesta = await process_message(
            user_id, f"[AUDIO] {texto}", "telegram", chat_id
        )
        if respuesta:
            await update.message.reply_text(respuesta)
    except Exception:
        logger.exception("Error procesando voz de Telegram de %s", user_id)
    finally:
        # Borrar el archivo de audio inmediatamente después de transcribir.
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                logger.warning("No se pudo borrar el audio temporal %s", tmp_path)


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request) -> dict:
    """Webhook de texto del bridge de WhatsApp: {from, body, timestamp, type}."""
    from .main import process_message

    try:
        data = await request.json()
        remitente = data.get("from", "")
        body = data.get("body", "")
        if not remitente or not body:
            return {"status": "ignored"}
        if not _whatsapp_permitido(remitente):
            logger.warning("WhatsApp no autorizado: %s", remitente)
            return {"status": "ignored"}
        user_id = f"wa_{remitente}"
        respuesta = await process_message(user_id, body, "whatsapp", remitente)
        # Si hay respuesta no-SILENCIO, enviarla al bridge de WhatsApp.
        if respuesta:
            await _enviar_whatsapp(remitente, respuesta)
        return {"status": "ok"}
    except Exception:
        logger.exception("Error en webhook /whatsapp")
        return {"status": "error"}


@app.post("/whatsapp-voice")
async def whatsapp_voice_webhook(request: Request) -> dict:
    """Webhook de voz del bridge: {from, timestamp, type, filename, mimetype, data}.

    data es el audio en base64. Se decodifica a un .ogg temporal, se
    transcribe localmente y se borra enseguida.
    """
    from .main import process_message

    tmp_path = None
    try:
        data = await request.json()
        remitente = data.get("from", "")
        audio_b64 = data.get("data", "")
        if not remitente or not audio_b64:
            return {"status": "ignored"}
        if not _whatsapp_permitido(remitente):
            logger.warning("WhatsApp no autorizado (voz): %s", remitente)
            return {"status": "ignored"}
        user_id = f"wa_{remitente}"
        audio_bytes = base64.b64decode(audio_b64)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        texto = await asyncio.to_thread(audio.transcribe, tmp_path)
        if not texto:
            return {"status": "error", "detail": "transcripcion vacia"}
        respuesta = await process_message(
            user_id, f"[AUDIO WHATSAPP] {texto}", "whatsapp", remitente
        )
        if respuesta:
            await _enviar_whatsapp(remitente, respuesta)
        return {"status": "ok"}
    except Exception:
        logger.exception("Error en webhook /whatsapp-voice")
        return {"status": "error"}
    finally:
        # Borrar el archivo de audio inmediatamente después de transcribir.
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                logger.warning("No se pudo borrar el audio temporal %s", tmp_path)


async def _enviar_whatsapp(remitente: str, texto: str) -> None:
    """Enviar un mensaje de WhatsApp a través del bridge Node.js."""
    try:
        resp = await asyncio.to_thread(
            requests.post,
            config.WHATSAPP_BRIDGE_URL,
            json={"to": remitente, "body": texto},
            timeout=30,
        )
        resp.raise_for_status()
    except Exception:
        logger.exception("Error enviando WhatsApp a %s", remitente)
