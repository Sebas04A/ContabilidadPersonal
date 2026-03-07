import pandas as pd
import os
import uuid
import shutil
from typing import List, Dict, Any, Optional
from datetime import date

# Define paths
BASE_DATA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'backend', 'interpolaciones'))

GROUPS_FILE = os.path.join(BASE_DATA_PATH, 'grupos.csv')
PAYMENTS_FILE = os.path.join(BASE_DATA_PATH, 'pagos.csv')

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
        print(f"Error reading {file_path}: {e}")
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
    def get_groups(type_filter: str = 'interpolated') -> List[Dict[str, Any]]:
        df = read_csv(GROUPS_FILE, ['id', 'name', 'description', 'type'])
        
        # Backward compatibility: treat None/NaN type as 'interpolated'
        if 'type' in df.columns:
            df['type'] = df['type'].fillna('interpolated')
        
        if type_filter:
            df = df[df['type'] == type_filter]
            
        return df.to_dict('records')

    @staticmethod
    def get_group(group_id: str) -> Optional[Dict[str, Any]]:
        df = read_csv(GROUPS_FILE, ['id', 'name', 'description', 'type'])
        group = df[df['id'] == group_id]
        if group.empty:
            return None
        return group.iloc[0].to_dict()

    @staticmethod
    def create_group(name: str, description: str = None, group_type: str = 'interpolated') -> Dict[str, Any]:
        ensure_data_dir()
        new_id = str(uuid.uuid4())
        new_row = {'id': new_id, 'name': name, 'description': description, 'type': group_type}
        df_new = pd.DataFrame([new_row])
        
        if os.path.exists(GROUPS_FILE) and os.path.getsize(GROUPS_FILE) > 0:
            try:
                shutil.copy2(GROUPS_FILE, GROUPS_FILE + ".bak")
            except Exception:
                pass
            df_new.to_csv(GROUPS_FILE, mode='a', header=False, index=False)
        else:
            df_new.to_csv(GROUPS_FILE, index=False)
        return new_row

    @staticmethod
    def update_group(group_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        df = read_csv(GROUPS_FILE, ['id', 'name', 'description', 'type'])
        mask = df['id'] == group_id
        if not mask.any():
            return None
        
        for key, value in updates.items():
            if key in df.columns:
                df.loc[mask, key] = value
        
        save_csv(df, GROUPS_FILE)
        return df[mask].iloc[0].to_dict()

    @staticmethod
    def delete_group(group_id: str) -> bool:
        df = read_csv(GROUPS_FILE, ['id', 'name', 'description', 'type'])
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
            
        for key, value in updates.items():
            if key in df.columns:
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
