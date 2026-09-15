import React, { useEffect } from 'react';
import * as echarts from 'echarts';
import type { FundMovement } from '../services/api';
import { money } from '../utils/format';
import { TOOLTIP } from '../utils/chartTheme';
import { useEChart } from '../hooks/useEChart';

interface FundBalanceChartProps {
  movements: FundMovement[];
  startBalance?: number;
}

/**
 * Step chart of the fund's running balance over time. Area turns green above zero
 * (a favor) and red below zero (en rojo / faltante), split at the y=0 line.
 */
const FundBalanceChart: React.FC<FundBalanceChartProps> = ({ movements, startBalance = 0 }) => {
  const { ref: chartRef, chart: chartInstance } = useEChart();

  useEffect(() => {
    if (!chartInstance.current) return;

    const dates = movements.map(m => m.date);
    const values = movements.map(m => m.running_balance);

    const minVal = Math.min(0, ...values, startBalance);
    const maxVal = Math.max(0, ...values, startBalance);

    const endBalance = values.length ? values[values.length - 1] : startBalance;
    const positive = endBalance >= 0;
    const accent = positive ? '#34d399' : '#fb7185';

    const options: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      grid: { left: 8, right: 16, top: 24, bottom: 24, containLabel: true },
      tooltip: {
        ...TOOLTIP,
        trigger: 'axis',
        formatter: (params: any) => {
          const p = Array.isArray(params) ? params[0] : params;
          const idx = p.dataIndex;
          const m = movements[idx];
          if (!m) return '';
          const sign = m.amount >= 0 ? '+' : '';
          const color = m.amount >= 0 ? '#34d399' : '#fb7185';
          return `
            <div style="font-weight:600;margin-bottom:4px">${m.date}</div>
            <div style="color:${color}">${sign}${money(m.amount)} · ${m.source === 'manual' ? 'manual' : 'transacción'}</div>
            <div style="color:#9ca3af;font-size:11px;max-width:220px;white-space:normal">${m.note || ''}</div>
            <div style="margin-top:4px;font-weight:600">Saldo: ${money(m.running_balance)}</div>
          `;
        },
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
        min: minVal < 0 ? minVal * 1.1 : 0,
        max: maxVal > 0 ? maxVal * 1.1 : 0,
        axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v: number) => `${money(v, 0)}` },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
      },
      series: [
        {
          name: 'Saldo',
          type: 'line',
          step: 'end',
          data: values,
          showSymbol: movements.length <= 40,
          symbolSize: 5,
          itemStyle: { color: accent },
          lineStyle: { width: 2, color: accent },
          areaStyle: {
            opacity: 0.15,
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: accent },
              { offset: 1, color: 'rgba(0,0,0,0)' },
            ]),
          },
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: 'rgba(255,255,255,0.25)', type: 'dashed' },
            data: [{ yAxis: 0 }],
          },
        },
      ],
    };

    chartInstance.current.setOption(options, true);
  }, [movements, startBalance]);

  return <div ref={chartRef} className="w-full h-full min-h-[240px]" />;
};

export default FundBalanceChart;
