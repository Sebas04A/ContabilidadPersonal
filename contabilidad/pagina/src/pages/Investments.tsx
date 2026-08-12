import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, GitCompare, LineChart, Scale, TrendingUp } from 'lucide-react';
import { investmentsApi } from '../services/investments';
import { EvolutionTab } from '../components/investments/EvolutionTab';
import { NeutralizationTab } from '../components/investments/NeutralizationTab';
import { PositionsTab } from '../components/investments/PositionsTab';
import { ReconcileTab } from '../components/investments/ReconcileTab';
import { SummaryTab } from '../components/investments/SummaryTab';

type Tab = 'posiciones' | 'resumen' | 'evolucion' | 'conciliacion' | 'neutralizacion';

const TABS: { id: Tab; label: string; icon: typeof TrendingUp }[] = [
  { id: 'posiciones', label: 'Posiciones', icon: TrendingUp },
  { id: 'resumen', label: 'Resumen', icon: Activity },
  { id: 'evolucion', label: 'Evolución', icon: LineChart },
  { id: 'conciliacion', label: 'Conciliación', icon: GitCompare },
  { id: 'neutralizacion', label: 'Neutralización', icon: Scale },
];

export function Investments() {
  const [tab, setTab] = useState<Tab>('posiciones');

  // Los portafolios los necesitan tres de las cuatro pestañas, así que se piden una vez
  // aquí y bajan por props en vez de repetir la consulta en cada una.
  const { data: portfolios } = useQuery({
    queryKey: ['inv-portfolios'],
    queryFn: investmentsApi.getPortfolios,
  });

  return (
    <div className="flex flex-col h-full bg-surface-950 relative overflow-hidden">
      <div className="fixed top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0">
        <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-primary-600/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] left-[-5%] w-[400px] h-[400px] bg-emerald-600/10 rounded-full blur-[100px]" />
      </div>

      <header className="relative z-10 px-6 pt-6 pb-4 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-primary-500/10 text-primary-400">
            <TrendingUp size={22} strokeWidth={1.5} />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white leading-tight">Inversiones</h1>
            <p className="text-[11px] text-surface-400">Plazos fijos, rendimiento y conciliación con el banco</p>
          </div>
        </div>

        <nav className="p-1 bg-surface-900/60 backdrop-blur-xl border border-white/[0.06] rounded-xl flex items-center gap-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                tab === id ? 'bg-primary-600 text-white shadow-lg shadow-primary-600/20' : 'text-surface-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </nav>
      </header>

      <div className="relative z-10 flex-1 overflow-y-auto px-6 pb-8 custom-scrollbar">
        <div className="max-w-[1500px] mx-auto animate-in fade-in slide-in-from-bottom-2 duration-300">
          {tab === 'posiciones' && <PositionsTab portfolios={portfolios ?? []} />}
          {tab === 'resumen' && <SummaryTab />}
          {tab === 'evolucion' && <EvolutionTab />}
          {tab === 'conciliacion' && <ReconcileTab portfolios={portfolios ?? []} />}
          {tab === 'neutralizacion' && <NeutralizationTab />}
        </div>
      </div>
    </div>
  );
}
