#!/usr/bin/env python3
"""
Siembra las posiciones de inversión que el banco no puede reconstruir.

Son cuatro, y salen de `PLAN_INVERSIONES.md` §3.5.1 paso 2. Dos clases distintas:

**Plazos fijos abiertos antes de que empiece el historial** (2024-03-12). El extracto
solo tiene su cancelación, así que el detector las reporta como huérfanas y no puede
saber ni cuándo ni con cuánto empezaron:

  - `Inversiones_Uni`   cerrada el 2024-05-29 (10.100)
  - `Inversiones_Madre` cerrada el 2024-10-25 (12.854,21 + 682,63 de interés)

Aquí también se sembraban dos **ajustes de residual** (3.228 de `Uni` y 647 de `Madre`).
**Ya no**: los dos contaban plata que ya estaba contada por el propio certificado, y
restaban de más. El razonamiento completo está en el comentario de `construir_siembras`;
si vuelven, vuelve el bug.

La corrección de −600 de `Mis Depositos` **no** se siembra: ese grupo se queda en
Variables con sus pagos fijos a mano.

Los montos de los dos plazos fijos NO están escritos aquí: se leen del detector, para
que la siembra sea del dato del banco y no de una copia que envejece. Si el detector
deja de ver esa huérfana, el script avisa y no inventa nada.

Idempotente: cada siembra tiene un id fijo (`siembra-…`), así que correrlo dos veces no
duplica. `--rehacer` las borra y las vuelve a crear; `--dry-run` no escribe.

Uso:
    python scripts/sembrar_posiciones_inversion.py --dry-run
    python scripts/sembrar_posiciones_inversion.py
    python scripts/sembrar_posiciones_inversion.py --rehacer
"""

import argparse
import os
import sys
from typing import Any, Dict, List, Optional

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from contabilidad.backend.services.investments import detect_positions, posiciones as svc
from contabilidad.backend.storage.data_pipeline import get_pipeline
from contabilidad.backend.storage.investments_storage import InvestmentStorage
from contabilidad.backend.storage.variables_storage import InterpolationStorage

# Los tres portafolios ya existen como grupos `fixed` en grupos.csv.
UNI = 'e996e29a-1443-4026-bb64-13f6da31ab32'
MADRE = '5a1076ed-9b20-4e86-bd35-a91c57db1246'
MIAS = 'bd963a38-13b9-4a6f-80a5-b871f9dc38d7'

#: `es_custodia`: la plata está en la cuenta del usuario pero no es suya, así que se
#: sigue igual que las demás pero nunca suma al patrimonio propio. Solo `Mias` es propio.
PORTAFOLIOS = {MIAS: False, UNI: True, MADRE: True}


def _primera_fecha_del_historial(df) -> str:
    """Cota inferior para lo que se abrió "antes del historial".

    No sabemos cuándo se abrieron, pero sí que ya existían el primer día del extracto.
    Fechar ahí el aporte es la afirmación más débil que sigue siendo cierta.
    """
    return df['FECHA'].min().date().isoformat()


def _huerfana_de(fecha: str, huerfanas) -> Optional[Any]:
    return next((h for h in huerfanas if h.fecha.isoformat() == fecha), None)


def _tx_del_capital(df, huerfana) -> Optional[str]:
    """De las filas de la huérfana, la que trae el capital (la de mayor monto)."""
    filas = df[df['id'].astype(str).isin(huerfana.tx_ids)]
    if filas.empty:
        return None
    return str(filas.loc[filas['MONTO'].idxmax(), 'id'])


def construir_siembras(df) -> List[Dict[str, Any]]:
    resultado = detect_positions(df)
    inicio = _primera_fecha_del_historial(df)
    siembras: List[Dict[str, Any]] = []

    # ── Plazos fijos anteriores al historial ─────────────────────────────────
    for slug, portafolio, fecha_cierre, etiqueta in (
        ('uni-2024-05-29', UNI, '2024-05-29', 'Inversiones_Uni'),
        ('madre-2024-10-25', MADRE, '2024-10-25', 'Inversiones_Madre'),
    ):
        huerfana = _huerfana_de(fecha_cierre, resultado.huerfanas)
        if huerfana is None:
            print(f"  ! No encontré la cancelación huérfana del {fecha_cierre}; la salto.")
            continue

        capital = huerfana.capital_sugerido
        movimientos = [
            {'fecha': inicio, 'tipo': 'aporte', 'monto': capital,
             'nota': 'Capital anterior al historial bancario (fecha estimada)'},
            {'fecha': fecha_cierre, 'tipo': 'retiro', 'monto': capital,
             'tx_id': _tx_del_capital(df, huerfana)},
        ]
        if huerfana.interes_sugerido:
            movimientos.append({'fecha': fecha_cierre, 'tipo': 'interes',
                                'monto': huerfana.interes_sugerido})
        if huerfana.retencion:
            movimientos.append({'fecha': fecha_cierre, 'tipo': 'retencion',
                                'monto': huerfana.retencion})

        siembras.append({
            'id': f'siembra-{slug}',
            'portafolio_id': portafolio,
            'tipo': 'plazo_fijo',
            'origen': 'manual',
            'fecha_apertura': None,
            'fecha_cierre': fecha_cierre,
            'tx_cierre_id': _tx_del_capital(df, huerfana),
            'institucion': 'Pichincha',
            'nota': f'{etiqueta}: abierta antes del historial bancario; solo se ve su cancelación',
            'movimientos': movimientos,
        })

    # ── Ajustes de residual — retirados el 2026-08-12 ────────────────────────
    #
    # Aquí se sembraban dos `ajuste`, y los dos contaban plata que ya estaba contada.
    # Se quitan a propósito; si vuelven, vuelve el bug. Los borra
    # `scripts/limpiar_ajustes_redundantes.py`.
    #
    # `siembra-uni-madre-tarjeta` (3.228, Uni, 2024-09-04 → 2024-09-23)
    #     Su propia nota decía «3.228 que **entraron** al portafolio», pero estaba escrita
    #     como `aporte` primero, o sea saliendo. Y ninguna de las dos lecturas era
    #     correcta: los 3.228 son **parte de los 10.482,64 que devolvió el CDT** ese día,
    #     escritos en una segunda fila de `pagos.csv` solo para etiquetarlos. Las dos filas
    #     del usuario suman 7.258 + 3.228 = 10.486 ≈ lo que devolvió el banco, y el 09-23
    #     esa plata se reparte en 6.648 (nuevo CDT) + 3.834,64 (matrícula) = 10.482,64
    #     exacto. No queda hueco para 3.228 más. Restarlos hacía que el escalón del
    #     2024-09-04 saliera en 7.245,41 en vez de 10.473,41.
    #
    # `siembra-madre-647` (647, Madre, 2025-12-22 → 2026-03-02)
    #     Igual: su nota decía «los 647 que **sobraron**», que es precisamente el residual
    #     —no una posición aparte—. Tras los dos retiros de 4.900 de diciembre, el residual
    #     aterriza solo en 646,97. Tenerlo además como `ajuste` lo restaba una vez de más.

    return siembras


def marcar_portafolios(dry_run: bool) -> None:
    for group_id, es_custodia in PORTAFOLIOS.items():
        grupo = InterpolationStorage.get_group(group_id)
        if grupo is None:
            print(f"  ! El grupo {group_id} no existe; no lo puedo marcar como portafolio.")
            continue
        if grupo.get('es_inversion') and grupo.get('es_custodia') == es_custodia:
            continue
        etiqueta = 'custodia' if es_custodia else 'propio'
        print(f"  · Marco «{grupo['name']}» como portafolio de inversión ({etiqueta})")
        if not dry_run:
            InterpolationStorage.update_group(
                group_id, {'es_inversion': True, 'es_custodia': es_custodia}
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true', help='Muestra qué haría, sin escribir')
    parser.add_argument('--rehacer', action='store_true', help='Borra las siembras existentes y las vuelve a crear')
    args = parser.parse_args()

    df = get_pipeline().get_account_data()
    siembras = construir_siembras(df)

    existentes = {p['id'] for p in InvestmentStorage.get_positions()}
    creadas = omitidas = 0

    print(f"\nSiembra de posiciones manuales{' (dry-run)' if args.dry_run else ''}\n")
    for siembra in siembras:
        totales = svc.calcular_totales(siembra['movimientos'])
        etiqueta = (f"{siembra['id']:28} {siembra['tipo']:11} "
                    f"capital {totales['capital']:>10.2f}  interés {totales['interes']:>8.2f}")

        if siembra['id'] in existentes:
            if not args.rehacer:
                print(f"  = {etiqueta}   (ya existe)")
                omitidas += 1
                continue
            print(f"  ~ {etiqueta}   (rehecha)")
            if not args.dry_run:
                InvestmentStorage.delete_position(siembra['id'])
        else:
            print(f"  + {etiqueta}")

        if not args.dry_run:
            svc.create_position(siembra)
        creadas += 1

    print()
    marcar_portafolios(args.dry_run)

    print(f"\n{creadas} sembradas, {omitidas} ya existían.")
    if not args.dry_run:
        diff = svc.reconcile(df)
        print(f"Reconciliación: {diff['resumen']}")
        if diff['huerfanas']:
            print("Huérfanas todavía sin cubrir:")
            for h in diff['huerfanas']:
                print(f"  - {h['fecha']}  capital {h['capital_sugerido']:.2f}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
