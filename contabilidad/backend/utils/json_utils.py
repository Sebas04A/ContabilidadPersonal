import pandas as pd

def sanitize_for_json(df: pd.DataFrame) -> pd.DataFrame:
    """Replace NaN values with appropriate defaults for JSON serialization."""
    df = df.copy()
    
    # String columns
    str_cols = ['DESCRIPCION', 'TIPO', 'nombre_limpio', 'categoria', 'tags', 'prioridad', 'pertenece_a', 'deudor', 'nota', 'split_group_id', 'id', 'group_id']

    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str)
    
    # Bool columns
    bool_cols = ['es_fijo', 'es_reembolsable', 'revisado']
    for col in bool_cols:
        if col in df.columns:
            # Fix FutureWarning: Avoid downcasting warning by using explicit assignment
            df.loc[df[col].isna(), col] = False
            df[col] = df[col].astype(bool)
    
    # Int columns
    if 'felicidad' in df.columns:
        df['felicidad'] = df['felicidad'].fillna(0).astype(int)
    
    # Float columns
    if 'MONTO' in df.columns:
        df['MONTO'] = df['MONTO'].fillna(0.0).astype(float)
        
    if 'monto_asignado' in df.columns:
        df['monto_asignado'] = df['monto_asignado'].fillna(0.0).astype(float)
    
    return df
