"""
Migration Script: gastos_maestros.csv -> etiquetas.csv
=====================================================

This script migrates labeling data from the old gastos_maestros.csv
to the new etiquetas.csv system.

The migration matches rows using TIPO to determine source (BANCA/TARJETA),
then uses FECHA + DESCRIPCION + MONTO to find the matching source_id.

For old CUENTA transactions that predate banca_unida.xlsx, it creates
a fallback legacy ID using hash of FECHA|DESCRIPCION|MONTO|TIPO.

Usage:
    python scripts/migrate_to_etiquetas.py [--dry-run]
"""

import pandas as pd
import os
import sys
import hashlib
import argparse
from datetime import datetime

raise NotImplementedError("Hay que actualizar los paths para volver a correr este archivo")

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Paths
GASTOS_MAESTROS_PATH = os.path.join(PROJECT_ROOT, 'data', 'sistema','etiquetado', 'gastos_maestros.csv')
ETIQUETAS_PATH = os.path.join(PROJECT_ROOT, 'data', 'sistema','etiquetado', 'etiquetas.csv')
BANCA_PATH = os.path.join(PROJECT_ROOT, 'data', 'sistema','procesada', 'banca', 'banca_unida.xlsx')
TARJETA_PATH = os.path.join(PROJECT_ROOT, 'data', 'sistema','procesada', 'tarjeta', 'tarjeta_unida.xlsx')

LABEL_COLUMNS = [
    'source_id', 'source_type',
    'nombre_limpio', 'categoria', 'tags', 'prioridad',
    'es_fijo', 'pertenece_a', 'es_reembolsable', 'deudor',
    'felicidad', 'revisado', 'nota', 'split_group_id',
]

LEGACY_EXTRA_COLUMNS = ['legacy_fecha', 'legacy_descripcion', 'legacy_monto']
ALL_COLUMNS = LABEL_COLUMNS + LEGACY_EXTRA_COLUMNS


def normalize_desc(desc):
    if pd.isna(desc):
        return ''
    return str(desc).strip().upper()


def normalize_date(date_val):
    if pd.isna(date_val):
        return ''
    try:
        return pd.to_datetime(date_val).strftime('%Y-%m-%d')
    except Exception:
        return str(date_val).split(' ')[0]


def make_key(row):
    date = normalize_date(row['FECHA'])
    desc = normalize_desc(row['DESCRIPCION'])
    try:
        monto = '{:.2f}'.format(float(row['MONTO']))
    except Exception:
        monto = str(row['MONTO'])
    return '{}|{}|{}'.format(date, desc, monto)


def make_legacy_id(row):
    """Create a deterministic legacy ID for old transactions with no source match."""
    date = normalize_date(row['FECHA'])
    desc = normalize_desc(row['DESCRIPCION'])
    try:
        monto = '{:.2f}'.format(float(row['MONTO']))
    except Exception:
        monto = str(row['MONTO'])
    tipo = str(row.get('TIPO', 'CUENTA'))
    raw = '{}|{}|{}|{}'.format(date, desc, monto, tipo)
    return 'legacy_' + hashlib.md5(raw.encode('utf-8')).hexdigest()


def has_label_data(row):
    """Check if a row has any actual labeling data."""
    checks = {
        'nombre_limpio': lambda v: v not in ('---', 'Sin Categoria', '', 'nan', 'None'),
        'categoria': lambda v: v not in ('---', 'Sin Categoria', '', 'nan', 'None'),
        'prioridad': lambda v: v not in ('---', '', 'nan', 'None'),
        'pertenece_a': lambda v: v not in ('---', '', 'nan', 'None'),
        'tags': lambda v: v not in ('', 'nan', 'None'),
        'deudor': lambda v: v not in ('', 'nan', 'None'),
        'nota': lambda v: v not in ('', 'nan', 'None'),
    }
    for field, check in checks.items():
        if field in row.index and not pd.isna(row[field]):
            if check(str(row[field]).strip()):
                return True
    
    for field in ['es_fijo', 'es_reembolsable', 'revisado']:
        if field in row.index and not pd.isna(row[field]):
            if row[field] == True or str(row[field]).strip() == 'True':
                return True
    
    if 'felicidad' in row.index and not pd.isna(row['felicidad']):
        try:
            if int(float(row['felicidad'])) != 0:
                return True
        except Exception:
            pass
    
    return False


def migrate(dry_run=False):
    log = []
    def p(msg):
        log.append(msg)
        print(msg)
    
    p('=' * 60)
    p('Migration: gastos_maestros.csv -> etiquetas.csv')
    p('=' * 60)
    
    # 1. Load
    p('\n1. Loading files...')
    if not os.path.exists(GASTOS_MAESTROS_PATH):
        p('   ERROR: gastos_maestros.csv not found')
        return False
    
    maestros = pd.read_csv(GASTOS_MAESTROS_PATH)
    maestros['FECHA'] = pd.to_datetime(maestros['FECHA'])
    p('   gastos_maestros: {} rows'.format(len(maestros)))
    
    banca = pd.DataFrame()
    tarjeta = pd.DataFrame()
    
    if os.path.exists(BANCA_PATH):
        banca = pd.read_excel(BANCA_PATH)
        banca['FECHA'] = pd.to_datetime(banca['FECHA'])
        p('   banca_unida: {} rows ({} to {})'.format(
            len(banca), banca['FECHA'].min().date(), banca['FECHA'].max().date()))
    
    if os.path.exists(TARJETA_PATH):
        tarjeta = pd.read_excel(TARJETA_PATH)
        tarjeta['FECHA'] = pd.to_datetime(tarjeta['FECHA'])
        p('   tarjeta_unida: {} rows ({} to {})'.format(
            len(tarjeta), tarjeta['FECHA'].min().date(), tarjeta['FECHA'].max().date()))
    
    # 2. Build lookup indices
    p('\n2. Building lookup indices...')
    
    def build_lookup(df, source_type):
        lookup = {}
        for _, row in df.iterrows():
            key = make_key(row)
            if key not in lookup:
                lookup[key] = []
            lookup[key].append((row['id'], source_type))
        return lookup
    
    banca_lookup = build_lookup(banca, 'BANCA') if not banca.empty else {}
    tarjeta_lookup = build_lookup(tarjeta, 'TARJETA') if not tarjeta.empty else {}
    
    p('   Banca keys: {}'.format(len(banca_lookup)))
    p('   Tarjeta keys: {}'.format(len(tarjeta_lookup)))
    
    # 3. Match
    p('\n3. Matching rows...')
    
    matched_banca = 0
    matched_tarjeta = 0
    legacy_created = 0
    skipped = 0
    etiquetas_rows = []
    
    # Track usage for duplicate handling
    used_banca = {}   # key -> index of next unused match
    used_tarjeta = {}
    
    for _, row in maestros.iterrows():
        if not has_label_data(row):
            skipped += 1
            continue
        
        key = make_key(row)
        tipo = str(row.get('TIPO', 'CUENTA')).strip().upper()
        
        source_id = None
        source_type = None
        
        if tipo == 'TARJETA' and key in tarjeta_lookup:
            matches = tarjeta_lookup[key]
            idx = used_tarjeta.get(key, 0)
            if idx < len(matches):
                source_id, source_type = matches[idx]
                used_tarjeta[key] = idx + 1
                matched_tarjeta += 1
            else:
                source_id, source_type = matches[0]
                matched_tarjeta += 1
        elif tipo in ('CUENTA', 'BANCA') and key in banca_lookup:
            matches = banca_lookup[key]
            idx = used_banca.get(key, 0)
            if idx < len(matches):
                source_id, source_type = matches[idx]
                used_banca[key] = idx + 1
                matched_banca += 1
            else:
                source_id, source_type = matches[0]
                matched_banca += 1
        else:
            # No match - create legacy ID
            source_id = make_legacy_id(row)
            source_type = 'BANCA' if tipo in ('CUENTA', 'BANCA') else 'TARJETA'
            legacy_created += 1
        
        # Build label row
        label_row = {'source_id': source_id, 'source_type': source_type}
        for col in LABEL_COLUMNS:
            if col in ('source_id', 'source_type'):
                continue
            label_row[col] = row.get(col, None)
        
        # For legacy IDs, also store FECHA/DESCRIPCION/MONTO
        if str(source_id).startswith('legacy_'):
            label_row['legacy_fecha'] = str(row['FECHA'])
            label_row['legacy_descripcion'] = str(row['DESCRIPCION'])
            label_row['legacy_monto'] = float(row['MONTO'])
        
        etiquetas_rows.append(label_row)
    
    p('   Matched to banca: {}'.format(matched_banca))
    p('   Matched to tarjeta: {}'.format(matched_tarjeta))
    p('   Created legacy IDs: {}'.format(legacy_created))
    p('   Skipped (no labels): {}'.format(skipped))
    p('   Total labels: {}'.format(len(etiquetas_rows)))
    
    # 4. Save
    if dry_run:
        p('\n4. DRY RUN - would save {} rows'.format(len(etiquetas_rows)))
    else:
        p('\n4. Saving...')
        
        etiquetas_df = pd.DataFrame(etiquetas_rows)
        cols = [c for c in ALL_COLUMNS if c in etiquetas_df.columns]
        etiquetas_df = etiquetas_df[cols]
        
        # Backup
        if os.path.exists(ETIQUETAS_PATH):
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup = ETIQUETAS_PATH + '.backup_' + ts
            os.rename(ETIQUETAS_PATH, backup)
            p('   Backed up existing etiquetas.csv')
        
        etiquetas_df.to_csv(ETIQUETAS_PATH, index=False)
        new_size = os.path.getsize(ETIQUETAS_PATH)
        old_size = os.path.getsize(GASTOS_MAESTROS_PATH)
        p('   Saved! {} rows'.format(len(etiquetas_df)))
        p('   Old size: {:.1f} KB'.format(old_size / 1024))
        p('   New size: {:.1f} KB'.format(new_size / 1024))
        p('   Saved: {:.1f} KB ({:.1f}%)'.format(
            (old_size - new_size) / 1024,
            (1 - new_size / old_size) * 100))
        
        # Backup maestros
        import shutil
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        shutil.copy2(GASTOS_MAESTROS_PATH, GASTOS_MAESTROS_PATH + '.backup_' + ts)
        p('   Backed up gastos_maestros.csv')
    
    # Summary
    p('\n' + '=' * 60)
    p('SUMMARY')
    p('=' * 60)
    p('  Total maestros rows:    {}'.format(len(maestros)))
    p('  Matched to banca:      {}'.format(matched_banca))
    p('  Matched to tarjeta:    {}'.format(matched_tarjeta))
    p('  Legacy IDs created:    {}'.format(legacy_created))
    p('  Skipped (no labels):   {}'.format(skipped))
    
    if legacy_created > 0:
        p('\n  NOTE: {} rows got legacy IDs (prefix "legacy_").'.format(legacy_created))
        p('  These are old transactions not in banca_unida.xlsx.')
        p('  They will appear in the system with their legacy IDs.')
        p('  When you re-process older banca data, you can re-run migration.')
    
    # Write log
    with open(os.path.join(SCRIPT_DIR, 'migration_log.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(log))
    
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)
