import { useMemo, useState } from 'react';
import { Search, Filter, Wallet, Calendar, BarChart3, User, ArrowRight, CheckCircle2, Clock, Link2, Scale, Layers, Scissors } from 'lucide-react';
import { useRefundableTransactions, useSupabaseDebts } from '../hooks/useTransactions';
import { DebtsChart } from '../components/DebtsChart';
import { buildTimeline, type DebtItem, type Granularity } from '../utils/debtTimeline';

const fmt = (n: number) =>
  n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function Debts() {
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState<{ startDate?: string; endDate?: string; debtor?: string }>({});
  const [showChart, setShowChart] = useState(false);
  const [granularity, setGranularity] = useState<Granularity>('month');

  // Left Side Data (Local Refundables)
  const { data: transactions, isLoading: isLoadingLeft } = useRefundableTransactions(filters);
  const uniqueDebtors = Array.from(new Set(transactions?.map(t => t.deudor).filter(Boolean) as string[])).sort();

  // Right Side Data (Supabase Debts)
  const { data: supabaseDebts, isLoading: isLoadingRight } = useSupabaseDebts({
    startDate: filters.startDate,
    endDate: filters.endDate,
    debtor: filters.debtor,
  });

  const handleDateChange = (type: 'start' | 'end', value: string) => {
    setFilters(prev => ({ ...prev, [type === 'start' ? 'startDate' : 'endDate']: value || undefined }));
  };

  // Client-side search filter (applied before grouping)
  const { bands, reconciliation } = useMemo(() => {
    const q = searchTerm.toLowerCase();
    const matchesSearch = (title: string, description: string, debtor: string) =>
      !q ||
      title.toLowerCase().includes(q) ||
      description.toLowerCase().includes(q) ||
      debtor.toLowerCase().includes(q);

    const tx = transactions?.filter(t =>
      matchesSearch(t.nombre_limpio || '', t.DESCRIPCION, t.deudor || ''),
    );
    const debts = supabaseDebts?.filter(d =>
      matchesSearch(d.DESCRIPCION, d.DESCRIPCION, d.DEUDOR_NOMBRE || ''),
    );

    return buildTimeline(tx, debts, granularity);
  }, [transactions, supabaseDebts, searchTerm, granularity]);

  const isLoading = isLoadingLeft || isLoadingRight;

  return (
    <div className="flex flex-col h-full bg-surface-950 relative overflow-hidden">
      {/* Background Gradients */}
      <div className="fixed top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0">
        <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-primary-600/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] left-[-5%] w-[400px] h-[400px] bg-secondary-600/10 rounded-full blur-[100px]" />
      </div>

      <div className="flex flex-col h-full relative z-10">
        {/* HEADER & CONTROLS */}
        <div className="shrink-0 p-6 md:p-8 flex flex-col gap-6">
          {/* Title & Actions */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-5">
              <div className="relative group">
                <div className="absolute -inset-0.5 bg-gradient-to-tr from-indigo-500 to-purple-500 rounded-2xl blur opacity-30 group-hover:opacity-60 transition duration-500"></div>
                <div className="relative p-3.5 rounded-2xl bg-surface-950 border border-white/10 text-white shadow-2xl">
                  <Wallet size={32} strokeWidth={1.5} />
                </div>
              </div>
              <div>
                <h1 className="text-3xl font-bold text-white tracking-tight">Gestión de Deudas</h1>
                <div className="flex items-center gap-2 mt-1">
                  <span className="flex h-2 w-2 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  <p className="text-surface-400 text-sm font-medium">Comparativa local ↔ Supabase por fecha</p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Granularity toggle */}
              <div className="flex items-center bg-surface-900 border border-white/10 rounded-xl p-1 shadow-lg">
                {(['month', 'week'] as Granularity[]).map(g => (
                  <button
                    key={g}
                    onClick={() => setGranularity(g)}
                    className={`px-3.5 py-1.5 rounded-lg text-sm font-semibold transition-all ${
                      granularity === g
                        ? 'bg-indigo-500/20 text-indigo-300 shadow-inner'
                        : 'text-surface-400 hover:text-white'
                    }`}
                  >
                    {g === 'month' ? 'Mes' : 'Semana'}
                  </button>
                ))}
              </div>

              <button
                onClick={() => setShowChart(true)}
                className="group relative px-5 py-2.5 bg-surface-900 hover:bg-surface-800 text-surface-200 hover:text-white rounded-xl border border-white/10 transition-all shadow-lg hover:shadow-indigo-500/20 hover:border-indigo-500/30 active:scale-95 flex items-center gap-2"
              >
                <BarChart3 size={18} />
                <span className="font-semibold text-sm">Analizar Datos</span>
              </button>
            </div>
          </div>

          {/* Filter Bar */}
          <div className="w-full bg-surface-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-2 flex flex-col lg:flex-row gap-2 shadow-2xl">
            <div className="flex-[2] relative group">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-500 group-focus-within:text-indigo-400 transition-colors pointer-events-none" size={20} />
              <input
                type="text"
                placeholder="Buscar por concepto o deudor..."
                className="w-full h-12 bg-surface-950/30 border border-transparent hover:border-white/5 focus:border-indigo-500/30 rounded-xl pl-12 pr-4 text-surface-100 placeholder:text-surface-500 focus:ring-0 text-base transition-all"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>

            <div className="flex-1 relative group min-w-[200px]">
              <User className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-500 group-hover:text-indigo-400 transition-colors pointer-events-none" size={18} />
              <select
                className="w-full h-12 bg-surface-950/30 border border-transparent hover:border-white/5 focus:border-indigo-500/30 rounded-xl pl-11 pr-10 text-surface-200 focus:ring-0 cursor-pointer text-sm font-medium hover:text-white transition-all appearance-none"
                onChange={(e) => setFilters(prev => ({ ...prev, debtor: e.target.value || undefined }))}
                value={filters.debtor || ''}
              >
                <option value="" className="bg-surface-950 text-surface-400">Todos los deudores</option>
                {uniqueDebtors.map(d => (
                  <option key={d} value={d} className="bg-surface-950 text-white">{d}</option>
                ))}
              </select>
              <Filter className="absolute right-4 top-1/2 -translate-y-1/2 text-surface-600 pointer-events-none" size={16} />
            </div>

            <div className="flex items-center bg-surface-950/30 rounded-xl px-4 border border-transparent hover:border-white/5 focus-within:border-indigo-500/30 transition-all h-12">
              <Calendar size={18} className="text-surface-500 mr-3" />
              <input
                type="date"
                className="bg-transparent border-none text-sm text-surface-300 focus:text-white focus:ring-0 cursor-pointer h-full w-28 font-mono p-0"
                onChange={(e) => handleDateChange('start', e.target.value)}
              />
              <span className="text-surface-600 mx-2">→</span>
              <input
                type="date"
                className="bg-transparent border-none text-sm text-surface-300 focus:text-white focus:ring-0 cursor-pointer h-full w-28 font-mono p-0"
                onChange={(e) => handleDateChange('end', e.target.value)}
              />
            </div>
          </div>

          {/* Reconciliation bar */}
          <div className="w-full grid grid-cols-2 md:grid-cols-4 gap-3">
            <ReconTile label="Total Local" value={`$${fmt(reconciliation.totalLocal)}`} tone="indigo" />
            <ReconTile label="Total Supabase" value={`$${fmt(reconciliation.totalSupabase)}`} tone="emerald" sub="por cobrar" />
            <ReconTile
              label="Diferencia"
              value={`${reconciliation.diff >= 0 ? '+' : '−'}$${fmt(Math.abs(reconciliation.diff))}`}
              tone={Math.abs(reconciliation.diff) < 0.01 ? 'emerald' : 'amber'}
              icon={<Scale size={14} />}
            />
            <div className="flex flex-col justify-center gap-1.5 rounded-2xl bg-surface-900/40 border border-white/10 px-4 py-3">
              <div className="flex items-center gap-2 text-[11px] font-semibold">
                <span className="flex items-center gap-1 text-amber-300"><Link2 size={12} />{reconciliation.countMatched} coincidentes</span>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-surface-400">
                <span>{reconciliation.countOnlyLocal} solo local</span>
                <span className="text-surface-600">·</span>
                <span>{reconciliation.countOnlySupabase} solo Supabase</span>
              </div>
            </div>
          </div>
        </div>

        {/* SINGLE SCROLL TIMELINE */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-4 md:px-8 pb-8">
          {/* Column headers (labels for each half) */}
          <div className="hidden lg:grid grid-cols-2 gap-0 sticky top-0 z-30 bg-surface-950/80 backdrop-blur-md">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5">
              <div className="p-1.5 bg-indigo-500/10 rounded-lg text-indigo-400"><ArrowRight size={14} /></div>
              <span className="text-xs font-bold text-white uppercase tracking-wide">Pendientes Locales</span>
              <span className="text-[10px] text-surface-500">reembolsos etiquetados</span>
            </div>
            <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5 border-l border-white/5">
              <div className="p-1.5 bg-emerald-500/10 rounded-lg text-emerald-400"><CheckCircle2 size={14} /></div>
              <span className="text-xs font-bold text-white uppercase tracking-wide">Histórico Supabase</span>
              <span className="text-[10px] text-surface-500">app de deudas</span>
            </div>
          </div>

          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-64 gap-3 text-surface-500">
              <div className="w-6 h-6 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin"></div>
              <span className="text-sm">Cargando comparativa...</span>
            </div>
          ) : bands.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-surface-500 border-2 border-dashed border-white/5 rounded-2xl bg-surface-900/20 mt-6">
              <Wallet size={32} className="mb-3 opacity-50" />
              <p className="text-sm font-medium">No hay deudas que coincidan con los filtros</p>
            </div>
          ) : (
            <div className="flex flex-col">
              {bands.map(band => (
                <section key={band.key}>
                  {/* Period header (sticky, shared time axis) */}
                  <div className="sticky top-[45px] z-20 flex items-center gap-3 py-3 bg-surface-950/90 backdrop-blur-md">
                    <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/10 to-white/10" />
                    <div className="flex items-center gap-3 px-4 py-1.5 rounded-full bg-surface-900 border border-white/10 shadow-lg">
                      <span className="text-xs font-mono font-bold text-indigo-300">${fmt(band.leftTotal)}</span>
                      <span className="text-sm font-bold text-white uppercase tracking-wider whitespace-nowrap">{band.label}</span>
                      <span className="text-xs font-mono font-bold text-emerald-300">${fmt(band.rightTotal)}</span>
                    </div>
                    <div className="flex-1 h-px bg-gradient-to-l from-transparent via-white/10 to-white/10" />
                  </div>

                  {/* Two halves of this period band */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 lg:gap-0 lg:divide-x lg:divide-white/5 pb-4">
                    <div className="flex flex-col gap-2.5 lg:pr-4">
                      {band.left.length === 0 ? (
                        <EmptySide />
                      ) : (
                        band.left.map(item => <DebtCard key={item.key} item={item} />)
                      )}
                    </div>
                    <div className="flex flex-col gap-2.5 lg:pl-4">
                      {band.right.length === 0 ? (
                        <EmptySide />
                      ) : (
                        band.right.map(item => <DebtCard key={item.key} item={item} />)
                      )}
                    </div>
                  </div>
                </section>
              ))}
            </div>
          )}
        </div>
      </div>

      {showChart && <DebtsChart onClose={() => setShowChart(false)} />}
    </div>
  );
}

function ReconTile({ label, value, tone, sub, icon }: {
  label: string;
  value: string;
  tone: 'indigo' | 'emerald' | 'amber';
  sub?: string;
  icon?: React.ReactNode;
}) {
  const toneMap = {
    indigo: 'text-indigo-400',
    emerald: 'text-emerald-400',
    amber: 'text-amber-400',
  };
  return (
    <div className="flex flex-col justify-center gap-0.5 rounded-2xl bg-surface-900/40 border border-white/10 px-4 py-3">
      <div className="flex items-center gap-1.5 text-[10px] text-surface-500 uppercase tracking-wider font-bold">
        {icon}
        {label}
      </div>
      <div className={`text-xl font-mono font-bold ${toneMap[tone]}`}>{value}</div>
      {sub && <div className="text-[10px] text-surface-500">{sub}</div>}
    </div>
  );
}

function EmptySide() {
  return (
    <div className="flex items-center justify-center h-16 rounded-xl border border-dashed border-white/5 bg-surface-900/10 text-[11px] text-surface-600 font-medium">
      — sin registro —
    </div>
  );
}

function DebtCard({ item }: { item: DebtItem }) {
  const isLocal = item.side === 'local';
  const matched = item.matchId !== undefined;
  const paidDebt = item.side === 'supabase' && item.paid;

  const baseClass = matched
    ? 'border-amber-500/40 bg-amber-500/[0.04] hover:bg-amber-500/[0.07]'
    : paidDebt
      ? 'bg-surface-900/20 border-white/5 opacity-60 hover:opacity-100'
      : isLocal
        ? 'bg-surface-900/40 border-white/5 hover:border-indigo-500/30 hover:bg-surface-800/60'
        : 'bg-surface-900/40 border-white/5 hover:border-emerald-500/30 hover:bg-surface-800/60';

  return (
    <div
      className={`group relative p-3.5 rounded-2xl border transition-all overflow-hidden ${baseClass}`}
      title={matched ? 'Posible misma deuda (mismo monto y fecha cercana)' : undefined}
    >
      {matched && (
        <span className="absolute top-2 right-2 flex items-center gap-1 text-[9px] font-bold text-amber-300/90 bg-amber-500/10 px-1.5 py-0.5 rounded-md">
          <Link2 size={9} /> POSIBLE MATCH
        </span>
      )}

      <div className="relative z-10 flex justify-between items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className={`font-bold truncate text-sm ${paidDebt ? 'text-surface-400 line-through' : 'text-surface-100'}`}>
              {item.title}
            </h3>
            {item.groupCount && item.groupCount > 1 && (
              <span
                className="flex items-center gap-1 shrink-0 text-[9px] font-bold text-purple-300 bg-purple-500/10 border border-purple-500/20 px-1.5 py-0.5 rounded-md uppercase tracking-wide"
                title={`Grupo de ${item.groupCount} transacciones sumadas`}
              >
                <Layers size={9} /> {item.groupCount} agrup.
              </span>
            )}
            {item.isSplitPart && (
              <span
                className="flex items-center gap-1 shrink-0 text-[9px] font-bold text-cyan-300 bg-cyan-500/10 border border-cyan-500/20 px-1.5 py-0.5 rounded-md uppercase tracking-wide"
                title="Parte de una transacción dividida"
              >
                <Scissors size={9} /> división
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-surface-400">
            {item.debtor && (
              <span className={`px-1.5 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wide shrink-0 ${
                isLocal
                  ? 'bg-indigo-500/10 border border-indigo-500/20 text-indigo-300'
                  : 'bg-sky-500/10 border border-sky-500/20 text-sky-300'
              }`}>
                {item.debtor}
              </span>
            )}
            <span className="flex items-center gap-1">
              <Calendar size={11} />
              {item.date.toLocaleDateString()}
            </span>
            {paidDebt && item.paidDate && (
              <span className="flex items-center gap-1 text-emerald-400/80">
                <Clock size={11} />
                Pagado: {new Date(item.paidDate.replace(' ', 'T')).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className={`text-base font-mono font-bold ${paidDebt ? 'text-surface-500' : 'text-white'}`}>
            ${item.amount.toFixed(2)}
          </div>
          {item.side === 'supabase' ? (
            <div className={`text-[10px] font-bold px-1.5 py-0.5 rounded inline-flex items-center gap-1 mt-1 ${
              item.paid ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'
            }`}>
              {item.paid ? (<><CheckCircle2 size={10} /> PAGADA</>) : 'PENDIENTE'}
            </div>
          ) : (
            <span className="text-[10px] font-bold text-surface-500 bg-surface-950/50 px-1.5 py-0.5 rounded mt-1 inline-block">
              PENDIENTE
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
