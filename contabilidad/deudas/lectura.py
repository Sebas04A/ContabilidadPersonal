"""
Modulo de lectura de deudas desde Supabase.
Proporciona funciones para obtener datos limpios de deudas en formato DataFrame.
"""

import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from typing import Optional, List
import os

# Credenciales de Supabase
SUPABASE_URL = "https://rcmdzvbxerumzxvnubfo.supabase.co"
SUPABASE_KEY = "sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw"

# Cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def obtener_todos_deudores() -> pd.DataFrame:
    """
    Obtiene todos los deudores registrados.
    
    Returns:
        DataFrame con columnas: id, nombre, token, created_at
    """
    response = supabase.table('deudores').select('*').execute()
    
    if not response.data:
        return pd.DataFrame(columns=['id', 'nombre', 'token', 'created_at'])
    
    df = pd.DataFrame(response.data)
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    return df


def obtener_todas_deudas(solo_pendientes: bool = True) -> pd.DataFrame:
    """
    Obtiene todas las deudas registradas desde la vista de estado.
    """
    query = supabase.table('vista_estado_deudas').select('*')
    
    # En la vista, la columna de filtro es 'estado'
    # 'PAGADA', 'PENDIENTE', 'PARCIAL'
    if solo_pendientes:
        query = query.neq('estado', 'PAGADA')
    
    response = query.execute()
    
    if not response.data:
        # Retornamos estructura compatible pero con los campos nuevos
        return pd.DataFrame(columns=[
            'id', 'titulo', 'monto_original', 'deudor_id', 'fecha_gasto', 
            'monto_pagado', 'saldo_pendiente', 'estado'
        ])
    
    df = pd.DataFrame(response.data)
    df['fecha_gasto'] = pd.to_datetime(df['fecha_gasto'])
    # Renombrar para compatibilidad hacia atras si es necesario
    # df['monto'] ahora es 'monto_original' en la vista
    df['monto'] = pd.to_numeric(df['monto_original'])
    df['pagada'] = df['estado'] == 'PAGADA'
    
    return df


def obtener_deudas_por_deudor(deudor_id: str, solo_pendientes: bool = True) -> pd.DataFrame:
    """
    Obtiene las deudas de un deudor especifico desde la vista.
    """
    query = supabase.table('vista_estado_deudas').select('*').eq('deudor_id', deudor_id)
    
    if solo_pendientes:
        query = query.neq('estado', 'PAGADA')
    
    response = query.execute()
    
    if not response.data:
        return pd.DataFrame(columns=[
            'id', 'titulo', 'monto_original', 'deudor_id', 'fecha_gasto', 
            'monto_pagado', 'saldo_pendiente', 'estado'
        ])
    
    df = pd.DataFrame(response.data)
    df['fecha_gasto'] = pd.to_datetime(df['fecha_gasto'])
    df['monto'] = pd.to_numeric(df['monto_original'])
    df['pagada'] = df['estado'] == 'PAGADA'
    
    return df.sort_values('fecha_gasto', ascending=False).reset_index(drop=True)


def obtener_deudas_con_deudor(solo_pendientes: bool = True) -> pd.DataFrame:
    """
    Obtiene todas las deudas con informacion del deudor (JOIN).
    Para esto usamos la tabla 'deudas' cruda para el JOIN, pero necesitamos el estado.
    Estrategia: Usar la vista y hacer fetch de deudores por separado o JOIN si Supabase lo permite en vistas.
    Supabase (PostgREST) permite Foreign Tables en vistas si estan definidas.
    Asumamos que NO estan linkeadas en la vista por ahora.
    Hacemos: SELECT * FROM vista_estado_deudas, luego map de deudores.
    """
    # 1. Obtener vista
    query = supabase.table('vista_estado_deudas').select('*')
    if solo_pendientes:
        query = query.neq('estado', 'PAGADA')
    resp_deudas = query.execute()
    
    if not resp_deudas.data:
        return pd.DataFrame()
        
    df = pd.DataFrame(resp_deudas.data)
    
    # 2. Obtener deudores
    # Optimizacion: Deudores uniques
    ids_deudores = df['deudor_id'].unique().tolist()
    resp_deudores = supabase.table('deudores').select('id, nombre, token').in_('id', ids_deudores).execute()
    
    mapa_deudores = {d['id']: d for d in resp_deudores.data}
    
    # 3. Merge manual
    data_expandida = []
    for _, row in df.iterrows():
        item = row.to_dict()
        deudor = mapa_deudores.get(item['deudor_id'], {})
        item['deudor_nombre'] = deudor.get('nombre', 'Desconocido')
        item['deudor_token'] = deudor.get('token', '')
        data_expandida.append(item)
        
    df_final = pd.DataFrame(data_expandida)
    df_final['fecha_gasto'] = pd.to_datetime(df_final['fecha_gasto'])
    df_final['monto'] = pd.to_numeric(df_final['monto_original'])
    df_final['pagada'] = df_final['estado'] == 'PAGADA'
    
    return df_final.sort_values('fecha_gasto', ascending=False).reset_index(drop=True)


def obtener_resumen_por_deudor(solo_pendientes: bool = True) -> pd.DataFrame:
    """
    Obtiene un resumen de deudas agrupado por deudor.
    
    Args:
        solo_pendientes: Si True, solo cuenta deudas no pagadas. Default: True
        
    Returns:
        DataFrame con columnas: deudor_id, deudor_nombre, total_deuda, 
                               cantidad_deudas, deuda_mas_antigua
    """
    df_deudas = obtener_deudas_con_deudor(solo_pendientes=solo_pendientes)
    
    if df_deudas.empty:
        return pd.DataFrame(columns=[
            'deudor_id', 'deudor_nombre', 'total_deuda', 
            'cantidad_deudas', 'deuda_mas_antigua'
        ])
    
    resumen = df_deudas.groupby(['deudor_id', 'deudor_nombre']).agg({
        'monto': ['sum', 'count'],
        'fecha_gasto': 'min'
    }).reset_index()
    
    resumen.columns = [
        'deudor_id', 'deudor_nombre', 'total_deuda', 
        'cantidad_deudas', 'deuda_mas_antigua'
    ]
    
    return resumen.sort_values('total_deuda', ascending=False).reset_index(drop=True)


def obtener_deudas_para_analisis(
    fecha_inicio: Optional[datetime] = None,
    fecha_fin: Optional[datetime] = None,
    solo_pendientes: bool = False
) -> pd.DataFrame:
    """
    Obtiene deudas con informacion completa para analisis financiero.
    Compatible con el resto del sistema de contabilidad.
    
    Args:
        fecha_inicio: Fecha minima de deuda (fecha_gasto)
        fecha_fin: Fecha maxima de deuda (fecha_gasto)
        solo_pendientes: Si True, solo deudas no pagadas
        
    Returns:
        DataFrame limpio listo para analisis con columnas estandar:
        FECHA, DESCRIPCION, MONTO, TIPO, DEUDOR_NOMBRE, PAGADA, 
        FECHA_PAGO, FECHA_CREACION
    """
    df = obtener_deudas_con_deudor(solo_pendientes=solo_pendientes)
    
    if df.empty:
        return pd.DataFrame(columns=[
            'FECHA', 'DESCRIPCION', 'MONTO', 'TIPO', 
            'DEUDOR_NOMBRE', 'PAGADA', 'FECHA_PAGO', 'FECHA_CREACION'
        ])
    
    # Filtrar por fechas si se proporcionan
    if fecha_inicio:
        df = df[df['fecha_gasto'] >= fecha_inicio]
    if fecha_fin:
        df = df[df['fecha_gasto'] <= fecha_fin]
    
    # Renombrar y seleccionar columnas al estilo del sistema
    df_limpio = pd.DataFrame({
        'FECHA': df['fecha_gasto'],
        'DESCRIPCION': df['titulo'],
        'MONTO': df['monto'],
        'TIPO': 'DEUDA',
        'DEUDOR_NOMBRE': df['deudor_nombre'],
        'DEUDOR_ID': df['deudor_id'],
        'PAGADA': df['pagada'],
        'FECHA_PAGO': df.get('fecha_pago'),
        'FECHA_CREACION': df.get('created_at'),
        'ID': df['id']
    })
    
    return df_limpio.sort_values('FECHA', ascending=False).reset_index(drop=True)


def obtener_todos_pagos() -> pd.DataFrame:
    """
    Obtiene todos los pagos realizados registrados en la tabla 'pagos'.
    
    Returns:
        DataFrame con columnas: id, fecha_pago, monto_total, deudor_id, deudor_nombre
    """
    # 1. Obtener pagos
    response = supabase.table('pagos').select('*').execute()
    
    if not response.data:
        return pd.DataFrame(columns=['id', 'fecha_pago', 'monto_total', 'deudor_id', 'deudor_nombre'])
        
    df = pd.DataFrame(response.data)
    
    # 2. Enriquecer con nombre de deudor
    # Obtener deudores para map
    ids_deudores = df['deudor_id'].unique().tolist()
    if ids_deudores:
        try:
            resp_deudores = supabase.table('deudores').select('id, nombre').in_('id', ids_deudores).execute()
            if resp_deudores.data:
                mapa_deudores = {d['id']: d['nombre'] for d in resp_deudores.data}
                # Use apply/map instead of map directly to avoid errors if some ids are missing
                df['deudor_nombre'] = df['deudor_id'].apply(lambda x: mapa_deudores.get(x, 'Desconocido'))
            else:
                 df['deudor_nombre'] = 'Desconocido'
        except Exception:
            df['deudor_nombre'] = 'Desconocido'
    else:
        df['deudor_nombre'] = 'Desconocido'
        
    df['fecha_pago'] = pd.to_datetime(df['fecha_pago'])
    df['monto_total'] = pd.to_numeric(df['monto_total'])
    
    return df.sort_values('fecha_pago', ascending=False)



if __name__ == "__main__":
    # Ejemplos de uso
    print("=== DEUDORES ===")
    df_deudores = obtener_todos_deudores()
    print(df_deudores)
    
    print("\n=== DEUDAS PENDIENTES ===")
    df_deudas = obtener_todas_deudas(solo_pendientes=True)
    print(df_deudas)
    
    print("\n=== RESUMEN POR DEUDOR ===")
    df_resumen = obtener_resumen_por_deudor()
    print(df_resumen)
    
    print("\n=== DEUDAS PARA ANALISIS ===")
    df_analisis = obtener_deudas_para_analisis()
    print(df_analisis.head())
