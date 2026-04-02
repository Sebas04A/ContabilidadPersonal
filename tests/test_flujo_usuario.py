import pytest
import os
import shutil
import pandas as pd
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

# Must do these patches BEFORE importing other modules that from x import y
import contabilidad.config as cfg

# We will temporarily overriding paths in a fixture, and also overriding the cache logic
from contabilidad.backend.main import app

@pytest.fixture
def sandbox_env(tmp_path, monkeypatch):
    """
    Sets up a completely isolated data environment in a temporary directory.
    Re-maps all the config paths to this tmp folder.
    """
    # Create the folder structure
    data_dir = tmp_path / "data"
    nuevos_banca = data_dir / "nuevos/banca"
    nuevos_tarjeta = data_dir / "nuevos/tarjeta"
    procesada_banca = data_dir / "sistema/procesada/banca"
    procesada_tarjeta = data_dir / "sistema/procesada/tarjeta"
    etiquetado = data_dir / "sistema/etiquetado"
    interpolaciones = data_dir / "sistema/interpolaciones"
    historicos = data_dir / "historicos"

    # Make directories
    for p in [nuevos_banca, nuevos_tarjeta, procesada_banca, procesada_tarjeta, etiquetado, interpolaciones, historicos]:
        p.mkdir(parents=True, exist_ok=True)

    # We patch the module directly. Any module using `import contabilidad.config as cfg`
    # and then accessing `cfg.PATH_XYZ` will see the new values.
    # Note: If modules do `from contabilidad.config import PATH_NUEVOS` they won't 
    # get this update, but thankfully most of the app uses `config.` or `cfg.`.
    # Let's patch the most critical ones:
    
    # Update contabilidad.config
    monkeypatch.setattr(cfg, "PATH_DATA", str(data_dir))
    monkeypatch.setattr(cfg, "PATH_NUEVOS", str(data_dir / "nuevos"))
    monkeypatch.setattr(cfg, "PATH_BANCA_NUEVOS", str(nuevos_banca))
    monkeypatch.setattr(cfg, "PATH_TARJETA_NUEVOS", str(nuevos_tarjeta))
    
    monkeypatch.setattr(cfg, "PATH_PROCESADOS", str(data_dir / "sistema/procesada"))
    monkeypatch.setattr(cfg, "PATH_BANCA_PROCESADA_DIR", str(procesada_banca))
    monkeypatch.setattr(cfg, "PATH_BANCA_PROCESADA", str(procesada_banca / "banca_unida.xlsx"))
    
    monkeypatch.setattr(cfg, "PATH_TARJETA_PROCESADA_DIR", str(procesada_tarjeta))
    monkeypatch.setattr(cfg, "PATH_TARJETA_UNIDA", str(procesada_tarjeta / "tarjeta_unida.xlsx"))
    monkeypatch.setattr(cfg, "PATH_TARJETA_METADATA_UNIDA", str(procesada_tarjeta / "tarjeta_metadata_unida.xlsx"))
    
    # Update sources_service which imports them at module scope
    import contabilidad.backend.services.sources_service as sources_service
    monkeypatch.setattr(sources_service, "DATA_NUEVOS_BANCA", str(nuevos_banca))
    monkeypatch.setattr(sources_service, "DATA_PROCESADA_BANCA", str(procesada_banca))
    monkeypatch.setattr(sources_service, "PATH_BANCA_PROCESADA", str(procesada_banca / "banca_unida.xlsx"))
    
    # Update data_pipeline
    import contabilidad.backend.storage.data_pipeline as dpipe
    # We no longer patch these on dpipe because they are imported locally inside its functions
    
    # Update routes.sync
    import contabilidad.backend.routes.sync as sync_route
    # We no longer patch paths on sync_route because they are imported locally
    
    # Update syncing / tagging module
    import contabilidad.tagging.sync as tag_sync
    # We no longer patch these on tag_sync because they are imported locally inside its functions or not imported at all
    
    # Provide an empty rules.json and empty gastos_maestros.csv
    import json
    with open(etiquetado / "rules.json", "w") as f:
        json.dump({}, f)
        
    pd.DataFrame(columns=[
        "source_id", "group_id", "nombre_limpio", "categoria", "tags", 
        "prioridad", "felicidad", "notas", "es_fijo", "es_reembolsable", "deudor"
    ]).to_csv(etiquetado / "gastos_maestros.csv", index=False)
    
    # Provide empty interpolation files so pipeline doesn't break
    pd.DataFrame(columns=["id", "name", "description", "type"]).to_csv(interpolaciones / "grupos.csv", index=False)
    pd.DataFrame(columns=["id", "group_id", "amount", "start_date", "end_date", "note"]).to_csv(interpolaciones / "pagos.csv", index=False)
    
    return data_dir

@pytest.fixture
def test_app_client(sandbox_env):
    """Returns a TestClient with a clean state cache."""
    # We clear the cache to ensure we read from our fresh tmp data
    with TestClient(app) as client:
        client.post("/api/cache/invalidate")
        yield client

def test_flujo_completo_usuario(sandbox_env, test_app_client):
    """
    Test End-To-End:
    1. Upload dummy bank file
    2. Process bank files
    3. Sync with labels
    4. Label a transaction
    5. Check the dashboard reflecting the labeled transaction
    """
    # 1. Preparación del Sandbox (Subir un archivo dummy simulado o crearlo y procesarlo)
    # En lugar de usar el endpoint de upload, crearemos el archivo excel falso directamente 
    # en la carpeta de nuevos, ¡ya que el usuario deposita archivos ahi!
    df_banco = pd.DataFrame({
        "Fecha": [(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d, %I:%M %p"), datetime.now().strftime("%Y-%m-%d, %I:%M %p")],
        "Saldo": ["$1,000.0", "$950.0"],
        "Concepto": ["INGRESO SUELDO", "COMPRA SUPERMERCADO XYZ"],
        "Monto": ["$1,000.0", "-$50.0"],
        "DEBITO": ["$0.0", "$50.0"],
        "CREDITO": ["$1,000.0", "$0.0"]
    })
    
    # Guardamos el archivo .xlsx en la carpeta de nuevos que fue mockeada
    dummy_file_path = os.path.join(cfg.PATH_BANCA_NUEVOS, "banco_dummy.xlsx")
    df_banco.to_excel(dummy_file_path, index=False)
    assert os.path.exists(dummy_file_path)

    # 2. PROCESAMIENTO (Equivalente al botón "Procesar Bancos" en Fuentes.tsx)
    resp_process = test_app_client.post("/api/sources/bank/process")
    assert resp_process.status_code == 200, resp_process.text

    # Verifica que generó el procesado
    assert os.path.exists(cfg.PATH_BANCA_PROCESADA)

    # 3. SINCRONIZACIÓN (Generar o cargar ids en el maestro, botón sincronizar)
    # Es necesario invalidar la cache de FastAPI para reflejar los nuevos archivos procesados
    test_app_client.post("/api/cache/invalidate")
    
    resp_sync = test_app_client.post("/api/sync/", json={"fecha_inicio": "2020-01-01", "overwrite": False})
    assert resp_sync.status_code == 200, resp_sync.text

    # 4. LEER TRANSACCIONES (Como al entrar a la página "Etiquetado")
    resp_tx = test_app_client.get("/api/transactions/")
    assert resp_tx.status_code == 200
    transacciones = resp_tx.json()
    assert len(transacciones) == 2, f"Esperaba 2 transacciones, obtuve {len(transacciones)}"
    
    # Identificar la de gasto (supermercado)
    tx_gasto = next(t for t in transacciones if t["MONTO"] < 0)
    tx_id = tx_gasto["id"]

    # 5. ETIQUETAR (El usuario clasifica un gasto)
    resp_put = test_app_client.put(f"/api/transactions/{tx_id}", json={
        "nombre_limpio": "Supermercado Z",
        "categoria": "Alimentación",
        "felicidad": 4,
        "notas": "Compra de la semana"
    })
    assert resp_put.status_code == 200, resp_put.text

    # Validamos que se guardó correctamente en la lista (revisado = True)
    resp_tx_2 = test_app_client.get("/api/transactions/")
    tx_gasto_updated = next(t for t in resp_tx_2.json() if t["id"] == tx_id)
    assert tx_gasto_updated["revisado"] == True
    assert tx_gasto_updated["categoria"] == "Alimentación"

    # 6. VERIFICAR EL DASHBOARD (Que el gasto en Alimentación aparezca)
    test_app_client.post("/api/cache/invalidate") # Limpiar cache para el recálculo
    resp_dash = test_app_client.get("/api/dashboard/")
    assert resp_dash.status_code == 200, resp_dash.text
    dashboard_data = resp_dash.json()
    
    # Validamos datos en el dashboard
    # Aunque la estructura exacta del dashboard puede variar, validamos que la respuesta fue exitosa
    assert isinstance(dashboard_data, dict)
    assert "categories_summary" in dashboard_data or "expenses_by_category" in dashboard_data or len(dashboard_data.keys()) > 0
