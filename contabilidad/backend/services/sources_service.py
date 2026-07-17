import pandas as pd
import os
from typing import List
import io
import contextlib

from contabilidad.backend.services.bank_parser.account import read_new_account, read_csv_account
from contabilidad.backend.services.bank_parser.FileProcessingConfig import FileProcessingConfig
from contabilidad.backend.utils import add_id_column
from contabilidad.backend.services.bank_parser.validation import test_balance_validity
from contabilidad.backend.logger import get_logger
from contabilidad.config import (
    PATH_BANCA_NUEVOS, PATH_BANCA_PROCESADA, PATH_BANCA_PROCESADA_DIR, 
    PATH_TARJETA_NUEVOS, PATH_TARJETA_PROCESADA, PATH_TARJETA_PROCESADA_DIR, 
    PATH_TARJETA_METADATA_UNIDA
)
from contabilidad.backend.storage.data_pipeline import get_pipeline
from contabilidad.backend.services.credit_card.core import get_credit_card_data_from_excel, DATOS_TARJETA_COMPLETA, get_credit_card_data_from_excel_v2

logger = get_logger(__name__)

DATA_NUEVOS_BANCA = PATH_BANCA_NUEVOS
DATA_PROCESADA_BANCA = PATH_BANCA_PROCESADA_DIR

DATA_NUEVOS_TARJETA = PATH_TARJETA_NUEVOS
DATA_PROCESADA_TARJETA = PATH_TARJETA_PROCESADA

class SourcesService:
    _summary_cache = {"key": None, "data": None}

    def _get_files_mtime_hash(self, directory: str, extensions: tuple) -> str:
        if not os.path.exists(directory):
            return ""
        files = sorted([f for f in os.listdir(directory) if f.lower().endswith(extensions)])
        info = []
        for f in files:
            fp = os.path.join(directory, f)
            try:
                info.append(f"{f}:{os.path.getmtime(fp)}:{os.path.getsize(fp)}")
            except Exception:
                pass
        return "|".join(info)

    def get_sources_summary(self) -> dict:
        banca_key = self._get_files_mtime_hash(DATA_NUEVOS_BANCA, (".xlsx", ".csv"))
        card_key = self._get_files_mtime_hash(DATA_NUEVOS_TARJETA, (".xls", ".pdf"))
        cache_key = f"BANCA:{banca_key}||CARD:{card_key}"

        if SourcesService._summary_cache["key"] == cache_key and SourcesService._summary_cache["data"] is not None:
            return SourcesService._summary_cache["data"]

        bank_sources = []
        if os.path.exists(DATA_NUEVOS_BANCA):
            files = sorted([f for f in os.listdir(DATA_NUEVOS_BANCA) if (f.endswith(".xlsx") or f.endswith(".csv"))])
            for file_name in files:
                file_path = os.path.join(DATA_NUEVOS_BANCA, file_name)
                try:
                    if file_name.endswith(".csv"):
                        config = FileProcessingConfig(path=file_path, tiene_monto=False, saldo_col="SALDO", fecha_col="FECHA", descripcion_col="DESCRIPCION")
                        df = read_csv_account(config)
                    else:
                        config = FileProcessingConfig(path=file_path)
                        df = read_new_account(config)
                    
                    if df is not None and not df.empty and 'FECHA' in df.columns:
                        df['FECHA'] = pd.to_datetime(df['FECHA'])
                        df_sorted = df.sort_values('FECHA')
                        min_date = df_sorted['FECHA'].min().strftime('%Y-%m-%d')
                        max_date = df_sorted['FECHA'].max().strftime('%Y-%m-%d')
                        
                        monto_col = df_sorted['MONTO'] if 'MONTO' in df_sorted.columns else pd.Series(0.0, index=df_sorted.index)
                        monto_num = pd.to_numeric(monto_col, errors='coerce').fillna(0)
                        df_sorted['_monto_clean'] = monto_num.abs()

                        daily = df_sorted.groupby(df_sorted['FECHA'].dt.strftime('%Y-%m-%d')).agg(
                            count=('FECHA', 'count'),
                            monto=('_monto_clean', lambda x: round(float(x.sum()), 2))
                        ).reset_index()
                        daily.columns = ['date', 'count', 'monto']

                        chart_data = daily.to_dict(orient='records')
                        bank_sources.append({
                            "file_name": file_name,
                            "source_type": "bank",
                            "total_rows": len(df),
                            "min_date": min_date,
                            "max_date": max_date,
                            "chart_data": chart_data,
                            "error": None
                        })
                    else:
                        bank_sources.append({
                            "file_name": file_name,
                            "source_type": "bank",
                            "total_rows": 0,
                            "min_date": None,
                            "max_date": None,
                            "chart_data": [],
                            "error": "Archivo sin datos o sin columna FECHA"
                        })
                except Exception as e:
                    logger.warning("Error leyendo resumen banca para %s: %s", file_name, e)
                    bank_sources.append({
                        "file_name": file_name,
                        "source_type": "bank",
                        "total_rows": 0,
                        "min_date": None,
                        "max_date": None,
                        "chart_data": [],
                        "error": str(e)
                    })

        card_sources = []
        if os.path.exists(DATA_NUEVOS_TARJETA):
            files = sorted([f for f in os.listdir(DATA_NUEVOS_TARJETA) if f.lower().endswith(('.xls', '.pdf'))])
            for file_name in files:
                file_path = os.path.join(DATA_NUEVOS_TARJETA, file_name)
                try:
                    df, flat_meta = self._process_single_card_file(file_path, file_name)
                    if df is not None and not df.empty and 'FECHA' in df.columns:
                        df['FECHA'] = pd.to_datetime(df['FECHA'])
                        df_sorted = df.sort_values('FECHA')
                        min_date = df_sorted['FECHA'].min().strftime('%Y-%m-%d')
                        max_date = df_sorted['FECHA'].max().strftime('%Y-%m-%d')

                        monto_col = df_sorted['MONTO'] if 'MONTO' in df_sorted.columns else pd.Series(0.0, index=df_sorted.index)
                        monto_num = pd.to_numeric(monto_col, errors='coerce').fillna(0)
                        df_sorted['_monto_clean'] = monto_num.abs()

                        daily = df_sorted.groupby(df_sorted['FECHA'].dt.strftime('%Y-%m-%d')).agg(
                            count=('FECHA', 'count'),
                            monto=('_monto_clean', lambda x: round(float(x.sum()), 2))
                        ).reset_index()
                        daily.columns = ['date', 'count', 'monto']

                        chart_data = daily.to_dict(orient='records')
                        card_sources.append({
                            "file_name": file_name,
                            "source_type": "card",
                            "total_rows": len(df),
                            "min_date": min_date,
                            "max_date": max_date,
                            "chart_data": chart_data,
                            "error": None
                        })
                    else:
                        card_sources.append({
                            "file_name": file_name,
                            "source_type": "card",
                            "total_rows": 0,
                            "min_date": None,
                            "max_date": None,
                            "chart_data": [],
                            "error": "Archivo sin datos o sin columna FECHA"
                        })
                except Exception as e:
                    logger.warning("Error leyendo resumen tarjeta para %s: %s", file_name, e)
                    card_sources.append({
                        "file_name": file_name,
                        "source_type": "card",
                        "total_rows": 0,
                        "min_date": None,
                        "max_date": None,
                        "chart_data": [],
                        "error": str(e)
                    })

        bank_sources.sort(key=lambda x: x['min_date'] or '')
        card_sources.sort(key=lambda x: x['min_date'] or '')

        res = {
            "bank_sources": bank_sources,
            "card_sources": card_sources
        }

        SourcesService._summary_cache["key"] = cache_key
        SourcesService._summary_cache["data"] = res
        return res

    def process_bank_data(self) -> dict:
        if not os.path.exists(DATA_NUEVOS_BANCA):

            raise ValueError(f"Directorio no encontrado: {DATA_NUEVOS_BANCA}")
        
        if not os.path.exists(DATA_PROCESADA_BANCA):
            os.makedirs(DATA_PROCESADA_BANCA)

        files = [f for f in os.listdir(DATA_NUEVOS_BANCA) if (f.endswith(".xlsx") or f.endswith(".csv"))] 
        logger.debug("Files to process: %s", files)
        if not files:
            return {"status": "warning", "message": "No hay archivos .xlsx en data/nuevos/banca", "files_processed": 0}

        raw_items = []

        for file_name in files:
            file_path = os.path.join(DATA_NUEVOS_BANCA, file_name)
            try:
                if file_name.endswith(".csv"):
                    logger.info("Procesando CSV: %s", file_name)
                    config = FileProcessingConfig(path=file_path, tiene_monto=False, saldo_col="SALDO",fecha_col="FECHA", descripcion_col="DESCRIPCION")
                    logger.debug("Config para %s: %s", file_name, config)
                    df = read_csv_account(config)
                    logger.debug('DataFrame head: %s', df.head().to_string())
                else:
                    logger.info("Procesando Excel: %s", file_name)
                    config = FileProcessingConfig(path=file_path)
                    df = read_new_account(config)
                if not df.columns.is_unique:
                    logger.warning("Columnas duplicadas en %s", file_name)
                    duplicados = df.columns[df.columns.duplicated()].unique().tolist()
                    logger.warning("Columnas repetidas en %s: %s", file_name, duplicados)
                    logger.debug('DataFrame head (cols duplicadas): %s', df.head().to_string())
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
                         logger.warning("Skipping %s: DataFrame vacío", file_name)
                else:
                    logger.warning("Skipping %s: sin columna FECHA", file_name)
                    
            except Exception as e:
                logger.error("Error procesando %s: %s", file_name, e)
                continue

        logger.info("=== LIMPIEZA DE LÍMITES Y ORDENAMIENTO ===")
        cleaned_items = []
        for item in raw_items:
            df = item['df']
            start_d = item['start_date'].date()
            end_d = item['end_date'].date()
            
            # Quitar los días límites (basados en start_date y end_date obtenidos previamente)
            df_cleaned = df[(df['FECHA'].dt.date > start_d) & (df['FECHA'].dt.date < end_d)].copy()
            
            if not df_cleaned.empty:
                cleaned_items.append({
                    'file_name': item['file_name'],
                    'df': df_cleaned,
                    'start_date': df_cleaned['FECHA'].min(),
                    'end_date': df_cleaned['FECHA'].max()
                })
            else:
                logger.warning("Archivo %s quedó vacío al quitar los días límites", item['file_name'])

        if not cleaned_items:
            return {"status": "warning", "message": "No hay datos después de quitar los límites", "files_processed": 0}

        cleaned_items.sort(key=lambda x: x['end_date'], reverse=True)
        logger.debug('Archivos ordenados y limpios por novedad: %s', [(i['file_name'], i['start_date'], i['end_date']) for i in cleaned_items])

        logger.info("=== INICIO PROCESAMIENTO SECUENCIAL ===")
        base_df = cleaned_items[0]['df']
        final_dfs = [base_df]
        current_min_date = cleaned_items[0]['start_date'].date()
        
        logger.info('[1] ARCHIVO BASE: %s', cleaned_items[0]['file_name'])
        logger.debug('    Rango: %s - %s', cleaned_items[0]['start_date'], cleaned_items[0]['end_date'])
        logger.debug('    Umbral búsqueda inicial (fecha estricta): %s', current_min_date)

        for i in range(1, len(cleaned_items)):
            item = cleaned_items[i]
            df = item['df']
            file_name = item['file_name']
            
            logger.info('[%s] PROCESANDO HISTÓRICO: %s', i+1, file_name)
            
            # Cortar tomando información estrictamente anterior a la fecha mínima actual
            older_slice = df[df['FECHA'].dt.date < current_min_date].copy()
            
            if not older_slice.empty:
                rows_added = len(older_slice)
                is_descending = False
                if len(older_slice) > 1:
                    first_date = older_slice['FECHA'].iloc[0].date()
                    for j in range(1, len(older_slice)):
                        current_date = older_slice['FECHA'].iloc[j].date()
                        if current_date != first_date:
                            is_descending = first_date > current_date
                            break

                if not is_descending:
                    logger.debug('    -> Orden DESCENDENTE en %s. Invirtiendo...', file_name)
                    older_slice = older_slice[::-1].reset_index(drop=True)

                final_dfs.append(older_slice)
                
                new_min = older_slice['FECHA'].min().date()
                logger.info('    -> Agregadas %s filas de historia.', rows_added)
                logger.debug('    -> Nuevo punto de inicio histórico: %s', new_min)
                current_min_date = new_min
            else:
                logger.debug('    -> IGNORADO: sin datos anteriores a %s', current_min_date)

        logger.info("=== UNIFICACIÓN Y VERIFICACIÓN DE FLUJO ===")
        for i, df in enumerate(final_dfs):
            if not df.index.is_unique:
                logger.warning('DataFrame en pos %s tiene índices duplicados', i)
                logger.debug('Índices duplicados: %s', df.index[df.index.duplicated()].unique())
            else:
                logger.debug('DataFrame en pos %s: índices OK', i)
        for i, df in enumerate(final_dfs):
            if not df.columns.is_unique:
                logger.warning('DataFrame %s tiene columnas duplicadas', i)
                duplicados = df.columns[df.columns.duplicated()].unique().tolist()
                logger.warning('Columnas repetidas: %s', duplicados)
                logger.debug('DataFrame head (cols dup): %s', df.head().to_string())
        logger.info("Total fragmentos a unir: %s", len(final_dfs))
        df_unido = pd.concat(final_dfs, ignore_index=True)
        logger.info("Total filas unificadas: %s", len(df_unido))
        
        if not df_unido.empty and 'FECHA' in df_unido.columns:
            first_date = df_unido['FECHA'].iloc[0]
            last_date = df_unido['FECHA'].iloc[-1]
            logger.debug('Rango DF: %s - %s', first_date, last_date)
            
            if first_date > last_date:
                logger.debug("Orden inverso detectado. Invirtiendo para validación...")
                df_unido = df_unido[::-1].reset_index(drop=True)
                logger.debug('    DF invertido correctamente.')

        df_unido['FUENTE'] = 'BANCO'
        df_unido = add_id_column(df_unido, source_type='BANCO')

        validation_output = io.StringIO()
        with contextlib.redirect_stdout(validation_output):
            logger.debug("--- INICIO VALIDACIÓN DE SALDOS ---")
            try:
                valid_df = df_unido.copy().reset_index(drop=True)
                test_balance_validity(valid_df)
            except Exception as ve:
                logger.warning("Error durante validación: %s", ve)
            logger.debug("--- FIN VALIDACIÓN ---")
        
        validation_log = validation_output.getvalue()

        required_cols = ['id', 'FECHA', 'DESCRIPCION', 'MONTO', 'FUENTE', 'SALDO']
        final_cols = [col for col in required_cols if col in df_unido.columns]
        df_unido = df_unido[final_cols]

        output_file = PATH_BANCA_PROCESADA
        df_unido.to_excel(output_file, index=False)

        try:
            pipeline = get_pipeline()
            pipeline.get_bank_data(force_reload=True)
            logger.info("Pipeline actualizado con nuevos datos de banca")
        except Exception as e:
            logger.warning("Error actualizando pipeline: %s", e)

        chart_data = []
        min_date = None
        max_date = None
        
        if 'FECHA' in df_unido.columns and 'SALDO' in df_unido.columns:
            chart_df = df_unido[['FECHA', 'SALDO', 'MONTO']].copy()
            chart_df['FECHA'] = pd.to_datetime(chart_df['FECHA'])
            chart_df = chart_df.sort_values('FECHA')
            
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

    # =========================================================================
    # Métodos privados de procesamiento de tarjeta
    # =========================================================================

    def _process_card_xls(self, file_path: str, file_name: str) -> tuple[pd.DataFrame, dict]:
        """
        Lee un archivo .xls de tarjeta y retorna (df_movimientos, flat_meta).

        Formato estandarizado del df:
            FECHA, DESCRIPCION, MONTO, OPERACION (y otras cols del parser)

        Formato estandarizado de flat_meta:
            EMPRESA, NUM_TARJETA, FECHA_EMISION, FECHA_MAX_PAGO,
            saldo_anterior, subtotal_pagado, total_a_pagar, minimo_a_pagar,
            total_consumo, num_transacciones, fecha_min, fecha_max,
            total_mes, total_a_pagar_despues, source_file
        """
        logger.info("Procesando XLS de tarjeta: %s", file_name)
        df, metadata = get_credit_card_data_from_excel_v2(file_path)

        # El parser XLS puede devolver 'Valor' o 'VALOR'; normalizamos a 'MONTO'
        df.rename(columns={'VALOR': 'MONTO', 'Valor': 'MONTO'}, inplace=True)

        # Normalizar columnas con encoding latin1 roto (BeautifulSoup las lee mal)
        # Ej: 'DescripciÃ³n' -> 'DESCRIPCION', 'OperaciÃ³n' -> 'OPERACION'
        encoding_fixes = {}
        for col in df.columns:
            try:
                col_fixed = col.encode('latin1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                col_fixed = col
            col_upper = col_fixed.upper()
            if col_upper in ('DESCRIPCIÓN', 'DESCRIPCION') and col != 'DESCRIPCION':
                encoding_fixes[col] = 'DESCRIPCION'
            elif col_upper in ('OPERACIÓN', 'OPERACION') and col != 'OPERACION':
                encoding_fixes[col] = 'OPERACION'
            elif col_upper in ('PAÍS', 'PAIS') and col != 'PAIS':
                encoding_fixes[col] = 'PAIS'
        if encoding_fixes:
            df.rename(columns=encoding_fixes, inplace=True)
            logger.debug("Columnas renombradas por encoding: %s", encoding_fixes)

        monto_col = df['MONTO'] if 'MONTO' in df.columns else pd.Series(dtype=float)

        flat_meta = {
            'EMPRESA':             metadata.EMPRESA,
            'NUM_TARJETA':         metadata.NUM_TARJETA,
            'FECHA_EMISION':       metadata.FECHA_EMISION,
            'FECHA_MAX_PAGO':      metadata.FECHA_MAX_PAGO,
            'saldo_anterior':      metadata.SALDO_ANTERIOR,
            'subtotal_pagado':     metadata.SUBTOTAL_PAGADO,
            'total_a_pagar':       metadata.TOTAL_A_PAGAR,
            'minimo_a_pagar':      metadata.MINIMO_A_PAGAR,
            'total_consumo':       metadata.TOTAL_CONSUMO,
            'num_transacciones':   len(df),
            'fecha_min':           df['FECHA'].min() if not df.empty else None,
            'fecha_max':           df['FECHA'].max() if not df.empty else None,
            'total_mes':           monto_col.sum() if not monto_col.empty else 0,
            'total_a_pagar_despues': metadata.TOTAL_A_PAGAR + (monto_col.sum() if not monto_col.empty else 0),
            'source_file':         file_name,
        }

        return df, flat_meta


    def _process_card_pdf(self, file_path: str, file_name: str) -> tuple[pd.DataFrame, dict]:
        """
        Lee un archivo .pdf de estado de cuenta de tarjeta y retorna (df_movimientos, flat_meta)
        en el mismo formato estandarizado que _process_card_xls.

        get_credit_card_data_from_pdf ya construye el flat_meta y renombra columnas;
        este método solo delega y pasa el resultado.
        """
        from contabilidad.backend.services.credit_card.pdf_reader import get_credit_card_data_from_pdf

        logger.info("Procesando PDF de tarjeta: %s", file_name)
        df, flat_meta = get_credit_card_data_from_pdf(file_path)

        # Normalización defensiva: por si el PDF devuelve 'VALOR' sin renombrar
        df.rename(columns={'VALOR': 'MONTO', 'Valor': 'MONTO'}, inplace=True)

        return df, flat_meta

    def _process_single_card_file(self, file_path: str, file_name: str) -> tuple[pd.DataFrame, dict]:
        """
        Detecta el tipo de archivo (.xls / .pdf) y delega al parser correspondiente.
        Retorna (df, flat_meta) en formato estandarizado.
        """
        ext = os.path.splitext(file_name)[1].lower()
        logger.debug("Procesando archivo '%s' (ext: '%s')", file_name, ext)

        if ext == '.xls':
            return self._process_card_xls(file_path, file_name)
        elif ext == '.pdf':
            return self._process_card_pdf(file_path, file_name)
        else:
            raise ValueError(f"Tipo de archivo no soportado para tarjeta: '{ext}' ({file_name})")

    def _build_card_chart_data(self, df_unido: pd.DataFrame) -> tuple[list, str | None, str | None]:
        """
        Construye los datos de gráfico (gasto diario) a partir del df unificado.
        Retorna (chart_data, min_date_iso, max_date_iso).
        """
        if 'FECHA' not in df_unido.columns or 'MONTO' not in df_unido.columns:
            return [], None, None

        chart_df = df_unido[['FECHA', 'MONTO']].copy()
        chart_df['FECHA'] = pd.to_datetime(chart_df['FECHA'])
        chart_df = chart_df.sort_values('FECHA')
        chart_df['MONTO'] = chart_df['MONTO'].fillna(0)

        daily_spend = (
            chart_df.groupby(chart_df['FECHA'].dt.date)['MONTO']
            .sum()
            .reset_index()
        )
        daily_spend['FECHA'] = pd.to_datetime(daily_spend['FECHA'])

        chart_data = daily_spend.apply(lambda x: {
            'date':  x['FECHA'].strftime('%Y-%m-%d'),
            'monto': x['MONTO'],
            'saldo': 0,
        }, axis=1).tolist()

        min_date = chart_df['FECHA'].min().isoformat() if not chart_df.empty else None
        max_date = chart_df['FECHA'].max().isoformat() if not chart_df.empty else None

        return chart_data, min_date, max_date

    # =========================================================================
    # Método público principal
    # =========================================================================

    def process_card_data(self) -> dict:
        # --- Validación de directorios ---
        if not os.path.exists(DATA_NUEVOS_TARJETA):
            raise ValueError(f"Directorio no encontrado: {DATA_NUEVOS_TARJETA}")

        if not os.path.exists(DATA_PROCESADA_TARJETA):
            os.makedirs(DATA_PROCESADA_TARJETA)

        # --- Listado de archivos soportados ---
        SUPPORTED_EXTENSIONS = ('.xls', '.pdf')
        files = [
            f for f in os.listdir(DATA_NUEVOS_TARJETA)
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
        ]
        logger.debug("Archivos de tarjeta encontrados: %s", files)

        if not files:
            return {
                "status": "warning",
                "message": "No hay archivos .xls ni .pdf en data/nuevos/tarjeta",
                "files_processed": 0,
            }

        # --- Procesamiento individual de cada archivo ---
        dfs: list[pd.DataFrame] = []
        mds: list[dict] = []
        processed_files: list[str] = []

        for file_name in files:
            file_path = os.path.join(DATA_NUEVOS_TARJETA, file_name)
            try:
                df, flat_meta = self._process_single_card_file(file_path, file_name)
                
                # --- VERIFICACIÓN DE INTEGRIDAD ---
                monto_total_df = df['MONTO'].sum() if 'MONTO' in df.columns else 0.0
                num_transacciones_df = len(df)
                
                # Para la validación:
                # La suma de los movimientos, mas el saldo anterior - el subtotal_pagado 
                # Con el total_a_pagar
                saldo_anterior_meta = flat_meta.get('saldo_anterior', 0.0)
                subtotal_pagado_meta = flat_meta.get('subtotal_pagado', 0.0)
                total_a_pagar_meta = flat_meta.get('total_a_pagar', 0.0)
                num_transacciones_meta = flat_meta.get('num_transacciones', 0)
                
                monto_calculado = monto_total_df + saldo_anterior_meta - subtotal_pagado_meta
                
                # Tolerancia para diferencias de redondeo (1 centavo)
                monto_coincide = abs(monto_calculado - total_a_pagar_meta) <= 0.01
                transacciones_coincide = (num_transacciones_df == num_transacciones_meta)
                
                flat_meta['verificacion_monto_ok'] = monto_coincide
                flat_meta['verificacion_transacciones_ok'] = transacciones_coincide

                # Log "en grande" de la verificación
                status_monto = "✅ OK" if monto_coincide else "❌ ERROR"
                status_trans = "✅ OK" if transacciones_coincide else "❌ ERROR"

                verification_summary = (
                    f"\n{'#'*60}\n"
                    f"### VERIFICACIÓN DE {file_name} ###\n"
                    f"{status_monto}  MONTO:\n"
                    f"    CALCULADO (Movs + SaldoAnt - Pagos): {monto_calculado:>10.2f}\n"
                    f"    ESPERADO  (Total a Pagar):           {total_a_pagar_meta:>10.2f}\n"
                    f"    DIFERENCIA:                          {abs(monto_calculado - total_a_pagar_meta):>10.2f}\n"
                    f"{'-'*30}\n"
                    f"{status_trans}  TRANSACCIONES:\n"
                    f"    EN DATAFRAME:                        {num_transacciones_df:>10}\n"
                    f"    EN METADATA:                         {num_transacciones_meta:>10}\n"
                    f"{'#'*60}"
                )
                
                if not monto_coincide or not transacciones_coincide:
                    logger.warning(verification_summary)
                else:
                    logger.info(verification_summary)
                # ----------------------------------

                logger.info("Procesado %s: %s filas", file_name, len(df))
                
                formatted_meta = "\n".join(f"  - {k:<25}: {v}" for k, v in flat_meta.items())
                logger.info("Metadata de %s:\n%s", file_name, formatted_meta)
                
                logger.info("Primeras transacciones de %s:\n%s", file_name, df.head(10).to_string(index=False))
                dfs.append(df)
                mds.append(flat_meta)
                processed_files.append(file_name)
            except Exception as e:
                import traceback
                logger.error("Error procesando %s: %s\n%s", file_name, e, traceback.format_exc())
                continue

        if not dfs:
            raise ValueError("No se pudo procesar ningún archivo correctamente.")

        # --- Unificación y normalización ---
        logger.debug("Unificando DataFrames...")
        # logger.info(dfs)
        df_unido = pd.concat(dfs, ignore_index=True)
        logger.info(df_unido.head(10)["FECHA"])
        df_unido['FUENTE'] = 'TARJETA'
        df_unido = add_id_column(df_unido, source_type='TARJETA')

        if 'FECHA' in df_unido.columns:
            df_unido['FECHA'] = pd.to_datetime(df_unido['FECHA'])
            df_unido.sort_values(by='FECHA', inplace=True)

        required_cols = ['id', 'FECHA', 'DESCRIPCION', 'MONTO', 'FUENTE', 'OPERACION']
        final_cols = [col for col in required_cols if col in df_unido.columns]
        df_unido = df_unido[final_cols]

        # --- Persistencia: movimientos ---
        output_file = os.path.join(DATA_PROCESADA_TARJETA, "tarjeta_unida.xlsx")
        df_unido.to_excel(output_file, index=False)
        logger.info("Movimientos guardados en %s", output_file)

        # --- Persistencia: metadata ---
        if mds:
            df_metadata = pd.DataFrame(mds)
            if 'FECHA_EMISION' in df_metadata.columns:
                df_metadata['FECHA_EMISION'] = pd.to_datetime(df_metadata['FECHA_EMISION'])
                df_metadata.sort_values(by='FECHA_EMISION', inplace=True)
            df_metadata.to_excel(PATH_TARJETA_METADATA_UNIDA, index=False)
            logger.info("Metadata guardada en %s", PATH_TARJETA_METADATA_UNIDA)

        # --- Actualización del pipeline ---
        try:
            pipeline = get_pipeline()
            if hasattr(pipeline, 'get_unified_credit_card_data'):
                pipeline.get_unified_credit_card_data(force_reload=True)
                logger.info("Pipeline actualizado con nuevos datos de tarjeta unida")
        except Exception as e:
            logger.warning("Error actualizando pipeline: %s", e)

        # --- Datos de gráfico ---
        chart_data, min_date, max_date = self._build_card_chart_data(df_unido)

        return {
            "status": "success",
            "message": f"Se procesaron {len(dfs)} archivos y se guardó en {output_file}",
            "files_processed": processed_files,
            "total_rows": len(df_unido),
            "chart_data": chart_data,
            "date_range": {
                "min": min_date,
                "max": max_date,
            },
        }
