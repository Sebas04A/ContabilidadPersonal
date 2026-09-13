import { useMemo } from 'react';
import { Transaction, SupabaseDebt, SupabasePayment, FundListItem, TransactionDriver, ComponentType } from '../services/api';
import { useSupabaseDebts, useSupabasePayments, useFunds } from '../hooks/useTransactions';
import { matchFund } from '../utils/matchFund';
import {
  Calendar, HandCoins, PiggyBank, TrendingUp, ArrowRight, CheckCircle2, Clock, AlertTriangle, Banknote,
} from 'lucide-react';

/**
 * PROTOTYPE (read-only): an enriched ledger. Each transaction is shown with cross
 * references — if it looks like a debt/reimbursement (matched to a Supabase debt by
 * amount + date), if it feeds/comes from a fund, or if it's an investment. The point
 * is to give more context per row than the plain list, without touching anything else.
 */

// --- helpers ---------------------------------------------------------------

function normalize(s: string | null | undefined): string {
  if (!s) return '';
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').trim().toLowerCase();
}

const AMOUNT_TOL_FRAC = 0.10; // a debt matches if amounts are within 10%

function dayOf(value: string | null | undefined): string {
  return (value || '').slice(0, 10); // YYYY-MM-DD
}

function fmtSigned(v: number): string {
  return `${v >= 0 ? '+' : '−'}$${Math.abs(v).toLocaleString('es-CO', { minimumFractionDigits: 2 })}`;
}

/** Splits a fixed-payment driver description "note (group)" into its parts. */
function splitPagoDesc(desc: string): { main: string; group: string } {
  const m = desc.match(/^(.*)\s\(([^)]*)\)\s*$/);
  return m ? { main: m[1], group: m[2] } : { main: desc, group: '' };
}

type NetInfo = { kind: 'dup' | 'net' | 'debt' | 'pago' | 'inv' | 'raw'; value: number };

/** Renders a row's contribution to the total (fund/debt/investment net / raw / already-counted). */
function AporteValue({ nb, fundName, size = 'sm', showTag = true }: {
  nb: NetInfo; fundName?: string; size?: 'sm' | 'lg'; showTag?: boolean;
}) {
  if (nb.kind === 'dup') {
    return (
      <span className={`text-surface-600 italic ${size === 'lg' ? 'text-sm' : 'text-xs'}`} title="Ya contado arriba en el neto de su grupo">
        ↳ ya contado
      </span>
    );
  }
  const isFundNet = nb.kind === 'net';
  const isDebt = nb.kind === 'debt';
  const isInv = nb.kind === 'inv';
  const isPago = nb.kind === 'pago';
  const emphasized = isFundNet || isDebt || isInv || isPago;
  const valueCls = size === 'lg'
    ? 'text-lg font-bold'
    : emphasized ? 'text-base font-bold' : 'text-xs font-medium opacity-70';
  return (
    <span className="inline-flex items-center justify-end gap-1.5">
      {showTag && isFundNet && <span className="text-[8px] font-bold uppercase tracking-wide px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-300/80 border border-emerald-500/20">neto</span>}
      {showTag && isDebt && <span className="text-[8px] font-bold uppercase tracking-wide px-1 py-0.5 rounded bg-rose-500/10 text-rose-300/80 border border-rose-500/20">deuda</span>}
      {showTag && isPago && <span className="text-[8px] font-bold uppercase tracking-wide px-1 py-0.5 rounded bg-sky-500/10 text-sky-300/80 border border-sky-500/20">pago</span>}
      {showTag && isInv && <span className="text-[8px] font-bold uppercase tracking-wide px-1 py-0.5 rounded bg-amber-500/10 text-amber-300/80 border border-amber-500/20">inv.</span>}
      <span
        className={`font-mono tabular-nums ${valueCls} ${nb.value >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}
        title={isFundNet ? `Fondo ${fundName}: ingreso del día − pagos fijos generados`
          : isDebt ? 'Deuda: gasto de la transacción + monto en Supabase (como ingreso)'
          : isPago ? 'Pago: monto de la transacción − pago en Supabase (el pago baja la deuda acumulada)'
          : isInv ? 'Inversión: transacciones del día − pagos fijos de inversión'
          : 'Transacción no-fondo: aporta su monto al total'}
      >
        {fmtSigned(nb.value)}
      </span>
    </span>
  );
}

function hasInvestmentMark(t: Transaction): boolean {
  const cat = normalize(t.categoria);
  const tags = normalize(t.tags);
  return cat.includes('inversion') || tags.includes('inversion');
}

/** Card payment (categoría "Tarjeta"): an internal transfer bank→card, not a real
 *  income/expense, so it's excluded from the ledger and the total. */
function isCardPayment(t: Transaction): boolean {
  return normalize(t.categoria) === 'tarjeta';
}

interface DebtMatch {
  debt: SupabaseDebt;
  amountDiff: number;
}

/** Best Supabase debt for a transaction: the one it is explicitly linked to (`deuda_id`),
 *  or, for an unlinked reimbursable row, SAME day and amount within 10%. */
function matchDebt(t: Transaction, debts: SupabaseDebt[]): DebtMatch | null {
  const amt = Math.abs(t.MONTO);
  if (t.deuda_id) {
    const linked = debts.find(d => String(d.ID) === String(t.deuda_id));
    if (linked) return { debt: linked, amountDiff: Math.abs(amt - linked.MONTO) };
  }
  if (!t.es_reembolsable) return null;
  if (amt <= 0) return null;
  const txDay = dayOf(t.FECHA);
  let best: DebtMatch | null = null;
  for (const d of debts) {
    if (dayOf(d.FECHA) !== txDay) continue;
    const amountDiff = Math.abs(amt - d.MONTO);
    if (amountDiff > d.MONTO * AMOUNT_TOL_FRAC) continue;
    if (!best || amountDiff < best.amountDiff) best = { debt: d, amountDiff };
  }
  return best;
}

// --- component -------------------------------------------------------------

interface Props {
  transactions: Transaction[];
  // The day's fixed-payment drivers (the "Pagos Fijos" panel), used to net a fund's
  // income against the generated payments that income covers.
  dayDrivers?: TransactionDriver[];
  // 'full' = wide table (default). 'compact' = narrow stacked list for tight panels.
  variant?: 'full' | 'compact';
  // The selected day (YYYY-MM-DD); used to surface Supabase debts of that day that have
  // no matching transaction. Falls back to the first transaction's date.
  date?: string;
}

/** Sum of the generated fixed-payments (START events) of a fund on the shown day. */
function fundPayments(fund: FundListItem, drivers: TransactionDriver[]): number {
  const groupTag = `(Pagos ${fund.name})`;
  let sum = 0;
  for (const d of drivers) {
    if (d.source !== ComponentType.PAGOS_FIJO) continue;
    if (d.description.startsWith('Fin')) continue; // skip payment-end (+) events
    if (d.description.includes(groupTag)) sum += d.amount; // negative amounts
  }
  return sum;
}

/** Sum of the fixed-payments (START events) of investment groups on the shown day.
 *  Investments behave like a fund: the deposit is offset by its investment payments. */
function investmentPayments(drivers: TransactionDriver[]): number {
  let sum = 0;
  for (const d of drivers) {
    if (d.source !== ComponentType.PAGOS_FIJO) continue;
    if (d.description.startsWith('Fin')) continue;
    if (normalize(d.description).includes('inversion')) sum += d.amount; // negative
  }
  return sum;
}

export default function EnrichedLedger({ transactions, dayDrivers, variant = 'full', date }: Props) {
  const { data: debts, isLoading: debtsLoading } = useSupabaseDebts();
  const { data: funds, isLoading: fundsLoading } = useFunds();
  // Cruces included: the dashboard subtracts every payment, virtual ones too, and the
  // day's total has to follow the same rule to add up to the series.
  const { data: payments, isLoading: paymentsLoading } = useSupabasePayments({ incluirCruces: true });

  const rows = useMemo(() => {
    const debtList = debts ?? [];
    const fundList = funds ?? [];
    const paymentById = new Map((payments ?? []).map(p => [String(p.id), p]));
    // Card payments (categoría "Tarjeta") are internal bank→card transfers: excluded.
    return transactions.filter(t => !isCardPayment(t)).map(t => {
      // A payment is only ever an explicit link: guessing it by amount would catch any
      // transfer that happens to match.
      const pago = t.pago_id ? paymentById.get(String(t.pago_id)) ?? null : null;
      return {
        t,
        pago,
        // An explicit `deuda_id` wins; otherwise only transactions flagged as reimbursable
        // are matched by amount+date. Matching every transaction would produce false
        // positives on coincidental amounts.
        debt: pago ? null : matchDebt(t, debtList),
        fund: matchFund(t, fundList),
        isInvestment: hasInvestmentMark(t),
      };
    });
  }, [transactions, debts, payments, funds]);

  const counts = useMemo(() => ({
    debts: rows.filter(r => r.debt).length,
    payments: rows.filter(r => r.pago).length,
    funds: rows.filter(r => r.fund).length,
    investments: rows.filter(r => r.isInvestment).length,
  }), [rows]);

  // Net per fund for THIS day = the fund's income (positive transactions) minus all the
  // generated fixed-payments that income covers (the "Pagos Fijos" of the fund today).
  // e.g. Gasolina income +80 with generated payments −76.59 → net +3.41.
  const fundDayNet = useMemo(() => {
    const drivers = dayDrivers ?? [];
    const fundList = funds ?? [];
    const income = new Map<string, number>();
    for (const r of rows) {
      if (r.fund && r.t.MONTO > 0) income.set(r.fund.id, (income.get(r.fund.id) ?? 0) + r.t.MONTO);
    }
    const m = new Map<string, number>();
    for (const f of fundList) {
      const inc = income.get(f.id) ?? 0;
      const pagos = fundPayments(f, drivers); // negative
      if (inc !== 0 || pagos !== 0) m.set(f.id, inc + pagos);
    }
    return m;
  }, [rows, funds, dayDrivers]);

  // Fund subtotal: each fund's net counted ONCE (the map holds one entry per fund, so
  // repeated rows of the same fund don't double-count).
  const totalFundNet = useMemo(
    () => Array.from(fundDayNet.values()).reduce((a, b) => a + b, 0),
    [fundDayNet],
  );

  // Investment behaves like a single fund bucket: all investment transactions of the day
  // netted against the investment groups' fixed-payments. null when there are none.
  const investmentNet = useMemo(() => {
    let has = false;
    let sum = 0;
    for (const r of rows) {
      if (r.isInvestment && !r.fund && !r.debt && !r.pago) { sum += r.t.MONTO; has = true; }
    }
    if (!has) return null;
    return sum + investmentPayments(dayDrivers ?? []); // payments are negative
  }, [rows, dayDrivers]);

  // Per-row contribution to the global total, so the column literally adds up:
  //  - fund row  -> the fund net, only on its FIRST row ('net'); repeats are 'dup' (0).
  //  - debt row  -> the transaction (expense) PLUS the matched Supabase debt as income
  //                 (a loan given nets to ~0). The debt income is added once per debt.
  //  - payment row -> the transaction MINUS the linked payment (a friend paying back
  //                 nets to ~0). Counted once per payment.
  //  - other row -> its own amount ('raw').
  const netByRow = useMemo(() => {
    const seenFunds = new Set<string>();
    const seenDebts = new Set<string>();
    const seenPagos = new Set<string>();
    let seenInv = false;
    return rows.map(r => {
      if (r.fund) {
        if (seenFunds.has(r.fund.id)) return { kind: 'dup' as const, value: 0 };
        seenFunds.add(r.fund.id);
        return { kind: 'net' as const, value: fundDayNet.get(r.fund.id) ?? 0 };
      }
      if (r.pago) {
        const id = String(r.pago.id);
        const pagoOut = seenPagos.has(id) ? 0 : r.pago.monto_total;
        seenPagos.add(id);
        return { kind: 'pago' as const, value: r.t.MONTO - pagoOut };
      }
      if (r.debt) {
        const id = String(r.debt.debt.ID);
        const debtIncome = seenDebts.has(id) ? 0 : r.debt.debt.MONTO;
        seenDebts.add(id);
        return { kind: 'debt' as const, value: r.t.MONTO + debtIncome };
      }
      if (r.isInvestment) {
        // Whole investment bucket netted once (deposit − investment fixed-payments).
        if (seenInv) return { kind: 'dup' as const, value: 0 };
        seenInv = true;
        return { kind: 'inv' as const, value: investmentNet ?? r.t.MONTO };
      }
      return { kind: 'raw' as const, value: r.t.MONTO };
    });
  }, [rows, fundDayNet, investmentNet]);

  // Other fixed-payments of the day that belong to NEITHER a fund nor an investment
  // (e.g. Parqueadero, Arreglos). They have no transaction row, so we list them on their
  // own and subtract their amount as-is (start events negative, end events positive).
  const otherPagos = useMemo(() => {
    const drivers = dayDrivers ?? [];
    const fundList = funds ?? [];
    const isFundPago = (desc: string) => fundList.some(f => desc.includes(`(Pagos ${f.name})`));
    return drivers.filter(d =>
      d.source === ComponentType.PAGOS_FIJO &&
      !isFundPago(d.description) &&
      !normalize(d.description).includes('inversion'),
    );
  }, [dayDrivers, funds]);

  const otherPagosTotal = useMemo(() => otherPagos.reduce((s, d) => s + d.amount, 0), [otherPagos]);

  // Supabase debts of the day that no transaction matched: surfaced as a WARNING and
  // still counted (their amount is income, like the Supabase side of a matched debt).
  const dayDate = date ?? dayOf(transactions[0]?.FECHA);
  const unmatchedDebts = useMemo(() => {
    const debtList = debts ?? [];
    if (!dayDate) return [];
    const matched = new Set(rows.filter(r => r.debt).map(r => String(r.debt!.debt.ID)));
    return debtList.filter(d => dayOf(d.FECHA) === dayDate && !matched.has(String(d.ID)));
  }, [debts, rows, dayDate]);

  const unmatchedDebtTotal = useMemo(() => unmatchedDebts.reduce((s, d) => s + d.MONTO, 0), [unmatchedDebts]);

  // Payments of the day no transaction is linked to (cash, or a cruce): a warning, and
  // still counted, subtracting their amount like the dashboard does.
  const unmatchedPayments = useMemo(() => {
    if (!dayDate) return [];
    const linked = new Set(rows.filter(r => r.pago).map(r => String(r.pago!.id)));
    return (payments ?? []).filter(p => dayOf(p.fecha_pago) === dayDate && !linked.has(String(p.id)));
  }, [payments, rows, dayDate]);

  const unmatchedPaymentTotal = useMemo(
    () => unmatchedPayments.reduce((s, p) => s - p.monto_total, 0),
    [unmatchedPayments],
  );
  const hasExtras = otherPagos.length > 0 || unmatchedDebts.length > 0 || unmatchedPayments.length > 0;

  // Global total = every row's contribution (funds/investments netted once, debts netted
  // against Supabase, rest at face value) PLUS other fixed-payments and unmatched debts.
  const globalTotal = useMemo(
    () => netByRow.reduce((s, nb) => s + nb.value, 0) + otherPagosTotal + unmatchedDebtTotal + unmatchedPaymentTotal,
    [netByRow, otherPagosTotal, unmatchedDebtTotal, unmatchedPaymentTotal],
  );

  const loading = debtsLoading || fundsLoading || paymentsLoading;

  // --- Compact variant: narrow stacked list for the detail panel (~400px) ----------
  if (variant === 'compact') {
    return (
      <div className="space-y-2.5">
        {loading && <div className="text-center text-surface-400 text-xs py-6">Cargando…</div>}
        {!loading && rows.length === 0 && !hasExtras && <div className="text-center text-surface-500 text-xs py-6">Sin transacciones.</div>}

        <div className="space-y-1.5">
          {rows.map(({ t, debt, pago, fund, isInvestment }, i) => (
            <div key={t.id} className="rounded-lg bg-white/[0.02] border border-white/5 px-2.5 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-white truncate">{t.nombre_limpio || t.DESCRIPCION}</span>
                <span className={`font-mono text-xs font-bold tabular-nums shrink-0 ${t.MONTO >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{fmtSigned(t.MONTO)}</span>
              </div>
              <div className="flex items-center justify-between gap-2 mt-1.5">
                <div className="flex flex-wrap items-center gap-1 min-w-0">
                  {fund && <MiniChip className="bg-emerald-500/10 text-emerald-300 border-emerald-500/20"><PiggyBank size={10} />{fund.name}</MiniChip>}
                  {debt && <MiniChip className="bg-rose-500/10 text-rose-300 border-rose-500/20"><HandCoins size={10} />Deuda: {debt.debt.DEUDOR_NOMBRE}</MiniChip>}
                  {pago && <MiniChip className="bg-sky-500/10 text-sky-300 border-sky-500/20"><Banknote size={10} />Pago: {pago.deudor_nombre}</MiniChip>}
                  {isInvestment && <MiniChip className="bg-amber-500/10 text-amber-300 border-amber-500/20"><TrendingUp size={10} />Inv.</MiniChip>}
                  {t.es_reembolsable && !debt && !pago && <MiniChip className="bg-rose-500/10 text-rose-300/80 border-rose-500/20">Reemb.</MiniChip>}
                  {!fund && !debt && !pago && !isInvestment && !t.es_reembolsable && <span className="text-surface-600 text-[10px]">·</span>}
                </div>
                <div className="shrink-0"><AporteValue nb={netByRow[i]} fundName={fund?.name} size="lg" showTag={false} /></div>
              </div>
            </div>
          ))}

          {otherPagos.map((d, i) => {
            const { main, group } = splitPagoDesc(d.description);
            return (
              <div key={`pf-${i}`} className="rounded-lg bg-white/[0.02] border border-white/5 px-2.5 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-white truncate">{main}</span>
                  <span className={`font-mono text-lg font-bold tabular-nums shrink-0 ${d.amount >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{fmtSigned(d.amount)}</span>
                </div>
                <div className="mt-1.5">
                  <MiniChip className="bg-slate-500/10 text-slate-300 border-slate-500/20">Pago fijo{group ? `: ${group}` : ''}</MiniChip>
                </div>
              </div>
            );
          })}

          {unmatchedDebts.map((d, i) => (
            <div key={`ud-${i}`} className="rounded-lg bg-amber-500/[0.06] border border-amber-500/20 px-2.5 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-white truncate">{d.DESCRIPCION}</span>
                <span className="font-mono text-lg font-bold tabular-nums shrink-0 text-emerald-400">{fmtSigned(d.MONTO)}</span>
              </div>
              <div className="mt-1.5">
                <MiniChip className="bg-amber-500/10 text-amber-300 border-amber-500/25"><AlertTriangle size={10} />Deuda sin transacción · {d.DEUDOR_NOMBRE}</MiniChip>
              </div>
            </div>
          ))}

          {unmatchedPayments.map(p => (
            <div key={`up-${p.id}`} className="rounded-lg bg-amber-500/[0.06] border border-amber-500/20 px-2.5 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-white truncate">{pagoTitulo(p)}</span>
                <span className="font-mono text-lg font-bold tabular-nums shrink-0 text-rose-400">{fmtSigned(-p.monto_total)}</span>
              </div>
              <div className="mt-1.5">
                <MiniChip className="bg-amber-500/10 text-amber-300 border-amber-500/25"><AlertTriangle size={10} />{p.es_compensacion ? 'Cruce' : 'Pago sin transacción'} · {p.deudor_nombre}</MiniChip>
              </div>
            </div>
          ))}
        </div>

        {!loading && (rows.length > 0 || hasExtras) && (
          <div className="border-t border-white/10 pt-2.5 space-y-1.5">
            {fundDayNet.size > 0 && (
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-surface-400">Neto fondos <span className="text-surface-600">· {fundDayNet.size}</span></span>
                <span className={`font-mono font-semibold tabular-nums ${totalFundNet >= 0 ? 'text-emerald-400/80' : 'text-rose-400/80'}`}>{fmtSigned(totalFundNet)}</span>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-widest text-white">Total global</span>
              <span className={`font-mono font-bold text-base tabular-nums ${globalTotal >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{fmtSigned(globalTotal)}</span>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Summary bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <LegendChip icon={<HandCoins size={13} />} count={counts.debts} label="Deudas" className="bg-rose-500/10 text-rose-300 border-rose-500/20" />
          <LegendChip icon={<Banknote size={13} />} count={counts.payments} label="Pagos" className="bg-sky-500/10 text-sky-300 border-sky-500/20" />
          <LegendChip icon={<PiggyBank size={13} />} count={counts.funds} label="Fondos" className="bg-emerald-500/10 text-emerald-300 border-emerald-500/20" />
          <LegendChip icon={<TrendingUp size={13} />} count={counts.investments} label="Inversiones" className="bg-amber-500/10 text-amber-300 border-amber-500/20" />
        </div>
        {!loading && rows.length > 0 && (
          <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-surface-950/60 px-4 py-2 shadow-inner">
            <span className="text-[10px] font-bold uppercase tracking-widest text-surface-500">Total del día</span>
            <span className={`font-mono font-bold text-lg tabular-nums ${globalTotal >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {globalTotal >= 0 ? '+' : '−'}${Math.abs(globalTotal).toLocaleString('es-CO', { minimumFractionDigits: 2 })}
            </span>
          </div>
        )}
      </div>
      <p className="text-[11px] text-surface-500 leading-relaxed">
        Deudas emparejadas el <strong className="text-surface-400">mismo día</strong> con monto ±<strong className="text-surface-400">10%</strong>. Los pagos solo se enlazan por <strong className="text-surface-400">vínculo explícito</strong> y restan su monto, como en el dashboard. El neto de cada fondo, deuda y pago se cuenta <strong className="text-surface-400">una sola vez</strong> en el total.
      </p>

      <div className="bg-surface-900/40 backdrop-blur-xl border border-white/10 rounded-3xl overflow-hidden shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-950/60 text-surface-400 text-[11px] font-bold uppercase tracking-widest border-b border-white/10">
                <th className="px-5 py-3.5">Fecha / Fuente</th>
                <th className="px-6 py-3.5">Concepto</th>
                <th className="px-5 py-3.5 text-right">Monto</th>
                <th className="px-6 py-3.5">Enlace / Contexto</th>
                <th className="px-5 py-3.5 text-right whitespace-nowrap border-l border-white/5 bg-white/[0.02] text-surface-300" title="Aporte de cada fila al total: fondo = su neto (una vez); no-fondo = su monto">Aporte al total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {rows.map(({ t, debt, pago, fund, isInvestment }, i) => (
                <tr key={t.id} className="odd:bg-white/[0.015] hover:bg-white/[0.04] transition-colors align-top">
                  {/* Date / Source */}
                  <td className="px-5 py-4 text-surface-400 text-xs whitespace-nowrap">
                    <div className="flex flex-col gap-1">
                      <span className="text-surface-200 font-medium flex items-center gap-1.5">
                        <Calendar size={12} className="text-surface-500" />
                        {t.FECHA?.substring(0, 10)}
                      </span>
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded w-fit uppercase tracking-wider ${
                        t.TIPO?.toUpperCase() === 'TARJETA'
                          ? 'bg-purple-500/15 text-purple-300 border border-purple-500/20'
                          : 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/20'
                      }`}>
                        {t.TIPO || 'BANCA'}
                      </span>
                    </div>
                  </td>

                  {/* Concept */}
                  <td className="px-6 py-4">
                    <div className="flex flex-col gap-0.5 min-w-0">
                      <span className="text-sm font-semibold text-white truncate max-w-md">
                        {t.nombre_limpio || t.DESCRIPCION}
                      </span>
                      {t.categoria && (
                        <span className="text-[11px] text-surface-500">{t.categoria}</span>
                      )}
                    </div>
                  </td>

                  {/* Amount */}
                  <td className={`px-5 py-4 text-right text-sm font-mono font-bold tabular-nums whitespace-nowrap ${t.MONTO >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {t.MONTO >= 0 ? '+' : '−'}${Math.abs(t.MONTO).toLocaleString('es-CO', { minimumFractionDigits: 2 })}
                  </td>

                  {/* Context */}
                  <td className="px-6 py-4">
                    <div className="flex flex-col gap-2">
                      {debt && <DebtContext tx={t} debt={debt.debt} />}
                      {pago && <PaymentContext tx={t} pago={pago} />}
                      {fund && (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-semibold">
                            <PiggyBank size={12} /> Fondo: {fund.name}
                          </span>
                        </div>
                      )}
                      {isInvestment && (
                        <span className="inline-flex w-fit items-center gap-1 px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300 border border-amber-500/20 font-semibold text-xs">
                          <TrendingUp size={12} /> Inversión
                        </span>
                      )}
                      {t.es_reembolsable && !debt && !pago && (
                        <span className="inline-flex w-fit items-center gap-1 px-2 py-0.5 rounded-md bg-rose-500/10 text-rose-300 border border-rose-500/20 font-semibold text-xs">
                          <HandCoins size={12} /> Reembolsable (sin deuda emparejada)
                        </span>
                      )}
                      {!debt && !pago && !fund && !isInvestment && !t.es_reembolsable && (
                        <span className="text-surface-600 text-xs italic">—</span>
                      )}
                    </div>
                  </td>

                  {/* Contribution of this row to the global total */}
                  <td className="px-5 py-4 text-right whitespace-nowrap border-l border-white/5 bg-white/[0.02]">
                    <AporteValue nb={netByRow[i]} fundName={fund?.name} />
                  </td>
                </tr>
              ))}

              {/* Other fixed-payments (not fund, not investment) */}
              {otherPagos.map((d, i) => {
                const { main, group } = splitPagoDesc(d.description);
                return (
                  <tr key={`pf-${i}`} className="odd:bg-white/[0.015] hover:bg-white/[0.04] transition-colors align-top">
                    <td className="px-5 py-4 text-surface-400 text-xs whitespace-nowrap">
                      <div className="flex flex-col gap-1">
                        <span className="text-surface-200 font-medium flex items-center gap-1.5">
                          <Calendar size={12} className="text-surface-500" />
                          {d.date?.substring(0, 10)}
                        </span>
                        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded w-fit uppercase tracking-wider bg-slate-500/15 text-slate-300 border border-slate-500/20">
                          Pago fijo
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-col gap-0.5 min-w-0">
                        <span className="text-sm font-semibold text-white truncate max-w-md">{main}</span>
                        {group && <span className="text-[11px] text-surface-500">{group}</span>}
                      </div>
                    </td>
                    <td className={`px-5 py-4 text-right text-sm font-mono font-bold tabular-nums whitespace-nowrap ${d.amount >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {fmtSigned(d.amount)}
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex w-fit items-center gap-1 px-2 py-0.5 rounded-md bg-slate-500/10 text-slate-300 border border-slate-500/20 font-semibold text-xs">
                        Pago fijo (ni fondo ni inversión)
                      </span>
                    </td>
                    <td className="px-5 py-4 text-right whitespace-nowrap border-l border-white/5 bg-white/[0.02]">
                      <AporteValue nb={{ kind: 'raw', value: d.amount }} />
                    </td>
                  </tr>
                );
              })}

              {/* Supabase debts of the day with NO matching transaction (warning) */}
              {unmatchedDebts.map((d, i) => (
                <tr key={`ud-${i}`} className="bg-amber-500/[0.04] hover:bg-amber-500/[0.07] transition-colors align-top">
                  <td className="px-5 py-4 text-surface-400 text-xs whitespace-nowrap">
                    <div className="flex flex-col gap-1">
                      <span className="text-surface-200 font-medium flex items-center gap-1.5">
                        <Calendar size={12} className="text-surface-500" />
                        {dayOf(d.FECHA)}
                      </span>
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded w-fit uppercase tracking-wider bg-amber-500/15 text-amber-300 border border-amber-500/25">
                        Supabase
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col gap-0.5 min-w-0">
                      <span className="text-sm font-semibold text-white truncate max-w-md">{d.DESCRIPCION}</span>
                      <span className="text-[11px] text-surface-500">{d.DEUDOR_NOMBRE}</span>
                    </div>
                  </td>
                  <td className="px-5 py-4 text-right text-sm font-mono font-bold tabular-nums whitespace-nowrap text-emerald-400">
                    {fmtSigned(d.MONTO)}
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex w-fit items-center gap-1 px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300 border border-amber-500/25 font-semibold text-xs">
                      <AlertTriangle size={12} /> Deuda sin transacción emparejada
                    </span>
                  </td>
                  <td className="px-5 py-4 text-right whitespace-nowrap border-l border-white/5 bg-white/[0.02]">
                    <span className="font-mono tabular-nums text-base font-bold text-emerald-400" title="Deuda de Supabase sin transacción: contada como ingreso">
                      {fmtSigned(d.MONTO)}
                    </span>
                  </td>
                </tr>
              ))}

              {/* Supabase payments of the day with NO linked transaction (warning) */}
              {unmatchedPayments.map(p => (
                <tr key={`up-${p.id}`} className="bg-amber-500/[0.04] hover:bg-amber-500/[0.07] transition-colors align-top">
                  <td className="px-5 py-4 text-surface-400 text-xs whitespace-nowrap">
                    <div className="flex flex-col gap-1">
                      <span className="text-surface-200 font-medium flex items-center gap-1.5">
                        <Calendar size={12} className="text-surface-500" />
                        {dayOf(p.fecha_pago)}
                      </span>
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded w-fit uppercase tracking-wider bg-amber-500/15 text-amber-300 border border-amber-500/25">
                        Supabase
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col gap-0.5 min-w-0">
                      <span className="text-sm font-semibold text-white truncate max-w-md">{pagoTitulo(p)}</span>
                      <span className="text-[11px] text-surface-500 truncate max-w-md">{pagoDetalle(p)}</span>
                    </div>
                  </td>
                  <td className="px-5 py-4 text-right text-sm font-mono font-bold tabular-nums whitespace-nowrap text-rose-400">
                    {fmtSigned(-p.monto_total)}
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex w-fit items-center gap-1 px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300 border border-amber-500/25 font-semibold text-xs">
                      <AlertTriangle size={12} /> {p.es_compensacion ? 'Cruce (pago virtual)' : 'Pago sin transacción vinculada'}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-right whitespace-nowrap border-l border-white/5 bg-white/[0.02]">
                    <span className="font-mono tabular-nums text-base font-bold text-rose-400" title="Pago de Supabase sin transacción: resta su monto, como en el dashboard">
                      {fmtSigned(-p.monto_total)}
                    </span>
                  </td>
                </tr>
              ))}
              {loading && (
                <tr>
                  <td colSpan={5} className="px-6 py-10 text-center text-surface-400 text-sm">
                    Cargando deudas y fondos para enriquecer…
                  </td>
                </tr>
              )}
              {!loading && rows.length === 0 && !hasExtras && (
                <tr>
                  <td colSpan={5} className="px-6 py-16 text-center text-surface-500 text-sm">
                    No hay transacciones con los filtros actuales.
                  </td>
                </tr>
              )}
            </tbody>
            {!loading && (rows.length > 0 || hasExtras) && (
              <tfoot className="border-t-2 border-white/10 bg-surface-950/60">
                {fundDayNet.size > 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 pt-3.5 pb-1 text-right text-[11px] font-medium text-surface-400">
                      Subtotal neto fondos <span className="text-surface-600">· {fundDayNet.size} fondo{fundDayNet.size > 1 ? 's' : ''}, sin duplicar</span>
                    </td>
                    <td className="px-5 pt-3.5 pb-1 text-right whitespace-nowrap border-l border-white/5 bg-white/[0.02]">
                      <span className={`font-mono font-semibold text-sm tabular-nums ${totalFundNet >= 0 ? 'text-emerald-400/80' : 'text-rose-400/80'}`}>
                        {totalFundNet >= 0 ? '+' : '−'}${Math.abs(totalFundNet).toLocaleString('es-CO', { minimumFractionDigits: 2 })}
                      </span>
                    </td>
                  </tr>
                )}
                <tr>
                  <td colSpan={4} className="px-6 pt-1 pb-4 text-right text-xs font-bold uppercase tracking-widest text-white">
                    Total global del día <span className="text-surface-500 normal-case font-medium tracking-normal">· netos de fondo + demás</span>
                  </td>
                  <td className="px-5 pt-1 pb-4 text-right whitespace-nowrap border-l border-white/5 bg-white/[0.03]">
                    <span className={`font-mono font-bold text-lg tabular-nums ${globalTotal >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {globalTotal >= 0 ? '+' : '−'}${Math.abs(globalTotal).toLocaleString('es-CO', { minimumFractionDigits: 2 })}
                    </span>
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>
    </div>
  );
}

/** Shows the matched debt with the "net between the two": tx amount vs debt, pending. */
function DebtContext({ tx, debt }: { tx: Transaction; debt: SupabaseDebt }) {
  const net = Math.abs(tx.MONTO) - debt.MONTO; // difference between the paired amounts
  return (
    <div className="flex flex-col gap-1 text-xs bg-rose-500/[0.04] border border-rose-500/15 rounded-lg px-2.5 py-2 w-fit max-w-md">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-rose-500/10 text-rose-300 border border-rose-500/20 font-semibold">
          <HandCoins size={12} /> Deuda: {debt.DEUDOR_NOMBRE}
        </span>
        <span className="text-surface-400 truncate max-w-[180px]" title={debt.DESCRIPCION}>{debt.DESCRIPCION}</span>
      </div>
      <div className="flex items-center gap-3 font-mono text-surface-300">
        <span title="Monto de la transacción">tx ${Math.abs(tx.MONTO).toFixed(2)}</span>
        <ArrowRight size={11} className="text-surface-600" />
        <span title="Monto de la deuda">deuda ${debt.MONTO.toFixed(2)}</span>
        <span className={`${Math.abs(net) < 0.01 ? 'text-emerald-400' : 'text-amber-400'}`} title="Diferencia entre ambos">
          neto {net >= 0 ? '+' : '−'}${Math.abs(net).toFixed(2)}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        {debt.PAGADA ? (
          <span className="inline-flex items-center gap-1 text-emerald-400"><CheckCircle2 size={12} /> Pagada{debt.FECHA_PAGO ? ` (${debt.FECHA_PAGO.substring(0, 10)})` : ''}</span>
        ) : (
          <span className="inline-flex items-center gap-1 text-amber-400"><Clock size={12} /> Pendiente</span>
        )}
      </div>
    </div>
  );
}

/** "Juan te pagó" / "Le pagaste a Ana". */
function pagoTitulo(p: SupabasePayment): string {
  return p.es_mi_pago ? `Le pagaste a ${p.deudor_nombre}` : `${p.deudor_nombre} te pagó`;
}

/** The debts a payment settled, e.g. "Cena $12.00 · Taxi $8.00". */
function pagoDetalle(p: SupabasePayment): string {
  const deudas = (p.deudas ?? []).map(d => `${d.titulo} $${d.monto_asignado.toFixed(2)}`).join(' · ');
  return deudas || 'Sin deudas abonadas';
}

/** Shows the linked payment next to the transaction: what it settled and the net. */
function PaymentContext({ tx, pago }: { tx: Transaction; pago: SupabasePayment }) {
  const net = Math.abs(tx.MONTO) - pago.monto_total;
  const sobrante = pago.sobrante ?? 0;
  return (
    <div className="flex flex-col gap-1 text-xs bg-sky-500/[0.04] border border-sky-500/15 rounded-lg px-2.5 py-2 w-fit max-w-md">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-sky-500/10 text-sky-300 border border-sky-500/20 font-semibold">
          <Banknote size={12} /> {pagoTitulo(pago)}
        </span>
      </div>
      <div className="flex items-center gap-3 font-mono text-surface-300">
        <span title="Monto de la transacción">tx ${Math.abs(tx.MONTO).toFixed(2)}</span>
        <ArrowRight size={11} className="text-surface-600" />
        <span title="Monto del pago">pago ${pago.monto_total.toFixed(2)}</span>
        <span className={`${Math.abs(net) < 0.01 ? 'text-emerald-400' : 'text-amber-400'}`} title="Diferencia entre ambos">
          neto {net >= 0 ? '+' : '−'}${Math.abs(net).toFixed(2)}
        </span>
      </div>
      <div className="text-surface-400 truncate" title={pagoDetalle(pago)}>{pagoDetalle(pago)}</div>
      {sobrante > 0.01 && <div className="text-sky-300">Saldo a favor ${sobrante.toFixed(2)}</div>}
    </div>
  );
}

function MiniChip({ children, className }: { children: React.ReactNode; className: string }) {
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold border max-w-full truncate ${className}`}>
      {children}
    </span>
  );
}

function LegendChip({ icon, count, label, className }: { icon: React.ReactNode; count: number; label: string; className: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 pl-2 pr-2.5 py-1 rounded-lg border font-medium ${count === 0 ? 'opacity-45' : ''} ${className}`}>
      {icon}
      <span className="font-bold tabular-nums">{count}</span>
      <span className="opacity-80">{label}</span>
    </span>
  );
}
