#!/usr/bin/env python3
"""
seed_deudas_prueba.py — Crea en Supabase un deudor por cada escenario del
PLAN_PRUEBAS_DEUDAS.md (contabilidad/debts/PLAN_PRUEBAS_DEUDAS.md).

Cada persona se llama "TEST <ID> · <situación>" para que sea obvia en la lista del
modal Estado de cuenta y en la app Flutter.

Uso:
    python scripts/seed_deudas_prueba.py            # crea los escenarios E/B del plan
    python scripts/seed_deudas_prueba.py --verify   # solo verifica lo ya sembrado
    python scripts/seed_deudas_prueba.py --clean    # borra SOLO las personas "TEST "
    python scripts/seed_deudas_prueba.py --arbol 3  # el árbol de casos_arbol.py hasta nivel 3

`--arbol N` siembra la fase 1 (solo deudas `debe`/`debo`, sin pagos) descrita en
contabilidad/debts/CASOS_ARBOL_DEUDAS.md. Ojo con el volumen: nivel 3 son 30 personas,
nivel 4 son 86 y nivel 5 son 254.

El borrado es en cascada (deudas → pagos → detalle_pagos) y nunca toca deudores reales.
"""
import argparse
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contabilidad.debts import casos_arbol  # noqa: E402
from contabilidad.debts.reading import supabase, obtener_estado_cuenta  # noqa: E402

PREFIJO = "TEST "


# ── DSL de escenarios ────────────────────────────────────────────────────────
@dataclass
class D:
    """Deuda. mine=True → 'tú debes' (es_mi_deuda), mine=False → 'te deben'."""
    key: str
    titulo: str
    monto: float
    mine: bool
    fecha: str


@dataclass
class P:
    """Pago. mine=True → entregado por mí (es_mi_pago); comp=True → cruce."""
    key: str
    monto: float
    mine: bool
    fecha: str
    asigna: dict = field(default_factory=dict)  # {deuda_key: monto_asignado}
    comp: bool = False


@dataclass
class S:
    code: str
    titulo: str
    deudas: list
    pagos: list
    neto: float          # neto esperado según la semántica documentada
    ledger: float = None  # saldo final del ledger; None ⇒ debe coincidir con neto
    nota: str = ""

    @property
    def nombre(self):
        return f"{PREFIJO}{self.code} · {self.titulo}"

    @property
    def ledger_esperado(self):
        return self.neto if self.ledger is None else self.ledger


F1, F2, F3, F4 = "2026-06-01", "2026-06-15", "2026-06-20", "2026-06-25"

ESCENARIOS = [
    # ── Bloque A: solo "te deben" ────────────────────────────────────────────
    S("E01", "Te deben, nadie paga",
      [D("d1", "Préstamo", 100, False, F1)], [], +100),

    S("E02", "Te deben, me paga exacto",
      [D("d1", "Préstamo", 100, False, F1)],
      [P("p1", 100, False, F3, {"d1": 100})], 0),

    S("E03", "Te deben, me paga parcial",
      [D("d1", "Préstamo", 100, False, F1)],
      [P("p1", 40, False, F3, {"d1": 40})], +60),

    S("E04", "Te deben, me paga de más",
      [D("d1", "Préstamo", 100, False, F1)],
      [P("p1", 150, False, F3, {"d1": 100})], -50,
      nota="sobrante 50 = saldo a favor del deudor"),

    S("E05", "Te deben x2, el sobrante abona la otra",
      [D("d1", "Préstamo 1", 100, False, F1), D("d2", "Préstamo 2", 60, False, F2)],
      [P("p1", 130, False, F3, {"d1": 100})], +30,
      nota="abono_saldo_favor 30 sobre d2"),

    S("E06", "Te deben, dos pagos parciales la cierran",
      [D("d1", "Préstamo", 100, False, F1)],
      [P("p1", 30, False, F2, {"d1": 30}), P("p2", 70, False, F3, {"d1": 70})], 0),

    S("E07", "Un pago cubre N deudas",
      [D("d1", "Cena", 50, False, F1), D("d2", "Taxi", 50, False, F1)],
      [P("p1", 100, False, F3, {"d1": 50, "d2": 50})], 0),

    S("E08", "Me paga sin deudas (anticipo)",
      [], [P("p1", 80, False, F3)], -80),

    # ── Bloque B: solo "tú debes" ────────────────────────────────────────────
    S("E09", "Debo, no pago",
      [D("d1", "Me prestó", 100, True, F1)], [], -100),

    S("E10", "Debo, pago exacto",
      [D("d1", "Me prestó", 100, True, F1)],
      [P("p1", 100, True, F3, {"d1": 100})], 0),

    S("E11", "Debo, pago parcial",
      [D("d1", "Me prestó", 100, True, F1)],
      [P("p1", 40, True, F3, {"d1": 40})], -60),

    S("E12", "Debo, pago de más",
      [D("d1", "Me prestó", 100, True, F1)],
      [P("p1", 120, True, F3, {"d1": 100})], +20,
      nota="saldo_favor_owner 20 — el modal no lo muestra hoy"),

    S("E13", "Debo x2, el sobrante abona la otra",
      [D("d1", "Me prestó 1", 100, True, F1), D("d2", "Me prestó 2", 60, True, F2)],
      [P("p1", 130, True, F3, {"d1": 100})], -30),

    S("E14", "Pago sin deudas (adelanto mío)",
      [], [P("p1", 80, True, F3)], +80),

    # ── Bloque C: mezcla y cruce ─────────────────────────────────────────────
    S("E15", "Ambas direcciones, sin pagos",
      [D("d1", "Le presté", 100, False, F1), D("d2", "Me prestó", 60, True, F2)],
      [], +40, nota="total_pendiente = 160"),

    S("E16", "Cruce parcial",
      [D("d1", "Le presté", 100, False, F1), D("d2", "Me prestó", 60, True, F2)],
      [P("c1", 60, True, F3, {"d2": 60}, comp=True),
       P("c2", 60, False, F3, {"d1": 60}, comp=True)], +40),

    S("E17", "Cruce total",
      [D("d1", "Le presté", 100, False, F1), D("d2", "Me prestó", 100, True, F2)],
      [P("c1", 100, True, F3, {"d2": 100}, comp=True),
       P("c2", 100, False, F3, {"d1": 100}, comp=True)], 0),

    S("E18", "Cruce + pago físico del remanente",
      [D("d1", "Le presté", 100, False, F1), D("d2", "Me prestó", 60, True, F2)],
      [P("c1", 60, True, F3, {"d2": 60}, comp=True),
       P("c2", 60, False, F3, {"d1": 60}, comp=True),
       P("p1", 40, False, F4, {"d1": 40})], 0),

    S("E19", "Cruce con sobrante sin asignar",
      [D("d1", "Le presté", 100, False, F1), D("d2", "Me prestó", 60, True, F2)],
      [P("c1", 60, True, F3, {"d2": 60}, comp=True),
       P("c2", 80, False, F3, {"d1": 70}, comp=True)], +30, ledger=+40,
      nota="DIVERGENCIA esperada: el sobrante de una compensación no entra al saldo a favor"),

    # ── Bloque D: temporalidad ───────────────────────────────────────────────
    S("E20", "Pago ANTES de la deuda",
      [D("d1", "Préstamo", 100, False, F3)],
      [P("p1", 100, False, F1, {"d1": 100})], 0,
      nota="saldo transitorio −100; en pantalla el pago va debajo"),

    S("E21", "Deuda y pago el mismo día",
      [D("d1", "Préstamo", 100, False, F1)],
      [P("p1", 100, False, F1, {"d1": 100})], 0,
      nota="la deuda se calcula primero; el pago se muestra arriba"),

    # ── Bloque E: dirección incoherente (invariante rota) ────────────────────
    S("E23", "Te deben pero YO pago esa deuda",
      [D("d1", "Le presté", 100, False, F1)],
      [P("p1", 50, True, F3, {"d1": 50})], +50, ledger=+150,
      nota="DIVERGENCIA esperada"),

    S("E24", "Debo pero ÉL paga esa deuda",
      [D("d1", "Me prestó", 100, True, F1)],
      [P("p1", 50, False, F3, {"d1": 50})], -50, ledger=-150,
      nota="DIVERGENCIA esperada"),

    S("E25", "Un pago repartido a deudas de ambas direcciones",
      [D("d1", "Le presté", 100, False, F1), D("d2", "Me prestó", 100, True, F1)],
      [P("p1", 100, False, F3, {"d1": 50, "d2": 50})], 0, ledger=-100,
      nota="DIVERGENCIA esperada"),

    # ── Bordes ───────────────────────────────────────────────────────────────
    S("B01", "Deuda de monto 0",
      [D("d1", "Nada", 0, False, F1)], [], 0),

    S("B02", "Deuda de monto negativo",
      [D("d1", "Ajuste negativo", -50, False, F1)], [], 0, ledger=-50,
      nota="DIVERGENCIA esperada: saldo_pendiente se corta en 0"),

    S("B03", "Redondeo: 3 deudas de 33.33 y pago de 100",
      [D("d1", "Tercio 1", 33.33, False, F1), D("d2", "Tercio 2", 33.33, False, F1),
       D("d3", "Tercio 3", 33.33, False, F1)],
      [P("p1", 100, False, F3, {"d1": 33.33, "d2": 33.33, "d3": 33.33})], 0, ledger=-0.01,
      nota="sobrante 0.01 no supera el umbral > 0.01"),

    S("B04", "Asignado mayor que el monto de la deuda",
      [D("d1", "Préstamo", 100, False, F1)],
      [P("p1", 150, False, F3, {"d1": 150})], 0, ledger=-50,
      nota="DIVERGENCIA esperada: el exceso se pierde en vez de ser saldo a favor"),

    S("B10", "Deuda saldada por cruce Y por dinero",
      [D("d1", "Le presté", 100, False, F1), D("d2", "Me prestó", 40, True, F2)],
      [P("c1", 40, True, F3, {"d2": 40}, comp=True),
       P("c2", 40, False, F3, {"d1": 40}, comp=True),
       P("p1", 60, False, F4, {"d1": 60})], 0),
]

# Fechas de los niveles del árbol: una deuda por nivel, en orden cronológico.
FECHAS_ARBOL = ["2026-06-01", "2026-06-05", "2026-06-10", "2026-06-15", "2026-06-20"]


def escenarios_arbol(nivel_max: int) -> list:
    """Traduce el árbol de casos_arbol.py al DSL de este script (deudas y pagos)."""
    out = []
    for caso in casos_arbol.generar():
        if caso.nivel > nivel_max:
            continue
        deudas, pagos = [], []
        for i, m in enumerate(caso.movs):
            if m.tipo == "deuda":
                deudas.append(D(f"d{i}", m.nombre_corto, m.monto,
                                m.direccion == "debo", FECHAS_ARBOL[i]))
            else:
                pagos.append(P(f"p{i}", m.monto, m.direccion == "doy", FECHAS_ARBOL[i]))
        # El reparto FIFO del árbol es el que produce las asignaciones pago→deuda.
        por_pago = {}
        for ap in caso.estado.aplicaciones:
            por_pago[f"p{ap.idx}"] = {f"d{idx}": monto for idx, _, monto in ap.abonos}
        for p in pagos:
            p.asigna = por_pago.get(p.key, {})
        out.append(S(caso.code, caso.titulo, deudas, pagos, caso.neto))
    return out


# ── Siembra ──────────────────────────────────────────────────────────────────
def sembrar(escenarios=ESCENARIOS):
    existentes = {d["nombre"] for d in
                  (supabase.table("deudores").select("nombre").execute().data or [])}

    deudores, deudas, pagos, detalles = [], [], [], []
    for esc in escenarios:
        if esc.nombre in existentes:
            print(f"  ~ {esc.code} ya existe, se omite")
            continue
        did = str(uuid.uuid4())
        deudores.append({"id": did, "nombre": esc.nombre,
                         "token": str(uuid.uuid4()), "synced": True})
        ids_deuda = {}
        for d in esc.deudas:
            ids_deuda[d.key] = str(uuid.uuid4())
            deudas.append({"id": ids_deuda[d.key], "deudor_id": did, "titulo": d.titulo,
                           "monto": d.monto, "fecha_gasto": d.fecha,
                           "es_mi_deuda": d.mine, "synced": True})
        for p in esc.pagos:
            pid = str(uuid.uuid4())
            pagos.append({"id": pid, "deudor_id": did, "monto_total": p.monto,
                          "fecha_pago": p.fecha, "es_mi_pago": p.mine,
                          "es_compensacion": p.comp, "synced": True})
            for dk, monto in p.asigna.items():
                detalles.append({"id": str(uuid.uuid4()), "pago_id": pid,
                                 "deuda_id": ids_deuda[dk], "monto_asignado": monto,
                                 "synced": True})

    if not deudores:
        print("Nada nuevo que sembrar.")
        return

    supabase.table("deudores").insert(deudores).execute()
    if deudas:
        supabase.table("deudas").insert(deudas).execute()
    if pagos:
        supabase.table("pagos").insert(pagos).execute()
    if detalles:
        supabase.table("detalle_pagos").insert(detalles).execute()
    print(f"Sembrado: {len(deudores)} personas, {len(deudas)} deudas, "
          f"{len(pagos)} pagos, {len(detalles)} asignaciones.")


# ── Verificación ─────────────────────────────────────────────────────────────
def verificar(escenarios=ESCENARIOS):
    mapa = {d["nombre"]: d["id"] for d in
            (supabase.table("deudores").select("id, nombre").execute().data or [])}

    print(f"\n{'ID':5} {'neto esp':>9} {'neto':>9} {'ledger esp':>11} {'ledger':>9}  estado")
    print("─" * 78)
    ok = div_esperadas = fallos = 0
    for esc in escenarios:
        did = mapa.get(esc.nombre)
        if not did:
            print(f"{esc.code:5} {'—':>9} {'(no sembrado)':>30}")
            continue
        est = obtener_estado_cuenta(did)
        neto = est["resumen"]["neto"]
        movs = est["movimientos"]
        ledger = movs[0]["saldo_acumulado"] if movs else 0.0

        neto_ok = abs(neto - esc.neto) < 0.011
        led_ok = abs(ledger - esc.ledger_esperado) < 0.011
        coincide = abs(neto - ledger) < 0.011

        if not (neto_ok and led_ok):
            estado, fallos = "✗ INESPERADO", fallos + 1
        elif not coincide:
            estado, div_esperadas = "⚠ divergencia (conocida)", div_esperadas + 1
        else:
            estado, ok = "✓", ok + 1

        print(f"{esc.code:5} {esc.neto:>9.2f} {neto:>9.2f} "
              f"{esc.ledger_esperado:>11.2f} {ledger:>9.2f}  {estado}")
        if esc.nota:
            print(f"{'':5} └─ {esc.nota}")

    print("─" * 78)
    print(f"{ok} correctos · {div_esperadas} divergencias conocidas · {fallos} inesperados")
    return fallos


# ── Limpieza ─────────────────────────────────────────────────────────────────
def limpiar():
    objetivo = [d for d in (supabase.table("deudores").select("id, nombre").execute().data or [])
                if d["nombre"].startswith(PREFIJO)]
    if not objetivo:
        print("No hay personas de prueba que borrar.")
        return
    for d in objetivo:
        # Sin ON DELETE CASCADE garantizado en todas las FKs: borramos de hoja a raíz.
        deuda_ids = [x["id"] for x in supabase.table("deudas").select("id")
                     .eq("deudor_id", d["id"]).execute().data or []]
        if deuda_ids:
            supabase.table("detalle_pagos").delete().in_("deuda_id", deuda_ids).execute()
        supabase.table("deudas").delete().eq("deudor_id", d["id"]).execute()
        supabase.table("pagos").delete().eq("deudor_id", d["id"]).execute()
        supabase.table("deudores").delete().eq("id", d["id"]).execute()
    print(f"Borradas {len(objetivo)} personas de prueba y todos sus datos.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true", help="borra las personas TEST")
    ap.add_argument("--verify", action="store_true", help="solo verificar")
    ap.add_argument("--arbol", type=int, metavar="NIVEL",
                    help=f"usa el árbol de casos_arbol.py hasta ese nivel "
                         f"(1..{casos_arbol.NIVEL_MAX}) en vez de los escenarios E/B")
    args = ap.parse_args()

    if args.arbol:
        escenarios = escenarios_arbol(args.arbol)
        print(f"Árbol hasta nivel {args.arbol}: {len(escenarios)} casos.")
    else:
        escenarios = ESCENARIOS

    if args.clean:
        limpiar()
    elif args.verify:
        sys.exit(1 if verificar(escenarios) else 0)
    else:
        sembrar(escenarios)
        sys.exit(1 if verificar(escenarios) else 0)
