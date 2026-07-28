"""
Modulo de lectura de deudas desde Supabase.
Proporciona funciones para obtener datos limpios de deudas en formato DataFrame.
"""

import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from typing import Optional, List
import os

from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

# Credenciales de Supabase
SUPABASE_URL = "https://rcmdzvbxerumzxvnubfo.supabase.co"
SUPABASE_KEY = "sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw"

# Cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def obtener_todos_deudores() -> pd.DataFrame:
    """
    Obtiene todos los deudores registrados.
    
    Returns:
        DataFrame con columnas: id, nombre, token, created_at
    """
    response = supabase.table('deudores').select('*').where('nombre', '!=', '').execute()
    
    if not response.data:
        return pd.DataFrame(columns=['id', 'nombre', 'token', 'created_at'])
    
    df = pd.DataFrame(response.data)
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    return df


def listar_deudores() -> pd.DataFrame:
    """
    Lista simple de deudores (id, nombre) para poblar selects en el frontend.
    Robusta ante nombres vacíos. Soporta MOCK_MODE derivando de las deudas mock.
    """
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        mock_path = os.path.join(base_dir, "data_mock", "sistema", "deudas", "deudas.csv")
        if os.path.exists(mock_path):
            m = pd.read_csv(mock_path)
            if {'deudor_id', 'deudor_nombre'}.issubset(m.columns):
                d = m[['deudor_id', 'deudor_nombre']].drop_duplicates()
                d = d.rename(columns={'deudor_id': 'id', 'deudor_nombre': 'nombre'})
                return d.sort_values('nombre').reset_index(drop=True)
        return pd.DataFrame(columns=['id', 'nombre'])

    response = supabase.table('deudores').select('id, nombre').execute()
    if not response.data:
        return pd.DataFrame(columns=['id', 'nombre'])

    df = pd.DataFrame(response.data)
    df = df[df['nombre'].notna() & (df['nombre'].astype(str).str.strip() != '')]
    return df.sort_values('nombre').reset_index(drop=True)


def _ec_num(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _ec_fecha(v):
    return str(v)[:10] if v is not None else None


def _ec_ts(v):
    """
    `created_at` como string ordenable: es el desempate del ledger.

    `fecha_gasto` y `fecha_pago` son DATE, así que todo lo que pasa en un mismo día empata.
    Sin desempate el orden lo decide el sort estable (o sea, el orden en que Supabase
    devolvió las filas) y se ven todas las deudas juntas y todos los pagos juntos, en vez
    de la secuencia real deuda → pago → deuda → pago.
    """
    return str(v) if v is not None else ''


def _operaciones_de_pago(out_pagos: list) -> dict:
    """
    Agrupa los pagos que se escribieron en una misma operación: los dos pagos virtuales de
    un cruce y el pago físico que lo disparó. `registrar_pago` los inserta en la misma
    transacción, así que comparten `created_at` al microsegundo.

    Devuelve pago_id → clave de operación. Un pago suelto es su propia operación.
    """
    grupos = {}
    for p in out_pagos:
        grupos[p['id']] = f"cruce:{p['cruce_id']}" if p['es_compensacion'] and p['cruce_id'] \
            else f"pago:{p['id']}"

    # El pago físico se une al cruce con el que comparte instante y fecha.
    cruce_por_instante = {(p['fecha_pago'], p['creado']): grupos[p['id']]
                          for p in out_pagos if p['es_compensacion'] and p['creado']}
    for p in out_pagos:
        if p['es_compensacion']:
            continue
        clave = cruce_por_instante.get((p['fecha_pago'], p['creado']))
        if clave:
            grupos[p['id']] = clave
    return grupos


def _rango_evento(e) -> int:
    """
    Desempate final cuando ni la fecha ni `created_at` distinguen dos eventos.

    Un pago que cruza escribe los dos pagos virtuales y el pago físico en la MISMA
    transacción, y `NOW()` es el instante de la transacción: los tres comparten
    `created_at`. El orden real es deuda → cruce → pago físico.
    """
    if e['tipo'] == 'deuda':
        return 0
    return 1 if e.get('es_compensacion') else 2


def _cruce_sugerido(out_deudas: list) -> dict:
    """
    El cruce que TODAVÍA se puede hacer, sin que haya habido ningún pago.

    Es un derivado puro: no se escribe nada. Se compensa `min(Σ te deben, Σ tú debes)`
    sobre el saldo REAL de cada deuda (ya descontado el saldo a favor: si el crédito la
    cubre, cruzarla la descontaría dos veces) emparejando de la más antigua a la más
    reciente, igual que hace la app al aplicar el cruce.
    """
    vivas = [d for d in out_deudas if d['saldo_real'] > 0.01]
    lado = {False: sorted((d for d in vivas if not d['es_tu_deuda']),
                          key=lambda d: d['fecha_gasto'] or ''),
            True: sorted((d for d in vivas if d['es_tu_deuda']),
                         key=lambda d: d['fecha_gasto'] or '')}

    monto = round(min(sum(d['saldo_real'] for d in lado[False]),
                      sum(d['saldo_real'] for d in lado[True])), 2)

    items = {False: [], True: []}
    for tuya in (False, True):
        restante = monto
        for d in lado[tuya]:
            if restante <= 0.01:
                break
            aplica = round(min(d['saldo_real'], restante), 2)
            restante = round(restante - aplica, 2)
            items[tuya].append({
                'deuda_id': d['id'], 'titulo': d['titulo'],
                'fecha_gasto': d['fecha_gasto'], 'es_tu_deuda': tuya,
                'monto_original': d['monto_original'],
                'saldo_antes': d['saldo_real'],
                'aplicado': aplica,
                'pagado_acumulado': round(d['monto_original'] - d['saldo_real'] + aplica, 2),
                'saldo_despues': round(d['saldo_real'] - aplica, 2),
                'cerrada': d['saldo_real'] - aplica <= 0.01,
                'abono_saldo_favor': d['abono_saldo_favor'],
            })

    return {
        'monto': monto,
        'lados': {
            'te_deben': {'total': round(sum(i['aplicado'] for i in items[False]), 2),
                         'items': items[False]},
            'tu_debes': {'total': round(sum(i['aplicado'] for i in items[True]), 2),
                         'items': items[True]},
        },
    }


def _colapsar_cruces(eventos: list, cruce_items: dict) -> list:
    """
    Funde los pagos de compensación del mismo día en UN movimiento `tipo='cruce'`.

    La app registra un cruce como dos pagos virtuales (uno por cada lado) justo antes del
    pago físico que lo disparó. Mostrarlos sueltos no deja ver que son un solo evento con
    dos lados, así que aquí se juntan: cada lado con las deudas que tocó y cuánto se cruzó
    de cada una, y el movimiento se coloca inmediatamente antes de ese pago.

    Los dos lados se reconocen por `cruce_id`. Agrupar por fecha (como antes) fundía en un
    solo movimiento todos los cruces del mismo día: pagando dos veces hoy se veía un único
    cruce gigante. Sin `cruce_id` (filas viejas, antes del backfill) se cae a la fecha.

    `eventos` viene en orden cronológico ascendente con `saldo_acumulado` ya calculado.
    """
    from collections import defaultdict

    por_cruce = defaultdict(list)
    for i, e in enumerate(eventos):
        if e['tipo'] == 'pago' and e.get('es_compensacion'):
            por_cruce[e.get('cruce_id') or f"fecha:{e['fecha'] or ''}"].append(i)
    if not por_cruce:
        return eventos

    nuevos, descartar = {}, set()
    for _clave, idxs in por_cruce.items():
        descartar.update(idxs)
        fecha = eventos[idxs[0]]['fecha'] or ''

        items = []
        for i in idxs:
            items.extend(cruce_items.get(eventos[i]['id'], []))
        items.sort(key=lambda it: it['fecha_gasto'] or '')
        te_deben = [it for it in items if not it['es_tu_deuda']]
        tu_debes = [it for it in items if it['es_tu_deuda']]

        # El pago físico que disparó el cruce: el que viene JUSTO DESPUÉS (se escribe en la
        # misma transacción). Buscarlo por fecha en todo el día ataba el cruce al primer
        # pago del día aunque fuera de otra ronda.
        destino, vinculado = min(idxs), None
        j = max(idxs) + 1
        sig = eventos[j] if j < len(eventos) else None
        if (sig and sig['tipo'] == 'pago' and not sig.get('es_compensacion')
                and (sig['fecha'] or '') == fecha):
            destino, vinculado = j, {
                'id': sig['id'], 'concepto': sig['concepto'],
                'monto_total': sig.get('monto_total', 0.0), 'fecha': sig['fecha'],
            }

        # Saldo con el que queda la cuenta tras el cruce: el que había justo antes del
        # pago vinculado, o el del último pago virtual si el cruce quedó suelto.
        if vinculado is not None:
            saldo = round(eventos[destino]['saldo_acumulado'] - eventos[destino]['delta'], 2)
        else:
            saldo = eventos[max(idxs)]['saldo_acumulado']

        # Cada lado aporta el MISMO monto (el cruce es min(Σ debe, Σ debo)), así que el
        # monto cruzado es el de un lado, no la suma de los dos.
        tot_te_deben = round(sum(it['aplicado'] for it in te_deben), 2)
        tot_tu_debes = round(sum(it['aplicado'] for it in tu_debes), 2)

        nuevos[destino] = {
            'fecha': fecha or None, 'tipo': 'cruce',
            'id': '+'.join(eventos[i]['id'] for i in idxs),
            'concepto': 'Cruce de cuentas', 'es_tu_deuda': False,
            'delta': 0.0, 'saldo_acumulado': saldo,
            'monto_cruzado': max(tot_te_deben, tot_tu_debes),
            'pago_ids': [eventos[i]['id'] for i in idxs],
            'lados': {
                'te_deben': {'total': tot_te_deben, 'items': te_deben},
                'tu_debes': {'total': tot_tu_debes, 'items': tu_debes},
            },
            'pago_vinculado': vinculado,
            'detalle': [],
            'items': items,
            # Las que el cruce no alcanzó a saldar: vuelven a mostrarse como parciales.
            'parciales': [{
                'deuda_id': it['deuda_id'], 'titulo': it['titulo'],
                'monto_original': it['monto_original'],
                'pagado_acumulado': it['pagado_acumulado'], 'saldo': it['saldo_despues'],
            } for it in items if it['saldo_despues'] > 0.01],
        }

    salida = []
    for i, e in enumerate(eventos):
        if i in nuevos:
            salida.append(nuevos[i])
        if i not in descartar:
            salida.append(e)
    return salida


def _construir_flujo_cuenta(deudas_raw: list, pagos_raw: list, detalles: list) -> dict:
    """
    Arma el estado de cuenta completo a partir de listas crudas de deudas, pagos y
    detalle_pagos (asignaciones pago→deuda). Devuelve deudas (con qué pagos las
    abonaron), pagos (con a qué deudas fueron + sobrante), un ledger cronológico con
    saldo acumulado, y un resumen con neto y saldo a favor.

    Convención de signo del ledger (POV = dueño): las deudas "te deben" suman al saldo
    por cobrar (+), las "tú debes" restan (−), y cada asignación de pago reduce el saldo.
    """
    pago_by_id = {str(p.get('id')): p for p in pagos_raw}
    titulo_by_deuda = {str(d.get('id')): (d.get('titulo') or 'Deuda') for d in deudas_raw}

    det_by_deuda: dict = {}
    det_by_pago: dict = {}
    for det in detalles:
        det_by_deuda.setdefault(str(det.get('deuda_id')), []).append(det)
        det_by_pago.setdefault(str(det.get('pago_id')), []).append(det)

    # --- Deudas ---
    out_deudas = []
    for d in deudas_raw:
        did = str(d.get('id'))
        allocs = det_by_deuda.get(did, [])
        pagado = round(sum(_ec_num(a.get('monto_asignado')) for a in allocs), 2)
        mo = _ec_num(d.get('monto') if d.get('monto') is not None else d.get('monto_original'))
        saldo = round(mo - pagado, 2)
        estado = 'PAGADA' if saldo <= 0.01 else ('PARCIAL' if pagado > 0.01 else 'PENDIENTE')
        out_deudas.append({
            'id': did,
            'titulo': d.get('titulo') or 'Deuda',
            'fecha_gasto': _ec_fecha(d.get('fecha_gasto')),
            'creado': _ec_ts(d.get('created_at')),
            'monto_original': mo,
            'monto_pagado': pagado,
            'saldo_pendiente': max(saldo, 0.0),
            'estado': estado,
            'es_tu_deuda': bool(d.get('es_mi_deuda')),
            'pagos': [{
                'pago_id': str(a.get('pago_id')),
                'fecha_pago': _ec_fecha((pago_by_id.get(str(a.get('pago_id'))) or {}).get('fecha_pago')),
                'monto_asignado': _ec_num(a.get('monto_asignado')),
            } for a in allocs],
        })

    # --- Pagos ---
    out_pagos = []
    for p in pagos_raw:
        pid = str(p.get('id'))
        allocs = det_by_pago.get(pid, [])
        asignado = round(sum(_ec_num(a.get('monto_asignado')) for a in allocs), 2)
        mt = _ec_num(p.get('monto_total'))
        out_pagos.append({
            'id': pid,
            'fecha_pago': _ec_fecha(p.get('fecha_pago')),
            'creado': _ec_ts(p.get('created_at')),
            'monto_total': mt,
            'asignado': asignado,
            'sobrante': round(mt - asignado, 2),
            'es_mi_pago': bool(p.get('es_mi_pago')),
            'es_compensacion': bool(p.get('es_compensacion')),
            # Los dos pagos virtuales de un mismo cruce comparten este id.
            'cruce_id': str(p['cruce_id']) if p.get('cruce_id') else None,
            'deudas': [{
                'deuda_id': str(a.get('deuda_id')),
                'titulo': titulo_by_deuda.get(str(a.get('deuda_id')), '—'),
                'monto_asignado': _ec_num(a.get('monto_asignado')),
            } for a in allocs],
        })

    # --- Saldo a favor abonado a las deudas ---
    # El sobrante de un pago (dinero entregado que no se asignó a ninguna deuda) es
    # crédito de quien pagó, así que cubre automáticamente SUS deudas pendientes, de la
    # más antigua a la más reciente. Se descuenta igual que un cruce: la deuda conserva
    # su `saldo_pendiente`, y `abono_saldo_favor` dice cuánto de eso ya está cubierto.
    favor_owner = round(sum(p['sobrante'] for p in out_pagos
                            if p['sobrante'] > 0.01 and not p['es_compensacion'] and p['es_mi_pago']), 2)
    favor_debtor = round(sum(p['sobrante'] for p in out_pagos
                             if p['sobrante'] > 0.01 and not p['es_compensacion'] and not p['es_mi_pago']), 2)

    credito = {True: favor_owner, False: favor_debtor}
    for d in out_deudas:
        d['abono_saldo_favor'] = 0.0
    for d in sorted((x for x in out_deudas if x['saldo_pendiente'] > 0.01),
                    key=lambda x: x['fecha_gasto'] or ''):
        disponible = credito[d['es_tu_deuda']]
        if disponible <= 0.01:
            continue
        abono = round(min(d['saldo_pendiente'], disponible), 2)
        d['abono_saldo_favor'] = abono
        credito[d['es_tu_deuda']] = round(disponible - abono, 2)

    # Lo que quedó de crédito sin abonar a ninguna deuda
    remanente_favor_owner = credito[True]
    remanente_favor_debtor = credito[False]

    for d in out_deudas:
        d['saldo_real'] = round(d['saldo_pendiente'] - d['abono_saldo_favor'], 2)
        if d['saldo_real'] <= 0.01:
            d['estado'] = 'PAGADA'
        elif d['monto_pagado'] > 0.01 or d['abono_saldo_favor'] > 0.01:
            d['estado'] = 'PARCIAL'

    # --- Ledger cronológico (ascendente) con saldo acumulado ---
    eventos = []
    for d in out_deudas:
        sign = -1 if d['es_tu_deuda'] else 1
        eventos.append({
            'fecha': d['fecha_gasto'], 'tipo': 'deuda', 'id': d['id'],
            'orden': d['creado'],
            'concepto': d['titulo'], 'es_tu_deuda': d['es_tu_deuda'],
            'delta': round(sign * d['monto_original'], 2), 'detalle': [],
        })
    for p in out_pagos:
        # Signo del pago (POV dueño = igual que edge function get_historial):
        #  - pago recibido (no es_mi_pago): resta del saldo por el TOTAL pagado.
        #  - pago entregado (es_mi_pago): suma al saldo por el total.
        #  - compensación (cruce): NO altera el saldo (el offset ya se refleja en las
        #    deudas de ambos lados); solo se muestra como movimiento informativo.
        # Se usa monto_total (asignado + sobrante) para que el saldo a favor quede
        # reflejado como crédito del deudor.
        if p['es_compensacion']:
            concepto, delta = 'Cruce de cuentas', 0.0
        elif p['es_mi_pago']:
            concepto, delta = 'Pago entregado', round(p['monto_total'], 2)
        else:
            concepto, delta = 'Pago recibido', round(-p['monto_total'], 2)
        eventos.append({
            'fecha': p['fecha_pago'], 'tipo': 'pago', 'id': p['id'],
            'orden': p['creado'], 'cruce_id': p['cruce_id'],
            'concepto': concepto, 'es_tu_deuda': False, 'es_mi_pago': p['es_mi_pago'],
            'delta': delta, 'sobrante': p['sobrante'],
            'es_compensacion': p['es_compensacion'], 'monto_total': p['monto_total'],
            'detalle': [{'deuda_id': a['deuda_id'], 'titulo': a['titulo'],
                         'monto': a['monto_asignado']} for a in p['deudas']],
        })
    # Las deudas mandan el orden: van por su fecha, y `created_at` desempata dentro del
    # día (la fecha es DATE, así que una tarde entera de deudas empata).
    orden_deudas = sorted(out_deudas, key=lambda d: ((d['fecha_gasto'] or ''), d['creado']))
    pos_deuda = {d['id']: i for i, d in enumerate(orden_deudas)}

    # Un pago NO va por su propia fecha: va justo DESPUÉS de la última deuda que pagó o
    # cruzó, que es donde se entiende su efecto. Pagar mañana lo de ayer se lee como el
    # cierre de ayer, no como un evento suelto al final del historial.
    ancla = {}
    for p in out_pagos:
        tocadas = [pos_deuda[a['deuda_id']] for a in p['deudas'] if a['deuda_id'] in pos_deuda]
        if tocadas:
            ancla[p['id']] = max(tocadas)
        else:
            # No abonó a ninguna deuda (quedó entero como saldo a favor): entonces sí
            # manda su fecha, después de todo lo que ya existía ese día.
            ancla[p['id']] = max([pos_deuda[d['id']] for d in out_deudas
                                  if (d['fecha_gasto'] or '') <= (p['fecha_pago'] or '')]
                                 or [-1])

    # El cruce y su pago físico son una sola operación: se mueven juntos, al ancla del más
    # nuevo de los dos. Si no, el cruce se quedaría anclado a deudas viejas y el bloque
    # "cruce + pago" se partiría en dos puntos del historial.
    grupos = _operaciones_de_pago(out_pagos)
    ancla_grupo: dict = {}
    for pid, clave in grupos.items():
        ancla_grupo[clave] = max(ancla_grupo.get(clave, -1), ancla[pid])
    for pid, clave in grupos.items():
        ancla[pid] = ancla_grupo[clave]

    def _clave(e):
        if e['tipo'] == 'deuda':
            return (pos_deuda[e['id']], 0, '', '', 0)
        # Empatados en ancla, el pago más viejo primero; y dentro de una operación, el
        # cruce antes del pago físico (comparten `created_at`).
        return (ancla[e['id']], 1, e['fecha'] or '', e.get('orden') or '', _rango_evento(e))

    # Saldo acumulado: se acumula en este mismo orden, así el saldo que muestra cada fila
    # es el que había justo después de ese movimiento tal como se lee en pantalla.
    eventos.sort(key=_clave)
    saldo = 0.0
    for e in eventos:
        saldo = round(saldo + e['delta'], 2)
        e['saldo_acumulado'] = saldo

    # --- Qué le pasó a cada deuda en cada pago (y cuáles quedaron parciales) ---
    # Recorriendo los pagos cronológicamente y acumulando lo abonado por deuda, cada pago
    # (real o virtual) queda con la foto de las deudas que tocó: con cuánto llegaba cada
    # una, cuánto le aplicó ese pago y con cuánto quedó. De ahí salen tanto las deudas
    # saldadas como las que siguen vivas y hay que volver a mostrar como parciales.
    from collections import defaultdict
    deuda_orig = {d['id']: d['monto_original'] for d in out_deudas}
    deuda_titulo = {d['id']: d['titulo'] for d in out_deudas}
    deuda_dir = {d['id']: d['es_tu_deuda'] for d in out_deudas}
    deuda_fecha = {d['id']: d['fecha_gasto'] for d in out_deudas}
    deuda_favor = {d['id']: d['abono_saldo_favor'] for d in out_deudas}
    cum: dict = defaultdict(float)
    items_by_pago: dict = {}
    # Dentro del mismo día los cruces van primero: así los crea la app (`compensarDeudas`
    # corre antes de registrar el pago físico), y así se ven los saldos que cruzaron.
    for p in sorted(out_pagos, key=lambda x: (ancla[x['id']], x['fecha_pago'] or '',
                                              x['creado'],
                                              0 if x['es_compensacion'] else 1)):
        # Un pago puede tocar la misma deuda en varios detalles: se suman.
        agrupado: dict = {}
        for a in p['deudas']:
            agrupado[a['deuda_id']] = round(agrupado.get(a['deuda_id'], 0.0)
                                            + a['monto_asignado'], 2)
        items = []
        for did, monto in agrupado.items():
            orig = deuda_orig.get(did, 0.0)
            antes = round(orig - cum[did], 2)
            cum[did] = round(cum[did] + monto, 2)
            despues = round(orig - cum[did], 2)
            items.append({
                'deuda_id': did, 'titulo': deuda_titulo.get(did, '—'),
                'fecha_gasto': deuda_fecha.get(did),
                'es_tu_deuda': bool(deuda_dir.get(did, False)),
                'monto_original': orig,
                'saldo_antes': antes,
                'aplicado': monto,
                'pagado_acumulado': round(orig - despues, 2),
                'saldo_despues': max(despues, 0.0),
                'cerrada': despues <= 0.01,
                # Del saldo que quedó vivo, cuánto lo cubre después el saldo a favor
                # (dinero ya entregado pero sin asignar a ninguna deuda).
                'abono_saldo_favor': deuda_favor.get(did, 0.0),
            })
        items.sort(key=lambda it: it['fecha_gasto'] or '')
        items_by_pago[p['id']] = items

    for e in eventos:
        if e['tipo'] != 'pago':
            continue
        items = items_by_pago.get(e['id'], [])
        e['items'] = items
        # Compat: las que siguen vivas tras este pago (0 < pagado < original).
        e['parciales'] = [{
            'deuda_id': it['deuda_id'], 'titulo': it['titulo'],
            'monto_original': it['monto_original'],
            'pagado_acumulado': it['pagado_acumulado'], 'saldo': it['saldo_despues'],
        } for it in items
            if it['saldo_despues'] > 0.01 and it['pagado_acumulado'] > 0.01]

    # Los dos pagos virtuales de un cruce se muestran como un solo movimiento de dos lados.
    eventos = _colapsar_cruces(eventos, items_by_pago)

    # --- Orden de presentación: presente→pasado (cronológico descendente) ---
    # El pago tiene fecha posterior a las deudas que abonó, así que queda ARRIBA
    # (más actual) que ellas. En misma fecha, el pago va sobre la deuda.
    movimientos = list(reversed(eventos))

    out_deudas.sort(key=lambda d: ((d['fecha_gasto'] or ''), d['creado']), reverse=True)
    out_pagos.sort(key=lambda p: ((p['fecha_pago'] or ''), p['creado'],
                                  1 if p['es_compensacion'] else 0), reverse=True)

    # Totales sobre el saldo REAL: lo que ya cubre el saldo a favor no se debe.
    total_te_deben = round(sum(d['saldo_real'] for d in out_deudas if not d['es_tu_deuda']), 2)
    total_tu_debes = round(sum(d['saldo_real'] for d in out_deudas if d['es_tu_deuda']), 2)

    resumen = {
        'total_original': round(sum(d['monto_original'] for d in out_deudas), 2),
        'total_pagado': round(sum(d['monto_pagado'] for d in out_deudas), 2),
        'total_pendiente': round(sum(d['saldo_real'] for d in out_deudas), 2),
        'total_te_deben': total_te_deben,
        'total_tu_debes': total_tu_debes,
        # + te deben, − tú debes. El crédito que quedó sin abonar es deuda pura: lo que
        # el deudor pagó de más se lo debes, lo que pagaste de más te lo debe.
        'neto': round(total_te_deben - total_tu_debes
                      - remanente_favor_debtor + remanente_favor_owner, 2),
        'saldo_favor': remanente_favor_debtor,
        'saldo_favor_owner': remanente_favor_owner,
        'count': len(out_deudas),
        'count_pagadas': sum(1 for d in out_deudas if d['estado'] == 'PAGADA'),
        'count_pendientes': sum(1 for d in out_deudas if d['estado'] != 'PAGADA'),
    }

    # Cruce que todavía se puede aplicar: derivado, no toca la base.
    sugerido = _cruce_sugerido(out_deudas)
    resumen['monto_ideal_a_cruzar'] = sugerido['monto']
    cruzables = {i['deuda_id']: i['aplicado']
                 for lado in sugerido['lados'].values() for i in lado['items']}
    for d in out_deudas:
        d['cruce_sugerido'] = cruzables.get(d['id'], 0.0)

    return {'deudas': out_deudas, 'pagos': out_pagos, 'movimientos': movimientos,
            'resumen': resumen, 'cruce_sugerido': sugerido}


def obtener_estado_cuenta(deudor_id: str) -> dict:
    """
    Estado de cuenta completo de un deudor: deudas con qué pagos las abonaron, pagos con
    a qué deudas fueron (+ sobrante), ledger cronológico con saldo acumulado y resumen.
    Modela el flujo real de dinero usando las tablas `deudas`, `pagos` y `detalle_pagos`.
    """
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        dpath = os.path.join(base_dir, "data_mock", "sistema", "deudas", "deudas.csv")
        ppath = os.path.join(base_dir, "data_mock", "sistema", "deudas", "pagos_deudas.csv")
        deudas_raw, pagos_raw = [], []
        if os.path.exists(dpath):
            m = pd.read_csv(dpath)
            m = m[m['deudor_id'].astype(str) == str(deudor_id)]
            deudas_raw = m.to_dict(orient='records')
        if os.path.exists(ppath):
            p = pd.read_csv(ppath)
            p = p[p['deudor_id'].astype(str) == str(deudor_id)]
            pagos_raw = p.to_dict(orient='records')
        # El mock no tiene detalle_pagos; los pagos quedan como saldo a favor.
        return _construir_flujo_cuenta(deudas_raw, pagos_raw, [])

    deudas_raw = supabase.table('deudas').select('*').eq('deudor_id', deudor_id).execute().data or []
    pagos_raw = supabase.table('pagos').select('*').eq('deudor_id', deudor_id).execute().data or []
    deuda_ids = [d.get('id') for d in deudas_raw if d.get('id') is not None]
    detalles = []
    if deuda_ids:
        detalles = supabase.table('detalle_pagos').select('*').in_('deuda_id', deuda_ids).execute().data or []

    local = _construir_flujo_cuenta(deudas_raw, pagos_raw, detalles)
    return _con_saldos_del_servidor(deudor_id, local)


def _con_saldos_del_servidor(deudor_id: str, local: dict) -> dict:
    """
    Los saldos los decide la función `estado_cuenta` de Postgres; aquí solo se arma el
    ledger (que es presentación y no existe en SQL).

    Mientras la migración no esté desplegada en todos los entornos, si el RPC no está
    disponible se sigue con el cálculo local — que es idéntico, pero deja de ser la
    autoridad. Si difiere, se avisa: significa que las dos definiciones se separaron.
    """
    try:
        remoto = supabase.rpc('estado_cuenta', {'p_deudor_id': deudor_id}).execute().data
    except Exception as e:
        logger.warning("estado_cuenta (RPC) no disponible, se usa el cálculo local: %s", e)
        return local

    if not remoto or 'resumen' not in remoto:
        return local

    if abs(_ec_num(remoto['resumen'].get('neto')) - local['resumen']['neto']) > 0.011:
        logger.warning("El neto del servidor (%s) no coincide con el local (%s) para %s",
                       remoto['resumen'].get('neto'), local['resumen']['neto'], deudor_id)

    por_id = {str(d.get('id')): d for d in (remoto.get('deudas') or [])}
    for d in local['deudas']:
        r = por_id.get(d['id'])
        if not r:
            continue
        for campo in ('saldo_pendiente', 'abono_saldo_favor', 'saldo_real', 'cruce_sugerido'):
            d[campo] = _ec_num(r.get(campo))
        d['estado'] = r.get('estado', d['estado'])

    for k, v in remoto['resumen'].items():
        if k in local['resumen'] or k == 'monto_ideal_a_cruzar':
            local['resumen'][k] = int(v) if k.startswith('count') else _ec_num(v)
    if remoto.get('cruce_sugerido'):
        local['cruce_sugerido'] = remoto['cruce_sugerido']
    return local


def obtener_saldos_deudores() -> dict:
    """
    Calcula de manera eficiente los saldos netos, total pendiente y saldo a favor
    para todos los deudores con una sola query global.
    Retorna un diccionario de deudor_id (como string) -> {neto, total_pendiente, saldo_favor}
    """
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        dpath = os.path.join(base_dir, "data_mock", "sistema", "deudas", "deudas.csv")
        ppath = os.path.join(base_dir, "data_mock", "sistema", "deudas", "pagos_deudas.csv")
        deudas_raw, pagos_raw = [], []
        if os.path.exists(dpath):
            try:
                m = pd.read_csv(dpath)
                deudas_raw = m.to_dict(orient='records')
            except Exception as e:
                logger.error("Error reading mock debts: %s", e)
        if os.path.exists(ppath):
            try:
                p = pd.read_csv(ppath)
                pagos_raw = p.to_dict(orient='records')
            except Exception as e:
                logger.error("Error reading mock payments: %s", e)
        detalles = []
    else:
        try:
            deudas_raw = supabase.table('deudas').select('*').execute().data or []
            pagos_raw = supabase.table('pagos').select('*').execute().data or []
            deuda_ids = [d.get('id') for d in deudas_raw if d.get('id') is not None]
            detalles = []
            if deuda_ids:
                detalles = supabase.table('detalle_pagos').select('*').in_('deuda_id', deuda_ids).execute().data or []
        except Exception as e:
            logger.error("Error querying Supabase for deudores balances: %s", e)
            return {}

    from collections import defaultdict
    deudas_by_deudor = defaultdict(list)
    for d in deudas_raw:
        did = d.get('deudor_id')
        if did is not None:
            deudas_by_deudor[str(did)].append(d)
        
    pagos_by_deudor = defaultdict(list)
    for p in pagos_raw:
        pid = p.get('deudor_id')
        if pid is not None:
            pagos_by_deudor[str(pid)].append(p)
        
    deuda_to_deudor = {}
    for d in deudas_raw:
        did = d.get('id')
        deudor_id = d.get('deudor_id')
        if did is not None and deudor_id is not None:
            deuda_to_deudor[str(did)] = str(deudor_id)
    
    detalles_by_deudor = defaultdict(list)
    for det in detalles:
        did = str(det.get('deuda_id'))
        if did in deuda_to_deudor:
            deudor_id = deuda_to_deudor[did]
            detalles_by_deudor[deudor_id].append(det)

    all_deudor_ids = set(deudas_by_deudor.keys()) | set(pagos_by_deudor.keys())
    saldos = {}
    for deudor_id in all_deudor_ids:
        if not deudor_id or deudor_id == 'None' or deudor_id == 'nan':
            continue
        try:
            res = _construir_flujo_cuenta(
                deudas_by_deudor[deudor_id],
                pagos_by_deudor[deudor_id],
                detalles_by_deudor[deudor_id]
            )
            saldos[deudor_id] = {
                'neto': res['resumen']['neto'],
                'total_pendiente': res['resumen']['total_pendiente'],
                'saldo_favor': res['resumen']['saldo_favor']
            }
        except Exception as e:
            logger.error("Error calculating balance for deudor %s: %s", deudor_id, e)
            saldos[deudor_id] = {'neto': 0.0, 'total_pendiente': 0.0, 'saldo_favor': 0.0}
    return saldos



def obtener_todas_deudas(solo_pendientes: bool = True) -> pd.DataFrame:
    """
    Obtiene todas las deudas registradas desde la vista de estado.
    """
    query = supabase.table('vista_estado_deudas').select('*').where('nombre', '!=', '').execute()
    
    # En la vista, la columna de filtro es 'estado'
    # 'PAGADA', 'PENDIENTE', 'PARCIAL'
    if solo_pendientes:
        query = query.neq('estado', 'PAGADA')
    
    response = query.execute()
    
    if not response.data:
        # Retornamos estructura compatible pero con los campos nuevos
        return pd.DataFrame(columns=[
            'id', 'titulo', 'monto_original', 'deudor_id', 'fecha_gasto', 
            'monto_pagado', 'saldo_pendiente', 'estado'
        ])
    
    df = pd.DataFrame(response.data)
    df['fecha_gasto'] = pd.to_datetime(df['fecha_gasto'])
    # Renombrar para compatibilidad hacia atras si es necesario
    # df['monto'] ahora es 'monto_original' en la vista
    df['monto'] = pd.to_numeric(df['monto_original'])
    df['pagada'] = df['estado'] == 'PAGADA'
    
    return df


def obtener_deudas_por_deudor(deudor_id: str, solo_pendientes: bool = True) -> pd.DataFrame:
    """
    Obtiene las deudas de un deudor especifico desde la vista.
    """
    query = supabase.table('vista_estado_deudas').select('*').eq('deudor_id', deudor_id)
    
    if solo_pendientes:
        query = query.neq('estado', 'PAGADA')
    
    response = query.execute()
    
    if not response.data:
        return pd.DataFrame(columns=[
            'id', 'titulo', 'monto_original', 'deudor_id', 'fecha_gasto', 
            'monto_pagado', 'saldo_pendiente', 'estado'
        ])
    
    df = pd.DataFrame(response.data)
    df['fecha_gasto'] = pd.to_datetime(df['fecha_gasto'])
    df['monto'] = pd.to_numeric(df['monto_original'])
    df['pagada'] = df['estado'] == 'PAGADA'
    
    return df.sort_values('fecha_gasto', ascending=False).reset_index(drop=True)


def obtener_deudas_con_deudor(solo_pendientes: bool = True) -> pd.DataFrame:
    """
    Obtiene todas las deudas con informacion del deudor (JOIN).
    Para esto usamos la tabla 'deudas' cruda para el JOIN, pero necesitamos el estado.
    Estrategia: Usar la vista y hacer fetch de deudores por separado o JOIN si Supabase lo permite en vistas.
    Supabase (PostgREST) permite Foreign Tables en vistas si estan definidas.
    Asumamos que NO estan linkeadas en la vista por ahora.
    Hacemos: SELECT * FROM vista_estado_deudas, luego map de deudores.
    """
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        mock_path = os.path.join(base_dir, "data_mock", "sistema", "deudas", "deudas.csv")
        if os.path.exists(mock_path):
            df_final = pd.read_csv(mock_path)
            if solo_pendientes:
                df_final = df_final[df_final['estado'] != 'PAGADA']
            if not df_final.empty:
                df_final['fecha_gasto'] = pd.to_datetime(df_final['fecha_gasto'])
                df_final['monto'] = pd.to_numeric(df_final['monto_original'])
                df_final['pagada'] = df_final['estado'] == 'PAGADA'
                return df_final.sort_values('fecha_gasto', ascending=False).reset_index(drop=True)
            return pd.DataFrame()
        return pd.DataFrame()

    # 1. Obtener vista
    query = supabase.table('vista_estado_deudas').select('*')
    if solo_pendientes:
        query = query.neq('estado', 'PAGADA')
    resp_deudas = query.execute()
    
    if not resp_deudas.data:
        return pd.DataFrame()
        
    df = pd.DataFrame(resp_deudas.data)
    
    # 2. Obtener deudores
    # Optimizacion: Deudores uniques
    ids_deudores = df['deudor_id'].unique().tolist()
    resp_deudores = supabase.table('deudores').select('id, nombre, token').in_('id', ids_deudores).execute()
    
    mapa_deudores = {d['id']: d for d in resp_deudores.data}
    
    # 3. Merge manual
    data_expandida = []
    for _, row in df.iterrows():
        item = row.to_dict()
        deudor = mapa_deudores.get(item['deudor_id'], {})
        item['deudor_nombre'] = deudor.get('nombre', 'Desconocido')
        item['deudor_token'] = deudor.get('token', '')
        data_expandida.append(item)
        
    df_final = pd.DataFrame(data_expandida)
    df_final['fecha_gasto'] = pd.to_datetime(df_final['fecha_gasto'])
    df_final['monto'] = pd.to_numeric(df_final['monto_original'])
    df_final['pagada'] = df_final['estado'] == 'PAGADA'
    
    return df_final.sort_values('fecha_gasto', ascending=False).reset_index(drop=True)


def obtener_resumen_por_deudor(solo_pendientes: bool = True) -> pd.DataFrame:
    """
    Obtiene un resumen de deudas agrupado por deudor.
    
    Args:
        solo_pendientes: Si True, solo cuenta deudas no pagadas. Default: True
        
    Returns:
        DataFrame con columnas: deudor_id, deudor_nombre, total_deuda, 
                               cantidad_deudas, deuda_mas_antigua
    """
    df_deudas = obtener_deudas_con_deudor(solo_pendientes=solo_pendientes)
    
    if df_deudas.empty:
        return pd.DataFrame(columns=[
            'deudor_id', 'deudor_nombre', 'total_deuda', 
            'cantidad_deudas', 'deuda_mas_antigua'
        ])
    
    resumen = df_deudas.groupby(['deudor_id', 'deudor_nombre']).agg({
        'monto': ['sum', 'count'],
        'fecha_gasto': 'min'
    }).reset_index()
    
    resumen.columns = [
        'deudor_id', 'deudor_nombre', 'total_deuda', 
        'cantidad_deudas', 'deuda_mas_antigua'
    ]
    
    return resumen.sort_values('total_deuda', ascending=False).reset_index(drop=True)


def obtener_deudas_para_analisis(
    fecha_inicio: Optional[datetime] = None,
    fecha_fin: Optional[datetime] = None,
    solo_pendientes: bool = False
) -> pd.DataFrame:
    """
    Obtiene deudas con informacion completa para analisis financiero.
    Compatible con el resto del sistema de contabilidad.
    
    Args:
        fecha_inicio: Fecha minima de deuda (fecha_gasto)
        fecha_fin: Fecha maxima de deuda (fecha_gasto)
        solo_pendientes: Si True, solo deudas no pagadas
        
    Returns:
        DataFrame limpio listo para analisis con columnas estandar:
        FECHA, DESCRIPCION, MONTO, TIPO, DEUDOR_NOMBRE, PAGADA, 
        FECHA_PAGO, FECHA_CREACION
    """
    df = obtener_deudas_con_deudor(solo_pendientes=solo_pendientes)
    
    if df.empty:
        return pd.DataFrame(columns=[
            'FECHA', 'DESCRIPCION', 'MONTO', 'TIPO', 
            'DEUDOR_NOMBRE', 'PAGADA', 'FECHA_PAGO', 'FECHA_CREACION'
        ])
    
    # Filtrar por fechas si se proporcionan
    if fecha_inicio:
        df = df[df['fecha_gasto'] >= fecha_inicio]
    if fecha_fin:
        df = df[df['fecha_gasto'] <= fecha_fin]
    
    # Renombrar y seleccionar columnas al estilo del sistema
    df_limpio = pd.DataFrame({
        'FECHA': df['fecha_gasto'],
        'DESCRIPCION': df['titulo'],
        'MONTO': df['monto'],
        'TIPO': 'DEUDA',
        'DEUDOR_NOMBRE': df['deudor_nombre'],
        'DEUDOR_ID': df['deudor_id'],
        'PAGADA': df['pagada'],
        'FECHA_PAGO': df.get('fecha_pago'),
        'FECHA_CREACION': df.get('created_at'),
        'ID': df['id']
    })
    
    return df_limpio.sort_values('FECHA', ascending=False).reset_index(drop=True)


def obtener_todos_pagos() -> pd.DataFrame:
    """
    Obtiene todos los pagos realizados registrados en la tabla 'pagos'.
    
    Returns:
        DataFrame con columnas: id, fecha_pago, monto_total, deudor_id, deudor_nombre
    """
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        mock_path = os.path.join(base_dir, "data_mock", "sistema", "deudas", "pagos_deudas.csv")
        if os.path.exists(mock_path):
            df = pd.read_csv(mock_path)
            if not df.empty:
                df['fecha_pago'] = pd.to_datetime(df['fecha_pago'])
                df['monto_total'] = pd.to_numeric(df['monto_total'])
                return df.sort_values('fecha_pago', ascending=False)
            return pd.DataFrame()
        return pd.DataFrame()

    # 1. Obtener pagos
    response = supabase.table('pagos').select('*').execute()
    
    if not response.data:
        return pd.DataFrame(columns=['id', 'fecha_pago', 'monto_total', 'deudor_id', 'deudor_nombre'])
        
    df = pd.DataFrame(response.data)
    
    # 2. Enriquecer con nombre de deudor
    # Obtener deudores para map
    ids_deudores = df['deudor_id'].unique().tolist()
    if ids_deudores:
        try:
            resp_deudores = supabase.table('deudores').select('id, nombre').in_('id', ids_deudores).execute()
            if resp_deudores.data:
                mapa_deudores = {d['id']: d['nombre'] for d in resp_deudores.data}
                # Use apply/map instead of map directly to avoid errors if some ids are missing
                df['deudor_nombre'] = df['deudor_id'].apply(lambda x: mapa_deudores.get(x, 'Desconocido'))
            else:
                 df['deudor_nombre'] = 'Desconocido'
        except Exception:
            df['deudor_nombre'] = 'Desconocido'
    else:
        df['deudor_nombre'] = 'Desconocido'
        
    df['fecha_pago'] = pd.to_datetime(df['fecha_pago'])
    df['monto_total'] = pd.to_numeric(df['monto_total'])
    
    return df.sort_values('fecha_pago', ascending=False)



if __name__ == "__main__":
    # Ejemplos de uso
    print("=== DEUDORES ===")
    df_deudores = obtener_todos_deudores()
    print(df_deudores)
    
    print("\n=== DEUDAS PENDIENTES ===")
    df_deudas = obtener_todas_deudas(solo_pendientes=True)
    print(df_deudas)
    
    print("\n=== RESUMEN POR DEUDOR ===")
    df_resumen = obtener_resumen_por_deudor()
    print(df_resumen)
    
    print("\n=== DEUDAS PARA ANALISIS ===")
    df_analisis = obtener_deudas_para_analisis()
    print(df_analisis.head())
