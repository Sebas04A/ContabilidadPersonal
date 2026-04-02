from pathlib import Path
from bs4 import BeautifulSoup
from contabilidad.backend.logger import get_logger
import numpy as np


logger = get_logger(__name__)
def fix_encoding(text: str) -> str:
    """Corrige texto con codificación latin1 mal interpretada como utf-8."""
    try:
        return text.encode('latin1').decode('utf-8')
    except UnicodeError:
        return text

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
def end_movements_index(rows: list[list[str]]) -> int:
    """Encuentra el índice donde terminan los movimientos (filas vacias excepto 2 y 7). Fila 2 diga Subtotal"""
    for i, row in enumerate(rows):
        # print("Row:",row)
        if all(not cell.strip() for j, cell in enumerate(row) if j not in [1, 6]):
            if len(row) > 2 and re.search(r'Subtotal', row[1], re.IGNORECASE):
                return i
    return np.nan

def obtener_indices_todos_movimientos(rows: list[list[str]], empresa: str) -> list[tuple[int, int]]:
    """Obtiene los índices de inicio y fin de todos los bloques de movimientos en el archivo."""
    indices = []
    end_movement=0
    # end_movement = end_movements_index(rows)
    # print("End movements index inicial:", end_movement)
    # print(rows[end_movement:])
    while end_movements_index != np.nan:
        start_new_movement = get_header_separator(rows[end_movement:], empresa) + end_movement +1
        # print("Start new movement index:", start_new_movement)
        if np.isnan(start_new_movement):
            break
        # print(rows[start_new_movement:])
        
        end_movement = end_movements_index(rows[start_new_movement:]) + start_new_movement
        # print("End movements index:", end_movement)
        # print(rows[end_movement:])
        indices.append((start_new_movement, end_movement))
    if not indices:
        end_header_idx = get_header_separator_no_movements(rows)
        # print("Header separator no movements index:", end_header_idx)
        # end_header_idx += start_header_idx 
        # print("Header separator no movements index:", end_header_idx)

        # start_movements_idx = end_header_idx +1
        # end_movements_idx = 0
        indices.append((end_header_idx,end_header_idx))

    # print("Todos los índices de movimientos encontrados:", indices)
    # for indices in indices:
    #     print(f"Bloque de movimientos: inicio={indices[0]}, fin={indices[1]}")
    #     print(rows[indices[0]:indices[1]])
    return indices


def start_movements_index(rows: list[list[str]]):
    """Encuentra el índice donde empiezan los movimientos."""
    for i, row in enumerate(rows):
        if "ARCENTALES" in " ".join(row):
            return i
    return np.nan
def get_totales_index(rows: list[list[str]]):
    """Encuentra el índice donde empiezan los totales."""
    for i, row in enumerate(rows):
        if "SUBTOTAL" in " ".join(row):
            return i
    return len(rows)
def dividir_archivo_tarjeta(rows: list[list[str]]):
    """
    Divide las filas en metadata, encabezado, movimientos y totales.
    """
    from contabilidad.backend.services.credit_card.parsers.metadata import get_info_header
    from contabilidad.backend.services.credit_card.parsers.movements import get_header_separator, end_movements_index
    
    # 1. Sacamos la metadata y los info headers (como totales adeudados previos)
    start_header_index = find_start_header_index(rows)
    metadata_rows = rows[:start_header_index]
    table_rows = rows[start_header_index:]
    cols_names = rows[start_header_index] 
    logger.info(f"start_header_index: {start_header_index}")
    logger.info(f"metadata_rows: {metadata_rows}")
    logger.info(f"table_rows: {table_rows}")
    logger.info(f"cols_names: {cols_names}")

    start_movements_idx = start_movements_index(table_rows)
    if isinstance(start_movements_idx, float) and np.isnan(start_movements_idx):
        start_movements_idx = 1
        
    info_rows=table_rows[1:start_movements_idx]
    movements_rows=table_rows[start_movements_idx+1:]

    parsed_metadata, parsed_header, _ = get_info_header(metadata_rows)
    logger.info(f"Dict_header {(parsed_metadata, parsed_header)}")
    # logger.info(f"start_movements_idx: {start_movements_idx}")
    logger.info(f"info_rows: {info_rows}")
    logger.info(f"movements_rows: {movements_rows}")

    totales_idx = get_totales_index(movements_rows)
    totales_rows = movements_rows[totales_idx:]
    movements_rows = movements_rows[:totales_idx]
    logger.info(f"totales_rows: {totales_rows}")
    logger.info(f"movements_rows: {movements_rows}")
    # 2. Encontramos el inicio y el fin de los movimientos

    return {
        "data_tarjeta": parsed_metadata,
        "dict_header": parsed_header,
        "movimientos": movements_rows, 
        "totales": totales_rows
    }
