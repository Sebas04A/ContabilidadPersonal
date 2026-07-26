import type { Transaction, SupabaseDebt } from '../services/api';

export type Side = 'local' | 'supabase';
export type Granularity = 'month' | 'week';

export interface DebtItem {
  key: string; // unique DOM/React key
  side: Side;
  date: Date;
  title: string;
  amount: number;
  debtor: string;
  paid: boolean;
  paidDate?: string | null;
  matchId?: number; // set by detectMatches when paired heuristically with the other side
  linked?: boolean; // true when explicitly (manually) linked via deuda_id
  linkId?: number;  // shared id between the two sides of a manual link
  groupCount?: number; // >1 when this card represents a collapsed group of transactions
  isSplitPart?: boolean; // true when this row is one part of a split transaction
  raw: Transaction | SupabaseDebt;
}

export interface PeriodBand {
  key: string; // bucket key, e.g. "2026-07"
  label: string; // human label, e.g. "Julio 2026"
  left: DebtItem[];
  right: DebtItem[];
  leftTotal: number; // sum of all local amounts
  rightTotal: number; // sum of pending supabase amounts (mirrors "por cobrar")
}

export interface Reconciliation {
  totalLocal: number;
  totalSupabase: number;
  diff: number; // totalLocal - totalSupabase
  countOnlyLocal: number;
  countOnlySupabase: number;
  countMatched: number;
  countLinked: number; // pares vinculados manualmente (deuda_id)
}

const MESES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];
const MESES_CORTOS = [
  'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
  'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
];

/** Normaliza un nombre de deudor (minúsculas, sin acentos, sin espacios extra). Solo para mostrar/filtrar. */
export function normalizeDebtor(s: string | null | undefined): string {
  if (!s) return '';
  return s
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toLowerCase();
}

function parseDate(value: string): Date {
  // Las fechas llegan como "YYYY-MM-DD HH:MM:SS" o "YYYY-MM-DD".
  const d = new Date(value.replace(' ', 'T'));
  return isNaN(d.getTime()) ? new Date(0) : d;
}

function isRealGroupId(id: string | null | undefined): id is string {
  return !!id && id !== 'None' && id !== 'nan';
}

/**
 * Mapea ambos lados al modelo unificado DebtItem.
 *
 * Transacciones locales — casos especiales:
 *  - AGRUPADAS (mismo `group_id`): son transacciones distintas que el usuario unió como
 *    una sola deuda lógica. Se colapsan en UNA tarjeta con el monto sumado, para comparar
 *    1:1 contra la deuda equivalente en Supabase.
 *  - DIVIDIDAS (mismo `id`, varias filas): el backend ya devuelve solo las partes
 *    reembolsables; cada parte es su propia deuda (puede tener su propio deudor). Se
 *    muestran por separado. Como `split_group_id` puede venir vacío, la key se
 *    desambigua con el índice para evitar colisiones de React.
 */
export function toDebtItems(
  transactions: Transaction[] | undefined,
  debts: SupabaseDebt[] | undefined,
): DebtItem[] {
  const items: DebtItem[] = [];
  const rows = transactions ?? [];

  // 1. Separar filas agrupadas de las demás
  const groups = new Map<string, Transaction[]>();
  const singles: { tx: Transaction; idx: number }[] = [];
  rows.forEach((tx, idx) => {
    if (isRealGroupId(tx.group_id)) {
      const list = groups.get(tx.group_id!) ?? [];
      list.push(tx);
      groups.set(tx.group_id!, list);
    } else {
      singles.push({ tx, idx });
    }
  });

  // 2. Grupos → una tarjeta colapsada con monto sumado
  for (const [gid, members] of groups) {
    const total = members.reduce((s, m) => s + m.MONTO, 0);
    const latest = members.reduce((a, b) => (parseDate(b.FECHA) > parseDate(a.FECHA) ? b : a));
    const base = members[0];
    items.push({
      key: `local:group:${gid}`,
      side: 'local',
      date: parseDate(latest.FECHA),
      title: base.nombre_limpio || base.DESCRIPCION,
      amount: total,
      debtor: base.deudor || '',
      paid: false,
      groupCount: members.length,
      raw: base,
    });
  }

  // 3. Filas sueltas (incluye partes de una división) → una tarjeta cada una
  //    Detectamos partes de división: varias filas con el mismo `id`.
  const idCounts = new Map<string, number>();
  for (const { tx } of singles) idCounts.set(tx.id, (idCounts.get(tx.id) ?? 0) + 1);

  for (const { tx, idx } of singles) {
    items.push({
      key: `local:${tx.id}:${idx}`,
      side: 'local',
      date: parseDate(tx.FECHA),
      title: tx.nombre_limpio || tx.DESCRIPCION,
      amount: tx.MONTO,
      debtor: tx.deudor || '',
      paid: false, // el lado local no tiene estado de reembolso
      isSplitPart: (idCounts.get(tx.id) ?? 0) > 1,
      raw: tx,
    });
  }

  for (const d of debts ?? []) {
    items.push({
      key: `supabase:${d.ID}`,
      side: 'supabase',
      date: parseDate(d.FECHA),
      title: d.DESCRIPCION,
      amount: d.MONTO,
      debtor: d.DEUDOR_NOMBRE || '',
      paid: !!d.PAGADA,
      paidDate: d.FECHA_PAGO,
      raw: d,
    });
  }

  return items;
}

/** Lunes de la semana ISO que contiene a `date`. */
function startOfISOWeek(date: Date): Date {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const day = (d.getDay() + 6) % 7; // 0 = lunes
  d.setDate(d.getDate() - day);
  return d;
}

function bucketKey(date: Date, granularity: Granularity): string {
  if (granularity === 'month') {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  }
  const start = startOfISOWeek(date);
  return `w:${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
}

function bucketLabel(date: Date, granularity: Granularity): string {
  if (granularity === 'month') {
    return `${MESES[date.getMonth()]} ${date.getFullYear()}`;
  }
  const start = startOfISOWeek(date);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  const sameMonth = start.getMonth() === end.getMonth();
  if (sameMonth) {
    return `${start.getDate()}–${end.getDate()} ${MESES_CORTOS[start.getMonth()]} ${start.getFullYear()}`;
  }
  return `${start.getDate()} ${MESES_CORTOS[start.getMonth()]} – ${end.getDate()} ${MESES_CORTOS[end.getMonth()]} ${end.getFullYear()}`;
}

/** Agrupa los items en bandas de período, ordenadas de presente → pasado. */
export function groupByPeriod(items: DebtItem[], granularity: Granularity): PeriodBand[] {
  const map = new Map<string, PeriodBand>();

  for (const item of items) {
    const key = bucketKey(item.date, granularity);
    let band = map.get(key);
    if (!band) {
      band = {
        key,
        label: bucketLabel(item.date, granularity),
        left: [],
        right: [],
        leftTotal: 0,
        rightTotal: 0,
      };
      map.set(key, band);
    }
    if (item.side === 'local') {
      band.left.push(item);
      band.leftTotal += item.amount;
    } else {
      band.right.push(item);
      if (!item.paid) band.rightTotal += item.amount;
    }
  }

  const bands = Array.from(map.values());
  // Ordenar bandas presente → pasado (la clave es comparable lexicográficamente salvo el prefijo "w:")
  const norm = (k: string) => k.replace(/^w:/, '');
  bands.sort((a, b) => norm(b.key).localeCompare(norm(a.key)));
  // Ordenar items dentro de cada banda por fecha desc
  for (const band of bands) {
    band.left.sort((a, b) => b.date.getTime() - a.date.getTime());
    band.right.sort((a, b) => b.date.getTime() - a.date.getTime());
  }
  return bands;
}

/** Clave de día calendario (YYYY-MM-DD) para comparar fechas de forma exacta. */
function dayKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/**
 * Empareja items local↔supabase de forma GLOBAL por monto + MISMO DÍA exacto.
 *
 * Una deuda y su reembolso local comparten la misma fecha de gasto; si el día difiere,
 * no se considera la misma deuda. Antes el matching era por banda de mes, lo que rompía
 * pares que caían cerca de un límite de mes; ahora se recorren todos los items y se exige
 * día idéntico, sin depender de la banda.
 *
 * NO usa el nombre del deudor (los nombres nunca coinciden entre ambos lados).
 * Marca `matchId` en ambos items de cada par. Es una sugerencia visual, no una afirmación dura.
 *
 * `items` son las MISMAS referencias que viven dentro de las bandas, así que mutar aquí
 * también actualiza lo que se renderiza en cada banda.
 */
/**
 * Vincula explícitamente los pares que el usuario unió a mano: una transacción local
 * con `deuda_id` apuntando a una deuda de Supabase presente. Marca ambos con `linked` y
 * un `linkId` compartido. Estos pares NO participan del match heurístico.
 */
export function detectLinks(items: DebtItem[]): void {
  const supaById = new Map<string, DebtItem>();
  for (const it of items) {
    if (it.side === 'supabase') supaById.set(String((it.raw as SupabaseDebt).ID), it);
  }
  let nextLinkId = 1;
  for (const it of items) {
    if (it.side !== 'local') continue;
    const deudaId = (it.raw as Transaction).deuda_id;
    if (!deudaId) continue;
    const supa = supaById.get(String(deudaId));
    if (!supa) continue;
    if (!supa.linked) {
      supa.linked = true;
      supa.linkId = nextLinkId++;
    }
    it.linked = true;
    it.linkId = supa.linkId;
  }
}

export function detectMatches(items: DebtItem[]): void {
  // Los pares vinculados manualmente quedan fuera del match heurístico.
  const locals = items.filter(i => i.side === 'local' && !i.linked);
  const supas = items.filter(i => i.side === 'supabase' && !i.linked);

  // Candidatos: pares (l, r) con monto compatible y el mismo día exacto
  const candidates: { l: DebtItem; r: DebtItem; amountDiff: number }[] = [];
  for (const l of locals) {
    for (const r of supas) {
      if (dayKey(l.date) !== dayKey(r.date)) continue;
      // Los gastos locales se guardan en negativo y las deudas de Supabase en positivo,
      // así que comparamos por valor absoluto.
      const la = Math.abs(l.amount);
      const ra = Math.abs(r.amount);
      const tol = Math.max(0.8, la * 0.01);
      const amountDiff = Math.abs(la - ra);
      if (amountDiff > tol) continue;
      candidates.push({ l, r, amountDiff });
    }
  }

  // Emparejar greedy: mejor par primero (menor diferencia de monto)
  candidates.sort((a, b) => a.amountDiff - b.amountDiff);
  let nextMatchId = 1;
  for (const c of candidates) {
    if (c.l.matchId !== undefined || c.r.matchId !== undefined) continue;
    const id = nextMatchId++;
    c.l.matchId = id;
    c.r.matchId = id;
  }
}

/** Resumen global de reconciliación. Debe llamarse después de detectMatches. */
export function reconcile(items: DebtItem[]): Reconciliation {
  let totalLocal = 0;
  let totalSupabase = 0;
  let countOnlyLocal = 0;
  let countOnlySupabase = 0;
  let countMatched = 0; // pares heurísticos
  let countLinked = 0;  // pares vinculados manualmente

  for (const it of items) {
    if (it.side === 'local') {
      totalLocal += it.amount;
      if (it.linked) countLinked++;
      else if (it.matchId === undefined) countOnlyLocal++;
      else countMatched++;
    } else {
      if (!it.paid) totalSupabase += it.amount;
      if (!it.linked && it.matchId === undefined) countOnlySupabase++;
    }
  }

  return {
    totalLocal,
    totalSupabase,
    diff: totalLocal - totalSupabase,
    countOnlyLocal,
    countOnlySupabase,
    countMatched, // cuenta los items locales emparejados = número de pares
    countLinked,
  };
}

/** Pipeline completo: de datos crudos a bandas + reconciliación. */
export function buildTimeline(
  transactions: Transaction[] | undefined,
  debts: SupabaseDebt[] | undefined,
  granularity: Granularity,
): { bands: PeriodBand[]; reconciliation: Reconciliation; items: DebtItem[] } {
  const items = toDebtItems(transactions, debts);
  const bands = groupByPeriod(items, granularity);
  detectLinks(items);
  detectMatches(items);
  const reconciliation = reconcile(items);
  return { bands, reconciliation, items };
}
