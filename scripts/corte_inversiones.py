"""
corte_inversiones.py — La fase 6, paso a paso y con freno de mano.

    python scripts/corte_inversiones.py --estado      dónde está el corte
    python scripts/corte_inversiones.py --sombra      genera los grupos `shadow`
    python scripts/corte_inversiones.py --verificar   compara las dos series, sin escribir
    python scripts/corte_inversiones.py --cortar      EL CORTE (pide confirmación)
    python scripts/corte_inversiones.py --limpiar     borra la sombra y deja todo como estaba

Los tres primeros son seguros: `--sombra` solo añade grupos `type='shadow'`, que
`VirtualItemsProcessor` ignora, y `--verificar` no escribe nada.

**`--cortar` es el único destructivo**: vacía los pagos de los grupos `Inversiones_*` y
activa los sombra. No está expuesto por HTTP a propósito — una operación que reescribe el
patrimonio histórico no debería estar a una llamada de distancia. Pide confirmación por
teclado salvo que se pase `--si`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contabilidad.backend.services.investments import corte  # noqa: E402


def _tabla(estado):
    print(f"  {'portafolio':<24} {'pagos propios':>14} {'sombra':>8} {'generado activo':>16}")
    for fila in estado['portafolios']:
        print(f"  {fila['portafolio']:<24} {fila['pagos_propios']:>14} "
              f"{fila['sombra']:>8} {fila['generado_activo']:>16}")
    print(f"\n  cortado: {'sí' if estado['cortado'] else 'no'}")


def estado():
    _tabla(corte.estado())


def sombra():
    resultado = corte.sembrar_sombra()
    for fila in resultado['portafolios']:
        print(f"  {fila['portafolio']:<24} {fila['pagos']:>4} pagos → {fila['grupo_sombra_id']}")
    print(f"\n{resultado['pagos']} pagos en sombra. El dashboard no cambia: nadie aplica «shadow».")


def verificar() -> bool:
    r = corte.verificar()
    if 'error' in r:
        print(f"  {r['error']}")
        return False

    print(f"  pagos hoy: {r['pagos_antes']}  →  tras el corte: {r['pagos_despues']}")
    print(f"  días comparados: {r['dias']}   cambian: {r['dias_que_cambian']}   "
          f"desvío máx: {r['max_desvio']:,.2f}  (tolerancia {r['tolerancia']})")
    if r['peores_dias']:
        print("\n  los días que más se mueven:")
        for d in r['peores_dias']:
            print(f"    {d['fecha']}   {d['desvio']:>10,.2f}")
    print(f"\n  {'EQUIVALENTE — se puede cortar' if r['equivalente'] else 'NO equivalente'}")
    return r['equivalente']


def cortar(si: bool):
    if not verificar():
        print("\nLa verificación no pasa. Revisa los días de arriba antes de insistir.")
        return

    if not si:
        print("\nEsto vacía los pagos de los grupos Inversiones_* y activa los generados.")
        print("Respaldo automático en pagos.csv.bak y grupos.csv.bak.")
        if input("Escribe «cortar» para confirmar: ").strip().lower() != 'cortar':
            print("Cancelado.")
            return

    r = corte.aplicar_corte()
    if not r['ok']:
        print(f"\nNo se cortó: {r.get('error')}")
        return
    print(f"\nCorte aplicado: {r['pagos_vaciados']} pagos vaciados, "
          f"{r['grupos_activados']} grupos activados.")
    _tabla(corte.estado())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--estado', action='store_true')
    grupo.add_argument('--sombra', action='store_true')
    grupo.add_argument('--verificar', action='store_true')
    grupo.add_argument('--cortar', action='store_true')
    grupo.add_argument('--limpiar', action='store_true')
    parser.add_argument('--si', action='store_true', help='no preguntar al cortar')
    args = parser.parse_args()

    if args.estado:
        estado()
    elif args.sombra:
        sombra()
    elif args.verificar:
        verificar()
    elif args.cortar:
        cortar(args.si)
    else:
        print(f"{corte.limpiar_sombra()} grupos sombra borrados.")
