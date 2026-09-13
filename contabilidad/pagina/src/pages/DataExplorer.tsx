import { useState, useEffect, useMemo, useCallback, Fragment } from 'react';
import { api, Transaction, InterpolationGroup } from '../services/api';
import { useCategories, useTags, useUpdateTransaction, useMarkAsReviewed, useFunds } from '../hooks/useTransactions';
import { EditModal } from '../components/EditModal';
import { sortTransactions, groupSplits } from '../utils/groupSplits';
import { matchFund } from '../utils/matchFund';

import {
  Search, Tag, Filter, ArrowUpRight, ArrowDownRight, Calendar, Info, ChevronDown, Check,
  List as ListIcon, TrendingUp, Settings2, Calculator, Pencil, X,
  CheckCircle2, RotateCcw, SlidersHorizontal, CheckSquare, Square,
  ArrowUpDown, Scissors, PiggyBank
} from 'lucide-react';
import ExplorerChart from '../components/ExplorerChart';
import PaymentCRUD from '../components/PaymentCRUD';
import AutoPaymentsModal from '../components/AutoPaymentsModal';

export type SortByOption = 'date_desc' | 'date_asc' | 'amount_desc' | 'amount_asc';
export type StructureFilterOption = 'all' | 'split' | 'grouped' | 'simple';
export type ReimbursableFilterOption = 'all' | 'included' | 'excluded';
export type PriorityFilterOption = 'all' | 'needs' | 'wants' | 'rated' | 'unrated';
export type TypeFilterOption = 'all' | 'expenses' | 'income';
export type LabeledFilterOption = 'all' | 'labeled' | 'unlabeled';

export function DataExplorer() {
  const [viewMode, setViewMode] = useState<'list' | 'analysis'>('list'); // UI Mode

  // Filter States
  const [searchText, setSearchText] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [tagFilter, setTagFilter] = useState('');
  const [sourceTypeFilter, setSourceTypeFilter] = useState('');
  const [pendingOnlyFilter, setPendingOnlyFilter] = useState(false);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [rowLimit, setRowLimit] = useState<number | 'all'>(50);

  // New Budget-style and Explorer feature states
  const [sortBy, setSortBy] = useState<SortByOption>('date_desc');
  const [groupSplitsMode, setGroupSplitsMode] = useState(true);
  const [structureFilter, setStructureFilter] = useState<StructureFilterOption>('all');
  const [reimbursableFilter, setReimbursableFilter] = useState<ReimbursableFilterOption>('all');
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilterOption>('all');
  const [typeFilter, setTypeFilter] = useState<TypeFilterOption>('all');
  const [labeledFilter, setLabeledFilter] = useState<LabeledFilterOption>('all');
  const [selectedFunds, setSelectedFunds] = useState<string[] | null>(null);
  const [showFundFilter, setShowFundFilter] = useState(false);
  const [expandedSplits, setExpandedSplits] = useState<Set<string>>(new Set());

  // Data States
  const [rawTransactions, setRawTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);

  // Queries & Mutations
  const { data: categories } = useCategories();
  const { data: tags } = useTags();
  const { data: funds } = useFunds();
  const updateMutation = useUpdateTransaction();
  const markReviewedMutation = useMarkAsReviewed();

  // Load raw transactions based on API-level filters
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getTransactions(
        undefined, // date
        undefined, // pendingOnly (handled in client filter for instant reactive switching)
        undefined, // esReembolsable (handled in client filter)
        startDate || undefined,
        endDate || undefined,
        undefined, // debtor
        searchText.trim() || undefined
      );

      setRawTransactions(data);
    } catch (error) {
      console.error("Error loading transactions in DataExplorer", error);
    } finally {
      setLoading(false);
    }
  }, [searchText, startDate, endDate]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Client-side filtering, splitting and sorting
  const results = useMemo(() => {
    let list = rawTransactions;

    // 1. Filtro de Categoría (incluye "Sin categoría")
    if (categoryFilter === '__sin_categoria__') {
      const isUncat = (c?: string) => !c || c.trim() === '' || c === '---';
      list = list.filter(t => {
        if (isUncat(t.categoria)) return true;
        if (t.subTransactions && t.subTransactions.length > 0) {
          return t.subTransactions.some(sub => isUncat(sub.categoria));
        }
        return false;
      });
    } else if (categoryFilter) {
      list = list.filter(t => {
        if (t.categoria === categoryFilter) return true;
        if (t.subTransactions && t.subTransactions.length > 0) {
          return t.subTransactions.some(sub => sub.categoria === categoryFilter);
        }
        return false;
      });
    }

    // 2. Filtro de Tags (incluye "Sin tags / Sin etiquetas")
    if (tagFilter === '__sin_tags__') {
      const isUntagged = (tg?: string) => !tg || tg.trim() === '' || tg === '---';
      list = list.filter(t => {
        if (isUntagged(t.tags)) return true;
        if (t.subTransactions && t.subTransactions.length > 0) {
          return t.subTransactions.some(sub => isUntagged(sub.tags));
        }
        return false;
      });
    } else if (tagFilter) {
      const tagLower = tagFilter.toLowerCase();
      list = list.filter(t => {
        const matchTag = (tagsStr?: string) => {
          if (!tagsStr) return false;
          return tagsStr.split(',').map(s => s.trim().toLowerCase()).includes(tagLower);
        };
        if (matchTag(t.tags)) return true;
        if (t.subTransactions && t.subTransactions.length > 0) {
          return t.subTransactions.some(sub => matchTag(sub.tags));
        }
        return false;
      });
    }

    // 3. Filtro de Fuente (Banca/Tarjeta)
    if (sourceTypeFilter) {
      list = list.filter(t => (t.TIPO || '').toUpperCase() === sourceTypeFilter.toUpperCase());
    }

    // 4. Filtro de Reembolsables (estilo Presupuesto)
    if (reimbursableFilter === 'included') {
      list = list.filter(t => t.es_reembolsable);
    } else if (reimbursableFilter === 'excluded') {
      list = list.filter(t => !t.es_reembolsable);
    }

    // 5. Filtro de Prioridad (Necesidad / Deseo - estilo Presupuesto)
    if (priorityFilter === 'needs') {
      list = list.filter(t => t.MONTO >= 0 || t.prioridad === 'Necesidad');
    } else if (priorityFilter === 'wants') {
      list = list.filter(t => t.MONTO >= 0 || t.prioridad === 'Deseo');
    } else if (priorityFilter === 'rated') {
      list = list.filter(t => t.MONTO >= 0 || (t.prioridad === 'Necesidad' || t.prioridad === 'Deseo'));
    } else if (priorityFilter === 'unrated') {
      list = list.filter(t => t.MONTO < 0 && (!t.prioridad || t.prioridad === '---'));
    }

    // 6. Filtro de Estado de Etiquetado / Revisado
    if (labeledFilter === 'unlabeled' || pendingOnlyFilter) {
      list = list.filter(t => !t.revisado);
    } else if (labeledFilter === 'labeled') {
      list = list.filter(t => t.revisado);
    }

    // 7. Filtro de Tipo (Ingresos vs Gastos)
    if (typeFilter === 'expenses') {
      list = list.filter(t => t.MONTO < 0);
    } else if (typeFilter === 'income') {
      list = list.filter(t => t.MONTO > 0);
    }

    // 8. Filtro de Fondos (estilo Presupuesto)
    if (selectedFunds !== null) {
      list = list.filter(t => {
        const f = matchFund(t, funds);
        if (!f) return selectedFunds.includes('__sin_fondo__');
        return selectedFunds.includes(f.id);
      });
    }

    // 9. Agrupación de Splits
    if (groupSplitsMode) {
      list = groupSplits(list);
    }

    // 10. Filtro de Estructura (Divisiones y Grupos)
    if (structureFilter === 'split') {
      list = list.filter(t => (t.subTransactions && t.subTransactions.length > 1) || (t.split_group_id && t.split_group_id.trim() !== ''));
    } else if (structureFilter === 'grouped') {
      list = list.filter(t => t.group_id && t.group_id.trim() !== '');
    } else if (structureFilter === 'simple') {
      list = list.filter(t => (!t.subTransactions || t.subTransactions.length <= 1) && (!t.split_group_id || t.split_group_id.trim() === '') && (!t.group_id || t.group_id.trim() === ''));
    }

    // 11. Ordenación
    if (sortBy === 'date_desc') {
      return sortTransactions(list, 'desc');
    } else if (sortBy === 'date_asc') {
      return sortTransactions(list, 'asc');
    } else if (sortBy === 'amount_desc') {
      return [...list].sort((a, b) => Math.abs(b.MONTO) - Math.abs(a.MONTO));
    } else if (sortBy === 'amount_asc') {
      return [...list].sort((a, b) => Math.abs(a.MONTO) - Math.abs(b.MONTO));
    }

    return sortTransactions(list, 'desc');
  }, [rawTransactions, categoryFilter, tagFilter, sourceTypeFilter, reimbursableFilter, priorityFilter, pendingOnlyFilter, labeledFilter, typeFilter, selectedFunds, funds, groupSplitsMode, structureFilter, sortBy]);

  const displayedResults = useMemo(() => {
    if (rowLimit === 'all') return results;
    return results.slice(0, rowLimit);
  }, [results, rowLimit]);

  // Editing Modal State
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);

  // Bulk Selection & Operations
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkTagInput, setBulkTagInput] = useState('');
  const [showBulkTagModal, setShowBulkTagModal] = useState(false);
  const [showBulkCategoryModal, setShowBulkCategoryModal] = useState(false);
  const [bulkCategoryInput, setBulkCategoryInput] = useState('');
  const [bulkLoading, setBulkLoading] = useState(false);

  // Analysis State
  const [chartData, setChartData] = useState<any>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [groups, setGroups] = useState<InterpolationGroup[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string>('');
  const [comparisonType, setComparisonType] = useState<'interpolated' | 'fixed'>('interpolated');

  // Auto Payments / Selection State
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [targetTransaction, setTargetTransaction] = useState<Transaction | null>(null);
  const [selectedExpenses, setSelectedExpenses] = useState<Transaction[]>([]);
  const [isAutoPaymentsModalOpen, setIsAutoPaymentsModalOpen] = useState(false);

  // Load groups for comparison dropdown
  useEffect(() => {
    if (viewMode === 'analysis') {
      const loadGroups = async () => {
        try {
          const g = await api.getGroups(comparisonType);
          setGroups(g);
        } catch (e) { console.error(e); }
      };
      loadGroups();
    }
  }, [viewMode, comparisonType]);

  // Load Analysis Data
  useEffect(() => {
    if (viewMode === 'analysis') {
      const loadAnalysis = async () => {
        setAnalysisLoading(true);
        try {
          const data = await api.getAnalysisChartData(
            categoryFilter || undefined,
            tagFilter || undefined,
            startDate || undefined,
            endDate || undefined,
            selectedGroupId
          );
          setChartData(data);
        } catch (e) {
          console.error(e);
        } finally {
          setAnalysisLoading(false);
        }
      };
      loadAnalysis();
    } else {
      setChartData(null);
    }
  }, [viewMode, categoryFilter, tagFilter, startDate, endDate, selectedGroupId]);

  // Reset all filters
  const handleResetFilters = () => {
    setSearchText('');
    setCategoryFilter('');
    setTagFilter('');
    setSourceTypeFilter('');
    setPendingOnlyFilter(false);
    setStartDate('');
    setEndDate('');
    setRowLimit(50);
    setSortBy('date_desc');
    setGroupSplitsMode(true);
    setStructureFilter('all');
    setReimbursableFilter('all');
    setPriorityFilter('all');
    setTypeFilter('all');
    setLabeledFilter('all');
    setSelectedFunds(null);
    setSelectedIds(new Set());
    setExpandedSplits(new Set());
  };

  // Bulk Selection Handlers
  const toggleSelectRow = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAllRows = () => {
    if (selectedIds.size === displayedResults.length && displayedResults.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(displayedResults.map(r => r.id)));
    }
  };

  // Bulk operations
  const handleBulkAddTags = async () => {
    if (!bulkTagInput.trim() || selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      const newTagList = bulkTagInput.split(',').map(t => t.trim()).filter(Boolean);
      for (const id of selectedIds) {
        const tx = results.find(r => r.id === id);
        if (!tx) continue;
        const current = tx.tags ? tx.tags.split(',').map(t => t.trim()) : [];
        const merged = Array.from(new Set([...current, ...newTagList])).join(',');
        await api.updateTransaction(id, { tags: merged });
      }
      setShowBulkTagModal(false);
      setBulkTagInput('');
      setSelectedIds(new Set());
      await loadData();
    } catch (e) {
      console.error("Bulk tag error", e);
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkSetCategory = async () => {
    if (!bulkCategoryInput || selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      for (const id of selectedIds) {
        await api.updateTransaction(id, { categoria: bulkCategoryInput });
      }
      setShowBulkCategoryModal(false);
      setBulkCategoryInput('');
      setSelectedIds(new Set());
      await loadData();
    } catch (e) {
      console.error("Bulk category error", e);
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkMarkReviewed = async () => {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      for (const id of selectedIds) {
        await api.markAsReviewed(id);
      }
      setSelectedIds(new Set());
      await loadData();
    } catch (e) {
      console.error("Bulk mark reviewed error", e);
    } finally {
      setBulkLoading(false);
    }
  };

  // Calculations
  const totalAmount = useMemo(() => results.reduce((acc, curr) => acc + curr.MONTO, 0), [results]);
  const income = useMemo(() => results.filter(t => t.MONTO > 0).reduce((acc, curr) => acc + curr.MONTO, 0), [results]);
  const expenses = useMemo(() => results.filter(t => t.MONTO < 0).reduce((acc, curr) => acc + curr.MONTO, 0), [results]);
  const unreviewedCount = useMemo(() => rawTransactions.filter(t => !t.revisado).length, [rawTransactions]);

  const activeFiltersCount =
    (searchText ? 1 : 0) +
    (categoryFilter ? 1 : 0) +
    (tagFilter ? 1 : 0) +
    (sourceTypeFilter ? 1 : 0) +
    (pendingOnlyFilter || labeledFilter !== 'all' ? 1 : 0) +
    (startDate ? 1 : 0) +
    (endDate ? 1 : 0) +
    (sortBy !== 'date_desc' ? 1 : 0) +
    (!groupSplitsMode ? 1 : 0) +
    (structureFilter !== 'all' ? 1 : 0) +
    (reimbursableFilter !== 'all' ? 1 : 0) +
    (priorityFilter !== 'all' ? 1 : 0) +
    (typeFilter !== 'all' ? 1 : 0) +
    (selectedFunds !== null ? 1 : 0);

  const fundList = funds || [];
  const activeFundIds = selectedFunds ?? [...fundList.map(f => f.id), '__sin_fondo__'];

  return (
    <div className="flex-1 overflow-y-auto px-4 md:px-8 pb-8 custom-scrollbar">
      <div className="max-w-7xl mx-auto space-y-6 mt-8">

        {/* Header & View Switcher */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
          <div className="space-y-2">
            <h1 className="text-4xl font-bold text-white tracking-tight flex items-center gap-3">
              <Search className="text-primary-400" size={36} />
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-white to-surface-400">
                Explorador de Datos
              </span>
            </h1>
            <p className="text-surface-400 text-sm md:text-base max-w-2xl">
              Busca, filtra, inspecciona y etiqueta transacciones detalladamente en tiempo real.
            </p>
          </div>

          <div className="flex gap-4 items-center">
            {/* View Switcher */}
            <div className="bg-surface-900/50 p-1.5 rounded-2xl border border-white/10 shadow-lg flex shrink-0">
              <button
                onClick={() => setViewMode('list')}
                className={`
                  flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-300 relative overflow-hidden
                  ${viewMode === 'list' ? 'text-white bg-white/10' : 'text-surface-400 hover:text-white hover:bg-white/5'}
                `}
              >
                <ListIcon size={18} /> Lista y Etiquetado
              </button>
              <button
                onClick={() => setViewMode('analysis')}
                className={`
                  flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-300 relative overflow-hidden
                  ${viewMode === 'analysis' ? 'text-white bg-white/10' : 'text-surface-400 hover:text-white hover:bg-white/5'}
                `}
              >
                <TrendingUp size={18} /> Análisis
              </button>
            </div>
          </div>
        </div>

        {/* Filter Control Panel */}
        <div className="bg-gradient-to-b from-surface-900/60 to-surface-950/60 backdrop-blur-xl border border-white/10 rounded-3xl p-6 shadow-2xl space-y-4">
          <div className="flex items-center justify-between gap-4 flex-wrap border-b border-white/5 pb-4">
            <div className="flex items-center gap-2">
              <SlidersHorizontal size={18} className="text-primary-400" />
              <span className="text-sm font-bold text-white uppercase tracking-wider">Filtros de Búsqueda</span>
              {activeFiltersCount > 0 && (
                <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-primary-500/20 text-primary-300 border border-primary-500/30">
                  {activeFiltersCount} activo{activeFiltersCount > 1 ? 's' : ''}
                </span>
              )}
            </div>
            {activeFiltersCount > 0 && (
              <button
                onClick={handleResetFilters}
                className="flex items-center gap-1.5 text-xs text-surface-400 hover:text-rose-400 transition-colors px-2.5 py-1 rounded-lg hover:bg-white/5"
              >
                <RotateCcw size={14} /> Limpiar filtros
              </button>
            )}
          </div>

          {/* Grid Principal de Filtros */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Search Input */}
            <div className="relative col-span-1 md:col-span-2">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-surface-500" size={16} />
              <input
                type="text"
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
                placeholder="Buscar por concepto, nombre limpio, notas, tags..."
                className="w-full bg-surface-950/80 border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-white text-sm focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/30 placeholder:text-surface-500"
              />
              {searchText && (
                <button onClick={() => setSearchText('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-white">
                  <X size={14} />
                </button>
              )}
            </div>

            {/* Selector de Orden */}
            <div className="relative">
              <div className="flex items-center">
                <select
                  value={sortBy}
                  onChange={e => setSortBy(e.target.value as SortByOption)}
                  className={`w-full bg-surface-950/80 border rounded-xl pl-9 pr-8 py-2.5 text-sm font-medium focus:outline-none appearance-none cursor-pointer transition-all ${
                    sortBy !== 'date_desc'
                      ? 'border-primary-500/60 text-primary-300 ring-1 ring-primary-500/30'
                      : 'border-white/10 text-surface-200'
                  }`}
                  title="Elegir el orden en el que se muestran las transacciones"
                >
                  <option value="date_desc" className="bg-surface-900 text-white">📅 Fecha: Más reciente primero</option>
                  <option value="date_asc" className="bg-surface-900 text-white">📅 Fecha: Más antigua primero</option>
                  <option value="amount_desc" className="bg-surface-900 text-white">💎 Monto: Mayor importe</option>
                  <option value="amount_asc" className="bg-surface-900 text-white">🔹 Monto: Menor importe</option>
                </select>
                <ArrowUpDown className="absolute left-3 top-1/2 -translate-y-1/2 text-primary-400 pointer-events-none" size={15} />
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={16} />
              </div>
            </div>

            {/* Category Dropdown */}
            <div className="relative">
              <select
                value={categoryFilter}
                onChange={e => setCategoryFilter(e.target.value)}
                className={`w-full bg-surface-950/80 border rounded-xl px-3.5 py-2.5 text-sm focus:outline-none appearance-none cursor-pointer transition-all ${
                  categoryFilter
                    ? 'border-indigo-500/60 text-indigo-300 ring-1 ring-indigo-500/30'
                    : 'border-white/10 text-surface-200'
                }`}
              >
                <option value="" className="bg-surface-900 text-white">Todas las categorías</option>
                <option value="__sin_categoria__" className="bg-surface-900 text-amber-300 font-semibold">⚪ Sin categoría</option>
                {(categories ?? []).map(c => (
                  <option key={c} value={c} className="bg-surface-900 text-white">{c}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={16} />
            </div>

            {/* Reembolsables Dropdown (Estilo Presupuesto) */}
            <div className="relative">
              <select
                value={reimbursableFilter}
                onChange={e => setReimbursableFilter(e.target.value as ReimbursableFilterOption)}
                className={`w-full bg-surface-950/80 border rounded-xl px-3.5 py-2.5 text-sm focus:outline-none appearance-none cursor-pointer transition-all ${
                  reimbursableFilter !== 'all'
                    ? 'border-purple-500/60 text-purple-300 ring-1 ring-purple-500/30'
                    : 'border-white/10 text-surface-200'
                }`}
              >
                <option value="all" className="bg-surface-900 text-white">Reembolsables: Todo</option>
                <option value="included" className="bg-surface-900 text-purple-300">🟣 Solo Reembolsables</option>
                <option value="excluded" className="bg-surface-900 text-surface-300">🚫 Sin Reembolsables</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={16} />
            </div>

            {/* Prioridad Dropdown (Necesidad / Deseo - Estilo Presupuesto) */}
            <div className="relative">
              <select
                value={priorityFilter}
                onChange={e => setPriorityFilter(e.target.value as PriorityFilterOption)}
                className={`w-full bg-surface-950/80 border rounded-xl px-3.5 py-2.5 text-sm focus:outline-none appearance-none cursor-pointer transition-all ${
                  priorityFilter !== 'all'
                    ? 'border-amber-400/60 text-amber-300 ring-1 ring-amber-400/30'
                    : 'border-white/10 text-surface-200'
                }`}
                title="Solo afecta a los gastos: clasifica por Necesidad o Deseo"
              >
                <option value="all" className="bg-surface-900 text-white">Prioridad: Todas (Nec / Des)</option>
                <option value="needs" className="bg-surface-900 text-emerald-300">🟢 Solo Necesidades</option>
                <option value="wants" className="bg-surface-900 text-amber-300">🟡 Solo Deseos</option>
                <option value="rated" className="bg-surface-900 text-surface-200">🏷️ Solo Clasificadas (Nec + Des)</option>
                <option value="unrated" className="bg-surface-900 text-surface-400">⚪ Sin clasificar</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={16} />
            </div>

            {/* Control de Divisiones / Grupos */}
            <div className="relative">
              <select
                value={structureFilter}
                onChange={e => setStructureFilter(e.target.value as StructureFilterOption)}
                className={`w-full bg-surface-950/80 border rounded-xl px-3.5 py-2.5 text-sm focus:outline-none appearance-none cursor-pointer transition-all ${
                  structureFilter !== 'all'
                    ? 'border-sky-500/60 text-sky-300 ring-1 ring-sky-500/30'
                    : 'border-white/10 text-surface-200'
                }`}
              >
                <option value="all" className="bg-surface-900 text-white">Estructura: Todas</option>
                <option value="split" className="bg-surface-900 text-cyan-300">✂️ Solo Divididas (Splits)</option>
                <option value="grouped" className="bg-surface-900 text-blue-300">🔗 Solo Agrupadas</option>
                <option value="simple" className="bg-surface-900 text-surface-300">📄 Solo Simples (Sin división)</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={16} />
            </div>

            {/* Toggle de Agrupar Divisiones */}
            <button
              onClick={() => setGroupSplitsMode(!groupSplitsMode)}
              className={`flex items-center justify-between gap-2 py-2.5 px-3.5 rounded-xl border text-sm font-medium transition-all ${
                groupSplitsMode
                  ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-200'
                  : 'bg-surface-950/80 border-white/10 text-surface-400 hover:text-white'
              }`}
              title="Colapsar las partes de transacciones divididas en una fila o mostrarlas por separado"
            >
              <div className="flex items-center gap-2">
                <Scissors size={15} className={groupSplitsMode ? 'text-cyan-400' : 'text-surface-500'} />
                <span className="truncate">{groupSplitsMode ? 'Divisiones agrupadas' : 'Partes individuales'}</span>
              </div>
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${groupSplitsMode ? 'bg-cyan-500/20 text-cyan-300' : 'bg-white/5 text-surface-500'}`}>
                {groupSplitsMode ? 'ON' : 'OFF'}
              </span>
            </button>

            {/* Tag Dropdown */}
            <div className="relative">
              <select
                value={tagFilter}
                onChange={e => setTagFilter(e.target.value)}
                className={`w-full bg-surface-950/80 border rounded-xl px-3.5 py-2.5 text-sm focus:outline-none appearance-none cursor-pointer transition-all ${
                  tagFilter
                    ? 'border-violet-500/60 text-violet-300 ring-1 ring-violet-500/30'
                    : 'border-white/10 text-surface-200'
                }`}
              >
                <option value="" className="bg-surface-900 text-white">Todos los tags</option>
                <option value="__sin_tags__" className="bg-surface-900 text-amber-300 font-semibold">⚪ Sin tags / Sin etiquetas</option>
                {(tags ?? []).map(t => (
                  <option key={t} value={t} className="bg-surface-900 text-white">#{t}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={16} />
            </div>

            {/* Source Dropdown */}
            <div className="relative">
              <select
                value={sourceTypeFilter}
                onChange={e => setSourceTypeFilter(e.target.value)}
                className="w-full bg-surface-950/80 border border-white/10 rounded-xl px-3.5 py-2.5 text-surface-200 text-sm focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/30 appearance-none"
              >
                <option value="">Todas las fuentes (Banca/Tarjeta)</option>
                <option value="BANCA" className="bg-surface-900 text-white">BANCA</option>
                <option value="TARJETA" className="bg-surface-900 text-white">TARJETA</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={16} />
            </div>

            {/* Type Filter (Ingresos / Gastos) */}
            <div className="relative">
              <select
                value={typeFilter}
                onChange={e => setTypeFilter(e.target.value as TypeFilterOption)}
                className={`w-full bg-surface-950/80 border rounded-xl px-3.5 py-2.5 text-sm focus:outline-none appearance-none cursor-pointer transition-all ${
                  typeFilter !== 'all'
                    ? 'border-emerald-500/60 text-emerald-300 ring-1 ring-emerald-500/30'
                    : 'border-white/10 text-surface-200'
                }`}
              >
                <option value="all" className="bg-surface-900 text-white">Tipo: Todo (Gastos e Ingresos)</option>
                <option value="expenses" className="bg-surface-900 text-rose-300">🔻 Solo Gastos</option>
                <option value="income" className="bg-surface-900 text-emerald-300">🔺 Solo Ingresos</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={16} />
            </div>

            {/* Estado de Revisión Dropdown */}
            <div className="relative">
              <select
                value={labeledFilter}
                onChange={e => {
                  const val = e.target.value as LabeledFilterOption;
                  setLabeledFilter(val);
                  if (val === 'unlabeled') setPendingOnlyFilter(true);
                  else setPendingOnlyFilter(false);
                }}
                className={`w-full bg-surface-950/80 border rounded-xl px-3.5 py-2.5 text-sm focus:outline-none appearance-none cursor-pointer transition-all ${
                  labeledFilter !== 'all'
                    ? 'border-amber-500/60 text-amber-300 ring-1 ring-amber-500/30'
                    : 'border-white/10 text-surface-200'
                }`}
              >
                <option value="all" className="bg-surface-900 text-white">Estado: Todas</option>
                <option value="unlabeled" className="bg-surface-900 text-amber-300 font-semibold">
                  ⏳ Solo Sin Revisar{unreviewedCount > 0 ? ` (${unreviewedCount})` : ''}
                </option>
                <option value="labeled" className="bg-surface-900 text-emerald-300 font-semibold">✅ Solo Revisadas</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={16} />
            </div>

            {/* Date Range Start */}
            <div className="flex items-center gap-2 bg-surface-950/80 border border-white/10 rounded-xl px-3 py-1.5">
              <Calendar size={14} className="text-surface-500 shrink-0" />
              <span className="text-[11px] text-surface-400 font-medium shrink-0">Desde</span>
              <input
                type="date"
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
                className="bg-transparent border-none text-xs text-white focus:ring-0 p-0 font-mono w-full cursor-pointer"
              />
              {startDate && <button onClick={() => setStartDate('')} className="text-surface-500 hover:text-white"><X size={12} /></button>}
            </div>

            {/* Date Range End */}
            <div className="flex items-center gap-2 bg-surface-950/80 border border-white/10 rounded-xl px-3 py-1.5">
              <Calendar size={14} className="text-surface-500 shrink-0" />
              <span className="text-[11px] text-surface-400 font-medium shrink-0">Hasta</span>
              <input
                type="date"
                value={endDate}
                onChange={e => setEndDate(e.target.value)}
                className="bg-transparent border-none text-xs text-white focus:ring-0 p-0 font-mono w-full cursor-pointer"
              />
              {endDate && <button onClick={() => setEndDate('')} className="text-surface-500 hover:text-white"><X size={12} /></button>}
            </div>

            {/* Row Limit Selector */}
            <div className="relative">
              <select
                value={rowLimit}
                onChange={e => setRowLimit(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                className="w-full bg-surface-950/80 border border-white/10 rounded-xl px-3.5 py-2.5 text-surface-200 text-sm focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/30 appearance-none font-medium"
              >
                <option value={50} className="bg-surface-900 text-white">Máx 50 filas (por defecto)</option>
                <option value={100} className="bg-surface-900 text-white">Máx 100 filas</option>
                <option value={200} className="bg-surface-900 text-white">Máx 200 filas</option>
                <option value="all" className="bg-surface-900 text-white">Todas ({results.length})</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={16} />
            </div>

            {/* Filtro por Fondos (Popover estilo Presupuesto) */}
            <div className="relative">
              <button
                onClick={() => setShowFundFilter(!showFundFilter)}
                className={`w-full flex items-center justify-between gap-2 py-2.5 px-3.5 rounded-xl border text-sm font-medium transition-all ${
                  selectedFunds !== null
                    ? 'bg-teal-500/15 border-teal-500/40 text-teal-300'
                    : 'bg-surface-950/80 border-white/10 text-surface-400 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <PiggyBank size={16} className={selectedFunds !== null ? 'text-teal-400' : 'text-surface-500'} />
                  <span className="truncate">
                    {selectedFunds === null
                      ? 'Todos los fondos'
                      : `Fondos (${activeFundIds.length}/${fundList.length + 1})`}
                  </span>
                </div>
                <ChevronDown size={14} />
              </button>

              {showFundFilter && (
                <>
                  <div className="fixed inset-0 z-30" onClick={() => setShowFundFilter(false)} />
                  <div className="absolute z-40 mt-2 right-0 w-72 bg-surface-900 border border-white/10 rounded-2xl shadow-2xl p-3 backdrop-blur-xl space-y-2">
                    <div className="flex justify-between items-center pb-2 border-b border-white/10">
                      <span className="text-xs font-bold uppercase tracking-wider text-surface-300">Filtrar por fondo</span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setSelectedFunds(null)}
                          className="text-[11px] text-teal-400 hover:text-teal-300 font-semibold"
                        >
                          Todos
                        </button>
                        <span className="text-surface-600">|</span>
                        <button
                          onClick={() => setSelectedFunds([])}
                          className="text-[11px] text-surface-400 hover:text-surface-200 font-semibold"
                        >
                          Ninguno
                        </button>
                      </div>
                    </div>
                    <div className="max-h-56 overflow-y-auto custom-scrollbar space-y-1">
                      <button
                        onClick={() => {
                          const sinFondoMarcado = activeFundIds.includes('__sin_fondo__');
                          const next = sinFondoMarcado
                            ? activeFundIds.filter(id => id !== '__sin_fondo__')
                            : [...activeFundIds, '__sin_fondo__'];
                          setSelectedFunds(next);
                        }}
                        className={`w-full text-left text-xs px-2.5 py-1.5 rounded-lg flex items-center gap-2 transition-colors border-b border-white/5 pb-2 mb-1 ${
                          activeFundIds.includes('__sin_fondo__') ? 'bg-teal-500/10 text-teal-200' : 'text-surface-400 hover:bg-white/5'
                        }`}
                      >
                        <span className={`w-3.5 h-3.5 rounded border flex-shrink-0 flex items-center justify-center ${
                          activeFundIds.includes('__sin_fondo__') ? 'bg-teal-500 border-teal-500' : 'border-surface-600'
                        }`}>
                          {activeFundIds.includes('__sin_fondo__') && <Check size={10} className="text-surface-950" />}
                        </span>
                        <span className="truncate font-medium">⚪ Sin fondo asignado</span>
                      </button>

                      {fundList.length === 0 && (
                        <p className="text-xs text-surface-500 italic py-2 text-center">No hay fondos configurados.</p>
                      )}
                      {fundList.map(f => {
                        const marcado = activeFundIds.includes(f.id);
                        return (
                          <button
                            key={f.id}
                            onClick={() => {
                              const next = marcado
                                ? activeFundIds.filter(id => id !== f.id)
                                : [...activeFundIds, f.id];
                              setSelectedFunds(next);
                            }}
                            className={`w-full text-left text-xs px-2.5 py-1.5 rounded-lg flex items-center gap-2 transition-colors ${
                              marcado ? 'bg-teal-500/10 text-teal-200' : 'text-surface-400 hover:bg-white/5'
                            }`}
                          >
                            <span className={`w-3.5 h-3.5 rounded border flex-shrink-0 flex items-center justify-center ${
                              marcado ? 'bg-teal-500 border-teal-500' : 'border-surface-600'
                            }`}>
                              {marcado && <Check size={10} className="text-surface-950" />}
                            </span>
                            <span className="truncate">{f.name}</span>
                          </button>
                        );
                      })}
                    </div>
                    <p className="text-[10px] text-surface-500 pt-2 border-t border-white/10 leading-relaxed">
                      Selecciona fondos específicos o marca &ldquo;Sin fondo asignado&rdquo;.
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* ANALYSIS VIEW */}
        {viewMode === 'analysis' && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Analysis Controls */}
            <div className="bg-gradient-to-b from-surface-900/60 to-surface-950/60 backdrop-blur-xl border border-white/10 rounded-3xl p-6 shadow-2xl grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-surface-300 mb-2 uppercase tracking-wider">
                  1. Tipo de Referencia
                </label>
                <div className="flex bg-surface-950 rounded-xl p-1 border border-white/10">
                  <button
                    onClick={() => { setComparisonType('interpolated'); setSelectedGroupId(''); }}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${comparisonType === 'interpolated' ? 'bg-surface-800 text-white' : 'text-surface-400 hover:text-white'}`}
                  >
                    Interpolado
                  </button>
                  <button
                    onClick={() => { setComparisonType('fixed'); setSelectedGroupId(''); }}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${comparisonType === 'fixed' ? 'bg-surface-800 text-white' : 'text-surface-400 hover:text-white'}`}
                  >
                    Fijo
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold text-surface-300 mb-2 uppercase tracking-wider">
                  2. Comparar con Grupo
                </label>
                <div className="relative">
                  <select
                    className="w-full bg-surface-950 border border-white/10 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary-500/50 appearance-none"
                    value={selectedGroupId}
                    onChange={(e) => setSelectedGroupId(e.target.value)}
                  >
                    <option value="">-- Ninguno --</option>
                    {groups.map(g => (
                      <option key={g.id} value={g.id}>{g.name}</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={16} />
                </div>
              </div>
            </div>

            {/* Chart Section */}
            <div className="bg-surface-900/40 backdrop-blur-xl border border-white/10 rounded-3xl p-6 shadow-2xl">
              <div className="mb-6 flex justify-between items-center">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <TrendingUp className="text-emerald-400" />
                  Tendencia {categoryFilter ? `[Categoría: ${categoryFilter}]` : ''} {tagFilter ? `[Tag: ${tagFilter}]` : ''}
                </h2>
              </div>
              <div className="h-[400px]">
                {chartData ? (
                  <ExplorerChart data={chartData} loading={analysisLoading} />
                ) : (
                  <div className="h-full flex items-center justify-center text-surface-500">
                    {analysisLoading ? 'Cargando gráfico...' : 'Aplica un filtro o selecciona un grupo para ver el análisis.'}
                  </div>
                )}
              </div>
            </div>

            {/* Management Section */}
            <div className="bg-surface-900/40 backdrop-blur-xl border border-white/10 rounded-3xl overflow-hidden shadow-2xl">
              <div className="p-6 border-b border-white/5 flex items-center gap-2">
                <Settings2 className="text-primary-400" />
                <h2 className="text-xl font-bold text-white">Administrar Referencias</h2>
              </div>
              <div className="h-[600px]">
                <PaymentCRUD
                  groupType={comparisonType}
                  onDataChange={() => {
                    api.getGroups(comparisonType).then(setGroups);
                    if (selectedGroupId) {
                      const current = selectedGroupId;
                      setSelectedGroupId('');
                      setTimeout(() => setSelectedGroupId(current), 100);
                    }
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {/* LIST & LABELING VIEW */}
        {viewMode === 'list' && (
          <div className="space-y-6">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                label="Transacciones"
                value={results.length.toString()}
                icon={<Info size={20} />}
                colorClass="bg-blue-500/10 text-blue-400 border-blue-500/20"
              />
              <StatCard
                label="Ingresos"
                value={income.toLocaleString('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })}
                icon={<ArrowUpRight size={20} />}
                colorClass="bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
              />
              <StatCard
                label="Gastos"
                value={expenses.toLocaleString('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })}
                icon={<ArrowDownRight size={20} />}
                colorClass="bg-rose-500/10 text-rose-400 border-rose-500/20"
              />
              <StatCard
                label="Neto Total"
                value={totalAmount.toLocaleString('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })}
                icon={<Filter size={20} />}
                colorClass={`${totalAmount >= 0 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20'}`}
              />
            </div>

            {/* Auto Payments & Mode Controls */}
            <div className="flex flex-col sm:flex-row justify-between items-center bg-surface-900/50 backdrop-blur-xl border border-white/10 rounded-2xl p-4 gap-4 shadow-lg">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => {
                    setIsSelectionMode(!isSelectionMode);
                    if (isSelectionMode) {
                      setTargetTransaction(null);
                      setSelectedExpenses([]);
                    }
                  }}
                  className={`px-4 py-2 rounded-xl text-sm font-bold transition-all border ${
                    isSelectionMode
                      ? 'bg-rose-500/10 text-rose-400 border-rose-500/20 hover:bg-rose-500/20'
                      : 'bg-surface-800 text-white border-white/5 hover:bg-surface-700 hover:border-white/10'
                  }`}
                >
                  {isSelectionMode ? 'Cancelar Modo Pagos' : '⚡ Modo Pagos Automáticos'}
                </button>
                {isSelectionMode && (
                  <p className="text-xs text-surface-400">
                    {!targetTransaction
                      ? "1. Selecciona el Objetivo (Ingreso)"
                      : "2. Selecciona los Gastos relacionados"
                    }
                  </p>
                )}
              </div>

              {isSelectionMode && targetTransaction && selectedExpenses.length > 0 && (
                <button
                  onClick={() => setIsAutoPaymentsModalOpen(true)}
                  className="px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 text-white text-sm font-bold rounded-xl transition-all shadow-lg shadow-emerald-900/20 flex items-center gap-2 animate-in fade-in slide-in-from-right-4"
                >
                  <Calculator size={16} /> Configurar Pagos ({selectedExpenses.length})
                </button>
              )}
            </div>

            {/* Sticky Bulk Action Bar when items selected in Normal Mode */}
            {!isSelectionMode && selectedIds.size > 0 && (
              <div className="flex items-center justify-between gap-3 p-4 rounded-2xl bg-primary-600/10 border border-primary-500/30 backdrop-blur-xl animate-in fade-in slide-in-from-top-2 duration-300">
                <div className="flex items-center gap-2 text-sm text-white font-medium">
                  <CheckSquare size={18} className="text-primary-400" />
                  <span className="font-bold">{selectedIds.size}</span> seleccionadas
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={() => setShowBulkTagModal(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-800 hover:bg-primary-500/20 text-primary-300 border border-primary-500/30 text-xs font-bold transition-all"
                  >
                    <Tag size={14} /> Tag en masa
                  </button>
                  <button
                    onClick={() => setShowBulkCategoryModal(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-800 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-bold transition-all"
                  >
                    <Filter size={14} /> Categoría en masa
                  </button>
                  <button
                    onClick={handleBulkMarkReviewed}
                    disabled={bulkLoading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-800 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-bold transition-all disabled:opacity-50"
                  >
                    <CheckCircle2 size={14} /> Marcar revisadas
                  </button>
                  <button
                    onClick={() => setSelectedIds(new Set())}
                    className="p-1.5 rounded-lg text-surface-400 hover:text-white hover:bg-white/10"
                    title="Desmarcar todo"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>
            )}

            {/* Table */}
            <div className="bg-surface-900/40 backdrop-blur-xl border border-white/10 rounded-3xl overflow-hidden shadow-2xl">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-20 gap-4">
                  <div className="relative">
                    <div className="w-12 h-12 border-4 border-surface-800 border-t-primary-500 rounded-full animate-spin"></div>
                  </div>
                  <p className="text-surface-400 text-sm font-medium animate-pulse">Cargando transacciones...</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-surface-950/50 text-surface-400 text-xs font-bold uppercase tracking-widest border-b border-white/5">
                        <th className="px-5 py-4 w-12 text-center">
                          {!isSelectionMode && (
                            <button onClick={toggleSelectAllRows} className="text-surface-400 hover:text-white">
                              {selectedIds.size > 0 && selectedIds.size === results.length ? (
                                <CheckSquare size={16} className="text-primary-400" />
                              ) : (
                                <Square size={16} />
                              )}
                            </button>
                          )}
                        </th>
                        <th className="px-5 py-4">Fecha / Fuente</th>
                        <th className="px-6 py-4">Concepto / Nombre Limpio</th>
                        <th className="px-5 py-4">Categoría</th>
                        <th className="px-5 py-4">Tags</th>
                        <th className="px-5 py-4 text-right">Monto</th>
                        <th className="px-5 py-4 text-center">Estado</th>
                        <th className="px-5 py-4 text-right">Acción</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {displayedResults.map((t) => {
                        const isSelected = selectedIds.has(t.id);
                        const isSplit = Boolean(t.subTransactions && t.subTransactions.length > 1);
                        const isExpanded = expandedSplits.has(t.id);
                        const fund = matchFund(t, funds);

                        const toggleSplitExpand = (e: React.MouseEvent) => {
                          e.stopPropagation();
                          setExpandedSplits(prev => {
                            const next = new Set(prev);
                            if (next.has(t.id)) next.delete(t.id);
                            else next.add(t.id);
                            return next;
                          });
                        };

                        return (
                          <Fragment key={t.id}>
                            <tr
                              onClick={() => !isSelectionMode && setEditingTransaction(t)}
                              className={`hover:bg-white/[0.03] transition-colors group cursor-pointer ${
                                targetTransaction?.id === t.id ? 'bg-emerald-500/10' : isSelected ? 'bg-primary-500/[0.08]' : ''
                              } ${isExpanded ? 'bg-cyan-950/20' : ''}`}
                            >
                              <td className="px-5 py-4 text-center align-middle" onClick={(e) => e.stopPropagation()}>
                                {isSelectionMode ? (
                                  t.MONTO > 0 ? (
                                    <div
                                      onClick={() => setTargetTransaction(t)}
                                      className={`w-5 h-5 mx-auto rounded-full border flex items-center justify-center cursor-pointer transition-all ${targetTransaction?.id === t.id ? 'border-emerald-500 bg-emerald-500/20' : 'border-white/20 hover:border-white/40'}`}
                                      title="Seleccionar como Objetivo"
                                    >
                                      {targetTransaction?.id === t.id && <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />}
                                    </div>
                                  ) : (
                                    <div
                                      onClick={() => {
                                        const isChecked = selectedExpenses.some(e => e.id === t.id);
                                        if (isChecked) {
                                          setSelectedExpenses(selectedExpenses.filter(e => e.id !== t.id));
                                        } else {
                                          setSelectedExpenses([...selectedExpenses, t]);
                                        }
                                      }}
                                      className={`w-5 h-5 mx-auto rounded border flex items-center justify-center cursor-pointer transition-all ${selectedExpenses.some(e => e.id === t.id) ? 'bg-primary-500 border-primary-500' : 'border-white/20 hover:border-white/40'}`}
                                      title="Seleccionar como Gasto"
                                    >
                                      {selectedExpenses.some(e => e.id === t.id) && <Check size={14} className="text-white" />}
                                    </div>
                                  )
                                ) : (
                                  <button onClick={() => toggleSelectRow(t.id)} className="text-surface-400 hover:text-white">
                                    {isSelected ? <CheckSquare size={16} className="text-primary-400" /> : <Square size={16} />}
                                  </button>
                                )}
                              </td>

                              {/* Date / Source */}
                              <td className="px-5 py-4 text-surface-400 text-xs whitespace-nowrap">
                                <div className="flex flex-col gap-1">
                                  <span className="text-surface-200 font-medium flex items-center gap-1.5">
                                    <Calendar size={12} className="text-surface-500" />
                                    {t.FECHA?.substring(0, 10)}
                                  </span>
                                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded w-fit uppercase tracking-wider ${
                                    t.TIPO?.toUpperCase() === 'TARJETA'
                                      ? 'bg-purple-500/15 text-purple-300 border border-purple-500/20'
                                      : 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/20'
                                  }`}>
                                    {t.TIPO || 'BANCA'}
                                  </span>
                                </div>
                              </td>

                              {/* Concept / Clean Name & Badges */}
                              <td className="px-6 py-4">
                                <div className="flex flex-col gap-1 min-w-0">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className="text-sm font-semibold text-white truncate max-w-md">
                                      {t.nombre_limpio || t.DESCRIPCION}
                                    </span>
                                    {isSplit && (
                                      <button
                                        onClick={toggleSplitExpand}
                                        className={`text-[10px] font-bold px-2 py-0.5 rounded-md flex items-center gap-1 transition-all shrink-0 ${
                                          isExpanded
                                            ? 'bg-cyan-500 text-surface-950 shadow-sm'
                                            : 'bg-cyan-500/15 text-cyan-300 hover:bg-cyan-500/25 border border-cyan-500/30'
                                        }`}
                                        title={isExpanded ? 'Ocultar partes de la división' : 'Ver partes de la división'}
                                      >
                                        <Scissors size={10} />
                                        <span>{t.subTransactions!.length} partes</span>
                                        <ChevronDown size={11} className={`transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
                                      </button>
                                    )}
                                    {t.prioridad && t.prioridad !== '---' && (
                                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border shrink-0 ${
                                        t.prioridad === 'Necesidad'
                                          ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                                          : 'bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/20'
                                      }`}>
                                        {t.prioridad}
                                      </span>
                                    )}
                                    {fund && (
                                      <span
                                        title={`Fondo: ${fund.name}`}
                                        className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-teal-500/15 text-teal-300 border border-teal-500/25 flex items-center gap-1 shrink-0 uppercase tracking-wider"
                                      >
                                        <PiggyBank size={9} /> {fund.name}
                                      </span>
                                    )}
                                  </div>
                                  {t.nombre_limpio && (
                                    <span className="text-xs text-surface-500 truncate max-w-md">
                                      {t.DESCRIPCION}
                                    </span>
                                  )}
                                  {t.nota && (
                                    <span className="text-[11px] text-amber-300/80 italic truncate">
                                      Nota: {t.nota}
                                    </span>
                                  )}
                                </div>
                              </td>

                              {/* Category */}
                              <td className="px-5 py-4">
                                {t.categoria ? (
                                  <span className="px-2.5 py-1 bg-surface-800 border border-white/10 rounded-lg text-xs font-medium text-surface-200">
                                    {t.categoria}
                                  </span>
                                ) : (
                                  <span className="text-xs text-surface-600 italic">Sin categoría</span>
                                )}
                              </td>

                              {/* Tags */}
                              <td className="px-5 py-4">
                                <div className="flex flex-wrap gap-1.5 max-w-xs">
                                  {t.tags ? (
                                    t.tags.split(',').map((tg, i) => (
                                      <span key={i} className="px-2 py-0.5 bg-violet-500/10 border border-violet-500/20 rounded-md text-[11px] font-semibold text-violet-300">
                                        #{tg.trim()}
                                      </span>
                                    ))
                                  ) : (
                                    <span className="text-surface-700 text-xs">-</span>
                                  )}
                                </div>
                              </td>

                              {/* Amount */}
                              <td className={`px-5 py-4 text-right text-sm font-mono font-bold whitespace-nowrap ${t.MONTO >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {t.MONTO >= 0 ? '+' : '−'}${Math.abs(t.MONTO).toLocaleString('es-CO', { minimumFractionDigits: 2 })}
                              </td>

                              {/* Status & Badges */}
                              <td className="px-5 py-4 text-center">
                                <div className="flex flex-col items-center gap-1">
                                  {!t.revisado ? (
                                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/20 uppercase tracking-wide">
                                      sin revisar
                                    </span>
                                  ) : (
                                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 uppercase tracking-wide">
                                      revisado
                                    </span>
                                  )}
                                  {t.es_reembolsable && (
                                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/20">
                                      reembolsable
                                    </span>
                                  )}
                                </div>
                              </td>

                              {/* Actions */}
                              <td className="px-5 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                                <div className="flex items-center justify-end gap-1">
                                  {!t.revisado && (
                                    <button
                                      onClick={async () => {
                                        await markReviewedMutation.mutateAsync(t.id);
                                        await loadData();
                                      }}
                                      className="p-2 rounded-lg text-surface-400 hover:text-emerald-300 hover:bg-emerald-500/10 transition-all"
                                      title="Marcar como revisado"
                                    >
                                      <Check size={16} />
                                    </button>
                                  )}
                                  <button
                                    onClick={() => setEditingTransaction(t)}
                                    className="p-2 rounded-lg text-surface-400 hover:text-primary-300 hover:bg-primary-500/10 transition-all"
                                    title="Editar y etiquetar transaccion"
                                  >
                                    <Pencil size={16} />
                                  </button>
                                </div>
                              </td>
                            </tr>

                            {/* Sub-row: Expandable Split Parts Breakdown */}
                            {isExpanded && isSplit && (
                              <tr key={`${t.id}-expanded`} className="bg-surface-950/70 border-b border-white/5">
                                <td colSpan={8} className="p-0 border-t border-cyan-500/20">
                                  <div className="p-4 pl-12 pr-6 bg-surface-950/80 border-l-4 border-cyan-500 space-y-2.5">
                                    <div className="flex items-center justify-between">
                                      <span className="text-xs font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1.5">
                                        <Scissors size={13} /> Partes de la división ({t.subTransactions!.length})
                                      </span>
                                      <span className="text-[11px] text-surface-400">
                                        Total división: <strong className="text-white font-mono">{t.MONTO >= 0 ? '+' : '−'}${Math.abs(t.MONTO).toLocaleString('es-CO', { minimumFractionDigits: 2 })}</strong>
                                      </span>
                                    </div>
                                    <div className="space-y-1.5">
                                      {t.subTransactions!.map((sub, idx) => (
                                        <div
                                          key={sub.id || idx}
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setEditingTransaction(sub);
                                          }}
                                          className="flex items-center justify-between gap-3 p-2.5 rounded-xl bg-surface-900/90 border border-white/5 hover:border-cyan-500/30 hover:bg-surface-850 transition-all cursor-pointer group/sub"
                                        >
                                          <div className="flex items-center gap-3 min-w-0 flex-1">
                                            <span className="text-[11px] font-mono text-cyan-400/70 font-bold w-5 text-center">
                                              #{idx + 1}
                                            </span>
                                            <div className="flex flex-col min-w-0">
                                              <div className="flex items-center gap-2 flex-wrap">
                                                <span className="text-xs font-medium text-white truncate group-hover/sub:text-cyan-200">
                                                  {sub.nombre_limpio || sub.DESCRIPCION}
                                                </span>
                                                {sub.categoria && sub.categoria !== '---' && (
                                                  <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-surface-800 text-surface-300 border border-white/5">
                                                    {sub.categoria}
                                                  </span>
                                                )}
                                                {sub.prioridad && sub.prioridad !== '---' && (
                                                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${
                                                    sub.prioridad === 'Necesidad'
                                                      ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                                                      : 'bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/20'
                                                  }`}>
                                                    {sub.prioridad}
                                                  </span>
                                                )}
                                                {sub.es_reembolsable && (
                                                  <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-500/15 text-rose-300 border border-rose-500/20">
                                                    reembolsable
                                                  </span>
                                                )}
                                              </div>
                                              {sub.tags && (
                                                <div className="flex flex-wrap gap-1 mt-0.5">
                                                  {sub.tags.split(',').map((tg, i) => (
                                                    <span key={i} className="text-[10px] text-violet-300/80 font-mono">
                                                      #{tg.trim()}
                                                    </span>
                                                  ))}
                                                </div>
                                              )}
                                              {sub.nota && (
                                                <span className="text-[10px] text-amber-300/80 italic truncate mt-0.5">
                                                  Nota: {sub.nota}
                                                </span>
                                              )}
                                            </div>
                                          </div>
                                          <div className="flex items-center gap-3 shrink-0">
                                            <span className={`text-xs font-mono font-bold ${sub.MONTO >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                              {sub.MONTO >= 0 ? '+' : '−'}${Math.abs(sub.MONTO).toLocaleString('es-CO', { minimumFractionDigits: 2 })}
                                            </span>
                                            <Pencil size={13} className="text-surface-500 group-hover/sub:text-cyan-300 transition-colors" />
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </Fragment>
                        );
                      })}
                      {results.length > displayedResults.length && (
                        <tr>
                          <td colSpan={8} className="px-6 py-4 bg-surface-950/40 border-t border-white/5 text-xs text-surface-400">
                            <div className="flex items-center justify-between">
                              <span>Mostrando <strong className="text-white">{displayedResults.length}</strong> de <strong className="text-white">{results.length}</strong> transacciones encontradas</span>
                              <button
                                onClick={() => setRowLimit('all')}
                                className="px-3.5 py-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-primary-300 font-bold transition-all border border-white/5 hover:border-white/10"
                              >
                                Cargar todas ({results.length})
                              </button>
                            </div>
                          </td>
                        </tr>
                      )}
                      {results.length === 0 && (
                        <tr>
                          <td colSpan={8} className="px-6 py-20 text-center">
                            <div className="flex flex-col items-center justify-center gap-3">
                              <div className="p-4 bg-surface-800/50 rounded-full text-surface-500">
                                <Search size={28} />
                              </div>
                              <div>
                                <p className="text-white font-medium text-base">No se encontraron transacciones</p>
                                <p className="text-surface-500 text-xs mt-1">Ajusta o limpia los filtros de búsqueda.</p>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

      </div>

      {/* Full Edit & Labeling Modal */}
      {editingTransaction && (
        <EditModal
          transaction={editingTransaction}
          isOpen={!!editingTransaction}
          onClose={() => setEditingTransaction(null)}
          onSave={async (id, updates) => {
            await updateMutation.mutateAsync({ id, updates });
            setEditingTransaction(null);
            await loadData();
          }}
          categories={categories || []}
          existingTags={tags || []}
        />
      )}

      {/* Bulk Tag Modal */}
      {showBulkTagModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setShowBulkTagModal(false)}>
          <div className="bg-surface-900 border border-white/10 rounded-2xl p-6 w-full max-w-md space-y-4 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-white/5 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Tag size={18} className="text-primary-400" /> Agregar Tags en Masa ({selectedIds.size})
              </h3>
              <button onClick={() => setShowBulkTagModal(false)} className="text-surface-400 hover:text-white"><X size={18} /></button>
            </div>
            <div>
              <label className="block text-xs font-semibold text-surface-400 mb-1.5">Tags (separados por coma)</label>
              <input
                autoFocus
                type="text"
                value={bulkTagInput}
                onChange={e => setBulkTagInput(e.target.value)}
                placeholder="ej: supermercado, viaje, mensual"
                className="w-full bg-surface-950 border border-white/10 rounded-xl px-3.5 py-2.5 text-white text-sm focus:outline-none focus:border-primary-500/50"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowBulkTagModal(false)} className="px-4 py-2 text-xs font-bold text-surface-400 hover:text-white">Cancelar</button>
              <button
                onClick={handleBulkAddTags}
                disabled={bulkLoading || !bulkTagInput.trim()}
                className="px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white text-xs font-bold rounded-xl disabled:opacity-50"
              >
                {bulkLoading ? 'Aplicando...' : 'Aplicar a Seleccionadas'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Category Modal */}
      {showBulkCategoryModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setShowBulkCategoryModal(false)}>
          <div className="bg-surface-900 border border-white/10 rounded-2xl p-6 w-full max-w-md space-y-4 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-white/5 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Filter size={18} className="text-indigo-400" /> Cambiar Categoría en Masa ({selectedIds.size})
              </h3>
              <button onClick={() => setShowBulkCategoryModal(false)} className="text-surface-400 hover:text-white"><X size={18} /></button>
            </div>
            <div>
              <label className="block text-xs font-semibold text-surface-400 mb-1.5">Seleccionar nueva categoría</label>
              <select
                value={bulkCategoryInput}
                onChange={e => setBulkCategoryInput(e.target.value)}
                className="w-full bg-surface-950 border border-white/10 rounded-xl px-3.5 py-2.5 text-white text-sm focus:outline-none focus:border-indigo-500/50"
              >
                <option value="">-- Seleccionar --</option>
                {(categories ?? []).map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowBulkCategoryModal(false)} className="px-4 py-2 text-xs font-bold text-surface-400 hover:text-white">Cancelar</button>
              <button
                onClick={handleBulkSetCategory}
                disabled={bulkLoading || !bulkCategoryInput}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl disabled:opacity-50"
              >
                {bulkLoading ? 'Aplicando...' : 'Aplicar a Seleccionadas'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Auto Payments Modal */}
      {isAutoPaymentsModalOpen && targetTransaction && (
        <AutoPaymentsModal
          targetTransaction={targetTransaction}
          expenseTransactions={selectedExpenses}
          onClose={() => setIsAutoPaymentsModalOpen(false)}
          onSuccess={() => {
            setIsAutoPaymentsModalOpen(false);
            setIsSelectionMode(false);
            setTargetTransaction(null);
            setSelectedExpenses([]);
            loadData();
          }}
        />
      )}
    </div>
  );
}

function StatCard({ label, value, icon, colorClass }: { label: string, value: string, icon: React.ReactNode, colorClass: string }) {
  return (
    <div className="bg-surface-900/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 flex flex-col justify-between h-full hover:border-white/10 transition-colors shadow-lg">
      <div className="flex items-start justify-between mb-4">
        <span className="text-xs text-surface-400 font-semibold uppercase tracking-wider">{label}</span>
        <div className={`p-2.5 rounded-xl border ${colorClass}`}>
          {icon}
        </div>
      </div>
      <p className="text-3xl font-bold text-white tracking-tight">{value}</p>
    </div>
  );
}
