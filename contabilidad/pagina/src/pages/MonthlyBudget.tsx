import { useState, useEffect, useMemo } from 'react';
import { api, Transaction, BudgetConfig } from '../services/api';
import { Wallet, X, TrendingDown, Heart, Scale, Filter } from 'lucide-react';


import { GeneralBudgetTab } from '../components/budget/GeneralBudgetTab';
import { HappinessTab } from '../components/budget/HappinessTab';
import { NeedsWantsTab } from '../components/budget/NeedsWantsTab';
import { CategoriesTagsTab } from '../components/budget/CategoriesTagsTab';

const CATEGORIES = ['Alimentación', 'Transporte', 'Ocio', 'Salud', 'Subscripciones', 'Mensual', 'Inversion', 'Regalo', 'Mujeres', 'Aseo', 'Deudas', 'Tarjeta', 'Ropa', 'Viajes', 'Otro'];

export function MonthlyBudget() {
  const [activeTab, setActiveTab] = useState<'budget' | 'happiness' | 'needs' | 'categories'>('budget');
  const [budgetConfig, setBudgetConfig] = useState<BudgetConfig>({ tracked_tags: [] });
  const [allPeriodTransactions, setAllPeriodTransactions] = useState<Transaction[]>([]);
  const [labeledFilter, setLabeledFilter] = useState<'all' | 'labeled' | 'unlabeled'>('all');
  const [reimbursableFilter, setReimbursableFilter] = useState<'all' | 'included' | 'excluded'>('all');
  
  const [excludedCategories, setExcludedCategories] = useState<string[]>([]);
  const [excludedTags, setExcludedTags] = useState<string[]>([]);
  const [showExclusionModal, setShowExclusionModal] = useState(false);
  
  const filteredByReimbursable = useMemo(() => {
     return allPeriodTransactions.filter(t => {
         if (reimbursableFilter === 'all') return true;
         const isReim = t.es_reembolsable;
         return reimbursableFilter === 'included' ? isReim : !isReim;
     });
  }, [allPeriodTransactions, reimbursableFilter]);

  const transactionsBaseFilter = useMemo(() => {
     return filteredByReimbursable.filter(t => {
         const tCategory = (!t.categoria || t.categoria === '---') ? 'Sin Categoría' : t.categoria;
         if (excludedCategories.includes(tCategory)) return false;

         if (excludedTags.length > 0) {
             const tTags = t.tags ? t.tags.split(',').map(tag => tag.trim()).filter(Boolean) : [];
             if (tTags.length === 0) {
                 if (excludedTags.includes('Sin Etiqueta')) return false;
             } else {
                 if (tTags.some(tg => excludedTags.includes(tg))) return false;
             }
         }

         return true;
     });
  }, [filteredByReimbursable, excludedCategories, excludedTags]);

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

  const [selectedPeriod, setSelectedPeriod] = useState<string>('current');
  const [customStartDate, setCustomStartDate] = useState<string>('');
  const [customEndDate, setCustomEndDate] = useState<string>('');
  const [currentMonthName, setCurrentMonthName] = useState("");
  const [availableTags, setAvailableTags] = useState<string[]>([]);

  // Modal State
  const [modalTitle, setModalTitle] = useState<string | null>(null);
  const [modalDescription, setModalDescription] = useState<string>("");
  const [modalTransactions, setModalTransactions] = useState<Transaction[]>([]);
  const [loadingModal, setLoadingModal] = useState(false);

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

  useEffect(() => {
    const fetchPeriodTransactions = async () => {
      // Don't fetch if custom is selected but dates are missing
      if (selectedPeriod === 'custom' && (!customStartDate || !customEndDate)) {
          return;
      }

      setLoading(true);
      try {
        let firstDayStr = undefined;
        let lastDayStr = undefined;
        let title = "";

        if (selectedPeriod === 'current') {
            const now = new Date();
            const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
            const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
            firstDayStr = firstDay.toISOString().split('T')[0];
            lastDayStr = lastDay.toISOString().split('T')[0];
            title = new Intl.DateTimeFormat('es-CO', { year: 'numeric', month: 'long' }).format(now);
        } else if (selectedPeriod === 'all') {
            title = "Todo el tiempo";
        } else if (selectedPeriod === 'custom') {
            firstDayStr = customStartDate;
            lastDayStr = customEndDate;
            title = `Desde ${customStartDate} hasta ${customEndDate}`;
        } else {
            const [year, month] = selectedPeriod.split('-');
            const firstDay = new Date(Number(year), Number(month) - 1, 1);
            const lastDay = new Date(Number(year), Number(month), 0);
            firstDayStr = firstDay.toISOString().split('T')[0];
            lastDayStr = lastDay.toISOString().split('T')[0];
            title = new Intl.DateTimeFormat('es-CO', { year: 'numeric', month: 'long' }).format(firstDay);
        }

        setCurrentMonthName(title);

        const data = await api.getTransactions(
          undefined, undefined, undefined,
          firstDayStr,
          lastDayStr
        );
        setAllPeriodTransactions(data);
      } catch (error) {
        console.error("Error loading period data", error);
      } finally {
        setLoading(false);
      }
    };
    fetchPeriodTransactions();
  }, [selectedPeriod, customStartDate, customEndDate]);

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
         if (reimbursableFilter === 'excluded' && t.es_reembolsable) return false;
         if (reimbursableFilter === 'included' && !t.es_reembolsable) return false;
         
         if (labeledFilter === 'labeled' && !t.revisado) return false;
         if (labeledFilter === 'unlabeled' && t.revisado) return false;
         
         const tCategory = (!t.categoria || t.categoria === '---') ? 'Sin Categoría' : t.categoria;
         if (excludedCategories.includes(tCategory)) return false;

         if (excludedTags.length > 0) {
             const tTags = t.tags ? t.tags.split(',').map(tag => tag.trim()).filter(Boolean) : [];
             if (tTags.length === 0) {
                 if (excludedTags.includes('Sin Etiqueta')) return false;
             } else {
                 if (tTags.some(tg => excludedTags.includes(tg))) return false;
             }
         }
         return true;
      });
  }, [allTimeTransactions, reimbursableFilter, labeledFilter, excludedCategories, excludedTags]);

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
    setModalTransactions(txs.sort((a,b) => new Date(b.FECHA).getTime() - new Date(a.FECHA).getTime()));
  };

  const openLocalModal = (title: string, desc: string, txs: Transaction[]) => {
      setModalTitle(title);
      setModalDescription(desc);
      setModalTransactions(txs);
      setLoadingModal(false);
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
                     className="bg-surface-800/50 border border-white/10 text-white text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2 backdrop-blur-md"
                 >
                     {periodOptions.map(opt => (
                         <option key={opt.value} value={opt.value}>{opt.label}</option>
                     ))}
                 </select>

                 <select
                     value={labeledFilter}
                     onChange={(e) => setLabeledFilter(e.target.value as any)}
                     className="bg-surface-800/50 border border-white/10 text-white text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2 backdrop-blur-md"
                 >
                     <option value="all">Todas las transacciones</option>
                     <option value="labeled">Solo Etiquetadas</option>
                     <option value="unlabeled">No Etiquetadas</option>
                 </select>

                 <select
                     value={reimbursableFilter}
                     onChange={(e) => setReimbursableFilter(e.target.value as any)}
                     className="bg-surface-800/50 border border-white/10 text-white text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2 backdrop-blur-md"
                 >
                     <option value="all">Todas (Incl. Reembolsables)</option>
                     <option value="excluded">Sin Reembolsables</option>
                     <option value="included">Solo Reembolsables</option>
                 </select>

                 <button 
                     onClick={() => setShowExclusionModal(true)}
                     className={`border text-sm rounded-lg block px-3 py-2 flex items-center gap-2 transition-colors ${
                         (excludedCategories.length + excludedTags.length) > 0 
                         ? 'bg-rose-500/20 border-rose-500/50 text-rose-400 hover:bg-rose-500/30' 
                         : 'bg-surface-800/50 border-white/10 text-white hover:bg-surface-700 backdrop-blur-md'
                     }`}
                 >
                     <Filter size={16} /> 
                     <span className="hidden md:inline">
                         Exclusiones {(excludedCategories.length + excludedTags.length) > 0 ? `(${excludedCategories.length + excludedTags.length})` : ''}
                     </span>
                 </button>
                 
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
                              Filtros de Exclusión
                          </h2>
                          <p className="text-surface-400 text-sm mt-1">Oculta categorías o etiquetas específicas de todo el análisis.</p>
                      </div>
                      <button onClick={() => setShowExclusionModal(false)} className="p-2 text-surface-400 hover:text-white transition-colors bg-surface-950 rounded-xl hover:bg-surface-700">
                          <X size={24} />
                      </button>
                  </div>
                  
                  <div className="p-6 overflow-y-auto custom-scrollbar flex-1 space-y-8">
                      {/* Categorías */}
                      <div>
                          <div className="flex justify-between items-center mb-4">
                              <h3 className="text-lg font-bold text-white">Categorías Excluidas</h3>
                              <button 
                                  onClick={() => setExcludedCategories([])}
                                  className="text-xs text-rose-400 hover:text-rose-300"
                              >
                                  Limpiar todas
                              </button>
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                              {[...CATEGORIES.filter(c => c !== '---'), 'Sin Categoría'].map(cat => (
                                  <label key={cat} className="flex items-center gap-2 p-2 bg-surface-950 rounded-lg border border-white/5 cursor-pointer hover:bg-surface-800 transition-colors">
                                      <input 
                                          type="checkbox" 
                                          checked={excludedCategories.includes(cat)}
                                          onChange={(e) => {
                                              if (e.target.checked) setExcludedCategories([...excludedCategories, cat]);
                                              else setExcludedCategories(excludedCategories.filter(c => c !== cat));
                                          }}
                                          className="rounded border-surface-600 bg-surface-800 text-rose-500 focus:ring-rose-500/50 focus:ring-offset-surface-950"
                                      />
                                      <span className={`text-sm ${excludedCategories.includes(cat) ? 'text-rose-400 font-medium line-through' : 'text-surface-300'}`}>{cat}</span>
                                  </label>
                              ))}
                          </div>
                      </div>

                      {/* Etiquetas */}
                      <div>
                          <div className="flex justify-between items-center mb-4">
                              <h3 className="text-lg font-bold text-white">Etiquetas Excluidas</h3>
                              <button 
                                  onClick={() => setExcludedTags([])}
                                  className="text-xs text-rose-400 hover:text-rose-300"
                              >
                                  Limpiar todas
                              </button>
                          </div>
                          <div className="flex flex-wrap gap-2">
                              {[...availableTags, 'Sin Etiqueta'].map(tag => (
                                  <label key={tag} className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border cursor-pointer transition-colors ${excludedTags.includes(tag) ? 'bg-rose-500/10 border-rose-500/30' : 'bg-surface-950 border-white/5 hover:bg-surface-800'}`}>
                                      <input 
                                          type="checkbox" 
                                          checked={excludedTags.includes(tag)}
                                          onChange={(e) => {
                                              if (e.target.checked) setExcludedTags([...excludedTags, tag]);
                                              else setExcludedTags(excludedTags.filter(t => t !== tag));
                                          }}
                                          className="rounded border-surface-600 bg-surface-800 text-rose-500 focus:ring-rose-500/50 focus:ring-offset-surface-950"
                                      />
                                      <span className={`text-sm ${excludedTags.includes(tag) ? 'text-rose-400 font-medium line-through' : 'text-surface-300'}`}>{tag}</span>
                                  </label>
                              ))}
                          </div>
                          {availableTags.length === 0 && (
                              <p className="text-surface-500 text-sm italic">No hay etiquetas disponibles aún.</p>
                          )}
                      </div>
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
              <div className="bg-surface-900 border border-white/10 rounded-2xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
                  <div className="p-6 border-b border-white/10 flex justify-between items-center bg-surface-800/50">
                      <div>
                          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                              {modalTitle}
                          </h2>
                          <p className="text-surface-400 text-sm mt-1">{modalDescription}</p>
                      </div>
                      <button onClick={() => setModalTitle(null)} className="p-2 text-surface-400 hover:text-white transition-colors bg-surface-950 rounded-xl hover:bg-surface-700">
                          <X size={24} />
                      </button>
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
                              
                              <div className="space-y-3">
                                  {modalTransactions.length === 0 ? (
                                      <div className="text-center py-10 text-surface-500">No hay transacciones para este tag.</div>
                                  ) : (
                                      modalTransactions.map((tx) => (
                                          <div key={tx.id} className="flex justify-between items-center p-4 bg-surface-950/50 hover:bg-surface-800 rounded-xl border border-white/5 transition-colors group">
                                              <div className="flex flex-col">
                                                  <span className="font-bold text-white group-hover:text-primary-300 transition-colors uppercase text-sm">{tx.nombre_limpio || tx.DESCRIPCION}</span>
                                                  <span className="text-xs text-surface-500">{new Date(tx.FECHA).toLocaleDateString('es-CO')} &bull; {tx.categoria}</span>
                                              </div>
                                              <span className={`font-mono font-bold ${tx.MONTO > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                  {tx.MONTO > 0 ? '+' : ''}{formatCurrency(tx.MONTO)}
                                              </span>
                                          </div>
                                      ))
                                  )}
                              </div>
                          </>
                      )}
                  </div>
              </div>
          </div>
      )}
    </div>
  );
}
