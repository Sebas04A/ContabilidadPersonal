import { useCallback, useMemo, useState } from 'react';
import { Transaction, TransactionUpdate } from '../services/api';
import { useAllTransactions, useTags, useUpdateTransaction } from '../hooks/useTransactions';
import { EditModal } from '../components/EditModal';
import VerificationChart, { MonthlyIssuePoint } from '../components/VerificationChart';
import {
  ShieldCheck, Tag, CheckCircle2, AlertCircle, RefreshCw,
  ChevronRight, ArrowUpRight, ArrowDownLeft, Search, X, Sparkles, Scissors, Flame, Heart, Calendar,
} from 'lucide-react';

// ── Issue definitions ─────────────────────────────────────────────────────────

type IssueKey = 'sin_revisar' | 'sin_categoria' | 'sin_prioridad' | 'sin_felicidad' | 'sin_tags';

const catMissing = (t: Transaction) => {
  const c = (t.categoria || '').trim().toLowerCase();
  return !c || c === '---' || c === 'sin categoría' || c === 'sin categoria';
};
const tagsMissing = (t: Transaction) => !(t.tags || '').trim();
const prioridadMissing = (t: Transaction) => {
  const cat = (t.categoria || '').trim().toLowerCase();
  const isExcluded = cat === 'inversion' || cat === 'inversión' || cat === 'inversiones' ||
                     cat === 'deuda' || cat === 'deudas' ||
                     cat === 'tarjeta' || cat === 'tarjetas';
  if (isExcluded) return false;

  const p = (t.prioridad || '').trim().toLowerCase();
  return !p || p === '---';
};
const felicidadMissing = (t: Transaction) => {
  if (t.es_reembolsable) return false;

  const cat = (t.categoria || '').trim().toLowerCase();
  const isExcluded = cat === 'inversion' || cat === 'inversión' || cat === 'inversiones' ||
                     cat === 'deuda' || cat === 'deudas' ||
                     cat === 'tarjeta' || cat === 'tarjetas';
  if (isExcluded) return false;

  const f = Number(t.felicidad);
  return t.felicidad == null || Number.isNaN(f) || f === 0;
};
const reviewMissing = (t: Transaction) => !t.revisado;

const SECTION_LIMIT = 6;

interface IssueDef {
  key: IssueKey;
  label: string;
  short: string;
  severity: string;    // human label for the severity tier
  sevColor: string;    // tailwind classes for the severity badge
  icon: any;
  color: string;       // tailwind text color
  ring: string;        // hex for ring / chart
  test: (t: Transaction) => boolean;
}

// Order = hierarchy (most important first): drives cards, sections and chart.
const ISSUES: IssueDef[] = [
  { key: 'sin_revisar', label: 'Sin revisar', short: 'Revisar', severity: 'Crítico', sevColor: 'bg-red-500/15 text-red-300 border-red-500/30', icon: CheckCircle2, color: 'text-red-400', ring: '#ef4444', test: reviewMissing },
  { key: 'sin_categoria', label: 'Sin categoría', short: 'Categoría', severity: 'Grave', sevColor: 'bg-amber-500/15 text-amber-300 border-amber-500/30', icon: Tag, color: 'text-amber-400', ring: '#f59e0b', test: catMissing },
  { key: 'sin_prioridad', label: 'Sin necesidad/deseo', short: 'Prioridad', severity: 'Grave', sevColor: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', icon: Flame, color: 'text-emerald-400', ring: '#10b981', test: prioridadMissing },
  { key: 'sin_felicidad', label: 'Sin felicidad', short: 'Felicidad', severity: 'Medio', sevColor: 'bg-pink-500/15 text-pink-300 border-pink-500/30', icon: Heart, color: 'text-pink-400', ring: '#ec4899', test: felicidadMissing },
  { key: 'sin_tags', label: 'Sin etiquetas', short: 'Etiquetas', severity: 'Leve', sevColor: 'bg-violet-500/15 text-violet-300 border-violet-500/30', icon: Sparkles, color: 'text-violet-400', ring: '#8b5cf6', test: tagsMissing },
];

// A display transaction fails an issue if it — or any of its split parts — fails.
function txFails(t: Transaction, test: (t: Transaction) => boolean): boolean {
  if (t.subTransactions && t.subTransactions.length > 0) {
    return t.subTransactions.some(test);
  }
  return test(t);
}

// Issues that apply to a transaction. An unreviewed transaction can't reasonably
// have the rest filled in, so it only surfaces under "Sin revisar".
function activeIssuesFor(t: Transaction): IssueDef[] {
  if (txFails(t, reviewMissing)) {
    return ISSUES.filter(i => i.key === 'sin_revisar');
  }
  return ISSUES.filter(i => i.key !== 'sin_revisar' && txFails(t, i.test));
}

// Group split parts into a single "master" display transaction (mirrors Labeling).
function groupSplits(txs: Transaction[]): Transaction[] {
  const map = new Map<string, Transaction[]>();
  txs.forEach(t => {
    if (!map.has(t.id)) map.set(t.id, []);
    map.get(t.id)!.push(t);
  });
  const result: Transaction[] = [];
  map.forEach(parts => {
    if (parts.length === 1) {
      result.push(parts[0]);
    } else {
      const total = parts.reduce((s, p) => s + p.MONTO, 0);
      result.push({ ...parts[0], MONTO: total, subTransactions: parts });
    }
  });
  return result;
}

// ── Small SVG donut ring ────────────────────────────────────────────────────

function Ring({ pct, color, size = 88 }: { pct: number; color: string; size?: number }) {
  const stroke = 8;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - pct / 100);
  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} fill="none" />
      <circle
        cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none"
        strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
        style={{ transition: 'stroke-dashoffset 0.6s ease' }}
      />
    </svg>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export function Verification() {
  const { data: rawTx, isLoading, isError, refetch, isFetching } = useAllTransactions();
  const { data: existingTags } = useTags();
  const updateMutation = useUpdateTransaction();

  const [activeIssue, setActiveIssue] = useState<IssueKey | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [chartMode, setChartMode] = useState<'issues' | 'review'>('issues');
  const [reviewUnit, setReviewUnit] = useState<'pct' | 'count'>('pct');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const allTx = useMemo(() => groupSplits((rawTx || []).filter(t => !t.es_reembolsable)), [rawTx]);

  // Full available date span (for presets / input bounds).
  const dateBounds = useMemo(() => {
    let min = '', max = '';
    for (const t of allTx) {
      const d = (t.FECHA || '').slice(0, 10);
      if (!d) continue;
      if (!min || d < min) min = d;
      if (!max || d > max) max = d;
    }
    return { min, max };
  }, [allTx]);

  // Everything on the page is scoped to the selected date range.
  const displayTx = useMemo(() => {
    if (!startDate && !endDate) return allTx;
    return allTx.filter(t => {
      const d = (t.FECHA || '').slice(0, 10);
      if (startDate && d < startDate) return false;
      if (endDate && d > endDate) return false;
      return true;
    });
  }, [allTx, startDate, endDate]);

  // Set range to the last N months, anchored on the latest data (or today).
  const setLastMonths = (n: number) => {
    const anchor = dateBounds.max || new Date().toISOString().slice(0, 10);
    const d = new Date(anchor);
    d.setMonth(d.getMonth() - n);
    setStartDate(d.toISOString().slice(0, 10));
    setEndDate(dateBounds.max || anchor);
  };
  const setThisYear = () => {
    const anchor = dateBounds.max || new Date().toISOString().slice(0, 10);
    setStartDate(`${anchor.slice(0, 4)}-01-01`);
    setEndDate(anchor);
  };
  const clearRange = () => { setStartDate(''); setEndDate(''); };
  const rangeActive = !!(startDate || endDate);

  // Per-issue failing sets
  const buckets = useMemo(() => {
    const b: Record<IssueKey, Transaction[]> = {
      sin_revisar: [], sin_categoria: [], sin_prioridad: [], sin_felicidad: [], sin_tags: [],
    };
    for (const t of displayTx) {
      for (const issue of activeIssuesFor(t)) b[issue.key].push(t);
    }
    return b;
  }, [displayTx]);

  const total = displayTx.length;

  const totalSumAmount = useMemo(() => {
    return displayTx.reduce((sum, t) => sum + Math.abs(t.MONTO), 0);
  }, [displayTx]);

  const health = useMemo(() => {
    if (total === 0) return 100;
    const clean = displayTx.filter(t =>
      !txFails(t, reviewMissing) && !txFails(t, catMissing) && !txFails(t, prioridadMissing)
    ).length;
    return Math.round((clean / total) * 100);
  }, [displayTx, total]);

  const monthly: MonthlyIssuePoint[] = useMemo(() => {
    const m = new Map<string, MonthlyIssuePoint>();
    for (const t of displayTx) {
      const month = (t.FECHA || '').slice(0, 7);
      if (!month) continue;
      if (!m.has(month)) {
        m.set(month, { month, total: 0, sin_revisar: 0, sin_categoria: 0, sin_prioridad: 0, sin_felicidad: 0, sin_tags: 0 });
      }
      const p = m.get(month)!;
      p.total += 1;
      for (const issue of activeIssuesFor(t)) p[issue.key] += 1;
    }
    return Array.from(m.values()).sort((a, b) => a.month.localeCompare(b.month));
  }, [displayTx]);

  // Apply month + search filters and sort by most-negative amount first.
  const filterSort = useCallback((base: Transaction[]) => {
    let r = base;
    if (selectedMonth) r = r.filter(t => (t.FECHA || '').slice(0, 7) === selectedMonth);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      r = r.filter(t =>
        (t.DESCRIPCION || '').toLowerCase().includes(q) ||
        (t.nombre_limpio || '').toLowerCase().includes(q)
      );
    }
    return [...r].sort((a, b) => a.MONTO - b.MONTO);
  }, [selectedMonth, search]);

  // Filtered+sorted list per issue (visible sections respect the active filter).
  const sections = useMemo(() => {
    return ISSUES
      .filter(i => !activeIssue || i.key === activeIssue)
      .map(issue => ({ issue, txs: filterSort(buckets[issue.key]) }));
  }, [activeIssue, buckets, filterSort]);

  const handleSave = (id: string, updates: TransactionUpdate) => {
    updateMutation.mutate({ id, updates });
  };

  if (isError) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="bg-red-500/10 p-6 rounded-2xl border border-red-500/20 text-center max-w-md">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-red-400 mb-2">Error de conexión</h3>
          <p className="text-gray-400 mb-4">No se pudieron cargar las transacciones.</p>
          <button onClick={() => refetch()} className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded-lg transition-colors">
            Reintentar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden relative">
      {/* Header */}
      <header className="h-24 flex items-center justify-between px-8 z-20 relative shrink-0">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-2xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 border border-white/5 text-emerald-400">
            <ShieldCheck size={26} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Verificación</h1>
            <p className="text-xs text-gray-500 font-medium tracking-wide">Calidad del etiquetado en todos tus movimientos</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Overall health pill */}
          <div className="hidden md:flex glass px-6 py-3 rounded-2xl items-center gap-4 ring-1 ring-white/5 shadow-2xl">
            <div className="relative flex items-center justify-center">
              <Ring pct={health} color={health >= 80 ? '#10b981' : health >= 50 ? '#f59e0b' : '#f43f5e'} size={56} />
              <span className="absolute text-xs font-bold text-white">{health}%</span>
            </div>
            <div>
              <p className="text-[10px] text-emerald-300/60 font-bold uppercase tracking-[0.2em]">Salud</p>
              <p className="text-sm font-bold text-white">{total.toLocaleString()} movimientos</p>
            </div>
          </div>

          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="glass p-3.5 rounded-2xl text-emerald-400 hover:text-white hover:bg-emerald-600 transition-all duration-300 shadow-lg disabled:opacity-50 group active:scale-95"
            title="Recargar"
          >
            <RefreshCw size={22} className={`transition-transform duration-700 ${isFetching ? 'animate-spin' : 'group-hover:rotate-180'}`} />
          </button>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 pb-8 custom-scrollbar">
        <div className="max-w-[1600px] mx-auto space-y-8 mt-2">

          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="w-10 h-10 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
            </div>
          ) : (
            <>
              {/* Date range filter */}
              <div className="glass-card p-4 rounded-2xl flex flex-col lg:flex-row lg:items-center gap-4">
                <div className="flex items-center gap-2 text-gray-400 shrink-0">
                  <Calendar size={18} className="text-emerald-400" />
                  <span className="text-sm font-bold text-white">Rango de fechas</span>
                </div>

                {/* Presets */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  {[
                    { label: 'Todo', fn: clearRange, active: !rangeActive },
                    { label: '3M', fn: () => setLastMonths(3) },
                    { label: '6M', fn: () => setLastMonths(6) },
                    { label: '1 año', fn: () => setLastMonths(12) },
                    { label: 'Este año', fn: setThisYear },
                  ].map(p => (
                    <button
                      key={p.label}
                      onClick={p.fn}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${
                        p.active
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                          : 'bg-white/[0.03] text-gray-400 hover:text-white border-white/5 hover:bg-white/[0.06]'
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>

                {/* Manual inputs */}
                <div className="flex items-center gap-2 lg:ml-auto">
                  <input
                    type="date"
                    value={startDate}
                    min={dateBounds.min || undefined}
                    max={endDate || dateBounds.max || undefined}
                    onChange={e => setStartDate(e.target.value)}
                    className="bg-surface-900 border border-white/5 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500/40 [color-scheme:dark]"
                  />
                  <span className="text-gray-600 text-sm">→</span>
                  <input
                    type="date"
                    value={endDate}
                    min={startDate || dateBounds.min || undefined}
                    max={dateBounds.max || undefined}
                    onChange={e => setEndDate(e.target.value)}
                    className="bg-surface-900 border border-white/5 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500/40 [color-scheme:dark]"
                  />
                  {rangeActive && (
                    <button
                      onClick={clearRange}
                      className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
                      title="Quitar filtro"
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
              </div>

              {/* Metric cards (donuts) */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 md:gap-6">
                {ISSUES.map((issue, idx) => {
                  const count = buckets[issue.key].length;
                  const sumAmount = buckets[issue.key].reduce((sum, t) => sum + Math.abs(t.MONTO), 0);
                  const okPct = total === 0 ? 100 : Math.round(((total - count) / total) * 100);
                  const isActive = activeIssue === issue.key;
                  const Icon = issue.icon;
                  return (
                    <button
                      key={issue.key}
                      onClick={() => { setActiveIssue(isActive ? null : issue.key); }}
                      className={`
                        glass-card p-5 md:p-6 rounded-2xl flex items-center gap-4 md:gap-5 text-left transition-all relative overflow-hidden
                        ring-1 ${isActive ? 'ring-2 ring-white/20 bg-white/[0.04]' : 'ring-white/5 hover:bg-white/[0.03]'}
                      `}
                    >
                      {/* Hierarchy rank + severity */}
                      <div className="absolute top-3 right-3 flex items-center gap-1.5">
                        <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${issue.sevColor}`}>
                          {issue.severity}
                        </span>
                        <span className="text-[10px] font-bold text-gray-600 font-mono">#{idx + 1}</span>
                      </div>

                      <div className="relative flex items-center justify-center shrink-0">
                        <Ring pct={okPct} color={issue.ring} />
                        <div className="absolute flex flex-col items-center">
                          <Icon size={18} className={issue.color} />
                          <span className="text-[10px] font-bold text-gray-400 mt-0.5">{okPct}%</span>
                        </div>
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline gap-1.5">
                          <span className={`text-3xl font-bold font-mono leading-none tracking-tight ${count > 0 ? 'text-white' : 'text-emerald-400'}`}>
                            {count}
                          </span>
                          {count > 0 && (
                            <span className="text-xs font-semibold text-gray-500 font-mono">
                              ({((count / total) * 100).toFixed(1)}%)
                            </span>
                          )}
                        </div>
                        <p className="text-xs font-bold uppercase tracking-wider text-gray-400 mt-1.5">{issue.label}</p>
                        <p className="text-[11px] text-gray-600 mt-0.5 flex items-center gap-1.5 flex-wrap">
                          {count > 0 ? (
                            <>
                              <span className="font-mono font-semibold text-gray-400">
                                ${sumAmount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </span>
                              {totalSumAmount > 0 && (
                                <span className="font-mono text-gray-500 text-[10px]">
                                  ({((sumAmount / totalSumAmount) * 100).toFixed(1)}%)
                                </span>
                              )}
                              <span className="text-[9px] text-gray-500">•</span>
                              <span>pendientes</span>
                              <ChevronRight size={12} className="text-gray-500 shrink-0" />
                            </>
                          ) : (
                            'todo listo ✓'
                          )}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Monthly chart */}
              <div className="glass-card p-6 rounded-2xl relative overflow-hidden">
                <div className="flex flex-col md:flex-row md:items-center justify-between mb-4 gap-3">
                  <div>
                    <h3 className="text-lg font-bold text-white tracking-tight">Distribución mensual</h3>
                    <p className="text-xs text-gray-500">
                      {chartMode === 'review'
                        ? '¿Qué tanto reviso cada mes? · aplasta una barra para filtrar'
                        : <>{activeIssue ? ISSUES.find(i => i.key === activeIssue)!.label : 'Todos los problemas'} por mes · aplasta una barra para filtrar</>}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    {selectedMonth && (
                      <button
                        onClick={() => setSelectedMonth(null)}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 text-gray-300 hover:text-white hover:bg-white/10 text-xs font-bold border border-white/5"
                      >
                        {selectedMonth} <X size={14} />
                      </button>
                    )}

                    {/* Mode toggle */}
                    <div className="flex items-center p-1 rounded-xl bg-surface-900/60 border border-white/5">
                      {(['issues', 'review'] as const).map(m => (
                        <button
                          key={m}
                          onClick={() => setChartMode(m)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${chartMode === m ? 'bg-white/10 text-white shadow' : 'text-gray-400 hover:text-white'}`}
                        >
                          {m === 'issues' ? 'Problemas' : 'Revisión'}
                        </button>
                      ))}
                    </div>

                    {/* Unit toggle (only for review mode) */}
                    {chartMode === 'review' && (
                      <div className="flex items-center p-1 rounded-xl bg-surface-900/60 border border-white/5">
                        {(['pct', 'count'] as const).map(u => (
                          <button
                            key={u}
                            onClick={() => setReviewUnit(u)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${reviewUnit === u ? 'bg-emerald-500/20 text-emerald-300 shadow' : 'text-gray-400 hover:text-white'}`}
                          >
                            {u === 'pct' ? '%' : '#'}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <div className="h-[300px]">
                  <VerificationChart
                    data={monthly}
                    activeIssue={activeIssue}
                    selectedMonth={selectedMonth}
                    onSelectMonth={setSelectedMonth}
                    mode={chartMode}
                    reviewUnit={reviewUnit}
                  />
                </div>
              </div>

              {/* Search bar */}
              <div className="flex items-center justify-between gap-4">
                <p className="text-sm text-gray-500">
                  {activeIssue
                    ? <>Mostrando solo <span className="text-white font-bold">{ISSUES.find(i => i.key === activeIssue)!.label}</span></>
                    : 'Secciones por tipo de problema · aplasta una tarjeta arriba para enfocar una'}
                </p>
                <div className="flex items-center gap-2">
                  {activeIssue && (
                    <button
                      onClick={() => setActiveIssue(null)}
                      className="text-xs font-bold text-gray-400 hover:text-white px-3 py-2 rounded-lg hover:bg-white/5 border border-white/5"
                    >
                      Ver todas las secciones
                    </button>
                  )}
                  <div className="relative">
                    <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                    <input
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                      placeholder="Buscar..."
                      className="bg-surface-900 border border-white/5 rounded-xl pl-9 pr-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-primary-500/40 w-48"
                    />
                  </div>
                </div>
              </div>

              {/* Sections per issue */}
              {sections.every(s => s.txs.length === 0) ? (
                <div className="glass-card rounded-2xl py-16 flex flex-col items-center justify-center text-center">
                  <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 mb-4">
                    <CheckCircle2 size={32} className="text-emerald-400" />
                  </div>
                  <p className="text-white font-bold">¡Todo etiquetado!</p>
                  <p className="text-gray-500 text-sm mt-1">No hay movimientos pendientes con este filtro.</p>
                </div>
              ) : (
                sections.map(({ issue, txs }) => {
                  if (txs.length === 0) return null;
                  const isFull = activeIssue === issue.key;
                  const shown = isFull ? txs : txs.slice(0, SECTION_LIMIT);
                  const Icon = issue.icon;
                  const sectionSum = txs.reduce((sum, t) => sum + Math.abs(t.MONTO), 0);
                  return (
                    <div key={issue.key} className="glass-card rounded-2xl overflow-hidden">
                      {/* Section header */}
                      <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
                        <div className="flex items-center gap-3 flex-wrap">
                          <div className={`p-2 rounded-xl bg-white/[0.03] border border-white/5 ${issue.color}`}>
                            <Icon size={18} />
                          </div>
                          <h3 className="text-base font-bold text-white tracking-tight">{issue.label}</h3>
                          <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${issue.sevColor}`}>
                            {issue.severity}
                          </span>
                          <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-white/5 text-gray-300 border border-white/5 flex items-center gap-1.5 flex-wrap">
                            <span>
                              {txs.length} {txs.length === 1 ? 'transacción' : 'transacciones'}{' '}
                              <span className="text-gray-500 font-normal">({((txs.length / total) * 100).toFixed(1)}%)</span>
                            </span>
                            <span className="text-white/20">|</span>
                            <span className="text-emerald-400 font-mono">
                              ${sectionSum.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}{' '}
                              {totalSumAmount > 0 && (
                                <span className="text-emerald-500/70 font-normal text-[10px]">
                                  ({((sectionSum / totalSumAmount) * 100).toFixed(1)}%)
                                </span>
                              )}
                            </span>
                          </span>
                        </div>
                        {!isFull && txs.length > SECTION_LIMIT && (
                          <button
                            onClick={() => setActiveIssue(issue.key)}
                            className="flex items-center gap-1 text-xs font-bold text-gray-400 hover:text-white px-3 py-1.5 rounded-lg hover:bg-white/5"
                          >
                            Ver los {txs.length} <ChevronRight size={14} />
                          </button>
                        )}
                      </div>

                      {/* Rows */}
                      <div className="divide-y divide-white/[0.04]">
                        {shown.map(t => {
                          const isExpense = t.MONTO < 0;
                          const flags = activeIssuesFor(t);
                          const isSplit = !!(t.subTransactions && t.subTransactions.length > 1);
                          return (
                            <button
                              key={t.id}
                              onClick={() => setEditing(t)}
                              className="w-full flex items-center gap-4 px-6 py-4 hover:bg-white/[0.03] transition-colors text-left group"
                            >
                              <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border border-white/5 ${isExpense ? 'bg-rose-500/10 text-rose-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
                                {isExpense ? <ArrowDownLeft size={18} /> : <ArrowUpRight size={18} />}
                              </div>

                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <p className="font-bold text-white truncate">{t.nombre_limpio || t.DESCRIPCION}</p>
                                  {isSplit && (
                                    <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-primary-300 bg-primary-500/10 px-1.5 py-0.5 rounded border border-primary-500/20">
                                      <Scissors size={10} /> {t.subTransactions!.length}
                                    </span>
                                  )}
                                </div>
                                <p className="text-xs text-gray-500 truncate">
                                  {(t.FECHA || '').slice(0, 10)} · {t.DESCRIPCION}
                                </p>
                              </div>

                              <div className="hidden sm:flex items-center gap-1.5 shrink-0">
                                {flags.map(f => (
                                  <span key={f.key} className={`text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-md border border-white/5 bg-white/[0.03] ${f.color}`}>
                                    {f.short}
                                  </span>
                                ))}
                              </div>

                              <div className={`font-mono font-bold text-right shrink-0 w-24 ${isExpense ? 'text-white' : 'text-emerald-400'}`}>
                                {isExpense ? '-' : '+'}${Math.abs(t.MONTO).toFixed(2)}
                              </div>

                              <ChevronRight size={18} className="text-gray-600 group-hover:text-white transition-colors shrink-0" />
                            </button>
                          );
                        })}
                      </div>

                      {!isFull && txs.length > SECTION_LIMIT && (
                        <button
                          onClick={() => setActiveIssue(issue.key)}
                          className="w-full py-3 text-xs font-bold uppercase tracking-wider text-gray-500 hover:text-white hover:bg-white/[0.03] transition-colors border-t border-white/5"
                        >
                          Ver los {txs.length - SECTION_LIMIT} restantes
                        </button>
                      )}
                    </div>
                  );
                })
              )}
            </>
          )}
        </div>
      </div>

      {/* Edit Modal */}
      <EditModal
        transaction={editing}
        isOpen={!!editing}
        onClose={() => setEditing(null)}
        onSave={handleSave}
        categories={[]}
        existingTags={existingTags || []}
      />
    </div>
  );
}
