"""
Concurrencia de las propuestas y de la aceptación automática (fases 6.4 y 8.4 de
deudas/PLAN_MULTIUSUARIO.md).

    contabilidad/backend/.venv/bin/python scripts/v2/probar_concurrencia_propuestas.py \
        [--destino local] [--rondas 25] [--semilla 1]

Dos cuentas temporales, A y B, se vinculan por el flujo real (invitación, canje y una
conciliación vacía). Desde la fase 8 lo nuevo entra solo en la libreta del otro (y crea su
espejo en la misma transacción), así que en cada ronda los DOS, a la vez y en dos hilos,
hacen primero lo mismo (registrar_pago de un pago que RECIBEN: cada uno crea el espejo
en la libreta del otro, el choque de candados más probable; sin `_candado_vinculo` se
traban con 40P01) y después, en orden al azar:
  * anotar una deuda (REST, como el sync de Flutter): entra sola, o nace propuesta si ya
    se pasó el tope diario (decisión 24);
  * registrar un pago (registrar_pago: cruce + FIFO; si lo recibe, crea el espejo del otro
    y reparte en SU libreta);
  * subir un pago directo (REST), en cualquier dirección;
  * rechazar algo que anotó el otro (rechazar_fila, §4.2 en las dos libretas);
  * proponer un cambio de monto a algo propio acordado (proponer_cambio);
  * responder lo pendiente: pagos por confirmar, cambios y lo que pasó el tope.
Chocar con lo que el otro acaba de hacer (un cambio ya pendiente, una fila que el otro
rechazó, una propuesta que se anuló) es parte del juego: esas respuestas del servidor
(22023, 23505) se cuentan aparte, no son fallos.

Al final, cada uno acepta lo que le quede y se comprueba:
  * ningún error sin manejar (un 500, o un 40P01 que llegue al cliente);
  * ningún deadlock en la base (`pg_stat_database.deadlocks` antes y después): PostgREST
    reintenta solo un 40P01, así que el cliente no lo ve; solo tarda un segundo más
    (el `deadlock_timeout`). Así se vio que faltaba `_candado_vinculo` (fase 8);
  * verificar_vinculo().ok: lo acordado de A es lo de B con el signo cambiado;
  * en cada libreta, ningún pago virtual con sobrante, ninguna deuda ni pago con más
    repartido que su monto, y nada repartido sobre una fila rechazada;
  * la edge get_estado_cuenta trae el mismo saldo acordado, y get_historial no muestra lo
    rechazado.
Las dos cuentas se borran al terminar (la cascada se lleva sus libretas y el vínculo),
salvo con `--conservar` (para mirar el resultado, p. ej. con verificar_vinculos.py; la
siguiente corrida las reutiliza y las borra). Solo contra local, o contra la nube de
PRUEBA: crea y borra cuentas.
"""
import argparse
import os
import random
import re
import sys
import tempfile
import threading
import uuid
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comun import Cliente, conexion, sql  # noqa: E402
from crear_usuario import crear_o_encontrar  # noqa: E402

CUENTAS = {"A": "concurrencia-a@deudas.local", "B": "concurrencia-b@deudas.local"}
CLAVE = "concurrencia-local-123"
# Respuestas del servidor que son carreras normales entre los dos, no fallos.
ESPERABLES = {"22023", "23505"}


def sesion(destino, quien):
    url, anon = conexion(destino, rol="anon")
    c = Cliente(url, anon)
    c.uid = c.iniciar_sesion(CUENTAS[quien], CLAVE)
    return c


def codigo_de(error):
    m = re.search(r'"code":\s*"(\w+)"', str(error))
    return m.group(1) if m else None


def deadlocks(destino):
    """Deadlocks detectados en la base desde siempre (contador de Postgres)."""
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
        f.write("SELECT deadlocks FROM pg_stat_database WHERE datname = current_database()")
    try:
        return int(sql(destino, f.name)[0]["deadlocks"])
    finally:
        os.unlink(f.name)


def pendientes(c):
    return c.pedir("GET", f"/rest/v1/propuestas?select=id&para_usuario=eq.{c.uid}"
                          "&estado=eq.pendiente&order=created_at,id")


def acordadas(c, deudor, del_otro):
    """Mis filas acordadas del vínculo: las que anotó el otro (`origen_id`) o las mías."""
    filtro = "not.is.null" if del_otro else "is.null"
    filas = []
    for tabla, entidad in (("deudas", "deuda"), ("pagos", "pago")):
        for f in c.pedir("GET", f"/rest/v1/{tabla}?select=id&deudor_id=eq.{deudor}"
                                f"&estado_acuerdo=eq.acordada&origen_id={filtro}&order=id"):
            filas.append((entidad, f["id"]))
    return filas


def revisar_libreta(c, deudor, quien):
    """Lista de problemas de cuadre en la libreta de `c` para su deudor del vínculo."""
    deudas = {d["id"]: d for d in c.pedir(
        "GET", f"/rest/v1/deudas?select=id,monto,estado_acuerdo&deudor_id=eq.{deudor}")}
    pagos = {p["id"]: p for p in c.pedir(
        "GET", f"/rest/v1/pagos?select=id,monto_total,es_compensacion,estado_acuerdo&deudor_id=eq.{deudor}")}
    detalles = [d for d in c.pedir("GET", "/rest/v1/detalle_pagos?select=pago_id,deuda_id,monto_asignado")
                if d["pago_id"] in pagos]
    por_deuda, por_pago = {}, {}
    for d in detalles:
        por_deuda[d["deuda_id"]] = por_deuda.get(d["deuda_id"], 0) + d["monto_asignado"]
        por_pago[d["pago_id"]] = por_pago.get(d["pago_id"], 0) + d["monto_asignado"]
    malos = []
    for i, p in pagos.items():
        asignado = round(por_pago.get(i, 0), 2)
        if p["es_compensacion"] and abs(asignado - p["monto_total"]) > 0.001:
            malos.append(f"{quien}: cruce {i} con sobrante ({asignado} de {p['monto_total']})")
        if asignado > p["monto_total"] + 0.001:
            malos.append(f"{quien}: pago {i} con más repartido que su monto")
        if p["estado_acuerdo"] == "rechazada" and asignado:
            malos.append(f"{quien}: pago rechazado {i} con reparto")
    for i, d in deudas.items():
        asignado = round(por_deuda.get(i, 0), 2)
        if asignado > d["monto"] + 0.001:
            malos.append(f"{quien}: deuda {i} con más repartido que su monto")
        if d["estado_acuerdo"] == "rechazada" and asignado:
            malos.append(f"{quien}: deuda rechazada {i} con reparto")
    return malos, deudas, pagos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default="local", choices=["local", "nube"])
    ap.add_argument("--rondas", type=int, default=25)
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--conservar", action="store_true", help="no borrar las cuentas al terminar")
    a = ap.parse_args()
    rng = random.Random(a.semilla)

    admin = Cliente(*conexion(a.destino))
    ids = {q: crear_o_encontrar(admin, e, CLAVE, f"Prueba {q}") for q, e in CUENTAS.items()}
    # Si quedaron de una corrida con --conservar, se empieza de cero.
    for uid in ids.values():
        admin.pedir("DELETE", f"/auth/v1/admin/users/{uid}")
    ids = {q: crear_o_encontrar(admin, e, CLAVE, f"Prueba {q}") for q, e in CUENTAS.items()}
    try:
        A, B = sesion(a.destino, "A"), sesion(a.destino, "B")
        deudor = {"A": str(uuid.uuid4()), "B": str(uuid.uuid4())}
        A.pedir("POST", "/rest/v1/deudores", {"id": deudor["A"], "nombre": "Bea"})
        B.pedir("POST", "/rest/v1/deudores", {"id": deudor["B"], "nombre": "Ana"})
        codigo = A.rpc("crear_invitacion", {"p_deudor_id": deudor["A"]})
        vinculo = B.rpc("reclamar_invitacion", {"p_codigo": codigo, "p_deudor_existente": deudor["B"]})
        A.rpc("confirmar_conciliacion", {"p_vinculo_id": vinculo})
        estado = B.rpc("confirmar_conciliacion", {"p_vinculo_id": vinculo})["estado"]
        assert estado == "activo", estado

        errores = []
        deadlocks_antes = deadlocks(a.destino)
        cuenta = {k: 0 for k in ("deudas", "pagos", "rechazos", "cambios", "aceptadas",
                                 "rechazadas", "choques")}
        cerrojo = threading.Lock()
        hoy = date(2026, 9, 1)

        def sumar(clave):
            with cerrojo:
                cuenta[clave] += 1

        def turno(c, quien, barrera, ronda, r):
            fecha = (hoy + timedelta(days=ronda)).isoformat()
            acciones = ["deuda", "pago", "pago_directo", "rechazo", "cambio", "bandeja"]
            r.shuffle(acciones)
            acciones.insert(0, "pago_recibido")
            barrera.wait()
            for acc in acciones:
                try:
                    if acc == "deuda":
                        c.pedir("POST", "/rest/v1/deudas", {
                            "deudor_id": deudor[quien], "titulo": f"{quien} ronda {ronda}",
                            "monto": r.randint(1, 30), "es_mi_deuda": r.random() < 0.4,
                            "fecha_gasto": fecha})
                        sumar("deudas")
                    elif acc in ("pago", "pago_recibido"):
                        c.rpc("registrar_pago", {
                            "p_deudor_id": deudor[quien], "p_monto": r.randint(1, 12),
                            "p_es_mi_pago": acc == "pago" and r.random() < 0.5, "p_fecha": fecha,
                            "p_idem_key": str(uuid.uuid4())})
                        sumar("pagos")
                    elif acc == "pago_directo":
                        c.pedir("POST", "/rest/v1/pagos", {
                            "deudor_id": deudor[quien], "monto_total": r.randint(1, 8),
                            "es_mi_pago": r.random() < 0.5, "fecha_pago": fecha})
                        sumar("pagos")
                    elif acc == "rechazo":
                        filas = acordadas(c, deudor[quien], del_otro=True)
                        if filas and r.random() < 0.3:
                            entidad, fila = r.choice(filas)
                            c.rpc("rechazar_fila", {"p_entidad": entidad, "p_fila": fila,
                                                    "p_motivo": "prueba"})
                            sumar("rechazos")
                    elif acc == "cambio":
                        filas = [f for f in acordadas(c, deudor[quien], del_otro=False) if f[0] == "deuda"]
                        if filas and r.random() < 0.3:
                            _, fila = r.choice(filas)
                            actual = c.pedir("GET", f"/rest/v1/deudas?select=monto&id=eq.{fila}")
                            if actual:
                                c.rpc("proponer_cambio", {
                                    "p_entidad": "deuda", "p_fila": fila, "p_tipo": "editar",
                                    "p_payload": {"monto": actual[0]["monto"] + 1},
                                    "p_idem_key": str(uuid.uuid4())})
                                sumar("cambios")
                    else:
                        for p in pendientes(c):
                            if r.random() < 0.7:
                                c.rpc("aceptar_propuesta", {"p_id": p["id"], "p_crear_nueva": True,
                                                            "p_idem_key": str(uuid.uuid4())})
                                sumar("aceptadas")
                            else:
                                c.rpc("rechazar_propuesta", {"p_id": p["id"], "p_motivo": "prueba"})
                                sumar("rechazadas")
                except Exception as e:  # noqa: BLE001 — lo inesperado es un fallo de la prueba
                    if codigo_de(e) in ESPERABLES:
                        sumar("choques")
                    else:
                        errores.append(f"ronda {ronda}, {quien}, {acc}: {e}")

        for ronda in range(a.rondas):
            barrera = threading.Barrier(2)
            hilos = [threading.Thread(target=turno, args=(c, q, barrera, ronda, random.Random(rng.random())))
                     for c, q in ((A, "A"), (B, "B"))]
            for h in hilos:
                h.start()
            for h in hilos:
                h.join()

        # Cierre: cada uno acepta lo que le quedó (sin carreras ya).
        for c in (A, B):
            for p in pendientes(c):
                c.rpc("aceptar_propuesta", {"p_id": p["id"], "p_crear_nueva": True})
                cuenta["aceptadas"] += 1

        ver = A.rpc("verificar_vinculo", {"p_vinculo_id": vinculo})
        malos = []
        trabas = deadlocks(a.destino) - deadlocks_antes
        if trabas:
            malos.append(f"{trabas} deadlocks en la base (PostgREST los reintentó sin avisar)")
        for c, q in ((A, "A"), (B, "B")):
            m, deudas, _ = revisar_libreta(c, deudor[q], q)
            malos += m
            ec = c.pedir("POST", "/functions/v1/get_estado_cuenta", {"deudor_id": deudor[q]})
            esperado = ver["neto_a"] if q == "A" else ver["neto_b"]
            if ec["resumen"].get("saldo_acordado") != esperado:
                malos.append(f"{q}: la edge da saldo_acordado {ec['resumen'].get('saldo_acordado')}, "
                             f"verificar_vinculo {esperado}")
            hi = c.pedir("POST", "/functions/v1/get_historial", {"deudor_id": deudor[q]})
            rechazadas = {i for i, d in deudas.items() if d["estado_acuerdo"] == "rechazada"}
            if any(it["type"] == "deuda" and it["id"] in rechazadas for it in hi):
                malos.append(f"{q}: el historial muestra deudas rechazadas")

        print(f"{a.rondas} rondas: {cuenta['deudas']} deudas, {cuenta['pagos']} pagos, "
              f"{cuenta['rechazos']} filas rechazadas, {cuenta['cambios']} cambios propuestos, "
              f"{cuenta['aceptadas']} propuestas aceptadas y {cuenta['rechazadas']} rechazadas; "
              f"{cuenta['choques']} choques esperables (22023/23505)")
        print(f"verificar_vinculo: {ver}")
        for e in errores + malos:
            print("  ✗", e)
        if errores or malos or not ver["ok"]:
            print("FALLÓ")
            return 1
        print("TODO OK: sin errores de concurrencia, invariante y cuadre en las dos libretas.")
        return 0
    finally:
        for uid in ([] if a.conservar else ids.values()):
            admin.pedir("DELETE", f"/auth/v1/admin/users/{uid}")
            admin.pedir("DELETE", f"/rest/v1/borrados?owner_id=eq.{uid}")


if __name__ == "__main__":
    sys.exit(main())
