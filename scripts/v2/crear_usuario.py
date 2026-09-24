"""
Crea (o encuentra) un usuario de Auth con email y contraseña, ya confirmado.

    contabilidad/backend/.venv/bin/python scripts/v2/crear_usuario.py \
        --destino local --email dueno@deudas.local --clave … [--nombre Sebas]

Imprime el UUID. Usa la API de administración de Auth con la key de servicio, así que
solo sirve contra local o contra un proyecto propio (nunca contra prod). El trigger
`_crear_perfil` le crea el perfil.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comun import Cliente, conexion  # noqa: E402


def crear_o_encontrar(cli, email, clave, nombre=None):
    try:
        r = cli.pedir("POST", "/auth/v1/admin/users", {
            "email": email, "password": clave, "email_confirm": True,
            "user_metadata": {"nombre": nombre} if nombre else {},
        })
        return r["id"]
    except RuntimeError as e:
        if "already" not in str(e) and "422" not in str(e):
            raise
    # Ya existía: buscarlo en la lista (pocas cuentas en local).
    pagina = 1
    while True:
        r = cli.pedir("GET", f"/auth/v1/admin/users?page={pagina}&per_page=200")
        for u in r.get("users", []):
            if u.get("email") == email:
                return u["id"]
        if len(r.get("users", [])) < 200:
            raise SystemExit(f"No se pudo crear ni encontrar a {email}")
        pagina += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", required=True, choices=["local", "nube"])
    ap.add_argument("--email", required=True)
    ap.add_argument("--clave", required=True)
    ap.add_argument("--nombre")
    a = ap.parse_args()
    print(crear_o_encontrar(Cliente(*conexion(a.destino)), a.email, a.clave, a.nombre))


if __name__ == "__main__":
    main()
