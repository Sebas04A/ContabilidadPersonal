"""
analisis.py — Una inversión, mirada de cerca.

El resto del módulo mira el conjunto: cuánto capital hay invertido, qué rindió el año
pasado, cómo va el portafolio. Aquí se mira **una sola posición** y se responden tres
preguntas que el agregado no puede responder:

1. **¿Cómo subió?** El interés de un plazo fijo se cobra de golpe el día del cierre, así
   que en los datos crudos la posición es una línea plana con un escalón al final. Eso es
   verdad contable pero no es verdad económica: la plata rindió todos los días. La curva
   de esta pantalla reparte el interés día a día, que es como de verdad creció.

2. **¿Cómo puede seguir?** Para una posición abierta, el devengo continúa hasta el
   vencimiento con la tasa pactada. Es aritmética, no pronóstico: el banco ya se
   comprometió a ese número.

3. **¿Cuánto gané?** Bruto, retención y neto, y el rendimiento sobre el capital.

**La tasa con la que se reparte el interés no se inventa.** Para una posición cerrada se
despeja del interés que el banco pagó de verdad (`interes / capital · 360 / plazo`), así
que la curva **termina exactamente en el interés real** — no es una aproximación que se
parece, es una redistribución en el tiempo de un número conocido. Para una abierta hace
falta la tasa pactada; sin ella no hay curva de crecimiento y se dice por qué, en vez de
dibujar una recta inventada con la tasa de otra posición (el mismo criterio que
`metricas.interes_devengado`).

El escenario de reinversión es lo único que **no** es aritmética sobre datos ciertos, y va
aparte por eso: supone que el usuario renueva capital e interés al mismo plazo y a la misma
tasa, cosa que el historial demuestra que no pasa (las tasas cayeron del 8,70 % al 2,90 %).
Sirve para dimensionar, no para planificar.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from contabilidad.backend.logger import get_logger
from contabilidad.backend.services.investments import metricas

logger = get_logger(__name__)

#: Base de cálculo del banco: actual/360, comprobada sobre los 15 plazos fijos del
#: historial (§2.9 del handoff). La misma que usa `posiciones.inferir_plazo_y_tasa`.
BASE_ANIO = 360

#: Horizontes del escenario de reinversión, en años.
HORIZONTES = (1, 2, 3, 5, 10)

#: Si no se conoce el plazo, el escenario compone una vez al año. Es el supuesto más
#: conservador de los razonables: renovar más seguido a la misma tasa da un poco más.
PLAZO_POR_DEFECTO = 360


def _to_date(value: Any) -> Optional[date]:
    return metricas._to_date(value)


# ── Con qué tasa se reparte el interés ───────────────────────────────────────

def tasa_para_devengo(vista: Dict[str, Any]) -> Dict[str, Any]:
    """La tasa base 360 con la que repartir el interés en el tiempo, y de dónde sale.

    El orden importa y no es el mismo que el de la tabla de posiciones:

    - **Cerrada** → se despeja del interés realmente cobrado. Es la única que garantiza
      que la curva aterrice en el número del banco, así que gana incluso a una tasa
      capturada a mano (que puede estar redondeada en el certificado).
    - **Abierta** → la pactada, capturada a mano. No hay nada de dónde despejarla.

    Sin tasa devuelve `None` y el motivo, para que la pantalla lo explique en vez de
    dibujar una recta que nadie pidió.
    """
    capital = float(vista.get('capital') or 0.0)
    interes = float(vista.get('interes') or 0.0)
    apertura = _to_date(vista.get('fecha_apertura'))
    cierre = _to_date(vista.get('fecha_cierre'))

    if vista.get('estado') == 'cerrada' and apertura and cierre and capital > 0:
        plazo = (cierre - apertura).days
        if plazo > 0:
            return {
                'tasa': round(interes / capital * BASE_ANIO / plazo * 100, 4),
                'origen': 'liquidada',
                'motivo': None,
            }

    pactada = vista.get('tasa_pactada')
    if pactada:
        return {'tasa': float(pactada), 'origen': 'pactada', 'motivo': None}

    if vista.get('estado') == 'abierta':
        return {
            'tasa': None, 'origen': None,
            'motivo': ('Esta posición sigue abierta y no tiene tasa pactada capturada. '
                       'Sin ella no se puede saber cuánto lleva ganado: captúrala en la '
                       'fila de la posición y la curva aparece.'),
        }
    return {
        'tasa': None, 'origen': None,
        'motivo': 'No se puede deducir una tasa: la posición no tiene interés ni fechas con las que despejarla.',
    }


# ── La curva ─────────────────────────────────────────────────────────────────

def _capital_por_dia(vista: Dict[str, Any], dias: List[date], fin: date) -> List[float]:
    """Capital dentro de la posición cada día.

    **El retiro del último día no baja el capital**, y esa es la única sutileza del
    archivo. En un plazo fijo el retiro de cierre *es* el pago de lo que la posición
    valía: descontarlo haría que la curva se desplomara a cero justo el día que se cobra,
    que es lo contrario de lo que pasó. Un retiro parcial a mitad de vida sí baja el
    capital, porque ahí sí salió plata que dejó de rendir.
    """
    deltas: Dict[date, float] = {}
    for movimiento in vista.get('movimientos', []):
        fecha = _to_date(movimiento.get('fecha'))
        tipo = movimiento.get('tipo')
        if fecha is None or tipo not in ('aporte', 'retiro'):
            continue
        if tipo == 'retiro' and fecha >= fin:
            continue
        signo = 1.0 if tipo == 'aporte' else -1.0
        deltas[fecha] = deltas.get(fecha, 0.0) + signo * float(movimiento.get('monto') or 0.0)

    serie: List[float] = []
    acumulado = 0.0
    for dia in dias:
        acumulado += deltas.get(dia, 0.0)
        serie.append(round(acumulado, 2))
    return serie


def _devengar(dias: List[date], capital: List[float], tasa: Optional[float],
              desde_interes: float = 0.0) -> List[float]:
    """Interés corrido acumulado, día a día, sobre el capital que había cada día.

    Se acumula día por día en vez de con la fórmula cerrada porque el capital puede
    cambiar a mitad de vida (un retiro parcial deja de rendir desde ese día). Con capital
    constante da exactamente lo mismo, y para un plazo fijo cerrado eso significa aterrizar
    en el interés real del banco al centavo.

    El primer día no devenga: la plata entra ese día y empieza a contar al siguiente, que
    es la convención con la que se dedujo la tasa.
    """
    serie: List[float] = []
    acumulado = desde_interes
    for i, dia in enumerate(dias):
        if i > 0 and tasa:
            acumulado += capital[i] * (tasa / 100) / BASE_ANIO
        serie.append(round(acumulado, 2))
    return serie


def _rango(inicio: date, fin: date) -> List[date]:
    dias, dia = [], inicio
    while dia <= fin:
        dias.append(dia)
        dia += timedelta(days=1)
    return dias


def curva(vista: Dict[str, Any], tasa: Optional[float], hoy: date) -> Dict[str, Any]:
    """Serie diaria de capital, interés devengado y valor, desde la apertura hasta hoy."""
    apertura = _to_date(vista.get('fecha_apertura'))
    cierre = _to_date(vista.get('fecha_cierre'))
    if apertura is None:
        return {'fechas': [], 'capital': [], 'interes': [], 'valor': []}

    fin = cierre if cierre else hoy
    if fin < apertura:
        fin = apertura

    dias = _rango(apertura, fin)
    capital = _capital_por_dia(vista, dias, fin)
    interes = _devengar(dias, capital, tasa)

    return {
        'fechas': [d.isoformat() for d in dias],
        'capital': capital,
        'interes': interes,
        'valor': [round(c + i, 2) for c, i in zip(capital, interes)],
    }


def proyeccion(vista: Dict[str, Any], tasa: Optional[float], hoy: date,
               serie: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Lo que falta hasta el vencimiento, si la posición sigue abierta y se sabe cuándo.

    No es un pronóstico: el capital ya está adentro, la tasa ya está pactada y la fecha ya
    está fijada. Es la misma aritmética de la curva, corrida hacia adelante.
    """
    if vista.get('estado') != 'abierta' or not tasa:
        return None
    vencimiento = _to_date(metricas.fecha_vencimiento(vista))
    if vencimiento is None or vencimiento <= hoy:
        return None

    capital_hoy = serie['capital'][-1] if serie['capital'] else 0.0
    interes_hoy = serie['interes'][-1] if serie['interes'] else 0.0

    dias = _rango(hoy, vencimiento)
    capitales = [capital_hoy] * len(dias)
    interes = _devengar(dias, capitales, tasa, desde_interes=interes_hoy)

    return {
        'fechas': [d.isoformat() for d in dias],
        'capital': capitales,
        'interes': interes,
        'valor': [round(c + i, 2) for c, i in zip(capitales, interes)],
        'fecha_vencimiento': vencimiento.isoformat(),
        'dias_restantes': (vencimiento - hoy).days,
        'interes_al_vencimiento': interes[-1],
        'valor_al_vencimiento': round(capital_hoy + interes[-1], 2),
        'falta_por_devengar': round(interes[-1] - interes_hoy, 2),
    }


# ── Cuánto se ganó, y cuánto podría ─────────────────────────────────────────

def ganancia(vista: Dict[str, Any], serie: Dict[str, Any],
             proy: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Lo cobrado (o lo devengado), la retención y el rendimiento sobre el capital."""
    capital = float(vista.get('capital') or 0.0)
    cerrada = vista.get('estado') == 'cerrada'

    bruto = float(vista.get('interes') or 0.0) if cerrada else (serie['interes'][-1] if serie['interes'] else 0.0)
    retencion = float(vista.get('retencion') or 0.0)
    comisiones = float(vista.get('comisiones') or 0.0)
    neto = round(bruto - retencion - comisiones, 2)

    return {
        'realizado': cerrada,
        'capital': round(capital, 2),
        'interes_bruto': round(bruto, 2),
        'retencion': round(retencion, 2),
        'comisiones': round(comisiones, 2),
        'interes_neto': neto,
        'rendimiento_pct': round(neto / capital * 100, 4) if capital > 0 else None,
        # Último punto de la curva real: lo que valía al cerrarse si está cerrada, lo que
        # vale hoy si sigue abierta.
        'valor_final': serie['valor'][-1] if serie['valor'] else None,
        'valor_al_vencimiento': proy['valor_al_vencimiento'] if proy else None,
        # Cuánto rinde cada día que la plata sigue adentro. Es el número que hace
        # tangible la diferencia entre dejarla en el banco y dejarla en la cuenta.
        'interes_por_dia': round(bruto / vista['dias'], 4) if cerrada and vista.get('dias') else (
            round(capital * (vista.get('tasa_pactada') or 0) / 100 / BASE_ANIO, 4)
            if vista.get('tasa_pactada') else None
        ),
    }


def escenarios(base: Optional[float], tasa: Optional[float], plazo: Optional[int],
               horizontes: tuple = HORIZONTES) -> List[Dict[str, Any]]:
    """Cuánto sería si se renovara capital e interés al mismo plazo y a la misma tasa.

    **Esto sí es un supuesto**, y uno que el propio historial contradice: las tasas de
    este banco cayeron del 8,70 % al 2,90 % en dos años. Se calcula para dimensionar el
    interés compuesto, no para planificar sobre él, y por eso viaja separado de `ganancia`.
    """
    if not base or base <= 0 or not tasa or tasa <= 0:
        return []
    plazo = int(plazo or PLAZO_POR_DEFECTO)
    if plazo <= 0:
        return []

    factor = 1 + (tasa / 100) * plazo / BASE_ANIO
    filas = []
    for anios in horizontes:
        renovaciones = anios * BASE_ANIO / plazo
        valor = base * (factor ** renovaciones)
        filas.append({
            'anios': anios,
            'renovaciones': round(renovaciones, 1),
            'valor': round(valor, 2),
            'ganancia': round(valor - base, 2),
        })
    return filas


# ── El portafolio entero: el bolsillo que rueda de certificado en certificado ─
#
# Esta es la unidad que el usuario llama «una inversión»: `Inversiones_Uni` no son doce
# certificados sueltos, es **el mismo dinero** rodando de uno a otro con matrículas
# saliendo por el camino. La vista por posición (arriba en este archivo) es el detalle al
# que se baja desde aquí, no la puerta de entrada.
#
# La cuenta central es una identidad, y por eso se puede comprobar en vez de creer:
#
#     total(t) = aportado_neto(t) + ganancia(t)
#
# donde `aportado_neto` es lo que se puso (saldo inicial + lo que ya estaba dentro +
# entradas − salidas) y `ganancia` es lo que el banco añadió. Si las dos mitades no suman
# el total, algo se está contando dos veces o falta un movimiento.

def _cumsum_por_dia(deltas: Dict[date, float], dias: List[date], inicial: float = 0.0) -> List[float]:
    serie, acumulado = [], inicial
    for dia in dias:
        acumulado = round(acumulado + deltas.get(dia, 0.0), 2)
        serie.append(acumulado)
    return serie


def _deltas(vistas, tipos, signo_por_tipo) -> Dict[date, float]:
    deltas: Dict[date, float] = {}
    for vista in vistas:
        if tipos is not None and vista.get('tipo') not in tipos:
            continue
        for movimiento in vista.get('movimientos', []):
            fecha = _to_date(movimiento.get('fecha'))
            signo = signo_por_tipo.get(movimiento.get('tipo'))
            if fecha is None or signo is None:
                continue
            deltas[fecha] = deltas.get(fecha, 0.0) + signo * float(movimiento.get('monto') or 0.0)
    return deltas


def _devengo_de_las_vivas(invertidas, dias: List[date]) -> List[float]:
    """Lo que las posiciones abiertas llevan corrido cada día, sumado.

    Solo las que tienen tasa pactada: las demás aportan cero y la pantalla lo dice. Es el
    mismo criterio que `metricas.interes_devengado`, no una segunda regla.
    """
    total = [0.0] * len(dias)
    for vista in invertidas:
        if vista.get('estado') != 'abierta' or not vista.get('tasa_pactada'):
            continue
        apertura = _to_date(vista.get('fecha_apertura'))
        if apertura is None:
            continue
        capital = float(vista.get('capital_vigente') or 0.0)
        tasa = float(vista['tasa_pactada'])
        for i, dia in enumerate(dias):
            if dia > apertura:
                total[i] = round(total[i] + capital * (tasa / 100) * (dia - apertura).days / BASE_ANIO, 2)
    return total


def analizar_portafolio(vistas: List[Dict[str, Any]], portafolio: Dict[str, Any],
                        hoy: Optional[date] = None) -> Dict[str, Any]:
    """Cómo creció el bolsillo entero: cuánto hay, cuánto rinde y cuánto ha dejado.

    Las tres series se dibujan apiladas y su suma es el total, que es lo que hace legible
    el gráfico de un portafolio: **lo que está dentro de un certificado rinde y lo que
    está suelto no**, y en `Uni` la diferencia entre las dos es meses de plata parada.
    """
    from contabilidad.backend.services.investments import neutralizacion

    hoy = hoy or date.today()
    del_portafolio = [v for v in vistas if v.get('portafolio_id') == portafolio['id']]
    invertidas = [v for v in del_portafolio if v.get('tipo') in metricas.TIPOS_INVERTIDOS]

    fechas_evento = [
        f for v in del_portafolio for f in (
            _to_date(v.get('fecha_apertura')), _to_date(v.get('fecha_cierre')),
        ) if f is not None
    ] + [
        f for v in del_portafolio for m in v.get('movimientos', [])
        if (f := _to_date(m.get('fecha'))) is not None
    ]
    if not fechas_evento:
        return {
            'portafolio_id': portafolio['id'], 'nombre': portafolio.get('name', ''),
            'apto': False, 'motivo': 'Este portafolio no tiene ninguna posición todavía.',
            'serie': {'fechas': [], 'dentro': [], 'suelto': [], 'devengado': [], 'total': [],
                      'ganancia': [], 'aportado_neto': []},
            'kpis': {}, 'escenarios': [], 'posiciones': [],
        }

    dias = _rango(min(fechas_evento), max(hoy, max(fechas_evento)))

    # El residual —la plata del portafolio que NO está dentro de un certificado— se arma
    # con los eventos de `neutralizacion`, que es donde vive su única definición. Duplicar
    # la fórmula aquí es exactamente cómo se separan dos pantallas que deben coincidir.
    saldo_inicial = float(portafolio.get('saldo_inicial') or 0.0)
    eventos = neutralizacion._eventos_por_portafolio(del_portafolio).get(portafolio['id'], {})
    suelto = _cumsum_por_dia(eventos, dias, saldo_inicial)

    dentro = _cumsum_por_dia(_deltas(invertidas, None, {'aporte': 1.0, 'retiro': -1.0}), dias)
    devengado = _devengo_de_las_vivas(invertidas, dias)

    realizada = _cumsum_por_dia(_deltas(
        del_portafolio, None,
        {'interes': 1.0, 'dividendo': 1.0, 'retencion': -1.0, 'comision': -1.0},
    ), dias)
    ganancia_serie = [round(r + d, 2) for r, d in zip(realizada, devengado)]

    # Lo que ya estaba dentro antes de que empiece el historial: su aporte no pasó por el
    # residual (`_eventos_por_portafolio` lo salta a propósito) pero sí es capital puesto.
    ya_estaba = round(sum(
        float(v.get('capital') or 0.0) for v in invertidas if not v.get('fecha_apertura')
    ), 2)
    flujos_netos = _cumsum_por_dia(
        _deltas([v for v in del_portafolio if v.get('tipo') == 'flujo'], None,
                {'aporte': -1.0, 'retiro': 1.0}), dias)
    aportado_neto = [round(saldo_inicial + ya_estaba + f, 2) for f in flujos_netos]

    total = [round(s + d + g, 2) for s, d, g in zip(suelto, dentro, devengado)]

    salidas = round(sum(float(v.get('capital') or 0.0)
                        for v in del_portafolio if v.get('tipo') == 'flujo'), 2)
    entradas = round(sum(float(v.get('retirado') or 0.0)
                         for v in del_portafolio if v.get('tipo') == 'flujo'), 2)
    kpis_conjunto = metricas.calcular_kpis(del_portafolio, hoy)
    abiertas = [v for v in invertidas if v.get('estado') == 'abierta']
    tendencia = tendencia_tasas(vistas, portafolio['id'], hoy)

    return {
        'portafolio_id': portafolio['id'],
        'nombre': portafolio.get('name', ''),
        'es_custodia': bool(portafolio.get('es_custodia')),
        'apto': True,
        'motivo': None,
        'saldo_inicial': round(saldo_inicial, 2),
        'saldo_inicial_configurado': bool(portafolio.get('saldo_inicial_configurado')),
        'serie': {
            'fechas': [d.isoformat() for d in dias],
            # Las tres capas del gráfico apilado; su suma es `total`.
            'dentro': dentro,
            'suelto': suelto,
            'devengado': devengado,
            'total': total,
            'ganancia': ganancia_serie,
            'aportado_neto': aportado_neto,
        },
        'kpis': {
            'total_hoy': total[-1] if total else 0.0,
            'dentro_hoy': dentro[-1] if dentro else 0.0,
            'suelto_hoy': suelto[-1] if suelto else 0.0,
            'aportado_neto': aportado_neto[-1] if aportado_neto else 0.0,
            'ganancia_acumulada': ganancia_serie[-1] if ganancia_serie else 0.0,
            'interes_cobrado': kpis_conjunto['interes_cobrado'],
            'retencion': kpis_conjunto['retencion'],
            'interes_devengado': devengado[-1] if devengado else 0.0,
            'salidas': salidas,
            'entradas': entradas,
            'tna_ponderada': kpis_conjunto['tna_ponderada'],
            'xirr': kpis_conjunto['xirr'],
            'capital_dia': kpis_conjunto['capital_dia'],
            'certificados': len(invertidas),
            'abiertos': len(abiertas),
            'proximo_vencimiento': kpis_conjunto['proximo_vencimiento'],
            'dias': len(dias),
            # Qué parte del tiempo la plata estuvo trabajando. En `Uni` es la cifra que
            # más duele y la que ninguna otra pantalla enseña.
            'dias_con_plata_parada': sum(
                1 for s, d in zip(suelto, dentro)
                if s > _umbral_material(invertidas) and d <= 0
            ),
        },
        # Lo que la serie diaria sabe y los totales no cuentan: rachas, ritmo de ganancia,
        # coste de la plata quieta y comparación entre certificados.
        'estadisticas': estadisticas(
            {'fechas': [d.isoformat() for d in dias], 'dentro': dentro, 'suelto': suelto,
             'ganancia': ganancia_serie},
            invertidas,
            kpis_conjunto['tna_ponderada'],
        ),
        # Reusa la misma definición que la pestaña de Resumen: el año de cierre manda, y
        # la TNA se pondera por capital-día. Dos tablas de rendimiento anual que no
        # coincidieran serían peor que no tener la segunda.
        'por_anio': metricas.por_anio(del_portafolio, hoy),
        # La tendencia se ajusta sobre TODOS los certificados, no solo los de este
        # portafolio: la tasa la pone el banco y es la misma para todo el dinero a la vez.
        'tasas': tendencia,
        # Un portafolio vaciado (hoy `Uni` tiene 1,33 y `Madre` 0,00) no se proyecta:
        # componer calderilla durante cinco años da una tabla de céntimos con pinta de
        # cálculo. El corte es el mismo umbral material que usan las estadísticas, no un
        # dólar fijo — si no, `Uni` proyectaría ganancias de 21 centavos.
        'proyeccion_ganancia': proyectar_ganancia(
            total[-1] if total and total[-1] >= _umbral_material(invertidas) else None,
            tendencia, hoy),
        'escenarios': escenarios(
            total[-1] if total and total[-1] >= _umbral_material(invertidas) else None,
            kpis_conjunto['tna_ponderada'],
            _plazo_tipico(invertidas),
        ),
        'posiciones': [
            {
                'id': v['id'],
                'fecha_apertura': v.get('fecha_apertura'),
                'fecha_cierre': v.get('fecha_cierre'),
                'estado': v.get('estado'),
                'capital': v.get('capital'),
                'interes': v.get('interes'),
                'tna': v.get('tna_pactada') or v.get('tna'),
                'dias': v.get('dias'),
            }
            for v in sorted(invertidas, key=lambda v: v.get('fecha_apertura') or '')
        ],
        'hoy': hoy.isoformat(),
    }


#: Suelo absoluto: por debajo de un dólar, un saldo es residuo de redondeo.
UMBRAL_PLATA = 1.0

#: Y por encima del suelo, lo que cuenta como «plata parada» es relativo a lo que ese
#: portafolio suele mover. `Uni` termina con 1,33 sueltos tras pagar la matrícula: con un
#: umbral fijo de un dólar, la pantalla anunciaba «148 días con la plata parada» por un
#: dólar y medio. Un 1 % del certificado medio (81 USD en `Uni`, 273 en `Mias`) separa el
#: residuo de una decisión de no reinvertir.
FRACCION_MATERIAL = 0.01


def _umbral_material(invertidas: List[Dict[str, Any]]) -> float:
    capitales = [float(v.get('capital') or 0.0) for v in invertidas if v.get('capital')]
    if not capitales:
        return UMBRAL_PLATA
    return max(UMBRAL_PLATA, sum(capitales) / len(capitales) * FRACCION_MATERIAL)


def _rachas(condicion: List[bool], fechas: List[str]) -> List[Dict[str, Any]]:
    """Tramos continuos en que se cumple la condición, del más largo al más corto."""
    tramos, inicio = [], None
    for i, valor in enumerate(condicion):
        if valor and inicio is None:
            inicio = i
        elif not valor and inicio is not None:
            tramos.append({'desde': fechas[inicio], 'hasta': fechas[i - 1], 'dias': i - inicio})
            inicio = None
    if inicio is not None:
        tramos.append({'desde': fechas[inicio], 'hasta': fechas[-1], 'dias': len(condicion) - inicio})
    return sorted(tramos, key=lambda t: -t['dias'])


def _huecos_entre_certificados(invertidas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cuánto tardó la plata en volver a un certificado después de cada cierre.

    Es el hábito que sí se puede corregir: la tasa la pone el banco, pero los días que la
    plata pasa fuera los pone uno. Solo cuenta si de verdad se reinvirtió después; un
    cierre sin apertura posterior no es un hueco, es el final de la historia.
    """
    cierres = sorted(f for v in invertidas if (f := _to_date(v.get('fecha_cierre'))))
    aperturas = sorted(f for v in invertidas if (f := _to_date(v.get('fecha_apertura'))))
    huecos = []
    for cierre in cierres:
        siguiente = next((a for a in aperturas if a > cierre), None)
        if siguiente is None:
            continue
        huecos.append({
            'desde': cierre.isoformat(),
            'hasta': siguiente.isoformat(),
            'dias': (siguiente - cierre).days,
        })
    return huecos


def estadisticas(serie: Dict[str, Any], invertidas: List[Dict[str, Any]],
                 tna: Optional[float]) -> Dict[str, Any]:
    """Lo que la serie diaria sabe y los totales no cuentan.

    Los tres estados **parten la ventana sin solaparse**: un día es `rindiendo` si hay algo
    dentro de un certificado (aunque además haya suelto), `parada` si hay plata material y
    ninguna está dentro, y `vacio` si no hay plata. Suman siempre el total de días, y eso
    es lo que permite enseñarlos como porcentajes que cierran en 100.

    «Material» es relativo al portafolio, no un dólar fijo — ver `_umbral_material`.

    El **lucro cesante** se calcula a la propia tasa histórica del portafolio, no a una
    inventada: es «lo que esa misma plata habría dado en tus propios certificados». Sin
    tasa conocida no se estima, se devuelve `None`.
    """
    fechas = serie['fechas']
    if not fechas:
        return {}

    umbral = _umbral_material(invertidas)
    rindiendo = [d > 0 for d in serie['dentro']]
    parada = [d <= 0 and s > umbral for d, s in zip(serie['dentro'], serie['suelto'])]
    vacio = [not r and not p for r, p in zip(rindiendo, parada)]

    dias_rindiendo = sum(rindiendo)
    dias_parada = sum(parada)
    ganancia = serie['ganancia'][-1] if serie['ganancia'] else 0.0

    # Lo que la plata quieta habría dado a la tasa del propio portafolio.
    lucro_cesante = None
    if tna:
        lucro_cesante = round(sum(
            s * (tna / 100) / BASE_ANIO
            for s, p in zip(serie['suelto'], parada) if p
        ), 2)

    sueltos_parados = [s for s, p in zip(serie['suelto'], parada) if p]
    huecos = _huecos_entre_certificados(invertidas)
    duraciones = [int(v['dias']) for v in invertidas if v.get('dias')]
    con_tasa = [v for v in invertidas
                if v.get('estado') == 'cerrada' and (v.get('tna_pactada') or v.get('tna'))]

    def _resumen_certificado(vista):
        return {
            'id': vista['id'],
            'fecha_apertura': vista.get('fecha_apertura'),
            'fecha_cierre': vista.get('fecha_cierre'),
            'capital': vista.get('capital'),
            'interes': vista.get('interes'),
            'dias': vista.get('dias'),
            'tna': vista.get('tna_pactada') or vista.get('tna'),
        }

    return {
        'dias_totales': len(fechas),
        'dias_rindiendo': dias_rindiendo,
        'dias_parada': dias_parada,
        'dias_vacio': sum(vacio),
        'pct_rindiendo': round(dias_rindiendo / len(fechas) * 100, 1),
        'pct_parada': round(dias_parada / len(fechas) * 100, 1),
        'desde': fechas[0],
        'hasta': fechas[-1],

        # Cuánto se ganó y en cuánto tiempo. Los dos ritmos: por día de calendario y por
        # día en que la plata de verdad estaba trabajando, que casi siempre es más alto.
        'ganancia': ganancia,
        'ganancia_por_dia': round(ganancia / len(fechas), 4),
        'ganancia_por_dia_rindiendo': round(ganancia / dias_rindiendo, 4) if dias_rindiendo else None,
        'ganancia_por_mes': round(ganancia / len(fechas) * 30, 2),

        # El coste de la plata quieta, y dónde estuvo quieta más tiempo.
        'lucro_cesante': lucro_cesante,
        'suelto_medio_parado': round(sum(sueltos_parados) / len(sueltos_parados), 2) if sueltos_parados else 0.0,
        'umbral_material': round(umbral, 2),
        'racha_parada': _rachas(parada, fechas)[:3],
        'racha_rindiendo': _rachas(rindiendo, fechas)[:3],

        # El hábito: cuánto tarda la plata en volver a un certificado.
        'huecos': len(huecos),
        'dias_para_reinvertir_medio': round(sum(h['dias'] for h in huecos) / len(huecos), 1) if huecos else None,
        'peor_hueco': huecos and max(huecos, key=lambda h: h['dias']) or None,

        # Los certificados, comparados entre sí.
        'duracion_media': round(sum(duraciones) / len(duraciones)) if duraciones else None,
        'capital_medio': round(sum(float(v.get('capital') or 0.0) for v in invertidas) / len(invertidas), 2)
                          if invertidas else 0.0,
        'mejor': _resumen_certificado(max(con_tasa, key=lambda v: v.get('tna_pactada') or v.get('tna'))) if con_tasa else None,
        'peor': _resumen_certificado(min(con_tasa, key=lambda v: v.get('tna_pactada') or v.get('tna'))) if con_tasa else None,
    }


# ── Hacia dónde van las tasas, y qué pasa si siguen ─────────────────────────
#
# La tasa no es un dato del portafolio: es del banco, y le pasa lo mismo a todo el dinero
# del usuario a la vez. Por eso la tendencia se ajusta sobre **todos** los certificados del
# historial —15 puntos en vez de los 4 a 7 de un portafolio suelto— y luego se marca cuáles
# son del portafolio que se está mirando.

#: Cuántos puntos porcentuales al año hay que moverse para no llamarlo «estable».
UMBRAL_TENDENCIA = 0.25

#: Por debajo de esto la recta no explica los datos y decirlo es más honesto que dibujarla
#: como si sí. Con tasas de banco, un R² bajo significa «cambió por tramos, no en línea».
R2_MINIMO = 0.30

#: Cuánto pueden separarse los puntos de la recta, en puntos porcentuales, para seguir
#: llamando «estable» a una serie sin pendiente. Un banco que paga 5 %, 5,05 % y 4,95 %
#: está quieto; uno que paga 8 %, 2 % y 9 % no lo está, aunque la media salga plana.
DISPERSION_MAXIMA = 1.0

#: Hasta dónde se extrapola. Más allá de dos años una recta ajustada sobre dos años y
#: medio de historia deja de decir nada, y una tasa nominal no baja de cero.
ANIOS_EXTRAPOLACION = 2

HORIZONTE_PROYECCION_MESES = 60


def _regresion(puntos: List[Tuple[float, float]]) -> Optional[Dict[str, float]]:
    """Mínimos cuadrados sobre (años, tasa). Devuelve None si no hay de dónde sacar recta."""
    if len(puntos) < 3:
        return None
    n = len(puntos)
    media_x = sum(x for x, _ in puntos) / n
    media_y = sum(y for _, y in puntos) / n
    sxx = sum((x - media_x) ** 2 for x, _ in puntos)
    if sxx == 0:
        return None
    pendiente = sum((x - media_x) * (y - media_y) for x, y in puntos) / sxx
    interseccion = media_y - pendiente * media_x

    sstot = sum((y - media_y) ** 2 for _, y in puntos)
    ssres = sum((y - (interseccion + pendiente * x)) ** 2 for x, y in puntos)
    return {
        'pendiente': pendiente,
        'interseccion': interseccion,
        'r2': 1 - ssres / sstot if sstot else 1.0,
        # Cuánto se separan los puntos de la recta, en puntos porcentuales. Hace falta
        # aparte del R²: una serie plana tiene R² ~0 por no tener varianza que explicar,
        # y solo la dispersión distingue «plana y ordenada» de «plana a saltos».
        'dispersion': (ssres / n) ** 0.5,
    }


def tendencia_tasas(vistas: List[Dict[str, Any]], portafolio_id: Optional[str],
                    hoy: date) -> Dict[str, Any]:
    """Cómo se han movido las tasas y hacia dónde apuntan.

    Cada punto es un certificado el día que cerró, con la tasa que el banco liquidó de
    verdad. La recta es una regresión sobre el tiempo, y viene con su **R²** porque una
    pendiente sin bondad de ajuste es una afirmación sin respaldo: si la recta no explica
    los datos se dice «irregular» en vez de dibujar una flecha inventada.
    """
    puntos = []
    for vista in vistas:
        if vista.get('tipo') not in metricas.TIPOS_INVERTIDOS or vista.get('estado') != 'cerrada':
            continue
        cierre = _to_date(vista.get('fecha_cierre'))
        tasa = vista.get('tna_pactada') or vista.get('tna')
        if cierre is None or not tasa:
            continue
        puntos.append({
            'id': vista['id'],
            'fecha': cierre.isoformat(),
            'tasa': round(float(tasa), 4),
            'capital': round(float(vista.get('capital') or 0.0), 2),
            'portafolio_id': vista.get('portafolio_id'),
            'propio': vista.get('portafolio_id') == portafolio_id,
        })
    puntos.sort(key=lambda p: p['fecha'])

    if not puntos:
        return {'puntos': [], 'direccion': 'sin_datos', 'ajuste': None, 'proyeccion': []}

    origen = date.fromisoformat(puntos[0]['fecha'])
    def _anios(f: str) -> float:
        return (date.fromisoformat(f) - origen).days / 365.0

    ajuste = _regresion([(_anios(p['fecha']), p['tasa']) for p in puntos])
    tasa_actual = puntos[-1]['tasa']
    tasa_media = round(sum(p['tasa'] for p in puntos) / len(puntos), 4)

    direccion = 'insuficiente'
    tasa_ajustada_hoy = None
    proyeccion: List[Dict[str, Any]] = []
    if ajuste:
        pendiente = ajuste['pendiente']
        # **El orden importa.** Con tasas planas el R² es ~0 —no hay varianza que
        # explicar, justamente por ser planas—, así que mirar primero el ajuste
        # convertiría el caso más limpio de todos en «irregular». La pendiente decide si
        # hay algo que afirmar; el R² solo entra a desmentir una dirección declarada.
        if abs(pendiente) <= UMBRAL_TENDENCIA:
            # Plana. Pero plana de dos maneras distintas: quieta en el 5 %, o saltando
            # entre el 2 % y el 9 % con media plana. Solo la dispersión las separa.
            direccion = 'estable' if ajuste['dispersion'] <= DISPERSION_MAXIMA else 'irregular'
        elif ajuste['r2'] < R2_MINIMO:
            direccion = 'irregular'
        else:
            direccion = 'bajando' if pendiente < 0 else 'subiendo'

        x_hoy = _anios(hoy.isoformat())
        tasa_ajustada_hoy = round(max(0.0, ajuste['interseccion'] + pendiente * x_hoy), 4)
        # La recta, de la primera observación hasta dos años vista, en pasos de tres meses.
        paso, fin = 0, x_hoy + ANIOS_EXTRAPOLACION
        while paso / 4 <= fin:
            x = paso / 4
            proyeccion.append({
                'fecha': (origen + timedelta(days=int(x * 365))).isoformat(),
                'tasa': round(max(0.0, ajuste['interseccion'] + pendiente * x), 4),
                'futuro': x > x_hoy,
            })
            paso += 1

    return {
        'puntos': puntos,
        'propios': sum(1 for p in puntos if p['propio']),
        'direccion': direccion,
        'pendiente_anual': round(ajuste['pendiente'], 3) if ajuste else None,
        'r2': round(ajuste['r2'], 3) if ajuste else None,
        'tasa_actual': tasa_actual,
        'tasa_media': tasa_media,
        'tasa_ajustada_hoy': tasa_ajustada_hoy,
        'primera': puntos[0],
        'ultima': puntos[-1],
        'proyeccion': proyeccion,
    }


def proyectar_ganancia(base: Optional[float], tendencia: Dict[str, Any],
                       hoy: date, meses: int = HORIZONTE_PROYECCION_MESES) -> Dict[str, Any]:
    """Cuánto seguiría dando la plata, bajo tres supuestos distintos y explícitos.

    Los tres se dibujan juntos **a propósito**: la horquilla entre ellos es la respuesta
    honesta, y cualquiera de los tres por separado se leería como una promesa.

    - **A la tasa de hoy**: la del último certificado, constante. El más defendible.
    - **Si la tendencia sigue**: la tasa se mueve cada mes según la recta ajustada, con
      suelo en cero. Es el que contesta «si todo sigue así», y también el que enseña que
      seguir así no es neutral.
    - **A tu media histórica**: lo que daría si volvieran las tasas de siempre.

    Se compone mes a mes (30/360) en vez de al plazo real de cada certificado: la
    diferencia sobre cinco años es de céntimos y la curva sale legible.
    """
    if not base or base <= 0:
        return {'meses': [], 'escenarios': []}

    pendiente = tendencia.get('pendiente_anual') or 0.0
    usable = tendencia.get('direccion') in ('bajando', 'subiendo', 'estable')
    partida = tendencia.get('tasa_ajustada_hoy') if usable else tendencia.get('tasa_actual')

    # `hasta` es donde cada supuesto deja de sostenerse. Una tasa constante se puede
    # llevar cinco años porque no afirma nada nuevo cada mes; **una tendencia no**:
    # −2,7 puntos al año llega a cero en diez meses y a partir de ahí la curva sería una
    # recta plana afirmando que el banco dejó de pagar intereses para siempre. La línea
    # termina donde termina la evidencia, y que se vea corta es la información.
    definiciones = [
        ('actual', 'A la tasa de hoy', tendencia.get('tasa_actual'), 0.0, meses),
        ('media', 'A tu media histórica', tendencia.get('tasa_media'), 0.0, meses),
    ]
    if usable and partida is not None:
        definiciones.insert(
            1, ('tendencia', 'Si la tendencia sigue', partida, pendiente,
                ANIOS_EXTRAPOLACION * 12),
        )

    fechas = [(hoy + timedelta(days=30 * m)).isoformat() for m in range(meses + 1)]
    escenarios_out = []
    for clave, nombre, tasa_inicial, deriva, limite in definiciones:
        if not tasa_inicial:
            continue
        valor = base
        valores: List[Optional[float]] = [round(base, 2)]
        tasas: List[Optional[float]] = [round(tasa_inicial, 4)]
        for mes in range(1, meses + 1):
            if mes > limite:
                valores.append(None)
                tasas.append(None)
                continue
            tasa = max(0.0, tasa_inicial + deriva * (mes / 12))
            valor *= 1 + (tasa / 100) * 30 / BASE_ANIO
            valores.append(round(valor, 2))
            tasas.append(round(tasa, 4))

        vivos = [v for v in valores if v is not None]
        escenarios_out.append({
            'clave': clave,
            'nombre': nombre,
            'tasa_inicial': round(tasa_inicial, 4),
            'tasa_final': [t for t in tasas if t is not None][-1],
            'hasta_meses': min(limite, meses),
            'valores': valores,
            'tasas': tasas,
            'hitos': [
                {'anios': a, 'valor': valores[a * 12], 'ganancia': round(valores[a * 12] - base, 2)}
                for a in (1, 3, 5) if a * 12 <= min(limite, meses)
            ],
            'ganancia_al_final': round(vivos[-1] - base, 2),
        })

    return {'meses': fechas, 'base': round(base, 2), 'escenarios': escenarios_out}


def _plazo_tipico(invertidas: List[Dict[str, Any]]) -> Optional[int]:
    """La mediana de los plazos, para saber cada cuánto renovaría el escenario.

    Mediana y no media: un CDT de 303 días entre quince de un mes movería el promedio
    hasta un plazo que el usuario no usa nunca.
    """
    plazos = sorted(
        int(v['plazo_pactado_dias'] or v['plazo_inferido'])
        for v in invertidas
        if v.get('plazo_pactado_dias') or v.get('plazo_inferido')
    )
    return plazos[len(plazos) // 2] if plazos else None


# ── La respuesta completa ────────────────────────────────────────────────────

def analizar(vista: Dict[str, Any], hoy: Optional[date] = None) -> Dict[str, Any]:
    """Todo lo que la pantalla de detalle necesita de una posición."""
    hoy = hoy or date.today()

    if vista.get('tipo') not in metricas.TIPOS_INVERTIDOS:
        return {
            'posicion_id': vista.get('id'),
            'apto': False,
            'motivo': ('Esto no es una inversión sino un movimiento del portafolio '
                       f"(tipo «{vista.get('tipo')}»): no tiene plazo ni tasa, así que no hay "
                       'crecimiento que analizar.'),
            'serie': {'fechas': [], 'capital': [], 'interes': [], 'valor': []},
            'proyeccion': None,
            'escenarios': [],
        }

    elegida = tasa_para_devengo(vista)
    tasa = elegida['tasa']
    serie = curva(vista, tasa, hoy)
    proy = proyeccion(vista, tasa, hoy, serie)
    resultado_ganancia = ganancia(vista, serie, proy)

    apertura = _to_date(vista.get('fecha_apertura'))
    motivo = elegida['motivo']
    if apertura is None:
        motivo = ('Esta posición se sembró a mano y no tiene fecha de apertura, así que no '
                  'se sabe en qué días creció. Los totales sí son correctos.')

    base_escenario = resultado_ganancia['valor_al_vencimiento'] or resultado_ganancia['valor_final']
    plazo_efectivo = vista.get('plazo_pactado_dias') or vista.get('plazo_inferido')

    return {
        'posicion_id': vista.get('id'),
        'portafolio_id': vista.get('portafolio_id'),
        'tipo': vista.get('tipo'),
        'estado': vista.get('estado'),
        'fecha_apertura': vista.get('fecha_apertura'),
        'fecha_cierre': vista.get('fecha_cierre'),
        'apto': bool(serie['fechas']),
        'motivo': motivo,
        'tasa_devengo': tasa,
        'tasa_origen': elegida['origen'],
        'plazo_efectivo': plazo_efectivo,
        'serie': serie,
        'proyeccion': proy,
        'ganancia': resultado_ganancia,
        'escenarios': escenarios(base_escenario, tasa, plazo_efectivo),
        'movimientos': vista.get('movimientos', []),
        'hoy': hoy.isoformat(),
    }
