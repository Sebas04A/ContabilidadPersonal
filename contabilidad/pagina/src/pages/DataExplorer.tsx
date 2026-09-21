import { useState, useEffect, useMemo, useCallback, Fragment } from 'react';
import { api, Transaction } from '../services/api';
import { useCategories, useTags, useUpdateTransaction, useMarkAsReviewed, useFunds, useSupabaseDebts, useSupabasePayments, useDeudores } from '../hooks/useTransactions';
import { EditModal } from '../components/EditModal';
import { sortTransactions, groupSplits } from '../utils/groupSplits';
import { matchFund } from '../utils/matchFund';
import {
  DebtSignFilterOption, DebtLinkFilterOption, DebtStatusFilterOption, DebtDirectionFilterOption,
  DebtPeopleModeOption, SIN_PERSONA, buildDebtLookup, applyDebtFilters, debtPerson, personKey, linkedDebtStatus
} from '../utils/debtFilters';
import {
  ReimbursableFilterOption, PriorityFilterOption, TypeFilterOption, LabeledFilterOption, FixedFilterOption,
  applyTransactionFilters, activeFundIds as fundIdsMarcados,
} from '../utils/transactionFilters';
import { FundFilterPanel, fundFilterLabel } from '../components/FundFilterPanel';

import {
  Search, Tag, Filter, ArrowUpRight, ArrowDownRight, Calendar, Info, ChevronDown, ChevronUp, Check,
  List as ListIcon, TrendingUp, Calculator, Pencil, X, Sparkles,
  CheckCircle2, RotateCcw, SlidersHorizontal, Sliders, CheckSquare, Square,
  ArrowUpDown, Scissors, PiggyBank, BarChart3, Layers, Scale, Ban, HandCoins
} from 'lucide-react';
import AutoPaymentsModal from '../components/AutoPaymentsModal';
import { ExplorerAnalyticsModal, ExplorerAnalyticsContent } from '../components/ExplorerAnalyticsModal';
import { ExplorerExclusionsModal } from '../components/ExplorerExclusionsModal';
import { money, signedMoney } from '../utils/format';
import { parseTags } from '../utils/tags';

export type SortByOption = 'date_desc' | 'date_asc' | 'amount_desc' | 'amount_asc';
export type StructureFilterOption = 'all' | 'split' | 'grouped' | 'simple';

const EXPLORER_STORAGE_KEY = 'explorer_filter_settings';

interface ExplorerStoredSettings {
  searchText?: string;
  categoryFilter?: string;
  tagFilter?: string;
  sourceTypeFilter?: string;
  pendingOnlyFilter?: boolean;
  startDate?: string;
  endDate?: string;
  rowLimit?: number | 'all';
  sortBy?: SortByOption;
  groupSplitsMode?: boolean;
  structureFilter?: StructureFilterOption;
  reimbursableFilter?: ReimbursableFilterOption;
  priorityFilter?: PriorityFilterOption;
  typeFilter?: TypeFilterOption;
  labeledFilter?: LabeledFilterOption;
  selectedFunds?: string[] | null;
  excludedCategories?: string[];
  excludedTags?: string[];
  fixedFilter?: FixedFilterOption;
  debtSignFilter?: DebtSignFilterOption;
  /** Formato viejo: una sola persona. Se lee para migrar a debtPeopleFilter. */
  debtPersonFilter?: string;
  debtPeopleFilter?: string[];
  debtPeopleMode?: DebtPeopleModeOption;
  debtLinkFilter?: DebtLinkFilterOption;
  debtStatusFilter?: DebtStatusFilterOption;
  debtDirectionFilter?: DebtDirectionFilterOption;
}

const getStoredSettings = (): ExplorerStoredSettings => {
  try {
    const saved = localStorage.getItem(EXPLORER_STORAGE_KEY);
    if (saved) return JSON.parse(saved);
  } catch (e) {
    console.error('Error reading explorer filters from localStorage', e);
  }
  return {};
};

export function DataExplorer() {
  const [viewMode, setViewMode] = useState<'list' | 'analysis'>('list'); // UI Mode
  const [savedSettings] = useState<ExplorerStoredSettings>(getStoredSettings);

  // Filter States (initialized from localStorage if present)
  const [searchText, setSearchText] = useState(savedSettings.searchText ?? '');
  const [categoryFilter, setCategoryFilter] = useState(savedSettings.categoryFilter ?? '');
  const [tagFilter, setTagFilter] = useState(savedSettings.tagFilter ?? '');
  const [sourceTypeFilter, setSourceTypeFilter] = useState(savedSettings.sourceTypeFilter ?? '');
  const [pendingOnlyFilter, setPendingOnlyFilter] = useState(savedSettings.pendingOnlyFilter ?? false);
  const [startDate, setStartDate] = useState(savedSettings.startDate ?? '');
  const [endDate, setEndDate] = useState(savedSettings.endDate ?? '');
  const [rowLimit, setRowLimit] = useState<number | 'all'>(savedSettings.rowLimit ?? 50);

  // Budget-style and Explorer feature states
  const [sortBy, setSortBy] = useState<SortByOption>(savedSettings.sortBy ?? 'date_desc');
  const [groupSplitsMode, setGroupSplitsMode] = useState(savedSettings.groupSplitsMode ?? true);
  const [structureFilter, setStructureFilter] = useState<StructureFilterOption>(savedSettings.structureFilter ?? 'all');
  const [reimbursableFilter, setReimbursableFilter] = useState<ReimbursableFilterOption>(savedSettings.reimbursableFilter ?? 'all');
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilterOption>(savedSettings.priorityFilter ?? 'all');
  const [typeFilter, setTypeFilter] = useState<TypeFilterOption>(savedSettings.typeFilter ?? 'all');
  const [labeledFilter, setLabeledFilter] = useState<LabeledFilterOption>(savedSettings.labeledFilter ?? 'all');
  const [selectedFunds, setSelectedFunds] = useState<string[] | null>(savedSettings.selectedFunds ?? null);
  const [showFundFilter, setShowFundFilter] = useState(false);
  const [expandedSplits, setExpandedSplits] = useState<Set<string>>(new Set());
  const [showAnalyticsModal, setShowAnalyticsModal] = useState(false);
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(true);

  // Exclusion filters (Presupuesto-style)
  const [excludedCategories, setExcludedCategories] = useState<string[]>(savedSettings.excludedCategories ?? []);
  const [excludedTags, setExcludedTags] = useState<string[]>(savedSettings.excludedTags ?? []);
  const [fixedFilter, setFixedFilter] = useState<FixedFilterOption>(savedSettings.fixedFilter ?? 'all');
  const [showExclusionModal, setShowExclusionModal] = useState(false);

  // Filtros de Deudas (persona, vínculo con Supabase, estado de pago)
  const [debtSignFilter, setDebtSignFilter] = useState<DebtSignFilterOption>(savedSettings.debtSignFilter ?? 'all');
  const [debtPeopleFilter, setDebtPeopleFilter] = useState<string[]>(
    savedSettings.debtPeopleFilter
      ?? (savedSettings.debtPersonFilter ? [savedSettings.debtPersonFilter === SIN_PERSONA ? SIN_PERSONA : savedSettings.debtPersonFilter.toLowerCase()] : [])
  );
  const [debtPeopleMode, setDebtPeopleMode] = useState<DebtPeopleModeOption>(savedSettings.debtPeopleMode ?? 'include');
  const [showPeopleFilter, setShowPeopleFilter] = useState(false);

  const toggleDebtPerson = (key: string) => {
    setDebtPeopleFilter(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]);
  };
  const [debtLinkFilter, setDebtLinkFilter] = useState<DebtLinkFilterOption>(savedSettings.debtLinkFilter ?? 'all');
  const [debtStatusFilter, setDebtStatusFilter] = useState<DebtStatusFilterOption>(savedSettings.debtStatusFilter ?? 'all');
  const [debtDirectionFilter, setDebtDirectionFilter] = useState<DebtDirectionFilterOption>(savedSettings.debtDirectionFilter ?? 'all');

  // Exclusion toggle handlers
  const handleToggleExcludedCategory = (cat: string) => {
    setExcludedCategories(prev => {
      if (prev.includes(cat)) {
        return prev.filter(c => c !== cat);
      }
      return [...prev, cat];
    });
  };

  const handleToggleExcludedTag = (tag: string) => {
    setExcludedTags(prev => {
      if (prev.includes(tag)) {
        return prev.filter(t => t !== tag);
      }
      return [...prev, tag];
    });
  };

  // Data States
  const [rawTransactions, setRawTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);

  // Queries & Mutations
  const { data: categories } = useCategories();
  const { data: tags } = useTags();
  const { data: funds } = useFunds();
  // Devengo: contar lo que consumí, no lo que se movió. Ver PLAN_DEUDAS_COMO_GASTO.md.
  const [devengo, setDevengo] = useState(false);
  const { data: supabaseDebts } = useSupabaseDebts();
  const { data: supabasePayments } = useSupabasePayments();
  const { data: deudores } = useDeudores();
  const debtLookup = useMemo(() => buildDebtLookup(supabaseDebts, supabasePayments), [supabaseDebts, supabasePayments]);
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
        searchText.trim() || undefined,
        undefined, // category
        undefined, // tag
        devengo,
      );

      setRawTransactions(data);
    } catch (error) {
      console.error("Error loading transactions in DataExplorer", error);
    } finally {
      setLoading(false);
    }
  }, [searchText, startDate, endDate, devengo]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Client-side filtering, splitting and sorting
  const results = useMemo(() => {
    let list = rawTransactions;

    // 1-11. Categoría, tag, fuente, reembolsables, prioridad, revisado, tipo, fondos,
    // exclusiones y gastos fijos: las mismas reglas que el presupuesto.
    list = applyTransactionFilters(list, {
      includedCategories: categoryFilter ? [categoryFilter] : [],
      excludedCategories,
      includedTags: tagFilter ? [tagFilter] : [],
      excludedTags,
      selectedFunds,
      reimbursable: reimbursableFilter,
      priority: priorityFilter,
      labeled: pendingOnlyFilter ? 'unlabeled' : labeledFilter,
      type: typeFilter,
      fixed: fixedFilter,
      sourceType: sourceTypeFilter,
    }, funds);

    // 12. Filtros de Deudas (signo, persona, vínculo, estado de pago, dirección)
    list = applyDebtFilters(list, {
      sign: debtSignFilter,
      people: debtPeopleFilter,
      peopleMode: debtPeopleMode,
      link: debtLinkFilter,
      status: debtStatusFilter,
      direction: debtDirectionFilter,
    }, debtLookup);

    // 12b. Agrupación de Splits
    if (groupSplitsMode) {
      list = groupSplits(list);
    }

    // 13. Filtro de Estructura (Divisiones y Grupos)
    if (structureFilter === 'split') {
      list = list.filter(t => (t.subTransactions && t.subTransactions.length > 1) || (t.split_group_id && t.split_group_id.trim() !== ''));
    } else if (structureFilter === 'grouped') {
      list = list.filter(t => t.group_id && t.group_id.trim() !== '');
    } else if (structureFilter === 'simple') {
      list = list.filter(t => (!t.subTransactions || t.subTransactions.length <= 1) && (!t.split_group_id || t.split_group_id.trim() === '') && (!t.group_id || t.group_id.trim() === ''));
    }

    // 14. Ordenación
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
  }, [
    rawTransactions,
    categoryFilter,
    tagFilter,
    sourceTypeFilter,
    reimbursableFilter,
    priorityFilter,
    pendingOnlyFilter,
    labeledFilter,
    typeFilter,
    selectedFunds,
    funds,
    groupSplitsMode,
    structureFilter,
    sortBy,
    excludedCategories,
    excludedTags,
    fixedFilter,
    debtSignFilter,
    debtPeopleFilter,
    debtPeopleMode,
    debtLinkFilter,
    debtStatusFilter,
    debtDirectionFilter,
    debtLookup
  ]);

  // Personas para el filtro: las de Supabase más cualquier `deudor` escrito al etiquetar
  // (con cuántas transacciones del rango aparece cada una)
  const debtPeople = useMemo(() => {
    const byKey = new Map<string, { key: string; name: string; count: number }>();
    (deudores ?? []).forEach(d => {
      if (d.nombre) byKey.set(personKey(d.nombre), { key: personKey(d.nombre), name: d.nombre, count: 0 });
    });
    rawTransactions.forEach(t => {
      const rows = t.subTransactions && t.subTransactions.length > 0 ? t.subTransactions : [t];
      rows.forEach(row => {
        const p = debtPerson(row, debtLookup);
        if (!p) return;
        const entry = byKey.get(personKey(p)) ?? { key: personKey(p), name: p, count: 0 };
        entry.count += 1;
        byKey.set(entry.key, entry);
      });
    });
    return Array.from(byKey.values()).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'es'));
  }, [deudores, rawTransactions, debtLookup]);

  const debtPeopleNames = useMemo(() => new Map(debtPeople.map(p => [p.key, p.name])), [debtPeople]);
  const personLabel = (key: string) => key === SIN_PERSONA ? 'Sin persona' : debtPeopleNames.get(key) ?? key;

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

  // Auto Payments / Selection State
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [targetTransaction, setTargetTransaction] = useState<Transaction | null>(null);
  const [selectedExpenses, setSelectedExpenses] = useState<Transaction[]>([]);
  const [isAutoPaymentsModalOpen, setIsAutoPaymentsModalOpen] = useState(false);

  // Save filters to localStorage whenever they change
  useEffect(() => {
    try {
      const settings: ExplorerStoredSettings = {
        searchText,
        categoryFilter,
        tagFilter,
        sourceTypeFilter,
        pendingOnlyFilter,
        startDate,
        endDate,
        rowLimit,
        sortBy,
        groupSplitsMode,
        structureFilter,
        reimbursableFilter,
        priorityFilter,
        typeFilter,
        labeledFilter,
        selectedFunds,
        excludedCategories,
        excludedTags,
        fixedFilter,
        debtSignFilter,
        debtPeopleFilter,
        debtPeopleMode,
        debtLinkFilter,
        debtStatusFilter,
        debtDirectionFilter,
      };
      localStorage.setItem(EXPLORER_STORAGE_KEY, JSON.stringify(settings));
    } catch (e) {
      console.error('Error saving explorer filters to localStorage', e);
    }
  }, [
    searchText,
    categoryFilter,
    tagFilter,
    sourceTypeFilter,
    pendingOnlyFilter,
    startDate,
    endDate,
    rowLimit,
    sortBy,
    groupSplitsMode,
    structureFilter,
    reimbursableFilter,
    priorityFilter,
    typeFilter,
    labeledFilter,
    selectedFunds,
    excludedCategories,
    excludedTags,
    fixedFilter,
    debtSignFilter,
    debtPeopleFilter,
    debtPeopleMode,
    debtLinkFilter,
    debtStatusFilter,
    debtDirectionFilter,
  ]);

  const resetDebtFilters = () => {
    setReimbursableFilter('all');
    setDebtSignFilter('all');
    setDebtPeopleFilter([]);
    setDebtPeopleMode('include');
    setDebtLinkFilter('all');
    setDebtStatusFilter('all');
    setDebtDirectionFilter('all');
  };

  // Reset all filters
  const handleResetFilters = () => {
    try {
      localStorage.removeItem(EXPLORER_STORAGE_KEY);
    } catch (e) {
      console.error('Error clearing explorer filters from localStorage', e);
    }
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
    setPriorityFilter('all');
    setTypeFilter('all');
    setLabeledFilter('all');
    setSelectedFunds(null);
    setExcludedCategories([]);
    setExcludedTags([]);
    setFixedFilter('all');
    resetDebtFilters();
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
      const newTagList = parseTags(bulkTagInput);
      for (const id of selectedIds) {
        const tx = results.find(r => r.id === id);
        if (!tx) continue;
        const current = parseTags(tx.tags);
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

  const totalExclusionsCount =
    excludedCategories.length +
    excludedTags.length +
    (fixedFilter !== 'all' ? 1 : 0);

  const debtFiltersCount =
    (reimbursableFilter !== 'all' ? 1 : 0) +
    (debtSignFilter !== 'all' ? 1 : 0) +
    (debtPeopleFilter.length > 0 ? 1 : 0) +
    (debtLinkFilter !== 'all' ? 1 : 0) +
    (debtStatusFilter !== 'all' ? 1 : 0) +
    (debtDirectionFilter !== 'all' ? 1 : 0);

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
    (priorityFilter !== 'all' ? 1 : 0) +
    (typeFilter !== 'all' ? 1 : 0) +
    (selectedFunds !== null ? 1 : 0) +
    debtFiltersCount +
    totalExclusionsCount;

  const activeFundIds = fundIdsMarcados(selectedFunds, funds);

  // Active filter chips list for visual badges and one-click removal
  const activeFilterChips = useMemo(() => {
    const chips: { key: string; label: string; value: string; color: string; onRemove: () => void }[] = [];

    if (searchText.trim()) {
      chips.push({
        key: 'search',
        label: 'Búsqueda',
        value: `"${searchText.trim()}"`,
        color: 'bg-primary-500/15 text-primary-300 border-primary-500/30',
        onRemove: () => setSearchText(''),
      });
    }

    if (categoryFilter === '__sin_categoria__') {
      chips.push({
        key: 'category_uncat',
        label: 'Categoría',
        value: 'Sin categoría',
        color: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
        onRemove: () => setCategoryFilter(''),
      });
    } else if (categoryFilter) {
      chips.push({
        key: 'category',
        label: 'Categoría',
        value: categoryFilter,
        color: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
        onRemove: () => setCategoryFilter(''),
      });
    }

    if (tagFilter === '__sin_tags__') {
      chips.push({
        key: 'tag_untagged',
        label: 'Tag',
        value: 'Sin tags',
        color: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
        onRemove: () => setTagFilter(''),
      });
    } else if (tagFilter) {
      chips.push({
        key: 'tag',
        label: 'Tag',
        value: `#${tagFilter}`,
        color: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
        onRemove: () => setTagFilter(''),
      });
    }

    if (labeledFilter === 'unlabeled' || pendingOnlyFilter) {
      chips.push({
        key: 'labeled_unlabeled',
        label: 'Estado',
        value: 'Sin Revisar',
        color: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
        onRemove: () => {
          setLabeledFilter('all');
          setPendingOnlyFilter(false);
        },
      });
    } else if (labeledFilter === 'labeled') {
      chips.push({
        key: 'labeled_labeled',
        label: 'Estado',
        value: 'Revisadas',
        color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
        onRemove: () => setLabeledFilter('all'),
      });
    }

    if (priorityFilter === 'needs') {
      chips.push({
        key: 'priority_needs',
        label: 'Prioridad',
        value: 'Necesidades',
        color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
        onRemove: () => setPriorityFilter('all'),
      });
    } else if (priorityFilter === 'wants') {
      chips.push({
        key: 'priority_wants',
        label: 'Prioridad',
        value: 'Deseos',
        color: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
        onRemove: () => setPriorityFilter('all'),
      });
    } else if (priorityFilter === 'rated') {
      chips.push({
        key: 'priority_rated',
        label: 'Prioridad',
        value: 'Clasificadas',
        color: 'bg-surface-800 text-surface-200 border-white/10',
        onRemove: () => setPriorityFilter('all'),
      });
    } else if (priorityFilter === 'unrated') {
      chips.push({
        key: 'priority_unrated',
        label: 'Prioridad',
        value: 'Sin clasificar',
        color: 'bg-surface-800 text-surface-400 border-white/10',
        onRemove: () => setPriorityFilter('all'),
      });
    }

    if (reimbursableFilter === 'included') {
      chips.push({
        key: 'reimbursable_inc',
        label: 'Reembolso',
        value: 'Solo Reembolsables',
        color: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
        onRemove: () => setReimbursableFilter('all'),
      });
    } else if (reimbursableFilter === 'excluded') {
      chips.push({
        key: 'reimbursable_exc',
        label: 'Reembolso',
        value: 'Sin Reembolsables',
        color: 'bg-surface-800 text-surface-300 border-white/10',
        onRemove: () => setReimbursableFilter('all'),
      });
    }

    if (debtSignFilter !== 'all') {
      chips.push({
        key: 'debt_sign',
        label: 'Deudas',
        value: debtSignFilter === 'positive' ? 'Montos positivos' : 'Montos negativos',
        color: debtSignFilter === 'positive'
          ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
          : 'bg-rose-500/15 text-rose-300 border-rose-500/30',
        onRemove: () => setDebtSignFilter('all'),
      });
    }

    debtPeopleFilter.forEach(key => {
      const excluding = debtPeopleMode === 'exclude';
      chips.push({
        key: `debt_person_${key}`,
        label: excluding ? '🚫 Excluir Persona' : 'Persona',
        value: personLabel(key),
        color: excluding
          ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
          : 'bg-orange-500/15 text-orange-300 border-orange-500/30',
        onRemove: () => toggleDebtPerson(key),
      });
    });

    if (debtLinkFilter !== 'all') {
      const linkLabels: Record<DebtLinkFilterOption, string> = {
        all: '',
        deuda: 'Vinculadas a deuda',
        pago: 'Vinculadas a pago',
        linked: 'Con vínculo',
        unlinked: 'Reembolsables sin vincular',
      };
      chips.push({
        key: 'debt_link',
        label: 'Vínculo',
        value: linkLabels[debtLinkFilter],
        color: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
        onRemove: () => setDebtLinkFilter('all'),
      });
    }

    if (debtStatusFilter !== 'all') {
      const statusLabels: Record<DebtStatusFilterOption, string> = {
        all: '',
        paid: 'Pagadas',
        pending: 'Pendientes',
        partial: 'Abonadas a medias',
      };
      chips.push({
        key: 'debt_status',
        label: 'Pago',
        value: statusLabels[debtStatusFilter],
        color: debtStatusFilter === 'paid'
          ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
          : 'bg-amber-500/15 text-amber-300 border-amber-500/30',
        onRemove: () => setDebtStatusFilter('all'),
      });
    }

    if (debtDirectionFilter !== 'all') {
      chips.push({
        key: 'debt_direction',
        label: 'Dirección',
        value: debtDirectionFilter === 'me_deben' ? 'Me deben' : 'Yo debo',
        color: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
        onRemove: () => setDebtDirectionFilter('all'),
      });
    }

    if (typeFilter === 'expenses') {
      chips.push({
        key: 'type_exp',
        label: 'Tipo',
        value: 'Solo Gastos',
        color: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
        onRemove: () => setTypeFilter('all'),
      });
    } else if (typeFilter === 'income') {
      chips.push({
        key: 'type_inc',
        label: 'Tipo',
        value: 'Solo Ingresos',
        color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
        onRemove: () => setTypeFilter('all'),
      });
    }

    if (sourceTypeFilter) {
      chips.push({
        key: 'source',
        label: 'Fuente',
        value: sourceTypeFilter,
        color: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
        onRemove: () => setSourceTypeFilter(''),
      });
    }

    if (structureFilter === 'split') {
      chips.push({
        key: 'struct_split',
        label: 'Estructura',
        value: 'Splits',
        color: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
        onRemove: () => setStructureFilter('all'),
      });
    } else if (structureFilter === 'grouped') {
      chips.push({
        key: 'struct_grouped',
        label: 'Estructura',
        value: 'Agrupadas',
        color: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
        onRemove: () => setStructureFilter('all'),
      });
    } else if (structureFilter === 'simple') {
      chips.push({
        key: 'struct_simple',
        label: 'Estructura',
        value: 'Simples',
        color: 'bg-surface-800 text-surface-300 border-white/10',
        onRemove: () => setStructureFilter('all'),
      });
    }

    if (!groupSplitsMode) {
      chips.push({
        key: 'splits_ungrouped',
        label: 'Splits',
        value: 'Partes individuales',
        color: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
        onRemove: () => setGroupSplitsMode(true),
      });
    }

    if (startDate || endDate) {
      chips.push({
        key: 'date_range',
        label: 'Fecha',
        value: `${startDate || '...'} → ${endDate || '...'}`,
        color: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
        onRemove: () => {
          setStartDate('');
          setEndDate('');
        },
      });
    }

    if (selectedFunds !== null) {
      chips.push({
        key: 'funds',
        label: 'Fondos',
        value: `${activeFundIds.length} activo(s)`,
        color: 'bg-teal-500/15 text-teal-300 border-teal-500/30',
        onRemove: () => setSelectedFunds(null),
      });
    }

    if (sortBy !== 'date_desc') {
      const sortLabels: Record<SortByOption, string> = {
        date_desc: 'Más reciente',
        date_asc: 'Más antigua',
        amount_desc: 'Mayor monto',
        amount_asc: 'Menor monto',
      };
      chips.push({
        key: 'sort',
        label: 'Orden',
        value: sortLabels[sortBy],
        color: 'bg-primary-500/15 text-primary-300 border-primary-500/30',
        onRemove: () => setSortBy('date_desc'),
      });
    }

    // Exclusion chips (Categories)
    excludedCategories.forEach(cat => {
      const displayVal = cat === '__sin_categoria__' ? 'Sin categoría' : cat;
      chips.push({
        key: `exclude_cat_${cat}`,
        label: '🚫 Excluir Cat',
        value: displayVal,
        color: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
        onRemove: () => handleToggleExcludedCategory(cat),
      });
    });

    // Exclusion chips (Tags)
    excludedTags.forEach(tg => {
      const displayVal = tg === '__sin_tags__' ? 'Sin etiqueta' : `#${tg}`;
      chips.push({
        key: `exclude_tag_${tg}`,
        label: '🚫 Excluir Tag',
        value: displayVal,
        color: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
        onRemove: () => handleToggleExcludedTag(tg),
      });
    });

    // Exclusion chip (Fixed Expenses)
    if (fixedFilter === 'fixed') {
      chips.push({
        key: 'fixed_only',
        label: 'Fijo',
        value: 'Solo Gastos Fijos',
        color: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
        onRemove: () => setFixedFilter('all'),
      });
    } else if (fixedFilter === 'non_fixed') {
      chips.push({
        key: 'fixed_exc',
        label: '🚫 Excluir',
        value: 'Gastos Fijos',
        color: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
        onRemove: () => setFixedFilter('all'),
      });
    }

    return chips;
  }, [
    searchText,
    categoryFilter,
    tagFilter,
    labeledFilter,
    pendingOnlyFilter,
    priorityFilter,
    reimbursableFilter,
    typeFilter,
    sourceTypeFilter,
    structureFilter,
    groupSplitsMode,
    startDate,
    endDate,
    selectedFunds,
    activeFundIds,
    sortBy,
    excludedCategories,
    excludedTags,
    fixedFilter,
    debtSignFilter,
    debtPeopleFilter,
    debtPeopleMode,
    debtPeopleNames,
    debtLinkFilter,
    debtStatusFilter,
    debtDirectionFilter,
  ]);

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
        <div className="bg-gradient-to-b from-surface-900/60 to-surface-950/70 backdrop-blur-xl border border-white/10 rounded-3xl p-5 md:p-6 shadow-2xl space-y-4">
          
          {/* Header & Controls Bar */}
          <div className="flex items-center justify-between gap-4 flex-wrap pb-4 border-b border-white/5">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-primary-500/10 border border-primary-500/20 text-primary-400">
                <SlidersHorizontal size={18} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-white tracking-wide">Filtros y Búsqueda</h2>
                  {activeFiltersCount > 0 && (
                    <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-primary-500/20 text-primary-300 border border-primary-500/30 animate-in fade-in">
                      {activeFiltersCount} activo{activeFiltersCount > 1 ? 's' : ''}
                    </span>
                  )}
                </div>
                <p className="text-xs text-surface-400">
                  <strong className="text-white font-semibold">{results.length}</strong> de <span className="text-surface-300">{rawTransactions.length}</span> transacciones encontradas
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5 flex-wrap">
              {/* Analytics Modal Button */}
              <button
                onClick={() => setShowAnalyticsModal(true)}
                className="flex items-center gap-2 px-3.5 py-2 bg-gradient-to-r from-primary-600 via-indigo-600 to-violet-600 hover:from-primary-500 hover:to-violet-500 text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-primary-900/25 hover:scale-[1.02] active:scale-[0.98]"
                title="Abrir modal con analíticas detalladas y KPIs de las transacciones filtradas"
              >
                <BarChart3 size={15} /> Ver Analíticas ({results.length})
              </button>

              {/* Exclusion Modal Button */}
              <button
                onClick={() => setShowExclusionModal(true)}
                className={`flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold rounded-xl transition-all border shadow-sm ${
                  totalExclusionsCount > 0
                    ? 'bg-rose-500/20 border-rose-500/50 text-rose-300 shadow-rose-950/30 hover:bg-rose-500/30'
                    : 'bg-surface-950/60 border-white/5 text-surface-300 hover:text-white hover:border-white/10'
                }`}
                title="Abrir modal de filtros de exclusión (ocultar categorías, etiquetas, gastos fijos o reembolsables)"
              >
                <Ban size={14} className={totalExclusionsCount > 0 ? 'text-rose-400' : 'text-surface-400'} />
                <span>Exclusiones</span>
                {totalExclusionsCount > 0 && (
                  <span className="px-1.5 py-0.2 bg-rose-500 text-white rounded-full text-[10px] font-bold">
                    {totalExclusionsCount}
                  </span>
                )}
              </button>

              {/* Toggle Advanced Filters */}
              <button
                onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-xl border transition-all ${
                  showAdvancedFilters
                    ? 'bg-surface-800 text-white border-white/10'
                    : 'bg-surface-950/60 text-surface-400 border-white/5 hover:text-white'
                }`}
                title={showAdvancedFilters ? 'Ocultar secciones de filtros' : 'Mostrar todas las secciones de filtros'}
              >
                {showAdvancedFilters ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                <span>{showAdvancedFilters ? 'Menos filtros' : 'Más filtros'}</span>
              </button>

              {/* Reset All */}
              {activeFiltersCount > 0 && (
                <button
                  onClick={handleResetFilters}
                  className="flex items-center gap-1.5 text-xs font-semibold text-surface-400 hover:text-rose-400 transition-colors px-3 py-2 rounded-xl hover:bg-rose-500/10 hover:border-rose-500/20 border border-transparent"
                  title="Restablecer todos los filtros a sus valores predeterminados"
                >
                  <RotateCcw size={14} /> Limpiar todo
                </button>
              )}
            </div>
          </div>

          {/* Tier 1: Search, Dates, Sorting and Limits */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-center">
            {/* Search Input */}
            <div className="relative lg:col-span-5">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-surface-400" size={17} />
              <input
                type="text"
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
                placeholder="Buscar por concepto, comercio, notas, tags..."
                className="w-full bg-surface-950 border border-white/10 rounded-xl pl-10 pr-9 py-2.5 text-white text-sm focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/30 placeholder:text-surface-500 transition-all"
              />
              {searchText && (
                <button
                  onClick={() => setSearchText('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-white p-0.5 rounded-md hover:bg-white/10 transition-colors"
                  title="Borrar búsqueda"
                >
                  <X size={14} />
                </button>
              )}
            </div>

            {/* Date Range Inputs */}
            <div className="lg:col-span-4 flex items-center gap-1.5 bg-surface-950 border border-white/10 rounded-xl px-3 py-1.5 focus-within:border-primary-500/50 transition-all">
              <Calendar size={15} className="text-primary-400 shrink-0" />
              <input
                type="date"
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
                className="bg-transparent border-none text-xs text-white focus:ring-0 p-0 font-mono w-full cursor-pointer"
                title="Fecha desde"
              />
              <span className="text-surface-600 text-xs px-0.5">→</span>
              <input
                type="date"
                value={endDate}
                onChange={e => setEndDate(e.target.value)}
                className="bg-transparent border-none text-xs text-white focus:ring-0 p-0 font-mono w-full cursor-pointer"
                title="Fecha hasta"
              />
              {(startDate || endDate) && (
                <button
                  onClick={() => { setStartDate(''); setEndDate(''); }}
                  className="text-surface-500 hover:text-white p-0.5 transition-colors"
                  title="Limpiar fechas"
                >
                  <X size={13} />
                </button>
              )}
            </div>

            {/* Sort Selector */}
            <div className="relative lg:col-span-2">
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value as SortByOption)}
                className={`w-full bg-surface-950 border rounded-xl pl-8 pr-7 py-2.5 text-xs font-semibold focus:outline-none appearance-none cursor-pointer transition-all ${
                  sortBy !== 'date_desc'
                    ? 'border-primary-500/60 text-primary-300 ring-1 ring-primary-500/30'
                    : 'border-white/10 text-surface-200'
                }`}
                title="Elegir orden de transacciones"
              >
                <option value="date_desc" className="bg-surface-900 text-white">📅 Más reciente</option>
                <option value="date_asc" className="bg-surface-900 text-white">📅 Más antigua</option>
                <option value="amount_desc" className="bg-surface-900 text-white">💎 Mayor monto</option>
                <option value="amount_asc" className="bg-surface-900 text-white">🔹 Menor monto</option>
              </select>
              <ArrowUpDown className="absolute left-2.5 top-1/2 -translate-y-1/2 text-primary-400 pointer-events-none" size={13} />
              <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={14} />
            </div>

            {/* Row Limit */}
            <div className="relative lg:col-span-1">
              <select
                value={rowLimit}
                onChange={e => setRowLimit(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                className="w-full bg-surface-950 border border-white/10 rounded-xl px-2 py-2.5 text-surface-300 text-xs font-medium focus:outline-none appearance-none text-center cursor-pointer hover:border-white/20 transition-all"
                title="Límite de transacciones visibles"
              >
                <option value={50} className="bg-surface-900 text-white">50 filas</option>
                <option value={100} className="bg-surface-900 text-white">100 filas</option>
                <option value={200} className="bg-surface-900 text-white">200 filas</option>
                <option value="all" className="bg-surface-900 text-white">Todas ({results.length})</option>
              </select>
              <ChevronDown className="absolute right-1.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={12} />
            </div>
          </div>

          {/* Structured Filter Cards */}
          {showAdvancedFilters && (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3.5 pt-2 border-t border-white/5 animate-in fade-in duration-200">
              
              {/* Card 1: Categorización & Tags */}
              <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-3.5 space-y-2.5">
                <div className="flex items-center gap-2 pb-1 border-b border-white/5">
                  <Layers size={14} className="text-indigo-400" />
                  <span className="text-xs font-bold text-surface-200 tracking-wide">Categorización & Tags</span>
                </div>

                {/* Categoría */}
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Categoría</label>
                  <div className="relative">
                    <select
                      value={categoryFilter}
                      onChange={e => setCategoryFilter(e.target.value)}
                      className={`w-full bg-surface-900 border rounded-xl px-3 py-2 text-xs focus:outline-none appearance-none cursor-pointer transition-all ${
                        categoryFilter
                          ? 'border-indigo-500/60 text-indigo-300 ring-1 ring-indigo-500/30 font-medium'
                          : 'border-white/10 text-surface-300'
                      }`}
                    >
                      <option value="" className="bg-surface-900 text-white">Todas las categorías</option>
                      <option value="__sin_categoria__" className="bg-surface-900 text-amber-300 font-semibold">⚪ Sin categoría</option>
                      {(categories ?? []).map(c => (
                        <option key={c} value={c} className="bg-surface-900 text-white">{c}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={13} />
                  </div>
                </div>

                {/* Tags */}
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Etiqueta (Tag)</label>
                  <div className="relative">
                    <select
                      value={tagFilter}
                      onChange={e => setTagFilter(e.target.value)}
                      className={`w-full bg-surface-900 border rounded-xl px-3 py-2 text-xs focus:outline-none appearance-none cursor-pointer transition-all ${
                        tagFilter
                          ? 'border-violet-500/60 text-violet-300 ring-1 ring-violet-500/30 font-medium'
                          : 'border-white/10 text-surface-300'
                      }`}
                    >
                      <option value="" className="bg-surface-900 text-white">Todos los tags</option>
                      <option value="__sin_tags__" className="bg-surface-900 text-amber-300 font-semibold">⚪ Sin tags / Sin etiquetas</option>
                      {(tags ?? []).map(t => (
                        <option key={t} value={t} className="bg-surface-900 text-white">#{t}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={13} />
                  </div>
                </div>

                {/* Estado de Revisión */}
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Estado de Auditoría</label>
                  <div className="relative">
                    <select
                      value={labeledFilter}
                      onChange={e => {
                        const val = e.target.value as LabeledFilterOption;
                        setLabeledFilter(val);
                        if (val === 'unlabeled') setPendingOnlyFilter(true);
                        else setPendingOnlyFilter(false);
                      }}
                      className={`w-full bg-surface-900 border rounded-xl px-3 py-2 text-xs focus:outline-none appearance-none cursor-pointer transition-all ${
                        labeledFilter !== 'all'
                          ? 'border-amber-500/60 text-amber-300 ring-1 ring-amber-500/30 font-medium'
                          : 'border-white/10 text-surface-300'
                      }`}
                    >
                      <option value="all" className="bg-surface-900 text-white">Todas las transacciones</option>
                      <option value="unlabeled" className="bg-surface-900 text-amber-300 font-semibold">
                        ⏳ Solo Sin Revisar {unreviewedCount > 0 ? `(${unreviewedCount})` : ''}
                      </option>
                      <option value="labeled" className="bg-surface-900 text-emerald-300 font-semibold">✅ Solo Revisadas</option>
                    </select>
                    <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={13} />
                  </div>
                </div>
              </div>

              {/* Card 2: Presupuesto & Prioridades */}
              <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-3.5 space-y-2.5">
                <div className="flex items-center gap-2 pb-1 border-b border-white/5">
                  <Scale size={14} className="text-amber-400" />
                  <span className="text-xs font-bold text-surface-200 tracking-wide">Presupuesto & Prioridad</span>
                </div>

                {/* Prioridad */}
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Prioridad (Gastos)</label>
                  <div className="relative">
                    <select
                      value={priorityFilter}
                      onChange={e => setPriorityFilter(e.target.value as PriorityFilterOption)}
                      className={`w-full bg-surface-900 border rounded-xl px-3 py-2 text-xs focus:outline-none appearance-none cursor-pointer transition-all ${
                        priorityFilter !== 'all'
                          ? 'border-amber-400/60 text-amber-300 ring-1 ring-amber-400/30 font-medium'
                          : 'border-white/10 text-surface-300'
                      }`}
                    >
                      <option value="all" className="bg-surface-900 text-white">Todas (Necesidades + Deseos)</option>
                      <option value="needs" className="bg-surface-900 text-emerald-300">🟢 Solo Necesidades</option>
                      <option value="wants" className="bg-surface-900 text-amber-300">🟡 Solo Deseos</option>
                      <option value="rated" className="bg-surface-900 text-surface-200">🏷️ Clasificadas (Nec + Des)</option>
                      <option value="unrated" className="bg-surface-900 text-surface-400">⚪ Sin clasificar</option>
                    </select>
                    <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={13} />
                  </div>
                </div>

                {/* Fondos Popover */}
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Qué contar</label>
                  <button
                    onClick={() => setDevengo(v => !v)}
                    title={devengo
                      ? 'Incluye lo que otros pagaron por ti, en la fecha del consumo, y descuenta lo que devolviste'
                      : 'Solo la plata que se movió en tus cuentas'}
                    className={`w-full mb-3 flex items-center gap-1.5 py-2 px-3 rounded-xl border text-xs font-medium transition-all ${
                      devengo
                        ? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
                        : 'bg-surface-900 border-white/10 text-surface-300 hover:text-white'
                    }`}
                  >
                    <Sparkles size={14} className={devengo ? 'text-amber-400' : 'text-surface-500'} />
                    <span className="truncate">{devengo ? 'Lo que consumí' : 'Lo que se movió'}</span>
                  </button>

                  <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Fondo Asignado</label>
                  <div className="relative">
                    <button
                      onClick={() => setShowFundFilter(!showFundFilter)}
                      className={`w-full flex items-center justify-between gap-2 py-2 px-3 rounded-xl border text-xs font-medium transition-all ${
                        selectedFunds !== null
                          ? 'bg-teal-500/15 border-teal-500/40 text-teal-300'
                          : 'bg-surface-900 border-white/10 text-surface-300 hover:text-white'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 truncate">
                        <PiggyBank size={14} className={selectedFunds !== null ? 'text-teal-400' : 'text-surface-500'} />
                        <span className="truncate">{fundFilterLabel(selectedFunds, funds)}</span>
                      </div>
                      <ChevronDown size={13} />
                    </button>

                    {showFundFilter && (
                      <FundFilterPanel
                        funds={funds}
                        selectedFunds={selectedFunds}
                        onChange={setSelectedFunds}
                        onClose={() => setShowFundFilter(false)}
                      />
                    )}
                  </div>
                </div>

                {/* Gastos Fijos */}
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Gastos Fijos</label>
                  <div className="relative">
                    <select
                      value={fixedFilter}
                      onChange={e => setFixedFilter(e.target.value as FixedFilterOption)}
                      className={`w-full bg-surface-900 border rounded-xl px-3 py-2 text-xs focus:outline-none appearance-none cursor-pointer transition-all ${
                        fixedFilter !== 'all'
                          ? fixedFilter === 'fixed' ? 'border-blue-500/60 text-blue-300 ring-1 ring-blue-500/30 font-medium' : 'border-rose-500/60 text-rose-300 ring-1 ring-rose-500/30 font-medium'
                          : 'border-white/10 text-surface-300'
                      }`}
                    >
                      <option value="all" className="bg-surface-900 text-white">Todos los gastos</option>
                      <option value="fixed" className="bg-surface-900 text-blue-300">🔒 Solo Fijos (recurrentes)</option>
                      <option value="non_fixed" className="bg-surface-900 text-rose-300">🚫 Excluir Gastos Fijos</option>
                    </select>
                    <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={13} />
                  </div>
                </div>

                {/* Botón Gestión de Exclusiones */}
                <button
                  type="button"
                  onClick={() => setShowExclusionModal(true)}
                  className="w-full flex items-center justify-between gap-1.5 py-2 px-3 rounded-xl border border-dashed border-rose-500/30 bg-rose-500/5 hover:bg-rose-500/10 text-rose-300 text-xs font-semibold transition-all group"
                >
                  <span className="flex items-center gap-1.5">
                    <Ban size={13} className="text-rose-400 group-hover:scale-110 transition-transform" />
                    <span>Filtros de Exclusión</span>
                  </span>
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300">
                    {excludedCategories.length + excludedTags.length > 0 ? `${excludedCategories.length + excludedTags.length} act.` : 'Configurar'}
                  </span>
                </button>
              </div>

              {/* Card 3: Flujo & Estructura */}
              <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-3.5 space-y-2.5">
                <div className="flex items-center gap-2 pb-1 border-b border-white/5">
                  <Sliders size={14} className="text-sky-400" />
                  <span className="text-xs font-bold text-surface-200 tracking-wide">Flujo & Estructura</span>
                </div>

                {/* Tipo de Transacción */}
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Tipo de Flujo</label>
                  <div className="relative">
                    <select
                      value={typeFilter}
                      onChange={e => setTypeFilter(e.target.value as TypeFilterOption)}
                      className={`w-full bg-surface-900 border rounded-xl px-3 py-2 text-xs focus:outline-none appearance-none cursor-pointer transition-all ${
                        typeFilter !== 'all'
                          ? 'border-emerald-500/60 text-emerald-300 ring-1 ring-emerald-500/30 font-medium'
                          : 'border-white/10 text-surface-300'
                      }`}
                    >
                      <option value="all" className="bg-surface-900 text-white">Todos (Ingresos + Gastos)</option>
                      <option value="expenses" className="bg-surface-900 text-rose-300 font-medium">🔻 Solo Gastos</option>
                      <option value="income" className="bg-surface-900 text-emerald-300 font-medium">🔺 Solo Ingresos</option>
                    </select>
                    <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={13} />
                  </div>
                </div>

                {/* Fuente */}
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Medio / Fuente</label>
                  <div className="relative">
                    <select
                      value={sourceTypeFilter}
                      onChange={e => setSourceTypeFilter(e.target.value)}
                      className={`w-full bg-surface-900 border rounded-xl px-3 py-2 text-xs focus:outline-none appearance-none cursor-pointer transition-all ${
                        sourceTypeFilter
                          ? 'border-sky-500/60 text-sky-300 ring-1 ring-sky-500/30 font-medium'
                          : 'border-white/10 text-surface-300'
                      }`}
                    >
                      <option value="" className="bg-surface-900 text-white">Todas las fuentes</option>
                      <option value="BANCA" className="bg-surface-900 text-white">🏦 BANCA</option>
                      <option value="TARJETA" className="bg-surface-900 text-white">💳 TARJETA</option>
                    </select>
                    <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={13} />
                  </div>
                </div>

                {/* Estructura & Toggle de splits */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Estructura</label>
                    <div className="relative">
                      <select
                        value={structureFilter}
                        onChange={e => setStructureFilter(e.target.value as StructureFilterOption)}
                        className={`w-full bg-surface-900 border rounded-xl px-2.5 py-2 text-xs focus:outline-none appearance-none cursor-pointer transition-all ${
                          structureFilter !== 'all'
                            ? 'border-cyan-500/60 text-cyan-300 ring-1 ring-cyan-500/30 font-medium'
                            : 'border-white/10 text-surface-300'
                        }`}
                      >
                        <option value="all" className="bg-surface-900 text-white">Todas</option>
                        <option value="split" className="bg-surface-900 text-cyan-300">✂️ Splits</option>
                        <option value="grouped" className="bg-surface-900 text-blue-300">🔗 Grupos</option>
                        <option value="simple" className="bg-surface-900 text-surface-300">📄 Simples</option>
                      </select>
                      <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={12} />
                    </div>
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Agrupación</label>
                    <button
                      onClick={() => setGroupSplitsMode(!groupSplitsMode)}
                      className={`w-full flex items-center justify-between gap-1 py-2 px-2.5 rounded-xl border text-xs font-semibold transition-all ${
                        groupSplitsMode
                          ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-200'
                          : 'bg-surface-900 border-white/10 text-surface-400 hover:text-white'
                      }`}
                      title="Agrupar las divisiones de una transacción en una sola fila o mostrarlas por separado"
                    >
                      <span className="truncate text-[11px]">{groupSplitsMode ? 'Agrupados' : 'Separados'}</span>
                      <span className={`text-[9px] px-1 py-0.2 rounded font-mono ${groupSplitsMode ? 'bg-cyan-500/25 text-cyan-300' : 'bg-white/5 text-surface-500'}`}>
                        {groupSplitsMode ? 'ON' : 'OFF'}
                      </span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Card 4: Deudas */}
              <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-3.5 space-y-2.5">
                <div className="flex items-center justify-between gap-2 pb-1 border-b border-white/5">
                  <div className="flex items-center gap-2">
                    <HandCoins size={14} className="text-orange-400" />
                    <span className="text-xs font-bold text-surface-200 tracking-wide">Deudas</span>
                    {debtFiltersCount > 0 && (
                      <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-orange-500/20 text-orange-300">
                        {debtFiltersCount}
                      </span>
                    )}
                  </div>
                  {debtFiltersCount > 0 && (
                    <button
                      onClick={resetDebtFilters}
                      className="text-[10px] font-semibold text-surface-400 hover:text-rose-400 transition-colors"
                      title="Quitar solo los filtros de deudas"
                    >
                      Limpiar
                    </button>
                  )}
                </div>

                {/* Reembolsables */}
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Reembolsos</label>
                  <div className="relative">
                    <select
                      value={reimbursableFilter}
                      onChange={e => setReimbursableFilter(e.target.value as ReimbursableFilterOption)}
                      className={`w-full bg-surface-900 border rounded-xl px-3 py-2 text-xs focus:outline-none appearance-none cursor-pointer transition-all ${
                        reimbursableFilter !== 'all'
                          ? 'border-purple-500/60 text-purple-300 ring-1 ring-purple-500/30 font-medium'
                          : 'border-white/10 text-surface-300'
                      }`}
                    >
                      <option value="all" className="bg-surface-900 text-white">Todos (Reembolsables y propios)</option>
                      <option value="included" className="bg-surface-900 text-purple-300 font-semibold">🟣 Solo Reembolsables</option>
                      <option value="excluded" className="bg-surface-900 text-surface-300">🚫 Excluir Reembolsables</option>
                    </select>
                    <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={13} />
                  </div>
                </div>

                {/* Signo del monto */}
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Monto</label>
                  <div className="grid grid-cols-3 gap-1 bg-surface-900 p-1 rounded-xl border border-white/10">
                    {([
                      { value: 'all', label: 'Todos', active: 'bg-surface-800 text-white' },
                      { value: 'positive', label: '+ Positivos', active: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' },
                      { value: 'negative', label: '− Negativos', active: 'bg-rose-500/20 text-rose-300 border border-rose-500/30' },
                    ] as const).map(opt => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setDebtSignFilter(opt.value)}
                        className={`py-1 text-[11px] font-semibold rounded-lg transition-all ${
                          debtSignFilter === opt.value ? opt.active : 'text-surface-400 hover:text-white'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Persona */}
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Persona</label>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setShowPeopleFilter(!showPeopleFilter)}
                      className={`w-full flex items-center justify-between gap-2 py-2 px-3 rounded-xl border text-xs font-medium transition-all ${
                        debtPeopleFilter.length === 0
                          ? 'bg-surface-900 border-white/10 text-surface-300 hover:text-white'
                          : debtPeopleMode === 'exclude'
                            ? 'bg-rose-500/15 border-rose-500/40 text-rose-300'
                            : 'bg-orange-500/15 border-orange-500/40 text-orange-300'
                      }`}
                    >
                      <span className="truncate">
                        {debtPeopleFilter.length === 0
                          ? 'Todas las personas'
                          : `${debtPeopleMode === 'exclude' ? 'Excepto' : 'Solo'} ${
                              debtPeopleFilter.length <= 2
                                ? debtPeopleFilter.map(personLabel).join(', ')
                                : `${debtPeopleFilter.length} personas`
                            }`}
                      </span>
                      <ChevronDown size={13} className="shrink-0" />
                    </button>

                    {showPeopleFilter && (
                      <>
                        <div className="fixed inset-0 z-30" onClick={() => setShowPeopleFilter(false)} />
                        <div className="absolute z-40 mt-2 right-0 w-72 bg-surface-900 border border-white/10 rounded-2xl shadow-2xl p-3 backdrop-blur-xl space-y-2">
                          {/* Modo: incluir solo las marcadas o excluirlas */}
                          <div className="grid grid-cols-2 gap-1 bg-surface-950 p-1 rounded-xl border border-white/5">
                            <button
                              type="button"
                              onClick={() => setDebtPeopleMode('include')}
                              className={`py-1.5 text-[11px] font-semibold rounded-lg transition-all ${
                                debtPeopleMode === 'include'
                                  ? 'bg-orange-500/20 text-orange-300 border border-orange-500/30'
                                  : 'text-surface-400 hover:text-white'
                              }`}
                            >
                              Solo estas
                            </button>
                            <button
                              type="button"
                              onClick={() => setDebtPeopleMode('exclude')}
                              className={`py-1.5 text-[11px] font-semibold rounded-lg transition-all ${
                                debtPeopleMode === 'exclude'
                                  ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                                  : 'text-surface-400 hover:text-white'
                              }`}
                            >
                              🚫 Excluir estas
                            </button>
                          </div>

                          <div className="flex justify-between items-center pb-2 border-b border-white/10">
                            <span className="text-[11px] text-surface-400">
                              {debtPeopleFilter.length === 0 ? 'Ninguna marcada: se ven todas' : `${debtPeopleFilter.length} marcada${debtPeopleFilter.length > 1 ? 's' : ''}`}
                            </span>
                            {debtPeopleFilter.length > 0 && (
                              <button
                                type="button"
                                onClick={() => setDebtPeopleFilter([])}
                                className="text-[11px] text-surface-400 hover:text-rose-300 font-semibold"
                              >
                                Desmarcar
                              </button>
                            )}
                          </div>

                          <div className="max-h-56 overflow-y-auto custom-scrollbar space-y-1">
                            {[{ key: SIN_PERSONA, name: '⚪ Sin persona', count: -1 }, ...debtPeople].map(p => {
                              const marcado = debtPeopleFilter.includes(p.key);
                              const excluding = debtPeopleMode === 'exclude';
                              return (
                                <button
                                  key={p.key}
                                  type="button"
                                  onClick={() => toggleDebtPerson(p.key)}
                                  className={`w-full text-left text-xs px-2.5 py-1.5 rounded-lg flex items-center gap-2 transition-colors ${
                                    p.key === SIN_PERSONA ? 'border-b border-white/5 pb-2 mb-1' : ''
                                  } ${
                                    marcado
                                      ? excluding ? 'bg-rose-500/10 text-rose-200 font-medium' : 'bg-orange-500/10 text-orange-200 font-medium'
                                      : 'text-surface-400 hover:bg-white/5'
                                  }`}
                                >
                                  <span className={`w-3.5 h-3.5 rounded border flex-shrink-0 flex items-center justify-center ${
                                    marcado ? (excluding ? 'bg-rose-500 border-rose-500' : 'bg-orange-500 border-orange-500') : 'border-surface-600'
                                  }`}>
                                    {marcado && (excluding ? <X size={10} className="text-surface-950" /> : <Check size={10} className="text-surface-950" />)}
                                  </span>
                                  <span className={`truncate flex-1 ${marcado && excluding ? 'line-through' : ''}`}>{p.name}</span>
                                  {p.count > 0 && (
                                    <span className="text-[10px] font-mono text-surface-500">{p.count}</span>
                                  )}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {/* Estado de pago & Vínculo */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Pago</label>
                    <div className="relative">
                      <select
                        value={debtStatusFilter}
                        onChange={e => setDebtStatusFilter(e.target.value as DebtStatusFilterOption)}
                        className={`w-full bg-surface-900 border rounded-xl px-2.5 py-2 text-xs focus:outline-none appearance-none cursor-pointer transition-all ${
                          debtStatusFilter !== 'all'
                            ? debtStatusFilter === 'paid' ? 'border-emerald-500/60 text-emerald-300 ring-1 ring-emerald-500/30 font-medium' : 'border-amber-500/60 text-amber-300 ring-1 ring-amber-500/30 font-medium'
                            : 'border-white/10 text-surface-300'
                        }`}
                        title="Estado de la deuda vinculada en Supabase"
                      >
                        <option value="all" className="bg-surface-900 text-white">Todas</option>
                        <option value="paid" className="bg-surface-900 text-emerald-300">✅ Pagadas</option>
                        <option value="pending" className="bg-surface-900 text-amber-300">⏳ Pendientes</option>
                        <option value="partial" className="bg-surface-900 text-amber-300">◐ Abonadas</option>
                      </select>
                      <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={12} />
                    </div>
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Dirección</label>
                    <div className="relative">
                      <select
                        value={debtDirectionFilter}
                        onChange={e => setDebtDirectionFilter(e.target.value as DebtDirectionFilterOption)}
                        className={`w-full bg-surface-900 border rounded-xl px-2.5 py-2 text-xs focus:outline-none appearance-none cursor-pointer transition-all ${
                          debtDirectionFilter !== 'all'
                            ? 'border-orange-500/60 text-orange-300 ring-1 ring-orange-500/30 font-medium'
                            : 'border-white/10 text-surface-300'
                        }`}
                        title="Según la deuda o el pago vinculado"
                      >
                        <option value="all" className="bg-surface-900 text-white">Ambas</option>
                        <option value="me_deben" className="bg-surface-900 text-white">Me deben</option>
                        <option value="debo" className="bg-surface-900 text-white">Yo debo</option>
                      </select>
                      <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={12} />
                    </div>
                  </div>
                </div>

                {/* Vínculo con Supabase */}
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1">Vínculo</label>
                  <div className="relative">
                    <select
                      value={debtLinkFilter}
                      onChange={e => setDebtLinkFilter(e.target.value as DebtLinkFilterOption)}
                      className={`w-full bg-surface-900 border rounded-xl px-3 py-2 text-xs focus:outline-none appearance-none cursor-pointer transition-all ${
                        debtLinkFilter !== 'all'
                          ? 'border-orange-500/60 text-orange-300 ring-1 ring-orange-500/30 font-medium'
                          : 'border-white/10 text-surface-300'
                      }`}
                    >
                      <option value="all" className="bg-surface-900 text-white">Cualquiera</option>
                      <option value="linked" className="bg-surface-900 text-white">🔗 Con deuda o pago</option>
                      <option value="deuda" className="bg-surface-900 text-white">🧾 Vinculadas a una deuda</option>
                      <option value="pago" className="bg-surface-900 text-white">💸 Vinculadas a un pago</option>
                      <option value="unlinked" className="bg-surface-900 text-amber-300">⚠️ Reembolsables sin vincular</option>
                    </select>
                    <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" size={13} />
                  </div>
                </div>
              </div>

            </div>
          )}

          {/* Tier 4: Active Filter Chips Bar */}
          {activeFilterChips.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap pt-3 border-t border-white/5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-surface-400 flex items-center gap-1 shrink-0">
                <Filter size={12} className="text-primary-400" /> Filtros aplicados:
              </span>
              <div className="flex items-center gap-1.5 flex-wrap flex-1">
                {activeFilterChips.map(chip => (
                  <span
                    key={chip.key}
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium border shadow-sm ${chip.color}`}
                  >
                    <span className="opacity-75 text-[10px] uppercase font-bold">{chip.label}:</span>
                    <strong className="font-semibold">{chip.value}</strong>
                    <button
                      onClick={chip.onRemove}
                      className="hover:bg-white/20 rounded-full p-0.5 ml-0.5 transition-colors"
                      title={`Remover filtro de ${chip.label}`}
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
              <button
                onClick={handleResetFilters}
                className="text-xs text-rose-400 hover:text-rose-300 font-semibold px-2.5 py-1 rounded-lg hover:bg-rose-500/10 transition-colors shrink-0"
              >
                Limpiar todos
              </button>
            </div>
          )}

        </div>

        {/* ANALYSIS VIEW */}
        {viewMode === 'analysis' && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <ExplorerAnalyticsContent
              transactions={results}
              funds={funds || []}
              onOpenTransactionDetails={(tx) => setEditingTransaction(tx)}
            />
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
                value={money(income)}
                icon={<ArrowUpRight size={20} />}
                colorClass="bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
              />
              <StatCard
                label="Gastos"
                value={money(expenses)}
                icon={<ArrowDownRight size={20} />}
                colorClass="bg-rose-500/10 text-rose-400 border-rose-500/20"
              />
              <StatCard
                label="Neto Total"
                value={money(totalAmount)}
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
                        const debtStatus = linkedDebtStatus(t, debtLookup);
                        const debtPersonName = debtPerson(t, debtLookup);

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
                                    parseTags(t.tags).map((tg, i) => (
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
                                {signedMoney(t.MONTO)}
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
                                  {debtStatus && (
                                    <span
                                      title={debtPersonName ? `Deuda con ${debtPersonName}` : 'Deuda vinculada'}
                                      className={`text-[9px] font-bold px-1.5 py-0.5 rounded border whitespace-nowrap ${
                                        debtStatus === 'paid'
                                          ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                                          : 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                                      }`}
                                    >
                                      {debtStatus === 'paid' ? 'pagada' : debtStatus === 'partial' ? 'abonada' : 'pendiente'}
                                      {debtPersonName && ` · ${debtPersonName}`}
                                    </span>
                                  )}
                                  {!debtStatus && t.pago_id && (
                                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded border whitespace-nowrap bg-sky-500/10 text-sky-300 border-sky-500/20">
                                      pago{debtPersonName && ` · ${debtPersonName}`}
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
                                        Total división: <strong className="text-white font-mono">{signedMoney(t.MONTO)}</strong>
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
                                                  {parseTags(sub.tags).map((tg, i) => (
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
                                              {signedMoney(sub.MONTO)}
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

      {/* Explorer Analytics Modal */}
      <ExplorerAnalyticsModal
        isOpen={showAnalyticsModal}
        onClose={() => setShowAnalyticsModal(false)}
        transactions={results}
        funds={funds || []}
        onOpenTransactionDetails={(tx) => {
          setShowAnalyticsModal(false);
          setEditingTransaction(tx);
        }}
      />

      {/* Explorer Exclusions Modal */}
      <ExplorerExclusionsModal
        isOpen={showExclusionModal}
        onClose={() => setShowExclusionModal(false)}
        categories={categories || []}
        tags={tags || []}
        excludedCategories={excludedCategories}
        onToggleCategory={handleToggleExcludedCategory}
        onClearCategories={() => setExcludedCategories([])}
        excludedTags={excludedTags}
        onToggleTag={handleToggleExcludedTag}
        onClearTags={() => setExcludedTags([])}
        fixedFilter={fixedFilter}
        onChangeFixedFilter={setFixedFilter}
        reimbursableFilter={reimbursableFilter}
        onChangeReimbursableFilter={setReimbursableFilter}
      />
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
