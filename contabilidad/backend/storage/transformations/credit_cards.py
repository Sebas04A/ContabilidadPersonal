import pandas as pd
from contabilidad.backend.logger import get_logger
from typing import Tuple, Any

logger = get_logger(__name__)


def _get_credit_card_metadata(pipeline) -> Tuple[pd.DataFrame, str, str, str]:
    df_metadata = pd.DataFrame()
    col_fecha_emision = "FECHA_EMISION"
    col_total_pagar = "TOTAL_A_PAGAR"
    col_fecha_max_pago = "FECHA_MAX_PAGO"
    try:
        df_metadata = pipeline.get_credit_card_metadata()
        from contabilidad.backend.services.credit_card.models import MAPEO_COLUMNAS
        col_fecha_emision = MAPEO_COLUMNAS.get("FECHA_EMISION", "FECHA_EMISION")
        col_total_pagar = MAPEO_COLUMNAS.get("TOTAL_A_PAGAR", "TOTAL_A_PAGAR")
        col_fecha_max_pago = MAPEO_COLUMNAS.get("FECHA_MAX_PAGO", "FECHA_MAX_PAGO")
        
        if not df_metadata.empty:
            df_metadata[col_fecha_emision] = pd.to_datetime(df_metadata[col_fecha_emision])
            df_metadata[col_fecha_max_pago] = pd.to_datetime(df_metadata[col_fecha_max_pago])
            df_metadata = df_metadata.sort_values(col_fecha_emision)
    except Exception as e:
        logger.warning("Error obteniendo metadata tarjeta: %s", e)
        df_metadata = pd.DataFrame()
        
    return df_metadata, col_fecha_emision, col_total_pagar, col_fecha_max_pago


def _get_credit_card_consumos(pipeline) -> Tuple[pd.DataFrame, str, str]:
    df_consumos = pd.DataFrame()
    col_consumo_fecha = "FECHA_EMISION"
    col_consumo_valor = "TOTAL_CONSUMO"
    try:
        df_consumos = pipeline.get_raw_data(source='tarjeta')
        
        try:
            from contabilidad.backend.services.credit_card.models import MAPEO_COLUMNAS
            col_consumo_fecha = MAPEO_COLUMNAS.get("FECHA_EMISION", "FECHA_EMISION")
            col_consumo_valor = MAPEO_COLUMNAS.get("TOTAL_CONSUMO", "TOTAL_CONSUMO")
        except ImportError:
            pass
            
        if col_consumo_valor not in df_consumos.columns:
             col_consumo_valor = "VALOR" if "VALOR" in df_consumos.columns else "MONTO"
        if col_consumo_fecha not in df_consumos.columns:
             col_consumo_fecha = "FECHA"

        if not df_consumos.empty:
            df_consumos[col_consumo_fecha] = pd.to_datetime(df_consumos[col_consumo_fecha])
    except Exception as e:
        logger.warning("Error obteniendo consumos tarjeta: %s", e)
        df_consumos = pd.DataFrame()
        
    return df_consumos, col_consumo_fecha, col_consumo_valor


def _apply_defaults(df: pd.DataFrame, pagos_tarjeta: list, min_banca_date) -> pd.DataFrame:
    from contabilidad.backend.services.bank_parser.get_variables import mark_fixed_payments
    logger.warning("Datos insuficientes para cálculo avanzado de tarjeta. Usando defaults.")
    pagos_filtrados = [p for p in pagos_tarjeta if p.start_date and pd.to_datetime(p.start_date) >= min_banca_date]
    df = mark_fixed_payments(df, pagos_filtrados, "PAGO_TARJETA", include_last=True)
    df["PAGO_TARJETA"] = df["PAGO_TARJETA"].fillna(0)
    df['ACUMULADO_TARJETA'] = 0.0
    df['TARJETA'] = -df["PAGO_TARJETA"]
    return df


def _calculate_anchor_point(
    df_metadata: pd.DataFrame, 
    min_meta_date, 
    min_banca_date, 
    pagos_tarjeta: list, 
    col_fecha_emision: str, 
    col_total_pagar: str, 
    col_fecha_max_pago: str
) -> Tuple[Any, float]:
    
    start_date = None
    initial_balance =  0.0
    
    is_metadata_older = min_meta_date < min_banca_date

    if not is_metadata_older:
        first_meta = df_metadata.iloc[0]
        start_date = first_meta[col_fecha_emision]
        initial_balance = 0.0 
        
        logger.debug("LOGIC: Metadata >= Bank. Start: %s, Init Bal: %s", start_date, initial_balance)
        
    else:
        pagos_en_banca = [p for p in pagos_tarjeta if p.start_date and pd.to_datetime(p.start_date) >= min_banca_date]
        pagos_en_banca.sort(key=lambda x: pd.to_datetime(x.start_date))
        if not pagos_en_banca:
            logger.warning("No se encontraron pagos en banca para anclar. Usando default.")
            start_date = min_banca_date
            initial_balance = 0.0
        else:
            primer_pago = pagos_en_banca[0]
            fecha_pago = pd.to_datetime(primer_pago.start_date)
            
            found_meta = None
            for _, meta in df_metadata.iterrows():
                if meta[col_fecha_emision] < fecha_pago <= meta[col_fecha_max_pago]:
                    found_meta = meta
                    break
            
            if found_meta is not None:
                start_date = found_meta[col_fecha_emision]
                initial_balance = float(found_meta[col_total_pagar])
                
                logger.debug("LOGIC: Metadata < Bank. Anchor: %s, Emision: %s, Bal: %s", fecha_pago, start_date, initial_balance)
            else:
                logger.warning("No se encontró metadata para el primer pago en %s", fecha_pago)
                start_date = min_banca_date
                initial_balance = 0.0
                
    return start_date, initial_balance - 56


def _merge_consumos_and_calculate_balance(
    df: pd.DataFrame, 
    df_consumos: pd.DataFrame, 
    pagos_tarjeta: list,
    start_date, 
    initial_balance: float, 
    col_consumo_fecha: str, 
    col_consumo_valor: str
) -> pd.DataFrame:
    from contabilidad.backend.services.bank_parser.get_variables import mark_fixed_payments, add_missing_dates
    
    df_consumos_filtered = df_consumos[df_consumos[col_consumo_fecha] >= start_date].copy()
    df_consumos_filtered[col_consumo_valor] = pd.to_numeric(df_consumos_filtered[col_consumo_valor], errors='coerce').fillna(0)
    
    # 1. Calcular el acumulado progresivo exacto fila por fila (para ver su crecimiento por monto)
    # CRITICO: Ordenar por FECHA y ID para que el cumsum sea determinista y el grouping .last() coincida con la ultima transaccion del dia
    if 'id' in df_consumos_filtered.columns:
        df_consumos_filtered = df_consumos_filtered.sort_values([col_consumo_fecha, 'id'])
    else:
        df_consumos_filtered = df_consumos_filtered.sort_values(col_consumo_fecha)
        
    df_consumos_filtered['ACUMULADO_EXACTO'] = df_consumos_filtered[col_consumo_valor].cumsum() + initial_balance        
    # Rellenamos los vacíos que puedan existir
    df['ACUMULADO_TARJETA'] = df_consumos_filtered['ACUMULADO_EXACTO'].ffill().fillna(0)
        
    pagos_validos = [p for p in pagos_tarjeta if p.start_date and pd.to_datetime(p.start_date) >= start_date]
    
    # Extraemos fechas que necesitamos agregar obligatoriamente (las de los pagos)
    fechas_pago = []
    for p in pagos_validos:
        if p.start_date: fechas_pago.append(p.start_date)
        if getattr(p, 'end_date', None): fechas_pago.append(p.end_date)
            
    # Función clean externa para inyectar solo fechas necesarias
    df = add_missing_dates(df, fechas_pago)
    
    temp_col_pagos = "PAGO_TARJETA"
    df = mark_fixed_payments(df, pagos_validos, temp_col_pagos, include_last=True)
    df[temp_col_pagos] = df[temp_col_pagos].fillna(0)

    # CRITICAL FIX: El DataFrame debe estar estrictamente ordenado antes del ffill
    # de lo contrario, filas inyectadas al final recibirán el ACUMULADO de la última fila random iterada
    if 'id' in df.columns:
        df = df.sort_values(['FECHA', 'id']).reset_index(drop=True)
    else:
        df = df.sort_values('FECHA').reset_index(drop=True)
    
    # Rellenamos huecos (incluyendo fechas inyectadas u omitted) con el acumulado previo real en el tiempo
    df['ACUMULADO_TARJETA'] = df['ACUMULADO_TARJETA'].ffill().fillna(0)
    
    df["TARJETA"] = df["ACUMULADO_TARJETA"] - df["PAGO_TARJETA"]

    df["TARJETA"] = df["TARJETA"].fillna(0)
    
    df.loc[df['FECHA'] < start_date, 'TARJETA'] = 0.0 
    df.loc[df['FECHA'] < start_date, 'ACUMULADO_TARJETA'] = 0.0
    df.loc[df['FECHA'] < start_date, 'PAGO_TARJETA'] = 0.0

    return df


def transform_credit_cards(df: pd.DataFrame) -> pd.DataFrame:
    try:
        from contabilidad.backend.services.bank_parser.get_variables import get_credit_card_payments
        from contabilidad.backend.storage.data_pipeline import get_pipeline
        
        pipeline = get_pipeline()
        
        pagos_tarjeta = get_credit_card_payments(pipeline.get_raw_data('cuenta'))
        min_banca_date = df["FECHA"].min() if not df.empty else None
        
        df_metadata, col_fecha_emision, col_total_pagar, col_fecha_max_pago = _get_credit_card_metadata(pipeline)
        
        df_consumos, col_consumo_fecha, col_consumo_valor = _get_credit_card_consumos(pipeline)

        if df.empty or df_metadata.empty or df_consumos.empty:
            return _apply_defaults(df, pagos_tarjeta, min_banca_date)

        min_meta_date = df_metadata[col_fecha_emision].min()
        
        start_date, initial_balance = _calculate_anchor_point(
            df_metadata, min_meta_date, min_banca_date, pagos_tarjeta, 
            col_fecha_emision, col_total_pagar, col_fecha_max_pago
        )
        df_consumos= df_consumos.sort_values(col_consumo_fecha)
        df = _merge_consumos_and_calculate_balance(
            df, df_consumos, pagos_tarjeta, start_date, initial_balance, 
            col_consumo_fecha, col_consumo_valor
        )

        return df
        
    except Exception as e:
        logger.warning("Error en transform_credit_cards: %s", e)
        for col in ["PAGO_TARJETA", "ACUMULADO_TARJETA", "TARJETA"]:
            if col not in df.columns:
                df[col] = 0.0
        return df
