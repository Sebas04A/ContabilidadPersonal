# 💚 Métricas de la pestaña Felicidad

Documentación de las fórmulas de `HappinessTab.tsx`: qué mide cada gráfico, por qué
esa fórmula y no otra, y qué alternativas se descartaron (con el motivo).

## 📋 Tabla de Contenidos

1. [La escala de felicidad](#la-escala-de-felicidad)
2. [Los tres gráficos y qué pregunta responde cada uno](#los-tres-gráficos-y-qué-pregunta-responde-cada-uno)
3. [Fórmulas](#fórmulas)
4. [Shrinkage (Empirical Bayes)](#shrinkage-empirical-bayes)
5. [Decisiones de diseño y alternativas descartadas](#decisiones-de-diseño-y-alternativas-descartadas)
6. [Controles de la UI](#controles-de-la-ui)
7. [Bugs corregidos](#bugs-corregidos)

---

## La escala de felicidad

La columna `felicidad` de `etiquetas.csv` va de **1 a 9**, y es **bipolar** con el
neutro en el 5:

| Nivel | Significado |
|-------|-------------|
| 8-9   | Agrega gran valor |
| 6-7   | Agrega valor real |
| **5** | **Neutro / funcional** |
| 3-4   | Insatisfacción |
| 1-2   | Arrepentimiento |

**Esto gobierna todas las fórmulas.** El cero real de la escala está en 5, no en 0.
Por eso casi todos los cálculos usan `v = felicidad − 5` (constante `NEUTRAL`):

- Sin centrar, un gasto indiferente aporta +5 puntos y una categoría de puros gastos
  neutros parece productiva solo por ser barata.
- Sin centrar no existe el signo negativo, y sin signo **no se puede responder "qué
  categorías evitar"**, que es la mitad del objetivo de la pestaña.

La escala además es **independiente del precio** por definición ("Felicidad Absoluta:
medida sin tomar en cuenta el precio"). Un café de $2 y una cena de $200 calificados
7 entregaron la misma experiencia; el precio se cruza después, no dentro de la nota.

---

## Los tres gráficos y qué pregunta responde cada uno

Cada vista responde una decisión distinta. No son tres formas de ver lo mismo.

### 1. Scatter individual — diagnóstico anecdótico

**Pregunta:** *"¿Este gasto puntual valió la pena?"*

Eje X = felicidad (1-9, con jitter), eje Y = monto. Sirve para encontrar gastos
baratos que encantaron y gastos caros que decepcionaron, y para calibrar el propio
criterio de calificación.

### 2. Barras — rendimiento del dinero

**Pregunta:** *"¿Cuánto rinde mi plata en cada categoría/tag?"*

Ranking por felicidad neta del dólar promedio. Es la vista de "a simple vista, dónde
rinde y dónde se quema".

### 3. Burbujas — mapa de decisión

**Pregunta:** *"¿Qué agrando y qué achico?"*

- Eje X = felicidad ponderada (1-9)
- Eje Y = **ticket promedio** (gasto por transacción)
- Tamaño = nº de transacciones
- Color = felicidad por dólar (la diagonal del gráfico)

**Por qué ticket promedio y no gasto total en el eje Y:** la acción del usuario es
*"repetir más veces al mismo precio"*, no *"gastar más por vez"*. Bajo esa acción el
ticket es **invariante**: al crecer un grupo el punto no se mueve, solo crece la
burbuja. Con gasto total en Y, actuar sobre un grupo mueve su posición y el mapa deja
de ser un mapa — la posición se contamina con la variable de decisión.

Lectura por cuadrantes: abajo-derecha (barato y bueno) conviene agrandar,
arriba-izquierda (caro y mediocre) conviene achicar.

---

## Fórmulas

### Por transacción

```
m_i = |MONTO_i|          monto (positivo)
v_i = felicidad_i − 5    puntos netos sobre el neutro, rango −4 … +4
```

### Acumuladores por grupo (`buildGroupStats`)

```
totalAmount  = Σ m_i
netWeighted  = Σ (v_i · m_i)                puntos-dólar
count        = nº de transacciones
ticket       = totalAmount / count
effectiveN   = (Σm)² / Σm²                  n efectivo de Kish
```

### Métrica principal: felicidad neta del dólar promedio

```
netWeighted / totalAmount  ≡  avgWeighted − 5
```

Es una **identidad exacta**:

```
Σ(v·m)/Σm = Σ((fel−5)·m)/Σm = Σ(fel·m)/Σm − 5 = ponderada − 5
```

**Unidades: puntos, no puntos/dólar.** Es un promedio de puntos donde el peso de cada
transacción es su monto — la unidad de observación es el dólar. Rango −4 a +4.

**Por qué `v·m` y no solo `v`:** ver [alternativas descartadas](#a-tasa-cruda-σfel5σmonto).

### Métricas secundarias

```
avgSimple    = Σfel / n                     experiencia típica (cada tx vota igual)
avgWeighted  = Σ(fel·m) / Σm                cómo rindió la plata (cada dólar vota igual)
gap          = avgWeighted − avgSimple
$/punto      = ticket / shrunk              cuánto cuesta un punto al ritmo del grupo
```

**El `gap` es un diagnóstico, no un ranking.** Cuando es grande, la plata y el
disfrute no están alineados *dentro* del grupo: los gastos caros y los baratos se
califican distinto. La acción correcta ahí no es agrandar ni achicar, es **partir la
categoría en tags**. Por eso `avgSimple` se calcula pero no se grafica: su valor está
en el gap.

### Métrica alternativa (toggle "$/pt bruto")

```
avgCostPerHappiness = Σ(m_i / fel_i) / n           se muestra sin ajuste
exp(Σ ln(m_i/fel_i) / n)                           media geométrica, base del ajuste
```

Dólares por punto de felicidad **bruta** (sin restar el neutro). Más bajo = mejor.
Con el ajuste activo se usa la media geométrica, por la razón explicada en
[shrinkage](#shrinkage-empirical-bayes).
Se mantiene como opción porque es intuitiva, pero tiene dos límites documentados en
[alternativas descartadas](#c-mfel-sin-restar-el-neutro). Las barras de grupos que
son neto negativo se pintan **rojas igual** con un ⚠ en el tooltip, para que el punto
ciego de la métrica quede visible en vez de escondido.

---

## Shrinkage (Empirical Bayes)

### El problema

Sin ajuste, un tag con 2 transacciones afortunadas encabeza el ranking. Eso no es
información, es ruido — y como la vista está pensada para leerse "a simple vista", el
tope tiene que ser confiable. Es el mismo problema que resuelve IMDB para que una
película con 3 votos de 10/10 no supere a El Padrino.

### La fórmula (`shrinkEmpiricalBayes`)

James-Stein / Empirical Bayes para medias con tamaños muestrales distintos:

```
s²_pooled = Σ(withinVar_i · weight_i) / Σ weight_i     varianza intra-grupo agrupada
σ²_i      = s²_pooled / effectiveN_i                   ruido de la media del grupo i

w_i  = 1 / σ²_i                                        precisión del grupo i
ȳ_w  = Σ(w_i · estimate_i) / Σw_i
Q    = Σ w_i (estimate_i − ȳ_w)²
C    = Σw_i − Σw_i² / Σw_i
τ²   = (Q − (k−1)) / C                                 DerSimonian-Laird

B_i  = σ²_i / (τ² + σ²_i)               clip a [0,1]
θ_i  = (1 − B_i)·estimate_i + B_i·μ
```

**`τ²` por DerSimonian-Laird**, el estándar de meta-análisis de efectos aleatorios, y
no por el método de momentos ingenuo (`Var(estimate_i) − mean(σ²_i)`). El ingenuo usa
la varianza **sin ponderar** de las medias, así que trata igual a un grupo de 1
transacción que a uno de 30: los grupos chicos le inflan las dos partes de la resta y
el resultado queda inestable. DL pondera cada grupo por su precisión antes de medir
la dispersión.

`B_i` es la fracción que se toma de la media global. Se lee directo:

- **τ² grande** (los grupos difieren de verdad) → `B_i` chico → casi no se encoge.
- **τ² → 0** (los grupos son indistinguibles del ruido) → todo colapsa a `μ`.

El método **se recalibra solo**: no hay parámetro que tocar cuando entren más datos.

### Detalles de implementación

**`s²` agrupado y no por grupo.** Un grupo de una sola transacción tiene varianza
observada 0; usarla daría `B_i = 0`, o sea "confío ciegamente en un único dato". El
estimador asume varianzas intra-grupo parecidas, que es su condición habitual.

**`effectiveN` de Kish** en vez de `count`, porque la estimación es una media
*ponderada por monto*. Un grupo de 20 transacciones donde una vale $200 y el resto $2
tiene `n_eff ≈ 2`, no 20 — una sola observación domina la media.

**`μ` sale de las transacciones, no de promediar los grupos.** Los tags se solapan;
sumarlos contaría la misma plata varias veces.

**El coste se encoge en log, no en dólares.** `monto/felicidad` es una razón de cola
pesada: su varianza crece con el *cuadrado* del monto, así que `τ²` y `σ²_i` crecen
los dos y su cociente queda a merced de qué gasto grande cayó en qué grupo. Medido
sobre escenarios con gastos de $800 a $3000 inyectados:

| escenario | `B_i` en dólares | `B_i` en log |
|-----------|------------------|--------------|
| datos base | 0-1% | 1-22% |
| + gasto $800 | 0-0% | 1-13% |
| + gasto $2000 | 0-0% | 0-10% |
| + 3 gastos grandes | 1-23% | 1-17% |

En dólares el ajuste es errático; en log se mantiene en un rango sensato. El síntoma
observado fue **todas las barras idénticas** (el estimador aterrizó en `B_i ≈ 1` y
colapsó todo a la media). `exp(media de logs)` es la media geométrica, que además es
la medida de centro natural para una razón.

**Guarda contra `τ² ≤ 0`.** El método de momentos puede tocar su piso cuando el ruido
estimado se come la varianza entre grupos. Encoger con `τ² = 0` da `B_i = 1` para
todos y deja el gráfico con todas las barras en la media, que no informa nada. Es un
artefacto conocido del estimador, no una conclusión: en ese caso se devuelven los
valores crudos y el tooltip lo avisa.

### Toggle "Con ajuste / Sin ajuste"

`Sin ajuste` grafica las estimaciones crudas. Sirve para ver cuánto del ranking es
evidencia y cuánto es corrección — si una barra se mueve mucho al apagar el ajuste,
ese grupo tiene poca evidencia detrás.

### Por qué el efecto casi no se ve

**Con datos reales el ajuste suele ser diminuto, y eso es el resultado correcto.**
Cuando `τ² >> σ²_i` — o sea cuando los grupos difieren mucho más de lo que fluctúan
por dentro — la conclusión estadística es "creeles casi todo":

| grupo | n | `B_i` | crudo | ajustado |
|-------|---|-------|-------|----------|
| Ocio | 28 | 1% | 0.85 | 0.85 |
| Alimentación | 28 | 1% | 0.75 | 0.75 |
| Regalo | 6 | 3% | 0.52 | 0.53 |
| Aseo | 1 | 17% | 2.29 | 2.07 |

Una barra que se corre 1% es indistinguible a ojo, así que el toggle parece no hacer
nada. Por eso la vista trae dos indicadores:

- Una **marca vertical blanca** en cada barra señalando dónde estaba el valor crudo.
- Un **pie de gráfico** con `τ²` y el rango de `B_i` aplicado, más un aviso explícito
  cuando `maxB < 8%` ("los grupos difieren mucho más que su ruido: casi no hace falta
  ajustar").

Sin eso no hay forma de distinguir "el ajuste está apagado", "el ajuste degeneró" y
"el ajuste corrigió un 1%".

---

## Decisiones de diseño y alternativas descartadas

Cada una se probó contra datos reales antes de descartarse.

### A) Tasa cruda `Σ(fel−5)/Σmonto`

**Descartada.** Cada transacción aporta lo mismo al numerador sin importar su tamaño,
mientras el denominador va en dinero. Resultado: los montos chicos tienen
apalancamiento desmedido.

> Caso real (tag Renata): una transacción de **$1.75** sobre $25 de gasto daba vuelta
> el signo del tag entero. Quitándola, la tasa pasaba de **−9.30 a +7.14**. La misma
> transacción mueve la métrica ponderada solo 0.35.

Ponderar el numerador arregla eso, **al precio de dejar de ser una tasa "por dólar"
en unidades**. Es inevitable: ser una tasa es dividir por el dinero, ser robusto es
multiplicarlo — se cancelan. Se conserva en el tooltip como dato secundario.

### B) Promedio de razones `Σ(monto/felicidad)/n` como métrica principal

**Disponible como toggle, no como default.** Es monótona y no tiene división por cero
(fel nunca es 0), pero:

- **Ordena casi por precio.** Correlación de rango con el ticket promedio: **+0.967**.
  Los montos varían 237× y `fel` solo puede variar 9×, así que la felicidad queda
  ahogada.
- **No puede expresar daño** (ver punto C).
- Una sola transacción cara mueve el resultado ~15%.

### C) `m/fel` sin restar el neutro

**Descartado como default.** Sin el `−5` el resultado nunca es negativo:

| caso | monto | fel | `m/fel` | `m/(fel−5)` |
|------|-------|-----|---------|-------------|
| regalo perfecto | 100 | 9 | 11.11 | **+25.00** |
| compra neutra | 100 | 5 | 20.00 | indef. |
| arrepentimiento total | 100 | 1 | 100.00 | **−25.00** |

El arrepentimiento total da **+100**, un número positivo: la métrica lo lee como
"compraste felicidad, salió cara". Un gasto que restó se disfraza de gasto caro.

De fondo: dividir por `fel` asume que la escala tiene un **cero verdadero** — que
felicidad 8 entrega el doble que felicidad 4. Pero 4 es *insatisfacción*, no "la mitad
de bueno".

### D) `Σ(m_i/(fel_i−5))/n`

**Descartada.** Polo en `fel = 5`: **el 25% de los gastos calificados tiene felicidad
5**, o sea división por cero en una de cada cuatro transacciones. Además no es
ordenable — la función salta de −∞ a +∞ al cruzar el neutro, así que "más alto es
mejor" y "más bajo es mejor" fallan las dos.

### E) Reparto del monto entre tags (`1/nTags`)

**Descartado.** La idea era conservar la plata al sumar tags, pero **penalizaba a los
gastos mejor etiquetados**.

> Caso real (tag Renata): los Motel (felicidad 7-9) llevan 3 tags cada uno y quedaban
> al 33% de su peso; el esquite (felicidad 1) llevaba un solo tag y pesaba completo.
> El tag caía de **+1.81 a +0.73** por cómo estaban *descritos* sus gastos, no por
> cómo fueron. Y solo distorsionaba 3 de 21 tags — los que tienen nº de tags
> heterogéneo; en el resto el peso se cancelaba y no hacía nada.

Como estas vistas son **rankings y nunca se suman tags entre sí**, la conservación no
compraba nada.

> ⚠️ **Consecuencia:** los totales por tag **no son aditivos**. Una transacción con 3
> tags cuenta completa en los 3. Sumar todos los tags da más que el gasto real.

### F) Métrica única con ponderación asimétrica

**Descartada.** Se exploró una fórmula que premiara lo barato-bueno y no castigara lo
barato-malo, con un parámetro λ ($ por punto de felicidad). Funcionaba, pero
**resolvía con aritmética un problema que la geometría del gráfico resuelve mejor**:
en el burbujas, un grupo de errores baratos cae abajo-a-la-izquierda, donde
naturalmente no le prestás atención. No hizo falta fórmula.

### G) Felicidad por dólar en el eje X del burbujas

**Descartada.** `Σ(fel−5)/Σm` es aproximadamente `1/ticket`, y el ticket ya es el eje
Y. Correlación en log: **−0.847**. Las burbujas colapsaban sobre una hipérbola y se
perdía una dimensión del gráfico. La información se conservó como **color** de la
burbuja, que es su lugar natural (la diagonal).

---

## Controles de la UI

| Control | Vistas | Efecto |
|---------|--------|--------|
| Scatter / Barras / Burbujas | — | Vista principal |
| Categorías / Tags | barras, burbujas | Agrupamiento |
| Neto / $/pt bruto | barras | Métrica ([A](#a-tasa-cruda-σfel5σmonto) vs [B](#b-promedio-de-razones-σmontofelicidadn)) |
| Con ajuste / Sin ajuste | barras | Shrinkage on/off |
| Lineal / Log | scatter, burbujas | Escala del eje de monto |
| Excluir fijos | todas | Quita `es_fijo` |
| Todo / Deseos / Necesidades | todas | Filtra por `prioridad` |

**Sobre la escala log:** el 91% de los gastos cae en el 10% inferior de un eje lineal
(mediana $6, máximo $206), justo la franja de interés "barato y me encantó". El
default es **lineal** por preferencia visual, y en ese modo el scatter trae **zoom
sobre el eje Y** (slider + rueda) para entrar a la franja densa sin cambiar de escala.

**Sobre los filtros:** los gastos fijos no son reasignables — pesan en el presupuesto
pero no son una decisión de "gastar más o menos acá". Excluirlos deja solo lo
accionable.

---

## Bugs corregidos

Restos de la migración de la escala 1-5 a 1-9:

1. **`% en niveles buenos (4-5)`** sumaba `dist[4] + dist[5]`. En la escala actual el
   4 es *insatisfacción* y el 5 es *neutro*. Ahora es `6-9`.
2. **Colores del scatter** pintaban el 5 de verde esmeralda y mandaban todo 6-9 al
   `else` rojo: escala vieja de 1-5. Unificados en `happinessColor`.
3. **Eficiencia sin centrar** (`totalHappiness / totalAmount`) premiaba gastar barato
   en cosas indiferentes. Ahora todo pasa por `v = fel − 5`.
4. **Inconsistencia en tags**: `efficiency` usaba el valor repartido entre tags pero
   `avg` usaba el crudo. Resuelto al eliminar el reparto ([E](#e-reparto-del-monto-entre-tags-1ntags)).
5. **Tarjetas mejores/peores** usaban promedio simple; ahora usan el ponderado y
   muestran el `gap` cuando supera 0.5.

---

## Referencias

- [Empirical Bayes for multiple sample sizes — Chris Said](https://chris-said.io/2017/05/03/empirical-bayes-for-multiple-sample-sizes/)
- [On Application of the Empirical Bayes Shrinkage in Epidemiological Settings — PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2872278/)
- [Bayesian average — Wikipedia](https://en.wikipedia.org/wiki/Bayesian_average)
- [IMDb Ratings FAQ](https://help.imdb.com/article/imdb/track-movies-tv/ratings-faq/G67Y87TFYYP6TWAV)

---

> **Nota sobre los números de este documento.** Los valores citados como "caso real"
> se calcularon sobre el subconjunto de transacciones que se pudo cruzar entre
> `transacciones_input.csv` y `etiquetas.csv` reconstruyendo el hash de `id_utils.py`
> a mano (~13% de los etiquetados; la data de banca vive en XLSX). Sirven para
> ilustrar el comportamiento de cada fórmula, **no como conclusiones sobre las
> categorías**. Las propiedades algebraicas (el polo en `fel=5`, la colinealidad de
> `fel/$` con `1/ticket`, la identidad `Σ(v·m)/Σm = ponderada − 5`) valen
> independientemente de la muestra.
