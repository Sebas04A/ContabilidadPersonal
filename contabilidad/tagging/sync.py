
import pandas as pd
import os
import sys



from contabilidad.backend.services.bank_parser.account import read_saved_account_data
from contabilidad.backend.services.credit_card.Lectura import leer_tarjetas
from contabilidad.config import PATH_TARJETA_PROCESADA
from contabilidad.tagging import rules_handler as rules_module

# Definimos las columnas extra aquí para asegurar consistencia
COLUMNAS_EXTRA = {
    'nombre_limpio': '',
    'categoria': '---',
    'tags': '',
    'prioridad': '---',
    'es_fijo': False,
    'pertenece_a': '---',
    'es_reembolsable': False,
    'deudor': '',
    'felicidad': 0,
    'revisado': False,
    'nota': '',
    'split_group_id': ''
}

def cargar_datos_fuente():
    """Carga y unifica datos de Cuentas y Tarjetas según lógica del usuario."""
    try:
        # 1. Cargar Cuenta
        df_cuenta = read_saved_account_data()
        
        # 2. Cargar Tarjetas
        # df_resumen, df_movs = leer_tarjetas(PATH_TARJETA_PROCESADA)
        # Nota: leer_tarjetas a veces imprime cosas, esperamos que no rompa streamlit
        _, df_movs = leer_tarjetas(PATH_TARJETA_PROCESADA)
        df_tarjetas = df_movs

        return df_cuenta, df_tarjetas
    except Exception as e:
        raise RuntimeError(f"Error cargando fuentes de datos: {e}")

def transformar_datos(df_cuenta, df_tarjetas):
    """Aplica la transformación solicitada para unificar formatos."""
    
    # --- CUENTA ---
    # Asumimos que df_cuenta ya tiene FECHA, DESCRIPCION, MONTO (normalizado)
    # Según lectura/cuenta.py: retorna FECHA, SALDO, DESCRIPCION, DEBITO, CREDITO, MONTO
    df_cuenta_etiquetado = df_cuenta[["FECHA", "DESCRIPCION", "MONTO"]].copy()
    df_cuenta_etiquetado["TIPO"] = "CUENTA"

    # --- TARJETA ---
    # Según user: extraer FECHA, DESCRIPCION, VALOR. Renombrar VALOR->MONTO. Multiplicar por -1.
    if 'VALOR' in df_tarjetas.columns:
        df_tarjetas_etiquetado = df_tarjetas[["FECHA", "DESCRIPCION", "VALOR"]].copy()
        df_tarjetas_etiquetado = df_tarjetas_etiquetado.rename(columns={"VALOR": "MONTO"})
    elif 'Monto' in df_tarjetas.columns:
         df_tarjetas_etiquetado = df_tarjetas[["FECHA", "DESCRIPCION", "Monto"]].copy()
         df_tarjetas_etiquetado = df_tarjetas_etiquetado.rename(columns={"Monto": "MONTO"})
    else:
        # Fallback si columnas cambian
        raise ValueError("No se encontró columna VALOR o Monto en dataframe de tarjetas")

    df_tarjetas_etiquetado["MONTO"] = df_tarjetas_etiquetado["MONTO"] * -1
    df_tarjetas_etiquetado["TIPO"] = "TARJETA"

    # --- UNIFICAR ---
    df_etiquetado = pd.concat([df_cuenta_etiquetado, df_tarjetas_etiquetado], ignore_index=True)
    
    # Asegurar tipo de dato fecha
    df_etiquetado['FECHA'] = pd.to_datetime(df_etiquetado['FECHA'])
    df_etiquetado.sort_values(by="FECHA", inplace=True)
    
    return df_etiquetado

def generar_id(row):
    """Genera ID robusto basado en contenido."""
    # Usamos timestamp para mayor precisión si existe, sino fecha string
    f_str = row['FECHA'].strftime('%Y-%m-%d')
    desc = str(row['DESCRIPCION']).strip()
    monto = f"{float(row['MONTO']):.2f}"
    tipo = str(row.get('TIPO', 'UNKNOWN'))
    
    return f"{f_str}|{desc}|{monto}|{tipo}"

def sincronizar_db(fecha_inicio_date, overwrite=False):
    """
    Sincroniza datos nuevos con el archivo maestro.
    fecha_inicio_date: datetime.date (obj) para filtrar.
    overwrite: Si True, elimina todo lo >= fecha_inicio y reescribe.
               Si False, solo agrega lo nuevo que no exista (id check).
    
    Retorna: (int num_agregados, str mensaje_alerta)
    """
    
    archivo_maestro = '../data/etiquetado/gastos_maestros.csv' # Path relativo asumido como en app.py

    # 1. Obtener Datos Frescos
    df_cuenta, df_tarjetas = cargar_datos_fuente()
    df_nuevos = transformar_datos(df_cuenta, df_tarjetas)
    df_nuevos['id'] = df_nuevos.apply(generar_id, axis=1)

    # 2. Leer Maestro
    if os.path.exists(archivo_maestro):
        df_maestro = pd.read_csv(archivo_maestro)
        df_maestro['FECHA'] = pd.to_datetime(df_maestro['FECHA'])
    else:
        df_maestro = pd.DataFrame()

    # Generar IDs en maestro si no existen (migración on-the-fly)
    if not df_maestro.empty and 'id' not in df_maestro.columns:
        df_maestro['id'] = df_maestro.apply(generar_id, axis=1)

    # Convertir fecha inicio a timestamp para comparaciones
    fecha_start_ts = pd.Timestamp(fecha_inicio_date)

    # 3. Lógica Diferenciada
    df_final = df_maestro.copy()
    registros_a_agregar = pd.DataFrame()

    if overwrite:
        # Borrar futuro existente
        df_final = df_final[df_final['FECHA'] < fecha_start_ts]
        # Tomar todo lo nuevo desde esa fecha
        registros_a_agregar = df_nuevos[df_nuevos['FECHA'] >= fecha_start_ts].copy()
    else:
        # Solo agregar lo que FALTA y es >= fecha_inicio
        candidatos = df_nuevos[df_nuevos['FECHA'] >= fecha_start_ts]
        
        existing_ids = set(df_final['id'])
        registros_a_agregar = candidatos[~candidatos['id'].isin(existing_ids)].copy()

    # 4. Chequeo de Alerta (Datos viejos olvidados)
    # Datos en 'nuevos' que son ANTERIORES a fecha_inicio y NO están en maestro
    datos_viejos = df_nuevos[df_nuevos['FECHA'] < fecha_start_ts]
    existing_ids_full = set(df_maestro['id']) if not df_maestro.empty else set()
    
    missed = datos_viejos[~datos_viejos['id'].isin(existing_ids_full)]
    msg_alerta = ""
    if not missed.empty:
        cnt = len(missed)
        min_date = missed['FECHA'].min().date()
        msg_alerta = f"⚠️ Atención: Hay {cnt} transacciones históricas (desde {min_date}) anteriores a la fecha de corte ({fecha_inicio_date}) que no están en el sistema y no se agregaron."

    # 5. Preparar y Guardar
    if not registros_a_agregar.empty:
        # Llenar columnas default
        for col, default in COLUMNAS_EXTRA.items():
            if col not in registros_a_agregar.columns:
                registros_a_agregar[col] = default
        
        # Aplicar reglas AUTOMATICAMENTE a lo nuevo
        registros_a_agregar = rules_module.apply_rules_to_df(registros_a_agregar)

        # Concatenar
        df_final = pd.concat([df_final, registros_a_agregar], ignore_index=True)
        
        # Sort
        df_final.sort_values(by='FECHA', inplace=True)
        
        # Guardar
        df_final.to_csv(archivo_maestro, index=False)
    
    return len(registros_a_agregar), msg_alerta

