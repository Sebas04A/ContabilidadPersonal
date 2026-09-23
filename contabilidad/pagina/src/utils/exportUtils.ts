import { Transaction, FundListItem } from '../services/api';
import { DebtLookup, debtPerson, linkedDebtStatus, debtDirection } from './debtFilters';
import { matchFund } from './matchFund';
import { money } from './format';

export type ExportFormat =
  | 'excel'
  | 'csv_comma'
  | 'csv_semicolon'
  | 'markdown'
  | 'text_list'
  | 'json';

export type ColumnCategory = 'basic' | 'naming' | 'classification' | 'debt' | 'meta';

export interface ExportColumn {
  id: string;
  label: string;
  category: ColumnCategory;
  default: boolean;
  align?: 'left' | 'right' | 'center';
  description?: string;
  getValue: (t: Transaction, extra: ExportContext) => string | number;
}

export interface ExportContext {
  funds?: FundListItem[];
  debtLookup?: DebtLookup;
}

export const EXPORT_COLUMNS: ExportColumn[] = [
  // 1. Fecha y Horas
  {
    id: 'fecha',
    label: 'Fecha',
    category: 'basic',
    default: true,
    align: 'center',
    description: 'Fecha en formato YYYY-MM-DD',
    getValue: (t) => (t.FECHA ? t.FECHA.substring(0, 10) : ''),
  },
  {
    id: 'hora',
    label: 'Hora',
    category: 'basic',
    default: false,
    align: 'center',
    description: 'Hora de la transacción (HH:MM)',
    getValue: (t) => t.HORA || '',
  },
  {
    id: 'tipo',
    label: 'Fuente / Tipo',
    category: 'basic',
    default: true,
    align: 'center',
    description: 'Origen: BANCA, TARJETA o DEUDA',
    getValue: (t) => t.TIPO || 'BANCA',
  },

  // 2. Nombres y Descripciones
  {
    id: 'concepto',
    label: 'Concepto',
    category: 'naming',
    default: true,
    align: 'left',
    description: 'Concepto o detalle de la transacción',
    getValue: (t) => t.DESCRIPCION || '',
  },
  {
    id: 'nombre_limpio',
    label: 'Nombre Limpio / Comercio',
    category: 'naming',
    default: true,
    align: 'left',
    description: 'Nombre normalizado del establecimiento o contacto',
    getValue: (t) => t.nombre_limpio || t.DESCRIPCION || '',
  },
  {
    id: 'descripcion',
    label: 'Descripción Bancaria Original',
    category: 'naming',
    default: false,
    align: 'left',
    description: 'Texto crudo del extracto bancario o tarjeta',
    getValue: (t) => t.DESCRIPCION || '',
  },

  // 3. Clasificación
  {
    id: 'categoria',
    label: 'Categoría',
    category: 'classification',
    default: true,
    align: 'left',
    description: 'Categoría asignada a la transacción',
    getValue: (t) => t.categoria || 'Sin Categoría',
  },
  {
    id: 'tags',
    label: 'Etiquetas',
    category: 'classification',
    default: true,
    align: 'left',
    description: 'Etiquetas personalizadas separadas por coma',
    getValue: (t) => t.tags || '',
  },

  // 4. Montos
  {
    id: 'monto',
    label: 'Monto',
    category: 'basic',
    default: true,
    align: 'right',
    description: 'Valor numérico (positivo para ingreso, negativo para gasto)',
    getValue: (t) => t.MONTO ?? 0,
  },
  {
    id: 'monto_formateado',
    label: 'Monto Formateado',
    category: 'basic',
    default: false,
    align: 'right',
    description: 'Valor formateado con signo de moneda ($)',
    getValue: (t) => money(t.MONTO ?? 0),
  },

  // 5. Deudas y Reembolsos
  {
    id: 'reembolsable',
    label: 'Reembolsable',
    category: 'debt',
    default: false,
    align: 'center',
    description: '¿Es un gasto que te deben reembolsar? (Sí/No)',
    getValue: (t) => (t.es_reembolsable ? 'Sí' : 'No'),
  },
  {
    id: 'deudor',
    label: 'Persona / Deudor',
    category: 'debt',
    default: false,
    align: 'left',
    description: 'Persona asociada a la deuda o reembolso',
    getValue: (t, ctx) => (ctx.debtLookup ? debtPerson(t, ctx.debtLookup) : t.deudor) || t.deudor || '',
  },
  {
    id: 'deuda_estado',
    label: 'Estado Deuda',
    category: 'debt',
    default: false,
    align: 'center',
    description: 'Estado en Supabase: Pagada, Parcial, Pendiente o Sin vincular',
    getValue: (t, ctx) => {
      if (ctx.debtLookup) {
        const st = linkedDebtStatus(t, ctx.debtLookup);
        if (st === 'paid') return 'Pagada';
        if (st === 'partial') return 'Parcial';
        if (st === 'pending') return 'Pendiente';
      }
      if (t.deuda_id) return 'Vinculada';
      if (t.pago_id) return 'Pago vinculado';
      if (t.es_reembolsable) return 'Sin vincular';
      return '';
    },
  },
  {
    id: 'deuda_direccion',
    label: 'Dirección Deuda',
    category: 'debt',
    default: false,
    align: 'center',
    description: 'Indica si tú debes o te deben',
    getValue: (t, ctx) => {
      if (ctx.debtLookup) {
        const dir = debtDirection(t, ctx.debtLookup);
        if (dir === 'debo') return 'Debo';
        if (dir === 'me_deben') return 'Me deben';
      }
      if (t.TIPO === 'DEUDA') return 'Debo';
      if (t.es_reembolsable) return 'Me deben';
      return '';
    },
  },
  {
    id: 'deuda_saldo',
    label: 'Saldo Pendiente Deuda',
    category: 'debt',
    default: false,
    align: 'right',
    description: 'Monto restante pendiente de la deuda vinculada',
    getValue: (t, ctx) => {
      if (t.SALDO_DEUDA != null) return t.SALDO_DEUDA;
      if (ctx.debtLookup && t.deuda_id) {
        const debt = ctx.debtLookup.debts.get(String(t.deuda_id));
        if (debt?.SALDO_PENDIENTE != null) return debt.SALDO_PENDIENTE;
      }
      return '';
    },
  },

  // 6. Clasificación Adicional
  {
    id: 'es_fijo',
    label: 'Gasto Fijo',
    category: 'classification',
    default: false,
    align: 'center',
    description: 'Indica si es un gasto fijo recurrente (Sí/No)',
    getValue: (t) => (t.es_fijo ? 'Sí' : 'No'),
  },
  {
    id: 'fondo',
    label: 'Fondo',
    category: 'classification',
    default: false,
    align: 'left',
    description: 'Fondo o ahorro asignado',
    getValue: (t, ctx) => matchFund(t, ctx.funds)?.name || '',
  },
  {
    id: 'prioridad',
    label: 'Prioridad',
    category: 'classification',
    default: false,
    align: 'center',
    description: 'Clasificación de necesidad (Needs, Wants, etc.)',
    getValue: (t) => t.prioridad || '',
  },

  // 7. Notas y Metadatos
  {
    id: 'nota',
    label: 'Nota',
    category: 'meta',
    default: false,
    align: 'left',
    description: 'Nota personal o comentario añadido',
    getValue: (t) => t.nota || '',
  },
  {
    id: 'felicidad',
    label: 'Felicidad',
    category: 'meta',
    default: false,
    align: 'center',
    description: 'Puntuación de satisfacción (1 a 5)',
    getValue: (t) => (t.felicidad != null ? t.felicidad : ''),
  },
  {
    id: 'revisado',
    label: 'Revisado',
    category: 'meta',
    default: false,
    align: 'center',
    description: 'Indica si la transacción ya fue revisada (Sí/No)',
    getValue: (t) => (t.revisado ? 'Sí' : 'No'),
  },
  {
    id: 'id',
    label: 'ID Transacción',
    category: 'meta',
    default: false,
    align: 'left',
    description: 'Identificador único del registro',
    getValue: (t) => t.id || '',
  },
];

export interface ColumnPreset {
  id: string;
  name: string;
  badge?: string;
  description: string;
  columnIds: string[];
}

export const COLUMN_PRESETS: ColumnPreset[] = [
  {
    id: 'default',
    name: 'Básico',
    badge: 'Recomendado',
    description: 'Fecha, Concepto, Comercio, Categoría, Tags y Monto',
    columnIds: ['fecha', 'concepto', 'nombre_limpio', 'categoria', 'tags', 'monto'],
  },
  {
    id: 'family_discrete',
    name: 'Compartir Familia',
    badge: 'Discreto',
    description: 'Solo Nombre, Fecha, Monto y Categoría. Oculta notas, tags, IDs y extractos del banco.',
    columnIds: ['fecha', 'nombre_limpio', 'categoria', 'monto'],
  },
  {
    id: 'debts',
    name: 'Deudas y Reembolsos',
    badge: 'Cobros / Pagos',
    description: 'Fecha, Comercio, Monto, Persona, Estado, Dirección, Saldo y Reembolsable',
    columnIds: ['fecha', 'nombre_limpio', 'monto', 'deudor', 'deuda_estado', 'deuda_direccion', 'deuda_saldo', 'reembolsable'],
  },
  {
    id: 'audit',
    name: 'Extracto y Auditoría',
    badge: 'Banco Original',
    description: 'Fecha, Hora, Tipo, Descripción Bancaria Original, Comercio, Categoría y Monto',
    columnIds: ['fecha', 'hora', 'tipo', 'descripcion', 'nombre_limpio', 'categoria', 'monto'],
  },
  {
    id: 'minimal',
    name: 'Simple',
    badge: 'Mínimo',
    description: 'Solo Fecha, Comercio y Monto',
    columnIds: ['fecha', 'nombre_limpio', 'monto'],
  },
  {
    id: 'all',
    name: 'Todas las Columnas',
    badge: 'Completo',
    description: 'Exporta todas las columnas y metadatos disponibles',
    columnIds: EXPORT_COLUMNS.map((c) => c.id),
  },
];

export const COLUMN_CATEGORIES: { id: ColumnCategory; label: string; iconName: string }[] = [
  { id: 'basic', label: 'Básicos e Importes', iconName: 'Calendar' },
  { id: 'naming', label: 'Nombres y Descripciones', iconName: 'FileText' },
  { id: 'classification', label: 'Categorías y Clasificación', iconName: 'Tag' },
  { id: 'debt', label: 'Deudas y Reembolsos', iconName: 'Users' },
  { id: 'meta', label: 'Notas y Metadatos', iconName: 'FileSignature' },
];

export interface ExportSummaryStats {
  count: number;
  income: number;
  expenses: number;
  net: number;
  minDate?: string;
  maxDate?: string;
  debtCount: number;
  reimbursableTotal: number;
  pendingDebtTotal: number;
  topCategories: { category: string; total: number; count: number }[];
  topTags: { tag: string; total: number; count: number }[];
  activeDaysCount: number;
  avgDailyExpense: number;
  highestExpense: { descripcion: string; monto: number; fecha: string } | null;
  peakSpendDay: { fecha: string; total: number; count: number } | null;
  savingsRate: number | null;
}

export interface SummaryGeneratorOptions {
  includeTotals?: boolean;
  includeDateRange?: boolean;
  includeDebts?: boolean;
  includeCategories?: boolean;
  includeTags?: boolean;
  includeInsights?: boolean;
  title?: string;
}

export interface ExportOptions {
  format: ExportFormat;
  selectedColumnIds: string[];
  flattenSplits: boolean;
  includeHeaders: boolean;
  includeSummary: boolean;
  summaryPosition?: 'bottom' | 'top' | 'only';
  customSummaryText?: string;
  numberFormat: 'raw' | 'formatted'; // e.g. raw (-12000.5) vs formatted ($ -12.000,50)
}

/**
 * Prepares the transaction list by flattening splits if requested.
 */
export function prepareTransactionsForExport(
  transactions: Transaction[],
  flattenSplits: boolean
): Transaction[] {
  if (!flattenSplits) return transactions;

  const result: Transaction[] = [];
  transactions.forEach((tx) => {
    if (tx.subTransactions && tx.subTransactions.length > 0) {
      tx.subTransactions.forEach((sub, subIdx) => {
        result.push({
          ...sub,
          id: `${tx.id}_sub_${subIdx}`,
          FECHA: sub.FECHA || tx.FECHA,
          HORA: sub.HORA ?? tx.HORA,
          TIPO: sub.TIPO || tx.TIPO,
          DESCRIPCION: sub.DESCRIPCION || tx.DESCRIPCION,
          nombre_limpio: sub.nombre_limpio || tx.nombre_limpio,
          categoria: sub.categoria || tx.categoria,
          tags: sub.tags || tx.tags,
          MONTO: sub.MONTO ?? 0,
          nota: sub.nota || tx.nota,
        });
      });
    } else {
      result.push(tx);
    }
  });

  return result;
}

/**
 * Calculates quick financial totals, debt stats, tags, and date insights for export summaries.
 */
export function calculateExportSummary(
  transactions: Transaction[],
  context?: ExportContext
): ExportSummaryStats {
  let income = 0;
  let expenses = 0;
  let count = transactions.length;
  let minDate = '';
  let maxDate = '';
  let debtCount = 0;
  let reimbursableTotal = 0;
  let pendingDebtTotal = 0;

  const categoryMap = new Map<string, { total: number; count: number }>();
  const tagMap = new Map<string, { total: number; count: number }>();
  const dailyExpenseMap = new Map<string, { total: number; count: number }>();
  let highestExpense: { descripcion: string; monto: number; fecha: string } | null = null;

  transactions.forEach((t) => {
    const val = Number(t.MONTO) || 0;
    if (val > 0) {
      income += val;
    } else {
      expenses += val;
      // Track highest individual expense
      if (!highestExpense || val < highestExpense.monto) {
        highestExpense = {
          descripcion: t.nombre_limpio || t.DESCRIPCION || 'Gasto',
          monto: val,
          fecha: t.FECHA ? t.FECHA.substring(0, 10) : '',
        };
      }
    }

    // Dates & daily spend
    if (t.FECHA) {
      const d = t.FECHA.substring(0, 10);
      if (!minDate || d < minDate) minDate = d;
      if (!maxDate || d > maxDate) maxDate = d;

      if (val < 0) {
        const dayData = dailyExpenseMap.get(d) || { total: 0, count: 0 };
        dayData.total += val;
        dayData.count += 1;
        dailyExpenseMap.set(d, dayData);
      }
    }

    // Categories
    const cat = t.categoria || 'Sin Categoría';
    const currentCat = categoryMap.get(cat) || { total: 0, count: 0 };
    currentCat.total += val;
    currentCat.count += 1;
    categoryMap.set(cat, currentCat);

    // Tags
    if (t.tags && typeof t.tags === 'string') {
      const splitTags = t.tags
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      splitTags.forEach((tag) => {
        const currentTag = tagMap.get(tag) || { total: 0, count: 0 };
        currentTag.total += val;
        currentTag.count += 1;
        tagMap.set(tag, currentTag);
      });
    }

    // Debts & Reimbursable
    const hasDebt = !!(t.deuda_id || t.pago_id || t.es_reembolsable || (t.deudor && t.deudor !== '---'));
    if (hasDebt) {
      debtCount += 1;
      if (t.es_reembolsable) {
        reimbursableTotal += Math.abs(val);
      }
      if (context?.debtLookup && t.deuda_id) {
        const d = context.debtLookup.debts.get(String(t.deuda_id));
        if (d?.SALDO_PENDIENTE != null) {
          pendingDebtTotal += Number(d.SALDO_PENDIENTE);
        }
      } else if (t.SALDO_DEUDA != null) {
        pendingDebtTotal += Number(t.SALDO_DEUDA);
      }
    }
  });

  const topCategories = Array.from(categoryMap.entries())
    .map(([category, d]) => ({ category, total: d.total, count: d.count }))
    .sort((a, b) => Math.abs(b.total) - Math.abs(a.total));

  const topTags = Array.from(tagMap.entries())
    .map(([tag, d]) => ({ tag, total: d.total, count: d.count }))
    .sort((a, b) => Math.abs(b.total) - Math.abs(a.total));

  // Peak expense day
  let peakSpendDay: { fecha: string; total: number; count: number } | null = null;
  dailyExpenseMap.forEach((data, fecha) => {
    if (!peakSpendDay || data.total < peakSpendDay.total) {
      peakSpendDay = { fecha, total: data.total, count: data.count };
    }
  });

  const activeDaysCount = dailyExpenseMap.size;
  const avgDailyExpense = activeDaysCount > 0 ? Math.abs(expenses) / activeDaysCount : 0;
  const savingsRate = income > 0 ? Math.round(((income + expenses) / income) * 100) : null;

  return {
    count,
    income,
    expenses,
    net: income + expenses,
    minDate,
    maxDate,
    debtCount,
    reimbursableTotal,
    pendingDebtTotal,
    topCategories,
    topTags,
    activeDaysCount,
    avgDailyExpense,
    highestExpense,
    peakSpendDay,
    savingsRate,
  };
}

/**
 * Builds a clean, editable text summary with rich metrics (totals, dates, debts, categories, tags, insights).
 */
export function buildDefaultSummaryText(
  stats: ExportSummaryStats,
  opts?: SummaryGeneratorOptions
): string {
  const lines: string[] = [];
  const title = opts?.title || 'RESUMEN FINANCIERO';
  lines.push(`=== ${title} ===`);

  if (opts?.includeDateRange !== false) {
    if (stats.minDate && stats.maxDate) {
      const dates = stats.minDate === stats.maxDate ? stats.minDate : `${stats.minDate} al ${stats.maxDate}`;
      lines.push(`Período: ${dates} (${stats.count} registros)`);
    } else {
      lines.push(`Total Registros: ${stats.count}`);
    }
  } else {
    lines.push(`Total Registros: ${stats.count}`);
  }

  if (opts?.includeTotals !== false) {
    lines.push(`Ingresos: ${money(stats.income)}`);
    lines.push(`Gastos: ${money(stats.expenses)}`);
    lines.push(`Balance Neto: ${money(stats.net)}`);
  }

  if (opts?.includeDebts && stats.debtCount > 0) {
    let debtLine = `Deudas / Reembolsos: ${stats.debtCount} registros`;
    if (stats.reimbursableTotal > 0) {
      debtLine += ` | Reembolsable: ${money(stats.reimbursableTotal)}`;
    }
    if (stats.pendingDebtTotal > 0) {
      debtLine += ` | Saldo pendiente: ${money(stats.pendingDebtTotal)}`;
    }
    lines.push(debtLine);
  }

  if (opts?.includeCategories && stats.topCategories.length > 0) {
    lines.push('Desglose Categorías:');
    stats.topCategories.slice(0, 5).forEach((c) => {
      lines.push(`  • ${c.category}: ${money(c.total)} (${c.count})`);
    });
  }

  if (opts?.includeTags && stats.topTags.length > 0) {
    lines.push('Top Etiquetas / Tags:');
    stats.topTags.slice(0, 5).forEach((t) => {
      lines.push(`  • #${t.tag}: ${money(t.total)} (${t.count})`);
    });
  }

  if (opts?.includeInsights) {
    const insightLines: string[] = [];
    if (stats.highestExpense) {
      insightLines.push(`  • Mayor gasto individual: ${money(stats.highestExpense.monto)} (${stats.highestExpense.descripcion}${stats.highestExpense.fecha ? ` - ${stats.highestExpense.fecha}` : ''})`);
    }
    if (stats.peakSpendDay && stats.activeDaysCount > 1) {
      insightLines.push(`  • Día con mayor gasto: ${stats.peakSpendDay.fecha} (${money(stats.peakSpendDay.total)} en ${stats.peakSpendDay.count} compras)`);
    }
    if (stats.avgDailyExpense > 0 && stats.activeDaysCount > 1) {
      insightLines.push(`  • Gasto promedio diario: ${money(-stats.avgDailyExpense)} / día (${stats.activeDaysCount} días con actividad)`);
    }
    if (stats.savingsRate !== null) {
      insightLines.push(`  • Tasa de ahorro: ${stats.savingsRate}% de los ingresos`);
    }

    if (insightLines.length > 0) {
      lines.push('Récords y Ritmo de Gasto:');
      lines.push(...insightLines);
    }
  }

  return lines.join('\n');
}

/**
 * Escapes a cell for CSV.
 */
function escapeCsvCell(val: string | number, delimiter: string): string {
  const str = String(val ?? '');
  if (
    str.includes(delimiter) ||
    str.includes('"') ||
    str.includes('\n') ||
    str.includes('\r')
  ) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Escapes a cell for Markdown tables.
 */
function escapeMarkdownCell(val: string | number): string {
  const str = String(val ?? '');
  return str.replace(/\|/g, '\\|').replace(/\r?\n/g, ' ');
}

/**
 * Escapes text for HTML content.
 */
function escapeHtml(str: string): string {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Generates the export output string and optional HTML representation.
 */
export function generateExportData(
  transactions: Transaction[],
  options: ExportOptions,
  context: ExportContext
): { text: string; html?: string; mimeType: string; filename: string } {
  const list = prepareTransactionsForExport(transactions, options.flattenSplits);

  // Preserve user-specified column ordering from selectedColumnIds
  const colMap = new Map(EXPORT_COLUMNS.map((c) => [c.id, c]));
  const activeCols: ExportColumn[] = [];
  options.selectedColumnIds.forEach((id) => {
    const col = colMap.get(id);
    if (col && !activeCols.some((c) => c.id === col.id)) {
      activeCols.push(col);
    }
  });

  const summary = calculateExportSummary(list, context);
  const today = new Date().toISOString().substring(0, 10);
  const isOnlySummary = options.summaryPosition === 'only';
  const isTopSummary = options.summaryPosition === 'top';

  // Helper to get formatted or raw cell value
  const getCellValue = (t: Transaction, col: ExportColumn): string | number => {
    if (col.id === 'monto' && options.numberFormat === 'formatted') {
      return money(t.MONTO ?? 0);
    }
    return col.getValue(t, context);
  };

  switch (options.format) {
    case 'excel': {
      // 1. TSV text for plain clipboard
      const lines: string[] = [];

      if (isOnlySummary) {
        const summaryText = options.customSummaryText || buildDefaultSummaryText(summary);
        const text = summaryText.replace(/\n/g, '\r\n');
        const html = `<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; padding: 16px; border: 1px solid #cbd5e1; background: #f8fafc; border-radius: 8px;">
          <h3 style="margin: 0 0 10px 0; color: #0f172a; font-size: 15px; font-weight: bold;">Resumen</h3>
          <pre style="font-family: inherit; margin: 0; white-space: pre-wrap; color: #334155; line-height: 1.6;">${escapeHtml(summaryText)}</pre>
        </div>`;
        return {
          text,
          html,
          mimeType: 'text/tab-separated-values',
          filename: `resumen_${today}.tsv`,
        };
      }

      // Summary lines preparation for TSV
      let summaryTsvLines: string[] = [];
      if (options.includeSummary) {
        if (options.customSummaryText) {
          summaryTsvLines = options.customSummaryText.split('\n');
        } else {
          summaryTsvLines = [
            `Resumen\tTotal Registros: ${summary.count}\tIngresos: ${money(summary.income)}\tGastos: ${money(summary.expenses)}\tNeto: ${money(summary.net)}`,
          ];
        }
      }

      if (options.includeSummary && isTopSummary) {
        lines.push(...summaryTsvLines);
        lines.push('');
      }

      if (options.includeHeaders) {
        lines.push(activeCols.map((c) => c.label).join('\t'));
      }
      list.forEach((t) => {
        lines.push(
          activeCols
            .map((c) => {
              const val = getCellValue(t, c);
              return String(val ?? '').replace(/[\t\r\n]/g, ' ');
            })
            .join('\t')
        );
      });

      if (options.includeSummary && !isTopSummary) {
        lines.push('');
        lines.push(...summaryTsvLines);
      }
      const text = lines.join('\r\n');

      // 2. Rich HTML Table for Excel / Sheets clipboard
      const colHeadersHtml = activeCols
        .map(
          (c) =>
            `<th style="background-color: #1e293b; color: #ffffff; font-weight: bold; padding: 8px 12px; border: 1px solid #cbd5e1; text-align: ${c.align || 'left'};">${c.label}</th>`
        )
        .join('');

      const rowsHtml = list
        .map((t, idx) => {
          const bg = idx % 2 === 0 ? '#ffffff' : '#f8fafc';
          const cells = activeCols
            .map((c) => {
              const val = getCellValue(t, c);
              const align = c.align || 'left';
              const isMonto = c.id === 'monto' || c.id === 'monto_formateado';
              const color = isMonto
                ? Number(t.MONTO) >= 0
                  ? '#059669'
                  : '#e11d48'
                : '#0f172a';
              return `<td style="padding: 6px 12px; border: 1px solid #e2e8f0; text-align: ${align}; color: ${color};">${val}</td>`;
            })
            .join('');
          return `<tr style="background-color: ${bg};">${cells}</tr>`;
        })
        .join('');

      let summaryHtml = '';
      if (options.includeSummary) {
        if (options.customSummaryText) {
          summaryHtml = `<tr style="background-color: #f1f5f9;">
            <td colspan="${activeCols.length}" style="padding: 10px 14px; border: 1px solid #cbd5e1; white-space: pre-wrap; font-family: monospace; color: #1e293b; font-size: 12px;">${escapeHtml(options.customSummaryText)}</td>
          </tr>`;
        } else {
          summaryHtml = `<tr style="background-color: #e2e8f0; font-weight: bold;">
            <td colspan="${activeCols.length}" style="padding: 8px 12px; border: 1px solid #cbd5e1;">
              Total Registros: ${summary.count} &nbsp;|&nbsp; 
              Ingresos: <span style="color:#059669">${money(summary.income)}</span> &nbsp;|&nbsp; 
              Gastos: <span style="color:#e11d48">${money(summary.expenses)}</span> &nbsp;|&nbsp; 
              Neto: <span style="color:${summary.net >= 0 ? '#059669' : '#e11d48'}">${money(summary.net)}</span>
            </td>
          </tr>`;
        }
      }

      const tbodyContent = isTopSummary
        ? `${summaryHtml}${rowsHtml}`
        : `${rowsHtml}${summaryHtml}`;

      const html = `<table style="border-collapse: collapse; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px;">
        <thead><tr>${colHeadersHtml}</tr></thead>
        <tbody>${tbodyContent}</tbody>
      </table>`;

      return {
        text,
        html,
        mimeType: 'text/tab-separated-values',
        filename: `transacciones_${today}.tsv`,
      };
    }

    case 'csv_comma':
    case 'csv_semicolon': {
      const delimiter = options.format === 'csv_semicolon' ? ';' : ',';
      const lines: string[] = [];

      if (isOnlySummary) {
        const summaryText = options.customSummaryText || buildDefaultSummaryText(summary);
        const text = '\uFEFF' + summaryText.replace(/\n/g, '\r\n');
        return {
          text,
          mimeType: 'text/csv;charset=utf-8;',
          filename: `resumen_${today}.csv`,
        };
      }

      const summaryCsvLines: string[] = [];
      if (options.includeSummary) {
        if (options.customSummaryText) {
          options.customSummaryText.split('\n').forEach((line) => {
            summaryCsvLines.push(`# ${line}`);
          });
        } else {
          summaryCsvLines.push(
            [
              '# RESUMEN',
              `Registros: ${summary.count}`,
              `Ingresos: ${summary.income}`,
              `Gastos: ${summary.expenses}`,
              `Neto: ${summary.net}`,
            ]
              .map((c) => escapeCsvCell(c, delimiter))
              .join(delimiter)
          );
        }
      }

      if (options.includeSummary && isTopSummary) {
        lines.push(...summaryCsvLines);
        lines.push('');
      }

      if (options.includeHeaders) {
        lines.push(activeCols.map((c) => escapeCsvCell(c.label, delimiter)).join(delimiter));
      }
      list.forEach((t) => {
        lines.push(
          activeCols
            .map((c) => escapeCsvCell(getCellValue(t, c), delimiter))
            .join(delimiter)
        );
      });

      if (options.includeSummary && !isTopSummary) {
        lines.push('');
        lines.push(...summaryCsvLines);
      }

      // Add BOM \uFEFF so Excel opens CSVs in Spanish locale with correct UTF-8 accents
      const text = '\uFEFF' + lines.join('\r\n');
      return {
        text,
        mimeType: 'text/csv;charset=utf-8;',
        filename: `transacciones_${today}.csv`,
      };
    }

    case 'markdown': {
      if (isOnlySummary) {
        const summaryText = options.customSummaryText || buildDefaultSummaryText(summary);
        const mdText = summaryText
          .split('\n')
          .map((l) => (l.startsWith('===') ? `### ${l.replace(/===/g, '').trim()}\n` : `> ${l}`))
          .join('\n');
        return {
          text: mdText,
          mimeType: 'text/markdown',
          filename: `resumen_${today}.md`,
        };
      }

      const lines: string[] = [];

      let summaryBlock = '';
      if (options.includeSummary) {
        if (options.customSummaryText) {
          summaryBlock = options.customSummaryText
            .split('\n')
            .map((l) => `> ${l}`)
            .join('\n');
        } else {
          summaryBlock = `> **Resumen**: ${summary.count} transacciones | **Ingresos**: ${money(summary.income)} | **Gastos**: ${money(summary.expenses)} | **Neto**: ${money(summary.net)}`;
        }
      }

      if (options.includeSummary && isTopSummary) {
        lines.push(summaryBlock);
        lines.push('');
      }

      if (options.includeHeaders) {
        lines.push(`| ${activeCols.map((c) => escapeMarkdownCell(c.label)).join(' | ')} |`);
        lines.push(
          `| ${activeCols
            .map((c) => {
              if (c.align === 'right') return '---:';
              if (c.align === 'center') return ':---:';
              return ':---';
            })
            .join(' | ')} |`
        );
      }
      list.forEach((t) => {
        lines.push(
          `| ${activeCols
            .map((c) => escapeMarkdownCell(getCellValue(t, c)))
            .join(' | ')} |`
        );
      });

      if (options.includeSummary && !isTopSummary) {
        lines.push('');
        lines.push(summaryBlock);
      }

      return {
        text: lines.join('\n'),
        mimeType: 'text/markdown',
        filename: `transacciones_${today}.md`,
      };
    }

    case 'text_list': {
      if (isOnlySummary) {
        const summaryText = options.customSummaryText || buildDefaultSummaryText(summary);
        return {
          text: summaryText,
          mimeType: 'text/plain',
          filename: `resumen_${today}.txt`,
        };
      }

      const lines: string[] = [];

      const formatTextSummary = () => {
        if (options.customSummaryText) {
          lines.push(options.customSummaryText);
          lines.push('----------------------------------------');
          lines.push('');
        } else {
          lines.push(`=== RESUMEN (${today}) ===`);
          lines.push(`Total Transacciones: ${summary.count}`);
          lines.push(`Ingresos: ${money(summary.income)}`);
          lines.push(`Gastos: ${money(summary.expenses)}`);
          lines.push(`Balance Neto: ${money(summary.net)}`);
          lines.push('----------------------------------------');
          lines.push('');
        }
      };

      if (options.includeSummary && isTopSummary) {
        formatTextSummary();
      }

      list.forEach((t) => {
        const fecha = t.FECHA ? t.FECHA.substring(0, 10) : '';
        const concepto = t.nombre_limpio || t.DESCRIPCION || 'Sin concepto';
        const montoStr = money(t.MONTO ?? 0);
        const cat = t.categoria ? ` [${t.categoria}]` : '';
        const tags = t.tags ? ` (${t.tags})` : '';
        const deudorStr = t.deudor ? ` {Deudor: ${t.deudor}}` : '';
        const nota = t.nota ? ` // ${t.nota}` : '';
        lines.push(`• ${fecha} | ${concepto}: ${montoStr}${cat}${tags}${deudorStr}${nota}`);
      });

      if (options.includeSummary && !isTopSummary) {
        lines.push('');
        formatTextSummary();
      }

      return {
        text: lines.join('\n'),
        mimeType: 'text/plain',
        filename: `transacciones_${today}.txt`,
      };
    }

    case 'json': {
      if (isOnlySummary) {
        const payload = {
          resumen: summary,
          texto_resumen: options.customSummaryText || buildDefaultSummaryText(summary),
        };
        return {
          text: JSON.stringify(payload, null, 2),
          mimeType: 'application/json',
          filename: `resumen_${today}.json`,
        };
      }

      const exportObjects = list.map((t) => {
        const obj: Record<string, string | number> = {};
        activeCols.forEach((c) => {
          obj[c.id] = getCellValue(t, c);
        });
        return obj;
      });

      const payload = options.includeSummary
        ? {
            resumen: summary,
            ...(options.customSummaryText ? { texto_resumen: options.customSummaryText } : {}),
            transacciones: exportObjects,
          }
        : exportObjects;

      return {
        text: JSON.stringify(payload, null, 2),
        mimeType: 'application/json',
        filename: `transacciones_${today}.json`,
      };
    }
  }
}

/**
 * Copies plain text or rich HTML table to clipboard with full fallbacks.
 */
export async function copyToClipboard(text: string, html?: string): Promise<boolean> {
  // 1. Try modern navigator.clipboard with HTML + Plain text
  if (html && window.ClipboardItem && navigator.clipboard?.write) {
    try {
      const textBlob = new Blob([text], { type: 'text/plain' });
      const htmlBlob = new Blob([html], { type: 'text/html' });
      await navigator.clipboard.write([
        new ClipboardItem({
          'text/plain': textBlob,
          'text/html': htmlBlob,
        }),
      ]);
      return true;
    } catch (err) {
      console.warn('Failed writing rich clipboard item, falling back to writeText', err);
    }
  }

  // 2. Try writeText
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      console.warn('Failed writeText, falling back to execCommand', err);
    }
  }

  // 3. Fallback textarea execCommand
  try {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-9999px';
    textArea.style.top = '-9999px';
    textArea.setAttribute('readonly', '');
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    const successful = document.execCommand('copy');
    document.body.removeChild(textArea);
    return successful;
  } catch (err) {
    console.error('execCommand copy failed', err);
    return false;
  }
}

/**
 * Triggers a file download in the browser.
 */
export function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
