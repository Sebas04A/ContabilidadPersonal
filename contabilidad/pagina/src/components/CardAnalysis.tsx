import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import CardChart, { CardData } from './CardChart';
import { Calendar, ChevronRight, ChevronLeft, CreditCard, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useState } from 'react';

export default function CardAnalysis() {
    const [isPanelOpen, setIsPanelOpen] = useState(true);
    
    const { data, isLoading } = useQuery<CardData>({
        queryKey: ['cardAnalysis'],
        queryFn: async () => {
            const res = await axios.get('http://localhost:8000/api/variables/cards');
            return res.data;
        }
    });

    return (
        <div className="relative h-full w-full overflow-hidden bg-surface-950/50">
            {/* Chart Area - Full Screen */}
            <div className={`absolute inset-0 transition-all duration-500 ease-in-out ${isPanelOpen ? 'pr-80' : 'pr-0'}`}>
                <div className="h-full w-full p-6">
                    <div className="h-full w-full bg-surface-900/20 rounded-2xl border border-white/5 relative overflow-hidden">
                        {/* Chart Background Glow */}
                        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary-500/5 rounded-full blur-[100px] pointer-events-none"></div>
                        
                        <CardChart data={data} isLoading={isLoading} />
                    </div>
                </div>
            </div>

            {/* Floating Toggle Button (Visible when closed) */}
            <button 
                onClick={() => setIsPanelOpen(!isPanelOpen)}
                className={`
                    absolute top-6 right-6 z-30 p-2 rounded-full bg-surface-800 border border-white/10 text-white shadow-xl hover:bg-surface-700 transition-all duration-300
                    ${isPanelOpen ? 'opacity-0 pointer-events-none scale-75' : 'opacity-100 pointer-events-auto scale-100'}
                `}
            >
                <ChevronLeft size={20} />
            </button>

            {/* Side Panel - Glass Overlay */}
            <div 
                className={`
                    absolute top-4 right-4 bottom-4 w-80 bg-surface-900/80 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl z-20 flex flex-col transition-all duration-500 ease-[cubic-bezier(0.23,1,0.32,1)]
                    ${isPanelOpen ? 'translate-x-0 opacity-100' : 'translate-x-[110%] opacity-0 pointer-events-none'}
                `}
            >
                {/* Panel Header */}
                <div className="p-5 border-b border-white/10 flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-primary-500/10 rounded-lg text-primary-400">
                            <CreditCard size={18} />
                        </div>
                        <h3 className="font-bold text-white text-sm">Estados de Cuenta</h3>
                    </div>
                    <button 
                        onClick={() => setIsPanelOpen(false)}
                        className="p-1.5 hover:bg-white/5 rounded-lg text-surface-400 hover:text-white transition-colors"
                    >
                        <ChevronRight size={18} />
                    </button>
                </div>

                {/* Panel Content (Scrollable) */}
                <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
                    {isLoading ? (
                        <div className="space-y-3">
                           {[1,2,3,4].map(i => (
                               <div key={i} className="h-28 bg-surface-800/50 rounded-xl animate-pulse border border-white/5" />
                           ))}
                        </div>
                    ) : (!data?.periods || data.periods.length === 0) ? (
                        <div className="h-full flex flex-col items-center justify-center text-center p-6 text-surface-500">
                            <div className="w-16 h-16 rounded-full bg-surface-800/50 flex items-center justify-center mb-4 border border-white/5">
                                <AlertCircle size={32} className="opacity-50" />
                            </div>
                            <p className="text-sm font-medium">No se encontraron estados de cuenta.</p>
                        </div>
                    ) : (
                        data.periods.slice().reverse().map((period, idx) => (
                            <div key={idx} className="group relative p-4 bg-surface-950/40 rounded-xl border border-white/5 hover:bg-surface-800/60 hover:border-primary-500/20 transition-all duration-200">
                                {/* Header Row */}
                                <div className="flex justify-between items-start mb-3">
                                    <div>
                                        <h4 className="font-bold text-white text-sm group-hover:text-primary-300 transition-colors">
                                            {period.period_name || 'Periodo Sin Nombre'}
                                        </h4>
                                        <div className="flex items-center gap-1.5 mt-1 text-[10px] text-surface-400 font-mono uppercase tracking-wide">
                                            <Calendar size={10} />
                                            {new Date(period.start_date).toLocaleDateString('es-ES', {month: 'short', year: '2-digit'})}
                                        </div>
                                    </div>
                                    <div className={`
                                        px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border flex items-center gap-1
                                        ${period.total_to_pay > 0.1 
                                            ? 'bg-red-500/10 text-red-400 border-red-500/20' 
                                            : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'}
                                    `}>
                                        {period.total_to_pay > 0.1 ? (
                                            <>Por Pagar</>
                                        ) : (
                                            <>
                                                <CheckCircle2 size={10} />
                                                Pagado
                                            </>
                                        )}
                                    </div>
                                </div>
                                
                                {/* Metrics Grid */}
                                <div className="grid grid-cols-2 gap-3 pt-3 border-t border-white/5">
                                    <div>
                                        <span className="text-[10px] text-surface-500 uppercase tracking-wider block mb-0.5">Consumo</span>
                                        <span className="text-surface-200 font-mono text-xs font-semibold block">
                                            ${period.consumption.toLocaleString('en-US', {minimumFractionDigits: 2})}
                                        </span>
                                    </div>
                                    <div className="text-right">
                                        <span className="text-[10px] text-surface-500 uppercase tracking-wider block mb-0.5">Total a Pagar</span>
                                        <span className={`font-mono text-sm font-bold block ${period.total_to_pay > 0.1 ? 'text-white' : 'text-emerald-400'}`}>
                                            ${period.total_to_pay.toLocaleString('en-US', {minimumFractionDigits: 2})}
                                        </span>
                                    </div>
                                </div>

                                {/* Hover Glow */}
                                <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-primary-500/0 via-primary-500/5 to-primary-500/0 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"></div>
                            </div>
                        ))
                    )}
                </div>

                {/* Footer Summary */}
                <div className="p-4 border-t border-white/10 bg-surface-950/50 backdrop-blur-sm rounded-b-2xl">
                    <div className="flex justify-between items-center text-xs">
                        <span className="text-surface-400 font-medium">Deuda Total Actual</span>
                        <span className="text-primary-400 font-mono font-bold text-sm">
                            ${data?.periods?.reduce((acc, p) => acc + p.total_to_pay, 0).toLocaleString('en-US', {minimumFractionDigits: 2}) || '0.00'}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}
