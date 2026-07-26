import { useState, useEffect } from 'react';
import {
  X, User, Search, Users, Calendar, ArrowDownLeft, ArrowUpRight,
  CheckCircle2, Clock, Scale, Coins, TrendingUp, AlertTriangle, RefreshCw,
} from 'lucide-react';
import { useDeudores, useEstadoCuenta } from '../hooks/useTransactions';
import type { SupabaseDeudor, EstadoCuentaDeuda, EstadoCuentaPago, EstadoCuentaMovimiento } from '../services/api';

const fmt = (n: number) =>
  n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const fecha = (s: string | null) =>
  s ? new Date(s.replace(' ', 'T')).toLocaleDateString('es-EC', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';

type Tab = 'flujo' | 'deudas' | 'pagos';

export function AccountStatementModal({ onClose }: { onClose: () => void }) {
  const { data: deudores, isLoading: loadingDeudores } = useDeudores();
  const [selected, setSelected] = useState<SupabaseDeudor | null>(null);
  const [q, setQ] = useState('');
  const [tab, setTab] = useState<Tab>('flujo');
  const { data: estado, isLoading: loadingEstado } = useEstadoCuenta(selected?.id);

  useEffect(() => {
    if (!selected && deudores && deudores.length) setSelected(deudores[0]);
  }, [deudores, selected]);

  const filtered = (deudores ?? []).filter(d => d.nombre.toLowerCase().includes(q.toLowerCase()));

  const neto = estado?.resumen.neto ?? 0;
  const netoTone = Math.abs(neto) < 0.01 ? 'slate' : neto > 0 ? 'emerald' : 'rose';
  const netoLabel = Math.abs(neto) < 0.01 ? 'Al día' : neto > 0 ? 'Te deben' : 'Tú debes';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-6xl h-[88vh] flex flex-col bg-surface-950 border border-white/10 rounded-3xl shadow-2xl overflow-hidden">
        {/* Header */}
        <header className="flex-none px-6 py-5 border-b border-white/5 bg-surface-900/50 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <Users size={24} strokeWidth={1.5} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Estado de cuenta</h1>
              <p className="text-surface-400 text-sm">Flujo de dinero por persona (Supabase)</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2.5 rounded-xl bg-surface-800 hover:bg-surface-700 text-surface-400 hover:text-white transition-colors border border-white/5">
            <X size={20} />
          </button>
        </header>

        <div className="flex-1 flex overflow-hidden">
          {/* Lista de personas */}
          <aside className="w-72 shrink-0 border-r border-white/5 bg-surface-900/30 flex flex-col">
            <div className="p-3 border-b border-white/5">
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                <input
                  value={q}
                  onChange={e => setQ(e.target.value)}
                  placeholder="Buscar persona..."
                  className="w-full h-10 bg-surface-950/50 border border-white/5 rounded-xl pl-9 pr-3 text-sm text-surface-100 placeholder:text-surface-600 focus:outline-none focus:border-emerald-500/30"
                />
              </div>
            </div>
            <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
              {loadingDeudores ? (
                <div className="text-center text-surface-500 text-sm py-8">Cargando…</div>
              ) : filtered.length === 0 ? (
                <div className="text-center text-surface-500 text-sm py-8">Sin personas</div>
              ) : (
                filtered.map(d => (
                  <button
                    key={d.id}
                    onClick={() => setSelected(d)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all ${
                      selected?.id === d.id
                        ? 'bg-emerald-500/15 border border-emerald-500/30 text-white'
                        : 'text-surface-300 hover:bg-surface-800/60 border border-transparent'
                    }`}
                  >
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${selected?.id === d.id ? 'bg-emerald-500/20 text-emerald-300' : 'bg-surface-800 text-surface-500'}`}>
                      <User size={15} />
                    </div>
                    <span className="font-medium text-sm truncate">{d.nombre}</span>
                  </button>
                ))
              )}
            </div>
          </aside>

          {/* Panel del deudor */}
          <main className="flex-1 overflow-y-auto custom-scrollbar p-6">
            {!selected ? (
              <div className="h-full flex items-center justify-center text-surface-500">Elige una persona</div>
            ) : loadingEstado ? (
              <div className="h-full flex flex-col items-center justify-center gap-3 text-surface-500">
                <div className="w-6 h-6 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
                <span className="text-sm">Cargando estado de cuenta…</span>
              </div>
            ) : estado ? (
              <div className="space-y-6">
                {/* Resumen */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <SummaryTile label={netoLabel} value={`$${fmt(Math.abs(neto))}`} tone={netoTone} icon={<Scale size={13} />} big />
                  <SummaryTile label="Pendiente" value={`$${fmt(estado.resumen.total_pendiente)}`} tone="rose" icon={<Clock size={13} />} />
                  <SummaryTile label="Pagado" value={`$${fmt(estado.resumen.total_pagado)}`} tone="emerald" icon={<CheckCircle2 size={13} />} />
                  <SummaryTile
                    label="Saldo a favor"
                    value={`$${fmt(estado.resumen.saldo_favor)}`}
                    tone={estado.resumen.saldo_favor > 0.01 ? 'amber' : 'slate'}
                    icon={<Coins size={13} />}
                  />
                </div>

                {/* Tabs */}
                <div className="flex items-center gap-1 bg-surface-900/60 border border-white/5 rounded-xl p-1 w-fit">
                  {([
                    ['flujo', 'Flujo', estado.movimientos.length],
                    ['deudas', 'Deudas', estado.deudas.length],
                    ['pagos', 'Pagos', estado.pagos.length],
                  ] as [Tab, string, number][]).map(([t, label, n]) => (
                    <button
                      key={t}
                      onClick={() => setTab(t)}
                      className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 ${
                        tab === t ? 'bg-emerald-500/20 text-emerald-200' : 'text-surface-400 hover:text-white'
                      }`}
                    >
                      {label}
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${tab === t ? 'bg-emerald-500/20' : 'bg-surface-800'}`}>{n}</span>
                    </button>
                  ))}
                </div>

                {/* Contenido */}
                {tab === 'flujo' && (
                  estado.movimientos.length === 0
                    ? <EmptyBox text="Sin movimientos" />
                    : <FlowLedger movimientos={estado.movimientos} />
                )}
                {tab === 'deudas' && (
                  estado.deudas.length === 0
                    ? <EmptyBox text="Sin deudas registradas" />
                    : <div className="space-y-2">{estado.deudas.map(d => <DebtRow key={d.id} d={d} />)}</div>
                )}
                {tab === 'pagos' && (
                  estado.pagos.length === 0
                    ? <EmptyBox text="Sin pagos registrados" />
                    : <div className="space-y-2">{estado.pagos.map(p => <PaymentRow key={p.id} p={p} />)}</div>
                )}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-surface-500">No se pudo cargar.</div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}

/* ── Flujo (ledger cronológico) ─────────────────────────────────────────── */
function FlowLedger({ movimientos }: { movimientos: EstadoCuentaMovimiento[] }) {
  return (
    <div className="relative pl-6">
      {/* línea vertical del timeline */}
      <div className="absolute left-[9px] top-2 bottom-2 w-px bg-white/10" />
      <div className="space-y-2.5">
        {movimientos.map((m, i) => {
          const isPago = m.tipo === 'pago';
          const isCruce = isPago && !!m.es_compensacion;
          return (
            <div key={`${m.tipo}-${m.id}-${i}`} className="relative">
              <div className={`absolute -left-[19px] top-3 w-3.5 h-3.5 rounded-full border-2 border-surface-950 ${isCruce ? 'bg-sky-500' : isPago ? 'bg-emerald-500' : m.es_tu_deuda ? 'bg-rose-500' : 'bg-indigo-500'}`} />
              <div className="rounded-xl bg-surface-900/40 border border-white/5 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className={`p-1.5 rounded-lg shrink-0 ${isCruce ? 'bg-sky-500/15 text-sky-300' : isPago ? 'bg-emerald-500/15 text-emerald-300' : m.es_tu_deuda ? 'bg-rose-500/15 text-rose-300' : 'bg-indigo-500/15 text-indigo-300'}`}>
                      {isCruce ? <RefreshCw size={15} /> : isPago ? <ArrowDownLeft size={15} /> : <ArrowUpRight size={15} />}
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-bold text-surface-100 truncate">{m.concepto}</div>
                      <div className="text-[11px] text-surface-500 flex items-center gap-1"><Calendar size={10} />{fecha(m.fecha)}</div>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    {isCruce ? (
                      <>
                        <div className="font-mono font-bold text-sm text-sky-300">${fmt(m.monto_total ?? 0)}</div>
                        <div className="text-[10px] text-surface-500 flex items-center gap-1 justify-end">
                          <TrendingUp size={9} /> saldo ${fmt(m.saldo_acumulado)}
                        </div>
                      </>
                    ) : (
                      <>
                        <div className={`font-mono font-bold text-sm ${m.delta >= 0 ? 'text-indigo-300' : 'text-emerald-300'}`}>
                          {m.delta >= 0 ? '+' : '−'}${fmt(Math.abs(m.delta))}
                        </div>
                        <div className="text-[10px] text-surface-500 flex items-center gap-1 justify-end">
                          <TrendingUp size={9} /> saldo ${fmt(m.saldo_acumulado)}
                        </div>
                      </>
                    )}
                  </div>
                </div>
                {/* Asignaciones de un pago */}
                {isPago && (m.detalle.length > 0 || (m.sobrante ?? 0) > 0.01) && (
                  <div className="mt-2 pl-9 space-y-1">
                    {m.detalle.map((a, j) => (
                      <div key={j} className="flex items-center justify-between text-[11px] text-surface-400">
                        <span className="flex items-center gap-1.5"><span className="w-1 h-1 rounded-full bg-emerald-400/60" /> abonó a <span className="text-surface-300 font-medium">{a.titulo}</span></span>
                        <span className="font-mono text-emerald-300/80">${fmt(a.monto)}</span>
                      </div>
                    ))}
                    {(m.sobrante ?? 0) > 0.01 && (
                      <div className="flex items-center justify-between text-[11px] text-amber-300/80">
                        <span className="flex items-center gap-1.5"><Coins size={10} /> saldo a favor</span>
                        <span className="font-mono">${fmt(m.sobrante!)}</span>
                      </div>
                    )}
                  </div>
                )}
                {/* Deudas que quedaron PARCIALMENTE cubiertas tras este pago */}
                {isPago && (m.parciales?.length ?? 0) > 0 && (
                  <div className="mt-2 pl-9 space-y-1.5">
                    {m.parciales!.map((pc, j) => {
                      const prog = pc.monto_original > 0 ? Math.min(1, pc.pagado_acumulado / pc.monto_original) : 0;
                      return (
                        <div key={j} className="rounded-lg bg-amber-500/[0.07] border border-amber-500/25 px-2.5 py-1.5">
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="flex items-center gap-1.5 text-amber-200 font-semibold">
                              <AlertTriangle size={11} /> {pc.titulo} <span className="text-amber-300/70 font-normal">— parcial</span>
                            </span>
                            <span className="font-mono text-amber-200">queda ${fmt(pc.saldo)}<span className="text-amber-300/50"> / ${fmt(pc.monto_original)}</span></span>
                          </div>
                          <div className="h-1 rounded-full bg-white/5 overflow-hidden mt-1">
                            <div className="h-full bg-gradient-to-r from-amber-500/60 to-amber-400 rounded-full" style={{ width: `${prog * 100}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Deuda con sus abonos ──────────────────────────────────────────────── */
function DebtRow({ d }: { d: EstadoCuentaDeuda }) {
  const pagada = d.estado === 'PAGADA';
  const parcial = d.estado === 'PARCIAL';
  const progreso = d.monto_original > 0 ? Math.min(1, d.monto_pagado / d.monto_original) : 0;

  return (
    <div className={`px-4 py-3 rounded-xl border transition-all ${pagada ? 'bg-surface-900/20 border-white/5 opacity-75' : 'bg-surface-900/40 border-white/5'}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className={`font-bold text-sm truncate ${pagada ? 'text-surface-400 line-through' : 'text-surface-100'}`}>{d.titulo}</div>
          <div className="flex items-center gap-2 text-[11px] text-surface-500 mt-0.5">
            <span className="flex items-center gap-1"><Calendar size={11} />{fecha(d.fecha_gasto)}</span>
            <span className={`px-1.5 py-0.5 rounded font-bold uppercase tracking-wide text-[9px] ${
              pagada ? 'bg-emerald-500/15 text-emerald-300' : parcial ? 'bg-amber-500/15 text-amber-300' : 'bg-rose-500/15 text-rose-300'
            }`}>{pagada ? 'Pagada' : parcial ? 'Parcial' : 'Pendiente'}</span>
            <span className={`px-1.5 py-0.5 rounded font-bold uppercase tracking-wide text-[9px] ${d.es_tu_deuda ? 'bg-rose-500/10 text-rose-300' : 'bg-indigo-500/10 text-indigo-300'}`}>
              {d.es_tu_deuda ? 'Tú debes' : 'Te debe'}
            </span>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className={`font-mono font-bold ${pagada ? 'text-surface-500' : 'text-white'}`}>${fmt(pagada ? d.monto_original : d.saldo_pendiente)}</div>
          {parcial && <div className="text-[10px] text-surface-500">de ${fmt(d.monto_original)}</div>}
        </div>
      </div>
      {parcial && (
        <div className="mt-2.5">
          <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
            <div className="h-full bg-gradient-to-r from-amber-500/60 to-amber-400 rounded-full" style={{ width: `${progreso * 100}%` }} />
          </div>
        </div>
      )}
      {d.pagos.length > 0 && (
        <div className="mt-2 pt-2 border-t border-white/5 space-y-1">
          {d.pagos.map((a, j) => (
            <div key={j} className="flex items-center justify-between text-[11px] text-surface-400">
              <span className="flex items-center gap-1.5"><CheckCircle2 size={10} className="text-emerald-400/70" /> abonado el {fecha(a.fecha_pago)}</span>
              <span className="font-mono text-emerald-300/80">${fmt(a.monto_asignado)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Pago con a qué deudas fue ─────────────────────────────────────────── */
function PaymentRow({ p }: { p: EstadoCuentaPago }) {
  return (
    <div className="px-4 py-3 rounded-xl bg-surface-900/40 border border-white/5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-emerald-500/15 text-emerald-300"><ArrowDownLeft size={15} /></div>
          <div>
            <div className="text-sm font-bold text-surface-100">Pago recibido</div>
            <div className="text-[11px] text-surface-500 flex items-center gap-1"><Calendar size={10} />{fecha(p.fecha_pago)}</div>
          </div>
        </div>
        <div className="text-right">
          <div className="font-mono font-bold text-emerald-300">+${fmt(p.monto_total)}</div>
          {p.sobrante > 0.01 && <div className="text-[10px] text-amber-300/80">a favor ${fmt(p.sobrante)}</div>}
        </div>
      </div>
      {p.deudas.length > 0 && (
        <div className="mt-2 pt-2 border-t border-white/5 space-y-1">
          {p.deudas.map((a, j) => (
            <div key={j} className="flex items-center justify-between text-[11px] text-surface-400">
              <span className="flex items-center gap-1.5"><span className="w-1 h-1 rounded-full bg-emerald-400/60" /> {a.titulo}</span>
              <span className="font-mono text-emerald-300/80">${fmt(a.monto_asignado)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SummaryTile({ label, value, tone, icon, big }: {
  label: string; value: string; tone: 'rose' | 'emerald' | 'indigo' | 'slate' | 'amber'; icon?: React.ReactNode; big?: boolean;
}) {
  const toneMap = {
    rose: 'text-rose-400', emerald: 'text-emerald-400', indigo: 'text-indigo-400',
    slate: 'text-surface-300', amber: 'text-amber-400',
  };
  return (
    <div className={`rounded-2xl bg-surface-900/40 border px-4 py-3 ${big ? 'border-white/15' : 'border-white/10'}`}>
      <div className="flex items-center gap-1.5 text-[10px] text-surface-500 uppercase tracking-wider font-bold">{icon}{label}</div>
      <div className={`font-mono font-bold mt-0.5 ${big ? 'text-2xl' : 'text-lg'} ${toneMap[tone]}`}>{value}</div>
    </div>
  );
}

function EmptyBox({ text }: { text: string }) {
  return <div className="text-center text-sm text-surface-500 border border-dashed border-white/5 rounded-xl bg-surface-900/20 py-6">{text}</div>;
}
