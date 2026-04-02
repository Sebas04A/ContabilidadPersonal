"""
test_transform_investments.py — Tests for transform_investments() in storage/transformations/investments.py
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock


@pytest.fixture
def base_df():
    dates = pd.date_range("2025-01-01", periods=10, freq="D")
    return pd.DataFrame({
        "FECHA": dates,
        "MONTO": [100.0] * 10,
        "SALDO": [1000.0 + i * 100 for i in range(10)],
        "DESCRIPCION": [f"DESC_{i}" for i in range(10)],
    })


# ── No data ───────────────────────────────────────────────────────────────────

def test_no_groups_column_defaults_to_zero(base_df):
    with patch(
        "contabilidad.backend.storage.variables_storage.InterpolationStorage.get_groups",
        return_value=[]
    ), patch(
        "contabilidad.backend.storage.variables_storage.InterpolationStorage.get_payments",
        return_value=[]
    ):
        from contabilidad.backend.storage.transformations.investments import transform_investments
        result = transform_investments(base_df.copy())
    assert "INVERSION" in result.columns
    assert (result["INVERSION"].fillna(0) == 0).all()


def test_column_added_even_with_no_groups(base_df):
    with patch(
        "contabilidad.backend.storage.variables_storage.InterpolationStorage.get_groups",
        return_value=[]
    ):
        from contabilidad.backend.storage.transformations.investments import transform_investments
        result = transform_investments(base_df.copy())
    assert "INVERSION" in result.columns


# ── With data ─────────────────────────────────────────────────────────────────

def test_with_fixed_payments_fills_investment_column(base_df):
    groups = [{"id": "g001", "name": "CDP", "type": "fixed"}]
    payments = [{"id": "p001", "group_id": "g001", "amount": 500.0,
                 "start_date": "2025-01-03", "end_date": "2025-01-07", "note": ""}]

    with patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_groups", return_value=groups), \
         patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_payments", return_value=payments):
        from contabilidad.backend.storage.transformations import investments as inv_mod
        import importlib
        importlib.reload(inv_mod)
        result = inv_mod.transform_investments(base_df.copy())

    assert "INVERSION" in result.columns
    # At least one row should have the investment value
    non_zero = result[result["INVERSION"].fillna(0) != 0]
    assert len(non_zero) > 0


# ── Error handling ────────────────────────────────────────────────────────────

def test_storage_error_handled_gracefully(base_df):
    with patch(
        "contabilidad.backend.storage.variables_storage.InterpolationStorage.get_groups",
        side_effect=Exception("Storage error")
    ):
        from contabilidad.backend.storage.transformations.investments import transform_investments
        result = transform_investments(base_df.copy())
    # Should not raise; INVERSION column should exist
    assert "INVERSION" in result.columns
    assert (result["INVERSION"].fillna(0) == 0).all()
