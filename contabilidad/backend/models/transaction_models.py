from pydantic import BaseModel
from typing import Optional, List

class TransactionOut(BaseModel):
    id: str                          # = source_id (hash from pipeline)
    FECHA: str
    DESCRIPCION: str
    MONTO: float
    TIPO: Optional[str] = None       # 'BANCA' or 'TARJETA'
    nombre_limpio: Optional[str] = None
    categoria: Optional[str] = None
    tags: Optional[str] = None
    prioridad: Optional[str] = None
    es_fijo: Optional[bool] = False
    pertenece_a: Optional[str] = None
    es_reembolsable: Optional[bool] = False
    deudor: Optional[str] = None
    felicidad: Optional[int] = 0
    revisado: Optional[bool] = False
    nota: Optional[str] = None
    split_group_id: Optional[str] = None
    group_id: Optional[str] = None   # NEW

class TransactionUpdate(BaseModel):
    nombre_limpio: Optional[str] = None
    categoria: Optional[str] = None
    tags: Optional[str] = None
    prioridad: Optional[str] = None
    es_fijo: Optional[bool] = None
    pertenece_a: Optional[str] = None
    es_reembolsable: Optional[bool] = None
    deudor: Optional[str] = None
    felicidad: Optional[int] = None
    revisado: Optional[bool] = None
    nota: Optional[str] = None
    group_id: Optional[str] = None   # Can be used to manually set/unset group
    monto_asignado: Optional[float] = None # For splits

class SplitItem(BaseModel):
    monto: float
    categoria: Optional[str] = None
    tags: Optional[str] = None
    nota: Optional[str] = None
    revisado: Optional[bool] = None
    nombre_limpio: Optional[str] = None
    prioridad: Optional[str] = None
    es_fijo: Optional[bool] = None
    pertenece_a: Optional[str] = None
    es_reembolsable: Optional[bool] = None
    deudor: Optional[str] = None
    felicidad: Optional[int] = None

class SplitRequest(BaseModel):
    splits: List[SplitItem]

class GroupRequest(BaseModel):
    transaction_ids: List[str]
    master_data: Optional[TransactionUpdate] = None
