"""
Tests de `services/investments/analisis.py` — el análisis de una inversión suelta.

Lo que estas pruebas defienden, en orden de importancia:

1. **La curva aterriza en el interés real del banco.** Es lo que separa esta pantalla de
   una estimación bonita: el número final no se aproxima, se reproduce. Si alguien cambia
   la base 360 por 365 o mueve el día en que empieza a devengar, esto se cae.
2. **Sin tasa no se dibuja nada.** Una recta inventada con la tasa de otra posición sería
   indistinguible de un dato real, y el módulo entero está construido sobre lo contrario.
3. **El retiro de cierre no hunde la curva.** El caso que más fácil se rompe al refactorizar.
"""
from datetime import date, timedelta

import pytest

from contabilidad.backend.services.investments import analisis


def _tasa(capital, interes, apertura, cierre, base):
    if not (apertura and cierre and capital):
        return None
    dias = (date.fromisoformat(cierre) - date.fromisoformat(apertura)).days
    return round(interes / capital * base / dias * 100, 4) if dias else None


def _plazo_fijo(capital=27000.0, interes=69.60, apertura='2026-06-25', cierre='2026-07-27',
                retencion=0.0, **extra):
    """Una posición cerrada como las que arma `posiciones.armar_vista`."""
    movimientos = [{'fecha': apertura, 'tipo': 'aporte', 'monto': capital}]
    if cierre:
        movimientos += [
            {'fecha': cierre, 'tipo': 'interes', 'monto': interes},
            {'fecha': cierre, 'tipo': 'retiro', 'monto': capital},
        ]
        if retencion:
            movimientos.append({'fecha': cierre, 'tipo': 'retencion', 'monto': retencion})
    vista = {
        'id': 'pos-1',
        'portafolio_id': 'p1',
        'tipo': 'plazo_fijo',
        'estado': 'cerrada' if cierre else 'abierta',
        'fecha_apertura': apertura,
        'fecha_cierre': cierre,
        'capital': capital,
        'capital_vigente': 0.0 if cierre else capital,
        'interes': interes if cierre else 0.0,
        'retencion': retencion,
        'comisiones': 0.0,
        'dias': (date.fromisoformat(cierre) - date.fromisoformat(apertura)).days if cierre and apertura else None,
        # `armar_vista` las calcula; las estadísticas comparan certificados por tasa y sin
        # esto el fixture no tendría ninguna que comparar.
        'tna': _tasa(capital, interes, apertura, cierre, 365),
        'tna_pactada': _tasa(capital, interes, apertura, cierre, 360),
        'plazo_pactado_dias': None,
        # `armar_vista` lo deduce de las fechas cuando la posición está cerrada, y el
        # escenario de reinversión lo usa como periodo de renovación. Sin esto el fixture
        # compondría una vez al año y no probaría lo que pasa de verdad.
        'plazo_inferido': (date.fromisoformat(cierre) - date.fromisoformat(apertura)).days
                          if cierre and apertura else None,
        'tasa_pactada': None,
        'movimientos': movimientos,
    }
    vista.update(extra)
    return vista


# ── 1. La curva reproduce el interés real ────────────────────────────────────

@pytest.mark.parametrize('capital,interes,apertura,cierre', [
    (26000.00, 1897.57, '2024-03-28', '2025-01-24'),   # el más largo, 303 días
    (10278.00, 208.82, '2024-06-04', '2024-09-04'),
    (6648.00, 27.48, '2024-09-23', '2024-10-24'),
    (28000.00, 139.84, '2025-02-21', '2025-03-24'),
    (4214.00, 67.28, '2025-11-18', '2026-03-19'),
    (27000.00, 69.60, '2026-06-25', '2026-07-27'),
])
def test_la_curva_termina_en_el_interes_que_pago_el_banco(capital, interes, apertura, cierre):
    """Casos reales del historial. El último punto tiene que ser el interés del extracto.

    No es una tolerancia generosa: al centavo. La tasa se despeja de ese mismo interés,
    así que cualquier desvío significa que el devengo no es el inverso del despeje.
    """
    vista = _plazo_fijo(capital, interes, apertura, cierre)
    resultado = analisis.analizar(vista, hoy=date(2026, 8, 13))

    assert resultado['apto']
    assert resultado['tasa_origen'] == 'liquidada'
    assert resultado['serie']['interes'][-1] == pytest.approx(interes, abs=0.01)
    assert resultado['serie']['valor'][-1] == pytest.approx(capital + interes, abs=0.01)


def test_la_tasa_despejada_cae_en_el_peldano_del_banco():
    """27.000 al 2,90 % por 32 días son 69,60. El despeje tiene que devolver ese 2,90."""
    resultado = analisis.analizar(_plazo_fijo(), hoy=date(2026, 8, 13))
    assert resultado['tasa_devengo'] == pytest.approx(2.90, abs=0.005)


def test_el_primer_dia_no_devenga():
    """La plata entra el día de apertura y empieza a contar al siguiente.

    Es la convención con la que se dedujo la tasa (§2.9 del handoff): 32 días de devengo
    entre el 25-06 y el 27-07, no 33. Si el devengo arrancara el día 0, la curva pasaría
    de largo el interés real por un día entero de intereses.
    """
    resultado = analisis.analizar(_plazo_fijo(), hoy=date(2026, 8, 13))
    assert resultado['serie']['interes'][0] == 0.0
    assert resultado['serie']['valor'][0] == 27000.0


def test_la_curva_crece_todos_los_dias_en_vez_de_saltar_al_final():
    """El punto de la pantalla: la línea sube a diario, no es plana con un escalón."""
    serie = analisis.analizar(_plazo_fijo(), hoy=date(2026, 8, 13))['serie']
    assert all(b >= a for a, b in zip(serie['valor'], serie['valor'][1:]))
    a_mitad = serie['valor'][len(serie['valor']) // 2]
    assert 27000.0 < a_mitad < 27069.60


# ── 2. Sin tasa no se inventa una curva ──────────────────────────────────────

def test_una_abierta_sin_tasa_pactada_no_dibuja_curva():
    vista = _plazo_fijo(cierre=None)
    vista['estado'] = 'abierta'
    resultado = analisis.analizar(vista, hoy=date(2026, 8, 13))

    assert resultado['tasa_devengo'] is None
    assert 'tasa pactada' in resultado['motivo']
    # La serie existe (el capital sí se sabe) pero no crece: no se inventa interés.
    assert set(resultado['serie']['interes']) == {0.0}


def test_una_abierta_con_tasa_pactada_devenga_y_proyecta():
    vista = _plazo_fijo(cierre=None)
    vista.update({'estado': 'abierta', 'tasa_pactada': 3.60, 'plazo_pactado_dias': 90,
                  'capital_vigente': 27000.0})
    resultado = analisis.analizar(vista, hoy=date(2026, 7, 25))

    assert resultado['tasa_origen'] == 'pactada'
    proy = resultado['proyeccion']
    assert proy is not None
    assert proy['fecha_vencimiento'] == '2026-09-23'   # 25-06 + 90 días
    assert proy['dias_restantes'] == 60
    # 27.000 al 3,60 % base 360 son 2,70 al día: 90 días son 243.
    assert proy['interes_al_vencimiento'] == pytest.approx(243.0, abs=0.05)
    assert proy['valor_al_vencimiento'] == pytest.approx(27243.0, abs=0.05)
    assert proy['falta_por_devengar'] == pytest.approx(2.70 * 60, abs=0.05)


def test_la_proyeccion_arranca_donde_termina_lo_real():
    """Las dos series se tocan; si no, el gráfico enseña un salto que no existió."""
    vista = _plazo_fijo(cierre=None)
    vista.update({'estado': 'abierta', 'tasa_pactada': 3.60, 'plazo_pactado_dias': 90})
    resultado = analisis.analizar(vista, hoy=date(2026, 7, 25))

    assert resultado['serie']['fechas'][-1] == resultado['proyeccion']['fechas'][0]
    assert resultado['serie']['valor'][-1] == resultado['proyeccion']['valor'][0]


def test_una_cerrada_no_proyecta():
    assert analisis.analizar(_plazo_fijo(), hoy=date(2026, 8, 13))['proyeccion'] is None


def test_una_siembra_sin_apertura_no_tiene_curva_pero_si_totales():
    """Las 2 posiciones sembradas a mano: se sabe cuánto dieron, no en qué días."""
    vista = _plazo_fijo(10100.0, 172.21, apertura=None, cierre='2024-05-29')
    resultado = analisis.analizar(vista, hoy=date(2026, 8, 13))

    assert not resultado['apto']
    assert 'fecha de apertura' in resultado['motivo']
    assert resultado['ganancia']['interes_bruto'] == 172.21


def test_un_flujo_no_es_una_inversion():
    """Una matrícula pagada no tiene plazo ni tasa: no hay nada que analizar."""
    vista = _plazo_fijo(3213.74, 0.0, '2025-04-28', '2025-04-28')
    vista['tipo'] = 'flujo'
    resultado = analisis.analizar(vista, hoy=date(2026, 8, 13))

    assert not resultado['apto']
    assert 'no es una inversión' in resultado['motivo']
    assert resultado['escenarios'] == []


# ── 3. El retiro de cierre no hunde la curva ─────────────────────────────────

def test_el_retiro_del_cierre_no_baja_el_capital():
    """El retiro de cierre *es* el pago de lo que la posición valía.

    Descontarlo dejaría la curva en cero justo el día que se cobra, que es lo contrario de
    lo que pasó: ese día la posición valía capital + interés.
    """
    serie = analisis.analizar(_plazo_fijo(), hoy=date(2026, 8, 13))['serie']
    assert serie['capital'][-1] == 27000.0
    assert serie['valor'][-1] == pytest.approx(27069.60, abs=0.01)


def test_un_retiro_parcial_a_mitad_de_vida_si_baja_el_capital():
    """Y desde ese día deja de rendir: es plata que salió, no el cobro final."""
    vista = _plazo_fijo(cierre=None)
    vista.update({'estado': 'abierta', 'tasa_pactada': 3.60})
    vista['movimientos'].append({'fecha': '2026-07-05', 'tipo': 'retiro', 'monto': 7000.0})

    resultado = analisis.analizar(vista, hoy=date(2026, 7, 25))
    serie = resultado['serie']
    i_05 = serie['fechas'].index('2026-07-05')

    assert serie['capital'][i_05 - 1] == 27000.0
    assert serie['capital'][i_05] == 20000.0
    # 27.000 rinden 2,70/día y 20.000 rinden 2,00: el tramo de después crece menos.
    antes = serie['interes'][i_05 - 1] - serie['interes'][i_05 - 2]
    despues = serie['interes'][i_05 + 1] - serie['interes'][i_05]
    assert antes == pytest.approx(2.70, abs=0.01)
    assert despues == pytest.approx(2.00, abs=0.01)


# ── Ganancia y escenarios ────────────────────────────────────────────────────

def test_la_ganancia_neta_descuenta_la_retencion():
    resultado = analisis.analizar(_plazo_fijo(retencion=2.09), hoy=date(2026, 8, 13))
    ganancia = resultado['ganancia']

    assert ganancia['realizado'] is True
    assert ganancia['interes_bruto'] == 69.60
    assert ganancia['retencion'] == 2.09
    assert ganancia['interes_neto'] == pytest.approx(67.51, abs=0.01)
    assert ganancia['rendimiento_pct'] == pytest.approx(67.51 / 27000 * 100, abs=0.0001)


def test_la_ganancia_de_una_abierta_es_devengada_no_cobrada():
    vista = _plazo_fijo(cierre=None)
    vista.update({'estado': 'abierta', 'tasa_pactada': 3.60})
    ganancia = analisis.analizar(vista, hoy=date(2026, 7, 25))['ganancia']

    assert ganancia['realizado'] is False
    assert ganancia['interes_bruto'] == pytest.approx(2.70 * 30, abs=0.05)


def test_el_escenario_compone_al_mismo_plazo_y_tasa():
    """32 días al 2,90 % renovados un año: (1 + 0,029·32/360)^(360/32) sobre el valor final."""
    resultado = analisis.analizar(_plazo_fijo(), hoy=date(2026, 8, 13))
    uno = next(e for e in resultado['escenarios'] if e['anios'] == 1)

    base = 27069.60
    esperado = base * (1 + 0.029 * 32 / 360) ** (360 / 32)
    assert uno['valor'] == pytest.approx(esperado, abs=1.0)
    assert uno['ganancia'] == pytest.approx(uno['valor'] - base, abs=0.01)


def test_el_escenario_crece_con_el_horizonte():
    escenarios = analisis.analizar(_plazo_fijo(), hoy=date(2026, 8, 13))['escenarios']
    valores = [e['valor'] for e in escenarios]
    assert valores == sorted(valores)
    assert [e['anios'] for e in escenarios] == [1, 2, 3, 5, 10]


def test_sin_tasa_no_hay_escenario():
    """Componer una tasa que no se conoce sería inventarse el número dos veces."""
    assert analisis.escenarios(10000.0, None, 90) == []
    assert analisis.escenarios(10000.0, 0.0, 90) == []
    assert analisis.escenarios(None, 3.6, 90) == []


def test_sin_plazo_el_escenario_compone_una_vez_al_ano():
    filas = analisis.escenarios(1000.0, 10.0, None)
    uno = next(f for f in filas if f['anios'] == 1)
    # Base 360 sobre 360 días: exactamente un 10 %.
    assert uno['valor'] == pytest.approx(1100.0, abs=0.01)
    assert uno['renovaciones'] == 1.0


# ── El portafolio entero ─────────────────────────────────────────────────────
#
# La unidad que el usuario llama «una inversión»: el mismo dinero rodando de certificado
# en certificado. Lo que más se defiende aquí es la identidad
# `total = aportado_neto + ganancia`, porque es lo que impide que un movimiento se cuente
# dos veces sin que nadie se entere.

PORTAFOLIO = {'id': 'uni', 'name': 'Inversiones_Uni', 'es_custodia': True,
              'saldo_inicial': 1000.0, 'saldo_inicial_configurado': True}


def _flujo(monto, fecha, salida=True):
    """Plata que sale del portafolio (matrícula) o que entra de fuera."""
    tipo = 'aporte' if salida else 'retiro'
    return {
        'id': f'flujo-{fecha}', 'portafolio_id': 'uni', 'tipo': 'flujo', 'estado': 'cerrada',
        'fecha_apertura': fecha, 'fecha_cierre': fecha,
        'capital': monto if salida else 0.0, 'retirado': 0.0 if salida else monto,
        'interes': 0.0, 'retencion': 0.0, 'comisiones': 0.0, 'dias': 0,
        'plazo_pactado_dias': None, 'plazo_inferido': None, 'tasa_pactada': None,
        'movimientos': [{'fecha': fecha, 'tipo': tipo, 'monto': monto}],
    }


def _del_portafolio(vista, portafolio_id='uni'):
    return {**vista, 'portafolio_id': portafolio_id}


def test_la_identidad_del_portafolio_se_cumple_todos_los_dias():
    """`total = aportado_neto + ganancia`, día a día y no solo al final.

    Es la comprobación que hace confiable el número grande de la pantalla: si un
    movimiento se contara dos veces (por ejemplo un flujo entrando también como capital
    invertido), las dos mitades dejarían de sumar el total en el día exacto del fallo.
    """
    vistas = [
        _del_portafolio(_plazo_fijo(1000.0, 10.0, '2025-01-10', '2025-02-10')),
        _flujo(300.0, '2025-03-01'),
        _flujo(50.0, '2025-03-15', salida=False),
    ]
    resultado = analisis.analizar_portafolio(vistas, PORTAFOLIO, hoy=date(2025, 4, 1))
    serie = resultado['serie']

    for fecha, total, aportado, ganancia in zip(
        serie['fechas'], serie['total'], serie['aportado_neto'], serie['ganancia'],
    ):
        assert aportado + ganancia == pytest.approx(total, abs=0.02), f'no cuadra el {fecha}'


def test_las_tres_capas_del_grafico_suman_el_total():
    """Se dibujan apiladas: si no suman, el gráfico miente sobre cuánto hay."""
    vistas = [_del_portafolio(_plazo_fijo(1000.0, 10.0, '2025-01-10', '2025-02-10'))]
    serie = analisis.analizar_portafolio(vistas, PORTAFOLIO, hoy=date(2025, 3, 1))['serie']

    for dentro, suelto, devengado, total in zip(
        serie['dentro'], serie['suelto'], serie['devengado'], serie['total'],
    ):
        assert dentro + suelto + devengado == pytest.approx(total, abs=0.02)


def test_abrir_un_certificado_no_cambia_el_total_solo_dónde_está():
    """Meter plata en un CDT la mueve de «suelta» a «rindiendo», no la crea ni la destruye.

    Es el invariante que más fácil se rompe: basta con que el residual y el capital usen
    definiciones distintas del mismo movimiento.
    """
    # La entrada del 01-01 existe para que la ventana empiece antes de que se abra el
    # certificado: sin ella el día de la apertura es el primero de la serie y no hay un
    # «antes» contra el que comparar.
    vistas = [
        _flujo(500.0, '2025-01-01', salida=False),
        _del_portafolio(_plazo_fijo(1000.0, 10.0, '2025-01-10', '2025-02-10')),
    ]
    serie = analisis.analizar_portafolio(vistas, PORTAFOLIO, hoy=date(2025, 3, 1))['serie']
    i = serie['fechas'].index('2025-01-10')

    assert serie['suelto'][i - 1] == 1500.0 and serie['dentro'][i - 1] == 0.0
    assert serie['suelto'][i] == 500.0 and serie['dentro'][i] == 1000.0
    assert serie['total'][i - 1] == serie['total'][i] == 1500.0


def test_al_cerrar_el_certificado_el_interes_entra_al_portafolio():
    vistas = [_del_portafolio(_plazo_fijo(1000.0, 10.0, '2025-01-10', '2025-02-10'))]
    resultado = analisis.analizar_portafolio(vistas, PORTAFOLIO, hoy=date(2025, 3, 1))

    assert resultado['kpis']['total_hoy'] == pytest.approx(1010.0, abs=0.01)
    assert resultado['kpis']['ganancia_acumulada'] == pytest.approx(10.0, abs=0.01)
    assert resultado['kpis']['aportado_neto'] == pytest.approx(1000.0, abs=0.01)


def test_una_salida_baja_el_total_y_no_la_ganancia():
    """Pagar la matrícula vacía el bolsillo pero no borra lo que se ganó."""
    vistas = [
        _del_portafolio(_plazo_fijo(1000.0, 10.0, '2025-01-10', '2025-02-10')),
        _flujo(600.0, '2025-02-20'),
    ]
    kpis = analisis.analizar_portafolio(vistas, PORTAFOLIO, hoy=date(2025, 3, 1))['kpis']

    assert kpis['total_hoy'] == pytest.approx(410.0, abs=0.01)
    assert kpis['ganancia_acumulada'] == pytest.approx(10.0, abs=0.01)
    assert kpis['salidas'] == 600.0


def test_lo_que_ya_estaba_dentro_cuenta_como_puesto_y_no_como_ganancia():
    """Una posición sembrada sin apertura ya estaba en un certificado antes de la ventana.

    Su aporte no pasa por el residual (`_eventos_por_portafolio` lo salta a propósito),
    así que si no se sumara al aportado, la identidad lo declararía ganancia — plata
    regalada que nunca existió.
    """
    siembra = _del_portafolio(_plazo_fijo(5000.0, 100.0, apertura=None, cierre='2025-02-10'))
    siembra['movimientos'] = [
        {'fecha': '2025-01-01', 'tipo': 'aporte', 'monto': 5000.0},   # fecha estimada
        {'fecha': '2025-02-10', 'tipo': 'interes', 'monto': 100.0},
        {'fecha': '2025-02-10', 'tipo': 'retiro', 'monto': 5000.0},
    ]
    resultado = analisis.analizar_portafolio([siembra], PORTAFOLIO, hoy=date(2025, 3, 1))
    kpis = resultado['kpis']

    assert kpis['aportado_neto'] == pytest.approx(6000.0, abs=0.01)   # 1.000 saldo + 5.000 dentro
    assert kpis['ganancia_acumulada'] == pytest.approx(100.0, abs=0.01)
    assert kpis['total_hoy'] == pytest.approx(6100.0, abs=0.01)


def test_los_dias_con_plata_parada_solo_cuentan_lo_que_esta_fuera():
    """La cifra que ninguna otra pantalla enseña: cuánto tiempo la plata no rindió."""
    vistas = [_del_portafolio(_plazo_fijo(1000.0, 10.0, '2025-01-10', '2025-02-10'))]
    kpis = analisis.analizar_portafolio(vistas, PORTAFOLIO, hoy=date(2025, 3, 1))['kpis']

    # Del 10-01 al 10-02 la plata está dentro; el resto de la ventana está suelta.
    assert kpis['dias_con_plata_parada'] == kpis['dias'] - 31


def test_un_portafolio_vacio_no_proyecta():
    """Componer 1,33 durante diez años da una tabla con pinta de cálculo y sin contenido."""
    vistas = [
        _del_portafolio(_plazo_fijo(1000.0, 10.0, '2025-01-10', '2025-02-10')),
        # Se lleva todo lo que devolvió el certificado: capital puesto más el interés.
        _flujo(1010.0, '2025-02-11'),
    ]
    resultado = analisis.analizar_portafolio(vistas, PORTAFOLIO, hoy=date(2025, 3, 1))

    assert resultado['kpis']['total_hoy'] == pytest.approx(0.0, abs=0.01)
    assert resultado['escenarios'] == []


def test_un_portafolio_sin_posiciones_lo_dice_en_vez_de_romperse():
    resultado = analisis.analizar_portafolio([], PORTAFOLIO, hoy=date(2025, 3, 1))
    assert not resultado['apto']
    assert 'ninguna posición' in resultado['motivo']
    assert resultado['serie']['fechas'] == []


def test_solo_entran_las_posiciones_del_portafolio():
    """Un certificado de otro portafolio no puede aparecer en este total."""
    vistas = [
        _del_portafolio(_plazo_fijo(1000.0, 10.0, '2025-01-10', '2025-02-10')),
        _del_portafolio(_plazo_fijo(9000.0, 90.0, '2025-01-10', '2025-02-10'), 'otro'),
    ]
    resultado = analisis.analizar_portafolio(vistas, PORTAFOLIO, hoy=date(2025, 3, 1))

    assert resultado['kpis']['total_hoy'] == pytest.approx(1010.0, abs=0.01)
    assert [p['capital'] for p in resultado['posiciones']] == [1000.0]


# ── Estadísticas derivadas ───────────────────────────────────────────────────

def _analisis_con_hueco():
    """Un portafolio con un certificado, un hueco de 18 días y otro certificado.

    1.000 de saldo, dentro del 10-01 al 10-02 y del 28-02 al 31-03. Entre medias la plata
    está quieta: es el caso que las estadísticas existen para medir.
    """
    vistas = [
        _del_portafolio(_plazo_fijo(1000.0, 10.0, '2025-01-10', '2025-02-10')),
        _del_portafolio(_plazo_fijo(1010.0, 20.0, '2025-02-28', '2025-03-31')),
    ]
    return analisis.analizar_portafolio(vistas, PORTAFOLIO, hoy=date(2025, 3, 31))


def test_los_tres_estados_parten_la_ventana_sin_solaparse():
    """Suman siempre el total de días: es lo que deja enseñarlos como porcentajes."""
    e = _analisis_con_hueco()['estadisticas']
    assert e['dias_rindiendo'] + e['dias_parada'] + e['dias_vacio'] == e['dias_totales']
    assert e['pct_rindiendo'] + e['pct_parada'] <= 100.0


def test_cuenta_los_dias_rindiendo_y_los_dias_parada():
    """**El día del cierre la plata ya está suelta**, y por eso cuenta como parada.

    Es la convención que hace que las tres cuentas partan la ventana: ese día el retiro y
    el interés entran al residual, así que `dentro` vale 0. Cada certificado aporta 31
    días rindiendo (10-01→09-02 y 28-02→30-03), no 32.
    """
    e = _analisis_con_hueco()['estadisticas']
    assert e['dias_rindiendo'] == 62
    # Del 10-02 (el día que se cobra) al 27-02 son 18, más el 31-03, que es el día en que
    # cierra el segundo certificado y también termina la ventana.
    assert e['dias_parada'] == 19
    assert e['dias_vacio'] == 0


def test_el_ritmo_por_dia_trabajado_es_mayor_que_el_del_calendario():
    """Es el punto de tener las dos cifras: la segunda diluye con los días parados."""
    e = _analisis_con_hueco()['estadisticas']
    assert e['ganancia_por_dia_rindiendo'] > e['ganancia_por_dia']
    assert e['ganancia'] == pytest.approx(30.0, abs=0.01)


def test_mide_cuanto_tarda_en_reinvertir():
    e = _analisis_con_hueco()['estadisticas']
    assert e['huecos'] == 1
    assert e['dias_para_reinvertir_medio'] == pytest.approx(18.0, abs=0.1)
    assert e['peor_hueco']['dias'] == 18


def test_la_racha_parada_lleva_sus_fechas():
    """Sin las fechas el número no sirve: hay que poder ir a mirar qué pasó ahí."""
    e = _analisis_con_hueco()['estadisticas']
    peor = e['racha_parada'][0]
    assert peor['dias'] == 18
    assert peor['desde'] == '2025-02-10'
    assert peor['hasta'] == '2025-02-27'


def test_el_lucro_cesante_usa_la_tasa_del_propio_portafolio():
    """«Lo que esa plata habría dado en tus certificados», no en una tasa inventada."""
    resultado = _analisis_con_hueco()
    e, tna = resultado['estadisticas'], resultado['kpis']['tna_ponderada']

    # 18 días con 1.010 sueltos entre los dos certificados, y el 31-03 con los 1.030 que
    # devolvió el segundo. Cada día cuenta con el saldo que de verdad había ese día.
    esperado = (1010.0 * 18 + 1030.0 * 1) * (tna / 100) / 360
    assert e['lucro_cesante'] == pytest.approx(esperado, abs=0.05)


def test_sin_tasa_conocida_no_se_estima_el_lucro_cesante():
    """Devolver None es la respuesta correcta; un cero diría que no costó nada."""
    vistas = [_del_portafolio(_plazo_fijo(1000.0, 0.0, '2025-01-10', '2025-02-10'))]
    e = analisis.analizar_portafolio(vistas, PORTAFOLIO, hoy=date(2025, 3, 1))['estadisticas']
    assert e['lucro_cesante'] is None


def test_un_residuo_de_redondeo_no_es_plata_parada():
    """`Uni` termina con 1,33 sueltos tras la matrícula.

    Con un umbral fijo de un dólar la pantalla anunciaba «148 días con la plata parada»
    por dólar y medio. El umbral es relativo a lo que el portafolio mueve.
    """
    vistas = [
        _del_portafolio(_plazo_fijo(1000.0, 100.0, '2025-01-10', '2025-02-10')),
        _flujo(1098.67, '2025-02-11'),   # se lleva casi todo y deja 1,33
    ]
    resultado = analisis.analizar_portafolio(vistas, PORTAFOLIO, hoy=date(2025, 6, 1))
    e = resultado['estadisticas']

    assert e['umbral_material'] == pytest.approx(10.0, abs=0.01)   # 1 % de 1.000
    assert resultado['kpis']['total_hoy'] == pytest.approx(1.33, abs=0.01)
    # Solo el 10-02, el día que el certificado devuelve los 1.100 antes de que salgan.
    # Los ~110 días siguientes con 1,33 en la cuenta NO son «plata parada».
    assert e['dias_parada'] == 1
    assert e['dias_vacio'] > 100


def test_el_mejor_y_el_peor_certificado():
    e = _analisis_con_hueco()['estadisticas']
    assert e['mejor']['tna'] >= e['peor']['tna']
    assert e['mejor']['fecha_cierre'] == '2025-03-31'   # 20 sobre 1.010 en 31 días


def test_las_estadisticas_de_un_portafolio_sin_serie_no_revientan():
    assert analisis.estadisticas({'fechas': [], 'dentro': [], 'suelto': [], 'ganancia': []},
                                 [], 5.0) == {}


def test_las_rachas_cierran_el_ultimo_tramo_abierto():
    """Un tramo que llega hasta el último día no se puede quedar sin cerrar."""
    tramos = analisis._rachas([False, True, True], ['2025-01-01', '2025-01-02', '2025-01-03'])
    assert tramos == [{'desde': '2025-01-02', 'hasta': '2025-01-03', 'dias': 2}]


# ── Tendencia de las tasas y proyección ──────────────────────────────────────

def _cert_con_tasa(tasa, cierre, capital=10000.0, portafolio='uni'):
    """Un certificado cerrado de 360 días cuya TNA liquidada es exactamente `tasa`."""
    apertura = (date.fromisoformat(cierre) - timedelta(days=360)).isoformat()
    interes = capital * tasa / 100
    vista = _del_portafolio(_plazo_fijo(capital, interes, apertura, cierre), portafolio)
    return vista


def test_detecta_que_las_tasas_bajan():
    vistas = [_cert_con_tasa(t, f) for t, f in [
        (8.0, '2024-01-31'), (7.0, '2024-07-31'), (6.0, '2025-01-31'),
        (4.0, '2025-07-31'), (3.0, '2026-01-31'),
    ]]
    t = analisis.tendencia_tasas(vistas, 'uni', date(2026, 6, 1))

    assert t['direccion'] == 'bajando'
    assert t['pendiente_anual'] < -2
    assert t['r2'] > 0.9
    assert t['primera']['tasa'] == pytest.approx(8.0, abs=0.01)
    assert t['ultima']['tasa'] == pytest.approx(3.0, abs=0.01)


def test_detecta_que_las_tasas_suben():
    vistas = [_cert_con_tasa(t, f) for t, f in [
        (2.0, '2024-01-31'), (3.0, '2024-07-31'), (4.5, '2025-01-31'), (6.0, '2025-07-31'),
    ]]
    assert analisis.tendencia_tasas(vistas, 'uni', date(2026, 6, 1))['direccion'] == 'subiendo'


def test_tasas_planas_son_estables_y_no_una_tendencia():
    vistas = [_cert_con_tasa(t, f) for t, f in [
        (5.0, '2024-01-31'), (5.05, '2024-07-31'), (4.95, '2025-01-31'), (5.0, '2025-07-31'),
    ]]
    assert analisis.tendencia_tasas(vistas, 'uni', date(2026, 6, 1))['direccion'] == 'estable'


def test_plana_a_saltos_no_es_estable():
    """Plana de dos maneras distintas, y solo la dispersión las separa.

    Estas tasas (8, 2, 9, 3, 7) tienen pendiente media casi nula, así que mirar solo la
    pendiente las declararía «estables» — y un banco que paga entre el 2 % y el 9 % no
    está quieto. El R² tampoco sirve aquí: en una serie sin tendencia vale ~0 tanto si
    está quieta como si salta.
    """
    vistas = [_cert_con_tasa(t, f) for t, f in [
        (8.0, '2024-01-31'), (2.0, '2024-07-31'), (9.0, '2025-01-31'),
        (3.0, '2025-07-31'), (7.0, '2026-01-31'),
    ]]
    t = analisis.tendencia_tasas(vistas, 'uni', date(2026, 6, 1))

    assert abs(t['pendiente_anual']) <= analisis.UMBRAL_TENDENCIA
    assert t['direccion'] == 'irregular'


def test_sin_bondad_de_ajuste_se_dice_irregular_en_vez_de_bajando():
    """Una pendiente sin R² es una flecha dibujada a mano.

    Estas tasas saltan sin patrón; la recta que las ajusta tiene pendiente pero no explica
    nada, y afirmar «van a la baja» sobre eso sería inventarse una lectura.
    """
    vistas = [_cert_con_tasa(t, f) for t, f in [
        (8.0, '2024-01-31'), (2.0, '2024-07-31'), (9.0, '2025-01-31'),
        (3.0, '2025-07-31'), (7.0, '2026-01-31'),
    ]]
    t = analisis.tendencia_tasas(vistas, 'uni', date(2026, 6, 1))

    assert t['r2'] < 0.30
    assert t['direccion'] == 'irregular'


def test_con_menos_de_tres_certificados_no_se_habla_de_tendencia():
    vistas = [_cert_con_tasa(8.0, '2024-01-31'), _cert_con_tasa(3.0, '2025-01-31')]
    t = analisis.tendencia_tasas(vistas, 'uni', date(2026, 6, 1))

    assert t['direccion'] == 'insuficiente'
    assert t['pendiente_anual'] is None
    assert t['proyeccion'] == []
    assert len(t['puntos']) == 2   # los puntos sí se enseñan; la recta no


def test_la_tendencia_mira_todos_los_portafolios_pero_marca_los_propios():
    """La tasa la pone el banco: mezclar portafolios da más puntos y ninguna distorsión."""
    vistas = [
        _cert_con_tasa(8.0, '2024-01-31', portafolio='uni'),
        _cert_con_tasa(6.0, '2024-07-31', portafolio='otro'),
        _cert_con_tasa(4.0, '2025-01-31', portafolio='otro'),
    ]
    t = analisis.tendencia_tasas(vistas, 'uni', date(2026, 6, 1))

    assert len(t['puntos']) == 3
    assert t['propios'] == 1
    assert [p['propio'] for p in t['puntos']] == [True, False, False]


def test_la_extrapolacion_no_baja_de_cero():
    """Una tasa nominal no es negativa: el banco no cobra por guardarte la plata."""
    vistas = [_cert_con_tasa(t, f) for t, f in [
        (8.0, '2024-01-31'), (5.0, '2024-07-31'), (2.0, '2025-01-31'),
    ]]
    t = analisis.tendencia_tasas(vistas, 'uni', date(2026, 6, 1))
    assert all(p['tasa'] >= 0 for p in t['proyeccion'])


def test_la_proyeccion_por_tendencia_se_corta_donde_acaba_la_evidencia():
    """El fallo que hacía absurdo el escenario: la recta llega a cero y sigue plana.

    Con −2,7 puntos al año la tasa se agota en meses, y prolongar la curva cinco años
    afirmaría que el banco dejó de pagar intereses para siempre. La línea termina a los
    dos años, y que se vea corta es la información.
    """
    vistas = [_cert_con_tasa(t, f) for t, f in [
        (8.0, '2024-01-31'), (6.0, '2024-07-31'), (4.0, '2025-01-31'), (2.0, '2025-07-31'),
    ]]
    tendencia = analisis.tendencia_tasas(vistas, 'uni', date(2026, 1, 1))
    proyeccion = analisis.proyectar_ganancia(10000.0, tendencia, date(2026, 1, 1))

    por_clave = {e['clave']: e for e in proyeccion['escenarios']}
    assert por_clave['tendencia']['hasta_meses'] == 24
    assert por_clave['tendencia']['valores'][24] is not None
    assert por_clave['tendencia']['valores'][25] is None
    assert [h['anios'] for h in por_clave['tendencia']['hitos']] == [1]

    # Los supuestos de tasa constante sí llegan a los cinco años: no afirman nada nuevo
    # cada mes que pasa.
    assert por_clave['actual']['hasta_meses'] == 60
    assert [h['anios'] for h in por_clave['actual']['hitos']] == [1, 3, 5]


def test_los_tres_supuestos_se_ordenan_como_sus_tasas():
    """Con tasas a la baja: la media histórica da más que la de hoy, y la tendencia menos."""
    vistas = [_cert_con_tasa(t, f) for t, f in [
        (8.0, '2024-01-31'), (6.0, '2024-07-31'), (4.0, '2025-01-31'), (2.0, '2025-07-31'),
    ]]
    tendencia = analisis.tendencia_tasas(vistas, 'uni', date(2026, 1, 1))
    proyeccion = analisis.proyectar_ganancia(10000.0, tendencia, date(2026, 1, 1))
    por_clave = {e['clave']: e for e in proyeccion['escenarios']}

    a_un_anio = {k: e['hitos'][0]['valor'] for k, e in por_clave.items()}
    assert a_un_anio['media'] > a_un_anio['actual'] > a_un_anio['tendencia']


def test_sin_plata_no_se_proyecta_nada():
    tendencia = analisis.tendencia_tasas(
        [_cert_con_tasa(5.0, '2025-01-31')], 'uni', date(2026, 1, 1))
    assert analisis.proyectar_ganancia(0.0, tendencia, date(2026, 1, 1))['escenarios'] == []
    assert analisis.proyectar_ganancia(None, tendencia, date(2026, 1, 1))['escenarios'] == []


def test_la_proyeccion_arranca_en_lo_que_hay_hoy():
    tendencia = analisis.tendencia_tasas(
        [_cert_con_tasa(t, f) for t, f in [(5.0, '2024-01-31'), (5.0, '2025-01-31')]],
        'uni', date(2026, 1, 1))
    proyeccion = analisis.proyectar_ganancia(28445.42, tendencia, date(2026, 1, 1))

    assert proyeccion['base'] == 28445.42
    for escenario in proyeccion['escenarios']:
        assert escenario['valores'][0] == 28445.42


def test_el_analisis_del_portafolio_trae_tendencia_y_proyeccion():
    vistas = [
        _del_portafolio(_plazo_fijo(1000.0, 10.0, '2025-01-10', '2025-02-10')),
        _del_portafolio(_plazo_fijo(1010.0, 20.0, '2025-02-28', '2025-03-31')),
    ]
    resultado = analisis.analizar_portafolio(vistas, PORTAFOLIO, hoy=date(2025, 3, 31))

    assert resultado['tasas']['puntos']
    assert 'escenarios' in resultado['proyeccion_ganancia']


def test_el_plazo_del_escenario_es_la_mediana_y_no_la_media():
    """Un CDT de 303 días entre quince de un mes no debe fijar el ritmo de renovación."""
    invertidas = [{'plazo_inferido': p, 'plazo_pactado_dias': None} for p in (31, 32, 303, 30, 32)]
    assert analisis._plazo_tipico(invertidas) == 32
    assert analisis._plazo_tipico([]) is None
