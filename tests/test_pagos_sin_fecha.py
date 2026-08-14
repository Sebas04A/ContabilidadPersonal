"""
test_pagos_sin_fecha.py — Un pago fijo puede no tener inicio, o no tener fin, o ninguno.

Hasta el 2026-08-12 las dos fechas eran obligatorias de facto: `get_payments()` hacía
`dropna` sobre las dos y `_apply_payment` descartaba lo que no tuviera inicio. Para decir
«este pago vale para siempre» había que escribir una fecha centinela (`3000-01-01` en el
generador del corte, `2030-01-01` a mano), y una fila a la que le faltara una fecha
desaparecía **a la vez** del dashboard y de la pantalla de Variables — invisible en los dos
sitios, imposible de borrar para el usuario.

Ahora la celda vacía es el significado:

    sin inicio → desde siempre        sin fin → para siempre

Con una excepción que no es negociable: un grupo `interpolated` necesita las dos puntas,
porque son el tramo sobre el que reparte. Sin ellas no hay nada que interpolar.

Lo que estos tests protegen es que **las dos implementaciones de la ventana digan lo
mismo**: `VirtualItemsProcessor._apply_fixed_payment` (lo que el patrimonio ve) y
`neutralizacion._activo` (lo que la pantalla de inversiones mide contra él).
"""
from datetime import date

import pandas as pd
import pytest
from unittest.mock import patch

from contabilidad.backend.services.dashboard_service import DashboardConfig, VirtualItemsProcessor
from contabilidad.backend.services.investments import neutralizacion as neu


@pytest.fixture
def storage(tmp_path):
    with patch("contabilidad.backend.storage.variables_storage.BASE_DATA_PATH", str(tmp_path)), \
         patch("contabilidad.backend.storage.variables_storage.GROUPS_FILE", str(tmp_path / "grupos.csv")), \
         patch("contabilidad.backend.storage.variables_storage.PAYMENTS_FILE", str(tmp_path / "pagos.csv")):
        from contabilidad.backend.storage.variables_storage import InterpolationStorage
        yield InterpolationStorage


def _calendario(desde="2025-01-01", hasta="2025-12-31"):
    return pd.DataFrame({'FECHA': pd.date_range(desde, hasta, freq='D')})


def _aplicar(pagos_por_tipo):
    """Corre el procesador real sobre un calendario y devuelve PAGOS_FIJOS por fecha."""
    df = _calendario()
    proc = VirtualItemsProcessor(DashboardConfig())
    for group_type, pagos in pagos_por_tipo.items():
        for pago in pagos:
            proc._apply_payment(df, pago, group_type)
    return {d.date().isoformat(): v for d, v in zip(df['FECHA'], df['PAGOS_FIJOS'])}


def _pago(amount, start, end, **extra):
    return {'amount': amount, 'start_date': start, 'end_date': end, **extra}


# ── La ventana del dashboard ─────────────────────────────────────────────────

def test_sin_fin_aplica_para_siempre():
    df = _calendario()
    df['PAGOS_FIJOS'] = 0.0
    proc = VirtualItemsProcessor(DashboardConfig())
    proc._apply_payment(df, _pago(100.0, '2025-06-01', None), 'fixed')

    serie = {d.date().isoformat(): v for d, v in zip(df['FECHA'], df['PAGOS_FIJOS'])}
    assert serie['2025-05-31'] == 0.0
    assert serie['2025-06-01'] == 100.0
    assert serie['2025-12-31'] == 100.0, "un fin vacío no debe cortar el tramo"


def test_sin_inicio_aplica_desde_siempre():
    df = _calendario()
    df['PAGOS_FIJOS'] = 0.0
    proc = VirtualItemsProcessor(DashboardConfig())
    proc._apply_payment(df, _pago(100.0, None, '2025-06-01'), 'fixed')

    serie = {d.date().isoformat(): v for d, v in zip(df['FECHA'], df['PAGOS_FIJOS'])}
    assert serie['2025-01-01'] == 100.0, "antes esto se descartaba entero"
    assert serie['2025-05-31'] == 100.0
    assert serie['2025-06-01'] == 0.0, "el fin sigue siendo exclusivo"


def test_sin_ninguna_de_las_dos_aplica_siempre():
    df = _calendario()
    df['PAGOS_FIJOS'] = 0.0
    proc = VirtualItemsProcessor(DashboardConfig())
    proc._apply_payment(df, _pago(50.0, None, None), 'fixed')

    valores = set(df['PAGOS_FIJOS'])
    assert valores == {50.0}


def test_interpolado_necesita_las_dos_puntas():
    """Sin tramo no hay nada que repartir: se ignora en vez de inventar un reparto."""
    proc = VirtualItemsProcessor(DashboardConfig())
    for start, end in [(None, '2025-06-01'), ('2025-01-01', None), (None, None)]:
        df = _calendario()
        df['PAGOS_FIJOS'] = 0.0
        df['INTERPOLADO'] = 0.0
        proc._apply_payment(df, _pago(100.0, start, end), 'interpolated')
        assert df['INTERPOLADO'].abs().sum() == 0.0, f"no debía interpolar con {start}/{end}"


def test_el_interpolado_normal_sigue_funcionando():
    df = _calendario()
    df['PAGOS_FIJOS'] = 0.0
    df['INTERPOLADO'] = 0.0
    proc = VirtualItemsProcessor(DashboardConfig())
    proc._apply_payment(df, _pago(100.0, '2025-01-01', '2025-01-11'), 'interpolated')

    serie = {d.date().isoformat(): round(v, 2) for d, v in zip(df['FECHA'], df['INTERPOLADO'])}
    assert serie['2025-01-01'] == 0.0
    assert serie['2025-01-06'] == 50.0
    assert serie['2025-01-11'] == 0.0, "fuera del tramo no reparte"


# ── El almacenamiento deja de esconderlas ────────────────────────────────────

def test_get_payments_devuelve_las_filas_sin_fecha(storage):
    grupo = storage.create_group("Abiertos", group_type="fixed")
    storage.create_payment(grupo["id"], 100.0, "2025-01-01", None)
    storage.create_payment(grupo["id"], 200.0, None, "2025-06-01")

    pagos = storage.get_payments(grupo["id"])

    assert len(pagos) == 2, "antes el dropna se las llevaba a las dos"
    por_monto = {p['amount']: p for p in pagos}
    assert por_monto[100.0]['end_date'] is None
    assert por_monto[200.0]['start_date'] is None


def test_las_fechas_ausentes_salen_como_none_no_como_nat(storage):
    """`NaT` no sobrevive a JSON y además es *truthy* en algunos caminos."""
    import json

    grupo = storage.create_group("Abiertos", group_type="fixed")
    storage.create_payment(grupo["id"], 100.0, "2025-01-01", None)

    pago = storage.get_payments(grupo["id"])[0]
    assert pago['end_date'] is None
    assert not isinstance(pago['end_date'], type(pd.NaT))
    json.dumps({k: str(v) for k, v in pago.items()})


def test_un_pago_fijo_sin_fechas_ya_no_es_invalido(storage):
    grupo = storage.create_group("Abiertos", group_type="fixed")
    storage.create_payment(grupo["id"], 100.0, None, None)

    assert storage.get_invalid_payments() == []
    assert len(storage.get_payments(grupo["id"])) == 1


def test_un_pago_interpolado_sin_fechas_si_es_invalido(storage):
    """Ahí la fecha no es significado, es un dato que falta y sin el cual no hace nada."""
    grupo = storage.create_group("Reparto", group_type="interpolated")
    storage.create_payment(grupo["id"], 100.0, "2025-01-01", None)

    invalidas = storage.get_invalid_payments()
    assert len(invalidas) == 1
    assert "fecha de fin" in invalidas[0]['motivo']


def test_sigue_siendo_invalida_una_fila_sin_monto(storage, tmp_path):
    grupo = storage.create_group("Abiertos", group_type="fixed")
    storage.create_payment(grupo["id"], 100.0, "2025-01-01", "2025-02-01")  # crea el encabezado
    with open(str(tmp_path / "pagos.csv"), "a") as f:
        f.write(f"sin-monto,{grupo['id']},,2025-01-01,2025-02-01,\n")

    invalidas = storage.get_invalid_payments()
    assert len(invalidas) == 1
    assert "monto" in invalidas[0]['motivo']


# ── Las dos implementaciones de la ventana tienen que coincidir ──────────────

@pytest.mark.parametrize("inicio,fin", [
    ('2025-06-01', None),
    (None, '2025-06-01'),
    (None, None),
    ('2025-03-01', '2025-09-01'),
    ('2025-06-01', '3000-01-01'),   # la centinela vieja sigue valiendo
])
def test_activo_y_el_dashboard_dicen_lo_mismo(inicio, fin):
    """`neutralizacion._activo` existe para medir lo que el patrimonio ve.

    Si las dos se separan, la pantalla de inversiones compara contra una serie que nadie
    tiene, y eso es exactamente el error que la fase 6 no se podía permitir.
    """
    df = _calendario()
    df['PAGOS_FIJOS'] = 0.0
    VirtualItemsProcessor(DashboardConfig())._apply_payment(
        df, _pago(100.0, inicio, fin), 'fixed')
    del_dashboard = {d.date(): v for d, v in zip(df['FECHA'], df['PAGOS_FIJOS'])}

    dias = list(del_dashboard)
    de_activo = neu.serie([{'amount': 100.0, 'start': inicio, 'end': fin}], dias)

    assert [del_dashboard[d] for d in dias] == de_activo


def test_la_centinela_vieja_equivale_a_no_poner_fin():
    dias = [date(2025, 1, 1), date(2025, 6, 1), date(2999, 1, 1)]
    con_centinela = neu.serie([{'amount': 10.0, 'start': '2025-01-01', 'end': '3000-01-01'}], dias)
    sin_fin = neu.serie([{'amount': 10.0, 'start': '2025-01-01', 'end': None}], dias)

    assert con_centinela == sin_fin == [10.0, 10.0, 10.0]
