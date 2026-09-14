"""
Prueba end-to-end de `editar_cruce`: sacar deudas del cruce de la última operación.

Crea un deudor temporal (`EDITAR CRUCE TEST …`), registra un pago que cruza, prueba la
simulación y la edición real sobre él, y lo borra al final pase lo que pase. No toca
ningún dato existente.

    python scripts/probar_editar_cruce.py              # contra Supabase
    python scripts/probar_editar_cruce.py --replica    # contra el contenedor `deudas-replica`

El caso: tú debes Cena $15 y Gasolina $30; él te debe Taxi $10 y Uber $5. Pagas $10 en
automático: el cruce de $15 cierra Cena, Taxi y Uber, y el pago abona $10 a Gasolina.
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
    if isinstance(valor, list):
        return "ARRAY[" + ",".join(f"'{v}'" for v in valor) + "]::uuid[]"
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
    cena, gasolina, taxi, uber = (str(uuid.uuid4()) for _ in range(4))

    def deuda(estado, deuda_id):
        return next(d for d in estado["deudas"] if d["id"] == deuda_id)

    def item(res, deuda_id):
        return next(i for i in res["items"] if i["deuda_id"] == deuda_id)

    def pagos():
        return leer("pagos", f"deudor_id=eq.{deudor_id}")

    try:
        print(f"Sembrando deudor temporal ({'réplica' if REPLICA else 'Supabase'})…")
        insertar("deudores", [{"id": deudor_id, "nombre": f"EDITAR CRUCE TEST {deudor_id[:8]}"}])
        insertar("deudas", [
            {"id": cena, "deudor_id": deudor_id, "titulo": "Cena", "monto": 15,
             "fecha_gasto": "2026-01-01", "es_mi_deuda": True},
            {"id": taxi, "deudor_id": deudor_id, "titulo": "Taxi", "monto": 10,
             "fecha_gasto": "2026-01-02", "es_mi_deuda": False},
            {"id": uber, "deudor_id": deudor_id, "titulo": "Uber", "monto": 5,
             "fecha_gasto": "2026-01-03", "es_mi_deuda": False},
            {"id": gasolina, "deudor_id": deudor_id, "titulo": "Gasolina", "monto": 30,
             "fecha_gasto": "2026-01-05", "es_mi_deuda": True},
        ])

        print("\n── pagas $10 en automático: cruza $15 y abona Gasolina ──")
        r = rpc("registrar_pago", {"p_deudor_id": deudor_id, "p_monto": 10,
                                   "p_es_mi_pago": True, "p_fecha": "2026-01-10",
                                   "p_idem_key": str(uuid.uuid4())})
        cruce_id = r["cruce"]["cruce_id"]
        e0 = r["estado"]
        check("hubo cruce de $15", cruce_id and cerca(r["cruce"]["aplicado"], 15), r["cruce"])
        check("Cena, Taxi y Uber saldadas",
              all(cerca(deuda(e0, x)["saldo_real"], 0) for x in (cena, taxi, uber)))
        check("Gasolina en $20", cerca(deuda(e0, gasolina)["saldo_real"], 20))

        print("\n── simular sacar Uber: el cruce baja a $10 ──")
        s = rpc("editar_cruce", {"p_cruce_id": cruce_id, "p_excluir": [uber], "p_simular": True})
        check("simulado", s["simulado"] is True)
        check("cruce de $15 a $10", cerca(s["monto_antes"], 15) and cerca(s["monto_despues"], 10),
              (s["monto_antes"], s["monto_despues"]))
        check("Cena recortada a $10", cerca(item(s, cena)["despues"], 10))
        check("Taxi se queda en $10", cerca(item(s, taxi)["despues"], 10))
        check("Uber fuera", cerca(item(s, uber)["despues"], 0) and item(s, uber)["excluida"])
        es = s["estado"]
        check("Cena queda en $5 y Uber en $5",
              cerca(deuda(es, cena)["saldo_real"], 5) and cerca(deuda(es, uber)["saldo_real"], 5))
        check("Gasolina no se mueve (el pago no se toca)", cerca(deuda(es, gasolina)["saldo_real"], 20))
        check("vuelve a haber $5 para cruzar", cerca(es["cruce_sugerido"]["monto"], 5))
        check("el neto no cambia", cerca(es["resumen"]["neto"], e0["resumen"]["neto"]),
              (es["resumen"]["neto"], e0["resumen"]["neto"]))
        check("la simulación no escribió nada",
              len(pagos()) == 3 and not leer("cruces_editados", f"deudor_id=eq.{deudor_id}"))
        cruce = [p for p in pagos() if p["cruce_id"] == cruce_id]
        check("el cruce sigue en $15", all(cerca(p["monto_total"], 15) for p in cruce))

        print("\n── validaciones ──")
        falla("una deuda que no está en el cruce",
              lambda: rpc("editar_cruce", {"p_cruce_id": cruce_id, "p_excluir": [gasolina],
                                           "p_simular": True}),
              "no están en el cruce")
        falla("lista vacía",
              lambda: rpc("editar_cruce", {"p_cruce_id": cruce_id, "p_excluir": [],
                                           "p_simular": True}),
              "ninguna deuda")
        falla("un cruce que no existe",
              lambda: rpc("editar_cruce", {"p_cruce_id": str(uuid.uuid4()), "p_simular": True}),
              "No existe el cruce")

        print("\n── sacar Uber de verdad ──")
        idem = str(uuid.uuid4())
        args = {"p_cruce_id": cruce_id, "p_excluir": [uber], "p_idem_key": idem}
        r = rpc("editar_cruce", args)
        e1 = r["estado"]
        check("no simulado", r["simulado"] is False and r["repetido"] is False)
        for x in (cena, taxi, uber, gasolina):
            check(f"{deuda(e1, x)['titulo']} igual que en la simulación",
                  cerca(deuda(e1, x)["saldo_real"], deuda(es, x)["saldo_real"]))
        cruce = [p for p in pagos() if p["cruce_id"] == cruce_id]
        check("los dos pagos virtuales en $10",
              len(cruce) == 2 and all(cerca(p["monto_total"], 10) for p in cruce))
        detalles = [d for p in cruce for d in leer("detalle_pagos", f"pago_id=eq.{p['id']}")]
        check("dos detalles: Cena y Taxi", sorted(d["deuda_id"] for d in detalles) == sorted([cena, taxi]),
              detalles)
        bitacora = leer("cruces_editados", f"deudor_id=eq.{deudor_id}")
        check("quedó en la bitácora", len(bitacora) == 1 and cerca(bitacora[0]["monto_despues"], 10))

        r2 = rpc("editar_cruce", args)
        check("reintentar no repite", r2["repetido"] is True)
        check("sigue una sola entrada", len(leer("cruces_editados", f"deudor_id=eq.{deudor_id}")) == 1)

        print("\n── deshacer el resto del cruce ──")
        r = rpc("editar_cruce", {"p_cruce_id": cruce_id, "p_excluir": None,
                                 "p_idem_key": str(uuid.uuid4())})
        e2 = r["estado"]
        check("eliminado", r["eliminado"] is True and cerca(r["monto_despues"], 0))
        check("solo queda el pago real", len(pagos()) == 1, len(pagos()))
        check("Cena $15, Taxi $10, Uber $5 pendientes",
              cerca(deuda(e2, cena)["saldo_real"], 15) and cerca(deuda(e2, taxi)["saldo_real"], 10)
              and cerca(deuda(e2, uber)["saldo_real"], 5))
        check("Gasolina sigue en $20", cerca(deuda(e2, gasolina)["saldo_real"], 20))
        check("el cruce vuelve a sugerirse entero", cerca(e2["cruce_sugerido"]["monto"], 15))
        check("el neto sigue igual", cerca(e2["resumen"]["neto"], e0["resumen"]["neto"]))

        print("\n── el siguiente pago los vuelve a cruzar ──")
        r = rpc("registrar_pago", {"p_deudor_id": deudor_id, "p_monto": 5,
                                   "p_es_mi_pago": True, "p_fecha": "2026-01-11",
                                   "p_idem_key": str(uuid.uuid4())})
        e3 = r["estado"]
        nuevo_cruce = r["cruce"]["cruce_id"]
        check("cruzó $15 otra vez", cerca(r["cruce"]["aplicado"], 15), r["cruce"])
        check("Gasolina en $15", cerca(deuda(e3, gasolina)["saldo_real"], 15))

        print("\n── un cruce que ya no es el último ──")
        insertar("pagos", [{"id": str(uuid.uuid4()), "deudor_id": deudor_id, "monto_total": 1,
                            "fecha_pago": "2026-01-12", "es_mi_pago": True,
                            "created_at": "2099-01-01T00:00:00Z"}])
        falla("se rechaza",
              lambda: rpc("editar_cruce", {"p_cruce_id": nuevo_cruce, "p_simular": True}),
              "última operación")

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
