"""Punto de entrada de Espejo Agudo.

Orquesta el flujo central de mensajes (process_message) y levanta en
paralelo: el bot de Telegram, el scheduler proactivo y la API FastAPI
(webhooks de WhatsApp) con Uvicorn en el puerto 8000.
"""

import asyncio
import logging
import os

import uvicorn
from telegram.ext import Application, MessageHandler, filters

from . import config, handlers, llm, memory, scheduler, state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

def cargar_system_prompt() -> str:
    """Carga el system prompt desde el archivo configurado.

    El system prompt contiene la personalidad del espejo y el contexto
    personal del usuario, por lo que vive en un archivo aparte
    (system_prompt.md, ignorado por git) y nunca en el código fuente.
    Si el archivo no existe, se usa el de ejemplo con una advertencia.
    """
    ruta = config.SYSTEM_PROMPT_FILE
    if not os.path.exists(ruta):
        logger.warning(
            "%s no existe. Usando system_prompt.example.md. "
            "Copialo con: cp system_prompt.example.md system_prompt.md "
            "y editalo con tu contexto personal.",
            ruta,
        )
        ruta = "system_prompt.example.md"
    with open(ruta, encoding="utf-8") as f:
        return f.read().strip()


SYSTEM_PROMPT = cargar_system_prompt()

# Prompt de onboarding: primera conversación con un usuario nuevo.
# Mantiene INTACTA la personalidad del espejo (directo, sin emojis, sin
# adulación) pero su misión en esta etapa es otra: entrevistar al usuario
# para conocer su vida y construir su base de conocimiento. Cuando tiene
# suficiente información, cierra con la marca PERFIL_COMPLETO.
ONBOARDING_PROMPT = """Sos un segundo cerebro, no un amigo. No tenés emociones.
No decís "buenos días", "te deseo suerte", "que tengas un lindo día".
Nunca uses emojis. Nunca finjas empatía. El silencio es válido.

Esta es la PRIMERA conversación con este usuario. Para serle útil necesitás
conocer su vida: en qué trabaja o qué está buscando, qué proyectos tiene en
curso, qué compromisos o plazos maneja, y qué patrones quiere que le señales.

Presentate brevemente en el primer mensaje: sos un segundo cerebro, no un
asistente servicial, y para funcionar necesitás conocer su contexto. Después,
entrevistalo.

Reglas de la entrevista:
- Hacé UNA o DOS preguntas por mensaje, no un cuestionario entero.
- Preguntas directas y concretas. Nada de "contame de vos".
- Si el usuario divaga o da respuestas vagas, repreguntá con precisión.
- Mantené el tono de espejo en todo momento: directo, sin frases de relleno.
- Cuando ya tengas un panorama claro (trabajo/búsqueda, proyectos en curso,
  compromisos, qué quiere que le señales), cerrá la entrevista con un
  resumen breve y directo de lo que entendiste y, en la ÚLTIMA LÍNEA del
  mensaje, escribí exactamente:
  PERFIL_COMPLETO"""

MARCADOR_PERFIL = "PERFIL_COMPLETO"


async def _procesar_onboarding(user_id: str, text: str, memoria_relevante: str) -> str:
    """Maneja la entrevista inicial con un usuario nuevo.

    Devuelve la respuesta a enviar. Si el LLM cierra la entrevista con
    PERFIL_COMPLETO, marca al usuario como onboarded y guarda un resumen
    del perfil en la memoria vectorial.
    """
    prompt = (
        f"MEMORIA DE LA CONVERSACIÓN:\n{memoria_relevante or '(primera interacción)'}\n\n"
        f"MENSAJE DEL USUARIO:\n{text}\n\n"
        "Continuá la entrevista (1-2 preguntas) o cerrala con el resumen "
        "y la marca PERFIL_COMPLETO si ya tenés el panorama."
    )
    respuesta = await asyncio.to_thread(llm.ask_ollama, ONBOARDING_PROMPT, prompt)

    if respuesta and MARCADOR_PERFIL in respuesta:
        state.marcar_onboarded(user_id)
        # Guardar el resumen del perfil como memoria semilla.
        resumen = respuesta.replace(MARCADOR_PERFIL, "").strip()
        await asyncio.to_thread(
            memory.save_memory,
            user_id,
            f"PERFIL DEL USUARIO (entrevista inicial): {resumen}",
            "assistant",
        )
        # Volver a pedir al LLM el cierre limpio, sin la marca técnica.
        return resumen
    return respuesta


async def process_message(
    user_id: str, text: str, platform: str, raw_chat_id
) -> str | None:
    """Flujo central para cada mensaje entrante.

    1. Registrar el usuario. 2. Guardar el mensaje en memoria.
    3. Extraer compromisos y programar recordatorios.
    4. Recuperar memoria relevante. 5. Consultar al LLM con contexto
       (onboarding si es usuario nuevo, modo espejo si ya está registrado).
    6. Guardar y retornar la respuesta (o None si es SILENCIO).
    """
    # 1. Registrar usuario (y su plataforma/chat para mensajes salientes).
    scheduler.registrar_usuario(user_id, platform, raw_chat_id)

    # 2. Guardar el mensaje en memoria como proveniente del usuario.
    await asyncio.to_thread(memory.save_memory, user_id, text, "user")

    # 3. Extraer compromisos con fecha/hora y programar recordatorios.
    try:
        compromisos = await asyncio.to_thread(llm.extract_commitments, text)
        for compromiso in compromisos:
            scheduler.programar_recordatorio(
                user_id,
                compromiso["descripcion"],
                compromiso["fecha_hora"],
            )
    except Exception:
        logger.exception("Error procesando compromisos de %s", user_id)

    # 4. Recuperar memoria relevante para este mensaje.
    memoria_relevante = await asyncio.to_thread(
        memory.get_relevant_memories, user_id, text
    )

    # 5a. Usuario nuevo: entrevista de onboarding (nunca devuelve SILENCIO).
    if not state.esta_onboarded(user_id):
        respuesta = await _procesar_onboarding(user_id, text, memoria_relevante)
        if respuesta:
            await asyncio.to_thread(
                memory.save_memory, user_id, respuesta, "assistant"
            )
        return respuesta

    # 5b. Usuario registrado: modo espejo normal.
    prompt = (
        f"MEMORIA RELEVANTE:\n{memoria_relevante or '(sin memoria relevante)'}\n\n"
        f"MENSAJE DEL USUARIO:\n{text}\n\n"
        "Respondé como espejo agudo. Si no hay nada incómodo pero útil que "
        "decir, respondé SILENCIO."
    )
    respuesta = await asyncio.to_thread(llm.ask_ollama, SYSTEM_PROMPT, prompt)

    # 6. Si no es SILENCIO, guardar como assistant y retornarla.
    if respuesta and respuesta.strip() != "SILENCIO":
        await asyncio.to_thread(memory.save_memory, user_id, respuesta, "assistant")
        return respuesta
    return None


async def _run_telegram() -> None:
    """Levantar el bot de Telegram con handlers de texto y voz."""
    tg_app = Application.builder().token(config.TELEGRAM_TOKEN).build()
    tg_app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.tg_text_handler)
    )
    tg_app.add_handler(
        MessageHandler(filters.VOICE | filters.AUDIO, handlers.tg_voice_handler)
    )
    # Conectar la app al scheduler para el envío proactivo por Telegram.
    scheduler.telegram_app = tg_app
    async with tg_app:
        await tg_app.start()
        await tg_app.updater.start_polling()
        logger.info("Bot de Telegram iniciado (polling)")
        # Mantener el bot corriendo indefinidamente.
        stop_event = asyncio.Event()
        await stop_event.wait()


async def _run_api() -> None:
    """Levantar la API FastAPI (webhooks de WhatsApp) en el puerto 8000."""
    server_config = uvicorn.Config(
        handlers.app, host="0.0.0.0", port=8000, log_level="info"
    )
    server = uvicorn.Server(server_config)
    await server.serve()


async def main() -> None:
    """Arrancar scheduler, Telegram y la API web en paralelo."""
    scheduler.iniciar()
    await asyncio.gather(
        _run_telegram(),
        _run_api(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Espejo Agudo detenido por el usuario")
