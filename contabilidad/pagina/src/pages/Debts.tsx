import { useState } from 'react';
import { Search, Filter, ArrowUpRight, Wallet, Calendar, BarChart3, Database, DollarSign, User, ArrowRight, CheckCircle2, Clock } from 'lucide-react';
import { useRefundableTransactions, useSupabaseDebts } from '../hooks/useTransactions';
import { DebtsChart } from '../components/DebtsChart';

export function Debts() {
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState<{ startDate?: string; endDate?: string; debtor?: string }>({});
  const [showChart, setShowChart] = useState(false);
  
  // Left Side Data (Local Refundables)
  const { data: transactions, isLoading: isLoadingLeft } = useRefundableTransactions(filters);
  const uniqueDebtors = Array.from(new Set(transactions?.map(t => t.deudor).filter(Boolean) as string[])).sort();
  
  // Right Side Data (Supabase Debts)
  const { data: supabaseDebts, isLoading: isLoadingRight } = useSupabaseDebts({
      startDate: filters.startDate,
      endDate: filters.endDate,
      debtor: filters.debtor
  });

  // Derived Values
  const leftTotal = transactions?.reduce((acc, tx) => acc + tx.MONTO, 0) || 0;
  const rightTotal = supabaseDebts?.filter(d => !d.PAGADA).reduce((acc, d) => acc + d.MONTO, 0) || 0;

  const handleDateChange = (type: 'start' | 'end', value: string) => {
    setFilters(prev => ({ ...prev, [type === 'start' ? 'startDate' : 'endDate']: value || undefined }));
  };

  const filteredLeft = transactions?.filter(tx => 
    tx.DESCRIPCION.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (tx.nombre_limpio && tx.nombre_limpio.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (tx.deudor && tx.deudor.toLowerCase().includes(searchTerm.toLowerCase()))
  ) || [];

  const filteredRight = supabaseDebts?.filter(debt => 
    debt.DESCRIPCION.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (debt.DEUDOR_NOMBRE && debt.DEUDOR_NOMBRE.toLowerCase().includes(searchTerm.toLowerCase()))
  ) || [];

  return (
    <div className="flex flex-col h-full bg-surface-950 relative overflow-hidden">
       {/* Background Gradients */}
       <div className="fixed top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0">
         <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-primary-600/10 rounded-full blur-[120px]" />
         <div className="absolute bottom-[-10%] left-[-5%] w-[400px] h-[400px] bg-secondary-600/10 rounded-full blur-[100px]" />
      </div>

      {/* Main Container */}
      <div className="flex flex-col h-full relative z-10">
        
        {/* HEADER & CONTROLS - "The Command Center" */}
        <div className="shrink-0 p-6 md:p-8 flex flex-col gap-6">
            
            {/* Top Row: Title & Analytics Action */}
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
                            <p className="text-surface-400 text-sm font-medium">Sistema de control financiero</p>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <button
                        onClick={() => setShowChart(true)}
                        className="group relative px-5 py-2.5 bg-surface-900 hover:bg-surface-800 text-surface-200 hover:text-white rounded-xl border border-white/10 transition-all shadow-lg hover:shadow-indigo-500/20 hover:border-indigo-500/30 active:scale-95 flex items-center gap-2 overflow-hidden"
                    >
                        <BarChart3 size={18} />
                        <span className="font-semibold text-sm">Analizar Datos</span>
                    </button>
                </div>
            </div>

            {/* Filter Bar - Large, Tactile, Accessible */}
            <div className="w-full bg-surface-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-2 flex flex-col lg:flex-row gap-2 shadow-2xl">
                
                {/* Search - Primary Input */}
                <div className="flex-[2] relative group">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-500 group-focus-within:text-indigo-400 transition-colors pointer-events-none" size={20} />
                    <input 
                        type="text" 
                        placeholder="Buscar por concepto..." 
                        className="w-full h-12 bg-surface-950/30 border border-transparent hover:border-white/5 focus:border-indigo-500/30 rounded-xl pl-12 pr-4 text-surface-100 placeholder:text-surface-500 focus:ring-0 text-base transition-all"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>

                {/* Debtor Filter */}
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

                 {/* Date Range - Unified Pill */}
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
        </div>

        {/* CONTENT COLUMNS */}
        <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-2 gap-0 lg:divide-x lg:divide-white/5">
            
            {/* LEFT COLUMN: Local Refundables */}
            <div className="flex flex-col overflow-hidden bg-gradient-to-b from-surface-900/10 to-transparent">
                <div className="px-8 py-5 border-b border-white/5 bg-surface-950/30 backdrop-blur-sm flex items-center justify-between shrink-0 sticky top-0 z-20">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
                             <ArrowRight size={18} />
                        </div>
                        <div>
                             <h2 className="text-base font-bold text-white leading-tight">Pendientes Locales</h2>
                             <p className="text-[11px] text-surface-400 uppercase tracking-wide font-medium">Reembolsos inmediatos</p>
                        </div>
                    </div>
                    <div className="text-right">
                         <p className="text-[10px] text-surface-500 uppercase tracking-wider font-bold mb-0.5">Total Pendiente</p>
                         <div className="text-xl font-mono font-bold text-indigo-400">${leftTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-3 custom-scrollbar">
                    {isLoadingLeft ? (
                         <div className="flex flex-col items-center justify-center h-64 gap-3 text-surface-500">
                              <div className="w-6 h-6 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin"></div>
                              <span className="text-sm">Cargando datos...</span>
                         </div>
                    ) : filteredLeft.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-64 text-surface-500 border-2 border-dashed border-white/5 rounded-2xl bg-surface-900/20">
                             <Wallet size={32} className="mb-3 opacity-50" />
                             <p className="text-sm font-medium">No se encontraron registros</p>
                        </div>
                    ) : (
                        filteredLeft.map((tx, idx) => (
                            <div key={tx.id} className="group relative p-4 rounded-2xl bg-surface-900/40 border border-white/5 hover:bg-surface-800/60 hover:border-indigo-500/20 transition-all cursor-default overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-500" style={{ animationDelay: `${idx * 0.05}s` }}>
                                <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 rounded-full blur-2xl -translate-y-1/2 translate-x-1/2 group-hover:bg-indigo-500/10 transition-colors"></div>
                                
                                <div className="relative z-10 flex justify-between items-start gap-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1.5">
                                            <h3 className="font-bold text-surface-100 truncate text-sm">{tx.nombre_limpio || tx.DESCRIPCION}</h3>
                                            {tx.deudor && (
                                                <span className="px-2 py-0.5 rounded-md bg-indigo-500/10 border border-indigo-500/20 text-[10px] font-bold text-indigo-300 uppercase tracking-wide shrink-0">
                                                    {tx.deudor}
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-4 text-xs text-surface-400">
                                            <span className="flex items-center gap-1.5">
                                                <Calendar size={12} />
                                                {new Date(tx.FECHA).toLocaleDateString()}
                                            </span>
                                            {/* Future: Add more details here like category icons if available */}
                                        </div>
                                    </div>
                                    <div className="text-right shrink-0">
                                         <div className="text-base font-mono font-bold text-white group-hover:text-indigo-300 transition-colors">
                                            ${tx.MONTO.toFixed(2)}
                                         </div>
                                         <span className="text-[10px] font-bold text-surface-500 bg-surface-950/50 px-1.5 py-0.5 rounded">
                                            PENDIENTE
                                         </span>
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* RIGHT COLUMN: Supabase Debts */}
            <div className="flex flex-col overflow-hidden bg-gradient-to-b from-[#050912] to-surface-950">
                 <div className="px-8 py-5 border-b border-white/5 bg-surface-950/30 backdrop-blur-sm flex items-center justify-between shrink-0 sticky top-0 z-20">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
                             <Database size={18} />
                        </div>
                        <div>
                             <h2 className="text-base font-bold text-white leading-tight">Histórico Supabase</h2>
                             <p className="text-[11px] text-surface-400 uppercase tracking-wide font-medium">Registro persistente</p>
                        </div>
                    </div>
                    <div className="text-right">
                         <p className="text-[10px] text-surface-500 uppercase tracking-wider font-bold mb-0.5">Total Por Cobrar</p>
                         <div className="text-xl font-mono font-bold text-emerald-400">${rightTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-3 custom-scrollbar">
                    {isLoadingRight ? (
                         <div className="flex flex-col items-center justify-center h-64 gap-3 text-surface-500">
                              <div className="w-6 h-6 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin"></div>
                              <span className="text-sm">Cargando histórico...</span>
                         </div>
                    ) : filteredRight.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-64 text-surface-500 border-2 border-dashed border-white/5 rounded-2xl bg-surface-900/20">
                             <Database size={32} className="mb-3 opacity-50" />
                             <p className="text-sm font-medium">No hay deudas registradas</p>
                        </div>
                    ) : (
                        filteredRight.map((debt, idx) => (
                            <div key={debt.ID} className={`group relative p-4 rounded-2xl border transition-all cursor-default overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-500 ${debt.PAGADA ? 'bg-surface-900/20 border-white/5 opacity-60 hover:opacity-100' : 'bg-surface-900/40 border-emerald-500/10 hover:border-emerald-500/30 hover:bg-surface-800/60'}`} style={{ animationDelay: `${idx * 0.05}s` }}>
                                {!debt.PAGADA && (
                                     <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-2xl -translate-y-1/2 translate-x-1/2 group-hover:bg-emerald-500/10 transition-colors"></div>
                                )}

                                <div className="relative z-10 flex justify-between items-start gap-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1.5">
                                            <h3 className={`font-bold truncate text-sm ${debt.PAGADA ? 'text-surface-400 line-through' : 'text-surface-100'}`}>{debt.DESCRIPCION}</h3>
                                            <span className="px-2 py-0.5 rounded-md bg-sky-500/10 border border-sky-500/20 text-[10px] font-bold text-sky-300 uppercase tracking-wide shrink-0">
                                                {debt.DEUDOR_NOMBRE}
                                            </span>
                                        </div>
                                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-surface-400">
                                            <span className="flex items-center gap-1.5">
                                                <Calendar size={12} />
                                                {new Date(debt.FECHA).toLocaleDateString()}
                                            </span>
                                            {debt.PAGADA && debt.FECHA_PAGO && (
                                                <span className="flex items-center gap-1.5 text-emerald-400/80">
                                                    <Clock size={12} />
                                                    Pagado: {new Date(debt.FECHA_PAGO).toLocaleDateString()}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="text-right shrink-0">
                                         <div className={`text-base font-mono font-bold group-hover:scale-105 transition-transform origin-right ${debt.PAGADA ? 'text-surface-500' : 'text-white'}`}>
                                            ${debt.MONTO.toFixed(2)}
                                         </div>
                                         <div className={`text-[10px] font-bold px-1.5 py-0.5 rounded inline-flex items-center gap-1 mt-1 ${debt.PAGADA ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'}`}>
                                            {debt.PAGADA ? (
                                                <>
                                                 <CheckCircle2 size={10} />
                                                 PAGADA
                                                </>
                                            ) : 'PENDIENTE'}
                                         </div>
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
      </div>

      {showChart && <DebtsChart onClose={() => setShowChart(false)} />}
    </div>
  );
}
