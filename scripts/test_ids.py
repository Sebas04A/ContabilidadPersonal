import pandas as pd
from contabilidad.backend.utils import add_id_column, generate_unique_id

def test_id_generation():
    # Caso 1: Datos idénticos
    data = {
        'FECHA': ['2023-01-01', '2023-01-01', '2023-01-02'],
        'MONTO': [100.0, 100.0, 50.0],
        'DESCRIPCION': ['Uber', 'Uber', 'Lunch'],
        'FUENTE': ['BANCO', 'BANCO', 'banco'] # Mixed case to test normalization
    }
    df = pd.DataFrame(data)
    
    print("--- DataFrame Inicial ---")
    print(df)
    
    df_with_id = add_id_column(df, source_type="BANCO")
    
    print("\n--- DataFrame con IDs ---")
    print(df_with_id[['FECHA', 'DESCRIPCION', 'id']])
    
    # Verificar unicidad
    if df_with_id['id'].is_unique:
        print("\n✅ IDs son únicos.")
    else:
        print("\n❌ IDs NO son únicos.")
        
    # Verificar determinismo (re-running should give same IDs)
    df_again = add_id_column(df, source_type="BANCO")
    if df_with_id['id'].equals(df_again['id']):
         print("✅ IDs son deterministas.")
    else:
         print("❌ IDs NO son deterministas.")
         
    # Verificar que el segundo duplicado tenga ID distinto al primero
    id1 = df_with_id.iloc[0]['id']
    id2 = df_with_id.iloc[1]['id']
    if id1 != id2:
        print(f"✅ Duplicados distinguidos: {id1} vs {id2}")
    else:
        print(f"❌ Duplicados tienen mismo ID: {id1}")

if __name__ == "__main__":
    test_id_generation()
