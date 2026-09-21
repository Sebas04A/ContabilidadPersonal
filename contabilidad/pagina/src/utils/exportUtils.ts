import { Transaction, FundListItem } from '../services/api';
import { DebtLookup, debtPerson } from './debtFilters';
import { matchFund } from './matchFund';
import { money } from './format';

export type ExportFormat =
  | 'excel'
  | 'csv_comma'
  | 'csv_semicolon'
  | 'markdown'
  | 'text_list'
  | 'json';

export interface ExportColumn {
  id: string;
  label: string;
  default: boolean;
  align?: 'left' | 'right' | 'center';
  getValue: (t: Transaction, extra: ExportContext) => string | number;
}

export interface ExportContext {
  funds?: FundListItem[];
  debtLookup?: DebtLookup;
}

export const EXPORT_COLUMNS: ExportColumn[] = [
  {
    id: 'fecha',
    label: 'Fecha',
    default: true,
    align: 'center',
    getValue: (t) => t.FECHA ? t.FECHA.substring(0, 10) : '',
  },
  {
    id: 'hora',
    label: 'Hora',
    default: false,
    align: 'center',
    getValue: (t) => t.HORA || '',
  },
  {
    id: 'tipo',
    label: 'Fuente / Tipo',
    default: true,
    align: 'center',
    getValue: (t) => t.TIPO || 'BANCA',
  },
  {
    id: 'concepto',
    label: 'Concepto',
    default: true,
    align: 'left',
    getValue: (t) => t.DESCRIPCION || '',
  },
  {
    id: 'nombre_limpio',
    label: 'Nombre Limpio / Comercio',
    default: true,
    align: 'left',
    getValue: (t) => t.nombre_limpio || t.DESCRIPCION || '',
  },
  {
    id: 'categoria',
    label: 'Categoría',
    default: true,
    align: 'left',
    getValue: (t) => t.categoria || 'Sin Categoría',
  },
  {
    id: 'tags',
    label: 'Etiquetas',
    default: true,
    align: 'left',
    getValue: (t) => t.tags || '',
  },
  {
    id: 'monto',
    label: 'Monto',
    default: true,
    align: 'right',
    getValue: (t) => t.MONTO ?? 0,
  },
  {
    id: 'monto_formateado',
    label: 'Monto Formateado',
    default: false,
    align: 'right',
    getValue: (t) => money(t.MONTO ?? 0),
  },
  {
    id: 'reembolsable',
    label: 'Reembolsable',
    default: false,
    align: 'center',
    getValue: (t) => (t.es_reembolsable ? 'Sí' : 'No'),
  },
  {
    id: 'deudor',
    label: 'Persona / Deudor',
    default: false,
    align: 'left',
    getValue: (t, ctx) => (ctx.debtLookup ? debtPerson(t, ctx.debtLookup) : t.deudor) || t.deudor || '',
  },
  {
    id: 'es_fijo',
    label: 'Gasto Fijo',
    default: false,
    align: 'center',
    getValue: (t) => (t.es_fijo ? 'Sí' : 'No'),
  },
  {
    id: 'fondo',
    label: 'Fondo',
    default: false,
    align: 'left',
    getValue: (t, ctx) => matchFund(t, ctx.funds)?.name || '',
  },
  {
    id: 'prioridad',
    label: 'Prioridad',
    default: false,
    align: 'center',
    getValue: (t) => t.prioridad || '',
  },
  {
    id: 'nota',
    label: 'Nota',
    default: false,
    align: 'left',
    getValue: (t) => t.nota || '',
  },
  {
    id: 'revisado',
    label: 'Revisado',
    default: false,
    align: 'center',
    getValue: (t) => (t.revisado ? 'Sí' : 'No'),
  },
];

export interface ExportOptions {
  format: ExportFormat;
  selectedColumnIds: string[];
  flattenSplits: boolean;
  includeHeaders: boolean;
  includeSummary: boolean;
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
 * Calculates quick financial totals for summary text or tables.
 */
export function calculateExportSummary(transactions: Transaction[]) {
  let income = 0;
  let expenses = 0;
  let count = transactions.length;

  transactions.forEach((t) => {
    const val = Number(t.MONTO) || 0;
    if (val > 0) income += val;
    else expenses += val;
  });

  return {
    count,
    income,
    expenses,
    net: income + expenses,
  };
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
 * Generates the export output string and optional HTML representation.
 */
export function generateExportData(
  transactions: Transaction[],
  options: ExportOptions,
  context: ExportContext
): { text: string; html?: string; mimeType: string; filename: string } {
  const list = prepareTransactionsForExport(transactions, options.flattenSplits);
  const activeCols = EXPORT_COLUMNS.filter((c) =>
    options.selectedColumnIds.includes(c.id)
  );
  const summary = calculateExportSummary(list);
  const today = new Date().toISOString().substring(0, 10);

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

      if (options.includeSummary) {
        lines.push('');
        lines.push(`Resumen\tTotal Registros: ${summary.count}\tIngresos: ${money(summary.income)}\tGastos: ${money(summary.expenses)}\tNeto: ${money(summary.net)}`);
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

      const summaryHtml = options.includeSummary
        ? `<tr style="background-color: #e2e8f0; font-weight: bold;">
            <td colspan="${activeCols.length}" style="padding: 8px 12px; border: 1px solid #cbd5e1;">
              Total Registros: ${summary.count} &nbsp;|&nbsp; 
              Ingresos: <span style="color:#059669">${money(summary.income)}</span> &nbsp;|&nbsp; 
              Gastos: <span style="color:#e11d48">${money(summary.expenses)}</span> &nbsp;|&nbsp; 
              Neto: <span style="color:${summary.net >= 0 ? '#059669' : '#e11d48'}">${money(summary.net)}</span>
            </td>
          </tr>`
        : '';

      const html = `<table style="border-collapse: collapse; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px;">
        <thead><tr>${colHeadersHtml}</tr></thead>
        <tbody>${rowsHtml}${summaryHtml}</tbody>
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

      if (options.includeSummary) {
        lines.push('');
        lines.push(
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

      // Add BOM \uFEFF so Excel opens CSVs in Spanish locale with correct UTF-8 accents
      const text = '\uFEFF' + lines.join('\r\n');
      return {
        text,
        mimeType: 'text/csv;charset=utf-8;',
        filename: `transacciones_${today}.csv`,
      };
    }

    case 'markdown': {
      const lines: string[] = [];
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

      if (options.includeSummary) {
        lines.push('');
        lines.push(`> **Resumen**: ${summary.count} transacciones | **Ingresos**: ${money(summary.income)} | **Gastos**: ${money(summary.expenses)} | **Neto**: ${money(summary.net)}`);
      }

      return {
        text: lines.join('\n'),
        mimeType: 'text/markdown',
        filename: `transacciones_${today}.md`,
      };
    }

    case 'text_list': {
      const lines: string[] = [];
      if (options.includeSummary) {
        lines.push(`=== RESUMEN (${today}) ===`);
        lines.push(`Total Transacciones: ${summary.count}`);
        lines.push(`Ingresos: ${money(summary.income)}`);
        lines.push(`Gastos: ${money(summary.expenses)}`);
        lines.push(`Balance Neto: ${money(summary.net)}`);
        lines.push('----------------------------------------');
        lines.push('');
      }

      list.forEach((t) => {
        const fecha = t.FECHA ? t.FECHA.substring(0, 10) : '';
        const concepto = t.nombre_limpio || t.DESCRIPCION || 'Sin concepto';
        const montoStr = money(t.MONTO ?? 0);
        const cat = t.categoria ? ` [${t.categoria}]` : '';
        const tags = t.tags ? ` (${t.tags})` : '';
        const nota = t.nota ? ` // ${t.nota}` : '';
        lines.push(`• ${fecha} | ${concepto}: ${montoStr}${cat}${tags}${nota}`);
      });

      return {
        text: lines.join('\n'),
        mimeType: 'text/plain',
        filename: `transacciones_${today}.txt`,
      };
    }

    case 'json': {
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
