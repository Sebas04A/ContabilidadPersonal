from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
import os
from datetime import date

# ── Logging central ── (debe ir antes de cualquier otro import del proyecto)
from contabilidad.backend.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

app = FastAPI(title="Accounting Data Labeler API", version="1.0.0")

# Allow frontend to connect (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
from contabilidad.backend.routes import transactions, sync, payments, investments, supabase_debts, dashboard, sources, variables, budget, rules, funds

app.include_router(transactions.router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(sync.router, prefix="/api/sync", tags=["Synchronization"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(investments.router, prefix="/api/investments", tags=["Investments"])
app.include_router(supabase_debts.router, prefix="/api/supabase-debts", tags=["Supabase Debts"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(sources.router, prefix="/api/sources", tags=["Sources"])
app.include_router(variables.router, prefix="/api/variables", tags=["Variables"])
app.include_router(budget.router, prefix="/api/budget", tags=["Budget"])
app.include_router(rules.router, prefix="/api/rules", tags=["Rules"])
app.include_router(funds.router, prefix="/api/funds", tags=["Funds"])
logger.info("Routers registrados: Transactions, Sync, Payments, Investments, Supabase Debts, Dashboard, Sources, Variables, Budget, Rules, Funds")

# --- Pipeline Setup ---
@app.on_event("startup")
async def startup_event():
    """Configurar pipeline al iniciar la aplicación."""
    try:
        from contabilidad.backend.storage.data_pipeline import get_pipeline
        pipeline = get_pipeline()

        # Pre-cargar caché (opcional, para que la primera request sea rápida)
        try:
            logger.info("Pre-cargando caché de datos...")
            pipeline.get_account_data()
            logger.info("Caché pre-cargado exitosamente")
        except Exception as e:
            logger.warning("No se pudo pre-cargar caché: %s — se cargará en la primera request", e)
    except Exception as e:
        logger.error("Error configurando pipeline: %s", e)

@app.on_event("shutdown")
async def shutdown_event():
    """Limpiar recursos al cerrar."""
    try:
        from contabilidad.backend.storage.data_pipeline import reset_pipeline
        reset_pipeline()
        logger.info("Pipeline limpiado")
    except Exception as e:
        logger.error("Error limpiando pipeline: %s", e)

# --- Root Endpoints ---
@app.get("/")
def root():
    return {"status": "ok", "message": "Accounting API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# --- Cache Monitoring Endpoints ---
@app.get("/api/cache/stats")
def get_cache_stats():
    """
    Obtener estadísticas del caché.

    Returns información sobre uso de memoria, entradas cacheadas, etc.
    """
    try:
        from contabilidad.backend.storage.data_pipeline import get_pipeline
        pipeline = get_pipeline()
        return pipeline.get_cache_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo stats: {str(e)}")

@app.post("/api/cache/invalidate")
def invalidate_cache(scope: str = "all"):
    """
    Invalidar caché manualmente.

    Args:
        scope: 'all', 'source', o 'transformations'
    """
    if scope not in ['all', 'source', 'transformations']:
        raise HTTPException(status_code=400, detail="scope debe ser 'all', 'source', o 'transformations'")

    try:
        from contabilidad.backend.storage.data_pipeline import get_pipeline
        pipeline = get_pipeline()
        pipeline.invalidate_cache(scope=scope)
        return {"status": "success", "message": f"Caché invalidado: {scope}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error invalidando caché: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
