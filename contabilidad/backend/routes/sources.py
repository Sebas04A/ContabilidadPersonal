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

@router.get("/summary")
async def get_sources_summary():
    """
    Retorna un resumen de cada archivo fuente individual presente en data/nuevos/banca y data/nuevos/tarjeta,
    incluyendo rango de fechas, total de filas y datos para gráfico de barras por fuente.
    """
    try:
        service = SourcesService()
        return service.get_sources_summary()
    except Exception as e:
        logger.exception("Error obteniendo resumen de fuentes")
        raise HTTPException(status_code=500, detail=str(e))

