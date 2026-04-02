"""
test_routes_sync.py — Tests for /api/sync endpoints using FastAPI TestClient
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from contabilidad.backend.main import app

client = TestClient(app)


def test_get_sync_status_returns_200():
    """GET /api/sync/status should always return 200 with expected keys."""
    response = client.get("/api/sync/status")
    assert response.status_code == 200
    data = response.json()
    assert "sync_module" in data
    assert "cuenta_source" in data
    assert "tarjeta_source" in data
    assert "errors" in data


def test_get_sync_status_errors_is_list():
    response = client.get("/api/sync/status")
    data = response.json()
    assert isinstance(data["errors"], list)


def test_post_sync_with_mocked_module():
    """POST /api/sync/ with sincronizacion module mocked → should return 200."""
    mock_module = MagicMock()
    mock_module.sincronizar_db.return_value = (5, "5 new records added")

    with patch.dict("sys.modules", {"sincronizacion": mock_module}):
        response = client.post(
            "/api/sync/",
            json={"fecha_inicio": "2025-01-01", "overwrite": False}
        )
    assert response.status_code == 200
    data = response.json()
    assert "records_added" in data
    assert data["records_added"] == 5


def test_post_sync_missing_module_returns_500():
    """If sincronizacion module is missing → 500."""
    with patch.dict("sys.modules", {"sincronizacion": None}):
        response = client.post(
            "/api/sync/",
            json={"fecha_inicio": "2025-01-01", "overwrite": False}
        )
    # Either 500 or ImportError message
    assert response.status_code in [500, 422]


def test_post_sync_invalidates_cache():
    """After POST /api/sync/, the pipeline cache should be invalidated."""
    mock_module = MagicMock()
    mock_module.sincronizar_db.return_value = (0, None)

    mock_pipeline = MagicMock()

    with patch.dict("sys.modules", {"sincronizacion": mock_module}), \
         patch("contabilidad.backend.storage.data_pipeline.get_pipeline", return_value=mock_pipeline):
        client.post("/api/sync/", json={"fecha_inicio": "2025-01-01", "overwrite": False})

    mock_pipeline.invalidate_cache.assert_called_once_with(scope="all")
