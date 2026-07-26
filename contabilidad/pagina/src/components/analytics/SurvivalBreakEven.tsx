import React from 'react';
import { Flame, Info, ArrowRight } from 'lucide-react';

export const SurvivalBreakEven: React.FC = () => {
    // Mock Data
    const survivalExpenses = 650; // Rent, utilities, basic food
    const currentIncome = 1200;
    const progressPercentage = Math.min((survivalExpenses / currentIncome) * 100, 100);

    return (
        <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 p-6 rounded-2xl shadow-xl hover:shadow-2xl hover:border-slate-700 transition-all duration-300 group">
            <div className="flex justify-between items-start mb-6">
                <div>
                    <h2 className="text-xl font-bold font-sans text-white flex items-center gap-2">
                        <Flame className="text-orange-500" size={24} />
                        Punto de Equilibrio
                    </h2>
                    <p className="text-sm text-slate-400 mt-1">Burn Rate: Tu "Mínimo Vital" mensual</p>
                </div>
            </div>

            <div className="bg-slate-800/80 rounded-xl p-5 border border-slate-700/50 relative overflow-hidden mb-6">
                 <div className="absolute top-0 right-0 p-4 opacity-5">
                      <Flame size={120} />
                 </div>
                 
                 <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">Presupuesto de Supervivencia</p>
                 <div className="flex items-baseline gap-2 mb-4">
                     <span className="text-4xl font-extrabold text-white">${survivalExpenses}</span>
                     <span className="text-slate-500 font-medium">/ mes</span>
                 </div>

                 <div className="space-y-2 relative z-10">
                     <div className="flex justify-between text-xs font-medium text-slate-400">
                         <span>$0</span>
                         <span>${currentIncome} (Ingreso Actual)</span>
                     </div>
                     <div className="h-3 w-full bg-slate-700 rounded-full overflow-hidden flex">
                         <div className="h-full bg-gradient-to-r from-orange-400 to-red-500" style={{ width: `${progressPercentage}%` }}></div>
                         <div className="h-full bg-emerald-400/20 flex-1"></div>
                     </div>
                 </div>
            </div>

            <div className="mt-4 p-4 bg-orange-500/10 border border-orange-500/20 rounded-xl flex items-start gap-3">
                 <Info className="text-orange-400 shrink-0 mt-0.5" size={18} />
                 <p className="text-sm text-orange-200 leading-relaxed">
                     <strong className="text-white">Alerta de Emergencia:</strong> Si hoy te quedas sin trabajo, debes generar al menos <strong className="text-orange-400 font-bold">${survivalExpenses}</strong> exactos cada mes (arriendo, servicios y comida básica) para no morir de hambre.
                 </p>
            </div>
            
            <button className="mt-4 w-full flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 text-white text-sm font-medium py-2.5 rounded-lg border border-slate-600 transition-colors">
                Ver detalle de gastos obligatorios <ArrowRight size={16} />
            </button>
        </div>
    );
};
