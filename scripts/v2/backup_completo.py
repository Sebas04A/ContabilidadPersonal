"""
Respaldo COMPLETO de la base de deudas a JSON, para importarlo en v2.

A diferencia de `scripts/backup_deudas_supabase.py`, incluye las bitácoras
`cruces_editados` y `pagos_editados`: sin ellas v2 perdería el historial de ediciones.
Solo lee.

    contabilidad/backend/.venv/bin/python scripts/v2/backup_completo.py [--destino prod] [carpeta]

Escribe backups/deudas_v2_origen_<fecha>/<tabla>.json y un _conteos.json.
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comun import RAIZ, TABLAS, Cliente, conexion  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta", nargs="?", help="por defecto backups/deudas_v2_origen_<fecha>")
    ap.add_argument("--destino", default="prod", choices=["prod", "local", "nube"])
    a = ap.parse_args()

    carpeta = a.carpeta or os.path.join(
        RAIZ, "backups", f"deudas_v2_origen_{datetime.now():%Y%m%d_%H%M%S}")
    os.makedirs(carpeta, exist_ok=True)
    cli = Cliente(*conexion(a.destino))

    conteos = {}
    for tabla in TABLAS:
        filas = cli.tabla(tabla)
        with open(os.path.join(carpeta, f"{tabla}.json"), "w", encoding="utf-8") as f:
            json.dump(filas, f, ensure_ascii=False, indent=2, default=str)
        conteos[tabla] = len(filas)
        print(f"  {tabla:16} {len(filas):5} filas")

    with open(os.path.join(carpeta, "_conteos.json"), "w", encoding="utf-8") as f:
        json.dump(conteos, f, indent=2)
    print(f"\nRespaldo en {carpeta}")


if __name__ == "__main__":
    main()
