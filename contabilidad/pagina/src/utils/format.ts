/**
 * Formato de números y dinero de toda la página: dólares, punto decimal y coma de miles
 * (1,234.56). Un valor nulo o NaN se muestra como '—'.
 */

type Num = number | null | undefined;

const vacio = (n: Num): n is null | undefined => n === null || n === undefined || Number.isNaN(n);

/** Número con decimales fijos: 1,234.56. */
export const fmt = (n: Num, decimales = 2): string =>
  vacio(n) ? '—' : n.toLocaleString('en-US', { minimumFractionDigits: decimales, maximumFractionDigits: decimales });

/** Dinero: -$1,234.56. */
export const money = (n: Num, decimales = 2): string =>
  vacio(n)
    ? '—'
    : n.toLocaleString('en-US', {
        style: 'currency', currency: 'USD', minimumFractionDigits: decimales, maximumFractionDigits: decimales,
      });

/** Dinero con signo siempre visible: +$1,234.56 / −$1,234.56. */
export const signedMoney = (n: Num, decimales = 2): string =>
  vacio(n) ? '—' : `${n >= 0 ? '+' : '−'}${money(Math.abs(n), decimales)}`;

/** Porcentaje: 12.50 %. */
export const pct = (n: Num, decimales = 2): string => (vacio(n) ? '—' : `${fmt(n, decimales)} %`);
