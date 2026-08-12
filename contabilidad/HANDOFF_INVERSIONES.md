# Handoff — Módulo de Inversiones

Estado al 2026-08-12, rama `enriquecimiento-horas`. Este documento es para retomar el
trabajo sin haber estado en la conversación. El plan completo (diseño, decisiones,
fases) está en **`contabilidad/PLAN_INVERSIONES.md`** — este archivo es el resumen
operativo de lo que existe hoy y lo que falta.

---

## 1. Estado por fases

| # | Fase | Estado |
|---|---|---|
| 0 | Limpiar la columna `INVERSION` | ✅ hecha |
| 1 | Detector de posiciones | ✅ hecha |
| 2 | Persistencia (`posiciones.csv` + `movimientos.csv`) | ✅ hecha |
| 3 | Métricas + Resumen | ✅ hecha |
| 4 | Evolución + Conciliación (frontend) | ✅ hecha |
| 5 | Patrimonio con toggle | ✅ **hecha** (2026-08-12) |
| 6 | Migración de pagos fijos | ⚠️ **previsualizable, sin migrar** |

La fase 6 se construyó a propósito **en modo solo lectura**: el generador existe, la
comparación existe, la pantalla existe. Nada de este módulo escribe en `pagos.csv`.

### Empieza por aquí

**El módulo reproduce la contabilidad del usuario.** Estado de la neutralización hoy:

| portafolio | días descuadrados | desvío máx. | |
|---|---:|---:|---|
| `Inversiones_Mias` | 0 de 1.320 | 1,38 | ✅ cuadra |
| `Inversiones_Madre` | 0 de 657 | 1,24 | ✅ cuadra |
| `Inversiones_Uni` | 806 de 9.721 | 12,59 | redondeo, ver §7.1 |

**Nada bloquea la fase 6.** Lo que queda son tres cosas, en orden de valor: cerrar el corte
(§7.4), quitar la dependencia de `pagos.csv` (§3.1 y §7.3) y capturar plazos y tasas (§7.2).

**Decisión del usuario (2026-08-12): `pagos.csv` se retira** y este módulo lo reemplaza. Se
verificó vaciándolo sobre una copia: el módulo **no se rompe**. El inventario de lo que
todavía depende de él está en §3.1.

**Antes de escribir código**, lee §9 (trampas) — hay varias que cuestan horas de descubrir.

---

## 2. Qué se hizo en la última sesión

### 2.0 Por qué divergían los pagos — resuelto

**Los pagos escritos a mano no estaban mal.** Los dos sistemas medían cosas distintas: los
del usuario dicen *cuánta plata de inversión existe*; los del generador, *cuánto salió de
certificados y no volvió a entrar*. Coinciden en `Mias`, donde nunca sale plata, y se
separan en `Uni` y `Madre`, donde sí.

Cada vez que vence un certificado de `Uni` salen ~3.2xx que se van en **matrícula**
(confirmado por el usuario) y no se reinvierten. Eso estaba registrado **solo como la
fecha de fin de un pago fijo** — ninguna de las dos puntas es una operación de
certificado, así que el banco no la delata y el generador seguía arrastrando esa plata.

La suma cierra al centavo, que es lo que prueba que no había nada más:

```
Uni:    3.177 − 9,23 + 3.834,64 − 3.635,07 + 3.213,74 + 3.267,33 + 4.279,26 = 14.127,67
Madre:  −0,84 + 3.533,84 + 0,95 + 1,13 + 10.446,97                          = 13.982,05
```

y esos son exactamente los residuales finales que reportaba el generador.

**La solución: `flujo`** (§2.1). Aplicado en dos pasos, los dos con script reversible:

| portafolio | antes | + 11 flujos | − 2 `ajuste` | hoy |
|---|---|---|---|---|
| `Inversiones_Mias` | máx 27.066,42 | igual | igual | **CUADRA** (máx 1,38) |
| `Inversiones_Madre` | máx 13.335,05 | 1.292,79 | 648,21 | **CUADRA** (máx 1,24) |
| `Inversiones_Uni` | máx 14.127,67 | 3.240,59 | **12,59** | 12,59 |

`Mias` cerró cuando el usuario escribió a mano el cierre del CDT del 2026-07-27 en
`pagos.csv` (27.067, con fin `2030-01-01`), más el arreglo de la ventana de comparación.
Sus 1,38 son el redondeo a enteros y nada más.

`Madre` cerró con una salida más: el sobrante de 648,21 del último ciclo, que se fue el
2026-03-02 (la fecha en que termina la fila «Lo que sobra»).

Lo de `Uni` son 8–12 dólares en tres tramos largos: vienen del 9,23 con que no cierra la
posición sembrada de 10.100 (10.100 + 172,21 − 3,44 = 10.268,77, pero el CDT siguiente
pide 10.278). Están por encima de `TOLERANCIA_REDONDEO = 2,0`, así que la pantalla dice
«no cuadra» aunque sean calderilla. **No se tapó subiendo el umbral**: mover la vara para
que pase es exactamente lo que no debe hacer esta herramienta.

**Dos arreglos de la comparación, no de los datos:**

1. **La ventana termina hoy.** Antes llegaba hasta el último `end_date` que no fuera
   centinela, y `ANIO_CENTINELA = 2900` no reconoce el `2030-01-01` que el usuario también
   usa como «hasta siempre». Eso estiraba la comparación tres años y medio y marcaba
   descuadrado el último día de un tramo que sí cuadra.
2. **Una fila sin `end_date` no cuenta.** `pagos_actuales()` marcaba `aplica=False` solo a
   las filas sin `start_date`, pero `get_payments()` hace `dropna` sobre **las dos** fechas.
   Los 647 duplicados de `Madre` no tienen fin: son invisibles para el dashboard *y* para la
   pantalla de Variables —el usuario no los ve y por tanto no puede borrarlos— y aun así se
   estaban contando aquí. **Ese era el descuadre de 645,79: un bug de esta herramienta, no
   un problema de los datos.** El usuario lo detectó diciendo que esa fila no la veía por
   ningún lado.

**Los 2 `ajuste` borrados contaban plata dos veces**, y sus propias notas los delataban:

- `siembra-uni-madre-tarjeta` (3.228) decía «3.228 que **entraron** al portafolio» pero
  estaba escrito como `aporte`, o sea saliendo. Y ninguna lectura era correcta: los 3.228
  son **parte de los 10.482,64 que devolvió el CDT** ese día, en una segunda fila de
  `pagos.csv` solo para etiquetarlos. Las dos filas del usuario suman 7.258 + 3.228 =
  10.486 ≈ lo devuelto, y el 09-23 esa plata se reparte en 6.648 (nuevo CDT) + 3.834,64
  (matrícula) = 10.482,64 exacto. No queda hueco para 3.228 más. Restarlos hacía que el
  escalón del 2024-09-04 saliera **7.245,41 en vez de 10.473,41** — que es lo que el
  usuario vio en el gráfico.
- `siembra-madre-647` decía «los 647 que **sobraron**», que es precisamente el residual, no
  una posición aparte. Tras los dos retiros de 4.900 el residual aterriza solo en 646,97.

Los dos salieron también de `scripts/sembrar_posiciones_inversion.py`, con el razonamiento
escrito ahí: si vuelven, vuelve el bug.

**El generador nunca escribió en `pagos.csv`** — todo lo anterior son filas de
`posiciones.csv` y `movimientos.csv`. `grupos.csv` sigue byte por byte idéntico. Y un A/B
del dashboard contra el snapshot previo confirma que `TOTAL`, `NOTIONCUM` y todos los
componentes salen iguales, porque un `flujo` no es capital invertido.

Lo único que se tocó de `pagos.csv` fue borrar 4 filas fantasma, a petición explícita del
usuario — §2.3.

### 2.1 Registrar salidas y entradas de dinero — `tipo='flujo'`

Un `flujo` es dinero que **entra o sale del portafolio y no vuelve**. Es distinto de un
`ajuste` justamente en eso: el ajuste es un tramo acotado que se cierra y devuelve la
plata; el flujo es definitivo.

- **Salida** → un movimiento `aporte` (SIGNO −1): el residual baja para siempre.
- **Entrada** → un movimiento `retiro` (SIGNO +1).
- Es **instantáneo**: `fecha_apertura == fecha_cierre`, así que nace `estado='cerrada'` sin
  forzar nada, y queda fuera del devengo y de los cierres ficticios del XIRR.
- El monto es **siempre positivo**; el signo lo da la dirección. Con negativos habría dos
  formas de escribir lo mismo y una terminaría al revés.
- `origen='manual'`, así que el detector no lo toca ni lo reporta como sobrante.

**Endpoints:** `POST /api/investments/flows` y `GET /api/investments/flows/preview`
(residual antes/después, sin escribir).

**UI:** botón «Registrar salida» en Inversiones → Posiciones, con selector de dirección y
el residual antes/después en vivo. Si el monto deja el portafolio en negativo lo avisa —
significa que falta registrar algo antes o que el monto está mal.

**`residual_portafolio()` usa las dos pasadas de `neutralizacion.preview`**, no el
`saldo_inicial` de `grupos.csv`. Tiene que ser así o el formulario y la pestaña de
Neutralización mostrarían números distintos del mismo día: mientras el saldo inicial siga
sin configurarse, el de `grupos.csv` es 0 y el deducido son los 26.000 de `Mias` o los
3.177 de `Uni`.

**Bug arreglado de paso: el XIRR incluía los `ajuste`.** `flujos_de()` no filtraba por
tipo, así que cualquier posición que no fuera inversión entraba en la TIR. Con matrículas
registradas eso habría convertido el rendimiento en una pérdida enorme que nunca existió.
Ahora solo entran `TIPOS_INVERTIDOS`.

### 2.2 Fase 5 — patrimonio con toggle

**`services/investments/patrimonio.py` — nuevo.** Devuelve, por día, el capital propio que
estaba dentro de una posición. Dos reglas deciden qué entra:

- **Solo lo propio.** `Uni` y `Madre` son `es_custodia`. Una posición sin portafolio cuenta
  como propia — mismo criterio que `metricas.resumen`.
- **Solo lo que está dentro de una posición.** Los `ajuste` quedan fuera (los filtra
  `metricas.timeline` por `TIPOS_INVERTIDOS`): son plata de inversión suelta que el saldo
  bancario ya muestra, y sumarla la contaría dos veces.

El interés devengado de las abiertas **no** se suma: es una estimación.

**Las dos series se calculan siempre; el flag vive en la respuesta, no en el pipeline.**
La transformación `capital_invertido` llena `NOTIONCUM` antes de `dashboard_metrics`;
`MetricProcessor` emite `TOTAL` (intacto, byte por byte) y
`TOTAL_CON_INVERSIONES = TOTAL + NOTIONCUM`; `_build_response` elige cuál va en `total`.
Así el caché del pipeline no se parte en dos por un flag de petición.

`GET /api/dashboard/chart-data?incluir_inversiones=true`, y el mismo parámetro en
`/variations` — **tienen que ir iguales**, porque el desglose se contrasta contra el mismo
total. En el frontend el toggle vive en `App.tsx` por esa misma razón, y entra en la
`queryKey` de las dos consultas.

**Dos cosas que el plan no anticipó y conviene no volver a descubrir:**

1. **Forzar `diff_notion` a cero con el flag apagado era necesario pero no suficiente.**
   `VariationsAnalyzer` calcula `residual = diff_total − drivers`, y el capital invertido
   no tiene transacción propia: abrir un CDT ya aparece como movimiento del banco *y* como
   pago fijo, y `diff_notion` es ese mismo dinero visto del otro lado. Con el toggle
   encendido, el día del CDT de 28.304 el desglose lo declaraba entero "sin explicar".
   Ahora el residual descuenta `d_notion`; con el toggle apagado vale 0 y no cambia nada.
2. **`Col` es un `(str, Enum)`.** `df[Col.NOTIONCUM]` encuentra la columna por igualdad,
   pero el Index se queda con el miembro del enum y al exportar a CSV el encabezado sale
   `Col.NOTIONCUM`. Las columnas se escriben con `.value`.

**Verificado sobre los datos reales:** `TOTAL` se reconstruye exacto con su fórmula
original (desvío máximo 0,0000000000), `NOTIONCUM` va de 0 a 28.304, el desglose diario
cuadra en las dos vistas con el mismo residual máximo (31.823,39), y **hoy el capital
propio vivo es 0** — el último CDT cerró el 2026-07-27, así que el toggle mueve la historia
pero no la cifra de hoy. Es esperado, no un fallo.

### 2.3 Las 4 filas fantasma de `pagos.csv`

`scripts/limpiar_pagos_fantasma.py --aplicar`. Eran filas que **nadie podía ver**: sin una
de las dos fechas, `get_payments()` las descarta y desaparecen del dashboard y de la
pantalla de Variables a la vez, así que el usuario no podía borrarlas desde la UI.

```
26.000,00  Inversiones_Mias           sin inicio, fin 2024-03-28
10.100,00  Inversiones_Uni            sin inicio, fin 2024-05-29
   647,00  Inversiones_Madre          inicio 2025-12-22, SIN FIN   ← la mina
  −600,00  Inversiones para corregir  sin inicio, fin 2025-03-21   (Mis Depositos)
```

Ninguna afectaba a un número —`TOTAL` es −875,83 antes y después— pero la de 647 era una
mina: `_apply_fixed_payment` ignora las que no tienen inicio (`if not start: return`), pero
**una con inicio y sin fin se aplicaría para siempre** en cuanto alguien arregle el
`dropna` de `get_payments()`.

**Hubo que borrar por índice de fila, no por id**: `pagos.csv` tenía el id
`1a2b3c4d-…` **repetido en dos filas** (una visible de 6.675 de `Uni` y la fantasma de
−600), y `delete_payment()` hace `df[df['id'] != id]` — habría borrado las dos. Ese bug de
la capa de Variables **sigue sin arreglar**; ver §7.7.

`pagos.csv` queda con 213 filas y **0 invisibles**.

### 2.4 Dos bugs que el handoff anterior daba por buenos

- **`GET /api/investments/neutralization/preview` respondía 500, no 200.**
  `get_neutralization_preview` nunca se exportó de `services/investments/__init__.py`, y la
  ruta lo llama a través del paquete. Ya está exportado.
- **Y una vez exportado, seguía en 500 al serializar.** `pagos_actuales()` devolvía
  `nota: NaN`. `read_csv` promete convertir los NaN a `None`, pero lo hace con un `.apply`
  que la inferencia de dtype deshace: en una columna de notas enteramente vacía —que pandas
  infiere `float64`— el NaN vuelve. Y `nan` es *truthy*, así que el `or ''` no lo atrapaba.
  Resuelto con `_texto()` dentro de `neutralizacion.py`. **La debilidad de `read_csv` sigue
  ahí** y puede morder a cualquier otro consumidor (§9).

### 2.5 Tests

`tests/test_investment_neutralizacion.py` (42), `tests/test_investment_patrimonio.py` (25)
y `tests/test_investment_flujos.py` (25). La suite completa pasa de 15.084 a **15.176
verdes**, con los mismos 3 fallos ajenos de antes (§7).

### 2.6 Fase 6 — la previsualización (de la sesión anterior)

`services/investments/neutralizacion.py` deriva los pagos fijos desde las posiciones y los
compara contra los escritos a mano.

**La cuenta central:**

```
residual(t) = saldo_inicial + Σ (retiro + interés − aporte − retención − comisión)
```

El residual es la plata de inversión del portafolio que **no** está dentro de un
certificado. Entre dos eventos es constante, y ese tramo constante es exactamente un
pago fijo. Los signos se importan de `metricas.SIGNO` (una sola definición).

**Cuatro decisiones de diseño que hay que conocer antes de tocar el archivo:**

1. **La semántica es la del dashboard, no la del CSV.**
   `VirtualItemsProcessor._apply_fixed_payment` aplica `start <= FECHA < end` y
   **descarta los pagos sin `start_date`** (`if not start: return`). Hay 2 filas así en
   los datos reales (26.000 de `Mias`, 10.100 de `Uni`): existen en el CSV y no hacen
   nada. `pagos_actuales()` lee el CSV crudo a propósito para poder mostrarlas marcadas
   con `aplica=False` — `InterpolationStorage.get_payments()` las descarta antes.

2. **El aporte de una posición sin `fecha_apertura` no cuenta para el residual.**
   Son las sembradas a mano (abiertas antes de que empiece el historial, 2024-03-12). Su
   aporte lleva una fecha estimada que existe solo para que las métricas tengan capital,
   pero esa plata nunca estuvo suelta en la ventana visible: ya estaba dentro del
   certificado. Contarla hundía el residual de `Madre` 12.854 durante siete meses.

3. **`saldo_inicial_sugerido` = la diferencia del primer día**, no la mediana ni el valor
   más repetido. Es la definición literal de saldo inicial: lo que el escalón actual ya
   valía antes de que ocurriera nada derivable. El "valor más repetido" fallaba en
   `Madre`, donde disfrazaba de siembra un descuadre real de 3.533.

4. **Dos tolerancias.** `TOLERANCIA = 0.01` (centavo) y `TOLERANCIA_REDONDEO = 2.0`. Los
   pagos a mano están redondeados a enteros (27.897 donde el banco dice 27.897,57), así
   que una diferencia de un par de dólares es redondeo del usuario, no error del
   generador. `dias_materiales` y `cuadra` usan la segunda.

**`preview()` hace dos pasadas:** la primera detecta el saldo inicial de cada portafolio;
la segunda regenera ya con esos saldos puestos y es la que se reporta. Sin esa
separación, la pantalla confunde "falta configurar una constante" con "la contabilidad no
coincide".

`GET /api/investments/neutralization/preview` — solo lectura. Devuelve `global`,
`por_portafolio`, `pagos_generados`, `pagos_actuales` y `resumen`.

`components/investments/NeutralizationTab.tsx` — quinta pestaña de Inversiones. El
gráfico usa el lenguaje del de *Rendimiento de Inversiones* que ya existía: escalón
actual (cyan) contra generado (violeta punteado), área rosa de diferencia en eje
secundario, y **cada pago generado como barra horizontal ámbar a su altura**. Debajo:
tramos descuadrados, y las dos listas de pagos lado a lado.

El eje arranca en el primer evento real (hay filas con fecha centinela del año 2000 que
estirarían veinte años de línea plana) con `dataZoom` para explorar hacia atrás.

---

## 3. El diagnóstico sobre los datos reales

Esto es lo que la pantalla dice **hoy, antes de sembrar las salidas de §7.2**. La causa
de cada número está en §2.0; se deja aquí para poder comparar contra el después.

| portafolio | pagos a mano → generados | siembra sugerida | días con descuadre real | desvío máx. |
|---|---|---|---:|---:|
| `Inversiones_Mias` | 13 → 14 | **26.000,00** | 17 de 1.320 | 27.066,42 |
| `Inversiones_Uni` | 12 → 12 | **3.177,00** | 878 de 9.721 | 14.127,67 |
| `Inversiones_Madre` | 7 → 8 | **−0,84** | 633 de 657 | 13.335,05 |

**Interpretación, portafolio por portafolio:**

- **`Mias` reproduce la contabilidad.** Con la siembra de 26.000, las diferencias en todo
  el historial son de **±1,38** (el redondeo a enteros del usuario). Los únicos 17 días
  descuadrados son del **2026-07-27 a hoy**: el generador ya sabe que el CDT de 27.000
  cerró y `pagos.csv` todavía no lo tiene escrito. **No es un fallo del generador, es
  información que le falta al CSV.**

- **`Uni` tiene descuadres reales** de miles de dólares en cuatro tramos largos
  (2024-06-04→2024-09-03, 2024-11-18→2025-03-18, 2025-04-28→2025-09-24,
  2025-10-24→2026-03-18). Ya se sabía que su cadena no cierra al centavo (hay un ajuste
  viejo a mano de 3,23), pero esto es mucho más grande. Hay que revisarlos uno por uno.

- **`Madre` tiene dos huecos grandes**: 3.533 durante 2024-11-18→2025-06-16 (al abrir el
  CDT de 10.003 el usuario dio por consumidos los 13.536 completos) y 13.335 desde
  2026-03-02 (el generador dice que `Madre` acumuló ~14k de residual y el CSV dice 647).

**Ninguno de estos números se resuelve solo.** Son preguntas de contabilidad para el
usuario, y esa es exactamente la función de la pantalla.

---

## 3.1 Qué depende todavía de `pagos.csv`

**Decisión del usuario (2026-08-12): `pagos.csv` se retira y este módulo lo reemplaza.**
Todo lo que hoy se deduce de él tiene que poder configurarse a mano. Verificado vaciando
`pagos.csv` sobre una copia: el módulo **no se rompe** —portafolios, posiciones, resumen,
timeline y conciliación siguen funcionando y la asignación a mano también—. Lo que se
pierde es solo lo deducido.

| dependencia | qué hace hoy | qué la reemplaza |
|---|---|---|
| `portafolios.sugerir()` (`portafolios.py:99`) | infiere de quién es cada CDT | **ya está**: se elige a mano en Conciliación (selector por fila) y en la fila de cualquier posición guardada. Sin pagos simplemente no hay sugerencia — probado: 14 posiciones, 0 sugerencias, cero errores |
| `saldo_inicial_sugerido()` | deduce el residual de partida de cada portafolio | la columna **`saldo_inicial` de `grupos.csv`**, que ya existe y `_con_saldo_inicial()` ya lee. Falta el campo en la GUI → **acción futura**, §7.5 |
| `pagos_actuales()` (`neutralizacion.py:296`) | lee el CSV crudo para comparar | **desaparece con la fase 6**: es la propia herramienta de migración. Cuando no haya `pagos.csv` que comparar, la pantalla ya cumplió su función |

Ojo: `posiciones.py` llama varias veces a `InterpolationStorage`, pero esas son a
**`grupos.csv`** (listar portafolios, validar que existan, leer `saldo_inicial`), que no se
retira: los portafolios siguen viviendo ahí como metadatos.

---

## 4. Mapa de archivos

### Backend

```
contabilidad/backend/
  services/investments/
    __init__.py          re-exporta todo lo público del paquete
    detector.py          empareja aperturas↔cierres sobre el extracto (solo lectura)
    posiciones.py        CRUD de dominio, derivados, reconcile(), split, summary, timeline
                         + registrar_flujo() y residual_portafolio()
    portafolios.py       infiere de qué portafolio es cada posición desde pagos.csv
    metricas.py          XIRR, TNA ponderada, capital-día, devengo, resumen, timeline
    neutralizacion.py    genera los pagos fijos y los compara (NO escribe)
    patrimonio.py        capital propio vivo por día → NOTIONCUM (fase 5)
  storage/investments_storage.py    posiciones.csv + movimientos.csv
  storage/variables_storage.py      +columnas es_inversion y es_custodia en grupos.csv
  storage/transformations/dashboard_transforms.py   +transform_investment_capital
  storage/data_pipeline.py          +transformación 'capital_invertido'
  services/dashboard_service.py     TOTAL_CON_INVERSIONES + el flag de la respuesta
  models/investment_models.py       pydantic de posiciones, movimientos, split, apply
  routes/investments.py             todos los endpoints
  routes/dashboard.py               ?incluir_inversiones en chart-data y variations
```

### Frontend

```
contabilidad/pagina/src/
  pages/Investments.tsx                     shell + 5 pestañas
  components/investments/
    shared.tsx              fmt/money/pct, KpiCard, Badge, Section, Spinner
    PositionsTab.tsx        tabla maestra, fila expandible, captura de plazo/tasa
    SummaryTab.tsx          KPIs con selector propio/custodia/todo, por portafolio, por año
    EvolutionTab.tsx        área de capital + interés acumulado, dispersión de TNA
    ReconcileTab.tsx        diff del detector con sugerencias de portafolio
    NeutralizationTab.tsx   fase 6 en previsualización
  services/investments.ts   cliente + tipos
  components/Sidebar.tsx    entrada 'inversiones' entre Fondos y Variables
  App.tsx                   ruta 'inversiones' + el toggle "Con inversiones" del dashboard
  hooks/useDashboard.ts     incluirInversiones en la queryKey de las dos consultas
  components/DashboardChart.tsx / VariationsChart.tsx   reciben el flag por prop
```

### Datos

```
data/sistema/inversiones/
  posiciones.csv    19 filas
  movimientos.csv   ~60 filas
```

27 posiciones = **10 flujos** (`flujo-*`, §2.0) + **17 plazos fijos**. De esos 17: 2
sembrados a mano (`siembra-*`, abiertos antes de que empiece el historial) + 15 filas que
representan los 14 certificados del banco — el CDT de 38.000 está repartido en 2 hermanas.
Las hermanas comparten `tx_apertura_id` y la reconciliación las suma para comparar contra
el banco, por eso el detector sigue reportando 14 iguales y 0 sobrantes.

Ya no hay ninguna posición de tipo `ajuste`: las 2 que había contaban plata dos veces
(§2.0). El tipo sigue existiendo en el modelo por si hace falta.

---

## 5. Endpoints

| método | ruta | qué hace |
|---|---|---|
| `GET` | `/api/investments/positions` | posiciones con derivados; filtros `portafolio_id`, `estado`, `tipo` |
| `POST` | `/api/investments/positions` | crear (valida tipos, fechas, portafolio) |
| `GET/PUT/DELETE` | `/api/investments/positions/{id}` | leer / editar / borrar |
| `POST` | `/api/investments/positions/{id}/split` | repartir un certificado entre portafolios |
| `GET` | `/api/investments/portfolios` | grupos que hacen de portafolio |
| `GET` | `/api/investments/summary` | KPIs globales, propio/custodia, por portafolio, por año |
| `GET` | `/api/investments/timeline` | serie diaria de capital e interés + eventos |
| `POST` | `/api/investments/detect` | diff contra el banco **sin escribir**, con sugerencia de portafolio |
| `POST` | `/api/investments/detect/apply` | confirma el diff (nunca pisa `origen='manual'`) |
| `POST` | `/api/investments/flows` | registra plata que entra o sale del portafolio |
| `GET` | `/api/investments/flows/preview` | residual antes/después, **sin escribir** |
| `GET` | `/api/investments/neutralization/preview` | fase 6 **sin escribir** |
| `GET` | `/api/investments/from-accounts` | legado, delega en el detector |
| `GET` | `/api/investments/chart-data` | legado (saldo vs inversión) |
| `GET` | `/api/dashboard/chart-data?incluir_inversiones=` | patrimonio con o sin el capital invertido |
| `GET` | `/api/dashboard/variations?incluir_inversiones=` | **el mismo valor que el anterior** |

---

## 6. Decisiones del usuario (no derivables del código)

1. **El patrimonio por defecto NO incluye el capital invertido.** Toggle opt-in, como
   parámetro de API y no switch de vista (porque `VariationsChart` descompone `diff_total`
   y descuadraría).
2. **`Inversiones_Uni` e `Inversiones_Madre` son custodia**: se siguen igual que las demás
   pero **nunca** suman al patrimonio propio. El único propio es `Inversiones_Mias`.
   Implementado con `es_custodia` en `grupos.csv`.
3. **`Mis Depositos` se queda en Variables** con sus pagos fijos a mano. No entra al
   módulo; la corrección de −600 no se siembra.
4. **Los 647 de `Madre` son uno solo y cerrado** (2025-12-22 → 2026-03-02).
5. **El plazo pactado se captura en la UI** (fila expandible de cada posición). Sin él, la
   TNA mostrada es calendario/365; con él aparece la que el banco liquidó (plazo/360).
6. **El portafolio se infiere de `pagos.csv`**, no se pide a mano.
7. **Los pagos fijos se migrarán**, pero con corte en sombra y test de equivalencia sobre
   la función escalón. Nada de migrar a ciegas.

### Abiertas

- ¿`Inversiones_Uni` tiene meta (monto objetivo, fecha de matrícula)? Habilitaría una
  vista de progreso como en Fondos.
- ¿Se quita `es_inversion`? Solo sirve para que un portafolio nuevo y vacío aparezca en la
  UI; en cuanto tiene una posición, `list_portfolios()` lo encuentra igual.

---

## 7. Lo que falta

> Ordenado por valor. Los tres primeros no necesitan ninguna decisión del usuario.

### Lo que falta, en orden

1. **Los 12,59 de `Uni`.** Son 8–12 dólares en tres tramos largos, y salen todos del mismo
   sitio: la posición sembrada `siembra-uni-2024-05-29` no cierra al centavo
   (10.100 + 172,21 − 3,44 = 10.268,77, pero el CDT siguiente pide 10.278 → faltan 9,23).
   Están por encima de `TOLERANCIA_REDONDEO = 2,0`, así que la pantalla dice «no cuadra».

   **No lo tapes subiendo el umbral.** Las dos salidas honestas son: averiguar de dónde
   salieron esos 9,23 y registrarlos como `flujo` de entrada el 2024-06-04, o corregir el
   capital/interés de la siembra si resulta que el dato estaba mal. Hace falta preguntarle
   al usuario; son 9 dólares, no corre prisa.

2. **Capturar plazo y tasa pactados**: 0 de 17 plazos fijos los tienen. Sin ellos la TNA que
   se muestra es calendario/365 en vez de la que el banco liquidó (plazo/360) — la
   diferencia real medida es 2,94 % contra 3,00 %. El campo ya está en la UI (fila
   expandible de cada posición); solo falta llenarlo.

3. **Quitar la dependencia de `pagos.csv`** — ver §3.1 para el inventario y §7.5 para la
   única pieza que falta construir (el `saldo_inicial` en la GUI).

4. **Fase 6 — el corte**, ver más abajo.

### Preguntas abiertas para el usuario

Ninguna bloquea nada, pero hasta que se respondan el dato queda con una nota al pie:

- **¿Los 3.533,84 que salen de `Madre` el 2024-11-18 y los 3.635,07 que entran a `Uni` ese
  mismo día son el mismo dinero?** Difieren en 101,23. Puede ser un traspaso entre los dos
  portafolios en vez de dos hechos sueltos. Numéricamente el par sembrado da igual; si es
  un traspaso conviene anotarlo como tal.
- **¿De dónde salieron los 9,23 de `Uni`?** (§7.1)
- **Nadie ha visto la página renderizada.** No hay navegador conectado en estas sesiones.
  Verificado: `tsc -b --noEmit` y `npm run build` limpios, y los 13 endpoints responden 200
  con los datos reales (§8). El render en sí no está confirmado — si tienes navegador,
  ábrela y míralo.

### Acciones futuras (pedidas por el usuario, no construidas)

5. **Configurar el `saldo_inicial` de cada portafolio desde la GUI.** Hoy se deduce de
   `pagos.csv` (§3.1); cuando ese archivo se retire no habrá de dónde. **El modelo ya está
   listo**: `grupos.csv` tiene la columna `saldo_inicial`, `_con_saldo_inicial()` la lee y
   `InterpolationStorage.update_group()` la escribe — probado de punta a punta.

   Falta: un input en la UI (el sitio natural es la cabecera de cada portafolio en Resumen)
   y **una regla de precedencia en `neutralizacion.preview()` y en
   `posiciones.residual_portafolio()`**: si el grupo tiene `saldo_inicial` configurado, se
   usa ése; solo si está vacío se deduce. Hoy la deducción siempre gana, y por eso no se
   cambió ahora: alteraría los números que la pantalla está reportando.

   El usuario pidió explícitamente dejarlo anotado y **no** construirlo todavía.

### Fases

6. **Fase 6 — el corte.** Cuando los descuadres se expliquen: generar en grupos sombra
   (`type='shadow'`, que `VirtualItemsProcessor` ignora), verificar que la serie coincide,
   y en **una sola operación** pasar los sombra a `fixed` y vaciar los originales.
   Respaldo en `.bak` antes de tocar nada.

### Aparte del módulo

7. **`pagos.csv` tiene ids repetidos y `delete_payment()` borra por id.**
   `1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d` estaba en dos filas distintas, y
   `delete_payment()` hace `df[df['id'] != id]` — o sea que borrar una se habría llevado
   la otra por delante. Al limpiar las fantasma hubo que operar **por índice de fila**
   (`scripts/limpiar_pagos_fantasma.py`). **Sigue sin arreglarse**: `create_payment()` no
   valida unicidad y `delete_payment()`/`update_payment()` siguen siendo por id. Es un bug
   real de la capa de Variables, con potencial de borrado silencioso.
8. **`get_payments()` esconde filas que existen.** Hace
   `dropna(subset=['id','group_id','amount','start_date','end_date'])`, así que a una fila
   le basta con no tener *una* de las dos fechas para desaparecer del dashboard **y** de la
   pantalla de Variables — el usuario no la ve y por tanto no puede borrarla, pero sigue en
   el CSV. Había 4 así y ya están borradas (§2.3), pero la UI seguirá escondiendo cualquier
   fila futura con el mismo defecto. Lo sano sería listarlas marcadas como inválidas.
9. **`read_csv` no limpia los NaN como dice.** `variables_storage.read_csv` promete
   convertirlos a `None`, pero usa `df[col].apply(lambda x: None if pd.isna(x) else x)` y
   en una columna que pandas infirió `float64` —cualquier columna de texto enteramente
   vacía— el `None` se re-infiere y el NaN vuelve. Eso es lo que hacía 500 al endpoint de
   neutralización. Se arregló **localmente** en `neutralizacion._texto()`; la función
   compartida sigue igual porque tocarla afecta a todos los lectores de `grupos.csv` y
   `pagos.csv`. Vale la pena arreglarla de raíz, con su test.
10. Tres tests fallan desde antes de todo este trabajo:
   `test_data_pipeline::test_pipeline_tarjeta_discrepancia_meses_unidos`,
   `test_pipeline_tarjeta_discrepancia_procesada_unidos` y
   `test_flujo_usuario::test_flujo_completo_usuario`. Son de la ruta de tarjeta y del
   procesamiento de fuentes.

---

## 8. Cómo correr y probar

**El venv del backend es `contabilidad/backend/.venv`** (pandas 3.0.1, uvicorn, supabase,
lxml). Existe también un `.venv_diag` incompleto — no sirve para la suite entera.

```bash
# app completa
./contabilidad/start_contabilidad.sh

# solo backend
contabilidad/backend/.venv/bin/python -m uvicorn contabilidad.backend.main:app --reload --port 8000

# tests del módulo (256, todos verdes)
contabilidad/backend/.venv/bin/python -m pytest \
  tests/test_investment_posiciones.py tests/test_investment_metricas.py \
  tests/test_investment_detector.py tests/test_investment_neutralizacion.py \
  tests/test_investment_patrimonio.py tests/test_investment_flujos.py \
  tests/test_routes_investments.py -q

# suite completa: 15.176 pasan, 3 fallan (ajenos, ver §7.10)
contabilidad/backend/.venv/bin/python -m pytest -q

# frontend
cd contabilidad/pagina && npx tsc -b --noEmit && npm run build
```

**Verificación rápida por API.** Levantar el backend **en un puerto propio** (ver §9) y no
en el 8000, que suele ser el del usuario:

```bash
contabilidad/backend/.venv/bin/python -m uvicorn contabilidad.backend.main:app --port 8123

curl -s -X POST localhost:8123/api/investments/detect | jq .resumen
# esperado: nuevas 0, huerfanas 0, iguales 14

curl -s localhost:8123/api/investments/neutralization/preview | jq .resumen
# esperado: siembra_total 29176.16, dias_materiales 878, cuadra false

# El invariante de la fase 5: el TOTAL con el toggle apagado es el de siempre.
for f in false true; do
  curl -s "localhost:8123/api/dashboard/chart-data?incluir_inversiones=$f" \
    | jq -c '[.data[] | select(.date=="2026-02-01")] | .[0] | {date,total,notion}'
done
# esperado: total -99.61 / 28204.39, notion 28304 en las dos
```

**Reversa de los flujos sembrados**: cada uno lleva id fijo (`flujo-uni-*`, `flujo-madre-*`),
así que se deshacen con precisión y sin heurísticas:

```bash
python scripts/sembrar_flujos_inversion.py --preview    # qué hay y qué falta
python scripts/sembrar_flujos_inversion.py --rehacer    # borra los 10

python scripts/limpiar_ajustes_redundantes.py --preview # los 2 ajuste borrados
```

`limpiar_ajustes_redundantes.py` **no tiene `--rehacer` a propósito**: recrearlos exigiría
volver a ponerlos en el script de siembra, que es justo lo que no queremos. Si hiciera
falta, están en sus `.bak` y en el historial de git del script de siembra.

**Reversa de todo el módulo**: borrar `data/sistema/inversiones/` y restaurar `grupos.csv`
desde su `.bak`. Nada más se tocó.

---

## 9. Trampas conocidas

- **No mates procesos por patrón.** `pkill -f "uvicorn contabilidad.backend.main"` mata
  también el backend que el usuario tenga corriendo. Cuando eso pasa, Vite devuelve
  **500** en todas las llamadas (su proxy convierte "connection refused" en 500) y parece
  un bug del backend. Usar PIDs exactos.
- **pandas 3 no deja escribir un int en una columna de dtype `str`.** Por eso
  `investments_storage.py` lee y escribe listas de diccionarios y solo usa pandas para el
  CSV: fuera son tipos de Python, dentro es texto, en el medio no hay dtypes.
- **Los tests no pueden leer `data/`.** Todo va contra `tmp_path` parcheando
  `BASE_DATA_PATH`, `POSITIONS_FILE`, `MOVEMENTS_FILE`, `GROUPS_FILE` y `PAYMENTS_FILE`.
  El historial bancario real que usa `test_investment_detector.py` está copiado como
  literal dentro del propio test.
- **`InterpolationStorage.get_payments()` descarta las filas sin `start_date`.** Si hace
  falta verlas (como en la neutralización), hay que leer el CSV crudo.
- **`read_csv` deja NaN en las columnas de texto vacías**, y `nan` es *truthy*: un
  `campo or ''` no lo atrapa y FastAPI revienta al serializar con "Out of range float
  values are not JSON compliant". Ver §7.6.
- **`Col` es un `(str, Enum)`, no un `StrEnum`.** `df[Col.X] = ...` funciona para buscar,
  pero deja el miembro del enum dentro del Index y el encabezado del CSV sale `Col.X`.
  Al escribir columnas, usar `Col.X.value`.
- **El flag `incluir_inversiones` tiene que ir igual en `/chart-data` y en `/variations`.**
  Si no, el desglose diario se contrasta contra un total que no es el suyo y la diferencia
  aparece como "sin explicar".
