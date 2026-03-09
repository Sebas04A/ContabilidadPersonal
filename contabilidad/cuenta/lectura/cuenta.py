import pandas as pd
from contabilidad.config import PATH_CUENTAS_ACTUAL
from contabilidad.cuenta.lectura import FileProcessingConfig as FileProcessingConfig
from contabilidad.cuenta.validacion import imprimir_cambios



# def leer_datos_guardados_cuenta():
#     """
#     Lee los datos guardados de la cuenta guardados en PATH_CUENTA_UNIDO
#     """
#     df= pd.read_excel(PATH_CUENTAS_ACTUAL)
#     df['FECHA'] = pd.to_datetime(df['FECHA'], format='%Y-%m-%d')
#     df["MONTO"] = df["CREDITO"] - df["DEBITO"]
#     return df
def leer_datos_guardados_cuenta():
    """
    Lee los datos guardados de la cuenta guardados en PATH_CUENTA_UNIDO
    """
    df= pd.read_excel(PATH_CUENTAS_ACTUAL)
    df['FECHA'] = pd.to_datetime(df['FECHA'], format='%Y-%m-%d')
    df["CREDITO"] = df["MONTO"].apply(lambda x: x if x > 0 else 0)
    df["DEBITO"] = df["MONTO"].apply(lambda x: -x if x < 0 else 0)
    # df["MONTO"] = df["CREDITO"] - df["DEBITO"]
    return df

def normalizar_monto(df,new_file_config:FileProcessingConfig):
    df = df.copy()
    df = df[~df[new_file_config.monto_col].str.contains(r'[^0-9.\-,$]', na=False) ]
    # Normalizar la columna de monto directamente en lugar de crear una nueva columna MONTO
    df[new_file_config.monto_col] = df[new_file_config.monto_col].replace({r'\$': '', r'\.': '', r',': '.'}, regex=True).astype(float)

    # PONER CREDITOS Y DEBITOS usando la columna original normalizada
    df["DEBITO"]= df[new_file_config.monto_col].apply(lambda x: -x if x < 0 else 0)
    df["CREDITO"]= df[new_file_config.monto_col].apply(lambda x: x if x > 0 else 0)
    return df

def normalizar_saldo(df,new_file_config:FileProcessingConfig):
    df = df.copy()
    s = (
        df[new_file_config.saldo_col]
        .astype(str)
        .str.replace(r'[^\d\-,\.]', '', regex=True)
    )
    s = s.str.replace(
        r'(?<=\d)[,\.](?=\d{3}(?:[,\.]|$))',
        '',
        regex=True
    )
    s = s.str.replace(',', '.', regex=False)
    df[new_file_config.saldo_col] = pd.to_numeric(s, errors='coerce')
    return df

def limpiar_filas_por_descripcion(df,new_file_config:FileProcessingConfig):
    df = df.copy()
    for desc in new_file_config.descripcion_a_eliminar:
        df = df[~df[new_file_config.descripcion_col].str.contains(desc, na=False)]
    return df

def limpiar(df,new_file_config:FileProcessingConfig):
    df = df.copy()
    df = eliminar_encabezado(df,new_file_config)
    #Eliminar columnas nan
    df = df.dropna(axis=1, how='all')
    df = df.loc[:, ~df.columns.str.startswith('Unnamed')]
    #Eliminar fechas vacias
    df = df.dropna(subset=[new_file_config.fecha_col])

    df = limpiar_filas_por_descripcion(df,new_file_config)
    return df

def eliminar_encabezado(df,new_file_config:FileProcessingConfig):
    fila_encabezado = None
    for i, fila in df.iterrows():
        if fila.astype(str).str.contains(new_file_config.fecha_col, case=False).any():
            fila_encabezado = i
            break
    if fila_encabezado is not None:
        fila_encabezado+=1
    else :
        fila_encabezado = 0
    if fila_encabezado is not None:
        print(f"Encabezados encontrados en la fila {fila_encabezado} (Excel)")
        return pd.read_excel(new_file_config.path, skiprows=fila_encabezado)
    else:
        print("No se encontró ninguna fila con 'Fecha', revissar manualmente el archivo.")
        raise ValueError("No se encontró ninguna fila con 'Fecha', revissar manualmente el archivo.")

def noramalizar(df,new_file_config:FileProcessingConfig):
    print("Iniciando normalización...")
    df = df.copy()
    df_saldo_norm = normalizar_saldo(df,new_file_config)
    print("Saldo normalizado, primeras filas:\n", df_saldo_norm.head())
    if not new_file_config.tiene_monto:
        df_saldo_norm["MONTO"]= df_saldo_norm[new_file_config.credito_col] - df_saldo_norm[new_file_config.debito_col]
        print("Monto calculado, primeras filas:\n", df_saldo_norm.head())
    if new_file_config.tiene_monto:
        df_saldo_norm = normalizar_monto(df_saldo_norm,new_file_config)
        print("Monto normalizado, primeras filas:\n", df_saldo_norm.head())

    df_saldo_norm[new_file_config.fecha_col] = pd.to_datetime(df_saldo_norm[new_file_config.fecha_col], format=new_file_config.fecha_format, errors='coerce')

    df_saldo_norm.rename(columns={new_file_config.fecha_col: 'FECHA', new_file_config.saldo_col: 'SALDO',new_file_config.descripcion_col:"DESCRIPCION", new_file_config.credito_col: "CREDITO", new_file_config.debito_col: "DEBITO", new_file_config.monto_col: "MONTO"}, inplace=True)
    if not df.columns.is_unique:
        print("¡Bingo! El DataFrame tiene nombres de columnas duplicados.")
        duplicados = df.columns[df.columns.duplicated()].unique().tolist()
        print(f"Columnas repetidas: {duplicados}")
        print(df.head())
        raise ValueError("El DataFrame tiene nombres de columnas duplicados, revisar el archivo de entrada.")
    # df_saldo_norm = df_saldo_norm[::-1].reset_index(drop=True)
    return df_saldo_norm[["FECHA","SALDO","DESCRIPCION","DEBITO","CREDITO","MONTO"]]


def leer_cuenta_nuevo(new_file_config:FileProcessingConfig):

    """
    Lee un archivo Excel de movimientos de cuenta, limpia,normaliza, dado un conjunto de configuraciones dado.
    """
    
    df = pd.read_excel(new_file_config.path)

    df_limpio = limpiar(df,new_file_config)

    return noramalizar(df_limpio,new_file_config)

def leer_cuenta_csv(new_file_config:FileProcessingConfig):
    """
    Lee un archivo CSV de movimientos de cuenta, limpia,normaliza, dado un conjunto de configuraciones dado.
    """
    # print(f"Leyendo CSV: {new_file_config.path}")
    df = pd.read_csv(new_file_config.path, encoding='utf-8')
    # print(f"Archivo CSV leído, primeras filas:\n{df.head()}")
    # df_limpio = limpiar(df, new_file_config)
    df_limpio = limpiar_filas_por_descripcion(df,new_file_config)
    print(f"Archivo CSV limpiado, primeras filas:\n{df_limpio.head()}")
    return noramalizar(df_limpio, new_file_config)

def obtener_todas_cuentas(new_file_config:FileProcessingConfig,ordenar_fecha=False):
    """ Lee las cuentas guardadas y las une con las cuentas del nuevo archivo si se da, se corta el anterior df para añadir limpiamente el nuevo"""
    
    df_unido_antiguo = leer_datos_guardados_cuenta()
    if new_file_config is None:
        return df_unido_antiguo
    
    path_nuevo = new_file_config.path
    print(f"Leyendo archivo nuevo: {path_nuevo}")
    df_nuevo = leer_cuenta_nuevo(new_file_config)
    print("-----------COMPARANDO DATOS NUEVOS CON ANTERIORES")
    imprimir_cambios(df_nuevo)
    fecha_inicio_nuevo = df_nuevo["FECHA"].min()
    #quitar los minutos y segundos por si acaso
    fecha_inicio_nuevo = fecha_inicio_nuevo.normalize()
    print(f"Fecha inicio nuevo archivo: {fecha_inicio_nuevo}")

    df_antiguo_cortado = df_unido_antiguo[df_unido_antiguo["FECHA"] < fecha_inicio_nuevo].copy()

    print(df_nuevo.head(10))
    print(df_antiguo_cortado.tail(10))


    df_unido_antiguo = pd.concat([df_antiguo_cortado, df_nuevo], ignore_index=True)
    if ordenar_fecha:
        # df_unido_antiguo = ordenar_por_saldo(df_unido_antiguo)
        df_unido_antiguo.sort_values(by='FECHA', inplace=True)
    df_unido_antiguo.reset_index(drop=True, inplace=True)
    return df_unido_antiguo
    
    return df_unido_antiguo
