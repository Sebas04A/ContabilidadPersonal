import { useState, useEffect, useRef } from 'react';
import { Transaction, TransactionUpdate, api, SplitItem, SupabaseDebt, SupabaseDeudor } from '../services/api';
import {
  X, Tag, ArrowUpRight, ArrowDownLeft, Check,
  CreditCard, Flame, Heart, Sparkles, User,
  Frown, Meh, DollarSign, StickyNote, Save, AlertCircle,
  Link2, Plus, CheckCircle2, Loader2
} from 'lucide-react';

interface EditModalProps {
  transaction: Transaction | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (id: string, updates: TransactionUpdate) => void;
  categories: string[];
  existingTags: string[];
}

const CATEGORY_OPTIONS = [
  '---', 'Alimentación', 'Transporte', 'Ocio', 'Salud', 
  'Subscripciones', 'Mensual', 'Inversion', 'Regalo', 
  'Mujeres', 'Aseo', 'Deudas', 'Tarjeta', 'Ropa', 'Viajes', 'Otro'
];

// "¿De quién es?": opciones fijas + todas las personas de Supabase (deudores).
const PERTENECE_BASE = ['---', 'Yo', 'Familia', 'Amigos'];

/** Fecha (YYYY-MM-DD) desde el FECHA de la transacción, sin corrimiento de zona horaria. */
const fechaDia = (fecha: string) => (fecha || '').slice(0, 10);

// --- Subcomponents for "Control Console" Look ---

const SectionLabel = ({ icon: Icon, label }: { icon: any, label: string }) => (
  <div className="flex items-center gap-2 mb-3 text-surface-400/80">
    <Icon size={14} className="stroke-[2.5] text-primary-400" />
    <span className="text-[11px] font-bold uppercase tracking-widest text-primary-200/70">{label}</span>
  </div>
);

const ConsoleInput = ({ className = "", ...props }: React.InputHTMLAttributes<HTMLInputElement>) => (
  <input 
    className={`
      w-full bg-surface-900 border border-white/5 rounded-xl px-4 py-3.5
      text-surface-50 placeholder:text-surface-600 font-medium
      focus:outline-none focus:border-primary-500/50 focus:bg-surface-800
      focus:ring-1 focus:ring-primary-500/20
      shadow-[inset_0_2px_4px_rgba(0,0,0,0.3)] 
      transition-all duration-200 ${className}
    `}
    {...props}
  />
);

const ConsoleSelect = ({ value, onChange, options, icon: Icon }: { value: string, onChange: (val: string) => void, options: string[], icon?: any }) => (
  <div className="relative group">
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="
        w-full appearance-none bg-surface-900 border border-white/5 rounded-xl px-4 py-3.5 pr-10
        text-surface-50 font-medium
        focus:outline-none focus:border-primary-500/50 focus:bg-surface-800
        focus:ring-1 focus:ring-primary-500/20
        shadow-[inset_0_2px_4px_rgba(0,0,0,0.3)]
        cursor-pointer transition-all duration-200
        hover:border-white/20
      "
    >
      {options.map(opt => (
        <option key={opt} value={opt} className="bg-surface-900 text-surface-300 py-2">{opt}</option>
      ))}
    </select>
    <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-surface-500 group-hover:text-surface-300 transition-colors">
      {Icon ? <Icon size={16} /> : <div className="w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-t-[5px] border-t-current" />}
    </div>
  </div>
);

export function EditModal({ transaction, isOpen, onClose, onSave, existingTags }: EditModalProps) {
  const [isSplitting, setIsSplitting] = useState(false);
  const [splits, setSplits] = useState<SplitItem[]>([]);
  
  const [formData, setFormData] = useState<TransactionUpdate>({});
  const [tagInput, setTagInput] = useState('');
  const [isClosing, setIsClosing] = useState(false);
  const [savingRule, setSavingRule] = useState(false);
  const [savingTagRule, setSavingTagRule] = useState(false);
  const [showTagSelect, setShowTagSelect] = useState(false);
  const tagInputRef = useRef<HTMLInputElement>(null);

  // --- Deuda / Supabase ---
  const [deudores, setDeudores] = useState<SupabaseDeudor[]>([]);
  const [sameDayDebts, setSameDayDebts] = useState<SupabaseDebt[]>([]);
  const [debtMode, setDebtMode] = useState<'associate' | 'create'>('create');
  const [selectedDeudaId, setSelectedDeudaId] = useState<string>('');
  const [debtTitulo, setDebtTitulo] = useState('');
  const [debtMonto, setDebtMonto] = useState<number>(0);
  const [debtDeudorId, setDebtDeudorId] = useState<string>('');
  const [creatingDebt, setCreatingDebt] = useState(false);
  const [debtError, setDebtError] = useState('');

  // Initialize form and splits when opening
  useEffect(() => {
    if (transaction) {
        const hasSplits = transaction.subTransactions && transaction.subTransactions.length > 0;
        
        setIsSplitting(hasSplits || false);

        if (hasSplits) {
            // Load existing splits
            const loadedSplits: SplitItem[] = transaction.subTransactions!.map(t => ({
                monto: Math.abs(t.MONTO),
                categoria: t.categoria || '---',
                tags: t.tags || '',
                nota: t.nota || '',
                prioridad: t.prioridad,
                es_fijo: t.es_fijo,
                nombre_limpio: t.nombre_limpio || t.DESCRIPCION, // Use nombre_limpio if avail
                // Add other fields as needed
                pertenece_a: t.pertenece_a,
                es_reembolsable: t.es_reembolsable,
                deudor: t.deudor,
                felicidad: t.felicidad
            }));
            setSplits(loadedSplits);
            setSelectedSplitIndex(0);

            // Init form with first split
            const first = loadedSplits[0];
            setFormData({
                nombre_limpio: first.nombre_limpio,
                categoria: first.categoria,
                tags: first.tags,
                prioridad: first.prioridad,
                es_fijo: first.es_fijo,
                pertenece_a: first.pertenece_a,
                es_reembolsable: first.es_reembolsable,
                deudor: first.deudor,
                felicidad: first.felicidad,
                nota: first.nota,
                revisado: true
            });

        } else {
            // Normal init
            setSplits([{
                monto: Math.abs(transaction.MONTO),
                categoria: transaction.categoria || '---',
                tags: transaction.tags || '',
                nota: transaction.nota || '',
                nombre_limpio: transaction.nombre_limpio
            }]);

            // Init Form Data
            setFormData({
                nombre_limpio: transaction.nombre_limpio || transaction.DESCRIPCION,
                categoria: transaction.categoria || '---',
                tags: transaction.tags || '',
                prioridad: transaction.prioridad || '---',
                es_fijo: transaction.es_fijo || false,
                pertenece_a: transaction.pertenece_a || '---',
                es_reembolsable: transaction.es_reembolsable || false,
                deudor: transaction.deudor || '',
                felicidad: transaction.felicidad || 0,
                nota: transaction.nota || '',
                revisado: true,
            });
        }
        
        setTagInput('');
        setIsClosing(false);
        setSavingRule(false);

        // Estado de deuda
        const existingDeuda = transaction.deuda_id ? String(transaction.deuda_id) : '';
        setSelectedDeudaId(existingDeuda);
        setDebtMode(existingDeuda ? 'associate' : 'create');
        setDebtTitulo(transaction.nombre_limpio || transaction.DESCRIPCION);
        setDebtMonto(Math.abs(transaction.MONTO));
        setDebtDeudorId('');
        setDebtError('');
        setSameDayDebts([]);
    }
  }, [transaction]);

  // Auto-fetch rule when clean name changes
  useEffect(() => {
      const fetchRule = async () => {
          if (!formData.nombre_limpio || !isOpen) return;
          
          try {
              const rule = await api.getEntityRule(formData.nombre_limpio);
              if (rule && Object.keys(rule).length > 0) {
                  let tagRuleData: any = {};
                  
                  // If the rule auto-populates a tag, let's fetch its tag rule to cascade
                  if (rule.tags) {
                      const tagsList = rule.tags.split(',').map((t: string) => t.trim()).filter(Boolean);
                      for (const tag of tagsList) {
                          try {
                              const tr = await api.getTagRule(tag);
                              if (tr && Object.keys(tr).length > 0) {
                                  tagRuleData = tr;
                                  break; // Apply first matched tag rule
                              }
                          } catch (e) {}
                      }
                  }

                  setFormData(prev => ({
                      ...prev,
                      categoria: rule.categoria || tagRuleData.categoria || prev.categoria,
                      tags: rule.tags || prev.tags,
                      prioridad: rule.prioridad || tagRuleData.prioridad || prev.prioridad,
                      es_fijo: rule.es_fijo !== undefined ? rule.es_fijo : (tagRuleData.es_fijo !== undefined ? tagRuleData.es_fijo : prev.es_fijo),
                      nota: rule.nota || tagRuleData.nota || prev.nota
                  }));
              }
          } catch (e) {
              // Ignore
          }
      };

      const timer = setTimeout(fetchRule, 500);
      return () => clearTimeout(timer);
  }, [formData.nombre_limpio, isOpen]);

  // Cargar deudores + deudas del mismo día cuando la transacción es reembolsable
  useEffect(() => {
      if (!isOpen || !transaction || !formData.es_reembolsable) return;
      let cancelled = false;
      const day = fechaDia(transaction.FECHA);
      (async () => {
          try {
              const [ds, debts] = await Promise.all([
                  deudores.length ? Promise.resolve(deudores) : api.getDeudores(),
                  api.getSupabaseDebts(day, day),
              ]);
              if (cancelled) return;
              setDeudores(ds);
              setSameDayDebts(debts);
          } catch (e) {
              // silencioso: la sección seguirá funcionando sin datos remotos
          }
      })();
      return () => { cancelled = true; };
      // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, transaction, formData.es_reembolsable]);


  const [selectedSplitIndex, setSelectedSplitIndex] = useState<number>(0);

  // Sync form data changes back to the selected split in the splits array
  useEffect(() => {
     if (isSplitting && splits.length > 0) {
         const newSplits = [...splits];
         const current = newSplits[selectedSplitIndex];
         
         // Update current split with form data
         // Only update if changes detected to avoid loops? 
         // Actually, we should update 'splits' whenever 'formData' changes
         
         const updatedSplit = {
             ...current,
             categoria: formData.categoria,
             tags: formData.tags,
             prioridad: formData.prioridad,
             es_fijo: formData.es_fijo,
             pertenece_a: formData.pertenece_a,
             es_reembolsable: formData.es_reembolsable,
             deudor: formData.deudor,
             felicidad: formData.felicidad,
             nota: formData.nota,
             nombre_limpio: formData.nombre_limpio
         };
         
         // Simple equality check to prevent infinite loops if we were syncing both ways
         if (JSON.stringify(current) !== JSON.stringify(updatedSplit)) {
             newSplits[selectedSplitIndex] = updatedSplit;
             setSplits(newSplits);
         }
     }
  }, [formData]); // Dependency on formData

  // When changing selection, populate form from that split
  useEffect(() => {
     if (isSplitting && splits[selectedSplitIndex]) {
         const s = splits[selectedSplitIndex];
         setFormData({
             nombre_limpio: s.nombre_limpio || '',
             categoria: s.categoria || '---',
             tags: s.tags || '',
             prioridad: s.prioridad || s.prioridad || '---', // Fix duplicate prop access if any
             es_fijo: s.es_fijo || false,
             pertenece_a: s.pertenece_a || '---',
             es_reembolsable: s.es_reembolsable || false,
             deudor: s.deudor || '',
             felicidad: s.felicidad || 0,
             nota: s.nota || '',
             revisado: true
         });
         setTagInput('');
     }
  }, [selectedSplitIndex, isSplitting]);


  const totalSplitAmount = splits.reduce((acc, curr) => acc + (curr.monto || 0), 0);
  const remainingAmount = Math.abs(transaction?.MONTO || 0) - totalSplitAmount;
  const isRemainingZero = Math.abs(remainingAmount) < 0.01;

  const handleAddSplit = () => {
    const newSplit: SplitItem = {
        monto: remainingAmount > 0 ? remainingAmount : 0,
        categoria: '---',
        tags: '',
        nota: '',
        nombre_limpio: ''
    };
    const newSplits = [...splits, newSplit];
    setSplits(newSplits);
    setSelectedSplitIndex(newSplits.length - 1); // Select the new one
  };
  
  const handleRemoveSplit = (e: React.MouseEvent, index: number) => {
      e.stopPropagation();
      if (splits.length <= 1) return;
      const newSplits = [...splits];
      newSplits.splice(index, 1);
      setSplits(newSplits);
      if (selectedSplitIndex >= index && selectedSplitIndex > 0) {
          setSelectedSplitIndex(selectedSplitIndex - 1);
      }
  };

  const handleClose = () => {
    setIsClosing(true);
    setTimeout(onClose, 200);
  };

  const handleSave = async () => {
    if (!transaction) return;
    
    if (isSplitting && splits.length > 1) {
        // Validation: Sum must match or warn?
        // Let's enforce it matches within a small margin
        if (Math.abs(remainingAmount) > 0.01) {
            alert(`El total dividido (${totalSplitAmount.toFixed(2)}) no coincide con el monto original (${Math.abs(transaction.MONTO).toFixed(2)})`);
            return;
        }
        
        const multiplier = transaction.MONTO < 0 ? -1 : 1;
        const processedSplits = splits.map(split => ({ 
            ...split, 
            monto: split.monto * multiplier,
            revisado: true 
        }));
        await api.splitTransaction(transaction.id, processedSplits);
        onSave(transaction.id, {}); // Trigger refresh
    } else {
        const updates: TransactionUpdate = { ...formData };

        if (formData.es_reembolsable) {
            if (debtMode === 'associate') {
                updates.deuda_id = selectedDeudaId || '';
            } else if (debtMode === 'create' && debtDeudorId) {
                // Crear deuda PENDIENTE en Supabase y vincularla
                setCreatingDebt(true);
                setDebtError('');
                try {
                    const created = await api.createSupabaseDebt({
                        titulo: (debtTitulo || formData.nombre_limpio || transaction.DESCRIPCION).trim(),
                        monto: Math.abs(debtMonto || 0),
                        deudor_id: debtDeudorId,
                        fecha_gasto: fechaDia(transaction.FECHA),
                    });
                    updates.deuda_id = String(created.id);
                } catch (e) {
                    setDebtError('No se pudo crear la deuda en Supabase. Revisa la conexión e intenta de nuevo.');
                    setCreatingDebt(false);
                    return; // aborta el guardado
                }
                setCreatingDebt(false);
            }
        } else {
            // Ya no es reembolsable: desvincular cualquier deuda previa
            updates.deuda_id = '';
        }

        onSave(transaction.id, updates);
    }
    handleClose();
  };

  const handleSaveRule = async () => {
    // ... existing logic ...
    if (!formData.nombre_limpio) return;
      setSavingRule(true);
      try {
          await api.saveEntityRule(formData.nombre_limpio, {
              categoria: formData.categoria,
              tags: formData.tags,
              prioridad: formData.prioridad,
              es_fijo: formData.es_fijo,
              nota: formData.nota
          });
          if (transaction && formData.nombre_limpio !== transaction.DESCRIPCION) {
              await api.saveMapRule(transaction.DESCRIPCION, formData.nombre_limpio);
          }
      } catch (e) {
          console.error("Failed to save rule", e);
      } finally {
          setSavingRule(false);
      }
  };

  const handleSaveTagRule = async (tag: string) => {
    if (!tag) return;
    setSavingTagRule(true);
    setShowTagSelect(false);
    try {
        await api.saveTagRule(tag, {
            categoria: formData.categoria,
            prioridad: formData.prioridad,
            es_fijo: formData.es_fijo,
            nota: formData.nota
        });
    } catch (e) {
        console.error("Failed to save tag rule", e);
    } finally {
        setSavingTagRule(false);
    }
  };

  if (!isOpen || !transaction) return null;

  // Helpers
  const isExpense = transaction.MONTO < 0;
  const currentTags = formData.tags ? formData.tags.split(',').map(t => t.trim()).filter(Boolean) : [];
  const perteneceOptions = Array.from(new Set([
    ...PERTENECE_BASE,
    ...deudores.map(d => d.nombre),
    ...(formData.pertenece_a ? [formData.pertenece_a] : []),
  ]));
  
  const addTag = async (tag: string) => {
    if (!currentTags.includes(tag)) {
      const newTags = [...currentTags, tag].join(', ');
      setFormData({ ...formData, tags: newTags });
      
      // Auto-apply Tag Rule if exists
      try {
        const rule = await api.getTagRule(tag);
        if (rule && Object.keys(rule).length > 0) {
            setFormData(prev => ({
                ...prev,
                categoria: rule.categoria || prev.categoria,
                prioridad: rule.prioridad || prev.prioridad,
                es_fijo: rule.es_fijo !== undefined ? rule.es_fijo : prev.es_fijo,
                nota: rule.nota || prev.nota
            }));
        }
      } catch (e) {
        // Tag rule doesn't exist or error, ignore
      }
    }
    setTagInput('');
    // tagInputRef.current?.focus(); // Assuming tagInputRef is defined elsewhere if needed
  };

  const removeTag = (tagToRemove: string) => {
    const newTags = currentTags.filter(t => t !== tagToRemove);
    setFormData({ ...formData, tags: newTags.join(', ') });
  };


  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center p-4 transition-all duration-200 ${isClosing ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}>
      
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" onClick={handleClose} />

      <div className={`
        relative w-full max-w-6xl max-h-[90vh] flex flex-col 
        bg-surface-950 border border-white/10 rounded-3xl shadow-2xl overflow-hidden
        transform transition-all duration-300
        ${isClosing ? 'scale-95 translate-y-4' : 'scale-100 translate-y-0'}
      `}>
        
        {/* Decorative Gradients */}
        <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-primary-500/5 rounded-full blur-[120px] pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-[600px] h-[600px] bg-emerald-500/5 rounded-full blur-[120px] pointer-events-none" />

        {/* --- Header --- */}
        <header className="flex-none px-8 py-6 border-b border-white/5 bg-surface-900/50 backdrop-blur-md flex items-center justify-between relative z-10">
          <div className="flex items-center gap-5">
            <div className={`
              w-14 h-14 rounded-2xl flex items-center justify-center text-2xl shadow-lg border border-white/5
              ${isExpense ? 'bg-rose-500/10 text-rose-500 shadow-rose-900/20' : 'bg-emerald-500/10 text-emerald-500 shadow-emerald-900/20'}
            `}>
              {isExpense ? <ArrowDownLeft className="stroke-[2.5]" /> : <ArrowUpRight className="stroke-[2.5]" />}
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                 <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest bg-surface-800 text-surface-400 border border-white/5">
                   {transaction.id.slice(0, 8)}
                 </span>
                  <span className="text-[10px] font-bold uppercase tracking-widest text-surface-500 flex items-center gap-1.5">
                    <span>{new Date(transaction.FECHA).toLocaleDateString()}</span>
                    <span className="opacity-40">•</span>
                    <span className="text-primary-400">{new Date(transaction.FECHA).toLocaleTimeString('es-EC', {hour: '2-digit', minute:'2-digit'})}</span>
                  </span>
              </div>
              <h1 className="text-xl font-bold text-white line-clamp-1 max-w-md tracking-tight">
                {transaction.DESCRIPCION}
              </h1>
            </div>
          </div>
          
          <div className="flex items-center gap-6">
             {/* Split Toggle */}
             <button 
                 onClick={() => setIsSplitting(!isSplitting)}
                 className={`
                     px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-wider border transition-all flex items-center gap-2
                     ${isSplitting 
                         ? 'bg-primary-500/20 border-primary-500/50 text-primary-300 shadow-[0_0_15px_-3px_rgba(59,130,246,0.2)]' 
                         : 'bg-surface-800 border-white/5 text-surface-400 hover:text-white hover:bg-surface-700'}
                 `}
             >
                 <div className="text-sm">✂️</div>
                 {isSplitting ? 'Modo División' : 'Dividir'}
             </button>

             <div className="w-px h-10 bg-white/5" />

             <div className="text-right">
                <div className="text-[10px] font-bold uppercase tracking-wider text-surface-500 mb-0.5">Monto Total</div>
                <div className={`text-4xl font-mono font-medium tracking-tighter ${isExpense ? 'text-white' : 'text-emerald-400'}`}>
                  {isExpense ? '-' : '+'}${Math.abs(transaction.MONTO).toFixed(2)}
                </div>
             </div>
             <button onClick={handleClose} className="p-2.5 rounded-xl bg-surface-800 hover:bg-surface-700 text-surface-400 hover:text-white transition-colors border border-white/5">
               <X size={20} />
             </button>
          </div>
        </header>

        {/* --- Body: The Grid --- */}
        <div className="flex-1 flex overflow-hidden relative z-10">
            
            {/* --- LEFT SIDEBAR (Only visible in Split Mode) --- */}
            {isSplitting && (
                <div className="w-80 bg-surface-900/30 border-r border-white/5 flex flex-col animate-slide-in-left">
                    <div className="p-4 border-b border-white/5 bg-surface-900/50">
                        <div className="flex justify-between items-center mb-2">
                             <div className="text-xs font-bold uppercase tracking-wider text-surface-400">Items</div>
                             <div className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${isRemainingZero ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'}`}>
                                 Restan: ${remainingAmount.toFixed(2)}
                             </div>
                        </div>
                    </div>
                    
                    <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
                        {splits.map((split, i) => (
                            <div 
                                key={i}
                                onClick={() => setSelectedSplitIndex(i)}
                                className={`
                                    p-3 rounded-xl border cursor-pointer transition-all hover:scale-[1.02] active:scale-[0.98] group relative
                                    ${i === selectedSplitIndex 
                                        ? 'bg-primary-500/10 border-primary-500/30 shadow-lg shadow-primary-900/20' 
                                        : 'bg-surface-800/40 border-white/5 hover:bg-surface-800 hover:border-white/10'}
                                `}
                            >
                                <div className="flex justify-between items-start mb-1">
                                    <div className={`font-bold text-sm ${i === selectedSplitIndex ? 'text-white' : 'text-surface-300'}`}>
                                        {split.nombre_limpio || '(Sin nombre)'}
                                    </div>
                                    <button 
                                        onClick={(e) => handleRemoveSplit(e, i)}
                                        className="text-surface-600 hover:text-rose-400 transition-colors opacity-0 group-hover:opacity-100 p-0.5"
                                    >
                                        <X size={12} />
                                    </button>
                                </div>
                                
                                <div className="flex justify-between items-center">
                                    <div className="text-[10px] text-surface-500 uppercase tracking-wider truncate max-w-[100px]">{split.categoria}</div>
                                    
                                    {/* Editable Amount directly in list? No, keep master-detail clean. Just display. */}
                                    {/* Actually, amount is critical, lets allow editing here OR show it big on right. */}
                                    {/* Let's show it here as display but editable on right */}
                                    <div className="font-mono text-sm font-bold text-surface-200">
                                        ${(split.monto || 0).toFixed(2)}
                                    </div>
                                </div>
                            </div>
                        ))}
                        
                        <button 
                            onClick={handleAddSplit}
                            className="w-full py-3 border border-dashed border-white/10 rounded-xl text-surface-500 hover:text-white hover:border-white/20 hover:bg-white/5 transition-all text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2"
                        >
                            <div className="p-0.5 rounded bg-surface-800"><ArrowDownLeft size={10} /></div>
                            Agregar
                        </button>
                    </div>
                </div>
            )}


            {/* --- RIGHT CONTENT (Main Form) --- */}
            <div className="flex-1 overflow-y-auto p-8 custom-scrollbar bg-surface-950/50">
              
              {isSplitting && (
                  <div className="mb-6 flex justify-between items-end border-b border-white/5 pb-6">
                      <div>
                          <h2 className="text-lg font-bold text-white mb-1">
                             Editando: <span className="text-primary-400">{formData.nombre_limpio || 'Nueva Parte'}</span>
                          </h2>
                          <div className="text-xs text-surface-500">Configura los detalles para esta porción de la transacción.</div>
                      </div>
                      <div className="flex flex-col items-end">
                           <label className="text-[10px] font-bold uppercase tracking-wider text-surface-500 mb-1">Monto Asignado</label>
                           <div className="relative">
                               <input 
                                  type="number" 
                                  step="0.01"
                                  value={splits[selectedSplitIndex]?.monto || 0}
                                  onChange={(e) => {
                                      const val = parseFloat(e.target.value) || 0;
                                      const newSplits = [...splits];
                                      newSplits[selectedSplitIndex] = { ...newSplits[selectedSplitIndex], monto: val };
                                      setSplits(newSplits);
                                  }}
                                  className="w-40 bg-surface-900 border border-white/10 rounded-xl px-4 py-2 text-right font-mono text-2xl font-bold text-white focus:outline-none focus:border-primary-500/50"
                               />
                               <span className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500">$</span>
                           </div>
                      </div>
                  </div>
              )}

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-full">

                {/* --- LEFT COLUMN: Context (Identity, Category, Tags) --- */}
                <div className="space-y-6 flex flex-col h-full">
                  
                  <section className="space-y-6">
                    <SectionLabel icon={Sparkles} label="Identidad & Clasificación" />
                    
                    {/* Name Input */}
                    <div className="group space-y-2">
                      <label className="text-xs text-primary-200/60 font-medium ml-1">Nombre Comercial</label>
                      <ConsoleInput 
                        value={formData.nombre_limpio || ''} 
                        onChange={e => setFormData({...formData, nombre_limpio: e.target.value})}
                        placeholder="Ej: Netflix, Uber..."
                        className="text-lg font-medium bg-surface-800/50 border-white/5 focus:border-primary-500/50 h-14"
                        autoFocus={!isSplitting} // Don't autofocus if just switching tabs
                      />
                    </div>
                    
                    {/* Grouped Category & Tags */}
                    <div className="bg-surface-800/30 border border-white/5 rounded-2xl p-4 space-y-4 shadow-sm">
                       {/* Category Select */}
                       <div className="space-y-2">
                         <label className="text-xs text-primary-200/60 font-medium ml-1 flex items-center gap-2">
                           <Tag size={12} /> Categoría
                         </label>
                         <ConsoleSelect 
                            value={formData.categoria || '---'} 
                            onChange={val => {
                              const updates: any = { categoria: val };
                              if (val.toLowerCase() === 'regalo') {
                                updates.prioridad = 'Deseo';
                              }
                              setFormData(prev => ({ ...prev, ...updates }));
                            }}
                            options={CATEGORY_OPTIONS}
                            icon={Tag}
                         />
                       </div>
    
                       {/* Tags (Expanded UX) */}
                       <div className="space-y-2 relative z-20">
                         <label className="text-xs text-primary-200/60 font-medium ml-1 flex items-center gap-2">
                           <Tag size={12} /> Etiquetas
                         </label>
                         <div className="bg-surface-900/50 border border-white/5 rounded-xl p-3 min-h-[80px] focus-within:ring-1 focus-within:ring-primary-500/30 focus-within:border-primary-500/30 transition-all cursor-text" onClick={() => tagInputRef.current?.focus()}>
                            <div className="flex flex-wrap gap-2">
                               {currentTags.map(tag => (
                                 <span key={tag} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-500/20 border border-primary-500/30 text-primary-100 text-xs font-bold uppercase tracking-wider shadow-sm animate-fade-in group/tag">
                                   {tag}
                                   <button 
                                     onClick={(e) => { e.stopPropagation(); removeTag(tag); }}
                                     className="text-primary-300 hover:text-white transition-colors p-0.5 rounded-md hover:bg-primary-500/20"
                                   >
                                     <X size={12} />
                                   </button>
                                 </span>
                               ))}
                               <input
                                 ref={tagInputRef}
                                 type="text"
                                 className="flex-1 min-w-[150px] bg-transparent border-none text-sm text-white focus:ring-0 placeholder:text-surface-600 p-1.5 h-8"
                                 placeholder={currentTags.length === 0 ? "Escribe para buscar o crear..." : "..."}
                                 value={tagInput}
                                 onChange={(e) => setTagInput(e.target.value)}
                                 onKeyDown={(e) => {
                                   if (e.key === 'Enter' && tagInput.trim()) {
                                     e.preventDefault();
                                     addTag(tagInput.trim());
                                   }
                                   if (e.key === 'Backspace' && !tagInput && currentTags.length > 0) {
                                     removeTag(currentTags[currentTags.length - 1]);
                                   }
                                 }}
                               />
                            </div>
                         </div>
                         
                         {/* Tag Suggestions Dropdown */}
                         {tagInput && (
                             <div className="absolute left-0 right-0 top-full mt-2 bg-surface-900 border border-white/10 rounded-xl shadow-2xl max-h-60 overflow-y-auto z-50 custom-scrollbar divide-y divide-white/5">
                               {existingTags.filter(t => t.toLowerCase().includes(tagInput.toLowerCase()) && !currentTags.includes(t)).map(tag => (
                                 <button
                                   key={tag}
                                   onClick={() => addTag(tag)}
                                   className="w-full text-left px-4 py-3 text-sm font-medium text-surface-300 hover:bg-surface-800 hover:text-white transition-colors flex items-center justify-between group"
                                 >
                                   <span>{tag}</span>
                                   <span className="text-[10px] text-surface-600 group-hover:text-surface-400 uppercase tracking-widest">Existente</span>
                                 </button>
                               ))}
                               {existingTags.filter(t => t.toLowerCase().includes(tagInput.toLowerCase()) && !currentTags.includes(t)).length === 0 && (
                                  <button 
                                    onClick={() => addTag(tagInput.trim())}
                                    className="w-full text-left px-4 py-3 text-sm font-medium text-primary-300 hover:bg-surface-800 hover:text-primary-200 transition-colors flex items-center gap-2"
                                  >
                                    <div className="p-1 rounded bg-primary-500/20"><Tag size={12} /></div>
                                    Crear nueva etiqueta: <span className="text-white font-bold">"{tagInput}"</span>
                                  </button>
                               )}
                             </div>
                          )}
                       </div>
                    </div>
    
                    {/* Notes Input */}
                    <div className="space-y-2">
                       <label className="text-xs text-primary-200/60 font-medium ml-1 flex items-center gap-2">
                          <StickyNote size={12} /> Notas
                       </label>
                       <div className="bg-surface-800/30 border border-white/5 rounded-2xl p-0 shadow-inner overflow-hidden focus-within:border-primary-500/30 transition-colors">
                         <textarea
                           value={formData.nota || ''}
                           onChange={e => setFormData({...formData, nota: e.target.value})}
                           className="w-full bg-transparent text-sm text-white/90 placeholder:text-surface-600 resize-none focus:outline-none min-h-[120px] p-4 leading-relaxed"
                           placeholder="Detalles adicionales de la transacción..."
                         />
                       </div>
                    </div>
                  </section>
    
                </div>
    
                {/* --- RIGHT COLUMN: Properties & Accounting --- */}
                <div className="flex flex-col gap-6 h-full"> 
                  
                  {/* Properties Card */}
                  <div className="bg-surface-800/20 border border-white/5 rounded-3xl p-6 space-y-6">
                     <SectionLabel icon={Flame} label="Propiedades" />
    
                     {/* Priority + Fixed Grid */}
                     <div className="grid grid-cols-2 gap-4">
                        {/* Priority Section */}
                        <div className="col-span-1 flex flex-col gap-3">
                           <label className="text-xs text-primary-200/60 font-medium ml-1">Prioridad</label>
                           <div className="flex flex-col gap-2 h-full">
                               <button
                                 onClick={() => setFormData({...formData, prioridad: 'Necesidad'})}
                                 className={`
                                   flex items-center gap-3 px-4 py-3 rounded-xl border transition-all text-left group flex-1
                                   ${formData.prioridad === 'Necesidad' 
                                     ? 'bg-amber-500/10 border-amber-500/40 text-amber-200 shadow-[0_0_15px_-3px_rgba(245,158,11,0.15)]' 
                                     : 'bg-surface-900 border-white/5 text-surface-400 hover:border-white/10 hover:text-surface-200'}
                                 `}
                               >
                                 <Flame size={18} className={formData.prioridad === 'Necesidad' ? 'fill-current text-amber-400' : 'text-surface-600'} />
                                 <span className="text-xs font-bold uppercase tracking-wider">Necesidad</span>
                               </button>
                               <button
                                 onClick={() => setFormData({...formData, prioridad: 'Deseo'})}
                                 className={`
                                   flex items-center gap-3 px-4 py-3 rounded-xl border transition-all text-left group flex-1
                                   ${formData.prioridad === 'Deseo' 
                                     ? 'bg-pink-500/10 border-pink-500/40 text-pink-200 shadow-[0_0_15px_-3px_rgba(236,72,153,0.15)]' 
                                     : 'bg-surface-900 border-white/5 text-surface-400 hover:border-white/10 hover:text-surface-200'}
                                 `}
                               >
                                 <Heart size={18} className={formData.prioridad === 'Deseo' ? 'fill-current text-pink-400' : 'text-surface-600'} />
                                 <span className="text-xs font-bold uppercase tracking-wider">Deseo</span>
                               </button>
                           </div>
                        </div>
    
                        {/* Fixed Recurrence Section */}
                        <div className="col-span-1 flex flex-col gap-3">
                           <label className="text-xs text-primary-200/60 font-medium ml-1">Recurrencia</label>
                           <div 
                              className={`
                                h-full p-4 rounded-xl border flex flex-col justify-between cursor-pointer transition-all group
                                ${formData.es_fijo 
                                  ? 'bg-blue-500/10 border-blue-500/40 shadow-[0_0_15px_-3px_rgba(59,130,246,0.15)]' 
                                  : 'bg-surface-900 border-white/5 hover:border-white/10'}
                              `}
                              onClick={() => setFormData({...formData, es_fijo: !formData.es_fijo})}
                           >
                              <div className="flex justify-between items-start">
                                 <DollarSign size={20} className={formData.es_fijo ? 'text-blue-400' : 'text-surface-600'} />
                                 <div className={`w-10 h-6 rounded-full relative transition-colors ${formData.es_fijo ? 'bg-blue-500' : 'bg-white/10'}`}>
                                   <div className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${formData.es_fijo ? 'translate-x-4' : 'translate-x-0'}`} />
                                 </div>
                              </div>
                              <div>
                                <div className={`text-sm font-bold ${formData.es_fijo ? 'text-blue-200' : 'text-surface-400'}`}>Gasto Fijo</div>
                                <div className="text-[10px] text-surface-500 leading-tight mt-1">Se repite cada mes</div>
                              </div>
                           </div>
                        </div>
                     </div>
    
                     {/* Happiness Slider */}
                     <div className="space-y-3 pt-2">
                        <div className="flex items-center justify-between group/hap text-primary-200/60 font-medium ml-1">
                           <label className="text-xs flex items-center gap-1 cursor-help relative">
                             Felicidad 
                             <AlertCircle size={10} className="text-surface-500" />
                             <span className="opacity-0 group-hover/hap:opacity-100 transition-opacity absolute top-6 left-0 bg-surface-800 text-surface-200 text-xs px-3 py-2 rounded-xl border border-white/10 w-48 shadow-2xl pointer-events-none z-10 font-normal normal-case tracking-normal">
                               <strong className="text-white block mb-0.5">Felicidad Absoluta</strong>
                               Etiqueta SIN tener en cuenta el costo o precio.
                             </span>
                           </label>
                           <span className="text-xs font-mono font-bold text-surface-400 bg-white/5 px-2 py-0.5 rounded">{formData.felicidad}/9</span>
                        </div>
                        <div className="bg-surface-900 rounded-xl p-4 border border-white/5">
                           <input
                             type="range"
                             min="0" max="9" step="1"
                             value={formData.felicidad || 0}
                             onChange={(e) => setFormData({...formData, felicidad: parseInt(e.target.value)})}
                             className={`
                                w-full h-2 rounded-full appearance-none cursor-pointer transition-all mb-3
                                ${(formData.felicidad || 0) >= 6 ? 'bg-emerald-500/20 accent-emerald-500' : 
                                  (formData.felicidad || 0) === 5 ? 'bg-surface-600/20 accent-surface-500' :
                                  (formData.felicidad || 0) > 0 ? 'bg-rose-500/20 accent-rose-500' : 'bg-white/10 accent-surface-400'}
                             `}
                           />
                           <div className="flex justify-between text-[10px] uppercase font-bold tracking-widest mt-2">
                              {/* 1-4 */}
                              <div className="flex flex-col items-start gap-1 w-24 text-rose-400/80">
                                <span className="flex items-center gap-1"><Frown size={12}/> 1-4</span>
                                <span className="text-[8px] leading-tight normal-case font-medium text-surface-500">Arrepentimiento</span>
                              </div>
                              {/* 5 */}
                              <div className="flex flex-col items-center gap-1 w-24 text-surface-400">
                                <span className="flex items-center gap-1"><Meh size={12}/> 5</span>
                                <span className="text-[8px] leading-tight normal-case font-medium text-surface-500 text-center">Neutro</span>
                              </div>
                              {/* 6-9 */}
                              <div className="flex flex-col items-end gap-1 w-24 text-emerald-400/80 text-right">
                                <span className="flex items-center gap-1"><Heart size={12}/> 6-9</span>
                                <span className="text-[8px] leading-tight normal-case font-medium text-surface-500">Agrega Valor</span>
                              </div>
                           </div>
                        </div>
                     </div>
                  </div>
    
                  {/* Accounting Card (Bottom, Collapsible) - MOVED & STYLED */}
                  <div className={`
                     bg-surface-800/20 border border-white/5 rounded-3xl overflow-hidden transition-all duration-300
                     ${formData.es_reembolsable ? 'border-purple-500/30 bg-purple-500/5' : 'hover:border-white/10'}
                  `}>
                      <div 
                        className="p-5 flex items-center justify-between cursor-pointer group"
                        onClick={() => setFormData({...formData, es_reembolsable: !formData.es_reembolsable})}
                      >
                         <div className="flex items-center gap-3">
                            <div className={`p-2 rounded-lg ${formData.es_reembolsable ? 'bg-purple-500/20 text-purple-300' : 'bg-surface-800 text-surface-500'}`}>
                               <CreditCard size={20} />
                            </div>
                            <div>
                               <div className={`text-sm font-bold ${formData.es_reembolsable ? 'text-purple-200' : 'text-surface-300'}`}>Reembolsable / Deuda</div>
                               <div className="text-[10px] text-surface-500">Compartido con otros</div>
                            </div>
                         </div>
                         <div className={`w-12 h-7 rounded-full relative transition-colors border border-white/5 ${formData.es_reembolsable ? 'bg-purple-600 border-purple-500/50' : 'bg-surface-900'}`}>
                            <div className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform shadow-sm ${formData.es_reembolsable ? 'translate-x-5' : 'translate-x-0'}`} />
                         </div>
                      </div>
    
                      {/* Expanded Content */}
                      <div className={`
                         px-5 pb-5 transition-all duration-300 ease-in-out space-y-4
                         ${formData.es_reembolsable ? 'max-h-[720px] opacity-100 overflow-y-auto custom-scrollbar' : 'max-h-0 opacity-0 overflow-hidden pb-0'}
                      `}>
                         <div className="h-px bg-purple-500/20 w-full mb-4" />

                         {/* ¿De quién es? / ¿Quién paga? */}
                         <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                               <label className="text-[10px] uppercase font-bold text-purple-300/70 ml-1">¿De quién es?</label>
                               <ConsoleSelect
                                  value={formData.pertenece_a || '---'}
                                  onChange={val => setFormData({...formData, pertenece_a: val})}
                                  options={perteneceOptions}
                                  icon={User}
                               />
                            </div>
                            <div className="space-y-1.5">
                               <label className="text-[10px] uppercase font-bold text-purple-300/70 ml-1 flex items-center gap-1">
                                  ¿Quién paga? <span className="text-purple-400/50 normal-case">(deudor Supabase)</span>
                               </label>
                               <div className="relative group">
                                  <select
                                     value={debtDeudorId}
                                     onChange={(e) => {
                                        const id = e.target.value;
                                        setDebtDeudorId(id);
                                        const d = deudores.find(x => String(x.id) === id);
                                        setFormData(prev => ({ ...prev, deudor: d ? d.nombre : '' }));
                                     }}
                                     className="w-full appearance-none bg-surface-900 border border-white/5 rounded-xl px-4 py-3.5 pr-10 text-surface-50 font-medium focus:outline-none focus:border-purple-500/50 focus:bg-surface-800 cursor-pointer transition-all hover:border-white/20 shadow-[inset_0_2px_4px_rgba(0,0,0,0.3)]"
                                  >
                                     <option value="">{deudores.length ? '— Selecciona —' : 'Cargando…'}</option>
                                     {deudores.map(d => (
                                        <option key={d.id} value={String(d.id)}>{d.nombre}</option>
                                     ))}
                                  </select>
                                  <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-surface-500">
                                     <CreditCard size={16} />
                                  </div>
                               </div>
                            </div>
                         </div>

                         {/* Modo: asociar deuda del mismo día / crear nueva */}
                         <div className="space-y-2">
                            <label className="text-[10px] uppercase font-bold text-purple-300/70 ml-1">Deuda en Supabase</label>
                            <div className="flex gap-2">
                               <button
                                  type="button"
                                  onClick={() => setDebtMode('create')}
                                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all ${debtMode === 'create' ? 'bg-purple-500/15 border-purple-500/40 text-purple-200' : 'bg-surface-900 border-white/5 text-surface-400 hover:text-white'}`}
                               >
                                  <Plus size={14} /> Crear nueva
                               </button>
                               <button
                                  type="button"
                                  onClick={() => setDebtMode('associate')}
                                  disabled={sameDayDebts.length === 0}
                                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-40 disabled:cursor-not-allowed ${debtMode === 'associate' ? 'bg-purple-500/15 border-purple-500/40 text-purple-200' : 'bg-surface-900 border-white/5 text-surface-400 hover:text-white'}`}
                               >
                                  <Link2 size={14} /> Asociar existente
                                  {sameDayDebts.length > 0 && <span className="px-1.5 py-0.5 rounded bg-purple-500/20 text-[9px]">{sameDayDebts.length}</span>}
                               </button>
                            </div>
                         </div>

                         {debtMode === 'associate' ? (
                            <div className="space-y-2">
                               <div className="text-[10px] text-surface-500 ml-1">Deudas del {fechaDia(transaction.FECHA)}</div>
                               {sameDayDebts.length === 0 ? (
                                  <div className="text-xs text-surface-500 bg-surface-900/50 border border-dashed border-white/10 rounded-xl px-4 py-3 text-center">
                                     No hay deudas registradas ese día
                                  </div>
                               ) : (
                                  <div className="space-y-2 max-h-44 overflow-y-auto custom-scrollbar pr-1">
                                     {sameDayDebts.map(d => {
                                        const active = selectedDeudaId === String(d.ID);
                                        return (
                                           <button
                                              type="button"
                                              key={String(d.ID)}
                                              onClick={() => {
                                                 setSelectedDeudaId(String(d.ID));
                                                 setFormData(prev => ({ ...prev, deudor: d.DEUDOR_NOMBRE || prev.deudor }));
                                              }}
                                              className={`w-full flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-xl border text-left transition-all ${active ? 'bg-purple-500/15 border-purple-500/50' : 'bg-surface-900 border-white/5 hover:border-white/15'}`}
                                           >
                                              <div className="min-w-0">
                                                 <div className="text-sm font-bold text-surface-100 truncate">{d.DESCRIPCION}</div>
                                                 <div className="text-[10px] text-surface-500 flex items-center gap-2">
                                                    <span className="text-sky-300">{d.DEUDOR_NOMBRE}</span>
                                                    <span className={d.PAGADA ? 'text-emerald-400' : 'text-rose-400'}>{d.PAGADA ? 'PAGADA' : 'PENDIENTE'}</span>
                                                 </div>
                                              </div>
                                              <div className="flex items-center gap-2 shrink-0">
                                                 <span className="font-mono font-bold text-white text-sm">${d.MONTO.toFixed(2)}</span>
                                                 {active && <CheckCircle2 size={16} className="text-purple-300" />}
                                              </div>
                                           </button>
                                        );
                                     })}
                                  </div>
                               )}
                            </div>
                         ) : (
                            <div className="grid grid-cols-2 gap-4">
                               <div className="space-y-1.5">
                                  <label className="text-[10px] uppercase font-bold text-purple-300/70 ml-1">Nombre de la deuda</label>
                                  <ConsoleInput
                                     value={debtTitulo}
                                     onChange={e => setDebtTitulo(e.target.value)}
                                     placeholder="Ej: 4 almuerzos"
                                  />
                               </div>
                               <div className="space-y-1.5">
                                  <label className="text-[10px] uppercase font-bold text-purple-300/70 ml-1 flex items-center gap-1">
                                     Monto <span className="text-purple-400/50 normal-case">(diferido si aplica)</span>
                                  </label>
                                  <div className="relative">
                                     <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-surface-500">$</span>
                                     <input
                                        type="number"
                                        step="0.01"
                                        value={debtMonto}
                                        onChange={e => setDebtMonto(parseFloat(e.target.value) || 0)}
                                        className="w-full bg-surface-900 border border-white/5 rounded-xl pl-8 pr-4 py-3.5 text-surface-50 font-mono font-bold focus:outline-none focus:border-purple-500/50 focus:bg-surface-800 shadow-[inset_0_2px_4px_rgba(0,0,0,0.3)] transition-all"
                                     />
                                  </div>
                               </div>
                               {!debtDeudorId && (
                                  <div className="col-span-2 text-[11px] text-amber-300/80 flex items-center gap-1.5">
                                     <AlertCircle size={12} /> Elige "¿Quién paga?" para crear la deuda al guardar.
                                  </div>
                               )}
                            </div>
                         )}

                         {debtError && (
                            <div className="text-xs text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-xl px-3 py-2 flex items-center gap-2">
                               <AlertCircle size={14} /> {debtError}
                            </div>
                         )}
                      </div>
                  </div>
    
                </div>
              </div>
            </div>
        </div>


        {/* --- Footer --- */}
        <div className="flex-none p-6 border-t border-white/5 bg-surface-900/50 backdrop-blur-md flex justify-between gap-4 z-20">
          <div className="flex gap-2 relative">
            {!isSplitting && (
               <>
                 <button
                    type="button"
                    onClick={handleSaveRule}
                    disabled={savingRule}
                    className="px-4 py-3.5 rounded-xl text-xs font-bold uppercase tracking-wider text-surface-500 hover:text-white hover:bg-white/5 transition-colors border border-transparent hover:border-white/5 flex items-center gap-2"
                    title="Guardar como regla por Nombre para futuras transacciones"
                 >
                    <Save size={16} className={savingRule ? 'animate-spin' : ''} />
                    {savingRule ? 'Guardando...' : 'Guardar Regla (Nombre)'}
                 </button>
                 
                 <button
                    type="button"
                    onClick={() => {
                        if (currentTags.length === 1) {
                            handleSaveTagRule(currentTags[0]);
                        } else if (currentTags.length > 1) {
                            setShowTagSelect(!showTagSelect);
                        }
                    }}
                    disabled={savingTagRule || currentTags.length === 0}
                    className={`px-4 py-3.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-colors border border-transparent flex items-center gap-2 ${currentTags.length > 0 ? 'text-surface-500 hover:text-white hover:bg-white/5 hover:border-white/5' : 'text-surface-700 cursor-not-allowed hidden md:flex'}`}
                    title="Guardar como regla por Etiqueta"
                 >
                    <Tag size={16} className={savingTagRule ? 'animate-spin' : ''} />
                    {savingTagRule ? 'Guardando...' : 'Guardar Regla (Tag)'}
                 </button>

                 {showTagSelect && currentTags.length > 1 && (
                     <div className="absolute left-full ml-2 bottom-0 mb-14 bg-surface-900 border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50 flex flex-col w-48">
                         <div className="px-3 py-2 text-[10px] uppercase font-bold tracking-wider text-surface-500 border-b border-white/5">
                             Selecciona el Tag
                         </div>
                         {currentTags.map(tag => (
                             <button
                                 key={tag}
                                 onClick={() => handleSaveTagRule(tag)}
                                 className="px-4 py-3 text-sm text-left font-bold text-primary-300 hover:bg-surface-800 hover:text-white transition-colors"
                             >
                                 {tag}
                             </button>
                         ))}
                     </div>
                 )}
               </>
            )}
          </div>
          <div className="flex gap-4">
              <button
                onClick={handleClose}
                className="px-6 py-3.5 rounded-xl text-xs font-bold uppercase tracking-wider text-surface-500 hover:text-white hover:bg-white/5 transition-colors border border-transparent hover:border-white/5"
              >
                Cancelar
              </button>
              <button
                onClick={handleSave}
                disabled={creatingDebt}
                className="
                  px-8 py-3.5 rounded-xl text-sm font-bold text-white
                  bg-gradient-to-r from-primary-600 to-primary-500
                  hover:from-primary-500 hover:to-primary-400
                  shadow-lg shadow-primary-600/50
                  hover:shadow-xl hover:shadow-primary-500/60
                  transform active:scale-[0.98] transition-all
                  flex items-center gap-2 border border-white/10
                  disabled:opacity-60 disabled:cursor-not-allowed
                "
              >
                {creatingDebt ? <Loader2 size={18} className="animate-spin" /> : <Check size={18} className="stroke-[3]" />}
                <span className="uppercase tracking-wider">
                  {creatingDebt ? 'Creando deuda…' : `Guardar ${isSplitting ? 'Divisiones' : 'Cambios'}`}
                </span>
              </button>
          </div>
        </div>

      </div>
    </div>
  );
}
