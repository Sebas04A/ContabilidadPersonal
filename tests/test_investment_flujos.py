"""
test_investment_flujos.py — Registrar dinero que entra o sale del portafolio.

Un `flujo` es plata que se va del portafolio y no vuelve —la matrícula que se paga con lo
que devolvió un certificado— o que llega de fuera. Antes esto solo existía como la *fecha
de fin* de un pago fijo, información que el generador de la fase 6 no puede ver: por eso
seguía arrastrando 14.127,67 de `Uni` y 13.982,05 de `Madre` que ya no estaban.

Todo corre contra CSVs en `tmp_path`.
"""
import pytest
from unittest.mock import patch

from contabilidad.backend.services.investments import metricas
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
        from contabilidad.backend.storage.investments_storage import InvestmentStorage
        yield InvestmentStorage


@pytest.fixture
def portafolio(storage):
    from contabilidad.backend.storage.variables_storage import InterpolationStorage
    return InterpolationStorage.create_group(
        name="Inversiones_Uni", group_type="fixed", es_inversion=True, es_custodia=True
    )


def certificado(portafolio_id, apertura="2025-01-10", cierre="2025-04-10",
                capital=10000.0, interes=200.0):
    """Un plazo fijo que se abre y se cierra, como los que detecta el banco."""
    return svc.create_position({
        "portafolio_id": portafolio_id,
        "tipo": "plazo_fijo",
        "origen": "detectado",
        "fecha_apertura": apertura,
        "fecha_cierre": cierre,
        "movimientos": [
            {"fecha": apertura, "tipo": "aporte", "monto": capital},
            {"fecha": cierre, "tipo": "retiro", "monto": capital},
            {"fecha": cierre, "tipo": "interes", "monto": interes},
        ],
    })


# ── Registrar ────────────────────────────────────────────────────────────────

def test_una_salida_es_una_posicion_de_tipo_flujo(portafolio):
    flujo = svc.registrar_flujo(portafolio["id"], "2025-04-28", 3213.74, nota="Matrícula 2025-1")

    assert flujo["tipo"] == "flujo"
    assert flujo["origen"] == "manual"
    assert flujo["capital"] == 3213.74
    assert flujo["nota"] == "Matrícula 2025-1"


def test_un_flujo_es_instantaneo_y_nace_cerrado(portafolio):
    """No es algo pendiente que haya que cerrar después: ya pasó."""
    flujo = svc.registrar_flujo(portafolio["id"], "2025-04-28", 3213.74)

    assert flujo["fecha_apertura"] == flujo["fecha_cierre"] == "2025-04-28"
    assert flujo["estado"] == "cerrada"
    assert flujo["dias"] == 0


def test_una_salida_se_guarda_como_aporte(portafolio):
    """`aporte` saca la plata del bolsillo de inversión: mismo signo que `metricas.SIGNO`."""
    flujo = svc.registrar_flujo(portafolio["id"], "2025-04-28", 3213.74)

    assert [(m["tipo"], m["monto"]) for m in flujo["movimientos"]] == [("aporte", 3213.74)]


def test_una_entrada_se_guarda_como_retiro(portafolio):
    flujo = svc.registrar_flujo(portafolio["id"], "2024-11-18", 3635.07, direccion="entrada")

    assert [(m["tipo"], m["monto"]) for m in flujo["movimientos"]] == [("retiro", 3635.07)]


def test_el_flujo_puede_apuntar_a_la_transaccion_del_banco(portafolio):
    flujo = svc.registrar_flujo(portafolio["id"], "2025-04-28", 3213.74, tx_id="tx-042")

    assert flujo["movimientos"][0]["tx_id"] == "tx-042"


def test_una_direccion_inventada_no_pasa(portafolio):
    with pytest.raises(svc.ValidationError, match="Dirección inválida"):
        svc.registrar_flujo(portafolio["id"], "2025-04-28", 100.0, direccion="lateral")


def test_el_monto_tiene_que_ser_positivo(portafolio):
    """El signo lo da la dirección. Con negativos habría dos formas de escribir lo mismo."""
    with pytest.raises(svc.ValidationError, match="positivo"):
        svc.registrar_flujo(portafolio["id"], "2025-04-28", -3213.74)

    with pytest.raises(svc.ValidationError, match="positivo"):
        svc.registrar_flujo(portafolio["id"], "2025-04-28", 0.0)


def test_una_fecha_ilegible_no_pasa(portafolio):
    with pytest.raises(svc.ValidationError, match="Fecha inválida"):
        svc.registrar_flujo(portafolio["id"], "el martes", 100.0)


def test_un_flujo_sin_portafolio_no_pasa(storage):
    """Un flujo es plata que sale de un portafolio concreto; sin él no significa nada."""
    with pytest.raises(svc.ValidationError, match="necesita portafolio"):
        svc.registrar_flujo("", "2025-04-28", 100.0)


def test_un_portafolio_inexistente_no_pasa(storage):
    with pytest.raises(svc.ValidationError, match="no existe"):
        svc.registrar_flujo("no-existe", "2025-04-28", 100.0)


# ── El efecto sobre el residual ──────────────────────────────────────────────

def residual_generado(portafolio, saldo_inicial=0.0):
    """El residual generado por fecha. Un tramo en cero no emite pago, así que no aparece."""
    from contabilidad.backend.services.investments import neutralizacion
    pagos = [p.to_dict() for p in neutralizacion.generar_pagos(
        svc.list_positions(), [{**portafolio, "saldo_inicial": saldo_inicial}])]
    return {p["start"]: p["amount"] for p in pagos}


def test_sin_registrar_la_salida_el_residual_arrastra_la_plata(portafolio):
    """El bug que motivó todo esto: el generador no ve la matrícula y la sigue contando."""
    certificado(portafolio["id"], capital=10000.0, interes=200.0)

    # Al cerrar vuelven 10.200 al bolsillo y ahí se quedan, según el generador.
    assert residual_generado(portafolio)["2025-04-10"] == 200.0


def test_registrar_la_salida_la_saca_del_residual_para_siempre(portafolio):
    certificado(portafolio["id"], capital=10000.0, interes=200.0)
    svc.registrar_flujo(portafolio["id"], "2025-04-28", 3213.74, nota="Matrícula")

    residual = residual_generado(portafolio)

    assert residual["2025-04-10"] == 200.0
    assert residual["2025-04-28"] == round(200.0 - 3213.74, 2)


def test_una_entrada_sube_el_residual(portafolio):
    certificado(portafolio["id"], capital=10000.0, interes=200.0)
    svc.registrar_flujo(portafolio["id"], "2025-04-28", 1000.0, direccion="entrada")

    assert residual_generado(portafolio)["2025-04-28"] == 1200.0


def test_sin_la_salida_el_ciclo_deja_un_sobrante_que_no_existe(portafolio):
    """El ciclo real de `Uni`: vence, se reinvierte una parte y el resto se va en matrícula.

    Sin registrar la matrícula, el generador cree que esos 3.200 siguen en la cuenta —
    y a partir de ahí los arrastra en todos los tramos siguientes.
    """
    certificado(portafolio["id"], apertura="2025-01-10", cierre="2025-04-10",
                capital=10000.0, interes=200.0)
    certificado(portafolio["id"], apertura="2025-04-10", cierre="2025-08-10",
                capital=7000.0, interes=150.0)

    residual = residual_generado(portafolio, saldo_inicial=10000.0)

    assert residual["2025-04-10"] == 3200.0
    assert residual["2025-08-10"] == 10350.0


def test_con_la_salida_registrada_el_ciclo_cierra_en_cero(portafolio):
    """Mismo ciclo, con la matrícula anotada: el residual no arrastra nada."""
    certificado(portafolio["id"], apertura="2025-01-10", cierre="2025-04-10",
                capital=10000.0, interes=200.0)
    svc.registrar_flujo(portafolio["id"], "2025-04-10", 3200.0, nota="Matrícula")
    certificado(portafolio["id"], apertura="2025-04-10", cierre="2025-08-10",
                capital=7000.0, interes=150.0)

    residual = residual_generado(portafolio, saldo_inicial=10000.0)

    # 10.200 vuelven, 3.200 se van en matrícula, 7.000 se reinvierten: el tramo queda en
    # cero y por eso ni siquiera emite pago.
    assert "2025-04-10" not in residual
    assert residual["2025-08-10"] == 7150.0


# ── Los KPIs ─────────────────────────────────────────────────────────────────

def test_una_salida_no_es_capital_invertido(portafolio):
    """No rinde, no está en un certificado y no se valúa."""
    certificado(portafolio["id"], capital=10000.0, interes=200.0)
    svc.registrar_flujo(portafolio["id"], "2025-04-28", 3213.74)

    kpis = metricas.calcular_kpis(svc.list_positions(), __import__('datetime').date(2025, 12, 31))

    assert kpis["capital_rotado"] == 10000.0
    assert kpis["capital_invertido"] == 0.0
    assert kpis["residual_suelto"] == 0.0


def test_los_kpis_reportan_lo_que_salio_y_lo_que_entro(portafolio):
    certificado(portafolio["id"])
    svc.registrar_flujo(portafolio["id"], "2025-04-28", 3213.74)
    svc.registrar_flujo(portafolio["id"], "2025-05-28", 3267.33)
    svc.registrar_flujo(portafolio["id"], "2025-06-28", 1000.0, direccion="entrada")

    kpis = metricas.calcular_kpis(svc.list_positions(), __import__('datetime').date(2025, 12, 31))

    assert kpis["salidas"] == 6481.07
    assert kpis["entradas"] == 1000.0


def test_una_salida_no_distorsiona_el_xirr(portafolio):
    """Pagar la matrícula no es una decisión de inversión: no puede volverla una pérdida."""
    certificado(portafolio["id"], capital=10000.0, interes=200.0)
    sin_flujo = metricas.calcular_kpis(svc.list_positions(),
                                       __import__('datetime').date(2025, 12, 31))["xirr"]

    svc.registrar_flujo(portafolio["id"], "2025-04-28", 3213.74)
    con_flujo = metricas.calcular_kpis(svc.list_positions(),
                                       __import__('datetime').date(2025, 12, 31))["xirr"]

    assert con_flujo == sin_flujo
    assert con_flujo > 0


def test_un_flujo_no_entra_al_patrimonio(portafolio):
    """La plata que se fue no puede seguir contando como capital tuyo."""
    from contabilidad.backend.services.investments import patrimonio

    svc.registrar_flujo(portafolio["id"], "2025-04-28", 3213.74)

    serie = patrimonio.capital_propio(svc.list_positions(), [portafolio])
    assert all(v == 0.0 for v in serie.values())


# ── El residual antes de registrar ───────────────────────────────────────────

def test_el_residual_del_portafolio_se_puede_consultar(portafolio):
    certificado(portafolio["id"], capital=10000.0, interes=200.0)

    assert svc.residual_portafolio(portafolio["id"], "2025-04-20") == 200.0
    assert svc.residual_portafolio(portafolio["id"], "2025-01-20") == -10000.0


def test_el_residual_usa_la_misma_base_que_la_pantalla_de_neutralizacion(portafolio):
    """Si no, el formulario y la pestaña mostrarían números distintos del mismo día.

    El saldo inicial de `grupos.csv` es 0 mientras nadie lo configure; el que importa es
    el que la neutralización deduce de los pagos escritos a mano.
    """
    from contabilidad.backend.storage.variables_storage import InterpolationStorage
    InterpolationStorage.create_payment(portafolio["id"], 5000.0, "2024-01-01", "2025-01-10")
    certificado(portafolio["id"], capital=10000.0, interes=200.0)

    # Con la siembra de 5.000 deducida: 5.000 − 10.000 + 10.200 = 5.200.
    assert svc.residual_portafolio(portafolio["id"], "2025-04-20") == 5200.0


def test_el_residual_de_un_portafolio_inexistente_es_none(storage):
    assert svc.residual_portafolio("no-existe", "2025-04-20") is None


# ── Que no lo pise el detector ───────────────────────────────────────────────

def test_el_detector_no_reporta_los_flujos_como_sobrantes(portafolio):
    """Nacen `origen='manual'`, y `solo_guardadas` solo mira las detectadas."""
    import pandas as pd

    svc.registrar_flujo(portafolio["id"], "2025-04-28", 3213.74)
    resultado = svc.reconcile(pd.DataFrame(
        columns=["id", "FECHA", "DESCRIPCION", "MONTO", "SALDO"]
    ))

    assert resultado["resumen"]["solo_guardadas"] == 0


def test_los_flujos_se_pueden_listar_aparte(portafolio):
    certificado(portafolio["id"])
    svc.registrar_flujo(portafolio["id"], "2025-04-28", 3213.74)

    assert len(svc.list_positions(tipo="flujo")) == 1
    assert len(svc.list_positions(tipo="plazo_fijo")) == 1


def test_el_id_se_puede_fijar_para_que_la_siembra_sea_idempotente(portafolio):
    """Sin id fijo, correr un script de siembra dos veces duplicaría todo."""
    flujo = svc.registrar_flujo(portafolio["id"], "2025-04-28", 3213.74,
                                position_id="flujo-uni-2025-04-28")

    assert flujo["id"] == "flujo-uni-2025-04-28"
    assert svc.get_position("flujo-uni-2025-04-28") is not None
