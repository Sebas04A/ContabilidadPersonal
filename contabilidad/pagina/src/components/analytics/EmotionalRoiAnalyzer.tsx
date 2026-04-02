import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Smile, TrendingDown, Clock } from 'lucide-react';

export const EmotionalRoiAnalyzer: React.FC = () => {
    // Shared Data
    const inefficientExpenses = [
        { id: 1, name: 'Suscripciones olvidadas', amount: 45.0, happiness: 2 },
        { id: 2, name: 'Comida rápida frecuente', amount: 120.0, happiness: 3 },
        { id: 3, name: 'Ropa de impulso', amount: 85.0, happiness: 2 },
    ];

    const totalWasted = inefficientExpenses.reduce((sum, item) => sum + item.amount, 0);

    // Echarts Option for the Scatter Plot or Bar Chart (Happiness)
    const happinessOption = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' }
        },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
        xAxis: {
            type: 'value',
            boundaryGap: [0, 0.01],
            splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } },
            axisLabel: { color: '#94a3b8' }
        },
        yAxis: {
            type: 'category',
            data: inefficientExpenses.map(e => e.name),
            axisLabel: { color: '#94a3b8', fontSize: 12 }
        },
        series: [
            {
                name: 'Gasto Mensual ($)',
                type: 'bar',
                data: inefficientExpenses.map(e => ({
                    value: e.amount,
                    itemStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 1, y2: 0,
                            colorStops: [{ offset: 0, color: '#ef4444' }, { offset: 1, color: '#f97316' }]
                        },
                        borderRadius: [0, 4, 4, 0]
                    }
                }))
            }
        ]
    };

    // Opportunity Cost calculation based on the totalWasted
    const years = [10, 20, 30];
    const interestRate = 0.08; // 8%

    const futureValues = years.map(year => {
        const n = year * 12;
        const r = interestRate / 12;
        return totalWasted * (((Math.pow(1 + r, n) - 1) / r) * (1 + r));
    });

    const opportunityOption = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            formatter: (params: any) => {
                const val = params[0];
                return `En ${val.name}:<br/><strong style="color: #c084fc">$${val.value.toLocaleString('en-US', {maximumFractionDigits:0})}</strong>`;
            }
        },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
        xAxis: {
            type: 'category',
            data: ['10 Años', '20 Años', '30 Años'],
            axisLabel: { color: '#94a3b8' },
            axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } }
        },
        yAxis: {
            type: 'value',
            splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)', type: 'dashed' } },
            axisLabel: { 
                color: '#94a3b8',
                formatter: (value: number) => `$${value/1000}k`
            }
        },
        series: [
            {
                data: futureValues,
                type: 'bar',
                barWidth: '40%',
                itemStyle: {
                    color: {
                        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [{ offset: 0, color: '#c084fc' }, { offset: 1, color: '#9333ea' }]
                    },
                    borderRadius: [8, 8, 0, 0]
                },
                label: {
                    show: true,
                    position: 'top',
                    color: '#e9d5ff',
                    formatter: (p: any) => `$${(p.value/1000).toFixed(1)}k`
                }
            }
        ]
    };

    return (
        <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl shadow-xl hover:shadow-2xl hover:border-slate-700 transition-all duration-300 overflow-hidden flex flex-col h-full">
            <div className="p-6 border-b border-white/5 flex justify-between items-center bg-gradient-to-r from-red-500/10 to-purple-500/10">
                <div>
                   <h2 className="text-xl font-bold font-sans text-white flex items-center gap-2">
                       <Smile className="text-yellow-400" size={24} />
                       ROI Emocional & Costo de Oportunidad
                   </h2>
                   <p className="text-sm text-slate-400 mt-1">
                       Impacto presente y futuro de los gastos de baja felicidad (&lt; 4)
                   </p>
                </div>
                <div className="bg-red-500/10 border border-red-500/20 px-4 py-2 rounded-xl flex items-center gap-3">
                    <div className="flex flex-col items-end">
                       <span className="text-xs text-red-300 uppercase tracking-wider font-semibold">Gasto Ineficiente</span>
                       <span className="text-red-400 font-bold text-lg">${totalWasted.toFixed(2)} / mes</span>
                    </div>
                    <TrendingDown className="text-red-400" size={24} />
                </div>
            </div>

            <div className="flex-1 grid grid-cols-1 md:grid-cols-2 p-6 gap-8">
                {/* Left Side: Happiness Breakdown */}
                <div className="flex flex-col">
                    <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
                        Desglose Mensual
                    </h3>
                    <div className="flex-1 min-h-[200px]">
                        <ReactECharts option={happinessOption} style={{ height: '100%', width: '100%' }} />
                    </div>
                </div>

                {/* Right Side: Opportunity Cost */}
                <div className="flex flex-col">
                    <div className="flex items-center gap-2 mb-4">
                        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                            Proyección de Inversión (8% anual)
                        </h3>
                        <Clock className="text-purple-400" size={16} />
                    </div>
                    
                    <div className="flex-1 min-h-[200px]">
                        <ReactECharts option={opportunityOption} style={{ height: '100%', width: '100%' }} />
                    </div>
                    
                    <div className="mt-4 p-4 bg-purple-500/10 border border-purple-500/20 rounded-xl text-center">
                        <p className="text-slate-300 text-sm">
                            Invirtiendo este monto ineficiente, acumularías <strong className="text-white text-base">${futureValues[2].toLocaleString('en-US', {maximumFractionDigits:0})}</strong> en 30 años.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};
