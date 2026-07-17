import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

export interface MonthlyIssuePoint {
  month: string;           // 'YYYY-MM'
  total: number;           // transactions in the month
  sin_revisar: number;
  sin_categoria: number;
  sin_prioridad: number;
  sin_felicidad: number;
  sin_tags: number;
}

interface SeriesDef {
  key: keyof Omit<MonthlyIssuePoint, 'month' | 'total'>;
  name: string;
  color: string;
}

interface VerificationChartProps {
  data: MonthlyIssuePoint[];
  /** When set, only this issue series is shown (highlighted view). */
  activeIssue?: SeriesDef['key'] | null;
  selectedMonth?: string | null;
  onSelectMonth?: (month: string | null) => void;
  /** 'issues' = stacked problems per month; 'review' = review progress per month. */
  mode?: 'issues' | 'review';
  /** For review mode: show percentage or absolute counts. */
  reviewUnit?: 'pct' | 'count';
}

const SERIES: SeriesDef[] = [
  { key: 'sin_revisar', name: 'Sin revisar', color: '#ef4444' },     // red
  { key: 'sin_categoria', name: 'Sin categoría', color: '#f59e0b' }, // amber
  { key: 'sin_prioridad', name: 'Sin prioridad', color: '#10b981' }, // emerald
  { key: 'sin_felicidad', name: 'Sin felicidad', color: '#ec4899' }, // pink
  { key: 'sin_tags', name: 'Sin etiquetas', color: '#8b5cf6' },      // violet
];

export function VerificationChart({
  data, activeIssue, selectedMonth, onSelectMonth,
  mode = 'issues', reviewUnit = 'pct',
}: VerificationChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current);
    }

    const months = data.map(d => d.month);
    const dim = (month: string) => (selectedMonth && month !== selectedMonth ? 0.3 : 0.95);
    const isPct = mode === 'review' && reviewUnit === 'pct';

    // Build the series depending on the mode.
    let seriesDefs: SeriesDef[];
    let seriesData: Record<string, (d: MonthlyIssuePoint) => number>;

    if (mode === 'review') {
      seriesDefs = [
        { key: 'sin_revisar' as any, name: reviewUnit === 'pct' ? '% Revisado' : 'Revisados', color: '#10b981' },
        { key: 'sin_categoria' as any, name: reviewUnit === 'pct' ? '% Pendiente' : 'No revisados', color: '#ef4444' },
      ];
      seriesData = {
        [seriesDefs[0].name]: (d) => {
          const reviewed = d.total - d.sin_revisar;
          return isPct ? (d.total ? Math.round((reviewed / d.total) * 100) : 0) : reviewed;
        },
        [seriesDefs[1].name]: (d) => {
          return isPct ? (d.total ? Math.round((d.sin_revisar / d.total) * 100) : 0) : d.sin_revisar;
        },
      };
    } else {
      seriesDefs = activeIssue ? SERIES.filter(s => s.key === activeIssue) : SERIES;
      seriesData = {};
      for (const s of seriesDefs) seriesData[s.name] = (d) => d[s.key];
    }

    const suffix = isPct ? '%' : '';

    const options: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: '#0f172a',
        borderColor: '#334155',
        textStyle: { color: '#f8fafc' },
        valueFormatter: (v: any) => `${v}${suffix}`,
      },
      legend: {
        data: seriesDefs.map(s => s.name),
        textStyle: { color: '#94a3b8' },
        top: 0,
        icon: 'roundRect',
      },
      grid: { top: 40, left: 10, right: 16, bottom: 30, containLabel: true },
      xAxis: {
        type: 'category',
        data: months,
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: {
          color: '#94a3b8',
          formatter: (v: string) => {
            const [y, m] = v.split('-');
            return `${m}/${y.slice(2)}`;
          },
        },
      },
      yAxis: {
        type: 'value',
        max: isPct ? 100 : undefined,
        splitLine: { lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8', formatter: (v: number) => `${v}${suffix}` },
      },
      // Series-level itemStyle.color drives the legend swatch; per-datum
      // itemStyle only tweaks opacity so the color stays consistent.
      series: seriesDefs.map(s => ({
        name: s.name,
        type: 'bar',
        stack: 'stack',
        itemStyle: { color: s.color, borderRadius: 3 },
        data: data.map(d => ({
          value: seriesData[s.name](d),
          itemStyle: { opacity: dim(d.month) },
        })),
        emphasis: { focus: 'series' },
        cursor: 'pointer',
        barMaxWidth: 34,
      })),
    };

    chartInstance.current.setOption(options, true);

    const clickHandler = (params: any) => {
      const month = params.name as string;
      onSelectMonth?.(month === selectedMonth ? null : month);
    };
    chartInstance.current.off('click');
    chartInstance.current.on('click', clickHandler);

    const handleResize = () => chartInstance.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [data, activeIssue, selectedMonth, onSelectMonth, mode, reviewUnit]);

  useEffect(() => {
    return () => {
      chartInstance.current?.dispose();
      chartInstance.current = null;
    };
  }, []);

  return (
    <div className="relative w-full h-full min-h-[280px]">
      {data.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-slate-500">
          Sin datos para mostrar
        </div>
      )}
      <div ref={chartRef} className="w-full h-full min-h-[280px]" />
    </div>
  );
}

export default VerificationChart;
