"""
test_fund_ciclos.py — El fondo repartido por ciclos: pertenencia y resumen.

Reproduce el caso que motivó la función, medido sobre los datos reales del fondo Comida:
el mensual llegaba el 22, febrero de 2026 no tuvo ingreso, y el crédito sobrante del
ingreso del 22 de enero acababa pagando gastos del 23 y el 26 de febrero.
"""
from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest


@pytest.fixture
def entorno(tmp_path):
    """Storage de grupos y ciclos en tmp_path, sin transacciones reales detrás."""
    with patch("contabilidad.backend.storage.variables_storage.GROUPS_FILE",
               str(tmp_path / "grupos.csv")), \
         patch("contabilidad.backend.storage.variables_storage.PAYMENTS_FILE",
               str(tmp_path / "pagos.csv")), \
         patch("contabilidad.backend.storage.variables_storage.BASE_DATA_PATH",
               str(tmp_path)), \
         patch("contabilidad.backend.storage.ciclos_storage.CICLOS_FILE",
               str(tmp_path / "ciclos.csv")), \
         patch("contabilidad.backend.services.fund_service.load_data",
               return_value=pd.DataFrame()):
        from contabilidad.backend.services import fund_service
        from contabilidad.backend.storage.variables_storage import InterpolationStorage
        yield fund_service, InterpolationStorage


def _mov(id_, fecha, monto):
    return {'id': id_, 'date': fecha, 'amount': monto, 'note': id_,
            'source': 'transaction', 'reviewed': True}


MOVIMIENTOS = [
    _mov('ingreso_enero', date(2026, 1, 22), 80.0),
    _mov('gasto_enero', date(2026, 1, 25), -30.0),
    _mov('gasto_feb_23', date(2026, 2, 23), -3.25),
    _mov('gasto_feb_26', date(2026, 2, 26), -4.0),
    _mov('ingreso_atrasado', date(2026, 3, 3), 70.0),
]


def _preparar(fund_service, storage, **config):
    grupo = storage.create_group('Comida', 'test', group_type='fixed', es_fondo=True,
                                 **config)
    movs = [dict(m) for m in MOVIMIENTOS]
    ciclos = fund_service._asegurar_ciclos(grupo, movs)
    for m in movs:
        ciclo = fund_service.ciclo_de_fecha(ciclos, m['date']) if ciclos else None
        m['ciclo_id'] = ciclo['id'] if ciclo else None
    return grupo, movs, ciclos


def test_un_fondo_sin_migrar_no_genera_ciclos(entorno):
    """`ciclo` vacío = `ingreso`: se comporta igual que antes de que esto existiera."""
    fund_service, storage = entorno
    _, movs, ciclos = _preparar(fund_service, storage)

    assert ciclos == []
    assert all(m['ciclo_id'] is None for m in movs)


def test_enero_no_puede_pagar_febrero(entorno):
    fund_service, storage = entorno
    _, movs, _ = _preparar(fund_service, storage, ciclo='mensual', dia_corte_default=22)

    por_id = {m['id']: m['ciclo_id'] for m in movs}
    assert por_id['ingreso_enero'] != por_id['gasto_feb_26']
    assert por_id['gasto_feb_23'] == por_id['gasto_feb_26']


def test_el_sobrante_de_un_ciclo_se_queda_en_su_ciclo(entorno):
    """Sin arrastre: los $50 que sobran de enero son ahorro, no financian febrero."""
    fund_service, storage = entorno
    _, movs, ciclos = _preparar(fund_service, storage, ciclo='mensual', dia_corte_default=22)

    resumen = {r['inicio']: r for r in fund_service._resumir_ciclos(ciclos, movs)}
    enero = resumen['2026-01-22']
    assert enero['credito'] == 80.0
    assert enero['gasto'] == 30.0
    assert enero['sobrante'] == 50.0
    assert enero['sin_cubrir'] == 0.0


def test_el_ingreso_atrasado_cae_en_el_ciclo_de_febrero(entorno):
    """Con corte el 22, el mensual que llega el 3 de marzo todavía es el de febrero."""
    fund_service, storage = entorno
    _, movs, ciclos = _preparar(fund_service, storage, ciclo='mensual', dia_corte_default=22)

    resumen = {r['inicio']: r for r in fund_service._resumir_ciclos(ciclos, movs)}
    febrero = resumen['2026-02-22']
    assert febrero['credito'] == 70.0
    assert febrero['gasto'] == 7.25
    assert febrero['sin_cubrir'] == 0.0


def test_un_ciclo_sin_ingreso_queda_sin_cubrir(entorno):
    """El síntoma que antes se tapaba: ahora el mes seco lo dice."""
    fund_service, storage = entorno
    grupo = storage.create_group('Seco', '', group_type='fixed', es_fondo=True,
                                 ciclo='mensual', dia_corte_default=22)
    movs = [
        dict(_mov('ingreso', date(2026, 1, 22), 40.0)),
        dict(_mov('gasto_enero', date(2026, 1, 30), -10.0)),
        dict(_mov('gasto_febrero', date(2026, 2, 25), -12.0)),
    ]
    ciclos = fund_service._asegurar_ciclos(grupo, movs)
    for m in movs:
        ciclo = fund_service.ciclo_de_fecha(ciclos, m['date'])
        m['ciclo_id'] = ciclo['id'] if ciclo else None

    resumen = {r['inicio']: r for r in fund_service._resumir_ciclos(ciclos, movs)}
    febrero = resumen['2026-02-22']
    assert febrero['credito'] == 0.0
    assert febrero['gasto'] == 12.0
    assert febrero['sin_cubrir'] == 12.0, "sin ingreso, el gasto queda al descubierto"

    enero = resumen['2026-01-22']
    assert enero['sobrante'] == 30.0, "y el sobrante de enero sigue siendo de enero"


def test_los_ciclos_llegan_hasta_hoy(entorno):
    """El ciclo en curso tiene que existir aunque este mes no haya pasado nada."""
    fund_service, storage = entorno
    _, _, ciclos = _preparar(fund_service, storage, ciclo='mensual', dia_corte_default=22)

    hoy = date.today().isoformat()
    assert any(c['inicio'] <= hoy < c['fin'] for c in ciclos)
    for anterior, siguiente in zip(ciclos, ciclos[1:]):
        assert anterior['fin'] == siguiente['inicio']


def test_el_resumen_marca_el_ciclo_en_curso(entorno):
    fund_service, storage = entorno
    _, movs, ciclos = _preparar(fund_service, storage, ciclo='mensual', dia_corte_default=22)

    resumen = fund_service._resumir_ciclos(ciclos, movs)
    assert sum(1 for r in resumen if r['en_curso']) == 1
