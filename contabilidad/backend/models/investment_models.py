from pydantic import BaseModel
from typing import Dict, List, Optional

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
    # Emparejamiento apertura↔cierre (opcionales: el frontend viejo los ignora)
    fecha_apertura: Optional[str] = None
    fecha_cierre: Optional[str] = None
    dias: Optional[int] = None
    tna: Optional[float] = None
    estado: Optional[str] = None  # "abierta" | "cerrada"
    ambiguo: Optional[bool] = None

class OrphanClosingOut(BaseModel):
    """Cancelación cuya apertura ocurrió antes de que empiece el historial bancario."""
    fecha: str
    capital_sugerido: float
    interes_sugerido: float
    retencion: float
    tx_ids: List[str] = []

class InvestmentsFromAccountsResponse(BaseModel):
    iniciadas: List[AccountInvestment]
    finalizadas: List[AccountInvestment]
    huerfanas: List[OrphanClosingOut] = []


# ── Posiciones guardadas ──────────────────────────────────────────────────────

class MovementIn(BaseModel):
    """Un flujo de dinero de la posición. El monto es siempre positivo: el signo lo da `tipo`."""
    fecha: str
    tipo: str  # aporte | retiro | interes | retencion | comision | dividendo
    monto: float
    tx_id: Optional[str] = None   # vacío si el dinero no pasó por la cuenta bancaria
    nota: Optional[str] = None


class FlowIn(BaseModel):
    """Dinero que entra o sale del portafolio sin pasar por una inversión.

    El monto es siempre positivo: el signo lo da `direccion`. Si se aceptaran negativos
    habría dos formas de escribir lo mismo y una terminaría al revés.
    """
    portafolio_id: str
    fecha: str
    monto: float
    direccion: str = "salida"     # salida (matrícula, retiro) | entrada (plata de fuera)
    nota: Optional[str] = None
    tx_id: Optional[str] = None   # la transacción bancaria, si el dinero pasó por la cuenta


class PositionIn(BaseModel):
    portafolio_id: Optional[str] = None
    tipo: str = "plazo_fijo"      # plazo_fijo | valuada | ajuste | flujo
    fecha_apertura: Optional[str] = None
    fecha_cierre: Optional[str] = None
    estado: Optional[str] = None  # se deriva de fecha_cierre si no viene
    origen: str = "manual"        # detectado | manual
    plazo_pactado_dias: Optional[int] = None
    tasa_pactada: Optional[float] = None
    institucion: Optional[str] = None
    moneda: str = "USD"
    nota: Optional[str] = None
    tx_apertura_id: Optional[str] = None
    tx_cierre_id: Optional[str] = None
    movimientos: List[MovementIn] = []


class PositionUpdate(BaseModel):
    """Todo opcional: solo se escribe lo que venga (`exclude_unset`).

    `movimientos` ausente deja los actuales intactos; presente los reemplaza por completo.
    """
    portafolio_id: Optional[str] = None
    tipo: Optional[str] = None
    fecha_apertura: Optional[str] = None
    fecha_cierre: Optional[str] = None
    estado: Optional[str] = None
    origen: Optional[str] = None
    plazo_pactado_dias: Optional[int] = None
    tasa_pactada: Optional[float] = None
    institucion: Optional[str] = None
    moneda: Optional[str] = None
    nota: Optional[str] = None
    tx_apertura_id: Optional[str] = None
    tx_cierre_id: Optional[str] = None
    movimientos: Optional[List[MovementIn]] = None


class ApplyDetectionRequest(BaseModel):
    """Qué parte del diff del detector confirmar.

    `tx_apertura_ids` en None confirma todo lo pendiente; con lista, solo esas.
    """
    tx_apertura_ids: Optional[List[str]] = None
    asignaciones: Dict[str, str] = {}   # tx_apertura_id -> portafolio_id
    portafolio_id: Optional[str] = None  # portafolio por defecto
    incluir_cambiadas: bool = True
    #: Toma el portafolio que sugieren las cadenas de pagos cuando no hay asignación
    #: explícita, y solo si la sugerencia es inequívoca.
    usar_sugerencias: bool = False


class SplitPart(BaseModel):
    portafolio_id: Optional[str] = None
    capital: float
    interes: Optional[float] = None    # None = prorratear por capital
    retencion: Optional[float] = None
    nota: Optional[str] = None


class SplitRequest(BaseModel):
    partes: List[SplitPart]
