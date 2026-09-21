import { useMemo, useState, useEffect } from 'react';
import { Search, Filter, Wallet, Calendar, BarChart3, User, ArrowRight, Check, CheckCircle2, Clock, Link2, Link as LinkIcon, Unlink, MousePointerClick, Scale, Layers, Scissors, X, Banknote, Sparkles } from 'lucide-react';
import { useRefundableTransactions, useSupabaseDebts, useSupabasePayments, useUpdateTransaction, useTags, useDeudasPorDevengar } from '../hooks/useTransactions';
import { DebtsChart } from '../components/DebtsChart';
import { EditModal } from '../components/EditModal';
import { AccountStatementModal } from '../components/AccountStatementModal';
import { DevengoModal } from '../components/DevengoModal';
import type { Transaction, SupabaseDebt, SupabasePayment, TransactionUpdate } from '../services/api';
import { buildTimeline, localKind, type DebtItem, type Granularity, type ItemKind } from '../utils/debtTimeline';
import { fmt, money } from '../utils/format';

export function Debts() {
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState<{ startDate?: string; endDate?: string; debtor?: string }>({});
  const [showChart, setShowChart] = useState(false);
  const [showAccount, setShowAccount] = useState(false);
  const [granularity, setGranularity] = useState<Granularity>('month');
  const [onlyMatches, setOnlyMatches] = useState(false);
  const [hoveredMatch, setHoveredMatch] = useState<number | null>(null);
  const [showPayments, setShowPayments] = useState(true);

  // Vinculación manual: selección de un lado local y uno de Supabase
  const [selLocal, setSelLocal] = useState<{ key: string; txId: string } | null>(null);
  const [selSupa, setSelSupa] = useState<{ key: string; debtId: string; kind: ItemKind } | null>(null);
  const updateTx = useUpdateTransaction();

  // Modal de etiquetado (clic normal en una transacción local)
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);

  // Devengo: una deuda mía que pagó otro también puede ser un gasto.
  const [devengando, setDevengando] = useState<SupabaseDebt | null>(null);
  const { data: deudasDevengo } = useDeudasPorDevengar();
  const [showBandeja, setShowBandeja] = useState(false);
  const sinDecidir = useMemo(() => (deudasDevengo ?? []).filter(d => !d.devengada), [deudasDevengo]);
  // Qué deudas mías ya tienen etiqueta, para pintarlas distinto sin volver a pedirlas.
  const devengadasPorId = useMemo(
    () => new Map((deudasDevengo ?? []).filter(d => d.devengada).map(d => [String(d.ID), d])),
    [deudasDevengo],
  );
  const conTransaccion = useMemo(
    () => new Set((deudasDevengo ?? []).filter(d => d.tiene_transaccion).map(d => String(d.ID))),
    [deudasDevengo],
  );
  const { data: existingTags } = useTags();
  const handleSaveLabel = (id: string, updates: TransactionUpdate) => {
    updateTx.mutate({ id, updates });
  };

  // Left Side Data (Local Refundables)
  const { data: transactions, isLoading: isLoadingLeft } = useRefundableTransactions(filters);
  const uniqueDebtors = Array.from(new Set(transactions?.map(t => t.deudor).filter(Boolean) as string[])).sort();

  // Right Side Data (Supabase Debts)
  const { data: supabaseDebts, isLoading: isLoadingRight } = useSupabaseDebts({
    startDate: filters.startDate,
    endDate: filters.endDate,
    debtor: filters.debtor,
  });

  // Right Side Data (Supabase Payments)
  const { data: supabasePayments, isLoading: isLoadingPayments } = useSupabasePayments({
    startDate: filters.startDate,
    endDate: filters.endDate,
    debtor: filters.debtor,
  });

  const handleDateChange = (type: 'start' | 'end', value: string) => {
    setFilters(prev => ({ ...prev, [type === 'start' ? 'startDate' : 'endDate']: value || undefined }));
  };

  // Client-side search filter (applied before grouping)
  const { bands, reconciliation, items } = useMemo(() => {
    const q = searchTerm.toLowerCase();
    const matchesSearch = (title: string, description: string, debtor: string) =>
      !q ||
      title.toLowerCase().includes(q) ||
      description.toLowerCase().includes(q) ||
      debtor.toLowerCase().includes(q);

    const tx = transactions?.filter(t =>
      matchesSearch(t.nombre_limpio || '', t.DESCRIPCION, t.deudor || '') &&
      (showPayments || localKind(t, t.MONTO) === 'deuda'),
    );
    const debts = supabaseDebts?.filter(d =>
      matchesSearch(d.DESCRIPCION, d.DESCRIPCION, d.DEUDOR_NOMBRE || ''),
    );
    const payments = showPayments
      ? supabasePayments?.filter(p =>
          matchesSearch(p.deudor_nombre || '', (p.deudas ?? []).map(d => d.titulo).join(' '), p.deudor_nombre || ''),
        )
      : undefined;

    return buildTimeline(tx, debts, granularity, payments);
  }, [transactions, supabaseDebts, supabasePayments, searchTerm, granularity, showPayments]);

  const isLoading = isLoadingLeft || isLoadingRight || (showPayments && isLoadingPayments);

  // Cuando hay un local y un Supabase seleccionados → vincular (guardar deuda_id o pago_id;
  // una transacción nunca queda atada a las dos cosas)
  useEffect(() => {
    if (selLocal && selSupa && !updateTx.isPending) {
      const updates = selSupa.kind === 'pago'
        ? { pago_id: selSupa.debtId, deuda_id: '' }
        : { deuda_id: selSupa.debtId, pago_id: '' };
      updateTx.mutate(
        { id: selLocal.txId, updates },
        { onSettled: () => { setSelLocal(null); setSelSupa(null); } },
      );
    }
  }, [selLocal, selSupa]); // eslint-disable-line react-hooks/exhaustive-deps

  // Checkbox → seleccionar para vincular
  const handleToggleSelect = (item: DebtItem) => {
    if (item.linked) return;
    if (item.side === 'local') {
      const txId = (item.raw as Transaction).id;
      setSelLocal(prev => (prev?.key === item.key ? null : { key: item.key, txId }));
    } else {
      const debtId = item.kind === 'pago'
        ? String((item.raw as SupabasePayment).id)
        : String((item.raw as SupabaseDebt).ID);
      setSelSupa(prev => (prev?.key === item.key ? null : { key: item.key, debtId, kind: item.kind }));
    }
  };

  // Clic normal en el cuerpo → abrir el modal de etiquetado (solo transacciones locales)
  const handleOpenModal = (item: DebtItem) => {
    if (item.side === 'local') { setEditingTransaction(item.raw as Transaction); return; }
    // Una deuda mía no tiene transacción que etiquetar: se etiqueta ella misma.
    if (item.kind === 'deuda' && item.esMiDeuda) setDevengando(item.raw as SupabaseDebt);
  };

  const handleUnlink = (item: DebtItem) => {
    // Encontrar la transacción local del par (para limpiar su deuda_id)
    const localPart = item.side === 'local'
      ? item
      : items.find(i => i.side === 'local' && i.linkId === item.linkId);
    if (!localPart) return;
    const txId = (localPart.raw as Transaction).id;
    updateTx.mutate({ id: txId, updates: { deuda_id: '', pago_id: '' } });
  };

  const clearSelection = () => { setSelLocal(null); setSelSupa(null); };
  const selecting = !!(selLocal || selSupa);

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

              {/* Pagos toggle */}
              <button
                onClick={() => setShowPayments(v => !v)}
                aria-pressed={showPayments}
                className={`px-3.5 py-2.5 rounded-xl border transition-all shadow-lg active:scale-95 flex items-center gap-2 text-sm font-semibold ${
                  showPayments
                    ? 'bg-sky-500/15 border-sky-500/40 text-sky-300'
                    : 'bg-surface-900 border-white/10 text-surface-300 hover:text-white hover:border-sky-500/30'
                }`}
                title="Mostrar los pagos de la app y los cobros etiquetados"
              >
                <Banknote size={18} />
                <span>Pagos</span>
              </button>

              {/* Solo coincidencias toggle */}
              <button
                onClick={() => setOnlyMatches(v => !v)}
                className={`px-3.5 py-2.5 rounded-xl border transition-all shadow-lg active:scale-95 flex items-center gap-2 text-sm font-semibold ${
                  onlyMatches
                    ? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
                    : 'bg-surface-900 border-white/10 text-surface-300 hover:text-white hover:border-amber-500/30'
                }`}
                title="Mostrar solo transacciones emparejadas con una deuda de Supabase"
              >
                <Link2 size={18} />
                <span>Solo coincidencias</span>
              </button>

              {/* Bandeja: deudas mías que nadie decidió si fueron gasto */}
              {sinDecidir.length > 0 && (
                <div className="relative">
                  <button
                    onClick={() => setShowBandeja(v => !v)}
                    title="Deudas que pagaron por ti y todavía no cuentan como gasto tuyo"
                    className={`px-3.5 py-2.5 rounded-xl border transition-all shadow-lg active:scale-95 flex items-center gap-2 text-sm font-semibold ${
                      showBandeja
                        ? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
                        : 'bg-surface-900 border-white/10 text-surface-300 hover:text-white hover:border-amber-500/30'
                    }`}
                  >
                    <Sparkles size={18} />
                    <span>Sin contar</span>
                    <span className="font-mono text-xs bg-amber-500/20 text-amber-300 px-1.5 rounded">{sinDecidir.length}</span>
                  </button>

                  {showBandeja && (
                    <>
                      <div className="fixed inset-0 z-30" onClick={() => setShowBandeja(false)} />
                      <div className="absolute right-0 top-full mt-2 z-40 w-80 max-h-96 overflow-y-auto rounded-2xl border border-white/10 bg-surface-900 shadow-2xl custom-scrollbar">
                        <div className="sticky top-0 px-4 py-3 border-b border-white/5 bg-surface-900">
                          <p className="text-xs font-bold uppercase tracking-wider text-amber-300">Pagaron por ti</p>
                          <p className="text-[11px] text-surface-500 mt-0.5">
                            Todavía no cuentan como gasto tuyo. Decide una por una.
                          </p>
                        </div>
                        {sinDecidir.map(d => (
                          <button
                            key={d.ID}
                            onClick={() => {
                              // La bandeja no depende del filtro de fechas del timeline, así
                              // que la deuda puede no estar en `supabaseDebts`: se arma con
                              // lo que ya trajo la bandeja.
                              setDevengando(supabaseDebts?.find(x => String(x.ID) === String(d.ID)) ?? {
                                ID: d.ID, FECHA: d.FECHA, DESCRIPCION: d.DESCRIPCION, MONTO: d.MONTO,
                                TIPO: 'DEUDA', DEUDOR_NOMBRE: d.DEUDOR_NOMBRE, PAGADA: d.PAGADA,
                                FECHA_PAGO: null, FECHA_CREACION: d.FECHA, ES_MI_DEUDA: true,
                              });
                              setShowBandeja(false);
                            }}
                            className="w-full px-4 py-2.5 flex items-center gap-3 text-left hover:bg-white/5 transition-colors border-b border-white/5 last:border-0"
                          >
                            <div className="flex-1 min-w-0">
                              <p className="text-sm text-white truncate">{d.DESCRIPCION}</p>
                              <p className="text-[11px] text-surface-500">{d.FECHA} · {d.DEUDOR_NOMBRE}</p>
                            </div>
                            <span className="font-mono text-sm text-surface-300 shrink-0">{money(d.MONTO)}</span>
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}

              <button
                onClick={() => setShowAccount(true)}
                className="group relative px-5 py-2.5 bg-surface-900 hover:bg-surface-800 text-surface-200 hover:text-white rounded-xl border border-white/10 transition-all shadow-lg hover:shadow-emerald-500/20 hover:border-emerald-500/30 active:scale-95 flex items-center gap-2"
              >
                <User size={18} />
                <span className="font-semibold text-sm">Por persona</span>
              </button>

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
            <ReconTile label="Total Local" value={`$${fmt(reconciliation.totalLocal)}`} tone="indigo" sub="deudas" />
            <ReconTile label="Total Supabase" value={`$${fmt(reconciliation.totalSupabase)}`} tone="emerald" sub="por cobrar" />
            <ReconTile
              label="Diferencia"
              value={`${reconciliation.diff >= 0 ? '+' : '−'}$${fmt(Math.abs(reconciliation.diff))}`}
              tone={Math.abs(reconciliation.diff) < 0.01 ? 'emerald' : 'amber'}
              icon={<Scale size={14} />}
            />
            <div className="flex flex-col justify-center gap-1.5 rounded-2xl bg-surface-900/40 border border-white/10 px-4 py-3">
              <div className="flex items-center gap-3 text-[11px] font-semibold">
                <span className="flex items-center gap-1 text-emerald-300"><LinkIcon size={12} />{reconciliation.countLinked} vinculados</span>
                <span className="text-surface-600">·</span>
                <span className="flex items-center gap-1 text-amber-300"><Link2 size={12} />{reconciliation.countMatched} coincidentes</span>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-surface-400">
                <span>{reconciliation.countOnlyLocal} solo local</span>
                <span className="text-surface-600">·</span>
                <span>{reconciliation.countOnlySupabase} solo Supabase</span>
              </div>
            </div>
          </div>

          {showPayments && reconciliation.countPagos > 0 && (
            <div className="w-full grid grid-cols-1 sm:grid-cols-3 gap-3">
              <ReconTile label="Pagos locales" value={`${reconciliation.pagosLocal >= 0 ? '+' : '−'}$${fmt(Math.abs(reconciliation.pagosLocal))}`} tone="sky" sub="entró − salió en las transacciones" icon={<Banknote size={14} />} />
              <ReconTile label="Pagos Supabase" value={`${reconciliation.pagosSupabase >= 0 ? '+' : '−'}$${fmt(Math.abs(reconciliation.pagosSupabase))}`} tone="sky" sub={`${reconciliation.countPagos} pagos · te pagaron − pagaste`} />
              <ReconTile
                label="Diferencia pagos"
                value={`${reconciliation.pagosDiff >= 0 ? '+' : '−'}$${fmt(Math.abs(reconciliation.pagosDiff))}`}
                tone={Math.abs(reconciliation.pagosDiff) < 0.01 ? 'emerald' : 'amber'}
                sub="efectivo o sin etiquetar"
                icon={<Scale size={14} />}
              />
            </div>
          )}

          {/* Selection helper / linking bar */}
          <div className={`flex items-center gap-3 rounded-xl border px-4 py-2.5 text-sm transition-all ${
            selecting
              ? 'bg-indigo-500/10 border-indigo-500/40 text-indigo-100'
              : 'bg-surface-900/40 border-white/5 text-surface-400'
          }`}>
            <MousePointerClick size={16} className={selecting ? 'text-indigo-300' : 'text-surface-500'} />
            {updateTx.isPending ? (
              <span className="flex items-center gap-2"><span className="w-3.5 h-3.5 border-2 border-indigo-400/40 border-t-indigo-400 rounded-full animate-spin" /> Guardando vínculo…</span>
            ) : selecting ? (
              <>
                <span className="font-medium">
                  {selLocal ? 'Transacción local marcada' : selSupa?.kind === 'pago' ? 'Pago de Supabase marcado' : 'Deuda de Supabase marcada'} — marca el check de {selLocal ? 'una deuda o un pago de Supabase' : 'una transacción local'} para vincular.
                </span>
                <button onClick={clearSelection} className="ml-auto flex items-center gap-1 text-xs font-semibold text-surface-400 hover:text-white transition-colors">
                  <X size={13} /> Cancelar
                </button>
              </>
            ) : (
              <span>Marca el <span className="text-indigo-300 font-medium">check</span> de una transacción local y una deuda o un pago de Supabase para vincularlas. El clic normal abre el <span className="text-emerald-300 font-medium">etiquetado</span>.</span>
            )}
          </div>
        </div>

        {/* SINGLE SCROLL TIMELINE */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-4 md:px-8 pb-8">
          {/* Column headers (labels for each half) */}
          <div className="hidden lg:grid grid-cols-2 gap-0 sticky top-0 z-30 bg-surface-950/80 backdrop-blur-md">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5">
              <div className="p-1.5 bg-indigo-500/10 rounded-lg text-indigo-400"><ArrowRight size={14} /></div>
              <span className="text-xs font-bold text-white uppercase tracking-wide">Pendientes Locales</span>
              <span className="text-[10px] text-surface-500">reembolsos{showPayments ? ' y cobros' : ''} etiquetados</span>
            </div>
            <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5 border-l border-white/5">
              <div className="p-1.5 bg-emerald-500/10 rounded-lg text-emerald-400"><CheckCircle2 size={14} /></div>
              <span className="text-xs font-bold text-white uppercase tracking-wide">Histórico Supabase</span>
              <span className="text-[10px] text-surface-500">deudas{showPayments ? ' y pagos' : ''} de la app</span>
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
              {bands.map(band => {
                const left = onlyMatches ? band.left.filter(i => i.matchId !== undefined || i.linked) : band.left;
                const right = onlyMatches ? band.right.filter(i => i.matchId !== undefined || i.linked) : band.right;
                if (onlyMatches && left.length === 0 && right.length === 0) return null;
                return (
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
                      {left.length === 0 ? (
                        <EmptySide />
                      ) : (
                        left.map(item => (
                          <DebtCard
                            key={item.key}
                            item={item}
                            hoveredMatch={hoveredMatch}
                            onHover={setHoveredMatch}
                            selected={selLocal?.key === item.key || selSupa?.key === item.key}
                            devengada={item.side === 'supabase' && item.kind === 'deuda'
                              && devengadasPorId.has(String((item.raw as SupabaseDebt).ID))}
                            onToggleSelect={() => handleToggleSelect(item)}
                            onOpen={() => handleOpenModal(item)}
                            onUnlink={() => handleUnlink(item)}
                          />
                        ))
                      )}
                    </div>
                    <div className="flex flex-col gap-2.5 lg:pl-4">
                      {right.length === 0 ? (
                        <EmptySide />
                      ) : (
                        right.map(item => (
                          <DebtCard
                            key={item.key}
                            item={item}
                            hoveredMatch={hoveredMatch}
                            onHover={setHoveredMatch}
                            selected={selLocal?.key === item.key || selSupa?.key === item.key}
                            devengada={item.side === 'supabase' && item.kind === 'deuda'
                              && devengadasPorId.has(String((item.raw as SupabaseDebt).ID))}
                            onToggleSelect={() => handleToggleSelect(item)}
                            onOpen={() => handleOpenModal(item)}
                            onUnlink={() => handleUnlink(item)}
                          />
                        ))
                      )}
                    </div>
                  </div>
                </section>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {showChart && <DebtsChart onClose={() => setShowChart(false)} />}
      {showAccount && <AccountStatementModal onClose={() => setShowAccount(false)} />}

      {devengando && (
        <DevengoModal
          deuda={devengando}
          devengada={devengadasPorId.get(String(devengando.ID)) ?? null}
          tieneTransaccion={conTransaccion.has(String(devengando.ID))}
          onClose={() => setDevengando(null)}
        />
      )}

      <EditModal
        transaction={editingTransaction}
        isOpen={!!editingTransaction}
        onClose={() => setEditingTransaction(null)}
        onSave={handleSaveLabel}
        categories={[]}
        existingTags={existingTags || []}
      />
    </div>
  );
}

function ReconTile({ label, value, tone, sub, icon }: {
  label: string;
  value: string;
  tone: 'indigo' | 'emerald' | 'amber' | 'sky';
  sub?: string;
  icon?: React.ReactNode;
}) {
  const toneMap = {
    sky: 'text-sky-400',
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

function DebtCard({ item, hoveredMatch, onHover, selected, devengada, onToggleSelect, onOpen, onUnlink }: {
  item: DebtItem;
  hoveredMatch: number | null;
  onHover: (m: number | null) => void;
  selected?: boolean;
  /** Solo deudas mías: ya está contada como gasto. */
  devengada?: boolean;
  onToggleSelect?: () => void;
  onOpen?: () => void;
  onUnlink?: () => void;
}) {
  const isLocal = item.side === 'local';
  const matched = item.matchId !== undefined;
  const linked = !!item.linked;
  const isPago = item.kind === 'pago';
  const paidDebt = item.side === 'supabase' && !isPago && item.paid;
  const isHighlighted = matched && item.matchId === hoveredMatch;
  // Las locales abren el etiquetado normal. Una deuda mía no tiene transacción
  // detrás, así que abre el devengo: se etiqueta la deuda misma.
  const esDeudaMia = item.side === 'supabase' && !isPago && !!item.esMiDeuda;
  const clickableBody = (isLocal && !linked) || esDeudaMia;

  const baseClass = linked
    ? 'border-emerald-400/70 bg-emerald-500/[0.12] ring-1 ring-emerald-400/40'
    : selected
      ? 'border-indigo-400 bg-indigo-500/[0.12] ring-2 ring-indigo-400/60'
      : isHighlighted
        ? 'border-amber-400 bg-amber-500/[0.12] ring-2 ring-amber-400/50'
        : matched
          ? 'border-amber-500/40 bg-amber-500/[0.04] hover:bg-amber-500/[0.07]'
          : paidDebt
            ? 'bg-surface-900/20 border-white/5 opacity-60 hover:opacity-100'
            : isPago
              ? 'bg-sky-500/[0.04] border-sky-500/15 hover:border-sky-500/35 hover:bg-surface-800/60'
              : isLocal
                ? 'bg-surface-900/40 border-white/5 hover:border-indigo-500/30 hover:bg-surface-800/60'
                : 'bg-surface-900/40 border-white/5 hover:border-emerald-500/30 hover:bg-surface-800/60';

  return (
    <div
      className={`group relative p-3.5 ${linked ? '' : 'pl-11'} rounded-2xl border transition-all overflow-hidden ${baseClass} ${clickableBody ? 'cursor-pointer' : ''}`}
      title={esDeudaMia ? (devengada ? 'Clic para editar el gasto' : 'Clic para contarla como gasto') : clickableBody ? 'Clic para etiquetar' : undefined}
      onClick={clickableBody ? onOpen : undefined}
      onMouseEnter={matched ? () => onHover(item.matchId!) : undefined}
      onMouseLeave={matched ? () => onHover(null) : undefined}
    >
      {/* Checkbox de selección para vincular (no en los ya vinculados) */}
      {!linked && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onToggleSelect?.(); }}
          title="Seleccionar para vincular"
          className={`absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 rounded-md border flex items-center justify-center transition-all z-20 ${
            selected
              ? 'bg-indigo-500 border-indigo-400 text-white'
              : 'bg-surface-950/60 border-white/20 text-transparent hover:border-indigo-400/60'
          }`}
        >
          <Check size={13} className="stroke-[3]" />
        </button>
      )}
      {linked && (
        <span className="absolute top-2 right-2 flex items-center gap-1 text-[9px] font-bold text-emerald-200 bg-emerald-500/20 border border-emerald-400/30 pl-1.5 pr-1 py-0.5 rounded-md">
          <LinkIcon size={9} /> VINCULADO
          <button
            onClick={(e) => { e.stopPropagation(); onUnlink?.(); }}
            className="ml-0.5 p-0.5 rounded hover:bg-emerald-400/20 text-emerald-200/80 hover:text-white transition-colors"
            title="Desvincular"
          >
            <Unlink size={9} />
          </button>
        </span>
      )}
      {!linked && matched && (
        <span className="absolute top-2 right-2 flex items-center gap-1 text-[9px] font-bold text-amber-300/90 bg-amber-500/10 px-1.5 py-0.5 rounded-md">
          <Link2 size={9} /> MATCH #{item.matchId}
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
            {isPago && (
              <span className="flex items-center gap-1 shrink-0 text-[9px] font-bold text-sky-300 bg-sky-500/10 border border-sky-500/20 px-1.5 py-0.5 rounded-md uppercase tracking-wide">
                <Banknote size={9} /> pago
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
            {isPago && !isLocal && (item.raw as SupabasePayment).deudas?.length ? (
              <span className="truncate max-w-[14rem]" title={(item.raw as SupabasePayment).deudas!.map(d => d.titulo).join(', ')}>
                abonó: {(item.raw as SupabasePayment).deudas!.map(d => d.titulo).join(', ')}
              </span>
            ) : null}
            {paidDebt && item.paidDate && (
              <span className="flex items-center gap-1 text-emerald-400/80">
                <Clock size={11} />
                Pagado: {new Date(item.paidDate.includes(' ') || item.paidDate.includes('T') ? item.paidDate.replace(' ', 'T') : `${item.paidDate}T00:00:00`).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className={`text-base font-mono font-bold ${paidDebt ? 'text-surface-500' : 'text-white'}`}>
            {money(item.amount)}
          </div>
          {isPago ? (
            <span className="text-[10px] font-bold text-sky-300 bg-sky-500/10 px-1.5 py-0.5 rounded mt-1 inline-block">
              {isLocal
                ? (item.amount >= 0 ? 'COBRO' : 'PAGO')
                : item.esMiPago ? 'ENTREGADO' : 'RECIBIDO'}
            </span>
          ) : item.side === 'supabase' ? (
            <div className="flex flex-col items-end gap-1 mt-1">
              <div className={`text-[10px] font-bold px-1.5 py-0.5 rounded inline-flex items-center gap-1 ${
                item.paid ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'
              }`}>
                {item.paid ? (<><CheckCircle2 size={10} /> PAGADA</>) : 'PENDIENTE'}
              </div>
              {esDeudaMia && (
                <div
                  title={devengada ? 'Cuenta como gasto tuyo' : 'La pagó otro y todavía no cuenta como gasto tuyo'}
                  className={`text-[10px] font-bold px-1.5 py-0.5 rounded inline-flex items-center gap-1 ${
                    devengada ? 'text-amber-300 bg-amber-500/15' : 'text-surface-500 bg-white/5'
                  }`}
                >
                  <Sparkles size={10} />
                  {devengada ? 'ES GASTO' : 'SIN CONTAR'}
                </div>
              )}
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
