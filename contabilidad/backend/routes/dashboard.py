"""
Dashboard API Module
====================
This module provides a unified dashboard service that aggregates financial data
from multiple sources (Bank, Card, Notion, Virtual Items) and exposes it via FastAPI.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from contabilidad.backend.logger import get_logger
from contabilidad.backend.storage.data_pipeline import get_pipeline
from contabilidad.backend.models.dashboard_models import ChartDataPoint, DashboardResponse, TransactionDriver, DailyVariation

# Import services
from contabilidad.backend.services.dashboard_service import DashboardService, VariationsAnalyzer, DashboardConfig

logger = get_logger(__name__)
router = APIRouter()

@router.get("/chart-data", response_model=DashboardResponse)
def get_dashboard_chart_data():
    """
    Generate unified dashboard chart data.
    """
    try:
        service = DashboardService()
        return service.get_chart_data()
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
def get_variations_analysis():
    """
    Analyze daily variations regarding ALL components.
    Uses VariationsAnalyzer for cleaner logic.
    """
    try:
        dash_service = DashboardService()
        dash_data_response = dash_service.get_chart_data()
        
        analyzer = VariationsAnalyzer()
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
