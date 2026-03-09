import os
import json
import pandas as pd

CSV_PATH = os.path.join("c:\\", "Users", "andre", "Programacion", "Cuentas", "data", "sistema","etiquetado", "etiquetas.csv")
JSON_PATH = os.path.join("c:\\", "Users", "andre", "Programacion", "Cuentas", "data", "sistema","etiquetado", "rules.json")

def convert_val(old_val):
    try:
        val = int(old_val)
        if 1 <= val <= 5:
            return (val * 2) - 1
        return val
    except (ValueError, TypeError):
        return old_val

def migrate_csv():
    print(f"Migrating CSV: {CSV_PATH}")
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        if 'felicidad' in df.columns:
            # Backup
            df.to_csv(CSV_PATH + ".bak", index=False)
            print("Backup created.")
            df['felicidad'] = df['felicidad'].apply(convert_val)
            df.to_csv(CSV_PATH, index=False)
            print("CSV migrated successfully.")
        else:
            print("Column 'felicidad' not found in CSV.")
    else:
        print("CSV not found.")

def migrate_json():
    print(f"\nMigrating JSON: {JSON_PATH}")
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        changed = False
        
        # rules.json has structure {"description_map": {...}, "entity_data": {...}, "tag_data": {...}}
        # Check entity_data and tag_data
        for block in ["entity_data", "tag_data"]:
            if block in data:
                for key, val in data[block].items():
                    if "felicidad" in val:
                        old_val = val["felicidad"]
                        new_val = convert_val(old_val)
                        if new_val != old_val:
                            val["felicidad"] = new_val
                            changed = True

        if changed:
            # Backup
            with open(JSON_PATH + ".bak", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print("Backup created.")
            
            with open(JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print("JSON migrated successfully.")
        else:
            print("No changes needed in JSON.")
    else:
        print("JSON not found.")

if __name__ == "__main__":
    migrate_csv()
    migrate_json()
