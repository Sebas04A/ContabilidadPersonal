import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { PiggyBank, TrendingDown, Check, AlertCircle, X, Plus, Settings2, Layers, Activity } from 'lucide-react';
import { Transaction, BudgetConfig } from '../../services/api';

interface GeneralBudgetTabProps {
  transactions: Transaction[];
  labeledFilter: string;
  totalExpenses: number;
  totalIncome: number;
  labelingStats: { labeled: Transaction[], unlabeled: Transaction[] };
  budgetConfig: BudgetConfig;
  isEditing: boolean;
  saving: boolean;
  editTags: string[];
  newTagKey: string;
  availableTags: string[];
  selectedPeriod: string;
  setNewTagKey: (val: string) => void;
  setIsEditing: (val: boolean) => void;
  setEditTags: (tags: string[]) => void;
  handleAddNewTag: () => void;
  handleRemoveTag: (tag: string) => void;
  handleSave: () => void;
  openTagModal: (tag: string) => void;
  openLocalModal: (title: string, desc: string, txs: Transaction[]) => void;
  formatCurrency: (val: number) => string;
  renderProgressBar: (spent: number, budget: number, colorClass?: string) => React.ReactNode;
  tagExpenses: Record<string, number>;
  tagBalances: Record<string, number>;
}

export function GeneralBudgetTab({
  transactions, labeledFilter, totalExpenses, totalIncome, labelingStats, budgetConfig, isEditing, saving,
  editTags, newTagKey, availableTags, selectedPeriod,
  setNewTagKey, setIsEditing, setEditTags, handleAddNewTag, handleRemoveTag, handleSave,
  openTagModal, openLocalModal, formatCurrency, renderProgressBar, tagExpenses, tagBalances
}: GeneralBudgetTabProps) {

  const { topExpenses, totalNegative, expenseChartOptions } = useMemo(() => {
     const expenses = transactions.filter(t => t.MONTO < 0);
     const totalNegative = expenses.reduce((acc, t) => acc + Math.abs(t.MONTO), 0);
     
     const grouped: Record<string, { value: number, txs: Transaction[] }> = {};
     expenses.forEach(t => {
         const name = t.nombre_limpio || t.DESCRIPCION || "Desconocido";
         const key = name.toUpperCase().trim();
         if (!grouped[key]) grouped[key] = { value: 0, txs: [] };
         grouped[key].value += Math.abs(t.MONTO);
         grouped[key].txs.push(t);
     });

     const sortedGroups = Object.keys(grouped)
         .map(key => ({ 
            name: key, 
            value: grouped[key].value,
            txs: grouped[key].txs
         }))
         .sort((a,b) => b.value - a.value);

     const top5 = sortedGroups.slice(0, 5);
     const pieData = sortedGroups.slice(0, 10).map(item => ({ value: item.value, name: item.name, txs: item.txs }));
     if (sortedGroups.length > 10) {
         const othersVal = sortedGroups.slice(10).reduce((acc, item) => acc + item.value, 0);
         const othersTxs = sortedGroups.slice(10).flatMap(item => item.txs);
         pieData.push({ value: othersVal, name: 'OTROS', txs: othersTxs });
     }

     const options = {
         tooltip: {
             trigger: 'item',
             formatter: (params: any) => {
                 return `<strong class="text-white">${params.data.name}</strong><br/>Monto: $${params.data.value.toLocaleString('es-CO')}<br/>Transacciones: ${params.data.txs.length}`;
             },
             backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#f3f4f6' }
         },
         legend: { show: false },
         series: [
             {
                 name: 'Gastos',
                 type: 'pie',
                 radius: ['45%', '75%'],
                 avoidLabelOverlap: true,
                 itemStyle: {
                     borderRadius: 8,
                     borderColor: '#111827',
                     borderWidth: 2
                 },
                 label: {
                     show: true,
                     formatter: '{b}\n{d}%',
                     color: '#9ca3af',
                     fontSize: 10
                 },
                 labelLine: { length: 10, length2: 10, lineStyle: { color: '#4b5563' } },
                 data: pieData
             }
         ]
     };

     return { topExpenses: top5, totalNegative, expenseChartOptions: options };
  }, [transactions]);


  return (
    <>
        {/* General Budget Card */}
        <div 
            className="bg-gradient-to-br from-surface-900/80 to-surface-950 border border-white/10 rounded-3xl p-8 shadow-2xl relative overflow-hidden cursor-pointer hover:border-white/20 transition-all group"
            onClick={() => openLocalModal("Presupuesto General", "Todas las transacciones que cumplen con los filtros actuales.", [...transactions].sort((a,b) => a.MONTO - b.MONTO))}
        >
             {/* Glow */}
             <div className="absolute top-0 right-0 w-64 h-64 bg-secondary-500/10 rounded-full blur-3xl pointer-events-none"></div>

             <div className="flex items-center gap-3 mb-6 relative z-10">
                 <div className="p-3 bg-secondary-500/20 text-secondary-400 rounded-2xl border border-secondary-500/30">
                     <PiggyBank size={24} />
                 </div>
                 <h2 className="text-2xl font-bold text-white">Presupuesto General</h2>
             </div>

             <div className="relative z-10">
                 <div className="flex justify-between items-end mb-4">
                     <div>
                         <p className="text-sm font-bold text-surface-400 uppercase tracking-wider mb-1">Gastado</p>
                         <p className={`text-3xl font-bold tracking-tight ${totalExpenses > totalIncome && totalIncome > 0 ? 'text-rose-400' : 'text-white'}`}>
                             {formatCurrency(totalExpenses)}
                         </p>
                     </div>
                     <div className="text-right">
                         <p className="text-sm font-bold text-surface-400 uppercase tracking-wider mb-1">Presupuesto (Ingresos)</p>
                         <p className="text-2xl font-bold tracking-tight text-emerald-400">
                             {formatCurrency(totalIncome)}
                         </p>
                     </div>
                 </div>
                 {renderProgressBar(totalExpenses, totalIncome)}
                 
                 <div className="mt-4 flex justify-between text-sm font-medium">
                     <span className="text-surface-400">
                         {((totalExpenses / (totalIncome || 1)) * 100).toFixed(1)}% utilizado
                     </span>
                     <span className={totalIncome - totalExpenses >= 0 ? "text-emerald-400" : "text-rose-400"}>
                         {formatCurrency(Math.abs(totalIncome - totalExpenses))} {totalIncome - totalExpenses >= 0 ? 'restantes' : 'excedidos'}
                     </span>
                 </div>
             </div>
        </div>

        {/* Labeling Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8">
             <div 
                className="bg-blue-500/10 border border-blue-500/20 rounded-2xl p-6 shadow-xl relative overflow-hidden cursor-pointer hover:bg-blue-500/20 transition-colors group"
                onClick={() => openLocalModal("Todas las Transacciones", "Todas las transacciones de este periodo.", [...labelingStats.labeled, ...labelingStats.unlabeled].sort((a,b) => a.MONTO - b.MONTO))}
             >
                 <div className="flex justify-between items-center relative z-10">
                     <div>
                         <p className="text-sm font-bold text-blue-400/80 uppercase tracking-wider mb-1">Todas</p>
                         <p className="text-3xl font-bold tracking-tight text-blue-400">
                             {labelingStats.labeled.length + labelingStats.unlabeled.length} <span className="text-lg font-medium text-blue-400/60">txs</span>
                         </p>
                     </div>
                     <div className="p-3 bg-blue-500/20 text-blue-400 rounded-2xl border border-blue-500/30 group-hover:scale-110 transition-transform">
                         <Layers size={24} />
                     </div>
                 </div>
             </div>
             <div 
                className={`bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-6 shadow-xl relative overflow-hidden cursor-pointer hover:bg-emerald-500/20 transition-all group ${labeledFilter === 'unlabeled' ? 'opacity-30 grayscale hover:opacity-100 hover:grayscale-0' : ''}`}
                onClick={() => openLocalModal("Transacciones Etiquetadas", "Transacciones que ya han sido revisadas y categorizadas.", labelingStats.labeled.sort((a,b) => a.MONTO - b.MONTO))}
             >
                 <div className="flex justify-between items-center relative z-10">
                     <div>
                         <p className="text-sm font-bold text-emerald-400/80 uppercase tracking-wider mb-1">Etiquetadas</p>
                         <p className="text-3xl font-bold tracking-tight text-emerald-400">
                             {labelingStats.labeled.length} <span className="text-lg font-medium text-emerald-400/60">txs</span>
                         </p>
                     </div>
                     <div className="p-3 bg-emerald-500/20 text-emerald-400 rounded-2xl border border-emerald-500/30 group-hover:scale-110 transition-transform">
                         <Check size={24} />
                     </div>
                 </div>
             </div>
             
             <div 
                className={`bg-rose-500/10 border border-rose-500/20 rounded-2xl p-6 shadow-xl relative overflow-hidden cursor-pointer hover:bg-rose-500/20 transition-all group ${labeledFilter === 'labeled' ? 'opacity-30 grayscale hover:opacity-100 hover:grayscale-0' : ''}`}
                onClick={() => openLocalModal("Transacciones No Etiquetadas", "Transacciones pendientes por revisar y categorizar.", labelingStats.unlabeled.sort((a,b) => a.MONTO - b.MONTO))}
             >
                 <div className="flex justify-between items-center relative z-10">
                     <div>
                         <p className="text-sm font-bold text-rose-400/80 uppercase tracking-wider mb-1">No Etiquetadas / Pendientes</p>
                         <p className="text-3xl font-bold tracking-tight text-rose-400">
                             {labelingStats.unlabeled.length} <span className="text-lg font-medium text-rose-400/60">txs</span>
                         </p>
                     </div>
                     <div className="p-3 bg-rose-500/20 text-rose-400 rounded-2xl border border-rose-500/30 group-hover:scale-110 transition-transform">
                         <AlertCircle size={24} />
                     </div>
                 </div>
             </div>
        </div>

        {/* Visual Analysis Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-8">
            {/* Top 5 Gastos Fuertes */}
            <div className="bg-surface-900/60 border border-white/10 rounded-2xl p-6 shadow-xl flex flex-col">
                <h3 className="text-lg font-bold text-white mb-4 border-b border-white/10 pb-3 flex items-center justify-between">
                    <span className="flex items-center gap-2"><Activity size={18} className="text-rose-400" /> Mayores Gastos Individuales</span>
                </h3>
                <div className="flex-1 space-y-3">
                    {topExpenses.map((expense, idx) => {
                        const pct = totalNegative > 0 ? (expense.value / totalNegative) * 100 : 0;
                        return (
                            <div 
                               key={idx} 
                               className="group relative cursor-pointer bg-surface-950/50 hover:bg-surface-800 border border-transparent hover:border-white/5 p-3 rounded-xl transition-all"
                               onClick={() => openLocalModal(`Gastos de: ${expense.name}`, `Detalle de transacciones agrupadas bajo este nombre.`, expense.txs.sort((a,b) => new Date(b.FECHA).getTime() - new Date(a.FECHA).getTime()))}
                            >
                                <div className="flex justify-between items-end mb-2">
                                    <span className="font-bold text-sm text-white truncate max-w-[60%] group-hover:text-rose-300 transition-colors uppercase">{expense.name}</span>
                                    <div className="flex flex-col items-end">
                                        <span className="font-mono font-bold text-rose-400 text-sm">{formatCurrency(expense.value)}</span>
                                    </div>
                                </div>
                                <div className="w-full h-1.5 bg-surface-800 rounded-full overflow-hidden">
                                    <div 
                                        className="h-full rounded-full transition-all duration-1000 bg-rose-500 shadow-[0_0_8px_#f43f5e]" 
                                        style={{ width: `${Math.min(pct, 100)}%` }}
                                    />
                                </div>
                                <div className="flex justify-between items-center mt-1">
                                   <span className="text-[10px] text-surface-500">{expense.txs.length} transacciones</span>
                                   <span className="text-xs text-surface-400 font-medium">{pct.toFixed(1)}% del total</span>
                                </div>
                            </div>
                        );
                    })}
                    {topExpenses.length === 0 && (
                        <div className="h-full flex items-center justify-center text-surface-500 italic text-sm py-10">No hay gastos en este periodo.</div>
                    )}
                </div>
            </div>

            {/* Distribucion Donut */}
            <div className="bg-surface-900/60 border border-white/10 rounded-2xl p-6 shadow-xl flex flex-col">
                <h3 className="text-lg font-bold text-white mb-2 border-b border-white/10 pb-3 flex items-center justify-between">
                    <span className="flex items-center gap-2"><TrendingDown size={18} className="text-purple-400" /> Distribución de Gastos</span>
                </h3>
                <div className="flex-1 w-full min-h-[300px] flex items-center justify-center relative">
                   {totalNegative > 0 ? (
                       <>
                           <div className="absolute inset-0 flex items-center justify-center pointer-events-none flex-col animate-fade-in">
                               <span className="text-sm font-medium text-surface-400 uppercase tracking-widest mb-1">Total Gastos</span>
                               <span className="text-2xl font-bold text-rose-400">{formatCurrency(totalNegative)}</span>
                           </div>
                           <ReactECharts 
                               option={expenseChartOptions} 
                               style={{ height: '100%', width: '100%', minHeight: '320px' }} 
                               opts={{ renderer: 'svg' }}
                               onEvents={{
                                   'click': (params: any) => {
                                       if (params.data && params.data.txs) {
                                           openLocalModal(`Distribución: ${params.data.name}`, `Transacciones que componen esta sección.`, params.data.txs.sort((a: Transaction, b: Transaction) => new Date(b.FECHA).getTime() - new Date(a.FECHA).getTime()));
                                       }
                                   }
                               }}
                           />
                       </>
                   ) : (
                       <div className="text-center text-surface-500 italic text-sm py-20">Aún no hay suficientes datos para graficar.</div>
                   )}
                </div>
            </div>
        </div>

        {/* Title and Edit Button for Tags */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pt-8">
             <div className="flex items-center gap-3">
                 <div className="p-2 bg-primary-500/20 text-primary-400 rounded-xl border border-primary-500/30">
                     <TrendingDown size={20} />
                 </div>
                 <h2 className="text-xl font-bold text-white">Presupuesto por Tags</h2>
             </div>
             
             <div className="flex gap-2">
                 {isEditing && (
                     <button 
                         onClick={() => {
                             setIsEditing(false);
                             setEditTags(budgetConfig.tracked_tags || []);
                         }}
                         className="px-4 py-2 rounded-xl font-bold transition-all bg-surface-800 border border-white/10 text-white hover:bg-rose-500/20 hover:text-rose-400 hover:border-rose-500/50 flex items-center gap-2 text-sm"
                     >
                         <X size={16} /> Cancelar
                     </button>
                 )}
                 <button 
                     onClick={() => isEditing ? handleSave() : setIsEditing(true)}
                     disabled={saving}
                     className={`px-4 py-2 rounded-xl font-bold transition-all shadow-lg flex items-center gap-2 text-sm ${
                         isEditing 
                         ? 'bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 text-white' 
                         : 'bg-surface-800 border border-white/10 hover:border-white/20 text-white hover:bg-surface-700'
                     }`}
                 >
                     {isEditing ? (
                         <>
                            {saving ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <Check size={16} />}
                            {saving ? 'Guardando...' : 'Guardar'}
                         </>
                     ) : (
                         <><Settings2 size={16} /> Editar Presupuesto</>
                     )}
                 </button>
             </div>
        </div>

        {/* Tags Budget Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
             {(isEditing ? editTags : budgetConfig.tracked_tags || []).map((tag) => {
                 const spent = tagExpenses[tag] || 0;
                 const amount = tagBalances[tag] || 0;
                 
                 return (
                     <div 
                         key={tag} 
                         className="bg-surface-900/60 backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-xl group hover:border-white/20 transition-all cursor-pointer"
                         onClick={() => openLocalModal(`Balance en: ${tag}`, 'Todas las transacciones (ingresos y gastos) para este tag en el periodo actual.', transactions.filter(t => t.tags && t.tags.split(',').map(tg => tg.trim()).includes(tag)).sort((a,b) => new Date(b.FECHA).getTime() - new Date(a.FECHA).getTime()))}
                     >
                         <div className="flex justify-between items-start mb-4">
                             <h3 
                                 className="text-lg font-bold text-white flex items-center gap-2 transition-colors"
                             >
                                 <span className="w-2 h-2 rounded-full bg-primary-500 shadow-[0_0_8px_#8b5cf6]" />
                                 {tag}
                             </h3>
                             {isEditing && (
                                 <button 
                                     onClick={(e) => { e.stopPropagation(); handleRemoveTag(tag); }} 
                                     className="text-surface-500 hover:text-rose-400 transition-colors p-1"
                                 >
                                     <X size={16} />
                                 </button>
                             )}
                         </div>

                         <div className="flex justify-between items-baseline mb-2">
                             <span className={`font-bold text-lg ${spent > amount && amount > 0 ? 'text-rose-400' : 'text-white'}`}>
                                 {formatCurrency(spent)} <span className="text-xs font-normal text-surface-500">gastado ({selectedPeriod === 'all' ? 'total' : 'periodo'})</span>
                             </span>
                             <span 
                                 className="text-emerald-400 text-sm font-medium cursor-pointer hover:underline transition-all"
                                 onClick={(e) => { e.stopPropagation(); openTagModal(tag); }}
                             >
                                 {formatCurrency(amount)} presupuestado
                             </span>
                         </div>
                         {renderProgressBar(spent, amount)}
                     </div>
                 );
             })}

             {isEditing && (
                 <div className="bg-surface-900/40 backdrop-blur-xl border border-dashed border-white/20 rounded-2xl p-6 flex flex-col justify-center gap-4">
                     <p className="text-sm font-bold text-surface-400 uppercase tracking-widest text-center">Nuevo Tag</p>
                     <div className="flex gap-2">
                         <div className="relative flex-1">
                             <select 
                                 value={newTagKey}
                                 onChange={(e) => setNewTagKey(e.target.value)}
                                 className="w-full bg-surface-950 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-primary-500 appearance-none"
                             >
                                 <option value="">Selecciona un tag para monitorear...</option>
                                 {availableTags
                                     .filter(t => !editTags.includes(t)) // Ocultar los que ya están
                                     .map(tag => (
                                     <option key={tag} value={tag}>{tag}</option>
                                 ))}
                             </select>
                         </div>
                         <button 
                             onClick={handleAddNewTag}
                             disabled={!newTagKey}
                             className="p-2 bg-primary-600 hover:bg-primary-500 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed px-4 flex items-center justify-center"
                         >
                             <Plus size={20} />
                         </button>
                     </div>
                 </div>
             )}
             
             {!isEditing && (budgetConfig.tracked_tags || []).length === 0 && (
                 <div className="col-span-full py-12 text-center border border-dashed border-white/10 rounded-2xl bg-surface-900/20">
                     <TrendingDown size={32} className="text-surface-600 mx-auto mb-3" />
                     <p className="text-surface-400 text-lg">No hay tags configurados.</p>
                     <p className="text-surface-500 text-sm mt-1">Haz clic en "Editar Presupuesto" para comenzar.</p>
                 </div>
             )}
        </div>
    </>
  );
}
