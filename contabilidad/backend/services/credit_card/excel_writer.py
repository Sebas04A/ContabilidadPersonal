import pandas as pd

def auto_ajustar_columnas(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame):
    """
    Ajusta el ancho de las columnas de una hoja de Excel específica.
    """
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]
    
    formato_moneda = workbook.add_format({'num_format': '"$"#,##0.00'})
    
    for i, col in enumerate(df.columns):
        series = df[col]
        
        # Calcular ancho máximo basado en el contenido y el encabezado
        max_len = max(
            series.astype(str).map(len).max(),
            len(str(series.name))
        ) + 2
        
        # Limitar el ancho máximo a 50
        max_len = min(max_len, 50)
        
        if col in ['Valor', 'TOTAL_A_PAGAR', 'TOTAL_CONSUMO', 'MINIMO_A_PAGAR', 'DEUDAS_MES_ANTERIOR', 'SUBTOTAL_PAGADO', 'SALDO_ANTERIOR']:
            worksheet.set_column(i, i, max_len, formato_moneda)
        else:
            worksheet.set_column(i, i, max_len)

def guardar_archivo(df_movimientos: pd.DataFrame, data_tarjeta, file_path: str):
    """
    Guarda el DataFrame de movimientos y los metadatos en un archivo Excel.
    """
    df_totales = pd.DataFrame([data_tarjeta.__dict__])
    
    # Transponer df_totales: columnas pasan a ser índices y los valores una columna (0)
    df_totales_t = df_totales.T
    # Renombrar la columna de los valores
    df_totales_t.columns = ['Valor']
    # Reiniciar el índice para que los nombres originales de columnas pasen a una nueva columna
    df_totales_t.reset_index(inplace=True)
    # Renombrar las columnas para que sea claro:
    df_totales_t.rename(columns={'index': 'Métrica'}, inplace=True)
    
    with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
        df_movimientos.to_excel(writer, sheet_name='Movimientos', index=False)
        auto_ajustar_columnas(writer, 'Movimientos', df_movimientos)
        df_totales_t.to_excel(writer, sheet_name='METADATA', index=False)
        auto_ajustar_columnas(writer, 'METADATA', df_totales_t)
