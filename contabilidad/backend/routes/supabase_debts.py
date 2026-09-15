from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime
import pandas as pd

from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


def _invalidar_deudas() -> None:
    """Una deuda o un pago nuevo mueve DEUDA_ACUMULADA: el dashboard no puede seguir
    sirviendo la serie cacheada."""
    try:
        from contabilidad.backend.storage.data_pipeline import get_pipeline

        pipeline = get_pipeline()
        pipeline.source_cache.invalidate('deuda_data')
        pipeline.invalidate_cache(scope='transformations')
    except Exception as e:
        logger.warning("No se pudo invalidar la caché de deudas: %s", e)

class SupabaseDebt(BaseModel):
    FECHA: str
    DESCRIPCION: str
    MONTO: float
    TIPO: str
    DEUDOR_NOMBRE: str
    DEUDOR_ID: Optional[str] = None
    PAGADA: bool
    FECHA_PAGO: Optional[str] = None
    FECHA_CREACION: Optional[str] = None
    ID: str | int
    ES_MI_DEUDA: bool = False
    SALDO_PENDIENTE: Optional[float] = None

@router.get("/", response_model=List[SupabaseDebt])
def get_supabase_debts(
    start_date: Optional[str] = Query(None, description="StartDate (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="EndDate (YYYY-MM-DD)"),
    pending_only: bool = Query(False, description="Show only pending debts"),
    deudor: Optional[str] = Query(None, description="Filter by debtor name")
):
    """
    Get debts from Supabase using deudas.lectura logic.
    """
    try:
        from contabilidad.debts.reading import obtener_deudas_para_analisis
        
        # Convert string dates to datetime if provided
        start_dt = pd.to_datetime(start_date) if start_date else None
        end_dt = pd.to_datetime(end_date) if end_date else None
        
        df = obtener_deudas_para_analisis(
            fecha_inicio=start_dt,
            fecha_fin=end_dt,
            solo_pendientes=pending_only
        )
        
        # Filter by debtor if provided
        if deudor:
             # Case insensitive match
             df = df[df['DEUDOR_NOMBRE'].astype(str).str.lower() == deudor.lower()]
        
        # Sanitize for JSON response
        df = df.copy()
        
        # Handle dates
        date_cols = ['FECHA', 'FECHA_PAGO', 'FECHA_CREACION']
        for col in date_cols:
             if col in df.columns:
                 df[col] = df[col].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(x) else None)

        # Handle NaNs in other columns
        df['DESCRIPCION'] = df['DESCRIPCION'].fillna('')
        df['MONTO'] = df['MONTO'].fillna(0.0)
        df['DEUDOR_NOMBRE'] = df['DEUDOR_NOMBRE'].fillna('Desconocido')
        df['PAGADA'] = df['PAGADA'].fillna(False)
        if 'DEUDOR_ID' in df.columns:
            df['DEUDOR_ID'] = df['DEUDOR_ID'].fillna('').astype(str)
        if 'ES_MI_DEUDA' in df.columns:
            df['ES_MI_DEUDA'] = df['ES_MI_DEUDA'].fillna(False).astype(bool)
        if 'SALDO_PENDIENTE' in df.columns:
            df['SALDO_PENDIENTE'] = df['SALDO_PENDIENTE'].fillna(0.0).astype(float)

        return df.to_dict(orient='records')
        
    except ImportError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Could not import deudas.lectura. Error: {e}"
        )
    except Exception as e:
        logger.error("Error al obtener deudas: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

class Deudor(BaseModel):
    id: str | int
    nombre: str
    neto: Optional[float] = None
    total_pendiente: Optional[float] = None
    saldo_favor: Optional[float] = None

@router.get("/deudores", response_model=List[Deudor])
def get_deudores():
    """Lista de deudores de Supabase para poblar los selects del etiquetado con sus saldos."""
    try:
        from contabilidad.debts.reading import listar_deudores, obtener_saldos_deudores
        df = listar_deudores()
        if df.empty:
            return []
        
        try:
            saldos = obtener_saldos_deudores()
        except Exception as s_err:
            logger.error("Error al calcular saldos de deudores: %s", s_err)
            saldos = {}

        df = df.copy()
        df['nombre'] = df['nombre'].fillna('').astype(str)
        
        records = df[['id', 'nombre']].to_dict(orient='records')
        for r in records:
            deudor_key = str(r['id'])
            s = saldos.get(deudor_key, {'neto': 0.0, 'total_pendiente': 0.0, 'saldo_favor': 0.0})
            r['neto'] = s.get('neto', 0.0)
            r['total_pendiente'] = s.get('total_pendiente', 0.0)
            r['saldo_favor'] = s.get('saldo_favor', 0.0)
            
        return records
    except Exception as e:
        logger.error("Error al obtener deudores: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/estado-cuenta")
def get_estado_cuenta(deudor_id: str = Query(..., description="ID del deudor")):
    """Estado de cuenta de un deudor: deudas (pagadas/pendientes) + pagos + resumen."""
    try:
        from contabilidad.debts.reading import obtener_estado_cuenta
        return obtener_estado_cuenta(deudor_id)
    except Exception as e:
        logger.error("Error al obtener estado de cuenta: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class CreateDeudorRequest(BaseModel):
    nombre: str

@router.post("/deudores", response_model=Deudor)
def create_deudor(req: CreateDeudorRequest):
    """Crea (o reutiliza) una persona para poder registrarle deudas desde el etiquetado."""
    nombre = req.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="nombre es requerido")
    try:
        from contabilidad.debts.escritura import obtener_o_crear_deudor
        d = obtener_o_crear_deudor(nombre)
        return {
            'id': d['id'],
            'nombre': d.get('nombre', nombre),
            'neto': 0.0,
            'total_pendiente': 0.0,
            'saldo_favor': 0.0,
        }
    except Exception as e:
        logger.error("Error al crear deudor: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class CreateDebtRequest(BaseModel):
    titulo: str
    monto: float
    deudor_id: str
    fecha_gasto: str  # YYYY-MM-DD
    # False = te deben (pagaste tú); True = tú debes (pagaron por ti).
    es_mi_deuda: bool = False

@router.post("/")
def create_debt(req: CreateDebtRequest):
    """
    Crea una deuda PENDIENTE en Supabase a partir de una transacción reembolsable.
    Devuelve la deuda creada (incluye su `id` para vincularla a la transacción).
    """
    try:
        from contabilidad.debts.escritura import crear_deuda

        try:
            fecha = datetime.strptime(req.fecha_gasto[:10], '%Y-%m-%d')
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"fecha_gasto inválida: {e}")

        if not req.deudor_id:
            raise HTTPException(status_code=400, detail="deudor_id es requerido")

        if abs(req.monto) < 0.01:
            raise HTTPException(status_code=400, detail="El monto de la deuda debe ser mayor a 0")

        deuda = crear_deuda(
            titulo=req.titulo.strip() or "Deuda",
            monto=abs(req.monto),
            deudor_id=req.deudor_id,
            fecha_gasto=fecha,
            pagada=False,
            es_mi_deuda=req.es_mi_deuda,
        )
        _invalidar_deudas()
        return deuda
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al crear deuda: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class PagoDeuda(BaseModel):
    deuda_id: str
    titulo: str
    monto_asignado: float

class SupabasePayment(BaseModel):
    id: str | int
    fecha_pago: Optional[str] = None
    monto_total: float
    deudor_id: str
    deudor_nombre: str
    # False = te pagaron; True = pagaste tú.
    es_mi_pago: bool = False
    es_compensacion: bool = False
    cruce_id: Optional[str] = None
    # Lo que no se asignó a ninguna deuda: saldo a favor de quien pagó.
    sobrante: float = 0.0
    deudas: List[PagoDeuda] = []

@router.get("/payments", response_model=List[SupabasePayment])
def get_supabase_payments(
    deudor: Optional[str] = Query(None, description="Filter by debtor name"),
    start_date: Optional[str] = Query(None, description="StartDate (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="EndDate (YYYY-MM-DD)"),
    incluir_cruces: bool = Query(False, description="Incluye los pagos virtuales de un cruce"),
):
    """Pagos de deudas con su dirección, las deudas que abonaron y el sobrante."""
    try:
        from contabilidad.debts.reading import obtener_pagos_para_analisis

        pagos = obtener_pagos_para_analisis(start_date, end_date, incluir_cruces)
        if deudor:
            pagos = [p for p in pagos if str(p['deudor_nombre']).lower() == deudor.lower()]
        return pagos
    except Exception as e:
        logger.error("Error al obtener pagos: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class CreatePaymentRequest(BaseModel):
    deudor_id: str
    monto: float
    # False = te pagaron; True = pagaste tú.
    es_mi_pago: bool = False
    fecha_pago: str  # YYYY-MM-DD
    # Clave del cliente: reintentar el guardado no duplica el pago.
    idem_key: Optional[str] = None
    # Vacío = reparto automático (cruce primero, luego FIFO).
    deudas_ids: Optional[List[str]] = None


def _validar_pago(req) -> str:
    if not req.deudor_id:
        raise HTTPException(status_code=400, detail="deudor_id es requerido")
    if not (abs(req.monto) > 0.01):
        raise HTTPException(status_code=400, detail="El monto del pago debe ser mayor a 0")
    fecha = getattr(req, 'fecha_pago', None)
    if fecha is None:
        return ''
    try:
        return datetime.strptime(fecha[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"fecha_pago inválida: {e}")


@router.post("/payments")
def create_payment(req: CreatePaymentRequest):
    """Registra un pago en Supabase por el RPC  (atómico e idempotente)."""
    fecha = _validar_pago(req)
    try:
        from contabilidad.debts.escritura import registrar_pago

        res = registrar_pago(
            deudor_id=req.deudor_id,
            monto=abs(req.monto),
            es_mi_pago=req.es_mi_pago,
            fecha=fecha,
            idem_key=req.idem_key or None,
            deudas_ids=req.deudas_ids or None,
        ) or {}
        if not res.get('pago_id'):
            raise HTTPException(status_code=500, detail="Supabase no devolvió el pago creado")
        _invalidar_deudas()
        return {
            'pago_id': str(res['pago_id']),
            'sobrante': float(res.get('sobrante') or 0),
            'repetido': bool(res.get('repetido')),
            'cruce': res.get('cruce'),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al registrar pago: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class PreviewPaymentRequest(BaseModel):
    deudor_id: str
    monto: float
    es_mi_pago: bool = False
    deudas_ids: Optional[List[str]] = None


@router.post("/payments/preview")
def preview_payment(req: PreviewPaymentRequest):
    """Reparto que tendría un pago, sin escribir nada. Solo lectura."""
    _validar_pago(req)
    try:
        from contabilidad.debts.escritura import previsualizar_pago

        estado = previsualizar_pago(req.deudor_id, abs(req.monto), req.es_mi_pago,
                                    req.deudas_ids or None) or {}
        plan = (estado.get('resumen') or {}).get('pago_planeado') or {}
        deudas = [{
            'deuda_id': str(d.get('id')),
            'titulo': d.get('titulo') or '—',
            'fecha_gasto': d.get('fecha_gasto'),
            'es_mi_deuda': bool(d.get('es_tu_deuda')),
            'saldo_real': float(d.get('saldo_real') or 0),
            'pago_planeado': float(d.get('pago_planeado') or 0),
        } for d in (estado.get('deudas') or [])]
        return {
            'asignado': float(plan.get('asignado') or 0),
            'sobrante': float(plan.get('sobrante') or 0),
            'deudas': deudas,
            'cruce_monto': float((estado.get('cruce_sugerido') or {}).get('monto') or 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al previsualizar pago: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class EditarCruceRequest(BaseModel):
    # Deudas que salen del cruce. Vacío o ausente = deshacer el cruce entero.
    excluir: Optional[List[str]] = None
    # Clave del cliente: reintentar el guardado no repite la edición.
    idem_key: Optional[str] = None


def _respuesta_edicion(res: dict) -> dict:
    """
    El resultado de `editar_cruce` con lo que la pantalla necesita de cada deuda: cuánto
    se cruzaba, cuánto se cruza ahora y con cuánto queda de verdad (el saldo a favor de
    quien pagó puede cubrir lo que se reabre).
    """
    estado = res.get('estado') or {}
    por_id = {str(d.get('id')): d for d in (estado.get('deudas') or [])}
    items = []
    for it in res.get('items') or []:
        d = por_id.get(str(it.get('deuda_id'))) or {}
        items.append({
            'deuda_id': str(it.get('deuda_id')),
            'titulo': it.get('titulo') or '—',
            'fecha_gasto': it.get('fecha_gasto'),
            'es_tu_deuda': it.get('lado') == 'tu_debes',
            'excluida': bool(it.get('excluida')),
            'antes': float(it.get('antes') or 0),
            'despues': float(it.get('despues') or 0),
            'saldo_real': float(d.get('saldo_real') or 0),
            'abono_saldo_favor': float(d.get('abono_saldo_favor') or 0),
        })
    resumen = estado.get('resumen') or {}
    return {
        'cruce_id': str(res.get('cruce_id')),
        'monto_antes': float(res.get('monto_antes') or 0),
        'monto_despues': float(res.get('monto_despues') or 0),
        'eliminado': bool(res.get('eliminado')),
        'simulado': bool(res.get('simulado')),
        'repetido': bool(res.get('repetido')),
        'neto': float(resumen.get('neto') or 0),
        'cruce_disponible': float((estado.get('cruce_sugerido') or {}).get('monto') or 0),
        'items': items,
    }


def _editar_cruce(cruce_id: str, req: EditarCruceRequest, simular: bool) -> dict:
    from postgrest.exceptions import APIError
    from contabilidad.debts.escritura import editar_cruce

    try:
        res = editar_cruce(cruce_id, excluir=req.excluir or None, simular=simular,
                           idem_key=None if simular else (req.idem_key or None)) or {}
    except APIError as e:
        # Las validaciones del RPC (no es el último, deuda ajena…) son errores del pedido.
        if e.code == 'P0001':
            raise HTTPException(status_code=400, detail=e.message)
        logger.error("Error al editar cruce %s: %s", cruce_id, e)
        raise HTTPException(status_code=500, detail=e.message or str(e))
    except Exception as e:
        logger.error("Error al editar cruce %s: %s", cruce_id, e)
        raise HTTPException(status_code=500, detail=str(e))
    return _respuesta_edicion(res)


@router.post("/cruces/{cruce_id}/editar/preview")
def preview_editar_cruce(cruce_id: str, req: EditarCruceRequest):
    """Cómo quedaría el cruce sin esas deudas. No escribe nada."""
    return _editar_cruce(cruce_id, req, simular=True)


@router.post("/cruces/{cruce_id}/editar")
def editar_cruce(cruce_id: str, req: EditarCruceRequest):
    """Saca deudas del cruce de la última operación (o lo deshace entero). El pago real
    no se toca; las deudas reabiertas se vuelven a cruzar en el siguiente pago."""
    out = _editar_cruce(cruce_id, req, simular=False)
    _invalidar_deudas()
    return out


class EditarPagoRequest(BaseModel):
    # None = no se toca. La nota vacía la borra.
    fecha_pago: Optional[str] = None  # YYYY-MM-DD
    nota: Optional[str] = None
    idem_key: Optional[str] = None


@router.post("/payments/{pago_id}/editar")
def editar_pago(pago_id: str, req: EditarPagoRequest):
    """Cambia la fecha y/o la nota de un pago. La fecha arrastra al cruce que disparó el
    pago; el monto y el reparto no se tocan."""
    from postgrest.exceptions import APIError
    from contabilidad.debts.escritura import editar_pago as _editar

    fecha = None
    if req.fecha_pago:
        try:
            fecha = datetime.strptime(req.fecha_pago[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"fecha_pago inválida: {e}")
    if fecha is None and req.nota is None:
        raise HTTPException(status_code=400, detail="No hay cambios que guardar")

    try:
        res = _editar(pago_id, fecha=fecha, nota=req.nota, idem_key=req.idem_key or None) or {}
    except APIError as e:
        # Las validaciones del RPC (cruce, sin cambios, nota larga) son errores del pedido.
        if e.code == 'P0001':
            raise HTTPException(status_code=400, detail=e.message)
        logger.error("Error al editar pago %s: %s", pago_id, e)
        raise HTTPException(status_code=500, detail=e.message or str(e))
    except Exception as e:
        logger.error("Error al editar pago %s: %s", pago_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    # La fecha mueve el día en que el pago cuenta en DEUDA_ACUMULADA.
    _invalidar_deudas()
    return res
