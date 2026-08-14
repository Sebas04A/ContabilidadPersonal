"""
neutralizacion.py — Los pagos fijos derivados de las posiciones. **No escribe nada.**

Un pago fijo de inversión existe para tapar un movimiento que sí tocó la cuenta pero que
no es flujo del usuario: cuando entra un CDT de 28.000, el saldo se desploma y el
dashboard mentiría si contara eso como gasto. El pago fijo dice "de este saldo visible,
tanto es plata de inversión".

Hoy esos pagos se escriben a mano en `pagos.csv`. Este módulo los **deriva** de las
posiciones, y la cuenta es una sola:

    residual(t) = saldo_inicial + Σ (retiro + interés − aporte − retención − comisión)

es decir, la plata de inversión del portafolio que **no** está dentro de un certificado.
Entre dos eventos consecutivos el residual es constante, y ese tramo constante es
exactamente un pago fijo. Los signos son los mismos de `metricas.SIGNO` y se importan de
ahí: poner plata en un certificado la saca del bolsillo tanto para la TIR como para el
residual.

## Por qué esto es solo una previsualización

Reemplazar los pagos a mano es la operación con más superficie de todo el módulo: un
error no rompe nada visible, solo desplaza el patrimonio histórico. El invariante que hay
que preservar no son las filas de `pagos.csv` sino **la función escalón evaluada**:

    para cada día:  PAGOS_FIJOS_actual(t) == PAGOS_FIJOS_generado(t)   ± 0,01

Por eso aquí solo se compara. Nada de esto toca `pagos.csv`.

## La semántica tiene que ser la del dashboard, no la del CSV

`VirtualItemsProcessor._apply_fixed_payment` aplica `start <= FECHA < end` **con las dos
puntas opcionales**: sin `start` el pago vale desde siempre y sin `end` vale para siempre.
`_activo()` replica esa regla exactamente, y tiene que seguir haciéndolo — si las dos se
separan, esta pantalla mide contra algo que el patrimonio nunca vio.

(Hasta el 2026-08-12 era al revés: un pago sin `start_date` se descartaba y había que
escribir fechas centinela para decir «hasta siempre». Las centinela que quedan escritas
siguen valiendo, `_es_centinela()` las trata como un fin ausente.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from contabilidad.backend.logger import get_logger
from contabilidad.backend.services.investments.metricas import SIGNO
from contabilidad.backend.storage.variables_storage import InterpolationStorage

logger = get_logger(__name__)

#: Los montos del banco vienen a dos decimales; por debajo de un centavo no hay descuadre.
TOLERANCIA = 0.01

#: Pero los pagos escritos a mano están redondeados a enteros (27.897 donde el banco dice
#: 27.897,57), así que una diferencia de un par de dólares es el redondeo del usuario y no
#: un error del generador. Separar las dos cosas es lo que hace legible la pantalla: un
#: portafolio que solo difiere por debajo de este umbral **reproduce** la contabilidad.
TOLERANCIA_REDONDEO = 2.0

#: `pagos.csv` usa fechas centinela (3000-01-01) para decir "hasta siempre". Más allá de
#: este límite una fecha no es un dato, es una convención, y no debe estirar el eje.
ANIO_CENTINELA = 2900


def _to_date(value: Any) -> Optional[date]:
    if value is None or value == '':
        return None
    try:
        ts = pd.to_datetime(value)
    except (ValueError, TypeError):
        return None
    return None if pd.isna(ts) else ts.date()


def _es_centinela(momento: Optional[date]) -> bool:
    return momento is not None and momento.year >= ANIO_CENTINELA


def _texto(value: Any) -> str:
    """Un campo de texto del CSV, con el NaN ya fuera.

    `read_csv` dice que convierte los NaN a `None`, pero lo hace con un `.apply` que no
    sobrevive al dtype: en una columna que pandas infirió `float64` —una columna de notas
    enteramente vacía, por ejemplo— devolver `None` la re-infiere y el NaN vuelve. Y `nan`
    es *truthy*, así que un `or ''` no lo atrapa; lo que sí pasa es que FastAPI revienta al
    serializar ("Out of range float values are not JSON compliant").
    """
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except (TypeError, ValueError):
        pass
    return str(value)


@dataclass
class PagoGenerado:
    """Un tramo constante del residual: el pago fijo que le corresponde."""

    portafolio_id: str
    portafolio: str
    amount: float
    start: date
    end: Optional[date]
    #: Qué evento abrió el tramo, para poder rastrear de dónde salió cada fila.
    motivo: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'portafolio_id': self.portafolio_id,
            'portafolio': self.portafolio,
            'amount': round(self.amount, 2),
            'start': self.start.isoformat(),
            'end': self.end.isoformat() if self.end else None,
            'motivo': self.motivo,
        }


@dataclass
class Comparacion:
    fechas: List[str] = field(default_factory=list)
    actual: List[float] = field(default_factory=list)
    generado: List[float] = field(default_factory=list)
    diferencia: List[float] = field(default_factory=list)

    @property
    def dias_descuadrados(self) -> int:
        return sum(1 for d in self.diferencia if abs(d) > TOLERANCIA)

    @property
    def max_desvio(self) -> float:
        return round(max((abs(d) for d in self.diferencia), default=0.0), 2)

    @property
    def dias_materiales(self) -> int:
        """Días que difieren por más de lo que explica el redondeo a mano."""
        return sum(1 for d in self.diferencia if abs(d) > TOLERANCIA_REDONDEO)

    @property
    def primer_descuadre(self) -> Optional[str]:
        for fecha, d in zip(self.fechas, self.diferencia):
            if abs(d) > TOLERANCIA_REDONDEO:
                return fecha
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'fechas': self.fechas,
            'actual': self.actual,
            'generado': self.generado,
            'diferencia': self.diferencia,
            'dias': len(self.fechas),
            'dias_descuadrados': self.dias_descuadrados,
            'dias_materiales': self.dias_materiales,
            'max_desvio': self.max_desvio,
            'primer_descuadre': self.primer_descuadre,
            'cuadra': self.dias_materiales == 0,
        }


# ── Generación ───────────────────────────────────────────────────────────────

def _eventos_por_portafolio(vistas: Sequence[Dict[str, Any]]) -> Dict[str, Dict[date, float]]:
    """`portafolio -> fecha -> cuánto cambia el residual ese día`.

    Con una excepción que importa: **el aporte de una posición sin fecha de apertura no
    cuenta**. Son las sembradas a mano, abiertas antes de que empiece el historial; su
    aporte lleva una fecha estimada (el primer día del extracto) que existe solo para que
    las métricas tengan capital, pero esa plata nunca estuvo suelta en la ventana visible
    —ya estaba dentro del certificado—. Contarla como salida hunde el residual del
    portafolio durante meses y obliga a inventar un saldo inicial que lo compense.
    """
    eventos: Dict[str, Dict[date, float]] = {}
    for vista in vistas:
        portafolio_id = vista.get('portafolio_id')
        if not portafolio_id:
            continue
        ya_estaba_dentro = vista.get('fecha_apertura') is None
        del_portafolio = eventos.setdefault(portafolio_id, {})
        for movimiento in vista.get('movimientos', []):
            fecha = _to_date(movimiento.get('fecha'))
            signo = SIGNO.get(movimiento.get('tipo'))
            if fecha is None or signo is None:
                continue
            if ya_estaba_dentro and movimiento.get('tipo') == 'aporte':
                continue
            monto = signo * float(movimiento.get('monto') or 0.0)
            del_portafolio[fecha] = round(del_portafolio.get(fecha, 0.0) + monto, 2)
    return eventos


def _motivo_de(vistas: Sequence[Dict[str, Any]], portafolio_id: str, fecha: date) -> str:
    """Qué pasó ese día en ese portafolio, en una línea.

    Un `flujo` se cuenta aparte porque es instantáneo: abre y cierra el mismo día, así que
    el «abre X · cierra X» de una posición normal lo describiría al revés y por duplicado.
    Y como una entrada no tiene aportes, su `capital` es 0: hay que mirar `retirado`.
    """
    partes = []
    for vista in vistas:
        if vista.get('portafolio_id') != portafolio_id:
            continue
        capital = float(vista.get('capital') or 0.0)

        if vista.get('tipo') == 'flujo':
            if _to_date(vista.get('fecha_apertura')) == fecha:
                retirado = float(vista.get('retirado') or 0.0)
                partes.append(f"sale {capital:,.0f}" if capital else f"entra {retirado:,.0f}")
            continue

        if _to_date(vista.get('fecha_apertura')) == fecha:
            partes.append(f"abre {capital:,.0f}")
        if _to_date(vista.get('fecha_cierre')) == fecha:
            partes.append(f"cierra {capital:,.0f}")
    return ' · '.join(partes)


def generar_pagos(vistas: Sequence[Dict[str, Any]],
                  portafolios: Sequence[Dict[str, Any]],
                  desde: Optional[Dict[str, date]] = None) -> List[PagoGenerado]:
    """Los pagos fijos que reproducen el residual de cada portafolio.

    Un tramo con residual cero no genera pago: sumar cero al escalón es lo mismo que no
    tener la fila, y así el CSV no se llena de ruido.

    `desde` da, por portafolio, la fecha en que empieza a contar su `saldo_inicial`. Sin
    ella el saldo inicial solo se ve a partir del primer evento, y el escalón queda mal
    justo en el tramo anterior — que es donde el usuario hoy tiene escritas sus filas más
    viejas (los 26.000 de `Mias` desde 2023-01-01, los 3.177 de `Uni` desde 2000-01-01).
    """
    eventos = _eventos_por_portafolio(vistas)
    desde = desde or {}
    pagos: List[PagoGenerado] = []

    for portafolio in portafolios:
        del_portafolio = eventos.get(portafolio['id'])
        if not del_portafolio:
            continue

        residual = round(float(portafolio.get('saldo_inicial') or 0.0), 2)
        fechas = sorted(del_portafolio)
        arranque = desde.get(portafolio['id'])

        # El tramo del saldo inicial: lo que el portafolio ya tenía suelto antes de que
        # ocurriera nada derivable de las posiciones.
        if arranque is not None and abs(residual) > TOLERANCIA and arranque < fechas[0]:
            pagos.append(PagoGenerado(
                portafolio_id=portafolio['id'],
                portafolio=portafolio['name'],
                amount=residual,
                start=arranque,
                end=fechas[0],
                motivo='saldo inicial',
            ))

        for indice, fecha in enumerate(fechas):
            residual = round(residual + del_portafolio[fecha], 2)
            siguiente = fechas[indice + 1] if indice + 1 < len(fechas) else None
            if abs(residual) <= TOLERANCIA:
                continue
            pagos.append(PagoGenerado(
                portafolio_id=portafolio['id'],
                portafolio=portafolio['name'],
                amount=residual,
                start=fecha,
                end=siguiente,
                motivo=_motivo_de(vistas, portafolio['id'], fecha),
            ))

    pagos.sort(key=lambda p: (p.start, p.portafolio))
    return pagos


def pagos_actuales(portafolios: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Los pagos que hoy están escritos a mano para esos portafolios.

    Se lee el CSV crudo a propósito, para poder mostrar también las filas que el camino
    normal descarta: existen, ocupan lugar y **no hacen nada**. Salen con `aplica=False` y
    no cuentan en la serie.

    **Qué descarta hoy `InterpolationStorage.get_payments()`**: solo las filas sin `id`,
    sin `group_id` o sin `amount`. Las fechas ya no son obligatorias — un pago fijo sin
    inicio vale desde siempre y sin fin vale para siempre—, así que una fila a la que le
    falte una fecha **sí** llega al dashboard y a la UI. Antes bastaba con que le faltara
    una para desaparecer de los dos sitios a la vez, y hubo 4 así.
    """
    from contabilidad.backend.storage.variables_storage import PAYMENTS_FILE, read_csv

    columnas = ['id', 'group_id', 'amount', 'start_date', 'end_date', 'note']
    crudos = read_csv(PAYMENTS_FILE, columnas).to_dict('records')
    por_id = {p['id']: p for p in portafolios}

    actuales: List[Dict[str, Any]] = []
    for pago in crudos:
        portafolio = por_id.get(str(pago.get('group_id')))
        if portafolio is None:
            continue
        inicio = _to_date(pago.get('start_date'))
        fin = _to_date(pago.get('end_date'))
        try:
            monto = round(float(pago.get('amount')), 2)
        except (TypeError, ValueError):
            continue
        actuales.append({
            'id': _texto(pago.get('id')),
            'portafolio_id': portafolio['id'],
            'portafolio': portafolio['name'],
            'amount': monto,
            'start': inicio.isoformat() if inicio else None,
            'end': None if (fin is None or _es_centinela(fin)) else fin.isoformat(),
            'nota': _texto(pago.get('note')),
            # Mismo criterio que `get_payments()`: lo único que hace que una fila no
            # llegue al dashboard es que le falte el monto, y aquí ya está garantizado.
            # Las fechas vacías son significado, no ausencia de dato.
            'aplica': True,
        })
    actuales.sort(key=lambda p: (p['start'] or '', p['portafolio']))
    return actuales


# ── Evaluación ───────────────────────────────────────────────────────────────

def _activo(inicio: Optional[date], fin: Optional[date], momento: date) -> bool:
    """La ventana del dashboard: `start <= día < end`, con las dos puntas opcionales.

    Sin `inicio` el pago vale desde siempre y sin `fin` vale para siempre — la misma regla
    que `VirtualItemsProcessor._apply_fixed_payment`, y **tiene que seguir siendo la
    misma**: esta función existe para medir exactamente lo que el patrimonio ve.

    Una fecha centinela (año ≥ 2900, o el `2030-01-01` que el usuario también usa) se trata
    igual que un fin ausente. Son la forma vieja de decir «hasta siempre», de cuando no se
    podía dejar la celda vacía; siguen funcionando y no hace falta migrarlas.
    """
    if inicio is not None and momento < inicio:
        return False
    return fin is None or _es_centinela(fin) or momento < fin


def serie(pagos: Sequence[Dict[str, Any]], fechas: Sequence[date]) -> List[float]:
    """`PAGOS_FIJOS(t)` para cada fecha, con la misma ventana que `VirtualItemsProcessor`.

    Los pagos marcados `aplica=False` no cuentan: son filas que el dashboard descarta, así
    que sumarlas mediría contra algo que el patrimonio nunca vio. Los pagos generados no
    llevan esa marca y siempre aplican — un `end` vacío ahí significa «hasta siempre», no
    «fila inválida», que es justo al revés que en el CSV.
    """
    ventanas = [
        (_to_date(p.get('start')), _to_date(p.get('end')), float(p.get('amount') or 0.0))
        for p in pagos
        if p.get('aplica', True)
    ]
    valores = []
    for momento in fechas:
        total = sum(monto for inicio, fin, monto in ventanas if _activo(inicio, fin, momento))
        valores.append(round(total, 2))
    return valores


def _rango(pagos: Sequence[Dict[str, Any]], hoy: date) -> Tuple[Optional[date], Optional[date]]:
    """Desde el primer pago **hasta hoy**, nunca más allá.

    El futuro no es validable: ninguna de las dos series tiene información sobre él, así
    que compararlo solo produce artefactos de borde. Antes la ventana llegaba hasta el
    último `end_date` que no fuera centinela, y bastaba con que un pago dijera
    `2030-01-01` —que el usuario usa como «hasta siempre», igual que el `3000-01-01` que
    sí se reconoce— para estirar la comparación tres años y medio y marcar un día
    descuadrado de 27.066 al final de un tramo que en realidad cuadra.
    """
    inicios = [_to_date(p.get('start')) for p in pagos]
    inicios = [i for i in inicios if i is not None]
    if not inicios:
        return None, None
    return min(inicios), hoy


def comparar(actual: Sequence[Dict[str, Any]], generado: Sequence[Dict[str, Any]],
             hoy: Optional[date] = None) -> Comparacion:
    """Evalúa las dos series día por día de calendario.

    Se comparan todos los días y no solo los que tienen transacción: si cuadran en el
    calendario completo, cuadran en cualquier subconjunto que el dashboard use, y el test
    deja de depender de qué días trae el extracto.
    """
    hoy = hoy or date.today()
    inicio_a, fin_a = _rango(actual, hoy)
    inicio_g, fin_g = _rango(generado, hoy)

    inicios = [i for i in (inicio_a, inicio_g) if i]
    finales = [f for f in (fin_a, fin_g) if f]
    if not inicios:
        return Comparacion()

    dia, ultimo = min(inicios), max(finales)
    fechas: List[date] = []
    while dia <= ultimo:
        fechas.append(dia)
        dia += timedelta(days=1)

    serie_actual = serie(actual, fechas)
    serie_generada = serie(generado, fechas)

    return Comparacion(
        fechas=[f.isoformat() for f in fechas],
        actual=serie_actual,
        generado=serie_generada,
        diferencia=[round(a - g, 2) for a, g in zip(serie_actual, serie_generada)],
    )


def saldo_inicial_sugerido(comparacion: Comparacion) -> float:
    """Cuánto habría que sembrar en el portafolio para que las dos series se alineen.

    **La diferencia el primer día de la ventana**, que es la definición literal de un
    saldo inicial: lo que el escalón actual ya valía antes de que ocurriera el primer
    evento derivable de las posiciones.

    La tentación es buscar el valor más repetido de la diferencia, pero eso confunde dos
    cosas distintas: cuando un portafolio no necesita siembra pero sí tiene un descuadre
    real y largo, el más repetido devuelve ese descuadre y lo disfraza de saldo inicial.
    El primer día no puede confundirse: ahí todavía no pasó nada que explique una
    diferencia.
    """
    return comparacion.diferencia[0] if comparacion.diferencia else 0.0


def residuo_tras_siembra(comparacion: Comparacion, siembra: float) -> Dict[str, Any]:
    """Qué queda descuadrado después de aplicar la siembra sugerida.

    Es la cifra que de verdad importa: separa "falta una constante" (trivial de arreglar,
    es un número en `grupos.csv`) de "aquí la contabilidad no coincide" (hay que mirarlo).
    """
    restos = [round(d - siembra, 2) for d in comparacion.diferencia]
    descuadrados = [(f, r) for f, r in zip(comparacion.fechas, restos) if abs(r) > TOLERANCIA]
    return {
        'serie': restos,
        'dias_descuadrados': len(descuadrados),
        'max_desvio': round(max((abs(r) for _, r in descuadrados), default=0.0), 2),
        'primer_descuadre': descuadrados[0][0] if descuadrados else None,
        'tramos': _tramos(descuadrados),
    }


def _tramos(descuadrados: Sequence[Tuple[str, float]], maximo: int = 12) -> List[Dict[str, Any]]:
    """Agrupa los días descuadrados en tramos contiguos con el mismo desvío.

    Mil días sueltos en una lista no dicen nada; seis tramos con su monto sí.
    """
    tramos: List[Dict[str, Any]] = []
    for fecha, resto in descuadrados:
        anterior = tramos[-1] if tramos else None
        contiguo = (
            anterior is not None
            and abs(anterior['monto'] - resto) <= TOLERANCIA
            and (date.fromisoformat(fecha) - date.fromisoformat(anterior['hasta'])).days == 1
        )
        if contiguo:
            anterior['hasta'] = fecha
            anterior['dias'] += 1
        else:
            tramos.append({'desde': fecha, 'hasta': fecha, 'dias': 1, 'monto': resto})
    tramos.sort(key=lambda t: -t['dias'])
    return tramos[:maximo]


# ── Previsualización ─────────────────────────────────────────────────────────

def _por_portafolio(pagos: Sequence[Dict[str, Any]], portafolio_id: str) -> List[Dict[str, Any]]:
    return [p for p in pagos if p['portafolio_id'] == portafolio_id]


def _primer_inicio(pagos: Sequence[Dict[str, Any]]) -> Optional[date]:
    inicios = [_to_date(p.get('start')) for p in pagos]
    inicios = [i for i in inicios if i is not None]
    return min(inicios) if inicios else None


def preview(vistas: Sequence[Dict[str, Any]],
            portafolios: Sequence[Dict[str, Any]],
            hoy: Optional[date] = None) -> Dict[str, Any]:
    """Todo lo que hace falta para decidir si los pagos generados son correctos.

    Se hacen **dos pasadas**, y la distinción es el corazón de la pantalla:

    1. Con los portafolios como están hoy (`saldo_inicial = 0`). La diferencia del primer
       día de cada uno es, por definición, la plata que ya tenía suelta antes de que
       ocurriera nada derivable: su saldo inicial.
    2. Con esos saldos iniciales puestos. Lo que quede descuadrado **aquí** ya no se
       explica por una constante que falta configurar; es contabilidad que no coincide, y
       es lo único que hay que mirar de verdad.

    Todo lo que se reporta —series, tramos, pagos— sale de la pasada 2. **No escribe nada.**
    """
    hoy = hoy or date.today()
    actuales = pagos_actuales(portafolios)

    # Pasada 1 — detectar el saldo inicial de cada portafolio.
    #
    # Salvo que ya esté configurado: un saldo escrito por el usuario en `grupos.csv` manda
    # sobre el deducido. La deducción existe porque hoy no hay dónde ponerlo, no porque sea
    # mejor —se apoya en `pagos.csv`, que es justo lo que la fase 6 va a retirar—. Ojo con
    # la distinción: «vacío» pide deducir y «0» es una afirmación del usuario, y las dos
    # llegan aquí como `saldo_inicial == 0.0`; lo que las separa es
    # `saldo_inicial_configurado`.
    tanteo = [p.to_dict() for p in generar_pagos(vistas, portafolios)]
    siembras: Dict[str, float] = {}
    arranques: Dict[str, date] = {}
    for portafolio in portafolios:
        del_actual = _por_portafolio(actuales, portafolio['id'])
        del_generado = _por_portafolio(tanteo, portafolio['id'])
        if not del_actual and not del_generado:
            continue
        if portafolio.get('saldo_inicial_configurado'):
            siembras[portafolio['id']] = round(float(portafolio.get('saldo_inicial') or 0.0), 2)
        else:
            siembras[portafolio['id']] = saldo_inicial_sugerido(comparar(del_actual, del_generado, hoy))
        inicio = _primer_inicio(del_actual)
        if inicio is not None:
            arranques[portafolio['id']] = inicio

    # Pasada 2 — regenerar ya con los saldos iniciales puestos.
    sembrados = [
        {**p, 'saldo_inicial': siembras.get(p['id'], 0.0)}
        for p in portafolios
    ]
    generados = [p.to_dict() for p in generar_pagos(vistas, sembrados, desde=arranques)]
    global_ = comparar(actuales, generados, hoy)

    detalle = []
    for portafolio in sembrados:
        del_actual = _por_portafolio(actuales, portafolio['id'])
        del_generado = _por_portafolio(generados, portafolio['id'])
        if not del_actual and not del_generado:
            continue

        comparacion = comparar(del_actual, del_generado, hoy)
        detalle.append({
            'portafolio_id': portafolio['id'],
            'nombre': portafolio['name'],
            'es_custodia': bool(portafolio.get('es_custodia')),
            'saldo_inicial_sugerido': round(portafolio['saldo_inicial'], 2),
            'saldo_inicial_configurado': bool(portafolio.get('saldo_inicial_configurado')),
            'pagos_actuales': len(del_actual),
            'pagos_generados': len(del_generado),
            'tramos': _tramos([
                (f, d) for f, d in zip(comparacion.fechas, comparacion.diferencia)
                if abs(d) > TOLERANCIA_REDONDEO
            ]),
            **comparacion.to_dict(),
        })

    logger.info(
        "Previsualización de neutralización: %s pagos generados vs %s actuales; "
        "%s de %s días descuadrados",
        len(generados), len(actuales), global_.dias_descuadrados, len(global_.fechas),
    )

    return {
        'fecha': hoy.isoformat(),
        'global': {
            **global_.to_dict(),
            'tramos': _tramos([
                (f, d) for f, d in zip(global_.fechas, global_.diferencia)
                if abs(d) > TOLERANCIA_REDONDEO
            ]),
        },
        'por_portafolio': detalle,
        'pagos_generados': generados,
        'pagos_actuales': actuales,
        'resumen': {
            'pagos_generados': len(generados),
            'pagos_actuales': len(actuales),
            'pagos_actuales_ignorados': sum(1 for p in actuales if not p['aplica']),
            'siembra_total': round(sum(siembras.values()), 2),
            'dias': len(global_.fechas),
            'dias_descuadrados': global_.dias_descuadrados,
            'dias_materiales': global_.dias_materiales,
            'max_desvio': global_.max_desvio,
            'primer_descuadre': global_.primer_descuadre,
            'cuadra': global_.dias_materiales == 0,
            'portafolios_que_cuadran': sum(1 for d in detalle if d['cuadra']),
            'portafolios': len(detalle),
        },
    }
