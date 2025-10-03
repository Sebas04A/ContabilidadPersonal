from contabilidad.config import PATH_GUARDAR_COMPLETO_HISTORICOS, COLUMNAS_GUARDAR_COMPLETO, PATH_UNIDO
import pandas as pd


def normalizar(df):
    df_imprimir = df[COLUMNAS_GUARDAR_COMPLETO].copy()

    df_imprimir["FECHA"] = df_imprimir["FECHA"].dt.strftime('%Y-%m-%d')
    df_imprimir["TOTAL"] = df_imprimir["TOTAL"].round(2)
    df_imprimir["TARJETA"] = df_imprimir["TARJETA"].round(2)
    df_imprimir["SALDO"] = df_imprimir["SALDO"].round(2)
    df_imprimir["INVERSION"] = df_imprimir["INVERSION"].round(2)
    df_imprimir["PAGOS_MENSUAL_MA INTER"] = df_imprimir["PAGOS_MENSUAL_MA INTER"].round(2)
    df_imprimir["NOTIONCUM"] = df_imprimir["NOTIONCUM"].round(2)

    return df_imprimir



def guardar_archivo_completo(df,nombre,guardar_definitivo=False):
    fecha_actual = pd.to_datetime('today').strftime('%Y-%m-%d')
    df_imprimir = normalizar(df)
    
    if guardar_definitivo:
        if(df["FECHA"].min()> pd.to_datetime('2024-03-22')):
            raise ValueError("Asegurate de enviar el df completo, no solo los nuevos datos")
        path = PATH_UNIDO+"/completo.xlsx"
    else:
        path = f"{PATH_GUARDAR_COMPLETO_HISTORICOS}/{nombre}_{fecha_actual}.xlsx"
    df_imprimir.to_excel(path, index=False)
    print("Guardado en:", path)
    
    # Guardar en formato compatible con Excel (.xlsx)
    
    