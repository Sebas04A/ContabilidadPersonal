import re
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from contabilidad.config import PATH_TARJETA_PROCESADA, PATH_TARJETA_NUEVOS
from contabilidad.backend.services.credit_card.models import (
    DATOS_TARJETA_COMPLETA, DATOS_TARJETA_HEADER, DATOS_TARJETA_INFO_MOVIMIENTOS, 
    DATOS_TARJETA_METADATA, DATOS_TARJETA_TOTALES
)
from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

def fix_encoding(text: str) -> str:
    """Corrige texto con codificación latin1 mal interpretada como utf-8."""
    try:
        return text.encode('latin1').decode('utf-8')
    except UnicodeError:
        return text


MONTHS_MAP = {
    'ENR':'Jan', 'FEB':'Feb', 'MAR':'Mar', 'ABR':'Apr',
    'MYO':'May', 'JUN':'Jun', 'JUL':'Jul', 'AGO':'Aug',
    'SEP':'Sep', 'OCT':'Oct', 'NOV':'Nov', 'DIC':'Dec',
}

def try_parse_date_es(s: str):
    s = s.strip().upper()
    # Esperamos algo como '06 ABR 2024'
    partes = re.split(r'\s+', s)
    if len(partes) == 3 and partes[1] in MONTHS_MAP:
        dia, mes_es, año = partes
        mes_en = MONTHS_MAP[mes_es]
        fecha_en = f"{dia} {mes_en} {año}"
        return datetime.strptime(fecha_en, "%d %b %Y")
    else:
        # si no encaja, devolvemos None o fallamos suave
        return None


def to_float(value: str) -> float:
    """Convierte cadenas tipo '1.234,56' a float 1234.56, o nan si falla."""
    if not isinstance(value, str):
        return np.nan
    try:
        return float(value.replace('.', '').replace(',', '.'))
    except ValueError:
        return np.nan


def load_table(file_path: Path) -> list[list[str]]:
    """Lee la primera tabla HTML de un .xls y devuelve sus filas limpias."""
    html = file_path.read_text(encoding='latin1', errors='ignore')
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find('table')
    if table is None:
        raise RuntimeError("No se encontró ninguna tabla en el HTML.")
    rows = []
    for tr in table.find_all('tr'):
        cells = [fix_encoding(td.get_text(strip=True)) for td in tr.find_all(['th', 'td'])]
        if any(cells):
            rows.append(cells)
    return rows


def find_start_header_index(rows: list[list[str]]) -> int:
    """Encuentra la fila del encabezado que contiene 'Fecha' y 'Valor'."""
    for i, row in enumerate(rows):
        if 'Fecha' in row and 'Valor' in row:
            return i
    raise RuntimeError("No se encontró el encabezado con 'Fecha' y 'Valor'.")


def extract_metadata_header(rows: list[list[str]]) -> DATOS_TARJETA_METADATA:
    """Extrae metadatos de las filas anteriores al encabezado."""
    meta = {}
    for row in rows:
        for cell in row:
            if ':' in cell:
                key, val = map(str.strip, cell.split(':', 1))
                meta[key] = val
    
    emision = try_parse_date_es(meta.get('Fecha de emisión', ''))
    pago_fecha = meta.get('Pague Hasta', '')
    if pago_fecha == "INMEDIATO":
        pago_fecha = emision.strftime('%d %b %Y') if emision else ''
    pago_fecha = try_parse_date_es(pago_fecha) if pago_fecha else None
    
    # Prevenir fallos duros en caso no se obtenga nada, usamos defaults
    return DATOS_TARJETA_METADATA(
        EMPRESA=meta.get('Empresa', ''),
        NUM_TARJETA=meta.get('Tarjeta No.', ''),
        FECHA_EMISION=emision or datetime.now(),
        FECHA_MAX_PAGO=pago_fecha or datetime.now()
    )


def get_header_separator(rows: list[list[str]], empresa: str) -> int:
    """Encuentra la fila que separa el resumen de los movimientos detallados con el nombre de la tarjeta."""
    for i, row in enumerate(rows):
        if empresa and re.search(re.escape(empresa), ' '.join(row), re.IGNORECASE):
            return i
    return np.nan


def get_header_separator_no_movements(rows: list[list[str]]) -> int:
    """Encuentra la fila que separa el header de los totales"""
    for i, row in enumerate(rows):
        if len(row) == 4 and re.search(r'TOTAL A', row[1], re.IGNORECASE):
            return i
        
    raise IndexError("No se encontró el separador de encabezado en las filas proporcionadas.")


def pick_value(df: pd.DataFrame, pattern: str) -> float:
    """Busca en 'Descripción' y devuelve el valor numérico que coincida con el patrón."""
    df_filtered = df[df['Descripción'].str.contains(pattern, case=False, na=False)]
    if not df_filtered.empty:
        return df_filtered.iloc[0]['Valor']
    return np.nan

def make_fecha(df, year: int, month_statement: int):
    df['day']   = df['raw_fecha'].str.slice(0,2).astype(int)
    df['month'] = df['raw_fecha'].str.slice(3,5).astype(int)

    # 2) Ajustamos el año: si el mes raw > mes de emisión, entonces es del año anterior
    df['year'] = np.where(
        df['month'] > month_statement,
        year - 1,
        year
    )

    # 3) Construimos la fecha completa
    df['Fecha'] = pd.to_datetime(
        df[['year','month','day']]
    )

    # 4) Limpiamos columnas auxiliares
    return df.drop(columns=['raw_fecha','day','month','year'])

def build_movements_df(
    data: list[list[str]],
    cols: list[str],
    year: int,
    month_statement: int,
    movements_header: pd.DataFrame
) -> pd.DataFrame:
    """Construye el DataFrame de movimientos a partir de las filas y el año."""
    df = pd.DataFrame(data, columns=cols)
    df['Valor'] = df['Valor'].apply(to_float)
    df = pd.concat([movements_header, df], ignore_index=True)
    notas_credito = df["Operación"].str.contains("N/C", case=False, na=False)
    df.loc[notas_credito, 'Valor'] *= -1


    df['raw_fecha'] = df['Fecha'].str.strip()
    df = df[df['raw_fecha'].str.match(r'^\d{2}/\d{2}$', na=False)]

    df= make_fecha(df, year, month_statement)

    df.rename(columns={
            'Descripción': 'DESCRIPCION',
            'Operación': 'OPERACION',
            "Valor":"VALOR",
            'Fecha': 'FECHA',

        }, inplace=True)
    
    # Asegurar que las columnas existan incluso si el data viene fallado
    for req_col in ['FECHA', 'DESCRIPCION', 'VALOR', 'OPERACION']:
        if req_col not in df.columns:
            df[req_col] = pd.NA
            
    return df[['FECHA', 'DESCRIPCION', 'VALOR', 'OPERACION']]

def extract_header_movements(df_header: pd.DataFrame) -> pd.DataFrame:
    """
    Extrae el encabezado de los movimientos a partir de las filas y el índice del encabezado.
    """
    if 'Operación' not in df_header.columns:
        return pd.DataFrame(columns=df_header.columns)
        
    def is_movement(row) -> bool:
        return str(row["Operación"]).strip() != ""
        
    header_movements = df_header[df_header.apply(is_movement, axis=1)]
    return header_movements


def get_info_header(df_header: pd.DataFrame) -> DATOS_TARJETA_HEADER:
    saldo_ant  = pick_value(df_header, r'SALDO ANTERIOR(?! A FAVOR)')
    saldo_ant_fav = pick_value(df_header, r'SALDO ANTERIOR A FAVOR')
    saldo_ant = saldo_ant if not np.isnan(saldo_ant) else -saldo_ant_fav

    pagos_gracias = df_header[df_header['Descripción'].str.contains('PAGO "MUCHAS GRACIAS"', case=False, na=False)]['Valor'].sum()

    subtotal_pg  = pick_value(df_header, r'Subtotal pagos')
    if np.isnan(subtotal_pg): 
        subtotal_pg = pagos_gracias

    movements_header = extract_header_movements(df_header=df_header)
    
    if 'Operación' in movements_header.columns and 'Valor' in movements_header.columns:
        debito_header = movements_header[movements_header["Operación"].str.contains("N/D", case=False, na=False)]
        credito_header = movements_header[movements_header["Operación"].str.contains("N/C", case=False, na=False)]
        total_movimientos_header = debito_header["Valor"].sum() - credito_header["Valor"].sum()
    else:
        total_movimientos_header = 0

    deuda_mes_anterior = saldo_ant - subtotal_pg

    return DATOS_TARJETA_HEADER(
        SALDO_ANTERIOR=        saldo_ant if not np.isnan(saldo_ant) else 0.0,
        SUBTOTAL_PAGADO=       subtotal_pg if not np.isnan(subtotal_pg) else 0.0,
        DEUDAS_MES_ANTERIOR=   deuda_mes_anterior if not np.isnan(deuda_mes_anterior) else 0.0,
    )

def end_movements_index(rows: list[list[str]]) -> int:
    """Encuentra el índice donde terminan los movimientos (filas vacias excepto 2 y 7). Fila 2 diga Subtotal"""
    for i, row in enumerate(rows):
        if all(not cell.strip() for j, cell in enumerate(row) if j not in [1, 6]):
            if len(row) > 2 and re.search(r'Subtotal', row[1], re.IGNORECASE):
                return i
    return np.nan


def extraer_valores_nulos(totales:list[list[str]]) -> dict:
    """Extreaer solo los valores no nulos de las listas interiores"""
    totales_filtrados = []
    for fila in totales:
       fila_nueva = []
       for valor in fila:
           if valor not in [None, '', ' ']:
               fila_nueva.append(valor)
       if fila_nueva:
           totales_filtrados.append(fila_nueva)
    return totales_filtrados

def get_info_totales(totales_info: list[list[str]]) -> DATOS_TARJETA_TOTALES:
    """Extrae totales de las filas de totales."""
    totales_filtrados = extraer_valores_nulos(totales_info)
    
    if totales_filtrados:
        subtotal = totales_filtrados[0]
        if len(subtotal) > 1 and re.search(r'Subtotal', subtotal[0], re.IGNORECASE):
            subtotal[1] = to_float(subtotal[1])
            totales_filtrados[0] = subtotal

    df_totales = pd.DataFrame(totales_filtrados, columns=['Descripción','Valor'] if len(totales_filtrados[0])==2 else None)
    
    if df_totales.empty or 'Valor' not in df_totales.columns:
         return DATOS_TARJETA_TOTALES(TOTAL_CONSUMO=0, TOTAL_A_PAGAR=0, MINIMO_A_PAGAR=0)
         
    df_totales['Valor'] = pd.to_numeric(df_totales['Valor'], errors='coerce')

    total_a_pagar = pick_value(df_totales, r'TOTAL A PAGAR')
    if np.isnan(total_a_pagar):
        total_a_pagar = pick_value(df_totales, r'TOTAL A')
    total_consumo_mes = pick_value(df_totales, r'TOTAL CONSUMOS MES')
    if np.isnan(total_consumo_mes):
        total_consumo_mes = 0
    minimo_a_pagar = pick_value(df_totales, r'PAGO M')
    return DATOS_TARJETA_TOTALES(
        TOTAL_CONSUMO= total_consumo_mes if not np.isnan(total_consumo_mes) else 0.0,
        TOTAL_A_PAGAR= total_a_pagar if not np.isnan(total_a_pagar) else 0.0,
        MINIMO_A_PAGAR= minimo_a_pagar if not np.isnan(minimo_a_pagar) else 0.0
    )


def obtener_indices_todos_movimientos(rows: list[list[str]], empresa: str) -> list[tuple[int, int]]:
    """Obtiene los índices de inicio y fin de todos los bloques de movimientos en el archivo."""
    indices = []
    end_movement=0
    
    # Evitar infinitos
    max_loops = 50
    loops = 0
    while not pd.isna(end_movements_index(rows[end_movement:])):
        if loops > max_loops: break
        loops += 1
        start_new_movement = get_header_separator(rows[end_movement:], empresa)
        if pd.isna(start_new_movement):
            break
            
        start_new_movement = int(start_new_movement) + end_movement + 1
        
        rel_end = end_movements_index(rows[start_new_movement:])
        if pd.isna(rel_end): break
        end_movement = int(rel_end) + start_new_movement
        
        indices.append((start_new_movement, end_movement))
        
    if not indices:
        try:
            end_header_idx = get_header_separator_no_movements(rows)
            indices.append((end_header_idx,end_header_idx))
        except:
            pass

    return indices

def dividir_archivo_tarjeta(rows: list[list[str]]):
    """Divide las filas en metadata, encabezado, movimientos y totales."""
    start_header_idx = find_start_header_index(rows)

    metadata_rows = rows[:start_header_idx]
    
    metadata = extract_metadata_header(metadata_rows)    
    
    indices_movimientos= obtener_indices_todos_movimientos(rows[start_header_idx:], metadata.EMPRESA)
    if not indices_movimientos: # Fallback safe si no hay patron de fin/inicio
        indices_movimientos = [(1, len(rows[start_header_idx:]))] 
        
    indices_movimientos = [(start + start_header_idx, end + start_header_idx) for start, end in indices_movimientos]
    end_header_idx = indices_movimientos[0][0] - 1

    return start_header_idx, end_header_idx, indices_movimientos


def get_credit_card_data_from_excel(file_path: str) -> tuple[pd.DataFrame, DATOS_TARJETA_COMPLETA]:
    """
    Procesa un archivo .xls de tarjeta y retorna el DataFrame de movimientos y los metadatos completos.
    (Versión adaptada del logic original proporcionado por el usuario)
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")

    rows = load_table(path)
    if not rows:
        raise ValueError("Archivo XLS sin filas.")
        
    start_header_idx, end_header_idx, movimientos_idx = dividir_archivo_tarjeta(rows)
    end_movements_idx = movimientos_idx[-1][1]

    metadata = extract_metadata_header(rows[:start_header_idx])    

    header_info = rows[start_header_idx+1 :end_header_idx]
    cols_names = rows[start_header_idx]
    
    # Rellenar con vacios a header_info temporalmente si falta longitud
    max_len = len(cols_names)
    header_info = [r + [''] * (max_len - len(r)) if len(r) < max_len else r[:max_len] for r in header_info]
    
    df_header = pd.DataFrame(header_info, columns=cols_names)
    if 'Valor' in df_header.columns:
        df_header['Valor'] = df_header['Valor'].apply(to_float)

    movements_rows = []
    for start, end in movimientos_idx:
        # Aseguramos longitud de movimientos iterando
        for r in rows[start:end]:
            movements_rows.append(r + [''] * (max_len - len(r)) if len(r) < max_len else r[:max_len])

    totales_info = rows[end_movements_idx:]
    
    header_info_extracted = get_info_header(df_header=df_header)
    info_totales = get_info_totales(totales_info=totales_info)

    TOTAL_A_PAGAR = info_totales.TOTAL_A_PAGAR

    movements_header = extract_header_movements(df_header=df_header)
    if 'Valor' in movements_header.columns:
        movements_header.loc[:, 'Valor'] = movements_header['Valor'].apply(to_float).astype(float)
    
    df_normalizado = build_movements_df(
        data=movements_rows,
        cols=cols_names,
        year=metadata.FECHA_EMISION.year if metadata.FECHA_EMISION else datetime.now().year,
        month_statement=metadata.FECHA_EMISION.month if metadata.FECHA_EMISION else datetime.now().month,
        movements_header=movements_header
    )

    min_fecha_movimientos = df_normalizado['FECHA'].min() if not df_normalizado.empty else pd.Timestamp.now()
    max_fecha_movimientos = df_normalizado['FECHA'].max() if not df_normalizado.empty else pd.Timestamp.now()
    
    if pd.isna(min_fecha_movimientos): min_fecha_movimientos = pd.Timestamp.now()
    if pd.isna(max_fecha_movimientos): max_fecha_movimientos = pd.Timestamp.now()
    
    # Prevenir cruces que harían crashear el validador
    if min_fecha_movimientos > max_fecha_movimientos:
        max_fecha_movimientos = min_fecha_movimientos

    movimientos_info=DATOS_TARJETA_INFO_MOVIMIENTOS(
        MIN_FECHA_MOVIMIENTO=min_fecha_movimientos,
        MAX_FECHA_MOVIMIENTO=max_fecha_movimientos
    )

    data_completa = DATOS_TARJETA_COMPLETA.desde_partes(
        metadata=metadata,
        header=header_info_extracted,
        totales=info_totales,
        movimientos=movimientos_info
    )

    return df_normalizado, data_completa

def _is_metadata_row(row: list[str]) -> bool:
    """
    Determina si una fila del header es puramente de metadata (saldo anterior,
    pagos/abonos, subtotales del resumen) y NO debe incluirse como movimiento.

    Las filas de metadata típicamente:
    - Tienen solo 1-2 celdas con texto (no tienen la estructura Fecha/Descripción/Valor)
    - Contienen palabras clave de resumen financiero
    """
    import re
    META_PATTERNS = [
        r'SALDO ANTERIOR',
        r'PAGOS?\s*/\s*ABONOS?',
        r'SUBTOTAL\s+PAGOS?',
        r'TOTAL\s+ANTES',
        r'DEUDA\s+MES',
        r'PAGO\s+"MUCHAS\s+GRACIAS"',
        r'SU\s+PAGO',
    ]
    text = ' '.join(c.strip() for c in row if c.strip())
    if not text:
        return True  # fila vacía → descartamos
    for pattern in META_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def extract_header_info(
    rows: list[list[str]],
    start_header_idx: int,
    end_header_idx: int,
    cols_names: list[str],
) -> tuple[pd.DataFrame, list[list[str]]]:
    """
    Analiza las filas situadas entre el encabezado de columnas (start_header_idx)
    y el primer bloque de movimientos reales (end_header_idx).

    Retorna:
        df_header_info : DataFrame con TODAS las filas del intervalo (para cálculos
                         de saldo anterior, pagos, etc.)
        header_movements: solo las filas que tienen estructura de movimiento
                          (fecha DD/MM + descripción + valor) para incluirlas
                          en el DataFrame de movimientos final (p.ej. IVA, cargos).
    """
    max_len = len(cols_names)
    raw_rows = rows[start_header_idx + 1: end_header_idx]

    # Normalizar longitud de columnas
    padded = [
        r + [''] * (max_len - len(r)) if len(r) < max_len else r[:max_len]
        for r in raw_rows
    ]

    df_header_info = pd.DataFrame(padded, columns=cols_names)
    if 'Valor' in df_header_info.columns:
        df_header_info['Valor'] = df_header_info['Valor'].apply(to_float)

    # Identificar filas del header que SÍ son movimientos (IVA, cargos especiales…)
    # Criterio: tienen formato de fecha DD/MM en la columna 'Fecha' y NO son metadata pura
    header_movements: list[list[str]] = []
    fecha_col_idx = cols_names.index('Fecha') if 'Fecha' in cols_names else 0
    for r in padded:
        # Excluir explicitamente "PAGO MUCHAS GRACIAS" y metadata
        if _is_metadata_row(r):
            continue
            
        fecha_val = r[fecha_col_idx].strip() if fecha_col_idx < len(r) else ''
        is_date_like = bool(np.char.startswith(np.array([fecha_val]), '').any())
        try:
            import re as _re
            is_date_like = bool(_re.match(r'^\d{2}/\d{2}$', fecha_val))
        except Exception:
            is_date_like = False
        if is_date_like:
            header_movements.append(r)

    return df_header_info, header_movements


def get_credit_card_data_from_excel_v2(file_path: str) -> tuple[pd.DataFrame, DATOS_TARJETA_COMPLETA]:
    """
    Versión limpia y modular de get_credit_card_data_from_excel.

    Mejoras respecto a la versión original:
    - Los movimientos del header (IVA, cargos especiales con formato DD/MM)
      se incluyen correctamente en el DataFrame final.
    - Las filas de metadata pura del header (saldo anterior, pagos, subtotales)
      se usan SOLO para los cálculos de header info y no contaminan los movimientos.
    - No usa extract_header_movements que mezclaba toda la zona del header.
    - Lógica de secciones explícita y documentada.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")

    rows = load_table(path)
    if not rows:
        raise ValueError("Archivo XLS sin filas.")

    # ── 1. Dividir el archivo en sus secciones lógicas ──────────────────────
    start_header_idx, end_header_idx, movimientos_idx = dividir_archivo_tarjeta(rows)
    end_movements_idx = movimientos_idx[-1][1]

    cols_names = rows[start_header_idx]
    max_len = len(cols_names)

    # ── 2. Metadata (filas ANTES del encabezado de columnas) ─────────────────
    metadata = extract_metadata_header(rows[:start_header_idx])

    year           = metadata.FECHA_EMISION.year  if metadata.FECHA_EMISION else datetime.now().year
    month_statement = metadata.FECHA_EMISION.month if metadata.FECHA_EMISION else datetime.now().month

    # ── 3. Header info (entre encabezado de columnas y primer movimiento) ────
    #    df_header_info → para calcular saldo anterior, pagos, deuda, etc.
    #    header_movements → filas con formato DD/MM que deben ir al DF final
    df_header_info, header_movement_rows = extract_header_info(
        rows, start_header_idx, end_header_idx, cols_names
    )

    header_info_extracted = get_info_header(df_header=df_header_info)

    # ── 4. Movimientos reales (bloques detectados por dividir_archivo_tarjeta) ─
    movements_rows: list[list[str]] = []
    for start, end in movimientos_idx:
        for r in rows[start:end]:
            movements_rows.append(
                r + [''] * (max_len - len(r)) if len(r) < max_len else r[:max_len]
            )

    # ── 5. Totales (filas DESPUÉS del último bloque de movimientos) ──────────
    totales_info = rows[end_movements_idx:]
    info_totales  = get_info_totales(totales_info=totales_info)

    # ── 6. Construir DataFrame de movimientos ────────────────────────────────
    #    Incluimos primero los movimientos del header (IVA, etc.) y luego
    #    los movimientos reales para mantener el orden cronológico.
    all_movement_rows = header_movement_rows + movements_rows

    # Build movements using the header movements as a pre-populated DataFrame
    header_mv_df = pd.DataFrame(header_movement_rows, columns=cols_names) if header_movement_rows else pd.DataFrame(columns=cols_names)
    if 'Valor' in header_mv_df.columns:
        header_mv_df['Valor'] = header_mv_df['Valor'].apply(to_float).astype(float)

    df_normalizado = build_movements_df(
        data=movements_rows,
        cols=cols_names,
        year=year,
        month_statement=month_statement,
        movements_header=header_mv_df,
    )

    # ── 7. Rango de fechas del DF ─────────────────────────────────────────────
    min_fecha = df_normalizado['FECHA'].min() if not df_normalizado.empty else pd.Timestamp.now()
    max_fecha = df_normalizado['FECHA'].max() if not df_normalizado.empty else pd.Timestamp.now()

    if pd.isna(min_fecha): min_fecha = pd.Timestamp.now()
    if pd.isna(max_fecha): max_fecha = pd.Timestamp.now()
    if min_fecha > max_fecha: max_fecha = min_fecha

    movimientos_info = DATOS_TARJETA_INFO_MOVIMIENTOS(
        MIN_FECHA_MOVIMIENTO=min_fecha,
        MAX_FECHA_MOVIMIENTO=max_fecha,
    )

    data_completa = DATOS_TARJETA_COMPLETA.desde_partes(
        metadata=metadata,
        header=header_info_extracted,
        totales=info_totales,
        movimientos=movimientos_info,
    )

    return df_normalizado, data_completa


def extraer_data_tarjeta(file_path: str):

    """
    Genera un CSV de movimientos de tarjeta a partir de un archivo .xls extraido de banca
    """
    try:
        df_movimientos, data_tarjeta = get_credit_card_data_from_excel_v2(file_path)
    except Exception as e:
        print(f"Error procesando el archivo {file_path}: {e}")
        import traceback
        traceback.print_exc()
        raise e
        
    path_xls = Path(file_path)
    filename = path_xls.stem
    from contabilidad.config import PATH_TARJETA_NUEVOS
    out_dir = Path(PATH_TARJETA_NUEVOS)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    out_file = out_dir / f"{filename}.xlsx"
    from contabilidad.backend.services.credit_card.excel_writer import guardar_archivo # Importing here to avoid circular imports if any
    guardar_archivo(df_movimientos, data_tarjeta, str(out_file))
    print(f"Archivo guardado exitosamente en: {out_file}")
    
    return str(out_file)


