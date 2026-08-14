"""
posiciones.py — Las posiciones guardadas: CRUD, derivados y reconciliación.

El detector (`detector.py`) lee el banco y no escribe nada. Este módulo es la otra
mitad: lo que quedó guardado en `posiciones.csv`/`movimientos.csv`, y cómo se compara
contra lo que el banco dice hoy.

Dos reglas que sostienen todo lo demás:

1. **Los montos son derivados.** `capital`, `interes` y `retencion` se calculan sumando
   movimientos, nunca se guardan. Así una posición externa con aportes parciales usa el
   mismo camino que un plazo fijo.

2. **Lo manual no se pisa.** `reconcile()` devuelve un diff y no escribe; `apply_detection()`
   escribe solo lo que le pidan y jamás toca una posición con `origen='manual'`. Las
   siembras (las inversiones abiertas antes de que empiece el historial bancario, los
   ajustes de residual) no salen del banco, así que ninguna corrida del detector puede
   reconstruirlas: si las sobrescribiera, se perderían sin aviso.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd

from contabilidad.backend.logger import get_logger
from contabilidad.backend.services.investments.detector import (
    DAYS_PER_YEAR,
    AMOUNT_TOLERANCE,
    DetectedPosition,
    DetectionResult,
    detect_positions,
)
from contabilidad.backend.services.investments import metricas, portafolios
from contabilidad.backend.storage.investments_storage import InvestmentStorage
from contabilidad.backend.storage.variables_storage import InterpolationStorage

logger = get_logger(__name__)


#: `ajuste` no es una inversión: es plata de inversión que se movió sin entrar a una
#: posición (la inyección desde la tarjeta de la madre, el sobrante que quedó suelto, la
#: corrección de −600). Existe porque el escalón de neutralización tiene que poder
#: reproducirse, y esos movimientos son parte del residual aunque no rindan intereses.
#:
#: `flujo` es dinero que **entra o sale del portafolio y no vuelve**: la matrícula que se
#: paga con lo que devolvió un certificado, la plata que llega de otro lado. Es distinto
#: de un `ajuste` justamente en eso: el ajuste es un tramo acotado que se cierra y
#: devuelve la plata; el flujo es definitivo. Sin él, el generador de la fase 6 sigue
#: arrastrando para siempre una plata que ya no está —que es exactamente lo que hacía
#: que `Uni` divergiera 14.127,67 y `Madre` 13.982,05.
POSITION_TYPES = ('plazo_fijo', 'valuada', 'ajuste', 'flujo')

#: La dirección de un flujo, traducida al movimiento que la representa. `aporte` saca la
#: plata del bolsillo de inversión y `retiro` la devuelve: son los mismos signos de
#: `metricas.SIGNO`, así que el residual de la neutralización sale solo, sin código nuevo.
FLOW_DIRECTIONS = {'salida': 'aporte', 'entrada': 'retiro'}

POSITION_STATES = ('abierta', 'cerrada')

ORIGINS = ('detectado', 'manual')

MOVEMENT_TYPES = ('aporte', 'retiro', 'interes', 'retencion', 'comision', 'dividendo')

INSTITUCION_POR_DEFECTO = 'Pichincha'

#: Campos que el detector reconstruye y que por lo tanto puede reclamar como suyos.
#: Si alguno difiere entre lo guardado y lo detectado, la posición sale como "cambiada".
CAMPOS_RECONCILIADOS = (
    'fecha_apertura',
    'fecha_cierre',
    'tx_cierre_id',
    'capital',
    'interes',
    'retencion',
)


class ValidationError(ValueError):
    """Dato inválido enviado por el usuario (la ruta lo traduce a un 400)."""


# ── Derivados ────────────────────────────────────────────────────────────────

def _suma(movimientos: Iterable[Dict[str, Any]], tipo: str) -> float:
    return round(sum(float(m.get('monto') or 0.0) for m in movimientos if m.get('tipo') == tipo), 2)


def _to_date(value: Any) -> Optional[date]:
    if value is None or value == '':
        return None
    try:
        ts = pd.to_datetime(value)
    except (ValueError, TypeError):
        return None
    return None if pd.isna(ts) else ts.date()


def calcular_totales(movimientos: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    """Los montos de una posición, sumados desde sus movimientos.

    `capital` es todo lo que se puso alguna vez; `capital_vigente` es lo que sigue
    adentro. En un plazo fijo cerrado el primero es el nominal del certificado y el
    segundo es cero, que es justo lo que hace falta para no contar como invertida plata
    que ya volvió.
    """
    aportes = _suma(movimientos, 'aporte')
    retiros = _suma(movimientos, 'retiro')
    interes = _suma(movimientos, 'interes')
    dividendos = _suma(movimientos, 'dividendo')
    retencion = _suma(movimientos, 'retencion')
    comisiones = _suma(movimientos, 'comision')

    return {
        'capital': aportes,
        'capital_vigente': round(aportes - retiros, 2),
        'retirado': retiros,
        'interes': interes,
        'dividendos': dividendos,
        'retencion': retencion,
        'comisiones': comisiones,
        'neto': round(interes + dividendos - retencion - comisiones, 2),
    }


def _tna(capital: float, interes: float, dias: Optional[int]) -> Optional[float]:
    """Tasa nominal anual aproximada, en porcentaje, sobre días calendario y base 365.

    Es una estimación para comparar posiciones entre sí, no la tasa pactada: el banco
    liquida sobre el plazo pactado con base 360 (ver `tna_pactada`).
    """
    if not dias or capital <= 0:
        return None
    return round(interes / capital * DAYS_PER_YEAR / dias * 100, 4)


def _tna_pactada(capital: float, interes: float, plazo_pactado_dias: Optional[int]) -> Optional[float]:
    """La tasa con la que el banco de verdad liquidó: plazo pactado, base 360.

    La posición 2025-11-18 → 2025-12-19 son 31 días calendario, pero sus 67,43 sobre
    27.000 son 30 días al 3 % base 360. Sin `plazo_pactado_dias` esto no se puede
    calcular, y por eso ese campo se pide a mano al confirmar una posición detectada.
    """
    if not plazo_pactado_dias or capital <= 0:
        return None
    return round(interes / capital * 360 / plazo_pactado_dias * 100, 4)


#: Los bancos cotizan en pasos de 0,05 %. Es lo que convierte la inferencia en una lectura
#: y no en una regresión: si el número que sale no cae en un peldaño, no se afirma nada.
PASO_TASA = 0.0005

#: Cuánto puede separarse el interés recalculado del que pagó el banco para dar la
#: inferencia por buena: un centavo, que es la resolución con la que el banco liquida.
#: Medido sobre los 15 plazos fijos reales, el peor caso es 0,0053.
#:
#: La fuerza de esta comprobación depende del tamaño de la posición: un peldaño de 0,05 %
#: sobre 27.000 a 31 días son 1,16 USD, así que acertar dentro de un centavo es ~1 % de
#: probabilidad por azar. Sobre montos pequeños el peldaño se encoge y la prueba pierde
#: valor —por eso lo que sostiene la convención no es una posición sino que **las 15**
#: caigan en su peldaño a la vez, y ninguna lo haga con base 365.
TOLERANCIA_INFERENCIA = 0.01


def inferir_plazo_y_tasa(capital: float, interes: float,
                         apertura: Optional[date], cierre: Optional[date]) -> Dict[str, Any]:
    """Deduce el plazo y la tasa pactados de una posición ya cerrada.

    Se apoya en dos hechos comprobados sobre los 15 plazos fijos del historial:

    1. **El banco liquida actual/360** y el certificado se cancela a vencimiento, así que
       el plazo pactado son los días calendario entre apertura y cierre.
    2. **La tasa cae en un múltiplo de 0,05 %.** Despejándola de
       `interes = capital · tasa · plazo/360` salen 8,70 / 7,95 / 4,80 / 6,60 / 6,50 /
       5,80 / 5,50 / 5,30 / 4,75 / 2,90 / 3,55 … — todas exactas. Con base 365 no cae
       ninguna, y eso es lo que identifica la convención.

    La comprobación es el propio interés: se redondea la tasa al peldaño y se recalcula lo
    que el banco habría pagado. Si no coincide al centavo, la hipótesis no se sostiene para
    esa posición y **no se devuelve nada**, en vez de un número aproximado que luego nadie
    distinguiría de un dato real.

    Una posición **abierta** no se puede inferir: sin cierre no hay plazo del que despejar.
    Ahí sigue haciendo falta capturar la tasa a mano, y por eso el campo no desaparece.
    """
    vacio = {'plazo_inferido': None, 'tasa_inferida': None, 'inferencia': None}
    if apertura is None or cierre is None or capital <= 0 or interes <= 0:
        return vacio

    plazo = (cierre - apertura).days
    if plazo <= 0:
        return vacio

    cruda = interes / capital * 360 / plazo
    tasa = round(cruda / PASO_TASA) * PASO_TASA
    if tasa <= 0:
        return vacio

    recalculado = capital * tasa * plazo / 360
    if abs(recalculado - interes) > TOLERANCIA_INFERENCIA:
        return vacio

    return {
        'plazo_inferido': plazo,
        'tasa_inferida': round(tasa * 100, 4),
        'inferencia': (f'Deducida: {interes:,.2f} sobre {capital:,.2f} en {plazo} días '
                       f'son {tasa * 100:.2f} % base 360 (±{abs(recalculado - interes):.2f}).'),
    }


def armar_vista(posicion: Dict[str, Any], movimientos: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Posición + sus movimientos + los montos derivados, lista para la API."""
    totales = calcular_totales(movimientos)

    apertura = _to_date(posicion.get('fecha_apertura'))
    cierre = _to_date(posicion.get('fecha_cierre'))
    dias = (cierre - apertura).days if apertura and cierre else None

    inferido = inferir_plazo_y_tasa(totales['capital'], totales['interes'], apertura, cierre)

    # El plazo capturado a mano manda siempre: es un dato, no una deducción. El inferido
    # solo rellena el hueco, y viaja aparte para que la UI pueda decir cuál está mostrando.
    plazo_efectivo = posicion.get('plazo_pactado_dias') or inferido['plazo_inferido']

    vista = {
        **posicion,
        **totales,
        **inferido,
        'dias': dias,
        'tna': _tna(totales['capital'], totales['interes'], dias),
        'tna_pactada': _tna_pactada(totales['capital'], totales['interes'], plazo_efectivo),
        'plazo_es_inferido': not posicion.get('plazo_pactado_dias') and bool(inferido['plazo_inferido']),
        'movimientos': list(movimientos),
    }

    # Lo que una posición abierta lleva ganado y cuánto le falta. Solo se puede saber si
    # se capturó la tasa y el plazo pactados; si no, quedan en None a propósito.
    vista['interes_devengado'] = metricas.interes_devengado(vista)
    vista['dias_restantes'] = metricas.dias_restantes(vista)
    vista['fecha_vencimiento'] = metricas.fecha_vencimiento(vista)
    return vista


# ── Lectura ──────────────────────────────────────────────────────────────────

def list_positions(portafolio_id: Optional[str] = None,
                   estado: Optional[str] = None,
                   tipo: Optional[str] = None) -> List[Dict[str, Any]]:
    posiciones = InvestmentStorage.get_positions(portafolio_id=portafolio_id, estado=estado)
    if tipo is not None:
        posiciones = [p for p in posiciones if p['tipo'] == tipo]

    por_posicion = InvestmentStorage.get_movements_by_position()
    return [armar_vista(p, por_posicion.get(p['id'], [])) for p in posiciones]


def get_position(position_id: str) -> Optional[Dict[str, Any]]:
    posicion = InvestmentStorage.get_position(position_id)
    if posicion is None:
        return None
    return armar_vista(posicion, InvestmentStorage.get_movements(position_id))


def get_analysis(position_id: str) -> Optional[Dict[str, Any]]:
    """El análisis de una sola posición: cómo creció, cómo puede seguir y cuánto rindió.

    Se importa dentro de la función igual que `neutralizacion`: `analisis` importa
    `metricas`, y traerlo arriba cerraría el ciclo con este módulo.
    """
    from contabilidad.backend.services.investments import analisis
    vista = get_position(position_id)
    if vista is None:
        return None
    return analisis.analizar(vista)


def get_portfolio_analysis(portafolio_id: str) -> Optional[Dict[str, Any]]:
    """Cómo creció un portafolio entero: el bolsillo que rueda de certificado en certificado.

    Es la unidad que el usuario llama «una inversión». El arranque de la curva es el
    `saldo_inicial` de `grupos.csv`; si no está configurado, la serie empieza en cero y la
    respuesta lo dice con `saldo_inicial_configurado: false` en vez de deducir por detrás
    un número que la pantalla presentaría como dato.
    """
    from contabilidad.backend.services.investments import analisis
    portafolio = next((p for p in list_portfolios() if p['id'] == portafolio_id), None)
    if portafolio is None:
        return None
    return analisis.analizar_portafolio(list_positions(), _con_saldo_inicial([portafolio])[0])


def get_summary() -> Dict[str, Any]:
    """KPIs globales, por portafolio y separando lo propio de lo que está en custodia."""
    vistas = list_positions()
    return {
        **metricas.resumen(vistas, list_portfolios()),
        'por_anio': metricas.por_anio(vistas),
    }


def get_timeline() -> Dict[str, Any]:
    """Serie diaria de capital invertido e interés acumulado, con sus eventos."""
    return metricas.timeline(list_positions(), list_portfolios())


def get_neutralization_preview() -> Dict[str, Any]:
    """Los pagos fijos que saldrían de las posiciones, comparados con los de hoy.

    Solo lectura: es la pantalla con la que se valida la migración antes de hacerla.
    """
    from contabilidad.backend.services.investments import neutralizacion
    portafolios = [p for p in list_portfolios() if p['es_inversion']]
    return neutralizacion.preview(list_positions(), _con_saldo_inicial(portafolios))


def configurar_saldo_inicial(portafolio_id: str, saldo: Optional[float]) -> Dict[str, Any]:
    """Fija (o borra) el saldo inicial de un portafolio en `grupos.csv`.

    Es la pieza que permite retirar `pagos.csv`: hoy el residual de partida se deduce de
    los pagos escritos a mano, y cuando esos desaparezcan no habrá de dónde deducirlo.

    `saldo=None` **borra** la configuración y devuelve el portafolio a la deducción. Es
    distinto de `saldo=0`, que afirma que el portafolio arranca vacío; por eso se escribe
    la celda en blanco y no un cero.
    """
    grupo = InterpolationStorage.get_group(portafolio_id)
    if grupo is None:
        raise ValidationError(f"El portafolio {portafolio_id!r} no existe en grupos.csv")

    if saldo is None:
        valor: Any = ''
    else:
        try:
            valor = round(float(saldo), 2)
        except (TypeError, ValueError):
            raise ValidationError(f"Saldo inicial inválido: {saldo!r}")

    actualizado = InterpolationStorage.update_group(portafolio_id, {'saldo_inicial': valor})
    return {
        'portafolio_id': portafolio_id,
        'nombre': actualizado['name'],
        'saldo_inicial': actualizado['saldo_inicial'],
        'saldo_inicial_configurado': actualizado['saldo_inicial_configurado'],
    }


def _con_saldo_inicial(portafolios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """`list_portfolios()` no trae `saldo_inicial`, y el residual arranca de ahí.

    Viaja junto con `saldo_inicial_configurado`, que es lo que distingue «configurado en
    cero» de «sin configurar»: los dos valen 0.0 y solo uno pide que se deduzca.
    """
    completos = []
    for portafolio in portafolios:
        grupo = InterpolationStorage.get_group(portafolio['id']) or {}
        completos.append({
            **portafolio,
            'saldo_inicial': grupo.get('saldo_inicial', 0.0),
            'saldo_inicial_configurado': bool(grupo.get('saldo_inicial_configurado')),
        })
    return completos


def list_portfolios() -> List[Dict[str, Any]]:
    """Los grupos que hacen de portafolio, con cuántas posiciones cuelgan de cada uno.

    Un grupo cuenta como portafolio si está marcado `es_inversion` o si ya hay una
    posición apuntándole. Lo segundo evita que una posición quede huérfana en la UI
    porque a alguien se le olvidó marcar el grupo.
    """
    conteo: Dict[str, int] = {}
    for posicion in InvestmentStorage.get_positions():
        if posicion['portafolio_id']:
            conteo[posicion['portafolio_id']] = conteo.get(posicion['portafolio_id'], 0) + 1

    encontrados: List[Dict[str, Any]] = []
    for grupo in InterpolationStorage.get_groups(type_filter=None):
        if not grupo.get('es_inversion') and grupo['id'] not in conteo:
            continue
        encontrados.append({
            'id': grupo['id'],
            'name': grupo['name'],
            'description': grupo.get('description', ''),
            'es_inversion': bool(grupo.get('es_inversion')),
            # Plata de otro que vive en tu cuenta: se sigue igual, pero no es patrimonio tuyo.
            'es_custodia': bool(grupo.get('es_custodia')),
            'saldo_inicial': float(grupo.get('saldo_inicial') or 0.0),
            'saldo_inicial_configurado': bool(grupo.get('saldo_inicial_configurado')),
            'posiciones': conteo.get(grupo['id'], 0),
        })
    return encontrados


# ── Escritura ────────────────────────────────────────────────────────────────

def _validar_movimientos(movimientos: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    limpios: List[Dict[str, Any]] = []
    for movimiento in movimientos:
        tipo = str(movimiento.get('tipo') or '').strip()
        if tipo not in MOVEMENT_TYPES:
            raise ValidationError(
                f"Tipo de movimiento inválido: {tipo!r}. Válidos: {', '.join(MOVEMENT_TYPES)}"
            )
        if _to_date(movimiento.get('fecha')) is None:
            raise ValidationError(f"El movimiento {tipo!r} necesita una fecha válida")
        try:
            monto = float(movimiento.get('monto'))
        except (TypeError, ValueError):
            raise ValidationError(f"El movimiento {tipo!r} necesita un monto numérico")
        if monto < 0:
            # El signo lo da el tipo. Un aporte de −500 sería un retiro escrito al revés,
            # y sumar eso rompe los derivados sin que nada avise.
            raise ValidationError(
                f"El movimiento {tipo!r} no puede ser negativo ({monto}): usa el tipo opuesto"
            )
        limpios.append({**movimiento, 'tipo': tipo, 'monto': monto})
    return limpios


def _validar_posicion(datos: Dict[str, Any]) -> None:
    tipo = datos.get('tipo') or 'plazo_fijo'
    if tipo not in POSITION_TYPES:
        raise ValidationError(f"Tipo inválido: {tipo!r}. Válidos: {', '.join(POSITION_TYPES)}")

    origen = datos.get('origen') or 'manual'
    if origen not in ORIGINS:
        raise ValidationError(f"Origen inválido: {origen!r}. Válidos: {', '.join(ORIGINS)}")

    estado = datos.get('estado')
    if estado is not None and estado not in POSITION_STATES:
        raise ValidationError(f"Estado inválido: {estado!r}. Válidos: {', '.join(POSITION_STATES)}")

    apertura = _to_date(datos.get('fecha_apertura'))
    cierre = _to_date(datos.get('fecha_cierre'))
    if apertura is None and cierre is None:
        # Las siembras pre-historial no tienen apertura conocida, y está bien; lo que no
        # puede pasar es que una posición no esté en ninguna parte de la línea de tiempo.
        raise ValidationError("La posición necesita al menos fecha_apertura o fecha_cierre")
    if apertura and cierre and cierre < apertura:
        raise ValidationError("fecha_cierre no puede ser anterior a fecha_apertura")

    portafolio_id = datos.get('portafolio_id')
    if portafolio_id and InterpolationStorage.get_group(portafolio_id) is None:
        raise ValidationError(f"El portafolio {portafolio_id!r} no existe en grupos.csv")


def create_position(datos: Dict[str, Any]) -> Dict[str, Any]:
    movimientos = _validar_movimientos(datos.get('movimientos') or [])
    _validar_posicion(datos)

    campos = {k: v for k, v in datos.items() if k != 'movimientos'}
    campos.setdefault('institucion', INSTITUCION_POR_DEFECTO)
    posicion = InvestmentStorage.create_position(**campos)
    guardados = InvestmentStorage.replace_movements(posicion['id'], movimientos)

    logger.info("Posición creada %s (%s movimientos)", posicion['id'], len(guardados))
    return armar_vista(posicion, guardados)


def registrar_flujo(portafolio_id: str, fecha: Any, monto: float,
                    direccion: str = 'salida', nota: Optional[str] = None,
                    tx_id: Optional[str] = None,
                    position_id: Optional[str] = None) -> Dict[str, Any]:
    """Registra que entró o salió dinero del portafolio sin pasar por una inversión.

    El caso que le da origen: cada vez que vence un certificado de `Inversiones_Uni` salen
    ~3.2xx que se van en matrícula y no se reinvierten. Eso hoy solo está anotado como la
    *fecha de fin* de un pago fijo, que es información invisible para el generador —
    ninguna de las dos puntas es una operación de certificado, así que el banco no la
    delata y el residual sigue arrastrando esa plata para siempre.

    Un flujo es **instantáneo**: se abre y se cierra el mismo día. No es algo pendiente que
    haya que cerrar después, y por eso queda `estado='cerrada'` sin tener que forzarlo —
    lo que además lo deja fuera del devengo y de los cierres ficticios del XIRR.

    `position_id` deja fijar el id, que es lo que hace idempotente a un script de siembra:
    correrlo dos veces no duplica nada y deshacerlo sabe exactamente qué borrar. Es la
    misma convención de `scripts/sembrar_posiciones_inversion.py`.
    """
    if direccion not in FLOW_DIRECTIONS:
        raise ValidationError(
            f"Dirección inválida: {direccion!r}. Válidas: {', '.join(FLOW_DIRECTIONS)}"
        )
    try:
        monto = float(monto)
    except (TypeError, ValueError):
        raise ValidationError(f"Monto inválido: {monto!r}")
    if monto <= 0:
        # El signo lo da la dirección, nunca el monto: si se aceptaran negativos habría
        # dos formas de escribir lo mismo y una de ellas terminaría al revés.
        raise ValidationError("El monto de un flujo tiene que ser positivo; el signo lo da la dirección")

    dia = _to_date(fecha)
    if dia is None:
        raise ValidationError(f"Fecha inválida: {fecha!r}")
    if not portafolio_id:
        raise ValidationError("Un flujo necesita portafolio: es plata que sale de uno concreto")

    return create_position({
        **({'id': position_id} if position_id else {}),
        'portafolio_id': portafolio_id,
        'tipo': 'flujo',
        'origen': 'manual',
        'fecha_apertura': dia.isoformat(),
        'fecha_cierre': dia.isoformat(),
        'nota': nota,
        'movimientos': [{
            'fecha': dia.isoformat(),
            'tipo': FLOW_DIRECTIONS[direccion],
            'monto': round(monto, 2),
            'tx_id': tx_id,
            'nota': nota,
        }],
    })


def residual_portafolio(portafolio_id: str, fecha: Any = None) -> Optional[float]:
    """Cuánta plata de inversión tiene suelta el portafolio en esa fecha, según las posiciones.

    Es el número contra el que hay que mirar un flujo antes de registrarlo: si sacar la
    matrícula deja el residual en negativo, o falta registrar algo o el monto está mal.

    Sigue **la misma regla de precedencia que `neutralizacion.preview`**, y tiene que ser
    la misma o el formulario y la pestaña de Neutralización mostrarían números distintos
    para el mismo día — comparar contra dos bases distintas es exactamente la clase de
    confusión que la pantalla existe para evitar:

    - si el portafolio tiene `saldo_inicial` configurado en `grupos.csv`, se usa ése;
    - si no, se deduce con las dos pasadas, que es lo que pasaba siempre antes de que
      hubiera dónde configurarlo (0 en `grupos.csv` y 26.000 deducidos para `Mias`).
    """
    from contabilidad.backend.services.investments import neutralizacion

    dia = _to_date(fecha) or date.today()
    portafolio = next((p for p in list_portfolios() if p['id'] == portafolio_id), None)
    if portafolio is None:
        return None

    vistas = list_positions()
    base = _con_saldo_inicial([portafolio])
    actuales = neutralizacion.pagos_actuales(base)

    # Pasada 1: qué saldo inicial haría falta para que las dos series arranquen iguales.
    # Sin pagos a mano no hay nada de donde deducirlo: la diferencia del primer día sería
    # el propio primer aporte y la "siembra" acabaría cancelando la primera inversión.
    siembra = 0.0
    if base[0].get('saldo_inicial_configurado'):
        siembra = round(float(base[0].get('saldo_inicial') or 0.0), 2)
    elif actuales:
        tanteo = [p.to_dict() for p in neutralizacion.generar_pagos(vistas, base)]
        siembra = neutralizacion.saldo_inicial_sugerido(neutralizacion.comparar(actuales, tanteo))

    # Pasada 2: el residual de verdad, ya con ese saldo puesto.
    sembrado = [{**base[0], 'saldo_inicial': siembra}]
    arranque = neutralizacion._primer_inicio(actuales)
    generados = [p.to_dict() for p in neutralizacion.generar_pagos(
        vistas, sembrado, desde={portafolio_id: arranque} if arranque else None,
    )]
    return neutralizacion.serie(generados, [dia])[0]


def update_position(position_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    actual = InvestmentStorage.get_position(position_id)
    if actual is None:
        return None

    movimientos = updates.get('movimientos')
    limpios = _validar_movimientos(movimientos) if movimientos is not None else None

    campos = {k: v for k, v in updates.items() if k != 'movimientos'}
    _validar_posicion({**actual, **campos})

    posicion = InvestmentStorage.update_position(position_id, campos) if campos else actual
    if limpios is not None:
        InvestmentStorage.replace_movements(position_id, limpios)

    return armar_vista(posicion, InvestmentStorage.get_movements(position_id))


def delete_position(position_id: str) -> bool:
    return InvestmentStorage.delete_position(position_id)


def split_position(position_id: str, partes: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reparte una posición entre varios portafolios, en posiciones hermanas.

    Un certificado puede juntar plata de más de un portafolio (el de 38.000 del
    2025-08-12 son 27.611 de `Mias` y 10.389 de `Madre`). Se guarda como N posiciones que
    comparten `tx_apertura_id` y `tx_cierre_id`; la reconciliación las suma para
    compararlas contra el banco, así que el certificado sigue cuadrando.

    Cada parte declara su `capital`; el interés y la retención se prorratean por capital
    salvo que la parte los traiga explícitos. Las hermanas nacen `origen='manual'` porque
    el reparto es una decisión del usuario, y eso además las protege del detector.
    """
    original = get_position(position_id)
    if original is None:
        return []
    if len(partes) < 2:
        raise ValidationError("Un reparto necesita al menos dos partes")

    capital_total = round(sum(float(p.get('capital') or 0.0) for p in partes), 2)
    if abs(capital_total - original['capital']) > 0.01:
        raise ValidationError(
            f"Las partes suman {capital_total} y la posición tiene {original['capital']}"
        )

    for parte in partes:
        if parte.get('portafolio_id') and InterpolationStorage.get_group(parte['portafolio_id']) is None:
            raise ValidationError(f"El portafolio {parte['portafolio_id']!r} no existe en grupos.csv")

    apertura = original['fecha_apertura'] or original['fecha_cierre']
    cierre = original['fecha_cierre']
    nuevas: List[Dict[str, Any]] = []

    for indice, parte in enumerate(partes, start=1):
        capital = round(float(parte.get('capital') or 0.0), 2)
        peso = capital / capital_total if capital_total else 0.0
        interes = parte.get('interes')
        retencion = parte.get('retencion')
        interes = round(original['interes'] * peso, 2) if interes is None else round(float(interes), 2)
        retencion = round(original['retencion'] * peso, 2) if retencion is None else round(float(retencion), 2)

        movimientos = [{'fecha': apertura, 'tipo': 'aporte', 'monto': capital,
                        'tx_id': original['tx_apertura_id']}]
        if cierre:
            movimientos.append({'fecha': cierre, 'tipo': 'retiro', 'monto': capital,
                                'tx_id': original['tx_cierre_id']})
            if interes:
                movimientos.append({'fecha': cierre, 'tipo': 'interes', 'monto': interes})
            if retencion:
                movimientos.append({'fecha': cierre, 'tipo': 'retencion', 'monto': retencion})

        nuevas.append(create_position({
            'portafolio_id': parte.get('portafolio_id'),
            'tipo': original['tipo'],
            'origen': 'manual',
            'fecha_apertura': original['fecha_apertura'],
            'fecha_cierre': cierre,
            'plazo_pactado_dias': original['plazo_pactado_dias'],
            'tasa_pactada': original['tasa_pactada'],
            'institucion': original['institucion'],
            'moneda': original['moneda'],
            'tx_apertura_id': original['tx_apertura_id'],
            'tx_cierre_id': original['tx_cierre_id'],
            'nota': parte.get('nota') or f"Parte {indice}/{len(partes)} del certificado repartido",
            'movimientos': movimientos,
        }))

    delete_position(position_id)
    logger.info("Posición %s repartida en %s partes", position_id, len(nuevas))
    return nuevas


# ── Reconciliación ───────────────────────────────────────────────────────────

def _account_data() -> pd.DataFrame:
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    return get_pipeline().get_account_data()


def _movimientos_de_detectada(detectada: DetectedPosition) -> List[Dict[str, Any]]:
    return [
        {
            'fecha': leg.fecha.isoformat(),
            'tipo': leg.tipo,
            'monto': round(leg.monto, 2),
            'tx_id': leg.tx_id,
            'nota': leg.descripcion,
        }
        for leg in detectada.movimientos
    ]


def _difiere(guardado: Any, detectado: Any) -> bool:
    if isinstance(guardado, (int, float)) and isinstance(detectado, (int, float)):
        return abs(float(guardado) - float(detectado)) > AMOUNT_TOLERANCE
    return (guardado or None) != (detectado or None)


def _comparar(vista: Dict[str, Any], detectada: DetectedPosition) -> Dict[str, Dict[str, Any]]:
    esperado = detectada.to_dict()
    cambios: Dict[str, Dict[str, Any]] = {}
    for campo in CAMPOS_RECONCILIADOS:
        actual, nuevo = vista.get(campo), esperado.get(campo)
        if _difiere(actual, nuevo):
            cambios[campo] = {'guardado': actual, 'detectado': nuevo}
    return cambios


def _fusionar(hermanas: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Las partes de un certificado repartido, vistas como una sola posición."""
    if len(hermanas) == 1:
        return hermanas[0]
    return {
        **hermanas[0],
        'capital': round(sum(h['capital'] for h in hermanas), 2),
        'interes': round(sum(h['interes'] for h in hermanas), 2),
        'retencion': round(sum(h['retencion'] for h in hermanas), 2),
    }


def _tx_ids_guardados(vista: Dict[str, Any]) -> set:
    ids = {vista.get('tx_apertura_id'), vista.get('tx_cierre_id')}
    ids.update(m.get('tx_id') for m in vista.get('movimientos', []))
    return {i for i in ids if i}


def reconcile(df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Compara el banco contra lo guardado. **No escribe nada.**

    Cinco cubetas:

    - `nuevas`: el banco tiene una posición que no está guardada.
    - `cambiadas`: está guardada pero algún monto o fecha ya no coincide (típicamente
      porque se reprocesó el extracto y apareció el interés que faltaba).
    - `iguales`: nada que hacer.
    - `huerfanas`: cancelaciones sin apertura que todavía no cubre ninguna posición
      manual. Son las que hay que sembrar a mano.
    - `solo_guardadas`: posiciones marcadas `detectado` que el detector ya no encuentra.
      Es la señal de que el extracto cambió debajo, y conviene mirarlas antes de borrar.
    """
    return _reconcile(detect_positions(_account_data() if df is None else df))


def _reconcile(resultado: DetectionResult) -> Dict[str, Any]:
    vistas = list_positions()
    tx_conocidos = set().union(*(_tx_ids_guardados(v) for v in vistas)) if vistas else set()

    # Agrupadas, no indexadas: un certificado repartido entre portafolios son varias
    # posiciones hermanas con el mismo `tx_apertura_id`, y lo que hay que comparar contra
    # el banco es la suma de las hermanas, no cada una por su lado.
    por_tx: Dict[str, List[Dict[str, Any]]] = {}
    for vista in vistas:
        if vista['tx_apertura_id']:
            por_tx.setdefault(vista['tx_apertura_id'], []).append(vista)

    sugerencias = portafolios.sugerir(resultado.posiciones)

    nuevas, cambiadas, iguales = [], [], []
    detectados_tx = set()

    for detectada in resultado.posiciones:
        detectados_tx.add(detectada.tx_apertura_id)
        hermanas = por_tx.get(detectada.tx_apertura_id)
        if not hermanas:
            nuevas.append({
                'detectada': detectada.to_dict(),
                'sugerencia': sugerencias.get(detectada.tx_apertura_id),
            })
            continue

        cambios = _comparar(_fusionar(hermanas), detectada)
        entrada = {
            'posicion_id': hermanas[0]['id'],
            'posicion_ids': [h['id'] for h in hermanas],
            'portafolio_id': hermanas[0]['portafolio_id'],
            # Una sola hermana manual protege a todo el grupo: el reparto es una decisión
            # del usuario y el detector no sabe reconstruirlo.
            'origen': 'manual' if any(h['origen'] == 'manual' for h in hermanas) else 'detectado',
            'detectada': detectada.to_dict(),
            'cambios': cambios,
        }
        (cambiadas if cambios else iguales).append(entrada)

    huerfanas = [
        h.to_dict() for h in resultado.huerfanas
        if not tx_conocidos.intersection(h.tx_ids)
    ]

    solo_guardadas = [
        {'posicion_id': v['id'], 'fecha_apertura': v['fecha_apertura'], 'capital': v['capital']}
        for v in vistas
        if v['origen'] == 'detectado' and v['tx_apertura_id'] not in detectados_tx
    ]

    return {
        'nuevas': nuevas,
        'cambiadas': cambiadas,
        'iguales': iguales,
        'huerfanas': huerfanas,
        'solo_guardadas': solo_guardadas,
        'resumen': {
            'detectadas': len(resultado.posiciones),
            'guardadas': len(vistas),
            'nuevas': len(nuevas),
            'cambiadas': len(cambiadas),
            'iguales': len(iguales),
            'huerfanas': len(huerfanas),
            'solo_guardadas': len(solo_guardadas),
        },
    }


def apply_detection(tx_apertura_ids: Optional[Sequence[str]] = None,
                    asignaciones: Optional[Dict[str, str]] = None,
                    portafolio_id: Optional[str] = None,
                    incluir_cambiadas: bool = True,
                    usar_sugerencias: bool = False,
                    df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Materializa el diff de `reconcile()`.

    `tx_apertura_ids=None` aplica todo lo pendiente; con lista, solo esas posiciones.
    `asignaciones` mapea `tx_apertura_id -> portafolio_id` y `portafolio_id` es el
    portafolio por defecto para las que no vengan asignadas. Con `usar_sugerencias`, las
    que no traigan asignación toman el portafolio que sugieren las cadenas de pagos
    (`portafolios.py`) — pero solo cuando la sugerencia es inequívoca: un certificado que
    juntó plata de varios portafolios se crea sin portafolio y espera un reparto explícito.

    Las posiciones con `origen='manual'` se saltan siempre y se reportan en `omitidas`:
    si el detector las pisara, se perdería la única información que no está en el banco.
    """
    resultado = detect_positions(_account_data() if df is None else df)
    diff = _reconcile(resultado)
    seleccion = set(tx_apertura_ids) if tx_apertura_ids is not None else None
    asignaciones = asignaciones or {}

    if portafolio_id and InterpolationStorage.get_group(portafolio_id) is None:
        raise ValidationError(f"El portafolio {portafolio_id!r} no existe en grupos.csv")

    creadas: List[Dict[str, Any]] = []
    actualizadas: List[Dict[str, Any]] = []
    omitidas: List[Dict[str, Any]] = []

    detectadas_por_tx = {p.tx_apertura_id: p for p in resultado.posiciones}

    for entrada in diff['nuevas']:
        tx_id = entrada['detectada']['tx_apertura_id']
        if seleccion is not None and tx_id not in seleccion:
            continue
        detectada = detectadas_por_tx[tx_id]
        sugerido = (entrada.get('sugerencia') or {}).get('sugerido') if usar_sugerencias else None
        creadas.append(create_position({
            'portafolio_id': asignaciones.get(tx_id) or sugerido or portafolio_id,
            'tipo': 'plazo_fijo',
            'origen': 'detectado',
            'fecha_apertura': detectada.fecha_apertura.isoformat(),
            'fecha_cierre': detectada.fecha_cierre.isoformat() if detectada.fecha_cierre else None,
            'institucion': INSTITUCION_POR_DEFECTO,
            'tx_apertura_id': detectada.tx_apertura_id,
            'tx_cierre_id': detectada.tx_cierre_id,
            'nota': 'Detectada en el extracto' + (' (interés prorrateado)' if detectada.ambiguo else ''),
            'movimientos': _movimientos_de_detectada(detectada),
        }))

    if incluir_cambiadas:
        for entrada in diff['cambiadas']:
            tx_id = entrada['detectada']['tx_apertura_id']
            if seleccion is not None and tx_id not in seleccion:
                continue
            if entrada['origen'] == 'manual':
                omitidas.append({'posicion_id': entrada['posicion_id'], 'motivo': 'origen manual'})
                continue
            detectada = detectadas_por_tx[tx_id]
            actualizado = update_position(entrada['posicion_id'], {
                'fecha_apertura': detectada.fecha_apertura.isoformat(),
                'fecha_cierre': detectada.fecha_cierre.isoformat() if detectada.fecha_cierre else None,
                'tx_cierre_id': detectada.tx_cierre_id,
                'movimientos': _movimientos_de_detectada(detectada),
            })
            if actualizado is not None:
                actualizadas.append(actualizado)

    logger.info(
        "Detección aplicada: %s creadas, %s actualizadas, %s omitidas",
        len(creadas), len(actualizadas), len(omitidas),
    )
    return {
        'creadas': creadas,
        'actualizadas': actualizadas,
        'omitidas': omitidas,
        'resumen': {
            'creadas': len(creadas),
            'actualizadas': len(actualizadas),
            'omitidas': len(omitidas),
        },
    }
