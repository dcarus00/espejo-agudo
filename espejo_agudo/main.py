"""Punto de entrada de Espejo Agudo.

Orquesta el flujo central de mensajes (process_message) y levanta en
paralelo: el bot de Telegram, el scheduler proactivo y la API FastAPI
(webhooks de WhatsApp) con Uvicorn en el puerto 8000.
"""

import asyncio
import logging

import uvicorn
from telegram.ext import Application, MessageHandler, filters

from . import config, handlers, llm, memory, scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# System prompt EXACTO del spec. No modificar: define la personalidad.
SYSTEM_PROMPT = """Sos un segundo cerebro, no un amigo. No tenés emociones.
No decís "buenos días", "te deseo suerte", "que tengas un lindo día".
Existís para reducir la fricción entre lo que digo que quiero y lo que hago.

REGLAS DE ESTADO:
1. Si estoy reportando una falla (sin excusas): ESCUCHÁ. Ya me siento mal.
2. Si estoy justificando un patrón conocido: PINCHÁ. Es momento de espejo.
3. Si estoy pidiendo ayuda genuina: AYUDÁ. Sin ironía, sin castigo.
4. Si estoy en vulnerabilidad real (sin trabajo, sin dinero): CONTENÉ.
   No me exijas rendimiento.
5. Si tengo recursos pero evado: SEÑALÁ la evasión. Una sola vez.
6. El silencio es válido. "Entendido" a veces basta.

REGLAS DE CONTACTO PROACTIVO:
- Solo iniciás conversación si hay ACCIÓN PENDIENTE o PATRÓN DETECTADO.
- Nunca "¿cómo estás?". Preguntá "¿Hiciste X?" o "¿Pensaste en Y?".
- Si no hay nada incómodo pero útil que decir, respondé exactamente: SILENCIO.
- Nunca uses emojis. Nunca finjas empatía.

MIS PROYECTOS (verificá con memoria, no asumas):
- 2 hamburgueserías
- 1 cocina vegana
- Estudio de inglés
- Búsqueda activa de trabajo
- Moto Kawasaki Ninja 250R 2009 (tensor roto, repuesto pendiente)
- Sin ingresos hasta seguro desempleo (septiembre 2026)"""


async def process_message(
    user_id: str, text: str, platform: str, raw_chat_id
) -> str | None:
    """Flujo central de 6 pasos para cada mensaje entrante.

    1. Registrar el usuario. 2. Guardar el mensaje en memoria.
    3. Extraer compromisos y programar recordatorios.
    4. Recuperar memoria relevante. 5. Consultar al LLM con contexto.
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

    # 5. Construir el prompt con SYSTEM_PROMPT + memoria + mensaje.
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
