"""
Rules Router
============
CRUD endpoints for entity rules, tag rules, and description-map rules.
All rule storage is delegated to contabilidad.backend.storage.rules_storage.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

from contabilidad.backend.logger import get_logger
from contabilidad.backend.storage import rules_storage as rules_service

logger = get_logger(__name__)
router = APIRouter()


# ── Pydantic models ───────────────────────────────────────────────────────────

class EntityRule(BaseModel):
    categoria: Optional[str] = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    prioridad: Optional[str] = ""
    es_fijo: Optional[bool] = False
    tags: Optional[str] = ""
    nota: Optional[str] = ""

class TagRule(BaseModel):
    categoria: Optional[str] = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    prioridad: Optional[str] = ""
    es_fijo: Optional[bool] = False
    nota: Optional[str] = ""

class MapRule(BaseModel):
    original: str
    clean: str


# ── Entity rules ──────────────────────────────────────────────────────────────

@router.get("/entity/{name}")
def get_entity_rule(name: str):
    """Get entity rule for a given clean name."""
    rules = rules_service.load_rules()
    return rules.get("entity_data", {}).get(name, {})


@router.post("/entity")
def save_entity_rule(
    rule: EntityRule,
    name: str = Query(..., description="Clean name to save rule for"),
):
    """Manually save an entity rule."""
    rules = rules_service.load_rules()
    entity_data = rules.setdefault("entity_data", {})

    existing = entity_data.get(name, {})
    existing.update(rule.model_dump(exclude_unset=True))
    entity_data[name] = existing

    rules_service.save_rules(rules)
    return {"status": "saved", "name": name, "rule": existing}


# ── Tag rules ─────────────────────────────────────────────────────────────────

@router.get("/tag/{tag}")
def get_tag_rule(tag: str):
    """Get rule for a given tag."""
    rules = rules_service.load_rules()
    return rules.get("tag_data", {}).get(tag, {})


@router.post("/tag")
def save_tag_rule(
    rule: TagRule,
    tag: str = Query(..., description="Tag to save rule for"),
):
    """Manually save a tag rule."""
    rules = rules_service.load_rules()
    tag_data = rules.setdefault("tag_data", {})

    existing = tag_data.get(tag, {})
    existing.update(rule.model_dump(exclude_unset=True))
    tag_data[tag] = existing

    rules_service.save_rules(rules)
    return {"status": "saved", "tag": tag, "rule": existing}


# ── Map rules ─────────────────────────────────────────────────────────────────

@router.post("/map")
def save_map_rule(rule: MapRule):
    """Manually save a description-to-clean-name mapping rule."""
    rules_service.save_rule_map(rule.original, rule.clean)
    return {"status": "saved", "original": rule.original, "clean": rule.clean}
