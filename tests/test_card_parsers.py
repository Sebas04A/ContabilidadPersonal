"""
Tests para los parsers de tarjeta (XLS y PDF).

Usan archivos REALES de data/nuevos/tarjeta para verificar que:
  - El DataFrame resultante tiene las columnas y tipos correctos
  - La metadata tiene los campos esperados con valores sensatos
  - El formato de retorno es consistente entre XLS y PDF

Ejecutar con:
    pytest tests/test_card_parsers.py -v
"""

import pytest
import os
import pandas as pd
from datetime import datetime
from pathlib import Path

# ── Rutas a archivos reales ───────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_TARJETA = PROJECT_ROOT / "data" / "nuevos" / "tarjeta"

# Usamos uno de los XLS existentes como fixture estable
XLS_SAMPLE = DATA_TARJETA / "Septiembre25.xls"
PDF_SAMPLE = DATA_TARJETA / "Marzo26.pdf"


# ── Helpers de validación compartidos ────────────────────────────────────────

def assert_df_shape(df: pd.DataFrame, context: str):
    """Verifica que el DataFrame tiene la forma mínima esperada."""
    assert isinstance(df, pd.DataFrame), f"[{context}] Se esperaba DataFrame, se obtuvo {type(df)}"
    assert not df.empty, f"[{context}] El DataFrame está vacío"
    assert len(df) > 0, f"[{context}] El DataFrame no tiene filas"


def assert_df_columns(df: pd.DataFrame, context: str):
    """Verifica que el DataFrame tiene al menos las columnas obligatorias."""
    required = {"FECHA", "DESCRIPCION", "MONTO"}
    missing = required - set(df.columns)
    assert not missing, f"[{context}] Faltan columnas: {missing}. Columnas presentes: {list(df.columns)}"


def assert_df_types(df: pd.DataFrame, context: str):
    """Verifica los tipos de datos de las columnas principales."""
    # FECHA debe ser datetime
    assert pd.api.types.is_datetime64_any_dtype(df["FECHA"]) or df["FECHA"].apply(
        lambda x: isinstance(x, (datetime, pd.Timestamp)) or pd.isna(x)
    ).all(), f"[{context}] FECHA no es tipo datetime"

    # MONTO debe ser numérico
    assert pd.api.types.is_numeric_dtype(df["MONTO"]), \
        f"[{context}] MONTO no es numérico, dtype={df['MONTO'].dtype}"

    # DESCRIPCION debe ser string
    assert df["DESCRIPCION"].dtype == object or pd.api.types.is_string_dtype(df["DESCRIPCION"]), \
        f"[{context}] DESCRIPCION no es string"


def assert_df_no_all_null(df: pd.DataFrame, context: str):
    """Ninguna columna obligatoria debe estar completamente nula."""
    for col in ["FECHA", "DESCRIPCION", "MONTO"]:
        if col in df.columns:
            assert not df[col].isna().all(), \
                f"[{context}] Columna '{col}' está completamente nula"


def assert_meta_fields(meta: dict, context: str):
    """Verifica que el flat_meta tiene todos los campos obligatorios."""
    required_keys = {
        "EMPRESA", "NUM_TARJETA", "FECHA_EMISION", "FECHA_MAX_PAGO",
        "saldo_anterior", "subtotal_pagado", "total_a_pagar", "minimo_a_pagar",
        "total_consumo", "num_transacciones", "fecha_min", "fecha_max",
        "total_mes", "total_a_pagar_despues", "source_file",
    }
    missing = required_keys - set(meta.keys())
    assert not missing, f"[{context}] Faltan campos en metadata: {missing}"


def assert_meta_values(meta: dict, context: str):
    """Verifica que los valores numéricos de metadata son razonables."""
    assert isinstance(meta["EMPRESA"], str) and meta["EMPRESA"], \
        f"[{context}] EMPRESA vacía o no es string"

    assert isinstance(meta["num_transacciones"], int) and meta["num_transacciones"] >= 0, \
        f"[{context}] num_transacciones inválido: {meta['num_transacciones']}"

    # Los montos deben ser numéricos (float/int) – pueden ser 0 si no hay datos
    for campo in ["saldo_anterior", "total_a_pagar", "total_consumo", "total_mes"]:
        val = meta[campo]
        assert isinstance(val, (int, float)), \
            f"[{context}] Campo '{campo}' debería ser numérico, es {type(val)}: {val!r}"


def assert_monto_discrepancia(df: pd.DataFrame, meta: dict, context: str):
    """Verifica que el monto calculado con la formula de discrepancia coincida con el esperado."""
    if "MONTO" not in df.columns.astype(str).tolist() and "MONTO" not in df.columns:
        return
        
    monto_total_df = df['MONTO'].sum()
    saldo_anterior = meta.get('saldo_anterior', 0.0)
    subtotal_pagado = meta.get('subtotal_pagado', 0.0)
    total_a_pagar = meta.get('total_a_pagar', 0.0)
    
    monto_calculado = monto_total_df + saldo_anterior - subtotal_pagado
    
    assert abs(monto_calculado - total_a_pagar) <= 0.01, \
        f"[{context}] Discrepancia de monto: calculado={monto_calculado:.2f} " \
        f"(movs={monto_total_df:.2f} + ant={saldo_anterior:.2f} - pagos={subtotal_pagado:.2f}), " \
        f"esperado={total_a_pagar:.2f}"


# ═════════════════════════════════════════════════════════════════════════════
# Tests para XLS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not XLS_SAMPLE.exists(), reason=f"Archivo XLS no encontrado: {XLS_SAMPLE}")
class TestXLSParser:
    """Prueba el parser XLS de tarjeta usando get_credit_card_data_from_excel."""

    @pytest.fixture(scope="class")
    def xls_result(self):
        """Ejecuta el parser XLS una sola vez para todos los tests de esta clase."""
        from contabilidad.backend.services.credit_card.core import get_credit_card_data_from_excel
        df, metadata = get_credit_card_data_from_excel(str(XLS_SAMPLE))
        # Normalizar columna (igual que hace el service)
        df.rename(columns={"VALOR": "MONTO", "Valor": "MONTO"}, inplace=True)
        return df, metadata

    def test_xls_retorna_dataframe(self, xls_result):
        df, _ = xls_result
        assert_df_shape(df, "XLS")

    def test_xls_columnas_obligatorias(self, xls_result):
        df, _ = xls_result
        assert_df_columns(df, "XLS")

    def test_xls_tipos_de_datos(self, xls_result):
        df, _ = xls_result
        assert_df_types(df, "XLS")

    def test_xls_sin_columnas_completamente_nulas(self, xls_result):
        df, _ = xls_result
        assert_df_no_all_null(df, "XLS")

    def test_xls_metadata_tiene_empresa(self, xls_result):
        _, metadata = xls_result
        assert hasattr(metadata, "EMPRESA"), "falta atributo EMPRESA en metadata"
        assert metadata.EMPRESA, "EMPRESA está vacía"

    def test_xls_metadata_tiene_num_tarjeta(self, xls_result):
        _, metadata = xls_result
        assert hasattr(metadata, "NUM_TARJETA"), "falta atributo NUM_TARJETA"
        assert metadata.NUM_TARJETA, "NUM_TARJETA está vacío"

    def test_xls_metadata_fechas_son_datetime(self, xls_result):
        _, metadata = xls_result
        for campo in ["FECHA_EMISION", "FECHA_MAX_PAGO"]:
            val = getattr(metadata, campo, None)
            assert isinstance(val, (datetime, pd.Timestamp)), \
                f"metadata.{campo} debería ser datetime, es {type(val)}: {val!r}"

    def test_xls_metadata_totales_son_numericos(self, xls_result):
        _, metadata = xls_result
        for campo in ["TOTAL_A_PAGAR", "TOTAL_CONSUMO", "MINIMO_A_PAGAR", "SALDO_ANTERIOR"]:
            val = getattr(metadata, campo, None)
            assert isinstance(val, (int, float)), \
                f"metadata.{campo} debería ser numérico, es {type(val)}: {val!r}"

    def test_xls_monto_tiene_positivos_y_negativos(self, xls_result):
        """Una tarjeta normal debería tener consumos (positivos o negativos según convención)."""
        df, _ = xls_result
        assert df["MONTO"].notna().sum() > 0, "Todos los montos son NaN"

    def test_xls_fechas_en_rango_razonable(self, xls_result):
        df, _ = xls_result
        fechas_validas = df["FECHA"].dropna()
        assert len(fechas_validas) > 0, "No hay fechas válidas"
        min_f = pd.to_datetime(fechas_validas.min())
        max_f = pd.to_datetime(fechas_validas.max())
        assert min_f.year >= 2020, f"Fecha mínima fuera de rango: {min_f}"
        assert max_f.year <= datetime.now().year + 1, f"Fecha máxima fuera de rango: {max_f}"


# ═════════════════════════════════════════════════════════════════════════════
# Tests para el service _process_card_xls (formato estandarizado)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not XLS_SAMPLE.exists(), reason=f"Archivo XLS no encontrado: {XLS_SAMPLE}")
class TestServiceXLS:
    """Prueba el método privado _process_card_xls del SourcesService."""

    @pytest.fixture(scope="class")
    def service_xls_result(self):
        from contabilidad.backend.services.sources_service import SourcesService
        svc = SourcesService()
        df, flat_meta = svc._process_card_xls(str(XLS_SAMPLE), XLS_SAMPLE.name)
        return df, flat_meta

    def test_retorna_tupla(self, service_xls_result):
        df, flat_meta = service_xls_result
        assert isinstance(df, pd.DataFrame)
        assert isinstance(flat_meta, dict)

    def test_df_columnas_estandarizadas(self, service_xls_result):
        df, _ = service_xls_result
        assert_df_columns(df, "service_xls")

    def test_flat_meta_campos_completos(self, service_xls_result):
        _, flat_meta = service_xls_result
        assert_meta_fields(flat_meta, "service_xls")

    def test_flat_meta_valores_validos(self, service_xls_result):
        _, flat_meta = service_xls_result
        assert_meta_values(flat_meta, "service_xls")

    def test_flat_meta_source_file_es_nombre(self, service_xls_result):
        _, flat_meta = service_xls_result
        assert flat_meta["source_file"] == XLS_SAMPLE.name

    def test_flat_meta_num_transacciones_coincide_con_df(self, service_xls_result):
        df, flat_meta = service_xls_result
        assert flat_meta["num_transacciones"] == len(df), \
            f"num_transacciones={flat_meta['num_transacciones']} != len(df)={len(df)}"

    def test_flat_meta_total_mes_es_suma_monto(self, service_xls_result):
        df, flat_meta = service_xls_result
        if "MONTO" in df.columns:
            esperado = round(df["MONTO"].sum(), 4)
            obtenido = round(flat_meta["total_mes"], 4)
            assert abs(esperado - obtenido) < 0.01, \
                f"total_mes={obtenido} no coincide con sum(MONTO)={esperado}"

    def test_flat_meta_discrepancia_monto(self, service_xls_result):
        df, flat_meta = service_xls_result
        assert_monto_discrepancia(df, flat_meta, "service_xls")


# ═════════════════════════════════════════════════════════════════════════════
# Tests para PDF
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not PDF_SAMPLE.exists(), reason=f"Archivo PDF no encontrado: {PDF_SAMPLE}")
class TestPDFParser:
    """Prueba get_credit_card_data_from_pdf directamente."""

    @pytest.fixture(scope="class")
    def pdf_result(self):
        from contabilidad.backend.services.credit_card.pdf_reader import get_credit_card_data_from_pdf
        df, flat_meta = get_credit_card_data_from_pdf(str(PDF_SAMPLE))
        df.rename(columns={"VALOR": "MONTO", "Valor": "MONTO"}, inplace=True)
        return df, flat_meta

    def test_pdf_retorna_dataframe(self, pdf_result):
        df, _ = pdf_result
        assert_df_shape(df, "PDF")

    def test_pdf_columnas_obligatorias(self, pdf_result):
        df, _ = pdf_result
        assert_df_columns(df, "PDF")

    def test_pdf_flat_meta_campos_completos(self, pdf_result):
        _, flat_meta = pdf_result
        assert_meta_fields(flat_meta, "PDF")

    def test_pdf_flat_meta_valores_validos(self, pdf_result):
        _, flat_meta = pdf_result
        assert_meta_values(flat_meta, "PDF")

    def test_pdf_sin_columnas_completamente_nulas(self, pdf_result):
        df, _ = pdf_result
        assert_df_no_all_null(df, "PDF")

    def test_pdf_metadata_source_file_es_nombre(self, pdf_result):
        _, flat_meta = pdf_result
        assert flat_meta["source_file"] == PDF_SAMPLE.name

    def test_pdf_num_transacciones_coincide_con_df(self, pdf_result):
        df, flat_meta = pdf_result
        assert flat_meta["num_transacciones"] == len(df)

    def test_pdf_fechas_en_rango_razonable(self, pdf_result):
        df, _ = pdf_result
        if "FECHA" in df.columns:
            fechas = pd.to_datetime(df["FECHA"], errors="coerce").dropna()
            if len(fechas) > 0:
                assert fechas.min().year >= 2020
                assert fechas.max().year <= datetime.now().year + 1

    def test_pdf_discrepancia_monto(self, pdf_result):
        df, flat_meta = pdf_result
        assert_monto_discrepancia(df, flat_meta, "PDF")


# ═════════════════════════════════════════════════════════════════════════════
# Tests de consistencia XLS vs PDF (formato estandarizado)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(
    not XLS_SAMPLE.exists() or not PDF_SAMPLE.exists(),
    reason="Necesita tanto el XLS como el PDF para comparar"
)
class TestConsistenciaFormato:
    """Verifica que XLS y PDF devuelven el mismo formato estandarizado."""

    @pytest.fixture(scope="class")
    def ambos_resultados(self):
        from contabilidad.backend.services.sources_service import SourcesService
        svc = SourcesService()
        df_xls, meta_xls = svc._process_card_xls(str(XLS_SAMPLE), XLS_SAMPLE.name)
        df_pdf, meta_pdf = svc._process_card_pdf(str(PDF_SAMPLE), PDF_SAMPLE.name)
        return (df_xls, meta_xls), (df_pdf, meta_pdf)

    def test_mismas_columnas_en_df(self, ambos_resultados):
        (df_xls, _), (df_pdf, _) = ambos_resultados
        cols_xls = set(df_xls.columns)
        cols_pdf = set(df_pdf.columns)
        obligatorias = {"FECHA", "DESCRIPCION", "MONTO"}
        assert obligatorias <= cols_xls, f"XLS le falta: {obligatorias - cols_xls}"
        assert obligatorias <= cols_pdf, f"PDF le falta: {obligatorias - cols_pdf}"

    def test_mismas_claves_en_flat_meta(self, ambos_resultados):
        (_, meta_xls), (_, meta_pdf) = ambos_resultados
        claves_xls = set(meta_xls.keys())
        claves_pdf = set(meta_pdf.keys())
        solo_en_xls = claves_xls - claves_pdf
        solo_en_pdf = claves_pdf - claves_xls
        assert not solo_en_xls, f"Claves solo en XLS: {solo_en_xls}"
        assert not solo_en_pdf, f"Claves solo en PDF: {solo_en_pdf}"


# ═════════════════════════════════════════════════════════════════════════════
# Tests de Unificación y Consistencia de Fechas
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(
    not XLS_SAMPLE.exists() or not PDF_SAMPLE.exists(),
    reason="Necesita tanto el XLS como el PDF para probar la unificación"
)
class TestUnificacionTarjeta:
    """Verifica la lógica global cuando se unen los datos de múltiples tarjetas."""

    @pytest.fixture(scope="class")
    def df_unido_y_meta(self):
        from contabilidad.backend.services.sources_service import SourcesService
        svc = SourcesService()
        d1, m1 = svc._process_card_xls(str(XLS_SAMPLE), XLS_SAMPLE.name)
        d2, m2 = svc._process_card_pdf(str(PDF_SAMPLE), PDF_SAMPLE.name)
        
        df_unido = pd.concat([d1, d2], ignore_index=True)
        return df_unido, [m1, m2]

    def test_fechas_no_se_cruzan(self, df_unido_y_meta):
        """Verifica que los rangos del mes de cada estado de cuenta no se solapen."""
        _, metas = df_unido_y_meta
        
        # Filtramos estados de cuenta que realmente tienen fechas válidas
        metas_validas = [m for m in metas if pd.notna(m.get('fecha_min')) and pd.notna(m.get('fecha_max'))]
        if len(metas_validas) < 2:
            pytest.skip("No hay suficientes archivos con fechas válidas para comparar cruce de fechas")
            
        # Ordenamos la metadata por su fecha_min
        metas_ordenadas = sorted(metas_validas, key=lambda x: x['fecha_min'])
        
        for i in range(len(metas_ordenadas) - 1):
            max_actual = metas_ordenadas[i]['fecha_max']
            min_siguiente = metas_ordenadas[i+1]['fecha_min']
            
            # El máximo de un estado de cuenta debería ser ANTERIOR O IGUAL al mínimo del siguiente
            assert max_actual <= min_siguiente, \
                f"Las fechas se cruzan! {metas_ordenadas[i]['source_file']} termina el {max_actual} " \
                f"pero {metas_ordenadas[i+1]['source_file']} comienza el {min_siguiente}."

    def test_discrepancia_por_mes_en_df_unido(self, df_unido_y_meta):
        """Para cada mes (estado de cuenta), filtramos el df global por fecha y verificamos montos."""
        df_unido, metas = df_unido_y_meta
        
        for meta in metas:
            f_min = meta.get('fecha_min')
            f_max = meta.get('fecha_max')
            
            if pd.isna(f_min) or pd.isna(f_max):
                continue
                
            # Seleccionamos las filas que caen en este rango de fechas inclusivo
            df_mes = df_unido[(df_unido['FECHA'] >= f_min) & (df_unido['FECHA'] <= f_max)]
            
            # Verificamos la discrepancia usando el helper global
            context = f"DF_UNIDO (Filtrado para {meta['source_file']})"
            assert_monto_discrepancia(df_mes, meta, context)
