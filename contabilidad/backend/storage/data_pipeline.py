"""
Sistema de Pipeline de Datos con Caché
======================================

Este módulo provee la instancia global del pipeline de datos de contabilidad,
orquestando cachés y transformaciones.
"""

import pandas as pd
import os
from typing import Optional, Dict, Any, List

from contabilidad.backend.logger import get_logger
from contabilidad.backend.storage.cache import DataCache
from contabilidad.backend.storage.pipeline_engine import TransformationPipeline

logger = get_logger(__name__)

class DataPipeline:
    """
    Pipeline principal para datos de contabilidad.
    Combina caché de datos fuente + transformaciones.
    """
    
    def __init__(self):
        self.source_cache = DataCache(ttl_seconds=300)  # 5 min para datos fuente
        self.pipeline = TransformationPipeline(name="contabilidad")
        self._setup_default_transformations()
    
    def _setup_default_transformations(self):
        """Configura las transformaciones por defecto."""
        from contabilidad.backend.storage.transformations.investments import transform_investments
        from contabilidad.backend.storage.transformations.credit_cards import transform_credit_cards
        from contabilidad.backend.storage.transformations.dashboard_transforms import transform_virtual_items, transform_metrics
        
        self.add_transformation('inversiones', transform_investments, cacheable=True)
        self.add_transformation('tarjetas', transform_credit_cards, cacheable=True)
        self.add_transformation('virtual_items', transform_virtual_items, cacheable=True)
        self.add_transformation('dashboard_metrics', transform_metrics, cacheable=True)

    def get_account_data(self, force_reload: bool = False) -> pd.DataFrame:
        from contabilidad.config import PATH_BANCA_PROCESADA
        
        if not force_reload:
            cached = self.source_cache.get('cuenta_data', PATH_BANCA_PROCESADA)
            if cached is not None:
                logger.debug("Cache hit: cuenta_data")
                return cached
        
        logger.info("Loading cuenta_data from Unified Banca Source")
        df = self.get_bank_data(force_reload)
        
        if 'MONTO' in df.columns:
            df['DEBITO'] = df['MONTO'].apply(lambda x: -x if x < 0 else 0.0)
            df['CREDITO'] = df['MONTO'].apply(lambda x: x if x > 0 else 0.0)
            
        if 'SALDO' not in df.columns and 'MONTO' in df.columns:
             df['SALDO'] = df['MONTO'].cumsum()
        
        try:
            from contabilidad.backend.storage.schemas import BancaSchema
            df = BancaSchema.validate(df)
        except Exception as e:
            logger.warning(f"Banca validation warnings/errors: {e}")
             
        self.source_cache.set('cuenta_data', df, PATH_BANCA_PROCESADA)
        return df
    
    def get_debt_data(self, force_reload: bool = False) -> pd.DataFrame:
        if not force_reload:
            cached = self.source_cache.get('deuda_data', None)
            if cached is not None:
                logger.debug("Cache hit: deuda_data")
                return cached
        
        logger.info("Loading deuda_data from Supabase")
        try:
            from contabilidad.debts.reading import obtener_deudas_para_analisis, obtener_todos_pagos
            
            df_debts = obtener_deudas_para_analisis(solo_pendientes=False)
            df_payments = obtener_todos_pagos()
            
            events = []
            if not df_debts.empty:
                for _, row in df_debts.iterrows():
                    try:
                        amount = float(row['MONTO'])
                    except:
                        amount = 0.0
                    if pd.notnull(row['FECHA']):
                        events.append({'FECHA': row['FECHA'], 'CHANGE': amount})
            
            if not df_payments.empty:
                for _, row in df_payments.iterrows():
                    try:
                        amount = float(row['monto_total'])
                    except:
                        amount = 0.0
                    if pd.notnull(row['fecha_pago']):
                         events.append({'FECHA': row['fecha_pago'], 'CHANGE': -amount})
            
            if not events:
                df = pd.DataFrame(columns=['FECHA', 'DEUDA_ACUMULADA'])
            else:
                df_events = pd.DataFrame(events)
                df_events['FECHA'] = pd.to_datetime(df_events['FECHA']).dt.normalize()
                df_daily = df_events.groupby('FECHA')['CHANGE'].sum().reset_index()
                df_daily = df_daily.sort_values('FECHA')
                df_daily['DEUDA_ACUMULADA'] = df_daily['CHANGE'].cumsum()
                df = df_daily[['FECHA', 'DEUDA_ACUMULADA']]
                
            from contabilidad.backend.storage.schemas import DeudaSchema
            df = DeudaSchema.validate(df)
        except ImportError:
            logger.warning("Supabase Debt integration not available")
            df = pd.DataFrame(columns=['FECHA', 'DEUDA_ACUMULADA'])
        except Exception as e:
            logger.error(f"Error fetching supabase debt data: {e}", exc_info=True)
            df = pd.DataFrame(columns=['FECHA', 'DEUDA_ACUMULADA'])
            
        self.source_cache.set('deuda_data', df, None)
        return df

    def get_credit_card_data(self, force_reload: bool = False) -> pd.DataFrame:
        from contabilidad.config import PATH_TARJETA_UNIDA
        
        if not force_reload:
            cached = self.source_cache.get('tarjeta_data', PATH_TARJETA_UNIDA)
            if cached is not None:
                logger.debug("Cache hit: tarjeta_data")
                return cached
        
        logger.info("Loading tarjeta_data from Unified Tarjeta Source")
        df = self.get_unified_credit_card_data(force_reload)
        
        if 'MONTO' in df.columns and 'VALOR' not in df.columns:
             df['VALOR'] = df['MONTO']
        
        if 'MONTO' in df.columns:
             df['MONTO'] = -df['MONTO']
             
        try:
            from contabilidad.backend.storage.schemas import TarjetaSchema
            df = TarjetaSchema.validate(df)
        except Exception as e:
            logger.warning(f"Tarjeta validation warnings/errors: {e}")
             
        self.source_cache.set('tarjeta_data', df, PATH_TARJETA_UNIDA)
        return df

    def get_unified_credit_card_data(self, force_reload: bool = False) -> pd.DataFrame:
        from contabilidad.config import PATH_TARJETA_UNIDA
        
        if not force_reload:
            cached = self.source_cache.get('tarjeta_unida_data', PATH_TARJETA_UNIDA)
            if cached is not None:
                logger.debug("Cache hit: tarjeta_unida_data")
                return cached
        
        logger.info("Loading tarjeta_unida_data from XLSX")
        if not os.path.exists(PATH_TARJETA_UNIDA):
            logger.warning("Archivo no encontrado: %s", PATH_TARJETA_UNIDA)
            return pd.DataFrame()
            
        df = pd.read_excel(PATH_TARJETA_UNIDA)
        
        if not df.empty and 'FECHA' in df.columns:
             logger.debug("Loaded Tarjeta %s, range: %s - %s", df.shape, df['FECHA'].min(), df['FECHA'].max())

        self.source_cache.set('tarjeta_unida_data', df, PATH_TARJETA_UNIDA)
        return df

    def get_bank_data(self, force_reload: bool = False) -> pd.DataFrame:
        from contabilidad.config import PATH_BANCA_PROCESADA
        
        if not force_reload:
            cached = self.source_cache.get('banca_data', PATH_BANCA_PROCESADA)
            if cached is not None:
                logger.debug("Cache hit: banca_data")
                return cached
        
        logger.info("Loading banca_data from XLSX")
        if not os.path.exists(PATH_BANCA_PROCESADA):
            logger.warning("Archivo no encontrado: %s", PATH_BANCA_PROCESADA)
            return pd.DataFrame()
            
        df = pd.read_excel(PATH_BANCA_PROCESADA)
        if not df.empty and 'FECHA' in df.columns:
            logger.debug("Loaded Banca %s, range: %s - %s", df.shape, df['FECHA'].min(), df['FECHA'].max())
        
        self.source_cache.set('banca_data', df, PATH_BANCA_PROCESADA)
        return df

    def get_credit_card_metadata(self, force_reload: bool = False) -> pd.DataFrame:
        from contabilidad.config import PATH_TARJETA_PROCESADA
        
        if not force_reload:
            cached = self.source_cache.get('tarjeta_metadata', None)
            if cached is not None:
                logger.debug("Cache hit: tarjeta_metadata")
                return cached
        
        logger.info("Loading tarjeta_metadata from Excel files")
        try:
            from contabilidad.backend.services.credit_card.Lectura import leer_tarjetas
            df_resumen, _ = leer_tarjetas(PATH_TARJETA_PROCESADA)
        except Exception as e:
            logger.warning("Error leyendo metadatos de tarjeta: %s", e)
            df_resumen = pd.DataFrame()
            
        self.source_cache.set('tarjeta_metadata', df_resumen, None)
        return df_resumen
    
    def add_transformation(
        self, 
        name: str, 
        func: callable,
        cacheable: bool = True,
        dependencies: Optional[list] = None
    ):
        self.pipeline.add_transformation(name, func, cacheable, dependencies)
    
    def get_raw_data(
        self,
        source: str,
        force_reload: bool = False
    ) -> pd.DataFrame:
        """Obtiene los datos en crudo sin aplicar transformaciones del pipeline."""
        if source == 'cuenta':
            return self.get_account_data(force_reload)
        elif source == 'tarjeta':
            return self.get_credit_card_data(force_reload)
        elif source == 'banca':
            return self.get_bank_data(force_reload)
        elif source == 'tarjeta_unida':
            return self.get_unified_credit_card_data(force_reload)
        elif source == 'debt':
            return self.get_debt_data(force_reload)
        elif source == 'all':
            df_cuenta = self.get_account_data(force_reload).copy()
            df_tarjeta = self.get_credit_card_data(force_reload).copy()
            df_debt = self.get_debt_data(force_reload).copy()
            
            frames = [f for f in [df_cuenta, df_tarjeta, df_debt] if not f.empty]
            
            if not frames:
                return pd.DataFrame()
            elif len(frames) == 1:
                return frames[0]
            else:
                return pd.concat(frames, ignore_index=True).sort_values('FECHA')
        else:
            raise ValueError(f"Source inválido: {source}")
            
    def get_processed_data(
        self, 
        source: str = 'all',
        force_reload: bool = False,
        skip_transform_cache: bool = False,
        run_only: Optional[List[str]] = None
    ) -> pd.DataFrame:
        if source == 'all':

            df_debt = self.get_processed_data('debt', force_reload, skip_transform_cache)
            df_cuenta = self.get_processed_data('cuenta', force_reload, skip_transform_cache)
            df_tarjeta = self.get_processed_data('tarjeta', force_reload, skip_transform_cache)
            
            frames = [f for f in [df_cuenta, df_tarjeta, df_debt] if not f.empty]
            if not frames:
                return pd.DataFrame()
            elif len(frames) == 1:
                df = frames[0]
            else:
                df = pd.concat(frames, ignore_index=True).sort_values('FECHA')
                ffill_cols = [c for c in ['SALDO',  'ACUMULADO_TARJETA', 'DEUDA_ACUMULADA'] if c in df.columns]
                df[ffill_cols] = df[ffill_cols].ffill().fillna(0)
                
            transforms_to_run = run_only
            if transforms_to_run is None:
                transforms_to_run = [t['name'] for t in self.pipeline.transformations]
                
            remaining_transforms = [t for t in transforms_to_run if t in ['virtual_items', 'dashboard_metrics']]
            if remaining_transforms and not df.empty:
                df = self.pipeline.execute(
                    df, 
                    skip_cache=skip_transform_cache,
                    run_only=remaining_transforms
                )
            return df
            
        df = self.get_raw_data(source, force_reload)
        
        # Definir transformaciones por defecto si no nos dicen cuáles correr
        transforms_to_run = run_only
        if transforms_to_run is None:
            if source in ['cuenta', 'banca']:
                transforms_to_run = ['inversiones']
            elif source in ['tarjeta', 'tarjeta_unida']:
                transforms_to_run = ['tarjetas']
            else:
                transforms_to_run = []
                
        if self.pipeline.transformations and not df.empty and transforms_to_run:
            df = self.pipeline.execute(
                df, 
                skip_cache=skip_transform_cache,
                run_only=transforms_to_run
            )
        
        return df

    def get_daily_data(
        self,
        source: str = 'all',
        force_reload: bool = False
    ) -> pd.DataFrame:
        """
        Obtiene los datos procesados resumiéndolos a un registro único por día.
        La lógica de agrupación depende de la fuente.
        """
        df = self.get_processed_data(source, force_reload)
        if df.empty or 'FECHA' not in df.columns:
            return df
            
        df['FECHA'] = pd.to_datetime(df['FECHA']).dt.normalize()
        
        if source in ['cuenta', 'banca']:
            # Cuenta bancaria: el saldo debe reflejar el del final del día ('last') 
            # y los ingresos o egresos se suman.
            agg_dict = {}
            if 'SALDO' in df.columns: agg_dict['SALDO'] = 'last'
            if 'MONTO' in df.columns: agg_dict['MONTO'] = 'sum'
            if 'DEBITO' in df.columns: agg_dict['DEBITO'] = 'sum'
            if 'CREDITO' in df.columns: agg_dict['CREDITO'] = 'sum'
            
            df_daily = df.groupby('FECHA').agg(agg_dict).reset_index()
            return df_daily
            
        elif source in ['tarjeta', 'tarjeta_unida']:
            # Tarjeta de crédito: el acumulado de deuda es el estado actual ('last')
            # y los consumos netos en el día se suman.
            agg_dict = {}
            if 'TARJETA' in df.columns: agg_dict['TARJETA'] = 'last'
            if 'ACUMULADO_TARJETA' in df.columns: agg_dict['ACUMULADO_TARJETA'] = 'last'
            # PAGO_TARJETA es una columna de pagos acumulados del ciclo actual. Debe extraerse con last, no sum!
            if 'PAGO_TARJETA' in df.columns: agg_dict['PAGO_TARJETA'] = 'last'
            if 'MONTO' in df.columns: agg_dict['MONTO'] = 'sum'
                
            df_daily = df.groupby('FECHA').agg(agg_dict).reset_index()
            return df_daily
            
        elif source == 'debt':
            if 'DEUDA_ACUMULADA' in df.columns:
                df_daily = df.groupby('FECHA').agg({'DEUDA_ACUMULADA': 'last'}).reset_index()
            else:
                df_daily = pd.DataFrame(columns=['FECHA', 'DEUDA_ACUMULADA'])
            return df_daily
            
        elif source == 'all':
            df_cuenta = self.get_daily_data('cuenta', force_reload)
            df_tarjeta = self.get_daily_data('tarjeta', force_reload)
            df_debt = self.get_daily_data('debt', force_reload)
            
            frames = [f for f in [df_cuenta, df_tarjeta, df_debt] if not f.empty]
            if not frames: return pd.DataFrame()
            if len(frames) == 1: return frames[0]
            
            min_date = min(f['FECHA'].min() for f in frames)
            max_date = max(f['FECHA'].max() for f in frames)
            
            all_dates = pd.date_range(start=min_date, end=max_date, freq='D')
            df_all = pd.DataFrame({'FECHA': all_dates})
            
            if not df_cuenta.empty:
                df_all = df_all.merge(df_cuenta, on='FECHA', how='left')
            if not df_tarjeta.empty:
                df_all = df_all.merge(df_tarjeta, on='FECHA', how='left', suffixes=('', '_TARJETA'))
            if not df_debt.empty:
                df_all = df_all.merge(df_debt, on='FECHA', how='left', suffixes=('', '_DEUDA'))
            
            # Forward fill a los balances para llenar vacíos de los días inertes
            ffill_cols = [c for c in ['SALDO', 'TARJETA', 'ACUMULADO_TARJETA', 'DEUDA_ACUMULADA'] if c in df_all.columns]
            df_all[ffill_cols] = df_all[ffill_cols].ffill().fillna(0)
            
            # Reponer nulos de sumas diarias a 0
            df_all.fillna(0, inplace=True)
            
            try:
                from contabilidad.backend.storage.schemas import DailyUnifiedSchema
                df_all = DailyUnifiedSchema.validate(df_all)
            except Exception as e:
                logger.warning(f"Daily Unified Validation warnings/errors: {e}")
            
            return df_all
        
        else:
            raise ValueError(f"Source inválido: {source}")
    
    def invalidate_cache(self, scope: str = 'all'):
        if scope in ['all', 'source']:
            self.source_cache.invalidate()
        if scope in ['all', 'transformations']:
            self.pipeline.clear_cache()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        return {
            'source_cache': self.source_cache.get_stats(),
            'transformation_cache': self.pipeline.cache.get_stats(),
            'transformations_registered': len(self.pipeline.transformations)
        }

_global_pipeline: Optional[DataPipeline] = None

def get_pipeline() -> DataPipeline:
    global _global_pipeline
    if _global_pipeline is None:
        _global_pipeline = DataPipeline()
    return _global_pipeline

def reset_pipeline():
    global _global_pipeline
    _global_pipeline = None
