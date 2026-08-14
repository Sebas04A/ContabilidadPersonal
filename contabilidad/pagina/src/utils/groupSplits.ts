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
