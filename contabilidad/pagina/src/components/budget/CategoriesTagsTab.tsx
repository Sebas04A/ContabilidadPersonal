import { useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { TrendingDown } from 'lucide-react';
import { Transaction } from '../../services/api';

interface CategoriesTagsTabProps {
  transactions: Transaction[];
  CATEGORIES: string[];
  availableTags: string[];
  formatCurrency: (val: number) => string;
  openLocalModal: (title: string, desc: string, txs: Transaction[]) => void;
}

export function CategoriesTagsTab({ transactions, CATEGORIES, availableTags, formatCurrency, openLocalModal }: CategoriesTagsTabProps) {
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedAnalyticsTags, setSelectedAnalyticsTags] = useState<string[]>([]);

  const topCategoriesOptions = useMemo(() => {
     const expenses = transactions.filter(t => t.MONTO < 0);
     const entities: Record<string, { name: string, value: number, count: number }> = {};
     
     expenses.forEach(t => {
         const amt = Math.abs(t.MONTO);
         const key = (!t.categoria || t.categoria === '---') ? 'Sin Categoría' : t.categoria;
         if (!entities[key]) entities[key] = { name: key, value: 0, count: 0 };
         entities[key].value += amt;
         entities[key].count += 1;
     });

     let sorted = Object.values(entities).sort((a,b) => b.value - a.value).slice(0, 10);
     sorted.reverse();

     if (sorted.length === 0) return null;

     return {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: (params: any) => {
                const d = params[0].data;
                return `<strong class="text-white">${d.name}</strong><br/>Monto: $${d.value.toLocaleString('es-CO')}<br/>Transacciones: ${d.count}`;
            },
            backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#f3f4f6' }
        },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '5%', containLabel: true },
        xAxis: { type: 'value', splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.05)' } }, axisLabel: { color: '#9ca3af', formatter: (val: number) => val >= 1000 ? (val/1000) + 'k' : val } },
        yAxis: { type: 'category', data: sorted.map(d => d.name), axisLabel: { color: '#e5e7eb', fontWeight: 'bold' }, axisTick: { show: false }, axisLine: { show: false } },
        series: [{
            name: 'Monto',
            type: 'bar',
            data: sorted.map(d => ({
                value: d.value,
                name: d.name,
                count: d.count,
                itemStyle: { color: '#a855f7', borderRadius: [0, 4, 4, 0] }
            }))
        }]
     };
  }, [transactions]);

  const topTagsOptions = useMemo(() => {
     const expenses = transactions.filter(t => t.MONTO < 0);
     const entities: Record<string, { name: string, value: number, count: number }> = {};
     
     expenses.forEach(t => {
         const amt = Math.abs(t.MONTO);
         if (!t.tags || t.tags.trim() === '') {
             const key = 'Sin Etiqueta';
             if (!entities[key]) entities[key] = { name: key, value: 0, count: 0 };
             entities[key].value += amt;
             entities[key].count += 1;
         } else {
             const tTags = t.tags.split(',').map(tag => tag.trim()).filter(Boolean);
             tTags.forEach(tag => {
                 const key = tag;
                 if (!entities[key]) entities[key] = { name: tag, value: 0, count: 0 };
                 entities[key].value += amt;
                 entities[key].count += 1;
             });
         }
     });

     let sorted = Object.values(entities).sort((a,b) => b.value - a.value).slice(0, 10);
     sorted.reverse();

     if (sorted.length === 0) return null;

     return {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: (params: any) => {
                const d = params[0].data;
                return `<strong class="text-white">${d.name}</strong><br/>Monto: $${d.value.toLocaleString('es-CO')}<br/>Transacciones: ${d.count}`;
            },
            backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#f3f4f6' }
        },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '5%', containLabel: true },
        xAxis: { type: 'value', splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.05)' } }, axisLabel: { color: '#9ca3af', formatter: (val: number) => val >= 1000 ? (val/1000) + 'k' : val } },
        yAxis: { type: 'category', data: sorted.map(d => d.name), axisLabel: { color: '#e5e7eb', fontWeight: 'bold' }, axisTick: { show: false }, axisLine: { show: false } },
        series: [{
            name: 'Monto',
            type: 'bar',
            data: sorted.map(d => ({
                value: d.value,
                name: d.name,
                count: d.count,
                itemStyle: { color: '#3b82f6', borderRadius: [0, 4, 4, 0] }
            }))
        }]
     };
  }, [transactions]);

  const categoryChartOptions = useMemo(() => {
     if (selectedCategories.length === 0) return null;
     
     const data = selectedCategories.map(cat => {
         const catTxs = transactions.filter(t => t.MONTO < 0 && (cat === 'Sin Categoría' ? (!t.categoria || t.categoria === '---') : t.categoria === cat));
         const amount = catTxs.reduce((acc, t) => acc + Math.abs(t.MONTO), 0);
         return { name: cat, value: amount, count: catTxs.length };
     }).filter(d => d.value > 0).sort((a,b) => b.value - a.value);

     return {
        tooltip: {
            trigger: 'item',
            formatter: (params: any) => {
                const d = params.data;
                return `<strong class="text-white">${d.name}</strong><br/>Monto: $${d.value.toLocaleString('es-CO')}<br/>Transacciones: ${d.count}`;
            },
            backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#f3f4f6' }
        },
        series: [{
            name: 'Categorías',
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: { borderRadius: 10, borderColor: '#111827', borderWidth: 2 },
            label: { show: false, position: 'center' },
            emphasis: {
                label: { show: true, fontSize: '18', fontWeight: 'bold', color: '#fff', formatter: '{b}\\n{d}%' }
            },
            labelLine: { show: false },
            data: data
        }]
     };
  }, [transactions, selectedCategories]);

  const tagAnalyticsOptions = useMemo(() => {
     if (selectedAnalyticsTags.length === 0) return null;
     
     const data = selectedAnalyticsTags.map(tag => {
         const tagTxs = transactions.filter(t => t.MONTO < 0 && (tag === 'Sin Etiqueta' ? (!t.tags || t.tags.trim() === '') : (t.tags && t.tags.split(',').map(tg => tg.trim()).includes(tag))));
         const amount = tagTxs.reduce((acc, t) => acc + Math.abs(t.MONTO), 0);
         return { name: tag, value: amount, count: tagTxs.length };
     }).filter(d => d.value > 0).sort((a,b) => b.value - a.value);

     return {
        tooltip: {
            trigger: 'item',
            formatter: (params: any) => {
                const d = params.data;
                return `<strong class="text-white">${d.name}</strong><br/>Monto: $${d.value.toLocaleString('es-CO')}<br/>Transacciones: ${d.count}`;
            },
            backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#f3f4f6' }
        },
        series: [{
            name: 'Etiquetas',
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: { borderRadius: 10, borderColor: '#111827', borderWidth: 2 },
            label: { show: false, position: 'center' },
            emphasis: {
                label: { show: true, fontSize: '18', fontWeight: 'bold', color: '#fff', formatter: '{b}\\n{d}%' }
            },
            labelLine: { show: false },
            data: data
        }]
     };
  }, [transactions, selectedAnalyticsTags]);

  return (
    <div className="space-y-8 animate-fade-in">
        {/* Global Top Analysis Section */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Top Categorías */}
            <div className="bg-surface-900/40 border border-white/10 rounded-3xl p-6 md:p-8 shadow-xl">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-3 bg-purple-500/20 text-purple-400 rounded-2xl border border-purple-500/30">
                        <TrendingDown size={24} />
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold text-white">Top 10 Categorías</h2>
                        <p className="text-surface-400 text-sm">Resumen de gastos por categoría.</p>
                    </div>
                </div>
                <div className="h-[350px] w-full bg-surface-900/50 rounded-2xl border border-white/5 p-4 relative flex items-center justify-center">
                    {topCategoriesOptions ? (
                        <ReactECharts option={topCategoriesOptions} style={{ height: '100%', width: '100%' }} />
                    ) : (
                        <p className="text-surface-500 text-sm">No hay datos en este periodo.</p>
                    )}
                </div>
            </div>

            {/* Top Etiquetas */}
            <div className="bg-surface-900/40 border border-white/10 rounded-3xl p-6 md:p-8 shadow-xl">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-3 bg-blue-500/20 text-blue-400 rounded-2xl border border-blue-500/30">
                        <TrendingDown size={24} />
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold text-white">Top 10 Etiquetas</h2>
                        <p className="text-surface-400 text-sm">Resumen de gastos por etiqueta.</p>
                    </div>
                </div>
                <div className="h-[350px] w-full bg-surface-900/50 rounded-2xl border border-white/5 p-4 relative flex items-center justify-center">
                    {topTagsOptions ? (
                        <ReactECharts option={topTagsOptions} style={{ height: '100%', width: '100%' }} />
                    ) : (
                        <p className="text-surface-500 text-sm">No hay datos en este periodo.</p>
                    )}
                </div>
            </div>
        </div>

        {/* Category Analysis Section */}
        <div className="bg-surface-900/40 border border-white/10 rounded-3xl p-6 md:p-8 shadow-xl">
            <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-purple-500/20 text-purple-400 rounded-2xl border border-purple-500/30">
                    <TrendingDown size={24} />
                </div>
                <div>
                    <h2 className="text-2xl font-bold text-white">Análisis por Categoría</h2>
                    <p className="text-surface-400 text-sm">Selecciona las categorías que deseas comparar.</p>
                </div>
            </div>

            {/* Category Selector */}
            <div className="flex flex-col gap-4 mb-8">
                <div className="flex gap-2">
                    <button 
                        onClick={() => setSelectedCategories([...CATEGORIES.filter(c => c !== '---'), 'Sin Categoría'])}
                        className="text-xs font-bold uppercase tracking-tighter text-purple-400 hover:text-purple-300 transition-colors bg-purple-500/10 px-3 py-1.5 rounded-lg border border-purple-500/20"
                    >
                        Marcar todos
                    </button>
                    <button 
                        onClick={() => setSelectedCategories([])}
                        className="text-xs font-bold uppercase tracking-tighter text-surface-400 hover:text-surface-300 transition-colors bg-surface-800 px-3 py-1.5 rounded-lg border border-white/5"
                    >
                        Desmarcar todos
                    </button>
                </div>
                <div className="flex flex-wrap gap-2">
                    {[...CATEGORIES.filter(c => c !== '---'), 'Sin Categoría'].map(cat => {
                        const isSelected = selectedCategories.includes(cat);
                        return (
                            <button
                                key={cat}
                                onClick={() => {
                                    setSelectedCategories(prev => 
                                        isSelected ? prev.filter(c => c !== cat) : [...prev, cat]
                                    );
                                }}
                                className={`px-4 py-2 rounded-xl text-sm font-bold uppercase tracking-wider transition-all border ${
                                    isSelected 
                                    ? 'bg-purple-500 border-purple-400 text-white shadow-[0_0_15px_-3px_rgba(168,85,247,0.4)]'
                                    : 'bg-surface-800 border-white/5 text-surface-400 hover:text-white hover:bg-surface-700'
                                }`}
                            >
                                {cat}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Content */}
            {selectedCategories.length === 0 ? (
                <div className="text-center py-10 bg-surface-900/50 rounded-2xl border border-dashed border-white/10">
                    <p className="text-surface-500 font-medium">Selecciona al menos una categoría para ver los datos.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
                    <div className="h-[350px] w-full bg-surface-900/50 rounded-2xl border border-white/5 p-4 relative flex items-center justify-center">
                        {categoryChartOptions ? (
                            <ReactECharts option={categoryChartOptions} style={{ height: '100%', width: '100%' }} />
                        ) : (
                            <p className="text-surface-500 text-sm">No hay datos en este periodo.</p>
                        )}
                    </div>
                    <div className="space-y-3">
                        {categoryChartOptions?.series[0].data.map((d: any, i: number) => (
                            <div 
                                key={d.name} 
                                className="flex justify-between items-center p-4 bg-surface-900/80 rounded-xl border border-white/5 cursor-pointer hover:bg-surface-800 transition-colors group"
                                onClick={() => openLocalModal(`Categoría: ${d.name}`, "Transacciones de esta categoría.", transactions.filter(t => t.MONTO < 0 && (d.name === 'Sin Categoría' ? (!t.categoria || t.categoria === '---') : t.categoria === d.name)).sort((a,b) => a.MONTO - b.MONTO))}
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 rounded-lg bg-purple-500/20 text-purple-400 flex items-center justify-center font-bold text-xs">{i+1}</div>
                                    <div>
                                        <div className="text-white font-bold uppercase">{d.name}</div>
                                        <div className="text-xs text-surface-500 uppercase tracking-widest">{d.count} transacciones</div>
                                    </div>
                                </div>
                                <div className="font-mono text-lg font-bold text-rose-400">
                                    {formatCurrency(d.value)}
                                </div>
                            </div>
                        ))}
                        {categoryChartOptions?.series[0].data.length === 0 && (
                            <p className="text-surface-500 text-sm py-4">No se registraron gastos en estas categorías durante el periodo.</p>
                        )}
                    </div>
                </div>
            )}
        </div>

        {/* Tags Analysis Section */}
        <div className="bg-surface-900/40 border border-white/10 rounded-3xl p-6 md:p-8 shadow-xl mt-8">
            <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-blue-500/20 text-blue-400 rounded-2xl border border-blue-500/30">
                    <TrendingDown size={24} />
                </div>
                <div>
                    <h2 className="text-2xl font-bold text-white">Análisis por Etiqueta</h2>
                    <p className="text-surface-400 text-sm">Selecciona las etiquetas que deseas comparar.</p>
                </div>
            </div>

            {/* Tags Selector */}
            <div className="flex flex-col gap-4 mb-8">
                <div className="flex gap-2">
                    <button 
                        onClick={() => setSelectedAnalyticsTags([...availableTags, 'Sin Etiqueta'])}
                        className="text-xs font-bold uppercase tracking-tighter text-blue-400 hover:text-blue-300 transition-colors bg-blue-500/10 px-3 py-1.5 rounded-lg border border-blue-500/20"
                    >
                        Marcar todos
                    </button>
                    <button 
                        onClick={() => setSelectedAnalyticsTags([])}
                        className="text-xs font-bold uppercase tracking-tighter text-surface-400 hover:text-surface-300 transition-colors bg-surface-800 px-3 py-1.5 rounded-lg border border-white/5"
                    >
                        Desmarcar todos
                    </button>
                </div>
                <div className="flex flex-wrap gap-2">
                    {[...availableTags, 'Sin Etiqueta'].map(tag => {
                        const isSelected = selectedAnalyticsTags.includes(tag);
                        return (
                            <button
                                key={tag}
                                onClick={() => {
                                    setSelectedAnalyticsTags(prev => 
                                        isSelected ? prev.filter(t => t !== tag) : [...prev, tag]
                                    );
                                }}
                                className={`px-4 py-2 rounded-xl text-sm font-bold uppercase tracking-wider transition-all border ${
                                    isSelected 
                                    ? 'bg-blue-500 border-blue-400 text-white shadow-[0_0_15px_-3px_rgba(59,130,246,0.4)]'
                                    : 'bg-surface-800 border-white/5 text-surface-400 hover:text-white hover:bg-surface-700'
                                }`}
                            >
                                {tag}
                            </button>
                        );
                    })}
                </div>
                {availableTags.length === 0 && (
                    <p className="text-surface-500 text-sm">No tienes etiquetas disponibles.</p>
                )}
            </div>

            {/* Content */}
            {selectedAnalyticsTags.length === 0 ? (
                <div className="text-center py-10 bg-surface-900/50 rounded-2xl border border-dashed border-white/10">
                    <p className="text-surface-500 font-medium">Selecciona al menos una etiqueta para ver los datos.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
                    <div className="h-[350px] w-full bg-surface-900/50 rounded-2xl border border-white/5 p-4 relative flex items-center justify-center">
                        {tagAnalyticsOptions ? (
                            <ReactECharts option={tagAnalyticsOptions} style={{ height: '100%', width: '100%' }} />
                        ) : (
                            <p className="text-surface-500 text-sm">No hay datos en este periodo.</p>
                        )}
                    </div>
                    <div className="space-y-3">
                        {tagAnalyticsOptions?.series[0].data.map((d: any, i: number) => (
                            <div 
                                key={d.name} 
                                className="flex justify-between items-center p-4 bg-surface-900/80 rounded-xl border border-white/5 cursor-pointer hover:bg-surface-800 transition-colors group"
                                onClick={() => openLocalModal(`Etiqueta: ${d.name}`, "Transacciones de esta etiqueta.", transactions.filter(t => t.MONTO < 0 && (d.name === 'Sin Etiqueta' ? (!t.tags || t.tags.trim() === '') : (t.tags && t.tags.split(',').map(tg => tg.trim()).includes(d.name)))).sort((a,b) => a.MONTO - b.MONTO))}
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-xs">{i+1}</div>
                                    <div>
                                        <div className="text-white font-bold uppercase">{d.name}</div>
                                        <div className="text-xs text-surface-500 uppercase tracking-widest">{d.count} transacciones</div>
                                    </div>
                                </div>
                                <div className="font-mono text-lg font-bold text-rose-400">
                                    {formatCurrency(d.value)}
                                </div>
                            </div>
                        ))}
                        {tagAnalyticsOptions?.series[0].data.length === 0 && (
                            <p className="text-surface-500 text-sm py-4">No se registraron gastos en estas etiquetas durante el periodo.</p>
                        )}
                    </div>
                </div>
            )}
        </div>
    </div>
  );
}
