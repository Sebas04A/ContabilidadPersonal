import { useState, useEffect } from 'react';
import { DollarSign, Calendar, CheckCircle2, Clock, BarChart3 } from 'lucide-react';
import { investmentsApi, AccountInvestment, ChartData } from '../services/investments';
import PaymentCRUD from '../components/PaymentCRUD';
import InvestmentChart from '../components/InvestmentChart';

interface InvestmentAnalysisProps {
  onBack: () => void;
}

export default function InvestmentAnalysis({}: InvestmentAnalysisProps) {
  const [activeTab, setActiveTab] = useState<'iniciadas' | 'finalizadas'>('iniciadas');
  const [iniciadas, setIniciadas] = useState<AccountInvestment[]>([]);
  const [finalizadas, setFinalizadas] = useState<AccountInvestment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Chart state
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const [chartLoading, setChartLoading] = useState(true);

  useEffect(() => {
    fetchInvestments();
    fetchChartData();
  }, []);

  const fetchChartData = async () => {
    setChartLoading(true);
    try {
      const data = await investmentsApi.getChartData();
      setChartData(data);
    } catch (err) {
      console.error('Error fetching chart data:', err);
    } finally {
      setChartLoading(false);
    }
  };

  const fetchInvestments = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await investmentsApi.getFromAccounts();
      setIniciadas(data.iniciadas);
      setFinalizadas(data.finalizadas);
    } catch (err) {
      console.error('Error fetching investments:', err);
      setError('Error al cargar las inversiones');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' });
  };

  const currentList = activeTab === 'iniciadas' ? iniciadas : finalizadas;

  return (
    <div className="h-full flex flex-col bg-surface-950 overflow-hidden">
      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden gap-3 p-4">
        {/* Left Sidebar - Investment List */}
        <div className="w-72 flex flex-col bg-surface-900/50 backdrop-blur-xl rounded-xl border border-white/[0.06] shadow-lg shadow-black/20 overflow-hidden">
          {/* Tabs */}
          <div className="flex-shrink-0 flex gap-1.5 p-2.5 border-b border-white/[0.06]">
            <button
              onClick={() => setActiveTab('iniciadas')}
              className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                activeTab === 'iniciadas'
                  ? 'bg-gradient-to-br from-primary-600 to-primary-700 text-white shadow-md shadow-primary-900/30'
                  : 'text-surface-400 hover:text-surface-200 hover:bg-white/[0.04]'
              }`}
            >
              <Clock className="w-3.5 h-3.5" />
              <span>Iniciadas</span>
              <span className={`px-1.5 py-0.5 rounded-md text-xs font-semibold ${
                activeTab === 'iniciadas' 
                  ? 'bg-white/20 text-white' 
                  : 'bg-surface-800/80 text-surface-500'
              }`}>
                {iniciadas.length}
              </span>
            </button>
            <button
              onClick={() => setActiveTab('finalizadas')}
              className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                activeTab === 'finalizadas'
                  ? 'bg-gradient-to-br from-primary-600 to-primary-700 text-white shadow-md shadow-primary-900/30'
                  : 'text-surface-400 hover:text-surface-200 hover:bg-white/[0.04]'
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Finalizadas</span>
              <span className={`px-1.5 py-0.5 rounded-md text-xs font-semibold ${
                activeTab === 'finalizadas' 
                  ? 'bg-white/20 text-white' 
                  : 'bg-surface-800/80 text-surface-500'
              }`}>
                {finalizadas.length}
              </span>
            </button>
          </div>

          {/* Investment List */}
          <div className="flex-1 overflow-y-auto p-2 space-y-2">
            {loading ? (
              <div className="flex items-center justify-center h-full">
                <div className="flex flex-col items-center gap-3">
                  <div className="w-8 h-8 rounded-full border-2 border-primary-500 border-t-transparent animate-spin"></div>
                  <div className="text-surface-500 text-sm">Cargando...</div>
                </div>
              </div>
            ) : error ? (
              <div className="flex items-center justify-center h-full p-4">
                <div className="text-center">
                  <div className="text-red-400 text-sm mb-2">{error}</div>
                  <button 
                    onClick={fetchInvestments} 
                    className="text-xs text-primary-400 hover:text-primary-300 transition-colors"
                  >
                    Reintentar
                  </button>
                </div>
              </div>
            ) : currentList.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-surface-600 px-4">
                <DollarSign className="w-12 h-12 mb-3 opacity-30" />
                <p className="text-sm font-medium">No hay inversiones {activeTab}</p>
              </div>
            ) : (
              currentList.map((inv, idx) => (
                <div 
                  key={`${inv.fecha}-${idx}`}
                  className="group bg-surface-900/60 backdrop-blur-sm rounded-xl p-3.5 border border-white/[0.05] hover:border-primary-500/30 hover:bg-surface-800/70 hover:shadow-lg hover:shadow-primary-900/10 transition-all duration-200 hover:-translate-y-0.5"
                >
                  <div className="flex items-start gap-3">
                    <div className={`flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center transition-all ${
                      activeTab === 'iniciadas' 
                        ? 'bg-amber-500/10 text-amber-400 group-hover:bg-amber-500/15'
                        : 'bg-emerald-500/10 text-emerald-400 group-hover:bg-emerald-500/15'
                    }`}>
                      {activeTab === 'iniciadas' 
                        ? <Clock className="w-4 h-4" /> 
                        : <CheckCircle2 className="w-4 h-4" />
                      }
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-base font-semibold text-white">
                        {formatCurrency(Math.abs(inv.monto))}
                      </div>
                      <div className="flex items-center gap-1.5 text-xs text-surface-400 mt-0.5">
                        <Calendar className="w-3 h-3" />
                        {formatDate(inv.fecha)}
                      </div>
                    </div>
                  </div>

                  {/* Details for completed */}
                  {activeTab === 'finalizadas' && inv.tipo === 'finalizada' && (
                    <div className="mt-3 pt-3 border-t border-white/[0.06] space-y-1.5">
                      <div className="flex justify-between text-xs">
                        <span className="text-surface-500">Interés</span>
                        <span className="font-mono font-medium text-emerald-400">
                          +{formatCurrency(inv.interes || 0)}
                        </span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-surface-500">Impuesto</span>
                        <span className="font-mono font-medium text-surface-400">
                          -{formatCurrency(inv.impuesto || 0)}
                        </span>
                      </div>
                      <div className="flex justify-between text-xs pt-1.5 border-t border-white/[0.05]">
                        <span className="text-surface-300 font-medium">Total</span>
                        <span className="font-mono font-semibold text-primary-400">
                          {formatCurrency(inv.total || 0)}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Side - Chart & CRUD */}
        <div className="flex-1 flex flex-col gap-3 overflow-hidden">
          {/* Chart - Takes more height as requested */}
          <div className="h-[65%] flex flex-col bg-surface-900/50 backdrop-blur-xl rounded-xl border border-white/[0.06] shadow-lg shadow-black/20 p-5 overflow-hidden">
            <div className="flex-shrink-0 flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-gradient-to-br from-primary-500/15 to-primary-600/10 border border-primary-500/20">
                <BarChart3 className="w-4 h-4 text-primary-400" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Rendimiento de Inversiones</h3>
                <p className="text-xs text-surface-400 mt-0.5">Evolución temporal del capital</p>
              </div>
            </div>
            <div className="flex-1 overflow-hidden rounded-lg bg-surface-950/60 border border-white/[0.04] p-3">
              <InvestmentChart data={chartData} loading={chartLoading} />
            </div>
          </div>

          {/* CRUD - Takes remaining height */}
          <div className="flex-1 overflow-hidden rounded-xl shadow-lg shadow-black/20">
            <PaymentCRUD 
              groupType="fixed"
              onDataChange={fetchChartData}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
