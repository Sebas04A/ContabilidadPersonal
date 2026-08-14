import { Transaction, FundListItem } from '../services/api';

function normalize(s: string | null | undefined): string {
  if (!s) return '';
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').trim().toLowerCase();
}

/**
 * Fondo al que pertenece una transacción: por `fondo_id` explícito (asignación
 * manual desde la página de Fondos) o porque lleva el tag vinculado del fondo.
 *
 * Es una búsqueda en memoria sobre la lista de fondos (una decena), sin llamadas
 * extra: `fondo_id` y `tags` ya vienen en cada transacción.
 */
export function matchFund(t: Transaction, funds: FundListItem[] | undefined): FundListItem | null {
  if (!funds || funds.length === 0) return null;
  const txTags = (t.tags || '').split(',').map(x => normalize(x)).filter(Boolean);
  for (const f of funds) {
    if (t.fondo_id && t.fondo_id === f.id) return f;
    const linked = normalize(f.tag_vinculado);
    if (linked && txTags.includes(linked)) return f;
  }
  return null;
}
