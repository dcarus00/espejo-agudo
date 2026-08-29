"""Configuración central de Espejo Agudo.

Carga las variables desde el archivo .env (si existe) usando python-dotenv.
Todos los valores tienen defaults razonables para un entorno local Debian.
"""

import os

from dotenv import load_dotenv

# Cargar variables de entorno desde .env en la raíz del proyecto.
load_dotenv()

# Token del bot de Telegram (obligatorio para usar Telegram).
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# Endpoint de generación de Ollama (local).
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

# Modelo de Ollama a utilizar. Qwen 2.5 14B respeta system prompts estrictos
# y tiene español nativo; no usar Gemma ni Llama 3 para este proyecto.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

# Conexión a Qdrant (memoria vectorial local).
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# Nombre de la colección de vectores.
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "espejo_agudo")

# Modelo de Whisper para transcripción local en CPU.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

# URL del bridge de WhatsApp (whatsapp-web.js) para enviar mensajes.
WHATSAPP_BRIDGE_URL = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3000/send")

# Archivo con el system prompt (personalidad + contexto personal del usuario).
# Copiar system_prompt.example.md a system_prompt.md y editar la sección
# de contexto con tus datos. El archivo real está en .gitignore.
SYSTEM_PROMPT_FILE = os.getenv("SYSTEM_PROMPT_FILE", "system_prompt.md")

# Ventana horaria diaria para mensajes proactivos (de 9 a 21 por defecto).
HORA_INICIO = int(os.getenv("HORA_INICIO", "9"))
HORA_FIN = int(os.getenv("HORA_FIN", "21"))


def _parse_lista(valor: str) -> list:
    """Parsea una lista separada por comas desde .env, ignorando vacíos."""
    return [item.strip() for item in valor.split(",") if item.strip()]


# Control de acceso: quién puede hablarle al espejo.
# Si la lista está vacía, el bot acepta mensajes de cualquiera (no recomendado
# salvo para pruebas). Configurar siempre en producción.
#
# ALLOWED_TELEGRAM_IDS: IDs numéricos de Telegram separados por comas.
#   Tu ID lo obtenés hablándole a @userinfobot en Telegram.
#   Ejemplo: ALLOWED_TELEGRAM_IDS=123456789
#
# ALLOWED_WHATSAPP_NUMBERS: números con formato WhatsApp separados por comas.
#   Formato: codigo_pais + numero + "@c.us" (sin "+", sin espacios).
#   Ejemplo: ALLOWED_WHATSAPP_NUMBERS=59899123456@c.us
ALLOWED_TELEGRAM_IDS = _parse_lista(os.getenv("ALLOWED_TELEGRAM_IDS", ""))
ALLOWED_WHATSAPP_NUMBERS = _parse_lista(os.getenv("ALLOWED_WHATSAPP_NUMBERS", ""))
