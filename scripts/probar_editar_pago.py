"""
Prueba end-to-end de `editar_pago`: cambiar la fecha y la nota de un pago.

Crea un deudor temporal (`EDITAR PAGO TEST …`), registra un pago que cruza, edita su
fecha y su nota, y lo borra al final pase lo que pase. No toca ningún dato existente.

    python scripts/probar_editar_pago.py              # contra Supabase
    python scripts/probar_editar_pago.py --replica    # contra el contenedor `deudas-replica`

El caso: tú debes Cena $15 y Gasolina $30; él te debe Taxi $10. Pagas $10 el 10 de enero:
el cruce de $10 cierra Taxi y abona Cena, y el pago abona $5 a Cena y $5 a Gasolina.
"""
import json
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

SUPABASE_URL = "https://rcmdzvbxerumzxvnubfo.supabase.co"
SUPABASE_KEY = "sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw"
HEAD = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"}
REPLICA = "--replica" in sys.argv
OK = True


class ErrorRpc(Exception):
    pass


def _psql(sql):
    r = subprocess.run(["podman", "exec", "-i", "deudas-replica", "psql", "-U", "postgres",
                        "-d", "deudas", "-At", "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise ErrorRpc(r.stderr)
    return r.stdout.strip()


def _literal(valor):
    if valor is None:
        return "NULL"
    if isinstance(valor, bool):
        return "TRUE" if valor else "FALSE"
    if isinstance(valor, (int, float)):
        return repr(valor)
    return "'" + str(valor).replace("'", "''") + "'"


def rpc(funcion, args):
    """Llama al RPC. Un error de la función se levanta como `ErrorRpc` con el mensaje."""
    if REPLICA:
        params = ", ".join(f"{k} => {_literal(v)}" for k, v in args.items())
        return json.loads(_psql(f"SELECT {funcion}({params})"))
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/rpc/{funcion}",
                                 data=json.dumps(args).encode(), headers=HEAD, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ErrorRpc(e.read().decode()[:400]) from e


def insertar(tabla, filas):
    if REPLICA:
        crudo = json.dumps(filas).replace("'", "''")
        _psql(f"INSERT INTO {tabla} SELECT * FROM jsonb_populate_recordset(NULL::{tabla}, "
              f"'{crudo}'::jsonb)")
        return
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{tabla}",
                                 data=json.dumps(filas).encode(), headers=HEAD, method="POST")
    urllib.request.urlopen(req, timeout=30).read()


def leer(tabla, filtro):
    """Filas de una tabla con un filtro `col=eq.valor` de PostgREST."""
    if REPLICA:
        col, valor = filtro.split("=eq.")
        crudo = _psql(f"SELECT COALESCE(json_agg(t), '[]') FROM {tabla} t "
                      f"WHERE {col} = '{valor}'")
        return json.loads(crudo)
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{tabla}?{filtro}&select=*",
                                 headers=HEAD)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def borrar_deudor(deudor_id):
    if REPLICA:
        _psql(f"DELETE FROM deudores WHERE id = '{deudor_id}'")
        return
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/deudores?id=eq.{deudor_id}",
                                 headers=HEAD, method="DELETE")
    urllib.request.urlopen(req, timeout=30).read()


def check(nombre, cond, extra=""):
    global OK
    print(f"  {'✓' if cond else '✗'} {nombre}{'' if cond else '  ← ' + str(extra)}")
    OK = OK and bool(cond)


def cerca(a, b):
    return abs(float(a) - float(b)) < 0.011


def falla(nombre, fn, texto):
    """El RPC tiene que fallar con un mensaje que contenga `texto`."""
    try:
        fn()
    except ErrorRpc as e:
        check(nombre, texto in str(e), str(e)[:200])
        return
    check(nombre, False, "no falló")


def main():
    deudor_id = str(uuid.uuid4())
    cena, gasolina, taxi = (str(uuid.uuid4()) for _ in range(3))

    def pagos():
        return leer("pagos", f"deudor_id=eq.{deudor_id}")

    def saldos():
        estado = rpc("estado_cuenta", {"p_deudor_id": deudor_id})
        return {d["id"]: d["saldo_real"] for d in estado["deudas"]}, estado["resumen"]["neto"]

    try:
        print(f"Sembrando deudor temporal ({'réplica' if REPLICA else 'Supabase'})…")
        insertar("deudores", [{"id": deudor_id, "nombre": f"EDITAR PAGO TEST {deudor_id[:8]}"}])
        insertar("deudas", [
            {"id": cena, "deudor_id": deudor_id, "titulo": "Cena", "monto": 15,
             "fecha_gasto": "2026-01-01", "es_mi_deuda": True},
            {"id": taxi, "deudor_id": deudor_id, "titulo": "Taxi", "monto": 10,
             "fecha_gasto": "2026-01-02", "es_mi_deuda": False},
            {"id": gasolina, "deudor_id": deudor_id, "titulo": "Gasolina", "monto": 30,
             "fecha_gasto": "2026-01-05", "es_mi_deuda": True},
        ])

        print("\n── pagas $10 el 10 de enero: cruza $10 ──")
        r = rpc("registrar_pago", {"p_deudor_id": deudor_id, "p_monto": 10,
                                   "p_es_mi_pago": True, "p_fecha": "2026-01-10",
                                   "p_idem_key": str(uuid.uuid4())})
        pago_id = r["pago_id"] if "pago_id" in r else next(
            p["id"] for p in pagos() if not p["es_compensacion"])
        cruce_id = r["cruce"]["cruce_id"]
        check("hubo cruce", bool(cruce_id), r.get("cruce"))
        check("tres pagos: el real y los dos del cruce", len(pagos()) == 3, len(pagos()))
        saldos0, neto0 = saldos()

        print("\n── validaciones ──")
        falla("un pago que no existe",
              lambda: rpc("editar_pago", {"p_pago_id": str(uuid.uuid4()), "p_nota": "x"}),
              "No existe el pago")
        virtual = next(p["id"] for p in pagos() if p["es_compensacion"])
        falla("un pago virtual del cruce",
              lambda: rpc("editar_pago", {"p_pago_id": virtual, "p_nota": "x"}),
              "Un cruce no se edita solo")
        falla("sin cambios",
              lambda: rpc("editar_pago", {"p_pago_id": pago_id, "p_fecha": "2026-01-10"}),
              "No hay cambios")
        falla("nota de más de 500 caracteres",
              lambda: rpc("editar_pago", {"p_pago_id": pago_id, "p_nota": "a" * 501}),
              "500 caracteres")
        check("las validaciones no escribieron nada",
              not leer("pagos_editados", f"deudor_id=eq.{deudor_id}"))

        print("\n── solo la nota ──")
        r = rpc("editar_pago", {"p_pago_id": pago_id, "p_nota": "  transferencia del almuerzo  ",
                                "p_idem_key": str(uuid.uuid4())})
        real = next(p for p in pagos() if p["id"] == pago_id)
        check("nota guardada sin espacios", real["nota"] == "transferencia del almuerzo", real["nota"])
        check("solo tocó el pago real", r["pagos_movidos"] == 1, r)
        check("la fecha no cambió", all(p["fecha_pago"] == "2026-01-10" for p in pagos()))

        print("\n── la fecha arrastra al cruce ──")
        idem = str(uuid.uuid4())
        args = {"p_pago_id": pago_id, "p_fecha": "2026-01-08", "p_idem_key": idem}
        r = rpc("editar_pago", args)
        check("movió el pago y los dos del cruce", r["pagos_movidos"] == 3, r)
        check("fecha antes y después", r["fecha_antes"] == "2026-01-10" and r["fecha"] == "2026-01-08", r)
        check("los tres en el 8 de enero", all(p["fecha_pago"] == "2026-01-08" for p in pagos()),
              [p["fecha_pago"] for p in pagos()])
        check("la nota se mantiene (p_nota NULL)",
              next(p for p in pagos() if p["id"] == pago_id)["nota"] == "transferencia del almuerzo")
        saldos1, neto1 = saldos()
        check("ninguna deuda cambió de saldo",
              all(cerca(saldos1[k], v) for k, v in saldos0.items()), (saldos0, saldos1))
        check("el neto no cambió", cerca(neto1, neto0), (neto0, neto1))
        check("el cruce sigue siendo editable (created_at intacto)",
              rpc("editar_cruce", {"p_cruce_id": cruce_id, "p_simular": True})["simulado"] is True)

        r2 = rpc("editar_pago", args)
        check("reintentar no repite", r2["repetido"] is True)
        check("dos entradas en la bitácora",
              len(leer("pagos_editados", f"deudor_id=eq.{deudor_id}")) == 2)

        print("\n── borrar la nota ──")
        rpc("editar_pago", {"p_pago_id": pago_id, "p_nota": "", "p_idem_key": str(uuid.uuid4())})
        check("nota en NULL", next(p for p in pagos() if p["id"] == pago_id)["nota"] is None)

        print("\n── un pago sin cruce ──")
        r = rpc("registrar_pago", {"p_deudor_id": deudor_id, "p_monto": 5,
                                   "p_es_mi_pago": True, "p_fecha": "2026-01-12",
                                   "p_idem_key": str(uuid.uuid4())})
        suelto = next(p["id"] for p in pagos()
                      if not p["es_compensacion"] and p["fecha_pago"] == "2026-01-12")
        r = rpc("editar_pago", {"p_pago_id": suelto, "p_fecha": "2026-01-08"})
        check("mueve solo ese pago aunque otro cruce comparta la fecha nueva",
              r["pagos_movidos"] == 1, r)

    except (urllib.error.HTTPError, ErrorRpc) as e:
        detalle = e.read().decode()[:400] if isinstance(e, urllib.error.HTTPError) else str(e)[:400]
        print(f"\n✗ {detalle}")
        return 1
    finally:
        print("\nLimpiando el deudor temporal…")
        try:
            borrar_deudor(deudor_id)
            print("  ✓ borrado")
        except Exception as e:  # noqa: BLE001 — hay que avisar pase lo que pase
            print(f"  ✗ no se pudo borrar ({e}): borra a mano el deudor {deudor_id}")

    print("\nTODO OK" if OK else "\nHAY FALLOS")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
