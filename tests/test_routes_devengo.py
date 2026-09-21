"""
test_routes_devengo.py — Etiquetar una deuda mía para que sea un gasto

Rutas bajo /api/supabase-debts: la bandeja, el alta de etiqueta y su baja.
Supabase se parchea; `etiquetas.csv` real nunca se toca.
"""
import sys
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from contabilidad.backend.main import app
from contabilidad.backend.services.transaction_service import LABEL_COLUMNS

client = TestClient(app)

MIA = "aaaaaaaa-0000-0000-0000-000000000001"
SUYA = "aaaaaaaa-0000-0000-0000-000000000002"
BASE = "/api/supabase-debts"


def deudas_df():
    return pd.DataFrame({
        "FECHA": pd.to_datetime(["2026-09-06", "2026-08-15"]),
        "DESCRIPCION": ["Carretao", "Le presté yo"],
        "MONTO": [36.83, 20.0],
        "TIPO": "DEUDA",
        "DEUDOR_NOMBRE": ["Ale", "rubia"],
        "DEUDOR_ID": ["d1", "d2"],
        "PAGADA": [False, False],
        "FECHA_PAGO": [None, None],
        "FECHA_CREACION": [None, None],
        "ID": [MIA, SUYA],
        "ES_MI_DEUDA": [True, False],
        "SALDO_PENDIENTE": [36.83, 20.0],
    })


def etiquetas_df(filas=()):
    return pd.DataFrame(list(filas), columns=LABEL_COLUMNS)


def fila_etiqueta(source_id, **extra):
    fila = {c: None for c in LABEL_COLUMNS}
    fila.update({"source_id": source_id, "source_type": "DEUDA"})
    fila.update(extra)
    return fila


def con_supabase(df=None):
    fake = MagicMock()
    fake.obtener_deudas_para_analisis.return_value = deudas_df() if df is None else df
    return patch.dict(sys.modules, {"contabilidad.debts.reading": fake})


def con_etiquetas(df):
    return patch("contabilidad.backend.services.transaction_service.load_labels", return_value=df)


# ── La bandeja ───────────────────────────────────────────────────────────────

def test_la_bandeja_solo_trae_deudas_mias():
    with con_supabase(), con_etiquetas(etiquetas_df()):
        r = client.get(f"{BASE}/devengo/pendientes")
    assert r.status_code == 200
    assert [d["ID"] for d in r.json()] == [MIA]


def test_la_bandeja_marca_cuales_ya_se_devengaron():
    etiquetas = etiquetas_df([fila_etiqueta(MIA, categoria="Alimentación", tags="Brasil_2026")])
    with con_supabase(), con_etiquetas(etiquetas):
        r = client.get(f"{BASE}/devengo/pendientes")
    fila = r.json()[0]
    assert fila["devengada"] is True
    assert fila["categoria"] == "Alimentación"
    assert fila["tags"] == "Brasil_2026"


def test_solo_pendientes_esconde_las_ya_decididas():
    etiquetas = etiquetas_df([fila_etiqueta(MIA)])
    with con_supabase(), con_etiquetas(etiquetas):
        r = client.get(f"{BASE}/devengo/pendientes", params={"solo_pendientes": True})
    assert r.json() == []


# ── Alta ─────────────────────────────────────────────────────────────────────

def test_etiquetar_una_deuda_mia_escribe_con_source_type_deuda():
    """La fila nueva trae además los valores estructurales del resto del CSV."""
    guardar = MagicMock()
    with con_supabase(), con_etiquetas(etiquetas_df()), \
         patch("contabilidad.backend.services.transaction_service.save_transaction_labels", guardar):
        r = client.put(f"{BASE}/{MIA}/etiqueta", json={"categoria": "Alimentación", "felicidad": 8})

    assert r.status_code == 200
    guardar.assert_called_once()
    args = guardar.call_args[0]
    assert args[0] == MIA
    assert args[1] == {
        "categoria": "Alimentación",
        "felicidad": 8,
        # Sin esto la fila queda con huecos donde las de banca y tarjeta tienen
        # su valor "apagado", y dos filas equivalentes se leen distinto.
        "es_fijo": False,
        "pertenece_a": "---",
        "es_reembolsable": False,
    }
    assert args[2] == "DEUDA"


def test_reetiquetar_no_pisa_lo_estructural_ya_guardado():
    """Los defectos son del alta. En una edición mandan los valores del archivo."""
    etiquetas = etiquetas_df([fila_etiqueta(MIA, categoria="Ocio", es_fijo=True, pertenece_a="Viaje")])
    guardar = MagicMock()
    with con_supabase(), con_etiquetas(etiquetas), \
         patch("contabilidad.backend.services.transaction_service.save_transaction_labels", guardar):
        r = client.put(f"{BASE}/{MIA}/etiqueta", json={"categoria": "Alimentación"})

    assert r.status_code == 200
    assert guardar.call_args[0][1] == {"categoria": "Alimentación"}


def test_no_se_devenga_una_deuda_que_me_deben():
    """Ese gasto ya está en mi transacción; devengarlo sería contarlo dos veces."""
    guardar = MagicMock()
    with con_supabase(), \
         patch("contabilidad.backend.services.transaction_service.save_transaction_labels", guardar):
        r = client.put(f"{BASE}/{SUYA}/etiqueta", json={"categoria": "Alimentación"})

    assert r.status_code == 400
    guardar.assert_not_called()


def test_deuda_inexistente_da_404():
    with con_supabase():
        r = client.put(f"{BASE}/no-existe/etiqueta", json={"categoria": "X"})
    assert r.status_code == 404


def test_sin_cambios_no_escribe():
    guardar = MagicMock()
    with con_supabase(), \
         patch("contabilidad.backend.services.transaction_service.save_transaction_labels", guardar):
        r = client.put(f"{BASE}/{MIA}/etiqueta", json={})
    assert r.status_code == 400
    guardar.assert_not_called()


def test_los_vinculos_no_se_escriben_a_mano():
    """`source_id` ya es el id de la deuda: `deuda_id`/`pago_id` los pone el lector."""
    guardar = MagicMock()
    with con_supabase(), \
         patch("contabilidad.backend.services.transaction_service.save_transaction_labels", guardar):
        client.put(f"{BASE}/{MIA}/etiqueta", json={"categoria": "X", "deuda_id": "otra", "pago_id": "p1"})
    enviado = guardar.call_args[0][1]
    assert "deuda_id" not in enviado and "pago_id" not in enviado


# ── Baja ─────────────────────────────────────────────────────────────────────

def test_quitar_el_devengo_borra_solo_esa_fila():
    etiquetas = etiquetas_df([
        fila_etiqueta(MIA),
        {**{c: None for c in LABEL_COLUMNS}, "source_id": "tx-banca", "source_type": "BANCA"},
    ])
    guardado = {}
    with patch("contabilidad.backend.services.transaction_service.load_labels", return_value=etiquetas), \
         patch("contabilidad.backend.services.transaction_service.save_labels",
               side_effect=lambda df: guardado.update({"df": df})):
        r = client.delete(f"{BASE}/{MIA}/etiqueta")

    assert r.status_code == 200
    quedaron = guardado["df"]
    assert list(quedaron["source_id"]) == ["tx-banca"], "la transacción de banca no se toca"


def test_quitar_el_devengo_de_algo_no_devengado_da_404():
    with patch("contabilidad.backend.services.transaction_service.load_labels",
               return_value=etiquetas_df()):
        r = client.delete(f"{BASE}/{MIA}/etiqueta")
    assert r.status_code == 404


# ── Las que ya tienen transacción no son "sin decidir" ───────────────────────

def test_una_deuda_con_transaccion_vinculada_sale_de_la_bandeja():
    """
    Si una transacción mía apunta a la deuda, esa plata ya pasó por mi cuenta y el
    gasto está contado ahí. Ofrecerla para devengar es ofrecer contarla dos veces.
    """
    vinculo = {**{c: None for c in LABEL_COLUMNS},
               "source_id": "tx-banca", "source_type": "BANCA", "deuda_id": MIA}
    with con_supabase(), con_etiquetas(etiquetas_df([vinculo])):
        bandeja = client.get(f"{BASE}/devengo/pendientes", params={"solo_pendientes": True}).json()
        todas = client.get(f"{BASE}/devengo/pendientes").json()

    assert bandeja == [], "no está sin decidir: su transacción ya la resolvió"
    assert todas[0]["tiene_transaccion"] is True, "sin el filtro sigue visible, pero marcada"


def test_sin_vinculo_la_deuda_sigue_en_la_bandeja():
    with con_supabase(), con_etiquetas(etiquetas_df()):
        bandeja = client.get(f"{BASE}/devengo/pendientes", params={"solo_pendientes": True}).json()
    assert [d["ID"] for d in bandeja] == [MIA]
    assert bandeja[0]["tiene_transaccion"] is False


# ── Editar una deuda devengada desde la lista normal ─────────────────────────

def test_editar_una_deuda_devengada_desde_la_ruta_de_transacciones():
    """
    En modo devengo la fila viaja con las transacciones, así que el usuario le hace
    clic para editarla. Antes eso daba 404: el id vive en Supabase, no en banca.
    """
    guardar = MagicMock()
    with patch("contabilidad.backend.routes.transactions.load_source_data",
               return_value=pd.DataFrame(columns=["id", "TIPO", "DESCRIPCION"])), \
         patch("contabilidad.backend.routes.transactions.load_labels",
               return_value=etiquetas_df([fila_etiqueta(MIA)])), \
         patch("contabilidad.backend.routes.transactions.save_transaction_labels", guardar):
        r = client.put(f"/api/transactions/{MIA}", json={"categoria": "Ocio"})

    assert r.status_code == 200
    assert guardar.call_args[0] == (MIA, {"categoria": "Ocio"}, "DEUDA")


def test_un_id_que_no_es_nada_sigue_dando_404():
    with patch("contabilidad.backend.routes.transactions.load_source_data",
               return_value=pd.DataFrame(columns=["id", "TIPO", "DESCRIPCION"])), \
         patch("contabilidad.backend.routes.transactions.load_labels",
               return_value=etiquetas_df()):
        r = client.put("/api/transactions/no-existe", json={"categoria": "Ocio"})
    assert r.status_code == 404
