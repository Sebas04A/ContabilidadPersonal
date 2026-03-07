import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';

export interface Period {
  start_date: string;
  end_date: string;
  total_to_pay: number;
  consumption: number;
  period_name: string;
  min_payment: number;
  status: string;
  max_transaction_date: string;
}

export interface CardData {
  chart_data: Array<{ date: string; tarjeta?: number; acumulado?: number }>;
  periods: Period[];
  payments: Array<{ date: string; amount: number }>;
}

interface CardChartProps {
    data?: CardData;
    isLoading: boolean;
}

/**
 * Renders a rectangular bar from start_date to end_date.
 */
const renderPeriodBar = (_: echarts.CustomSeriesRenderItemParams, api: echarts.CustomSeriesRenderItemAPI) => {
    const start = api.value(0) as number;
    const end = api.value(1) as number;
    const val = api.value(2) as number;

    if (isNaN(start) || isNaN(end)) return undefined;

    const c1 = api.coord([start, 0]);
    const c2 = api.coord([end, val]);

    return {
        type: 'rect',
        shape: {
            x: c1[0],
            y: Math.min(c1[1], c2[1]),
            width: Math.max(c2[0] - c1[0], 2),
            height: Math.abs(c1[1] - c2[1])
        },
        style: {
            fill: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(34, 197, 94, 0.4)' }, // Emerald-500 @ 40%
                { offset: 1, color: 'rgba(34, 197, 94, 0.1)' }  // Emerald-500 @ 10%
            ]),
            stroke: '#10b981', // Emerald-500
            lineWidth: 1,
            shadowBlur: 10,
            shadowColor: 'rgba(16, 185, 129, 0.2)'
        }
    };
};

const CardChart: React.FC<CardChartProps> = ({ data, isLoading }) => {
  const option = useMemo(() => {
    if (!data) return {};

    // 1. Data for Green Bars (Periodos)
    const periodData = data.periods.map(p => [
        new Date(p.start_date).getTime(),
        new Date(p.end_date).getTime(),
        p.total_to_pay,
        p.consumption
    ]);

    // 2. Data for Red Points (Cortes)
    const cutoffData = data.periods.map(p => ({
        value: [p.max_transaction_date, p.total_to_pay],
        name: p.period_name
    }));

    // 3. Red Dashed Lines
    const cutoffLines = data.periods.map(p => ({
        xAxis: p.max_transaction_date,
        lineStyle: { color: '#fb7185', type: 'dashed', width: 1, opacity: 0.6 } // Rose-400
    }));

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', label: { backgroundColor: '#18181b' }, snap: true },
        backgroundColor: 'rgba(9, 9, 11, 0.95)', // Surface-950
        borderColor: '#27272a', // Surface-800
        textStyle: { color: '#fafafa', fontFamily: 'Outfit, sans-serif' },
        padding: [16, 20],
        extraCssText: 'backdrop-filter: blur(8px); box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1); border-radius: 12px;',
        formatter: (params: any) => {
            if (!Array.isArray(params) || params.length === 0) return '';
            
            const timestamp = params[0].axisValue;
            const dateObj = new Date(timestamp);
            
            // Header
            let content = `<div class="font-bold border-b border-white/10 mb-3 pb-2 text-sm text-center capitalize text-surface-200">
                ${dateObj.toLocaleDateString('es-ES', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
            </div>`;
            
            // 1. Manual Period Check (Always show relevant period info)
            const activePeriod = data.periods.find(p => {
                const s = new Date(p.start_date).getTime();
                const e = new Date(p.end_date).getTime();
                // Check if current timestamp is within period range (inclusive)
                return timestamp >= s && timestamp <= e;
            });

            if (activePeriod) {
                 content += `
                 <div class="flex items-center justify-between gap-6 mb-2 text-xs group">
                    <div class="flex items-center gap-2">
                        <div class="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"></div>
                        <span class="text-surface-400 font-medium group-hover:text-emerald-300 transition-colors">Periodo Actual</span>
                    </div>
                    <div class="text-right">
                        <div class="font-mono font-bold text-emerald-400">$${activePeriod.total_to_pay.toLocaleString('en-US', {minimumFractionDigits: 2})}</div>
                        <div class="text-[10px] text-surface-500 max-w-[100px] truncate">${activePeriod.period_name}</div>
                    </div>
                 </div>`;
            }

            // 2. Iterate Params for other series
            params.forEach((p: any) => {
                // Skip 'Periodos' from params since we handled it manually
                if (p.seriesName === 'Periodos') return;

                const val = Array.isArray(p.value) ? p.value[1] : p.value;
                if (val !== null && val !== undefined) {
                     let label = p.seriesName;
                     let valueColor = 'text-surface-100';
                     let iconShadow = '';
                     
                     // Custom styling based on series
                     if (p.seriesName === 'Evolución Tarjeta') {
                         valueColor = 'text-indigo-400';
                         iconShadow = 'shadow-[0_0_8px_rgba(99,102,241,0.5)]';
                     } else if (p.seriesName === 'Pagos') {
                         valueColor = 'text-amber-400';
                         iconShadow = 'shadow-[0_0_8px_rgba(245,158,11,0.5)]';
                     } else if (p.seriesName === 'Cortes') {
                         valueColor = 'text-rose-400';
                         iconShadow = 'shadow-[0_0_8px_rgba(251,113,133,0.5)]';
                         label = 'Corte de Tarjeta';
                     }

                     content += `
                     <div class="flex items-center justify-between gap-6 mb-2 text-xs last:mb-0">
                        <div class="flex items-center gap-2">
                           <div class="w-2 h-2 rounded-full ${iconShadow}" style="background-color:${p.color};"></div>
                           <span class="text-surface-400 font-medium">${label}</span>
                        </div>
                        <span class="font-mono font-bold ml-auto ${valueColor}">$${Number(val).toLocaleString('en-US', {minimumFractionDigits: 2})}</span>
                     </div>`;
                }
            });
            return content;
        }
      },
      legend: {
        data: ['Evolución Tarjeta', 'Pagos', 'Periodos', 'Cortes'],
        top: 0,
        textStyle: { color: '#a1a1aa', fontFamily: 'Outfit, sans-serif' },
        icon: 'circle',
        itemGap: 20
      },
      grid: { 
          left: '2%', 
          right: '3%', 
          bottom: '10%', 
          top: '10%',
          containLabel: true 
      },
      xAxis: { 
          type: 'time', 
          boundaryGap: false, 
          axisLabel: { color: '#71717a', fontFamily: 'Outfit, sans-serif' },
          axisLine: { lineStyle: { color: '#27272a' } },
          splitLine: { show: false }
      },
      yAxis: { 
          type: 'value', 
          axisLabel: { color: '#71717a', fontFamily: 'Outfit, sans-serif' }, 
          splitLine: { lineStyle: { color: '#27272a', type: 'dashed' } } 
      },
      dataZoom: [
          { type: 'inside' }, 
          { 
              type: 'slider', 
              bottom: 20, 
              borderColor: 'transparent',
              backgroundColor: '#18181b',
              handleStyle: { color: '#6366f1' },
              textStyle: { color: '#a1a1aa' },
              fillerColor: 'rgba(99, 102, 241, 0.1)'
          }
      ],
      series: [
        // 1. Periods (Green Rects)
        {
          name: 'Periodos',
          type: 'custom',
          renderItem: renderPeriodBar,
          data: periodData,
          encode: { x: [0, 1], y: 2 },
          z: 2
        },
        // 2. Cutoffs (Red Points)
        {
            name: 'Cortes',
            type: 'scatter',
            data: cutoffData,
            symbol: 'circle',
            symbolSize: 8,
            itemStyle: { 
                color: '#fb7185', // Rose-400
                shadowBlur: 10,
                shadowColor: 'rgba(251, 113, 133, 0.5)'
            }, 
            z: 5,
            markLine: {
                data: cutoffLines,
                symbol: ['none', 'none'],
                silent: true,
                label: { show: false }
            }
        },
        // 3. Card Evolution (Blue Line)
        {
          name: 'Evolución Tarjeta',
          type: 'line',
          data: data.chart_data.map(d => [d.date, d.tarjeta]),
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 3, color: '#6366f1' }, // Indigo-500
          areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: 'rgba(99, 102, 241, 0.3)' },
                  { offset: 1, color: 'rgba(99, 102, 241, 0.0)' }
              ])
          },
          z: 3
        },
        // 4. Payments (Orange Bars)
        {
          name: 'Pagos',
          type: 'bar',
          data: data.payments.map(p => [p.date, p.amount]),
          itemStyle: { color: '#f59e0b', borderRadius: [2, 2, 0, 0] }, // Amber-500
          barWidth: 6,
          z: 4
        }
      ],
      backgroundColor: 'transparent',
    };
  }, [data]);

  return (
    <div className="h-full w-full">
        {isLoading ? (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-surface-500">
                <div className="w-8 h-8 border-2 border-primary-500/30 border-t-primary-500 rounded-full animate-spin"></div>
                <span className="text-sm font-medium tracking-wide uppercase">Cargando datos...</span>
            </div>
        ) : (
            <ReactECharts 
                option={option} 
                style={{ height: '100%', width: '100%' }} 
                opts={{ renderer: 'canvas' }} 
                theme="dark" 
                notMerge={true}
                lazyUpdate={true}
            />
        )}
    </div>
  );
};

export default CardChart;
