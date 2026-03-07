import pandas as pd
import contabilidad.config as config



def normalizar(df):
    columnas = config.COLUMNAS_GUARDAR_DESCRIPCIONES.copy()
    # columnas.remove("diff_notion")
    df=df[columnas].copy()
    df["FECHA"] = pd.to_datetime(df["FECHA"])
    df["DESCRIPCION"] = df["DESCRIPCION"].fillna("")
    df["MADRE"] = df["MADRE"].fillna("")
    return df


def leer_descripciones():
    print("Leyendo descripciones de:", config.PATH_ARCHIVO_DESCRIPCIONES)
    df_descripciones=pd.read_excel(config.PATH_ARCHIVO_DESCRIPCIONES)
    # print(df_descripciones)
    df_descripciones=normalizar(df_descripciones)
    return df_descripciones

def imprimir_excel(df_completo:pd.DataFrame, path_guardado:str = config.PATH_ARCHIVO_DESCRIPCIONES):
    print("Guardando descripciones en:", path_guardado)
    df_completo=normalizar(df_completo)
    df_completo.to_excel(path_guardado+"", index=False)

def guardar_descripciones(df_completo:pd.DataFrame, path_guardado:str = config.PATH_DATA_ACTUAL):
    # df_descripciones_nuevo = pd.read_excel(config.PATH_ARCHIVO_DESCRIPCIONES)
    # df_completo = leer_descripciones()
    df_normalizado = normalizar(df_completo)
    path = path_guardado + "/" + config.NOMBRE_DESCRIPCIONES
    # df_completo["DESCRIPCION"] = df_descripciones_nuevo["DESCRIPCION"]
    df_normalizado.to_excel(path, index=False)
    print("Guardado descripciones en:", path)

    return path