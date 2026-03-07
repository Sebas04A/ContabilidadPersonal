import hashlib
import pandas as pd

def generate_unique_id(fecha, monto, descripcion, source_type, discriminator=0):
    """
    Genera un ID único determinista basado en los campos principales de una transacción.
    
    Args:
        fecha: Fecha de la transacción (datetime, date o str iso format)
        monto: Monto de la transacción (float)
        descripcion: Descripción de la transacción (str)
        source_type: Tipo de fuente (str) - e.g. "BANCO", "TARJETA"
        discriminator: Entero para diferenciar transacciones idénticas (default 0)
        
    Returns:
        str: Hash MD5 de los datos
    """
    
    # Normalizar fecha
    if isinstance(fecha, (pd.Timestamp, pd.DatetimeIndex)):
        fecha_str = fecha.strftime('%Y-%m-%d')
    else:
        fecha_str = str(fecha).split(' ')[0] # Quedarse solo con YYYY-MM-DD si viene con hora
        
    # Normalizar monto (2 decimales)
    try:
        monto_float = float(monto)
        monto_str = f"{monto_float:.2f}"
    except (ValueError, TypeError):
        monto_str = "0.00"
        
    # Normalizar descripción
    desc_str = str(descripcion).strip().upper()
    
    # Normalizar fuente
    source_str = str(source_type).strip().upper()
    
    # Crear string base para el hash
    raw_id = f"{fecha_str}|{monto_str}|{desc_str}|{source_str}|{discriminator}"
    
    # Generar hash MD5
    return hashlib.md5(raw_id.encode('utf-8')).hexdigest()

def add_id_column(df: pd.DataFrame, source_type: str = "UNKNOWN") -> pd.DataFrame:
    """
    Agrega una columna 'id' al DataFrame asegurando unicidad incluso para transacciones idénticas.
    
    Estrategia:
    1. Normaliza los campos clave (FECHA, MONTO, DESCRIPCION, FUENTE).
    2. Agrupa por estos campos normalizados para detectar duplicados exactos.
    3. Asigna un contador secuencial (0, 1, 2...) a cada ocurrencia dentro del grupo.
    4. Genera el hash MD5 usando los campos + el contador.
    
    Esto asegura que:
    - No haya IDs repetidos.
    - Los IDs sean deterministas (siempre igual para el mismo archivo/orden).
    - Cualquier cambio en los datos genere un nuevo ID.
    """
    if df.empty:
        return df
        
    df = df.copy()
    
    if 'FUENTE' not in df.columns:
        df['FUENTE'] = source_type

    # Asegurarnos de tener las columnas necesarias
    required_cols = ['FECHA', 'MONTO', 'DESCRIPCION']
    for col in required_cols:
        if col not in df.columns:
            # Si falta alguna columna crítica, no podemos generar ID confiable
            # Podríamos lanzar error, pero es mejor devolver vacío o manejarlo
            print(f"Warning: columna {col} faltante para generar ID")
            return df
            
    # 1. Crear columnas normalizadas temporales para agrupación consistente
    # Fecha
    def norm_fecha(x):
        if isinstance(x, (pd.Timestamp, pd.DatetimeIndex)):
            return x.strftime('%Y-%m-%d')
        return str(x).split(' ')[0]
        
    temp_fecha = df['FECHA'].apply(norm_fecha)
    
    # Monto
    def norm_monto(m):
        try:
            return f"{float(m):.2f}"
        except:
            return "0.00"
    temp_monto = df['MONTO'].apply(norm_monto)
    
    # Descripción y Fuente
    temp_desc = df['DESCRIPCION'].astype(str).str.strip().str.upper()
    temp_fuente = df['FUENTE'].astype(str).str.strip().str.upper()
    
    # 2. Crear dataframe temporal para calcular discriminadores
    # Usamos un DataFrame temporal para no ensuciar el original y para el groupby
    temp_keys = pd.DataFrame({
        'f': temp_fecha,
        'm': temp_monto,
        'd': temp_desc,
        's': temp_fuente
    })
    
    # 3. Calcular discriminador (0 para el 1ro, 1 para el 2do, etc.)
    discriminators = temp_keys.groupby(['f', 'm', 'd', 's']).cumcount()
    
    # 4. Generar ID vectorizado
    # Concatenamos todo en un string gigante
    raw_ids = temp_keys['f'] + "|" + temp_keys['m'] + "|" + temp_keys['d'] + "|" + temp_keys['s'] + "|" + discriminators.astype(str)
    
    # Aplicar MD5 a cada string
    df['id'] = raw_ids.apply(lambda x: hashlib.md5(x.encode('utf-8')).hexdigest())
    
    return df
