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

#: Cuánto puede moverse la serie diaria y seguir considerándose la misma. Es el redondeo a
#: enteros del usuario; por encima de esto hay que mirar antes de cortar.
TOLERANCIA_CORTE = 2.0

PREFIJO = 'Pagos '

#: Un tramo abierto **no se puede escribir con `end_date` vacío**: `get_payments()` hace
#: `dropna` sobre las dos fechas, así que la fila desaparecería del dashboard y de la UI —
#: justo el defecto que tenían las filas fantasma que hubo que limpiar a mano. Se escribe
#: con la misma fecha centinela que el usuario ya usa, que sí pasa el filtro y que
#: `_apply_fixed_payment` aplica hasta el año 3000, o sea para siempre.
FECHA_CENTINELA = '3000-01-01'


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


# ── Paso 1: sembrar la sombra ────────────────────────────────────────────────

def sembrar_sombra() -> Dict[str, Any]:
    """Materializa los pagos generados en grupos `shadow`. Idempotente.

    No toca los grupos originales ni sus pagos, y como `shadow` no lo aplica nadie, el
    dashboard sigue exactamente igual mientras dure la validación.
    """
    from contabilidad.backend.services.investments import posiciones

    previsualizacion = posiciones.get_neutralization_preview()
    generados = previsualizacion['pagos_generados']

    resultado = []
    for portafolio in _portafolios():
        suyos = [p for p in generados if p['portafolio_id'] == portafolio['id']]

        anterior = _grupo_sombra(portafolio['id'])
        if anterior:
            InterpolationStorage.delete_group(anterior['id'])

        grupo = InterpolationStorage.create_group(
            name=f"{PREFIJO}{portafolio['name']}",
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
            'equivalente': maximo <= TOLERANCIA_CORTE,
            'tolerancia': TOLERANCIA_CORTE,
        }


def _pagos_de_grupos(tipos: Sequence[str], excluir: Sequence[str] = ()) -> List[Dict[str, Any]]:
    """Todos los pagos aplicables de los grupos de esos tipos, con la forma de `serie()`."""
    pagos = []
    for grupo in InterpolationStorage.get_groups(type_filter=None):
        if grupo.get('type') not in tipos or grupo['id'] in excluir:
            continue
        for pago in InterpolationStorage.get_payments(grupo['id']):
            pagos.append({
                'amount': float(pago['amount']),
                'start': pago['start_date'].isoformat() if pago['start_date'] else None,
                'end': pago['end_date'].isoformat() if pago['end_date'] else None,
            })
    return pagos


def verificar(hoy: Optional[date] = None) -> Dict[str, Any]:
    """Compara `PAGOS_FIJOS(t)` antes y después del corte. **No escribe nada.**

    - *Antes*: los grupos `fixed` como están hoy.
    - *Después*: los mismos `fixed` **menos** los pagos de los portafolios de inversión,
      **más** los pagos de los grupos sombra.

    Se leen los pagos con `get_payments()` a propósito, para medir exactamente lo que el
    dashboard aplicaría y no lo que dice el CSV — hay filas que el CSV tiene y el
    dashboard descarta.
    """
    hoy = hoy or date.today()
    portafolios = _portafolios()
    ids_portafolio = [p['id'] for p in portafolios]
    ids_sombra = [g['id'] for g in (_grupo_sombra(p['id']) for p in portafolios) if g]

    if not ids_sombra:
        return {'error': 'No hay grupos sombra: corre sembrar_sombra() primero.'}

    antes = _pagos_de_grupos(['fixed'])
    despues = _pagos_de_grupos(['fixed'], excluir=ids_portafolio) + _pagos_de_grupos([TIPO_SOMBRA])

    inicios = [neutralizacion._to_date(p['start']) for p in antes + despues]
    inicios = [i for i in inicios if i is not None]
    if not inicios:
        return {'error': 'No hay pagos que comparar.'}

    fechas: List[date] = []
    dia = min(inicios)
    while dia <= hoy:
        fechas.append(dia)
        dia += timedelta(days=1)

    equivalencia = Equivalencia(
        fechas=[f.isoformat() for f in fechas],
        antes=neutralizacion.serie(antes, fechas),
        despues=neutralizacion.serie(despues, fechas),
    )
    return {
        'fecha': hoy.isoformat(),
        'pagos_antes': len(antes),
        'pagos_despues': len(despues),
        'grupos_sombra': len(ids_sombra),
        **equivalencia.to_dict(),
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
        return {
            'ok': False,
            'error': (f"La serie se movería {comprobacion['max_desvio']} > "
                      f"{TOLERANCIA_CORTE}. Revisa `peores_dias` o pasa forzar=True."),
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
