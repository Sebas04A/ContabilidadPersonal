import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Target, AlertTriangle, TrendingUp, Info } from 'lucide-react';

export const LifestyleCreepAuditor: React.FC = () => {
    // Mock Data representing months
    const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    
    // Raw values to calculate percentages
    const rawIncome = [2000, 2050, 2100, 2150, 2200, 2250, 2300, 2320, 2350, 2400, 2450, 2500];
    const rawDesires = [400, 410, 425, 450, 480, 520, 500, 530, 550, 580, 600, 620];

    // Calculate Percentage Growth from month 0
    const incomeGrowth = rawIncome.map(val => ((val / rawIncome[0]) - 1) * 100);
    const desiresGrowth = rawDesires.map(val => ((val / rawDesires[0]) - 1) * 100);

    const isInflation = desiresGrowth[desiresGrowth.length - 1] > incomeGrowth[incomeGrowth.length - 1];

    const option = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            formatter: (params: any) => {
                let res = `<strong>${params[0].name}</strong><br/>`;
                params.forEach((p: any) => {
                    res += `${p.marker} ${p.seriesName}: <span style="font-weight:bold">${p.value.toFixed(1)}%</span><br/>`;
                });
                return res;
            },
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            textStyle: { color: '#f8fafc' }
        },
        legend: {
            data: ['Crecimiento de Ingresos', 'Crecimiento de Gastos en "Deseos"'],
            textStyle: { color: '#94a3b8', fontSize: 11 },
            top: 10,
            icon: 'rect'
        },
        grid: { left: '3%', right: '4%', bottom: '5%', top: '18%', containLabel: true },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: months,
            axisLabel: { color: '#64748b', fontSize: 10 },
            axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } }
        },
        yAxis: {
            type: 'value',
            axisLabel: { 
                color: '#64748b', 
                fontSize: 10,
                formatter: '{value}%'
            },
            splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
        },
        series: [
            {
                name: 'Crecimiento de Ingresos',
                type: 'line',
                data: incomeGrowth,
                smooth: true,
                showSymbol: false,
                lineStyle: { color: '#3b82f6', width: 2 },
                areaStyle: {
                    color: {
                        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [{ offset: 0, color: 'rgba(59, 130, 246, 0.2)' }, { offset: 1, color: 'rgba(59, 130, 246, 0)' }]
                    }
                }
            },
            {
                name: 'Crecimiento de Gastos en "Deseos"',
                type: 'line',
                data: desiresGrowth,
                smooth: true,
                showSymbol: false,
                lineStyle: { color: '#f97316', width: 3 },
                areaStyle: {
                    color: {
                        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [{ offset: 0, color: 'rgba(249, 115, 22, 0.3)' }, { offset: 1, color: 'rgba(249, 115, 22, 0)' }]
                    }
                }
            }
        ]
    };

    return (
        <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 p-6 rounded-2xl shadow-xl hover:shadow-2xl hover:border-slate-700 transition-all duration-300 relative overflow-hidden">
            {/* Header Style from Image */}
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-sm font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
                    <Target className="text-blue-400" size={18} />
                    Auditor de Lifestyle Creep
                </h2>
                
                {isInflation && (
                    <div className="bg-red-600/90 text-white text-[10px] font-black px-3 py-1 rounded flex items-center gap-2 uppercase tracking-tighter shadow-lg shadow-red-900/20">
                        <AlertTriangle size={12} fill="white" className="text-red-600" />
                        Alerta: Inflación
                    </div>
                )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
                {/* Main Chart Area */}
                <div className="lg:col-span-3 h-80 relative mt-2">
                    <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
                </div>

                {/* Growth Summary Side Panel */}
                <div className="flex flex-col justify-center gap-4 border-l border-white/5 pl-6">
                    <div className="space-y-1">
                        <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Crecimiento Ingresos</p>
                        <div className="flex items-center gap-2">
                            <span className="text-2xl font-black text-blue-400">+{incomeGrowth[incomeGrowth.length - 1].toFixed(0)}%</span>
                            <TrendingUp size={16} className="text-blue-500" />
                        </div>
                    </div>

                    <div className="space-y-1">
                        <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Crecimiento Lujos</p>
                        <div className="flex items-center gap-2">
                            <span className="text-2xl font-black text-orange-400">+{desiresGrowth[desiresGrowth.length - 1].toFixed(0)}%</span>
                            <TrendingUp size={16} className="text-orange-500" />
                        </div>
                    </div>

                    <div className="mt-4 pt-4 border-t border-white/5">
                        <div className="bg-orange-500/5 border border-orange-500/10 p-3 rounded-xl flex gap-3 items-start">
                             <Info className="text-orange-400 shrink-0 mt-0.5" size={14} />
                             <p className="text-[11px] text-slate-400 leading-relaxed font-medium">
                                Tus gastos en deseos crecen <strong className="text-orange-300">{(desiresGrowth[desiresGrowth.length - 1] / incomeGrowth[incomeGrowth.length - 1]).toFixed(1)}x</strong> más rápido que tus ingresos.
                             </p>
                        </div>
                    </div>
                    
                    <div className="text-center mt-2">
                         <p className="text-[9px] text-slate-500 italic">Datos normalizados base Ene = 0%</p>
                    </div>
                </div>
            </div>
        </div>
    );
};
