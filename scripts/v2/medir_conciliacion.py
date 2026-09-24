"""
Mide `candidatos_conciliacion` con datos reales (fase 5.2 de deudas/PLAN_MULTIUSUARIO.md).

    contabilidad/backend/.venv/bin/python scripts/v2/medir_conciliacion.py \
        --email dueno@deudas.local --clave dueno-local-123 [--deudor <uuid>] [--semilla 7]

SOLO LOCAL (nunca en la nube: copia datos reales a otra cuenta). Toma un deudor real del
dueño, crea una cuenta "espejo" que anotó lo mismo desde el otro lado con ruido:
  * fechas corridas ±2 días;
  * títulos distintos (minúsculas, solo la primera palabra, o uno genérico);
  * le faltan 2 deudas del dueño y tiene 2 de más;
vincula a los dos, pide los candidatos como el dueño y compara contra la verdad. Al final
borra la cuenta espejo (la cascada se lleva su libreta y el vínculo).
"""
import argparse
import os
import random
import sys
import uuid
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comun import Cliente, conexion  # noqa: E402
from crear_usuario import crear_o_encontrar  # noqa: E402

ESPEJO_EMAIL = "espejo-conciliacion@deudas.local"
ESPEJO_CLAVE = "espejo-local-123"


def titulo_con_ruido(rng, t):
    r = rng.random()
    if r < 0.35:
        return t.lower()
    if r < 0.65:
        return (t.split() or [t])[0].lower()
    if r < 0.8:
        return "gasto"
    return t


def fecha_con_ruido(rng, f):
    return (date.fromisoformat(f) + timedelta(days=rng.randint(-2, 2))).isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--clave", required=True)
    ap.add_argument("--deudor", help="por defecto, el que más deudas tiene")
    ap.add_argument("--semilla", type=int, default=7)
    a = ap.parse_args()
    rng = random.Random(a.semilla)

    url, service = conexion("local")
    admin = Cliente(url, service)
    _, anon = conexion("local", rol="anon")
    dueno = Cliente(url, anon)
    dueno_id = dueno.iniciar_sesion(a.email, a.clave)

    deudas = [d for d in admin.tabla("deudas") if d["owner_id"] == dueno_id]
    pagos = [p for p in admin.tabla("pagos")
             if p["owner_id"] == dueno_id and not p["es_compensacion"]]
    if a.deudor:
        deudor = a.deudor
    else:
        conteo = {}
        for d in deudas:
            conteo[d["deudor_id"]] = conteo.get(d["deudor_id"], 0) + 1
        deudor = max(conteo, key=conteo.get)
    deudas = [d for d in deudas if d["deudor_id"] == deudor]
    pagos = [p for p in pagos if p["deudor_id"] == deudor]

    espejo_id = crear_o_encontrar(admin, ESPEJO_EMAIL, ESPEJO_CLAVE, "Espejo")
    try:
        su_deudor = str(uuid.uuid4())
        admin.pedir("POST", "/rest/v1/deudores",
                    {"id": su_deudor, "nombre": "Sebas", "owner_id": espejo_id})

        verdad = {}  # id del dueño → id espejo
        faltan = set(d["id"] for d in rng.sample(deudas, min(2, len(deudas))))
        filas_deudas = []
        for d in deudas:
            if d["id"] in faltan:
                continue
            nuevo = str(uuid.uuid4())
            verdad[d["id"]] = nuevo
            filas_deudas.append({
                "id": nuevo, "deudor_id": su_deudor, "owner_id": espejo_id,
                "titulo": titulo_con_ruido(rng, d["titulo"]), "monto": d["monto"],
                "fecha_gasto": fecha_con_ruido(rng, d["fecha_gasto"]),
                "es_mi_deuda": not d["es_mi_deuda"],
            })
        for i in range(2):  # de más: montos que no están en la libreta del dueño
            filas_deudas.append({
                "id": str(uuid.uuid4()), "deudor_id": su_deudor, "owner_id": espejo_id,
                "titulo": f"extra {i}", "monto": 0.37 + i, "fecha_gasto": "2026-09-01",
                "es_mi_deuda": True,
            })
        filas_pagos = []
        for p in pagos:
            nuevo = str(uuid.uuid4())
            verdad[p["id"]] = nuevo
            filas_pagos.append({
                "id": nuevo, "deudor_id": su_deudor, "owner_id": espejo_id,
                "monto_total": p["monto_total"], "fecha_pago": fecha_con_ruido(rng, p["fecha_pago"]),
                "es_mi_pago": not p["es_mi_pago"], "es_compensacion": False,
            })
        if filas_deudas:
            admin.pedir("POST", "/rest/v1/deudas", filas_deudas)
        if filas_pagos:
            admin.pedir("POST", "/rest/v1/pagos", filas_pagos)

        vinculo = str(uuid.uuid4())
        admin.pedir("POST", "/rest/v1/vinculos", {
            "id": vinculo, "usuario_a": dueno_id, "deudor_a": deudor,
            "usuario_b": espejo_id, "deudor_b": su_deudor,
        })

        cand = dueno.rpc("candidatos_conciliacion", {"p_vinculo_id": vinculo})
        pares = cand["pares"]
        bien = [p for p in pares if verdad.get(p["mia"]) == p["suya"]]
        mal = [p for p in pares if verdad.get(p["mia"]) != p["suya"]]
        encontrados = {p["mia"] for p in bien}
        perdidos = [k for k in verdad if k not in encontrados]
        mal_seguros = [p for p in mal if not p["dudoso"]]
        bien_dudosos = [p for p in bien if p["dudoso"]]

        print(f"Deudor {deudor}: {len(deudas)} deudas y {len(pagos)} pagos del dueño; "
              f"{len(verdad)} con pareja real en la libreta espejo")
        print(f"  pares propuestos            {len(pares)}")
        print(f"  correctos                   {len(bien)}  (de ellos marcados dudosos: {len(bien_dudosos)})")
        print(f"  incorrectos                 {len(mal)}  (de ellos NO dudosos: {len(mal_seguros)})")
        print(f"  parejas reales no halladas  {len(perdidos)}")
        print(f"  solo mías / solo suyas      {len(cand['mias']) - len(pares)} / {len(cand['suyas']) - len(pares)}")
        for p in mal_seguros:
            print("  ✗ incorrecto sin marcar dudoso:", p)
        return 1 if mal_seguros else 0
    finally:
        admin.pedir("DELETE", f"/auth/v1/admin/users/{espejo_id}")
        admin.pedir("DELETE", f"/rest/v1/borrados?owner_id=eq.{espejo_id}")


if __name__ == "__main__":
    sys.exit(main())
