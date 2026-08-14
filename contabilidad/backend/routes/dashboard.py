"""
Dashboard API Module
====================
This module provides a unified dashboard service that aggregates financial data
from multiple sources (Bank, Card, Notion, Virtual Items) and exposes it via FastAPI.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from contabilidad.backend.logger import get_logger
from contabilidad.backend.storage.data_pipeline import get_pipeline
from contabilidad.backend.models.dashboard_models import ChartDataPoint, DashboardResponse, TransactionDriver, DailyVariation

# Import services
from contabilidad.backend.services.dashboard_service import DashboardService, VariationsAnalyzer, DashboardConfig
from contabilidad.backend.services.dashboard_filters import filtro_desde_query

logger = get_logger(__name__)
router = APIRouter()

# Filtro a nivel transacción, compartido por /chart-data y /variations. Los dos
# endpoints TIENEN que recibir los mismos valores: el desglose diario se contrasta
# contra el total, y si filtran distinto el descuadre cae en unexplained_difference.
# Ausentes o en 'all', el filtro queda inerte y la respuesta es la de siempre.
_DESC_CATEGORIAS = "Categorías a excluir, separadas por coma. 'Sin Categoría' para las que no tienen."
_DESC_TAGS = "Tags a excluir, separados por coma. 'Sin Etiqueta' para las que no tienen."
_DESC_ETIQUETADO = "all | labeled | unlabeled — por el campo `revisado`."
_DESC_REEMBOLSABLE = "all | included | excluded — por el campo `es_reembolsable`."
_DESC_PRIORIDAD = "all | needs | wants | rated — solo afecta a gastos; los ingresos no se clasifican."
_DESC_FONDOS = ("IDs de fondo a incluir, separados por coma. Ausente son todos; la cadena "
                "vacía es ninguno. Lo que no pertenece a un fondo siempre pasa.")


@router.get("/chart-data", response_model=DashboardResponse)
def get_dashboard_chart_data(
    incluir_inversiones: bool = Query(
        False,
        description="Sumar al patrimonio el capital propio que está dentro de una posición "
                    "de inversión. Apagado por defecto; la custodia nunca suma.",
    ),
    categorias_excluidas: Optional[str] = Query(None, description=_DESC_CATEGORIAS),
    tags_excluidos: Optional[str] = Query(None, description=_DESC_TAGS),
    etiquetado: str = Query('all', description=_DESC_ETIQUETADO),
    reembolsable: str = Query('all', description=_DESC_REEMBOLSABLE),
    prioridad: str = Query('all', description=_DESC_PRIORIDAD),
    fondos: Optional[str] = Query(None, description=_DESC_FONDOS),
):
    """
    Generate unified dashboard chart data.
    """
    try:
        service = DashboardService()
        return service.get_chart_data(
            incluir_inversiones=incluir_inversiones,
            tx_filter=filtro_desde_query(
                categorias_excluidas, tags_excluidos,
                etiquetado, reembolsable, prioridad, fondos,
            ),
        )
    except Exception as e:
        logger.error(f"Error generating dashboard data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating dashboard: {str(e)}")

@router.get("/config")
def get_dashboard_config():
    """
    Get current dashboard configuration.
    """
    config = DashboardConfig()
    return {
        "highlighted_days": config.highlighted_days,
        "features": {
            "calculate_differences": config.calculate_differences,
            "include_fixed_payments": config.include_fixed_payments,
            "include_interpolated": config.include_interpolated,
            "include_notion": config.include_notion
        },
        "data_processing": {
            "forward_fill": config.forward_fill,
            "initial_value": config.initial_value
        }
    }

@router.get("/variations", response_model=List[DailyVariation])
def get_variations_analysis(
    incluir_inversiones: bool = Query(
        False,
        description="Tiene que ir igual que en /chart-data: el desglose diario se contrasta "
                    "contra el mismo total, y si no coinciden el descuadre cae en "
                    "unexplained_difference.",
    ),
    categorias_excluidas: Optional[str] = Query(None, description=_DESC_CATEGORIAS),
    tags_excluidos: Optional[str] = Query(None, description=_DESC_TAGS),
    etiquetado: str = Query('all', description=_DESC_ETIQUETADO),
    reembolsable: str = Query('all', description=_DESC_REEMBOLSABLE),
    prioridad: str = Query('all', description=_DESC_PRIORIDAD),
    fondos: Optional[str] = Query(None, description=_DESC_FONDOS),
):
    """
    Analyze daily variations regarding ALL components.
    Uses VariationsAnalyzer for cleaner logic.
    """
    try:
        tx_filter = filtro_desde_query(
            categorias_excluidas, tags_excluidos,
            etiquetado, reembolsable, prioridad, fondos,
        )

        dash_service = DashboardService()
        dash_data_response = dash_service.get_chart_data(
            incluir_inversiones=incluir_inversiones, tx_filter=tx_filter,
        )

        # El mismo filtro que armó el total arma el desglose. No es opcional.
        analyzer = VariationsAnalyzer(tx_filter=tx_filter)
        analyzer.fetch_all_drivers()

        return analyzer.analyze(dash_data_response.data)

    except Exception as e:
        logger.error(f"Error producing detailed variation analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/invalidate")
def invalidate_dashboard_cache():
    """
    Forcefully invalidate the cache for the dashboard pipeline instance.
    """
    try:
        pipeline = get_pipeline()
        pipeline.source_cache.invalidate()
        pipeline.pipeline.clear_cache()
        logger.info("Dashboard cache invalidated via dedicated endpoint")
        return {"status": "success", "message": "Dashboard cache cleared"}
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))
