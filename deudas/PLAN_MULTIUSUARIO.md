# Deudas v2 — plan multiusuario

> Escrito el **2026-09-23**. Documento autocontenido: un agente que solo lea este archivo
> debe poder ejecutar cualquier fase sin perderse. Si algo de aquí contradice el código,
> **el código manda**: verifica, corrige este documento y avisa al dueño.

---

## 0. Cómo usar este documento (léelo si eres un agente)

1. Lee **§1 a §5 enteros** antes de tocar nada. Explican qué existe hoy, qué no se puede
   romper y qué queremos construir.
2. Después lee **§6 (entorno)** y **solo la fase que te toca en §8**. Cada fase trae su
   objetivo, contexto, archivos, pasos, verificación y criterio de salida.
3. **Nunca empieces una fase si la anterior no cumplió su criterio de salida.** Míralo en la
   tabla de §0.2.
4. Al terminar una tarea, marca su casilla `[x]` en la fase y actualiza §0.2 (estado y
   fecha). Si descubriste algo que el siguiente agente necesita saber, agrégalo en la
   sección **"Notas de ejecución"** de esa fase, no en otro archivo.
5. Idioma: todo (código, comentarios, commits y mensajes) en **español**, con el estilo del
   repo: comentarios que explican el *porqué*, nombres en español (`deudor`, `pago`,
   `cruce`).

### 0.1 Reglas que no se negocian

- 🔴 **La base de producción actual (`rcmdzvbxerumzxvnubfo`) NO se modifica** en ninguna
  fase anterior a la 3, salvo lo que la fase 3 dice explícitamente. Leerla (backups,
  capturas) sí se puede.
- 🔴 **El dueño usa la app todos los días.** Nada de lo que hagas puede dejar de funcionar
  para él: app Flutter, web de contabilidad y visor.
- 🔴 **No se hace commit ni push sin que el dueño lo pida.** Los commits llevan al final
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- 🔴 **No se despliega nada a un proyecto Supabase en la nube sin confirmación del dueño**
  (crear un proyecto, `db push`, `functions deploy`).
- 🟠 Toda fase que migra datos tiene una **comparación contra la línea base** que tiene que
  dar **cero diferencias**. "Casi igual" es un fallo.
- 🟠 Si una decisión de diseño no está en §3 ni en §9, **pregunta al dueño** antes de
  inventarla.

### 0.2 Estado de avance

| Fase | Nombre | Estado | Fecha | Quién |
|---|---|---|---|---|
| 0 | Preparación y réplica local | ✅ hecha | 2026-09-23 | Claude |
| 1 | Multi-dueño y seguridad (local) | ✅ hecha | 2026-09-23 | Claude |
| 2 | Clientes contra v2 (proyecto de prueba) | 🟨 casi: falta 2.5 (dispositivo, dueño); 2.3 y pull incremental hechos; Google listo en código | 2026-09-23 | Claude |
| 3 | Corte: el dueño se muda a v2 | ⬜ pendiente | | |
| 4 | Invitaciones y vínculos | 🟨 adelantada: 4.1–4.3 hechas y en el proyecto v2 de prueba; falta 4.4 (visor/App Link) y probar en 2 celulares | 2026-09-23 | Claude |
| 5 | Conciliación inicial | 🟨 adelantada: 5.1–5.4 hechas y en el proyecto v2 de prueba; hueco de las filas tardías y revincularse arreglados (2026-09-24); falta probar en celulares | 2026-09-24 | Claude |
| 6 | Propuestas continuas | 🟨 adelantada: 6.1–6.7 hechas y **en el proyecto v2 de prueba** (2026-09-24, con OK del dueño; 231 tests pgTAP allí); menores hechos (retirar propuesta, historial con estado); falta probar en celulares y la semana de uso real | 2026-09-24 | Claude |
| 7 | Publicación | 🟨 adelantada: 7.2 (exportar, borrar cuenta; política de privacidad en borrador) y 7.3 (límites) hechas y en la nube de prueba; faltan 7.1 (Firebase), 7.4, 7.5 y publicar la política: todo necesita al dueño | 2026-09-24 | Claude |

Estados: ⬜ pendiente · 🟨 en curso · ✅ hecha (criterio de salida cumplido) · ⛔ bloqueada
(escribir el motivo).

### 0.3 Dónde quedó todo (leer primero; actualizado 2026-09-24)

**Hecho:**
- v2 existe en local (`deudas/v2`) y en la nube: proyecto gratuito "Deudas v2",
  `ggzvxehcsorlbroucbkp` (§6.4).
- Cada fila tiene dueño y el RLS lo hace cumplir. Tests pgTAP: 89 (fases 1, 4 y 5) pasan en
  local y en la nube; con la fase 6 son 185, verdes en local.
- Los datos reales, importados, dan los mismos estados de cuenta que producción. Probado en
  local, y en la nube con un ensayo del corte que después se borró.
- La app Flutter tiene login y datos por usuario detrás de la bandera `DEUDAS_V2`.
- El visor usa solo el token.
- El backend de contabilidad elige la base por variables de entorno.
- Vínculos (fase 4) y conciliación (fase 5) están en la nube de prueba.
- Fase 6 (propuestas) en la nube de prueba desde el 2026-09-24: migración
  `20260924120000_propuestas.sql`, backend (`reading.py`) y Flutter (bandeja, saldo
  acordado, proponer cambios, cola sin conexión, retirar una propuesta, historial con el
  estado de cada fila).
- El hueco de la fase 5 (filas anotadas entre las dos confirmaciones) y dos defectos al
  **volver a vincularse** están arreglados (`20260924130000_conciliacion_tardias.sql`, en la
  nube).
- Fase 7, la parte que no necesita al dueño (`20260924140000_publicacion.sql`, edge
  `borrar_cuenta`, en la nube): exportar mis datos, borrar mi cuenta, límites de uso y el
  borrador de la política de privacidad (`deudas/v2/POLITICA_PRIVACIDAD.md`).
- La APK v2 contra la nube está recompilada con todo esto (§6.5).

**Siguiente (todo necesita al dueño):** la fase 2.5 (probar en un dispositivo), el corte
(fase 3), probar en dos celulares las fases 4 a 7, revisar las decisiones 10 a 20 de §3.3 y
el borrador de la política de privacidad, y lo que queda de la fase 7 (Firebase, plan,
Play Store).

**Commits (2026-09-24, pedidos por el dueño, sin push):**

| Repo | Rama | Qué hay |
|---|---|---|
| `ContabilidadPersonal` (este) | `feat/deudas-v2` (sale de `refactor/filtros-transacciones` en `85efa91`) | solo lo de v2: `deudas/PLAN_MULTIUSUARIO.md`, `deudas/v2/` (menos `.env` y `supabase/.temp`, ignorados), `scripts/v2/`, `contabilidad/debts/cliente.py`, `reading.py`, `escritura.py` y `tests/test_deudas_rechazadas.py`. Se armó sin cambiar de rama: el dueño sigue en `refactor/filtros-transacciones` con sus cambios sin commitear, y los archivos de v2 siguen en su copia de trabajo (sin seguimiento en esa rama) |
| `deudas/flutter_app` → `Sebas04A/app_deudas` | `v2` (salió de `main`) | las fases 2 a 7, commiteadas en la rama `v2` |
| `deudas/visor_web` → `Sebas04A/visor_deudas` (**público**) | `v2` | sin cambios nuevos: commiteado y subido (`640fc45`, 2026-09-23) |

Para seguir trabajando en v2 en este repo: `git switch feat/deudas-v2` (con los cambios
del dueño guardados antes, o en un worktree aparte). Mensajes de commit en español, con
`Co-Authored-By` (§0.1).

---

## 1. Qué es el sistema hoy

### 1.1 Qué hace

Una app para llevar **"quién le debe a quién"** entre el dueño (Sebas) y sus contactos:
deudas en ambos sentidos, pagos parciales, **cruce de cuentas** automático (si yo te debo
$10 y tú me debes $15, se compensan $10 y quedas debiendo $5) y un **visor web** de solo
lectura que se comparte por enlace con token para que el contacto vea su estado de cuenta.

Hoy es **de un solo usuario**: "yo" siempre es Sebas y no está escrito en ningún lado.

### 1.2 Componentes y dónde viven

Este cuadro describe **v1**, lo que el dueño usa hoy (ramas `main`). Lo que ya existe de
v2 está en §0.3, §6.4 y §7.

| Componente | Dónde | Cómo habla con Supabase |
|---|---|---|
| **Base de datos** | Supabase proyecto `Deudas`, ref `rcmdzvbxerumzxvnubfo`, región `us-east-2`, plan gratuito (compute Nano), org gestionada por Vercel. Postgres 17.6 | — |
| **Migraciones SQL** | `deudas/supabase/migrations/` (+ consolidado `deudas/supabase/aplicar_migraciones_cruce.sql`) | Se aplicaron a mano (SQL Editor / `supabase db query --linked`) |
| **Edge functions** | `deudas/supabase/functions/get_estado_cuenta/index.ts`, `…/get_historial/index.ts` | Llaman al RPC con `SUPABASE_ANON_KEY` |
| **App Flutter** (panel del dueño) | Repo aparte `Sebas04A/app_deudas` (privado), clonado en `deudas/flutter_app/` | anon key constante en `lib/main.dart:21`. Offline-first con Hive. Sube con `upsert` directo a las 4 tablas (`lib/services/sync_service.dart`), borra con `.delete()` directo (`lib/services/database_service.dart:283`), llama a los RPC `registrar_pago`, `editar_cruce`, `editar_pago` y a las edge functions con `pov: 'owner'` (`screens/deudor_detail_screen.dart:60`, `saldar_cuentas_screen.dart:102,229`, `history_screen.dart:108,129`) |
| **Visor web** | Repo público `Sebas04A/visor_deudas`, clonado en `deudas/visor_web/`, desplegado en `https://visor-deudas.vercel.app` | Lee `?token=` de la URL; `js/app.js:109-111` hace `GET /rest/v1/deudores?token=eq.X` y después llama a las edge functions `get_estado_cuenta` (pov `debtor`) y `get_historial` |
| **Backend de contabilidad** (FastAPI, uso personal) | `contabilidad/debts/reading.py` (lectura) y `contabilidad/debts/escritura.py` (escritura), usados por `contabilidad/backend/routes/supabase_debts.py` y `routes/efectivo.py` | En v1, anon key constante. **Desde la fase 2.4** (sin commitear) ambos usan `contabilidad/debts/cliente.py`: v1 por defecto, v2 con `DEUDAS_SUPABASE_URL`/`_KEY`/`DEUDAS_EMAIL`/`DEUDAS_PASSWORD` |
| **Web de contabilidad** (React) | `contabilidad/pagina/` | **No** habla con Supabase directo; todo pasa por el backend |
| **Scripts** | `scripts/*.py` (backup, verificaciones, pruebas end-to-end) | anon key constante |
| **Datos de contabilidad que referencian deudas** | `data/sistema/etiquetado/etiquetas.csv` (columnas `deuda_id`, `pago_id`) | Guardan **UUID de producción**. Por eso los UUID deben conservarse en v2 |

> Flutter y Dart **no** están instalados en el host. Ver §6.5 para el entorno de build.

### 1.3 Tamaño de los datos (medido el 2026-09-23)

| Tabla | Filas |
|---|---|
| `deudores` | 11 |
| `deudas` | 335 |
| `pagos` | 41 |
| `detalle_pagos` | 271 |
| `cruces_editados` | 4 |
| `pagos_editados` | 3 |

### 1.4 Esquema actual (producción, no `schema.sql`)

> ⚠️ `deudas/supabase/schema.sql` está **desactualizado**. No lo uses como referencia. La
> verdad es producción, y la fase 0 la vuelca a un archivo.

```
deudores      (id uuid PK, nombre text, token text UNIQUE, created_at, synced bool)
deudas        (id uuid PK, deudor_id → deudores ON DELETE CASCADE, titulo, monto numeric(10,2),
               fecha_gasto date, created_at, synced, es_mi_deuda bool)
pagos         (id uuid PK, deudor_id → deudores CASCADE, monto_total numeric(10,2), fecha_pago date,
               created_at, synced, es_compensacion bool, es_mi_pago bool,
               cruce_id uuid, idem_key uuid UNIQUE, nota text)
detalle_pagos (id uuid PK, pago_id → pagos CASCADE, deuda_id → deudas CASCADE,
               monto_asignado numeric(10,2), created_at, synced)
cruces_editados (id, idem_key, cruce_id, deudor_id, excluidas uuid[], monto_antes, monto_despues,
                 antes jsonb, despues jsonb, created_at)      -- bitácora de editar_cruce
pagos_editados  (id, idem_key, pago_id, deudor_id, antes jsonb, despues jsonb, created_at)
vista_estado_deudas (vista: saldo por deuda)
```

Funciones (todas `SECURITY INVOKER` según las migraciones del repo; **confirmar en el
volcado**): `estado_cuenta(p_deudor_id, p_pov, p_pago)`, `aplicar_cruce(…)`,
`registrar_pago(p_deudor_id, p_monto, p_es_mi_pago, p_fecha, p_idem_key, p_deudas_ids)`,
`editar_cruce(…)`, `_editar_cruce_aplicar(…)`, `editar_pago(p_pago_id, p_fecha, p_nota,
p_idem_key)`, `_idem_derivada(…)`, `_ec_lado(…)`.

### 1.5 Problemas de seguridad actuales (motivo de parte de este plan)

Detalle completo en `deudas/PENDIENTE_IO_Y_SEGURIDAD.md` §5. En resumen:

- Las policies son `FOR ALL USING (true)` para `anon` en las 4 tablas. Como la anon key es
  pública (está en el repo público del visor), **cualquiera puede leer, escribir y borrar
  todo**.
- Las edge functions aceptan un `deudor_id` crudo sin validar el token, así que el token
  del visor es decorativo.
- Los RPC y las tablas `*_editados` tienen `GRANT` a `anon`.

v2 nace sin estos agujeros. La base vieja los mantiene hasta el corte (fase 3).

---

## 2. Semántica que NO se puede romper

Esta es la matemática que el dueño ya validó caso por caso. En v2 se **porta tal cual**.
Referencia larga: `deudas/LOGICA_SISTEMA.md` y `contabilidad/debts/PLAN_PRUEBAS_DEUDAS.md`.

- **Punto de vista del dueño:** + te deben, − tú debes. `es_mi_deuda = true` → yo debo.
  `es_mi_pago = true` → el dinero lo entregué yo.
- **El estado de una deuda no se guarda, se calcula:** `saldo = monto − Σ detalle_pagos`.
- **Pago:** mueve el saldo por su `monto_total` completo. Lo no asignado (sobrante) es
  **saldo a favor** de quien pagó y abona automáticamente las deudas pendientes de esa
  misma parte, de la más antigua a la más reciente (`abono_saldo_favor`).
- **Cruce:** dos pagos virtuales (`es_compensacion = true`), uno por lado, unidos por
  `cruce_id`. Su efecto neto es cero: solo reparte. Se calcula sobre `saldo_real` (neto del
  saldo a favor), **no** sobre el bruto.
- **Orden FIFO:** `(fecha, created_at, id)`. El `created_at` real **no** se puede pisar
  (ya pasó: el pull de Flutter lo sobrescribía; se corrigió, pero hay filas afectadas).
- **Pago manual con deudas elegidas:** el pago va **primero** a las elegidas, el sobrante
  queda como saldo a favor y el cruce va **después** en FIFO puro. Sin deudas elegidas: el
  cruce va primero.
- **Única definición:** `estado_cuenta()` en Postgres es la única fuente de saldos. Los RPC
  de escritura no reimplementan la matemática: leen de `estado_cuenta()`. `reading.py`, las
  edge functions y Flutter son envoltorios. Flutter tiene una copia local (`PlanPago`) para
  trabajar sin conexión, con un test de paridad.
- **Idempotencia:** todo RPC de escritura recibe `idem_key`; repetir la llamada no duplica.
- **Concurrencia:** los RPC toman `pg_advisory_xact_lock` por deudor.

Defecto heredado y **conocido**: una deuda con saldo de exactamente $0.01 entra en el
cruzable pero el FIFO la salta (umbral `> 0.01`), así que el neto se mueve un centavo al
materializar el cruce. **Se porta tal cual** para que la comparación con la línea base
valga. Corregirlo es tarea aparte, con su propia verificación.

---

## 3. Qué queremos construir

### 3.1 La idea en una frase

Que **cualquier persona** pueda usar la app con su propia libreta de deudas y que, cuando
la otra parte también tiene la app, **los dos se pongan de acuerdo** sobre lo que se deben
sin perder la libertad de anotar a quien no la tiene.

### 3.2 Decisiones del dueño (no re-litigar)

| Tema | Decisión |
|---|---|
| Propiedad | Cada usuario es **dueño de su libreta**: sus deudores, deudas y pagos. **Nadie escribe en la libreta de otro.** |
| Persona sin app | Funciona **exactamente como hoy**: se registra sin pedir permiso a nadie. |
| Persona → Usuario | Un deudor de mi libreta se puede **vincular** a un usuario real mediante una invitación. Desde ahí, lo que yo registro le llega al otro como **propuesta**. |
| Aceptar | Si el otro acepta, se crea la **fila espejo** en su libreta (dirección invertida) y las dos filas quedan atadas en un **acuerdo**. |
| Rechazar | La fila sale como **rechazada** y **deja de contar** en los saldos. |
| Sin conexión | Todo se sincroniza igual que hoy: lo que se hace sin red sube al volver. |
| Visor por token | **Sigue funcionando tal cual**, para cualquier deudor, esté vinculado o no. |
| Base | **Proyecto Supabase nuevo (v2).** La base actual no se toca hasta el corte. Los datos se importan conservando los UUID. |
| Duplicados | Protección en capas (§4.5). La principal: al aceptar, se sugiere enlazar con una fila que ya existe en vez de crear otra. |

### 3.3 Decisiones de diseño tomadas en este plan (cambiables si el dueño lo pide)

1. **Los nombres se quedan.** v2 mantiene `deudores`, `deudas`, `pagos`, `detalle_pagos` y
   todas sus columnas. Solo se **agregan** columnas y tablas. Cada libreta sigue siendo del
   punto de vista de su dueño, así que la matemática de §2 no cambia y Flutter, el backend
   y las edge functions cambian poco.
2. **El servidor genera las propuestas.** Flutter sigue subiendo deudas con `upsert`; un
   trigger detecta que el deudor está vinculado y crea la propuesta. Así el sync no cambia
   de forma.
3. **"Mi saldo" y "saldo acordado".** Una propuesta pendiente cuenta en mi saldo (marcada
   como pendiente) pero no en el acordado. Ver §4.1.
4. **Lo derivado no se acuerda.** Cruces y `detalle_pagos` los calcula cada libreta por su
   cuenta; solo se acuerdan los hechos (deudas y pagos físicos).

Decisiones tomadas al implementar (fases 0 a 2):

5. **La idempotencia es por dueño:** `UNIQUE (owner_id, idem_key)`. Con la clave global,
   un usuario podía chocar con las claves de otro, o sondearlas.
6. **El token del visor lo sigue generando el teléfono** (UUID v4) y se sube con el deudor.
   Así el enlace que la app comparte sin conexión ya existe en el servidor cuando se
   sincroniza.
7. **Las edge functions de v1 se reutilizan sin reescribirlas** (`functions/_shared/`).
   Única diferencia a propósito: el historial tiene `ORDER BY` (fecha, created_at, id),
   porque en v1 el orden de los empates era el orden físico de las filas, es decir,
   arbitrario.
8. **La app Flutter tiene una sola base de código para v1 y v2**, separada por la bandera
   de compilación `DEUDAS_V2` (`lib/config.dart`). Sin la bandera, la app es exactamente
   la de antes. Tras el corte, v2 pasa a ser el valor por defecto y el camino v1 se puede
   borrar.
9. **El backend de contabilidad entra como el dueño** (email + contraseña en `.env`),
   **nunca** con la key secreta, que vería las libretas de todos.

Decisiones tomadas al implementar la fase 6 (**el dueño las puede cambiar**; las dos
primeras son las que más conviene que mire):

10. **El título (o la nota) viaja en la propuesta** y la fila espejo nace con él. Sin eso
    la bandeja diría "Ana anotó que le debes $20" sin decir de qué. Después cada uno lo
    edita en su libreta (§4.3). La conciliación (fase 5) sigue sin mandar títulos del
    historial; una propuesta de la conciliación, al aceptarse, nace "Anotada por <nombre>".
11. **Desvincular devuelve a `local` lo que esperaba respuesta.** Las propuestas pendientes
    se anulan (§4.4) y sus filas siguen contando en el saldo de quien las anotó, como
    antes de proponerlas. Lo acordado queda acordado.
12. **Roto el vínculo, la guardia se apaga:** cada uno vuelve a editar libremente lo que
    tenía acordado. Si no, esas filas quedarían congeladas para siempre.
13. **Al aceptar, un candidato puede ser una propuesta MÍA** (los dos anotaron lo mismo a
    la vez y cada uno se lo mandó al otro). Enlazarlas deja las dos acordadas y resuelve
    también la mía.
14. **Enlazar exige mismo monto y dirección invertida**, no la misma fecha: si el monto
    difiere, el saldo acordado de los dos dejaría de cuadrar.
15. **Un pago espejo se reparte con `registrar_pago`** (automático: cruce y FIFO), como
    cualquier pago de la libreta de quien acepta.
16. **Cambiar lo acordado ajusta el reparto de cada libreta:** si cambia la dirección, la
    fila suelta todo lo repartido; si el monto baja por debajo de lo ya pagado, suelta el
    exceso (primero de los pagos reales más recientes; si no alcanza, sale de sus
    cruces). Lo soltado queda como saldo a favor, que `estado_cuenta` abona solo.
17. **Una sola propuesta de cambio pendiente por acuerdo**, venga de quien venga (`23505`).

Decisiones tomadas el 2026-09-24 (también para que el dueño las revise):

18. **Filas tardías de la conciliación:** lo que anota quien confirmó primero, antes de que
    el otro confirme, se le propone al otro cuando el vínculo pasa a `activo`, con título
    (como cualquier fila anotada con el vínculo vivo).
19. **Volver a vincularse reconcilia todo:** al nacer un vínculo, lo `acordada` de sus dos
    deudores (por fuerza de un vínculo roto) vuelve a `local` y pasa por la conciliación
    nueva, que lo empareja como a cualquier historial; los acuerdos viejos se borran. Sin
    esto esas filas quedaban congeladas (§8, notas de la fase 5).
20. **Límites de uso:** 20 invitaciones por día, 10 códigos inválidos por hora y 60
    consultas por minuto al visor por IP (ventana del minuto del reloj). Para registrar el
    intento fallido, `reclamar_invitacion` con un código que no sirve **devuelve NULL** en
    vez de lanzar `22023` (un error desharía el registro). Superar un límite da `PT429`
    (PostgREST responde 429).

### 3.4 Glosario

| Término | Significado |
|---|---|
| **Libreta** | Todo lo que pertenece a un usuario: sus filas con `owner_id = su id`. |
| **Deudor** / **contacto** | Fila de `deudores`. Es "la otra persona" dentro de mi libreta. |
| **Persona** | Deudor sin vínculo: alguien sin app, o que no fue invitado. |
| **Usuario** | Cuenta real de Supabase Auth, con perfil en `perfiles`. |
| **Vínculo** | Enlace entre mi deudor "Ale" y el deudor "Sebas" de la libreta de Ale. |
| **Propuesta** | Pedido de crear, editar o borrar un hecho, enviado a la otra parte del vínculo. |
| **Fila espejo** | La copia de una deuda o pago en la libreta del otro, con la dirección invertida. |
| **Acuerdo** | El par (mi fila, su fila espejo) aceptado por ambos. |
| **Conciliación** | Emparejar el historial previo de las dos libretas al vincularse. |
| **Línea base** | Captura de `estado_cuenta` de todos los deudores, contra la que se compara v2. |

---

## 4. Modelo v2

### 4.1 Estados de una fila

Columna nueva `estado_acuerdo` en `deudas` y `pagos`:

| Estado | Cuándo | ¿Cuenta en *mi saldo*? | ¿Cuenta en el *saldo acordado*? | ¿La ve el otro? |
|---|---|---|---|---|
| `local` | Deudor sin vínculo, o historial previo al vínculo todavía sin conciliar | sí | no | no (en el visor sí) |
| `propuesta` | Creada con el vínculo activo, o enviada durante la conciliación | sí, marcada *pendiente* | no | en su bandeja |
| `acordada` | El otro la aceptó o la enlazó con una fila suya | sí | sí | sí, como fila espejo en su libreta |
| `rechazada` | El otro la rechazó, o quien la propuso la anuló | **no** | no | no |

- **Mi saldo** es lo que la app muestra hoy: todo lo de mi libreta menos lo rechazado.
- **Saldo acordado** solo existe para deudores vinculados y suma únicamente filas
  `acordada`. **Invariante:** el saldo acordado de A con B = −(saldo acordado de B con A).
  Se verifica con `verificar_vinculo()`.
- **Cruces** (`es_compensacion`): siempre `local` (restricción `CHECK`). Son derivados y no
  mueven el neto, así que no rompen la invariante.
- **`detalle_pagos`**: derivado; cada libreta calcula su reparto. Con propuestas pendientes
  intercaladas, el reparto *por deuda* puede diferir entre las dos libretas; el neto
  acordado no.
- **Para un deudor sin vínculo todo es `local` y la salida de `estado_cuenta()` debe ser
  byte a byte igual a la de hoy.** Así se mantiene la compatibilidad.

### 4.2 Qué pasa al rechazar algo que ya estaba repartido

`rechazar_propuesta` (y `anular_propuesta`) hace, en **una sola transacción** con el
`pg_advisory_xact_lock` del deudor:

1. **Si la fila participa en un cruce** (un `detalle_pagos` suyo cuelga de un pago con
   `es_compensacion`): deshacer ese cruce con la lógica de `_editar_cruce_aplicar(cruce_id,
   p_excluir => [fila])`, que ya existe. Hay que hacerlo **antes** que el paso 2: si no,
   uno de los dos pagos virtuales queda con sobrante y el sistema lo toma como saldo a
   favor, lo cual es falso.
2. **Pago rechazado:** borrar sus `detalle_pagos`. Las deudas que pagaba se reabren.
3. **Deuda rechazada:** borrar los `detalle_pagos` que apuntan a ella. El dinero de esos
   pagos queda como sobrante y abona las siguientes deudas por la regla de saldo a favor
   que ya existe.
4. Marcar la fila `rechazada` y la propuesta `rechazada` (o `anulada`).

### 4.3 Editar y borrar algo acordado

- **Campos del acuerdo:** `monto`/`monto_total`, `fecha_gasto`/`fecha_pago`,
  `es_mi_deuda`/`es_mi_pago`. Cambiarlos, o borrar la fila, genera una **propuesta de
  cambio** (`tipo = 'editar' | 'borrar'`). Mientras no se acepta, las dos filas siguen
  igual. Si se acepta, el cambio se aplica a ambas; si se rechaza, no pasa nada.
- **Campos privados:** `titulo` (deudas) y `nota` (pagos). Cada uno los edita libremente
  en su libreta.
- **Guardia en el servidor:** el trigger `_guardia_acordada` rechaza (`42501`) cualquier
  `UPDATE` directo de los campos del acuerdo y cualquier `DELETE` directo de una fila
  `acordada`. Así ni un Flutter viejo ni un script pueden saltarse la regla. Los RPC de
  propuestas lo desactivan con una variable de sesión
  (`set_config('deudas.en_rpc', 'on', true)`).

### 4.4 De Persona a Usuario

```
1. Sebas tiene el deudor "Ale" (persona). Todo `local`, igual que hoy.
2. Sebas → crear_invitacion(deudor "Ale") → código de un solo uso, expira en 7 días.
   Se comparte por WhatsApp (reutilizar services/resumen_whatsapp.dart).
3. Ale se registra o entra → reclamar_invitacion(código, deudor_existente?)
     · deudor_existente NULL → se crea en su libreta el deudor "Sebas" (nombre del perfil)
     · deudor_existente = su "Sebas" de antes → caso con duplicados; lo resuelve la conciliación
   → se crea el vínculo en estado 'conciliando'
4. Conciliación inicial (§4.6)
5. Vínculo 'activo': toda deuda o pago nuevo de cualquiera de los dos nace `propuesta`.
6. Desvincular (cualquiera de los dos) → vínculo 'roto'. Cada uno conserva su libreta y
   sus filas conservan su estado; las nuevas vuelven a nacer `local`. Las propuestas
   pendientes se anulan.
```

Reglas: nadie se vincula consigo mismo; un deudor tiene como máximo un vínculo no roto; un
par de usuarios tiene como máximo un vínculo no roto.

### 4.5 Anti-duplicados, por capas

| # | Capa | Dónde | Qué evita |
|---|---|---|---|
| 1 | `idem_key` en todos los RPC (ya existe) + `propuestas.idem_key UNIQUE` | SQL | Reintentos de red y colas sin conexión que se reenvían |
| 2 | `origen_id` en la fila espejo + `UNIQUE (owner_id, origen_id)` | SQL | Aceptar dos veces la misma propuesta (doble toque, dos dispositivos) |
| 3 | `acuerdos`: `UNIQUE (entidad, fila_a)` y `UNIQUE (entidad, fila_b)` | SQL | Una fila atada a dos filas del otro. Misma regla uno a uno que `contabilidad/backend/services/debt_links.py` |
| 4 | Candidatos al aceptar: `aceptar_propuesta` devuelve `{"resultado": "hay_candidatos", "candidatos": [...]}` si en mi libreta hay una fila **no acordada** con la dirección invertida, el mismo monto al centavo y la fecha a ±3 días, salvo que se mande `p_enlazar_con` o `p_crear_nueva => true` | SQL + UI | Que Ale cree una "Cena $20" cuando ya la había anotado |
| 5 | Emparejamiento masivo en la conciliación (§4.6) | SQL + UI | Duplicados de todo el historial previo al vínculo |

### 4.6 Conciliación inicial

Mientras el vínculo está en `conciliando`, las filas previas de ambas libretas siguen
`local` y siguen contando en *mi saldo*, así que ningún saldo salta.

1. `candidatos_conciliacion(vinculo_id)` empareja las dos libretas:
   - **Deudas:** `a.es_mi_deuda <> b.es_mi_deuda`, `a.monto = b.monto`,
     `|a.fecha_gasto − b.fecha_gasto| ≤ 3`. Puntaje = cercanía de fecha + parecido del
     título (`similarity()` de `pg_trgm`). Asignación voraz uno a uno, del mejor puntaje
     al peor.
   - **Pagos** (sin cruces): `a.es_mi_pago <> b.es_mi_pago`, mismo `monto_total`, fecha
     ±3 días.
   - Devuelve `{pares: [...], solo_mias: [...], solo_suyas: [...]}`.
2. La UI muestra tres listas: pares ("¿son la misma?"), "lo que solo tienes tú" y "lo que
   solo tiene el otro".
3. `confirmar_conciliacion(vinculo_id, pares_aceptados uuid[][])`, que la puede llamar
   **cualquiera de las dos partes**:
   - Los pares aceptados pasan a `acordada` e insertan su fila en `acuerdos`.
   - Las filas sin par de **quien llama** pasan a `propuesta` para el otro, todas juntas.
   - Si la otra parte ya confirmó, o no tiene filas, el vínculo pasa a `activo`.
4. El otro revisa el paquete como cualquier propuesta, con "aceptar todo" disponible.

"Importar todo el historial" (el otro no tenía nada) es este mismo flujo con cero pares.

---

## 5. Esquema v2 completo

Escrito como la diferencia contra el esquema actual. En el repo v2, la migración base es el
volcado de producción y las siguientes agregan lo de abajo.

### 5.1 Multi-dueño (migración `…_duenos.sql`, fase 1)

> **Implementado** en `deudas/v2/supabase/migrations/20260923190000_duenos.sql`. **Esa es la
> referencia**: el bloque de abajo es el diseño original. Diferencias con él:
> - `idem_key` único **por dueño** (los tres índices `idx_*_idem*`);
> - `vista_estado_deudas` con `security_invoker = true`;
> - `cruces_editados` y `pagos_editados` también con FK compuesta al deudor;
> - `_exigir_deudor_propio(uuid)` hace el chequeo de dueño y solo lo llaman
>   `aplicar_cruce` y `registrar_pago`;
> - `perfiles`: solo se puede cambiar `nombre`.

```sql
-- Perfil público mínimo de cada usuario
CREATE TABLE perfiles (
  id         uuid PRIMARY KEY REFERENCES auth.users ON DELETE CASCADE,
  nombre     text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- Trigger AFTER INSERT ON auth.users → INSERT INTO perfiles (id, nombre) con
-- raw_user_meta_data->>'nombre' o la parte local del email. SECURITY DEFINER,
-- SET search_path = public.

-- Dueño en cada tabla. DEFAULT auth.uid(): el upsert de Flutter no tiene que mandarlo.
ALTER TABLE deudores
  ADD COLUMN owner_id     uuid NOT NULL DEFAULT auth.uid() REFERENCES perfiles,
  ADD COLUMN token_expira timestamptz,                 -- NULL = no expira (como hoy)
  ADD COLUMN moneda       text NOT NULL DEFAULT 'USD',
  ADD COLUMN updated_at   timestamptz NOT NULL DEFAULT now(),
  ADD CONSTRAINT deudores_id_owner UNIQUE (id, owner_id);

ALTER TABLE deudas
  ADD COLUMN owner_id   uuid NOT NULL DEFAULT auth.uid(),
  ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
  ADD CONSTRAINT deudas_id_owner UNIQUE (id, owner_id),
  DROP CONSTRAINT deudas_deudor_id_fkey,
  ADD CONSTRAINT deudas_deudor_owner_fkey
      FOREIGN KEY (deudor_id, owner_id) REFERENCES deudores (id, owner_id) ON DELETE CASCADE;

ALTER TABLE pagos  -- igual que deudas (owner_id, updated_at, UNIQUE (id, owner_id), FK compuesta)

ALTER TABLE detalle_pagos
  ADD COLUMN owner_id   uuid NOT NULL DEFAULT auth.uid(),
  ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
  -- las dos puntas del detalle deben ser del mismo dueño
  DROP CONSTRAINT detalle_pagos_pago_id_fkey,
  DROP CONSTRAINT detalle_pagos_deuda_id_fkey,
  ADD FOREIGN KEY (pago_id,  owner_id) REFERENCES pagos  (id, owner_id) ON DELETE CASCADE,
  ADD FOREIGN KEY (deuda_id, owner_id) REFERENCES deudas (id, owner_id) ON DELETE CASCADE;

ALTER TABLE cruces_editados ADD COLUMN owner_id uuid NOT NULL DEFAULT auth.uid();
ALTER TABLE pagos_editados  ADD COLUMN owner_id uuid NOT NULL DEFAULT auth.uid();

-- Índices para RLS
CREATE INDEX ON deudores (owner_id);
CREATE INDEX ON deudas (owner_id, deudor_id);
CREATE INDEX ON pagos (owner_id, deudor_id);
CREATE INDEX ON detalle_pagos (owner_id);

-- updated_at automático (para el pull incremental de Flutter)
CREATE FUNCTION _tocar_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END $$;
-- BEFORE UPDATE en deudores, deudas, pagos, detalle_pagos

-- Lápidas: el pull incremental necesita enterarse de los borrados
CREATE TABLE borrados (
  tabla    text NOT NULL,
  id       uuid NOT NULL,
  owner_id uuid NOT NULL,
  at       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tabla, id)
);
-- AFTER DELETE en las 4 tablas → INSERT INTO borrados … ON CONFLICT DO NOTHING
```

**¿Por qué la FK compuesta?** Con solo `deudor_id`, alguien que conozca el UUID de un
deudor ajeno podría colgarle deudas. `(deudor_id, owner_id)` lo impide a nivel de esquema,
aunque el RLS falle.

**RLS**, en las 4 tablas y en `borrados`, `cruces_editados`, `pagos_editados`:

```sql
ALTER TABLE deudas ENABLE ROW LEVEL SECURITY;
CREATE POLICY propio ON deudas FOR ALL TO authenticated
  USING      (owner_id = (SELECT auth.uid()))
  WITH CHECK (owner_id = (SELECT auth.uid()));
-- borrados, cruces_editados, pagos_editados: solo SELECT propio (los escriben triggers/RPC)

-- Sin acceso anónimo a nada
REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM anon;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES    FROM anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon;
-- y DROP de todas las policies viejas "USING (true)"
```

`(SELECT auth.uid())` en vez de `auth.uid()` a secas: Postgres lo evalúa una vez por
consulta y no una por fila (recomendación de Supabase).

**RPC portados:**

- Se mantienen `SECURITY INVOKER`, así que el RLS los protege solos.
- Los de escritura en plpgsql (`aplicar_cruce`, `registrar_pago`, `editar_cruce`,
  `editar_pago`) agregan al inicio:
  ```sql
  IF NOT EXISTS (SELECT 1 FROM deudores WHERE id = p_deudor_id AND owner_id = auth.uid()) THEN
    RAISE EXCEPTION 'deudor ajeno o inexistente' USING ERRCODE = '42501';
  END IF;
  ```
  (`editar_pago` recibe `p_pago_id`: resolver el deudor desde el pago.)
- `estado_cuenta` es `LANGUAGE sql`: con RLS un deudor ajeno sale vacío, suficiente. **Su
  salida no cambia.**
- `GRANT EXECUTE … TO authenticated, service_role` (nada a `anon`).
- `rotar_token(p_deudor_id) RETURNS text`: pone un token nuevo y devuelve el valor.

### 5.2 Vínculos (migración `…_vinculos.sql`, fase 4)

```sql
CREATE TABLE invitaciones (
  codigo     text PRIMARY KEY,               -- 10 caracteres base32 (sin 0/O/1/I), aleatorio
  deudor_id  uuid NOT NULL,
  owner_id   uuid NOT NULL DEFAULT auth.uid(),
  expira     timestamptz NOT NULL DEFAULT now() + interval '7 days',
  usada_por  uuid REFERENCES perfiles,
  usada_at   timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (deudor_id, owner_id) REFERENCES deudores (id, owner_id) ON DELETE CASCADE
);

CREATE TABLE vinculos (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_a  uuid NOT NULL REFERENCES perfiles,  deudor_a uuid NOT NULL,  -- quien invitó
  usuario_b  uuid NOT NULL REFERENCES perfiles,  deudor_b uuid NOT NULL,  -- quien aceptó
  estado     text NOT NULL CHECK (estado IN ('conciliando','activo','roto')),
  conciliado_a boolean NOT NULL DEFAULT false,
  conciliado_b boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  roto_at    timestamptz,
  CHECK (usuario_a <> usuario_b),
  FOREIGN KEY (deudor_a, usuario_a) REFERENCES deudores (id, owner_id),
  FOREIGN KEY (deudor_b, usuario_b) REFERENCES deudores (id, owner_id)
);
CREATE UNIQUE INDEX ON vinculos (deudor_a) WHERE estado <> 'roto';
CREATE UNIQUE INDEX ON vinculos (deudor_b) WHERE estado <> 'roto';
CREATE UNIQUE INDEX ON vinculos (LEAST(usuario_a, usuario_b), GREATEST(usuario_a, usuario_b))
  WHERE estado <> 'roto';
```

- RLS: `SELECT` si `auth.uid() IN (usuario_a, usuario_b)`. Nadie escribe directo, solo por
  RPC.
- Las invitaciones las ve solo su dueño. El otro las consume con el RPC.
- Función auxiliar `_vinculo_de(p_deudor_id) RETURNS vinculos` (activo o conciliando),
  `STABLE SECURITY DEFINER`.

RPC: `crear_invitacion(p_deudor_id) RETURNS text` (anula las invitaciones previas sin usar
de ese deudor), `reclamar_invitacion(p_codigo, p_deudor_existente uuid DEFAULT NULL)
RETURNS uuid` (el vínculo), `desvincular(p_vinculo_id)`.

`reclamar_invitacion` es `SECURITY DEFINER` con `SET search_path = public`, porque lee una
invitación ajena. Debe:

- validar que exista, que no haya expirado, que no esté usada y que no sea propia;
- validar que ninguno de los dos deudores tenga ya un vínculo no roto;
- marcar la invitación como usada;
- crear el deudor si hace falta y crear el vínculo.

Todo en la misma transacción. Para un código inválido, el mensaje de error es siempre el
mismo, así no se puede sondear qué códigos existen.

### 5.3 Propuestas y acuerdos (migraciones `…_conciliacion.sql` y `…_propuestas.sql`, fases 5 y 6)

> **Implementado** en `20260924110000_conciliacion.sql` (fase 5) y
> `20260924120000_propuestas.sql` (fase 6). **Esas son la referencia.** Diferencias con el
> diseño de abajo: `propuestas` gana `resuelta_idem` y `resultado` (idempotencia de la
> respuesta); `verificar_vinculo` devuelve además `filas_sin_pareja`; la vista
> `vista_estado_deudas` gana `estado_acuerdo` al final; las decisiones 10 a 17 de §3.3.

```sql
ALTER TABLE deudas
  ADD COLUMN estado_acuerdo text NOT NULL DEFAULT 'local'
      CHECK (estado_acuerdo IN ('local','propuesta','acordada','rechazada')),
  ADD COLUMN origen_id uuid,
  ADD CONSTRAINT deudas_origen_unico UNIQUE (owner_id, origen_id);
ALTER TABLE pagos
  ADD COLUMN estado_acuerdo text NOT NULL DEFAULT 'local' CHECK (…mismo…),
  ADD COLUMN origen_id uuid,
  ADD CONSTRAINT pagos_origen_unico UNIQUE (owner_id, origen_id),
  ADD CONSTRAINT cruce_siempre_local CHECK (NOT es_compensacion OR estado_acuerdo = 'local');

CREATE TABLE propuestas (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vinculo_id   uuid NOT NULL REFERENCES vinculos,
  de_usuario   uuid NOT NULL DEFAULT auth.uid(),
  para_usuario uuid NOT NULL,
  entidad      text NOT NULL CHECK (entidad IN ('deuda','pago')),
  tipo         text NOT NULL CHECK (tipo IN ('crear','editar','borrar')),
  fila_origen  uuid NOT NULL,        -- fila en la libreta de quien propone
  payload      jsonb NOT NULL,       -- {monto, fecha, es_mia} DESDE el punto de vista de quien propone
  estado       text NOT NULL DEFAULT 'pendiente'
               CHECK (estado IN ('pendiente','aceptada','rechazada','anulada')),
  motivo       text,                 -- por qué se rechazó (opcional)
  fila_espejo  uuid,                 -- fila creada o enlazada al aceptar
  idem_key     uuid UNIQUE,
  created_at   timestamptz NOT NULL DEFAULT now(),
  resuelta_at  timestamptz
);
CREATE UNIQUE INDEX ON propuestas (fila_origen, tipo) WHERE estado = 'pendiente';
CREATE INDEX ON propuestas (para_usuario) WHERE estado = 'pendiente';

CREATE TABLE acuerdos (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vinculo_id uuid NOT NULL REFERENCES vinculos,
  entidad    text NOT NULL CHECK (entidad IN ('deuda','pago')),
  fila_a     uuid NOT NULL,   -- fila del usuario_a del vínculo
  fila_b     uuid NOT NULL,   -- fila del usuario_b
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (entidad, fila_a), UNIQUE (entidad, fila_b)
);
```

- RLS de `propuestas` y `acuerdos`: `SELECT` si soy parte del vínculo. Escritura solo por
  RPC o trigger.
- En el `payload`, `es_mia` es la dirección **vista por quien propone**. Al aceptar se
  invierte: `es_mi_deuda_espejo = NOT es_mia`.

**Triggers:**

- `_nace_propuesta`, `BEFORE INSERT` en deudas y pagos: si `_vinculo_de(NEW.deudor_id)`
  está `activo`, la fila no es un cruce y `NEW.origen_id IS NULL` (no es un espejo), pone
  `NEW.estado_acuerdo := 'propuesta'`.
- `_nace_propuesta_post`, `AFTER INSERT`: si la fila quedó `propuesta`, inserta en
  `propuestas` (`tipo = 'crear'`, `idem_key` derivado de la fila con `_idem_derivada`).
- `_guardia_acordada`, `BEFORE UPDATE OR DELETE` (§4.3).

**RPC:**

| RPC | Firma y comportamiento |
|---|---|
| `aceptar_propuesta` | `(p_id uuid, p_enlazar_con uuid DEFAULT NULL, p_crear_nueva boolean DEFAULT false, p_idem_key uuid DEFAULT NULL) RETURNS jsonb`. Solo la puede llamar `para_usuario`. Si `tipo = 'crear'`: aplica la capa 4 de §4.5, crea la fila espejo (dirección invertida, `origen_id = fila_origen`, `estado_acuerdo = 'acordada'`, en **mi** libreta) o enlaza con `p_enlazar_con` (que debe ser mía, del deudor del vínculo y no acordada). Para un pago espejo, reparte con la lógica interna de `registrar_pago`. Marca `acordada` la fila de origen e inserta en `acuerdos`. Si `tipo = 'editar' / 'borrar'`: aplica a las dos filas. `SECURITY DEFINER`, porque toca la fila del otro: **solo** su `estado_acuerdo` o los campos del acuerdo cuando la propuesta es de edición. |
| `rechazar_propuesta` | `(p_id uuid, p_motivo text DEFAULT NULL, p_idem_key uuid DEFAULT NULL)`. Solo `para_usuario`. §4.2 sobre la fila de origen (en la libreta del otro), así que también es `SECURITY DEFINER`. Si era `editar` o `borrar`, no toca ninguna fila. |
| `anular_propuesta` | `(p_id uuid)`. Solo `de_usuario`, solo si sigue pendiente. Si era `crear`, aplica §4.2 a su propia fila. |
| `proponer_cambio` | `(p_entidad text, p_fila uuid, p_tipo text, p_payload jsonb, p_idem_key uuid)`. Solo sobre filas `acordada` propias. |
| `candidatos_conciliacion` | `(p_vinculo_id) RETURNS jsonb` (§4.6). |
| `confirmar_conciliacion` | `(p_vinculo_id, p_pares jsonb)` (§4.6). |
| `verificar_vinculo` | `(p_vinculo_id) RETURNS jsonb {neto_a, neto_b, ok}`. |

**Cambios en `estado_cuenta()`:**

- Todas las lecturas filtran `estado_acuerdo <> 'rechazada'`.
- Cada deuda y pago de la salida gana `estado_acuerdo`.
- `resumen` gana `saldo_acordado` y `pendiente_acuerdo`, pero **solo** si el deudor tiene
  vínculo. Sin vínculo, la salida es idéntica a la de hoy (§4.1).
- `estado_cuenta` deja de poder ser `LANGUAGE sql` puro si hace falta una rama por
  vínculo: se puede resolver con un `LEFT JOIN` a `_vinculo_de`. Mantener `STABLE`.

---

## 6. Entorno y herramientas

### 6.1 Trampas del shell de esta máquina (Fedora 43, zsh)

- **No uses `cd`** en los comandos: un hook de zsh lanza `eza` y el comando se cuelga para
  siempre. Usa rutas absolutas o `env -C <dir> <comando>`.
- `cp` es interactivo (alias `cp -i`): usa `command cp -f`.
- **Escribe los archivos SQL con la herramienta de escritura de archivos, nunca con
  heredoc sin comillas**: los backticks de los comentarios se ejecutan (una migración ya
  quedó con `uid=1000(sebas)…` adentro). Antes de dar por bueno un `.sql`, revisa con
  `grep -n 'uid=1000' archivo`.
- `timeout` alrededor de `podman exec -i` se cuelga. Si necesitas un tiempo límite, ponlo
  dentro del programa (`subprocess.run(timeout=…)`).

### 6.2 Herramientas disponibles

| Herramienta | Dónde / cómo |
|---|---|
| Supabase CLI 2.109.1 | `~/.local/bin/supabase` **más** `~/.local/bin/supabase-go` (la primera es un *shim* que necesita la segunda al lado). Actualizar = bajar el tarball del release y copiar los **dos** binarios. No es npm |
| Proyecto al que apunta `--linked` | Depende del `--workdir`: en `deudas/v2` está enlazado a **v2 en la nube** (`deudas/v2/supabase/.temp/project-ref`, ignorado por git). En `deudas/` (la vieja) no hay enlace: para leer producción hay que crear a mano `deudas/supabase/.temp/project-ref` con `rcmdzvbxerumzxvnubfo` y borrarlo al terminar |
| SQL (local o nube) | `supabase db query --local` / `--linked` `-f archivo.sql` o `"SELECT …"` con `--workdir deudas/v2`. **Una sola sentencia por llamada** (para varias, un bloque `DO`); con `-o json` devuelve `{"rows": […]}`. `--linked` va por la Management API y no pide contraseña |
| Tests pgTAP | `supabase test db` (local) o `SUPABASE_DB_PASSWORD=… supabase test db --linked` (nube; `test db` no acepta `--password`) |
| Python del proyecto | `contabilidad/backend/.venv/bin/python` (el `python` del sistema no tiene pandas). **No hay `psycopg` ni `psql` en el host**: para SQL usa la CLI o `urllib` contra la API REST, como los scripts de `scripts/v2/` |
| Podman | Rootless. `podman.socket` de usuario **habilitado** (2026-09-23). `~/.config/containers/containers.conf` tiene `label = false` (necesario para el bundler de edge functions con SELinux) |
| Navegador headless | `firefox --headless --no-remote --profile <dir temporal> --window-size=430,1600 --screenshot out.png URL`. La captura sale en el evento `load`: si la página carga datos después, agrega a una **copia** de la página una imagen servida con retraso (ver notas de la fase 1) |
| Réplica PG17 vieja | Contenedor `deudas-replica` (`postgres:17-alpine`, parado). Es de la investigación del 12-sep: **v2 no la usa** |

### 6.3 Stack local de Supabase con Podman

```bash
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock   # la CLI espera Docker
env -C /home/sebas/dev/projects/ContabilidadPersonal/deudas/v2 ~/.local/bin/supabase start
env -C …/deudas/v2 ~/.local/bin/supabase status     # URLs y keys locales
env -C …/deudas/v2 ~/.local/bin/supabase stop       # apagar (conserva los datos)
```

- Puertos: API `54321`, DB `54322`, Studio `54323`, Mailpit/Inbucket (correos de prueba,
  magic links) `54324`.
- `config.toml` tiene apagados Realtime, Storage y Analytics.
- ⚠️ El stack escucha en `0.0.0.0` con keys de demostración. Apágalo en redes no
  confiables.
- `scripts/v2/_comun.py` pone el `DOCKER_HOST` solo.
- Rehacer la base local con los datos reales: ver `deudas/v2/README.md`. Es
  `db reset` → `crear_usuario.py` → `importar.py --owner`.

### 6.4 Proyecto v2 en la nube

| Dato | Valor |
|---|---|
| Nombre / ref | **Deudas v2** / `ggzvxehcsorlbroucbkp` |
| URL | `https://ggzvxehcsorlbroucbkp.supabase.co` |
| Región / compute | `us-east-2` / nano (plan **gratuito**) |
| Organización | `vercel_icfg_WvLWAK8UVzd44O4fr36p2Q7g` ("Sebas Arcentales' projects", gestionada por Vercel, gratuita). Es la **única** organización del dueño. Límite gratuito: 2 proyectos **activos**; hoy están activos "Deudas" (v1) y "Deudas v2"; "Solidaridad PUCE", "Trade" y "Titulacion" están pausados |
| Dashboard | https://supabase.com/dashboard/project/ggzvxehcsorlbroucbkp |
| Migraciones aplicadas | `20260923180000_base`, `20260923190000_duenos`, `20260924100000_vinculos`, `20260924110000_conciliacion`, `20260924120000_propuestas`, `20260924130000_conciliacion_tardias`, `20260924140000_publicacion` (`supabase migration list --linked`) |
| Edge functions | `get_estado_cuenta`, `get_historial`, `borrar_cuenta` (`verify_jwt = true`), `visor` (`verify_jwt = false`) |
| Auth | Email habilitado (magic link y contraseña). `site_url` y `additional_redirect_urls` = `com.deudas.deudas_app://login-callback`. Google **no** configurado (§9) |
| Usuarios hoy | `pruebas@deudas.local` (el de `probar_rpc_v2.py`, sin datos; sus ~240 lápidas en `borrados` son de sus pruebas y son legítimas). Ninguno real |
| Datos hoy | **Vacío.** Los datos reales se importaron una vez para ensayar el corte y se borraron (ver notas de la fase 2) |

**Secretos: `deudas/v2/.env`** (permisos 600, ignorado por git vía `.gitignore:11`).
Tiene `DEUDAS_V2_DB_PASSWORD`, `DEUDAS_V2_REF`, `DEUDAS_V2_URL`, `DEUDAS_V2_ANON_KEY` (la
*publishable*, pública por diseño) y `DEUDAS_V2_SERVICE_KEY` (la *secret*: **salta el
RLS**, solo para scripts de administración). Los scripts de `scripts/v2/` con
`--destino nube` lo leen solos. Si se pierde:

- las keys se vuelven a bajar con
  `supabase projects api-keys --reveal --project-ref ggzvxehcsorlbroucbkp -o json`
  (**sin `--reveal` la key secreta sale enmascarada** y da 401);
- la contraseña de la base se resetea desde el dashboard.

**Configuración de Auth como código:** `deudas/v2/supabase/config.toml` + el bloque
`[remotes.nube]` del final, que sobrescribe para la nube lo que arriba tiene valores de
desarrollo. Se aplica con `env -C deudas/v2 supabase config push`.

- ⚠️ **En modo agente `config push` NO pide confirmación: aplica directo.** Pasar "n" por
  stdin no sirve (así se aplicó por error una vez; ver notas de la fase 2).
- Revisa el diff que imprime y vuelve a correrlo: tiene que decir
  `Remote Auth config is up to date`.

**Cómo llevar un cambio a la nube** (fases 4 a 6; siempre **después** de que pase en local,
y con OK del dueño si toca algo que él usa). Desde la raíz, con
`set -a; . deudas/v2/.env; set +a` y
`export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock`:

```bash
# 1. migración nueva: deudas/v2/supabase/migrations/<AAAAMMDDhhmmss>_<nombre>.sql
#    (timestamp posterior a 20260923190000; escribirla con la herramienta de archivos)
env -C deudas/v2 ~/.local/bin/supabase db reset                        # local desde cero
#    … recrear usuario e importar (deudas/v2/README.md), correr tests y comparaciones …
~/.local/bin/supabase db push --password "$DEUDAS_V2_DB_PASSWORD" --workdir deudas/v2
~/.local/bin/supabase migration list --linked --workdir deudas/v2     # confirmar
SUPABASE_DB_PASSWORD="$DEUDAS_V2_DB_PASSWORD" ~/.local/bin/supabase test db --linked --workdir deudas/v2
# 2. edge functions
~/.local/bin/supabase functions deploy <nombres…> --project-ref $DEUDAS_V2_REF --workdir deudas/v2
# 3. end-to-end en la nube
contabilidad/backend/.venv/bin/python scripts/v2/probar_rpc_v2.py --destino nube
```

`db push` no revierte: una migración que falla a medias en la nube se arregla con otra
migración. Por eso se prueba en local primero.

**Keys nuevas vs legacy:** `sb_publishable_…` y `sb_secret_…` **no son JWT**. Van solo en
el header `apikey`, nunca en `Authorization: Bearer` (da 401). En `Authorization` solo va
el JWT de un usuario con sesión. Las legacy (`anon`, `service_role`, que empiezan por `eyJ`)
siguen activas, pero no hace falta usarlas.

### 6.5 Flutter

- Flutter y Dart no están en el host. Hay un distrobox `flutter-dev` (Ubuntu 24.04,
  Flutter 3.44.6, JDK 17, Android SDK 36).
- Comando: `distrobox enter flutter-dev -- bash -ic 'cd $APP_DEUDAS && flutter test'`. La
  primera vez puede tardar mientras "arma" el contenedor.
- **Build v1** (la que el dueño usa hoy): `flutter build apk`, sin defines.
- **Build v2** (login, contra la nube):
  ```bash
  set -a; . deudas/v2/.env; set +a
  distrobox enter flutter-dev -- bash -ic "cd \$APP_DEUDAS && flutter build apk --debug \
    --dart-define=DEUDAS_V2=true --dart-define=SUPABASE_URL=$DEUDAS_V2_URL \
    --dart-define=SUPABASE_ANON_KEY=$DEUDAS_V2_ANON_KEY"
  ```
  La última APK v2 compilada (2026-09-24, fases 2 a 7) está copiada en
  `deudas/flutter_app/build/app/outputs/flutter-apk/deudas-v2-nube-debug.apk`.
- Instalar en el celular: con el adb del host (`~/dev/tools/scrcpy/.../adb install -r <apk>`).
  ⚠️ La v1 y la v2 tienen el mismo `applicationId`: instalar una **reemplaza** a la otra.
  Para probar v2 sin perder la app diaria, usar otro teléfono o un emulador.
- `test/widget_test.dart` falla desde siempre (plantilla con `MyApp`); correr
  `flutter test test/plan_pago_test.dart test/resumen_whatsapp_test.dart`.
- `flutter analyze lib` da **167 avisos, todos previos** (mismo número en `main`); ningún
  error.
- El repo Flutter es **otro repo git** (`deudas/flutter_app/` → `Sebas04A/app_deudas`).
  Rama `v2`, **sin commits ni push** (ver §7).

---

## 7. Estructura de archivos de v2 (real, 2026-09-23)

```
deudas/
  PLAN_MULTIUSUARIO.md             ← este documento
  v2/                              ← proyecto Supabase v2 (repo ContabilidadPersonal)
    .env                           ← SECRETOS de la nube (ignorado por git), §6.4
    README.md                      ← cómo levantar, rehacer, probar
    supabase/
      config.toml                  ← local + [remotes.nube] (Auth de la nube)
      migrations/
        20260923180000_base.sql    ← volcado fiel de producción (generado, no editar)
        20260923190000_duenos.sql  ← fase 1
        20260924100000_vinculos.sql ← fase 4 (aplicada en la nube v2 el 2026-09-23)
        20260924110000_conciliacion.sql ← fase 5 (aplicada en la nube v2 el 2026-09-23)
        20260924120000_propuestas.sql ← fase 6 (generada, ver notas de la fase 6)
        20260924130000_conciliacion_tardias.sql ← hueco de la fase 5 y volver a vincularse
        20260924140000_publicacion.sql ← fase 7 (generada: copias exactas + «v2 fase 7»)
      functions/
        _shared/estado_cuenta.ts   ← lógica de v1 SIN CAMBIOS
        _shared/historial.ts       ← lógica de v1 + ORDER BY (notas de la fase 1)
        _shared/http.ts
        get_estado_cuenta/  get_historial/  visor/  borrar_cuenta/
      tests/
        01_rls.sql  02_rpc_duenos.sql  04_vinculos.sql  05_conciliacion.sql
        06_propuestas.sql  07_conciliacion_tardias.sql  08_publicacion.sql ← pgTAP, 231
    POLITICA_PRIVACIDAD.md         ← borrador (fase 7.2), sin publicar
  flutter_app/  (repo Sebas04A/app_deudas, rama v2, commiteada sin push)
    lib/config.dart                ← Entorno.esV2 / URL / key por --dart-define
    lib/screens/login_screen.dart  ← login (magic link + contraseña)
    lib/main.dart                  ← _PuertaDeSesion (solo v2)
    lib/services/database_service.dart  ← init(usuario:) y cerrar()
    lib/screens/home_screen.dart   ← "Cerrar sesión" (solo v2)
    lib/services/sync_report.dart  ← mensaje de 42501
    lib/services/cuenta_service.dart ← exportar mis datos / borrar mi cuenta (fase 7)
    android/app/src/main/AndroidManifest.xml ← intent-filter del deep link
  visor_web/    (repo público Sebas04A/visor_deudas, rama v2, commiteada y subida)
    js/app.js                      ← solo la edge `visor`; fuera de localhost → v2 nube
scripts/v2/                        ← ver deudas/v2/README.md
  _comun.py  backup_completo.py  capturar_linea_base.py  generar_migracion_base.py
  importar.py  crear_usuario.py  comparar_linea_base.py  comparar_edges.py  probar_rpc_v2.py
  medir_conciliacion.py  probar_concurrencia_propuestas.py  verificar_vinculos.py
  probar_fase7.py
contabilidad/debts/cliente.py      ← cliente Supabase por variables de entorno (fase 2.4)
backups/ (ignorado por git)
  deudas_v2_origen_20260923_181421/        ← respaldo completo de prod (6 tablas)
  estado_cuenta_baseline_v2_20260923/      ← línea base: 22 estados
```

La carpeta `deudas/supabase/` (la vieja) **no se toca**. Los datos reales van solo a
`backups/`, nunca a `deudas/v2/`, que sí se versiona (excepto `.env` y `supabase/.temp`).

---

## 8. Fases

---

### Fase 0 — Preparación y réplica local

**Objetivo.** Tener v2 corriendo en local con los datos reales del dueño y con **exactamente**
los mismos resultados que producción, *antes* de cambiar una sola regla. Si esta fase no
da cero diferencias, todo lo que venga después no se puede verificar.

**Prerrequisitos.** Ninguno.

**No toca producción:** solo la lee (backup y captura).

**Pasos**

- [x] **0.1 Backup completo.** `scripts/backup_deudas_supabase.py` solo respalda 4 tablas
      (`TABLAS = ["deudores", "deudas", "pagos", "detalle_pagos"]`). Crear
      `scripts/v2/backup_completo.py`, o agregar un argumento, que respalde también
      `cruces_editados` y `pagos_editados`. Destino: `backups/deudas_v2_origen_<fecha>/`.
      Verificar que los conteos coincidan con §1.3 (o con los actuales, si cambiaron).
- [x] **0.2 Capturar la línea base.** `scripts/v2/capturar_linea_base.py`: por cada
      deudor y cada `pov` en (`owner`, `debtor`), llama a `POST /rest/v1/rpc/estado_cuenta`
      y guarda `<deudor_id>__<pov>.json` más `_deudores.json`. Es el mismo formato que
      `backups/estado_cuenta_baseline_20260910/`, así que `comparar_linea_base.py` puede
      basarse en `scripts/verificar_estado_cuenta_equivalente.py`.
      **Capturar dos veces seguidas y comparar**: si difieren, la salida depende de la
      hora (`CURRENT_DATE`, etc.). Documentar qué campos y excluirlos de la comparación.
      Destino: `backups/estado_cuenta_baseline_v2_<fecha>/`.
- [x] **0.3 Volcar el esquema real.** `supabase db dump --linked --schema public -f
      /tmp/…/prod_schema.sql` (con `project-ref` temporal, §6.2). Si el volcado necesita
      Docker y falla, alternativa: consultas de solo lectura con `supabase db query
      --linked` que extraigan `pg_get_functiondef` de cada función, la definición de las
      tablas (`information_schema.columns`, constraints e índices con `pg_get_constraintdef`
      e `pg_indexes`), la vista y las policies (`pg_policies`).
      Anotar en "Notas de ejecución" si alguna función es `SECURITY DEFINER`.
- [x] **0.4 Inicializar v2.** `env -C deudas/v2 supabase init` (crear la carpeta).
      Levantar el stack local (§6.3).
- [x] **0.5 Migración base.** `deudas/v2/supabase/migrations/<ts>_base.sql` = el volcado
      de 0.3, con estos cambios y **ninguno más**:
      - quitar las policies `USING (true)` (el RLS se define en fase 1; mientras tanto el
        stack local solo lo usa el agente);
      - quitar los `GRANT … TO anon`;
      - las columnas `synced` **se quedan**: Flutter las manda en el `upsert`.
      Aplicar con `supabase db reset` (local) y confirmar que no hay errores.
- [x] **0.6 Importador.** `scripts/v2/importar.py --origen backups/deudas_v2_origen_<fecha>
      --destino local`:
      - genera un SQL con `INSERT … SELECT * FROM jsonb_populate_recordset(NULL::deudas,
        '<json>')` por tabla, en orden `deudores → deudas → pagos → detalle_pagos →
        cruces_editados → pagos_editados`;
      - conserva **todas** las columnas, incluidos `id`, `created_at`, `cruce_id`,
        `idem_key` y `nota`;
      - lo ejecuta con `supabase db query --local -f` dentro de un único bloque `DO` (la CLI
        manda una sola sentencia: `BEGIN; … COMMIT;` falla);
      - es idempotente: `ON CONFLICT (id) DO NOTHING`, o bien falla limpio si la base no
        está vacía.
- [x] **0.7 Comparar.** `scripts/v2/comparar_linea_base.py --destino local` llama a
      `estado_cuenta` en el stack local (API `54321` con la key `service_role` local, que
      en fase 0 no hay RLS que respetar) y compara contra 0.2.

**Verificación.** `comparar_linea_base.py` → `22 estados comparados, 0 diferencias` (11
deudores × 2 pov, o lo que den los conteos del momento).

**Criterio de salida.** Cero diferencias. Conteos de las 6 tablas en v2 local = backup.

**Qué NO hacer.** No "arreglar" nada del esquema ni de las funciones en la base (ni el bug
de $0.01, ni nombres, ni tipos). La fase 0 es una copia fiel.

**Notas de ejecución** (2026-09-23)

- **Resultado:** 22 estados comparados, 0 diferencias. Las 6 tablas son idénticas celda por
  celda al respaldo (11 / 335 / 41 / 271 / 4 / 3). Control negativo: alterar $0.01 en una
  copia de la línea base hace fallar la comparación, así que el cero es real.
- **Artefactos:**
  - respaldo `backups/deudas_v2_origen_20260923_181421/`;
  - línea base `backups/estado_cuenta_baseline_v2_20260923/`;
  - migración `deudas/v2/supabase/migrations/20260923180000_base.sql`;
  - scripts en `scripts/v2/` (ver `deudas/v2/README.md`).
- **`estado_cuenta` no depende de la fecha:** dos capturas seguidas salieron idénticas y el
  cuerpo de la función no usa `CURRENT_DATE` ni `now()`. No hay campos que excluir.
- **Lo que mostró el volcado de producción:**
  - **ninguna** función es `SECURITY DEFINER`;
  - no existe `_ec_lado` (solo estaba en migraciones viejas);
  - no hay triggers;
  - `pagos_editados.pago_id` **no** tiene FK (`cruces_editados.cruce_id` tampoco, porque no
    es una fila).
- ⚠️ **Para la fase 1:** la vista `vista_estado_deudas` es propiedad de `postgres` y **no**
  tiene `security_invoker`, así que se saltaría el RLS y mostraría las deudas de todos.
  Agregado al paso 1.1.
- **Entorno:**
  - La CLI `~/.local/bin/supabase` es un *shim* que necesita `supabase-go` al lado; faltaba.
    Se copió desde el tarball oficial v2.109.1 a `~/.local/bin/supabase-go`.
  - Se activó `podman.socket` (usuario).
  - `supabase db query` manda **una sola sentencia** y devuelve `{"rows": […]}`.
  - El stack local escucha en `0.0.0.0` con keys de demostración: no exponer esta máquina en
    redes no confiables mientras corre (`supabase stop` para apagarlo).
- `config.toml`: `project_id = "deudas_v2"`; Realtime, Storage y Analytics apagados.

---

### Fase 1 — Multi-dueño y seguridad (en local)

**Objetivo.** Que cada fila tenga dueño, que el RLS lo haga cumplir, que `anon` no pueda
nada y que el visor funcione solo con el token. Todo sin cambiar un centavo de ningún
saldo.

**Prerrequisitos.** Fase 0 ✅.

**Contexto.** §1.5 (agujeros actuales) y §5.1 (esquema). Después de esta fase, v2 es una app
multiusuario en la que cada uno tiene su libreta privada, sin vínculos todavía.

**Pasos**

- [x] **1.1 Migración `<ts>_duenos.sql`** con todo §5.1: `perfiles` + trigger de alta,
      `owner_id` y FK compuestas, `updated_at` + triggers, `borrados` + triggers, RLS en
      todas las tablas, `REVOKE` a `anon`, chequeo de dueño en los RPC de escritura,
      `rotar_token`, `moneda`.
      **Además:** `ALTER VIEW vista_estado_deudas SET (security_invoker = true);`, porque
      si no la vista corre como `postgres` y muestra las deudas de todos los usuarios. El
      test de RLS de 1.5 debe cubrirla.
      **Orden dentro de la migración:** columnas primero, **luego** el backfill de
      `owner_id` para las filas existentes (ver 1.2) y **después** `SET NOT NULL` y las FK
      compuestas.
- [x] **1.2 Usuario del dueño y backfill.**
      - En local: crear el usuario con la API de administración de Auth local
        (`POST /auth/v1/admin/users` con la `service_role` local) usando el email del
        dueño.
      - La migración no puede conocer ese UUID. Por eso el backfill lo hace
        `importar.py --owner <uuid>`: importar con `owner_id` explícito.
      - Recomendado: rehacer la base con `supabase db reset` (esquema de fase 1) y
        reimportar con `--owner`.
- [x] **1.3 Edge function `visor`** (`deudas/v2/supabase/functions/visor/index.ts`,
      `verify_jwt = false` en `config.toml`):
      - entrada `POST {token, accion: 'estado' | 'historial'}`;
      - con `SUPABASE_SERVICE_ROLE_KEY`, busca el deudor por `token`;
      - si no existe o `token_expira < now()` → `404` con un mensaje genérico;
      - si existe, devuelve lo mismo que hoy devuelven `get_estado_cuenta` (pov `debtor`)
        y `get_historial` para ese deudor;
      - **nunca** acepta `deudor_id` del cliente.
- [x] **1.4 Portar `get_estado_cuenta` y `get_historial`.** Copiarlas desde
      `deudas/supabase/functions/`. Cambio: crear el cliente con
      `global: { headers: { Authorization: req.headers.get('Authorization') } }` y la anon
      key, así corren **como el usuario** y el RLS aplica. Forzar `pov = 'owner'` (ignorar
      lo que mande el cliente). El resto del código, sin cambios.
- [x] **1.5 Tests pgTAP** en `deudas/v2/supabase/tests/`:
      - `00_helpers.sql`: crear dos usuarios de prueba A y B en `auth.users` y una función
        para "actuar como":
        `set local role authenticated; set local request.jwt.claims = '{"sub":"<uuid>","role":"authenticated"}'`.
      - `01_rls.sql`:
        - A no ve deudores, deudas, pagos, detalles ni bitácoras de B;
        - A no puede actualizar ni borrar filas de B (0 filas afectadas);
        - A no puede insertar una deuda con el `deudor_id` de B (falla la FK compuesta);
        - `anon` no puede hacer `SELECT` en ninguna tabla ni ejecutar ningún RPC.
      - `02_rpc_duenos.sql`:
        - `registrar_pago`, `aplicar_cruce`, `editar_cruce` y `editar_pago` con un deudor
          de B, actuando como A → error `42501`;
        - `estado_cuenta` con un deudor de B → vacío o sin deudas;
        - `rotar_token` ajeno → error.
      - Correr con `supabase test db`.
- [x] **1.6 Comparar otra vez contra la línea base**, ahora **autenticado como el dueño**:
      `comparar_linea_base.py` gana un modo que inicia sesión (`POST
      /auth/v1/token?grant_type=password` en local) y usa ese JWT.
- [x] **1.7 Prueba end-to-end de los RPC.** `scripts/v2/probar_rpc_v2.py`: portar la lógica
      de `scripts/probar_rpc_cruce.py`, `probar_pago_manual.py`, `probar_editar_cruce.py` y
      `probar_editar_pago.py` para que corra contra v2 local con un usuario de prueba (no
      el del dueño): crea su deudor temporal, ejercita y lo borra.
- [x] **1.8 Visor contra local.** Levantar `deudas/visor_web/` con un servidor estático
      apuntando a la API local y a la función `visor`, y abrir un token real importado.
      Solo cambia `fetchDebtorByToken` y las dos llamadas a funciones de `js/app.js`
      (líneas ~109-160). Hacerlo en una rama `v2` del repo `visor_deudas`.

**Verificación.** `supabase test db` en verde. Comparación autenticada con 0 diferencias.
`probar_rpc_v2.py` todo ✓. El visor muestra el mismo estado que en producción para el
mismo token.

**Criterio de salida.** Lo anterior, más una revisión manual de `pg_policies` en local:
ninguna policy con `USING (true)` y ninguna que mencione `anon`.

**Qué NO hacer.** No uses `service_role` fuera de las edge functions y los scripts de
administración. No cambies la matemática de ningún RPC.

**Notas de ejecución** (2026-09-23)

- **Resultado:**
  - `supabase test db` → 42 tests en verde (`tests/01_rls.sql`, `tests/02_rpc_duenos.sql`).
    Prueba en negativo: con `security_invoker` apagado en la vista y el RLS de `pagos`
    desactivado, la suite falla; al restaurar, pasa.
  - Línea base comparada como el dueño autenticado → 22/22 iguales.
  - `probar_rpc_v2.py` → los 4 scripts de v1 dan TODO OK como un usuario de prueba.
    Verificado que escribieron en v2, por las lápidas del usuario "Pruebas", y que
    producción sigue igual a la línea base.
  - `comparar_edges.py` → 55 respuestas iguales a las edges de producción.
  - Auditoría de `pg_policies`: 0 policies con `true` o para `anon`/`public`; todas las
    tablas con RLS.
- **Migración:** `20260923190000_duenos.sql`. `aplicar_cruce` y `registrar_pago` son copia
  exacta de la base más 2 líneas marcadas `v2:` (el chequeo de dueño). Las funciones que
  reciben un id de cruce o de pago no llevan chequeo, porque con RLS las filas ajenas no
  existen para ellas; los tests lo cubren. Además, `idem_key` pasó a ser único **por
  dueño**.
- **Usuario dueño en local:** `dueno@deudas.local` / `dueno-local-123` (nombre "Sebas"),
  creado con `scripts/v2/crear_usuario.py`. Es solo para local: la cuenta real con el email
  del dueño se crea en la fase 3. Usuario de pruebas: `pruebas@deudas.local`.
- **Rehacer local:** `supabase db reset` → `crear_usuario.py` → `importar.py --owner <uuid>`
  (el importador ahora inserta solo las columnas del respaldo, para que las nuevas tomen su
  DEFAULT).
- **Edge functions:**
  - La lógica de v1 se movió **tal cual** a `functions/_shared/estado_cuenta.ts` y
    `_shared/historial.ts` (cortada del código original con un script, no reescrita).
  - `get_estado_cuenta` y `get_historial` corren con el JWT del usuario y fuerzan
    `pov = 'owner'`.
  - `visor` (`verify_jwt = false`) recibe solo `{token, accion: deudor|estado|historial}` y
    nunca devuelve el id del deudor.
- ⚠️ **Diferencia a propósito con v1: el historial ahora tiene `ORDER BY`.** En v1 el orden
  de las deudas empatadas en `(fecha, created_at)` y el de los detalles de cada pago era el
  orden físico de las filas, es decir, arbitrario. Hay empates exactos al microsegundo por
  la migración masiva de febrero: en Madre, grupos de hasta 7 deudas el mismo día. v2
  desempata como el FIFO: `(fecha, created_at, id)`. `comparar_edges.py` exige el mismo
  contenido fila por fila y el mismo saldo final, e informa aparte las filas que cambian
  de lugar dentro de un empate (Ñaña 2, Madre 39). Revisadas una por una: todas están
  dentro de grupos empatados.
- **Visor:** rama `v2` del repo `visor_deudas` (local, **sin push**). `app.js` usa solo la
  edge `visor`, pasando el token en vez del `deudor_id`. En `localhost` apunta al stack
  local.
  - Probado con Firefox headless: el estado de Ñaña ($237,57) coincide con producción.
  - Truco para la captura: una imagen servida con 6 s de retraso hace esperar el evento
    `load`; si no, la captura sale en "Cargando…".
- **Pendiente para la fase 2:** en la nube hay que confirmar que los tests pasan (por
  `pg_safeupdate`) y que la anon key nueva (`sb_publishable_…`) funciona con
  `verify_jwt = true`.

---

### Fase 2 — Clientes contra v2 (proyecto de prueba en la nube)

**Objetivo.** Que la app Flutter, el visor y el backend de contabilidad funcionen contra un
proyecto v2 en la nube con **datos de prueba**, sin afectar al dueño, que sigue en la
base vieja.

**Prerrequisitos.** Fase 1 ✅. El dueño autorizó el 2026-09-23 crear el proyecto: "todo
gratuito, con mi cuenta".

**Estado (2026-09-23): 🟨 casi completa.** Lo que falta necesita al dueño o un dispositivo
(2.3, 2.5 y Google en 2.1) o es una mejora acotada (pull incremental en 2.2). Está al final
de la fase, en "Lo que falta".

**Pasos**

- [x] **2.1 Proyecto en la nube.** Creado "Deudas v2" (`ggzvxehcsorlbroucbkp`, us-east-2,
      nano, gratuito); todos los datos en §6.4.
      - `supabase link` + `db push`: las 2 migraciones aplicadas. El push imprime un error
        de `pg-delta` (`pgdelta-target-ca.crt: ENOENT`): es de un chequeo experimental
        posterior y no afecta; verificar siempre con `supabase migration list --linked`.
      - `functions deploy get_estado_cuenta get_historial visor`: las 3 activas y
        `verify_jwt` según `config.toml`.
      - `supabase test db --linked` → **42/42** en la nube.
      - Auth: email habilitado, deep link registrado (bloque `[remotes.nube]`).
      - [ ] **Google: código listo, falta el cliente OAuth del dueño** (§9). La app ya
            tiene "Continuar con Google" (`login_screen.dart`, `signInWithOAuth` por el
            navegador y el mismo deep link) detrás de `--dart-define=LOGIN_GOOGLE=true`; el
            bloque de `config.toml` está comentado al final con las instrucciones. Antes: Necesita crear un cliente OAuth en Google
            Cloud Console con su cuenta, y después:
            `[remotes.nube.auth.external.google] enabled = true`,
            `client_id = "…"`, `secret = "env(GOOGLE_SECRET)"` en `config.toml`, más
            `config push`. En la app: `signInWithOAuth(OAuthProvider.google,
            redirectTo: Entorno.redireccionLogin)`.
- [~] **2.2 Flutter** (repo `app_deudas`, rama `v2`, **sin commitear**):
      - [x] Configuración por entorno: `lib/config.dart` (`Entorno.esV2`, `supabaseUrl`,
            `supabaseAnonKey`, todo por `--dart-define`). **Sin defines = build v1 idéntica
            a la de antes**: la app diaria del dueño no cambia.
      - [x] Login (`lib/screens/login_screen.dart`): magic link, más "Entrar con contraseña"
            para las cuentas de prueba. Deep link `com.deudas.deudas_app://login-callback`
            en `AndroidManifest.xml`.
      - [x] Puerta de sesión (`main.dart`, `_PuertaDeSesion`, solo v2): sin sesión muestra
            el login; con sesión abre Hive **de esa cuenta** (`DatabaseService.init
            (usuario:)` → cajas `deudores_v2_<uid>`, …), crea el `SyncService` y monta la
            app de siempre. Al cerrar sesión cierra todo. `KeyedSubtree` por usuario.
      - [x] "Cerrar sesión" en el menú de la pantalla principal (solo v2).
      - [x] Error `42501` traducido como permanente ("el registro no pertenece a tu
            cuenta"). El sync ya no aborta todo ante un error de un registro.
      - [x] **El token del visor se sigue generando en el teléfono** (UUID v4 en
            `createDeudor`) y se sube con el deudor. Se decidió NO quitarlo de `toJson`
            (el plan original decía lo contrario): si lo generara el servidor, el enlace
            que la app comparte sin conexión no existiría. Es igual de seguro (122 bits
            aleatorios).
      - [x] `flutter analyze lib`: 0 errores, 167 avisos, **los mismos que en `main`**.
            `flutter test` (plan_pago + resumen_whatsapp): 11/11. APK v2 compila (§6.5).
      - [x] **Pull incremental** (2026-09-23, solo v2). `pullFromServer` guarda un cursor
            por cuenta (`ultimo_pull_<uid>` en `AppPreferences`, máximo `updated_at`/`at`
            recibido) y con él pide solo lo cambiado (`_pullIncremental`), con 2 min de
            margen hacia atrás (`updated_at` es la hora de inicio de la transacción).
            Lápidas de `borrados` → `DatabaseService.aplicarBorrados` (solo filas ya
            sincronizadas); `montoPagado` se rehace con los detalles de Hive
            (`recalcularMontosPagados`). No pisa filas locales sin subir. Sin cursor, en v1,
            tras "Reset a BD" o si una tanda llega a 1000 filas: pull completo como antes.
            Piezas puras en `lib/services/pull_incremental.dart`, test
            `test/pull_incremental_test.dart` (5). **Falta probarlo en un teléfono** (2.5,
            y editar un cruce desde otro dispositivo y sincronizar).
      - [ ] Probar en un dispositivo real: parte de 2.5.
- [x] **2.3 Visor** (repo público `visor_deudas`, rama `v2`, commit `640fc45`, **push hecho
      con OK del dueño el 2026-09-23**). Preview de Vercel:
      `https://visor-deudas-ed371l6vv-sebas-arcentales-projects.vercel.app/?token=<token>`
      (tiene la protección de despliegues de Vercel: desde fuera da 302 al login; el dueño
      la abre con su sesión o la desactiva en Settings → Deployment Protection). La nube
      está vacía, así que para probarla hace falta un deudor creado desde la APK v2 (2.5, paso 11).
      `js/app.js` usa solo la edge `visor` (token, nunca `deudor_id`). En `localhost`
      apunta al stack local y fuera de `localhost` al **proyecto v2 de la nube**. Probado
      contra el stack local con Firefox headless (fase 1), y las respuestas de la edge en
      la nube son iguales a producción (`comparar_edges.py --destino nube`).
      **Falta:** publicarlo en una URL de prueba. No hay CLI de Vercel en esta máquina y
      el visor se despliega por la integración de Git, así que la preview sale al hacer
      **push de la rama `v2`** (Vercel crea la preview de cualquier rama que no sea
      `main`). Es un repo **público**: pedir el OK del dueño antes del push. La rama solo
      contiene la URL y la key *publishable* de v2, que son públicas por diseño.
- [x] **2.4 Backend de contabilidad.** Nuevo `contabilidad/debts/cliente.py`: URL, key y
      sesión salen de `DEUDAS_SUPABASE_URL`, `DEUDAS_SUPABASE_KEY`, `DEUDAS_EMAIL` y
      `DEUDAS_PASSWORD` (entorno o `contabilidad/backend/.env`, ignorado por git). **Sin
      variables = v1 como siempre.** Rechaza una key `sb_secret_`. `reading.py` y
      `escritura.py` lo usan.
      - Se eligió email + contraseña y no refresh token: el proyecto rota los refresh
        tokens, así que uno guardado en `.env` deja de servir tras el primer uso.
      - Verificado: con las variables apuntando a v2 local y la sesión del dueño,
        `obtener_saldos_deudores`, `listar_deudores`, `obtener_deudas_para_analisis` y
        `obtener_pagos_para_analisis` dan **lo mismo** que v1. `obtener_estado_cuenta`
        también, salvo el `id` compuesto de un movimiento de cruce (`"a+b"` vs `"b+a"`):
        `reading.py` no ordena los dos pagos del cruce, que es el mismo orden físico
        arbitrario de las notas de la fase 1. Los resúmenes son idénticos.
      - Arreglado de paso: dos `.in_()` con todos los ids de las deudas en la URL
        (`reading.py`, `obtener_estado_cuenta` y `obtener_pagos_para_analisis`) superaban
        el límite del gateway (414 "URI too long") con deudores de cientos de deudas. Ahora
        van por tandas de 100.
      - Defecto previo, **no** arreglado: `reading.obtener_todas_deudas` usa `.where(…)`,
        que no existe en supabase-py (`AttributeError`). No la usa ninguna ruta del backend.
- [ ] **2.5 Flujo completo en un dispositivo** con una cuenta de prueba en v2. **Necesita
      al dueño** (un teléfono o emulador y un correo real para el magic link).
      Lista de comprobación, anotar el resultado de cada paso aquí:
      1. registrarse (magic link) y confirmar que abre la app por el deep link;
      2. crear un deudor;
      3. crear una deuda en cada sentido;
      4. pago automático;
      5. pago manual con deudas elegidas;
      6. cruce;
      7. editar el cruce;
      8. editar un pago;
      9. borrar una deuda;
      10. modo avión: crear una deuda y un pago, volver a la red y sincronizar;
      11. abrir el visor con el token de ese deudor (preview de 2.3);
      12. entrar en un segundo dispositivo y ver los mismos datos;
      13. cerrar sesión, entrar con **otra** cuenta y confirmar que no ve nada de la
          primera; volver a la primera y ver sus datos.

**Verificación hecha en la nube (2026-09-23)**

| Prueba | Resultado |
|---|---|
| `supabase test db --linked` | 42/42 |
| `probar_rpc_v2.py --destino nube` (4 scripts de v1, usuario de prueba, pasando por la API real con `pg_safeupdate`) | TODO OK |
| **Ensayo del corte**: `importar.py --destino nube` de los datos reales a una cuenta temporal `ensayo-corte@deudas.local` | 6/6 tablas con los conteos del respaldo |
| `comparar_linea_base.py --destino nube` (como esa cuenta) | 22/22 idénticos |
| `comparar_edges.py --destino nube` | 55/55 (mismas filas movidas por empates que en local) |
| Borrar la cuenta de ensayo (`DELETE /auth/v1/admin/users/<id>`) | La cascada borró su libreta entera (quedaron 0 filas). Se limpiaron sus 658 lápidas en `borrados`. Esto también prueba el "borrar mi cuenta" de la fase 7 |

**Lo que falta (para el siguiente agente)**

1. **2.5 con el dueño.** Es el criterio de salida. Instalar la APK v2 (§6.5) en un
   dispositivo que **no** sea el teléfono diario (misma `applicationId`: la reemplazaría).
2. **2.3 preview del visor:** con el OK del dueño,
   `git -C deudas/visor_web push -u origin v2` y abrir
   `https://<preview>/?token=<token de un deudor de prueba>`.
3. **Pull incremental (2.2).** Hoy `pullFromServer` (`lib/services/sync_service.dart`)
   baja las 4 tablas enteras. En v2 **funciona** igual (el RLS filtra), así que no bloquea
   el corte; es una optimización de disco y datos. Diseño:
   - guardar `ultimo_pull` por usuario (`AppPreferences`, clave con el uid);
   - pedir `deudores`, `deudas`, `pagos` y `detalle_pagos` con `.gt('updated_at',
     ultimo_pull)`, y `borrados` con `.gt('at', ultimo_pull)` para borrar localmente;
   - usar como nuevo `ultimo_pull` el máximo `updated_at` recibido, **no** la hora del
     teléfono, que puede estar desfasada;
   - ⚠️ hoy `montoPagado` de cada deuda sale de `vista_estado_deudas`. Si se baja solo lo
     que cambió, hay que recalcularlo localmente sumando los `detalle_pagos` de Hive (un
     pago nuevo cambia el `montoPagado` de deudas que no cambiaron);
   - la poda (`_podarLoQueYaNoEsta`) pasa a hacerse con `borrados`;
   - la primera vez (sin `ultimo_pull`) o con "Reset a BD", pull completo como hoy;
   - verificar: `flutter test` + un test nuevo del recálculo de `montoPagado`, y a mano:
     editar un cruce en la web o en otro dispositivo y ver que el teléfono lo refleja tras
     sincronizar.
4. **Google** (2.1), cuando el dueño cree el cliente OAuth.

**Criterio de salida.** 2.5 completo sin fallos, anotado aquí paso a paso.

**Qué NO hacer.**
- No apuntar la build que el dueño usa a diario al proyecto v2.
- No publicar el visor v2 en el dominio de producción (eso es la fase 3).
- No importar datos reales en v2 salvo para un ensayo, y borrarlos después, como el
  2026-09-23.

**Notas de ejecución** (2026-09-23)

- ⚠️ **Error cometido y corregido:** para ver el diff de Auth corrí `supabase config push`
  pasándole "n" por stdin. **En modo agente no pregunta: aplicó** los valores de
  desarrollo local a la nube:
  - confirmación de email apagada;
  - TOTP apagado;
  - reenvíos permitidos cada 1 s;
  - códigos de 6 dígitos.

  El proyecto estaba vacío y sin usuarios reales, así que no afectó a nadie. Se corrigió
  agregando `[remotes.nube]` (valores por defecto de la nube + deep link) y volviendo a
  hacer `config push`; la siguiente corrida dice "up to date". **No usar `config push`
  para mirar el diff.**
- La key secreta se guardó primero enmascarada (`api-keys` sin `--reveal`) y todo daba 401
  "Invalid API key". Ver §6.4.
- `supabase test db --linked` no acepta `--password`: usar `SUPABASE_DB_PASSWORD`.

---

### Fase 3 — Corte: el dueño se muda a v2

**Objetivo.** Pasar los datos reales del dueño a v2 y que desde ese momento la app, el visor
y el backend usen v2. La base vieja queda como respaldo de solo lectura y después se
pausa.

**Prerrequisitos.** Fase 2 ✅ (en particular 2.5). **El dueño elige el momento** (sin pagos
a medio registrar, con la app sincronizada). El corte **ya se ensayó** en la nube el
2026-09-23 con los datos reales (notas de la fase 2): importar y comparar funcionan tal cual.

**Por qué los enlaces del visor siguen funcionando:** el importador conserva el `token` de
cada deudor, igual que todos los ids. El mismo `?token=` de siempre, abierto en el visor v2,
encuentra al mismo deudor en v2.

**Pasos** (todos el mismo día, en este orden; `PY=contabilidad/backend/.venv/bin/python`,
todo desde la raíz del repo)

- [ ] **3.1 Congelar v1.**
      - El dueño abre la app vieja, sincroniza, comprueba en "Estado de sincronización"
        que no queda nada pendiente y **deja de usarla**.
      - El backend de contabilidad se apaga al final de 3.2, para que nadie escriba en v1
        durante el corte.
- [ ] **3.2 Respaldo y línea base finales** (solo leen producción):
      ```bash
      $PY scripts/v2/backup_completo.py              # → backups/deudas_v2_origen_<fecha>/
      $PY scripts/v2/capturar_linea_base.py          # → backups/estado_cuenta_baseline_v2_<fecha>/
      # con el backend de contabilidad TODAVÍA levantado y en v1 (el script llama a su API):
      $PY scripts/snapshot_dashboard.py capturar --nombre pre_corte_v2
      ```
      Después apagar el backend.
- [ ] **3.3 Cuenta real del dueño en v2.** Con su email real y una contraseña que el dueño
      elija (el backend la necesita; en la app puede entrar con magic link igual):
      ```bash
      OWNER=$($PY scripts/v2/crear_usuario.py --destino nube --email <email del dueño> \
                --clave '<contraseña>' --nombre Sebas)
      ```
      Anotar el UUID en las notas de esta fase.
- [ ] **3.4 Importar.**
      ```bash
      $PY scripts/v2/importar.py --origen backups/deudas_v2_origen_<fecha> --destino nube --owner $OWNER
      ```
      Imprime ✓ por tabla si los conteos coinciden con el respaldo. El usuario
      `pruebas@deudas.local` no tiene datos y puede quedarse, porque `probar_rpc_v2.py` lo
      usa.
- [ ] **3.5 Verificar** (todo tiene que dar 0 diferencias):
      ```bash
      $PY scripts/v2/comparar_linea_base.py backups/estado_cuenta_baseline_v2_<fecha> \
          --destino nube --email <email> --clave '<contraseña>'
      $PY scripts/v2/comparar_edges.py --destino nube --email <email> --clave '<contraseña>'
      ```
      - `comparar_edges.py` lee producción. Todavía funciona porque en 3.8 se deja el
        `SELECT`.
      - Además, cada `deuda_id` y `pago_id` de `data/sistema/etiquetado/etiquetas.csv`
        tiene que existir en v2. Script corto: leer el CSV con pandas, juntar los ids no
        vacíos, pedir `GET /rest/v1/deudas?select=id&id=in.(…)` por tandas de 100 con la
        sesión del dueño y comparar.
- [ ] **3.6 Cambiar los clientes.**
      - **Backend de contabilidad:** crear `contabilidad/backend/.env` (ignorado por git)
        con `DEUDAS_SUPABASE_URL`, `DEUDAS_SUPABASE_KEY` (la *publishable* de
        `deudas/v2/.env`), `DEUDAS_EMAIL` y `DEUDAS_PASSWORD` (los de 3.3). Levantar el
        backend. En el log tiene que aparecer "Deudas: sesión iniciada como …".
        `$PY scripts/snapshot_dashboard.py comparar --nombre pre_corte_v2` (con los
        filtros apagados) tiene que dar idéntico: el dashboard no puede moverse un centavo.
      - **Flutter** (repo `app_deudas`):
        - commitear la rama `v2` y fusionarla en `main`;
        - cambiar en `lib/config.dart` los `defaultValue` a los de v2 y `esV2` a
          `bool.fromEnvironment('DEUDAS_V2', defaultValue: true)`, para que una build sin
          defines ya sea v2;
        - build **release**. Ojo: `android/app/build.gradle.kts` firma el release con la
          clave de **debug** de esta máquina. Actualiza sin problema sobre las APK
          compiladas aquí, pero para la Play Store (fase 7) hace falta una clave propia;
        - instalar en el teléfono del dueño.

        Al primer login, la app baja todo del servidor a sus cajas nuevas por usuario. Las
        cajas viejas de v1 quedan en el teléfono sin uso; se pueden borrar después.
      - **Visor** (repo público `visor_deudas`): commitear la rama `v2`, fusionarla en
        `main` y hacer push. Vercel publica `main` en `visor-deudas.vercel.app`.
      - **Web de contabilidad:** no cambia; habla con el backend.
      - **Scripts viejos de `scripts/`** (`backup_deudas_supabase.py`, `verificar_*`,
        `probar_*`, `exportar_deudas_excel.py`, …): siguen apuntando a v1 y quedan
        obsoletos. Sus equivalentes están en `scripts/v2/` (`probar_rpc_v2.py` reutiliza
        los `probar_*`). Los que se sigan usando deben pasar a `contabilidad/debts/cliente.py`
        o a `scripts/v2/_comun.py`.
- [ ] **3.7 Comprobar el visor publicado** con 2 o 3 tokens reales: el monto y los
      movimientos iguales a los de 3.2.
- [ ] **3.8 Base vieja de solo escritura cerrada** (**con OK del dueño**). Guardar como
      `deudas/supabase/migrations/<ts>_solo_lectura_post_corte.sql` y aplicarlo con
      `supabase db query --linked -f …` desde `deudas/` (necesita el `project-ref`
      temporal, §6.2; una sola sentencia, así que un `DO`):
      ```sql
      DO $$
      BEGIN
          DROP POLICY "Admin full access deudores"        ON deudores;
          DROP POLICY "Admin full access deudas"          ON deudas;
          DROP POLICY "Admin full access pagos"           ON pagos;
          DROP POLICY "Admin full access detalles"        ON detalle_pagos;
          DROP POLICY "Admin full access cruces_editados" ON cruces_editados;
          DROP POLICY "Admin full access pagos_editados"  ON pagos_editados;
          REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
          REVOKE EXECUTE ON FUNCTION registrar_pago(uuid, numeric, boolean, date, uuid, uuid[]),
                                     aplicar_cruce(uuid, date, uuid, boolean),
                                     editar_cruce(uuid, uuid[], boolean, uuid),
                                     _editar_cruce_aplicar(uuid, uuid[]),
                                     editar_pago(uuid, date, text, uuid)
              FROM anon, authenticated, PUBLIC;
      END $$;
      ```
      Los nombres de las policies y las firmas salen del volcado de la fase 0; confirmar
      con `SELECT policyname, tablename FROM pg_policies` antes de aplicar. Las policies
      de `SELECT` se quedan, así que la base vieja sigue legible.
- [ ] **3.9 Pausar la base vieja** (**con OK del dueño**, una o dos semanas después del
      corte). Mientras exista, cualquiera puede **leerla**: la anon key de v1 está en el
      historial del repo público del visor y las policies de `SELECT` son `USING (true)`.
      - Antes de pausar: un último `scripts/v2/backup_completo.py`.
      - Pausar desde el dashboard (Settings → General → Pause project). Así queda un solo
        proyecto activo en el plan gratuito.
      - Un proyecto gratuito pausado se puede restaurar durante un tiempo limitado
        (confirmar el plazo actual en el dashboard); después solo queda el backup.
- [ ] **3.10 Documentación.**
      - Actualizar `deudas/README.md` ("la base de producción es v2").
      - En este plan: §1.2 (componentes) y §6.4 (usuarios y datos de la nube).
      - La memoria del proyecto (`deudas-v2-multiusuario.md`, `cruce-en-el-backend.md`,
        `entorno-shell-y-supabase-sql.md`).

**Plan de vuelta atrás.**
- **Si 3.5 da diferencias:** no seguir. La app vieja sigue funcionando porque la base
  vieja todavía no se cerró. Borrar la cuenta del dueño en v2 (la cascada limpia) y
  volver a intentarlo.
- **Si el problema aparece después de 3.8:** revertir el SQL de 3.8 (recrear las policies
  `FOR ALL USING (true)` y los grants a `anon`, que están en el volcado de la fase 0),
  reinstalar la APK vieja, devolver `main` del visor al commit anterior y borrar
  `contabilidad/backend/.env`. Lo escrito en v2 durante ese intervalo se exporta a mano.

**Criterio de salida.** El dueño usa v2 durante una semana sin incidentes. **Desde aquí la
app se puede publicar** en su versión "cada uno con su libreta" (fase 7 para lo mínimo
legal).

**Notas de ejecución.** *(vacío)*

---

### Fase 4 — Invitaciones y vínculos

**Objetivo.** Que una Persona de mi libreta pase a estar vinculada con su Usuario real.

**Prerrequisitos.** Fase 3 ✅. Se desarrolla **en local** y se despliega con confirmación.

**Contexto.** §4.4 y §5.2. Todavía no hay propuestas: en esta fase un vínculo se crea y
queda `conciliando` sin más. Las fases 5 y 6 le dan uso.

**Pasos**

- [x] **4.1** (2026-09-23; en la nube v2 con OK del dueño, 69/69 tests allí) Migración `20260924100000_vinculos.sql`: tablas, índices, RLS, `_vinculo_de`,
      `crear_invitacion`, `reclamar_invitacion` y `desvincular`, según §5.2.
- [x] **4.2** (2026-09-23) Tests pgTAP `04_vinculos.sql`, 27 tests; en local pasan los 69 (42 + 27):
      - flujo feliz A invita a B, con B creando deudor nuevo y con B eligiendo uno
        existente;
      - código expirado, usado o propio → error genérico;
      - segundo vínculo del mismo par → error;
      - deudor ya vinculado → error;
      - A no puede reclamar su propia invitación;
      - desvincular → `roto`, y se puede volver a invitar;
      - B no ve las invitaciones de A;
      - nadie hace `INSERT` directo en `vinculos`.
- [x] **4.3** Flutter, versión sin dominio (2026-09-23, rama `v2` de `app_deudas`, sin
      commitear): `services/vinculos_service.dart`; en el detalle del deudor, ícono
      "Invitar a la app" (o "Vinculado" con opción de desvincular) que comparte el mensaje
      con el **código** por la hoja de WhatsApp; menú ⋮ → "Aceptar invitación"
      (`screens/aceptar_invitacion_screen.dart`: código + contacto nuevo o existente);
      "Vinculado" en la lista de deudores. Todo solo en v2. **Pendiente:** el enlace
      `https://<dominio>/i/<código>` y el App Link, que esperan la decisión de dominio (§9);
      mientras tanto el código se escribe a mano. E2E por la API de la nube con dos
      cuentas temporales (borradas después): crear, canjear, reusar → 22023, desvincular. OK.
- Plan original de 4.3:
      - en el detalle del deudor, botón "Invitar a la app" → `crear_invitacion` →
        compartir por WhatsApp un enlace `https://<dominio>/i/<código>` (el mensaje reusa
        el estilo de `resumen_whatsapp.dart`);
      - deep link `/i/<código>`: si no hay sesión, login primero; después, pantalla
        "Sebas te invitó" con dos opciones: "Crear contacto nuevo" o "Ya lo tengo: elegir
        de mi lista";
      - indicador de "vinculado" en la lista de deudores;
      - ojo: hoy el único deep link registrado es
        `com.deudas.deudas_app://login-callback` (`AndroidManifest.xml`, fase 2.2). Para
        abrir `https://<dominio>/i/<código>` en la app hace falta un *App Link* de Android
        (`android:autoVerify="true"` más `/.well-known/assetlinks.json` publicado en ese
        dominio, que puede servir el visor en Vercel). La alternativa sin dominio propio:
        un esquema propio `com.deudas.deudas_app://invitacion/<código>`, que WhatsApp no
        muestra como enlace tocable. Recomendado: App Link, con la ruta del visor como
        respaldo (4.4).
- [ ] **4.4** Visor: la ruta `/i/<código>` en el dominio del visor muestra "Descarga la app"
      (Play Store) y pasa el código a la app si está instalada.

**Notas de 4.1/4.2 (2026-09-23).** Se adelantaron mientras la fase 2 espera el teléfono.
El dueño autorizó el `db push` al proyecto v2 de prueba para probar esta noche; el corte
(fase 3) importa sobre este esquema sin problema (las tablas nuevas nacen vacías).
Decisiones tomadas que el esquema de §5.2 no decía:
- `crear_invitacion` y `desvincular` son también `SECURITY DEFINER` (validan `auth.uid()`
  al principio): así nadie escribe `invitaciones` ni `vinculos` directo (ni se fabrica un
  código ni estira su vencimiento). §10 actualizado.
- Los FK de `vinculos` a `deudores` llevan `ON DELETE CASCADE`: sin eso la app no podría
  borrar un contacto vinculado. Borrarlo se lleva el vínculo (para los dos).
- `crear_invitacion` rechaza un deudor que ya tiene vínculo vivo (`23505`).
- El código se canjea sin importar mayúsculas ni espacios.
- Trampa: `(_vinculo_de(x)) IS NOT NULL` es falso aunque haya vínculo (`roto_at` es
  nulo, y `fila IS NOT NULL` exige todos los campos). Usar `(_vinculo_de(x)).id`.
- `db reset` borró los datos importados de la base **local**; para rehacerlos,
  `deudas/v2/README.md`.

**Criterio de salida.** Tests en verde y dos celulares reales vinculados en el proyecto v2
(con cuentas de prueba o con el dueño y alguien de confianza, lo que el dueño elija).

**Notas de ejecución.** *(vacío)*

---

### Fase 5 — Conciliación inicial

**Objetivo.** Al vincularse, emparejar el historial de las dos libretas sin duplicar nada.

**Prerrequisitos.** Fase 4 ✅. Necesita las columnas `estado_acuerdo`, `origen_id` y la tabla
`acuerdos`: ponerlas en `<ts>_conciliacion.sql`, o adelantar la parte de esquema de
`_propuestas.sql` (sin triggers).

**Contexto.** §4.6 y §4.5, capa 5.

**Pasos**

- [x] **5.1** (`20260924110000_conciliacion.sql`; en la nube v2 con OK del dueño) Migración: `CREATE EXTENSION IF NOT EXISTS pg_trgm`, las columnas de §5.3,
      `acuerdos`, `propuestas`, `candidatos_conciliacion` y `confirmar_conciliacion`.
      `estado_cuenta` todavía no cambia en esta fase.
- [x] **5.2** (`scripts/v2/medir_conciliacion.py`, solo local) Juego de datos de prueba realista:
      - tomar un deudor real **importado en local** (nunca en la nube) y crear una segunda
        libreta de prueba que lo refleje con ruido: fechas ±2 días, títulos distintos
        ("Uber 28 ag" vs "uber"), dos deudas de más de un lado y una de menos del otro;
      - medir cuántos pares acierta `candidatos_conciliacion` y anotarlo;
      - casos especiales: dos deudas con el mismo monto y fechas cercanas (la asignación
        voraz no debe cruzarlas mal si los títulos ayudan) y pagos que son cruces (deben
        ignorarse).
- [x] **5.3** (`05_conciliacion.sql`, 20 tests; 89 en total, verdes en local y nube) Tests pgTAP: los pares confirmados quedan `acordada` en ambas libretas; las
      filas sin par de quien confirma quedan `propuesta`; confirmar dos veces no duplica
      nada; ninguna fila queda en dos acuerdos.
- [x] **5.4** (`screens/conciliacion_screen.dart`) Flutter: pantalla de conciliación, que aparece al terminar de reclamar la
      invitación y en el detalle del deudor mientras el vínculo esté `conciliando`, con
      las tres listas de §4.6. Botones: "Son la misma" / "No", "Enviar las mías" y
      "Listo".

**Criterio de salida.** Tests en verde; en el juego de datos de 5.2, cero pares
incorrectos confirmados automáticamente (lo dudoso se le pregunta al usuario).

**Notas de ejecución** (2026-09-23)

- **Medición (5.2)** con el deudor real de más movimientos (222 deudas + 19 pagos), libreta
  espejo con fechas ±2 días, títulos cambiados (minúsculas, primera palabra o "gasto"), 2
  de menos y 2 de más, 12 semillas: ~237 de 239 pares correctos, 0–5 incorrectos por
  semilla (cuando falta la pareja real de una deuda repetida, otra igual la "ocupa").
  - Con el umbral de "dudoso" del diseño inicial (0.15) se colaba **1 par incorrecto sin
    marcar** (semilla 11). Con **0.5**: **0 en las 12 semillas**, a cambio de ~10 pares
    correctos que se le preguntan al usuario. Se dejó 0.5.
  - La UI no confirma nada sola: los pares no dudosos vienen marcados y el usuario los
    puede desmarcar. Los dudosos (⚠️) vienen sin marcar.
  - Tras la migración, `comparar_linea_base.py` en local: 22/22 idénticos (los saldos no
    cambian en esta fase).
- **Decisiones que el plan no decía:**
  - `candidatos_conciliacion` y `confirmar_conciliacion` son `SECURITY DEFINER` (leen y
    marcan filas del otro). §10 actualizado.
  - Del otro solo se muestran monto, fecha y dirección: **nunca sus títulos** (son
    privados, §4.3). La similitud de títulos se usa dentro del servidor para el puntaje.
  - Si el vínculo ya está `activo`, `confirmar_conciliacion` no hace nada (idempotente).
  - Toma el candado de los dos deudores, en orden fijo.
  - Las propuestas de la conciliación usan `idem_key = _idem_derivada(fila, 'conciliacion')`.
- **Límite conocido:** si a los dos les falta la pareja de filas idénticas (mismo monto y
  fecha), el par incorrecto no tiene competidor y no sale como dudoso. En los datos
  medidos no pasó.
- Las propuestas que genera la conciliación **todavía no se pueden aceptar ni rechazar**:
  eso es la fase 6.

**Notas de ejecución** (2026-09-24, `20260924130000_conciliacion_tardias.sql`, en la nube;
tests `07_conciliacion_tardias.sql`, 21)

- **Hueco de las filas tardías, arreglado** (decisión 18 de §3.3). Si una parte confirmaba
  y anotaba algo antes de que la otra confirmara, esa fila nacía `local` y se quedaba así.
  Ahora, cuando el vínculo pasa a `activo`, lo `local` que le queda al que confirmó
  primero se le propone al que cierra, con título. `confirmar_conciliacion` devuelve
  `"tardias": n` solo si hubo alguna (la respuesta de siempre no cambia). Control
  negativo: con la función anterior fallan 5 tests.
- **Volver a vincularse fallaba de dos formas** (encontrado al probar lo anterior):
  1. `confirmar_conciliacion` daba `23505`: la clave de idempotencia era
     `_idem_derivada(fila, 'conciliacion')`, sin el vínculo, y `desvincular` deja la
     propuesta anulada con esa clave mientras devuelve la fila a `local`. Ahora la clave
     lleva el vínculo (`'conciliacion|' || vínculo`; las tardías, `'tardia|' || vínculo`).
  2. Lo acordado en el vínculo roto seguía `acordada` sin acuerdo en el nuevo: la guardia
     lo bloqueaba, `proponer_cambio` no encontraba la pareja y `verificar_vinculo` daba
     descuadre. Ahora `reclamar_invitacion` llama a `_soltar_acuerdos_viejos` para los dos
     deudores: vuelve a `local`, se borran los acuerdos viejos y la conciliación nueva lo
     empareja (decisión 19).
- Regresión en local tras la migración: línea base 22/22, edges 55/55, `probar_rpc_v2` OK.

---

### Fase 6 — Propuestas continuas

**Objetivo.** Con el vínculo activo, cada deuda o pago nuevo, y cada cambio a algo
acordado, pasa por aceptar o rechazar.

**Prerrequisitos.** Fase 5 ✅.

**Contexto.** §4.1 a §4.5 y §5.3. Es la fase más delicada: toca `estado_cuenta` y el
reparto de pagos.

**Pasos**

- [x] **6.1** (`20260924120000_propuestas.sql`, solo local) Migración `<ts>_propuestas.sql`:
      - triggers `_nace_propuesta`, `_nace_propuesta_post` y `_guardia_acordada`;
      - RPC `aceptar_propuesta`, `rechazar_propuesta`, `anular_propuesta`,
        `proponer_cambio` y `verificar_vinculo`;
      - `estado_cuenta` con el filtro de `rechazada`, `estado_acuerdo` en la salida y
        `saldo_acordado`/`pendiente_acuerdo` solo con vínculo.
- [x] **6.2** (22/22, 0 diferencias; la línea base es la de la fase 0 porque la 3 no se hizo) **Regresión primero:** comparar contra la línea base de la fase 3 (deudores
      sin vínculo) → 0 diferencias. Si no da 0, parar.
- [x] **6.3** (96 tests, con control negativo) Tests pgTAP `06_propuestas.sql`. Cada escenario termina comprobando
      `verificar_vinculo(...).ok = true` **y** que "mi saldo" de cada uno sea el esperado:
      1. A crea una deuda "B me debe $20" → en A queda `propuesta`, B tiene una propuesta
         pendiente → B acepta → espejo en B con `es_mi_deuda = true`, ambas `acordada`,
         saldo acordado A = +20 y B = −20.
      2. Igual con un pago.
      3. B rechaza una deuda → en A queda `rechazada` y no cuenta en ningún saldo.
      4. A le había cobrado $5 a B (pago en A) y esa deuda de $20 queda rechazada → los $5
         pasan a saldo a favor de B en la libreta de A.
      5. Una deuda de A entró en un cruce y B la rechaza → el cruce se recorta; ningún pago
         virtual queda con sobrante.
      6. B ya tenía "Cena $20" (`local`) → aceptar la propuesta devuelve
         `hay_candidatos` → aceptar con `p_enlazar_con` → no se crea una fila nueva y la
         de B pasa a `acordada`.
      7. Doble aceptación con el mismo `idem_key` → segunda respuesta idéntica, una sola
         fila espejo. Con otro `idem_key` → error "ya resuelta".
      8. `proponer_cambio` de monto 20 → 25; B acepta → las dos filas en 25. B rechaza →
         las dos siguen en 20.
      9. `UPDATE deudas SET monto = 99` directo sobre una fila `acordada` → `42501`.
         `UPDATE … SET titulo = 'x'` → permitido.
      10. `anular_propuesta` por A mientras está pendiente → `rechazada` en A; B ya no la
          ve pendiente.
      11. Desvincular con propuestas pendientes → quedan anuladas.
      12. B intenta aceptar una propuesta dirigida a otro usuario → `42501`.
- [x] **6.4** (`scripts/v2/probar_concurrencia_propuestas.py`, con control negativo) Prueba de concurrencia: A registra un pago mientras B acepta una deuda del
      mismo vínculo (dos sesiones a la vez, script Python con dos hilos contra local).
      Ningún error de lock sin manejar y la invariante se mantiene.
- [x] **6.5** (rama `v2` de `app_deudas`, sin commitear; falta probarlo en celulares) Flutter:
      - bandeja de propuestas (contador en el inicio; cada una con Aceptar / Rechazar,
        motivo opcional y, si hay candidatos, "Es esta que ya tengo");
      - filas `propuesta` con la marca "pendiente" y `rechazada` tachadas con su motivo;
      - en el detalle del deudor vinculado: "Mi saldo" y "Saldo acordado";
      - editar monto, fecha o dirección de una fila acordada → abre "proponer cambio" en
        vez de guardar directo;
      - `PlanPago` (cálculo local) debe excluir `rechazada`;
      - actualizar `test/fixtures` si cambia su formato;
      - cola sin conexión: aceptar y rechazar se encolan como RPC con `idem_key`, igual
        que `registrar_pago`.
- [x] **6.6** (`tests/test_deudas_rechazadas.py`) Backend de contabilidad (`reading.py`): excluir `rechazada` donde lea deudas
      y pagos directo de las tablas (`obtener_todas_deudas`, `obtener_todos_pagos`,
      `obtener_*_para_analisis`); lo que viene de `estado_cuenta` ya llega filtrado.
- [~] **6.7** (`scripts/v2/verificar_vinculos.py` listo; programarlo, no) Opcional: tarea programada diaria que corre `verificar_vinculo` sobre todos
      los vínculos activos y registra los que no cuadran.

**Criterio de salida.** Los 12 escenarios y la prueba de concurrencia en verde; regresión en
0; una semana de uso real entre dos personas vinculadas sin descuadres.

**Notas de ejecución** (2026-09-23)

- **Resultado (todo en local):**
  - `supabase test db` → **185/185** (42 + 27 + 20 + 96). `06_propuestas.sql` recorre los
    12 escenarios en orden sobre la misma pareja; cada uno termina con
    `verificar_vinculo().ok` y con "mi saldo" (`resumen.neto`) de los dos, con los números
    calculados a mano en los comentarios. **Control negativo:** con `_sacar_de_cruces` y
    `_guardia_acordada` anulados fallan 15 (el saldo de A se mueve si no se recorta el
    cruce, y pasa el `UPDATE` directo).
  - Regresión: `comparar_linea_base.py` 22/22; `comparar_edges.py` 55/55 (las mismas
    filas movidas por empates que en la fase 1); `probar_rpc_v2.py` TODO OK. Auditoría de
    `pg_policies`: 0 con `true` o para `anon`/`public`.
  - Concurrencia (6.4): `probar_concurrencia_propuestas.py` con dos cuentas temporales
    vinculadas por el flujo real; en cada ronda cada uno anota una deuda y, a la vez en
    dos hilos, registra un pago y acepta o rechaza su bandeja. 6 semillas × 25–30 rondas:
    sin errores, `verificar_vinculo` ok y las dos libretas cuadran (ningún cruce con
    sobrante, nada repartido de más ni sobre algo rechazado; la edge da el mismo saldo
    acordado y el historial no muestra lo rechazado). **Control negativo:** sin los
    candados de `_bloquear_vinculo`, 3 de 3 semillas fallan (deudas rechazadas con
    reparto).
  - Backend: `pytest tests` → 15489 pasan; fallan 3 del pipeline de tarjeta/flujo de
    usuario que fallan igual sin estos cambios (son de la rama del dueño). Los 4 tests
    nuevos fallan si se quita el filtro.
  - Flutter: `flutter analyze lib` 0 errores (171 avisos: los 167 de antes + 4
    `withOpacity`, el mismo idioma del resto del archivo); `flutter test` de
    plan_pago, resumen_whatsapp, pull_incremental, vínculos y propuestas: 28/28. La APK v2
    compila (`deudas-v2-nube-debug.apk`, **contra la nube, que todavía no tiene esta
    migración**: no instalarla para probar la fase 6 hasta subirla).
  - `verificar_vinculos.py` (6.7) detecta un descuadre forzado a mano (sale con 1).
- **Cómo se armó la migración:** `estado_cuenta`, `registrar_pago`,
  `_editar_cruce_aplicar` y `confirmar_conciliacion` son copia **exacta** de su migración
  anterior más las líneas marcadas `v2 fase 6`. Se generaron con un script que copia la
  función y aplica cada parche exigiendo que el ancla aparezca una sola vez; el archivo
  final es estático y se revisa con un diff contra el original.
- **Qué cambió en funciones existentes y por qué:**
  - `estado_cuenta`: filtra `rechazada` en deudas y pagos; con vínculo vivo (vía
    `_vinculo_de`, que mira `auth.uid()`: el visor con la service_role nunca lo ve) agrega
    `estado_acuerdo` por deuda y `saldo_acordado`/`pendiente_acuerdo` al resumen. Sin
    vínculo la salida es byte a byte la de antes (lo prueba la regresión).
  - `registrar_pago`: el FIFO no le paga a una deuda rechazada.
  - `_editar_cruce_aplicar`: la variable `deudas.recorte_libre` salta la regla de "solo
    la última operación". La pone solo `_sacar_de_cruces`: al rechazar hay que recortar
    cruces viejos (§4.2).
  - `confirmar_conciliacion` (fase 5): enciende `deudas.en_rpc`; si no, la guardia nueva
    le conservaría el `estado_acuerdo` viejo. Se detectó porque fallaron sus tests.
  - `desvincular` (fase 4): decisión 11 de §3.3.
  - Vista `vista_estado_deudas`: gana `estado_acuerdo` al final (la app la usa en el pull
    completo y `reading.py` filtra con ella).
- **Piezas nuevas que el plan no nombraba:** `_detalle_antes` (trigger en
  `detalle_pagos`: en los RPC el dueño del detalle es el de su pago —quien rechaza
  recorta un cruce de la libreta del OTRO y el `DEFAULT auth.uid()` ponía mal el dueño; la
  FK compuesta lo frenó— y nadie reparte sobre una fila rechazada), `_propuesta_al_dia`
  (si quien propuso corrige su fila antes de la respuesta, la propuesta se actualiza),
  `_propuesta_sin_fila` (si la fila se borra, su propuesta se anula), `_soltar_deuda`,
  `_soltar_pago`, `_sacar_de_cruces`, `_bloquear_vinculo`, `_tomar_propuesta`.
- **Estados y origen los decide el servidor:** en un INSERT directo se ignoran (nace
  `local` o `propuesta`; `origen_id` NULL) y en un UPDATE directo se conservan los de
  antes. Así un Flutter viejo, o uno que suba un valor desactualizado, no puede
  "desacordar" nada. `importar.py` enciende `deudas.en_rpc` para que un respaldo de v2 se
  restaure con sus estados.
- **Flutter (6.5):** `estadoAcuerdo` en `Deuda` y `Pago` (campo Hive nuevo con valor por
  defecto; las cajas existentes se leen sin migrar; no se sube nunca). Los cálculos
  locales (totales, saldo a favor, cruce y pago sin conexión, `PlanPago`) ignoran lo
  rechazado. Bandeja con contador en la barra (`BotonBandeja`), aceptar con "¿es esta que
  ya tenías?" y rechazar con motivo; sin conexión se ve la última bandeja y las respuestas
  van a una cola (`cola_propuestas_<uid>`) con su `idem_key`, que el sync manda después de
  subir las filas. Detalle del deudor: "MI SALDO" + saldo acordado + lo que espera
  respuesta, marca PENDIENTE / 🤝 por fila y las rechazadas tachadas con su motivo.
  Editar algo acordado: el título se guarda directo, monto y fecha se proponen; borrarlo
  se propone. **Menores hechos el 2026-09-24:** el historial marca cada fila (PENDIENTE /
  🤝; la edge ya mandaba `estadoAcuerdo`) y una deuda mía pendiente tiene "Retirar
  propuesta" (pulsación larga → `anular_propuesta` + pull): queda tachada como rechazada,
  en vez de desaparecer como al borrarla.
- ~~**Pendiente detectado de la fase 5:** filas anotadas entre las dos confirmaciones~~.
  Arreglado el 2026-09-24 con OK del dueño (notas de la fase 5).

**Lo que falta (para el siguiente agente)**

1. ~~Subir a la nube de prueba~~: **hecho el 2026-09-24** con OK del dueño. `db push`,
   `test db --linked` 185/185 (231 con lo que se subió después), las 3 edges desplegadas,
   `probar_rpc_v2.py --destino nube` OK, `probar_concurrencia_propuestas.py --destino nube
   --rondas 10` OK, APK v2 recompilada.
2. **Probar en dos celulares** (cuentas de prueba): anotar, aceptar, rechazar con motivo,
   enlazar con una ya anotada, proponer un cambio de monto y de borrado, responder sin
   conexión y sincronizar.
3. **La semana de uso real** entre dos personas vinculadas (criterio de salida).
4. Programar `verificar_vinculos.py` (6.7), si el dueño lo quiere: GitHub Actions o
   `pg_cron` en el proyecto.
5. Que el dueño revise las decisiones 10 a 17 de §3.3.

---

### Fase 7 — Publicación

**Objetivo.** Lo necesario para abrir la app a cualquiera.

**Prerrequisitos.** Fase 3 ✅ para publicar "cada uno su libreta". Fase 6 ✅ para publicar
con vínculos.

- [ ] **7.1** Notificaciones push (Firebase Cloud Messaging):
      - tabla `dispositivos (owner_id, token_fcm)`;
      - edge function disparada por un *database webhook* en `INSERT` de `propuestas` y
        en `UPDATE` de su `estado`.
- [~] **7.2** Privacidad (Ley Orgánica de Protección de Datos Personales, Ecuador):
      - [~] política de privacidad: **borrador** en `deudas/v2/POLITICA_PRIVACIDAD.md`.
            Falta que el dueño complete lo que está entre corchetes (responsable, correo,
            plazos), la revise y la publique (p. ej. `/privacidad` en el visor);
      - [x] "Exportar mis datos": RPC `exportar_mis_datos()` (JSON de mi libreta, en orden
            fijo) y menú ⋮ → "Exportar mis datos" en la app (hoja de compartir);
      - [x] "Borrar mi cuenta": edge `borrar_cuenta` (`{confirmar: "BORRAR"}`, con la
            sesión del usuario) → `preparar_baja()` rompe sus vínculos con `desvincular` →
            `auth.admin.deleteUser` con la service_role → la cascada se lleva la libreta.
            Las filas espejo del otro no se tocan. Una cuenta que se borra ya no deja
            lápidas (`_lapida` mira si el perfil existe y `perfil_sin_lapidas` borra las
            viejas). En la app: menú ⋮ → "Borrar mi cuenta" (hay que escribir BORRAR), y
            la puerta de sesión borra sus cajas de Hive y sus preferencias.
- [x] **7.3** Límites de uso: `crear_invitacion` 20 por día por usuario, `reclamar_invitacion`
      10 códigos inválidos por hora (tabla `intentos_canje`) y `visor` 60 consultas por
      minuto e IP (tabla `visitas_visor`, con el SHA-256 de la IP, borrado a la hora).
      Pasado el límite: `PT429` → HTTP 429. Decisión 20 de §3.3.
- [ ] **7.4** Plan de Supabase adecuado (§9), backups diarios activos y alertas de uso.
- [ ] **7.5** Play Store: prueba interna → prueba cerrada → producción. Ficha, icono y
      capturas.

**Notas de ejecución** (2026-09-24). Se adelantó lo que no necesita al dueño (7.2 salvo
publicar la política, y 7.3), con su OK: "Fase 7 en local", y después subirlo a la nube de
prueba.

- `20260924140000_publicacion.sql` (en la nube): `_lapida`, `crear_invitacion` y
  `reclamar_invitacion` son copia exacta de su migración anterior más las líneas marcadas
  `v2 fase 7`; se generó con un script que exige que cada ancla aparezca una vez.
- **Cambio de contrato:** `reclamar_invitacion` con un código que no sirve devuelve NULL (la
  app lo traduce en `CodigoInvalido`). `04_vinculos.sql` se adaptó (5 asserts).
- Tests: `08_publicacion.sql` (25). En local y en la nube: 231/231. Control negativo: con
  el `_lapida` viejo y sin `perfil_sin_lapidas`, falla el de las lápidas.
- `scripts/v2/probar_fase7.py` (local y nube: TODO OK): exportar, canje con código malo,
  límite del visor, `borrar_cuenta` sin y con confirmación, que la cuenta no pueda entrar,
  sin lápidas ni libreta, y que el otro conserve lo suyo en `local`.
- El límite del visor es por **minuto del reloj**: una ráfaga que cruza el cambio de
  minuto puede llegar a 60 + 60 antes del 429 (pasó en la nube: 30 + 33). Suficiente contra
  abusos; si hiciera falta algo más fino, sumar el minuto anterior.
- Cada consulta al visor escribe una fila (`visitas_visor`). Con el uso actual es poco,
  pero cuenta para el Disk IO del plan gratuito (§10).
- Regresión tras la migración: línea base 22/22, edges 55/55 (el límite no molesta a
  `comparar_edges.py`), `probar_rpc_v2` OK (local y nube), concurrencia OK en la nube.
- Flutter: `flutter analyze lib` 0 errores (171 avisos, los de antes); tests 29/29 (uno
  nuevo en `vinculos_test.dart`). `XFile.fromData` para exportar: `share_plus` lo guarda
  en un temporal antes de compartir (`method_channel_share.dart`).
- **Falta probarlo en un celular:** exportar, borrar una cuenta de prueba, y que al volver a
  entrar con otra cuenta no quede nada de la borrada.

---

## 9. Pendiente de decidir (preguntar al dueño en la fase indicada)

| Decisión | Se necesita en | Opciones / recomendación |
|---|---|---|
| ~~Plan y organización del proyecto v2~~ | Fase 2 | **Decidido (2026-09-23):** todo gratuito, con la cuenta del dueño, en su única organización (la gestionada por Vercel). Para **publicar** (fase 7) conviene revisarlo: el plan gratuito con Nano ya agotó el presupuesto de Disk IO de v1 con un solo usuario; Pro cuesta ~$25/mes. **No subir de plan sin el dueño.** |
| Proveedores de login | Fase 2 | Email (magic link y contraseña) **ya activo**. Google: **aplazado por el dueño (2026-09-23)**; el código queda escondido tras `LOGIN_GOOGLE`. En su tesis solo podía entrar él: casi seguro la pantalla de consentimiento estaba en modo *Prueba* (solo entran los "usuarios de prueba"); para abrirlo a todos hay que *Publicar app*, y con solo email/perfil no pide verificación de Google. Antes: pendiente del dueño, que tiene que crear el cliente OAuth en Google Cloud Console (ver 2.1). Apple solo si hay versión iOS. |
| ¿Commitear el trabajo de v2 y en qué ramas? | Ya | Ver §0.3. Recomendación: rama `feat/deudas-v2` en este repo y ramas `v2` en `app_deudas` y `visor_deudas`. |
| Nombre y dominio públicos | Fase 4 (enlaces de invitación) | — |
| ¿Corregir el bug de $0.01? | Después de la fase 3 | Corregirlo con su propia verificación, nunca mezclado con una migración de v2. |
| ¿El visor muestra "saldo acordado" a un deudor vinculado? | Fase 6 | Por defecto el visor sigue igual (decisión del dueño: "funciona tal cual"). Implementado así: el visor usa la service_role y `estado_cuenta` no le agrega nada. |
| ¿El título viaja en la propuesta? ¿Desvincular devuelve a `local` lo pendiente? | Fase 6 (ya implementado así) | Decisiones 10 y 11 de §3.3. Confirmar con el dueño. |
| ~~Filas anotadas entre las dos confirmaciones de la conciliación~~ | — | **Decidido y hecho (2026-09-24):** se proponen al pasar a `activo` (decisión 18). |
| Límites de uso (20 invitaciones/día, 10 canjes fallidos/hora, 60 visor/minuto) | Antes de publicar | Implementados con esos valores (decisión 20). Ajustar si el dueño prefiere otros. |
| Política de privacidad | Antes de publicar | Borrador en `deudas/v2/POLITICA_PRIVACIDAD.md`: completar responsable, correo y plazos, revisar y publicar. |

---

## 10. Trampas conocidas

- **`pg_safeupdate`:** en la API de Supabase, un `UPDATE` o `DELETE` sin `WHERE` dentro de
  un RPC aborta con `21000`. El stack local **puede** no reproducirlo: correr los tests
  también en la nube (fase 2.1).
- **`created_at` es parte del orden FIFO.** No lo pises al importar, al hacer upsert desde
  Flutter ni al crear filas espejo. La espejo lleva su propio `created_at = now()`; el
  orden entre libretas no se compara.
- **`schema.sql` está desactualizado.** La verdad es el volcado de la fase 0.
- **La anon key es pública por diseño.** El problema nunca es la key sino las policies.
- **`SECURITY DEFINER`:** siempre con `SET search_path = public`, validando `auth.uid()` al
  principio, y solo en `crear_invitacion`, `reclamar_invitacion`, `desvincular`,
  `candidatos_conciliacion`, `confirmar_conciliacion`,
  `aceptar_propuesta`, `rechazar_propuesta`, `anular_propuesta`, `proponer_cambio`,
  `verificar_vinculo`, `_vinculo_de` y los triggers de `perfiles`, `borrados` y
  `propuestas` (`_nace_propuesta_post`, `_propuesta_al_dia`, `_propuesta_sin_fila`).
- **Flutter guardaba mal `es_compensacion`/`es_mi_pago` en el pull** (ya corregido). Si
  tocas `pullFromServer`, comprueba que las columnas nuevas (`estado_acuerdo`,
  `origen_id`, `updated_at`) también se copien.
- **Cola de sincronización envenenada:** un error permanente (FK, `42501`) no se reintenta
  para siempre; se reporta y se sigue con el resto. Ya hay un arreglo parcial en
  `sync_service.dart`; mantenerlo.
- **Disk IO en el plan gratuito:** iterar migraciones en la nube cuesta disco (PostgREST
  recarga su caché de esquema con cada DDL). Iterar en local y subir a la nube solo lo
  terminado.

Trampas encontradas en las fases 0 a 2:

- **`supabase config push` en modo agente aplica sin preguntar**, aunque le pases "n" por
  stdin. Nunca lo uses para "ver el diff" (§6.4).
- **`supabase projects api-keys` sin `--reveal` enmascara la key secreta**, y la versión
  enmascarada da 401 "Invalid API key".
- **Las keys `sb_publishable_…` y `sb_secret_…` no son JWT:** van solo en `apikey`, nunca
  en `Authorization: Bearer`.
- **`supabase db query` ejecuta una sola sentencia:** `BEGIN; …; COMMIT;` falla; usar un
  `DO`.
- **`supabase test db` no acepta `--password`:** usar `SUPABASE_DB_PASSWORD`.
- **`supabase db push` imprime un error de `pg-delta`** (`pgdelta-target-ca.crt: ENOENT`)
  aunque las migraciones se apliquen. Verificar con `supabase migration list --linked`.
- **Orden físico ≠ orden:** toda consulta sin `ORDER BY` devuelve las filas en el orden en
  que están guardadas, que cambia al importar. Afecta a los empates exactos (la migración
  masiva de febrero dejó hasta 7 deudas con el mismo `created_at` al microsegundo). Al
  comparar v1 con v2 se normaliza ese orden (`comparar_edges.py`), pero **cualquier
  consulta nueva debe llevar `ORDER BY` con desempate por `id`**.
- **Listas de ids en la URL** (`.in_()` de supabase-py, `id=in.(…)` de PostgREST): con
  cientos de UUID se pasa el límite del gateway (414). Mandarlos por tandas de 100.
- **zsh no separa en palabras una variable con espacios:** `Q="supabase db query …"; $Q`
  intenta ejecutar un archivo con ese nombre. Usar un arreglo `Q=(supabase db query …)`.
- **`pkill -f patrón` se mata a sí mismo** si el patrón aparece en la propia línea de
  comando del shell. Buscar los PID con `ps` y matar esos.
- **La app v1 y la v2 comparten `applicationId`** (`com.deudas.deudas_app`): instalar una
  reemplaza a la otra en el mismo teléfono.
- **`reading.obtener_todas_deudas` está rota desde antes** (`.where` no existe en
  supabase-py). No la usa ninguna ruta; no confundirla con una regresión. Por eso tampoco
  lleva el filtro de lo rechazado de la fase 6.

Trampas encontradas en la fase 6:

- **`deudas.en_rpc` se apaga antes de volver.** Es local a la transacción; en PostgREST
  cada llamada es la suya, pero en una prueba pgTAP (todo en una transacción) un 'on'
  olvidado desactivaría las guardias de todo lo que siga. Un error revierte el valor solo.
- **Quien acepta o rechaza escribe en la libreta del otro** (SECURITY DEFINER). Cualquier
  `INSERT` que dependa de `DEFAULT auth.uid()` pondría mal el dueño: por eso existe
  `_detalle_antes`. Si agregas un RPC así, revisa cada `INSERT`.
- **Todo `UPDATE` de `estado_acuerdo` o `origen_id` necesita `deudas.en_rpc`**: sin él, la
  guardia conserva el valor viejo EN SILENCIO (no da error). Así se rompió
  `confirmar_conciliacion` hasta que se le agregó.
- **Precedencia de operadores:** `x->'resumen' - 'clave'` se lee como
  `x -> ('resumen' - 'clave')`. Paréntesis: `(x->'resumen') - 'clave'`.
- **La APK v2 apunta a la nube.** Si la app es más nueva que las migraciones de la nube,
  lo que dependa de ellas falla (p. ej. aceptar propuestas sin la fase 6): no es un error
  de la app. Desde el 2026-09-24 la nube tiene todo lo del repo.

Trampas encontradas el 2026-09-24:

- **Claves de idempotencia derivadas de una fila:** si la fila puede volver a proponerse
  (desvincular y volver a vincular), la clave tiene que llevar también el vínculo; si no,
  choca con la propuesta anulada de antes (`23505`).
- **Runtime de edges local:** no ve una función nueva hasta reiniciarlo, y puede seguir
  sirviendo el código viejo de una editada: `podman restart supabase_edge_runtime_deudas_v2`.
- **`auth.getUser()` en una edge:** sin argumento busca una sesión guardada y falla
  aunque el header `Authorization` esté puesto; hay que pasarle el JWT.
- **pgTAP y dólares anidados:** `lives_ok($$DO $x$ … $x$$$)` no parsea (`$x$$$`). Usar
  otro delimitador por fuera: `$o$DO $x$ … $x$ $o$`.
- **Dentro de una función, un `RAISE` deshace todo lo que la función escribió**, también
  el registro de un intento fallido. Para contar fallos hay que responder sin error (por
  eso `reclamar_invitacion` devuelve NULL).

---

## 11. Documentos relacionados

| Documento | Para qué |
|---|---|
| `deudas/LOGICA_SISTEMA.md` | Arquitectura y matemática completa (cruce, pago manual, FIFO) |
| `deudas/PENDIENTE_IO_Y_SEGURIDAD.md` | Investigación de Disk IO y los agujeros de seguridad actuales |
| `contabilidad/debts/PLAN_PRUEBAS_DEUDAS.md` | Casos de prueba de la matemática |
| `contabilidad/debts/CASOS_ARBOL_DEUDAS.md` | Casos generados (árbol) |
| `deudas/flutter_app/DESARROLLO_LINUX.md` | Cómo compilar Flutter en esta máquina |
| `contabilidad/backend/services/debt_links.py` | Reglas de vínculo transacción↔deuda de contabilidad (mismo espíritu uno a uno que `acuerdos`) |
