from fastapi import APIRouter, HTTPException
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime

router = APIRouter()

@router.get("/cards")
def get_cards_analysis():
    """
    Obtiene datos para el análisis de tarjetas:
    - Gráfico de Línea: Evolución de 'TARJETA' (Acumulado - Pagos)
    - Gráfico de Barras: Pagos realizados
    - Áreas Sombreadas: Periodos de facturación (Verde/Rojo según estado)
    - Líneas Verticales: Fechas límite de pago
    """
    try:
        # 1. Obtener datos de cuenta procesados (con columnas TARJETA, PAGO_TARJETA, etc.)
        try:
            from ..data_pipeline import get_pipeline
        except ImportError:
            try:
                from contabilidad.backend.data_pipeline import get_pipeline
            except ImportError:
                 # Fallback for when running directly or different structure
                 import sys
                 import os
                 # Add backend dir to path if needed
                 current_dir = os.path.dirname(os.path.abspath(__file__)) # routes
                 backend_dir = os.path.dirname(current_dir) # backend
                 if backend_dir not in sys.path:
                     sys.path.append(backend_dir)
                 from data_pipeline import get_pipeline

        pipeline = get_pipeline()
        # Aseguramos que se ejecute la transformación 'tarjetas'
        df_cuenta = pipeline.get_processed_data(source='cuenta')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo datos de cuenta: {str(e)}")

    try:
        # 2. Obtener metadatos de tarjetas (Resúmenes de estados de cuenta)
        # Esto usa la función que agregamos al pipeline
        if hasattr(pipeline, 'get_tarjeta_metadata'):
            df_resumen = pipeline.get_tarjeta_metadata()
        else:
             # Fallback si no se actualizó la instancia en memoria (raro)
             print("Pipeline no tiene get_tarjeta_metadata, intentando recargar...")
             try:
                from ..data_pipeline import reset_pipeline, get_pipeline
             except ImportError:
                from contabilidad.backend.data_pipeline import reset_pipeline, get_pipeline
                
             reset_pipeline()
             pipeline = get_pipeline()
             df_resumen = pipeline.get_tarjeta_metadata()
    except Exception as e:
        print(f"Error obteniendo metadatos de tarjeta: {e}")
        df_resumen = pd.DataFrame()

    # 3. Obtener Pagos (Barras)
    try:
        from contabilidad.cuenta.ObtenerVariables import obtener_pagos_tarjetas
        # Usamos df_cuenta tal cual viene del pipeline (debería tener las columnas necesarias)
        raw_payments = obtener_pagos_tarjetas(df_cuenta)
        
        pagos_data = []
        for p in raw_payments:
             # p es un objeto PAGO con atributos inicio, monto
             fecha = p.inicio
             if hasattr(fecha, 'strftime'):
                 fecha_str = fecha.strftime('%Y-%m-%d')
             else:
                 fecha_str = str(fecha)
                 
             pagos_data.append({
                 'date': fecha_str,
                 'amount': float(p.monto)
             })
        # Ordenar pagos
        pagos_data.sort(key=lambda x: x['date'])
        
    except Exception as e:
        print(f"Error extrayendo pagos: {e}")
        pagos_data = []

    # 4. Construir Datos para el Gráfico (Línea Principal)
    chart_data = []
    if not df_cuenta.empty:
        # Filtrar y ordenar
        df_chart = df_cuenta.sort_values('FECHA').copy()
        
        # Seleccionar columnas relevantes
        cols_to_keep = ['FECHA', 'TARJETA', 'PAGO_TARJETA', 'ACUMULADO_TARJETA']
        available_cols = [c for c in cols_to_keep if c in df_chart.columns]
        
        for _, row in df_chart[available_cols].iterrows():
            ts = row['FECHA']
            date_str = ts.strftime('%Y-%m-%d')
            
            item = {'date': date_str}
            if 'TARJETA' in row:
                val = row['TARJETA']
                item['tarjeta'] = float(val) if pd.notnull(val) else 0.0
            
            if 'ACUMULADO_TARJETA' in row:
                 val = row['ACUMULADO_TARJETA']
                 item['acumulado'] = float(val) if pd.notnull(val) else 0.0
            
            chart_data.append(item)

    # 5. Construir Periodos (Áreas Sombreadas y Líneas Verticales)
    periods = []
    
    # Importar mapeo de columnas
    try:
        from contabilidad.tarjeta.tiposCsvDatos import MAPEO_COLUMNAS
    except ImportError:
        MAPEO_COLUMNAS = {}
        
    col_emision = MAPEO_COLUMNAS.get("FECHA_EMISION", "FECHA_EMISION")
    col_max_pago = MAPEO_COLUMNAS.get("FECHA_MAX_PAGO", "FECHA_MAX_PAGO")
    col_total = MAPEO_COLUMNAS.get("TOTAL_A_PAGAR", "TOTAL_A_PAGAR")
    col_consumo = MAPEO_COLUMNAS.get("TOTAL_CONSUMO", "TOTAL_CONSUMO")
    col_fecha_max_trans = MAPEO_COLUMNAS.get("MAX_FECHA_MOVIMIENTO", "MAX_FECHA_MOVIMIENTO")
    
    if not df_resumen.empty:
        # Asegurar fechas
        if col_emision in df_resumen.columns:
            df_resumen[col_emision] = pd.to_datetime(df_resumen[col_emision])
        if col_max_pago in df_resumen.columns:
            df_resumen[col_max_pago] = pd.to_datetime(df_resumen[col_max_pago])
        if col_fecha_max_trans in df_resumen.columns:
            df_resumen[col_fecha_max_trans] = pd.to_datetime(df_resumen[col_fecha_max_trans])
            
        for _, row in df_resumen.iterrows():
            try:
                f_em = row.get(col_emision)
                f_max = row.get(col_max_pago)
                f_max_trans = row.get(col_fecha_max_trans)
                total = row.get(col_total)
                consumo = row.get(col_consumo)
                
                if pd.isna(f_em) or pd.isna(f_max):
                    continue
                    
                periods.append({
                    'start_date': f_em.strftime('%Y-%m-%d'),
                    'end_date': f_max.strftime('%Y-%m-%d'),
                    'total_to_pay': float(total) if pd.notnull(total) else 0.0,
                    'max_transaction_date': f_max_trans.strftime('%Y-%m-%d'),
                    'consumption': float(consumo) if pd.notnull(consumo) else 0.0,
                    'period_name': row.get('Periodo', ''),
                    # Datos extra para la lista
                    'min_payment': float(row.get(MAPEO_COLUMNAS.get("MINIMO_A_PAGAR", "MINIMO_A_PAGAR"), 0)),
                    'status': 'closed' if f_max < datetime.now() else 'open'
                })
            except Exception as e:
                print(f"Error procesando periodo: {e}")
                continue
                
    # Ordenar periodos
    periods.sort(key=lambda x: x['start_date'])

    return {
        'chart_data': chart_data,
        'periods': periods,
        'payments': pagos_data
    }
