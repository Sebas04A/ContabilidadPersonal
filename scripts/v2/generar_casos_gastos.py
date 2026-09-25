"""
Casos de paridad de la fase 9 (deudas/PLAN_MULTIUSUARIO.md §4.8): lo que calcula el SQL
(que manda) y lo que tiene que calcular igual la app sin conexión.

    reparto_casos.json        `_repartir` y `_partes_gasto`  ↔ lib/dominio/reparto.dart
    saldos_grupo_casos.json   grupos al azar y sus pares    ↔ lib/dominio/saldos_grupo.dart

Corre contra el stack LOCAL (`supabase start` en deudas/v2), cada caso dentro de una
transacción que se deshace: no deja nada en la base. Escribe en
deudas/flutter_app/test/fixtures/. Los tests de Dart los leen; si cambia el SQL, se
regeneran con:

    contabilidad/backend/.venv/bin/python scripts/v2/generar_casos_gastos.py [--semilla N]

Usa `psql` DENTRO del contenedor de la base (en el host no hay psql, §6.2), porque un caso
son muchas sentencias en una transacción y `supabase db query` ejecuta una sola.
"""
import argparse
import json
import os
import random
import subprocess

from _comun import RAIZ

CONTENEDOR = "supabase_db_deudas_v2"
FIXTURES = os.path.join(RAIZ, "deudas", "flutter_app", "test", "fixtures")
MODOS = ["igual", "montos", "porcentaje", "partes"]


def psql(sql):
    """Corre `sql` en la base local y devuelve las filas (modo -t -A)."""
    r = subprocess.run(["podman", "exec", "-i", CONTENEDOR, "psql", "-U", "postgres", "-X", "-q",
                        "-t", "-A", "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise SystemExit(f"psql falló:\n{r.stderr}")
    return [l for l in r.stdout.splitlines() if l.strip()]


def lit(v):
    return "'" + json.dumps(v).replace("'", "''") + "'"


# ------------------------------------------------------------------------------------
# Reparto
# ------------------------------------------------------------------------------------

def casos_reparto(rnd):
    fijos = [
        (100, [1, 1, 1], 0), (100, [1, 1, 1], 2), (100, [1, 1, 1], None), (0.05, [1, 1, 1], 1),
        (100, [2, 1, 1], None), (10, [33.33, 33.33, 33.34], 0), (42.42, [1], 0), (0.01, [1, 1], 1),
        (99.99, [1, 1, 1, 1, 1, 1, 1], 3), (1, [1.5, 2.25, 0.3333], 1), (1234.56, [7, 3], None),
    ]
    rep = [{"monto": m, "pesos": w, "primero": p} for m, w, p in fijos]
    for _ in range(150):
        n = rnd.randint(1, 8)
        modo = rnd.choice(["enteros", "decimales", "porcentaje"])
        if modo == "enteros":
            pesos = [rnd.randint(1, 5) for _ in range(n)]
        elif modo == "decimales":
            pesos = [round(rnd.uniform(0.0001, 9), 4) for _ in range(n)]
        else:
            cortes = sorted(rnd.sample(range(1, 10000), n - 1)) if n > 1 else []
            bordes = [0] + cortes + [10000]
            pesos = [(bordes[i + 1] - bordes[i]) / 100 for i in range(n)]
        rep.append({"monto": round(rnd.uniform(0.01, 2000), 2), "pesos": pesos,
                    "primero": rnd.choice([None] + list(range(n)))})

    partes = []
    for _ in range(200):
        n = rnd.randint(2, 7)
        modo = rnd.choice(MODOS)
        pagador = rnd.randrange(n)
        participa = [True] * n
        if rnd.random() < 0.3:
            participa[pagador] = False
        if modo == "montos":
            centavos = [rnd.randint(1, 20000) for _ in range(n)]
            pesos = [c / 100 if participa[k] else None for k, c in enumerate(centavos)]
            monto = round(sum(p for p in pesos if p is not None), 2)
        elif modo == "porcentaje":
            k_part = [k for k in range(n) if participa[k]]
            cortes = sorted(rnd.sample(range(1, 10000), len(k_part) - 1)) if len(k_part) > 1 else []
            bordes = [0] + cortes + [10000]
            pesos = [None] * n
            for j, k in enumerate(k_part):
                pesos[k] = (bordes[j + 1] - bordes[j]) / 100
            monto = round(rnd.uniform(0.01, 3000), 2)
        else:
            pesos = [(1 if modo == "igual" else rnd.randint(1, 4)) if participa[k] else None for k in range(n)]
            monto = round(rnd.uniform(0.01, 3000), 2)
        # Rechazos: nunca todos los que participan (eso lo resuelve el estado del gasto).
        rech = [participa[k] and rnd.random() < 0.25 for k in range(n)]
        if all(rech[k] or not participa[k] for k in range(n)):
            rech = [False] * n
        filas = [{"peso": pesos[k], "rechazada": rech[k]} for k in range(n)]
        partes.append({"monto": monto, "modo": modo, "pagador": pagador, "filas": filas})

    # Una consulta por caso: psql devuelve una línea por cada una, en orden.
    consultas = [
        f"SELECT to_json(_repartir({c['monto']}, ARRAY[{', '.join(str(w) for w in c['pesos'])}]::numeric[], "
        f"{'NULL' if c['primero'] is None else c['primero'] + 1}));" for c in rep
    ] + [
        f"SELECT to_json(_partes_gasto({c['monto']}, '{c['modo']}', {lit(c['filas'])}::jsonb, {c['pagador'] + 1}));"
        for c in partes
    ]
    salida = [json.loads(l) for l in psql("\n".join(consultas))]
    assert len(salida) == len(rep) + len(partes)
    for c, r in zip(rep + partes, salida):
        c["resultado"] = r
    return {"repartir": rep, "partes": partes}


# ------------------------------------------------------------------------------------
# Saldos de un grupo
# ------------------------------------------------------------------------------------

U = [f"{i}0000000-0000-0000-0000-000000000000" for i in (1, 2, 3)]   # con app
M = [f"9{i}000000-0000-0000-0000-00000000000{i}" for i in range(1, 6)]  # m1..m3 = U, m4 y m5 personas
G = "90000000-0000-0000-0000-000000000000"


def como(k):
    return (f"SELECT set_config('request.jwt.claims', "
            f"'{{\"sub\":\"{U[k]}\",\"role\":\"authenticated\"}}', true);")


def caso_grupo(rnd, n_caso):
    s = ["BEGIN;",
         "INSERT INTO auth.users (id, email, aud, role, raw_user_meta_data) VALUES " + ", ".join(
             f"('{u}', 'u{i}@caso.local', 'authenticated', 'authenticated', '{{\"nombre\":\"U{i}\"}}')"
             for i, u in enumerate(U, 1)) + ";",
         # Los miembros con app se insertan directo (ids fijos): lo que se prueba son los saldos.
         f"INSERT INTO grupos (id, creado_por, nombre) VALUES ('{G}', '{U[0]}', 'Caso {n_caso}');",
         "INSERT INTO grupo_miembros (id, grupo_id, usuario_id, nombre) VALUES " + ", ".join(
             [f"('{M[i]}', '{G}', '{U[i]}', 'U{i + 1}')" for i in range(3)]
             + [f"('{M[i]}', '{G}', NULL, 'P{i + 1}')" for i in (3, 4)]) + ";",
         "SET LOCAL ROLE authenticated;"]
    app = {M[i]: i for i in range(3)}   # miembro → índice de usuario

    gastos = []
    for x in range(rnd.randint(3, 12)):
        gid = f"98{n_caso:02d}{x:04d}-0000-0000-0000-000000000000"
        n = rnd.randint(2, 5)
        miembros = rnd.sample(M, n)
        pagador = rnd.randrange(n)
        participa = [True] * n
        if rnd.random() < 0.25:
            participa[pagador] = False
        if sum(participa[k] for k in range(n) if k != pagador) == 0:
            participa = [True] * n
        modo = rnd.choice(MODOS)
        if modo == "montos":
            pesos = [rnd.randint(1, 9000) / 100 if participa[k] else None for k in range(n)]
            monto = round(sum(p for p in pesos if p is not None), 2)
        elif modo == "porcentaje":
            kp = [k for k in range(n) if participa[k]]
            cortes = sorted(rnd.sample(range(1, 10000), len(kp) - 1)) if len(kp) > 1 else []
            bordes = [0] + cortes + [10000]
            pesos = [None] * n
            for j, k in enumerate(kp):
                pesos[k] = (bordes[j + 1] - bordes[j]) / 100
            monto = rnd.randint(1, 50000) / 100
        else:
            pesos = [rnd.randint(1, 3) if participa[k] else None for k in range(n)]
            monto = rnd.randint(1, 50000) / 100
        filas = []
        for k in range(n):
            f = {"miembro_id": miembros[k], "pagado": monto if k == pagador else 0}
            if not participa[k]:
                f["participa"] = False
            elif modo != "igual":
                f["peso"] = pesos[k]
            filas.append(f)
        creador = app.get(miembros[pagador], 0)
        s.append(como(creador))
        s.append(f"SELECT 1 FROM crear_gasto('{gid}', '{G}', 'Gasto {x}', {monto}, '2026-08-01', "
                 f"'{modo}', {lit(filas)}::jsonb);")
        gastos.append((gid, miembros, participa))

    # Rechazos al azar de quien tiene app (a veces quien pagó: se rechaza entero).
    for gid, miembros, participa in gastos:
        if rnd.random() < 0.35:
            quienes = [m for k, m in enumerate(miembros) if m in app]
            if quienes:
                s.append(como(app[rnd.choice(quienes)]))
                s.append(f"SELECT 1 FROM rechazar_parte('{gid}', 'no');")

    # Pagos al azar: los anota quien corresponde y a veces se confirman o rechazan.
    for p in range(rnd.randint(0, 8)):
        de, para = rnd.sample(M, 2)
        # Lo anota una de sus dos puntas con app (si ninguna tiene, cualquiera): si es quien
        # entrega a alguien con app, queda por confirmar.
        quien = rnd.choice([app[x] for x in (para, de) if x in app] or [0])
        pid = f"97{n_caso:02d}{p:04d}-0000-0000-0000-000000000000"
        s.append(como(quien))
        s.append(f"SELECT 1 FROM registrar_pago_grupo('{pid}', '{G}', '{de}', '{para}', "
                 f"{rnd.randint(1, 20000) / 100}, '2026-08-02');")
        if para in app and quien != app[para]:
            r = rnd.random()
            if r < 0.4:
                s.append(como(app[para]))
                s.append(f"SELECT 1 FROM confirmar_pago_grupo('{pid}');")
            elif r < 0.6:
                s.append(como(app[para]))
                s.append(f"SELECT 1 FROM rechazar_pago_grupo('{pid}', 'no');")

    s.append(como(0))
    s.append(f"SELECT json_build_object('gastos', cambios_gastos() -> 'gastos', 'pagos', cambios_gastos() -> 'pagos', "
             f"'pares', estado_grupo('{G}') -> 'pares', 'miembros', estado_grupo('{G}') -> 'miembros');")
    s.append("ROLLBACK;")
    filas = [l for l in psql("\n".join(s)) if l.startswith('{"gastos"')]
    return json.loads(filas[-1])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--semilla", type=int, default=20260924)
    ap.add_argument("--grupos", type=int, default=40, help="cuántos grupos al azar")
    args = ap.parse_args()
    rnd = random.Random(args.semilla)

    os.makedirs(FIXTURES, exist_ok=True)
    reparto = casos_reparto(rnd)
    with open(os.path.join(FIXTURES, "reparto_casos.json"), "w", encoding="utf-8") as f:
        json.dump({"semilla": args.semilla, **reparto}, f, ensure_ascii=False, indent=1)
    print(f"reparto: {len(reparto['repartir'])} casos de _repartir y {len(reparto['partes'])} de _partes_gasto")

    grupos = [caso_grupo(rnd, i) for i in range(args.grupos)]
    with open(os.path.join(FIXTURES, "saldos_grupo_casos.json"), "w", encoding="utf-8") as f:
        json.dump({"semilla": args.semilla, "grupos": grupos}, f, ensure_ascii=False, indent=1)
    pares = sum(len(g["pares"]) for g in grupos)
    print(f"saldos: {len(grupos)} grupos, {sum(len(g['gastos']) for g in grupos)} gastos, {pares} pares")


if __name__ == "__main__":
    main()
