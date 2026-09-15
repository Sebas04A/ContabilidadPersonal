import { Transaction } from '../services/api';
import { txCategory, txTags } from './transactionFilters';

/**
 * Cómo cuenta el monto de un gasto con varios tags: repartido entre ellos
 * ('proportional', los totales suman el gasto real) o entero en cada uno ('full',
 * los totales se solapan y no son aditivos).
 */
export type TagMode = 'proportional' | 'full';

export interface GrupoGasto {
  /** Categoría o tag; SIN_CATEGORIA / SIN_ETIQUETA cuando falta. */
  name: string;
  /** Gasto total, en positivo. */
  value: number;
  /** Cuántos gastos entran en el grupo. */
  count: number;
  txs: Transaction[];
}

/** Gastos (MONTO < 0) agrupados por categoría o por tag, del mayor al menor. */
export function gastosPor(txs: Transaction[], dim: 'categoria' | 'tag', tagMode: TagMode = 'full'): GrupoGasto[] {
  const grupos = new Map<string, GrupoGasto>();
  const sumar = (name: string, monto: number, t: Transaction) => {
    let g = grupos.get(name);
    if (!g) {
      g = { name, value: 0, count: 0, txs: [] };
      grupos.set(name, g);
    }
    g.value += monto;
    g.count += 1;
    g.txs.push(t);
  };

  for (const t of txs) {
    if (!(t.MONTO < 0)) continue;
    const monto = Math.abs(t.MONTO);
    if (dim === 'categoria') {
      sumar(txCategory(t), monto, t);
      continue;
    }
    const tags = txTags(t);
    const parte = tagMode === 'proportional' ? monto / tags.length : monto;
    for (const tag of tags) sumar(tag, parte, t);
  }

  return [...grupos.values()].sort((a, b) => b.value - a.value);
}
