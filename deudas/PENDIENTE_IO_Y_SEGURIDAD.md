# Deudas — trabajo pendiente: Disk IO y seguridad

> Estado a **2026-09-10**. Documento de traspaso: recoge una investigación completa del
> aviso de Disk IO de Supabase, lo que se aplicó, lo que quedó escrito sin aplicar, y dos
> agujeros de seguridad confirmados en vivo. Léelo entero antes de tocar nada.
>
> **Regla que puso el dueño: la app está en uso. No romper nada.** Todo lo pendiente se
> aplica por fases verificables, nunca de golpe.

Proyecto Supabase: `Deudas`, ref `rcmdzvbxerumzxvnubfo`, región `us-east-2`,
org gestionada por Vercel (`vercel_icfg_…`) ⇒ plan gratuito, compute **Nano**.

---

## 1. El disparador

Supabase envió un aviso de *"Your project is depleting its Disk IO Budget"*. El dueño usa
la app él solo, así que sospechaba de un bug. El 10-sep la base llegó a quedar
**completamente sin responder**: el gateway contestaba (`GET /rest/v1/` → 401 en 0,27 s)
pero cualquier consulta que tocara Postgres agotaba el tiempo de espera a los 40 s.

### Cronología reconstruida de los logs

| Momento (UTC) | Qué pasó |
|---|---|
| 09-sep 18:01 | primeros `Warp server error: Thread killed by timeout manager` (PostgREST) |
| 09-sep 18:00 → 10-sep 06:38 | esporádicos, cada pocas horas |
| 10-sep 11:47 | empiezan los `statement timeout` en serie, ~23/hora sin parar |
| 10-sep 15:00 | 503/504 continuos: la instancia deja de responder |
| 10-sep ~16:50 | **Restart project** manual → recuperada, respuestas en 0,25 s |

La degradación arrancó menos de una hora después de aplicar
`20260909120000_cruce_cede_ante_pago_manual.sql` (los backups previos a esa migración son
de las 12:24 y 12:27 hora local del 9-sep).

---

## 2. Qué se descartó, con datos

Esto es lo más valioso del documento: **no repitas esta investigación**. Todo medido
contra la base real.

| Sospecha | Medición | Veredicto |
|---|---|---|
| Volumen de datos | 14 MB de base, 592 filas (11 deudores, 293 deudas, 36 pagos, 252 detalles) | descartado |
| Tráfico externo / bots | ~700 peticiones en 23 h, **todas de clientes propios** | descartado |
| Lecturas de disco | `cache_hit_pct` 99,81 %, 3.869 bloques leídos desde enero | descartado |
| Bloat de catálogo | `pg_attribute` 1.920 kB / 4.357 tuplas vivas, `autovacuum_count` 3 | descartado |
| Slot de replicación huérfano | `pg_replication_slots` vacío | descartado |
| Realtime | cero tablas en la publicación `supabase_realtime` | descartado |
| WAL acumulado | 8 ficheros, 80 MB | descartado |
| Logging a disco | `log_statement=ddl`, `log_min_duration_statement=-1`, `auto_explain.log_min_duration=10000` | descartado |
| Consultas caras | la peor, 611 bloques leídos y 1,5 s acumulados | descartado |
| Derrames a temporales | 79 MB en 10 ficheros **desde enero** | descartado |

### Desglose del tráfico (23 h de logs, export de 1000 filas)

| Cliente | Peticiones | Qué es |
|---|---|---|
| `python-httpx/0.28.1` | 442 | backend FastAPI de `contabilidad` (`contabilidad/debts/reading.py`) |
| `Deno/…SupabaseEdgeRuntime` | 105 | las propias edge functions llamando de vuelta |
| `Dart/3.12 (dart:io)` | 97 | app Flutter |
| `Python-urllib/3.14` | 43 | `scripts/backup_deudas_supabase.py` |
| Chrome Android | 2 | el visor, desde `visor-deudas.vercel.app` |

> ⚠️ El export del dashboard viene **muestreado** (1000 filas). Los conteos por hora no
> son absolutos. No construyas conclusiones sobre frecuencias a partir de ese fichero;
> en esta investigación se cometió ese error con los checkpoints y hubo que retractarse.

### Conclusión sobre la causa

No hay nada en la base que explique el consumo. El gasto es **el suelo de la plataforma en
compute Nano**: recolector de métricas de Supabase, envío de logs, pooler, checkpoints.
Lo que ocurrió fue un bucle: algo agotó el presupuesto → el disco cayó a su velocidad
base → las consultas se ralentizaron → PostgREST acumuló hilos → nunca se recuperaba
solo, porque hasta el tráfico normal excedía ya el disco limitado. El restart lo rompió.

Síntoma revelador en los logs de Postgres: consultas de monitorización de Supabase que no
tocan ninguna tabla tardando una eternidad —
`SELECT setting FROM pg_settings WHERE name='max_connections'` en **17,0 s**,
`pg_stat_activity` en 17,1 s, `pg_ls_waldir()` en 13,4 s. Son víctimas, no causas.

---

## 3. Lo que YA se aplicó en producción ✅

### Configuración de Postgres (10-sep)

`ALTER SYSTEM` está prohibido para el rol `postgres` en Supabase
(`ERROR: 42501: permission denied to set parameter "checkpoint_timeout"`). Se aplicó por
la API de configuración, que sí acepta ambos parámetros:

```bash
supabase --experimental postgres-config update --project-ref rcmdzvbxerumzxvnubfo \
  --config checkpoint_timeout=30min --config max_wal_size=2GB --no-restart
# → {"max_wal_size":"2GB","checkpoint_timeout":"30min","message":""}
```

Motivo: tras cada checkpoint, la primera escritura sobre cada página se copia entera al
WAL (*full page write*). Con escrituras esporádicas, checkpoints cada 5 min = amplificación
de escritura máxima. `--no-restart` basta porque ambos son recargables en caliente.

**Sin verificar todavía**: que el valor en ejecución lo haya recogido. Comprobar con
`SHOW checkpoint_timeout;` (esperado `30min`) y `SHOW max_wal_size;` (esperado `2GB`).
Si siguen en los valores viejos, el override está guardado y entra en el próximo reinicio.

### Pendiente de la misma tanda, NO aplicado

```sql
ALTER ROLE authenticator SET statement_timeout = '10s';
```

Es lo que impide que un throttle vuelva a convertirse en 24 h de caída: las peticiones
mueren rápido en vez de acumularse. La consulta más lenta de la app tarda 0,25 s.

---

## 4. Migraciones B y C: aplicadas el 12-sep ✅

B (`estado_cuenta` sin tabla temporal, `LANGUAGE sql STABLE` con sumas acumuladas) y C
(`aplicar_cruce(p_con_estado)`, para que `registrar_pago` no calcule un estado que tira)
**nunca se aplicaron sueltas**. Se fundieron en
`deudas/supabase/migrations/20260912180000_pago_manual_antes_que_el_cruce.sql`, que además
cambia la regla del pago manual (ver `LOGICA_SISTEMA.md` §3.2.1): la idea de B de empujar
al final del FIFO las deudas elegidas (`p_deudas_pago`) quedó descartada. Los ficheros
originales de B, C y su `REVERTIR_20260910.sql` están en
`backups/descartado_cruce_cede_20260912/`, fuera de la secuencia de migraciones.

Cómo se aplicó (12-sep, `supabase db query --linked -f`, en una sola transacción):

| Comprobación | Resultado |
|---|---|
| Réplica local (Postgres 17 en podman) con los datos reales, funciones de producción | 22/22 estados idénticos a producción |
| Misma réplica con la migración, sin `p_pago` | **22/22 idénticos** (repetido con los datos del momento del deploy) |
| Pagos manuales al azar en la réplica: vista previa = lo guardado, deuda por deuda | 231 casos, 0 fallos |
| Pagos automáticos: versión vieja vs nueva | 165 casos, 0 diferencias |
| `REVERTIR_20260912.sql` en la réplica, y re-aplicar | 22/22 idénticos en ambos sentidos |
| Producción tras aplicar: `estado_cuenta` y la edge vieja contra la captura previa | 22/22 y 22/22 idénticos |
| `scripts/probar_pago_manual.py` y `scripts/probar_rpc_cruce.py` en producción | TODO OK (deudores temporales, borrados) |
| Edge `get_estado_cuenta` nueva, sin `pago`, contra la captura previa | 22/22 idénticas |

**Revertir:** ejecutar `deudas/supabase/migrations/REVERTIR_20260912.sql` entero. Restaura
las definiciones exactas que había en producción (bajadas con `pg_get_functiondef`), y
luego redesplegar la edge desde el commit anterior.

⚠️ **Defecto previo encontrado, no corregido:** una deuda con saldo de exactamente $0.01
cuenta en el total cruzable pero el reparto FIFO la salta (umbral `> 0.01`). Al
materializar el cruce, un lado aplica un centavo menos que el otro y el neto se mueve
$0.01. Pasa hoy con "Almuerzo" de un deudor real, y ya pasaba con las funciones de antes.

## 5. 🔴 Seguridad: dos agujeros confirmados en vivo

Ninguno está explotado — los logs de 23 h no muestran un solo acceso externo. Pero los dos
son reales y se verificaron contra producción el 10-sep.

### Agujero 1 — el token del visor es decorativo

```ts
// supabase/functions/get_estado_cuenta/index.ts:31
// supabase/functions/get_historial/index.ts:15
const { deudor_id, pov = 'debtor' } = await req.json()
```

Las dos edge functions reciben un `deudor_id` crudo y **no validan ningún token**. El token
solo se usa en el navegador (`visor_web/js/app.js:728`) para traducirlo a un `deudor_id`.

Comprobado: una llamada a `get_estado_cuenta` con solo un `deudor_id`, **sin aportar token
alguno**, devuelve el estado de cuenta completo con sus 11 deudas.

### Agujero 2 — anon lista todos los deudores, con sus tokens

`deudas/supabase/schema.sql:88-104` tiene, sobre las cuatro tablas:

```sql
CREATE POLICY "Deudores visibles por token" ON deudores FOR SELECT USING (true);
CREATE POLICY "Admin full access deudores" ON deudores FOR ALL    USING (true);
-- …y las equivalentes para deudas, pagos y detalle_pagos
```

`FOR ALL USING (true)` para `anon` = SELECT, INSERT, UPDATE y DELETE para cualquiera.
Y la anon key está publicada en:

- `github.com/Sebas04A/visor_deudas` — **repo público**, `js/app.js:6`
- desplegado en `https://visor-deudas.vercel.app`

Comprobado: `GET /rest/v1/deudores?select=*` devuelve las 11 filas con las columnas
`id`, `nombre`, `token`, `created_at`. Es decir, cualquiera saca de un tirón la lista
completa de deudores, el token de cada uno y el id que alimenta el agujero 1.

> Nota: que la anon key sea pública es **por diseño** en Supabase y no es el fallo. El
> fallo son las policies que no la limitan.

### El diseño correcto

**Anon no debe tocar las tablas en absoluto.** Las edge functions reciben el *token*,
resuelven el deudor ellas mismas con la `service_role` key, y nunca se fían de un
`deudor_id` que venga del cliente.

### Secuencia que no rompe nada

El obstáculo: la app Flutter y el backend de contabilidad usan **la misma anon key** que el
visor. Cerrar las policies de golpe tumba los tres.

| Fase | Qué se hace | Qué se rompe |
|---|---|---|
| 1 | Las edge functions **aceptan `token`** además de `deudor_id`, y el visor pasa a mandar el token. El camino viejo sigue abierto. | nada |
| 2 | Las superficies de administración (Flutter y backend) dejan de usar la anon key y se autentican. | nada, si se hace antes de la fase 3 |
| 3 | Se cierran las policies a solo el dueño autenticado y se tapa el camino por `deudor_id`. Anon se queda sin nada. | nada, si la fase 2 está completa |

### ⚠️ Decisión abierta, pendiente del dueño

La fase 2 tiene tres caminos y **el dueño todavía no eligió**. Determina cómo se escriben
las fases 1 y 3, así que hay que preguntárselo antes de empezar:

1. **Supabase Auth con cuenta única de dueño** (era la recomendación). Cuenta
   email+contraseña; la app Flutter pide login una vez y guarda la sesión; el backend de
   contabilidad usa `service_role` en una variable de entorno (vive en la máquina del
   dueño, es seguro). Las policies pasan a `TO authenticated`. Si se pierde el móvil, se
   revoca la sesión sin tocar nada más. Coste: una pantalla de login en Flutter.
2. **`service_role` en ambos sitios.** Cero cambios de interfaz, una tarde de trabajo. Pero
   deja una llave maestra compilada en el APK: quien lo extraiga tiene acceso total e
   irrevocable, y la única salida es rotar la clave y recompilar.
3. **Solo el backend por ahora.** Obliga a dejar las policies de escritura abiertas para
   anon, así que el agujero grande sigue ahí. Solo tiene sentido si se va a retirar la app
   Flutter pronto.

### Superficies que tocar en la fase 2

- `deudas/flutter_app/lib/` — cliente Supabase inicializado en `main.dart`; llamadas en
  `services/sync_service.dart`, `services/database_service.dart`,
  `screens/saldar_cuentas_screen.dart:78`, `screens/deudor_detail_screen.dart:79`.
- `contabilidad/debts/reading.py` y `contabilidad/debts/escritura.py` — cliente del backend.
- `deudas/supabase/functions/*/index.ts` — hoy usan `SUPABASE_ANON_KEY`; pasan a
  `SUPABASE_SERVICE_ROLE_KEY`.
- `deudas/visor_web/js/app.js` — deja de llamar a `/rest/v1/deudores` y manda el token.

Ojo: `get_estado_cuenta` la usan **tanto el visor (pov `debtor`) como la app Flutter
(pov `owner`)**. No se puede convertir en "solo token" sin romper Flutter; hay que admitir
las dos entradas y cerrar la de `deudor_id` en la fase 3.

---

## 6. 🟠 Bug: la cola de sincronización de Flutter está envenenada

En los logs: **26 × HTTP 409** desde la app Flutter en `POST /rest/v1/deudas`, todos
`insert or update on table "deudas" violates foreign key constraint "deudas_deudor_id_fkey"`.
`pg_stat_database` marca `xact_rollback = 156`.

Hay al menos una deuda local cuyo `deudor_id` no existe en Supabase. En
`deudas/flutter_app/lib/services/sync_service.dart`, el error hace `rethrow` y la fila
nunca se marca como sincronizada, así que **se queda en la cola y se reintenta en cada
sync, para siempre**, bloqueando todo lo que venga detrás.

Arreglo: detectar el fallo permanente (violación de FK no se arregla reintentando),
apartar la fila a un estado de error y seguir con el resto, en vez de `rethrow`. Y
averiguar de dónde salió ese `deudor_id` fantasma.

(Los **18 × 401** desde Dart en `/rest/v1/` son correctos: es
`ConnectivityService.canReachSupabase()`, que trata el 401 como "servidor vivo".)

---

## 7. 🟡 Optimizaciones identificadas y no hechas

- **Backend de contabilidad sin caché.** 342 de las ~700 peticiones diarias son el par
  `deudores` + `vista_estado_deudas` repetido 171 veces. Son datos que cambian una vez al
  día como mucho. Un TTL de minutos se lleva ~48 % del tráfico total.
- **La app Flutter se baja todo, siempre.** `sync_service.dart::pullFromServer()` descarga
  las cuatro tablas completas en cada sincronización, sin filtro por fecha de
  modificación, y escribe fila a fila en Hive. Crece linealmente para siempre. Un sync
  incremental por `created_at` lo deja en casi nada.
- **`PostgREST` derrama al recargar su caché de esquema.** La consulta de introspección
  (`with f as (-- CTE with sane arg_modes…`) escribió 18 MB de temporales en 2 ejecuciones.
  Se dispara con cada DDL. No es accionable directamente, pero explica por qué iterar
  migraciones en producción sale caro en disco.

---

## 8. Si el problema de IO vuelve

1. **Restart project** en *Settings → General*. Desatasca el bucle en ~2 minutos y **no
   borra datos** (los datos viven en el volumen; solo se cortan conexiones y se vacía la
   caché en memoria). Cuidado con los botones vecinos: *Pause project* deja el proyecto
   offline y *Delete project* es lo que parece.
2. El reinicio **no rellena el presupuesto de Disk IO**; eso se recupera solo con el tiempo.
3. Sacar un backup en cuanto responda: `python scripts/backup_deudas_supabase.py`.
4. Si se repite a menudo, las opciones honestas son: subir a compute **Micro** (~10 $/mes,
   se paga por Vercel al estar la org ahí), convivir con reinicios ocasionales, o
   **llevársela a SQLite** — son 592 filas y 14 MB, y lo único que obliga a tenerla
   hosteada es el visor para los deudores.

### Consultas de diagnóstico que sirvieron

```sql
-- ¿bloat de catálogo?
SELECT relname, n_live_tup, n_dead_tup, pg_size_pretty(pg_total_relation_size(relid)),
       last_autovacuum, autovacuum_count
FROM pg_stat_all_tables WHERE schemaname='pg_catalog'
  AND relname IN ('pg_class','pg_attribute','pg_type','pg_depend','pg_attrdef')
ORDER BY n_dead_tup DESC;

-- ¿qué consulta mueve disco?
SELECT calls, shared_blks_read, shared_blks_written, shared_blks_dirtied,
       temp_blks_written, round(total_exec_time::numeric/1000,1) AS seg,
       left(regexp_replace(query,'\s+',' ','g'),110)
FROM pg_stat_statements
ORDER BY shared_blks_read+shared_blks_written+shared_blks_dirtied+temp_blks_written DESC
LIMIT 20;
-- OJO: pg_stat_statements se reinicia con el restart del proyecto. Se nota porque
-- aparecen con calls=1 las migraciones internas (ALTER TABLE realtime.messages…).

-- ¿WAL retenido por un slot?
SELECT slot_name, plugin, active,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn))
FROM pg_replication_slots;
SELECT count(*), pg_size_pretty(sum(size)) FROM pg_ls_waldir();

-- salud general
SELECT blks_read, blks_hit,
       round(100.0*blks_hit/nullif(blks_hit+blks_read,0),2) AS cache_hit_pct,
       temp_files, pg_size_pretty(temp_bytes), xact_commit, xact_rollback, stats_reset
FROM pg_stat_database WHERE datname = current_database();
```

---

## 9. Inventario de ficheros de esta tanda

| Ruta | Qué es | Estado |
|---|---|---|
| `deudas/supabase/migrations/20260912180000_pago_manual_antes_que_el_cruce.sql` | B + C + pago manual antes que el cruce | **aplicada 12-sep** |
| `deudas/supabase/migrations/REVERTIR_20260912.sql` | vuelta atrás exacta a las funciones del 12-sep | probado en réplica |
| `backups/descartado_cruce_cede_20260912/` | B, C y su reversión originales, sin aplicar | archivado |
| `scripts/verificar_estado_cuenta_equivalente.py` | compara producción contra la línea base | escrito |
| `backups/estado_cuenta_baseline_20260910/` | 22 estados de producción pre-migración | capturado 10-sep ~17:00 UTC |
| `backups/deudas_20260910_115329/` | 592 filas (11/293/36/252) | capturado 10-sep |
