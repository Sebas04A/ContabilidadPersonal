from fastapi import APIRouter, HTTPException
from contabilidad.backend.models.investment_models import InvestmentsFromAccountsResponse
from contabilidad.backend.services.investment_service import InvestmentService
from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.get("/from-accounts", response_model=InvestmentsFromAccountsResponse)
def get_investments_from_accounts():
    """
    Get investments from account data using the ver_inversiones logic.
    """
    try:
        service = InvestmentService()
        return service.get_investments_from_accounts()
    except Exception as e:
        logger.error(f"Error getting investments from accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chart-data")
def get_investment_chart_data():
    """
    Get chart data for investment visualization.
    """
    try:
        service = InvestmentService()
        return service.get_investment_chart_data()
    except Exception as e:
        logger.error(f"Error processing investment chart data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
