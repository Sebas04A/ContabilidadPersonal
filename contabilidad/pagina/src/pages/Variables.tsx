import { useState } from 'react';
import PaymentCRUD from '../components/PaymentCRUD';
import InvestmentAnalysis from './InvestmentAnalysis';
import { Calculator, TrendingUp, CreditCard, Layers, Settings2, Sparkles } from 'lucide-react';
import CardAnalysis from '../components/CardAnalysis';

export default function Variables() {
  const [activeTab, setActiveTab] = useState<'variables' | 'inversiones' | 'tarjeta'>('variables');
  const [variablesSubTab, setVariablesSubTab] = useState<'fijos' | 'interpolados'>('fijos');

  const mainTabs = [
    { id: 'variables', label: 'Variables', icon: Layers },
    { id: 'inversiones', label: 'Inversiones', icon: TrendingUp },
    { id: 'tarjeta', label: 'Tarjetas', icon: CreditCard },
  ] as const;

  return (
    <div className="flex flex-col h-full bg-surface-950 relative overflow-hidden">
      {/* Background Gradients */}
      <div className="fixed top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0">
         <div className="absolute top-[-10%] left-[-5%] w-[600px] h-[600px] bg-primary-600/10 rounded-full blur-[120px]" />
         <div className="absolute bottom-[-10%] right-[-5%] w-[500px] h-[500px] bg-secondary-600/10 rounded-full blur-[100px]" />
      </div>

      <div className="flex flex-col h-full relative z-10">
        
        {/* HEADER SECTION */}
        <div className="shrink-0 px-6 md:px-8 py-6 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex items-center gap-5">
                <div className="relative group">
                    <div className="absolute -inset-0.5 bg-gradient-to-tr from-primary-500 to-secondary-500 rounded-2xl blur opacity-30 group-hover:opacity-60 transition duration-500"></div>
                    <div className="relative p-3.5 rounded-2xl bg-surface-900 border border-white/10 text-white shadow-2xl">
                        <Settings2 size={32} strokeWidth={1.5} />
                    </div>
                </div>
                <div>
                    <h1 className="text-3xl font-bold text-white tracking-tight">Configuración</h1>
                    <div className="flex items-center gap-2 mt-1">
                        <Sparkles size={12} className="text-primary-400" />
                        <p className="text-surface-400 text-sm font-medium">Variables, inversiones y tarjetas</p>
                    </div>
                </div>
            </div>

            {/* Navigation Tabs */}
            <div className="flex p-1.5 bg-surface-900/60 backdrop-blur-xl border border-white/10 rounded-xl shadow-lg">
              {mainTabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`
                      relative flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-bold transition-all duration-300
                      ${isActive ? 'text-white shadow-md' : 'text-surface-400 hover:text-white hover:bg-white/5'}
                    `}
                  >
                    {isActive && (
                        <div className="absolute inset-0 bg-surface-800 border border-white/5 rounded-lg -z-10 animate-in fade-in zoom-in-95 duration-200" />
                    )}
                    <Icon className={`w-4 h-4 ${isActive ? 'text-primary-400' : ''}`} />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>
        </div>

        {/* Sub-navigation for Variables */}
        {activeTab === 'variables' && (
           <div className="px-6 md:px-8 pb-4 shrink-0 animate-in slide-in-from-top-2 fade-in duration-300">
             <div className="flex items-center gap-4 p-2 bg-surface-900/30 border border-white/5 rounded-xl w-fit backdrop-blur-sm">
                <div className="flex items-center gap-2 px-3 text-xs font-semibold text-surface-500 uppercase tracking-wider border-r border-white/5 pr-4">
                    <Calculator size={14} />
                    <span>Modo</span>
                </div>
                <div className="flex gap-1">
                    <button
                        onClick={() => setVariablesSubTab('fijos')}
                        className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${variablesSubTab === 'fijos' ? 'bg-primary-500/20 text-primary-300 border border-primary-500/30' : 'text-surface-400 hover:text-white hover:bg-white/5'}`}
                    >
                        Fijos
                    </button>
                    <button
                        onClick={() => setVariablesSubTab('interpolados')}
                        className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${variablesSubTab === 'interpolados' ? 'bg-primary-500/20 text-primary-300 border border-primary-500/30' : 'text-surface-400 hover:text-white hover:bg-white/5'}`}
                    >
                        Interpolados
                    </button>
                </div>
             </div>
           </div>
        )}

        {/* Content Area */}
        <div className="flex-1 overflow-hidden relative p-0 md:px-8 md:pb-8">
           <div className="h-full w-full bg-surface-900/20 border border-white/5 backdrop-blur-sm md:rounded-3xl overflow-hidden shadow-2xl relative">
              {activeTab === 'variables' && (
                <PaymentCRUD groupType={variablesSubTab === 'fijos' ? 'fixed' : 'interpolated'} />
              )}
              
              {activeTab === 'inversiones' && (
                <InvestmentAnalysis onBack={() => setActiveTab('variables')} />
              )}

              {activeTab === 'tarjeta' && (
                 <CardAnalysis />
              )}
           </div>
        </div>
      </div>
    </div>
  );
}
