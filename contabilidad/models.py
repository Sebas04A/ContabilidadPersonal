from dataclasses import dataclass, asdict, is_dataclass
from typing import Optional, List
import pandas as pd
from datetime import datetime 
from pathlib import Path
import json

@dataclass
class Payment:
    amount: int
    start_date: Optional[str] = None 
    end_date: Optional[str] = None
    description: Optional[str] = None

@dataclass
class SavedAccountChangesData:
    start_date: datetime
    end_date: datetime
    start_balance: float
    end_balance: float
    new_data_path: str
    changes: str

@dataclass
class SavedChangesData:
    date: datetime
    previous_folder_path: Path
    changes: str
    account_changes: SavedAccountChangesData

class EnhancedJSONEncoder(json.JSONEncoder):
    """
    An enhanced JSON encoder that knows how to handle:
    - dataclass objects
    - datetime objects (converting them to ISO format string)
    - Path objects (converting them to string)
    """
    def default(self, o):
        if is_dataclass(o):
            return asdict(o)
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, Path):
            return str(o)
        return super().default(o)
    
@dataclass
class ConfigData:
    current_path: Path