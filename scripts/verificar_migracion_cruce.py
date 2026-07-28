"""
Verifica contra Supabase que la migración del cruce quedó bien aplicada.

Solo lee: comprueba las columnas nuevas, el backfill de `cruce_id` y que la función SQL
`estado_cuenta` dé exactamente lo mismo que el motor local `reading.py` para todos los
deudores. No invoca `aplicar_cruce` ni `registrar_pago` (esos escriben).

    python scripts/verificar_migracion_cruce.py
"""
import json
import sys
import urllib.error
import urllib.request
from collections import defaultdict

sys.path.insert(0, ".")

SUPABASE_URL = "https://rcmdzvbxerumzxvnubfo.supabase.co"
SUPABASE_KEY = "sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw"
TOL = 0.011
CAMPOS = ("neto", "total_pendiente", "total_te_deben", "total_tu_debes",
          "saldo_favor", "saldo_favor_owner", "monto_ideal_a_cruzar")
# Divergencias `neto != ledger` ya documentadas en el plan de pruebas (§8).
CONOCIDAS = ("E19", "E23", "E24", "E25", "B02", "B04")

HEAD = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"}


def get(path, rango=None):
    h = dict(HEAD)
    if rango:
        h["Range"] = rango
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=h)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def tabla(nombre, select="*"):
    filas, desde = [], 0
    while True:
        lote = get(f"{nombre}?select={select}&order=id", f"{desde}-{desde + 999}")
        filas.extend(lote)
        if len(lote) < 1000:
            return filas
        desde += 1000


def rpc(nombre, args, intentos=3):
    """Con reintentos: la red se corta de vez en cuando y son decenas de llamadas."""
    for i in range(intentos):
        try:
            req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/rpc/{nombre}",
                                         data=json.dumps(args).encode(),
                                         headers=HEAD, method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except (TimeoutError, urllib.error.URLError):
            if i == intentos - 1:
                raise


def main():
    from contabilidad.debts.reading import _construir_flujo_cuenta

    print("── Columnas nuevas ──")
    try:
        muestra = get("pagos?select=id,cruce_id,idem_key&limit=1")
        print("  ✓ pagos.cruce_id e idem_key existen")
    except urllib.error.HTTPError as e:
        print(f"  ✗ no se pueden leer: {e.read().decode()[:200]}")
        return 1

    pagos = tabla("pagos")
    comp = [p for p in pagos if p.get("es_compensacion")]
    con_id = [p for p in comp if p.get("cruce_id")]
    grupos = defaultdict(list)
    for p in con_id:
        grupos[p["cruce_id"]].append(p)
    impares = [k for k, v in grupos.items() if len(v) != 2]
    print(f"  compensaciones: {len(comp)} · con cruce_id: {len(con_id)} · "
          f"sin pareja (esperado en las mal formadas): {len(comp) - len(con_id)}")
    print(f"  {'✓' if not impares else '✗'} cruces emparejados de a dos: "
          f"{len(grupos) - len(impares)}/{len(grupos)}")

    print("\n── Función estado_cuenta ──")
    deudores = tabla("deudores", "id,nombre")
    try:
        rpc("estado_cuenta", {"p_deudor_id": deudores[0]["id"]})
        print("  ✓ el RPC responde con la anon key")
    except urllib.error.HTTPError as e:
        print(f"  ✗ el RPC falla: {e.read().decode()[:300]}")
        return 1

    deudas = tabla("deudas")
    detalles = tabla("detalle_pagos")
    d_por_deudor, p_por_deudor = defaultdict(list), defaultdict(list)
    for d in deudas:
        d_por_deudor[str(d["deudor_id"])].append(d)
    for p in pagos:
        p_por_deudor[str(p["deudor_id"])].append(p)
    deudor_de_pago = {str(p["id"]): str(p["deudor_id"]) for p in pagos}
    det_por_deudor = defaultdict(list)
    for x in detalles:
        did = deudor_de_pago.get(str(x["pago_id"]))
        if did:
            det_por_deudor[did].append(x)

    print("\n── estado_cuenta() vs reading.py, deudor por deudor ──")
    fallos, ledger_raro, revisados = [], [], 0
    for dd in deudores:
        did = str(dd["id"])
        if not d_por_deudor[did] and not p_por_deudor[did]:
            continue
        revisados += 1
        py = _construir_flujo_cuenta(d_por_deudor[did], p_por_deudor[did], det_por_deudor[did])
        sq = rpc("estado_cuenta", {"p_deudor_id": did})
        for k in CAMPOS:
            a, b = float(py["resumen"][k]), float(sq["resumen"][k])
            if abs(a - b) > TOL:
                fallos.append((dd["nombre"], k, a, b))
        movs = py["movimientos"]
        ledger = movs[0]["saldo_acumulado"] if movs else 0.0
        if abs(ledger - py["resumen"]["neto"]) > TOL:
            ledger_raro.append((dd["nombre"], py["resumen"]["neto"], ledger))

    print(f"  {revisados} deudores revisados")
    print(f"  {'✓' if not fallos else '✗'} discrepancias SQL vs Python: {len(fallos)}")
    for f in fallos:
        print(f"      {f[0]}: {f[1]} py={f[2]} sql={f[3]}")

    inesperados = [x for x in ledger_raro if not any(k in x[0] for k in CONOCIDAS)]
    print(f"  {'✓' if not inesperados else '✗'} invariante neto==ledger: "
          f"{len(ledger_raro)} divergencias "
          f"({len(ledger_raro) - len(inesperados)} conocidas, {len(inesperados)} inesperadas)")
    for x in inesperados:
        print(f"      {x[0]}: neto={x[1]} ledger={x[2]}")

    ok = not (fallos or inesperados or impares)
    print("\nTODO OK" if ok else "\nHAY PROBLEMAS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
