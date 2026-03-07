import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Heart, Meh, Frown, AlertCircle } from 'lucide-react';
import { Transaction } from '../../services/api';

interface HappinessTabProps {
  transactions: Transaction[];
  formatCurrency: (val: number) => string;
  openLocalModal: (title: string, desc: string, txs: Transaction[]) => void;
}

const getHappinessInfo = (level: number) => {
    if (level >= 8) return { icon: <Heart size={24} className="text-emerald-400" />, label: 'Agrega Gran Valor', color: 'text-emerald-400', bg: 'bg-emerald-500/20', border: 'border-emerald-500/30' };
    if (level >= 6) return { icon: <Heart size={24} className="text-emerald-500" />, label: 'Agrega Valor', color: 'text-emerald-500', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' };
    if (level === 5) return { icon: <Meh size={24} className="text-surface-400" />, label: 'Neutro', color: 'text-surface-400', bg: 'bg-surface-700/50', border: 'border-surface-600/50' };
    if (level >= 3) return { icon: <Frown size={24} className="text-rose-400" />, label: 'Insatisfacción', color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/20' };
    if (level >= 1) return { icon: <Frown size={24} className="text-rose-500" />, label: 'Arrepentimiento', color: 'text-rose-500', bg: 'bg-rose-500/20', border: 'border-rose-500/30' };
    return { icon: null, label: 'Desconocido', color: 'text-surface-400', bg: 'bg-surface-800', border: 'border-surface-700' };
};

export function HappinessTab({ transactions, formatCurrency, openLocalModal }: HappinessTabProps) {
  const happinessStats = useMemo(() => {
    const expenses = transactions.filter(t => t.MONTO < 0);
    const ratedExpenses = expenses.filter(t => t.felicidad >= 1 && t.felicidad <= 9);
    const unratedExpenses = expenses.filter(t => !t.felicidad || t.felicidad < 1 || t.felicidad > 9);

    const dist: Record<number, { amount: number; count: number }> = {};
    for (let i = 1; i <= 9; i++) {
        dist[i] = { amount: 0, count: 0 };
    }

    let totalRatedAmount = 0;

    ratedExpenses.forEach(t => {
      const amt = Math.abs(t.MONTO);
      dist[t.felicidad].amount += amt;
      dist[t.felicidad].count += 1;
      totalRatedAmount += amt;
    });

    const unratedAmount = unratedExpenses.reduce((acc, t) => acc + Math.abs(t.MONTO), 0);

    return { dist, totalRatedAmount, unratedAmount, unratedCount: unratedExpenses.length };
  }, [transactions]);

  const scatterOptions = useMemo(() => {
    const expenses = transactions.filter(t => t.MONTO < 0 && t.felicidad >= 1 && t.felicidad <= 9);
    const data = expenses.map(t => [
      t.felicidad + (Math.random() * 0.4 - 0.2), // jitter for visibility
      Math.abs(t.MONTO),
      t.nombre_limpio || t.DESCRIPCION,
      new Date(t.FECHA).toLocaleDateString('es-CO')
    ]);

    return {
      tooltip: {
        trigger: 'item',
        formatter: function (params: any) {
          const d = params.data;
          return `<div class="font-sans text-sm text-white">
                    <strong>${d[2]}</strong><br/>
                    Fecha: ${d[3]}<br/>
                    Monto: $${d[1].toLocaleString('es-CO')}<br/>
                    Felicidad: ${Math.round(d[0])}
                  </div>`;
        },
        backgroundColor: '#1f2937',
        borderColor: '#374151',
        textStyle: { color: '#f3f4f6' }
      },
      grid: {
        left: '10%',
        right: '5%',
        bottom: '15%',
        top: '10%',
        containLabel: true
      },
      xAxis: {
        name: 'Nivel absoluto de Felicidad (1-9)',
        nameLocation: 'middle',
        nameGap: 30,
        type: 'value',
        min: 0.5,
        max: 9.5,
        interval: 1,
        splitLine: { show: false },
        axisLabel: {
          color: '#9ca3af',
          formatter: (val: number) => {
              if (val === 1) return '1';
              if (val === 5) return '5 - Neutro';
              if (val === 9) return '9';
              return Math.round(val);
          }
        }
      },
      yAxis: {
        name: 'Monto ($)',
        type: 'value',
        splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        axisLabel: { color: '#9ca3af', formatter: (val: number) => val >= 1000 ? (val/1000) + 'k' : val }
      },
      series: [
        {
          symbolSize: 16,
          itemStyle: {
            color: (params: any) => {
               const happiness = Math.round(params.data[0]);
               if (happiness === 5) return '#10b981';
               if (happiness === 4) return '#34d399';
               if (happiness === 3) return '#fbbf24';
               if (happiness === 2) return '#f87171';
               return '#e11d48';
            },
            opacity: 0.8,
            borderColor: '#111827',
            borderWidth: 1.5
          },
          data: data,
          type: 'scatter'
        }
      ]
    };
  }, [transactions]);

  return (
    <div className="space-y-6 animate-fade-in">
        {/* Summary */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="col-span-1 md:col-span-2 bg-gradient-to-br from-surface-900 to-surface-950 border border-white/10 p-6 rounded-2xl flex flex-col justify-center shadow-lg relative overflow-hidden">
                <div className="absolute top-0 right-0 w-48 h-48 bg-pink-500/10 rounded-full blur-3xl pointer-events-none"></div>
                <div className="relative z-10">
                    <p className="text-surface-400 uppercase font-bold tracking-wider text-sm mb-2">Gastos Etiquetados</p>
                    <h3 className="text-4xl font-bold text-white tracking-tight">{formatCurrency(happinessStats.totalRatedAmount)}</h3>
                    <p className="text-emerald-400 mt-2 font-medium">
                        {happinessStats.totalRatedAmount > 0 ? (((happinessStats.dist[4].amount + happinessStats.dist[5].amount) / happinessStats.totalRatedAmount) * 100).toFixed(0) : 0}% en niveles buenos (4-5)
                    </p>
                </div>
            </div>
            <div 
                className="bg-surface-900/60 border border-dashed border-white/20 p-6 rounded-2xl flex flex-col justify-center items-center text-center shadow-lg cursor-pointer hover:bg-surface-800 transition-colors group"
                onClick={() => openLocalModal("Gastos sin calificar", "Transacciones que aún no tienen un nivel de felicidad asignado.", transactions.filter(t => t.MONTO < 0 && (!t.felicidad || t.felicidad < 1 || t.felicidad > 9)).sort((a,b) => a.MONTO - b.MONTO))}
            >
                <p className="text-surface-400 uppercase font-bold tracking-wider text-sm mb-2 group-hover:text-surface-300 transition-colors">Sin Etiquetar</p>
                <h3 className="text-2xl font-bold text-surface-300 tracking-tight">{formatCurrency(happinessStats.unratedAmount)}</h3>
                <p className="text-surface-500 mt-1 text-sm">{happinessStats.unratedCount} transacciones sin calificar</p>
            </div>
        </div>

        {/* Happiness Distribution */}
        <div className="bg-surface-900/80 border border-white/10 rounded-2xl p-6 shadow-xl">
            <div className="mb-6 flex items-center justify-between border-b border-white/10 pb-4">
               <h3 className="text-xl font-bold text-white">Distribución de Gastos por Felicidad</h3>
               <div className="group relative cursor-help">
                  <AlertCircle size={16} className="text-surface-500 hover:text-white transition-colors" />
                  <div className="absolute right-0 top-full mt-2 w-64 bg-surface-800 border border-white/10 rounded-xl p-4 text-xs text-surface-300 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity shadow-2xl z-20">
                     <strong className="text-white block mb-1 text-sm">Felicidad Absoluta</strong>
                     Medida sin tomar en cuenta el precio.<br/><br/>
                     <span className="text-emerald-400 font-bold">8-9:</span> Agrega gran valor a tu vida.<br/>
                     <span className="text-emerald-500 font-bold">6-7:</span> Agrega valor real a tu vida.<br/>
                     <span className="text-surface-400 font-bold">5:</span> Funcional, neutral (ej. fijos).<br/>
                     <span className="text-rose-400 font-bold">1-4:</span> Insatisfacción o arrepentimiento.
                  </div>
               </div>
            </div>
            <div className="space-y-6">
                {/* Render ratings from 9 to 1 */}
                {[9, 8, 7, 6, 5, 4, 3, 2, 1].map(level => {
                    const stat = happinessStats.dist[level as keyof typeof happinessStats.dist];
                    const info = getHappinessInfo(level);
                    const percentage = happinessStats.totalRatedAmount > 0 ? (stat.amount / happinessStats.totalRatedAmount) * 100 : 0;
                    
                    return (
                        <div 
                            key={level} 
                            className="flex flex-col gap-2 relative cursor-pointer group hover:bg-surface-800/50 p-3 -mx-3 rounded-xl transition-colors"
                            onClick={() => openLocalModal(`Gastos: ${info.label}`, `Transacciones con nivel de felicidad ${level}.`, transactions.filter(t => t.MONTO < 0 && t.felicidad === level).sort((a,b) => a.MONTO - b.MONTO))}
                        >
                            <div className="flex justify-between items-end">
                                <div className="flex items-center gap-3">
                                    <div className={`p-2 rounded-xl ${info.bg} ${info.border} border shadow-lg`}>
                                        {info.icon}
                                    </div>
                                    <div>
                                        <p className={`font-bold ${info.color}`}>{info.label}</p>
                                        <p className="text-xs text-surface-400">{stat.count} transacciones</p>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <p className="font-bold text-white text-lg">{formatCurrency(stat.amount)}</p>
                                    <p className="text-xs text-surface-400">{percentage.toFixed(1)}%</p>
                                </div>
                            </div>
                            <div className="w-full h-2 bg-surface-950 rounded-full overflow-hidden border border-white/5 relative">
                                <div 
                                    className={`absolute left-0 top-0 h-full rounded-full transition-all duration-1000 ${info.bg.replace('/20', '')}`}
                                    style={{ width: `${percentage}%` }}
                                />
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>

        {/* Scatter Plot */}
        <div className="bg-surface-900/60 border border-white/10 rounded-2xl p-6 shadow-xl">
            <h3 className="text-xl font-bold text-white mb-2 border-b border-white/10 pb-4">Precio vs Felicidad</h3>
            <p className="text-sm text-surface-400 mb-4">Descubre si tus gastos más fuertes te están haciendo realmente feliz.</p>
            <div className="h-[400px] w-full">
                <ReactECharts option={scatterOptions} style={{ height: '100%', width: '100%' }} />
            </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
             {/* Top Regrets */}
             <div className="bg-surface-900/60 border border-rose-500/20 rounded-2xl p-6 shadow-xl">
                <h3 className="text-lg font-bold text-rose-400 mb-4 flex items-center gap-2"><Frown size={20}/> Mayor Insatisfacción</h3>
                <p className="text-sm text-surface-400 mb-4">
                    Los gastos de nivel 1-4
                </p>
                <div className="space-y-4">
                    {transactions
                        .filter(t => t.MONTO < 0 && t.felicidad >= 1 && t.felicidad <= 4)
                        .sort((a, b) => a.MONTO - b.MONTO) // ascending (most negative first)
                        .slice(0, 5)
                        .map(tx => (
                            <div key={tx.id} className="flex justify-between items-center p-4 bg-surface-900/80 rounded-xl border border-rose-500/10">
                                <div>
                                    <div className="font-bold text-rose-300">{tx.nombre_limpio || tx.DESCRIPCION}</div>
                                    <div className="text-xs text-surface-500 flex items-center gap-2 mt-1">
                                        <span className="px-2 py-0.5 bg-rose-500/20 text-rose-400 rounded-md">Nivel {tx.felicidad}</span>
                                        {new Date(tx.FECHA).toLocaleDateString('es-CO')}
                                    </div>
                                </div>
                                <div className="font-mono font-bold text-rose-400">{formatCurrency(tx.MONTO)}</div>
                            </div>
                        ))}
                    {transactions.filter(t => t.MONTO < 0 && t.felicidad >= 1 && t.felicidad <= 4).length === 0 && (
                        <p className="text-surface-500 italic text-center py-4">No hay gastos en esta categoría.</p>
                    )}
                </div>
             </div>

             {/* Top Joys */}
             <div className="bg-surface-900/60 border border-emerald-500/20 rounded-2xl p-6 shadow-xl">
                <h3 className="text-lg font-bold text-emerald-400 mb-4 flex items-center gap-2"><Heart size={20}/> Mayor Valor Agregado</h3>
                <p className="text-sm text-surface-400 mb-4">
                    Tus gastos de nivel 8 y 9
                </p>
                <div className="space-y-4">
                    {transactions
                        .filter(t => t.MONTO < 0 && t.felicidad >= 8 && t.felicidad <= 9)
                        .sort((a, b) => a.MONTO - b.MONTO)
                        .slice(0, 5)
                        .map(tx => (
                            <div key={tx.id} className="flex justify-between items-center p-4 bg-surface-900/80 rounded-xl border border-emerald-500/10">
                                <div>
                                    <div className="font-bold text-emerald-300">{tx.nombre_limpio || tx.DESCRIPCION}</div>
                                    <div className="text-xs text-surface-500 flex items-center gap-2 mt-1">
                                         <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded-md">Nivel {tx.felicidad}</span>
                                         {new Date(tx.FECHA).toLocaleDateString('es-CO')}
                                    </div>
                                </div>
                                <div className="font-mono font-bold text-emerald-400">{formatCurrency(tx.MONTO)}</div>
                            </div>
                        ))}
                    {transactions.filter(t => t.MONTO < 0 && t.felicidad >= 8 && t.felicidad <= 9).length === 0 && (
                        <p className="text-surface-500 italic text-center py-4">No hay gastos en esta categoría.</p>
                    )}
                </div>
             </div>
        </div>
    </div>
  );
}
