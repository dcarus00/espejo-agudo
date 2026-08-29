"""Comunicación con Ollama (LLM local) y extractor de compromisos."""

import json
import logging
import re
from datetime import datetime

import requests

from . import config

logger = logging.getLogger(__name__)


def ask_ollama(system: str, prompt: str, max_tokens: int = 800) -> str:
    """Enviar un prompt a Ollama y devolver la respuesta del modelo.

    Usa temperature 0.6 (directo pero no robótico) y timeout de 120s
    porque los modelos de 14B en CPU pueden tardar.
    """
    payload = {
        "model": config.OLLAMA_MODEL,
        "system": system,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.6,
            "num_predict": max_tokens,
        },
    }
    try:
        response = requests.post(config.OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.Timeout:
        logger.error("Timeout (120s) esperando respuesta de Ollama")
    except Exception:
        logger.exception("Error consultando Ollama")
    return ""


def extract_commitments(text: str) -> list:
    """Extraer compromisos con fecha/hora del texto usando el LLM como extractor.

    Retorna una lista de dicts {descripcion, fecha_hora, tipo}. fecha_hora debe
    ser parseable como "%Y-%m-%d %H:%M". Si algo falla, retorna lista vacía.
    """
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    system = "Sos un extractor de fechas. Respondé solo JSON. Sin texto adicional."
    prompt = (
        f"Fecha y hora actual: {ahora}.\n"
        "Extraé del siguiente texto todos los compromisos con fecha y hora "
        "(entrevistas, citas, plazos, turnos, reuniones). "
        "Respondé SOLO un array JSON de objetos con las claves "
        '"descripcion", "fecha_hora" (formato "YYYY-MM-DD HH:MM") y "tipo". '
        "Si no hay compromisos con fecha, respondé [].\n\n"
        f"Texto: {text}"
    )
    respuesta = ask_ollama(system, prompt, max_tokens=400)
    if not respuesta:
        return []
    # Limpiar fences de markdown (```json ... ```) que el modelo pueda agregar.
    limpio = re.sub(r"```(?:json)?", "", respuesta).strip()
    try:
        datos = json.loads(limpio)
    except json.JSONDecodeError:
        logger.warning("Extractor devolvió JSON inválido: %s", limpio[:200])
        return []
    if not isinstance(datos, list):
        return []
    compromisos = []
    for item in datos:
        try:
            descripcion = str(item["descripcion"])
            fecha_hora = str(item["fecha_hora"])
            tipo = str(item.get("tipo", "compromiso"))
            # Validar formato de fecha/hora antes de aceptar el compromiso.
            datetime.strptime(fecha_hora, "%Y-%m-%d %H:%M")
            compromisos.append(
                {"descripcion": descripcion, "fecha_hora": fecha_hora, "tipo": tipo}
            )
        except (KeyError, ValueError, TypeError):
            logger.warning("Compromiso descartado por formato inválido: %s", item)
    return compromisos
