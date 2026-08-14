#!/usr/bin/env python3
"""
Exportador de transacciones de ContabilidadPersonal hacia informacion.

Genera dos CSV planos sin necesidad de que el proyecto destino 'informacion'
tenga openpyxl instalado:

  contabilidad_<fecha>.csv  las transacciones de Banca y Tarjeta (hecho del
                            banco, inmutable), con la hora exacta resuelta.
  etiquetas_<fecha>.csv     el enriquecimiento manual (categoría, tags,
                            reembolsable/deudor, divisiones, agrupaciones).

Van separados a propósito: las transacciones son append-only en destino, las
etiquetas cambian cada vez que se editan aquí y se ingieren como snapshot.

Uso:
    python scripts/exportar_para_informacion.py [--output RUTA_CSV] [--output-etiquetas RUTA_CSV]
"""

import argparse
import os
import sys
from datetime import datetime, time
import pandas as pd

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from contabilidad.backend.services.transaction_service import (
    LABEL_COLUMNS,
    load_horas,
    _hora_de_fecha,
    load_labels,
)
from contabilidad.backend.storage.data_pipeline import get_pipeline


DEFAULT_OUTPUT_DIR = "/home/sebas/dev/projects/informacion/almacen/entrada"

# Columnas booleanas de etiquetas.csv: pandas las lee como True/False/NaN y el
# destino las quiere como 1/0/vacío. Vacío != False (no etiquetado != "no lo es").
COLUMNAS_BOOL = ["es_fijo", "es_reembolsable", "revisado"]


def exportar_transacciones(output_path: str = None) -> str:
    if output_path is None:
        today_str = datetime.now().strftime("%Y-%m-%d")
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(DEFAULT_OUTPUT_DIR, f"contabilidad_{today_str}.csv")

    pipeline = get_pipeline()
    horas = load_horas()
    labels = load_labels()

    # 1. Banca
    banca = pipeline.get_bank_data()
    if not banca.empty:
        b_fechas = pd.to_datetime(banca["FECHA"])
        banca["hora"] = _hora_de_fecha(b_fechas)
        banca["origen_hora"] = banca["hora"].apply(lambda h: "extracto" if h != "" else "")
        banca["tipo"] = "BANCA"
        banca["operacion"] = ""
        banca["fecha"] = b_fechas.dt.strftime("%Y-%m-%d")
        banca["descripcion"] = banca["DESCRIPCION"]
        banca["monto"] = banca["MONTO"]
        banca["saldo"] = banca["SALDO"]
    else:
        banca = pd.DataFrame(columns=["id", "fecha", "hora", "tipo", "descripcion", "monto", "saldo", "operacion", "origen_hora"])

    # 2. Tarjeta
    tarjeta = pipeline.get_credit_card_data()
    if not tarjeta.empty:
        t_fechas = pd.to_datetime(tarjeta["FECHA"])
        tarjeta_m = tarjeta.merge(horas, left_on="id", right_on="source_id", how="left")
        tarjeta["hora"] = tarjeta_m["HORA"].fillna("")
        tarjeta["origen_hora"] = tarjeta["hora"].apply(lambda h: "correo" if h != "" else "")
        tarjeta["tipo"] = "TARJETA"
        tarjeta["fecha"] = t_fechas.dt.strftime("%Y-%m-%d")
        tarjeta["descripcion"] = tarjeta["DESCRIPCION"]
        tarjeta["monto"] = tarjeta["MONTO"]
        tarjeta["saldo"] = 0.0
        tarjeta["operacion"] = tarjeta["OPERACION"] if "OPERACION" in tarjeta.columns else ""
    else:
        tarjeta = pd.DataFrame(columns=["id", "fecha", "hora", "tipo", "descripcion", "monto", "saldo", "operacion", "origen_hora"])

    # Combinar
    cols_base = ["id", "fecha", "hora", "tipo", "descripcion", "monto", "saldo", "operacion", "origen_hora"]
    merged = pd.concat([banca[cols_base], tarjeta[cols_base]], ignore_index=True)

    # Adjuntar establecimiento/nombre_limpio si existe en etiquetas
    if not labels.empty and "nombre_limpio" in labels.columns:
        labels_map = labels.drop_duplicates(subset="source_id", keep="first").set_index("source_id")["nombre_limpio"].to_dict()
        merged["establecimiento"] = merged["id"].map(labels_map).fillna("")
    else:
        merged["establecimiento"] = ""

    # Reordenar según especificación del PLAN_CONTABILIDAD.md
    columnas_finales = ["id", "fecha", "hora", "tipo", "descripcion", "monto", "saldo", "operacion", "establecimiento", "origen_hora"]
    merged = merged[columnas_finales]

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    merged.to_csv(output_path, index=False, encoding="utf-8")
    
    con_hora = (merged["hora"] != "").sum()
    print(f"Exportación exitosa -> {output_path}")
    print(f"Filas exportadas: {len(merged)} (Con hora: {con_hora}, Sin hora: {len(merged) - con_hora})")

    return output_path


def exportar_etiquetas(output_path: str = None) -> str:
    """Exporta el enriquecimiento manual (etiquetas.csv) tal cual, normalizado.

    Una transacción dividida ocupa varias filas con el mismo `source_id`, cada
    una con su `split_group_id` y su `monto_asignado`. Ese es el desglose que el
    destino necesita para poder mostrar las divisiones, así que se exportan
    todas las filas, no una por transacción.
    """
    if output_path is None:
        today_str = datetime.now().strftime("%Y-%m-%d")
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(DEFAULT_OUTPUT_DIR, f"etiquetas_{today_str}.csv")

    labels = load_labels()
    if labels.empty:
        labels = pd.DataFrame(columns=LABEL_COLUMNS)

    df = labels.reindex(columns=LABEL_COLUMNS).copy()

    # Booleanos -> 1/0, conservando el vacío de lo no etiquetado (Int64 admite
    # nulos, así que no degradan a 1.0/0.0 al escribir el CSV).
    for col in COLUMNAS_BOOL:
        df[col] = df[col].map({True: 1, False: 0, "True": 1, "False": 0, 1: 1, 0: 0}).astype("Int64")
    df["felicidad"] = pd.to_numeric(df["felicidad"], errors="coerce").astype("Int64")

    # `parte_idx` ordena las partes de una división y da una clave estable
    # incluso si algún split quedara sin `split_group_id`.
    df["parte_idx"] = df.groupby("source_id").cumcount()
    df["partes"] = df.groupby("source_id")["source_id"].transform("size")

    # Solo las columnas de texto se rellenan con vacío; las Int64 ya escriben
    # su nulo como celda vacía y fillna("") las rompería.
    texto = [c for c in df.columns if df[c].dtype == object]
    df[texto] = df[texto].fillna("")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")

    splits = int((df["partes"] > 1).sum())
    grupos = df.loc[df["group_id"] != "", "group_id"].nunique()
    reembolsables = int((df["es_reembolsable"] == 1).sum())
    print(f"Exportación de etiquetas -> {output_path}")
    print(
        f"Filas: {len(df)} sobre {df['source_id'].nunique()} transacciones "
        f"(partes de división: {splits}, grupos: {grupos}, reembolsables: {reembolsables})"
    )

    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exportar transacciones de ContabilidadPersonal para informacion.")
    parser.add_argument("--output", help="Ruta de destino del CSV de transacciones", default=None)
    parser.add_argument("--output-etiquetas", help="Ruta de destino del CSV de etiquetas", default=None)
    parser.add_argument("--solo-etiquetas", action="store_true", help="Exportar únicamente las etiquetas")
    args = parser.parse_args()

    if not args.solo_etiquetas:
        exportar_transacciones(args.output)
    exportar_etiquetas(args.output_etiquetas)
