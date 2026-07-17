"""
Fund (fondo) tracking service.

A "fondo" is an interpolaciones group flagged with es_fondo=True. It behaves like a
sinking-fund / envelope: money comes in (transfers, positive MONTO) and goes out
(expenses, negative MONTO), and we track the running balance F(t) = cumsum.

Movements come from two sources (hybrid):
  - Auto: real transactions assigned to the fund via label `fondo_id`.
  - Manual: entries in pagos.csv for the group (transfers/adjustments not in the
    transaction data).

Everything is anchored to the fund's `fecha_inicio` (defaults to the first movement)
so old, wrong historical balances are not carried in.

NOTE: The dashboard-hiding mechanism (creating offset payments) is intentionally NOT
implemented here yet — that comes later.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from contabilidad.backend.logger import get_logger
from contabilidad.backend.services.transaction_service import load_data
from contabilidad.backend.storage.variables_storage import InterpolationStorage

logger = get_logger(__name__)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
        return default if pd.isna(f) else f
    except (ValueError, TypeError):
        return default


def _to_date(value: Any) -> Optional[date]:
    if value is None or value == '':
        return None
    try:
        ts = pd.to_datetime(value)
        if pd.isna(ts):
            return None
        return ts.date()
    except Exception:
        return None


def _is_truthy(value: Any) -> bool:
    """Coerce a label value (bool / NaN / 'True'/'False' string) to bool."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in ('true', '1', 'yes', 'si', 'sí')
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return bool(value)


def _has_tag(tags_value: Any, tag: str) -> bool:
    """True if the comma-separated `tags` field contains `tag` as a whole token."""
    if not tag:
        return False
    tokens = [t.strip().lower() for t in str(tags_value or '').split(',')]
    return tag.strip().lower() in tokens


def _collect_transaction_movements(group_id: str, tag: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Transactions that belong to this fund, either because they were assigned
    manually (`fondo_id` label) OR because they carry the fund's linked tag.
    """
    df = load_data()
    if df.empty:
        return []

    has_fondo_col = 'fondo_id' in df.columns
    has_tags_col = 'tags' in df.columns

    if has_fondo_col:
        mask = df['fondo_id'].fillna('').astype(str) == str(group_id)
    else:
        mask = pd.Series(False, index=df.index)

    if tag and has_tags_col:
        tag_mask = df['tags'].apply(lambda v: _has_tag(v, tag))
        mask = mask | tag_mask

    df = df[mask]
    if df.empty:
        return []

    movements: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        d = _to_date(row.get('FECHA'))
        if d is None:
            continue
        # Refundable parts belong to the Debts module, not to a spending fund.
        # Exclude them so a split's refundable portion never pollutes the fund.
        if _is_truthy(row.get('es_reembolsable')):
            continue
        by_tag = tag is not None and _has_tag(row.get('tags'), tag)
        amount = _safe_float(row.get("MONTO"))
        note = row.get('nombre_limpio') or row.get('DESCRIPCION') or ''
        reviewed = bool(row.get('revisado')) if row.get('revisado') is not None else False
        movements.append({
            'id': str(row.get('id')),
            'date': d,
            'amount': amount,
            'note': str(note),
            'source': 'tag' if by_tag else 'transaction',
            'reviewed': reviewed,
        })
    return movements


def _collect_manual_movements(group_id: str) -> List[Dict[str, Any]]:
    """Manual entries stored as payments for this group."""
    payments = InterpolationStorage.get_payments(group_id)
    movements: List[Dict[str, Any]] = []
    for p in payments:
        # Event date: prefer end_date, fall back to start_date.
        d = _to_date(p.get('end_date')) or _to_date(p.get('start_date'))
        if d is None:
            continue
        movements.append({
            'id': str(p.get('id')),
            'date': d,
            'amount': _safe_float(p.get('amount')),
            'note': str(p.get('note') or ''),
            'source': 'manual',
            'reviewed': True,
        })
    return movements


def _compute_metrics(movements: List[Dict[str, Any]], saldo_inicial: float,
                     start_date: Optional[date]) -> Dict[str, Any]:
    total_in = sum(m['amount'] for m in movements if m['amount'] > 0)
    total_out = sum(-m['amount'] for m in movements if m['amount'] < 0)
    balance = saldo_inicial + sum(m['amount'] for m in movements)

    first_date = movements[0]['date'] if movements else start_date
    last_date = movements[-1]['date'] if movements else None

    # Burn rate: average spending per week over the active window.
    burn_rate_weekly: Optional[float] = None
    projection: Optional[Dict[str, Any]] = None

    if len(movements) >= 2 and total_out > 0 and first_date is not None:
        days_active = (date.today() - first_date).days
        if days_active >= 7:
            burn_rate_weekly = total_out / (days_active / 7.0)

    if burn_rate_weekly and burn_rate_weekly > 0:
        if balance > 0:
            weeks_left = balance / burn_rate_weekly
            agot = date.today() + timedelta(days=round(weeks_left * 7))
            projection = {
                'status': 'surplus',
                'weeks_left': round(weeks_left, 1),
                'runs_out_on': agot.isoformat(),
            }
        else:
            projection = {'status': 'deficit', 'weeks_left': 0, 'runs_out_on': None}

    return {
        'total_in': round(total_in, 2),
        'total_out': round(total_out, 2),
        'balance': round(balance, 2),
        'saldo_inicial': round(saldo_inicial, 2),
        'first_date': first_date.isoformat() if first_date else None,
        'last_date': last_date.isoformat() if last_date else None,
        'movement_count': len(movements),
        'burn_rate_weekly': round(burn_rate_weekly, 2) if burn_rate_weekly else None,
        'projection': projection,
    }


def get_fund_detail(group_id: str, view_start: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Full fund detail: config + ordered movements with running balance + metrics.

    `view_start` is a display-only lens: when given, only movements on/after that
    date are shown, the running balance restarts at 0 (prior accumulation is
    ignored), and metrics are recomputed over that window. It does NOT change the
    fund's permanent `fecha_inicio`.
    """
    group = InterpolationStorage.get_group(group_id)
    if group is None:
        return None

    saldo_inicial = _safe_float(group.get('saldo_inicial'))
    tag = group.get('tag_vinculado')

    movements = _collect_transaction_movements(group_id, tag) + _collect_manual_movements(group_id)

    # Anchor to fecha_inicio: explicit if set, else auto = first movement date.
    configured_start = _to_date(group.get('fecha_inicio'))
    if configured_start is not None:
        movements = [m for m in movements if m['date'] >= configured_start]
        start_date = configured_start
    else:
        start_date = min((m['date'] for m in movements), default=None)

    # Display lens: restart the view from a chosen date, balance from 0.
    view_start_date = _to_date(view_start)
    if view_start_date is not None:
        movements = [m for m in movements if m['date'] >= view_start_date]
        base_balance = 0.0
        start_date = view_start_date
    else:
        base_balance = saldo_inicial

    # Order by date, then manual after transaction on ties (stable), and cumsum.
    movements.sort(key=lambda m: (m['date'], 0 if m['source'] == 'transaction' else 1))

    running = base_balance
    out_movements: List[Dict[str, Any]] = []
    for m in movements:
        running += m['amount']
        out_movements.append({
            **m,
            'date': m['date'].isoformat(),
            'running_balance': round(running, 2),
        })

    metrics = _compute_metrics(movements, base_balance, start_date)

    # Generated payments group (if the flattened pairs were already materialized).
    generated = None
    for g in InterpolationStorage.get_groups_by_fondo_origen(group_id):
        generated = {
            'id': g['id'],
            'name': g['name'],
            'payment_count': len(InterpolationStorage.get_payments(g['id'])),
        }
        break

    return {
        'id': group['id'],
        'name': group['name'],
        'description': group.get('description', ''),
        'es_fondo': group.get('es_fondo', True),
        'tag_vinculado': tag,
        'fecha_inicio': start_date.isoformat() if start_date else None,
        'fecha_inicio_auto': configured_start is None,
        'view_start': view_start_date.isoformat() if view_start_date else None,
        'summary': metrics,
        'movements': out_movements,
        'generated_payments': generated,
    }


def get_all_funds() -> List[Dict[str, Any]]:
    """List every fund with a lightweight summary + balance sparkline."""
    groups = InterpolationStorage.get_groups(type_filter=None, fund_only=True)
    funds: List[Dict[str, Any]] = []
    for g in groups:
        detail = get_fund_detail(g['id'])
        if detail is None:
            continue
        sparkline = [m['running_balance'] for m in detail['movements']]
        funds.append({
            'id': detail['id'],
            'name': detail['name'],
            'description': detail['description'],
            'tag_vinculado': detail['tag_vinculado'],
            'fecha_inicio': detail['fecha_inicio'],
            'summary': detail['summary'],
            'sparkline': sparkline,
        })
    return funds
