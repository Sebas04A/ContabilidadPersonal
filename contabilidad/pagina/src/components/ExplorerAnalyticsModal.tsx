import { useState, useMemo, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import {
  X, BarChart3, PieChart, TrendingUp, ArrowUpRight, ArrowDownRight,
  Layers, Tag, Store, Scale, Heart, AlertTriangle, Sparkles, Flame,
  CreditCard, ThumbsUp, ThumbsDown, HelpCircle
} from 'lucide-react';
import { Transaction, FundListItem } from '../services/api';
import { money } from '../utils/format';
import { TOOLTIP } from '../utils/chartTheme';

export interface ExplorerAnalyticsContentProps {
  transactions: Transaction[];
  funds?: FundListItem[];
  onOpenTransactionDetails?: (tx: Transaction) => void;
}

export function ExplorerAnalyticsContent({
  transactions,
  onOpenTransactionDetails,
}: ExplorerAnalyticsContentProps) {
  const [activeTab, setActiveTab] = useState<'categories' | 'happiness' | 'needs_wants' | 'timeline'>('categories');
  const [tagCountMode, setTagCountMode] = useState<'proportional' | 'full'>('proportional');

  // 1. General Financial & Happiness Metrics
  const metrics = useMemo(() => {
    let totalIncome = 0;
    let totalExpense = 0;
    let incomeCount = 0;
    let expenseCount = 0;
    let maxExpense = 0;

    let needsAmount = 0;
    let wantsAmount = 0;
    let unratedPriorityAmount = 0;
    let needsCount = 0;
    let wantsCount = 0;
    let unratedPriorityCount = 0;

    let reimbursableAmount = 0;

    // Happiness stats
    let ratedHappinessAmount = 0;
    let weightedHappinessSum = 0;
    let simpleHappinessSum = 0;
    let ratedHappinessCount = 0;
    let highHappinessAmount = 0; // 7-9
    let highHappinessCount = 0;
    let lowHappinessAmount = 0; // 1-4
    let lowHappinessCount = 0;
    let neutralHappinessAmount = 0; // 5-6
    let unratedHappinessAmount = 0;
    let unratedHappinessCount = 0;

    transactions.forEach(t => {
      if (t.MONTO > 0) {
        totalIncome += t.MONTO;
        incomeCount++;
      } else if (t.MONTO < 0) {
        const amt = Math.abs(t.MONTO);
        totalExpense += amt;
        expenseCount++;
        if (amt > maxExpense) maxExpense = amt;

        // Needs / Wants
        if (t.prioridad === 'Necesidad') {
          needsAmount += amt;
          needsCount++;
        } else if (t.prioridad === 'Deseo') {
          wantsAmount += amt;
          wantsCount++;
        } else {
          unratedPriorityAmount += amt;
          unratedPriorityCount++;
        }

        // Reimbursable
        if (t.es_reembolsable) {
          reimbursableAmount += amt;
        }

        // Happiness
        if (typeof t.felicidad === 'number' && t.felicidad >= 1 && t.felicidad <= 9) {
          ratedHappinessAmount += amt;
          weightedHappinessSum += t.felicidad * amt;
          simpleHappinessSum += t.felicidad;
          ratedHappinessCount++;

          if (t.felicidad >= 7) {
            highHappinessAmount += amt;
            highHappinessCount++;
          } else if (t.felicidad <= 4) {
            lowHappinessAmount += amt;
            lowHappinessCount++;
          } else {
            neutralHappinessAmount += amt;
          }
        } else {
          unratedHappinessAmount += amt;
          unratedHappinessCount++;
        }
      }
    });

    const net = totalIncome - totalExpense;
    const avgExpense = expenseCount > 0 ? totalExpense / expenseCount : 0;
    const weightedAvgHappiness = ratedHappinessAmount > 0 ? weightedHappinessSum / ratedHappinessAmount : 0;
    const simpleAvgHappiness = ratedHappinessCount > 0 ? simpleHappinessSum / ratedHappinessCount : 0;
    const classifiedPriorityRatio = totalExpense > 0 ? ((needsAmount + wantsAmount) / totalExpense) * 100 : 0;
    const ratedHappinessRatio = totalExpense > 0 ? (ratedHappinessAmount / totalExpense) * 100 : 0;

    return {
      totalIncome,
      totalExpense,
      net,
      incomeCount,
      expenseCount,
      avgExpense,
      maxExpense,
      needsAmount,
      wantsAmount,
      unratedPriorityAmount,
      needsCount,
      wantsCount,
      unratedPriorityCount,
      reimbursableAmount,
      classifiedPriorityRatio,
      weightedAvgHappiness,
      simpleAvgHappiness,
      ratedHappinessAmount,
      ratedHappinessCount,
      ratedHappinessRatio,
      highHappinessAmount,
      highHappinessCount,
      lowHappinessAmount,
      lowHappinessCount,
      neutralHappinessAmount,
      unratedHappinessAmount,
      unratedHappinessCount,
      totalCount: transactions.length,
    };
  }, [transactions]);

  // -------------------------------------------------------------
  // CHARTS: CATEGORIES & MERCHANTS
  // -------------------------------------------------------------
  const topCategoriesBarOption = useMemo(() => {
    const expenses = transactions.filter(t => t.MONTO < 0);
    const catMap: Record<string, { name: string; value: number; count: number }> = {};

    expenses.forEach(t => {
      const key = (!t.categoria || t.categoria === '---') ? 'Sin Categoría' : t.categoria;
      if (!catMap[key]) catMap[key] = { name: key, value: 0, count: 0 };
      catMap[key].value += Math.abs(t.MONTO);
      catMap[key].count += 1;
    });

    const sorted = Object.values(catMap).sort((a, b) => b.value - a.value).slice(0, 10);
    sorted.reverse();

    if (sorted.length === 0) return null;

    return {
      tooltip: {
        ...TOOLTIP,
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const d = params[0].data;
          return `<strong class="text-white">${d.name}</strong><br/>Total: <span class="text-indigo-400 font-bold">${money(d.value)}</span><br/>Transacciones: ${d.count}`;
        }
      },
      grid: { left: '3%', right: '5%', bottom: '3%', top: '4%', containLabel: true },
      xAxis: {
        type: 'value',
        splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        axisLabel: { color: '#94a3b8', formatter: (v: number) => v >= 1000000 ? `${(v / 1000000).toFixed(1)}M` : v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v }
      },
      yAxis: {
        type: 'category',
        data: sorted.map(d => d.name.length > 20 ? d.name.substring(0, 18) + '...' : d.name),
        axisLabel: { color: '#e2e8f0', fontWeight: 'bold' },
        axisTick: { show: false },
        axisLine: { show: false }
      },
      series: [{
        name: 'Gasto por Categoría',
        type: 'bar',
        data: sorted.map(d => ({
          value: d.value,
          name: d.name,
          count: d.count,
          itemStyle: { color: '#6366f1', borderRadius: [0, 6, 6, 0] }
        }))
      }]
    };
  }, [transactions]);

  const categoriesPieOption = useMemo(() => {
    const expenses = transactions.filter(t => t.MONTO < 0);
    const catMap: Record<string, number> = {};

    expenses.forEach(t => {
      const key = (!t.categoria || t.categoria === '---') ? 'Sin Categoría' : t.categoria;
      catMap[key] = (catMap[key] || 0) + Math.abs(t.MONTO);
    });

    const data = Object.entries(catMap)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);

    if (data.length === 0) return null;

    const colors = ['#6366f1', '#ec4899', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#14b8a6', '#f43f5e', '#06b6d4', '#84cc16'];

    return {
      tooltip: {
        ...TOOLTIP,
        trigger: 'item',
        formatter: '{b}: <strong class="text-white">${c}</strong> ({d}%)'
      },
      legend: {
        orient: 'vertical',
        right: '2%',
        top: 'middle',
        textStyle: { color: '#cbd5e1', fontSize: 11 },
        type: 'scroll'
      },
      series: [{
        name: 'Categorías',
        type: 'pie',
        radius: ['45%', '75%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#0b132b',
          borderWidth: 2
        },
        label: { show: false },
        data: data.map((d, i) => ({
          ...d,
          itemStyle: { color: colors[i % colors.length] }
        }))
      }]
    };
  }, [transactions]);

  const topMerchantsOption = useMemo(() => {
    const expenses = transactions.filter(t => t.MONTO < 0);
    const conceptMap: Record<string, { name: string; value: number; count: number }> = {};

    expenses.forEach(t => {
      const name = t.nombre_limpio || t.DESCRIPCION || 'Sin concepto';
      const amt = Math.abs(t.MONTO);
      if (!conceptMap[name]) conceptMap[name] = { name, value: 0, count: 0 };
      conceptMap[name].value += amt;
      conceptMap[name].count += 1;
    });

    const sorted = Object.values(conceptMap).sort((a, b) => b.value - a.value).slice(0, 10);
    sorted.reverse();

    if (sorted.length === 0) return null;

    return {
      tooltip: {
        ...TOOLTIP,
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const d = params[0].data;
          return `<strong class="text-white">${d.name}</strong><br/>Total: <span class="text-rose-400 font-bold">${money(d.value)}</span><br/>Transacciones: ${d.count}`;
        }
      },
      grid: { left: '3%', right: '5%', bottom: '3%', top: '4%', containLabel: true },
      xAxis: {
        type: 'value',
        splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        axisLabel: { color: '#94a3b8', formatter: (v: number) => v >= 1000000 ? `${(v / 1000000).toFixed(1)}M` : v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v }
      },
      yAxis: {
        type: 'category',
        data: sorted.map(d => d.name.length > 20 ? d.name.substring(0, 18) + '...' : d.name),
        axisLabel: { color: '#e2e8f0', fontWeight: 'bold' },
        axisTick: { show: false },
        axisLine: { show: false }
      },
      series: [{
        name: 'Gasto Total',
        type: 'bar',
        data: sorted.map(d => ({
          value: d.value,
          name: d.name,
          count: d.count,
          itemStyle: { color: '#ec4899', borderRadius: [0, 6, 6, 0] }
        }))
      }]
    };
  }, [transactions]);

  const tagsBarOption = useMemo(() => {
    const expenses = transactions.filter(t => t.MONTO < 0);
    const tagMap: Record<string, { name: string; value: number; count: number }> = {};

    expenses.forEach(t => {
      const amt = Math.abs(t.MONTO);
      if (!t.tags || t.tags.trim() === '' || t.tags === '---') {
        const key = 'Sin Etiqueta';
        if (!tagMap[key]) tagMap[key] = { name: key, value: 0, count: 0 };
        tagMap[key].value += amt;
        tagMap[key].count += 1;
      } else {
        const rawTags = t.tags.split(',').map(tg => tg.trim()).filter(Boolean);
        const factor = tagCountMode === 'proportional' ? (rawTags.length > 0 ? 1 / rawTags.length : 1) : 1;
        rawTags.forEach(tg => {
          if (!tagMap[tg]) tagMap[tg] = { name: `#${tg}`, value: 0, count: 0 };
          tagMap[tg].value += amt * factor;
          tagMap[tg].count += 1;
        });
      }
    });

    const sorted = Object.values(tagMap).sort((a, b) => b.value - a.value).slice(0, 10);
    sorted.reverse();

    if (sorted.length === 0) return null;

    return {
      tooltip: {
        ...TOOLTIP,
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const d = params[0].data;
          return `<strong class="text-white">${d.name}</strong><br/>Total: <span class="text-violet-400 font-bold">${money(Math.round(d.value))}</span><br/>Apariciones: ${d.count}`;
        }
      },
      grid: { left: '3%', right: '5%', bottom: '3%', top: '4%', containLabel: true },
      xAxis: {
        type: 'value',
        splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        axisLabel: { color: '#94a3b8', formatter: (v: number) => v >= 1000000 ? `${(v / 1000000).toFixed(1)}M` : v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v }
      },
      yAxis: {
        type: 'category',
        data: sorted.map(d => d.name),
        axisLabel: { color: '#e2e8f0', fontWeight: 'bold' },
        axisTick: { show: false },
        axisLine: { show: false }
      },
      series: [{
        name: 'Gasto por Tag',
        type: 'bar',
        data: sorted.map(d => ({
          value: Math.round(d.value),
          name: d.name,
          count: d.count,
          itemStyle: { color: '#8b5cf6', borderRadius: [0, 6, 6, 0] }
        }))
      }]
    };
  }, [transactions, tagCountMode]);

  // -------------------------------------------------------------
  // CHARTS: HAPPINESS & EMOTIONAL ROI
  // -------------------------------------------------------------
  const happinessDistributionOption = useMemo(() => {
    const expenses = transactions.filter(t => t.MONTO < 0 && typeof t.felicidad === 'number' && t.felicidad >= 1 && t.felicidad <= 9);
    const dist: Record<number, { level: number; amount: number; count: number }> = {};

    for (let i = 1; i <= 9; i++) {
      dist[i] = { level: i, amount: 0, count: 0 };
    }

    expenses.forEach(t => {
      const lvl = t.felicidad!;
      dist[lvl].amount += Math.abs(t.MONTO);
      dist[lvl].count += 1;
    });

    const colorMap: Record<number, string> = {
      1: '#e11d48',
      2: '#f43f5e',
      3: '#fb7185',
      4: '#f97316',
      5: '#64748b',
      6: '#06b6d4',
      7: '#10b981',
      8: '#34d399',
      9: '#10b981'
    };

    const data = Object.values(dist);

    return {
      tooltip: {
        ...TOOLTIP,
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const d = params[0].data;
          const label = d.level >= 8 ? 'Gran Satisfacción' : d.level >= 6 ? 'Buena Satisfacción' : d.level === 5 ? 'Neutro' : d.level >= 3 ? 'Bajo Valor / Decepción' : 'Arrepentimiento / Quema de dinero';
          return `<strong class="text-white">Nivel ${d.level} — ${label}</strong><br/>Total gastado: <span class="text-pink-400 font-bold">${money(d.amount)}</span><br/>Transacciones: ${d.count}`;
        }
      },
      grid: { left: '3%', right: '4%', bottom: '5%', top: '6%', containLabel: true },
      xAxis: {
        type: 'category',
        data: ['1 (Malo)', '2', '3', '4', '5 (Neutro)', '6', '7', '8', '9 (Excelente)'],
        axisLabel: { color: '#cbd5e1', fontSize: 11, fontWeight: 'bold' },
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
      },
      yAxis: {
        type: 'value',
        splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        axisLabel: { color: '#94a3b8', formatter: (v: number) => v >= 1000000 ? `${(v / 1000000).toFixed(1)}M` : v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v }
      },
      series: [{
        name: 'Monto Gastado',
        type: 'bar',
        data: data.map(d => ({
          value: d.amount,
          level: d.level,
          amount: d.amount,
          count: d.count,
          itemStyle: {
            color: colorMap[d.level],
            borderRadius: [6, 6, 0, 0]
          }
        }))
      }]
    };
  }, [transactions]);

  // Top High Happiness Investments vs Regret Expenses
  const bestInvestments = useMemo(() => {
    return transactions
      .filter(t => t.MONTO < 0 && typeof t.felicidad === 'number' && t.felicidad >= 7)
      .sort((a, b) => Math.abs(b.MONTO) - Math.abs(a.MONTO))
      .slice(0, 5);
  }, [transactions]);

  const regretExpenses = useMemo(() => {
    return transactions
      .filter(t => t.MONTO < 0 && typeof t.felicidad === 'number' && t.felicidad <= 4)
      .sort((a, b) => Math.abs(b.MONTO) - Math.abs(a.MONTO))
      .slice(0, 5);
  }, [transactions]);

  // -------------------------------------------------------------
  // CHARTS: NEEDS VS WANTS
  // -------------------------------------------------------------
  const needsWantsDonutOption = useMemo(() => {
    if (metrics.totalExpense === 0) return null;

    const data = [
      { name: '🟢 Necesidades', value: metrics.needsAmount, itemStyle: { color: '#10b981' } },
      { name: '🟡 Deseos', value: metrics.wantsAmount, itemStyle: { color: '#f59e0b' } },
      { name: '⚪ Sin clasificar', value: metrics.unratedPriorityAmount, itemStyle: { color: '#64748b' } },
    ].filter(d => d.value > 0);

    return {
      tooltip: {
        ...TOOLTIP,
        trigger: 'item',
        formatter: '{b}: <strong class="text-white">${c}</strong> ({d}%)'
      },
      legend: {
        bottom: '0%',
        left: 'center',
        textStyle: { color: '#cbd5e1', fontSize: 12 }
      },
      series: [{
        name: 'Prioridad',
        type: 'pie',
        radius: ['50%', '75%'],
        center: ['50%', '42%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#0b132b',
          borderWidth: 2
        },
        label: {
          show: true,
          position: 'inside',
          formatter: '{d}%',
          color: '#ffffff',
          fontWeight: 'bold',
          fontSize: 12
        },
        data
      }]
    };
  }, [metrics]);

  const topNeeds = useMemo(() => {
    return transactions
      .filter(t => t.MONTO < 0 && t.prioridad === 'Necesidad')
      .sort((a, b) => Math.abs(b.MONTO) - Math.abs(a.MONTO))
      .slice(0, 5);
  }, [transactions]);

  const topWants = useMemo(() => {
    return transactions
      .filter(t => t.MONTO < 0 && t.prioridad === 'Deseo')
      .sort((a, b) => Math.abs(b.MONTO) - Math.abs(a.MONTO))
      .slice(0, 5);
  }, [transactions]);

  // -------------------------------------------------------------
  // CHARTS: TIMELINE & ACCOUNTS
  // -------------------------------------------------------------
  const timelineOption = useMemo(() => {
    if (transactions.length === 0) return null;

    const dayMap: Record<string, { date: string; income: number; expense: number }> = {};

    transactions.forEach(t => {
      const dateKey = (t.FECHA || '').substring(0, 10);
      if (!dateKey) return;
      if (!dayMap[dateKey]) dayMap[dateKey] = { date: dateKey, income: 0, expense: 0 };
      if (t.MONTO > 0) dayMap[dateKey].income += t.MONTO;
      else if (t.MONTO < 0) dayMap[dateKey].expense += Math.abs(t.MONTO);
    });

    const dates = Object.keys(dayMap).sort();
    if (dates.length === 0) return null;

    const incomeSeries = dates.map(d => dayMap[d].income);
    const expenseSeries = dates.map(d => dayMap[d].expense);

    return {
      tooltip: {
        ...TOOLTIP,
        trigger: 'axis',
        axisPointer: { type: 'cross', label: { backgroundColor: '#334155' } },
        formatter: (params: any) => {
          let res = `<div class="font-bold text-white mb-1">${params[0]?.axisValue}</div>`;
          params.forEach((p: any) => {
            const color = p.seriesName === 'Ingresos' ? '#34d399' : '#f87171';
            res += `<div class="flex items-center justify-between gap-4 text-xs">
              <span style="color:${color}">${p.seriesName}:</span>
              <strong class="font-mono">${money(p.value)}</strong>
            </div>`;
          });
          return res;
        }
      },
      legend: {
        data: ['Ingresos', 'Gastos'],
        textStyle: { color: '#cbd5e1' },
        top: 0,
        right: '4%'
      },
      grid: { left: '3%', right: '4%', bottom: '5%', top: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: dates,
        axisLabel: { color: '#94a3b8', fontSize: 10 },
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        axisLabel: {
          color: '#94a3b8',
          formatter: (v: number) => v >= 1000000 ? `${(v / 1000000).toFixed(1)}M` : v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v
        }
      },
      series: [
        {
          name: 'Ingresos',
          type: 'line',
          smooth: true,
          showSymbol: dates.length < 30,
          itemStyle: { color: '#10b981' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [{ offset: 0, color: 'rgba(16, 185, 129, 0.35)' }, { offset: 1, color: 'rgba(16, 185, 129, 0.0)' }]
            }
          },
          data: incomeSeries
        },
        {
          name: 'Gastos',
          type: 'line',
          smooth: true,
          showSymbol: dates.length < 30,
          itemStyle: { color: '#f43f5e' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [{ offset: 0, color: 'rgba(244, 63, 94, 0.35)' }, { offset: 1, color: 'rgba(244, 63, 94, 0.0)' }]
            }
          },
          data: expenseSeries
        }
      ]
    };
  }, [transactions]);

  const sourceBreakdownOption = useMemo(() => {
    const expenses = transactions.filter(t => t.MONTO < 0);
    const sourceMap: Record<string, number> = {};

    expenses.forEach(t => {
      const src = (t.TIPO || 'OTRO').toUpperCase();
      sourceMap[src] = (sourceMap[src] || 0) + Math.abs(t.MONTO);
    });

    const data = Object.entries(sourceMap).map(([name, value]) => ({ name, value }));
    if (data.length === 0) return null;

    return {
      tooltip: {
        ...TOOLTIP,
        trigger: 'item',
        formatter: '{b}: <strong class="text-white">${c}</strong> ({d}%)'
      },
      legend: {
        bottom: '0%',
        left: 'center',
        textStyle: { color: '#cbd5e1', fontSize: 11 }
      },
      series: [{
        name: 'Fuente',
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['50%', '42%'],
        itemStyle: {
          borderRadius: 8,
          borderColor: '#0b132b',
          borderWidth: 2
        },
        data: data.map(d => ({
          ...d,
          itemStyle: { color: d.name === 'BANCA' ? '#38bdf8' : d.name === 'TARJETA' ? '#a855f7' : '#64748b' }
        }))
      }]
    };
  }, [transactions]);

  return (
    <div className="space-y-6">
      
      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        {/* Total Expense */}
        <div className="p-4 rounded-2xl bg-surface-950/70 border border-white/5 space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-surface-400 flex items-center gap-1.5">
            <ArrowDownRight size={14} className="text-rose-400" /> Total Gastos
          </span>
          <p className="text-lg md:text-2xl font-bold font-mono text-rose-400 truncate">
            {money(metrics.totalExpense)}
          </p>
          <p className="text-[11px] text-surface-500">{metrics.expenseCount} transacciones de salida</p>
        </div>

        {/* Total Income */}
        <div className="p-4 rounded-2xl bg-surface-950/70 border border-white/5 space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-surface-400 flex items-center gap-1.5">
            <ArrowUpRight size={14} className="text-emerald-400" /> Total Ingresos
          </span>
          <p className="text-lg md:text-2xl font-bold font-mono text-emerald-400 truncate">
            {money(metrics.totalIncome)}
          </p>
          <p className="text-[11px] text-surface-500">{metrics.incomeCount} transacciones de entrada</p>
        </div>

        {/* Weighted Happiness */}
        <div className="p-4 rounded-2xl bg-surface-950/70 border border-white/5 space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-surface-400 flex items-center gap-1.5">
            <Heart size={14} className="text-pink-400" /> Felicidad Ponderada
          </span>
          <div className="flex items-baseline gap-2">
            <p className={`text-lg md:text-2xl font-bold font-mono truncate ${
              metrics.weightedAvgHappiness >= 7 ? 'text-emerald-400' :
              metrics.weightedAvgHappiness >= 5 ? 'text-amber-300' : 'text-rose-400'
            }`}>
              {metrics.weightedAvgHappiness > 0 ? `${metrics.weightedAvgHappiness.toFixed(2)} / 9` : 'Sin datos'}
            </p>
          </div>
          <p className="text-[11px] text-surface-500">
            {metrics.ratedHappinessCount} calificados ({metrics.ratedHappinessRatio.toFixed(0)}% del gasto)
          </p>
        </div>

        {/* Net Flow / Classification */}
        <div className="p-4 rounded-2xl bg-surface-950/70 border border-white/5 space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-surface-400 flex items-center gap-1.5">
            <Scale size={14} className="text-amber-400" /> Nec vs Deseo
          </span>
          <p className="text-lg md:text-2xl font-bold text-amber-300 truncate">
            {metrics.classifiedPriorityRatio.toFixed(0)}% evaluado
          </p>
          <p className="text-[11px] text-surface-500">
            Nec: {money(metrics.needsAmount)} · Des: {money(metrics.wantsAmount)}
          </p>
        </div>
      </div>

      {/* Navigation Tabs Bar */}
      <div className="flex items-center gap-2 p-1.5 bg-surface-950/70 border border-white/10 rounded-2xl overflow-x-auto custom-scrollbar">
        <button
          onClick={() => setActiveTab('categories')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 ${
            activeTab === 'categories'
              ? 'bg-primary-600 text-white shadow-lg shadow-primary-600/30'
              : 'text-surface-400 hover:text-white hover:bg-white/5'
          }`}
        >
          <Layers size={15} /> Categorías & Comercios
        </button>

        <button
          onClick={() => setActiveTab('happiness')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 ${
            activeTab === 'happiness'
              ? 'bg-pink-600 text-white shadow-lg shadow-pink-600/30'
              : 'text-surface-400 hover:text-white hover:bg-white/5'
          }`}
        >
          <Heart size={15} /> Felicidad & ROI Emocional
        </button>

        <button
          onClick={() => setActiveTab('needs_wants')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 ${
            activeTab === 'needs_wants'
              ? 'bg-amber-600 text-white shadow-lg shadow-amber-600/30'
              : 'text-surface-400 hover:text-white hover:bg-white/5'
          }`}
        >
          <Flame size={15} /> Necesidades vs Deseos
        </button>

        <button
          onClick={() => setActiveTab('timeline')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 ${
            activeTab === 'timeline'
              ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-600/30'
              : 'text-surface-400 hover:text-white hover:bg-white/5'
          }`}
        >
          <TrendingUp size={15} /> Evolución & Cuentas
        </button>
      </div>

      {/* TAB 1: CATEGORIES & MERCHANTS */}
      {activeTab === 'categories' && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top 10 Categories Bar */}
            <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-5 shadow-xl">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2 mb-3">
                <Layers size={16} className="text-indigo-400" /> Top Categorías por Gasto
              </h3>
              <div className="h-[360px] w-full">
                {topCategoriesBarOption ? (
                  <ReactECharts option={topCategoriesBarOption} style={{ height: '100%', width: '100%' }} />
                ) : (
                  <div className="h-full flex items-center justify-center text-surface-500 text-xs italic">
                    No hay suficientes transacciones de gasto para generar el ranking de categorías.
                  </div>
                )}
              </div>
            </div>

            {/* Categories Distribution Donut */}
            <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-5 shadow-xl">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2 mb-3">
                <PieChart size={16} className="text-primary-400" /> Distribución Porcentual
              </h3>
              <div className="h-[360px] w-full">
                {categoriesPieOption ? (
                  <ReactECharts option={categoriesPieOption} style={{ height: '100%', width: '100%' }} />
                ) : (
                  <div className="h-full flex items-center justify-center text-surface-500 text-xs italic">
                    No hay categorías para mostrar.
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top 10 Merchants / Concepts */}
            <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-5 shadow-xl">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2 mb-3">
                <Store size={16} className="text-pink-400" /> Top 10 Comercios / Conceptos
              </h3>
              <div className="h-[360px] w-full">
                {topMerchantsOption ? (
                  <ReactECharts option={topMerchantsOption} style={{ height: '100%', width: '100%' }} />
                ) : (
                  <div className="h-full flex items-center justify-center text-surface-500 text-xs italic">
                    No hay gastos para mostrar el ranking de comercios.
                  </div>
                )}
              </div>
            </div>

            {/* Top 10 Tags */}
            <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-5 shadow-xl">
              <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Tag size={16} className="text-violet-400" /> Top 10 Etiquetas (Tags)
                </h3>
                <div className="flex items-center gap-1 bg-surface-900 p-1 rounded-xl border border-white/5">
                  <button
                    onClick={() => setTagCountMode('proportional')}
                    className={`px-2 py-0.5 rounded-lg text-[10px] font-bold uppercase transition-all ${
                      tagCountMode === 'proportional' ? 'bg-primary-600 text-white shadow-sm' : 'text-surface-400 hover:text-white'
                    }`}
                    title="Dividir monto si hay múltiples tags (1x)"
                  >
                    Dividir (1x)
                  </button>
                  <button
                    onClick={() => setTagCountMode('full')}
                    className={`px-2 py-0.5 rounded-lg text-[10px] font-bold uppercase transition-all ${
                      tagCountMode === 'full' ? 'bg-primary-600 text-white shadow-sm' : 'text-surface-400 hover:text-white'
                    }`}
                    title="Monto completo en cada tag"
                  >
                    Completo
                  </button>
                </div>
              </div>
              <div className="h-[360px] w-full">
                {tagsBarOption ? (
                  <ReactECharts option={tagsBarOption} style={{ height: '100%', width: '100%' }} />
                ) : (
                  <div className="h-full flex items-center justify-center text-surface-500 text-xs italic">
                    No hay etiquetas para mostrar.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: HAPPINESS & EMOTIONAL ROI */}
      {activeTab === 'happiness' && (
        <div className="space-y-6 animate-in fade-in duration-200">
          {/* Top Happiness Overview Card */}
          <div className="bg-gradient-to-r from-pink-950/40 via-surface-950/60 to-purple-950/40 border border-pink-500/20 rounded-3xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Heart className="text-pink-400" size={22} />
                  <span>Análisis de Retorno Emocional (Escala 1 a 9)</span>
                </h3>
                <p className="text-xs text-surface-300 mt-0.5">
                  Mide el disfrute y valor real obtenido por cada peso gastado en las transacciones filtradas.
                </p>
              </div>
              <div className="flex items-center gap-4 text-xs font-semibold">
                <span className="flex items-center gap-1.5 text-emerald-400">
                  <ThumbsUp size={15} /> Alta satisfacción (7-9): <strong>{money(metrics.highHappinessAmount)}</strong>
                </span>
                <span className="flex items-center gap-1.5 text-rose-400">
                  <ThumbsDown size={15} /> Bajo valor / Arrepentimiento (1-4): <strong>{money(metrics.lowHappinessAmount)}</strong>
                </span>
              </div>
            </div>

            {/* Happiness Bar Distribution (Levels 1 to 9) */}
            <div className="bg-surface-950/70 border border-white/5 rounded-2xl p-5">
              <h4 className="text-xs font-bold uppercase tracking-wider text-surface-300 mb-3">
                Distribución de Gasto por Nivel de Felicidad
              </h4>
              <div className="h-[280px] w-full">
                <ReactECharts option={happinessDistributionOption} style={{ height: '100%', width: '100%' }} />
              </div>
            </div>
          </div>

          {/* Best vs Worst Investments List */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top Satisfying Purchases */}
            <div className="bg-surface-950/60 border border-emerald-500/20 rounded-2xl p-5 space-y-3 shadow-lg">
              <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2 text-emerald-400">
                <Sparkles size={16} /> Mayores Compras con Alta Felicidad (7-9)
              </h4>
              <div className="space-y-2">
                {bestInvestments.length === 0 ? (
                  <p className="text-xs text-surface-500 italic py-4 text-center">No hay gastos registrados con felicidad alta en este filtro.</p>
                ) : (
                  bestInvestments.map(t => (
                    <div
                      key={t.id}
                      onClick={() => onOpenTransactionDetails?.(t)}
                      className="flex items-center justify-between p-3 rounded-xl bg-surface-900/60 border border-white/5 hover:border-emerald-500/30 transition-all cursor-pointer"
                    >
                      <div className="truncate mr-2">
                        <p className="text-xs font-bold text-white truncate">{t.nombre_limpio || t.DESCRIPCION}</p>
                        <p className="text-[10px] text-surface-400">{t.FECHA?.substring(0, 10)} · {t.categoria || 'Sin categoría'}</p>
                      </div>
                      <div className="text-right shrink-0 flex items-center gap-3">
                        <span className="text-xs font-mono font-bold text-emerald-400">{money(Math.abs(t.MONTO))}</span>
                        <span className="px-2 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-300 text-xs font-bold border border-emerald-500/30">
                          ⭐ {t.felicidad}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Top Regret / Low Value Purchases */}
            <div className="bg-surface-950/60 border border-rose-500/20 rounded-2xl p-5 space-y-3 shadow-lg">
              <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2 text-rose-400">
                <AlertTriangle size={16} /> Gastos que Menos Rindieron (Felicidad 1-4)
              </h4>
              <div className="space-y-2">
                {regretExpenses.length === 0 ? (
                  <p className="text-xs text-surface-500 italic py-4 text-center">¡Excelente! No hay gastos de bajo retorno emocional en este filtro.</p>
                ) : (
                  regretExpenses.map(t => (
                    <div
                      key={t.id}
                      onClick={() => onOpenTransactionDetails?.(t)}
                      className="flex items-center justify-between p-3 rounded-xl bg-surface-900/60 border border-white/5 hover:border-rose-500/30 transition-all cursor-pointer"
                    >
                      <div className="truncate mr-2">
                        <p className="text-xs font-bold text-white truncate">{t.nombre_limpio || t.DESCRIPCION}</p>
                        <p className="text-[10px] text-surface-400">{t.FECHA?.substring(0, 10)} · {t.categoria || 'Sin categoría'}</p>
                      </div>
                      <div className="text-right shrink-0 flex items-center gap-3">
                        <span className="text-xs font-mono font-bold text-rose-400">{money(Math.abs(t.MONTO))}</span>
                        <span className="px-2 py-0.5 rounded-lg bg-rose-500/20 text-rose-300 text-xs font-bold border border-rose-500/30">
                          ⚠️ {t.felicidad}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: NEEDS VS WANTS */}
      {activeTab === 'needs_wants' && (
        <div className="space-y-6 animate-in fade-in duration-200">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Necesidades Card */}
            <div className="p-5 rounded-2xl bg-surface-950/60 border border-emerald-500/30 space-y-2 shadow-lg">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                  <Flame size={16} /> Necesidades
                </span>
                <span className="text-xs font-bold text-emerald-300">
                  {metrics.totalExpense > 0 ? ((metrics.needsAmount / metrics.totalExpense) * 100).toFixed(1) : 0}%
                </span>
              </div>
              <p className="text-2xl font-bold font-mono text-emerald-400">{money(metrics.needsAmount)}</p>
              <p className="text-xs text-surface-400">{metrics.needsCount} transacciones de subsistencia básica</p>
            </div>

            {/* Deseos Card */}
            <div className="p-5 rounded-2xl bg-surface-950/60 border border-amber-500/30 space-y-2 shadow-lg">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
                  <Sparkles size={16} /> Deseos (Estilo de Vida)
                </span>
                <span className="text-xs font-bold text-amber-300">
                  {metrics.totalExpense > 0 ? ((metrics.wantsAmount / metrics.totalExpense) * 100).toFixed(1) : 0}%
                </span>
              </div>
              <p className="text-2xl font-bold font-mono text-amber-400">{money(metrics.wantsAmount)}</p>
              <p className="text-xs text-surface-400">{metrics.wantsCount} transacciones de disfrute y extras</p>
            </div>

            {/* Sin Clasificar Card */}
            <div className="p-5 rounded-2xl bg-surface-950/60 border border-white/10 space-y-2 shadow-lg">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-surface-400 flex items-center gap-1.5">
                  <HelpCircle size={16} /> Sin Clasificar
                </span>
                <span className="text-xs font-bold text-surface-400">
                  {metrics.totalExpense > 0 ? ((metrics.unratedPriorityAmount / metrics.totalExpense) * 100).toFixed(1) : 0}%
                </span>
              </div>
              <p className="text-2xl font-bold font-mono text-surface-300">{money(metrics.unratedPriorityAmount)}</p>
              <p className="text-xs text-surface-500">{metrics.unratedPriorityCount} transacciones pendientes</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Donut Chart */}
            <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-5 shadow-xl flex flex-col">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2 mb-3">
                <Scale size={16} className="text-amber-400" /> Distribución
              </h3>
              <div className="h-[320px] w-full">
                {needsWantsDonutOption ? (
                  <ReactECharts option={needsWantsDonutOption} style={{ height: '100%', width: '100%' }} />
                ) : (
                  <div className="h-full flex items-center justify-center text-surface-500 text-xs italic">
                    No hay gastos para clasificar.
                  </div>
                )}
              </div>
            </div>

            {/* Top Needs List */}
            <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-5 shadow-xl space-y-3">
              <h3 className="text-sm font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-2">
                <Flame size={16} /> Principales Necesidades
              </h3>
              <div className="space-y-2">
                {topNeeds.length === 0 ? (
                  <p className="text-xs text-surface-500 italic py-4 text-center">No hay necesidades registradas en este filtro.</p>
                ) : (
                  topNeeds.map(t => (
                    <div
                      key={t.id}
                      onClick={() => onOpenTransactionDetails?.(t)}
                      className="flex items-center justify-between p-2.5 rounded-xl bg-surface-900/60 border border-white/5 hover:border-emerald-500/30 transition-all cursor-pointer"
                    >
                      <div className="truncate mr-2">
                        <p className="text-xs font-bold text-white truncate">{t.nombre_limpio || t.DESCRIPCION}</p>
                        <p className="text-[10px] text-surface-400">{t.FECHA?.substring(0, 10)} · {t.categoria || 'Sin categoría'}</p>
                      </div>
                      <span className="text-xs font-mono font-bold text-emerald-400 shrink-0">{money(Math.abs(t.MONTO))}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Top Wants List */}
            <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-5 shadow-xl space-y-3">
              <h3 className="text-sm font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
                <Sparkles size={16} /> Principales Deseos
              </h3>
              <div className="space-y-2">
                {topWants.length === 0 ? (
                  <p className="text-xs text-surface-500 italic py-4 text-center">No hay deseos registrados en este filtro.</p>
                ) : (
                  topWants.map(t => (
                    <div
                      key={t.id}
                      onClick={() => onOpenTransactionDetails?.(t)}
                      className="flex items-center justify-between p-2.5 rounded-xl bg-surface-900/60 border border-white/5 hover:border-amber-500/30 transition-all cursor-pointer"
                    >
                      <div className="truncate mr-2">
                        <p className="text-xs font-bold text-white truncate">{t.nombre_limpio || t.DESCRIPCION}</p>
                        <p className="text-[10px] text-surface-400">{t.FECHA?.substring(0, 10)} · {t.categoria || 'Sin categoría'}</p>
                      </div>
                      <span className="text-xs font-mono font-bold text-amber-400 shrink-0">{money(Math.abs(t.MONTO))}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: TIMELINE & ACCOUNTS */}
      {activeTab === 'timeline' && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Timeline Evolution Chart (2 cols) */}
            <div className="lg:col-span-2 bg-surface-950/60 border border-white/5 rounded-2xl p-5 shadow-xl">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2 mb-3">
                <TrendingUp size={16} className="text-emerald-400" /> Evolución de Ingresos y Gastos en el Tiempo
              </h3>
              <div className="h-[360px] w-full">
                {timelineOption ? (
                  <ReactECharts option={timelineOption} style={{ height: '100%', width: '100%' }} />
                ) : (
                  <div className="h-full flex items-center justify-center text-surface-500 text-xs italic">
                    No hay suficientes datos temporales para graficar la evolución.
                  </div>
                )}
              </div>
            </div>

            {/* Source / Account Breakdown (1 col) */}
            <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-5 shadow-xl">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2 mb-3">
                <CreditCard size={16} className="text-sky-400" /> Distribución por Medio (Cuenta)
              </h3>
              <div className="h-[360px] w-full">
                {sourceBreakdownOption ? (
                  <ReactECharts option={sourceBreakdownOption} style={{ height: '100%', width: '100%' }} />
                ) : (
                  <div className="h-full flex items-center justify-center text-surface-500 text-xs italic">
                    No hay información de fuentes disponible.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

export interface ExplorerAnalyticsModalProps {
  isOpen: boolean;
  onClose: () => void;
  transactions: Transaction[];
  funds?: FundListItem[];
  onOpenTransactionDetails?: (tx: Transaction) => void;
}

export function ExplorerAnalyticsModal({
  isOpen,
  onClose,
  transactions,
  funds,
  onOpenTransactionDetails,
}: ExplorerAnalyticsModalProps) {
  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-3 md:p-6 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-surface-900 border border-white/10 rounded-3xl w-full max-w-6xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        
        {/* Modal Header */}
        <div className="p-5 md:px-8 border-b border-white/10 flex justify-between items-center bg-surface-950/70 backdrop-blur-xl">
          <div className="space-y-1">
            <h2 className="text-xl md:text-2xl font-bold text-white flex items-center gap-2.5">
              <BarChart3 className="text-primary-400" size={26} />
              <span>Analíticas y Resumen Financiero</span>
            </h2>
            <p className="text-xs md:text-sm text-surface-400">
              Métricas, categorías, felicidad y flujo basadas en las <strong className="text-primary-300">{transactions.length} transacciones</strong> filtradas.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="p-2 text-surface-400 hover:text-white transition-colors bg-surface-800/80 hover:bg-surface-700 rounded-xl"
              title="Cerrar modal (Esc)"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-5 md:p-8 overflow-y-auto custom-scrollbar flex-1">
          <ExplorerAnalyticsContent
            transactions={transactions}
            funds={funds}
            onOpenTransactionDetails={(tx) => {
              onClose();
              onOpenTransactionDetails?.(tx);
            }}
          />
        </div>

        {/* Modal Footer */}
        <div className="p-4 px-8 border-t border-white/10 bg-surface-950/70 flex justify-between items-center text-xs text-surface-400">
          <span>Consejo: las analíticas se recalculan en vivo según los filtros que apliques en el explorador.</span>
          <button
            onClick={onClose}
            className="px-5 py-2 bg-surface-800 hover:bg-surface-700 text-white font-bold rounded-xl transition-all border border-white/10"
          >
            Cerrar
          </button>
        </div>

      </div>
    </div>
  );
}

