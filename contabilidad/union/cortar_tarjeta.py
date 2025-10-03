import pandas as pd
from contabilidad.tarjeta.tiposCsvDatos import MAPEO_COLUMNAS


def calcular_deuda_inicial_tarjeta(datos_tarjetas,pagos_tarjeta, primer_dia):

    primer_dia = pd.to_datetime(primer_dia)

    estado_cuenta_consumo_actual = datos_tarjetas[datos_tarjetas[MAPEO_COLUMNAS["MIN_FECHA_MOVIMIENTO"]] < primer_dia].iloc[-1]
    print(f"Estado de tarjeta del futuro pero del consumo actual:\n{estado_cuenta_consumo_actual}")
    primer_dia_consumo = estado_cuenta_consumo_actual[MAPEO_COLUMNAS["MIN_FECHA_MOVIMIENTO"]]
    print(f"Primer día de consumo: {primer_dia_consumo}")
    a_pagar_este_mes = estado_cuenta_consumo_actual[MAPEO_COLUMNAS["SALDO_ANTERIOR"]]
    print(f"A pagar este mes: {a_pagar_este_mes}")
    pagos_a_buscar = estado_cuenta_consumo_actual[MAPEO_COLUMNAS["SUBTOTAL_PAGADO"]]
    print(f"Pagado en el estado de cuenta actual: {pagos_a_buscar}")

    estado_cuenta_vigente = datos_tarjetas[datos_tarjetas[MAPEO_COLUMNAS["MIN_FECHA_MOVIMIENTO"]] < primer_dia].iloc[-2]
    print(f"Estado de cuenta vigente con consumos antiguos:\n{estado_cuenta_vigente}")
    primer_dia_pago_tarjeta = estado_cuenta_vigente[MAPEO_COLUMNAS["FECHA_EMISION"]]
    print(f"Primer día de pago en el estado de cuenta anterior: {primer_dia_pago_tarjeta}")

    print(f"\nBUSCANDO PAGOS DE ${pagos_a_buscar} ENTRE {primer_dia_pago_tarjeta} y {primer_dia}")

    pagos_tarjeta_estado_cuenta = [pago for pago in pagos_tarjeta if pd.to_datetime(primer_dia_pago_tarjeta) <= pd.to_datetime(pago.inicio) < primer_dia_consumo]
    print(f"Pagos de tarjeta entre {primer_dia_pago_tarjeta} y {primer_dia}:\n{pagos_tarjeta_estado_cuenta}")

    total_pago = sum(pago.monto for pago in pagos_tarjeta_estado_cuenta)
    print(f"PAGO DE ESTADO DE TARJETA VIGENTE anterior a la fecha dada: Entre {primer_dia_pago_tarjeta} y {primer_dia}: {total_pago}")

    deuda = a_pagar_este_mes - total_pago
    print(f"Deuda calculada: {deuda}")
    return deuda

def calcular_consumos_tarjetas_actuales_cortados(df_tarjetas, primer_dia, datos_tarjetas):
    primer_dia_consumo= datos_tarjetas[datos_tarjetas[MAPEO_COLUMNAS["MIN_FECHA_MOVIMIENTO"]] < primer_dia].iloc[-1][MAPEO_COLUMNAS["MIN_FECHA_MOVIMIENTO"]]
    tarjetas_anteriores_a_la_fecha = df_tarjetas[(df_tarjetas["FECHA"] >= primer_dia_consumo) & (df_tarjetas["FECHA"] < primer_dia)]
    print(f"Consumos de tarjeta anteriores a la fecha: Entre {primer_dia_consumo} y {primer_dia}:\n", tarjetas_anteriores_a_la_fecha)
    consumos_tarjeta = tarjetas_anteriores_a_la_fecha["VALOR"].sum()
    print(f"Consumos de tarjeta anterior a la fecha: Entre {primer_dia_consumo} y {primer_dia}: {consumos_tarjeta}")
    return consumos_tarjeta


def calcular_deuda_inicial_tarjeta(datos_tarjetas, pagos_tarjeta, primer_dia):
    deuda_anterior = datos_tarjetas[datos_tarjetas[MAPEO_COLUMNAS["FECHA_EMISION"]] < primer_dia].iloc[-1][MAPEO_COLUMNAS["TOTAL_A_PAGAR"]]
    print(f"Deuda anterior al primer día: {deuda_anterior}")

    primer_dia_pago_tarjeta = datos_tarjetas[datos_tarjetas[MAPEO_COLUMNAS["FECHA_EMISION"]] < primer_dia].iloc[-1][MAPEO_COLUMNAS["FECHA_EMISION"]]
    pagos_tarjeta_estado_cuenta = [pago for pago in pagos_tarjeta if pd.to_datetime(primer_dia_pago_tarjeta) <= pd.to_datetime(pago.inicio) < primer_dia]
    print(f"Pagos de tarjeta entre {primer_dia_pago_tarjeta} y {primer_dia}:\n{pagos_tarjeta_estado_cuenta}")

    total_pago = sum(pago.monto for pago in pagos_tarjeta_estado_cuenta)
    print(f"PAGO DE ESTADO DE TARJETA VIGENTE anterior a la fecha dada: Entre {primer_dia_pago_tarjeta} y {primer_dia}: {total_pago}")
    deuda = deuda_anterior - total_pago
    print(f"Deuda calculada: {deuda}")


def obtener_total_antes_corte(datos_tarjetas,pagos_tarjetas,df_tarjetas, primer_dia):
    deuda=calcular_deuda_inicial_tarjeta(datos_tarjetas=datos_tarjetas, pagos_tarjeta=pagos_tarjetas, primer_dia=primer_dia)
    deuda = datos_tarjetas[datos_tarjetas[MAPEO_COLUMNAS["MIN_FECHA_MOVIMIENTO"]] < primer_dia].iloc[-1][MAPEO_COLUMNAS["SALDO_ANTERIOR"]]
    consumo_anteriores = calcular_consumos_tarjetas_actuales_cortados(df_tarjetas=df_tarjetas, primer_dia=primer_dia, datos_tarjetas=datos_tarjetas)
    total_antes_corte = deuda + consumo_anteriores
    print(f"Deuda inicial: {deuda}, Consumos anteriores: {consumo_anteriores} = Total antes de corte: {total_antes_corte}")
    return total_antes_corte

def cuadrar_tarjeta_corte(df_unido, primer_dia, datos_tarjetas, pagos_tarjeta, df_tarjetas):
    from contabilidad.cuenta import ObtenerVariables as ObtenerVariablesCuenta

    total_antes_corte = obtener_total_antes_corte(datos_tarjetas=datos_tarjetas, pagos_tarjetas=pagos_tarjeta, df_tarjetas=df_tarjetas, primer_dia=primer_dia)

    dia_anterior_primer_dia = primer_dia - pd.Timedelta(days=1)
    dia_anterior_primer_dia = pd.to_datetime(dia_anterior_primer_dia)

    fila_para_cuadrar = pd.DataFrame({
        "FECHA": [dia_anterior_primer_dia],
        "VALOR_TARJETA": [total_antes_corte],
        "ACUMULADO_TARJETA": [total_antes_corte],
    })

    df_tarjeta_unido_corregido = pd.concat([fila_para_cuadrar, df_unido]).sort_values("FECHA").reset_index(drop=True)

    df_tarjeta_unido_corregido["ACUMULADO_TARJETA"] = df_tarjeta_unido_corregido["VALOR_TARJETA"].cumsum()
    df_tarjeta_unido_corregido["TARJETA"] = df_tarjeta_unido_corregido["TARJETA"].fillna(0)

    pagos_filtrados = [pago for pago in pagos_tarjeta if pd.to_datetime(pago.inicio) >= primer_dia]
    df_tarjeta_unido_corregido = ObtenerVariablesCuenta.marcar_fijos(df_tarjeta_unido_corregido, pagos_filtrados, "PAGO_TARJETA", incluir_ultimo=True)
    df_tarjeta_unido_corregido["PAGO_TARJETA"]  = df_tarjeta_unido_corregido["PAGO_TARJETA"].fillna(0)
    df_tarjeta_unido_corregido["TARJETA"] = df_tarjeta_unido_corregido["ACUMULADO_TARJETA"] - df_tarjeta_unido_corregido["PAGO_TARJETA"]






    return df_tarjeta_unido_corregido

def cortar_dia(df_unido,datos_tarjetas, primer_dia,pagos_tarjeta, df_tarjetas):
    """Corta el dataframe de tarjeta en el primer dia dado"""
    df = df_unido[df_unido["FECHA"] >= primer_dia].copy()
    df_cuadrado_corte = cuadrar_tarjeta_corte(df_unido=df, primer_dia=primer_dia, datos_tarjetas=datos_tarjetas, pagos_tarjeta=pagos_tarjeta, df_tarjetas=df_tarjetas)

    return df_cuadrado_corte


