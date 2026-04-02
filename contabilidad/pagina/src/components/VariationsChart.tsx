import React, { useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { useVariations } from '../hooks/useDashboard'
import { Loader2, AlertCircle, List, BarChart2, Calendar, X } from 'lucide-react'
import type { EChartsOption } from 'echarts'
import { TransactionDriver, ComponentType, api } from '../services/api'

interface Props {
    className?: string
}

// Helper to classify a driver into a specific component type
// const classifyDriver = (d: TransactionDriver): ComponentType => {
//     if (d.source === 'debt') return 'debt'; // From Supabase Debts

//     // Explicit Fixed Flag
//     if (d.source === 'fixed' || (d as any).is_fixed) return 'fixed';

//     const cat = (d.description || '').toLowerCase();
//     const acc = (d.source || '').toLowerCase();

//     // Investment
//     if (cat.includes('inversi') || acc.includes('inversi')) return 'invest';

//     // Debt / Loans (Transactions that are debt-related)
//     if (cat.includes('préstamo') || cat.includes('deuda')) return 'debt';

//     // Card
//     if (acc.includes('tarjeta')) return 'card';

//     // Default to Bank/Cash
//     return 'bank';
// };

export function VariationsChart({ className }: Props) {
    const { data: variations, isLoading, isError, error } = useVariations()
    const isFirstRender = React.useRef(true)

    const getDailyDrivers = (dateStr: string): TransactionDriver[] => {
        // Use the top_drivers directly from the backend response
        if (!variations) return []
        // Match only YYYY-MM-DD
        const targetDate = dateStr.slice(0, 10)
        const day = variations.find(v => v.date === targetDate)
        return day ? day.top_drivers : []
    }

    const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
    const [detailMode, setDetailMode] = useState<'chart' | 'list'>('chart')
    const [dateFilter, setDateFilter] = useState<{ start: string; end: string }>({
        start: '',
        end: '',
    })

    const filteredVariations = React.useMemo(() => {
        if (!variations) return []
        let data = variations
        if (dateFilter.start) data = data.filter(v => v.date >= dateFilter.start)
        if (dateFilter.end) data = data.filter(v => v.date <= dateFilter.end)
        return data
    }, [variations, dateFilter])

    // Safe active index logic
    const activeIndex =
        selectedIndex !== null && selectedIndex < filteredVariations.length
            ? selectedIndex
            : Math.max(0, filteredVariations.length - 1)

    const echartsRef = React.useRef<any>(null)

    React.useEffect(() => {
        // Reset zoom only when filter changes
        if (echartsRef.current && (dateFilter.start || dateFilter.end)) {
            console.log('Resetting Zoom for filter')
            echartsRef.current.getEchartsInstance().dispatchAction({
                type: 'dataZoom',
                start: 0,
                end: 100,
            })
        }
    }, [dateFilter])

    React.useEffect(() => {
        if (variations && variations.length > 0) {
            isFirstRender.current = false
        }
    }, [variations])

    if (isLoading) {
        return (
            <div className={`w-full h-[400px] flex items-center justify-center ${className}`}>
                <Loader2 className='animate-spin text-blue-500' size={48} />
            </div>
        )
    }

    if (isError) {
        return (
            <div
                className={`w-full h-[400px] flex flex-col items-center justify-center text-red-400 ${className}`}
            >
                <AlertCircle size={48} className='mb-4' />
                <p>Error cargando análisis de variaciones: {(error as Error).message}</p>
            </div>
        )
    }

    if (!variations || variations.length === 0) {
        return null
    }

    // --- Main Chart: Daily Totals (Net Change) ---
    const getMainOption = (): EChartsOption => {
        const dates = filteredVariations.map(v => v.date.slice(5)) // MM-DD
        const values = filteredVariations.map(v => v.total_change)

        const zoomConfig: any[] = [
            { type: 'inside' }, // Allow zooming inside
            { type: 'slider', bottom: 0, height: 20, textStyle: { color: '#94a3b8' } },
        ]

        // Only force the range on the very first render/mount AND if no filter is active
        if (isFirstRender.current && !dateFilter.start && !dateFilter.end) {
            zoomConfig[0].start = 70
            zoomConfig[0].end = 100
        }

        // Removed the 'else if' that forced reset on every render if filtered

        return {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter: (params: any) => {
                    const item = filteredVariations[params[0].dataIndex]
                    if (!item) return ''
                    const color = item.total_change >= 0 ? '#22c55e' : '#ef4444'
                    return `
                    <div class="font-bold mb-1">${item.date}</div>
                    <div class="text-sm text-gray-400">Variación Neta:</div>
                    <div class="font-mono font-bold text-lg" style="color: ${color}">
                        ${item.total_change >= 0 ? '+' : ''}${item.total_change.toFixed(2)}
                    </div>
                  `
                },
            },
            grid: { left: '2%', right: '2%', top: '5%', bottom: '10%', containLabel: true },
            xAxis: {
                type: 'category',
                data: dates,
                axisLine: { lineStyle: { color: '#475569' } },
                axisLabel: { color: '#94a3b8' },
            },
            yAxis: {
                type: 'value',
                splitLine: { lineStyle: { color: '#334155', opacity: 0.3 } },
                axisLabel: { color: '#94a3b8' },
            },
            dataZoom: zoomConfig,
            series: [
                {
                    data: values.map((v, idx) => ({
                        value: v,
                        itemStyle: {
                            color: v >= 0 ? '#22c55e' : '#ef4444',
                            opacity: idx === activeIndex ? 1 : 0.5,
                            shadowBlur: idx === activeIndex ? 10 : 0,
                            shadowColor:
                                idx === activeIndex
                                    ? v >= 0
                                        ? '#22c55e'
                                        : '#ef4444'
                                    : 'transparent',
                        },
                    })),
                    type: 'bar',
                    barMaxWidth: 20,
                },
            ],
        }
    }

    const getDayComponents = (v: any, drivers: TransactionDriver[]) => {
        const sumSource = (source: string) =>
            drivers.filter(d => d.source === source).reduce((acc, curr) => acc + curr.amount, 0)

        const all = [
            {
                id: 'bank',
                name: 'Cuentas Bancarias',
                val: v.diff_saldo_neto, // Cambio matemático real
                transactionsSum: sumSource(ComponentType.BANCA),
                color: 'text-blue-400',
                hex: '#60a5fa',
                type: ComponentType.BANCA,
            },
            {
                id: 'invest',
                name: 'Inversiones',
                val: v.diff_notion,
                transactionsSum: sumSource(ComponentType.INVERSION),
                color: 'text-orange-400',
                hex: '#fb923c',
                type: ComponentType.INVERSION,
            },
            {
                id: 'debt',
                name: 'Deuda (Bolsa)',
                val: v.diff_deuda_acumulada,
                transactionsSum: sumSource(ComponentType.DEUDA),
                color: 'text-purple-400',
                hex: '#c084fc',
                type: ComponentType.DEUDA,
            },
            {
                id: 'card',
                name: 'Tarjeta de Crédito',
                // Ojo: En la matematica TOTAL = ... - TARJETA. Por ende, un aumento en tarjeta es un impacto negativo en patrimonio.
                val: -v.diff_tarjeta, 
                transactionsSum: sumSource(ComponentType.TARJETA),
                color: 'text-green-400',
                hex: '#4ade80',
                type: ComponentType.TARJETA,
            },
            {
                id: 'fixed',
                name: 'Pagos Fijos',
                val: -v.diff_pagos_fijos,
                transactionsSum: sumSource(ComponentType.PAGOS_FIJO),
                color: 'text-gray-400',
                hex: '#94a3b8',
                type: ComponentType.PAGOS_FIJO,
            },
            {
                id: 'val',
                name: 'Valuación Diferida',
                val: v.diff_interpolados,
                transactionsSum: sumSource(ComponentType.INTERPOLADOS),
                color: 'text-yellow-400',
                hex: '#facc15',
                type: ComponentType.INTERPOLADOS,
            }
        ]

        return all
            .map(item => ({
                ...item,
                discrepancy: item.val - item.transactionsSum,
            }))
            .filter(s => Math.abs(s.val) > 0.01 || Math.abs(s.discrepancy) > 0.1 || Math.abs(s.transactionsSum) > 0.01)
    }

    // --- Detail Chart: Component Bars ---
    const getDetailOption = (): EChartsOption => {
        if (!filteredVariations[activeIndex]) return {}

        const v = filteredVariations[activeIndex]
        const drivers = getDailyDrivers(v.date)
        const steps = getDayComponents(v, drivers)

        return {
            backgroundColor: 'transparent',
            title: {
                text: `Desglose: ${v.date}`,
                left: 'center',
                textStyle: { color: '#dda0dd', fontSize: 14, fontWeight: 'bold' },
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                borderColor: 'rgba(255,255,255,0.1)',
                textStyle: { color: '#e2e8f0' },
                formatter: (params: any) => {
                    const param = params[0]
                    if (!param) return ''

                    const idx = param.dataIndex
                    const cmp = steps[idx]
                    if (!cmp) return ''

                    // Show Component Summary
                    let html = `<div class="mb-2 border-b border-white/10 pb-1">
                      <span class="font-bold text-base" style="color: ${cmp.hex}">${cmp.name}</span>
                      <span class="float-right font-mono font-bold">${cmp.val > 0 ? '+' : ''}${cmp.val.toFixed(2)}</span>
                  </div>`

                    if (Math.abs(cmp.discrepancy) > 0.1) {
                        html += `<div class="mb-2 text-xs text-yellow-500 font-mono bg-yellow-900/20 p-1.5 rounded">
                        ⚠ Variación Inexplicada: Movimientos listados suman ${cmp.transactionsSum > 0 ? '+' : ''}${cmp.transactionsSum.toFixed(2)}. Faltan ${(cmp.discrepancy > 0 ? '+' : '')}${cmp.discrepancy.toFixed(2)}.
                      </div>`
                    }

                    // Show Related Transactions using unified classifier
                    const relatedTx = drivers
                        .filter(d => d.source === cmp.type)
                        .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount))
                        .slice(0, 5)

                    if (relatedTx.length > 0) {
                        html += `<div class="flex flex-col gap-1">`
                        relatedTx.forEach(tx => {
                            html += `
                            <div class="flex justify-between text-xs items-center gap-4">
                                <span class="opacity-80 truncate max-w-[150px]">${tx.description}</span>
                                <span class="font-mono ${tx.amount >= 0 ? 'text-green-400' : 'text-red-400'}">
                                    ${tx.amount?.toFixed(0)}
                                </span>
                            </div>
                          `
                        })
                        const count = drivers.filter(d => d.source === cmp.type).length
                        if (count > 5) {
                            html += `<div class="text-[10px] text-slate-500 mt-1 italic">... y ${count - 5} más</div>`
                        }
                        html += `</div>`
                    } else {
                        html += `<div class="text-xs text-slate-500 italic">Cambio sin transacciones directas</div>`
                    }

                    return html
                },
            },
            grid: { left: '3%', right: '3%', top: '40px', bottom: '10%', containLabel: true },
            xAxis: {
                type: 'category',
                data: steps.map(s => s.name),
                axisLine: { show: false },
                axisTick: { show: false },
                axisLabel: {
                    color: '#94a3b8',
                    fontSize: 10,
                    interval: 0,
                    formatter: (val: string) => val.split(' ')[0], // Shorten names
                },
            },
            yAxis: {
                type: 'value',
                splitLine: { lineStyle: { color: '#334155', opacity: 0.2 } },
                axisLabel: { color: '#64748b' },
            },
            series: [
                {
                    type: 'bar',
                    barMaxWidth: 40,
                    itemStyle: { borderRadius: [4, 4, 4, 4] },
                    data: steps.map(s => ({
                        value: s.val,
                        itemStyle: {
                            color: s.hex,
                            shadowBlur: 10,
                            shadowColor: s.hex + '40',
                        },
                    })),
                },
            ],
        }
    }

    const onChartEvent = (params: any) => {
        if (params.componentType === 'series') {
            setSelectedIndex(params.dataIndex)
        }
    }

    // Calculate Total from components
    const activeDay = filteredVariations[activeIndex]
    const activeDrivers = activeDay ? getDailyDrivers(activeDay.date) : []
    const dayComponents = activeDay ? getDayComponents(activeDay, activeDrivers) : []
    const calculatedTotal = dayComponents.reduce((sum, cmp) => sum + cmp.val, 0)

    return (
        <div
            className={`w-full bg-slate-900/60 p-6 rounded-3xl border border-white/10 shadow-2xl backdrop-blur-xl flex flex-col gap-6 ${className}`}
        >
            <div className='flex justify-between items-center border-b border-white/5 pb-4'>
                <h3 className='text-xl font-bold text-white flex items-center gap-3'>
                    <div className='w-2 h-8 bg-gradient-to-b from-purple-500 to-pink-500 rounded-full shadow-lg shadow-purple-500/20'></div>
                    Variación Patrimonial
                </h3>
                <button
                    onClick={async () => {
                        try {
                            await api.refreshCache()
                            window.location.reload()
                        } catch (e) {
                            console.error(e)
                        }
                    }}
                    className='text-xs text-slate-500 hover:text-white transition-colors bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-lg border border-white/5'
                >
                    🔄 Recargar Datos
                </button>
            </div>

            {/* Filters Bar */}
            <div className='flex flex-wrap items-center gap-4 bg-white/5 p-3 rounded-2xl border border-white/5'>
                <div className='flex items-center gap-2 text-sm text-gray-400'>
                    <Calendar size={16} />
                    <span className='font-medium'>Rango:</span>
                </div>
                <div className='flex items-center gap-2'>
                    <input
                        type='date'
                        value={dateFilter.start}
                        onChange={e => setDateFilter(prev => ({ ...prev, start: e.target.value }))}
                        className='bg-slate-900 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:ring-2 focus:ring-purple-500 outline-none'
                    />
                    <span className='text-gray-500'>→</span>
                    <input
                        type='date'
                        value={dateFilter.end}
                        onChange={e => setDateFilter(prev => ({ ...prev, end: e.target.value }))}
                        className='bg-slate-900 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:ring-2 focus:ring-purple-500 outline-none'
                    />
                </div>
                {(dateFilter.start || dateFilter.end) && (
                    <button
                        onClick={() => setDateFilter({ start: '', end: '' })}
                        className='flex items-center gap-1 text-xs text-red-400 hover:text-red-300 px-3 py-1.5 bg-red-500/10 rounded-lg transition-colors border border-red-500/20'
                    >
                        <X size={14} /> Limpiar
                    </button>
                )}
            </div>

            <div className='flex flex-col lg:flex-row gap-6 h-[500px]'>
                {/* MAIN CHART AREA */}
                <div className='flex-1 h-full min-h-[300px] flex flex-col'>
                    <div className='flex justify-between items-end mb-2'>
                        <h4 className='text-xs font-bold text-slate-500 uppercase tracking-widest'>
                            Histórico Diario
                        </h4>
                    </div>
                    <div className='flex-1 bg-slate-900/40 rounded-2xl p-2 border border-white/5 shadow-inner'>
                        <ReactECharts
                            ref={echartsRef}
                            option={getMainOption()}
                            style={{ height: '100%', width: '100%' }}
                            theme='dark'
                            onEvents={{
                                click: onChartEvent,
                            }}
                        />
                    </div>
                </div>

                {/* DETAIL PANEL AREA */}
                <div className='w-full lg:w-[400px] h-full flex flex-col animate-in fade-in slide-in-from-right duration-500'>
                    <div className='flex justify-between items-center mb-3'>
                        <h4 className='text-xs font-bold text-slate-500 uppercase tracking-widest'>
                            {detailMode === 'chart' ? 'Desglose Gráfico' : 'Lista Detallada'}
                        </h4>
                        <div className='flex bg-slate-800/80 rounded-lg p-1 gap-1'>
                            <button
                                onClick={() => setDetailMode('chart')}
                                className={`p-1.5 rounded-md transition-all ${detailMode === 'chart' ? 'bg-purple-500/20 text-purple-300 shadow-sm' : 'text-slate-500 hover:text-white'}`}
                            >
                                <BarChart2 size={16} />
                            </button>
                            <button
                                onClick={() => setDetailMode('list')}
                                className={`p-1.5 rounded-md transition-all ${detailMode === 'list' ? 'bg-purple-500/20 text-purple-300 shadow-sm' : 'text-slate-500 hover:text-white'}`}
                            >
                                <List size={16} />
                            </button>
                        </div>
                    </div>

                    <div className='flex-1 bg-slate-800/20 rounded-2xl border border-white/5 flex flex-col overflow-hidden relative backdrop-blur-sm'>
                        {detailMode === 'chart' ? (
                            <div className='p-2 h-full'>
                                <ReactECharts
                                    option={getDetailOption()}
                                    style={{ height: '100%', width: '100%' }}
                                    theme='dark'
                                />
                            </div>
                        ) : (
                            <div className='flex-1 overflow-y-auto custom-scrollbar p-4'>
                                {activeDay && (
                                    <>
                                        <div className='text-center mb-6'>
                                            <div className='text-white font-bold text-xl tracking-tight'>
                                                {activeDay.date}
                                            </div>
                                            <div className='text-xs text-slate-500 uppercase tracking-widest mt-1'>
                                                Resumen de Cambios
                                            </div>
                                        </div>

                                        <div className='space-y-6'>
                                            {dayComponents.map((cmp, i) => {
                                                const dailyDrivers = getDailyDrivers(activeDay.date)

                                                // Unified filtering
                                                console.log(cmp.type)
                                                const relatedTx = dailyDrivers.filter(
                                                    d => d.source === cmp.type
                                                )

                                                // Sort tx by amount magnitude
                                                relatedTx.sort(
                                                    (a, b) =>
                                                        Math.abs(b.amount) - Math.abs(a.amount)
                                                )

                                                return (
                                                    <div key={i} className='flex flex-col gap-2'>
                                                        {/* Header Line */}
                                                        <div className='flex justify-between items-center border-b border-white/5 pb-1'>
                                                            <div className='flex items-center gap-2'>
                                                                <div
                                                                    className='w-2 h-2 rounded-full'
                                                                    style={{
                                                                        backgroundColor: cmp.hex,
                                                                    }}
                                                                ></div>
                                                                <span
                                                                    className={`text-sm font-medium ${cmp.color} brightness-125`}
                                                                >
                                                                    {cmp.name}
                                                                </span>
                                                            </div>
                                                            <span
                                                                className={`font-mono font-bold text-sm ${cmp.val >= 0 ? 'text-green-400' : 'text-red-400'}`}
                                                            >
                                                                {cmp.val > 0 ? '+' : ''}
                                                                {cmp.val.toFixed(2)}
                                                            </span>
                                                        </div>

                                                        {/* Transactions List */}
                                                        {relatedTx.length > 0 && (
                                                            <div className='pl-3 border-l-2 border-white/5 ml-1 space-y-2 mt-1'>
                                                                {relatedTx.map((tx, idx) => (
                                                                    <div
                                                                        key={idx}
                                                                        className='flex justify-between items-center text-xs group'
                                                                    >
                                                                        <div className='flex flex-col flex-1 mr-4'>
                                                                            <span
                                                                                className='text-slate-300 truncate w-[180px]'
                                                                                title={
                                                                                    tx.description
                                                                                }
                                                                            >
                                                                                {tx.description.replace(
                                                                                    /Transferencia Directa/gi,
                                                                                    'T. Directa'
                                                                                )}
                                                                            </span>
                                                                            {tx.source && (
                                                                                <span className='text-[10px] text-slate-500 uppercase font-medium'>
                                                                                    {tx.source}
                                                                                </span>
                                                                            )}
                                                                        </div>
                                                                        <span className='font-mono text-slate-400 group-hover:text-white transition-colors'>
                                                                            {tx.amount?.toFixed(0)}
                                                                        </span>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        )}

                                                        {/* Check for residuals */}
                                                        {Math.abs(cmp.discrepancy) > 0.1 && (
                                                            <div className='pl-3 border-l-2 border-yellow-500/30 ml-1 mt-2 text-[11px] text-yellow-500/80 italic'>
                                                                ⚠ Variación Inexplicada: Las transacciones listadas suman {cmp.transactionsSum > 0 ? '+' : ''}{cmp.transactionsSum.toFixed(2)}. Falta justificar {(cmp.discrepancy > 0 ? '+' : '')}{cmp.discrepancy.toFixed(2)} de este salto.
                                                            </div>
                                                        )}
                                                        {relatedTx.length === 0 && Math.abs(cmp.val) > 1 && Math.abs(cmp.discrepancy) <= 0.1 && (
                                                            <div className='pl-4 text-[10px] text-slate-600 italic mt-1'>
                                                                Sin movimientos detallados
                                                            </div>
                                                        )}
                                                    </div>
                                                )
                                            })}
                                        </div>

                                        {/* Footer / Total */}
                                        <div className='mt-8 pt-4 border-t border-dashed border-white/10 flex justify-between items-center bg-slate-900/30 -mx-4 px-4 pb-2'>
                                            <div className='flex flex-col'>
                                                <span className='text-slate-400 text-xs uppercase'>
                                                    Total del Día
                                                </span>
                                                <span className='text-[10px] text-slate-600'>
                                                    (Calculado)
                                                </span>
                                            </div>
                                            <span
                                                className={`font-mono font-bold text-2xl ${calculatedTotal >= 0 ? 'text-green-400' : 'text-red-400'}`}
                                            >
                                                {calculatedTotal >= 0 ? '+' : ''}
                                                {calculatedTotal.toFixed(2)}
                                            </span>
                                        </div>
                                    </>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
