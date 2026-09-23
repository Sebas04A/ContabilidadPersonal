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
  Search,
  RotateCcw,
  ArrowLeft,
  ArrowRight,
  Sparkles,
  ChevronDown,
  ChevronUp,
  type LucideIcon,
} from 'lucide-react';
import { Transaction, FundListItem } from '../services/api';
import { DebtLookup } from '../utils/debtFilters';
import {
  EXPORT_COLUMNS,
  COLUMN_PRESETS,
  COLUMN_CATEGORIES,
  ColumnCategory,
  ColumnPreset,
  ExportFormat,
  ExportOptions,
  generateExportData,
  copyToClipboard,
  downloadFile,
  calculateExportSummary,
  prepareTransactionsForExport,
  buildDefaultSummaryText,
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
    title: 'Excel / Sheets (Directo)',
    badge: 'Recomendado',
    description: 'Copia en formato TSV y tabla HTML. Pégala con Ctrl+V directo en Excel o Google Sheets.',
    icon: FileSpreadsheet,
    color: 'text-emerald-400',
    bgLight: 'bg-emerald-500/10 hover:bg-emerald-500/20',
    borderColor: 'border-emerald-500/40',
    ext: '.tsv',
  },
  {
    id: 'csv_comma',
    title: 'CSV (Comas estándar)',
    badge: 'Universal',
    description: 'Valores separados por comas estándar (RFC 4180) para Python, pandas o bases de datos.',
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
    description: 'Tabla formateada con | columnas |, perfecta para Obsidian, Notion o notas Markdown.',
    icon: Table,
    color: 'text-purple-400',
    bgLight: 'bg-purple-500/10 hover:bg-purple-500/20',
    borderColor: 'border-purple-500/40',
    ext: '.md',
  },
  {
    id: 'text_list',
    title: 'Lista de Texto Resumida',
    badge: 'Notas / WhatsApp',
    description: 'Viñetas limpias con fecha, concepto, monto y deudor para enviar por chat o correo.',
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
    description: 'Estructura en JSON con resumen e índices para scripts, automatizaciones o análisis.',
    icon: Code,
    color: 'text-surface-300',
    bgLight: 'bg-surface-800 hover:bg-surface-700',
    borderColor: 'border-white/20',
    ext: '.json',
  },
];

type ModalTab = 'columns' | 'summary' | 'format';

export function ExplorerExportModal({
  isOpen,
  onClose,
  filteredTransactions,
  displayedTransactions,
  selectedTransactions,
  funds,
  debtLookup,
}: ExplorerExportModalProps) {
  // Scope: 'filtered' (all filtered), 'displayed' (only on page), 'selected' (checked rows)
  const defaultScope = selectedTransactions.length > 0 ? 'selected' : 'filtered';
  const [scope, setScope] = useState<'filtered' | 'displayed' | 'selected'>(defaultScope);
  const [activeTab, setActiveTab] = useState<ModalTab>('columns');

  // Columns & Presets
  const [selectedColumnIds, setSelectedColumnIds] = useState<string[]>(() =>
    EXPORT_COLUMNS.filter((c) => c.default).map((c) => c.id)
  );
  const [columnSearch, setColumnSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<'all' | ColumnCategory>('all');
  const [expandedCategories, setExpandedCategories] = useState<Record<ColumnCategory, boolean>>({
    basic: true,
    naming: true,
    classification: false,
    debt: false,
    meta: false,
  });
  const [showOrderDrawer, setShowOrderDrawer] = useState(false);

  // Format & Export Options
  const [format, setFormat] = useState<ExportFormat>('excel');
  const [flattenSplits, setFlattenSplits] = useState(true);
  const [includeHeaders, setIncludeHeaders] = useState(true);
  const [numberFormat, setNumberFormat] = useState<'raw' | 'formatted'>('raw');

  // Summary Customization State
  const [includeSummary, setIncludeSummary] = useState(true);
  const [summaryPosition, setSummaryPosition] = useState<'bottom' | 'top' | 'only'>('bottom');
  const [summaryIncludeTotals, setSummaryIncludeTotals] = useState(true);
  const [summaryIncludeDateRange, setSummaryIncludeDateRange] = useState(true);
  const [summaryIncludeDebts, setSummaryIncludeDebts] = useState(false);
  const [summaryIncludeCategories, setSummaryIncludeCategories] = useState(false);
  const [summaryIncludeTags, setSummaryIncludeTags] = useState(false);
  const [summaryIncludeInsights, setSummaryIncludeInsights] = useState(false);

  // Editable summary text state
  const [customSummaryText, setCustomSummaryText] = useState('');
  const [isSummaryManuallyEdited, setIsSummaryManuallyEdited] = useState(false);

  // Preview & Copy feedback
  const [showPreview, setShowPreview] = useState(false);
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

  const exportContext = useMemo(() => ({ funds, debtLookup }), [funds, debtLookup]);

  // Summary statistics of the exported set
  const summaryStats = useMemo(() => {
    const prepared = prepareTransactionsForExport(targetTransactions, flattenSplits);
    return calculateExportSummary(prepared, exportContext);
  }, [targetTransactions, flattenSplits, exportContext]);

  // Default auto-generated summary string
  const autoSummaryText = useMemo(() => {
    return buildDefaultSummaryText(summaryStats, {
      includeTotals: summaryIncludeTotals,
      includeDateRange: summaryIncludeDateRange,
      includeDebts: summaryIncludeDebts,
      includeCategories: summaryIncludeCategories,
      includeTags: summaryIncludeTags,
      includeInsights: summaryIncludeInsights,
    });
  }, [
    summaryStats,
    summaryIncludeTotals,
    summaryIncludeDateRange,
    summaryIncludeDebts,
    summaryIncludeCategories,
    summaryIncludeTags,
    summaryIncludeInsights,
  ]);

  // Keep customSummaryText in sync with autoSummaryText if not manually edited
  useEffect(() => {
    if (!isSummaryManuallyEdited) {
      setCustomSummaryText(autoSummaryText);
    }
  }, [autoSummaryText, isSummaryManuallyEdited]);

  const exportOptions = useMemo<ExportOptions>(() => {
    return {
      format,
      selectedColumnIds,
      flattenSplits,
      includeHeaders,
      includeSummary,
      summaryPosition,
      customSummaryText: includeSummary ? customSummaryText : undefined,
      numberFormat: format === 'text_list' ? 'formatted' : numberFormat,
    };
  }, [
    format,
    selectedColumnIds,
    flattenSplits,
    includeHeaders,
    includeSummary,
    summaryPosition,
    customSummaryText,
    numberFormat,
  ]);

  // Generate data output
  const generatedData = useMemo(() => {
    if (!isOpen) return { text: '', mimeType: 'text/plain', filename: 'transacciones.txt' };
    return generateExportData(targetTransactions, exportOptions, exportContext);
  }, [isOpen, targetTransactions, exportOptions, exportContext]);

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

  // Toggle category collapsed state
  const handleToggleCategoryExpand = (cat: ColumnCategory) => {
    setExpandedCategories((prev) => ({
      ...prev,
      [cat]: !prev[cat],
    }));
  };

  // Toggle an entire category's selection
  const handleToggleCategorySelection = (cat: ColumnCategory) => {
    const catCols = EXPORT_COLUMNS.filter((c) => c.category === cat).map((c) => c.id);
    const allSelected = catCols.every((id) => selectedColumnIds.includes(id));
    if (allSelected) {
      const remaining = selectedColumnIds.filter((id) => !catCols.includes(id));
      if (remaining.length > 0) setSelectedColumnIds(remaining);
    } else {
      const missing = catCols.filter((id) => !selectedColumnIds.includes(id));
      setSelectedColumnIds((prev) => [...prev, ...missing]);
    }
  };

  // Apply column preset
  const handleApplyPreset = (preset: ColumnPreset) => {
    setSelectedColumnIds(preset.columnIds);
  };

  const handleSelectAllColumns = () => {
    setSelectedColumnIds(EXPORT_COLUMNS.map((c) => c.id));
  };

  const handleMoveColumn = (id: string, direction: 'left' | 'right') => {
    setSelectedColumnIds((prev) => {
      const idx = prev.indexOf(id);
      if (idx === -1) return prev;
      const targetIdx = direction === 'left' ? idx - 1 : idx + 1;
      if (targetIdx < 0 || targetIdx >= prev.length) return prev;
      const copy = [...prev];
      const temp = copy[idx];
      copy[idx] = copy[targetIdx];
      copy[targetIdx] = temp;
      return copy;
    });
  };

  // Reset summary text back to automatic
  const handleResetSummaryToAuto = () => {
    setIsSummaryManuallyEdited(false);
    setCustomSummaryText(autoSummaryText);
  };

  // Copy Action
  const handleCopy = async (overrideFormat?: ExportFormat) => {
    const opts = overrideFormat ? { ...exportOptions, format: overrideFormat } : exportOptions;
    const data = generateExportData(targetTransactions, opts, exportContext);
    const success = await copyToClipboard(data.text, data.html);

    if (success) {
      setCopiedState(true);
      const targetLabel = FORMATS.find((f) => f.id === (overrideFormat || format))?.title || 'Datos';
      const detailMsg =
        summaryPosition === 'only'
          ? `¡Resumen copiado en formato ${targetLabel}!`
          : `¡${summaryStats.count} registros copiados (${targetLabel})!`;
      setCopyFeedbackMessage(detailMsg);
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

  // Filtered columns by search & category filter
  const visibleCategories = COLUMN_CATEGORIES.filter((cat) => {
    if (categoryFilter === 'all') return true;
    return cat.id === categoryFilter;
  });

  // Filtered columns for search
  const isSearching = columnSearch.trim().length > 0;

  // Preview truncated lines
  const previewLines = generatedData.text.split('\n');
  const maxPreviewLines = 15;
  const isPreviewTruncated = previewLines.length > maxPreviewLines;
  const displayPreviewText = isPreviewTruncated
    ? previewLines.slice(0, maxPreviewLines).join('\n') + `\n\n... y ${previewLines.length - maxPreviewLines} líneas más.`
    : generatedData.text;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 md:p-6 bg-black/85 backdrop-blur-md animate-in fade-in duration-200">
      <div
        className="bg-surface-900 border border-white/10 rounded-3xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4.5 border-b border-white/10 flex justify-between items-center bg-surface-950/80">
          <div className="flex items-center gap-3.5">
            <div className="p-2.5 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
              <FileSpreadsheet size={22} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base md:text-lg font-bold text-white tracking-tight">
                  Exportar y Compartir
                </h2>
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                  {summaryPosition === 'only' ? 'Solo Resumen' : `${summaryStats.count} filas`}
                </span>
                <span className="hidden sm:inline-block text-[11px] px-2 py-0.5 rounded-full bg-surface-800 text-surface-300 border border-white/5">
                  {selectedColumnIds.length} columnas
                </span>
              </div>
              <p className="text-xs text-surface-400 mt-0.5">
                Configura columnas precisas, añade estadísticas inteligentes o comparte discretamente.
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

        {/* Scope Selector Bar (Clean segmented pills) */}
        <div className="px-6 py-2.5 bg-surface-950/40 border-b border-white/5 flex items-center justify-between flex-wrap gap-2 text-xs">
          <span className="text-surface-400 font-medium">Registros a exportar:</span>

          <div className="flex items-center gap-1.5 bg-surface-950 p-1 rounded-xl border border-white/5">
            <button
              type="button"
              onClick={() => setScope('filtered')}
              className={`px-3 py-1 rounded-lg font-medium transition-all ${
                scope === 'filtered'
                  ? 'bg-primary-500/20 text-primary-200 border border-primary-500/40 shadow-sm font-semibold'
                  : 'text-surface-400 hover:text-surface-200'
              }`}
            >
              Filtradas ({filteredTransactions.length})
            </button>

            <button
              type="button"
              onClick={() => setScope('displayed')}
              className={`px-3 py-1 rounded-lg font-medium transition-all ${
                scope === 'displayed'
                  ? 'bg-primary-500/20 text-primary-200 border border-primary-500/40 shadow-sm font-semibold'
                  : 'text-surface-400 hover:text-surface-200'
              }`}
            >
              Visibles ({displayedTransactions.length})
            </button>

            <button
              type="button"
              onClick={() => {
                if (selectedTransactions.length > 0) setScope('selected');
              }}
              disabled={selectedTransactions.length === 0}
              className={`px-3 py-1 rounded-lg font-medium transition-all ${
                selectedTransactions.length === 0
                  ? 'opacity-30 cursor-not-allowed text-surface-600'
                  : scope === 'selected'
                  ? 'bg-primary-500/20 text-primary-200 border border-primary-500/40 shadow-sm font-semibold'
                  : 'text-surface-400 hover:text-surface-200'
              }`}
            >
              Seleccionadas ({selectedTransactions.length})
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="px-6 py-2 border-b border-white/10 bg-surface-950/30 flex items-center justify-between">
          <div className="flex items-center gap-1.5 p-1 rounded-2xl bg-surface-950/60 border border-white/5">
            <button
              type="button"
              onClick={() => setActiveTab('columns')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 ${
                activeTab === 'columns'
                  ? 'bg-surface-800 text-white shadow-sm ring-1 ring-white/10'
                  : 'text-surface-400 hover:text-surface-200 hover:bg-white/5'
              }`}
            >
              <Table size={14} className={activeTab === 'columns' ? 'text-primary-400' : ''} />
              <span>Columnas</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-primary-500/20 text-primary-300 font-mono">
                {selectedColumnIds.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('summary')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 ${
                activeTab === 'summary'
                  ? 'bg-surface-800 text-white shadow-sm ring-1 ring-white/10'
                  : 'text-surface-400 hover:text-surface-200 hover:bg-white/5'
              }`}
            >
              <Sparkles size={14} className={activeTab === 'summary' ? 'text-teal-400' : ''} />
              <span>Resumen Inteligente</span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full font-medium ${
                  includeSummary
                    ? summaryPosition === 'only'
                      ? 'bg-amber-500/20 text-amber-300'
                      : 'bg-teal-500/20 text-teal-300'
                    : 'bg-surface-800 text-surface-500'
                }`}
              >
                {includeSummary ? (summaryPosition === 'only' ? 'Solo Resumen' : 'Activo') : 'Off'}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('format')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 ${
                activeTab === 'format'
                  ? 'bg-surface-800 text-white shadow-sm ring-1 ring-white/10'
                  : 'text-surface-400 hover:text-surface-200 hover:bg-white/5'
              }`}
            >
              <Settings2 size={14} className={activeTab === 'format' ? 'text-indigo-400' : ''} />
              <span>Formato</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-white/10 text-surface-300 font-mono">
                {currentFormatMeta.badge}
              </span>
            </button>
          </div>

          <span className="text-[11px] text-surface-400 font-medium hidden sm:inline">
            Formato: <strong className="text-white">{currentFormatMeta.title.split(' ')[0]}</strong>
          </span>
        </div>

        {/* Tab Body */}
        <div className="flex-1 overflow-y-auto p-5 md:p-6 space-y-5 custom-scrollbar">

          {/* ==================== TAB 1: COLUMNAS ==================== */}
          {activeTab === 'columns' && (
            <div className="space-y-4 animate-in fade-in duration-200">

              {/* Presets Cards (Clear, direct, featuring Compartir Familia) */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-surface-300">
                    Presets de columnas
                  </span>
                  <span className="text-[11px] text-surface-500">
                    Un clic para configurar las columnas deseadas
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
                  {COLUMN_PRESETS.map((preset) => {
                    const isFullyMatching =
                      preset.columnIds.length === selectedColumnIds.length &&
                      preset.columnIds.every((id) => selectedColumnIds.includes(id));

                    const isFamily = preset.id === 'family_discrete';

                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => handleApplyPreset(preset)}
                        className={`p-2.5 rounded-xl border text-left transition-all relative flex flex-col justify-between ${
                          isFullyMatching
                            ? isFamily
                              ? 'bg-emerald-500/20 border-emerald-500/60 text-white ring-1 ring-emerald-500/40 shadow-sm'
                              : 'bg-primary-500/20 border-primary-500/60 text-white ring-1 ring-primary-500/40 shadow-sm'
                            : 'bg-surface-950/40 border-white/5 text-surface-400 hover:text-surface-200 hover:bg-surface-950/70 hover:border-white/15'
                        }`}
                        title={preset.description}
                      >
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-bold leading-tight text-white truncate">
                              {preset.name}
                            </span>
                          </div>
                          <div className="text-[10px] text-surface-400 leading-tight line-clamp-1">
                            {preset.badge || `${preset.columnIds.length} cols`}
                          </div>
                        </div>

                        <div className="mt-2 pt-1 border-t border-white/5 text-[9px] font-mono text-surface-400 flex items-center justify-between">
                          <span>{preset.columnIds.length} cols</span>
                          {isFullyMatching && (
                            <Check size={11} className={isFamily ? 'text-emerald-400' : 'text-primary-400'} />
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Active Selection Summary Bar (Progressive disclosure for reordering) */}
              <div className="bg-surface-950/50 border border-white/5 rounded-2xl p-3 flex items-center justify-between flex-wrap gap-2 text-xs">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-surface-400 font-medium">Columnas incluidas:</span>
                  <span className="font-bold text-white">
                    {selectedColumnIds.length} de {EXPORT_COLUMNS.length}
                  </span>
                  <span className="text-surface-600">•</span>
                  <div className="text-surface-300 font-medium truncate max-w-md">
                    {selectedColumnIds
                      .map((id) => EXPORT_COLUMNS.find((c) => c.id === id)?.label)
                      .filter(Boolean)
                      .join(', ')}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setShowOrderDrawer(!showOrderDrawer)}
                    className="text-primary-400 hover:text-primary-300 font-semibold flex items-center gap-1 transition-colors"
                  >
                    <span>{showOrderDrawer ? 'Ocultar orden' : 'Reordenar / Quitar'}</span>
                    <ChevronDown size={13} className={`transform transition-transform ${showOrderDrawer ? 'rotate-180' : ''}`} />
                  </button>
                  <span className="text-surface-700">|</span>
                  <button
                    type="button"
                    onClick={handleSelectAllColumns}
                    className="text-surface-400 hover:text-white"
                  >
                    Todas
                  </button>
                  <button
                    type="button"
                    onClick={() => handleApplyPreset(COLUMN_PRESETS[1])} // Compartir Familia
                    className="text-emerald-400 hover:text-emerald-300 font-medium"
                    title="Preset rápido: Fecha, Comercio, Categoría y Monto"
                  >
                    Solo Familia
                  </button>
                </div>
              </div>

              {/* Order and Remove Drawer (Collapsible) */}
              {showOrderDrawer && (
                <div className="bg-surface-950/70 border border-white/10 rounded-2xl p-3.5 space-y-2 animate-in fade-in duration-150">
                  <div className="flex items-center justify-between text-xs text-surface-400">
                    <span className="font-semibold text-surface-200">
                      Arrastra u ordena la secuencia de exportación:
                    </span>
                    <span className="text-[11px] text-surface-500">
                      Usa ← y → para cambiar posición
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto custom-scrollbar pt-1">
                    {selectedColumnIds.map((colId, idx) => {
                      const col = EXPORT_COLUMNS.find((c) => c.id === colId);
                      if (!col) return null;

                      return (
                        <div
                          key={col.id}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-900 border border-white/10 text-xs text-surface-200 font-medium group"
                        >
                          <span className="text-[10px] font-mono text-surface-500">{idx + 1}.</span>
                          <span className="truncate max-w-[130px]">{col.label}</span>

                          <div className="flex items-center gap-0.5 ml-1">
                            <button
                              type="button"
                              disabled={idx === 0}
                              onClick={() => handleMoveColumn(col.id, 'left')}
                              className="text-surface-500 hover:text-white disabled:opacity-20 disabled:hover:text-surface-500 p-0.5"
                              title="Mover a la izquierda"
                            >
                              <ArrowLeft size={10} />
                            </button>
                            <button
                              type="button"
                              disabled={idx === selectedColumnIds.length - 1}
                              onClick={() => handleMoveColumn(col.id, 'right')}
                              className="text-surface-500 hover:text-white disabled:opacity-20 disabled:hover:text-surface-500 p-0.5"
                              title="Mover a la derecha"
                            >
                              <ArrowRight size={10} />
                            </button>
                            {selectedColumnIds.length > 1 && (
                              <button
                                type="button"
                                onClick={() => handleToggleColumn(col.id)}
                                className="text-surface-500 hover:text-rose-400 p-0.5 ml-0.5"
                                title="Quitar columna"
                              >
                                <X size={11} />
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Filter pills & Search toolbar */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 pt-1">
                {/* Category Filter Pills */}
                <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0 custom-scrollbar text-xs">
                  <button
                    type="button"
                    onClick={() => setCategoryFilter('all')}
                    className={`px-2.5 py-1 rounded-lg font-medium transition-colors whitespace-nowrap ${
                      categoryFilter === 'all'
                        ? 'bg-white/15 text-white font-semibold'
                        : 'text-surface-400 hover:text-surface-200 hover:bg-white/5'
                    }`}
                  >
                    Todas ({EXPORT_COLUMNS.length})
                  </button>
                  {COLUMN_CATEGORIES.map((cat) => {
                    const countInCat = EXPORT_COLUMNS.filter((c) => c.category === cat.id).length;
                    return (
                      <button
                        key={cat.id}
                        type="button"
                        onClick={() => {
                          setCategoryFilter(cat.id);
                          setExpandedCategories((prev) => ({ ...prev, [cat.id]: true }));
                        }}
                        className={`px-2.5 py-1 rounded-lg font-medium transition-colors whitespace-nowrap ${
                          categoryFilter === cat.id
                            ? 'bg-primary-500/20 text-primary-200 border border-primary-500/30 font-semibold'
                            : 'text-surface-400 hover:text-surface-200 hover:bg-white/5'
                        }`}
                      >
                        {cat.label.split(' ')[0]} ({countInCat})
                      </button>
                    );
                  })}
                </div>

                {/* Search */}
                <div className="relative min-w-[200px]">
                  <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
                  <input
                    type="text"
                    value={columnSearch}
                    onChange={(e) => setColumnSearch(e.target.value)}
                    placeholder="Filtrar columnas..."
                    className="w-full pl-8 pr-7 py-1.5 rounded-xl bg-surface-950/60 border border-white/10 text-xs text-white placeholder-surface-500 focus:outline-none focus:border-primary-500/50"
                  />
                  {columnSearch && (
                    <button
                      onClick={() => setColumnSearch('')}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-400 hover:text-white"
                    >
                      <X size={11} />
                    </button>
                  )}
                </div>
              </div>

              {/* Folded / Collapsible Category Accordions */}
              <div className="space-y-2.5">
                {visibleCategories.map((catMeta) => {
                  const catColumns = EXPORT_COLUMNS.filter((c) => {
                    if (c.category !== catMeta.id) return false;
                    if (!columnSearch.trim()) return true;
                    const q = columnSearch.toLowerCase();
                    return (
                      c.label.toLowerCase().includes(q) ||
                      c.id.toLowerCase().includes(q) ||
                      (c.description && c.description.toLowerCase().includes(q))
                    );
                  });

                  if (catColumns.length === 0) return null;

                  const isExpanded = isSearching || expandedCategories[catMeta.id];
                  const totalInCat = EXPORT_COLUMNS.filter((c) => c.category === catMeta.id).length;
                  const selectedInCat = catColumns.filter((c) => selectedColumnIds.includes(c.id)).length;
                  const isAllSelectedInCat = selectedInCat === totalInCat;

                  return (
                    <div
                      key={catMeta.id}
                      className="bg-surface-950/40 border border-white/5 rounded-2xl overflow-hidden transition-all"
                    >
                      {/* Accordion Header */}
                      <div
                        onClick={() => handleToggleCategoryExpand(catMeta.id)}
                        className="px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-surface-950/70 select-none transition-colors"
                      >
                        <div className="flex items-center gap-2.5">
                          <span className="text-xs font-bold text-white tracking-tight">
                            {catMeta.label}
                          </span>
                          <span className="text-[10px] px-2 py-0.2 rounded-full bg-surface-900 border border-white/10 text-surface-300 font-mono">
                            {selectedInCat} de {totalInCat}
                          </span>

                          {!isExpanded && selectedInCat > 0 && (
                            <span className="hidden md:inline-block text-[11px] text-surface-500 truncate max-w-xs">
                              {catColumns
                                .filter((c) => selectedColumnIds.includes(c.id))
                                .map((c) => c.label)
                                .join(', ')}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleToggleCategorySelection(catMeta.id);
                            }}
                            className="text-[11px] font-semibold text-primary-400 hover:text-primary-300 transition-colors"
                          >
                            {isAllSelectedInCat ? 'Desmarcar' : 'Marcar todas'}
                          </button>

                          <div className="text-surface-400">
                            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                          </div>
                        </div>
                      </div>

                      {/* Accordion Content */}
                      {isExpanded && (
                        <div className="p-4 pt-1 border-t border-white/5 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 animate-in fade-in duration-150">
                          {catColumns.map((col) => {
                            const isChecked = selectedColumnIds.includes(col.id);

                            return (
                              <button
                                key={col.id}
                                type="button"
                                onClick={() => handleToggleColumn(col.id)}
                                className={`text-left p-2.5 rounded-xl border flex items-start gap-2.5 transition-all ${
                                  isChecked
                                    ? 'bg-primary-500/10 border-primary-500/30 text-white font-medium shadow-sm'
                                    : 'bg-surface-900/30 border-white/5 text-surface-400 hover:text-surface-200 hover:border-white/15'
                                }`}
                              >
                                <span
                                  className={`w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center mt-0.5 transition-all ${
                                    isChecked
                                      ? 'bg-primary-500 border-primary-500 shadow-sm'
                                      : 'border-surface-600 bg-surface-950/50'
                                  }`}
                                >
                                  {isChecked && <Check size={11} className="text-surface-950 font-bold" />}
                                </span>

                                <div className="flex-1 min-w-0">
                                  <div className="text-xs font-semibold leading-tight truncate">
                                    {col.label}
                                  </div>
                                  {col.description && (
                                    <div className="text-[10px] text-surface-400 leading-snug mt-0.5 line-clamp-1">
                                      {col.description}
                                    </div>
                                  )}
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

            </div>
          )}

          {/* ==================== TAB 2: RESUMEN INTELIGENTE ==================== */}
          {activeTab === 'summary' && (
            <div className="space-y-4 animate-in fade-in duration-200">

              {/* Master Switch */}
              <div className="bg-surface-950/50 border border-white/5 rounded-2xl p-4 flex items-center justify-between">
                <div>
                  <div className="text-xs font-bold text-white flex items-center gap-2">
                    <Sparkles size={15} className="text-teal-400" />
                    <span>Incluir resumen financiero en la exportación</span>
                  </div>
                  <p className="text-[11px] text-surface-400 mt-0.5">
                    Calcula totales, rango de fechas, top categorías, tags e insights de gasto. Puedes editarlo libremente.
                  </p>
                </div>

                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includeSummary}
                    onChange={(e) => setIncludeSummary(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-surface-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-surface-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-teal-600"></div>
                </label>
              </div>

              {includeSummary && (
                <>
                  {/* Position Selector */}
                  <div className="space-y-2">
                    <span className="text-xs font-semibold text-surface-300">
                      Ubicación del resumen
                    </span>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                      <button
                        type="button"
                        onClick={() => setSummaryPosition('bottom')}
                        className={`p-3 rounded-xl border text-left transition-all ${
                          summaryPosition === 'bottom'
                            ? 'bg-teal-500/15 border-teal-500/50 text-white ring-1 ring-teal-500/30'
                            : 'bg-surface-950/40 border-white/5 text-surface-400 hover:text-surface-200'
                        }`}
                      >
                        <div className="font-bold">⬇️ Al final</div>
                        <div className="text-[10px] text-surface-400 mt-0.5">
                          Debajo de las transacciones
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => setSummaryPosition('top')}
                        className={`p-3 rounded-xl border text-left transition-all ${
                          summaryPosition === 'top'
                            ? 'bg-teal-500/15 border-teal-500/50 text-white ring-1 ring-teal-500/30'
                            : 'bg-surface-950/40 border-white/5 text-surface-400 hover:text-surface-200'
                        }`}
                      >
                        <div className="font-bold">⬆️ Al inicio</div>
                        <div className="text-[10px] text-surface-400 mt-0.5">
                          Encabezando las transacciones
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => setSummaryPosition('only')}
                        className={`p-3 rounded-xl border text-left transition-all ${
                          summaryPosition === 'only'
                            ? 'bg-amber-500/15 border-amber-500/50 text-white ring-1 ring-amber-500/30'
                            : 'bg-surface-950/40 border-white/5 text-surface-400 hover:text-surface-200'
                        }`}
                      >
                        <div className="font-bold text-amber-300">📄 Solo el resumen</div>
                        <div className="text-[10px] text-surface-400 mt-0.5">
                          Copia solo el texto (para chat o notas)
                        </div>
                      </button>
                    </div>
                  </div>

                  {/* Smart Metric Checkboxes / Toggle Chips */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-surface-300">
                        Estadísticas automáticas a incluir
                      </span>
                      <span className="text-[11px] text-surface-500">
                        Activa o desactiva secciones del resumen
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 text-xs">
                      <label className={`p-2.5 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                        summaryIncludeTotals
                          ? 'bg-teal-500/10 border-teal-500/30 text-white font-medium'
                          : 'bg-surface-950/40 border-white/5 text-surface-400'
                      }`}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[11px] font-bold">Totales</span>
                          <input
                            type="checkbox"
                            checked={summaryIncludeTotals}
                            onChange={(e) => setSummaryIncludeTotals(e.target.checked)}
                            className="rounded border-surface-600 text-teal-600 focus:ring-teal-500 bg-surface-800"
                          />
                        </div>
                        <span className="text-[10px] text-surface-400">Ingresos y Neto</span>
                      </label>

                      <label className={`p-2.5 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                        summaryIncludeDateRange
                          ? 'bg-teal-500/10 border-teal-500/30 text-white font-medium'
                          : 'bg-surface-950/40 border-white/5 text-surface-400'
                      }`}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[11px] font-bold">Fechas</span>
                          <input
                            type="checkbox"
                            checked={summaryIncludeDateRange}
                            onChange={(e) => setSummaryIncludeDateRange(e.target.checked)}
                            className="rounded border-surface-600 text-teal-600 focus:ring-teal-500 bg-surface-800"
                          />
                        </div>
                        <span className="text-[10px] text-surface-400">Período y conteo</span>
                      </label>

                      <label className={`p-2.5 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                        summaryIncludeCategories
                          ? 'bg-teal-500/10 border-teal-500/30 text-white font-medium'
                          : 'bg-surface-950/40 border-white/5 text-surface-400'
                      }`}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[11px] font-bold">Categorías</span>
                          <input
                            type="checkbox"
                            checked={summaryIncludeCategories}
                            onChange={(e) => setSummaryIncludeCategories(e.target.checked)}
                            className="rounded border-surface-600 text-teal-600 focus:ring-teal-500 bg-surface-800"
                          />
                        </div>
                        <span className="text-[10px] text-surface-400">Mayores rubros</span>
                      </label>

                      {/* NEW: Top Tags */}
                      <label className={`p-2.5 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                        summaryIncludeTags
                          ? 'bg-teal-500/10 border-teal-500/30 text-white font-medium'
                          : 'bg-surface-950/40 border-white/5 text-surface-400'
                      }`}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[11px] font-bold text-purple-300">Top Tags</span>
                          <input
                            type="checkbox"
                            checked={summaryIncludeTags}
                            onChange={(e) => setSummaryIncludeTags(e.target.checked)}
                            className="rounded border-surface-600 text-teal-600 focus:ring-teal-500 bg-surface-800"
                          />
                        </div>
                        <span className="text-[10px] text-surface-400">#etiquetas clave</span>
                      </label>

                      {/* NEW: Daily Insights & Records */}
                      <label className={`p-2.5 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                        summaryIncludeInsights
                          ? 'bg-teal-500/10 border-teal-500/30 text-white font-medium'
                          : 'bg-surface-950/40 border-white/5 text-surface-400'
                      }`}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[11px] font-bold text-amber-300">Récords</span>
                          <input
                            type="checkbox"
                            checked={summaryIncludeInsights}
                            onChange={(e) => setSummaryIncludeInsights(e.target.checked)}
                            className="rounded border-surface-600 text-teal-600 focus:ring-teal-500 bg-surface-800"
                          />
                        </div>
                        <span className="text-[10px] text-surface-400">Día pico y mayor</span>
                      </label>

                      <label className={`p-2.5 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                        summaryIncludeDebts
                          ? 'bg-teal-500/10 border-teal-500/30 text-white font-medium'
                          : 'bg-surface-950/40 border-white/5 text-surface-400'
                      }`}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[11px] font-bold">Deudas</span>
                          <input
                            type="checkbox"
                            checked={summaryIncludeDebts}
                            onChange={(e) => setSummaryIncludeDebts(e.target.checked)}
                            className="rounded border-surface-600 text-teal-600 focus:ring-teal-500 bg-surface-800"
                          />
                        </div>
                        <span className="text-[10px] text-surface-400">Cobros y saldos</span>
                      </label>
                    </div>
                  </div>

                  {/* Live Editable Textarea */}
                  <div className="bg-surface-950/60 border border-white/10 rounded-2xl p-4 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white">
                          Texto del resumen
                        </span>
                        {isSummaryManuallyEdited && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                            Editado a mano
                          </span>
                        )}
                      </div>

                      <button
                        type="button"
                        onClick={handleResetSummaryToAuto}
                        className="text-xs text-primary-400 hover:text-primary-300 font-semibold flex items-center gap-1 transition-colors"
                        title="Restaura el resumen calculado a partir de las opciones actuales"
                      >
                        <RotateCcw size={12} />
                        <span>Restablecer automático</span>
                      </button>
                    </div>

                    <textarea
                      value={customSummaryText}
                      onChange={(e) => {
                        setIsSummaryManuallyEdited(true);
                        setCustomSummaryText(e.target.value);
                      }}
                      rows={7}
                      className="w-full p-3 rounded-xl bg-surface-900 border border-white/10 font-mono text-xs text-surface-200 focus:outline-none focus:border-teal-500/50 leading-relaxed custom-scrollbar"
                      placeholder="Escribe o ajusta aquí el texto del resumen..."
                    />

                    <div className="flex items-center justify-between text-[11px] text-surface-500">
                      <span>
                        💡 Las notas o números que modifiques aquí se exportarán directamente a Excel, Markdown o portapapeles.
                      </span>
                      <span>{customSummaryText.length} carácteres</span>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* ==================== TAB 3: FORMATO ==================== */}
          {activeTab === 'format' && (
            <div className="space-y-4 animate-in fade-in duration-200">
              <div className="space-y-2">
                <span className="text-xs font-semibold text-surface-300">
                  Formato de salida
                </span>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                  {FORMATS.map((fmt) => {
                    const isSelected = format === fmt.id;
                    const IconComponent = fmt.icon;
                    return (
                      <div
                        key={fmt.id}
                        onClick={() => setFormat(fmt.id)}
                        className={`p-3.5 rounded-2xl border cursor-pointer transition-all flex flex-col justify-between ${
                          isSelected
                            ? `bg-surface-800 ${fmt.borderColor} ring-1 ${fmt.borderColor} shadow-md`
                            : 'bg-surface-950/40 border-white/5 hover:border-white/15 hover:bg-surface-950/70'
                        }`}
                      >
                        <div>
                          <div className="flex items-center justify-between mb-1.5">
                            <div className="flex items-center gap-2">
                              <div className={`p-1.5 rounded-xl bg-white/5 ${fmt.color}`}>
                                <IconComponent size={15} />
                              </div>
                              <span className="text-xs font-bold text-white">{fmt.title}</span>
                            </div>
                            <span
                              className={`text-[9px] font-bold px-1.5 py-0.5 rounded-md border ${
                                isSelected
                                  ? 'bg-white/10 text-white border-white/20'
                                  : 'bg-surface-900 text-surface-400 border-white/5'
                              }`}
                            >
                              {fmt.badge}
                            </span>
                          </div>
                          <p className="text-[11px] text-surface-400 leading-relaxed">
                            {fmt.description}
                          </p>
                        </div>

                        <div className="mt-3 pt-2 border-t border-white/5 flex items-center justify-between">
                          <span className="text-[10px] font-mono text-surface-500">{fmt.ext}</span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setFormat(fmt.id);
                              handleCopy(fmt.id);
                            }}
                            className={`text-[11px] font-bold px-2 py-0.5 rounded-lg transition-all flex items-center gap-1 ${
                              isSelected
                                ? 'bg-primary-500/20 text-primary-300'
                                : 'text-surface-400 hover:text-white'
                            }`}
                          >
                            <Copy size={11} /> Copiar ya
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Format Options */}
              <div className="bg-surface-950/50 border border-white/5 rounded-2xl p-4 space-y-3">
                <span className="text-xs font-bold uppercase tracking-wider text-surface-300 flex items-center gap-1.5">
                  <Settings2 size={13} className="text-primary-400" /> Opciones estructurales
                </span>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                  <label className="flex items-center gap-2.5 p-3 rounded-xl bg-surface-900/60 border border-white/5 cursor-pointer hover:bg-surface-900">
                    <input
                      type="checkbox"
                      checked={flattenSplits}
                      onChange={(e) => setFlattenSplits(e.target.checked)}
                      className="rounded border-surface-600 text-primary-600 focus:ring-primary-500 bg-surface-800"
                    />
                    <div>
                      <div className="font-semibold text-white">Desglosar Splits</div>
                      <div className="text-[10px] text-surface-400">Exporta las partes individuales</div>
                    </div>
                  </label>

                  <label className="flex items-center gap-2.5 p-3 rounded-xl bg-surface-900/60 border border-white/5 cursor-pointer hover:bg-surface-900">
                    <input
                      type="checkbox"
                      checked={includeHeaders}
                      onChange={(e) => setIncludeHeaders(e.target.checked)}
                      className="rounded border-surface-600 text-primary-600 focus:ring-primary-500 bg-surface-800"
                    />
                    <div>
                      <div className="font-semibold text-white">Encabezados</div>
                      <div className="text-[10px] text-surface-400">Nombres de columna en la primera fila</div>
                    </div>
                  </label>

                  <div className="p-3 rounded-xl bg-surface-900/60 border border-white/5 flex flex-col justify-between">
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
              </div>
            </div>
          )}

          {/* ==================== LIVE PREVIEW DRAWER (Collapsible) ==================== */}
          <div className="pt-2 border-t border-white/5">
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => setShowPreview(!showPreview)}
                className="text-xs font-semibold text-surface-400 flex items-center gap-1.5 hover:text-white transition-colors"
              >
                <Eye size={13} className="text-primary-400" />
                <span>{showPreview ? 'Ocultar vista previa' : 'Ver vista previa de salida'}</span>
                <span className="text-[10px] text-surface-500">
                  ({generatedData.filename})
                </span>
                <ChevronDown size={13} className={`transform transition-transform ${showPreview ? 'rotate-180' : ''}`} />
              </button>

              <span className="text-[11px] text-surface-500 font-mono">
                {previewLines.length} líneas generadas
              </span>
            </div>

            {showPreview && (
              <div className="mt-2 relative rounded-2xl border border-white/10 bg-surface-950 p-3.5 font-mono text-xs text-surface-300 overflow-x-auto max-h-48 custom-scrollbar">
                <pre className="whitespace-pre">{displayPreviewText}</pre>
              </div>
            )}
          </div>

          {/* Quick Metrics Strip */}
          <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-surface-950/30 border border-white/5 text-xs text-surface-400 flex-wrap gap-2">
            <span>
              Registros: <strong className="text-white">{summaryStats.count}</strong>
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
            {summaryStats.debtCount > 0 && (
              <span className="text-amber-400/90 font-medium">
                Deudas: {summaryStats.debtCount} ({money(summaryStats.reimbursableTotal)})
              </span>
            )}
            {summaryStats.highestExpense && (
              <span className="text-surface-500 hidden md:inline">
                Mayor gasto: <span className="text-surface-300">{money(summaryStats.highestExpense.monto)}</span>
              </span>
            )}
          </div>

        </div>

        {/* Footer with Primary Actions */}
        <div className="p-4 md:px-6 border-t border-white/10 bg-surface-950/80 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button
              type="button"
              onClick={onClose}
              className="w-full sm:w-auto px-4 py-2 rounded-xl border border-white/10 text-surface-300 hover:text-white hover:bg-white/5 text-xs font-bold transition-all"
            >
              Cerrar
            </button>
            <button
              type="button"
              onClick={handleDownload}
              className="w-full sm:w-auto px-4 py-2 rounded-xl border border-white/10 text-surface-200 hover:text-white hover:bg-white/10 text-xs font-bold transition-all flex items-center justify-center gap-2"
              title={`Descargar archivo ${generatedData.filename}`}
            >
              <Download size={14} /> Descargar archivo
            </button>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            {copyFeedbackMessage && (
              <span className="text-xs text-emerald-400 font-semibold animate-in fade-in">
                {copyFeedbackMessage}
              </span>
            )}
            <button
              type="button"
              onClick={() => handleCopy()}
              className={`w-full sm:w-auto px-6 py-2.5 rounded-xl text-xs font-bold transition-all duration-200 flex items-center justify-center gap-2 shadow-xl ${
                copiedState
                  ? 'bg-emerald-500 text-white shadow-emerald-900/30 scale-105'
                  : 'bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-700 hover:from-emerald-500 hover:to-teal-500 text-white shadow-emerald-950/40 hover:scale-[1.01] active:scale-[0.99]'
              }`}
            >
              {copiedState ? (
                <>
                  <Check size={15} />
                  <span>¡Copiado al portapapeles!</span>
                </>
              ) : (
                <>
                  <Copy size={15} />
                  <span>
                    {summaryPosition === 'only'
                      ? 'Copiar Solo Resumen'
                      : `Copiar al Portapapeles (${summaryStats.count})`}
                  </span>
                </>
              )}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
