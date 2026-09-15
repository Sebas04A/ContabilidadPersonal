import React, { useEffect } from 'react';
import * as echarts from 'echarts';
import { money } from '../utils/format';
import { TOOLTIP } from '../utils/chartTheme';
import { useEChart } from '../hooks/useEChart';

interface FundFlattenChartProps {
  dates: string[];
  raw: number[];
  offset: number[];       // the "pagos" (sum of active fixed-payments)
  flattened: number[];
  visible?: { raw: boolean; offset: boolean; flattened: boolean };
}

/**
 * Shows how the fixed-payments (offset) transform the raw running balance into a
 * flat line: crudo − pagos = aplanado. Purely a preview visualization.
 */
const FundFlattenChart: React.FC<FundFlattenChartProps> = ({ dates, raw, offset, flattened, visible }) => {
  const { ref: chartRef, chart: chartInstance } = useEChart();
  const show = visible ?? { raw: true, offset: true, flattened: true };

  useEffect(() => {
    if (!chartInstance.current) return;

    const allSeries: Record<string, echarts.SeriesOption> = {
      raw: {
        name: 'Crudo',
        type: 'line',
        step: 'end',
        data: raw,
        showSymbol: false,
        lineStyle: { width: 1.5, color: '#64748b', type: 'dashed' },
        itemStyle: { color: '#64748b' },
      },
      offset: {
        name: 'Pagos',
        type: 'line',
        step: 'end',
        data: offset,
        showSymbol: false,
        lineStyle: { width: 1.5, color: '#a78bfa' },
        itemStyle: { color: '#a78bfa' },
        areaStyle: {
          opacity: 0.12,
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#a78bfa' },
            { offset: 1, color: 'rgba(0,0,0,0)' },
          ]),
        },
      },
      flattened: {
        name: 'Aplanado',
        type: 'line',
        step: 'end',
        data: flattened,
        showSymbol: dates.length <= 40,
        symbolSize: 5,
        lineStyle: { width: 2.5, color: '#34d399' },
        itemStyle: { color: '#34d399' },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: 'rgba(255,255,255,0.25)', type: 'dashed' },
          data: [{ yAxis: 0 }],
        },
      },
    };

    const series = (['raw', 'offset', 'flattened'] as const)
      .filter(k => show[k])
      .map(k => allSeries[k]);

    const options: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      grid: { left: 8, right: 16, top: 16, bottom: 24, containLabel: true },
      tooltip: {
        ...TOOLTIP,
        trigger: 'axis',
        valueFormatter: (v: any) => (v == null ? '' : `${money(Number(v))}`),
      },
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        axisLabel: { color: '#6b7280', fontSize: 10, hideOverlap: true },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v: number) => `${money(v, 0)}` },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
      },
      series,
    };

    chartInstance.current.setOption(options, true);
  }, [dates, raw, offset, flattened, show.raw, show.offset, show.flattened]);

  return <div ref={chartRef} className="w-full h-full min-h-[240px]" />;
};

export default FundFlattenChart;
