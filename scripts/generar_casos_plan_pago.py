"""
Genera los casos con que la app comprueba que su vista previa del pago coincide con Postgres.

La pantalla de pago calcula el reparto al instante en el teléfono (`PlanPago` en Dart) y
luego lo confirma con `estado_cuenta(p_pago)`. Para que no diverjan, este script siembra
deudores SINTÉTICOS en el contenedor `deudas-replica` (dentro de una transacción que se
deshace), le pide a la función SQL cientos de vistas previas y las guarda como fixture:

    python scripts/generar_casos_plan_pago.py

    → deudas/flutter_app/test/fixtures/plan_pago_casos.json

El test `test/plan_pago_test.dart` recorre ese fichero. Hay que regenerarlo cada vez que
cambie la función SQL. Solo usa datos inventados: nada de la base real sale al repo.
"""
import json
import os
import random
import subprocess
import uuid

DESTINO = os.path.join(os.path.dirname(__file__), "..", "deudas", "flutter_app", "test",
                       "fixtures", "plan_pago_casos.json")


def psql(sql):
    r = subprocess.run(["podman", "exec", "-i", "deudas-replica", "psql", "-U", "postgres",
                        "-d", "deudas", "-At", "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise RuntimeError(r.stderr)
    return [l for l in r.stdout.splitlines() if l not in ("BEGIN", "ROLLBACK", "INSERT 0 1")
            and not l.startswith("INSERT")]


def cents(lo, hi):
    return random.randint(int(lo * 100), int(hi * 100)) / 100


def sembrar():
    """Un deudor con deudas de los dos lados, abonos parciales y pagos con sobrante."""
    deudor = str(uuid.uuid4())
    deudas, pagos, detalles = [], [], []
    for _ in range(random.randint(1, 9)):
        deudas.append({"id": str(uuid.uuid4()), "deudor_id": deudor, "titulo": "d",
                       "monto": cents(1, 90), "es_mi_deuda": random.random() < 0.5,
                       # pocas fechas distintas: los empates los desempata el id
                       "fecha_gasto": f"2026-01-0{random.randint(1, 4)}"})
    for _ in range(random.randint(0, 3)):
        lado = random.random() < 0.5
        del_lado = [d for d in deudas if d["es_mi_deuda"] == lado]
        pago = {"id": str(uuid.uuid4()), "deudor_id": deudor, "fecha_pago": "2026-01-05",
                "es_mi_pago": lado, "es_compensacion": False, "monto_total": 0}
        total = 0.0
        for d in random.sample(del_lado, k=random.randint(0, len(del_lado))):
            pagado = sum(x["monto_asignado"] for x in detalles if x["deuda_id"] == d["id"])
            falta = round(d["monto"] - pagado, 2)
            if falta <= 0.01:
                continue
            # abono parcial o completo, nunca dejando un resto de un centavo
            a = falta if random.random() < 0.4 else cents(0.01, max(falta - 0.02, 0.01))
            if falta - a == 0.01:
                a = falta
            detalles.append({"id": str(uuid.uuid4()), "pago_id": pago["id"],
                             "deuda_id": d["id"], "monto_asignado": a})
            total += a
        sobrante = cents(0.02, 40) if random.random() < 0.5 else 0
        pago["monto_total"] = round(total + sobrante, 2)
        if pago["monto_total"] > 0:
            pagos.append(pago)
        else:
            detalles = [x for x in detalles if x["pago_id"] != pago["id"]]
    return deudor, deudas, pagos, detalles


def insertar(tabla, filas):
    crudo = json.dumps(filas).replace("'", "''")
    return (f"INSERT INTO {tabla} SELECT * FROM jsonb_populate_recordset(NULL::{tabla}, "
            f"'{crudo}'::jsonb);")


def pendientes_como_la_edge(estado):
    """Lo mismo que `get_estado_cuenta` le devuelve a la app: saldos de HOY."""
    salida = []
    for d in estado["deudas"]:
        pago = d.get("pago_planeado", 0)
        saldo_hoy = round(d["saldo_pendiente"] + pago, 2)
        if saldo_hoy > 0.01:
            salida.append({**d, "saldo_pendiente": saldo_hoy,
                           "monto_pagado": round(d["monto_pagado"] - pago, 2)})
    return salida


def main():
    random.seed(20260912)
    casos = []
    while len(casos) < 400:
        deudor, deudas, pagos, detalles = sembrar()
        sql = ["BEGIN;",
               insertar("deudores", [{"id": deudor, "nombre": "sintético"}]),
               insertar("deudas", deudas)]
        if pagos:
            sql += [insertar("pagos", pagos)]
        if detalles:
            sql += [insertar("detalle_pagos", detalles)]
        sql.append(f"SELECT estado_cuenta('{deudor}');")

        planes = []
        for _ in range(6):
            lado = random.random() < 0.5
            ids = [d["id"] for d in deudas if random.random() < 0.5]
            monto = random.choice([cents(0.02, 20), cents(10, 150), 0])
            planes.append((monto, lado, ids))
            pago = json.dumps({"monto": monto, "es_mi_pago": lado, "deudas_ids": ids})
            sql.append(f"SELECT estado_cuenta('{deudor}', 'owner', '{pago}'::jsonb);")
        sql.append("ROLLBACK;")

        filas = psql("\n".join(sql))
        hoy = json.loads(filas[0])
        # El caso del centavo (una deuda con saldo de 0.01) es un defecto conocido de la
        # función: la app no ve esas deudas, así que no se puede comparar.
        if any(0 < d["saldo_real"] <= 0.01 for d in hoy["deudas"]):
            continue
        base = pendientes_como_la_edge(hoy)
        for (monto, lado, ids), fila in zip(planes, filas[1:]):
            plan = json.loads(fila)
            visibles = {d["id"] for d in base}
            casos.append({
                "deudas": [{"id": d["id"], "fecha_gasto": d["fecha_gasto"],
                            "es_tu_deuda": d["es_tu_deuda"],
                            "saldo_pendiente": d["saldo_pendiente"],
                            "monto_pagado": d["monto_pagado"],
                            "monto_original": d["monto_original"],
                            "abono_saldo_favor": d["abono_saldo_favor"],
                            "cruce_sugerido": d["cruce_sugerido"]} for d in base],
                "mi_saldo_favor": hoy["resumen"]["saldo_favor_owner"],
                "su_saldo_favor": hoy["resumen"]["saldo_favor"],
                "monto": monto, "es_mi_pago": lado, "elegidas": ids,
                "esperado": {
                    "pagos": {d["id"]: d["pago_planeado"] for d in plan["deudas"] if d["id"] in visibles},
                    "abonos": {d["id"]: d["abono_saldo_favor"] for d in plan["deudas"] if d["id"] in visibles},
                    "cruces": {d["id"]: d["cruce_sugerido"] for d in plan["deudas"] if d["id"] in visibles},
                    "sobrante": plan["resumen"]["pago_planeado"]["sobrante"],
                },
            })

    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    with open(DESTINO, "w", encoding="utf-8") as f:
        json.dump(casos, f, separators=(",", ":"))
    print(f"{len(casos)} casos -> {os.path.normpath(DESTINO)}")


if __name__ == "__main__":
    main()
