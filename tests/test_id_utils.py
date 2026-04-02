"""
test_id_utils.py — Tests for generate_unique_id and add_id_column in utils/id_utils.py
"""
import pytest
import pandas as pd
from contabilidad.backend.utils.id_utils import generate_unique_id, add_id_column


# ── generate_unique_id ────────────────────────────────────────────────────────

def test_determinism_same_inputs_same_hash():
    id1 = generate_unique_id("2025-01-01", 100.0, "SUPERMERCADO", "BANCA", discriminator=0)
    id2 = generate_unique_id("2025-01-01", 100.0, "SUPERMERCADO", "BANCA", discriminator=0)
    assert id1 == id2


def test_different_date_gives_different_id():
    id1 = generate_unique_id("2025-01-01", 100.0, "DESC", "BANCA")
    id2 = generate_unique_id("2025-01-02", 100.0, "DESC", "BANCA")
    assert id1 != id2


def test_different_monto_gives_different_id():
    id1 = generate_unique_id("2025-01-01", 100.0, "DESC", "BANCA")
    id2 = generate_unique_id("2025-01-01", 200.0, "DESC", "BANCA")
    assert id1 != id2


def test_different_discriminator_gives_different_id():
    id1 = generate_unique_id("2025-01-01", 100.0, "DESC", "BANCA", discriminator=0)
    id2 = generate_unique_id("2025-01-01", 100.0, "DESC", "BANCA", discriminator=1)
    assert id1 != id2


def test_returns_32_char_md5_string():
    result = generate_unique_id("2025-01-01", 100.0, "SOME DESC", "TARJETA")
    assert isinstance(result, str)
    assert len(result) == 32


def test_handles_pandas_timestamp_date():
    ts = pd.Timestamp("2025-06-15")
    id1 = generate_unique_id(ts, 50.0, "PAGO", "TARJETA")
    id2 = generate_unique_id("2025-06-15", 50.0, "PAGO", "TARJETA")
    assert id1 == id2


def test_handles_bad_monto_gracefully():
    # Should not raise; falls back to "0.00"
    result = generate_unique_id("2025-01-01", "NOT_A_NUMBER", "DESC", "BANCA")
    assert isinstance(result, str)
    assert len(result) == 32


# ── add_id_column ─────────────────────────────────────────────────────────────

@pytest.fixture
def simple_df():
    return pd.DataFrame({
        "FECHA": pd.date_range("2025-01-01", periods=3, freq="D"),
        "MONTO": [100.0, -50.0, 200.0],
        "DESCRIPCION": ["UBER", "NETFLIX", "SUPERMERCADO"],
    })


def test_add_id_column_adds_id(simple_df):
    result = add_id_column(simple_df, source_type="BANCA")
    assert "id" in result.columns


def test_add_id_column_unique_per_row(simple_df):
    result = add_id_column(simple_df, source_type="BANCA")
    assert result["id"].nunique() == len(simple_df)


def test_add_id_column_is_deterministic(simple_df):
    r1 = add_id_column(simple_df.copy(), source_type="BANCA")
    r2 = add_id_column(simple_df.copy(), source_type="BANCA")
    assert r1["id"].tolist() == r2["id"].tolist()


def test_duplicate_rows_get_different_ids():
    df = pd.DataFrame({
        "FECHA": pd.to_datetime(["2025-01-01", "2025-01-01"]),
        "MONTO": [100.0, 100.0],
        "DESCRIPCION": ["DUP", "DUP"],
    })
    result = add_id_column(df, source_type="BANCA")
    assert result["id"].iloc[0] != result["id"].iloc[1]


def test_empty_df_returned_unchanged():
    df = pd.DataFrame()
    result = add_id_column(df, source_type="BANCA")
    assert result.empty


def test_missing_required_column_returns_df_without_id():
    df = pd.DataFrame({
        "FECHA": pd.date_range("2025-01-01", periods=2, freq="D"),
        "DESCRIPCION": ["A", "B"],
        # MONTO is missing
    })
    result = add_id_column(df, source_type="BANCA")
    assert "id" not in result.columns
