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
