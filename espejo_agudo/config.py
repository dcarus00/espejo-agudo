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

# Ventana horaria diaria para mensajes proactivos (de 9 a 21 por defecto).
HORA_INICIO = int(os.getenv("HORA_INICIO", "9"))
HORA_FIN = int(os.getenv("HORA_FIN", "21"))
