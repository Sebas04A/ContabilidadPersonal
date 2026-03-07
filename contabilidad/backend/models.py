from pydantic import BaseModel
from typing import Optional, List
from datetime import date
import uuid

class InterpolationGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    type: str = 'interpolated'

class InterpolationGroup(InterpolationGroupCreate):
    id: str

class InterpolatedPaymentCreate(BaseModel):
    amount: float
    start_date: date
    end_date: date
    note: Optional[str] = None

class InterpolatedPayment(InterpolatedPaymentCreate):
    id: str
    group_id: str
    group_name: Optional[str] = None
