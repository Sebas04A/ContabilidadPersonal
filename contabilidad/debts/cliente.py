"""
Cliente de Supabase de deudas, compartido por `reading.py` y `escritura.py`.

A qué base habla se decide por variables de entorno (o por `contabilidad/backend/.env`,
que no se versiona):

    DEUDAS_SUPABASE_URL   URL del proyecto. Por defecto, la base v1 de siempre.
    DEUDAS_SUPABASE_KEY   key pública (publishable). Por defecto, la de v1.
    DEUDAS_EMAIL          en Deudas v2 (multiusuario, con RLS) hay que iniciar sesión
    DEUDAS_PASSWORD       como el dueño de la libreta: sin sesión el servidor no devuelve
                          nada. En v1 no hacen falta.

Sin ninguna variable el comportamiento es exactamente el de antes (v1, sin sesión).

NUNCA la key secreta / service_role: en v2 esa key se salta el RLS y vería las libretas
de todos los usuarios (deudas/PLAN_MULTIUSUARIO.md, fase 2.4).
"""
import os

from supabase import Client, create_client

from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

URL_V1 = "https://rcmdzvbxerumzxvnubfo.supabase.co"
KEY_V1 = "sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw"

_ENV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", ".env")


def _variables() -> dict:
    """Las de `contabilidad/backend/.env`, pisadas por las del entorno."""
    valores = {}
    if os.path.exists(_ENV):
        for linea in open(_ENV, encoding="utf-8"):
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                valores[k.strip()] = v.strip()
    valores.update({k: v for k, v in os.environ.items() if k.startswith("DEUDAS_")})
    return valores


def crear_cliente() -> Client:
    v = _variables()
    url = v.get("DEUDAS_SUPABASE_URL", URL_V1)
    key = v.get("DEUDAS_SUPABASE_KEY", KEY_V1)
    if key.startswith("sb_secret_"):
        raise RuntimeError("DEUDAS_SUPABASE_KEY es una key secreta: usa la publishable (ver cliente.py).")
    cliente = create_client(url, key)
    email, clave = v.get("DEUDAS_EMAIL"), v.get("DEUDAS_PASSWORD")
    if email and clave:
        # supabase-py pasa el JWT de la sesión a PostgREST y a las RPC, y lo renueva solo.
        cliente.auth.sign_in_with_password({"email": email, "password": clave})
        logger.info("Deudas: sesión iniciada como %s en %s", email, url)
    elif url != URL_V1:
        logger.warning("Deudas: %s sin DEUDAS_EMAIL/DEUDAS_PASSWORD; con RLS no se verá nada.", url)
    return cliente
