import re
from datetime import datetime
import numpy as np
import pandas as pd

MONTHS_MAP = {
    'ENR':'Jan', 'FEB':'Feb', 'MAR':'Mar', 'ABR':'Apr',
    'MYO':'May', 'JUN':'Jun', 'JUL':'Jul', 'AGO':'Aug',
    'SEP':'Sep', 'OCT':'Oct', 'NOV':'Nov', 'DIC':'Dec',
    # Variantes largas en español
    'ENERO':'Jan', 'FEBRERO':'Feb', 'MARZO':'Mar', 'ABRIL':'Apr',
    'MAYO':'May', 'JUNIO':'Jun', 'JULIO':'Jul', 'AGOSTO':'Aug',
    'SEPTIEMBRE':'Sep', 'OCTUBRE':'Oct', 'NOVIEMBRE':'Nov', 'DICIEMBRE':'Dec',
}

def fix_encoding(text: str) -> str:
    """Corrige texto con codificación latin1 mal interpretada como utf-8."""
    if not isinstance(text, str):
        return text
    try:
        return text.encode('latin1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

def try_parse_date_es(s: str) -> datetime | None:
    """Intenta parsear una fecha en varios formatos con meses en español.

    Soporta:
      - '06/SEP/2025'  -> formato banco antiguo
      - '06 SEP 2025'  -> formato banco nuevo
      - '06-SEP-2025'
      - '06 SEPTIEMBRE 2025'
    """
    if not isinstance(s, str) or not s.strip():
        return None
    s_clean = s.strip().upper()

    # Reemplazar mes en español por inglés (de más largo a más corto para evitar reemplazos parciales)
    for es, en in sorted(MONTHS_MAP.items(), key=lambda x: -len(x[0])):
        if es in s_clean:
            s_clean = s_clean.replace(es, en.upper())
            break

    for fmt in ('%d/%b/%Y', '%d %b %Y', '%d-%b-%Y', '%d/%B/%Y', '%d %B %Y'):
        try:
            return datetime.strptime(s_clean, fmt)
        except ValueError:
            continue
    return None

# Mapa de columnas con encoding roto → nombre estandarizado
_COLUMN_NORMALIZE_MAP = {
    'DESCRIPCIÓN': 'DESCRIPCION',
    'DESCRIPCION': 'DESCRIPCION',
    'OPERACIÓN':   'OPERACION',
    'OPERACION':   'OPERACION',
    'PAÍS':        'PAIS',
    'PAIS':        'PAIS',
}

def normalize_df_columns(df) -> object:
    """Renombra columnas del XLS cuyo encoding quedó roto (latin1 leído como utf-8).

    Ej: 'DescripciÃ³n' → fix_encoding → 'Descripción' → upper → 'DESCRIPCION'
    """
    rename_map = {}
    for col in df.columns:
        col_fixed = fix_encoding(str(col)).upper()
        if col_fixed in _COLUMN_NORMALIZE_MAP and col != _COLUMN_NORMALIZE_MAP[col_fixed]:
            rename_map[col] = _COLUMN_NORMALIZE_MAP[col_fixed]
    if rename_map:
        df = df.rename(columns=rename_map)
    return df

def to_float(value: str) -> float:
    """Convierte cadenas tipo '1.234,56' a float 1234.56, o nan si falla."""
    if not isinstance(value, str):
        return float(value) if pd.notna(value) else np.nan
    clean = re.sub(r'[^\d,-]', '', value).replace('.', '').replace(',', '.')
    try:
        return float(clean)
    except ValueError:
        return np.nan

def make_fecha(df, year: int, month_statement: int):
    # La fecha original viene como string 'DD/MM' o similar.
    # Necesitamos reconstruir el año correcto cuidando que Dic pueda ser del año anterior
    # si el statement se emite en Enero.
    def build_date(val: str):
        if not val or not isinstance(val, str):
            return pd.NaT
        # Se asume DD/MM
        parts = val.strip().split('/')
        if len(parts) == 2:
            try:
                d = int(parts[0])
                m = int(parts[1])
                # Si el mes de la transacción es mayor al del statement (Enero vs Dic),
                # entonces pertenece al año anterior.
                y = year - 1 if m > month_statement else year
                return datetime(y, m, d)
            except (ValueError, TypeError):
                return pd.NaT
        return pd.NaT  # fallback seguro: nunca devolver el string original
    
    df['FECHA'] = df['Fecha'].fillna("").apply(build_date)
    return df

def convertir_a_datetime_con_referencia(fecha_str: str, fecha_referencia: datetime) -> datetime:
    """
    Convierte una fecha 'DD/MM' a datetime, usando una fecha de 
    referencia para determinar el año correcto.
    """
    try:
        dia, mes = map(int, fecha_str.split('/'))
        
        # Si el mes es diciembre y la referencia es enero, es el año anterior
        if mes == 12 and fecha_referencia.month == 1:
            año = fecha_referencia.year - 1
        # Si el mes es enero y la referencia es diciembre, es el año siguiente
        elif mes == 1 and fecha_referencia.month == 12:
            año = fecha_referencia.year + 1
        else:
            año = fecha_referencia.year
            
        return datetime(año, mes, dia)
    except ValueError:
        raise ValueError(f"Formato de fecha inválido: {fecha_str}. Se esperaba 'DD/MM'.")
