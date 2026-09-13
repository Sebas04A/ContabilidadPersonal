"""
Compara `estado_cuenta` en Supabase contra la línea base capturada antes de migrar.

    python scripts/verificar_estado_cuenta_equivalente.py backups/estado_cuenta_baseline_20260910

Solo lee. Falla si algún estado difiere, o si los datos cambiaron entre la captura y
ahora (en ese caso la comparación no vale y hay que recapturar antes de migrar).
"""
import json
import os
import sys
import urllib.request

SUPABASE_URL = "https://rcmdzvbxerumzxvnubfo.supabase.co"
SUPABASE_KEY = "sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw"
CABECERAS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def pedir(ruta, cuerpo=None):
    req = urllib.request.Request(
        SUPABASE_URL + ruta,
        headers=CABECERAS,
        data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
        method="POST" if cuerpo is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else "backups/estado_cuenta_baseline_20260910"
    if not os.path.isdir(carpeta):
        sys.exit(f"No existe la carpeta de línea base: {carpeta}")

    deudores_base = json.load(open(os.path.join(carpeta, "_deudores.json"), encoding="utf-8"))
    deudores_hoy = pedir("/rest/v1/deudores?select=id,nombre&order=id")

    if [d["id"] for d in deudores_base] != [d["id"] for d in deudores_hoy]:
        sys.exit("Los deudores cambiaron desde la captura: recaptura la línea base.")

    fallos, comparados = [], 0
    for d in deudores_hoy:
        for pov in ("owner", "debtor"):
            ruta_f = os.path.join(carpeta, f"{d['id']}__{pov}.json")
            if not os.path.exists(ruta_f):
                continue
            antes = json.load(open(ruta_f, encoding="utf-8"))
            ahora = pedir("/rest/v1/rpc/estado_cuenta",
                          {"p_deudor_id": d["id"], "p_pov": pov})
            comparados += 1
            if antes != ahora:
                fallos.append((d["nombre"], pov, antes, ahora))

    print(f"{comparados} estados comparados, {len(fallos)} diferencias")
    for nombre, pov, antes, ahora in fallos:
        print(f"\n✗ {nombre} ({pov})")
        print(f"    resumen antes: {json.dumps(antes.get('resumen'), sort_keys=True)}")
        print(f"    resumen ahora: {json.dumps(ahora.get('resumen'), sort_keys=True)}")

    if fallos:
        sys.exit(f"\n{len(fallos)} estados difieren. Revierte la migración.")
    print("Equivalencia confirmada.")


if __name__ == "__main__":
    main()
