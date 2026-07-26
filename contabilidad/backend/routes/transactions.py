"""
Transactions Router
===================
Pure HTTP layer — validation, delegation to services, and response serialization.
Business logic lives in:
  - contabilidad.backend.services.transaction_service
  - contabilidad.backend.storage.rules_storage
  - contabilidad.backend.utils.json_utils
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import pandas as pd
import uuid
from datetime import datetime

from contabilidad.backend.logger import get_logger
from contabilidad.backend.storage import rules_storage as rules_service
from contabilidad.backend.storage import undo_store
from contabilidad.backend.models.transaction_models import (
    TransactionOut, TransactionUpdate, SplitItem, SplitRequest, GroupRequest,
    BulkUpdateRequest,
)
from contabilidad.backend.services.transaction_service import (
    LABEL_COLUMNS,
    load_data,
    load_labels,
    load_source_data,
    save_transaction_labels,
    bulk_save_transaction_labels,
    expand_ids_with_groups,
    restore_label_snapshot,
    save_transaction_split,
    propagate_group_update,
    apply_filters,
)
from contabilidad.backend.utils.json_utils import sanitize_for_json

logger = get_logger(__name__)
router = APIRouter()


# ── Read endpoints ────────────────────────────────────────────────────────────

@router.get("/")
def get_all_transactions(
    date: Optional[str] = Query(None, description="Filter by exact date (YYYY-MM-DD)"),
    start_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    pending_only: bool = Query(False, description="Show only pending transactions"),
    es_reembolsable: Optional[bool] = Query(None, description="Filter by refundable status"),
    deudor: Optional[str] = Query(None, description="Filter by debtor name"),
    search: Optional[str] = Query(None, description="Search term in description or name"),
    source_type: Optional[str] = Query(None, description="Filter by source: BANCA or TARJETA"),
    category: Optional[str] = Query(None, description="Filter by exact category"),
    tag: Optional[str] = Query(None, description="Filter by tag presence"),
    fondo_id: Optional[str] = Query(None, description="Filter by fund id"),
):
    """Get all transactions, optionally filtered."""
    df = load_data()
    logger.debug("Data loaded")
    logger.debug(df)
    if df.empty:
        return []

    df = rules_service.apply_rules_to_dataframe(df)
    logger.debug("Data after rules")
    logger.debug(df)
    df = apply_filters(
        df,
        date=date, start_date=start_date, end_date=end_date,
        pending_only=pending_only, es_reembolsable=es_reembolsable,
        deudor=deudor, search=search, source_type=source_type,
        category=category, tag=tag, fondo_id=fondo_id,
    )

    df = sanitize_for_json(df)
    df['FECHA'] = df['FECHA'].dt.strftime('%Y-%m-%d %H:%M:%S')
    return df.to_dict(orient='records')


@router.get("/dates", response_model=List[str])
def get_available_dates():
    """Get list of unique dates that have transactions."""
    df = load_data()
    if df.empty:
        return []
    dates = sorted(df['FECHA'].dt.date.unique(), reverse=True)
    return [d.isoformat() for d in dates]


@router.get("/stats")
def get_stats(date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get summary stats for a date or overall."""
    df = load_data()

    if date:
        try:
            df = df[df['FECHA'].dt.date == pd.to_datetime(date).date()]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    total = float(df['MONTO'].sum()) if not df.empty else 0.0
    pending = int((df['revisado'] == False).sum()) if 'revisado' in df.columns else 0
    reviewed = int((df['revisado'] == True).sum()) if 'revisado' in df.columns else 0

    return {"total_monto": total, "count": len(df), "pending": pending, "reviewed": reviewed}


@router.get("/categories")
def get_categories():
    """Get list of unique categories used in the data."""
    labels = load_labels()
    if 'categoria' not in labels.columns:
        return []
    categories = labels['categoria'].dropna().unique().tolist()
    return sorted([c for c in categories if c and c not in ['---', 'Sin Categoría', '']])


@router.get("/tags")
def get_tags():
    """Get list of unique tags used in the data."""
    labels = load_labels()
    if 'tags' not in labels.columns:
        return []
    all_tags = []
    for tags_str in labels['tags'].dropna().astype(str):
        if tags_str.strip():
            all_tags.extend([t.strip() for t in tags_str.split(',') if t.strip()])
    return sorted(list(set(all_tags)))


@router.get("/analysis-chart")
def get_analysis_chart_data(
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    group_id: Optional[str] = Query(None),
):
    """
    Get data for analysis chart:
    - Actual transaction values (filtered by category/tag)
    - Reference/Interpolated values (filtered by group_id)
    """
    try:
        logger.debug("--- ANALYSIS CHART ---")
        logger.debug("Params: cat=%s tag=%s start=%s end=%s group=%s", category, tag, start_date, end_date, group_id)

        # 1. Actual Data
        df = load_data()
        if not df.empty:
            logger.debug("Loaded data: %s  range: %s - %s", df.shape, df['FECHA'].min(), df['FECHA'].max())
            logger.debug("2025 entries: %s", len(df[df['FECHA'].dt.year == 2025]))
        else:
            logger.debug("Loaded data is EMPTY")

        if start_date:
            df = df[df['FECHA'].dt.date >= pd.to_datetime(start_date).date()]
        if end_date:
            df = df[df['FECHA'].dt.date <= pd.to_datetime(end_date).date()]

        df = rules_service.apply_rules_to_dataframe(df)
        df = apply_filters(df, category=category, tag=tag)

        if not df.empty:
            logger.debug("Filtered data: %s  range: %s - %s", df.shape, df['FECHA'].min(), df['FECHA'].max())
        else:
            logger.debug("Filtered data is EMPTY")

        actual_series = []
        actual_df = pd.DataFrame(columns=['date', 'actual'])

        if not df.empty:
            daily_sum = df.groupby(df['FECHA'].dt.date)['MONTO'].sum()
            d_min = pd.to_datetime(start_date).date() if start_date else daily_sum.index.min()
            d_max = pd.to_datetime(end_date).date() if end_date else daily_sum.index.max()
            logger.debug("Plot range: %s - %s", d_min, d_max)

            if d_min and d_max:
                full_idx = pd.date_range(d_min, d_max).date
                daily_sum = daily_sum.reindex(full_idx, fill_value=0.0).cumsum()
                actual_df = pd.DataFrame({'date': daily_sum.index, 'actual': daily_sum.values})
                actual_series = [{"date": d.strftime('%Y-%m-%d'), "actual": v} for d, v in daily_sum.items()]

        # 2. Reference / Interpolated Data
        reference_series = []
        ref_df_final = pd.DataFrame(columns=['date', 'value'])

        if group_id:
            from contabilidad.backend.storage.variables_storage import InterpolationStorage
            from contabilidad.backend.services.bank_parser.get_variables import mark_fixed_payments
            from contabilidad.backend.services.data_merger.interpolar import interpolar_a_cero
            from contabilidad.models import Payment
            import numpy as np

            group = InterpolationStorage.get_group(group_id)
            payments = InterpolationStorage.get_payments(group_id)

            if group and payments:
                group_type = group.get('type', 'interpolated')

                if start_date and end_date:
                    dates = pd.date_range(start=start_date, end=end_date)
                else:
                    p_dates = [pd.to_datetime(p['start_date']) for p in payments]
                    p_dates.extend([pd.to_datetime(p['end_date']) for p in payments if p['end_date']])
                    if not p_dates:
                        p_dates = [datetime.now()]
                    min_d = min(p_dates) - pd.Timedelta(days=30)
                    max_d = max(p_dates) + pd.Timedelta(days=30) if len(p_dates) > 1 else min(p_dates) + pd.Timedelta(days=365)
                    dates = pd.date_range(start=min_d, end=max_d)

                ref_df = pd.DataFrame({'FECHA': dates}).sort_values('FECHA')
                col_name = "REFERENCE"

                if group_type == 'fixed':
                    pagos_obj = []
                    for p in payments:
                        s = pd.to_datetime(p['start_date'])
                        e = pd.to_datetime(p['end_date']) if p['end_date'] else None
                        pagos_obj.append(Payment(float(p['amount']), s, e))
                    ref_df = mark_fixed_payments(ref_df, pagos_obj, col_name)
                else:
                    ref_df[col_name] = np.nan
                    for p in payments:
                        target_date = pd.to_datetime(p['end_date'] if p['end_date'] else p['start_date'])
                        mask = ref_df['FECHA'] == target_date
                        if mask.any():
                            ref_df.loc[mask, col_name] = float(p['amount'])

                    try:
                        res_df = interpolar_a_cero(ref_df, col_name)
                        inter_col = f"{col_name} INTER"
                        if inter_col in res_df.columns:
                            ref_df = res_df.reset_index() if 'FECHA' not in res_df.columns else res_df
                            col_name = inter_col
                        else:
                            logger.warning("Interpolation column %s not found", inter_col)
                    except Exception as e:
                        logger.warning("Interpolation failed: %s", e)
                        ref_df[col_name] = ref_df[col_name].fillna(0)

                    if col_name in ref_df.columns:
                        ref_df[col_name] = ref_df[col_name] * -1

                ref_df['date'] = ref_df['FECHA'].dt.date
                ref_df['value'] = ref_df[col_name].fillna(0)
                ref_df_final = ref_df[['date', 'value']]
                reference_series = [
                    {"date": d.strftime('%Y-%m-%d'), "value": v}
                    for d, v in zip(ref_df['date'], ref_df['value'])
                ]

        # 3. Difference (Actual − Reference)
        difference_series = []
        if not actual_df.empty or not ref_df_final.empty:
            merged = pd.merge(actual_df, ref_df_final, on='date', how='outer', suffixes=('_act', '_ref')).sort_values('date')
            merged['actual'] = merged['actual'].ffill().fillna(0)
            merged['value'] = merged['value'].fillna(0)
            merged['diff'] = merged['actual'] - merged['value']
            difference_series = [
                {"date": d.strftime('%Y-%m-%d'), "diff": v}
                for d, v in zip(merged['date'], merged['diff'])
            ]

        return {
            "actual": actual_series,
            "reference": reference_series,
            "difference": difference_series,
            "meta": {"group_id": group_id, "range": [start_date, end_date]},
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Write endpoints ───────────────────────────────────────────────────────────

@router.put("/{transaction_id}")
def update_transaction(transaction_id: str, updates: TransactionUpdate):
    """Update a specific transaction's labels by its source_id."""
    source = load_source_data()
    if source.empty or transaction_id not in source['id'].values:
        raise HTTPException(status_code=404, detail=f"Transaction not found: {transaction_id}")

    source_row = source[source['id'] == transaction_id].iloc[0]
    source_type = source_row.get('TIPO', 'BANCA')
    original_desc = str(source_row['DESCRIPCION'])

    labels = load_labels()
    current_label_row = labels[labels['source_id'] == transaction_id]
    group_id = None
    if not current_label_row.empty:
        group_id = current_label_row.iloc[0].get('group_id')
        if pd.isna(group_id):
            group_id = None

    update_dict = updates.model_dump(exclude_unset=True)

    if group_id:
        logger.info("Updating group %s for transaction %s", group_id, transaction_id)
        propagate_group_update(group_id, update_dict)
    else:
        save_transaction_labels(transaction_id, update_dict, source_type)

    try:
        if 'nombre_limpio' in update_dict:
            new_name = update_dict['nombre_limpio']
            if new_name and str(new_name).strip() != original_desc.strip():
                rules_service.save_rule_map(original_desc, new_name)
    except Exception as e:
        logger.error("Error auto-saving rules: %s", e)

    return {"status": "updated", "id": transaction_id, "group_id": group_id, "updated_fields": list(update_dict.keys())}


@router.post("/bulk-update")
def bulk_update_transactions(req: BulkUpdateRequest):
    """
    Apply the same set of label updates to many transactions at once.

    By default only empty fields are written (`overwrite=False`); the caller can
    inspect `skipped_fields` in the response to see what was left untouched and
    re-send with `overwrite=True`.
    """
    if not req.transaction_ids:
        raise HTTPException(status_code=400, detail="No transaction IDs provided")

    update_dict = req.updates.model_dump(exclude_unset=True, exclude_none=True)
    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields to update")

    ids = expand_ids_with_groups(req.transaction_ids) if req.propagate_groups else req.transaction_ids

    source = load_source_data()
    source_types = {}
    if not source.empty:
        source_types = source.set_index('id')['TIPO'].to_dict()

    result = bulk_save_transaction_labels(
        ids,
        update_dict,
        overwrite=req.overwrite,
        tags_mode=req.tags_mode,
        source_types=source_types,
    )

    # Optionally persist the same attributes as a reusable rule.
    # The previous rule (or its absence) is snapshotted so undo can restore it.
    rules_saved = []
    rules_before = []
    if req.save_as_rule:
        rule_attrs = {
            k: v for k, v in update_dict.items()
            if k in ('categoria', 'prioridad', 'es_fijo', 'tags', 'nota')
        }
        if rule_attrs:
            existing_rules = rules_service.load_rules()
            for name in req.rule_entities or []:
                rules_before.append({
                    "type": "entity", "key": name,
                    "rule": existing_rules.get("entity_data", {}).get(name),
                })
                rules_service.save_entity_rule(name, rule_attrs)
                rules_saved.append({"type": "entity", "key": name})
            for tag in req.rule_tags or []:
                rules_before.append({
                    "type": "tag", "key": tag,
                    "rule": existing_rules.get("tag_data", {}).get(tag),
                })
                rules_service.save_tag_rule(
                    tag, {k: v for k, v in rule_attrs.items() if k != 'tags'}
                )
                rules_saved.append({"type": "tag", "key": tag})

    undo_id = undo_store.save_snapshot({
        "labels_before": result["before"],
        "rules_before": rules_before,
        "summary": {
            "updated": result["updated"],
            "applied_fields": result["applied_fields"],
            "fields": update_dict,
        },
    })

    logger.info(
        "Bulk update: %s transacciones, campos %s, overwrite=%s, undo=%s",
        result['updated'], list(update_dict.keys()), req.overwrite, undo_id,
    )
    return {
        "status": "updated",
        "requested": len(req.transaction_ids),
        "affected": len(ids),
        "updated": result["updated"],
        "applied_fields": result["applied_fields"],
        "skipped_fields": result["skipped_fields"],
        "rules_saved": rules_saved,
        "undo_id": undo_id,
    }


@router.post("/bulk-undo/{undo_id}")
def undo_bulk_update(undo_id: str):
    """Revert a previous bulk update, restoring labels and any rule it wrote."""
    snapshot = undo_store.load_snapshot(undo_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Esta operación ya no se puede deshacer (revertida o expirada)",
        )

    restored = restore_label_snapshot(snapshot.get("labels_before", []))

    rules_restored = 0
    for entry in snapshot.get("rules_before", []):
        previous = entry.get("rule")
        if entry["type"] == "entity":
            # Delete first: save_* merges, and the restored rule must be exact.
            rules_service.delete_entity_rule(entry["key"])
            if previous is not None:
                rules_service.save_entity_rule(entry["key"], previous)
        else:
            rules_service.delete_tag_rule(entry["key"])
            if previous is not None:
                rules_service.save_tag_rule(entry["key"], previous)
        rules_restored += 1

    undo_store.discard_snapshot(undo_id)
    logger.info("Undo %s: %s transacciones restauradas", undo_id, restored)

    return {"status": "reverted", "restored": restored, "rules_restored": rules_restored}


@router.post("/group")
def group_transactions_endpoint(req: GroupRequest):
    """Group multiple transactions together under a shared group_id."""
    if not req.transaction_ids:
        raise HTTPException(status_code=400, detail="No transaction IDs provided")

    new_group_id = str(uuid.uuid4())

    master_updates = {}
    if req.master_data:
        master_updates = req.master_data.model_dump(exclude_unset=True)
    else:
        first_id = req.transaction_ids[0]
        labels = load_labels()
        row = labels[labels['source_id'] == first_id]
        if not row.empty:
            for col in LABEL_COLUMNS:
                if col not in ['source_id', 'source_type', 'group_id'] and pd.notna(row.iloc[0].get(col)):
                    master_updates[col] = row.iloc[0][col]

    master_updates['group_id'] = new_group_id

    source = load_source_data()
    updated_count = 0
    for tid in req.transaction_ids:
        if tid in source['id'].values:
            stype = source[source['id'] == tid].iloc[0].get('TIPO', 'BANCA')
            save_transaction_labels(tid, master_updates, stype)
            updated_count += 1

    return {"status": "grouped", "group_id": new_group_id, "count": updated_count}


@router.post("/ungroup/{transaction_id}")
def ungroup_transaction(transaction_id: str):
    """Remove a transaction from its group."""
    save_transaction_labels(transaction_id, {"group_id": None})
    return {"status": "ungrouped", "id": transaction_id}


@router.post("/{transaction_id}/split")
def split_transaction_endpoint(transaction_id: str, req: SplitRequest):
    """Split a transaction into multiple parts."""
    source = load_source_data()
    if source.empty or transaction_id not in source['id'].values:
        raise HTTPException(status_code=404, detail=f"Transaction not found: {transaction_id}")

    source_row = source[source['id'] == transaction_id].iloc[0]
    source_type = source_row.get('TIPO', 'BANCA')

    new_label_rows = []
    for split_item in req.splits:
        row_dict = split_item.model_dump(exclude_unset=True)
        if 'monto' in row_dict:
            row_dict['monto_asignado'] = row_dict.pop('monto')
        new_label_rows.append(row_dict)

    save_transaction_split(transaction_id, new_label_rows, source_type)
    return {"status": "split", "id": transaction_id, "parts": len(new_label_rows)}
