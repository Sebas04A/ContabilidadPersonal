"""
Siembra en Supabase el árbol de casos de `contabilidad/debts/casos_arbol.py`.

Cada caso queda como un deudor `ARBOL <code> · <descripción>`, con sus deudas, pagos y
asignaciones. Sirve para revisar a ojo (app, visor y modal de React) todas las
combinaciones de debe/debo y pagos.

    python scripts/seed_arbol_deudas.py --nivel 4        # siembra hasta el nivel 4
    python scripts/seed_arbol_deudas.py --clean          # borra los ARBOL
    python scripts/seed_arbol_deudas.py --clean-test     # borra TEST y Persona Prueba
    python scripts/seed_arbol_deudas.py --verificar      # contrasta contra estado_cuenta()

Los ids son determinísticos: volver a sembrar reemplaza, no duplica.
"""
import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, ".")

SUPABASE_URL = "https://rcmdzvbxerumzxvnubfo.supabase.co"
SUPABASE_KEY = "sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw"
HEAD = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"}
PREFIJO = "ARBOL"
LOTE = 400


def pedir(metodo, path, cuerpo=None, prefer=None):
    h = dict(HEAD)
    if prefer:
        h["Prefer"] = prefer
    data = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", data=data,
                                 headers=h, method=metodo)
    with urllib.request.urlopen(req, timeout=120) as r:
        crudo = r.read()
        return json.loads(crudo) if crudo else None


def uid(*partes):
    h = hashlib.md5("|".join(partes).encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def en_lotes(tabla, filas):
    for i in range(0, len(filas), LOTE):
        pedir("POST", tabla, filas[i:i + LOTE], prefer="resolution=merge-duplicates")
        print(f"    {tabla}: {min(i + LOTE, len(filas))}/{len(filas)}", end="\r")
    if filas:
        print(f"    {tabla}: {len(filas)} filas          ")


def borrar_por_prefijo(patron, etiqueta):
    # El patrón puede llevar espacios ("Persona Prueba*"): hay que escaparlo.
    victimas = pedir("GET",
                     f"deudores?select=id,nombre&nombre=like.{urllib.parse.quote(patron)}")
    if not victimas:
        print(f"  no hay deudores {etiqueta}")
        return 0
    print(f"  borrando {len(victimas)} deudores {etiqueta} (cascade)…")
    for i in range(0, len(victimas), 50):
        ids = ",".join(v["id"] for v in victimas[i:i + 50])
        pedir("DELETE", f"deudores?id=in.({ids})")
    print(f"  ✓ {len(victimas)} borrados")
    return len(victimas)


def quedarse_con(codes):
    """Deja en Supabase solo los casos ARBOL indicados y borra los demás."""
    quiero = {c.strip().upper() for c in codes if c.strip()}
    actuales = pedir("GET", f"deudores?select=id,nombre&nombre=like."
                            f"{urllib.parse.quote(PREFIJO + '*')}") or []

    def code_de(nombre):
        partes = nombre.split(" ")
        return partes[1].upper() if len(partes) > 1 else ""

    sobran = [d for d in actuales if code_de(d["nombre"]) not in quiero]
    quedan = sorted(code_de(d["nombre"]) for d in actuales
                    if code_de(d["nombre"]) in quiero)

    print(f"  hay {len(actuales)} casos sembrados · se quedan {len(quedan)} · "
          f"se borran {len(sobran)}")
    for i in range(0, len(sobran), 50):
        ids = ",".join(v["id"] for v in sobran[i:i + 50])
        pedir("DELETE", f"deudores?id=in.({ids})")
        print(f"    borrados {min(i + 50, len(sobran))}/{len(sobran)}", end="\r")

    faltan = sorted(quiero - set(quedan))
    print(f"\n  ✓ quedan {len(quedan)}: {', '.join(quedan)}")
    if faltan:
        print(f"  ⚠ pedidos que no estaban sembrados: {', '.join(faltan)}")
    return 0


def sembrar(nivel):
    from contabilidad.debts.casos_arbol import generar, listas_crudas

    casos = [c for c in generar() if c.nivel <= nivel]
    print(f"  {len(casos)} casos hasta el nivel {nivel}")

    deudores, deudas, pagos, detalles = [], [], [], []
    for c in casos:
        did = uid("arbol", c.code)
        titulo = (c.titulo or c.nombre or "")[:80]
        deudores.append({"id": did, "nombre": f"{PREFIJO} {c.code} · {titulo}"})

        cd, cp, cdet = listas_crudas(c)
        for d in cd:
            deudas.append({"id": uid(c.code, d["id"]), "deudor_id": did,
                           "titulo": d["titulo"], "monto": d["monto"],
                           "fecha_gasto": d["fecha_gasto"],
                           "es_mi_deuda": d["es_mi_deuda"]})
        for p in cp:
            pagos.append({"id": uid(c.code, p["id"]), "deudor_id": did,
                          "monto_total": p["monto_total"], "fecha_pago": p["fecha_pago"],
                          "es_mi_pago": p["es_mi_pago"],
                          "es_compensacion": p["es_compensacion"]})
        for a in cdet:
            detalles.append({"id": uid(c.code, a["pago_id"], a["deuda_id"]),
                             "pago_id": uid(c.code, a["pago_id"]),
                             "deuda_id": uid(c.code, a["deuda_id"]),
                             "monto_asignado": a["monto_asignado"]})

    # El orden importa por las claves foráneas.
    en_lotes("deudores", deudores)
    en_lotes("deudas", deudas)
    en_lotes("pagos", pagos)
    en_lotes("detalle_pagos", detalles)
    print(f"  ✓ {len(deudores)} deudores, {len(deudas)} deudas, "
          f"{len(pagos)} pagos, {len(detalles)} detalles")
    return casos


def verificar(casos):
    """Cada caso sembrado debe dar el neto que predice el árbol."""
    print(f"\n── Verificando {len(casos)} casos contra estado_cuenta() ──")
    fallos = []
    for i, c in enumerate(casos):
        if i % 50 == 0:
            print(f"  {i}/{len(casos)}", end="\r")
        est = pedir("POST", "rpc/estado_cuenta", {"p_deudor_id": uid("arbol", c.code)},
                    )
        if abs(float(est["resumen"]["neto"]) - c.neto) > 0.011:
            fallos.append((c.code, c.neto, est["resumen"]["neto"]))
    print(f"  {len(casos)} verificados · {len(fallos)} netos que no cuadran")
    for f in fallos[:15]:
        print(f"    ✗ {f[0]}: esperado {f[1]} · servidor {f[2]}")
    return not fallos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nivel", type=int, default=4)
    ap.add_argument("--clean", action="store_true", help="borra los deudores ARBOL")
    ap.add_argument("--clean-test", action="store_true",
                    help="borra los TEST y Persona Prueba")
    ap.add_argument("--verificar", action="store_true")
    ap.add_argument("--solo", help="deja únicamente estos casos, separados por coma "
                                   "(p. ej. --solo AS,AI,ASN). Borra el resto de ARBOL.")
    args = ap.parse_args()

    if args.solo:
        return quedarse_con(args.solo.replace(" ", ",").split(","))

    try:
        if args.clean_test:
            print("── Limpiando deudores de prueba viejos ──")
            borrar_por_prefijo("TEST*", "TEST")
            borrar_por_prefijo("Persona Prueba*", "Persona Prueba")

        if args.clean:
            print("── Limpiando el árbol ──")
            borrar_por_prefijo(f"{PREFIJO}*", PREFIJO)
            if not args.clean_test:
                return 0

        if args.clean and not args.clean_test:
            return 0

        print("── Sembrando el árbol ──")
        borrar_por_prefijo(f"{PREFIJO}*", PREFIJO)  # evita restos de una siembra previa
        casos = sembrar(args.nivel)

        if args.verificar:
            return 0 if verificar(casos) else 1
        return 0
    except urllib.error.HTTPError as e:
        print(f"\n✗ HTTP {e.code}: {e.read().decode()[:400]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
