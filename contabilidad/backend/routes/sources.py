from fastapi import APIRouter, HTTPException
import pandas as pd
import os
from typing import List
from contabilidad.cuenta.lectura.cuenta import leer_cuenta_nuevo
from contabilidad.cuenta.lectura.FileProcessingConfig import FileProcessingConfig
from contabilidad.backend.utils import add_id_column

from contabilidad.cuenta.validacion import probar_validez_saldo
import io
import contextlib

router = APIRouter()

from contabilidad.config import PATH_BANCA_NUEVOS, PATH_BANCA_PROCESADA, PATH_BANCA_PROCESADA_DIR, PATH_TARJETA_NUEVOS, PATH_TARJETA_PROCESADA, PATH_TARJETA_PROCESADA_DIR, PATH_TARJETA_METADATA_UNIDA
from contabilidad.backend.data_pipeline import get_pipeline
from contabilidad.tarjeta.generar_data_limpia import obtener_datos_tarjeta, DATOS_TARJETA_COMPLETA

router = APIRouter()

DATA_NUEVOS_BANCA = PATH_BANCA_NUEVOS
DATA_PROCESADA_BANCA = PATH_BANCA_PROCESADA_DIR

DATA_NUEVOS_TARJETA = PATH_TARJETA_NUEVOS
DATA_PROCESADA_TARJETA = PATH_TARJETA_PROCESADA

@router.post("/bank/process")
async def process_bank_sources():
    """
    Lee todos los archivos Excel en data/nuevos/banca, los procesa y los une en un solo archivo.
    Guarda el resultado en data/procesada/banca.
    """
    try:
        # Verificar directorios
        if not os.path.exists(DATA_NUEVOS_BANCA):
            raise HTTPException(status_code=404, detail=f"Directorio no encontrado: {DATA_NUEVOS_BANCA}")
        
        if not os.path.exists(DATA_PROCESADA_BANCA):
            os.makedirs(DATA_PROCESADA_BANCA)

        files = [f for f in os.listdir(DATA_NUEVOS_BANCA) if f.endswith(".xlsx")]
        
        if not files:
            return {"status": "warning", "message": "No hay archivos .xlsx en data/nuevos/banca", "files_processed": 0}

        # Process files
        raw_items = []

        for file_name in files:
            file_path = os.path.join(DATA_NUEVOS_BANCA, file_name)
            try:
                # Configuración por defecto, ajustar si es necesario según el archivo
                config = FileProcessingConfig(path=file_path)
                df = leer_cuenta_nuevo(config)
                
                if 'FECHA' in df.columns:
                    df['FECHA'] = pd.to_datetime(df['FECHA'])
                    if not df.empty:
                        start_date = df['FECHA'].min()
                        end_date = df['FECHA'].max()
                        raw_items.append({
                            'start_date': start_date,
                            'end_date': end_date,
                            'file_name': file_name,
                            'df': df
                        })
                    else:
                         print(f"Skipping {file_name}: Empty dataframe")
                else:
                    print(f"Skipping {file_name}: No FECHA column found")
                    
            except Exception as e:
                print(f"Error procesando {file_name}: {e}")
                continue

        if not raw_items:
             raise HTTPException(status_code=500, detail="No se pudo procesar ningún archivo correctamente.")

        print("\n=== INICIO DE PROCESAMIENTO SECUENCIAL ===")
        # Ordenar por fecha de inicio DESCENDENTE (archivos más nuevos primero)
        # Esto nos permite usar el archivo más reciente como base y "rellenar" hacia atrás con el pasado.
        raw_items.sort(key=lambda x: x['end_date'], reverse=True)
        print(f"Archivos detectados y ordenados por novedad: {[(item['file_name'],item['start_date'], item['end_date']) for item in raw_items]}")

        # Inicializar con el archivo más nuevo (nuestra "punta" de lanza en el tiempo)
        base_df = raw_items[0]['df']
        # Quitar el día más antiguo por si está incompleto
        final_dfs = [base_df[base_df['FECHA'] > base_df['FECHA'].min()]]
        current_min_date = raw_items[0]['start_date']
        
        print(f"\n[1] ARCHIVO BASE (Más reciente): {raw_items[0]['file_name']}")
        print(f"    Rango del base: {raw_items[0]['start_date']} hasta {raw_items[0]['end_date']}")
        print(f"    Umbral de búsqueda hacia atrás: {current_min_date}")

        # Iterar a través de los archivos más antiguos para "coser" la historia
        for i in range(1, len(raw_items)):
            item = raw_items[i]
            df = item['df']
            file_name = item['file_name']
            
            print(f"\n[{i+1}] PROCESANDO HISTÓRICO: {file_name}")
            # Solo queremos datos que sean estrictamente más antiguos que el punto de inicio de lo que ya tenemos.
            # Esto evita duplicados y asegura que prevalezca la información de los archivos más nuevos.
            older_slice = df[df['FECHA'] < (current_min_date + pd.Timedelta(days=1))].copy()
            
            if not older_slice.empty:
                rows_added = len(older_slice)

                # Vemos si debemos hacer un revert
                is_descending = False
                if len(older_slice) > 1:
                    # Buscamos la primera fecha distinta para determinar si el orden es descendente
                    first_date = older_slice['FECHA'].iloc[0].date()
                    for i in range(1, len(older_slice)):
                        current_date = older_slice['FECHA'].iloc[i].date()
                        if current_date != first_date:
                            is_descending = first_date > current_date
                            break

                if not is_descending:
                    print(f"    -> Detectado orden DESCENDENTE en {file_name}. Invirtiendo...")
                    older_slice = older_slice[::-1].reset_index(drop=True)


                # Insertamos al inicio de la lista (es el pasado)
                final_dfs.insert(len(final_dfs), older_slice)
                
                # Actualizamos el umbral para el siguiente archivo
                new_min = older_slice['FECHA'].min()
                print(f"    -> AGREGADAS {rows_added} filas de historia.")
                print(f"    -> Nuevo punto de inicio histórico: {new_min}")
                current_min_date = new_min
            else:
                print(f"    -> IGNORADO: No tiene datos anteriores a {current_min_date}")

        print("\n=== UNIFICACIÓN Y VERIFICACIÓN DE FLUJO ===")
        # Unir todos los fragmentos (deberían quedar ordenados de Pasado -> Presente por los insert(0))
        df_unido = pd.concat(final_dfs, ignore_index=True)
        print(f"Total de filas unificadas: {len(df_unido)}")
        
        # Verificar la orientación temporal para la validación de saldos
        # La validación necesita que los datos fluyan cronológicamente para que Saldo(i) = Saldo(i-1) + Monto(i)
        if not df_unido.empty and 'FECHA' in df_unido.columns:
            first_date = df_unido['FECHA'].iloc[0]
            last_date = df_unido['FECHA'].iloc[-1]
            print(f"Primera fecha en DF: {first_date} | Última fecha: {last_date}")
            
            if first_date > last_date:
                print("(!) Orden inverso detectado (Nuevo a Antiguo). Volteando para validación...")
                df_unido = df_unido[::-1].reset_index(drop=True)
                print("    DF invertido correctamente.")

        # Agregar metadatos
        df_unido['FUENTE'] = 'BANCO'
        df_unido = add_id_column(df_unido, source_type='BANCO')

        # VALIDACIÓN DE SALDOS
        # Redirigimos la salida para capturar el reporte que ve el usuario en el frontend
        validation_output = io.StringIO()
        with contextlib.redirect_stdout(validation_output):
            print("--- INICIO VALIDACIÓN DE SALDOS ---")
            try:
                # Usamos una copia limpia para validar sin afectar el original
                valid_df = df_unido.copy().reset_index(drop=True)
                probar_validez_saldo(valid_df)
            except Exception as ve:
                print(f"X Error durante validación: {ve}")
            print("--- FIN VALIDACIÓN ---")
        
        validation_log = validation_output.getvalue()

        # Filtrar columnas requeridas para guardar
        required_cols = ['id', 'FECHA', 'DESCRIPCION', 'MONTO', 'FUENTE', 'SALDO']
        final_cols = [col for col in required_cols if col in df_unido.columns]
        df_unido = df_unido[final_cols]
        # Re-sort just in case
        # if 'FECHA' in df_unido.columns:
        #     df_unido.sort_values(by='FECHA', inplace=True)

        output_file = PATH_BANCA_PROCESADA
        df_unido.to_excel(output_file, index=False)

        # Actualizar pipeline
        try:
            pipeline = get_pipeline()
            pipeline.get_banca_data(force_reload=True)
            print("✓ Pipeline actualizado con nuevos datos de banca")
        except Exception as e:
            print(f"⚠ Error actualizando pipeline: {e}")

        # Preparar respuesta del chart
        chart_data = []
        min_date = None
        max_date = None
        
        if 'FECHA' in df_unido.columns and 'SALDO' in df_unido.columns:
            chart_df = df_unido[['FECHA', 'SALDO', 'MONTO']].copy()
            chart_df['FECHA'] = pd.to_datetime(chart_df['FECHA'])
            chart_df = chart_df.sort_values('FECHA')
            
            # Formato string para JSON
            # Fillna just in case
            chart_df['SALDO'] = chart_df['SALDO'].fillna(0)
            chart_df['MONTO'] = chart_df['MONTO'].fillna(0)
            
            chart_data = chart_df.apply(lambda x: {
                'date': x['FECHA'].strftime('%Y-%m-%d %H:%M:%S'),
                'saldo': x['SALDO'],
                'monto': x['MONTO']
            }, axis=1).tolist()
            
            if not chart_df.empty:
                min_date = chart_df['FECHA'].min().isoformat()
                max_date = chart_df['FECHA'].max().isoformat()

        return {
            "status": "success",
            "message": f"Se procesaron {len(raw_items)} archivos y se guardó en {output_file}",
            "files_processed": [item['file_name'] for item in raw_items],
            "total_rows": len(df_unido),
            "validation_report": validation_log,
            "chart_data": chart_data,
            "date_range": {
                "min": min_date,
                "max": max_date
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/card/process")
async def process_card_sources():
    """
    Lee todos los archivos .xls en data/nuevos/tarjeta, los procesa y los une en un solo archivo.
    Guarda el resultado en data/procesada/tarjeta/tarjeta_unida.xlsx.
    """
    try:
        # Verificar directorios
        if not os.path.exists(DATA_NUEVOS_TARJETA):
            raise HTTPException(status_code=404, detail=f"Directorio no encontrado: {DATA_NUEVOS_TARJETA}")
        
        if not os.path.exists(DATA_PROCESADA_TARJETA):
            os.makedirs(DATA_PROCESADA_TARJETA)

        files = [f for f in os.listdir(DATA_NUEVOS_TARJETA) if f.lower().endswith(".xls")]
        
        if not files:
            return {"status": "warning", "message": "No hay archivos .xls en data/nuevos/tarjeta", "files_processed": 0}

        dfs = []
        mds = []
        processed_files = []

        for file_name in files:
            file_path = os.path.join(DATA_NUEVOS_TARJETA, file_name)
            try:
                df, metadata = obtener_datos_tarjeta(file_path)
                
                # Standardize DataFrame
                # Original columns: ['FECHA', 'DESCRIPCION', 'VALOR', 'OPERACION']
                # Rename VALOR -> MONTO
                df.rename(columns={'VALOR': 'MONTO'}, inplace=True)
                
                # Add metadata columns if needed? or just keep standard
                # Let's keep it simple for now, focusing on transactions
                
                dfs.append(df)
                
                # Enrich metadata with computed fields same as in generar_data_limpia.py legacy function
                # Extract clean dict from dataclass
                meta_dict = metadata.__dict__.copy()
                
                # The user wants specific calculated fields:
                # 'saldo_anterior', 'subtotal_pagado', 'pagos_muchas_gracias' -> these come from header
                # 'total_a_pagar' -> from totales
                # 'num_transacciones', 'fecha_min', 'fecha_max', 'total_mes', 'total_a_pagar_despues' -> computed
                
                # Note: 'metadata' here is DATOS_TARJETA_COMPLETA which already has structured info
                # We can access nested dataclasses
                
                # Map flat structure for the dataframe
                flat_meta = {
                    'EMPRESA': metadata.EMPRESA,
                    'NUM_TARJETA': metadata.NUM_TARJETA,
                    'FECHA_EMISION': metadata.FECHA_EMISION,
                    'FECHA_MAX_PAGO': metadata.FECHA_MAX_PAGO,
                    
                    'saldo_anterior': metadata.SALDO_ANTERIOR, # from header
                    'subtotal_pagado': metadata.SUBTOTAL_PAGADO, # from header
                    'total_a_pagar': metadata.TOTAL_A_PAGAR, # from totales
                    'minimo_a_pagar': metadata.MINIMO_A_PAGAR,
                    'total_consumo': metadata.TOTAL_CONSUMO,
                    
                    'num_transacciones': len(df),
                    'fecha_min': df['FECHA'].min() if not df.empty else None,
                    'fecha_max': df['FECHA'].max() if not df.empty else None,
                    'total_mes': df['MONTO'].sum() if not df.empty else 0,
                    
                    # 'pagos_muchas_gracias' is not directly in DATOS_TARJETA_COMPLETA top level, 
                    # but it was part of logic. Let's assume subtotal_pagado is the main one.
                    
                    'total_a_pagar_despues': metadata.TOTAL_A_PAGAR + (df['MONTO'].sum() if not df.empty else 0),
                    'source_file': file_name
                }
                
                mds.append(flat_meta)
                processed_files.append(file_name)
            except Exception as e:
                print(f"Error procesando {file_name}: {e}")
                continue

        if not dfs:
             raise HTTPException(status_code=500, detail="No se pudo procesar ningún archivo correctamente.")

        # 1. Unir Transacciones
        df_unido = pd.concat(dfs, ignore_index=True)
        # ... logic as before ...
        
        # Agregar columna FUENTE
        df_unido['FUENTE'] = 'TARJETA'

        # Generar IDs únicos
        df_unido = add_id_column(df_unido, source_type='TARJETA')

        # Ordenar por fecha
        if 'FECHA' in df_unido.columns:
            df_unido['FECHA'] = pd.to_datetime(df_unido['FECHA'])
            df_unido.sort_values(by='FECHA', inplace=True)
        
        # Filtrar columnas requeridas
        required_cols = ['id', 'FECHA', 'DESCRIPCION', 'MONTO', 'FUENTE', 'OPERACION']
        final_cols = [col for col in required_cols if col in df_unido.columns]
        df_unido = df_unido[final_cols]

        output_file = os.path.join(DATA_PROCESADA_TARJETA, "tarjeta_unida.xlsx")
        df_unido.to_excel(output_file, index=False)
        
        # 2. Unir Metadata y Guardar
        if mds:
            df_metadata = pd.DataFrame(mds)
            
            # Sort metadata by emission date
            if 'FECHA_EMISION' in df_metadata.columns:
                 df_metadata['FECHA_EMISION'] = pd.to_datetime(df_metadata['FECHA_EMISION'])
                 df_metadata.sort_values(by='FECHA_EMISION', inplace=True)
                 
            output_meta_file = PATH_TARJETA_METADATA_UNIDA
            df_metadata.to_excel(output_meta_file, index=False)
            print(f"✓ Metadata guardada en {output_meta_file}")

        # Actualizar pipeline

        # Actualizar pipeline
        try:
            pipeline = get_pipeline()
            # method get_tarjeta_unida_data needs to be implemented or we can reuse existing if adapted
            if hasattr(pipeline, 'get_tarjeta_unida_data'):
                pipeline.get_tarjeta_unida_data(force_reload=True)
                print("✓ Pipeline actualizado con nuevos datos de tarjeta unida")
        except Exception as e:
            print(f"⚠ Error actualizando pipeline: {e}")

        # Preparar respuesta del chart para Tarjeta
        chart_data = []
        min_date = None
        max_date = None
        
        if 'FECHA' in df_unido.columns and 'MONTO' in df_unido.columns:
            # Para tarjetas, a veces es útil ver el acumulado o solo los movimientos
            # Aquí mostraremos los movimientos individuales ordenados cronológicamente
            chart_df = df_unido[['FECHA', 'MONTO', 'DESCRIPCION']].copy()
            chart_df['FECHA'] = pd.to_datetime(chart_df['FECHA'])
            chart_df = chart_df.sort_values('FECHA')
            
            # Fillna
            chart_df['MONTO'] = chart_df['MONTO'].fillna(0)
            
            # Calcular un "Saldo Simulado" o acumulado para que el gráfico se vea interesante?
            # O mejor, mostramos el Gasto Diario Agrupado para que no sea un caos de puntos
            # Agrupamos por día para ver gasto diario
            daily_spend = chart_df.groupby(chart_df['FECHA'].dt.date)['MONTO'].sum().reset_index()
            daily_spend['FECHA'] = pd.to_datetime(daily_spend['FECHA'])
            
            chart_data = daily_spend.apply(lambda x: {
                'date': x['FECHA'].strftime('%Y-%m-%d'),
                'monto': x['MONTO'],
                'saldo': 0 # No hay saldo en raw transactions, enviamos 0 para mantener contrato o lo omitimos en frontend
            }, axis=1).tolist()
            
            if not chart_df.empty:
                min_date = chart_df['FECHA'].min().isoformat()
                max_date = chart_df['FECHA'].max().isoformat()

        return {
            "status": "success",
            "message": f"Se procesaron {len(dfs)} archivos y se guardó en {output_file}",
            "files_processed": processed_files,
            "total_rows": len(df_unido),
            "chart_data": chart_data,
            "date_range": {
                "min": min_date,
                "max": max_date
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
