import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import * as echarts from 'echarts';
import { AlertTriangle, Check, EyeOff, Lock, Sprout } from 'lucide-react';
import { investmentsApi, type StepComparison } from '../../services/investments';
import { Badge, EmptyState, KpiCard, Section, Spinner, money } from './shared';

const ACTUAL = '#06b6d4';     // cyan: lo que hay hoy escrito a mano
const GENERADO = '#8b5cf6';   // violeta: lo que sale de las posiciones
const DIFERENCIA = '#f43f5e'; // rosa: donde no coinciden
const PAGO = '#fbbf24';       // ámbar: cada pago generado, como en Rendimiento de Inversiones

/**
 * Fase 6 en modo previsualización: se dibuja la función escalón que hoy produce
 * `pagos.csv` contra la que producirían las posiciones. **Nada de esto escribe.**
 */
export function NeutralizationTab() {
  const [foco, setFoco] = useState('global');

  const { data: preview, isLoading } = useQuery({
    queryKey: ['inv-neutralization'],
    queryFn: investmentsApi.getNeutralizationPreview,
  });

  if (isLoading) return <Spinner />;
  if (!preview) return <EmptyState>No se pudo generar la previsualización.</EmptyState>;

  const { resumen } = preview;
  const portafolio = preview.por_portafolio.find(p => p.portafolio_id === foco);
  const comparacion: StepComparison = portafolio ?? preview.global;
  const pagosGenerados = portafolio
    ? preview.pagos_generados.filter(p => p.portafolio_id === portafolio.portafolio_id)
    : preview.pagos_generados;

  return (
    <div className="space-y-4">
      <div className="p-3 rounded-xl bg-surface-900/60 border border-white/[0.06] flex items-center gap-3">
        <Lock size={15} className="text-surface-400 shrink-0" />
        <p className="text-xs text-surface-300">
          Solo lectura. Esta pantalla <span className="font-semibold text-white">no escribe nada</span> en
          <code className="mx-1 px-1 py-0.5 rounded bg-surface-950/60 text-surface-200">pagos.csv</code>:
          compara lo que hay con lo que saldría de las posiciones, para decidir si el generador
          reproduce tu contabilidad antes de migrar.
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          icon={<Check size={12} />}
          label="Portafolios que cuadran"
          value={`${resumen.portafolios_que_cuadran} / ${resumen.portafolios}`}
          tone={resumen.portafolios_que_cuadran === resumen.portafolios ? 'good' : 'warn'}
          hint="Sin contar diferencias de redondeo"
        />
        <KpiCard
          icon={<AlertTriangle size={12} />}
          label="Días con descuadre real"
          value={resumen.dias_materiales.toLocaleString('en-US')}
          tone={resumen.dias_materiales === 0 ? 'good' : 'bad'}
          hint={`de ${resumen.dias.toLocaleString('en-US')} comparados`}
        />
        <KpiCard
          label="Desvío máximo"
          value={money(resumen.max_desvio)}
          tone={resumen.max_desvio > 2 ? 'bad' : 'good'}
          hint={resumen.primer_descuadre ? `Primero el ${resumen.primer_descuadre}` : 'Todo cuadra'}
        />
        <KpiCard
          icon={<Sprout size={12} />}
          label="Saldo inicial a sembrar"
          value={money(resumen.siembra_total)}
          hint={`${resumen.pagos_actuales} pagos a mano → ${resumen.pagos_generados} generados`}
        />
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setFoco('global')}
          className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
            foco === 'global' ? 'bg-primary-600 text-white' : 'bg-surface-900/60 text-surface-400 hover:text-white'
          }`}
        >
          Global
        </button>
        {preview.por_portafolio.map(p => (
          <button
            key={p.portafolio_id}
            onClick={() => setFoco(p.portafolio_id)}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
              foco === p.portafolio_id ? 'bg-primary-600 text-white' : 'bg-surface-900/60 text-surface-400 hover:text-white'
            }`}
          >
            {p.nombre}
            <span className={p.cuadra ? 'text-emerald-400' : 'text-rose-400'}>{p.cuadra ? '✓' : '✗'}</span>
          </button>
        ))}
      </div>

      <Section
        title="Escalón de pagos fijos: hoy vs. generado"
        subtitle="Las barras ámbar son cada pago generado; el área rosa, donde las dos series no coinciden"
        action={
          portafolio && (
            <div className="flex items-center gap-2 text-[11px]">
              {portafolio.es_custodia && <Badge tone="sky">custodia</Badge>}
              <span className="text-surface-400">
                saldo inicial sugerido{' '}
                <span className="font-mono text-surface-200">{money(portafolio.saldo_inicial_sugerido)}</span>
              </span>
            </div>
          )
        }
      >
        <StepChart comparacion={comparacion} pagos={pagosGenerados} />
      </Section>

      {comparacion.tramos.length > 0 && (
        <Section
          title="Dónde no coinciden"
          subtitle="Tramos contiguos con el mismo desvío; positivo = tus pagos dicen más que las posiciones"
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[520px]">
              <thead>
                <tr className="text-[11px] uppercase tracking-wider text-surface-500 border-b border-white/[0.06]">
                  <th className="text-left font-semibold px-4 py-2.5">Desde</th>
                  <th className="text-left font-semibold px-3 py-2.5">Hasta</th>
                  <th className="text-right font-semibold px-3 py-2.5">Días</th>
                  <th className="text-right font-semibold px-4 py-2.5">Desvío</th>
                </tr>
              </thead>
              <tbody>
                {comparacion.tramos.map(t => (
                  <tr key={`${t.desde}-${t.monto}`} className="border-b border-white/[0.03] last:border-0">
                    <td className="px-4 py-2 font-mono text-surface-300">{t.desde}</td>
                    <td className="px-3 py-2 font-mono text-surface-300">{t.hasta}</td>
                    <td className="px-3 py-2 text-right font-mono text-surface-400">{t.dias}</td>
                    <td className={`px-4 py-2 text-right font-mono font-bold ${t.monto < 0 ? 'text-rose-400' : 'text-amber-400'}`}>
                      {money(t.monto)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="Pagos generados" subtitle={`${pagosGenerados.length} tramos derivados de las posiciones`}>
          <div className="max-h-80 overflow-y-auto custom-scrollbar">
            <table className="w-full text-xs">
              <tbody>
                {pagosGenerados.map((p, i) => (
                  <tr key={`${p.portafolio_id}-${p.start}-${i}`} className="border-b border-white/[0.03] last:border-0">
                    <td className="px-4 py-1.5 font-mono text-surface-400">{p.start}</td>
                    <td className="px-2 py-1.5 font-mono text-surface-500">{p.end ?? '—'}</td>
                    <td className={`px-2 py-1.5 text-right font-mono ${p.amount < 0 ? 'text-rose-300' : 'text-surface-100'}`}>
                      {money(p.amount)}
                    </td>
                    <td className="px-4 py-1.5 text-surface-500 truncate max-w-[180px]" title={`${p.portafolio} · ${p.motivo}`}>
                      {p.motivo || p.portafolio}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section
          title="Pagos escritos a mano"
          subtitle={`${preview.pagos_actuales.length} filas en pagos.csv`}
          action={
            resumen.pagos_actuales_ignorados > 0 && (
              <span className="flex items-center gap-1.5 text-[11px] text-amber-400">
                <EyeOff size={12} />
                {resumen.pagos_actuales_ignorados} sin efecto
              </span>
            )
          }
        >
          <div className="max-h-80 overflow-y-auto custom-scrollbar">
            <table className="w-full text-xs">
              <tbody>
                {preview.pagos_actuales
                  .filter(p => !portafolio || p.portafolio_id === portafolio.portafolio_id)
                  .map(p => (
                    <tr key={p.id} className={`border-b border-white/[0.03] last:border-0 ${p.aplica ? '' : 'opacity-50'}`}>
                      <td className="px-4 py-1.5 font-mono text-surface-400">{p.start ?? '—'}</td>
                      <td className="px-2 py-1.5 font-mono text-surface-500">{p.end ?? '—'}</td>
                      <td className={`px-2 py-1.5 text-right font-mono ${p.amount < 0 ? 'text-rose-300' : 'text-surface-100'}`}>
                        {money(p.amount)}
                      </td>
                      <td className="px-4 py-1.5 text-surface-500 truncate max-w-[180px]" title={p.nota}>
                        {p.aplica ? p.nota : 'sin fecha de inicio: el dashboard la ignora'}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Section>
      </div>
    </div>
  );
}

/**
 * Las dos funciones escalón superpuestas, con un pago dibujado como barra horizontal a
 * su altura — el mismo lenguaje del gráfico de Rendimiento de Inversiones, que es donde
 * se ve de un vistazo si un tramo está en su sitio.
 */
function StepChart({ comparacion, pagos }: {
  comparacion: StepComparison;
  pagos: { start: string; end: string | null; amount: number; portafolio: string; motivo: string }[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  const instance = useRef<echarts.ECharts | null>(null);

  const option = useMemo<echarts.EChartsOption>(() => {
    const { fechas } = comparacion;
    const indice = new Map(fechas.map((f, i) => [f, i]));

    // Cada pago como una serie de un solo tramo: null fuera de su ventana, su monto
    // dentro. Así el tooltip lo nombra y la barra se ve exactamente donde aplica.
    const barras = pagos.map(p => {
      const desde = indice.get(p.start) ?? fechas.findIndex(f => f >= p.start);
      const hastaBruto = p.end ? (indice.get(p.end) ?? fechas.findIndex(f => f >= p.end!)) : fechas.length;
      const hasta = hastaBruto < 0 ? fechas.length : hastaBruto;
      return {
        name: `${p.portafolio}: ${p.motivo || 'pago'}`,
        type: 'line' as const,
        data: fechas.map((_f, i) => (desde >= 0 && i >= desde && i < hasta ? p.amount : null)),
        lineStyle: { color: PAGO, width: 3 },
        itemStyle: { color: PAGO },
        symbol: 'none',
        z: 5,
        tooltip: { show: false },
      };
    });

    // El eje arranca donde empieza a pasar algo: hay filas con fecha centinela (año 2000)
    // que estirarían veinte años de línea plana.
    const primerEvento = comparacion.generado.findIndex(v => Math.abs(v) > 0.01);
    const arranque = primerEvento > 0 ? Math.max(0, primerEvento - 30) : 0;

    return {
      grid: { top: 40, right: 70, bottom: 60, left: 78 },
      legend: {
        data: ['Pagos actuales', 'Pagos generados', 'Diferencia'],
        textStyle: { color: '#a1a1aa', fontSize: 11 },
        top: 6,
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(9,9,11,0.92)',
        borderColor: 'rgba(255,255,255,0.1)',
        textStyle: { color: '#e4e4e7', fontSize: 12 },
        valueFormatter: (v: unknown) => (v === null ? '—' : money(Number(v))),
      },
      xAxis: {
        type: 'category',
        data: fechas,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#3f3f46' } },
        axisLabel: { color: '#a1a1aa', fontSize: 11 },
      },
      yAxis: [
        {
          type: 'value',
          name: 'PAGOS_FIJOS',
          nameTextStyle: { color: '#71717a', fontSize: 10 },
          axisLine: { lineStyle: { color: '#3f3f46' } },
          axisLabel: { color: '#a1a1aa', fontSize: 11 },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
        },
        {
          type: 'value',
          name: 'Diferencia',
          nameTextStyle: { color: '#71717a', fontSize: 10 },
          axisLine: { lineStyle: { color: '#3f3f46' } },
          axisLabel: { color: '#a1a1aa', fontSize: 11 },
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        { type: 'inside', startValue: arranque },
        {
          type: 'slider', height: 18, bottom: 14, startValue: arranque,
          borderColor: 'transparent', fillerColor: 'rgba(139,92,246,0.15)',
          handleStyle: { color: GENERADO }, textStyle: { color: '#71717a', fontSize: 10 },
        },
      ],
      series: [
        ...barras,
        {
          name: 'Pagos actuales',
          type: 'line',
          step: 'end',
          data: comparacion.actual,
          symbol: 'none',
          lineStyle: { color: ACTUAL, width: 2.5 },
          z: 10,
        },
        {
          name: 'Pagos generados',
          type: 'line',
          step: 'end',
          data: comparacion.generado,
          symbol: 'none',
          lineStyle: { color: GENERADO, width: 2.5, type: 'dashed' },
          z: 10,
        },
        {
          name: 'Diferencia',
          type: 'line',
          yAxisIndex: 1,
          step: 'end',
          data: comparacion.diferencia,
          symbol: 'none',
          lineStyle: { color: DIFERENCIA, width: 1 },
          areaStyle: { color: 'rgba(244,63,94,0.18)' },
          z: 2,
        },
      ],
    };
  }, [comparacion, pagos]);

  useEffect(() => {
    if (!ref.current) return;
    instance.current = echarts.init(ref.current);
    const onResize = () => instance.current?.resize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      instance.current?.dispose();
      instance.current = null;
    };
  }, []);

  useEffect(() => {
    instance.current?.setOption(option, true);
  }, [option]);

  return <div ref={ref} style={{ height: 420 }} className="w-full" />;
}
