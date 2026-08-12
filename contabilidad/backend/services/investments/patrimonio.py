"""
patrimonio.py — El puente entre las posiciones y el `NOTIONCUM` del dashboard.

Mientras la plata está dentro de un certificado, el saldo bancario no la muestra y el
pago fijo la resta del flujo: el patrimonio la trata como si no existiera. Este módulo
devuelve, para cada día, **cuánto capital estaba efectivamente invertido**, que es lo que
falta para poder sumarlo.

Dos reglas deciden qué entra:

1. **Solo lo propio.** `Inversiones_Uni` e `Inversiones_Madre` están marcados `es_custodia`:
   son plata de otro que vive en tu cuenta. Se siguen igual que las demás, pero no son tu
   patrimonio. Una posición sin portafolio cuenta como propia, que es el mismo criterio
   que usa `metricas.resumen`.
2. **Solo lo que está dentro de una posición.** Los `ajuste` quedan fuera (los filtra
   `metricas.timeline` por `TIPOS_INVERTIDOS`): son plata de inversión suelta, que el
   saldo bancario ya muestra. Sumarla aquí sería contarla dos veces.

El interés devengado de las posiciones abiertas **no** se suma: es una estimación, y el
patrimonio no es lugar para estimaciones.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from contabilidad.backend.logger import get_logger
from contabilidad.backend.services.investments import metricas

logger = get_logger(__name__)


def capital_propio(vistas: Sequence[Dict[str, Any]],
                   portafolios: Sequence[Dict[str, Any]],
                   hoy: Optional[date] = None) -> Dict[str, float]:
    """`fecha ISO -> capital propio que estaba dentro de una posición ese día`.

    La serie es densa: trae todos los días de calendario entre el primer movimiento y hoy.
    """
    custodia = {p['id'] for p in portafolios if p.get('es_custodia')}
    propias = [v for v in vistas if v.get('portafolio_id') not in custodia]
    serie = metricas.timeline(propias, portafolios, hoy=hoy)
    return dict(zip(serie['fechas'], serie['capital']))


def capital_propio_diario(hoy: Optional[date] = None) -> Dict[str, float]:
    """Lo mismo, leyendo las posiciones guardadas."""
    from contabilidad.backend.services.investments import posiciones

    portafolios = posiciones.list_portfolios()
    return capital_propio(posiciones.list_positions(), portafolios, hoy=hoy)


def evaluar(serie: Dict[str, float], fechas: Sequence[date]) -> List[float]:
    """El capital invertido en cada fecha pedida, sin depender de que vengan ordenadas.

    Fuera del rango de la serie no hay NaN sino la respuesta correcta: **antes** del primer
    movimiento no había nada invertido; **después** del último sigue vigente lo que hubiera
    quedado abierto.
    """
    if not serie:
        return [0.0] * len(fechas)

    primera, ultima = min(serie), max(serie)
    valores = []
    for momento in fechas:
        clave = momento.isoformat()
        if clave in serie:
            valores.append(serie[clave])
        else:
            valores.append(0.0 if clave < primera else serie[ultima])
    return valores
