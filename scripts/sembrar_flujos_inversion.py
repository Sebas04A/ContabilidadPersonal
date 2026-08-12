"""
sembrar_flujos_inversion.py — Registra las salidas y entradas de dinero de los portafolios.

Cada vez que vence un certificado de `Inversiones_Uni` salen ~3.2xx que se van en
matrícula y no se reinvierten; en `Inversiones_Madre` pasó lo mismo con la matrícula que
se separó en 2024-11 y con los dos retiros de diciembre de 2025. Todo eso estaba
registrado **solo como la fecha de fin de un pago fijo** — información que el generador de
la neutralización no puede ver, porque ninguna de las dos puntas es una operación de
certificado y el banco no la delata.

Las fechas y los montos no son inventados: son las fechas de fin y los importes de los
pagos que ya estaban escritos a mano en `pagos.csv`. Es la contabilidad del usuario
diciendo cuándo se fue cada pedazo; esto solo la traduce a algo que el sistema entiende.

Idempotente: cada flujo lleva un id fijo, así que correrlo dos veces no duplica nada y
`--rehacer` sabe exactamente qué borrar.

    python scripts/sembrar_flujos_inversion.py --preview
    python scripts/sembrar_flujos_inversion.py --aplicar
    python scripts/sembrar_flujos_inversion.py --rehacer
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contabilidad.backend.services.investments import posiciones  # noqa: E402
from contabilidad.backend.storage.investments_storage import InvestmentStorage  # noqa: E402


#: (id fijo, portafolio, fecha, monto, dirección, motivo)
FLUJOS = [
    # `Uni` — la fila vieja de 3.177 termina el 2024-03-18: no es una base permanente,
    # es plata que se acabó ese día.
    ('flujo-uni-2024-03-18', 'Inversiones_Uni',   '2024-03-18', 3177.00, 'salida',  'Se acaba el saldo viejo'),
    # De estos 3.834,64 el usuario tenía etiquetados 3.228 como «madre terjeta»; el resto
    # es la parte del tramo que tampoco se reinvirtió. Se registra junto porque lo que el
    # residual necesita saber es cuánto salió, no en qué se gastó cada pedazo.
    ('flujo-uni-2024-09-23', 'Inversiones_Uni',   '2024-09-23', 3834.64, 'salida',  'Matrícula 2024-2 (incluye 3.228 de «madre terjeta»)'),
    ('flujo-uni-2024-11-18', 'Inversiones_Uni',   '2024-11-18', 3635.07, 'entrada', 'Plata que entra de fuera'),
    ('flujo-uni-2025-04-28', 'Inversiones_Uni',   '2025-04-28', 3213.00, 'salida',  'Matrícula 2025-1'),
    ('flujo-uni-2025-10-24', 'Inversiones_Uni',   '2025-10-24', 3267.00, 'salida',  'Matrícula 2025-2'),
    ('flujo-uni-2026-04-29', 'Inversiones_Uni',   '2026-04-29', 3279.00, 'salida',  'Matrícula 2026-1'),
    ('flujo-uni-2026-05-18', 'Inversiones_Uni',   '2026-05-18', 1000.00, 'salida',  'Matrícula 2026-1'),
    # `Madre` — la matrícula que se separó para pagar después, y los dos retiros.
    ('flujo-madre-2024-11-18', 'Inversiones_Madre', '2024-11-18', 3533.84, 'salida', 'Matrícula separada para pagar'),
    ('flujo-madre-2025-12-26', 'Inversiones_Madre', '2025-12-26', 4900.00, 'salida', 'Retiro'),
    ('flujo-madre-2025-12-29', 'Inversiones_Madre', '2025-12-29', 4900.00, 'salida', 'Retiro'),
    # El sobrante del último ciclo. La fila «Lo que sobra» termina el 2026-03-02, así que
    # esa es la fecha en que se fue. 648,21 es el residual derivado; a mano está escrito
    # 647 y la diferencia es el redondeo de siempre.
    ('flujo-madre-2026-03-02', 'Inversiones_Madre', '2026-03-02',  648.21, 'salida', 'Lo que sobra'),
]


def _por_nombre():
    return {p['name']: p['id'] for p in posiciones.list_portfolios()}


def _diagnostico(titulo: str) -> None:
    p = posiciones.get_neutralization_preview()
    print(f"\n{titulo}")
    for d in p['por_portafolio']:
        estado = 'CUADRA' if d['cuadra'] else 'no cuadra'
        print(f"  {d['nombre']:<20} {d['dias_materiales']:>4} de {d['dias']:>5} días   "
              f"máx {d['max_desvio']:>11,.2f}   {estado}")


def preview() -> None:
    nombres = _por_nombre()
    print(f"{'id':<24} {'portafolio':<20} {'fecha':<12} {'monto':>10}  dirección  motivo")
    total = 0.0
    for fid, portafolio, fecha, monto, direccion, nota in FLUJOS:
        existe = ' (ya existe)' if InvestmentStorage.get_position(fid) else ''
        falta = ' (PORTAFOLIO NO ENCONTRADO)' if portafolio not in nombres else ''
        signo = -1 if direccion == 'salida' else 1
        total += signo * monto
        print(f"{fid:<24} {portafolio:<20} {fecha:<12} {monto:>10,.2f}  "
              f"{direccion:<9}  {nota}{existe}{falta}")
    print(f"\n{len(FLUJOS)} flujos; efecto neto sobre los residuales: {total:,.2f}")
    _diagnostico("Estado actual de la neutralización:")


def aplicar() -> None:
    nombres = _por_nombre()
    faltantes = {p for _, p, *_ in FLUJOS} - set(nombres)
    if faltantes:
        raise SystemExit(f"No existen estos portafolios: {', '.join(sorted(faltantes))}")

    _diagnostico("ANTES:")
    creados = 0
    for fid, portafolio, fecha, monto, direccion, nota in FLUJOS:
        if InvestmentStorage.get_position(fid):
            print(f"  = {fid} ya existe, se salta")
            continue
        posiciones.registrar_flujo(
            portafolio_id=nombres[portafolio], fecha=fecha, monto=monto,
            direccion=direccion, nota=nota, position_id=fid,
        )
        print(f"  + {fid}  {portafolio:<20} {fecha}  {monto:>10,.2f}  {direccion}")
        creados += 1

    print(f"\n{creados} flujos registrados.")
    _diagnostico("DESPUÉS:")


def rehacer() -> None:
    borrados = sum(1 for fid, *_ in FLUJOS if posiciones.delete_position(fid))
    print(f"{borrados} flujos borrados.")
    _diagnostico("Estado tras deshacer:")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--preview', action='store_true', help='muestra qué se escribiría')
    grupo.add_argument('--aplicar', action='store_true', help='escribe los flujos que falten')
    grupo.add_argument('--rehacer', action='store_true', help='borra los flujos sembrados')
    args = parser.parse_args()

    if args.preview:
        preview()
    elif args.aplicar:
        aplicar()
    else:
        rehacer()
