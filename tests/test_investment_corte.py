"""
test_investment_corte.py — La fase 6: cambiar los pagos a mano por los generados.

El invariante que estos tests protegen no son las filas de `pagos.csv` sino **la función
escalón evaluada**: dos conjuntos distintos de pagos pueden producir el mismo
`PAGOS_FIJOS(t)`, y lo que no puede cambiar es la serie diaria.

Todo corre contra CSVs en `tmp_path`.
"""
from datetime import date

import pytest
from unittest.mock import patch

from contabilidad.backend.services.investments import corte
from contabilidad.backend.services.investments import neutralizacion
from contabilidad.backend.services.investments import posiciones as svc


@pytest.fixture
def storage(tmp_path):
    inversiones = tmp_path / "inversiones"
    interpolaciones = tmp_path / "interpolaciones"
    inversiones.mkdir()
    interpolaciones.mkdir()

    with patch("contabilidad.backend.storage.investments_storage.BASE_DATA_PATH", str(inversiones)), \
         patch("contabilidad.backend.storage.investments_storage.POSITIONS_FILE", str(inversiones / "posiciones.csv")), \
         patch("contabilidad.backend.storage.investments_storage.MOVEMENTS_FILE", str(inversiones / "movimientos.csv")), \
         patch("contabilidad.backend.storage.variables_storage.BASE_DATA_PATH", str(interpolaciones)), \
         patch("contabilidad.backend.storage.variables_storage.GROUPS_FILE", str(interpolaciones / "grupos.csv")), \
         patch("contabilidad.backend.storage.variables_storage.PAYMENTS_FILE", str(interpolaciones / "pagos.csv")):
        from contabilidad.backend.storage.variables_storage import InterpolationStorage
        yield InterpolationStorage


@pytest.fixture
def escenario(storage):
    """Un portafolio con un certificado y los pagos a mano que le corresponden.

    El certificado de 10.000 se abre el 2025-01-10 y vence el 2025-04-10 devolviendo
    10.200. Con una siembra de 10.000, el residual es 10.000 antes de abrirlo, 0 mientras
    está dentro y 10.200 después.
    """
    grupo = storage.create_group(name="Inversiones_Mias", group_type="fixed", es_inversion=True)
    storage.create_payment(grupo["id"], 10000.0, "2024-06-01", "2025-01-10")
    storage.create_payment(grupo["id"], 10200.0, "2025-04-10", "3000-01-01")

    svc.create_position({
        "portafolio_id": grupo["id"],
        "tipo": "plazo_fijo",
        "origen": "detectado",
        "fecha_apertura": "2025-01-10",
        "fecha_cierre": "2025-04-10",
        "movimientos": [
            {"fecha": "2025-01-10", "tipo": "aporte", "monto": 10000.0},
            {"fecha": "2025-04-10", "tipo": "retiro", "monto": 10000.0},
            {"fecha": "2025-04-10", "tipo": "interes", "monto": 200.0},
        ],
    })
    return grupo


HOY = date(2025, 6, 1)


# ── Paso 1: la sombra ────────────────────────────────────────────────────────

def test_sembrar_sombra_crea_un_grupo_por_portafolio(escenario, storage):
    resultado = corte.sembrar_sombra()

    assert resultado['portafolios'][0]['portafolio'] == "Inversiones_Mias"
    assert resultado['pagos'] > 0
    sombra = [g for g in storage.get_groups(type_filter=None) if g['type'] == 'shadow']
    assert len(sombra) == 1
    assert sombra[0]['fondo_origen'] == escenario['id']


def test_la_sombra_no_cambia_lo_que_el_dashboard_aplica(escenario, storage):
    """`VirtualItemsProcessor` solo aplica `fixed` e `interpolated`."""
    fechas = [date(2024, 12, 1), date(2025, 2, 1), date(2025, 5, 1)]
    antes = corte._pagos_de_grupos(['fixed'])
    corte.sembrar_sombra()
    despues = corte._pagos_de_grupos(['fixed'])

    from contabilidad.backend.services.investments import neutralizacion
    assert neutralizacion.serie(antes, fechas) == neutralizacion.serie(despues, fechas)


def test_sembrar_sombra_dos_veces_no_duplica(escenario, storage):
    """Idempotente: se borra el grupo anterior y se reconstruye."""
    corte.sembrar_sombra()
    primera = len(corte._pagos_de_grupos(['shadow']))
    corte.sembrar_sombra()

    assert len(corte._pagos_de_grupos(['shadow'])) == primera
    assert len([g for g in storage.get_groups(type_filter=None) if g['type'] == 'shadow']) == 1


def test_la_sombra_se_localiza_por_fondo_origen_no_por_nombre(escenario, storage):
    """Si se buscara por nombre, renombrar el grupo crearía un segundo en vez de reemplazar."""
    corte.sembrar_sombra()
    sombra = [g for g in storage.get_groups(type_filter=None) if g['type'] == 'shadow'][0]
    storage.update_group(sombra['id'], {'name': 'Otro nombre cualquiera'})

    corte.sembrar_sombra()

    assert len([g for g in storage.get_groups(type_filter=None) if g['type'] == 'shadow']) == 1


def test_un_tramo_abierto_se_escribe_con_end_date_vacio(escenario, storage):
    """El último tramo de cada portafolio no tiene fin, y eso ahora se escribe vacío.

    Hasta el 2026-08-12 había que poner la centinela `3000-01-01`: `get_payments()` hacía
    `dropna` sobre las dos fechas, así que un fin vacío hacía desaparecer la fila del
    dashboard *y* de la UI, y el corte habría perdido justo el tramo vigente. Ya no.

    Lo que este test protege de verdad es la segunda mitad: **ningún pago se pierde por el
    camino**, que es lo que la centinela existía para garantizar.
    """
    corte.sembrar_sombra()
    sombra = [g for g in storage.get_groups(type_filter=None) if g['type'] == 'shadow'][0]

    pagos = storage.get_payments(sombra['id'])
    assert any(p['end_date'] is None for p in pagos), "el tramo vigente no tiene fin"
    assert len(pagos) == len(corte._pagos_de_grupos(['shadow']))


def test_limpiar_sombra_deja_todo_como_estaba(escenario, storage):
    antes = len(storage.get_groups(type_filter=None))
    corte.sembrar_sombra()

    assert corte.limpiar_sombra() == 1
    assert len(storage.get_groups(type_filter=None)) == antes


# ── Paso 2: la verificación ──────────────────────────────────────────────────

def test_verificar_exige_que_haya_sombra(escenario):
    assert 'error' in corte.verificar(hoy=HOY)


def test_verificar_no_escribe_nada(escenario, tmp_path):
    corte.sembrar_sombra()
    antes = (tmp_path / "interpolaciones" / "pagos.csv").read_bytes()

    corte.verificar(hoy=HOY)

    assert (tmp_path / "interpolaciones" / "pagos.csv").read_bytes() == antes


def test_un_generador_que_reproduce_la_contabilidad_es_equivalente(escenario):
    corte.sembrar_sombra()

    resultado = corte.verificar(hoy=HOY)

    assert resultado['equivalente'] is True
    assert resultado['max_desvio'] <= corte.TOLERANCIA_CORTE


def test_verificar_detecta_una_serie_que_se_movería(escenario, storage):
    """Un pago a mano que el generador no reproduce tiene que salir en el diff."""
    storage.create_payment(escenario["id"], 5000.0, "2025-04-10", "2025-05-10")
    corte.sembrar_sombra()

    resultado = corte.verificar(hoy=HOY)

    assert resultado['equivalente'] is False
    assert resultado['max_desvio'] == 5000.0
    assert resultado['peores_dias'][0]['desvio'] == 5000.0


def test_verificar_no_toca_los_grupos_ajenos(escenario, storage):
    """Un grupo `fixed` que no es de inversión tiene que sobrevivir al corte intacto."""
    otro = storage.create_group(name="Fondo Comida", group_type="fixed")
    storage.create_payment(otro["id"], 300.0, "2024-06-01", "3000-01-01")
    corte.sembrar_sombra()

    resultado = corte.verificar(hoy=HOY)

    # Los 300 están en las dos series, así que no aportan diferencia.
    assert resultado['equivalente'] is True


# ── Paso 3: el corte ─────────────────────────────────────────────────────────

def test_el_corte_se_niega_si_la_serie_se_movería(escenario, storage):
    storage.create_payment(escenario["id"], 5000.0, "2025-04-10", "2025-05-10")
    corte.sembrar_sombra()

    resultado = corte.aplicar_corte(hoy=HOY)

    assert resultado['ok'] is False
    assert 'se movería' in resultado['error']
    # Y no ha tocado nada.
    assert len(storage.get_payments(escenario['id'])) == 3


def test_forzar_corta_igual(escenario, storage):
    storage.create_payment(escenario["id"], 5000.0, "2025-04-10", "2025-05-10")
    corte.sembrar_sombra()

    assert corte.aplicar_corte(forzar=True, hoy=HOY)['ok'] is True
    assert storage.get_payments(escenario['id']) == []


def test_el_corte_vacia_el_original_y_activa_la_sombra(escenario, storage):
    corte.sembrar_sombra()

    resultado = corte.aplicar_corte(hoy=HOY)

    assert resultado['ok'] is True
    assert resultado['pagos_vaciados'] == 2
    assert storage.get_payments(escenario['id']) == []
    assert [g['type'] for g in storage.get_groups(type_filter=None)
            if g['fondo_origen'] == escenario['id']] == ['fixed']


def test_el_portafolio_sobrevive_al_corte_como_metadatos(escenario, storage):
    """Los grupos `Inversiones_*` siguen existiendo, sin pagos: son los portafolios."""
    corte.sembrar_sombra()
    corte.aplicar_corte(hoy=HOY)

    grupo = storage.get_group(escenario['id'])
    assert grupo is not None
    assert grupo['name'] == "Inversiones_Mias"
    assert grupo['es_inversion'] is True


def test_la_serie_diaria_es_la_misma_despues_del_corte(escenario):
    """El invariante de toda la fase: el dashboard no puede notar la migración."""
    from contabilidad.backend.services.investments import neutralizacion
    fechas = [date(2024, 6, 1) + __import__('datetime').timedelta(days=n) for n in range(0, 400, 7)]
    antes = neutralizacion.serie(corte._pagos_de_grupos(['fixed']), fechas)

    corte.sembrar_sombra()
    corte.aplicar_corte(hoy=HOY)
    despues = neutralizacion.serie(corte._pagos_de_grupos(['fixed']), fechas)

    for f, a, d in zip(fechas, antes, despues):
        assert abs(a - d) <= corte.TOLERANCIA_CORTE, f"{f}: {a} → {d}"


def test_el_estado_dice_donde_esta_el_corte(escenario):
    assert corte.estado()['cortado'] is False

    corte.sembrar_sombra()
    assert corte.estado()['cortado'] is False
    assert corte.estado()['portafolios'][0]['sombra'] > 0

    corte.aplicar_corte(hoy=HOY)
    estado = corte.estado()
    assert estado['cortado'] is True
    assert estado['portafolios'][0]['pagos_propios'] == 0
    assert estado['portafolios'][0]['generado_activo'] > 0


# ── La unidad de la tolerancia ───────────────────────────────────────────────
#
# `TOLERANCIA_CORTE` mide el redondeo a enteros de UN portafolio. Medirla contra la serie
# agregada compara la suma de N redondeos independientes contra una vara calibrada para
# uno, y el corte se niega por un descuadre que no existe en ninguna contabilidad. Pasó de
# verdad: el agregado marcaba 3,40 y era 1,09 + 1,07 + 1,24.

def _portafolio_con_redondeo(storage, nombre, desvio):
    """Un portafolio cuyo pago a mano difiere `desvio` del que genera el módulo.

    El certificado devuelve 10.200 exactos; el pago escrito a mano dice 10.200 − desvío,
    que es justo lo que pasa cuando el usuario redondea a enteros.
    """
    grupo = storage.create_group(name=nombre, group_type="fixed", es_inversion=True)
    storage.create_payment(grupo["id"], 10000.0, "2024-06-01", "2025-01-10")
    storage.create_payment(grupo["id"], 10200.0 - desvio, "2025-04-10", "3000-01-01")

    svc.create_position({
        "portafolio_id": grupo["id"],
        "tipo": "plazo_fijo",
        "origen": "detectado",
        "fecha_apertura": "2025-01-10",
        "fecha_cierre": "2025-04-10",
        "movimientos": [
            {"fecha": "2025-01-10", "tipo": "aporte", "monto": 10000.0},
            {"fecha": "2025-04-10", "tipo": "retiro", "monto": 10000.0},
            {"fecha": "2025-04-10", "tipo": "interes", "monto": 200.0},
        ],
    })
    return grupo


def test_tres_redondeos_pequenos_no_se_suman_para_bloquear_el_corte(storage):
    """Cada portafolio dentro de tolerancia ⇒ se puede cortar, aunque el agregado no.

    Es el caso real que tenía la fase 6 parada.
    """
    _portafolio_con_redondeo(storage, "Inversiones_Mias", 1.4)
    _portafolio_con_redondeo(storage, "Inversiones_Uni", 1.3)
    _portafolio_con_redondeo(storage, "Inversiones_Madre", 1.2)
    corte.sembrar_sombra()

    r = corte.verificar(hoy=HOY)

    assert [p['cuadra'] for p in r['por_portafolio']] == [True, True, True]
    assert r['peor_portafolio'] <= corte.TOLERANCIA_CORTE
    assert r['max_desvio'] > corte.TOLERANCIA_CORTE, "el agregado sí los suma"
    assert r['equivalente'] is True, "el agregado no puede ser la puerta"


def test_un_solo_portafolio_fuera_de_tolerancia_bloquea_el_corte(storage):
    """La vara no se movió: un descuadre real de un portafolio sigue parando el corte."""
    _portafolio_con_redondeo(storage, "Inversiones_Mias", 1.0)
    _portafolio_con_redondeo(storage, "Inversiones_Uni", 40.0)
    corte.sembrar_sombra()

    r = corte.verificar(hoy=HOY)

    assert r['equivalente'] is False
    culpables = [p['portafolio'] for p in r['por_portafolio'] if not p['cuadra']]
    assert culpables == ["Inversiones_Uni"]

    resultado = corte.aplicar_corte(hoy=HOY)
    assert resultado['ok'] is False
    assert "Inversiones_Uni" in resultado['error']


def test_verificar_reporta_el_agregado_aunque_no_decida(storage):
    """El impacto sobre el patrimonio se sigue viendo: es lo que el usuario firma."""
    _portafolio_con_redondeo(storage, "Inversiones_Mias", 1.4)
    _portafolio_con_redondeo(storage, "Inversiones_Uni", 1.3)
    corte.sembrar_sombra()

    r = corte.verificar(hoy=HOY)

    assert r['max_desvio'] == pytest.approx(2.7, abs=0.01)
    assert r['dias'] > 0 and r['dias_que_cambian'] > 0
    assert r['peores_dias'], "hay que poder ver qué días se mueven"


def test_el_corte_solo_toca_grupos_marcados_es_inversion(storage):
    """`es_inversion` no es decorativo: es lo que el corte tiene permiso de vaciar.

    `list_portfolios()` es permisivo a propósito —incluye cualquier grupo que ya tenga una
    posición colgando, para que ninguna quede huérfana en la UI—, pero `_portafolios()`
    filtra por la marca. Sin ella, un grupo al que se le asignó una posición por error en
    Conciliación se quedaría sin sus pagos escritos a mano el día del corte.
    """
    marcado = storage.create_group(name="Inversiones_Mias", group_type="fixed", es_inversion=True)
    storage.create_payment(marcado["id"], 10000.0, "2024-06-01", "2025-01-10")

    # Un grupo normal del usuario, con una posición mal asignada colgando.
    ajeno = storage.create_group(name="Mis Depositos", group_type="fixed")
    storage.create_payment(ajeno["id"], 500.0, "2024-06-01", "3000-01-01")

    for grupo, apertura, cierre in [(marcado, "2025-01-10", "2025-04-10"),
                                    (ajeno, "2025-01-10", "2025-04-10")]:
        svc.create_position({
            "portafolio_id": grupo["id"], "tipo": "plazo_fijo", "origen": "detectado",
            "fecha_apertura": apertura, "fecha_cierre": cierre,
            "movimientos": [
                {"fecha": apertura, "tipo": "aporte", "monto": 10000.0},
                {"fecha": cierre, "tipo": "retiro", "monto": 10000.0},
                {"fecha": cierre, "tipo": "interes", "monto": 200.0},
            ],
        })

    # La UI ve los dos; el corte, solo el marcado.
    assert len(svc.list_portfolios()) == 2
    assert [p['name'] for p in corte._portafolios()] == ["Inversiones_Mias"]

    corte.sembrar_sombra()
    corte.aplicar_corte(forzar=True, hoy=HOY)

    assert storage.get_payments(marcado["id"]) == [], "el marcado sí se vacía"
    assert len(storage.get_payments(ajeno["id"])) == 1, "el ajeno no se toca"


def test_sembrar_sombra_se_niega_si_ya_se_corto(escenario, storage):
    """Sembrar dos veces con el corte hecho **duplicaba el patrimonio**.

    `_grupo_sombra()` busca por `fondo_origen` **y** `type == 'shadow'`. Tras el corte el
    grupo generado pasa a `fixed`, así que dejaba de encontrarlo y creaba uno nuevo al lado
    en vez de reemplazarlo. Con los dos grupos vivos, un `aplicar_corte(forzar=True)`
    activaba el segundo sobre el primero: medido, 10.200 pasaban a 20.400.

    `verificar()` lo detecta y el corte sin `forzar` se niega, pero eso es la última red —
    y forzar es exactamente lo que se hace cuando la verificación «no cuadra por poco».
    """
    corte.sembrar_sombra()
    corte.aplicar_corte(forzar=True, hoy=HOY)
    assert corte.estado()['cortado'] is True

    fechas = [date(2025, 5, 1)]
    antes = neutralizacion.serie(corte._pagos_de_grupos(['fixed']), fechas)

    resultado = corte.sembrar_sombra()

    assert 'error' in resultado
    assert resultado['ya_cortados'] == ["Inversiones_Mias"]
    assert [g for g in storage.get_groups(type_filter=None) if g['type'] == 'shadow'] == []

    corte.aplicar_corte(forzar=True, hoy=HOY)
    assert neutralizacion.serie(corte._pagos_de_grupos(['fixed']), fechas) == antes, \
        "el patrimonio se duplicó"


# ── Después del corte: mantener los pagos al día ─────────────────────────────
#
# El corte es de una sola vez; regenerar es la operación de todos los días. Lo que la hace
# segura de correr es que **es idempotente**: sin cambios en las posiciones, la serie no se
# mueve ni un día. Si eso deja de cumplirse, correr la actualización rutinaria empieza a
# desplazar el patrimonio histórico solita, y nadie lo notaría.

def _nueva_posicion(grupo_id, apertura, cierre, capital, interes):
    svc.create_position({
        "portafolio_id": grupo_id, "tipo": "plazo_fijo", "origen": "detectado",
        "fecha_apertura": apertura, "fecha_cierre": cierre,
        "movimientos": [
            {"fecha": apertura, "tipo": "aporte", "monto": capital},
            {"fecha": cierre, "tipo": "retiro", "monto": capital},
            {"fecha": cierre, "tipo": "interes", "monto": interes},
        ],
    })


@pytest.fixture
def cortado(escenario, storage):
    """Un portafolio ya migrado, con su saldo inicial configurado.

    Lo segundo no es decorado: tras el corte no quedan pagos a mano de los que deducir el
    residual de partida, así que `grupos.csv` es la única fuente. Sin él, regenerar se
    niega — ver `test_regenerar_exige_el_saldo_inicial_configurado`.
    """
    corte.sembrar_sombra()
    corte.aplicar_corte(forzar=True, hoy=HOY)
    assert corte.estado()['cortado'] is True
    svc.configurar_saldo_inicial(escenario['id'], 10000.0)
    return escenario


def test_regenerar_sin_cambios_no_mueve_la_serie(cortado, storage):
    """El invariante que hace seguro correrlo por rutina."""
    fechas = [date(2024, 12, 1), date(2025, 2, 1), date(2025, 5, 1)]
    antes = neutralizacion.serie(corte._pagos_de_grupos(['fixed']), fechas)
    pagos_antes = len(storage.get_payments(corte._grupo_generado_activo(cortado['id'])['id']))

    previa = corte.previsualizar_regeneracion(hoy=HOY)
    assert previa['sin_cambios'] is True

    resultado = corte.regenerar(hoy=HOY)

    assert resultado['ok'] is True
    grupo = corte._grupo_generado_activo(cortado['id'])
    assert len(storage.get_payments(grupo['id'])) == pagos_antes
    assert neutralizacion.serie(corte._pagos_de_grupos(['fixed']), fechas) == antes


def test_regenerar_recoge_una_inversion_nueva(cortado, storage):
    """Para esto existe: el certificado nuevo tiene que llegar al patrimonio."""
    _nueva_posicion(cortado['id'], "2025-04-10", "2025-05-10", 10200.0, 300.0)

    previa = corte.previsualizar_regeneracion(hoy=HOY)
    assert previa['sin_cambios'] is False
    assert previa['por_portafolio'][0]['dias_que_cambian'] > 0

    corte.regenerar(hoy=HOY)

    # Mientras el CDT nuevo está abierto, el residual del portafolio es cero.
    dentro = neutralizacion.serie(corte._pagos_de_grupos(['fixed']), [date(2025, 4, 20)])
    assert dentro == [0.0]
    # Y al vencer vuelve, con su interés.
    fuera = neutralizacion.serie(corte._pagos_de_grupos(['fixed']), [date(2025, 5, 20)])
    assert fuera == [10500.0]


def test_regenerar_es_idempotente_tambien_despues_de_un_cambio(cortado, storage):
    _nueva_posicion(cortado['id'], "2025-04-10", "2025-05-10", 10200.0, 300.0)
    corte.regenerar(hoy=HOY)

    fechas = [date(2025, 4, 20), date(2025, 5, 20)]
    primera = neutralizacion.serie(corte._pagos_de_grupos(['fixed']), fechas)
    corte.regenerar(hoy=HOY)

    assert neutralizacion.serie(corte._pagos_de_grupos(['fixed']), fechas) == primera
    assert corte.previsualizar_regeneracion(hoy=HOY)['sin_cambios'] is True


def test_regenerar_no_crea_grupos(cortado, storage):
    """Reemplaza en su sitio. Es lo que lo distingue de sembrar otra sombra."""
    antes = sorted(g['id'] for g in storage.get_groups(type_filter=None))
    _nueva_posicion(cortado['id'], "2025-04-10", "2025-05-10", 10200.0, 300.0)
    corte.regenerar(hoy=HOY)

    assert sorted(g['id'] for g in storage.get_groups(type_filter=None)) == antes


def test_regenerar_conserva_el_tramo_del_saldo_inicial(cortado, storage):
    """`preview()` deduce el arranque de los pagos a mano, y tras el corte no queda ninguno.

    Sin `_arranques_vigentes()` el tramo más viejo de cada portafolio —el del saldo
    inicial— desaparecería en la primera regeneración, y es justo el que nadie miraría.
    """
    grupo = corte._grupo_generado_activo(cortado['id'])
    inicio_antes = min(p['start_date'] for p in storage.get_payments(grupo['id'])
                       if p['start_date'])

    corte.regenerar(hoy=HOY)

    inicio_despues = min(p['start_date'] for p in storage.get_payments(grupo['id'])
                         if p['start_date'])
    assert inicio_despues == inicio_antes


def test_regenerar_se_niega_si_el_portafolio_no_esta_cortado(escenario, storage):
    """Sin corte hay dos fuentes compitiendo, y esa es la migración, no la rutina."""
    resultado = corte.regenerar(hoy=HOY)

    assert resultado['ok'] is False
    assert "no está cortado" in resultado['error']


def test_regenerar_exige_el_saldo_inicial_configurado(escenario, storage):
    """Sin él la pérdida sería muda, que es lo peor que puede pasar aquí.

    Antes del corte el residual de partida se deducía de los pagos a mano. El corte los
    borra, así que el generador arrancaría de cero y la serie se hundiría el importe del
    saldo inicial — y el tramo más viejo del portafolio, el que nadie mira, desaparecería
    sin que nada lo avisara.
    """
    corte.sembrar_sombra()
    corte.aplicar_corte(forzar=True, hoy=HOY)   # sin configurar el saldo

    fechas = [date(2024, 12, 1), date(2025, 5, 1)]
    antes = neutralizacion.serie(corte._pagos_de_grupos(['fixed']), fechas)

    resultado = corte.regenerar(hoy=HOY)

    assert resultado['ok'] is False
    assert "saldo_inicial" in resultado['error']
    assert neutralizacion.serie(corte._pagos_de_grupos(['fixed']), fechas) == antes, \
        "se negó, así que no puede haber tocado nada"

    # Y en cuanto se configura, funciona.
    svc.configurar_saldo_inicial(escenario['id'], 10000.0)
    assert corte.regenerar(hoy=HOY)['ok'] is True
    assert neutralizacion.serie(corte._pagos_de_grupos(['fixed']), fechas) == antes
