# Deudas v2 — plan multiusuario

> Escrito el **2026-09-23**. Documento autocontenido: un agente que solo lea este archivo
> debe poder ejecutar cualquier fase sin perderse. Si algo de aquí contradice el código,
> **el código manda**: verifica, corrige este documento y avisa al dueño.

---

## 0. Cómo usar este documento (léelo si eres un agente)

> **¿Eres el dueño?** Lo que te toca, paso a paso, está en **§0.4**.

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
| 3 | Corte: el dueño se muda a v2 | 🟨 hecho el corte (3.1–3.7, 2026-09-25): datos en la nube, backend, app y visor en v2; faltan instalar la app en el teléfono del dueño, 3.8 (cerrar la base vieja, con OK), 3.9 y la semana de uso | 2026-09-25 | Claude |
| 4 | Invitaciones y vínculos | 🟨 adelantada: 4.1–4.3 hechas y en el proyecto v2 de prueba; falta 4.4 (visor/App Link) y probar en 2 celulares | 2026-09-23 | Claude |
| 5 | Conciliación inicial | 🟨 adelantada: 5.1–5.4 hechas y en el proyecto v2 de prueba; hueco de las filas tardías y revincularse arreglados (2026-09-24); falta probar en celulares | 2026-09-24 | Claude |
| 6 | Propuestas continuas | 🟨 adelantada: 6.1–6.7 hechas y **en el proyecto v2 de prueba** (2026-09-24, con OK del dueño; 231 tests pgTAP allí); menores hechos (retirar propuesta, historial con estado); falta probar en celulares y la semana de uso real | 2026-09-24 | Claude |
| 7 | Publicación | 🟨 adelantada: 7.2 (exportar, borrar cuenta; política de privacidad en borrador) y 7.3 (límites) hechas y en la nube de prueba; faltan 7.1 (Firebase), 7.4, 7.5 y publicar la política: todo necesita al dueño | 2026-09-24 | Claude |
| 8 | Aceptación automática y avisos | 🟨 hecha y **en la nube de prueba** (398 tests allí, concurrencia OK), commiteada, APK recompilada; falta probar en dos celulares (§0.4 B) | 2026-09-24 | Claude |
| 9 | Gastos divididos y grupos | 🟨 hecha en local (9.1–9.7: 714 tests pgTAP, paridad Dart↔SQL, `probar_grupos.py` con 3 cuentas, regresión en 0, `flutter build web` OK); `180000` corregida (2026-09-25, dos agujeros de seguridad); **en la nube de prueba desde el 2026-09-25** (714/714 allí, `probar_grupos` y `probar_rpc_v2` OK), commiteada y APK recompilada; falta probar en celulares | 2026-09-25 | Claude |

Estados: ⬜ pendiente · 🟨 en curso · ✅ hecha (criterio de salida cumplido) · ⛔ bloqueada
(escribir el motivo).

### 0.3 Dónde quedó todo (leer primero; actualizado 2026-09-24)

**Hecho:**
- v2 existe en local (`deudas/v2`) y en la nube: proyecto gratuito "Deudas v2",
  `ggzvxehcsorlbroucbkp` (§6.4).
- Cada fila tiene dueño y el RLS lo hace cumplir. Tests pgTAP: **231** (fases 1 y 4 a 7),
  verdes en local y en la nube (2026-09-24); **398** con la fase 8, en los dos.
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

**Fase 8 hecha en local (2026-09-24, tarde):** el dueño revisó las decisiones 21 a 24
(cambió 21, 22 y 24) y se implementó todo: migración `20260924150000_aceptacion_automatica.sql`
(398 tests), concurrencia, Flutter con "Novedades" y el aviso previo de duplicados, y
`flutter build web`. Commiteada, con la APK recompilada y **en la nube de prueba** (el
`db push` lo corrió el dueño; 398/398 allí). Lo que sigue es la prueba en dos celulares.

**Fase 9 hecha en local (2026-09-24, noche)**, sin nube ni commit, como pidió el dueño:
migraciones `20260924160000_gastos.sql` (9A), `20260924170000_grupos.sql` (9B) y
`20260924190000_grupos_sin_nadie.sql` (arreglo), tests `10`, `11` y `13` (709 en total),
Flutter con "Dividir entre varios", pestaña Grupos e inicio con contactos + grupos, y
`scripts/v2/probar_grupos.py` (3 cuentas por la API real: los saldos de los tres cuadran).
En local también quedó aplicada `20260924180000_fix_rechazar_cruces.sql` (de otra sesión),
**corregida el 2026-09-25**: su primera versión abría dos agujeros de seguridad (notas de la
fase 9); 714 tests. **Cerrada el 2026-09-25 a pedido del dueño:** commits `53c4d77`
(`feat/deudas-v2`) y `4d619a6` + `7a458c0` (`app_deudas`, versión `1.0.0+3`), `db push` de
las cuatro migraciones (lo corrió él), 714/714 en la nube y APK recompiladas
(`deudas-v2-nube-debug.apk` y `Deudas-v2.apk`, versionCode 2003). Decisiones del agente para revisar: 32 a 34
de §3.3.

**Revisión de decisiones (2026-09-25):** el dueño revisó 10 a 20 y 32 a 34 (§3.3); cambió
12 (desvincular deja todo como con una Persona, con advertencia), 14 (±2 días), 17 (varios
cambios pendientes), 32 (5 días) y 34 (30 días de gracia). Migración
`20260925100000_decisiones_dueno.sql` + test 14, Flutter (advertencia al desvincular, ±2
días, textos). **En la nube de prueba desde el 2026-09-25** (push del dueño): 748/748 allí,
`pg_cron` con la purga diaria, `probar_grupos`, `probar_rpc_v2` y `probar_fase7` OK. APK
`1.0.0+4` compilada. Sin commit.

**Fases 8 y 9**, pedidas por el dueño el 2026-09-24 (§4.7, §4.8, §5.4). Orden recomendado:
- La fase 2.5 y el corte (fase 3) **no dependen** de 8 ni de 9: son de un solo usuario.
- **La fase 8 va antes de probar en dos celulares las fases 4 a 7.** Cambia la bandeja por
  la aceptación automática: probar hoy los pasos 4 a 10 del bloque B de §0.4 sería probar
  un flujo que se va a reemplazar.
- La fase 9 va después de la 8 (usa sus `avisos`).
- **Todo el código nuevo de Flutter tiene que quedar listo para una futura PWA** (§6.5,
  "Listo para web"). La PWA en sí está aplazada.

**Commits (2026-09-24, pedidos por el dueño, sin push):**

| Repo | Rama | Qué hay |
|---|---|---|
| `ContabilidadPersonal` (este) | `feat/deudas-v2` (sale de `refactor/filtros-transacciones` en `85efa91`) | solo lo de v2: `deudas/PLAN_MULTIUSUARIO.md`, `deudas/v2/` (menos `.env` y `supabase/.temp`, ignorados), `scripts/v2/`, `contabilidad/debts/cliente.py`, `reading.py`, `escritura.py` y `tests/test_deudas_rechazadas.py`. Se armó sin cambiar de rama: el dueño sigue en `refactor/filtros-transacciones` con sus cambios sin commitear, y los archivos de v2 siguen en su copia de trabajo (sin seguimiento en esa rama) |
| `deudas/flutter_app` → `Sebas04A/app_deudas` | `v2` (salió de `main`) | las fases 2 a 8, commiteadas en la rama `v2` |
| `deudas/visor_web` → `Sebas04A/visor_deudas` (**público**) | `v2` | sin cambios nuevos: commiteado y subido (`640fc45`, 2026-09-23) |

Para seguir trabajando en v2 en este repo **no** se cambia de rama: ver §0.4, bloque E
(`scripts/v2/rama_v2.sh`). Mensajes de commit en español, con `Co-Authored-By` (§0.1).

### 0.4 Guía para el dueño: lo que te toca (escrita el 2026-09-24)

Todo lo que se podía hacer sin ti está hecho y en la nube de **prueba**. Tu app diaria
(v1) no se tocó y sigue funcionando igual. Lo que falta necesita tus decisiones, un
teléfono o tus cuentas. Va en orden: cada bloque desbloquea el siguiente. Si trabajas con
un agente, pásale esta sección y la fase de que se trate.

#### A. Decidir (sin teléfono, ~30 min)

Anota cada respuesta en §9 (o dísela al agente, que la anota). Nada de esto frena la
prueba en el teléfono (B), pero sí el corte y la publicación.

1. ✅ **Revisadas el 2026-09-25** (cambió 12, 14 y 17). **Decisiones 10 a 20 de §3.3**, que tomaron los agentes. Para cada una: "de acuerdo" o
   qué cambiar. Las que más conviene mirar:
   - 10: el título de una deuda viaja en la propuesta (el otro ve "Cena", no solo "$20").
   - 11 y 12: al desvincular, lo pendiente vuelve a ser solo de quien lo anotó y lo
     acordado queda como está, editable libremente.
   - 18: lo anotado entre las dos confirmaciones de la conciliación se propone al activar.
   - 19: al volver a vincularse con alguien, todo lo acordado antes se vuelve a conciliar.
   - 20: límites de uso (20 invitaciones/día, 10 códigos inválidos/hora, 60 consultas por
     minuto al visor por IP).
2. **Política de privacidad** (`deudas/v2/POLITICA_PRIVACIDAD.md`): ✅ Completada por el dueño el 2026-09-24. Pendiente revisión legal antes de publicar en producción (fase 7.2).
3. **Nombre y dominio públicos** de la app (§9): El dueño definió usar `visor-deudas.vercel.app` por el momento.
4. ~~Decisiones 21 a 31 (fases 8 y 9)~~: **revisadas el 2026-09-24** (§3.3). ✅ **32 a 34
   revisadas el 2026-09-25**; quedan 35 a 37, menores, del agente. Antes: **32
   a 34** (las tomó el agente al implementar la fase 9): enlace de grupo para varias
   personas, quién edita un gasto del grupo y borrar los grupos sin nadie con app.
5. Opcionales: ¿revisión diaria automática de los vínculos (6.7, `verificar_vinculos.py`)
   por GitHub Actions o `pg_cron`? ¿Login con Google (2.1, necesita que crees el cliente
   OAuth en Google Cloud Console)?

#### B. Probar la app v2 en un teléfono (fase 2.5; es lo que desbloquea el corte)

**Qué necesitas:**
- **Un teléfono Android que NO sea el tuyo de todos los días.** La v1 y la v2 tienen el
  mismo `applicationId`: instalar la v2 en tu teléfono **borraría tu app diaria**. En esta
  máquina no hay emulador instalado; un agente puede prepararlo (paquetes `emulator` y
  una imagen de sistema con el `sdkmanager` del distrobox `flutter-dev`), pero un
  teléfono viejo es más fácil.
- La APK: `deudas/flutter_app/build/app/outputs/flutter-apk/deudas-v2-nube-debug.apk`
  (219 MB, compilada el 2026-09-24 con las fases 2 a 8, que necesitan la migración de la fase 8 en la nube; `build/` no se
  versiona, solo existe en esta máquina). Si se pierde, §6.5 dice cómo recompilarla.
- Instalar: depuración USB activada en el teléfono, conectarlo y
  `~/dev/tools/scrcpy/scrcpy-linux-x86_64-v3.3.4/adb install -r <ruta de la APK>`
  (o copiar la APK al teléfono y abrirla).
- **Cuentas de prueba.** Dos formas de entrar:
  - Enlace mágico con un correo real: el correo integrado de Supabase manda muy pocos
    correos por hora en el plan gratuito; si no llega, espera o usa la otra forma.
  - Con contraseña ("Entrar con contraseña" en el login): la cuenta la crea un agente con
    `contabilidad/backend/.venv/bin/python scripts/v2/crear_usuario.py --destino nube
    --email <correo> --clave <clave> --nombre <nombre>` (queda confirmada). Para las
    pruebas de dos personas hacen falta **dos cuentas**.
- La nube de prueba está **vacía** (solo el usuario técnico `pruebas@deudas.local`): lo
  que crees ahí es de prueba y se puede borrar.

**Qué probar:** la lista de 2.5 (13 pasos, en la fase 2). Para el paso 11 (visor): el
enlace que comparte la app apunta a `visor-deudas.vercel.app`, que hasta el corte sigue
leyendo la base **v1** y no encontrará un contacto de v2 ("enlace inválido"). Copia solo
el `?token=…` del enlace y ábrelo sobre la preview de la rama `v2` del visor (URL en 2.3;
tiene la protección de Vercel: ábrela con tu sesión de Vercel o desactívala en Settings →
Deployment Protection). Anota ✅ o ❌ con lo que viste
en la tabla de 2.5. Un ❌ no es grave: díselo a un agente con lo que pasó.

> ⚠️ **Esta lista es la de la fase 8** (lo nuevo entra solo; 8.7). La nube de prueba y la
> APK ya la tienen (2026-09-24).

**Además, si tienes dos teléfonos o dos personas** (fases 4 a 8; si solo hay un teléfono,
casi todo se puede hacer cerrando sesión y entrando con la otra cuenta):
1. Cuenta A: crea un contacto "B", ícono de invitar en su detalle → comparte el código.
2. Cuenta B: menú ⋮ → "Aceptar invitación" → escribe el código → "contacto nuevo".
3. Conciliación: a B le aparece sola al aceptar el código; A la abre desde el detalle de
   B (ícono "Vinculado" → "Comparar cuentas"). Los dos tocan "Listo".
4. A anota una deuda con B → **sin que B haga nada**, en B aparece en el detalle de A con
   la marca NUEVA y el 🤝, y el ícono de campana del inicio muestra 1. Los dos ven el
   "saldo acordado" con el signo contrario.
5. B abre Novedades → "Rechazar" con un motivo → en A la deuda sale tachada con el motivo y
   no suma en ninguno de los dos.
6. A anota que B le pagó (A recibe la plata) → entra sola en B. B anota que le pagó a A (B
   entrega) → a A le llega "B dice que te pagó $X: ¿lo recibiste?" → "Confirmar". Otro
   pago de B → A "No lo recibí" → en B sale rechazado con el motivo.
7. **Duplicado avisado antes:** B anota "le debo $7 a A" y sincroniza; A sincroniza y
   anota "B me debe $7" → la app pregunta "¿Es lo mismo?" → "Sí, es esa" → no se guarda
   otra.
8. **Duplicado que se cuela:** con A en modo avión, A anota "B me debe $9"; B anota lo
   mismo. A vuelve a tener red y sincroniza → en B el aviso dice "¿Duplicada?" → "Es la
   misma" → deja de contar dos veces en los dos.
9. A cambia el monto de algo acordado → se propone → B lo ve en Novedades ("quiere
   cambiar…") → Aceptar → cambia en los dos y a A le llega "aceptó tu cambio".
10. A propone borrar algo acordado → B lo rechaza → sigue igual en los dos.
11. Sin conexión (modo avión) B rechaza algo que entró solo o confirma un pago → al volver
    la red y sincronizar, llega.
12. En el historial, un pago que anotó el otro tiene el botón ⛔ (rechazar).
13. Menú ⋮ → "Exportar mis datos" → se puede guardar o mandar el JSON (trae los avisos).
14. Con una tercera cuenta de prueba: menú ⋮ → "Borrar mi cuenta" → escribir BORRAR →
    vuelve al login y esa cuenta ya no puede entrar. (No lo hagas con A ni B si quieres
    seguir probando con ellas.)

Anota el resultado en las notas de la fase 8 (y 7 para los pasos 13-14).

#### C. El corte (fase 3): tu app diaria pasa a v2

Solo después de B sin fallos graves. **Tú eliges el momento** (sin pagos a medio
registrar). Lo hace un agente contigo siguiendo la fase 3; lo que te toca a ti:
1. En la app vieja: sincronizar, comprobar en "Estado de sincronización" que no queda
   nada pendiente y **dejar de usarla** hasta terminar.
2. Dar tu correo real y elegir una contraseña para tu cuenta v2 (el backend de
   contabilidad la necesita; en la app puedes entrar con enlace mágico igual).
3. Aprobar cada paso que publica algo: el push del visor a `main` (repo **público**), la
   APK release en tu teléfono, y después (3.8) cerrar la escritura de la base vieja y
   (3.9, una o dos semanas después) pausarla.
4. Usar v2 una semana (criterio de salida de la fase 3).

#### D. Publicar para otros (fase 7, cuando quieras)

Solo tú puedes: crear el proyecto de Firebase para las notificaciones (7.1), decidir el
plan de Supabase (7.4; el gratuito se queda corto de Disk IO, Pro ~$25/mes), abrir la
cuenta de Play Console (pago único de $25), crear la clave de firma propia (hoy el release
se firma con la clave de debug de esta máquina) y publicar la política de privacidad.

#### E. Estado de git (nada se subió)

| Repo | Rama | Commit | Cómo subirlo, si quieres |
|---|---|---|---|
| `ContabilidadPersonal` | `feat/deudas-v2` | ver `git log feat/deudas-v2` | `git push -u origin feat/deudas-v2` |
| `app_deudas` (`deudas/flutter_app`) | `v2` | ver `git -C deudas/flutter_app log v2` (fase 8 sobre el QR `2cba7d5`) | `git -C deudas/flutter_app push -u origin v2` |
| `visor_deudas` (`deudas/visor_web`) | `v2` | `640fc45` (ya subido) | — |

⚠️ **Sobre `feat/deudas-v2` en este repo** (léelo antes de cambiar de rama):
- Sigues en `refactor/filtros-transacciones` con tus cambios sin commitear. Los archivos de
  v2 están **también** en tu copia de trabajo, sin seguimiento en tu rama (son idénticos a
  los de `feat/deudas-v2`). Por eso **`git switch feat/deudas-v2` falla** ("los archivos
  sin seguimiento serían sobrescritos"). No es un problema: se puede seguir trabajando
  así.
- **Para commitear más trabajo de v2** sin cambiar de rama:
  `scripts/v2/rama_v2.sh estado` (qué cambió respecto de la rama) y
  `scripts/v2/rama_v2.sh commitear <archivo con el mensaje>`. No toca tu rama, tu índice
  ni tu copia de trabajo.
- **Para juntar las dos ramas** cuando termines `refactor/filtros-transacciones` (o
  pídeselo a un agente):
  1. Commitea tus cambios **sin** incluir `contabilidad/debts/reading.py` ni
     `escritura.py` (esos cambios son de v2 y ya están en `feat/deudas-v2`).
  2. `scripts/v2/rama_v2.sh estado` → no debe listar diferencias (si las hay,
     `commitear` primero).
  3. Quita las copias de v2 de tu copia de trabajo, que la rama ya tiene:
     `git restore contabilidad/debts/reading.py contabilidad/debts/escritura.py` y
     `git clean -n -- deudas/PLAN_MULTIUSUARIO.md deudas/v2 scripts/v2 contabilidad/debts/cliente.py tests/test_deudas_rechazadas.py`
     (mira la lista: también sale `deudas/v2/supabase/snippets/`, una carpeta vacía que
     crea el CLI; se puede borrar) y lo mismo con `-f`. `git clean` sin `-x` **no** toca lo ignorado:
     `deudas/v2/.env`, `deudas/v2/supabase/.temp` y `backups/` se quedan.
  4. `git merge feat/deudas-v2`. Los archivos vuelven, ahora con seguimiento.

#### F. Para el agente que siga

- Lee §0.1 (reglas), §0.3, esta sección y la fase que toque. El trabajo pendiente de
  agente está en las secciones "Lo que falta" de las fases 2 y 6 y en las casillas sin
  marcar de la fase 7; casi todo espera al dueño (bloques A a D).
- Antes de tocar la base: `supabase start` (§6.3; si dice "already running" con el
  contenedor de la base parado, `supabase stop` y `start`), `supabase test db`
  → **750/750** en local y en la nube (desde `20260925110000_aviso_mismo_cambio.sql`, subida el 2026-09-25)
  (la nube todavía no la tiene). Apágalo al terminar (escucha en `0.0.0.0` con keys de demostración).
- La base local tiene los datos reales importados (usuario `dueno@deudas.local`) para las
  comparaciones de regresión; si se hace `db reset`, rehacerlos (`deudas/v2/README.md`).
- Batería completa tras cualquier cambio de SQL o edges (en local y, con OK del dueño, en
  la nube): `supabase test db`, `comparar_linea_base.py` (22/22),
  `comparar_edges.py` (55/55), `probar_rpc_v2.py`, `probar_concurrencia_propuestas.py`,
  `probar_fase7.py`, `probar_grupos.py`. Comandos en `deudas/v2/README.md`. Entre dos
  corridas de `comparar_edges.py` espera un minuto: el límite del visor (60/min por IP) la
  hace fallar con un traceback.
- Commits de este repo: con `scripts/v2/rama_v2.sh` (E). Nunca en la rama del dueño.

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
| **Backend de contabilidad** (FastAPI, uso personal) | `contabilidad/debts/reading.py` (lectura) y `contabilidad/debts/escritura.py` (escritura), usados por `contabilidad/backend/routes/supabase_debts.py` y `routes/efectivo.py` | En v1, anon key constante. **Desde la fase 2.4** (en `feat/deudas-v2`) ambos usan `contabilidad/debts/cliente.py`: v1 por defecto, v2 con `DEUDAS_SUPABASE_URL`/`_KEY`/`DEUDAS_EMAIL`/`DEUDAS_PASSWORD` |
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

**Decisiones del 2026-09-24 (fases 8 y 9). Cambian las filas "Propiedad", "Persona →
Usuario" y "Aceptar" de arriba en lo que digan:**

| Tema | Decisión |
|---|---|
| **Aceptación automática** (fase 8, §4.7) | Con el vínculo activo, lo que anota uno **aparece y cuenta de una vez** en la libreta del otro, que recibe un **aviso** de que llegó algo nuevo. Solo deja de contar si lo **rechaza**. La bandeja se va porque ahí las cosas pasaban desapercibidas. En palabras del dueño: "que siempre estén ahí y que cuenten al total siempre, a menos que se rechace, y que se alerte que llegaron nuevas deudas". |
| **Pagos** (fases 8 y 9) | Si anota el pago **quien recibe la plata**, cuenta de una vez. Si lo anota **quien la entrega**, el que la recibe tiene que **confirmarlo**. Si no, cualquiera se marcaría "pagado" solo. |
| **Grupos** (fase 9, §4.8) | Grupos **compartidos** (viajes, almuerzos…). Las mismas personas pueden estar en varios grupos. Los gastos del grupo se dividen solos y **quedan en el grupo**: **no** hace falta vincular a los miembros entre sí ni pasar las deudas a las libretas. |
| **Rechazo en grupo** | Si alguien rechaza su parte de un gasto, queda **rechazada solo para esa persona**. El gasto se **reparte de nuevo** entre los demás y queda **en revisión** para ellos (cuenta con los montos nuevos y les llega un aviso). |
| **Gasto suelto** (fase 9) | Sin crear un grupo, anotar una deuda **dividida entre varios contactos**, con opción de incluirme a mí, y que se reparta sola. |
| **Guardar el gasto** | El gasto se guarda como un registro propio (no solo N deudas sueltas): permite editar el total y repartir de nuevo, rechazar por partes, mostrar "Cena $90 entre 3" y saber cuál fue mi parte. |
| **PWA** | Aplazada. **Todo el código nuevo tiene que quedar fácil de pasar a web** (§6.5, "Listo para web"). |

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
12. **Al desvincular, todo queda como con una Persona sin app** *(cambiada por el dueño el
    2026-09-25; antes: "roto el vínculo, la guardia se apaga" y lo acordado seguía
    `acordada`)*. En las dos libretas lo acordado vuelve a `local`, se olvida quién anotó
    cada fila (`origen_id`) y se borran los acuerdos; cada uno edita o borra libremente. El
    saldo no cambia: lo rechazado sigue rechazado. La app lo advierte antes de desvincular
    (segunda confirmación).
13. **Al aceptar, un candidato puede ser una propuesta MÍA** (los dos anotaron lo mismo a
    la vez y cada uno se lo mandó al otro). Enlazarlas deja las dos acordadas y resuelve
    también la mía.
14. **Enlazar exige mismo monto y dirección invertida, y fecha a ±2 días** *(el dueño,
    2026-09-25; antes ±3)*, y siempre lo confirma el usuario ("¿Es la misma?"). Vale para
    todos los emparejamientos: conciliación, candidatos al aceptar, aviso previo de
    duplicados (también en Dart) y `fusionar_espejo`.
15. **Un pago espejo se reparte con `registrar_pago`** (automático: cruce y FIFO), como
    cualquier pago de la libreta de quien acepta.
16. **Cambiar lo acordado ajusta el reparto de cada libreta:** si cambia la dirección, la
    fila suelta todo lo repartido; si el monto baja por debajo de lo ya pagado, suelta el
    exceso (primero de los pagos reales más recientes; si no alcanza, sale de sus
    cruces). Lo soltado queda como saldo a favor, que `estado_cuenta` abona solo.
17. **Pueden convivir varios cambios pendientes sobre un acuerdo** *(el dueño, 2026-09-25;
    antes uno solo, `23505`)*. Si dos dicen exactamente lo mismo (monto, fecha y dirección,
    vistos desde cada libreta), venga de quien venga, queda el más nuevo y el otro se anula.
    Aceptar uno anula los demás, que se propusieron sobre cómo estaba antes.

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

**Revisión del dueño (2026-09-25):** aprobó 10, 11, 13, 15, 16, 18, 19 y 20 tal cual y cambió
12, 14 y 17 (arriba). Sobre la 16: los cambios a lo acordado ya quedan pendientes hasta que
el otro acepta (decisión 22); la 16 solo dice cómo se ajusta el reparto cuando se aceptan.
Implementado en `20260925100000_decisiones_dueno.sql` (test `14_decisiones_dueno.sql`).

Decisiones de diseño de la fase 8, **revisadas por el dueño el 2026-09-24** (21, 22 y 24
cambiaron respecto de lo que propuso el agente; no re-litigar):

21. **Posible duplicado: se avisa ANTES, a quien anota.** Al guardar una deuda o un pago
    para un contacto vinculado, la app busca si eso ya está (el otro lo anotó y su espejo
    ya está en mi libreta, o me lo propuso y espera mi respuesta): "Ana ya anotó $20 del
    12-sep. ¿Es lo mismo?". **Sí** = no se anota de nuevo (y si era una propuesta, se
    acepta). **No** = se crea normal. Si igual se crea (sin conexión, sin sync reciente),
    el aviso que le llega al otro trae los candidatos y "Es la misma" (`fusionar_espejo`).
    *(El agente había propuesto solo lo segundo.)*
22. **Cambiar o borrar algo acordado sigue siendo propuesta**, como en la fase 6
    (`proponer_cambio`, el otro acepta o rechaza). Lo que entra solo es lo **nuevo**. No
    hay `cambiar_acordada`, `deshacer_cambio` ni `cambios_acordados`. *(El agente había
    propuesto aplicarlo de una vez con "Deshacer".)*
23. **La conciliación inicial (fase 5) sigue siendo explícita:** es una sola vez y se
    revisa en pantalla con "aceptar todo". Meter todo un historial en la libreta del otro
    sin que lo vea es demasiado. *(Confirmada por el dueño.)*
24. **Tope contra abusos: 50 filas nuevas por persona y vínculo en 24 horas.** Lo que pase
    del tope nace `propuesta` y espera respuesta, como en la fase 6, en vez de fallar el
    sync. *(El agente había propuesto 100.)*

Decisiones de la fase 9 (las propuso el agente el 2026-09-24; **el dueño las aprobó todas tal
cual el 2026-09-24**; no re-litigar):
25. **Centavos al dividir:** se reparte el monto truncado a centavos y los centavos que
    sobran se dan de a uno: primero a quien pagó (si participa) y después en el orden de
    la lista. $100 entre 3 → 33.34 / 33.33 / 33.33. La suma cuadra siempre.
26. **Rechazo en modo "montos" fijos:** no hay proporción para repartir de nuevo, así que
    la parte rechazada la absorbe quien pagó y el gasto queda en revisión para quien lo
    anotó, que lo corrige.
27. **Si rechaza quien pagó**, el gasto entero queda `rechazado` para todos (no hay a quién
    deberle). Lo mismo si después de los rechazos solo queda quien pagó.
28. **Un pago del grupo por confirmar no cuenta** hasta que se confirma. Se muestra como
    "por confirmar".
29. **Dentro de un grupo no hay FIFO ni cruces por deuda:** el saldo es el neto de cada par
    (gastos menos pagos). "Simplificar deudas" (menos pagos entre todos) queda para la
    etapa 9C.
30. **Solo se sale de un grupo con saldo 0** en él. Un grupo se archiva, no se borra, si
    tiene gastos.
31. **Gasto suelto que pagó un contacto:** en mi libreta queda solo "le debo mi parte a
    quien pagó". Las partes de los demás se guardan en el gasto como información, pero no
    son deudas mías.

Decisiones que tomó el agente al implementar la fase 9 (2026-09-24; **el dueño las
revisa**, igual que las 10 a 20):
32. **El enlace de un grupo sirve para varias personas** (se comparte en el chat del grupo)
    hasta que vence a los **5 días** *(el dueño, 2026-09-25; antes 7)* o quien lo creó
    genera otro, que anula el anterior. El de
    un contacto (fase 4) sigue siendo de un solo uso.
33. **Quién edita qué en un grupo:** un gasto lo editan o borran quien lo anotó y quien lo
    pagó; un pago del grupo lo borra quien lo anotó. En un gasto suelto cuyas deudas ya
    están acordadas con un contacto vinculado, editarlo o borrarlo **se le propone**
    (decisión 22 manda sobre el caso 7 de 9.2, que decía "pasan a rechazada").
34. **Un grupo sin nadie con la app se borra a los 30 días** *(el dueño, 2026-09-25; antes
    en el acto)*. Cuando se borra la última cuenta con app de un grupo (las demás filas son
    personas sin app), nadie puede volver a verlo: se marca `grupos.sin_nadie_desde` y
    `_purgar_grupos_sin_nadie()` lo borra con sus gastos, pagos y lápidas pasados 30 días
    (a diario por `pg_cron`, 04:17 UTC, y en cada borrado de cuenta). Si queda una cuenta
    viva, aunque haya salido del grupo, no se toca. El dueño revisó 32 a 34 el 2026-09-25:
    33 tal cual.

Decisiones que tomó el agente al implementar la revisión del 2026-09-25 (**aprobadas por el
dueño el mismo día**; la 36, "avisando correctamente al usuario"):
35. **Al desvincular, lo rechazado sigue rechazado** (no empieza a contar), para que el
    saldo no cambie, como pidió el dueño.
36. **"Exactamente lo mismo" (17) se compara entre libretas:** si A propone $30 y B propone
    $30 desde su lado (con la dirección al revés), es el mismo cambio y queda el de B. A A
    le llega el aviso "B propone el mismo cambio que tú habías propuesto: acéptalo para que
    quede" (`datos.mismo_que_el_tuyo`, `20260925110000_aviso_mismo_cambio.sql`).
37. **En el detalle del contacto se ve un solo cambio mío por deuda** (la marca y "Retirar"),
    aunque haya varios; todos aparecen en Novedades.

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

> ⚠️ Esto describe la fase 6. La **fase 8** (implementada en local) cambia cuándo nace
> cada estado: casi todo nace `acordada` y `propuesta` queda para los pagos que anota
> quien entrega la plata, lo que pase del tope y los cambios o borrados de lo acordado.
> Ver §4.7.

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

### 4.7 Aceptación automática y avisos (fase 8; reemplaza la bandeja de la fase 6)

> **Implementado** (2026-09-24) en `20260924150000_aceptacion_automatica.sql`, con las
> decisiones 21 a 24 de §3.3 **revisadas por el dueño**. Esa migración es la referencia.

Decisión del dueño del 2026-09-24 (§3.2). La bandeja obligaba a aceptar todo y las cosas
pasaban desapercibidas. Ahora **lo nuevo que anota uno aparece y cuenta de una vez en la
libreta del otro**, que recibe un aviso y puede rechazarlo cuando quiera.

**Qué nace cómo, con el vínculo `activo`:**

| Lo que anota A | En la libreta de A | En la de B, al mismo tiempo | Aviso a B |
|---|---|---|---|
| Una deuda (en cualquier dirección) | `acordada` | espejo `acordada` (dirección invertida, `origen_id`) + fila en `acuerdos` | `deuda_nueva` |
| Un pago que **A recibió** (`es_mi_pago = false`) | `acordada` | espejo `acordada`, repartido con `registrar_pago` (decisión 15) | `pago_nuevo` |
| Un pago que **A entregó** (`es_mi_pago = true`) | `propuesta` (como en la fase 6) | nada hasta que B confirme | `pago_por_confirmar` |
| Un cruce | `local` (sin cambio) | nada | — |
| Pasado el tope: más de 50 filas de A en el vínculo en 24 horas (decisión 24) | `propuesta` | nada hasta que B acepte | `propuesta` |
| Un cambio o un borrado de algo acordado (decisión 22) | `proponer_cambio`, como en la fase 6 | nada cambia hasta que B acepte | `cambio` / `borrado` |

- Cuenta en **mi saldo** y en el **saldo acordado** de los dos desde el primer momento. La
  invariante (acordado de A = −acordado de B) se cumple porque las dos filas nacen en la
  misma transacción.
- **Mecánica:** `_nace_propuesta_post` sigue creando la propuesta (historial e
  idempotencia: el reintento del sync es un UPDATE, no crea otro espejo) y llama a
  `_llegada`. Si entra sola, `_llegada` **actúa como B**: pone su id en
  `request.jwt.claim.sub` (`_suplantar`, lo primero que mira `auth.uid()`), busca
  candidatos a duplicado en la libreta de B y llama a `aceptar_propuesta(…, p_crear_nueva
  => true)`, que ya crea el espejo, reparte un pago y ata el acuerdo. Cero lógica nueva de
  saldos. La variable `deudas.sin_aviso` apaga el aviso de "confirmado" de esa aceptación.
- **Rechazar** (`rechazar_fila(p_entidad, p_fila, p_motivo, p_idem_key)`): solo sobre
  filas **que anotó el otro** (`origen_id` no nulo; lo mío se cambia o se borra
  proponiéndolo, decisión 22), en cualquier momento mientras haya vínculo. Las dos filas
  pasan a `rechazada` aplicando §4.2 en las dos libretas; el acuerdo se borra; la propuesta
  de 'crear' de la otra fila pasa de `aceptada` a `rechazada` con el motivo (de ahí lo lee
  la app de siempre) y el trigger de avisos le manda `rechazo`.
- **Posibles duplicados (decisión 21):** primero se avisa **a quien anota, antes de
  guardar**: la app (`lib/dominio/duplicados.dart`, sin conexión) busca en sus espejos y en
  las propuestas que le llegaron algo con la misma dirección, el mismo monto y la fecha a
  ±3 días y pregunta "¿Es lo mismo?". Sí = no guarda nada (o acepta la propuesta). Si igual
  se duplica (sin sync reciente), el aviso de B trae los candidatos
  (`_candidatos_duplicado`, que también mira lo `acordada`) y B elige "Es la misma"
  (`fusionar_espejo(p_entidad, p_espejo, p_existente)`):
  - si la de B ya estaba acordada, el par nuevo sobra: sus dos filas pasan a `rechazada`
    ("Ya estaba anotada") y A recibe el `rechazo`;
  - si la de B era `local` o `propuesta`, ocupa el lugar del espejo en `acuerdos` y el
    espejo se borra soltando su reparto (§4.2). La propuesta de B, si la había, queda
    aceptada.
- **Pagos por confirmar y lo que pasa el tope:** `aceptar_propuesta` /
  `rechazar_propuesta`, como en la fase 6. En la app son "Confirmar" / "No lo recibí".
- **Conciliación (fase 5):** sin cambios (decisión 23). Sus propuestas no generan un aviso
  por fila; un rechazo sí.
- **Desvincular:** los pagos por confirmar se anulan (decisión 11) y sus avisos sin ver se
  borran; lo acordado queda; al otro le llega `desvinculado`.
- **Freno de emergencia:** `deudas.tope_diario` cambia el tope; en 0 todo vuelve a nacer
  propuesta (`ALTER DATABASE postgres SET deudas.tope_diario = 0`, sin migrar nada). Los
  tests de la fase 6 lo usan para seguir probando el camino de la propuesta.
- **Candados:** `registrar_pago` toma los dos candados del vínculo (`_candado_vinculo`)
  antes que el suyo. Sin eso, dos personas que registran a la vez un pago recibido se
  trababan (el espejo toma el candado del otro): 40P01 que PostgREST reintenta en silencio
  (§10).

**Avisos.** La tabla `avisos` (§5.4) guarda, por usuario, lo que llegó: `deuda_nueva`,
`pago_nuevo`, `pago_por_confirmar`, `propuesta`, `cambio`, `borrado`, `confirmado`,
`rechazo`, `desvinculado`, y en la fase 9 `gasto_nuevo`, `gasto_en_revision`,
`pago_grupo_por_confirmar`, `gasto_rechazado`. Los datos van en el punto de vista de quien
lo recibe. La escriben `_llegada`, el trigger `_aviso_propuesta` (al nacer un cambio o
borrado y al responderse o anularse una propuesta) y `_aviso_vinculo`; nunca la app.
- En la app: **Novedades** (reemplaza la bandeja) con contador en el inicio: "Por
  responder" (las propuestas) y "Novedades" (los avisos, con "Rechazar" y "Es la misma").
  Marca **NUEVA** en la fila y "incluye $X que anotó … y no habías visto" en el detalle del
  contacto, que al abrirse marca esos avisos como vistos. `marcar_vistos(p_ids uuid[])`.
- Las notificaciones push (7.1) se disparan con el `INSERT` en `avisos`, no en
  `propuestas`.

### 4.8 Gastos divididos y grupos (fase 9)

Hay dos lugares donde vive un gasto dividido:

| | **Gasto suelto** (`grupo_id` NULL) | **Gasto de grupo** |
|---|---|---|
| Participantes | contactos de **mi libreta** (+ yo) | **miembros del grupo** (usuarios o personas sin app) |
| Dónde viven las deudas | en mi libreta: una **deuda normal** por contacto, con `gasto_id` | **en el grupo**, no en las libretas (decisión del dueño) |
| Saldo | el de cada contacto (`estado_cuenta`, sin cambios) | `estado_grupo(grupo_id)`, aparte |
| Contactos vinculados | cada deuda sigue §4.7 (espejo + aviso) | no hace falta ningún vínculo |
| Quién lo ve | yo (y el espejo de cada vinculado) | todos los miembros con app |

**El gasto** (`gastos` + `gasto_participantes`, §5.4) guarda por participante lo que
**puso** (`pagado`) y lo que le **toca** (`parte`). Por ahora hay exactamente un
participante con `pagado > 0`; la tabla ya sirve para varios pagadores (9C). Invariantes,
que comprueba el RPC: Σ `pagado` = `monto_total` y Σ `parte` de las partes activas =
`monto_total`.

**Repartir.** Modos: `igual` (por defecto), `montos`, `porcentaje`, `partes` (el peso de
cada uno se guarda en `peso`). Centavos: decisión 25. La función vive **dos veces**: en SQL
(`_repartir(monto, pesos numeric[]) RETURNS numeric[]`, la que manda) y en Dart puro
(`lib/dominio/reparto.dart`, para la vista previa sin conexión), con un test de paridad
como el de `PlanPago`.

**Gasto suelto** (`crear_gasto` con `p_grupo_id => NULL`), por ejemplo $90 entre yo, Ana y
Beto:
- Pagué yo → dos deudas "me debe $30" (Ana, Beto) con `gasto_id`. Mi parte de $30 queda
  en el gasto, sin deuda (le sirve después a contabilidad: mi gasto real fue $30).
- Pagó Ana → una deuda "le debo $30 a Ana". Lo que Beto le debe a Ana queda solo como
  información en el gasto (decisión 31).
- Sin incluirme → $45 cada uno.
- Una deuda con `gasto_id` no se edita suelta: monto, fecha, dirección y borrado van por
  `editar_gasto`/`borrar_gasto`, que reparten de nuevo (con la decisión 16 si ya tenía
  pagos). El título sí se edita suelto. Lo hace cumplir un trigger, como `_guardia_acordada`.

**Grupo:**
- Lo crea un usuario. Los miembros son **usuarios**, que entran con un enlace
  `…/grupo/<código>` (tabla `grupo_invitaciones`, mismo estilo que `invitaciones`), o
  **personas sin app** (solo un nombre; las agrega cualquier miembro). Las mismas personas
  pueden estar en varios grupos, sin restricción.
- Cualquier miembro con app anota gastos y ve **todos** los gastos y saldos del grupo,
  también los de pares en los que no está.
- **Saldo de un par** (A, B) = lo que B le debe a A por gastos activos − lo que A le debe
  a B − pagos confirmados de B a A + pagos confirmados de A a B. Sin FIFO ni cruces por
  deuda (decisión 29). `estado_grupo` devuelve miembros con su neto, pares con saldo ≠ 0,
  gastos con su estado y pagos por confirmar.
- **Todo cuenta de una vez:** al anotar un gasto, cada participante con app recibe
  `gasto_nuevo`.
- **Rechazar mi parte** (`rechazar_parte(p_gasto_id, p_motivo, p_idem_key)`): mi fila de
  `gasto_participantes` pasa a `rechazada` **solo para mí**. El resto se reparte de nuevo
  con sus pesos entre las partes activas. El gasto pasa a `en_revision`: cuenta con los
  montos nuevos y cada participante con app recibe `gasto_en_revision` ("Beto rechazó su
  parte de 'Cena': <motivo>. Tu parte pasó de $30 a $45"). Vuelve a `activo` cuando todos
  lo vieron o cuando quien lo anotó lo edita. Casos de borde: decisiones 26 y 27. Una
  persona sin app no rechaza; lo que la involucra lo corrige un miembro editando el gasto.
- **Editar o borrar un gasto:** quien lo anotó o quien lo pagó. Se aplica de una vez y
  avisa a los participantes. Al editar se puede volver a incluir a alguien que había
  rechazado.
- **Pagos del grupo** (`grupo_pagos`), con la regla de §3.2: si lo anota quien recibe, o si
  quien recibe es una persona sin app, queda `confirmado`; si lo anota quien entrega,
  queda `por_confirmar` (no cuenta, decisión 28) y el que recibe tiene "Confirmar" / "No lo
  recibí". Un pago lo anota una de sus dos partes; si las dos son personas sin app,
  cualquier miembro. "Saldar" en la app propone el monto del par.
- **Salir y archivar:** decisión 30.
- **Inicio de la app:** total = saldo en contactos + saldo en grupos, mostrados por
  separado.

**Etapas:**
- **9A: gasto suelto.** Se crean ya todas las tablas del gasto.
- **9B: grupos compartidos.**
- **9C (opcional, después):** una persona sin app que se registra reclama su lugar en el
  grupo (código por miembro), simplificar deudas, varios pagadores en la pantalla, visor
  por token para las personas sin app del grupo, en el detalle de un contacto vinculado
  "además, en grupos: …", y leer mi parte de los gastos desde contabilidad
  (`reading.py`, devengo).

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

### 5.4 Avisos, gastos y grupos (fases 8 y 9 implementadas)

> La parte de la fase 8 está **implementada** en `20260924150000_aceptacion_automatica.sql`
> (la referencia). No hay `cambios_acordados`: cambiar o borrar lo acordado sigue siendo
> propuesta (decisión 22).
>
> La fase 9 está **implementada en local** en `20260924160000_gastos.sql`,
> `20260924170000_grupos.sql` y `20260924190000_grupos_sin_nadie.sql`: **la referencia son
> esas migraciones**, no el boceto de abajo. Diferencias: `creado_por` de `grupos` y
> `gastos` es `ON DELETE SET NULL` (la cuenta se puede borrar), las lápidas van en su propia
> tabla `borrados_gastos` (lo de un grupo lo bajan todos sus miembros), hay más tipos de
> aviso (`gasto_editado`, `gasto_borrado`, `pago_grupo_nuevo|confirmado|rechazado|borrado`),
> un RPC más (`borrar_pago_grupo`) y `cambios_gastos(p_desde)` para el pull incremental.

```sql
-- ── Fase 8 ──────────────────────────────────────────────────────────────
CREATE TABLE avisos (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id   uuid NOT NULL REFERENCES perfiles ON DELETE CASCADE,  -- para quién
  tipo         text NOT NULL CHECK (tipo IN ('deuda_nueva','pago_nuevo','pago_por_confirmar',
                 'propuesta','cambio','borrado','confirmado','rechazo','desvinculado',
                 'gasto_nuevo','gasto_en_revision','gasto_rechazado','pago_grupo_por_confirmar')),
  de_usuario   uuid,                 -- quién lo causó (sin FK: su cuenta se puede borrar)
  entidad      text,  fila_id uuid,  -- la fila de MI libreta, si la hay
  vinculo_id   uuid REFERENCES vinculos ON DELETE CASCADE,
  propuesta_id uuid REFERENCES propuestas ON DELETE CASCADE,
  grupo_id uuid, gasto_id uuid,      -- fase 9
  datos        jsonb NOT NULL DEFAULT '{}',  -- monto, fecha, es_mia, texto, candidatos, antes, motivo
  created_at   timestamptz NOT NULL DEFAULT now(),
  visto_at     timestamptz
);
-- RLS: SELECT propio. Nadie escribe directo: marcar_vistos() pone visto_at.

-- ── Fase 9 ──────────────────────────────────────────────────────────────
CREATE TABLE grupos (
  id         uuid PRIMARY KEY,                 -- lo genera el teléfono
  creado_por uuid NOT NULL DEFAULT auth.uid() REFERENCES perfiles,
  nombre     text NOT NULL,
  tipo       text NOT NULL DEFAULT 'otro',     -- viaje | comida | casa | otro (ícono)
  moneda     text NOT NULL DEFAULT 'USD',
  archivado  boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grupo_miembros (
  id           uuid PRIMARY KEY,
  grupo_id     uuid NOT NULL REFERENCES grupos ON DELETE CASCADE,
  usuario_id   uuid REFERENCES perfiles ON DELETE SET NULL,  -- NULL = persona sin app
  nombre       text NOT NULL,
  agregado_por uuid NOT NULL DEFAULT auth.uid(),
  salio_at     timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (grupo_id, usuario_id)
);

CREATE TABLE grupo_invitaciones (      -- como `invitaciones` (§5.2), con el límite de 7.3
  codigo     text PRIMARY KEY,
  grupo_id   uuid NOT NULL REFERENCES grupos ON DELETE CASCADE,
  creado_por uuid NOT NULL DEFAULT auth.uid(),
  miembro_id uuid REFERENCES grupo_miembros,  -- 9C: reclamar el lugar de una persona sin app
  expira     timestamptz NOT NULL DEFAULT now() + interval '7 days',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE gastos (
  id          uuid PRIMARY KEY,                -- lo genera el teléfono
  grupo_id    uuid REFERENCES grupos ON DELETE CASCADE,  -- NULL = gasto suelto
  creado_por  uuid NOT NULL DEFAULT auth.uid() REFERENCES perfiles,
  titulo      text NOT NULL,
  monto_total numeric(10,2) NOT NULL CHECK (monto_total > 0),
  fecha       date NOT NULL,
  modo        text NOT NULL DEFAULT 'igual' CHECK (modo IN ('igual','montos','porcentaje','partes')),
  estado      text NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo','en_revision','rechazado')),
  idem_key    uuid,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, creado_por), UNIQUE (creado_por, idem_key)
);

CREATE TABLE gasto_participantes (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  gasto_id   uuid NOT NULL REFERENCES gastos ON DELETE CASCADE,
  miembro_id uuid REFERENCES grupo_miembros,   -- gasto de grupo
  deudor_id  uuid,                             -- gasto suelto: contacto de la libreta de creado_por
                                               -- (miembro y deudor NULL = quien lo anotó)
  pagado     numeric(10,2) NOT NULL DEFAULT 0 CHECK (pagado >= 0),
  parte      numeric(10,2) NOT NULL DEFAULT 0 CHECK (parte >= 0),
  peso       numeric,                          -- % o partes, para repartir de nuevo
  estado     text NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa','rechazada')),
  motivo     text,
  deuda_id   uuid,                             -- gasto suelto: la deuda que generó
  UNIQUE NULLS NOT DISTINCT (gasto_id, miembro_id, deudor_id),
  CHECK (miembro_id IS NULL OR deudor_id IS NULL)
);

ALTER TABLE deudas ADD COLUMN gasto_id uuid;  -- FK a gastos (id, creado_por) con owner_id

CREATE TABLE grupo_pagos (
  id          uuid PRIMARY KEY,
  grupo_id    uuid NOT NULL REFERENCES grupos ON DELETE CASCADE,
  de_miembro  uuid NOT NULL REFERENCES grupo_miembros,   -- entrega la plata
  para_miembro uuid NOT NULL REFERENCES grupo_miembros,  -- la recibe
  monto       numeric(10,2) NOT NULL CHECK (monto > 0),
  fecha       date NOT NULL,
  nota        text,
  registrado_por uuid NOT NULL DEFAULT auth.uid(),
  estado      text NOT NULL CHECK (estado IN ('confirmado','por_confirmar','rechazado')),
  idem_key    uuid,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (registrado_por, idem_key),
  CHECK (de_miembro <> para_miembro)
);
```

- **RLS:** lo del grupo (`grupos`, `grupo_miembros`, `gastos` con `grupo_id`, sus
  participantes, `grupo_pagos`) se puede leer si soy miembro activo (`_soy_miembro(grupo_id)`,
  `STABLE SECURITY DEFINER`). Un gasto suelto y sus participantes, solo quien lo anotó.
  **Nadie escribe directo: todo va por RPC**, con `idem_key`.
- **Lápidas y pull incremental:** las tablas nuevas tienen `updated_at` y lápidas en
  `borrados`, como las de §5.1, para que Flutter las traiga incrementales.
- **RPC de la fase 9:** `crear_grupo`, `invitar_a_grupo`, `unirse_a_grupo(p_codigo)`,
  `agregar_persona(p_grupo_id, p_nombre)`, `salir_de_grupo`, `archivar_grupo`,
  `crear_gasto(p_id, p_grupo_id, p_titulo, p_monto, p_fecha, p_modo, p_participantes jsonb,
  p_idem_key)`, `editar_gasto`, `borrar_gasto`, `rechazar_parte`, `registrar_pago_grupo`,
  `confirmar_pago_grupo`, `rechazar_pago_grupo`, `estado_grupo(p_grupo_id) RETURNS jsonb`.
- **Nada de esto toca `estado_cuenta`.** Un gasto suelto crea deudas normales; el grupo
  tiene su propio `estado_grupo`.

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
| Migraciones aplicadas | `20260923180000_base`, `20260923190000_duenos`, `20260924100000_vinculos`, `20260924110000_conciliacion`, `20260924120000_propuestas`, `20260924130000_conciliacion_tardias`, `20260924140000_publicacion`, `20260924150000_aceptacion_automatica` (`supabase migration list --linked`) |
| Edge functions | `get_estado_cuenta`, `get_historial`, `borrar_cuenta` (`verify_jwt = true`), `visor` (`verify_jwt = false`) |
| Auth | Email habilitado (código por correo, enlace de respaldo y contraseña). `site_url` y `additional_redirect_urls` = `com.deudas.deudas_app://login-callback`. Plantillas `magic_link` y `confirmation` con el código (`supabase/templates/codigo.html`): **en config.toml; en la nube solo después de que el dueño corra `config push`** (notas de la fase 8). Google **no** configurado (§9) |
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
  La última APK v2 compilada (2026-09-24, fases 2 a 8) está copiada en
  `deudas/flutter_app/build/app/outputs/flutter-apk/deudas-v2-nube-debug.apk`.
- Instalar en el celular: con el adb del host (`~/dev/tools/scrcpy/.../adb install -r <apk>`).
  ⚠️ La v1 y la v2 tienen el mismo `applicationId`: instalar una **reemplaza** a la otra.
  Para probar v2 sin perder la app diaria, usar otro teléfono o un emulador.
- `test/widget_test.dart` falla desde siempre (plantilla con `MyApp`); correr
  `flutter test test/plan_pago_test.dart test/resumen_whatsapp_test.dart
  test/pull_incremental_test.dart test/vinculos_test.dart test/propuestas_test.dart
  test/duplicados_test.dart` (35/35 el 2026-09-24, con la fase 8).
- `flutter analyze lib` da **183 avisos, todos de estilo** con la fase 8 (eran 187 con
  el commit del QR; se fueron los de la bandeja). Antes: 171 (167 previos en `main` + 4
  `withOpacity` de la fase 6); ningún error.
- Sin entrar al distrobox (útil para agentes): `podman start flutter-dev` y
  `podman exec -u sebas -w <ruta de la app> -e HOME=$H -e PATH=$H/flutter/bin:/usr/bin:/bin
  flutter-dev bash -c 'flutter …'` con `H=~/dev/projects/distroboxes/flutter-dev`. Para
  compilar, agregar `-e ANDROID_HOME=$H/android-sdk -e JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64`.
- Emulador instalado (2026-09-24): AVD `deudas_test` (Pixel 6, Android 14) con aceleración NVIDIA en el host. Ver §8 (notas de la fase 2) y §0.4 B.
- El repo Flutter es **otro repo git** (`deudas/flutter_app/` → `Sebas04A/app_deudas`).
  Rama `v2`, commiteada con la fase 8 y **sin push** (§0.4 E). La APK v2 de
  `deudas-v2-nube-debug.apk` ya trae la fase 8: necesita la migración en la nube.

**Listo para web (regla desde el 2026-09-24).** El dueño quiere, más adelante, publicar la
app también como PWA (`flutter build web`, en Vercel como el visor) para que nadie tenga
que instalar nada. La PWA está aplazada, pero **todo código nuevo** tiene que cumplir esto
para que después sea compilar y publicar:
- **Nada de `dart:io` fuera de `lib/plataforma/`**, que usa imports condicionales
  (`if (dart.library.js_interop)`). Hoy lo usan solo `services/connectivity_service.dart`
  (`InternetAddress.lookup`) y `services/sync_report.dart`: se mueven cuando se toquen.
- **Reglas de negocio en Dart puro** (`lib/dominio/`: repartir, redondear, saldos del
  grupo), sin importar Flutter, con tests. El servidor manda; la copia de Dart es para
  trabajar sin conexión, con un test de paridad.
- **Pantallas con ruta y URL** (`/grupo/<id>`, `/grupo/unirse/<código>`,
  `/contacto/<id>`). Las invitaciones son enlaces, que en web funcionan solos.
- **Antes de agregar un paquete, confirmar en pub.dev que soporta web.** Si no hay
  alternativa, se envuelve en `lib/plataforma/` con una versión web que degrade.
- Login nuevo: preferir el **código de 6 dígitos por correo** (OTP de Supabase) al enlace
  mágico, que en un iPhone con la PWA instalada se abre en Safari, con otra sesión.
- Almacenamiento: Hive sirve en web (IndexedDB). No usar archivos ni rutas del sistema.
- Verificación barata en cada fase: `flutter build web` tiene que compilar (sin
  publicarlo).

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
        20260924150000_aceptacion_automatica.sql ← fase 8 (en la nube; copias + «v2 fase 8»)
      functions/
        _shared/estado_cuenta.ts   ← lógica de v1 SIN CAMBIOS
        _shared/historial.ts       ← lógica de v1 + ORDER BY (notas de la fase 1)
        _shared/http.ts
        get_estado_cuenta/  get_historial/  visor/  borrar_cuenta/
      tests/
        01_rls.sql  02_rpc_duenos.sql  04_vinculos.sql  05_conciliacion.sql
        06_propuestas.sql  07_conciliacion_tardias.sql  08_publicacion.sql
        09_aceptacion_automatica.sql ← pgTAP, 398
    POLITICA_PRIVACIDAD.md         ← borrador (fase 7.2), sin publicar
  flutter_app/  (repo Sebas04A/app_deudas, rama v2, commiteada sin push)
    lib/config.dart                ← Entorno.esV2 / URL / key por --dart-define
    lib/screens/login_screen.dart  ← login (magic link + contraseña)
    lib/main.dart                  ← _PuertaDeSesion (solo v2)
    lib/services/database_service.dart  ← init(usuario:) y cerrar()
    lib/screens/home_screen.dart   ← "Cerrar sesión" (solo v2)
    lib/services/sync_report.dart  ← mensaje de 42501
    lib/services/cuenta_service.dart ← exportar mis datos / borrar mi cuenta (fase 7)
    lib/services/avisos_service.dart ← avisos, rechazar_fila, fusionar_espejo, su cola (fase 8)
    lib/screens/novedades_screen.dart ← Novedades: reemplaza la bandeja (fase 8)
    lib/dominio/duplicados.dart    ← aviso previo "¿es lo mismo?", Dart puro (fase 8)
    lib/widgets/aviso_duplicado.dart, rechazar_fila.dart ← (fase 8)
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
- [~] **2.2 Flutter** (repo `app_deudas`, rama `v2`; commiteado el 2026-09-24):
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

      Cómo instalar, qué cuentas usar y qué hacer si falla: §0.4 B.

      | Paso | Resultado (✅/❌ y qué se vio) | Fecha |
      |---|---|---|
      | 1 | ✅ Login con contraseña (`alice@deudas.local`, `bob@deudas.local`) en emulador | 2026-09-24 |
      | 2 | ✅ Crear deudores ("Bob", "Juan Prueba") en libreta local y sincronizados con nube v2 | 2026-09-24 |
      | 3 | ✅ Crear deudas en ambos sentidos ($10 a favor, $5 en contra). Flujo rápido si no hay deudores | 2026-09-24 |
      | 4 | ✅ Pago automático probado en suite de tests (`plan_pago_test.dart`); el dueño también probó 4 a 8 en la app (2026-09-25) y quiere repetir toda la lista cuando la app esté completa | 2026-09-24 |
      | 5 | ✅ Pago manual probado en suite de tests | 2026-09-24 |
      | 6 | ✅ Cruce probado en suite de tests | 2026-09-24 |
      | 7 | ✅ Editar cruce probado en suite de tests | 2026-09-24 |
      | 8 | ✅ Editar pago probado en suite de tests | 2026-09-24 |
      | 9 | ✅ Borrar deuda probado en suite y UI | 2026-09-24 |
      | 10 | ✅ Modo avión: el dueño lo probó y sincroniza bien | 2026-09-25 |
      | 11 | ⏳ Visor: la preview v2 decía "Enlace expirado" porque el emulador tenía la APK de la **base local** (`deudas-v2-local-fase9-debug.apk`, instalada el 24 a las 23:08): sus contactos no existen en la nube. La edge `visor` de la nube responde bien a tokens v2 (probado). El 2026-09-25 se instaló la APK contra la nube: repetir con un contacto creado en ella. (Cualquier fallo del visor, no solo un token vencido, muestra "Enlace expirado".) | 2026-09-25 |
      | 12 | ✅ Dos cuentas vinculadas ven sus respectivos lados con signos invertidos y sincronizados | 2026-09-24 |
      | 13 | ✅ Cuentas separadas no ven datos ajenos (RLS v2 garantizado) | 2026-09-24 |

      **Mejoras de UX y Vinculación agregadas el 2026-09-24:**
      - **Crear deudor rápido:** Al crear una deuda si no hay deudores, ofrece crear uno inmediatamente sin volver atrás.
      - **Invertir sentido en edición:** Botón para invertir entre "debo" y "me debe" directamente al editar una deuda.
      - **Propuestas en detalle de deudor:** Se renderizan propuestas entrantes (con Aceptar/Rechazar) y salientes (con opción de retirar) directamente en `deudor_detail_screen.dart`.
      - **Badges de propuestas:** Chips `PENDIENTE`, `CAMBIO PENDIENTE`, `BORRADO PENDIENTE` en cada deuda usando `Wrap` (sin pixel overflow).
      - **Vincular por código QR:** Modal con visualización de código QR e invitación instantánea (`invitacion_qr_modal.dart`).
      - **Escanear QR con cámara:** Integración de `mobile_scanner` con permisos Android en `escaner_qr_modal.dart` y botón en `aceptar_invitacion_screen.dart`.
      - **Configuración de visor:** `Entorno.visorUrl` apunta a la preview v2 en desarrollo para evitar choques con el visor en producción.

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

- **Emulador Android y cuentas de prueba (2026-09-24):**
  - Paquetes `emulator` y `system-images;android-34;google_apis;x86_64` instalados en el SDK (`distrobox flutter-dev`). AVD `deudas_test` (Pixel 6, Android 14) creado en `$HOME/.config/.android/avd/deudas_test.avd` (symlinkeado a `$HOME/.android/avd`).
  - Para correr con aceleración de GPU nativa (NVIDIA RTX 4060):
    ```bash
    export ANDROID_HOME=/home/sebas/dev/projects/distroboxes/flutter-dev/android-sdk
    export ANDROID_AVD_HOME=/home/sebas/dev/projects/distroboxes/flutter-dev/.config/.android/avd
    export QT_QPA_PLATFORM=xcb
    $ANDROID_HOME/emulator/emulator -avd deudas_test -crash-report-mode disabled
    ```
  - APK `deudas-v2-nube-debug.apk` instalada en el emulador (`adb install -r ...`). La app inicia en pantalla de login.
  - Cuentas creadas en la nube v2 (`ggzvxehcsorlbroucbkp`):
    - `alice@deudas.local` / `deudas1234` (UUID: `643e98f4-179c-4431-8c4d-78cda43f770b`, perfil Alice).
    - `bob@deudas.local` / `deudas1234` (UUID: `15764ec4-093b-474e-a974-11ddb9a43892`, perfil Bob).
  - Dominio público acordado para invitaciones: `visor-deudas.vercel.app`.
  - `deudas/v2/POLITICA_PRIVACIDAD.md` completado y limpio (Sebastián Arcentales, Quito, Ecuador; correo de contacto, 7 días retención).

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

- [x] **3.1 Congelar v1.**
      - El dueño abre la app vieja, sincroniza, comprueba en "Estado de sincronización"
        que no queda nada pendiente y **deja de usarla**.
      - El backend de contabilidad se apaga al final de 3.2, para que nadie escriba en v1
        durante el corte.
- [x] **3.2 Respaldo y línea base finales** (solo leen producción):
      ```bash
      $PY scripts/v2/backup_completo.py              # → backups/deudas_v2_origen_<fecha>/
      $PY scripts/v2/capturar_linea_base.py          # → backups/estado_cuenta_baseline_v2_<fecha>/
      # con el backend de contabilidad TODAVÍA levantado y en v1 (el script llama a su API):
      $PY scripts/snapshot_dashboard.py capturar --nombre pre_corte_v2
      ```
      Después apagar el backend.
- [x] **3.3 Cuenta real del dueño en v2.** Con su email real y una contraseña que el dueño
      elija (el backend la necesita; en la app puede entrar con magic link igual):
      ```bash
      OWNER=$($PY scripts/v2/crear_usuario.py --destino nube --email <email del dueño> \
                --clave '<contraseña>' --nombre Sebas)
      ```
      Anotar el UUID en las notas de esta fase.
- [x] **3.4 Importar.**
      ```bash
      $PY scripts/v2/importar.py --origen backups/deudas_v2_origen_<fecha> --destino nube --owner $OWNER
      ```
      Imprime ✓ por tabla si los conteos coinciden con el respaldo. El usuario
      `pruebas@deudas.local` no tiene datos y puede quedarse, porque `probar_rpc_v2.py` lo
      usa.
- [x] **3.5 Verificar** (todo tiene que dar 0 diferencias):
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
- [x] **3.6 Cambiar los clientes.**
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
- [x] **3.7 Comprobar el visor publicado** con 2 o 3 tokens reales: el monto y los
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

**Notas de ejecución (2026-09-25, pedido por el dueño: "Migra mis datos")**

- 3.1: el dueño confirmó la app vieja sincronizada y sin usar.
- 3.2: `backups/deudas_v2_origen_20260925_130342` (11 deudores, 335 deudas, 41 pagos, 271
  detalles, 4 + 3 bitácoras), `backups/estado_cuenta_baseline_v2_20260925_130345` (22) y
  `backups/dashboard_snapshots/pre_corte_v2.json`.
- 3.3: cuenta `andresebasarcentalesarciniega@gmail.com`, UUID
  `6c8072b7-680a-46ad-809d-1eab82d4d856`. Contraseña aleatoria generada por el agente, solo
  en `contabilidad/backend/.env` (modo 600, ignorado por git); en la app se entra con código.
- 3.4: importado. El chequeo de `importar.py` contaba la tabla entera y en la nube hay otras
  cuentas (pruebas y la mamá): daba ✗ con los datos bien. Ahora cuenta solo las filas del
  `--owner`; la segunda corrida (idempotente) dio ✓ en las 6 tablas.
- 3.5: `comparar_linea_base` 22/22 sin diferencias; `comparar_edges` igual que producción.
  De `etiquetas.csv`: 129 `deuda_id` y 5 `pago_id`; falta uno,
  `c081007b-7897-4865-9f03-d0a2aeec3984` ("Uber cromos", Ñaña, 2 filas), que **tampoco
  existe en v1**: referencia rota de antes del corte, no de la migración.
- 3.6: backend con `.env` → "Deudas: sesión iniciada como …" y
  `snapshot_dashboard comparar` **IDÉNTICO**. `app_deudas`: `config.dart` con v2 por
  defecto (`5ca26a1`, versión `1.0.0+5`), `main` adelantado a `v2` y los dos subidos. La
  release sin defines se probó en el emulador (abre v2 y sincroniza):
  `build/app/outputs/flutter-apk/Deudas-v2.apk` (arm64, versionCode 2005, clave de debug de
  esta máquina: se instala encima de la v1 del dueño y de la de la mamá). Visor: `v2`
  (`640fc45`) publicado en `main`; `visor-deudas.vercel.app` ya sirve la versión v2.
- 3.7: la página publicada apunta a v2 y 3 tokens reales responden en la nube (la
  igualdad con producción la probó `comparar_edges`).
- **Falta:** que el dueño instale la APK en su teléfono (si el correo trae un enlace y no
  el código, correr `config push`: §6.4), 3.8 (con su OK), 3.9 y 3.10 (`deudas/README.md`
  está fuera de las rutas de v2: se actualiza en la rama del dueño).

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

- [x] **6.1** (`20260924120000_propuestas.sql`; en la nube de prueba desde el 2026-09-24) Migración `<ts>_propuestas.sql`:
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
- [x] **6.5** (rama `v2` de `app_deudas`, commiteada; falta probarlo en celulares: §0.4 B) Flutter:
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
    compila (`deudas-v2-nube-debug.apk`). *(2026-09-24: la migración ya está en la nube y la
    APK se recompiló; se puede instalar.)*
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

**Prerrequisitos.** Fase 3 ✅ para publicar "cada uno su libreta". Fases 6 y 8 ✅ para
publicar con vínculos. Fase 9 ✅ para publicar con grupos.

- [ ] **7.1** Notificaciones push (Firebase Cloud Messaging):
      - tabla `dispositivos (owner_id, token_fcm)`;
      - edge function disparada por un *database webhook* en `INSERT` de `avisos`
        (fase 8, §4.7). Antes de la fase 8 el diseño decía `propuestas`.
      - Firebase Cloud Messaging también manda notificaciones a la web: sirve para la
        futura PWA.
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

### Fase 8 — Aceptación automática y avisos

**Objetivo.** Con un vínculo activo, lo que anota uno aparece y cuenta de una vez en la
libreta del otro, que recibe un aviso y puede rechazarlo. Reemplaza la bandeja de la
fase 6.

**Prerrequisitos.** Fase 6 hecha en la nube de prueba (lo está). Que el dueño haya
revisado las decisiones 21 a 24 de §3.3 (**hecho el 2026-09-24**: cambió 21, 22 y 24).
**No** depende de la fase 3.

**Contexto.** §3.2 (decisiones del 2026-09-24), §4.7, §5.4 (fase 8) y las notas de la
fase 6 (qué hace cada función auxiliar). Es tan delicada como la 6: escribe en la libreta
del otro dentro del `INSERT` de uno.

**Pasos**

- [x] **8.1** (2026-09-24; en la nube de prueba desde ese día, push del dueño) Migración `20260924150000_aceptacion_automatica.sql`:
      - tabla `avisos` con su RLS (sin `cambios_acordados`: decisión 22);
      - `_nace_propuesta_post` llama a `_llegada`: entran solos las deudas y los pagos que
        anota quien recibe; nacen `propuesta` los pagos que anota quien entrega y lo que
        pase del tope de 50 (decisión 24); un aviso por cada caso;
      - RPC `rechazar_fila`, `fusionar_espejo` y `marcar_vistos`. `proponer_cambio` sigue
        igual (decisión 22): no hay `cambiar_acordada` ni `deshacer_cambio`;
      - avisos de `aceptar_propuesta`, `rechazar_propuesta`, `anular_propuesta`,
        `proponer_cambio` y `desvincular` por triggers (`_aviso_propuesta` en `propuestas`,
        `_aviso_vinculo` en `vinculos`), sin redefinir esas funciones;
      - lo pendiente al aplicarla pasa por `_llegada` (bloque `DO`; en local no había nada;
        **comprobar la nube con un `SELECT` antes del `db push`**);
      - funciones redefinidas (`registrar_pago`, `_nace_propuesta_post`,
        `exportar_mis_datos`): copia exacta de su última versión más líneas marcadas
        `v2 fase 8`, generadas con script con anclas.
- [x] **8.2** Regresión: `comparar_linea_base.py` 22/22 y `comparar_edges.py` 55/55
      (igual a producción). Sin vínculo no cambia nada.
- [x] **8.3** `09_aceptacion_automatica.sql`, **167 tests**, con control negativo. Los 15
      escenarios de abajo, ajustados a las decisiones del dueño (el 8 y el 9 comprueban que
      cambiar y borrar siguen siendo propuesta, con sus avisos), más 7c (fusión de una deuda
      que esperaba respuesta). Cada uno termina con `verificar_vinculo().ok` y "mi saldo" de
      los dos calculado a mano:
      1. A anota "B me debe $20" → las dos filas `acordada` y un acuerdo; aviso
         `deuda_nueva` a B; saldo acordado A = +20, B = −20.
      2. B anota "le debo $10 a A" → lo mismo, visto desde el otro lado.
      3. A anota un pago que recibió de B → acordado, espejo repartido en B (FIFO).
      4. B anota un pago que entregó → `propuesta` + `pago_por_confirmar` a A; no cuenta
         en el acordado. A confirma → acordado y `confirmado` a B. Otro pago: A dice "no lo
         recibí" → `rechazada` en B, `rechazo` con motivo.
      5. B rechaza el espejo del escenario 1 → las dos `rechazada`; aviso `rechazo` a A.
         Lo repartido pasa a saldo a favor (§4.2). No se rechaza lo propio (22023) ni lo
         ajeno (42501).
      6. Rechazar una deuda que entró en un cruce de la OTRA libreta → el cruce se
         recorta; ningún pago virtual queda con sobrante.
      7. Duplicados: (a) la de B ya estaba acordada → `fusionar_espejo` rechaza el par
         nuevo; (b) y (c) un pago y una deuda de B que esperaban respuesta ocupan el lugar
         del espejo. Ningún saldo queda duplicado.
      8. A propone cambiar el monto de 20 a 25 → aviso `cambio` a B, nada cambia hasta
         aceptar; B acepta → las dos filas cambian y a A le llega `confirmado`.
      9. B propone borrar algo acordado → aviso `borrado` a A; A lo rechaza → sigue igual.
      10. `UPDATE` directo del monto de una fila acordada → `42501` (la guardia sigue).
      11. El sync reintenta el mismo `INSERT` (upsert) → un solo espejo y un solo aviso;
          una fila nueva por upsert entra sola.
      12. Deudor sin vínculo → todo `local`, sin avisos.
      13. `registrar_pago` por RPC con el vínculo; la fila 51 del día nace `propuesta`; el
          tope es por persona.
      14. Desvincular con un pago por confirmar → queda anulado y su aviso se va; lo
          acordado sigue; `desvinculado` al otro.
      15. RLS: B no lee los avisos de A; nadie inserta, cambia ni borra avisos directo.
- [x] **8.4** `probar_concurrencia_propuestas.py` adaptado: en cada ronda los dos, a la
      vez, registran un pago recibido y después, en orden al azar, anotan deudas y pagos,
      rechazan, proponen cambios y responden lo pendiente. 6 semillas × 25 rondas: sin
      errores, invariante y cuadre intactos y **0 deadlocks**. Control negativo sin
      `_candado_vinculo`: 16 y 19 deadlocks (ver notas).
- [x] **8.5** Flutter (rama `v2` de `app_deudas`, commiteada sin push), "Listo para web":
      - **Novedades** (`screens/novedades_screen.dart`) en lugar de la bandeja: "Por
        responder" (Confirmar / No lo recibí para los pagos, Aceptar / Rechazar para lo
        demás) y "Novedades" (Rechazar, "Es la misma", marcar todo como visto). Contador
        en el inicio (`BotonNovedades`).
      - Marca **NUEVA** en la fila y "incluye $X … no habías visto" en el detalle.
      - "Rechazar (no la reconozco)" en la pulsación larga de una deuda que anotó el otro
        y un botón en los pagos del historial (`widgets/rechazar_fila.dart`).
      - Aviso previo "¿Es lo mismo?" al guardar una deuda o un pago
        (`widgets/aviso_duplicado.dart` + `lib/dominio/duplicados.dart`, Dart puro).
      - Editar algo acordado sigue proponiendo (decisión 22): sin cambios.
      - Cola sin conexión para `rechazar_fila`, `fusionar_espejo` y `marcar_vistos`
        (`services/avisos_service.dart`, `cola_avisos_<uid>`); las confirmaciones usan la
        cola de propuestas de siempre.
      - `origenId` en `Deuda` y `Pago` (campos Hive nuevos, sin migrar cajas).
      - `PlanPago` y sus tests no cambian.
- [x] **8.6** `reading.py`: no hace falta nada. Lo `rechazada` ya se filtra y los espejos
      llegan `acordada`, como al aceptar en la fase 6.
- [x] **8.7** Lista de dos celulares reescrita (§0.4, bloque B).

**Criterio de salida.** Tests y concurrencia en verde, regresión en 0, `flutter build
web` compila (todo ✅ en local, 2026-09-24) y la prueba en dos celulares (8.7) sin fallos
graves (**falta**: necesita la migración en la nube y la APK nueva, con OK del dueño).

**Notas de ejecución** (2026-09-24)

- **Resultado en local:** `supabase test db` → **398/398** (231 + 167). Línea base 22/22,
  edges 55/55, `probar_rpc_v2` OK, `probar_fase7` OK (adaptado: ahora las deudas entran
  solas y lo pendiente es un pago entregado), concurrencia OK en 6 semillas. Flutter:
  `flutter analyze lib` 0 errores (183 avisos, 4 menos que antes: se fue la bandeja);
  tests 35/35 (6 nuevos en `duplicados_test.dart`); `flutter build web` compila.
- **Control negativo de `09`:** sin aceptación automática fallan 140; sin apagar el aviso
  al aceptar en nombre del otro, 1; si el rechazo no descuenta la fila del otro, 24; si la
  fusión no borra el espejo (deuda o pago), 62 o 65.
- **Actuar como el otro:** `_suplantar` escribe `request.jwt.claim.sub`, que `auth.uid()`
  mira antes que `request.jwt.claims`. Así `aceptar_propuesta` y `registrar_pago` (que
  valida el deudor con `auth.uid()` y pone `owner_id` por DEFAULT) corren como B dentro
  del `INSERT` de A. Se restaura al volver; un error lo deshace solo.
- **Deadlock encontrado por la prueba de concurrencia:** `registrar_pago` de A toma el
  candado de su deudor y, en el trigger, el espejo pide los dos del vínculo; B, al mismo
  tiempo, al revés. Postgres lo detecta al segundo (`deadlock_timeout`) y **PostgREST
  reintenta el 40P01 sin avisar**: el cliente no veía error, solo ~1,1 s de espera por
  pago (contra ~90 ms). Con `_candado_vinculo` al principio de `registrar_pago`, 0. El
  script ahora mide `pg_stat_database.deadlocks` antes y después.
- **Bug encontrado por los tests:** `_es_de_conciliacion` daba NULL con un `idem_key`
  nulo (un cambio propuesto sin clave) y el aviso "confirmado" no salía. Con `COALESCE`.
- **Tests de la fase 6 (`06`, `08`):** prueban el camino de la propuesta, así que ponen
  `deudas.tope_diario = 0` al preparar. Sin eso fallaban 95 (lo esperado: ahora todo entra
  solo).
- **Las propuestas de 'crear' se siguen creando** (ya `aceptada`): la app lee de ahí los
  motivos de rechazo, y `_nacidas_hoy` cuenta el tope con ellas (solo las del trigger, con
  su clave `crear`; la conciliación no cuenta).
- **En la nube de prueba (2026-09-24):** el agente no pudo hacer el `db push` (el modo
  automático no le deja modificar la base en la nube; un `--dry-run` sí) y lo corrió el
  dueño con `! …` desde la sesión. Salió el error conocido de `pg-delta` (§10), pero
  `migration list` confirmó `20260924150000` en remoto.
  - La nube ya tenía datos de prueba del dueño (3 perfiles, 1 vínculo activo) con **una
    propuesta pendiente** (deuda de $10 de "Alice" a "Bob"): el bloque `DO` la hizo entrar
    sola y a Bob le llegó su `deuda_nueva`. `verificar_vinculo` ok.
  - `test db --linked`: 398/398 tras corregir `05_conciliacion.sql`, que contaba **todos**
    los acuerdos de la base (con datos del dueño daba 7, no 5): ahora cuenta los de su
    vínculo. `probar_rpc_v2`, `probar_fase7` y `probar_concurrencia_propuestas --rondas 10`
    con `--destino nube`: OK. Las edges no cambian.
  - Commits: `fbbb40b` (este repo, `feat/deudas-v2`) y `27858ce` (`app_deudas`, `v2`), más
    el de este arreglo; APK v2 recompilada (`deudas-v2-nube-debug.apk`, 219 MB). Sin push.
- **Pendiente:** instalar la APK y la prueba en dos celulares (§0.4 B, lista nueva).

**Primera persona real y login con código (2026-09-24, noche)**

- El dueño le pasó la app a su mamá (APK release por WhatsApp, sin cable):
  `flutter build apk --release --split-per-abi` con los `--dart-define` de v2 → la de
  `arm64-v8a` (27 MB), copiada como `build/app/outputs/flutter-apk/Deudas-v2.apk`. Firmada
  con la clave de debug de esta máquina (§0.4 D): las actualizaciones solo instalan encima
  si se compilan aquí.
- **`--split-per-abi` suma 1000/2000/4000 al `versionCode`** (armeabi/arm64/x86_64). La de
  la mamá es 2002 (`version: 1.0.0+2`): una actualización tiene que ser `split-per-abi` y
  con el `+N` más alto, o Android la rechaza (`INSTALL_FAILED_VERSION_DOWNGRADE`).
- **El enlace mágico falló** ("Email link is invalid or has expired"): en la nube el
  correo quedó confirmado, el token gastado y el `flow_state` PKCE sin canjear. El
  navegador interno de Gmail validó el enlace pero no volvió a la app, y el segundo toque
  encontró el token usado. Arreglo inmediato: contraseña puesta por la API de
  administración (la cuenta es `paulyarciniega@gmail.com`; su perfil se llama
  "paulyarciniega", falta el nombre que ella quiera).
- **Arreglo de fondo: entrar con código.** El correo trae el código
  (`supabase/templates/codigo.html`, plantillas `magic_link` y `confirmation` en
  `config.toml`) y la app lo pide después de "Enviarme el código" (`verifyOTP` con
  `OtpType.email`, sirve para cuenta nueva y existente); el enlace queda de respaldo. Probado:
  `scripts/v2/probar_login_codigo.py` (local, lee el correo en Mailpit; control negativo sin
  plantillas: falla) y en el emulador contra el stack local (APK con el manifiesto de debug
  permitiendo HTTP, revertido después): código → sesión → libreta vacía. APK release
  recompilada con esto (`1.0.0+2`).
- **Falta: `supabase config push` en la nube** (lo corre el dueño: el agente no puede
  modificar la nube y en modo agente aplica sin preguntar). Hasta entonces, la nube manda el
  correo viejo (solo enlace) y la app nueva pide un código que no llega: en la nube se entra
  con contraseña o con el enlace. La última vez que se pushó, la configuración de Auth
  quedó "up to date", así que la diferencia deberían ser solo las dos plantillas.

---

### Fase 9 — Gastos divididos y grupos

**Objetivo.** Dividir un gasto entre varios contactos sin crear un grupo (9A) y grupos
compartidos donde los gastos se dividen solos y todo cuenta de una vez salvo rechazo (9B).

**Prerrequisitos.** Fase 8 ✅ (usa `avisos` y, en el gasto suelto con contactos vinculados,
la aceptación automática). Que el dueño haya revisado las decisiones 25 a 31 de §3.3
(**hecho el 2026-09-24**: las aprobó sin cambios y pidió 9A y 9B en local, sin nube ni
commit hasta que lo pida).

**Contexto.** §3.2, §4.8, §5.4 (fase 9) y "Listo para web" (§6.5).

**Pasos: 9A, gasto suelto**

- [x] **9.1** Repartir: `_repartir(monto, pesos)` en SQL y `lib/dominio/reparto.dart` en
      Dart puro. Test de paridad con una tabla de casos compartida: $100 entre 3; $0.05
      entre 3; montos fijos que no suman el total (error); porcentajes que no suman 100
      (error); partes 2:1:1; un solo participante; repartir de nuevo tras un rechazo.
- [x] **9.2** Migración `<ts>_gastos.sql`: `gastos`, `gasto_participantes`,
      `deudas.gasto_id` (FK compuesta con el dueño), trigger de guardia para las deudas
      de un gasto, lápidas y `updated_at`, `crear_gasto`/`editar_gasto`/`borrar_gasto`
      para `grupo_id` NULL. Tests `10_gastos.sql` con control negativo:
      1. Pagué $90 entre yo, Ana y Beto → dos deudas de $30 con `gasto_id`; mi parte en el
         gasto; `estado_cuenta` de Ana y de Beto +30.
      2. Pagó Ana → una deuda "le debo $30"; la parte de Beto solo en el gasto.
      3. Sin incluirme → $45 cada uno.
      4. Editar el total a $96 → deudas de $32. Bajarlo por debajo de lo ya pagado de una
         → suelta el exceso (decisión 16).
      5. `UPDATE` directo del monto de una deuda del gasto → `42501`; el título sí se puede.
      6. Ana vinculada → su deuda sigue §4.7 (espejo y aviso en la libreta de Ana).
      7. Borrar el gasto → sus deudas se van (o pasan a `rechazada` si están acordadas).
      8. Idempotencia de `crear_gasto`; RLS (nadie ve un gasto suelto ajeno).
      9. Regresión: 22/22 y 55/55.
- [x] **9.3** Flutter 9A: en "Nueva deuda", el interruptor **"Dividir entre varios"**:
      selección múltiple de contactos, "Incluirme" (marcado por defecto), quién pagó (yo
      o un contacto), modo, vista previa de cuánto le toca a cada uno (con
      `reparto.dart`) y guardar (cola sin conexión con `idem_key`; se ve al instante). En
      el historial: "Cena · $90 entre 3"; tocarla abre el gasto para editarlo.

**Pasos: 9B, grupos**

- [x] **9.4** Migración `<ts>_grupos.sql`: `grupos`, `grupo_miembros`,
      `grupo_invitaciones`, `grupo_pagos`, `_soy_miembro`, RLS, los RPC de §5.4,
      `rechazar_parte` y `estado_grupo`, los avisos del grupo y los límites de uso
      (invitaciones de grupo por día, como 7.3). Tests `11_grupos.sql` con control
      negativo:
      1. Grupo con A, B y C (usuarios) y D (persona). A paga $90 entre A, B y C → B y C le
         deben $30 a A; avisos `gasto_nuevo` a B y C.
      2. Otro grupo con los mismos miembros → saldos independientes.
      3. C rechaza su parte → rechazada para C; la de B pasa a $45; gasto `en_revision`;
         avisos a A y B; el neto de C por ese gasto es 0.
      4. A (quien pagó) rechaza → gasto `rechazado` para todos.
      5. Modo `montos`: B rechaza → lo absorbe A y queda en revisión (decisión 26).
      6. Pagos: A (recibe) anota B→A $30 → cuenta. B (entrega) anota B→A → por
         confirmar, no cuenta; A confirma → cuenta; A dice "no lo recibí" → rechazado.
      7. D (persona): A anota que D le debe; el pago D→A que anota A cuenta de una vez.
      8. Editar un gasto quien no lo anotó ni lo pagó → `42501`. Volver a incluir a quien
         rechazó.
      9. Salir con saldo ≠ 0 → error; con saldo 0 → sale y deja de ver el grupo.
      10. RLS: quien no es miembro no ve nada; un miembro no lee la libreta de otro;
          nadie escribe directo en ninguna tabla del grupo.
      11. Unirse con un código vencido, usado o inválido → mismo error (sin sondeo).
      12. Idempotencia de todos los RPC.
      13. Regresión: 22/22 y 55/55 (los grupos no tocan `estado_cuenta`).
- [x] **9.5** Flutter 9B: pestaña **Grupos** (lista con mi saldo en cada uno), detalle
      (gastos con su estado, saldos por par, "Saldar", pagos por confirmar), nuevo gasto
      del grupo (mismo formulario que 9.3 con los miembros), invitar (enlace
      `/grupo/unirse/<código>` + QR y WhatsApp), unirse, agregar persona sin app, rechazar
      mi parte con motivo, salir o archivar. Los avisos del grupo en Novedades. Pull
      incremental de las tablas del grupo. Saldos del grupo sin conexión con Dart puro
      (`lib/dominio/saldos_grupo.dart`) y paridad con `estado_grupo`.
- [x] **9.6** Inicio: total = contactos + grupos, mostrados por separado.
- [x] **9.7** `exportar_mis_datos` (7.2) incluye mis grupos, gastos y pagos del grupo.
      `borrar_cuenta`: mis filas de `grupo_miembros` pasan a persona sin app (`usuario_id`
      NULL, se conserva el nombre) para que los saldos de los demás no cambien. Pasa
      también a la política de privacidad.

**Criterio de salida.** Tests en verde, regresión en 0, `flutter build web` compila y una
prueba real: un grupo con 3 cuentas de prueba, con gastos, un rechazo y pagos (confirmado
y por confirmar), en el que los saldos de los tres cuadran.

**Etapa 9C** (opcional, después): ver §4.8.

**Notas de ejecución (2026-09-24, noche; todo en LOCAL, sin nube ni commit)**

- **Qué hay.** SQL: `20260924160000_gastos.sql` (9A: `gastos`, `gasto_participantes`,
  `borrados_gastos`, `_repartir`, `_partes_gasto`, guardia de las deudas de un gasto,
  `crear_gasto`/`editar_gasto`/`borrar_gasto`, `cambios_gastos`) y
  `20260924170000_grupos.sql` (9B: tablas del grupo, RLS con `_soy_miembro`, los RPC de
  §5.4 más `borrar_pago_grupo`, `estado_grupo`, avisos y límites: 20 grupos y 20 enlaces
  por día, 50 miembros). Tests `10_gastos.sql`, `11_grupos.sql` y `13_grupos_sin_nadie.sql`.
  Flutter (`app_deudas`, sin commitear en la rama `v2`): `lib/dominio/reparto.dart` y
  `saldos_grupo.dart` (Dart puro, con paridad contra el SQL por fixtures que genera
  `scripts/v2/generar_casos_gastos.py`: 161 casos de `_repartir`, 200 de `_partes_gasto`,
  40 grupos al azar), `GastosService` (pull incremental con su propio cursor, cola sin
  conexión con `idem_key`, guarda en preferencias: sirve en web), `PanelDividir` en "Nueva
  deuda", pantallas de gasto, grupos y grupo, rutas `/grupo/unirse/<código>`,
  `/grupo/<id>` y `/gasto/<id>`, avisos del grupo en Novedades e inicio con contactos +
  grupos.
- **Verificado (local):** `supabase test db` 709/709 (714 desde el arreglo de la 180000); `comparar_linea_base` 22/22;
  `comparar_edges` 55/55; `probar_rpc_v2`, `probar_concurrencia_propuestas` y
  `probar_fase7` OK; `flutter test test/reparto_test.dart test/saldos_grupo_test.dart` OK;
  `flutter analyze` sin errores (queda una advertencia vieja en `database_service.dart`);
  `flutter build web --dart-define=DEUDAS_V2=true` compila.
- **Criterio de salida, prueba real:** `scripts/v2/probar_grupos.py` (por la API, con 3
  cuentas temporales y una persona sin app): dos gastos, un rechazo de parte (el gasto pasa
  a revisión y vuelve a activo cuando los avisados lo ven), pagos confirmado, por
  confirmar → confirmado, rechazado y de una persona sin app, salir con saldo ≠ 0 (error) y
  con saldo 0. En cada paso A, B y C ven los mismos pares y netos, iguales a los
  calculados a mano, y ninguna libreta cambia. Falta la prueba en celulares (necesita la
  nube y una APK nueva).
- **Bug encontrado por esa prueba: un grupo no se podía borrar** (`23503`). Las cascadas
  de `grupos` corren una tras otra y la FK `gasto_participantes → grupo_miembros` (NO
  ACTION) se comprobaba apenas se iban los miembros, con las partes todavía ahí; igual las
  dos puntas de `grupo_pagos`. Arreglo en `20260924190000_grupos_sin_nadie.sql`: esas FK
  pasan a `DEFERRABLE INITIALLY DEFERRED` (borrar un miembro suelto sigue fallando, con
  control negativo en el test 13). Ninguna pantalla borra grupos, pero sin esto tampoco se
  podía limpiar nada a mano.
- **Grupos sin nadie (decisión 34):** al borrar la última cuenta con app de un grupo, el
  grupo quedaba para siempre sin que nadie pudiera verlo. `_perfil_sin_gastos` ahora lo
  borra, con las lápidas de grupos que ya no existen. Recorre todos los grupos en cada
  cuenta borrada (el FK ya puso `usuario_id` en NULL, así que no se sabe cuáles eran los
  suyos): barato con pocos grupos; si crece, guardar antes los grupos de la cuenta.
- **`20260924180000_fix_rechazar_cruces.sql` (+ test `12_fix_rechazar_cruces.sql`):** la
  escribió otra sesión el 2026-09-24 a las 19:29 (no es de la fase 9). Hace tolerantes
  `_sacar_de_cruces` y `_editar_cruce_aplicar` a cruces con los dos pagos virtuales en
  `es_mi_pago = false` o sin `cruce_id`. **Corregida el 2026-09-25** (nunca llegó a la
  nube), porque la primera versión abría dos agujeros:
  1. `_editar_cruce_aplicar` pasaba a `SECURITY DEFINER`. Tiene `GRANT` a
     `authenticated` y depende del RLS para no ver cruces ajenos: cualquiera con sesión
     podía recortar o borrar el cruce de otro sabiendo su id.
  2. El `DELETE FROM pagos WHERE es_compensacion AND cruce_id IS NULL AND <sin detalle>`
     de `_sacar_de_cruces` no filtraba por dueño, y esa función corre dentro de RPC
     `SECURITY DEFINER` (`rechazar_fila`, `rechazar_propuesta`): rechazar una deuda
     borraba los pagos de compensación huérfanos **de todos los usuarios**.

  Ahora las dos funciones son copia exacta de su versión de `120000` más líneas marcadas
  («v2 arreglo cruces mal formados»), generadas por script y verificadas con `diff`;
  `_editar_cruce_aplicar` sigue `SECURITY INVOKER` y el `DELETE` borra solo los pagos cuyo
  detalle acaba de soltar (`DELETE … RETURNING` en una sentencia y el borrado en otra: en
  la misma, el `NOT EXISTS` todavía ve los detalles borrados). La deducción de cuál pago
  es cuál solo se aplica si da dos pagos distintos. Test 12 con 5 aserciones nuevas
  (8 a 11 son el control negativo: contra la versión vieja fallaron las 4). `db reset` +
  reimportar + batería completa en local: 714/714, 22/22, edges iguales, `probar_*` OK.
- **Flutter:** se corrigió un uso de `notifyListeners` desde fuera del `ChangeNotifier`
  (`ControlDividir.agregar`, al sumar una persona sin app desde el formulario) y se quitaron
  imports sin usar. En la misma copia de trabajo hay cambios de otra sesión (punto de
  pendientes en el inicio y los contactos, Novedades más grande, `pendientes_helper.dart`):
  compilan, pero no los revisó este agente.
- **Para subir la fase 9** (cuando el dueño lo pida): revisar 32 a 34 y la 180000; `db
  push` de 160000 a 190000 (lo corre el dueño con `! …`; antes, `--dry-run`); `test db
  --linked` (la nube tiene datos del dueño: los tests no suponen tablas vacías, pero
  conviene mirar los que cuentan filas); `probar_grupos.py --destino nube`; commit con
  `rama_v2.sh` (correr `estado` antes: hay archivos de otra sesión) y en `app_deudas`;
  recompilar las APK (§6.5).

---

## 9. Pendiente de decidir (preguntar al dueño en la fase indicada)

| Decisión | Se necesita en | Opciones / recomendación |
|---|---|---|
| ~~Plan y organización del proyecto v2~~ | Fase 2 | **Decidido (2026-09-23):** todo gratuito, con la cuenta del dueño, en su única organización (la gestionada por Vercel). Para **publicar** (fase 7) conviene revisarlo: el plan gratuito con Nano ya agotó el presupuesto de Disk IO de v1 con un solo usuario; Pro cuesta ~$25/mes. **No subir de plan sin el dueño.** |
| Proveedores de login | Fase 2 | Email (magic link y contraseña) **ya activo**. Google: **aplazado por el dueño (2026-09-23)**; el código queda escondido tras `LOGIN_GOOGLE`. En su tesis solo podía entrar él: casi seguro la pantalla de consentimiento estaba en modo *Prueba* (solo entran los "usuarios de prueba"); para abrirlo a todos hay que *Publicar app*, y con solo email/perfil no pide verificación de Google. Antes: pendiente del dueño, que tiene que crear el cliente OAuth en Google Cloud Console (ver 2.1). Apple solo si hay versión iOS. |
| ~~¿Commitear el trabajo de v2 y en qué ramas?~~ | — | **Hecho (2026-09-24):** `feat/deudas-v2` aquí y `v2` en `app_deudas`, sin push. ¿Push? Lo decide el dueño (§0.4 E). |
| ~~Decisiones 10 a 20 de §3.3~~ | — | **Revisadas por el dueño (2026-09-25):** cambió 12, 14 y 17; las demás tal cual. |
| ~~Nombre y dominio públicos~~ | Fase 4 (enlaces de invitación) | **Decidido por el dueño (2026-09-24):** `visor-deudas.vercel.app` por el momento. |
| ¿Corregir el bug de $0.01? | Después de la fase 3 | Corregirlo con su propia verificación, nunca mezclado con una migración de v2. |
| ¿El visor muestra "saldo acordado" a un deudor vinculado? | Fase 6 | Por defecto el visor sigue igual (decisión del dueño: "funciona tal cual"). Implementado así: el visor usa la service_role y `estado_cuenta` no le agrega nada. |
| ¿El título viaja en la propuesta? ¿Desvincular devuelve a `local` lo pendiente? | Fase 6 (ya implementado así) | Decisiones 10 y 11 de §3.3. Confirmar con el dueño. |
| ~~Filas anotadas entre las dos confirmaciones de la conciliación~~ | — | **Decidido y hecho (2026-09-24):** se proponen al pasar a `activo` (decisión 18). |
| Límites de uso (20 invitaciones/día, 10 canjes fallidos/hora, 60 visor/minuto) | Antes de publicar | Implementados con esos valores (decisión 20). Ajustar si el dueño prefiere otros. |
| Política de privacidad | Antes de publicar | Borrador en `deudas/v2/POLITICA_PRIVACIDAD.md`: completar responsable, correo y plazos, revisar y publicar. |
| ~~Decisiones 21 a 24 de §3.3 (aceptación automática)~~ | — | **Revisadas por el dueño (2026-09-24):** 21 = avisar antes a quien anota; 22 = cambios y borrados siguen siendo propuesta; 23 = conciliación explícita; 24 = tope de 50. |
| ~~Decisiones 25 a 31 de §3.3 (gastos y grupos)~~ | — | **Aprobadas por el dueño sin cambios (2026-09-24).** |
| ~~Decisiones 32 a 34 de §3.3~~ | — | **Revisadas por el dueño (2026-09-25):** 32 = 5 días; 34 = 30 días de gracia; 33 tal cual. |
| ~~Decisiones 35 a 37 de §3.3~~ | — | **Aprobadas por el dueño (2026-09-25)**; la 36 con aviso claro a quien propuso primero. |
| ¿PWA? | Después de la fase 9 | **Aplazada por el dueño (2026-09-24).** Mientras tanto, todo el código nuevo cumple "Listo para web" (§6.5). A favor: sin instalar nada, sirve en iPhone, invitar es un enlace y se evita Play Store. En contra: iOS puede borrar lo guardado sin sincronizar si no se agrega a la pantalla de inicio, y en iPhone los push solo funcionan con la PWA instalada. |

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

Trampas encontradas en la fase 8:

- **Enlace mágico de un solo uso:** el navegador interno de Gmail (o un escáner de enlaces)
  lo puede gastar sin volver a la app, y el siguiente toque da `otp_expired`. Por eso se
  entra con código (notas de la fase 8).

- **PostgREST reintenta un 40P01 (deadlock) sin avisar.** El cliente no ve el error, solo
  ~1 s de espera (el `deadlock_timeout`). Para detectarlo, mirar
  `pg_stat_database.deadlocks` antes y después (lo hace `probar_concurrencia_propuestas.py`)
  o el log del contenedor (`podman logs supabase_db_deudas_v2 | grep deadlock`).
- **Un trigger que escribe en la libreta del otro toma SUS candados.** Si la operación que
  lo dispara ya tenía el candado de su deudor (`registrar_pago`), los dos se traban. Tomar
  los candados del vínculo primero (`_candado_vinculo`).
- **Actuar como otro usuario:** `auth.uid()` mira `request.jwt.claim.sub` antes que
  `request.jwt.claims`; `_suplantar` escribe el primero y lo restaura. Solo desde
  funciones internas (sin `EXECUTE` para los clientes).
- **`x IN (…)` con `x` NULL da NULL**, y `NOT NULL` también: un `IF` así no entra. Pasó con
  `_es_de_conciliacion` y un `idem_key` nulo; envolver en `COALESCE(…, false)`.
- **Los tests de la fase 6 prueban la bandeja:** con la aceptación automática fallarían.
  `set_config('deudas.tope_diario', '0', true)` al preparar los devuelve a ese camino.

Trampas encontradas en la fase 9:

- **FK `NO ACTION` y cascadas en cadena:** al borrar un padre con dos cascadas (grupo →
  miembros y grupo → gastos → partes), la FK de las partes a los miembros se comprueba
  apenas se van los miembros, antes de que se vayan las partes (`23503`). Hacerla
  `DEFERRABLE INITIALLY DEFERRED` (§ fase 9, notas).
- **Una función sin `SECURITY DEFINER` llamada desde una que sí lo es corre sin RLS.** Un
  `DELETE` sin filtro por dueño dentro de ella borra filas de todos (pasó en
  `20260924180000_fix_rechazar_cruces.sql`, sin subir).
- **`comparar_edges.py` dos veces en el mismo minuto falla** por el límite del visor (60
  consultas por minuto por IP): esperar un minuto.

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
