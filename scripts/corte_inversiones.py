"""
corte_inversiones.py — La fase 6, paso a paso y con freno de mano.

    python scripts/corte_inversiones.py --estado      dónde está el corte
    python scripts/corte_inversiones.py --sombra      genera los grupos `shadow`
    python scripts/corte_inversiones.py --verificar   compara las dos series, sin escribir
    python scripts/corte_inversiones.py --cortar      EL CORTE (pide confirmación)
    python scripts/corte_inversiones.py --limpiar     borra la sombra y deja todo como estaba

Y una vez cortado, la operación de todos los días — cuando entra una inversión nueva:

    python scripts/corte_inversiones.py --regenerar-preview   qué cambiaría, sin escribir
    python scripts/corte_inversiones.py --regenerar           reescribe los pagos generados

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

    # La puerta es por portafolio: la tolerancia mide el redondeo de uno solo.
    print(f"\n  por portafolio (tolerancia {r['tolerancia']}):")
    for p in r['por_portafolio']:
        marca = 'cuadra' if p['cuadra'] else 'NO CUADRA'
        print(f"    {p['portafolio']:<22} {p['dias_que_cambian']:>5} días cambian   "
              f"desvío máx {p['max_desvio']:>6,.2f}   {marca}")

    print(f"\n  efecto sobre el patrimonio (la suma de los tres):")
    print(f"    {r['dias_que_cambian']} de {r['dias']} días cambian, desvío máx {r['max_desvio']:,.2f}")
    if r['peores_dias']:
        print("    los días que más se mueven:")
        for d in r['peores_dias'][:5]:
            print(f"      {d['fecha']}   {d['desvio']:>10,.2f}")

    print(f"\n  {'EQUIVALENTE — se puede cortar' if r['equivalente'] else 'NO equivalente'}")
    return r['equivalente']


def regenerar(si: bool, solo_preview: bool):
    """Pone al día los pagos generados de un portafolio ya cortado."""
    r = corte.previsualizar_regeneracion()

    for d in r['por_portafolio']:
        if 'error' in d:
            print(f"  {d['portafolio']:<22} {d['error']}")
            continue
        marca = 'sin cambios' if d['sin_cambios'] else 'CAMBIA'
        print(f"  {d['portafolio']:<22} pagos {d['pagos_ahora']:>3} → {d['pagos_nuevos']:<3} "
              f"{d['dias_que_cambian']:>5} días cambian   máx {d['max_desvio']:>10,.2f}   {marca}")
        for x in d['peores_dias'][:3]:
            print(f"      {x['fecha']}   {x['desvio']:>12,.2f}")

    if r['sin_cambios']:
        print("\nLos pagos ya reflejan las posiciones. No hay nada que regenerar.")
        return
    if solo_preview:
        print("\nEsto es solo la previsualización. Con --regenerar se escribe.")
        return

    if not si:
        print("\nEsto reescribe los pagos generados que el dashboard está aplicando.")
        print("Respaldo automático en pagos.csv.bak.")
        if input("Escribe «regenerar» para confirmar: ").strip().lower() != 'regenerar':
            print("Cancelado.")
            return

    resultado = corte.regenerar()
    if not resultado['ok']:
        print(f"\nNo se regeneró: {resultado.get('error')}")
        return
    print(f"\nRegenerado: {resultado['pagos_borrados']} pagos borrados, "
          f"{resultado['pagos_escritos']} escritos.")
    _tabla(corte.estado())


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
    grupo.add_argument('--regenerar', action='store_true')
    grupo.add_argument('--regenerar-preview', action='store_true', dest='regenerar_preview')
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
    elif args.regenerar or args.regenerar_preview:
        regenerar(args.si, solo_preview=args.regenerar_preview)
    else:
        print(f"{corte.limpiar_sombra()} grupos sombra borrados.")
