from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from contabilidad.backend.logger import get_logger
from contabilidad.backend.models.investment_models import (
    ApplyDetectionRequest,
    FlowIn,
    InvestmentsFromAccountsResponse,
    PositionIn,
    SaldoInicialIn,
    PositionUpdate,
    SplitRequest,
)
from contabilidad.backend.services import investments as posiciones_service
from contabilidad.backend.services.investment_service import InvestmentService

logger = get_logger(__name__)
router = APIRouter()

@router.get("/from-accounts", response_model=InvestmentsFromAccountsResponse)
def get_investments_from_accounts():
    """
    Get investments from account data using the ver_inversiones logic.
    """
    try:
        service = InvestmentService()
        return service.get_investments_from_accounts()
    except Exception as e:
        logger.error(f"Error getting investments from accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chart-data")
def get_investment_chart_data():
    """
    Get chart data for investment visualization.
    """
    try:
        service = InvestmentService()
        return service.get_investment_chart_data()
    except Exception as e:
        logger.error(f"Error processing investment chart data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Posiciones guardadas ──────────────────────────────────────────────────────

@router.get("/portfolios")
def list_portfolios():
    """Grupos que hacen de portafolio de inversión, con su conteo de posiciones."""
    return posiciones_service.list_portfolios()


@router.put("/portfolios/{portafolio_id}/saldo-inicial")
def configurar_saldo_inicial(portafolio_id: str, cuerpo: SaldoInicialIn):
    """Fija el residual de partida del portafolio, o lo devuelve a la deducción.

    `saldo: null` borra la configuración; `saldo: 0` afirma que arranca vacío. No son lo
    mismo: el primero pide deducirlo de `pagos.csv` y el segundo lo da por sabido.
    """
    try:
        resultado = posiciones_service.configurar_saldo_inicial(portafolio_id, cuerpo.saldo)
    except posiciones_service.ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        from contabilidad.backend.storage.data_pipeline import get_pipeline

        get_pipeline().invalidate_cache(scope='transformations')
    except Exception:
        pass

    return resultado


@router.get("/portfolios/{portafolio_id}/analysis")
def get_portfolio_analysis(portafolio_id: str):
    """El portafolio entero: cuánta plata hay, cuánta está rindiendo y cuánta ha dejado.

    Es la unidad que el usuario llama «una inversión» —el mismo dinero rodando de
    certificado en certificado—; `/positions/{id}/analysis` es el detalle al que se baja
    desde aquí.
    """
    analisis = posiciones_service.get_portfolio_analysis(portafolio_id)
    if analisis is None:
        raise HTTPException(status_code=404, detail="Portafolio no encontrado")
    return analisis


@router.get("/summary")
def get_summary():
    """KPIs globales y por portafolio, más el rendimiento por año de cierre."""
    try:
        return posiciones_service.get_summary()
    except Exception as e:
        logger.error(f"Error calculando el resumen de inversiones: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline")
def get_timeline():
    """Serie diaria de capital invertido e interés acumulado, con aperturas y cierres."""
    try:
        return posiciones_service.get_timeline()
    except Exception as e:
        logger.error(f"Error calculando la evolución de inversiones: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/neutralization/preview")
def get_neutralization_preview():
    """Los pagos fijos que saldrían de las posiciones, comparados día a día con los de hoy.

    **Solo lectura.** Es la pantalla con la que se valida la fase 6 antes de migrar nada:
    `pagos.csv` no se toca aquí ni en ningún otro lado del módulo.
    """
    try:
        return posiciones_service.get_neutralization_preview()
    except Exception as e:
        logger.error(f"Error generando la previsualización de neutralización: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
def list_positions(
    portafolio_id: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
):
    return posiciones_service.list_positions(portafolio_id=portafolio_id, estado=estado, tipo=tipo)


@router.post("/positions")
def create_position(position: PositionIn):
    try:
        return posiciones_service.create_position(position.model_dump())
    except posiciones_service.ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/flows")
def registrar_flujo(flujo: FlowIn):
    """Registra dinero que entró o salió del portafolio sin pasar por una inversión.

    El caso de uso: la matrícula que se paga con lo que devolvió un certificado. Hoy eso
    solo queda anotado como la fecha de fin de un pago fijo, que el generador de la fase 6
    no puede ver — y por eso arrastra para siempre una plata que ya no está.
    """
    try:
        return posiciones_service.registrar_flujo(
            portafolio_id=flujo.portafolio_id,
            fecha=flujo.fecha,
            monto=flujo.monto,
            direccion=flujo.direccion,
            nota=flujo.nota,
            tx_id=flujo.tx_id,
        )
    except posiciones_service.ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/flows/preview")
def preview_flujo(
    portafolio_id: str = Query(...),
    fecha: str = Query(...),
    monto: float = Query(0.0),
    direccion: str = Query('salida'),
):
    """El residual del portafolio antes y después del flujo, **sin escribir nada**.

    Es lo que hace seguro el formulario: si sacar la matrícula deja el portafolio en
    negativo, o falta registrar algo antes o el monto está mal.
    """
    antes = posiciones_service.residual_portafolio(portafolio_id, fecha)
    if antes is None:
        raise HTTPException(status_code=404, detail="Portafolio no encontrado")

    signo = -1 if direccion == 'salida' else 1
    return {
        'fecha': fecha,
        'residual_antes': antes,
        'residual_despues': round(antes + signo * abs(monto), 2),
    }


@router.get("/cut/status")
def estado_corte():
    """Dónde está la fase 6 ahora mismo. Solo lectura."""
    from contabilidad.backend.services.investments import corte
    return corte.estado()


@router.post("/cut/shadow")
def sembrar_sombra():
    """Materializa los pagos generados en grupos `shadow`, que nadie aplica. Idempotente.

    No toca los grupos originales: el dashboard sigue exactamente igual.
    """
    from contabilidad.backend.services.investments import corte
    try:
        return corte.sembrar_sombra()
    except Exception as e:
        logger.error(f"Error sembrando la sombra: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cut/shadow")
def limpiar_sombra():
    from contabilidad.backend.services.investments import corte
    return {'grupos_borrados': corte.limpiar_sombra()}


@router.get("/cut/verify")
def verificar_corte():
    """Compara la función escalón antes y después del corte, día a día. **No escribe.**"""
    from contabilidad.backend.services.investments import corte
    return corte.verificar()


@router.get("/cut/regenerate/preview")
def previsualizar_regeneracion(portafolio_id: Optional[str] = Query(None)):
    """Qué cambiaría al poner los pagos generados al día. **No escribe.**"""
    from contabilidad.backend.services.investments import corte
    return corte.previsualizar_regeneracion(portafolio_id)


@router.post("/cut/regenerate")
def regenerar_pagos(portafolio_id: Optional[str] = Query(None)):
    """Reescribe los pagos generados de un portafolio ya cortado desde sus posiciones.

    A diferencia del corte, esto **sí** está expuesto por HTTP: reemplaza en su sitio, no
    puede duplicar el patrimonio, y es la operación normal cuando entra una inversión
    nueva. Correrla sin que nada haya cambiado no mueve la serie.
    """
    from contabilidad.backend.services.investments import corte

    resultado = corte.regenerar(portafolio_id)
    if not resultado['ok']:
        raise HTTPException(status_code=400, detail=resultado['error'])

    try:
        from contabilidad.backend.storage.data_pipeline import get_pipeline

        get_pipeline().invalidate_cache(scope='transformations')
    except Exception:
        pass

    return resultado


@router.get("/positions/{position_id}")
def get_position(position_id: str):
    posicion = posiciones_service.get_position(position_id)
    if posicion is None:
        raise HTTPException(status_code=404, detail="Posición no encontrada")
    return posicion


@router.get("/positions/{position_id}/analysis")
def get_position_analysis(position_id: str):
    """Una inversión de cerca: su curva de crecimiento, lo que falta y lo que rindió.

    La curva reparte el interés día a día en vez de dejarlo como el escalón del día del
    cierre. Para una posición cerrada la tasa se despeja del interés real, así que la
    serie aterriza en el número del banco; para una abierta hace falta la tasa pactada y,
    si no está, se devuelve `apto: false` con el motivo en vez de una recta inventada.
    """
    analisis = posiciones_service.get_analysis(position_id)
    if analisis is None:
        raise HTTPException(status_code=404, detail="Posición no encontrada")
    return analisis


@router.put("/positions/{position_id}")
def update_position(position_id: str, updates: PositionUpdate):
    try:
        actualizada = posiciones_service.update_position(
            position_id, updates.model_dump(exclude_unset=True)
        )
    except posiciones_service.ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if actualizada is None:
        raise HTTPException(status_code=404, detail="Posición no encontrada")
    return actualizada


@router.delete("/positions/{position_id}")
def delete_position(position_id: str):
    if not posiciones_service.delete_position(position_id):
        raise HTTPException(status_code=404, detail="Posición no encontrada")
    return {"status": "deleted", "id": position_id}


@router.post("/positions/{position_id}/split")
def split_position(position_id: str, req: SplitRequest):
    """Reparte un certificado entre varios portafolios, en posiciones hermanas."""
    try:
        partes = posiciones_service.split_position(
            position_id, [p.model_dump() for p in req.partes]
        )
    except posiciones_service.ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not partes:
        raise HTTPException(status_code=404, detail="Posición no encontrada")
    return {"status": "split", "partes": partes}


@router.post("/detect")
def detect():
    """Corre el detector y devuelve el diff contra lo guardado. No escribe nada.

    Es POST porque en la UI es una acción ("conciliar"), no una lectura de pantalla:
    recorre todo el extracto y su resultado no se cachea.
    """
    try:
        return posiciones_service.reconcile()
    except Exception as e:
        logger.error(f"Error reconciliando inversiones: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect/apply")
def apply_detection(req: ApplyDetectionRequest):
    """Confirma el diff: crea las posiciones nuevas y actualiza las que cambiaron.

    Nunca sobrescribe una posición con `origen='manual'` (las siembras no salen del
    banco y el detector no las puede reconstruir).
    """
    try:
        return posiciones_service.apply_detection(
            tx_apertura_ids=req.tx_apertura_ids,
            asignaciones=req.asignaciones,
            portafolio_id=req.portafolio_id,
            incluir_cambiadas=req.incluir_cambiadas,
            usar_sugerencias=req.usar_sugerencias,
        )
    except posiciones_service.ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error aplicando la detección: {e}")
        raise HTTPException(status_code=500, detail=str(e))
