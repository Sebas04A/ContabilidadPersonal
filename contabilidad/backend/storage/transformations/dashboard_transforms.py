import pandas as pd
from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

from contabilidad.config import Col
from contabilidad.backend.storage.validation import requires_columns, provides_columns

@requires_columns([Col.FECHA])
@provides_columns([Col.PAGOS_FIJOS, Col.INTERPOLADO])
def transform_virtual_items(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies fixed and interpolated payments to the DataFrame using the existing VirtualItemsProcessor.
    Requires FECHA column to be present.
    """
    if df.empty:
        return df

    try:
        from contabilidad.backend.services.dashboard_service import VirtualItemsProcessor, DashboardConfig
        config = DashboardConfig()
        processor = VirtualItemsProcessor(config)
        return processor.apply(df)
    except Exception as e:
        logger.error(f"Error applying virtual items transformation: {e}", exc_info=True)
        return df

@requires_columns([Col.FECHA])
@provides_columns([Col.NOTIONCUM])
def transform_investment_capital(df: pd.DataFrame) -> pd.DataFrame:
    """Llena NOTIONCUM con el capital propio que estaba dentro de una posición cada día.

    Se calcula **siempre**, esté o no encendido el toggle de patrimonio: así el resultado
    cacheado no depende del flag de la petición, y es `_build_response` quien decide si la
    serie se suma al TOTAL o solo se informa.
    """
    if df.empty:
        return df

    # El nombre se escribe plano y no como `Col.NOTIONCUM`: `Col` es un `(str, Enum)`, así
    # que la búsqueda funcionaría igual, pero el Index se quedaría con el miembro del enum
    # y al exportar a CSV el encabezado saldría "Col.NOTIONCUM".
    try:
        from contabilidad.backend.services.investments import patrimonio

        serie = patrimonio.capital_propio_diario()
        fechas = pd.to_datetime(df[Col.FECHA.value]).dt.date
        df[Col.NOTIONCUM.value] = patrimonio.evaluar(serie, list(fechas))
        return df
    except Exception as e:
        logger.error(f"Error calculating invested capital: {e}", exc_info=True)
        if Col.NOTIONCUM.value not in df.columns:
            df[Col.NOTIONCUM.value] = 0.0
        return df

@requires_columns([Col.SALDO, Col.TARJETA, Col.PAGOS_FIJOS, Col.INTERPOLADO])
@provides_columns([Col.TOTAL, Col.DIFF_TOTAL, Col.DIFF_INTERPOLADOS, Col.DIFF_TARJETA, Col.DIFF_PAGOS_FIJOS])
def transform_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates unified metrics (TOTAL, differences) using the existing MetricProcessor.
    Requires FECHA, SALDO, TARJETA, PAGOS_FIJOS, INTERPOLADO to be present or handled gracefully.
    """
    if df.empty:
        return df

    try:
        from contabilidad.backend.services.dashboard_service import MetricProcessor, DashboardConfig
        config = DashboardConfig()
        processor = MetricProcessor(config)
        return processor.calculate_all(df)
    except Exception as e:
        logger.error(f"Error applying metrics transformation: {e}", exc_info=True)
        return df
