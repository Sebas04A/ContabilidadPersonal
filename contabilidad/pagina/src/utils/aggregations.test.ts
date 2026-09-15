import { describe, it, expect } from 'vitest';
import { Transaction } from '../services/api';
import { gastosPor } from './aggregations';

const tx = (MONTO: number, categoria: string, tags: string): Transaction => ({
  id: `${MONTO}${categoria}${tags}`, FECHA: '2026-09-01', DESCRIPCION: '', MONTO, TIPO: 'BANCA',
  nombre_limpio: '', categoria, tags, prioridad: '---', es_fijo: false, pertenece_a: '',
  es_reembolsable: false, deudor: '', felicidad: 0, revisado: true, nota: '', split_group_id: '',
});

const lista = [
  tx(-30, 'Ocio', 'cine, amigos'),
  tx(-10, 'Ocio', 'cine'),
  tx(-5, '---', ''),
  tx(100, 'Ocio', 'cine'), // ingreso: no cuenta
];

describe('gastosPor', () => {
  it('por categoría, del mayor al menor', () => {
    expect(gastosPor(lista, 'categoria').map(g => [g.name, g.value, g.count])).toEqual([
      ['Ocio', 40, 2],
      ['Sin Categoría', 5, 1],
    ]);
  });

  it('por tag con el monto entero en cada tag', () => {
    expect(gastosPor(lista, 'tag', 'full').map(g => [g.name, g.value, g.count])).toEqual([
      ['cine', 40, 2],
      ['amigos', 30, 1],
      ['Sin Etiqueta', 5, 1],
    ]);
  });

  it('por tag repartido: los totales suman el gasto real', () => {
    const grupos = gastosPor(lista, 'tag', 'proportional');
    expect(grupos.map(g => [g.name, g.value])).toEqual([
      ['cine', 25],
      ['amigos', 15],
      ['Sin Etiqueta', 5],
    ]);
    expect(grupos.reduce((s, g) => s + g.value, 0)).toBe(45);
  });
});
