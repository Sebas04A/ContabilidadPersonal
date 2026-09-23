import { Transaction, SupabaseDebt, SupabasePayment } from '../services/api';

export type DebtSignFilterOption = 'all' | 'positive' | 'negative';
export type DebtLinkFilterOption = 'all' | 'deuda' | 'pago' | 'linked' | 'unlinked';
export type DebtStatusFilterOption = 'all' | 'paid' | 'pending' | 'partial';
export type DebtDirectionFilterOption = 'all' | 'me_deben' | 'debo';

export type DebtPeopleModeOption = 'include' | 'exclude';

export const SIN_PERSONA = '__sin_persona__';

export interface DebtFilters {
  sign: DebtSignFilterOption;
  /** Personas elegidas (en minúsculas, o SIN_PERSONA); vacío = sin filtro. */
  people: string[];
  peopleMode: DebtPeopleModeOption;
  link: DebtLinkFilterOption;
  status: DebtStatusFilterOption;
  direction: DebtDirectionFilterOption;
}

export interface DebtLookup {
  debts: Map<string, SupabaseDebt>;
  payments: Map<string, SupabasePayment>;
}

export function buildDebtLookup(debts?: SupabaseDebt[], payments?: SupabasePayment[]): DebtLookup {
  return {
    debts: new Map((debts ?? []).map(d => [String(d.ID), d])),
    payments: new Map((payments ?? []).map(p => [String(p.id), p])),
  };
}

const isBlank = (s?: string | null) => !s || s.trim() === '' || s === '---';

/**
 * Persona de una transacción: la de la deuda o el pago vinculado en Supabase
 * (fuente de verdad) y, si no hay vínculo, el `deudor` escrito al etiquetar.
 */
export function debtPerson(t: Transaction, lookup: DebtLookup): string {
  const debt = t.deuda_id ? lookup.debts.get(String(t.deuda_id)) : undefined;
  if (debt?.DEUDOR_NOMBRE) return debt.DEUDOR_NOMBRE;
  const pago = t.pago_id ? lookup.payments.get(String(t.pago_id)) : undefined;
  if (pago?.deudor_nombre) return pago.deudor_nombre;
  return isBlank(t.deudor) ? '' : t.deudor.trim();
}

/** Clave con la que se elige a una persona en el filtro. */
export function personKey(persona: string): string {
  return persona ? persona.toLowerCase() : SIN_PERSONA;
}

/** Estado de la deuda vinculada; null si la transacción no apunta a una deuda conocida. */
export function linkedDebtStatus(t: Transaction, lookup: DebtLookup): 'paid' | 'partial' | 'pending' | null {
  const debt = t.deuda_id ? lookup.debts.get(String(t.deuda_id)) : undefined;
  if (!debt) return null;
  if (debt.PAGADA) return 'paid';
  const saldo = debt.SALDO_PENDIENTE;
  if (saldo != null && Math.abs(saldo) > 0.009 && Math.abs(saldo) < Math.abs(debt.MONTO) - 0.009) return 'partial';
  return 'pending';
}

/** 'debo' si la deuda es mía o el pago lo hice yo; 'me_deben' en el caso contrario. */
export function debtDirection(t: Transaction, lookup: DebtLookup): 'me_deben' | 'debo' | null {
  const debt = t.deuda_id ? lookup.debts.get(String(t.deuda_id)) : undefined;
  if (debt) return debt.ES_MI_DEUDA ? 'debo' : 'me_deben';
  const pago = t.pago_id ? lookup.payments.get(String(t.pago_id)) : undefined;
  if (pago) return pago.es_mi_pago ? 'debo' : 'me_deben';
  return null;
}

function matchesRow(t: Transaction, f: DebtFilters, lookup: DebtLookup): boolean {
  if (f.sign === 'positive' && !(t.MONTO > 0)) return false;
  if (f.sign === 'negative' && !(t.MONTO < 0)) return false;

  if (f.people.length > 0) {
    const chosen = f.people.includes(personKey(debtPerson(t, lookup)));
    if (f.peopleMode === 'include' ? !chosen : chosen) return false;
  }

  const hasDeuda = !!t.deuda_id;
  const hasPago = !!t.pago_id;
  if (f.link === 'deuda' && !hasDeuda) return false;
  if (f.link === 'pago' && !hasPago) return false;
  if (f.link === 'linked' && !hasDeuda && !hasPago) return false;
  // Sin vincular solo tiene sentido para lo que se marcó como reembolsable.
  if (f.link === 'unlinked' && (!t.es_reembolsable || hasDeuda || hasPago)) return false;

  if (f.status !== 'all') {
    const status = linkedDebtStatus(t, lookup);
    if (f.status === 'pending' ? status !== 'pending' && status !== 'partial' : status !== f.status) return false;
  }

  if (f.direction !== 'all' && debtDirection(t, lookup) !== f.direction) return false;

  return true;
}

export function hasActiveDebtFilters(f: DebtFilters): boolean {
  return f.sign !== 'all' || f.people.length > 0 || f.link !== 'all' || f.status !== 'all' || f.direction !== 'all';
}

/** Una transacción pasa si ella o alguna de sus partes (split) cumple todos los filtros. */
export function applyDebtFilters(list: Transaction[], f: DebtFilters, lookup: DebtLookup): Transaction[] {
  if (!hasActiveDebtFilters(f)) return list;
  return list.filter(t => {
    if (t.subTransactions && t.subTransactions.length > 0) {
      return t.subTransactions.some(sub => matchesRow(sub, f, lookup));
    }
    return matchesRow(t, f, lookup);
  });
}
