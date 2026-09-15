import { Transaction, FundListItem } from '../services/api';
import { matchFund } from './matchFund';
import { parseTags } from './tags';

/**
 * Filtros de transacciones compartidos por Presupuesto y el Explorador.
 *
 * Se aplican sobre las filas tal como llegan de la API, antes de `groupSplits`:
 * cada parte de una división es su propia fila con su categoría, tags y fondo,
 * así que una división se filtra parte por parte.
 */

export const SIN_CATEGORIA = 'Sin Categoría';
export const SIN_ETIQUETA = 'Sin Etiqueta';
/** Pseudo-fondo de las transacciones que no pertenecen a ningún fondo. */
export const SIN_FONDO = '__sin_fondo__';

// Claves viejas del Explorador para "sin categoría" y "sin tags".
const ALIAS: Record<string, string> = {
  __sin_categoria__: SIN_CATEGORIA,
  __sin_tags__: SIN_ETIQUETA,
};

export type ReimbursableFilterOption = 'all' | 'included' | 'excluded';
export type PriorityFilterOption = 'all' | 'needs' | 'wants' | 'rated' | 'unrated';
export type LabeledFilterOption = 'all' | 'labeled' | 'unlabeled';
export type TypeFilterOption = 'all' | 'expenses' | 'income';
export type FixedFilterOption = 'all' | 'fixed' | 'non_fixed';

export interface TransactionFilters {
  /** Si hay alguna, solo pasan esas categorías (O entre ellas). */
  includedCategories: string[];
  excludedCategories: string[];
  /** Si hay alguna, solo pasan las transacciones con alguno de esos tags. */
  includedTags: string[];
  excludedTags: string[];
  /** null = todos los fondos y lo que no tiene fondo; si no, los ids marcados (y SIN_FONDO). */
  selectedFunds: string[] | null;
  reimbursable: ReimbursableFilterOption;
  priority: PriorityFilterOption;
  labeled: LabeledFilterOption;
  type: TypeFilterOption;
  fixed: FixedFilterOption;
  /** 'BANCA' o 'TARJETA'; '' = las dos. */
  sourceType: string;
}

export const DEFAULT_TRANSACTION_FILTERS: TransactionFilters = {
  includedCategories: [],
  excludedCategories: [],
  includedTags: [],
  excludedTags: [],
  selectedFunds: null,
  reimbursable: 'all',
  priority: 'all',
  labeled: 'all',
  type: 'all',
  fixed: 'all',
  sourceType: '',
};

const isBlank = (s?: string | null) => !s || s.trim() === '' || s.trim() === '---';

/** Clave de comparación: sin espacios, sin mayúsculas y con los alias resueltos. */
const key = (s: string) => (ALIAS[s] ?? s).trim().toLowerCase();

/** Categoría de una transacción; vacía o '---' es SIN_CATEGORIA. */
export function txCategory(t: Transaction): string {
  return isBlank(t.categoria) ? SIN_CATEGORIA : t.categoria.trim();
}

/** Tags de una transacción; sin tags cuenta como la pseudo-etiqueta SIN_ETIQUETA. */
export function txTags(t: Transaction): string[] {
  const tags = parseTags(t.tags);
  return tags.length > 0 ? tags : [SIN_ETIQUETA];
}

/**
 * Categorías y tags. Las inclusiones se combinan con Y entre categoría y tag (si hay
 * de ambas, deben cumplirse las dos) y con O dentro de cada grupo. Las exclusiones
 * se aplican después y siempre ganan.
 */
export function matchesCategoryTag(t: Transaction, f: CategoryTagFilters): boolean {
  return categoryTagMatcher(f)(t);
}

type CategoryTagFilters = Pick<TransactionFilters, 'includedCategories' | 'excludedCategories' | 'includedTags' | 'excludedTags'>;

// Las claves de los filtros se calculan una vez por lista, no una vez por fila.
function categoryTagMatcher(f: CategoryTagFilters): (t: Transaction) => boolean {
  const incCat = new Set(f.includedCategories.map(key));
  const excCat = new Set(f.excludedCategories.map(key));
  const incTag = new Set(f.includedTags.map(key));
  const excTag = new Set(f.excludedTags.map(key));
  if (incCat.size + excCat.size + incTag.size + excTag.size === 0) return () => true;
  return t => {
    const cat = key(txCategory(t));
    const tags = txTags(t).map(key);
    if (incCat.size > 0 && !incCat.has(cat)) return false;
    if (incTag.size > 0 && !tags.some(tg => incTag.has(tg))) return false;
    if (excCat.has(cat)) return false;
    if (tags.some(tg => excTag.has(tg))) return false;
    return true;
  };
}

/** Fondo: pasa si su fondo está marcado, o si no tiene fondo y SIN_FONDO está marcado. */
export function matchesFund(t: Transaction, selectedFunds: string[] | null, funds: FundListItem[] | undefined): boolean {
  if (selectedFunds === null) return true;
  const fund = matchFund(t, funds);
  return selectedFunds.includes(fund ? fund.id : SIN_FONDO);
}

/**
 * Prioridad. Los ingresos no se clasifican como Necesidad/Deseo, así que siguen
 * pasando (y cuentan para los porcentajes); 'unrated' es solo para gastos.
 */
export function matchesPriority(t: Transaction, priority: PriorityFilterOption): boolean {
  if (priority === 'all') return true;
  if (priority === 'unrated') return t.MONTO < 0 && isBlank(t.prioridad);
  if (t.MONTO >= 0) return true;
  if (priority === 'needs') return t.prioridad === 'Necesidad';
  if (priority === 'wants') return t.prioridad === 'Deseo';
  return t.prioridad === 'Necesidad' || t.prioridad === 'Deseo';
}

function transactionMatcher(f: TransactionFilters, funds: FundListItem[] | undefined): (t: Transaction) => boolean {
  const categoryTag = categoryTagMatcher(f);
  const source = f.sourceType.toUpperCase();
  return t => {
    if (f.reimbursable === 'included' && !t.es_reembolsable) return false;
    if (f.reimbursable === 'excluded' && t.es_reembolsable) return false;
    if (f.labeled === 'labeled' && !t.revisado) return false;
    if (f.labeled === 'unlabeled' && t.revisado) return false;
    if (f.type === 'expenses' && !(t.MONTO < 0)) return false;
    if (f.type === 'income' && !(t.MONTO > 0)) return false;
    if (f.fixed === 'fixed' && !t.es_fijo) return false;
    if (f.fixed === 'non_fixed' && t.es_fijo) return false;
    if (source && (t.TIPO || '').toUpperCase() !== source) return false;
    if (!matchesPriority(t, f.priority)) return false;
    if (!matchesFund(t, f.selectedFunds, funds)) return false;
    return categoryTag(t);
  };
}

export function matchesTransactionFilters(t: Transaction, f: TransactionFilters, funds: FundListItem[] | undefined): boolean {
  return transactionMatcher(f, funds)(t);
}

export function applyTransactionFilters(list: Transaction[], f: TransactionFilters, funds: FundListItem[] | undefined): Transaction[] {
  return list.filter(transactionMatcher(f, funds));
}

/** Clic en un chip de categoría/tag: sin filtro → solo mostrar → ocultar → sin filtro. */
export function cycleIncludeExclude(value: string, included: string[], excluded: string[]): { included: string[]; excluded: string[] } {
  if (included.includes(value)) {
    return { included: included.filter(v => v !== value), excluded: [...excluded, value] };
  }
  if (excluded.includes(value)) {
    return { included, excluded: excluded.filter(v => v !== value) };
  }
  return { included: [...included, value], excluded };
}

/** Ids marcados en el selector de fondos; null equivale a todos más SIN_FONDO. */
export function activeFundIds(selectedFunds: string[] | null, funds: FundListItem[] | undefined): string[] {
  return selectedFunds ?? [...(funds ?? []).map(f => f.id), SIN_FONDO];
}

/** Marca o desmarca un fondo (o SIN_FONDO); si quedan todos marcados vuelve a null. */
export function toggleFund(id: string, selectedFunds: string[] | null, funds: FundListItem[] | undefined): string[] | null {
  const current = activeFundIds(selectedFunds, funds);
  const next = current.includes(id) ? current.filter(x => x !== id) : [...current, id];
  const all = activeFundIds(null, funds);
  return all.every(x => next.includes(x)) ? null : next;
}
