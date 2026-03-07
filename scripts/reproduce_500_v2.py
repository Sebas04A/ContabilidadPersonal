from pydantic import BaseModel
from typing import Optional
from datetime import date

class InterpolatedPayment(BaseModel):
    id: str
    group_id: str
    amount: float
    start_date: date
    end_date: date
    note: Optional[str] = None
    group_name: Optional[str] = None

# Test case 1: All valid
try:
    p = InterpolatedPayment(id="1", group_id="g1", amount=100.0, start_date=date(2023,1,1), end_date=date(2023,1,2))
    print("Test 1 (Valid): Success")
except Exception as e:
    print(f"Test 1 (Valid): Failed - {e}")

# Test case 2: Amount is None
try:
    p = InterpolatedPayment(id="2", group_id="g1", amount=None, start_date=date(2023,1,1), end_date=date(2023,1,2))
    print("Test 2 (Amount=None): Success")
except Exception as e:
    print(f"Test 2 (Amount=None): Failed - {e}")

# Test case 3: Dates are None
try:
    p = InterpolatedPayment(id="3", group_id="g1", amount=100.0, start_date=None, end_date=None)
    print("Test 3 (Dates=None): Success")
except Exception as e:
    print(f"Test 3 (Dates=None): Failed - {e}")
