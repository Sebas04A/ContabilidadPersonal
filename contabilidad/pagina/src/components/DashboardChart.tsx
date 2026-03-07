import { useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { useDashboardChartData } from '../hooks/useDashboard';
import { Loader2, AlertCircle, MousePointerClick, Activity, TrendingUp, Layers } from 'lucide-react';
import { ChartAnalysis, Curve } from './ChartAnalysis';
import type { EChartsOption } from 'echarts';

export function DashboardChart() {
  const { data: chartData, isLoading, isError, error } = useDashboardChartData();
  const [curves, setCurves] = useState<Curve[]>([]);
  const [tempPoint, setTempPoint] = useState<{date: string, value: number} | null>(null);
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [smoothness, setSmoothness] = useState(0.4);
  const [windowSize, setWindowSize] = useState(1);

  const allSeriesNames = ['Variación Neta', 'Patrimonio Neto', 'Saldo Banco', 'Saldo (Sin Inv)', 'Deuda Tarjeta', 'Deuda Acumulada', 'Pagos Fijos', 'Interpolaciones'];
  const [selectedSeries, setSelectedSeries] = useState<Record<string, boolean>>({
      'Variación Neta': true,
      'Patrimonio Neto': true,
      'Saldo Banco': false,
      'Saldo (Sin Inv)': true,
      'Deuda Tarjeta': true,
      'Deuda Acumulada': true,
      'Pagos Fijos': false,
      'Interpolaciones': true
  });

  const toggleAllSeries = () => {
    // Check if any is visible
    const someVisible = Object.values(selectedSeries).some(v => v);
    // If some are visible, turn all off. If none are visible, turn all on.
    const targetState = !someVisible;
    
    const newSelection: Record<string, boolean> = {};
    allSeriesNames.forEach(name => {
        newSelection[name] = targetState;
    });
    setSelectedSeries(newSelection);
  };

  const handleLegendSelectChange = (e: any) => {
    setSelectedSeries(e.selected);
  };

  const smoothedData = useMemo(() => {
    if (!chartData || !chartData.data) return [];
    if (windowSize === 1) return chartData.data;

    const keys = ['total', 'saldo', 'saldo_sin_inversion', 'tarjeta', 'deuda_acumulada', 'pagos_fijos', 'interpolado'];
    return chartData.data.map((item: any, index: number, array: any[]) => {
      const start = Math.max(0, index - windowSize + 1);
      const slice = array.slice(start, index + 1);
      const newItem = { ...item };
      
      keys.forEach(key => {
        const sum = slice.reduce((acc: number, curr: any) => acc + (typeof curr[key] === 'number' ? curr[key] : 0), 0);
        newItem[key] = sum / slice.length;
      });
      return newItem;
    });
  }, [chartData, windowSize]);

  if (isLoading) {
    return (
      <div className="w-full h-[600px] flex items-center justify-center">
        <Loader2 className="animate-spin text-blue-500" size={48} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="w-full h-[600px] flex flex-col items-center justify-center text-red-400">
        <AlertCircle size={48} className="mb-4" />
        <p>Error cargando datos del gráfico: {(error as Error).message}</p>
      </div>
    );
  }

  if (!chartData || !chartData.data || chartData.data.length === 0) {
    return (
      <div className="w-full h-[600px] flex items-center justify-center text-gray-500">
        No hay datos disponibles para mostrar.
      </div>
    );
  }

  const { data, highlighted_days } = chartData;
  const dates = data.map((item: any) => item.date);

  // Use smoothedData for interaction lookups too? 
  // Probably better to use raw data for clicks to get exact dates, 
  // but if the line is smoothed, the user might expect the value on the line.
  // Let's keep interaction on raw data or find the closest date.
  // Actually, for slopes, we want REAL endpoints, not averaged ones.
  // So we keep 'data' for click lookup, but use 'smoothedData' for display series.
  
  const onChartClick = (params: any) => {
    if (!isSelectionMode) return;
    if (!params || !params.name) return;
    
    const date = params.name;
    const pointData = data.find((d: any) => d.date === date);
    if (!pointData) return;
    
    const value = pointData.total; 
    const clickedPoint = { date, value };

    if (!tempPoint) {
        setTempPoint(clickedPoint);
    } else {
        const newCurve: Curve = {
            id: crypto.randomUUID(),
            start: new Date(tempPoint.date) < new Date(date) ? tempPoint : clickedPoint,
            end: new Date(tempPoint.date) < new Date(date) ? clickedPoint : tempPoint
        };
        
        setCurves(prev => [...prev, newCurve]);
        setTempPoint(null); 
    }
  };

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: 'Inter, sans-serif' },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: '#334155',
      textStyle: { color: '#f8fafc' },
      axisPointer: { 
        type: 'cross', 
        label: { backgroundColor: '#334155' },
        lineStyle: { color: '#94a3b8', type: 'dashed' }
      },
      formatter: function (params: any) {
        let tooltip = `<div class="font-bold mb-2">${params[0].axisValueLabel}</div>`;
        params.forEach((param: any) => {
          const value = typeof param.value === 'number' ? param.value.toFixed(2) : param.value;
          const color = param.color;
          tooltip += `<div class="flex items-center justify-between gap-4 text-sm">
            <span class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full" style="background-color: ${color}"></span>
              ${param.seriesName}
            </span>
            <span class="font-mono font-medium">$${value}</span>
          </div>`;
        });
        return tooltip;
      }
    },
    toolbox: {
      feature: {
        dataZoom: {
          yAxisIndex: 'none',
          title: { zoom: 'Zoom', back: 'Restaurar' }
        },
        magicType: { type: ['line', 'bar'], title: { line: 'Línea', bar: 'Barra' } },
        restore: { title: 'Restaurar' },
        saveAsImage: { title: 'Guardar Imagen' }
      },
      iconStyle: {
        borderColor: '#94a3b8'
      },
      right: 20,
      top: 0
    },
    dataZoom: [
      {
        type: 'inside',
        start: 50, // Start zoomed in a bit on the recent data
        end: 100
      },
      {
        start: 0,
        end: 100,
        handleIcon: 'path://M10.7,11.9v-1.3H9.3v1.3c-4.9,0.3-8.8,4.4-8.8,9.4c0,5,3.9,9.1,8.8,9.4v1.3h1.3v-1.3c4.9-0.3,8.8-4.4,8.8-9.4C19.5,16.3,15.6,12.2,10.7,11.9z M13.3,24.4H6.7V23h6.6V24.4z M13.3,19.6H6.7v-1.4h6.6V19.6z',
        handleSize: '80%',
        handleStyle: {
          color: '#fff',
          shadowBlur: 3,
          shadowColor: 'rgba(0, 0, 0, 0.6)',
          shadowOffsetX: 2,
          shadowOffsetY: 2
        },
        textStyle: { color: '#94a3b8' },
        borderColor: '#334155',
        fillerColor: 'rgba(59, 130, 246, 0.2)'
      }
    ],
    legend: {
      data: allSeriesNames,
      selected: selectedSeries,
      textStyle: { color: '#e2e8f0' },
      bottom: 0,
      padding: [20, 0, 0, 0],
      icon: 'roundRect'
    },
    grid: {
      left: '2%',
      right: '2%',
      bottom: '15%',
      top: '12%',
      containLabel: true,
      borderColor: '#334155'
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#475569' } },
      axisLabel: { 
        color: '#94a3b8',
        formatter: (value: string) => new Date(value).toLocaleDateString('es-ES', { month: 'short', year: '2-digit' })
      },
      axisTick: { alignWithLabel: true }
    },
    yAxis: [
      {
        type: 'value',
        name: 'Variación',
        position: 'left',
        axisLine: { show: false },
        axisLabel: { color: '#64748b', formatter: '${value}' },
        splitLine: { show: false }
      },
      {
        type: 'value',
        position: 'right',
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: '#334155', type: 'dashed', opacity: 0.3 } },
        axisLabel: { color: '#94a3b8', formatter: '${value}' },
        scale: true
      }
    ],
    series: [
      {
        name: 'Variación Neta',
        type: 'bar',
        yAxisIndex: 0,
        data: data.map((item: any) => item.diff_total),
        itemStyle: { 
            color: (params: any) => {
                const val = typeof params.value === 'number' ? params.value : 0;
                return val >= 0 ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)';
            },
            borderRadius: [2, 2, 0, 0]
        },
        barMaxWidth: 10,
        z: 1
      },
      {
        name: 'Patrimonio Neto',
        type: 'line',
        yAxisIndex: 1,
        data: smoothedData.map((item: any) => item.total),
        smooth: smoothness,
        showSymbol: false,
        symbolSize: 8,
        lineStyle: { width: 4, shadowColor: 'rgba(239, 68, 68, 0.5)', shadowBlur: 10 }, 
        itemStyle: { color: '#ef4444' }, // Red
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(239, 68, 68, 0.2)' },
              { offset: 1, color: 'rgba(239, 68, 68, 0)' }
            ]
          }
        },
        z: 10
      },
      {
        name: 'Saldo Banco',
        type: 'line',
        yAxisIndex: 1,
        data: smoothedData.map((item: any) => item.saldo),
        smooth: smoothness,
        showSymbol: false,
        lineStyle: { width: 2, type: 'dashed' }, 
        itemStyle: { color: '#64748b' }, // Slate
        z: 5
      },
      {
        name: 'Saldo (Sin Inv)',
        type: 'line',
        yAxisIndex: 1,
        data: smoothedData.map((item: any) => item.saldo_sin_inversion),
        smooth: smoothness,
        showSymbol: false,
        lineStyle: { width: 3 }, 
        itemStyle: { color: '#22c55e' }, // Green
        z: 8
      },
      {
        name: 'Deuda Tarjeta',
        type: 'line',
        yAxisIndex: 1,
        data: smoothedData.map((item: any) => item.tarjeta),
        smooth: smoothness,
        showSymbol: false,
        lineStyle: { width: 2 }, 
        itemStyle: { color: '#3b82f6' }, // Blue
        z: 6
      },
      {
        name: 'Deuda Acumulada',
        type: 'line',
        yAxisIndex: 1,
        data: smoothedData.map((item: any) => item.deuda_acumulada),
        smooth: smoothness,
        showSymbol: false,
        lineStyle: { width: 3 }, 
        itemStyle: { color: '#8b5cf6' }, // Violet
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(139, 92, 246, 0.2)' },
              { offset: 1, color: 'rgba(139, 92, 246, 0)' }
            ]
          }
        },
        z: 7
      },
       {
        name: 'Pagos Fijos',
        type: 'line',
        yAxisIndex: 1,
        data: smoothedData.map((item: any) => item.pagos_fijos),
        smooth: smoothness,
        showSymbol: false,
        lineStyle: { width: 2, type: 'dotted' }, 
        itemStyle: { color: '#a855f7' }, // Purple
        z: 4
      },
      {
        name: 'Interpolaciones',
        type: 'line',
        yAxisIndex: 1,
        data: smoothedData.map((item: any) => item.interpolado),
        smooth: smoothness,
        showSymbol: false,
        lineStyle: { width: 2, type: 'dashed' }, 
        itemStyle: { color: '#f97316' }, // Orange
        z: 4
      }
    ]

  };

  // Add markLines logic
  let markLineData: any[] = [];
  let markPointData: any[] = [];
  
  // 1. Highlighted Days
  if (highlighted_days && highlighted_days.length > 0) {
     highlighted_days.forEach((day: string) => {
         markLineData.push({ 
             xAxis: day, 
             label: { formatter: '!', position: 'end', color: '#ef4444' }, 
             lineStyle: { color: '#ef4444', type: 'dotted', width: 2 } 
         });
     });
  }

  // 2. Slope Analysis Lines (Curves)
  if (curves && curves.length > 0) {
      curves.forEach((curve: Curve) => {
        // Arrow Line
        markLineData.push([
                { coord: [curve.start.date, curve.start.value], symbol: 'circle', symbolSize: 6 },
                { 
                    coord: [curve.end.date, curve.end.value], 
                    symbol: 'arrow' 
                }
        ]);
      });
  }

  // 3. Temp Point (Selection in progress)
  if (tempPoint) {
       // Use markPoint for dots!
       markPointData.push({ 
           coord: [tempPoint.date, tempPoint.value], 
           symbol: 'circle',
           symbolSize: 8,
           itemStyle: { color: '#3b82f6', borderColor: '#fff', borderWidth: 2 },
           label: { show: true, formatter: 'Fin?', position: 'top', color: '#fff', backgroundColor: 'rgba(59, 130, 246, 0.8)', padding: [2, 4], borderRadius: 4 }
       });
  }

  // Inject into series
  if (option.series && Array.isArray(option.series)) {
      const targetSeries = option.series[1] as any;
      
      targetSeries.markLine = {
          data: markLineData,
          symbol: ['none', 'none'],
          animation: false,
          lineStyle: { color: '#fbbf24', width: 2 }
      };

      targetSeries.markPoint = {
          data: markPointData,
          symbol: 'circle',
          label: { show: false }
      };
  }


  return (
    <>
      <div className="w-full bg-slate-900/50 p-6 rounded-3xl border border-white/10 shadow-xl backdrop-blur-xl relative">
        <div className="flex flex-col md:flex-row items-center justify-between mb-6 gap-4">
            <h3 className="text-xl font-bold text-white flex items-center gap-3">
            <span className="w-2 h-8 bg-gradient-to-b from-blue-500 to-green-500 rounded-full"></span>
            Evolución Financiera
            </h3>

            {/* Selection Toggle */}
            <div className="flex items-center gap-4">
               <div className="flex items-center gap-2 bg-white/5 border border-white/10 px-3 py-2 rounded-xl">
                 <Activity size={16} className="text-gray-400" />
                 <div className="flex flex-col gap-1">
                    <div className="flex justify-between text-[10px] text-gray-500 uppercase font-bold tracking-wider">
                        <span>Curva</span>
                        <span>{smoothness}</span>
                    </div>
                    <input 
                    type="range" 
                    min="0" 
                    max="1" 
                    step="0.1" 
                    value={smoothness} 
                    onChange={(e) => setSmoothness(parseFloat(e.target.value))}
                    className="w-20 h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                    title="Curvatura Visual"
                    />
                 </div>
               </div>

                <div className="flex items-center gap-2 bg-white/5 border border-white/10 px-3 py-2 rounded-xl">
                 <TrendingUp size={16} className="text-gray-400" />
                 <div className="flex flex-col gap-1">
                    <div className="flex justify-between text-[10px] text-gray-500 uppercase font-bold tracking-wider">
                        <span>Tendencia</span>
                        <span>{windowSize}d</span>
                    </div>
                    <input 
                    type="range" 
                    min="1" 
                    max="30" 
                    step="1" 
                    value={windowSize} 
                    onChange={(e) => setWindowSize(parseInt(e.target.value))}
                    className="w-20 h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-violet-500"
                    title="Suavizado de Datos (Media Móvil)"
                    />
                 </div>
               </div>

               <button 
                  onClick={toggleAllSeries}
                  className="p-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-gray-400 hover:text-white transition-colors"
                  title={Object.values(selectedSeries).some(v => v) ? "Ocultar Todo" : "Mostrar Todo"}
               >
                  <Layers size={18} />
               </button>

                <button 
                    onClick={() => {
                        setIsSelectionMode(!isSelectionMode);
                        setTempPoint(null); 
                    }}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl border transition-all text-sm font-medium
                        ${isSelectionMode 
                            ? 'bg-blue-500/20 border-blue-500 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.5)]' 
                            : 'bg-white/5 border-white/10 text-gray-400 hover:text-white hover:bg-white/10'}
                    `}
                >
                    <MousePointerClick size={18} />
                    {isSelectionMode ? 'Modo Selección Activo' : 'Analizar Pendientes'}
                </button>
            </div>
        </div>
        
        <div className="w-full h-[600px]">
          <ReactECharts 
            option={option} 
            style={{ height: '100%', width: '100%' }}
            theme="dark"
            onEvents={{ 
                click: onChartClick,
                legendselectchanged: handleLegendSelectChange
            }}
          />
        </div>
      </div>

      <ChartAnalysis 
        curves={curves} 
        onRemove={(id) => setCurves(prev => prev.filter(c => c.id !== id))} 
      />
    </>
  );
}

