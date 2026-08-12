"""
investments_storage.py — Persistencia de posiciones de inversión y sus movimientos.

Dos archivos en `data/sistema/inversiones/`:

    posiciones.csv     qué es la inversión, de quién es y cuándo se abrió
    movimientos.csv    cada flujo de dinero de esa inversión

**Los montos no viven en la posición.** Parece una vuelta larga para un plazo fijo
—capital, interés y retención cabrían en tres columnas— pero una posición externa
(cripto, acciones, un fondo) tiene aportes y retiros parciales que un esquema plano no
soporta. Con movimientos, el plazo fijo se guarda como 3-4 filas y se lee igual que
antes, y lo que venga después entra sin rehacer el modelo. `capital`, `interes` y
`retencion` pasan a ser derivados (ver `services/investments/posiciones.py`).

El formato es CSV a mano, como `variables_storage.py`: son pocas filas, se leen en un
editor y se versionan en git. Cada escritura deja un `.bak` al lado, que es la
convención del repo para los CSV del sistema.
"""
from __future__ import annotations

import os
import shutil
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from contabilidad.backend.logger import get_logger
from contabilidad.config import PATH_DATA

logger = get_logger(__name__)

BASE_DATA_PATH = os.path.join(PATH_DATA, 'sistema', 'inversiones')

POSITIONS_FILE = os.path.join(BASE_DATA_PATH, 'posiciones.csv')
MOVEMENTS_FILE = os.path.join(BASE_DATA_PATH, 'movimientos.csv')

#: `tx_apertura_id` es la llave con la que el detector reconoce una posición que ya
#: guardaste: los ids de transacción son deterministas (md5 de fecha|monto|descripción),
#: así que sobreviven a reprocesar el extracto mientras la fila no cambie.
POSITION_COLUMNS = [
    'id',
    'portafolio_id',
    'tipo',
    'fecha_apertura',
    'fecha_cierre',
    'estado',
    'origen',
    'plazo_pactado_dias',
    'tasa_pactada',
    'institucion',
    'moneda',
    'nota',
    'tx_apertura_id',
    'tx_cierre_id',
]

MOVEMENT_COLUMNS = ['id', 'posicion_id', 'fecha', 'tipo', 'monto', 'tx_id', 'nota']


# ── Coerción ─────────────────────────────────────────────────────────────────

def _clean_str(value: Any, default: Optional[str] = '') -> Optional[str]:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return default if text == '' or text.lower() == 'nan' else text


def _clean_date(value: Any) -> Optional[str]:
    """Fecha en ISO corto (`YYYY-MM-DD`), o None si no hay nada usable."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    text = _clean_str(value, None)
    if text is None:
        return None
    try:
        ts = pd.to_datetime(text)
    except (ValueError, TypeError):
        return None
    if pd.isna(ts):
        return None
    return ts.date().isoformat()


def _clean_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    text = _clean_str(value, None)
    if text is None:
        return default
    try:
        number = float(text)
    except (ValueError, TypeError):
        return default
    return default if pd.isna(number) else number


def _clean_int(value: Any) -> Optional[int]:
    number = _clean_float(value, None)
    return None if number is None else int(round(number))


def _normalize_position(row: Dict[str, Any]) -> Dict[str, Any]:
    fecha_cierre = _clean_date(row.get('fecha_cierre'))
    estado = _clean_str(row.get('estado'), None)
    return {
        'id': _clean_str(row.get('id'), None),
        'portafolio_id': _clean_str(row.get('portafolio_id'), None),
        'tipo': _clean_str(row.get('tipo'), 'plazo_fijo'),
        'fecha_apertura': _clean_date(row.get('fecha_apertura')),
        'fecha_cierre': fecha_cierre,
        # Sin `estado` explícito, la fecha de cierre manda: es imposible que queden
        # desincronizados si nadie los escribe por separado.
        'estado': estado or ('cerrada' if fecha_cierre else 'abierta'),
        'origen': _clean_str(row.get('origen'), 'manual'),
        'plazo_pactado_dias': _clean_int(row.get('plazo_pactado_dias')),
        'tasa_pactada': _clean_float(row.get('tasa_pactada')),
        'institucion': _clean_str(row.get('institucion'), None),
        'moneda': _clean_str(row.get('moneda'), 'USD'),
        'nota': _clean_str(row.get('nota'), '') or '',
        'tx_apertura_id': _clean_str(row.get('tx_apertura_id'), None),
        'tx_cierre_id': _clean_str(row.get('tx_cierre_id'), None),
    }


def _normalize_movement(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'id': _clean_str(row.get('id'), None),
        'posicion_id': _clean_str(row.get('posicion_id'), None),
        'fecha': _clean_date(row.get('fecha')),
        'tipo': _clean_str(row.get('tipo'), None),
        # Los montos son siempre positivos: el signo lo pone `tipo`.
        'monto': round(_clean_float(row.get('monto'), 0.0) or 0.0, 2),
        'tx_id': _clean_str(row.get('tx_id'), None),
        'nota': _clean_str(row.get('nota'), '') or '',
    }


# ── Archivos ─────────────────────────────────────────────────────────────────

def ensure_data_dir() -> None:
    os.makedirs(BASE_DATA_PATH, exist_ok=True)


def read_records(file_path: str, normalizer) -> List[Dict[str, Any]]:
    """Filas del CSV ya normalizadas.

    Se lee todo como texto y se convierte en `normalizer`, en vez de dejar que pandas
    infiera: una columna con un solo valor numérico se volvía float y `plazo_pactado_dias`
    salía como `30.0`, y con dtypes de string ni siquiera se puede escribir un int encima.
    Aquí adentro el CSV es texto y afuera son tipos de Python; en el medio no hay dtypes.
    """
    if not os.path.exists(file_path):
        return []
    try:
        df = pd.read_csv(file_path, dtype=str, keep_default_na=False, na_values=[''])
    except Exception as e:
        logger.error("Error leyendo %s: %s", file_path, e)
        return []

    return [normalizer(row) for row in df.to_dict('records')]


def save_records(records: List[Dict[str, Any]], file_path: str, columns: List[str]) -> None:
    ensure_data_dir()
    if os.path.exists(file_path):
        try:
            shutil.copy2(file_path, file_path + '.bak')
        except OSError as e:
            logger.warning("No se pudo respaldar %s: %s", file_path, e)
    df = pd.DataFrame(records, columns=columns) if records else pd.DataFrame(columns=columns)
    df.to_csv(file_path, index=False)


class InvestmentStorage:
    """CRUD plano sobre los dos CSV. Las reglas de negocio viven en el servicio."""

    # ── Posiciones ───────────────────────────────────────────────────────────

    @staticmethod
    def get_positions(
        portafolio_id: Optional[str] = None,
        estado: Optional[str] = None,
        origen: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        posiciones = [p for p in read_records(POSITIONS_FILE, _normalize_position) if p['id']]

        if portafolio_id is not None:
            posiciones = [p for p in posiciones if p['portafolio_id'] == portafolio_id]
        if estado is not None:
            posiciones = [p for p in posiciones if p['estado'] == estado]
        if origen is not None:
            posiciones = [p for p in posiciones if p['origen'] == origen]

        posiciones.sort(key=lambda p: (p['fecha_apertura'] or '', p['fecha_cierre'] or ''))
        return posiciones

    @staticmethod
    def get_position(position_id: str) -> Optional[Dict[str, Any]]:
        for posicion in InvestmentStorage.get_positions():
            if posicion['id'] == position_id:
                return posicion
        return None

    @staticmethod
    def create_position(**fields: Any) -> Dict[str, Any]:
        row = _normalize_position(fields)
        row['id'] = _clean_str(fields.get('id'), None) or str(uuid.uuid4())

        posiciones = read_records(POSITIONS_FILE, _normalize_position)
        save_records(posiciones + [row], POSITIONS_FILE, POSITION_COLUMNS)
        return row

    @staticmethod
    def update_position(position_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        posiciones = read_records(POSITIONS_FILE, _normalize_position)
        actual = next((p for p in posiciones if p['id'] == str(position_id)), None)
        if actual is None:
            return None

        merged = {**actual, **{k: v for k, v in updates.items() if k in POSITION_COLUMNS and k != 'id'}}
        # Recalcular el estado salvo que lo hayan pedido explícitamente: cambiar la fecha
        # de cierre y dejar 'abierta' es la clase de incoherencia que después nadie explica.
        if 'estado' not in updates:
            merged.pop('estado', None)
        row = _normalize_position(merged)
        row['id'] = str(position_id)

        save_records(
            [row if p['id'] == row['id'] else p for p in posiciones],
            POSITIONS_FILE, POSITION_COLUMNS,
        )
        return row

    @staticmethod
    def delete_position(position_id: str) -> bool:
        posiciones = read_records(POSITIONS_FILE, _normalize_position)
        quedan = [p for p in posiciones if p['id'] != str(position_id)]
        if len(quedan) == len(posiciones):
            return False

        save_records(quedan, POSITIONS_FILE, POSITION_COLUMNS)
        InvestmentStorage.delete_movements_of(position_id)
        return True

    # ── Movimientos ──────────────────────────────────────────────────────────

    @staticmethod
    def get_movements(posicion_id: Optional[str] = None) -> List[Dict[str, Any]]:
        movimientos = [m for m in read_records(MOVEMENTS_FILE, _normalize_movement) if m['id']]

        if posicion_id is not None:
            movimientos = [m for m in movimientos if m['posicion_id'] == posicion_id]

        movimientos.sort(key=lambda m: (m['fecha'] or '', m['tipo'] or ''))
        return movimientos

    @staticmethod
    def get_movements_by_position() -> Dict[str, List[Dict[str, Any]]]:
        """Todos los movimientos agrupados: una sola lectura para listar N posiciones."""
        agrupados: Dict[str, List[Dict[str, Any]]] = {}
        for movimiento in InvestmentStorage.get_movements():
            agrupados.setdefault(movimiento['posicion_id'], []).append(movimiento)
        return agrupados

    @staticmethod
    def create_movement(posicion_id: str, fecha: Any, tipo: str, monto: float,
                        tx_id: Optional[str] = None, nota: Optional[str] = None,
                        **extra: Any) -> Dict[str, Any]:
        row = _normalize_movement({
            'id': extra.get('id'),
            'posicion_id': posicion_id,
            'fecha': fecha,
            'tipo': tipo,
            'monto': monto,
            'tx_id': tx_id,
            'nota': nota,
        })
        row['id'] = row['id'] or str(uuid.uuid4())

        movimientos = read_records(MOVEMENTS_FILE, _normalize_movement)
        save_records(movimientos + [row], MOVEMENTS_FILE, MOVEMENT_COLUMNS)
        return row

    @staticmethod
    def update_movement(movement_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        movimientos = read_records(MOVEMENTS_FILE, _normalize_movement)
        actual = next((m for m in movimientos if m['id'] == str(movement_id)), None)
        if actual is None:
            return None

        merged = {**actual, **{k: v for k, v in updates.items() if k in MOVEMENT_COLUMNS and k != 'id'}}
        row = _normalize_movement(merged)
        row['id'] = str(movement_id)

        save_records(
            [row if m['id'] == row['id'] else m for m in movimientos],
            MOVEMENTS_FILE, MOVEMENT_COLUMNS,
        )
        return row

    @staticmethod
    def delete_movement(movement_id: str) -> bool:
        movimientos = read_records(MOVEMENTS_FILE, _normalize_movement)
        quedan = [m for m in movimientos if m['id'] != str(movement_id)]
        if len(quedan) == len(movimientos):
            return False
        save_records(quedan, MOVEMENTS_FILE, MOVEMENT_COLUMNS)
        return True

    @staticmethod
    def delete_movements_of(posicion_id: str) -> int:
        movimientos = read_records(MOVEMENTS_FILE, _normalize_movement)
        quedan = [m for m in movimientos if m['posicion_id'] != str(posicion_id)]
        borrados = len(movimientos) - len(quedan)
        if borrados:
            save_records(quedan, MOVEMENTS_FILE, MOVEMENT_COLUMNS)
        return borrados

    @staticmethod
    def replace_movements(posicion_id: str, movimientos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deja la posición exactamente con estos movimientos, en una sola escritura.

        Borrar y volver a crear uno por uno reescribiría el CSV N+1 veces y dejaría el
        `.bak` inservible a mitad de camino.
        """
        otros = [m for m in read_records(MOVEMENTS_FILE, _normalize_movement)
                 if m['posicion_id'] != str(posicion_id)]

        nuevas: List[Dict[str, Any]] = []
        for movimiento in movimientos:
            row = _normalize_movement({**movimiento, 'posicion_id': posicion_id})
            row['id'] = row['id'] or str(uuid.uuid4())
            nuevas.append(row)

        save_records(otros + nuevas, MOVEMENTS_FILE, MOVEMENT_COLUMNS)
        return nuevas
