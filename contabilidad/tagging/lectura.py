import pandas as pd
import numpy as np

def leer_y_limpiar_datos():
    """
    Lee y limpia los datos del archivo gastos_maestros.csv
    """
    raise NotImplementedError("Esta función ya no esta en funcionamiento.")
    # Leer el archivo CSV
    df = pd.read_csv('../data/etiquetado/gastos_maestros.csv')
    
    # Mostrar información básica del dataset
    print(f"Forma del dataset: {df.shape}")
    print(f"Columnas: {df.columns.tolist()}")
    
    # Limpieza básica
    # Eliminar filas completamente vacías
    df = df.dropna(how='all')
    
    
    return df

