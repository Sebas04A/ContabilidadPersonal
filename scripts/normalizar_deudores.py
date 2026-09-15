"""
normalizar_deudores.py — Que el `deudor` de cada etiqueta sea una persona de Supabase
=====================================================================================

Antes de conectar la app de deudas, el etiquetado guardaba nombres libres («Mamá»,
«Hermana», «Familia»…) que no coinciden con los deudores de Supabase («Madre», «Ñaña»),
así que esas transacciones no se cruzaban con las deudas. Este script deja el `deudor`
de `etiquetas.csv` con el nombre exacto de Supabase.

Regla, en orden:
  1. CORRECCIONES puntuales (vínculos rotos revisados a mano).
  2. Si la fila está vinculada a una deuda (`deuda_id`) o a un pago (`pago_id`), el
     deudor es el de ese vínculo: Supabase es la fuente de verdad.
  3. ALIAS de los nombres viejos («Mamá» → «Madre»), o quitar el nombre (SIN_PERSONA).
  4. El nombre de Supabase que coincida sin mayúsculas ni acentos («RUBIA» → «rubia»).
Lo que no se resuelve se lista y no se toca.

    python scripts/normalizar_deudores.py            # muestra los cambios
    python scripts/normalizar_deudores.py --aplicar  # los escribe (deja etiquetas.csv.bak)

Después de aplicar, invalidar la caché del backend: POST /api/cache/invalidate.
"""

import os
import sys
import unicodedata
from collections import Counter

import pandas as pd

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from contabilidad.backend.services.transaction_service import load_labels, save_labels  # noqa: E402
from contabilidad.debts.reading import (  # noqa: E402
    listar_deudores, obtener_deudas_para_analisis, obtener_pagos_para_analisis,
)

# Nombres del etiquetado viejo → deudor de Supabase. Confirmados el 2026-09-14 con las
# filas ya vinculadas: las 76 de «Mamá» con vínculo son deudas de Madre y las 5 de
# «Hermana», de Ñaña.
ALIAS = {
    'mama': 'Madre',
    'hermana': 'Ñaña',
}

# Nombres que no son una persona de Supabase: se quita el nombre.
SIN_PERSONA = {'amigo', 'yo'}

# La foto de $4.89 del 25 ago 2026 (tarjeta) se dividió en tres y las tres partes
# apuntaban a una deuda borrada. Cada parte va a la deuda que calza con su monto; la de
# $1.64 fue del propio usuario.
_FOTO = '9b4142d8314f2b5605c67643868cd8f0'
CORRECCIONES = [
    {'source_id': _FOTO, 'monto_asignado': -1.62,
     'cambios': {'deuda_id': 'eaa17b6c-3b4c-4782-b0fb-a5af5d6a213f'}},  # rubia · FOTO GRAFICA
    {'source_id': _FOTO, 'monto_asignado': -1.63,
     'cambios': {'deuda_id': 'abf3e5c3-fca1-4d24-b306-a395c8ca706f'}},  # Ale · Foto
    {'source_id': _FOTO, 'monto_asignado': -1.64,
     'cambios': {'deuda_id': None, 'deudor': None, 'es_reembolsable': False}},
]

APLICAR = '--aplicar' in sys.argv


def clave(nombre: str) -> str:
    """Sin acentos, sin espacios a los lados y en minúsculas."""
    s = unicodedata.normalize('NFD', nombre)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').strip().lower()


def texto(v) -> str:
    return v.strip() if isinstance(v, str) else ''


def main() -> int:
    df = load_labels()

    deudores = listar_deudores()
    por_clave = {clave(n): n for n in deudores['nombre'].dropna()}
    deudas = obtener_deudas_para_analisis()
    deudor_de_deuda = dict(zip(deudas['ID'].astype(str), deudas['DEUDOR_NOMBRE']))
    deudor_de_pago = {str(p['id']): p['deudor_nombre']
                      for p in obtener_pagos_para_analisis(incluir_cruces=True)}

    cambios = Counter()       # (campo, antes, después) -> filas
    sin_resolver = Counter()  # nombre -> filas
    vinculos_rotos = []

    # 1. Correcciones puntuales
    for c in CORRECCIONES:
        filas = df.index[(df['source_id'] == c['source_id'])
                         & ((df['monto_asignado'] - c['monto_asignado']).abs() < 0.001)]
        if len(filas) != 1:
            print(f"✗ La corrección {c['source_id'][:8]} {c['monto_asignado']} encontró {len(filas)} filas; se omite.")
            continue
        i = filas[0]
        for campo, valor in c['cambios'].items():
            antes = df.at[i, campo]
            if (pd.isna(antes) and valor is None) or antes == valor:
                continue
            df.at[i, campo] = valor
            cambios[(campo, str(antes) if not pd.isna(antes) else '', '' if valor is None else str(valor))] += 1

    # 2-4. El deudor de cada fila
    for i, fila in df.iterrows():
        actual = texto(fila['deudor'])
        deuda_id, pago_id = texto(fila['deuda_id']), texto(fila['pago_id'])

        if deuda_id and deuda_id not in deudor_de_deuda:
            vinculos_rotos.append(('deuda', deuda_id, fila['source_id']))
        if pago_id and pago_id not in deudor_de_pago:
            vinculos_rotos.append(('pago', pago_id, fila['source_id']))

        if deuda_id in deudor_de_deuda:
            nuevo = deudor_de_deuda[deuda_id]
        elif pago_id in deudor_de_pago:
            nuevo = deudor_de_pago[pago_id]
        elif not actual:
            continue
        elif clave(actual) in ALIAS:
            nuevo = ALIAS[clave(actual)]
        elif clave(actual) in SIN_PERSONA:
            nuevo = ''
        elif clave(actual) in por_clave:
            nuevo = por_clave[clave(actual)]
        else:
            sin_resolver[actual] += 1
            continue

        if nuevo != actual:
            df.at[i, 'deudor'] = nuevo or None
            cambios[('deudor', actual, nuevo)] += 1

    print('Cambios:')
    if not cambios:
        print('  (ninguno)')
    for (campo, antes, despues), n in sorted(cambios.items()):
        print(f"  {campo:15} {antes or '(vacío)':>20} → {despues or '(vacío)':20} {n} fila(s)")
    if sin_resolver:
        print('\nSin resolver (no se tocan):')
        for nombre, n in sin_resolver.most_common():
            print(f'  {nombre}: {n}')
    if vinculos_rotos:
        print('\nVínculos a deudas o pagos que no existen en Supabase:')
        for tipo, vid, sid in vinculos_rotos:
            print(f'  {tipo} {vid} (transacción {sid})')

    finales = Counter(texto(d) for d in df['deudor'] if texto(d))
    fuera = {n: c for n, c in finales.items() if n not in por_clave.values()}
    print('\nDeudores tras normalizar:', dict(finales.most_common()))
    print('Nombres que no son de Supabase:', fuera or 'ninguno')

    if not APLICAR:
        print('\nNada escrito. Repetir con --aplicar para guardar.')
        return 0
    save_labels(df)
    print(f'\n✓ Guardado. Respaldo en etiquetas.csv.bak.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
