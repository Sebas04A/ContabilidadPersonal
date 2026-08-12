"""
limpiar_ajustes_redundantes.py — Borra los dos `ajuste` que contaban plata dos veces.

Los sembró `scripts/sembrar_posiciones_inversion.py` en la fase 2, antes de que existiera
el tipo `flujo`. Los dos modelan «la plata se aparta y vuelve», pero en los dos casos la
plata que apartan **ya está contada** por el certificado que se canceló ese mismo día.

`siembra-uni-madre-tarjeta` — 3.228, `Uni`, 2024-09-04 → 2024-09-23
    El 2024-09-04 el CDT de 10.278 devuelve 10.482,64. Las dos filas que el usuario tiene
    escritas para ese tramo suman 7.258 + 3.228 = 10.486 ≈ eso mismo: la segunda fila
    etiqueta una parte, no añade dinero. Y el 09-23 la plata se reparte en 6.648 (nuevo
    CDT) + 3.834,64 (matrícula) = 10.482,64 exacto, sin hueco para 3.228 más. Con el
    ajuste, el escalón generado del 2024-09-04 salía 7.245,41 en vez de 10.473,41.

`siembra-madre-647` — 647, `Madre`, 2025-12-22 → 2026-03-02
    Su nota lo dice: «los 647 que sobraron». Un sobrante *es* el residual, no una posición
    aparte. Tras los dos retiros de 4.900 de diciembre el residual aterriza solo en 646,97.

Reversible: `--rehacer` no existe a propósito — para recrearlos habría que volver a
ponerlos en el script de siembra, que es justo lo que no queremos. El respaldo de
`posiciones.csv` y `movimientos.csv` está en sus `.bak`.

    python scripts/limpiar_ajustes_redundantes.py --preview
    python scripts/limpiar_ajustes_redundantes.py --aplicar
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contabilidad.backend.services.investments import posiciones  # noqa: E402
from contabilidad.backend.storage.investments_storage import InvestmentStorage  # noqa: E402


REDUNDANTES = ['siembra-uni-madre-tarjeta', 'siembra-madre-647']


def _diagnostico(titulo: str) -> None:
    p = posiciones.get_neutralization_preview()
    print(f"\n{titulo}")
    for d in p['por_portafolio']:
        estado = 'CUADRA' if d['cuadra'] else 'no cuadra'
        print(f"  {d['nombre']:<20} {d['dias_materiales']:>4} de {d['dias']:>5} días   "
              f"máx {d['max_desvio']:>11,.2f}   {estado}")


def preview() -> None:
    for pid in REDUNDANTES:
        v = posiciones.get_position(pid)
        if v is None:
            print(f"  = {pid}: ya no está")
            continue
        print(f"  - {pid}: {v['fecha_apertura']} → {v['fecha_cierre']}  "
              f"cap={float(v['capital']):,.2f}  ({len(v['movimientos'])} movimientos)")
    _diagnostico("Estado actual:")


def aplicar() -> None:
    _diagnostico("ANTES:")
    borrados = 0
    for pid in REDUNDANTES:
        if InvestmentStorage.get_position(pid) is None:
            print(f"  = {pid} ya no está, se salta")
            continue
        posiciones.delete_position(pid)
        print(f"  - {pid} borrado")
        borrados += 1
    print(f"\n{borrados} ajustes borrados.")
    _diagnostico("DESPUÉS:")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--preview', action='store_true', help='muestra qué se borraría')
    grupo.add_argument('--aplicar', action='store_true', help='borra los ajustes redundantes')
    args = parser.parse_args()

    preview() if args.preview else aplicar()
