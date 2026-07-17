from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from contabilidad.backend.logger import get_logger
from contabilidad.backend.services import fund_service
from contabilidad.backend.services.transaction_service import (
    load_labels,
    set_fondo_for_part,
)
from contabilidad.backend.storage.variables_storage import InterpolationStorage

logger = get_logger(__name__)
router = APIRouter()


class FundCreate(BaseModel):
    name: str
    description: Optional[str] = None
    fecha_inicio: Optional[str] = None
    saldo_inicial: Optional[float] = 0.0
    tag_vinculado: Optional[str] = None


class FundUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    fecha_inicio: Optional[str] = None
    saldo_inicial: Optional[float] = None
    es_fondo: Optional[bool] = None
    tag_vinculado: Optional[str] = None


class FundPartRef(BaseModel):
    transaction_id: str
    split_group_id: Optional[str] = None


class AssignRequest(BaseModel):
    # A part may be a whole transaction (split_group_id=None) or a single split part.
    parts: List[FundPartRef]


class GeneratedPayment(BaseModel):
    start: str          # income date (YYYY-MM-DD)
    end: str            # expense date it covers (YYYY-MM-DD)
    amount: float       # covered amount (positive)
    note: Optional[str] = None


class GeneratePaymentsRequest(BaseModel):
    payments: List[GeneratedPayment]


@router.get("/")
def list_funds():
    return fund_service.get_all_funds()


@router.get("/{fund_id}")
def get_fund(fund_id: str, from_date: Optional[str] = Query(None, alias="from")):
    detail = fund_service.get_fund_detail(fund_id, view_start=from_date)
    if detail is None:
        raise HTTPException(status_code=404, detail="Fund not found")
    return detail


@router.post("/")
def create_fund(fund: FundCreate):
    group = InterpolationStorage.create_group(
        name=fund.name,
        description=fund.description,
        group_type='fixed',
        es_fondo=True,
        fecha_inicio=fund.fecha_inicio,
        saldo_inicial=fund.saldo_inicial,
        tag_vinculado=fund.tag_vinculado,
    )
    return group


@router.put("/{fund_id}")
def update_fund(fund_id: str, fund: FundUpdate):
    updates = fund.model_dump(exclude_unset=True)
    updated = InterpolationStorage.update_group(fund_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="Fund not found")
    return updated


@router.delete("/{fund_id}")
def delete_fund(fund_id: str):
    # Unassign every part pointing at this fund so no orphan fondo_id remains.
    labels = load_labels()
    if 'fondo_id' in labels.columns:
        rows = labels[labels['fondo_id'].fillna('').astype(str) == str(fund_id)]
        for _, r in rows.iterrows():
            set_fondo_for_part(str(r['source_id']), r.get('split_group_id'), "")
    ok = InterpolationStorage.delete_group(fund_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Fund not found")
    return {"status": "deleted", "id": fund_id}


@router.post("/{fund_id}/assign")
def assign_transactions(fund_id: str, req: AssignRequest):
    if InterpolationStorage.get_group(fund_id) is None:
        raise HTTPException(status_code=404, detail="Fund not found")
    count = sum(1 for p in req.parts if set_fondo_for_part(p.transaction_id, p.split_group_id, fund_id))
    return {"status": "assigned", "fund_id": fund_id, "count": count}


@router.post("/{fund_id}/unassign")
def unassign_transactions(fund_id: str, req: AssignRequest):
    count = sum(1 for p in req.parts if set_fondo_for_part(p.transaction_id, p.split_group_id, ""))
    return {"status": "unassigned", "fund_id": fund_id, "count": count}


@router.post("/{fund_id}/generate-payments")
def generate_payments(fund_id: str, req: GeneratePaymentsRequest):
    """
    Materialize the fund's flattened (income→expense) pairs as real `fixed`
    payments in a group linked to the fund (`fondo_origen`). Idempotent: any group
    previously generated from this fund is deleted and rebuilt, so the group is
    kept in sync with the current state instead of duplicating.

    These payments live in their OWN group_id (not the fund's), so they feed the
    dashboard's fixed-payment offset without being double-counted as fund movements.
    """
    fund = InterpolationStorage.get_group(fund_id)
    if fund is None:
        raise HTTPException(status_code=404, detail="Fund not found")

    # Idempotent replace: drop any group previously generated from this fund.
    for g in InterpolationStorage.get_groups_by_fondo_origen(fund_id):
        InterpolationStorage.delete_group(g['id'])

    group = InterpolationStorage.create_group(
        name=f"Pagos {fund['name']}",
        description=f"Pagos generados automáticamente del fondo «{fund['name']}»",
        group_type='fixed',
        es_fondo=False,
        fondo_origen=fund_id,
    )

    count = 0
    for p in req.payments:
        if p.amount == 0:
            continue
        InterpolationStorage.create_payment(
            group_id=group['id'],
            amount=p.amount,
            start_date=p.start,
            end_date=p.end,
            note=p.note or f"Fondo {fund['name']}",
        )
        count += 1

    return {"status": "generated", "fund_id": fund_id, "group": group, "count": count}
