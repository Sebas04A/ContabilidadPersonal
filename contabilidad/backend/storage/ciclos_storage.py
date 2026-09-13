"""Ciclos de un fondo: los períodos en los que se confina la cobertura.

Un ciclo es un tramo `[inicio, fin)` de un fondo. Los ingresos de un ciclo cubren los
gastos de ese mismo ciclo y de ninguno más, así que el sobrante de un mes no puede acabar
pagando el mes siguiente — que era justo la fuga que este módulo existe para cortar.

Las fronteras se **guardan**, no se derivan. Es la diferencia que hace que todo esto
aguante: el día en que llega el dinero cambia con el tiempo (en el fondo Comida ha sido el
24, el 22, el 3 y el 20), y si el corte fuera un solo número en el grupo, cambiarlo hoy
reescribiría en silencio los emparejamientos de 2025. Con las fronteras escritas, el grupo
solo decide **cómo nacen los ciclos nuevos**; los que ya existen se leen a sí mismos.

La fila guarda decisiones —dónde están los límites, por qué este mes fue raro—, nunca
resultados: crédito, cubierto y sobrante se calculan de los movimientos cada vez. Guardarlos
sería una caché que se queda vieja.
"""
from __future__ import annotations

import calendar
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from contabilidad.backend.logger import get_logger
from contabilidad.backend.storage.variables_storage import (
    BASE_DATA_PATH,
    _id_unico,
    _indices_de,
    _texto_plano,
    read_csv,
    save_csv,
)

logger = get_logger(__name__)

CICLOS_FILE = os.path.join(BASE_DATA_PATH, 'ciclos.csv')

CICLO_COLUMNS = ['id', 'group_id', 'inicio', 'fin', 'nota']

DIA_CORTE_POR_DEFECTO = 1


# ── Fechas y fronteras ────────────────────────────────────────────────────────

def a_fecha(valor: Any) -> Optional[date]:
    """El valor como `date`, o None si no hay nada que interpretar."""
    if valor is None or valor == '':
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        ts = pd.to_datetime(valor)
        if pd.isna(ts):
            return None
        return ts.date()
    except Exception:
        return None


def _dia_del_mes(anio: int, mes: int, dia: int) -> date:
    """El día `dia` de ese mes, recortado al último si el mes es más corto.

    Sin el recorte, un corte el 31 no existiría en febrero y la generación se rompería
    justo en el mes donde más se nota.
    """
    ultimo = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, min(max(dia, 1), ultimo))


def frontera_en_o_antes(fecha: date, dia_corte: int) -> date:
    """La última frontera que cae en `fecha` o antes."""
    candidata = _dia_del_mes(fecha.year, fecha.month, dia_corte)
    if candidata <= fecha:
        return candidata
    mes_anterior = fecha.replace(day=1) - timedelta(days=1)
    return _dia_del_mes(mes_anterior.year, mes_anterior.month, dia_corte)


def frontera_siguiente(fecha: date, dia_corte: int) -> date:
    """La primera frontera estrictamente posterior a `fecha`.

    Es estrictamente posterior a propósito: si devolviera la misma fecha, el generador
    crearía un ciclo vacío `[f, f)` y se quedaría dando vueltas ahí.
    """
    candidata = _dia_del_mes(fecha.year, fecha.month, dia_corte)
    if candidata > fecha:
        return candidata
    mes_siguiente = (fecha.replace(day=1) + timedelta(days=32)).replace(day=1)
    return _dia_del_mes(mes_siguiente.year, mes_siguiente.month, dia_corte)


# ── Almacenamiento ────────────────────────────────────────────────────────────

def _normalizar(fila: Dict[str, Any]) -> Dict[str, Any]:
    inicio = a_fecha(fila.get('inicio'))
    fin = a_fecha(fila.get('fin'))
    return {
        'id': _texto_plano(fila.get('id')),
        'group_id': _texto_plano(fila.get('group_id')),
        'inicio': inicio.isoformat() if inicio else None,
        'fin': fin.isoformat() if fin else None,
        'nota': _texto_plano(fila.get('nota')),
    }


class CicloStorage:
    @staticmethod
    def get_ciclos(group_id: str) -> List[Dict[str, Any]]:
        """Los ciclos del fondo, en orden. Los que no tengan fronteras se descartan:
        una fila sin `inicio` o sin `fin` no delimita nada."""
        df = read_csv(CICLOS_FILE, CICLO_COLUMNS)
        if df.empty:
            return []
        df = df[df['group_id'].fillna('').astype(str) == str(group_id)]
        ciclos = [_normalizar(f) for f in df.to_dict('records')]
        ciclos = [c for c in ciclos if c['inicio'] and c['fin']]
        return sorted(ciclos, key=lambda c: c['inicio'])

    @staticmethod
    def get_ciclo(ciclo_id: str) -> Optional[Dict[str, Any]]:
        df = read_csv(CICLOS_FILE, CICLO_COLUMNS)
        indices = _indices_de(df, 'id', ciclo_id)
        if not indices:
            return None
        return _normalizar(df.loc[indices[0]].to_dict())

    @staticmethod
    def crear_muchos(filas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Alta en lote: una sola lectura y una sola escritura.

        El generador crea ciclos de mes en mes y un fondo con dos años de historia son
        veinticuatro filas; darlas de alta una a una reescribiría el CSV veinticuatro veces.
        """
        if not filas:
            return []
        df = read_csv(CICLOS_FILE, CICLO_COLUMNS)
        nuevas: List[Dict[str, Any]] = []
        ids = set(df['id'].astype(str)) if 'id' in df.columns and not df.empty else set()
        for fila in filas:
            nuevo_id = _id_unico(df)
            while nuevo_id in ids:
                nuevo_id = _id_unico(df)
            ids.add(nuevo_id)
            nuevas.append({
                'id': nuevo_id,
                'group_id': fila['group_id'],
                'inicio': fila['inicio'],
                'fin': fila['fin'],
                'nota': fila.get('nota') or None,
            })
        df = pd.concat([df, pd.DataFrame(nuevas)], ignore_index=True)
        save_csv(df[CICLO_COLUMNS], CICLOS_FILE)
        return [_normalizar(f) for f in nuevas]

    @staticmethod
    def actualizar(ciclo_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        df = read_csv(CICLOS_FILE, CICLO_COLUMNS)
        indices = _indices_de(df, 'id', ciclo_id)
        if not indices:
            return None
        fila = indices[0]
        for clave, valor in updates.items():
            if clave in CICLO_COLUMNS and clave != 'id':
                if isinstance(valor, (date, datetime)):
                    valor = valor.isoformat()[:10]
                if valor is None or (isinstance(valor, str) and valor.strip() == ''):
                    df[clave] = df[clave].astype(object)
                    valor = None
                df.at[fila, clave] = valor
        save_csv(df[CICLO_COLUMNS], CICLOS_FILE)
        return _normalizar(df.loc[fila].to_dict())

    @staticmethod
    def borrar_de(group_id: str) -> int:
        """Todos los ciclos de un fondo. Lo usa el borrado del fondo, para no dejar
        ciclos apuntando a un grupo que ya no existe."""
        df = read_csv(CICLOS_FILE, CICLO_COLUMNS)
        if df.empty:
            return 0
        sobran = df['group_id'].fillna('').astype(str) == str(group_id)
        cuantos = int(sobran.sum())
        if cuantos:
            save_csv(df[~sobran][CICLO_COLUMNS], CICLOS_FILE)
        return cuantos


# ── Generación ────────────────────────────────────────────────────────────────

def generar_ciclos(
    group_id: str,
    dia_corte: int,
    primera_fecha: Optional[date],
    ultima_fecha: Optional[date],
) -> List[Dict[str, Any]]:
    """Crea los ciclos que falten para cubrir `[primera_fecha, ultima_fecha]`.

    Dos garantías, y las dos importan:

    - **Nunca toca una fila existente.** Si moviste una frontera a mano, sigue donde la
      pusiste; el generador se limita a añadir por los extremos.
    - **Sin huecos.** Los ciclos nuevos arrancan exactamente donde acaba el último que
      había (o acaban donde empieza el primero), así `fin(n) == inicio(n+1)` se sostiene
      por construcción y ningún movimiento puede quedar huérfano.

    Se extiende por los dos lados a propósito: un import del banco puede traer una
    transacción con fecha vieja, anterior al primer ciclo que ya existía.
    """
    if primera_fecha is None or ultima_fecha is None:
        return []
    if ultima_fecha < primera_fecha:
        primera_fecha, ultima_fecha = ultima_fecha, primera_fecha

    existentes = CicloStorage.get_ciclos(group_id)
    pendientes: List[Dict[str, Any]] = []

    if not existentes:
        cursor = frontera_en_o_antes(primera_fecha, dia_corte)
        while cursor <= ultima_fecha:
            fin = frontera_siguiente(cursor, dia_corte)
            pendientes.append({
                'group_id': group_id,
                'inicio': cursor.isoformat(),
                'fin': fin.isoformat(),
            })
            cursor = fin
        return CicloStorage.crear_muchos(pendientes)

    primer_inicio = a_fecha(existentes[0]['inicio'])
    ultimo_fin = a_fecha(existentes[-1]['fin'])

    # Hacia atrás: tramos que terminan justo donde empieza el primero que ya había.
    if primer_inicio is not None and primera_fecha < primer_inicio:
        hacia_atras: List[Dict[str, Any]] = []
        fin = primer_inicio
        while fin > primera_fecha:
            inicio = frontera_en_o_antes(fin - timedelta(days=1), dia_corte)
            # Una frontera que no retrocede dejaría el bucle girando en el sitio.
            if inicio >= fin:
                break
            hacia_atras.append({
                'group_id': group_id,
                'inicio': inicio.isoformat(),
                'fin': fin.isoformat(),
            })
            fin = inicio
        pendientes.extend(reversed(hacia_atras))

    # Hacia adelante: desde donde acabó el último, respetando su frontera aunque la
    # hayas movido a mano.
    if ultimo_fin is not None:
        cursor = ultimo_fin
        while cursor <= ultima_fecha:
            fin = frontera_siguiente(cursor, dia_corte)
            pendientes.append({
                'group_id': group_id,
                'inicio': cursor.isoformat(),
                'fin': fin.isoformat(),
            })
            cursor = fin

    return CicloStorage.crear_muchos(pendientes)


def mover_frontera(ciclo_id: str, nueva_fecha: date) -> Optional[List[Dict[str, Any]]]:
    """Mueve el límite entre un ciclo y el anterior, cambiando las dos filas a la vez.

    La unidad editable es **la frontera, no el ciclo**: si se pudieran editar `inicio` y
    `fin` por separado, la primera mitad de la edición dejaría un hueco o un solape. Así
    la contigüidad no se puede romper desde la UI ni por accidente.

    Devuelve los ciclos tocados, o None si el movimiento no es válido (el primer ciclo no
    tiene frontera anterior que mover, y ninguna frontera puede saltarse a sus vecinas).
    """
    ciclo = CicloStorage.get_ciclo(ciclo_id)
    if ciclo is None:
        return None

    ciclos = CicloStorage.get_ciclos(ciclo['group_id'])
    posicion = next((i for i, c in enumerate(ciclos) if c['id'] == ciclo_id), None)
    if posicion is None or posicion == 0:
        return None

    anterior = ciclos[posicion - 1]
    inicio_anterior = a_fecha(anterior['inicio'])
    fin_actual = a_fecha(ciclo['fin'])
    if inicio_anterior is None or fin_actual is None:
        return None
    # La frontera vive estrictamente entre el arranque del anterior y el cierre de este:
    # fuera de ahí uno de los dos ciclos quedaría vacío o invertido.
    if not (inicio_anterior < nueva_fecha < fin_actual):
        return None

    fecha = nueva_fecha.isoformat()
    tocados = [
        CicloStorage.actualizar(anterior['id'], {'fin': fecha}),
        CicloStorage.actualizar(ciclo_id, {'inicio': fecha}),
    ]
    return [c for c in tocados if c is not None]


def ciclo_de_fecha(ciclos: List[Dict[str, Any]], fecha: date) -> Optional[Dict[str, Any]]:
    """El ciclo que contiene la fecha: `inicio <= fecha < fin`."""
    for ciclo in ciclos:
        inicio = a_fecha(ciclo['inicio'])
        fin = a_fecha(ciclo['fin'])
        if inicio is not None and fin is not None and inicio <= fecha < fin:
            return ciclo
    return None
