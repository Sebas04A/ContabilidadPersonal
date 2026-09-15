import { useState, useEffect, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { api, Transaction, TransactionUpdate, BudgetConfig } from '../services/api';
import { Wallet, X, TrendingDown, Heart, Scale, Filter, BarChart3, List, PiggyBank, Check, ArrowLeft } from 'lucide-react';

import { groupSplits } from '../utils/groupSplits';
import { matchFund } from '../utils/matchFund';
import { useFunds } from '../hooks/useTransactions';
import { EditModal } from '../components/EditModal';
import { BudgetTransactionRow } from '../components/budget/BudgetTransactionRow';

import { GeneralBudgetTab } from '../components/budget/GeneralBudgetTab';
import { HappinessTab } from '../components/budget/HappinessTab';
import { NeedsWantsTab } from '../components/budget/NeedsWantsTab';
import { CategoriesTagsTab } from '../components/budget/CategoriesTagsTab';

const CATEGORIES = ['Alimentación', 'Transporte', 'Ocio', 'Salud', 'Subscripciones', 'Mensual', 'Inversion', 'Regalo', 'Mujeres', 'Aseo', 'Deudas', 'Tarjeta', 'Ropa', 'Viajes', 'Otro'];

export function MonthlyBudget() {
  const [activeTab, setActiveTab] = useState<'budget' | 'happiness' | 'needs' | 'categories'>(() => {
    const saved = localStorage.getItem('budget_activeTab');
    return (saved as any) || 'budget';
  });
  const [budgetConfig, setBudgetConfig] = useState<BudgetConfig>({ tracked_tags: [] });
  const [allPeriodTransactions, setAllPeriodTransactions] = useState<Transaction[]>([]);
  const [labeledFilter, setLabeledFilter] = useState<'all' | 'labeled' | 'unlabeled'>(() => {
    const saved = localStorage.getItem('budget_labeledFilter');
    return (saved as any) || 'all';
  });
  const [reimbursableFilter, setReimbursableFilter] = useState<'all' | 'included' | 'excluded'>(() => {
    const saved = localStorage.getItem('budget_reimbursableFilter');
    return (saved as any) || 'all';
  });
  const [priorityFilter, setPriorityFilter] = useState<'all' | 'needs' | 'wants' | 'rated'>(() => {
    const saved = localStorage.getItem('budget_priorityFilter');
    return (saved as any) || 'all';
  });

  const [excludedCategories, setExcludedCategories] = useState<string[]>(() => {
    const saved = localStorage.getItem('budget_excludedCategories');
    try {
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [excludedTags, setExcludedTags] = useState<string[]>(() => {
    const saved = localStorage.getItem('budget_excludedTags');
    try {
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  // Inclusiones: si hay alguna, solo se muestran las transacciones que coinciden.
  const [includedCategories, setIncludedCategories] = useState<string[]>(() => {
    const saved = localStorage.getItem('budget_includedCategories');
    try {
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [includedTags, setIncludedTags] = useState<string[]>(() => {
    const saved = localStorage.getItem('budget_includedTags');
    try {
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [showExclusionModal, setShowExclusionModal] = useState(false);

  const txCategory = (t: Transaction) => (!t.categoria || t.categoria === '---') ? 'Sin Categoría' : t.categoria;
  // Una transacción sin tags cuenta como la pseudo-etiqueta 'Sin Etiqueta'.
  const txTags = (t: Transaction) => {
      const tags = t.tags ? t.tags.split(',').map(tag => tag.trim()).filter(Boolean) : [];
      return tags.length > 0 ? tags : ['Sin Etiqueta'];
  };

  /**
   * Filtro de categorías y etiquetas. Las inclusiones se combinan con Y entre
   * categoría y etiqueta (si hay de ambas, deben cumplirse las dos) y con O dentro
   * de cada grupo. Las exclusiones se aplican después y siempre ganan.
   */
  const matchesCategoryTag = (t: Transaction) => {
      const cat = txCategory(t);
      const tags = txTags(t);
      if (includedCategories.length > 0 && !includedCategories.includes(cat)) return false;
      if (includedTags.length > 0 && !tags.some(tg => includedTags.includes(tg))) return false;
      if (excludedCategories.includes(cat)) return false;
      if (tags.some(tg => excludedTags.includes(tg))) return false;
      return true;
  };

  // Clic en un chip del modal: sin filtro → solo mostrar → ocultar → sin filtro.
  const cycleFilter = (
      value: string,
      included: string[], setIncluded: (v: string[]) => void,
      excluded: string[], setExcluded: (v: string[]) => void,
  ) => {
      if (included.includes(value)) {
          setIncluded(included.filter(v => v !== value));
          setExcluded([...excluded, value]);
      } else if (excluded.includes(value)) {
          setExcluded(excluded.filter(v => v !== value));
      } else {
          setIncluded([...included, value]);
      }
  };

  // Lista de fondos (cacheada por react-query) para marcar y filtrar a qué fondo
  // pertenece cada transacción: búsqueda en memoria, sin peticiones por fila.
  const { data: funds } = useFunds();

  /**
   * Fondos seleccionados. Si `selectedFunds` es `null`, significa 'por defecto (todos marcados)'.
   * De lo contrario es un array con los IDs de los fondos actualmente marcados.
   */
  const [selectedFunds, setSelectedFunds] = useState<string[] | null>(() => {
    const saved = localStorage.getItem('budget_selectedFunds');
    try {
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [showFundFilter, setShowFundFilter] = useState(false);

  // Array efectivo de fondos marcados (si es null, son todos los disponibles)
  const activeFundIds = useMemo(() => {
    if (selectedFunds === null) {
      return (funds || []).map(f => f.id);
    }
    return selectedFunds;
  }, [selectedFunds, funds]);

  const matchesFund = (t: Transaction) => {
    const f = matchFund(t, funds);
    if (!f) return true; // Las transacciones que no pertenecen a NINGÚN fondo SIEMPRE se muestran
    
    // Si la transacción pertenece a un fondo:
    // Solo se muestra si ese fondo está marcado en la lista de activos
    return activeFundIds.includes(f.id);
  };

  // El filtro de prioridad solo aplica a gastos: los ingresos no se clasifican
  // como Necesidad/Deseo y deben seguir contando para los porcentajes.
  const matchesPriority = (t: Transaction) => {
      if (priorityFilter === 'all' || t.MONTO >= 0) return true;
      if (priorityFilter === 'needs') return t.prioridad === 'Necesidad';
      if (priorityFilter === 'wants') return t.prioridad === 'Deseo';
      return t.prioridad === 'Necesidad' || t.prioridad === 'Deseo';
  };

  const filteredByReimbursable = useMemo(() => {
     return allPeriodTransactions.filter(t => {
         if (!matchesPriority(t)) return false;
         if (!matchesFund(t)) return false;
         if (reimbursableFilter === 'all') return true;
         const isReim = t.es_reembolsable;
         return reimbursableFilter === 'included' ? isReim : !isReim;
     });
  }, [allPeriodTransactions, reimbursableFilter, priorityFilter, selectedFunds, funds]);

  const transactionsBaseFilter = useMemo(() => {
     return filteredByReimbursable.filter(matchesCategoryTag);
  }, [filteredByReimbursable, excludedCategories, excludedTags, includedCategories, includedTags]);

  const transactions = useMemo(() => {
      return transactionsBaseFilter.filter(t => {
          if (labeledFilter !== 'all') {
             const isLabeled = t.revisado;
             if (labeledFilter === 'labeled' && !isLabeled) return false;
             if (labeledFilter === 'unlabeled' && isLabeled) return false;
          }
          return true;
      });
  }, [transactionsBaseFilter, labeledFilter]);

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
    localStorage.setItem('budget_labeledFilter', labeledFilter);
  }, [labeledFilter]);

  useEffect(() => {
    localStorage.setItem('budget_reimbursableFilter', reimbursableFilter);
  }, [reimbursableFilter]);

  useEffect(() => {
    localStorage.setItem('budget_priorityFilter', priorityFilter);
  }, [priorityFilter]);

  useEffect(() => {
    localStorage.setItem('budget_excludedCategories', JSON.stringify(excludedCategories));
  }, [excludedCategories]);

  useEffect(() => {
    localStorage.setItem('budget_excludedTags', JSON.stringify(excludedTags));
  }, [excludedTags]);

  useEffect(() => {
    localStorage.setItem('budget_includedCategories', JSON.stringify(includedCategories));
  }, [includedCategories]);

  useEffect(() => {
    localStorage.setItem('budget_includedTags', JSON.stringify(includedTags));
  }, [includedTags]);

  useEffect(() => {
    localStorage.setItem('budget_selectedFunds', JSON.stringify(selectedFunds));
  }, [selectedFunds]);

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
        const tTags = t.tags.split(',').map(tag => tag.trim());
        tTags.forEach(tag => {
          if (!expenses[tag]) expenses[tag] = 0;
          expenses[tag] += (t.MONTO * -1); // Summing negative amounts as positive expenses, and positive amounts as deductions
        });
      }
    });
    return expenses;
  }, [transactions]);

  const allTimeFiltered = useMemo(() => {
      return allTimeTransactions.filter(t => {
         if (!matchesPriority(t)) return false;
         if (!matchesFund(t)) return false;

         if (reimbursableFilter === 'excluded' && t.es_reembolsable) return false;
         if (reimbursableFilter === 'included' && !t.es_reembolsable) return false;
         
         if (labeledFilter === 'labeled' && !t.revisado) return false;
         if (labeledFilter === 'unlabeled' && t.revisado) return false;

         return matchesCategoryTag(t);
      });
  }, [allTimeTransactions, reimbursableFilter, labeledFilter, priorityFilter, excludedCategories, excludedTags, includedCategories, includedTags, selectedFunds, funds]);

  const tagBalances = useMemo(() => {
    const balances: Record<string, number> = {};
    if (!budgetConfig.tracked_tags) return balances;
    
    budgetConfig.tracked_tags.forEach(tag => {
       const sum = allTimeFiltered
          .filter(t => t.tags && t.tags.split(',').map(tg => tg.trim()).includes(tag) && t.MONTO > 0)
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
    
    const txs = allTimeFiltered.filter(t => t.tags && t.tags.split(',').map(tg => tg.trim()).includes(tag) && t.MONTO > 0);
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
  const formatCurrency = (val: number) => val.toLocaleString('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

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
              const tTags = t.tags.split(',').map(tag => tag.trim()).filter(Boolean);
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
                  trigger: 'axis',
                  axisPointer: { type: 'shadow' },
                  confine: true,
                  position: (pos: any) => [pos[0] + 15, Math.max(10, pos[1] - 30)],
                  formatter: (params: any) => {
                      const d = params[0].data;
                      return `<strong class="text-white">${d.name}</strong><br/>Monto: $${d.value.toLocaleString('es-CO')}`;
                  },
                  backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#f3f4f6' }
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
                  trigger: 'item',
                  formatter: (params: any) => {
                      const percentage = totalNegative > 0 ? (params.value / totalNegative) * 100 : 0;
                      return `<strong class="text-white">${params.name}</strong><br/>Monto Distribuido: $${params.value.toLocaleString('es-CO')}<br/>Proporción: ${percentage.toFixed(1)}%`;
                  },
                  backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#f3f4f6' }
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
                  trigger: 'item',
                  formatter: (params: any) => {
                      return `<strong class="text-white">${params.data.name}</strong><br/>Monto: $${params.data.value.toLocaleString('es-CO')} (${params.percent.toFixed(1)}%)`;
                  },
                  backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#f3f4f6' }
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
                  trigger: 'item',
                  formatter: (params: any) => {
                      return `<strong class="text-white">${params.data.name}</strong><br/>Monto: $${params.data.value.toLocaleString('es-CO')} (${params.percent.toFixed(1)}%)`;
                  },
                  backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#f3f4f6' }
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
                 </select>

                 {/* Filtro de fondos */}
                 <div className="relative">
                     {(() => {
                         const fundList = funds || [];
                         const totalFundsCount = fundList.length;
                         const isAllSelected = activeFundIds.length === totalFundsCount && totalFundsCount > 0;
                         const isNoneSelected = activeFundIds.length === 0;

                         let buttonLabel = 'Todos los fondos';
                         if (isNoneSelected) {
                             buttonLabel = 'Solo sin fondo (0 de ' + totalFundsCount + ')';
                         } else if (isAllSelected) {
                             buttonLabel = 'Todos los fondos';
                         } else if (activeFundIds.length === 1) {
                             const singleFund = fundList.find(f => f.id === activeFundIds[0]);
                             buttonLabel = singleFund ? singleFund.name : '1 fondo';
                         } else {
                             buttonLabel = `Fondos (${activeFundIds.length}/${totalFundsCount})`;
                         }

                         return (
                             <>
                                 <button
                                     onClick={() => setShowFundFilter(v => !v)}
                                     className={`border text-sm rounded-lg px-3 py-2 flex items-center gap-2 transition-all ${
                                         !isNoneSelected
                                         ? 'bg-teal-500/20 border-teal-500/50 text-teal-300 hover:bg-teal-500/30 shadow-sm shadow-teal-500/10'
                                         : 'bg-surface-800/40 border-white/10 text-surface-400 hover:bg-surface-700 hover:text-surface-200 backdrop-blur-md opacity-70'
                                     }`}
                                 >
                                     <PiggyBank size={16} className={!isNoneSelected ? "text-teal-400" : "text-surface-500"} />
                                     <span className="hidden md:inline font-medium">
                                         {buttonLabel}
                                     </span>
                                     {!isNoneSelected && !isAllSelected && (
                                         <span className="bg-teal-500 text-surface-950 font-bold text-[10px] px-1.5 py-0.2 rounded-full min-w-[18px] text-center">
                                             {activeFundIds.length}
                                         </span>
                                     )}
                                     {isAllSelected && (
                                         <span className="bg-teal-500/30 text-teal-200 text-[10px] font-semibold px-1.5 py-0.5 rounded border border-teal-500/30">
                                             Todos
                                         </span>
                                     )}
                                     {isNoneSelected && (
                                         <span className="bg-white/10 text-surface-400 text-[10px] font-semibold px-1.5 py-0.5 rounded">
                                             0
                                         </span>
                                     )}
                                 </button>

                                 {showFundFilter && (
                                     <>
                                         <div className="fixed inset-0 z-30" onClick={() => setShowFundFilter(false)} />
                                         <div className="absolute z-40 mt-2 w-72 right-0 bg-surface-900 border border-white/10 rounded-xl shadow-2xl p-3 space-y-2 backdrop-blur-xl">
                                             <div className="flex justify-between items-center px-1 pb-2 border-b border-white/10">
                                                 <div className="flex items-center gap-1.5">
                                                     <PiggyBank size={14} className="text-teal-400" />
                                                     <span className="text-xs font-bold uppercase tracking-wider text-surface-300">Filtrar por Fondo</span>
                                                 </div>
                                                 <div className="flex items-center gap-2">
                                                     <button
                                                         onClick={() => setSelectedFunds(fundList.map(f => f.id))}
                                                         className="text-[11px] text-teal-400 hover:text-teal-300 font-semibold transition-colors"
                                                     >
                                                         Marcar todos
                                                     </button>
                                                     <span className="text-surface-600">|</span>
                                                     <button
                                                         onClick={() => setSelectedFunds([])}
                                                         className="text-[11px] text-surface-400 hover:text-surface-200 font-semibold transition-colors"
                                                     >
                                                         Desmarcar todos
                                                     </button>
                                                 </div>
                                             </div>

                                             <div className="max-h-64 overflow-y-auto custom-scrollbar space-y-1 pr-0.5">
                                                 {fundList.length === 0 && (
                                                     <p className="text-xs text-surface-500 italic px-1 py-2 text-center">No hay fondos configurados.</p>
                                                 )}

                                                 {fundList.map(opt => {
                                                     const checked = activeFundIds.includes(opt.id);
                                                     return (
                                                         <button
                                                             key={opt.id}
                                                             onClick={() => {
                                                                 const current = activeFundIds;
                                                                 const next = current.includes(opt.id)
                                                                     ? current.filter(x => x !== opt.id)
                                                                     : [...current, opt.id];
                                                                 setSelectedFunds(next);
                                                             }}
                                                             className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left text-sm transition-all ${
                                                                 checked 
                                                                     ? 'bg-teal-500/15 text-teal-200 border border-teal-500/30' 
                                                                     : 'text-surface-400 hover:bg-white/5 border border-transparent'
                                                             }`}
                                                         >
                                                             <div className="flex items-center gap-2.5 truncate pr-2">
                                                                 <span className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors ${
                                                                     checked ? 'bg-teal-500 border-teal-500 text-surface-950' : 'border-white/20'
                                                                 }`}>
                                                                     {checked && <Check size={12} strokeWidth={3} />}
                                                                 </span>
                                                                 <span className="truncate font-medium">
                                                                     {opt.name}
                                                                 </span>
                                                             </div>

                                                             {opt.tag_vinculado && (
                                                                 <span className="text-[10px] bg-white/5 text-surface-400 px-1.5 py-0.5 rounded border border-white/5 shrink-0">
                                                                     #{opt.tag_vinculado}
                                                                 </span>
                                                             )}
                                                         </button>
                                                     );
                                                 })}
                                             </div>

                                             <div className="pt-2 border-t border-white/10 flex justify-between items-center text-[10px] text-surface-400 px-1">
                                                 <span>
                                                     {isNoneSelected 
                                                         ? 'Mostrando solo transacciones sin fondo' 
                                                         : isAllSelected
                                                             ? 'Todos los fondos marcados + No fondos'
                                                             : `${activeFundIds.length} de ${totalFundsCount} fondos + No fondos`}
                                                 </span>
                                                 {!isAllSelected && (
                                                     <button 
                                                         onClick={() => setSelectedFunds(fundList.map(f => f.id))}
                                                         className="text-teal-400 hover:text-teal-300 underline"
                                                     >
                                                         Restablecer todos
                                                     </button>
                                                 )}
                                             </div>
                                         </div>
                                     </>
                                 )}
                             </>
                         );
                     })()}
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

                          return (
                              <>
                      {/* Categorías */}
                      <div>
                          {renderHeader('Categorías', includedCategories, excludedCategories, () => { setIncludedCategories([]); setExcludedCategories([]); })}
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                              {[...CATEGORIES.filter(c => c !== '---'), 'Sin Categoría'].map(cat =>
                                  renderChip(cat, includedCategories, excludedCategories,
                                      () => cycleFilter(cat, includedCategories, setIncludedCategories, excludedCategories, setExcludedCategories), true)
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
                              {[...availableTags, 'Sin Etiqueta'].map(tag =>
                                  renderChip(tag, includedTags, excludedTags,
                                      () => cycleFilter(tag, includedTags, setIncludedTags, excludedTags, setExcludedTags), false)
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
                                                                      return t.tags.split(',').map((tag: string) => tag.trim()).filter(Boolean).includes(name);
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
