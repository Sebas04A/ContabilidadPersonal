import { useMemo } from 'react';
import { Flame, Sparkles } from 'lucide-react';
import { Transaction } from '../../services/api';

interface NeedsWantsTabProps {
  transactions: Transaction[];
  totalIncome: number;
  formatCurrency: (val: number) => string;
  renderProgressBar: (spent: number, budget: number, colorClass?: string) => React.ReactNode;
  openLocalModal: (title: string, desc: string, txs: Transaction[]) => void;
}

export function NeedsWantsTab({ transactions, totalIncome, formatCurrency, renderProgressBar, openLocalModal }: NeedsWantsTabProps) {
  const priorityStats = useMemo(() => {
    const expenses = transactions.filter(t => t.MONTO < 0);
    const needs = expenses.filter(t => t.prioridad === 'Necesidad');
    const wants = expenses.filter(t => t.prioridad === 'Deseo');
    const unratedExpenses = expenses.filter(t => t.prioridad !== 'Necesidad' && t.prioridad !== 'Deseo');

    const needsAmount = needs.reduce((acc, t) => acc + Math.abs(t.MONTO), 0);
    const wantsAmount = wants.reduce((acc, t) => acc + Math.abs(t.MONTO), 0);
    const unratedAmount = unratedExpenses.reduce((acc, t) => acc + Math.abs(t.MONTO), 0);
    
    return { 
        needsAmount, 
        wantsAmount, 
        unratedAmount, 
        needsCount: needs.length, 
        wantsCount: wants.length, 
        unratedCount: unratedExpenses.length,
        totalRatedAmount: needsAmount + wantsAmount 
    };
  }, [transactions]);

  return (
    <div className="space-y-6 animate-fade-in">
        {/* Summary */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="col-span-1 md:col-span-2 bg-gradient-to-br from-surface-900 to-surface-950 border border-white/10 p-6 rounded-2xl flex flex-col justify-center shadow-lg relative overflow-hidden">
                <div className="absolute top-0 right-0 w-48 h-48 bg-amber-500/10 rounded-full blur-3xl pointer-events-none"></div>
                <div className="relative z-10">
                    <p className="text-surface-400 uppercase font-bold tracking-wider text-sm mb-2">Gastos Clasificados (Nec/Des)</p>
                    <h3 className="text-4xl font-bold text-white tracking-tight">{formatCurrency(priorityStats.totalRatedAmount)}</h3>
                    {totalIncome > 0 && (
                        <p className="text-secondary-400 mt-2 font-medium">
                            Representa el {((priorityStats.totalRatedAmount / totalIncome) * 100).toFixed(1)}% de tus ingresos del periodo
                        </p>
                    )}
                </div>
            </div>
            <div 
                className="bg-surface-900/60 border border-dashed border-white/20 p-6 rounded-2xl flex flex-col justify-center items-center text-center shadow-lg cursor-pointer hover:bg-surface-800 transition-colors group"
                onClick={() => openLocalModal("Sin Clasificar", "Transacciones sin prioridad asignada.", transactions.filter(t => t.MONTO < 0 && t.prioridad !== 'Necesidad' && t.prioridad !== 'Deseo').sort((a,b) => a.MONTO - b.MONTO))}
            >
                <p className="text-surface-400 uppercase font-bold tracking-wider text-sm mb-2 group-hover:text-surface-300 transition-colors">Sin Clasificar</p>
                <h3 className="text-2xl font-bold text-surface-300 tracking-tight">{formatCurrency(priorityStats.unratedAmount)}</h3>
                <p className="text-surface-500 mt-1 text-sm">{priorityStats.unratedCount} transacciones sin evaluar</p>
            </div>
        </div>

        {/* Distribution */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
             {/* Necesidades */}
             <div 
                className="bg-surface-900/60 border border-amber-500/20 rounded-2xl p-6 shadow-xl relative overflow-hidden group hover:border-amber-500/40 transition-colors cursor-pointer"
                onClick={() => openLocalModal("Necesidades", "Tus gastos clasificados como necesidades, ordenados de mayor a menor.", transactions.filter(t => t.MONTO < 0 && t.prioridad === 'Necesidad').sort((a,b) => a.MONTO - b.MONTO))}
             >
                <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/5 rounded-full blur-2xl group-hover:bg-amber-500/10 transition-colors"></div>
                <div className="relative z-10">
                    <h3 className="text-xl font-bold text-white mb-2 border-b border-white/10 pb-4 flex items-center justify-between">
                        <span className="flex items-center gap-2"><Flame className="text-amber-400" /> Necesidades</span>
                        <span className="text-amber-400 text-sm">{priorityStats.totalRatedAmount > 0 ? ((priorityStats.needsAmount / priorityStats.totalRatedAmount) * 100).toFixed(1) : 0}%</span>
                    </h3>
                    <div className="py-2">
                         <p className="text-3xl font-bold text-white tracking-tight break-all mb-1">{formatCurrency(priorityStats.needsAmount)}</p>
                         <p className="text-sm text-surface-400">{priorityStats.needsCount} transacciones</p>
                    </div>
                    {totalIncome > 0 && (
                        <div className="mt-4 bg-surface-950 p-3 rounded-xl border border-white/5">
                            <p className="text-xs text-surface-400 mb-1 flex justify-between">
                                <span>Consumo de ingresos (Ideal &lt;= 50%)</span>
                                <span className={((priorityStats.needsAmount / totalIncome) * 100) > 50 ? 'text-rose-400' : 'text-emerald-400'}>{((priorityStats.needsAmount / totalIncome) * 100).toFixed(1)}%</span>
                            </p>
                            {renderProgressBar(priorityStats.needsAmount, totalIncome * 0.5, 'bg-amber-400 shadow-[0_0_10px_#fbbf2480]')}
                        </div>
                    )}
                </div>
             </div>

             {/* Deseos */}
             <div 
                className="bg-surface-900/60 border border-primary-500/20 rounded-2xl p-6 shadow-xl relative overflow-hidden group hover:border-primary-500/40 transition-colors cursor-pointer"
                onClick={() => openLocalModal("Deseos", "Tus gastos clasificados como deseos, ordenados de mayor a menor.", transactions.filter(t => t.MONTO < 0 && t.prioridad === 'Deseo').sort((a,b) => a.MONTO - b.MONTO))}
             >
                <div className="absolute top-0 right-0 w-32 h-32 bg-primary-500/5 rounded-full blur-2xl group-hover:bg-primary-500/10 transition-colors"></div>
                <div className="relative z-10">
                    <h3 className="text-xl font-bold text-white mb-2 border-b border-white/10 pb-4 flex items-center justify-between">
                        <span className="flex items-center gap-2"><Sparkles className="text-primary-400" /> Deseos</span>
                        <span className="text-primary-400 text-sm">{priorityStats.totalRatedAmount > 0 ? ((priorityStats.wantsAmount / priorityStats.totalRatedAmount) * 100).toFixed(1) : 0}%</span>
                    </h3>
                    <div className="py-2">
                         <p className="text-3xl font-bold text-white tracking-tight break-all mb-1">{formatCurrency(priorityStats.wantsAmount)}</p>
                         <p className="text-sm text-surface-400">{priorityStats.wantsCount} transacciones</p>
                    </div>
                    {totalIncome > 0 && (
                        <div className="mt-4 bg-surface-950 p-3 rounded-xl border border-white/5">
                            <p className="text-xs text-surface-400 mb-1 flex justify-between">
                                <span>Consumo de ingresos (Ideal &lt;= 30%)</span>
                                <span className={((priorityStats.wantsAmount / totalIncome) * 100) > 30 ? 'text-rose-400' : 'text-emerald-400'}>{((priorityStats.wantsAmount / totalIncome) * 100).toFixed(1)}%</span>
                            </p>
                            {renderProgressBar(priorityStats.wantsAmount, totalIncome * 0.3, 'bg-primary-500 shadow-[0_0_10px_#8b5cf680]')}
                        </div>
                    )}
                </div>
             </div>
        </div>

        {/* List comparisons */}
        <div className="grid grid-cols-1 gap-4">
             <div className="bg-surface-900/60 border border-white/10 rounded-2xl p-6 shadow-xl">
                <h3 className="text-lg font-bold text-white mb-4 border-b border-white/10 pb-3 flex items-center justify-between">
                    <span>Top 10 Deseos más costosos</span>
                    <Sparkles size={18} className="text-primary-400" />
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {transactions
                        .filter(t => t.MONTO < 0 && t.prioridad === 'Deseo')
                        .sort((a, b) => a.MONTO - b.MONTO) // ascending (most negative first)
                        .slice(0, 10)
                        .map(tx => (
                            <div key={tx.id} className="flex justify-between items-center p-3 py-2 bg-surface-950 hover:bg-surface-800 rounded-xl border border-white/5 transition-colors group">
                                <div className="flex flex-col overflow-hidden">
                                    <span className="font-bold text-white text-sm truncate group-hover:text-primary-300 transition-colors uppercase">{tx.nombre_limpio || tx.DESCRIPCION}</span>
                                    <div className="flex text-[10px] text-surface-500 gap-2 uppercase tracking-widest mt-0.5">
                                        <span>{new Date(tx.FECHA).toLocaleDateString('es-CO')}</span>
                                        <span>&bull;</span>
                                        <span className="truncate">{tx.categoria}</span>
                                    </div>
                                </div>
                                <span className="font-mono font-bold text-rose-400 shrink-0 ml-2 text-sm">
                                    {formatCurrency(tx.MONTO)}
                                </span>
                            </div>
                        ))}
                    {transactions.filter(t => t.MONTO < 0 && t.prioridad === 'Deseo').length === 0 && (
                        <p className="text-surface-500 text-sm italic text-center py-4 col-span-full">No has registrado deseos en este periodo.</p>
                    )}
                </div>
             </div>
        </div>
    </div>
  );
}
