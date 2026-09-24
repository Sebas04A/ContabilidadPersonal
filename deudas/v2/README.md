# Deudas v2

Proyecto Supabase nuevo de la app de deudas, multiusuario. El plan completo, con el estado
de cada fase, está en [`../PLAN_MULTIUSUARIO.md`](../PLAN_MULTIUSUARIO.md). **Léelo antes de
tocar nada aquí.**

La base de producción actual (`../supabase/`, ref `rcmdzvbxerumzxvnubfo`) no se toca desde
este directorio.

## Levantar el stack local

```bash
systemctl --user enable --now podman.socket                 # una sola vez
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
env -C deudas/v2 ~/.local/bin/supabase start                # API :54321, DB :54322, Studio :54323
env -C deudas/v2 ~/.local/bin/supabase status               # keys locales
env -C deudas/v2 ~/.local/bin/supabase stop                 # apagar (conserva los datos)
```

En `supabase/config.toml` están apagados Realtime, Storage y Analytics: la app no los usa,
y el colector de logs de Analytics no funciona con Podman rootless.

## Rehacer la base local con los datos reales

```bash
PY=contabilidad/backend/.venv/bin/python
env -C deudas/v2 ~/.local/bin/supabase db reset             # aplica supabase/migrations/
OWNER=$($PY scripts/v2/crear_usuario.py --destino local \
          --email dueno@deudas.local --clave dueno-local-123 --nombre Sebas)
$PY scripts/v2/importar.py --origen backups/deudas_v2_origen_<fecha> --destino local --owner $OWNER
$PY scripts/v2/comparar_linea_base.py backups/estado_cuenta_baseline_v2_<fecha> --destino local \
    --email dueno@deudas.local --clave dueno-local-123
```

`db reset` borra todo, incluidos los usuarios, así que después hay que volver a crearlos e
importar. Las credenciales de arriba son **solo del stack local**.

## Probar

```bash
env -C deudas/v2 ~/.local/bin/supabase test db              # pgTAP: RLS, RPC, vínculos, conciliación, propuestas, fase 7 (231)
$PY scripts/v2/probar_rpc_v2.py --destino local             # pruebas end-to-end de v1, como usuario de prueba
$PY scripts/v2/probar_concurrencia_propuestas.py            # fase 6: dos sesiones a la vez
$PY scripts/v2/probar_fase7.py                              # fase 7: exportar, límites, borrar la cuenta
$PY scripts/v2/comparar_edges.py --destino local --email dueno@deudas.local --clave dueno-local-123
```

## Proyecto en la nube

"Deudas v2", ref `ggzvxehcsorlbroucbkp` (plan gratuito, us-east-2). Este directorio ya está
enlazado (`supabase/.temp/project-ref`), así que `--linked` apunta ahí. Los secretos
(contraseña de la base, keys) están en `deudas/v2/.env`, que **no se versiona**. Qué hay
desplegado, cómo desplegar y las trampas (en modo agente `config push` aplica sin
preguntar): [`../PLAN_MULTIUSUARIO.md` §6.4](../PLAN_MULTIUSUARIO.md).

Los scripts aceptan `--destino nube`:

```bash
$PY scripts/v2/probar_rpc_v2.py --destino nube
SUPABASE_DB_PASSWORD=… ~/.local/bin/supabase test db --linked --workdir deudas/v2
```

## Edge functions

| Función | Sesión | Qué hace |
|---|---|---|
| `get_estado_cuenta` | JWT del usuario | Estado de cuenta de un deudor propio, punto de vista del dueño |
| `get_historial` | JWT del usuario | Historial de un deudor propio |
| `visor` | ninguna | `{token, accion: deudor\|estado\|historial}`: lo que ve el deudor por su enlace. 60 consultas por minuto e IP (429 después) |
| `borrar_cuenta` | JWT del usuario | `{confirmar: "BORRAR"}`: rompe sus vínculos (`preparar_baja`) y borra el usuario de Auth con la service_role; la cascada se lleva la libreta |

La lógica compartida está en `functions/_shared/`, copiada de las edges de v1.

En local, el runtime de edges no ve una función **nueva** ni siempre recarga una editada:
`podman restart supabase_edge_runtime_deudas_v2`.

## Privacidad

Borrador de la política de privacidad (fase 7.2, sin publicar): [`POLITICA_PRIVACIDAD.md`](POLITICA_PRIVACIDAD.md).

## Scripts (`scripts/v2/`)

| Script | Qué hace |
|---|---|
| `backup_completo.py [--destino prod\|local\|nube]` | Respaldo JSON de las 6 tablas (incluye las bitácoras de edición). Solo lee |
| `capturar_linea_base.py` | `estado_cuenta` de cada deudor en los dos puntos de vista. Solo lee |
| `generar_migracion_base.py <volcado> <salida>` | Arma `migrations/*_base.sql` desde `supabase db dump` (quita policies `USING (true)` y grants a anon) |
| `importar.py --origen … --destino local\|nube [--owner uuid]` | Importa un respaldo conservando ids y `created_at`. Idempotente, todo o nada |
| `comparar_linea_base.py <carpeta> --destino … [--email --clave]` | Compara `estado_cuenta` contra la línea base, byte a byte |
| `crear_usuario.py --destino … --email --clave [--nombre]` | Crea (o encuentra) un usuario de Auth confirmado e imprime su UUID |
| `comparar_edges.py --destino … --email --clave` | Edges de v2 contra las de producción, deudor por deudor |
| `probar_rpc_v2.py --destino …` | Corre `scripts/probar_*.py` de v1 contra v2 como usuario de prueba |
| `medir_conciliacion.py --email --clave` | Mide los pares de `candidatos_conciliacion` con un deudor real (solo local) |
| `probar_concurrencia_propuestas.py [--destino …] [--rondas N] [--semilla S] [--conservar]` | Dos cuentas temporales vinculadas se pagan y se aceptan/rechazan propuestas a la vez; comprueba la invariante y el cuadre de las dos libretas |
| `probar_fase7.py [--destino …]` | Fase 7 por la API real: exportar, canje con código malo (null), límite del visor y borrar la cuenta. Crea y borra dos cuentas |
| `verificar_vinculos.py [--destino …]` | `verificar_vinculo()` sobre todos los vínculos vivos, con la key de servicio. Sale con 1 si alguno no cuadra |

Los datos reales (respaldos y líneas base) viven en `backups/`, que está fuera de git.
Nunca van a este directorio.
