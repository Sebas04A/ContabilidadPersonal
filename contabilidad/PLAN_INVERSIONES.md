# Plan — Módulo de Inversiones

Estado: propuesta, con las decisiones de arquitectura tomadas (§6).
Escrito el 2026-08-11 sobre la rama `enriquecimiento-horas`.

---

## 1. Qué hay hoy

### 1.1 El mecanismo de neutralización (pagos fijos)

La cadena real es:

```
pagos.csv (grupos type='fixed')
   └─> mark_fixed_payments(df, pagos, 'INVERSION')   # get_variables.py:112
          suma amount a todas las filas con start <= FECHA < end
   └─> dashboard_service.py:271
          saldo_sin_inversion = SALDO - PAGOS_FIJOS
   └─> dashboard_service.py:275
          TOTAL = saldo_sin_inversion + INTERPOLADO - TARJETA + DEUDA_ACUMULADA
```

Es decir: `PAGOS_FIJOS` es un *tramo escalonado* que dice "de este saldo visible, tanto
es plata de inversión y no es flujo mío". Funciona, y por eso los gráficos no se
distorsionan cuando entra un CDT de 28.000.

Los tres portafolios viven como grupos `fixed` en `grupos.csv`:

| grupo | id | pagos |
|---|---|---|
| `Inversiones_Mias` | `bd963a38…` | 10 |
| `Inversiones_Uni` | `e996e29a…` | 8 |
| `Inversiones_Madre` | `5a1076ed…` | 6 |

más una corrección suelta (`-600`, "Inversiones para corregir") en el grupo
`Mis Depositos`.

### 1.2 Lo que ese mecanismo **no** guarda

Los `amount` de `pagos.csv` son **saldos residuales**, no inversiones. Ejemplo real
de `Inversiones_Mias`:

```
27897.0  2025-01-24 → 2025-02-21
 -103.0  2025-02-21 → 2025-03-24
28034.0  2025-03-24 → 2025-05-12
```

De ahí no se puede sacar: cuánto capital pusiste, cuánto te pagaron de interés,
a qué plazo, a qué tasa, cuánto te retuvieron. Toda esa información se pierde en la
resta. Y el `-103` es un artefacto contable (invertiste 28.000 teniendo 27.897 de
plata de inversión), no un dato interpretable.

### 1.3 La sección de inversiones actual

Existe: `routes/investments.py` → `services/investment_service.py` →
`pages/InvestmentAnalysis.tsx`, montada como tab dentro de **Variables**. Tiene tres
problemas de fondo:

1. **Cuenta mal las finalizadas.** `get_investments_from_accounts()` toma *todas* las
   filas `CANCELACION PLAZO FIJO` como inversiones cerradas. Pero el banco emite el
   interés como una **segunda fila con la misma descripción**. Hay 22 filas
   `CANCELACION PLAZO FIJO` en `banca_unida.xlsx` y solo **14 cancelaciones reales**;
   las otras 8 son intereses listados como si fueran inversiones de $1.897,57, $682,63,
   $225,25, $139,84, $123,23, $27,48…

2. **No detecta todos los formatos de interés.** El código busca `TRANSFERENCIA INTERIOR`
   y si no, la segunda `CANCELACION`. Pero desde 2026 el banco lo manda como
   `REGULARIZACIÓN DE TRANSACCIÓN` (ver 2026-07-27, $69,60) — ese interés hoy se pierde.

3. **No empareja apertura con cierre.** Sin ese vínculo no hay plazo, no hay tasa, no hay
   "qué tengo abierto ahora mismo". Las listas "iniciadas" y "finalizadas" son dos
   montones sueltos.

Además, `NOTIONCUM` (el slot "Inversiones" del patrimonio, `dashboard_service.py:26`)
**nunca se llena** — está fijo en `0.0`. En el gráfico de variaciones el componente
"Inversiones" siempre marca cero. Consecuencia: mientras la plata está adentro de un CDT,
tu patrimonio la muestra como si no existiera.

### 1.4 La columna `INVERSION` no contiene inversiones

`transform_investments()` (`storage/transformations/investments.py:13`) hace:

```python
groups = InterpolationStorage.get_groups(type_filter=None)   # ← TODOS los grupos
```

y suma **todos los pagos de todos los grupos** dentro de la columna `INVERSION`: los 116
de `Fondo Comida`, los 32 de `Gasolina_PAGOS`, los 10 interpolados de `Mensual_Madre`,
los de `Arreglos`, `Parqueadero`… La serie "inversión" que hoy dibuja `InvestmentChart`
no es de inversiones, es la suma de todo lo virtual del sistema.

Vale aclarar el alcance del bug: el **dashboard no usa esa columna**. `PAGOS_FIJOS` se
construye aparte en `VirtualItemsProcessor` (`dashboard_service.py:193-235`), que sí
filtra por `group_type == 'fixed'`. Los consumidores contaminados son solo
`InvestmentChart` y `snapshots/completos.py`. Pero como el módulo nuevo se va a apoyar
en esta capa, hay que arreglarlo antes de construir encima.

---

## 2. Hallazgo central: los datos del banco ya contienen todo

Corrí un emparejamiento sobre `banca_unida.xlsx` (1.122 filas):

- **apertura** = `MONTO < 0` y descripción `CERTIFICADO DE DEPOSITO` o `…A PLAZO FIJO`
- **cierre** = `CANCELACION PLAZO FIJO` con `MONTO > 0` **cuyo monto calza exacto** con
  el capital de una apertura abierta (FIFO)
- **interés** = las demás filas de crédito con la misma marca de tiempo del cierre
- **retención** = filas `RETENCION … RENDIMIENTO FINANCIERO` con esa marca de tiempo

Resultado: **14 aperturas → 14 cierres, cero huérfanas, cero ambiguas.**

| Apertura | Cierre | Días | Capital | Interés | Ret. | TNA |
|---|---|---:|---:|---:|---:|---:|
| 2024-06-04 | 2024-09-04 | 92 | 10.278,00 | 208,82 | 4,18 | 8,06 % |
| 2024-09-23 | 2024-10-24 | 30 | 6.648,00 | 27,48 | 0,55 | 5,03 % |
| 2024-03-28 | 2025-01-24 | 302 | 26.000,00 | 1.897,57 | — | 8,82 % |
| 2024-11-18 | 2025-03-19 | 120 | 10.310,00 | 225,25 | 4,51 | 6,65 % |
| 2025-02-21 | 2025-03-24 | 30 | 28.000,00 | 139,84 | 2,80 | 6,08 % |
| 2025-05-12 | 2025-06-12 | 30 | 27.000,00 | 123,23 | 2,46 | 5,55 % |
| 2024-11-18 | 2025-06-17 | 210 | 10.003,00 | 386,95 | — | 6,72 % |
| 2025-08-12 | 2025-09-12 | 30 | 38.000,00 | 116,16 | 2,32 | 3,72 % |
| 2025-04-28 | 2025-09-25 | 149 | 7.317,00 | 167,68 | 3,35 | 5,61 % |
| 2025-11-18 | 2025-12-19 | 30 | 27.000,00 | 67,43 | 1,35 | 3,04 % |
| 2025-11-18 | 2025-12-22 | 33 | 10.419,00 | 28,54 | 0,57 | 3,03 % |
| 2026-01-21 | 2026-02-23 | 32 | 28.304,00 | 75,24 | 1,50 | 3,03 % |
| 2025-11-18 | 2026-03-19 | 120 | 4.214,00 | 67,28 | 2,02 | 4,86 % |
| 2026-06-25 | 2026-07-27 | 31 | 27.000,00 | 69,60 | 2,09 | 3,04 % |

Totales: **capital rotado 260.493**, **interés 3.601,07**, **retención 27,70**,
**neto 3.573,37**, **TNA ponderada 6,70 %**. Y una tendencia que hoy no ves en ningún
lado:

| año de cierre | n | capital medio | interés | TNA ponderada |
|---|---:|---:|---:|---:|
| 2024 | 2 | 8.463 | 236,30 | 7,53 % |
| 2025 | 9 | 20.450 | 3.152,65 | 7,09 % |
| 2026 | 3 | 19.839 | 212,12 | **3,44 %** |

Tu tasa se partió a la mitad en 2026. Eso es exactamente el tipo de cosa que la sección
debería gritarte.

**Solo 3 cancelaciones no emparejan** — 2024-05-29 ($10.100), 2024-10-25 ($12.854,21) y
2024-10-25 ($682,63) — porque son inversiones abiertas **antes** de que empiece el
historial bancario. Ya están anotadas a mano en `pagos.csv` (la fila de
`Inversiones_Uni` de 10.100 sin `start_date`, etc.). Son casos de siembra manual, no un
fallo del emparejamiento.

### 2.1 Los pagos de `pagos.csv` son derivables

Verifiqué el encadenamiento completo de `Inversiones_Mias`:

```
26.000 (cap) + 1.897,57 (int)           = 27.897,57  ≈ 27897   ✓ 2025-01-24
27.897 − 28.000 (nueva apertura)        =    −103    ✓ 2025-02-21
28.000 + 139,84 − 2,80 + (−103)         = 28.034,04  ≈ 28034   ✓ 2025-03-24
28.034 − 27.000                         =  1.034     ✓ 2025-05-12
27.000 + 123,23 − 2,46 + 1.034          = 28.154,77  ≈ 28154   ✓ 2025-06-12
28.154 + 10.389 (Madre) − 38.000        =    543     ✓ 2025-08-12
```

Es una cuenta corriente: `residual_nuevo = residual_previo + capital_devuelto +
interés − retención − capital_reinvertido`. Todo lo que hoy escribes a mano sale de ahí.

**Lo único que no es derivable** es la línea 6: el CDT de 38.000 juntó plata de
`Mias` (28.154) y de `Madre` (10.389). Ese reparto es una decisión tuya, no un dato
del banco. Es el único input manual que el sistema realmente necesita.

---

## 3. Propuesta

### 3.1 Principio

> La **posición** (apertura↔cierre, capital, interés, retención, plazo) es la fuente de
> verdad. Los pagos fijos de `pagos.csv` pasan a ser **salida generada**, no entrada
> manual.

Esto es exactamente el patrón que ya estableciste en Fondos: un fondo genera su grupo
`Pagos <fondo>` con `fondo_origen` apuntando de vuelta, de forma idempotente
(`routes/funds.py:127`). Aquí se reutiliza tal cual.

### 3.2 Modelo de datos

Archivo nuevo `data/sistema/inversiones/posiciones.csv`, con el mismo estilo CSV +
storage class que `variables_storage.py`:

| columna | tipo | origen |
|---|---|---|
| `id` | uuid | generado |
| `portafolio_id` | fk → `grupos.csv` | **manual** (o heredado del anterior) |
| `tipo` | `plazo_fijo` \| `valuada` | manual, default `plazo_fijo` |
| `fecha_apertura` | date | detectado |
| `fecha_cierre` | date \| null | detectado |
| `estado` | `abierta` \| `cerrada` \| `manual` | derivado |
| `origen` | `detectado` \| `manual` | según quién la creó |
| `plazo_pactado_dias` | int \| null | **manual, opcional** |
| `tasa_pactada` | float \| null | **manual, opcional** |
| `institucion` | str | **manual**, default "Pichincha" |
| `moneda` | str | default `USD` |
| `nota` | str | manual |

Los montos **no** van aquí — viven en `movimientos.csv` (§3.2.1). `capital`, `interes` y
`retencion` son derivados, y `origen='manual'` es lo que protege tus siembras de que el
detector las pise.

Los portafolios siguen siendo grupos `fixed` en `grupos.csv` (`Inversiones_Mias`,
`_Uni`, `_Madre`) — no hay que migrar nada. Se les puede añadir bandera `es_inversion`
al lado de `es_fondo`, o simplemente marcarlos por `fondo_origen`/convención de nombre.

**Reparto multi-portafolio:** si un CDT junta plata de varios portafolios (caso 38.000),
se guarda como *N posiciones hermanas* con el mismo `tx_apertura_id` y capitales que
suman el total. La UI ofrece "dividir posición" cuando el capital nuevo no calza con el
residual de un solo portafolio.

### 3.2.1 Dejar lugar a las inversiones externas

**Dato confirmado: en el futuro sí habrá inversiones fuera del banco.** No hay que
construirlas ahora, pero sí evitar que el modelo las haga imposibles. Dos decisiones
bastan para eso, y ninguna cuesta trabajo hoy:

**(a) La posición no guarda montos; los guardan sus movimientos.** De ahí que
`capital`/`interes`/`retencion` no sean columnas de `posiciones.csv` sino filas de
`data/sistema/inversiones/movimientos.csv`:

| columna | |
|---|---|
| `id`, `posicion_id` | |
| `fecha` | |
| `tipo` | `aporte` \| `retiro` \| `interes` \| `retencion` \| `comision` \| `dividendo` |
| `monto` | |
| `tx_id` | fk a banca, o vacío si el dinero no pasó por la cuenta |

Un plazo fijo genera 3-4 movimientos automáticos y se ve idéntico a hoy. Una posición en
cripto o acciones genera aportes y retiros parciales, que es justo lo que el esquema
plano no soporta. El campo `capital` de §3.2 pasa a ser derivado
(`Σ aportes − Σ retiros`), y las columnas de montos desaparecen de `posiciones.csv`.

**(b) `tipo` de posición decide cómo se valúa.**
- `plazo_fijo` → valor = capital + interés devengado. Determinista, lo que ya tenemos.
- `valuada` → valor = precio × cantidad a una fecha, con un `valuaciones.csv`
  (`posicion_id`, `fecha`, `valor`). Cripto, acciones, fondos.

La capa de métricas se escribe una sola vez sobre movimientos, no sobre plazos fijos:
**XIRR** generaliza la TNA y funciona para ambos tipos. Para un plazo fijo, XIRR ≈ TEA,
así que no se pierde nada y no hay que reescribir métricas cuando lleguen las externas.

**(c) La neutralización depende del dinero, no del tipo.** Un pago fijo existe para tapar
un movimiento que sí tocó tu cuenta bancaria. Regla: **se neutraliza el movimiento que
tiene `tx_id`**. Una compra de cripto pagada por transferencia desde el Pichincha se
neutraliza igual que un CDT; una posición que nunca tocó la cuenta no genera pago fijo
alguno. Sale gratis y evita el error clásico de neutralizar plata que nunca se movió.

### 3.3 Backend

```
services/investments/
   detector.py     # empareja aperturas↔cierres sobre banca_unida (la lógica de §2)
   posiciones.py   # CRUD sobre posiciones.csv + reconciliación con el detector
   metricas.py     # TNA, TEA, plazo medio, capital-día, interés devengado
   neutralizacion.py  # posiciones -> pagos fijos (patrón fondo_origen)
storage/investments_storage.py
routes/investments.py   # ampliado
```

Endpoints:

| método | ruta | qué hace |
|---|---|---|
| `GET` | `/api/investments/positions` | posiciones + métricas, filtrable por portafolio/estado |
| `POST` | `/api/investments/detect` | corre el detector y devuelve **diff** contra lo guardado (nuevas, cambiadas, huérfanas) |
| `POST` | `/api/investments/positions` | crear/sembrar manual (las 3 pre-historial) |
| `PUT/DELETE` | `/api/investments/positions/{id}` | editar / borrar |
| `POST` | `/api/investments/positions/{id}/split` | repartir capital entre portafolios |
| `POST` | `/api/investments/generate-payments` | regenera los pagos fijos de neutralización, idempotente |
| `GET` | `/api/investments/summary` | KPIs globales y por portafolio |
| `GET` | `/api/investments/timeline` | serie diaria de capital invertido + interés acumulado |

`detect` devuelve un diff en vez de escribir directo — así nunca pisa una corrección
manual tuya, y confirmas desde la UI. Mismo espíritu que el flujo de undo del etiquetado.

### 3.4 Corregir el detector actual

Independiente de todo lo demás, `investment_service.py` tiene que:

- descartar como cierre toda fila `CANCELACION PLAZO FIJO` que no calce con un capital
  abierto (esas son intereses);
- reconocer `REGULARIZACIÓN DE TRANSACCIÓN` además de `TRANSFERENCIA INTERIOR` y de la
  segunda `CANCELACION`;
- aceptar `RETENCION 2% RENDIMIENTO FINANCIERO` (ya lo hace por `str.contains`, pero hoy
  el filtro es igualdad exacta en `investment_service.py:50`);
- agrupar por marca de tiempo con tolerancia (mismo día) en vez de igualdad de
  `Timestamp`.

### 3.5 Neutralización automática

`generate-payments` recorre las posiciones ordenadas por fecha y emite, por portafolio,
el escalón residual:

```
residual(t) = residual(t⁻) + capital_devuelto + interes − retencion − capital_invertido
```

y lo materializa como pagos del grupo `Pagos Inversiones_Mias` con
`fondo_origen = <id del portafolio>` — borrando y reconstruyendo el grupo, igual que
`funds.py:143`. Los grupos actuales `Inversiones_Mias`/`_Uni`/`_Madre` quedan como
portafolios (metadatos), y sus pagos manuales se migran una sola vez.

### 3.5.1 Protocolo de migración sin pérdida

**Decisión tomada: los pagos fijos se migran y el módulo pasa a generarlos.** Esta es la
fase con más superficie, así que va con red.

**El invariante que hay que preservar no son las filas, es la función escalón.** Dos
conjuntos distintos de pagos pueden producir el mismo `PAGOS_FIJOS(t)`. Lo que no puede
cambiar es la serie diaria evaluada. Test de equivalencia:

```
para cada día del historial:
    PAGOS_FIJOS_antes(t) == PAGOS_FIJOS_despues(t)   ± $0.01
```

evaluado con el mismo `VirtualItemsProcessor`, no comparando CSVs. Si eso pasa, el
dashboard es matemáticamente idéntico y la migración es invisible.

**A favor nuestro hay un detalle del código:** `PAGOS_FIJOS` se arma leyendo *todos* los
grupos (`dashboard_service.py:201`) y filtrando por `type == 'fixed'` — nunca por
`group_id`. Es decir, **mover un pago de `Inversiones_Mias` a `Pagos Inversiones_Mias` no
cambia absolutamente nada** mientras monto y fechas se conserven. La migración de
pertenencia es gratis; lo único que hay que validar es la aritmética del generador.

Pasos, en orden:

1. **Respaldo.** `pagos.csv.bak` y `grupos.csv.bak` ya existen como convención del repo;
   además, snapshot fechado antes de escribir. Nada se borra hasta el paso 6.
2. **Sembrar lo no derivable.** Estas filas no salen del banco y hay que meterlas a mano
   como posiciones `estado='manual'` antes de generar nada:
   - `Inversiones_Uni` 10.100 (cierre 2024-05-29, apertura fuera del historial)
   - las dos cancelaciones de 2024-10-25 (12.854,21 y 682,63)
   - `Inversiones_Uni (madre terjeta)` 3.228
   - `Mis Depositos` −600 "Inversiones para corregir"
   - `Inversiones_Madre` 647 (abierto, sin `end_date`)
   Cada una queda con `origen='manual'` y el generador las respeta tal cual.
3. **Generar en sombra.** `generate-payments` escribe en grupos nuevos
   `Pagos Inversiones_X` con `fondo_origen`, **sin tocar los originales**. Durante esta
   fase los pagos están duplicados, así que los grupos sombra nacen con `type='shadow'`
   para que `VirtualItemsProcessor` los ignore (solo aplica `fixed` e `interpolated`).
4. **Diferencia.** Endpoint que evalúa las dos series escalón y devuelve los días que no
   cuadran, con el detalle de qué pago aporta qué. Aquí es donde vas a ver si el modelo
   de residuales reproduce tu contabilidad o si hay un caso que no anticipé.
5. **Cerrar la brecha.** Cada día descuadrado es una de dos cosas: un reparto
   multi-portafolio que hay que declarar (como el CDT de 38.000 = 28.154 Mías + 10.389
   Madre), o un ajuste manual tuyo que hay que sembrar como en el paso 2. Se itera hasta
   que la diferencia sea cero.
6. **Corte.** Los grupos sombra pasan a `type='fixed'` y los pagos de los grupos
   originales se vacían — en la misma operación, para que nunca exista un instante con
   ambos activos ni con ninguno. Los grupos `Inversiones_Mias`/`_Uni`/`_Madre` sobreviven
   como portafolios (metadatos), sin pagos.
7. **Reversa.** Mientras exista el `.bak` y las posiciones sembradas, el paso 6 se
   deshace restaurando dos CSVs. Conviene dejarlo escrito como comando.

Ya validé la aritmética del generador contra `Inversiones_Mias` completo (§2.1) y calza
al centavo. Falta hacer lo mismo con `_Uni` y `_Madre`, que es exactamente lo que el
paso 4 automatiza.

### 3.6 Conectar el patrimonio — apagado por defecto, con toggle

**Decisión tomada: el patrimonio por defecto NO incluye el capital invertido.** Se añade
un toggle que lo suma. **Y suma solo lo propio:** `Inversiones_Uni` e `Inversiones_Madre`
están marcados `es_custodia`, así que su capital nunca entra a `NOTIONCUM` — solo
`Inversiones_Mias`.

La forma segura de hacerlo es **calcular las dos series siempre y no tocar `TOTAL`**:

```python
# dashboard_service.py:_calculate_total
df['TOTAL'] = (                       # ← intacto, byte por byte igual a hoy
    df['saldo_sin_inversion'] + df[col_interpolado] - df[col_tarjeta] + df[col_deuda_acumulada]
)
df['TOTAL_CON_INVERSIONES'] = df['TOTAL'] + df[col_notion]
```

`NOTIONCUM` se llena con el capital vivo en cada fecha (`transform_investments` es el
lugar natural, una vez arreglado el §1.4). El toggle del frontend elige qué serie grafica;
ningún consumidor actual cambia de comportamiento si no lo activas.

**Ojo con `VariationsChart`.** Ahí sí hay un efecto colateral aunque el toggle esté
apagado: `diff_notion` se calcula en `dashboard_service.py:296` y el componente
"Inversiones" del desglose diario lo lee (`VariationsChart.tsx:222`). Hoy vale cero
siempre; al llenar `NOTIONCUM` empezaría a moverse, pero `total_change` (que es
`diff_total`, `dashboard_service.py:444`) seguiría sin incluirlo — el desglose dejaría de
cuadrar y el descuadre caería en `unexplained_difference`.

Por eso el toggle tiene que ser **un parámetro del backend, no un switch de vista**:
`GET /api/dashboard?incluir_inversiones=true` decide si `TOTAL` lleva `NOTIONCUM` y, en
consecuencia, si el desglose de variaciones lo cuenta. Así las dos vistas cuadran
internamente cada una por su lado. Con el flag apagado (default) `diff_notion` se fuerza
a `0.0` y todo queda exactamente como hoy.

---

## 4. La sección de Inversiones

Sacarla de ser un tab de *Variables* y darle entrada propia en el `Sidebar`
(`TrendingUp`, entre Fondos y Variables). Estructura en cuatro pestañas:

**Posiciones** — tabla maestra. Columnas: portafolio, apertura, cierre, días, capital,
interés, retención, neto, TNA. Fila expandible con las transacciones bancarias que la
originan. Las abiertas arriba con días restantes y **interés devengado estimado**
(`capital × tasa × días_transcurridos / 365`).

**Resumen** — KPIs: capital invertido hoy, interés cobrado histórico, interés neto,
TNA ponderada, retención acumulada, capital-día (19,6 M USD·día hasta hoy),
próximo vencimiento. Desglose por portafolio (Mías / Uni / Madre) con su propio capital
y rendimiento — hoy no puedes responder "¿cuánto ha rendido la plata de mi mamá?".

**Evolución** — el gráfico que falta: área de capital invertido en el tiempo + línea de
interés acumulado + puntos de apertura/cierre. Encima, la serie de TNA por posición, que
es donde se ve el desplome de 7 % → 3 %. El `InvestmentChart` actual (saldo vs. inversión)
se conserva como vista secundaria de auditoría.

**Conciliación** — el diff del detector: posiciones nuevas detectadas por confirmar,
cancelaciones sin apertura, aperturas sin cerrar hace más de X días, y el botón de
regenerar pagos fijos con preview del antes/después. Es la pantalla que reemplaza el
`PaymentCRUD` a mano.

Reutilizar tal cual el lenguaje visual de Fondos/Deudas (`bg-surface-900/50`,
`backdrop-blur-xl`, `rounded-xl`, `border-white/[0.06]`); nada de sistema nuevo.

---

## 5. Fases

| # | Fase | Entrega | Riesgo |
|---|---|---|---|
| 0 | ~~**Limpiar `INVERSION`**~~ ✅ | filtrar por `type=='fixed'` en `transform_investments` (§1.4) | nulo — hoy la columna está mal |
| 1 | ~~**Detector correcto**~~ ✅ | `detector.py` + tests con los 14 casos reales; arregla el bug de las 22 "finalizadas" | nulo, es solo lectura |
| 2 | ~~**Persistencia**~~ ✅ | `posiciones.csv` + `movimientos.csv`, storage, CRUD, siembra de las 5 manuales | bajo |
| 3 | ~~**Métricas + Resumen**~~ ✅ | `metricas.py` (XIRR) y las pestañas Posiciones/Resumen | bajo |
| 4 | ~~**Evolución + Conciliación**~~ ✅ | gráficos y pantalla de diff del detector | bajo |
| 5 | ~~**Patrimonio con toggle**~~ ✅ | `NOTIONCUM` real + `TOTAL_CON_INVERSIONES` + flag de API | bajo — el default no cambia |
| 6 | **Migración de pagos fijos** | ⚠️ previsualización hecha; falta el corte (§3.5.1) | **el único delicado** |

Cambié el orden respecto a la versión anterior: como el patrimonio ahora es
*opt-in*, la fase 5 dejó de ser riesgosa y bajó de prioridad; y la conciliación sube,
porque su pantalla de diff es justamente la herramienta con la que vas a validar la
fase 6. Las fases 0–4 no tocan ni un número de las pantallas que ya usas.

### Fases 0 y 1 — hechas (2026-08-11)

- `transformations/investments.py` filtra por `type=='fixed'`. Impacto medido sobre los
  datos reales: **431 de 1122 filas** tenían la columna `INVERSION` contaminada, con
  hasta **410 USD** de desviación (los pagos interpolados de `Mensual_Madre`, 22 pagos
  de un grupo que no debía entrar).
- `services/investments/detector.py` — 14/14 posiciones, 2 huérfanas agrupadas, interés
  total 3.601,07. Emparejamiento FIFO por capital exacto, lista blanca de descripciones
  para el interés, prorrateo marcado como `ambiguo` si varias cancelaciones comparten
  marca de tiempo.
- `investment_service.get_investments_from_accounts()` delega en el detector: el endpoint
  pasó de reportar **22 inversiones cerradas a 14**, con apertura, plazo y TNA por
  posición, y expone las huérfanas para la pantalla de conciliación.
- `tests/test_investment_detector.py` — 36 tests. El historial real va copiado como
  literal en el propio test, así que la suite sigue sin leer `data/`.

**Hallazgo para la fase 3 (métricas):** la TNA calculada con días calendario **no es la
tasa pactada**. La posición 2025-11-18 → 2025-12-19 son 31 días calendario, pero el
interés (67,43 sobre 27.000) corresponde a 30 días al 3 % con base 360 — el banco liquida
sobre plazo pactado/360, no sobre calendario/365. Las cuatro posiciones de 2026 dan
2,94 % calendario y 3,00 % pactado. Sirve para comparar posiciones entre sí, pero la
tasa real necesita capturar `plazo_pactado_dias`; conviene pedirlo en la UI al confirmar
una posición detectada. (La fase 2 ya expone `tna_pactada` en cuanto ese campo tenga
valor; lo que falta es pedirlo.)

### Fase 2 — hecha (2026-08-12)

- `storage/investments_storage.py` — `posiciones.csv` + `movimientos.csv` con CRUD plano.
  El CSV se lee y se escribe como texto y se convierte en funciones de normalización, sin
  dtypes de pandas en el medio: con inferencia, una columna con un solo valor volvía
  `plazo_pactado_dias` un `30.0`, y con `dtype=str` pandas 3 ni siquiera deja escribir un
  int encima.
- `services/investments/posiciones.py` — CRUD de dominio con validación, derivados
  (`capital`, `capital_vigente`, `interes`, `retencion`, `neto`, `dias`, `tna`,
  `tna_pactada`) y la reconciliación contra el detector.
- Endpoints: `GET/POST /positions`, `GET/PUT/DELETE /positions/{id}`, `GET /portfolios`,
  `POST /detect` (diff, no escribe) y `POST /detect/apply` (confirma el diff).
- `tests/test_investment_posiciones.py` (45) y 11 tests nuevos de rutas. Todos contra CSV
  en `tmp_path`; ninguno lee `data/`.

**Tres decisiones que el plan no traía:**

1. **Un tercer `tipo`: `ajuste`.** Tres de las cinco siembras no son inversiones — son
   plata de inversión moviéndose sin entrar a ninguna posición (la inyección de 3.228 de
   la tarjeta de la madre, la corrección de −600, los 647 sueltos). Sin un tipo aparte
   habría que contarlas como capital invertido en los KPIs, que es falso; con él, el
   escalón de la fase 6 se sigue pudiendo reproducir. Un tramo acotado se guarda como par
   de movimientos opuestos (retiro que lo abre, aporte que lo cierra).
2. **Las siembras tienen id fijo** (`siembra-uni-2024-05-29`, …), así que el script es
   idempotente sin heurísticas y `--rehacer` sabe exactamente qué borrar.
3. **`es_inversion` en `grupos.csv`**, al lado de `es_fondo`. `list_portfolios()` también
   devuelve grupos sin la bandera que ya tengan posiciones apuntándoles, para que una
   posición no desaparezca de la UI por un olvido.

**Estado de los datos tras `scripts/sembrar_posiciones_inversion.py`:** 5 posiciones
sembradas, **cero huérfanas sin cubrir**, y las 14 detectadas siguen pendientes de
confirmar a propósito — a qué portafolio va cada CDT es una decisión tuya, y ese es
justamente el trabajo de la pantalla de Conciliación (fase 4). Para confirmarlas de una
vez: `POST /api/investments/detect/apply` con `asignaciones`.

**Dos cosas que va a encontrar la fase 6:**

- La cadena de `Inversiones_Uni` no cierra al centavo como la de `Mias`: 10.100 + 172,21
  − 3,44 = 10.268,77, pero el pago siguiente dice 10.272 (3,23 de diferencia). Es un
  ajuste a mano viejo, no un fallo del detector.
- Los 647 de `Inversiones_Madre` están **dos veces** en `pagos.csv`: uno abierto desde
  2025-12-22 y otro 2025-12-22 → 2026-03-02 («Lo que sobra»). Sembré solo el abierto; el
  otro hay que decidir si es duplicado o un tramo real.

### Fases 3 y 4 — hechas (2026-08-12)

**Portafolios inferidos de los pagos** (`services/investments/portafolios.py`). El banco
no dice de quién es cada certificado, pero las cadenas de residuales de `pagos.csv` sí:
cambian exactamente los días en que una inversión de ese portafolio se abre o se cierra.

    portafolio  =  el que tiene pagos que empiezan o terminan justo en la apertura y en el cierre

Sobre los datos reales acierta **13 de 14 sin ambigüedad**. La catorceava es el CDT de
38.000 del 2025-08-12, donde dos portafolios tienen frontera ese día — que es justo lo
esperado, porque juntó plata de dos. Y cuánto puso cada uno también se deriva: el residual
del día anterior menos el del propio día da **27.611 de `Mias` + 10.389 de `Madre` =
38.000 exacto**. La sugerencia nunca se aplica sola cuando hay reparto: eso lo confirma
el usuario.

**Posiciones hermanas.** Un certificado repartido se guarda como N posiciones con el mismo
`tx_apertura_id`; la reconciliación las agrupa y compara la **suma** contra el banco, así
que el certificado sigue cuadrando. Nacen `origen='manual'`, lo que además las protege de
que una corrida del detector deshaga el reparto.

**`metricas.py`** — tres medidas que responden preguntas distintas: TNA por posición
(comparar dos certificados), TNA ponderada por capital-día (cuánto rindió el conjunto) y
**XIRR** por bisección (la única que aguanta aportes parciales, y por eso la que va a
seguir sirviendo con inversiones externas). Más devengo de las abiertas (base 360, solo si
hay tasa pactada), capital-día, próximo vencimiento y desglose por año.

**Endpoints nuevos:** `GET /summary`, `GET /timeline`, `POST /positions/{id}/split`, y
`POST /detect` ahora adjunta la sugerencia de portafolio a cada posición nueva.

**Frontend:** entrada propia en el Sidebar (`TrendingUp`, entre Fondos y Variables) y
`pages/Investments.tsx` con las cuatro pestañas — Posiciones (tabla maestra con fila
expandible, movimientos y captura de plazo/tasa pactados), Resumen (KPIs con selector
propio/custodia/todo, por portafolio y por año), Evolución (área de capital + línea de
interés acumulado + dispersión de TNA donde el punto es el capital) y Conciliación (el
diff con su sugerencia y los botones de confirmar).

**Un detalle que costó encontrar:** la TNA ponderada de 2024 daba **34 %**. Las dos
posiciones sembradas sin fecha de apertura no aportan capital-día, pero su interés sí
estaba en el numerador. Ahora quedan fuera de las dos partes de la división y el resumen
reporta cuántas excluyó (`sin_apertura`).

Números finales sobre los datos reales, ya con los 14 CDT confirmados y el reparto hecho:

| ámbito | rotado | interés | TNA pond. | XIRR |
|---|---:|---:|---:|---:|
| propio (`Mias`) | 190.915 | 2.457,31 | 6,87 % | 7,02 % |
| custodia (`Uni` + `Madre`) | 92.532 | 1.998,60 | 6,15 % | 6,99 % |
| todo | 283.447 | 4.455,91 | 6,62 % | 7,01 % |

y la caída año a año: **7,49 % (2024) → 7,02 % (2025) → 3,35 % (2026)**.

### Fase 6 — previsualización (2026-08-12)

El generador existe, la comparación existe, la pantalla existe. **Nada escribe en
`pagos.csv`**: los pasos 3 a 6 del protocolo (§3.5.1) siguen pendientes.

`services/investments/neutralizacion.py` deriva los pagos fijos de las posiciones con la
cuenta de §3.5 y los compara contra los escritos a mano. Cuatro decisiones que no estaban
en el plan:

1. **La semántica es la del dashboard, no la del CSV.** `_apply_fixed_payment` aplica
   `start <= FECHA < end` y **descarta los pagos sin `start_date`**. Hay 2 filas así en
   los datos reales (26.000 de `Mias`, 10.100 de `Uni`): existen y no hacen nada.
   `pagos_actuales()` lee el CSV crudo a propósito para poder mostrarlas con `aplica=False`
   — `get_payments()` las descarta antes de que se vean.
2. **El aporte de una posición sin `fecha_apertura` no cuenta para el residual.** Son las
   sembradas a mano: su aporte lleva una fecha estimada para que las métricas tengan
   capital, pero esa plata nunca estuvo suelta en la ventana visible. Contarla hundía el
   residual de `Madre` 12.854 durante siete meses.
3. **`saldo_inicial_sugerido` = la diferencia del primer día**, no la mediana ni el valor
   más repetido. Es la definición literal de saldo inicial. El "más repetido" fallaba en
   `Madre`, donde disfrazaba de siembra un descuadre real de 3.533.
4. **Dos tolerancias.** `TOLERANCIA = 0,01` y `TOLERANCIA_REDONDEO = 2,0`. Los pagos a mano
   están redondeados a enteros (27.897 donde el banco dice 27.897,57), así que un par de
   dólares es redondeo del usuario y no error del generador.

`preview()` hace **dos pasadas**: la primera detecta el saldo inicial de cada portafolio,
la segunda regenera ya con esos saldos puestos. Sin esa separación la pantalla confunde
"falta configurar una constante" con "la contabilidad no coincide".

Endpoint `GET /api/investments/neutralization/preview` (solo lectura) y quinta pestaña
`NeutralizationTab.tsx`.

**El diagnóstico sobre los datos reales — y por qué la fase no puede cerrarse todavía:**

| portafolio | pagos a mano → generados | siembra sugerida | días con descuadre real | desvío máx. |
|---|---|---:|---:|---:|
| `Inversiones_Mias` | 13 → 14 | **26.000,00** | 17 de 1.320 | 27.066,42 |
| `Inversiones_Uni` | 12 → 12 | **3.177,00** | 878 de 9.721 | 14.127,67 |
| `Inversiones_Madre` | 7 → 8 | **−0,84** | 633 de 657 | 13.335,05 |

- **`Mias` reproduce la contabilidad.** Con la siembra de 26.000 las diferencias son de
  ±1,38 en todo el historial. Los 17 días descuadrados son del 2026-07-27 a hoy: el
  generador ya sabe que el CDT de 27.000 cerró y `pagos.csv` todavía no. Es información
  que le falta al CSV, no un fallo del generador.
- **`Uni` tiene descuadres reales** de miles en cuatro tramos largos (2024-06-04→2024-09-03,
  2024-11-18→2025-03-18, 2025-04-28→2025-09-24, 2025-10-24→2026-03-18).
- **`Madre` tiene dos huecos**: 3.533 en 2024-11-18→2025-06-16 (al abrir el CDT de 10.003
  se dieron por consumidos los 13.536 completos) y 13.335 desde 2026-03-02.

### Por qué divergían — resuelto (2026-08-12)

**Los pagos escritos a mano no estaban mal.** Los dos sistemas miden cosas distintas: los
del usuario dicen *cuánta plata de inversión existe*; el generador dice *cuánto salió de
certificados y no volvió a entrar*. Coinciden en `Mias`, donde nunca sale plata, y se
separan en `Uni` y `Madre`, donde sí.

Cada vez que vence un certificado de `Uni` salen ~3.2xx que se van en **matrícula** y no
se reinvierten. Los ciclos lo muestran sin ambigüedad:

| vence | sale del certificado | se reinvierte | no vuelve | lo escrito a mano |
|---|---:|---:|---:|---|
| 2024-09-04 | 10.482,64 | 6.648,00 | **3.834,64** | 7.258 + **3.228** |
| 2025-03-19 | 10.530,74 | 7.317,00 | **3.213,74** | 7.317 + **3.213** |
| 2025-09-25 | 7.481,33 | 4.214,00 | **3.267,33** | 4.214 + **3.267** |
| 2026-03-19 | 4.279,26 | — | **4.279,26** | **3.279 + 1.000** |

La columna de la derecha calza con "sale" cada vez: el usuario **sí** registraba esas
salidas, pero solo como la *fecha de fin* de un pago fijo. Ninguna de las dos puntas es
una operación de certificado, así que el banco no la delata y el generador no puede
verla. La suma cierra al centavo:

```
Uni:    3.177 − 9,23 + 3.834,64 − 3.635,07 + 3.213,74 + 3.267,33 + 4.279,26 = 14.127,67
Madre:  −0,84 + 3.533,84 + 0,95 + 1,13 + 10.446,97                          = 13.982,05
```

que son exactamente los residuales finales del generador.

**La solución: un cuarto `tipo`, `flujo`** — dinero que entra o sale del portafolio y **no
vuelve**. Es distinto de un `ajuste` justamente en eso: el ajuste es un tramo acotado que
se cierra y devuelve la plata. Una salida es un movimiento `aporte` (SIGNO −1) y una
entrada un `retiro` (+1), así que el residual sale solo, sin código nuevo. Es
instantáneo (`fecha_apertura == fecha_cierre`), nace `origen='manual'` y el monto es
siempre positivo: el signo lo da la dirección.

`POST /api/investments/flows`, `GET /api/investments/flows/preview` (residual
antes/después, sin escribir) y el botón «Registrar salida» en la pestaña de Posiciones.

**Bug arreglado de paso:** `flujos_de()` no filtraba por tipo, así que los `ajuste` ya
entraban en el XIRR. Con matrículas registradas eso habría convertido el rendimiento en
una pérdida enorme que nunca existió.

**Y dos `ajuste` que contaban plata dos veces.** `siembra-uni-madre-tarjeta` (3.228) decía
en su nota «3.228 que *entraron* al portafolio» pero estaba escrito como `aporte`, o sea
saliendo — y ninguna lectura era correcta: esos 3.228 son parte de los 10.482,64 que
devolvió el CDT ese día, en una segunda fila de `pagos.csv` solo para etiquetarlos.
`siembra-madre-647` decía «los 647 que *sobraron*», que es el residual mismo. Los dos se
borraron, también del script que los creaba.

**Aplicado sobre los datos reales:**

| portafolio | antes | + 10 flujos | − 2 `ajuste` |
|---|---:|---:|---:|
| `Inversiones_Uni` | 14.127,67 | 3.240,59 | **12,59** |
| `Inversiones_Madre` | 13.335,05 | 1.292,79 | **645,79** |
| `Inversiones_Mias` | 27.066,42 | igual | igual |

Lo que queda son dos ediciones de `pagos.csv`, que el usuario pidió no tocar: la fila
duplicada de 647 (dejaría `Madre` en 1,24) y el cierre del CDT del 2026-07-27 (todo lo de
`Mias`). El módulo sigue sin escribir una sola línea en `pagos.csv`.

### Fase 5 — hecha (2026-08-12)

El patrimonio ya puede incluir el capital invertido, **apagado por defecto**.

`services/investments/patrimonio.py` devuelve, por día, el capital propio que estaba
dentro de una posición. Dos reglas deciden qué entra: solo lo **propio** (`Uni` y `Madre`
son `es_custodia`; una posición sin portafolio cuenta como propia, igual criterio que
`metricas.resumen`) y solo lo que está **dentro de una posición** (los `ajuste` quedan
fuera: son plata suelta que el saldo bancario ya muestra, y sumarla la duplicaría). El
interés devengado de las abiertas no se suma — es una estimación, y el patrimonio no es
lugar para estimaciones.

**Las dos series se calculan siempre y el flag vive en la respuesta, no en el pipeline.**
La transformación `capital_invertido` llena `NOTIONCUM` antes de `dashboard_metrics`, y
`MetricProcessor` emite `TOTAL` (intacto) y `TOTAL_CON_INVERSIONES = TOTAL + NOTIONCUM`.
Quien elige es `_build_response`. Así el caché del pipeline no se parte en dos por un flag
de petición y cada vista cuadra internamente por su lado.

`GET /api/dashboard/chart-data?incluir_inversiones=true` y el mismo parámetro en
`/variations`, que **tiene que ir igual en las dos**: el desglose diario se contrasta
contra el mismo total. En el frontend el toggle vive en `App.tsx` (por eso mismo: las dos
pestañas del dashboard tienen que pedir lo mismo) y entra en la `queryKey`.

**Dos cosas que el plan no anticipó:**

1. **`diff_notion` forzado a cero con el flag apagado** era necesario pero no suficiente.
   `VariationsAnalyzer` calcula `residual = diff_total − drivers`, y `diff_notion` no tiene
   transacción propia (abrir un CDT ya aparece como movimiento del banco *y* como pago
   fijo; el capital invertido es el mismo dinero visto del otro lado). Con el toggle
   encendido, el día del CDT de 28.304 el desglose lo declaraba entero "sin explicar".
   Ahora el residual descuenta `d_notion`; con el toggle apagado vale 0 y no cambia nada.
2. **`Col` es un `(str, Enum)`**, así que `df[Col.NOTIONCUM]` encuentra la columna por
   igualdad, pero el Index se queda con el miembro del enum y al exportar a CSV el
   encabezado sale `Col.NOTIONCUM`. Las columnas se escriben con `.value`.

Verificado sobre los datos reales: `TOTAL` se reconstruye **exacto** con su fórmula
original (máx. desvío 0,0000000000), `NOTIONCUM` va de 0 a 28.304, el desglose cuadra en
las dos vistas con el mismo residual máximo, y **hoy el capital propio vivo es 0** — el
último CDT cerró el 2026-07-27, así que el toggle cambia la historia pero no la cifra de
hoy.

---

## 6. Decisiones

### Resueltas (2026-08-11)

1. **Patrimonio:** por defecto **no** incluye el capital invertido; se agrega un toggle
   que lo suma. → §3.6, fase 5.
2. **Pagos fijos:** se **migran** y el módulo pasa a generarlos, con protocolo de corte
   sin pérdida. → §3.5.1, fase 6.
3. **Inversiones externas:** **sí las habrá** más adelante. No se construyen ahora, pero
   el modelo se diseña desde el principio con movimientos + valuaciones para no rehacerlo.
   → §3.2.1.

### Resueltas (2026-08-12)

4. **`Inversiones_Madre` e `Inversiones_Uni` no son patrimonio propio.** Las dos son
   custodia: se siguen exactamente igual que las demás, pero nunca suman a *tu* patrimonio.
   Implementado como bandera `es_custodia` en `grupos.csv`; el único portafolio propio es
   `Inversiones_Mias`. Cuando llegue la fase 5, el toggle suma solo lo propio.
5. **Los 647 de `Inversiones_Madre` son uno solo y está cerrado** (2025-12-22 → 2026-03-02).
   La otra fila era duplicada.
6. **`Mis Depositos` se queda en Variables** con sus pagos fijos a mano. No entra al módulo
   de inversiones y la corrección de −600 no se siembra.
7. **El plazo pactado se captura en la UI**, en la fila expandible de cada posición. Sin él
   la TNA que se muestra es la de calendario/365; con él aparece la que el banco liquidó
   (plazo/360).
8. **El portafolio de cada posición se infiere de `pagos.csv`**, no se pide a mano. Ver
   fases 3 y 4.

### Abiertas

9. **`Inversiones_Uni` — ¿tiene meta?** (monto objetivo, fecha de matrícula). Si sí, vale
   una vista de progreso contra meta como en Fondos. No bloquea nada.
10. **¿`es_inversion` debería salir del etiquetado?** Hoy es una bandera del grupo, que es
    un objeto distinto de la transacción: la categoría «inversión» y los tags viven en las
    transacciones, no en los portafolios. La bandera solo hace falta para que un portafolio
    recién creado y todavía vacío aparezca en la UI — en cuanto tiene una posición,
    `list_portfolios()` lo encuentra igual. Si prefieres una cosa menos que mantener, se
    puede quitar y quedarse solo con esa segunda regla.
