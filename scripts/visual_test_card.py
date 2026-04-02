import sys
import os
import pprint
import pandas as pd
from pathlib import Path

# Configurar el path para poder importar
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from contabilidad.backend.services.sources_service import SourcesService
from contabilidad.config import PATH_TARJETA_PROCESADA, PATH_TARJETA_METADATA_UNIDA

def main():
    print("=== INICIANDO PRUEBA VISUAL DE EXTRACCIÓN DE DATOS DE TARJETA ===")
    service = SourcesService()
    
    try:
        resultado = service.process_card_data()
        
        print("\n--- RESULTADO DEL PROCESAMIENTO ---")
        print(f"Status: {resultado.get('status')}")
        print(f"Mensaje: {resultado.get('message')}")
        print(f"Archivos procesados: {resultado.get('files_processed')}")
        print(f"Total de filas generadas: {resultado.get('total_rows')}")
        
        print("\n--- VISUALIZACIÓN DE MOVIMIENTOS UNIFICADOS (tarjeta_unida.xlsx) ---")
        output_file = os.path.join(PATH_TARJETA_PROCESADA, "tarjeta_unida.xlsx")
        if os.path.exists(output_file):
            df = pd.read_excel(output_file)
            print(f"Columnas resultantes: {df.columns.tolist()}")
            print("\nPrimeras 10 filas de los movimientos:")
            print(df.head(10).to_string())
        else:
            print(f"No se encontró el archivo: {output_file}")
            
        print("\n--- VISUALIZACIÓN DE METADATA (metadata_tarjetas.xlsx) ---")
        if os.path.exists(PATH_TARJETA_METADATA_UNIDA):
            df_meta = pd.read_excel(PATH_TARJETA_METADATA_UNIDA)
            print(f"Total de metadatos extraídos: {len(df_meta)}")
            print("Columnas de metadata:")
            print(df_meta.columns.tolist())
            print("\nÚltimos 2 registros de metadata:")
            print(df_meta.tail(2).to_string())
        else:
            print(f"No se encontró la metadata: {PATH_TARJETA_METADATA_UNIDA}")

    except Exception as e:
        print(f"Ocurrió un error probando process_card_data: {e}")

if __name__ == '__main__':
    main()
