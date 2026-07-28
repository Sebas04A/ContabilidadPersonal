"""
Prueba end-to-end de `aplicar_cruce` y `registrar_pago` contra Supabase.

Crea un deudor temporal (`RPC TEST …`), ejercita los RPC sobre él y lo borra al final,
pase lo que pase. No toca ningún dato existente.

    python scripts/probar_rpc_cruce.py
"""
import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date

SUPABASE_URL = "https://rcmdzvbxerumzxvnubfo.supabase.co"
SUPABASE_KEY = "sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw"
HEAD = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"}
OK = True


def pedir(metodo, path, cuerpo=None, prefer=None):
    h = dict(HEAD)
    if prefer:
        h["Prefer"] = prefer
    data = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", data=data,
                                 headers=h, method=metodo)
    with urllib.request.urlopen(req, timeout=30) as r:
        crudo = r.read()
        return json.loads(crudo) if crudo else None


def check(nombre, cond, extra=""):
    global OK
    print(f"  {'✓' if cond else '✗'} {nombre}{'' if cond else '  ← ' + str(extra)}")
    OK = OK and bool(cond)


def main():
    hoy = date.today().isoformat()
    deudor_id = str(uuid.uuid4())
    d_te_deben, d_tu_debes = str(uuid.uuid4()), str(uuid.uuid4())

    try:
        print("Sembrando deudor temporal…")
        pedir("POST", "deudores", {"id": deudor_id, "nombre": f"RPC TEST {deudor_id[:8]}"})
        pedir("POST", "deudas", [
            {"id": d_te_deben, "deudor_id": deudor_id, "titulo": "Te deben 100",
             "monto": 100, "fecha_gasto": hoy, "es_mi_deuda": False},
            {"id": d_tu_debes, "deudor_id": deudor_id, "titulo": "Tú debes 60",
             "monto": 60, "fecha_gasto": hoy, "es_mi_deuda": True},
        ])

        print("\n── estado inicial ──")
        est = pedir("POST", "rpc/estado_cuenta", {"p_deudor_id": deudor_id})
        check("neto = +40", abs(est["resumen"]["neto"] - 40) < 0.011, est["resumen"]["neto"])
        check("cruce sugerido = 60",
              abs(est["resumen"]["monto_ideal_a_cruzar"] - 60) < 0.011,
              est["resumen"]["monto_ideal_a_cruzar"])

        print("\n── aplicar_cruce ──")
        idem = str(uuid.uuid4())
        r = pedir("POST", "rpc/aplicar_cruce",
                  {"p_deudor_id": deudor_id, "p_fecha": hoy, "p_idem_key": idem})
        check("cruzó 60", abs(float(r["aplicado"]) - 60) < 0.011, r["aplicado"])
        check("el neto no cambió", abs(r["estado"]["resumen"]["neto"] - 40) < 0.011,
              r["estado"]["resumen"]["neto"])
        check("ya no queda cruce", r["estado"]["resumen"]["monto_ideal_a_cruzar"] <= 0.011)

        pagos = pedir("GET", f"pagos?deudor_id=eq.{deudor_id}&select=id,cruce_id,es_mi_pago,es_compensacion")
        comp = [p for p in pagos if p["es_compensacion"]]
        check("creó dos pagos virtuales", len(comp) == 2, len(comp))
        check("con el mismo cruce_id", len({p["cruce_id"] for p in comp}) == 1)
        check("uno por cada lado", sorted(p["es_mi_pago"] for p in comp) == [False, True])

        r2 = pedir("POST", "rpc/aplicar_cruce",
                   {"p_deudor_id": deudor_id, "p_fecha": hoy, "p_idem_key": idem})
        check("reintentar no duplica (idempotente)", r2["repetido"] is True)
        pagos2 = pedir("GET", f"pagos?deudor_id=eq.{deudor_id}&select=id&es_compensacion=is.true")
        check("siguen siendo dos", len(pagos2) == 2, len(pagos2))

        print("\n── registrar_pago del remanente ──")
        idem_pago = str(uuid.uuid4())
        r3 = pedir("POST", "rpc/registrar_pago",
                   {"p_deudor_id": deudor_id, "p_monto": 40, "p_es_mi_pago": False,
                    "p_fecha": hoy, "p_idem_key": idem_pago})
        check("queda al día", abs(r3["estado"]["resumen"]["neto"]) < 0.011,
              r3["estado"]["resumen"]["neto"])
        check("sin sobrante", abs(float(r3["sobrante"])) < 0.011, r3["sobrante"])

        r4 = pedir("POST", "rpc/registrar_pago",
                   {"p_deudor_id": deudor_id, "p_monto": 40, "p_es_mi_pago": False,
                    "p_fecha": hoy, "p_idem_key": idem_pago})
        check("reintentar el pago no duplica", r4["repetido"] is True)
        reales = pedir("GET", f"pagos?deudor_id=eq.{deudor_id}&es_compensacion=is.false&select=id")
        check("un solo pago real", len(reales) == 1, len(reales))

    except urllib.error.HTTPError as e:
        print(f"\n✗ HTTP {e.code}: {e.read().decode()[:400]}")
        return 1
    finally:
        print("\nLimpiando el deudor temporal…")
        try:
            pedir("DELETE", f"deudores?id=eq.{deudor_id}")
            resto = pedir("GET", f"deudores?id=eq.{deudor_id}&select=id")
            print("  ✓ borrado" if not resto else f"  ✗ quedó: {resto}")
        except urllib.error.HTTPError as e:
            print(f"  ✗ no se pudo borrar ({e.code}): borra a mano el deudor {deudor_id}")

    print("\nTODO OK" if OK else "\nHAY FALLOS")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
