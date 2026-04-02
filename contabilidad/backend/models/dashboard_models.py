from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ChartDataPoint(BaseModel):
    """Single point in the dashboard chart."""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    total: float = Field(..., description="Total net worth")
    saldo: float = Field(..., description="Bank account balance")
    saldo_sin_inversion: float = Field(..., description="Liquid balance (excluding investments)")
    tarjeta: float = Field(..., description="Credit card debt")
    pagos_fijos: float = Field(..., description="Fixed payments/investments")
    interpolado: float = Field(..., description="Interpolated/accrued values")
    notion: float = Field(..., description="External debts/assets from Notion")
    deuda_acumulada: float = Field(..., description="Net accumulated debt from Supabase")
    pago_tarjeta: Optional[float] = Field(0.0, description="Cumulative credit card payments in current cycle")
    
    # Daily differences (changes from previous day)
    diff_total: Optional[float] = 0.0
    diff_tarjeta: Optional[float] = 0.0
    diff_pago_tarjeta: Optional[float] = 0.0
    diff_saldo_sin_inversion: Optional[float] = 0.0
    diff_notion: Optional[float] = 0.0
    diff_deuda_acumulada: Optional[float] = 0.0 
    diff_pagos_fijos: Optional[float] = 0.0
    diff_interpolados: Optional[float] = 0.0 

class DashboardResponse(BaseModel):
    """Complete dashboard data response."""
    data: List[ChartDataPoint]
    highlighted_days: List[str]
    metadata: Optional[Dict[str, Any]] = None

class TransactionDriver(BaseModel):
    description: str
    amount: float
    type: str # 'income' or 'expense'
    category: Optional[str] = None
    account: Optional[str] = None
    source: str = 'BANCA' # 'BANCA', 'TARJETA', 'DEUDA', 'PAGOS_FIJO', 'INTERPOLADOS'
    date: str

class DailyVariation(BaseModel):
    date: str
    total_change: float
    
    # Components
    diff_saldo_neto: float  # Only transactional changes (income - expense)
    diff_tarjeta: float     # Change in card debt (negative if debt increases)
    diff_notion: float
    diff_deuda_acumulada: float
    diff_pagos_fijos: float
    diff_interpolados: float
    
    # Analysis
    top_drivers: List[TransactionDriver]
    income_total: float
    expense_total: float
    unexplained_difference: float # Remaining (likely investments or valuation changes)
