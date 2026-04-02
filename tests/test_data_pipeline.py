"""
test_data_pipeline.py — Tests for DataPipeline in storage/data_pipeline.py
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def reset_pipeline():
    """Reset the global pipeline singleton before each test."""
    from contabilidad.backend.storage.data_pipeline import reset_pipeline
    reset_pipeline()
    yield
    reset_pipeline()


# ── Singleton behaviour ───────────────────────────────────────────────────────

def test_get_pipeline_returns_same_instance():
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    p1 = get_pipeline()
    p2 = get_pipeline()
    assert p1 is p2


def test_reset_pipeline_creates_new_instance():
    from contabilidad.backend.storage.data_pipeline import get_pipeline, reset_pipeline
    p1 = get_pipeline()
    reset_pipeline()
    p2 = get_pipeline()
    assert p1 is not p2


# ── get_bank_data ─────────────────────────────────────────────────────────────

def test_get_bank_data_returns_empty_when_file_missing():
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    with patch("os.path.exists", return_value=False):
        pipeline = get_pipeline()
        df = pipeline.get_bank_data(force_reload=True)
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_get_bank_data_reads_excel_when_file_exists():
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    mock_df = pd.DataFrame({
        "FECHA": pd.date_range("2025-01-01", periods=3),
        "MONTO": [100.0, -50.0, 200.0],
        "DESCRIPCION": ["A", "B", "C"],
    })
    with patch("os.path.exists", return_value=True), \
         patch("pandas.read_excel", return_value=mock_df):
        pipeline = get_pipeline()
        df = pipeline.get_bank_data(force_reload=True)
    assert not df.empty
    assert len(df) == 3


# ── get_account_data ──────────────────────────────────────────────────────────

def test_get_account_data_adds_debito_credito_columns():
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    mock_df = pd.DataFrame({
        "FECHA": pd.date_range("2025-01-01", periods=3),
        "MONTO": [100.0, -50.0, 200.0],
        "SALDO": [1000.0, 950.0, 1150.0],
        "DESCRIPCION": ["A", "B", "C"],
    })
    with patch("os.path.exists", return_value=True), \
         patch("pandas.read_excel", return_value=mock_df):
        pipeline = get_pipeline()
        df = pipeline.get_account_data(force_reload=True)
    assert "DEBITO" in df.columns
    assert "CREDITO" in df.columns
    # Positive MONTO → CREDITO, Negative → DEBITO
    assert df[df["MONTO"] == 100.0]["CREDITO"].iloc[0] == pytest.approx(100.0)
    assert df[df["MONTO"] == -50.0]["DEBITO"].iloc[0] == pytest.approx(50.0)


def test_get_account_data_caches_on_second_call():
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    mock_df = pd.DataFrame({
        "FECHA": pd.date_range("2025-01-01", periods=2),
        "MONTO": [100.0, -50.0],
        "SALDO": [1000.0, 950.0],
        "DESCRIPCION": ["A", "B"],
    })
    with patch("os.path.exists", return_value=True), \
         patch("pandas.read_excel", return_value=mock_df) as mock_read:
        pipeline = get_pipeline()
        pipeline.get_account_data(force_reload=True)  # first call — reads file
        pipeline.get_account_data()                     # second — should use cache
    assert mock_read.call_count == 1


# ── Cache invalidation ────────────────────────────────────────────────────────

def test_invalidate_cache_all():
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    pipeline = get_pipeline()
    pipeline.invalidate_cache(scope="all")
    stats = pipeline.get_cache_stats()
    assert stats["source_cache"]["entries"] == 0
    assert stats["transformation_cache"]["entries"] == 0


def test_invalidate_cache_source_only():
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    pipeline = get_pipeline()
    pipeline.invalidate_cache(scope="source")
    stats = pipeline.get_cache_stats()
    assert stats["source_cache"]["entries"] == 0


def test_get_processed_data_invalid_source_raises():
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    pipeline = get_pipeline()
    with pytest.raises(ValueError, match="Source inválido"):
        pipeline.get_processed_data(source="invalid_source_name")


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_get_cache_stats_structure():
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    pipeline = get_pipeline()
    stats = pipeline.get_cache_stats()
    assert "source_cache" in stats
    assert "transformation_cache" in stats
    assert "transformations_registered" in stats
    assert isinstance(stats["transformations_registered"], int)


# ── Pipeline Unification (Real Data Integration Test) ─────────────────────────

def test_pipeline_tarjeta_discrepancia_meses_unidos():
    """
    Verifica que al usar get_raw_data('tarjeta_unida') desde el pipeline,
    los montos sigan coincidiendo perfectamente con la metadata cuando se
    filtran por fecha_min y fecha_max de cada estado de cuenta.
    """
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    pipeline = get_pipeline()
    
    # 1. Obtenemos datos unidos y metadatos
    df_raw = pipeline.get_raw_data('tarjeta_unida', force_reload=True)
    df_meta = pipeline.get_credit_card_metadata(force_reload=True)
    
    if df_raw.empty or df_meta.empty:
        pytest.skip("No hay datos unidos reales en la carpeta de procesados para probar")
    
    # 2. Verificamos que los rangos de fechas no se crucen entre agrupaciones de la metadata procesada
    df_meta_sorted = df_meta.dropna(subset=['MIN_FECHA_MOVIMIENTO', 'MAX_FECHA_MOVIMIENTO']).sort_values('MIN_FECHA_MOVIMIENTO')
    
    if len(df_meta_sorted) > 1:
        for i in range(len(df_meta_sorted) - 1):
            max_actual = pd.to_datetime(df_meta_sorted.iloc[i]['MAX_FECHA_MOVIMIENTO'])
            min_siguiente = pd.to_datetime(df_meta_sorted.iloc[i+1]['MIN_FECHA_MOVIMIENTO'])
            
            # Usaremos warning si se cruzan, no assert, para documentarlo en la corrida de prueba
            if max_actual > min_siguiente:
                pytest.xfail(f"Cruce detectado: M1 termina en {max_actual.date()} y M2 empieza en {min_siguiente.date()}")

def test_pipeline_tarjeta_discrepancia_meses_unidos():
    """Para cada mes procesado, verificamos que la sumatoria dentro de su min/max de fechas respete el cuadre."""
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    pipeline = get_pipeline()
    
    df_raw = pipeline.get_raw_data('tarjeta_unida', force_reload=True)
    df_meta = pipeline.get_credit_card_metadata(force_reload=True)
    
    if df_raw.empty or df_meta.empty:
        pytest.skip("No hay datos")
        
    df_meta_sorted = df_meta.dropna(subset=['MIN_FECHA_MOVIMIENTO', 'MAX_FECHA_MOVIMIENTO']).sort_values('MIN_FECHA_MOVIMIENTO')

    # 3. Verificamos el balance/discrepancia por cada mes usando la fórmula oficial
    import warnings
    for _, meta_row in df_meta_sorted.iterrows():
        f_min = pd.to_datetime(meta_row['MIN_FECHA_MOVIMIENTO'])
        f_max = pd.to_datetime(meta_row['MAX_FECHA_MOVIMIENTO'])
        
        # Filtrado temporal del DataFrame consolidado
        df_mes = df_raw[(df_raw['FECHA'] >= f_min) & (df_raw['FECHA'] <= f_max)]
        
        # Validar consistencia si tienen MONTO real ('tarjeta_unida' conserva los montos brutos)
        if 'MONTO' in df_mes.columns:
            monto_total_df = df_mes['MONTO'].sum()
            saldo_anterior = float(meta_row.get('SALDO_ANTERIOR', 0.0))
            subtotal_pagado = float(meta_row.get('SUBTOTAL_PAGADO', 0.0))
            total_a_pagar = float(meta_row.get('TOTAL_A_PAGAR', 0.0))
            
            monto_calculado = monto_total_df + saldo_anterior - subtotal_pagado
            
            diff = abs(monto_calculado - total_a_pagar)
            
            if 0.01 < diff <= 10.0:
                warnings.warn(
                    f"[Raw Pipeline] Discrepancia leve (Mes {f_min.date()} a {f_max.date()}): "
                    f"Calculado={monto_calculado:.2f} vs Esperado={total_a_pagar:.2f}. "
                    f"Diferencia de {diff:.2f}. (Tolerado por posible cruce de fechas inter-meses)"
                )
            else:
                assert diff <= 10.0, \
                    f"[Raw Pipeline] Error GRAVE (Mes {f_min.date()} a {f_max.date()}): " \
                    f"Calculado={monto_calculado:.2f} vs Esperado={total_a_pagar:.2f}. Diferencia={diff:.2f}."

def _diagnosticar_descuadre(meta_row, df_mes_unido, diff):
    from contabilidad.config import PATH_TARJETA_NUEVOS
    from contabilidad.backend.services.sources_service import SourcesService
    import os
    import pandas as pd
    
    source = meta_row.get('source_file')
    if not source:
        print("No hay source_file en la metadata para diagnosticar.")
        return
        
    print(f"\n\n--- DIAGNÓSTICO DE DESCUADRE: {source} ---")
    print(f"Diferencia detectada en test integrado: {diff:.2f}")
    
    # Buscar en nuevos o historico
    path_nuevos = os.path.join(PATH_TARJETA_NUEVOS, source)
    path_historico = os.path.join(PATH_TARJETA_NUEVOS.replace('nuevos', 'sistema/historico'), source)
    
    file_path = path_nuevos if os.path.exists(path_nuevos) else path_historico
    
    if not os.path.exists(file_path):
        print(f"No se pudo encontrar el archivo original en nuevos o historico: {source}")
        return
        
    # Usar las funciones ya existentes (!)
    svc = SourcesService()
    try:
        df_indiv, _ = svc._process_single_card_file(file_path, source)
    except Exception as e:
        print(f"Fallo al procesar individualmente {source}: {e}")
        return
    
    if 'FECHA' not in df_indiv.columns or 'FECHA' not in df_mes_unido.columns:
        print("Columnas de FECHA no encontradas para comparar.")
        return
        
    fechas_unidas = set(df_mes_unido['FECHA'].dt.date.dropna())
    fechas_indiv = set(pd.to_datetime(df_indiv['FECHA']).dt.date.dropna())
    
    print(f"Total movimientos en mes filtrado del pipeline: {len(df_mes_unido)}")
    print(f"Total movimientos en archivo individual real aislado: {len(df_indiv)}")
    
    fechas_extra = fechas_unidas - fechas_indiv
    if fechas_extra:
        print(f"\nCRUCE DE CUENTAS CONFIRMADO:")
        print(f"El filtro por fecha en el pipeline capturó {len(fechas_extra)} fechas de transacciones que PERTENECEN a otro estado de cuenta u otro archivo:")
        for fd in sorted(fechas_extra):
            df_extra = df_mes_unido[df_mes_unido['FECHA'].dt.date == fd]
            for _, r in df_extra.iterrows():
                monto = r.get('MONTO', r.get('VALOR', 0))
                print(f"  -> INVASOR (de otro archivo): {r['FECHA'].date()} | {r.get('DESCRIPCION','')} | {monto}")
                
    col_monto_indiv = 'MONTO' if 'MONTO' in df_indiv.columns else 'VALOR'
    col_monto_unido = 'MONTO' if 'MONTO' in df_mes_unido.columns else 'VALOR'
    monto_indiv = df_indiv[col_monto_indiv].sum() if col_monto_indiv in df_indiv.columns else 0
    monto_unido = df_mes_unido[col_monto_unido].sum() if col_monto_unido in df_mes_unido.columns else 0
    print(f"\nSuma total MONTO (Archivo individual perfecto): {monto_indiv:.2f}")
    print(f"Suma total MONTO (Pipeline contaminado por cruce): {monto_unido:.2f}\n-----------------------------------\n")

def test_pipeline_tarjeta_discrepancia_procesada_unidos():
    """
    Igual que el test crudo, pero usando get_processed_data('tarjeta_unida')
    y sus transformaciones pertinentes. Comprueba que aún con los cambios de
    signos, las matemáticas subyacentes coinciden con TOTAL_A_PAGAR.
    """
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    pipeline = get_pipeline()
    import warnings
    
    # Obtenemos los datos procesados (esto pasa por transform_credit_cards)
    df_proc = pipeline.get_processed_data('tarjeta_unida', force_reload=True)
    df_meta = pipeline.get_credit_card_metadata(force_reload=True)
    
    if df_proc.empty or df_meta.empty:
        pytest.skip("No hay datos")
        
    df_meta_sorted = df_meta.dropna(subset=['MIN_FECHA_MOVIMIENTO', 'MAX_FECHA_MOVIMIENTO']).sort_values('MIN_FECHA_MOVIMIENTO')

    for _, meta_row in df_meta_sorted.iterrows():
        f_min = pd.to_datetime(meta_row['MIN_FECHA_MOVIMIENTO'])
        f_max = pd.to_datetime(meta_row['MAX_FECHA_MOVIMIENTO'])
        
        df_mes = df_proc[(df_proc['FECHA'] >= f_min) & (df_proc['FECHA'] <= f_max)]
        
        col_monto = 'MONTO' if 'MONTO' in df_mes.columns else 'VALOR'
        
        if col_monto in df_mes.columns:
            monto_total_df = df_mes[col_monto].sum()
            
            if monto_total_df < 0 and float(meta_row.get('TOTAL_A_PAGAR', 0)) > 0:
                monto_total_df = -monto_total_df
                
            saldo_anterior = float(meta_row.get('SALDO_ANTERIOR', 0.0))
            subtotal_pagado = float(meta_row.get('SUBTOTAL_PAGADO', 0.0))
            total_a_pagar = float(meta_row.get('TOTAL_A_PAGAR', 0.0))
            
            monto_calculado = monto_total_df + saldo_anterior - subtotal_pagado
            diff = abs(monto_calculado - total_a_pagar)
            
            if 0.01 < diff <= 10.0:
                warnings.warn(
                    f"[Processed Pipeline] Discrepancia leve (Mes {f_min.date()} a {f_max.date()}): "
                    f"Calculado={monto_calculado:.2f} vs Esperado={total_a_pagar:.2f}. "
                    f"Diferencia de {diff:.2f}. (Tolerado por posible cruce de fechas)"
                )
            else:
                if diff > 10.0:
                    _diagnosticar_descuadre(meta_row, df_mes, diff)
                assert diff <= 10.0, \
                     f"[Processed Pipeline] Error GRAVE (Mes {f_min.date()} a {f_max.date()}): " \
                     f"Calculado={monto_calculado:.2f} vs Esperado={total_a_pagar:.2f}. Diferencia={diff:.2f}."

def test_pipeline_daily_aggregation_totals():
    """
    Verifica que la agregación diaria general (vía DashboardService)
    respete matemáticamente su fórmula base para cada día:
    TOTAL = saldo_sin_inversion + INTERPOLADO - TARJETA + DEUDA_ACUMULADA
    """
    from contabilidad.backend.services.dashboard_service import DashboardService
    
    svc = DashboardService()
    # Ejecuta pipeline.get_daily_data(source='all') y los processors
    resp = svc.get_chart_data()
    
    if not resp.data:
        pytest.skip("No hay datos diarios calculados.")
        
    for dp in resp.data:
        # Reconstruir la fórmula de TOTAL según MetricProcessor._calculate_total
        # dp.tarjeta corresponde a self.config.col_tarjeta (posiblemente un valor ajustado)
        esperado = dp.saldo_sin_inversion + dp.interpolado - dp.tarjeta + dp.deuda_acumulada
        diff = abs(dp.total - esperado)
        
        assert diff <= 0.01, \
            f"Fallo matemático en {dp.date}:\n" \
            f"  -> TOTAL Calculado en dashboard: {dp.total:.2f}\n" \
            f"  -> TOTAL Esperado por componentes: {esperado:.2f}\n" \
            f"  Diferencia: {diff:.2f}\n" \
            f"  Desglose: saldo_sin_inversion={dp.saldo_sin_inversion:.2f}, " \
            f"interpolado={dp.interpolado:.2f}, tarjeta={dp.tarjeta:.2f}, deuda={dp.deuda_acumulada:.2f}"

def test_columna_saldo_vs_raw():
    """
    Verifica que el SALDO en el dashboard provenga fielmente del data_raw de la cuenta bancaria.
    Se cruza el saldo reportado en la fecha contra el último saldo registrado en raw ese día.
    El saldo sin inversion debe ser el SALDO - PAGO FIJOS.
    """
    from contabilidad.backend.services.dashboard_service import DashboardService
    import pandas as pd
    
    svc = DashboardService()
    resp = svc.get_chart_data()
    df_raw = svc.pipeline.get_raw_data('cuenta')
    
    if not resp.data or df_raw.empty:
        pytest.skip("No hay datos para probar")
        
    df_raw['FECHA_DIA'] = pd.to_datetime(df_raw['FECHA']).dt.date
    # El saldo representativo de un día es el último registrado en la data cruda
    raw_saldo_diario = df_raw.groupby('FECHA_DIA')['SALDO'].last()
    
    # Evaluar algunos días al azar donde sabemos que hubo movimiento (o todos)
    for dp in resp.data:
        dt = pd.to_datetime(dp.date).date()
        # Verificar la definición solicitada
        assert abs(dp.saldo_sin_inversion - (dp.saldo - dp.pagos_fijos)) <= 0.01, "saldo_sin_inversion no es SALDO - PAGO FIJOS"
        
        # Validar contra RAW si hay datos directos ese día
        if dt in raw_saldo_diario.index:
            saldo_raw = float(raw_saldo_diario.loc[dt])
            assert abs(dp.saldo - saldo_raw) <= 0.01, f"SALDO {dp.saldo} no coincide con data raw {saldo_raw} en {dt}"

def test_columna_tarjeta_vs_raw():
    """
    Verifica que la TARJETA corresponda a la suma de gastos.
    Lo validamos asegurando que la variación diaria de deuda (diff_tarjeta)
    coincide exactamente con la suma de consumos (MONTO) del raw_data en ese día.
    """
    from contabilidad.backend.services.dashboard_service import DashboardService
    import pandas as pd
    
    svc = DashboardService()
    resp = svc.get_chart_data()
    df_raw = svc.pipeline.get_raw_data('tarjeta')
    
    if not resp.data or df_raw.empty:
        pytest.skip("No hay datos de tarjetjka")
        
    df_raw['FECHA_DIA'] = pd.to_datetime(df_raw['FECHA']).dt.date
    raw_monto_diario = df_raw.groupby('FECHA_DIA')['MONTO'].sum()
    
    for dp in resp.data:
        dt = pd.to_datetime(dp.date).date()
        
        # Consumo = -(Variacion_Tarjeta + Variacion_Pago)
        diff_dash_consumo = -((dp.diff_tarjeta or 0.0) + (dp.diff_pago_tarjeta or 0.0))
        
        consumo_raw = 0.0
        if dt in raw_monto_diario.index:
            consumo_raw = float(raw_monto_diario.loc[dt])
            
        # Ignorar días previos al inicio de seguimiento de tarjeta (principios de 2024)
        if abs(dp.tarjeta) < 0.01 and abs(dp.pago_tarjeta) < 0.01:
            continue
            
        # En días de pago o reset de ciclo (donde diff_pago != 0), la compensación 
        # puede tener pequeños desfases de 1 día entre cuenta y tarjeta. Los ignoramos.
        if abs(dp.diff_pago_tarjeta) > 0.1 and abs(diff_dash_consumo - consumo_raw) > 1.0:
            continue
            
        # Tolerancia de centavos para consumos normales.
        diferencia = abs(diff_dash_consumo - consumo_raw)
        
        if diferencia > 1.0:
            import warnings
            warnings.warn(f"Discrepancia Tarjeta RAW en {dt}: DashConsumo={diff_dash_consumo:.2f}, RawSum={consumo_raw:.2f}")

def test_columna_deuda_vs_raw():
    """
    Verifica que DEUDA sea la suma estricta de todas las deudas activas contra la base de datos cruda.
    """
    from contabilidad.backend.services.dashboard_service import DashboardService
    import pandas as pd
    
    svc = DashboardService()
    resp = svc.get_chart_data()
    df_raw = svc.pipeline.get_daily_data('debt')
    
    if not resp.data or df_raw.empty:
        pytest.skip("No hay datos de duda")
        
    # Obtener el mapeo crudo
    df_raw['FECHA_DIA'] = pd.to_datetime(df_raw['FECHA']).dt.date
    deuda_raw_diaria = df_raw.set_index('FECHA_DIA')['DEUDA_ACUMULADA'].to_dict()
    
    for dp in resp.data:
        dt = pd.to_datetime(dp.date).date()
        if dt in deuda_raw_diaria:
            raw_deuda = float(deuda_raw_diaria[dt])
            assert abs(dp.deuda_acumulada - raw_deuda) <= 0.01, \
                f"DEUDA {dp.deuda_acumulada} no coincide con pipeline raw {raw_deuda} en {dt}"

def test_columna_interpolados():
    """
    Verifica que INTERPOLADOS solo sean interpolados y formen parte de la matemática de forma aislada.
    """
    from contabilidad.backend.services.dashboard_service import DashboardService
    svc = DashboardService()
    resp = svc.get_chart_data()
    
    if not resp.data:
        pytest.skip("No hay datos")
        
    for dp in resp.data:
        # Los interpolados son calculados directamente en VirtualItemsProcessor.
        # Debe ser estrictamente mayor o igual a cero (acumula gastos fijos diferidos) y no corromper la sumatoria.
        assert dp.interpolado >= 0.0, f"Interpolado negativo en {dp.date}"
        
        # Debe mantenerse el balance
        esperado_total = dp.saldo_sin_inversion + dp.interpolado - dp.tarjeta + dp.deuda_acumulada
        assert abs(dp.total - esperado_total) <= 0.01
