import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional

router = APIRouter()

# Data directory is at contabilidad/../data/backend/
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'backend'))
BUDGET_FILE = os.path.join(DATA_DIR, 'presupuesto_config.json')

class BudgetConfig(BaseModel):
    tracked_tags: list[str] = []

def load_budget() -> BudgetConfig:
    if not os.path.exists(BUDGET_FILE):
        return BudgetConfig()
    try:
        with open(BUDGET_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Migration from old format just in case
            if 'tags' in data and isinstance(data['tags'], dict):
                return BudgetConfig(tracked_tags=list(data['tags'].keys()))
            return BudgetConfig(**data)
    except Exception as e:
        print(f"Error loading budget config: {e}")
        return BudgetConfig()

def save_budget_config(config: BudgetConfig):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BUDGET_FILE, 'w', encoding='utf-8') as f:
        json.dump(config.dict(), f, indent=4)

@router.get("/")
def get_budget():
    """Get the current budget configuration"""
    return load_budget()

@router.post("/")
def save_budget(config: BudgetConfig):
    """Save the budget configuration"""
    try:
        save_budget_config(config)
        return {"status": "success", "message": "Budget configuration saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
