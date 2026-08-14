"""
test_variables_storage.py — Tests for InterpolationStorage (CRUD de CSV de grupos y pagos)

All tests use tmp_path to avoid touching real data files.
Correct signatures:
  - create_group(name, description=None, group_type='interpolated')
  - create_payment(group_id, amount, start_date, end_date, note=None)
  - save_entity_rule(name, attrs: dict)
"""
import pytest
import pandas as pd
from unittest.mock import patch


@pytest.fixture
def patched_storage(tmp_path):
    """Patch GROUPS_FILE and PAYMENTS_FILE to tmp_path."""
    groups_file = str(tmp_path / "grupos.csv")
    payments_file = str(tmp_path / "pagos.csv")
    base_path = str(tmp_path)

    with patch("contabilidad.backend.storage.variables_storage.GROUPS_FILE", groups_file), \
         patch("contabilidad.backend.storage.variables_storage.PAYMENTS_FILE", payments_file), \
         patch("contabilidad.backend.storage.variables_storage.BASE_DATA_PATH", base_path):
        from contabilidad.backend.storage.variables_storage import InterpolationStorage
        yield InterpolationStorage


# ── Groups CRUD ───────────────────────────────────────────────────────────────

def test_create_and_get_group(patched_storage):
    group = patched_storage.create_group(name="Renta", description="Pago mensual", group_type="fixed")
    assert group is not None
    assert group["name"] == "Renta"
    assert group["type"] == "fixed"

    groups = patched_storage.get_groups(type_filter="fixed")
    assert any(g["name"] == "Renta" for g in groups)


def test_get_groups_type_filter(patched_storage):
    patched_storage.create_group("Fixed G", "desc", group_type="fixed")
    patched_storage.create_group("Interp G", "desc", group_type="interpolated")

    fixed = patched_storage.get_groups(type_filter="fixed")
    interp = patched_storage.get_groups(type_filter="interpolated")

    assert all(g["type"] == "fixed" for g in fixed)
    assert all(g["type"] == "interpolated" for g in interp)


def test_update_group(patched_storage):
    group = patched_storage.create_group("Original", "desc", group_type="fixed")
    gid = group["id"]
    updated = patched_storage.update_group(gid, {"name": "Updated", "description": "new desc", "type": "fixed"})
    assert updated is not None
    assert updated["name"] == "Updated"


def test_update_nonexistent_group_returns_none(patched_storage):
    result = patched_storage.update_group("nonexistent-id", {"name": "X"})
    assert result is None


def test_delete_group(patched_storage):
    group = patched_storage.create_group("ToDelete", "desc", group_type="fixed")
    gid = group["id"]
    success = patched_storage.delete_group(gid)
    assert success is True
    groups = patched_storage.get_groups(type_filter="fixed")
    assert not any(g["id"] == gid for g in groups)


def test_delete_group_also_deletes_payments(patched_storage):
    group = patched_storage.create_group("WithPayments", "desc", group_type="fixed")
    gid = group["id"]
    patched_storage.create_payment(gid, 100.0, "2025-01-01", None)
    patched_storage.delete_group(gid)
    payments = patched_storage.get_payments(gid)
    assert len(payments) == 0


def test_delete_nonexistent_group_returns_false(patched_storage):
    result = patched_storage.delete_group("fake-id")
    assert result is False


# ── Payments CRUD ─────────────────────────────────────────────────────────────

def test_create_and_get_payment(patched_storage):
    group = patched_storage.create_group("G1", "desc", group_type="fixed")
    gid = group["id"]
    payment = patched_storage.create_payment(gid, 1500.0, "2025-01-01", "2025-01-31")
    assert payment is not None
    assert float(payment["amount"]) == 1500.0

    payments = patched_storage.get_payments(gid)
    assert len(payments) == 1
    assert float(payments[0]["amount"]) == 1500.0


def test_create_payment_with_null_end_date(patched_storage):
    group = patched_storage.create_group("G2", "desc", group_type="fixed")
    gid = group["id"]
    payment = patched_storage.create_payment(gid, 500.0, "2025-01-01", None)
    assert payment["end_date"] is None


def test_update_payment(patched_storage):
    group = patched_storage.create_group("G3", "desc", group_type="fixed")
    gid = group["id"]
    payment = patched_storage.create_payment(gid, 100.0, "2025-01-01", None)
    pid = payment["id"]
    updated = patched_storage.update_payment(pid, {"amount": 999.0, "start_date": "2025-01-01", "end_date": None, "note": ""})
    assert updated is not None
    assert float(updated["amount"]) == 999.0


def test_update_nonexistent_payment_returns_none(patched_storage):
    result = patched_storage.update_payment("fake-pid", {"amount": 100.0})
    assert result is None


def test_delete_payment(patched_storage):
    group = patched_storage.create_group("G4", "desc", group_type="fixed")
    gid = group["id"]
    payment = patched_storage.create_payment(gid, 200.0, "2025-02-01", None)
    pid = payment["id"]
    success = patched_storage.delete_payment(pid)
    assert success is True
    payments = patched_storage.get_payments(gid)
    assert not any(p["id"] == pid for p in payments)


def test_delete_nonexistent_payment_returns_false(patched_storage):
    result = patched_storage.delete_payment("fake-pid")
    assert result is False


def test_multiple_payments_for_same_group(patched_storage):
    group = patched_storage.create_group("G5", "desc", group_type="fixed")
    gid = group["id"]
    patched_storage.create_payment(gid, 100.0, "2025-01-01", "2025-01-31")
    patched_storage.create_payment(gid, 200.0, "2025-02-01", "2025-02-28")
    payments = patched_storage.get_payments(gid)
    assert len(payments) == 2


# ── Regresiones: los tres bugs de §7.7–7.9 del handoff de inversiones ─────────
#
# Los tres son de la misma familia: el CSV puede contener cosas que la capa de acceso
# no contempla, y en vez de fallar hace algo peor —borrar de más, esconder, o colar un
# NaN—. Ninguno se manifiesta con datos limpios, y por eso vivieron tanto tiempo.

def _anexar_fila_cruda(payments_file, fila: str):
    """Escribe una fila directamente en el CSV, saltándose la capa de acceso."""
    with open(payments_file, "a") as f:
        f.write(fila.rstrip("\n") + "\n")


def test_borrar_un_id_repetido_no_arrastra_la_otra_fila(patched_storage, tmp_path):
    """§7.7 — `pagos.csv` llegó a tener el mismo id en dos filas.

    `delete_payment()` hacía `df[df['id'] != id]`, o sea que borrar una se llevaba la
    otra por delante sin decir nada.
    """
    grupo = patched_storage.create_group("Repes", "desc", group_type="fixed")
    gid = grupo["id"]
    pago = patched_storage.create_payment(gid, 100.0, "2025-01-01", "2025-02-01")
    otro = patched_storage.create_payment(gid, 200.0, "2025-02-01", "2025-03-01")

    # El clon: mismo id que `pago`, monto distinto.
    _anexar_fila_cruda(str(tmp_path / "pagos.csv"),
                       f"{pago['id']},{gid},999.0,2025-05-01,2025-06-01,clon")
    assert len(patched_storage.get_payments(gid)) == 3

    assert patched_storage.delete_payment(pago["id"]) is True

    quedan = patched_storage.get_payments(gid)
    assert len(quedan) == 2, "se llevó por delante la fila del id repetido"
    assert sorted(p["amount"] for p in quedan) == [200.0, 999.0]
    assert any(p["id"] == otro["id"] for p in quedan)


def test_editar_un_id_repetido_toca_una_sola_fila(patched_storage, tmp_path):
    """§7.7, la otra mitad: `update_payment()` también escribía sobre todas."""
    grupo = patched_storage.create_group("Repes2", "desc", group_type="fixed")
    gid = grupo["id"]
    pago = patched_storage.create_payment(gid, 100.0, "2025-01-01", "2025-02-01")
    _anexar_fila_cruda(str(tmp_path / "pagos.csv"),
                       f"{pago['id']},{gid},999.0,2025-05-01,2025-06-01,clon")

    patched_storage.update_payment(pago["id"], {"amount": 111.0})

    montos = sorted(p["amount"] for p in patched_storage.get_payments(gid))
    assert montos == [111.0, 999.0], "la edición pisó también el clon"


def test_create_payment_no_reutiliza_un_id_existente(patched_storage, tmp_path):
    """§7.7 en el origen: el id nuevo se comprueba contra los que ya están."""
    grupo = patched_storage.create_group("Unicos", "desc", group_type="fixed")
    gid = grupo["id"]
    pagos = [patched_storage.create_payment(gid, 10.0 * i, "2025-01-01", "2025-02-01")
             for i in range(1, 6)]
    ids = [p["id"] for p in pagos]
    assert len(set(ids)) == len(ids)


def test_las_filas_rotas_se_pueden_ver_y_borrar(patched_storage, tmp_path):
    """§7.8 — una fila que el camino normal descarta desaparecía del dashboard *y* de la
    pantalla de Variables a la vez: el usuario no podía borrar lo que no podía ver.

    (La fila sin fecha de fin, que era el ejemplo original, ya **no** es inválida: vale
    «para siempre». Lo que sigue sin significar nada es una fila sin monto.)
    """
    grupo = patched_storage.create_group("Fantasmas", "desc", group_type="fixed")
    gid = grupo["id"]
    patched_storage.create_payment(gid, 100.0, "2025-01-01", "2025-02-01")
    _anexar_fila_cruda(str(tmp_path / "pagos.csv"),
                       f"rota-1,{gid},,2025-12-22,2026-01-01,la que nadie veia")

    assert len(patched_storage.get_payments(gid)) == 1, "no debe aplicarse"

    invalidas = patched_storage.get_invalid_payments()
    assert len(invalidas) == 1
    assert invalidas[0]["id"] == "rota-1"
    assert "monto" in invalidas[0]["motivo"]

    assert patched_storage.delete_payment_row(invalidas[0]["fila"]) is True
    assert patched_storage.get_invalid_payments() == []
    assert len(patched_storage.get_payments(gid)) == 1, "no debía tocar la fila buena"


def test_get_invalid_payments_filtra_por_grupo(patched_storage, tmp_path):
    a = patched_storage.create_group("A", "desc", group_type="fixed")
    b = patched_storage.create_group("B", "desc", group_type="fixed")
    ruta = str(tmp_path / "pagos.csv")
    patched_storage.create_payment(a["id"], 1.0, "2025-01-01", "2025-02-01")
    _anexar_fila_cruda(ruta, f"mala-a,{a['id']},,2025-01-01,2025-02-01,")
    _anexar_fila_cruda(ruta, f"mala-b,{b['id']},,2025-01-01,2025-02-01,")

    assert len(patched_storage.get_invalid_payments()) == 2
    solo_a = patched_storage.get_invalid_payments(a["id"])
    assert [x["id"] for x in solo_a] == ["mala-a"]


def test_delete_payment_row_fuera_de_rango(patched_storage):
    patched_storage.create_group("X", "desc", group_type="fixed")
    assert patched_storage.delete_payment_row(999) is False
    assert patched_storage.delete_payment_row(0) is False


def test_read_csv_no_deja_nan_en_columnas_de_texto_vacias(patched_storage, tmp_path):
    """§7.9 — `read_csv` promete convertir los NaN a None y no lo cumplía.

    En una columna que pandas infiere `float64` o `str` —cualquier columna de texto
    enteramente vacía— asignar de vuelta una serie de `None` la re-infiere y el NaN
    vuelve. Y `nan` es *truthy*, así que un `campo or ''` no lo atrapa: eso es lo que
    hacía que el endpoint de neutralización respondiera 500 al serializar.
    """
    import json
    from contabilidad.backend.storage import variables_storage as vs

    grupo = patched_storage.create_group("SinNotas", "desc", group_type="fixed")
    gid = grupo["id"]
    ruta = str(tmp_path / "pagos.csv")
    patched_storage.create_payment(gid, 100.0, "2025-01-01", "2025-02-01")
    _anexar_fila_cruda(ruta, f"otro,{gid},50.0,2026-01-01,2026-02-01,")

    crudos = vs.read_csv(ruta, vs.PAYMENT_COLUMNS).to_dict("records")
    notas = [r["note"] for r in crudos]
    assert all(n is None or isinstance(n, str) for n in notas), f"quedó un NaN: {notas}"
    assert not any(isinstance(n, float) for n in notas)

    json.dumps(crudos)  # es lo que reventaba en FastAPI


def test_read_csv_conserva_el_dtype_de_las_columnas_llenas(patched_storage, tmp_path):
    """El arreglo de §7.9 solo convierte a `object` las columnas con huecos."""
    from contabilidad.backend.storage import variables_storage as vs

    grupo = patched_storage.create_group("Llenas", "desc", group_type="fixed")
    patched_storage.create_payment(grupo["id"], 100.0, "2025-01-01", "2025-02-01", note="n1")
    patched_storage.create_payment(grupo["id"], 200.0, "2025-02-01", "2025-03-01", note="n2")

    df = vs.read_csv(str(tmp_path / "pagos.csv"), vs.PAYMENT_COLUMNS)
    assert df["amount"].dtype != object, "sin huecos no hay por qué perder el dtype"
    assert df["amount"].sum() == 300.0
