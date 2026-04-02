"""
test_variables_storage.py — Tests for InterpolationStorage (CRUD de CSV de grupos y pagos)

All tests use tmp_path to avoid touching real data files.
Correct signatures:
  - create_group(name, description=None, group_type='interpolated')
  - create_payment(group_id, amount, start_date, end_date, note=None)
  - save_entity_rule(name, attrs: dict)
"""
import pytest
import pandas as pd
from unittest.mock import patch


@pytest.fixture
def patched_storage(tmp_path):
    """Patch GROUPS_FILE and PAYMENTS_FILE to tmp_path."""
    groups_file = str(tmp_path / "grupos.csv")
    payments_file = str(tmp_path / "pagos.csv")
    base_path = str(tmp_path)

    with patch("contabilidad.backend.storage.variables_storage.GROUPS_FILE", groups_file), \
         patch("contabilidad.backend.storage.variables_storage.PAYMENTS_FILE", payments_file), \
         patch("contabilidad.backend.storage.variables_storage.BASE_DATA_PATH", base_path):
        from contabilidad.backend.storage.variables_storage import InterpolationStorage
        yield InterpolationStorage


# ── Groups CRUD ───────────────────────────────────────────────────────────────

def test_create_and_get_group(patched_storage):
    group = patched_storage.create_group(name="Renta", description="Pago mensual", group_type="fixed")
    assert group is not None
    assert group["name"] == "Renta"
    assert group["type"] == "fixed"

    groups = patched_storage.get_groups(type_filter="fixed")
    assert any(g["name"] == "Renta" for g in groups)


def test_get_groups_type_filter(patched_storage):
    patched_storage.create_group("Fixed G", "desc", group_type="fixed")
    patched_storage.create_group("Interp G", "desc", group_type="interpolated")

    fixed = patched_storage.get_groups(type_filter="fixed")
    interp = patched_storage.get_groups(type_filter="interpolated")

    assert all(g["type"] == "fixed" for g in fixed)
    assert all(g["type"] == "interpolated" for g in interp)


def test_update_group(patched_storage):
    group = patched_storage.create_group("Original", "desc", group_type="fixed")
    gid = group["id"]
    updated = patched_storage.update_group(gid, {"name": "Updated", "description": "new desc", "type": "fixed"})
    assert updated is not None
    assert updated["name"] == "Updated"


def test_update_nonexistent_group_returns_none(patched_storage):
    result = patched_storage.update_group("nonexistent-id", {"name": "X"})
    assert result is None


def test_delete_group(patched_storage):
    group = patched_storage.create_group("ToDelete", "desc", group_type="fixed")
    gid = group["id"]
    success = patched_storage.delete_group(gid)
    assert success is True
    groups = patched_storage.get_groups(type_filter="fixed")
    assert not any(g["id"] == gid for g in groups)


def test_delete_group_also_deletes_payments(patched_storage):
    group = patched_storage.create_group("WithPayments", "desc", group_type="fixed")
    gid = group["id"]
    patched_storage.create_payment(gid, 100.0, "2025-01-01", None)
    patched_storage.delete_group(gid)
    payments = patched_storage.get_payments(gid)
    assert len(payments) == 0


def test_delete_nonexistent_group_returns_false(patched_storage):
    result = patched_storage.delete_group("fake-id")
    assert result is False


# ── Payments CRUD ─────────────────────────────────────────────────────────────

def test_create_and_get_payment(patched_storage):
    group = patched_storage.create_group("G1", "desc", group_type="fixed")
    gid = group["id"]
    payment = patched_storage.create_payment(gid, 1500.0, "2025-01-01", "2025-01-31")
    assert payment is not None
    assert float(payment["amount"]) == 1500.0

    payments = patched_storage.get_payments(gid)
    assert len(payments) == 1
    assert float(payments[0]["amount"]) == 1500.0


def test_create_payment_with_null_end_date(patched_storage):
    group = patched_storage.create_group("G2", "desc", group_type="fixed")
    gid = group["id"]
    payment = patched_storage.create_payment(gid, 500.0, "2025-01-01", None)
    assert payment["end_date"] is None


def test_update_payment(patched_storage):
    group = patched_storage.create_group("G3", "desc", group_type="fixed")
    gid = group["id"]
    payment = patched_storage.create_payment(gid, 100.0, "2025-01-01", None)
    pid = payment["id"]
    updated = patched_storage.update_payment(pid, {"amount": 999.0, "start_date": "2025-01-01", "end_date": None, "note": ""})
    assert updated is not None
    assert float(updated["amount"]) == 999.0


def test_update_nonexistent_payment_returns_none(patched_storage):
    result = patched_storage.update_payment("fake-pid", {"amount": 100.0})
    assert result is None


def test_delete_payment(patched_storage):
    group = patched_storage.create_group("G4", "desc", group_type="fixed")
    gid = group["id"]
    payment = patched_storage.create_payment(gid, 200.0, "2025-02-01", None)
    pid = payment["id"]
    success = patched_storage.delete_payment(pid)
    assert success is True
    payments = patched_storage.get_payments(gid)
    assert not any(p["id"] == pid for p in payments)


def test_delete_nonexistent_payment_returns_false(patched_storage):
    result = patched_storage.delete_payment("fake-pid")
    assert result is False


def test_multiple_payments_for_same_group(patched_storage):
    group = patched_storage.create_group("G5", "desc", group_type="fixed")
    gid = group["id"]
    patched_storage.create_payment(gid, 100.0, "2025-01-01", "2025-01-31")
    patched_storage.create_payment(gid, 200.0, "2025-02-01", "2025-02-28")
    payments = patched_storage.get_payments(gid)
    assert len(payments) == 2
