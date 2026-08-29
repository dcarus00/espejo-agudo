"""Transcripción de voz 100% local con faster-whisper (CPU, int8).

Los audios nunca salen de la máquina y se borran inmediatamente después
de transcribir (responsabilidad del handler que llama a transcribe()).
"""

import logging

from faster_whisper import WhisperModel

from . import config

logger = logging.getLogger(__name__)

# Cargar el modelo al iniciar para no pagar el costo en cada audio.
_model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
logger.info("Modelo Whisper cargado: %s (cpu, int8)", config.WHISPER_MODEL)


def transcribe(file_path: str) -> str:
    """Transcribir un archivo de audio en español y retornar el texto unido."""
    try:
        segments, info = _model.transcribe(file_path, language="es", beam_size=5)
        texto = " ".join(segment.text.strip() for segment in segments).strip()
        logger.info(
            "Audio transcrito (%s, idioma=%s, prob=%.2f): %s",
            file_path,
            info.language,
            info.language_probability,
            texto[:80],
        )
        return texto
    except Exception:
        logger.exception("Error transcribiendo audio %s", file_path)
        return ""
