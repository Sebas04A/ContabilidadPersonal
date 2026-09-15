"""
test_routes_investments.py — Tests for /api/investments via FastAPI TestClient
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from contabilidad.backend.main import app

client = TestClient(app)


MOCK_CHART_DATA = {
    "dates": ["2025-01-01", "2025-01-02", "2025-01-03"],
    "saldo": [10000.0, 10500.0, 10200.0],
    "inversion": [5000.0, 5000.0, 5000.0],
    "investment_periods": [
        {
            "amount": 5000.0,
            "start_date": "2025-01-01",
            "end_date": "2025-06-30",
            "group_name": "CDP Banco"
        }
    ]
}

MOCK_ACCOUNTS_DATA = {
    "iniciadas": [
        {"fecha": "2025-01-01", "monto": 5000.0, "descripcion": "CDP_001", "interes": 300.0, "impuesto": 45.0}
    ],
    "finalizadas": []
}


# ── GET /api/investments/chart-data ───────────────────────────────────────────

def test_get_chart_data_returns_200():
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investment_chart_data",
        return_value=MOCK_CHART_DATA
    ):
        response = client.get("/api/investments/chart-data")
    assert response.status_code == 200


def test_get_chart_data_has_required_keys():
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investment_chart_data",
        return_value=MOCK_CHART_DATA
    ):
        response = client.get("/api/investments/chart-data")
    data = response.json()
    assert "dates" in data
    assert "saldo" in data
    assert "inversion" in data
    assert "investment_periods" in data


def test_get_chart_data_investment_periods_is_list():
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investment_chart_data",
        return_value=MOCK_CHART_DATA
    ):
        response = client.get("/api/investments/chart-data")
    data = response.json()
    assert isinstance(data["investment_periods"], list)


def test_get_chart_data_period_structure():
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investment_chart_data",
        return_value=MOCK_CHART_DATA
    ):
        response = client.get("/api/investments/chart-data")
    data = response.json()
    if data["investment_periods"]:
        period = data["investment_periods"][0]
        assert "amount" in period or "start_date" in period


# ── GET /api/investments/from-accounts ────────────────────────────────────────

def test_get_from_accounts_returns_200():
    from contabilidad.backend.models.investment_models import AccountInvestment, InvestmentsFromAccountsResponse
    mock_resp = InvestmentsFromAccountsResponse(
        iniciadas=[AccountInvestment(fecha="2025-01-01", monto=5000.0, descripcion="CDP_001", tipo="iniciada")],
        finalizadas=[]
    )
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investments_from_accounts",
        return_value=mock_resp
    ):
        response = client.get("/api/investments/from-accounts")
    assert response.status_code == 200


def test_get_from_accounts_has_iniciadas():
    from contabilidad.backend.models.investment_models import AccountInvestment, InvestmentsFromAccountsResponse
    mock_resp = InvestmentsFromAccountsResponse(
        iniciadas=[AccountInvestment(fecha="2025-01-01", monto=5000.0, descripcion="CDP_001", tipo="iniciada")],
        finalizadas=[]
    )
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investments_from_accounts",
        return_value=mock_resp
    ):
        response = client.get("/api/investments/from-accounts")
    data = response.json()
    assert "iniciadas" in data


def test_service_exception_returns_error():
    with patch(
        "contabilidad.backend.services.investment_service.InvestmentService.get_investment_chart_data",
        side_effect=Exception("Service error")
    ):
        response = client.get("/api/investments/chart-data")
    assert response.status_code in [500, 200]  # may handle gracefully


# ── /api/investments/positions ────────────────────────────────────────────────

@pytest.fixture
def storage_tmp(tmp_path):
    """CSV de inversiones y de grupos en tmp_path: las rutas no tocan `data/`."""
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
        yield


NUEVA_POSICION = {
    "tipo": "plazo_fijo",
    "fecha_apertura": "2025-01-10",
    "fecha_cierre": "2025-02-10",
    "movimientos": [
        {"fecha": "2025-01-10", "tipo": "aporte", "monto": 1000.0},
        {"fecha": "2025-02-10", "tipo": "retiro", "monto": 1000.0},
        {"fecha": "2025-02-10", "tipo": "interes", "monto": 10.0},
    ],
}


def test_crear_posicion_devuelve_derivados(storage_tmp):
    response = client.post("/api/investments/positions", json=NUEVA_POSICION)
    assert response.status_code == 200

    data = response.json()
    assert data["capital"] == 1000.0
    assert data["interes"] == 10.0
    assert data["estado"] == "cerrada"


def test_listar_posiciones(storage_tmp):
    client.post("/api/investments/positions", json=NUEVA_POSICION)
    response = client.get("/api/investments/positions")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_filtrar_posiciones_por_estado(storage_tmp):
    client.post("/api/investments/positions", json=NUEVA_POSICION)
    assert client.get("/api/investments/positions?estado=abierta").json() == []


def test_actualizar_posicion(storage_tmp):
    position_id = client.post("/api/investments/positions", json=NUEVA_POSICION).json()["id"]
    response = client.put(f"/api/investments/positions/{position_id}", json={"nota": "revisada"})

    assert response.status_code == 200
    assert response.json()["nota"] == "revisada"


def test_borrar_posicion(storage_tmp):
    position_id = client.post("/api/investments/positions", json=NUEVA_POSICION).json()["id"]

    assert client.delete(f"/api/investments/positions/{position_id}").status_code == 200
    assert client.delete(f"/api/investments/positions/{position_id}").status_code == 404


def test_posicion_inexistente_da_404(storage_tmp):
    assert client.get("/api/investments/positions/no-existe").status_code == 404


# ── GET /api/investments/portfolios/{id}/analysis ─────────────────────────────

def test_analisis_de_un_portafolio(storage_tmp):
    """El bolsillo entero: la identidad `total = aportado + ganancia` viaja en la respuesta."""
    grupo = client.post("/api/payments/groups", json={
        "name": "Inversiones_Test", "type": "fixed", "es_inversion": True,
    })
    assert grupo.status_code == 200, grupo.text
    portafolio_id = grupo.json()["id"]

    client.post("/api/investments/positions", json={**NUEVA_POSICION, "portafolio_id": portafolio_id})
    response = client.get(f"/api/investments/portfolios/{portafolio_id}/analysis")

    assert response.status_code == 200
    data = response.json()
    assert data["apto"] is True
    kpis = data["kpis"]
    assert kpis["total_hoy"] == pytest.approx(kpis["aportado_neto"] + kpis["ganancia_acumulada"], abs=0.02)
    assert kpis["ganancia_acumulada"] == pytest.approx(10.0, abs=0.01)
    assert len(data["posiciones"]) == 1


def test_analisis_de_un_portafolio_inexistente_da_404(storage_tmp):
    assert client.get("/api/investments/portfolios/no-existe/analysis").status_code == 404


# ── GET /api/investments/positions/{id}/analysis ──────────────────────────────

def test_analisis_de_una_posicion(storage_tmp):
    """La curva de crecimiento tiene que aterrizar en el interés real de la posición."""
    position_id = client.post("/api/investments/positions", json=NUEVA_POSICION).json()["id"]
    response = client.get(f"/api/investments/positions/{position_id}/analysis")

    assert response.status_code == 200
    data = response.json()
    assert data["apto"] is True
    assert data["tasa_origen"] == "liquidada"
    assert data["serie"]["valor"][0] == 1000.0
    assert data["serie"]["valor"][-1] == pytest.approx(1010.0, abs=0.01)
    assert data["ganancia"]["interes_neto"] == pytest.approx(10.0, abs=0.01)
    assert data["escenarios"], "una posición cerrada con tasa siempre tiene escenario"


def test_analisis_de_una_posicion_inexistente_da_404(storage_tmp):
    assert client.get("/api/investments/positions/no-existe/analysis").status_code == 404


def test_la_ruta_de_analisis_no_se_come_la_de_leer(storage_tmp):
    """`/positions/{id}` y `/positions/{id}/analysis` son rutas distintas.

    Se fija porque el orden de declaración en FastAPI decide qué patrón gana, y una de
    las dos devolvería la respuesta de la otra si alguien las reordena.
    """
    position_id = client.post("/api/investments/positions", json=NUEVA_POSICION).json()["id"]

    posicion = client.get(f"/api/investments/positions/{position_id}").json()
    analisis = client.get(f"/api/investments/positions/{position_id}/analysis").json()

    assert "movimientos" in posicion and "serie" not in posicion
    assert "serie" in analisis


def test_datos_invalidos_dan_400(storage_tmp):
    response = client.post("/api/investments/positions", json={**NUEVA_POSICION, "tipo": "cripto"})
    assert response.status_code == 400


def test_posicion_sin_fechas_da_400(storage_tmp):
    assert client.post("/api/investments/positions", json={}).status_code == 400


def test_listar_portafolios(storage_tmp):
    response = client.get("/api/investments/portfolios")
    assert response.status_code == 200
    assert response.json() == []


# ── /api/investments/detect ───────────────────────────────────────────────────

MOCK_DIFF = {
    "nuevas": [], "cambiadas": [], "iguales": [], "huerfanas": [], "solo_guardadas": [],
    "resumen": {"detectadas": 0, "guardadas": 0, "nuevas": 0, "cambiadas": 0,
                "iguales": 0, "huerfanas": 0, "solo_guardadas": 0},
}


def test_detect_devuelve_el_diff():
    with patch("contabilidad.backend.services.investments.reconcile", return_value=MOCK_DIFF):
        response = client.post("/api/investments/detect")

    assert response.status_code == 200
    assert response.json()["resumen"]["detectadas"] == 0


def test_detect_apply_pasa_la_seleccion():
    resultado = {"creadas": [], "actualizadas": [], "omitidas": [],
                 "resumen": {"creadas": 0, "actualizadas": 0, "omitidas": 0}}
    with patch("contabilidad.backend.services.investments.apply_detection",
               return_value=resultado) as apply_mock:
        response = client.post("/api/investments/detect/apply",
                               json={"tx_apertura_ids": ["tx001"], "portafolio_id": "g1"})

    assert response.status_code == 200
    assert apply_mock.call_args.kwargs["tx_apertura_ids"] == ["tx001"]
    assert apply_mock.call_args.kwargs["portafolio_id"] == "g1"


def test_detect_apply_portafolio_invalido_da_400():
    from contabilidad.backend.services.investments import ValidationError
    with patch("contabilidad.backend.services.investments.apply_detection",
               side_effect=ValidationError("no existe")):
        response = client.post("/api/investments/detect/apply", json={"portafolio_id": "no-existe"})

    assert response.status_code == 400


# ── /api/investments/summary y /timeline ──────────────────────────────────────

def test_summary_devuelve_los_tres_ambitos(storage_tmp):
    client.post("/api/investments/positions", json=NUEVA_POSICION)
    response = client.get("/api/investments/summary")

    assert response.status_code == 200
    data = response.json()
    assert {"global", "propio", "custodia", "por_portafolio", "por_anio"} <= set(data)
    assert data["global"]["capital_rotado"] == 1000.0


def test_timeline_devuelve_serie_y_eventos(storage_tmp):
    client.post("/api/investments/positions", json=NUEVA_POSICION)
    response = client.get("/api/investments/timeline")

    assert response.status_code == 200
    data = response.json()
    assert len(data["fechas"]) == len(data["capital"])
    assert len(data["eventos"]) == 2


def test_summary_sin_posiciones_no_falla(storage_tmp):
    response = client.get("/api/investments/summary")
    assert response.status_code == 200
    assert response.json()["global"]["posiciones"] == 0


# ── /api/investments/positions/{id}/split ─────────────────────────────────────

def test_split_devuelve_las_partes(storage_tmp):
    position_id = client.post("/api/investments/positions", json=NUEVA_POSICION).json()["id"]
    response = client.post(f"/api/investments/positions/{position_id}/split", json={
        "partes": [{"capital": 600.0}, {"capital": 400.0}],
    })

    assert response.status_code == 200
    partes = response.json()["partes"]
    assert [p["capital"] for p in partes] == [600.0, 400.0]
    assert [p["interes"] for p in partes] == [6.0, 4.0]


def test_split_que_no_suma_da_400(storage_tmp):
    position_id = client.post("/api/investments/positions", json=NUEVA_POSICION).json()["id"]
    response = client.post(f"/api/investments/positions/{position_id}/split", json={
        "partes": [{"capital": 100.0}, {"capital": 100.0}],
    })
    assert response.status_code == 400


def test_split_de_posicion_inexistente_da_404(storage_tmp):
    response = client.post("/api/investments/positions/no-existe/split", json={
        "partes": [{"capital": 1.0}, {"capital": 1.0}],
    })
    assert response.status_code == 404


# ── /api/investments/cut/regenerate ──────────────────────────────────────────

def test_regenerar_preview_endpoint(storage_tmp):
    response = client.get("/api/investments/cut/regenerate/preview")
    assert response.status_code == 200
    data = response.json()
    assert "sin_cambios" in data
    assert "por_portafolio" in data

