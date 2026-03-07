"""
Sistema de Pipeline de Datos con Caché
======================================

Este módulo implementa:
1. Caché en memoria para datos de cuenta/tarjeta
2. Pipeline de transformaciones secuenciales
3. Invalidación inteligente de caché
4. Sistema de transformaciones composables

Uso:
    pipeline = DataPipeline()
    df = pipeline.get_processed_data()
"""

import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Optional, Callable, List, Dict, Any
from functools import wraps
import hashlib
import json


class DataCache:
    """
    Caché en memoria con TTL (Time To Live) y detección de cambios en archivos.
    """
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minutos por defecto
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds
    
    def _get_file_hash(self, file_path: str) -> str:
        """Genera hash del archivo para detectar cambios."""
        if not os.path.exists(file_path):
            return ""
        
        # Usar timestamp de modificación + tamaño como hash rápido
        stat = os.stat(file_path)
        return f"{stat.st_mtime}_{stat.st_size}"
    
    def get(self, key: str, file_path: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Obtiene datos del caché si están vigentes.
        
        Args:
            key: Identificador único del caché
            file_path: Ruta del archivo fuente (para detectar cambios)
        
        Returns:
            DataFrame si está en caché y vigente, None si no
        """
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        
        # Verificar TTL
        if datetime.now() > entry['expires_at']:
            del self.cache[key]
            return None
        
        # Verificar si el archivo cambió
        if file_path:
            current_hash = self._get_file_hash(file_path)
            if current_hash != entry.get('file_hash', ''):
                del self.cache[key]
                return None
        
        return entry['data'].copy()  # Retornar copia para evitar mutaciones
    
    def set(self, key: str, data: pd.DataFrame, file_path: Optional[str] = None):
        """
        Guarda datos en caché.
        
        Args:
            key: Identificador único
            data: DataFrame a cachear
            file_path: Ruta del archivo fuente
        """
        self.cache[key] = {
            'data': data.copy(),
            'cached_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(seconds=self.ttl_seconds),
            'file_hash': self._get_file_hash(file_path) if file_path else None
        }
    
    def invalidate(self, key: Optional[str] = None):
        """
        Invalida caché.
        
        Args:
            key: Si se especifica, invalida solo esa entrada. Si es None, limpia todo.
        """
        if key:
            self.cache.pop(key, None)
        else:
            self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del caché."""
        return {
            'entries': len(self.cache),
            'keys': list(self.cache.keys()),
            'total_memory_mb': sum(
                entry['data'].memory_usage(deep=True).sum() / 1024 / 1024
                for entry in self.cache.values()
            )
        }


class TransformationPipeline:
    """
    Pipeline de transformaciones que se aplican secuencialmente a un DataFrame.
    Cada transformación puede tener caché individual.
    """
    
    def __init__(self, name: str = "default"):
        self.name = name
        self.transformations: List[Dict[str, Any]] = []
        self.cache = DataCache(ttl_seconds=600)  # 10 minutos para transformaciones
    
    def add_transformation(
        self, 
        name: str, 
        func: Callable[[pd.DataFrame], pd.DataFrame],
        cacheable: bool = True,
        dependencies: Optional[List[str]] = None
    ):
        """
        Agrega una transformación al pipeline.
        
        Args:
            name: Nombre único de la transformación
            func: Función que recibe y retorna DataFrame
            cacheable: Si True, cachea el resultado de esta transformación
            dependencies: Lista de nombres de transformaciones que deben ejecutarse antes
        """
        self.transformations.append({
            'name': name,
            'func': func,
            'cacheable': cacheable,
            'dependencies': dependencies or []
        })
    
    def _get_transformation_hash(self, df: pd.DataFrame, transform_name: str) -> str:
        """Genera hash único para el estado del DataFrame + transformación."""
        # Usar shape + primeras/últimas filas como fingerprint
        fingerprint = {
            'shape': tuple(int(x) for x in df.shape),
            'columns': list(df.columns),
            'first_hash': str(pd.util.hash_pandas_object(df.head(5)).sum()),
            'last_hash': str(pd.util.hash_pandas_object(df.tail(5)).sum()),
            'transform': transform_name
        }
        return hashlib.md5(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
    
    def execute(self, df: pd.DataFrame, skip_cache: bool = False) -> pd.DataFrame:
        """
        Ejecuta el pipeline completo.
        
        Args:
            df: DataFrame inicial
            skip_cache: Si True, ignora caché y recalcula todo
        
        Returns:
            DataFrame transformado
        """
        result = df.copy()
        
        for transform in self.transformations:
            transform_name = transform['name']
            
            # Generar key de caché única para esta transformación + estado del df
            cache_key = f"{self.name}_{transform_name}_{self._get_transformation_hash(result, transform_name)}"
            
            # Intentar obtener del caché
            if transform['cacheable'] and not skip_cache:
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    print(f"✓ Cache hit: {transform_name}")
                    result = cached_result
                    continue
            
            # Ejecutar transformación
            print(f"⚙ Executing: {transform_name}")
            result = transform['func'](result)
            
            # Cachear resultado
            if transform['cacheable']:
                self.cache.set(cache_key, result)
        
        return result
    
    def invalidate_from(self, transformation_name: str):
        """Invalida caché desde una transformación en adelante."""
        # Encontrar índice de la transformación
        idx = next(
            (i for i, t in enumerate(self.transformations) if t['name'] == transformation_name),
            None
        )
        
        if idx is not None:
            # Invalidar todas las transformaciones desde ese punto
            for transform in self.transformations[idx:]:
                # Invalidar todas las entradas que contengan el nombre de la transformación
                keys_to_invalidate = [
                    key for key in self.cache.cache.keys() 
                    if transform['name'] in key
                ]
                for key in keys_to_invalidate:
                    self.cache.invalidate(key)
    
    def clear_cache(self):
        """Limpia todo el caché del pipeline."""
        self.cache.invalidate()


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
        
        # 1. Transformación de Inversiones
        def transform_inversiones(df: pd.DataFrame) -> pd.DataFrame:
            try:
                # Importar dependencias dinámicamente para evitar ciclos
                try:
                    from .storage import InterpolationStorage
                except ImportError:
                    from storage import InterpolationStorage
                    
                from contabilidad.cuenta.ObtenerVariables import marcar_fijos
                from contabilidad.Modelos import PAGO
                
                # Obtener pagos fijos de inversiones
                groups = InterpolationStorage.get_groups(type_filter=None)
                all_payments = []
                for group in groups:
                    group_payments = InterpolationStorage.get_payments(group['id'])
                    all_payments.extend(group_payments)
                
                pagos = []
                for payment in all_payments:
                    start_date = pd.to_datetime(payment['start_date']) if payment['start_date'] else None
                    end_date = pd.to_datetime(payment['end_date']) if payment['end_date'] else None
                    
                    pago_obj = PAGO(
                        monto=float(payment['amount']),
                        inicio=start_date,
                        fin=end_date
                    )
                    pagos.append(pago_obj)
                
                # Aplicar marcar_fijos
                if pagos:
                    df = marcar_fijos(df, pagos, 'INVERSION', incluir_ultimo=False)
                else:
                    df['INVERSION'] = 0.0
                    
                return df
            except Exception as e:
                print(f"⚠ Error en transform_inversiones: {e}")
                # En caso de error, devolver df sin modificar o con col 0
                if 'INVERSION' not in df.columns:
                    df['INVERSION'] = 0.0
                return df

        self.add_transformation('inversiones', transform_inversiones, cacheable=True)

        # 2. Transformación de Tarjetas
        def transform_tarjetas(df: pd.DataFrame) -> pd.DataFrame:
            try:
                from contabilidad.cuenta.ObtenerVariables import obtener_pagos_tarjetas, marcar_fijos
                
                # --- PREPARACIÓN ---
                # Obtener pagos de tarjetas (desde df cuenta)
                pagos_tarjeta = obtener_pagos_tarjetas(df)
                min_banca_date = df["FECHA"].min() if not df.empty else None
                
                # Obtener metadatos de tarjeta
                try:
                    df_metadata = self.get_tarjeta_metadata()
                    # Mapeo de columnas para metadata
                    try:
                        from contabilidad.tarjeta.tiposCsvDatos import MAPEO_COLUMNAS
                        col_fecha_emision = MAPEO_COLUMNAS.get("FECHA_EMISION", "FECHA_EMISION")
                        col_total_pagar = MAPEO_COLUMNAS.get("TOTAL_A_PAGAR", "TOTAL_A_PAGAR")
                        col_fecha_max_pago = MAPEO_COLUMNAS.get("FECHA_MAX_PAGO", "FECHA_MAX_PAGO")
                    except ImportError:
                        col_fecha_emision = "FECHA_EMISION"
                        col_total_pagar = "TOTAL_A_PAGAR"
                        col_fecha_max_pago = "FECHA_MAX_PAGO"

                    # Asegurar tipos y orden
                    if not df_metadata.empty:
                        df_metadata[col_fecha_emision] = pd.to_datetime(df_metadata[col_fecha_emision])
                        df_metadata[col_fecha_max_pago] = pd.to_datetime(df_metadata[col_fecha_max_pago])
                        df_metadata = df_metadata.sort_values(col_fecha_emision)
                except Exception as e:
                    print(f"⚠ Error obteniendo metadata tarjeta: {e}")
                    df_metadata = pd.DataFrame()

                # Obtener datos de consumos de tarjeta
                try:
                    df_consumos = self.get_tarjeta_unida_data()
                    col_consumo_fecha = "FECHA_EMISION" # Asumimos nombres estándar o mapeados
                    col_consumo_valor = "TOTAL_CONSUMO"
                    
                    try:
                        from contabilidad.tarjeta.tiposCsvDatos import MAPEO_COLUMNAS
                        col_consumo_fecha = MAPEO_COLUMNAS.get("FECHA_EMISION", "FECHA_EMISION")
                        col_consumo_valor = MAPEO_COLUMNAS.get("TOTAL_CONSUMO", "TOTAL_CONSUMO")
                    except ImportError:
                        pass
                        
                    # Fallback columnas consumos
                    if col_consumo_valor not in df_consumos.columns:
                         col_consumo_valor = "VALOR" if "VALOR" in df_consumos.columns else "MONTO"
                    if col_consumo_fecha not in df_consumos.columns:
                         col_consumo_fecha = "FECHA"

                    if not df_consumos.empty:
                        df_consumos[col_consumo_fecha] = pd.to_datetime(df_consumos[col_consumo_fecha])
                except Exception as e:
                    print(f"⚠ Error obteniendo consumos tarjeta: {e}")
                    df_consumos = pd.DataFrame()

                # Verificar si tenemos datos suficientes
                if df.empty or df_metadata.empty or df_consumos.empty:
                    print("⚠ Datos insuficientes para cálculo avanzado de tarjeta. Usando defaults.")
                    # Default calc
                    pagos_filtrados = [p for p in pagos_tarjeta if p.inicio and pd.to_datetime(p.inicio) >= min_banca_date]
                    df = marcar_fijos(df, pagos_filtrados, "PAGO_TARJETA", incluir_ultimo=True)
                    df["PAGO_TARJETA"] = df["PAGO_TARJETA"].fillna(0)
                    df['ACUMULADO_TARJETA'] = 0.0
                    df['TARJETA'] = -df["PAGO_TARJETA"]
                    return df

                min_meta_date = df_metadata[col_fecha_emision].min()
                
                # Variables para el anclaje
                start_date = None
                initial_balance = 0.0
                
                # --- LÓGICA DE DECISIÓN ---
                # "metada es mas antigua que banca"
                is_metadata_older = min_meta_date < min_banca_date

                if not is_metadata_older:
                    # CASE NO: Metadata >= Bank
                    # "La tarjeta empieza desde fecha de emision y se agrega el monto a pagar"
                    # En realidad el usuario dijo: "el primer valor de tarjeta va a empezar en fecha emision por lo que va a ser 0"
                    # Pero también dijo "y se agrega el monto a pagar" en el diagrama?
                    # Corrección usuario: "En caseNo, no debes calcular ninguna valor, ya que el primer valor de tarjeta va a empezar en fecha emision por lo que va a ser 0"
                    
                    # Usamos el primer metadata disponible
                    first_meta = df_metadata.iloc[0]
                    start_date = first_meta[col_fecha_emision]
                    initial_balance = 0.0 # Segun instruccion usuario: "va a ser 0"
                    
                    print(f"ℹ LOGIC: Metadata >= Bank. Start Date: {start_date}, Init Bal: {initial_balance}")
                    
                else:
                    # CASE YES: Metadata < Bank
                    # "Ver primer pago fecha y monto" --> Encontrar primer pago en banca
                    # "Ver metada de tarjeta que la fecha sea mayor que la de emision y menor que la fecha max pago"
                    
                    # Filtrar pagos dentro del rango de banca
                    pagos_en_banca = [p for p in pagos_tarjeta if p.inicio and pd.to_datetime(p.inicio) >= min_banca_date]
                    pagos_en_banca.sort(key=lambda x: pd.to_datetime(x.inicio))
                    
                    if not pagos_en_banca:
                        print("⚠ No se encontraron pagos en banca para anclar. Usando default.")
                        start_date = min_banca_date
                        initial_balance = 0.0
                    else:
                        primer_pago = pagos_en_banca[0]
                        fecha_pago = pd.to_datetime(primer_pago.inicio)
                        
                        # Buscar metadata correspondiente
                        # Condición: meta.FECHA_EMISION < fecha_pago < meta.FECHA_MAX_PAGO
                        # (O ajustar segun la lógica exacta de periodos)
                        
                        found_meta = None
                        for _, meta in df_metadata.iterrows():
                            if meta[col_fecha_emision] < fecha_pago <= meta[col_fecha_max_pago]:
                                found_meta = meta
                                break
                        
                        if found_meta is not None:
                            # "Extraer monto a pagar y fecha de emision de metada mas antigua" (del match)
                            start_date = found_meta[col_fecha_emision]
                            initial_balance = float(found_meta[col_total_pagar])
                            
                            print(f"ℹ LOGIC: Metadata < Bank. Anchor Pago: {fecha_pago}. Meta Emision: {start_date}. Balance: {initial_balance}")
                        else:
                            print(f"⚠ No se encontró metadata para el primer pago en {fecha_pago}.")
                            start_date = min_banca_date
                            initial_balance = 0.0

                # --- CÁLCULO ---
                
                # 1. Filtrar consumos desde start_date
                df_consumos_filtered = df_consumos[df_consumos[col_consumo_fecha] >= start_date].copy()
                
                # 2. Calcular Acumulado Consumos
                df_consumos_filtered = df_consumos_filtered.sort_values(col_consumo_fecha)
                df_consumos_filtered['ACUMULADO_TARJETA'] = df_consumos_filtered[col_consumo_valor].cumsum()
                
                # Sumar saldo inicial (si aplica)
                # En Case NO es 0. En Case YES es el Total a Pagar del periodo anclado.
                # Nota: Si el "Total a Pagar" es la deuda al inicio del periodo (corte), entonces se suma.
                df_consumos_filtered['ACUMULADO_TARJETA'] += initial_balance
                
                # Merge con DF principal
                df_lookup = df_consumos_filtered[[col_consumo_fecha, 'ACUMULADO_TARJETA']].rename(columns={col_consumo_fecha: 'FECHA'})
                
                # --- FIX: Inyectar fechas faltantes de tarjeta en el DF principal ---
                # Esto permite que los movimientos de tarjeta se reflejen el día exacto
                # aunque no haya movimientos bancarios ese día.
                card_dates = df_lookup['FECHA'].unique()
                existing_dates = set(df['FECHA'])
                
                missing = [d for d in card_dates if d not in existing_dates]
                
                if missing:
                    df_missing = pd.DataFrame({'FECHA': missing})
                    df = pd.concat([df, df_missing], ignore_index=True)

                df = df.sort_values('FECHA')
                df = pd.merge_asof(
                    df,
                    df_lookup,
                    on='FECHA',
                    direction='backward'
                )
                df['ACUMULADO_TARJETA'] = df['ACUMULADO_TARJETA'].fillna(0)
                
                # 3. Calcular Pagos Acumulados
                # Solo considerar pagos desde start_date
                pagos_validos = [p for p in pagos_tarjeta if p.inicio and pd.to_datetime(p.inicio) >= start_date]
                
                # Usar marcar_fijos para crear la columna, pero necesitamos que sea acumulativa
                # La función marcar_fijos original crea una columna con valores puntuales o acumulados? 
                # Reavisando uso anterior: marcar_fijos(..., incluir_ultimo=True)
                # Si marcar_fijos no acumula, debemos acumular nosotros.
                # Asumimos que marcar_fijos pone el monto en la fecha.
                
                temp_col_pagos = "PAGO_TARJETA"
                df = marcar_fijos(df, pagos_validos, temp_col_pagos, incluir_ultimo=True)
                df[temp_col_pagos] = df[temp_col_pagos].fillna(0)
                
                
                # Si estamos en Case YES, el "monto que se pagó" (primer pago) ya está incluido en esta suma
                # y se restará del balance.
                
                # 4. Cálculo Final
                # TARJETA = (Saldo Inicial + Consumos) - Pagos
                df["TARJETA"] = df["ACUMULADO_TARJETA"] - df["PAGO_TARJETA"]

                # Limpieza
                df["TARJETA"] = df["TARJETA"].fillna(0)
                if temp_col_pagos in df.columns:
                    df = df.drop(columns=[temp_col_pagos])
                
                # Enmascarar fechas anteriores a start_date (según flujo: "ignorar todos los periodos anteriores")
                df.loc[df['FECHA'] < start_date, 'TARJETA'] = 0.0 # O NaN? "ignorar" suele ser 0 o no mostrar.
                df.loc[df['FECHA'] < start_date, 'ACUMULADO_TARJETA'] = 0.0
                df.loc[df['FECHA'] < start_date, 'PAGO_TARJETA'] = 0.0

                return df
                
            except Exception as e:
                print(f"⚠ Error en transform_tarjetas: {e}")
                # Asegurar columnas para no romper pipeline
                for col in ["PAGO_TARJETA", "ACUMULADO_TARJETA", "TARJETA"]:
                    if col not in df.columns:
                        df[col] = 0.0
                return df
                
            except Exception as e:
                print(f"⚠ Error en transform_tarjetas: {e}")
                # Asegurar columnas para no romper pipeline
                for col in ["PAGO_TARJETA", "ACUMULADO_TARJETA", "TARJETA"]:
                    if col not in df.columns:
                        df[col] = 0.0
                return df

        self.add_transformation('tarjetas', transform_tarjetas, cacheable=True, dependencies=['inversiones'])

    
    def get_cuenta_data(self, force_reload: bool = False) -> pd.DataFrame:
        """
        Obtiene datos de cuenta con caché.
        
        Args:
            force_reload: Si True, ignora caché y recarga desde archivo
        """
        import sys
        current_file = os.path.abspath(__file__)
        backend_dir = os.path.dirname(current_file)
        contabilidad_dir = os.path.dirname(backend_dir)
        project_root = os.path.dirname(contabilidad_dir)
        
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from contabilidad.config import PATH_BANCA_PROCESADA
        
        # Intentar obtener del caché
        if not force_reload:
            cached = self.source_cache.get('cuenta_data', PATH_BANCA_PROCESADA)
            if cached is not None:
                print("✓ Cache hit: cuenta_data")
                return cached
        
        # Cargar desde archivo unificado de banca
        print("⚙ Loading: cuenta_data from Unified Banca Source")
        df = self.get_banca_data(force_reload)
        
        # Ensure compatibility with legacy 'cuenta' structure:
        # Expected cols: FECHA, SALDO, DESCRIPCION, MONTO, DEBITO, CREDITO
        
        if 'MONTO' in df.columns:
            # Calculate DEBITO and CREDITO as positive values
            # DEBITO: Absolute value of negative amounts
            df['DEBITO'] = df['MONTO'].apply(lambda x: -x if x < 0 else 0.0)
            # CREDITO: Positive amounts
            df['CREDITO'] = df['MONTO'].apply(lambda x: x if x > 0 else 0.0)
            
        if 'SALDO' not in df.columns and 'MONTO' in df.columns:
             # Calculate SALDO if missing (cumulative sum)
            #  df = df.sort_values('FECHA')
             df['SALDO'] = df['MONTO'].cumsum()
        
        # Cachear
        self.source_cache.set('cuenta_data', df, PATH_BANCA_PROCESADA)
        
        return df
    
    def get_tarjeta_data(self, force_reload: bool = False) -> pd.DataFrame:
        """
        Obtiene datos de tarjeta con caché.
        
        Args:
            force_reload: Si True, ignora caché y recarga desde archivo
        """
        import sys
        current_file = os.path.abspath(__file__)
        backend_dir = os.path.dirname(current_file)
        contabilidad_dir = os.path.dirname(backend_dir)
        project_root = os.path.dirname(contabilidad_dir)
        
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from contabilidad.config import PATH_TARJETA_UNIDA
        
        # Intentar obtener del caché
        if not force_reload:
            cached = self.source_cache.get('tarjeta_data', PATH_TARJETA_UNIDA)
            if cached is not None:
                print("✓ Cache hit: tarjeta_data")
                return cached
        
        # Cargar desde archivo unificado de tarjeta
        print("⚙ Loading: tarjeta_data from Unified Tarjeta Source")
        df = self.get_tarjeta_unida_data(force_reload)
        
        # Standardize for legacy compatibility if needed
        # The new file uses 'MONTO', legacy might expect 'VALOR'
        if 'MONTO' in df.columns and 'VALOR' not in df.columns:
             df['VALOR'] = df['MONTO']
        
        # Invertir el signo de MONTO
        if 'MONTO' in df.columns:
             df['MONTO'] = -df['MONTO']
             
        # Cachear
        self.source_cache.set('tarjeta_data', df, PATH_TARJETA_UNIDA)
        
        return df

    def get_tarjeta_unida_data(self, force_reload: bool = False) -> pd.DataFrame:
        """
        Obtiene datos de tarjeta unida con caché.
        
        Args:
            force_reload: Si True, ignora caché y recarga desde archivo
        """
        import sys
        current_file = os.path.abspath(__file__)
        backend_dir = os.path.dirname(current_file)
        contabilidad_dir = os.path.dirname(backend_dir)
        project_root = os.path.dirname(contabilidad_dir)
        
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from contabilidad.config import PATH_TARJETA_UNIDA
        
        # Intentar obtener del caché
        if not force_reload:
            cached = self.source_cache.get('tarjeta_unida_data', PATH_TARJETA_UNIDA)
            if cached is not None:
                print("✓ Cache hit: tarjeta_unida_data")
                return cached
        
        # Cargar desde archivo
        print("⚙ Loading: tarjeta_unida_data from XLSX")
        if not os.path.exists(PATH_TARJETA_UNIDA):
            print(f"⚠ Archivo no encontrado: {PATH_TARJETA_UNIDA}")
            return pd.DataFrame()
            
        df = pd.read_excel(PATH_TARJETA_UNIDA)
        
        # # User fix: Card source contains only negative values but they are expenses.
        # # Invert sign to make them positive (accounting standard for expenses).
        # # We handle 'MONTO', 'VALOR' or 'TOTAL_CONSUMO'
        # cols_to_invert = [c for c in ['MONTO', 'VALOR', 'TOTAL_CONSUMO'] if c in df.columns]
        
        # for col in cols_to_invert:
        #     # We assume the file contains positive numbers for expenses.
        #     # We enforce negativity.
        #     df[col] = df[col].abs()
        
        if not df.empty and 'FECHA' in df.columns:
             print(f"DEBUG PIPELINE: Loaded Tarjeta {df.shape}, Range: {df['FECHA'].min()} - {df['FECHA'].max()}")

        # Cachear
        self.source_cache.set('tarjeta_unida_data', df, PATH_TARJETA_UNIDA)
        
        return df

    def get_banca_data(self, force_reload: bool = False) -> pd.DataFrame:
        """
        Obtiene datos de banca unida con caché.
        
        Args:
            force_reload: Si True, ignora caché y recarga desde archivo
        """
        import sys
        current_file = os.path.abspath(__file__)
        backend_dir = os.path.dirname(current_file)
        contabilidad_dir = os.path.dirname(backend_dir)
        project_root = os.path.dirname(contabilidad_dir)
        
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from contabilidad.config import PATH_BANCA_PROCESADA
        
        # Intentar obtener del caché
        if not force_reload:
            cached = self.source_cache.get('banca_data', PATH_BANCA_PROCESADA)
            if cached is not None:
                print("✓ Cache hit: banca_data")
                return cached
        
        # Cargar desde archivo
        print("⚙ Loading: banca_data from XLSX")
        if not os.path.exists(PATH_BANCA_PROCESADA):
            print(f"⚠ Archivo no encontrado: {PATH_BANCA_PROCESADA}")
            return pd.DataFrame()
            
        df = pd.read_excel(PATH_BANCA_PROCESADA)
        if not df.empty and 'FECHA' in df.columns:
            print(f"DEBUG PIPELINE: Loaded Banca {df.shape}, Range: {df['FECHA'].min()} - {df['FECHA'].max()}")
        
        # Cachear
        self.source_cache.set('banca_data', df, PATH_BANCA_PROCESADA)
        
        return df

    def get_tarjeta_metadata(self, force_reload: bool = False) -> pd.DataFrame:
        """
        Obtiene metadatos de los estados de cuenta de tarjeta (resúmenes) con caché.
        
        Args:
            force_reload: Si True, ignora caché y recarga desde archivos
        """
        import sys
        current_file = os.path.abspath(__file__)
        backend_dir = os.path.dirname(current_file)
        contabilidad_dir = os.path.dirname(backend_dir)
        project_root = os.path.dirname(contabilidad_dir)
        
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from contabilidad.config import PATH_TARJETA_PROCESADA
        
        # Intentar obtener del caché
        if not force_reload:
            # Usarlo como key simple sin file_path check (es un dir)
            cached = self.source_cache.get('tarjeta_metadata', None)
            if cached is not None:
                print("✓ Cache hit: tarjeta_metadata")
                return cached
        
        # Cargar desde lectura de archivos
        print("⚙ Loading: tarjeta_metadata from Excel files")
        try:
            from contabilidad.tarjeta.Lectura import leer_tarjetas
            # leer_cards reads all excel files in the folder
            df_resumen, _ = leer_tarjetas(PATH_TARJETA_PROCESADA)
        except Exception as e:
            print(f"⚠ Error leyendo metadatos de tarjeta: {e}")
            df_resumen = pd.DataFrame()
            
        # Cachear
        self.source_cache.set('tarjeta_metadata', df_resumen, None)
        
        return df_resumen
    
    def add_transformation(
        self, 
        name: str, 
        func: Callable[[pd.DataFrame], pd.DataFrame],
        cacheable: bool = True,
        dependencies: Optional[List[str]] = None
    ):
        """
        Agrega una transformación al pipeline.
        
        Args:
            name: Nombre único
            func: Función transformadora
            cacheable: Si se debe cachear
            dependencies: Lista de transformaciones previas requeridas
        
        Ejemplo:
            def agregar_columna_mes(df):
                df['MES'] = df['FECHA'].dt.month
                return df
            
            pipeline.add_transformation('agregar_mes', agregar_columna_mes)
        """
        self.pipeline.add_transformation(name, func, cacheable, dependencies)
    
    def get_processed_data(
        self, 
        source: str = 'cuenta',
        force_reload: bool = False,
        skip_transform_cache: bool = False
    ) -> pd.DataFrame:
        """
        Obtiene datos procesados con todas las transformaciones aplicadas.
        
        Args:
            source: 'cuenta' o 'tarjeta'
            force_reload: Recargar datos fuente
            skip_transform_cache: Recalcular transformaciones
        
        Returns:
            DataFrame procesado
        """
        # Obtener datos fuente
        if source == 'cuenta':
            df = self.get_cuenta_data(force_reload)
        elif source == 'tarjeta':
            df = self.get_tarjeta_data(force_reload)
        elif source == 'banca':
            df = self.get_banca_data(force_reload)
        elif source == 'tarjeta_unida':
            df = self.get_tarjeta_unida_data(force_reload)
        else:
            raise ValueError(f"Source inválido: {source}")
        
        # Aplicar pipeline de transformaciones
        if self.pipeline.transformations:
            df = self.pipeline.execute(df, skip_cache=skip_transform_cache)
        
        return df
    
    def invalidate_cache(self, scope: str = 'all'):
        """
        Invalida caché.
        
        Args:
            scope: 'all', 'source', 'transformations'
        """
        if scope in ['all', 'source']:
            self.source_cache.invalidate()
        
        if scope in ['all', 'transformations']:
            self.pipeline.clear_cache()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas de caché."""
        return {
            'source_cache': self.source_cache.get_stats(),
            'transformation_cache': self.pipeline.cache.get_stats(),
            'transformations_registered': len(self.pipeline.transformations)
        }


# Singleton global para reutilizar en toda la aplicación
_global_pipeline: Optional[DataPipeline] = None


def get_pipeline() -> DataPipeline:
    """
    Obtiene la instancia global del pipeline.
    Usar esta función en lugar de crear instancias nuevas.
    """
    global _global_pipeline
    if _global_pipeline is None:
        _global_pipeline = DataPipeline()
    return _global_pipeline


def reset_pipeline():
    """Resetea el pipeline global (útil para testing)."""
    global _global_pipeline
    _global_pipeline = None
