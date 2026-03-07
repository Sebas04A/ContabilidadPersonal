import json
import os
import pandas as pd

RULES_FILE = '../data/etiquetado/rules.json'

def load_rules():
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"description_map": {}, "entity_data": {}}
    return {"description_map": {}, "entity_data": {}}

def save_rules(rules):
    # Asegurar que el directorio existe
    os.makedirs(os.path.dirname(RULES_FILE), exist_ok=True)
    with open(RULES_FILE, 'w', encoding='utf-8') as f:
        json.dump(rules, f, indent=4, ensure_ascii=False)

def learn_from_transaction(description, clean_name, attributes=None):
    """
    Aprende de una transacción guardada.
    description: str (descripción original del banco)
    clean_name: str (nombre comercial limpio)
    attributes: dict (opcional: categoria, tags, prioridad, es_fijo, felicidad)
    """
    rules = load_rules()
    
    # 1. Aprender mapeo Descripción -> Nombre Limpio
    # Usamos la descripción tal cual para mapping directo, aunque la búsqueda sea fuzzy
    if description and clean_name:
        rules.setdefault("description_map", {})
        rules["description_map"][description] = clean_name

    # 2. Aprender atributos de la Entidad (Solo si se pasan atributos)
    if clean_name and attributes is not None:
        rules.setdefault("entity_data", {})
        # Actualizamos siempre con lo último (Overwrite strategy)
        relevant_attrs = {k: v for k, v in attributes.items() if k in ['categoria', 'prioridad', 'es_fijo', 'nota']}
        relevant_attrs['tags'] = attributes.get('tags', '')
        rules["entity_data"][clean_name] = relevant_attrs

    save_rules(rules)

def apply_rules_to_df(df):
    """
    Aplica las reglas a las filas NO revisadas del DataFrame.
    """
    rules = load_rules()
    map_desc = rules.get("description_map", {})
    entity_data = rules.get("entity_data", {})
    
    # Pre-computar keys ordenadas por longitud para matching "greedy"
    # Convertimos keys a lowercase para matching case-insensitive
    desc_keys = sorted(map_desc.keys(), key=len, reverse=True)

    def apply_row(row):
        if row['revisado']:
            return row
            
        desc = str(row['DESCRIPCION'])
        clean_name = row['nombre_limpio']
        
        # 1. Intentar encontrar Nombre Limpio si no tiene
        found_match = False
        if pd.isna(clean_name) or str(clean_name).strip() == "":
            desc_normalized = desc.lower() # Normalizamos solo para buscar coincidencia
            for key in desc_keys:
                # Buscamos si la KEY (ej: "Uber") está dentro de la DESCRIPCIÓN (ej: "lkjasd uber lkjsad")
                # Lo hacemos case-insensitive
                if key.lower() in desc_normalized:
                    clean_name = map_desc[key]
                    row['nombre_limpio'] = clean_name
                    found_match = True
                    break
            
            # Si después de buscar reglas no hay match, usamos la descripción por defecto
            if not found_match:
                clean_name = desc.title()
                row['nombre_limpio'] = clean_name
        else:
            # Si ya tiene nombre limpio (quizas se autollenó antes o vino así), lo usamos
            found_match = True
            
        # 2. Si tenemos Nombre Limpio, rellenar resto de datos
        if found_match and clean_name in entity_data:
            data = entity_data[clean_name]
            
            # Solo llenar si está vacío o es valor default
            if pd.isna(row['categoria']) or row['categoria'] in ["Sin Categoría", "---"]:
                row['categoria'] = data.get('categoria', row['categoria'])
                
            if pd.isna(row['tags']) or str(row['tags']).strip() == "":
                row['tags'] = data.get('tags', "")
                
            # Prioridad y Fijo se pueden sobrescribir con lo aprendido
            row['prioridad'] = data.get('prioridad', row['prioridad'])
            row['es_fijo'] = data.get('es_fijo', row['es_fijo'])
            
            # Nota se propaga si está vacía o es valor default
            if pd.isna(row['nota']) or str(row['nota']).strip() == "":
                row['nota'] = data.get('nota', "")
            
        return row

    return df.apply(apply_row, axis=1)
