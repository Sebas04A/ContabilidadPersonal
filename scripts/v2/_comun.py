"""
Piezas compartidas por los scripts de la migración a Deudas v2 (`deudas/PLAN_MULTIUSUARIO.md`).

Un "destino" es a qué base se habla:

    prod   la base actual (rcmdzvbxerumzxvnubfo). Solo se LEE: backups y líneas base.
    local  el stack local de Supabase levantado en deudas/v2 (`supabase start`).
    nube   el proyecto v2 en la nube (ref ggzvxehcsorlbroucbkp); URL y keys salen de
           deudas/v2/.env (DEUDAS_V2_URL, DEUDAS_V2_ANON_KEY, DEUDAS_V2_SERVICE_KEY).

Solo usa la biblioteca estándar: en esta máquina no hay psycopg ni psql, así que todo pasa
por la API REST (lecturas y RPC) o por `supabase db query` (SQL crudo).
"""
import json
import os
import subprocess
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V2 = os.path.join(RAIZ, "deudas", "v2")
SUPABASE_CLI = os.path.expanduser("~/.local/bin/supabase")

PROD_URL = "https://rcmdzvbxerumzxvnubfo.supabase.co"
# Anon key pública: con las policies actuales tiene SELECT sobre todo (ver §1.5 del plan).
PROD_KEY = "sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw"

# La CLI espera Docker; en esta máquina el stack local corre sobre el socket de Podman
# (`systemctl --user enable --now podman.socket`).
os.environ.setdefault(
    "DOCKER_HOST", f"unix://{os.environ.get('XDG_RUNTIME_DIR', '/run/user/1000')}/podman/podman.sock")

# Orden de inserción: cada tabla después de aquellas a las que apunta.
TABLAS = ["deudores", "deudas", "pagos", "detalle_pagos", "cruces_editados", "pagos_editados"]
PAGINA = 1000


def _estado_local():
    """URL y keys del stack local, tal como las imprime `supabase status`."""
    r = subprocess.run([SUPABASE_CLI, "status", "-o", "json", "--workdir", V2],
                       capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise SystemExit(f"El stack local no responde (¿`supabase start`?):\n{r.stderr}")
    # La CLI a veces antepone avisos a la salida JSON.
    return json.loads(r.stdout[r.stdout.index("{"):])


def _env_nube():
    """
    Variables del proyecto v2 en la nube: las del entorno pisan las de deudas/v2/.env.
    Ese archivo NO se versiona (.gitignore) y tiene la contraseña de la base y la key
    secreta; ver deudas/PLAN_MULTIUSUARIO.md §6.4.
    """
    valores = {}
    ruta = os.path.join(V2, ".env")
    if os.path.exists(ruta):
        for linea in open(ruta, encoding="utf-8"):
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                valores[k.strip()] = v.strip()
    valores.update({k: v for k, v in os.environ.items() if k.startswith("DEUDAS_V2_")})
    return valores


def conexion(destino, rol="service_role"):
    """(url, key) del destino. En local, `rol` elige entre la key anon y la service_role."""
    if destino == "prod":
        return PROD_URL, PROD_KEY
    if destino == "local":
        st = _estado_local()
        return st["API_URL"], st["SERVICE_ROLE_KEY" if rol == "service_role" else "ANON_KEY"]
    if destino == "nube":
        env = _env_nube()
        nombre = "DEUDAS_V2_SERVICE_KEY" if rol == "service_role" else "DEUDAS_V2_ANON_KEY"
        url, key = env.get("DEUDAS_V2_URL"), env.get(nombre)
        if not url or not key:
            raise SystemExit(f"Falta DEUDAS_V2_URL / {nombre} (en deudas/v2/.env o en el entorno).")
        return url, key
    raise SystemExit(f"Destino desconocido: {destino}")


class Cliente:
    """Cliente REST mínimo. `token` es el JWT con el que se actúa (por defecto, la key)."""

    def __init__(self, url, key, token=None):
        self.url, self.key, self.token = url.rstrip("/"), key, token or key

    def pedir(self, metodo, ruta, cuerpo=None, cabeceras=None):
        h = {"apikey": self.key, "Content-Type": "application/json"}
        # Las keys nuevas (sb_publishable_…, sb_secret_…) no son JWT: van solo en `apikey`
        # y la plataforma arma el rol. En Authorization solo viaja un JWT (el de un usuario
        # o las keys legacy / locales, que sí lo son).
        if self.token.startswith("eyJ"):
            h["Authorization"] = f"Bearer {self.token}"
        h.update(cabeceras or {})
        data = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(self.url + ruta, data=data, headers=h, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                crudo = r.read()
                return json.loads(crudo) if crudo else None
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{metodo} {ruta} → {e.code}: {e.read().decode()[:500]}") from None

    def tabla(self, nombre, select="*"):
        """Tabla completa, paginando para no toparse con el límite de filas del API."""
        filas, desde = [], 0
        while True:
            lote = self.pedir("GET", f"/rest/v1/{nombre}?select={select}&order=id",
                              cabeceras={"Range": f"{desde}-{desde + PAGINA - 1}"})
            filas.extend(lote)
            if len(lote) < PAGINA:
                return filas
            desde += PAGINA

    def rpc(self, funcion, args):
        return self.pedir("POST", f"/rest/v1/rpc/{funcion}", args)

    def iniciar_sesion(self, email, clave):
        """Cambia el token por el JWT de un usuario (email + contraseña)."""
        r = self.pedir("POST", "/auth/v1/token?grant_type=password",
                       {"email": email, "password": clave})
        self.token = r["access_token"]
        return r["user"]["id"]


def sql(destino, archivo):
    """Ejecuta un archivo SQL con la CLI. Devuelve la salida JSON ya parseada (o texto)."""
    if destino == "local":
        args = ["--local"]
    elif destino == "nube":
        args = ["--linked"]
    else:
        raise SystemExit("SQL crudo solo contra local o nube: prod no se escribe.")
    r = subprocess.run([SUPABASE_CLI, "db", "query", *args, "-f", archivo, "-o", "json",
                        "--workdir", V2], capture_output=True, text=True, timeout=600)
    if r.returncode:
        raise RuntimeError(f"supabase db query falló:\n{r.stderr or r.stdout}")
    # La salida JSON es {"rows": [...], "boundary": …, "warning": …}, a veces con avisos antes.
    try:
        return json.loads(r.stdout[r.stdout.index("{"):]).get("rows", [])
    except ValueError:
        return r.stdout
