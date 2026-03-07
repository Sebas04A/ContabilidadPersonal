"""
Ejemplos de Uso del Data Pipeline
==================================

Este archivo muestra cómo usar el sistema de pipeline en diferentes escenarios.
"""

from data_pipeline import get_pipeline
import pandas as pd


# ============================================================================
# EJEMPLO 1: Uso Básico - Obtener datos con caché
# ============================================================================

def ejemplo_basico():
    """Obtener datos de cuenta con caché automático."""
    pipeline = get_pipeline()
    
    # Primera llamada: lee del CSV
    df = pipeline.get_cuenta_data()  # ⚙ Loading: cuenta_data from CSV
    
    # Segunda llamada: usa caché
    df = pipeline.get_cuenta_data()  # ✓ Cache hit: cuenta_data
    
    # Forzar recarga
    df = pipeline.get_cuenta_data(force_reload=True)  # ⚙ Loading: cuenta_data from CSV


# ============================================================================
# EJEMPLO 2: Pipeline de Transformaciones
# ============================================================================

def ejemplo_transformaciones():
    """Agregar transformaciones secuenciales."""
    pipeline = get_pipeline()
    
    # Definir transformaciones
    def agregar_mes(df: pd.DataFrame) -> pd.DataFrame:
        """Agrega columna de mes."""
        df['MES'] = df['FECHA'].dt.month
        return df
    
    def agregar_año(df: pd.DataFrame) -> pd.DataFrame:
        """Agrega columna de año."""
        df['AÑO'] = df['FECHA'].dt.year
        return df
    
    def marcar_pagos_fijos(df: pd.DataFrame) -> pd.DataFrame:
        """Marca pagos fijos (ejemplo simplificado)."""
        from storage import InterpolationStorage
        
        # Obtener grupos de tipo 'fixed'
        groups = InterpolationStorage.get_groups(type_filter='fixed')
        
        # Por cada grupo, marcar pagos
        for group in groups:
            payments = InterpolationStorage.get_payments(group['id'])
            # ... lógica de marcado ...
        
        return df
    
    # Agregar transformaciones al pipeline
    pipeline.add_transformation('agregar_mes', agregar_mes)
    pipeline.add_transformation('agregar_año', agregar_año)
    pipeline.add_transformation('marcar_fijos', marcar_pagos_fijos)
    
    # Obtener datos procesados
    df = pipeline.get_processed_data()
    # Primera vez:
    # ⚙ Loading: cuenta_data from CSV
    # ⚙ Executing: agregar_mes
    # ⚙ Executing: agregar_año
    # ⚙ Executing: marcar_fijos
    
    # Segunda vez (todo desde caché):
    df = pipeline.get_processed_data()
    # ✓ Cache hit: cuenta_data
    # ✓ Cache hit: agregar_mes
    # ✓ Cache hit: agregar_año
    # ✓ Cache hit: marcar_fijos


# ============================================================================
# EJEMPLO 3: Uso en Endpoint de Investments
# ============================================================================

def ejemplo_investments_endpoint():
    """Cómo usar el pipeline en el endpoint de chart-data."""
    from fastapi import APIRouter, HTTPException
    from storage import InterpolationStorage
    from contabilidad.cuenta.ObtenerVariables import marcar_fijos
    from contabilidad.Modelos import PAGO
    
    router = APIRouter()
    
    @router.get("/investments/chart-data")
    def get_investment_chart_data():
        """
        Versión optimizada con pipeline.
        """
        pipeline = get_pipeline()
        
        # 1. Obtener datos base (con caché)
        df = pipeline.get_cuenta_data()
        
        # 2. Obtener pagos de inversiones
        groups = InterpolationStorage.get_groups(type_filter='fixed')
        inversiones_group = next(
            (g for g in groups if g.get('name', '').lower() == 'inversiones'),
            None
        )
        
        if not inversiones_group:
            return prepare_chart_response(df, [], None)
        
        payments = InterpolationStorage.get_payments(inversiones_group['id'])
        
        # 3. Convertir a objetos PAGO
        pagos = []
        for payment in payments:
            start_date = pd.to_datetime(payment['start_date'])
            end_date = pd.to_datetime(payment['end_date']) if payment['end_date'] else None
            
            pagos.append(PAGO(
                monto=float(payment['amount']),
                inicio=start_date,
                fin=end_date
            ))
        
        # 4. Aplicar transformación (esta parte se puede cachear también)
        if pagos:
            df_with_inversion = marcar_fijos(df.copy(), pagos, 'INVERSION', incluir_ultimo=False)
        else:
            df_with_inversion = df.copy()
            df_with_inversion['INVERSION'] = 0.0
        
        # 5. Preparar respuesta
        return prepare_chart_response(df_with_inversion, pagos)


# ============================================================================
# EJEMPLO 4: Pipeline Completo para Análisis de Inversiones
# ============================================================================

def setup_investment_pipeline():
    """Configura un pipeline específico para análisis de inversiones."""
    pipeline = get_pipeline()
    
    # Limpiar transformaciones anteriores si existen
    pipeline.pipeline.transformations.clear()
    
    # 1. Transformación: Agregar columnas temporales
    def add_time_columns(df: pd.DataFrame) -> pd.DataFrame:
        df['MES'] = df['FECHA'].dt.month
        df['AÑO'] = df['FECHA'].dt.year
        df['DIA_SEMANA'] = df['FECHA'].dt.dayofweek
        return df
    
    # 2. Transformación: Marcar inversiones
    def mark_investments(df: pd.DataFrame) -> pd.DataFrame:
        from storage import InterpolationStorage
        from contabilidad.cuenta.ObtenerVariables import marcar_fijos
        from contabilidad.Modelos import PAGO
        
        groups = InterpolationStorage.get_groups(type_filter='fixed')
        inversiones_group = next(
            (g for g in groups if g.get('name', '').lower() == 'inversiones'),
            None
        )
        
        if not inversiones_group:
            df['INVERSION'] = 0.0
            return df
        
        payments = InterpolationStorage.get_payments(inversiones_group['id'])
        
        pagos = []
        for payment in payments:
            start_date = pd.to_datetime(payment['start_date'])
            end_date = pd.to_datetime(payment['end_date']) if payment['end_date'] else None
            
            pagos.append(PAGO(
                monto=float(payment['amount']),
                inicio=start_date,
                fin=end_date
            ))
        
        if pagos:
            df = marcar_fijos(df, pagos, 'INVERSION', incluir_ultimo=False)
        else:
            df['INVERSION'] = 0.0
        
        return df
    
    # 3. Transformación: Calcular métricas
    def calculate_metrics(df: pd.DataFrame) -> pd.DataFrame:
        df['SALDO_DISPONIBLE'] = df['SALDO'] - df['INVERSION']
        df['PORCENTAJE_INVERTIDO'] = (df['INVERSION'] / df['SALDO'] * 100).fillna(0)
        return df
    
    # Agregar al pipeline
    pipeline.add_transformation('time_columns', add_time_columns, cacheable=True)
    pipeline.add_transformation('mark_investments', mark_investments, cacheable=True)
    pipeline.add_transformation('calculate_metrics', calculate_metrics, cacheable=True)
    
    return pipeline


def get_investment_analysis():
    """Obtiene análisis completo de inversiones con pipeline."""
    pipeline = setup_investment_pipeline()
    
    # Obtener datos procesados (todo cacheado)
    df = pipeline.get_processed_data(source='cuenta')
    
    # Ahora df tiene todas las transformaciones aplicadas
    return df


# ============================================================================
# EJEMPLO 5: Invalidación de Caché
# ============================================================================

def ejemplo_invalidacion():
    """Cómo invalidar caché cuando los datos cambian."""
    pipeline = get_pipeline()
    
    # Obtener datos
    df = pipeline.get_processed_data()
    
    # Cuando se agrega un nuevo pago fijo, invalidar transformaciones
    # pero mantener caché de datos fuente
    pipeline.invalidate_cache(scope='transformations')
    
    # Cuando se sincroniza nueva data, invalidar todo
    pipeline.invalidate_cache(scope='all')
    
    # Invalidar solo desde una transformación específica en adelante
    pipeline.pipeline.invalidate_from('mark_investments')


# ============================================================================
# EJEMPLO 6: Estadísticas de Caché
# ============================================================================

def ejemplo_estadisticas():
    """Ver estadísticas de uso de caché."""
    pipeline = get_pipeline()
    
    stats = pipeline.get_cache_stats()
    print(stats)
    # {
    #     'source_cache': {
    #         'entries': 2,
    #         'keys': ['cuenta_data', 'tarjeta_data'],
    #         'total_memory_mb': 15.3
    #     },
    #     'transformation_cache': {
    #         'entries': 3,
    #         'keys': ['contabilidad_time_columns_...', ...],
    #         'total_memory_mb': 45.7
    #     },
    #     'transformations_registered': 3
    # }


# ============================================================================
# EJEMPLO 7: Integración con FastAPI Endpoint
# ============================================================================

def ejemplo_fastapi_completo():
    """Ejemplo completo de endpoint optimizado."""
    from fastapi import APIRouter
    
    router = APIRouter()
    
    @router.get("/investments/chart-data-optimized")
    def get_chart_data_optimized():
        """
        Endpoint optimizado que usa pipeline con caché.
        
        Primera llamada: ~2-3 segundos (carga CSV + transformaciones)
        Llamadas siguientes: ~50-100ms (todo desde caché)
        """
        # Setup pipeline (solo se ejecuta una vez)
        pipeline = setup_investment_pipeline()
        
        # Obtener datos procesados (cacheado)
        df = pipeline.get_processed_data(source='cuenta')
        
        # Preparar respuesta
        dates = df['FECHA'].dt.strftime('%Y-%m-%d').tolist()
        saldo = df['SALDO'].tolist()
        inversion = df['INVERSION'].tolist()
        saldo_disponible = df['SALDO_DISPONIBLE'].tolist()
        porcentaje_invertido = df['PORCENTAJE_INVERTIDO'].tolist()
        
        return {
            'dates': dates,
            'saldo': saldo,
            'inversion': inversion,
            'saldo_disponible': saldo_disponible,
            'porcentaje_invertido': porcentaje_invertido
        }
    
    @router.post("/investments/invalidate-cache")
    def invalidate_investment_cache():
        """Endpoint para invalidar caché manualmente."""
        pipeline = get_pipeline()
        pipeline.invalidate_cache(scope='transformations')
        return {"status": "cache_invalidated"}


# ============================================================================
# EJEMPLO 8: Testing con Pipeline
# ============================================================================

def ejemplo_testing():
    """Cómo testear con el pipeline."""
    from data_pipeline import reset_pipeline, get_pipeline
    
    # En cada test, resetear pipeline
    reset_pipeline()
    
    # Crear pipeline fresco
    pipeline = get_pipeline()
    
    # Agregar transformaciones de test
    def test_transform(df):
        df['TEST'] = 1
        return df
    
    pipeline.add_transformation('test', test_transform)
    
    # Usar skip_transform_cache para tests
    df = pipeline.get_processed_data(
        force_reload=True,
        skip_transform_cache=True
    )
    
    assert 'TEST' in df.columns
