"""
Modulo de lectura de deudas desde Supabase.
Proporciona funciones para obtener datos limpios de deudas en formato DataFrame.
"""

import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from typing import Optional, List
import os

from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

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
    response = supabase.table('deudores').select('*').where('nombre', '!=', '').execute()
    
    if not response.data:
        return pd.DataFrame(columns=['id', 'nombre', 'token', 'created_at'])
    
    df = pd.DataFrame(response.data)
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    return df


def listar_deudores() -> pd.DataFrame:
    """
    Lista simple de deudores (id, nombre) para poblar selects en el frontend.
    Robusta ante nombres vacíos. Soporta MOCK_MODE derivando de las deudas mock.
    """
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        mock_path = os.path.join(base_dir, "data_mock", "sistema", "deudas", "deudas.csv")
        if os.path.exists(mock_path):
            m = pd.read_csv(mock_path)
            if {'deudor_id', 'deudor_nombre'}.issubset(m.columns):
                d = m[['deudor_id', 'deudor_nombre']].drop_duplicates()
                d = d.rename(columns={'deudor_id': 'id', 'deudor_nombre': 'nombre'})
                return d.sort_values('nombre').reset_index(drop=True)
        return pd.DataFrame(columns=['id', 'nombre'])

    response = supabase.table('deudores').select('id, nombre').execute()
    if not response.data:
        return pd.DataFrame(columns=['id', 'nombre'])

    df = pd.DataFrame(response.data)
    df = df[df['nombre'].notna() & (df['nombre'].astype(str).str.strip() != '')]
    return df.sort_values('nombre').reset_index(drop=True)


def _ec_num(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _ec_fecha(v):
    return str(v)[:10] if v is not None else None


def _construir_flujo_cuenta(deudas_raw: list, pagos_raw: list, detalles: list) -> dict:
    """
    Arma el estado de cuenta completo a partir de listas crudas de deudas, pagos y
    detalle_pagos (asignaciones pago→deuda). Devuelve deudas (con qué pagos las
    abonaron), pagos (con a qué deudas fueron + sobrante), un ledger cronológico con
    saldo acumulado, y un resumen con neto y saldo a favor.

    Convención de signo del ledger (POV = dueño): las deudas "te deben" suman al saldo
    por cobrar (+), las "tú debes" restan (−), y cada asignación de pago reduce el saldo.
    """
    pago_by_id = {str(p.get('id')): p for p in pagos_raw}
    titulo_by_deuda = {str(d.get('id')): (d.get('titulo') or 'Deuda') for d in deudas_raw}

    det_by_deuda: dict = {}
    det_by_pago: dict = {}
    for det in detalles:
        det_by_deuda.setdefault(str(det.get('deuda_id')), []).append(det)
        det_by_pago.setdefault(str(det.get('pago_id')), []).append(det)

    # --- Deudas ---
    out_deudas = []
    for d in deudas_raw:
        did = str(d.get('id'))
        allocs = det_by_deuda.get(did, [])
        pagado = round(sum(_ec_num(a.get('monto_asignado')) for a in allocs), 2)
        mo = _ec_num(d.get('monto') if d.get('monto') is not None else d.get('monto_original'))
        saldo = round(mo - pagado, 2)
        estado = 'PAGADA' if saldo <= 0.01 else ('PARCIAL' if pagado > 0.01 else 'PENDIENTE')
        out_deudas.append({
            'id': did,
            'titulo': d.get('titulo') or 'Deuda',
            'fecha_gasto': _ec_fecha(d.get('fecha_gasto')),
            'monto_original': mo,
            'monto_pagado': pagado,
            'saldo_pendiente': max(saldo, 0.0),
            'estado': estado,
            'es_tu_deuda': bool(d.get('es_mi_deuda')),
            'pagos': [{
                'pago_id': str(a.get('pago_id')),
                'fecha_pago': _ec_fecha((pago_by_id.get(str(a.get('pago_id'))) or {}).get('fecha_pago')),
                'monto_asignado': _ec_num(a.get('monto_asignado')),
            } for a in allocs],
        })

    # --- Pagos ---
    out_pagos = []
    for p in pagos_raw:
        pid = str(p.get('id'))
        allocs = det_by_pago.get(pid, [])
        asignado = round(sum(_ec_num(a.get('monto_asignado')) for a in allocs), 2)
        mt = _ec_num(p.get('monto_total'))
        out_pagos.append({
            'id': pid,
            'fecha_pago': _ec_fecha(p.get('fecha_pago')),
            'monto_total': mt,
            'asignado': asignado,
            'sobrante': round(mt - asignado, 2),
            'es_mi_pago': bool(p.get('es_mi_pago')),
            'es_compensacion': bool(p.get('es_compensacion')),
            'deudas': [{
                'deuda_id': str(a.get('deuda_id')),
                'titulo': titulo_by_deuda.get(str(a.get('deuda_id')), '—'),
                'monto_asignado': _ec_num(a.get('monto_asignado')),
            } for a in allocs],
        })

    # --- Saldo a favor abonado a las deudas ---
    # El sobrante de un pago (dinero entregado que no se asignó a ninguna deuda) es
    # crédito de quien pagó, así que cubre automáticamente SUS deudas pendientes, de la
    # más antigua a la más reciente. Se descuenta igual que un cruce: la deuda conserva
    # su `saldo_pendiente`, y `abono_saldo_favor` dice cuánto de eso ya está cubierto.
    favor_owner = round(sum(p['sobrante'] for p in out_pagos
                            if p['sobrante'] > 0.01 and not p['es_compensacion'] and p['es_mi_pago']), 2)
    favor_debtor = round(sum(p['sobrante'] for p in out_pagos
                             if p['sobrante'] > 0.01 and not p['es_compensacion'] and not p['es_mi_pago']), 2)

    credito = {True: favor_owner, False: favor_debtor}
    for d in out_deudas:
        d['abono_saldo_favor'] = 0.0
    for d in sorted((x for x in out_deudas if x['saldo_pendiente'] > 0.01),
                    key=lambda x: x['fecha_gasto'] or ''):
        disponible = credito[d['es_tu_deuda']]
        if disponible <= 0.01:
            continue
        abono = round(min(d['saldo_pendiente'], disponible), 2)
        d['abono_saldo_favor'] = abono
        credito[d['es_tu_deuda']] = round(disponible - abono, 2)

    # Lo que quedó de crédito sin abonar a ninguna deuda
    remanente_favor_owner = credito[True]
    remanente_favor_debtor = credito[False]

    for d in out_deudas:
        d['saldo_real'] = round(d['saldo_pendiente'] - d['abono_saldo_favor'], 2)
        if d['saldo_real'] <= 0.01:
            d['estado'] = 'PAGADA'
        elif d['monto_pagado'] > 0.01 or d['abono_saldo_favor'] > 0.01:
            d['estado'] = 'PARCIAL'

    # --- Ledger cronológico (ascendente) con saldo acumulado ---
    eventos = []
    for d in out_deudas:
        sign = -1 if d['es_tu_deuda'] else 1
        eventos.append({
            'fecha': d['fecha_gasto'], 'tipo': 'deuda', 'id': d['id'],
            'concepto': d['titulo'], 'es_tu_deuda': d['es_tu_deuda'],
            'delta': round(sign * d['monto_original'], 2), 'detalle': [],
        })
    for p in out_pagos:
        # Signo del pago (POV dueño = igual que edge function get_historial):
        #  - pago recibido (no es_mi_pago): resta del saldo por el TOTAL pagado.
        #  - pago entregado (es_mi_pago): suma al saldo por el total.
        #  - compensación (cruce): NO altera el saldo (el offset ya se refleja en las
        #    deudas de ambos lados); solo se muestra como movimiento informativo.
        # Se usa monto_total (asignado + sobrante) para que el saldo a favor quede
        # reflejado como crédito del deudor.
        if p['es_compensacion']:
            concepto, delta = 'Cruce de cuentas', 0.0
        elif p['es_mi_pago']:
            concepto, delta = 'Pago entregado', round(p['monto_total'], 2)
        else:
            concepto, delta = 'Pago recibido', round(-p['monto_total'], 2)
        eventos.append({
            'fecha': p['fecha_pago'], 'tipo': 'pago', 'id': p['id'],
            'concepto': concepto, 'es_tu_deuda': False,
            'delta': delta, 'sobrante': p['sobrante'],
            'es_compensacion': p['es_compensacion'], 'monto_total': p['monto_total'],
            'detalle': [{'titulo': a['titulo'], 'monto': a['monto_asignado']} for a in p['deudas']],
        })
    # Saldo acumulado se calcula en orden cronológico (pasado→presente).
    eventos.sort(key=lambda e: ((e['fecha'] or ''), 0 if e['tipo'] == 'deuda' else 1))
    saldo = 0.0
    for e in eventos:
        saldo = round(saldo + e['delta'], 2)
        e['saldo_acumulado'] = saldo

    # --- Deudas que quedan PARCIALMENTE cubiertas tras cada pago ---
    # Recorriendo los pagos cronológicamente, acumulamos lo abonado por deuda; si tras un
    # pago una deuda que ese pago tocó sigue con saldo (0 < pagado < original), se repite
    # bajo el pago con su saldo restante en ese momento.
    from collections import defaultdict
    deuda_orig = {d['id']: d['monto_original'] for d in out_deudas}
    deuda_titulo = {d['id']: d['titulo'] for d in out_deudas}
    cum: dict = defaultdict(float)
    for p in sorted(out_pagos, key=lambda x: (x['fecha_pago'] or '')):
        for a in p['deudas']:
            cum[a['deuda_id']] += a['monto_asignado']
        parciales, seen = [], set()
        for a in p['deudas']:
            did = a['deuda_id']
            if did in seen:
                continue
            seen.add(did)
            orig = deuda_orig.get(did, 0.0)
            pagado = round(cum[did], 2)
            saldo_d = round(orig - pagado, 2)
            if pagado > 0.01 and saldo_d > 0.01:  # parcialmente cubierta
                parciales.append({
                    'deuda_id': did, 'titulo': deuda_titulo.get(did, '—'),
                    'monto_original': orig, 'pagado_acumulado': pagado, 'saldo': saldo_d,
                })
        p['_parciales'] = parciales
    parciales_by_pago = {p['id']: p.get('_parciales', []) for p in out_pagos}
    for e in eventos:
        if e['tipo'] == 'pago':
            e['parciales'] = parciales_by_pago.get(e['id'], [])
    for p in out_pagos:
        p.pop('_parciales', None)

    # --- Orden de presentación: presente→pasado (cronológico descendente) ---
    # El pago tiene fecha posterior a las deudas que abonó, así que queda ARRIBA
    # (más actual) que ellas. En misma fecha, el pago va sobre la deuda.
    movimientos = list(reversed(eventos))

    out_deudas.sort(key=lambda d: d['fecha_gasto'] or '', reverse=True)
    out_pagos.sort(key=lambda p: p['fecha_pago'] or '', reverse=True)

    # Totales sobre el saldo REAL: lo que ya cubre el saldo a favor no se debe.
    total_te_deben = round(sum(d['saldo_real'] for d in out_deudas if not d['es_tu_deuda']), 2)
    total_tu_debes = round(sum(d['saldo_real'] for d in out_deudas if d['es_tu_deuda']), 2)

    resumen = {
        'total_original': round(sum(d['monto_original'] for d in out_deudas), 2),
        'total_pagado': round(sum(d['monto_pagado'] for d in out_deudas), 2),
        'total_pendiente': round(sum(d['saldo_real'] for d in out_deudas), 2),
        'total_te_deben': total_te_deben,
        'total_tu_debes': total_tu_debes,
        # + te deben, − tú debes. El crédito que quedó sin abonar es deuda pura: lo que
        # el deudor pagó de más se lo debes, lo que pagaste de más te lo debe.
        'neto': round(total_te_deben - total_tu_debes
                      - remanente_favor_debtor + remanente_favor_owner, 2),
        'saldo_favor': remanente_favor_debtor,
        'saldo_favor_owner': remanente_favor_owner,
        'count': len(out_deudas),
        'count_pagadas': sum(1 for d in out_deudas if d['estado'] == 'PAGADA'),
        'count_pendientes': sum(1 for d in out_deudas if d['estado'] != 'PAGADA'),
    }
    return {'deudas': out_deudas, 'pagos': out_pagos, 'movimientos': movimientos, 'resumen': resumen}


def obtener_estado_cuenta(deudor_id: str) -> dict:
    """
    Estado de cuenta completo de un deudor: deudas con qué pagos las abonaron, pagos con
    a qué deudas fueron (+ sobrante), ledger cronológico con saldo acumulado y resumen.
    Modela el flujo real de dinero usando las tablas `deudas`, `pagos` y `detalle_pagos`.
    """
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        dpath = os.path.join(base_dir, "data_mock", "sistema", "deudas", "deudas.csv")
        ppath = os.path.join(base_dir, "data_mock", "sistema", "deudas", "pagos_deudas.csv")
        deudas_raw, pagos_raw = [], []
        if os.path.exists(dpath):
            m = pd.read_csv(dpath)
            m = m[m['deudor_id'].astype(str) == str(deudor_id)]
            deudas_raw = m.to_dict(orient='records')
        if os.path.exists(ppath):
            p = pd.read_csv(ppath)
            p = p[p['deudor_id'].astype(str) == str(deudor_id)]
            pagos_raw = p.to_dict(orient='records')
        # El mock no tiene detalle_pagos; los pagos quedan como saldo a favor.
        return _construir_flujo_cuenta(deudas_raw, pagos_raw, [])

    deudas_raw = supabase.table('deudas').select('*').eq('deudor_id', deudor_id).execute().data or []
    pagos_raw = supabase.table('pagos').select('*').eq('deudor_id', deudor_id).execute().data or []
    deuda_ids = [d.get('id') for d in deudas_raw if d.get('id') is not None]
    detalles = []
    if deuda_ids:
        detalles = supabase.table('detalle_pagos').select('*').in_('deuda_id', deuda_ids).execute().data or []
    return _construir_flujo_cuenta(deudas_raw, pagos_raw, detalles)


def obtener_todas_deudas(solo_pendientes: bool = True) -> pd.DataFrame:
    """
    Obtiene todas las deudas registradas desde la vista de estado.
    """
    query = supabase.table('vista_estado_deudas').select('*').where('nombre', '!=', '').execute()
    
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
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        mock_path = os.path.join(base_dir, "data_mock", "sistema", "deudas", "deudas.csv")
        if os.path.exists(mock_path):
            df_final = pd.read_csv(mock_path)
            if solo_pendientes:
                df_final = df_final[df_final['estado'] != 'PAGADA']
            if not df_final.empty:
                df_final['fecha_gasto'] = pd.to_datetime(df_final['fecha_gasto'])
                df_final['monto'] = pd.to_numeric(df_final['monto_original'])
                df_final['pagada'] = df_final['estado'] == 'PAGADA'
                return df_final.sort_values('fecha_gasto', ascending=False).reset_index(drop=True)
            return pd.DataFrame()
        return pd.DataFrame()

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
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        mock_path = os.path.join(base_dir, "data_mock", "sistema", "deudas", "pagos_deudas.csv")
        if os.path.exists(mock_path):
            df = pd.read_csv(mock_path)
            if not df.empty:
                df['fecha_pago'] = pd.to_datetime(df['fecha_pago'])
                df['monto_total'] = pd.to_numeric(df['monto_total'])
                return df.sort_values('fecha_pago', ascending=False)
            return pd.DataFrame()
        return pd.DataFrame()

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
