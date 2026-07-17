import pandas as pd
import os
import uuid
import shutil
from typing import List, Dict, Any, Optional
from datetime import date, datetime

from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

# Define paths
from contabilidad.config import PATH_DATA
BASE_DATA_PATH = os.path.join(PATH_DATA, 'sistema', 'interpolaciones')

GROUPS_FILE = os.path.join(BASE_DATA_PATH, 'grupos.csv')
PAYMENTS_FILE = os.path.join(BASE_DATA_PATH, 'pagos.csv')

# Full schema for groups. New columns are appended automatically by read_csv for
# backward compatibility with older grupos.csv files.
# `fondo_origen` links a generated payments group back to the fund (fund id) it was
# materialized from, so re-generating can find and replace it idempotently.
GROUP_COLUMNS = ['id', 'name', 'description', 'type', 'es_fondo', 'fecha_inicio', 'saldo_inicial', 'tag_vinculado', 'fondo_origen']


def _normalize_group(row: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce a raw group record into clean, JSON-friendly types."""
    es_fondo = row.get('es_fondo')
    if isinstance(es_fondo, str):
        es_fondo_bool = es_fondo.strip().lower() in ('true', '1', 'yes', 'si', 'sí')
    else:
        es_fondo_bool = bool(es_fondo) if es_fondo is not None else False

    saldo = row.get('saldo_inicial')
    try:
        if saldo is None or (isinstance(saldo, float) and pd.isna(saldo)) or str(saldo).strip() == '':
            saldo_val = 0.0
        else:
            saldo_val = float(saldo)
            if pd.isna(saldo_val):
                saldo_val = 0.0
    except (ValueError, TypeError):
        saldo_val = 0.0

    def _clean_str(value, default=''):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        s = str(value).strip()
        return default if s == '' or s.lower() == 'nan' else s

    fecha_raw = _clean_str(row.get('fecha_inicio'), '')
    fecha_val = fecha_raw[:10] if fecha_raw else None

    return {
        'id': row.get('id'),
        'name': _clean_str(row.get('name')),
        'description': _clean_str(row.get('description')),
        'type': _clean_str(row.get('type'), 'interpolated'),
        'es_fondo': es_fondo_bool,
        'fecha_inicio': fecha_val,
        'saldo_inicial': saldo_val,
        'tag_vinculado': _clean_str(row.get('tag_vinculado')) or None,
        'fondo_origen': _clean_str(row.get('fondo_origen')) or None,
    }

def ensure_data_dir():
    if not os.path.exists(BASE_DATA_PATH):
        os.makedirs(BASE_DATA_PATH)

def read_csv(file_path: str, columns: List[str]) -> pd.DataFrame:
    ensure_data_dir()
    if not os.path.exists(file_path):
        return pd.DataFrame(columns=columns)
    try:
        df = pd.read_csv(file_path)
        # Ensure all columns exist
        for col in columns:
            if col not in df.columns:
                df[col] = None
        
        # Replace NaN with None for JSON/Pydantic compatibility
        # Using apply/map is more robust than where() for object/float mix
        for col in df.columns:
            df[col] = df[col].apply(lambda x: None if pd.isna(x) else x)
        
        return df
    except Exception as e:
        logger.error("Error leyendo %s: %s", file_path, e)
        return pd.DataFrame(columns=columns)

def save_csv(df: pd.DataFrame, file_path: str):
    ensure_data_dir()
    if os.path.exists(file_path):
        try:
            shutil.copy2(file_path, file_path + ".bak")
        except Exception:
            pass
    df.to_csv(file_path, index=False)

class InterpolationStorage:
    @staticmethod
    def get_groups(type_filter: str = 'interpolated', fund_only: bool = False) -> List[Dict[str, Any]]:
        df = read_csv(GROUPS_FILE, GROUP_COLUMNS)
        # Backward compatibility: treat None/NaN type as 'interpolated'
        if 'type' in df.columns:
            df['type'] = df['type'].fillna('interpolated')

        if type_filter:
            df = df[df['type'] == type_filter]

        groups = [_normalize_group(r) for r in df.to_dict('records')]
        if fund_only:
            groups = [g for g in groups if g['es_fondo']]
        return groups

    @staticmethod
    def get_groups_by_fondo_origen(fund_id: str) -> List[Dict[str, Any]]:
        """Every group generated (materialized) from the given fund."""
        df = read_csv(GROUPS_FILE, GROUP_COLUMNS)
        if 'fondo_origen' not in df.columns:
            return []
        df = df[df['fondo_origen'].fillna('').astype(str) == str(fund_id)]
        return [_normalize_group(r) for r in df.to_dict('records')]

    @staticmethod
    def get_group(group_id: str) -> Optional[Dict[str, Any]]:
        df = read_csv(GROUPS_FILE, GROUP_COLUMNS)
        group = df[df['id'] == group_id]
        if group.empty:
            return None
        return _normalize_group(group.iloc[0].to_dict())

    @staticmethod
    def create_group(name: str, description: str = None, group_type: str = 'interpolated',
                     es_fondo: bool = False, fecha_inicio: Optional[str] = None,
                     saldo_inicial: Optional[float] = None,
                     tag_vinculado: Optional[str] = None,
                     fondo_origen: Optional[str] = None) -> Dict[str, Any]:
        ensure_data_dir()
        new_id = str(uuid.uuid4())
        new_row = {
            'id': new_id, 'name': name, 'description': description, 'type': group_type,
            'es_fondo': bool(es_fondo),
            'fecha_inicio': str(fecha_inicio)[:10] if fecha_inicio else None,
            'saldo_inicial': saldo_inicial if saldo_inicial is not None else 0.0,
            'tag_vinculado': tag_vinculado or None,
            'fondo_origen': fondo_origen or None,
        }

        # Read existing (to guarantee full/consistent columns) then append.
        df = read_csv(GROUPS_FILE, GROUP_COLUMNS)
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_csv(df[GROUP_COLUMNS], GROUPS_FILE)
        return _normalize_group(new_row)

    @staticmethod
    def update_group(group_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        df = read_csv(GROUPS_FILE, GROUP_COLUMNS)
        mask = df['id'] == group_id
        if not mask.any():
            return None

        for key, value in updates.items():
            if key in GROUP_COLUMNS and key != 'id':
                if isinstance(value, (date, datetime)):
                    value = value.isoformat()[:10]
                df.loc[mask, key] = value

        save_csv(df[GROUP_COLUMNS], GROUPS_FILE)
        return _normalize_group(df[mask].iloc[0].to_dict())

    @staticmethod
    def delete_group(group_id: str) -> bool:
        df = read_csv(GROUPS_FILE, GROUP_COLUMNS)
        if group_id not in df['id'].values:
            return False
        
        # Remove group
        df = df[df['id'] != group_id]
        save_csv(df, GROUPS_FILE)
        
        # Remove associated payments
        payments_df = read_csv(PAYMENTS_FILE, ['id', 'group_id', 'amount', 'start_date', 'end_date', 'note'])
        payments_df = payments_df[payments_df['group_id'] != group_id]
        save_csv(payments_df, PAYMENTS_FILE)
        
        return True

    @staticmethod
    def get_payments(group_id: str = None) -> List[Dict[str, Any]]:
        df = read_csv(PAYMENTS_FILE, ['id', 'group_id', 'amount', 'start_date', 'end_date', 'note'])
        
        # Coerce types to handle invalid data
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        # Convert dates and handle errors
        df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce').dt.date
        df['end_date'] = pd.to_datetime(df['end_date'], errors='coerce').dt.date
        
        # Filter invalid rows (ensure required fields are present)
        required_cols = ['id', 'group_id', 'amount', 'start_date', 'end_date']
        df = df.dropna(subset=required_cols)
        
        if group_id:
            df = df[df['group_id'] == group_id]
        
        df["note"] = df["note"].fillna("")  # Ensure note is never None

        return df.to_dict('records')
        
    @staticmethod
    def get_payment(payment_id: str) -> Optional[Dict[str, Any]]:
        df = read_csv(PAYMENTS_FILE, ['id', 'group_id', 'amount', 'start_date', 'end_date', 'note'])
        
        # Coerce types to handle invalid data
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce').dt.date
        df['end_date'] = pd.to_datetime(df['end_date'], errors='coerce').dt.date
        
        # Filter invalid rows first
        required_cols = ['id', 'group_id', 'amount', 'start_date', 'end_date']
        df = df.dropna(subset=required_cols)
        
        payment = df[df['id'] == payment_id]
        if payment.empty:
            return None
            
        return payment.iloc[0].to_dict()

    @staticmethod
    def create_payment(group_id: str, amount: float, start_date: date, end_date: date, note: str = None) -> Dict[str, Any]:
        ensure_data_dir()
        new_id = str(uuid.uuid4())
        new_row = {
            'id': new_id, 
            'group_id': group_id, 
            'amount': amount, 
            'start_date': start_date, 
            'end_date': end_date, 
            'note': note
        }
        df_new = pd.DataFrame([new_row])
        
        if os.path.exists(PAYMENTS_FILE) and os.path.getsize(PAYMENTS_FILE) > 0:
            try:
                shutil.copy2(PAYMENTS_FILE, PAYMENTS_FILE + ".bak")
            except Exception:
                pass
            df_new.to_csv(PAYMENTS_FILE, mode='a', header=False, index=False)
        else:
            df_new.to_csv(PAYMENTS_FILE, index=False)
        return new_row

    @staticmethod
    def update_payment(payment_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        df = read_csv(PAYMENTS_FILE, ['id', 'group_id', 'amount', 'start_date', 'end_date', 'note'])
        
        mask = df['id'] == payment_id
        if not mask.any():
            return None
        if df[mask]["note"].isna().all():
            df.loc[mask, "note"] = ""  # Ensure note is not NaN for the update process
        for key, value in updates.items():
            if key in df.columns:
                if isinstance(value, (date, datetime)):
                    value = value.isoformat()
                df.loc[mask, key] = value
        save_csv(df, PAYMENTS_FILE)

        return df[mask].iloc[0].to_dict()

    @staticmethod
    def delete_payment(payment_id: str) -> bool:
        df = read_csv(PAYMENTS_FILE, ['id', 'group_id', 'amount', 'start_date', 'end_date', 'note'])
        if payment_id not in df['id'].values:
            return False
            
        df = df[df['id'] != payment_id]
        save_csv(df, PAYMENTS_FILE)
        return True
