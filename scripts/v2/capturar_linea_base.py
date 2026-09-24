"""
Captura la línea base: `estado_cuenta` de cada deudor en los dos puntos de vista.

Es la referencia contra la que se compara v2 (`comparar_linea_base.py`): mismo formato que
`backups/estado_cuenta_baseline_20260910/`, un `<deudor_id>__<pov>.json` por estado más
`_deudores.json`. Solo lee.

    contabilidad/backend/.venv/bin/python scripts/v2/capturar_linea_base.py [--destino prod] [carpeta]
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comun import RAIZ, Cliente, conexion  # noqa: E402

POVS = ("owner", "debtor")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta", nargs="?",
                    help="por defecto backups/estado_cuenta_baseline_v2_<fecha>")
    ap.add_argument("--destino", default="prod", choices=["prod", "local", "nube"])
    a = ap.parse_args()

    carpeta = a.carpeta or os.path.join(
        RAIZ, "backups", f"estado_cuenta_baseline_v2_{datetime.now():%Y%m%d_%H%M%S}")
    os.makedirs(carpeta, exist_ok=True)
    cli = Cliente(*conexion(a.destino))

    deudores = cli.pedir("GET", "/rest/v1/deudores?select=id,nombre&order=id")
    with open(os.path.join(carpeta, "_deudores.json"), "w", encoding="utf-8") as f:
        json.dump(deudores, f, ensure_ascii=False, indent=2)

    for d in deudores:
        for pov in POVS:
            estado = cli.rpc("estado_cuenta", {"p_deudor_id": d["id"], "p_pov": pov})
            ruta = os.path.join(carpeta, f"{d['id']}__{pov}.json")
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(estado, f, ensure_ascii=False, indent=2)
    print(f"{len(deudores) * len(POVS)} estados capturados en {carpeta}")


if __name__ == "__main__":
    main()
