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

# Cliente de Qdrant local.
_client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)


def _ensure_collection() -> None:
    """Crear la colección si no existe (384 dims, distancia COSINE)."""
    try:
        existing = {c.name for c in _client.get_collections().collections}
        if config.COLLECTION_NAME not in existing:
            _client.create_collection(
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
        _client.upsert(collection_name=config.COLLECTION_NAME, points=[point])
        logger.debug("Memoria guardada para %s (%s): %s", user_id, source, text[:80])
    except Exception:
        logger.exception("Error guardando memoria para %s", user_id)


def get_relevant_memories(user_id: str, query: str, limit: int = 7) -> str:
    """Buscar recuerdos relevantes para la query, filtrados por user_id.

    Retorna un string formateado con fecha, fuente y texto, una por línea.
    """
    try:
        vector = _model.encode(query).tolist()
        results = _client.search(
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
