"""Scheduler: proactividad aleatoria y recordatorios de compromisos.

Usa APScheduler (AsyncIOScheduler) con DateTrigger en momentos aleatorios.
No hay cron fijo: la frecuencia proactiva es ~1 mensaje cada 1-2 días, y
solo se envía si el LLM detecta algo útil que decir (si no, SILENCIO).
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta

import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from . import config, llm, memory

logger = logging.getLogger(__name__)

# Referencia a la aplicación de Telegram (se conecta desde main.py).
telegram_app = None

# Registro global de usuarios: user_id -> {"platform": ..., "chat_id": ...}.
# Se llena dinámicamente cuando el usuario habla por primera vez.
user_registry: dict = {}

# Scheduler asíncrono global.
scheduler = AsyncIOScheduler()

# Query fija para revisar la memoria reciente en los mensajes proactivos.
_QUERY_PROACTIVO = (
    "acciones pendientes compromisos entrevistas CVs moto trabajo inglés cocina"
)


def iniciar() -> None:
    """Arrancar el scheduler (llamar una vez desde main)."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler iniciado")


def registrar_usuario(user_id: str, platform: str, chat_id) -> None:
    """Registrar/actualizar un usuario y asegurar su ciclo proactivo."""
    es_nuevo = user_id not in user_registry
    user_registry[user_id] = {"platform": platform, "chat_id": chat_id}
    if es_nuevo:
        logger.info("Usuario registrado: %s (%s)", user_id, platform)
        _programar_siguiente_aleatorio(user_id)


def _programar_siguiente_aleatorio(user_id: str) -> None:
    """Programar el próximo mensaje proactivo en un momento aleatorio.

    Si la hora actual < HORA_FIN y random() < 0.4, se programa para hoy.
    Si no, para mañana o pasado mañana (1-2 días).
    """
    ahora = datetime.now()
    if ahora.hour < config.HORA_FIN and random.random() < 0.4:
        dias = 0
    else:
        dias = random.randint(1, 2)
    hora = random.randint(config.HORA_INICIO, config.HORA_FIN - 1)
    minuto = random.randint(0, 59)
    momento = (ahora + timedelta(days=dias)).replace(
        hour=hora, minute=minuto, second=0, microsecond=0
    )
    # Si el momento calculado para hoy ya pasó, moverlo a mañana.
    if momento <= ahora:
        momento = momento + timedelta(days=1)
    job_id = f"proactivo_{user_id}"
    # Reemplazar el job anterior si existe.
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        _enviar_proactivo,
        trigger=DateTrigger(run_date=momento),
        args=[user_id],
        id=job_id,
    )
    logger.info("Proactivo programado para %s el %s", user_id, momento)


async def _enviar_proactivo(user_id: str) -> None:
    """Revisar memoria y escribir al usuario SOLO si hay algo útil que decir."""
    try:
        memoria_reciente = memory.get_relevant_memories(
            user_id, _QUERY_PROACTIVO
        )
        prompt = (
            "Revisá la memoria reciente del usuario y detectá si hay una acción "
            "pendiente, una contradicción o un patrón de evasión. Si lo hay, "
            "escribí un mensaje directo y útil (sin emojis, sin saludos). "
            "Si no hay nada incómodo pero útil que decir, respondé "
            "exactamente: SILENCIO.\n\n"
            f"MEMORIA RECIENTE:\n{memoria_reciente or '(sin memoria registrada)'}"
        )
        # Importación diferida para evitar dependencia circular con main.
        from .main import SYSTEM_PROMPT

        respuesta = await asyncio.to_thread(llm.ask_ollama, SYSTEM_PROMPT, prompt)
        if respuesta and respuesta.strip() != "SILENCIO":
            await _enviar_a_usuario(user_id, respuesta)
        else:
            logger.info("Proactivo para %s: SILENCIO (nada útil que decir)", user_id)
    except Exception:
        logger.exception("Error en mensaje proactivo para %s", user_id)
    finally:
        # Reprogramar el siguiente contacto proactivo.
        _programar_siguiente_aleatorio(user_id)


def programar_recordatorio(
    user_id: str,
    descripcion: str,
    fecha_hora: str,
    minutos_antes: int | None = None,
) -> None:
    """Programar un recordatorio 30-90 minutos (aleatorio) antes del compromiso."""
    if minutos_antes is None:
        minutos_antes = random.randint(30, 90)
    try:
        momento_compromiso = datetime.strptime(fecha_hora, "%Y-%m-%d %H:%M")
    except ValueError:
        logger.warning("Fecha de compromiso inválida, no se programa: %s", fecha_hora)
        return
    momento_recordatorio = momento_compromiso - timedelta(minutes=minutos_antes)
    # Si el momento del recordatorio ya pasó, no hacer nada.
    if momento_recordatorio <= datetime.now():
        logger.info(
            "Recordatorio ya vencido, no se programa: %s (%s)", descripcion, fecha_hora
        )
        return
    job_id = f"recordatorio_{user_id}_{int(momento_recordatorio.timestamp())}"
    scheduler.add_job(
        _enviar_recordatorio,
        trigger=DateTrigger(run_date=momento_recordatorio),
        args=[user_id, descripcion, momento_compromiso],
        id=job_id,
    )
    logger.info(
        "Recordatorio programado para %s: '%s' el %s (%d min antes)",
        user_id,
        descripcion,
        momento_recordatorio,
        minutos_antes,
    )


async def _enviar_recordatorio(
    user_id: str, descripcion: str, momento_compromiso: datetime
) -> None:
    """Generar y enviar el recordatorio de un compromiso próximo."""
    try:
        prompt = (
            f"El usuario tiene un compromiso próximo: {descripcion} "
            f"a las {momento_compromiso.strftime('%H:%M')}. "
            "Enviá recordatorio útil y directo. Sin emojis. Sin suerte."
        )
        from .main import SYSTEM_PROMPT

        respuesta = await asyncio.to_thread(llm.ask_ollama, SYSTEM_PROMPT, prompt)
        if respuesta and respuesta.strip() != "SILENCIO":
            await _enviar_a_usuario(user_id, respuesta)
    except Exception:
        logger.exception("Error enviando recordatorio a %s", user_id)


async def _enviar_a_usuario(user_id: str, texto: str) -> None:
    """Enviar un mensaje al usuario por su plataforma registrada.

    Telegram: bot.send_message. WhatsApp: POST al bridge con {to, body}.
    Luego guarda la respuesta en memoria como assistant.
    """
    datos = user_registry.get(user_id)
    if not datos:
        logger.warning("Usuario %s no registrado, no se puede enviar", user_id)
        return
    platform = datos["platform"]
    chat_id = datos["chat_id"]
    try:
        if platform == "telegram":
            if telegram_app is None:
                logger.error("telegram_app no inicializada; mensaje perdido")
                return
            await telegram_app.bot.send_message(chat_id=chat_id, text=texto)
        elif platform == "whatsapp":
            resp = await asyncio.to_thread(
                requests.post,
                config.WHATSAPP_BRIDGE_URL,
                json={"to": chat_id, "body": texto},
                timeout=30,
            )
            resp.raise_for_status()
        else:
            logger.warning("Plataforma desconocida para %s: %s", user_id, platform)
            return
        memory.save_memory(user_id, texto, source="assistant")
        logger.info("Mensaje enviado a %s (%s)", user_id, platform)
    except Exception:
        logger.exception("Error enviando mensaje a %s (%s)", user_id, platform)
