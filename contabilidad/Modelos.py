from dataclasses import dataclass,asdict, is_dataclass
from typing import Optional, List
import pandas as pd
from datetime import datetime 
from pathlib import Path
import json



@dataclass
class PAGO:
    monto:int
    inicio:Optional[str] = None 
    fin:Optional[str] = None
    descripcion:Optional[str] = None



@dataclass
class DataCambiosGuardadoCuenta:
    fecha_inicio:datetime
    fecha_fin:datetime
    saldo_inicio:float
    saldo_fin:float
    path_nuevos_datos:str
    cambios:str

@dataclass
class DataCambiosGuardado():
    fecha:datetime
    path_carpeta_anterior:Path
    cambios:str
    cambiosCuenta:DataCambiosGuardadoCuenta
    

class EnhancedJSONEncoder(json.JSONEncoder):
    """
    Un codificador JSON mejorado que sabe como manejar:
    - Objetos dataclass
    - Objetos datetime (los convierte a string en formato ISO)
    - Objetos Path (los convierte a string)
    """
    def default(self, o):
        # Si el objeto es un dataclass, lo convierte a diccionario
        if is_dataclass(o):
            return asdict(o)
        # Si es un objeto de fecha y hora, lo formatea como string
        if isinstance(o, datetime):
            return o.isoformat()
        # Si es un objeto Path, lo convierte a su representación en string
        if isinstance(o, Path):
            return str(o)
        # Para cualquier otro tipo, usa el comportamiento por defecto
        return super().default(o)
    

@dataclass
class ConfigData:
    path_actual:Path