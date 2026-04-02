from pydantic import BaseModel
from typing import List, Optional

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
