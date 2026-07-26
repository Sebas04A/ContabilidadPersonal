import { useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Heart, Meh, Frown, AlertCircle } from 'lucide-react';
import { Transaction } from '../../services/api';

interface HappinessTabProps {
  transactions: Transaction[];
  formatCurrency: (val: number) => string;
  openLocalModal: (title: string, desc: string, txs: Transaction[]) => void;
}

/**
 * Metricas de la pestana Felicidad.
 *
 * Las formulas, el por que de cada una y las alternativas que se descartaron (con el
 * caso real que las descarto) estan en ./METRICAS_FELICIDAD.md. Leerlo antes de
 * cambiar cualquier calculo de este archivo — varias decisiones que parecen
 * arbitrarias se probaron contra datos y tienen contraejemplo documentado.
 */

/** Punto neutro de la escala 1-9: por debajo hay disgusto, por encima valor real. */
const NEUTRAL = 5;

type PriorityFilter = 'all' | 'Deseo' | 'Necesidad';

/**
 * Metrica del grafico de barras.
 *  - 'net'  : (felicidad ponderada - 5). Mas alto mejor, puede ser negativo.
 *  - 'cost' : promedio de (monto / felicidad) sin restar el neutro. Mas bajo mejor,
 *             nunca negativo — no distingue un gasto caro de uno que te resto.
 */
type BarMetric = 'net' | 'cost';

/**
 * Unica metrica de calidad del eje X. El promedio simple se sigue calculando pero
 * no se grafica: su valor esta en el `gap` contra el ponderado, que delata cuando
 * la plata y el disfrute no estan alineados dentro del grupo.
 */
const X_AXIS_LABEL = 'Felicidad Ponderada por Monto (1-9)';

/** Color por nivel de felicidad en la escala 1-9 (5 = neutro). */
const happinessColor = (level: number) => {
  if (level >= 8) return '#34d399';
  if (level >= 6) return '#10b981';
  if (level === 5) return '#64748b';
  if (level >= 3) return '#fb7185';
  return '#e11d48';
};

/** Escala divergente para la eficiencia: rojo (quema plata) → gris (neutro) → verde (rinde). */
const NEG_RGB = [225, 29, 72];
const MID_RGB = [100, 116, 139];
const POS_RGB = [16, 185, 129];

const efficiencyColor = (eff: number, maxAbs: number) => {
  if (maxAbs <= 0) return `rgb(${MID_RGB.join(',')})`;
  const t = Math.max(-1, Math.min(1, eff / maxAbs));
  const target = t >= 0 ? POS_RGB : NEG_RGB;
  const k = Math.abs(t);
  return `rgb(${MID_RGB.map((v, i) => Math.round(v + (target[i] - v) * k)).join(',')})`;
};

/**
 * Un grupo listo para encoger: su estimacion propia, cuanta evidencia la respalda
 * y cuanto varia por dentro.
 */
interface ShrinkInput {
  /** Estimacion propia del grupo (media, ponderada o no). */
  estimate: number;
  /** Tamano muestral efectivo. Para medias ponderadas, el n efectivo de Kish. */
  effectiveN: number;
  /** Varianza intra-grupo observada. */
  withinVar: number;
  /** Peso del grupo al agrupar varianzas (dinero o nº de transacciones). */
  weight: number;
}

/**
 * Empirical Bayes / James-Stein para medias con tamanos muestrales distintos.
 *
 *   B_i = sigma2_i / (tau2 + sigma2_i)        peso hacia la media global
 *   out = (1 - B_i)*estimate_i + B_i*mu
 *
 * donde sigma2_i = s2_pooled / effectiveN_i es la varianza de muestreo de la media
 * del grupo, y tau2 = max(0, Var(estimate_i) - mean(sigma2_i)) es la varianza real
 * ENTRE grupos por metodo de momentos. Si los grupos difieren mucho mas que su
 * propio ruido, tau2 es grande, B_i chico y casi no se encoge; si los grupos son
 * indistinguibles, tau2 -> 0 y todo colapsa a la media global.
 *
 * s2 se agrupa (pooled) entre todos los grupos en vez de usar el s2 propio de cada
 * uno: un grupo de una sola transaccion tiene varianza observada 0, y usarla daria
 * B_i = 0, o sea "confio ciegamente en un unico dato". Asume varianzas intra-grupo
 * parecidas, que es la condicion habitual de este estimador.
 *
 * Referencia: https://chris-said.io/2017/05/03/empirical-bayes-for-multiple-sample-sizes/
 */
const shrinkEmpiricalBayes = (
  groups: ShrinkInput[],
  mu: number
): { results: { value: number; B: number }[]; degenerate: boolean; tau2: number } => {
  const k = groups.length;
  if (k < 2) {
    return { results: groups.map(g => ({ value: g.estimate, B: 0 })), degenerate: false, tau2: 0 };
  }

  const totalWeight = groups.reduce((acc, g) => acc + g.weight, 0);
  const s2Pooled = totalWeight > 0
    ? groups.reduce((acc, g) => acc + Math.max(g.withinVar, 0) * g.weight, 0) / totalWeight
    : 0;

  const sigma2 = groups.map(g => (g.effectiveN > 0 ? s2Pooled / g.effectiveN : Infinity));

  // tau2 por DerSimonian-Laird, el estandar de meta-analisis de efectos aleatorios.
  // La version ingenua (Var sin ponderar de las medias menos el ruido promedio) trata
  // igual a un grupo de 1 transaccion que a uno de 30, asi que los grupos chicos le
  // inflan las dos partes de la resta y el resultado es inestable. DL pondera cada
  // grupo por su precision (w_i = 1/sigma2_i) antes de medir la dispersion.
  //   Q   = Σ w_i (y_i - y_ponderada)²
  //   C   = Σw_i - Σw_i²/Σw_i
  //   tau2 = (Q - (k-1)) / C
  const w = sigma2.map(s => (isFinite(s) && s > 0 ? 1 / s : 0));
  const sumW = w.reduce((acc, x) => acc + x, 0);
  let tau2 = 0;
  if (sumW > 0) {
    const yBarW = groups.reduce((acc, g, i) => acc + w[i] * g.estimate, 0) / sumW;
    const Q = groups.reduce((acc, g, i) => acc + w[i] * (g.estimate - yBarW) ** 2, 0);
    const C = sumW - w.reduce((acc, x) => acc + x * x, 0) / sumW;
    tau2 = C > 0 ? (Q - (k - 1)) / C : 0;
  }

  // tau2 <= 0 significa que el metodo de momentos toco su piso: el ruido estimado se
  // come toda la varianza entre grupos. Encoger con tau2 = 0 da B_i = 1 para todos y
  // deja el grafico con todas las barras identicas en la media, que no informa nada.
  // Es un artefacto conocido del estimador, no una conclusion: mejor devolver los
  // valores crudos y avisar.
  if (!(tau2 > 0)) {
    return { results: groups.map(g => ({ value: g.estimate, B: 0 })), degenerate: true, tau2: 0 };
  }

  return {
    results: groups.map((g, i) => {
      if (!isFinite(sigma2[i])) return { value: mu, B: 1 };
      const B = Math.min(1, Math.max(0, sigma2[i] / (tau2 + sigma2[i])));
      return { value: (1 - B) * g.estimate + B * mu, B };
    }),
    degenerate: false,
    tau2,
  };
};

/** Una transacción atribuida a un grupo (categoría o tag). */
interface GroupEntry {
  key: string;
  tx: Transaction;
}

export interface GroupStat {
  name: string;
  /** Promedio simple: cada transacción vota igual. Es "la experiencia típica". */
  avgSimple: number;
  /** Promedio ponderado por monto: cada dólar vota igual. Es "cómo rindió la plata". */
  avgWeighted: number;
  /** Suma de puntos netos Σ(fel-5). Numerador de la tasa cruda. */
  netPoints: number;
  /**
   * Puntos netos ponderados por monto: Σ((fel-5)·monto). Identico a
   * (avgWeighted - 5) · totalAmount. Cada dolar pesa igual, asi que una transaccion
   * barata no puede dar vuelta el signo del grupo.
   */
  netWeighted: number;
  /**
   * Tasa cruda: puntos netos por cada $100. Sensible a montos chicos por
   * construccion (numerador por transaccion, denominador por dinero). Se muestra
   * como dato secundario, no como ranking.
   */
  perDollar: number;
  /** Gasto promedio por transacción. Invariante si crecés el grupo repitiendo. */
  ticket: number;
  /**
   * Promedio de (monto / felicidad) transaccion por transaccion, SIN restar el neutro.
   * Mas bajo = mejor. No puede ser negativo, asi que no distingue "caro" de "daniño":
   * un gasto de felicidad 1 solo se ve como uno que costo mucho por punto.
   */
  avgCostPerHappiness: number;
  /**
   * n efectivo de Kish: (Σm)² / Σm². Para la media ponderada por monto, mide cuantas
   * observaciones "de verdad" hay. Un grupo de 20 transacciones donde una vale $200 y
   * el resto $2 tiene n_eff ~ 2, no 20.
   */
  effectiveN: number;
  /** Varianza intra-grupo de (fel-5), ponderada por monto. */
  withinVarNet: number;
  /**
   * Media de ln(monto/felicidad) y su varianza intra-grupo.
   *
   * El shrinkage del coste se hace en log y no en dolares: monto/felicidad es una
   * razon de cola pesada, su varianza crece con el CUADRADO del monto, y con gastos
   * grandes el ruido estimado se come la varianza entre grupos (tau2 -> 0, todo
   * colapsa a la media). En log la escala se estabiliza y el estimador se comporta.
   * exp(media de logs) es la media geometrica, que es la medida natural de centro
   * para una razon.
   */
  meanLogCost: number;
  withinVarLogCost: number;
  /**
   * OJO: para tags, los totales NO son aditivos entre grupos — una transaccion con
   * varios tags cuenta completa en cada uno. Sumar tags da mas que el gasto real.
   */
  totalAmount: number;
  count: number;
  /** avgWeighted - avgSimple. Grande => plata y disfrute desalineados adentro del grupo. */
  gap: number;
  txs: Transaction[];
}

/**
 * Agrega entradas en estadísticas por grupo.
 *
 * Cada transaccion entra completa en cada grupo al que pertenece. Antes se repartia
 * el monto entre los tags (1/nTags) para que la plata se conservara al sumar tags,
 * pero eso penalizaba a los gastos mejor etiquetados: en el tag Renata los Motel
 * (felicidad 7-9) llevan 3 tags y quedaban al 33% de su peso, mientras el esquite
 * (felicidad 1) llevaba uno solo y pesaba completo — el tag caia de +1.81 a +0.73
 * por como estaban descritos sus gastos, no por como fueron. Como estas vistas son
 * rankings y nunca se suman tags entre si, la conservacion no compraba nada.
 */
const buildGroupStats = (entries: GroupEntry[]): GroupStat[] => {
  const acc: Record<string, {
    sumFel: number;
    sumAmount: number;
    sumFelByAmount: number;
    sumNet: number;
    sumCostRatio: number;
    sumAmountSq: number;
    sumNetSqByAmount: number;
    sumLogCost: number;
    sumLogCostSq: number;
    count: number;
    txs: Transaction[];
  }> = {};

  entries.forEach(({ key, tx }) => {
    if (!acc[key]) {
      acc[key] = {
        sumFel: 0, sumAmount: 0, sumFelByAmount: 0, sumNet: 0, sumCostRatio: 0,
        sumAmountSq: 0, sumNetSqByAmount: 0, sumLogCost: 0, sumLogCostSq: 0, count: 0, txs: [],
      };
    }
    const amount = Math.abs(tx.MONTO);
    const net = tx.felicidad - NEUTRAL;
    const costRatio = amount / tx.felicidad;
    const logCost = Math.log(costRatio);
    const a = acc[key];
    a.sumFel += tx.felicidad;
    a.sumAmount += amount;
    a.sumFelByAmount += tx.felicidad * amount;
    a.sumNet += net;
    a.sumCostRatio += costRatio;
    a.sumAmountSq += amount * amount;
    a.sumNetSqByAmount += net * net * amount;
    a.sumLogCost += logCost;
    a.sumLogCostSq += logCost * logCost;
    a.count += 1;
    a.txs.push(tx);
  });

  return Object.entries(acc).map(([name, a]) => {
    const avgSimple = a.count > 0 ? a.sumFel / a.count : 0;
    const avgWeighted = a.sumAmount > 0 ? a.sumFelByAmount / a.sumAmount : avgSimple;
    const netRatio = avgWeighted - NEUTRAL;
    const avgCost = a.count > 0 ? a.sumCostRatio / a.count : 0;
    return {
      name,
      avgSimple,
      avgWeighted,
      netPoints: a.sumNet,
      netWeighted: a.sumFelByAmount - NEUTRAL * a.sumAmount,
      perDollar: a.sumAmount > 0 ? (a.sumNet / a.sumAmount) * 100 : 0,
      ticket: a.count > 0 ? a.sumAmount / a.count : 0,
      avgCostPerHappiness: avgCost,
      effectiveN: a.sumAmountSq > 0 ? (a.sumAmount * a.sumAmount) / a.sumAmountSq : 0,
      withinVarNet: a.sumAmount > 0
        ? Math.max(0, a.sumNetSqByAmount / a.sumAmount - netRatio * netRatio)
        : 0,
      meanLogCost: a.count > 0 ? a.sumLogCost / a.count : 0,
      withinVarLogCost: a.count > 0
        ? Math.max(0, a.sumLogCostSq / a.count - (a.sumLogCost / a.count) ** 2)
        : 0,
      totalAmount: a.sumAmount,
      count: a.count,
      gap: avgWeighted - avgSimple,
      txs: a.txs,
    };
  });
};

const getHappinessInfo = (level: number) => {
    if (level >= 8) return { icon: <Heart size={24} className="text-emerald-400" />, label: 'Agrega Gran Valor', color: 'text-emerald-400', bg: 'bg-emerald-500/20', border: 'border-emerald-500/30' };
    if (level >= 6) return { icon: <Heart size={24} className="text-emerald-500" />, label: 'Agrega Valor', color: 'text-emerald-500', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' };
    if (level === 5) return { icon: <Meh size={24} className="text-surface-400" />, label: 'Neutro', color: 'text-surface-400', bg: 'bg-surface-700/50', border: 'border-surface-600/50' };
    if (level >= 3) return { icon: <Frown size={24} className="text-rose-400" />, label: 'Insatisfacción', color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/20' };
    if (level >= 1) return { icon: <Frown size={24} className="text-rose-500" />, label: 'Arrepentimiento', color: 'text-rose-500', bg: 'bg-rose-500/20', border: 'border-rose-500/30' };
    return { icon: null, label: 'Desconocido', color: 'text-surface-400', bg: 'bg-surface-800', border: 'border-surface-700' };
};

export function HappinessTab({ transactions, formatCurrency, openLocalModal }: HappinessTabProps) {
  const [chartView, setChartView] = useState<'individual' | 'bar' | 'bubble'>('individual');
  const [chartGroup, setChartGroup] = useState<'category' | 'tag'>('category');
  const [logScale, setLogScale] = useState(false);
  const [barMetric, setBarMetric] = useState<BarMetric>('net');
  const [useShrink, setUseShrink] = useState(true);
  const [excludeFijos, setExcludeFijos] = useState(false);
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('all');

  /**
   * Gastos calificados que alimentan los gráficos de grupos.
   * Los fijos y las necesidades se pueden excluir porque no son reasignables:
   * pesan en el presupuesto pero no son una decisión de "gastar más o menos acá".
   */
  const ratedExpenses = useMemo(() => transactions.filter(t =>
    t.MONTO < 0 &&
    t.felicidad >= 1 && t.felicidad <= 9 &&
    Math.abs(t.MONTO) > 0 &&
    (!excludeFijos || !t.es_fijo) &&
    (priorityFilter === 'all' || t.prioridad === priorityFilter)
  ), [transactions, excludeFijos, priorityFilter]);

  const happinessStats = useMemo(() => {
    const expenses = transactions.filter(t => t.MONTO < 0);
    const unratedExpenses = expenses.filter(t => !t.felicidad || t.felicidad < 1 || t.felicidad > 9);

    const dist: Record<number, { amount: number; count: number }> = {};
    for (let i = 1; i <= 9; i++) {
        dist[i] = { amount: 0, count: 0 };
    }

    let totalRatedAmount = 0;
    let weightedHappinessSum = 0;

    ratedExpenses.forEach(t => {
      const amt = Math.abs(t.MONTO);
      dist[t.felicidad].amount += amt;
      dist[t.felicidad].count += 1;
      totalRatedAmount += amt;
      weightedHappinessSum += t.felicidad * amt;
    });

    const unratedAmount = unratedExpenses.reduce((acc, t) => acc + Math.abs(t.MONTO), 0);
    const overallHappinessScore = totalRatedAmount > 0 ? (weightedHappinessSum / totalRatedAmount) : 0;

    // Niveles 6-9 = agregan valor real. El 5 es neutro y el 4 ya es insatisfaccion.
    const goodAmount = [6, 7, 8, 9].reduce((acc, lvl) => acc + dist[lvl].amount, 0);

    return {
        dist,
        totalRatedAmount,
        goodAmount,
        unratedAmount,
        unratedCount: unratedExpenses.length,
        overallHappinessScore,
    };
  }, [transactions, ratedExpenses]);

  const scatterOptions = useMemo(() => {
    const expenses = transactions.filter(
      t => t.MONTO < 0 && t.felicidad >= 1 && t.felicidad <= 9 && Math.abs(t.MONTO) > 0
    );
    const data = expenses.map(t => [
      t.felicidad + (Math.random() * 0.4 - 0.2), // jitter for visibility
      Math.abs(t.MONTO),
      t.nombre_limpio || t.DESCRIPCION,
      new Date(t.FECHA).toLocaleDateString('es-CO')
    ]);

    return {
      tooltip: {
        trigger: 'item',
        formatter: function (params: any) {
          const d = params.data;
          return `<div class="font-sans text-sm text-white">
                    <strong>${d[2]}</strong><br/>
                    Fecha: ${d[3]}<br/>
                    Monto: $${d[1].toLocaleString('es-CO')}<br/>
                    Felicidad: ${Math.round(d[0])}
                  </div>`;
        },
        backgroundColor: '#1f2937',
        borderColor: '#374151',
        textStyle: { color: '#f3f4f6' }
      },
      grid: {
        left: '10%',
        // En lineal el slider de zoom ocupa el margen derecho.
        right: logScale ? '5%' : '9%',
        bottom: '15%',
        top: '10%',
        containLabel: true
      },
      // En escala lineal la cola de gastos grandes aplasta al resto contra el borde
      // inferior. El zoom permite entrar a la franja densa sin cambiar de escala.
      dataZoom: logScale ? [] : [
        { type: 'inside', yAxisIndex: 0, filterMode: 'none' },
        {
          type: 'slider', yAxisIndex: 0, filterMode: 'none',
          width: 14, right: 10,
          backgroundColor: 'rgba(255,255,255,0.03)',
          borderColor: 'rgba(255,255,255,0.08)',
          fillerColor: 'rgba(99,102,241,0.20)',
          handleStyle: { color: '#6366f1' },
          textStyle: { color: '#9ca3af', fontSize: 10 }
        }
      ],
      xAxis: {
        name: 'Nivel absoluto de Felicidad (1-9)',
        nameLocation: 'middle',
        nameGap: 30,
        type: 'value',
        min: 0.5,
        max: 9.5,
        interval: 1,
        splitLine: { show: false },
        axisLabel: {
          color: '#9ca3af',
          formatter: (val: number) => {
              if (val === 1) return '1';
              if (val === 5) return '5 - Neutro';
              if (val === 9) return '9';
              return Math.round(val);
          }
        }
      },
      yAxis: {
        name: logScale ? 'Monto ($) — escala log' : 'Monto ($)',
        // Log: ~90% de los gastos viven en la parte baja del rango. En escala lineal
        // esa franja queda aplastada contra el borde y es justo la zona de interés
        // ("barato y me encantó"). Con lineal, usar el zoom para entrar ahí.
        type: logScale ? 'log' : 'value',
        ...(logScale ? { logBase: 10 } : {}),
        splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        axisLabel: { color: '#9ca3af', formatter: (val: number) => val >= 1000 ? (val/1000) + 'k' : val }
      },
      series: [
        {
          symbolSize: 16,
          itemStyle: {
            color: (params: any) => happinessColor(Math.round(params.data[0])),
            opacity: 0.8,
            borderColor: '#111827',
            borderWidth: 1.5
          },
          data: data,
          type: 'scatter'
        }
      ]
    };
  }, [transactions, logScale]);

  // 1. Agrupamiento de Categorías (una transacción pertenece a una sola)
  const categoriesStats = useMemo(() => buildGroupStats(
    ratedExpenses.map(t => ({
      key: (!t.categoria || t.categoria === '---') ? 'Sin Categoría' : t.categoria,
      tx: t,
    }))
  ), [ratedExpenses]);

  // 2. Agrupamiento de Tags: la transacción entra completa en cada tag que lleva.
  //    Los tags se solapan, así que sus totales no son aditivos entre sí.
  const tagsStats = useMemo(() => {
    const entries: GroupEntry[] = [];
    ratedExpenses.forEach(t => {
      const tTags = t.tags ? t.tags.split(',').map(tag => tag.trim()).filter(Boolean) : [];
      if (tTags.length === 0) {
        entries.push({ key: 'Sin Etiqueta', tx: t });
      } else {
        tTags.forEach(tag => entries.push({ key: tag, tx: t }));
      }
    });
    return buildGroupStats(entries);
  }, [ratedExpenses]);

  /**
   * Mejores y peores categorias por felicidad ponderada por monto: mide como rindio
   * la plata, no la experiencia tipica. Ver `gap` para detectar desalineacion interna.
   */
  const bestCategories = useMemo(
    () => [...categoriesStats].sort((a, b) => b.avgWeighted - a.avgWeighted || b.totalAmount - a.totalAmount).slice(0, 3),
    [categoriesStats]
  );
  const worstCategories = useMemo(
    () => [...categoriesStats].sort((a, b) => a.avgWeighted - b.avgWeighted || b.totalAmount - a.totalAmount).slice(0, 3),
    [categoriesStats]
  );

  /**
   * Ranking de rendimiento del dinero: puntos netos de felicidad por dolar gastado,
   * ponderando cada dolar igual  =  (felicidad ponderada - 5).
   *
   * No se usa la tasa cruda \u03a3(fel-5)/\u03a3monto porque cada transaccion aporta lo mismo
   * al numerador sin importar su tamano, mientras el denominador va en dinero: un
   * gasto de $1.75 puede dar vuelta el signo de un tag de $25 (caso real: Renata,
   * -9.30 -> +7.14 al quitar una sola transaccion). Ponderar el numerador arregla
   * eso, al precio de dejar de ser una tasa "por dolar" en unidades \u2014 ser una tasa
   * es dividir por el dinero y ser robusto es multiplicar por el, se cancelan.
   * La tasa cruda queda en el tooltip como dato secundario.
   */
  const barOptions = useMemo(() => {
    const dataSet = chartGroup === 'category' ? categoriesStats : tagsStats;
    if (dataSet.length === 0) return null;

    // Shrinkage empirico-bayesiano: el peso hacia la media global sale de la razon
    // entre el ruido de cada grupo y la varianza real entre grupos, no de un
    // parametro elegido a mano. Ver shrinkEmpiricalBayes.
    // La media global sale de las transacciones, no de sumar los grupos: los tags se
    // solapan y sumarlos contaria la misma plata varias veces.
    const globalNet = happinessStats.overallHappinessScore - NEUTRAL;
    const totalCount = Math.max(dataSet.reduce((acc, d) => acc + d.count, 0), 1);
    const globalLogCost = dataSet.reduce((acc, d) => acc + d.meanLogCost * d.count, 0) / totalCount;

    const shrunkNets = shrinkEmpiricalBayes(
      dataSet.map(d => ({
        estimate: d.avgWeighted - NEUTRAL,
        effectiveN: d.effectiveN,
        withinVar: d.withinVarNet,
        weight: d.totalAmount,
      })),
      globalNet
    );
    // El coste se encoge en log y se des-loguea al final: en dolares la razon es de
    // cola pesada y el estimador degenera (ver meanLogCost).
    const shrunkCosts = shrinkEmpiricalBayes(
      dataSet.map(d => ({
        estimate: d.meanLogCost,
        effectiveN: d.count,
        withinVar: d.withinVarLogCost,
        weight: d.count,
      })),
      globalLogCost
    );

    const isCost = barMetric === 'cost';
    const degenerate = isCost ? shrunkCosts.degenerate : shrunkNets.degenerate;

    const rows = dataSet
      .map((d, i) => {
        // Con el shrink apagado se grafica la estimacion cruda de cada grupo: util
        // para ver cuanto del ranking es evidencia y cuanto es ajuste.
        const shrunk = useShrink ? shrunkNets.results[i].value : d.avgWeighted - NEUTRAL;
        const shrunkCost = useShrink
          ? Math.exp(shrunkCosts.results[i].value)  // de vuelta a dólares
          : Math.exp(d.meanLogCost);
        // Cuanto se encogio: 0% = el grupo conserva su numero, 100% = quedo en la media.
        const shrinkPct = useShrink
          ? (isCost ? shrunkCosts.results[i].B : shrunkNets.results[i].B) * 100
          : 0;
        // En modo coste el numero nunca es negativo: se marca en rojo igual cuando el
        // grupo es neto negativo, para que el punto ciego de la metrica quede visible.
        const isHarmful = shrunk < -0.01;
        return {
          value: Number((isCost ? shrunkCost : shrunk).toFixed(3)),
          shrunk,
          shrunkCost,
          shrinkPct,
          rawEstimate: isCost ? Math.exp(d.meanLogCost) : d.avgWeighted - NEUTRAL,
          rawCost: d.avgCostPerHappiness,
          raw: d.perDollar,
          isHarmful,
          // Cuanto cuesta un punto de felicidad en una transaccion tipica del grupo.
          // Robusto porque ticket y shrunk lo son. Solo aplica si el grupo suma positivo.
          costPerPoint: shrunk > 0.01 ? d.ticket / shrunk : null,
          name: d.name,
          count: d.count,
          totalAmount: d.totalAmount,
          ticket: d.ticket,
          avgWeighted: d.avgWeighted,
          gap: d.gap,
          txs: d.txs,
          itemStyle: {
            color: isCost
              ? (isHarmful ? '#e11d48' : '#8b5cf6')
              : (shrunk > 0.01 ? '#10b981' : shrunk < -0.01 ? '#e11d48' : '#64748b'),
            borderRadius: !isCost && shrunk < 0 ? [4, 0, 0, 4] : [0, 4, 4, 0]
          }
        };
      })
      // ECharts dibuja de abajo hacia arriba, y "mejor" va arriba. En neto mejor es
      // mas alto; en coste mejor es mas bajo, asi que se invierte el orden.
      .sort((a, b) => isCost ? b.value - a.value : a.value - b.value);

    const option = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const d = params[0].data;
          const amountLabel = chartGroup === 'category' ? 'Gastado Total' : 'Gastado con este tag';
          const cost = d.costPerPoint !== null
            ? `$${d.costPerPoint.toLocaleString('es-CO', { maximumFractionDigits: 2 })} por punto de felicidad`
            : 'No compra felicidad neta';
          const head = isCost
            ? `<span style="color:${d.isHarmful ? '#fb7185' : '#c4b5fd'}">$${d.value.toFixed(2)} por punto de felicidad bruta</span>` +
              (d.isHarmful
                ? `<br/><span style="color:#fb7185;font-size:11px">⚠ Grupo neto NEGATIVO (${d.shrunk.toFixed(2)}); esta métrica no lo puede mostrar</span>`
                : '') +
              ''
            : `<span style="color:${d.value >= 0 ? '#34d399' : '#fb7185'}">${d.value >= 0 ? '+' : ''}${d.value.toFixed(2)} pts netos (felicidad del dólar promedio)</span><br/>${cost}`;
          const shrinkNote = !useShrink
            ? `<span style="color:#fbbf24;font-size:11px">Sin ajuste — grupos con pocas transacciones no son confiables</span>`
            : degenerate
              ? `<span style="color:#fbbf24;font-size:11px">Ajuste inactivo: el ruido intra-grupo se come la varianza entre grupos (τ²≤0)</span>`
              : `<span style="color:#6b7280;font-size:11px">Propio: ${d.rawEstimate >= 0 ? '+' : ''}${d.rawEstimate.toFixed(2)} · encogido ${d.shrinkPct.toFixed(0)}% hacia la media</span>`;
          return `<strong class="text-white">${d.name}</strong><br/>
                  ${head}<br/>
                  ${shrinkNote}<br/>
                  <span style="color:#9ca3af">\u2500\u2500</span><br/>
                  Felicidad ponderada: \u2605 ${d.avgWeighted.toFixed(2)} / 9<br/>
                  ${amountLabel}: $${d.totalAmount.toLocaleString('es-CO', { maximumFractionDigits: 0 })}<br/>
                  Ticket promedio: $${d.ticket.toLocaleString('es-CO', { maximumFractionDigits: 2 })}<br/>
                  Transacciones: ${d.count}<br/>
                  Gap ponderado-simple: ${d.gap >= 0 ? '+' : ''}${d.gap.toFixed(2)}<br/>
                  <span style="color:#6b7280;font-size:11px">Tasa cruda (sensible a montos chicos): ${d.raw.toFixed(2)} pts/$100</span>`;
        },
        backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#f3f4f6' }
      },
      grid: { left: '3%', right: '6%', bottom: '3%', top: '5%', containLabel: true },
      xAxis: {
        // No es una tasa "puntos / dólar": es un promedio de puntos donde el peso de
        // cada transacción es su monto. La unidad de observación es el dólar.
        name: isCost
          ? 'Dólares por punto de felicidad bruta (más bajo = mejor)'
          : 'Felicidad neta del dólar promedio (−4 a +4)',
        nameLocation: 'middle',
        nameGap: 28,
        nameTextStyle: { color: '#9ca3af', fontSize: 11 },
        type: 'value',
        splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        axisLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.15)' } },
        axisLabel: { color: '#9ca3af' }
      },
      yAxis: {
        type: 'category',
        data: rows.map(d => d.name),
        axisLabel: { color: '#e5e7eb', fontWeight: 'bold' },
        axisTick: { show: false },
        axisLine: { show: false }
      },
      series: [{
        name: 'Eficiencia',
        type: 'bar',
        data: rows,
        // Marca dónde estaba el valor sin ajustar, para que el efecto del shrinkage
        // sea visible: sin esto una corrección del 1-5% es indistinguible a ojo.
        markPoint: useShrink && !degenerate ? {
          symbol: 'rect',
          symbolSize: [2, 22],
          silent: true,
          itemStyle: { color: 'rgba(255,255,255,0.55)' },
          label: { show: false },
          data: rows.map((d, i) => ({ xAxis: d.rawEstimate, yAxis: i })),
        } : undefined,
        label: {
          show: true,
          position: 'right',
          color: '#9ca3af',
          fontSize: 10,
          formatter: (p: any) => {
            if (isCost) return `$${p.data.ticket.toFixed(2)} tkt`;
            return p.data.costPerPoint !== null ? `$${p.data.costPerPoint.toFixed(2)}/pt` : '';
          }
        }
      }]
    };

    const shrinkPcts = rows.map(r => r.shrinkPct);
    return {
      option,
      diag: {
        degenerate,
        tau2: isCost ? shrunkCosts.tau2 : shrunkNets.tau2,
        minB: Math.min(...shrinkPcts),
        maxB: Math.max(...shrinkPcts),
      },
    };
  }, [categoriesStats, tagsStats, chartGroup, barMetric, useShrink, happinessStats.overallHappinessScore]);

  const bubbleOptions = useMemo(() => {
    const dataSet = chartGroup === 'category' ? categoriesStats : tagsStats;

    const data = dataSet
      .filter(d => d.ticket > 0)
      .map(d => [
        d.avgWeighted,          // 0 -> felicidad ponderada por monto (X)
        d.ticket,               // 1 -> ticket promedio (Y, log) — invariante si repetis
        d.count,                // 2 -> cantidad (tamano)
        d.name,                 // 3 -> nombre
        d.txs,                  // 4 -> transacciones
        d.perDollar,            // 5 -> eficiencia (color)
        d.totalAmount,          // 6 -> exposicion total
        d.avgSimple,            // 7
        d.avgWeighted,          // 8
      ]);

    const maxCount = Math.max(...data.map(d => d[2] as number), 1);
    const maxAbsEff = Math.max(...data.map(d => Math.abs(d[5] as number)), 1e-9);


    return {
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          const d = params.data;
          const gap = (d[8] as number) - (d[7] as number);
          return `<div class="font-sans text-sm text-white">
                    <strong class="text-white text-base">${d[3]}</strong><br/>
                    Felicidad simple: \u2605 ${(d[7] as number).toFixed(2)}<br/>
                    Felicidad ponderada: \u2605 ${(d[8] as number).toFixed(2)}
                      <span style="color:${gap >= 0 ? '#34d399' : '#fb7185'}">(gap ${gap >= 0 ? '+' : ''}${gap.toFixed(2)})</span><br/>
                    Ticket promedio: $${(d[1] as number).toLocaleString('es-CO', { maximumFractionDigits: 2 })}<br/>
                    Eficiencia: ${(d[5] as number).toFixed(2)} pts / $100<br/>
                    Gasto total: $${(d[6] as number).toLocaleString('es-CO', { maximumFractionDigits: 0 })}<br/>
                    Transacciones: ${d[2]}
                  </div>`;
        },
        backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#f3f4f6' }
      },
      grid: { left: '8%', right: '8%', bottom: '15%', top: '10%', containLabel: true },
      xAxis: {
        name: X_AXIS_LABEL,
        nameLocation: 'middle',
        nameGap: 30,
        type: 'value',
        min: 0.5,
        max: 9.5,
        interval: 1,
        splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        axisLabel: { color: '#9ca3af' }
      },
      yAxis: {
        // Ticket promedio y no gasto total: es invariante bajo la accion de "repetir
        // mas veces", asi el punto no cambia de cuadrante cuando actuas sobre el.
        name: logScale
          ? 'Gasto Promedio por Transaccion ($) — escala log'
          : 'Gasto Promedio por Transaccion ($)',
        type: logScale ? 'log' : 'value',
        ...(logScale ? { logBase: 10 } : {}),
        splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        axisLabel: { color: '#9ca3af', formatter: (val: number) => val >= 1000 ? (val / 1000) + 'k' : val }
      },
      series: [
        {
          name: chartGroup === 'category' ? 'Categorias' : 'Tags',
          type: 'scatter',
          symbolSize: (d: any) => 15 + (d[2] / maxCount) * 45,
          label: {
            show: true,
            formatter: (params: any) => params.data[3],
            position: 'top',
            color: '#e5e7eb',
            fontSize: 10,
            fontWeight: 'bold'
          },
          itemStyle: {
            // Color = felicidad por dolar. Asi la eficiencia queda visible sin
            // gastar un eje en ella (es la diagonal del grafico).
            color: (params: any) => efficiencyColor(params.data[5], maxAbsEff),
            opacity: 0.8,
            borderColor: '#111827',
            borderWidth: 1.5
          },
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: 'rgba(255,255,255,0.25)', type: 'dashed' },
            label: { show: false },
            data: [{ xAxis: NEUTRAL }]
          },
          data
        }
      ]
    };
  }, [categoriesStats, tagsStats, chartGroup, logScale]);

  return (
    <div className="space-y-6 animate-fade-in">
        {/* Summary */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="col-span-1 md:col-span-2 bg-gradient-to-br from-surface-900 to-surface-950 border border-white/10 p-6 rounded-2xl flex flex-col justify-between shadow-lg relative overflow-hidden">
                <div className="absolute top-0 right-0 w-48 h-48 bg-pink-500/10 rounded-full blur-3xl pointer-events-none"></div>
                <div className="relative z-10">
                    <p className="text-surface-400 uppercase font-bold tracking-wider text-sm mb-2">Gastos Etiquetados</p>
                    <h3 className="text-4xl font-bold text-white tracking-tight">{formatCurrency(happinessStats.totalRatedAmount)}</h3>
                    <p className="text-emerald-400 mt-2 font-medium">
                        {happinessStats.totalRatedAmount > 0 ? ((happinessStats.goodAmount / happinessStats.totalRatedAmount) * 100).toFixed(0) : 0}% en niveles que agregan valor (6-9)
                    </p>
                </div>
            </div>
            <div 
                className="bg-surface-900/60 border border-dashed border-white/20 p-6 rounded-2xl flex flex-col justify-center items-center text-center shadow-lg cursor-pointer hover:bg-surface-800 transition-colors group"
                onClick={() => openLocalModal("Gastos sin calificar", "Transacciones que aún no tienen un nivel de felicidad asignado.", transactions.filter(t => t.MONTO < 0 && (!t.felicidad || t.felicidad < 1 || t.felicidad > 9)).sort((a,b) => a.MONTO - b.MONTO))}
            >
                <p className="text-surface-400 uppercase font-bold tracking-wider text-sm mb-2 group-hover:text-surface-300 transition-colors">Sin Etiquetar</p>
                <h3 className="text-2xl font-bold text-surface-300 tracking-tight">{formatCurrency(happinessStats.unratedAmount)}</h3>
                <p className="text-surface-500 mt-1 text-sm">{happinessStats.unratedCount} transacciones sin calificar</p>
            </div>
        </div>

        {/* Insights de Felicidad */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Happiness Score Card */}
            <div className="bg-surface-900/60 border border-white/10 p-6 rounded-2xl flex flex-col justify-between shadow-xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-primary-500/5 rounded-full blur-2xl"></div>
                <div>
                    <h4 className="text-xs font-bold text-surface-400 uppercase tracking-widest mb-1">Retorno de Felicidad (ROI)</h4>
                    <p className="text-[10px] text-surface-500">Promedio de felicidad ponderado por el monto de tus gastos.</p>
                </div>
                <div className="my-3 flex items-baseline gap-2">
                    <span className="text-4xl font-extrabold text-white tracking-tight">{happinessStats.overallHappinessScore.toFixed(1)}</span>
                    <span className="text-sm text-surface-500">/ 9.0</span>
                </div>
                <div className="w-full bg-surface-950 h-2 rounded-full overflow-hidden border border-white/5">
                    <div 
                        className="h-full rounded-full bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-500 shadow-[0_0_8px_rgba(236,72,153,0.4)]"
                        style={{ width: `${(happinessStats.overallHappinessScore / 9) * 100}%` }}
                    />
                </div>
            </div>

            {/* Best Categories */}
            <div className="bg-surface-900/60 border border-emerald-500/10 p-6 rounded-2xl flex flex-col justify-between shadow-xl relative overflow-hidden">
                <div>
                    <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                        <Heart size={14} /> Mejor Rendimiento del Dinero
                    </h4>
                    <div className="space-y-1.5">
                        {bestCategories.map(cat => (
                            <div key={cat.name} className="flex justify-between items-center text-xs bg-surface-950/40 p-2 rounded-lg border border-white/5">
                                <span className="font-semibold text-white truncate max-w-[60%] uppercase">{cat.name}</span>
                                <div className="flex items-center gap-1.5">
                                    <span className="font-mono text-emerald-400 font-bold" title="Felicidad ponderada por monto">★ {cat.avgWeighted.toFixed(1)}</span>
                                    {Math.abs(cat.gap) >= 0.5 && (
                                        <span className="text-[10px] text-amber-400 font-mono" title="Diferencia con el promedio simple: la plata y el disfrute no están alineados dentro de esta categoría">
                                            gap {cat.gap >= 0 ? '+' : ''}{cat.gap.toFixed(1)}
                                        </span>
                                    )}
                                    <span className="text-[10px] text-surface-500">({formatCurrency(cat.totalAmount)})</span>
                                </div>
                            </div>
                        ))}
                        {bestCategories.length === 0 && (
                            <p className="text-xs text-surface-500 italic py-4 text-center">Sin datos suficientes.</p>
                        )}
                    </div>
                </div>
            </div>

            {/* Worst Categories */}
            <div className="bg-surface-900/60 border border-rose-500/10 p-6 rounded-2xl flex flex-col justify-between shadow-xl relative overflow-hidden">
                <div>
                    <h4 className="text-xs font-bold text-rose-400 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                        <Frown size={14} /> Fugas de Felicidad Financiera
                    </h4>
                    <div className="space-y-1.5">
                        {worstCategories.map(cat => (
                            <div key={cat.name} className="flex justify-between items-center text-xs bg-surface-950/40 p-2 rounded-lg border border-white/5">
                                <span className="font-semibold text-white truncate max-w-[60%] uppercase">{cat.name}</span>
                                <div className="flex items-center gap-1.5">
                                    <span className="font-mono text-rose-400 font-bold" title="Felicidad ponderada por monto">★ {cat.avgWeighted.toFixed(1)}</span>
                                    {Math.abs(cat.gap) >= 0.5 && (
                                        <span className="text-[10px] text-amber-400 font-mono" title="Diferencia con el promedio simple: la plata y el disfrute no están alineados dentro de esta categoría">
                                            gap {cat.gap >= 0 ? '+' : ''}{cat.gap.toFixed(1)}
                                        </span>
                                    )}
                                    <span className="text-[10px] text-surface-500">({formatCurrency(cat.totalAmount)})</span>
                                </div>
                            </div>
                        ))}
                        {worstCategories.length === 0 && (
                            <p className="text-xs text-surface-500 italic py-4 text-center">Sin datos suficientes.</p>
                        )}
                    </div>
                </div>
            </div>
        </div>

        {/* Interactive Happiness Chart Block */}
        <div className="bg-surface-900/60 border border-white/10 rounded-2xl p-6 shadow-xl flex flex-col">
            <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-4 border-b border-white/10 pb-4 mb-4">
                <div>
                    <h3 className="text-xl font-bold text-white">
                        {chartView === 'individual' && "Precio vs Felicidad (Gastos Individuales)"}
                        {chartView === 'bar' && `Rendimiento del Dinero por ${chartGroup === 'category' ? 'Categoría' : 'Etiqueta (Tag)'}`}
                        {chartView === 'bubble' && `Portafolio de Felicidad por ${chartGroup === 'category' ? 'Categoría' : 'Etiqueta (Tag)'}`}
                    </h3>
                    <p className="text-xs text-surface-400 mt-1">
                        {chartView === 'individual' && "Visualiza cada gasto para ver si el precio se alinea con la felicidad generada."}
                        {chartView === 'bar' && "Cuánto rinde tu dinero: felicidad neta (sobre el neutro 5) del dólar promedio, ponderando cada dólar igual. Un gasto chico no puede dar vuelta el ranking. La etiqueta muestra cuánto te cuesta un punto en una transacción típica."}
                        {chartView === 'bubble' && "Eje Y = ticket promedio (log), invariante si repetís más veces. Tamaño = nº de transacciones, color = felicidad por dólar. Abajo-derecha conviene agrandar, arriba-izquierda achicar."}
                    </p>
                </div>
                
                {/* Controles del gráfico */}
                <div className="flex flex-wrap items-center gap-3">
                    {/* Selector de Vista Principal */}
                    <div className="flex bg-surface-950 p-1 rounded-xl border border-white/5 text-xs">
                        <button
                            onClick={() => setChartView('individual')}
                            className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${chartView === 'individual' ? 'bg-primary-600 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
                        >
                            Gastos (Scatter)
                        </button>
                        <button
                            onClick={() => setChartView('bar')}
                            className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${chartView === 'bar' ? 'bg-primary-600 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
                        >
                            Distribución (Barras)
                        </button>
                        <button
                            onClick={() => setChartView('bubble')}
                            className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${chartView === 'bubble' ? 'bg-primary-600 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
                            title="Monto (Eje X) vs Felicidad (Eje Y). Tamaño = Transacciones"
                        >
                            Portafolio (Burbujas)
                        </button>
                    </div>

                    {/* Selector de Agrupamiento (solo para barras y burbujas) */}
                    {chartView !== 'individual' && (
                        <div className="flex bg-surface-950 p-1 rounded-xl border border-white/5 text-xs">
                            <button
                                onClick={() => setChartGroup('category')}
                                className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${chartGroup === 'category' ? 'bg-blue-600 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
                            >
                                Categorías
                            </button>
                            <button
                                onClick={() => setChartGroup('tag')}
                                className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${chartGroup === 'tag' ? 'bg-blue-600 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
                            >
                                Tags
                            </button>
                        </div>
                    )}

                    {/* Métrica de las barras */}
                    {chartView === 'bar' && (
                        <div className="flex bg-surface-950 p-1 rounded-xl border border-white/5 text-xs">
                            <button
                                onClick={() => setBarMetric('net')}
                                className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${barMetric === 'net' ? 'bg-emerald-600 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
                                title="Felicidad neta del dólar promedio: (ponderada − 5). Más alto es mejor y puede ser negativo, así que marca las categorías a evitar."
                            >
                                Neto
                            </button>
                            <button
                                onClick={() => setBarMetric('cost')}
                                className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${barMetric === 'cost' ? 'bg-violet-600 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
                                title="Promedio de (monto / felicidad), sin restar el neutro. Más bajo es mejor. Nunca es negativo: un gasto que te restó se ve solo como caro. Las barras rojas marcan los grupos que son neto negativo."
                            >
                                $/pt bruto
                            </button>
                        </div>
                    )}

                    {/* Ajuste por confiabilidad */}
                    {chartView === 'bar' && (
                        <button
                            onClick={() => setUseShrink(v => !v)}
                            className={`px-3 py-1.5 rounded-lg font-semibold border text-xs transition-all ${useShrink ? 'bg-sky-500/20 border-sky-500/40 text-sky-300' : 'bg-surface-950 border-white/5 text-surface-400 hover:text-white'}`}
                            title="Empirical Bayes: acerca a la media global los grupos con poca evidencia, según cuánto difieren los grupos entre sí frente al ruido de cada uno. Apagalo para ver los números crudos."
                        >
                            {useShrink ? 'Con ajuste' : 'Sin ajuste'}
                        </button>
                    )}

                    {/* Escala del eje de monto (no aplica a barras, cuyo eje X es la métrica) */}
                    {chartView !== 'bar' && (
                        <div className="flex bg-surface-950 p-1 rounded-xl border border-white/5 text-xs">
                            <button
                                onClick={() => setLogScale(false)}
                                className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${!logScale ? 'bg-surface-700 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
                                title="Escala lineal. En el scatter podés arrastrar el slider derecho para entrar a la franja de gastos chicos."
                            >
                                Lineal
                            </button>
                            <button
                                onClick={() => setLogScale(true)}
                                className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${logScale ? 'bg-surface-700 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
                                title="Escala logarítmica: abre la zona de gastos chicos, donde vive ~90% de tus transacciones."
                            >
                                Log
                            </button>
                        </div>
                    )}

                    {/* Filtros de alcance */}
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                        <button
                            onClick={() => setExcludeFijos(v => !v)}
                            className={`px-3 py-1.5 rounded-lg font-semibold border transition-all ${excludeFijos ? 'bg-amber-500/20 border-amber-500/40 text-amber-300' : 'bg-surface-950 border-white/5 text-surface-400 hover:text-white'}`}
                            title="Los gastos fijos no son reasignables: pesan en el presupuesto pero no son una decisión de gastar más o menos."
                        >
                            Excluir fijos
                        </button>
                        {(['all', 'Deseo', 'Necesidad'] as PriorityFilter[]).map(pf => (
                            <button
                                key={pf}
                                onClick={() => setPriorityFilter(pf)}
                                className={`px-3 py-1.5 rounded-lg font-semibold border transition-all ${priorityFilter === pf ? 'bg-blue-500/20 border-blue-500/40 text-blue-300' : 'bg-surface-950 border-white/5 text-surface-400 hover:text-white'}`}
                            >
                                {pf === 'all' ? 'Todo' : pf === 'Deseo' ? 'Solo deseos' : 'Solo necesidades'}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Canvas del Gráfico */}
            <div className="h-[600px] w-full relative flex items-center justify-center">
                {chartView === 'individual' && (
                    <ReactECharts option={scatterOptions} style={{ height: '100%', width: '100%' }} />
                )}
                {chartView === 'bar' && barOptions && (
                    <ReactECharts
                        option={barOptions.option}
                        style={{ height: '100%', width: '100%' }}
                        onEvents={{
                            'click': (params: any) => {
                                if (params.data && params.data.txs) {
                                    const sortedTxs = [...params.data.txs].sort((a, b) => b.felicidad - a.felicidad);
                                    openLocalModal(
                                        `${chartGroup === 'category' ? 'Categoría' : 'Etiqueta'}: ${params.data.name}`,
                                        `Transacciones del grupo ordenadas por nivel de felicidad de mayor a menor.`,
                                        sortedTxs
                                    );
                                }
                            }
                        }}
                    />
                )}
                {chartView === 'bubble' && bubbleOptions && (
                    <ReactECharts 
                        option={bubbleOptions} 
                        style={{ height: '100%', width: '100%' }}
                        onEvents={{
                            'click': (params: any) => {
                                if (params.data && params.data[4]) {
                                    const sortedTxs = [...params.data[4]].sort((a, b) => b.felicidad - a.felicidad);
                                    openLocalModal(
                                        `${chartGroup === 'category' ? 'Categoría' : 'Etiqueta'}: ${params.data[3]}`,
                                        `Transacciones asociadas ordenadas por nivel de felicidad.`,
                                        sortedTxs
                                    );
                                }
                            }
                        }}
                    />
                )}
            </div>

            {/* Diagnóstico del shrinkage: sin esto no hay forma de saber si el ajuste
                está haciendo algo, porque una corrección del 1-5% es invisible. */}
            {chartView === 'bar' && barOptions && useShrink && (
                <div className="mt-3 pt-3 border-t border-white/5 text-[11px] text-surface-500 flex flex-wrap items-center gap-x-4 gap-y-1">
                    {barOptions.diag.degenerate ? (
                        <span className="text-amber-400">
                            ⚠ Ajuste inactivo — el ruido dentro de los grupos se come la varianza entre ellos (τ² ≤ 0). Se muestran los valores crudos.
                        </span>
                    ) : (
                        <>
                            <span>
                                Varianza real entre grupos <span className="font-mono text-surface-400">τ² = {barOptions.diag.tau2.toFixed(3)}</span>
                            </span>
                            <span>
                                Encogido <span className="font-mono text-surface-400">{barOptions.diag.minB.toFixed(0)}%–{barOptions.diag.maxB.toFixed(0)}%</span> según el grupo
                            </span>
                            <span className="flex items-center gap-1.5">
                                <span className="inline-block w-[2px] h-3 bg-white/55" /> valor sin ajustar
                            </span>
                            {barOptions.diag.maxB < 8 && (
                                <span className="text-surface-600">
                                    (los grupos difieren mucho más que su ruido: casi no hace falta ajustar)
                                </span>
                            )}
                        </>
                    )}
                </div>
            )}
        </div>

        {/* Happiness Distribution */}
        <div className="bg-surface-900/80 border border-white/10 rounded-2xl p-6 shadow-xl">
            <div className="mb-6 flex items-center justify-between border-b border-white/10 pb-4">
               <h3 className="text-xl font-bold text-white">Distribución de Gastos por Felicidad</h3>
               <div className="group relative cursor-help">
                  <AlertCircle size={16} className="text-surface-500 hover:text-white transition-colors" />
                  <div className="absolute right-0 top-full mt-2 w-64 bg-surface-800 border border-white/10 rounded-xl p-4 text-xs text-surface-300 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity shadow-2xl z-20">
                     <strong className="text-white block mb-1 text-sm">Felicidad Absoluta</strong>
                     Medida sin tomar en cuenta el precio.<br/><br/>
                     <span className="text-emerald-400 font-bold">8-9:</span> Agrega gran valor a tu vida.<br/>
                     <span className="text-emerald-500 font-bold">6-7:</span> Agrega valor real a tu vida.<br/>
                     <span className="text-surface-400 font-bold">5:</span> Funcional, neutral (ej. fijos).<br/>
                     <span className="text-rose-400 font-bold">1-4:</span> Insatisfacción o arrepentimiento.
                  </div>
               </div>
            </div>
            <div className="space-y-6">
                {/* Render ratings from 9 to 1 */}
                {[9, 8, 7, 6, 5, 4, 3, 2, 1].map(level => {
                    const stat = happinessStats.dist[level as keyof typeof happinessStats.dist];
                    const info = getHappinessInfo(level);
                    const percentage = happinessStats.totalRatedAmount > 0 ? (stat.amount / happinessStats.totalRatedAmount) * 100 : 0;
                    
                    return (
                        <div 
                            key={level} 
                            className="flex flex-col gap-2 relative cursor-pointer group hover:bg-surface-800/50 p-3 -mx-3 rounded-xl transition-colors"
                            onClick={() => openLocalModal(`Gastos: ${info.label}`, `Transacciones con nivel de felicidad ${level}.`, transactions.filter(t => t.MONTO < 0 && t.felicidad === level).sort((a,b) => a.MONTO - b.MONTO))}
                        >
                            <div className="flex justify-between items-end">
                                <div className="flex items-center gap-3">
                                    <div className={`p-2 rounded-xl ${info.bg} ${info.border} border shadow-lg`}>
                                        {info.icon}
                                    </div>
                                    <div>
                                        <p className={`font-bold ${info.color}`}>{info.label}</p>
                                        <p className="text-xs text-surface-400">{stat.count} transacciones</p>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <p className="font-bold text-white text-lg">{formatCurrency(stat.amount)}</p>
                                    <p className="text-xs text-surface-400">{percentage.toFixed(1)}%</p>
                                </div>
                            </div>
                            <div className="w-full h-2 bg-surface-950 rounded-full overflow-hidden border border-white/5 relative">
                                <div 
                                    className={`absolute left-0 top-0 h-full rounded-full transition-all duration-1000 ${info.bg.replace('/20', '')}`}
                                    style={{ width: `${percentage}%` }}
                                />
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
             {/* Top Regrets */}
             <div className="bg-surface-900/60 border border-rose-500/20 rounded-2xl p-6 shadow-xl">
                <h3 className="text-lg font-bold text-rose-400 mb-4 flex items-center gap-2"><Frown size={20}/> Mayor Insatisfacción</h3>
                <p className="text-sm text-surface-400 mb-4">
                    Los gastos de nivel 1-4
                </p>
                <div className="space-y-2">
                    {transactions
                        .filter(t => t.MONTO < 0 && t.felicidad >= 1 && t.felicidad <= 4)
                        .sort((a, b) => a.MONTO - b.MONTO) // ascending (most negative first)
                        .slice(0, 5)
                        .map(tx => (
                            <div key={tx.id} className="flex justify-between items-center p-2.5 px-3 bg-surface-950/50 hover:bg-surface-800/50 rounded-xl border border-white/5 transition-all text-xs">
                                <div className="flex items-center gap-2 min-w-0">
                                    <span className="px-1.5 py-0.5 bg-rose-500/15 text-rose-400 rounded font-semibold shrink-0">N{tx.felicidad}</span>
                                    <span className="font-semibold text-white truncate uppercase" title={tx.nombre_limpio || tx.DESCRIPCION}>
                                        {tx.nombre_limpio || tx.DESCRIPCION}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2.5 shrink-0 ml-2">
                                    <span className="text-[10px] text-surface-500">{new Date(tx.FECHA).toLocaleDateString('es-CO')}</span>
                                    <span className="font-mono font-bold text-rose-400">{formatCurrency(tx.MONTO)}</span>
                                </div>
                            </div>
                        ))}
                    {transactions.filter(t => t.MONTO < 0 && t.felicidad >= 1 && t.felicidad <= 4).length === 0 && (
                        <p className="text-surface-500 italic text-center py-4 text-xs">No hay gastos en esta categoría.</p>
                    )}
                </div>
             </div>

             {/* Top Joys */}
             <div className="bg-surface-900/60 border border-emerald-500/20 rounded-2xl p-6 shadow-xl">
                <h3 className="text-lg font-bold text-emerald-400 mb-4 flex items-center gap-2"><Heart size={20}/> Mayor Valor Agregado</h3>
                <p className="text-sm text-surface-400 mb-4">
                    Tus gastos de nivel 8 y 9
                </p>
                <div className="space-y-2">
                    {transactions
                        .filter(t => t.MONTO < 0 && t.felicidad >= 8 && t.felicidad <= 9)
                        .sort((a, b) => a.MONTO - b.MONTO)
                        .slice(0, 5)
                        .map(tx => (
                            <div key={tx.id} className="flex justify-between items-center p-2.5 px-3 bg-surface-950/50 hover:bg-surface-800/50 rounded-xl border border-white/5 transition-all text-xs">
                                <div className="flex items-center gap-2 min-w-0">
                                    <span className="px-1.5 py-0.5 bg-emerald-500/15 text-emerald-400 rounded font-semibold shrink-0">N{tx.felicidad}</span>
                                    <span className="font-semibold text-white truncate uppercase" title={tx.nombre_limpio || tx.DESCRIPCION}>
                                        {tx.nombre_limpio || tx.DESCRIPCION}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2.5 shrink-0 ml-2">
                                     <span className="text-[10px] text-surface-500">{new Date(tx.FECHA).toLocaleDateString('es-CO')}</span>
                                     <span className="font-mono font-bold text-emerald-400">{formatCurrency(tx.MONTO)}</span>
                                </div>
                            </div>
                        ))}
                    {transactions.filter(t => t.MONTO < 0 && t.felicidad >= 8 && t.felicidad <= 9).length === 0 && (
                        <p className="text-surface-500 italic text-center py-4 text-xs">No hay gastos en esta categoría.</p>
                    )}
                </div>
             </div>
        </div>
    </div>
  );
}
