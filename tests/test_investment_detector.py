"""
test_investment_detector.py — Tests para detect_positions() en services/investments/detector.py

Dos bloques:

- **Reglas**, con DataFrames mínimos escritos a mano, uno por comportamiento.
- **Historial completo**, con las 59 filas de inversión que aparecen en los datos reales
  copiadas como literal. Son datos reales pero el test no lee `data/`, así que respeta
  la regla del conftest de no tocar archivos del usuario, y a la vez ancla el detector
  contra el caso que de verdad importa: 14 posiciones, no 22.
"""
import pandas as pd
import pytest

from contabilidad.backend.services.investments.detector import (
    detect_positions,
    normalize_description,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_df(rows):
    """`rows` es una lista de (fecha, descripcion, monto)."""
    return pd.DataFrame(
        {
            "id": [f"tx{i:03d}" for i in range(len(rows))],
            # `mixed`: unas filas traen hora y otras no, igual que el extracto real.
            "FECHA": pd.to_datetime([r[0] for r in rows], format="mixed"),
            "DESCRIPCION": [r[1] for r in rows],
            "MONTO": [float(r[2]) for r in rows],
        }
    )


APERTURA = "CERTIFICADO DE DEPOSITO"
CANCELACION = "CANCELACION PLAZO FIJO"
RETENCION = "RETENCION 2% RENDIMIENTO FINANCIERO"


# ── Normalización ────────────────────────────────────────────────────────────

def test_normalize_quita_tildes_y_mayusculiza():
    assert normalize_description("Regularización de Transacción") == "REGULARIZACION DE TRANSACCION"


def test_normalize_colapsa_espacios():
    assert normalize_description("  CANCELACION   PLAZO  FIJO ") == "CANCELACION PLAZO FIJO"


def test_normalize_tolera_none():
    assert normalize_description(None) == ""


# ── Emparejamiento básico ────────────────────────────────────────────────────

def test_apertura_y_cierre_se_emparejan():
    df = make_df([
        ("2025-01-10", APERTURA, -1000.0),
        ("2025-02-10", CANCELACION, 1000.0),
    ])
    res = detect_positions(df)

    assert len(res.posiciones) == 1
    p = res.posiciones[0]
    assert p.estado == "cerrada"
    assert p.capital == 1000.0
    assert p.fecha_apertura.isoformat() == "2025-01-10"
    assert p.fecha_cierre.isoformat() == "2025-02-10"
    assert p.dias == 31
    assert res.huerfanas == []


def test_apertura_por_plazo_fijo_tambien_cuenta():
    """El banco cambió a 'APERTURA DE DEPÓSTIO A PLAZO FIJO' (sic) en 2026."""
    df = make_df([
        ("2026-01-21", "APERTURA DE DEPÓSTIO A PLAZO FIJO", -500.0),
        ("2026-02-21", CANCELACION, 500.0),
    ])
    res = detect_positions(df)
    assert len(res.cerradas) == 1
    assert res.cerradas[0].capital == 500.0


def test_apertura_sin_cierre_queda_abierta():
    df = make_df([("2025-01-10", APERTURA, -1000.0)])
    res = detect_positions(df)

    assert len(res.abiertas) == 1
    p = res.abiertas[0]
    assert p.estado == "abierta"
    assert p.dias is None
    assert p.tna is None
    assert res.capital_abierto == 1000.0


def test_fifo_empareja_la_apertura_mas_antigua():
    """Dos posiciones del mismo monto: la cancelación cierra la más vieja."""
    df = make_df([
        ("2025-01-01", APERTURA, -1000.0),
        ("2025-02-01", APERTURA, -1000.0),
        ("2025-03-01", CANCELACION, 1000.0),
    ])
    res = detect_positions(df)

    cerrada = res.cerradas[0]
    assert cerrada.fecha_apertura.isoformat() == "2025-01-01"
    assert res.abiertas[0].fecha_apertura.isoformat() == "2025-02-01"


def test_empareja_por_monto_no_por_orden():
    """Con montos distintos manda el monto, no quién llegó primero."""
    df = make_df([
        ("2025-01-01", APERTURA, -1000.0),
        ("2025-01-02", APERTURA, -2000.0),
        ("2025-03-01", CANCELACION, 2000.0),
    ])
    res = detect_positions(df)

    assert res.cerradas[0].capital == 2000.0
    assert res.abiertas[0].capital == 1000.0


# ── Interés: las tres formas en que el banco lo rotula ───────────────────────

def test_segunda_cancelacion_es_interes_no_una_posicion():
    """El bug original: el interés viene como una segunda fila 'CANCELACION PLAZO FIJO'."""
    df = make_df([
        ("2025-01-10", APERTURA, -1000.0),
        ("2025-02-10 04:53", CANCELACION, 1000.0),
        ("2025-02-10 04:53", CANCELACION, 50.0),
    ])
    res = detect_positions(df)

    assert len(res.posiciones) == 1, "el interés no puede contarse como inversión aparte"
    assert res.posiciones[0].interes == 50.0
    assert res.huerfanas == []


def test_transferencia_interior_es_interes():
    df = make_df([
        ("2025-01-10", APERTURA, -1000.0),
        ("2025-02-10 05:07", CANCELACION, 1000.0),
        ("2025-02-10 05:07", "TRANSFERENCIA INTERIOR", 40.0),
    ])
    assert detect_positions(df).cerradas[0].interes == 40.0


def test_regularizacion_de_transaccion_es_interes():
    """Formato de 2026, con tildes."""
    df = make_df([
        ("2026-06-25", APERTURA, -1000.0),
        ("2026-07-27 08:16", CANCELACION, 1000.0),
        ("2026-07-27 08:16", "REGULARIZACIÓN DE TRANSACCIÓN", 60.0),
    ])
    assert detect_positions(df).cerradas[0].interes == 60.0


def test_cierre_sin_interes_da_cero():
    df = make_df([
        ("2025-01-10", APERTURA, -1000.0),
        ("2025-02-10", CANCELACION, 1000.0),
    ])
    p = detect_positions(df).cerradas[0]
    assert p.interes == 0.0
    assert p.retencion == 0.0


# ── Retención ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "descripcion",
    ["RETENCION RENDIMIENTO FINANCIERO", "RETENCION 2% RENDIMIENTO FINANCIERO"],
)
def test_ambas_variantes_de_retencion(descripcion):
    df = make_df([
        ("2025-01-10", APERTURA, -1000.0),
        ("2025-02-10 06:00", CANCELACION, 1000.0),
        ("2025-02-10 06:00", "TRANSFERENCIA INTERIOR", 40.0),
        ("2025-02-10 06:00", descripcion, -0.8),
    ])
    p = detect_positions(df).cerradas[0]
    assert p.retencion == 0.8
    assert p.neto == 39.2
    assert p.total_devuelto == 1039.2


# ── Falsos positivos ─────────────────────────────────────────────────────────

def test_transferencia_ajena_el_mismo_dia_no_es_interes():
    """El 2025-12-22 real hay depósitos de 110/75/45 que no son interés."""
    df = make_df([
        ("2025-01-10", APERTURA, -1000.0),
        ("2025-02-10 08:59", CANCELACION, 1000.0),
        ("2025-02-10 08:59", "TRANSFERENCIA INTERIOR", 28.54),
        ("2025-02-10 11:20", "TRANSF. DIRECTA DE ARCINIEGA BASANTES PAULINA", 110.0),
    ])
    assert detect_positions(df).cerradas[0].interes == 28.54


def test_credito_no_listado_a_la_misma_hora_no_es_interes():
    """Aun compartiendo marca de tiempo, si la descripción no está en la lista blanca no cuenta."""
    df = make_df([
        ("2025-01-10", APERTURA, -1000.0),
        ("2025-02-10 08:59", CANCELACION, 1000.0),
        ("2025-02-10 08:59", "DEPOSITO EN EFECTIVO", 500.0),
    ])
    assert detect_positions(df).cerradas[0].interes == 0.0


def test_dia_sin_hora_no_arrastra_debitos_ajenos():
    """En los extractos viejos todo cae a medianoche (real: 2024-09-04)."""
    df = make_df([
        ("2024-06-04", APERTURA, -10278.0),
        ("2024-09-04", "TRANSFERENCIA INTERBANCARIA ENVIADA", -26.30),
        ("2024-09-04", CANCELACION, 10278.0),
        ("2024-09-04", "TRANSFERENCIA INTERIOR", 208.82),
        ("2024-09-04", RETENCION, -4.18),
    ])
    p = detect_positions(df).cerradas[0]
    assert p.interes == 208.82
    assert p.retencion == 4.18
    assert p.legs_por_dia is True


def test_cancelacion_no_emparejada_no_cuenta_como_apertura():
    """'CANCELACION PLAZO FIJO' contiene 'PLAZO FIJO' pero es un crédito, no una apertura."""
    df = make_df([("2025-02-10", CANCELACION, 1000.0)])
    res = detect_positions(df)
    assert res.posiciones == []


# ── Cancelaciones huérfanas ──────────────────────────────────────────────────

def test_cancelacion_sin_apertura_es_huerfana():
    df = make_df([("2024-05-29", CANCELACION, 10100.0)])
    res = detect_positions(df)

    assert res.posiciones == []
    assert len(res.huerfanas) == 1
    assert res.huerfanas[0].capital_sugerido == 10100.0


def test_huerfanas_del_mismo_dia_se_agrupan_y_sugieren_capital():
    """Real: 2024-10-25 con 12.854,21 y 682,63 — la mayor es el capital."""
    df = make_df([
        ("2024-10-25 04:18", CANCELACION, 12854.21),
        ("2024-10-25 04:18", CANCELACION, 682.63),
    ])
    h = detect_positions(df).huerfanas
    assert len(h) == 1
    assert h[0].capital_sugerido == 12854.21
    assert h[0].interes_sugerido == 682.63


def test_huerfana_suma_interes_y_retencion_sueltos():
    df = make_df([
        ("2024-05-29", CANCELACION, 10100.0),
        ("2024-05-29", "TRANSFERENCIA INTERIOR", 172.21),
        ("2024-05-29", RETENCION, -3.44),
    ])
    h = detect_positions(df).huerfanas[0]
    assert h.capital_sugerido == 10100.0
    assert h.interes_sugerido == 172.21
    assert h.retencion == 3.44


# ── Ambigüedad ───────────────────────────────────────────────────────────────

def test_dos_cierres_a_la_misma_hora_prorratean_y_se_marcan():
    df = make_df([
        ("2025-01-01", APERTURA, -1000.0),
        ("2025-01-01", APERTURA, -3000.0),
        ("2025-02-01 07:00", CANCELACION, 1000.0),
        ("2025-02-01 07:00", CANCELACION, 3000.0),
        ("2025-02-01 07:00", "TRANSFERENCIA INTERIOR", 80.0),
    ])
    res = detect_positions(df)

    assert len(res.cerradas) == 2
    assert all(p.ambiguo for p in res.cerradas)
    por_capital = {p.capital: p.interes for p in res.cerradas}
    assert por_capital[1000.0] == 20.0
    assert por_capital[3000.0] == 60.0
    assert res.interes_total == 80.0


# ── Métricas ─────────────────────────────────────────────────────────────────

def test_tna_se_calcula_sobre_dias_calendario():
    df = make_df([
        ("2025-01-01", APERTURA, -1000.0),
        ("2025-01-31", CANCELACION, 1000.0),
        ("2025-01-31", "TRANSFERENCIA INTERIOR", 10.0),
    ])
    p = detect_positions(df).cerradas[0]
    assert p.dias == 30
    assert p.tna == pytest.approx(10 / 1000 * 365 / 30 * 100, abs=1e-4)  # tna viene redondeada


def test_tna_none_si_abre_y_cierra_el_mismo_dia():
    df = make_df([
        ("2025-01-01", APERTURA, -1000.0),
        ("2025-01-01", CANCELACION, 1000.0),
    ])
    p = detect_positions(df).cerradas[0]
    assert p.dias == 0
    assert p.tna is None


# ── Robustez de entrada ──────────────────────────────────────────────────────

def test_dataframe_vacio():
    res = detect_positions(make_df([]))
    assert res.posiciones == []
    assert res.huerfanas == []


def test_falta_columna_obligatoria():
    df = pd.DataFrame({"FECHA": pd.to_datetime(["2025-01-01"])})
    with pytest.raises(ValueError, match="Faltan columnas"):
        detect_positions(df)


def test_sin_columna_id_usa_el_indice():
    df = make_df([
        ("2025-01-10", APERTURA, -1000.0),
        ("2025-02-10", CANCELACION, 1000.0),
    ]).drop(columns=["id"])
    p = detect_positions(df).cerradas[0]
    assert p.tx_apertura_id == "0"
    assert p.tx_cierre_id == "1"


def test_no_muta_el_dataframe_de_entrada():
    df = make_df([
        ("2025-01-10", APERTURA, -1000.0),
        ("2025-02-10", CANCELACION, 1000.0),
    ])
    antes = df.copy()
    detect_positions(df)
    pd.testing.assert_frame_equal(df, antes)


def test_filas_desordenadas_dan_el_mismo_resultado():
    rows = [
        ("2025-02-10", CANCELACION, 1000.0),
        ("2025-01-10", APERTURA, -1000.0),
    ]
    p = detect_positions(make_df(rows)).cerradas[0]
    assert p.fecha_apertura.isoformat() == "2025-01-10"
    assert p.fecha_cierre.isoformat() == "2025-02-10"


# ── Historial real ───────────────────────────────────────────────────────────

#: Las 59 filas relacionadas con plazos fijos que hay en `banca_unida.xlsx`, copiadas
#: literalmente. Reproducen todas las rarezas del extracto: interés bajo tres nombres,
#: días sin hora, tres aperturas el mismo día, dos cancelaciones pre-historial.
HISTORIAL_REAL = [
    ("2024-03-28 00:00:00", "CERTIFICADO DE DEPOSITO", -26000.0),
    ("2024-05-29 00:00:00", "CANCELACION PLAZO FIJO", 10100.0),
    ("2024-05-29 00:00:00", "TRANSFERENCIA INTERIOR", 172.21),
    ("2024-05-29 00:00:00", "RETENCION 2% RENDIMIENTO FINANCIERO", -3.44),
    ("2024-06-04 00:00:00", "CERTIFICADO DE DEPOSITO", -10278.0),
    ("2024-09-04 00:00:00", "CANCELACION PLAZO FIJO", 10278.0),
    ("2024-09-04 00:00:00", "TRANSFERENCIA INTERIOR", 208.82),
    ("2024-09-04 00:00:00", "RETENCION 2% RENDIMIENTO FINANCIERO", -4.18),
    ("2024-09-23 12:07:00", "CERTIFICADO DE DEPOSITO", -6648.0),
    ("2024-10-24 03:41:00", "CANCELACION PLAZO FIJO", 6648.0),
    ("2024-10-24 03:41:00", "CANCELACION PLAZO FIJO", 27.48),
    ("2024-10-24 03:41:00", "RETENCION 2% RENDIMIENTO FINANCIERO", -0.55),
    ("2024-10-25 04:18:00", "CANCELACION PLAZO FIJO", 12854.21),
    ("2024-10-25 04:18:00", "CANCELACION PLAZO FIJO", 682.63),
    ("2024-11-18 13:11:00", "CERTIFICADO DE DEPOSITO", -10310.0),
    ("2024-11-18 13:12:00", "CERTIFICADO DE DEPOSITO", -10003.0),
    ("2025-01-24 04:53:00", "CANCELACION PLAZO FIJO", 26000.0),
    ("2025-01-24 04:53:00", "CANCELACION PLAZO FIJO", 1897.57),
    ("2025-02-21 12:35:00", "CERTIFICADO DE DEPOSITO", -28000.0),
    ("2025-03-19 05:45:00", "CANCELACION PLAZO FIJO", 10310.0),
    ("2025-03-19 05:45:00", "CANCELACION PLAZO FIJO", 225.25),
    ("2025-03-19 05:45:00", "RETENCION RENDIMIENTO FINANCIERO", -4.51),
    ("2025-03-24 07:22:00", "CANCELACION PLAZO FIJO", 28000.0),
    ("2025-03-24 07:22:00", "CANCELACION PLAZO FIJO", 139.84),
    ("2025-03-24 07:22:00", "RETENCION RENDIMIENTO FINANCIERO", -2.8),
    ("2025-04-28 19:58:00", "CERTIFICADO DE DEPOSITO", -7317.0),
    ("2025-05-12 21:24:00", "CERTIFICADO DE DEPOSITO", -27000.0),
    ("2025-06-12 06:45:00", "CANCELACION PLAZO FIJO", 27000.0),
    ("2025-06-12 06:45:00", "CANCELACION PLAZO FIJO", 123.23),
    ("2025-06-12 06:45:00", "RETENCION RENDIMIENTO FINANCIERO", -2.46),
    ("2025-06-17 05:07:00", "CANCELACION PLAZO FIJO", 10003.0),
    ("2025-06-17 05:07:00", "TRANSFERENCIA INTERIOR", 386.95),
    ("2025-08-12 23:35:00", "CERTIFICADO DE DEPOSITO", -38000.0),
    ("2025-09-12 04:20:00", "CANCELACION PLAZO FIJO", 38000.0),
    ("2025-09-12 04:20:00", "TRANSFERENCIA INTERIOR", 116.16),
    ("2025-09-12 04:20:00", "RETENCION RENDIMIENTO FINANCIERO", -2.32),
    ("2025-09-25 05:01:00", "CANCELACION PLAZO FIJO", 7317.0),
    ("2025-09-25 05:01:00", "TRANSFERENCIA INTERIOR", 167.68),
    ("2025-09-25 05:01:00", "RETENCION RENDIMIENTO FINANCIERO", -3.35),
    ("2025-11-18 19:10:00", "CERTIFICADO DE DEPOSITO", -10419.0),
    ("2025-11-18 19:12:00", "CERTIFICADO DE DEPOSITO", -4214.0),
    ("2025-11-18 19:14:00", "CERTIFICADO DE DEPOSITO", -27000.0),
    ("2025-12-19 06:39:00", "CANCELACION PLAZO FIJO", 27000.0),
    ("2025-12-19 06:39:00", "TRANSFERENCIA INTERIOR", 67.43),
    ("2025-12-19 06:39:00", "RETENCION 2% RENDIMIENTO FINANCIERO", -1.35),
    ("2025-12-22 08:59:00", "CANCELACION PLAZO FIJO", 10419.0),
    ("2025-12-22 08:59:00", "TRANSFERENCIA INTERIOR", 28.54),
    ("2025-12-22 08:59:00", "RETENCION 2% RENDIMIENTO FINANCIERO", -0.57),
    ("2026-01-21 19:42:00", "APERTURA DE DEPÓSTIO A PLAZO FIJO", -28304.0),
    ("2026-02-23 08:03:00", "CANCELACION PLAZO FIJO", 28304.0),
    ("2026-02-23 08:03:00", "TRANSFERENCIA INTERIOR", 75.24),
    ("2026-02-23 08:03:00", "RETENCION 2% RENDIMIENTO FINANCIERO", -1.5),
    ("2026-03-19 05:46:00", "CANCELACION PLAZO FIJO", 4214.0),
    ("2026-03-19 05:46:00", "TRANSFERENCIA INTERIOR", 67.28),
    ("2026-03-19 05:46:00", "RETENCION 2% RENDIMIENTO FINANCIERO", -2.02),
    ("2026-06-25 14:45:00", "APERTURA DE DEPÓSTIO A PLAZO FIJO", -27000.0),
    ("2026-07-27 08:16:00", "CANCELACION PLAZO FIJO", 27000.0),
    ("2026-07-27 08:16:00", "REGULARIZACIÓN DE TRANSACCIÓN", 69.6),
    ("2026-07-27 08:16:00", "RETENCION RENDIMIENTO FINANCIERO", -2.09),
]

#: (apertura, cierre, capital, interés, retención) esperados, verificados a mano contra
#: el extracto.
POSICIONES_ESPERADAS = [
    ("2024-03-28", "2025-01-24", 26000.0, 1897.57, 0.0),
    ("2024-06-04", "2024-09-04", 10278.0, 208.82, 4.18),
    ("2024-09-23", "2024-10-24", 6648.0, 27.48, 0.55),
    ("2024-11-18", "2025-03-19", 10310.0, 225.25, 4.51),
    ("2024-11-18", "2025-06-17", 10003.0, 386.95, 0.0),
    ("2025-02-21", "2025-03-24", 28000.0, 139.84, 2.8),
    ("2025-04-28", "2025-09-25", 7317.0, 167.68, 3.35),
    ("2025-05-12", "2025-06-12", 27000.0, 123.23, 2.46),
    ("2025-08-12", "2025-09-12", 38000.0, 116.16, 2.32),
    ("2025-11-18", "2025-12-19", 27000.0, 67.43, 1.35),
    ("2025-11-18", "2025-12-22", 10419.0, 28.54, 0.57),
    ("2025-11-18", "2026-03-19", 4214.0, 67.28, 2.02),
    ("2026-01-21", "2026-02-23", 28304.0, 75.24, 1.5),
    ("2026-06-25", "2026-07-27", 27000.0, 69.6, 2.09),
]


@pytest.fixture
def historial():
    return detect_positions(make_df(HISTORIAL_REAL))


def test_historial_hay_catorce_posiciones_no_veintidos(historial):
    """Hay 22 filas 'CANCELACION PLAZO FIJO' pero solo 14 cancelaciones reales."""
    filas_cancelacion = sum(1 for r in HISTORIAL_REAL if r[1] == CANCELACION)
    assert filas_cancelacion == 22
    assert len(historial.cerradas) == 14


def test_historial_ninguna_posicion_queda_abierta(historial):
    assert historial.abiertas == []
    assert historial.capital_abierto == 0.0


def test_historial_cada_posicion_coincide(historial):
    obtenidas = sorted(
        (
            p.fecha_apertura.isoformat(),
            p.fecha_cierre.isoformat(),
            p.capital,
            p.interes,
            p.retencion,
        )
        for p in historial.cerradas
    )
    assert obtenidas == sorted(POSICIONES_ESPERADAS)


def test_historial_totales(historial):
    assert historial.interes_total == 3601.07
    assert historial.retencion_total == 27.70


def test_historial_ninguna_posicion_ambigua(historial):
    assert not any(p.ambiguo for p in historial.cerradas)


def test_historial_dos_huerfanas_pre_historial(historial):
    resumen = [(h.fecha.isoformat(), h.capital_sugerido, h.interes_sugerido) for h in historial.huerfanas]
    assert resumen == [
        ("2024-05-29", 10100.0, 172.21),
        ("2024-10-25", 12854.21, 682.63),
    ]


def test_historial_la_tna_cayo_a_la_mitad_en_2026(historial):
    """La señal que el módulo existe para mostrar."""
    def tna_ponderada(anio):
        pos = [p for p in historial.cerradas if p.fecha_cierre.year == anio]
        interes = sum(p.interes for p in pos)
        capital_dia = sum(p.capital * p.dias / 365 for p in pos)
        return interes / capital_dia * 100

    assert tna_ponderada(2025) > 6.5
    assert tna_ponderada(2026) < 4.0
