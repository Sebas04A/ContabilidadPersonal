import { useState, useEffect } from 'react';
import { TransactionTable } from '../../components/TransactionTable';
import { EditModal } from '../../components/EditModal';
import { CalendarPopover } from '../../components/CalendarPopover';
import { SearchModal } from '../../components/SearchModal';
import { Transaction, TransactionUpdate } from '../../services/api';
import { 
  useDates, 
  useTransactions, 
  useStats, 
  useTags,
  useUpdateTransaction, 
  useMarkAsReviewed,
  useSyncData,
  useGroupTransactions,     // Added
  useUngroupTransaction,    // Added
  useSupabaseDebts          // Added
} from '../../hooks/useTransactions';
import { 
  AlertCircle, 
  RefreshCw, 
  ChevronLeft, 
  ChevronRight,
  Wallet,
  ArrowUpRight,
  Clock,
  Search,
  Link2,
  X,
  CreditCard
} from 'lucide-react';

export function DailyLabeling() {
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Queries
  const { data: dates, isLoading: datesLoading, isError: datesError } = useDates();
  // Use raw transactions for stats, but grouped for display
  const { data: rawTransactions, isLoading: txLoading } = useTransactions(selectedDate || undefined);
  const { data: stats } = useStats(selectedDate || undefined);
  const { data: existingTags } = useTags();

  // Fetch debts for the currently selected day
  const { data: dailyDebts, isLoading: debtsLoading } = useSupabaseDebts(
    selectedDate ? { startDate: selectedDate, endDate: selectedDate } : undefined
  );

  // Helper to group splits for display
  const groupSplitsForDisplay = (txs: Transaction[] | undefined): Transaction[] => {
      if (!txs) return [];
      
      const groupedMap = new Map<string, Transaction[]>();
      
      txs.forEach(t => {
          if (!groupedMap.has(t.id)) {
              groupedMap.set(t.id, []);
          }
          groupedMap.get(t.id)!.push(t);
      });

      const result: Transaction[] = [];
      
      groupedMap.forEach((parts) => {
          if (parts.length === 1) {
              result.push(parts[0]);
          } else {
              // Create a "Master" transaction for the split
              // Sum amounts
              const totalAmount = parts.reduce((sum, p) => sum + p.MONTO, 0);
              // Use first part as base, but mark as split parent
              const base = parts[0];
              
              const masterTx: Transaction = {
                  ...base,
                  MONTO: totalAmount,
                  DESCRIPCION: base.DESCRIPCION, // Keep original desc
                  // Special flag for display, we can use 'isSplitParent' if we add it to type or checking parts len
                  // We'll attach the parts implicitly or via a new property if we extend the type. 
                  // For now, let's just assume the table checks if we are passing a "fake" combined one.
                  // We might need to extend the type in api.ts to support 'subTransactions'
                  subTransactions: parts
              };
              result.push(masterTx);
          }
      });
      
      return result;
  };

  const displayTransactions = groupSplitsForDisplay(rawTransactions);


  // Mutations
  const updateMutation = useUpdateTransaction();
  const markReviewedMutation = useMarkAsReviewed();
  const syncMutation = useSyncData();
  const groupMutation = useGroupTransactions();
  const ungroupMutation = useUngroupTransaction();

  // Clear selection when date changes
  useEffect(() => {
    setSelectedIds(new Set());
  }, [selectedDate]);

  // Set initial date when dates load
  useEffect(() => {
    if (!selectedDate && dates?.length) {
      setSelectedDate(dates[0]);
    }
  }, [dates, selectedDate]);

  const handleEdit = (transaction: Transaction) => {
    setEditingTransaction(transaction);
  };

  const handleSave = (id: string, updates: TransactionUpdate) => {
    updateMutation.mutate({ id, updates });
  };

  const handleQuickReview = (id: string) => {
    markReviewedMutation.mutate(id);
  };

  const handleToggleSelect = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };
  
  const handleClearSelection = () => {
    setSelectedIds(new Set());
  };

  const handleGroupSelected = () => {
    const ids = Array.from(selectedIds);
    if (ids.length < 2) return;
    
    groupMutation.mutate({ ids }, {
      onSuccess: () => {
        setSyncMessage(`✅ ${ids.length} transacciones agrupadas.`);
        setTimeout(() => setSyncMessage(null), 3000);
        handleClearSelection();
      },
      onError: () => {
        setSyncMessage(`❌ Error al agrupar.`);
        setTimeout(() => setSyncMessage(null), 3000);
      }
    });
  };

  const handleUngroupSelected = () => {
     // Naive implementation: ungroup one by one
     const ids = Array.from(selectedIds);
     ids.forEach(id => ungroupMutation.mutate(id));
     setSyncMessage(`✅ Transacciones desagrupadas.`);
     setTimeout(() => setSyncMessage(null), 3000);
     handleClearSelection();
  };


  const handleSync = () => {
    if (!selectedDate) return;
    
    syncMutation.mutate(
      { fecha_inicio: selectedDate, overwrite: false },
      {
        onSuccess: (data) => {
          if (data.message) {
            setSyncMessage(data.message);
          } else if (data.records_added > 0) {
            setSyncMessage(`✅ +${data.records_added} registros nuevos.`);
          } else {
            setSyncMessage('Todo sincronizado.');
          }
          setTimeout(() => setSyncMessage(null), 5000);
        },
        onError: (error) => {
          setSyncMessage(`❌ Error: ${error.message}`);
          setTimeout(() => setSyncMessage(null), 5000);
        },
      }
    );
  };

  // Navigation Logic
  const handlePrevDay = () => {
    if (!selectedDate || !dates) return;
    const sortedDates = [...dates].sort();
    const currentIdx = sortedDates.indexOf(selectedDate);
    if (currentIdx > 0) setSelectedDate(sortedDates[currentIdx - 1]);
  };

  const handleNextDay = () => {
    if (!selectedDate || !dates) return;
    const sortedDates = [...dates].sort();
    const currentIdx = sortedDates.indexOf(selectedDate);
    if (currentIdx < sortedDates.length - 1) setSelectedDate(sortedDates[currentIdx + 1]);
  };

  // Error state
  if (datesError) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="bg-red-500/10 p-6 rounded-2xl border border-red-500/20 text-center max-w-md">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-red-400 mb-2">Error de conexión</h3>
            <p className="text-gray-400 mb-4">No se pudieron cargar los datos.</p>
            <button onClick={() => window.location.reload()} className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded-lg transition-colors">
                Reintentar
            </button>
        </div>
      </div>
    );
  }

  // Loading state
  if (datesLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
         <div className="flex flex-col items-center gap-4">
            <div className="w-10 h-10 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
            <p className="text-blue-400 font-medium tracking-widest text-sm uppercase">Cargando...</p>
         </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden relative">
      {/* Floating Gradient Header */}
      <header className="h-24 flex items-center justify-between px-8 z-20 relative shrink-0">
        
        {/* Left: Date Navigation */}
        <div className="glass px-2 py-1.5 rounded-2xl flex items-center gap-2 shadow-lg shadow-black/20 ring-1 ring-white/5">
           <button 
             onClick={handlePrevDay}
             className="p-2.5 rounded-xl hover:bg-white/10 text-gray-400 hover:text-white transition-all active:scale-90 group"
           >
             <ChevronLeft size={20} className="group-hover:-translate-x-0.5 transition-transform" />
           </button>

           <div className="h-8 w-px bg-gradient-to-b from-transparent via-white/10 to-transparent mx-1"></div>

           {selectedDate && (
             <CalendarPopover 
               selectedDate={selectedDate} 
               onDateSelect={setSelectedDate} 
               availableDates={dates || []} 
             />
           )}

           <div className="h-8 w-px bg-gradient-to-b from-transparent via-white/10 to-transparent mx-1"></div>

           <button 
             onClick={handleNextDay}
             className="p-2.5 rounded-xl hover:bg-white/10 text-gray-400 hover:text-white transition-all active:scale-90 group"
           >
             <ChevronRight size={20} className="group-hover:translate-x-0.5 transition-transform" />
           </button>
        </div>

        {/* Center: Dynamic Stat Cards */}
        <div className="hidden md:flex items-center gap-6">
          {/* Total Balance */}
          <div className="glass px-8 py-3 rounded-2xl flex items-center gap-5 group hover:bg-white/[0.07] transition-all cursor-default relative overflow-hidden ring-1 ring-white/5 shadow-2xl">
            <div className="absolute inset-0 bg-blue-500/5 blur-xl group-hover:bg-blue-500/10 transition-colors"></div>
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center text-blue-400 group-hover:scale-110 transition-transform shadow-inner border border-white/5">
              <Wallet size={22} />
            </div>
            <div className="relative">
              <p className="text-[10px] text-blue-300/60 font-bold uppercase tracking-[0.2em] mb-0.5">Total</p>
              <p className={`text-2xl font-bold font-mono leading-none tracking-tight ${
                  (stats?.total_monto || 0) >= 0 ? 'text-transparent bg-clip-text bg-gradient-to-r from-emerald-300 to-teal-400' : 'text-white'
                }`}>
                ${stats?.total_monto.toFixed(2) || '0.00'}
              </p>
            </div>
          </div>

          {/* Pending */}
          <div className="glass px-8 py-3 rounded-2xl flex items-center gap-5 group hover:bg-white/[0.07] transition-all cursor-default relative overflow-hidden ring-1 ring-white/5 shadow-2xl">
            <div className="absolute inset-0 bg-orange-500/5 blur-xl group-hover:bg-orange-500/10 transition-colors"></div>
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-orange-500/20 to-red-500/20 flex items-center justify-center text-orange-400 group-hover:scale-110 transition-transform shadow-inner border border-white/5">
              <Clock size={22} className="group-hover:rotate-12 transition-transform duration-500" />
            </div>
            <div className="relative">
              <p className="text-[10px] text-orange-300/60 font-bold uppercase tracking-[0.2em] mb-0.5">Pendientes</p>
              <p className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-orange-300 to-amber-400 font-mono leading-none tracking-tight">
                {stats?.pending || 0}
              </p>
            </div>
          </div>
        </div>

        {/* Right: Actions & Status */}
        <div className="flex items-center gap-4">
           {syncMessage && (
             <div className={`
               px-6 py-2.5 rounded-2xl text-sm font-bold flex items-center gap-3 shadow-2xl backdrop-blur-md animate-slide-up ring-1
               ${syncMessage.includes('Error') 
                 ? 'bg-red-500/10 text-red-200 border-red-500/20 ring-red-500/20' 
                 : 'bg-emerald-500/10 text-emerald-200 border-emerald-500/20 ring-emerald-500/20'}
             `}>
               <span className={`w-2 h-2 rounded-full ${syncMessage.includes('Error') ? 'bg-red-500' : 'bg-emerald-500'} animate-pulse`}></span>
               {syncMessage}
             </div>
           )}

          {/* Search Button */}
          <button
              onClick={() => setIsSearchOpen(true)}
              className="glass p-3.5 rounded-2xl text-gray-400 hover:text-white hover:bg-white/10 transition-all duration-300 shadow-lg shadow-black/20 group active:scale-95"
              title="Buscar"
          >
              <Search size={22} className="group-hover:scale-110 transition-transform" />
          </button>
           
          <button 
            onClick={handleSync}
            disabled={syncMutation.isPending}
            className="glass p-3.5 rounded-2xl text-blue-400 hover:text-white hover:bg-blue-600 hover:border-blue-500 hover:shadow-[0_0_20px_rgba(37,99,235,0.5)] transition-all duration-300 shadow-lg shadow-black/20 disabled:opacity-50 group active:scale-95"
            title="Sincronizar"
          >
            <RefreshCw size={22} className={`transition-transform duration-700 ${syncMutation.isPending ? 'animate-spin' : 'group-hover:rotate-180'}`} />
          </button>
        </div>
      </header>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 pb-8 custom-scrollbar">
        <div className="max-w-[1600px] mx-auto space-y-8 mt-4">
          
          {/* Table Container */}
          <div className="glass-card min-h-[600px] flex flex-col relative overflow-hidden group/container">
             {/* Decorative blurs */}
             <div className="absolute top-0 right-0 w-96 h-96 bg-blue-500/5 rounded-full blur-[100px] pointer-events-none group-hover/container:bg-blue-500/10 transition-colors duration-1000"></div>
             <div className="absolute bottom-0 left-0 w-96 h-96 bg-purple-500/5 rounded-full blur-[100px] pointer-events-none group-hover/container:bg-purple-500/10 transition-colors duration-1000"></div>

            {/* Header inside table */}
            <div className="px-8 py-6 border-b border-white/5 flex items-center justify-between bg-white/[0.01] relative z-10">
              <div className="flex items-center gap-4">
                <div className="p-2.5 rounded-xl bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-white/5">
                  <ArrowUpRight className="text-blue-400" size={20} />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white tracking-tight">Transacciones</h3>
                  <p className="text-xs text-gray-500 font-medium tracking-wide">
                    Gestiona tus movimientos diarios
                  </p>
                </div>
              </div>
            <div className="text-sm font-medium px-4 py-1.5 rounded-full bg-white/5 text-gray-400 border border-white/5">
                <span className="text-white font-bold">{displayTransactions?.length || 0}</span> registros
              </div>
            </div>

            {txLoading ? (
              <div className="absolute inset-0 flex items-center justify-center bg-black/40 z-20 backdrop-blur-sm">
                <div className="flex flex-col items-center">
                  <div className="relative">
                    <div className="w-16 h-16 border-4 border-blue-500/30 rounded-full animate-spin"></div>
                    <div className="absolute top-0 left-0 w-16 h-16 border-4 border-t-blue-500 rounded-full animate-spin"></div>
                  </div>
                  <span className="mt-4 text-sm text-blue-400 font-bold tracking-widest uppercase animate-pulse">Cargando datos...</span>
                </div>
              </div>
            ) : null}
            
            <div className="flex-1 overflow-x-auto relative z-10">
              <TransactionTable
                transactions={displayTransactions || []}
                onEdit={handleEdit}
                onQuickReview={handleQuickReview}
                onToggleSelect={handleToggleSelect}
                selectedIds={selectedIds}
                isLoading={txLoading}
              />
            </div>
            
            {/* Floating Selection Bar */}
            {selectedIds.size > 0 && (
              <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-30 animate-slide-up">
                 <div className="glass px-6 py-3 rounded-2xl flex items-center gap-4 shadow-2xl border border-white/10 ring-1 ring-black/20 backdrop-blur-xl bg-surface-900/90">
                    <div className="flex items-center gap-2 text-white font-bold mr-2">
                       <div className="w-6 h-6 rounded-full bg-primary-500 flex items-center justify-center text-xs">
                         {selectedIds.size}
                       </div>
                       <span className="text-sm">Seleccionados</span>
                    </div>
                    
                    <div className="h-6 w-px bg-white/10"></div>
                    
                    <button 
                       onClick={handleGroupSelected}
                       disabled={selectedIds.size < 2 || groupMutation.isPending}
                       className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500 hover:text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm border border-indigo-500/20"
                    >
                       <Link2 size={16} />
                       Agrupar
                    </button>

                    {(Array.from(selectedIds).some(id => rawTransactions?.find(t => t.id === id)?.group_id)) && (
                       <button 
                         onClick={handleUngroupSelected}
                         className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-500/20 text-red-300 hover:bg-red-500 hover:text-white transition-all font-medium text-sm border border-red-500/20"
                       >
                         <Link2 size={16} className="strikethrough" /> {/* Strikethrough icon would be nice, but checking lucide */}
                         Desagrupar
                       </button>
                    )}

                    <div className="h-6 w-px bg-white/10"></div>

                    <button 
                       onClick={handleClearSelection}
                       className="p-2 rounded-xl hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
                    >
                       <X size={18} />
                    </button>
                 </div>
              </div>
            )}
          </div>

          {/* Daily Debts Section */}
          {!debtsLoading && dailyDebts && dailyDebts.length > 0 && (
            <div className="glass-card flex flex-col relative overflow-hidden group/debt mt-8 animate-fade-in mb-8">
              {/* Decorative backgrounds */}
              <div className="absolute top-0 right-0 w-96 h-96 bg-purple-500/5 rounded-full blur-[100px] pointer-events-none group-hover/debt:bg-purple-500/10 transition-colors duration-1000"></div>
              
              <div className="px-8 py-6 border-b border-white/5 flex items-center justify-between bg-white/[0.01] relative z-10">
                <div className="flex items-center gap-4">
                  <div className="p-2.5 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-white/5">
                    <CreditCard className="text-purple-400" size={20} />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-white tracking-tight">Deudas del Día</h3>
                    <p className="text-xs text-gray-400 font-medium tracking-wide">
                      Registros en tarjetas o deudas agrupadas
                    </p>
                  </div>
                </div>
                <div className="text-sm font-medium px-4 py-1.5 rounded-full bg-white/5 text-gray-400 border border-white/5">
                  <span className="text-white font-bold">{dailyDebts.length}</span> registros
                </div>
              </div>

              <div className="p-8 relative z-10">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {dailyDebts.map((debt) => (
                    <div 
                      key={debt.ID} 
                      className={`
                        p-5 rounded-2xl border flex flex-col justify-between transition-all group/card
                        ${debt.PAGADA 
                          ? 'bg-emerald-500/5 border-emerald-500/20 hover:border-emerald-500/40 hover:bg-emerald-500/10' 
                          : 'bg-rose-500/5 border-rose-500/20 hover:border-rose-500/40 hover:bg-rose-500/10'
                        }
                      `}
                    >
                      <div className="flex justify-between items-start mb-4">
                        <div className="flex-1 min-w-0 pr-4">
                          <h4 className="font-bold text-white truncate text-base leading-tight mb-1">{debt.DESCRIPCION}</h4>
                          <div className="flex items-center gap-2">
                             <div className="text-[10px] uppercase font-bold tracking-wider text-purple-300 bg-purple-500/10 px-2 py-0.5 rounded-md border border-purple-500/20 inline-block truncate max-w-full">
                               {debt.DEUDOR_NOMBRE}
                             </div>
                             <div className="text-[10px] text-gray-500 font-medium uppercase tracking-widest">{debt.TIPO}</div>
                          </div>
                        </div>
                        <div className={`px-2 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider shrink-0 border ${
                           debt.PAGADA ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                        }`}>
                          {debt.PAGADA ? 'Pagada' : 'Pendiente'}
                        </div>
                      </div>

                      <div className="mt-auto flex justify-between items-end">
                        <div>
                           <div className="text-[9px] text-gray-500 uppercase font-bold tracking-wider mb-0.5">Monto original</div>
                           <div className="text-2xl font-mono font-bold tracking-tighter text-white">
                             ${Math.abs(debt.MONTO).toFixed(2)}
                           </div>
                        </div>
                        {debt.PAGADA && debt.FECHA_PAGO && (
                           <div className="text-[10px] font-medium text-gray-400 text-right">
                              Pagado el<br/><span className="text-gray-300 font-bold">{new Date(debt.FECHA_PAGO).toLocaleDateString()}</span>
                           </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

        </div>
      </div>

      {/* Edit Modal */}
      <EditModal
        transaction={editingTransaction}
        isOpen={!!editingTransaction}
        onClose={() => setEditingTransaction(null)}
        onSave={handleSave}
        categories={[]} 
        existingTags={existingTags || []}
      />

       {/* Search Modal */}
       <SearchModal 
          isOpen={isSearchOpen} 
          onClose={() => setIsSearchOpen(false)}
          onSelectDate={(date) => setSelectedDate(date)}
       />

    </div>
  );
}
