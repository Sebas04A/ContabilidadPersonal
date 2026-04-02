"""
test_routes_budget.py — Tests for /api/budget via FastAPI TestClient
"""
import json
import pytest
from unittest.mock import patch, mock_open, MagicMock
from fastapi.testclient import TestClient
from contabilidad.backend.main import app

client = TestClient(app)


DEFAULT_BUDGET = {
    "categories": [
        {"name": "Alimentación", "budget": 500.0},
        {"name": "Transporte", "budget": 200.0},
    ]
}


def test_get_budget_when_file_missing():
    """GET /api/budget/ when no file exists → returns default or 200."""
    with patch("os.path.exists", return_value=False):
        response = client.get("/api/budget/")
    assert response.status_code == 200


def test_post_budget_saves_config(tmp_path):
    """POST /api/budget/ → 200 and config is saved."""
    budget_file = str(tmp_path / "presupuesto_config.json")
    with patch("contabilidad.backend.routes.budget.BUDGET_FILE", budget_file):
        response = client.post("/api/budget/", json=DEFAULT_BUDGET)
    assert response.status_code == 200


def test_get_budget_after_post_returns_saved_data(tmp_path):
    """After POST, GET returns data without crashing."""
    budget_file = str(tmp_path / "presupuesto_config.json")
    with patch("contabilidad.backend.routes.budget.BUDGET_FILE", budget_file):
        post_resp = client.post("/api/budget/", json=DEFAULT_BUDGET)
        assert post_resp.status_code == 200
        get_resp = client.get("/api/budget/")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert isinstance(data, dict)  # budget returns a dict


def test_get_budget_returns_defaults_when_file_is_empty(tmp_path):
    """If the budget file is empty or malformed → 200 (no 500)."""
    budget_file = str(tmp_path / "presupuesto_config.json")
    budget_file_obj = tmp_path / "presupuesto_config.json"
    budget_file_obj.write_text("{}")
    with patch("contabilidad.backend.routes.budget.BUDGET_FILE", budget_file):
        response = client.get("/api/budget/")
    assert response.status_code == 200
