"""
Undo Store — historial de operaciones masivas reversibles
=========================================================

Cada operación masiva guarda un snapshot de los valores previos en
data/sistema/etiquetado/undo/<id>.json, para poder revertirla después.

Se conservan las últimas MAX_ENTRIES operaciones; las viejas se purgan.
Es almacenamiento en disco (no en memoria) para que un reinicio del backend
no deje al usuario sin la opción de deshacer.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Optional

from contabilidad.config import PATH_DATA
from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

UNDO_DIR = os.path.join(PATH_DATA, 'sistema', 'etiquetado', 'undo')
MAX_ENTRIES = 30


def _path(undo_id: str) -> str:
    return os.path.join(UNDO_DIR, f"{undo_id}.json")


def _purge_old() -> None:
    """Mantiene solo las MAX_ENTRIES operaciones más recientes."""
    try:
        files = [os.path.join(UNDO_DIR, f) for f in os.listdir(UNDO_DIR) if f.endswith('.json')]
        for old in sorted(files, key=os.path.getmtime, reverse=True)[MAX_ENTRIES:]:
            os.remove(old)
    except Exception as e:
        logger.warning("No se pudo purgar el historial de undo: %s", e)


def save_snapshot(payload: dict) -> str:
    """Guarda un snapshot reversible y retorna su id."""
    os.makedirs(UNDO_DIR, exist_ok=True)
    undo_id = str(uuid.uuid4())
    payload = {**payload, "id": undo_id, "created_at": datetime.now().isoformat()}

    try:
        with open(_path(undo_id), 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error("No se pudo guardar el snapshot de undo: %s", e)
        return ""

    _purge_old()
    return undo_id


def load_snapshot(undo_id: str) -> Optional[dict]:
    """Carga un snapshot por id, o None si ya no existe."""
    try:
        with open(_path(undo_id), 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error("No se pudo leer el snapshot %s: %s", undo_id, e)
        return None


def discard_snapshot(undo_id: str) -> None:
    """Elimina un snapshot ya consumido (una operación se deshace una vez)."""
    try:
        os.remove(_path(undo_id))
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning("No se pudo eliminar el snapshot %s: %s", undo_id, e)
