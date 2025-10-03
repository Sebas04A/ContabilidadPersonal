import pandas as pd
import numpy as np

def interpolar_a_cero(df,valor,incluir_ultimo=False):    
    df= df.copy()
    df = df.set_index('FECHA')
    
    # print(original[~original.isna()])
    # Paso 1: Reindexar para incluir todas las fechas
    # df = df.reindex(pd.date_range(start=df.index.min(), end=df.index.max(), freq='D'))
    # Paso 2: Crear una copia del DataFrame original para referencia
    
    # Paso 3: Encontrar índices donde hay valores reales
    original = df[valor].copy()
    known_indices = original[(~original.isna())& (original != 0)].index

    print(f"MODIFICANDO {valor} - FECHAS: {known_indices}")
    if known_indices.empty:
        print("NO EXISTIERON FECHAS CON VALORES")
        return df
    #quitar ultima fecha que debe ser igual a 0
    # Paso 4: Rellenar con rampas
    for i in range(len(known_indices) - 1):
        start_date = known_indices[i]
        end_date = known_indices[i + 1]
        final_value = original[end_date]
        if not incluir_ultimo:
            end_date = end_date - pd.Timedelta(days=1)  # Excluir el último día

        print(f"Rellenando desde {start_date} hasta {end_date} con valor final {final_value}")

        fechas_completas = pd.date_range(start=start_date, end=end_date)
        ramp = np.linspace(0, final_value, len(fechas_completas))
        print(f"Ramp: {ramp}")
        ramp_df = pd.DataFrame({
            "FECHA": fechas_completas,
            "VALOR": ramp
        }).set_index("FECHA")
        fechas_existentes = df.index.intersection(ramp_df.index)
        df.loc[fechas_existentes, valor + " INTER"] = ramp_df.loc[fechas_existentes, "VALOR"]
    


    start_date = df.index.min()
    end_date = known_indices[0]
    final_value = original[end_date]

    fechas_completas = pd.date_range(start=start_date, end=end_date)
    ramp = np.linspace(0, final_value, len(fechas_completas))
    ramp_df = pd.DataFrame({
        "FECHA": fechas_completas,
        "VALOR": ramp
    }).set_index("FECHA")
    fechas_existentes = df.index.intersection(ramp_df.index)
    df.loc[fechas_existentes, valor + " INTER"] = ramp_df.loc[fechas_existentes, "VALOR"]
    # Paso 5: Resetear índice si lo necesitas
    df = df.reset_index().rename(columns={'index': 'FECHA'})
    df.fillna({valor + " INTER": 0}, inplace=True)  # Rellenar NaN con 0
    return df