import pandas as pd
from datetime import datetime
from contabilidad.backend.services.credit_card.utils import try_parse_date_es, fix_encoding, make_fecha, to_float, convertir_a_datetime_con_referencia, normalize_df_columns

def get_header_separator(rows: list[list[str]], empresa: str) -> int:
    """Encuentra la fila que separa el resumen de los movimientos detallados."""
    import re
    # La empresa puede venir en la misma línea
    pattern = re.compile(rf'^{empresa}\s+\|', re.IGNORECASE) if empresa and empresa != "Unknown" else None
    
    for i, row in enumerate(rows):
        for cell in row:
            if pattern and pattern.match(cell.strip()):
                return i
            if cell.strip() == "SUBTOTALES":
                return i
            if "T O T A L   N U E V O   S A L D O" in fix_encoding(cell):
                return None
    return 0

def end_movements_index(rows: list[list[str]]) -> int:
    """Encuentra el índice donde terminan los movimientos."""
    import re
    for i in range(len(rows)-1, -1, -1):
        row = rows[i]
        for cell in row:
            if "SUBTOTALES" in cell:
                return i
    return -1

def extract_header_movements(df_header: list[list[str]]) -> pd.DataFrame:
    """Extrae el encabezado de las columnas de la tabla principal usando Pandas."""
    def is_movement(row):
        from .metadata import find_start_header_index
        if "Fecha" in row or "Valor" in row: return True
        return False
        
    for i, row in enumerate(df_header):
        row_lower = [str(r).lower() for r in row]
        if 'fecha' in row_lower and 'valor' in row_lower:
            return pd.DataFrame([row])
            
    return pd.DataFrame()

def build_movements_df(
    data: list[list[str]],
    cols: list[str],
    year: int,
    month_statement: int,
    movements_header: pd.DataFrame
) -> pd.DataFrame:
    """Construye el DataFrame de movimientos aplicando casteo estricto numérico."""
    if not data:
        return pd.DataFrame()
        
    cleaned_data = []
    # Si las cols vienen vacías, las tomamos del header real
    if not cols and not movements_header.empty:
        cols = list(movements_header.iloc[0])
        
    # Validamos que tengamos columnas suficientes
    max_len = max([len(r) for r in data]) if data else 0
    if len(cols) < max_len:
        cols.extend([f"Col_{i}" for i in range(len(cols), max_len)])
        
    for row in data:
        if not any(row): continue
        if len(row) < len(cols):
            row.extend([''] * (len(cols) - len(row)))
        cleaned_data.append(row[:len(cols)])

    if not cleaned_data:
        return pd.DataFrame()
        
    df = pd.DataFrame(cleaned_data, columns=cols)
    
    if 'Fecha' in df.columns:
        df = make_fecha(df, year, month_statement)
    else:
        # Fallback date if no Fecha column
        df['FECHA'] = pd.NaT

    if 'Valor' in df.columns:
        df['Valor'] = df['Valor'].apply(to_float)
    
    # Limpiar columnas vacias full null
    df.dropna(axis=1, how='all', inplace=True)

    # Normalizar columnas con encoding roto (DescripciÃ³n → DESCRIPCION, etc.)
    df = normalize_df_columns(df)

    return df
