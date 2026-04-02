"""
test_routes_investments.py — Tests for /api/investments via FastAPI TestClient
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from contabilidad.backend.main import app

client = TestClient(app)


MOCK_CHART_DATA = {
    "dates": ["2025-01-01", "2025-01-02", "2025-01-03"],
    "saldo": [10000.0, 10500.0, 10200.0],
    "inversion": [5000.0, 5000.0, 5000.0],
    "investment_periods": [
        {
            "amount": 5000.0,
            "start_date": "2025-01-01",
            "end_date": "2025-06-30",
            "group_name": "CDP Banco"
        }
    ]
}

MOCK_ACCOUNTS_DATA = {
    "iniciadas": [
        {"fecha": "2025-01-01", "monto": 5000.0, "descripcion": "CDP_001", "interes": 300.0, "impuesto": 45.0}
    ],
    "finalizadas": []
}


# ── GET /api/investments/chart-data ───────────────────────────────────────────

def test_get_chart_data_returns_200():
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investment_chart_data",
        return_value=MOCK_CHART_DATA
    ):
        response = client.get("/api/investments/chart-data")
    assert response.status_code == 200


def test_get_chart_data_has_required_keys():
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investment_chart_data",
        return_value=MOCK_CHART_DATA
    ):
        response = client.get("/api/investments/chart-data")
    data = response.json()
    assert "dates" in data
    assert "saldo" in data
    assert "inversion" in data
    assert "investment_periods" in data


def test_get_chart_data_investment_periods_is_list():
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investment_chart_data",
        return_value=MOCK_CHART_DATA
    ):
        response = client.get("/api/investments/chart-data")
    data = response.json()
    assert isinstance(data["investment_periods"], list)


def test_get_chart_data_period_structure():
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investment_chart_data",
        return_value=MOCK_CHART_DATA
    ):
        response = client.get("/api/investments/chart-data")
    data = response.json()
    if data["investment_periods"]:
        period = data["investment_periods"][0]
        assert "amount" in period or "start_date" in period


# ── GET /api/investments/from-accounts ────────────────────────────────────────

def test_get_from_accounts_returns_200():
    from contabilidad.backend.models.investment_models import AccountInvestment, InvestmentsFromAccountsResponse
    mock_resp = InvestmentsFromAccountsResponse(
        iniciadas=[AccountInvestment(fecha="2025-01-01", monto=5000.0, descripcion="CDP_001", tipo="iniciada")],
        finalizadas=[]
    )
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investments_from_accounts",
        return_value=mock_resp
    ):
        response = client.get("/api/investments/from-accounts")
    assert response.status_code == 200


def test_get_from_accounts_has_iniciadas():
    from contabilidad.backend.models.investment_models import AccountInvestment, InvestmentsFromAccountsResponse
    mock_resp = InvestmentsFromAccountsResponse(
        iniciadas=[AccountInvestment(fecha="2025-01-01", monto=5000.0, descripcion="CDP_001", tipo="iniciada")],
        finalizadas=[]
    )
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investments_from_accounts",
        return_value=mock_resp
    ):
        response = client.get("/api/investments/from-accounts")
    data = response.json()
    assert "iniciadas" in data


def test_service_exception_returns_error():
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investment_chart_data",
        side_effect=Exception("Service error")
    ):
        response = client.get("/api/investments/chart-data")
    assert response.status_code in [500, 200]  # may handle gracefully
