import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

interface ExplorerChartProps {
  data: {
    actual: { date: string; actual: number }[];
    reference: { date: string; value: number }[];
    difference?: { date: string; diff: number }[];
  };
  loading: boolean;
}

const ExplorerChart: React.FC<ExplorerChartProps> = ({ data, loading }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current);
    }

    const { actual, reference } = data;

    // Combine dates from both sources to ensure axis covers everything
    const allDates = new Set([
        ...actual.map(d => d.date),
        ...reference.map(d => d.date)
    ]);
    const dates = Array.from(allDates).sort(); // Renamed sortedDates to dates

    // Map data to the unified timeline
    // We need      // --- Data Preparation with Forward Fill ---
      const actualMap = new Map(data.actual.map(i => [i.date, i.actual]));
      const refMap = new Map(data.reference.map(i => [i.date, i.value]));
      // Difference map might be sparse or full? Should be full if backend forward filled, but let's be safe
      const diffMap = new Map((data.difference || []).map(i => [i.date, i.diff]));

      let lastActual = 0;
      const actualValues = dates.map(d => {
        if (actualMap.has(d)) {
            lastActual = actualMap.get(d)!;
        }
        return lastActual;
      });

      const referenceValues = dates.map(d => refMap.get(d) || 0);

      // We should also forward fill difference if we want consistency, or just map it?
      // Backend already calculated it based on FF actuals, so just mapping should be enough.
      // But let's check safety.
      const differenceValues = dates.map(d => diffMap.get(d) || 0);

      const options: echarts.EChartsOption = { // Renamed option to options
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1e293b',
        borderColor: '#334155',
        textStyle: { color: '#f8fafc' },
        formatter: (params: any) => {
           let date = '';
           let actual = '';
           let ref = '';
           let diff = ''; // Added diff for difference series
           if (Array.isArray(params)) {
               date = params[0].axisValue;
               params.forEach(p => {
                   const val = (p.value !== undefined && p.value !== null) ? Number(p.value).toFixed(2) : 'N/A';
                   if (p.seriesName === 'Real (Transacciones)') actual = `Real: ${val}`;
                   if (p.seriesName === 'Objetivo / Referencia') ref = `Ref: ${val}`;
                   if (p.seriesName === 'Diferencia') diff = `Diff: ${val}`; // Added difference tooltip line
               });
           }
           return `<b>${date}</b><br/>${actual}<br/>${ref}<br/>${diff}`; // Updated return string
        }
      },
      legend: {
        data: ['Real (Transacciones)', 'Objetivo / Referencia', 'Diferencia'], // Added Diferencia to legend
        textStyle: { color: '#94a3b8' },
        bottom: 40 
      },
      grid: {
        top: 20,
        left: 20,
        right: 20,
        bottom: 80, // Space for slider
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: dates, // Used dates here
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8' }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8' }
      },
      series: [
        {
          name: 'Real (Transacciones)',
          type: 'line',
          data: actualValues,
          smooth: true,
          showSymbol: false,
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(99, 102, 241, 0.5)' }, // Indigo 500
              { offset: 1, color: 'rgba(99, 102, 241, 0.0)' }
            ])
          },
          lineStyle: {
            color: '#6366f1',
            width: 3
          }
        },
        {
          name: 'Objetivo / Referencia',
          type: 'line',
          data: referenceValues,
          showSymbol: false,
          smooth: true,
          lineStyle: {
            color: '#10b981',
            width: 3,
            type: 'dashed',
             shadowColor: 'rgba(16, 185, 129, 0.5)',
             shadowBlur: 10
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(16, 185, 129, 0.3)' },
                { offset: 1, color: 'rgba(16, 185, 129, 0.0)' }
            ])
          }
        },
        {
          name: 'Diferencia',
          type: 'line',
          data: differenceValues,
          showSymbol: false,
          smooth: true,
          lineStyle: {
            color: '#f59e0b', // Amber 500
            width: 2,
            type: 'dotted'
          }
        }
      ],
      dataZoom: [
        {
          type: 'inside',
          start: 0,
          end: 100
        },
        {
          type: 'slider',
          start: 0,
          end: 100,
          bottom: 10,
          height: 20,
          handleSize: '80%',
          handleStyle: {
            color: '#64748b',
            shadowBlur: 3,
            shadowColor: 'rgba(0, 0, 0, 0.6)',
            shadowOffsetX: 2,
            shadowOffsetY: 2
          },
          textStyle: {
            color: '#94a3b8'
          },
          borderColor: '#334155'
        }
      ]
    };

    chartInstance.current.setOption(options);

    const handleResize = () => {
      chartInstance.current?.resize();
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chartInstance.current?.dispose();
      chartInstance.current = null;
    };
  }, [data]);

    // Handle Resize separately to avoid disposing if just resizing
    useEffect(() => {
        if(chartInstance.current) {
            chartInstance.current.resize();
        }
    });


  return (
    <div className="relative w-full h-full min-h-[400px]">
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface-950/50 z-10 backdrop-blur-sm">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
        </div>
      )}
      {!loading && data.actual.length === 0 && data.reference.length === 0 && (
         <div className="absolute inset-0 flex items-center justify-center text-slate-500">
             Sin datos para mostrar
         </div>
      )}
      <div ref={chartRef} className="w-full h-full" />
    </div>
  );
};

export default ExplorerChart;
