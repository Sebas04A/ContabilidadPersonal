import { useState, useEffect } from 'react';
import {
  X, Search, Users, Calendar, ArrowDownLeft, ArrowUpRight,
  CheckCircle2, Clock, Scale, Coins, TrendingUp, AlertTriangle, RefreshCw,
  ChevronDown, ChevronRight,
} from 'lucide-react';
import { useDeudores, useEstadoCuenta } from '../hooks/useTransactions';
import type { SupabaseDeudor, EstadoCuentaDeuda, EstadoCuentaPago, EstadoCuentaMovimiento, MovimientoItem, CruceSugerido } from '../services/api';

const fmt = (n: number) =>
  n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const fecha = (s: string | null) => {
  if (!s) return '—';
  const hasTime = s.includes(' ') || s.includes('T');
  const normalized = hasTime ? s.replace(' ', 'T') : `${s}T00:00:00`;
  return new Date(normalized).toLocaleDateString('es-EC', { day: '2-digit', month: 'short', year: 'numeric' });
};

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
        {/* Background Gradients */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none z-0 opacity-45">
          <div className="absolute top-[-10%] right-[-10%] w-[350px] h-[350px] bg-emerald-500/10 rounded-full blur-[90px]" />
          <div className="absolute bottom-[-10%] left-[-10%] w-[350px] h-[350px] bg-indigo-500/10 rounded-full blur-[90px]" />
        </div>

        {/* Header */}
        <header className="relative z-10 flex-none px-6 py-5 border-b border-white/5 bg-surface-900/50 flex items-center justify-between">
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

        <div className="flex-1 flex overflow-hidden relative z-10">
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
                filtered.map(d => {
                  const neto = d.neto ?? 0;
                  const hasBalance = Math.abs(neto) >= 0.01;
                  const owesMe = neto > 0;
                  const isSelected = selected?.id === d.id;

                  return (
                    <button
                      key={d.id}
                      onClick={() => setSelected(d)}
                      className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-left transition-all border ${
                        isSelected
                          ? 'bg-emerald-500/15 border-emerald-500/30 text-white shadow-lg'
                          : 'text-surface-300 hover:bg-surface-800/60 border-transparent hover:text-white'
                      }`}
                    >
                      <div className="truncate min-w-0">
                        <span className="font-semibold text-sm truncate block leading-tight">{d.nombre}</span>
                        {hasBalance ? (
                          <span className="text-[10px] text-surface-500 block mt-0.5">
                            {owesMe ? 'Te debe' : 'Tú debes'}
                          </span>
                        ) : (
                          <span className="text-[10px] text-surface-600 block mt-0.5">
                            Al día
                          </span>
                        )}
                      </div>
                      <div className="text-right shrink-0 ml-2">
                        <span className={`font-mono text-xs ${
                          hasBalance
                            ? owesMe
                              ? 'text-emerald-400 font-bold'
                              : 'text-rose-400 font-bold'
                            : 'text-surface-500'
                        }`}>
                          {hasBalance ? `${owesMe ? '+' : '−'}$${fmt(Math.abs(neto))}` : '$0.00'}
                        </span>
                      </div>
                    </button>
                  );
                })
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
                  {/* El crédito puede ser de cualquiera de los dos: se dice de quién. */}
                  <SummaryTile
                    label="Saldo a favor"
                    value={`$${fmt(Math.max(estado.resumen.saldo_favor, estado.resumen.saldo_favor_owner))}`}
                    sub={
                      estado.resumen.saldo_favor > 0.01 && estado.resumen.saldo_favor_owner > 0.01
                        ? `de ${selected.nombre} $${fmt(estado.resumen.saldo_favor)} · tuyo $${fmt(estado.resumen.saldo_favor_owner)}`
                        : estado.resumen.saldo_favor > 0.01
                          ? `a favor de ${selected.nombre}`
                          : estado.resumen.saldo_favor_owner > 0.01
                            ? 'a favor tuyo'
                            : undefined
                    }
                    tone={Math.max(estado.resumen.saldo_favor, estado.resumen.saldo_favor_owner) > 0.01 ? 'amber' : 'slate'}
                    icon={<Coins size={13} />}
                  />
                </div>

                {/* Cruce que todavía se puede hacer (aunque nadie haya pagado) */}
                {estado.cruce_sugerido && estado.cruce_sugerido.monto > 0.01 && (
                  <CruceSugeridoCard cruce={estado.cruce_sugerido} neto={neto} />
                )}

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
                    : <FlowLedger movimientos={estado.movimientos} nombre={selected.nombre} />
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
function FlowLedger({ movimientos, nombre }: { movimientos: EstadoCuentaMovimiento[]; nombre: string }) {
  // La lista viene presente→pasado, así que un cruce aparece JUSTO DEBAJO del pago que lo
  // disparó (ocurrió antes). Cuando ese par existe se dibujan dentro de un mismo bloque.
  const filas: { pago?: EstadoCuentaMovimiento; mov: EstadoCuentaMovimiento }[] = [];
  for (let i = 0; i < movimientos.length; i++) {
    const m = movimientos[i];
    const sig = movimientos[i + 1];
    if (m.tipo === 'pago' && sig?.tipo === 'cruce' && sig.pago_vinculado?.id === m.id) {
      filas.push({ pago: m, mov: sig });
      i++;
    } else {
      filas.push({ mov: m });
    }
  }

  return (
    <div className="relative pl-6">
      {/* línea vertical del timeline */}
      <div className="absolute left-[9px] top-2 bottom-2 w-px bg-white/10" />
      <div className="space-y-2.5">
        {filas.map((f, i) =>
          f.pago ? (
            <LiquidacionGroup key={`liq-${f.pago.id}-${i}`} pago={f.pago} cruce={f.mov} nombre={nombre} />
          ) : f.mov.tipo === 'cruce' ? (
            <div key={`cruce-${f.mov.id}-${i}`} className="relative">
              <TimelineDot tone="sky" />
              <CruceCard m={f.mov} />
            </div>
          ) : (
            <div key={`${f.mov.tipo}-${f.mov.id}-${i}`} className="relative">
              <TimelineDot tone={f.mov.tipo === 'pago' ? 'emerald' : f.mov.es_tu_deuda ? 'rose' : 'indigo'} />
              <MovimientoCard m={f.mov} nombre={nombre} />
            </div>
          )
        )}
      </div>
    </div>
  );
}

function TimelineDot({ tone }: { tone: 'sky' | 'emerald' | 'rose' | 'indigo' }) {
  const bg = { sky: 'bg-sky-500', emerald: 'bg-emerald-500', rose: 'bg-rose-500', indigo: 'bg-indigo-500' }[tone];
  return <div className={`absolute -left-[19px] top-3 w-3.5 h-3.5 rounded-full border-2 border-surface-950 ${bg}`} />;
}

/* El cruce se genera siempre justo antes de un pago: se muestran encadenados. */
function LiquidacionGroup({ pago, cruce, nombre }: {
  pago: EstadoCuentaMovimiento; cruce: EstadoCuentaMovimiento; nombre: string;
}) {
  return (
    <div className="relative">
      <TimelineDot tone="emerald" />
      <div className="rounded-xl border border-sky-500/20 bg-sky-500/[0.03] p-1.5 space-y-1.5">
        <MovimientoCard m={pago} nombre={nombre} />
        <div className="flex items-center gap-2 px-2 text-[10px] font-bold uppercase tracking-wider text-sky-400/70">
          <div className="h-px flex-1 bg-sky-500/20" />
          antes de este pago
          <div className="h-px flex-1 bg-sky-500/20" />
        </div>
        <CruceCard m={cruce} />
      </div>
    </div>
  );
}

/* ── Cruce disponible (propuesta, nada escrito todavía) ────────────────── */
function CruceSugeridoCard({ cruce, neto }: { cruce: CruceSugerido; neto: number }) {
  const [open, setOpen] = useState(false);
  const nDeudas = cruce.lados.te_deben.items.length + cruce.lados.tu_debes.items.length;

  return (
    <div className="rounded-2xl border border-dashed border-sky-500/40 bg-sky-500/[0.04]">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full px-4 py-3.5 flex items-center justify-between gap-3 text-left hover:bg-white/[0.02] rounded-2xl transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="p-2 rounded-xl bg-sky-500/15 text-sky-300 shrink-0"><RefreshCw size={18} /></div>
          <div className="min-w-0">
            <div className="text-sm font-bold text-sky-200 flex items-center gap-1.5">
              Cruce disponible
              {open ? <ChevronDown size={14} className="text-sky-400/70" /> : <ChevronRight size={14} className="text-sky-400/70" />}
            </div>
            <div className="text-[11px] text-surface-400">
              {nDeudas} deuda{nDeudas === 1 ? '' : 's'} se compensarían entre sí · nadie tiene que pagar esta parte
            </div>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="font-mono font-bold text-2xl text-sky-300 leading-tight">${fmt(cruce.monto)}</div>
          <div className="text-[10px] text-surface-500">aún sin aplicar</div>
        </div>
      </button>

      {open && (
        <div className="px-4 pb-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <CruceLado titulo="Te deben" tone="indigo" total={cruce.lados.te_deben.total} items={cruce.lados.te_deben.items} />
            <CruceLado titulo="Tú debes" tone="rose" total={cruce.lados.tu_debes.total} items={cruce.lados.tu_debes.items} />
          </div>
          <div className="mt-3 pt-2.5 border-t border-sky-500/15">
            <SaldoResultante saldo={neto} label="Quedaría en" />
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Piezas compartidas por pagos y cruces ─────────────────────────────── */

/** Una deuda saldada: tachada y en verde, sin badges. Solo se ve al expandir. */
function DeudaSaldadaRow({ it, tone }: { it: MovimientoItem; tone: string }) {
  return (
    <div className="flex items-center justify-between gap-2 px-2 py-1.5 rounded-md bg-emerald-500/[0.05] opacity-60">
      <span className="flex items-center gap-1.5 min-w-0">
        <CheckCircle2 size={12} className="text-emerald-400 shrink-0" />
        <span className="text-[11px] font-medium text-surface-400 line-through truncate">{it.titulo}</span>
      </span>
      <span className={`font-mono text-[11px] shrink-0 line-through ${tone}`}>−${fmt(it.aplicado)}</span>
    </div>
  );
}

/**
 * Una deuda que sobrevivió al movimiento: se repite aquí, destacada en ámbar, con lo que
 * le falta como protagonista y lo que ya lleva abonado como dato secundario.
 */
function DeudaParcialRow({ it }: { it: MovimientoItem }) {
  const prog = it.monto_original > 0 ? Math.min(1, it.pagado_acumulado / it.monto_original) : 0;
  return (
    <div className="rounded-lg bg-amber-500/[0.07] border border-amber-500/30 px-2.5 py-2">
      <div className="flex items-end justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-amber-200 font-semibold text-[11px]">
            <AlertTriangle size={11} className="shrink-0" />
            <span className="truncate">{it.titulo}</span>
            <span className="px-1.5 py-px rounded bg-amber-500/20 text-amber-300 font-bold uppercase tracking-wide text-[9px] shrink-0">
              Parcial
            </span>
          </div>
          <div className="text-[10px] text-surface-500 mt-0.5">
            inicial ${fmt(it.monto_original)} · abonado ${fmt(it.pagado_acumulado)}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[9px] font-bold uppercase tracking-wider text-amber-400/70">Le falta</div>
          <div className="font-mono font-bold text-lg text-amber-300 leading-tight">${fmt(it.saldo_despues)}</div>
          {(it.abono_saldo_favor ?? 0) > 0.01 && (
            <div className="text-[9px] text-sky-300 font-bold">
              −${fmt(it.abono_saldo_favor)} con saldo a favor
            </div>
          )}
        </div>
      </div>
      <div className="h-1.5 rounded-full bg-white/5 overflow-hidden mt-1.5">
        <div className="h-full bg-gradient-to-r from-amber-500/60 to-amber-400 rounded-full" style={{ width: `${prog * 100}%` }} />
      </div>
    </div>
  );
}

/** Sobrante de un pago: dinero que quedó a favor de quien pagó. */
function SaldoFavorBanner({ monto, deQuien }: { monto: number; deQuien: string }) {
  return (
    <div className="rounded-lg bg-amber-500/[0.09] border border-amber-500/30 px-3 py-2 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2 text-amber-300">
        <Coins size={16} className="shrink-0" />
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-amber-400/80">Saldo a favor</div>
          <div className="text-[11px] text-surface-400">de {deQuien}</div>
        </div>
      </div>
      <div className="font-mono font-bold text-2xl text-amber-300">${fmt(monto)}</div>
    </div>
  );
}

/** Saldo con el que queda la cuenta tras el movimiento, en grande y con su lado. */
function SaldoResultante({ saldo, label }: { saldo: number; label: string }) {
  const alDia = Math.abs(saldo) < 0.01;
  const tone = alDia ? 'text-surface-300' : saldo > 0 ? 'text-emerald-300' : 'text-rose-300';
  const lado = alDia ? 'Al día' : saldo > 0 ? 'Te deben' : 'Tú debes';
  return (
    <div className="flex items-end justify-between gap-3">
      <span className="text-[10px] font-bold uppercase tracking-wider text-surface-500">{label}</span>
      <div className="text-right">
        <div className={`text-[10px] font-bold uppercase tracking-wider ${tone} opacity-80`}>{lado}</div>
        <div className={`font-mono font-bold text-2xl leading-tight ${tone}`}>${fmt(Math.abs(saldo))}</div>
      </div>
    </div>
  );
}

/* ── Cruce de cuentas: dos lados, colapsable ───────────────────────────── */
function CruceCard({ m }: { m: EstadoCuentaMovimiento }) {
  const [open, setOpen] = useState(false);
  const teDeben = m.lados?.te_deben ?? { total: 0, items: [] };
  const tuDebes = m.lados?.tu_debes ?? { total: 0, items: [] };
  const items = m.items ?? [];
  const saldadas = items.filter(it => it.cerrada);
  const parciales = items.filter(it => !it.cerrada);
  const cruzado = m.monto_cruzado ?? 0;

  return (
    <div className="rounded-xl bg-surface-900/40 border border-sky-500/25">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full px-4 py-3 flex items-center justify-between gap-3 text-left hover:bg-white/[0.02] rounded-xl transition-colors"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-1.5 rounded-lg shrink-0 bg-sky-500/15 text-sky-300"><RefreshCw size={15} /></div>
          <div className="min-w-0">
            <div className="text-sm font-bold text-surface-100 flex items-center gap-1.5">
              Cruce de cuentas
              {open ? <ChevronDown size={13} className="text-sky-400/70" /> : <ChevronRight size={13} className="text-sky-400/70" />}
            </div>
            <div className="text-[11px] text-surface-500 flex items-center gap-2">
              <span className="flex items-center gap-1"><Calendar size={10} />{fecha(m.fecha)}</span>
              {saldadas.length > 0 && (
                <span className="text-emerald-400/80 flex items-center gap-1">
                  <CheckCircle2 size={10} />{saldadas.length} saldada{saldadas.length === 1 ? '' : 's'}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="font-mono font-bold text-sm text-sky-300">${fmt(cruzado)}</div>
          <div className="text-[10px] text-surface-500 flex items-center gap-1 justify-end">
            <TrendingUp size={9} /> saldo ${fmt(Math.abs(m.saldo_acumulado))}
          </div>
        </div>
      </button>

      {/* Siempre visible: lo que el cruce NO alcanzó a saldar sigue vivo. */}
      {parciales.length > 0 && (
        <div className="px-4 pb-3 space-y-1.5">
          {parciales.map(it => <DeudaParcialRow key={it.deuda_id} it={it} />)}
        </div>
      )}

      {open && (
        <div className="px-4 pb-3.5 pt-3 border-t border-sky-500/15">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <CruceLado titulo="Te deben" tone="indigo" total={teDeben.total} items={teDeben.items} />
            <CruceLado titulo="Tú debes" tone="rose" total={tuDebes.total} items={tuDebes.items} />
          </div>

          <div className="mt-3 pt-2.5 border-t border-white/5 flex items-center justify-between gap-3">
            <span className="text-[11px] font-bold uppercase tracking-wider text-sky-400/80">Total cruzado</span>
            <span className="font-mono font-bold text-sky-300">${fmt(cruzado)}</span>
          </div>
          <div className="mt-2">
            <SaldoResultante saldo={m.saldo_acumulado} label="Saldo después del cruce" />
          </div>
          {m.pago_vinculado && (
            <div className="mt-1.5 flex items-center justify-between gap-3 text-[11px] text-surface-500">
              <span>Luego se aplicó {m.pago_vinculado.concepto.toLowerCase()}</span>
              <span className="font-mono">${fmt(m.pago_vinculado.monto_total)}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CruceLado({ titulo, tone, total, items }: {
  titulo: string; tone: 'indigo' | 'rose'; total: number; items: MovimientoItem[];
}) {
  const text = tone === 'indigo' ? 'text-indigo-300' : 'text-rose-300';

  return (
    <div className="rounded-lg bg-surface-950/40 border border-white/5 p-2.5">
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className={`text-[10px] font-bold uppercase tracking-wider ${text}`}>{titulo}</span>
        <span className={`font-mono text-xs font-bold ${text}`}>${fmt(total)}</span>
      </div>
      {items.length === 0 ? (
        <div className="text-[11px] text-surface-600 py-1">Sin deudas de este lado</div>
      ) : (
        <div className="space-y-1.5">
          {items.map(it => it.cerrada
            ? <DeudaSaldadaRow key={it.deuda_id} it={it} tone={text} />
            : <DeudaParcialRow key={it.deuda_id} it={it} />)}
        </div>
      )}
    </div>
  );
}

/* ── Movimiento normal (deuda o pago) ──────────────────────────────────── */
function MovimientoCard({ m, nombre }: { m: EstadoCuentaMovimiento; nombre: string }) {
  if (m.tipo === 'pago') return <PagoCard m={m} nombre={nombre} />;
  return (
    <div className="rounded-xl bg-surface-900/40 border border-white/5 px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className={`p-1.5 rounded-lg shrink-0 ${m.es_tu_deuda ? 'bg-rose-500/15 text-rose-300' : 'bg-indigo-500/15 text-indigo-300'}`}>
            <ArrowUpRight size={15} />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-bold text-surface-100 truncate">{m.concepto}</div>
            <div className="text-[11px] text-surface-500 flex items-center gap-1"><Calendar size={10} />{fecha(m.fecha)}</div>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className={`font-mono font-bold text-sm ${m.delta >= 0 ? 'text-indigo-300' : 'text-emerald-300'}`}>
            {m.delta >= 0 ? '+' : '−'}${fmt(Math.abs(m.delta))}
          </div>
          <div className="text-[10px] text-surface-500 flex items-center gap-1 justify-end">
            <TrendingUp size={9} /> saldo ${fmt(m.saldo_acumulado)}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Pago: mismo lenguaje visual que el cruce ──────────────────────────── */
function PagoCard({ m, nombre }: { m: EstadoCuentaMovimiento; nombre: string }) {
  const [open, setOpen] = useState(false);
  const items = m.items ?? [];
  const saldadas = items.filter(it => it.cerrada);
  const parciales = items.filter(it => !it.cerrada);
  const sobrante = m.sobrante ?? 0;
  const entregado = !!m.es_mi_pago;
  const tone = entregado ? 'text-indigo-300' : 'text-emerald-300';
  const chip = entregado ? 'bg-indigo-500/15 text-indigo-300' : 'bg-emerald-500/15 text-emerald-300';
  const asignado = items.reduce((s, it) => s + it.aplicado, 0);

  return (
    <div className="rounded-xl bg-surface-900/40 border border-white/5">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full px-4 py-3 flex items-center justify-between gap-3 text-left hover:bg-white/[0.02] rounded-xl transition-colors"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className={`p-1.5 rounded-lg shrink-0 ${chip}`}>
            {entregado ? <ArrowUpRight size={15} /> : <ArrowDownLeft size={15} />}
          </div>
          <div className="min-w-0">
            <div className="text-sm font-bold text-surface-100 flex items-center gap-1.5">
              {m.concepto}
              {items.length > 0 && (open
                ? <ChevronDown size={13} className="text-surface-500" />
                : <ChevronRight size={13} className="text-surface-500" />)}
            </div>
            <div className="text-[11px] text-surface-500 flex items-center gap-2">
              <span className="flex items-center gap-1"><Calendar size={10} />{fecha(m.fecha)}</span>
              {saldadas.length > 0 && (
                <span className="text-emerald-400/80 flex items-center gap-1">
                  <CheckCircle2 size={10} />{saldadas.length} saldada{saldadas.length === 1 ? '' : 's'}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className={`font-mono font-bold text-sm ${m.delta >= 0 ? 'text-indigo-300' : 'text-emerald-300'}`}>
            {m.delta >= 0 ? '+' : '−'}${fmt(Math.abs(m.delta))}
          </div>
          <div className="text-[10px] text-surface-500 flex items-center gap-1 justify-end">
            <TrendingUp size={9} /> saldo ${fmt(m.saldo_acumulado)}
          </div>
        </div>
      </button>

      {/* Siempre visible: lo que quedó a favor y lo que el pago no alcanzó a cerrar. */}
      {(sobrante > 0.01 || parciales.length > 0) && (
        <div className="px-4 pb-3 space-y-1.5">
          {sobrante > 0.01 && (
            <SaldoFavorBanner monto={sobrante} deQuien={entregado ? 'ti' : nombre} />
          )}
          {parciales.map(it => <DeudaParcialRow key={it.deuda_id} it={it} />)}
        </div>
      )}

      {open && items.length > 0 && (
        <div className="px-4 pb-3.5 pt-3 border-t border-white/5">
          <div className="rounded-lg bg-surface-950/40 border border-white/5 p-2.5">
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-surface-400">
                Abonó a {items.length} deuda{items.length === 1 ? '' : 's'}
              </span>
              <span className={`font-mono text-xs font-bold ${tone}`}>${fmt(asignado)}</span>
            </div>
            <div className="space-y-1.5">
              {items.map(it => it.cerrada
                ? <DeudaSaldadaRow key={it.deuda_id} it={it} tone={tone} />
                : <DeudaParcialRow key={it.deuda_id} it={it} />)}
            </div>
          </div>
          <div className="mt-3">
            <SaldoResultante saldo={m.saldo_acumulado} label="Saldo después del pago" />
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Deuda con sus abonos ──────────────────────────────────────────────── */
function DebtRow({ d }: { d: EstadoCuentaDeuda }) {
  const pagada = d.estado === 'PAGADA';
  const parcial = d.estado === 'PARCIAL';
  const abonoFavor = d.abono_saldo_favor ?? 0;
  // Lo que se saldaría sola si se aplicara el cruce disponible.
  const cruzable = d.cruce_sugerido ?? 0;
  const seCruzaEntera = cruzable > 0.01 && d.saldo_real - cruzable <= 0.01;
  const progreso = d.monto_original > 0
    ? Math.min(1, (d.monto_pagado + abonoFavor) / d.monto_original)
    : 0;

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
            {cruzable > 0.01 && (
              <span className="px-1.5 py-0.5 rounded font-bold uppercase tracking-wide text-[9px] bg-sky-500/15 text-sky-300 flex items-center gap-1">
                <RefreshCw size={9} />{seCruzaEntera ? 'Se cruza entera' : 'Cruce parcial'}
              </span>
            )}
          </div>
        </div>
        <div className="text-right shrink-0">
          {abonoFavor > 0.01 && !pagada && (
            <div className="text-[10px] text-surface-500 line-through">${fmt(d.saldo_pendiente)}</div>
          )}
          <div className={`font-mono font-bold ${pagada ? 'text-surface-500' : 'text-white'}`}>${fmt(pagada ? d.monto_original : d.saldo_real)}</div>
          {abonoFavor > 0.01 && (
            <div className="text-[10px] font-bold text-sky-300">−${fmt(abonoFavor)} (saldo a favor)</div>
          )}
          {cruzable > 0.01 && (
            <div className="text-[10px] font-bold text-sky-300">−${fmt(cruzable)} si se cruza</div>
          )}
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
  // Un cruce es un pago virtual (no movió dinero); un pago propio sale de tu bolsillo.
  const cruce = !!p.es_compensacion;
  const label = cruce ? 'Cruce de cuentas' : p.es_mi_pago ? 'Pago entregado' : 'Pago recibido';
  const tone = cruce ? 'text-sky-300' : p.es_mi_pago ? 'text-indigo-300' : 'text-emerald-300';
  const chip = cruce ? 'bg-sky-500/15 text-sky-300' : p.es_mi_pago ? 'bg-indigo-500/15 text-indigo-300' : 'bg-emerald-500/15 text-emerald-300';
  const signo = cruce ? '' : p.es_mi_pago ? '+' : '−';

  return (
    <div className={`px-4 py-3 rounded-xl bg-surface-900/40 border ${cruce ? 'border-sky-500/25' : 'border-white/5'}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className={`p-1.5 rounded-lg ${chip}`}>
            {cruce ? <RefreshCw size={15} /> : p.es_mi_pago ? <ArrowUpRight size={15} /> : <ArrowDownLeft size={15} />}
          </div>
          <div>
            <div className="text-sm font-bold text-surface-100">{label}</div>
            <div className="text-[11px] text-surface-500 flex items-center gap-1"><Calendar size={10} />{fecha(p.fecha_pago)}</div>
          </div>
        </div>
        <div className="text-right">
          <div className={`font-mono font-bold ${tone}`}>{signo}${fmt(p.monto_total)}</div>
          {cruce
            ? <div className="text-[10px] text-sky-300/70">no movió dinero</div>
            : p.sobrante > 0.01 && <div className="text-[10px] text-amber-300/80">a favor ${fmt(p.sobrante)}</div>}
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

function SummaryTile({ label, value, tone, icon, big, sub }: {
  label: string; value: string; tone: 'rose' | 'emerald' | 'indigo' | 'slate' | 'amber';
  icon?: React.ReactNode; big?: boolean; sub?: string;
}) {
  const toneMap = {
    rose: 'text-rose-400 from-rose-500/[0.04] to-transparent',
    emerald: 'text-emerald-400 from-emerald-500/[0.04] to-transparent',
    indigo: 'text-indigo-400 from-indigo-500/[0.04] to-transparent',
    slate: 'text-surface-300 from-surface-500/[0.04] to-transparent',
    amber: 'text-amber-400 from-amber-500/[0.04] to-transparent',
  };

  const toneTextMap = {
    rose: 'text-rose-400',
    emerald: 'text-emerald-400',
    indigo: 'text-indigo-400',
    slate: 'text-surface-300',
    amber: 'text-amber-400',
  };
  
  const iconColor = {
    rose: 'text-rose-400/80',
    emerald: 'text-emerald-400/80',
    indigo: 'text-indigo-400/80',
    slate: 'text-surface-500',
    amber: 'text-amber-400/80',
  };

  return (
    <div className={`relative overflow-hidden rounded-2xl bg-gradient-to-br ${toneMap[tone]} backdrop-blur-md border transition-all duration-300 hover:border-white/20 hover:scale-[1.01] px-4 py-3.5 ${big ? 'border-white/20 shadow-xl' : 'border-white/10 shadow-md'}`}>
      <div className="absolute top-0 right-0 w-24 h-24 bg-white/[0.005] rounded-full blur-xl pointer-events-none" />
      <div className={`flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider ${iconColor[tone]}`}>
        {icon}
        <span>{label}</span>
      </div>
      <div className={`font-mono font-bold mt-1.5 ${big ? 'text-2xl' : 'text-xl'} ${toneTextMap[tone]}`}>{value}</div>
      {sub && <div className="text-[10px] text-surface-500 mt-0.5 truncate">{sub}</div>}
    </div>
  );
}

function EmptyBox({ text }: { text: string }) {
  return <div className="text-center text-sm text-surface-500 border border-dashed border-white/5 rounded-xl bg-surface-900/20 py-6">{text}</div>;
}
