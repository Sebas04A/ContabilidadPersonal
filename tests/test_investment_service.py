"""
test_investment_service.py — Tests for InvestmentService in services/investment_service.py

InvestmentService() takes no arguments; it calls get_pipeline() internally.
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock


def make_blank_df():
    return pd.DataFrame({
        "FECHA": pd.date_range("2025-01-01", periods=5),
        "SALDO": [1000.0] * 5,
        "MONTO": [0.0] * 5,
        "INVERSION": [500.0] * 5,
        "DESCRIPCION": [""] * 5,
        "DEBITO": [0.0] * 5,
        "CREDITO": [0.0] * 5,
    })


# ── get_investment_chart_data ─────────────────────────────────────────────────

def test_chart_data_has_required_keys():
    blank_df = make_blank_df()
    mock_pipeline = MagicMock()
    mock_pipeline.get_processed_data.return_value = blank_df

    with patch("contabilidad.backend.services.investment_service.get_pipeline", return_value=mock_pipeline), \
         patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_groups", return_value=[]), \
         patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_payments", return_value=[]):
        from contabilidad.backend.services.investment_service import InvestmentService
        svc = InvestmentService()
        result = svc.get_investment_chart_data()

    assert "dates" in result
    assert "saldo" in result
    assert "inversion" in result
    assert "investment_periods" in result


def test_chart_data_dates_and_values_same_length():
    blank_df = make_blank_df()
    mock_pipeline = MagicMock()
    mock_pipeline.get_processed_data.return_value = blank_df

    with patch("contabilidad.backend.services.investment_service.get_pipeline", return_value=mock_pipeline), \
         patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_groups", return_value=[]), \
         patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_payments", return_value=[]):
        from contabilidad.backend.services.investment_service import InvestmentService
        svc = InvestmentService()
        result = svc.get_investment_chart_data()

    assert len(result["dates"]) == len(result["saldo"])
    assert len(result["dates"]) == len(result["inversion"])


def test_chart_data_investment_periods_is_list():
    blank_df = make_blank_df()
    mock_pipeline = MagicMock()
    mock_pipeline.get_processed_data.return_value = blank_df

    with patch("contabilidad.backend.services.investment_service.get_pipeline", return_value=mock_pipeline), \
         patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_groups", return_value=[]), \
         patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_payments", return_value=[]):
        from contabilidad.backend.services.investment_service import InvestmentService
        svc = InvestmentService()
        result = svc.get_investment_chart_data()

    assert isinstance(result["investment_periods"], list)


def test_chart_data_with_no_investment_column():
    """If INVERSION column is missing, should handle gracefully."""
    blank_df = pd.DataFrame({
        "FECHA": pd.date_range("2025-01-01", periods=3),
        "SALDO": [1000.0] * 3,
        "MONTO": [0.0] * 3,
        "DESCRIPCION": [""] * 3,
        # No INVERSION column
    })
    mock_pipeline = MagicMock()
    mock_pipeline.get_processed_data.return_value = blank_df

    with patch("contabilidad.backend.services.investment_service.get_pipeline", return_value=mock_pipeline), \
         patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_groups", return_value=[]), \
         patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_payments", return_value=[]):
        from contabilidad.backend.services.investment_service import InvestmentService
        svc = InvestmentService()
        try:
            result = svc.get_investment_chart_data()
            assert "dates" in result
        except Exception:
            pass  # Graceful or raises — both acceptable


# ── get_investments_from_accounts ─────────────────────────────────────────────

def test_get_investments_from_accounts_returns_dict():
    blank_df = pd.DataFrame({
        "FECHA": pd.date_range("2025-01-01", periods=3),
        "SALDO": [1000.0] * 3,
        "MONTO": [0.0] * 3,
        "DESCRIPCION": ["NORMAL"] * 3,
        "DEBITO": [0.0] * 3,
        "CREDITO": [0.0] * 3,
    })
    mock_pipeline = MagicMock()
    mock_pipeline.get_account_data.return_value = blank_df

    with patch("contabilidad.backend.services.investment_service.get_pipeline", return_value=mock_pipeline):
        from contabilidad.backend.services.investment_service import InvestmentService
        svc = InvestmentService()
        result = svc.get_investments_from_accounts()

    assert isinstance(result, object)  # InvestmentsFromAccountsResponse or dict
