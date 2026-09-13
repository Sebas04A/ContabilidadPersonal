"""
Prueba end-to-end del pago con deudas elegidas a mano: el pago va antes que el cruce.

Crea un deudor temporal (`PAGO MANUAL TEST …`), prueba la vista previa
(`estado_cuenta` con `p_pago`) y `registrar_pago` sobre él, y lo borra al final pase lo
que pase. No toca ningún dato existente.

    python scripts/probar_pago_manual.py              # contra Supabase
    python scripts/probar_pago_manual.py --replica    # contra el contenedor `deudas-replica`

El caso base es el de LOGICA_SISTEMA.md: tú debes Cena $40 (vieja) y Gasolina $30, él te
debe Taxi $15.
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


def _psql(sql):
    r = subprocess.run(["podman", "exec", "-i", "deudas-replica", "psql", "-U", "postgres",
                        "-d", "deudas", "-At", "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise RuntimeError(r.stderr)
    return r.stdout.strip()


def _literal(valor):
    if valor is None:
        return "NULL"
    if isinstance(valor, bool):
        return "TRUE" if valor else "FALSE"
    if isinstance(valor, (int, float)):
        return repr(valor)
    if isinstance(valor, list):
        return "ARRAY[" + ",".join(f"'{v}'" for v in valor) + "]::uuid[]"
    if isinstance(valor, dict):
        return "'" + json.dumps(valor) + "'::jsonb"
    return "'" + str(valor).replace("'", "''") + "'"


def rpc(funcion, args):
    if REPLICA:
        params = ", ".join(f"{k} => {_literal(v)}" for k, v in args.items())
        return json.loads(_psql(f"SELECT {funcion}({params})"))
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/rpc/{funcion}",
                                 data=json.dumps(args).encode(), headers=HEAD, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def insertar(tabla, filas):
    if REPLICA:
        crudo = json.dumps(filas).replace("'", "''")
        _psql(f"INSERT INTO {tabla} SELECT * FROM jsonb_populate_recordset(NULL::{tabla}, "
              f"'{crudo}'::jsonb)")
        return
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{tabla}",
                                 data=json.dumps(filas).encode(), headers=HEAD, method="POST")
    urllib.request.urlopen(req, timeout=30).read()


def contar_pagos(deudor_id):
    if REPLICA:
        return int(_psql(f"SELECT count(*) FROM pagos WHERE deudor_id = '{deudor_id}'"))
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/pagos?deudor_id=eq.{deudor_id}&select=id",
                                 headers=HEAD)
    with urllib.request.urlopen(req, timeout=30) as r:
        return len(json.loads(r.read()))


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


def main():
    deudor_id = str(uuid.uuid4())
    cena, gasolina, taxi = (str(uuid.uuid4()) for _ in range(3))

    def deuda(estado, deuda_id):
        return next(d for d in estado["deudas"] if d["id"] == deuda_id)

    def plan(monto, ids, es_mi_pago=True):
        return rpc("estado_cuenta", {"p_deudor_id": deudor_id, "p_pov": "owner",
                                     "p_pago": {"monto": monto, "es_mi_pago": es_mi_pago,
                                                "deudas_ids": ids}})

    try:
        print(f"Sembrando deudor temporal ({'réplica' if REPLICA else 'Supabase'})…")
        insertar("deudores", [{"id": deudor_id, "nombre": f"PAGO MANUAL TEST {deudor_id[:8]}"}])
        insertar("deudas", [
            {"id": cena, "deudor_id": deudor_id, "titulo": "Cena", "monto": 40,
             "fecha_gasto": "2026-01-01", "es_mi_deuda": True},
            {"id": gasolina, "deudor_id": deudor_id, "titulo": "Gasolina", "monto": 30,
             "fecha_gasto": "2026-01-02", "es_mi_deuda": True},
            {"id": taxi, "deudor_id": deudor_id, "titulo": "Taxi", "monto": 15,
             "fecha_gasto": "2026-01-03", "es_mi_deuda": False},
        ])

        print("\n── sin pago: el cruce va a la más antigua ──")
        e = rpc("estado_cuenta", {"p_deudor_id": deudor_id})
        check("cruce $15 en Cena", cerca(deuda(e, cena)["cruce_sugerido"], 15))
        check("nada en Gasolina", cerca(deuda(e, gasolina)["cruce_sugerido"], 0))
        check("sin pago planeado no hay clave nueva", "pago_planeado" not in deuda(e, cena))

        print("\n── eliges Cena y pagas $30 ──")
        p = plan(30, [cena])
        check("el pago va entero a Cena", cerca(deuda(p, cena)["pago_planeado"], 30))
        check("el cruce tapa los $10 que faltan de Cena", cerca(deuda(p, cena)["cruce_sugerido"], 10))
        check("y los $5 que sobran van a Gasolina", cerca(deuda(p, gasolina)["cruce_sugerido"], 5))
        check("Taxi se cruza entero", cerca(deuda(p, taxi)["cruce_sugerido"], 15))
        check("sin sobrante", cerca(p["resumen"]["pago_planeado"]["sobrante"], 0))

        print("\n── eliges Cena y pagas solo $10: el cruce igual la rellena primero ──")
        p = plan(10, [cena])
        check("pago $10 en Cena", cerca(deuda(p, cena)["pago_planeado"], 10))
        check("cruce $15 en Cena aunque no se complete", cerca(deuda(p, cena)["cruce_sugerido"], 15))
        check("nada en Gasolina", cerca(deuda(p, gasolina)["cruce_sugerido"], 0))

        print("\n── eliges Gasolina (la nueva) y pagas $30 ──")
        p = plan(30, [gasolina])
        check("Gasolina saldada con el pago", cerca(deuda(p, gasolina)["pago_planeado"], 30))
        check("el cruce se queda en Cena", cerca(deuda(p, cena)["cruce_sugerido"], 15))

        print("\n── pagas más de lo elegido: el resto es saldo a favor ──")
        p = plan(50, [cena])
        check("pago $40 en Cena", cerca(deuda(p, cena)["pago_planeado"], 40))
        check("sobrante $10", cerca(p["resumen"]["pago_planeado"]["sobrante"], 10))
        check("el saldo a favor abona Gasolina", cerca(deuda(p, gasolina)["abono_saldo_favor"], 10))
        check("y el cruce sigue con Gasolina", cerca(deuda(p, gasolina)["cruce_sugerido"], 15))
        check("Gasolina no recibe pago directo", cerca(deuda(p, gasolina)["pago_planeado"], 0))

        print("\n── una deuda del otro lado se ignora ──")
        p = plan(5, [taxi])
        check("sin pago en Taxi", cerca(deuda(p, taxi)["pago_planeado"], 0))
        check("todo es sobrante", cerca(p["resumen"]["pago_planeado"]["sobrante"], 5))

        print("\n── registrar: se guarda lo mismo que se vio ──")
        vista = plan(30, [cena])
        idem = str(uuid.uuid4())
        args = {"p_deudor_id": deudor_id, "p_monto": 30, "p_es_mi_pago": True,
                "p_fecha": "2026-01-10", "p_idem_key": idem, "p_deudas_ids": [cena]}
        r = rpc("registrar_pago", args)
        luego = r["estado"]
        for d in vista["deudas"]:
            esperado = round(d["saldo_real"] - d["cruce_sugerido"], 2)
            check(f"{d['titulo']} queda en ${esperado}",
                  cerca(deuda(luego, d["id"])["saldo_real"], esperado),
                  deuda(luego, d["id"])["saldo_real"])
        check("el neto no se movió respecto a la vista", cerca(luego["resumen"]["neto"], vista["resumen"]["neto"]))
        check("no quedó cruce pendiente", luego["resumen"]["monto_ideal_a_cruzar"] <= 0.011)
        check("un pago real y dos virtuales", contar_pagos(deudor_id) == 3, contar_pagos(deudor_id))

        r2 = rpc("registrar_pago", args)
        check("reintentar no duplica", r2["repetido"] is True)
        check("siguen siendo tres pagos", contar_pagos(deudor_id) == 3, contar_pagos(deudor_id))

    except (urllib.error.HTTPError, RuntimeError) as e:
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
