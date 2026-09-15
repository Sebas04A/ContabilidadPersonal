import React, { useEffect, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { Clock, Sunrise, Sun, Sunset, Moon, Info, AlertCircle } from 'lucide-react';
import { api, HourlyAnalysis } from '../../services/api';
import { money } from '../../utils/format';

/**
 * Ritmo de Gasto — when the money actually leaves, by time of day.
 *
 * Fed by /api/transactions/hourly-analysis, which reads the HORA enrichment
 * recovered from the bank's "Notificación de Consumos" emails. Only card
 * transactions have a time, so this view is implicitly about the credit card;
 * the coverage note below states that outright instead of letting the charts
 * imply a completeness they don't have.
 */

// Single hue (violet, the app's primary) — this is one series measuring one
// magnitude, so it needs one color, not a categorical palette.
const HUE = '#8b5cf6';
const SURFACE = '#18181b';
const INK_MUTED = '#a1a1aa';
const GRID_LINE = 'rgba(255, 255, 255, 0.05)';

const DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

const ICONO_FRANJA: Record<string, React.ReactNode> = {
    Madrugada: <Moon size={16} />,
    'Mañana': <Sunrise size={16} />,
    Tarde: <Sun size={16} />,
    Noche: <Sunset size={16} />,
};

export const SpendingRhythm: React.FC = () => {
    const [data, setData] = useState<HourlyAnalysis | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        api.getHourlyAnalysis()
            .then((res) => {
                if (!cancelled) { setData(res); setLoading(false); }
            })
            .catch((e) => {
                if (!cancelled) {
                    setError(e?.message ?? 'No se pudo cargar el análisis horario');
                    setLoading(false);
                }
            });
        return () => { cancelled = true; };
    }, []);

    const shell = (children: React.ReactNode) => (
        <div className="bg-slate-900/60 backdrop-blur-2xl border border-white/10 rounded-3xl p-8 shadow-2xl">
            <div className="flex items-center gap-3 mb-6">
                <div className="p-2.5 rounded-xl bg-primary-500/10 ring-1 ring-primary-500/20 text-primary-300">
                    <Clock size={20} />
                </div>
                <div>
                    <h2 className="text-xl font-bold text-white tracking-tight">Ritmo de Gasto</h2>
                    <p className="text-sm text-slate-400">A qué hora del día se te va el dinero</p>
                </div>
            </div>
            {children}
        </div>
    );

    if (loading) {
        return shell(
            <div className="h-64 flex items-center justify-center text-slate-500 text-sm animate-pulse">
                Cargando análisis horario…
            </div>
        );
    }

    if (error) {
        return shell(
            <div className="h-64 flex flex-col items-center justify-center gap-2 text-slate-400 text-sm">
                <AlertCircle size={24} className="text-amber-400" />
                {error}
            </div>
        );
    }

    if (!data || data.cobertura.con_hora === 0) {
        return shell(
            <div className="h-64 flex flex-col items-center justify-center gap-3 text-center px-6">
                <Info size={24} className="text-slate-500" />
                <p className="text-slate-400 text-sm max-w-md">
                    Todavía no hay transacciones con hora. Ejecuta{' '}
                    <code className="text-primary-300 bg-primary-500/10 px-1.5 py-0.5 rounded text-xs">
                        scripts/enriquecer_horas_tarjeta.py
                    </code>{' '}
                    para recuperarlas desde las notificaciones de consumo del banco.
                </p>
            </div>
        );
    }

    const { por_hora, heatmap, franjas, destacados, cobertura } = data;

    // ── Chart 1: magnitude across the 24-hour cycle → bars, one hue ───────────
    const barOption = {
        backgroundColor: 'transparent',
        grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(255,255,255,0.04)' } },
            backgroundColor: 'rgba(9, 9, 11, 0.95)',
            borderColor: 'rgba(255,255,255,0.1)',
            textStyle: { color: '#e4e4e7', fontSize: 12 },
            formatter: (params: any) => {
                const p = params[0];
                const b = por_hora[p.dataIndex];
                return `<strong>${String(b.hora).padStart(2, '0')}:00 – ${String(b.hora).padStart(2, '0')}:59</strong><br/>
                        Gasto total: <strong>${money(b.total)}</strong><br/>
                        Transacciones: ${b.count}<br/>
                        Ticket medio: ${money(b.promedio)}`;
            },
        },
        xAxis: {
            type: 'category',
            data: por_hora.map((b) => String(b.hora).padStart(2, '0')),
            axisLabel: { color: INK_MUTED, fontSize: 10, interval: 1 },
            axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
            axisTick: { show: false },
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: INK_MUTED, fontSize: 10, formatter: (v: number) => `$${v}` },
            splitLine: { lineStyle: { color: GRID_LINE } },
        },
        series: [
            {
                type: 'bar',
                data: por_hora.map((b) => b.total),
                // 4px rounded data-ends, anchored to the baseline.
                itemStyle: { color: HUE, borderRadius: [4, 4, 0, 0] },
                emphasis: { itemStyle: { color: '#a78bfa' } },
                barMaxWidth: 22,
            },
        ],
    };

    // ── Chart 2: two categorical axes + magnitude → heatmap, sequential ramp ──
    const maxCelda = heatmap.length ? Math.max(...heatmap.map((c) => c.total)) : 0;
    const heatOption = {
        backgroundColor: 'transparent',
        grid: { left: 8, right: 16, top: 12, bottom: 56, containLabel: true },
        tooltip: {
            backgroundColor: 'rgba(9, 9, 11, 0.95)',
            borderColor: 'rgba(255,255,255,0.1)',
            textStyle: { color: '#e4e4e7', fontSize: 12 },
            formatter: (p: any) => {
                const [hora, dia, total] = p.data;
                const celda = heatmap.find((c) => c.hora === hora && c.dia === dia);
                return `<strong>${DIAS[dia]} · ${String(hora).padStart(2, '0')}:00</strong><br/>
                        Gasto: <strong>${money(total)}</strong><br/>
                        Transacciones: ${celda?.count ?? 0}`;
            },
        },
        xAxis: {
            type: 'category',
            data: Array.from({ length: 24 }, (_, h) => String(h).padStart(2, '0')),
            splitArea: { show: false },
            axisLabel: { color: INK_MUTED, fontSize: 10, interval: 1 },
            axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
            axisTick: { show: false },
        },
        yAxis: {
            type: 'category',
            data: DIAS,
            splitArea: { show: false },
            axisLabel: { color: INK_MUTED, fontSize: 11 },
            axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
            axisTick: { show: false },
        },
        // Sequential: one hue, dark (low) -> bright (high) against a dark surface.
        // Doubles as the magnitude legend, so no separate legend box is needed.
        visualMap: {
            min: 0,
            max: maxCelda || 1,
            calculable: false,
            orient: 'horizontal',
            left: 'center',
            bottom: 4,
            itemWidth: 12,
            itemHeight: 120,
            textStyle: { color: INK_MUTED, fontSize: 10 },
            formatter: (v: number) => `$${Math.round(v)}`,
            inRange: { color: ['#1e1b2e', '#4c1d95', '#7c3aed', '#a78bfa', '#ddd6fe'] },
        },
        series: [
            {
                type: 'heatmap',
                data: heatmap.map((c) => [c.hora, c.dia, c.total]),
                // 2px surface gap between cells.
                itemStyle: { borderColor: SURFACE, borderWidth: 2, borderRadius: 3 },
                emphasis: { itemStyle: { borderColor: '#fff', borderWidth: 1 } },
                progressive: 0,
            },
        ],
    };

    return shell(
        <div className="flex flex-col gap-8">
            {/* Coverage note — states the scope instead of letting charts imply it */}
            <div className="flex items-start gap-2.5 text-xs text-slate-400 bg-slate-800/40 border border-white/5 rounded-xl px-4 py-3">
                <Info size={14} className="mt-0.5 shrink-0 text-slate-500" />
                <span>
                    Basado en <strong className="text-slate-200">{cobertura.con_hora}</strong> de{' '}
                    {cobertura.total_gastos} movimientos con hora conocida ({cobertura.porcentaje}%):
                    la de cuenta viene en el extracto del banco, la de tarjeta se recuperó de las
                    notificaciones de consumo. Los movimientos sin hora quedan fuera.
                </span>
            </div>

            {/* Day parts */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {franjas.map((f) => (
                    <div
                        key={f.nombre}
                        className="bg-slate-800/40 border border-white/5 rounded-2xl p-4 hover:border-primary-500/30 transition-colors"
                    >
                        <div className="flex items-center gap-2 text-primary-300 mb-2">
                            {ICONO_FRANJA[f.nombre]}
                            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                                {f.nombre}
                            </span>
                        </div>
                        <div className="text-2xl font-extrabold text-white tabular-nums tracking-tight">
                            {money(f.total)}
                        </div>
                        <div className="text-[11px] text-slate-500 mt-1">
                            {f.count} tx · media {money(f.promedio)}
                        </div>
                        <div className="text-[10px] text-slate-600 mt-0.5 font-mono">{f.rango}</div>
                    </div>
                ))}
            </div>

            {/* Hourly distribution */}
            <div>
                <h3 className="text-sm font-bold text-slate-300 mb-1">Gasto por hora del día</h3>
                <p className="text-xs text-slate-500 mb-3">Suma de todos los consumos en cada franja horaria</p>
                <ReactECharts option={barOption} style={{ height: 280 }} notMerge lazyUpdate />
            </div>

            {/* Weekday x hour */}
            <div>
                <h3 className="text-sm font-bold text-slate-300 mb-1">Día de la semana × hora</h3>
                <p className="text-xs text-slate-500 mb-3">Dónde se concentran tus consumos a lo largo de la semana</p>
                <ReactECharts option={heatOption} style={{ height: 300 }} notMerge lazyUpdate />
            </div>

            {/* Highlights */}
            {destacados && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-white/5">
                    <div className="pt-4">
                        <div className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-1">
                            Hora más cara
                        </div>
                        <div className="text-xl font-bold text-white tabular-nums">
                            {String(destacados.hora_mas_gasto).padStart(2, '0')}:00
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">
                            {money(destacados.hora_mas_gasto_total)} acumulados
                        </div>
                    </div>
                    <div className="pt-4">
                        <div className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-1">
                            Hora más frecuente
                        </div>
                        <div className="text-xl font-bold text-white tabular-nums">
                            {String(destacados.hora_mas_frecuente).padStart(2, '0')}:00
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">
                            {destacados.hora_mas_frecuente_count} transacciones
                        </div>
                    </div>
                    <div className="pt-4">
                        <div className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-1">
                            Mayor consumo
                        </div>
                        <div className="text-xl font-bold text-white tabular-nums">
                            {money(destacados.ticket_mayor.monto)}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5 truncate">
                            {destacados.ticket_mayor.descripcion} · {destacados.ticket_mayor.hora}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
