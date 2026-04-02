"""
test_routes_payments.py — Tests for /api/payments (groups and payments CRUD) via TestClient
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from contabilidad.backend.main import app

client = TestClient(app)


# ── Shared mock data ──────────────────────────────────────────────────────────

MOCK_GROUP = {
    "id": "g001",
    "name": "Renta",
    "description": "Pago de renta mensual",
    "type": "fixed",
}

MOCK_PAYMENT = {
    "id": "p001",
    "group_id": "g001",
    "amount": 1500.0,
    "start_date": "2025-01-01",
    "end_date": "2025-01-31",
    "note": "Enero",
}


# ── Groups ────────────────────────────────────────────────────────────────────

def test_get_empty_groups_returns_200():
    with patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_groups", return_value=[]):
        response = client.get("/api/payments/groups?type=fixed")
    assert response.status_code == 200
    assert response.json() == []


def test_get_groups_returns_list():
    with patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_groups", return_value=[MOCK_GROUP]):
        response = client.get("/api/payments/groups?type=fixed")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Renta"


def test_post_create_group():
    with patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.create_group", return_value=MOCK_GROUP):
        response = client.post("/api/payments/groups", json={
            "name": "Renta",
            "description": "Pago de renta mensual",
            "type": "fixed",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Renta"
    assert "id" in data


def test_put_update_group():
    updated = {**MOCK_GROUP, "name": "Renta Actualizada"}
    with patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.update_group", return_value=updated):
        response = client.put("/api/payments/groups/g001", json={
            "name": "Renta Actualizada",
            "description": "desc",
            "type": "fixed",
        })
    assert response.status_code == 200
    assert response.json()["name"] == "Renta Actualizada"


def test_put_update_group_not_found():
    with patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.update_group", return_value=None):
        response = client.put("/api/payments/groups/nonexistent", json={
            "name": "X", "description": "Y", "type": "fixed"
        })
    assert response.status_code == 404


def test_delete_group_success():
    with patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.delete_group", return_value=True):
        response = client.delete("/api/payments/groups/g001")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_delete_group_not_found():
    with patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.delete_group", return_value=False):
        response = client.delete("/api/payments/groups/nonexistent")
    assert response.status_code == 404


# ── Payments ──────────────────────────────────────────────────────────────────

def test_get_group_payments():
    with patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_payments", return_value=[MOCK_PAYMENT]):
        response = client.get("/api/payments/groups/g001/payments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["amount"] == 1500.0


def test_post_create_payment():
    with patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.get_group", return_value=MOCK_GROUP), \
         patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.create_payment", return_value=MOCK_PAYMENT), \
         patch("contabilidad.backend.storage.data_pipeline.get_pipeline"):
        response = client.post("/api/payments/groups/g001/payments", json={
            "amount": 1500.0,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "note": "Enero",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == 1500.0


def test_post_create_payment_group_not_found():
    with patch("contabilidad.backend.routes.payments.InterpolationStorage.get_group", return_value=None):
        response = client.post("/api/payments/groups/nonexistent/payments", json={
            "amount": 100.0,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "note": "",
        })
    assert response.status_code == 404


def test_put_update_payment():
    updated = {**MOCK_PAYMENT, "amount": 2000.0}
    with patch("contabilidad.backend.routes.payments.InterpolationStorage.update_payment", return_value=updated), \
         patch("contabilidad.backend.storage.data_pipeline.get_pipeline"):
        response = client.put("/api/payments/payments/p001", json={
            "amount": 2000.0,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "note": "",
        })
    assert response.status_code == 200
    assert response.json()["amount"] == 2000.0


def test_put_update_payment_not_found():
    with patch("contabilidad.backend.routes.payments.InterpolationStorage.update_payment", return_value=None):
        response = client.put("/api/payments/payments/nonexistent", json={
            "amount": 100.0, "start_date": "2025-01-01", "end_date": "2025-12-31", "note": ""
        })
    assert response.status_code == 404


def test_delete_payment_success():
    with patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.delete_payment", return_value=True), \
         patch("contabilidad.backend.storage.data_pipeline.get_pipeline"):
        response = client.delete("/api/payments/payments/p001")
    assert response.status_code == 200


def test_delete_payment_not_found():
    with patch("contabilidad.backend.storage.variables_storage.InterpolationStorage.delete_payment", return_value=False):
        response = client.delete("/api/payments/payments/nonexistent")
    assert response.status_code == 404
