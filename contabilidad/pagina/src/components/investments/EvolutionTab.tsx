import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import * as echarts from 'echarts';
import { investmentsApi, type Position } from '../../services/investments';
import { Chart, EJE, EmptyState, GRID, Section, Spinner, TOOLTIP, money } from './shared';

export function EvolutionTab() {
  const { data: timeline, isLoading } = useQuery({
    queryKey: ['inv-timeline'],
    queryFn: investmentsApi.getTimeline,
  });
  const { data: positions } = useQuery({
    queryKey: ['inv-positions', '', ''],
    queryFn: () => investmentsApi.getPositions(),
  });

  const capitalOption = useMemo<echarts.EChartsOption>(() => {
    if (!timeline) return {};
    const cierres = timeline.eventos.filter(e => e.tipo === 'cierre');
    return {
      grid: GRID,
      tooltip: {
        trigger: 'axis',
        ...TOOLTIP,
        valueFormatter: (v: unknown) => money(Number(v)),
      },
      legend: {
        data: ['Capital invertido', 'Interés acumulado'],
        textStyle: { color: '#a1a1aa', fontSize: 11 },
        top: 6,
      },
      xAxis: { type: 'category', data: timeline.fechas, ...EJE, boundaryGap: false },
      yAxis: [
        { type: 'value', name: 'Capital', nameTextStyle: { color: '#71717a', fontSize: 10 }, ...EJE,
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } } },
        { type: 'value', name: 'Interés', nameTextStyle: { color: '#71717a', fontSize: 10 }, ...EJE,
          splitLine: { show: false } },
      ],
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 12, borderColor: 'transparent',
        fillerColor: 'rgba(139,92,246,0.15)', handleStyle: { color: '#8b5cf6' },
        textStyle: { color: '#71717a', fontSize: 10 } }],
      series: [
        {
          name: 'Capital invertido',
          type: 'line',
          step: 'end',
          data: timeline.capital,
          symbol: 'none',
          lineStyle: { color: '#8b5cf6', width: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(139,92,246,0.35)' },
              { offset: 1, color: 'rgba(139,92,246,0.02)' },
            ]),
          },
          markPoint: {
            symbolSize: 8,
            itemStyle: { color: '#34d399' },
            label: { show: false },
            data: cierres.slice(-12).map(e => ({
              coord: [e.fecha, 0],
              value: e.interes,
              name: `Cierre ${e.portafolio}`,
            })),
          },
        },
        {
          name: 'Interés acumulado',
          type: 'line',
          yAxisIndex: 1,
          data: timeline.interes_acumulado,
          symbol: 'none',
          lineStyle: { color: '#34d399', width: 2 },
        },
      ],
    };
  }, [timeline]);

  const tnaOption = useMemo<echarts.EChartsOption>(() => {
    const cerradas = (positions ?? []).filter(
      (p: Position) => p.estado === 'cerrada' && p.fecha_cierre && (p.tna_pactada ?? p.tna) !== null,
    );
    if (!cerradas.length) return {};
    const puntos = cerradas
      .map(p => ({
        value: [p.fecha_cierre as string, p.tna_pactada ?? p.tna, p.capital],
        nombre: p.nota,
      }))
      .sort((a, b) => (a.value[0] as string).localeCompare(b.value[0] as string));

    return {
      grid: { ...GRID, right: 30 },
      tooltip: {
        ...TOOLTIP,
        formatter: (p: any) =>
          `${p.value[0]}<br/>TNA <b>${Number(p.value[1]).toFixed(2)} %</b><br/>capital ${money(p.value[2])}`,
      },
      xAxis: { type: 'time', ...EJE },
      yAxis: {
        type: 'value', name: 'TNA %', nameTextStyle: { color: '#71717a', fontSize: 10 }, ...EJE,
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
      },
      series: [{
        type: 'scatter',
        data: puntos,
        // El tamaño del punto es el capital: una tasa alta sobre 4.000 no pesa lo mismo
        // que la misma tasa sobre 28.000.
        symbolSize: (v: number[]) => Math.max(8, Math.sqrt(Number(v[2])) / 12),
        itemStyle: { color: '#8b5cf6', opacity: 0.75 },
      }],
    };
  }, [positions]);

  if (isLoading) return <Spinner />;
  if (!timeline || timeline.fechas.length === 0) {
    return <EmptyState>Todavía no hay posiciones que dibujar.</EmptyState>;
  }

  return (
    <div className="space-y-4">
      <Section
        title="Capital invertido e interés acumulado"
        subtitle="El área es la plata dentro de certificados; la línea verde, el interés neto que se fue cobrando"
      >
        <Chart option={capitalOption} height={380} />
      </Section>

      <Section
        title="Tasa por posición"
        subtitle="Cada punto es un certificado al cerrarse; el tamaño es su capital"
      >
        {Object.keys(tnaOption).length === 0
          ? <EmptyState>No hay posiciones cerradas con tasa calculable.</EmptyState>
          : <Chart option={tnaOption} height={300} />}
      </Section>
    </div>
  );
}
