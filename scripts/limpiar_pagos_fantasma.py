"""
limpiar_pagos_fantasma.py — Borra de `pagos.csv` las filas que nadie puede ver.

`InterpolationStorage.get_payments()` hace
`dropna(subset=['id','group_id','amount','start_date','end_date'])`, así que a una fila le
basta con no tener *una* de las dos fechas para desaparecer del dashboard **y** de la
pantalla de Variables. El usuario no las ve, no puede borrarlas desde la UI, y siguen
ocupando su línea en el CSV.

Hoy no afectan a ningún número, pero son una mina: `_apply_fixed_payment` ignora las que no
tienen inicio (`if not start: return`), pero **una fila con inicio y sin fin sí se aplicaría
para siempre** en cuanto alguien arregle el `dropna` de `get_payments()`. Los 647 duplicados
de `Inversiones_Madre` son exactamente ese caso.

Las 4 filas de los datos reales, todas invisibles:

    26.000,00  Inversiones_Mias           sin inicio, fin 2024-03-28
    10.100,00  Inversiones_Uni            sin inicio, fin 2024-05-29
       647,00  Inversiones_Madre          inicio 2025-12-22, SIN FIN   ← la mina
      −600,00  Inversiones para corregir  sin inicio, fin 2025-03-21   (grupo Mis Depositos)

Las tres primeras ya están representadas en el módulo de inversiones: los 26.000 y los
10.100 como posiciones sembradas, y el sobrante de `Madre` como el residual que sale solo.
La de −600 pertenece a `Mis Depositos`, que se queda en Variables; se borra igual porque
tiene el mismo defecto y tampoco hacía nada.

    python scripts/limpiar_pagos_fantasma.py --preview
    python scripts/limpiar_pagos_fantasma.py --aplicar
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contabilidad.backend.storage.variables_storage import (  # noqa: E402
    PAYMENTS_FILE,
    InterpolationStorage,
    save_csv,
)

COLUMNAS = ['id', 'group_id', 'amount', 'start_date', 'end_date', 'note']

#: Los mismos que `get_payments()` pasa a su `dropna`.
REQUERIDAS = ['id', 'group_id', 'amount', 'start_date', 'end_date']


def _fantasmas():
    """`(df crudo, índices de las filas invisibles)`.

    Se trabaja con **índices de fila, nunca con ids**: `pagos.csv` tiene ids repetidos —
    `1a2b3c4d-…` está en dos filas, una visible de 6.675 de `Uni` y la fantasma de −600 de
    `Mis Depositos`— y `InterpolationStorage.delete_payment()` borra con
    `df[df['id'] != id]`, o sea **todas** las filas que compartan ese id. Usarlo aquí se
    habría llevado por delante un pago bueno.
    """
    df = pd.read_csv(PAYMENTS_FILE)
    for columna in COLUMNAS:
        if columna not in df.columns:
            df[columna] = None

    # Réplica exacta de lo que hace `get_payments()` antes de su dropna.
    prueba = df.copy()
    prueba['amount'] = pd.to_numeric(prueba['amount'], errors='coerce')
    prueba['start_date'] = pd.to_datetime(prueba['start_date'], errors='coerce')
    prueba['end_date'] = pd.to_datetime(prueba['end_date'], errors='coerce')
    visibles = prueba.dropna(subset=REQUERIDAS).index

    return df, [i for i in df.index if i not in set(visibles)]


def _mostrar(df, indice) -> str:
    fila = df.loc[indice]

    def txt(v):
        return '' if v is None or pd.isna(v) else str(v)[:10]

    grupo = InterpolationStorage.get_group(str(fila['group_id'])) or {}
    return (f"  línea {indice + 2:<4} {grupo.get('name', '?'):<26} "
            f"{float(fila['amount']):>10,.2f}  "
            f"inicio=[{txt(fila['start_date']):>10}] fin=[{txt(fila['end_date']):>10}]  "
            f"{txt(fila['note'])}")


def preview() -> None:
    df, fantasmas = _fantasmas()
    print(f"pagos.csv: {len(df)} filas, {len(df) - len(fantasmas)} visibles, "
          f"{len(fantasmas)} fantasma\n")
    for indice in fantasmas:
        print(_mostrar(df, indice))
    if not fantasmas:
        print("  (ninguna)")


def aplicar() -> None:
    df, fantasmas = _fantasmas()
    if not fantasmas:
        print("No hay filas fantasma que borrar.")
        return

    print(f"pagos.csv: {len(df)} filas\n")
    for indice in fantasmas:
        print(_mostrar(df, indice))

    save_csv(df.drop(index=fantasmas)[COLUMNAS], PAYMENTS_FILE)

    df2, quedan = _fantasmas()
    print(f"\n{len(fantasmas)} filas borradas. pagos.csv queda con {len(df2)} filas y "
          f"{len(quedan)} invisibles.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--preview', action='store_true', help='muestra qué se borraría')
    grupo.add_argument('--aplicar', action='store_true', help='borra las filas fantasma')
    args = parser.parse_args()

    preview() if args.preview else aplicar()
