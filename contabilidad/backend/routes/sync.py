from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date

from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

from contabilidad.backend.models.sync_models import SyncRequest, SyncResponse

@router.post("/", response_model=SyncResponse)
def sync_data(request: SyncRequest):
    """
    Trigger data synchronization from source files (Cuenta + Tarjeta).
    
    - fecha_inicio: Start date for new data
    - overwrite: If True, replaces all data from fecha_inicio onwards
    
    ⚡ Invalida caché después de sincronizar
    """
    try:
        # Import your existing sync logic
        import sincronizacion
        
        added, msg = sincronizacion.sincronizar_db(request.fecha_inicio, overwrite=request.overwrite)
        
        # ⚡ Invalidar TODO el caché (los datos fuente cambiaron)
        try:
            from contabilidad.backend.storage.data_pipeline import get_pipeline
            
            pipeline = get_pipeline()
            pipeline.invalidate_cache(scope='all')
            logger.info("Caché invalidado después de sincronización")
        except Exception as cache_error:
            logger.warning("No se pudo invalidar caché: %s", cache_error)
            # No fallar la sincronización por esto
        
        return SyncResponse(
            status="success",
            records_added=added,
            message=msg if msg else None
        )
    except ImportError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Could not import sincronizacion module. Make sure it exists in the etiquetado folder. Error: {e}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
def sync_status():
    """Check if sync module is available and data sources are accessible."""
    status = {
        "sync_module": False,
        "cuenta_source": False,
        "tarjeta_source": False,
        "errors": []
    }
    
    try:
        import sincronizacion
        status["sync_module"] = True
    except ImportError as e:
        status["errors"].append(f"sincronizacion module: {e}")
    
    try:
        from contabilidad.backend.services.bank_parser.account import read_saved_account_data
        # Try to load data
        df = read_saved_account_data()
        status["cuenta_source"] = True
        status["cuenta_records"] = len(df)
    except Exception as e:
        status["errors"].append(f"cuenta source: {e}")
    
    try:
        from contabilidad.backend.services.credit_card.Lectura import leer_tarjetas
        from contabilidad.config import PATH_TARJETA_PROCESADA
        _, df = leer_tarjetas(PATH_TARJETA_PROCESADA)
        status["tarjeta_source"] = True
        status["tarjeta_records"] = len(df)
    except Exception as e:
        status["errors"].append(f"tarjeta source: {e}")
    
    return status
