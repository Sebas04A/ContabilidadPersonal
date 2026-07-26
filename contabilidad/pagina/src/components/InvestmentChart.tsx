import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import { ChartData } from '../services/investments';

interface InvestmentChartProps {
  data: ChartData | null;
  loading?: boolean;
}

export default function InvestmentChart({ data, loading }: InvestmentChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  // Initialize chart once
  useEffect(() => {
    if (!chartRef.current) return;

    // Initialize chart instance
    chartInstance.current = echarts.init(chartRef.current);

    // Handle resize
    const handleResize = () => {
      chartInstance.current?.resize();
    };

    window.addEventListener('resize', handleResize);

    // Cleanup on unmount
    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartInstance.current) {
        chartInstance.current.dispose();
        chartInstance.current = null;
      }
    };
  }, []); // Only run once on mount

  // Update chart when data or loading changes
  useEffect(() => {
    if (!chartInstance.current) return;

    // Handle loading state - Premium spinner
    if (loading) {
      chartInstance.current.showLoading('default', {
        text: 'Cargando datos...',
        color: '#8b5cf6',
        textColor: '#a78bfa',
        maskColor: 'rgba(9, 9, 11, 0.8)',
        fontSize: 14,
        fontWeight: '600',
        fontFamily: 'Outfit, Inter, sans-serif',
      });
      return;
    }

    chartInstance.current.hideLoading();

    if (!data || data.dates.length === 0) {
      chartInstance.current.setOption({
        title: {
          text: 'No hay datos disponibles',
          left: 'center',
          top: 'center',
          textStyle: {
            color: '#52525b',
            fontSize: 16,
            fontWeight: '500',
            fontFamily: 'Outfit, Inter, sans-serif',
          },
        },
      });
      return;
    }

    // Prepare series data with gradient fills - Balanced elegance
    const series: any[] = [
      {
        name: 'INVERSIÓN',
        type: 'line',
        data: data.inversion,
        smooth: true,
        smoothMonotone: 'x',
        lineStyle: {
          color: '#8b5cf6', // Violeta primary
          width: 3,
        },
        itemStyle: {
          color: '#8b5cf6',
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(139, 92, 246, 0.3)' },
            { offset: 1, color: 'rgba(139, 92, 246, 0.02)' }
          ])
        },
        showSymbol: false,
        emphasis: {
          focus: 'series',
          lineStyle: {
            width: 4,
            shadowBlur: 8,
            shadowColor: 'rgba(139, 92, 246, 0.4)',
          },
        },
      },
      {
        name: 'SALDO',
        type: 'line',
        data: data.saldo,
        smooth: true,
        smoothMonotone: 'x',
        lineStyle: {
          color: '#06b6d4', // Cyan - contraste visual
          width: 2.5,
        },
        itemStyle: {
          color: '#06b6d4',
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(6, 182, 212, 0.2)' },
            { offset: 1, color: 'rgba(6, 182, 212, 0.01)' }
          ])
        },
        symbol: 'circle',
        symbolSize: 5,
        showSymbol: false,
        emphasis: {
          focus: 'series',
          lineStyle: {
            width: 3.5,
            shadowBlur: 8,
            shadowColor: 'rgba(6, 182, 212, 0.4)',
          },
          showSymbol: true,
        },
      },
    ];

    // Add investment period markers - amber/gold for active periods
    data.investment_periods.forEach((period) => {
      const startIndex = data.dates.findIndex(d => d >= period.start_date);
      const endIndex = data.dates.findIndex(d => d >= period.end_date);
      
      if (startIndex !== -1) {
        const actualEndIndex = endIndex !== -1 ? endIndex : data.dates.length - 1;
        
        // Construct detailed name for tooltip
        const seriesName = period.note ? `${period.group_name}: ${period.note}` : period.group_name;
        
        series.push({
          name: seriesName,
          type: 'line',
          data: data.dates.map((_d, i) => {
            if (i >= startIndex && i <= actualEndIndex) {
              return period.amount;
            }
            return null;
          }),
          lineStyle: {
            color: '#fbbf24', // Amber/dorado - períodos activos
            width: 4,
            type: 'solid',
            shadowBlur: 6,
            shadowColor: 'rgba(251, 191, 36, 0.25)',
          },
          itemStyle: {
            color: '#fbbf24',
          },
          symbol: 'rect',
          symbolSize: [3, 13],
          showSymbol: true,
          symbolOffset: [0, 0],
          z: 10,
          emphasis: {
            lineStyle: {
              width: 5,
              shadowBlur: 10,
              shadowColor: 'rgba(251, 191, 36, 0.4)',
            },
          },
        });
      }
    });

    // Chart configuration - Premium dark theme
    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          crossStyle: {
            color: '#52525b',
            width: 1,
            type: 'dashed',
          },
          label: {
            backgroundColor: 'rgba(139, 92, 246, 0.9)',
            borderColor: 'rgba(167, 139, 250, 0.3)',
            borderWidth: 1,
            color: '#ffffff',
            fontFamily: 'Outfit, Inter, sans-serif',
            fontWeight: 600,
          },
        },
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(139, 92, 246, 0.2)',
        borderWidth: 1,
        textStyle: {
          color: '#fafafa',
          fontSize: 13,
          fontFamily: 'Outfit, Inter, sans-serif',
        },
        padding: [12, 16],
        extraCssText: 'backdrop-filter: blur(12px); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);',
        formatter: (params: any) => {
          if (!Array.isArray(params)) return '';
          
          const date = params[0].axisValue;
          const dateObj = new Date(date);
          const formattedDate = dateObj.toLocaleDateString('es-ES', { 
            day: '2-digit', 
            month: 'long', 
            year: 'numeric' 
          });
          
          let html = `<div style="font-weight: 700; margin-bottom: 12px; font-size: 14px; color: #ffffff; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px;">${formattedDate}</div>`;
          
          params.forEach((param: any) => {
            if (param.value !== null && param.value !== undefined) {
              const color = param.color;
              const value = param.value.toLocaleString('en-US', { 
                style: 'currency', 
                currency: 'USD',
                minimumFractionDigits: 2,
                maximumFractionDigits: 2 
              });
              
              const name = param.seriesName;
              
              // More strict logic: don't show generic 'Inversiones Activas' if we have specific ones
              // Actually we just updated the seriesName in previous step, so it should be correct now.
              
              html += `
                <div style="display: flex; align-items: center; justify-content: space-between; margin: 8px 0; gap: 24px;">
                  <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="display: inline-block; width: 12px; height: 12px; background-color: ${color}; border-radius: 3px; box-shadow: 0 0 8px ${color}40;"></span>
                    <span style="color: #d4d4d8; font-size: 12px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${name}</span>
                  </div>
                  <span style="font-weight: 700; color: #ffffff; font-family: 'SF Mono', 'Consolas', monospace; font-size: 13px;">${value}</span>
                </div>
              `;
            }
          });
          
          return html;
        },
      },
      legend: {
        type: 'scroll',
        data: ['INVERSIÓN', 'SALDO'], // Only show main lines in legend initially or let echarts handle it
        top: 15,
        textStyle: {
          color: '#a1a1aa',
          fontSize: 12,
          fontFamily: 'Outfit, Inter, sans-serif',
          fontWeight: 500,
        },
        itemWidth: 28,
        itemHeight: 16,
        itemGap: 20,
        icon: 'roundRect',
        selectedMode: true,
        pageIconColor: '#a1a1aa',
        pageIconInactiveColor: '#52525b',
        pageTextStyle: {
          color: '#a1a1aa'
        }
      },
      grid: {
        left: '70px',
        right: '40px',
        bottom: '80px',
        top: 60,
        containLabel: false,
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: data.dates,
        axisLabel: {
          color: '#71717a',
          fontSize: 11,
          fontFamily: 'Outfit, Inter, sans-serif',
          rotate: 0,
          interval: Math.floor(data.dates.length / 12),
          formatter: (value: string) => {
            const date = new Date(value);
            const month = date.toLocaleDateString('es-ES', { month: 'short' });
            const year = date.getFullYear();
            return `${month}\n${year}`;
          },
          margin: 12,
        },
        axisLine: {
          lineStyle: {
            color: '#27272a',
            width: 1,
          },
        },
        axisTick: {
          show: false,
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: '#18181b',
            type: 'dashed',
            width: 1,
          },
        },
      },
      yAxis: {
        type: 'value',
        name: 'Monto (USD)',
        nameLocation: 'middle',
        nameGap: 55,
        nameTextStyle: {
          color: '#71717a',
          fontSize: 13,
          fontWeight: 600,
          fontFamily: 'Outfit, Inter, sans-serif',
        },
        axisLabel: {
          color: '#71717a',
          fontSize: 11,
          fontFamily: 'SF Mono, Consolas, monospace',
          formatter: (value: number) => {
            if (value >= 1000) {
              return `$${(value / 1000).toFixed(0)}k`;
            }
            return `$${value.toFixed(0)}`;
          },
        },
        axisLine: {
          show: true,
          lineStyle: {
            color: '#27272a',
            width: 1,
          },
        },
        axisTick: {
          show: false,
        },
        splitLine: {
          lineStyle: {
            color: '#18181b',
            type: 'solid',
            width: 1,
          },
        },
      },
      dataZoom: [
        {
          type: 'inside',
          start: 70,
          end: 100,
          zoomOnMouseWheel: true,
          moveOnMouseMove: true,
          moveOnMouseWheel: false,
        },
        {
          type: 'slider',
          start: 70,
          end: 100,
          height: 28,
          bottom: 10,
          handleIcon: 'path://M10.7,11.9v-1.3H9.3v1.3c-4.9,0.3-8.8,4.4-8.8,9.4c0,5,3.9,9.1,8.8,9.4v1.3h1.3v-1.3c4.9-0.3,8.8-4.4,8.8-9.4C19.5,16.3,15.6,12.2,10.7,11.9z M13.3,24.4H6.7V23h6.6V24.4z M13.3,19.6H6.7v-1.4h6.6V19.6z',
          handleSize: '100%',
          handleStyle: {
            color: '#3f3f46',
            borderColor: '#52525b',
            borderWidth: 1,
          },
          moveHandleSize: 6,
          emphasis: {
            handleStyle: {
              color: '#52525b',
              borderColor: '#71717a',
            },
            handleLabel: { show: false },
          },
          dataBackground: {
            lineStyle: {
              color: '#27272a',
              width: 1,
            },
            areaStyle: {
              color: '#18181b',
            },
          },
          selectedDataBackground: {
            lineStyle: {
              color: '#52525b',
            },
            areaStyle: {
              color: '#27272a',
            },
          },
          fillerColor: 'rgba(139, 92, 246, 0.12)',
          borderColor: '#27272a',
          textStyle: {
            color: '#71717a',
            fontSize: 11,
            fontFamily: 'Outfit, Inter, sans-serif',
          },
        },
      ],
      series: series,
    };

    chartInstance.current.setOption(option, true);
  }, [data, loading]);

  return (
    <div 
      ref={chartRef} 
      className="w-full h-full"
      style={{ minHeight: '400px' }}
    />
  );
}
