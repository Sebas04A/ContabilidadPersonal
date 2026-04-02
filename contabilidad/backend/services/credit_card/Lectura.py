import pandas as pd
from pathlib import Path
from contabilidad.config import PATH_TARJETA_UNIDA

def normalizar(df):
    df = df.copy()
    if not df.empty and 'FECHA' in df.columns:
        df.sort_values(by='FECHA', inplace=True)
        if "VALOR" in df.columns:
            df["ACUMULADO"] = df["VALOR"].cumsum()
    return df

def limpiar(df):
    df = df.copy()
    if 'FECHA' in df.columns:
        df = df[df["FECHA"].notna()]
    return df

def leer_tarjeta(path_excel: str | Path):
    """Lee un archivo Excel mensual con hojas 'Resumen' y 'Movimientos'."""
    archivo = Path(path_excel)

    if not archivo.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {archivo}")

    periodo = archivo.stem.split('_')[0]  # Extrae 'YYYY-MM' del nombre

    df_resumen = pd.read_excel(archivo, sheet_name='Resumen')
    df_movs = pd.read_excel(archivo, sheet_name='Movimientos')

    df_movs = limpiar(df_movs)
    df_movs = normalizar(df_movs)

    df_resumen['Periodo'] = periodo
    df_movs['Periodo'] = periodo

    return df_resumen, df_movs

def leer_tarjetas(carpeta=None):
    """
    Lee todos los archivos mensuales en una carpeta y concatenalos.
    Si carpeta no es proveido, lee el archivo unificado de PATH_TARJETA_UNIDA.
    """
    if carpeta is None:
        archivo = Path(PATH_TARJETA_UNIDA)
        if not archivo.exists():
            return pd.DataFrame(), pd.DataFrame()
        df_resumen = pd.read_excel(archivo, sheet_name='Resumen')
        df_movs = pd.read_excel(archivo, sheet_name='Movimientos')
        return df_resumen, df_movs
    
    carpeta_path = Path(carpeta)
    archivos = sorted(carpeta_path.glob("????-??.xlsx"))

    resúmenes = []
    movimientos = []
    print(f"Leyendo {len(archivos)} archivos de tarjetas en {carpeta_path}")
    for archivo in archivos:
        try:
            df_resumen, df_movs = leer_tarjeta(archivo)
            resúmenes.append(df_resumen)
            movimientos.append(df_movs)
        except Exception as e:
            print(f"Error leyendo {archivo.name}: {e}")

    if not resúmenes or not movimientos:
        return pd.DataFrame(), pd.DataFrame()

    movimientos_normalizados = normalizar(pd.concat(movimientos, ignore_index=True))
    df_resumen_total = pd.concat(resúmenes, ignore_index=True)

    return df_resumen_total, movimientos_normalizados
