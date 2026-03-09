from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import json
import os

# Get the directory of this config file to resolve paths correctly
_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CONFIG_DIR)  # Go up from contabilidad/ to Cuentas/

# _CONFIG_FILE = os.path.join(_PROJECT_ROOT, 'data', 'config.json')
# with open(_CONFIG_FILE, 'r') as f:
#         config = json.load(f)

#         PATH_ACTUAL = config.get("path_actual", "")


# PATH_DATOS_ANTERIORES = "../datos_anteriores.csv" #todo unido
# PATH_CUENTA_UNIDO = "../cuentas/unido.csv"
# PATH_CUENTA_GUARDAR = "../cuentas/guardado/"

# PATH_DATOS_TARJETA = '../tarjeta/datos'

# PATH_NOTION = "../notion/CuentasHasta7Agosto.csv"




PATH_DATA = os.path.join(_PROJECT_ROOT, "data")

# PATH_DATA_ACTUAL = PATH_DATA+"/completos/"+PATH_ACTUAL
# PATH_CUENTAS_ACTUAL = PATH_DATA_ACTUAL+"/banca.xlsx"


# --------- COMPLETOS
PATH_COMPLETOS = PATH_DATA+"/completos" 


PATH_COMPLETOS_VALIDACION  = PATH_COMPLETOS+"/validacion"

# NOMBRES DE CADA CARPETA DE GUARDADO
NOMBRE_COMPLETO = "completo.xlsx"
NOMBRE_BANCA = "banca.xlsx"
NOMBRE_DESCRIPCIONES = "descripciones.xlsx"


# PATH_ARCHIVO_COMPLETO = PATH_DATA_ACTUAL+"/"+NOMBRE_COMPLETO
# PATH_ARCHIVO_CUENTA = PATH_DATA_ACTUAL+"/"+NOMBRE_BANCA
# PATH_ARCHIVO_DESCRIPCIONES = PATH_DATA_ACTUAL+"/"+NOMBRE_DESCRIPCIONES

# PATH_CUENTAS_UNIDO_NOMBRE = "cuentas_unido.csv" #para que sirve esto? CAMBIADO


# PATH_DATA_ACTUAL = PATH_DATA+"/actual"


# PATH_HISTORICO = PATH_DATA+"/historico" #cambiado
# PATH_UNIDO=PATH_DATA+"/unido" #cambiado


# PATH_ATIPICOS_ACTUAL = PATH_DATA_ACTUAL+"/atipicos.xlsx"
# PATH_DECRIPCIONES_ACTUAL = PATH_DATA_ACTUAL+"/descripciones.xlsx"

# PATH_COMPLETO_ACTUAL = PATH_DATA_ACTUAL+"/completo.xlsx"



# PATH_ATIPICOS_DESCRIPCIONES = "../guardarCompleto/atipicos_descripciones.xlsx"  //cambiado

# PATH_GUARDAR_ATIPICOS_HISTORICOS = PATH_HISTORICO+"/atipicos"
# PATH_GUARDAR_COMPLETO_HISTORICOS = PATH_HISTORICO+"/completos"

# PATH_ATIPICOS = PATH_UNIDO

# PATH_BANCA_HISTORICO = PATH_HISTORICO+"/banca" #cambiado

# PATH_BANCA_NUEVOS = PATH_BANCA_HISTORICO+"/nuevos"



# PATH_BANCA_HISTORICO_COMPLETO = PATH_BANCA_HISTORICO+"/completos" #cambiado

# PATH_CUENTA_UNIDO  = PATH_UNIDO+"/cuentas.csv" #cambiado




# PATH_TARJETA_HISTORICO = PATH_HISTORICO+"/tarjeta" #cambiado
# PATH_TARJETAS_DATA_CRUDA = PATH_TARJETA_HISTORICO + "/nuevos" #cambiado
# PATH_TARJETAS_DATA = PATH_TARJETA_HISTORICO +  "/data" #cambiado


# ----- PROCESADO
PATH_PROCESADOS = PATH_DATA+"/sistema"+"/procesada"
PATH_TARJETA_PROCESADA_DIR = PATH_PROCESADOS+"/tarjeta"
PATH_TARJETA_PROCESADA = PATH_TARJETA_PROCESADA_DIR
PATH_TARJETA_UNIDA = PATH_TARJETA_PROCESADA_DIR + "/tarjeta_unida.xlsx"
PATH_TARJETA_METADATA_UNIDA = PATH_TARJETA_PROCESADA_DIR + "/tarjeta_metadata_unida.xlsx"
PATH_BANCA_PROCESADA_DIR = PATH_PROCESADOS+"/banca"
PATH_BANCA_PROCESADA = PATH_BANCA_PROCESADA_DIR + "/banca_unida.xlsx"


#----- NUEVOS
PATH_NUEVOS = PATH_DATA+"/nuevos"
PATH_BANCA_NUEVOS = PATH_NUEVOS+"/banca"
PATH_TARJETA_NUEVOS = PATH_NUEVOS+"/tarjeta"





MAPEO_COLUMNAS_DATOS_TARJETA = {
    "EMPRESA": "EMPRESA",
    "#TARJETA": "NUM_TARJETA",
    "FECHA_EMISION": "FECHA_EMISION",
    "FECHA_MAX_PAGO": "FECHA_MAX_PAGO",
}
CUENTAS_COLUMNAS = ["FECHA","SALDO","DESCRIPCION","MONTO"]



COLUMNAS_DATOS_TARJETA_ORDENADAS =[]


# PATH_TARJETA_HISTORICO_COMPLETO = PATH_TARJETA_HISTORICO+"/completos" #cambiado
# PATH_TARJETA_UNIDO = PATH_UNIDO+"/tarjeta.xlsx" #cambiado

COLUMNAS_GUARDADAS = ["FECHA", "diff_TOTAL", "diff_tarjeta", "diff_saldo_sin_inversion","diff_notion", "DESCRIPCION","DESCRIPCION_NOTION","comentario","MADRE"]
COLUMNAS_GUARDAR_COMPLETO =['FECHA',"TOTAL", 'SALDO', 'TARJETA',"INVERSION","PAGOS_MENSUAL_MA INTER","NOTIONCUM","DESCRIPCION","MADRE"]
COLUMNAS_GUARDAR_DESCRIPCIONES =["FECHA","diff_TOTAL","diff_tarjeta","diff_saldo_sin_inversion","DESCRIPCION","DESCRIPCION_NOTION","MADRE"]
COLUMNAS_GUARDAR_CUENTAS = ['FECHA', 'SALDO', 'DESCRIPCION', "MONTO"]










# COLUMNAS



