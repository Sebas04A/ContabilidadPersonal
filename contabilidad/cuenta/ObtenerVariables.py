from contabilidad.Modelos import PAGO
import pandas as pd

# pagos_tarjetas_cancelado = ["2025-04-28","2024-08-23","2024-09-23"]
DESCRIPCION_PAGO_OBLIGATORIO = "PAGO TARJETA" #Los que tienen esta descripcion son pagos obligatorios de 20 dolares en general. El minimo

DESCRIPCION_PAGO_INTERBANCARIA = "INTERBANCARIA" #Pagos a otras tarjetas
DESCRIPCION_PAGO_MASTERCARD = "MASTE" #Pagos que nos aseguramos que sea mastercard
DESCRIPCION_ES_MI_NUMERO = "223067" #Numero de mi tarjeta principal

#EJEMPLO NUEVO
# PAGO TARJETA DE CREDITO MASTERCARD BANCO PICHINCHA  22306700007562


def obtener_pagos_tarjetas(df,pagos_cancelados=[]):
    df=df.copy()
    ES_PAGO_CANCELADO=df["FECHA"].astype(str).isin(pagos_cancelados)
    ES_PAGO_OBLIGATORIO = df['DESCRIPCION'].str.contains(DESCRIPCION_PAGO_OBLIGATORIO, na=False)
    NO_ES_DISCOVER = ~df['DESCRIPCION'].str.contains(DESCRIPCION_PAGO_INTERBANCARIA, na=False)

    # pago_obligatorio = df[ES_PAGO_OBLIGATORIO& NO_ES_DISCOVER]
    ES_PAGO_TARJETA_MASTERCARD = df['DESCRIPCION'].str.contains(DESCRIPCION_PAGO_MASTERCARD, na=False) & ~ES_PAGO_CANCELADO
    ES_MI_TARJETA = df['DESCRIPCION'].str.contains(DESCRIPCION_ES_MI_NUMERO, na=False) & ES_PAGO_TARJETA_MASTERCARD
        

    pagos = df[(ES_PAGO_OBLIGATORIO & NO_ES_DISCOVER) | (ES_MI_TARJETA)].copy()
    pagos_clase =[]
    print("Pagos encontrados de tarjeta:")
    print(pagos)
    for pago in pagos.index:
        pagos_clase.append(
            PAGO(
                monto=df.loc[pago, "DEBITO"],
                inicio=df.loc[pago, "FECHA"].strftime('%Y-%m-%d')
            )
        )
    
    return pagos_clase

    
def ver_inversiones(df):
    
    ES_INVERSION_INICIADA = ["CERTIFICADO DE DEPOSITO","A PLAZO FIJO"]
    ES_INVERSION_ACABADA = "CANCELACION PLAZO FIJO"

    inversion_acabada = df[df['DESCRIPCION'] == ES_INVERSION_ACABADA ]
    inversion_inicidada =df[df["DESCRIPCION"].str.contains("|".join(ES_INVERSION_INICIADA), na=False)]
    print(inversion_inicidada[["FECHA","DESCRIPCION","MONTO"]], end="\n\n")

    df_inversiones_vista  = pd.concat([inversion_acabada, inversion_inicidada], ignore_index=True)
    df_inversiones_vista = df_inversiones_vista.sort_values(by='FECHA')
    print("------INVERSIONES")
    print(df_inversiones_vista[["FECHA","DESCRIPCION","MONTO"]], end="\n\n")

    print("------INVERSIONES ACABADAS")
    for inversion_fecha in inversion_acabada["FECHA"]:
        filas_inversion = df[df["FECHA"] == inversion_fecha]
        print(f"Fecha Inversion: {inversion_fecha}")
        plazo_fijo = filas_inversion[filas_inversion["DESCRIPCION"] == ES_INVERSION_ACABADA]["MONTO"].values[0]
        # interes = filas_inversion[filas_inversion["DESCRIPCION"] == "TRANSFERENCIA INTERIOR"]["CREDITO"].values[0]
        interes_filtrado = filas_inversion[filas_inversion["DESCRIPCION"] == "TRANSFERENCIA INTERIOR"]
        if not interes_filtrado.empty:
            interes = interes_filtrado["CREDITO"].values[0]
        else:
            interes = filas_inversion[filas_inversion["DESCRIPCION"] == ES_INVERSION_ACABADA]["MONTO"].values[1]
        
        # Verificar si existe la fila de impuesto antes de acceder
        if not filas_inversion[filas_inversion["DESCRIPCION"] == "RETENCION RENDIMIENTO FINANCIERO"].empty:
            impuesto = filas_inversion[filas_inversion["DESCRIPCION"] == "RETENCION RENDIMIENTO FINANCIERO"]["DEBITO"].values[0]
        else:
            impuesto = 0.0
    #     print(f'Fecha {fecha}')
    #     print(f'Plazo FIJO {plazo_fijo}')
    #     print(f'Interes {interes}')
    #     print(f'Impuesto {impuesto}')
        print(f'Plazo FIJO {plazo_fijo:,.2f} | Interes {interes:,.2f} | Impuesto {impuesto:,.2f}')
        total = plazo_fijo + interes - impuesto
        
        print(f'Total {total:,}',end="\n\n")

    print("------INVERSIONES INICIADAS")
    print(inversion_inicidada[["FECHA","DESCRIPCION","MONTO"]],end="\n\n")


def marcar_fijos(df,pagos:list[PAGO],columna,incluir_ultimo=False):
    """ Marca en el DataFrame los pagos fijos en una columna nueva."""
    df = df.copy()
    df[columna] = 0.0
    
    for pago in pagos:
        fin = None
        inicio = None
        if pago.fin:
            fin = df["FECHA"]<=pago.fin if incluir_ultimo else df["FECHA"]< pago.fin
        else:
            fin = pd.Series(True, index=df.index)
        inicio = df["FECHA"]>=pago.inicio if pago.inicio else pd.Series(True, index=df.index)

        print(f"Pago: {pago.monto} desde {pago.inicio} hasta {pago.fin}")
        # print(inicio)
        mask  = inicio & fin
        df.loc[mask, columna] += pago.monto
    return df