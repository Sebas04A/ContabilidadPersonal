"""
Respaldo de las tablas de deudas de Supabase a JSON.

Se corre ANTES de aplicar migraciones sobre la base real. Solo lee (usa la anon key, que
tiene SELECT público por las policies) y escribe un archivo por tabla con la fecha:

    python scripts/backup_deudas_supabase.py [destino]

Para restaurar una tabla se puede recorrer el JSON y hacer upsert por `id`.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime

SUPABASE_URL = "https://rcmdzvbxerumzxvnubfo.supabase.co"
SUPABASE_KEY = "sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw"
TABLAS = ["deudores", "deudas", "pagos", "detalle_pagos"]
PAGINA = 1000


def traer(tabla):
    """Baja una tabla completa, paginando para no toparse con el límite del API."""
    filas, desde = [], 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{tabla}?select=*&order=id"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Range": f"{desde}-{desde + PAGINA - 1}",
        })
        with urllib.request.urlopen(req, timeout=60) as r:
            lote = json.loads(r.read())
        filas.extend(lote)
        if len(lote) < PAGINA:
            return filas
        desde += PAGINA


def main():
    destino = sys.argv[1] if len(sys.argv) > 1 else "backups"
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta = os.path.join(destino, f"deudas_{sello}")
    os.makedirs(carpeta, exist_ok=True)

    total = 0
    for tabla in TABLAS:
        filas = traer(tabla)
        ruta = os.path.join(carpeta, f"{tabla}.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(filas, f, ensure_ascii=False, indent=2, default=str)
        print(f"  {tabla:15} {len(filas):5} filas -> {ruta}")
        total += len(filas)

    print(f"\n{total} filas respaldadas en {carpeta}")


if __name__ == "__main__":
    main()
