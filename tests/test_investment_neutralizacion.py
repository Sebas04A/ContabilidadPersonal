"""
test_investment_neutralizacion.py — Los pagos fijos derivados de las posiciones.

Cubre `services/investments/neutralizacion.py`, que es solo lectura: genera el escalón
residual de cada portafolio, lo evalúa con la misma ventana que el dashboard y lo compara
contra los pagos escritos a mano. Ningún test escribe en `pagos.csv`.

Casi todo es puro sobre listas de diccionarios y no toca disco. Lo único que lee un CSV es
`pagos_actuales()` (y por lo tanto `preview()`), y esos tests van contra `tmp_path`.
"""
from datetime import date

import pytest
from unittest.mock import patch

from contabilidad.backend.services.investments import neutralizacion as neu


P1 = "p1"
P2 = "p2"


def portafolio(id=P1, name="Inversiones_Mias", saldo_inicial=0.0, **extra):
    return {"id": id, "name": name, "saldo_inicial": saldo_inicial, **extra}


def vista(capital=1000.0, interes=0.0, retencion=0.0, apertura="2025-01-10",
          cierre="2025-02-10", portafolio_id=P1, **extra):
    """Una posición ya armada, con los movimientos que le corresponden."""
    movimientos = [{"fecha": apertura, "tipo": "aporte", "monto": capital}] if apertura else []
    if cierre:
        movimientos.append({"fecha": cierre, "tipo": "retiro", "monto": capital})
        if interes:
            movimientos.append({"fecha": cierre, "tipo": "interes", "monto": interes})
        if retencion:
            movimientos.append({"fecha": cierre, "tipo": "retencion", "monto": retencion})
    return {
        "id": extra.pop("id", "pos1"),
        "tipo": "plazo_fijo",
        "portafolio_id": portafolio_id,
        "fecha_apertura": apertura,
        "fecha_cierre": cierre,
        "capital": capital,
        "interes": interes,
        "retencion": retencion,
        "movimientos": movimientos,
        **extra,
    }


def generados(vistas, portafolios=None, desde=None):
    portafolios = portafolios or [portafolio()]
    return [p.to_dict() for p in neu.generar_pagos(vistas, portafolios, desde=desde)]


def pago(amount, start, end=None):
    return {"amount": amount, "start": start, "end": end}


# ── El residual ──────────────────────────────────────────────────────────────

def test_la_apertura_baja_el_residual_y_el_cierre_lo_sube():
    """Meter plata en un certificado la saca del bolsillo; sacarla la devuelve con interés."""
    pagos = generados([vista(capital=1000.0, interes=10.0, retencion=0.2)])

    assert [(p["amount"], p["start"], p["end"]) for p in pagos] == [
        (-1000.0, "2025-01-10", "2025-02-10"),
        (9.8, "2025-02-10", None),
    ]


def test_el_residual_encadena_una_reinversion():
    """La cadena real de `Inversiones_Mias`, incluido su tramo negativo.

    Reinvertir 1.200 teniendo 1.009,80 de plata de inversión deja el residual en −190,20.
    Ese número no es una deuda: es el artefacto contable que en los datos del usuario
    aparece como el pago de −103.
    """
    pagos = generados(
        [vista(id="a", capital=1000.0, interes=10.0, retencion=0.2,
               apertura="2025-01-10", cierre="2025-02-10"),
         vista(id="b", capital=1200.0, interes=12.0, retencion=0.24,
               apertura="2025-02-10", cierre="2025-03-10")],
        [portafolio(saldo_inicial=1000.0)],
    )

    assert [(p["amount"], p["start"]) for p in pagos] == [
        # 2025-01-10 no genera pago: 1.000 − 1.000 deja el residual en cero.
        (-190.2, "2025-02-10"),   # 0 + 1.009,80 − 1.200
        (1021.56, "2025-03-10"),  # −190,20 + 1.200 + 12 − 0,24
    ]


def test_el_tramo_con_residual_cero_no_genera_pago():
    """Sumar cero al escalón es lo mismo que no tener la fila."""
    pagos = generados([vista(capital=1000.0, interes=0.0)],
                      [portafolio(saldo_inicial=1000.0)])

    assert [(p["amount"], p["start"]) for p in pagos] == [(1000.0, "2025-02-10")]


def test_el_aporte_de_una_posicion_sin_apertura_no_cuenta():
    """La sembrada a mano ya estaba dentro del certificado: su plata nunca estuvo suelta.

    Su aporte lleva una fecha estimada solo para que las métricas tengan capital. Contarlo
    como salida hundiría el residual del portafolio durante meses.
    """
    sembrada = vista(capital=1000.0, interes=10.0, apertura=None, cierre="2025-02-10")
    sembrada["movimientos"].insert(0, {"fecha": "2024-03-12", "tipo": "aporte", "monto": 1000.0})

    pagos = generados([sembrada])

    assert [(p["amount"], p["start"]) for p in pagos] == [(1010.0, "2025-02-10")]


def test_los_movimientos_de_tipo_desconocido_se_ignoran():
    """Sin signo definido en `metricas.SIGNO`, un movimiento no puede mover el residual."""
    posicion = vista(capital=1000.0)
    posicion["movimientos"].append({"fecha": "2025-02-10", "tipo": "inventado", "monto": 500.0})

    # El retiro de 1.000 devuelve el residual a cero, así que el cierre no genera pago.
    assert [p["amount"] for p in generados([posicion])] == [-1000.0]


def test_una_posicion_sin_portafolio_no_genera_nada():
    assert generados([vista(portafolio_id=None)]) == []


def test_cada_portafolio_lleva_su_propia_cuenta():
    pagos = generados(
        [vista(id="a", capital=1000.0, portafolio_id=P1),
         vista(id="b", capital=500.0, portafolio_id=P2, cierre=None)],
        [portafolio(), portafolio(id=P2, name="Inversiones_Uni")],
    )

    por_portafolio = {}
    for p in pagos:
        por_portafolio.setdefault(p["portafolio"], []).append(p["amount"])
    assert por_portafolio == {
        # `Mias` cierra sin interés: el retiro devuelve el residual a cero y no genera pago.
        "Inversiones_Mias": [-1000.0],
        "Inversiones_Uni": [-500.0],
    }


def test_el_motivo_dice_que_paso_ese_dia():
    pagos = generados([vista(capital=1000.0, interes=10.0)])

    assert pagos[0]["motivo"] == "abre 1,000"
    assert pagos[1]["motivo"] == "cierra 1,000"


def test_el_motivo_de_una_salida_no_dice_abre_y_cierra():
    """Un flujo es instantáneo: «abre 3,835 · cierra 3,835» lo describiría por duplicado."""
    salida = vista(capital=3834.64, apertura="2024-09-23", cierre="2024-09-23", tipo="flujo")
    salida["movimientos"] = [{"fecha": "2024-09-23", "tipo": "aporte", "monto": 3834.64}]

    assert generados([salida])[0]["motivo"] == "sale 3,835"


def test_el_motivo_de_una_entrada_mira_lo_retirado():
    """Una entrada no tiene aportes, así que su `capital` es 0 y diría «entra 0»."""
    entrada = vista(capital=0.0, apertura="2024-11-18", cierre="2024-11-18", tipo="flujo",
                    retirado=3635.07)
    entrada["movimientos"] = [{"fecha": "2024-11-18", "tipo": "retiro", "monto": 3635.07}]

    assert generados([entrada])[0]["motivo"] == "entra 3,635"


# ── El tramo del saldo inicial ───────────────────────────────────────────────

def test_el_saldo_inicial_abre_su_propio_tramo():
    """Lo que el portafolio ya tenía suelto antes del primer evento derivable."""
    pagos = generados([vista(capital=1000.0)],
                      [portafolio(saldo_inicial=300.0)],
                      desde={P1: date(2024, 3, 12)})

    assert [(p["amount"], p["start"], p["end"], p["motivo"]) for p in pagos][0] == (
        300.0, "2024-03-12", "2025-01-10", "saldo inicial",
    )


def test_sin_arranque_no_hay_tramo_de_saldo_inicial():
    """El saldo inicial sigue contando en el residual, pero no se ve antes del primer evento."""
    pagos = generados([vista(capital=1000.0)], [portafolio(saldo_inicial=300.0)])

    assert [(p["amount"], p["start"]) for p in pagos] == [
        (-700.0, "2025-01-10"),
        (300.0, "2025-02-10"),
    ]


def test_un_arranque_posterior_al_primer_evento_no_abre_tramo():
    pagos = generados([vista(capital=1000.0)],
                      [portafolio(saldo_inicial=300.0)],
                      desde={P1: date(2025, 6, 1)})

    assert all(p["motivo"] != "saldo inicial" for p in pagos)


def test_un_saldo_inicial_de_cero_no_abre_tramo():
    pagos = generados([vista(capital=1000.0)],
                      [portafolio(saldo_inicial=0.0)],
                      desde={P1: date(2024, 3, 12)})

    assert all(p["motivo"] != "saldo inicial" for p in pagos)


# ── La ventana del dashboard ─────────────────────────────────────────────────

def test_la_ventana_incluye_el_inicio_y_excluye_el_fin():
    """`start <= FECHA < end`, igual que `VirtualItemsProcessor._apply_fixed_payment`."""
    fechas = [date(2025, 1, 9), date(2025, 1, 10), date(2025, 1, 11), date(2025, 1, 12)]

    assert neu.serie([pago(100.0, "2025-01-10", "2025-01-12")], fechas) == [0.0, 100.0, 100.0, 0.0]


def test_un_pago_sin_start_date_no_entra_en_la_serie():
    """El dashboard los descarta (`if not start: return`), así que aquí tampoco cuentan."""
    fechas = [date(2025, 1, 10), date(2026, 1, 10)]

    assert neu.serie([pago(26000.0, None, "2025-06-01")], fechas) == [0.0, 0.0]


def test_un_pago_sin_end_date_no_termina_nunca():
    fechas = [date(2025, 1, 10), date(2030, 1, 10)]

    assert neu.serie([pago(100.0, "2025-01-10", None)], fechas) == [100.0, 100.0]


def test_una_fecha_centinela_equivale_a_no_tener_fin():
    fechas = [date(2025, 1, 10), date(2030, 1, 10)]

    assert neu.serie([pago(100.0, "2025-01-10", "3000-01-01")], fechas) == [100.0, 100.0]


def test_la_serie_suma_los_pagos_solapados():
    fechas = [date(2025, 1, 10)]

    assert neu.serie([pago(100.0, "2025-01-01"), pago(50.0, "2025-01-05")], fechas) == [150.0]


# ── La comparación ───────────────────────────────────────────────────────────

def test_dos_conjuntos_distintos_con_la_misma_serie_cuadran():
    """El invariante no son las filas, es la función escalón evaluada."""
    partido = [pago(100.0, "2025-01-01", "2025-02-01"), pago(100.0, "2025-02-01", "2025-03-01")]
    entero = [pago(100.0, "2025-01-01", "2025-03-01")]

    comparacion = neu.comparar(partido, entero, hoy=date(2025, 3, 1))

    assert comparacion.dias_descuadrados == 0
    assert comparacion.to_dict()["cuadra"] is True


def test_la_comparacion_recorre_todos_los_dias_del_calendario():
    """Del primer pago hasta hoy, día por día."""
    comparacion = neu.comparar([pago(100.0, "2025-01-01", "2025-01-11")], [], hoy=date(2025, 1, 10))

    assert comparacion.fechas[0] == "2025-01-01"
    assert comparacion.fechas[-1] == "2025-01-10"
    assert comparacion.diferencia == [100.0] * 10


def test_la_comparacion_no_pasa_de_hoy():
    """El futuro no es validable: comparar más allá de hoy solo da artefactos de borde.

    Basta un pago que diga `2030-01-01` —que el usuario usa como «hasta siempre», igual que
    el `3000-01-01` que sí se reconoce como centinela— para estirar la ventana años y
    marcar descuadrado el último día de un tramo que en realidad cuadra.
    """
    comparacion = neu.comparar([pago(27067.0, "2026-07-27", "2030-01-01")], [],
                               hoy=date(2026, 8, 12))

    assert comparacion.fechas[-1] == "2026-08-12"
    assert set(comparacion.diferencia) == {27067.0}


def test_sin_pagos_de_ninguno_de_los_dos_lados_la_comparacion_es_vacia():
    assert neu.comparar([], [], hoy=date(2025, 1, 10)).to_dict()["dias"] == 0


def test_una_diferencia_de_redondeo_descuadra_pero_no_es_material():
    """Los pagos a mano están redondeados a enteros; un par de dólares es del usuario."""
    comparacion = neu.comparar([pago(27897.0, "2025-01-01", "2025-01-03")],
                               [pago(27897.57, "2025-01-01", "2025-01-03")],
                               hoy=date(2025, 1, 2))

    assert comparacion.dias_descuadrados == 2
    assert comparacion.dias_materiales == 0
    assert comparacion.max_desvio == 0.57
    assert comparacion.to_dict()["cuadra"] is True


def test_una_diferencia_grande_si_es_material():
    comparacion = neu.comparar([pago(3533.0, "2025-01-01", "2025-01-03")], [],
                               hoy=date(2025, 1, 2))

    assert comparacion.dias_materiales == 2
    assert comparacion.primer_descuadre == "2025-01-01"
    assert comparacion.to_dict()["cuadra"] is False


# ── El saldo inicial sugerido ────────────────────────────────────────────────

def test_el_saldo_inicial_sugerido_es_la_diferencia_del_primer_dia():
    """Definición literal: lo que el escalón ya valía antes del primer evento derivable."""
    comparacion = neu.comparar([pago(26000.0, "2025-01-01", "2025-01-05")],
                               [pago(1000.0, "2025-01-03", "2025-01-05")],
                               hoy=date(2025, 1, 4))

    assert neu.saldo_inicial_sugerido(comparacion) == 26000.0


def test_el_saldo_inicial_sugerido_no_confunde_un_descuadre_largo_con_una_siembra():
    """El valor más repetido devolvía el descuadre y lo disfrazaba de saldo inicial."""
    comparacion = neu.comparar(
        [pago(3533.0, "2025-01-03", "2025-01-20")],
        [pago(0.0, "2025-01-01", "2025-01-20")],
        hoy=date(2025, 1, 19),
    )

    assert neu.saldo_inicial_sugerido(comparacion) == 0.0


def test_sin_comparacion_el_saldo_inicial_sugerido_es_cero():
    assert neu.saldo_inicial_sugerido(neu.Comparacion()) == 0.0


def test_el_residuo_tras_la_siembra_separa_la_constante_del_descuadre_real():
    """Una diferencia que es exactamente una constante desaparece al sembrarla."""
    comparacion = neu.comparar([pago(1100.0, "2025-01-01", None)],
                               [pago(100.0, "2025-01-01", None)],
                               hoy=date(2025, 1, 3))

    residuo = neu.residuo_tras_siembra(comparacion, siembra=1000.0)

    assert residuo["serie"] == [0.0, 0.0, 0.0]
    assert residuo["dias_descuadrados"] == 0
    assert residuo["primer_descuadre"] is None


def test_el_residuo_tras_la_siembra_deja_ver_lo_que_no_explica():
    comparacion = neu.comparar([pago(1500.0, "2025-01-01", None)], [], hoy=date(2025, 1, 2))

    residuo = neu.residuo_tras_siembra(comparacion, siembra=1000.0)

    assert residuo["max_desvio"] == 500.0
    assert residuo["tramos"] == [
        {"desde": "2025-01-01", "hasta": "2025-01-02", "dias": 2, "monto": 500.0},
    ]


# ── Los tramos ───────────────────────────────────────────────────────────────

def test_los_tramos_agrupan_dias_contiguos_con_el_mismo_desvio():
    tramos = neu._tramos([("2025-01-01", 500.0), ("2025-01-02", 500.0), ("2025-01-03", 500.0)])

    assert tramos == [{"desde": "2025-01-01", "hasta": "2025-01-03", "dias": 3, "monto": 500.0}]


def test_un_hueco_de_calendario_parte_el_tramo():
    tramos = neu._tramos([("2025-01-01", 500.0), ("2025-01-03", 500.0)])

    assert [t["desde"] for t in tramos] == ["2025-01-01", "2025-01-03"]


def test_un_cambio_de_monto_parte_el_tramo():
    tramos = neu._tramos([("2025-01-01", 500.0), ("2025-01-02", 700.0)])

    assert [t["monto"] for t in tramos] == [500.0, 700.0]


def test_los_tramos_salen_del_mas_largo_al_mas_corto_y_acotados():
    descuadrados = [(date(2025, 1, 1).replace(day=d).isoformat(), float(d)) for d in range(1, 21)]

    tramos = neu._tramos(descuadrados, maximo=3)

    assert len(tramos) == 3
    assert all(t["dias"] == 1 for t in tramos)


# ── Los pagos que hoy están escritos a mano ──────────────────────────────────

@pytest.fixture
def interpolaciones(tmp_path):
    """Apunta `grupos.csv` y `pagos.csv` a `tmp_path`."""
    carpeta = tmp_path / "interpolaciones"
    carpeta.mkdir()
    with patch("contabilidad.backend.storage.variables_storage.BASE_DATA_PATH", str(carpeta)), \
         patch("contabilidad.backend.storage.variables_storage.GROUPS_FILE", str(carpeta / "grupos.csv")), \
         patch("contabilidad.backend.storage.variables_storage.PAYMENTS_FILE", str(carpeta / "pagos.csv")):
        from contabilidad.backend.storage.variables_storage import InterpolationStorage
        yield InterpolationStorage


def test_pagos_actuales_marca_las_filas_sin_start_date_como_que_no_aplican(interpolaciones):
    """Existen en el CSV, ocupan lugar y el dashboard las ignora. Hay que poder verlas."""
    grupo = interpolaciones.create_group(name="Inversiones_Mias", group_type="fixed",
                                         es_inversion=True)
    interpolaciones.create_payment(grupo["id"], 26000.0, None, "2025-01-24")
    interpolaciones.create_payment(grupo["id"], 27897.0, "2025-01-24", "2025-02-21")

    actuales = neu.pagos_actuales([{**grupo, "saldo_inicial": 0.0}])

    assert [(p["amount"], p["aplica"]) for p in actuales] == [(26000.0, False), (27897.0, True)]


def test_pagos_actuales_tambien_descarta_las_filas_sin_end_date(interpolaciones):
    """`get_payments()` hace dropna sobre las DOS fechas, no solo sobre `start_date`.

    Una fila sin fin es invisible en las dos puntas: el dashboard no la aplica y la
    pantalla de Variables no la lista, así que el usuario tampoco puede borrarla. En los
    datos reales hay una así —los 647 duplicados de `Madre`— y contarla inventaba un
    descuadre de 645,79 que ningún dashboard tenía.
    """
    grupo = interpolaciones.create_group(name="Inversiones_Madre", group_type="fixed")
    interpolaciones.create_payment(grupo["id"], 647.0, "2025-12-22", None)
    interpolaciones.create_payment(grupo["id"], 647.0, "2025-12-22", "2026-03-02")

    actuales = neu.pagos_actuales([grupo])

    assert [(p["end"], p["aplica"]) for p in actuales] == [(None, False), ("2026-03-02", True)]


def test_una_fila_que_no_aplica_no_entra_en_la_serie(interpolaciones):
    """El escalón tiene que medir lo que el patrimonio de verdad vio."""
    fechas = [date(2026, 1, 1)]
    invisible = {"amount": 647.0, "start": "2025-12-22", "end": None, "aplica": False}
    visible = {"amount": 647.0, "start": "2025-12-22", "end": "2026-03-02", "aplica": True}

    assert neu.serie([invisible, visible], fechas) == [647.0]


def test_un_pago_generado_sin_fin_si_aplica():
    """En un pago generado `end` vacío significa «hasta siempre», no «fila inválida»."""
    assert neu.serie([pago(100.0, "2025-01-10", None)], [date(2030, 1, 1)]) == [100.0]


def test_pagos_actuales_ignora_los_grupos_que_no_son_portafolios(interpolaciones):
    portafolio_ = interpolaciones.create_group(name="Inversiones_Mias", group_type="fixed")
    otro = interpolaciones.create_group(name="Fondo Comida", group_type="fixed")
    interpolaciones.create_payment(portafolio_["id"], 100.0, "2025-01-01", "2025-02-01")
    interpolaciones.create_payment(otro["id"], 999.0, "2025-01-01", "2025-02-01")

    actuales = neu.pagos_actuales([portafolio_])

    assert [p["amount"] for p in actuales] == [100.0]


def test_pagos_actuales_deja_las_notas_vacias_como_texto(interpolaciones):
    """Una columna de notas enteramente vacía vuelve de pandas como NaN, y NaN no es JSON.

    `read_csv` promete convertirlos a `None`, pero lo hace con un `.apply` que la
    inferencia de dtype deshace. Y como `nan` es *truthy*, un `or ''` tampoco lo atrapa:
    el endpoint respondía 500 al serializar.
    """
    grupo = interpolaciones.create_group(name="Inversiones_Mias", group_type="fixed")
    interpolaciones.create_payment(grupo["id"], 100.0, "2025-01-10", "2025-02-10")

    actuales = neu.pagos_actuales([grupo])

    assert actuales[0]["nota"] == ""
    assert isinstance(actuales[0]["id"], str)


def test_preview_es_serializable_a_json(interpolaciones):
    """La garantía de punta a punta: lo que devuelve el endpoint tiene que poder viajar."""
    import json

    grupo = interpolaciones.create_group(name="Inversiones_Mias", group_type="fixed")
    interpolaciones.create_payment(grupo["id"], 100.0, "2025-01-10", "3000-01-01")

    resultado = neu.preview([vista(capital=1000.0, portafolio_id=grupo["id"])],
                            [grupo], hoy=date(2025, 3, 1))

    json.dumps(resultado, allow_nan=False)


def test_pagos_actuales_normaliza_la_fecha_centinela_a_sin_fin(interpolaciones):
    grupo = interpolaciones.create_group(name="Inversiones_Madre", group_type="fixed")
    interpolaciones.create_payment(grupo["id"], 647.0, "2025-12-22", "3000-01-01")

    assert neu.pagos_actuales([grupo])[0]["end"] is None


# ── La previsualización ──────────────────────────────────────────────────────

def test_preview_detecta_el_saldo_inicial_y_luego_cuadra(interpolaciones):
    """Las dos pasadas: primero la constante que falta, después lo que no se explica.

    El portafolio tenía 1.000 sueltos antes de que empezara el historial derivable. La
    pasada 1 lo descubre y la pasada 2 regenera con ese saldo puesto — y ahí ya cuadra.
    """
    grupo = interpolaciones.create_group(name="Inversiones_Mias", group_type="fixed",
                                         es_inversion=True)
    interpolaciones.create_payment(grupo["id"], 1000.0, "2024-03-12", "2025-01-10")
    interpolaciones.create_payment(grupo["id"], 0.0, "2025-01-10", "2025-02-10")
    interpolaciones.create_payment(grupo["id"], 1010.0, "2025-02-10", "3000-01-01")

    resultado = neu.preview([vista(capital=1000.0, interes=10.0, portafolio_id=grupo["id"])],
                            [grupo], hoy=date(2025, 3, 1))

    assert resultado["resumen"]["siembra_total"] == 1000.0
    assert resultado["resumen"]["cuadra"] is True
    assert resultado["resumen"]["portafolios_que_cuadran"] == 1
    assert resultado["por_portafolio"][0]["saldo_inicial_sugerido"] == 1000.0


def test_preview_reporta_lo_que_no_explica_la_siembra(interpolaciones):
    """Un pago a mano de más queda como tramo descuadrado, no como saldo inicial."""
    grupo = interpolaciones.create_group(name="Inversiones_Uni", group_type="fixed")
    interpolaciones.create_payment(grupo["id"], -1000.0, "2025-01-10", "2025-02-10")
    interpolaciones.create_payment(grupo["id"], 5000.0, "2025-02-10", "3000-01-01")

    resultado = neu.preview([vista(capital=1000.0, interes=10.0, portafolio_id=grupo["id"])],
                            [grupo], hoy=date(2025, 3, 1))

    assert resultado["resumen"]["siembra_total"] == 0.0
    assert resultado["resumen"]["cuadra"] is False
    detalle = resultado["por_portafolio"][0]
    # El residual generado el 2025-02-10 es 10 (−1.000 + 1.000 + 10), no 1.010: el pago
    # es el residual acumulado, no el cobro del día. Contra los 5.000 escritos a mano
    # quedan 4.990 sin explicar.
    assert detalle["tramos"][0] == {
        "desde": "2025-02-10", "hasta": "2025-03-01", "dias": 20, "monto": 4990.0,
    }


def test_preview_cuenta_los_pagos_que_el_dashboard_ignora(interpolaciones):
    grupo = interpolaciones.create_group(name="Inversiones_Mias", group_type="fixed")
    interpolaciones.create_payment(grupo["id"], 26000.0, None, "2025-01-10")

    resultado = neu.preview([vista(capital=1000.0, portafolio_id=grupo["id"])],
                            [grupo], hoy=date(2025, 3, 1))

    assert resultado["resumen"]["pagos_actuales"] == 1
    assert resultado["resumen"]["pagos_actuales_ignorados"] == 1


def test_preview_marca_la_custodia(interpolaciones):
    grupo = interpolaciones.create_group(name="Inversiones_Madre", group_type="fixed",
                                         es_custodia=True)
    interpolaciones.create_payment(grupo["id"], 100.0, "2025-01-10", "3000-01-01")

    resultado = neu.preview([vista(capital=1000.0, portafolio_id=grupo["id"])],
                            [grupo], hoy=date(2025, 3, 1))

    assert resultado["por_portafolio"][0]["es_custodia"] is True


def test_preview_omite_los_portafolios_sin_pagos_de_ningun_lado(interpolaciones):
    con_datos = interpolaciones.create_group(name="Inversiones_Mias", group_type="fixed")
    vacio = interpolaciones.create_group(name="Inversiones_Nuevo", group_type="fixed")
    interpolaciones.create_payment(con_datos["id"], 100.0, "2025-01-10", "3000-01-01")

    resultado = neu.preview([vista(capital=1000.0, portafolio_id=con_datos["id"])],
                            [con_datos, vacio], hoy=date(2025, 3, 1))

    assert [d["nombre"] for d in resultado["por_portafolio"]] == ["Inversiones_Mias"]
    assert resultado["resumen"]["portafolios"] == 1


def test_preview_no_escribe_en_pagos_csv(interpolaciones, tmp_path):
    """La fase 6 está a propósito en modo solo lectura."""
    grupo = interpolaciones.create_group(name="Inversiones_Mias", group_type="fixed")
    interpolaciones.create_payment(grupo["id"], 100.0, "2025-01-10", "3000-01-01")
    antes = (tmp_path / "interpolaciones" / "pagos.csv").read_bytes()

    neu.preview([vista(capital=1000.0, portafolio_id=grupo["id"])], [grupo], hoy=date(2025, 3, 1))

    assert (tmp_path / "interpolaciones" / "pagos.csv").read_bytes() == antes
