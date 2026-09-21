import { useState, useMemo, useEffect } from 'react';
import {
  X,
  Check,
  Copy,
  Download,
  FileSpreadsheet,
  FileText,
  Table,
  List,
  Code,
  Settings2,
  Eye,
  ArrowRight,
  type LucideIcon,
} from 'lucide-react';
import { Transaction, FundListItem } from '../services/api';
import { DebtLookup } from '../utils/debtFilters';
import {
  EXPORT_COLUMNS,
  ExportFormat,
  ExportOptions,
  generateExportData,
  copyToClipboard,
  downloadFile,
  calculateExportSummary,
  prepareTransactionsForExport,
} from '../utils/exportUtils';
import { money } from '../utils/format';

export interface ExplorerExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  filteredTransactions: Transaction[];
  displayedTransactions: Transaction[];
  selectedTransactions: Transaction[];
  funds?: FundListItem[];
  debtLookup?: DebtLookup;
}

interface FormatMeta {
  id: ExportFormat;
  title: string;
  badge: string;
  description: string;
  icon: LucideIcon;
  color: string;
  bgLight: string;
  borderColor: string;
  ext: string;
}

const FORMATS: FormatMeta[] = [
  {
    id: 'excel',
    title: 'Excel / Sheets (Tabla directa)',
    badge: 'Recomendado',
    description: 'Copia con formato de celdas TSV/HTML. Pégala con Ctrl+V en Excel o Google Sheets.',
    icon: FileSpreadsheet,
    color: 'text-emerald-400',
    bgLight: 'bg-emerald-500/10 hover:bg-emerald-500/20',
    borderColor: 'border-emerald-500/40',
    ext: '.tsv',
  },
  {
    id: 'csv_comma',
    title: 'CSV (Comas)',
    badge: 'Universal',
    description: 'Valores separados por comas estándar (RFC 4180) para scripts, pandas o bases de datos.',
    icon: FileText,
    color: 'text-sky-400',
    bgLight: 'bg-sky-500/10 hover:bg-sky-500/20',
    borderColor: 'border-sky-500/40',
    ext: '.csv',
  },
  {
    id: 'csv_semicolon',
    title: 'CSV (Punto y coma ;)',
    badge: 'Excel Español',
    description: 'Separado por punto y coma con BOM UTF-8, ideal para Excel en español y números con coma.',
    icon: FileText,
    color: 'text-indigo-400',
    bgLight: 'bg-indigo-500/10 hover:bg-indigo-500/20',
    borderColor: 'border-indigo-500/40',
    ext: '.csv',
  },
  {
    id: 'markdown',
    title: 'Tabla Markdown',
    badge: 'Obsidian / Notion',
    description: 'Tabla formateada con | columnas |, perfecta para Obsidian, Notion o GitHub.',
    icon: Table,
    color: 'text-purple-400',
    bgLight: 'bg-purple-500/10 hover:bg-purple-500/20',
    borderColor: 'border-purple-500/40',
    ext: '.md',
  },
  {
    id: 'text_list',
    title: 'Lista de Texto Resumida',
    badge: 'Notas / Chat',
    description: 'Viñetas legibles con fecha, concepto, monto y balance para compartir en notas o chat.',
    icon: List,
    color: 'text-amber-400',
    bgLight: 'bg-amber-500/10 hover:bg-amber-500/20',
    borderColor: 'border-amber-500/40',
    ext: '.txt',
  },
  {
    id: 'json',
    title: 'JSON Estructurado',
    badge: 'Desarrollo / IA',
    description: 'Estructura limpia en JSON con claves y valores formateados.',
    icon: Code,
    color: 'text-surface-300',
    bgLight: 'bg-surface-800 hover:bg-surface-700',
    borderColor: 'border-white/20',
    ext: '.json',
  },
];

export function ExplorerExportModal({
  isOpen,
  onClose,
  filteredTransactions,
  displayedTransactions,
  selectedTransactions,
  funds,
  debtLookup,
}: ExplorerExportModalProps) {
  // Scope: 'filtered' (all filtered results), 'displayed' (only currently shown on page), 'selected' (checked rows)
  const defaultScope = selectedTransactions.length > 0 ? 'selected' : 'filtered';
  const [scope, setScope] = useState<'filtered' | 'displayed' | 'selected'>(defaultScope);
  const [format, setFormat] = useState<ExportFormat>('excel');
  const [flattenSplits, setFlattenSplits] = useState(true);
  const [includeHeaders, setIncludeHeaders] = useState(true);
  const [includeSummary, setIncludeSummary] = useState(true);
  const [numberFormat, setNumberFormat] = useState<'raw' | 'formatted'>('raw');

  const [selectedColumnIds, setSelectedColumnIds] = useState<string[]>(() =>
    EXPORT_COLUMNS.filter((c) => c.default).map((c) => c.id)
  );

  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false);
  const [showPreview, setShowPreview] = useState(true);
  const [copiedState, setCopiedState] = useState(false);
  const [copyFeedbackMessage, setCopyFeedbackMessage] = useState('');

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Adjust default scope when selected changes
  useEffect(() => {
    if (selectedTransactions.length > 0) {
      setScope('selected');
    } else if (scope === 'selected') {
      setScope('filtered');
    }
  }, [selectedTransactions.length]);

  // Target transactions based on selected scope
  const targetTransactions = useMemo(() => {
    if (scope === 'selected' && selectedTransactions.length > 0) {
      return selectedTransactions;
    }
    if (scope === 'displayed') {
      return displayedTransactions;
    }
    return filteredTransactions;
  }, [scope, selectedTransactions, displayedTransactions, filteredTransactions]);

  const exportOptions = useMemo<ExportOptions>(() => {
    return {
      format,
      selectedColumnIds,
      flattenSplits,
      includeHeaders,
      includeSummary,
      numberFormat: format === 'text_list' ? 'formatted' : numberFormat,
    };
  }, [format, selectedColumnIds, flattenSplits, includeHeaders, includeSummary, numberFormat]);

  const exportContext = useMemo(() => ({ funds, debtLookup }), [funds, debtLookup]);

  // Generate data output
  const generatedData = useMemo(() => {
    if (!isOpen) return { text: '', mimeType: 'text/plain', filename: 'transacciones.txt' };
    return generateExportData(targetTransactions, exportOptions, exportContext);
  }, [isOpen, targetTransactions, exportOptions, exportContext]);

  // Summary statistics of the exported set
  const summaryStats = useMemo(() => {
    const prepared = prepareTransactionsForExport(targetTransactions, flattenSplits);
    return calculateExportSummary(prepared);
  }, [targetTransactions, flattenSplits]);

  // Toggle single column
  const handleToggleColumn = (id: string) => {
    setSelectedColumnIds((prev) => {
      if (prev.includes(id)) {
        if (prev.length <= 1) return prev; // Keep at least one column
        return prev.filter((colId) => colId !== id);
      }
      return [...prev, id];
    });
  };

  const handleSelectAllColumns = () => {
    setSelectedColumnIds(EXPORT_COLUMNS.map((c) => c.id));
  };

  const handleSelectBasicColumns = () => {
    setSelectedColumnIds(EXPORT_COLUMNS.filter((c) => c.default).map((c) => c.id));
  };

  // Copy Action
  const handleCopy = async (overrideFormat?: ExportFormat) => {
    const opts = overrideFormat ? { ...exportOptions, format: overrideFormat } : exportOptions;
    const data = generateExportData(targetTransactions, opts, exportContext);
    const success = await copyToClipboard(data.text, data.html);

    if (success) {
      setCopiedState(true);
      const targetLabel = FORMATS.find((f) => f.id === (overrideFormat || format))?.title || 'Datos';
      setCopyFeedbackMessage(`¡${targetLabel} copiado al portapapeles!`);
      setTimeout(() => {
        setCopiedState(false);
        setCopyFeedbackMessage('');
      }, 2500);
    } else {
      alert('No se pudo copiar automáticamente. Puedes seleccionar el texto de la vista previa y copiarlo manualmente.');
    }
  };

  // Download Action
  const handleDownload = () => {
    downloadFile(generatedData.text, generatedData.filename, generatedData.mimeType);
  };

  if (!isOpen) return null;

  // Selected format metadata
  const currentFormatMeta = FORMATS.find((f) => f.id === format) || FORMATS[0];

  // Preview truncated preview text
  const previewLines = generatedData.text.split('\n');
  const maxPreviewLines = 18;
  const isPreviewTruncated = previewLines.length > maxPreviewLines;
  const displayPreviewText = isPreviewTruncated
    ? previewLines.slice(0, maxPreviewLines).join('\n') + `\n\n... y ${previewLines.length - maxPreviewLines} filas más.`
    : generatedData.text;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 md:p-6 bg-black/75 backdrop-blur-md animate-in fade-in duration-200">
      <div
        className="bg-surface-900/95 border border-white/10 rounded-3xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden backdrop-blur-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 md:px-7 border-b border-white/10 flex justify-between items-center bg-surface-950/70">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 border border-emerald-500/30 text-emerald-300">
              <FileSpreadsheet size={24} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg md:text-xl font-bold text-white tracking-tight">
                  Exportar / Copiar Datos
                </h2>
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-primary-500/15 text-primary-300 border border-primary-500/30">
                  {summaryStats.count} filas
                </span>
              </div>
              <p className="text-xs text-surface-400 mt-0.5">
                Copia las transacciones filtradas a tu portapapeles para pegarlas en Excel, Sheets, Notion o notas.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="text-surface-400 hover:text-white p-2 rounded-xl hover:bg-white/10 transition-colors"
            title="Cerrar (Esc)"
          >
            <X size={20} />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-5 md:p-7 space-y-6 custom-scrollbar">

          {/* 1. Scope Selector (Which records?) */}
          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-wider text-surface-400 flex items-center gap-2">
              <span>1. Qué transacciones exportar</span>
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <button
                type="button"
                onClick={() => setScope('filtered')}
                className={`flex items-center justify-between p-3 rounded-2xl border text-left transition-all ${
                  scope === 'filtered'
                    ? 'bg-primary-500/15 border-primary-500/50 text-white ring-1 ring-primary-500/30'
                    : 'bg-surface-950/50 border-white/5 text-surface-400 hover:text-surface-200 hover:border-white/10'
                }`}
              >
                <div>
                  <div className="text-xs font-bold">Todas las filtradas</div>
                  <div className="text-[11px] text-surface-400">Coinciden con los filtros</div>
                </div>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-lg bg-surface-900 border border-white/10 text-primary-300">
                  {filteredTransactions.length}
                </span>
              </button>

              <button
                type="button"
                onClick={() => setScope('displayed')}
                className={`flex items-center justify-between p-3 rounded-2xl border text-left transition-all ${
                  scope === 'displayed'
                    ? 'bg-primary-500/15 border-primary-500/50 text-white ring-1 ring-primary-500/30'
                    : 'bg-surface-950/50 border-white/5 text-surface-400 hover:text-surface-200 hover:border-white/10'
                }`}
              >
                <div>
                  <div className="text-xs font-bold">Visibles en tabla</div>
                  <div className="text-[11px] text-surface-400">Límite de pantalla</div>
                </div>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-lg bg-surface-900 border border-white/10 text-primary-300">
                  {displayedTransactions.length}
                </span>
              </button>

              <button
                type="button"
                onClick={() => {
                  if (selectedTransactions.length > 0) setScope('selected');
                }}
                disabled={selectedTransactions.length === 0}
                className={`flex items-center justify-between p-3 rounded-2xl border text-left transition-all ${
                  selectedTransactions.length === 0
                    ? 'opacity-40 cursor-not-allowed bg-surface-950/30 border-white/5 text-surface-500'
                    : scope === 'selected'
                    ? 'bg-primary-500/15 border-primary-500/50 text-white ring-1 ring-primary-500/30'
                    : 'bg-surface-950/50 border-white/5 text-surface-400 hover:text-surface-200 hover:border-white/10'
                }`}
              >
                <div>
                  <div className="text-xs font-bold">Seleccionadas ({selectedTransactions.length})</div>
                  <div className="text-[11px] text-surface-400">Marcadas con casilla</div>
                </div>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-lg bg-surface-900 border border-white/10 text-primary-300">
                  {selectedTransactions.length}
                </span>
              </button>
            </div>
          </div>

          {/* 2. Format Selection */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-surface-400 flex items-center gap-2">
                <span>2. Formato de exportación</span>
              </label>
              <span className="text-[11px] text-surface-400">
                Selecciona cómo quieres que se peguen los datos
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {FORMATS.map((fmt) => {
                const isSelected = format === fmt.id;
                const IconComponent = fmt.icon;
                return (
                  <div
                    key={fmt.id}
                    onClick={() => setFormat(fmt.id)}
                    className={`relative p-3.5 rounded-2xl border cursor-pointer transition-all duration-200 flex flex-col justify-between ${
                      isSelected
                        ? `bg-surface-800/90 ${fmt.borderColor} ring-1 ${fmt.borderColor} shadow-lg shadow-black/40`
                        : 'bg-surface-950/40 border-white/5 hover:border-white/15 hover:bg-surface-950/70'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <div className={`p-1.5 rounded-xl bg-white/5 ${fmt.color}`}>
                            <IconComponent size={16} />
                          </div>
                          <span className="text-xs font-bold text-white tracking-wide">{fmt.title}</span>
                        </div>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                          isSelected ? 'bg-white/10 text-white border-white/20' : 'bg-surface-900 text-surface-400 border-white/5'
                        }`}>
                          {fmt.badge}
                        </span>
                      </div>
                      <p className="text-[11px] text-surface-400 leading-relaxed">
                        {fmt.description}
                      </p>
                    </div>

                    {/* Quick instant copy button for this specific format */}
                    <div className="mt-3 pt-2 border-t border-white/5 flex items-center justify-between">
                      <span className="text-[10px] font-mono text-surface-500">{fmt.ext}</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setFormat(fmt.id);
                          handleCopy(fmt.id);
                        }}
                        className={`text-[11px] font-bold px-2.5 py-1 rounded-lg transition-all flex items-center gap-1 ${
                          isSelected
                            ? 'bg-primary-500/20 hover:bg-primary-500/30 text-primary-300 border border-primary-500/30'
                            : 'text-surface-400 hover:text-white hover:bg-white/5'
                        }`}
                        title={`Copiar directamente en formato ${fmt.title}`}
                      >
                        <Copy size={12} /> Copiar ya
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 3. Fast Config & Toggles */}
          <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-4 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-surface-300 flex items-center gap-2">
                <Settings2 size={14} className="text-primary-400" /> Opciones de Formato y Estructura
              </span>

              <button
                type="button"
                onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
                className="text-xs text-primary-400 hover:text-primary-300 font-semibold flex items-center gap-1 transition-colors"
              >
                <span>{showAdvancedOptions ? 'Ocultar columnas' : 'Personalizar columnas'}</span>
                <ArrowRight size={12} className={`transform transition-transform ${showAdvancedOptions ? 'rotate-90' : ''}`} />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              {/* Splits Toggle */}
              <label className="flex items-center gap-2.5 p-2.5 rounded-xl bg-surface-900/60 border border-white/5 cursor-pointer hover:bg-surface-900 transition-colors">
                <input
                  type="checkbox"
                  checked={flattenSplits}
                  onChange={(e) => setFlattenSplits(e.target.checked)}
                  className="rounded border-surface-600 text-primary-600 focus:ring-primary-500 bg-surface-800"
                />
                <div>
                  <div className="font-semibold text-white">Desglosar Splits</div>
                  <div className="text-[10px] text-surface-400">Exporta subtransacciones</div>
                </div>
              </label>

              {/* Include Headers */}
              <label className="flex items-center gap-2.5 p-2.5 rounded-xl bg-surface-900/60 border border-white/5 cursor-pointer hover:bg-surface-900 transition-colors">
                <input
                  type="checkbox"
                  checked={includeHeaders}
                  onChange={(e) => setIncludeHeaders(e.target.checked)}
                  className="rounded border-surface-600 text-primary-600 focus:ring-primary-500 bg-surface-800"
                />
                <div>
                  <div className="font-semibold text-white">Encabezados</div>
                  <div className="text-[10px] text-surface-400">Nombres de columna</div>
                </div>
              </label>

              {/* Include Summary Block */}
              <label className="flex items-center gap-2.5 p-2.5 rounded-xl bg-surface-900/60 border border-white/5 cursor-pointer hover:bg-surface-900 transition-colors">
                <input
                  type="checkbox"
                  checked={includeSummary}
                  onChange={(e) => setIncludeSummary(e.target.checked)}
                  className="rounded border-surface-600 text-primary-600 focus:ring-primary-500 bg-surface-800"
                />
                <div>
                  <div className="font-semibold text-white">Bloque Resumen</div>
                  <div className="text-[10px] text-surface-400">Totales e ingresos/gastos</div>
                </div>
              </label>

              {/* Number Format */}
              <div className="p-2.5 rounded-xl bg-surface-900/60 border border-white/5 flex flex-col justify-between">
                <div className="font-semibold text-white mb-1">Formato de Montos</div>
                <div className="flex items-center gap-1 bg-surface-950 p-0.5 rounded-lg border border-white/5">
                  <button
                    type="button"
                    onClick={() => setNumberFormat('raw')}
                    className={`flex-1 py-1 text-[11px] font-semibold rounded transition-all ${
                      numberFormat === 'raw'
                        ? 'bg-primary-500/20 text-primary-300 font-bold'
                        : 'text-surface-400 hover:text-white'
                    }`}
                    title="Números limpios para fórmulas de Excel (ej: -15000)"
                  >
                    123 (Excel)
                  </button>
                  <button
                    type="button"
                    onClick={() => setNumberFormat('formatted')}
                    className={`flex-1 py-1 text-[11px] font-semibold rounded transition-all ${
                      numberFormat === 'formatted'
                        ? 'bg-primary-500/20 text-primary-300 font-bold'
                        : 'text-surface-400 hover:text-white'
                    }`}
                    title="Formato legible (ej: -$ 15.000)"
                  >
                    $ 123 (Texto)
                  </button>
                </div>
              </div>
            </div>

            {/* Column Customization Drawer */}
            {showAdvancedOptions && (
              <div className="pt-3 border-t border-white/5 space-y-2.5 animate-in fade-in duration-200">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-surface-400 uppercase tracking-wider">
                    Columnas a incluir ({selectedColumnIds.length} de {EXPORT_COLUMNS.length})
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleSelectBasicColumns}
                      className="text-[11px] text-primary-400 hover:text-primary-300 font-semibold"
                    >
                      Básicas
                    </button>
                    <span className="text-surface-600">•</span>
                    <button
                      type="button"
                      onClick={handleSelectAllColumns}
                      className="text-[11px] text-primary-400 hover:text-primary-300 font-semibold"
                    >
                      Todas
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                  {EXPORT_COLUMNS.map((col) => {
                    const isChecked = selectedColumnIds.includes(col.id);
                    return (
                      <button
                        key={col.id}
                        type="button"
                        onClick={() => handleToggleColumn(col.id)}
                        className={`text-left text-xs px-2.5 py-1.5 rounded-xl border flex items-center gap-2 transition-colors ${
                          isChecked
                            ? 'bg-primary-500/10 border-primary-500/30 text-white font-medium'
                            : 'bg-surface-950/40 border-white/5 text-surface-400 hover:text-surface-200 hover:border-white/10'
                        }`}
                      >
                        <span className={`w-3.5 h-3.5 rounded border flex-shrink-0 flex items-center justify-center ${
                          isChecked ? 'bg-primary-500 border-primary-500' : 'border-surface-600'
                        }`}>
                          {isChecked && <Check size={10} className="text-surface-950" />}
                        </span>
                        <span className="truncate">{col.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* 4. Live Preview */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => setShowPreview(!showPreview)}
                className="text-xs font-bold uppercase tracking-wider text-surface-400 flex items-center gap-1.5 hover:text-white transition-colors"
              >
                <Eye size={14} className="text-primary-400" />
                <span>Vista previa de salida ({currentFormatMeta.title})</span>
                <span className="text-[10px] text-surface-500 font-normal">
                  ({generatedData.filename})
                </span>
              </button>

              <span className="text-[11px] text-surface-500">
                {previewLines.length} líneas generadas
              </span>
            </div>

            {showPreview && (
              <div className="relative rounded-2xl border border-white/10 bg-surface-950 p-4 font-mono text-xs text-surface-300 overflow-x-auto max-h-56 custom-scrollbar shadow-inner">
                <pre className="whitespace-pre">{displayPreviewText}</pre>
              </div>
            )}
          </div>

          {/* Quick Summary Pill Bar */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-surface-950/40 border border-white/5 text-xs text-surface-400 flex-wrap gap-2">
            <span>
              Resumen:{' '}
              <strong className="text-white">{summaryStats.count}</strong> transacciones
            </span>
            <span>
              Ingresos: <strong className="text-emerald-400">{money(summaryStats.income)}</strong>
            </span>
            <span>
              Gastos: <strong className="text-rose-400">{money(summaryStats.expenses)}</strong>
            </span>
            <span>
              Neto:{' '}
              <strong className={summaryStats.net >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                {money(summaryStats.net)}
              </strong>
            </span>
          </div>

        </div>

        {/* Footer with Primary Actions */}
        <div className="p-4 md:px-7 border-t border-white/10 bg-surface-950/80 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button
              type="button"
              onClick={onClose}
              className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-white/10 text-surface-300 hover:text-white hover:bg-white/5 text-xs font-bold transition-all"
            >
              Cerrar
            </button>
            <button
              type="button"
              onClick={handleDownload}
              className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-white/10 text-surface-200 hover:text-white hover:bg-white/10 text-xs font-bold transition-all flex items-center justify-center gap-2"
              title={`Descargar archivo ${generatedData.filename}`}
            >
              <Download size={15} /> Descargar archivo
            </button>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            {copyFeedbackMessage && (
              <span className="text-xs text-emerald-400 font-semibold animate-in fade-in slide-in-from-bottom-1">
                {copyFeedbackMessage}
              </span>
            )}
            <button
              type="button"
              onClick={() => handleCopy()}
              className={`w-full sm:w-auto px-6 py-2.5 rounded-xl text-xs font-bold transition-all duration-200 flex items-center justify-center gap-2 shadow-xl ${
                copiedState
                  ? 'bg-emerald-500 text-white shadow-emerald-900/30 scale-105'
                  : 'bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-700 hover:from-emerald-500 hover:to-teal-500 text-white shadow-emerald-950/40 hover:scale-[1.02] active:scale-[0.98]'
              }`}
            >
              {copiedState ? (
                <>
                  <Check size={16} className="animate-in zoom-in" />
                  <span>¡Copiado a la papelera / portapapeles!</span>
                </>
              ) : (
                <>
                  <Copy size={16} />
                  <span>Copiar al Portapapeles ({summaryStats.count})</span>
                </>
              )}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
