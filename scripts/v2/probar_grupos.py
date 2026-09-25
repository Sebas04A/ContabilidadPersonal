"""
Fase 9B de deudas/PLAN_MULTIUSUARIO.md, de punta a punta por la API real (el criterio de
salida de la fase: "un grupo con 3 cuentas de prueba, con gastos, un rechazo y pagos
(confirmado y por confirmar), en el que los saldos de los tres cuadran"):

    contabilidad/backend/.venv/bin/python scripts/v2/probar_grupos.py [--destino local]

Tres cuentas temporales, A, B y C, y Dani, una persona sin app:
  * A crea el grupo y agrega a Dani; B y C entran con el enlace (`unirse_a_grupo`);
  * A paga $90 entre A, B y C → B y C le deben $30; a B y a C les llega `gasto_nuevo`;
  * B paga $60 entre los cuatro ($15 c/u); C rechaza su parte → los otros tres pasan a
    $20, el gasto queda en revisión y a A y B les llega `gasto_en_revision`; cuando los
    dos lo ven, vuelve a activo;
  * pagos: A anota que B le pagó $30 (recibe: cuenta); C anota que le pagó $30 a A
    (entrega: por confirmar, no cuenta hasta que A confirma); B anota otro de $5 y A dice
    "no lo recibí"; B anota que Dani le pagó $20 (Dani no tiene app: cuenta);
  * C no puede salir con saldo ≠ 0; cuando queda en 0 sale y deja de ver el grupo.
En cada paso, A, B y C tienen que ver los mismos pares y netos (`estado_grupo`), iguales a
los que se calculan aquí a mano, y nada de esto toca sus libretas. Al final se borran el
grupo y las cuentas. Solo contra local, o contra la nube de PRUEBA: crea y borra cuentas.
"""
import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comun import Cliente, conexion  # noqa: E402
from crear_usuario import crear_o_encontrar  # noqa: E402

CUENTAS = {"A": "grupos-a@deudas.local", "B": "grupos-b@deudas.local", "C": "grupos-c@deudas.local"}
CLAVE = "grupos-local-123"
FECHA = "2026-09-24"


def sesion(destino, quien):
    url, anon = conexion(destino, rol="anon")
    c = Cliente(url, anon)
    c.uid = c.iniciar_sesion(CUENTAS[quien], CLAVE)
    return c


def nuevo():
    return str(uuid.uuid4())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default="local", choices=["local", "nube"])
    a = ap.parse_args()

    admin = Cliente(*conexion(a.destino))
    uids = {q: crear_o_encontrar(admin, e, CLAVE, nombre=f"Grupos {q}") for q, e in CUENTAS.items()}
    grupo = nuevo()
    fallos = []

    def comprobar(ok, que):
        print(("  ✓ " if ok else "  ✗ ") + que)
        if not ok:
            fallos.append(que)

    def falla(fn):
        try:
            fn()
            return None
        except RuntimeError as e:
            return str(e)

    try:
        S = {q: sesion(a.destino, q) for q in CUENTAS}
        A, B, C = S["A"], S["B"], S["C"]

        print("Armar el grupo")
        r = A.rpc("crear_grupo", {"p_id": grupo, "p_nombre": "Viaje a la playa", "p_tipo": "viaje"})
        m = {"A": r["mi_miembro_id"]}
        m["D"] = A.rpc("agregar_persona", {"p_grupo_id": grupo, "p_nombre": "Dani", "p_id": nuevo()})["id"]
        codigo = A.rpc("invitar_a_grupo", {"p_grupo_id": grupo})
        comprobar(B.rpc("unirse_a_grupo", {"p_codigo": codigo}) == grupo
                  and C.rpc("unirse_a_grupo", {"p_codigo": codigo}) == grupo,
                  "B y C entran con el mismo enlace")
        for q in "BC":
            m[q] = A.pedir("GET", f"/rest/v1/grupo_miembros?select=id&grupo_id=eq.{grupo}"
                                  f"&usuario_id=eq.{uids[q]}")[0]["id"]
        nombre = {v: k for k, v in m.items()}

        def pares_de(quien):
            e = S[quien].rpc("estado_grupo", {"p_grupo_id": grupo})
            pares = sorted((nombre[p["debe"]], nombre[p["a"]], float(p["monto"])) for p in e["pares"])
            netos = {nombre[x["id"]]: float(x["neto"]) for x in e["miembros"]}
            return pares, netos, float(e["mi_neto"])

        def cuadran(esperado, quienes="ABC"):
            """Los pares que ve cada uno son `esperado` y su neto es el de su fila."""
            netos = {q: 0.0 for q in "ABCD"}
            for debe, acreedor, monto in esperado:
                netos[debe] -= monto
                netos[acreedor] += monto
            vistas = {q: pares_de(q) for q in quienes}
            ok = all(p == sorted(esperado) and n == netos and mio == netos[q]
                     for q, (p, n, mio) in vistas.items())
            comprobar(ok and abs(sum(netos.values())) < 0.005,
                      f"{', '.join(quienes)} ven lo mismo: "
                      + ("; ".join(f"{d} le debe ${x:g} a {c}" for d, c, x in sorted(esperado)) or "todo en 0"))
            if not ok:
                for q, v in vistas.items():
                    print(f"      {q}: {v}")

        def avisos(quien, gasto, tipo):
            return len(S[quien].pedir("GET", f"/rest/v1/avisos?select=id&gasto_id=eq.{gasto}&tipo=eq.{tipo}"))

        print("A paga $90 entre A, B y C")
        cena = nuevo()
        args = {"p_id": cena, "p_grupo_id": grupo, "p_titulo": "Cena", "p_monto": 90,
                "p_fecha": FECHA, "p_modo": "igual", "p_idem_key": nuevo(),
                "p_participantes": [{"miembro_id": m["A"], "pagado": 90},
                                    {"miembro_id": m["B"]}, {"miembro_id": m["C"]}]}
        A.rpc("crear_gasto", args)
        comprobar(A.rpc("crear_gasto", args).get("repetido") is True, "repetirlo no crea otro")
        cuadran([("B", "A", 30), ("C", "A", 30)])
        comprobar(avisos("B", cena, "gasto_nuevo") == 1 and avisos("C", cena, "gasto_nuevo") == 1
                  and avisos("A", cena, "gasto_nuevo") == 0, "avisos gasto_nuevo a B y C, no a A")

        print("B paga $60 entre los cuatro y C rechaza su parte")
        nafta = nuevo()
        B.rpc("crear_gasto", {"p_id": nafta, "p_grupo_id": grupo, "p_titulo": "Gasolina", "p_monto": 60,
                              "p_fecha": FECHA, "p_modo": "igual", "p_idem_key": nuevo(),
                              "p_participantes": [{"miembro_id": m["B"], "pagado": 60},
                                                  {"miembro_id": m["A"]}, {"miembro_id": m["C"]},
                                                  {"miembro_id": m["D"]}]})
        cuadran([("B", "A", 15), ("C", "A", 30), ("C", "B", 15), ("D", "B", 15)])
        comprobar(falla(lambda: A.rpc("editar_gasto", {
            "p_gasto_id": nafta, "p_titulo": "Gasolina", "p_monto": 1, "p_fecha": FECHA, "p_modo": "igual",
            "p_participantes": [{"miembro_id": m["B"], "pagado": 1}, {"miembro_id": m["A"]}]})) is not None,
            "A no puede editar un gasto que no anotó ni pagó")
        C.rpc("rechazar_parte", {"p_gasto_id": nafta, "p_motivo": "No fui en ese auto", "p_idem_key": nuevo()})
        cuadran([("B", "A", 10), ("C", "A", 30), ("D", "B", 20)])
        estado = A.pedir("GET", f"/rest/v1/gastos?select=estado&id=eq.{nafta}")[0]["estado"]
        comprobar(estado == "en_revision", "el gasto queda en revisión")
        comprobar(avisos("A", nafta, "gasto_en_revision") == 1 and avisos("B", nafta, "gasto_en_revision") == 1,
                  "avisos gasto_en_revision a A y B")
        for q in "AB":
            S[q].rpc("marcar_vistos", {})
        estado = B.pedir("GET", f"/rest/v1/gastos?select=estado&id=eq.{nafta}")[0]["estado"]
        comprobar(estado == "activo", "cuando los dos lo ven, vuelve a activo")

        print("Pagos")
        pago = lambda quien, de, para, monto: S[quien].rpc("registrar_pago_grupo", {  # noqa: E731
            "p_id": nuevo(), "p_grupo_id": grupo, "p_de": m[de], "p_para": m[para],
            "p_monto": monto, "p_fecha": FECHA, "p_idem_key": nuevo()})
        comprobar(pago("A", "B", "A", 30)["estado"] == "confirmado", "A anota que B le pagó $30: cuenta")
        cuadran([("A", "B", 20), ("C", "A", 30), ("D", "B", 20)])
        p_c = pago("C", "C", "A", 30)
        comprobar(p_c["estado"] == "por_confirmar", "C anota que le pagó $30 a A: por confirmar")
        cuadran([("A", "B", 20), ("C", "A", 30), ("D", "B", 20)])
        comprobar(len(A.pedir(
            "GET", "/rest/v1/avisos?select=id&tipo=eq.pago_grupo_por_confirmar")) == 1,
            "a A le llega pago_grupo_por_confirmar")
        comprobar(falla(lambda: C.rpc("salir_de_grupo", {"p_grupo_id": grupo})) is not None,
                  "C no puede salir con saldo ≠ 0")
        A.rpc("confirmar_pago_grupo", {"p_pago_id": p_c["id"]})
        cuadran([("A", "B", 20), ("D", "B", 20)])
        p_b = pago("B", "B", "A", 5)
        A.rpc("rechazar_pago_grupo", {"p_pago_id": p_b["id"], "p_motivo": "No lo recibí"})
        estado = B.pedir("GET", f"/rest/v1/grupo_pagos?select=estado,motivo&id=eq.{p_b['id']}")[0]
        comprobar(estado == {"estado": "rechazado", "motivo": "No lo recibí"},
                  "A dice que no recibió los $5 de B: rechazado, con el motivo")
        comprobar(pago("B", "D", "B", 20)["estado"] == "confirmado",
                  "B anota que Dani (sin app) le pagó $20: cuenta")
        cuadran([("A", "B", 20)])

        print("Nada de esto toca las libretas")
        comprobar(all(S[q].pedir("GET", "/rest/v1/deudas?select=id") == [] for q in "ABC"),
                  "ninguno de los tres tiene deudas en su libreta")

        print("C sale del grupo")
        C.rpc("salir_de_grupo", {"p_grupo_id": grupo, "p_idem_key": nuevo()})
        comprobar(C.pedir("GET", "/rest/v1/grupos?select=id") == []
                  and C.pedir("GET", f"/rest/v1/gastos?select=id&grupo_id=eq.{grupo}") == []
                  and C.pedir("GET", "/rest/v1/grupo_pagos?select=id") == [],
                  "con saldo 0 sale y deja de ver el grupo, sus gastos y sus pagos")
        cuadran([("A", "B", 20)], quienes="AB")
    finally:
        try:
            admin.pedir("DELETE", f"/rest/v1/grupos?id=eq.{grupo}")
        except RuntimeError as e:
            print(f"(no se pudo borrar el grupo de prueba {grupo}: {e})")
        for uid in uids.values():
            try:
                admin.pedir("DELETE", f"/auth/v1/admin/users/{uid}")
            except RuntimeError:
                pass

    if fallos:
        print(f"\nFALLARON {len(fallos)}")
        sys.exit(1)
    print("\nTODO OK")


if __name__ == "__main__":
    main()
