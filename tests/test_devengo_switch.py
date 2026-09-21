"""
test_devengo_switch.py — El interruptor de devengo

Lo que se prueba, en orden de importancia:
  1. **Apagado, nada se mueve.** Es la invariante I2 del plan.
  2. El descuento a las liquidaciones es proporcional: ni se pierde plata ni se
     cuenta dos veces, decida el usuario devengar lo que decida.
"""
import pandas as pd
import pytest
from unittest.mock import patch

from contabilidad.backend.services import debt_expenses
from contabilidad.backend.services.debt_expenses import COLUMNAS, aplicar_devengo

CENA = "deuda-devengada-1"
TAXI = "deuda-devengada-2"
OTRA = "deuda-sin-devengar"
PAGO = "pago-1"


def ledger(filas):
    """Un ledger mínimo con las columnas que mira el devengo."""
    base = {c: None for c in COLUMNAS}
    return pd.DataFrame([{**base, **f} for f in filas])


def devengadas(*ids):
    if not ids:
        return pd.DataFrame(columns=COLUMNAS)
    base = {c: None for c in COLUMNAS}
    return pd.DataFrame([
        {**base, 'id': i, 'FECHA': pd.Timestamp('2026-09-06'), 'DESCRIPCION': i,
         'MONTO': -10.0, 'TIPO': 'DEUDA'}
        for i in ids
    ])


def con(devengadas_df, detalles):
    return (
        patch.object(debt_expenses, 'cargar_deudas_devengadas', return_value=devengadas_df),
        patch.object(debt_expenses, '_detalles_por_pago', return_value=detalles),
    )


def aplicar(df, devengadas_df, detalles):
    p1, p2 = con(devengadas_df, detalles)
    with p1, p2:
        return aplicar_devengo(df)


# ── I2: apagado, nada se mueve ───────────────────────────────────────────────

def test_sin_deudas_devengadas_el_ledger_no_cambia():
    df = ledger([
        {'id': 'tx1', 'FECHA': pd.Timestamp('2026-09-10'), 'MONTO': -25.0, 'TIPO': 'BANCA', 'pago_id': PAGO},
        {'id': 'tx2', 'FECHA': pd.Timestamp('2026-09-11'), 'MONTO': -8.0, 'TIPO': 'BANCA'},
    ])
    out, resumen = aplicar(df, devengadas(), {PAGO: [(OTRA, 25.0)]})

    pd.testing.assert_frame_equal(out, df)
    assert resumen['deudas_devengadas'] == 0
    assert resumen['monto_descontado'] == 0.0


def test_load_data_por_defecto_no_devenga():
    """El default es lo que protege al dashboard, a los fondos y a los drivers."""
    from contabilidad.backend.services import transaction_service

    llamadas = []
    with patch.object(transaction_service, '_load_data_caja', return_value=pd.DataFrame()), \
         patch.object(debt_expenses, 'aplicar_devengo', side_effect=lambda df: llamadas.append(1)):
        transaction_service.load_data()

    assert llamadas == [], "load_data() sin argumentos no puede tocar el devengo"


# ── Entran las deudas ────────────────────────────────────────────────────────

def test_la_deuda_devengada_entra_como_gasto():
    df = ledger([{'id': 'tx1', 'FECHA': pd.Timestamp('2026-09-10'), 'MONTO': -8.0, 'TIPO': 'BANCA'}])
    out, resumen = aplicar(df, devengadas(CENA), {})

    assert len(out) == 2
    fila = out[out['TIPO'] == 'DEUDA'].iloc[0]
    assert fila['MONTO'] == -10.0
    assert resumen['deudas_devengadas'] == 1
    assert resumen['monto_devengado'] == 10.0


# ── Salen las liquidaciones, en su justa medida ──────────────────────────────

def test_la_liquidacion_de_una_deuda_devengada_deja_de_contar():
    """Pagué $10 por la cena que ya conté como gasto: devolverla no es gastar otra vez."""
    df = ledger([{'id': 'tx1', 'FECHA': pd.Timestamp('2026-09-12'), 'MONTO': -10.0,
                  'TIPO': 'BANCA', 'pago_id': PAGO}])
    out, resumen = aplicar(df, devengadas(CENA), {PAGO: [(CENA, 10.0)]})

    liq = out[out['id'] == 'tx1'].iloc[0]
    assert liq['MONTO'] == 0.0
    assert resumen['monto_descontado'] == 10.0


def test_una_liquidacion_mixta_solo_pierde_la_parte_ya_contada():
    """
    El caso que obliga a que el descuento sea proporcional: un pago de $25 que
    salda una deuda devengada ($10) y una que no ($15). Si se descontara entero,
    esos $15 de consumo real desaparecerían del análisis.
    """
    df = ledger([{'id': 'tx1', 'FECHA': pd.Timestamp('2026-09-12'), 'MONTO': -25.0,
                  'TIPO': 'BANCA', 'pago_id': PAGO}])
    out, resumen = aplicar(df, devengadas(CENA), {PAGO: [(CENA, 10.0), (OTRA, 15.0)]})

    assert out[out['id'] == 'tx1'].iloc[0]['MONTO'] == pytest.approx(-15.0)
    assert resumen['monto_descontado'] == pytest.approx(10.0)


def test_un_pago_vinculado_a_dos_transacciones_reparte_el_descuento():
    """
    El mismo pago aparece en dos transacciones de $10. Salda una deuda devengada
    ($10) y una que no ($10): hay que descontar $10 **en total**, no $10 a cada
    una. Si se aplicara entero a cada fila, el gasto bajaría $20 de la nada.
    """
    df = ledger([
        {'id': 'tx1', 'FECHA': pd.Timestamp('2026-09-12'), 'MONTO': -10.0, 'TIPO': 'BANCA', 'pago_id': PAGO},
        {'id': 'tx2', 'FECHA': pd.Timestamp('2026-09-12'), 'MONTO': -10.0, 'TIPO': 'BANCA', 'pago_id': PAGO},
    ])
    out, resumen = aplicar(df, devengadas(CENA), {PAGO: [(CENA, 10.0), (OTRA, 10.0)]})

    montos = sorted(out[out['TIPO'] == 'BANCA']['MONTO'])
    assert montos == pytest.approx([-5.0, -5.0])
    assert resumen['monto_descontado'] == pytest.approx(10.0)


def test_si_todo_el_pago_saldaba_deudas_devengadas_no_queda_gasto():
    df = ledger([
        {'id': 'tx1', 'FECHA': pd.Timestamp('2026-09-12'), 'MONTO': -10.0, 'TIPO': 'BANCA', 'pago_id': PAGO},
        {'id': 'tx2', 'FECHA': pd.Timestamp('2026-09-12'), 'MONTO': -10.0, 'TIPO': 'BANCA', 'pago_id': PAGO},
    ])
    out, resumen = aplicar(df, devengadas(CENA, TAXI), {PAGO: [(CENA, 10.0), (TAXI, 10.0)]})

    assert list(out[out['TIPO'] == 'BANCA']['MONTO']) == pytest.approx([0.0, 0.0])
    assert resumen['monto_descontado'] == pytest.approx(20.0)


def test_nunca_se_descuenta_mas_de_lo_que_hay():
    """El cruce puede saldar más de lo que la transferencia movió; el gasto no baja de cero."""
    df = ledger([{'id': 'tx1', 'FECHA': pd.Timestamp('2026-09-12'), 'MONTO': -5.0,
                  'TIPO': 'BANCA', 'pago_id': PAGO}])
    out, _ = aplicar(df, devengadas(CENA), {PAGO: [(CENA, 40.0)]})

    assert out[out['id'] == 'tx1'].iloc[0]['MONTO'] == 0.0


def test_un_cobro_recibido_tambien_se_ajusta():
    """Que me devuelvan plata no es un ingreso: el signo no cambia la regla."""
    df = ledger([{'id': 'tx1', 'FECHA': pd.Timestamp('2026-09-12'), 'MONTO': 10.0,
                  'TIPO': 'BANCA', 'pago_id': PAGO}])
    out, _ = aplicar(df, devengadas(CENA), {PAGO: [(CENA, 10.0)]})

    assert out[out['id'] == 'tx1'].iloc[0]['MONTO'] == 0.0


def test_sin_detalle_de_pago_no_se_inventa_el_ajuste():
    """Si Supabase no contesta, mejor el número de hoy que uno inventado. Y se dice."""
    df = ledger([{'id': 'tx1', 'FECHA': pd.Timestamp('2026-09-12'), 'MONTO': -10.0,
                  'TIPO': 'BANCA', 'pago_id': PAGO}])
    out, resumen = aplicar(df, devengadas(CENA), {})

    assert out[out['id'] == 'tx1'].iloc[0]['MONTO'] == -10.0
    assert resumen['liquidaciones_sin_detalle'] == 1


def test_una_transaccion_sin_pago_id_no_se_toca():
    df = ledger([{'id': 'tx1', 'FECHA': pd.Timestamp('2026-09-12'), 'MONTO': -30.0, 'TIPO': 'BANCA'}])
    out, _ = aplicar(df, devengadas(CENA), {PAGO: [(CENA, 10.0)]})

    assert out[out['id'] == 'tx1'].iloc[0]['MONTO'] == -30.0


# ── La ruta ──────────────────────────────────────────────────────────────────

def _cliente():
    from fastapi.testclient import TestClient
    from contabilidad.backend.main import app
    return TestClient(app)


def test_la_ruta_pide_caja_por_defecto():
    with patch('contabilidad.backend.routes.transactions.load_data',
               return_value=pd.DataFrame()) as cargar:
        _cliente().get("/api/transactions/")
    assert cargar.call_args.kwargs == {'devengo': False}


def test_la_ruta_pide_devengo_cuando_se_lo_piden():
    with patch('contabilidad.backend.routes.transactions.load_data',
               return_value=pd.DataFrame()) as cargar:
        _cliente().get("/api/transactions/", params={"devengo": True})
    assert cargar.call_args.kwargs == {'devengo': True}


def test_el_resumen_se_puede_pedir_sin_las_transacciones():
    resumen = {'deudas_devengadas': 2, 'monto_devengado': 56.31, 'liquidaciones_ajustadas': 0,
               'monto_descontado': 0.0, 'liquidaciones_sin_detalle': 0}
    from contabilidad.backend.services import transaction_service
    with patch.object(transaction_service, 'load_data_devengo', return_value=(pd.DataFrame(), resumen)):
        r = _cliente().get("/api/transactions/devengo/resumen")
    assert r.status_code == 200
    assert r.json() == resumen


# ── El saldo de la deuda viaja con la fila ───────────────────────────────────

def test_el_saldo_de_la_deuda_sobrevive_al_concat():
    """
    El ledger de caja no tiene `SALDO_DEUDA`, y el `concat` selecciona por las
    columnas de `df`: sin abrirla del otro lado, la columna se perdería justo en
    el camino que la necesita.
    """
    from contabilidad.backend.services.debt_expenses import COLUMNA_SALDO

    df = ledger([
        {'id': 'tx1', 'FECHA': pd.Timestamp('2026-09-10'), 'MONTO': -25.0, 'TIPO': 'BANCA'},
    ]).drop(columns=[COLUMNA_SALDO])

    dev = devengadas(CENA)
    dev[COLUMNA_SALDO] = 10.0

    out, _ = aplicar(df, dev, {})

    assert out.loc[out['TIPO'] == 'DEUDA', COLUMNA_SALDO].iloc[0] == 10.0
    # En una transacción de banca la columna existe pero está vacía: no hay deuda
    # detrás, y un 0 ahí se leería como "deuda saldada", que es otra cosa.
    assert pd.isna(out.loc[out['TIPO'] == 'BANCA', COLUMNA_SALDO].iloc[0])


def test_el_saldo_ausente_se_serializa_como_null_y_no_como_nan():
    """
    `json.dumps` rechaza NaN con un 500, y en modo devengo toda fila de banca
    tiene la columna vacía. Sin esto, el Explorador no cargaba ni una vez.
    """
    import json
    from contabilidad.backend.services.debt_expenses import COLUMNA_SALDO
    from contabilidad.backend.utils.json_utils import sanitize_for_json

    df = ledger([
        {'id': 'tx1', 'FECHA': pd.Timestamp('2026-09-10'), 'MONTO': -25.0, 'TIPO': 'BANCA'},
        {'id': 'd1', 'FECHA': pd.Timestamp('2026-09-06'), 'MONTO': -10.0, 'TIPO': 'DEUDA'},
    ])
    df[COLUMNA_SALDO] = [float('nan'), 10.0]

    limpio = sanitize_for_json(df)
    # La ruta formatea la fecha después de sanear; acá solo estorba.
    limpio['FECHA'] = limpio['FECHA'].dt.strftime('%Y-%m-%d')
    filas = limpio.to_dict(orient='records')
    json.dumps(filas, allow_nan=False)  # revienta si queda un NaN

    assert filas[0][COLUMNA_SALDO] is None
    assert filas[1][COLUMNA_SALDO] == 10.0
