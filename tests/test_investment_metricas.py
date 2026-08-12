"""
test_investment_metricas.py — XIRR, TNA ponderada, devengo, resumen y timeline.

Las métricas son funciones puras sobre listas de diccionarios, así que estos tests no
tocan ni CSV ni pipeline: se les pasa la posición ya armada.
"""
from datetime import date

import pytest

from contabilidad.backend.services.investments import metricas


def posicion(capital=1000.0, interes=0.0, retencion=0.0, apertura="2025-01-10",
             cierre="2025-02-10", tipo="plazo_fijo", portafolio_id="p1", **extra):
    movimientos = [{"fecha": apertura, "tipo": "aporte", "monto": capital}] if apertura else []
    if cierre:
        movimientos.append({"fecha": cierre, "tipo": "retiro", "monto": capital})
        if interes:
            movimientos.append({"fecha": cierre, "tipo": "interes", "monto": interes})
        if retencion:
            movimientos.append({"fecha": cierre, "tipo": "retencion", "monto": retencion})
    return {
        "id": extra.pop("id", "pos1"),
        "tipo": tipo,
        "portafolio_id": portafolio_id,
        "fecha_apertura": apertura,
        "fecha_cierre": cierre,
        "estado": "cerrada" if cierre else "abierta",
        "capital": capital,
        "capital_vigente": 0.0 if cierre else capital,
        "interes": interes,
        "retencion": retencion,
        "neto": round(interes - retencion, 2),
        "movimientos": movimientos,
        "plazo_pactado_dias": None,
        "tasa_pactada": None,
        **extra,
    }


# ── XIRR ─────────────────────────────────────────────────────────────────────

def test_xirr_de_un_ano_exacto():
    """100 que se convierten en 110 en 365 días son 10 %."""
    assert metricas.xirr([("2025-01-01", -100.0), ("2026-01-01", 110.0)]) == pytest.approx(10.0, abs=0.05)


def test_xirr_de_un_mes_se_anualiza():
    """1 % en 30 días compuesto da mucho más que 12 % anual."""
    tasa = metricas.xirr([("2025-01-01", -1000.0), ("2025-01-31", 1010.0)])
    assert tasa > 12.0


def test_xirr_sin_flujos_de_los_dos_signos_es_none():
    assert metricas.xirr([("2025-01-01", -100.0), ("2025-06-01", -50.0)]) is None


def test_xirr_de_un_solo_flujo_es_none():
    assert metricas.xirr([("2025-01-01", -100.0)]) is None


def test_xirr_de_una_perdida_es_negativa():
    assert metricas.xirr([("2025-01-01", -1000.0), ("2026-01-01", 900.0)]) < 0


def test_flujos_respetan_el_signo_de_cada_tipo():
    flujos = metricas.flujos_de([posicion(capital=1000.0, interes=10.0, retencion=0.2)])
    montos = sorted(m for _, m in flujos)
    assert montos == [-1000.0, -0.2, 10.0, 1000.0]


def test_cerrar_abiertas_agrega_el_valor_de_hoy():
    abierta = posicion(cierre=None, tasa_pactada=3.0)
    extras = metricas.cerrar_abiertas([abierta], date(2025, 2, 9))
    assert len(extras) == 1
    assert extras[0][1] >= 1000.0


# ── Devengo ──────────────────────────────────────────────────────────────────

def test_interes_devengado_usa_base_360():
    """1000 al 3,6 % durante 30 días: 1000 × 0,036 × 30/360 = 3,00."""
    abierta = posicion(cierre=None, apertura="2025-01-01", tasa_pactada=3.6)
    assert metricas.interes_devengado(abierta, date(2025, 1, 31)) == pytest.approx(3.0, abs=0.01)


def test_sin_tasa_pactada_no_se_inventa_devengo():
    assert metricas.interes_devengado(posicion(cierre=None), date(2025, 2, 1)) is None


def test_una_posicion_cerrada_no_devenga():
    assert metricas.interes_devengado(posicion(tasa_pactada=3.0), date(2025, 3, 1)) is None


def test_dias_restantes_y_vencimiento():
    abierta = posicion(cierre=None, apertura="2025-01-01", plazo_pactado_dias=30)
    assert metricas.fecha_vencimiento(abierta) == "2025-01-31"
    assert metricas.dias_restantes(abierta, date(2025, 1, 21)) == 10


def test_dias_restantes_negativos_cuando_ya_vencio():
    abierta = posicion(cierre=None, apertura="2025-01-01", plazo_pactado_dias=30)
    assert metricas.dias_restantes(abierta, date(2025, 2, 10)) == -10


# ── Agregados ────────────────────────────────────────────────────────────────

HOY = date(2026, 1, 1)


def test_tna_ponderada_pesa_por_capital_dia():
    """Una tasa alta sobre poco capital no puede arrastrar el promedio."""
    grande = posicion(capital=100000.0, interes=1000.0, apertura="2025-01-01", cierre="2025-12-31")
    chica = posicion(capital=100.0, interes=50.0, apertura="2025-01-01", cierre="2025-12-31", id="pos2")

    kpis = metricas.calcular_kpis([grande, chica], HOY)
    assert kpis["tna_ponderada"] == pytest.approx(1.05, abs=0.1)


def test_las_posiciones_sin_apertura_no_entran_en_la_tna():
    """Sin fecha de apertura no hay capital-día, y su interés dispararía la tasa."""
    normal = posicion(capital=10000.0, interes=500.0, apertura="2025-01-01", cierre="2025-12-31")
    sembrada = posicion(capital=10000.0, interes=800.0, apertura=None, cierre="2025-06-01", id="pos2")

    kpis = metricas.calcular_kpis([normal, sembrada], HOY)
    solo_normal = metricas.calcular_kpis([normal], HOY)

    assert kpis["tna_ponderada"] == solo_normal["tna_ponderada"]
    assert kpis["sin_apertura"] == 1
    # Su interés sí cuenta como cobrado: se cobró de verdad.
    assert kpis["interes_cobrado"] == 1300.0


def test_capital_dia_multiplica_monto_por_duracion():
    kpis = metricas.calcular_kpis([posicion(capital=1000.0, apertura="2025-01-01", cierre="2025-01-11")], HOY)
    assert kpis["capital_dia"] == 10000.0


def test_los_ajustes_no_cuentan_como_capital_invertido():
    """Plata suelta del portafolio no está rindiendo: va en `residual_suelto`."""
    ajuste = posicion(capital=500.0, tipo="ajuste", cierre=None)
    kpis = metricas.calcular_kpis([ajuste], HOY)

    assert kpis["capital_invertido"] == 0.0
    assert kpis["residual_suelto"] == 500.0
    assert kpis["capital_rotado"] == 0.0


def test_capital_invertido_solo_cuenta_lo_abierto():
    abierta = posicion(capital=2000.0, cierre=None)
    cerrada = posicion(capital=1000.0, id="pos2")
    kpis = metricas.calcular_kpis([abierta, cerrada], HOY)

    assert kpis["capital_invertido"] == 2000.0
    assert kpis["capital_rotado"] == 3000.0
    assert (kpis["abiertas"], kpis["cerradas"]) == (1, 1)


def test_proximo_vencimiento_es_el_mas_cercano():
    lejana = posicion(cierre=None, apertura="2025-01-01", plazo_pactado_dias=200)
    cercana = posicion(cierre=None, apertura="2025-01-01", plazo_pactado_dias=30, id="pos2")
    kpis = metricas.calcular_kpis([lejana, cercana], HOY)
    assert kpis["proximo_vencimiento"] == "2025-01-31"


# ── Resumen ──────────────────────────────────────────────────────────────────

PORTAFOLIOS = [
    {"id": "p1", "name": "Mias", "es_custodia": False},
    {"id": "p2", "name": "Madre", "es_custodia": True},
]


def test_resumen_separa_propio_de_custodia():
    mia = posicion(capital=1000.0, interes=10.0, portafolio_id="p1")
    de_madre = posicion(capital=2000.0, interes=20.0, portafolio_id="p2", id="pos2")

    resumen = metricas.resumen([mia, de_madre], PORTAFOLIOS, HOY)

    assert resumen["propio"]["capital_rotado"] == 1000.0
    assert resumen["custodia"]["capital_rotado"] == 2000.0
    assert resumen["global"]["capital_rotado"] == 3000.0


def test_una_posicion_sin_portafolio_cuenta_como_propia():
    """No asignada todavía; ocultarla del total sería peor que asumirla propia."""
    suelta = posicion(portafolio_id=None)
    resumen = metricas.resumen([suelta], PORTAFOLIOS, HOY)

    assert resumen["propio"]["posiciones"] == 1
    assert resumen["sin_portafolio"] == 1


def test_resumen_por_portafolio_trae_la_bandera_de_custodia():
    resumen = metricas.resumen([posicion(portafolio_id="p2")], PORTAFOLIOS, HOY)
    madre = next(p for p in resumen["por_portafolio"] if p["portafolio_id"] == "p2")
    assert madre["es_custodia"] is True


def test_por_anio_agrupa_por_fecha_de_cierre():
    filas = metricas.por_anio([
        posicion(capital=1000.0, interes=80.0, apertura="2024-01-01", cierre="2024-12-31"),
        posicion(capital=1000.0, interes=30.0, apertura="2025-01-01", cierre="2025-12-31", id="pos2"),
    ], HOY)

    assert [f["anio"] for f in filas] == [2024, 2025]
    assert filas[0]["tna_ponderada"] > filas[1]["tna_ponderada"]


# ── Timeline ─────────────────────────────────────────────────────────────────

def test_timeline_sube_en_la_apertura_y_baja_en_el_cierre():
    serie = metricas.timeline([posicion(capital=1000.0, interes=10.0,
                                        apertura="2025-01-10", cierre="2025-01-20")],
                              PORTAFOLIOS, date(2025, 1, 25))
    por_fecha = dict(zip(serie["fechas"], serie["capital"]))

    assert por_fecha["2025-01-10"] == 1000.0
    assert por_fecha["2025-01-19"] == 1000.0
    assert por_fecha["2025-01-20"] == 0.0


def test_timeline_acumula_el_interes_neto():
    serie = metricas.timeline([posicion(capital=1000.0, interes=10.0, retencion=0.2,
                                        apertura="2025-01-10", cierre="2025-01-20")],
                              PORTAFOLIOS, date(2025, 1, 25))
    assert serie["interes_acumulado"][-1] == pytest.approx(9.8)


def test_timeline_marca_aperturas_y_cierres():
    serie = metricas.timeline([posicion(apertura="2025-01-10", cierre="2025-01-20")],
                              PORTAFOLIOS, date(2025, 1, 25))
    assert [e["tipo"] for e in serie["eventos"]] == ["apertura", "cierre"]


def test_timeline_vacio_no_revienta():
    assert metricas.timeline([], PORTAFOLIOS, HOY)["fechas"] == []


def test_timeline_ignora_los_ajustes():
    """El área del gráfico es capital invertido, y un ajuste no lo es."""
    serie = metricas.timeline([posicion(tipo="ajuste", apertura="2025-01-10", cierre="2025-01-20")],
                              PORTAFOLIOS, date(2025, 1, 25))
    assert serie["fechas"] == []
