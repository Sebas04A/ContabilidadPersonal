"""
test_debt_expenses.py — Deudas mías convertidas en gasto (devengo)

Todo sintético: ni Supabase ni `etiquetas.csv` real se tocan.
El contrato que se prueba está en `PLAN_DEUDAS_COMO_GASTO.md` §3 (invariantes).
"""
import sys
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from contabilidad.backend.services import debt_expenses
from contabilidad.backend.services.debt_expenses import (
    COLUMNAS,
    TIPO_DEUDA,
    cargar_deudas_devengadas,
    marcar_liquidaciones,
)
from contabilidad.backend.services.transaction_service import LABEL_COLUMNS


# ── Datos de mentira ─────────────────────────────────────────────────────────

CENA = "aaaaaaaa-0000-0000-0000-000000000001"   # mía, etiquetada
PRESTAMO = "aaaaaaaa-0000-0000-0000-000000000002"  # mía, SIN etiquetar
SUYA = "aaaaaaaa-0000-0000-0000-000000000003"   # me la deben, etiquetada por error


def deudas_df():
    return pd.DataFrame({
        "FECHA": pd.to_datetime(["2026-09-06", "2026-09-01", "2026-08-15"]),
        "DESCRIPCION": ["Carretao", "Me prestó efectivo", "Le presté yo"],
        "MONTO": [36.83, 100.0, 20.0],
        "TIPO": "DEUDA",
        "DEUDOR_NOMBRE": ["Ale", "Ale", "rubia"],
        "DEUDOR_ID": ["d1", "d1", "d2"],
        "PAGADA": [False, False, False],
        "FECHA_PAGO": [None, None, None],
        "FECHA_CREACION": [None, None, None],
        "ID": [CENA, PRESTAMO, SUYA],
        "ES_MI_DEUDA": [True, True, False],
        "SALDO_PENDIENTE": [36.83, 100.0, 20.0],
    })


def etiquetas_df(ids=(CENA,)):
    filas = []
    for i in ids:
        fila = {c: None for c in LABEL_COLUMNS}
        fila.update({
            "source_id": i,
            "source_type": "DEUDA",
            "nombre_limpio": "Carretao",
            "categoria": "Alimentación",
            "tags": "Brasil_2026",
            "prioridad": "Deseo",
            "felicidad": 8.0,
            "revisado": True,
            "deudor": "lo que diga la etiqueta",
        })
        filas.append(fila)
    return pd.DataFrame(filas, columns=LABEL_COLUMNS)


def con_supabase(df):
    """Parchea el módulo de lectura de Supabase con uno de mentira."""
    fake = MagicMock()
    fake.obtener_deudas_para_analisis.return_value = df
    return patch.dict(sys.modules, {"contabilidad.debts.reading": fake})


# ── I4: devengar es explícito ────────────────────────────────────────────────

def test_sin_etiquetas_de_deuda_no_hay_gasto():
    with patch.object(debt_expenses, "load_labels", return_value=pd.DataFrame(columns=LABEL_COLUMNS)):
        out = cargar_deudas_devengadas()
    assert out.empty
    assert list(out.columns) == COLUMNAS


def test_sin_etiquetas_ni_siquiera_consulta_supabase():
    """El atajo importa: hoy no hay etiquetas de deuda y no queremos pegarle a la red."""
    fake = MagicMock()
    with patch.object(debt_expenses, "load_labels", return_value=pd.DataFrame(columns=LABEL_COLUMNS)), \
         patch.dict(sys.modules, {"contabilidad.debts.reading": fake}):
        cargar_deudas_devengadas()
    fake.obtener_deudas_para_analisis.assert_not_called()


def test_deuda_mia_sin_etiqueta_no_se_devenga():
    """`PRESTAMO` es mía pero nadie dijo que fuera consumo: no entra."""
    with patch.object(debt_expenses, "load_labels", return_value=etiquetas_df([CENA])), \
         con_supabase(deudas_df()):
        out = cargar_deudas_devengadas()
    assert list(out["id"]) == [CENA]


def test_deuda_ajena_no_se_devenga_aunque_este_etiquetada():
    """Si me deben, el gasto ya está en mi transacción: devengarlo sería contarlo dos veces."""
    with patch.object(debt_expenses, "load_labels", return_value=etiquetas_df([CENA, SUYA])), \
         con_supabase(deudas_df()):
        out = cargar_deudas_devengadas()
    assert list(out["id"]) == [CENA]


# ── La forma de la fila ──────────────────────────────────────────────────────

def test_la_fila_devengada_es_un_gasto_bien_formado():
    with patch.object(debt_expenses, "load_labels", return_value=etiquetas_df([CENA])), \
         con_supabase(deudas_df()):
        out = cargar_deudas_devengadas()

    fila = out.iloc[0]
    assert fila["MONTO"] == -36.83, "un gasto es negativo"
    assert fila["TIPO"] == TIPO_DEUDA
    assert fila["FECHA"] == pd.Timestamp("2026-09-06"), "la fecha es la del consumo, no la del pago"
    assert fila["DESCRIPCION"] == "Carretao"
    assert fila["categoria"] == "Alimentación"
    assert fila["tags"] == "Brasil_2026"
    assert fila["felicidad"] == 8.0
    assert fila["deuda_id"] == CENA


def test_el_deudor_lo_manda_supabase_no_la_etiqueta():
    with patch.object(debt_expenses, "load_labels", return_value=etiquetas_df([CENA])), \
         con_supabase(deudas_df()):
        out = cargar_deudas_devengadas()
    assert out.iloc[0]["deudor"] == "Ale"


def test_las_columnas_encajan_con_las_del_ledger():
    """
    Si no coinciden, un `concat` con `load_data()` inventaría columnas.

    La única de más es `SALDO_DEUDA`, y es deliberada: una transacción de banca no
    tiene deuda detrás. `aplicar_devengo` la abre del otro lado antes de concatenar.
    """
    from contabilidad.backend.services.debt_expenses import COLUMNA_SALDO
    from contabilidad.backend.services.transaction_service import load_data

    with patch.object(debt_expenses, "load_labels", return_value=etiquetas_df([CENA])), \
         con_supabase(deudas_df()):
        out = cargar_deudas_devengadas()

    ledger = load_data()
    if ledger.empty:
        pytest.skip("sin datos de origen en este entorno")
    faltan = set(out.columns) - set(ledger.columns)
    assert faltan == {COLUMNA_SALDO}, f"columnas que el ledger no tiene: {faltan}"


def test_el_saldo_pendiente_viaja_en_la_fila():
    """`SALDO_DEUDA` sale de Supabase en cada lectura, no del CSV."""
    from contabilidad.backend.services.debt_expenses import COLUMNA_SALDO

    with patch.object(debt_expenses, "load_labels", return_value=etiquetas_df([CENA])), \
         con_supabase(deudas_df()):
        out = cargar_deudas_devengadas()

    assert out[COLUMNA_SALDO].iloc[0] > 0


# ── Degradar sin caerse ──────────────────────────────────────────────────────

def test_si_supabase_falla_no_revienta_el_analisis():
    fake = MagicMock()
    fake.obtener_deudas_para_analisis.side_effect = RuntimeError("sin red")
    with patch.object(debt_expenses, "load_labels", return_value=etiquetas_df([CENA])), \
         patch.dict(sys.modules, {"contabilidad.debts.reading": fake}):
        out = cargar_deudas_devengadas()
    assert out.empty
    assert list(out.columns) == COLUMNAS


# ── Liquidaciones ────────────────────────────────────────────────────────────

def test_marcar_liquidaciones_reconoce_el_pago_id():
    df = pd.DataFrame({"pago_id": ["p-1", None, "", "nan", "---", "p-2"]})
    assert list(marcar_liquidaciones(df)) == [True, False, False, False, False, True]


def test_marcar_liquidaciones_sin_columna_no_marca_nada():
    df = pd.DataFrame({"MONTO": [-1.0, -2.0]})
    assert not marcar_liquidaciones(df).any()
