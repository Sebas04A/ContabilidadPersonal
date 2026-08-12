"""
portafolios.py — De qué portafolio es cada posición detectada.

El banco no lo dice: para el Pichincha todos los plazos fijos son de la misma cuenta.
Pero los pagos fijos que el usuario lleva a mano en `pagos.csv` sí lo saben, porque cada
portafolio tiene su propia cadena de residuales y **esa cadena cambia exactamente los
días en que una inversión de ese portafolio se abre o se cierra**.

De ahí sale todo este módulo:

    portafolio de una posición  =  el que tiene pagos que empiezan o terminan
                                   justo en su apertura y en su cierre

Sobre los datos reales el heurístico acierta 13 de 14 sin ambigüedad. La catorceava es
el CDT de 38.000 del 2025-08-12, donde **dos** portafolios tienen frontera ese día — que
es justo lo que se espera, porque ese certificado juntó plata de `Mias` y de `Madre`.

Y cuánto puso cada uno también sale de la misma fuente: el residual de un portafolio
justo antes de la apertura menos el de justo después es lo que ese portafolio metió.

    Mias   28.154 → 543     ⇒ puso 27.611
    Madre  10.389 → 0       ⇒ puso 10.389
                              27.611 + 10.389 = 38.000 ✓

Nada de esto se escribe solo: son sugerencias para la pantalla de Conciliación.
Confirmar es siempre del usuario, porque un reparto es una decisión suya.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from contabilidad.backend.logger import get_logger
from contabilidad.backend.services.investments.detector import DetectedPosition
from contabilidad.backend.storage.variables_storage import InterpolationStorage

logger = get_logger(__name__)

#: Un candidato con las dos fronteras (apertura y cierre) es una coincidencia fuerte;
#: con una sola puede ser casualidad de calendario.
SCORE_COMPLETO = 2


def _to_date(value: Any) -> Optional[date]:
    if value is None or value == '':
        return None
    try:
        ts = pd.to_datetime(value)
    except (ValueError, TypeError):
        return None
    return None if pd.isna(ts) else ts.date()


class CadenaPagos:
    """Los pagos fijos de un portafolio, listos para preguntarles fechas y residuales."""

    def __init__(self, portafolio_id: str, nombre: str, pagos: Sequence[Dict[str, Any]]):
        self.portafolio_id = portafolio_id
        self.nombre = nombre
        self.pagos = [
            (_to_date(p.get('start_date')), _to_date(p.get('end_date')), float(p.get('amount') or 0.0))
            for p in pagos
        ]
        self.fronteras = {d for inicio, fin, _ in self.pagos for d in (inicio, fin) if d}

    def residual(self, momento: date) -> float:
        """Cuánta plata de este portafolio estaba fuera de una inversión ese día.

        Misma ventana que `mark_fixed_payments`: `start <= día < end`. Un pago sin
        `start` cuenta desde siempre; sin `end`, hasta siempre.
        """
        total = 0.0
        for inicio, fin, monto in self.pagos:
            if inicio is not None and momento < inicio:
                continue
            if fin is not None and momento >= fin:
                continue
            total += monto
        return round(total, 2)

    def aporte_en(self, apertura: date) -> float:
        """Lo que este portafolio puso el día que se abrió una inversión.

        El residual del día anterior menos el del propio día: la plata que dejó de estar
        suelta es exactamente la que entró al certificado.
        """
        return round(self.residual(apertura - timedelta(days=1)) - self.residual(apertura), 2)


def cargar_cadenas() -> List[CadenaPagos]:
    """Una cadena por portafolio marcado `es_inversion`."""
    cadenas: List[CadenaPagos] = []
    for grupo in InterpolationStorage.get_groups(type_filter=None):
        if not grupo.get('es_inversion'):
            continue
        cadenas.append(CadenaPagos(
            grupo['id'], grupo['name'], InterpolationStorage.get_payments(grupo['id'])
        ))
    return cadenas


def sugerir_para(detectada: DetectedPosition,
                 cadenas: Optional[Sequence[CadenaPagos]] = None) -> Dict[str, Any]:
    """Candidatos a portafolio de una posición detectada, mejor primero.

    Devuelve `sugerido` solo cuando hay un único candidato con las dos fronteras; si hay
    varios, `reparto` queda en True y cada candidato trae su `aporte_estimado`.
    """
    cadenas = cargar_cadenas() if cadenas is None else cadenas
    apertura = detectada.fecha_apertura
    cierre = detectada.fecha_cierre

    candidatos: List[Dict[str, Any]] = []
    for cadena in cadenas:
        coincidencias = [d.isoformat() for d in (apertura, cierre) if d and d in cadena.fronteras]
        if not coincidencias:
            continue
        candidatos.append({
            'portafolio_id': cadena.portafolio_id,
            'nombre': cadena.nombre,
            'score': len(coincidencias),
            'fronteras': coincidencias,
            'aporte_estimado': cadena.aporte_en(apertura) if apertura else 0.0,
        })

    candidatos.sort(key=lambda c: (-c['score'], -c['aporte_estimado']))
    completos = [c for c in candidatos if c['score'] >= SCORE_COMPLETO]

    # Con un solo candidato fuerte no hay nada que repartir. Con varios, el certificado
    # juntó plata de más de un portafolio y hace falta que el usuario confirme cuánto
    # puso cada uno.
    reparto = len(completos) > 1
    sugerido = None
    if len(completos) == 1:
        sugerido = completos[0]['portafolio_id']
    elif not completos and len(candidatos) == 1:
        # Una sola frontera, pero nadie más la reclama: alcanza para sugerirlo.
        sugerido = candidatos[0]['portafolio_id']

    return {
        'candidatos': candidatos,
        'sugerido': sugerido,
        'reparto': reparto,
        'reparto_sugerido': (
            [{'portafolio_id': c['portafolio_id'], 'nombre': c['nombre'],
              'capital': c['aporte_estimado']} for c in completos] if reparto else []
        ),
    }


def sugerir(detectadas: Sequence[DetectedPosition]) -> Dict[str, Dict[str, Any]]:
    """`tx_apertura_id -> sugerencia`, para adjuntar al diff de conciliación."""
    cadenas = cargar_cadenas()
    if not cadenas:
        return {}
    return {d.tx_apertura_id: sugerir_para(d, cadenas) for d in detectadas}
