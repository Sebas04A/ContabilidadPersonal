import pandas as pd
import sys

def peek_excel(path, name):
    try:
        df = pd.read_excel(path)
        print(f"=== {name} ===")
        print("Columns & Types:")
        print(df.dtypes)
        print("\nHead (5 rows):")
        print(df.head(5).to_string())
        
        # If it's banca or metadata, print specific rows related to 'tarjeta'
        if name == 'banca_unida':
            pagos = df[df['DESCRIPCION'].str.contains('tarjeta', case=False, na=False)]
            print("\nPagos de Tarjeta en la banca (últimos 5):")
            print(pagos.tail(5).to_string())
        elif name == 'tarjeta_metadata':
            print("\nÚltimos 10 metadata:")
            print(df.tail(10).to_string())
            
        print("\n" + "="*40 + "\n")
    except Exception as e:
        print(f"Error reading {path}: {e}")

peek_excel("data/sistema/procesada/banca/banca_unida.xlsx", "banca_unida")
peek_excel("data/sistema/procesada/tarjeta/tarjeta_metadata_unida.xlsx", "tarjeta_metadata")
peek_excel("data/sistema/procesada/tarjeta/tarjeta_unida.xlsx", "tarjeta_unida")
