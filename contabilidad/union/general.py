import pandas as pd
from contabilidad.cuenta.ObtenerVariables import obtener_pagos_tarjeta
def obtener_primer_dia_valido(datos_tarjetas,pagos_tarjeta df_cuenta):
    """Obtiene el primer dia valido para poder coincidir la tarjeta con la cuenta. EN ESTE CASO SOLO SE ESCOGE EL PRIMER PAGO"""
    # pagos_tarjeta = obtener_pagos_tarjeta(datos_tarjetas)
    primerPagoTarjeta = pagos_tarjeta[0].inicio
    datos_pago=datos_tarjetas[(datos_tarjetas["fecha_emision"] < primerPagoTarjeta) & (datos_tarjetas["fecha_pago"] > primerPagoTarjeta)].iloc[0]#ver si hay datos entre el primer pago y el inicio
    diferencia = abs(datos_pago["total_a_pagar_despues"].sum() - pagos_tarjeta[0].monto)
    if diferencia > 10:
        print(f"Hay una diferencia de grande entre el pago de la tarjeta y el pago de la cuenta.")
        print("REVISAR MANUALMENTE")
    else:
        INICIO = pd.to_datetime(datos_pago["fecha_min"])
        print("PRIMER PAGO DE TARJETA EN CUENTA:\n-----------------\n",df_cuenta[df_cuenta["FECHA"]==pagos_tarjeta[0].inicio][["FECHA","DESCRIPCION","MONTO","SALDO"]],end="\n---------------\n\n")
        print("PRIMER PAGO TARJETA DESDE LA CUENTA", pagos_tarjeta[0],end="\n\n")
        print("DATOS DE LA TARJETA:\n-----------------\n", datos_pago[["fecha_emision","fecha_pago","total_a_pagar_despues"]],end="\n---------------\n\n")
        print(f"Fecha de inicio: {INICIO}")
    return INICIO


def resetear_tarjeta_primer_dia(df,deuda_inicial,primer_dia):
    """Resetea la tarjeta al primer dia dado"""
    df_ajustado = df.copy()
    df_ajustado = df_ajustado[df_ajustado["FECHA"] >= primer_dia].copy()
    if df_ajustado.empty:
        print("No hay datos despues del primer dia dado")
        return df_ajustado
    saldo_inicial = df_ajustado.iloc[0]["SALDO"]
    ajuste = deuda_inicial - saldo_inicial
    print(f"Ajuste de saldo inicial: {saldo_inicial} -> {deuda_inicial} (Ajuste: {ajuste})")
    df_ajustado["SALDO"] = df_ajustado["SALDO"] + ajuste
    return df_ajustado

def obtener_total_pagos_tarjeta(df,inicio,fin):
    """Obtiene el total de pagos de tarjeta entre dos fechas"""
    df_pagos = df[(df["FECHA"] >= inicio) & (df["FECHA"] <= fin) & (df["DESCRIPCION"].str.contains("PAGO TARJETA", case=False, na=False))]
    total_pagos = df_pagos["MONTO"].sum()
    return total_pagos

def ajustar_tarjeta_primer_dia(datos_tarjetas,primer_dia=None):
    PRIMER_PAGO_TARJETA_EN_CUENTA= obtener_pagos_tarjeta(datos_tarjetas)[0]
    ESTADO_CUENTA_TARJETA_PRIMER_DIA = datos_tarjetas[(datos_tarjetas["fecha_emision"] < PRIMER_PAGO_TARJETA_EN_CUENTA.inicio) & (datos_tarjetas["fecha_pago"] > PRIMER_PAGO_TARJETA_EN_CUENTA.inicio)].iloc[0]
    if(ESTADO_CUENTA_TARJETA_PRIMER_DIA.empty):
        #Se deberia implementar para empezar desde el primer estado de cuenta de la tarjeta
        raise ValueError("No se encontró un estado de cuenta que coincida con el primer pago de la tarjeta en la cuenta.")


    diferencia = abs(ESTADO_CUENTA_TARJETA_PRIMER_DIA["total_a_pagar_despues"] - PRIMER_PAGO_TARJETA_EN_CUENTA.monto)

    if diferencia > 10:
        raise ValueError("Hay una diferencia grande entre el pago de la tarjeta y el pago de la cuenta. REVISAR MANUALMENTE")
    
    deuda_inicial = ESTADO_CUENTA_TARJETA_PRIMER_DIA["total_a_pagar"]
    print(f"Deuda inicial de la tarjeta: {deuda_inicial}")

    # pago_tarjeta_inicial = obtener_total_pagos_tarjeta(datos_tarjetas, ESTADO_CUENTA_TARJETA_PRIMER_DIA["fecha_min"],primer_dia )


    
def ajustar_tarjeta_primer_dia(datos_tarjetas,df):
    """Ajustar los gastos en tarjeta para coincidir con el primer dia"""
    PRIMER_DIA =  df["FECHA"].min()
    PRIMER_ESTADO_CUENTA_TARJETA = datos_tarjetas[datos_tarjetas["fecha_emision"] < PRIMER_DIA].iloc[-1]
    

def ajustar_todos_primer_dia(df_unido,datos_tarjetas,primer_dia=None):
    """Ajusta todas las tarjetas al primer dia valido"""
    if primer_dia:
        INICIO = primer_dia
        print(f"Usando primer dia dado: {INICIO}")
    tarjetas = df_unido["TARJETA"].dropna().unique()
    pagos_tarjeta = obtener_pagos_tarjeta(datos_tarjetas)
    for tarjeta in tarjetas:
        pagos_tarjeta = datos_tarjetas[datos_tarjetas["tarjeta"]==tarjeta].sort_values(by="fecha_pago").to_dict('records')
        df_interpolar_tarjeta = df_unido[df_unido["TARJETA"]==tarjeta]
        INICIO = obtener_primer_dia_valido( datos_tarjetas,pagos_tarjeta, df_interpolar_tarjeta)
        df_interpolar_tarjeta_ajustado = ajustar_tarjeta_fecha_inicial(df_interpolar_tarjeta, INICIO)
        df_unido.loc[df_unido["TARJETA"]==tarjeta, :] = df_interpolar_tarjeta_ajustado
    return df_unido

def cortar_df_primer_dia(df,primer_dia):
    """Corta el DataFrame al primer dia dado"""
    df_cortado = df[df["FECHA"] >= primer_dia].copy()
    return df_cortado