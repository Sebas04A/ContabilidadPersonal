import React, { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';
import { X, Loader2, Users, TrendingUp, Activity, BarChart3 } from 'lucide-react';
import { useSupabaseDebts, useSupabasePayments } from '../hooks/useTransactions';

interface DebtsChartProps {
  onClose: () => void;
}

export function DebtsChart({ onClose }: DebtsChartProps) {
  const [viewMode, setViewMode] = useState<'debtor' | 'time' | 'daily'>('debtor');
  
  // Fetch ALL debts (no filters)
  const { data: allDebts, isLoading: isLoadingDebts } = useSupabaseDebts({});
  const { data: allPayments, isLoading: isLoadingPayments } = useSupabasePayments();

  const isLoading = isLoadingDebts || isLoadingPayments;

  // --- Option 1: By Debtor (Summary) ---
  const debtorOption = useMemo(() => {
    if (!allDebts || allDebts.length === 0) return {};

    // Group by Debtor
    const debtorStats = allDebts.reduce((acc, debt) => {
      const debtor = debt.DEUDOR_NOMBRE || 'Desconocido';
      if (!acc[debtor]) {
        acc[debtor] = { pending: 0, paid: 0 };
      }
      if (debt.PAGADA) {
        acc[debtor].paid += debt.MONTO;
      } else {
        acc[debtor].pending += debt.MONTO;
      }
      return acc;
    }, {} as Record<string, { pending: number; paid: number }>);

    const debtors = Object.keys(debtorStats).sort();
    const pendingData = debtors.map(d => debtorStats[d].pending);
    const paidData = debtors.map(d => debtorStats[d].paid);

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: 'rgba(9, 9, 11, 0.9)',
        borderColor: '#27272a',
        textStyle: { color: '#fafafa' },
        padding: [12, 16],
        formatter: (params: any) => {
           let tooltip = `<div style="font-weight:700; margin-bottom:8px; font-size:14px; border-bottom:1px solid #3f3f46; padding-bottom:4px;">${params[0].name}</div>`;
           params.forEach((p: any) => {
              const value = p.value as number;
              if (value > 0) {
                 tooltip += `<div style="display:flex; justify-content:space-between; width:160px; margin-top:4px;">
                   <span style="color:${p.color}; font-size:12px;">● ${p.seriesName}</span>
                   <span style="font-family:monospace; font-weight:600;">$${value.toLocaleString('en-US', {minimumFractionDigits: 2})}</span>
                 </div>`;
              }
           });
           return tooltip;
        }
      },
      legend: {
        data: ['Pendiente', 'Pagada'],
        top: 0,
        textStyle: { color: '#a1a1aa' },
        icon: 'circle'
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        top: '10%',
        containLabel: true
      },
      xAxis: {
        type: 'value',
        axisLabel: { color: '#71717a' },
        splitLine: { lineStyle: { color: '#27272a' } }
      },
      yAxis: {
        type: 'category',
        data: debtors,
        axisLabel: { color: '#cbd5e1', fontWeight: 600 },
        axisLine: { show: false },
        axisTick: { show: false }
      },
      series: [
        {
          name: 'Pendiente',
          type: 'bar',
          stack: 'total',
          label: { 
            show: true, 
            position: 'insideRight',
            formatter: (params: any) => params.value > 0 ? `$${params.value.toLocaleString('en-US', {maximumFractionDigits:0})}` : ''
          },
          emphasis: { focus: 'series' },
          data: pendingData,
          itemStyle: { color: '#fb7185', borderRadius: [0, 6, 6, 0] } // Rose-400
        },
        {
          name: 'Pagada',
          type: 'bar',
          stack: 'total',
          label: { 
             show: true, 
             position: 'insideRight',
             formatter: (params: any) => params.value > 0 ? `$${params.value.toLocaleString('en-US', {maximumFractionDigits:0})}` : '',
             color: '#064e3b'
          },
          emphasis: { focus: 'series' },
          data: paidData,
          itemStyle: { color: '#34d399', borderRadius: [0, 6, 6, 0] } // Emerald-400
        }
      ],
      backgroundColor: 'transparent',
      textStyle: { fontFamily: 'Outfit, sans-serif' }
    };
  }, [allDebts]);

  // --- Option 2: By Time (Monthly History) ---
  const timeOption = useMemo(() => {
    if (!allDebts || allDebts.length === 0) return {};

    const allDebtors = Array.from(new Set(allDebts.map(d => d.DEUDOR_NOMBRE || 'Desconocido'))).sort();
    const monthMap: Record<string, Record<string, number>> = {};
    
    allDebts.forEach(debt => {
      if (!debt.FECHA) return;
      // Extract YYYY-MM
      const month = debt.FECHA.substring(0, 7);
      const debtor = debt.DEUDOR_NOMBRE || 'Desconocido';
      
      if (!monthMap[month]) monthMap[month] = {};
      if (!monthMap[month][debtor]) monthMap[month][debtor] = 0;
      
      monthMap[month][debtor] += debt.MONTO;
    });

    const months = Object.keys(monthMap).sort();

    const series = allDebtors.map(debtor => {
      return {
        name: debtor,
        type: 'bar',
        stack: 'total',
        emphasis: { focus: 'series' },
        data: months.map(m => monthMap[m][debtor] || 0),
        itemStyle: { borderRadius: [0, 0, 0, 0] }
      };
    });

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: 'rgba(9, 9, 11, 0.9)',
        borderColor: '#27272a',
        textStyle: { color: '#fafafa' },
        formatter: (params: any) => {
          if (!params.length) return '';
          let tooltip = `<div style="font-weight:700; margin-bottom:8px; border-bottom:1px solid #3f3f46; padding-bottom:4px;">${params[0].axisValueLabel}</div>`;
          let total = 0;
          const activeParams = params.filter((p: any) => p.value > 0);
          
          activeParams.forEach((p: any) => {
             const value = p.value as number;
             total += value;
             tooltip += `<div style="display:flex; justify-content:space-between; width:180px; margin-top:2px;">
               <span style="color:${p.color}">● ${p.seriesName}</span>
               <span style="font-family:monospace;">$${value.toLocaleString('en-US', {minimumFractionDigits: 0})}</span>
             </div>`;
          });
          
          if (activeParams.length > 0) {
              tooltip += `<div style="border-top:1px solid #3f3f46; margin-top:6px; padding-top:4px; display:flex; justify-content:space-between; font-weight:700; color:#e4e4e7;">
                <span>Total</span>
                <span>$${total.toLocaleString('en-US', {minimumFractionDigits: 0})}</span>
              </div>`;
          }
          return tooltip;
        }
      },
      legend: {
        data: allDebtors,
        top: 0,
        type: 'scroll',
        textStyle: { color: '#a1a1aa' },
        icon: 'circle'
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '15%',
        top: '10%',
        containLabel: true
      },
      dataZoom: [
        {
          type: 'slider',
          show: true,
          xAxisIndex: [0],
          start: 0,
          end: 100,
          bottom: 10,
          borderColor: 'transparent',
          backgroundColor: '#18181b',
          brushSelect: false,
          handleStyle: { color: '#6366f1' },
          textStyle: { color: '#a1a1aa' },
          fillerColor: 'rgba(99, 102, 241, 0.2)'
        },
        { type: 'inside', xAxisIndex: [0], start: 0, end: 100 }
      ],
      xAxis: {
        type: 'category',
        data: months,
        axisLabel: { color: '#a1a1aa' },
        axisLine: { lineStyle: { color: '#3f3f46' } }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#71717a' },
        splitLine: { lineStyle: { color: '#27272a' } }
      },
      series: series,
      backgroundColor: 'transparent',
      textStyle: { fontFamily: 'Outfit, sans-serif' }
    };
  }, [allDebts]);

  // --- Option 3: Cumulative ---
  const cumulativeOption = useMemo(() => {
    if (!allDebts || allDebts.length === 0) return {};

    const dayMap: Record<string, { debt: number; payment: number; net: number }> = {};
    allDebts.forEach(debt => {
      if (!debt.FECHA) return;
      const date = new Date(debt.FECHA);
      if (isNaN(date.getTime())) return;
      const dayStr = date.toISOString().split('T')[0];
      if (!dayMap[dayStr]) dayMap[dayStr] = { debt: 0, payment: 0, net: 0 };
      dayMap[dayStr].debt += debt.MONTO;
      dayMap[dayStr].net += debt.MONTO;
    });

    if (allPayments) {
      allPayments.forEach(payment => {
        if (!payment.fecha_pago) return;
        const date = new Date(payment.fecha_pago);
        if (isNaN(date.getTime())) return;
        const dayStr = date.toISOString().split('T')[0];
        if (!dayMap[dayStr]) dayMap[dayStr] = { debt: 0, payment: 0, net: 0 };
        dayMap[dayStr].payment += payment.monto_total;
        dayMap[dayStr].net -= payment.monto_total;
      });
    }

    const days = Object.keys(dayMap).sort();
    let runningTotal = 0;
    const values: number[] = [];
    const metaData: { debt: number; payment: number; net: number }[] = [];

    for (const d of days) {
      runningTotal += dayMap[d].net;
      values.push(runningTotal);
      metaData.push(dayMap[d]);
    }

    return {
       tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(9, 9, 11, 0.9)',
        borderColor: '#27272a',
        textStyle: { color: '#fafafa' },
        formatter: (params: any) => {
           if (!params.length) return '';
           const p = params[0];
           const index = p.dataIndex;
           const meta = metaData[index];
           
           return `<div style="font-weight:700; margin-bottom:6px;">${p.name}</div>
                   <div style="display:flex; justify-content:space-between; width:220px; margin-bottom:6px; border-bottom:1px solid #3f3f46; padding-bottom:4px;">
                      <span style="color:${p.color}">● Acumulado</span>
                      <span style="font-family:monospace; font-weight:700;">$${(p.value as number).toLocaleString('en-US', {minimumFractionDigits: 2})}</span>
                   </div>
                   ${meta.debt > 0 ? 
                     `<div style="display:flex; justify-content:space-between; width:220px; font-size:12px; margin-bottom:2px;">
                        <span style="color:#fb7185;">+ Nueva Deuda</span>
                        <span style="font-family:monospace;">$${meta.debt.toLocaleString('en-US', {minimumFractionDigits: 2})}</span>
                      </div>` : ''}
                   ${meta.payment > 0 ? 
                     `<div style="display:flex; justify-content:space-between; width:220px; font-size:12px;">
                        <span style="color:#34d399;">- Pagos Realizados</span>
                        <span style="font-family:monospace;">$${meta.payment.toLocaleString('en-US', {minimumFractionDigits: 2})}</span>
                      </div>` : ''}
                   `;
        }
      },
      grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
      dataZoom: [
        {
          type: 'slider',
          show: true,
          xAxisIndex: [0],
          start: 0, end: 100, bottom: 10,
          borderColor: 'transparent',
          backgroundColor: '#18181b',
          handleStyle: { color: '#8b5cf6' },
          textStyle: { color: '#a1a1aa' },
          fillerColor: 'rgba(139, 92, 246, 0.2)'
        },
        { type: 'inside', xAxisIndex: [0], start: 0, end: 100 }
      ],
      xAxis: {
        type: 'category',
        data: days,
        axisLabel: { color: '#a1a1aa' },
        axisLine: { lineStyle: { color: '#3f3f46' } }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#71717a' },
        splitLine: { lineStyle: { color: '#27272a' } }
      },
      series: [
        {
          name: 'Deuda Neta Acumulada',
          type: 'line',
          smooth: true,
          showSymbol: false,
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(139, 92, 246, 0.4)' },
              { offset: 1, color: 'rgba(139, 92, 246, 0.0)' }
            ])
          },
          lineStyle: { color: '#8b5cf6', width: 3 },
          data: values
        }
      ],
      backgroundColor: 'transparent',
      textStyle: { fontFamily: 'Outfit, sans-serif' }
    };
  }, [allDebts, allPayments]);

  const getOption = () => {
    switch(viewMode) {
      case 'debtor': return debtorOption;
      case 'time': return timeOption;
      case 'daily': return cumulativeOption;
      default: return debtorOption;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-4 animate-in fade-in duration-300">
      <div className="bg-surface-950/90 w-full max-w-6xl h-[85vh] rounded-3xl border border-white/10 flex flex-col shadow-2xl overflow-hidden relative backdrop-blur-xl">
        
        {/* Background Gradients */}
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-primary-600/10 rounded-full blur-[100px] pointer-events-none -translate-y-1/2 translate-x-1/2"></div>
        <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-secondary-600/10 rounded-full blur-[100px] pointer-events-none translate-y-1/2 -translate-x-1/2"></div>

        {/* Header */}
        <div className="flex flex-col md:flex-row items-center justify-between p-6 border-b border-white/5 relative z-10 shrink-0 gap-4 bg-surface-900/40">
          <div className="flex items-center gap-4 w-full md:w-auto">
            <div className="p-2.5 bg-indigo-500/20 rounded-xl text-indigo-400">
                <BarChart3 size={24} />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white tracking-tight">Análisis Financiero</h2>
              <p className="text-surface-400 text-xs font-medium">Visualización de deudas y pagos</p>
            </div>
          </div>
            
          {/* View Toggles */}
          <div className="flex bg-surface-950/50 p-1.5 rounded-xl border border-white/5 shadow-inner">
            {[
                { id: 'debtor', label: 'Por Deudor', icon: Users },
                { id: 'time', label: 'Mensual', icon: TrendingUp },
                { id: 'daily', label: 'Acumulado', icon: Activity },
            ].map((mode) => (
                <button 
                  key={mode.id}
                  onClick={() => setViewMode(mode.id as any)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                    viewMode === mode.id 
                      ? 'bg-surface-800 text-white shadow-lg border border-white/5' 
                      : 'text-surface-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <mode.icon size={14} />
                  {mode.label}
                </button>
            ))}
          </div>

          <button 
            onClick={onClose}
            className="p-2 hover:bg-white/10 rounded-full text-surface-400 hover:text-white transition-colors absolute right-4 top-4 md:relative md:right-0 md:top-0"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 p-6 relative z-10 w-full overflow-hidden">
          {isLoading ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-surface-400">
              <Loader2 className="animate-spin text-primary-500" size={48} />
              <p className="text-sm font-medium tracking-wide uppercase">Cargando datos...</p>
            </div>
          ) : (
            <div className="w-full h-full bg-surface-900/20 rounded-2xl border border-white/5 p-4 backdrop-blur-sm shadow-inner relative">
               {allDebts && allDebts.length > 0 ? (
                 <ReactECharts 
                   option={getOption()} 
                   style={{ height: '100%', width: '100%' }} 
                   theme="dark"
                   notMerge={true}
                   lazyUpdate={true}
                 />
               ) : (
                 <div className="flex flex-col items-center justify-center h-full text-surface-500 gap-2">
                    <Activity size={32} className="opacity-20" />
                    <p>No hay datos disponibles para visualizar</p>
                 </div>
               )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
