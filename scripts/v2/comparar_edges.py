"""
Compara las edge functions de v2 contra las de producción, deudor por deudor.

    contabilidad/backend/.venv/bin/python scripts/v2/comparar_edges.py \
        --destino local --email dueno@deudas.local --clave …

Para cada deudor de producción:
  * visor (token, accion estado|historial)  ==  get_estado_cuenta / get_historial de prod con pov 'debtor'
  * get_estado_cuenta / get_historial de v2 con el JWT del dueño  ==  las de prod con pov 'owner'
  * visor accion deudor devuelve el nombre y NO el id.

Solo lee (las edges de prod solo leen). Requiere que v2 tenga los mismos datos que prod
(importados del respaldo) y que prod no haya cambiado desde entonces: si difiere, primero
se comprueba con comparar_linea_base.py --destino prod.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comun import Cliente, conexion  # noqa: E402


LISTAS_SIN_ORDEN = ("detalles", "linkedCruceDetails", "parciales")


def _sin_orden(item):
    """Copia del ítem con sus sublistas ordenadas: en v1 salían en orden físico."""
    x = dict(item)
    for k in LISTAS_SIN_ORDEN:
        if isinstance(x.get(k), list):
            x[k] = sorted(x[k], key=lambda e: json.dumps(e, sort_keys=True))
    return x


def comparar_historial(ref, obt):
    """
    (iguales, n_movidas). El historial de v1 no tenía ORDER BY: las deudas empatadas en
    (fecha, created_at) y los detalles de cada pago salían en orden físico. Por eso se
    exige igualdad EXACTA de cada fila (menos su saldo intermedio, que depende del orden),
    del conjunto de filas y del saldo final; y se informa aparte cuántas cambiaron de
    posición o de saldo intermedio, para revisarlas.
    """
    if not isinstance(ref, list) or not isinstance(obt, list) or len(ref) != len(obt):
        return False, 0
    clave = lambda it: (it.get("type"), it.get("id"))  # noqa: E731
    sin_saldo = lambda it: {k: v for k, v in _sin_orden(it).items() if k != "balance"}  # noqa: E731
    a = {clave(it): sin_saldo(it) for it in ref}
    b = {clave(it): sin_saldo(it) for it in obt}
    if a != b:
        return False, 0
    if ref and ref[0].get("balance") != obt[0].get("balance"):
        return False, 0
    movidas = sum(1 for x, y in zip(ref, obt)
                  if clave(x) != clave(y) or x.get("balance") != y.get("balance"))
    return True, movidas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", required=True, choices=["local", "nube"])
    ap.add_argument("--email", required=True)
    ap.add_argument("--clave", required=True)
    a = ap.parse_args()

    prod = Cliente(*conexion("prod"))
    v2_anon = Cliente(*conexion(a.destino, rol="anon"))
    v2_dueno = Cliente(*conexion(a.destino, rol="anon"))
    v2_dueno.iniciar_sesion(a.email, a.clave)

    deudores = prod.tabla("deudores", select="id,nombre,token")
    fallos, comparados, movidas = [], 0, []

    def comparar(nombre, que, esperado, obtenido):
        nonlocal comparados
        comparados += 1
        if esperado != obtenido:
            fallos.append((nombre, que, esperado, obtenido))

    for d in deudores:
        for pov in ("debtor", "owner"):
            ref_ec = prod.pedir("POST", "/functions/v1/get_estado_cuenta", {"deudor_id": d["id"], "pov": pov})
            ref_hi = prod.pedir("POST", "/functions/v1/get_historial", {"deudor_id": d["id"], "pov": pov})
            if pov == "debtor":
                ec = v2_anon.pedir("POST", "/functions/v1/visor", {"token": d["token"], "accion": "estado"})
                hi = v2_anon.pedir("POST", "/functions/v1/visor", {"token": d["token"], "accion": "historial"})
            else:
                ec = v2_dueno.pedir("POST", "/functions/v1/get_estado_cuenta", {"deudor_id": d["id"], "pov": pov})
                hi = v2_dueno.pedir("POST", "/functions/v1/get_historial", {"deudor_id": d["id"], "pov": pov})
            comparar(d["nombre"], f"estado/{pov}", ref_ec, ec)
            comparados += 1
            iguales, n = comparar_historial(ref_hi, hi)
            if not iguales:
                fallos.append((d["nombre"], f"historial/{pov}", ref_hi, hi))
            elif n:
                movidas.append(f"{d['nombre']} ({pov}): {n} filas")

        quien = v2_anon.pedir("POST", "/functions/v1/visor", {"token": d["token"], "accion": "deudor"})
        comparar(d["nombre"], "visor/deudor", {"nombre": d["nombre"], "moneda": "USD"}, quien)

    print(f"{comparados} respuestas comparadas, {len(fallos)} diferencias")
    if movidas:
        print("Historiales con el mismo contenido pero otro orden en empates (v1 no tenía ORDER BY):")
        for m in movidas:
            print(f"  · {m}")
    for nombre, que, esp, obt in fallos[:10]:
        print(f"\n✗ {nombre} — {que}")
        print(f"    prod: {json.dumps(esp, ensure_ascii=False)[:300]}")
        print(f"    v2:   {json.dumps(obt, ensure_ascii=False)[:300]}")
    if fallos:
        sys.exit(1)
    print("Las edges de v2 responden igual que las de producción.")


if __name__ == "__main__":
    main()
