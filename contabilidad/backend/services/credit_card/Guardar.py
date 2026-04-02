import pandas as pd
import numpy as np
import re
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
from contabilidad.config import PATH_DATOS_TARJETA

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
        # si no encaja, lanzamos error o devolvemos None
        raise ValueError(f"Formato de fecha no reconocido: '{s}'")


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


def find_header_index(rows: list[list[str]]) -> int:
    """Encuentra la fila del encabezado que contiene 'Fecha' y 'Valor'."""
    for i, row in enumerate(rows):
        if 'Fecha' in row and 'Valor' in row:
            return i
    raise RuntimeError("No se encontró el encabezado con 'Fecha' y 'Valor'.")


def extract_metadata_header(rows: list[list[str]], header_idx: int) -> dict:
    """Extrae metadatos de las filas anteriores al encabezado."""
    meta = {}
    for row in rows[:header_idx]:
        for cell in row:
            if ':' in cell:
                key, val = map(str.strip, cell.split(':', 1))
                meta[key] = val
    
    emision = try_parse_date_es(meta.get('Fecha de emisión', ''))
    pago_fecha = meta.get('Pague Hasta', '')
    if pago_fecha == "INMEDIATO":
        pago_fecha = emision.strftime('%d %b %Y')
    pago_fecha = try_parse_date_es(pago_fecha) if pago_fecha else None

    return {
        'Empresa':            meta.get('Empresa', ''),
        'Tarjeta No.':        meta.get('Tarjeta No.', ''),
        'fecha_emision':      emision,
        'fecha_pago':         pago_fecha
    }


def extract_summary_movements(rows: list[list[str]], header_idx: int, empresa: str) -> tuple[list[list[str]], int]:
    """
    Devuelve las filas de resumen (entre encabezado y aparición de la empresa)
    y el índice donde comienzan los movimientos detallados.
    """
    header = rows[header_idx]
    col_idx = {col: idx for idx, col in enumerate(header)}
    for i, row in enumerate(rows[header_idx + 1:], start=header_idx + 1):
        if empresa and re.search(re.escape(empresa), ' '.join(row), re.IGNORECASE):
            return rows[header_idx + 1 : i], i
    else:
        print(f"No se encontró la empresa '{empresa}' en el resumen.")
        return rows[header_idx + 1 :], i
    return [], header_idx + 1


def pick_value(summary: list[list[str]], col_idx: dict, pattern: str) -> float:
    """Busca en 'Descripción' y devuelve el valor numérico que coincida con el patrón."""
    for row in summary:
        desc = row[col_idx.get('Descripción', 2)]
        if re.search(pattern, desc, re.IGNORECASE):
            return to_float(row[col_idx['Valor']])
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
    rows: list[list[str]],
    start_idx: int,
    cols: list[str],
    year: int,
    month_statement: int
) -> pd.DataFrame:
    """Construye el DataFrame de movimientos a partir de las filas y el año."""
    data = rows[start_idx + 1 :]
    print(f"Data")
    print(data[:5])  # Mostrar las primeras 5 filas de datos
    df = pd.DataFrame(data, columns=cols)
    df['Valor'] = df['Valor'].apply(to_float)
    df['raw_fecha'] = df['Fecha'].str.strip()
    df = df[df['raw_fecha'].str.match(r'^\d{2}/\d{2}$')]

    df= make_fecha(df, year, month_statement)

    df.rename(columns={
            'Descripción': 'DESCRIPCION',
            'Operación': 'OPERACION',
            "Valor":"VALOR",
            'Fecha': 'FECHA',

        }, inplace=True)
    return df[['FECHA', 'DESCRIPCION', 'VALOR', 'OPERACION']]



def generar_csv_tarjeta(file_path: str):
    """
    Genera un CSV de movimientos de tarjeta a partir de un archivo .xls extraido de banca
    y el resumen de los movimientos
    """
    path = Path(file_path)
    rows = load_table(path)
    header_idx = find_header_index(rows)
    metadata = extract_metadata_header(rows, header_idx)

    cols = rows[header_idx]
    summary, name_idx = extract_summary_movements(rows, header_idx, metadata['Empresa'])
    print(f"Resumen de movimientos encontrado:", summary)
    col_idx = {col: idx for idx, col in enumerate(cols)}

    # Valores de resumen
    saldo_ant    = pick_value(summary, col_idx, r'^SALDO ANTERIOR$')
    saldo_ant_fav = pick_value(summary, col_idx, r'SALDO ANTERIOR A FAVOR')
    saldo_ant = saldo_ant if not np.isnan(saldo_ant) else -saldo_ant_fav
    subtotal_pg  = pick_value(summary, col_idx, r'Subtotal pagos')
   
    
    pagos_gracias = sum(
        to_float(row[col_idx['Valor']])
        for row in summary
        if 'PAGO "MUCHAS GRACIAS"' in row[col_idx.get('Descripción', 2)]
    )
    print(f"Pagos 'Muchas Gracias': {pagos_gracias}")
    subtotal_pg = subtotal_pg if not np.isnan(subtotal_pg) else pagos_gracias
    total_a_pagar = saldo_ant - subtotal_pg

    # Construir df de movimientos
    year = metadata['fecha_emision'].year if metadata['fecha_emision'] else datetime.now().year
    month = metadata['fecha_emision'].month if metadata['fecha_emision'] else datetime.now().month
    movimientos_df = build_movements_df(rows, name_idx, cols, year,month)

    # Completar metadata con totales y rangos
    metadata.update({
        'saldo_anterior':        saldo_ant,
        'subtotal_pagado':       subtotal_pg,
        'pagos_muchas_gracias':  pagos_gracias,
        'deuda_a_pagar':         total_a_pagar,
        'num_transacciones':     len(movimientos_df),
        'fecha_min':             movimientos_df['FECHA'].min(),
        'fecha_max':             movimientos_df['FECHA'].max(),
        'total_mes':             movimientos_df['VALOR'].sum(),
        'total_a_pagar': total_a_pagar + movimientos_df['VALOR'].sum(),
    })

    # Mostrar resultados
    df_header = pd.DataFrame([metadata])
    print(df_header)
    # Guardar CSV
    nombre_archivo = f"{PATH_DATOS_TARJETA}/{metadata.get('fecha_emision').strftime('%Y-%m')}.xlsx"

    # Guardar como Excel con 2 hojas
    with pd.ExcelWriter(nombre_archivo, engine='xlsxwriter') as writer:
        df_header.to_excel(writer, sheet_name='Resumen', index=False)
        movimientos_df.to_excel(writer, sheet_name='Movimientos', index=False)

    print(f"Archivo guardado en: {nombre_archivo}")


