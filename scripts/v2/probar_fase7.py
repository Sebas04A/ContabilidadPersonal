"""
Fase 7 de deudas/PLAN_MULTIUSUARIO.md, de punta a punta por la API real:

    contabilidad/backend/.venv/bin/python scripts/v2/probar_fase7.py [--destino local]

Dos cuentas temporales, A y B, se vinculan por el flujo real (invitación, canje y una
conciliación vacía). Cada una anota una deuda, que entra sola en la libreta del otro
(fase 8), y B anota un pago que entregó, que espera a que A lo confirme. Después:
  * A exporta sus datos (`exportar_mis_datos`): solo lo suyo (su deuda y el espejo de la
    de B), las propuestas en que es parte y sus avisos;
  * B prueba un código que no existe: `reclamar_invitacion` responde null, no un error;
  * el visor responde con el token de A y, pasadas las 60 consultas del minuto, da 429;
  * A borra su cuenta (edge `borrar_cuenta`): sin la palabra de confirmación, 400; con
    ella, la cuenta desaparece, no le quedan lápidas, y B conserva su libreta: lo acordado
    sigue acordado (su deuda y el espejo de la de A) y el pago que esperaba vuelve a
    `local`.
B se borra al final. Solo contra local, o contra la nube de PRUEBA: crea y borra cuentas.
Ojo: la prueba del límite deja la IP de esta máquina sin visor durante un minuto.
"""
import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comun import Cliente, conexion  # noqa: E402
from crear_usuario import crear_o_encontrar  # noqa: E402

CUENTAS = {"A": "fase7-a@deudas.local", "B": "fase7-b@deudas.local"}
CLAVE = "fase7-local-123"


def sesion(destino, quien):
    url, anon = conexion(destino, rol="anon")
    c = Cliente(url, anon)
    c.uid = c.iniciar_sesion(CUENTAS[quien], CLAVE)
    return c


def estado_http(fn):
    """Código HTTP de una llamada que puede fallar (200 si no falla)."""
    try:
        fn()
        return 200
    except RuntimeError as e:
        return int(str(e).split("→ ")[1].split(":")[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default="local", choices=["local", "nube"])
    a = ap.parse_args()

    admin = Cliente(*conexion(a.destino))
    uids = {q: crear_o_encontrar(admin, e, CLAVE, nombre=f"Fase7 {q}") for q, e in CUENTAS.items()}
    fallos = []

    def comprobar(ok, que):
        print(("  ✓ " if ok else "  ✗ ") + que)
        if not ok:
            fallos.append(que)

    try:
        A, B = sesion(a.destino, "A"), sesion(a.destino, "B")

        # A anota a "Bea" y la invita; B canjea con un contacto nuevo; conciliación vacía.
        deudor_a, token_a = str(uuid.uuid4()), str(uuid.uuid4())
        A.pedir("POST", "/rest/v1/deudores", {"id": deudor_a, "nombre": "Bea", "token": token_a})
        codigo = A.rpc("crear_invitacion", {"p_deudor_id": deudor_a})
        vinculo = B.rpc("reclamar_invitacion", {"p_codigo": codigo})
        A.rpc("confirmar_conciliacion", {"p_vinculo_id": vinculo})
        B.rpc("confirmar_conciliacion", {"p_vinculo_id": vinculo})
        deudor_b = B.pedir("GET", f"/rest/v1/vinculos?select=deudor_b&id=eq.{vinculo}")[0]["deudor_b"]
        A.pedir("POST", "/rest/v1/deudas", {"deudor_id": deudor_a, "titulo": "Cena", "monto": 20,
                                            "fecha_gasto": "2026-09-20", "es_mi_deuda": False})
        B.pedir("POST", "/rest/v1/deudas", {"id": str(uuid.uuid4()), "deudor_id": deudor_b,
                                            "titulo": "Taxi", "monto": 5,
                                            "fecha_gasto": "2026-09-21", "es_mi_deuda": False})
        B.pedir("POST", "/rest/v1/pagos", {"deudor_id": deudor_b, "monto_total": 3,
                                           "fecha_pago": "2026-09-22", "es_mi_pago": True})

        print("Exportar mis datos")
        exp = A.rpc("exportar_mis_datos", {})
        comprobar([d["id"] for d in exp["deudores"]] == [deudor_a], "A exporta solo su contacto")
        comprobar(sorted(d["titulo"] for d in exp["deudas"]) == ["Cena", "Taxi"]
                  and {d["owner_id"] for d in exp["deudas"]} == {uids["A"]},
                  "y solo sus deudas: la suya y el espejo de la de B")
        comprobar(len(exp["propuestas"]) == 3, "y las 3 propuestas en que es parte")
        comprobar(sorted(x["tipo"] for x in exp["avisos"]) == ["deuda_nueva", "pago_por_confirmar"],
                  "y sus avisos")

        print("Canje con un código que no sirve")
        comprobar(B.rpc("reclamar_invitacion", {"p_codigo": "NOEXISTE00"}) is None,
                  "responde null, no un error")

        print("Visor")
        # Contador limpio: si no, una corrida anterior en el mismo minuto ya tiene la IP frenada.
        admin.pedir("DELETE", "/rest/v1/visitas_visor?n=gte.0")
        url, anon = conexion(a.destino, rol="anon")
        visor = Cliente(url, anon)
        estado = visor.pedir("POST", "/functions/v1/visor", {"token": token_a, "accion": "deudor"})
        comprobar(estado == {"nombre": "Bea", "moneda": "USD"}, "responde con el token de A")
        # La ventana es el minuto del reloj: si la ráfaga cruza el cambio de minuto, el 429
        # llega más tarde (hasta 60 + 61 consultas). Nunca antes de la 61 del minuto.
        codigos = []
        while len(codigos) < 125 and (not codigos or codigos[-1] != 429):
            codigos.append(estado_http(lambda: visor.pedir(
                "POST", "/functions/v1/visor", {"token": "no-existe", "accion": "deudor"})))
        comprobar(codigos[-1] == 429 and len(codigos) >= 60 and set(codigos[:-1]) == {404},
                  f"pasadas las 60 consultas del minuto da 429 (a la consulta {len(codigos) + 1}, "
                  "contando la del token bueno)")

        print("Borrar la cuenta de A")
        comprobar(estado_http(lambda: A.pedir("POST", "/functions/v1/borrar_cuenta", {})) == 400,
                  "sin la palabra de confirmación, 400")
        r = A.pedir("POST", "/functions/v1/borrar_cuenta", {"confirmar": "BORRAR"})
        comprobar(r == {"borrada": True}, "con ella, borrada")
        comprobar(estado_http(lambda: sesion(a.destino, "A")) == 400, "A ya no puede entrar")
        comprobar(admin.pedir("GET", f"/rest/v1/borrados?select=id&owner_id=eq.{uids['A']}") == [],
                  "no quedan lápidas de A")
        comprobar(admin.pedir("GET", f"/rest/v1/deudores?select=id&owner_id=eq.{uids['A']}") == [],
                  "ni su libreta")
        propias = B.pedir("GET", f"/rest/v1/deudas?select=titulo,estado_acuerdo&deudor_id=eq.{deudor_b}"
                                 "&order=titulo")
        comprobar(propias == [{"titulo": "Cena", "estado_acuerdo": "acordada"},
                              {"titulo": "Taxi", "estado_acuerdo": "acordada"}],
                  "B conserva lo acordado: su deuda y el espejo de la de A")
        pagos = B.pedir("GET", f"/rest/v1/pagos?select=estado_acuerdo&deudor_id=eq.{deudor_b}")
        comprobar(pagos == [{"estado_acuerdo": "local"}], "y el pago que esperaba vuelve a local")
        comprobar(B.pedir("GET", "/rest/v1/vinculos?select=id") == [], "y ya no tiene vínculo")
    finally:
        for uid in uids.values():
            try:
                admin.pedir("DELETE", f"/auth/v1/admin/users/{uid}")
            except RuntimeError:
                pass  # A ya se borró sola

    if fallos:
        print(f"\nFALLARON {len(fallos)}")
        sys.exit(1)
    print("\nTODO OK")


if __name__ == "__main__":
    main()
