import { useState, useMemo, useEffect } from 'react';
import { X, Search, RotateCcw, Check, Ban, Tag, Layers, Lock, ShieldAlert } from 'lucide-react';

export interface ExplorerExclusionsModalProps {
  isOpen: boolean;
  onClose: () => void;
  categories: string[];
  tags: string[];
  excludedCategories: string[];
  onToggleCategory: (category: string) => void;
  onClearCategories: () => void;
  excludedTags: string[];
  onToggleTag: (tag: string) => void;
  onClearTags: () => void;
  fixedFilter: 'all' | 'fixed' | 'non_fixed';
  onChangeFixedFilter: (value: 'all' | 'fixed' | 'non_fixed') => void;
  reimbursableFilter: 'all' | 'included' | 'excluded';
  onChangeReimbursableFilter: (value: 'all' | 'included' | 'excluded') => void;
}

const DEFAULT_CATEGORIES = [
  'Alimentación', 'Transporte', 'Ocio', 'Salud', 'Subscripciones',
  'Mensual', 'Inversion', 'Regalo', 'Mujeres', 'Aseo', 'Deudas',
  'Tarjeta', 'Ropa', 'Viajes', 'Otro'
];

export function ExplorerExclusionsModal({
  isOpen,
  onClose,
  categories,
  tags,
  excludedCategories,
  onToggleCategory,
  onClearCategories,
  excludedTags,
  onToggleTag,
  onClearTags,
  fixedFilter,
  onChangeFixedFilter,
  reimbursableFilter,
  onChangeReimbursableFilter,
}: ExplorerExclusionsModalProps) {
  const [searchCat, setSearchCat] = useState('');
  const [searchTag, setSearchTag] = useState('');

  // Close on ESC
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const allCategories = useMemo(() => {
    const raw = categories && categories.length > 0 ? categories : DEFAULT_CATEGORIES;
    const cleanList = Array.from(new Set(raw.filter(c => c && c !== '---')));
    return [...cleanList, 'Sin Categoría'];
  }, [categories]);

  const filteredCategories = useMemo(() => {
    if (!searchCat.trim()) return allCategories;
    const q = searchCat.toLowerCase();
    return allCategories.filter(c => c.toLowerCase().includes(q));
  }, [allCategories, searchCat]);

  const allTags = useMemo(() => {
    const cleanList = Array.from(new Set((tags || []).filter(Boolean)));
    return [...cleanList, 'Sin Etiqueta'];
  }, [tags]);

  const filteredTags = useMemo(() => {
    if (!searchTag.trim()) return allTags;
    const q = searchTag.toLowerCase();
    return allTags.filter(t => t.toLowerCase().includes(q));
  }, [allTags, searchTag]);

  const totalExclusionsCount =
    excludedCategories.length +
    excludedTags.length +
    (fixedFilter !== 'all' ? 1 : 0) +
    (reimbursableFilter !== 'all' ? 1 : 0);

  const handleResetAllExclusions = () => {
    onClearCategories();
    onClearTags();
    onChangeFixedFilter('all');
    onChangeReimbursableFilter('all');
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-surface-900/95 border border-white/10 rounded-3xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden backdrop-blur-xl">
        
        {/* Modal Header */}
        <div className="p-5 md:px-7 border-b border-white/10 flex justify-between items-center bg-surface-950/70">
          <div className="space-y-1">
            <h2 className="text-xl md:text-2xl font-bold text-white flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
                <Ban size={22} />
              </div>
              <span>Filtros de Exclusión</span>
              {totalExclusionsCount > 0 && (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                  {totalExclusionsCount} activa{totalExclusionsCount > 1 ? 's' : ''}
                </span>
              )}
            </h2>
            <p className="text-xs md:text-sm text-surface-400">
              Oculta categorías, etiquetas, reembolsables o gastos fijos de las transacciones y analíticas en tiempo real.
            </p>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-surface-400 hover:text-white transition-colors bg-surface-800/80 hover:bg-surface-700 rounded-xl"
            title="Cerrar modal (Esc)"
          >
            <X size={20} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 md:p-7 overflow-y-auto custom-scrollbar flex-1 space-y-7">

          {/* Section 1: Exclusión de Categorías */}
          <div className="space-y-3.5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-white/5">
              <div className="flex items-center gap-2">
                <Layers size={16} className="text-indigo-400" />
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">Categorías Excluidas</h3>
                {excludedCategories.length > 0 && (
                  <span className="text-xs text-rose-400 font-semibold">
                    ({excludedCategories.length} seleccionada{excludedCategories.length > 1 ? 's' : ''})
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                {excludedCategories.length > 0 && (
                  <button
                    onClick={onClearCategories}
                    className="text-xs text-rose-400 hover:text-rose-300 font-medium hover:underline flex items-center gap-1"
                  >
                    <RotateCcw size={12} /> Limpiar categorías
                  </button>
                )}
              </div>
            </div>

            {/* Search Categories */}
            {allCategories.length > 8 && (
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                <input
                  type="text"
                  value={searchCat}
                  onChange={e => setSearchCat(e.target.value)}
                  placeholder="Buscar categoría para excluir..."
                  className="w-full bg-surface-950/80 border border-white/10 rounded-xl pl-9 pr-3 py-1.5 text-xs text-white placeholder:text-surface-500 focus:outline-none focus:border-indigo-500/50"
                />
                {searchCat && (
                  <button
                    onClick={() => setSearchCat('')}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 hover:text-white"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>
            )}

            {/* Categories Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
              {filteredCategories.map(cat => {
                const isExcluded = excludedCategories.includes(cat) || (cat === 'Sin Categoría' && excludedCategories.includes('__sin_categoria__'));
                return (
                  <label
                    key={cat}
                    onClick={() => onToggleCategory(cat === 'Sin Categoría' ? '__sin_categoria__' : cat)}
                    className={`flex items-center gap-2 p-2 rounded-xl border cursor-pointer select-none transition-all ${
                      isExcluded
                        ? 'bg-rose-500/15 border-rose-500/40 text-rose-300 shadow-sm shadow-rose-950/30 font-semibold'
                        : 'bg-surface-950/60 border-white/5 text-surface-300 hover:bg-surface-800 hover:border-white/10'
                    }`}
                  >
                    <div className={`w-4 h-4 rounded-md border flex items-center justify-center shrink-0 transition-colors ${
                      isExcluded ? 'bg-rose-500 border-rose-500 text-white' : 'border-surface-600 bg-surface-900'
                    }`}>
                      {isExcluded && <Check size={11} strokeWidth={3} />}
                    </div>
                    <span className={`text-xs truncate ${isExcluded ? 'line-through opacity-90' : ''}`}>
                      {cat}
                    </span>
                  </label>
                );
              })}
            </div>
            {filteredCategories.length === 0 && (
              <p className="text-xs text-surface-500 italic py-2 text-center">No se encontraron categorías coincidentes.</p>
            )}
          </div>

          {/* Section 2: Exclusión de Etiquetas (Tags) */}
          <div className="space-y-3.5 pt-2 border-t border-white/5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-white/5">
              <div className="flex items-center gap-2">
                <Tag size={16} className="text-violet-400" />
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">Etiquetas (Tags) Excluidas</h3>
                {excludedTags.length > 0 && (
                  <span className="text-xs text-rose-400 font-semibold">
                    ({excludedTags.length} seleccionada{excludedTags.length > 1 ? 's' : ''})
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                {excludedTags.length > 0 && (
                  <button
                    onClick={onClearTags}
                    className="text-xs text-rose-400 hover:text-rose-300 font-medium hover:underline flex items-center gap-1"
                  >
                    <RotateCcw size={12} /> Limpiar etiquetas
                  </button>
                )}
              </div>
            </div>

            {/* Search Tags */}
            {allTags.length > 8 && (
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                <input
                  type="text"
                  value={searchTag}
                  onChange={e => setSearchTag(e.target.value)}
                  placeholder="Buscar tag para excluir..."
                  className="w-full bg-surface-950/80 border border-white/10 rounded-xl pl-9 pr-3 py-1.5 text-xs text-white placeholder:text-surface-500 focus:outline-none focus:border-violet-500/50"
                />
                {searchTag && (
                  <button
                    onClick={() => setSearchTag('')}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 hover:text-white"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>
            )}

            {/* Tags Flex Wrap */}
            <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto custom-scrollbar p-1">
              {filteredTags.map(tag => {
                const isExcluded = excludedTags.includes(tag) || (tag === 'Sin Etiqueta' && excludedTags.includes('__sin_tags__'));
                return (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => onToggleTag(tag === 'Sin Etiqueta' ? '__sin_tags__' : tag)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs cursor-pointer select-none transition-all ${
                      isExcluded
                        ? 'bg-rose-500/15 border-rose-500/40 text-rose-300 shadow-sm shadow-rose-950/30 font-semibold'
                        : 'bg-surface-950/60 border-white/5 text-surface-300 hover:bg-surface-800 hover:border-white/10'
                    }`}
                  >
                    <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 transition-colors ${
                      isExcluded ? 'bg-rose-500 border-rose-500 text-white' : 'border-surface-600 bg-surface-900'
                    }`}>
                      {isExcluded && <Check size={10} strokeWidth={3} />}
                    </div>
                    <span className={isExcluded ? 'line-through opacity-90' : ''}>
                      {tag === 'Sin Etiqueta' ? '⚪ Sin Etiqueta' : `#${tag}`}
                    </span>
                  </button>
                );
              })}
            </div>
            {filteredTags.length === 0 && (
              <p className="text-xs text-surface-500 italic py-2 text-center">No se encontraron etiquetas coincidentes.</p>
            )}
          </div>

          {/* Section 3: Gastos Fijos y Reembolsables */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-white/5">
            
            {/* Gastos Fijos */}
            <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-4 space-y-2.5">
              <div className="flex items-center gap-2 pb-1 border-b border-white/5">
                <Lock size={15} className="text-blue-400" />
                <span className="text-xs font-bold text-surface-200 uppercase tracking-wider">Gastos Fijos</span>
              </div>
              <p className="text-[11px] text-surface-400">
                Filtra o excluye gastos recurrentes/fijos (arriendo, servicios, cuotas fijas).
              </p>
              <div className="grid grid-cols-3 gap-1.5 bg-surface-900 p-1 rounded-xl border border-white/5">
                <button
                  type="button"
                  onClick={() => onChangeFixedFilter('all')}
                  className={`py-1.5 text-xs font-medium rounded-lg transition-all ${
                    fixedFilter === 'all'
                      ? 'bg-surface-800 text-white font-semibold'
                      : 'text-surface-400 hover:text-white'
                  }`}
                >
                  Todos
                </button>
                <button
                  type="button"
                  onClick={() => onChangeFixedFilter('fixed')}
                  className={`py-1.5 text-xs font-medium rounded-lg transition-all ${
                    fixedFilter === 'fixed'
                      ? 'bg-blue-500/20 text-blue-300 font-semibold border border-blue-500/30'
                      : 'text-surface-400 hover:text-white'
                  }`}
                >
                  Solo Fijos
                </button>
                <button
                  type="button"
                  onClick={() => onChangeFixedFilter('non_fixed')}
                  className={`py-1.5 text-xs font-medium rounded-lg transition-all ${
                    fixedFilter === 'non_fixed'
                      ? 'bg-rose-500/20 text-rose-300 font-semibold border border-rose-500/30'
                      : 'text-surface-400 hover:text-white'
                  }`}
                >
                  🚫 Excluir
                </button>
              </div>
            </div>

            {/* Reembolsables */}
            <div className="bg-surface-950/60 border border-white/5 rounded-2xl p-4 space-y-2.5">
              <div className="flex items-center gap-2 pb-1 border-b border-white/5">
                <ShieldAlert size={15} className="text-purple-400" />
                <span className="text-xs font-bold text-surface-200 uppercase tracking-wider">Reembolsos</span>
              </div>
              <p className="text-[11px] text-surface-400">
                Filtra gastos que serán devueltos o cobrados a terceros.
              </p>
              <div className="grid grid-cols-3 gap-1.5 bg-surface-900 p-1 rounded-xl border border-white/5">
                <button
                  type="button"
                  onClick={() => onChangeReimbursableFilter('all')}
                  className={`py-1.5 text-xs font-medium rounded-lg transition-all ${
                    reimbursableFilter === 'all'
                      ? 'bg-surface-800 text-white font-semibold'
                      : 'text-surface-400 hover:text-white'
                  }`}
                >
                  Todos
                </button>
                <button
                  type="button"
                  onClick={() => onChangeReimbursableFilter('included')}
                  className={`py-1.5 text-xs font-medium rounded-lg transition-all ${
                    reimbursableFilter === 'included'
                      ? 'bg-purple-500/20 text-purple-300 font-semibold border border-purple-500/30'
                      : 'text-surface-400 hover:text-white'
                  }`}
                >
                  Solo Reemb.
                </button>
                <button
                  type="button"
                  onClick={() => onChangeReimbursableFilter('excluded')}
                  className={`py-1.5 text-xs font-medium rounded-lg transition-all ${
                    reimbursableFilter === 'excluded'
                      ? 'bg-rose-500/20 text-rose-300 font-semibold border border-rose-500/30'
                      : 'text-surface-400 hover:text-white'
                  }`}
                >
                  🚫 Excluir
                </button>
              </div>
            </div>

          </div>

        </div>

        {/* Modal Footer */}
        <div className="p-4 px-7 border-t border-white/10 bg-surface-950/70 flex justify-between items-center text-xs text-surface-400">
          <div>
            {totalExclusionsCount > 0 ? (
              <button
                type="button"
                onClick={handleResetAllExclusions}
                className="text-rose-400 hover:text-rose-300 font-semibold hover:underline flex items-center gap-1.5"
              >
                <RotateCcw size={13} /> Limpiar todas las exclusiones ({totalExclusionsCount})
              </button>
            ) : (
              <span>No hay exclusiones activas.</span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-6 py-2.5 bg-gradient-to-r from-primary-600 to-indigo-600 hover:from-primary-500 hover:to-indigo-500 text-white font-bold rounded-xl transition-all shadow-lg shadow-primary-900/25 active:scale-[0.98]"
          >
            Aplicar y Cerrar
          </button>
        </div>

      </div>
    </div>
  );
}
