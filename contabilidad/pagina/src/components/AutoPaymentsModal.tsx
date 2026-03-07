import React, { useState, useEffect, useMemo } from 'react';
import { Transaction } from '../services/api';
import { getGroups, createPayment, InterpolationGroup } from '../services/interpolated';
import { X, Calendar, DollarSign, Calculator, ChevronRight } from 'lucide-react';
import ExplorerChart from './ExplorerChart';

interface AutoPaymentsModalProps {
  targetTransaction: Transaction;
  expenseTransactions: Transaction[];
  onClose: () => void;
  onSuccess: () => void;
}

interface PlannedPayment {
  amount: number;
  start_date: string;
  end_date: string;
  note: string;
}

const AutoPaymentsModal: React.FC<AutoPaymentsModalProps> = ({ 
  targetTransaction, 
  expenseTransactions, 
  onClose, 
  onSuccess 
}) => {
  const [groups, setGroups] = useState<InterpolationGroup[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string>('');
  const [isSaving, setIsSaving] = useState(false);
  const [loadingGroups, setLoadingGroups] = useState(true);

  // Fetch Fixed Groups
  useEffect(() => {
    const fetchFixedGroups = async () => {
      try {
        const data = await getGroups('fixed');
        setGroups(data);
        if (data.length > 0) {
           // Default to first optionally, although explicit selection is better
           setSelectedGroupId(data[0].id);
        }
      } catch (error) {
        console.error('Error fetching fixed groups:', error);
      } finally {
        setLoadingGroups(false);
      }
    };
    fetchFixedGroups();
  }, []);

  // Calculate planned payments
  const plannedPayments: PlannedPayment[] = useMemo(() => {
    return expenseTransactions.map(expense => {
      const targetDate = new Date(targetTransaction.FECHA);
      const expenseDate = new Date(expense.FECHA);
      
      const targetDateStr = targetTransaction.FECHA.substring(0, 10);
      const expenseDateStr = expense.FECHA.substring(0, 10);

      let amount = 0;
      let start_date = '';
      let end_date = '';

      if (expenseDate < targetDate) {
        amount = -Math.abs(expense.MONTO);
        start_date = expenseDateStr;
        end_date = targetDateStr;
      } else {
        amount = Math.abs(expense.MONTO);
        start_date = targetDateStr;
        end_date = expenseDateStr;
      }

      return {
        amount,
        start_date,
        end_date,
        note: expense.DESCRIPCION || expense.nombre_limpio || 'Pago automático'
      };
    });
  }, [targetTransaction, expenseTransactions]);

  const handleSave = async () => {
    if (!selectedGroupId) {
      alert('Por favor selecciona un grupo de referencia.');
      return;
    }

    setIsSaving(true);
    try {
      // Save payments sequentially to prevent backend CSV file race conditions
      for (const payment of plannedPayments) {
        await createPayment(selectedGroupId, payment);
      }
      onSuccess();
    } catch (error) {
      console.error('Error saving payments:', error);
      alert('Hubo un error al guardar los pagos.');
    } finally {
      setIsSaving(false);
    }
  };

  const chartData = useMemo(() => {
      if (!targetTransaction && expenseTransactions.length === 0) return { actual: [], reference: [] };

      // 1. Collect all explicit dates
      const datesToInclude = new Set<string>();
      if (targetTransaction) datesToInclude.add(targetTransaction.FECHA.substring(0, 10));
      expenseTransactions.forEach(t => datesToInclude.add(t.FECHA.substring(0, 10)));
      plannedPayments.forEach(p => {
          datesToInclude.add(p.start_date);
          datesToInclude.add(p.end_date);
      });

      if (datesToInclude.size === 0) return { actual: [], reference: [] };

      // 2. Generate continuous date range
      const sortedDatesList = Array.from(datesToInclude).sort();
      const minDate = new Date(sortedDatesList[0]);
      const maxDate = new Date(sortedDatesList[sortedDatesList.length - 1]);
      
      // Add a couple of days padding
      minDate.setDate(minDate.getDate() - 3);
      maxDate.setDate(maxDate.getDate() + 3);

      const timeline: string[] = [];
      let currentDate = new Date(minDate);
      while (currentDate <= maxDate) {
          timeline.push(currentDate.toISOString().split('T')[0]);
          currentDate.setDate(currentDate.getDate() + 1);
      }

      // 3. Compute Actual CumSum
      const allTx = [targetTransaction, ...expenseTransactions].filter(Boolean) as Transaction[];
      const txByDate: Record<string, number> = {};
      allTx.forEach(t => {
          const d = t.FECHA.substring(0, 10);
          txByDate[d] = (txByDate[d] || 0) + t.MONTO;
      });

      let currentSum = 0;
      const actualSeries = timeline.map(d => {
          if (txByDate[d]) {
              currentSum += txByDate[d];
          }
          return { date: d, actual: currentSum };
      });

      // 4. Compute Reference Sum (Active periods)
      // Reference is NOT cumulative; it's the sum of active amounts on a given day
      const referenceSeries = timeline.map(d => {
          let dailyRefSum = 0;
          plannedPayments.forEach(p => {
              if (d >= p.start_date && d <= p.end_date) {
                  dailyRefSum += p.amount;
              }
          });
          return { date: d, value: dailyRefSum };
      });
      //Compute actualSeries - differenceSeries
      const differenceSeries = timeline.map((d, i) => ({
          date: d,
          diff: actualSeries[i].actual - referenceSeries[i].value
      }));
      

      return {
          actual: actualSeries,
          reference: referenceSeries,
          difference:  differenceSeries
      };
  }, [targetTransaction, expenseTransactions, plannedPayments]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(amount);
  };

  return (
    <div className="fixed inset-0 z-[100] flex flex-col items-center pt-10 sm:justify-center sm:pt-0 bg-black/60 backdrop-blur-sm p-4 overflow-y-auto custom-scrollbar" onClick={onClose}>
      <div 
        className="bg-surface-900/95 backdrop-blur-xl rounded-2xl shadow-2xl w-full max-w-4xl border border-white/[0.08] flex flex-col my-auto" 
        style={{ maxHeight: '90vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-6 border-b border-white/[0.06] flex justify-between items-center bg-surface-900/95 sticky top-0 z-10 rounded-t-2xl">
          <div>
             <h2 className="text-2xl font-bold text-white flex items-center gap-3">
               <Calculator className="text-primary-400" />
               Configurar Pagos Automáticos
             </h2>
             <p className="text-surface-400 text-sm mt-1">
               Objetivo: {targetTransaction.DESCRIPCION} ({formatCurrency(targetTransaction.MONTO)})
             </p>
          </div>
          <button 
            onClick={onClose}
            className="p-2 text-surface-400 hover:text-white hover:bg-white/[0.06] rounded-xl transition-all"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
            
            {/* Chart Section */}
            <div className="bg-surface-950/50 rounded-xl border border-white/[0.05] p-4 flex flex-col h-[350px]">
                <h3 className="text-white font-medium mb-4 pl-2">Proyección de Pagos Calculada</h3>
                <div className="flex-1 min-h-0 relative">
                    {chartData.actual.length > 0 ? (
                        <ExplorerChart data={chartData} loading={false} />
                    ) : (
                        <div className="absolute inset-0 flex items-center justify-center text-surface-500">
                            Cargando gráfico...
                        </div>
                    )}
                </div>
            </div>

            {/* List of planned payments */}
            <div>
                <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <DollarSign size={20} className="text-emerald-400" /> 
                    Pagos a Crear ({plannedPayments.length})
                </h3>
                <div className="space-y-3">
                    {plannedPayments.map((payment, index) => (
                         <div key={index} className="bg-surface-800/30 border border-white/[0.04] rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                             <div className="flex-1 min-w-0">
                                <span className="text-sm font-medium text-white block truncate">{payment.note}</span>
                                <div className="flex items-center gap-2 mt-1.5 opacity-80">
                                   <Calendar size={14} className="text-surface-500" />
                                   <div className="text-xs text-surface-400 flex items-center gap-1.5 font-mono">
                                      <span>{payment.start_date}</span>
                                      <ChevronRight size={12} className="text-surface-600" />
                                      <span>{payment.end_date}</span>
                                   </div>
                                </div>
                             </div>
                             <div className={`text-right font-bold font-mono ${payment.amount >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                 {payment.amount > 0 ? '+' : ''}{formatCurrency(payment.amount)}
                             </div>
                         </div>
                    ))}
                </div>
            </div>

            {/* Options */}
            <div className="bg-surface-800/20 border border-white/[0.04] p-5 rounded-xl">
                 <label className="block text-sm font-bold text-surface-300 mb-3 uppercase tracking-wider">
                    Grupo de Referencia
                </label>
                {loadingGroups ? (
                    <div className="text-surface-400 text-sm flex items-center gap-2">
                        <div className="w-4 h-4 rounded-full border-2 border-primary-500 border-t-transparent animate-spin"/>
                        Cargando grupos...
                    </div>
                ) : groups.length === 0 ? (
                    <div className="text-rose-400 text-sm">
                        No hay grupos clasificados como "Fijos" en el sistema. Debes crear uno primero desde la vista de Administración.
                    </div>
                ) : (
                    <select 
                        className="w-full bg-surface-950 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-1 focus:ring-primary-500/50 appearance-none"
                        value={selectedGroupId}
                        onChange={(e) => setSelectedGroupId(e.target.value)}
                    >
                        <option value="">-- Selecciona un grupo (Obligatorio) --</option>
                        {groups.map(g => (
                            <option key={g.id} value={g.id}>{g.name}</option>
                        ))}
                    </select>
                )}
            </div>

        </div>

        {/* Footer */}
        <div className="p-6 border-t border-white/[0.06] bg-surface-900/40 backdrop-blur-lg flex justify-end gap-3 rounded-b-2xl">
            <button
              onClick={onClose}
              className="px-6 py-2.5 text-sm font-medium text-surface-300 hover:text-white hover:bg-white/[0.06] rounded-xl transition-all"
              disabled={isSaving}
            >
               Cancelar
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving || !selectedGroupId || groups.length === 0}
              className="px-6 py-2.5 bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600 text-white text-sm font-bold rounded-xl transition-all shadow-lg shadow-primary-900/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isSaving ? (
                <>
                  <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin"/>
                  Guardando...
                </>
              ) : (
                'Guardar Pagos'
              )}
            </button>
        </div>
      </div>
    </div>
  );
};

export default AutoPaymentsModal;
