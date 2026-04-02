"""
test_routes_transactions.py — Tests for /api/transactions via FastAPI TestClient

All file I/O is mocked. Builds on the mock pipeline from conftest.py.
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from contabilidad.backend.main import app

client = TestClient(app)


# ── Shared mock data ──────────────────────────────────────────────────────────

def make_source_df(n=5):
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    df = pd.DataFrame({
        "id": [f"id_{i:04d}" for i in range(n)],
        "FECHA": dates,
        "DESCRIPCION": [f"PAGO_{i}" for i in range(n)],
        "MONTO": [-100.0 * (i + 1) for i in range(n)],
        "SALDO": [5000.0 - i * 100 for i in range(n)],
        "DEBITO": [100.0 * (i + 1) for i in range(n)],
        "CREDITO": [0.0] * n,
        "TIPO": "BANCA",
        "revisado": [False] * n,
        "nombre_limpio": [None] * n,
        "categoria": [None] * n,
        "tags": [None] * n,
        "prioridad": [None] * n,
        "felicidad": [None] * n,
        "notas": [None] * n,
        "es_fijo": [False] * n,
        "es_reembolsable": [False] * n,
        "deudor": [None] * n,
        "group_id": [None] * n,
    })
    return df


# ── List / Filter endpoints ───────────────────────────────────────────────────

def test_get_transactions_returns_200():
    with patch("contabilidad.backend.services.transaction_service.load_data", return_value=make_source_df()), \
         patch("contabilidad.backend.storage.rules_storage.apply_rules_to_dataframe", side_effect=lambda df: df):
        response = client.get("/api/transactions/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_transactions_returns_list_of_dicts():
    with patch("contabilidad.backend.services.transaction_service.load_data", return_value=make_source_df()), \
         patch("contabilidad.backend.storage.rules_storage.apply_rules_to_dataframe", side_effect=lambda df: df):
        response = client.get("/api/transactions/")
    data = response.json()
    if len(data) > 0:
        assert isinstance(data[0], dict)


def test_get_transactions_with_valid_source_returns_list():
    """GET /api/transactions/?source=banca always returns a list (may be from real data)."""
    response = client.get("/api/transactions/?source=banca")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_transactions_filter_pending_only():
    df = make_source_df(4)
    df.loc[2, "revisado"] = True
    with patch("contabilidad.backend.services.transaction_service.load_data", return_value=df), \
         patch("contabilidad.backend.storage.rules_storage.apply_rules_to_dataframe", side_effect=lambda df: df):
        response = client.get("/api/transactions/?pending_only=true")
    data = response.json()
    # All returned should be pending (revisado=False)
    assert all(row.get("revisado") is False or row.get("revisado") == "False" or not row.get("revisado")
               for row in data)


def test_get_available_dates_returns_list():
    with patch("contabilidad.backend.services.transaction_service.load_data", return_value=make_source_df()):
        response = client.get("/api/transactions/dates")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_stats_returns_correct_structure():
    with patch("contabilidad.backend.services.transaction_service.load_data", return_value=make_source_df(3)):
        response = client.get("/api/transactions/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_monto" in data
    assert "count" in data
    assert "pending" in data
    assert "reviewed" in data


def test_get_categories_returns_list():
    df = make_source_df(3)
    df["categoria"] = ["Alimentación", "Transporte", None]
    with patch("contabilidad.backend.services.transaction_service.load_labels", return_value=df):
        response = client.get("/api/transactions/categories")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_tags_returns_list():
    df = make_source_df(2)
    df["tags"] = ["uber,taxi", "restaurante"]
    with patch("contabilidad.backend.services.transaction_service.load_labels", return_value=df):
        response = client.get("/api/transactions/tags")
    assert response.status_code == 200
    tags = response.json()
    assert isinstance(tags, list)
    # Tags come from real or mocked data, just verify it's a list of strings
    assert all(isinstance(t, str) for t in tags)


# ── Update endpoint ───────────────────────────────────────────────────────────

def test_put_transaction_returns_200():
    source_df = make_source_df(3)
    labels_df = pd.DataFrame(columns=["source_id", "group_id", "nombre_limpio", "categoria"])
    with patch("contabilidad.backend.routes.transactions.load_source_data", return_value=source_df), \
         patch("contabilidad.backend.routes.transactions.load_labels", return_value=labels_df), \
         patch("contabilidad.backend.routes.transactions.save_transaction_labels"), \
         patch("contabilidad.backend.routes.transactions.rules_service.save_rule_map"):
        response = client.put("/api/transactions/id_0000", json={
            "nombre_limpio": "Uber",
            "categoria": "Transporte",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "updated"
    assert "nombre_limpio" in data["updated_fields"]


def test_put_transaction_saves_rule_when_name_differs():
    source_df = make_source_df(1)
    source_df.iloc[0, source_df.columns.get_loc("DESCRIPCION")] = "PAGO UBER TRIP"
    labels_df = pd.DataFrame(columns=["source_id", "group_id", "nombre_limpio"])

    save_rule_called = {"called": False}

    def mock_save_rule(desc, name):
        save_rule_called["called"] = True

    with patch("contabilidad.backend.routes.transactions.load_source_data", return_value=source_df), \
         patch("contabilidad.backend.routes.transactions.load_labels", return_value=labels_df), \
         patch("contabilidad.backend.routes.transactions.save_transaction_labels"), \
         patch("contabilidad.backend.routes.transactions.rules_service.save_rule_map", side_effect=mock_save_rule):
        client.put("/api/transactions/id_0000", json={"nombre_limpio": "Uber"})

    assert save_rule_called["called"] is True


def test_put_transaction_not_found_returns_404():
    source_df = make_source_df(2)
    with patch("contabilidad.backend.services.transaction_service.load_source_data", return_value=source_df):
        response = client.put("/api/transactions/NONEXISTENT_ID", json={"nombre_limpio": "Test"})
    assert response.status_code == 404


# ── Group / Split endpoints ───────────────────────────────────────────────────

def test_post_group_transactions():
    source_df = make_source_df(3)
    labels_df = pd.DataFrame(columns=["source_id", "group_id", "nombre_limpio"])
    with patch("contabilidad.backend.routes.transactions.load_source_data", return_value=source_df), \
         patch("contabilidad.backend.routes.transactions.load_labels", return_value=labels_df), \
         patch("contabilidad.backend.routes.transactions.save_transaction_labels"):
        response = client.post("/api/transactions/group", json={
            "transaction_ids": ["id_0000", "id_0001"],
            "master_data": None
        })
    assert response.status_code == 200
    data = response.json()
    assert "group_id" in data
    assert data["count"] == 2


def test_post_group_empty_ids_returns_400():
    response = client.post("/api/transactions/group", json={"transaction_ids": []})
    assert response.status_code == 400


def test_post_split_transaction():
    source_df = make_source_df(2)
    with patch("contabilidad.backend.routes.transactions.load_source_data", return_value=source_df), \
         patch("contabilidad.backend.routes.transactions.save_transaction_split"):
        response = client.post("/api/transactions/id_0000/split", json={
            "splits": [
                {"monto": 50.0, "nombre_limpio": "Parte 1"},
                {"monto": 50.0, "nombre_limpio": "Parte 2"},
            ]
        })
    assert response.status_code == 200
    assert response.json()["parts"] == 2


def test_post_split_transaction_not_found():
    source_df = make_source_df(2)
    with patch("contabilidad.backend.routes.transactions.load_source_data", return_value=source_df):
        response = client.post("/api/transactions/NONEXISTENT/split", json={
            "splits": [{"monto": 50.0}]
        })
    assert response.status_code == 404
