import pandas as pd
import contabilidad.config as config



def normalizar(df):
    columnas = config.COLUMNAS_GUARDADAS.copy()
    columnas.remove("diff_notion")
    df=df[columnas].copy()
    df["FECHA"] = pd.to_datetime(df["FECHA"])
    df["DESCRIPCION"] = df["DESCRIPCION"].fillna("")
    df["MADRE"] = df["MADRE"].fillna("")
    return df


def leer_descripciones():
    df_descripciones=pd.read_excel(config.PATH_ATIPICOS_DESCRIPCIONES)
    df_descripciones=normalizar(df_descripciones)
    return df_descripciones