"""
test_cache.py — Tests for DataCache in storage/cache.py
"""
import time
import os
import pytest
import pandas as pd
from contabilidad.backend.storage.cache import DataCache


@pytest.fixture
def cache():
    return DataCache(ttl_seconds=300)


@pytest.fixture
def small_df():
    return pd.DataFrame({"A": [1, 2, 3], "B": [4.0, 5.0, 6.0]})


# ── Basic get/set ─────────────────────────────────────────────────────────────

def test_set_and_get_returns_data(cache, small_df):
    cache.set("key1", small_df)
    result = cache.get("key1")
    assert result is not None
    pd.testing.assert_frame_equal(result, small_df)


def test_get_returns_copy_not_reference(cache, small_df):
    cache.set("key1", small_df)
    result = cache.get("key1")
    result["A"] = 99  # mutate the copy
    result2 = cache.get("key1")
    assert result2["A"].tolist() == [1, 2, 3]  # original unchanged


def test_get_missing_key_returns_none(cache):
    result = cache.get("nonexistent_key")
    assert result is None


# ── TTL ───────────────────────────────────────────────────────────────────────

def test_ttl_zero_always_expires(small_df):
    cache = DataCache(ttl_seconds=0)
    cache.set("key1", small_df)
    # TTL 0 means it should already be stale
    time.sleep(0.01)
    result = cache.get("key1")
    assert result is None


def test_ttl_not_expired_returns_data(cache, small_df):
    cache.set("key1", small_df)
    result = cache.get("key1")
    assert result is not None


# ── Invalidation ──────────────────────────────────────────────────────────────

def test_invalidate_all_clears_cache(cache, small_df):
    cache.set("k1", small_df)
    cache.set("k2", small_df)
    cache.invalidate()
    assert cache.get("k1") is None
    assert cache.get("k2") is None


def test_invalidate_single_key_leaves_others(cache, small_df):
    cache.set("k1", small_df)
    cache.set("k2", small_df)
    cache.invalidate("k1")
    assert cache.get("k1") is None
    assert cache.get("k2") is not None


def test_invalidate_nonexistent_key_does_not_raise(cache):
    cache.invalidate("does_not_exist")  # should not raise


# ── File hash detection ───────────────────────────────────────────────────────

def test_file_change_forces_reload(cache, small_df, tmp_path):
    f = tmp_path / "test.xlsx"
    f.write_text("initial")

    cache.set("key1", small_df, file_path=str(f))
    # Simulate file change by writing new content
    time.sleep(0.01)
    f.write_text("changed content")

    result = cache.get("key1", file_path=str(f))
    assert result is None  # File changed, cache invalidated


def test_file_unchanged_returns_from_cache(cache, small_df, tmp_path):
    f = tmp_path / "test.xlsx"
    f.write_text("static content")

    cache.set("key1", small_df, file_path=str(f))
    result = cache.get("key1", file_path=str(f))
    assert result is not None


def test_missing_file_path_returns_none_for_hash(cache):
    # If file doesn't exist, hash is ""
    h = cache._get_file_hash("/nonexistent/path.xlsx")
    assert h == ""


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_get_stats_correct_structure(cache, small_df):
    cache.set("k1", small_df)
    stats = cache.get_stats()
    assert "entries" in stats
    assert "keys" in stats
    assert "total_memory_mb" in stats
    assert stats["entries"] == 1
    assert "k1" in stats["keys"]


def test_stats_memory_mb_is_non_negative(cache, small_df):
    cache.set("k1", small_df)
    stats = cache.get_stats()
    assert stats["total_memory_mb"] >= 0
