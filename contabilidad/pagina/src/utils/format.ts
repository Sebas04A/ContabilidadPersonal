/** Dinero en dólares con centavos: -$1,234.50. */
export const money = (n: number | null | undefined): string =>
  n === null || n === undefined || Number.isNaN(n)
    ? '—'
    : n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
