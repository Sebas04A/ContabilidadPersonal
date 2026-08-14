"""
snapshot_dashboard.py — Red de seguridad para tocar el dashboard
================================================================

El dashboard es de solo lectura, pero su salida es el patrimonio: si un refactor
la mueve un centavo, hay que enterarse en el acto y no tres commits después.

Este script congela la respuesta de /chart-data y /variations (en sus dos
variantes de `incluir_inversiones`) y luego la compara contra la actual.

    # antes de tocar nada
    python scripts/snapshot_dashboard.py capturar --nombre baseline

    # después de los cambios, con los filtros APAGADOS
    python scripts/snapshot_dashboard.py comparar --nombre baseline

Con los filtros apagados la salida tiene que ser idéntica hasta el centavo. Ese
es todo el contrato: la ruta sin filtro no cambia de comportamiento.

Dos modos, y el que se usa para capturar tiene que ser el mismo que para
comparar:

  --via http    (por defecto) le pega al backend que ya está corriendo. Es el
                autoritativo: corre con el entorno real, así que DEUDA_ACUMULADA
                trae los datos de Supabase de verdad.
  --via directo importa el servicio en este intérprete. Sirve si no hay backend
                levantado, pero si al intérprete le falta `supabase` la deuda
                sale en cero y el snapshot queda ciego a ese componente.

Los snapshots viven en backups/dashboard_snapshots/ y no se versionan.
"""

import argparse
import json
import math
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

SNAP_DIR = os.path.join(_PROJECT_ROOT, "backups", "dashboard_snapshots")

# Un centavo. Por debajo de eso es ruido de coma flotante al serializar, no un
# cambio de cálculo.
TOLERANCIA = 0.005


def _construir_directo(incluir_inversiones: bool) -> dict:
    from contabilidad.backend.services.dashboard_service import (
        DashboardService,
        VariationsAnalyzer,
    )

    service = DashboardService()
    chart = service.get_chart_data(incluir_inversiones=incluir_inversiones)

    analyzer = VariationsAnalyzer()
    analyzer.fetch_all_drivers()
    variations = analyzer.analyze(chart.data)

    return {
        "chart_data": [p.model_dump() for p in chart.data],
        "highlighted_days": chart.highlighted_days,
        "metadata": chart.metadata,
        "variations": [v.model_dump() for v in variations],
    }


def _construir_http(incluir_inversiones: bool, base_url: str) -> dict:
    import urllib.request

    def _get(ruta: str):
        url = f"{base_url}{ruta}?incluir_inversiones={str(incluir_inversiones).lower()}"
        with urllib.request.urlopen(url, timeout=300) as r:
            return json.loads(r.read().decode("utf-8"))

    chart = _get("/api/dashboard/chart-data")
    return {
        "chart_data": chart["data"],
        "highlighted_days": chart["highlighted_days"],
        "metadata": chart.get("metadata"),
        "variations": _get("/api/dashboard/variations"),
    }


def _snapshot(via: str, base_url: str) -> dict:
    def construir(flag: bool) -> dict:
        if via == "http":
            return _construir_http(flag, base_url)
        return _construir_directo(flag)

    return {
        "_via": via,
        "sin_inversiones": construir(False),
        "con_inversiones": construir(True),
    }


def capturar(nombre: str, via: str, base_url: str) -> str:
    os.makedirs(SNAP_DIR, exist_ok=True)
    snap = _snapshot(via, base_url)
    ruta = os.path.join(SNAP_DIR, f"{nombre}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, sort_keys=True)

    for variante in ("sin_inversiones", "con_inversiones"):
        cuerpo = snap[variante]
        deuda = sum(abs(p.get("deuda_acumulada", 0.0)) for p in cuerpo["chart_data"])
        print(
            f"  {variante}: {len(cuerpo['chart_data'])} días, "
            f"{len(cuerpo['variations'])} variaciones, "
            f"deuda_acumulada {'presente' if deuda > 0 else 'EN CERO'}"
        )
    print(f"Snapshot guardado en {ruta} (via {via})")
    return ruta


def _difs(camino: str, viejo, nuevo, out: list) -> None:
    """Recorre las dos estructuras en paralelo y anota toda divergencia."""
    if len(out) >= 40:
        return

    if isinstance(viejo, dict) and isinstance(nuevo, dict):
        for k in sorted(set(viejo) | set(nuevo)):
            if k not in viejo:
                out.append(f"{camino}.{k}: apareció (={nuevo[k]!r})")
            elif k not in nuevo:
                out.append(f"{camino}.{k}: desapareció (era {viejo[k]!r})")
            else:
                _difs(f"{camino}.{k}", viejo[k], nuevo[k], out)
        return

    if isinstance(viejo, list) and isinstance(nuevo, list):
        if len(viejo) != len(nuevo):
            out.append(f"{camino}: largo {len(viejo)} -> {len(nuevo)}")
        for i in range(min(len(viejo), len(nuevo))):
            _difs(f"{camino}[{i}]", viejo[i], nuevo[i], out)
        return

    if isinstance(viejo, (int, float)) and isinstance(nuevo, (int, float)):
        if isinstance(viejo, bool) or isinstance(nuevo, bool):
            if viejo != nuevo:
                out.append(f"{camino}: {viejo!r} -> {nuevo!r}")
            return
        # NaN nunca es igual a sí mismo; aquí dos NaN son el mismo "sin dato".
        if math.isnan(viejo) and math.isnan(nuevo):
            return
        if not math.isclose(viejo, nuevo, abs_tol=TOLERANCIA):
            out.append(f"{camino}: {viejo} -> {nuevo}  (Δ {nuevo - viejo:+.4f})")
        return

    if viejo != nuevo:
        out.append(f"{camino}: {viejo!r} -> {nuevo!r}")


def comparar(nombre: str, via: str, base_url: str) -> int:
    ruta = os.path.join(SNAP_DIR, f"{nombre}.json")
    if not os.path.exists(ruta):
        print(f"No existe el snapshot {ruta}. Corré primero: capturar --nombre {nombre}")
        return 2

    with open(ruta, encoding="utf-8") as f:
        viejo = json.load(f)

    via_original = viejo.get("_via")
    if via_original and via_original != via:
        print(
            f"El snapshot se capturó via '{via_original}' y estás comparando via "
            f"'{via}'. Los dos modos no producen la misma salida (la deuda de "
            f"Supabase, entre otras). Volvé a correr con --via {via_original}."
        )
        return 2

    nuevo = _snapshot(via, base_url)

    difs: list = []
    _difs("", viejo, nuevo, difs)

    if not difs:
        print(f"IDÉNTICO a {nombre} (tolerancia ${TOLERANCIA}). La ruta sin filtro no cambió.")
        return 0

    print(f"DIVERGE de {nombre} — {len(difs)} diferencia(s)"
          f"{' (primeras 40)' if len(difs) >= 40 else ''}:\n")
    for d in difs:
        print(f"  {d}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="accion", required=True)
    for accion in ("capturar", "comparar"):
        p = sub.add_parser(accion)
        p.add_argument("--nombre", default="baseline")
        p.add_argument("--via", choices=("http", "directo"), default="http")
        p.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()

    if args.accion == "capturar":
        capturar(args.nombre, args.via, args.url)
        return 0
    return comparar(args.nombre, args.via, args.url)


if __name__ == "__main__":
    raise SystemExit(main())
