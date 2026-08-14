from pydantic import BaseModel
from typing import Optional, List
from datetime import date
import uuid

class InterpolationGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    type: str = 'interpolated'

class InterpolationGroup(InterpolationGroupCreate):
    id: str
    #: Derivado, no una columna: quién manda sobre el grupo — `manual` lo escribió el
    #: usuario, `fondo` y `inversion` los gestiona su módulo, `generado` lo produjo una
    #: máquina desde otro grupo. `type` solo dice cómo se ejecuta, no qué es.
    origen: str = 'manual'
    #: De qué grupo salió, cuando `origen == 'generado'`. La UI lo necesita para pintarlo
    #: de la familia de su padre en vez de dejarlo en un gris que no dice de quién es.
    fondo_origen: Optional[str] = None

class InterpolatedPaymentCreate(BaseModel):
    amount: float
    #: Las dos puntas son opcionales en un grupo `fixed`: sin inicio el pago vale desde
    #: siempre y sin fin vale para siempre. Un grupo `interpolated` sí necesita las dos
    #: —son el tramo que reparte— y eso se valida en la ruta, donde se sabe el tipo.
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    note: Optional[str] = None

class InterpolatedPayment(InterpolatedPaymentCreate):
    id: str
    group_id: str
    group_name: Optional[str] = None
