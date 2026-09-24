"""
Compara `estado_cuenta` de un destino contra una línea base de `capturar_linea_base.py`.

    contabilidad/backend/.venv/bin/python scripts/v2/comparar_linea_base.py \
        <carpeta_linea_base> --destino local [--email E --clave C]

Sin `--email` usa la key de servicio (fase 0: no hay RLS que respetar). Con `--email`
inicia sesión y compara COMO ESE USUARIO (fase 1 en adelante: así se prueba que el RLS
deja ver al dueño exactamente lo mismo que antes).

Solo lee. La comparación es exacta, byte a byte del JSON: "casi igual" es un fallo.
Sale con código 1 si algo difiere o si los deudores no son los mismos.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comun import RAIZ, Cliente, conexion  # noqa: E402

POVS = ("owner", "debtor")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta")
    ap.add_argument("--destino", required=True, choices=["prod", "local", "nube"])
    ap.add_argument("--email")
    ap.add_argument("--clave")
    a = ap.parse_args()

    carpeta = a.carpeta if os.path.isabs(a.carpeta) else os.path.join(RAIZ, a.carpeta)
    base = json.load(open(os.path.join(carpeta, "_deudores.json"), encoding="utf-8"))

    if a.email:
        cli = Cliente(*conexion(a.destino, rol="anon"))
        cli.iniciar_sesion(a.email, a.clave)
    else:
        cli = Cliente(*conexion(a.destino))

    hoy = cli.pedir("GET", "/rest/v1/deudores?select=id,nombre&order=id")
    if [d["id"] for d in base] != [d["id"] for d in hoy]:
        sys.exit(f"Los deudores no coinciden (base {len(base)}, destino {len(hoy)}): "
                 "o cambiaron los datos o el destino no ve los mismos.")

    fallos, comparados = [], 0
    for d in hoy:
        for pov in POVS:
            ruta = os.path.join(carpeta, f"{d['id']}__{pov}.json")
            if not os.path.exists(ruta):
                continue
            antes = json.load(open(ruta, encoding="utf-8"))
            ahora = cli.rpc("estado_cuenta", {"p_deudor_id": d["id"], "p_pov": pov})
            comparados += 1
            if antes != ahora:
                fallos.append((d["nombre"], pov, antes, ahora))

    print(f"{comparados} estados comparados, {len(fallos)} diferencias")
    for nombre, pov, antes, ahora in fallos:
        print(f"\n✗ {nombre} ({pov})")
        print(f"    resumen base:    {json.dumps(antes.get('resumen'), sort_keys=True)}")
        print(f"    resumen destino: {json.dumps(ahora.get('resumen'), sort_keys=True)}")
    if fallos:
        sys.exit(1)
    print("Equivalencia confirmada.")


if __name__ == "__main__":
    main()
