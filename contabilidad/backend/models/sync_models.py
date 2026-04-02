from pydantic import BaseModel
from datetime import date

class SyncRequest(BaseModel):
    fecha_inicio: date
    overwrite: bool = False

class SyncResponse(BaseModel):
    status: str
    records_added: int
    message: str | None = None
