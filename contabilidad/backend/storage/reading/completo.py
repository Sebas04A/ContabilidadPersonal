import pandas as pd

from contabilidad.config import PATH_UNIDO

def leer_completo():
    df_completo = pd.read_excel(PATH_UNIDO+"/completo.xlsx")
    return df_completo
