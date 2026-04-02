import pandera as pa
from pandera.typing import Series
from contabilidad.config import Col

class BancaSchema(pa.DataFrameModel):
    """Schema for Bank Account Data (Banca)."""
    FECHA: Series[pa.DateTime] = pa.Field(alias=Col.FECHA)
    SALDO: Series[float] = pa.Field(alias=Col.SALDO)
    
    class Config:
        coerce = True
        strict = False  # allow other columns like MONTO, DEBITO

class TarjetaSchema(pa.DataFrameModel):
    """Schema for Credit Card Data (Tarjeta) before aggregations."""
    FECHA: Series[pa.DateTime] = pa.Field(alias=Col.FECHA)
    MONTO: Series[float] = pa.Field(alias=Col.MONTO)
    
    class Config:
        coerce = True
        strict = False

class DeudaSchema(pa.DataFrameModel):
    """Schema for Supabase Debts Data."""
    FECHA: Series[pa.DateTime] = pa.Field(alias=Col.FECHA)
    DEUDA_ACUMULADA: Series[float] = pa.Field(alias=Col.DEUDA_ACUMULADA)
    
    class Config:
        coerce = True
        strict = False

class DailyUnifiedSchema(pa.DataFrameModel):
    """
    Schema for the final Unified Daily Data, before dashboard transformations.
    """
    FECHA: Series[pa.DateTime] = pa.Field(alias=Col.FECHA)
    SALDO: Series[float] = pa.Field(alias=Col.SALDO)
    TARJETA: Series[float] = pa.Field(alias=Col.TARJETA)
    DEUDA_ACUMULADA: Series[float] = pa.Field(alias=Col.DEUDA_ACUMULADA, nullable=True)
    
    class Config:
        coerce = True
        strict = False
