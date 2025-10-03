import re
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from contabilidad.config import PATH_TARJETA_PROCESADA,PATH_TARJETAS_DATA_CRUDA
from contabilidad.tarjeta.tiposCsvDatos import DATOS_TARJETA_COMPLETA,DATOS_TARJETA_HEADER,DATOS_TARJETA_INFO_MOVIMIENTOS,DATOS_TARJETA_METADATA,DATOS_TARJETA_TOTALES

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
        pago_fecha = emision.strftime('%d %b %Y')
    pago_fecha = try_parse_date_es(pago_fecha) if pago_fecha else None
    return DATOS_TARJETA_METADATA(
        EMPRESA=meta.get('Empresa', ''),
        NUM_TARJETA=meta.get('Tarjeta No.', ''),
        FECHA_EMISION=emision,
        FECHA_MAX_PAGO=pago_fecha
    )


def get_header_separator(rows: list[list[str]], empresa: str) -> int:
    """Encuentra la fila que separa el resumen de los movimientos detallados con el nombre de la tarjeta. Si no se encuentra, devuelve el final de los movimientos."""
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


# def pick_value(summary: list[list[str]], col_idx: dict, pattern: str) -> float:
#     """Busca en 'Descripción' y devuelve el valor numérico que coincida con el patrón."""
#     for row in summary:
#         desc = row[col_idx.get('Descripción', 2)]
#         if re.search(pattern, desc, re.IGNORECASE):
#             return to_float(row[col_idx['Valor']])
#     return np.nan

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
    # print(f"Data")
    # print(data[:5])  # Mostrar las primeras 5 filas de datos
    df = pd.DataFrame(data, columns=cols)
    df['Valor'] = df['Valor'].apply(to_float)
    df = pd.concat([movements_header, df], ignore_index=True)
    notas_credito = df["Operación"].str.contains("N/C", case=False, na=False)
    df.loc[notas_credito, 'Valor'] *= -1


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

def extract_header_movements(df_header) -> pd.DataFrame:
    """
    Extrae el encabezado de los movimientos a partir de las filas y el índice del encabezado.
    """
    def is_movement(row) -> bool:
        # row["Operación"] = row["Operación"].strip().upper()
        return row["Operación"] != ""
    header_movements = df_header[df_header.apply(is_movement, axis=1)]
    return header_movements


def get_info_header(df_header: pd.DataFrame) -> DATOS_TARJETA_HEADER:
    # print(f"DataFrame Header:\n{df_header}")

    saldo_ant  = pick_value(df_header, r'SALDO ANTERIOR(?! A FAVOR)')
    # Valores de resumen
    saldo_ant_fav = pick_value(df_header, r'SALDO ANTERIOR A FAVOR')
    saldo_ant = saldo_ant if not np.isnan(saldo_ant) else -saldo_ant_fav
    # print("Saldo Anterior:", saldo_ant)

    

    pagos_gracias = df_header[df_header['Descripción'].str.contains('PAGO "MUCHAS GRACIAS"', case=False, na=False)]['Valor'].sum()
    # print(f"Pagos 'Muchas Gracias': {pagos_gracias}")

    subtotal_pg  = pick_value(df_header, r'Subtotal pagos')
    if np.isnan(subtotal_pg): 
        print("________--------------REVISAR SUBTOTAL PAGOS NAN-----------------__________")
        subtotal_pg=pagos_gracias

    # print("Subtotal pagado calculado:", pagos_gracias," Subtotal pagado extraído:", subtotal_pg)
    if not np.isclose(pagos_gracias, subtotal_pg):
        raise Warning(f"Advertencia: El valor de 'pagos_gracias' ({pagos_gracias}) no coincide con 'subtotal_pg' ({subtotal_pg}).")

    if np.isnan(subtotal_pg) and not np.isnan(pagos_gracias):
        raise Warning("Advertencia: 'subtotal_pg' es NaN pero 'pagos_gracias' tiene un valor.")
    
    movements_header= extract_header_movements(df_header=df_header)
    # print(f"Movimientos header: {movements_header}")
    debito_header = movements_header[movements_header["Operación"].str.contains("N/D", case=False, na=False)]
    credito_header = movements_header[movements_header["Operación"].str.contains("N/C", case=False, na=False)]
    total_movimientos_header = debito_header["Valor"].sum() - credito_header["Valor"].sum()


    deuda_mes_anterior = saldo_ant - subtotal_pg
    # total_a_pagar_calculado = deuda_mes_anterior + total_movimientos_header

    return DATOS_TARJETA_HEADER(
        SALDO_ANTERIOR=        saldo_ant,
        SUBTOTAL_PAGADO=       subtotal_pg,
        DEUDAS_MES_ANTERIOR=   deuda_mes_anterior,
        # TOTAL_ANTES_CONSUMOS=  total_a_pagar_calculado,
    )

def end_movements_index(rows: list[list[str]]) -> int:
    """Encuentra el índice donde terminan los movimientos (filas vacias excepto 2 y 7). Fila 2 diga Subtotal"""
    for i, row in enumerate(rows):
        # print("Row:",row)
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
       totales_filtrados.append(fila_nueva)
       fila_nueva = []
    return totales_filtrados

def get_info_totales(totales_info: list[list[str]]) -> DATOS_TARJETA_TOTALES:
    """Extrae totales de las filas de totales."""
    totales_filtrados = extraer_valores_nulos(totales_info)
    # print(f"Totales filtrados: {totales_filtrados}")
    
    subtotal = totales_filtrados[0]
    if re.search(r'Subtotal', subtotal[0], re.IGNORECASE):
        subtotal[1] = to_float(subtotal[1])
        totales_filtrados[0] = subtotal
    

    
    df_totales = pd.DataFrame(totales_filtrados, columns=['Descripción','Valor'])
    df_totales['Valor'] = df_totales['Valor'].astype(float)

    total_a_pagar = pick_value(df_totales, r'TOTAL A PAGAR')
    if np.isnan(total_a_pagar):
        total_a_pagar = pick_value(df_totales, r'TOTAL A')
    total_consumo_mes = pick_value(df_totales, r'TOTAL CONSUMOS MES')
    if np.isnan(total_consumo_mes):
        total_consumo_mes = 0
    minimo_a_pagar = pick_value(df_totales, r'PAGO M')
    return DATOS_TARJETA_TOTALES(
        TOTAL_CONSUMO= total_consumo_mes,
        TOTAL_A_PAGAR= total_a_pagar,
        MINIMO_A_PAGAR= minimo_a_pagar
    )
def auto_ajustar_columnas(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame):
    """
    Ajusta el ancho de las columnas de una hoja de Excel específica.

    Args:
        writer (pd.ExcelWriter): El objeto ExcelWriter.
        sheet_name (str): El nombre de la hoja a formatear.
        df (pd.DataFrame): El DataFrame que se usó para crear la hoja.
    """
    worksheet = writer.sheets[sheet_name]
    for idx, col in enumerate(df):
        series = df[col]
        max_len = (
            max(
                (
                    series.astype(str).map(len).max(),  # Longitud del dato más largo
                    len(str(series.name)),  # Longitud del encabezado
                )
            )
            + 1 # Un poco de espacio extra
        )
        worksheet.set_column(idx, idx, max_len)

def guardar_archivo(df_movimientos: pd.DataFrame, data_tarjeta: DATOS_TARJETA_COMPLETA, file_path: str):
    """Guarda el DataFrame de movimientos y los metadatos en un archivo Excel."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    
    df_metadata = pd.DataFrame([data_tarjeta.__dict__],columns=data_tarjeta.get_column_order())
    # print(data_tarjeta.get_column_order())
    df_metadata_ordenado = df_metadata[data_tarjeta.get_column_order()]
    

    # print(f"Datos a guardar:\n{df_metadata_ordenado}")
    with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
        df_metadata_ordenado.to_excel(writer, sheet_name='Resumen', index=False)
        df_movimientos.to_excel(writer, sheet_name='Movimientos', index=False)

        auto_ajustar_columnas(writer, 'Resumen', df_metadata_ordenado)


    print(f"Archivo guardado en: {path}")

def convertir_a_datetime_con_referencia(fecha_str: str, fecha_referencia: datetime) -> datetime:
    """
    Convierte una fecha 'DD/MM' a un objeto datetime, usando una fecha de 
    referencia completa para determinar el año correcto.

    Args:
        fecha_str: La fecha en formato 'DD/MM'.
        fecha_referencia: Una fecha (datetime) que es cronológicamente posterior
                          a la fecha que se está convirtiendo.

    Returns:
        Un objeto datetime con el año, mes y día correctos.
    """
    dia, mes = map(int, fecha_str.split('/'))
    
    # 1. Creamos una fecha candidata con el año de la fecha de referencia.
    año_candidato = fecha_referencia.year
    fecha_candidata = datetime(year=año_candidato, month=mes, day=dia)
    
    # 2. Si la fecha candidata es posterior a la referencia, le restamos un año.
    if fecha_candidata > fecha_referencia:
        return fecha_candidata.replace(year=año_candidato - 1)
    # 3. De lo contrario, el año era correcto.
    else:
        return fecha_candidata


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

def dividir_archivo_tarjeta(rows: list[list[str]]):
    """Divide las filas en metadata, encabezado, movimientos y totales."""
    start_header_idx = find_start_header_index(rows)
    
    # print(rows)

    metadata_rows = rows[:start_header_idx]
    table_rows = rows[start_header_idx:]
    cols_names = rows[start_header_idx]

    metadata = extract_metadata_header(metadata_rows)    
    # print("Metadata extraída:", metadata)
    
    indices_movimientos= obtener_indices_todos_movimientos(rows[start_header_idx:], metadata.EMPRESA)
    indices_movimientos = [(start + start_header_idx, end + start_header_idx) for start, end in indices_movimientos]
    # print("Movimientos ajustados", indices_movimientos)
    end_header_idx = indices_movimientos[0][0] - 1

    # print("Header separator index:", end_header_idx)
    # if(np.isnan(end_header_idx)):
    #     end_header_idx = get_header_separator_no_movements(table_rows)
    #     end_header_idx += start_header_idx 
    #     # print("Header separator no movements index:", end_header_idx)

    #     start_movements_idx = end_header_idx +1
    #     end_movements_idx = 0
    # else:
    #     indices = obtener_indices_todos_movimientos(rows, metadata.EMPRESA)
    #     print("Todos los índices de movimientos encontrados:", indices)
        
    #     return
    #     end_header_idx += start_header_idx  # Ajustar al índice global
    #     start_movements_idx = end_header_idx +1
    #     end_movements_idx = end_movements_index(rows=rows[start_movements_idx:])

    #     new_start_header_idx = start_movements_idx + end_movements_idx + 1
    #     print("New start header index calculation:", new_start_header_idx)
    #     print(rows[new_start_header_idx:])
    #     new_end_movements_idx = get_header_separator(rows[new_start_header_idx:], metadata.EMPRESA)
    #     print("New end movements index calculation:", new_end_movements_idx)
    #     # return
    #     while new_end_movements_idx != np.nan:
    #         new_start_header_idx += new_end_movements_idx + 1
    #         print("New start header index calculation in loop:", new_start_header_idx)
    #         temp_end = end_movements_index(rows=rows[new_start_header_idx:])
    #         if temp_end == np.nan:
    #             break
    #         new_end_movements_idx = temp_end
    #     print(f"New start header index: {new_start_header_idx}, New end movements index: {new_end_movements_idx}")
        

    # print(end_header_idx)
    # print("\nHEADER\n",rows[start_header_idx:end_header_idx])

    


    # print("MOVIMIENTOS\n",rows[start_movements_idx:end_movements_idx])
    # print(start_movements_idx,end_movements_idx)
        
    # print("TOTALES\n",rows[end_movements_idx:])
    
    return start_header_idx,end_header_idx, indices_movimientos


def extraer_data_tarjeta(file_path: str):
    """
    Genera un CSV de movimientos de tarjeta a partir de un archivo .xls extraido de banca
    y el resumen de los movimientos
    """
    path = Path(file_path)
    print(f"Procesando archivo: {path}")
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")
    if path.suffix.lower() != '.xls':
        raise ValueError(f"Se esperaba un archivo con extensión .xls y se recibió: {path.name}")

    rows = load_table(path)
    start_header_idx,end_header_idx,movimientos_idx = dividir_archivo_tarjeta(rows)
    end_movements_idx = movimientos_idx[-1][1]  # Ajustar al índice global

    metadata = extract_metadata_header(rows[:start_header_idx])    

    header_info = rows[start_header_idx+1 :end_header_idx]
    cols_names = rows[start_header_idx]
    df_header = pd.DataFrame(header_info, columns=cols_names)
    df_header['Valor'] = df_header['Valor'].apply(to_float)
    # print(df_header)

    movements_rows = []
    for start, end in movimientos_idx:
        movements_rows.extend(rows[start : end])

    # print("Movements rows",movements_rows)

    df_movements = pd.DataFrame(movements_rows, columns=cols_names)
    df_movements['Valor'] = df_movements['Valor'].apply(to_float)

    # print(df_movements)

    totales_info = rows[end_movements_idx:]
    # print(f"Totales info: {totales_info}")
    
    header_info = get_info_header(df_header=df_header)
    # print("Header info extraída:", header_info)

    info_totales = get_info_totales(totales_info=totales_info)
    # print("Info totales extraída:", info_totales)

    TOTAL_A_PAGAR = info_totales.TOTAL_A_PAGAR

    

    movements_header = extract_header_movements(df_header=df_header)
    movements_header.loc[:, 'Valor'] = movements_header['Valor'].astype(float)
    # print(f"Movements header:\n{movements_header}")
    
    df_normalizado = build_movements_df(
        data=movements_rows,
        cols=cols_names,
        year=metadata.FECHA_EMISION.year,
        month_statement=metadata.FECHA_EMISION.month,
        movements_header=movements_header
    )

    total_movimientos = df_normalizado['VALOR'].sum()
    total_calculado = total_movimientos + header_info.DEUDAS_MES_ANTERIOR
    # print('Total movimientos:', total_movimientos, "Antes consumos:", header_info.TOTAL_ANTES_CONSUMOS)
    # print(f"Total extraido : {TOTAL_A_PAGAR}, total calculado: {total_calculado}")
    # print(f"Total extraido : {TOTAL_A_PAGAR}, total calculado: {total_calculado},total movimientos: {total_movimientos}")
    if not np.isclose(TOTAL_A_PAGAR, total_calculado, atol=1):
        print(f"Total movimientos: {total_movimientos}, Deudas mes anterior: {header_info.DEUDAS_MES_ANTERIOR}")
        raise Warning(f"Advertencia: El valor de 'TOTAL_A_PAGAR' ({TOTAL_A_PAGAR}) no coincide con 'total_calculado' ({total_calculado}).")

    min_fecha_movimientos  = df_normalizado['FECHA'].min()
    max_fecha_movimientos = df_normalizado['FECHA'].max()
    # print(f"Rango de movimientos: {min_fecha_movimientos} - {max_fecha_movimientos}")

    movimientos_info=DATOS_TARJETA_INFO_MOVIMIENTOS(
        MIN_FECHA_MOVIMIENTO=min_fecha_movimientos,
        MAX_FECHA_MOVIMIENTO=max_fecha_movimientos
    )

    # print("METADATA ROWS:")
    # print(metadata_rows)
    # print("HEADER:")
    # print(df_header) 
    # print("MOVIMIENTOS:")
    # print(df_movements)
    # print("TOTALES:")
    # print(totales_info)

    data_completa= DATOS_TARJETA_COMPLETA.desde_partes(
        metadata=metadata,
        header=header_info,
        totales=info_totales,
        movimientos=movimientos_info
    )

    
    # data_completa = {**metadata, **header_info, **info_totales, **{
    #     'min_fecha_movimientos': min_fecha_movimientos,
    #     'max_fecha_movimientos': max_fecha_movimientos
    # }}
    # print("Datos completos:", data_completa)

    year  = data_completa.FECHA_EMISION.year 
    month = data_completa.FECHA_EMISION.month 

    guardar_archivo(df_normalizado, data_completa, PATH_TARJETA_PROCESADA + f"/{year}-{month:02}.xlsx")

    return data_completa

    df_movements_normalizado = build_movements_df(df_movements, cols_names, year, month)

    guardar_archivo(df_movements_normalizado, data_completa, PATH_TARJETAS_DATA + f"/{year}-{month:02}.xlsx")
    return
    # Construir df de movimientos
    year = metadata['fecha_emision'].year if metadata['fecha_emision'] else datetime.now().year
    month = metadata['fecha_emision'].month if metadata['fecha_emision'] else datetime.now().month
    movimientos_df = build_movements_df(rows, name_idx, cols, year,month)

    # Completar metadata con totales y rangos
    metadata.update({
        'saldo_anterior':        saldo_ant,
        'subtotal_pagado':       subtotal_pg,
        'pagos_muchas_gracias':  pagos_gracias,
        'total_a_pagar':         total_a_pagar,
        'num_transacciones':     len(movimientos_df),
        'fecha_min':             movimientos_df['FECHA'].min(),
        'fecha_max':             movimientos_df['FECHA'].max(),
        'total_mes':             movimientos_df['VALOR'].sum(),
        'total_a_pagar_despues': total_a_pagar + movimientos_df['VALOR'].sum(),
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


def extraer_data_todas_tarjetas(carpeta: str=PATH_TARJETAS_DATA_CRUDA):
    """Genera archivos CSV para todos los archivos .xls en una carpeta."""
    carpeta_path = Path(carpeta)
    archivos = sorted(carpeta_path.glob("*.xls"))
    
    print(f"Encontrados {len(archivos)} archivos en {carpeta_path}")
    for archivo in archivos:
        try:
            print(f"----------------------Procesando {archivo.name}----------------------\n")
            extraer_data_tarjeta(archivo)
            print(f"----------------------Finalizado {archivo.name}----------------------\n")
        except Exception as e:
            print(f"Error procesando {archivo.name}: {e}")


def leer_archivo_limpio(path: str) -> tuple[pd.DataFrame, dict]:
    """Lee un archivo Excel limpio y devuelve el DataFrame de movimientos y los metadatos."""
    archivo = Path(path)
    print(f"Procesando archivo limpio: {archivo}")
    if not archivo.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {archivo}")

    df_resumen = pd.read_excel(archivo, sheet_name='Resumen')
    df_movs = pd.read_excel(archivo, sheet_name='Movimientos')

    # print(f"Metadatos leídos:\n{df_resumen}")
    # print(f"Movimientos leídos:\n {df_movs} filas")

    df_movs.sort_values(by='FECHA', inplace=True)
    df_movs["ACUMULADO"] = df_movs["VALOR"].cumsum()

    metadata = df_resumen.iloc[0].to_dict()
    return df_movs, metadata

def leer_archivos_limpios(carpeta=PATH_TARJETA_PROCESADA):
    """Lee todos los archivos limpios en una carpeta y concatena los datos."""
    carpeta_path = Path(carpeta)
    archivos = sorted(carpeta_path.glob("????-??.xlsx"))

    movimientos = []
    metadatos = []
    print(f"Leyendo {len(archivos)} archivos de tarjetas en {carpeta_path}")
    for archivo in archivos:
        try:
            df_movs, metadata = leer_archivo_limpio(archivo)
            print(f"Leído {archivo.name} con {len(df_movs)} movimientos.")
            movimientos.append(df_movs)
            metadatos.append(metadata)
        except Exception as e:
            print(f"Error leyendo {archivo.name}: {e}")
    if not movimientos:
        raise RuntimeError("No se leyeron archivos de movimientos correctamente.")
    movimientos_normalizados = pd.concat(movimientos, ignore_index=True)
    df_metadatos = pd.DataFrame(metadatos)

    return df_metadatos, movimientos_normalizados