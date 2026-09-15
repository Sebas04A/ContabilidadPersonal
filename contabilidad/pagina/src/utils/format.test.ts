import { describe, it, expect } from 'vitest';
import { fmt, money, signedMoney, pct } from './format';
import { parseTags } from './tags';
import { normalizeText } from './text';

describe('format', () => {
  it('dinero en dólares con centavos y coma de miles', () => {
    expect(money(1234.5)).toBe('$1,234.50');
    expect(money(-12)).toBe('-$12.00');
    expect(money(1234.56, 0)).toBe('$1,235');
  });

  it('signo siempre visible', () => {
    expect(signedMoney(5)).toBe('+$5.00');
    expect(signedMoney(-5)).toBe('−$5.00');
    expect(signedMoney(0)).toBe('+$0.00');
  });

  it('números y porcentajes', () => {
    expect(fmt(1234.567)).toBe('1,234.57');
    expect(fmt(3, 0)).toBe('3');
    expect(pct(12.5)).toBe('12.50 %');
  });

  it('nulo o NaN es una raya', () => {
    for (const f of [fmt, money, signedMoney, pct]) {
      expect(f(null)).toBe('—');
      expect(f(undefined)).toBe('—');
      expect(f(NaN)).toBe('—');
    }
  });
});

describe('parseTags', () => {
  it('separa, limpia y descarta vacíos y ---', () => {
    expect(parseTags(' uber, viaje ,,---')).toEqual(['uber', 'viaje']);
    expect(parseTags('')).toEqual([]);
    expect(parseTags(undefined)).toEqual([]);
  });
});

describe('normalizeText', () => {
  it('sin acentos, espacios ni mayúsculas', () => {
    expect(normalizeText('  Inversión ')).toBe('inversion');
    expect(normalizeText(null)).toBe('');
  });
});
