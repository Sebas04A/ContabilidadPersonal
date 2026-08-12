"""
test_investment_patrimonio.py — El capital invertido dentro del patrimonio (fase 5).

Cubre `services/investments/patrimonio.py` (qué capital cuenta y en qué día) y el toggle
que decide si ese capital se suma al `TOTAL` del dashboard.

El invariante que estos tests protegen es que **con el toggle apagado nada cambia**: el
`TOTAL` de hoy tiene que seguir siendo byte por byte el de antes de la fase 5, y el
desglose de variaciones tiene que seguir cuadrando.
"""
from datetime import date

import pandas as pd
import pytest

from contabilidad.backend.services.investments import patrimonio


MIAS = "p-mias"
MADRE = "p-madre"

PORTAFOLIOS = [
    {"id": MIAS, "name": "Inversiones_Mias", "es_custodia": False},
    {"id": MADRE, "name": "Inversiones_Madre", "es_custodia": True},
]


def vista(capital=1000.0, apertura="2025-01-10", cierre="2025-02-10",
          portafolio_id=MIAS, tipo="plazo_fijo", **extra):
    movimientos = [{"fecha": apertura, "tipo": "aporte", "monto": capital}] if apertura else []
    if cierre:
        movimientos.append({"fecha": cierre, "tipo": "retiro", "monto": capital})
    return {
        "id": extra.pop("id", "pos1"),
        "tipo": tipo,
        "portafolio_id": portafolio_id,
        "fecha_apertura": apertura,
        "fecha_cierre": cierre,
        "capital": capital,
        "capital_vigente": 0.0 if cierre else capital,
        "movimientos": movimientos,
        **extra,
    }


def serie(vistas, hoy=date(2025, 3, 1)):
    return patrimonio.capital_propio(vistas, PORTAFOLIOS, hoy=hoy)


# ── Qué capital cuenta ───────────────────────────────────────────────────────

def test_el_capital_esta_vivo_entre_la_apertura_y_el_cierre():
    """La serie arranca en el primer movimiento; lo anterior lo resuelve `evaluar`."""
    valores = serie([vista(capital=1000.0)])

    assert min(valores) == "2025-01-10"
    assert valores["2025-01-10"] == 1000.0
    assert valores["2025-02-09"] == 1000.0
    assert valores["2025-02-10"] == 0.0


def test_una_posicion_abierta_sigue_contando_hasta_hoy():
    valores = serie([vista(capital=1000.0, cierre=None)])

    assert valores["2025-03-01"] == 1000.0


def test_la_custodia_nunca_suma_al_patrimonio_propio():
    """`Uni` y `Madre` son plata de otro que vive en tu cuenta.

    Un portafolio en custodia y solo, ni siquiera produce serie: no hay nada propio que
    graficar, y `evaluar` devuelve ceros para cualquier fecha.
    """
    valores = serie([vista(capital=1000.0, portafolio_id=MADRE, cierre=None)])

    assert valores == {}
    assert patrimonio.evaluar(valores, [date(2025, 3, 1)]) == [0.0]


def test_lo_propio_y_la_custodia_conviven_sin_mezclarse():
    valores = serie([
        vista(id="a", capital=1000.0, portafolio_id=MIAS, cierre=None),
        vista(id="b", capital=5000.0, portafolio_id=MADRE, cierre=None),
    ])

    assert valores["2025-03-01"] == 1000.0


def test_una_posicion_sin_portafolio_cuenta_como_propia():
    """Mismo criterio que `metricas.resumen`: es tuya hasta que se diga lo contrario."""
    valores = serie([vista(capital=1000.0, portafolio_id=None, cierre=None)])

    assert valores["2025-03-01"] == 1000.0


def test_un_ajuste_no_es_capital_invertido():
    """Plata de inversión suelta que el saldo bancario ya muestra: sumarla la duplicaría."""
    valores = serie([vista(capital=647.0, tipo="ajuste", cierre=None)])

    assert valores.get("2025-03-01", 0.0) == 0.0


def test_dos_posiciones_solapadas_se_suman():
    valores = serie([
        vista(id="a", capital=1000.0, apertura="2025-01-10", cierre="2025-02-10"),
        vista(id="b", capital=500.0, apertura="2025-01-20", cierre="2025-03-01"),
    ])

    assert valores["2025-01-15"] == 1000.0
    assert valores["2025-01-25"] == 1500.0
    assert valores["2025-02-15"] == 500.0


def test_sin_posiciones_la_serie_es_vacia():
    assert patrimonio.capital_propio([], PORTAFOLIOS, hoy=date(2025, 3, 1)) == {}


# ── Evaluar la serie sobre las fechas del dashboard ──────────────────────────

def test_antes_del_primer_movimiento_no_habia_nada_invertido():
    valores = patrimonio.evaluar({"2025-01-10": 1000.0}, [date(2024, 3, 12)])

    assert valores == [0.0]


def test_despues_del_ultimo_dia_sigue_vigente_lo_que_quedo_abierto():
    valores = patrimonio.evaluar({"2025-01-10": 1000.0}, [date(2026, 1, 1)])

    assert valores == [1000.0]


def test_evaluar_no_depende_de_que_las_fechas_vengan_ordenadas():
    serie_ = {"2025-01-10": 1000.0, "2025-01-11": 2000.0}

    assert patrimonio.evaluar(serie_, [date(2025, 1, 11), date(2025, 1, 10)]) == [2000.0, 1000.0]


def test_evaluar_una_serie_vacia_da_ceros():
    assert patrimonio.evaluar({}, [date(2025, 1, 1), date(2025, 1, 2)]) == [0.0, 0.0]


# ── El toggle sobre el dashboard ─────────────────────────────────────────────

@pytest.fixture
def df_dashboard():
    """Un tramo mínimo ya pasado por virtual_items, con NOTIONCUM puesto."""
    return pd.DataFrame({
        "FECHA": pd.to_datetime(["2025-01-09", "2025-01-10", "2025-01-11"]),
        "SALDO": [5000.0, 4000.0, 4000.0],
        "TARJETA": [0.0, 0.0, 0.0],
        "PAGO_TARJETA": [0.0, 0.0, 0.0],
        "PAGOS_FIJOS": [0.0, -1000.0, -1000.0],
        "INTERPOLADO": [0.0, 0.0, 0.0],
        "DEUDA_ACUMULADA": [0.0, 0.0, 0.0],
        "NOTIONCUM": [0.0, 1000.0, 1000.0],
    })


def metricas_de(df):
    from contabilidad.backend.services.dashboard_service import DashboardConfig, MetricProcessor
    return MetricProcessor(DashboardConfig()).calculate_all(df)


def test_el_total_no_cambia_por_llenar_notioncum(df_dashboard):
    """El invariante de la fase 5: la serie de siempre se calcula igual que siempre."""
    con_capital = metricas_de(df_dashboard.copy())
    sin_capital = metricas_de(df_dashboard.assign(NOTIONCUM=0.0))

    assert list(con_capital["TOTAL"]) == list(sin_capital["TOTAL"])
    assert list(con_capital["diff_total"]) == list(sin_capital["diff_total"])


def test_la_serie_con_inversiones_suma_el_capital_vivo(df_dashboard):
    df = metricas_de(df_dashboard)

    assert list(df["TOTAL"]) == [5000.0, 5000.0, 5000.0]
    assert list(df["TOTAL_CON_INVERSIONES"]) == [5000.0, 6000.0, 6000.0]


def test_las_dos_series_tienen_su_propia_diferencia(df_dashboard):
    df = metricas_de(df_dashboard)

    assert list(df["diff_total"]) == [0.0, 0.0, 0.0]
    assert list(df["diff_total_con_inversiones"]) == [0.0, 1000.0, 0.0]


def _respuesta(df, incluir_inversiones):
    from contabilidad.backend.services.dashboard_service import DashboardConfig, DashboardService
    servicio = DashboardService.__new__(DashboardService)
    servicio.config = DashboardConfig()
    return servicio._build_response(metricas_de(df), incluir_inversiones)


def test_con_el_toggle_apagado_el_total_es_el_de_siempre(df_dashboard):
    puntos = _respuesta(df_dashboard, incluir_inversiones=False).data

    assert [p.total for p in puntos] == [5000.0, 5000.0, 5000.0]


def test_con_el_toggle_encendido_el_total_incluye_el_capital(df_dashboard):
    puntos = _respuesta(df_dashboard, incluir_inversiones=True).data

    assert [p.total for p in puntos] == [5000.0, 6000.0, 6000.0]
    assert [p.diff_total for p in puntos] == [0.0, 1000.0, 0.0]


def test_con_el_toggle_apagado_diff_notion_se_fuerza_a_cero(df_dashboard):
    """Si el desglose contara el capital sin que el total lo incluya, no cuadraría.

    `VariationsChart` suma los componentes del día y contrasta contra `total_change`
    (que es `diff_total`); la diferencia cae en `unexplained_difference`.
    """
    puntos = _respuesta(df_dashboard, incluir_inversiones=False).data

    assert [p.diff_notion for p in puntos] == [0.0, 0.0, 0.0]


def test_con_el_toggle_encendido_diff_notion_es_real(df_dashboard):
    puntos = _respuesta(df_dashboard, incluir_inversiones=True).data

    assert [p.diff_notion for p in puntos] == [0.0, 1000.0, 0.0]


def test_el_desglose_diario_cuadra_con_el_toggle_apagado(df_dashboard):
    """La suma de los componentes tiene que reconstruir el cambio del total."""
    for punto in _respuesta(df_dashboard, incluir_inversiones=False).data:
        componentes = (punto.diff_saldo - punto.diff_pagos_fijos + punto.diff_interpolados
                       - punto.diff_tarjeta + punto.diff_deuda_acumulada + punto.diff_notion)
        assert componentes == pytest.approx(punto.diff_total, abs=0.01)


def test_el_desglose_diario_cuadra_con_el_toggle_encendido(df_dashboard):
    for punto in _respuesta(df_dashboard, incluir_inversiones=True).data:
        componentes = (punto.diff_saldo - punto.diff_pagos_fijos + punto.diff_interpolados
                       - punto.diff_tarjeta + punto.diff_deuda_acumulada + punto.diff_notion)
        assert componentes == pytest.approx(punto.diff_total, abs=0.01)


def test_el_capital_invertido_se_informa_aunque_el_toggle_este_apagado(df_dashboard):
    """Que no sume al patrimonio no quiere decir que haya que esconderlo."""
    respuesta = _respuesta(df_dashboard, incluir_inversiones=False)

    assert [p.notion for p in respuesta.data] == [0.0, 1000.0, 1000.0]
    assert respuesta.metadata["incluir_inversiones"] is False
    assert respuesta.metadata["capital_invertido"] == 1000.0


# ── La transformación del pipeline ───────────────────────────────────────────

def test_la_transformacion_llena_notioncum_por_fecha(monkeypatch):
    from contabilidad.backend.storage.transformations import dashboard_transforms

    monkeypatch.setattr(patrimonio, "capital_propio_diario",
                        lambda *a, **k: {"2025-01-10": 1000.0, "2025-01-11": 1000.0})
    df = pd.DataFrame({"FECHA": pd.to_datetime(["2025-01-09", "2025-01-10", "2025-01-11"])})

    resultado = dashboard_transforms.transform_investment_capital(df)

    assert list(resultado["NOTIONCUM"]) == [0.0, 1000.0, 1000.0]


def test_la_transformacion_no_revienta_si_las_posiciones_fallan(monkeypatch):
    """Un error del módulo de inversiones no puede tumbar el dashboard entero."""
    from contabilidad.backend.storage.transformations import dashboard_transforms

    def explota(*a, **k):
        raise RuntimeError("posiciones.csv corrupto")

    monkeypatch.setattr(patrimonio, "capital_propio_diario", explota)
    df = pd.DataFrame({"FECHA": pd.to_datetime(["2025-01-10"])})

    assert list(dashboard_transforms.transform_investment_capital(df)["NOTIONCUM"]) == [0.0]


def test_la_transformacion_deja_pasar_un_df_vacio():
    from contabilidad.backend.storage.transformations import dashboard_transforms

    assert dashboard_transforms.transform_investment_capital(pd.DataFrame()).empty
