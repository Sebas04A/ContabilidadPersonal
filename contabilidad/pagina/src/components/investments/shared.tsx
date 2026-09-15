import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import * as echarts from 'echarts';
import { fmt, money, pct } from '../../utils/format';
import { useEChart } from '../../hooks/useEChart';

export { GRID, EJE, TOOLTIP } from '../../utils/chartTheme';

/** An echarts canvas that rebuilds its option whenever `option` changes. */
export function Chart({ option, height = 340, onEvento }: {
  option: echarts.EChartsOption;
  height?: number;
  /** Handlers de echarts por nombre de evento («click», «dblclick»…). */
  onEvento?: Record<string, (params: any) => void>;
}) {
  const { ref, chart: instance } = useEChart();
  // En una ref y no en la dependencia del efecto: así cambiar el handler no obliga a
  // destruir y reconstruir el gráfico entero en cada render.
  const handlers = useRef(onEvento);
  handlers.current = onEvento;

  useEffect(() => {
    const chart = instance.current;
    if (!chart) return;
    const nombres = Object.keys(handlers.current ?? {});
    for (const nombre of nombres) {
      chart.on(nombre, (params: any) => handlers.current?.[nombre]?.(params));
    }
    if (nombres.includes('click')) {
      chart.getZr().setCursorStyle('default');
    }
    return () => {
      for (const nombre of nombres) chart.off(nombre);
    };
  }, [instance]);

  useEffect(() => {
    // `true` replaces the option instead of merging: series that disappear must not
    // linger from the previous render.
    instance.current?.setOption(option, true);
  }, [option]);

  return <div ref={ref} style={{ height }} className="w-full" />;
}

export { fmt, money, pct };

export const fecha = (iso: string | null | undefined) => iso || '—';

/** Millions of USD·day: the raw number is unreadable, and only its order of magnitude matters. */
export const capitalDia = (n: number) => `${fmt(n / 1_000_000, 1)} M`;

export function KpiCard({ label, value, hint, tone = 'default', icon }: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: 'default' | 'good' | 'warn' | 'bad';
  icon?: ReactNode;
}) {
  const tones = {
    default: 'text-white',
    good: 'text-emerald-400',
    warn: 'text-amber-400',
    bad: 'text-rose-400',
  };
  return (
    <div className="p-4 rounded-xl bg-surface-900/50 backdrop-blur-xl border border-white/[0.06] flex flex-col gap-1">
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-surface-400">
        {icon}
        {label}
      </div>
      <div className={`text-2xl font-bold font-mono tabular-nums ${tones[tone]}`}>{value}</div>
      {hint && <div className="text-[11px] text-surface-400 leading-snug">{hint}</div>}
    </div>
  );
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'violet' | 'emerald' | 'amber' | 'sky' }) {
  const tones = {
    neutral: 'bg-surface-800/80 text-surface-300 border-white/10',
    violet: 'bg-primary-500/10 text-primary-300 border-primary-500/20',
    emerald: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20',
    amber: 'bg-amber-500/10 text-amber-300 border-amber-500/20',
    sky: 'bg-sky-500/10 text-sky-300 border-sky-500/20',
  };
  return (
    <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wide border ${tones[tone]}`}>
      {children}
    </span>
  );
}

/**
 * Navegación de segundo nivel, deliberadamente más callada que la de arriba.
 *
 * La barra principal usa relleno sólido; ésta marca lo activo con una línea inferior, para
 * que a simple vista se vea cuál de las dos jerarquías se está tocando.
 */
export function SubTabs<T extends string>({ items, value, onChange, label }: {
  items: { id: T; label: string; icon?: ReactNode }[];
  value: T;
  onChange: (id: T) => void;
  label: string;
}) {
  return (
    <nav aria-label={label} className="flex items-center gap-1 border-b border-white/[0.06] -mx-1 px-1">
      {items.map(({ id, label: texto, icon }) => {
        const activo = id === value;
        return (
          <button
            key={id}
            aria-current={activo ? 'page' : undefined}
            onClick={() => onChange(id)}
            className={`relative flex items-center gap-2 px-3 py-2.5 text-xs font-bold transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/70 rounded-t-lg ${
              activo ? 'text-white' : 'text-surface-400 hover:text-surface-100'
            }`}
          >
            {icon}
            {texto}
            {activo && <span className="absolute left-2 right-2 -bottom-px h-0.5 rounded-full bg-primary-500" />}
          </button>
        );
      })}
    </nav>
  );
}

export function Spinner() {
  return (
    <div className="flex justify-center py-14">
      <div className="w-6 h-6 border-2 border-primary-500/30 border-t-primary-500 rounded-full animate-spin" />
    </div>
  );
}

export function EmptyState({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return (
    <div className="text-center text-surface-400 text-sm leading-relaxed py-14 px-6 max-w-[52ch] mx-auto">
      {icon && <div className="flex justify-center mb-3 text-surface-500">{icon}</div>}
      {children}
    </div>
  );
}

export function Section({ title, subtitle, children, action }: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="rounded-2xl bg-surface-900/40 backdrop-blur-xl border border-white/[0.06] overflow-hidden">
      <header className="px-5 py-3.5 border-b border-white/[0.06] flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-bold text-white">{title}</h2>
          {subtitle && <p className="text-[11px] text-surface-400 mt-0.5 leading-snug">{subtitle}</p>}
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}
