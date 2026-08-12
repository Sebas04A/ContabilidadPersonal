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


def test_un_tramo_abierto_no_se_escribe_con_end_date_vacio(escenario, storage):
    """Si se escribiera vacío, `get_payments()` lo descartaría y el pago sería invisible.

    Es el mismo defecto de las filas fantasma que hubo que limpiar a mano: sin una de las
    dos fechas la fila desaparece del dashboard *y* de la UI. El generador emite el último
    tramo de cada portafolio sin fin, así que sin la centinela el corte perdería justo el
    tramo vigente.
    """
    corte.sembrar_sombra()
    sombra = [g for g in storage.get_groups(type_filter=None) if g['type'] == 'shadow'][0]

    pagos = storage.get_payments(sombra['id'])
    assert all(p['end_date'] is not None for p in pagos)
    assert any(p['end_date'].isoformat() == corte.FECHA_CENTINELA for p in pagos)
    # Y sobre todo: ninguno se pierde por el camino.
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
