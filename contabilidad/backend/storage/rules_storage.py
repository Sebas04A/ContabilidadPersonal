"""
Motor de Reglas — Servicio centralizado
=======================================

Gestiona el aprendizaje y aplicación de reglas de clasificación
automática de transacciones.

Reglas almacenadas en data/sistema/etiquetado/rules.json:
  - description_map  : DESCRIPCION_BANCO -> nombre_limpio
  - entity_data      : nombre_limpio     -> {categoria, tags, prioridad, es_fijo, nota}
  - tag_data         : tag               -> {categoria, prioridad, es_fijo}
"""

import json
import os
import pandas as pd
from typing import Optional
import numpy as np

from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

# Ruta al archivo de reglas
from contabilidad.config import PATH_DATA
import os
_RULES_PATH = os.path.join(PATH_DATA, 'sistema', 'etiquetado', 'rules.json')

# ── Helpers de lectura/escritura ──────────────────────────────────────────────

def get_rules_path() -> str:
    return _RULES_PATH


def load_rules() -> dict:
    """Carga el archivo de reglas. Retorna dict vacío si no existe o hay error."""
    if not os.path.exists(_RULES_PATH):
        return {"description_map": {}, "entity_data": {}, "tag_data": {}}
    try:
        with open(_RULES_PATH, 'r', encoding='utf-8') as f:
            rules = json.load(f)
            rules.setdefault("description_map", {})
            rules.setdefault("entity_data", {})
            rules.setdefault("tag_data", {})
            return rules
    except Exception as e:
        logger.error("Error cargando rules.json: %s", e)
        return {"description_map": {}, "entity_data": {}, "tag_data": {}}


def save_rules(rules: dict) -> None:
    """Persiste el dict de reglas en disco."""
    os.makedirs(os.path.dirname(_RULES_PATH), exist_ok=True)
    try:
        with open(_RULES_PATH, 'w', encoding='utf-8') as f:
            json.dump(rules, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error("Error guardando rules.json: %s", e)


# ── Operaciones de escritura ──────────────────────────────────────────────────

def save_rule_map(original: str, clean: str) -> None:
    """
    Guarda un mapeo descripción → nombre limpio.
    Solo escribe si el valor realmente cambió.
    """
    rules = load_rules()
    if rules["description_map"].get(original) != clean:
        rules["description_map"][original] = clean
        save_rules(rules)
        logger.info("Regla descripción guardada: '%s' -> '%s'", original, clean)


def save_entity_rule(name: str, attrs: dict) -> dict:
    """
    Guarda o actualiza los atributos de una entidad (nombre limpio).
    Hace merge con los datos existentes (no sobreescribe todo).
    """
    rules = load_rules()
    existing = rules["entity_data"].get(name, {})
    existing.update(attrs)
    rules["entity_data"][name] = existing
    save_rules(rules)
    return existing


def save_tag_rule(tag: str, attrs: dict) -> dict:
    """
    Guarda o actualiza los atributos de un tag.
    Hace merge con los datos existentes.
    """
    rules = load_rules()
    existing = rules["tag_data"].get(tag, {})
    existing.update(attrs)
    rules["tag_data"][tag] = existing
    save_rules(rules)
    return existing


# ── Motor de aplicación ───────────────────────────────────────────────────────

def apply_rules_to_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica las reglas a un DataFrame de transacciones.

    Para cada fila NO revisada:
      1. Busca el nombre limpio via description_map (substring case-insensitive)
      2. Si lo encuentra, aplica entity_data (categoria, tags, prioridad, es_fijo, nota)
      3. Si aún sin categoria, busca via tag_data

    Modifica en su sitio las columnas: nombre_limpio, categoria, tags, prioridad,
    es_fijo, nota.
    """
    logger.debug("Aplicando reglas a dataframe")
    
    rules = load_rules()
    logger.debug("Reglas cargadas")
    # logger.debug(rules)
    desc_map: dict = rules["description_map"]
    entity_data: dict = rules["entity_data"]
    tag_data: dict = rules["tag_data"]
    # logger.debug("Reglas cargadas")
    # logger.debug(desc_map)
    # logger.debug(entity_data)
    # logger.debug(tag_data)

    if not desc_map and not entity_data and not tag_data:
        return df  # Sin reglas, nada que hacer

    # Asegurar columnas necesarias
    for col in ('nombre_limpio', 'categoria', 'tags', 'prioridad', 'nota'):
        if col not in df.columns:
            df[col] = None
    logger.debug("Comenzando a aplicar reglas a cada fila")

    df = df.apply(lambda row: _apply_rules_to_row(row, desc_map, entity_data, tag_data), axis=1)
    logger.debug("Reglas aplicadas")
    # logger.debug(df)
    return df


def _is_empty(val) -> bool:
    """Retorna True si el valor es None, NaN o string vacío/placeholder."""
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    s = str(val).strip()
    return s in ('', 'nan', '---', 'Sin Categoría')


def _apply_rules_to_row(row: pd.Series, desc_map: dict, entity_data: dict, tag_data: dict) -> pd.Series:
    """Aplica reglas a una fila individual. No toca filas ya revisadas."""
    # logger.debug("revisado: ")
    # logger.debug("revisado: %s","True" if row.get('revisado')==np.nan else "False")
    if row.get('revisado')==np.nan:
        return row
    # logger.warning("Fila no revisada")
    # logger.debug(row)

    # ── Paso 1: Resolver nombre limpio ───────────────────────────────────────
    clean_name = row.get('nombre_limpio')
    if _is_empty(clean_name):
        desc = str(row.get('DESCRIPCION', ''))
        desc_lower = desc.lower()
        # Ordenar por longitud descendente para matching greedy
        for key in sorted(desc_map.keys(), key=len, reverse=True):
            if key.lower() in desc_lower:
                clean_name = desc_map[key]
                row['nombre_limpio'] = clean_name
                break

    # ── Paso 2: Aplicar entity_data ───────────────────────────────────────────
    if clean_name and not _is_empty(clean_name) and clean_name in entity_data:
        rule = entity_data[clean_name]

        if _is_empty(row.get('categoria')):
            row['categoria'] = rule.get('categoria', row.get('categoria'))

        if _is_empty(row.get('tags')):
            row['tags'] = rule.get('tags', row.get('tags'))

        if _is_empty(row.get('prioridad')):
            row['prioridad'] = rule.get('prioridad', row.get('prioridad'))

        # es_fijo y nota siempre se propagan si la regla los tiene
        if 'es_fijo' in rule:
            row['es_fijo'] = rule['es_fijo']

        if 'nota' in rule and _is_empty(row.get('nota')):
            row['nota'] = rule['nota']

    # ── Paso 3: Fallback via tag_data ─────────────────────────────────────────
    if _is_empty(row.get('categoria')) and tag_data:
        tags_str = row.get('tags')
        if not _is_empty(tags_str):
            for tag in [t.strip() for t in str(tags_str).split(',') if t.strip()]:
                if tag in tag_data:
                    rule = tag_data[tag]
                    row['categoria'] = rule.get('categoria', row.get('categoria'))
                    if _is_empty(row.get('prioridad')):
                        row['prioridad'] = rule.get('prioridad', row.get('prioridad'))
                    if 'es_fijo' in rule:
                        row['es_fijo'] = rule['es_fijo']
                    break

    return row
