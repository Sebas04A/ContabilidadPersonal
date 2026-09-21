# Plan: una deuda mía también es un gasto

Cuando alguien paga algo por mí, ese consumo es real pero **no existe en ninguna parte del
análisis**: no hay transacción mía que etiquetar. Este plan le da a esas deudas categoría,
tags, prioridad y felicidad, en su fecha real, sin mover el patrimonio ni un centavo.

> **Cómo se usa este documento.** Es un documento vivo. Cada fase tiene su verificación y su
> casilla; la **§9 Bitácora** se va llenando con lo que se hizo y con lo que se descubrió
> que estaba mal. Si una decisión cambia, se edita la §3 y se anota por qué en la bitácora.
> Nada se da por hecho hasta que su verificación pasó.

Estado: **fases 0 a 4 hechas, backfill cerrado.** El interruptor funciona de punta a punta y
el dashboard no se movió. Se devengaron las **13 del viaje** ($215,75); las tres restantes
($6,24) quedaron fuera por decisión, no por olvido. La fase 5 (fondos) sigue sin decidirse
a propósito.
Última revisión: 2026-09-20.

---

## 1. El problema

### 1.1. El ledger no tiene dónde poner esto

`load_data()` (`contabilidad/backend/services/transaction_service.py:256`) es
`load_source_data()` LEFT JOIN `etiquetas.csv` por `id = source_id`. Y `load_source_data()`
(línea 68) lee **exactamente dos fuentes**: banca y tarjeta.

```
banca['TIPO']   = 'BANCA'      # transaction_service.py:84
tarjeta['TIPO'] = 'TARJETA'    # transaction_service.py:99
```

Si no hubo movimiento en una cuenta mía, no hay fila. Y si no hay fila, no hay `source_id`
al que enganchar una etiqueta. **El etiquetado no es que no cubra las deudas: es que no
tiene a qué agarrarse.**

Del otro lado, una deuda en Supabase tiene cuatro campos de contenido y ninguno es
descriptivo (`deudas/supabase/schema.sql:19`):

```sql
CREATE TABLE deudas (
    id, deudor_id,
    titulo      TEXT,      -- "Almuerzo"
    monto       DECIMAL,
    fecha_gasto DATE,
    es_mi_deuda BOOLEAN    -- true = yo debo pagarle
);
```

Ni categoría, ni tags, ni prioridad, ni felicidad, ni fondo.

### 1.2. Por qué no alcanza con etiquetar el pago de vuelta

La salida obvia —"cuando le pague, etiqueto la transferencia"— falla por tres motivos, en
orden de gravedad:

1. **Con el cruce de cuentas a veces nunca hay transferencia.** Si le debo $20 y él me debe
   $25, `registrar_pago` crea pagos virtuales (`es_compensacion = true`) y las deudas se
   matan entre sí sin que se mueva un dólar. Ese consumo **no aparece jamás**. El netting no
   es un caso raro en este sistema: es su función central (`deudas/LOGICA_SISTEMA.md` §3.2).
2. **La fecha queda mal.** El consumo fue en agosto, el pago en septiembre. Para presupuesto
   mensual, categorías y fondos eso es ruido.
3. **Un pago tapa N deudas de categorías distintas.** Habría que partirlo a mano con
   `split_group_id` cada vez, replicando información que **ya está** en `detalle_pagos`.

### 1.3. El tamaño del agujero, medido

**Medido en vivo contra Supabase el 2026-09-20** (la primera medición, contra el respaldo
`backups/deudas_20260913_180016`, daba 5 deudas y $28,84 — siete días después el número es
casi ocho veces mayor; ver la bitácora de §9):

| | deudas | monto |
|---|---:|---:|
| Deudas totales | 336 | |
| `es_mi_deuda = true` (yo debo) | **18** | $480,34 |
| **Yo debo, sin transacción vinculada** | **16** | **$221,99** |

Las 16 invisibles de hoy:

| fecha | título | monto | quién pagó |
|---|---|---:|---|
| 2026-09-07 | Uber 7 sep debo | 8,55 | Ale |
| 2026-09-07 | Rio Beleza regalos | 26,26 | Ale |
| 2026-09-06 | Carretao | 36,83 | Ale |
| 2026-09-06 | Aqua rio | 43,62 | Ale |
| 2026-09-06 | Burger king | 4,86 | Ale |
| 2026-09-06 | Uber 6 sep debo | 3,84 | Ale |
| 2026-09-06 | Aguas | 0,74 | Ale |
| 2026-09-05 | Rooftop comida | 17,51 | Ale |
| 2026-09-05 | Debo uber | 2,45 | Ale |
| 2026-09-04 | Barzin | 25,82 | Ale |
| 2026-09-04 | Baila baila | 19,48 | Ale |
| 2026-09-04 | Uber debo 4 sep | 4,81 | Ale |
| 2026-08-28 | Caipis y eso | 16,72 | Ale |
| 2026-08-23 | Uber aeropuerto | 5,00 | Ale |
| 2026-05-18 | Shawar.a | 2,50 | rubia |
| 2026-04-13 | Almuerzo | 3,00 | rubia |

**Esto ya no es plata chica, y el caso que lo prueba es el viaje a Brasil.**

`ETIQUETADO_VIAJE_BRASIL_2026.md` analiza el viaje del 22-ago al 06-sep sobre **117
movimientos** de banca y tarjeta. Pero 14 de estas 16 deudas caen dentro de ese período y
**ninguna aparece en ese documento**, porque las pagó Ale y no hay movimiento mío que
analizar:

- Del 4 al 7 de septiembre en Río: **12 deudas, $194,77** — Carretao, Aqua Rio, Barzin,
  Baila baila, Rio Beleza, los Ubers.
- Con "Caipis y eso" (28-ago) y "Uber aeropuerto" (23-ago): **$216,49 del viaje**.
- Fuera del viaje quedan dos, de $5,50 en total.

O sea: **el 97,5% del agujero es el viaje a Brasil**, y el costo real de ese viaje está
subestimado en ~$216 en el único documento que lo analiza. Un viaje compartido es
precisamente el escenario donde uno deja de pagar cada cosa por su cuenta.

**Y la otra lectura sigue en pie, más fuerte:** de 336 deudas solo 18 son mías. No es que
nunca me paguen las cosas; es que registrar "yo debo" **no sirve para nada hoy** más allá
del cruce, así que se registra solo cuando alguien se acuerda. Si etiquetarlas empieza a
servir, el número sube. El plan hay que juzgarlo por lo que habilita, no solo por los $222
que rescata hoy.

> De la primera medición sobrevive un dato que la de hoy no muestra y que es el argumento
> más fuerte del plan: **3 de esas deudas se saldaron solo por cruce**, sin que se moviera
> un dólar mío. Para esas, no existe ni existirá jamás una transacción que etiquetar.

> Aparte: **194 deudas "me deben" ($4.422) no tienen transacción vinculada**. Es otro
> problema (conciliación incompleta: efectivo, o el vínculo que nunca se hizo). Fuera del
> alcance de este plan; anotado en §8.

---

## 2. La decisión

Una deuda mía sin transacción propia pasa a ser **una fila de gasto de pleno derecho**, en
su fecha real, etiquetable con todo lo que ya existe. Esto es **devengo**: el gasto se
reconoce cuando se consume, no cuando sale la plata.

Y como eso rompe la equivalencia "gasto = flujo de caja" que sostiene el dashboard de hoy,
va **detrás de un interruptor, apagado por defecto**.

El interruptor mueve **dos cosas a la vez**, y esa es la parte que hay que entender:

| | modo caja (hoy, por defecto) | modo devengo (opt-in) |
|---|---|---|
| Deuda mía que pagó otro | no existe | **entra como gasto** en `fecha_gasto` |
| Transacción de liquidación (`pago_id`) | cuenta como gasto | **sale**: pagar no es gastar |

Las dos juntas o ninguna. Si solo entran las deudas, se cuenta dos veces; si solo salen las
liquidaciones, desaparece gasto real.

---

## 3. Invariantes (no negociables)

Si alguna de estas se rompe, el cambio se revierte, no se parchea.

- **I1 — El patrimonio no se toca.** Lo que debo y lo que me deben **ya** afecta al
  patrimonio vía `DEUDA_ACUMULADA` (`dashboard_service.py:128` lo construye,
  `dashboard_service.py:283` lo suma a `TOTAL`). Este plan **no modifica esa serie, ni su
  fuente, ni su signo**. El devengo vive en el lado del gasto y solo ahí.
- **I2 — Con el interruptor apagado, la salida es idéntica al centavo.**
  `scripts/snapshot_dashboard.py comparar` tiene que dar cero diferencias.
- **I3 — Ninguna fila `DEUDA` entra a `load_data()`.** Ver §5: hay minas concretas. Las
  filas devengadas se sirven por una función aparte que los consumidores piden a propósito.
- **I4 — Devengar es explícito.** Una deuda no se convierte en gasto sola. Hace falta que yo
  diga que ese consumo fue mío.
- **I5 — El cruce no cambia.** Ni `estado_cuenta()`, ni `registrar_pago`, ni `editar_cruce`,
  ni `detalle_pagos`. Este plan es de solo lectura sobre el dominio de deudas.

---

## 4. El modelo de datos

**Cero tablas nuevas. Cero columnas nuevas.** Una deuda devengada es una fila más en
`etiquetas.csv` con un `source_type` nuevo:

```
source_id   = el UUID de la deuda en Supabase
source_type = 'DEUDA'          ← hoy solo existen 'BANCA' y 'TARJETA'
```

Todas las columnas que ya están funcionan tal cual: `nombre_limpio`, `categoria`, `tags`,
`prioridad`, `es_fijo`, `pertenece_a`, `felicidad`, `revisado`, `nota`, `fondo_id`.

No hay colisión de `source_id`: banca y tarjeta usan hashes md5 de 32 hex, Supabase usa
UUIDs con guiones.

La fila sintética que se construye desde Supabase:

| campo del ledger | de dónde sale |
|---|---|
| `id` | `deudas.id` |
| `FECHA` | `deudas.fecha_gasto` |
| `DESCRIPCION` | `deudas.titulo` |
| `MONTO` | `-deudas.monto` ← **negativo**: en este sistema gasto es negativo |
| `TIPO` | `'DEUDA'` |
| `deudor` | `deudores.nombre` (ya normalizado, ver `scripts/normalizar_deudores.py`) |
| `SALDO_DEUDA` | `deudas.saldo_pendiente` ← **solo en estas filas**; `>0` = todavía la debo |

`SALDO_DEUDA` es lo que permite leer un gasto devengado sin confundirlo con uno de caja:
dice que esa plata **no salió de mis cuentas** y que sigue contada como deuda en el
patrimonio. Va en la fila y **no** en `etiquetas.csv`, por la misma razón que `deudor`: es
estado vivo que cambia con cada pago y con cada cruce. Una columna en el CSV sería una copia
que envejece, y envejecería enseguida — de las 13 deudas devengadas hoy, 12 están pendientes
y una (`Uber aeropuerto`) ya está saldada.

**Qué significa que exista la fila de etiqueta:** que esa deuda es consumo mío y se devenga.
Si una deuda mía **no** es consumo (me prestaron efectivo, por ejemplo — ahí el gasto es en
qué lo usé, no la deuda), simplemente **no se le crea fila**. Por eso hace falta la bandeja
de la fase 4: para que "sin decidir" no se confunda con "decidido que no".

---

## 5. Dónde se enchufa, y sobre todo dónde NO

### 5.1. La tentación y por qué no

Lo natural sería agregar un tercer frame en `load_source_data()` y que todo lo demás lo
herede gratis. **No se hace.** Hay minas concretas, verificadas:

| mina | dónde | qué pasaría |
|---|---|---|
| El filtro clasifica por descarte | `dashboard_service.py:444` → `es_banca = df_tx['TIPO'] == 'BANCA'`, y después `df_tx[~es_banca]` **es tarjeta** | Toda fila `DEUDA` se trataría como consumo de tarjeta y corrompería `ACUMULADO_TARJETA` al filtrar |
| El contrato escrito del filtro | `dashboard_service.py:410-411`: *"Deuda de Supabase, pagos fijos, interpolados y capital invertido no nacen de transacciones etiquetadas: ningún filtro los mueve"* | Una deuda etiquetada rompe esa frase, y con ella la conciliación del desglose |
| Fondos | `fund_service.py:86` llama `load_data()` | Las deudas entrarían a los fondos sin que nadie lo haya decidido (§8) |
| Drivers del desglose | `dashboard_service.py:757` `_process_transactions()` | Aparecerían movimientos que no mueven ningún saldo → `unexplained_difference` |

### 5.2. Lo que sí

Un módulo nuevo y un parámetro:

```
contabilidad/backend/services/debt_expenses.py     ← NUEVO
    cargar_deudas_devengadas() -> DataFrame        # filas sintéticas + sus etiquetas
    es_liquidacion(fila) -> bool                   # transacción con pago_id

contabilidad/backend/services/transaction_service.py
    load_data(devengo: bool = False)               # False ⇒ byte-idéntico a hoy
```

`devengo=True` hace **las dos** cosas de §2: concatena las filas `DEUDA` y marca las
liquidaciones para que el consumidor las descarte. Solo los endpoints de análisis y
presupuesto lo piden. Dashboard, fondos y verificación lo dejan en `False`.

---

## 6. Fases

| # | fase | estado |
|---|---|---|
| 0 | Medir el agujero y congelar el baseline | ✅ **hecha** (2026-09-20) |
| 1 | Lectura: las filas devengadas existen | ✅ **hecha** (2026-09-20) |
| 2 | Escritura: poder etiquetar una deuda | ✅ **hecha** (2026-09-20), falta el backfill |
| 3 | El interruptor de devengo en el análisis | ✅ **hecha** (2026-09-20) |
| 4 | Bandeja de "deudas mías sin decidir" | ✅ **hecha** (2026-09-20) |
| 5 | Fondos y presupuesto (opcional) | ⬜ |

---

### Fase 0 — Red de seguridad

- [x] Medir el agujero contra el respaldo real, y después **en vivo** (§1.3)
- [x] `snapshot_dashboard.py capturar --nombre pre_devengo --via http` con el backend
      levantado (el modo `directo` sin `supabase` deja `DEUDA_ACUMULADA` en cero y el
      snapshot queda ciego justo al componente que hay que proteger)
- [x] Comprobar que la red de seguridad **además de existir, funciona**: comparar contra sí
      misma da `IDÉNTICO`

**Snapshot de referencia:** `backups/dashboard_snapshots/pre_devengo_ordenado.json`
· capturado 2026-09-20 · vía http · 983 días · 983 variaciones
· `deuda_acumulada presente` en las dos variantes (no está ciego a Supabase).

> El primero (`pre_devengo.json`) se capturó **antes** de arreglar el orden no determinista
> de las deudas (ver la bitácora del 2026-09-20). Contra él, el comparador daba IDÉNTICO o
> DIVERGE según la corrida, sin que ningún número cambiara. Se conserva, pero el bueno es
> `pre_devengo_ordenado`.

Cómo levantar el backend sin el frontend (el script `start_contabilidad.sh` levanta los dos):

```bash
env -C <raíz> contabilidad/backend/.venv/bin/python -m uvicorn contabilidad.backend.main:app --port 8000
```

**Verificación — ya pasó:**
```
IDÉNTICO a pre_devengo (tolerancia $0.005). La ruta sin filtro no cambió.
```

---

### Fase 1 — Lectura

Construir `debt_expenses.py`: leer de Supabase las deudas con `es_mi_deuda = true`, armar
las filas sintéticas de §4 y pegarles sus etiquetas. Reutiliza
`obtener_deudas_para_analisis()` (`contabilidad/debts/reading.py:944`), que ya devuelve
`ES_MI_DEUDA` y `SALDO_PENDIENTE`.

- [x] `cargar_deudas_devengadas()` devuelve solo las deudas **con fila en `etiquetas.csv`**
      (I4: sin etiqueta no hay gasto)
- [x] `MONTO` negativo
- [x] `deudor` lo manda Supabase, no la etiqueta (misma regla que `debtPerson` en
      `debtFilters.ts`)
- [x] `HORA = ''` en el origen, en vez de dejar que `_attach_horas()` improvise: una deuda
      no tiene hora y el ledger ya sabe caer al fallback de `FECHA`
- [x] Degrada solo: si Supabase falla, frame vacío y un log, no una excepción que tumbe el
      análisis
- [x] Atajo sin red: sin etiquetas de deuda **ni se consulta Supabase**. Hoy ese es el
      camino normal, y está cubierto por un test que verifica que no se llama
- [x] `tests/test_debt_expenses.py` — 10 casos

**Archivo:** `contabilidad/backend/services/debt_expenses.py`
(`cargar_deudas_devengadas()` y `marcar_liquidaciones()`).

**Verificación — pasó:** `pytest tests/test_debt_expenses.py` → **10 passed**.
Uno de los casos compara las columnas producidas contra las de `load_data()` real, para que
un `concat` en la fase 3 no pueda inventar columnas.
Suite completa: `15401 passed, 3 failed`; los 3 fallos son **previos y ajenos**
(`test_data_pipeline` ×2 y `test_flujo_usuario`, todos sobre el procesado de Excel en
tmpdirs). Ningún archivo de esta fase los toca.

---

### Fase 2 — Escritura

Poder ponerle categoría a una deuda. `save_transaction_labels()`
(`transaction_service.py:310`) **ya recibe** `source_type`, así que el backend es casi un
endpoint nuevo y nada más.

- [x] Tres rutas en `contabilidad/backend/routes/supabase_debts.py`:
      `GET /devengo/pendientes` (con `solo_pendientes`), `PUT /{deuda_id}/etiqueta`,
      `DELETE /{deuda_id}/etiqueta`
- [x] Solo para `ES_MI_DEUDA = true`: una deuda que me deben responde **400** con el motivo
      (su gasto ya está en mi transacción)
- [x] **La baja existe.** Devengar es una decisión y las decisiones se revierten. El DELETE
      borra la fila de `etiquetas.csv` y **no toca Supabase**: la deuda sigue viva, se sigue
      cruzando y sigue pesando en el patrimonio
- [x] UI: `components/DevengoModal.tsx`, propio y chico
- [x] `pages/Debts.tsx`: una tarjeta de deuda mía ahora es clicable y trae distintivo
      **ES GASTO** / **SIN CONTAR**
- [x] `utils/categorias.ts` para no escribir la lista de categorías por quinta vez
- [x] **La fila nueva trae los valores estructurales del resto del CSV**
      (`es_fijo=False`, `pertenece_a='---'`, `es_reembolsable=False`): el modal no los
      pregunta y quedaban en blanco, así que una deuda devengada se leía distinta de una
      transacción etiquetada aunque signifiquen lo mismo. `DEFECTOS_DEVENGO` se aplica
      **solo al alta**; una edición posterior no pisa lo que haya en el archivo. `deudor`
      sigue en blanco a propósito: lo manda Supabase
- [x] **Backfill a mano de las 16 de §1.3** — cerrado en **13** (2026-09-20)
      Devengadas las 13 del viaje, todas con tag `Viaje_RIO`: **$215,75**.
      `Aguas` (0,74 · Ale), `Shawar.a` (2,50 · rubia) y `Almuerzo` (3,00 · rubia) quedan
      **fuera por decisión**: $6,24 que no vale la pena etiquetar
- [x] **La fila devengada dice si la deuda sigue viva** (`SALDO_DEUDA`, §4): mirando el
      gasto se sabe que esa plata no salió de mis cuentas y que ya está contada como deuda

**Por qué un modal propio y no `EditModal`.** El plan decía "ver si se adapta". Se miró:
`EditModal` son ~1.500 líneas de dividir transacciones, vincular deudas, vincular pagos y
guardar reglas de nombre — nada de eso aplica a una deuda (dividir una deuda no significa
nada, y vincularla a sí misma menos). `DevengoModal` pide lo que importa: nombre, categoría,
tags, necesidad/deseo, felicidad y nota.

**Verificación — pasó.**
```
pytest tests/test_routes_devengo.py     → 10 passed
npx tsc --noEmit                        → sin errores
npm test -- --run                       → 25 passed
```
Y una ida y vuelta contra Supabase y el `etiquetas.csv` real:

| paso | resultado |
|---|---|
| `PUT` sobre "Carretao" ($36,83, Ale, 06-sep) | fila escrita con `source_type=DEUDA` |
| `cargar_deudas_devengadas()` | 1 fila, **−36,83**, fecha 2026-09-06, deudor `Ale` |
| `PUT` sobre una deuda que me deben | 400 con el motivo |
| `PUT` sobre una deuda inexistente | 404 |
| `DELETE` | borrada; **`etiquetas.csv` volvió byte a byte al md5 original** |
| `DELETE` otra vez | 404 |

El `.bak` (rodante) quedó pisado por la prueba y se restauró a mano a su contenido previo.

---

### Fase 3 — El interruptor

- [x] `load_data(devengo=False)` — el cuerpo de siempre se mudó a `_load_data_caja()` y el
      camino por defecto es **el mismo objeto de antes**, sin tocar nada
- [x] `debt_expenses.aplicar_devengo(df)` hace las dos mitades y devuelve `(df, resumen)`
- [x] `GET /api/transactions/?devengo=true` y `GET /api/transactions/devengo/resumen`
- [x] Frontend: interruptor **«Lo que se movió» ↔ «Lo que consumí»** en **Presupuesto**
      (con el resumen en el tooltip y memoria en localStorage) y en el **Explorador**
- [x] Tests de ruta: por defecto pide caja, con `devengo=true` pide devengo
- [x] Ningún otro consumidor de `load_data()` cambió de llamada

### El descuento es proporcional, y esto no es un detalle

El plan decía "las liquidaciones salen". Al escribirlo apareció el caso que lo rompe:

> Una transferencia de $25 salda dos deudas: una devengada ($10) y una que no ($15).

Si la liquidación saliera entera, esos **$15 de consumo real desaparecerían** del análisis
—nunca se contaron al consumirse y ahora tampoco al pagarse—. Así que el descuento se
calcula contra `detalle_pagos`, que es la tabla que dice qué deuda saldó cada dólar:

- se descuenta **solo** lo que saldaba deudas devengadas;
- si un pago está vinculado a varias transacciones, el descuento **se reparte** entre ellas
  en vez de aplicarse entero a cada una;
- nunca se descuenta más de lo que la transacción movió;
- si Supabase no devuelve el detalle, **no se ajusta nada** y el resumen lo dice
  (`liquidaciones_sin_detalle`). Mejor el número de hoy que uno inventado.

Con esto, el usuario puede devengar unas deudas sí y otras no sin que el total mienta en
ninguna dirección.

**Verificación — pasó.**
```
pytest tests/test_devengo_switch.py                          → 11 passed
pytest tests/                                                 → 15422 passed, 3 failed (previos)
snapshot_dashboard.py comparar --nombre pre_devengo --via http
      → IDÉNTICO a pre_devengo (tolerancia $0.005)
npx tsc --noEmit / npm test -- --run                          → limpio / 25 passed
```
Y contra los datos reales, etiquetando Carretao ($36,83) y Baila baila ($25,82):

| septiembre 2026 | filas | gasto |
|---|---:|---:|
| `devengo=false` | 48 | $460,19 |
| `devengo=true` | 50 | $516,50 |

La diferencia es **$56,31 = 36,83 + 25,82**, exacta. Las dos etiquetas de prueba se
borraron y `etiquetas.csv` quedó byte-idéntico.

---

### Fase 4 — La bandeja

Sin esto el sistema es un colador silencioso: una deuda que nunca decidí no se distingue de
una que decidí que no era gasto.

- [x] Botón **«Sin contar»** con el número, en la cabecera del tab Deudas
- [x] Despliega la lista y cada una abre su modal, para decidirlas en fila
- [x] La bandeja **no depende del filtro de fechas** del timeline: una deuda de abril
      aparece aunque estés mirando septiembre, y el modal se arma con sus propios datos

- [x] **Se caen las que ya tienen transacción vinculada** (`deuda_id`): si la plata pasó por
      mi cuenta, el gasto ya está contado ahí. Siguen visibles sin el filtro, marcadas con
      `tiene_transaccion`, y el modal avisa en rojo antes de dejar duplicarlas

**Verificación:** hoy marca **16** ($221,99), no 18. El botón desaparece cuando no queda
ninguna.

---

### Fase 5 — Fondos y presupuesto (decidir con datos, no antes)

Una cena que pagó Ale, ¿debería descontar del fondo Comida? Económicamente sí. Pero el fondo
modela **cobertura de plata**, y esa plata no se movió.

**Hoy están aislados y eso es correcto por accidente, no por diseño:**
`fund_service._collect_transaction_movements` llama a `load_data()` sin devengo, así que
ninguna deuda devengada llega a un fondo. Conviene que siga así hasta decidirlo, porque:

1. **Un fondo no es solo una vista.** Con "Crear pagos" sus movimientos se materializan en
   un grupo `fixed` con `fondo_origen`, que alimenta `PAGOS_FIJOS`, y
   `saldo_sin_inversion = SALDO − PAGOS_FIJOS` entra en `TOTAL`. Una deuda devengada que
   entrara al fondo y se materializara **movería el patrimonio**: justo lo que prohíbe I1.
2. **El fondo ya excluye deliberadamente todo lo reembolsable** ("pertenecen a Deudas",
   `fund_service.py`). Una deuda mía es el espejo exacto de eso.
3. **El caso no es teórico.** Existe el fondo **«Viaje Rio»** (`tag_vinculado='Viaje_RIO'`,
   82 movimientos, $1.332,86 de salida, último el 2026-09-03). Las 14 deudas del viaje son
   consumo de ese mismo viaje: el fondo dice que costó $1.332,86 y el consumo real fue
   ~$1.549 (**+16%**). Y como el fondo incluye por **tag**, si algún día `fund_service`
   pasara a `devengo=True`, etiquetar una deuda con `Viaje_RIO` la metería al fondo sin que
   nadie lo decidiera.

**Si se hace, la forma segura** es una **segunda serie** en el tab Fondos ("consumo" junto a
"caja"), que no altere `F(t)` ni se materialice nunca como pago. Decidirlo después del
backfill, mirando cuántas deudas caen en categorías con fondo.

---

## 7. Riesgos

| riesgo | mitigación |
|---|---|
| Doble conteo deuda + liquidación | El interruptor mueve las dos cosas juntas (§2); nunca una sola |
| El baseline se mueve | I2 + snapshot antes y después de la fase 3 |
| `TIPO` distinto de BANCA se trata como tarjeta | I3: las filas `DEUDA` no entran a `load_data()` por defecto |
| Deudas que no son consumo se devengan por error | I4 + la bandeja de la fase 4 |
| Las mediciones envejecen rápido | Pasó: en 7 días el agujero fue de $28,84 a $221,99. Volver a medir en vivo antes de cada fase, nunca contra un respaldo |

---

## 8. Abierto

1. **Fondos.** ¿Un consumo que pagó otro descuenta del fondo? Empatado entre "sí, es consumo"
   y "no, el fondo cubre plata". Decidir en la fase 5, no antes.
2. **El signo de `DEUDA_ACUMULADA`.** Sigue sumando todas las deudas en positivo sin mirar
   `es_mi_deuda` (`dashboard_service.py:148-158`). Con lo de hoy el error máximo es
   ~2 × $237,51. **Decisión previa en pie: no se corrige acá.** Anotado para que no se
   redescubra por tercera vez.
3. **Las 194 "me deben" sin vincular ($4.422,45).** Conciliación incompleta, problema
   distinto. Merece su propio plan.
4. **`es_reembolsable`.** El filtro `all|included|excluded` (`dashboard_filters.py:140`)
   ya permite sacar del gasto lo que me van a devolver. En modo devengo eso y las
   liquidaciones se pisan conceptualmente. Revisar al llegar a la fase 3.
5. **La lista de categorías está en cinco sitios.** `utils/categorias.ts` es el nuevo hogar,
   pero EditModal, MonthlyBudget, DashboardFilterBar y ExplorerExclusionsModal siguen con su
   copia. Migrarlos es un cambio chico y ajeno a este plan.
6. **Etiquetar desde Flutter.** La deuda nace en el celular; ahí sería natural ponerle
   categoría. Requeriría columnas en Supabase y dos fuentes de etiquetas que mergear. No
   ahora.

---

## 9. Bitácora

### 2026-09-20 — Arranque
Medido el agujero contra `backups/deudas_20260913_180016` (§1.3): 5 deudas mías sin
transacción, $28,84; 3 de ellas saldadas solo por cruce, o sea invisibles para siempre.
Confirmado que el patrimonio ya cuenta las deudas y que este plan no lo toca (I1).
Encontradas las cuatro minas de §5.1 que descartan la implementación "obvia".
Pendiente inmediato: capturar el snapshot baseline de la fase 0.

### 2026-09-20 — Fase 0 cerrada
`pre_devengo.json` capturado vía http con `deuda_acumulada presente` en las dos variantes, y
**verificado que la comparación funciona** (comparar contra sí mismo → `IDÉNTICO`). Una red
de seguridad que nunca se probó no es una red de seguridad.

Al medir **en vivo** (no contra el respaldo del 13-sep) el agujero resultó ser **16 deudas y
$221,99**, no 5 y $28,84: aparecieron las 12 deudas con Ale del viaje a Brasil, del 4 al 7
de septiembre. §1.3 reescrita con los números reales. El hallazgo cambia el peso del plan:
el 97,5% del agujero es el viaje, y `ETIQUETADO_VIAJE_BRASIL_2026.md` —117 movimientos
analizados— no ve ni uno de esos $216. **Regla que queda:** medir en vivo, nunca contra un
respaldo.

Siguiente: fase 1, `debt_expenses.py`.

### 2026-09-20 — Fase 1 hecha
`debt_expenses.py` escrito y probado. Dos decisiones que no estaban en el plan y que el
código pidió:

1. **`HORA = ''` se fija en el origen.** Era un "revisar que no reviente"; resultó más
   limpio decidirlo que dejar que `_attach_horas()` improvise sobre una columna ausente.
2. **El atajo sin red.** Si no hay etiquetas de deuda, la función vuelve sin consultar
   Supabase. Hoy ese es el 100% de las llamadas, y sin el atajo cada carga del análisis
   pagaría un viaje a la red para no traer nada. Tiene test propio.

También quedó claro que `deuda_id` en la fila devengada es redundante con `id`, pero se
rellena igual: el frontend filtra por `deuda_id` (`debtFilters.ts`) y no tiene por qué
aprender un caso especial.

Siguiente: fase 2, poder etiquetar una deuda desde la web.

### 2026-09-20 — Fase 2 hecha (salvo el backfill)
Backend, modal y cableado del tab Deudas. Tres cosas que valen la pena anotar:

1. **Apareció una ruta que el plan no tenía: la baja (`DELETE`).** Sin ella, devengar era un
   viaje de ida: cualquier error quedaba clavado en el gasto para siempre. Borra solo la fila
   de `etiquetas.csv`; Supabase no se entera.
2. **`EditModal` se descartó con motivo**, no por gusto: ~1.500 líneas de dividir y vincular
   que a una deuda no le aplican. `DevengoModal` es chico y dice en su cabecera qué no toca.
3. **La lista de categorías ya estaba copiada en cuatro sitios** (EditModal, MonthlyBudget,
   DashboardFilterBar, ExplorerExclusionsModal), idénticas salvo el `'---'`. Escribí
   `utils/categorias.ts` y lo nuevo la usa; **los cuatro viejos quedan como están** —
   migrarlos es otra tarea, no esta. Anotado en §8.

La prueba de ida y vuelta se hizo contra el `etiquetas.csv` real y el archivo quedó
byte-idéntico al terminar (md5 verificado antes y después).

Siguiente: el backfill de las 16, y después la fase 3 (el interruptor).

### 2026-09-20 — Fases 3 y 4 hechas
El interruptor existe y el dashboard no se movió un centavo (`IDÉNTICO` contra
`pre_devengo`, ya con todo el backend nuevo cargado).

**Lo que el plan tenía mal y se corrigió al escribirlo:** decía "las liquidaciones salen",
y eso pierde plata cuando un pago salda deudas devengadas *y* deudas que no. El descuento
es proporcional, calculado contra `detalle_pagos`. Está explicado en la fase 3 y cubierto
por cuatro tests que son el corazón de la fase: el mixto, el reparto entre dos
transacciones, el tope y el caso sin detalle.

Medido de paso: hoy solo **6 transacciones** tienen `pago_id`, y 5 ya están categorizadas
como `Deudas`. O sea que el ajuste casi no tiene sobre qué actuar todavía — razón de más
para que sea correcto antes de que crezca.

La fase 4 salió casi gratis: el endpoint ya tenía `solo_pendientes` de la fase 2.

Queda: el backfill de las 16 (es del usuario) y la fase 5 (fondos), que sigue sin
decidirse a propósito.

### 2026-09-20 — Un defecto de la bandeja, encontrado al explicar el backfill
La bandeja mostraba **18** deudas, no 16. Las dos de más son transferencias que **entraron a
mi cuenta** ("Creo que paga mal los zapatos ya pagados" $49,68 y "Devuelto Exceso pero mal"
$208,67): tienen una transacción mía vinculada por `deuda_id`, así que su plata ya está en
el ledger. Devengarlas habría metido **$258,35 de gasto que nunca existió** — más que todo
lo que el plan pretende rescatar.

Arreglado: la bandeja excluye las que tienen `deuda_id` apuntándolas, el campo
`tiene_transaccion` las deja ver sin el filtro, y el modal avisa antes de duplicar. Dos
tests nuevos. La bandeja ahora dice 16 / $221,99, que es el número de §1.3.

**La lección, para las fases que quedan:** "deuda mía sin etiqueta" no era lo mismo que
"deuda mía sin contar". El vínculo `deuda_id` ya resolvía dos de ellas y nadie lo había
mirado.

También quedó anotado en la fase 5 que el fondo **«Viaje Rio»** existe y mide $1.332,86 del
mismo viaje cuyas deudas suman $216 más. La pregunta de los fondos dejó de ser teórica.

### 2026-09-20 — La red de seguridad avisaba en falso
Cerrando los cabos sueltos, el comparador del dashboard empezó a decir **DIVERGE**. Nada de
lo que toqué está en ese camino (`dashboard_service.py` no aparece en `git status`), así que
lo perseguí:

- Las 40 diferencias eran **siempre los mismos `top_drivers` en distinto orden**, todas de
  deudas, y `chart_data` —el patrimonio— idéntico en todas las corridas.
- Repetido: **IDÉNTICO, DIVERGE, DIVERGE, DIVERGE, IDÉNTICO, DIVERGE** con el mismo código.

**Causa:** `obtener_deudas_para_analisis` ordenaba solo por `FECHA`, y la consulta a Supabase
no lleva `ORDER BY`. Dos deudas del mismo día volvían en el orden físico que le diera la gana
a Postgres, y ese orden se filtraba hasta los `top_drivers`. Igual en `obtener_todos_pagos`.

**Arreglo:** `id` desempata en las dos (`sort_values(['FECHA','ID'])`). Cuatro comparaciones
seguidas después del arreglo: **IDÉNTICO las cuatro**. Baseline recapturado como
`pre_devengo_ordenado`.

Efecto medido de fijar el orden: la suma acumulada se hace en otro orden y `deuda_acumulada`
cambia en el **decimal 13** (`1381,8600000000001` → `...004`). Está catorce órdenes de
magnitud por debajo del centavo de tolerancia; el comparador ni se inmuta.

**Por qué esto importaba más que el bug en sí:** todo el plan se apoya en la invariante I2, y
I2 se verifica con esa herramienta. Una red de seguridad que da IDÉNTICO o DIVERGE según la
corrida no prueba nada — y peor, enseña a ignorarla.

### 2026-09-20 — Commiteado, y un 404 que salió al revisar
Cinco commits en `refactor/filtros-transacciones` (**sin push**): el arreglo del orden
aparte por ser un fix independiente, el backend del devengo, la web, este plan y el
reetiquetado a mano de ASJ Santa Teresa que estaba sin commitear desde antes.

Revisando qué faltaba apareció un hueco que ningún test cubría porque cruzaba dos módulos:
en modo devengo la fila de la deuda viaja **en la misma lista** que las transacciones, así
que en Presupuesto y Explorador se le hace clic para editarla — y `update_transaction`
respondía **404**, porque solo buscaba el id en banca y tarjeta. Arreglado y con dos tests.

La lección se repite: cada vez que una fila `DEUDA` entra en un sitio nuevo, hay que
preguntarse qué pasa cuando alguien la trata como a una transacción normal.

**Pendiente de verdad:** nadie ha visto esto en el navegador todavía.


### 2026-09-20 — Backfill del viaje y las columnas que faltaban
Etiquetadas **13 de las 16**, todas las del viaje a Río, con tag `Viaje_RIO`: **$215,75**.
Quedan tres de $6,24 (`Aguas`, `Shawar.a`, `Almuerzo`).

Al mirar el CSV se vio que las filas `DEUDA` tenían **huecos donde las de banca y tarjeta
llevan su valor "apagado"**: `es_fijo`, `pertenece_a` y `es_reembolsable` en blanco, porque
`DevengoModal` manda solo los siete campos que pregunta y `save_transaction_labels` rellena
el resto con `None`. Funcionaba igual —`is_empty_label` trata `''`, `'---'` y `'False'`
como lo mismo—, pero eran dos escrituras distintas para un mismo significado.

Arreglado en los dos lados: `DEFECTOS_DEVENGO` en la ruta `PUT`, aplicado **solo al alta**
(una edición posterior no pisa lo que haya en el archivo), y las 13 filas ya escritas
normalizadas con un script que toca esas tres columnas y copia el resto línea por línea.
`git diff` sigue mostrando **13 inserciones y ninguna otra línea movida**. Dos tests nuevos:
el alta trae los defectos, la reedición no los reinyecta.

**Verificación — pasó.**
```
pytest tests/test_routes_devengo.py tests/test_debt_expenses.py
       tests/test_devengo_switch.py tests/test_routes_supabase_debts.py  → 61 passed
snapshot_dashboard.py comparar --nombre pre_devengo_ordenado --via http
       → IDÉNTICO (ya con las 13 deudas devengadas en el CSV)
GET /api/transactions/devengo/resumen  → 13 deudas, $215,75
GET .../devengo/pendientes?solo_pendientes=true → 3, $6,24
```
El ledger en modo devengo trae **13 filas `TIPO=DEUDA`** y $215,75 más de gasto que en modo
caja — la diferencia exacta, sin liquidaciones ajustadas (ninguno de esos pagos se hizo aún).

**Dónde se ven, que era la pregunta:** en **Presupuesto** y **Explorador**, con el
interruptor «Lo que consumí». En **Etiquetado** no aparecen —`DailyLabeling` llama a
`useTransactions` sin devengo— y se etiquetan desde el tab **Deudas**, que es donde vive el
modal. En **Fondos** tampoco, por la decisión abierta de la fase 5.

### 2026-09-20 — Saber, mirando el gasto, que sigue siendo una deuda
Pedido: marcar las devengadas «como reembolsable o algo así» para saber que eso ya está
contado en las deudas de Supabase.

**`es_reembolsable` no, y por un motivo concreto:** en este sistema significa lo contrario
—*me van a devolver esta plata*— y tiene consecuencias. `dashboard_filters._pasa_reembolsable`
con `excluded` saca esas filas del gasto, y `fund_service` las excluye siempre
(«Refundable parts belong to the Debts module»). Marcar las 13 habría **anulado el devengo**:
se sacarían del gasto justo las que el plan mete.

**Lo que se hizo:** la fila devengada lleva `SALDO_DEUDA` (§4), leído de
`deudas.saldo_pendiente` en cada lectura. `>0` ⇒ esa plata todavía la debo y ya pesa en
`DEUDA_ACUMULADA`; `0` ⇒ la deuda se saldó, con plata o por cruce. En el Explorador, el
distintivo `DEUDA` ahora tiene color propio y al lado va **«Debo $X»** o **«Saldada»**, con
el detalle en el tooltip.

**Por qué derivado y no una columna en el CSV:** sería una copia que envejece con cada pago
y cada cruce, y envejecería enseguida — **hoy mismo** 12 de las 13 están pendientes y
`Uber aeropuerto` ($5,00) ya está saldada. Una etiqueta fija ya estaría mintiendo sobre una
de trece el día que se escribe. Es la misma regla que `deudor`: lo vivo lo manda Supabase.

**Dos cosas que aparecieron al hacerlo, las dos con test:**

1. **El `concat` se comía la columna.** `aplicar_devengo` concatenaba con `devengadas[df.columns]`,
   o sea seleccionando por las columnas del ledger de caja — que no tiene `SALDO_DEUDA`. Se
   abre también del otro lado, con vacío en banca: ahí no hay deuda detrás, y un 0 se leería
   como "saldada".
2. **`json.dumps` rechaza NaN con un 500.** Con la columna vacía en 227 filas de banca, el
   Explorador **no cargaba ni una vez** en modo devengo. Saneado en `json_utils` a `null`,
   no a 0, por lo mismo del punto anterior.

**Verificación — pasó.**
```
pytest tests/                                                 → 15433 passed, 3 failed (previos y ajenos)
snapshot_dashboard.py comparar --nombre pre_devengo_ordenado  → IDÉNTICO
npx tsc --noEmit / npm test -- --run                          → limpio / 25 passed
GET /api/transactions/?...&devengo=true                       → 200; 13 filas DEUDA con saldo,
                                                                227 de banca con saldo null
```

**Aparte, de levantar la app:** había un backend viejo en `:8000` (sin `--reload`) y un Vite
viejo en `:5173` de una sesión anterior. El script no lo dice y arranca igual: el backend
nuevo muere con `Address already in use` y Vite se corre a `:5174`, así que el navegador
mostraba código viejo y las pruebas por HTTP daban respuestas de un proceso que no tenía los
cambios. Se mataron los dos y se levantó limpio. **Si algo "no se ve", mirar primero qué
proceso está contestando.**

**Decidido:** las tres deudas que faltaban del backfill ($6,24) **no se devengan**. El
backfill queda cerrado en 13 y $215,75.
