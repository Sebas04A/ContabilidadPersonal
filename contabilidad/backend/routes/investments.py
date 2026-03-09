from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import os
import uuid
from datetime import datetime

# Import from storage for group/payment loading
try:
    from ..storage import InterpolationStorage
except ImportError:
    from storage import InterpolationStorage

router = APIRouter()

# Data Path: c:\Users\andre\Programacion\Cuentas\contabilidad\backend\data\investments.csv
# Assuming we are running from project root or backend root.
# Let's locate it relative to this file:
# contabilidad/backend/routes/investments.py -> ../data/investments.csv
# DATA_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'investments.csv'))

# Ensure directory exists
# os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

# class Investment(BaseModel):
#     id: Optional[str] = None
#     amount: float
#     start_date: str  # YYYY-MM-DD
#     end_date: Optional[str] = None
#     note: Optional[str] = None
#     type: str = "INVERSION" # Default type
#     active: bool = True

# def load_investments() -> pd.DataFrame:
#     if not os.path.exists(DATA_FILE):
#         return pd.DataFrame(columns=["id", "amount", "start_date", "end_date", "note", "type", "active"])
#     try:
#         df = pd.read_csv(DATA_FILE)
#         # Ensure ID column exists and is string
#         if "id" not in df.columns:
#              df["id"] = [str(uuid.uuid4()) for _ in range(len(df))]
#         df["id"] = df["id"].astype(str)
#         return df
#     except Exception:
#         return pd.DataFrame(columns=["id", "amount", "start_date", "end_date", "note", "type", "active"])

# def save_investments(df: pd.DataFrame):
#     df.to_csv(DATA_FILE, index=False)

# @router.get("/", response_model=List[Investment])
# def get_investments():
#     df = load_investments()
#     # Replace NaN with None/appropriate defaults for Pydantic
#     df = df.where(pd.notnull(df), None)
    
#     investments = []
#     for _, row in df.iterrows():
#         inv = Investment(
#             id=str(row["id"]),
#             amount=float(row["amount"]),
#             start_date=str(row["start_date"]),
#             end_date=row["end_date"] if row["end_date"] else None,
#             note=row["note"] if row["note"] else "",
#             type=row["type"] if row["type"] else "INVERSION",
#             active=bool(row["active"]) if row["active"] is not None else True
#         )
#         investments.append(inv)
#     return investments

# @router.post("/", response_model=Investment)
# def create_investment(investment: Investment):
#     df = load_investments()
    
#     new_id = str(uuid.uuid4())
#     investment.id = new_id
    
#     new_row = {
#         "id": new_id,
#         "amount": investment.amount,
#         "start_date": investment.start_date,
#         "end_date": investment.end_date,
#         "note": investment.note,
#         "type": investment.type,
#         "active": investment.active
#     }
    
#     # Check if empty
#     if df.empty:
#         df = pd.DataFrame([new_row])
#     else:
#         df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
#     save_investments(df)
#     return investment

# @router.put("/{investment_id}", response_model=Investment)
# def update_investment(investment_id: str, investment: Investment):
#     df = load_investments()
    
#     if df.empty:
#         raise HTTPException(status_code=404, detail="Investment not found")
        
#     mask = df["id"] == investment_id
#     if not mask.any():
#         raise HTTPException(status_code=404, detail="Investment not found")
    
#     # Update row
#     df.loc[mask, "amount"] = investment.amount
#     df.loc[mask, "start_date"] = investment.start_date
#     df.loc[mask, "end_date"] = investment.end_date
#     df.loc[mask, "note"] = investment.note
#     df.loc[mask, "type"] = investment.type
#     df.loc[mask, "active"] = investment.active
    
#     save_investments(df)
#     investment.id = investment_id
#     return investment

# @router.delete("/{investment_id}")
# def delete_investment(investment_id: str):
#     df = load_investments()
    
#     if df.empty:
#         raise HTTPException(status_code=404, detail="Investment not found")

#     mask = df["id"] == investment_id
#     if not mask.any():
#         raise HTTPException(status_code=404, detail="Investment not found")
        
#     df = df[~mask]
#     save_investments(df)
#     return {"status": "success", "message": "Investment deleted"}


# --- Get investments from account data (using ver_inversiones logic) ---
class AccountInvestment(BaseModel):
    fecha: str
    descripcion: str
    monto: float
    tipo: str  # "iniciada" or "finalizada"
    # For finalizadas
    plazo_fijo: Optional[float] = None
    interes: Optional[float] = None
    impuesto: Optional[float] = None
    total: Optional[float] = None

class InvestmentsFromAccountsResponse(BaseModel):
    iniciadas: List[AccountInvestment]
    finalizadas: List[AccountInvestment]

@router.get("/from-accounts", response_model=InvestmentsFromAccountsResponse)
def get_investments_from_accounts():
    """
    Get investments from account data using the ver_inversiones logic.
    This reads from the unified account file and extracts investment transactions.
    
    ⚡ Optimizado con caché
    """
    import sys
    # Add project root to path to import contabilidad modules
    current_file = os.path.abspath(__file__)
    backend_routes_dir = os.path.dirname(current_file)
    backend_dir = os.path.dirname(backend_routes_dir)
    contabilidad_dir = os.path.dirname(backend_dir)
    project_root = os.path.dirname(contabilidad_dir)
    
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    try:
        # ⚡ Usar pipeline con caché
        try:
            from ..data_pipeline import get_pipeline
        except ImportError:
            from data_pipeline import get_pipeline
        
        pipeline = get_pipeline()
        df = pipeline.get_cuenta_data()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading account data: {str(e)}")
    
    # Define investment patterns (from ObtenerVariables.py)
    ES_INVERSION_INICIADA = ["CERTIFICADO DE DEPOSITO", "A PLAZO FIJO"]
    ES_INVERSION_ACABADA = "CANCELACION PLAZO FIJO"
    
    # Filter investments
    inversion_acabada = df[df['DESCRIPCION'] == ES_INVERSION_ACABADA]
    inversion_iniciada = df[df["DESCRIPCION"].str.contains("|".join(ES_INVERSION_INICIADA), na=False)]
    
    # Build response
    iniciadas = []
    for _, row in inversion_iniciada.iterrows():
        iniciadas.append(AccountInvestment(
            fecha=row["FECHA"].strftime('%Y-%m-%d') if hasattr(row["FECHA"], 'strftime') else str(row["FECHA"]),
            descripcion=str(row["DESCRIPCION"]),
            monto=float(row["MONTO"]),
            tipo="iniciada"
        ))
    
    finalizadas = []
    for _, row in inversion_acabada.iterrows():
        fecha = row["FECHA"]
        fecha_str = fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha)
        
        # Get related transactions for this date to calculate interest and tax
        filas_inversion = df[df["FECHA"] == fecha]
        
        plazo_fijo = float(row["MONTO"])
        
        # Try to get interest
        interes_filtrado = filas_inversion[filas_inversion["DESCRIPCION"] == "TRANSFERENCIA INTERIOR"]
        if not interes_filtrado.empty:
            interes = float(interes_filtrado["CREDITO"].values[0])
        else:
            # Fallback: second MONTO value if exists
            cancelacion_rows = filas_inversion[filas_inversion["DESCRIPCION"] == ES_INVERSION_ACABADA]
            if len(cancelacion_rows) > 1:
                interes = float(cancelacion_rows["MONTO"].values[1])
            else:
                interes = 0.0
        
        # Try to get tax
        impuesto_filtrado = filas_inversion[filas_inversion["DESCRIPCION"] == "RETENCION RENDIMIENTO FINANCIERO"]
        if not impuesto_filtrado.empty:
            impuesto = float(impuesto_filtrado["DEBITO"].values[0])
        else:
            impuesto = 0.0
        
        total = plazo_fijo + interes - impuesto
        
        finalizadas.append(AccountInvestment(
            fecha=fecha_str,
            descripcion=str(row["DESCRIPCION"]),
            monto=plazo_fijo,
            tipo="finalizada",
            plazo_fijo=plazo_fijo,
            interes=interes,
            impuesto=impuesto,
            total=total
        ))
    
    # Sort by date (newest first)
    iniciadas.sort(key=lambda x: x.fecha, reverse=True)
    finalizadas.sort(key=lambda x: x.fecha, reverse=True)
    
    return InvestmentsFromAccountsResponse(
        iniciadas=iniciadas,
        finalizadas=finalizadas
    )


@router.get("/chart-data")
def get_investment_chart_data():
    """
    Get chart data for investment visualization.
    Returns df_cuenta with INVERSION column calculated from fixed payments.
    
    ⚡ Optimizado con caché - Primera llamada lenta, siguientes ~20-30x más rápidas
    """
    import sys
    # Add project root to path to import contabilidad modules
    current_file = os.path.abspath(__file__)
    backend_routes_dir = os.path.dirname(current_file)
    backend_dir = os.path.dirname(backend_routes_dir)
    contabilidad_dir = os.path.dirname(backend_dir)
    project_root = os.path.dirname(contabilidad_dir)
    
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    try:
        from contabilidad.cuenta.ObtenerVariables import marcar_fijos
        from contabilidad.Modelos import PAGO
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Could not import required modules: {str(e)}")
    
    try:
        # ⚡ Usar pipeline con caché
        try:
            # Intenta importar desde el módulo relativo
            from ..data_pipeline import get_pipeline
        except ImportError:
            # Fallback a import absoluto
            from data_pipeline import get_pipeline
        
        pipeline = get_pipeline()
        
        # Get account data con caché - Primera vez lento, siguientes rápido
        df = pipeline.get_cuenta_data()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading account data: {str(e)}")
    
    # Get all payments from ALL groups (fixed and interpolated)
    try:
        # Get all groups (pass None to type_filter to get all)
        groups = InterpolationStorage.get_groups(type_filter=None)
        
        # Create group lookup map
        group_map = {g['id']: g['name'] for g in groups}
        
        all_payments = []
        for group in groups:
            # Get payments for each group
            group_payments = InterpolationStorage.get_payments(group['id'])
            all_payments.extend(group_payments)
        
        # Convert to PAGO objects and keep details
        pagos = []
        payment_details = []
        
        for payment in all_payments:
            # payments are returned as dicts
            # Convert string dates to pd.Timestamp for compatibility with DataFrame
            start_date = pd.to_datetime(payment['start_date']) if payment['start_date'] else None
            end_date = pd.to_datetime(payment['end_date']) if payment['end_date'] else None
            
            pago_obj = PAGO(
                monto=float(payment['amount']),
                inicio=start_date,
                fin=end_date
            )
            pagos.append(pago_obj)
            
            # Store details for frontend
            payment_details.append({
                'pago': pago_obj,
                'group_name': group_map.get(payment['group_id'], 'Desconocido'),
                'note': payment.get('note', '')
            })
        pagos.sort(key=lambda p: p.inicio)  # Sort payments by start date
        
        return prepare_chart_response(df, pagos, marcar_fijos, payment_details)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing payments: {str(e)}")


def prepare_chart_response(df: pd.DataFrame, pagos: list, marcar_fijos_func, payment_details: list = None):
    """
    Prepare chart data response with INVERSION column calculated.
    """
    # Apply marcar_fijos to add INVERSION column
    if pagos:
        df_with_inversion = marcar_fijos_func(df.copy(), pagos, 'INVERSION', incluir_ultimo=False)
    else:
        df_with_inversion = df.copy()
        df_with_inversion['INVERSION'] = 0.0
    
    # Prepare time series data
    dates = []
    saldo_values = []
    inversion_values = []
    
    for _, row in df_with_inversion.iterrows():
        fecha = row['FECHA']
        fecha_str = fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha)
        dates.append(fecha_str)
        saldo_values.append(float(row['SALDO']))
        inversion_values.append(float(row.get('INVERSION', 0.0)))
    
    # Prepare individual investment periods for yellow lines
    investment_periods = []
    
    # Use payment_details if available, otherwise fallback to pagos list
    iterable = payment_details if payment_details else [{'pago': p, 'group_name': f'Inv {i+1}', 'note': ''} for i, p in enumerate(pagos)]
    
    for idx, item in enumerate(iterable):
        pago = item['pago']
        group_name = item.get('group_name', f'Inv {idx + 1}')
        note = item.get('note', '')
        
        investment_periods.append({
            'index': idx + 1,
            'amount': float(pago.monto),
            'start_date': pago.inicio if isinstance(pago.inicio, str) else pago.inicio.strftime('%Y-%m-%d'),
            'end_date': pago.fin if isinstance(pago.fin, str) else pago.fin.strftime('%Y-%m-%d') if pago.fin else dates[-1],
            'group_name': group_name,
            'note': note
        })
    return {
        'dates': dates,
        'saldo': saldo_values,
        'inversion': inversion_values,
        'investment_periods': investment_periods
    }

