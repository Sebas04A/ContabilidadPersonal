import pandas as pd
from contabilidad.backend.services.credit_card.models import DATOS_TARJETA_METADATA, DATOS_TARJETA_HEADER
from contabilidad.backend.services.credit_card.utils import try_parse_date_es, fix_encoding

def find_start_header_index(rows: list[list[str]]) -> int:
    """Encuentra la fila del encabezado que contiene 'Fecha' y 'Valor'."""
    for i, row in enumerate(rows):
        row_lower = [str(r).lower() for r in row]
        if 'fecha' in row_lower and 'valor' in row_lower:
            return i
    for i, row in enumerate(rows):
        if len(row) > 4 and ('fecha' in str(row[0]).lower() or 'fecha' in str(row[1]).lower()):
            return i
    return -1

def extract_metadata_header(rows: list[list[str]]) -> tuple[DATOS_TARJETA_METADATA, int]:
    """Extrae metadatos de las filas anteriores al encabezado.
    
    Soporta múltiples formatos de XLS (distintas versiones del banco):
    - 'Tarjeta: XXXX'          o  'Tarjeta No.: XXXX'
    - 'Fecha de Corte: DD/MMM/YYYY' o 'Fecha de emisión: DD MMM YYYY'
    - 'Pago Máximo el: ...'    o  'Pague Hasta: ...'
    """
    metadata = {}
    empresa = "Unknown"
    last_index = 0

    for i, row in enumerate(rows):
        last_index = i
        for cell in row:
            cell_fixed = fix_encoding(cell)  # normaliza latin1 mal interpretado

            # --- Empresa ---
            if cell_fixed.startswith("Empresa:"):
                empresa = cell_fixed.replace("Empresa:", "").strip()

            # --- Número de tarjeta (dos variantes) ---
            if 'NUM_TARJETA' not in metadata:
                for prefix in ("Tarjeta No.: ", "Tarjeta: "):
                    if prefix in cell_fixed:
                        metadata['NUM_TARJETA'] = cell_fixed.split(prefix, 1)[1].strip()
                        break

            # --- Fecha de emisión / corte (dos variantes) ---
            if 'FECHA_EMISION' not in metadata:
                for prefix in ("Fecha de emisión: ", "Fecha de Corte: "):
                    if prefix in cell_fixed:
                        fecha_str = cell_fixed.split(prefix, 1)[1].strip()
                        # Puede venir junto con más info: tomamos solo la fecha
                        fecha_str = fecha_str.split("\n")[0].split("  ")[0].strip()
                        metadata['FECHA_EMISION'] = try_parse_date_es(fecha_str)
                        break

            # --- Fecha máxima de pago (dos variantes) ---
            if 'FECHA_MAX_PAGO' not in metadata:
                for prefix in ("Pague Hasta: ", "Pago Máximo el: "):
                    if prefix in cell_fixed:
                        fecha_str = cell_fixed.split(prefix, 1)[1].strip()
                        fecha_str = fecha_str.split("\n")[0].split("  ")[0].strip()
                        metadata['FECHA_MAX_PAGO'] = try_parse_date_es(fecha_str)
                        break

        if all(k in metadata for k in ['NUM_TARJETA', 'FECHA_EMISION', 'FECHA_MAX_PAGO']):
            break

    # Si la empresa sigue como 'Unknown', intentamos sacarla de la primera celda no vacía
    if empresa == "Unknown":
        for row in rows[:5]:
            for cell in row:
                if cell.strip():
                    empresa = fix_encoding(cell).split(" ")[0]
                    break
            if empresa != "Unknown":
                break

    try:
        data_tarjeta = DATOS_TARJETA_METADATA(
            EMPRESA=empresa,
            NUM_TARJETA=metadata.get('NUM_TARJETA', ''),
            FECHA_EMISION=metadata.get('FECHA_EMISION', ''),
            FECHA_MAX_PAGO=metadata.get('FECHA_MAX_PAGO', '')
        )
        return data_tarjeta, last_index + 1
    except Exception as e:
        raise ValueError(f"Faltan metadatos vitales de la tarjeta en el archivo. {metadata}. Detalle: {e}")

def get_header_separator_no_movements(rows: list[list[str]]) -> int:
    for i, row in enumerate(rows):
        for cell in row:
            if "T O T A L   N U E V O   S A L D O" in fix_encoding(cell):
                return i
    return None

def get_info_header(df_header: list[list[str]]) -> tuple[DATOS_TARJETA_METADATA, DATOS_TARJETA_HEADER, int]:
    """Extrae la Metadata base y los Saldos Anteriores (Header)"""
    from contabilidad.backend.services.credit_card.utils import to_float
    def pick_value(df_sub: list[list[str]], pattern: str) -> float:
        import re
        for row in df_sub:
            if len(row) < 3: continue
            desc = fix_encoding(row[0]) if len(row) > 0 else ""
            if not desc:
                desc = fix_encoding(row[1]) if len(row) > 1 else ""
            if re.search(pattern, desc, re.IGNORECASE):
                for val in row[::-1]:
                    f = to_float(val)
                    if not pd.isna(f): return f
        return np.nan

    data_tarjeta, data_index = extract_metadata_header(df_header)
    header_index = find_start_header_index(df_header)
    
    if header_index == -1:    
        header_index = get_header_separator_no_movements(df_header)
        
    df_h = df_header[data_index:header_index]
    
    import numpy as np
    dict_header = DATOS_TARJETA_HEADER(
        SALDO_ANTERIOR=pick_value(df_h, 'SALDO ANTERIOR'),
        SUBTOTAL_PAGADO=pick_value(df_h, 'PAGOS/ABONOS|SU PAGO'),
        DEUDAS_MES_ANTERIOR=pick_value(df_h, 'TOTAL ANTES CONSUMOS'),
    )
    
    # Manejar caso Sucursal Virtual donde SALDO ANTERIOR no viene explícito
    if pd.isna(dict_header.SALDO_ANTERIOR) and (not pd.isna(dict_header.DEUDAS_MES_ANTERIOR) and not pd.isna(dict_header.SUBTOTAL_PAGADO)):
        dict_header.SALDO_ANTERIOR = dict_header.DEUDAS_MES_ANTERIOR + dict_header.SUBTOTAL_PAGADO

    return data_tarjeta, dict_header, header_index
