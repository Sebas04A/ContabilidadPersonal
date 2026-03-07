from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
import os
import sys
from datetime import date

# Add parent directory to path to import existing modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))

if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

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
try:
    from .routes import transactions, sync, interpolated, investments, supabase_debts, dashboard, sources, variables, budget
except ImportError:
    from routes import transactions, sync, interpolated, investments, supabase_debts, dashboard, sources, variables, budget

app.include_router(transactions.router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(sync.router, prefix="/api/sync", tags=["Synchronization"])
app.include_router(interpolated.router, prefix="/api", tags=["Interpolated Payments"])
app.include_router(investments.router, prefix="/api/investments", tags=["Investments"])
app.include_router(supabase_debts.router, prefix="/api/supabase-debts", tags=["Supabase Debts"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(sources.router, prefix="/api/sources", tags=["Sources"])
app.include_router(variables.router, prefix="/api/variables", tags=["Variables"])
app.include_router(budget.router, prefix="/api/budget", tags=["Budget"])
print("Routers included: Transactions, Sync, Interpolated, Investments, Supabase Debts, Dashboard, Sources, Variables, Budget")

# --- Pipeline Setup ---
@app.on_event("startup")
async def startup_event():
    """Configurar pipeline al iniciar la aplicación."""
    try:
        from data_pipeline import get_pipeline
        pipeline = get_pipeline()
        
        # Pre-cargar caché (opcional, para que la primera request sea rápida)
        try:
            print("⚡ Pre-cargando caché de datos...")
            pipeline.get_cuenta_data()
            print("✓ Caché pre-cargado exitosamente")
        except Exception as e:
            print(f"⚠ No se pudo pre-cargar caché: {e}")
            print("  (El caché se cargará en la primera request)")
    except Exception as e:
        print(f"⚠ Error configurando pipeline: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Limpiar recursos al cerrar."""
    try:
        from data_pipeline import reset_pipeline
        reset_pipeline()
        print("✓ Pipeline limpiado")
    except Exception as e:
        print(f"⚠ Error limpiando pipeline: {e}")

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
        from data_pipeline import get_pipeline
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
        from data_pipeline import get_pipeline
        pipeline = get_pipeline()
        pipeline.invalidate_cache(scope=scope)
        return {"status": "success", "message": f"Caché invalidado: {scope}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error invalidando caché: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
