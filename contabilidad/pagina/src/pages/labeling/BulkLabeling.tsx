import { useMemo, useState } from 'react';
import {
  useCategories,
  useTags,
  useFilteredTransactions,
  useBulkUpdate,
  useUndoBulkUpdate,
} from '../../hooks/useTransactions';
import {
  BulkUpdateResponse,
  Transaction,
  TransactionFilters,
  TransactionUpdate,
} from '../../services/api';
import {
  AlertTriangle,
  Check,
  CheckCheck,
  Filter,
  Flame,
  Heart,
  Layers,
  Loader2,
  RotateCcw,
  Search,
  Sparkles,
  Square,
  Undo2,
  X,
} from 'lucide-react';

// ── Field definitions ────────────────────────────────────────────────────────
// Each field the bulk panel can write. `key` matches TransactionUpdate.
type FieldKey = 'categoria' | 'prioridad' | 'tags' | 'es_fijo' | 'felicidad' | 'nota' | 'revisado';

const FIELD_LABELS: Record<FieldKey, string> = {
  categoria: 'Categoría',
  prioridad: 'Prioridad',
  tags: 'Tags',
  es_fijo: 'Gasto fijo',
  felicidad: 'Felicidad',
  nota: 'Nota',
  revisado: 'Revisado',
};

const EMPTY_VALUES = ['', '---', 'nan', 'None', 'Sin Categoría'];

// Mirror of is_empty_label() in transaction_service.py: for these fields the
// "off" value means never labeled, so it is safe to fill without overwriting.
const FALSY_AS_EMPTY = ['es_fijo', 'revisado', 'es_reembolsable', 'felicidad'];

function isEmptyValue(val: unknown, field?: string): boolean {
  if (val === null || val === undefined) return true;
  if (field && FALSY_AS_EMPTY.includes(field) && !val) return true;
  if (typeof val === 'number') return false;
  if (typeof val === 'boolean') return false;
  return EMPTY_VALUES.includes(String(val).trim());
}

// Human-readable rendering of a value about to be written.
function describeValue(field: FieldKey, value: any): string {
  if (field === 'es_fijo') return value ? 'Sí' : 'No';
  if (field === 'revisado') return value ? 'Revisado' : 'Pendiente';
  if (field === 'felicidad') return `${value}/9`;
  return String(value || '—');
}

// Date presets, resolved against the current clock.
function datePresets() {
  const now = new Date();
  const y = now.getFullYear();
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return [
    { label: 'Este año', start: `${y}-01-01`, end: iso(now) },
    { label: 'Año pasado', start: `${y - 1}-01-01`, end: `${y - 1}-12-31` },
    { label: 'Este mes', start: iso(new Date(y, now.getMonth(), 1)), end: iso(now) },
    { label: 'Últimos 3 meses', start: iso(new Date(y, now.getMonth() - 2, 1)), end: iso(now) },
    { label: 'Todo', start: '', end: '' },
  ];
}

export function BulkLabeling() {
  // ── Filters ────────────────────────────────────────────────────────────────
  const [filters, setFilters] = useState<TransactionFilters>({
    startDate: `${new Date().getFullYear()}-01-01`,
    endDate: '',
  });
  const [searchInput, setSearchInput] = useState('');
  const [showFilters, setShowFilters] = useState(true);

  const { data: categories } = useCategories();
  const { data: allTags } = useTags();
  const { data: results, isFetching } = useFilteredTransactions(filters);

  // ── Selection ──────────────────────────────────────────────────────────────
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const transactions = results || [];
  const selected = useMemo(
    () => transactions.filter((t) => selectedIds.has(t.id)),
    [transactions, selectedIds]
  );

  const toggleOne = (id: string) => {
    const next = new Set(selectedIds);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelectedIds(next);
  };

  const selectAll = () => setSelectedIds(new Set(transactions.map((t) => t.id)));
  const clearSelection = () => setSelectedIds(new Set());
  const invertSelection = () =>
    setSelectedIds(new Set(transactions.filter((t) => !selectedIds.has(t.id)).map((t) => t.id)));

  // ── Bulk form ──────────────────────────────────────────────────────────────
  const [isApplyOpen, setIsApplyOpen] = useState(false);
  const [active, setActive] = useState<Set<FieldKey>>(new Set());
  const [values, setValues] = useState<Record<string, any>>({
    categoria: '',
    prioridad: 'Necesidad',
    tags: '',
    es_fijo: false,
    felicidad: 5,
    nota: '',
    revisado: true,
  });
  const [tagsMode, setTagsMode] = useState<'append' | 'replace'>('append');
  const [overwrite, setOverwrite] = useState(false);
  const [saveAsRule, setSaveAsRule] = useState(false);
  const [ruleEntities, setRuleEntities] = useState<Set<string>>(new Set());

  // Result of the last applied operation — drives the summary modal.
  const [result, setResult] = useState<BulkUpdateResponse | null>(null);
  const [resultFields, setResultFields] = useState<TransactionUpdate>({});
  const [undone, setUndone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bulkMutation = useBulkUpdate();
  const undoMutation = useUndoBulkUpdate();

  const toggleField = (key: FieldKey) => {
    const next = new Set(active);
    next.has(key) ? next.delete(key) : next.add(key);
    setActive(next);
  };

  // Distinct clean names in the selection — candidates for an entity rule.
  const selectionEntities = useMemo(() => {
    const names = new Set<string>();
    selected.forEach((t) => {
      if (t.nombre_limpio && !isEmptyValue(t.nombre_limpio)) names.add(t.nombre_limpio);
    });
    return Array.from(names).sort();
  }, [selected]);

  // Conflicts: selected transactions that already hold a different value for an
  // active field. These are the ones skipped unless `overwrite` is on.
  const conflicts = useMemo(() => {
    const out: { field: FieldKey; count: number; samples: string[] }[] = [];
    active.forEach((field) => {
      if (field === 'tags' && tagsMode === 'append') return; // append never conflicts
      const clashing = selected.filter((t) => {
        const current = (t as any)[field];
        return !isEmptyValue(current, field) && String(current) !== String(values[field]);
      });
      if (clashing.length) {
        const samples = Array.from(new Set(clashing.map((t) => String((t as any)[field])))).slice(0, 4);
        out.push({ field, count: clashing.length, samples });
      }
    });
    return out;
  }, [active, selected, values, tagsMode]);

  const handleApply = () => {
    if (!selected.length || !active.size) return;

    const updates: Record<string, any> = {};
    active.forEach((field) => {
      updates[field] = values[field];
    });

    bulkMutation.mutate(
      {
        transactionIds: selected.map((t) => t.id),
        updates: updates as TransactionUpdate,
        overwrite,
        tagsMode,
        saveAsRule,
        ruleEntities: saveAsRule ? Array.from(ruleEntities) : [],
        ruleTags: saveAsRule && filters.tag ? [filters.tag] : [],
      },
      {
        onSuccess: (res) => {
          setResult(res);
          setResultFields(updates as TransactionUpdate);
          setUndone(false);
          setIsApplyOpen(false);
          clearSelection();
        },
        onError: (err: any) => setError(err?.message ?? 'Error desconocido'),
      }
    );
  };

  const handleUndo = () => {
    if (!result?.undo_id) return;
    undoMutation.mutate(result.undo_id, {
      onSuccess: () => setUndone(true),
      onError: (err: any) => setError(err?.response?.data?.detail ?? err?.message ?? 'Error al deshacer'),
    });
  };

  const selectedTotal = selected.reduce((sum, t) => sum + (t.MONTO || 0), 0);
  const activeFilterCount = [
    filters.category,
    filters.tag,
    filters.search,
    filters.sourceType,
    filters.pendingOnly ? 'p' : '',
  ].filter(Boolean).length;

  return (
    <div className="flex-1 overflow-y-auto px-4 md:px-8 pb-8 custom-scrollbar">
      <div className="max-w-[1700px] mx-auto space-y-5 mt-4">
        {/* ── Action bar ──────────────────────────────────────────────────── */}
        <div className="sticky top-0 z-30 -mx-2 px-2 py-2">
          <div className="glass px-5 py-3.5 rounded-2xl flex items-center justify-between gap-4 flex-wrap shadow-2xl ring-1 ring-white/10 bg-slate-900/80 backdrop-blur-xl">
            <div className="flex items-center gap-3 flex-wrap">
              <button
                onClick={selectAll}
                className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs font-bold text-gray-300 flex items-center gap-1.5 transition-colors"
              >
                <CheckCheck size={14} /> Todo
              </button>
              <button
                onClick={invertSelection}
                className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs font-bold text-gray-300 transition-colors"
              >
                Invertir
              </button>
              <button
                onClick={clearSelection}
                className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs font-bold text-gray-300 flex items-center gap-1.5 transition-colors"
              >
                <Square size={14} /> Ninguno
              </button>

              <div className="h-6 w-px bg-white/10 mx-1"></div>

              <button
                onClick={() => setShowFilters((v) => !v)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors border ${
                  showFilters
                    ? 'bg-blue-500/15 text-blue-200 border-blue-500/30'
                    : 'bg-white/5 text-gray-300 border-white/5 hover:bg-white/10'
                }`}
              >
                <Filter size={14} /> Filtros
                {activeFilterCount > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-blue-500/30 text-[10px]">{activeFilterCount}</span>
                )}
              </button>

              {isFetching && <Loader2 size={16} className="animate-spin text-blue-400" />}
            </div>

            <div className="flex items-center gap-4">
              <div className="text-xs text-right hidden sm:block">
                <div className="text-white font-bold">
                  {selected.length} <span className="text-gray-500 font-medium">de {transactions.length}</span>
                </div>
                <div className="text-gray-500 font-mono">${selectedTotal.toFixed(2)}</div>
              </div>

              <button
                onClick={() => setIsApplyOpen(true)}
                disabled={!selected.length}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 text-white font-bold text-sm tracking-wide disabled:opacity-30 disabled:cursor-not-allowed hover:shadow-[0_0_25px_rgba(16,185,129,0.35)] transition-all active:scale-95 flex items-center gap-2"
              >
                <Layers size={16} />
                Etiquetar {selected.length ? `(${selected.length})` : ''}
              </button>
            </div>
          </div>
        </div>

        {/* ── Filters ─────────────────────────────────────────────────────── */}
        {showFilters && (
          <div className="glass-card p-6 relative overflow-hidden animate-in fade-in slide-in-from-top-2 duration-300">
            <div className="absolute top-0 right-0 w-96 h-96 bg-blue-500/5 rounded-full blur-[100px] pointer-events-none"></div>

            <div className="flex flex-wrap gap-2 mb-5 relative z-10">
              {datePresets().map((p) => {
                const isActive = filters.startDate === p.start && filters.endDate === p.end;
                return (
                  <button
                    key={p.label}
                    onClick={() => setFilters({ ...filters, startDate: p.start, endDate: p.end })}
                    className={`px-4 py-1.5 rounded-xl text-xs font-bold transition-all border ${
                      isActive
                        ? 'bg-blue-500/20 text-blue-200 border-blue-500/40'
                        : 'bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-white'
                    }`}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4 relative z-10">
              <label className="flex flex-col gap-1.5">
                <span className="text-[10px] uppercase font-bold tracking-widest text-gray-500">Desde</span>
                <input
                  type="date"
                  value={filters.startDate || ''}
                  onChange={(e) => setFilters({ ...filters, startDate: e.target.value })}
                  className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:border-blue-500/50 outline-none"
                />
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-[10px] uppercase font-bold tracking-widest text-gray-500">Hasta</span>
                <input
                  type="date"
                  value={filters.endDate || ''}
                  onChange={(e) => setFilters({ ...filters, endDate: e.target.value })}
                  className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:border-blue-500/50 outline-none"
                />
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-[10px] uppercase font-bold tracking-widest text-gray-500">Categoría</span>
                <select
                  value={filters.category || ''}
                  onChange={(e) => setFilters({ ...filters, category: e.target.value || undefined })}
                  className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:border-blue-500/50 outline-none"
                >
                  <option value="" className="bg-slate-900">Todas</option>
                  {(categories || []).map((c) => (
                    <option key={c} value={c} className="bg-slate-900">{c}</option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-[10px] uppercase font-bold tracking-widest text-gray-500">Tag</span>
                <select
                  value={filters.tag || ''}
                  onChange={(e) => setFilters({ ...filters, tag: e.target.value || undefined })}
                  className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:border-blue-500/50 outline-none"
                >
                  <option value="" className="bg-slate-900">Todos</option>
                  {(allTags || []).map((t) => (
                    <option key={t} value={t} className="bg-slate-900">{t}</option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-[10px] uppercase font-bold tracking-widest text-gray-500">Fuente</span>
                <select
                  value={filters.sourceType || ''}
                  onChange={(e) => setFilters({ ...filters, sourceType: (e.target.value || undefined) as any })}
                  className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:border-blue-500/50 outline-none"
                >
                  <option value="" className="bg-slate-900">Todas</option>
                  <option value="BANCA" className="bg-slate-900">Banca</option>
                  <option value="TARJETA" className="bg-slate-900">Tarjeta</option>
                </select>
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-[10px] uppercase font-bold tracking-widest text-gray-500">Buscar</span>
                <div className="flex gap-2">
                  <input
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') setFilters({ ...filters, search: searchInput || undefined });
                    }}
                    placeholder="Texto…"
                    className="flex-1 min-w-0 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:border-blue-500/50 outline-none"
                  />
                  <button
                    onClick={() => setFilters({ ...filters, search: searchInput || undefined })}
                    className="px-3 rounded-xl bg-blue-500/20 text-blue-300 hover:bg-blue-500 hover:text-white transition-colors"
                  >
                    <Search size={16} />
                  </button>
                </div>
              </label>
            </div>

            <label className="flex items-center gap-2 mt-4 text-sm text-gray-400 cursor-pointer relative z-10 w-fit">
              <input
                type="checkbox"
                checked={!!filters.pendingOnly}
                onChange={(e) => setFilters({ ...filters, pendingOnly: e.target.checked })}
                className="accent-blue-500 w-4 h-4"
              />
              Solo pendientes de revisar
            </label>
          </div>
        )}

        {error && (
          <div className="px-6 py-3 rounded-2xl text-sm font-bold bg-red-500/10 text-red-200 ring-1 ring-red-500/20 flex items-center justify-between">
            ❌ {error}
            <button onClick={() => setError(null)} className="text-red-300 hover:text-white">
              <X size={16} />
            </button>
          </div>
        )}

        {/* ── Results table ─────────────────────────────────────────────────── */}
        <div className="glass-card flex flex-col overflow-hidden">
          <div className="overflow-auto max-h-[70vh] custom-scrollbar">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-900/95 backdrop-blur-sm z-10">
                <tr className="text-[10px] uppercase tracking-widest text-gray-500">
                  <th className="w-10 px-4 py-3"></th>
                  <th className="text-left px-3 py-3 font-bold">Fecha</th>
                  <th className="text-left px-3 py-3 font-bold">Descripción</th>
                  <th className="text-right px-3 py-3 font-bold">Monto</th>
                  <th className="text-left px-3 py-3 font-bold">Categoría</th>
                  <th className="text-left px-3 py-3 font-bold">Prioridad</th>
                  <th className="text-left px-3 py-3 font-bold">Tags</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((t: Transaction) => {
                  const isSel = selectedIds.has(t.id);
                  return (
                    <tr
                      key={t.id}
                      onClick={() => toggleOne(t.id)}
                      className={`border-t border-white/5 cursor-pointer transition-colors ${
                        isSel ? 'bg-blue-500/10 hover:bg-blue-500/15' : 'hover:bg-white/[0.03]'
                      }`}
                    >
                      <td className="px-4 py-2.5">
                        <div
                          className={`w-4 h-4 rounded border flex items-center justify-center ${
                            isSel ? 'bg-blue-500 border-blue-500' : 'border-white/20'
                          }`}
                        >
                          {isSel && <Check size={12} className="text-white" />}
                        </div>
                      </td>
                      <td className="px-3 py-2.5 text-gray-400 font-mono text-xs whitespace-nowrap">
                        {String(t.FECHA).slice(0, 10)}
                      </td>
                      <td className="px-3 py-2.5 max-w-[320px]">
                        <div className="truncate text-white font-medium">{t.nombre_limpio || t.DESCRIPCION}</div>
                        {t.nombre_limpio && (
                          <div className="truncate text-[10px] text-gray-600">{t.DESCRIPCION}</div>
                        )}
                      </td>
                      <td
                        className={`px-3 py-2.5 text-right font-mono font-bold whitespace-nowrap ${
                          t.MONTO >= 0 ? 'text-emerald-400' : 'text-gray-300'
                        }`}
                      >
                        ${t.MONTO?.toFixed(2)}
                      </td>
                      <td className="px-3 py-2.5 text-gray-400">{t.categoria || '—'}</td>
                      <td className="px-3 py-2.5">
                        {t.prioridad && t.prioridad !== '---' ? (
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                              t.prioridad === 'Necesidad'
                                ? 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                                : 'bg-pink-500/10 text-pink-300 border-pink-500/20'
                            }`}
                          >
                            {t.prioridad}
                          </span>
                        ) : (
                          <span className="text-gray-600">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-gray-500 text-xs max-w-[180px] truncate">{t.tags || '—'}</td>
                    </tr>
                  );
                })}
                {!transactions.length && !isFetching && (
                  <tr>
                    <td colSpan={7} className="text-center py-16 text-gray-600">
                      Sin resultados para estos filtros
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ── Apply modal ───────────────────────────────────────────────────── */}
      {isApplyOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="glass-card w-full max-w-lg max-h-[92vh] flex flex-col overflow-hidden">
            <div className="px-6 py-5 border-b border-white/5 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-gradient-to-br from-emerald-500/10 to-teal-500/10 border border-white/5">
                  <Layers className="text-emerald-400" size={18} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white tracking-tight">Aplicar etiquetas</h3>
                  <p className="text-xs text-gray-500">
                    {selected.length} transacciones · ${selectedTotal.toFixed(2)}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsApplyOpen(false)}
                className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white"
              >
                <X size={18} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar px-6 py-5 space-y-4">
              <p className="text-xs text-gray-500">Activa solo los campos que quieras cambiar.</p>

              {/* Categoría */}
              <FieldBlock label={FIELD_LABELS.categoria} active={active.has('categoria')} onToggle={() => toggleField('categoria')}>
                <input
                  list="bulk-categories"
                  value={values.categoria}
                  onChange={(e) => setValues({ ...values, categoria: e.target.value })}
                  placeholder="Alimentación…"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-emerald-500/50"
                />
                <datalist id="bulk-categories">
                  {(categories || []).map((c) => (
                    <option key={c} value={c} />
                  ))}
                </datalist>
              </FieldBlock>

              {/* Prioridad */}
              <FieldBlock label={FIELD_LABELS.prioridad} active={active.has('prioridad')} onToggle={() => toggleField('prioridad')}>
                <div className="flex gap-2">
                  {(['Necesidad', 'Deseo'] as const).map((p) => (
                    <button
                      key={p}
                      onClick={() => setValues({ ...values, prioridad: p })}
                      className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all ${
                        values.prioridad === p
                          ? p === 'Necesidad'
                            ? 'bg-amber-500/20 text-amber-200 border-amber-500/40'
                            : 'bg-pink-500/20 text-pink-200 border-pink-500/40'
                          : 'bg-white/5 text-gray-500 border-white/10 hover:text-white'
                      }`}
                    >
                      {p === 'Necesidad' ? <Flame size={14} /> : <Heart size={14} />}
                      {p}
                    </button>
                  ))}
                </div>
              </FieldBlock>

              {/* Tags */}
              <FieldBlock label={FIELD_LABELS.tags} active={active.has('tags')} onToggle={() => toggleField('tags')}>
                <input
                  list="bulk-tags"
                  value={values.tags}
                  onChange={(e) => setValues({ ...values, tags: e.target.value })}
                  placeholder="tag1, tag2…"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-emerald-500/50"
                />
                <datalist id="bulk-tags">
                  {(allTags || []).map((t) => (
                    <option key={t} value={t} />
                  ))}
                </datalist>
                <div className="flex gap-2 mt-2">
                  {(['append', 'replace'] as const).map((m) => (
                    <button
                      key={m}
                      onClick={() => setTagsMode(m)}
                      className={`flex-1 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider border transition-all ${
                        tagsMode === m
                          ? 'bg-emerald-500/20 text-emerald-200 border-emerald-500/40'
                          : 'bg-white/5 text-gray-500 border-white/10'
                      }`}
                    >
                      {m === 'append' ? 'Sumar a los existentes' : 'Reemplazar'}
                    </button>
                  ))}
                </div>
              </FieldBlock>

              {/* Gasto fijo */}
              <FieldBlock label={FIELD_LABELS.es_fijo} active={active.has('es_fijo')} onToggle={() => toggleField('es_fijo')}>
                <div className="flex gap-2">
                  {[true, false].map((v) => (
                    <button
                      key={String(v)}
                      onClick={() => setValues({ ...values, es_fijo: v })}
                      className={`flex-1 py-2 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all ${
                        values.es_fijo === v
                          ? 'bg-indigo-500/20 text-indigo-200 border-indigo-500/40'
                          : 'bg-white/5 text-gray-500 border-white/10 hover:text-white'
                      }`}
                    >
                      {v ? 'Sí' : 'No'}
                    </button>
                  ))}
                </div>
              </FieldBlock>

              {/* Felicidad */}
              <FieldBlock label={FIELD_LABELS.felicidad} active={active.has('felicidad')} onToggle={() => toggleField('felicidad')}>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min={0}
                    max={9}
                    value={values.felicidad}
                    onChange={(e) => setValues({ ...values, felicidad: parseInt(e.target.value) })}
                    className="flex-1 accent-emerald-500"
                  />
                  <span className="text-xs font-mono font-bold text-gray-300 bg-white/5 px-2 py-0.5 rounded">
                    {values.felicidad}/9
                  </span>
                </div>
              </FieldBlock>

              {/* Nota */}
              <FieldBlock label={FIELD_LABELS.nota} active={active.has('nota')} onToggle={() => toggleField('nota')}>
                <input
                  value={values.nota}
                  onChange={(e) => setValues({ ...values, nota: e.target.value })}
                  placeholder="Nota…"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-emerald-500/50"
                />
              </FieldBlock>

              {/* Revisado */}
              <FieldBlock label={FIELD_LABELS.revisado} active={active.has('revisado')} onToggle={() => toggleField('revisado')}>
                <div className="flex gap-2">
                  {[true, false].map((v) => (
                    <button
                      key={String(v)}
                      onClick={() => setValues({ ...values, revisado: v })}
                      className={`flex-1 py-2 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all ${
                        values.revisado === v
                          ? 'bg-emerald-500/20 text-emerald-200 border-emerald-500/40'
                          : 'bg-white/5 text-gray-500 border-white/10 hover:text-white'
                      }`}
                    >
                      {v ? 'Marcar revisado' : 'Dejar pendiente'}
                    </button>
                  ))}
                </div>
              </FieldBlock>

              {/* Guardar como regla */}
              <div className="pt-4 border-t border-white/5 space-y-3">
                <label className="flex items-center gap-2.5 text-sm text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={saveAsRule}
                    onChange={(e) => {
                      setSaveAsRule(e.target.checked);
                      if (e.target.checked) setRuleEntities(new Set(selectionEntities));
                    }}
                    className="accent-purple-500 w-4 h-4"
                  />
                  <Sparkles size={14} className="text-purple-400" />
                  También guardar como regla
                </label>

                {saveAsRule && (
                  <div className="pl-6 space-y-2">
                    <p className="text-[11px] text-gray-500">
                      Las futuras transacciones de estas entidades se etiquetarán solas:
                    </p>
                    <div className="max-h-40 overflow-y-auto custom-scrollbar space-y-1 pr-1">
                      {selectionEntities.map((name) => (
                        <label
                          key={name}
                          className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer hover:text-white"
                        >
                          <input
                            type="checkbox"
                            checked={ruleEntities.has(name)}
                            onChange={() => {
                              const next = new Set(ruleEntities);
                              next.has(name) ? next.delete(name) : next.add(name);
                              setRuleEntities(next);
                            }}
                            className="accent-purple-500 w-3.5 h-3.5"
                          />
                          <span className="truncate">{name}</span>
                        </label>
                      ))}
                      {!selectionEntities.length && (
                        <p className="text-xs text-gray-600">La selección no tiene nombres limpios definidos.</p>
                      )}
                    </div>
                    {filters.tag && (
                      <p className="text-[11px] text-purple-300/80">
                        También se guardará una regla para el tag «{filters.tag}».
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Conflictos */}
              {conflicts.length > 0 && (
                <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 space-y-2">
                  <div className="flex items-center gap-2 text-amber-200 font-bold text-sm">
                    <AlertTriangle size={16} />
                    Valores existentes
                  </div>
                  {conflicts.map((c) => (
                    <p key={c.field} className="text-xs text-amber-100/80">
                      <span className="font-bold">{c.count}</span> ya tienen {FIELD_LABELS[c.field]}:{' '}
                      {c.samples.join(', ')}
                      {c.samples.length >= 4 ? '…' : ''}
                    </p>
                  ))}
                  <label className="flex items-center gap-2 text-xs text-amber-100 cursor-pointer pt-1">
                    <input
                      type="checkbox"
                      checked={overwrite}
                      onChange={(e) => setOverwrite(e.target.checked)}
                      className="accent-amber-500 w-4 h-4"
                    />
                    Sobrescribir estos valores
                  </label>
                  {!overwrite && (
                    <p className="text-[11px] text-amber-200/60">
                      Sin marcar, solo se rellenan los campos vacíos.
                    </p>
                  )}
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-white/5 flex items-center justify-between gap-3 shrink-0">
              <button
                onClick={() => setActive(new Set())}
                disabled={!active.size}
                className="text-xs text-gray-500 hover:text-white transition-colors flex items-center gap-1.5 disabled:opacity-30"
              >
                <RotateCcw size={13} /> Limpiar campos
              </button>
              <button
                onClick={handleApply}
                disabled={!selected.length || !active.size || bulkMutation.isPending}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 text-white font-bold text-sm disabled:opacity-30 disabled:cursor-not-allowed hover:shadow-[0_0_25px_rgba(16,185,129,0.35)] transition-all active:scale-95 flex items-center gap-2"
              >
                {bulkMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
                Aplicar a {selected.length}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Result summary ────────────────────────────────────────────────── */}
      {result && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="glass-card w-full max-w-md p-6 space-y-5">
            <div className="flex items-center gap-3">
              <div
                className={`p-3 rounded-2xl border border-white/5 ${
                  undone ? 'bg-amber-500/10' : 'bg-emerald-500/10'
                }`}
              >
                {undone ? (
                  <Undo2 className="text-amber-400" size={20} />
                ) : (
                  <Check className="text-emerald-400" size={20} />
                )}
              </div>
              <div>
                <h3 className="text-lg font-bold text-white tracking-tight">
                  {undone ? 'Cambios revertidos' : 'Etiquetado aplicado'}
                </h3>
                <p className="text-xs text-gray-500">
                  {undone
                    ? 'Todo volvió a como estaba antes'
                    : `${result.updated} de ${result.affected} transacciones modificadas`}
                </p>
              </div>
            </div>

            {!undone && (
              <>
                {result.affected > result.requested && (
                  <p className="text-xs text-blue-300/80 bg-blue-500/10 border border-blue-500/20 rounded-xl px-3 py-2">
                    Se incluyeron {result.affected - result.requested} transacciones extra por pertenecer a los
                    mismos grupos.
                  </p>
                )}

                <div className="space-y-2">
                  <p className="text-[10px] uppercase font-bold tracking-widest text-gray-500">Se aplicó</p>
                  {Object.entries(result.applied_fields).length ? (
                    Object.entries(result.applied_fields).map(([field, count]) => (
                      <div
                        key={field}
                        className="flex items-center justify-between text-sm bg-white/5 rounded-xl px-3 py-2"
                      >
                        <span className="text-gray-400">{FIELD_LABELS[field as FieldKey] ?? field}</span>
                        <span className="text-white font-medium">
                          {describeValue(field as FieldKey, (resultFields as any)[field])}
                          <span className="text-gray-500 font-mono text-xs ml-2">×{count}</span>
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-gray-500">Ningún campo cambió.</p>
                  )}
                </div>

                {!!Object.keys(result.skipped_fields).length && (
                  <div className="space-y-2">
                    <p className="text-[10px] uppercase font-bold tracking-widest text-amber-400/70">
                      Omitido por tener valor
                    </p>
                    {Object.entries(result.skipped_fields).map(([field, count]) => (
                      <div
                        key={field}
                        className="flex items-center justify-between text-sm bg-amber-500/10 rounded-xl px-3 py-2 text-amber-100/80"
                      >
                        <span>{FIELD_LABELS[field as FieldKey] ?? field}</span>
                        <span className="font-mono text-xs">×{count}</span>
                      </div>
                    ))}
                  </div>
                )}

                {!!result.rules_saved.length && (
                  <div className="space-y-2">
                    <p className="text-[10px] uppercase font-bold tracking-widest text-purple-400/70">
                      Reglas guardadas
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {result.rules_saved.map((r) => (
                        <span
                          key={`${r.type}-${r.key}`}
                          className="text-[11px] px-2 py-1 rounded-lg bg-purple-500/10 text-purple-200 border border-purple-500/20"
                        >
                          {r.key}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            <div className="flex items-center justify-between gap-3 pt-2">
              {!undone ? (
                <button
                  onClick={handleUndo}
                  disabled={undoMutation.isPending || !result.undo_id}
                  className="px-4 py-2.5 rounded-xl bg-amber-500/15 text-amber-200 border border-amber-500/30 hover:bg-amber-500 hover:text-white text-sm font-bold transition-colors flex items-center gap-2 disabled:opacity-40"
                >
                  {undoMutation.isPending ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <Undo2 size={15} />
                  )}
                  Deshacer
                </button>
              ) : (
                <span />
              )}
              <button
                onClick={() => setResult(null)}
                className="px-5 py-2.5 rounded-xl bg-white/5 text-gray-300 hover:bg-white/10 text-sm font-bold transition-colors"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// A single toggleable field in the apply modal: disabled fields are never sent.
function FieldBlock({
  label,
  active,
  onToggle,
  children,
}: {
  label: string;
  active: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`rounded-2xl border p-3 transition-all ${
        active ? 'border-emerald-500/30 bg-emerald-500/[0.04]' : 'border-white/5 bg-white/[0.02]'
      }`}
    >
      <label className="flex items-center gap-2.5 cursor-pointer mb-2">
        <input type="checkbox" checked={active} onChange={onToggle} className="accent-emerald-500 w-4 h-4" />
        <span
          className={`text-[11px] uppercase font-bold tracking-widest ${
            active ? 'text-emerald-300' : 'text-gray-500'
          }`}
        >
          {label}
        </span>
      </label>
      <div className={active ? '' : 'opacity-40 pointer-events-none'}>{children}</div>
    </div>
  );
}
