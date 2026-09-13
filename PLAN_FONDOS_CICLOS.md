# Plan: ciclos en los fondos

Dar al fondo una noción de **período**, para que la cobertura automática deje de gotear
hacia adelante y para poder decidir a mano qué ingreso paga qué mes.

---

## 1. El problema

`computeFlatten` (`contabilidad/pagina/src/pages/Funds.tsx:61`) empareja ingresos con gastos
de forma **secuencial, no calendario**. Cada ingreso abre una ventana de cobertura que solo
se cierra por dos motivos:

1. llega otro ingreso "grande" — ≥ 40% del que la abrió (`LARGE_INCOME_FRAC`, línea 42), o
2. se acaba la lista de movimientos — `const windowEnd = i;` (línea 96), *"or movs.length"*.

No hay un tercer motivo: **la ventana no tiene tope temporal**. Cuando un mes no trae
mensual, el crédito sobrante del mes anterior sigue cubriendo gastos hacia adelante, y al
materializar salen pagos que arrancan en un ingreso de hace dos meses.

### Evidencia en los datos reales

Agrupando `pagos.csv` del grupo generado del fondo **Comida** por fecha de ingreso:

| ingreso | pagos | total cubierto | último gasto cubierto |
|---|---:|---:|---|
| 2025-11-24 | 13 | $65.54 | 2025-12-22 |
| 2025-12-22 | 15 | $65.02 | 2026-01-21 |
| **2026-01-22** | **19** | **$80.83** | **2026-02-26** ← se pasa de la frontera |
| 2026-03-03 | 7 | $24.75 | 2026-03-19 |
| 2026-03-20 | 19 | $70.10 | 2026-04-21 |
| 2026-04-22 | 12 | $43.25 | 2026-05-22 |
| 2026-05-22 | 17 | $69.52 | 2026-06-22 |
| 2026-06-22 | 14 | $73.23 | 2026-07-09 |

El mensual llega alrededor del **22**. Febrero de 2026 no tuvo ingreso, y se ve el efecto:
el ingreso del 2026-01-22 acaba pagando gastos del 23, 24 y 26 de febrero, ya dentro del
mes siguiente. Y marzo trae **dos** ingresos —el 03-03, que es el de febrero llegando
tarde, y el 03-20, que es el suyo— amontonados en la misma ventana.

Los dos síntomas que motivan este plan están ahí, medidos, no supuestos.

---

## 2. El modelo

Cuatro archivos. Uno nuevo, tres que ganan columnas al final.

```
ciclos.csv     id, group_id, inicio, fin, nota                    ← nuevo
grupos.csv     ...existente + ciclo, dia_corte_default
etiquetas.csv  ...existente + ciclo_id
pagos.csv      ...existente + ciclo_id
```

### `ciclos.csv`

Vive junto a `grupos.csv` y `pagos.csv`, en `data/sistema/interpolaciones/`.

| columna | qué es |
|---|---|
| `id` | uuid |
| `group_id` | el fondo |
| `inicio` | **inclusivo** |
| `fin` | **exclusivo** |
| `nota` | por qué este ciclo fue raro. Texto libre |

Invariante: `fin(n) == inicio(n+1)`. Los ciclos de un fondo son contiguos y sin huecos, así
un movimiento en el día de la frontera cae en exactamente uno, sin desempates.

**La fila guarda decisiones, no resultados.** Nada de `credito`, `cubierto` o `sobrante` en
el CSV: eso se calcula de los movimientos cada vez. Guardarlo sería una caché que se queda
vieja — el mismo error del que huimos.

### `grupos.csv`

| columna | valores | vacío |
|---|---|---|
| `ciclo` | `ingreso` · `mensual` · `ninguno` | `ingreso` = comportamiento actual |
| `dia_corte_default` | 1–31 (se recorta al último día del mes) | 1 |

Son **defaults de generación**, no política de lectura. La regla que sostiene el modelo:

> El grupo dice **cómo nacen** los ciclos nuevos. El ciclo dice **cómo se lee él mismo**.
> Una vez que la fila existe, nada del grupo puede cambiar su interpretación.

Por eso `dia_corte_default` se puede cambiar cuando quieras sin reescribir el pasado, y por
eso no hace falta un archivo de reglas con vigencia: las fronteras ya están guardadas en
cada fila.

### `etiquetas.csv` y `pagos.csv`

`ciclo_id` en ambos. En etiquetas es el override — "este movimiento pertenece a ese ciclo
aunque su fecha diga otra cosa"—; en pagos es a qué ciclo pertenece el emparejamiento.

Se llama `ciclo_id` y no `periodo` por dos razones: encaja con el patrón que ya existe en
`LABEL_COLUMNS` (`group_id`, `fondo_id`, `deuda_id`) y, sobre todo, si más adelante mueves
una frontera, una referencia por fecha se queda huérfana y una por id no.

---

## 3. Las reglas

**Generación de fronteras.** El primer `inicio` es la última ocurrencia de
`dia_corte_default` en o antes del primer movimiento del fondo. Cada `inicio` siguiente es
la siguiente ocurrencia del día de corte. Se generan ciclos hasta pasar la más tardía de
(hoy, último movimiento), así ningún movimiento queda fuera. Un día de corte mayor que los
días del mes se recorta al último día.

**Pertenencia de un movimiento.** En este orden:

1. ¿tiene `ciclo_id` en su etiqueta? → ese ciclo, y se acabó.
2. ¿no? → el ciclo donde `inicio <= fecha < fin`.

**Cobertura.** Confinada al ciclo. El crédito de sus ingresos cubre sus gastos con el mismo
drawdown FIFO que ya hay, y el pase 2 —gasto anterior a su ingreso— sigue funcionando
dentro del ciclo. Los pagos salen con las **fechas reales** de los movimientos: el
`ciclo_id` cambia el emparejamiento, nunca falsea una fecha.

**Sin arrastre entre ciclos.** Un sobrante es ahorro de ese mes; un déficit es que ese mes
gastaste de más. Las dos cosas son verdad y se ven en la línea aplanada. Un ciclo queda
fijo el día que termina y nada posterior lo toca.

**Sin huecos.** Si el ciclo acaba el 21 y el mensual llega el 25, el ciclo nuevo empieza el
22 y su ingreso entra tarde, dentro de él. Los días 22–24 existen y tienen gastos. Con
hueco quedarían huérfanos, invisibles para toda la maquinaria, y cada consulta necesitaría
una rama "¿y si no cae en ningún ciclo?". Si alguna vez hace falta un hueco de verdad, ya
es expresable: un ciclo al que no le asignas nada se comporta como tal.

---

## 4. Fases

### Fase 1 — El corte por ciclo *(la que arregla el problema)* — **hecha**

- [x] `CICLO_COLUMNS` + `CicloStorage` en `contabilidad/backend/storage/ciclos_storage.py`,
      reutilizando `read_csv` / `save_csv` / `_id_unico` / `_indices_de` de
      `variables_storage.py`.
- [x] `ciclo` y `dia_corte_default` en `GROUP_COLUMNS`, `_normalize_group`, `create_group`.
- [x] Generador `generar_ciclos()`: crea las filas que falten, contiguas, por los dos
      extremos, y nunca toca las que ya existen.
- [x] `mover_frontera()`: la frontera es la unidad editable, cambia dos filas a la vez.
- [x] `fund_service`: reparte los movimientos por ciclo y devuelve el resumen de cada uno
      con `credito`, `gasto`, `cubierto`, `sin_cubrir`, `sobrante` y `en_curso`.
- [x] Endpoints en `routes/funds.py`: listar ciclos, editar la nota, mover una frontera.
- [x] `computeFlatten` confinado al ciclo, y `generate-payments` guardando `ciclo_id`.
- [x] Panel de ciclos en la pestaña Seguimiento + selector de ciclo y día de corte en los
      modales de crear y editar fondo.

Dos decisiones que se tomaron al implementar:

- **Los ciclos se generan de forma perezosa al leer el fondo**, no con un botón. Un GET que
  escribe no es bonito, pero la generación es idempotente y la alternativa era que el
  usuario tuviera que acordarse de pulsar algo para que su mes existiera.
- **El resumen de los ciclos ignora la lente "Ver desde"**. Si dependiera de ella, un ciclo
  cuyo ingreso quedara fuera de la ventana aparecería como "sin ingreso" sin serlo. La
  lente es para el gráfico y el extracto, no para la contabilidad de los períodos.
- **`asegurar_cabecera()`**, en `variables_storage`: `create_payment` anexa con
  `header=False`, o sea por posición, así que contra un `pagos.csv` con el esquema viejo
  habría metido un campo de más, el archivo habría quedado dentado y `read_csv` habría
  devuelto un DataFrame vacío tragándose la excepción — todos los pagos desaparecidos de la
  app sin un solo error a la vista. Se migra el esquema antes de anexar.

### Fase 2 — El control manual

- [ ] `ciclo_id` en `LABEL_COLUMNS` + `set_ciclo_for_part`, gemelo de `set_fondo_for_part`.
- [ ] Badge de ciclo editable en cada fila del extracto.

### Fase 3 — Cierre *(opcional, decidir al llegar)*

Un `estado` en `ciclos.csv`. Regenerar salta los cerrados y los descuadres se muestran en
vez de reconciliarse en silencio. Solo gana algo cuando un import trae una transacción con
fecha vieja y no quieres que se aplique sola a un mes que ya diste por bueno.

### Fase 4 — Que el ciclo viaje a `informacion`

- [ ] `ciclo_id` en el exportador, en `CAMPOS_ETIQUETAS` (`ingest.py:42`) y en la vista
      `etiquetas_por_transaccion` (`ingest.py:262`, con `MAX(ciclo_id)`).
- [ ] **Ojo**: `init_etiquetas` usa `CREATE TABLE IF NOT EXISTS`. Sobre una DB que ya
      existe, añadir el campo a `campos_sql` no hace nada y el insert falla con *"no such
      column"*. Hace falta un `ALTER TABLE` o reconstruir con `--reset`.

---

## 5. Lo que cuesta

Derivar no puede desincronizarse; materializar sí. Aquí se materializa a propósito, porque
"qué ingreso paga qué mes" es una decisión humana y las decisiones humanas hay que
guardarlas. A cambio hay tres piezas nuevas que mantener —generador, editor de fronteras y,
si llega, el cierre— y cada feature futura tendrá que preguntarse qué hace con un ciclo ya
escrito.

## 6. Retrocompatibilidad

Ninguna migración. Las columnas se añaden al final y `read_csv` sobre un archivo viejo
simplemente no las trae; `_normalize_group` les pone el default. `ciclos.csv` ausente = un
fondo sin ciclos. Un fondo con `ciclo` vacío se comporta **exactamente** como hoy, así que
esto se activa fondo por fondo cuando tú quieras.
