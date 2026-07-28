# Plan de pruebas — Sección Deudas

Objetivo: cubrir **todas las combinaciones** de dirección de deuda (`me deben` / `debo`) con
dirección de pago (`me paga` / `pago` / `cruce`), y verificar que las 4 capas den el mismo número.

## 1. Capas bajo prueba

| # | Capa | Artefacto | Cómo se prueba |
|---|------|-----------|----------------|
| L1 | Motor de saldos | `contabilidad/debts/reading.py::_construir_flujo_cuenta` | unit test puro (sin red) |
| L2 | Agregado global | `reading.py::obtener_saldos_deudores` | unit test con listas mezcladas de varios deudores |
| L3 | API | `GET /api/supabase-debts/estado-cuenta`, `/deudores` | TestClient con `reading` mockeado |
| L4 | UI modal | `AccountStatementModal.tsx` (tiles + Flujo/Deudas/Pagos) | checklist manual sobre seed |
| L5 | UI timeline | `Debts.tsx` + `utils/debtTimeline.ts` (local vs Supabase) | checklist manual sobre seed |
| L6 | Espejo móvil | edge `get_estado_cuenta` / `get_historial` | comparar JSON contra L1 para el mismo deudor |

L1 es donde vive toda la matemática → **ahí va el grueso de los casos**. L4/L5 solo verifican
presentación (signos, etiquetas, colores, orden).

## 2. Dimensiones del espacio de casos

Toda situación es una combinación de estos ejes:

| Eje | Valores |
|-----|---------|
| **A. Dirección de la deuda** | `es_mi_deuda=false` → *te deben* (+) · `es_mi_deuda=true` → *tú debes* (−) |
| **B. Dirección del pago** | `es_mi_pago=false` → *me paga* (−) · `es_mi_pago=true` → *yo pago* (+) · `es_compensacion=true` → *cruce* (δ=0) |
| **C. Cobertura** | sin pago · parcial · exacto · con sobrante (saldo a favor) |
| **D. Cardinalidad** | 1 pago→1 deuda · 1 pago→N deudas · N pagos→1 deuda · pago sin asignar |
| **E. Temporalidad** | pago después de la deuda · mismo día · pago **antes** · fecha nula |
| **F. Coherencia** | pago en la misma dirección que la deuda · pago cruzado (dirección opuesta) |
| **G. Mezcla por deudor** | solo *te deben* · solo *tú debes* · ambas a la vez |

El producto cartesiano completo no se prueba: A×B×C ya son 24 y muchos son redundantes. La
matriz de §3 es el **conjunto mínimo que toca cada eje al menos una vez** y cubre todas las
combinaciones A×B, más los bordes de §5.

**Convención de signo (POV dueño):** `+ te deben`, `− tú debes`. Deuda *te deben* suma su monto;
deuda *tú debes* resta; pago recibido resta su `monto_total` **completo**; pago entregado suma;
compensación no mueve el saldo.

## 2.bis Árbol de casos generado (`casos_arbol.py`)

El espacio de casos se **genera** en [`casos_arbol.py`](casos_arbol.py) y queda documentado en
[`CASOS_ARBOL_DEUDAS.md`](CASOS_ARBOL_DEUDAS.md). Cada nivel agrega **un** movimiento al caso
del nivel anterior.

- Nivel 1: `{debe, debo} × {0, 100}` → 4 casos.
- **Deudas**, clasificadas contra la **brecha** (`|neto|`) del nivel anterior: `S` Sobrante
  (> brecha, cambia el signo), `I` Igual (= brecha, neto 0), `N` Insuficiente (< brecha,
  conserva el signo), `M` Mayor (al lado que ya tenía más). Desde neto 0 (hijos de `I`) no hay
  brecha: solo `X` (agregar un `debe`) o `Y` (un `debo`). En nivel 2 no hay `M`.
- **Pagos**, clasificados contra lo que queda pendiente en el lado que abonan. Un pago se
  comporta como una deuda para el saldo pero se muestra distinto, y tiene **tres salidas**:
  `E`/`P` exacto (después no queda nada de ese lado), `F`/`Q` insuficiente (quedan deudas
  abiertas, que se vuelven a mostrar como parciales) y `G`/`R` en exceso (lo que sobró pasa a
  saldo a favor de quien pagó). `E F G` son pagos recibidos; `P Q R`, pagos que doy.
  El **reordenamiento** de pagos no está implementado.
- Cortes: profundidad máxima `NIVEL_MAX` (hoy **4**), y una rama no se expande cuando su
  etiqueta repite la del padre (queda como hoja).

Conteo por profundidad — con pagos la ramificación pasó de ~4 a ~10 hijos por nodo:

| `NIVEL_MAX` | Casos |
|---|---|
| 3 | 126 |
| **4** (actual) | **922** |
| 5 | 6 890 |

**Cierre de cada caso — cruce de cuentas.** Todo caso termina compensando las dos
direcciones: se cruza `min(Σ debe, Σ debo)` emparejando las deudas de la más antigua a la
más reciente (mismo orden FIFO que usa `reading.py` para abonar el saldo a favor). El
resultado incluye qué deuda se cruzó contra cuál y por cuánto, el estado en que queda cada
una (`CRUZADA` / `PARCIAL` / `INTACTA` / `VACÍA`) y el saldo final. Invariantes:

1. `cruzado == min(Σ debe, Σ debo) == Σ montos emparejados`.
2. `saldo_final == neto`, y `Σ restantes con signo == neto` (el cruce no crea ni destruye).
3. Ninguna deuda se cruza por más de su monto; cada lado aporta exactamente `cruzado`.
4. Tras el cruce **solo un lado queda vivo**: si `neto > 0` sobreviven deudas `debe`, si
   `neto < 0` solo `debo`, y si es 0 no queda ninguna.
5. `PARCIAL` ⟺ se cruzó algo y sobró algo — el árbol ejercita parciales en las dos
   direcciones.

Cubierto por `tests/test_debts_arbol_deudas.py` (puro, sin red) y sembrable con
`python scripts/seed_deudas_prueba.py --arbol N` para revisar L4/L5/L6.

Para revisarlo a ojo, `scripts/ver_arbol_deudas.py` pinta el árbol con una barra divergente
del neto y, con `--verificar`, contrasta cada caso contra `reading.py`:

```bash
python scripts/ver_arbol_deudas.py --nivel 3 --verificar   # árbol hasta nivel 3, con ✓/✗
python scripts/ver_arbol_deudas.py --rama AN               # una sola rama
python scripts/ver_arbol_deudas.py --solo-hojas            # solo los casos terminales
python scripts/ver_arbol_deudas.py --cruce                 # columnas de cruce y saldo final
python scripts/ver_arbol_deudas.py --detalle ANS           # el cruce completo de un caso

# Vista de flujo (espejo del modal Estado de cuenta), abierta en el navegador:
python scripts/ver_arbol_deudas.py --vista flujo --nivel 3 --verificar \
       --html /tmp/flujo.html --abrir
```

La **fase 2** es el mismo árbol pero agregando pagos en cada nivel; los escenarios E01–E25 de
§3 son el conjunto mínimo que ya existe de ese espacio y se reemplazarán por el árbol
equivalente cuando la fase 1 esté cerrada.

## 3. Matriz de escenarios canónicos

Cada escenario = un deudor sintético aislado. `neto` es `resumen.neto`; `ledger` es el
`saldo_acumulado` del último movimiento (el más reciente). **Deben ser iguales siempre.**

### Bloque A — Solo "te deben" (A+ × B)

| ID | Situación | Datos | Deuda queda | `neto` = `ledger` | Tile |
|----|-----------|-------|-------------|-------------------|------|
| E01 | Te deben, nadie paga | D+ 100 | PENDIENTE 100 | +100 | Te deben 100 |
| E02 | Te deben, me paga exacto | D+ 100, P← 100 asignado 100 | PAGADA 0 | 0 | Al día |
| E03 | Te deben, me paga parcial | D+ 100, P← 40 → 40 | PARCIAL 60 | +60 | Te deben 60 |
| E04 | Te deben, me paga de más | D+ 100, P← 150 → 100 (sobra 50) | PAGADA 0 | −50 | Tú debes 50 · saldo a favor 50 |
| E05 | Te deben ×2, me paga y el sobrante abona la otra | D+ 100 (ene), D+ 60 (feb), P← 130 → 100 | 1ª PAGADA · 2ª PARCIAL, `abono_saldo_favor` 30, `saldo_real` 30 | +30 | Te deben 30 |
| E06 | Te deben, dos pagos parciales que la cierran | D+ 100, P← 30 → 30, P← 70 → 70 | PAGADA | 0 | Al día |
| E07 | Un pago cubre N deudas | D+ 50, D+ 50, P← 100 → 50+50 | ambas PAGADAS | 0 | Al día |
| E08 | Pago recibido sin asignar (anticipo) | P← 80, sin deudas | — | −80 | Tú debes 80 · saldo a favor 80 |

### Bloque B — Solo "tú debes" (A− × B)

| ID | Situación | Datos | Deuda queda | `neto` = `ledger` | Tile |
|----|-----------|-------|-------------|-------------------|------|
| E09 | Debo, no pago | D− 100 | PENDIENTE 100 | −100 | Tú debes 100 |
| E10 | Debo, pago exacto | D− 100, P→ 100 → 100 | PAGADA | 0 | Al día |
| E11 | Debo, pago parcial | D− 100, P→ 40 → 40 | PARCIAL 60 | −60 | Tú debes 60 |
| E12 | Debo, pago de más | D− 100, P→ 120 → 100 (sobra 20) | PAGADA | +20 | Te deben 20 · **`saldo_favor_owner`=20** |
| E13 | Debo ×2, el sobrante abona la otra | D− 100, D− 60, P→ 130 → 100 | 2ª con `abono_saldo_favor` 30 → `saldo_real` 30 | −30 | Tú debes 30 |
| E14 | Pago entregado sin asignar | P→ 80, sin deudas | — | +80 | Te deben 80 |

### Bloque C — Mezcla y cruce (G = ambas)

| ID | Situación | Datos | Resultado | `neto` = `ledger` |
|----|-----------|-------|-----------|-------------------|
| E15 | Ambas direcciones, sin pagos | D+ 100, D− 60 | ambas PENDIENTES; `total_pendiente`=160 | +40 |
| E16 | Cruce parcial | E15 + PC 60 (es_mi_pago=true → abona **D−**) + PC 60 (es_mi_pago=false → abona **D+**) | D− PAGADA, D+ saldo 40 | +40 |
| E17 | Cruce total | D+ 100, D− 100 + par de PC 100 | ambas PAGADAS | 0 |
| E18 | Cruce + pago físico del remanente | E16 + P← 40 → 40 | todo PAGADO | 0 |
| E19 | Cruce con sobrante | cruce por más del solapamiento | sobrante entra como saldo a favor del lado que pagó | verificar invariante |

En E16–E19 los dos pagos de compensación tienen **δ=0**: el saldo del ledger no debe saltar al
pasar por ellos, solo deben aparecer como "Cruce de cuentas" en azul.

### Bloque D — Temporalidad (E)

| ID | Situación | Esperado |
|----|-----------|----------|
| E20 | Pago con fecha **anterior** a la deuda | Ledger cronológico: primero −P (saldo negativo transitorio), luego +D. Final igual que E02. En pantalla (presente→pasado) el pago queda **debajo** de la deuda |
| E21 | Deuda y pago el **mismo día** | En el cálculo la deuda va primero; en pantalla el pago aparece **arriba** |
| E22 | Deuda o pago con `fecha` nula | No revienta; ordena al inicio; UI muestra "—" |

### Bloque E — Coherencia de dirección (F) ⚠️

Casos donde el pago va en dirección **opuesta** a la deuda que abona. La invariante
`neto == ledger` **no se sostiene** con la semántica actual; hay que decidir si el sistema
los previene (validación) o los soporta.

| ID | Situación | Qué pasa hoy |
|----|-----------|--------------|
| E23 | D+ 100 y un pago **entregado** de 50 asignado a esa deuda | `saldo_real`=50 → `neto`=+50, pero ledger = 100+50 = **150**. Divergencia |
| E24 | D− 100 y un pago **recibido** de 50 asignado a esa deuda | `neto`=−50, ledger = −150. Divergencia |
| E25 | Un mismo pago asignado a deudas de **ambas** direcciones | Divergencia proporcional a la parte cruzada |

**Resultado esperado del test:** o bien el motor los normaliza, o bien la app garantiza que no
existen y el test se convierte en un *guard* sobre los datos reales (§6).

## 4. Invariantes (se verifican en **todos** los escenarios)

1. `resumen.neto == movimientos[0].saldo_acumulado` (el más reciente, orden presente→pasado).
2. `resumen.neto == total_te_deben − total_tu_debes − saldo_favor + saldo_favor_owner`.
3. Por deuda: `saldo_real == max(monto_original − monto_pagado, 0) − abono_saldo_favor` y `saldo_real ≥ −0.01`.
4. `estado == PAGADA ⟺ saldo_real ≤ 0.01`; `PARCIAL ⟺ monto_pagado > 0.01 ∨ abono_saldo_favor > 0.01`.
5. Suma de `abono_saldo_favor` por lado ≤ sobrante disponible de ese lado; el remanente sale en `saldo_favor` / `saldo_favor_owner`.
6. `total_pendiente == Σ saldo_real` (ambas direcciones).
7. Un pago con `es_compensacion` tiene δ=0 → el `saldo_acumulado` no cambia al atravesarlo.
8. **Paridad L1↔L6:** para el mismo `deudor_id`, `reading.obtener_estado_cuenta` y la edge
   `get_estado_cuenta` (pov=owner) devuelven el mismo `neto`, `total_pendiente`, `saldo_favor`
   y el mismo `abono_saldo_favor` por deuda.
9. **Paridad L1↔L2:** `obtener_saldos_deudores()[id]` coincide con el `resumen` de
   `obtener_estado_cuenta(id)` para los tres campos que expone.

## 5. Casos borde

| ID | Caso | Esperado |
|----|------|----------|
| B01 | Deuda con `monto` = 0 | PAGADA, no divide por cero en la barra de progreso |
| B02 | `monto` negativo | Documentar: hoy invierte el signo del delta |
| B03 | Redondeo: 3 deudas de 33.33 y pago de 100 | Sobrante 0.01 → **no** cuenta como saldo a favor (umbral `> 0.01`) |
| B04 | `detalle_pagos` que suma **más** que el `monto` de la deuda | `saldo_pendiente` se corta en 0; verificar que no genere neto fantasma |
| B05 | Deudor con pagos pero **sin** deudas | `obtener_estado_cuenta` no consulta `detalle_pagos` → todo el pago es sobrante (E08/E14) |
| B06 | Deudor con nombre vacío | No aparece en `listar_deudores`, pero sí puede tener saldo → no debe romper `/deudores` |
| B07 | `deudor_id` inexistente | Estado de cuenta vacío, resumen en ceros, sin excepción |
| B08 | Supabase caído / módulo ausente | Endpoint responde 500 controlado, la UI muestra "No se pudo cargar" |
| B09 | Dos pagos de compensación separados >2s | La edge no los agrupa en bundle; verificar que igual se muestren como cruce |
| B10 | Deuda pagada por cruce **y** por dinero | Aparece un solo `saldo_real`, sin doble descuento |

## 6. Verificación contra datos reales

Script que recorra **los 13 deudores reales** y afirme las invariantes 1, 2, 6 y 8, además de
detectar E23–E25 (pagos con dirección incoherente respecto a la deuda que abonan). Es la red de
seguridad: si algún deudor real viola una invariante, el caso sintético que falta se agrega a §3.

## 7. Checklist de UI

### L4 — `AccountStatementModal`

- [ ] Tile principal: `Te deben` verde / `Tú debes` rosa / `Al día` gris según signo de `neto`.
- [ ] Tile **Saldo a favor** muestra `resumen.saldo_favor` (crédito del deudor). En **E12** el crédito es tuyo (`saldo_favor_owner`) → hoy el tile muestra $0.00. Definir si se pinta o se agrega un segundo tile.
- [ ] Tile **Pendiente** suma las dos direcciones (E15 → $160 con neto +40). Confirmar que se lee así o etiquetar mejor.
- [ ] Pestaña **Flujo**: orden presente→pasado, punto azul + "Cruce de cuentas" en compensaciones, sobrante en ámbar, bloque "parcial" con barra de progreso tras un pago que no cierra la deuda (E03, E06).
- [ ] Pestaña **Deudas**: monto tachado + `−$X (saldo a favor)` cuando `abono_saldo_favor > 0.01` (E05, E13); badge `Tú debes` / `Te debe` correcto.
- [ ] Pestaña **Pagos**: hoy toda fila dice **"Pago recibido"** con `+$` fijo → en E10/E12/E14 (pagos entregados) y en los cruces el texto y el signo son incorrectos. Debe distinguir `es_mi_pago` y `es_compensacion`.
- [ ] Estados vacíos (B05, B07) y de carga.

### L5 — Timeline `Debts.tsx` / `debtTimeline.ts`

- [ ] Match heurístico: gasto local negativo vs deuda Supabase positiva, mismo día, tolerancia `max($0.80, 1%)` → "POSIBLE MATCH" ámbar.
- [ ] Sin coincidencia a ningún lado → placeholder "sin registro" en la banda correcta.
- [ ] Vinculación manual: al vincular queda "VINCULADO" verde, se persiste `deuda_id` en la etiqueta y el par sale del match heurístico; desvincular revierte.
- [ ] Transacción dividida: N filas con badge "división", sin colisión de key React.
- [ ] Grupo: una tarjeta con monto sumado y badge "N agrup." que matchea 1:1 contra Supabase.
- [ ] Toggle mes/semana y "Solo coincidencias"; barra de reconciliación (total local, total Supabase, diff y conteos) cuadra con lo visible.
- [ ] Ambos lados del mismo período siempre en la misma banda (sin desalineación al hacer scroll).

## 8. Estado: escenarios ya sembrados en Supabase

`scripts/seed_deudas_prueba.py` crea **29 personas** `TEST <ID> · <situación>` (una por escenario
de §3 y §5), con `--verify` para contrastar `neto` y `ledger` contra lo esperado y `--clean` para
borrarlas. Corrida del 2026-07-27: **23 correctos · 6 divergencias conocidas · 0 inesperados**.

Las 6 divergencias `neto ≠ ledger` confirmadas en datos reales son E19, E23, E24, E25, B02 y B04.
E22 (fecha nula) no es sembrable: `fecha_gasto`/`fecha_pago` son `NOT NULL` → queda solo como
unit test sobre `_construir_flujo_cuenta`.

## 9. Implementación sugerida

1. **`tests/test_debts_flujo_cuenta.py`** — parametrizado sobre §3 y §5 con *fixtures* de listas
   crudas (`deudas_raw`, `pagos_raw`, `detalles`) e invariantes de §4 como helper compartido.
   Sin red, corre con el resto de la suite pytest.
2. **`tests/test_routes_supabase_debts.py`** — ampliar con `estado-cuenta` mockeado: 200 con
   forma correcta, 500 controlado, `deudor_id` inexistente.
3. **`scripts/seed_deudas_prueba.py`** — recrea en Supabase las personas `Prueba E01…E19` con
   sus deudas/pagos/detalles, y `--clean` para borrarlas. Sirve para L4/L5/L6 (la app Flutter y
   el visor también quedan cubiertos visualmente).
4. **`scripts/verificar_invariantes_deudas.py`** — §6 sobre los deudores reales + paridad con la
   edge function.

Orden de trabajo: 1 → 4 → 2 → 3 (los unit tests primero porque ahí van a caer E23–E25 y E12).
