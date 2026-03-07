import pandas as pd
import numpy as np

def test_sanitization():
    # Create DataFrame with NaN in 'note'
    df = pd.DataFrame([
        {'id': '1', 'note': np.nan},
        {'id': '2', 'note': None},
        {'id': '3', 'note': 'some note'}
    ])
    
    print("Original types:")
    print(df.dtypes)
    print(df)
    
    # Current logic in storage.py
    # df['note'] = df['note'].where(df['note'].notnull(), None)
    
    # Mimic exactly what's in storage.py
    try:
        df['note'] = df['note'].where(df['note'].notnull(), None)
    except Exception as e:
        print(f"Error in where: {e}")
        
    print("\nAfter .where():")
    print(df)
    print("Records:")
    print(df.to_dict('records'))
    
    # Robust alternative
    df2 = pd.DataFrame([
        {'id': '1', 'note': np.nan}
    ])
    df2['note'] = df2['note'].apply(lambda x: None if pd.isna(x) else x)
    print("\nAfter .apply():")
    print(df2.to_dict('records'))

if __name__ == "__main__":
    test_sanitization()
