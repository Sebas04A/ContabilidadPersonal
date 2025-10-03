from contabilidad.config import COLUMNAS_GUARDAR_CUENTAS,PATH_BANCA_HISTORICO_COMPLETO,PATH_CUENTA_UNIDO
import pandas as pd
def guardar_archivo_banca_completo(df, nombre, guardar_definitivo=False):
    df_imprimir = df[COLUMNAS_GUARDAR_CUENTAS].copy()
    df_imprimir["FECHA"] = df_imprimir["FECHA"].dt.strftime('%Y-%m-%d')
    df_imprimir["MONTO"] = df_imprimir["MONTO"].round(2)
    if guardar_definitivo:
        df_imprimir.to_excel(PATH_CUENTA_UNIDO, index=False)
        print("Guardado en:", PATH_CUENTA_UNIDO)
    else:
        fecha_actual = pd.to_datetime('today').strftime('%Y-%m-%d')
        path = f"{PATH_BANCA_HISTORICO_COMPLETO}/{nombre}_{fecha_actual}.xlsx"
        df_imprimir.to_excel(path, index=False)
        print("Guardado en:", path)
