from dataclasses import dataclass,asdict,fields
from datetime import datetime

@dataclass
class DATOS_TARJETA_METADATA:
    EMPRESA: str
    NUM_TARJETA: str
    FECHA_MAX_PAGO: datetime
    FECHA_EMISION: datetime

@dataclass
class DATOS_TARJETA_HEADER:
    # TOTAL_ANTES_CONSUMOS: float
    DEUDAS_MES_ANTERIOR: float
    SUBTOTAL_PAGADO: float
    SALDO_ANTERIOR: float

@dataclass
class DATOS_TARJETA_TOTALES:
    TOTAL_A_PAGAR: float
    TOTAL_CONSUMO: float
    MINIMO_A_PAGAR: float

@dataclass
class DATOS_TARJETA_INFO_MOVIMIENTOS:
    MIN_FECHA_MOVIMIENTO: datetime
    MAX_FECHA_MOVIMIENTO: datetime
    def __post_init__(self):
        # print(f"Validando fechas: MIN_FECHA_MOVIMIENTO={self.MIN_FECHA_MOVIMIENTO}, MAX_FECHA_MOVIMIENTO={self.MAX_FECHA_MOVIMIENTO}")
        if self.MIN_FECHA_MOVIMIENTO > self.MAX_FECHA_MOVIMIENTO:
            raise ValueError("MIN_FECHA_MOVIMIENTO no puede ser mayor que MAX_FECHA_MOVIMIENTO")
        if not isinstance(self.MIN_FECHA_MOVIMIENTO, datetime):
            raise TypeError("MIN_FECHA_MOVIMIENTO debe ser un objeto datetime")
        if not isinstance(self.MAX_FECHA_MOVIMIENTO, datetime):
            raise TypeError("MAX_FECHA_MOVIMIENTO debe ser un objeto datetime")




@dataclass
class DATOS_TARJETA_COMPLETA(
    DATOS_TARJETA_METADATA,
    DATOS_TARJETA_HEADER,
    DATOS_TARJETA_TOTALES,
    DATOS_TARJETA_INFO_MOVIMIENTOS
):
    @classmethod
    def desde_partes(cls, *, metadata: DATOS_TARJETA_METADATA, header: DATOS_TARJETA_HEADER, totales: DATOS_TARJETA_TOTALES, movimientos: DATOS_TARJETA_INFO_MOVIMIENTOS) -> 'DATOS_TARJETA_COMPLETA':
        """
        Constructor alternativo que crea una instancia principal
        a partir de los objetos componentes.
        """
        # 1. Convertimos cada objeto componente a un diccionario
        dict_metadata = asdict(metadata)
        dict_header = asdict(header)
        dict_totales = asdict(totales)
        dict_movimientos = asdict(movimientos)

        # 2. Unimos todos los diccionarios en uno solo
        datos_combinados = {**dict_metadata, **dict_header, **dict_totales, **dict_movimientos}

        # 3. Creamos la instancia de la clase principal usando los datos combinados
        return cls(**datos_combinados)
    @classmethod
    def get_column_order(cls) -> list[str]:
        """
        Devuelve una lista con los nombres de los campos
        en el orden de definición de la clase.
        """
        return [field.name for field in reversed(fields(cls))]


MAPEO_COLUMNAS = {
    "EMPRESA": "EMPRESA",
    "NUM_TARJETA": "NUM_TARJETA",
    "FECHA_MAX_PAGO": "FECHA_MAX_PAGO",
    "FECHA_EMISION": "FECHA_EMISION",
    # "TOTAL_ANTES_CONSUMOS": "TOTAL_ANTES_CONSUMOS",
    "DEUDAS_MES_ANTERIOR": "DEUDAS_MES_ANTERIOR",
    "SUBTOTAL_PAGADO": "SUBTOTAL_PAGADO",
    "SALDO_ANTERIOR": "SALDO_ANTERIOR",
    "TOTAL_A_PAGAR": "TOTAL_A_PAGAR",
    "TOTAL_CONSUMO": "TOTAL_CONSUMO",
    "MINIMO_A_PAGAR": "MINIMO_A_PAGAR",
    "MIN_FECHA_MOVIMIENTO": "MIN_FECHA_MOVIMIENTO",
    "MAX_FECHA_MOVIMIENTO": "MAX_FECHA_MOVIMIENTO",
}