import contabilidad.backend.services.bank_parser.account as LecturaCuenta
import pandas as pd
from contabilidad.backend.services.bank_parser.FileProcessingConfig import FileProcessingConfig 
# from contabilidad.config import DATA



def     verificar_nuevas_cuentas(df_cuentas_unido, df_cuentas_comprobacion, columnas_clave=['FECHA',"SALDO"], columnas_a_comparar=["MONTO"]) -> str:
    """
    Compara dos DataFrames y devuelve un resumen de los cambios.

    Args:
        df_cuentas_unido (pd.DataFrame): El primer DataFrame.
        df_cuentas_comprobacion (pd.DataFrame): El segundo DataFrame.
        columnas_clave (list): Columnas para usar como identificador único de fila.
        columnas_a_comparar (list, optional): Columnas a comparar. Si es None, se usan todas.

    Returns:
        str: Una cadena de texto con el resumen de los cambios.
    """

    fecha_inicio_nuevo = df_cuentas_comprobacion["FECHA"].min()
    
    df_cuentas_unido = df_cuentas_unido[df_cuentas_unido["FECHA"] >= fecha_inicio_nuevo]

    if df_cuentas_unido.equals(df_cuentas_comprobacion):
        return "Los DataFrames son idénticos."

    if columnas_a_comparar is None:
        columnas_a_comparar = df_cuentas_unido.columns.tolist()
    print(columnas_a_comparar)

    # Asegurarse de que las columnas clave estén en las columnas a comparar
    cols_completas = sorted(list(set(columnas_clave + columnas_a_comparar)))

    df1 = df_cuentas_unido[cols_completas].copy()
    df2 = df_cuentas_comprobacion[cols_completas].copy()

    # Fusionar los dataframes para alinear las filas
    merged_df = pd.merge(df1, df2, on=columnas_clave, how='outer', suffixes=('_unido', '_comprobacion'), indicator=True)

    cambios = []

    # Filas solo en df_cuentas_unido (eliminadas)
    eliminadas = merged_df[merged_df['_merge'] == 'left_only']
    if not eliminadas.empty:
        cambios.append(f"--- {len(eliminadas)} FILAS ELIMINADAS ---\n{eliminadas[columnas_clave].to_string(index=False)}")

    # Filas solo en df_cuentas_comprobacion (nuevas)
    nuevas = merged_df[merged_df['_merge'] == 'right_only']
    if not nuevas.empty:
        cambios.append(f"--- {len(nuevas)} FILAS NUEVAS ---\n{nuevas[columnas_clave].to_string(index=False)}")

    # Filas modificadas
    modificadas = merged_df[merged_df['_merge'] == 'both']
    for col in [c for c in columnas_a_comparar if c not in columnas_clave]:
        diff = modificadas[modificadas[f'{col}_unido'] != modificadas[f'{col}_comprobacion']]
        if not diff.empty:
            for _, row in diff.iterrows():
                clave_str = ' | '.join([f"{k}: {row[k]}" for k in columnas_clave])
                cambios.append(f"Cambio en [{clave_str}] -> Columna '{col}': '{row[f'{col}_unido']}' -> '{row[f'{col}_comprobacion']}'")
    
    if not cambios:
        return "Los DataFrames son idénticos tras la comparación."
    
    resumen_cambios = "\n".join(cambios)
    print("Se encontraron diferencias:\n" + resumen_cambios)
    raise ValueError("Los DataFrames de cuentas no son idénticos. Revisa las diferencias.")

import pandas as pd
import numpy as np

def comparar_df_completos(df_antiguo: pd.DataFrame, df_nuevo: pd.DataFrame, columnas_clave=['FECHA']) -> str:
    """
    Compara dos DataFrames de datos bancarios usando un conjunto de columnas clave para alinear las filas.
    Está diseñado para manejar floats con precisión y cambios en el orden de las filas.

    Args:
        df_antiguo (pd.DataFrame): El DataFrame de la versión anterior.
        df_nuevo (pd.DataFrame): El DataFrame de la versión nueva.
        columnas_clave (list): Lista de columnas que identifican unívocamente una fila (ej. ['fecha']).

    Returns:
        str: Un string formateado con el resumen de filas añadidas, eliminadas y modificadas.
    """
    # --- 1. Pre-procesamiento y Validación ---
    # Crear copias para no modificar los dataframes originales
    df_antiguo = df_antiguo.copy()
    df_nuevo = df_nuevo.copy()

    for col in columnas_clave:
        if col not in df_antiguo.columns or col not in df_nuevo.columns:
            raise ValueError(f"La columna clave '{col}' no se encuentra en ambos DataFrames.")
        # Asegurar que la columna de fecha sea de tipo datetime para una comparación correcta
        if 'fecha' in col.lower():
            try:
                df_antiguo[col] = pd.to_datetime(df_antiguo[col])
                df_nuevo[col] = pd.to_datetime(df_nuevo[col])
            except Exception as e:
                print(f"Advertencia: No se pudo convertir la columna '{col}' a datetime. Se comparará como texto. Error: {e}")

    # Eliminar duplicados en las claves para evitar errores en el merge
    df_antiguo = df_antiguo.drop_duplicates(subset=columnas_clave)
    df_nuevo = df_nuevo.drop_duplicates(subset=columnas_clave)

    # --- 2. Realizar un "merge" para comparar ---
    # El merge outer nos permite encontrar filas que están en un df pero no en el otro.
    # 'indicator=True' crea una columna llamada '_merge' que nos dice el origen de cada fila.
    df_merged = pd.merge(
        df_antiguo,
        df_nuevo,
        on=columnas_clave,
        how='outer',
        suffixes=('_antiguo', '_nuevo'),
        indicator=True
    )

    # --- 3. Identificar filas añadidas y eliminadas ---
    filas_eliminadas = df_merged[df_merged['_merge'] == 'left_only'][df_antiguo.columns]
    filas_anadidas = df_merged[df_merged['_merge'] == 'right_only'][df_nuevo.columns]

    # --- 4. Identificar filas modificadas con alta precisión ---
    df_comunes = df_merged[df_merged['_merge'] == 'both']
    cambios_modificados = {}
    
    # Columnas a comparar (todas excepto las clave)
    columnas_a_comparar = [c for c in df_nuevo.columns if c not in columnas_clave]

    for index, row in df_comunes.iterrows():
        # Generar una tupla con los valores de las claves para identificar la fila
        id_fila = tuple(row[key] for key in columnas_clave)
        cambios_en_fila = []

        for col in columnas_a_comparar:
            val_antiguo = row[col + '_antiguo']
            val_nuevo = row[col + '_nuevo']
            
            # Manejar valores nulos (NaN)
            if pd.isna(val_antiguo) and pd.isna(val_nuevo):
                continue
            
            # Comparación precisa
            diferentes = False
            # Si es numérico, usar np.isclose para precisión de floats
            if pd.api.types.is_numeric_dtype(df_nuevo[col]):
                if not np.isclose(val_antiguo, val_nuevo, equal_nan=True):
                    diferentes = True
            # Si no, usar comparación normal
            elif val_antiguo != val_nuevo:
                diferentes = True

            if diferentes:
                cambios_en_fila.append(f"    - Columna '{col}': cambió de '{val_antiguo}' a '{val_nuevo}'")

        if cambios_en_fila:
            cambios_modificados[id_fila] = cambios_en_fila

    # --- 5. Construcción del reporte en formato string ---
    reporte = []
    reporte.append("=" * 60)
    reporte.append("      REPORTE DE CAMBIOS EN DATOS BANCARIOS")
    reporte.append("=" * 60)
    reporte.append(f"Resumen: {len(filas_anadidas)} días añadidos, {len(filas_eliminadas)} días eliminados, {len(cambios_modificados)} días modificados.\n")

    reporte.append("-" * 20 + f" DÍAS AÑADIDOS ({len(filas_anadidas)}) " + "-" * 20)
    if not filas_anadidas.empty:
        reporte.append(filas_anadidas.to_string(index=False))
    else:
        reporte.append("Ninguno.")
    reporte.append("\n")

    reporte.append("-" * 20 + f" DÍAS ELIMINADOS ({len(filas_eliminadas)}) " + "-" * 20)
    if not filas_eliminadas.empty:
        reporte.append(filas_eliminadas.to_string(index=False))
    else:
        reporte.append("Ninguno.")
    reporte.append("\n")
    
    reporte.append("-" * 20 + f" DÍAS CON MODIFICACIONES ({len(cambios_modificados)}) " + "-" * 20)
    if cambios_modificados:
        for id_fila, cambios in cambios_modificados.items():
            # Formatear el identificador para que sea legible
            id_str = ", ".join([f"{k}='{v.strftime('%Y-%m-%d') if isinstance(v, pd.Timestamp) else v}'" for k, v in zip(columnas_clave, id_fila)])
            reporte.append(f"-> Cambios en el día con {id_str}:")
            reporte.extend(cambios)
    else:
        reporte.append("Ninguno.")

    return "\n".join(reporte)


# def verificar_cambios(df_completo,df_cuentas,cuenta_nueva_config:FileProcessingConfig):
#     df_cuentas_comprobacion = LecturaCuenta.obtener_todas_cuentas(cuenta_nueva_config)
#     verificar_nuevas_cuentas(df_cuentas,df_cuentas_comprobacion)
#     return
