import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Calendar, Clock, Coins, Percent, PiggyBank, TrendingDown, Wallet } from 'lucide-react';
import { investmentsApi, type Kpis } from '../../services/investments';
import { Badge, EmptyState, KpiCard, Section, Spinner, capitalDia, fmt, money, pct } from './shared';

type Ambito = 'propio' | 'custodia' | 'global';

const AMBITOS: { id: Ambito; label: string; hint: string }[] = [
  { id: 'propio', label: 'Propio', hint: 'Solo la plata que es tuya' },
  { id: 'custodia', label: 'Custodia', hint: 'Plata de otros en tu cuenta' },
  { id: 'global', label: 'Todo', hint: 'Propio y custodia juntos' },
];

export function SummaryTab() {
  const [ambito, setAmbito] = useState<Ambito>('propio');
  const { data: summary, isLoading } = useQuery({
    queryKey: ['inv-summary'],
    queryFn: investmentsApi.getSummary,
  });

  if (isLoading) return <Spinner />;
  if (!summary) return <EmptyState>No se pudo calcular el resumen.</EmptyState>;

  const kpis: Kpis = summary[ambito];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="p-1 bg-surface-900/60 border border-white/[0.06] rounded-xl flex items-center gap-1">
          {AMBITOS.map(a => (
            <button
              key={a.id}
              onClick={() => setAmbito(a.id)}
              title={a.hint}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                ambito === a.id ? 'bg-primary-600 text-white' : 'text-surface-400 hover:text-white hover:bg-white/5'
              }`}
            >
              {a.label}
            </button>
          ))}
        </div>
        <span className="text-[11px] text-surface-500">Al {summary.fecha}</span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          icon={<Wallet size={12} />}
          label="Capital invertido hoy"
          value={money(kpis.capital_invertido)}
          tone={kpis.capital_invertido > 0 ? 'good' : 'default'}
          hint={kpis.abiertas > 0 ? `${kpis.abiertas} posición(es) abierta(s)` : 'Nada adentro ahora mismo'}
        />
        <KpiCard
          icon={<Coins size={12} />}
          label="Interés cobrado"
          value={money(kpis.interes_cobrado)}
          tone="good"
          hint={`Neto ${money(kpis.interes_neto)} · retención ${money(kpis.retencion)}`}
        />
        <KpiCard
          icon={<Percent size={12} />}
          label="TNA ponderada"
          value={pct(kpis.tna_ponderada)}
          hint={kpis.sin_apertura > 0
            ? `${kpis.sin_apertura} sin apertura conocida quedan fuera`
            : 'Pesada por capital-día'}
        />
        <KpiCard
          icon={<TrendingDown size={12} />}
          label="XIRR"
          value={pct(kpis.xirr)}
          hint="Tasa real con las fechas de cada flujo"
        />
        <KpiCard
          icon={<PiggyBank size={12} />}
          label="Capital rotado"
          value={money(kpis.capital_rotado)}
          hint={`${kpis.cerradas} cerradas · ${kpis.posiciones} en total`}
        />
        <KpiCard
          icon={<Clock size={12} />}
          label="Capital·día"
          value={capitalDia(kpis.capital_dia)}
          hint="USD que estuvieron trabajando, por día"
        />
        <KpiCard
          icon={<Coins size={12} />}
          label="Suelto sin rendir"
          value={money(kpis.residual_suelto)}
          tone={kpis.residual_suelto > 0 ? 'warn' : 'default'}
          hint="Plata de inversión fuera de un certificado"
        />
        <KpiCard
          icon={<Calendar size={12} />}
          label="Próximo vencimiento"
          value={kpis.proximo_vencimiento ?? '—'}
          hint={kpis.interes_devengado ? `Devengado ≈${money(kpis.interes_devengado)}` : 'Sin posiciones con plazo'}
        />
      </div>

      <Section title="Por portafolio" subtitle="Cuánto rindió la plata de cada uno">
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[760px]">
            <thead>
              <tr className="text-[11px] uppercase tracking-wider text-surface-500 border-b border-white/[0.06]">
                <th className="text-left font-semibold px-4 py-2.5">Portafolio</th>
                <th className="text-right font-semibold px-3 py-2.5">Invertido hoy</th>
                <th className="text-right font-semibold px-3 py-2.5">Rotado</th>
                <th className="text-right font-semibold px-3 py-2.5">Interés</th>
                <th className="text-right font-semibold px-3 py-2.5">Neto</th>
                <th className="text-right font-semibold px-3 py-2.5">TNA pond.</th>
                <th className="text-right font-semibold px-4 py-2.5">XIRR</th>
              </tr>
            </thead>
            <tbody>
              {summary.por_portafolio.map(p => (
                <tr key={p.portafolio_id} className="border-b border-white/[0.03] last:border-0 hover:bg-white/[0.02]">
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="text-surface-200">{p.nombre}</span>
                      {p.es_custodia && <Badge tone="sky">custodia</Badge>}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-surface-200">{money(p.capital_invertido)}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-surface-400">{money(p.capital_rotado)}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-emerald-400">{money(p.interes_cobrado)}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-surface-200">{money(p.interes_neto)}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-primary-300">{pct(p.tna_ponderada)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-primary-300">{pct(p.xirr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section
        title="Por año de cierre"
        subtitle="La tendencia que no se ve en ninguna otra pantalla"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[560px]">
            <thead>
              <tr className="text-[11px] uppercase tracking-wider text-surface-500 border-b border-white/[0.06]">
                <th className="text-left font-semibold px-4 py-2.5">Año</th>
                <th className="text-right font-semibold px-3 py-2.5">Posiciones</th>
                <th className="text-right font-semibold px-3 py-2.5">Capital medio</th>
                <th className="text-right font-semibold px-3 py-2.5">Interés</th>
                <th className="text-right font-semibold px-4 py-2.5">TNA ponderada</th>
              </tr>
            </thead>
            <tbody>
              {summary.por_anio.map((fila, i) => {
                const previa = summary.por_anio[i - 1]?.tna_ponderada;
                const cae = previa != null && fila.tna_ponderada != null && fila.tna_ponderada < previa - 1;
                return (
                  <tr key={fila.anio} className="border-b border-white/[0.03] last:border-0">
                    <td className="px-4 py-2.5 font-mono text-surface-200">{fila.anio}</td>
                    <td className="px-3 py-2.5 text-right font-mono text-surface-400">{fila.posiciones}</td>
                    <td className="px-3 py-2.5 text-right font-mono text-surface-300">{money(fila.capital_medio)}</td>
                    <td className="px-3 py-2.5 text-right font-mono text-emerald-400">{money(fila.interes)}</td>
                    <td className={`px-4 py-2.5 text-right font-mono font-bold ${cae ? 'text-rose-400' : 'text-primary-300'}`}>
                      {fila.tna_ponderada != null ? `${fmt(fila.tna_ponderada)} %` : '—'}
                      {cae && <span className="ml-1 text-[10px] font-normal">▼</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      {summary.sin_portafolio > 0 && (
        <div className="p-3 rounded-xl bg-amber-500/[0.06] border border-amber-500/20 text-xs text-amber-200">
          {summary.sin_portafolio} posición(es) sin portafolio asignado: no entran en ningún
          desglose. Asígnalas desde Posiciones o repártelas en Conciliación.
        </div>
      )}
    </div>
  );
}
