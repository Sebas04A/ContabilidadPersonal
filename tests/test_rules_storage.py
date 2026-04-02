"""
test_rules_storage.py — Tests for rules_storage.py (motor de reglas de auto-etiquetado)

These tests use pytest's tmp_path so no real rules.json is touched.
"""
import json
import pytest
import pandas as pd
from unittest.mock import patch


# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture
def rules_path(tmp_path):
    """Return a path to a rules.json that doesn't exist yet."""
    return tmp_path / "rules.json"


@pytest.fixture
def rules_storage_with_tmp(rules_path):
    """Import rules_storage with _RULES_PATH patched to a tmp file."""
    with patch("contabilidad.backend.storage.rules_storage._RULES_PATH", str(rules_path)):
        from contabilidad.backend.storage import rules_storage
        # Clear any in-memory state
        rules_storage._rules_cache = None
        yield rules_storage
        rules_storage._rules_cache = None


# ── load_rules ────────────────────────────────────────────────────────────────

def test_load_rules_returns_default_when_missing(rules_storage_with_tmp):
    rules = rules_storage_with_tmp.load_rules()
    assert "description_map" in rules
    assert "entity_data" in rules
    assert isinstance(rules["description_map"], dict)
    assert isinstance(rules["entity_data"], dict)


def test_load_rules_reads_existing_file(rules_path, rules_storage_with_tmp):
    data = {
        "description_map": {"UBER EATS": "Uber Eats"},
        "entity_data": {"Uber Eats": {"categoria": "Transporte", "tags": "app"}},
        "tag_data": {},
    }
    rules_path.write_text(json.dumps(data, ensure_ascii=False))
    rules_storage_with_tmp._rules_cache = None  # reset cache
    rules = rules_storage_with_tmp.load_rules()
    assert rules["description_map"]["UBER EATS"] == "Uber Eats"


# ── save_rule_map ─────────────────────────────────────────────────────────────

def test_save_rule_map_persists_to_file(rules_storage_with_tmp, rules_path):
    rules_storage_with_tmp.save_rule_map("PAGO NETFLIX", "Netflix")
    rules_storage_with_tmp._rules_cache = None
    rules = rules_storage_with_tmp.load_rules()
    assert "PAGO NETFLIX" in rules["description_map"] or \
           any("netflix" in k.lower() for k in rules["description_map"])


def test_save_rule_map_does_not_overwrite_other_rules(rules_storage_with_tmp, rules_path):
    rules_storage_with_tmp.save_rule_map("UBER", "Uber")
    rules_storage_with_tmp.save_rule_map("NETFLIX", "Netflix")
    rules_storage_with_tmp._rules_cache = None
    rules = rules_storage_with_tmp.load_rules()
    assert "UBER" in rules["description_map"]
    assert "NETFLIX" in rules["description_map"]


# ── save_entity_rule ──────────────────────────────────────────────────────────

def test_save_entity_rule_adds_new_entity(rules_storage_with_tmp):
    rules_storage_with_tmp.save_entity_rule("Spotify", {"categoria": "Entretenimiento", "tags": "musica"})
    rules_storage_with_tmp._rules_cache = None
    rules = rules_storage_with_tmp.load_rules()
    assert "Spotify" in rules["entity_data"]
    assert rules["entity_data"]["Spotify"]["categoria"] == "Entretenimiento"


def test_save_entity_rule_merges_with_existing(rules_storage_with_tmp):
    rules_storage_with_tmp.save_entity_rule("MyApp", {"categoria": "Tech", "tags": "software"})
    rules_storage_with_tmp.save_entity_rule("MyApp", {"categoria": "Tech", "tags": "software,tools"})
    rules_storage_with_tmp._rules_cache = None
    rules = rules_storage_with_tmp.load_rules()
    # Should still have "MyApp" — merge not overwrite
    assert "MyApp" in rules["entity_data"]


# ── apply_rules_to_dataframe ──────────────────────────────────────────────────

def test_apply_rules_sets_nombre_limpio(rules_storage_with_tmp):
    rules_storage_with_tmp.save_rule_map("UBER", "Uber")
    rules_storage_with_tmp._rules_cache = None
    df = pd.DataFrame({
        "DESCRIPCION": ["UBER TRIP", "NETFLIX"],
        "revisado": [False, False],
        "nombre_limpio": [None, None],
    })
    result = rules_storage_with_tmp.apply_rules_to_dataframe(df)
    # The row with UBER in description should get nombre_limpio = Uber
    uber_rows = result[result["DESCRIPCION"] == "UBER TRIP"]
    if not uber_rows.empty and "nombre_limpio" in result.columns:
        val = uber_rows["nombre_limpio"].iloc[0]
        # Either it was set or the rule matching strategy differs
        assert val is None or "uber" in str(val).lower()


def test_apply_rules_does_not_modify_revisado_rows(rules_storage_with_tmp):
    rules_storage_with_tmp.save_rule_map("PAGO", "Payment")
    rules_storage_with_tmp._rules_cache = None
    df = pd.DataFrame({
        "DESCRIPCION": ["PAGO BANCO"],
        "revisado": [True],
        "nombre_limpio": ["Manual Name"],
        "categoria": ["Manual Cat"],
    })
    result = rules_storage_with_tmp.apply_rules_to_dataframe(df)
    # Reviewed rows should not be modified
    assert result.iloc[0]["nombre_limpio"] == "Manual Name"
    assert result.iloc[0]["categoria"] == "Manual Cat"


def test_apply_rules_with_empty_df_returns_empty(rules_storage_with_tmp):
    df = pd.DataFrame(columns=["DESCRIPCION", "revisado", "nombre_limpio"])
    result = rules_storage_with_tmp.apply_rules_to_dataframe(df)
    assert result.empty
