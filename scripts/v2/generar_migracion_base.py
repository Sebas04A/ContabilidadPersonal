"""
Genera la migración base de v2 a partir del volcado del esquema de producción.

    contabilidad/backend/.venv/bin/python scripts/v2/generar_migracion_base.py <volcado.sql> <salida.sql>

El volcado sale de `supabase db dump --linked --schema public` (fase 0.3 del plan). La base
de v2 tiene que ser una copia FIEL de producción, así que solo se quita lo que abre la
base a cualquiera:

  * las policies `USING (true)` (el RLS de verdad llega en la fase 1; mientras tanto, con
    RLS activo y sin policies, solo `service_role` y `postgres` ven las tablas);
  * los GRANT y DEFAULT PRIVILEGES a `anon`.

Y se agrega un REVOKE explícito al final: la imagen de Supabase trae default privileges
que le conceden a `anon` todo lo nuevo en `public`, así que borrar los GRANT del volcado
no alcanza.
"""
import re
import sys

CABECERA = """\
-- Deudas v2 — migración base.
--
-- Copia fiel del esquema de producción (rcmdzvbxerumzxvnubfo) volcado el {fecha} con
-- `supabase db dump --linked --schema public`, generada por
-- scripts/v2/generar_migracion_base.py. NO editar a mano: los cambios van en migraciones
-- nuevas. Diferencias con producción (a propósito):
--   * sin las policies USING (true) ni los GRANT a anon (agujeros de seguridad, ver
--     deudas/PLAN_MULTIUSUARIO.md §1.5);
--   * REVOKE explícito a anon al final.

"""

REVOKE = """
-- ------------------------------------------------------------------------------------
-- Agregado por generar_migracion_base.py: anon no toca nada.
-- ------------------------------------------------------------------------------------
REVOKE ALL ON ALL TABLES IN SCHEMA "public" FROM "anon";
REVOKE ALL ON ALL SEQUENCES IN SCHEMA "public" FROM "anon";
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA "public" FROM "anon", PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON TABLES FROM "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON SEQUENCES FROM "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON FUNCTIONS FROM "anon", PUBLIC;
"""


def main():
    origen, salida, *resto = sys.argv[1:]
    fecha = resto[0] if resto else "2026-09-23"
    texto = open(origen, encoding="utf-8").read()

    # Los GRANT son de una línea cada uno, pero van pegados a los de authenticated y
    # service_role: se quitan línea por línea.
    lineas = texto.split("\n")
    grant_anon = re.compile(r'^(GRANT|ALTER DEFAULT PRIVILEGES) .* TO "anon";$')
    quitados = {"grant_anon": sum(1 for l in lineas if grant_anon.match(l)), "policy": 0}
    texto = "\n".join(l for l in lineas if not grant_anon.match(l))

    # Las policies ocupan varias líneas y el volcado las separa con una línea en blanco.
    quedan = []
    for b in re.split(r"\n\s*\n", texto):
        if b.strip().startswith("CREATE POLICY"):
            quitados["policy"] += 1
            continue
        quedan.append(b)

    with open(salida, "w", encoding="utf-8") as f:
        f.write(CABECERA.format(fecha=fecha))
        f.write("\n\n".join(quedan).rstrip() + "\n")
        f.write(REVOKE)
    print(f"{quitados['policy']} policies y {quitados['grant_anon']} grants a anon quitados → {salida}")


if __name__ == "__main__":
    main()
