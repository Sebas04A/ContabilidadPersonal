import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  PiggyBank, Plus, TrendingDown, TrendingUp, Calendar, Wallet, Search,
  ArrowDownRight, ArrowUpRight, Flame, Target, Link2, X, Check, ListPlus, Tag, Pencil,
  FolderPlus, RefreshCw, CalendarRange, ChevronDown,
} from 'lucide-react';
import {
  useFunds, useFund, useAssignToFund, useCreateFund, useCategories, useTags, useUpdateFund,
  useGenerateFundPayments,
} from '../hooks/useTransactions';
import {
  api,
  type FundCiclo, type FundCicloModo, type FundListItem, type FundMovement, type Transaction,
} from '../services/api';
import { createPayment } from '../services/interpolated';
import FundFlattenChart from '../components/FundFlattenChart';
import { fmt } from '../utils/format';

// Identifies a fund member: a whole transaction, or a single split part.
const partKey = (t: Transaction) => `${t.id}::${t.split_group_id || ''}`;

const round2 = (n: number) => Math.round(n * 100) / 100;

export interface FlattenPayment {
  start: string; // income date
  end: string;   // expense date
  amount: number;
  ciclo_id: string | null;
}

export interface FlattenResult {
  dates: string[];
  raw: number[];        // raw running balance
  offset: number[];     // sum of active fixed-payments (the "pagos")
  flattened: number[];  // raw - offset
  payments: FlattenPayment[];
}

// An income only ends the current coverage window if it is "large" relative to the
// income that opened the window — at least this fraction of it. Smaller incomes
// (refunds, reversals, tiny transfers) are pooled into the current credit instead of
// resetting the window, so a monthly allowance keeps covering roughly its whole month.
const LARGE_INCOME_FRAC = 0.4;

/**
 * PREVIEW ONLY (no data changes): aplana el saldo con el enfoque de pagos fijos.
 *
 * La unidad de cobertura es la **ventana**, y hay dos formas de obtenerla:
 *
 * - **Con ciclos** (`ciclo: 'mensual'`): la ventana es el ciclo, con sus fronteras
 *   guardadas. Nada cruza de un ciclo al siguiente, así que el sobrante de un mes no
 *   puede acabar pagando el mes siguiente. Un mes sin ingreso se queda sin cubrir y se
 *   ve el bajón real, que es lo que de verdad pasó.
 * - **Sin ciclos** (`ciclo: 'ingreso'`, el default): cada ingreso "grande" abre una
 *   ventana que dura hasta el siguiente ingreso grande, y los pequeños se acumulan como
 *   crédito en vez de cerrarla. Es una heurística para adivinar dónde acaba un período
 *   cuando nadie lo ha dicho — y **no tiene tope temporal**: si nunca llega otro ingreso
 *   grande, la ventana se estira hasta el final de los datos. Ese es exactamente el
 *   goteo que los ciclos vienen a cortar.
 *
 * Dentro de una ventana, en los dos casos, el reparto va en dos pases:
 *
 *  1. Hacia adelante: el crédito de un ingreso cubre los gastos posteriores, con un
 *     offset POSITIVO sobre [ingreso, gasto) — aplana el pico del dinero parado.
 *  2. Hacia atrás: el gasto que quedó sin cubrir se pagó antes de que llegara su dinero,
 *     así que se empareja con un ingreso posterior, con offset NEGATIVO sobre
 *     [gasto, ingreso) — aplana el hundimiento.
 *
 * Restar el offset del saldo crudo cancela lo emparejado en las dos direcciones y deja
 * solo el exceso o el ahorro.
 */
/**
 * Los índices agrupados por ciclo, en orden, o `null` si el fondo no usa ciclos.
 *
 * Se agrupa por `ciclo_id` y no por tramos contiguos de índice a propósito: hoy los ciclos
 * son contiguos en el tiempo y los movimientos vienen ordenados por fecha, así que las dos
 * cosas coinciden — pero en cuanto una etiqueta pueda mandar un ingreso a otro ciclo, el
 * grupo dejará de ser un tramo y esto seguirá funcionando igual.
 */
function agruparPorCiclo(movs: FundMovement[]): number[][] | null {
  if (!movs.some(m => m.ciclo_id)) return null;
  const grupos = new Map<string, number[]>();
  movs.forEach((m, i) => {
    if (!m.ciclo_id) return;   // fuera de todo ciclo: sin cobertura, se ve el bajón real
    const actual = grupos.get(m.ciclo_id);
    if (actual) actual.push(i);
    else grupos.set(m.ciclo_id, [i]);
  });
  return [...grupos.values()];
}

function computeFlatten(movs: FundMovement[]): FlattenResult {
  const expenseRemaining = movs.map(m => (m.amount < 0 ? -m.amount : 0));
  const incomeRemaining = movs.map(m => (m.amount > 0 ? m.amount : 0));
  // Boundaries use the movement INDEX, not the date: several movements can share
  // the same day, so a date-based range would deactivate all same-day payments at
  // the first movement of that day and desync from the raw balance.
  const internal: { startIdx: number; endIdx: number; amount: number }[] = [];
  const payments: FlattenPayment[] = [];

  const addPayment = (startIdx: number, endIdx: number, amount: number) => {
    internal.push({ startIdx, endIdx, amount });
    payments.push({
      start: movs[startIdx].date,
      end: movs[endIdx].date,
      amount,
      // El ciclo del gasto: es el período al que se le imputa la cobertura, aunque el
      // dinero haya entrado en otra fecha.
      ciclo_id: movs[amount >= 0 ? endIdx : startIdx].ciclo_id,
    });
  };

  const ciclos = agruparPorCiclo(movs);

  if (ciclos) {
    // --- Con ciclos: la cobertura no cruza la frontera ---
    //
    // Aquí no hace falta la heurística del "ingreso grande": existía solo para adivinar
    // dónde acababa un período, y el ciclo ya lo dice. Todo el ingreso del ciclo es un
    // único crédito, y se reparte primero entre los gastos posteriores a cada ingreso
    // (pase 1) y luego entre los que se adelantaron a su dinero (pase 2).
    for (const indices of ciclos) {
      for (const k of indices) {
        if (movs[k].amount >= 0 || expenseRemaining[k] <= 0) continue;
        for (const m of indices) {
          if (m >= k) break;                     // solo ingresos que ya habían llegado
          if (expenseRemaining[k] <= 0) break;
          if (incomeRemaining[m] <= 0) continue;
          const cover = round2(Math.min(expenseRemaining[k], incomeRemaining[m]));
          addPayment(m, k, cover);
          incomeRemaining[m] = round2(incomeRemaining[m] - cover);
          expenseRemaining[k] = round2(expenseRemaining[k] - cover);
        }
      }
      for (const k of indices) {
        if (expenseRemaining[k] <= 0) continue;
        for (const j of indices) {
          if (j <= k) continue;
          if (expenseRemaining[k] <= 0) break;
          if (incomeRemaining[j] <= 0) continue;
          const cover = round2(Math.min(expenseRemaining[k], incomeRemaining[j]));
          // Negativo: el saldo crudo está ABAJO durante [gasto, ingreso), así que el
          // pago tiene que restar para que `raw - offset` vuelva al nivel.
          addPayment(k, j, -cover);
          expenseRemaining[k] = round2(expenseRemaining[k] - cover);
          incomeRemaining[j] = round2(incomeRemaining[j] - cover);
        }
      }
    }
  } else {
    // --- Sin ciclos: el emparejamiento secuencial de siempre ---
    // Pass 1: an income covers later expenses (upward spikes)
    let i = 0;
    while (i < movs.length) {
      if (movs[i].amount <= 0) { i++; continue; }
      // Open a window on this income. Its own amount anchors the "large" threshold, so
      // subsequent tiny incomes don't reset the window; only a comparably large income
      // (>= LARGE_INCOME_FRAC of the anchor) ends it. Small ones are pooled as credit.
      const groupStart = i;
      const anchor = movs[i].amount;
      const members = [i]; // income indices whose credit this window pools
      let remaining = anchor;
      i++;
      while (i < movs.length) {
        const amt = movs[i].amount;
        if (amt > 0) {
          if (amt >= LARGE_INCOME_FRAC * anchor) break; // large income -> new window
          remaining += amt;                             // small income -> pool as credit
          members.push(i);
        }
        i++;
      }
      const windowEnd = i; // index of the next large income, or movs.length

      for (let k = groupStart + 1; k < windowEnd && remaining > 0; k++) {
        if (movs[k].amount < 0 && expenseRemaining[k] > 0) {
          const cover = round2(Math.min(remaining, expenseRemaining[k]));
          remaining = round2(remaining - cover);
          expenseRemaining[k] = round2(expenseRemaining[k] - cover);
          // Draw the credit down from the pooled incomes (FIFO), emitting one payment per
          // chunk: each starts at the date of the income that actually funded it, so a
          // chunk coming from a pooled small income doesn't offset the days before it
          // arrived. Pass 2 then only sees credit that is genuinely left over.
          let left = cover;
          for (const m of members) {
            if (left <= 0) break;
            const take = round2(Math.min(left, incomeRemaining[m]));
            if (take <= 0) continue;
            addPayment(m, k, take);
            incomeRemaining[m] = round2(incomeRemaining[m] - take);
            left = round2(left - take);
          }
        }
      }
    }

    // Pass 2: expenses paid ahead of their income (downward dips)
    for (let k = 0; k < movs.length; k++) {
      if (expenseRemaining[k] <= 0) continue;
      for (let j = k + 1; j < movs.length && expenseRemaining[k] > 0; j++) {
        if (incomeRemaining[j] <= 0) continue;
        const cover = round2(Math.min(expenseRemaining[k], incomeRemaining[j]));
        // Negative offset: the raw balance is DOWN by `cover` over [expense, income),
        // so the payment must be negative for `raw - offset` to come back to level.
        addPayment(k, j, -cover);
        expenseRemaining[k] = round2(expenseRemaining[k] - cover);
        incomeRemaining[j] = round2(incomeRemaining[j] - cover);
      }
    }
  }

  // Both passes emit in their own order; sort so the list reads like a timeline.
  payments.sort((a, b) => (a.start < b.start ? -1 : a.start > b.start ? 1 : 0));

  const offsetAt = (j: number) =>
    internal.reduce((s, p) => s + (j >= p.startIdx && j < p.endIdx ? p.amount : 0), 0);

  const dates = movs.map(m => m.date);
  const raw = movs.map(m => m.running_balance);
  const offset = movs.map((_, j) => round2(offsetAt(j)));
  const flattened = raw.map((r, i) => round2(r - offset[i]));

  return { dates, raw, offset, flattened, payments };
}

export function Funds() {
  const { data: funds, isLoading } = useFunds();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const activeId = selectedId ?? funds?.[0]?.id ?? null;

  return (
    <div className="flex flex-col h-full bg-surface-950 relative overflow-hidden">
      <div className="fixed top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0">
        <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-emerald-600/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] left-[-5%] w-[400px] h-[400px] bg-primary-600/10 rounded-full blur-[100px]" />
      </div>

      <div className="flex h-full relative z-10">
        {/* LEFT: fund list */}
        <div className="w-80 shrink-0 border-r border-white/5 flex flex-col bg-surface-950/40">
          <div className="p-5 border-b border-white/5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400">
                <PiggyBank size={22} strokeWidth={1.5} />
              </div>
              <div>
                <h1 className="text-lg font-bold text-white leading-tight">Fondos</h1>
                <p className="text-[11px] text-surface-400">Seguimiento de saldos</p>
              </div>
            </div>
            <button
              onClick={() => setShowCreate(true)}
              className="p-2 rounded-lg bg-surface-800 hover:bg-emerald-600/20 text-surface-300 hover:text-emerald-300 transition-all"
              title="Nuevo fondo"
            >
              <Plus size={18} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
            {isLoading ? (
              <div className="flex justify-center py-10">
                <div className="w-6 h-6 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
              </div>
            ) : !funds || funds.length === 0 ? (
              <div className="text-center text-surface-500 text-sm py-10 px-4">
                <PiggyBank size={28} className="mx-auto mb-2 opacity-40" />
                No tienes fondos aún. Crea uno con el botón +.
              </div>
            ) : (
              funds.map(f => (
                <FundListCard
                  key={f.id}
                  fund={f}
                  active={f.id === activeId}
                  onClick={() => setSelectedId(f.id)}
                />
              ))
            )}
          </div>
        </div>

        {/* RIGHT: detail */}
        <div className="flex-1 min-w-0 overflow-hidden">
          {activeId ? (
            <FundDetail key={activeId} fundId={activeId} />
          ) : (
            <div className="flex items-center justify-center h-full text-surface-500">
              Selecciona o crea un fondo
            </div>
          )}
        </div>
      </div>

      {showCreate && <CreateFundModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}

function FundListCard({ fund, active, onClick }: { fund: FundListItem; active: boolean; onClick: () => void }) {
  const balance = fund.summary.balance;
  const positive = balance >= 0;
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-3.5 rounded-xl border transition-all ${
        active
          ? 'bg-surface-800/60 border-emerald-500/30'
          : 'bg-surface-900/40 border-white/5 hover:bg-surface-800/40 hover:border-white/10'
      }`}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="font-bold text-white text-sm truncate">{fund.name}</span>
        <span className={`font-mono font-bold text-sm ${positive ? 'text-emerald-400' : 'text-rose-400'}`}>
          {positive ? '' : '−'}${fmt(Math.abs(balance))}
        </span>
      </div>
      <div className="flex items-center justify-between text-[11px] text-surface-500">
        <span>{fund.summary.movement_count} movimientos</span>
        {fund.tag_vinculado
          ? <span className="flex items-center gap-1 text-violet-300"><Tag size={10} />{fund.tag_vinculado}</span>
          : <span>{positive ? 'a favor' : 'en rojo'}</span>}
      </div>
    </button>
  );
}

function FundDetail({ fundId }: { fundId: string }) {
  const [tab, setTab] = useState<'seguimiento' | 'asignar'>('seguimiento');
  const [viewStart, setViewStart] = useState('');
  const [showEdit, setShowEdit] = useState(false);
  const { data: fund, isLoading } = useFund(fundId, viewStart);

  if (isLoading || !fund) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-6 h-6 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
      </div>
    );
  }

  const s = fund.summary;
  const positive = s.balance >= 0;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-6 border-b border-white/5 shrink-0">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-2xl font-bold text-white">{fund.name}</h2>
              <button
                onClick={() => setShowEdit(true)}
                className="p-1.5 rounded-lg text-surface-500 hover:text-white hover:bg-white/5 transition-all"
                title="Editar fondo"
              >
                <Pencil size={16} />
              </button>
            </div>
            {fund.description && <p className="text-surface-400 text-sm mt-0.5">{fund.description}</p>}
            <div className="flex items-center gap-3 mt-1 flex-wrap">
              <p className="text-[11px] text-surface-500 flex items-center gap-1.5">
                <Calendar size={11} />
                Desde {fund.fecha_inicio || '—'} {fund.fecha_inicio_auto && <span className="text-surface-600">(automático)</span>}
              </p>
              {fund.tag_vinculado && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-violet-500/10 border border-violet-500/20 text-violet-300 flex items-center gap-1">
                  <Tag size={10} /> {fund.tag_vinculado}
                </span>
              )}
            </div>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-surface-500 uppercase tracking-wider font-bold">
              {fund.view_start ? 'Movido desde la fecha' : 'Saldo actual'}
            </p>
            <div className={`text-3xl font-mono font-bold ${positive ? 'text-emerald-400' : 'text-rose-400'}`}>
              {positive ? '' : '−'}${fmt(Math.abs(s.balance))}
            </div>
            <p className="text-[11px] text-surface-500">
              {fund.view_start
                ? (positive ? 'entró más de lo que gastaste' : 'gastaste más de lo que entró')
                : (positive ? 'a favor' : 'gastaste de más')}
            </p>
          </div>
        </div>

        {/* Tabs + view-date filter */}
        <div className="flex items-center justify-between gap-3 mt-5 flex-wrap">
          <div className="flex items-center gap-1 bg-surface-900 border border-white/10 rounded-xl p-1 w-fit">
            {(['seguimiento', 'asignar'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-all ${
                  tab === t ? 'bg-emerald-500/20 text-emerald-300' : 'text-surface-400 hover:text-white'
                }`}
              >
                {t === 'seguimiento' ? 'Seguimiento' : 'Asignar transacciones'}
              </button>
            ))}
          </div>

          {tab === 'seguimiento' && (
            <div className="flex items-center gap-2 bg-surface-900 border border-white/10 rounded-xl px-3 h-10">
              <Calendar size={15} className="text-surface-500" />
              <span className="text-[11px] text-surface-400 font-medium">Ver desde</span>
              <input
                type="date"
                value={viewStart}
                onChange={e => setViewStart(e.target.value)}
                className="bg-transparent border-none text-sm text-surface-200 focus:text-white focus:ring-0 cursor-pointer p-0 font-mono w-28"
              />
              {viewStart && (
                <button
                  onClick={() => setViewStart('')}
                  className="p-1 text-surface-500 hover:text-white rounded"
                  title="Quitar filtro de fecha"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {tab === 'seguimiento'
          ? <FundTracking fund={fund} />
          : <FundAssign fundId={fundId} currentBalance={s.balance} />}
      </div>

      {showEdit && <EditFundModal fund={fund} onClose={() => setShowEdit(false)} />}
    </div>
  );
}

function FundTracking({ fund }: { fund: import('../services/api').FundDetail }) {
  const [showManual, setShowManual] = useState(false);
  const [lines, setLines] = useState({ raw: true, offset: true, flattened: true });
  const s = fund.summary;
  const generateMutation = useGenerateFundPayments();
  const generated = fund.generated_payments;

  const reversed = useMemo(() => [...fund.movements].reverse(), [fund.movements]);

  // Preview-only flattened series + the fixed-payments it would create.
  const flat = useMemo(() => computeFlatten(fund.movements), [fund.movements]);

  const materialize = () => {
    if (flat.payments.length === 0) return;
    generateMutation.mutate({
      fundId: fund.id,
      payments: flat.payments.map(p => ({
        start: p.start, end: p.end, amount: p.amount, ciclo_id: p.ciclo_id,
      })),
    });
  };

  return (
    <div className="p-6 space-y-6">
      {/* Metric tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Tile icon={<ArrowUpRight size={14} />} label="Recibido" value={`$${fmt(s.total_in)}`} tone="emerald" />
        <Tile icon={<ArrowDownRight size={14} />} label="Gastado" value={`$${fmt(s.total_out)}`} tone="rose" />
        <Tile
          icon={<Flame size={14} />}
          label="Ritmo semanal"
          value={s.burn_rate_weekly != null ? `$${fmt(s.burn_rate_weekly)}` : '—'}
          tone="amber"
        />
        <Tile
          icon={<Target size={14} />}
          label="Proyección"
          value={
            s.projection == null
              ? 'sin datos'
              : s.projection.status === 'deficit'
                ? 'en déficit'
                : `~${s.projection.weeks_left} sem`
          }
          sub={s.projection?.status === 'surplus' ? `agota ${s.projection.runs_out_on}` : undefined}
          tone={s.projection?.status === 'deficit' ? 'rose' : 'primary'}
        />
      </div>

      {fund.ciclos.length > 0 && <CiclosPanel ciclos={fund.ciclos} />}

      {/* Flattened chart + line toggles + payments list (client-side, no data changes) */}
      {flat.dates.length > 0 ? (
        <div className="bg-surface-900/40 border border-dashed border-violet-500/30 rounded-2xl p-4">
          <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              Vista aplanada
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-300 uppercase">previsualización</span>
            </h3>
            <div className="flex items-center gap-1.5">
              <LineToggle label="Crudo" color="#64748b" active={lines.raw} onClick={() => setLines(l => ({ ...l, raw: !l.raw }))} />
              <LineToggle label="Pagos" color="#a78bfa" active={lines.offset} onClick={() => setLines(l => ({ ...l, offset: !l.offset }))} />
              <LineToggle label="Aplanado" color="#34d399" active={lines.flattened} onClick={() => setLines(l => ({ ...l, flattened: !l.flattened }))} />
            </div>
          </div>
          <div className="h-[280px]">
            <FundFlattenChart dates={flat.dates} raw={flat.raw} offset={flat.offset} flattened={flat.flattened} visible={lines} />
          </div>

          {/* Payments that would be created */}
          <div className="mt-3">
            <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-bold text-violet-300 uppercase tracking-wide">Pagos a crear ({flat.payments.length})</span>
                <span className="text-[11px] text-surface-500">cada gasto se empareja con el ingreso que lo cubre, antes o después</span>
                {generated && (
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 flex items-center gap-1">
                    <Check size={10} /> {generated.payment_count} creados en «{generated.name}»
                  </span>
                )}
              </div>
              <button
                onClick={materialize}
                disabled={flat.payments.length === 0 || generateMutation.isPending}
                title={generated
                  ? 'Regenera el grupo de pagos: reemplaza los pagos anteriores por el estado actual'
                  : 'Crea estos pagos en un grupo nuevo asociado a este fondo'}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold disabled:opacity-50 transition-all shrink-0"
              >
                {generateMutation.isPending
                  ? <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  : generated ? <RefreshCw size={14} /> : <FolderPlus size={14} />}
                {generated ? 'Regenerar pagos' : 'Crear pagos'}
              </button>
            </div>
            {flat.payments.length === 0 ? (
              <p className="text-[11px] text-surface-500">No hay ingresos que emparejar con gastos en este fondo.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 max-h-52 overflow-y-auto custom-scrollbar">
                {flat.payments.map((p, i) => (
                  <div key={i} className="flex items-center justify-between gap-2 text-[11px] bg-surface-950/40 border border-white/5 rounded-lg px-2.5 py-1.5">
                    <span className="text-surface-400 font-mono flex items-center gap-1">
                      {p.start} <span className="text-surface-600">→</span> {p.end}
                    </span>
                    {/* Negative = the gasto came first and a later ingreso repaid it. */}
                    <span
                      className={`font-mono font-bold ${p.amount < 0 ? 'text-amber-300' : 'text-violet-300'}`}
                      title={p.amount < 0 ? 'Gasto adelantado: el ingreso que lo cubre llega después' : 'Ingreso que cubre un gasto posterior'}
                    >
                      {p.amount < 0 ? '−' : ''}${fmt(Math.abs(p.amount))}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <p className="text-[11px] text-surface-500 mt-3">
            Cada pago cubre un ingreso hasta el gasto que lo consume; si el gasto ocurrió <em>antes</em> que su ingreso, el pago sale
            en <span className="text-amber-300 font-semibold">negativo</span> y cubre el tramo inverso. Con <span className="text-violet-300 font-semibold">Crear pagos</span> se
            materializan en un grupo <span className="text-surface-400">fixed</span> aparte, vinculado a este fondo, que alimenta el dashboard. Regenerar reemplaza el grupo anterior.
          </p>
        </div>
      ) : (
        <div className="flex items-center justify-center h-40 text-surface-500 text-sm border border-dashed border-white/5 rounded-2xl">
          Sin movimientos todavía
        </div>
      )}

      {/* Extracto */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-white">Extracto ({fund.movements.length})</h3>
          <button
            onClick={() => setShowManual(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-800 hover:bg-emerald-600/20 text-surface-300 hover:text-emerald-300 text-xs font-semibold transition-all"
          >
            <Plus size={14} /> Movimiento manual
          </button>
        </div>
        <div className="space-y-2">
          {reversed.map(m => <MovementRow key={`${m.source}-${m.id}-${m.date}`} m={m} />)}
          {fund.movements.length === 0 && (
            <div className="text-center text-surface-500 text-sm py-8 border border-dashed border-white/5 rounded-xl">
              Aún no hay movimientos. Asigna transacciones o agrega uno manual.
            </div>
          )}
        </div>
      </div>

      {showManual && <ManualMovementModal fundId={fund.id} onClose={() => setShowManual(false)} />}
    </div>
  );
}

/** El último día que el ciclo incluye. `fin` es exclusivo, y enseñárselo a un humano
 *  como si fuera el final haría que cada mes pareciera acabar un día tarde. */
function ultimoDia(fin: string): string {
  const d = new Date(`${fin}T00:00:00`);
  d.setDate(d.getDate() - 1);
  return d.toISOString().substring(0, 10);
}

function CiclosPanel({ ciclos }: { ciclos: FundCiclo[] }) {
  const [abierto, setAbierto] = useState(true);
  // Del más reciente al más antiguo: lo que se mira es el mes en curso.
  const recientes = useMemo(() => [...ciclos].reverse(), [ciclos]);
  const secos = recientes.filter(c => c.credito === 0 && c.gasto > 0).length;

  return (
    <div className="bg-surface-900/40 border border-white/10 rounded-2xl overflow-hidden">
      <button
        onClick={() => setAbierto(a => !a)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors"
      >
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <CalendarRange size={15} className="text-primary-400" />
          Ciclos ({ciclos.length})
        </h3>
        <div className="flex items-center gap-2">
          {secos > 0 && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-500/10 text-rose-300">
              {secos} sin ingreso
            </span>
          )}
          <ChevronDown
            size={16}
            className={`text-surface-500 transition-transform ${abierto ? 'rotate-180' : ''}`}
          />
        </div>
      </button>

      {abierto && (
        <div className="border-t border-white/5 divide-y divide-white/5 max-h-72 overflow-y-auto custom-scrollbar">
          {recientes.map(c => <CicloRow key={c.id} c={c} />)}
        </div>
      )}
    </div>
  );
}

function CicloRow({ c }: { c: FundCiclo }) {
  // Un ciclo sin ingreso es el síntoma que trajo todo esto: antes se tapaba con el
  // sobrante del mes anterior y no se veía. Ahora se dice.
  const seco = c.credito === 0 && c.gasto > 0;

  return (
    <div className="flex items-center gap-3 px-4 py-2.5">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[12px] text-surface-200">
            {c.inicio} <span className="text-surface-600">→</span> {ultimoDia(c.fin)}
          </span>
          {c.en_curso && (
            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-primary-500/10 text-primary-300 uppercase tracking-wide">
              en curso
            </span>
          )}
          {seco && (
            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-300 uppercase tracking-wide">
              sin ingreso
            </span>
          )}
        </div>
        {c.nota && <span className="text-[11px] text-surface-500">{c.nota}</span>}
      </div>

      <div className="flex items-center gap-4 shrink-0 text-right">
        <div>
          <div className="text-[9px] text-surface-600 uppercase tracking-wider font-bold">Entró</div>
          <div className="font-mono text-[12px] text-emerald-400">${fmt(c.credito)}</div>
        </div>
        <div>
          <div className="text-[9px] text-surface-600 uppercase tracking-wider font-bold">Gastó</div>
          <div className="font-mono text-[12px] text-rose-400">${fmt(c.gasto)}</div>
        </div>
        <div className="w-24">
          {c.sin_cubrir > 0 ? (
            <>
              <div className="text-[9px] text-surface-600 uppercase tracking-wider font-bold">Sin cubrir</div>
              <div className="font-mono text-[12px] font-bold text-amber-300">${fmt(c.sin_cubrir)}</div>
            </>
          ) : c.sobrante > 0 ? (
            <>
              <div className="text-[9px] text-surface-600 uppercase tracking-wider font-bold">Sobra</div>
              <div className="font-mono text-[12px] font-bold text-emerald-300">${fmt(c.sobrante)}</div>
            </>
          ) : (
            <>
              <div className="text-[9px] text-surface-600 uppercase tracking-wider font-bold">Cuadrado</div>
              <div className="font-mono text-[12px] text-surface-500">—</div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function MovementRow({ m }: { m: FundMovement }) {
  const income = m.amount >= 0;
  return (
    <div className="flex items-center gap-3 p-3 rounded-xl bg-surface-900/40 border border-white/5">
      <div className={`p-1.5 rounded-lg ${income ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
        {income ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm text-surface-100 truncate">{m.note || '(sin nota)'}</span>
          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide shrink-0 ${
            m.source === 'manual' ? 'bg-sky-500/10 text-sky-300'
              : m.source === 'tag' ? 'bg-violet-500/10 text-violet-300'
              : 'bg-white/5 text-surface-400'
          }`}>
            {m.source === 'manual' ? 'manual' : m.source === 'tag' ? 'tag' : 'transacción'}
          </span>
          {m.source === 'transaction' && !m.reviewed && (
            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 shrink-0">sin revisar</span>
          )}
        </div>
        <span className="text-[11px] text-surface-500 flex items-center gap-1"><Calendar size={10} />{m.date}</span>
      </div>
      <div className="text-right shrink-0">
        <div className={`font-mono font-bold text-sm ${income ? 'text-emerald-400' : 'text-rose-400'}`}>
          {income ? '+' : '−'}${fmt(Math.abs(m.amount))}
        </div>
        <div className="text-[11px] font-mono text-surface-500">saldo ${fmt(m.running_balance)}</div>
      </div>
    </div>
  );
}

function FundAssign({ fundId, currentBalance }: { fundId: string; currentBalance: number }) {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [tag, setTag] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const { data: categories } = useCategories();
  const { data: tags } = useTags();
  const assignMutation = useAssignToFund();
  const queryClient = useQueryClient();

  const { data: results, isFetching } = useQuery({
    queryKey: ['fund-candidates', search, category, tag],
    queryFn: () => api.getTransactions(
      undefined, undefined, undefined, undefined, undefined, undefined,
      search || undefined, category || undefined, tag || undefined
    ),
    enabled: search.length > 0 || category.length > 0 || tag.length > 0,
  });

  const toggle = (key: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const sortedResults = useMemo(
    () => [...(results ?? [])].sort((a, b) => (b.FECHA || '').localeCompare(a.FECHA || '')),
    [results],
  );

  const selectableResults = useMemo(
    () => sortedResults.filter(t => !t.es_reembolsable),
    [sortedResults],
  );

  const allSelected = selectableResults.length > 0 && selectableResults.every(t => selected.has(partKey(t)));

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      const next = new Set<string>();
      selectableResults.forEach(t => next.add(partKey(t)));
      setSelected(next);
    }
  };

  // Ids appearing more than once = split transactions (each row is one part).
  const splitIds = useMemo(() => {
    const counts = new Map<string, number>();
    (results ?? []).forEach(t => counts.set(t.id, (counts.get(t.id) ?? 0) + 1));
    return new Set([...counts.entries()].filter(([, n]) => n > 1).map(([id]) => id));
  }, [results]);

  const selectedTx = useMemo(
    () => (results ?? []).filter(t => selected.has(partKey(t))),
    [results, selected],
  );
  const previewDelta = selectedTx.reduce((acc, t) => acc + t.MONTO, 0);

  const runAssign = async (assign: boolean) => {
    if (selectedTx.length === 0) return;
    const parts = selectedTx.map(t => ({ transaction_id: t.id, split_group_id: t.split_group_id || null }));
    await assignMutation.mutateAsync({ fundId, parts, assign });
    setSelected(new Set());
    queryClient.invalidateQueries({ queryKey: ['fund-candidates'] });
  };

  return (
    <div className="p-6 space-y-4">
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-2">
        <div className="flex-[2] relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" size={16} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar transacciones por concepto..."
            className="w-full h-11 bg-surface-900/40 border border-white/10 rounded-xl pl-10 pr-3 text-surface-100 text-sm focus:border-emerald-500/40 focus:ring-0"
          />
        </div>
        <select
          value={category}
          onChange={e => setCategory(e.target.value)}
          className="flex-1 h-11 bg-surface-900/40 border border-white/10 rounded-xl px-3 text-surface-200 text-sm focus:ring-0"
        >
          <option value="">Todas las categorías</option>
          {(categories ?? []).map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select
          value={tag}
          onChange={e => setTag(e.target.value)}
          className="flex-1 h-11 bg-surface-900/40 border border-white/10 rounded-xl px-3 text-surface-200 text-sm focus:ring-0"
        >
          <option value="">Todos los tags</option>
          {(tags ?? []).map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {/* Preview bar */}
      {selected.size > 0 && (
        <div className="flex items-center justify-between gap-3 p-3 rounded-xl bg-emerald-500/[0.06] border border-emerald-500/20">
          <div className="text-sm text-surface-200">
            <span className="font-bold">{selected.size}</span> seleccionadas ·
            impacto <span className={`font-mono font-bold ${previewDelta >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {previewDelta >= 0 ? '+' : '−'}${fmt(Math.abs(previewDelta))}
            </span> →
            saldo quedaría <span className="font-mono font-bold text-white">${fmt(currentBalance + previewDelta)}</span>
          </div>
          <div className="flex gap-2 shrink-0">
            <button
              onClick={() => runAssign(true)}
              disabled={assignMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold disabled:opacity-50"
            >
              <ListPlus size={14} /> Asignar al fondo
            </button>
            <button
              onClick={() => runAssign(false)}
              disabled={assignMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-800 hover:bg-rose-600/20 text-surface-300 hover:text-rose-300 text-xs font-bold disabled:opacity-50"
            >
              <X size={14} /> Quitar del fondo
            </button>
          </div>
        </div>
      )}

      {/* Candidate list */}
      <div className="space-y-2">
        {isFetching ? (
          <div className="flex justify-center py-8">
            <div className="w-5 h-5 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
          </div>
        ) : !results ? (
          <div className="text-center text-surface-500 text-sm py-10">
            Busca por concepto o filtra por categoría o tag para encontrar transacciones que asignar.
          </div>
        ) : results.length === 0 ? (
          <div className="text-center text-surface-500 text-sm py-10">Sin resultados.</div>
        ) : (
          <>
            <div className="flex items-center justify-between px-1 pb-1">
              <span className="text-xs font-semibold text-surface-400">
                {sortedResults.length} transacciones encontradas
              </span>
              {selectableResults.length > 0 && (
                <button
                  onClick={toggleSelectAll}
                  className="flex items-center gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 font-semibold px-2.5 py-1 rounded-lg bg-surface-900/60 hover:bg-surface-800 border border-white/10 transition-all"
                >
                  <Check size={13} />
                  {allSelected ? 'Desmarcar todo' : 'Seleccionar todo'}
                </button>
              )}
            </div>
            {sortedResults.map((t, idx) => (
              <CandidateRow
                key={`${partKey(t)}-${idx}`}
                tx={t}
                fundId={fundId}
                isSplit={splitIds.has(t.id)}
                checked={selected.has(partKey(t))}
                onToggle={() => toggle(partKey(t))}
              />
            ))}
          </>
        )}
      </div>
    </div>
  );
}

function CandidateRow({ tx, fundId, checked, onToggle, isSplit }: {
  tx: Transaction; fundId: string; checked: boolean; onToggle: () => void; isSplit?: boolean;
}) {
  const assignedHere = tx.fondo_id === fundId;
  const assignedElsewhere = !!tx.fondo_id && tx.fondo_id !== fundId;
  const income = tx.MONTO >= 0;
  const refundable = !!tx.es_reembolsable;

  return (
    <button
      onClick={refundable ? undefined : onToggle}
      disabled={refundable}
      title={refundable ? 'Reembolsable: pertenece a Deudas, no cuenta en el fondo' : undefined}
      className={`w-full flex items-center gap-3 p-3 rounded-xl border text-left transition-all ${
        refundable
          ? 'bg-rose-500/[0.05] border-rose-500/20 opacity-70 cursor-not-allowed'
          : checked
            ? 'bg-emerald-500/[0.08] border-emerald-500/30'
            : 'bg-surface-900/40 border-white/5 hover:border-white/10'
      }`}
    >
      <div className={`w-5 h-5 rounded border flex items-center justify-center shrink-0 ${
        refundable ? 'border-rose-500/30 bg-rose-500/10'
          : checked ? 'bg-emerald-500 border-emerald-500' : 'border-white/20'
      }`}>
        {refundable ? <X size={12} className="text-rose-300" /> : checked ? <Check size={14} className="text-white" /> : null}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-sm truncate ${refundable ? 'text-rose-200/80' : 'text-surface-100'}`}>{tx.nombre_limpio || tx.DESCRIPCION}</span>
          {isSplit && !refundable && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 shrink-0">parte</span>}
          {refundable && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-300 shrink-0">reembolsable</span>}
          {assignedHere && !refundable && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 shrink-0 flex items-center gap-1"><Link2 size={9} />en este fondo</span>}
          {assignedElsewhere && !refundable && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 shrink-0">otro fondo</span>}
        </div>
        <span className="text-[11px] text-surface-500 flex items-center gap-1"><Calendar size={10} />{tx.FECHA?.substring(0, 10)}{tx.categoria ? ` · ${tx.categoria}` : ''}{tx.tags ? ` · ${tx.tags}` : ''}</span>
      </div>
      <div className={`font-mono font-bold text-sm shrink-0 ${refundable ? 'text-rose-300/70' : income ? 'text-emerald-400' : 'text-rose-400'}`}>
        {income ? '+' : '−'}${fmt(Math.abs(tx.MONTO))}
      </div>
    </button>
  );
}

function Tile({ icon, label, value, sub, tone }: {
  icon: React.ReactNode; label: string; value: string; sub?: string;
  tone: 'emerald' | 'rose' | 'amber' | 'primary';
}) {
  const toneMap = { emerald: 'text-emerald-400', rose: 'text-rose-400', amber: 'text-amber-400', primary: 'text-primary-400' };
  return (
    <div className="rounded-2xl bg-surface-900/40 border border-white/10 px-4 py-3">
      <div className="flex items-center gap-1.5 text-[10px] text-surface-500 uppercase tracking-wider font-bold">
        {icon}{label}
      </div>
      <div className={`text-lg font-mono font-bold ${toneMap[tone]}`}>{value}</div>
      {sub && <div className="text-[10px] text-surface-500 truncate">{sub}</div>}
    </div>
  );
}

function LineToggle({ label, color, active, onClick }: {
  label: string; color: string; active: boolean; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-semibold transition-all ${
        active ? 'bg-surface-800 border-white/10 text-white' : 'bg-transparent border-white/5 text-surface-500'
      }`}
    >
      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: active ? color : 'transparent', border: `1.5px solid ${color}` }} />
      {label}
    </button>
  );
}

function EditFundModal({ fund, onClose }: { fund: import('../services/api').FundDetail; onClose: () => void }) {
  const [name, setName] = useState(fund.name);
  const [description, setDescription] = useState(fund.description || '');
  const [fechaInicio, setFechaInicio] = useState(fund.fecha_inicio_auto ? '' : (fund.fecha_inicio || ''));
  const [tag, setTag] = useState(fund.tag_vinculado || '');
  const [ciclo, setCiclo] = useState<FundCicloModo>(fund.ciclo);
  const [diaCorte, setDiaCorte] = useState(String(fund.dia_corte_default || 1));
  const { data: tags } = useTags();
  const updateMutation = useUpdateFund();

  const submit = async () => {
    if (!name.trim()) return;
    await updateMutation.mutateAsync({
      id: fund.id,
      updates: {
        name: name.trim(),
        description: description.trim(),
        fecha_inicio: fechaInicio || null,
        tag_vinculado: tag || null,
        ciclo,
        dia_corte_default: Number(diaCorte) || 1,
      },
    });
    onClose();
  };

  return (
    <ModalShell title="Editar fondo" icon={<Pencil size={18} className="text-emerald-400" />} onClose={onClose}>
      <Field label="Título">
        <input autoFocus value={name} onChange={e => setName(e.target.value)} className={inputCls} />
      </Field>
      <Field label="Descripción">
        <input value={description} onChange={e => setDescription(e.target.value)} className={inputCls} placeholder="Para qué es este fondo" />
      </Field>
      <Field label="Fecha de inicio (vacía = automática, desde el primer movimiento)">
        <input type="date" value={fechaInicio} onChange={e => setFechaInicio(e.target.value)} className={inputCls} />
      </Field>
      <Field label="Tag vinculado (opcional)">
        <select value={tag} onChange={e => setTag(e.target.value)} className={inputCls}>
          <option value="">Sin tag</option>
          {(tags ?? []).map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </Field>
      <CicloFields
        ciclo={ciclo} setCiclo={setCiclo}
        diaCorte={diaCorte} setDiaCorte={setDiaCorte}
      />
      <ModalActions onClose={onClose} onSubmit={submit} loading={updateMutation.isPending} disabled={!name.trim()} submitLabel="Guardar cambios" />
    </ModalShell>
  );
}

function CreateFundModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [fechaInicio, setFechaInicio] = useState('');
  const [tag, setTag] = useState('');
  const [ciclo, setCiclo] = useState<FundCicloModo>('ingreso');
  const [diaCorte, setDiaCorte] = useState('1');
  const { data: tags } = useTags();
  const createMutation = useCreateFund();

  const submit = async () => {
    if (!name.trim()) return;
    await createMutation.mutateAsync({
      name: name.trim(),
      description: description.trim() || undefined,
      fecha_inicio: fechaInicio || null,
      tag_vinculado: tag || null,
      ciclo,
      dia_corte_default: ciclo === 'mensual' ? (Number(diaCorte) || 1) : null,
    });
    onClose();
  };

  return (
    <ModalShell title="Nuevo fondo" icon={<PiggyBank size={20} className="text-emerald-400" />} onClose={onClose}>
      <Field label="Nombre">
        <input autoFocus value={name} onChange={e => setName(e.target.value)} className={inputCls} placeholder="Ej: Gasolina" />
      </Field>
      <Field label="Descripción (opcional)">
        <input value={description} onChange={e => setDescription(e.target.value)} className={inputCls} placeholder="Para qué es este fondo" />
      </Field>
      <Field label="Tag vinculado (opcional — incluye automáticamente toda transacción con este tag)">
        <select value={tag} onChange={e => setTag(e.target.value)} className={inputCls}>
          <option value="">Sin tag (asignación manual)</option>
          {(tags ?? []).map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </Field>
      <Field label="Fecha de inicio (opcional — si la dejas vacía, se usa el primer movimiento)">
        <input type="date" value={fechaInicio} onChange={e => setFechaInicio(e.target.value)} className={inputCls} />
      </Field>
      <CicloFields
        ciclo={ciclo} setCiclo={setCiclo}
        diaCorte={diaCorte} setDiaCorte={setDiaCorte}
      />
      <ModalActions onClose={onClose} onSubmit={submit} loading={createMutation.isPending} disabled={!name.trim()} submitLabel="Crear fondo" />
    </ModalShell>
  );
}

function ManualMovementModal({ fundId, onClose }: { fundId: string; onClose: () => void }) {
  const [kind, setKind] = useState<'in' | 'out'>('in');
  const [amount, setAmount] = useState('');
  const [date, setDate] = useState(new Date().toISOString().substring(0, 10));
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(false);
  const queryClient = useQueryClient();

  const submit = async () => {
    const value = parseFloat(amount);
    if (!value || value <= 0) return;
    setLoading(true);
    try {
      const signed = kind === 'in' ? Math.abs(value) : -Math.abs(value);
      await createPayment(fundId, { amount: signed, start_date: date, end_date: date, note: note || (kind === 'in' ? 'Transferencia' : 'Gasto') });
      queryClient.invalidateQueries({ queryKey: ['fund', fundId] });
      queryClient.invalidateQueries({ queryKey: ['funds'] });
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModalShell title="Movimiento manual" icon={<Wallet size={20} className="text-emerald-400" />} onClose={onClose}>
      <div className="flex gap-2">
        <button onClick={() => setKind('in')} className={`flex-1 py-2 rounded-lg text-sm font-bold flex items-center justify-center gap-1.5 ${kind === 'in' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-surface-800 text-surface-400'}`}>
          <TrendingUp size={14} /> Entrada
        </button>
        <button onClick={() => setKind('out')} className={`flex-1 py-2 rounded-lg text-sm font-bold flex items-center justify-center gap-1.5 ${kind === 'out' ? 'bg-rose-500/20 text-rose-300' : 'bg-surface-800 text-surface-400'}`}>
          <TrendingDown size={14} /> Salida
        </button>
      </div>
      <Field label="Monto">
        <input autoFocus type="number" value={amount} onChange={e => setAmount(e.target.value)} className={inputCls} placeholder="0.00" />
      </Field>
      <Field label="Fecha">
        <input type="date" value={date} onChange={e => setDate(e.target.value)} className={inputCls} />
      </Field>
      <Field label="Nota (opcional)">
        <input value={note} onChange={e => setNote(e.target.value)} className={inputCls} placeholder="Descripción" />
      </Field>
      <p className="text-[11px] text-surface-500">
        Usa esto solo para dinero que no está en tus transacciones (transferencias/ajustes), para no duplicar.
      </p>
      <ModalActions onClose={onClose} onSubmit={submit} loading={loading} disabled={!amount} submitLabel="Guardar" />
    </ModalShell>
  );
}

/** Los defaults de generación de ciclos. Cambiarlos no reinterpreta el pasado: los ciclos
 *  ya escritos llevan sus fronteras guardadas y solo se tocan moviéndolas a mano. */
function CicloFields({ ciclo, setCiclo, diaCorte, setDiaCorte }: {
  ciclo: FundCicloModo; setCiclo: (v: FundCicloModo) => void;
  diaCorte: string; setDiaCorte: (v: string) => void;
}) {
  return (
    <>
      <Field label="Ciclo">
        <select
          value={ciclo}
          onChange={e => setCiclo(e.target.value as FundCicloModo)}
          className={inputCls}
        >
          <option value="ingreso">Por ingreso — cada ingreso abre su ventana (como antes)</option>
          <option value="mensual">Mensual — la cobertura no cruza de un mes al siguiente</option>
          <option value="ninguno">Ninguno — sin emparejamiento automático</option>
        </select>
      </Field>
      {ciclo === 'mensual' && (
        <Field label="Día de corte para los ciclos nuevos (1–31)">
          <input
            type="number" min={1} max={31}
            value={diaCorte}
            onChange={e => setDiaCorte(e.target.value)}
            className={inputCls}
          />
          <p className="text-[11px] text-surface-500 mt-1.5">
            Solo afecta a los ciclos que aún no existen. Los que ya están guardan sus
            propias fronteras, así que cambiar esto no toca el pasado.
          </p>
        </Field>
      )}
    </>
  );
}

// ── Small shared modal primitives ─────────────────────────────────────────────
const inputCls = 'w-full bg-surface-950 border border-white/10 rounded-xl px-3.5 py-2.5 text-white text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500/40';

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[11px] font-semibold text-surface-400 mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function ModalShell({ title, icon, onClose, children }: { title: string; icon: React.ReactNode; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-surface-900/95 backdrop-blur-xl rounded-2xl shadow-2xl w-full max-w-md border border-white/10" onClick={e => e.stopPropagation()}>
        <div className="p-5 border-b border-white/10 flex items-center justify-between">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">{icon}{title}</h3>
          <button onClick={onClose} className="p-1.5 text-surface-400 hover:text-white rounded-lg hover:bg-white/5"><X size={20} /></button>
        </div>
        <div className="p-5 space-y-4">{children}</div>
      </div>
    </div>
  );
}

function ModalActions({ onClose, onSubmit, loading, disabled, submitLabel }: {
  onClose: () => void; onSubmit: () => void; loading: boolean; disabled: boolean; submitLabel: string;
}) {
  return (
    <div className="flex justify-end gap-2 pt-2">
      <button onClick={onClose} className="px-4 py-2 text-sm text-surface-300 hover:text-white rounded-lg hover:bg-white/5">Cancelar</button>
      <button
        onClick={onSubmit}
        disabled={loading || disabled}
        className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold rounded-lg disabled:opacity-50 flex items-center gap-2"
      >
        {loading && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
        {submitLabel}
      </button>
    </div>
  );
}
