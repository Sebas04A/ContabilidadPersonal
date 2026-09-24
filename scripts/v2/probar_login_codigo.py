"""
Entrar con código por correo (Deudas v2), de punta a punta y SOLO en local:

    contabilidad/backend/.venv/bin/python scripts/v2/probar_login_codigo.py

Para una cuenta nueva y para una que ya existe: pide el correo (`/auth/v1/otp`, lo mismo
que `signInWithOtp` en la app), lo lee en Mailpit (el buzón de prueba del stack local,
:54324), comprueba que trae el código (plantilla supabase/templates/codigo.html) y entra con
él (`/auth/v1/verify` con type `email`, lo mismo que `verifyOTP` en la app). En la nube no
se puede: los correos llegan de verdad.

La cuenta de prueba se borra al terminar.
"""
import json
import os
import re
import sys
import time
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comun import Cliente, conexion  # noqa: E402

MAILPIT = "http://127.0.0.1:54324/api/v1"


def ultimo_correo(email, despues_de):
    """El último correo que llegó a `email` después del id `despues_de` (espera hasta 20 s)."""
    for _ in range(40):
        with urllib.request.urlopen(f"{MAILPIT}/search?query=to:{email}", timeout=10) as r:
            msgs = json.loads(r.read())["messages"]
        if msgs and msgs[0]["ID"] != despues_de:
            with urllib.request.urlopen(f"{MAILPIT}/message/{msgs[0]['ID']}", timeout=10) as r:
                return json.loads(r.read())
        time.sleep(0.5)
    raise SystemExit(f"No llegó el correo a {email}")


def pedir_y_entrar(anon, admin, email, que):
    previo = None
    with urllib.request.urlopen(f"{MAILPIT}/search?query=to:{email}", timeout=10) as r:
        msgs = json.loads(r.read())["messages"]
        previo = msgs[0]["ID"] if msgs else None
    anon.pedir("POST", "/auth/v1/otp", {"email": email, "create_user": True})
    m = ultimo_correo(email, previo)
    codigo = re.search(r">\s*(\d{6,10})\s*<", m["HTML"])
    fallos = []
    if m["Subject"] != "Tu código para entrar a Deudas":
        fallos.append(f"{que}: asunto inesperado {m['Subject']!r}")
    if not codigo:
        fallos.append(f"{que}: el correo no trae el código")
        return fallos
    r = anon.pedir("POST", "/auth/v1/verify", {"type": "email", "email": email, "token": codigo.group(1)})
    if not r.get("access_token"):
        fallos.append(f"{que}: el código no dio sesión")
    else:
        print(f"  ✓ {que}: correo con código {len(codigo.group(1))} dígitos → sesión")
    return fallos


def main():
    admin = Cliente(*conexion("local"))
    anon = Cliente(*conexion("local", rol="anon"))
    email = f"codigo-{uuid.uuid4().hex[:8]}@deudas.local"
    fallos = []
    try:
        fallos += pedir_y_entrar(anon, admin, email, "cuenta nueva (plantilla confirmation)")
        time.sleep(2)  # max_frequency: un correo por segundo en local
        fallos += pedir_y_entrar(anon, admin, email, "cuenta que ya existe (plantilla magic_link)")
    finally:
        for u in admin.pedir("GET", "/auth/v1/admin/users?page=1&per_page=200")["users"]:
            if u["email"] == email:
                admin.pedir("DELETE", f"/auth/v1/admin/users/{u['id']}")
                admin.pedir("DELETE", f"/rest/v1/borrados?owner_id=eq.{u['id']}")
    for f in fallos:
        print("  ✗", f)
    print("FALLÓ" if fallos else "TODO OK")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
