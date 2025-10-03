from contabilidad.config import PATH_UNIDO,COLUMNAS_GUARDADAS, PATH_GUARDAR_ATIPICOS_HISTORICOS
import pandas as pd


def normalizar(df):
    df_imprimir = df[COLUMNAS_GUARDADAS].copy()

    df_imprimir["FECHA"] = df_imprimir["FECHA"].dt.strftime('%Y-%m-%d')
    df_imprimir["diff_TOTAL"] = df_imprimir["diff_TOTAL"].round(2)
    df_imprimir["diff_tarjeta"] = df_imprimir["diff_tarjeta"].round(2)
    df_imprimir["diff_saldo_sin_inversion"] = df_imprimir["diff_saldo_sin_inversion"].round(2)
    return df_imprimir

def obtener_atipicos(df):
    df_atipicos = df[df["diff_TOTAL"].abs() > 10].copy()
    return df_atipicos

def guardar_archivo(df,nombre, guardar_definitivo=False):
    fecha_actual = pd.to_datetime('today').strftime('%Y-%m-%d')
   
    df_imprimir = normalizar(df)

   
    df_imprimir = obtener_atipicos(df_imprimir)

    if (guardar_definitivo):
        if(df["FECHA"].min()> pd.to_datetime('2024-03-22')):
            raise ValueError("Asegurate de enviar el df completo, no solo los nuevos datos")

        path = PATH_UNIDO+"/atipicos_descripciones.xlsx"
    else:
        path = f"{PATH_GUARDAR_ATIPICOS_HISTORICOS}/{nombre}_{fecha_actual}.xlsx" 
    
    print("Guardando archivo...")
    df_imprimir.to_excel(path, index=False)
    print("Guardado en:", path)

    # if guardar_definitivo:
    #         df_imprimir.to_excel(PATH_ATIPICOS_DESCRIPCIONES, index=False)
    #         print("Sobreescribiendo en:", PATH_ATIPICOS_DESCRIPCIONES)
    
    # Guardar en formato compatible con Excel (.xlsx)
    
    