"""
test_routes_dashboard.py — Tests for /api/dashboard via FastAPI TestClient

Dashboard endpoint is at /api/dashboard/chart-data (not /).
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from contabilidad.backend.main import app

client = TestClient(app)


MOCK_DASHBOARD_RESPONSE = MagicMock()
MOCK_DASHBOARD_RESPONSE.model_dump.return_value = {
    "dates": ["2025-01-01", "2025-01-02"],
    "data": [],
}


# ── GET /api/dashboard/chart-data ─────────────────────────────────────────────

def test_get_dashboard_chart_data_returns_200():
    """Dashboard chart-data endpoint should return 200 with mock service."""
    from contabilidad.backend.models.dashboard_models import DashboardResponse, ChartDataPoint, DailyVariation
    mock_resp = DashboardResponse(data=[], highlighted_days=[])
    with patch(
        "contabilidad.backend.services.dashboard_service.DashboardService.get_chart_data",
        return_value=mock_resp
    ):
        response = client.get("/api/dashboard/chart-data")
    assert response.status_code == 200


def test_get_dashboard_config_returns_200():
    response = client.get("/api/dashboard/config")
    assert response.status_code == 200


def test_get_dashboard_config_has_features():
    response = client.get("/api/dashboard/config")
    data = response.json()
    assert "features" in data or "highlighted_days" in data


# ── Cache endpoints ───────────────────────────────────────────────────────────

def test_get_cache_stats_returns_200():
    response = client.get("/api/cache/stats")
    assert response.status_code == 200


def test_get_cache_stats_has_expected_keys():
    response = client.get("/api/cache/stats")
    data = response.json()
    assert "source_cache" in data or "transformation_cache" in data


def test_post_cache_invalidate_all():
    response = client.post("/api/cache/invalidate?scope=all")
    assert response.status_code == 200


def test_post_cache_invalidate_source():
    response = client.post("/api/cache/invalidate?scope=source")
    assert response.status_code == 200


def test_post_cache_invalidate_invalid_scope():
    response = client.post("/api/cache/invalidate?scope=invalid_scope")
    assert response.status_code == 400
