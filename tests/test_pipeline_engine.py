"""
test_pipeline_engine.py — Tests for TransformationPipeline in storage/pipeline_engine.py
"""
import pytest
import pandas as pd
from contabilidad.backend.storage.pipeline_engine import TransformationPipeline


@pytest.fixture
def base_df():
    return pd.DataFrame({"A": [1, 2, 3], "B": [10.0, 20.0, 30.0]})


def add_col_x(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["X"] = df["A"] * 2
    return df


def add_col_y(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Y"] = df["B"] + 100
    return df


# ── Registration ──────────────────────────────────────────────────────────────

def test_add_transformation_stores_in_order():
    pipeline = TransformationPipeline("test")
    pipeline.add_transformation("t1", add_col_x)
    pipeline.add_transformation("t2", add_col_y)
    names = [t["name"] for t in pipeline.transformations]
    assert names == ["t1", "t2"]


def test_add_transformation_sets_cacheable_flag():
    pipeline = TransformationPipeline("test")
    pipeline.add_transformation("t1", add_col_x, cacheable=False)
    assert pipeline.transformations[0]["cacheable"] is False


# ── Execution ─────────────────────────────────────────────────────────────────

def test_execute_applies_all_transformations(base_df):
    pipeline = TransformationPipeline("test")
    pipeline.add_transformation("t1", add_col_x)
    pipeline.add_transformation("t2", add_col_y)

    result = pipeline.execute(base_df)
    assert "X" in result.columns
    assert "Y" in result.columns
    assert result["X"].tolist() == [2, 4, 6]
    assert result["Y"].tolist() == [110.0, 120.0, 130.0]


def test_execute_with_no_transformations_returns_copy(base_df):
    pipeline = TransformationPipeline("test")
    result = pipeline.execute(base_df)
    pd.testing.assert_frame_equal(result, base_df)


# ── Caching ───────────────────────────────────────────────────────────────────

def test_cache_hit_skips_function_call(base_df):
    pipeline = TransformationPipeline("test")
    call_count = {"n": 0}

    def counting_transform(df):
        call_count["n"] += 1
        df = df.copy()
        df["Z"] = 99
        return df

    pipeline.add_transformation("t", counting_transform, cacheable=True)

    pipeline.execute(base_df)       # first call — executes
    pipeline.execute(base_df)       # second call — should hit cache
    assert call_count["n"] == 1     # function called only once


def test_skip_cache_always_re_executes(base_df):
    pipeline = TransformationPipeline("test")
    call_count = {"n": 0}

    def counting_transform(df):
        call_count["n"] += 1
        return df.copy()

    pipeline.add_transformation("t", counting_transform, cacheable=True)

    pipeline.execute(base_df, skip_cache=False)
    pipeline.execute(base_df, skip_cache=True)
    pipeline.execute(base_df, skip_cache=True)
    assert call_count["n"] == 3  # called every time with skip_cache=True


# ── Cache control ─────────────────────────────────────────────────────────────

def test_clear_cache_empties_pipeline_cache(base_df):
    pipeline = TransformationPipeline("test")
    pipeline.add_transformation("t", add_col_x, cacheable=True)
    pipeline.execute(base_df)  # populate cache
    pipeline.clear_cache()
    assert pipeline.cache.get_stats()["entries"] == 0


def test_invalidate_from_removes_named_entry(base_df):
    pipeline = TransformationPipeline("test")
    call_count = {"n": 0}

    def cached_transform(df):
        call_count["n"] += 1
        return df.copy()

    pipeline.add_transformation("t1", cached_transform, cacheable=True)
    pipeline.execute(base_df)     # populate cache with t1
    assert call_count["n"] == 1

    pipeline.invalidate_from("t1")
    pipeline.execute(base_df)     # t1 should re-run
    assert call_count["n"] == 2
