import pandas as pd

def guardar_archivo_tarjeta(df,nombre,guardar_definitivo=False):
    from contabilidad.config import PATH_TARJETA,PATH_TARJETA_HISTORICO_COMPLETO

    fecha_actual = pd.to_datetime('today').strftime('%Y-%m-%d')
    df_imprimir = df.copy()
    
    if guardar_definitivo:
        if(df["FECHA"].min()> pd.to_datetime('2024-03-22')):
            raise ValueError("Asegurate de enviar el df completo, no solo los nuevos datos")
        path = PATH_TARJETA
    else:
        path = f"{PATH_TARJETA_HISTORICO_COMPLETO}/{nombre}_{fecha_actual}.xlsx"
        
    df_imprimir.to_excel(path, index=False)
    print("Guardado en:", path)