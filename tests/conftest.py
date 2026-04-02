"""
conftest.py — Global fixtures for the ContabilidadPersonal test suite.
All tests use synthetic data. No real files in `data/` are touched.
"""
import sys
import os
import pytest
import pandas as pd
from datetime import date, datetime
from unittest.mock import patch, MagicMock


# ── Sample DataFrames ────────────────────────────────────────────────────────

@pytest.fixture
def sample_banca_df():
    """Synthetic bank account DataFrame with standard columns."""
    dates = pd.date_range("2025-01-01", periods=10, freq="D")
    return pd.DataFrame({
        "FECHA": dates,
        "SALDO": [1000.0 + i * 100 for i in range(10)],
        "DESCRIPCION": [f"DESCRIPCION_{i}" for i in range(10)],
        "MONTO": [(-50.0 if i % 2 == 0 else 100.0) for i in range(10)],
        "DEBITO": [(50.0 if i % 2 == 0 else 0.0) for i in range(10)],
        "CREDITO": [(0.0 if i % 2 == 0 else 100.0) for i in range(10)],
        "TIPO": "BANCA",
    })


@pytest.fixture
def sample_tarjeta_df():
    """Synthetic credit card DataFrame."""
    dates = pd.date_range("2025-01-05", periods=5, freq="D")
    return pd.DataFrame({
        "FECHA": dates,
        "DESCRIPCION": [f"TARJETA_GASTO_{i}" for i in range(5)],
        "MONTO": [-200.0 - i * 50 for i in range(5)],
        "VALOR": [200.0 + i * 50 for i in range(5)],
        "TIPO": "TARJETA",
    })


@pytest.fixture
def sample_transactions_df(sample_banca_df):
    """Bank DataFrame enriched with labeling columns."""
    df = sample_banca_df.copy()
    df["id"] = [f"id_{i:04d}" for i in range(len(df))]
    df["revisado"] = False
    df["nombre_limpio"] = None
    df["categoria"] = None
    df["tags"] = None
    df["prioridad"] = None
    df["felicidad"] = None
    df["notas"] = None
    df["es_fijo"] = False
    df["es_reembolsable"] = False
    df["deudor"] = None
    return df


# ── Payment fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def sample_payment_obj():
    """A single Payment object for use in tests."""
    from contabilidad.models import Payment
    return Payment(
        amount=500.0,
        start_date=pd.Timestamp("2025-01-03"),
        end_date=pd.Timestamp("2025-01-07"),
    )


@pytest.fixture
def sample_groups_csv(tmp_path):
    """Write grupos.csv to a tmp dir and return the path."""
    grupos_path = tmp_path / "interpolaciones" / "grupos.csv"
    grupos_path.parent.mkdir(parents=True, exist_ok=True)
    grupos_path.write_text(
        "id,name,description,type\n"
        "g001,Renta,Pago mensual de renta,fixed\n"
        "g002,Sueldo,Ingreso mensual,interpolated\n"
    )
    return tmp_path


@pytest.fixture
def sample_pagos_csv(tmp_path):
    """Write pagos.csv to a tmp dir and return the path (linked to sample groups)."""
    pagos_path = tmp_path / "interpolaciones" / "pagos.csv"
    pagos_path.parent.mkdir(parents=True, exist_ok=True)
    pagos_path.write_text(
        "id,group_id,amount,start_date,end_date,note\n"
        "p001,g001,1500.0,2025-01-01,2025-01-31,Enero\n"
        "p002,g001,1500.0,2025-02-01,2025-02-28,Febrero\n"
        "p003,g002,3000.0,2025-01-15,,Sueldo enero\n"
    )
    return tmp_path


# ── FastAPI TestClient ────────────────────────────────────────────────────────

@pytest.fixture
def test_client(mock_pipeline):
    """FastAPI TestClient with the pipeline mocked to avoid real file I/O."""
    from fastapi.testclient import TestClient
    from contabilidad.backend.main import app
    return TestClient(app)


# ── Pipeline mock ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_pipeline(sample_banca_df, sample_tarjeta_df):
    """
    Patches the global pipeline singleton so no file I/O happens.
    Returns the mock pipeline instance.
    """
    pipeline_mock = MagicMock()
    pipeline_mock.get_account_data.return_value = sample_banca_df.copy()
    pipeline_mock.get_bank_data.return_value = sample_banca_df.copy()
    pipeline_mock.get_credit_card_data.return_value = sample_tarjeta_df.copy()
    pipeline_mock.get_unified_credit_card_data.return_value = sample_tarjeta_df.copy()
    pipeline_mock.get_credit_card_metadata.return_value = pd.DataFrame()
    pipeline_mock.get_processed_data.return_value = sample_banca_df.copy()
    pipeline_mock.get_cache_stats.return_value = {
        "source_cache": {"entries": 0, "keys": [], "total_memory_mb": 0},
        "transformation_cache": {"entries": 0, "keys": [], "total_memory_mb": 0},
        "transformations_registered": 2,
    }

    with patch(
        "contabilidad.backend.storage.data_pipeline.get_pipeline",
        return_value=pipeline_mock
    ):
        yield pipeline_mock
