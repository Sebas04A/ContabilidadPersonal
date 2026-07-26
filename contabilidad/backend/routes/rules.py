"""
Rules Router
============
CRUD endpoints for entity rules, tag rules, and description-map rules.
All rule storage is delegated to contabilidad.backend.storage.rules_storage.
"""

from fastapi import APIRouter, HTTPException, Query
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

class RenameRequest(BaseModel):
    old_name: str
    new_name: str


# ── Overview ──────────────────────────────────────────────────────────────────

@router.get("/")
def get_all_rules():
    """Return the whole rulebook: description_map, entity_data and tag_data."""
    rules = rules_service.load_rules()
    return {
        "description_map": rules.get("description_map", {}),
        "entity_data": rules.get("entity_data", {}),
        "tag_data": rules.get("tag_data", {}),
        "counts": {
            "description_map": len(rules.get("description_map", {})),
            "entity_data": len(rules.get("entity_data", {})),
            "tag_data": len(rules.get("tag_data", {})),
        },
    }


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


@router.delete("/entity/{name}")
def delete_entity_rule(name: str):
    """Delete an entity rule."""
    if not rules_service.delete_entity_rule(name):
        raise HTTPException(status_code=404, detail=f"Regla no encontrada: {name}")
    return {"status": "deleted", "name": name}


@router.post("/entity/rename")
def rename_entity_rule(req: RenameRequest):
    """Rename an entity, repointing every description mapping that used it."""
    if not rules_service.rename_entity_rule(req.old_name, req.new_name):
        raise HTTPException(status_code=400, detail="No se pudo renombrar la entidad")
    return {"status": "renamed", "old_name": req.old_name, "new_name": req.new_name}


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


@router.delete("/tag/{tag}")
def delete_tag_rule(tag: str):
    """Delete a tag rule."""
    if not rules_service.delete_tag_rule(tag):
        raise HTTPException(status_code=404, detail=f"Regla no encontrada: {tag}")
    return {"status": "deleted", "tag": tag}


# ── Map rules ─────────────────────────────────────────────────────────────────

@router.post("/map")
def save_map_rule(rule: MapRule):
    """Manually save a description-to-clean-name mapping rule."""
    rules_service.save_rule_map(rule.original, rule.clean)
    return {"status": "saved", "original": rule.original, "clean": rule.clean}


@router.delete("/map")
def delete_map_rule(original: str = Query(..., description="Original description key to remove")):
    """Delete a description-to-clean-name mapping rule."""
    if not rules_service.delete_rule_map(original):
        raise HTTPException(status_code=404, detail=f"Mapeo no encontrado: {original}")
    return {"status": "deleted", "original": original}
