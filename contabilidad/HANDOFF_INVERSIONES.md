# Handoff — Módulo de Inversiones

Estado al 2026-08-12; **revisado y contrastado contra el código y los datos el 2026-08-13**
(conteos, referencias cruzadas y estado del corte). Rama `enriquecimiento-horas`. Este documento es para retomar el
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
| 6 | Migración de pagos fijos | ✅ **CORTADA** (2026-08-12, autorizada por el usuario) |

**Las seis fases están hechas.** Los pagos fijos de inversiones ya no se escriben a mano:
los genera el módulo desde las posiciones.

### Empieza por aquí

**El corte se aplicó el 2026-08-12.** 30 pagos a mano vaciados, 3 grupos generados
activados. Estado: `cortado: sí`, y `pagos_actuales = 0` en la neutralización.

Antes de cortar, los tres portafolios cuadraban por debajo de la tolerancia:

| portafolio | días que cambian | desvío máx. | |
|---|---:|---:|---|
| `Inversiones_Mias` | 566 | 1,38 | ✅ cuadra |
| `Inversiones_Uni` | 562 | 1,33 | ✅ cuadra |
| `Inversiones_Madre` | 469 | 1,24 | ✅ cuadra |

Dos cosas lo desbloquearon, y las dos importan:

1. **El usuario corrigió los dos pagos de `Uni` de 2024** (10.272 → 10.269 y 7.258 → 7.255
   en `pagos.csv`): eran el «ajuste a mano viejo» que menciona §3, y con eso todo 2024 quedó
   limpio.
2. **La tolerancia estaba en la unidad equivocada** — ver §2.8. No se movió la vara; se
   aplicó donde corresponde.

**Lo que el corte movió de verdad, medido después sobre el dashboard**: 677 días de los 944
del gráfico, mediana de 0,75, **máximo 3,40** — exactamente lo que `--verificar` había
predicho. El cambio va hacia el número del banco, así que el patrimonio histórico quedó más
exacto, no menos.

**El respaldo NO está en los `.bak`.** Son rodantes —cada escritura los pisa con la versión
inmediatamente anterior— y a día de hoy `pagos.csv.bak` y `grupos.csv.bak` ya son
post-corte: 0 pagos en los tres portafolios originales y los grupos generados en `fixed`.
Los 30 pagos a mano de antes del corte sobreviven **solo en git**, en el commit `77ac01f`:

```bash
git show 77ac01f:data/sistema/interpolaciones/pagos.csv   # 13 Mias + 11 Uni + 6 Madre
```

El procedimiento de reversa completo está en §8.

~~**La pestaña de Neutralización ahora dice «683 de 806 días descuadrados» y eso es
correcto**~~: decía eso porque ya no hay pagos a mano contra los que comparar, así que
comparaba contra cero. Cumplió su función y **se retiró el 2026-08-14** (§2.15, §7.3); el
backend sigue en pie porque el corte depende de él.

Lo que queda, en orden de valor: capturar los 2 plazos que no se pueden deducir (§7.1),
decidir cuándo se borra `pagos.csv` del todo (§3.1, §7.2) y **darle un disparador a
`regenerar()`** (§7.5) — hoy hay que acordarse de correrlo a mano cada vez que entra un
certificado nuevo, y si no se hace el patrimonio se queda atrás sin avisar.

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

> **Ya no aplica** (2026-08-12, noche): el usuario corrigió los dos pagos a mano de `Uni`
> (10.272 → 10.269 y 7.258 → 7.255) y esos tramos desaparecieron. Los tres portafolios
> cuadran por debajo de la tolerancia. Ver «Empieza por aquí» y §2.8.

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
y `tests/test_investment_flujos.py` (25).

La sesión del 2026-08-12 (noche) añadió 75: la unidad de la tolerancia y el permiso de
`es_inversion` en `test_investment_corte.py`, la inferencia de plazo/tasa y la precedencia
del saldo inicial en `test_investment_posiciones.py`, los tres bugs de §7.7–7.9 en
`test_variables_storage.py`, y **`tests/test_pagos_sin_fecha.py`** entero (§2.11), que es el
que garantiza que el dashboard y la neutralización sigan midiendo la misma ventana.

**Medido el 2026-08-13**: los 10 archivos del módulo dan **380 verdes** (317 antes de
`test_investment_analisis.py`, §2.14), y la suite completa
**15.298 pasan / 3 fallan**, los tres ajenos de siempre (§7.10). Si un recuento de tests de
este documento no cuadra, vuelve a correrlo: es el número que más rápido envejece.

Siete tests de la sesión anterior fijaban la regla contraria («un pago sin inicio no
aplica», «un tramo abierto se escribe con centinela»). Se reescribieron para la regla nueva
conservando en el docstring por qué existía la vieja: son cambios de decisión, no
regresiones, y dentro de un mes eso no se distingue si no está escrito.

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

### 2.7 Fase 6 — la maquinaria del corte

`services/investments/corte.py` + `scripts/corte_inversiones.py`. Tres pasos separados, y
solo el último escribe sobre lo que el dashboard lee:

```bash
python scripts/corte_inversiones.py --estado      # dónde está
python scripts/corte_inversiones.py --sombra      # crea los grupos `shadow`  (aditivo)
python scripts/corte_inversiones.py --verificar   # compara las dos series    (no escribe)
python scripts/corte_inversiones.py --cortar      # EL CORTE (pide confirmación)
python scripts/corte_inversiones.py --limpiar     # borra la sombra
```

**Estado actual: el corte ya se aplicó y no queda sombra.** `--estado` dice `cortado: sí`,
0 pagos propios y 0 sombra en los tres portafolios, y 14 / 12 / 9 pagos en los grupos
generados, que hoy son `fixed`. Los pasos `--sombra`, `--verificar` y `--cortar` quedan
documentados porque describen la maquinaria, **no porque haya nada pendiente que correr**:
la operación de todos los días es `--regenerar` (§2.13).

Mientras existió, la sombra **el dashboard no la veía** — verificado: `PAGOS_FIJOS`,
`SALDO` y `TARJETA` idénticos antes y después, porque `VirtualItemsProcessor` solo aplica
`fixed` e `interpolated`. Si algún día vuelven a aparecer grupos `Pagos Inversiones_*`
duplicados en la pantalla de Variables, son eso; `--limpiar` los quita.

**El corte tiene freno de mano.** `aplicar_corte()` corre `verificar()` primero y **se
niega** si algún portafolio se movería más que `TOLERANCIA_CORTE = 2,0`, salvo
`forzar=True`. Se aplicó sin forzar: los tres cuadraban (1,38 / 1,33 / 1,24). El 3,40 que
este documento citaba como bloqueante era el **agregado**, que no es el criterio — §2.8.

**El orden del corte importa**: primero se vacían los originales y después se activan los
sombra. Al revés habría un instante con las dos series aplicándose y el patrimonio
duplicado; así el peor caso intermedio es un instante sin ninguna.

**No hay endpoint POST para cortar, a propósito** — una operación que reescribe el
patrimonio histórico no debería estar a una llamada de distancia. Sí hay
`GET /cut/status`, `POST /cut/shadow`, `DELETE /cut/shadow` y `GET /cut/verify`.

**Una trampa que el test encontró:** cuando se escribió el generador, un tramo abierto **no
se podía dejar con `end_date` vacío** —`get_payments()` lo descartaba y el pago quedaba
invisible, el mismo defecto de las filas fantasma de §2.3—, así que se usó
`FECHA_CENTINELA = '3000-01-01'`. **Desde §2.11 la celda vacía ya significa «para
siempre»**, y `regenerar()` escribe el hueco; las centinela viejas siguen siendo válidas
porque `_es_centinela()` las trata igual.

---

### 2.8 La tolerancia del corte estaba en la unidad equivocada

**Diagnóstico que estuvo mal escrito durante toda una sesión.** El handoff decía que el
corte movería «3,40 como mucho, en 25 días de 2024, y céntimos en el resto». Medido: eran
**276 días** por encima del umbral, de 2024-05-29 a 2026-02-22, con un bloque continuo de
2025-06 a 2026-02 que el documento no mencionaba. El error venía de mezclar los *días
materiales* de la neutralización (una medida por portafolio) con el impacto del corte (una
medida agregada). Si un número de este handoff parece redondo, vuelve a medirlo.

Y una vez medido bien, se ve el fallo real: `TOLERANCIA_CORTE = 2,0` representa **el
redondeo a enteros de un portafolio**, pero `verificar()` la contrastaba contra la **serie
agregada**, que suma los tres. El día peor, 2025-09-25:

```
Inversiones_Mias   +1,09
Inversiones_Uni    +1,07
Inversiones_Madre  +1,24
                   ─────
agregado            3,40   ← comparado contra una vara calibrada para uno solo
```

Ninguna contabilidad estaba mal: eran tres redondeos independientes apilándose. **La vara
no se movió** —sigue en 2,0— y ahora se aplica portafolio por portafolio, que es su unidad.
El agregado se sigue calculando y mostrando, porque es el impacto real sobre el patrimonio
y es lo que el usuario firma al cortar, pero no es el criterio.

Está fijado en `tests/test_investment_corte.py`: tres portafolios con 1,4 / 1,3 / 1,2 no
bloquean el corte, y uno solo con 40 sí lo bloquea.

### 2.9 Plazo y tasa pactados: no hacía falta pedirlos

Los 17 plazos fijos tenían **0 plazos capturados**, así que `tna_pactada` no se podía
calcular para ninguno. Resulta que se deducen de los datos que ya había:

- **El banco liquida actual/360 y cancela a vencimiento**, así que el plazo pactado son los
  días calendario entre apertura y cierre.
- Despejando la tasa de `interes = capital · tasa · plazo/360`, las **15 posiciones con
  apertura caen en un múltiplo exacto de 0,05 %**: 8,70 / 7,95 / 4,80 / 6,60 / 6,50 / 5,80
  / 5,50 / 5,30 / 4,75 / 2,90 / 3,55… Con base 365 no cae ninguna, y **eso** es lo que
  identifica la convención. El interés recalculado se separa del real **0,0053 USD** en el
  peor caso.

`posiciones.inferir_plazo_y_tasa()`. La comprobación es el propio interés: si redondear al
peldaño no reproduce lo que pagó el banco al centavo, no se devuelve nada. Un dato
capturado a mano **siempre** manda sobre la deducción, y `plazo_es_inferido` viaja en la
vista para que la UI diga cuál está mostrando («121 días (deducido)»).

**Las 2 siembras no se pueden deducir** y no es un fallo: sin `fecha_apertura` hay una
ecuación y dos incógnitas. Para `siembra-uni` (10.100 con 172,21) encajan igual de bien 62
días al 9,90 %, 93 al 6,60 %, 186 al 3,30 %… Esas dos siguen necesitando el certificado.

### 2.10 El saldo inicial ya se configura desde la GUI

Era la pieza que faltaba para poder retirar `pagos.csv`. Resumen → **Saldo inicial
por portafolio**, con `PUT /api/investments/portfolios/{id}/saldo-inicial`.

**Lo que costaba trabajo era distinguir «sin configurar» de «configurado en cero»**, porque
`_normalize_group` colapsaba los dos a `0.0`. Ahora viaja `saldo_inicial_configurado` al
lado, y la regla de precedencia es la misma en `neutralizacion.preview()` y en
`posiciones.residual_portafolio()` —tiene que serlo, o el formulario de flujos y la pestaña
de Neutralización mostrarían números distintos del mismo día—.

Dos cosas que salieron a la luz al implementarlo:

- **`create_group` escribía `saldo_inicial = 0.0`** en todo grupo nuevo, o sea que todos
  nacían «configurados en cero». Ahora nace vacío.
- **pandas 3 no deja escribir un hueco en una columna `float64`**, y vaciar la celda es
  justamente la operación que devuelve el portafolio a la deducción. `update_group` pasa la
  columna a `object` cuando el valor es vacío.

Con nada configurado —el estado de hoy— la deducción sigue ganando y los números no se
movieron: 26.000 / 3.177 / −0,84, igual que antes.

### 2.11 Un pago puede no tener fecha de inicio, o de fin, o ninguna

Pedido del usuario (2026-08-12): «hay algunos pagos que no tienen inicio ni fin, pero
actualmente se pone una fecha de referencia». Era verdad y era una limitación real:

- `get_payments()` hacía `dropna` sobre las **dos** fechas.
- `_apply_payment` descartaba lo que no tuviera inicio (`if not start: return`).

O sea que para decir «esto vale para siempre» había que inventarse una centinela
(`3000-01-01` en el generador del corte, `2030-01-01` a mano), y una fila a la que le
faltara una fecha desaparecía **a la vez** del dashboard y de la pantalla de Variables: el
usuario no podía borrar lo que no podía ver. Es el origen de las 4 filas fantasma de §2.3.

Ahora la celda vacía **es** el significado:

```
sin inicio → desde siempre          sin fin → para siempre
```

Con una excepción que no es negociable: un grupo **`interpolated` necesita las dos puntas**,
porque son el tramo sobre el que reparte. Sin ellas el pago no haría nada, así que la ruta
lo rechaza con un 400 en vez de guardar una fila muerta.

**Las centinela que ya están escritas siguen valiendo.** `_es_centinela()` trata un año
≥ 2900 igual que un fin ausente, y el `2030-01-01` que el usuario usa sigue siendo una fecha
normal que simplemente queda lejos. No hay que migrar nada.

Lo que había que cuidar es que **las dos implementaciones de la ventana no se separaran**:
`VirtualItemsProcessor._apply_fixed_payment` (lo que el patrimonio ve) y
`neutralizacion._activo` (lo que la pantalla de inversiones mide contra él). Están fijadas
juntas en `tests/test_pagos_sin_fecha.py`, comparando las dos series sobre los cinco casos
de borde. Verificado además contra los datos reales: `PAGOS_FIJOS` no se movió ni un día.

En la UI las dos fechas quedan opcionales solo en los grupos fijos, con la etiqueta
«vacío = siempre», y la lista muestra «desde siempre» / «para siempre» en vez de un hueco.

### 2.12 El traspaso `Madre` → `Uni` del 2024-11-18 — confirmado

Era la pregunta abierta más vieja del módulo. **Sí era un traspaso**, y lo resolvieron las
notas del usuario, no los datos: el extracto no distingue un traspaso interno de dos
movimientos sueltos.

La nota dice, del cierre del CDT de `Madre` el 2024-10-25:

> «Se Quita 3_635 para Uni para mejorar inversion. Se queda con 9901 / Puse 102 para
> completar para la inversion»

y los números cuadran al centavo contra `movimientos.csv`:

```
  13.536,84   devuelve el CDT (12.854,21 de capital + 682,63 de interés)
 −  3.635,07   se van a `Uni`
  ─────────
   9.901,77   «Se queda con 9901»
 +    101,23   «Puse 102» — plata de fuera
  ─────────
  10.003,00   el CDT que se abre el 2024-11-18
```

Eso explica de dónde salía la diferencia de 101,23 que hacía dudar: **no era ruido, era el
aporte propio**. El módulo tenía las dos cosas fundidas en un único flujo neto de 3.533,84
con la nota «Matrícula separada para pagar», que además era falsa.

Ahora son dos flujos, `flujo-madre-2024-11-18` (traspaso) y `flujo-madre-2024-11-18-aporte`
(los 101,23), más la nota corregida en `flujo-uni-2024-11-18`. **El neto es idéntico**
(3.635,07 − 101,23 = 3.533,84), así que la serie no se movió ni un día — se comprobó.

La confirmación independiente es bonita: con el traspaso bien modelado, el residual de
`Uni` el 2024-11-18 aterriza en **0,00 exacto** (6.674,93 + 3.635,07 − 10.310 del CDT). El
bolsillo se vacía justo, que es lo que tiene que pasar si el dinero salió de `Madre`.

### 2.13 Después del corte: `regenerar()`

El corte es de una sola vez; esto es la operación de todos los días. Cuando entra un
certificado nuevo, las posiciones cambian y los pagos generados tienen que seguirlas.

**El camino obvio era destructivo.** `sembrar_sombra()` localiza su grupo por
`fondo_origen` **y** `type == 'shadow'`; tras el corte el grupo generado es `fixed`, así
que dejaba de encontrarlo y creaba un **segundo grupo al lado**. Con los dos vivos, un
`aplicar_corte(forzar=True)` activaba uno sobre otro: medido en sandbox, **10.200 pasaban a
20.400**. `verificar()` lo detectaba y el corte sin `forzar` se negaba, pero eso es la
última red — y forzar es justo lo que se hace cuando «no cuadra por poco». Ahora
`sembrar_sombra()` se niega en seco si algún portafolio ya está cortado.

`corte.regenerar(portafolio_id=None)` reescribe **en su sitio** los pagos del grupo activo.
No crea grupos, así que no puede duplicar nada.

**Aquí no hay sombra ni tolerancia, a propósito.** La sombra existía porque durante la
migración competían dos fuentes y había que validar que dijeran lo mismo; ya solo hay una.
Y la serie **debe** moverse —eso es lo que significa que hubo una inversión nueva—, así que
un umbral que se negara a aplicar el cambio mediría lo contrario de lo que pasa. Lo que sí
hay es previsualización: `previsualizar_regeneracion()` enseña el diff antes de escribir.

**Dos cosas que el corte dejó rotas y que esto tuvo que recuperar**, las dos porque
`preview()` las deducía de los pagos a mano que el corte borra:

- **El `saldo_inicial`.** Sin él el generador arranca de cero y la serie se hunde el importe
  del saldo de partida (26.000 en `Mias`). `regenerar()` **se niega** si el portafolio no lo
  tiene configurado en `grupos.csv`, porque la pérdida sería muda. Los tres ya lo tienen.
- **El arranque del tramo del saldo inicial.** `_arranques_vigentes()` lo recupera del
  primer pago del grupo activo, que es de donde salió la primera vez. Sin eso, la primera
  regeneración se comía el tramo más viejo de cada portafolio — el que nadie mira.

**El invariante que lo hace seguro de correr por rutina es la idempotencia**: regenerar sin
que hayan cambiado las posiciones no mueve la serie ni un día. Verificado sobre los datos
reales — 14/12/9 pagos antes y después, `PAGOS_FIJOS` idéntico en los 944 puntos del
gráfico; lo único que cambia en el CSV son los ids y que el `3000-01-01` pasa a celda vacía.

```bash
python scripts/corte_inversiones.py --regenerar-preview   # qué cambiaría, sin escribir
python scripts/corte_inversiones.py --regenerar           # pide confirmación
```

`GET /api/investments/cut/regenerate/preview` y `POST /api/investments/cut/regenerate`.
Este sí está expuesto por HTTP, al revés que el corte: reemplaza en su sitio, no puede
duplicar y es la operación normal del día a día.

### 2.14 La pestaña de Detalle: el portafolio primero, el certificado después (2026-08-13)

Pedido del usuario: «ver y analizar cada una de mis inversiones, cómo han ido subiendo con
el tiempo, cómo podrá ser en un futuro, cuánto he ganado».

**«Una inversión» es el portafolio, no el certificado**, y esto se construyó primero al
revés. La corrección del usuario: *«me refería a inversión Uni, inversión Mía, esos grupos,
ya que es el mismo dinero, no una por una»*. `Inversiones_Uni` no son doce plazos fijos
sueltos: es el mismo dinero rodando de uno a otro con matrículas saliendo por el camino.
La vista por certificado se conservó **como drill-down**, que es donde tiene sentido.

`services/investments/analisis.py` + dos endpoints
(`/portfolios/{id}/analysis` y `/positions/{id}/analysis`) +
`components/investments/AnalysisTab.tsx`.

**La cuenta del portafolio es una identidad, y por eso se comprueba en vez de creerse:**

```
total(t) = aportado_neto(t) + ganancia(t)
         = (saldo inicial + lo que ya estaba dentro + entradas − salidas) + lo que puso el banco

total(t) = dentro(t) + suelto(t) + devengado(t)     ← las tres capas del gráfico apilado
```

Las dos descomposiciones cierran **todos los días** en los tres portafolios reales (869,
885 y 885 días, verificado). Si un movimiento se contara dos veces, las mitades dejarían de
sumar en el día exacto del fallo — es la red que hace fiable el número grande de la
pantalla, y está fijada en `test_la_identidad_del_portafolio_se_cumple_todos_los_dias`.

**El residual sale de `neutralizacion._eventos_por_portafolio`, no de una fórmula nueva.**
Duplicarla aquí es exactamente cómo se separan dos pantallas que tienen que coincidir
(§9). Lo mismo con el devengo: mismo criterio que `metricas.interes_devengado`.

**El gráfico apilado contesta dos preguntas con una figura**: la altura total es «cuánto
tengo aquí» y el corte entre capas es «cuánto está trabajando». En `Uni` eso enseña algo
que ninguna otra pantalla decía — la plata estuvo parada 292 de 885 días.

**Cómo se dibuja, y por qué así** (el usuario dijo que la primera versión «no se entiende»,
y tenía razón por tres motivos concretos):

1. **Dos `grid` en una sola instancia de echarts, no un eje secundario.** Con dos escalas
   en la misma caja, echarts cuadra los ticks de las dos y el eje izquierdo acababa bajando
   a **−5.000** aunque el portafolio nunca estuvo en negativo. Arriba la plata, abajo la
   ganancia, `min: 0` en los dos. Y una sola instancia —no dos gráficos— porque
   `dataZoom` y `axisPointer` se comparten con `xAxisIndex: [0, 1]`; dos gráficos separados
   se desincronizan en cuanto tocas uno.
2. **`step: 'end'`.** La plata se mueve el día que se mueve; entre dos eventos la cifra es
   constante. La interpolación diagonal dibujaba rampas que sugerían un goteo inexistente.
3. **`itemStyle` explícito en cada serie.** Sin él la bolita de la leyenda sale de la
   paleta por defecto de echarts: la leyenda decía azul/amarillo/gris mientras el gráfico
   pintaba morado/ámbar/verde. Estaba en las dos curvas y es un fallo fácil de repetir.

Lo suelto va en **ámbar y no en gris**: es la plata que existe y no rinde, y sobre fondo
oscuro el gris se perdía justo en los huecos entre certificados, que es lo que hay que ver.
Una serie que vale cero todos los días (hoy el devengo, sin certificados vivos) no se
dibuja ni aparece en la leyenda.

#### Las estadísticas derivadas: `analisis.estadisticas()`

Lo que la serie diaria sabe y los totales no cuentan. Cada cifra contesta algo accionable
—la tasa la pone el banco, los días fuera de un certificado los pone uno—:

- **Los tres estados parten la ventana sin solaparse**, y por eso se pueden enseñar como
  porcentajes que cierran en 100: `rindiendo` (hay algo dentro), `parada` (hay plata
  material y nada dentro), `vacio` (no hay plata). **El día del cierre cuenta como
  parada**: ese día el retiro y el interés entran al residual, así que `dentro` vale 0 y la
  plata está de vuelta en la cuenta. Fijado en `test_cuenta_los_dias_rindiendo_y_los_dias_parada`.
- **Dos ritmos de ganancia**: por día de calendario y **por día trabajado**. El segundo es
  el honesto y siempre es mayor; en `Mias` son 2,81 contra 4,98 al día.
- **Lucro cesante**: lo que la plata quieta habría dado **a la propia tasa histórica del
  portafolio**, no a una inventada. Sin tasa conocida devuelve `None`, no cero — un cero
  diría que no costó nada. En `Mias` son **2.037,84 frente a 2.445,42 ganados**: tener la
  plata fuera 378 días costó casi tanto como todo lo que el portafolio llegó a ganar.
- **Rachas con fechas** (parada y rindiendo) y **cuánto tarda en reinvertir** tras cada
  cierre. Sin las fechas el número no sirve: hay que poder ir a mirar qué pasó ahí.
- **Mejor y peor certificado** por tasa, duración media y capital medio.
- **Por año** reusa `metricas.por_anio`, la misma definición que la pestaña de Resumen. Dos
  tablas de rendimiento anual que no coincidieran serían peor que no tener la segunda.

#### La tendencia de las tasas y la proyección: `tendencia_tasas()` + `proyectar_ganancia()`

**La tasa no es un dato del portafolio, es del banco**, y le pasa lo mismo a todo el dinero
del usuario a la vez. Por eso la recta se ajusta sobre **los 15 certificados del historial
completo** y luego se marca cuáles son del portafolio que se mira (`propio: true`). Con 4 a
7 puntos por portafolio no habría tendencia que ajustar.

Sobre los datos reales: **bajando −2,69 puntos por año, R² 0,58**, del 7,95 % (2024-09) al
2,90 % (2026-07).

**Clasificar la dirección tiene un orden que importa, y las dos veces que lo cambié salió
mal.** La regla final mira tres cosas y en esta secuencia:

1. **Pendiente plana** (≤ 0,25 pp/año) → puede ser `estable` o `irregular`, y lo decide la
   **dispersión** de los residuos, no el R². Mirar el R² primero declaraba `irregular` el
   caso más limpio de todos: una serie plana tiene R² ~0 porque **no hay varianza que
   explicar**, justamente por ser plana.
2. Pero plana con dispersión alta tampoco es estable: 8 %, 2 %, 9 %, 3 %, 7 % tiene media
   plana y un banco así no está quieto. Por encima de `DISPERSION_MAXIMA = 1.0` pp →
   `irregular`.
3. **Pendiente con dirección** → se aplica el R²: por debajo de `R2_MINIMO = 0.30` la recta
   no explica los datos y se dice `irregular` en vez de dibujar una flecha a mano.

Los tres casos están fijados en `test_plana_a_saltos_no_es_estable`,
`test_tasas_planas_son_estables_y_no_una_tendencia` y
`test_sin_bondad_de_ajuste_se_dice_irregular_en_vez_de_bajando`.

**La proyección son tres supuestos dibujados juntos**, porque la horquilla entre ellos es la
respuesta y cualquiera por separado se leería como una promesa: a la tasa de hoy, siguiendo
la tendencia, y a la media histórica.

**Y la línea de la tendencia se corta a los dos años**, que es lo único no obvio de todo el
bloque. Con −2,69 pp/año la tasa llega a cero en diez meses, y prolongar la curva cinco años
dibujaba **una recta plana durante cuatro años afirmando que el banco dejó de pagar
intereses para siempre** — aritméticamente consistente y económicamente absurdo. Cada
escenario lleva `hasta_meses` y sus valores posteriores son `null`; los de tasa constante sí
llegan a cinco años porque no afirman nada nuevo cada mes. Que la línea se vea corta es la
información, no un fallo.

**El umbral de «plata parada» es relativo, no un dólar fijo.** `Uni` termina con 1,33
sueltos tras pagar la matrícula, y con un umbral absoluto la pantalla anunciaba «148 días
con la plata parada» por dólar y medio. Ahora es el **1 % del certificado medio** del
propio portafolio (81 USD en `Uni`, 273 en `Mias`), que separa el residuo de redondeo de una
decisión de no reinvertir. Con eso `Uni` pasa a 204 días parada y 88 sin plata.

**Números de hoy** (2026-08-13): `Mias` 28.445,42 con 2.445,42 ganados y 378 días de plata
parada; `Uni` 1,33 con 850,67 ganados y 17.770,64 en salidas; `Madre` 0,00 con 1.128,68
ganados y 14.083,28 en salidas. Los dos últimos están vaciados a propósito (matrículas), y
por eso **no se les calcula escenario**: componer 1,33 durante diez años da una tabla con
pinta de cálculo y sin contenido.

#### El drill-down: un certificado de cerca

**La idea que lo sostiene**: el interés de un plazo fijo se cobra de golpe el día del
cierre, así que en los datos crudos una posición es una línea plana con un escalón al
final. Eso es verdad contable y mentira económica —la plata rindió todos los días—, y la
curva reparte el interés día a día.

**Lo que hace que no sea una estimación bonita**: para una posición cerrada la tasa del
devengo **se despeja del interés que el banco pagó de verdad** (`interes/capital · 360/plazo`),
así que la curva no se aproxima al número real, **aterriza en él al centavo**. Comprobado
sobre los 15 plazos fijos con apertura conocida: los 15 cierran exactos. Para una abierta
hace falta la `tasa_pactada` capturada a mano y, si no está, se devuelve `apto: false` con
el motivo en vez de dibujar una recta con la tasa de otra posición — el mismo criterio de
`metricas.interes_devengado`.

**Tres cosas que se decidieron y no son obvias:**

1. **El retiro del día del cierre no baja el capital de la curva.** Ese retiro *es* el pago
   de lo que la posición valía; descontarlo desplomaría la línea a cero justo el día que se
   cobra. Un retiro parcial a mitad de vida sí baja el capital, porque ahí sí salió plata
   que dejó de rendir. Fijado en dos tests, es lo que más fácil se rompe al refactorizar.
2. **La proyección no es un pronóstico.** El capital ya está adentro, la tasa ya está
   pactada y la fecha ya está fijada: es la misma aritmética corrida hacia adelante. Por
   eso se dibuja punteada pero se afirma.
3. **El escenario de reinversión sí es un supuesto, y viaja aparte por eso.** Supone
   renovar capital e interés al mismo plazo y a la misma tasa, cosa que el propio historial
   contradice (8,70 % → 2,90 % en dos años). La pantalla lo dice con esas palabras debajo
   de la tabla.

El `Chart` de echarts y su paleta se movieron de `EvolutionTab.tsx` a `shared.tsx`: las dos
pestañas dibujan ahora con el mismo componente en vez de con dos copias.

`tests/test_investment_analisis.py` (58) y 5 tests de ruta, uno de ellos para que
`/positions/{id}` y `/positions/{id}/analysis` no se coman entre sí si alguien las reordena.

### 2.15 La navegación del módulo, el borrado de los portafolios y `origen` (2026-08-14)

**Tres pestañas, no seis.** La barra pasó a `Resumen · Detalle · Conciliación`, cada una con
subsecciones propias:

| Pestaña | Subsecciones |
|---|---|
| Resumen | Totales · Evolución · Posiciones |
| Detalle | Resumen general · Proyección · Por certificado |

Posiciones y Evolución dejaron de ser pestañas de primer nivel: son dos maneras de leer el
resumen. Neutralización **se eliminó** (§7.3) y `NeutralizationTab.tsx` está borrado; el
servicio `neutralizacion.py` y sus endpoints siguen porque `corte.py` depende de ellos.

Dentro de Detalle: la lista de certificados y el drill-down viven **lado a lado** en pantalla
ancha —antes el detalle se abría debajo de una lista con scroll propio, así que clicar una
fila mandaba la respuesta fuera de la vista—, las tasas cierran la pestaña en vez de abrirla
(el usuario no decide la tasa; decide los días dentro de un certificado), y las estadísticas
se partieron en «mientras trabajaba» / «mientras estaba quieta», atadas por color a los
tramos de la barra de tiempo.

**El saldo inicial se mudó de Resumen a Detalle** (§2.10, §7.4): era una lista con los tres
portafolios a la vez, lejos de la única pantalla donde el número se nota. Ahora es un botón
con modal sobre **el portafolio que se está mirando**, y al guardar la curva de al lado se
recalcula. Sigue distinguiendo vacío de cero: «volver a deducir» borra la configuración,
guardar un `0` afirma que arranca vacío.

**Posiciones tiene por fin un gráfico**: una línea de tiempo tipo Gantt, un carril por
portafolio, cada certificado una barra de apertura a cierre con su TNA escrita dentro. El
ancho es tiempo y no capital a propósito —lo que rinde es el capital *por día*— y lo que el
gráfico enseña de verdad son **los huecos entre barras**: los días en que esa plata no
rendía. Los `flujo` y `ajuste` quedan fuera del gráfico (duración cero) y siguen en la tabla.

#### El accidente: los tres portafolios se borraron

A las 11:08 de ese día `grupos.csv` se reescribió sin las filas `Inversiones_Mias`, `_Uni` y
`_Madre`. `list_portfolios()` las lee de ahí, así que la API devolvía `[]` y el módulo entero
se quedó en blanco. `posiciones.csv` y `movimientos.csv` estaban intactos: no se perdió ni un
certificado, solo lo que los agrupa. Se restauraron con los `saldo_inicial` vigentes
(26.000 / 3.177 / −0,84).

**Nada del corte pudo hacerlo**: `corte.py` solo borra grupos con `type == 'shadow'`
localizados por `fondo_origen`, y `funds.py` borra por `fondo_origen`, nunca al portafolio.
La única ruta capaz es el `DELETE /api/payments/groups/{id}` genérico, el de la pantalla de
grupos. Y hay una explicación mecánica de por qué alguien lo pulsaría: **después del corte
los grupos originales se quedan sin ningún pago** —`aplicar_corte()` los vacía a propósito—
así que en Variables → Pagos fijos aparecen como grupos huecos, aparentemente residuales.
Borrarlos parece limpieza y destruye el módulo.

#### `origen`: `type` dice cómo se ejecuta, no qué es

La causa de fondo, y no es solo de Inversiones. `VirtualItemsProcessor` aplica al patrimonio
exactamente `fixed` e `interpolated`, así que **todo el que quiera contar acaba marcado
`fixed`**: los pagos fijos a mano, los fondos, los portafolios y las series generadas. La
pantalla de Pagos fijos filtraba solo por `type` y enseñaba quince grupos cuando pagos fijos
del usuario hay tres.

`_normalize_group()` deriva ahora un campo `origen` —sin columna nueva ni migración— de lo
que ya está en el CSV, en este orden:

| `origen` | condición | quién manda |
|---|---|---|
| `generado` | `fondo_origen` puesto | la pantalla que lo genera |
| `fondo` | `es_fondo` | Fondos |
| `inversion` | `es_inversion` | Inversiones |
| `manual` | nada de lo anterior | el usuario, en Variables |

Sobre los datos reales: 15 `fixed` → 3 `manual` (Mis Depositos, Arreglos, Pagos Parqueadero),
3 `inversion`, 3 `fondo`, 6 `generado`.

**Los generados se llaman «X Pagos», con sufijo, no «Pagos X».** No es estética: la lista se
ordena por nombre, así que el sufijo deja cada grupo generado **pegado al que lo genera**
(`Inversiones_Uni`, `Inversiones_Uni Pagos`) en vez de mandarlo a la letra P, lejos de su
origen. `funds.py` ya lo hacía; `corte.py` usaba `PREFIJO = 'Pagos '` y ahora usa
`SUFIJO = ' Pagos'`. Las seis filas antiguas se renombraron en `grupos.csv` el 2026-08-14
—identificadas por `fondo_origen`, nunca por el nombre, para no tocar el grupo `manual`
«Pagos Parqueadero», que es del usuario—. Renombrar es seguro porque **nada busca grupos por
nombre**: `_grupo_sombra()` y `_grupo_generado_activo()` van por `fondo_origen`, y así se
documenta en `corte.py:85`.

Fondos ya hacía lo correcto (`get_groups(type_filter=None, fund_only=True)`, filtra por
`es_fondo`) e Inversiones también (`es_inversion` o tener posiciones). Los que filtraban bien
eran ellos; el que no filtraba nada era Pagos fijos — y son Fondos e Inversiones quienes
producen los grupos generados que allí aterrizaban.

Dos consecuencias, las dos en producción:

- `GET /api/payments/groups?type=fixed&origen=manual`, y la pantalla lo usa por defecto. Los
  demás **se etiquetan, no se esconden**, tras una casilla «ver los que gestionan otras
  pantallas», en solo lectura y diciendo quién es su dueño. Esconderlos del todo repetiría el
  problema: un grupo invisible que existe y se puede borrar es la receta del accidente.
- `DELETE /api/payments/groups/{id}` devuelve **409** si el grupo no es `manual`, nombrando a
  su dueño, y exige `forzar=true` para pasar por encima.

---

## 3. El diagnóstico sobre los datos reales — FOTO HISTÓRICA

> ⚠️ **Esto ya no es «hoy».** Es el estado *antes* de sembrar los flujos (§2.0/§2.1), antes
> de que el usuario corrigiera los dos pagos de `Uni` y antes del corte. Los tres
> portafolios cuadran desde entonces por debajo de la tolerancia (1,38 / 1,33 / 1,24 — ver
> «Empieza por aquí»), y la pestaña de Neutralización ya no compara contra pagos a mano.
> Se conserva porque explica de dónde venía cada descuadre y contra qué se midió el
> arreglo; **no lo uses como diagnóstico actual**.

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
| `saldo_inicial_sugerido()` | deduce el residual de partida de cada portafolio | la columna **`saldo_inicial` de `grupos.csv`**, que ya existe y `_con_saldo_inicial()` ya lee. **Ya está en la GUI** (§2.10) y los tres portafolios lo tienen configurado: 26.000 / 3.177 / −0,84 |
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
                         + registrar_flujo(), residual_portafolio(),
                         inferir_plazo_y_tasa() y configurar_saldo_inicial()
    portafolios.py       infiere de qué portafolio es cada posición desde pagos.csv
    metricas.py          XIRR, TNA ponderada, capital-día, devengo, resumen, timeline
    neutralizacion.py    genera los pagos fijos y los compara (NO escribe)
    corte.py             fase 6: sombra → verificación → corte (§2.7) + regenerar() (§2.13)
    patrimonio.py        capital propio vivo por día → NOTIONCUM (fase 5)
    analisis.py          el portafolio entero y, dentro, un certificado de cerca (§2.14)
  storage/investments_storage.py    posiciones.csv + movimientos.csv
  storage/variables_storage.py      +es_inversion/es_custodia y saldo_inicial_configurado;
                                    get_invalid_payments() y delete_payment_row()
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
  pages/Investments.tsx                     shell + 3 pestañas y las subsecciones de Resumen (§2.15)
  components/investments/
    shared.tsx              fmt/money/pct, KpiCard, Badge, Section, Spinner, SubTabs + Chart y su paleta
    PositionsTab.tsx        línea de tiempo (§2.15) + tabla maestra, fila expandible, «Analizar»
    AnalysisTab.tsx         portafolio en 3 subsecciones + drill-down y el modal de saldo inicial (§2.14, §2.15)
    SummaryTab.tsx          KPIs con selector propio/custodia/todo, por portafolio, por año
    EvolutionTab.tsx        área de capital + interés acumulado, dispersión de TNA
    ReconcileTab.tsx        diff del detector con sugerencias de portafolio (§7.7)
  services/investments.ts   cliente + tipos
  components/Sidebar.tsx    entrada 'inversiones' entre Fondos y Variables
  App.tsx                   ruta 'inversiones' + el toggle "Con inversiones" del dashboard
  hooks/useDashboard.ts     incluirInversiones en la queryKey de las dos consultas
  components/DashboardChart.tsx / VariationsChart.tsx   reciben el flag por prop
```

### Datos

```
data/sistema/inversiones/
  posiciones.csv    30 filas   (2026-08-13)
  movimientos.csv   78 filas
```

30 posiciones = **13 flujos** (`flujo-*`, §2.0 y §2.12) + **17 plazos fijos**. De esos 17: 2
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
| `GET` | `/api/investments/positions/{id}/analysis` | un certificado de cerca: curva diaria, proyección al vencimiento y ganancia (§2.14) |
| `GET` | `/api/investments/portfolios/{id}/analysis` | **el bolsillo entero**: cuánta plata hay, cuánta rinde, cuánta ha dejado y escenarios (§2.14) |
| `POST` | `/api/investments/positions/{id}/split` | repartir un certificado entre portafolios |
| `GET` | `/api/investments/portfolios` | grupos que hacen de portafolio |
| `PUT` | `/api/investments/portfolios/{id}/saldo-inicial` | fija el residual de partida (`null` vuelve a deducirlo) |
| `GET` | `/api/investments/summary` | KPIs globales, propio/custodia, por portafolio, por año |
| `GET` | `/api/investments/timeline` | serie diaria de capital e interés + eventos |
| `POST` | `/api/investments/detect` | diff contra el banco **sin escribir**, con sugerencia de portafolio |
| `POST` | `/api/investments/detect/apply` | confirma el diff (nunca pisa `origen='manual'`) |
| `POST` | `/api/investments/flows` | registra plata que entra o sale del portafolio |
| `GET` | `/api/investments/flows/preview` | residual antes/después, **sin escribir** |
| `GET` | `/api/investments/neutralization/preview` | fase 6 **sin escribir** |
| `GET` | `/api/investments/cut/status` | dónde está el corte |
| `POST` | `/api/investments/cut/shadow` | siembra los grupos `shadow` (aditivo, idempotente) |
| `DELETE` | `/api/investments/cut/shadow` | los borra |
| `GET` | `/api/investments/cut/verify` | compara las dos series **sin escribir** |
| `GET` | `/api/investments/cut/regenerate/preview` | qué cambiaría al poner los pagos al día |
| `POST` | `/api/investments/cut/regenerate` | los reescribe en su sitio (idempotente) |
| `GET` | `/api/investments/from-accounts` | legado, delega en el detector |
| `GET` | `/api/investments/chart-data` | legado (saldo vs inversión) |
| `GET` | `/api/dashboard/chart-data?incluir_inversiones=` | patrimonio con o sin el capital invertido |
| `GET` | `/api/dashboard/variations?incluir_inversiones=` | **el mismo valor que el anterior** |
| `GET` | `/api/payments/payments/invalidos` | las filas de `pagos.csv` que nadie más muestra |
| `DELETE` | `/api/payments/payments/invalidos/{fila}` | borra una de esas filas, por número de fila |
| `GET` | `/api/payments/groups?type=&origen=` | grupos; `origen` = `manual`/`fondo`/`inversion`/`generado` (§2.15) |
| `DELETE` | `/api/payments/groups/{id}?forzar=` | **409** si el grupo no es `manual`; `forzar=true` pasa por encima (§2.15) |

> El `payments/payments` no es una errata: el router se monta con prefijo `/api/payments` y
> sus rutas de pago ya empiezan por `/payments`. Es la convención que ya seguían
> `PUT`/`DELETE /api/payments/payments/{id}`.

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
6. ~~**El portafolio se infiere de `pagos.csv`**, no se pide a mano.~~ **Superado por el
   corte**: al vaciarse `pagos.csv`, `portafolios.sugerir()` se quedó sin fuente y ya no
   sugiere nada (probado: 14 posiciones, 0 sugerencias, cero errores). Hoy **se elige a
   mano** en Conciliación y en la fila de cualquier posición guardada — §3.1.
7. **Los pagos fijos se migrarán**, pero con corte en sombra y test de equivalencia sobre
   la función escalón. Nada de migrar a ciegas.

### Abiertas

- ¿`Inversiones_Uni` tiene meta (monto objetivo, fecha de matrícula)? Habilitaría una
  vista de progreso como en Fondos.
- ~~¿Se quita `es_inversion`?~~ **Resuelta: no se quita** — §7.6. La premisa era falsa: no
  sirve solo para la UI, es el permiso del corte para vaciar los pagos de un grupo.

---

## 7. Lo que falta

> Ordenado por valor. Nada de esto bloquea operar el módulo: el corte está hecho y
> `regenerar()` mantiene los pagos al día cuando entra una inversión nueva.

> **La numeración de §7 es estable**: los apartados se citan como §7.1…§7.10 desde el resto
> del documento. Si añades uno, ponlo al final; no renumeres.

### 7.1 Capturar el plazo de las 2 siembras

Las otras 15 se deducen (§2.9). Estas dos no tienen `fecha_apertura`, así que admiten
infinitas combinaciones de plazo y tasa: hace falta el certificado o la memoria del usuario.

### 7.2 Borrar `pagos.csv` del todo

Ver §3.1. Ya no queda ningún pago de inversiones en él; lo que resta es decidir si el
archivo desaparece o se queda para los grupos que no son de inversión (`Mis Depositos`, los
fondos), que es lo más probable.

### 7.3 ~~Reconvertir~~ Eliminar la pestaña de Neutralización — **hecha a medias (2026-08-14)**

Cumplió su función: era la herramienta de migración y ya no hay pagos a mano contra los que
comparar, así que informaba «683 de 806 días descuadrados», correcto pero inútil. **Se
eliminó** —pestaña y `NeutralizationTab.tsx`— en §2.15; el backend sigue intacto porque
`corte.py` depende de `neutralizacion.py`.

**Lo que queda pendiente es su otra mitad**: el diff de `previsualizar_regeneracion()`
(§2.13) sigue sin sitio en la UI, y era el destino que este apartado le daba. Hoy solo se ve
por script y por API. Es lo que §7.5 daba por resuelto apoyándose en esta pestaña, así que
ahora ese hueco no tiene dónde apoyarse: hay que darle uno nuevo (Conciliación es el
candidato natural — ver §7.7).

### 7.4 El `saldo_inicial` ya está configurado — pero es frágil

Los tres portafolios lo tienen (26.000 / 3.177 / −0,84), porque el corte dejó la deducción
sin fuente y `residual_portafolio()` empezó a devolver negativos. Queda anotado aquí porque
es la clase de dato que hay que revisar si alguna vez se regeneran los pagos desde cero.

### 7.5 Nada avisa de que los pagos generados se quedaron atrás

**El hueco operativo real del módulo.** `regenerar()` (§2.13) existe y funciona, pero hay
que **acordarse de correrlo**: no hay disparador en la UI, ni aviso, ni comprobación
automática. Si entra un certificado nuevo y nadie corre `--regenerar`, las posiciones se
actualizan y los pagos fijos no, así que **el patrimonio queda desactualizado en silencio**
— exactamente el modo de fallo que el módulo venía a eliminar.

Es idempotente y previsualizable, así que las salidas son baratas: un aviso cuando
`previsualizar_regeneracion()` devuelva un diff no vacío, y un botón para aplicarlo. **Ya no
puede ir en la pestaña de Neutralización** —se eliminó en §2.15— así que hay que elegirle
sitio; Conciliación es el candidato natural, porque es la otra pantalla que ya carea lo
guardado contra su fuente (§7.7).

### 7.6 Resuelta: ¿sirve de algo `es_inversion`?

**Sí, y no por lo que decía este documento.** Decía que solo servía para que un portafolio
nuevo y vacío apareciera en la UI. En realidad es un filtro estricto en tres sitios, y el
que importa es `corte._portafolios()`: **`es_inversion` es la lista de grupos cuyos pagos el
corte tiene permiso de vaciar.**

`list_portfolios()` sí es permisivo a propósito (incluye cualquier grupo con una posición
colgando, para que ninguna quede huérfana), y esa es la asimetría que había que ver: si se
quitara la marca y el corte cayera en esa lista permisiva, un grupo al que se le asignó una
posición por error en Conciliación se quedaría sin sus pagos escritos a mano el día del
corte. **No se quita.** Fijado en
`test_el_corte_solo_toca_grupos_marcados_es_inversion`.

**La otra cara, que conviene ver antes de tocar nada**: los tres grupos generados
(`Pagos Inversiones_*`) tienen `es_inversion = False` en `grupos.csv`, así que **quedan
fuera de `corte._portafolios()` y el corte no puede vaciarlos** — es justo lo que se
quiere. `regenerar()` no los busca por esa lista sino por `fondo_origen` + `type == 'fixed'`
(`corte.py:97`), que es la única razón por la que los alcanza. Si alguien «arregla» esa
incoherencia marcándolos `es_inversion`, un corte futuro se llevaría por delante los pagos
generados.

### 7.7 Revisar si Conciliación está bien planteada — **pedido por el usuario (2026-08-14)**

No hay un bug reportado: es una duda sobre el planteamiento. El usuario pidió expresamente
dejarla como está por ahora y volver a mirarla, así que **este apartado se abre antes de
tocar cualquier otra pestaña del módulo**.

Qué hace hoy: `POST /detect` (solo lectura) carea el extracto del banco contra
`posiciones.csv` y reparte el resultado en cuatro cubos — **nuevas** (el banco las reporta y
no están guardadas, con portafolio sugerido a partir de las cadenas de pagos fijos),
**cambiadas** (guardadas que ya no cuadran, típico tras reprocesar el extracto cuando aparece
interés que faltaba), **huérfanas** (cancelación sin apertura: certificados abiertos antes de
donde empieza el historial, hay que sembrarlos a mano) y **solo guardadas** (las tienes tú y
el banco ya no las reporta). Nada escribe hasta confirmar.

Su papel en el módulo es el que hay que juzgar: **es la única puerta de entrada de datos**.
Las otras dos pestañas solo leen lo que ésta deja escrito. Al revisarla, dos cosas que ya
están sobre la mesa:

- Es el sitio natural para el aviso y el botón de `regenerar()` que se quedaron sin casa al
  eliminar Neutralización (§7.3, §7.5): es la otra pantalla que ya carea lo guardado contra
  su fuente.
- Conviene mirarla junto a §7.6: es aquí donde una posición puede quedar asignada al grupo
  equivocado, y esa asignación es la que decide qué pagos puede vaciar el corte.

### Preguntas abiertas para el usuario

Ninguna bloquea nada, pero hasta que se respondan el dato queda con una nota al pie:

- ~~¿Los 3.533,84 de `Madre` y los 3.635,07 de `Uni` son el mismo dinero?~~ **Resuelto: sí**
  (2026-08-12, con las notas del usuario). Ver §2.12.
- **Nadie ha visto la página renderizada.** No hay navegador conectado en estas sesiones.
  Verificado: `tsc -b --noEmit` limpio y los endpoints responden 200 con los datos reales
  (§8). El render en sí no está confirmado — si tienes navegador, ábrela y míralo.

### Aparte del módulo — los tres arreglados el 2026-08-12

7. ✅ **(§7.7) `pagos.csv` admitía ids repetidos y las escrituras eran por id.**
   `delete_payment()` hacía `df[df['id'] != id]`, o sea que borrar una fila se llevaba por
   delante la otra que compartiera id. Ahora toda escritura por id pasa por `_indices_de()`
   y actúa **sobre una sola fila**, dejando un `warning` si hay más; `create_payment()` y
   `create_group()` comprueban el id contra los existentes. `update_group`/`delete_group`
   tenían el mismo defecto y también están arreglados.
8. ✅ **(§7.8) `get_payments()` escondía filas que existen.** Dos arreglos, en este orden:

   - Lo que sigue siendo inválido (sin id, sin grupo o sin monto) ya no desaparece:
     `get_invalid_payments()` lo lista con el motivo y el número de fila, y
     `delete_payment_row()` lo borra aunque no tenga id o lo tenga repetido.
   - **Y una fecha que falta ya no es un error, es un significado** — ver §2.11.
9. ✅ **(§7.9) `read_csv` no limpiaba los NaN como prometía.** Ahora pasa por `object` a la fuerza,
   que es lo único que impide que pandas re-infiera el dtype y devuelva el NaN. Solo
   convierte las columnas que de verdad tienen huecos, así que una columna llena conserva
   su dtype y su aritmética. **Verificado A/B contra el dashboard real: `PAGOS_FIJOS`
   idéntico en los 944 puntos.** `neutralizacion._texto()` se queda como está: es correcto y
   quitarlo no aporta nada.
10. **(§7.10)** Tres tests fallan desde antes de todo este trabajo, y seguían fallando el
   2026-08-13:
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

# tests del módulo (380, todos verdes) — los 10 archivos, no 7:
# faltaban `corte` y `pagos_sin_fecha`, que son justo los de las últimas dos sesiones
contabilidad/backend/.venv/bin/python -m pytest \
  tests/test_investment_posiciones.py tests/test_investment_metricas.py \
  tests/test_investment_detector.py tests/test_investment_neutralizacion.py \
  tests/test_investment_patrimonio.py tests/test_investment_flujos.py \
  tests/test_investment_corte.py tests/test_investment_analisis.py \
  tests/test_pagos_sin_fecha.py tests/test_routes_investments.py -q

# el módulo toca además estos, que no llevan `investment` en el nombre:
#   tests/test_variables_storage.py  tests/test_transform_investments.py
#   tests/test_investment_service.py (legado)

# suite completa: 15.298 pasan, 3 fallan (ajenos, ver §7.10)
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
# esperado HOY (2026-08-13, post-corte): pagos_generados 33, pagos_actuales 0,
#   siembra_total 29176.16, dias_descuadrados 684 de 807, cuadra false
# El `cuadra false` es correcto y esperado: ya no hay pagos a mano contra los que
# comparar, así que compara contra cero. Es la pantalla la que sobra, no el dato (§7.3).

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

**Reversa del corte** — la operación de emergencia más probable, y la que no estaba escrita.

⚠️ **Los `.bak` no sirven para esto.** `grupos.csv.bak` y `pagos.csv.bak` son rodantes: los
pisa cada escritura, y a fecha de hoy los dos ya son **post-corte** (0 pagos en los tres
portafolios originales, grupos generados en `fixed`). La única copia de los 30 pagos a mano
está en git, en `77ac01f`.

```bash
# 1. Recuperar los pagos a mano de antes del corte
git show 77ac01f:data/sistema/interpolaciones/pagos.csv > /tmp/pagos_precorte.csv

# 2. Comparar antes de pisar nada: los pagos generados (grupos `Pagos Inversiones_*`)
#    NO están en esa copia, así que restaurarla entera los borraría.
#    Lo correcto es fusionar: filas de los 3 portafolios originales desde /tmp,
#    todo lo demás desde el `pagos.csv` de hoy.

# 3. Devolver los grupos generados a `shadow` para que el dashboard deje de verlos
#    (columna `type` de `Pagos Inversiones_*` en grupos.csv), o borrarlos.

# 4. Comprobar que la serie volvió: PAGOS_FIJOS del dashboard contra el snapshot previo.
```

**El orden es el inverso del corte**: primero desactivar los generados y después restaurar
los originales, para no tener un instante con las dos series aplicándose (§2.7). Con el
backend en `--reload` corriendo, párale antes o comprueba `md5sum` (§9).

**Reversa de todo el módulo**: borrar `data/sistema/inversiones/` y restaurar `grupos.csv`
desde git (no desde su `.bak`, por lo mismo de arriba). Nada más se tocó.

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
- **Las fechas de un pago son opcionales, pero solo en los grupos `fixed`.** Vacío
  significa «desde/para siempre» (§2.11). En un grupo `interpolated` siguen siendo
  obligatorias porque son el tramo que reparte, y la ruta lo rechaza con un 400.
- **Si tocas la ventana de un pago, tócala en los dos sitios.**
  `VirtualItemsProcessor._apply_fixed_payment` y `neutralizacion._activo` implementan la
  misma regla por separado, y la segunda existe para medir la primera. `test_pagos_sin_fecha
  .py::test_activo_y_el_dashboard_dicen_lo_mismo` las compara; si falla, no lo arregles
  cambiando solo una.
- **`read_csv` deja NaN en las columnas de texto vacías**, y `nan` es *truthy*: un
  `campo or ''` no lo atrapa y FastAPI revienta al serializar con "Out of range float
  values are not JSON compliant". Ver §7.9.
- **`Col` es un `(str, Enum)`, no un `StrEnum`.** `df[Col.X] = ...` funciona para buscar,
  pero deja el miembro del enum dentro del Index y el encabezado del CSV sale `Col.X`.
  Al escribir columnas, usar `Col.X.value`.
- **El flag `incluir_inversiones` tiene que ir igual en `/chart-data` y en `/variations`.**
  Si no, el desglose diario se contrasta contra un total que no es el suyo y la diferencia
  aparece como "sin explicar".
- **El usuario tiene el backend corriendo con `--reload` y usa la app mientras trabajas.**
  Dos consecuencias, las dos vividas: (a) `data/sistema/interpolaciones/*.csv` puede
  cambiar bajo tus pies —una re-materialización de un fondo reescribió `grupos.csv` y
  `pagos.csv` a mitad de una comparación A/B—; comprueba `md5sum` antes y después en vez de
  fiarte del resultado. (b) `deuda_acumulada` viene de Supabase en vivo y **cambia entre dos
  ejecuciones seguidas** sin que nadie toque el código: si comparas el dashboard contra una
  línea base, compara el campo que te interesa, no el total.
- **Los `.bak` no son un respaldo, son la versión anterior.** `InterpolationStorage` los
  pisa en cada escritura, así que a las pocas horas de una migración ya reflejan el estado
  nuevo. Para recuperar algo de antes de una operación grande, **git**. Si vas a hacer algo
  irreversible, haz el commit antes.
- **Una tolerancia tiene unidades.** `TOLERANCIA_CORTE` mide el redondeo de *un* portafolio
  y durante una sesión entera se contrastó contra la suma de tres (§2.8). Antes de subir un
  umbral porque «no pasa por poco», comprueba que lo estés midiendo sobre lo que fue
  calibrado.
