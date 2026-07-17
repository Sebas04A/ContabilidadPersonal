import os
import pytest
import pandas as pd
from contabilidad.backend.storage.data_pipeline import get_pipeline, reset_pipeline

@pytest.fixture(autouse=True)
def setup_mock_env(monkeypatch):
    """Asegura que todos los tests corren usando la mock data."""
    monkeypatch.setenv("MOCK_MODE", "true")
    reset_pipeline()

def test_metadata_structure():
    """Valida la estructura de la metadata (pagos unificados)."""
    pipeline = get_pipeline()
    metadata = pipeline.get_credit_card_metadata()
    
    # 1. Debe cargar y no estar vacía
    assert not metadata.empty, "La metadata de la tarjeta no debería estar vacía. Revisa la lectura de Excels YYYY-MM."
    
    # 2. Debe contener columnas críticas
    required_cols = ['FECHA_EMISION', 'FECHA_MAX_PAGO', 'total_a_pagar', 'minimo_a_pagar', 'total_consumo']
    for col in required_cols:
         assert col in metadata.columns, f"Falta la columna '{col}' en la metadata."

def test_consumos_structure():
    """Valida la estructura de la tarjeta unida (consumos brutos)."""
    pipeline = get_pipeline()
    consumos = pipeline.get_raw_data('tarjeta')
    
    assert not consumos.empty, "Los consumos no deben estar vacíos."
    required_cols = ['FECHA', 'MONTO', 'DESCRIPCION']
    for col in required_cols:
         assert col in consumos.columns, f"Falta la columna '{col}' en los consumos."
         
    # MONTO should effectively represent the numeric value of the consumption
    assert pd.api.types.is_numeric_dtype(consumos['MONTO']), "MONTO debe ser numérico."

def test_banca_structure():
    """Valida que la banca tenga la estructura adecuada para los pagos cruzados."""
    pipeline = get_pipeline()
    banca = pipeline.get_raw_data('cuenta')
    
    assert not banca.empty, "Los datos del banco no deben estar vacíos."
    
    # Validar que al menos un pago de tarjeta exista
    pagos = banca[banca['DESCRIPCION'].str.contains('PAGO TARJETA', case=False, na=False)]
    assert not pagos.empty, "No se generaron o encontraron pagos de tarjeta en la banca."
    
    # El monto de pago debe ser numérico y preferiblemente negativo (salida de dinero)
    assert pd.api.types.is_numeric_dtype(banca['MONTO'])
    assert pagos['MONTO'].mean() < 0, "Los pagos de tarjeta deben registrarse como salidas bancarias (negativas)."
