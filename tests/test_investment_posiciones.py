"""
test_investment_posiciones.py — Persistencia y reconciliación de posiciones de inversión.

Cubre `storage/investments_storage.py` y `services/investments/posiciones.py`.
Todo corre contra CSVs en `tmp_path`: ni los archivos del usuario ni el pipeline real
se tocan (los tests de reconciliación pasan su propio DataFrame).
"""
import pandas as pd
import pytest
from unittest.mock import patch

from contabilidad.backend.services.investments import posiciones as svc


APERTURA = "CERTIFICADO DE DEPOSITO"
CANCELACION = "CANCELACION PLAZO FIJO"
RETENCION = "RETENCION 2% RENDIMIENTO FINANCIERO"


@pytest.fixture
def storage(tmp_path):
    """Apunta los CSV de inversiones y de grupos/pagos a tmp_path."""
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
        name="Inversiones_Mias", group_type="fixed", es_inversion=True
    )


def plazo_fijo(fecha_apertura="2025-01-10", fecha_cierre="2025-02-10", capital=1000.0,
               interes=10.0, retencion=0.2, **extra):
    movimientos = [
        {"fecha": fecha_apertura, "tipo": "aporte", "monto": capital},
    ]
    if fecha_cierre:
        movimientos += [
            {"fecha": fecha_cierre, "tipo": "retiro", "monto": capital},
            {"fecha": fecha_cierre, "tipo": "interes", "monto": interes},
            {"fecha": fecha_cierre, "tipo": "retencion", "monto": retencion},
        ]
    return {
        "tipo": "plazo_fijo",
        "origen": "manual",
        "fecha_apertura": fecha_apertura,
        "fecha_cierre": fecha_cierre,
        "movimientos": movimientos,
        **extra,
    }


def make_df(rows):
    """`rows` es una lista de (fecha, descripcion, monto)."""
    return pd.DataFrame({
        "id": [f"tx{i:03d}" for i in range(len(rows))],
        "FECHA": pd.to_datetime([r[0] for r in rows], format="mixed"),
        "DESCRIPCION": [r[1] for r in rows],
        "MONTO": [float(r[2]) for r in rows],
    })


# ── CRUD ─────────────────────────────────────────────────────────────────────

def test_crear_y_leer_posicion(storage):
    creada = svc.create_position(plazo_fijo())

    assert creada["id"]
    assert creada["estado"] == "cerrada"
    assert len(creada["movimientos"]) == 4

    leida = svc.get_position(creada["id"])
    assert leida["id"] == creada["id"]
    assert leida["capital"] == 1000.0


def test_estado_se_deriva_de_la_fecha_de_cierre(storage):
    abierta = svc.create_position(plazo_fijo(fecha_cierre=None))
    assert abierta["estado"] == "abierta"
    assert abierta["dias"] is None


def test_institucion_por_defecto(storage):
    creada = svc.create_position(plazo_fijo())
    assert creada["institucion"] == "Pichincha"


def test_actualizar_posicion_conserva_los_movimientos(storage):
    creada = svc.create_position(plazo_fijo())
    actualizada = svc.update_position(creada["id"], {"nota": "revisada"})

    assert actualizada["nota"] == "revisada"
    assert len(actualizada["movimientos"]) == 4
    assert actualizada["capital"] == 1000.0


def test_actualizar_movimientos_los_reemplaza(storage):
    creada = svc.create_position(plazo_fijo())
    actualizada = svc.update_position(creada["id"], {
        "movimientos": [{"fecha": "2025-01-10", "tipo": "aporte", "monto": 500}],
    })

    assert len(actualizada["movimientos"]) == 1
    assert actualizada["capital"] == 500.0


def test_reabrir_una_posicion_recalcula_el_estado(storage):
    creada = svc.create_position(plazo_fijo())
    reabierta = svc.update_position(creada["id"], {"fecha_cierre": None})
    assert reabierta["estado"] == "abierta"


def test_actualizar_posicion_inexistente_devuelve_none(storage):
    assert svc.update_position("no-existe", {"nota": "x"}) is None


def test_borrar_posicion_arrastra_sus_movimientos(storage):
    creada = svc.create_position(plazo_fijo())
    assert svc.delete_position(creada["id"]) is True
    assert svc.list_positions() == []
    assert storage.get_movements() == []


def test_borrar_posicion_inexistente_devuelve_false(storage):
    assert svc.delete_position("no-existe") is False


def test_los_movimientos_de_una_posicion_no_afectan_a_otra(storage):
    primera = svc.create_position(plazo_fijo())
    segunda = svc.create_position(plazo_fijo(capital=2000.0))

    svc.update_position(segunda["id"], {"movimientos": []})

    assert len(svc.get_position(primera["id"])["movimientos"]) == 4
    assert svc.get_position(segunda["id"])["capital"] == 0.0


def test_filtrar_por_estado_y_tipo(storage):
    svc.create_position(plazo_fijo())
    svc.create_position(plazo_fijo(fecha_cierre=None))
    svc.create_position({**plazo_fijo(), "tipo": "ajuste"})

    assert len(svc.list_positions(estado="abierta")) == 1
    assert len(svc.list_positions(estado="cerrada")) == 2
    assert len(svc.list_positions(tipo="ajuste")) == 1


def test_los_tipos_no_se_pierden_al_releer(storage):
    """`plazo_pactado_dias` es int y `tasa_pactada` float, también después del CSV."""
    creada = svc.create_position(plazo_fijo(plazo_pactado_dias=30, tasa_pactada=3.0))
    leida = svc.get_position(creada["id"])

    assert leida["plazo_pactado_dias"] == 30
    assert isinstance(leida["plazo_pactado_dias"], int)
    assert leida["tasa_pactada"] == 3.0


# ── Derivados ────────────────────────────────────────────────────────────────

def test_capital_vigente_es_cero_cuando_el_dinero_volvio(storage):
    cerrada = svc.create_position(plazo_fijo())
    assert cerrada["capital"] == 1000.0
    assert cerrada["capital_vigente"] == 0.0


def test_neto_descuenta_retencion_y_comision():
    totales = svc.calcular_totales([
        {"tipo": "aporte", "monto": 1000.0},
        {"tipo": "interes", "monto": 10.0},
        {"tipo": "retencion", "monto": 0.2},
        {"tipo": "comision", "monto": 1.0},
    ])
    assert totales["neto"] == 8.8


def test_aportes_parciales_acumulan_capital(storage):
    """El caso que el esquema plano no soportaba: una posición con varios aportes."""
    creada = svc.create_position({
        "tipo": "valuada",
        "fecha_apertura": "2025-01-01",
        "movimientos": [
            {"fecha": "2025-01-01", "tipo": "aporte", "monto": 100.0},
            {"fecha": "2025-02-01", "tipo": "aporte", "monto": 250.0},
            {"fecha": "2025-03-01", "tipo": "retiro", "monto": 50.0},
        ],
    })
    assert creada["capital"] == 350.0
    assert creada["capital_vigente"] == 300.0


def test_tna_usa_dias_calendario(storage):
    creada = svc.create_position(plazo_fijo(capital=27000.0, interes=67.43,
                                            fecha_apertura="2025-11-18", fecha_cierre="2025-12-19"))
    assert creada["dias"] == 31
    assert creada["tna"] == pytest.approx(2.94, abs=0.01)


def test_tna_pactada_usa_plazo_y_base_360(storage):
    """La tasa con la que el banco liquidó: 30 días al 3 %, no los 31 del calendario."""
    creada = svc.create_position(plazo_fijo(capital=27000.0, interes=67.43,
                                            fecha_apertura="2025-11-18", fecha_cierre="2025-12-19",
                                            plazo_pactado_dias=30))
    assert creada["tna_pactada"] == pytest.approx(3.0, abs=0.01)


def test_sin_plazo_pactado_no_hay_tna_pactada(storage):
    creada = svc.create_position(plazo_fijo())
    assert creada["tna_pactada"] is None


# ── Validación ───────────────────────────────────────────────────────────────

def test_tipo_invalido(storage):
    with pytest.raises(svc.ValidationError):
        svc.create_position({**plazo_fijo(), "tipo": "cripto"})


def test_movimiento_negativo_se_rechaza(storage):
    with pytest.raises(svc.ValidationError):
        svc.create_position({
            "fecha_apertura": "2025-01-01",
            "movimientos": [{"fecha": "2025-01-01", "tipo": "aporte", "monto": -100}],
        })


def test_movimiento_sin_fecha_se_rechaza(storage):
    with pytest.raises(svc.ValidationError):
        svc.create_position({
            "fecha_apertura": "2025-01-01",
            "movimientos": [{"fecha": None, "tipo": "aporte", "monto": 100}],
        })


def test_posicion_sin_ninguna_fecha_se_rechaza(storage):
    with pytest.raises(svc.ValidationError):
        svc.create_position({"tipo": "plazo_fijo", "movimientos": []})


def test_cierre_anterior_a_la_apertura_se_rechaza(storage):
    with pytest.raises(svc.ValidationError):
        svc.create_position(plazo_fijo(fecha_apertura="2025-02-10", fecha_cierre="2025-01-10"))


def test_portafolio_inexistente_se_rechaza(storage):
    with pytest.raises(svc.ValidationError):
        svc.create_position({**plazo_fijo(), "portafolio_id": "no-existe"})


def test_portafolio_existente_se_acepta(storage, portafolio):
    creada = svc.create_position({**plazo_fijo(), "portafolio_id": portafolio["id"]})
    assert creada["portafolio_id"] == portafolio["id"]


def test_siembra_sin_apertura_conocida(storage, portafolio):
    """Las inversiones anteriores al historial solo tienen cancelación, y eso es válido."""
    creada = svc.create_position({
        "portafolio_id": portafolio["id"],
        "tipo": "plazo_fijo",
        "origen": "manual",
        "fecha_apertura": None,
        "fecha_cierre": "2024-05-29",
        "movimientos": [{"fecha": "2024-05-29", "tipo": "retiro", "monto": 10100.0}],
    })
    assert creada["estado"] == "cerrada"
    assert creada["dias"] is None


# ── Portafolios ──────────────────────────────────────────────────────────────

def test_list_portfolios_incluye_los_marcados(storage, portafolio):
    portafolios = svc.list_portfolios()
    assert [p["id"] for p in portafolios] == [portafolio["id"]]
    assert portafolios[0]["posiciones"] == 0


def test_list_portfolios_cuenta_posiciones(storage, portafolio):
    svc.create_position({**plazo_fijo(), "portafolio_id": portafolio["id"]})
    assert svc.list_portfolios()[0]["posiciones"] == 1


def test_list_portfolios_incluye_grupos_no_marcados_con_posiciones(storage):
    """Un grupo sin la bandera pero con posiciones apuntándole no puede desaparecer de la UI."""
    from contabilidad.backend.storage.variables_storage import InterpolationStorage
    grupo = InterpolationStorage.create_group(name="Suelto", group_type="fixed")
    svc.create_position({**plazo_fijo(), "portafolio_id": grupo["id"]})

    portafolios = svc.list_portfolios()
    assert [p["id"] for p in portafolios] == [grupo["id"]]
    assert portafolios[0]["es_inversion"] is False


def test_list_portfolios_ignora_grupos_sin_relacion(storage):
    from contabilidad.backend.storage.variables_storage import InterpolationStorage
    InterpolationStorage.create_group(name="Comida", group_type="fixed", es_fondo=True)
    assert svc.list_portfolios() == []


# ── Reconciliación ───────────────────────────────────────────────────────────

DF_UN_PLAZO_FIJO = [
    ("2025-01-10", APERTURA, -1000.0),
    ("2025-02-10 09:00", CANCELACION, 1000.0),
    ("2025-02-10 09:00", "TRANSFERENCIA INTERIOR", 10.0),
    ("2025-02-10 09:00", RETENCION, -0.2),
]


def test_reconcile_no_escribe_nada(storage):
    diff = svc.reconcile(make_df(DF_UN_PLAZO_FIJO))

    assert diff["resumen"]["nuevas"] == 1
    assert svc.list_positions() == []


def test_apply_detection_crea_la_posicion(storage):
    df = make_df(DF_UN_PLAZO_FIJO)
    resultado = svc.apply_detection(df=df)

    assert resultado["resumen"]["creadas"] == 1
    creada = svc.list_positions()[0]
    assert creada["origen"] == "detectado"
    assert creada["capital"] == 1000.0
    assert creada["interes"] == 10.0
    assert creada["retencion"] == 0.2
    assert creada["tx_apertura_id"] == "tx000"


def test_apply_detection_es_idempotente(storage):
    df = make_df(DF_UN_PLAZO_FIJO)
    svc.apply_detection(df=df)
    segunda = svc.apply_detection(df=df)

    assert segunda["resumen"]["creadas"] == 0
    assert len(svc.list_positions()) == 1
    assert svc.reconcile(df)["resumen"]["iguales"] == 1


def test_apply_detection_asigna_portafolio(storage, portafolio):
    df = make_df(DF_UN_PLAZO_FIJO)
    svc.apply_detection(df=df, portafolio_id=portafolio["id"])
    assert svc.list_positions()[0]["portafolio_id"] == portafolio["id"]


def test_apply_detection_asignacion_puntual_gana(storage, portafolio):
    from contabilidad.backend.storage.variables_storage import InterpolationStorage
    otro = InterpolationStorage.create_group(name="Uni", group_type="fixed", es_inversion=True)

    df = make_df(DF_UN_PLAZO_FIJO)
    svc.apply_detection(df=df, portafolio_id=portafolio["id"], asignaciones={"tx000": otro["id"]})

    assert svc.list_positions()[0]["portafolio_id"] == otro["id"]


def test_apply_detection_portafolio_inexistente_se_rechaza(storage):
    with pytest.raises(svc.ValidationError):
        svc.apply_detection(df=make_df(DF_UN_PLAZO_FIJO), portafolio_id="no-existe")


def test_apply_detection_respeta_la_seleccion(storage):
    df = make_df(DF_UN_PLAZO_FIJO + [
        ("2025-03-01", APERTURA, -500.0),
        ("2025-04-01", CANCELACION, 500.0),
    ])
    resultado = svc.apply_detection(tx_apertura_ids=["tx000"], df=df)

    assert resultado["resumen"]["creadas"] == 1
    assert svc.reconcile(df)["resumen"]["nuevas"] == 1


def test_reconcile_marca_como_cambiada_una_posicion_con_otro_monto(storage):
    df = make_df(DF_UN_PLAZO_FIJO)
    svc.apply_detection(df=df)
    posicion = svc.list_positions()[0]
    svc.update_position(posicion["id"], {
        "movimientos": [{"fecha": "2025-01-10", "tipo": "aporte", "monto": 999.0}],
    })

    diff = svc.reconcile(df)
    assert diff["resumen"]["cambiadas"] == 1
    assert "capital" in diff["cambiadas"][0]["cambios"]


def test_apply_detection_repara_la_posicion_cambiada(storage):
    df = make_df(DF_UN_PLAZO_FIJO)
    svc.apply_detection(df=df)
    posicion = svc.list_positions()[0]
    svc.update_position(posicion["id"], {"movimientos": []})

    resultado = svc.apply_detection(df=df)
    assert resultado["resumen"]["actualizadas"] == 1
    assert svc.list_positions()[0]["capital"] == 1000.0


def test_apply_detection_no_pisa_una_posicion_manual(storage):
    """La siembra manual es la única información que no está en el banco."""
    df = make_df(DF_UN_PLAZO_FIJO)
    svc.apply_detection(df=df)
    posicion = svc.list_positions()[0]
    svc.update_position(posicion["id"], {"origen": "manual", "movimientos": []})

    resultado = svc.apply_detection(df=df)
    assert resultado["resumen"]["actualizadas"] == 0
    assert resultado["omitidas"][0]["posicion_id"] == posicion["id"]
    assert svc.list_positions()[0]["capital"] == 0.0


def test_incluir_cambiadas_false_solo_crea(storage):
    df = make_df(DF_UN_PLAZO_FIJO)
    svc.apply_detection(df=df)
    posicion = svc.list_positions()[0]
    svc.update_position(posicion["id"], {"movimientos": []})

    resultado = svc.apply_detection(df=df, incluir_cambiadas=False)
    assert resultado["resumen"] == {"creadas": 0, "actualizadas": 0, "omitidas": 0}


def test_reconcile_reporta_huerfanas_sin_cubrir(storage):
    df = make_df([("2024-05-29", CANCELACION, 10100.0)])
    diff = svc.reconcile(df)

    assert diff["resumen"]["huerfanas"] == 1
    assert diff["huerfanas"][0]["capital_sugerido"] == 10100.0


def test_una_siembra_manual_tapa_la_huerfana(storage):
    """Sembrada la posición, la cancelación deja de pedir atención."""
    df = make_df([("2024-05-29", CANCELACION, 10100.0)])
    svc.create_position({
        "tipo": "plazo_fijo",
        "origen": "manual",
        "fecha_cierre": "2024-05-29",
        "tx_cierre_id": "tx000",
        "movimientos": [{"fecha": "2024-05-29", "tipo": "retiro", "monto": 10100.0, "tx_id": "tx000"}],
    })

    assert svc.reconcile(df)["resumen"]["huerfanas"] == 0


def test_reconcile_avisa_de_posiciones_que_el_banco_ya_no_tiene(storage):
    df = make_df(DF_UN_PLAZO_FIJO)
    svc.apply_detection(df=df)

    diff = svc.reconcile(make_df([("2025-01-10", "OTRA COSA", -50.0)]))
    assert diff["resumen"]["solo_guardadas"] == 1


def test_una_posicion_manual_nunca_sale_como_solo_guardada(storage):
    svc.create_position(plazo_fijo())
    diff = svc.reconcile(make_df([("2025-01-10", "OTRA COSA", -50.0)]))
    assert diff["resumen"]["solo_guardadas"] == 0


# ── Sugerencia de portafolio ─────────────────────────────────────────────────

def crear_portafolio(nombre, pagos, es_custodia=False):
    """Portafolio con su cadena de pagos: `pagos` es una lista de (monto, inicio, fin)."""
    from contabilidad.backend.storage.variables_storage import InterpolationStorage
    grupo = InterpolationStorage.create_group(
        name=nombre, group_type="fixed", es_inversion=True, es_custodia=es_custodia
    )
    for monto, inicio, fin in pagos:
        InterpolationStorage.create_payment(grupo["id"], monto, inicio, fin, nombre)
    return grupo


def test_sugiere_el_portafolio_con_las_dos_fronteras(storage):
    """La cadena de residuales cambia exactamente el día que se abre o se cierra un CDT."""
    from contabilidad.backend.services.investments import portafolios

    mias = crear_portafolio("Mias", [(5000.0, "2025-01-10", "2025-02-10")])
    crear_portafolio("Uni", [(300.0, "2025-06-01", "2025-07-01")])

    diff = svc.reconcile(make_df(DF_UN_PLAZO_FIJO))
    sugerencia = diff["nuevas"][0]["sugerencia"]

    assert sugerencia["sugerido"] == mias["id"]
    assert sugerencia["reparto"] is False
    assert portafolios.SCORE_COMPLETO == 2


def test_una_sola_frontera_no_le_gana_a_dos(storage):
    mias = crear_portafolio("Mias", [(5000.0, "2025-01-10", "2025-02-10")])
    crear_portafolio("Uni", [(300.0, "2025-01-10", "2025-09-01")])

    diff = svc.reconcile(make_df(DF_UN_PLAZO_FIJO))
    assert diff["nuevas"][0]["sugerencia"]["sugerido"] == mias["id"]


def test_dos_portafolios_con_las_dos_fronteras_piden_reparto(storage):
    """Es el CDT que juntó plata de dos portafolios: nadie decide eso por el usuario."""
    crear_portafolio("Mias", [(5000.0, "2025-01-10", "2025-02-10")])
    crear_portafolio("Madre", [(2000.0, "2025-01-10", "2025-02-10")])

    sugerencia = svc.reconcile(make_df(DF_UN_PLAZO_FIJO))["nuevas"][0]["sugerencia"]

    assert sugerencia["reparto"] is True
    assert sugerencia["sugerido"] is None
    assert len(sugerencia["reparto_sugerido"]) == 2


def test_el_aporte_estimado_sale_del_residual(storage):
    """Lo que un portafolio puso es su residual del día anterior menos el del día."""
    crear_portafolio("Mias", [(1000.0, "2024-12-01", "2025-01-10"), (200.0, "2025-01-10", "2025-02-10")])

    sugerencia = svc.reconcile(make_df(DF_UN_PLAZO_FIJO))["nuevas"][0]["sugerencia"]
    assert sugerencia["candidatos"][0]["aporte_estimado"] == 800.0


def test_sin_portafolios_marcados_no_hay_sugerencia(storage):
    assert svc.reconcile(make_df(DF_UN_PLAZO_FIJO))["nuevas"][0]["sugerencia"] is None


def test_apply_detection_usa_la_sugerencia(storage):
    mias = crear_portafolio("Mias", [(5000.0, "2025-01-10", "2025-02-10")])
    svc.apply_detection(df=make_df(DF_UN_PLAZO_FIJO), usar_sugerencias=True)
    assert svc.list_positions()[0]["portafolio_id"] == mias["id"]


def test_apply_detection_no_asigna_cuando_hay_que_repartir(storage):
    crear_portafolio("Mias", [(5000.0, "2025-01-10", "2025-02-10")])
    crear_portafolio("Madre", [(2000.0, "2025-01-10", "2025-02-10")])

    svc.apply_detection(df=make_df(DF_UN_PLAZO_FIJO), usar_sugerencias=True)
    assert svc.list_positions()[0]["portafolio_id"] is None


def test_la_asignacion_explicita_le_gana_a_la_sugerencia(storage):
    crear_portafolio("Mias", [(5000.0, "2025-01-10", "2025-02-10")])
    otro = crear_portafolio("Uni", [])

    svc.apply_detection(df=make_df(DF_UN_PLAZO_FIJO), usar_sugerencias=True,
                        asignaciones={"tx000": otro["id"]})
    assert svc.list_positions()[0]["portafolio_id"] == otro["id"]


# ── Reparto ──────────────────────────────────────────────────────────────────

def test_split_reparte_capital_e_interes(storage):
    a = crear_portafolio("Mias", [])
    b = crear_portafolio("Madre", [])
    original = svc.create_position(plazo_fijo(capital=1000.0, interes=10.0, retencion=0.2))

    partes = svc.split_position(original["id"], [
        {"portafolio_id": a["id"], "capital": 750.0},
        {"portafolio_id": b["id"], "capital": 250.0},
    ])

    assert [p["capital"] for p in partes] == [750.0, 250.0]
    assert [p["interes"] for p in partes] == [7.5, 2.5]
    assert svc.get_position(original["id"]) is None
    assert all(p["origen"] == "manual" for p in partes)


def test_split_acepta_interes_explicito(storage):
    a = crear_portafolio("Mias", [])
    b = crear_portafolio("Madre", [])
    original = svc.create_position(plazo_fijo(capital=1000.0, interes=10.0))

    partes = svc.split_position(original["id"], [
        {"portafolio_id": a["id"], "capital": 500.0, "interes": 8.0},
        {"portafolio_id": b["id"], "capital": 500.0, "interes": 2.0},
    ])
    assert [p["interes"] for p in partes] == [8.0, 2.0]


def test_split_exige_que_las_partes_sumen_el_capital(storage):
    original = svc.create_position(plazo_fijo(capital=1000.0))
    with pytest.raises(svc.ValidationError):
        svc.split_position(original["id"], [{"capital": 400.0}, {"capital": 400.0}])


def test_split_necesita_al_menos_dos_partes(storage):
    original = svc.create_position(plazo_fijo(capital=1000.0))
    with pytest.raises(svc.ValidationError):
        svc.split_position(original["id"], [{"capital": 1000.0}])


def test_split_de_una_posicion_inexistente_devuelve_vacio(storage):
    assert svc.split_position("no-existe", [{"capital": 1.0}, {"capital": 1.0}]) == []


def test_las_hermanas_siguen_cuadrando_contra_el_banco(storage):
    """Repartir no puede convertir un certificado correcto en una discrepancia."""
    df = make_df(DF_UN_PLAZO_FIJO)
    svc.apply_detection(df=df)
    original = svc.list_positions()[0]

    a = crear_portafolio("Mias", [])
    b = crear_portafolio("Madre", [])
    svc.split_position(original["id"], [
        {"portafolio_id": a["id"], "capital": 600.0},
        {"portafolio_id": b["id"], "capital": 400.0},
    ])

    diff = svc.reconcile(df)
    assert diff["resumen"]["iguales"] == 1
    assert diff["resumen"]["nuevas"] == 0
    assert len(diff["iguales"][0]["posicion_ids"]) == 2


def test_el_detector_no_pisa_un_reparto(storage):
    df = make_df(DF_UN_PLAZO_FIJO)
    svc.apply_detection(df=df)
    original = svc.list_positions()[0]
    svc.split_position(original["id"], [{"capital": 600.0}, {"capital": 400.0}])

    # Se rompe una parte a propósito: el diff debe verlo, pero no repararlo solo.
    partes = svc.list_positions()
    svc.update_position(partes[0]["id"], {"movimientos": []})

    resultado = svc.apply_detection(df=df)
    assert resultado["resumen"]["actualizadas"] == 0
    assert resultado["omitidas"][0]["motivo"] == "origen manual"


# ── Resumen y evolución ──────────────────────────────────────────────────────

def test_summary_reune_kpis_y_anios(storage, portafolio):
    svc.create_position({**plazo_fijo(), "portafolio_id": portafolio["id"]})
    resumen = svc.get_summary()

    assert resumen["global"]["capital_rotado"] == 1000.0
    assert resumen["por_portafolio"][0]["nombre"] == "Inversiones_Mias"
    assert resumen["por_anio"][0]["anio"] == 2025


def test_timeline_devuelve_serie_y_eventos(storage):
    svc.create_position(plazo_fijo())
    serie = svc.get_timeline()

    assert len(serie["fechas"]) == len(serie["capital"]) > 0
    assert len(serie["eventos"]) == 2
