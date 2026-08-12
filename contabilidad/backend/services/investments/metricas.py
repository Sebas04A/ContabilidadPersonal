"""
metricas.py — Qué tan bien (o mal) rindió la plata.

Todo se calcula sobre **movimientos**, nunca sobre columnas de la posición. Eso es lo que
permite que la misma función sirva para un plazo fijo y para una posición externa con
aportes y retiros parciales: lo único que cambia son las filas, no el cálculo.

Tres medidas, y cada una responde una pregunta distinta:

- **TNA** (`posiciones.py`): interés sobre capital, anualizado por días calendario. Sirve
  para comparar dos certificados entre sí.
- **TNA ponderada por capital-día**: la de un conjunto de posiciones. Un CDT de 28.000 a
  tres meses pesa más que uno de 4.000 a un mes, que es lo que uno espera al preguntar
  "¿a cuánto me rindió la plata este año?".
- **XIRR**: la tasa que hace cero el valor presente de todos los flujos con sus fechas
  reales. Es la única que no se rompe cuando hay aportes parciales, y por eso es la que
  va a seguir sirviendo cuando entren inversiones fuera del banco. Para un plazo fijo
  simple da prácticamente la TEA.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

DIAS_ANIO = 365

#: Signo de cada tipo de movimiento visto desde el bolsillo del usuario: poner plata es
#: negativo, recibirla es positivo.
SIGNO = {
    'aporte': -1,
    'retiro': +1,
    'interes': +1,
    'dividendo': +1,
    'retencion': -1,
    'comision': -1,
}

#: Un `ajuste` es plata de inversión que quedó suelta, no capital invertido. Contarlo
#: como inversión inflaría el rendimiento con dinero que no estaba rindiendo nada.
TIPOS_INVERTIDOS = ('plazo_fijo', 'valuada')


def _to_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


# ── XIRR ─────────────────────────────────────────────────────────────────────

def _vpn(tasa: float, flujos: Sequence[Tuple[date, float]], origen: date) -> float:
    """Valor presente neto a una tasa anual (`tasa` = 0.05 es 5 %)."""
    return sum(
        monto / (1.0 + tasa) ** ((f - origen).days / DIAS_ANIO)
        for f, monto in flujos
    )


def xirr(flujos: Sequence[Tuple[Any, float]], maximo_iter: int = 100) -> Optional[float]:
    """Tasa interna de retorno con fechas irregulares, en porcentaje anual.

    Devuelve None si los flujos no permiten una respuesta: hacen falta al menos una
    salida y una entrada, y la raíz tiene que existir dentro de un rango razonable
    (−99 % a +1000 %). Se resuelve por bisección porque Newton se va a cualquier lado
    con series cortas, y aquí las series son cortas por definición.
    """
    limpios = [(_to_date(f), float(m)) for f, m in flujos]
    limpios = [(f, m) for f, m in limpios if f is not None and m]
    if len(limpios) < 2:
        return None
    if not (any(m < 0 for _, m in limpios) and any(m > 0 for _, m in limpios)):
        return None

    limpios.sort(key=lambda x: x[0])
    origen = limpios[0][0]

    bajo, alto = -0.99, 10.0
    v_bajo, v_alto = _vpn(bajo, limpios, origen), _vpn(alto, limpios, origen)
    if v_bajo * v_alto > 0:
        return None

    for _ in range(maximo_iter):
        medio = (bajo + alto) / 2
        v_medio = _vpn(medio, limpios, origen)
        if abs(v_medio) < 1e-9 or (alto - bajo) < 1e-9:
            break
        if v_bajo * v_medio < 0:
            alto, v_alto = medio, v_medio
        else:
            bajo, v_bajo = medio, v_medio

    return round((bajo + alto) / 2 * 100, 4)


def flujos_de(vistas: Sequence[Dict[str, Any]]) -> List[Tuple[date, float]]:
    """Los movimientos de varias posiciones como flujos de caja con signo."""
    flujos: List[Tuple[date, float]] = []
    for vista in vistas:
        for movimiento in vista.get('movimientos', []):
            fecha = _to_date(movimiento.get('fecha'))
            signo = SIGNO.get(movimiento.get('tipo'))
            if fecha is None or signo is None:
                continue
            flujos.append((fecha, signo * float(movimiento.get('monto') or 0.0)))
    return flujos


def cerrar_abiertas(vistas: Sequence[Dict[str, Any]], hoy: date) -> List[Tuple[date, float]]:
    """Flujos de cierre ficticios para que XIRR pueda con las posiciones abiertas.

    Una posición abierta no tiene retiro, así que sus flujos son solo salidas y la TIR no
    existe. Se le suma hoy el valor que tendría si se cancelara: capital vigente más el
    interés que lleva devengado.
    """
    extras: List[Tuple[date, float]] = []
    for vista in vistas:
        if vista.get('estado') != 'abierta':
            continue
        valor = float(vista.get('capital_vigente') or 0.0) + (interes_devengado(vista, hoy) or 0.0)
        if valor:
            extras.append((hoy, round(valor, 2)))
    return extras


# ── Devengo ──────────────────────────────────────────────────────────────────

def interes_devengado(vista: Dict[str, Any], hoy: Optional[date] = None) -> Optional[float]:
    """Interés corrido de una posición abierta, si se sabe la tasa pactada.

    Sin `tasa_pactada` no hay forma honesta de estimarlo, así que devuelve None en vez de
    inventar un número con la tasa de otra posición.
    """
    if vista.get('estado') != 'abierta':
        return None
    tasa = vista.get('tasa_pactada')
    apertura = _to_date(vista.get('fecha_apertura'))
    capital = float(vista.get('capital_vigente') or 0.0)
    if not tasa or apertura is None or capital <= 0:
        return None

    hoy = hoy or date.today()
    dias = max((hoy - apertura).days, 0)
    return round(capital * (float(tasa) / 100) * dias / 360, 2)


def dias_restantes(vista: Dict[str, Any], hoy: Optional[date] = None) -> Optional[int]:
    """Cuántos días le faltan a una posición abierta con plazo pactado."""
    plazo = vista.get('plazo_pactado_dias')
    apertura = _to_date(vista.get('fecha_apertura'))
    if vista.get('estado') != 'abierta' or not plazo or apertura is None:
        return None
    return (apertura + timedelta(days=int(plazo)) - (hoy or date.today())).days


def fecha_vencimiento(vista: Dict[str, Any]) -> Optional[str]:
    plazo = vista.get('plazo_pactado_dias')
    apertura = _to_date(vista.get('fecha_apertura'))
    if vista.get('estado') != 'abierta' or not plazo or apertura is None:
        return None
    return (apertura + timedelta(days=int(plazo))).isoformat()


# ── Agregados ────────────────────────────────────────────────────────────────

def _capital_dia(vistas: Sequence[Dict[str, Any]], hoy: date) -> float:
    """USD·día: cuánta plata estuvo invertida y por cuánto tiempo.

    Es el denominador honesto para ponderar tasas, y por sí solo ya dice algo — que la
    plata trabajó, no solo que existió.
    """
    total = 0.0
    for vista in vistas:
        if vista.get('tipo') not in TIPOS_INVERTIDOS:
            continue
        apertura = _to_date(vista.get('fecha_apertura'))
        if apertura is None:
            continue
        cierre = _to_date(vista.get('fecha_cierre')) or hoy
        total += float(vista.get('capital') or 0.0) * max((cierre - apertura).days, 0)
    return round(total, 2)


def _tna_ponderada(vistas: Sequence[Dict[str, Any]], hoy: date) -> Optional[float]:
    """Interés total sobre capital-día, anualizado. La tasa "de verdad" del conjunto.

    Las posiciones sin fecha de apertura quedan fuera **de las dos partes** de la
    división. Son las sembradas a mano, abiertas antes de que empiece el historial: no
    aportan capital-día porque no se sabe cuántos días duraron, y dejar su interés en el
    numerador disparaba la tasa de 2024 a un 34 % que no existió.
    """
    elegibles = [
        v for v in vistas
        if v.get('estado') == 'cerrada' and _to_date(v.get('fecha_apertura')) is not None
    ]
    capital_dia = _capital_dia(elegibles, hoy)
    if capital_dia <= 0:
        return None
    interes = sum(float(v.get('interes') or 0.0) for v in elegibles)
    return round(interes / capital_dia * DIAS_ANIO * 100, 4)


def calcular_kpis(vistas: Sequence[Dict[str, Any]], hoy: date) -> Dict[str, Any]:
    """Los números de un conjunto de posiciones (todas, o las de un portafolio)."""
    invertidas = [v for v in vistas if v.get('tipo') in TIPOS_INVERTIDOS]
    abiertas = [v for v in invertidas if v.get('estado') == 'abierta']
    cerradas = [v for v in invertidas if v.get('estado') == 'cerrada']
    ajustes = [v for v in vistas if v.get('tipo') == 'ajuste']
    flujos_portafolio = [v for v in vistas if v.get('tipo') == 'flujo']

    interes = round(sum(float(v.get('interes') or 0.0) for v in vistas), 2)
    retencion = round(sum(float(v.get('retencion') or 0.0) for v in vistas), 2)
    devengado = [interes_devengado(v, hoy) for v in abiertas]
    devengado_total = round(sum(d for d in devengado if d), 2)

    vencimientos = sorted(f for f in (fecha_vencimiento(v) for v in abiertas) if f)
    # Solo lo invertido entra en la TIR. Una matrícula pagada con lo que devolvió un
    # certificado es un flujo del portafolio, no una decisión de inversión: contarla como
    # salida de caja convertiría el rendimiento en una pérdida enorme que nunca existió.
    # Lo mismo vale para los `ajuste`, que ya estaban entrando.
    flujos = flujos_de(invertidas) + cerrar_abiertas(invertidas, hoy)

    return {
        'capital_invertido': round(sum(float(v.get('capital_vigente') or 0.0) for v in abiertas), 2),
        # Plata de inversión que está fuera de cualquier certificado, sin rendir.
        'residual_suelto': round(sum(float(v.get('capital_vigente') or 0.0) for v in ajustes), 2),
        # Plata que salió del portafolio y no volvió (matrícula), y la que llegó de fuera.
        'salidas': round(sum(float(v.get('capital') or 0.0) for v in flujos_portafolio), 2),
        'entradas': round(sum(float(v.get('retirado') or 0.0) for v in flujos_portafolio), 2),
        'capital_rotado': round(sum(float(v.get('capital') or 0.0) for v in invertidas), 2),
        'interes_cobrado': interes,
        'retencion': retencion,
        'interes_neto': round(interes - retencion, 2),
        'interes_devengado': devengado_total,
        'tna_ponderada': _tna_ponderada(invertidas, hoy),
        'capital_dia': _capital_dia(invertidas, hoy),
        'xirr': xirr(flujos),
        'posiciones': len(vistas),
        'abiertas': len(abiertas),
        'cerradas': len(cerradas),
        # Las sembradas sin apertura conocida no entran en la TNA ponderada; decirlo
        # evita que el número parezca calculado sobre todo cuando no lo está.
        'sin_apertura': sum(1 for v in invertidas if not _to_date(v.get('fecha_apertura'))),
        'proximo_vencimiento': vencimientos[0] if vencimientos else None,
    }


def resumen(vistas: Sequence[Dict[str, Any]],
            portafolios: Sequence[Dict[str, Any]],
            hoy: Optional[date] = None) -> Dict[str, Any]:
    """KPIs globales, por portafolio, y separando lo propio de lo que está en custodia."""
    hoy = hoy or date.today()
    por_id = {p['id']: p for p in portafolios}

    detalle = []
    for portafolio in portafolios:
        del_portafolio = [v for v in vistas if v.get('portafolio_id') == portafolio['id']]
        detalle.append({
            'portafolio_id': portafolio['id'],
            'nombre': portafolio['name'],
            'es_custodia': bool(portafolio.get('es_custodia')),
            **calcular_kpis(del_portafolio, hoy),
        })

    def _es_propio(vista: Dict[str, Any]) -> bool:
        portafolio = por_id.get(vista.get('portafolio_id'))
        return not (portafolio and portafolio.get('es_custodia'))

    propias = [v for v in vistas if _es_propio(v)]
    custodia = [v for v in vistas if not _es_propio(v)]

    return {
        'fecha': hoy.isoformat(),
        'global': calcular_kpis(vistas, hoy),
        'propio': calcular_kpis(propias, hoy),
        'custodia': calcular_kpis(custodia, hoy),
        'por_portafolio': sorted(detalle, key=lambda d: -d['capital_rotado']),
        'sin_portafolio': sum(1 for v in vistas if not v.get('portafolio_id')),
    }


def por_anio(vistas: Sequence[Dict[str, Any]], hoy: Optional[date] = None) -> List[Dict[str, Any]]:
    """Rendimiento por año de cierre. Es donde se ve el desplome de 7 % a 3 %."""
    hoy = hoy or date.today()
    agrupadas: Dict[int, List[Dict[str, Any]]] = {}
    for vista in vistas:
        cierre = _to_date(vista.get('fecha_cierre'))
        if cierre is None or vista.get('tipo') not in TIPOS_INVERTIDOS:
            continue
        agrupadas.setdefault(cierre.year, []).append(vista)

    filas = []
    for anio, del_anio in sorted(agrupadas.items()):
        capitales = [float(v.get('capital') or 0.0) for v in del_anio]
        filas.append({
            'anio': anio,
            'posiciones': len(del_anio),
            'capital_medio': round(sum(capitales) / len(capitales), 2) if capitales else 0.0,
            'interes': round(sum(float(v.get('interes') or 0.0) for v in del_anio), 2),
            'tna_ponderada': _tna_ponderada(del_anio, hoy),
        })
    return filas


def timeline(vistas: Sequence[Dict[str, Any]],
             portafolios: Sequence[Dict[str, Any]] = (),
             hoy: Optional[date] = None) -> Dict[str, Any]:
    """Serie diaria de capital invertido e interés acumulado, con sus eventos.

    Se arma con deltas y una suma acumulada en vez de recorrer las posiciones día por
    día: son dos años y medio de historia y el resultado es idéntico.
    """
    hoy = hoy or date.today()
    invertidas = [v for v in vistas if v.get('tipo') in TIPOS_INVERTIDOS]
    if not invertidas:
        return {'fechas': [], 'capital': [], 'interes_acumulado': [], 'eventos': [], 'por_portafolio': []}

    nombres = {p['id']: p['name'] for p in portafolios}
    deltas_capital: Dict[date, float] = {}
    deltas_interes: Dict[date, float] = {}
    deltas_portafolio: Dict[str, Dict[date, float]] = {}
    eventos: List[Dict[str, Any]] = []

    for vista in invertidas:
        portafolio_id = vista.get('portafolio_id') or ''
        por_p = deltas_portafolio.setdefault(portafolio_id, {})
        for movimiento in vista.get('movimientos', []):
            fecha = _to_date(movimiento.get('fecha'))
            if fecha is None:
                continue
            tipo, monto = movimiento.get('tipo'), float(movimiento.get('monto') or 0.0)
            if tipo == 'aporte':
                deltas_capital[fecha] = deltas_capital.get(fecha, 0.0) + monto
                por_p[fecha] = por_p.get(fecha, 0.0) + monto
            elif tipo == 'retiro':
                deltas_capital[fecha] = deltas_capital.get(fecha, 0.0) - monto
                por_p[fecha] = por_p.get(fecha, 0.0) - monto
            elif tipo in ('interes', 'dividendo'):
                deltas_interes[fecha] = deltas_interes.get(fecha, 0.0) + monto
            elif tipo in ('retencion', 'comision'):
                deltas_interes[fecha] = deltas_interes.get(fecha, 0.0) - monto

        apertura = _to_date(vista.get('fecha_apertura'))
        cierre = _to_date(vista.get('fecha_cierre'))
        if apertura:
            eventos.append({
                'fecha': apertura.isoformat(), 'tipo': 'apertura',
                'capital': vista.get('capital'), 'posicion_id': vista.get('id'),
                'portafolio': nombres.get(portafolio_id, ''),
            })
        if cierre:
            eventos.append({
                'fecha': cierre.isoformat(), 'tipo': 'cierre',
                'capital': vista.get('capital'), 'interes': vista.get('interes'),
                'posicion_id': vista.get('id'), 'portafolio': nombres.get(portafolio_id, ''),
                'tna': vista.get('tna'),
            })

    inicio = min(list(deltas_capital) + list(deltas_interes))
    fin = max(max(list(deltas_capital) + list(deltas_interes)), hoy)

    fechas, capital, interes = [], [], []
    acumulado_capital = acumulado_interes = 0.0
    series_portafolio = {pid: [] for pid in deltas_portafolio}
    acumulado_portafolio = {pid: 0.0 for pid in deltas_portafolio}

    dia = inicio
    while dia <= fin:
        acumulado_capital = round(acumulado_capital + deltas_capital.get(dia, 0.0), 2)
        acumulado_interes = round(acumulado_interes + deltas_interes.get(dia, 0.0), 2)
        for pid, deltas in deltas_portafolio.items():
            acumulado_portafolio[pid] = round(acumulado_portafolio[pid] + deltas.get(dia, 0.0), 2)
            series_portafolio[pid].append(acumulado_portafolio[pid])
        fechas.append(dia.isoformat())
        capital.append(acumulado_capital)
        interes.append(acumulado_interes)
        dia += timedelta(days=1)

    return {
        'fechas': fechas,
        'capital': capital,
        'interes_acumulado': interes,
        'eventos': sorted(eventos, key=lambda e: e['fecha']),
        'por_portafolio': [
            {'portafolio_id': pid, 'nombre': nombres.get(pid, 'Sin portafolio'), 'capital': serie}
            for pid, serie in series_portafolio.items()
        ],
    }
