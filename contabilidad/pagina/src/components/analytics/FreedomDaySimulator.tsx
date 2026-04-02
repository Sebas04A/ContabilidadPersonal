import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Bird, ShieldAlert, Activity } from 'lucide-react';

export const FreedomDaySimulator: React.FC = () => {
    // Mock simulation data
    const monthsSurviving = 14.5;
    const confidenceLevel = 85;

    const gaugeOption = {
        series: [
            {
                type: 'gauge',
                startAngle: 180,
                endAngle: 0,
                center: ['50%', '75%'],
                radius: '100%',
                min: 0,
                max: 24,
                splitNumber: 8,
                axisLine: {
                    lineStyle: {
                        width: 15,
                        color: [
                            [0.25, '#ef4444'], // 0-6 months (Danger)
                            [0.5, '#eab308'],  // 6-12 months (Warning)
                            [1, '#10b981']     // 12-24+ months (Good)
                        ]
                    }
                },
                pointer: {
                    icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
                    length: '60%',
                    width: 8,
                    offsetCenter: [0, '-20%'],
                    itemStyle: { color: '#f8fafc' }
                },
                axisTick: { show: false },
                splitLine: { show: false },
                axisLabel: { color: '#94a3b8', fontSize: 10, distance: -30 },
                title: { offsetCenter: [0, '30%'], fontSize: 14, color: '#94a3b8' },
                detail: {
                    fontSize: 28,
                    offsetCenter: [0, '0%'],
                    valueAnimation: true,
                    formatter: '{value}',
                    color: '#f8fafc',
                    fontWeight: 'bold'
                },
                data: [{ value: monthsSurviving, name: 'Meses de Vida' }]
            }
        ]
    };

    return (
        <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 p-6 rounded-2xl shadow-xl hover:shadow-2xl hover:border-slate-700 transition-all duration-300 group">
            <div className="flex justify-between items-start mb-2">
                <div>
                    <h2 className="text-xl font-bold font-sans text-white flex items-center gap-2">
                        <Bird className="text-cyan-400" size={24} />
                        Día de Libertad
                    </h2>
                    <p className="text-sm text-slate-400 mt-1">Paz Mental: Días de vida basados en Patrimonio Líquido</p>
                </div>
            </div>

            <div className="h-44 w-full mb-4 relative -mt-4">
                <ReactECharts option={gaugeOption} style={{ height: '100%', width: '100%' }} />
            </div>

            <div className="bg-slate-800/80 rounded-xl p-4 border border-slate-700/50">
                <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                        <Activity size={16} className="text-cyan-400"/> Nivel de Confianza (Monte Carlo)
                    </span>
                    <span className="text-cyan-400 font-bold">{confidenceLevel}%</span>
                </div>
                <div className="h-2 w-full bg-slate-700 rounded-full overflow-hidden">
                    <div className="h-full bg-cyan-400 rounded-full" style={{ width: `${confidenceLevel}%` }}></div>
                </div>
                
                <div className="mt-4 pt-4 border-t border-slate-700/50">
                    <div className="flex items-start gap-3">
                        <div className="mt-1 bg-cyan-500/20 p-1.5 rounded-full">
                            <ShieldAlert className="text-cyan-400" size={16} />
                        </div>
                        <p className="text-sm text-slate-300 leading-relaxed">
                            Considerando inflación e imprevistos simulados, tendrías <strong className="text-white">14.5 meses</strong> de supervivencia asegurada si decides parar hoy de generar ingresos.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};
