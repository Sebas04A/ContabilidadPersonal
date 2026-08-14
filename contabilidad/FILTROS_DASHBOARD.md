# Filtros del dashboard

Los tabs **Evolución** y **Variaciones** comparten un filtro a nivel transacción, con los
mismos campos que el presupuesto: categorías, etiquetas, fondos, prioridad, reembolsables y
estado de etiquetado.

La diferencia con el presupuesto es dónde se aplica. `MonthlyBudget` filtra un array de
transacciones en el navegador porque las tiene todas a mano. Los dashboards no: reciben
series **ya agregadas por día**. Así que el filtro viaja como query params y el backend lo
aplica transacción por transacción antes de agrupar.

---

## 1. El problema de fondo

La agregación diaria no suma transacciones, las **lee** (`data_pipeline.py:336`):

```python
if 'SALDO' in df.columns: agg_dict['SALDO'] = 'last'
```

`SALDO` es el saldo corrido que trae el extracto del banco. Si se filtran filas antes de
agrupar, la que sobrevive como `last` sigue trayendo un saldo que incluye lo que se quitó:
**el filtro no tendría ningún efecto sobre las líneas**. Lo mismo con `TARJETA`,
`ACUMULADO_TARJETA` y `PAGO_TARJETA`, todos `last`.

## 2. La solución: restar lo excluido

En vez de rearmar las series sumando lo que queda, se le resta al dato real el aporte de lo
que salió:

```
SALDO(d)   = SALDO_real(d)   − Σ(MONTO banca excluido hasta d)
TARJETA(d) = TARJETA_real(d) − Σ(consumos excluidos)  + Σ(pagos excluidos)
```

En aritmética limpia las dos vías dan lo mismo. En la práctica no:

> **Medición (2026-08-14).** Sobre 437 días y 1122 transacciones de banca, el `SALDO` del
> extracto y `saldo_inicial + cumsum(MONTO)` divergen $12,67 acumulados, con 5 días de salto
> > $1 (dos de ellos un par que se cancela, +501,43 el 2024-06-30 y −501,98 el 2024-07-04).

Reconstruyendo, esa deriva contaminaría **toda** serie filtrada. Restando, el dato real queda
de ancla y la deriva se queda exactamente donde está hoy. Y con el filtro abierto la resta es
cero, así que la salida es idéntica a la de siempre — lo cual es verificable, y se verifica
(§6).

## 3. Alcance: qué se filtra y qué no

| Componente | ¿Se filtra? | Por qué |
|---|---|---|
| `saldo` (banca) | **Sí** | Nace de transacciones etiquetadas |
| `tarjeta` | **Sí** | Ídem, ver §4 |
| `saldo_sin_inversion`, `total`, `diff_*` | **Sí**, derivado | `MetricProcessor` los recalcula |
| `deuda_acumulada` | No | Sale de Supabase |
| `pagos_fijos`, `interpolado` | No | Salen de los grupos de interpolación |
| `notion` (capital invertido) | No | Sale de las posiciones |
| `pago_tarjeta` | No | Ver la nota al final de §4 |

Los cuatro que no se filtran **no nacen de transacciones etiquetadas**, así que ningún filtro
de categoría puede moverlos. La UI lo dice explícitamente cuando hay filtro puesto: un gráfico
filtrado a medias que no lo avisa es peor que uno sin filtrar.

## 4. La tarjeta

Parecía el caso difícil y no lo es. Medir `TARJETA` contra `cumsum(MONTO)` da una deriva de
$8.711 y 376 de 384 días con salto, lo que sugiere que hay que recalcular ciclos. **Es un
espejismo**: esa comparación mide consumos contra consumos-menos-pagos. La estructura real
(`transformations/credit_cards.py`) es:

```
ACUMULADO_TARJETA = initial_balance + cumsum(consumos)   ← acumulado plano
PAGO_TARJETA      = cumsum(pagos)                        ← verificado: nunca se resetea
TARJETA           = ACUMULADO − PAGO
```

Los dos términos son acumulados lineales, así que basta restar. No hay que recalcular ciclos.

**El ancla.** Antes de `start_date` la transformación fuerza `TARJETA`, `ACUMULADO_TARJETA` y
`PAGO_TARJETA` a cero: esos consumos ya están dentro de `initial_balance`. Descontarlos movería
una deuda que en el gráfico nunca existió. Por eso `credit_cards.py` expone `get_card_anchor()`,
extraída de `transform_credit_cards` para que el filtro use el mismo ancla y no una copia que
se desincronice.

> ⚠ En `transform_credit_cards`, la variable `min_banca_date` recibe el DataFrame de **tarjeta**,
> no el de banca. El nombre engaña. `get_card_anchor()` replica ese valor y no el literal del
> nombre; pasarle la fecha de banca daría un ancla distinta a la que produjo la serie del gráfico.

**Los pagos suben la deuda.** Un pago de tarjeta es una transacción de BANCA. Si el filtro la
excluye, el saldo sube (esa plata no salió) y la deuda tiene que subir igual (nunca se canceló).
Como `TOTAL` resta la deuda, el patrimonio queda **neutro** — que es lo correcto: pagar la
tarjeta mueve plata de bolsillo, no la crea ni la destruye. Los pagos se detectan con el mismo
`get_credit_card_payments()` que arma la serie real, sobre el subconjunto excluido, en vez de
reimplementar el reconocimiento.

Una transacción partida en splits solo cuenta como pago excluido si **ningún** pedazo sobrevivió:
el pago es un evento entero, o se hizo o no se hizo, así que no se prorratea.

> **Nota sobre `pago_tarjeta`.** No se ajusta, y es a propósito: `PAGO_TARJETA` no entra a
> `ffill_cols` en `get_daily_data('all')`, así que se va a cero en los días sin movimiento y deja
> de ser una serie diaria sobre la que se pueda restar. Por eso la identidad
> `TARJETA = ACUMULADO − PAGO` **no** vale en `df_master` (desvío máximo medido: $7.614,98), y
> por eso se ajusta `TARJETA` directo en vez de recomputarla. Ningún gráfico usa `pago_tarjeta`
> hoy; si algún día se usa, hay que resolver esto antes.

## 5. Coherencia entre las dos vistas

`/chart-data` y `/variations` tienen que recibir **los mismos** filtros, y el filtro de los
drivers tiene que tener el **mismo alcance** que el de las series. Si el desglose lista un
movimiento que el total ya no cuenta (o al revés), la diferencia se va muda a
`unexplained_difference` y nadie se entera.

Por eso el estado vive en `App.tsx`, arriba de las dos vistas, junto a `incluirInversiones`,
que está ahí por el mismo motivo.

Durante el desarrollo esto falló de verdad: en la etapa 1 se filtraban los drivers de tarjeta
mientras la serie de tarjeta no se filtraba, y Σ|residual| subió de $9.716,63 a $10.096,94. La
prueba lo detectó (§6).

## 6. Cómo se verifica

### El contrato: sin filtro, nada cambia

```bash
# antes de tocar el dashboard
python scripts/snapshot_dashboard.py capturar --nombre baseline
# después
python scripts/snapshot_dashboard.py comparar --nombre baseline
```

Congela `/chart-data` y `/variations` en sus dos variantes de `incluir_inversiones` y compara
con tolerancia de un centavo. Con los filtros apagados tiene que dar **IDÉNTICO**.

Usar `--via http` contra el backend corriendo: es el autoritativo, porque corre con el entorno
real y `DEUDA_ACUMULADA` trae los datos de Supabase. `--via directo` sirve si no hay backend,
pero si al intérprete le falta `supabase` la deuda sale en cero y el snapshot queda ciego a ese
componente. El script rechaza comparar entre modos distintos.

### La prueba del residual

Con un filtro puesto, **ningún día debe empeorar** su `unexplained_difference`. Que baje está
bien: los días de pago de tarjeta traen un residual estructural (el pago figura como driver pero
neto cero en el total) que el filtro elimina legítimamente. Que suba es un descuadre.

Medido sobre 5 filtros distintos: 0 días empeoran.

### Tests

`tests/test_dashboard_filters.py` — 34 tests con datos sintéticos: los predicados de `TxFilter`
(espejo de los del presupuesto) y la aritmética del descuento, incluidas la neutralidad del pago
y el corte del ancla. No dependen de los CSV reales a propósito: si dependieran, avisarían de
cambios en los datos en vez de cambios en el código.

## 7. Archivos

| Archivo | Rol |
|---|---|
| `backend/services/dashboard_filters.py` | `TxFilter` y sus predicados |
| `backend/services/dashboard_service.py` | `_descontar_filtrado`, `_ajuste_tarjeta` |
| `backend/storage/transformations/credit_cards.py` | `get_card_anchor()` |
| `backend/routes/dashboard.py` | Los query params en los dos endpoints |
| `pagina/src/hooks/useDashboardFilters.ts` | Estado, localStorage, serialización |
| `pagina/src/components/DashboardFilterBar.tsx` | La barra |
| `scripts/snapshot_dashboard.py` | El arnés de regresión |
| `tests/test_dashboard_filters.py` | Los tests |

## 8. Pendientes

- **Revisión visual de la barra.** El código compila y tipa limpio, pero nadie ha mirado la UI.
- **`prioridad` en una curva acumulada.** Espeja al presupuesto (solo afecta gastos, los ingresos
  siempre pasan), pero en un gráfico de patrimonio de dos años el resultado es raro: "solo
  necesidades" excluye ~$300.639 de gastos y deja todos los ingresos, así que el saldo se dispara.
  Es correcto según lo especificado, pero puede que no sea lo que se quiere leer ahí.
- **Segunda tarjeta.** Hay un pago de $647 (2026-03-02) a una tarjeta cuyo número no es
  `MY_CARD_NUMBER_DESC`. Está correctamente fuera de `PAGO_TARJETA` porque el dashboard no la
  rastrea, pero quizá debería rastrearla.
