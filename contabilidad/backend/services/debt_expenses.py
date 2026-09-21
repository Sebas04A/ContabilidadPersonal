"""
Debt Expenses — deudas mías como gasto (devengo)
================================================

Cuando alguien paga algo por mí, ese consumo es real pero no deja rastro en mis
cuentas: no hay movimiento de banca ni de tarjeta, así que el ledger no tiene
ninguna fila a la que enganchar una etiqueta. Y con el cruce de cuentas la deuda
puede saldarse sin que se mueva un dólar mío, o sea que ese gasto no aparecería
nunca, ni siquiera más tarde.

Este módulo construye la fila que falta: una deuda con `es_mi_deuda = true` se
convierte en una fila de gasto sintética, fechada en `fecha_gasto`, que se
etiqueta como cualquier otra transacción.

Reglas que este módulo hace cumplir (plan: `PLAN_DEUDAS_COMO_GASTO.md`):

  · **Devengar es explícito** (I4). Solo se devenga una deuda que ya tiene fila en
    `etiquetas.csv` con `source_type = 'DEUDA'`. Una deuda sin etiqueta no es un
    gasto: puede ser plata que me prestaron, y ahí el gasto es en qué la usé.
  · **Nadie las recibe sin pedirlas** (I3). `load_data()` no las incluye. Quien
    las quiera llama a `cargar_deudas_devengadas()` a propósito. El motivo está
    medido: `dashboard_service._descontar_filtrado` trata todo `TIPO != 'BANCA'`
    como tarjeta, y fondos y drivers también consumen `load_data()`.
  · **El patrimonio no se toca** (I1). Lo que debo ya pesa en `DEUDA_ACUMULADA`.
    Acá solo se produce gasto.

Degrada solo: si Supabase no contesta, se registra el aviso y se devuelve un
frame vacío. El análisis se queda sin las deudas devengadas, no se cae.
"""

import pandas as pd

from contabilidad.backend.logger import get_logger
from contabilidad.backend.services.transaction_service import (
    LABEL_COLUMNS,
    load_labels,
)

logger = get_logger(__name__)

# El tercer `TIPO` del ledger, junto a 'BANCA' y 'TARJETA'.
TIPO_DEUDA = 'DEUDA'

# Las columnas que produce este módulo: las del origen más las etiquetas, igual
# que `load_data()`, para que un `concat` entre ambos no invente columnas.
_COLUMNAS_ORIGEN = ['id', 'FECHA', 'DESCRIPCION', 'MONTO', 'TIPO', 'HORA']
_COLUMNAS_ETIQUETA = [c for c in LABEL_COLUMNS if c not in ('source_id', 'source_type')]
COLUMNAS = _COLUMNAS_ORIGEN + _COLUMNAS_ETIQUETA


def _frame_vacio() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNAS)


def _etiquetas_de_deuda() -> pd.DataFrame:
    """Las filas de `etiquetas.csv` que describen deudas, no transacciones."""
    labels = load_labels()
    if labels.empty:
        return labels
    tipo = labels['source_type'].astype(str).str.strip().str.upper()
    return labels[tipo == TIPO_DEUDA].copy()


def _deudas_mias() -> pd.DataFrame:
    """Deudas de Supabase con `es_mi_deuda = true`. Frame vacío si no se puede leer."""
    try:
        from contabilidad.debts.reading import obtener_deudas_para_analisis
    except ImportError:
        logger.warning("Sin integración de Supabase: no hay deudas que devengar.")
        return pd.DataFrame()

    try:
        df = obtener_deudas_para_analisis(solo_pendientes=False)
    except Exception as e:
        logger.error("No se pudieron leer las deudas para devengar: %s", e, exc_info=True)
        return pd.DataFrame()

    if df.empty or 'ES_MI_DEUDA' not in df.columns:
        return pd.DataFrame()

    # El booleano llega de Supabase; `fillna(False)` por si alguna fila vieja lo trae nulo.
    return df[df['ES_MI_DEUDA'].fillna(False).astype(bool)].copy()


def cargar_deudas_devengadas() -> pd.DataFrame:
    """
    Filas de gasto para las deudas mías que ya fueron etiquetadas.

    `MONTO` sale **negativo**: en este sistema un gasto es negativo, y el monto de
    una deuda en Supabase es siempre positivo.

    `deudor` lo manda Supabase, no la etiqueta: el nombre de la tabla `deudores`
    es la fuente de verdad (misma regla que `debtPerson` en `debtFilters.ts`).
    """
    etiquetas = _etiquetas_de_deuda()
    if etiquetas.empty:
        # Atajo deliberado: sin etiquetas no hay nada que devengar, así que no
        # hay por qué salir a la red. Hoy este es el camino normal.
        return _frame_vacio()

    deudas = _deudas_mias()
    if deudas.empty:
        return _frame_vacio()

    deudas['_ID'] = deudas['ID'].astype(str)
    etiquetas['_ID'] = etiquetas['source_id'].astype(str)

    unidas = deudas.merge(
        etiquetas.drop(columns=['source_id', 'source_type']),
        on='_ID',
        how='inner',           # I4: sin etiqueta no hay gasto
        suffixes=('', '_etiqueta'),
    )
    if unidas.empty:
        return _frame_vacio()

    salida = pd.DataFrame({
        'id': unidas['_ID'],
        'FECHA': pd.to_datetime(unidas['FECHA']),
        'DESCRIPCION': unidas['DESCRIPCION'],
        'MONTO': -pd.to_numeric(unidas['MONTO'], errors='coerce').fillna(0.0).abs(),
        'TIPO': TIPO_DEUDA,
        # Una deuda no tiene hora: nadie anota el minuto de una cena que pagó otro.
        'HORA': '',
    })

    for col in _COLUMNAS_ETIQUETA:
        salida[col] = unidas[col] if col in unidas.columns else None

    salida['deudor'] = unidas['DEUDOR_NOMBRE']
    # La deuda ya es el vínculo; repetirlo en `deuda_id` sería decir dos veces lo mismo.
    salida['deuda_id'] = unidas['_ID']

    logger.info("Deudas devengadas: %d filas, $%.2f", len(salida), abs(salida['MONTO'].sum()))
    return salida[COLUMNAS]


def _detalles_por_pago() -> dict:
    """
    `pago_id -> [(deuda_id, monto_asignado)]`, leído de `detalle_pagos`.

    Es la tabla que dice qué deuda saldó cada dólar de un pago, y es lo único que
    permite saber **qué parte** de una transferencia ya se contó como gasto.
    """
    try:
        from contabilidad.debts.reading import supabase
        filas = supabase.table('detalle_pagos').select('pago_id,deuda_id,monto_asignado').execute().data or []
    except Exception as e:
        logger.error("No se pudo leer detalle_pagos: %s", e, exc_info=True)
        return {}

    fuera = {}
    for f in filas:
        fuera.setdefault(str(f['pago_id']), []).append((str(f['deuda_id']), float(f['monto_asignado'] or 0.0)))
    return fuera


def marcar_liquidaciones(df: pd.DataFrame) -> pd.Series:
    """
    Qué filas de `df` son liquidaciones: transacciones que saldan una deuda.

    Devolverle plata a alguien no es un gasto, y que me la devuelvan no es un
    ingreso: en los dos casos la plata solo cambia de bolsillo. En modo devengo
    el gasto ya se contó cuando se consumió, así que la liquidación tiene que
    salir o se cuenta dos veces.

    Se reconocen por `pago_id`, que es el vínculo explícito a un pago de Supabase.
    """
    if df.empty or 'pago_id' not in df.columns:
        return pd.Series(False, index=df.index)

    pago = df['pago_id'].astype(str).str.strip()
    return pago.notna() & ~pago.isin(['', 'nan', 'None', '---'])


def aplicar_devengo(df: pd.DataFrame) -> tuple:
    """
    El ledger visto por consumo en vez de por caja.

    Hace **las dos mitades a la vez**, y por eso vive en una sola función: si se
    hiciera solo una, el resultado estaría mal.

      1. **Entran** las deudas mías etiquetadas, fechadas el día del consumo.
      2. **Sale** de cada liquidación la parte que salda esas mismas deudas. Esa
         plata ya se contó arriba; contarla otra vez al devolverla sería contar
         la cena dos veces.

    El descuento es **proporcional, no todo o nada**. Una transferencia puede
    saldar cinco deudas de las cuales solo dos se devengaron: se descuenta lo que
    esas dos valían y el resto sigue contando como gasto, igual que hoy. Así no
    se pierde plata ni se cuenta de más, decida el usuario lo que decida.

    Devuelve `(df, resumen)`. El resumen dice qué se movió, para que la respuesta
    pueda explicarlo en vez de que los números cambien sin motivo visible.
    """
    resumen = {
        'deudas_devengadas': 0,
        'monto_devengado': 0.0,
        'liquidaciones_ajustadas': 0,
        'monto_descontado': 0.0,
        'liquidaciones_sin_detalle': 0,
    }

    devengadas = cargar_deudas_devengadas()
    ids = set(devengadas['id'].astype(str)) if not devengadas.empty else set()

    # ── 2. Las liquidaciones pierden lo que ya se contó ──────────────────────
    if ids and not df.empty:
        es_liq = marcar_liquidaciones(df)
        if es_liq.any():
            detalles = _detalles_por_pago()
            df = df.copy()
            montos = pd.to_numeric(df['MONTO'], errors='coerce').fillna(0.0)

            for pago_id, filas in df[es_liq].groupby(df.loc[es_liq, 'pago_id'].astype(str).str.strip()):
                asignaciones = detalles.get(pago_id)
                if asignaciones is None:
                    # Sin detalle no se puede saber qué parte ya se contó, así que
                    # no se toca: mejor el número de hoy que uno inventado.
                    resumen['liquidaciones_sin_detalle'] += len(filas)
                    continue

                devengado = sum(m for deuda_id, m in asignaciones if deuda_id in ids)
                if devengado <= 0.0049:
                    continue

                # Un mismo pago puede estar vinculado a más de una transacción:
                # se reparte entre ellas y nunca se descuenta más de lo que hay.
                total = float(montos.loc[filas.index].abs().sum())
                if total <= 0:
                    continue
                devengado = min(devengado, total)

                for idx in filas.index:
                    monto = float(montos.loc[idx])
                    if monto == 0:
                        continue
                    baja = devengado * abs(monto) / total
                    nuevo = (1 if monto > 0 else -1) * max(0.0, abs(monto) - baja)
                    df.loc[idx, 'MONTO'] = nuevo
                    resumen['monto_descontado'] += abs(monto) - abs(nuevo)
                    resumen['liquidaciones_ajustadas'] += 1

    # ── 1. Entran las deudas devengadas ──────────────────────────────────────
    if not devengadas.empty:
        resumen['deudas_devengadas'] = int(len(devengadas))
        resumen['monto_devengado'] = float(devengadas['MONTO'].abs().sum())
        faltan = [c for c in df.columns if c not in devengadas.columns]
        for c in faltan:
            devengadas[c] = None
        df = pd.concat([df, devengadas[df.columns]], ignore_index=True)

    resumen['monto_descontado'] = round(resumen['monto_descontado'], 2)
    resumen['monto_devengado'] = round(resumen['monto_devengado'], 2)
    return df, resumen

