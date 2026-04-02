import React from 'react';
import { EmotionalRoiAnalyzer } from '../components/analytics/EmotionalRoiAnalyzer';
import { LifestyleCreepAuditor } from '../components/analytics/LifestyleCreepAuditor';
import { FreedomDaySimulator } from '../components/analytics/FreedomDaySimulator';
import { CategoryEfficiencyMap } from '../components/analytics/CategoryEfficiencyMap';
import { SurvivalBreakEven } from '../components/analytics/SurvivalBreakEven';
import { SROptimizer } from '../components/analytics/SROptimizer';
import { Sparkles } from 'lucide-react';

export const AdvancedAnalytics: React.FC = () => {
    return (
        <div className="flex-1 overflow-y-auto px-4 md:px-8 pb-12 custom-scrollbar">
            <div className="max-w-[1600px] mx-auto mt-8">
                
                {/* Header Section */}
                <div className="mb-10 relative">
                    <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 rounded-[2rem] blur-2xl opacity-20 -z-10"></div>
                    <div className="bg-slate-900/60 backdrop-blur-2xl border border-white/10 rounded-3xl p-8 shadow-2xl overflow-hidden relative">
                        {/* Decorative glow inside */}
                        <div className="absolute top-0 right-0 w-64 h-64 bg-white opacity-5 mix-blend-overlay rounded-full blur-3xl transform translate-x-1/2 -translate-y-1/2"></div>
                        
                        <div className="flex flex-col md:flex-row gap-6 justify-between items-center relative z-10">
                            <div className="flex-1">
                                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-bold tracking-widest uppercase mb-4">
                                    <Sparkles size={14} /> Insights Financieros
                                </div>
                                <h1 className="text-4xl md:text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-200 to-slate-400 tracking-tight leading-tight">
                                    Analíticas Avanzadas
                                </h1>
                                <p className="text-slate-400 mt-4 text-base md:text-lg max-w-2xl leading-relaxed">
                                    Indicadores financieros de nueva generación. Diagnostica tu salud financiera más allá del saldo bancario,
                                    evaluando tu <strong>ROI Emocional</strong> y proyectando tu <strong>Libertad Financiera</strong>.
                                </p>
                            </div>

                        </div>
                    </div>
                </div>

                {/* Dashboard Grid */}
                <div className="flex flex-col gap-8 animate-in fade-in slide-in-from-bottom-8 duration-700 fill-mode-both">
                    
                    {/* Row 1: Unified Module: Emotional ROI & Opportunity Cost (Full Width) */}
                    <div className="animate-in slide-in-from-bottom-4 delay-[100ms] fill-mode-both">
                        <EmotionalRoiAnalyzer />
                    </div>
                    
                    {/* Row 2: Freedom & Survival (Shared) */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                        <div className="animate-in slide-in-from-bottom-4 delay-[200ms] fill-mode-both h-full">
                            <FreedomDaySimulator />
                        </div>
                        <div className="animate-in slide-in-from-bottom-4 delay-[300ms] fill-mode-both h-full">
                            <SurvivalBreakEven />
                        </div>
                    </div>

                    {/* Row 3: Category Efficiency Map (Full Width) */}
                    <div className="animate-in slide-in-from-bottom-4 delay-[350ms] fill-mode-both">
                        <CategoryEfficiencyMap />
                    </div>

                    {/* Row 4: Lifestyle Creep (Full Width) */}
                    <div className="animate-in slide-in-from-bottom-4 delay-[400ms] fill-mode-both">
                        <LifestyleCreepAuditor />
                    </div>

                    {/* Row 4: SRI Optimizer (Full Width) */}
                    <div className="animate-in slide-in-from-bottom-4 delay-[500ms] fill-mode-both">
                        <SROptimizer />
                    </div>

                </div>

            </div>
        </div>
    );
};
