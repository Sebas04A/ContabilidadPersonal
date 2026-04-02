
import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { DashboardChart } from './components/DashboardChart';
import { VariationsChart } from './components/VariationsChart';
import Variables from './pages/Variables';
import { Debts } from './pages/Debts';
import { Sources } from './pages/Sources';
import { DataExplorer } from './pages/DataExplorer';
import { Labeling } from './pages/Labeling';
import { MonthlyBudget } from './pages/MonthlyBudget';
import { AdvancedAnalytics } from './pages/AdvancedAnalytics';
import { LayoutDashboard, BarChart3, TrendingUp } from 'lucide-react';

function App() {
  const [currentView, setCurrentView] = useState('etiquetado');
  const [dashboardView, setDashboardView] = useState<'evolution' | 'variations'>('evolution');

  return (
    <div className="min-h-screen flex text-gray-100 overflow-hidden font-sans selection:bg-pink-500/30">
      <Sidebar currentView={currentView} onViewChange={setCurrentView} />

      <main className="flex-1 flex flex-col h-screen overflow-hidden relative bg-slate-950">
        
        {currentView === 'variables' ? (
          <Variables />
        ) : currentView === 'deudas' ? (
          <Debts />
        ) : currentView === 'dashboard' ? (
          <div className="flex-1 overflow-y-auto px-4 md:px-8 pb-8 custom-scrollbar">
             <div className="max-w-[1600px] mx-auto flex flex-col items-center mt-6 gap-8">
                 
                 {/* Dashboard Navigation */}
                 <div className="p-1.5 bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl flex items-center gap-1 shadow-2xl sticky top-4 z-50">
                    <button 
                        onClick={() => setDashboardView('evolution')}
                        className={`
                            flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-300 relative overflow-hidden group
                            ${dashboardView === 'evolution' 
                                ? 'text-white shadow-lg shadow-blue-500/25 scale-[1.02]' 
                                : 'text-slate-400 hover:text-white hover:bg-white/5'}
                        `}
                    >
                        {dashboardView === 'evolution' && (
                            <div className="absolute inset-0 bg-gradient-to-r from-blue-600 to-cyan-500 opacity-100 rounded-xl -z-10 animate-in fade-in zoom-in-95 duration-300"></div>
                        )}
                        <TrendingUp size={18} className={dashboardView === 'evolution' ? 'text-white' : ''} />
                        <span>Evolución</span>
                    </button>

                    <div className="w-px h-6 bg-white/10 mx-1"></div>

                    <button 
                        onClick={() => setDashboardView('variations')}
                        className={`
                            flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-300 relative overflow-hidden group
                            ${dashboardView === 'variations' 
                                ? 'text-white shadow-lg shadow-purple-500/25 scale-[1.02]' 
                                : 'text-slate-400 hover:text-white hover:bg-white/5'}
                        `}
                    >
                        {dashboardView === 'variations' && (
                            <div className="absolute inset-0 bg-gradient-to-r from-purple-600 to-pink-500 opacity-100 rounded-xl -z-10 animate-in fade-in zoom-in-95 duration-300"></div>
                        )}
                        <BarChart3 size={18} className={dashboardView === 'variations' ? 'text-white' : ''} />
                        <span>Variaciones</span>
                    </button>
                 </div>

                 {/* Content Area */}
                 <div className="w-full animate-in fade-in slide-in-from-bottom-4 duration-500 px-1">
                    {dashboardView === 'evolution' ? (
                        <DashboardChart />
                    ) : (
                        <VariationsChart />
                    )}
                 </div>

             </div>
          </div>
        ) : currentView === 'sources' ? (
          <Sources />
        ) : currentView === 'explorer' ? (
          <DataExplorer />
        ) : currentView === 'presupuesto' ? (
          <MonthlyBudget />
        ) : currentView === 'advanced' ? (
          <AdvancedAnalytics />
        ) : (
          <Labeling />
        )}
      </main>
    </div>
  );
}

export default App;
