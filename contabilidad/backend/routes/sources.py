from fastapi import APIRouter, HTTPException
from contabilidad.backend.logger import get_logger
from contabilidad.backend.services.sources_service import SourcesService

logger = get_logger(__name__)
router = APIRouter()

@router.post("/bank/process")
async def process_bank_sources():
    """
    Lee todos los archivos Excel en data/nuevos/banca, los procesa y los une en un solo archivo.
    Guarda el resultado en data/sistema/procesada/banca.
    """
    try:
        service = SourcesService()
        return service.process_bank_data()
    except Exception as e:
        logger.error(f"Error procesando bancos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/card/process")
async def process_card_sources():
    """
    Lee todos los archivos .xls en data/nuevos/tarjeta, los procesa y los une en un solo archivo.
    Guarda el resultado en data/procesada/tarjeta/tarjeta_unida.xlsx.
    """
    try:
        service = SourcesService()
        return service.process_card_data()
    except Exception as e:
        logger.exception("Error procesando tarjetas")
        raise HTTPException(status_code=500, detail=str(e))
