"""
El árbol de `contabilidad/debts/casos_arbol.py` (deudas `debe`/`debo` + pagos recibidos y
entregados) contra el motor puro `reading._construir_flujo_cuenta`.

Sin red: se le pasan listas crudas como las que devolvería Supabase.
"""
import pytest

from contabilidad.debts.casos_arbol import (NIVEL_MAX, PAGOS, cruzar, generar,
                                            listas_crudas)
from contabilidad.debts.reading import _construir_flujo_cuenta

CASOS = generar()
IDS = [c.code for c in CASOS]


@pytest.fixture(scope="module", params=CASOS, ids=IDS)
def caso(request):
    return request.param


@pytest.fixture(scope="module")
def motor():
    return _construir_flujo_cuenta


def _estado_motor(c):
    return _construir_flujo_cuenta(*listas_crudas(c))


# ── El saldo ────────────────────────────────────────────────────────────────
def test_neto_es_la_suma_de_los_movimientos(caso):
    """Deuda 'debe' suma, 'debo' resta; pago recibido resta, pago entregado suma."""
    assert caso.neto == pytest.approx(sum(m.signo for m in caso.movs), abs=0.011)


def test_estado_reproduce_el_neto(caso):
    """El estado (pendientes + créditos) tiene que dar el mismo neto que el ledger."""
    assert caso.estado.neto == pytest.approx(caso.neto, abs=0.011)


def test_paridad_con_el_motor(caso):
    """Invariante 1 del plan: neto del motor == ledger == neto esperado del caso."""
    est = _estado_motor(caso)
    movs = est["movimientos"]
    ledger = movs[0]["saldo_acumulado"] if movs else 0.0
    assert est["resumen"]["neto"] == pytest.approx(caso.neto, abs=0.011)
    assert ledger == pytest.approx(caso.neto, abs=0.011)


def test_saldo_a_favor_coincide_con_el_motor(caso):
    """Los créditos del árbol son los mismos `saldo_favor` que calcula reading.py."""
    r = _estado_motor(caso)["resumen"]
    est = caso.estado
    assert r["saldo_favor"] == pytest.approx(est.credito_deudor, abs=0.011)
    assert r["saldo_favor_owner"] == pytest.approx(est.credito_owner, abs=0.011)


def test_pendiente_coincide_con_el_motor(caso):
    r = _estado_motor(caso)["resumen"]
    est = caso.estado
    assert r["total_te_deben"] == pytest.approx(est.pend_debe, abs=0.011)
    assert r["total_tu_debes"] == pytest.approx(est.pend_debo, abs=0.011)


# ── Pagos: las tres salidas ─────────────────────────────────────────────────
def test_reparto_de_cada_pago(caso):
    """Un pago abona su lado y lo que sobra es crédito; nunca abona de más."""
    est = caso.estado
    assert len(est.aplicaciones) == len(caso.pagos)
    for ap in est.aplicaciones:
        assert ap.aplicado + ap.sobrante == pytest.approx(ap.monto, abs=0.011)
        assert ap.sobrante >= -0.011
        lado = "debe" if ap.direccion == "recibido" else "debo"
        for idx, _, monto in ap.abonos:
            assert monto > 0.005
            assert caso.movs[idx].tipo == "deuda"
            assert caso.movs[idx].direccion == lado   # solo abona su propio lado


def test_salida_del_pago_coincide_con_su_etiqueta(caso):
    """E/P exacto · F/Q insuficiente · G/R en exceso."""
    est = caso.estado
    for ap in est.aplicaciones:
        etiqueta = caso.movs[ap.idx].etiqueta
        if etiqueta not in PAGOS:
            continue
        _, salida_esperada = PAGOS[etiqueta]
        # Un pago "exacto" contra un lado sin nada pendiente degenera en exceso; el
        # generador solo emite la etiqueta de exceso en ese caso, así que no hay choque.
        assert ap.salida == salida_esperada, f"{caso.code}: {etiqueta} dio {ap.salida}"


def test_pago_exacto_no_deja_nada(caso):
    for ap in caso.estado.aplicaciones:
        if ap.salida != "exacto":
            continue
        assert ap.sobrante <= 0.005
        assert not ap.parciales


def test_pago_insuficiente_deja_parciales_visibles(caso):
    """Lo que pidió el usuario: si no alcanza, la deuda vuelve a salir como parcial."""
    for ap in caso.estado.aplicaciones:
        if ap.salida != "insuficiente":
            continue
        assert ap.parciales, "un pago insuficiente tiene que dejar algo abierto"
        assert ap.sobrante <= 0.005
        lado = "debe" if ap.direccion == "recibido" else "debo"
        for idx, _, restante, _tocada in ap.parciales:
            assert restante > 0.005
            assert caso.movs[idx].tipo == "deuda"
            assert caso.movs[idx].direccion == lado


def test_pago_en_exceso_deja_saldo_a_favor(caso):
    for ap in caso.estado.aplicaciones:
        if ap.salida != "exceso":
            continue
        assert ap.sobrante > 0.005
        assert not ap.parciales   # si sobró, es que cerró todo lo que había


def test_creditos_no_conviven_con_pendiente_del_mismo_lado(caso):
    """El crédito cancela contra su propio lado: no pueden quedar los dos vivos."""
    est = caso.estado
    if est.credito_deudor > 0.005:
        assert est.pend_debe <= 0.005
    if est.credito_owner > 0.005:
        assert est.pend_debo <= 0.005


def test_el_arbol_ejercita_las_tres_salidas():
    salidas = {ap.salida for c in CASOS for ap in c.estado.aplicaciones}
    assert salidas == {"exacto", "insuficiente", "exceso"}
    direcciones = {ap.direccion for c in CASOS for ap in c.estado.aplicaciones}
    assert direcciones == {"recibido", "doy"}


# ── Cruce de cuentas ────────────────────────────────────────────────────────
def test_cruce_compensa_el_menor_de_los_pendientes(caso):
    x = cruzar(caso)
    est = caso.estado
    assert x.total_debe == pytest.approx(est.pend_debe, abs=0.011)
    assert x.total_debo == pytest.approx(est.pend_debo, abs=0.011)
    assert x.cruzado == pytest.approx(min(est.pend_debe, est.pend_debo), abs=0.011)
    assert x.cruzado == pytest.approx(sum(e.monto for e in x.emparejamientos), abs=0.011)


def test_cruce_conserva_el_saldo(caso):
    x = cruzar(caso)
    assert x.saldo_final == pytest.approx(caso.neto, abs=0.011)
    vivo = sum(d.restante if d.direccion == "debe" else -d.restante for d in x.deudas)
    vivo += -x.credito_deudor + x.credito_owner
    assert vivo == pytest.approx(caso.neto, abs=0.011)


def test_cruce_por_deuda(caso):
    x = cruzar(caso)
    for d in x.deudas:
        assert d.pagado + d.cruzado <= d.monto + 0.011
        assert d.restante == pytest.approx(d.monto - d.pagado - d.cruzado, abs=0.011)
    for direccion in ("debe", "debo"):
        aporte = sum(d.cruzado for d in x.deudas if d.direccion == direccion)
        assert aporte == pytest.approx(x.cruzado, abs=0.011)


def test_cruce_deja_vivo_un_solo_lado(caso):
    x = cruzar(caso)
    lados = {d.direccion for d in x.restantes}
    assert len(lados) <= 1


def test_cruce_estados(caso):
    x = cruzar(caso)
    for d in x.deudas:
        if d.monto <= 0.005:
            assert d.estado == "VACÍA"
        elif d.restante <= 0.005:
            assert d.estado in ("CRUZADA", "PAGADA")
        elif d.cruzado > 0.005 or d.pagado > 0.005:
            assert d.estado == "PARCIAL"
        else:
            assert d.estado == "INTACTA"


def test_cruce_hay_parciales_en_el_arbol():
    estados = [d.estado for c in CASOS for d in cruzar(c).deudas]
    for esperado in ("PARCIAL", "CRUZADA", "INTACTA", "PAGADA"):
        assert estados.count(esperado) > 0, f"el árbol no ejercita {esperado}"


# ── Propiedades del árbol en sí ─────────────────────────────────────────────
def test_arbol_respeta_los_cortes():
    for c in CASOS:
        assert c.nivel <= NIVEL_MAX
        if len(c.ruta) >= 3:
            repetido = c.ruta[-1] == c.ruta[-2]
            assert not (repetido and c.hijos), f"{c.code} repite etiqueta y aun así expande"


def test_etiquetas_de_deuda_coinciden_con_su_definicion():
    por_code = {c.code: c for c in CASOS}
    for c in CASOS:
        if not c.padre or c.padre not in por_code or c.etiqueta in PAGOS:
            continue
        padre, nueva = por_code[c.padre], c.movs[-1]
        if c.etiqueta in ("X", "Y"):
            assert padre.brecha == pytest.approx(0, abs=0.005)
        elif c.etiqueta == "M":
            assert (nueva.signo > 0) == (padre.neto > 0)
            assert abs(c.neto) > abs(padre.neto)
        elif c.etiqueta == "S":
            assert nueva.monto > padre.brecha and (c.neto > 0) != (padre.neto > 0)
        elif c.etiqueta == "I":
            assert c.neto == pytest.approx(0, abs=0.011)
        elif c.etiqueta == "N":
            assert 0 < nueva.monto < padre.brecha
            assert (c.neto > 0) == (padre.neto > 0)


def test_hay_casos_en_todos_los_niveles():
    assert {c.nivel for c in CASOS} == set(range(1, NIVEL_MAX + 1))



# ── Dónde se coloca cada pago en el ledger ──────────────────────────────────
# Un pago no va por su fecha: va justo después de la última deuda que pagó o cruzó. Es la
# única referencia que no depende del reloj de quien escribió la fila (`fecha_gasto` y
# `fecha_pago` son DATE, y la app y el servidor no comparten zona horaria).
HOY = "2026-07-27"
MANANA = "2026-07-28"


def _deuda(id_, monto, mia, fecha=HOY, ts="12:00:00"):
    return {'id': id_, 'titulo': id_, 'monto': monto, 'es_mi_deuda': mia,
            'fecha_gasto': fecha, 'created_at': f"{fecha}T{ts}+00:00"}


def _pago(id_, monto, mio, fecha=HOY, ts="12:00:00", comp=False, cruce_id=None):
    return {'id': id_, 'monto_total': monto, 'es_mi_pago': mio, 'fecha_pago': fecha,
            'es_compensacion': comp, 'cruce_id': cruce_id,
            'created_at': f"{fecha}T{ts}+00:00"}


def _det(pago_id, deuda_id, monto):
    return {'pago_id': pago_id, 'deuda_id': deuda_id, 'monto_asignado': monto}


def _ronda(n, ts_deuda, ts_pago):
    """
    Una ronda como las de las pruebas a mano: te debe 10, le debo 12, se cruzan 10 y con
    un pago físico de 2 se cierra lo que quedó. El cruce y el pago comparten instante,
    igual que los escribe `registrar_pago` en una sola transacción.
    """
    a, b, cruce = f"d{n}a", f"d{n}b", f"c{n}"
    deudas = [_deuda(a, 10.0, False, ts=ts_deuda), _deuda(b, 12.0, True, ts=ts_deuda)]
    pagos = [_pago(f"p{n}x", 10.0, True, ts=ts_pago, comp=True, cruce_id=cruce),
             _pago(f"p{n}y", 10.0, False, ts=ts_pago, comp=True, cruce_id=cruce),
             _pago(f"f{n}", 2.0, True, ts=ts_pago)]
    det = [_det(f"p{n}x", b, 10.0), _det(f"p{n}y", a, 10.0), _det(f"f{n}", b, 2.0)]
    return deudas, pagos, det


def _dia_de_pruebas():
    """Dos rondas seguidas el mismo día: deudas, cruce+pago, deudas, cruce+pago."""
    d1, p1, x1 = _ronda(1, "19:04:00", "19:05:00")
    d2, p2, x2 = _ronda(2, "19:08:00", "19:09:00")
    return d1 + d2, p1 + p2, x1 + x2


def test_cada_pago_queda_pegado_a_las_deudas_que_salda():
    est = _construir_flujo_cuenta(*_dia_de_pruebas())
    # De presente a pasado: pago, su cruce, las dos deudas de esa ronda, y otra vez.
    assert [m['tipo'] for m in est['movimientos']] == [
        'pago', 'cruce', 'deuda', 'deuda',
        'pago', 'cruce', 'deuda', 'deuda',
    ]
    assert [m['concepto'] for m in est['movimientos'][2:4]] == ['d2b', 'd2a']


def test_el_pago_de_manana_se_coloca_entre_las_deudas_de_ayer():
    """Lo que manda es a qué deudas fue el pago, no cuándo se hizo."""
    deudas = [_deuda("ayer1", 10.0, False, fecha=HOY, ts="09:00:00"),
              _deuda("ayer2", 5.0, False, fecha=HOY, ts="10:00:00"),
              _deuda("hoy1", 8.0, False, fecha=MANANA, ts="09:00:00")]
    pagos = [_pago("pago_tardio", 15.0, False, fecha=MANANA, ts="23:00:00")]
    det = [_det("pago_tardio", "ayer1", 10.0), _det("pago_tardio", "ayer2", 5.0)]

    est = _construir_flujo_cuenta(deudas, pagos, det)
    # Presente→pasado: la deuda nueva arriba, y el pago cerrando el bloque de ayer.
    assert [m['concepto'] for m in est['movimientos']] == [
        'hoy1', 'Pago recibido', 'ayer2', 'ayer1',
    ]


def test_un_pago_sin_deudas_se_coloca_por_su_fecha():
    """Si no abonó a nada (quedó como saldo a favor) no hay ancla: manda su fecha."""
    deudas = [_deuda("ayer", 10.0, False, fecha=HOY),
              _deuda("hoy", 8.0, False, fecha=MANANA)]
    est = _construir_flujo_cuenta(deudas, [_pago("suelto", 3.0, False, fecha=HOY)], [])
    assert [m['concepto'] for m in est['movimientos']] == ['hoy', 'Pago recibido', 'ayer']
    assert est['resumen']['saldo_favor'] == pytest.approx(0.0)  # se abona a las pendientes


def test_dos_cruces_del_mismo_dia_no_se_funden():
    est = _construir_flujo_cuenta(*_dia_de_pruebas())
    cruces = [m for m in est['movimientos'] if m['tipo'] == 'cruce']
    assert len(cruces) == 2
    for c in cruces:
        assert c['monto_cruzado'] == pytest.approx(10.0)
    # Cada cruce queda atado al pago físico de SU ronda, no al primero del día.
    assert {c['pago_vinculado']['id'] for c in cruces} == {'f1', 'f2'}


def test_sin_created_at_el_orden_no_se_rompe():
    """Los CSV de mock no traen `created_at`: el ledger sigue armándose."""
    deudas, pagos, det = _dia_de_pruebas()
    for fila in deudas + pagos:
        fila.pop('created_at')
    est = _construir_flujo_cuenta(deudas, pagos, det)
    assert len(est['movimientos']) == len(deudas) + len(pagos) - 2  # los 2 cruces se funden
    assert est['resumen']['neto'] == pytest.approx(0.0)
