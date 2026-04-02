import React from 'react';
import ReactECharts from 'echarts-for-react';
import { BarChart3, TrendingUp, Info } from 'lucide-react';

export const CategoryEfficiencyMap: React.FC = () => {
    // Mock Data: Average Spending vs Average Happiness for all categories
    const categoriesData = [
        { name: 'Vivienda', spent: 850, happiness: 8 },
        { name: 'Suscripciones', spent: 65, happiness: 3 },
        { name: 'Restaurantes', spent: 220, happiness: 6 },
        { name: 'Supermercado', spent: 450, happiness: 7 },
        { name: 'Transporte', spent: 180, happiness: 5 },
        { name: 'Viajes', spent: 300, happiness: 10 },
        { name: 'Ropa', spent: 120, happiness: 4 },
        { name: 'Salud', spent: 150, happiness: 9 },
        { name: 'Gym / Deporte', spent: 80, happiness: 9 },
        { name: 'Gadgets / Tech', spent: 250, happiness: 5 },
    ];

    const option = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'item',
            formatter: (params: any) => {
                const data = params.data;
                return `<strong>${data[2]}</strong><br/>
                        Felicidad: ${data[0]}/10<br/>
                        Gasto: $${data[1]}`;
            }
        },
        grid: { left: '8%', right: '8%', bottom: '10%', top: '15%', containLabel: true },
        xAxis: {
            name: 'Felicidad (ROI Emocional)',
            nameLocation: 'middle',
            nameGap: 35,
            type: 'value',
            min: 0,
            max: 10,
            splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
            axisLabel: { color: '#94a3b8' }
        },
        yAxis: {
            name: 'Gasto Promedio Mensual ($)',
            nameLocation: 'middle',
            nameGap: 50,
            type: 'value',
            splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
            axisLabel: { color: '#94a3b8' }
        },
        series: [
            {
                type: 'scatter',
                symbolSize: (data: any) => Math.sqrt(data[1]) * 2,
                data: categoriesData.map(item => [item.happiness, item.spent, item.name]),
                label: {
                    show: true,
                    formatter: (param: any) => param.data[2],
                    position: 'top',
                    color: '#cbd5e1',
                    fontSize: 10
                },
                itemStyle: {
                    color: (params: any) => {
                        const happiness = params.data[0];
                        if (happiness < 4) return '#ef4444'; // Efficiency Risk
                        if (happiness > 7) return '#10b981'; // High ROI
                        return '#3b82f6'; // Neutral
                    }
                },
                markLine: {
                    silent: true,
                    lineStyle: { type: 'dashed', color: 'rgba(255, 255, 255, 0.15)' },
                    data: [
                        { xAxis: 5 },
                        { yAxis: 300 } // Average baseline
                    ]
                }
            }
        ]
    };

    return (
        <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 p-6 rounded-2xl shadow-xl hover:shadow-2xl hover:border-slate-700 transition-all duration-300">
            <div className="flex flex-col md:flex-row justify-between items-start gap-4 mb-8">
                <div>
                    <h2 className="text-xl font-bold font-sans text-white flex items-center gap-2">
                        <BarChart3 className="text-purple-400" size={24} />
                        Mapa de Eficiencia por Categoría
                    </h2>
                    <p className="text-sm text-slate-400 mt-1">Comparativa de Impacto Emocional vs. Esfuerzo Financiero</p>
                </div>

                <div className="flex gap-4">
                    <div className="flex items-center gap-2 text-[10px] text-slate-400 font-bold uppercase tracking-widest">
                        <div className="w-3 h-3 bg-emerald-500 rounded-full"></div> Inversión Felicidad
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-slate-400 font-bold uppercase tracking-widest">
                        <div className="w-3 h-3 bg-red-500 rounded-full"></div> Gastos Ineficientes
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
                <div className="lg:col-span-3 h-96">
                    <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
                </div>

                <div className="flex flex-col gap-4">
                    <div className="p-4 bg-slate-800/40 border border-slate-700/50 rounded-xl">
                        <h4 className="text-xs font-bold text-slate-300 uppercase mb-3 flex items-center gap-2">
                            <TrendingUp size={14} className="text-emerald-400" /> Top ROI Emocional
                        </h4>
                        <div className="space-y-2">
                           {categoriesData.filter(c => c.happiness >= 8).slice(0, 3).map((c, i) => (
                               <div key={i} className="flex justify-between items-center text-sm">
                                   <span className="text-slate-400">{c.name}</span>
                                   <span className="text-emerald-400 font-bold">{c.happiness}/10</span>
                               </div>
                           ))}
                        </div>
                    </div>

                    <div className="p-4 bg-red-500/5 border border-red-500/10 rounded-xl space-y-3">
                        <div className="flex items-start gap-3">
                            <Info size={16} className="text-red-400 mt-0.5 shrink-0" />
                            <p className="text-xs text-slate-400 leading-relaxed">
                                Las categorías en el cuadrante superior izquierdo representan gastos altos con poca satisfacción. 
                                Considera renegociar o eliminar estos rubros.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
