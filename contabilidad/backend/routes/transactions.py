from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
import os
from datetime import datetime

router = APIRouter()

# Path to the new labels-only CSV (no FECHA/DESCRIPCION/MONTO/TIPO duplication)
LABELS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data','sistema' ,'etiquetado', 'etiquetas.csv'))

# Columns that live in the labels file
LABEL_COLUMNS = [
    'source_id',     # id from banca_unida or tarjeta_unida (or legacy_ prefix for old data)
    'source_type',   # 'BANCA' or 'TARJETA'
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
    'group_id',      # NEW: Common ID for grouped transactions
    'monto_asignado', # NEW: For split transactions
]

# Legacy column definitions removed


# --- Pydantic Models ---
class TransactionOut(BaseModel):
    id: str                          # = source_id (hash from pipeline)
    FECHA: str
    DESCRIPCION: str
    MONTO: float
    TIPO: Optional[str] = None       # 'BANCA' or 'TARJETA'
    nombre_limpio: Optional[str] = None
    categoria: Optional[str] = None
    tags: Optional[str] = None
    prioridad: Optional[str] = None
    es_fijo: Optional[bool] = False
    pertenece_a: Optional[str] = None
    es_reembolsable: Optional[bool] = False
    deudor: Optional[str] = None
    felicidad: Optional[int] = 0
    revisado: Optional[bool] = False
    nota: Optional[str] = None
    split_group_id: Optional[str] = None
    group_id: Optional[str] = None   # NEW

class TransactionUpdate(BaseModel):
    nombre_limpio: Optional[str] = None
    categoria: Optional[str] = None
    tags: Optional[str] = None
    prioridad: Optional[str] = None
    es_fijo: Optional[bool] = None
    pertenece_a: Optional[str] = None
    es_reembolsable: Optional[bool] = None
    deudor: Optional[str] = None
    felicidad: Optional[int] = None
    revisado: Optional[bool] = None
    nota: Optional[str] = None
    nota: Optional[str] = None
    group_id: Optional[str] = None   # Can be used to manually set/unset group
    monto_asignado: Optional[float] = None # For splits

class SplitItem(BaseModel):
    monto: float
    categoria: Optional[str] = None
    tags: Optional[str] = None
    nota: Optional[str] = None
    revisado: Optional[bool] = None
    nombre_limpio: Optional[str] = None
    prioridad: Optional[str] = None
    es_fijo: Optional[bool] = None
    pertenece_a: Optional[str] = None
    es_reembolsable: Optional[bool] = None
    deudor: Optional[str] = None
    felicidad: Optional[int] = None

class SplitRequest(BaseModel):
    splits: List[SplitItem]


class GroupRequest(BaseModel):
    transaction_ids: List[str]
    master_data: Optional[TransactionUpdate] = None


# --- Helper Functions ---

# --- Helper Functions ---

def _get_pipeline():
    """Get the global DataPipeline instance."""
    import sys
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    contabilidad_dir = os.path.dirname(backend_dir)
    project_root = os.path.dirname(contabilidad_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from contabilidad.backend.data_pipeline import get_pipeline
    return get_pipeline()


def load_source_data() -> pd.DataFrame:
    """
    Load all transaction data from banca + tarjeta via the pipeline.
    Returns a unified DataFrame with columns: id, FECHA, DESCRIPCION, MONTO, TIPO
    """
    pipeline = _get_pipeline()
    
    # Load banca
    banca = pipeline.get_banca_data()
    if not banca.empty:
        # Ensure required columns exist
        cols = ['id', 'FECHA', 'DESCRIPCION', 'MONTO']
        available_cols = [c for c in cols if c in banca.columns]
        
        if 'id' not in banca.columns:
            # Fallback if ID is missing (should not happen in prod ideally)
            print("Warning: 'id' column missing in banca data")
            banca['id'] = banca.apply(lambda x: str(hash(str(x.name) + str(x.get('FECHA')) + str(x.get('MONTO')))), axis=1)

        banca = banca[['id', 'FECHA', 'DESCRIPCION', 'MONTO']].copy()
        banca['TIPO'] = 'BANCA'
    
    #verificar ids repetidos bancas
    ids_repetidos = banca[banca.duplicated('id', keep=False)]['id'].unique()
    print("Warning: Duplicate IDs found in banca data:", ids_repetidos)
    
    # Load tarjeta
    tarjeta = pipeline.get_tarjeta_data()
    if not tarjeta.empty:
        # Ensure required columns exist
        if 'id' not in tarjeta.columns:
             # Fallback
             print("Warning: 'id' column missing in tarjeta data")
             tarjeta['id'] = tarjeta.apply(lambda x: str(hash(str(x.name) + str(x.get('FECHA')) + str(x.get('MONTO')))), axis=1)

        tarjeta = tarjeta[['id', 'FECHA', 'DESCRIPCION', 'MONTO']].copy()
        tarjeta['TIPO'] = 'TARJETA'
    
    #verificar ids repetidos tarjeta
    ids_repetidos = tarjeta[tarjeta.duplicated('id', keep=False)]['id'].unique()
    print("Warning: Duplicate IDs found in tarjeta data:", ids_repetidos)
    
    # Combine
    frames = [df for df in [banca, tarjeta] if not df.empty]
    if not frames:
        return pd.DataFrame(columns=['id', 'FECHA', 'DESCRIPCION', 'MONTO', 'TIPO'])
    
    combined = pd.concat(frames, ignore_index=True)
    combined['FECHA'] = pd.to_datetime(combined['FECHA'])

    #verificar ids repetidos combined
    # ids_repetidos = combined[combined.duplicated('id', keep=False)]['id'].unique()
    # print("Warning: Duplicate IDs found in combined data:", ids_repetidos)
    
    return combined


def load_labels() -> pd.DataFrame:
    """Load the labels CSV. Creates it if it doesn't exist."""
    if not os.path.exists(LABELS_PATH):
        # Create empty labels file
        df = pd.DataFrame(columns=LABEL_COLUMNS)
        save_labels(df)
        return df
    
    df = pd.read_csv(LABELS_PATH)
    
    # Ensure all expected columns exist
    for col in LABEL_COLUMNS:
        if col not in df.columns:
            df[col] = None
    
    # Deduplicate by source_id? 
    # NO. We now allow multiple rows per source_id to support SPLITS.
    # If a source_id appears multiple times, it means it has been split into multiple labels.
    
    # However, legacy data might have duplicates by accident. 
    # We assume from now on that duplicates are intentional splits.
    
    return df


def save_labels(df: pd.DataFrame):
    """Save the labels DataFrame to CSV."""
    os.makedirs(os.path.dirname(LABELS_PATH), exist_ok=True)
    
    if os.path.exists(LABELS_PATH):
        try:
            import shutil
            shutil.copy2(LABELS_PATH, LABELS_PATH + ".bak")
        except Exception:
            pass
            
    # Save only label columns
    cols_to_save = [c for c in LABEL_COLUMNS if c in df.columns]
    df[cols_to_save].to_csv(LABELS_PATH, index=False)


def load_data() -> pd.DataFrame:
    """
    Load merged transaction data:
      1. source data (from pipeline)
      2. LEFT JOIN labels (from etiquetas.csv) ON id = source_id
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
    
    # Merge source data with labels
    # We only care about labels that match existing source IDs
    merged = source.merge(
        labels,
        left_on='id',
        right_on='source_id',
        how='left',
        suffixes=('', '_label')
    )
    
    # Cleanup: remove auxiliary join columns and any duplicate columns from merge
    drop_cols = [c for c in merged.columns if c.endswith('_label')]
    drop_cols.extend(['source_id', 'source_type'])
    merged = merged.drop(columns=[c for c in drop_cols if c in merged.columns], errors='ignore')

    # SPLIT LOGIC: Override MONTO with monto_asignado if present
    if 'monto_asignado' in merged.columns:
        # If monto_asignado is not null/nan, use it. Otherwise keep original MONTO.
        
        # Careful: If we have multiple rows for same ID (splits), they SHOULD have monto_asignado.
        # If we have 1 row (no split), monto_asignado might be null.
        
        # We need to ensure types first
        merged['monto_asignado'] = pd.to_numeric(merged['monto_asignado'], errors='coerce')
        
        # Apply override
        merged['MONTO'] = merged['monto_asignado'].fillna(merged['MONTO'])

    return merged


def save_transaction_labels(transaction_id: str, updates: dict, source_type: str = 'BANCA'):
    """
    Save/update labels for a specific transaction.
    Only modifies the etiquetas.csv.
    """
    labels = load_labels()
    
    mask = labels['source_id'] == transaction_id
    
    if mask.any():
        # Update existing label row
        for key, value in updates.items():
            if key in LABEL_COLUMNS:
                labels.loc[mask, key] = value
    else:
        # Create new label row
        new_row = {col: None for col in LABEL_COLUMNS}
        new_row['source_id'] = transaction_id
        new_row['source_type'] = source_type
        for key, value in updates.items():
            if key in LABEL_COLUMNS:
                new_row[key] = value
        labels = pd.concat([labels, pd.DataFrame([new_row])], ignore_index=True)
    
    save_labels(labels)

def save_transaction_split(transaction_id: str, splits: List[dict], source_type: str = 'BANCA'):
    """
    Save a split: Delete ALL existing rows for this transaction_id and insert N new rows.
    """
    labels = load_labels()
    
    # 1. Remove existing rows for this ID
    labels = labels[labels['source_id'] != transaction_id]
    
    # 2. Add new rows
    new_rows = []
    for split in splits:
        row = {col: None for col in LABEL_COLUMNS}
        row['source_id'] = transaction_id
        row['source_type'] = source_type
        
        # Fill data
        for k, v in split.items():
            if k in LABEL_COLUMNS:
                row[k] = v
        new_rows.append(row)
        
    if new_rows:
        labels = pd.concat([labels, pd.DataFrame(new_rows)], ignore_index=True)
        
    save_labels(labels)


def propagate_group_update(group_id: str, updates: dict):
    """
    Update ALL transactions sharing the same group_id with the new values.
    """
    # Exclude group_id itself from propagation to avoid recursion/issues, unless specifically updating it?
    # Actually, we want to update labels. group_id is the key.
    
    labels = load_labels()
    
    # filters by group_id
    mask = labels['group_id'] == group_id
    
    if mask.any():
        for key, value in updates.items():
            if key in LABEL_COLUMNS and key != 'source_id': # Don't update ID
                 labels.loc[mask, key] = value
        
        save_labels(labels)


def sanitize_for_json(df: pd.DataFrame) -> pd.DataFrame:
    """Replace NaN values with appropriate defaults for JSON serialization."""
    df = df.copy()
    # String columns
    # String columns
    str_cols = ['DESCRIPCION', 'TIPO', 'nombre_limpio', 'categoria', 'tags', 'prioridad', 'pertenece_a', 'deudor', 'nota', 'split_group_id', 'id', 'group_id']

    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str)
    
    # Bool columns
    bool_cols = ['es_fijo', 'es_reembolsable', 'revisado']
    for col in bool_cols:
        if col in df.columns:
            # Fix FutureWarning: Avoid downcasting warning by using explicit assignment
            df.loc[df[col].isna(), col] = False
            df[col] = df[col].astype(bool)
    
    # Int columns
    if 'felicidad' in df.columns:
        df['felicidad'] = df['felicidad'].fillna(0).astype(int)
    
    # Float columns
    if 'MONTO' in df.columns:
        df['MONTO'] = df['MONTO'].fillna(0.0).astype(float)
        
    if 'monto_asignado' in df.columns:
        df['monto_asignado'] = df['monto_asignado'].fillna(0.0).astype(float)
    
    return df


# --- Filtering Helper ---
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
    tag: Optional[str] = None
) -> pd.DataFrame:
    """Helper function to apply common filters to transaction DataFrame."""
    print("Applying filters: ",f"date={date}, start_date={start_date}, end_date={end_date}, pending_only={pending_only}, es_reembolsable={es_reembolsable}, deudor={deudor}, search={search}, source_type={source_type}, category={category}, tag={tag}")
    
    if source_type:
        df = df[df['TIPO'].str.upper() == source_type.upper()]
    
    if date:
        try:
            filter_date = pd.to_datetime(date).date()
            df = df[df['FECHA'].dt.date == filter_date]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    
    if start_date:
        try:
            start = pd.to_datetime(start_date).date()
            df = df[df['FECHA'].dt.date >= start]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid start_date format: {e}")

    if end_date:
        try:
            end = pd.to_datetime(end_date).date()
            df = df[df['FECHA'].dt.date <= end]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid end_date format: {e}")
            
    if pending_only:
        df = df[df['revisado'] == False]

    if es_reembolsable is not None:
        if 'es_reembolsable' in df.columns:
             # Fix FutureWarning here too
             df.loc[df['es_reembolsable'].isna(), 'es_reembolsable'] = False
             df['es_reembolsable'] = df['es_reembolsable'].astype(bool)
             df = df[df['es_reembolsable'] == es_reembolsable]
        elif es_reembolsable:
             return df.iloc[0:0] # Return empty if column missing but requested true

    if deudor:
         if 'deudor' in df.columns:
             df['deudor'] = df['deudor'].fillna('').astype(str)
             df = df[df['deudor'].str.lower() == deudor.lower()]
         else:
             return df.iloc[0:0]
    
    if search:
        search_lower = search.lower()
        
        search_desc = df['DESCRIPCION'].fillna('').astype(str).str.lower()
        mask = search_desc.str.contains(search_lower, regex=False)
        
        if 'nombre_limpio' in df.columns:
            search_clean = df['nombre_limpio'].fillna('').astype(str).str.lower()
            mask |= search_clean.str.contains(search_lower, regex=False)
            
        if 'categoria' in df.columns:
            search_cat = df['categoria'].fillna('').astype(str).str.lower()
            mask |= search_cat.str.contains(search_lower, regex=False)
            
        if 'tags' in df.columns:
            search_tags = df['tags'].fillna('').astype(str).str.lower()
            mask |= search_tags.str.contains(search_lower, regex=False)

        df = df[mask]
    print("Filteres before category and tag: ",df.shape, f"Min Date: {df['FECHA'].min()}, Max Date: {df['FECHA'].max()}")

    if category:
        if 'categoria' in df.columns:
            df = df[df['categoria'] == category]
        else:
            return df.iloc[0:0]

    if tag:
        if 'tags' in df.columns:
            tag_search = tag.lower()
            tags_series = df['tags'].fillna('').astype(str).str.lower()
            df = df[tags_series.str.contains(tag_search, regex=False)]
        else:
            return df.iloc[0:0]
    print("Filteres after category and tag: ",df.shape, f"Min Date: {df['FECHA'].min()}, Max Date: {df['FECHA'].max()}")
            
    return df

# --- Endpoints ---

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
    tag: Optional[str] = Query(None, description="Filter by tag presence")
):
    """Get all transactions, optionally filtered by date, range, status, debtor, search term, category or tag."""
    df = load_data()
    
    if df.empty:
        return []

    # --- Apply Rules: Description Map ---
    # Try to fill empty 'nombre_limpio' from rules if available
    rules = load_rules()
    desc_map = rules.get("description_map", {})
    
    if desc_map:
        if 'nombre_limpio' not in df.columns:
            df['nombre_limpio'] = None
        
        descriptions = df['DESCRIPCION'].astype(str)
        mapped_names = descriptions.map(desc_map)
        df['nombre_limpio'] = df['nombre_limpio'].fillna(mapped_names)
        
        entity_data = rules.get("entity_data", {})
        tag_data = rules.get("tag_data", {})
        if entity_data or tag_data:
             if 'categoria' not in df.columns:
                 df['categoria'] = None
             
             def apply_entity_rule(row):
                 if pd.isna(row.get('categoria')) or row.get('categoria') == '' or row.get('categoria') == '---':
                     clean = row.get('nombre_limpio')
                     if clean and clean in entity_data:
                         rule = entity_data[clean]
                         if 'categoria' in rule: row['categoria'] = rule['categoria']
                         if 'tags' in rule and (pd.isna(row.get('tags')) or row.get('tags') == ''): row['tags'] = rule['tags']
                         if 'prioridad' in rule and (pd.isna(row.get('prioridad')) or row.get('prioridad') == ''): row['prioridad'] = rule['prioridad']
                         if 'es_fijo' in rule: row['es_fijo'] = rule['es_fijo']
                     
                     if pd.isna(row.get('categoria')) or row.get('categoria') == '' or row.get('categoria') == '---':
                         tags_str = row.get('tags')
                         if pd.notna(tags_str) and tags_str != '':
                             tags_list = [t.strip() for t in str(tags_str).split(',') if t.strip()]
                             for tag in tags_list:
                                 if tag in tag_data:
                                     rule = tag_data[tag]
                                     if 'categoria' in rule: row['categoria'] = rule['categoria']
                                     if 'prioridad' in rule and (pd.isna(row.get('prioridad')) or row.get('prioridad') == ''): row['prioridad'] = rule['prioridad']
                                     if 'es_fijo' in rule: row['es_fijo'] = rule['es_fijo']
                                     break
                         
                 return row

             df = df.apply(apply_entity_rule, axis=1)

    # Apply filters using helper
    df = apply_filters(
        df, 
        date=date,
        start_date=start_date,
        end_date=end_date,
        pending_only=pending_only,
        es_reembolsable=es_reembolsable,
        deudor=deudor,
        search=search,
        source_type=source_type,
        category=category,
        tag=tag
    )

    # Sanitize and convert
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
            filter_date = pd.to_datetime(date).date()
            df = df[df['FECHA'].dt.date == filter_date]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    
    total = float(df['MONTO'].sum()) if not df.empty else 0.0
    pending = int((df['revisado'] == False).sum()) if 'revisado' in df.columns else 0
    reviewed = int((df['revisado'] == True).sum()) if 'revisado' in df.columns else 0
    
    return {
        "total_monto": total,
        "count": len(df),
        "pending": pending,
        "reviewed": reviewed,
    }

@router.get("/categories")
def get_categories():
    """Get list of unique categories used in the data."""
    labels = load_labels()
    if 'categoria' not in labels.columns:
        return []
    categories = labels['categoria'].dropna().unique().tolist()
    categories = [c for c in categories if c and c not in ['---', 'Sin Categoría', '']]
    return sorted(categories)

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
    group_id: Optional[str] = Query(None)
):
    """
    Get data for analysis chart: 
    - Actual transaction values (filtered by category/tag)
    - Reference/Interpolated values (filtered by group_id)
    """
    try:
        print(f"--- DEBUG ANALYSIS CHART ---")
        print(f"Params: cat={category}, tag={tag}, start={start_date}, end={end_date}, group={group_id}")
        
        # 1. Get Actual Data
        df = load_data()
        if not df.empty:
            print(f"Loaded Data: {df.shape}, Range: {df['FECHA'].min()} to {df['FECHA'].max()}")
            # Check for 2025 data specifically
            df_2025 = df[df['FECHA'].dt.year == 2025]
            print(f"2025 Data entries: {len(df_2025)}")
        else:
            print("Loaded Data is EMPTY")
        
        # Apply strict date filtering for chart clarity
        if start_date:
            df = df[df['FECHA'].dt.date >= pd.to_datetime(start_date).date()]
        if end_date:
            df = df[df['FECHA'].dt.date <= pd.to_datetime(end_date).date()]

        # --- RULE APPLICATION (CRITICAL FOR FILTERING) ---
        # Apply rules to ensure categories/tags are populated for older data
        rules = load_rules()
        desc_map = rules.get("description_map", {})
        
        if desc_map:
            if 'nombre_limpio' not in df.columns:
                df['nombre_limpio'] = None
            
            descriptions = df['DESCRIPCION'].astype(str)
            mapped_names = descriptions.map(desc_map)
            df['nombre_limpio'] = df['nombre_limpio'].fillna(mapped_names)
            
            entity_data = rules.get("entity_data", {})
            tag_data = rules.get("tag_data", {})
            if entity_data or tag_data:
                    if 'categoria' not in df.columns:
                        df['categoria'] = None
                    
                    def apply_entity_rule(row):
                        if pd.isna(row.get('categoria')) or row.get('categoria') == '' or row.get('categoria') == '---':
                            clean = row.get('nombre_limpio')
                            if clean and clean in entity_data:
                                rule = entity_data[clean]
                                if 'categoria' in rule: row['categoria'] = rule['categoria']
                                if 'tags' in rule and (pd.isna(row.get('tags')) or row.get('tags') == ''): row['tags'] = rule['tags']
                                if 'prioridad' in rule and (pd.isna(row.get('prioridad')) or row.get('prioridad') == ''): row['prioridad'] = rule['prioridad']
                                if 'es_fijo' in rule: row['es_fijo'] = rule['es_fijo']
                            
                            if pd.isna(row.get('categoria')) or row.get('categoria') == '' or row.get('categoria') == '---':
                                tags_str = row.get('tags')
                                if pd.notna(tags_str) and tags_str != '':
                                    tags_list = [t.strip() for t in str(tags_str).split(',') if t.strip()]
                                    for tag in tags_list:
                                        if tag in tag_data:
                                            rule = tag_data[tag]
                                            if 'categoria' in rule: row['categoria'] = rule['categoria']
                                            if 'prioridad' in rule and (pd.isna(row.get('prioridad')) or row.get('prioridad') == ''): row['prioridad'] = rule['prioridad']
                                            if 'es_fijo' in rule: row['es_fijo'] = rule['es_fijo']
                                            break
                                
                        return row

                    df = df.apply(apply_entity_rule, axis=1)
        # ------------------------------------------------

        # Apply Category/Tag filters (Critical for "Actual" series)
        # We reuse apply_filters but only for relevant fields
        df = apply_filters(df, category=category, tag=tag)
        
        if not df.empty:
            print(f"Filtered Data: {df.shape}, Range: {df['FECHA'].min()} to {df['FECHA'].max()}")
            print(df)
        else:
            print("Filtered Data is EMPTY")

        actual_df = pd.DataFrame(columns=['date', 'actual'])
        if not df.empty:
            # Aggregate to daily
            daily_sum = df.groupby(df['FECHA'].dt.date)['MONTO'].sum()
            print(f"Daily Sum Start: {daily_sum.index.min()}, End: {daily_sum.index.max()}")
            
            # Determine range for plotting (align with requested or data range)
            d_min = pd.to_datetime(start_date).date() if start_date else daily_sum.index.min()
            d_max = pd.to_datetime(end_date).date() if end_date else daily_sum.index.max()
            
            print(f"Plot Range: {d_min} to {d_max}")
            
            if d_min and d_max:
                full_idx = pd.date_range(d_min, d_max).date
                daily_sum = daily_sum.reindex(full_idx, fill_value=0.0)
                
                # CUMULATIVE SUM
                daily_sum = daily_sum.cumsum()
                
                # Make DF for merging
                actual_df = pd.DataFrame({'date': daily_sum.index, 'actual': daily_sum.values})
                actual_series = [{"date": d.strftime('%Y-%m-%d'), "actual": v} for d, v in daily_sum.items()]
        
        # 2. Get Reference/Interpolated Data
        reference_series = []
        ref_df_final = pd.DataFrame(columns=['date', 'value'])
        
        if group_id:
            # Lazy imports
            from contabilidad.backend.storage import InterpolationStorage
            from contabilidad.cuenta.ObtenerVariables import marcar_fijos
            from contabilidad.union.interpolar import interpolar_a_cero
            from contabilidad.Modelos import PAGO
            import numpy as np
            
            # Fetch group and payments
            group = InterpolationStorage.get_group(group_id)
            payments = InterpolationStorage.get_payments(group_id)
            
            if group and payments:
                group_type = group.get('type', 'interpolated')
                
                # Determine date range for interpolation
                if start_date and end_date:
                    dates = pd.date_range(start=start_date, end=end_date)
                else:
                    # Fallback range logic
                    p_dates = [pd.to_datetime(p['start_date']) for p in payments]
                    p_dates.extend([pd.to_datetime(p['end_date']) for p in payments if p['end_date']])
                    if not p_dates:
                        p_dates = [datetime.now()]
                    
                    min_d = min(p_dates)
                    max_d = max(p_dates) if len(p_dates) > 1 else min_d + pd.Timedelta(days=365)
                    # Extend a bit
                    min_d = min_d - pd.Timedelta(days=30)
                    max_d = max_d + pd.Timedelta(days=30)
                    dates = pd.date_range(start=min_d, end=max_d)

                # Create base DF for reference
                ref_df = pd.DataFrame({'FECHA': dates})
                ref_df = ref_df.sort_values('FECHA')
                
                col_name = "REFERENCE"
                
                if group_type == 'fixed':
                    # Convert to PAGO objects
                    pagos_obj = []
                    for p in payments:
                        s = pd.to_datetime(p['start_date'])
                        e = pd.to_datetime(p['end_date']) if p['end_date'] else None
                        pagos_obj.append(PAGO(float(p['amount']), s, e))
                        
                    ref_df = marcar_fijos(ref_df, pagos_obj, col_name)
                    # User requested NO cumulative sum for Fixed payments
                    # ref_df[col_name] = ref_df[col_name].cumsum()
                    
                else: # interpolated
                    # Logic: interpolate between payments (Already cumulative-ish target)
                    ref_df[col_name] = np.nan
                    
                    for p in payments:
                        target_date = pd.to_datetime(p['end_date']) if p['end_date'] else pd.to_datetime(p['start_date'])
                        
                        # Find closest date in ref_df
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
                            print(f"Warning: Interpolation column {inter_col} not found")
                            
                    except Exception as e:
                        print(f"Interpolation failed: {e}")
                        ref_df[col_name] = ref_df[col_name].fillna(0) # Fallback
                        
                    # FLIP SIGN for Interpolated as requested
                    # "para las interpoladas, debes cambiar el signo"
                    if col_name in ref_df.columns:
                        ref_df[col_name] = ref_df[col_name] * -1

                # Extract result
                ref_df['date'] = ref_df['FECHA'].dt.date
                ref_df['value'] = ref_df[col_name].fillna(0)
                
                ref_df_final = ref_df[['date', 'value']]
                reference_series = [{"date": d.strftime('%Y-%m-%d'), "value": v} for d, v in zip(ref_df['date'], ref_df['value'])]

        # 3. Calculate Difference (Actual - Reference)
        difference_series = []
        if not actual_df.empty or not ref_df_final.empty:
            # Merge on date
            # Ensure "date" columns are same type (datetime.date)
            
            merged = pd.merge(
                actual_df, 
                ref_df_final, 
                on='date', 
                how='outer', 
                suffixes=('_act', '_ref')
            ).sort_values('date')
            
            # Forward Fill Actuals (as requested: "que en la ultima transaccion se quede en la posicion de la utima suma acumulada")
            merged['actual'] = merged['actual'].ffill().fillna(0)
            merged['value'] = merged['value'].fillna(0)
            
            merged['diff'] = merged['actual'] - merged['value']
            
            difference_series = [{"date": d.strftime('%Y-%m-%d'), "diff": v} for d, v in zip(merged['date'], merged['diff'])]


        return {
            "actual": actual_series,
            "reference": reference_series,
            "difference": difference_series,
            "meta": {
                "group_id": group_id,
                "range": [start_date, end_date]
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Rules Logic ---

import json

def get_rules_path():
    """Get absolute path to rules file."""
    return os.path.join(os.path.dirname(LABELS_PATH), 'rules.json')

def load_rules():
    path = get_rules_path()
    if not os.path.exists(path):
        return {"description_map": {}, "entity_data": {}, "tag_data": {}}
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            rules = json.load(f)
            if "tag_data" not in rules:
                rules["tag_data"] = {}
            return rules
    except Exception as e:
        print(f"Error loading rules: {e}")
        return {"description_map": {}, "entity_data": {}, "tag_data": {}}

def save_rules_file(rules_data):
    path = get_rules_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving rules: {e}")

class EntityRule(BaseModel):
    categoria: Optional[str] = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    prioridad: Optional[str] = ""
    es_fijo: Optional[bool] = False
    tags: Optional[str] = ""
    nota: Optional[str] = ""

class TagRule(BaseModel):
    categoria: Optional[str] = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    prioridad: Optional[str] = ""
    es_fijo: Optional[bool] = False
    nota: Optional[str] = ""

class MapRule(BaseModel):
    original: str
    clean: str

@router.get("/rules/entity/{name}")
def get_entity_rule(name: str):
    """Get entity rule for a given clean name."""
    rules = load_rules()
    entity_data = rules.get("entity_data", {})
    
    if name in entity_data:
        return entity_data[name]
    return {}

@router.post("/rules/entity")
def save_entity_rule(rule: EntityRule, name: str = Query(..., description="Clean name to save rule for")):
    """Manually save an entity rule."""
    rules = load_rules()
    if "entity_data" not in rules:
        rules["entity_data"] = {}
        
    rule_dict = rule.model_dump(exclude_unset=True)
    
    existing = rules["entity_data"].get(name, {})
    existing.update(rule_dict)
    rules["entity_data"][name] = existing
    
    save_rules_file(rules)
    return {"status": "saved", "name": name, "rule": existing}

def save_rule_map(original: str, clean: str):
    """
    Save a mapping rule: original description -> clean name.
    """
    rules = load_rules()
    if "description_map" not in rules:
        rules["description_map"] = {}
    
    # Only save/update if different to avoid unnecessary writes
    current = rules["description_map"].get(original)
    if current != clean:
        rules["description_map"][original] = clean
        save_rules_file(rules)
        print(f"Rule updated via save_rule_map: '{original}' -> '{clean}'")

@router.post("/rules/map")
def save_map_rule(rule: MapRule):
    """Manually save a description mapping rule."""
    save_rule_map(rule.original, rule.clean)
    return {"status": "saved", "original": rule.original, "clean": rule.clean}

@router.get("/rules/tag/{tag}")
def get_tag_rule(tag: str):
    """Get rule for a given tag."""
    rules = load_rules()
    tag_data = rules.get("tag_data", {})
    
    if tag in tag_data:
        return tag_data[tag]
    return {}

@router.post("/rules/tag")
def save_tag_rule(rule: TagRule, tag: str = Query(..., description="Tag to save rule for")):
    """Manually save a tag rule."""
    rules = load_rules()
    if "tag_data" not in rules:
        rules["tag_data"] = {}
        
    rule_dict = rule.model_dump(exclude_unset=True)
    
    existing = rules["tag_data"].get(tag, {})
    existing.update(rule_dict)
    rules["tag_data"][tag] = existing
    
    save_rules_file(rules)
    return {"status": "saved", "tag": tag, "rule": existing}

# Update transaction - now only writes to etiquetas.csv
@router.put("/{transaction_id}")
def update_transaction(transaction_id: str, updates: TransactionUpdate):
    """Update a specific transaction's labels by its source_id."""
    
    # Verify the transaction exists in source data
    source = load_source_data()
    if source.empty or transaction_id not in source['id'].values:
        raise HTTPException(status_code=404, detail=f"Transaction not found: {transaction_id}")
    
    # Determine source type
    source_row = source[source['id'] == transaction_id].iloc[0]
    source_type = source_row.get('TIPO', 'BANCA')
    original_desc = str(source_row['DESCRIPCION'])
    
    # Load labels to check for existing group_id
    labels = load_labels()
    current_label_row = labels[labels['source_id'] == transaction_id]
    group_id = None
    if not current_label_row.empty:
        group_id = current_label_row.iloc[0].get('group_id')
        if pd.isna(group_id): group_id = None

    # Apply updates to labels only
    update_dict = updates.model_dump(exclude_unset=True)
    
    if group_id:
        # If part of a group, update ALL members
        print(f"Updating group {group_id} for transaction {transaction_id}")
        propagate_group_update(group_id, update_dict)
    else:
        # Just update this one
        save_transaction_labels(transaction_id, update_dict, source_type)
    
    # --- Auto-save Rules Logic ---
    try:
        # LOAD RULES FRESH
        rules = load_rules()
        
        # 1. Update Description Map if name changed/provided
        if 'nombre_limpio' in update_dict:
            new_name = update_dict['nombre_limpio']
            if new_name and str(new_name).strip() != original_desc.strip():
                 # Verify if we changed the name (user request: verify => save rule)
                 save_rule_map(original_desc, new_name)
                 # Reload rules after saving map
                 rules = load_rules()
            
    except Exception as e:
        print(f"Error auto-saving rules: {e}")
    
    return {"status": "updated", "id": transaction_id, "group_id": group_id, "updated_fields": list(update_dict.keys())}


@router.post("/group")
def group_transactions_endpoint(req: GroupRequest):
    """
    Group multiple transactions together.
    They will share a generated group_id and all label attributes.
    """
    import uuid
    
    if not req.transaction_ids:
        raise HTTPException(status_code=400, detail="No transaction IDs provided")
        
    new_group_id = str(uuid.uuid4())
    
    # Determine master data
    master_updates = {}
    if req.master_data:
        master_updates = req.master_data.model_dump(exclude_unset=True)
    else:
        # Use first transaction's existing labels as base if not provided
        first_id = req.transaction_ids[0]
        labels = load_labels()
        row = labels[labels['source_id'] == first_id]
        if not row.empty:
            # Extract relevant columns
            for col in LABEL_COLUMNS:
                if col not in ['source_id', 'source_type', 'group_id'] and pd.notna(row.iloc[0].get(col)):
                    master_updates[col] = row.iloc[0][col]

    # Ensure group_id is set
    master_updates['group_id'] = new_group_id
    
    # Apply to all
    source = load_source_data() # To check existence and get types
    
    updated_count = 0
    for tid in req.transaction_ids:
        if tid in source['id'].values:
            # get type
            stype = source[source['id'] == tid].iloc[0].get('TIPO', 'BANCA')
            save_transaction_labels(tid, master_updates, stype)
            updated_count += 1
            
    return {"status": "grouped", "group_id": new_group_id, "count": updated_count}

@router.post("/ungroup/{transaction_id}")
def ungroup_transaction(transaction_id: str):
    """Remove a transaction from its group."""
    save_transaction_labels(transaction_id, {"group_id": None}) # Set to None/Null
    return {"status": "ungrouped", "id": transaction_id}


@router.post("/{transaction_id}/split")
def split_transaction_endpoint(transaction_id: str, req: SplitRequest):
    """
    Split a transaction into multiple parts (rows).
    """
    # Verify existance
    source = load_source_data()
    if source.empty or transaction_id not in source['id'].values:
        raise HTTPException(status_code=404, detail=f"Transaction not found: {transaction_id}")

    source_row = source[source['id'] == transaction_id].iloc[0]
    source_type = source_row.get('TIPO', 'BANCA')
    
    # Build list of dicts for the new label rows
    # We need to preserve current 'nombre_limpio' if not provided? 
    # Usually split implies we are defining everything new or inheriting.
    
    # Let's verify total amount matches? (Optional, maybe just warn or trust frontend)
    # user logic: "cada una con un monto diferente dividido"
    
    new_label_rows = []
    
    # Need to know the base name/details? 
    # If the user splits, they probably send detailed info for each split.
    # If they only send amount, we inherit from original description?
    
    for split_item in req.splits:
        # Create a label row dict
        row_dict = split_item.model_dump(exclude_unset=True)
        # Map 'monto' to 'monto_asignado'
        if 'monto' in row_dict:
            row_dict['monto_asignado'] = row_dict.pop('monto')
            
        # Inherit defaults if missing?
        if 'nombre_limpio' not in row_dict:
             # Default to existing logic? 
             # Maybe the frontend sends everything explicit.
             pass
             
        new_label_rows.append(row_dict)
        
    save_transaction_split(transaction_id, new_label_rows, source_type)
    
    return {"status": "split", "id": transaction_id, "parts": len(new_label_rows)}


