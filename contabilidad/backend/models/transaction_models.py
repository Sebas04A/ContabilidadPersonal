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
    fondo_id: Optional[str] = None   # Fund this transaction belongs to
    deuda_id: Optional[str] = None   # Linked Supabase debt id

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
    fondo_id: Optional[str] = None   # Assign/unassign a fund (empty string to clear)
    deuda_id: Optional[str] = None   # Link/unlink a Supabase debt (empty string to clear)

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

class BulkUpdateRequest(BaseModel):
    transaction_ids: List[str]
    updates: TransactionUpdate
    overwrite: bool = False          # False = solo rellenar campos vacíos
    tags_mode: str = 'append'        # 'append' suma tags, 'replace' los sustituye
    propagate_groups: bool = True    # Incluir transacciones del mismo group_id
    save_as_rule: bool = False       # Guardar también en rules.json
    rule_entities: Optional[List[str]] = None   # nombres limpios -> entity_data
    rule_tags: Optional[List[str]] = None       # tags -> tag_data
