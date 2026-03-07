
import { useState, useEffect, useMemo, useRef } from 'react';
import { api, Transaction, InterpolationGroup } from '../services/api';
import { Search, Tag, Filter, ArrowUpRight, ArrowDownRight, Calendar, Info, ChevronDown, Check, List as ListIcon, TrendingUp, Settings2, Calculator } from 'lucide-react';
import ExplorerChart from '../components/ExplorerChart';
import PaymentCRUD from '../components/PaymentCRUD';
import AutoPaymentsModal from '../components/AutoPaymentsModal';

// --- Searchable Select Component ---
interface SearchableSelectProps {
  options: string[];
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  icon?: React.ReactNode;
  disabled?: boolean;
}

function SearchableSelect({ options, value, onChange, placeholder, icon, disabled }: SearchableSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Filter options based on search term
  const filteredOptions = useMemo(() => {
    if (!searchTerm) return options;
    return options.filter(opt => opt.toLowerCase().includes(searchTerm.toLowerCase()));
  }, [options, searchTerm]);

  // Handle clicking outside to close
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Sync search term and focus
  useEffect(() => {
    if (isOpen) {
        // Force focus after a short delay to allow render/animation
        setTimeout(() => {
            inputRef.current?.focus();
        }, 50);
    } else {
        setSearchTerm(''); // Reset search when closed
    }
  }, [isOpen]);

  return (
    <div className="relative w-full" ref={containerRef}>
      {/* Trigger Button */}
      <div 
        onClick={() => { if(!disabled) setIsOpen(!isOpen); }}
        className={`
            w-full bg-surface-950 border border-white/10 rounded-xl px-4 py-3 flex items-center justify-between
            cursor-pointer hover:border-white/20 transition-all duration-200 group
            ${isOpen ? 'ring-2 ring-primary-500/50 border-primary-500/50' : ''}
            ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      >
        <div className="flex items-center gap-3 overflow-hidden">
            {icon && <span className="text-surface-400 group-hover:text-primary-400 transition-colors">{icon}</span>}
            <span className={`truncate ${!value ? 'text-surface-500' : 'text-white'}`}>
                {value || placeholder}
            </span>
        </div>
        <ChevronDown size={18} className={`text-surface-400 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`} />
      </div>

      {/* Dropdown Menu */}
      {isOpen && (
        <div 
            className="absolute top-full left-0 w-full mt-2 bg-surface-800 border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-200 ring-1 ring-white/5"
            onClick={(e) => e.stopPropagation()} 
        >
            {/* Search Input */}
            <div className="p-2 border-b border-white/5 bg-surface-800">
                <div className="relative">
                    <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
                    <input 
                        ref={inputRef}
                        type="text" 
                        placeholder="Buscar..."
                        className="w-full bg-surface-900 border border-white/5 rounded-lg py-2 pl-9 pr-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-primary-500/50 placeholder:text-surface-500"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && filteredOptions.length > 0) {
                                onChange(filteredOptions[0]);
                                setIsOpen(false);
                            }
                        }}
                    />
                </div>
            </div>
            
            {/* Options List */}
            <div className="max-h-60 overflow-y-auto custom-scrollbar p-1 bg-surface-800">
                {filteredOptions.length > 0 ? (
                    filteredOptions.map((opt) => (
                        <div 
                            key={opt} 
                            onClick={() => { onChange(opt); setIsOpen(false); }}
                            className={`
                                flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-colors text-sm
                                ${value === opt ? 'bg-primary-500/20 text-primary-300' : 'text-surface-300 hover:bg-surface-700 hover:text-white'}
                            `}
                        >
                            <span className="truncate">{opt}</span>
                            {value === opt && <Check size={16} className="text-primary-400" />}
                        </div>
                    ))
                ) : (
                    <div className="px-3 py-8 text-center text-sm text-surface-500 italic flex flex-col items-center gap-2">
                        <Search size={20} className="text-surface-600" />
                        No se encontraron resultados
                    </div>
                )}
            </div>
        </div>
      )}
    </div>
  );
}


export function DataExplorer() {
  const [mode, setMode] = useState<'category' | 'tag'>('category'); // Filter mode
  const [viewMode, setViewMode] = useState<'list' | 'analysis'>('list'); // UI Mode
  
  const [options, setOptions] = useState<string[]>([]);
  const [selectedFilter, setSelectedFilter] = useState('');
  const [results, setResults] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingOptions, setLoadingOptions] = useState(false);

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
    if (viewMode === 'analysis' && selectedFilter) {
        const loadAnalysis = async () => {
            setAnalysisLoading(true);
            try {
                const data = await api.getAnalysisChartData(
                    mode === 'category' ? selectedFilter : undefined,
                    mode === 'tag' ? selectedFilter : undefined,
                    undefined, undefined,
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
  }, [viewMode, selectedFilter, mode, selectedGroupId]);

  // Load options based on mode
  useEffect(() => {
    const loadOptions = async () => {
      setLoadingOptions(true);
      try {
        if (mode === 'category') {
          const cats = await api.getCategories();
          setOptions(cats);
        } else {
          const tags = await api.getTags();
          setOptions(tags);
        }
      } catch (error) {
        console.error("Error loading options", error);
      } finally {
        setLoadingOptions(false);
      }
    };
    
    loadOptions();
    setSelectedFilter(''); // Reset selection when mode changes
    setResults([]);
  }, [mode]);

  // Load data when filter is selected
  useEffect(() => {
    if (!selectedFilter) {
      setResults([]);
      return;
    }

    const loadData = async () => {
      setLoading(true);
      try {
        const data = await api.getTransactions(
          undefined, // date
          undefined, // pending
          undefined, // reembolsable
          undefined, // start
          undefined, // end
          undefined, // debtor
          undefined, // search
          mode === 'category' ? selectedFilter : undefined,
          mode === 'tag' ? selectedFilter : undefined
        );
        // Sort by date desc
        setResults(data.sort((a, b) => new Date(b.FECHA).getTime() - new Date(a.FECHA).getTime()));
      } catch (error) {
        console.error("Error loading data", error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [selectedFilter, mode]);

  // Calculations
  const totalAmount = useMemo(() => results.reduce((acc, curr) => acc + curr.MONTO, 0), [results]);
  const income = useMemo(() => results.filter(t => t.MONTO > 0).reduce((acc, curr) => acc + curr.MONTO, 0), [results]);
  const expenses = useMemo(() => results.filter(t => t.MONTO < 0).reduce((acc, curr) => acc + curr.MONTO, 0), [results]);
  
  return (
    <div className="flex-1 overflow-y-auto px-4 md:px-8 pb-8 custom-scrollbar">
      <div className="max-w-7xl mx-auto space-y-8 mt-8">
        
        {/* Header & Mode Switcher */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
          <div className="space-y-2">
            <h1 className="text-4xl font-bold text-white tracking-tight flex items-center gap-3">
              <Search className="text-primary-400" size={36} />
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-white to-surface-400">
                Explorador de Datos
              </span>
            </h1>
            <p className="text-surface-400 text-lg max-w-2xl">
                Analiza tus finanzas filtrando detalladamente por {mode === 'category' ? 'categorías' : 'etiquetas'}.
            </p>
          </div>

          <div className="flex gap-4 items-center">
            {/* View Switcher */}
            <div className="bg-surface-900/50 p-1.5 rounded-2xl border border-white/10 shadow-lg flex shrink-0">
                <button
                onClick={() => setViewMode('list')}
                className={`
                    flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-300 relative overflow-hidden
                    ${viewMode === 'list' ? 'text-white bg-white/10' : 'text-surface-400 hover:text-white hover:bg-white/5'}
                `}
                >
                <ListIcon size={18} /> Lista
                </button>
                <button
                onClick={() => setViewMode('analysis')}
                className={`
                    flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-300 relative overflow-hidden
                    ${viewMode === 'analysis' ? 'text-white bg-white/10' : 'text-surface-400 hover:text-white hover:bg-white/5'}
                `}
                >
                <TrendingUp size={18} /> Análisis
                </button>
            </div>

            {/* Filter Mode Switcher */}
            <div className="bg-surface-900/50 p-1.5 rounded-2xl border border-white/10 shadow-lg flex shrink-0">
                <button
                onClick={() => setMode('category')}
                className={`
                    flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold transition-all duration-300 relative overflow-hidden
                    ${mode === 'category' ? 'text-white' : 'text-surface-400 hover:text-white hover:bg-white/5'}
                `}
                >
                {mode === 'category' && (
                    <div className="absolute inset-0 bg-gradient-to-r from-primary-600 to-indigo-600 rounded-xl shadow-lg shadow-primary-500/20"></div>
                )}
                <span className="relative z-10 flex items-center gap-2">
                    <Filter size={18} /> Categoría
                </span>
                </button>
                <button
                onClick={() => setMode('tag')}
                className={`
                    flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold transition-all duration-300 relative overflow-hidden
                    ${mode === 'tag' ? 'text-white' : 'text-surface-400 hover:text-white hover:bg-white/5'}
                `}
                >
                {mode === 'tag' && (
                    <div className="absolute inset-0 bg-gradient-to-r from-secondary-600 to-pink-600 rounded-xl shadow-lg shadow-secondary-500/20"></div>
                )}
                <span className="relative z-10 flex items-center gap-2">
                    <Tag size={18} /> Tag
                </span>
                </button>
            </div>
          </div>
        </div>

        {/* Search Bar + Analysis Controls */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-gradient-to-b from-surface-900/60 to-surface-950/60 backdrop-blur-xl border border-white/10 rounded-3xl p-8 shadow-2xl relative">
                {/* Decorational globs */}
                <div className="absolute inset-0 overflow-hidden rounded-3xl pointer-events-none">
                    <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary-500/10 rounded-full blur-3xl"></div>
                </div>

                <div className="relative z-20">
                    <label className="block text-sm font-bold text-surface-300 mb-2 uppercase tracking-wider">
                        {mode === 'category' ? '1. Selecciona Categoría' : '1. Selecciona Tag'}
                    </label>
                    <SearchableSelect 
                        options={options}
                        value={selectedFilter}
                        onChange={setSelectedFilter}
                        placeholder={loadingOptions ? "Cargando..." : (mode === 'category' ? "Ej: Comida..." : "Ej: vacacion...")}
                        icon={mode === 'category' ? <Filter size={18} /> : <Tag size={18} />}
                        disabled={loadingOptions}
                    />
                </div>
            </div>

            {viewMode === 'analysis' && (
                <div className="bg-gradient-to-b from-surface-900/60 to-surface-950/60 backdrop-blur-xl border border-white/10 rounded-3xl p-8 shadow-2xl relative">
                     <div className="absolute inset-0 overflow-hidden rounded-3xl pointer-events-none">
                        <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-emerald-500/10 rounded-full blur-3xl"></div>
                    </div>
                     <div className="relative z-20 grid grid-cols-2 gap-4">
                        <div>
                             <label className="block text-sm font-bold text-surface-300 mb-2 uppercase tracking-wider">
                                2. Tipo Referencia
                            </label>
                            <div className="flex bg-surface-950 rounded-lg p-1 border border-white/10">
                                <button
                                    onClick={() => { setComparisonType('interpolated'); setSelectedGroupId(''); }}
                                    className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${comparisonType === 'interpolated' ? 'bg-surface-800 text-white' : 'text-surface-400 hover:text-white'}`}
                                >
                                    Interpolado
                                </button>
                                <button
                                    onClick={() => { setComparisonType('fixed'); setSelectedGroupId(''); }}
                                    className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${comparisonType === 'fixed' ? 'bg-surface-800 text-white' : 'text-surface-400 hover:text-white'}`}
                                >
                                    Fijo
                                </button>
                            </div>
                        </div>
                        <div>
                             <label className="block text-sm font-bold text-surface-300 mb-2 uppercase tracking-wider">
                                3. Comparar con
                            </label>
                            <div className="relative">
                                <select 
                                    className="w-full bg-surface-950 border border-white/10 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:ring-1 focus:ring-primary-500/50 appearance-none"
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
                </div>
            )}
        </div>

        {/* ANALYSIS VIEW */}
        {viewMode === 'analysis' && selectedFilter && (
            <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                {/* Chart Section */}
                <div className="bg-surface-900/40 backdrop-blur-xl border border-white/10 rounded-3xl p-6 shadow-2xl">
                    <div className="mb-6 flex justify-between items-center">
                        <h2 className="text-xl font-bold text-white flex items-center gap-2">
                            <TrendingUp className="text-emerald-400" />
                            Tendencia: {selectedFilter} vs {groups.find(g => g.id === selectedGroupId)?.name || 'Nada'}
                        </h2>
                    </div>
                    <div className="h-[400px]">
                        {chartData ? (
                            <ExplorerChart data={chartData} loading={analysisLoading} />
                        ) : (
                            <div className="h-full flex items-center justify-center text-surface-500">
                                {analysisLoading ? 'Cargando gráfico...' : 'Selecciona un filtro para ver el análisis'}
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
                                // Reload groups if CRUD changes something
                                api.getGroups(comparisonType).then(setGroups);
                                // Trigger chart reload if selected group was modified?
                                // Effect dependencies handle this if we toggle group_id, but generic update might need force
                                if (selectedGroupId) {
                                    // Hack to force reload:
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

        {/* LIST VIEW */}
        {viewMode === 'list' && (
            <>
            {/* Results Area */}
            {loading ? (
                <div className="flex flex-col items-center justify-center py-20 gap-4">
                    <div className="relative">
                        <div className="w-16 h-16 border-4 border-surface-800 border-t-primary-500 rounded-full animate-spin"></div>
                        <div className="absolute inset-0 flex items-center justify-center">
                            <Search size={20} className="text-primary-500 animate-pulse" />
                        </div>
                    </div>
                    <p className="text-surface-400 font-medium animate-pulse">Buscando transacciones...</p>
                </div>
            ) : selectedFilter && (
                <div className="space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700">
                    
                    {/* Stats Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <StatCard 
                            label="Registros" 
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

                    {/* Auto Payments Control Bar */}
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
                                {isSelectionMode ? 'Cancelar Selección' : '⚡ Modo Pagos Automáticos'}
                            </button>
                            {isSelectionMode && (
                                <p className="text-sm text-surface-400">
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

                    {/* Table */}
                    <div className="bg-surface-900/40 backdrop-blur-xl border border-white/10 rounded-3xl overflow-hidden shadow-2xl">
                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="bg-surface-950/50 text-surface-400 text-xs font-bold uppercase tracking-widest border-b border-white/5">
                                        {isSelectionMode && <th className="px-6 py-5 w-16 text-center">Sel.</th>}
                                        <th className="px-8 py-5">Fecha</th>
                                        <th className="px-8 py-5">Descripción</th>
                                        <th className="px-8 py-5">Nombre Limpio</th>
                                        <th className="px-8 py-5 text-right">Monto</th>
                                        <th className="px-8 py-5">Tags</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {results.map((t) => (
                                        <tr key={t.id} className={`hover:bg-white/[0.02] transition-colors group ${targetTransaction?.id === t.id ? 'bg-emerald-500/10' : ''}`}>
                                            {isSelectionMode && (
                                                <td className="px-6 py-4 text-center align-middle" onClick={(e) => e.stopPropagation()}>
                                                    {t.MONTO > 0 ? (
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
                                                    )}
                                                </td>
                                            )}
                                            <td className="px-8 py-4 text-surface-400 text-sm whitespace-nowrap font-medium">
                                                <div className="flex items-center gap-3">
                                                    <div className="p-2 bg-surface-800 rounded-lg text-surface-400 group-hover:text-primary-400 group-hover:bg-primary-500/10 transition-colors">
                                                        <Calendar size={16} />
                                                    </div>
                                                    {new Date(t.FECHA).toLocaleDateString('es-CO', { year: 'numeric', month: 'short', day: 'numeric' })}
                                                </div>
                                            </td>
                                            <td className="px-8 py-4 text-white text-sm font-medium">
                                                {t.DESCRIPCION}
                                            </td>
                                            <td className="px-8 py-4 text-surface-300 text-sm">
                                                {t.nombre_limpio || <span className="text-surface-600 italic">No asignado</span>}
                                            </td>
                                            <td className={`px-8 py-4 text-right text-sm font-bold whitespace-nowrap ${t.MONTO >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                {t.MONTO.toLocaleString('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })}
                                            </td>
                                            <td className="px-8 py-4">
                                                <div className="flex flex-wrap gap-2">
                                                    {t.tags ? t.tags.split(',').map((tag, i) => (
                                                        <span key={i} className="px-2.5 py-1 bg-surface-800 border border-white/5 rounded-md text-xs font-semibold text-surface-300">
                                                            {tag.trim()}
                                                        </span>
                                                    )) : <span className="text-surface-700 text-xs">-</span>}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                    {results.length === 0 && (
                                        <tr>
                                            <td colSpan={5} className="px-6 py-24 text-center">
                                                <div className="flex flex-col items-center justify-center gap-4">
                                                    <div className="p-4 bg-surface-800/50 rounded-full text-surface-500">
                                                        <Search size={32} />
                                                    </div>
                                                    <div>
                                                        <p className="text-white font-medium text-lg">No se encontraron transacciones</p>
                                                        <p className="text-surface-500">Intenta seleccionar otra categoría o etiqueta.</p>
                                                    </div>
                                                </div>
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}
            </>
        )}
      </div>

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
                  // Optionally show a success toast here
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
              <span className="text-sm text-surface-400 font-semibold uppercase tracking-wider">{label}</span>
              <div className={`p-2.5 rounded-xl border ${colorClass}`}>
                  {icon}
              </div>
           </div>
           <p className="text-3xl font-bold text-white tracking-tight">{value}</p>
        </div>
    );
}
