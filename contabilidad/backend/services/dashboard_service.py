import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Protocol
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from contabilidad.backend.logger import get_logger
from contabilidad.backend.storage.data_pipeline import get_pipeline
from contabilidad.backend.storage.variables_storage import InterpolationStorage
from contabilidad.backend.models.dashboard_models import ChartDataPoint, DashboardResponse, TransactionDriver, DailyVariation

logger = get_logger(__name__)

# ============================================================================
# 2. CONFIGURATION
# ============================================================================

@dataclass
class DashboardConfig:
    """Centralized configuration for dashboard behavior."""
    
    col_fecha: str = 'FECHA'
    col_saldo: str = 'SALDO'
    col_tarjeta: str = 'TARJETA'
    col_notion: str = 'NOTIONCUM'
    col_deuda_acumulada: str = 'DEUDA_ACUMULADA'
    col_pagos_fijos: str = 'PAGOS_FIJOS'
    col_interpolado: str = 'INTERPOLADO'
    col_pago_tarjeta: str = 'PAGO_TARJETA'
    col_monto: str = 'MONTO'
    
    highlighted_days: List[str] = field(default_factory=lambda: [
        '2024-06-22',
        '2024-09-30',
        '2025-01-31',
        '2025-03-22',
        '2025-07-18',
        "2025-09-30",
        '2026-01-30',
        '2026-03-16'
    ])
    
    forward_fill: bool = True
    initial_value: float = 0.0
    
    auto_extend_range: bool = True
    min_date_override: Optional[date] = date(2024, 3, 12)
    max_date_override: Optional[date] = None
    
    calculate_differences: bool = True
    include_fixed_payments: bool = True
    include_interpolated: bool = True
    include_notion: bool = False
    include_deuda_acumulada: bool = True

# ============================================================================
# 4. DATA SOURCE ABSTRACTION
# ============================================================================

class DataSource(ABC):
    def __init__(self, config: DashboardConfig):
        self.config = config
    
    @abstractmethod
    def fetch(self) -> pd.DataFrame:
        pass
    
    @property
    @abstractmethod
    def output_columns(self) -> List[str]:
        pass
    
    def _create_empty_df(self) -> pd.DataFrame:
        return pd.DataFrame(columns=[self.config.col_fecha] + self.output_columns)

class BankDataSource(DataSource):
    def __init__(self, config: DashboardConfig, pipeline):
        super().__init__(config)
        self.pipeline = pipeline
    
    @property
    def output_columns(self) -> List[str]:
        return [self.config.col_saldo]
    
    def fetch(self) -> pd.DataFrame:
        try:
            df_daily = self.pipeline.get_daily_data(source='cuenta')
            if df_daily.empty or "SALDO" not in df_daily.columns:
                return self._create_empty_df()
            
            df_daily = df_daily[[self.config.col_fecha, 'SALDO']].copy()
            df_daily.rename(columns={'SALDO': self.config.col_saldo}, inplace=True)
            return df_daily
        except Exception as e:
            logger.error(f"Error fetching bank data: {e}", exc_info=True)
            return self._create_empty_df()

class CardDataSource(DataSource):
    def __init__(self, config: DashboardConfig, pipeline):
        super().__init__(config)
        self.pipeline = pipeline
    
    @property
    def output_columns(self) -> List[str]:
        return [self.config.col_tarjeta, self.config.col_pago_tarjeta]
    
    def fetch(self) -> pd.DataFrame:
        try:
            df_daily = self.pipeline.get_daily_data(source='tarjeta')
            if df_daily.empty or "TARJETA" not in df_daily.columns:
                return self._create_empty_df()
                
            df_daily = df_daily[[self.config.col_fecha, 'TARJETA', 'PAGO_TARJETA']].copy()
            df_daily['TARJETA'] = -df_daily['TARJETA']
            df_daily.rename(columns={
                'TARJETA': self.config.col_tarjeta,
                'PAGO_TARJETA': self.config.col_pago_tarjeta
            }, inplace=True)
            return df_daily
        except Exception as e:
            logger.error(f"Error fetching card data: {e}", exc_info=True)
            return self._create_empty_df()

class SupabaseDebtDataSource(DataSource):
    def __init__(self, config: DashboardConfig):
        super().__init__(config)
    
    @property
    def output_columns(self) -> List[str]:
        return [self.config.col_deuda_acumulada]
    
    def fetch(self) -> pd.DataFrame:
        if not self.config.include_deuda_acumulada:
            return self._create_empty_df()
        
        try:
            from contabilidad.debts.reading import obtener_deudas_para_analisis, obtener_todos_pagos
            
            df_debts = obtener_deudas_para_analisis(solo_pendientes=False)
            df_payments = obtener_todos_pagos()
            
            events = []
            
            if not df_debts.empty:
                for _, row in df_debts.iterrows():
                    try:
                        amount = float(row['MONTO'])
                    except:
                        amount = 0.0
                    
                    if pd.notnull(row['FECHA']):
                        events.append({'FECHA': row['FECHA'], 'CHANGE': amount})
            
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
    def __init__(self, config: DashboardConfig):
        self.config = config
    
    def apply(self, df_master: pd.DataFrame) -> pd.DataFrame:
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
        try:
            amount = float(payment['amount'])
            start = pd.to_datetime(payment['start_date']) if payment.get('start_date') else None
            end = pd.to_datetime(payment['end_date']) if payment.get('end_date') else None
            
            if not start:
                return
            
            if group_type == 'fixed' and self.config.include_fixed_payments:
                self._apply_fixed_payment(df, amount, start, end)
            elif group_type == 'interpolated' and self.config.include_interpolated:
                self._apply_interpolated_payment(df, amount, start, end)
                
        except Exception as e:
            logger.error(f"Error applying payment {payment}: {e}")
    
    def _apply_fixed_payment(self, df: pd.DataFrame, amount: float, start: pd.Timestamp, end: Optional[pd.Timestamp]) -> None:
        mask = (df[self.config.col_fecha] >= start)
        if end:
            mask &= (df[self.config.col_fecha] < end)
        df.loc[mask, self.config.col_pagos_fijos] += amount
    
    def _apply_interpolated_payment(self, df: pd.DataFrame, amount: float, start: pd.Timestamp, end: Optional[pd.Timestamp]) -> None:
        if not end:
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
    def __init__(self, config: DashboardConfig):
        self.config = config
    
    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._calculate_saldo_sin_inversion(df)
        df = self._calculate_total(df)
        
        if self.config.calculate_differences:
            df = self._calculate_differences(df)
        return df
    
    def _calculate_saldo_sin_inversion(self, df: pd.DataFrame) -> pd.DataFrame:
        print(df.columns)
        df['saldo_sin_inversion'] = df[self.config.col_saldo] - df[self.config.col_pagos_fijos]
        return df
    
    def _calculate_total(self, df: pd.DataFrame) -> pd.DataFrame:
        df['TOTAL'] = (
            df['saldo_sin_inversion'] +
            df[self.config.col_interpolado] -
            df[self.config.col_tarjeta]
            + df.get(self.config.col_deuda_acumulada, 0.0) 
        )
        return df
    
    def _calculate_differences(self, df: pd.DataFrame) -> pd.DataFrame:
        df['diff_total'] = df['TOTAL'].diff().fillna(0.0)
        df['diff_tarjeta'] = df[self.config.col_tarjeta].diff().fillna(0.0)
        df['diff_pago_tarjeta'] = df[self.config.col_pago_tarjeta].diff().fillna(0.0)
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
    def __init__(self, config: Optional[DashboardConfig] = None):
        self.config = config or DashboardConfig()
        self.pipeline = get_pipeline()
        
        self.data_sources: List[DataSource] = [
            BankDataSource(self.config, self.pipeline),
            CardDataSource(self.config, self.pipeline),
            SupabaseDebtDataSource(self.config),
        ]
        
        self.virtual_processor = VirtualItemsProcessor(self.config)
        self.metric_processor = MetricProcessor(self.config)
    
    def get_chart_data(self) -> DashboardResponse:
        df_master = self.pipeline.get_daily_data(source='all')
        if not df_master.empty:
            df_master = self.pipeline.pipeline.execute(
                df_master, 
                skip_cache=False, 
                run_only=['virtual_items', 'dashboard_metrics']
            )
            
        if df_master.empty:
            return DashboardResponse(
                data=[],
                highlighted_days=self.config.highlighted_days,
                metadata={'status': 'no_data'}
            )
        
        return self._build_response(df_master)
    
    def _fetch_all_sources(self) -> List[pd.DataFrame]:
        dataframes = []
        for source in self.data_sources:
            logger.info(f"Fetching data from {source.__class__.__name__}")
            df = source.fetch()
            dataframes.append(df)
        return dataframes
    
    def _determine_date_range(self, dataframes: List[pd.DataFrame]) -> pd.DatetimeIndex:
        all_dates = pd.concat([
            df[self.config.col_fecha] if not df.empty else pd.Series(dtype='datetime64[ns]')
            for df in dataframes
        ])
        if all_dates.empty:
            return pd.DatetimeIndex([])
        
        min_date = self.config.min_date_override or all_dates.min()
        max_date = self.config.max_date_override or all_dates.max()
        return pd.date_range(start=min_date, end=max_date, freq='D')
    
    def _create_master_timeline(self, date_range: pd.DatetimeIndex, dataframes: List[pd.DataFrame]) -> pd.DataFrame:
        df_master = pd.DataFrame({self.config.col_fecha: date_range})
        for i, df in enumerate(dataframes):
            if df.empty:
                continue
            df_master = df_master.merge(df, on=self.config.col_fecha, how='left')
        
        snapshot_cols = [
            self.config.col_saldo,
            self.config.col_tarjeta,
            self.config.col_deuda_acumulada,
            self.config.col_pago_tarjeta
        ]
        
        for col in snapshot_cols:
            if col not in df_master.columns:
                df_master[col] = float('nan')
        
        if self.config.forward_fill:
            df_master[snapshot_cols] = df_master[snapshot_cols].ffill().fillna(self.config.initial_value)
        else:
            df_master[snapshot_cols] = df_master[snapshot_cols].fillna(self.config.initial_value)
            
        if self.config.col_notion not in df_master.columns:
             df_master[self.config.col_notion] = 0.0
        
        return df_master
    
    def _build_response(self, df_master: pd.DataFrame) -> DashboardResponse:
        data_points = []
        for _, row in df_master.iterrows():
            data_points.append(ChartDataPoint(
                date=row[self.config.col_fecha].strftime('%Y-%m-%d'),
                total=float(row['TOTAL']),
                saldo=float(row.get(self.config.col_saldo, 0.0)),
                saldo_sin_inversion=float(row.get('saldo_sin_inversion', 0.0)),
                tarjeta=float(row.get(self.config.col_tarjeta, 0.0)),
                pago_tarjeta=float(row.get(self.config.col_pago_tarjeta, 0.0)),
                pagos_fijos=float(row.get(self.config.col_pagos_fijos, 0.0)),
                interpolado=float(row.get(self.config.col_interpolado, 0.0)),
                notion=float(row.get(self.config.col_notion, 0.0)),
                deuda_acumulada=float(row.get(self.config.col_deuda_acumulada, 0.0)),
                diff_total=float(row.get('diff_total', 0.0)),
                diff_tarjeta=float(row.get('diff_tarjeta', 0.0)),
                diff_pago_tarjeta=float(row.get('diff_pago_tarjeta', 0.0)),
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
# 9. VARIATION ANALYSIS
# ============================================================================

class VariationsAnalyzer:
    def __init__(self):
        self.drivers_by_date: Dict[str, List[TransactionDriver]] = {}

    def fetch_all_drivers(self):
        self.drivers_by_date = {}
        self._process_transactions()
        self._process_debts()
        self._process_debt_payments()
        self._process_fixed_payments()
        
    def analyze(self, chart_data: List[ChartDataPoint]) -> List[DailyVariation]:
        variations = []
        sorted_data = sorted(chart_data, key=lambda x: x.date)
        
        for point in sorted_data:
            dt_str = point.date
            net_change = point.diff_total
            
            d_tarjeta = point.diff_tarjeta or 0.0
            d_notion = point.diff_notion or 0.0
            d_interpolados = point.diff_interpolados or 0.0
            d_deuda_acum = point.diff_deuda_acumulada or 0.0
            real_saldo_impact = point.diff_saldo_sin_inversion
            d_pagos_fijos = point.diff_pagos_fijos or 0.0
            
            day_drivers = self.drivers_by_date.get(dt_str, [])
            
            income_total = sum(d.amount for d in day_drivers if d.amount > 0)
            expense_total = sum(d.amount for d in day_drivers if d.amount < 0)
            
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
        if len(variations_sin_inicio) > 1:
            variations_sin_inicio.pop(0)
        if len(variations_sin_inicio) > 0:
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
            t_type = row.get('TIPO', 'BANCA')
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
        try:
            from contabilidad.debts.reading import obtener_deudas_para_analisis
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
        try:
            from contabilidad.debts.reading import obtener_todos_pagos
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
        try:
            from contabilidad.backend.storage.variables_storage import InterpolationStorage
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
        
        if group_type != 'interpolated':
            start_dt = p.get('start_date')
            end_dt = p.get('end_date')
            amt = float(p.get('amount', 0.0))
            if start_dt:
                s_str = self._safe_date_str(start_dt)
                self._add_driver(s_str, TransactionDriver(
                    description=f"{p.get('note') or 'Pago Fijo'} ({p['group_name']})",
                    amount=-amt, 
                    type='fixed_payment',
                    source='PAGOS_FIJO',
                    date=s_str
                ))
            if end_dt:
                e_str = self._safe_date_str(end_dt)
                self._add_driver(e_str, TransactionDriver(
                    description=f"Fin Pago Fijo ({p['group_name']})",
                    amount=amt, 
                    type='fixed_payment_end',
                    source='PAGOS_FIJO',
                    date=e_str
                ))
                
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
                        for i in range(days):
                            current_day = s + pd.Timedelta(days=i)
                            d_str = current_day.strftime('%Y-%m-%d')
                            
                            self._add_driver(d_str, TransactionDriver(
                                description=f"Valuación: {p.get('note') or 'Interpolado'} ({p['group_name']})",
                                amount=daily_amt,
                                type='interpolated_accrual',
                                source='INTERPOLADOS',
                                date=d_str
                            ))
                except Exception as e:
                    logger.error(f"Error calculating interpolation for {p}: {e}")

    def _safe_date_str(self, val):
        if hasattr(val, 'strftime'):
            return val.strftime('%Y-%m-%d')
        return str(val)
