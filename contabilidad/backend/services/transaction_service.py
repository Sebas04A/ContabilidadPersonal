"""
Transaction Service
===================
Centralizes all data-access logic for transactions:
- Loading source data (banca + tarjeta via pipeline)
- Loading/saving labels (etiquetas.csv)
- Split and group operations
- Filter helper
"""

import os
import shutil
import uuid
import pandas as pd
from typing import Optional, List
from fastapi import HTTPException

from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

# ── Paths & Constants ────────────────────────────────────────────────────────

from contabilidad.config import PATH_DATA
LABELS_PATH = os.path.join(PATH_DATA, 'sistema', 'etiquetado', 'etiquetas.csv')

LABEL_COLUMNS = [
    'source_id',      # id from banca_unida or tarjeta_unida
    'source_type',    # 'BANCA' or 'TARJETA'
    'nombre_limpio',
    'categoria',
    'tags',
    'prioridad',
    'es_fijo',
    'pertenece_a',
    'es_reembolsable',
    'deudor',
    'felicidad',
    'revisado',
    'nota',
    'split_group_id',
    'group_id',       # Common ID for grouped transactions
    'monto_asignado', # For split transactions
    'fondo_id',       # Fund (interpolaciones group) this transaction belongs to
    'deuda_id',       # Linked Supabase debt id (when refundable + associated/created)
]


# ── Pipeline helper ───────────────────────────────────────────────────────────

def _get_pipeline():
    """Return the global DataPipeline instance (lazy import to avoid circular deps)."""
    from contabilidad.backend.storage.data_pipeline import get_pipeline
    return get_pipeline()


# ── Source data ───────────────────────────────────────────────────────────────

def load_source_data() -> pd.DataFrame:
    """
    Load all transaction data from banca + tarjeta via the pipeline.
    Returns a unified DataFrame with columns: id, FECHA, DESCRIPCION, MONTO, TIPO.
    """
    pipeline = _get_pipeline()

    # --- Banca ---
    banca = pipeline.get_bank_data()
    if not banca.empty:
        if 'id' not in banca.columns:
            logger.warning("'id' column missing in banca data")
            banca['id'] = banca.apply(
                lambda x: str(hash(str(x.name) + str(x.get('FECHA')) + str(x.get('MONTO')))), axis=1
            )
        banca = banca[['id', 'FECHA', 'DESCRIPCION', 'MONTO']].copy()
        banca['TIPO'] = 'BANCA'

        ids_dup = banca[banca.duplicated('id', keep=False)]['id'].unique()
        if len(ids_dup) > 0:
            logger.warning("Duplicate IDs found in banca data: %s", ids_dup.tolist())

    # --- Tarjeta ---
    tarjeta = pipeline.get_credit_card_data()
    if not tarjeta.empty:
        if 'id' not in tarjeta.columns:
            logger.warning("'id' column missing in tarjeta data")
            tarjeta['id'] = tarjeta.apply(
                lambda x: str(hash(str(x.name) + str(x.get('FECHA')) + str(x.get('MONTO')))), axis=1
            )
        tarjeta = tarjeta[['id', 'FECHA', 'DESCRIPCION', 'MONTO']].copy()
        tarjeta['TIPO'] = 'TARJETA'

        ids_dup = tarjeta[tarjeta.duplicated('id', keep=False)]['id'].unique()
        if len(ids_dup) > 0:
            logger.warning("Duplicate IDs found in tarjeta data: %s", ids_dup.tolist())

    frames = [df for df in [banca, tarjeta] if not df.empty]
    if not frames:
        return pd.DataFrame(columns=['id', 'FECHA', 'DESCRIPCION', 'MONTO', 'TIPO'])

    combined = pd.concat(frames, ignore_index=True)
    combined['FECHA'] = pd.to_datetime(combined['FECHA'])
    return combined


# ── Labels I/O ────────────────────────────────────────────────────────────────

def load_labels() -> pd.DataFrame:
    """Load the labels CSV. Creates it if it doesn't exist."""
    if not os.path.exists(LABELS_PATH):
        df = pd.DataFrame(columns=LABEL_COLUMNS)
        save_labels(df)
        return df

    df = pd.read_csv(LABELS_PATH)
    for col in LABEL_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df


def save_labels(df: pd.DataFrame) -> None:
    """Persist the labels DataFrame to CSV (with backup)."""
    os.makedirs(os.path.dirname(LABELS_PATH), exist_ok=True)

    if os.path.exists(LABELS_PATH):
        try:
            shutil.copy2(LABELS_PATH, LABELS_PATH + ".bak")
        except Exception:
            pass

    cols_to_save = [c for c in LABEL_COLUMNS if c in df.columns]
    df[cols_to_save].to_csv(LABELS_PATH, index=False)


# ── Merged data ───────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    """
    Return source data LEFT-JOINed with labels on id = source_id.
    Handles split logic (monto_asignado overrides MONTO when present).
    """
    source = load_source_data()
    labels = load_labels()

    if source.empty:
        return pd.DataFrame()

    if labels.empty:
        merged = source.copy()
        for col in LABEL_COLUMNS:
            if col not in ('source_id', 'source_type') and col not in merged.columns:
                merged[col] = None
        return merged

    merged = source.merge(
        labels,
        left_on='id',
        right_on='source_id',
        how='left',
        suffixes=('', '_label')
    )

    drop_cols = [c for c in merged.columns if c.endswith('_label')]
    drop_cols.extend(['source_id', 'source_type'])
    merged = merged.drop(columns=[c for c in drop_cols if c in merged.columns], errors='ignore')

    if 'monto_asignado' in merged.columns:
        merged['monto_asignado'] = pd.to_numeric(merged['monto_asignado'], errors='coerce')
        merged['MONTO'] = merged['monto_asignado'].fillna(merged['MONTO'])

    return merged


# ── Label mutations ───────────────────────────────────────────────────────────

def _safe_set(df: pd.DataFrame, mask, key: str, value) -> None:
    """
    Assign a value to df.loc[mask, key] without pandas dtype errors.
    An all-NaN column is inferred as float64; assigning a string to it raises
    (pandas >= 2.1). Cast the column to object first when writing a string.
    """
    if key not in df.columns:
        df[key] = None
    if isinstance(value, str) and df[key].dtype != object:
        df[key] = df[key].astype(object)
    df.loc[mask, key] = value


def save_transaction_labels(transaction_id: str, updates: dict, source_type: str = 'BANCA') -> None:
    """Upsert labels for a single transaction."""
    labels = load_labels()
    mask = labels['source_id'] == transaction_id

    if mask.any():
        for key, value in updates.items():
            if key in LABEL_COLUMNS:
                _safe_set(labels, mask, key, value)
    else:
        new_row = {col: None for col in LABEL_COLUMNS}
        new_row['source_id'] = transaction_id
        new_row['source_type'] = source_type
        for key, value in updates.items():
            if key in LABEL_COLUMNS:
                new_row[key] = value
        labels = pd.concat([labels, pd.DataFrame([new_row])], ignore_index=True)

    save_labels(labels)


# Columnas donde el valor "apagado" (False / 0) equivale a no haber sido
# etiquetado nunca, no a una decisión del usuario.
FALSY_AS_EMPTY_COLUMNS = ('es_fijo', 'revisado', 'es_reembolsable', 'felicidad')


def is_empty_label(val, column: Optional[str] = None) -> bool:
    """True si el valor cuenta como 'vacío' para efectos de etiquetado."""
    if val is None:
        return True
    try:
        if pd.isna(val):
            return True
    except (TypeError, ValueError):
        pass

    text = str(val).strip()
    if column in FALSY_AS_EMPTY_COLUMNS and text in ('False', 'false', '0', '0.0'):
        return True
    return text in ('', 'nan', 'None', '---', 'Sin Categoría')


def _merge_tags(current, incoming: str) -> str:
    """Une tags existentes con los nuevos, sin duplicar y preservando el orden."""
    result: List[str] = []
    for chunk in (current, incoming):
        if is_empty_label(chunk):
            continue
        for tag in str(chunk).split(','):
            tag = tag.strip()
            if tag and tag not in result:
                result.append(tag)
    return ', '.join(result)


def bulk_save_transaction_labels(
    transaction_ids: List[str],
    updates: dict,
    overwrite: bool = False,
    tags_mode: str = 'append',
    source_types: Optional[dict] = None,
) -> dict:
    """
    Aplica el mismo conjunto de updates a muchas transacciones en una sola
    lectura/escritura del CSV de etiquetas.

    overwrite=False  → un campo solo se escribe si el valor actual está vacío.
    tags_mode='append' → los tags nuevos se suman a los existentes en vez de
                         reemplazarlos (ignora `overwrite` para ese campo).

    Retorna {'updated': n, 'skipped_fields': {…}, 'applied_fields': {…},
             'before': [...]}, donde `before` es el snapshot necesario para
    deshacer la operación.
    """
    updates = {k: v for k, v in updates.items() if k in LABEL_COLUMNS}
    if not transaction_ids or not updates:
        return {"updated": 0, "skipped_fields": {}, "applied_fields": {}, "before": []}

    source_types = source_types or {}
    labels = load_labels()
    skipped: dict = {}
    applied: dict = {}
    updated_ids = set()
    new_rows = []
    before: List[dict] = []

    for tid in transaction_ids:
        mask = labels['source_id'] == tid

        if not mask.any():
            row = {col: None for col in LABEL_COLUMNS}
            row['source_id'] = tid
            row['source_type'] = source_types.get(tid, 'BANCA')
            for key, value in updates.items():
                row[key] = _merge_tags(None, value) if key == 'tags' and tags_mode == 'append' else value
                applied[key] = applied.get(key, 0) + 1
            new_rows.append(row)
            updated_ids.add(tid)
            # Undo de una fila creada = eliminarla.
            before.append({"source_id": tid, "created": True, "values": {}})
            continue

        previous: dict = {}
        for key, value in updates.items():
            current = labels.loc[mask, key].iloc[0] if key in labels.columns else None

            if key == 'tags' and tags_mode == 'append':
                _safe_set(labels, mask, key, _merge_tags(current, str(value)))
            elif overwrite or is_empty_label(current, key):
                _safe_set(labels, mask, key, value)
            else:
                skipped[key] = skipped.get(key, 0) + 1
                continue

            previous[key] = None if (current is None or pd.isna(current)) else current
            applied[key] = applied.get(key, 0) + 1
            updated_ids.add(tid)

        if previous:
            before.append({"source_id": tid, "created": False, "values": previous})

    if new_rows:
        labels = pd.concat([labels, pd.DataFrame(new_rows)], ignore_index=True)

    save_labels(labels)
    return {
        "updated": len(updated_ids),
        "skipped_fields": skipped,
        "applied_fields": applied,
        "before": before,
    }


def restore_label_snapshot(before: List[dict]) -> int:
    """
    Revierte una operación masiva: repone los valores previos y elimina las
    filas de etiquetas que la operación había creado desde cero.
    """
    if not before:
        return 0

    labels = load_labels()
    created_ids = [e['source_id'] for e in before if e.get('created')]
    restored = 0

    for entry in before:
        if entry.get('created'):
            continue
        mask = labels['source_id'] == entry['source_id']
        if not mask.any():
            continue
        for key, value in entry.get('values', {}).items():
            if key in LABEL_COLUMNS:
                _safe_set(labels, mask, key, value)
        restored += 1

    if created_ids:
        labels = labels[~labels['source_id'].isin(created_ids)]
        restored += len(created_ids)

    save_labels(labels)
    return restored


def expand_ids_with_groups(transaction_ids: List[str]) -> List[str]:
    """Añade a la selección todas las transacciones que comparten group_id."""
    labels = load_labels()
    if labels.empty or 'group_id' not in labels.columns:
        return list(transaction_ids)

    selected = set(transaction_ids)
    groups = labels[labels['source_id'].isin(selected)]['group_id'].dropna()
    groups = {g for g in groups if not is_empty_label(g)}
    if groups:
        selected |= set(labels[labels['group_id'].isin(groups)]['source_id'].dropna())
    return list(selected)


def save_transaction_split(transaction_id: str, splits: List[dict], source_type: str = 'BANCA') -> None:
    """Replace all rows for a transaction_id with the given split rows."""
    labels = load_labels()
    labels = labels[labels['source_id'] != transaction_id]

    new_rows = []
    for split in splits:
        row = {col: None for col in LABEL_COLUMNS}
        row['source_id'] = transaction_id
        row['source_type'] = source_type
        for k, v in split.items():
            if k in LABEL_COLUMNS:
                row[k] = v
        # Give each part a stable id so a fund can be assigned to a single part.
        if not row.get('split_group_id'):
            row['split_group_id'] = str(uuid.uuid4())
        new_rows.append(row)

    if new_rows:
        labels = pd.concat([labels, pd.DataFrame(new_rows)], ignore_index=True)

    save_labels(labels)


def backfill_split_group_ids() -> int:
    """
    One-time migration: give every split part (source_id with >1 label row) a
    unique split_group_id when it lacks one, so funds can target a single part.
    Returns the number of rows updated.
    """
    labels = load_labels()
    if labels.empty or 'split_group_id' not in labels.columns:
        return 0

    labels['split_group_id'] = labels['split_group_id'].astype(object)
    counts = labels['source_id'].value_counts()
    multi_ids = set(counts[counts > 1].index)

    updated = 0
    for idx, row in labels.iterrows():
        if row['source_id'] in multi_ids:
            sgid = row.get('split_group_id')
            if sgid is None or (isinstance(sgid, float) and pd.isna(sgid)) or str(sgid).strip() in ('', 'nan'):
                labels.at[idx, 'split_group_id'] = str(uuid.uuid4())
                updated += 1

    if updated:
        save_labels(labels)
    return updated


def set_fondo_for_part(source_id: str, split_group_id: Optional[str], value: str) -> bool:
    """
    Assign/unassign a fund on a single transaction OR a single split part.
    When split_group_id is given, only that part's label row is touched;
    otherwise the whole transaction (all its rows) is affected.
    """
    labels = load_labels()
    mask = labels['source_id'] == source_id
    if split_group_id:
        mask = mask & (labels['split_group_id'].astype(str) == str(split_group_id))
    if not mask.any():
        return False
    _safe_set(labels, mask, 'fondo_id', value)
    save_labels(labels)
    return True


def propagate_group_update(group_id: str, updates: dict) -> None:
    """Apply updates to ALL transactions sharing the given group_id."""
    labels = load_labels()
    mask = labels['group_id'] == group_id

    if mask.any():
        for key, value in updates.items():
            if key in LABEL_COLUMNS and key != 'source_id':
                _safe_set(labels, mask, key, value)
        save_labels(labels)


# ── Filter helper ─────────────────────────────────────────────────────────────

def apply_filters(
    df: pd.DataFrame,
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    pending_only: bool = False,
    es_reembolsable: Optional[bool] = None,
    deudor: Optional[str] = None,
    search: Optional[str] = None,
    source_type: Optional[str] = None,
    category: Optional[str] = None,
    tag: Optional[str] = None,
    fondo_id: Optional[str] = None,
) -> pd.DataFrame:
    """Apply common filters to a transaction DataFrame."""
    logger.debug(
        "Applying filters: date=%s start=%s end=%s pending=%s source=%s category=%s tag=%s",
        date, start_date, end_date, pending_only, source_type, category, tag,
    )

    if source_type:
        df = df[df['TIPO'].str.upper() == source_type.upper()]

    if date:
        try:
            df = df[df['FECHA'].dt.date == pd.to_datetime(date).date()]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    if start_date:
        try:
            df = df[df['FECHA'].dt.date >= pd.to_datetime(start_date).date()]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid start_date format: {e}")

    if end_date:
        try:
            df = df[df['FECHA'].dt.date <= pd.to_datetime(end_date).date()]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid end_date format: {e}")

    if pending_only:
        df = df[df['revisado'] == False]

    if es_reembolsable is not None:
        if 'es_reembolsable' in df.columns:
            df.loc[df['es_reembolsable'].isna(), 'es_reembolsable'] = False
            df['es_reembolsable'] = df['es_reembolsable'].astype(bool)
            df = df[df['es_reembolsable'] == es_reembolsable]
        elif es_reembolsable:
            return df.iloc[0:0]

    if deudor:
        if 'deudor' in df.columns:
            df['deudor'] = df['deudor'].fillna('').astype(str)
            df = df[df['deudor'].str.lower() == deudor.lower()]
        else:
            return df.iloc[0:0]

    if search:
        search_lower = search.lower()
        mask = df['DESCRIPCION'].fillna('').astype(str).str.lower().str.contains(search_lower, regex=False)
        for col in ('nombre_limpio', 'categoria', 'tags'):
            if col in df.columns:
                mask |= df[col].fillna('').astype(str).str.lower().str.contains(search_lower, regex=False)
        df = df[mask]

    logger.debug("Rows before cat/tag filter: %s  range: %s - %s", df.shape, df['FECHA'].min(), df['FECHA'].max())

    if category:
        if 'categoria' in df.columns:
            df = df[df['categoria'] == category]
        else:
            return df.iloc[0:0]

    if tag:
        if 'tags' in df.columns:
            df = df[df['tags'].fillna('').astype(str).str.lower().str.contains(tag.lower(), regex=False)]
        else:
            return df.iloc[0:0]

    if fondo_id:
        if 'fondo_id' in df.columns:
            df = df[df['fondo_id'].fillna('').astype(str) == str(fondo_id)]
        else:
            return df.iloc[0:0]

    logger.debug("Rows after cat/tag filter: %s  range: %s - %s", df.shape, df['FECHA'].min(), df['FECHA'].max())
    return df
