import { describe, it, expect } from 'vitest';
import { Transaction, FundListItem } from '../services/api';
import {
  DEFAULT_TRANSACTION_FILTERS, SIN_CATEGORIA, SIN_ETIQUETA, SIN_FONDO, TransactionFilters,
  applyTransactionFilters, matchesCategoryTag, matchesPriority, matchesFund,
  txCategory, txTags, cycleIncludeExclude, toggleFund, activeFundIds,
} from './transactionFilters';

const tx = (over: Partial<Transaction> = {}): Transaction => ({
  id: 'x', FECHA: '2026-09-01', DESCRIPCION: '', MONTO: -10, TIPO: 'BANCA',
  nombre_limpio: '', categoria: 'Alimentación', tags: '', prioridad: '---',
  es_fijo: false, pertenece_a: '', es_reembolsable: false, deudor: '',
  felicidad: 0, revisado: true, nota: '', split_group_id: '',
  ...over,
});

const fund = (id: string, tag_vinculado: string | null = null) =>
  ({ id, name: id, tag_vinculado } as unknown as FundListItem);

const filters = (over: Partial<TransactionFilters> = {}): TransactionFilters => ({ ...DEFAULT_TRANSACTION_FILTERS, ...over });

describe('categoría y tags de una transacción', () => {
  it('vacía, espacios o --- es Sin Categoría', () => {
    expect(txCategory(tx({ categoria: '' }))).toBe(SIN_CATEGORIA);
    expect(txCategory(tx({ categoria: '  ' }))).toBe(SIN_CATEGORIA);
    expect(txCategory(tx({ categoria: '---' }))).toBe(SIN_CATEGORIA);
    expect(txCategory(tx({ categoria: ' Ocio ' }))).toBe('Ocio');
  });

  it('separa tags, limpia y sin tags es Sin Etiqueta', () => {
    expect(txTags(tx({ tags: 'uber, viaje ,,' }))).toEqual(['uber', 'viaje']);
    expect(txTags(tx({ tags: '' }))).toEqual([SIN_ETIQUETA]);
    expect(txTags(tx({ tags: '---' }))).toEqual([SIN_ETIQUETA]);
  });
});

describe('matchesCategoryTag', () => {
  const base = { includedCategories: [], excludedCategories: [], includedTags: [], excludedTags: [] };

  it('sin filtros pasa todo', () => {
    expect(matchesCategoryTag(tx(), base)).toBe(true);
  });

  it('inclusiones: O dentro del grupo, Y entre categoría y tag', () => {
    const t = tx({ categoria: 'Ocio', tags: 'cine' });
    expect(matchesCategoryTag(t, { ...base, includedCategories: ['Salud', 'Ocio'] })).toBe(true);
    expect(matchesCategoryTag(t, { ...base, includedCategories: ['Ocio'], includedTags: ['cine'] })).toBe(true);
    expect(matchesCategoryTag(t, { ...base, includedCategories: ['Ocio'], includedTags: ['bar'] })).toBe(false);
  });

  it('la exclusión gana sobre la inclusión', () => {
    const t = tx({ categoria: 'Ocio', tags: 'cine' });
    expect(matchesCategoryTag(t, { ...base, includedCategories: ['Ocio'], excludedTags: ['cine'] })).toBe(false);
  });

  it('el nombre visible y la clave vieja del explorador son lo mismo', () => {
    const sinNada = tx({ categoria: '---', tags: '' });
    for (const f of [
      { ...base, excludedCategories: [SIN_CATEGORIA] },
      { ...base, excludedCategories: ['__sin_categoria__'] },
      { ...base, excludedTags: [SIN_ETIQUETA] },
      { ...base, excludedTags: ['__sin_tags__'] },
    ]) {
      expect(matchesCategoryTag(sinNada, f)).toBe(false);
    }
    expect(matchesCategoryTag(sinNada, { ...base, includedTags: ['__sin_tags__'] })).toBe(true);
  });

  it('los tags se comparan sin mayúsculas ni espacios', () => {
    expect(matchesCategoryTag(tx({ tags: 'Uber' }), { ...base, includedTags: ['uber '] })).toBe(true);
    expect(matchesCategoryTag(tx({ tags: 'Uber' }), { ...base, excludedTags: ['UBER'] })).toBe(false);
  });
});

describe('matchesPriority', () => {
  const gasto = (prioridad: string) => tx({ MONTO: -5, prioridad });
  const ingreso = tx({ MONTO: 100, prioridad: '---' });

  it('los ingresos siguen pasando en necesidades, deseos y clasificadas', () => {
    for (const p of ['needs', 'wants', 'rated'] as const) {
      expect(matchesPriority(ingreso, p)).toBe(true);
    }
  });

  it('filtra gastos por su prioridad', () => {
    expect(matchesPriority(gasto('Necesidad'), 'needs')).toBe(true);
    expect(matchesPriority(gasto('Deseo'), 'needs')).toBe(false);
    expect(matchesPriority(gasto('Deseo'), 'wants')).toBe(true);
    expect(matchesPriority(gasto('---'), 'rated')).toBe(false);
  });

  it('sin calificar: solo gastos sin prioridad', () => {
    expect(matchesPriority(gasto('---'), 'unrated')).toBe(true);
    expect(matchesPriority(gasto(''), 'unrated')).toBe(true);
    expect(matchesPriority(gasto('Deseo'), 'unrated')).toBe(false);
    expect(matchesPriority(ingreso, 'unrated')).toBe(false);
  });
});

describe('fondos', () => {
  const funds = [fund('f1', 'viaje'), fund('f2')];
  const enF1 = tx({ tags: 'viaje' });
  const enF2 = tx({ fondo_id: 'f2' });
  const sinFondo = tx();

  it('null deja pasar todo', () => {
    expect([enF1, enF2, sinFondo].every(t => matchesFund(t, null, funds))).toBe(true);
  });

  it('lo que no tiene fondo pasa solo con SIN_FONDO marcado', () => {
    expect(matchesFund(sinFondo, ['f1'], funds)).toBe(false);
    expect(matchesFund(sinFondo, ['f1', SIN_FONDO], funds)).toBe(true);
    expect(matchesFund(enF1, ['f1'], funds)).toBe(true);
    expect(matchesFund(enF2, ['f1', SIN_FONDO], funds)).toBe(false);
  });

  it('marcar todo vuelve a null y desmarcar parte de todos', () => {
    expect(activeFundIds(null, funds)).toEqual(['f1', 'f2', SIN_FONDO]);
    expect(toggleFund('f2', null, funds)).toEqual(['f1', SIN_FONDO]);
    expect(toggleFund('f2', ['f1', SIN_FONDO], funds)).toBeNull();
  });
});

describe('cycleIncludeExclude', () => {
  it('sin filtro → solo mostrar → ocultar → sin filtro', () => {
    let s = { included: [] as string[], excluded: [] as string[] };
    s = cycleIncludeExclude('Ocio', s.included, s.excluded);
    expect(s).toEqual({ included: ['Ocio'], excluded: [] });
    s = cycleIncludeExclude('Ocio', s.included, s.excluded);
    expect(s).toEqual({ included: [], excluded: ['Ocio'] });
    s = cycleIncludeExclude('Ocio', s.included, s.excluded);
    expect(s).toEqual({ included: [], excluded: [] });
  });
});

describe('applyTransactionFilters', () => {
  it('combina todos los filtros con Y', () => {
    const list = [
      tx({ id: 'a', MONTO: -20, TIPO: 'TARJETA', es_reembolsable: true }),
      tx({ id: 'b', MONTO: -20, TIPO: 'BANCA' }),
      tx({ id: 'c', MONTO: 50, TIPO: 'BANCA' }),
      tx({ id: 'd', MONTO: -5, TIPO: 'BANCA', revisado: false, es_fijo: true }),
    ];
    const ids = (f: TransactionFilters) => applyTransactionFilters(list, f, []).map(t => t.id);
    expect(ids(filters())).toEqual(['a', 'b', 'c', 'd']);
    expect(ids(filters({ reimbursable: 'excluded', sourceType: 'banca' }))).toEqual(['b', 'c', 'd']);
    expect(ids(filters({ type: 'expenses', labeled: 'labeled' }))).toEqual(['a', 'b']);
    expect(ids(filters({ fixed: 'fixed' }))).toEqual(['d']);
    expect(ids(filters({ type: 'income' }))).toEqual(['c']);
  });

  it('una división se filtra parte por parte', () => {
    const partes = [
      tx({ id: 's', MONTO: -30, categoria: 'Ocio' }),
      tx({ id: 's', MONTO: -10, categoria: 'Salud' }),
    ];
    const r = applyTransactionFilters(partes, filters({ excludedCategories: ['Ocio'] }), []);
    expect(r.map(t => t.categoria)).toEqual(['Salud']);
  });
});
