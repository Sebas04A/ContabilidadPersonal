import pandas as pd

def sanitize_for_json(df: pd.DataFrame) -> pd.DataFrame:
    """Replace NaN values with appropriate defaults for JSON serialization."""
    df = df.copy()
    
    # String columns
    str_cols = ['DESCRIPCION', 'TIPO', 'nombre_limpio', 'categoria', 'tags', 'prioridad', 'pertenece_a', 'deudor', 'nota', 'split_group_id', 'id', 'group_id', 'fondo_id', 'deuda_id', 'pago_id', 'HORA']

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

    # Floats que pueden faltar de verdad, y cuyo hueco **no** es un cero.
    # `SALDO_DEUDA` solo existe en las filas devengadas (`TIPO='DEUDA'`): en una
    # transacción de banca no hay deuda detrás, y un 0 ahí se leería como "deuda
    # saldada", que es otra cosa. Van a `null`, no a 0, y hace falta hacerlo acá
    # porque `json.dumps` rechaza NaN con un 500.
    for col in ('SALDO_DEUDA',):
        if col in df.columns:
            df[col] = df[col].astype(object).where(df[col].notna(), None)

    return df
