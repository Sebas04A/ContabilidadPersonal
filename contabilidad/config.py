from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import json
import os

class Col(str, Enum):
    # Core temporal/identifying
    FECHA = 'FECHA'
    DESCRIPCION = 'DESCRIPCION'
    
    # Financial metrics
    MONTO = 'MONTO'
    SALDO = 'SALDO'
    TARJETA = 'TARJETA'
    
    # Virtual items & Debts
    PAGOS_FIJOS = 'PAGOS_FIJOS'
    INTERPOLADO = 'INTERPOLADO'
    DEUDA_ACUMULADA = 'DEUDA_ACUMULADA'
    NOTIONCUM = 'NOTIONCUM'
    
    # Processed Metrics
    TOTAL = 'TOTAL'
    SALDO_SIN_INVERSION = 'saldo_sin_inversion'
    
    # Differences
    DIFF_TOTAL = 'diff_total'
    DIFF_TARJETA = 'diff_tarjeta'
    DIFF_SALDO_SIN_INVERSION = 'diff_saldo_sin_inversion'
    DIFF_PAGOS_FIJOS = 'diff_pagos_fijos'
    DIFF_INTERPOLADOS = 'diff_interpolados'
    DIFF_NOTION = 'diff_notion'
    DIFF_DEUDA_ACUMULADA = 'diff_deuda_acumulada'

_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CONFIG_DIR)  # Go up from contabilidad/ to Cuentas/

MOCK_MODE = os.environ.get("MOCK_MODE", "false").lower() == "true"
if MOCK_MODE:
    PATH_DATA = os.path.join(_PROJECT_ROOT, "data_mock")
else:
    PATH_DATA = os.path.join(_PROJECT_ROOT, "data")

PATH_PROCESADOS = PATH_DATA+"/sistema"+"/procesada"
PATH_TARJETA_PROCESADA_DIR = PATH_PROCESADOS+"/tarjeta"
PATH_TARJETA_PROCESADA = PATH_TARJETA_PROCESADA_DIR
PATH_TARJETA_UNIDA = PATH_TARJETA_PROCESADA_DIR + "/tarjeta_unida.xlsx"
PATH_TARJETA_METADATA_UNIDA = PATH_TARJETA_PROCESADA_DIR + "/tarjeta_metadata_unida.xlsx"
PATH_BANCA_PROCESADA_DIR = PATH_PROCESADOS+"/banca"
PATH_BANCA_PROCESADA = PATH_BANCA_PROCESADA_DIR + "/banca_unida.xlsx"

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

COLUMNAS_GUARDADAS = ["FECHA", "diff_TOTAL", "diff_tarjeta", "diff_saldo_sin_inversion","diff_notion", "DESCRIPCION","DESCRIPCION_NOTION","comentario","MADRE"]
COLUMNAS_GUARDAR_COMPLETO =['FECHA',"TOTAL", 'SALDO', 'TARJETA',"INVERSION","PAGOS_MENSUAL_MA INTER","NOTIONCUM","DESCRIPCION","MADRE"]
COLUMNAS_GUARDAR_DESCRIPCIONES =["FECHA","diff_TOTAL","diff_tarjeta","diff_saldo_sin_inversion","DESCRIPCION","DESCRIPCION_NOTION","MADRE"]
COLUMNAS_GUARDAR_CUENTAS = ['FECHA', 'SALDO', 'DESCRIPCION', "MONTO"]

