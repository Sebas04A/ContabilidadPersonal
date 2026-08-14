"""
test_dashboard_filters.py — Tests del filtro a nivel transacción del dashboard.

Dos capas:
  1. `TxFilter`: los predicados, que tienen que responder igual que los del
     presupuesto en MonthlyBudget.tsx.
  2. `_descontar_filtrado`: la aritmética del descuento sobre las series diarias.

Todo con datos sintéticos: estos tests no pueden depender de los CSV reales, o
dejarían de correr en otra máquina y avisarían de cambios en los datos en vez de
cambios en el código.
"""
import pandas as pd
import pytest

from contabilidad.backend.services.dashboard_filters import TxFilter, filtro_desde_query


def _tx(**kw):
    """Una transacción con todos los campos que mira el filtro."""
    fila = {
        'id': 'x', 'FECHA': '2025-01-15', 'DESCRIPCION': 'algo', 'MONTO': -10.0,
        'TIPO': 'BANCA', 'categoria': 'Ocio', 'tags': '', 'prioridad': '',
        'es_reembolsable': False, 'revisado': True, 'fondo_id': None,
    }
    fila.update(kw)
    return fila


def _df(*filas):
    return pd.DataFrame(list(filas))


# ── Filtro inerte ─────────────────────────────────────────────────────────────

def test_filtro_vacio_no_esta_activo():
    assert not TxFilter().activo()


def test_filtro_vacio_devuelve_todo_sin_copiar():
    df = _df(_tx(), _tx(categoria='Salud'))
    assert TxFilter().aplicar(df) is df


def test_lista_de_fondos_vacia_si_activa_el_filtro():
    """[] significa 'ningún fondo', que no es lo mismo que None ('todos')."""
    assert TxFilter(fondos=[]).activo()
    assert not TxFilter(fondos=None).activo()


# ── Categorías ────────────────────────────────────────────────────────────────

def test_excluye_categoria():
    df = _df(_tx(categoria='Ocio'), _tx(categoria='Salud'))
    r = TxFilter(categorias_excluidas=['Ocio']).aplicar(df)
    assert list(r['categoria']) == ['Salud']


@pytest.mark.parametrize('valor', ['', '---', None, 'nan'])
def test_sin_categoria_agrupa_los_vacios(valor):
    """Igual que el presupuesto: vacío, '---' y NaN son todos 'Sin Categoría'."""
    df = _df(_tx(categoria=valor), _tx(categoria='Salud'))
    r = TxFilter(categorias_excluidas=['Sin Categoría']).aplicar(df)
    assert list(r['categoria']) == ['Salud']


# ── Tags ──────────────────────────────────────────────────────────────────────

def test_excluye_por_tag_suelto():
    df = _df(_tx(tags='viaje, comida'), _tx(tags='comida'))
    r = TxFilter(tags_excluidos=['viaje']).aplicar(df)
    assert list(r['tags']) == ['comida']


def test_tag_no_matchea_por_substring():
    """'via' no debe sacar a 'viaje': los tags se comparan enteros."""
    df = _df(_tx(tags='viaje'))
    assert len(TxFilter(tags_excluidos=['via']).aplicar(df)) == 1


def test_sin_etiqueta_saca_las_que_no_tienen_tags():
    df = _df(_tx(tags=''), _tx(tags='comida'))
    r = TxFilter(tags_excluidos=['Sin Etiqueta']).aplicar(df)
    assert list(r['tags']) == ['comida']


# ── Prioridad ─────────────────────────────────────────────────────────────────

def test_prioridad_no_toca_los_ingresos():
    """Los ingresos no se clasifican como necesidad/deseo y deben pasar siempre
    (espejo de matchesPriority en MonthlyBudget.tsx:95)."""
    df = _df(
        _tx(MONTO=100.0, prioridad=''),        # ingreso sin clasificar
        _tx(MONTO=-10.0, prioridad='Deseo'),   # gasto que no es necesidad
    )
    r = TxFilter(prioridad='needs').aplicar(df)
    assert list(r['MONTO']) == [100.0]


def test_prioridad_rated_pide_cualquiera_de_las_dos():
    df = _df(
        _tx(MONTO=-1.0, prioridad='Necesidad'),
        _tx(MONTO=-2.0, prioridad='Deseo'),
        _tx(MONTO=-3.0, prioridad=''),
    )
    r = TxFilter(prioridad='rated').aplicar(df)
    assert sorted(r['MONTO']) == [-2.0, -1.0]


# ── Reembolsable y etiquetado ─────────────────────────────────────────────────

@pytest.mark.parametrize('crudo,esperado', [
    (True, True), ('True', True), ('true', True), ('si', True), ('1', True),
    (False, False), ('False', False), (None, False), (float('nan'), False),
])
def test_booleanos_de_etiquetas_csv(crudo, esperado):
    """etiquetas.csv devuelve bool, texto o NaN según cómo se escribió la fila."""
    df = _df(_tx(es_reembolsable=crudo))
    quedan = len(TxFilter(reembolsable='included').aplicar(df))
    assert bool(quedan) is esperado


def test_solo_no_etiquetadas():
    df = _df(_tx(revisado=True), _tx(revisado=False))
    r = TxFilter(etiquetado='unlabeled').aplicar(df)
    assert list(r['revisado']) == [False]


# ── Fondos ────────────────────────────────────────────────────────────────────

CATALOGO = [
    {'id': 'f1', 'tag_vinculado': 'Gasolina'},
    {'id': 'f2', 'tag_vinculado': None},
]


def test_lo_que_no_es_de_ningun_fondo_siempre_pasa(monkeypatch):
    """Regla del presupuesto: el filtro de fondos acota, no esconde el resto."""
    monkeypatch.setattr(
        'contabilidad.backend.services.dashboard_filters._catalogo_de_fondos',
        lambda: CATALOGO,
    )
    df = _df(_tx(id='libre'), _tx(id='deF1', tags='Gasolina'))
    r = TxFilter(fondos=[]).aplicar(df)
    assert list(r['id']) == ['libre']


def test_fondo_por_tag_ignora_tildes_y_mayusculas(monkeypatch):
    monkeypatch.setattr(
        'contabilidad.backend.services.dashboard_filters._catalogo_de_fondos',
        lambda: [{'id': 'f1', 'tag_vinculado': 'Alimentación'}],
    )
    df = _df(_tx(id='a', tags='alimentacion'))
    assert len(TxFilter(fondos=[]).aplicar(df)) == 0
    assert len(TxFilter(fondos=['f1']).aplicar(df)) == 1


def test_fondo_id_explicito_gana(monkeypatch):
    monkeypatch.setattr(
        'contabilidad.backend.services.dashboard_filters._catalogo_de_fondos',
        lambda: CATALOGO,
    )
    df = _df(_tx(id='a', fondo_id='f2'))
    assert len(TxFilter(fondos=['f2']).aplicar(df)) == 1
    assert len(TxFilter(fondos=['f1']).aplicar(df)) == 0


# ── Serialización desde query params ──────────────────────────────────────────

def test_fondos_ausente_es_todos_y_vacio_es_ninguno():
    """La distinción importa: None no filtra, [] deja solo lo que no es de fondo."""
    assert filtro_desde_query().fondos is None
    assert filtro_desde_query(fondos='').fondos == []
    assert filtro_desde_query(fondos='a,b').fondos == ['a', 'b']


def test_firma_es_estable_ante_el_orden():
    a = filtro_desde_query(categorias_excluidas='Ocio,Salud')
    b = filtro_desde_query(categorias_excluidas='Salud,Ocio')
    assert a.firma() == b.firma()


# ── Aritmética del descuento sobre las series diarias ─────────────────────────
#
# La parte con más filo: si esto se corre un día o invierte un signo, el
# patrimonio del gráfico miente sin que nada falle. Todo sintético y con el
# mínimo de mocks para que el cálculo quede a la vista.

from unittest.mock import patch, MagicMock


EJE = pd.date_range('2025-01-01', '2025-01-05', freq='D')


def _master():
    """Cinco días de eje con saldo y deuda planos, para que cualquier movimiento
    de las series sea atribuible al filtro y no al dato de fondo."""
    return pd.DataFrame({
        'FECHA': EJE,
        'SALDO': [1000.0] * 5,
        'TARJETA': [200.0] * 5,
        'ACUMULADO_TARJETA': [200.0] * 5,
    })


def _servicio():
    from contabilidad.backend.services.dashboard_service import DashboardService
    s = DashboardService()
    s.pipeline = MagicMock()
    s.pipeline.get_raw_data.return_value = pd.DataFrame(columns=['id', 'FECHA', 'DESCRIPCION', 'DEBITO'])
    return s


def _descontar(df_tx, tx_filter, anchor='2025-01-01', pagos=()):
    s = _servicio()
    with patch('contabilidad.backend.services.transaction_service.load_data', return_value=df_tx), \
         patch('contabilidad.backend.storage.transformations.credit_cards.get_card_anchor',
               return_value=(pd.Timestamp(anchor), 0.0)), \
         patch('contabilidad.backend.services.bank_parser.get_variables.get_credit_card_payments',
               return_value=list(pagos)):
        return s._descontar_filtrado(_master(), tx_filter)


def test_gasto_de_banca_excluido_sube_el_saldo_desde_su_fecha():
    """Un gasto que sale del filtro es plata que no se fue: el saldo sube, y solo
    a partir del día en que había ocurrido."""
    df_tx = _df(_tx(id='a', FECHA='2025-01-03', MONTO=-50.0, categoria='Ocio'))
    out, resumen = _descontar(df_tx, TxFilter(categorias_excluidas=['Ocio']))

    assert list(out['SALDO']) == [1000.0, 1000.0, 1050.0, 1050.0, 1050.0]
    assert resumen['excluidas_banca'] == 1
    assert resumen['monto_excluido_banca'] == -50.0


def test_ingreso_de_banca_excluido_baja_el_saldo():
    df_tx = _df(_tx(id='a', FECHA='2025-01-02', MONTO=300.0, categoria='Ocio'))
    out, _ = _descontar(df_tx, TxFilter(categorias_excluidas=['Ocio']))
    assert list(out['SALDO']) == [1000.0, 700.0, 700.0, 700.0, 700.0]


def test_consumo_de_tarjeta_excluido_baja_la_deuda():
    """En tarjeta el consumo viene negativo y la deuda es positiva: VALOR = −MONTO."""
    df_tx = _df(_tx(id='a', TIPO='TARJETA', FECHA='2025-01-03', MONTO=-30.0, categoria='Ocio'))
    out, resumen = _descontar(df_tx, TxFilter(categorias_excluidas=['Ocio']))

    assert list(out['TARJETA']) == [200.0, 200.0, 170.0, 170.0, 170.0]
    assert resumen['consumo_excluido_tarjeta'] == 30.0
    # El saldo del banco no se entera de un consumo de tarjeta.
    assert list(out['SALDO']) == [1000.0] * 5


def test_consumo_anterior_al_ancla_no_se_descuenta():
    """Esa deuda está dentro de initial_balance y la transformación la fuerza a
    cero: descontarla movería una deuda que en el gráfico nunca existió."""
    df_tx = _df(_tx(id='a', TIPO='TARJETA', FECHA='2025-01-01', MONTO=-30.0, categoria='Ocio'))
    out, resumen = _descontar(df_tx, TxFilter(categorias_excluidas=['Ocio']), anchor='2025-01-04')

    assert list(out['TARJETA']) == [200.0] * 5
    assert resumen['excluidas_tarjeta_antes_del_ancla'] == 1
    assert resumen['consumo_excluido_tarjeta'] == 0.0


def test_pago_de_tarjeta_excluido_sube_la_deuda_y_deja_el_patrimonio_quieto():
    """Excluir un pago sube el saldo (no salió la plata) y sube la deuda (nunca se
    canceló). Como TOTAL resta la deuda, el patrimonio no se mueve: pagar la
    tarjeta cambia de bolsillo, no crea ni destruye."""
    pago = MagicMock(start_date='2025-01-02', amount=80.0)
    df_tx = _df(_tx(id='p1', FECHA='2025-01-02', MONTO=-80.0, categoria='Tarjeta'))

    s = _servicio()
    s.pipeline.get_raw_data.return_value = pd.DataFrame([
        {'id': 'p1', 'FECHA': pd.Timestamp('2025-01-02'), 'DESCRIPCION': 'PAGO TARJETA', 'DEBITO': 80.0}
    ])
    with patch('contabilidad.backend.services.transaction_service.load_data', return_value=df_tx), \
         patch('contabilidad.backend.storage.transformations.credit_cards.get_card_anchor',
               return_value=(pd.Timestamp('2025-01-01'), 0.0)), \
         patch('contabilidad.backend.services.bank_parser.get_variables.get_credit_card_payments',
               return_value=[pago]):
        out, resumen = s._descontar_filtrado(_master(), TxFilter(categorias_excluidas=['Tarjeta']))

    assert resumen['pagos_tarjeta_excluidos'] == 80.0
    assert list(out['SALDO']) == [1000.0, 1080.0, 1080.0, 1080.0, 1080.0]
    assert list(out['TARJETA']) == [200.0, 280.0, 280.0, 280.0, 280.0]
    # TOTAL = ... saldo − tarjeta ...: los dos suben 80, el neto es cero.
    neto = (out['SALDO'] - out['TARJETA']) - (1000.0 - 200.0)
    assert list(neto) == [0.0] * 5


def test_filtro_que_no_excluye_nada_deja_las_series_intactas():
    """El contrato de toda la feature: si el filtro no saca nada, no toca nada."""
    df_tx = _df(_tx(id='a', FECHA='2025-01-03', MONTO=-50.0, categoria='Salud'))
    out, resumen = _descontar(df_tx, TxFilter(categorias_excluidas=['Ocio']))

    assert list(out['SALDO']) == [1000.0] * 5
    assert list(out['TARJETA']) == [200.0] * 5
    assert resumen['excluidas_banca'] == 0
