"""Estado persistente de usuarios (onboarding, flags).

Se guarda en un JSON local (data/users_state.json). No es información
sensible más allá de si el usuario completó o no la entrevista inicial.
"""

import json
import logging
import os
import threading

logger = logging.getLogger(__name__)

DATA_DIR = "data"
STATE_FILE = os.path.join(DATA_DIR, "users_state.json")

_lock = threading.Lock()
_state = None


def _cargar() -> dict:
    global _state
    if _state is not None:
        return _state
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                _state = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Estado de usuarios corrupto, se reinicia.")
            _state = {}
    else:
        _state = {}
    return _state


def _guardar() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def usuario_estado(user_id: str) -> dict:
    """Devuelve el dict de estado del usuario (creado si no existe)."""
    with _lock:
        estado = _cargar()
        return estado.setdefault(user_id, {"onboarded": False})


def marcar_onboarded(user_id: str) -> None:
    """Marca al usuario como entrevistado (onboarding completo)."""
    with _lock:
        usuario_estado(user_id)["onboarded"] = True
        _guardar()
    logger.info("Onboarding completado para %s", user_id)


def esta_onboarded(user_id: str) -> bool:
    with _lock:
        return bool(usuario_estado(user_id).get("onboarded"))
