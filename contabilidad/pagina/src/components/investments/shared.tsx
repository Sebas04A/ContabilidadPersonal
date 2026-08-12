import type { ReactNode } from 'react';

export const fmt = (n: number | null | undefined, decimales = 2) =>
  n === null || n === undefined
    ? '—'
    : n.toLocaleString('en-US', { minimumFractionDigits: decimales, maximumFractionDigits: decimales });

export const money = (n: number | null | undefined) => (n === null || n === undefined ? '—' : `$${fmt(n)}`);

export const pct = (n: number | null | undefined) => (n === null || n === undefined ? '—' : `${fmt(n)} %`);

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
      {hint && <div className="text-[11px] text-surface-500">{hint}</div>}
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

export function Spinner() {
  return (
    <div className="flex justify-center py-14">
      <div className="w-6 h-6 border-2 border-primary-500/30 border-t-primary-500 rounded-full animate-spin" />
    </div>
  );
}

export function EmptyState({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return (
    <div className="text-center text-surface-500 text-sm py-14 px-6">
      {icon && <div className="flex justify-center mb-3 opacity-40">{icon}</div>}
      {children}
    </div>
  );
}

export function Section({ title, subtitle, children, action }: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="rounded-2xl bg-surface-900/40 backdrop-blur-xl border border-white/[0.06] overflow-hidden">
      <header className="px-5 py-3.5 border-b border-white/[0.06] flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-white">{title}</h2>
          {subtitle && <p className="text-[11px] text-surface-400 mt-0.5">{subtitle}</p>}
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}
