"""
test_ciclos_storage.py — Ciclos de un fondo: fronteras, generación y edición.

Todo contra `tmp_path`: no se toca ningún archivo real de `data/`.
"""
from datetime import date
from unittest.mock import patch

import pytest


@pytest.fixture
def ciclos(tmp_path):
    """`CICLOS_FILE` y `BASE_DATA_PATH` apuntando a tmp_path."""
    with patch("contabilidad.backend.storage.ciclos_storage.CICLOS_FILE",
               str(tmp_path / "ciclos.csv")), \
         patch("contabilidad.backend.storage.variables_storage.BASE_DATA_PATH",
               str(tmp_path)):
        from contabilidad.backend.storage import ciclos_storage
        yield ciclos_storage


# ── Fronteras ─────────────────────────────────────────────────────────────────

def test_frontera_en_o_antes(ciclos):
    # El propio día de corte cuenta como frontera.
    assert ciclos.frontera_en_o_antes(date(2026, 3, 22), 22) == date(2026, 3, 22)
    # Antes del corte hay que retroceder al mes anterior.
    assert ciclos.frontera_en_o_antes(date(2026, 3, 10), 22) == date(2026, 2, 22)
    # Cruce de año.
    assert ciclos.frontera_en_o_antes(date(2026, 1, 5), 22) == date(2025, 12, 22)


def test_frontera_siguiente_es_estrictamente_posterior(ciclos):
    # Si devolviera la misma fecha, el generador crearía un ciclo vacío y se colgaría.
    assert ciclos.frontera_siguiente(date(2026, 1, 22), 22) == date(2026, 2, 22)
    assert ciclos.frontera_siguiente(date(2026, 1, 10), 22) == date(2026, 1, 22)


def test_dia_de_corte_se_recorta_al_mes_corto(ciclos):
    # Un corte el 31 no existe en febrero: se recorta al último día.
    assert ciclos.frontera_siguiente(date(2026, 1, 31), 31) == date(2026, 2, 28)
    # Y desde ese día recortado sigue avanzando, sin quedarse clavado.
    assert ciclos.frontera_siguiente(date(2026, 2, 28), 31) == date(2026, 3, 31)


def test_dia_de_corte_29_en_anio_bisiesto(ciclos):
    assert ciclos.frontera_siguiente(date(2024, 1, 29), 29) == date(2024, 2, 29)


# ── Generación ────────────────────────────────────────────────────────────────

def test_generar_desde_cero_cubre_el_rango_y_es_contiguo(ciclos):
    creados = ciclos.generar_ciclos("f1", 22, date(2025, 11, 24), date(2026, 3, 5))
    assert creados

    todos = ciclos.CicloStorage.get_ciclos("f1")
    # El primero arranca en la frontera anterior al primer movimiento, no en él.
    assert todos[0]["inicio"] == "2025-11-22"
    # El último contiene la fecha final.
    assert todos[-1]["inicio"] <= "2026-03-05" < todos[-1]["fin"]
    # fin(n) == inicio(n+1): sin huecos ni solapes.
    for anterior, siguiente in zip(todos, todos[1:]):
        assert anterior["fin"] == siguiente["inicio"]


def test_generar_es_idempotente(ciclos):
    ciclos.generar_ciclos("f1", 22, date(2026, 1, 1), date(2026, 3, 5))
    cuantos = len(ciclos.CicloStorage.get_ciclos("f1"))

    assert ciclos.generar_ciclos("f1", 22, date(2026, 1, 1), date(2026, 3, 5)) == []
    assert len(ciclos.CicloStorage.get_ciclos("f1")) == cuantos


def test_generar_extiende_hacia_adelante_sin_tocar_lo_que_habia(ciclos):
    ciclos.generar_ciclos("f1", 22, date(2026, 1, 1), date(2026, 1, 30))
    antes = ciclos.CicloStorage.get_ciclos("f1")

    ciclos.generar_ciclos("f1", 22, date(2026, 1, 1), date(2026, 4, 10))
    despues = ciclos.CicloStorage.get_ciclos("f1")

    assert len(despues) > len(antes)
    assert despues[:len(antes)] == antes  # los viejos, intactos e iguales
    assert despues[-1]["inicio"] <= "2026-04-10" < despues[-1]["fin"]


def test_generar_extiende_hacia_atras(ciclos):
    """Un import del banco puede traer una transacción anterior al primer ciclo."""
    ciclos.generar_ciclos("f1", 22, date(2026, 3, 1), date(2026, 3, 30))
    primero_antes = ciclos.CicloStorage.get_ciclos("f1")[0]["inicio"]

    ciclos.generar_ciclos("f1", 22, date(2025, 12, 15), date(2026, 3, 30))
    todos = ciclos.CicloStorage.get_ciclos("f1")

    assert todos[0]["inicio"] < primero_antes
    assert todos[0]["inicio"] <= "2025-12-15" < todos[0]["fin"]
    for anterior, siguiente in zip(todos, todos[1:]):
        assert anterior["fin"] == siguiente["inicio"]


def test_generar_respeta_una_frontera_movida_a_mano(ciclos):
    """Lo que el usuario ajustó manda sobre el día de corte por defecto."""
    ciclos.generar_ciclos("f1", 22, date(2026, 1, 1), date(2026, 2, 25))
    todos = ciclos.CicloStorage.get_ciclos("f1")
    ultimo = todos[-1]
    ciclos.CicloStorage.actualizar(ultimo["id"], {"fin": "2026-03-05"})

    ciclos.generar_ciclos("f1", 22, date(2026, 1, 1), date(2026, 4, 10))
    todos = ciclos.CicloStorage.get_ciclos("f1")

    # El ciclo nuevo arranca donde acabó el movido, no en el 22.
    siguiente = next(c for c in todos if c["inicio"] == "2026-03-05")
    assert siguiente["fin"] == "2026-03-22"
    for anterior, sig in zip(todos, todos[1:]):
        assert anterior["fin"] == sig["inicio"]


def test_generar_sin_fechas_no_hace_nada(ciclos):
    assert ciclos.generar_ciclos("f1", 22, None, None) == []
    assert ciclos.CicloStorage.get_ciclos("f1") == []


# ── Pertenencia ───────────────────────────────────────────────────────────────

def test_el_dia_de_la_frontera_cae_en_el_ciclo_nuevo(ciclos):
    """`inicio` inclusivo, `fin` exclusivo: sin esto habría que desempatar."""
    ciclos.generar_ciclos("f1", 22, date(2026, 1, 1), date(2026, 3, 5))
    todos = ciclos.CicloStorage.get_ciclos("f1")

    ciclo = ciclos.ciclo_de_fecha(todos, date(2026, 2, 22))
    assert ciclo["inicio"] == "2026-02-22"

    anterior = ciclos.ciclo_de_fecha(todos, date(2026, 2, 21))
    assert anterior["fin"] == "2026-02-22"
    assert anterior["id"] != ciclo["id"]


def test_todo_movimiento_del_rango_tiene_ciclo(ciclos):
    ciclos.generar_ciclos("f1", 22, date(2025, 11, 24), date(2026, 6, 22))
    todos = ciclos.CicloStorage.get_ciclos("f1")

    for fecha in (date(2025, 11, 24), date(2026, 1, 22), date(2026, 2, 26),
                  date(2026, 3, 3), date(2026, 6, 22)):
        assert ciclos.ciclo_de_fecha(todos, fecha) is not None, fecha


def test_febrero_sin_ingreso_no_lo_paga_enero(ciclos):
    """El caso real del fondo Comida: el ingreso del 22-01 cubría gastos del 26-02."""
    ciclos.generar_ciclos("f1", 22, date(2026, 1, 22), date(2026, 3, 20))
    todos = ciclos.CicloStorage.get_ciclos("f1")

    ingreso_enero = ciclos.ciclo_de_fecha(todos, date(2026, 1, 22))
    gasto_febrero = ciclos.ciclo_de_fecha(todos, date(2026, 2, 26))
    assert ingreso_enero["id"] != gasto_febrero["id"]

    # Y los dos ingresos amontonados de marzo caen en el ciclo de febrero, que es de
    # donde la etiqueta `ciclo_id` tendrá que sacar al segundo (fase 2).
    assert ciclos.ciclo_de_fecha(todos, date(2026, 3, 3))["id"] == gasto_febrero["id"]
    assert ciclos.ciclo_de_fecha(todos, date(2026, 3, 20))["id"] == gasto_febrero["id"]


# ── Mover fronteras ───────────────────────────────────────────────────────────

def test_mover_frontera_cambia_los_dos_ciclos(ciclos):
    ciclos.generar_ciclos("f1", 22, date(2026, 1, 1), date(2026, 3, 5))
    todos = ciclos.CicloStorage.get_ciclos("f1")
    segundo = todos[1]

    tocados = ciclos.mover_frontera(segundo["id"], date(2026, 1, 25))
    assert tocados is not None

    todos = ciclos.CicloStorage.get_ciclos("f1")
    assert todos[0]["fin"] == "2026-01-25"
    assert todos[1]["inicio"] == "2026-01-25"
    for anterior, siguiente in zip(todos, todos[1:]):
        assert anterior["fin"] == siguiente["inicio"]


def test_no_se_puede_mover_la_frontera_del_primer_ciclo(ciclos):
    ciclos.generar_ciclos("f1", 22, date(2026, 1, 1), date(2026, 3, 5))
    primero = ciclos.CicloStorage.get_ciclos("f1")[0]
    assert ciclos.mover_frontera(primero["id"], date(2026, 1, 5)) is None


def test_no_se_puede_saltar_a_los_vecinos(ciclos):
    """Fuera del tramo, uno de los dos ciclos quedaría vacío o invertido."""
    ciclos.generar_ciclos("f1", 22, date(2026, 1, 1), date(2026, 4, 5))
    todos = ciclos.CicloStorage.get_ciclos("f1")
    tercero = todos[2]

    assert ciclos.mover_frontera(tercero["id"], date(2025, 6, 1)) is None
    assert ciclos.mover_frontera(tercero["id"], date(2030, 1, 1)) is None
    # Y el archivo quedó como estaba.
    assert ciclos.CicloStorage.get_ciclos("f1") == todos


# ── Borrado ───────────────────────────────────────────────────────────────────

def test_borrar_de_solo_afecta_a_su_fondo(ciclos):
    ciclos.generar_ciclos("f1", 22, date(2026, 1, 1), date(2026, 3, 5))
    ciclos.generar_ciclos("f2", 5, date(2026, 1, 1), date(2026, 3, 5))

    borrados = ciclos.CicloStorage.borrar_de("f1")
    assert borrados > 0
    assert ciclos.CicloStorage.get_ciclos("f1") == []
    assert ciclos.CicloStorage.get_ciclos("f2") != []
