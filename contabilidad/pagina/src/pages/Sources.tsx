import { useState, useEffect, useMemo } from 'react';
import { api, BankProcessResponse } from '../services/api';
import { 
  Database, FolderInput, FileSpreadsheet, CheckCircle, AlertCircle, 
  Loader2, ArrowRight, CreditCard, Activity, Terminal, ShieldCheck, 
  FileText, ArrowUpRight, Check 
} from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';

export function Sources() {
  const [activeTab, setActiveTab] = useState<'bank' | 'card'>('bank');
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<BankProcessResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Clear results when switching tabs
  useEffect(() => {
    setResult(null);
    setError(null);
  }, [activeTab]);

  const validationErrors = useMemo(() => {
    if (!result?.validation_report) return [];
    const errors: any[] = [];
    const lines = result.validation_report.split('\n');
    
    let currentError: any = null;
    
    lines.forEach(line => {
      if (line.includes('Saldo incorrecto en')) {
        const dateMatch = line.match(/Saldo incorrecto en (.*?):/);
        const expMatch = line.match(/esperado (.*?),/);
        const foundMatch = line.match(/encontrado (.*)/);
        
        currentError = {
            date: dateMatch ? dateMatch[1] : 'Desconocida',
            expected: expMatch ? expMatch[1] : '?',
            found: foundMatch ? foundMatch[1] : '?'
        };
      } 
      else if (line.includes('DIFERENCIA') && currentError) {
        currentError.diff = line.replace('DIFERENCIA', '').trim();
        errors.push(currentError);
        currentError = null;
      }
    });
    return errors;
  }, [result?.validation_report]);

  const handleProcess = async () => {
    setProcessing(true);
    setError(null);
    setResult(null);
    try {
      const response = activeTab === 'bank' 
        ? await api.processBankSource() 
        : await api.processCardSource();
      setResult(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Error desconocido al procesar');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto px-6 md:px-12 pb-12 custom-scrollbar h-full bg-surface-950 relative">
      {/* Background Gradients */}
      <div className="fixed top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0">
         <div className="absolute top-[-20%] right-[-10%] w-[600px] h-[600px] bg-primary-600/10 rounded-full blur-[120px]" />
         <div className="absolute bottom-[-20%] left-[-10%] w-[500px] h-[500px] bg-secondary-600/10 rounded-full blur-[100px]" />
      </div>

      <div className="max-w-7xl mx-auto space-y-10 mt-10 relative z-10">
        
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-center gap-5">
            <div className="relative group">
              <div className="absolute -inset-1 bg-gradient-to-r from-primary-600 to-secondary-600 rounded-2xl blur opacity-25 group-hover:opacity-50 transition duration-500"></div>
              <div className="relative p-4 rounded-2xl bg-surface-900 border border-white/10 text-primary-400 shadow-xl">
                <Database size={32} />
              </div>
            </div>
            <div>
              <h1 className="text-4xl font-bold text-white tracking-tight">Gestión de Fuentes</h1>
              <p className="text-surface-400 mt-2 text-lg">Centraliza y procesa tus datos financieros.</p>
            </div>
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 items-start">
          
          {/* Left Column: Actions */}
          <div className="xl:col-span-2 space-y-8">
            
            {/* Tab Navigation */}
            <div className="bg-surface-900/40 backdrop-blur-md p-1.5 rounded-2xl inline-flex border border-white/5 shadow-inner">
              {[
                { id: 'bank', label: 'Cuentas Bancarias', icon: FolderInput },
                { id: 'card', label: 'Tarjetas de Crédito', icon: CreditCard }
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as 'bank' | 'card')}
                  className={`
                    relative px-6 py-3 rounded-xl text-sm font-bold flex items-center gap-2 transition-all duration-300
                    ${activeTab === tab.id 
                      ? 'text-white shadow-lg' 
                      : 'text-surface-400 hover:text-white hover:bg-white/5'}
                  `}
                >
                  {activeTab === tab.id && (
                    <div className="absolute inset-0 bg-gradient-to-br from-primary-600 to-primary-500 rounded-xl shadow-lg shadow-primary-500/25 -z-10 animate-in fade-in zoom-in-95 duration-200" />
                  )}
                  <tab.icon size={18} />
                  <span>{tab.label}</span>
                </button>
              ))}
            </div>

            {/* Action Card */}
            <div className="bg-surface-900/60 backdrop-blur-xl border border-white/10 rounded-[2rem] p-8 md:p-10 shadow-2xl relative overflow-hidden group">
              {/* Dynamic Background Effect */}
              <div className="absolute top-0 right-0 w-96 h-96 bg-primary-500/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 group-hover:bg-primary-500/10 transition-colors duration-700"></div>
              
              <div className="relative z-10">
                <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 mb-8">
                  <div>
                    <h2 className="text-2xl font-bold text-white mb-2">
                       {activeTab === 'bank' ? 'Procesamiento Bancario' : 'Estados de Cuenta'}
                    </h2>
                    <p className="text-surface-300 max-w-lg leading-relaxed">
                      {activeTab === 'bank' 
                        ? 'Unifica y limpia archivos Excel (.xlsx) desde la carpeta de entrada para generar un registro consolidado.'
                        : 'Procesa y normaliza los estados de cuenta de tarjetas (.xls), asignando identificadores únicos.'}
                    </p>
                  </div>
                  <div className="hidden md:block">
                     <div className="w-16 h-16 rounded-full bg-surface-800/50 border border-white/5 flex items-center justify-center">
                        {activeTab === 'bank' ? <FileSpreadsheet className="text-primary-400" size={32} /> : <Activity className="text-secondary-400" size={32} />}
                     </div>
                  </div>
                </div>

                <div className="bg-surface-950/30 rounded-2xl p-4 border border-white/5 mb-8 flex items-center gap-3">
                  <div className="p-2 bg-surface-800 rounded-lg text-surface-400">
                     <FolderInput size={18} />
                  </div>
                  <code className="text-primary-300 font-mono text-sm flex-1 truncate">
                    {activeTab === 'bank' ? 'data/nuevos/banca/*.xlsx' : 'data/nuevos/tarjeta/*.xls'}
                  </code>
                </div>

                <button
                  onClick={handleProcess}
                  disabled={processing}
                  className={`
                    w-full md:w-auto relative group/btn overflow-hidden rounded-2xl px-10 py-5 font-bold text-white shadow-xl transition-all duration-300
                    ${processing ? 'bg-surface-800 cursor-wait opacity-80' : 'bg-gradient-to-r from-primary-600 via-primary-500 to-primary-600 background-animate hover:scale-[1.02] hover:shadow-primary-500/30'}
                  `}
                >
                    <div className="absolute inset-0 bg-white/20 translate-y-full group-hover/btn:translate-y-0 transition-transform duration-300 rounded-2xl"></div>
                    <div className="relative flex items-center justify-center gap-3">
                        {processing ? (
                            <>
                                <Loader2 size={22} className="animate-spin" />
                                <span className="tracking-wide">Procesando Archivos...</span>
                            </>
                        ) : (
                            <>
                                <FileSpreadsheet size={22} />
                                <span className="tracking-wide text-lg">Iniciar Procesamiento</span>
                                <ArrowRight size={20} className="group-hover/btn:translate-x-1 transition-transform" />
                            </>
                        )}
                    </div>
                </button>
              </div>
            </div>

            {/* Results Section */}
            {(result || error) && (
              <div className="animate-in fade-in slide-in-from-bottom-8 duration-500 space-y-6">
                
                {/* Status Banner */}
                <div className={`
                  rounded-2xl p-6 border backdrop-blur-xl flex items-start gap-5
                  ${error 
                    ? 'bg-red-500/10 border-red-500/20 shadow-[0_0_30px_-10px_rgba(239,68,68,0.3)]' 
                    : 'bg-emerald-500/10 border-emerald-500/20 shadow-[0_0_30px_-10px_rgba(16,185,129,0.3)]'}
                `}>
                  <div className={`
                    p-3 rounded-xl shrink-0
                    ${error ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'}
                  `}>
                    {error ? <AlertCircle size={28} /> : <CheckCircle size={28} />}
                  </div>
                  <div>
                    <h3 className={`text-xl font-bold mb-1 ${error ? 'text-red-400' : 'text-emerald-400'}`}>
                      {error ? 'Error en el procesamiento' : 'Procesamiento Exitoso'}
                    </h3>
                    <p className={`text-sm ${error ? 'text-red-200/70' : 'text-emerald-200/70'}`}>
                      {error || result?.message}
                    </p>
                  </div>
                </div>

                {!error && result && (
                  <>
                    {/* Key Metrics */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="bg-surface-900/40 border border-white/5 rounded-2xl p-6 hover:border-white/10 transition-colors">
                          <div className="flex items-center gap-3 mb-2">
                             <div className="p-2 bg-primary-500/20 rounded-lg text-primary-400">
                               <Database size={18} />
                             </div>
                             <p className="text-surface-400 text-xs font-bold uppercase tracking-wider">Registros</p>
                          </div>
                          <p className="text-4xl font-bold text-white font-mono tracking-tight">{result.total_rows?.toLocaleString()}</p>
                        </div>
                        <div className="bg-surface-900/40 border border-white/5 rounded-2xl p-6 hover:border-white/10 transition-colors">
                          <div className="flex items-center gap-3 mb-2">
                             <div className="p-2 bg-secondary-500/20 rounded-lg text-secondary-400">
                               <FileSpreadsheet size={18} />
                             </div>
                             <p className="text-surface-400 text-xs font-bold uppercase tracking-wider">Archivos</p>
                          </div>
                          <p className="text-4xl font-bold text-white font-mono tracking-tight">{result.files_processed.length}</p>
                        </div>
                    </div>

                    {/* Chart Card */}
                    {result.chart_data && result.chart_data.length > 0 && (
                        <div className="bg-surface-900/60 backdrop-blur-xl border border-white/10 rounded-3xl p-8 shadow-xl">
                            <div className="flex items-center justify-between mb-8">
                                <div className="flex items-center gap-3">
                                    <div className="p-2 bg-surface-800 rounded-lg text-primary-400">
                                        <Activity size={20} />
                                    </div>
                                    <h3 className="text-xl font-bold text-white">Análisis de Datos</h3>
                                </div>
                                <div className="px-3 py-1 bg-surface-800/50 rounded-lg border border-white/5 text-xs font-mono text-surface-400">
                                    {result.date_range?.min?.split('T')[0]} — {result.date_range?.max?.split('T')[0]}
                                </div>
                            </div>
                            <div className="h-[350px] w-full">
                                <ReactECharts
                                    theme="dark"
                                    style={{ height: '100%', width: '100%' }}
                                    option={{
                                        backgroundColor: 'transparent',
                                        tooltip: {
                                            trigger: 'axis',
                                            backgroundColor: '#18181b',
                                            borderColor: '#27272a',
                                            textStyle: { color: '#ffffff' },
                                            padding: [10, 15]
                                        },
                                        grid: { top: 20, right: 30, bottom: 30, left: 60, containLabel: true },
                                        xAxis: {
                                            type: 'category',
                                            data: result.chart_data.map(d => d.date),
                                            axisLine: { show: false },
                                            axisTick: { show: false },
                                            axisLabel: { color: '#71717a', margin: 15 },
                                        },
                                        yAxis: {
                                            type: 'value',
                                            scale: true,
                                            splitLine: { lineStyle: { color: '#27272a', type: 'dashed' } },
                                            axisLabel: { color: '#71717a' }
                                        },
                                        series: activeTab === 'bank' ? [
                                            {
                                                name: 'Saldo',
                                                type: 'line',
                                                data: result.chart_data.map(d => d.saldo),
                                                smooth: true,
                                                showSymbol: false,
                                                lineStyle: { color: '#8b5cf6', width: 3 },
                                                areaStyle: {
                                                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                                        { offset: 0, color: 'rgba(139, 92, 246, 0.4)' },
                                                        { offset: 1, color: 'rgba(139, 92, 246, 0.0)' }
                                                    ])
                                                }
                                            }
                                        ] : [
                                            {
                                                name: 'Monto Diario',
                                                type: 'bar',
                                                data: result.chart_data.map(d => d.monto),
                                                itemStyle: { color: '#fb7185', borderRadius: [4, 4, 0, 0] },
                                                barMaxWidth: 20
                                            }
                                        ]
                                    }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Validation & Log Section */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Validation Report */}
                        <div className={`
                             rounded-3xl border overflow-hidden flex flex-col h-[500px]
                             ${validationErrors.length > 0 ? 'bg-surface-900/60 border-red-500/30' : 'bg-surface-900/60 border-emerald-500/20'}
                        `}>
                            <div className="p-6 border-b border-white/5 bg-surface-950/20 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <ShieldCheck size={20} className={validationErrors.length > 0 ? 'text-red-400' : 'text-emerald-400'} />
                                    <h3 className="font-bold text-white">Reporte de Validación</h3>
                                </div>
                                <span className={`px-2 py-1 rounded text-xs font-bold uppercase tracking-wider ${validationErrors.length > 0 ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
                                    {validationErrors.length > 0 ? 'Atención' : 'OK'}
                                </span>
                            </div>

                            <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-3">
                                {validationErrors.length === 0 ? (
                                    <div className="h-full flex flex-col items-center justify-center text-center p-8 text-surface-500">
                                        <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center mb-4">
                                            <Check size={32} className="text-emerald-500" />
                                        </div>
                                        <p className="text-lg font-medium text-emerald-200/80 mb-2">Todo en orden</p>
                                        <p className="text-sm max-w-xs">No se encontraron inconsistencias en los saldos procesados.</p>
                                    </div>
                                ) : (
                                    validationErrors.map((err, idx) => (
                                        <div key={idx} className="bg-surface-950/40 p-4 rounded-xl border border-red-500/10 hover:border-red-500/30 transition-all group">
                                            <div className="flex items-center justify-between mb-3">
                                                <div className="flex items-center gap-2">
                                                    <div className="w-2 h-2 rounded-full bg-red-500/50"></div>
                                                    <span className="text-xs text-red-300 font-mono">{err.date}</span>
                                                </div>
                                                <span className="text-xs font-bold text-red-400 bg-red-500/10 px-2 py-0.5 rounded">
                                                    Dif: {Number(err.diff).toFixed(2)}
                                                </span>
                                            </div>
                                            <div className="grid grid-cols-2 gap-4 text-sm">
                                                <div className="space-y-1">
                                                    <span className="text-[10px] uppercase text-surface-500 tracking-wider">Esperado</span>
                                                    <p className="font-mono text-emerald-400/90">{Number(err.expected).toFixed(2)}</p>
                                                </div>
                                                <div className="space-y-1">
                                                    <span className="text-[10px] uppercase text-surface-500 tracking-wider">Encontrado</span>
                                                    <p className="font-mono text-red-400/90">{Number(err.found).toFixed(2)}</p>
                                                </div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>

                        {/* Raw Log */}
                        <div className="rounded-3xl border border-white/10 bg-surface-950/50 overflow-hidden flex flex-col h-[500px]">
                             <div className="p-6 border-b border-white/5 bg-surface-950/20 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <Terminal size={20} className="text-surface-400" />
                                    <h3 className="font-bold text-white">Log del Sistema</h3>
                                </div>
                             </div>
                             <div className="flex-1 overflow-auto custom-scrollbar p-4 bg-[#0a0a0f]">
                                <pre className="text-xs font-mono text-surface-300 leading-relaxed whitespace-pre-wrap">
                                    {result.validation_report}
                                </pre>
                             </div>
                        </div>
                    </div>

                    {/* Compact File List */}
                    <div className="bg-surface-900/40 border border-white/5 rounded-2xl p-6">
                        <h4 className="text-white font-bold mb-4 flex items-center gap-2">
                             <FileText size={16} className="text-surface-400"/>
                             Archivos Integrados
                             <span className="text-xs font-normal text-surface-500 ml-2">({result.files_processed.length})</span>
                        </h4>
                        <div className="flex flex-wrap gap-2">
                            {result.files_processed.map((file, idx) => (
                                <span key={idx} className="px-3 py-1.5 rounded-lg bg-surface-800 border border-white/5 text-xs text-surface-300 flex items-center gap-2">
                                    {file}
                                </span>
                            ))}
                        </div>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Right Column: Info & Context */}
          <div className="xl:col-span-1 space-y-6">
            <div className="bg-surface-900/60 backdrop-blur-xl border border-white/10 rounded-3xl p-6 sticky top-8">
              <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                <Activity size={20} className="text-primary-500"/>
                Flujo de Datos
              </h3>
              
              <div className="space-y-8 relative">
                {/* Connecting Line */}
                <div className="absolute left-[19px] top-8 bottom-8 w-0.5 bg-gradient-to-b from-primary-500/50 to-surface-800"></div>

                <div className="relative flex gap-4 group">
                    <div className="w-10 h-10 rounded-full bg-surface-800 border-2 border-primary-500/50 flex items-center justify-center shrink-0 z-10 shadow-[0_0_15px_-5px_#8b5cf6]">
                        <FolderInput size={18} className="text-white" />
                    </div>
                    <div>
                        <h4 className="text-white font-bold text-sm">Entrada</h4>
                        <p className="text-sm text-surface-400 mt-1">
                            Archivos en <span className="text-primary-300">/data/nuevos</span>
                        </p>
                    </div>
                </div>

                <div className={`relative flex gap-4 transition-all duration-300 ${processing ? 'opacity-100 scale-105' : 'opacity-60'}`}>
                    <div className={`w-10 h-10 rounded-full border-2 flex items-center justify-center shrink-0 z-10 bg-surface-900 ${processing ? 'border-amber-500 shadow-[0_0_15px_-5px_#f59e0b]' : 'border-surface-700'}`}>
                        {processing ? <Loader2 size={18} className="text-amber-500 animate-spin" /> : <Activity size={18} className="text-surface-500" />}
                    </div>
                    <div>
                        <h4 className={`font-bold text-sm ${processing ? 'text-amber-400' : 'text-surface-400'}`}>Procesamiento</h4>
                        <p className="text-sm text-surface-500 mt-1">Limpieza, unificación y validación</p>
                    </div>
                </div>

                <div className="relative flex gap-4">
                     <div className="w-10 h-10 rounded-full bg-surface-800 border-2 border-emerald-500/30 flex items-center justify-center shrink-0 z-10">
                        <ArrowUpRight size={18} className="text-emerald-400" />
                    </div>
                    <div>
                        <h4 className="text-white font-bold text-sm">Salida</h4>
                        <p className="text-sm text-surface-400 mt-1">
                            Archivo unificado en <span className="text-emerald-400/80">/data/procesada</span>
                        </p>
                    </div>
                </div>
              </div>

              <div className="mt-8 pt-6 border-t border-white/5">
                <div className="p-4 rounded-xl bg-surface-800/50 border border-white/5">
                    <h5 className="text-xs font-bold text-surface-300 mb-2 uppercase tracking-wide">Nota Técnica</h5>
                    <p className="text-xs text-surface-400 leading-relaxed">
                        El sistema valida automáticamente que no haya discrepancias entre los movimientos y los saldos diarios reportados por el banco.
                    </p>
                </div>
              </div>

            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
