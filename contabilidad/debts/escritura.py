"""
Modulo de escritura de deudas a Supabase.
Proporciona funciones para crear y actualizar deudores y deudas.
"""

import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from typing import Optional, Dict, List
import uuid

# Credenciales de Supabase
SUPABASE_URL = "https://rcmdzvbxerumzxvnubfo.supabase.co"
SUPABASE_KEY = "sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw"

# Cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def crear_deudor(nombre: str) -> Dict:
    """
    Crea un nuevo deudor.
    
    Args:
        nombre: Nombre del deudor
        
    Returns:
        Dict con la informacion del deudor creado
    """
    data = {
        'nombre': nombre,
    }
    
    response = supabase.table('deudores').insert(data).execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0]
    else:
        raise Exception(f"Error al crear deudor: {response}")


def obtener_o_crear_deudor(nombre: str) -> Dict:
    """
    Obtiene un deudor existente por nombre o lo crea si no existe.
    
    Args:
        nombre: Nombre del deudor
        
    Returns:
        Dict con la informacion del deudor
    """
    # Buscar deudor existente
    response = supabase.table('deudores').select('*').eq('nombre', nombre).execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0]
    else:
        # Crear nuevo deudor
        return crear_deudor(nombre)


def crear_deuda(
    titulo: str,
    monto: float,
    deudor_id: str,
    fecha_gasto: datetime,
    pagada: bool = False,
    fecha_pago: Optional[datetime] = None,
    es_mi_deuda: bool = False
) -> Dict:
    """
    Crea una nueva deuda.
    NOTA: Si pagada=True, se creara la deuda y luego un pago automatico.

    es_mi_deuda=False -> te deben (pagaste tú por el otro).
    es_mi_deuda=True  -> tú debes (el otro pagó por ti).
    """
    data = {
        'titulo': titulo,
        'monto': monto,
        'deudor_id': deudor_id,
        'fecha_gasto': fecha_gasto.strftime('%Y-%m-%d'),
        'es_mi_deuda': bool(es_mi_deuda),
        # 'pagada': Ya no existe en la tabla base
    }
    
    # 1. Insertar Deuda
    response = supabase.table('deudas').insert(data).execute()
    
    if not response.data:
        raise Exception(f"Error al crear deuda: {response}")
    
    deuda_creada = response.data[0]
    
    # 2. Si estaba marcada como pagada, crear pago y detalle
    if pagada:
        f_pago = fecha_pago if fecha_pago else datetime.now()
        marcar_deuda_como_pagada(deuda_creada['id'], f_pago)
        
    return deuda_creada


def crear_deudas_bulk(deudas: List[Dict]) -> int:
    """
    Crea multiples deudas. NO procesa pagos automaticos en bulk por simplicidad.
    Se recomienda usar solo para deudas pendientes o procesar pagos aparte.
    """
    deudas_formateadas = []
    
    for deuda in deudas:
        # Solo tomamos campos validos para la tabla 'deudas'
        d_clean = {
            'titulo': deuda['titulo'],
            'monto': deuda['monto'],
            'deudor_id': deuda['deudor_id'],
            'fecha_gasto': deuda['fecha_gasto']
        }
        
        if isinstance(d_clean['fecha_gasto'], datetime):
            d_clean['fecha_gasto'] = d_clean['fecha_gasto'].strftime('%Y-%m-%d')
            
        deudas_formateadas.append(d_clean)
    
    if not deudas_formateadas:
        return 0
        
    response = supabase.table('deudas').insert(deudas_formateadas).execute()
    
    if response.data:
        return len(response.data)
    else:
        raise Exception(f"Error al crear deudas: {response}")


def marcar_deuda_como_pagada(deuda_id: str, fecha_pago: Optional[datetime] = None) -> Dict:
    """
    Saldar una deuda creando un Pago y un DetallePago.
    """
    if fecha_pago is None:
        fecha_pago = datetime.now()
        
    # 1. Obtener info de la deuda para saber cuanto pagar
    # Usamos la vista para saber saldo real
    res_vista = supabase.table('vista_estado_deudas').select('*').eq('id', deuda_id).execute()
    if not res_vista.data:
        raise Exception("Deuda no encontrada")
        
    info_deuda = res_vista.data[0]
    saldo = float(info_deuda['saldo_pendiente'])
    
    if saldo <= 0.01:
        return {"message": "La deuda ya esta pagada"}
        
    # 2. Crear Pago
    data_pago = {
        'deudor_id': info_deuda['deudor_id'],
        'monto_total': saldo,
        'fecha_pago': fecha_pago.strftime('%Y-%m-%d')
    }
    res_pago = supabase.table('pagos').insert(data_pago).execute()
    pago_id = res_pago.data[0]['id']
    
    # 3. Crear Detalle (Asignacion)
    data_detalle = {
        'pago_id': pago_id,
        'deuda_id': deuda_id,
        'monto_asignado': saldo
    }
    supabase.table('detalle_pagos').insert(data_detalle).execute()
    
    return {"pago_id": pago_id, "monto": saldo}


def registrar_pago(
    deudor_id: str,
    monto: float,
    es_mi_pago: bool,
    fecha: str,
    idem_key: Optional[str] = None,
    deudas_ids: Optional[List[str]] = None,
) -> Dict:
    """
    Registra un pago con el RPC , la única escritura de pagos.

    No se reparte aquí: Postgres cruza, asigna y deja el sobrante como saldo a favor con
    la misma regla que usa la app.  hace que reintentar no duplique el pago.
    Sin  el reparto es automático (cruce primero, luego FIFO); con ellas el
    pago va primero a esas deudas y el cruce después.
    """
    params = {
        'p_deudor_id': deudor_id,
        'p_monto': round(float(monto), 2),
        'p_es_mi_pago': bool(es_mi_pago),
        'p_fecha': fecha[:10],
        'p_idem_key': idem_key,
        'p_deudas_ids': deudas_ids or None,
    }
    return supabase.rpc('registrar_pago', params).execute().data


def previsualizar_pago(
    deudor_id: str,
    monto: float,
    es_mi_pago: bool,
    deudas_ids: Optional[List[str]] = None,
) -> Dict:
    """
    Cómo quedaría repartido un pago sin escribir nada:  con el pago
    planeado. Con deudas elegidas es exactamente el reparto que hará .
    """
    p_pago = {'monto': round(float(monto), 2), 'es_mi_pago': bool(es_mi_pago)}
    if deudas_ids:
        p_pago['deudas_ids'] = deudas_ids
    return supabase.rpc('estado_cuenta', {
        'p_deudor_id': deudor_id, 'p_pov': 'owner', 'p_pago': p_pago,
    }).execute().data


def editar_cruce(
    cruce_id: str,
    excluir: Optional[List[str]] = None,
    simular: bool = False,
    idem_key: Optional[str] = None,
) -> Dict:
    """
    Saca deudas del cruce de la última operación con el RPC `editar_cruce`.

    Sin `excluir` deshace el cruce entero. El pago real no se toca: solo se recortan los
    dos pagos virtuales para que el cruce siga cuadrando. Con `simular` no escribe y
    devuelve el estado tal como quedaría.
    """
    return supabase.rpc('editar_cruce', {
        'p_cruce_id': cruce_id,
        'p_excluir': excluir,
        'p_simular': bool(simular),
        'p_idem_key': idem_key,
    }).execute().data


def eliminar_deuda(deuda_id: str) -> bool:
    response = supabase.table('deudas').delete().eq('id', deuda_id).execute()
    return True


def eliminar_deudor(deudor_id: str) -> bool:
    response = supabase.table('deudores').delete().eq('id', deudor_id).execute()
    return True

if __name__ == "__main__":
    # Test basico
    print("Modulo de escritura actualizado. Importar para usar.")
