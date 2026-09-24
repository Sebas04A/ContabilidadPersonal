"""
Revisión de todos los vínculos vivos (fase 6.7 de deudas/PLAN_MULTIUSUARIO.md).

    contabilidad/backend/.venv/bin/python scripts/v2/verificar_vinculos.py [--destino local|nube]

Corre `verificar_vinculo()` sobre cada vínculo `activo` o `conciliando` con la key de
servicio (la función la deja pasar sin sesión) y lista los que no cuadran: lo acordado
de un lado tiene que ser exactamente lo del otro con el signo cambiado, y cada fila
acordada tiene que estar en un acuerdo. Solo lee.

Sale con código 1 si alguno no cuadra, para poder programarlo (cron, GitHub Actions) y
que avise. Programarlo en la nube es decisión del dueño (§9 del plan).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comun import Cliente, conexion  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default="local", choices=["local", "nube"])
    a = ap.parse_args()

    admin = Cliente(*conexion(a.destino))
    vinculos = admin.pedir("GET", "/rest/v1/vinculos?select=id,estado&estado=neq.roto&order=created_at")
    malos = []
    for v in vinculos:
        r = admin.rpc("verificar_vinculo", {"p_vinculo_id": v["id"]})
        if not r["ok"]:
            malos.append(r)
    print(f"{len(vinculos)} vínculos revisados, {len(malos)} no cuadran")
    for r in malos:
        print(f"  ✗ {r['vinculo_id']} ({r['estado']}): neto_a {r['neto_a']}, neto_b {r['neto_b']}, "
              f"filas sin pareja {r['filas_sin_pareja']}")
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
