"""
Configuración general del proyecto ContabilidadPersonal
=======================================================

Centraliza todos los paths de datos y constantes de columnas usadas
a través de los módulos de contabilidad, banca y tarjeta.
"""

from pathlib import Path

# ── Directorios base ──────────────────────────────────────────────────────────

_CONFIG_DIR   = Path(__file__).parent          # contabilidad/
_PROJECT_ROOT = _CONFIG_DIR.parent             # ContabilidadPersonal/

DATA_DIR                  = _PROJECT_ROOT / "data"

# ── Datos procesados (sistema) ────────────────────────────────────────────────

_PROCESADOS               = DATA_DIR / "sistema" / "procesada"

PATH_PROCESADOS           = str(_PROCESADOS)

PATH_BANCA_PROCESADA_DIR  = str(_PROCESADOS / "banca")
PATH_BANCA_PROCESADA      = str(_PROCESADOS / "banca" / "banca_unida.xlsx")

PATH_TARJETA_PROCESADA_DIR   = str(_PROCESADOS / "tarjeta")
PATH_TARJETA_PROCESADA       = PATH_TARJETA_PROCESADA_DIR   # directorio
PATH_TARJETA_UNIDA           = str(_PROCESADOS / "tarjeta" / "tarjeta_unida.xlsx")
PATH_TARJETA_METADATA_UNIDA  = str(_PROCESADOS / "tarjeta" / "tarjeta_metadata_unida.xlsx")

# Alias para compatibilidad con codigo existente
PATH_DATA = str(DATA_DIR)

# ── Datos nuevos (sin procesar) ───────────────────────────────────────────────

_NUEVOS               = DATA_DIR / "nuevos"

PATH_NUEVOS           = str(_NUEVOS)
PATH_BANCA_NUEVOS     = str(_NUEVOS / "banca")
PATH_TARJETA_NUEVOS   = str(_NUEVOS / "tarjeta")

# ── Columnas ──────────────────────────────────────────────────────────────────

MAPEO_COLUMNAS_DATOS_TARJETA = {
    "EMPRESA":        "EMPRESA",
    "#TARJETA":       "NUM_TARJETA",
    "FECHA_EMISION":  "FECHA_EMISION",
    "FECHA_MAX_PAGO": "FECHA_MAX_PAGO",
}

CUENTAS_COLUMNAS = ["FECHA", "SALDO", "DESCRIPCION", "MONTO"]

# Nota: COLUMNAS_DATOS_TARJETA_ORDENADAS se mantiene vacío por ahora
# (pendiente definir orden canónico de columnas de tarjeta)
COLUMNAS_DATOS_TARJETA_ORDENADAS: list = []

COLUMNAS_GUARDADAS = [
    "FECHA", "diff_TOTAL", "diff_tarjeta", "diff_saldo_sin_inversion",
    "diff_notion", "DESCRIPCION", "DESCRIPCION_NOTION", "comentario", "MADRE",
]

COLUMNAS_GUARDAR_COMPLETO = [
    "FECHA", "TOTAL", "SALDO", "TARJETA", "INVERSION",
    "PAGOS_MENSUAL_MA_INTER",   # era "PAGOS_MENSUAL_MA INTER" (espacio tipográfico corregido)
    "NOTIONCUM", "DESCRIPCION", "MADRE",
]

COLUMNAS_GUARDAR_DESCRIPCIONES = [
    "FECHA", "diff_TOTAL", "diff_tarjeta", "diff_saldo_sin_inversion",
    "DESCRIPCION", "DESCRIPCION_NOTION", "MADRE",
]

COLUMNAS_GUARDAR_CUENTAS = ["FECHA", "SALDO", "DESCRIPCION", "MONTO"]
