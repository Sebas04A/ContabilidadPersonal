/**
 * El lenguaje visual de los gráficos de ECharts, en un solo sitio. Cada gráfico lo
 * extiende: `tooltip: { ...TOOLTIP, trigger: 'axis', formatter }`.
 */

export const TOOLTIP = {
  backgroundColor: 'rgba(9,9,11,0.92)',
  borderColor: 'rgba(255,255,255,0.1)',
  textStyle: { color: '#e4e4e7', fontSize: 12 },
};

export const EJE = {
  axisLine: { lineStyle: { color: '#3f3f46' } },
  axisLabel: { color: '#a1a1aa', fontSize: 11 },
};

export const GRID = { top: 40, right: 60, bottom: 50, left: 70 };
