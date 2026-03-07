import pandas as pd
import requests
import os
import uuid
from datetime import date

# simulate storage.py behavior
def clean_data(data):
    # simulate Pydantic processing
    try:
        # If amount is NaN, float() might fail or Pydantic might fail if it expects strict float and gets NaN
        print(f"Data: {data}")
    except Exception as e:
        print(f"Error: {e}")

# Create a dummy CSV with problematic data
os.makedirs("data/backend/interpolaciones", exist_ok=True)
df = pd.DataFrame([{
    "id": "1",
    "group_id": "g1",
    "amount": None, # NaN
    "start_date": "2023-01-01",
    "end_date": None,
    "note": None
}])
df.to_csv("data/backend/interpolaciones/pagos_test.csv", index=False)

# Read it back and convert to dict
df_read = pd.read_csv("data/backend/interpolaciones/pagos_test.csv")
records = df_read.to_dict('records')
print("Records from CSV:", records)

# Validate against Pydantic model (simulated)
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

try:
    for r in records:
        # Pandar returns float('nan') for None in numeric columns
        # Pydantic might fail on 'nan' for date or float
        print(f"Validating: {r}")
        InterpolatedPayment(**r)
except Exception as e:
    print(f"Validation Error: {e}")
