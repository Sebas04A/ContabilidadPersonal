"""
corte.py — La fase 6: pasar de pagos escritos a mano a pagos generados.

Es la operación con más superficie de todo el módulo: un error no rompe nada visible, solo
desplaza el patrimonio histórico. Por eso va en tres pasos separados, y solo el último
escribe sobre lo que el dashboard lee.

    1. sembrar_sombra()   crea grupos `type='shadow'` con los pagos generados.
                          `VirtualItemsProcessor` solo aplica `fixed` e `interpolated`,
                          así que la sombra existe y no afecta a nada.
    2. verificar()        evalúa la función escalón **antes** y **después** del corte, día
                          por día, sin escribir. Es la puerta: si no pasa, no se corta.
    3. aplicar_corte()    en una sola pasada, los sombra pasan a `fixed` y se vacían los
                          pagos de los grupos originales.

## El invariante no son las filas, es la función escalón

Dos conjuntos distintos de pagos pueden producir el mismo `PAGOS_FIJOS(t)` — el usuario
usa filas solapadas (una base abierta más una temporal) y el generador emite una por
tramo. Comparar CSVs daría diferencias que no existen. Lo que no puede cambiar es la serie
diaria evaluada:

    para cada día:  PAGOS_FIJOS_antes(t) == PAGOS_FIJOS_despues(t)   ± tolerancia

Y a favor nuestro hay un detalle del código: `PAGOS_FIJOS` se arma leyendo *todos* los
grupos y filtrando por `type == 'fixed'`, nunca por `group_id`. Mover un pago de
`Inversiones_Mias` a `Pagos Inversiones_Mias` no cambia absolutamente nada mientras monto
y fechas se conserven. La migración de pertenencia es gratis; lo que hay que validar es la
aritmética del generador.

## Por qué la tolerancia no es cero

Los pagos a mano están redondeados a enteros y los generados salen del banco al centavo,
así que la serie **va a cambiar** unos pocos dólares por definición. `verificar()` reporta
el desvío máximo y quién lo aporta, y `aplicar_corte()` exige pasar un umbral explícito:
migrar es aceptar ese cambio a sabiendas, no fingir que no existe.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence

from contabilidad.backend.logger import get_logger
from contabilidad.backend.services.investments import neutralizacion
from contabilidad.backend.storage.variables_storage import InterpolationStorage

logger = get_logger(__name__)

#: Los grupos sombra nacen con este tipo justamente porque `VirtualItemsProcessor` lo
#: ignora: durante la fase de validación los pagos están duplicados y no se pueden aplicar.
TIPO_SOMBRA = 'shadow'

#: Cuánto puede moverse la serie diaria de **un portafolio** y seguir considerándose la
#: misma. Es el redondeo a enteros del usuario; por encima de esto hay que mirar antes de
#: cortar.
#:
#: La unidad importa y costó un diagnóstico equivocado. Este umbral mide el redondeo de
#: *un* portafolio, así que hay que aplicarlo portafolio por portafolio: contrastarlo
#: contra la serie agregada compara la suma de tres redondeos independientes contra una
#: vara calibrada para uno solo, y el corte se niega por un descuadre que no existe. Pasó:
#: el agregado marcaba 3,40 el 2025-09-25 y era 1,09 + 1,07 + 1,24, ninguno fuera de rango.
TOLERANCIA_CORTE = 2.0

#: Sufijo y no prefijo, a propósito: en cualquier lista ordenada por nombre el grupo
#: generado cae **justo debajo del que lo genera** («Inversiones_Uni», «Inversiones_Uni
#: Pagos») en vez de irse a la letra P, lejos de su origen. Es la misma convención que
#: ya usa `funds.py` al materializar los pagos de un fondo.
SUFIJO = ' Pagos'

#: Un tramo abierto se escribe con `end_date` **vacío**, que es lo que significa: «para
#: siempre».
#:
#: Hasta el 2026-08-12 no se podía. `get_payments()` hacía `dropna` sobre las dos fechas, o
#: sea que una fila sin fin desaparecía a la vez del dashboard y de la pantalla de
#: Variables, y había que escribir la fecha centinela `3000-01-01` para expresarlo. Ya no
#: hace falta; las centinela que quedan escritas siguen valiendo igual.
FECHA_CENTINELA = None


def _portafolios() -> List[Dict[str, Any]]:
    from contabilidad.backend.services.investments import posiciones
    return [p for p in posiciones.list_portfolios() if p['es_inversion']]


def _grupo_sombra(portafolio_id: str) -> Optional[Dict[str, Any]]:
    """El grupo sombra de un portafolio, si ya existe.

    Se localiza por `fondo_origen`, no por nombre: el nombre lo puede cambiar el usuario y
    entonces la regeneración crearía un segundo grupo en vez de reemplazar el primero.
    """
    for grupo in InterpolationStorage.get_groups(type_filter=None):
        if grupo.get('fondo_origen') == portafolio_id and grupo.get('type') == TIPO_SOMBRA:
            return grupo
    return None


def _grupo_generado_activo(portafolio_id: str) -> Optional[Dict[str, Any]]:
    """El grupo de pagos generados que **ya está aplicándose**, o sea, tras el corte."""
    for grupo in InterpolationStorage.get_groups(type_filter=None):
        if grupo.get('fondo_origen') == portafolio_id and grupo.get('type') == 'fixed':
            return grupo
    return None


# ── Paso 1: sembrar la sombra ────────────────────────────────────────────────

def sembrar_sombra() -> Dict[str, Any]:
    """Materializa los pagos generados en grupos `shadow`. Idempotente.

    No toca los grupos originales ni sus pagos, y como `shadow` no lo aplica nadie, el
    dashboard sigue exactamente igual mientras dure la validación.

    **Solo sirve para migrar, una vez.** Si el corte ya se aplicó, sembrar otra sombra
    crearía un segundo grupo con los mismos pagos junto al que ya está activo, y un
    `aplicar_corte(forzar=True)` encima **duplicaría el patrimonio** — medido: 10.200 pasan
    a 20.400. `verificar()` lo detecta y el corte sin `forzar` se niega, pero eso es la
    última red, no una defensa. Para actualizar los pagos de un portafolio ya cortado hace
    falta regenerar el grupo activo en su sitio, que es otra operación (§7 del handoff).
    """
    from contabilidad.backend.services.investments import posiciones

    ya_cortados = [p['name'] for p in _portafolios() if _grupo_generado_activo(p['id'])]
    if ya_cortados:
        return {
            'error': ("Estos portafolios ya están cortados y sus pagos generados están "
                      f"activos: {', '.join(ya_cortados)}. Sembrar otra sombra duplicaría "
                      "el patrimonio al cortar. Regenera el grupo activo en su sitio."),
            'ya_cortados': ya_cortados,
            'portafolios': [],
            'pagos': 0,
        }

    previsualizacion = posiciones.get_neutralization_preview()
    generados = previsualizacion['pagos_generados']

    resultado = []
    for portafolio in _portafolios():
        suyos = [p for p in generados if p['portafolio_id'] == portafolio['id']]

        anterior = _grupo_sombra(portafolio['id'])
        if anterior:
            InterpolationStorage.delete_group(anterior['id'])

        grupo = InterpolationStorage.create_group(
            name=f"{portafolio['name']}{SUFIJO}",
            description=f"Pagos generados desde las posiciones de «{portafolio['name']}»",
            group_type=TIPO_SOMBRA,
            fondo_origen=portafolio['id'],
        )
        for pago in suyos:
            InterpolationStorage.create_payment(
                group_id=grupo['id'],
                amount=pago['amount'],
                start_date=pago['start'],
                end_date=pago['end'] or FECHA_CENTINELA,
                note=pago['motivo'] or 'generado',
            )

        resultado.append({
            'portafolio_id': portafolio['id'],
            'portafolio': portafolio['name'],
            'grupo_sombra_id': grupo['id'],
            'pagos': len(suyos),
        })
        logger.info("Sombra de %s: %s pagos en %s", portafolio['name'], len(suyos), grupo['id'])

    return {'portafolios': resultado, 'pagos': sum(r['pagos'] for r in resultado)}


def limpiar_sombra() -> int:
    """Borra los grupos sombra. Deja el sistema como antes de `sembrar_sombra()`."""
    borrados = 0
    for portafolio in _portafolios():
        grupo = _grupo_sombra(portafolio['id'])
        if grupo and InterpolationStorage.delete_group(grupo['id']):
            borrados += 1
    return borrados


# ── Paso 2: verificar la equivalencia ────────────────────────────────────────

@dataclass
class Equivalencia:
    fechas: List[str]
    antes: List[float]
    despues: List[float]

    @property
    def diferencia(self) -> List[float]:
        return [round(a - d, 2) for a, d in zip(self.antes, self.despues)]

    def to_dict(self) -> Dict[str, Any]:
        diferencia = self.diferencia
        peores = sorted(zip(self.fechas, diferencia), key=lambda x: -abs(x[1]))
        maximo = round(max((abs(d) for d in diferencia), default=0.0), 2)
        return {
            'dias': len(self.fechas),
            'dias_que_cambian': sum(1 for d in diferencia if abs(d) > 0.01),
            'max_desvio': maximo,
            'peores_dias': [{'fecha': f, 'desvio': d} for f, d in peores[:10] if abs(d) > 0.01],
        }


def _forma_serie(pago: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'amount': float(pago['amount']),
        'start': pago['start_date'].isoformat() if pago['start_date'] else None,
        'end': pago['end_date'].isoformat() if pago['end_date'] else None,
    }


def _pagos_de_grupos(tipos: Sequence[str], excluir: Sequence[str] = ()) -> List[Dict[str, Any]]:
    """Todos los pagos aplicables de los grupos de esos tipos, con la forma de `serie()`."""
    pagos = []
    for grupo in InterpolationStorage.get_groups(type_filter=None):
        if grupo.get('type') not in tipos or grupo['id'] in excluir:
            continue
        pagos.extend(_forma_serie(p) for p in InterpolationStorage.get_payments(grupo['id']))
    return pagos


def _pagos_de_grupo(grupo_id: Optional[str]) -> List[Dict[str, Any]]:
    if not grupo_id:
        return []
    return [_forma_serie(p) for p in InterpolationStorage.get_payments(grupo_id)]


def _rango(pagos: Sequence[Dict[str, Any]], hoy: date) -> List[date]:
    inicios = [neutralizacion._to_date(p['start']) for p in pagos]
    inicios = [i for i in inicios if i is not None]
    if not inicios:
        return []
    fechas, dia = [], min(inicios)
    while dia <= hoy:
        fechas.append(dia)
        dia += timedelta(days=1)
    return fechas


def verificar(hoy: Optional[date] = None) -> Dict[str, Any]:
    """Compara `PAGOS_FIJOS(t)` antes y después del corte. **No escribe nada.**

    - *Antes*: los grupos `fixed` como están hoy.
    - *Después*: los mismos `fixed` **menos** los pagos de los portafolios de inversión,
      **más** los pagos de los grupos sombra.

    Se leen los pagos con `get_payments()` a propósito, para medir exactamente lo que el
    dashboard aplicaría y no lo que dice el CSV — hay filas que el CSV tiene y el
    dashboard descarta.

    **La puerta se decide portafolio por portafolio, no sobre el agregado.** Lo que la
    tolerancia representa es el redondeo a enteros de *un* portafolio; el agregado suma
    tres de esos redondeos, así que su desvío máximo puede triplicar el umbral sin que
    ninguna contabilidad esté mal. El agregado se sigue calculando y reportando —es el
    impacto real sobre el patrimonio y hay que verlo— pero no es el criterio.
    """
    hoy = hoy or date.today()
    portafolios = _portafolios()
    ids_portafolio = [p['id'] for p in portafolios]
    ids_sombra = [g['id'] for g in (_grupo_sombra(p['id']) for p in portafolios) if g]

    if not ids_sombra:
        return {'error': 'No hay grupos sombra: corre sembrar_sombra() primero.'}

    antes = _pagos_de_grupos(['fixed'])
    despues = _pagos_de_grupos(['fixed'], excluir=ids_portafolio) + _pagos_de_grupos([TIPO_SOMBRA])

    fechas = _rango(antes + despues, hoy)
    if not fechas:
        return {'error': 'No hay pagos que comparar.'}

    agregado = Equivalencia(
        fechas=[f.isoformat() for f in fechas],
        antes=neutralizacion.serie(antes, fechas),
        despues=neutralizacion.serie(despues, fechas),
    ).to_dict()

    # La puerta: cada portafolio contra su propia sombra.
    por_portafolio = []
    for portafolio in portafolios:
        sombra = _grupo_sombra(portafolio['id'])
        suyos_antes = _pagos_de_grupo(portafolio['id'])
        suyos_despues = _pagos_de_grupo(sombra['id'] if sombra else None)
        propias = _rango(suyos_antes + suyos_despues, hoy)
        if not propias:
            continue
        medida = Equivalencia(
            fechas=[f.isoformat() for f in propias],
            antes=neutralizacion.serie(suyos_antes, propias),
            despues=neutralizacion.serie(suyos_despues, propias),
        ).to_dict()
        por_portafolio.append({
            'portafolio': portafolio['name'],
            'portafolio_id': portafolio['id'],
            'cuadra': medida['max_desvio'] <= TOLERANCIA_CORTE,
            **medida,
        })

    return {
        'fecha': hoy.isoformat(),
        'pagos_antes': len(antes),
        'pagos_despues': len(despues),
        'grupos_sombra': len(ids_sombra),
        'por_portafolio': por_portafolio,
        'peor_portafolio': round(max((p['max_desvio'] for p in por_portafolio), default=0.0), 2),
        'equivalente': all(p['cuadra'] for p in por_portafolio) and bool(por_portafolio),
        'tolerancia': TOLERANCIA_CORTE,
        **agregado,
    }


# ── Paso 3: el corte ─────────────────────────────────────────────────────────

def aplicar_corte(forzar: bool = False, hoy: Optional[date] = None) -> Dict[str, Any]:
    """Los sombra pasan a `fixed` y los originales se vacían, en una sola pasada.

    El orden importa: **primero se vacían los originales y después se activan los sombra**.
    Al revés habría un instante con las dos series aplicándose y el patrimonio duplicado;
    así el peor caso intermedio es un instante sin ninguna, que es recuperable y no se
    persiste en ningún lado.

    Sin `forzar`, se niega a cortar si `verificar()` no pasa la tolerancia.
    """
    comprobacion = verificar(hoy)
    if 'error' in comprobacion:
        return {'ok': False, **comprobacion}
    if not comprobacion['equivalente'] and not forzar:
        culpables = ', '.join(f"{p['portafolio']} {p['max_desvio']}"
                              for p in comprobacion['por_portafolio'] if not p['cuadra'])
        return {
            'ok': False,
            'error': (f"Hay portafolios que se moverían más de {TOLERANCIA_CORTE}: "
                      f"{culpables}. Revisa `por_portafolio` o pasa forzar=True."),
            **comprobacion,
        }

    vaciados = 0
    for portafolio in _portafolios():
        for pago in InterpolationStorage.get_payments(portafolio['id']):
            if InterpolationStorage.delete_payment(pago['id']):
                vaciados += 1

    activados = 0
    for portafolio in _portafolios():
        grupo = _grupo_sombra(portafolio['id'])
        if grupo and InterpolationStorage.update_group(grupo['id'], {'type': 'fixed'}):
            activados += 1

    logger.info("Corte aplicado: %s pagos vaciados, %s grupos sombra activados",
                vaciados, activados)
    return {
        'ok': True,
        'pagos_vaciados': vaciados,
        'grupos_activados': activados,
        'max_desvio': comprobacion['max_desvio'],
    }


# ── Después del corte: mantener los pagos al día ─────────────────────────────
#
# El corte es de una sola vez; esto es la operación de todos los días. Cuando entra un
# certificado nuevo, las posiciones cambian y los pagos generados tienen que seguirlas.
#
# **Aquí no hay sombra ni tolerancia, y es a propósito.** La sombra existía porque durante
# la migración competían dos fuentes —los pagos a mano y los generados— y había que
# validar que dijeran lo mismo antes de cambiar de una a otra. Ya no hay más que una
# fuente, así que un segundo grupo solo puede duplicar. Y la serie **debe** moverse: eso
# es justo lo que significa que hubo una inversión nueva, así que un umbral que se negara
# a aplicar el cambio estaría midiendo lo contrario de lo que pasa.
#
# Lo que sí hay es previsualización: el diff se enseña antes de escribir.


def _saldo_configurado(portafolio_id: str) -> bool:
    grupo = InterpolationStorage.get_group(portafolio_id) or {}
    return bool(grupo.get('saldo_inicial_configurado'))


def _arranques_vigentes(portafolios: Sequence[Dict[str, Any]]) -> Dict[str, date]:
    """Desde cuándo cuenta el `saldo_inicial` de cada portafolio, según lo ya materializado.

    `preview()` lo deduce del primer pago escrito a mano, y tras el corte no queda ninguno:
    sin esto la regeneración perdería el tramo del saldo inicial de cada portafolio, que es
    el más viejo de todos y el que nadie miraría. Se toma del grupo generado que ya está
    activo, que es exactamente de donde salió la primera vez.
    """
    arranques: Dict[str, date] = {}
    for portafolio in portafolios:
        grupo = _grupo_generado_activo(portafolio['id'])
        if not grupo:
            continue
        inicios = [p['start_date'] for p in InterpolationStorage.get_payments(grupo['id'])
                   if p['start_date']]
        if inicios:
            arranques[portafolio['id']] = min(inicios)
    return arranques


def _generados_hoy(portafolios: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Los pagos que le tocarían hoy a cada portafolio, desde sus posiciones."""
    from contabilidad.backend.services.investments import posiciones

    completos = posiciones._con_saldo_inicial(portafolios)
    generados = neutralizacion.generar_pagos(
        posiciones.list_positions(), completos, desde=_arranques_vigentes(portafolios),
    )
    return [p.to_dict() for p in generados]


def previsualizar_regeneracion(portafolio_id: Optional[str] = None,
                               hoy: Optional[date] = None) -> Dict[str, Any]:
    """Qué cambiaría al regenerar, **sin escribir nada**."""
    hoy = hoy or date.today()
    portafolios = [p for p in _portafolios()
                   if portafolio_id is None or p['id'] == portafolio_id]

    generados = _generados_hoy(portafolios)
    detalle = []
    for portafolio in portafolios:
        grupo = _grupo_generado_activo(portafolio['id'])
        if not grupo:
            detalle.append({
                'portafolio': portafolio['name'],
                'portafolio_id': portafolio['id'],
                'error': 'Este portafolio no está cortado: sus pagos generados no están activos.',
            })
            continue

        # Sin `saldo_inicial` configurado no se puede regenerar, y el fallo sería mudo.
        #
        # Antes del corte el residual de partida se deducía de los pagos escritos a mano.
        # El corte los borra, así que esa deducción se queda sin fuente y el generador
        # arrancaría de cero: la serie se hundiría el importe del saldo inicial —en los
        # datos reales, 26.000 en `Mias`— y el tramo más viejo del portafolio, que es
        # justo el que nadie mira, desaparecería. `grupos.csv` es la única fuente que
        # queda, y por eso el campo existe en Resumen.
        if not _saldo_configurado(portafolio['id']):
            detalle.append({
                'portafolio': portafolio['name'],
                'portafolio_id': portafolio['id'],
                'error': ("Este portafolio no tiene `saldo_inicial` configurado. Tras el "
                          "corte no hay de dónde deducirlo, así que regenerar perdería su "
                          "saldo de partida. Configúralo en Resumen → Saldo inicial."),
            })
            continue

        ahora = _pagos_de_grupo(grupo['id'])
        nuevos = [{'amount': p['amount'], 'start': p['start'], 'end': p['end']}
                  for p in generados if p['portafolio_id'] == portafolio['id']]

        fechas = _rango(ahora + nuevos, hoy)
        medida = Equivalencia(
            fechas=[f.isoformat() for f in fechas],
            antes=neutralizacion.serie(ahora, fechas),
            despues=neutralizacion.serie(nuevos, fechas),
        ).to_dict() if fechas else {'dias': 0, 'dias_que_cambian': 0, 'max_desvio': 0.0,
                                    'peores_dias': []}

        detalle.append({
            'portafolio': portafolio['name'],
            'portafolio_id': portafolio['id'],
            'grupo_id': grupo['id'],
            'pagos_ahora': len(ahora),
            'pagos_nuevos': len(nuevos),
            'sin_cambios': medida['dias_que_cambian'] == 0 and len(ahora) == len(nuevos),
            **medida,
        })

    return {
        'fecha': hoy.isoformat(),
        'por_portafolio': detalle,
        'sin_cambios': all(d.get('sin_cambios') for d in detalle) if detalle else True,
    }


def regenerar(portafolio_id: Optional[str] = None,
              hoy: Optional[date] = None) -> Dict[str, Any]:
    """Reescribe los pagos del grupo generado que ya está activo, desde las posiciones.

    Es lo que hay que correr cuando entra una inversión nueva. Reemplaza **en su sitio**:
    no crea grupos, así que no puede duplicar el patrimonio como haría sembrar otra sombra
    sobre un portafolio ya cortado.

    Idempotente: regenerar sin que hayan cambiado las posiciones no mueve la serie ni un
    día. Ese es el invariante que lo hace seguro de correr, y está en los tests.
    """
    previa = previsualizar_regeneracion(portafolio_id, hoy)
    fallos = [d for d in previa['por_portafolio'] if 'error' in d]
    if fallos:
        return {'ok': False, 'error': fallos[0]['error'], **previa}

    portafolios = [p for p in _portafolios()
                   if portafolio_id is None or p['id'] == portafolio_id]
    generados = _generados_hoy(portafolios)

    borrados = escritos = 0
    for portafolio in portafolios:
        grupo = _grupo_generado_activo(portafolio['id'])
        suyos = [p for p in generados if p['portafolio_id'] == portafolio['id']]

        # Se vacía y se reescribe. Hay un instante con el grupo sin pagos, igual que en el
        # corte: es el peor caso recuperable, y el contrario —escribir antes de borrar—
        # dejaría un instante con la serie duplicada, que sí se vería en el patrimonio.
        for pago in InterpolationStorage.get_payments(grupo['id']):
            if InterpolationStorage.delete_payment(pago['id']):
                borrados += 1
        for pago in suyos:
            InterpolationStorage.create_payment(
                group_id=grupo['id'],
                amount=pago['amount'],
                start_date=pago['start'],
                end_date=pago['end'] or FECHA_CENTINELA,
                note=pago['motivo'] or 'generado',
            )
            escritos += 1

    logger.info("Regeneración: %s pagos borrados, %s escritos en %s portafolio(s)",
                borrados, escritos, len(portafolios))
    return {'ok': True, 'pagos_borrados': borrados, 'pagos_escritos': escritos, **previa}


def estado() -> Dict[str, Any]:
    """Dónde está el corte ahora mismo, sin escribir nada."""
    filas = []
    for portafolio in _portafolios():
        grupo = _grupo_sombra(portafolio['id'])
        generado = None
        if grupo is None:
            for g in InterpolationStorage.get_groups(type_filter=None):
                if g.get('fondo_origen') == portafolio['id'] and g.get('type') == 'fixed':
                    generado = g
                    break
        filas.append({
            'portafolio': portafolio['name'],
            'pagos_propios': len(InterpolationStorage.get_payments(portafolio['id'])),
            'sombra': len(InterpolationStorage.get_payments(grupo['id'])) if grupo else 0,
            'generado_activo': len(InterpolationStorage.get_payments(generado['id'])) if generado else 0,
        })
    cortado = all(f['pagos_propios'] == 0 and f['generado_activo'] > 0 for f in filas) if filas else False
    return {'portafolios': filas, 'cortado': cortado}
