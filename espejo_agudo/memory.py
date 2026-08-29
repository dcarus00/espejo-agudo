"""Memoria semántica persistente con Qdrant + sentence-transformers.

Cada recuerdo guarda el embedding del texto junto con el user_id, la fuente
(user / assistant) y un timestamp. Las búsquedas son semánticas y siempre
filtradas por user_id para aislar la memoria de cada usuario.
"""

import logging
import time
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

from . import config

logger = logging.getLogger(__name__)

# Modelo de embeddings: 384 dimensiones, liviano y rápido en CPU.
_model = SentenceTransformer("all-MiniLM-L6-v2")

# Cliente de Qdrant local. Se crea de forma perezosa y con reintentos para
# no crashear al importar si Qdrant todavía no está levantado.
_client = None


def _get_client():
    """Devuelve el cliente de Qdrant, conectando con reintentos si hace falta.

    Si Qdrant no responde, reintenta 5 veces (3 s entre intentos) y luego
    lanza un error con un mensaje accionable en lugar de un stacktrace crudo.
    """
    global _client
    if _client is not None:
        return _client

    intentos = 5
    for intento in range(1, intentos + 1):
        try:
            cliente = QdrantClient(
                host=config.QDRANT_HOST, port=config.QDRANT_PORT, timeout=5
            )
            cliente.get_collections()  # verificación real de conectividad
            _client = cliente
            return _client
        except Exception:
            if intento == intentos:
                logger.error(
                    "No se pudo conectar a Qdrant en %s:%s después de %d intentos. "
                    "¿Está levantado? Probá con: docker compose up -d",
                    config.QDRANT_HOST,
                    config.QDRANT_PORT,
                    intentos,
                )
                raise
            logger.warning(
                "Qdrant no responde (intento %d/%d). Reintentando en 3 s...",
                intento,
                intentos,
            )
            time.sleep(3)
    return _client


def _ensure_collection() -> None:
    """Crear la colección si no existe (384 dims, distancia COSINE)."""
    try:
        existing = {c.name for c in _get_client().get_collections().collections}
        if config.COLLECTION_NAME not in existing:
            _get_client().create_collection(
                collection_name=config.COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            logger.info("Colección Qdrant creada: %s", config.COLLECTION_NAME)
    except Exception:
        logger.exception("No se pudo verificar/crear la colección en Qdrant")


_ensure_collection()


def save_memory(user_id: str, text: str, source: str = "user") -> None:
    """Guardar un recuerdo: texto + embedding + timestamp + fuente."""
    try:
        vector = _model.encode(text).tolist()
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "user_id": user_id,
                "text": text,
                "source": source,
                "timestamp": time.time(),
            },
        )
        _get_client().upsert(collection_name=config.COLLECTION_NAME, points=[point])
        logger.debug("Memoria guardada para %s (%s): %s", user_id, source, text[:80])
    except Exception:
        logger.exception("Error guardando memoria para %s", user_id)


def get_relevant_memories(user_id: str, query: str, limit: int = 7) -> str:
    """Buscar recuerdos relevantes para la query, filtrados por user_id.

    Retorna un string formateado con fecha, fuente y texto, una por línea.
    """
    try:
        vector = _model.encode(query).tolist()
        results = _get_client().search(
            collection_name=config.COLLECTION_NAME,
            query_vector=vector,
            limit=limit,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id),
                    )
                ]
            ),
        )
        if not results:
            return ""
        lines = []
        for hit in results:
            payload = hit.payload or {}
            fecha = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(payload.get("timestamp", 0))
            )
            source = payload.get("source", "user")
            texto = payload.get("text", "")
            lines.append(f"[{fecha}] ({source}): {texto}")
        return "\n".join(lines)
    except Exception:
        logger.exception("Error recuperando memorias para %s", user_id)
        return ""
