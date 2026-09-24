"""
Corre las pruebas end-to-end de los RPC de v1 contra v2, autenticado como un usuario de
prueba (nunca el dueño).

    contabilidad/backend/.venv/bin/python scripts/v2/probar_rpc_v2.py --destino local

No copia las pruebas: importa los cuatro scripts de `scripts/` (probar_rpc_cruce,
probar_pago_manual, probar_editar_cruce, probar_editar_pago) y les cambia la conexión.
Todos leen `SUPABASE_URL` y `HEAD` como globales en cada llamada, así que basta con
reasignarlos: pasan a hablar con v2 con el JWT del usuario de prueba, y así también
prueban que el RLS deja trabajar a un usuario normal sobre lo suyo.

Cada script crea su deudor temporal, lo ejercita y lo borra al final.
"""
import argparse
import importlib
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))  # scripts/, para importar las pruebas de v1
from _comun import Cliente, conexion  # noqa: E402
from crear_usuario import crear_o_encontrar  # noqa: E402

PRUEBAS = ["probar_rpc_cruce", "probar_pago_manual", "probar_editar_cruce", "probar_editar_pago"]
EMAIL, CLAVE = "pruebas@deudas.local", "pruebas-local-123"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", required=True, choices=["local", "nube"])
    a = ap.parse_args()

    crear_o_encontrar(Cliente(*conexion(a.destino)), EMAIL, CLAVE, "Pruebas")
    url, anon = conexion(a.destino, rol="anon")
    sesion = Cliente(url, anon)
    sesion.iniciar_sesion(EMAIL, CLAVE)

    resultados = {}
    sys.argv = sys.argv[:1]  # los scripts miran sys.argv (--replica): que no vean el nuestro
    for nombre in PRUEBAS:
        mod = importlib.import_module(nombre)
        mod.SUPABASE_URL = url
        mod.SUPABASE_KEY = anon
        mod.HEAD = {"apikey": anon, "Authorization": f"Bearer {sesion.token}",
                    "Content-Type": "application/json"}
        if hasattr(mod, "REPLICA"):
            mod.REPLICA = False
        print(f"\n{'=' * 70}\n{nombre}\n{'=' * 70}")
        resultados[nombre] = mod.main()

    print(f"\n{'=' * 70}")
    for nombre, codigo in resultados.items():
        print(f"  {'✓' if codigo == 0 else '✗'} {nombre}")
    sys.exit(0 if all(c == 0 for c in resultados.values()) else 1)


if __name__ == "__main__":
    main()
