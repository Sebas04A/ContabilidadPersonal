from pydantic import BaseModel

class BudgetConfig(BaseModel):
    tracked_tags: list[str] = []
