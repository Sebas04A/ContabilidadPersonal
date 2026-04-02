from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime
import pandas as pd

from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

class SupabaseDebt(BaseModel):
    FECHA: str
    DESCRIPCION: str
    MONTO: float
    TIPO: str
    DEUDOR_NOMBRE: str
    PAGADA: bool
    FECHA_PAGO: Optional[str] = None
    FECHA_CREACION: Optional[str] = None
    ID: str | int

@router.get("/", response_model=List[SupabaseDebt])
def get_supabase_debts(
    start_date: Optional[str] = Query(None, description="StartDate (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="EndDate (YYYY-MM-DD)"),
    pending_only: bool = Query(False, description="Show only pending debts"),
    deudor: Optional[str] = Query(None, description="Filter by debtor name")
):
    """
    Get debts from Supabase using deudas.lectura logic.
    """
    try:
        from contabilidad.debts.reading import obtener_deudas_para_analisis
        
        # Convert string dates to datetime if provided
        start_dt = pd.to_datetime(start_date) if start_date else None
        end_dt = pd.to_datetime(end_date) if end_date else None
        
        df = obtener_deudas_para_analisis(
            fecha_inicio=start_dt,
            fecha_fin=end_dt,
            solo_pendientes=pending_only
        )
        
        # Filter by debtor if provided
        if deudor:
             # Case insensitive match
             df = df[df['DEUDOR_NOMBRE'].astype(str).str.lower() == deudor.lower()]
        
        # Sanitize for JSON response
        df = df.copy()
        
        # Handle dates
        date_cols = ['FECHA', 'FECHA_PAGO', 'FECHA_CREACION']
        for col in date_cols:
             if col in df.columns:
                 df[col] = df[col].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(x) else None)

        # Handle NaNs in other columns
        df['DESCRIPCION'] = df['DESCRIPCION'].fillna('')
        df['MONTO'] = df['MONTO'].fillna(0.0)
        df['DEUDOR_NOMBRE'] = df['DEUDOR_NOMBRE'].fillna('Desconocido')
        df['PAGADA'] = df['PAGADA'].fillna(False)
        
        return df.to_dict(orient='records')
        
    except ImportError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Could not import deudas.lectura. Error: {e}"
        )
    except Exception as e:
        logger.error("Error al obtener deudas: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

class SupabasePayment(BaseModel):
    id: str | int
    fecha_pago: str
    monto_total: float
    deudor_id: str
    deudor_nombre: str

@router.get("/payments", response_model=List[SupabasePayment])
def get_supabase_payments(
    deudor: Optional[str] = Query(None, description="Filter by debtor name")
):
    """
    Get all payments from Supabase using deudas.lectura logic.
    """
    try:
        from deudas.lectura import obtener_todos_pagos
        
        df = obtener_todos_pagos()
        
        # Filter by debtor if provided
        if deudor:
             # Case insensitive match
             df = df[df['deudor_nombre'].astype(str).str.lower() == deudor.lower()]
        
        # Sanitize for JSON response
        df = df.copy()
        
        # Handle dates
        if 'fecha_pago' in df.columns:
             df['fecha_pago'] = df['fecha_pago'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(x) else None)

        # Handle NaNs in other columns
        df['monto_total'] = df['monto_total'].fillna(0.0)
        df['deudor_nombre'] = df['deudor_nombre'].fillna('Desconocido')
        
        return df.to_dict(orient='records')
        
    except ImportError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Could not import deudas.lectura. Error: {e}"
        )
    except Exception as e:
        logger.error("Error al obtener pagos: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
