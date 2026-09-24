"""
Deudas v2, fase 6 (deudas/PLAN_MULTIUSUARIO.md §4.1 y paso 6.6): lo que la otra persona
rechazó no cuenta en ningún saldo del backend de contabilidad.

`reading.py` lee tablas y la vista directo, así que filtra en Python. Contra v1 las filas
no traen `estado_acuerdo` y no se quita nada: eso también se comprueba aquí.
"""
from types import SimpleNamespace
from unittest.mock import patch

from contabilidad.debts import reading

DEUDOR = "d0000000-0000-0000-0000-000000000000"


class _Consulta:
    """Lo justo de la API de supabase-py: filtros encadenados y `.execute().data`."""

    def __init__(self, filas):
        self.filas = list(filas)

    def select(self, *_):
        return self

    def eq(self, col, valor):
        self.filas = [f for f in self.filas if f.get(col) == valor]
        return self

    def neq(self, col, valor):
        self.filas = [f for f in self.filas if f.get(col) != valor]
        return self

    def in_(self, col, valores):
        self.filas = [f for f in self.filas if f.get(col) in set(valores)]
        return self

    def gte(self, *_):
        return self

    def lte(self, *_):
        return self

    def execute(self):
        return SimpleNamespace(data=self.filas)


class _Supabase:
    def __init__(self, tablas):
        self.tablas = tablas

    def table(self, nombre):
        return _Consulta(self.tablas.get(nombre, []))


def _deuda(i, monto, estado=None, **extra):
    fila = {"id": i, "deudor_id": DEUDOR, "titulo": i, "monto": monto, "fecha_gasto": "2026-09-01",
            "created_at": f"2026-09-01T00:00:0{len(i) % 10}+00:00", "es_mi_deuda": False, **extra}
    if estado:
        fila["estado_acuerdo"] = estado
    return fila


def _pago(i, monto, estado=None):
    fila = {"id": i, "deudor_id": DEUDOR, "monto_total": monto, "fecha_pago": "2026-09-02",
            "created_at": "2026-09-02T00:00:00+00:00", "es_mi_pago": False,
            "es_compensacion": False, "cruce_id": None, "nota": None}
    if estado:
        fila["estado_acuerdo"] = estado
    return fila


def _tablas(v2: bool):
    e = (lambda s: s) if v2 else (lambda s: None)
    deudas = [_deuda("cena", 20, e("acordada")), _deuda("taxi", 5, e("rechazada") if v2 else None)]
    pagos = [_pago("p1", 8, e("acordada")), _pago("p2", 3, e("rechazada") if v2 else None)]
    vista = [{"id": d["id"], "titulo": d["titulo"], "monto_original": d["monto"],
              "fecha_gasto": d["fecha_gasto"], "deudor_id": DEUDOR, "es_mi_deuda": False,
              "monto_pagado": 0, "saldo_pendiente": d["monto"], "estado": "PENDIENTE",
              **({"estado_acuerdo": d["estado_acuerdo"]} if "estado_acuerdo" in d else {})}
             for d in deudas]
    return {"deudas": deudas, "pagos": pagos, "detalle_pagos": [], "vista_estado_deudas": vista,
            "deudores": [{"id": DEUDOR, "nombre": "Ana", "token": "t"}]}


def test_v2_el_saldo_no_cuenta_lo_rechazado():
    with patch.object(reading, "supabase", _Supabase(_tablas(v2=True))):
        saldos = reading.obtener_saldos_deudores()
    # cena 20 − pago 8; ni el taxi de 5 ni el pago de 3 (rechazados)
    assert saldos[DEUDOR]["neto"] == 12.0


def test_v1_sin_la_columna_no_se_filtra_nada():
    with patch.object(reading, "supabase", _Supabase(_tablas(v2=False))):
        saldos = reading.obtener_saldos_deudores()
    # 20 + 5 − 8 − 3
    assert saldos[DEUDOR]["neto"] == 14.0


def test_v2_las_listas_para_analisis_no_traen_lo_rechazado():
    with patch.object(reading, "supabase", _Supabase(_tablas(v2=True))):
        deudas = reading.obtener_deudas_con_deudor(solo_pendientes=False)
        por_deudor = reading.obtener_deudas_por_deudor(DEUDOR, solo_pendientes=False)
        pagos = reading.obtener_pagos_para_analisis()
        todos = reading.obtener_todos_pagos()
    assert list(deudas["id"]) == ["cena"]
    assert list(por_deudor["id"]) == ["cena"]
    assert [p["id"] for p in pagos] == ["p1"]
    assert list(todos["id"]) == ["p1"]


def test_v2_el_estado_de_cuenta_no_trae_lo_rechazado():
    with patch.object(reading, "supabase", _Supabase(_tablas(v2=True))), \
         patch.object(reading, "_saldos_remotos", return_value=None):
        ec = reading.obtener_estado_cuenta(DEUDOR)
    assert [d["id"] for d in ec["deudas"]] == ["cena"]
    assert ec["resumen"]["neto"] == 12.0
