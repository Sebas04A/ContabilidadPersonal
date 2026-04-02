import React, { useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { Landmark, Users, Info } from 'lucide-react';

export const SROptimizer: React.FC = () => {
    // SRI Ecuador 2025 Constants
    const CANASTA_BASICA = 798.31;
    const REBAJA_PERCENT = 0.18;
    
    // Limits based on "Cargas Familiares"
    const limitsConfig: Record<number, number> = {
        0: 7,
        1: 9,
        2: 11,
        3: 14,
        4: 17,
        5: 20 // 5 or more
    };

    const [cargas, setCargas] = useState(0);
    
    const maxDeductible = CANASTA_BASICA * limitsConfig[cargas];
    
    // Mock Data for categories
    const categories = [
        { name: 'Vivienda', spent: 1200 },
        { name: 'Educación, Arte y Cultura', spent: 300 },
        { name: 'Salud', spent: 850 },
        { name: 'Alimentación', spent: 2100 },
        { name: 'Vestimenta', spent: 400 },
        { name: 'Turismo Nacional', spent: 150 },
    ];

    const totalSpent = categories.reduce((acc, curr) => acc + curr.spent, 0);
    const effectiveDeductible = Math.min(totalSpent, maxDeductible);
    const taxRebate = effectiveDeductible * REBAJA_PERCENT;

    const radarOption = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item' },
        radar: {
            indicator: categories.map(c => ({ name: c.name, max: maxDeductible / 3 })), // Simplified scale for radar
            shape: 'polygon',
            splitNumber: 4,
            axisName: { color: '#94a3b8', fontSize: 10 },
            splitLine: { lineStyle: { color: ['rgba(255, 255, 255, 0.1)'] } },
            splitArea: { show: false },
            axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.2)' } }
        },
        series: [{
            type: 'radar',
            data: [
                {
                    value: categories.map(c => c.spent),
                    name: 'Gasto Real',
                    areaStyle: { color: 'rgba(56, 189, 248, 0.3)' },
                    lineStyle: { color: '#38bdf8', width: 2 },
                    itemStyle: { color: '#38bdf8', borderVisible: false },
                    symbol: 'none'
                }
            ]
        }]
    };

    return (
        <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 p-6 rounded-2xl shadow-xl hover:shadow-2xl hover:border-slate-700 transition-all duration-300 group">
            <div className="flex flex-col md:flex-row justify-between items-start gap-4 mb-6">
                <div>
                    <h2 className="text-xl font-bold font-sans text-white flex items-center gap-2">
                        <Landmark className="text-sky-400" size={24} />
                        Optimizador Fiscal SRI (Ecuador)
                    </h2>
                    <p className="text-sm text-slate-400 mt-1">Estimación de Rebaja del Impuesto a la Renta 2025</p>
                </div>

                <div className="flex items-center gap-3 bg-slate-800/80 p-1.5 rounded-xl border border-white/5 shadow-inner">
                    <span className="text-xs font-semibold text-slate-400 ml-3 flex items-center gap-1">
                        <Users size={14} /> Cargas:
                    </span>
                    <div className="flex gap-1">
                        {[0, 1, 2, 3, 4, 5].map((n) => (
                            <button
                                key={n}
                                onClick={() => setCargas(n)}
                                className={`w-8 h-8 rounded-lg text-xs font-bold transition-all ${
                                    cargas === n 
                                    ? 'bg-sky-500 text-white shadow-lg shadow-sky-500/20' 
                                    : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'
                                }`}
                            >
                                {n === 5 ? '5+' : n}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Left: Summary Cards */}
                <div className="space-y-4">
                    <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700/50">
                        <p className="text-xs text-slate-400 font-medium uppercase tracking-widest mb-1">Tu Rebaja Estimada</p>
                        <p className="text-3xl font-black text-emerald-400">${taxRebate.toFixed(2)}</p>
                        <p className="text-[10px] text-slate-500 mt-1">18% de USD {effectiveDeductible.toFixed(2)}</p>
                    </div>

                    <div className="bg-slate-800/30 p-4 rounded-xl border border-slate-700/30">
                        <div className="flex justify-between items-center mb-2">
                            <p className="text-xs text-slate-400 font-medium">Límite de Gastos (n={limitsConfig[cargas]} CFB)</p>
                            <span className="text-white font-bold text-sm">${maxDeductible.toFixed(2)}</span>
                        </div>
                        <div className="h-2 w-full bg-slate-700 rounded-full overflow-hidden">
                            <div 
                                className={`h-full transition-all duration-500 rounded-full ${totalSpent > maxDeductible ? 'bg-orange-500' : 'bg-sky-500'}`}
                                style={{ width: `${Math.min((totalSpent / maxDeductible) * 100, 100)}%` }}
                            ></div>
                        </div>
                        <p className="text-[10px] text-slate-500 mt-2">
                            Basado en Canasta Familiar Básica (Ene 2025): ${CANASTA_BASICA}
                        </p>
                    </div>

                    <div className="p-3 bg-sky-500/5 border border-sky-500/10 rounded-lg flex items-start gap-2">
                        <Info size={14} className="text-sky-400 mt-0.5 shrink-0" />
                        <p className="text-[10px] text-sky-200/70 leading-relaxed italic">
                            Recuerda que la rebaja se aplica sobre el impuesto causado, no sobre la base imponible. Los gastos deben estar sustentados con facturas electrónicas.
                        </p>
                    </div>
                </div>

                {/* Center: Graph */}
                <div className="lg:col-span-2 flex flex-col">
                    <div className="h-96 w-full">
                        <ReactECharts option={radarOption} style={{ height: '100%', width: '100%' }} />
                    </div>
                    
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-4">
                        {categories.map((cat, idx) => (
                            <div key={idx} className="bg-slate-800/20 p-2.5 rounded-lg border border-slate-700/20 flex justify-between items-center group/item hover:bg-slate-800/40 transition-colors">
                                <span className="text-[11px] text-slate-400 truncate pr-2">{cat.name}</span>
                                <span className="text-xs font-bold text-white">${cat.spent}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};
