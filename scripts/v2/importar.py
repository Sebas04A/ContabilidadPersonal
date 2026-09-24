"""
Importa un respaldo JSON (de `backup_completo.py`) a la base v2, conservando TODO.

    contabilidad/backend/.venv/bin/python scripts/v2/importar.py \
        --origen backups/deudas_v2_origen_<fecha> --destino local [--owner <uuid>]

Conserva cada columna tal cual: `id` (etiquetas.csv de contabilidad apunta a los UUID de
producción), `created_at` (es parte del orden FIFO: pisarlo cambia qué deuda queda a
medias), `cruce_id`, `idem_key`, `nota` y las bitácoras de edición.

`--owner` (fase 1 en adelante, obligatorio desde entonces): pone ese `owner_id` en todas
las filas. El usuario tiene que existir antes (`crear_usuario.py`).

Idempotente: `ON CONFLICT (id) DO NOTHING`. Todo va en un solo bloque DO: o entra el
respaldo entero o no entra nada.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comun import RAIZ, TABLAS, Cliente, conexion, sql  # noqa: E402

ETIQUETA = "$respaldo$"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origen", required=True)
    ap.add_argument("--destino", required=True, choices=["local", "nube"])
    ap.add_argument("--owner", help="UUID del usuario dueño de todo el respaldo")
    ap.add_argument("--solo-sql", action="store_true", help="escribe el SQL y no lo ejecuta")
    a = ap.parse_args()

    origen = a.origen if os.path.isabs(a.origen) else os.path.join(RAIZ, a.origen)
    conteos = json.load(open(os.path.join(origen, "_conteos.json"), encoding="utf-8"))

    # `supabase db query` manda una sola sentencia (protocolo extendido), así que no sirve
    # BEGIN/COMMIT: todo va dentro de un DO, que es atómico igual.
    # `deudas.en_rpc` (fase 6): los triggers dejan pasar `estado_acuerdo` y `origen_id` tal
    # como vienen. Un respaldo de v1 no los trae (todo nace 'local'); uno de v2 sí, y sin
    # esto se perderían.
    partes = ["DO $importar$\nBEGIN\nPERFORM set_config('deudas.en_rpc', 'on', true);"]
    for tabla in TABLAS:
        filas = json.load(open(os.path.join(origen, f"{tabla}.json"), encoding="utf-8"))
        if a.owner:
            for f in filas:
                f["owner_id"] = a.owner
        crudo = json.dumps(filas, ensure_ascii=False)
        if ETIQUETA in crudo:
            sys.exit(f"{tabla}: el respaldo contiene {ETIQUETA}; cambia la etiqueta de comillas.")
        if not filas:
            continue
        # Solo las columnas que trae el respaldo: las que v2 agregó (updated_at, …) toman
        # su DEFAULT. Con SELECT * llegarían como NULL explícito.
        cols = ", ".join(f'"{c}"' for c in filas[0])
        partes.append(
            f'INSERT INTO public."{tabla}" ({cols})\n'
            f'SELECT {cols} FROM jsonb_populate_recordset(NULL::public."{tabla}", {ETIQUETA}{crudo}{ETIQUETA})\n'
            f"ON CONFLICT (id) DO NOTHING;")
    partes.append("END\n$importar$;")

    archivo = os.path.join(origen, f"_importar_{a.destino}.sql")
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("\n\n".join(partes) + "\n")
    print(f"SQL en {archivo}")
    if a.solo_sql:
        return

    sql(a.destino, archivo)

    # Comprobación: los conteos del destino tienen que ser los del respaldo.
    cli = Cliente(*conexion(a.destino))
    mal = False
    for tabla in TABLAS:
        hay = len(cli.tabla(tabla, select="id"))
        ok = hay == conteos[tabla]
        mal |= not ok
        print(f"  {'✓' if ok else '✗'} {tabla:16} {hay:5} (respaldo {conteos[tabla]})")
    if mal:
        sys.exit("Los conteos no coinciden.")
    print("Importación completa.")


if __name__ == "__main__":
    main()
