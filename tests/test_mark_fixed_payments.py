"""
test_mark_fixed_payments.py — Tests for mark_fixed_payments() in modules/account/get_variables.py
"""
import pytest
import pandas as pd
from contabilidad.backend.services.bank_parser.get_variables import mark_fixed_payments
from contabilidad.models import Payment


COL = "INVERSION"


@pytest.fixture
def base_range_df():
    """DataFrame spanning Jan 1-10, 2025."""
    dates = pd.date_range("2025-01-01", periods=10, freq="D")
    return pd.DataFrame({"FECHA": dates})


def make_payment(amount, start, end):
    """Helper to create a Payment with Timestamp dates."""
    return Payment(
        amount=float(amount),
        start_date=pd.Timestamp(start) if start else None,
        end_date=pd.Timestamp(end) if end else None,
    )


# ── Column creation ───────────────────────────────────────────────────────────

def test_no_payments_column_is_zero(base_range_df):
    result = mark_fixed_payments(base_range_df, [], COL)
    assert COL in result.columns
    assert (result[COL].fillna(0) == 0).all()


# ── Basic range behaviour ─────────────────────────────────────────────────────

def test_payment_within_range_fills_monto(base_range_df):
    p = make_payment(500.0, "2025-01-03", "2025-01-05")
    result = mark_fixed_payments(base_range_df, [p], COL)
    # Rows for dates 2025-01-03, 2025-01-04 (and maybe 01-05 depending on
    # include_last default) should have value 500
    dates_with_value = result[result[COL].notna() & (result[COL] != 0)]["FECHA"]
    assert pd.Timestamp("2025-01-03") in dates_with_value.values
    assert pd.Timestamp("2025-01-04") in dates_with_value.values


def test_payment_outside_range_rows_are_zero(base_range_df):
    p = make_payment(500.0, "2025-01-05", "2025-01-07")
    result = mark_fixed_payments(base_range_df, [p], COL)
    # Rows strictly before start_date should be 0 or NaN
    before = result[result["FECHA"] < pd.Timestamp("2025-01-05")][COL].fillna(0)
    assert (before == 0).all()


# ── include_last ──────────────────────────────────────────────────────────────

def test_include_last_true_includes_end_date(base_range_df):
    p = make_payment(300.0, "2025-01-03", "2025-01-05")
    result = mark_fixed_payments(base_range_df, [p], COL, include_last=True)
    end_row = result[result["FECHA"] == pd.Timestamp("2025-01-05")][COL]
    assert not end_row.empty
    assert end_row.iloc[0] == pytest.approx(300.0)


def test_include_last_false_excludes_end_date(base_range_df):
    p = make_payment(300.0, "2025-01-03", "2025-01-05")
    result = mark_fixed_payments(base_range_df, [p], COL, include_last=False)
    end_row = result[result["FECHA"] == pd.Timestamp("2025-01-05")][COL].fillna(0)
    assert not end_row.empty
    assert end_row.iloc[0] == pytest.approx(0.0)


# ── Open-ended payments ───────────────────────────────────────────────────────

def test_open_ended_payment_goes_to_end_of_df(base_range_df):
    p = make_payment(100.0, "2025-01-05", None)
    result = mark_fixed_payments(base_range_df, [p], COL)
    # From 2025-01-05 to the end (2025-01-10), all rows should have value 100
    after_start = result[result["FECHA"] >= pd.Timestamp("2025-01-05")]
    vals = after_start[COL].fillna(0)
    assert (vals == 100.0).all()


# ── Multiple payments ─────────────────────────────────────────────────────────

def test_multiple_payments_sum_on_overlapping_rows(base_range_df):
    p1 = make_payment(100.0, "2025-01-03", "2025-01-06")
    p2 = make_payment(200.0, "2025-01-03", "2025-01-06")
    result = mark_fixed_payments(base_range_df, [p1, p2], COL)
    overlap = result[result["FECHA"] == pd.Timestamp("2025-01-03")][COL].fillna(0)
    assert overlap.iloc[0] == pytest.approx(300.0)


def test_non_overlapping_payments_each_fill_their_range(base_range_df):
    p1 = make_payment(100.0, "2025-01-01", "2025-01-03")
    p2 = make_payment(200.0, "2025-01-07", "2025-01-10")
    result = mark_fixed_payments(base_range_df, [p1, p2], COL, include_last=True)
    val_p1 = result[result["FECHA"] == pd.Timestamp("2025-01-02")][COL].iloc[0]
    val_p2 = result[result["FECHA"] == pd.Timestamp("2025-01-08")][COL].iloc[0]
    assert val_p1 == pytest.approx(100.0)
    assert val_p2 == pytest.approx(200.0)
