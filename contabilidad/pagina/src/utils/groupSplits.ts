import { Transaction } from '../services/api';

/**
 * Collapse split transactions into a single display row.
 *
 * load_data() in the backend LEFT-JOINs the source rows against the labels CSV,
 * and a split transaction has one label row per part. That means the API returns
 * several rows sharing the same `id`. This merges them back into one row whose
 * MONTO is the sum of the parts, keeping the parts in `subTransactions`.
 */
export function groupSplits(txs: Transaction[] | undefined): Transaction[] {
  if (!txs) return [];

  const map = new Map<string, Transaction[]>();
  txs.forEach(t => {
    if (!map.has(t.id)) map.set(t.id, []);
    map.get(t.id)!.push(t);
  });

  const result: Transaction[] = [];
  map.forEach(parts => {
    if (parts.length === 1) {
      result.push(parts[0]);
    } else {
      const total = parts.reduce((sum, p) => sum + (p.MONTO || 0), 0);
      result.push({ ...parts[0], MONTO: total, subTransactions: parts });
    }
  });
  return result;
}

/**
 * Extracts an ISO-like sortable string "YYYY-MM-DD HH:MM" from a transaction.
 * Prioritizes HORA ('HH:MM') when present; falls back to time in FECHA or '00:00'.
 */
export function getEffectiveDateTime(t: Transaction): string {
  const datePart = (t.FECHA || '').slice(0, 10);
  let horaPart = t.HORA;
  if (!horaPart || horaPart.trim() === '') {
    if (t.FECHA && t.FECHA.length > 11) {
      horaPart = t.FECHA.slice(11, 16);
    } else {
      horaPart = '00:00';
    }
  }
  return `${datePart} ${horaPart}`;
}

/**
 * Sorts an array of transactions chronologically by FECHA and HORA.
 * @param txs Array of transactions
 * @param order 'asc' (morning to evening) or 'desc' (newest first)
 */
export function sortTransactions(txs: Transaction[] | undefined, order: 'asc' | 'desc' = 'desc'): Transaction[] {
  if (!txs || txs.length === 0) return [];
  return [...txs].sort((a, b) => {
    const dtA = getEffectiveDateTime(a);
    const dtB = getEffectiveDateTime(b);
    if (dtA !== dtB) {
      return order === 'asc' ? dtA.localeCompare(dtB) : dtB.localeCompare(dtA);
    }
    return a.id.localeCompare(b.id);
  });
}

