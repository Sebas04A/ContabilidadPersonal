"""
Dashboard API Module
====================
This module provides a unified dashboard service that aggregates financial data
from multiple sources (Bank, Card, Notion, Virtual Items) and exposes it via FastAPI.

Architecture:
- DataSource: Abstract base class for all data sources
- DashboardConfig: Centralized configuration
- MetricProcessor: Calculates derived metrics
- DashboardService: Orchestrates everything
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Protocol
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, date
import logging

# ============================================================================
# 1. PROJECT SETUP & CONFIGURATION
# ============================================================================

# Path Setup
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
contabilidad_dir = os.path.dirname(backend_dir)
project_root = os.path.dirname(contabilidad_dir)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Imports with fallback
try:
    from contabilidad.backend.data_pipeline import get_pipeline
    from contabilidad.backend.storage import InterpolationStorage
    from contabilidad.Modelos import PAGO
except ImportError as e:
    logger.error(f"Critical Import Error: {e}")
    def get_pipeline():
        raise ImportError(f"Pipeline not available: {e}")
    
    class InterpolationStorage:
        @staticmethod
        def get_groups(*args, **kwargs):
            return []
        @staticmethod
        def get_payments(*args, **kwargs):
            return []


# ============================================================================
# 2. CONFIGURATION
# ============================================================================

@dataclass
class DashboardConfig:
    """Centralized configuration for dashboard behavior."""
    
    # Column names (easy to change if your data structure changes)
    col_fecha: str = 'FECHA'
    col_saldo: str = 'SALDO'
    col_tarjeta: str = 'TARJETA'
    col_notion: str = 'NOTIONCUM'
    col_deuda_acumulada: str = 'DEUDA_ACUMULADA'
    col_pagos_fijos: str = 'PAGOS_FIJOS'
    col_interpolado: str = 'INTERPOLADO'
    col_monto: str = 'MONTO'
    
    # Highlighted days (special events to mark on the chart)
    highlighted_days: List[str] = field(default_factory=lambda: [
        '2024-06-22',
        '2024-09-30',
        '2025-01-31',
        '2025-03-22',
        '2025-07-18'
    ])
    
    # Data processing options
    forward_fill: bool = True  # Fill gaps with last known value
    initial_value: float = 0.0  # Value to use before first data point
    
    # Date range behavior
    auto_extend_range: bool = True  # Extend range to cover all data sources
    min_date_override: Optional[date] = date(2024, 3, 12)
    max_date_override: Optional[date] = None
    
    # Metric calculation flags (enable/disable specific calculations)
    calculate_differences: bool = True
    include_fixed_payments: bool = True
    include_interpolated: bool = True
    include_notion: bool = False
    include_deuda_acumulada: bool = True


# ============================================================================
# 3. DATA MODELS
# ============================================================================

class ChartDataPoint(BaseModel):
    """Single point in the dashboard chart."""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    total: float = Field(..., description="Total net worth")
    saldo: float = Field(..., description="Bank account balance")
    saldo_sin_inversion: float = Field(..., description="Liquid balance (excluding investments)")
    tarjeta: float = Field(..., description="Credit card debt")
    pagos_fijos: float = Field(..., description="Fixed payments/investments")
    interpolado: float = Field(..., description="Interpolated/accrued values")
    notion: float = Field(..., description="External debts/assets from Notion")
    deuda_acumulada: float = Field(..., description="Net accumulated debt from Supabase")
    
    # Daily differences (changes from previous day)
    diff_total: Optional[float] = 0.0
    diff_tarjeta: Optional[float] = 0.0
    diff_saldo_sin_inversion: Optional[float] = 0.0
    diff_notion: Optional[float] = 0.0
    diff_deuda_acumulada: Optional[float] = 0.0 
    diff_pagos_fijos: Optional[float] = 0.0
    diff_interpolados: Optional[float] = 0.0 


class DashboardResponse(BaseModel):
    """Complete dashboard data response."""
    data: List[ChartDataPoint]
    highlighted_days: List[str]
    metadata: Optional[Dict[str, Any]] = None  # Extra info like date range, data quality, etc.


# ============================================================================
# 4. DATA SOURCE ABSTRACTION
# ============================================================================

class DataSource(ABC):
    """
    Abstract base class for all data sources.
    Makes it easy to add/remove data sources without touching core logic.
    """
    
    def __init__(self, config: DashboardConfig):
        self.config = config
    
    @abstractmethod
    def fetch(self) -> pd.DataFrame:
        """Fetch and normalize data from this source."""
        pass
    
    @property
    @abstractmethod
    def output_columns(self) -> List[str]:
        """Columns this source provides."""
        pass
    
    def _create_empty_df(self) -> pd.DataFrame:
        """Create empty DataFrame with expected columns."""
        return pd.DataFrame(columns=[self.config.col_fecha] + self.output_columns)


class BankDataSource(DataSource):
    """Fetches bank account balance data."""
    
    def __init__(self, config: DashboardConfig, pipeline):
        super().__init__(config)
        self.pipeline = pipeline
    
    @property
    def output_columns(self) -> List[str]:
        return [self.config.col_saldo]
    
    def fetch(self) -> pd.DataFrame:
        try:
            df = self.pipeline.get_banca_data()
            if df.empty:
                return self._create_empty_df()
            
            # Normalize date
            df[self.config.col_fecha] = pd.to_datetime(df[self.config.col_fecha]).dt.normalize()
            
            # Ensure SALDO column exists
            if self.config.col_saldo not in df.columns:
                if self.config.col_monto in df.columns:
                    df[self.config.col_monto] = pd.to_numeric(df[self.config.col_monto], errors='coerce').fillna(0.0)
                    df = df.sort_values(self.config.col_fecha)
                    df[self.config.col_saldo] = df[self.config.col_monto].cumsum()
                else:
                    logger.warning("Bank data has no SALDO or MONTO column")
                    return self._create_empty_df()
            
            # Take last balance of each day
            df_daily = df.groupby(self.config.col_fecha)[self.config.col_saldo].last().reset_index()
            return df_daily
            
        except Exception as e:
            logger.error(f"Error fetching bank data: {e}", exc_info=True)
            return self._create_empty_df()


class CardDataSource(DataSource):
    """Fetches credit card debt data."""
    
    def __init__(self, config: DashboardConfig, pipeline):
        super().__init__(config)
        self.pipeline = pipeline
    
    @property
    def output_columns(self) -> List[str]:
        return [self.config.col_tarjeta]
    
    def fetch(self) -> pd.DataFrame:
        try:
            # Usar datos procesados que incluyen la lógica avanzada de transformación de tarjetas
            # 'cuenta' es el source base al que se le aplican las transformaciones (inversiones, tarjetas)
            df = self.pipeline.get_processed_data(source='cuenta')
            
            if df.empty:
                return self._create_empty_df()
            
            # Asegurar columnas
            if "TARJETA" not in df.columns:
                return self._create_empty_df()
                
            # Normalizar fechas y seleccionar columnas de interés
            df[self.config.col_fecha] = pd.to_datetime(df[self.config.col_fecha]).dt.normalize()
            
            # Tomar el último valor de cada día para el gráfico diario
            # La columna 'TARJETA' ya tiene el balance acumulado (Saldo + Consumos - Pagos)
            # Como los consumos ahora son negativos (gastos), el balance 'TARJETA' viene negativo (ej: -100 deuda).
            # Para el dashboard, esperamos una deuda positiva para restarla del total (Total = Activos - Deuda).
            # Por lo tanto, invertimos el signo aquí.
            df_daily = df.groupby(self.config.col_fecha)['TARJETA'].last().reset_index()
            # No invertir el signo. El pipeline ya entrega la deuda como negativa (ej: -100).
            # Al sumarla al TOTAL, restará correctamente.
            df_daily['TARJETA'] = -df_daily['TARJETA']
            
            # Renombrar a la columna esperada por el config
            df_daily.rename(columns={'TARJETA': self.config.col_tarjeta}, inplace=True)
            
            return df_daily
            
        except Exception as e:
            logger.error(f"Error fetching card data: {e}", exc_info=True)
            return self._create_empty_df()


class SupabaseDebtDataSource(DataSource):
    """Fetches cumulative debts minus payments from Supabase."""
    
    def __init__(self, config: DashboardConfig):
        super().__init__(config)
    
    @property
    def output_columns(self) -> List[str]:
        return [self.config.col_deuda_acumulada]
    
    def fetch(self) -> pd.DataFrame:
        if not self.config.include_deuda_acumulada:
            return self._create_empty_df()
        
        try:
            from contabilidad.deudas.lectura import obtener_deudas_para_analisis, obtener_todos_pagos
            
            df_debts = obtener_deudas_para_analisis(solo_pendientes=False)
            df_payments = obtener_todos_pagos()
            
            events = []
            
            # 1. Process Debts (+ Amount)
            if not df_debts.empty:
                for _, row in df_debts.iterrows():
                    try:
                        amount = float(row['MONTO'])
                    except:
                        amount = 0.0
                    
                    if pd.notnull(row['FECHA']):
                        events.append({'FECHA': row['FECHA'], 'CHANGE': amount})
            
            # 2. Process Payments (- Amount)
            if not df_payments.empty:
                for _, row in df_payments.iterrows():
                    try:
                        amount = float(row['monto_total'])
                    except:
                        amount = 0.0
                        
                    if pd.notnull(row['fecha_pago']):
                         events.append({'FECHA': row['fecha_pago'], 'CHANGE': -amount})
            
            if not events:
                return self._create_empty_df()
            
            df_events = pd.DataFrame(events)
            df_events[self.config.col_fecha] = pd.to_datetime(df_events['FECHA']).dt.normalize()
            
            # Calculate cumulative
            df_daily = df_events.groupby(self.config.col_fecha)['CHANGE'].sum().reset_index()
            df_daily = df_daily.sort_values(self.config.col_fecha)
            df_daily[self.config.col_deuda_acumulada] = df_daily['CHANGE'].cumsum()
            
            return df_daily[[self.config.col_fecha, self.config.col_deuda_acumulada]]
            
        except ImportError:
            logger.warning("Supabase Debt integration not available")
            return self._create_empty_df()
        except Exception as e:
            logger.error(f"Error fetching supabase debt data: {e}", exc_info=True)
            return self._create_empty_df()



# ============================================================================
# 5. VIRTUAL ITEMS PROCESSOR
# ============================================================================

class VirtualItemsProcessor:
    """
    Processes user-defined virtual items (fixed payments and interpolated values).
    This is separate from data sources because it operates on the timeline, not raw data.
    """
    
    def __init__(self, config: DashboardConfig):
        self.config = config
    
    def apply(self, df_master: pd.DataFrame) -> pd.DataFrame:
        """Add PAGOS_FIJOS and INTERPOLADO columns to the master DataFrame."""
        
        # Initialize columns
        df_master[self.config.col_pagos_fijos] = 0.0
        df_master[self.config.col_interpolado] = 0.0
        
        if df_master.empty:
            return df_master
        
        try:
            groups = InterpolationStorage.get_groups(type_filter=None)
            
            for group in groups:
                group_type = group.get('type', 'interpolated')
                payments = InterpolationStorage.get_payments(group['id'])
                
                for payment in payments:
                    self._apply_payment(df_master, payment, group_type)
                    
        except Exception as e:
            logger.error(f"Error processing virtual items: {e}", exc_info=True)
        
        return df_master
    
    def _apply_payment(self, df: pd.DataFrame, payment: Dict, group_type: str) -> None:
        """Apply a single payment to the DataFrame."""
        try:
            amount = float(payment['amount'])
            start = pd.to_datetime(payment['start_date']) if payment.get('start_date') else None
            end = pd.to_datetime(payment['end_date']) if payment.get('end_date') else None
            
            if not start:
                logger.warning(f"Payment {payment.get('id', 'unknown')} has no start date, skipping")
                return
            
            if group_type == 'fixed' and self.config.include_fixed_payments:
                self._apply_fixed_payment(df, amount, start, end)
            elif group_type == 'interpolated' and self.config.include_interpolated:
                self._apply_interpolated_payment(df, amount, start, end)
                
        except Exception as e:
            logger.error(f"Error applying payment {payment}: {e}")
    
    def _apply_fixed_payment(self, df: pd.DataFrame, amount: float, start: pd.Timestamp, end: Optional[pd.Timestamp]) -> None:
        """Add constant value from start to end date."""
        mask = (df[self.config.col_fecha] >= start)
        if end:
            mask &= (df[self.config.col_fecha] < end)  # Exclusive end
        
        df.loc[mask, self.config.col_pagos_fijos] += amount
    
    def _apply_interpolated_payment(self, df: pd.DataFrame, amount: float, start: pd.Timestamp, end: Optional[pd.Timestamp]) -> None:
        """Apply linear interpolation from start to end."""
        if not end:
            logger.warning("Interpolated payment requires end date, skipping")
            return
        
        total_days = (end - start).days
        if total_days <= 0:
            return
        
        mask = (df[self.config.col_fecha] >= start) & (df[self.config.col_fecha] < end)
        df_slice = df.loc[mask]
        
        if not df_slice.empty:
            days_passed = (df_slice[self.config.col_fecha] - start).dt.days
            values = (days_passed / total_days) * amount
            df.loc[mask, self.config.col_interpolado] += values


# ============================================================================
# 6. METRIC PROCESSOR
# ============================================================================

class MetricProcessor:
    """
    Calculates derived metrics from raw data.
    Each metric is independent and can be easily modified or disabled.
    """
    
    def __init__(self, config: DashboardConfig):
        self.config = config
    
    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all derived metrics."""
        df = self._calculate_saldo_sin_inversion(df)
        df = self._calculate_total(df)
        
        if self.config.calculate_differences:
            df = self._calculate_differences(df)
        
        return df
    
    def _calculate_saldo_sin_inversion(self, df: pd.DataFrame) -> pd.DataFrame:
        """Liquid balance = Total Saldo - Fixed Payments (locked money)."""
        df['saldo_sin_inversion'] = df[self.config.col_saldo] - df[self.config.col_pagos_fijos]
        return df
    
    def _calculate_total(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Total Net Worth = Liquid + Interpolated - Tarjeta
        Note: DeudaAcumulada (Receivables) is EXCLUDED from Total per user request,
        but implies it can be viewed as a separate metric.
        """
        df['TOTAL'] = (
            df['saldo_sin_inversion'] +
            # df[self.config.col_pagos_fijos] +
            df[self.config.col_interpolado] +
            df[self.config.col_tarjeta]
            + df.get(self.config.col_deuda_acumulada, 0.0) 
        )
        return df
    
    def _calculate_differences(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate daily changes for key metrics."""
        df['diff_total'] = df['TOTAL'].diff().fillna(0.0)
        df['diff_tarjeta'] = df[self.config.col_tarjeta].diff().fillna(0.0)
        df['diff_saldo_sin_inversion'] = df['saldo_sin_inversion'].diff().fillna(0.0)
        df['diff_pagos_fijos'] = df[self.config.col_pagos_fijos].diff().fillna(0.0)
        df['diff_interpolados'] = df[self.config.col_interpolado].diff().fillna(0.0)
        
        if self.config.col_deuda_acumulada in df.columns:
            df['diff_deuda_acumulada'] = df[self.config.col_deuda_acumulada].diff().fillna(0.0)
            
        if self.config.col_notion in df.columns:
            df['diff_notion'] = df[self.config.col_notion].diff().fillna(0.0)
            
        return df


# ============================================================================
# 7. MAIN DASHBOARD SERVICE
# ============================================================================

class DashboardService:
    """
    Main orchestrator that brings everything together.
    To add a new data source: just add it to self.data_sources list.
    To modify a metric: edit MetricProcessor.
    To change config: edit DashboardConfig.
    """
    
    def __init__(self, config: Optional[DashboardConfig] = None):
        self.config = config or DashboardConfig()
        self.pipeline = get_pipeline()
        
        # Register all data sources (easy to add/remove)
        self.data_sources: List[DataSource] = [
            BankDataSource(self.config, self.pipeline),
            CardDataSource(self.config, self.pipeline),
            SupabaseDebtDataSource(self.config),
        ]
        
        self.virtual_processor = VirtualItemsProcessor(self.config)
        self.metric_processor = MetricProcessor(self.config)
    
    def get_chart_data(self) -> DashboardResponse:
        """Main method to generate dashboard data."""
        
        # Step 1: Fetch all data sources
        dataframes = self._fetch_all_sources()
        
        # Step 2: Determine date range
        date_range = self._determine_date_range(dataframes)
        if date_range.empty:
            return DashboardResponse(
                data=[],
                highlighted_days=self.config.highlighted_days,
                metadata={'status': 'no_data'}
            )
        
        # Step 3: Create master timeline
        df_master = self._create_master_timeline(date_range, dataframes)
        
        # Step 4: Apply virtual items
        df_master = self.virtual_processor.apply(df_master)
        
        # Step 5: Calculate derived metrics
        df_master = self.metric_processor.calculate_all(df_master)
        
        # Step 6: Convert to response format
        return self._build_response(df_master)
    
    def _fetch_all_sources(self) -> List[pd.DataFrame]:
        """Fetch data from all registered sources."""
        dataframes = []
        for source in self.data_sources:
            logger.info(f"Fetching data from {source.__class__.__name__}")
            df = source.fetch()
            dataframes.append(df)
        return dataframes
    
    def _determine_date_range(self, dataframes: List[pd.DataFrame]) -> pd.DatetimeIndex:
        """Determine the full date range covering all data sources."""
        
        # Collect all dates
        all_dates = pd.concat([
            df[self.config.col_fecha] if not df.empty else pd.Series(dtype='datetime64[ns]')
            for df in dataframes
        ])
        
        if all_dates.empty:
            return pd.DatetimeIndex([])
        
        # Determine min/max
        min_date = self.config.min_date_override or all_dates.min()
        max_date = self.config.max_date_override or all_dates.max()
        
        return pd.date_range(start=min_date, end=max_date, freq='D')
    
    def _create_master_timeline(self, date_range: pd.DatetimeIndex, dataframes: List[pd.DataFrame]) -> pd.DataFrame:
        """Create master DataFrame by merging all sources on the timeline."""
        
        df_master = pd.DataFrame({self.config.col_fecha: date_range})
        
        # Merge each data source
        for i, df in enumerate(dataframes):
            if df.empty:
                continue
            df_master = df_master.merge(df, on=self.config.col_fecha, how='left')
        
        # Fill missing values
        snapshot_cols = [
            self.config.col_saldo,
            self.config.col_tarjeta,
            self.config.col_deuda_acumulada
        ]
        
        for col in snapshot_cols:
            if col not in df_master.columns:
                df_master[col] = float('nan')
        
        # Forward fill (last known value) then fill initial NaNs with 0
        if self.config.forward_fill:
            df_master[snapshot_cols] = df_master[snapshot_cols].ffill().fillna(self.config.initial_value)
        else:
            df_master[snapshot_cols] = df_master[snapshot_cols].fillna(self.config.initial_value)
            
        # For backward compatibility if col_notion is still referenced somewhere
        if self.config.col_notion not in df_master.columns:
             df_master[self.config.col_notion] = 0.0
        
        return df_master
    
    def _build_response(self, df_master: pd.DataFrame) -> DashboardResponse:
        """Convert DataFrame to API response format."""
        
        data_points = []
        for _, row in df_master.iterrows():
            data_points.append(ChartDataPoint(
                date=row[self.config.col_fecha].strftime('%Y-%m-%d'),
                total=float(row['TOTAL']),
                saldo=float(row[self.config.col_saldo]),
                saldo_sin_inversion=float(row['saldo_sin_inversion']),
                tarjeta=float(row[self.config.col_tarjeta]),
                pagos_fijos=float(row[self.config.col_pagos_fijos]),
                interpolado=float(row[self.config.col_interpolado]),
                notion=float(row[self.config.col_notion]),
                deuda_acumulada=float(row.get(self.config.col_deuda_acumulada, 0.0)),
                diff_total=float(row.get('diff_total', 0.0)),
                diff_tarjeta=float(row.get('diff_tarjeta', 0.0)),
                diff_saldo_sin_inversion=float(row.get('diff_saldo_sin_inversion', 0.0)),
                diff_notion=float(row.get('diff_notion', 0.0)),
                diff_deuda_acumulada=float(row.get('diff_deuda_acumulada', 0.0)),
                diff_pagos_fijos=float(row.get('diff_pagos_fijos', 0.0)),
                diff_interpolados=float(row.get('diff_interpolados', 0.0))
            ))
        
        metadata = {
            'total_days': len(df_master),
            'date_range': {
                'start': df_master[self.config.col_fecha].min().strftime('%Y-%m-%d'),
                'end': df_master[self.config.col_fecha].max().strftime('%Y-%m-%d')
            }
        }
        
        return DashboardResponse(
            data=data_points,
            highlighted_days=self.config.highlighted_days,
            metadata=metadata
        )



# ============================================================================
# 8. API ENDPOINTS
# ============================================================================

router = APIRouter()


@router.get("/chart-data", response_model=DashboardResponse)
def get_dashboard_chart_data():
    """
    Generate unified dashboard chart data.
    
    Returns:
        DashboardResponse: Complete dashboard data with all metrics
        
    Raises:
        HTTPException: If there's a critical error generating the data
    """
    try:
        service = DashboardService()
        return service.get_chart_data()
    except Exception as e:
        logger.error(f"Error generating dashboard data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating dashboard: {str(e)}")


@router.get("/config")
def get_dashboard_config():
    """
    Get current dashboard configuration.
    Useful for debugging or showing what's enabled/disabled.
    """
    config = DashboardConfig()
    return {
        "highlighted_days": config.highlighted_days,
        "features": {
            "calculate_differences": config.calculate_differences,
            "include_fixed_payments": config.include_fixed_payments,
            "include_interpolated": config.include_interpolated,
            "include_notion": config.include_notion
        },
        "data_processing": {
            "forward_fill": config.forward_fill,
            "initial_value": config.initial_value
        }
    }


# ============================================================================
# 9. VARIATION ANALYSIS (NEW)
# ============================================================================



class TransactionDriver(BaseModel):
    description: str
    amount: float
    type: str # 'income' or 'expense'
    category: Optional[str] = None
    account: Optional[str] = None
    source: str = 'BANCA' # 'BANCA', 'TARJETA', 'DEUDA', 'PAGOS_FIJO', 'INTERPOLADOS'
    date: str

class DailyVariation(BaseModel):
    date: str
    total_change: float
    
    # Components
    diff_saldo_neto: float  # Only transactional changes (income - expense)
    diff_tarjeta: float     # Change in card debt (negative if debt increases)
    diff_notion: float
    diff_deuda_acumulada: float
    diff_pagos_fijos: float
    diff_interpolados: float
    
    # Analysis
    top_drivers: List[TransactionDriver]
    income_total: float
    expense_total: float
    unexplained_difference: float # Remaining (likely investments or valuation changes)

class VariationsAnalyzer:
    """
    Service responsible for aggregating all financial events (drivers)
    and correlating them with daily chart variations.
    """
    
    def __init__(self):
        self.drivers_by_date: Dict[str, List[TransactionDriver]] = {}

    def fetch_all_drivers(self):
        """Load and process all drivers from different sources."""
        self.drivers_by_date = {} # Reset
        
        self._process_transactions()
        self._process_debts()
        self._process_debt_payments()
        self._process_fixed_payments()
        
    def analyze(self, chart_data: List[ChartDataPoint]) -> List[DailyVariation]:
        """Generate daily variations report based on chart data and loaded drivers."""
        variations = []
        sorted_data = sorted(chart_data, key=lambda x: x.date)
        
        for point in sorted_data:
            dt_str = point.date
            net_change = point.diff_total
            
            # Extract Summaries
            d_tarjeta = point.diff_tarjeta or 0.0
            d_notion = point.diff_notion or 0.0
            d_interpolados = point.diff_interpolados or 0.0
            d_deuda_acum = point.diff_deuda_acumulada or 0.0
            real_saldo_impact = point.diff_saldo_sin_inversion
            d_pagos_fijos = point.diff_pagos_fijos or 0.0
            
            # Drivers for this day
            day_drivers = self.drivers_by_date.get(dt_str, [])
            
            # Calculate totals for verification/summary
            income_total = sum(d.amount for d in day_drivers if d.amount > 0)
            expense_total = sum(d.amount for d in day_drivers if d.amount < 0)
            
            # Residual Calculation
            # "explained_sum" must include ALL known components so that 'residual' is purely unexplained noise.
            explained_sum = income_total + expense_total
            
            residual = net_change - explained_sum

            variations.append(DailyVariation(
                date=dt_str,
                total_change=net_change,
                diff_saldo_neto=real_saldo_impact,
                diff_tarjeta=d_tarjeta,
                diff_notion=d_notion,
                diff_deuda_acumulada=d_deuda_acum,
                diff_pagos_fijos=d_pagos_fijos,
                diff_interpolados=d_interpolados,
                
                top_drivers=day_drivers, 
                income_total=income_total,
                expense_total=expense_total,
                unexplained_difference=residual
            ))
        variations_sin_inicio = variations.copy()
        #Elimino los dos primeros para no tener diferencias de inicio inexplicado
        variations_sin_inicio.pop(0)
        variations_sin_inicio.pop(0)
            
        return variations

    def _add_driver(self, dt_str: str, driver: TransactionDriver):
        if dt_str not in self.drivers_by_date:
            self.drivers_by_date[dt_str] = []
        self.drivers_by_date[dt_str].append(driver)

    def _process_transactions(self):
        from contabilidad.backend.routes.transactions import load_data
        df_trans = load_data()
        
        if df_trans.empty:
            return

        for _, row in df_trans.iterrows():
            dt_str = pd.to_datetime(row['FECHA']).strftime('%Y-%m-%d')
            
            # Determine Source
            t_type = row.get('TIPO', 'BANCA')
            # Robust description extraction
            nl = row.get('nombre_limpio')
            if pd.isna(nl) or str(nl).strip().lower() == 'nan' or not str(nl).strip():
                nl = None
            
            d_raw = row.get('DESCRIPCION')
            if pd.isna(d_raw) or str(d_raw).strip().lower() == 'nan' or not str(d_raw).strip():
                d_raw = None
                
            desc = str(nl or d_raw or 'Desconocido')
            monto = float(row.get('MONTO', 0.0))
            
            cat = str(row.get('categoria', ''))
            if cat.lower() == 'otro':
                logger.error(f"Category 'Otro' found for transaction {desc} ({monto}). Marking as ERROR_OTRO.")
                cat = "ERROR_OTRO"
            

            self._add_driver(dt_str, TransactionDriver(
                description=desc,
                amount=monto,
                type='income' if monto >= 0 else 'expense',
                category=cat,
                source=t_type,
                date=dt_str
            ))

    def _process_debts(self):
        from contabilidad.deudas.lectura import obtener_deudas_para_analisis
        try:
            df_debts = obtener_deudas_para_analisis(solo_pendientes=False)
            if df_debts.empty: return

            for _, row in df_debts.iterrows():
                dt_str = pd.to_datetime(row['FECHA']).strftime('%Y-%m-%d')
                self._add_driver(dt_str, TransactionDriver(
                    description=f"Deuda: {row['DESCRIPCION']} ({row['DEUDOR_NOMBRE']})",
                    amount=float(row['MONTO']),
                    type='debt',
                    source='DEUDA',
                    date=dt_str
                ))
        except Exception as e:
            logger.error(f"Error loading debts: {e}")

    def _process_debt_payments(self):
        from contabilidad.deudas.lectura import obtener_todos_pagos
        try:
            df_payments = obtener_todos_pagos()
            if df_payments.empty: return

            for _, row in df_payments.iterrows():
                dt_str = pd.to_datetime(row['fecha_pago']).strftime('%Y-%m-%d')
                self._add_driver(dt_str, TransactionDriver(
                    description=f"Pago Deuda: {row['deudor_nombre']}",
                    amount=-float(row['monto_total']),
                    type='debt_payment',
                    source='DEUDA',
                    date=dt_str
                ))
        except Exception as e:
            logger.error(f"Error loading debt payments: {e}")

    def _process_fixed_payments(self):
        from contabilidad.backend.storage import InterpolationStorage
        try:
            groups = InterpolationStorage.get_groups(type_filter=None)
            all_payments = []
            for g in groups:
                 pys = InterpolationStorage.get_payments(g['id'])
                 for p in pys:
                     p['group_type'] = g['type']
                     p['group_name'] = g['name']
                     all_payments.append(p)
            
            for p in all_payments:
                self._add_fixed_payment_event(p)
        except Exception as e:
            logger.error(f"Error loading fixed payments: {e}")

    def _add_fixed_payment_event(self, p):
        group_type = p.get('group_type', 'interpolated')
        
        # 1. FIXED PAYMENTS: Discrete Expense Logic (Single Event)
        # We treat anything NOT explicitly interpolated as a Fixed Payment/Expense
        if group_type != 'interpolated':
            # Start Date is the payment date
            start_dt = p['start_date']
            if start_dt:
                s_str = self._safe_date_str(start_dt)
                self._add_driver(s_str, TransactionDriver(
                    description=f"{p.get('note') or 'Pago Fijo'} ({p['group_name']})",
                    amount=-float(p['amount']), # FORCE NEGATIVE (Expense)
                    type='fixed_payment',
                    source='PAGOS_FIJO',
                    date=s_str
                ))
            
            # We ignore end_date for fixed payments as they are single events in this view
            
                
        # 2. INTERPOLATED: Continuous Accrual Logic (Daily Difference)
        elif group_type == 'interpolated':
            start_dt = p.get('start_date')
            end_dt = p.get('end_date')
            amount = float(p['amount'])
            
            if start_dt and end_dt:
                try:
                    s = pd.to_datetime(start_dt)
                    e = pd.to_datetime(end_dt)
                    days = (e - s).days
                    
                    if days > 0:
                        daily_amt = amount / days
                        
                        # Add a driver for EACH day in the range
                        for i in range(days):
                            current_day = s + pd.Timedelta(days=i)
                            d_str = current_day.strftime('%Y-%m-%d')
                            
                            self._add_driver(d_str, TransactionDriver(
                                description=f"Valuación: {p.get('note') or 'Interpolado'} ({p['group_name']})",
                                amount=daily_amt,
                                type='interpolated_accrual',
                                source='INTERPOLADOS', # Matches ComponentType
                                date=d_str
                            ))
                except Exception as e:
                    logger.error(f"Error calculating interpolation for {p}: {e}")

    def _safe_date_str(self, val):
        if hasattr(val, 'strftime'):
            return val.strftime('%Y-%m-%d')
        return str(val)


@router.get("/variations", response_model=List[DailyVariation])
def get_variations_analysis():
    """
    Analyze daily variations regarding ALL components.
    Uses VariationsAnalyzer for cleaner logic.
    """
    try:
        # 1. Get Dashboard Data
        dash_service = DashboardService()
        dash_data_response = dash_service.get_chart_data()
        
        # 2. Analyze Drivers
        analyzer = VariationsAnalyzer()
        analyzer.fetch_all_drivers()
        
        # 3. Combine
        return analyzer.analyze(dash_data_response.data)

    except Exception as e:
        logger.error(f"Error producing detailed variation analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invalidate")
def invalidate_dashboard_cache():
    """
    Forcefully invalidate the cache for the dashboard pipeline instance.
    This bypasses potential singleton mismatches in main.py.
    """
    try:
        pipeline = get_pipeline()
        pipeline.source_cache.invalidate()
        pipeline.pipeline.clear_cache()
        logger.info("Dashboard cache invalidated via dedicated endpoint")
        return {"status": "success", "message": "Dashboard cache cleared"}
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))
