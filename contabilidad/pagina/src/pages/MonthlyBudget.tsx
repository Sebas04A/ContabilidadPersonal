import { useState, useEffect, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { api, Transaction, TransactionUpdate, BudgetConfig } from '../services/api';
import { Wallet, X, TrendingDown, Heart, Scale, Filter, BarChart3, List, PiggyBank, Check, ArrowLeft } from 'lucide-react';

import { groupSplits } from '../utils/groupSplits';
import { matchFund } from '../utils/matchFund';
import {
  TransactionFilters, DEFAULT_TRANSACTION_FILTERS, SIN_CATEGORIA, SIN_ETIQUETA, SIN_FONDO,
  applyTransactionFilters, cycleIncludeExclude,
  LabeledFilterOption, ReimbursableFilterOption, PriorityFilterOption,
} from '../utils/transactionFilters';
import { money } from '../utils/format';
import { useFunds } from '../hooks/useTransactions';
import { usePersistentState } from '../hooks/usePersistentState';
import { FundFilterPanel, fundFilterLabel } from '../components/FundFilterPanel';
import { EditModal } from '../components/EditModal';
import { BudgetTransactionRow } from '../components/budget/BudgetTransactionRow';

import { GeneralBudgetTab } from '../components/budget/GeneralBudgetTab';
import { HappinessTab } from '../components/budget/HappinessTab';
import { NeedsWantsTab } from '../components/budget/NeedsWantsTab';
import { CategoriesTagsTab } from '../components/budget/CategoriesTagsTab';
import { TOOLTIP } from '../utils/chartTheme';
import { parseTags } from '../utils/tags';

const CATEGORIES = ['Alimentación', 'Transporte', 'Ocio', 'Salud', 'Subscripciones', 'Mensual', 'Inversion', 'Regalo', 'Mujeres', 'Aseo', 'Deudas', 'Tarjeta', 'Ropa', 'Viajes', 'Otro'];

export function MonthlyBudget() {
  const [activeTab, setActiveTab] = useState<'budget' | 'happiness' | 'needs' | 'categories'>(() => {
    const saved = localStorage.getItem('budget_activeTab');
    return (saved as any) || 'budget';
  });
  const [budgetConfig, setBudgetConfig] = useState<BudgetConfig>({ tracked_tags: [] });
  const [allPeriodTransactions, setAllPeriodTransactions] = useState<Transaction[]>([]);
  const [labeledFilter, setLabeledFilter] = usePersistentState<LabeledFilterOption>('budget_labeledFilter', 'all');
  const [reimbursableFilter, setReimbursableFilter] = usePersistentState<ReimbursableFilterOption>('budget_reimbursableFilter', 'all');
  const [priorityFilter, setPriorityFilter] = usePersistentState<PriorityFilterOption>('budget_priorityFilter', 'all');

  // Categorías y etiquetas: inclusiones (solo mostrar) y exclusiones (ocultar).
  const [excludedCategories, setExcludedCategories] = usePersistentState<string[]>('budget_excludedCategories', []);
  const [excludedTags, setExcludedTags] = usePersistentState<string[]>('budget_excludedTags', []);
  const [includedCategories, setIncludedCategories] = usePersistentState<string[]>('budget_includedCategories', []);
  const [includedTags, setIncludedTags] = usePersistentState<string[]>('budget_includedTags', []);
  const [showExclusionModal, setShowExclusionModal] = useState(false);

  // Lista de fondos (cacheada por react-query) para marcar y filtrar a qué fondo
  // pertenece cada transacción: búsqueda en memoria, sin peticiones por fila.
  const { data: funds } = useFunds();

  /**
   * Fondos marcados; null = todos y lo que no tiene fondo. Antes lo que no tenía fondo
   * se mostraba siempre, así que una selección guardada con el formato viejo lo marca.
   */
  const [selectedFunds, setSelectedFunds] = usePersistentState<string[] | null>('budget_selectedFunds_v2', () => {
    try {
      const legacy = JSON.parse(localStorage.getItem('budget_selectedFunds') ?? 'null');
      return Array.isArray(legacy) ? [...legacy, SIN_FONDO] : null;
    } catch {
      return null;
    }
  });
  const [showFundFilter, setShowFundFilter] = useState(false);

  // Todo menos el estado de etiquetado, que se aplica aparte para contar etiquetadas y no.
  const baseFilters = useMemo<TransactionFilters>(() => ({
    ...DEFAULT_TRANSACTION_FILTERS,
    includedCategories, excludedCategories, includedTags, excludedTags,
    selectedFunds,
    reimbursable: reimbursableFilter,
    priority: priorityFilter,
  }), [includedCategories, excludedCategories, includedTags, excludedTags, selectedFunds, reimbursableFilter, priorityFilter]);

  const transactionsBaseFilter = useMemo(
    () => applyTransactionFilters(allPeriodTransactions, baseFilters, funds),
    [allPeriodTransactions, baseFilters, funds],
  );

  const transactions = useMemo(
    () => applyTransactionFilters(transactionsBaseFilter, { ...DEFAULT_TRANSACTION_FILTERS, labeled: labeledFilter }, funds),
    [transactionsBaseFilter, labeledFilter, funds],
  );

  const labelingStats = useMemo(() => {
      const labeled = transactionsBaseFilter.filter(t => t.revisado);
      const unlabeled = transactionsBaseFilter.filter(t => !t.revisado);
      return { labeled, unlabeled };
  }, [transactionsBaseFilter]);

  const [allTimeTransactions, setAllTimeTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Edit Mode State
  const [isEditing, setIsEditing] = useState(false);
  const [editTags, setEditTags] = useState<string[]>([]);
  const [newTagKey, setNewTagKey] = useState("");

  const [selectedPeriod, setSelectedPeriod] = useState<string>(() => {
    return localStorage.getItem('budget_selectedPeriod') || 'current';
  });
  const [customStartDate, setCustomStartDate] = useState<string>(() => {
    return localStorage.getItem('budget_customStartDate') || '';
  });
  const [customEndDate, setCustomEndDate] = useState<string>(() => {
    return localStorage.getItem('budget_customEndDate') || '';
  });
  const [currentMonthName, setCurrentMonthName] = useState("");
  const [availableTags, setAvailableTags] = useState<string[]>([]);

  // Local Storage sync effects
  useEffect(() => {
    localStorage.setItem('budget_activeTab', activeTab);
  }, [activeTab]);

  useEffect(() => {
    localStorage.setItem('budget_selectedPeriod', selectedPeriod);
  }, [selectedPeriod]);

  useEffect(() => {
    localStorage.setItem('budget_customStartDate', customStartDate);
  }, [customStartDate]);

  useEffect(() => {
    localStorage.setItem('budget_customEndDate', customEndDate);
  }, [customEndDate]);

  // Modal State
  const [modalTitle, setModalTitle] = useState<string | null>(null);
  const [modalDescription, setModalDescription] = useState<string>("");
  const [modalTransactions, setModalTransactions] = useState<Transaction[]>([]);
  const [modalHistory, setModalHistory] = useState<Array<{ title: string; description: string; transactions: Transaction[]; viewMode: 'list' | 'chart' }>>([]);
  const [loadingModal, setLoadingModal] = useState(false);
  const [modalSortBy, setModalSortBy] = useState<'amount' | 'date'>('amount');
  const [modalViewMode, setModalViewMode] = useState<'list' | 'chart'>('list');
  const [tagCountMode, setTagCountMode] = useState<'proportional' | 'full'>('proportional');

  // Etiquetado desde el modal de detalle
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // Mantener modalTransactions actualizado tras guardar en EditModal
  useEffect(() => {
    if (modalTransactions.length > 0 && allTimeTransactions.length > 0) {
      const rawMap = new Map(allTimeTransactions.map(t => [t.id, t]));
      setModalTransactions(prev => prev.map(t => rawMap.get(t.id) || t));
    }
  }, [allTimeTransactions]);

  /**
   * Índice id -> transacción con sus partes reagrupadas. Solo se usa para el clic
   * (abrir el split completo en el EditModal) y para saber cuántas partes tiene una
   * fila: las agregaciones del presupuesto siguen usando las filas sin agrupar,
   * porque cada parte tiene su propia categoría/tags/felicidad.
   */
  const groupedById = useMemo(() => {
    const m = new Map<string, Transaction>();
    groupSplits(allPeriodTransactions).forEach(t => m.set(t.id, t));
    return m;
  }, [allPeriodTransactions]);

  /**
   * Tras recargar el periodo, reemplaza las transacciones del modal abierto por su
   * versión fresca (mismo id, misma posición entre las partes de un split) para que
   * el cambio se vea sin cerrar el modal.
   */
  const remapModalTransactions = (fresh: Transaction[]) => {
    setModalTransactions(prev => {
      if (prev.length === 0) return prev;
      const byId = new Map<string, Transaction[]>();
      fresh.forEach(t => {
        if (!byId.has(t.id)) byId.set(t.id, []);
        byId.get(t.id)!.push(t);
      });
      const seen = new Map<string, number>();
      const out: Transaction[] = [];
      prev.forEach(t => {
        const parts = byId.get(t.id);
        if (!parts || parts.length === 0) return; // desapareció del periodo
        const i = seen.get(t.id) ?? 0;
        out.push(parts[Math.min(i, parts.length - 1)]);
        seen.set(t.id, i + 1);
      });
      return out;
    });
  };

  const handleTransactionSave = async (id: string, updates: TransactionUpdate) => {
    try {
      // Al dividir, el EditModal ya llamó a splitTransaction y manda updates vacío:
      // ahí solo hace falta refrescar.
      if (Object.keys(updates).length > 0) {
        await api.updateTransaction(id, updates);
      }
    } catch (e) {
      console.error("Error guardando la transacción", e);
    } finally {
      setEditingTransaction(null);
      setRefreshKey(k => k + 1);
    }
  };

  const periodOptions = useMemo(() => {
    const options = [
      { value: 'current', label: 'Este mes' },
      { value: 'all', label: 'Todo el tiempo (General)' },
      { value: 'custom', label: 'Fechas personalizadas...' }
    ];
    const now = new Date();
    // Generate last 24 months
    for (let i = 1; i <= 24; i++) {
        const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
        const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
        const labelStr = new Intl.DateTimeFormat('es-CO', { year: 'numeric', month: 'long' }).format(d);
        options.push({ value, label: labelStr.charAt(0).toUpperCase() + labelStr.slice(1) });
    }
    return options;
  }, []);

  useEffect(() => {
    const loadConfigAndHistory = async () => {
      try {
        const config = await api.getBudget();
        setBudgetConfig(config);
        setEditTags(config.tracked_tags || []);
        const tags = await api.getTags();
        setAvailableTags(tags);
        const allData = await api.getTransactions();
        setAllTimeTransactions(allData);
      } catch (error) {
        console.error("Error loading config", error);
      }
    };
    loadConfigAndHistory();
  }, []);

  const activePeriodDates = useMemo(() => {
    if (selectedPeriod === 'current') {
      const now = new Date();
      const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
      const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
      return {
        firstDayStr: firstDay.toISOString().split('T')[0],
        lastDayStr: lastDay.toISOString().split('T')[0],
        title: new Intl.DateTimeFormat('es-CO', { year: 'numeric', month: 'long' }).format(now)
      };
    } else if (selectedPeriod === 'all') {
      return {
        firstDayStr: undefined,
        lastDayStr: undefined,
        title: "Todo el tiempo"
      };
    } else if (selectedPeriod === 'custom') {
      return {
        firstDayStr: customStartDate || undefined,
        lastDayStr: customEndDate || undefined,
        title: customStartDate && customEndDate ? `Desde ${customStartDate} hasta ${customEndDate}` : ""
      };
    } else {
      const [year, month] = selectedPeriod.split('-');
      const firstDay = new Date(Number(year), Number(month) - 1, 1);
      const lastDay = new Date(Number(year), Number(month), 0);
      return {
        firstDayStr: firstDay.toISOString().split('T')[0],
        lastDayStr: lastDay.toISOString().split('T')[0],
        title: new Intl.DateTimeFormat('es-CO', { year: 'numeric', month: 'long' }).format(firstDay)
      };
    }
  }, [selectedPeriod, customStartDate, customEndDate]);

  useEffect(() => {
    const fetchPeriodTransactions = async () => {
      // Don't fetch if custom is selected but dates are missing
      if (selectedPeriod === 'custom' && (!customStartDate || !customEndDate)) {
          return;
      }

      setLoading(true);
      try {
        const { firstDayStr, lastDayStr, title } = activePeriodDates;
        setCurrentMonthName(title);

        const data = await api.getTransactions(
          undefined, undefined, undefined,
          firstDayStr,
          lastDayStr
        );
        setAllPeriodTransactions(data);
        remapModalTransactions(data);
      } catch (error) {
        console.error("Error loading period data", error);
      } finally {
        setLoading(false);
      }
    };
    fetchPeriodTransactions();
  }, [selectedPeriod, customStartDate, customEndDate, refreshKey, activePeriodDates]);

  // Aggregations
  const totalExpenses = useMemo(() => {
    return Math.abs(transactions.filter(t => t.MONTO < 0).reduce((acc, curr) => acc + curr.MONTO, 0));
  }, [transactions]);

  const totalIncome = useMemo(() => {
    return transactions.filter(t => t.MONTO > 0).reduce((acc, curr) => acc + curr.MONTO, 0);
  }, [transactions]);

  const tagExpenses = useMemo(() => {
    const expenses: Record<string, number> = {};
    
    transactions.forEach(t => {
      if (t.tags) {
        const tTags = parseTags(t.tags);
        tTags.forEach(tag => {
          if (!expenses[tag]) expenses[tag] = 0;
          expenses[tag] += (t.MONTO * -1); // Summing negative amounts as positive expenses, and positive amounts as deductions
        });
      }
    });
    return expenses;
  }, [transactions]);

  // Los mismos filtros del período, sobre todo el histórico.
  const allTimeFiltered = useMemo(
    () => applyTransactionFilters(allTimeTransactions, { ...baseFilters, labeled: labeledFilter }, funds),
    [allTimeTransactions, baseFilters, labeledFilter, funds],
  );

  const tagBalances = useMemo(() => {
    const balances: Record<string, number> = {};
    if (!budgetConfig.tracked_tags) return balances;
    
    budgetConfig.tracked_tags.forEach(tag => {
       const sum = allTimeFiltered
          .filter(t => t.tags && parseTags(t.tags).includes(tag) && t.MONTO > 0)
          .reduce((acc, t) => acc + t.MONTO, 0);
       balances[tag] = sum;
    });
    return balances;
  }, [allTimeFiltered, budgetConfig.tracked_tags]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const newConfig: BudgetConfig = {
        tracked_tags: editTags
      };
      await api.saveBudget(newConfig);
      setBudgetConfig(newConfig);
      setIsEditing(false);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const handleAddNewTag = () => {
     if (newTagKey && !editTags.includes(newTagKey)) {
         setEditTags([...editTags, newTagKey]);
         setNewTagKey("");
     }
  };

  const handleRemoveTag = (key: string) => {
      setEditTags(editTags.filter(t => t !== key));
  };

  const openTagModal = async (tag: string) => {
    setModalTitle(`Ingresos Presupuestados: ${tag}`);
    setModalDescription('Todas las transacciones de ingreso (positivas) para este tag en todo el tiempo, con los filtros actuales aplicados.');
    
    const txs = allTimeFiltered.filter(t => t.tags && parseTags(t.tags).includes(tag) && t.MONTO > 0);
    setModalTransactions(txs);
    setModalSortBy('amount');
    setModalViewMode('list');
  };

  const openLocalModal = (title: string, desc: string, txs: Transaction[], isSubModal: boolean = false) => {
      if (isSubModal && modalTitle) {
          setModalHistory(prev => [...prev, {
              title: modalTitle,
              description: modalDescription,
              transactions: modalTransactions,
              viewMode: modalViewMode
          }]);
      } else if (!isSubModal) {
          setModalHistory([]);
      }
      setModalTitle(title);
      setModalDescription(desc);
      setModalTransactions(txs);
      setLoadingModal(false);
      setModalSortBy('amount');
      setModalViewMode('list');
  };

  const handleModalBack = () => {
      if (modalHistory.length === 0) return;
      const last = modalHistory[modalHistory.length - 1];
      setModalHistory(prev => prev.slice(0, -1));
      setModalTitle(last.title);
      setModalDescription(last.description);
      setModalTransactions(last.transactions);
      setModalViewMode(last.viewMode);
  };

  const handleCloseModal = () => {
      setModalTitle(null);
      setModalHistory([]);
  };

  // UI Components
  const formatCurrency = money;

  const renderProgressBar = (spent: number, budget: number, colorClass?: string) => {
    const percentage = budget > 0 ? Math.min((spent / budget) * 100, 100) : 0;
    const isOver = spent > budget && budget > 0;

    return (
      <div className="w-full h-3 bg-surface-900 rounded-full overflow-hidden border border-white/5">
        <div 
           className={`h-full rounded-full transition-all duration-1000 ${isOver ? 'bg-rose-500 shadow-[0_0_10px_#f43f5e80]' : colorClass || 'bg-emerald-500 shadow-[0_0_10px_#10b98180]'}`}
           style={{ width: `${percentage}%` }}
        />
      </div>
    );
  };

  const sortedModalTransactions = useMemo(() => {
      // Las partes de un mismo split se colapsan en una sola fila (sumando los
      // montos que entraron al filtro) para no repetir la transacción.
      const txs = groupSplits(modalTransactions);
      if (modalSortBy === 'amount') {
          return txs.sort((a, b) => Math.abs(b.MONTO) - Math.abs(a.MONTO));
      } else {
          return txs.sort((a, b) => new Date(b.FECHA).getTime() - new Date(a.FECHA).getTime());
      }
  }, [modalTransactions, modalSortBy]);

  const modalChartsData = useMemo(() => {
      if (!modalTitle || modalTransactions.length === 0) return null;

      const titleLower = modalTitle.toLowerCase();
      const isCategory = titleLower.includes('categoría') || titleLower.includes('categoría:') || titleLower.includes('distribución:');
      const isTag = titleLower.includes('tag') || titleLower.includes('etiqueta') || titleLower.includes('balance en:') || titleLower.includes('ingresos presupuestados:');

      const expenses = modalTransactions.filter(t => t.MONTO < 0);
      const totalNegative = expenses.reduce((acc, t) => acc + Math.abs(t.MONTO), 0);

      // 1. Top Comercios
      const groupedComercios: Record<string, number> = {};
      expenses.forEach(t => {
          const name = t.nombre_limpio || t.DESCRIPCION || "Desconocido";
          groupedComercios[name] = (groupedComercios[name] || 0) + Math.abs(t.MONTO);
      });
      const sortedComercios = Object.entries(groupedComercios)
          .map(([name, value]) => ({ name, value }))
          .sort((a, b) => b.value - a.value)
          .slice(0, 10);

      // 2. Tags con distribución según tagCountMode (proporcional vs monto completo)
      const groupedTags: Record<string, number> = {};
      expenses.forEach(t => {
          if (!t.tags || t.tags.trim() === '') {
              groupedTags['Sin Etiqueta'] = (groupedTags['Sin Etiqueta'] || 0) + Math.abs(t.MONTO);
          } else {
              const tTags = parseTags(t.tags);
              if (tTags.length === 0) {
                  groupedTags['Sin Etiqueta'] = (groupedTags['Sin Etiqueta'] || 0) + Math.abs(t.MONTO);
              } else {
                  const tagAmount = tagCountMode === 'proportional' 
                      ? Math.abs(t.MONTO) / tTags.length 
                      : Math.abs(t.MONTO);
                  tTags.forEach(tag => {
                      groupedTags[tag] = (groupedTags[tag] || 0) + tagAmount;
                  });
              }
          }
      });
      const sortedTags = Object.entries(groupedTags)
          .map(([name, value]) => ({ name, value }))
          .sort((a, b) => b.value - a.value);

      // 3. Categorías
      const groupedCategories: Record<string, number> = {};
      expenses.forEach(t => {
          const cat = (!t.categoria || t.categoria === '---') ? 'Sin Categoría' : t.categoria;
          groupedCategories[cat] = (groupedCategories[cat] || 0) + Math.abs(t.MONTO);
      });
      const sortedCategories = Object.entries(groupedCategories)
          .map(([name, value]) => ({ name, value }))
          .sort((a, b) => b.value - a.value);

      // Bar Chart for Top Comercios
      let barChartOption = null;
      if (sortedComercios.length > 0) {
          const dataReversed = [...sortedComercios].reverse();
          barChartOption = {
              tooltip: {
                  ...TOOLTIP,
                  trigger: 'axis',
                  axisPointer: { type: 'shadow' },
                  confine: true,
                  position: (pos: any) => [pos[0] + 15, Math.max(10, pos[1] - 30)],
                  formatter: (params: any) => {
                      const d = params[0].data;
                      return `<strong class="text-white">${d.name}</strong><br/>Monto: ${money(d.value)}`;
                  },
              },
              grid: { left: '3%', right: '4%', bottom: '3%', top: '5%', containLabel: true },
              xAxis: { 
                  type: 'value', 
                  splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.05)' } },
                  axisLabel: { color: '#9ca3af', formatter: (val: number) => val >= 1000 ? (val/1000) + 'k' : val }
              },
              yAxis: { 
                  type: 'category', 
                  data: dataReversed.map(d => d.name), 
                  axisLabel: { 
                      color: '#e5e7eb', 
                      fontWeight: 'bold',
                      fontSize: 11,
                      formatter: (val: string) => {
                          if (!val) return '';
                          return val.length > 14 ? val.substring(0, 14) + '...' : val;
                      }
                  },
                  axisTick: { show: false }, 
                  axisLine: { show: false } 
              },
              series: [{
                  name: 'Monto',
                  type: 'bar',
                  data: dataReversed.map(d => ({
                      value: d.value,
                      name: d.name,
                      itemStyle: { color: '#a855f7', borderRadius: [0, 4, 4, 0] }
                  }))
              }]
          };
      }

      // Pie Chart for distribution
      let pieChartOption = null;
      let pieTitle = "";
      if (isCategory) {
          pieTitle = tagCountMode === 'proportional' 
              ? "Distribución de Etiquetas (Proporcional 1x)" 
              : "Distribución de Etiquetas (Monto Completo Multi)";
          const treemapData = sortedTags.map(item => ({ 
              name: item.name, 
              value: parseFloat(item.value.toFixed(0)) 
          }));
          pieChartOption = {
              tooltip: {
                  ...TOOLTIP,
                  trigger: 'item',
                  formatter: (params: any) => {
                      const percentage = totalNegative > 0 ? (params.value / totalNegative) * 100 : 0;
                      return `<strong class="text-white">${params.name}</strong><br/>Monto Distribuido: ${money(params.value)}<br/>Proporción: ${percentage.toFixed(1)}%`;
                  },
              },
              series: [
                  {
                      name: 'Etiquetas',
                      type: 'treemap',
                      visibleMin: 300,
                      label: {
                          show: true,
                          formatter: '{b}\n$ {c}',
                          fontSize: 11,
                          fontWeight: 'bold',
                          color: '#fff'
                      },
                      itemStyle: {
                          borderColor: '#111827',
                          borderWidth: 2,
                          gapWidth: 1
                      },
                      breadcrumb: {
                          show: false
                      },
                      data: treemapData
                  }
              ]
          };
      } else if (isTag) {
          pieTitle = "Distribución de Categorías";
          const pieData = sortedCategories.map(item => ({ value: item.value, name: item.name }));
          pieChartOption = {
              tooltip: {
                  ...TOOLTIP,
                  trigger: 'item',
                  formatter: (params: any) => {
                      return `<strong class="text-white">${params.data.name}</strong><br/>Monto: ${money(params.data.value)} (${params.percent.toFixed(1)}%)`;
                  },
              },
              legend: { show: false },
              series: [
                  {
                      name: 'Categorías',
                      type: 'pie',
                      radius: ['40%', '70%'],
                      avoidLabelOverlap: true,
                      itemStyle: { borderRadius: 8, borderColor: '#111827', borderWidth: 2 },
                      label: { show: true, formatter: '{b}\n{d}%', color: '#9ca3af', fontSize: 10 },
                      labelLine: { length: 10, length2: 10, lineStyle: { color: '#4b5563' } },
                      data: pieData
                  }
              ]
          };
      } else {
          pieTitle = "Distribución por Categorías";
          const pieData = sortedCategories.map(item => ({ value: item.value, name: item.name }));
          pieChartOption = {
              tooltip: {
                  ...TOOLTIP,
                  trigger: 'item',
                  formatter: (params: any) => {
                      return `<strong class="text-white">${params.data.name}</strong><br/>Monto: ${money(params.data.value)} (${params.percent.toFixed(1)}%)`;
                  },
              },
              legend: { show: false },
              series: [
                  {
                      name: 'Categorías',
                      type: 'pie',
                      radius: ['40%', '70%'],
                      avoidLabelOverlap: true,
                      itemStyle: { borderRadius: 8, borderColor: '#111827', borderWidth: 2 },
                      label: { show: true, formatter: '{b}\n{d}%', color: '#9ca3af', fontSize: 10 },
                      labelLine: { length: 10, length2: 10, lineStyle: { color: '#4b5563' } },
                      data: pieData
                  }
              ]
          };
      }

      return {
          barChartOption,
          pieChartOption,
          pieTitle,
          totalNegative,
          isCategory,
          isTag
      };
  }, [modalTitle, modalTransactions, tagCountMode]);

  return (
    <div className="flex-1 overflow-y-auto px-4 md:px-8 pb-8 custom-scrollbar">
      <div className="max-w-4xl mx-auto space-y-8 mt-8">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
          <div className="space-y-2">
             <h1 className="text-4xl font-bold text-white tracking-tight flex items-center gap-3">
               <Wallet className="text-secondary-400" size={36} />
               <span className="bg-clip-text text-transparent bg-gradient-to-r from-white to-surface-400">
                 Presupuesto & Analytics
               </span>
             </h1>
             <div className="flex flex-wrap items-center gap-4 mt-2">
                 <p className="text-surface-400 text-lg capitalize font-medium mr-2">
                     {currentMonthName}
                 </p>
                 <select 
                     value={selectedPeriod}
                     onChange={(e) => setSelectedPeriod(e.target.value)}
                     className="bg-surface-800/50 border border-white/10 text-white text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2 backdrop-blur-md [&>option]:bg-surface-900 [&>option]:text-white"
                 >
                     {periodOptions.map(opt => (
                         <option key={opt.value} value={opt.value}>{opt.label}</option>
                     ))}
                 </select>

                 <select
                     value={labeledFilter}
                     onChange={(e) => setLabeledFilter(e.target.value as any)}
                     className="bg-surface-800/50 border border-white/10 text-white text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2 backdrop-blur-md [&>option]:bg-surface-900 [&>option]:text-white"
                 >
                     <option value="all">Todas las transacciones</option>
                     <option value="labeled">Solo Etiquetadas</option>
                     <option value="unlabeled">No Etiquetadas</option>
                 </select>

                 <select
                     value={reimbursableFilter}
                     onChange={(e) => setReimbursableFilter(e.target.value as any)}
                     className="bg-surface-800/50 border border-white/10 text-white text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2 backdrop-blur-md [&>option]:bg-surface-900 [&>option]:text-white"
                 >
                     <option value="all">Todas (Incl. Reembolsables)</option>
                     <option value="excluded">Sin Reembolsables</option>
                     <option value="included">Solo Reembolsables</option>
                 </select>

                 <select
                     value={priorityFilter}
                     onChange={(e) => setPriorityFilter(e.target.value as any)}
                     className={`bg-surface-800/50 border text-white text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2 backdrop-blur-md [&>option]:bg-surface-900 [&>option]:text-white ${
                         priorityFilter === 'all'
                         ? 'border-white/10'
                         : 'border-amber-400/60 ring-1 ring-amber-400/40'
                     }`}
                 >
                     <option value="all">Necesidades y Deseos (Todo)</option>
                     <option value="needs">Solo Necesidades</option>
                     <option value="wants">Solo Deseos</option>
                     <option value="rated">Solo Clasificadas (Nec + Des)</option>
                     <option value="unrated">Gastos sin Clasificar</option>
                 </select>

                 {/* Filtro de fondos */}
                 <div className="relative">
                     <button
                         onClick={() => setShowFundFilter(v => !v)}
                         className={`border text-sm rounded-lg px-3 py-2 flex items-center gap-2 transition-all ${
                             selectedFunds !== null
                             ? 'bg-teal-500/20 border-teal-500/50 text-teal-300 hover:bg-teal-500/30 shadow-sm shadow-teal-500/10'
                             : 'bg-surface-800/50 border-white/10 text-white hover:bg-surface-700 backdrop-blur-md'
                         }`}
                     >
                         <PiggyBank size={16} className={selectedFunds !== null ? 'text-teal-400' : 'text-surface-400'} />
                         <span className="hidden md:inline font-medium">
                             {fundFilterLabel(selectedFunds, funds)}
                         </span>
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

                 {(() => {
                     const includedCount = includedCategories.length + includedTags.length;
                     const excludedCount = excludedCategories.length + excludedTags.length;
                     const parts = [
                         includedCount > 0 ? `${includedCount} solo` : '',
                         excludedCount > 0 ? `${excludedCount} excl.` : '',
                     ].filter(Boolean);
                     return (
                         <button
                             onClick={() => setShowExclusionModal(true)}
                             className={`border text-sm rounded-lg block px-3 py-2 flex items-center gap-2 transition-colors ${
                                 includedCount > 0
                                 ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/30'
                                 : excludedCount > 0
                                 ? 'bg-rose-500/20 border-rose-500/50 text-rose-400 hover:bg-rose-500/30'
                                 : 'bg-surface-800/50 border-white/10 text-white hover:bg-surface-700 backdrop-blur-md'
                             }`}
                         >
                             <Filter size={16} />
                             <span className="hidden md:inline">
                                 Filtros {parts.length > 0 ? `(${parts.join(' · ')})` : ''}
                             </span>
                         </button>
                     );
                 })()}
                 
                 {selectedPeriod === 'custom' && (
                     <div className="flex items-center gap-2 animate-fade-in">
                         <input 
                             type="date" 
                             value={customStartDate}
                             onChange={(e) => setCustomStartDate(e.target.value)}
                             className="bg-surface-800/50 border border-white/10 text-white text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block px-3 py-2"
                         />
                         <span className="text-surface-500 font-medium">a</span>
                         <input 
                             type="date" 
                             value={customEndDate}
                             onChange={(e) => setCustomEndDate(e.target.value)}
                             className="bg-surface-800/50 border border-white/10 text-white text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block px-3 py-2"
                         />
                     </div>
                 )}
             </div>
          </div>
        </div>
          
         {loading ? (
            <div className="flex flex-col items-center justify-center py-32 gap-4">
                <div className="w-16 h-16 border-4 border-surface-800 border-t-primary-500 rounded-full animate-spin"></div>
                <p className="text-surface-400 font-medium animate-pulse">Cargando datos del periodo...</p>
            </div>
         ) : (
            <>
                {/* Navigation Tabs */}
                <div className="flex gap-4 border-b border-surface-800/80 mb-6">
                    <button 
                        onClick={() => { setActiveTab('budget'); setIsEditing(false); }}
                        className={`px-4 py-3 font-bold transition-all border-b-2 flex items-center gap-2 ${activeTab === 'budget' ? 'border-primary-500 text-white bg-surface-800/30' : 'border-transparent text-surface-400 hover:text-surface-300 hover:bg-surface-800/10'} rounded-t-lg`}
                    >
                        <Wallet size={18} /> Resumen General
                    </button>
                    <button 
                        onClick={() => { setActiveTab('happiness'); setIsEditing(false); }}
                        className={`px-4 py-3 font-bold transition-all border-b-2 flex items-center gap-2 ${activeTab === 'happiness' ? 'border-pink-500 text-white bg-surface-800/30' : 'border-transparent text-surface-400 hover:text-surface-300 hover:bg-surface-800/10'} rounded-t-lg`}
                    >
                        <Heart size={18} /> Análisis de Felicidad
                    </button>
                    <button 
                        onClick={() => { setActiveTab('needs'); setIsEditing(false); }}
                        className={`px-4 py-3 font-bold transition-all border-b-2 flex items-center gap-2 ${activeTab === 'needs' ? 'border-amber-400 text-white bg-surface-800/30' : 'border-transparent text-surface-400 hover:text-surface-300 hover:bg-surface-800/10'} rounded-t-lg`}
                    >
                        <Scale size={18} /> Necesidades vs Deseos
                    </button>
                    <button 
                        onClick={() => { setActiveTab('categories'); setIsEditing(false); }}
                        className={`px-4 py-3 font-bold transition-all border-b-2 flex items-center gap-2 ${activeTab === 'categories' ? 'border-purple-500 text-white bg-surface-800/30' : 'border-transparent text-surface-400 hover:text-surface-300 hover:bg-surface-800/10'} rounded-t-lg`}
                    >
                        <TrendingDown size={18} /> Categorías & Etiquetas
                    </button>
                </div>

                {activeTab === 'budget' ? (
            <GeneralBudgetTab 
                transactions={transactions}
                labeledFilter={labeledFilter}
                totalExpenses={totalExpenses}
                totalIncome={totalIncome}
                labelingStats={labelingStats}
                budgetConfig={budgetConfig}
                isEditing={isEditing}
                saving={saving}
                editTags={editTags}
                newTagKey={newTagKey}
                availableTags={availableTags}
                selectedPeriod={selectedPeriod}
                periodStart={activePeriodDates.firstDayStr}
                periodEnd={activePeriodDates.lastDayStr}
                setNewTagKey={setNewTagKey}
                setIsEditing={setIsEditing}
                setEditTags={setEditTags}
                handleAddNewTag={handleAddNewTag}
                handleRemoveTag={handleRemoveTag}
                handleSave={handleSave}
                openTagModal={openTagModal}
                openLocalModal={openLocalModal}
                formatCurrency={formatCurrency}
                renderProgressBar={renderProgressBar}
                tagExpenses={tagExpenses}
                tagBalances={tagBalances}
            />
        ) : activeTab === 'happiness' ? (
            <HappinessTab transactions={transactions} formatCurrency={formatCurrency} openLocalModal={openLocalModal} />
        ) : activeTab === 'needs' ? (
            <NeedsWantsTab transactions={transactions} totalIncome={totalIncome} formatCurrency={formatCurrency} renderProgressBar={renderProgressBar} openLocalModal={openLocalModal} />
        ) : activeTab === 'categories' ? (
            <CategoriesTagsTab transactions={transactions} CATEGORIES={CATEGORIES} availableTags={availableTags} formatCurrency={formatCurrency} openLocalModal={openLocalModal} />
                ) : null}
            </>
        )}

      </div>

      {/* Exclusion Modal */}
      {showExclusionModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
              <div className="bg-surface-900 border border-white/10 rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
                  <div className="p-6 border-b border-white/10 flex justify-between items-center bg-surface-800/50">
                      <div>
                          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                              Filtros de Categorías y Etiquetas
                          </h2>
                          <p className="text-surface-400 text-sm mt-1">
                              Clic en un elemento para alternar:{' '}
                              <span className="text-emerald-400 font-medium">solo mostrar</span> →{' '}
                              <span className="text-rose-400 font-medium">ocultar</span> → sin filtro.
                          </p>
                      </div>
                      <button onClick={() => setShowExclusionModal(false)} className="p-2 text-surface-400 hover:text-white transition-colors bg-surface-950 rounded-xl hover:bg-surface-700">
                          <X size={24} />
                      </button>
                  </div>

                  <div className="p-6 overflow-y-auto custom-scrollbar flex-1 space-y-8">
                      {(() => {
                          const renderChip = (value: string, included: string[], excluded: string[], onClick: () => void, fullWidth: boolean) => {
                              const isIncluded = included.includes(value);
                              const isExcluded = excluded.includes(value);
                              return (
                                  <button
                                      key={value}
                                      onClick={onClick}
                                      title={isIncluded ? 'Solo mostrar (clic para ocultar)' : isExcluded ? 'Oculto (clic para quitar el filtro)' : 'Sin filtro (clic para mostrar solo esto)'}
                                      className={`flex items-center gap-2 ${fullWidth ? 'p-2' : 'px-3 py-1.5'} rounded-lg border text-left text-sm transition-colors ${
                                          isIncluded
                                          ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300 font-medium'
                                          : isExcluded
                                          ? 'bg-rose-500/10 border-rose-500/30 text-rose-400 font-medium'
                                          : 'bg-surface-950 border-white/5 text-surface-300 hover:bg-surface-800'
                                      }`}
                                  >
                                      <span className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${
                                          isIncluded ? 'bg-emerald-500 border-emerald-500 text-surface-950'
                                          : isExcluded ? 'bg-rose-500 border-rose-500 text-surface-950'
                                          : 'border-surface-600 bg-surface-800'
                                      }`}>
                                          {isIncluded && <Check size={12} strokeWidth={3} />}
                                          {isExcluded && <X size={12} strokeWidth={3} />}
                                      </span>
                                      <span className={`truncate ${isExcluded ? 'line-through' : ''}`}>{value}</span>
                                  </button>
                              );
                          };

                          const renderHeader = (title: string, included: string[], excluded: string[], onClear: () => void) => (
                              <div className="flex justify-between items-center mb-4 gap-3">
                                  <div className="flex items-center gap-2 flex-wrap">
                                      <h3 className="text-lg font-bold text-white">{title}</h3>
                                      {included.length > 0 && (
                                          <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                                              Solo {included.length}
                                          </span>
                                      )}
                                      {excluded.length > 0 && (
                                          <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-300 border border-rose-500/30">
                                              Ocultas {excluded.length}
                                          </span>
                                      )}
                                  </div>
                                  {(included.length + excluded.length) > 0 && (
                                      <button onClick={onClear} className="text-xs text-surface-400 hover:text-white shrink-0">
                                          Limpiar
                                      </button>
                                  )}
                              </div>
                          );

                          const cycle = (
                              value: string,
                              included: string[], setIncluded: (v: string[]) => void,
                              excluded: string[], setExcluded: (v: string[]) => void,
                          ) => {
                              const next = cycleIncludeExclude(value, included, excluded);
                              setIncluded(next.included);
                              setExcluded(next.excluded);
                          };

                          return (
                              <>
                      {/* Categorías */}
                      <div>
                          {renderHeader('Categorías', includedCategories, excludedCategories, () => { setIncludedCategories([]); setExcludedCategories([]); })}
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                              {[...CATEGORIES.filter(c => c !== '---'), SIN_CATEGORIA].map(cat =>
                                  renderChip(cat, includedCategories, excludedCategories,
                                      () => cycle(cat, includedCategories, setIncludedCategories, excludedCategories, setExcludedCategories), true)
                              )}
                          </div>
                      </div>

                      {/* Etiquetas */}
                      <div>
                          {renderHeader('Etiquetas', includedTags, excludedTags, () => { setIncludedTags([]); setExcludedTags([]); })}
                          {includedTags.length > 1 && (
                              <p className="text-xs text-surface-500 -mt-2 mb-3">Se muestran las transacciones que tengan al menos una de las etiquetas marcadas.</p>
                          )}
                          <div className="flex flex-wrap gap-2">
                              {[...availableTags, SIN_ETIQUETA].map(tag =>
                                  renderChip(tag, includedTags, excludedTags,
                                      () => cycle(tag, includedTags, setIncludedTags, excludedTags, setExcludedTags), false)
                              )}
                          </div>
                          {availableTags.length === 0 && (
                              <p className="text-surface-500 text-sm italic">No hay etiquetas disponibles aún.</p>
                          )}
                      </div>
                              </>
                          );
                      })()}
                  </div>
                  <div className="p-4 border-t border-white/10 bg-surface-800/50 flex justify-end">
                      <button 
                          onClick={() => setShowExclusionModal(false)}
                          className="px-6 py-2 bg-primary-600 hover:bg-primary-500 text-white font-bold rounded-xl transition-colors shadow-lg"
                      >
                          Aplicar y Cerrar
                      </button>
                  </div>
              </div>
          </div>
      )}

      {/* Transaction Modal */}
      {modalTitle && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
              <div className="bg-surface-900 border border-white/10 rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
                  <div className="p-6 border-b border-white/10 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-surface-800/50">
                      <div className="flex items-center gap-3">
                          {modalHistory.length > 0 && (
                              <button
                                  onClick={handleModalBack}
                                  className="p-2 text-surface-400 hover:text-white transition-colors bg-surface-950 rounded-xl hover:bg-surface-700 shrink-0"
                                  title="Volver a la vista anterior"
                              >
                                  <ArrowLeft size={20} />
                              </button>
                          )}
                          <div>
                              <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                                  {modalTitle}
                              </h2>
                              <p className="text-surface-400 text-sm mt-1">{modalDescription}</p>
                          </div>
                      </div>
                      <div className="flex items-center gap-3 self-end sm:self-center shrink-0">
                          {modalTransactions.length > 0 && (
                              <button
                                  onClick={() => setModalViewMode(modalViewMode === 'list' ? 'chart' : 'list')}
                                  className="px-4 py-2 bg-gradient-to-r from-primary-600 to-indigo-600 hover:from-primary-500 hover:to-indigo-500 text-white font-bold rounded-xl transition-all shadow-lg flex items-center gap-2 text-sm"
                              >
                                  {modalViewMode === 'list' ? (
                                      <>
                                          <BarChart3 size={16} />
                                          Ver Gráfica
                                      </>
                                  ) : (
                                      <>
                                          <List size={16} />
                                          Ver Lista
                                      </>
                                  )}
                              </button>
                          )}
                          <button onClick={handleCloseModal} className="p-2 text-surface-400 hover:text-white transition-colors bg-surface-950 rounded-xl hover:bg-surface-700">
                              <X size={24} />
                          </button>
                      </div>
                  </div>
                  
                  <div className="p-6 overflow-y-auto custom-scrollbar flex-1">
                      {loadingModal ? (
                           <div className="flex justify-center items-center py-20">
                               <div className="w-12 h-12 border-4 border-surface-800 border-t-primary-500 rounded-full animate-spin"></div>
                           </div>
                      ) : (
                          <>
                              <div className="grid grid-cols-2 gap-4 mb-6">
                                  <div className="bg-surface-950 p-4 rounded-xl border border-white/5">
                                      <p className="text-sm text-surface-400 uppercase font-bold tracking-wider mb-1">Total Ingresos (+)</p>
                                      <p className="text-2xl font-bold text-emerald-400 flex justify-between items-baseline">
                                          {formatCurrency(modalTransactions.filter(t => t.MONTO > 0).reduce((acc, t) => acc + t.MONTO, 0))}
                                          <span className="text-xs font-normal text-surface-500 px-2 py-1 bg-emerald-500/10 rounded-lg">{modalTransactions.filter(t => t.MONTO > 0).length} txs</span>
                                      </p>
                                  </div>
                                  <div className="bg-surface-950 p-4 rounded-xl border border-white/5">
                                      <p className="text-sm text-surface-400 uppercase font-bold tracking-wider mb-1">Total Gastos (-)</p>
                                      <p className="text-2xl font-bold text-rose-400 flex justify-between items-baseline">
                                          {formatCurrency(Math.abs(modalTransactions.filter(t => t.MONTO < 0).reduce((acc, t) => acc + t.MONTO, 0)))}
                                          <span className="text-xs font-normal text-surface-500 px-2 py-1 bg-rose-500/10 rounded-lg">{modalTransactions.filter(t => t.MONTO < 0).length} txs</span>
                                      </p>
                                  </div>
                              </div>
                              
                              {modalViewMode === 'chart' && modalChartsData ? (
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
                                      {/* Top Comercios */}
                                      {modalChartsData.barChartOption ? (
                                          <div className="bg-surface-950/40 border border-white/5 p-5 rounded-2xl flex flex-col">
                                              <h3 className="text-base font-bold text-white mb-3">Top 10 Comercios / Conceptos</h3>
                                              <div className="h-[380px] w-full relative flex items-center justify-center">
                                                  <ReactECharts 
                                                      option={modalChartsData.barChartOption} 
                                                      style={{ height: '100%', width: '100%' }} 
                                                      onEvents={{
                                                          'click': (params: any) => {
                                                              if (!params || !params.name) return;
                                                              const name = params.name;
                                                              const filtered = modalTransactions.filter(t => {
                                                                  const cName = t.nombre_limpio || t.DESCRIPCION || "Desconocido";
                                                                  return cName === name;
                                                              });
                                                              if (filtered.length > 0) {
                                                                  openLocalModal(
                                                                      `Comercio: ${name}`,
                                                                      `Transacciones agrupadas bajo ${name}`,
                                                                      filtered.sort((a,b) => new Date(b.FECHA).getTime() - new Date(a.FECHA).getTime()),
                                                                      true
                                                                  );
                                                              }
                                                          }
                                                      }}
                                                  />
                                              </div>
                                          </div>
                                      ) : (
                                          <div className="bg-surface-950/40 border border-white/5 p-5 rounded-2xl flex items-center justify-center h-[350px]">
                                              <p className="text-surface-500 italic text-sm">No hay suficientes gastos para graficar comercios.</p>
                                          </div>
                                      )}

                                      {/* Distribution Pie Chart */}
                                      {modalChartsData.pieChartOption ? (
                                          <div className="bg-surface-950/40 border border-white/5 p-5 rounded-2xl flex flex-col">
                                               <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                                                   <h3 className="text-base font-bold text-white">{modalChartsData.pieTitle}</h3>
                                                   {modalChartsData.isCategory && (
                                                       <div className="flex items-center gap-1 bg-surface-950 p-1 rounded-xl border border-white/5 shrink-0 self-start sm:self-auto">
                                                           <button
                                                               onClick={() => setTagCountMode('proportional')}
                                                               className={`px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
                                                                   tagCountMode === 'proportional'
                                                                       ? 'bg-primary-600 text-white shadow-md'
                                                                       : 'text-surface-400 hover:text-white'
                                                               }`}
                                                               title="Dividir el monto de la transacción entre la cantidad de etiquetas (cuenta 1 vez en total)"
                                                           >
                                                               Dividir (1x)
                                                           </button>
                                                           <button
                                                               onClick={() => setTagCountMode('full')}
                                                               className={`px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
                                                                   tagCountMode === 'full'
                                                                       ? 'bg-primary-600 text-white shadow-md'
                                                                       : 'text-surface-400 hover:text-white'
                                                               }`}
                                                               title="Asignar el monto completo a cada etiqueta (cuenta en cada una)"
                                                           >
                                                               Monto completo
                                                           </button>
                                                       </div>
                                                   )}
                                               </div>
                                              <div className="h-[380px] w-full relative flex items-center justify-center">
                                                  <ReactECharts 
                                                      option={modalChartsData.pieChartOption} 
                                                      style={{ height: '100%', width: '100%' }} 
                                                      onEvents={{
                                                          'click': (params: any) => {
                                                              if (!params || !params.name) return;
                                                              const name = params.name;
                                                              let filtered: any[] = [];

                                                              if (modalChartsData.isCategory) {
                                                                  filtered = modalTransactions.filter(t => {
                                                                      if (name === 'Sin Etiqueta') return !t.tags || t.tags.trim() === '';
                                                                      if (!t.tags) return false;
                                                                      return parseTags(t.tags).includes(name);
                                                                  });
                                                                  if (filtered.length > 0) {
                                                                      openLocalModal(
                                                                          `Etiqueta: ${name}`,
                                                                          `Transacciones con la etiqueta #${name}`,
                                                                          filtered.sort((a,b) => new Date(b.FECHA).getTime() - new Date(a.FECHA).getTime()),
                                                                          true
                                                                      );
                                                                  }
                                                              } else {
                                                                  filtered = modalTransactions.filter(t => {
                                                                      const cat = (!t.categoria || t.categoria === '---') ? 'Sin Categoría' : t.categoria;
                                                                      return cat === name;
                                                                  });
                                                                  if (filtered.length > 0) {
                                                                      openLocalModal(
                                                                          `Categoría: ${name}`,
                                                                          `Transacciones en la categoría ${name}`,
                                                                          filtered.sort((a,b) => new Date(b.FECHA).getTime() - new Date(a.FECHA).getTime()),
                                                                          true
                                                                      );
                                                                  }
                                                              }
                                                          }
                                                      }}
                                                  />
                                              </div>
                                          </div>
                                      ) : (
                                          <div className="bg-surface-950/40 border border-white/5 p-5 rounded-2xl flex items-center justify-center h-[350px]">
                                              <p className="text-surface-500 italic text-sm">No hay suficientes datos para graficar la distribución.</p>
                                          </div>
                                      )}
                                  </div>
                              ) : (
                                  <>
                                      {/* Ordenamiento */}
                                      <div className="flex justify-between items-center mb-4 px-1">
                                          <span className="text-xs font-bold uppercase tracking-wider text-surface-400">Transacciones del periodo</span>
                                          <div className="flex gap-2 bg-surface-950 p-1 rounded-xl border border-white/5">
                                              <button 
                                                  onClick={() => setModalSortBy('amount')}
                                                  className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${modalSortBy === 'amount' ? 'bg-primary-600 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
                                              >
                                                  Por Monto
                                              </button>
                                              <button 
                                                  onClick={() => setModalSortBy('date')}
                                                  className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${modalSortBy === 'date' ? 'bg-primary-600 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
                                              >
                                                  Por Fecha
                                              </button>
                                          </div>
                                      </div>

                                      <div className="space-y-3">
                                          {sortedModalTransactions.length === 0 ? (
                                              <div className="text-center py-10 text-surface-500">No hay transacciones para mostrar.</div>
                                          ) : (
                                              sortedModalTransactions.map((tx) => {
                                                  const full = groupedById.get(tx.id);
                                                  return (
                                                      <BudgetTransactionRow
                                                          key={tx.id}
                                                          tx={tx}
                                                          parts={full?.subTransactions || tx.subTransactions}
                                                          fund={matchFund(tx, funds)}
                                                          formatCurrency={formatCurrency}
                                                          onClick={() => setEditingTransaction(full || tx)}
                                                      />
                                                  );
                                              })
                                          )}
                                      </div>
                                  </>
                              )}
                          </>
                      )}
                  </div>
              </div>
          </div>
      )}

      {/* Modal de etiquetado: va después para quedar por encima del modal de detalle */}
      <EditModal
        transaction={editingTransaction}
        isOpen={!!editingTransaction}
        onClose={() => setEditingTransaction(null)}
        onSave={handleTransactionSave}
        categories={CATEGORIES}
        existingTags={availableTags}
      />
    </div>
  );
}
