from dataclasses import dataclass
from typing import Optional, List
@dataclass
class PAGO:
    monto:int
    inicio:Optional[str] = None 
    fin:Optional[str] = None
    descripcion:Optional[str] = None