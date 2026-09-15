import { useState, useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Transaction, TransactionUpdate, api, SplitItem, SupabaseDebt, SupabaseDeudor, SupabasePayment, PaymentPreview } from '../services/api';
import {
  X, Tag, ArrowUpRight, ArrowDownLeft, Check,
  CreditCard, Flame, Heart, Sparkles, User,
  Frown, Meh, DollarSign, StickyNote, Save, AlertCircle,
  Link2, Plus, CheckCircle2, Loader2, Search, Users,
  HandCoins, Wallet, Unlink, Ban, Scissors, Settings2, Clock, Banknote
} from 'lucide-react';
import { money } from '../utils/format';
import { parseTags } from '../utils/tags';
import { nuevaIdemKey } from '../utils/requests';

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

/**
 * Hora real del movimiento ('HH:MM'), o null si no se conoce.
 *
 * FECHA por sí sola NO sirve: para TARJETA el extracto no trae hora y la fila
 * queda a medianoche. La hora del consumo vive en la columna HORA, que el
 * backend arma en _attach_horas() a partir de los correos de notificación
 * (horas_tarjeta.csv) para tarjeta y del propio FECHA para banca.
 *
 * Devuelve null en vez de '00:00' cuando no hay hora: preferimos no mostrar
 * nada antes que inventar una medianoche, igual que TransactionTable.
 */
const horaEfectiva = (t: Transaction): string | null => {
  if (t.HORA && t.HORA.trim() !== '') return t.HORA.trim().slice(0, 5);
  const desdeFecha = (t.FECHA || '').slice(11, 16);
  return desdeFecha && desdeFecha !== '00:00' ? desdeFecha : null;
};

/**
 * Enlace al visor unificado (proyecto `informacion`) apuntando al momento del gasto.
 *
 * El visor lee `from`/`to` (día) y `hf`/`ht` (franja horaria, enteros 0-23) desde
 * la URL, y su vista Momento coloca el puntero del reloj en el CENTRO de esa
 * franja. Sin `hf`/`ht` la franja es el día entero y el puntero cae siempre a las
 * 12:00, que es la razón por la que el botón "no llevaba a la hora correcta".
 *
 * Mandando hf = ht = la hora del consumo, el puntero cae en HH:30: la franja
 * resaltada es la correcta y el desfase máximo es de media hora, que el propio
 * visor deja ajustar. Si no conocemos la hora seguimos abriendo el día completo.
 */
const urlRecordarMomento = (t: Transaction): string => {
  const dia = fechaDia(t.FECHA);
  const params = new URLSearchParams({ mode: 'recordar', view: 'momento', from: dia, to: dia });
  const hora = horaEfectiva(t);
  if (hora) {
    const h = String(parseInt(hora.slice(0, 2), 10));
    params.set('hf', h);
    params.set('ht', h);
  }
  return `http://localhost:5273/?${params.toString()}`;
};

/**
 * Cómo se registra esta transacción reembolsable en el sistema de deudas:
 *  - `create`    → nace una deuda nueva en Supabase al guardar.
 *  - `associate` → se engancha a una deuda que ya existe.
 *  - `none`      → solo se marca como reembolsable, sin deuda que la respalde.
 */
type DebtLinkMode = 'none' | 'create' | 'associate';

/** Qué es la transacción para el sistema de deudas: nace o salda una cuenta. */
type DebtKind = 'deuda' | 'pago';

/** Un pago siempre existe en Supabase: o se engancha a uno registrado o se registra. */
type PagoLinkMode = 'associate' | 'create';

interface DebtDraft {
  kind: DebtKind;
  mode: DebtLinkMode;
  deudorId: string;
  titulo: string;
  monto: number;
  /** true = tú debes (pagaron por ti); false = te deben (pagaste tú). */
  esMiDeuda: boolean;
  /** Deuda vinculada (la existente al abrir, o la elegida en modo `associate`). */
  deudaId: string;
  pagoMode: PagoLinkMode;
  /** Pago vinculado (el existente al abrir, o el elegido en modo `associate`). */
  pagoId: string;
  pagoMonto: number;
  /** true = pagaste tú; false = te pagaron. */
  esMiPago: boolean;
  /** Deudas a las que va el pago nuevo. Vacío = reparto automático. */
  pagoDeudasIds: string[];
  /** Idempotencia: el mismo borrador guardado dos veces no registra dos pagos. */
  idemKey: string;
}

/**
 * `esIngreso` sugiere el tipo cuando no hay vínculo: a un ingreso casi siempre lo
 * explica alguien que te paga, a un gasto una deuda. `yaReembolsable` conserva lo que
 * ya estaba marcado antes de que existieran los pagos: eso era una deuda.
 */
const nuevoDraft = (
  titulo: string, monto: number, esIngreso: boolean,
  deudaId = '', pagoId = '', yaReembolsable = false,
): DebtDraft => ({
  kind: deudaId ? 'deuda' : pagoId ? 'pago' : (esIngreso && !yaReembolsable ? 'pago' : 'deuda'),
  mode: deudaId ? 'associate' : 'create',
  deudorId: '',
  titulo,
  monto: Math.abs(monto),
  esMiDeuda: esIngreso,
  deudaId,
  pagoMode: 'associate',
  pagoId,
  pagoMonto: Math.abs(monto),
  esMiPago: !esIngreso,
  pagoDeudasIds: [],
  idemKey: nuevaIdemKey(),
});

/** Lo que una parte deja escrito en sus etiquetas: nunca las dos cosas a la vez. */
interface VinculoDeudas { deuda_id: string; pago_id: string }
const SIN_VINCULO: VinculoDeudas = { deuda_id: '', pago_id: '' };

// --- Subcomponents for "Control Console" Look ---

/** Encabezado numerado de los pasos de la sección de reembolso. */
const StepLabel = ({ n, title, hint }: { n: number; title: string; hint?: string }) => (
  <div className="flex items-start gap-2.5">
    <div className="w-5 h-5 rounded-md bg-purple-500/20 border border-purple-500/30 text-purple-200 text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
      {n}
    </div>
    <div className="min-w-0">
      <div className="text-xs font-bold text-purple-100 uppercase tracking-wider">{title}</div>
      {hint && <div className="text-[10px] text-surface-500 leading-tight mt-0.5">{hint}</div>}
    </div>
  </div>
);

/** Select con buscador: mismo aspecto que ConsoleSelect pero filtrando la lista. */
const SearchableSelect = ({ value, onChange, options, icon: Icon, placeholder = 'Buscar…' }: {
  value: string;
  onChange: (val: string) => void;
  options: string[];
  icon?: any;
  placeholder?: string;
}) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const filtered = options.filter(o => o.toLowerCase().includes(query.trim().toLowerCase()));

  const close = () => { setOpen(false); setQuery(''); };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => (open ? close() : setOpen(true))}
        className="
          w-full flex items-center justify-between gap-2 bg-surface-900 border border-white/5 rounded-xl px-4 py-3.5
          text-surface-50 font-medium text-left
          focus:outline-none focus:border-purple-500/50
          shadow-[inset_0_2px_4px_rgba(0,0,0,0.3)] hover:border-white/20 transition-all
        "
      >
        <span className={value && value !== '---' ? '' : 'text-surface-500'}>{value || '---'}</span>
        {Icon ? <Icon size={16} className="text-surface-500 shrink-0" /> : null}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={close} />
          <div className="absolute z-40 left-0 right-0 mt-2 bg-surface-900 border border-white/10 rounded-xl shadow-2xl overflow-hidden">
            <div className="relative border-b border-white/5">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" />
              <input
                autoFocus
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder={placeholder}
                className="w-full bg-transparent pl-8 pr-3 py-2.5 text-sm text-white placeholder:text-surface-600 focus:outline-none"
              />
            </div>
            <div className="max-h-52 overflow-y-auto custom-scrollbar">
              {filtered.map(opt => (
                <button
                  type="button"
                  key={opt}
                  onClick={() => { onChange(opt); close(); }}
                  className={`w-full flex items-center justify-between gap-2 px-4 py-2.5 text-sm text-left transition-colors ${
                    opt === value ? 'bg-purple-500/15 text-purple-100 font-bold' : 'text-surface-300 hover:bg-surface-800 hover:text-white'
                  }`}
                >
                  <span className="truncate">{opt}</span>
                  {opt === value && <Check size={14} className="text-purple-300 shrink-0" />}
                </button>
              ))}
              {filtered.length === 0 && (
                <div className="px-4 py-3 text-xs text-surface-500 text-center">Nadie coincide</div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

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
  const [nearbyDebts, setNearbyDebts] = useState<SupabaseDebt[]>([]);
  const [loadingDebts, setLoadingDebts] = useState(false);
  /** Un borrador de deuda por parte: en modo normal solo existe el índice 0. */
  const [debtDrafts, setDebtDrafts] = useState<DebtDraft[]>([]);
  const [personSearch, setPersonSearch] = useState('');
  const [debtSearch, setDebtSearch] = useState('');
  const [creatingPerson, setCreatingPerson] = useState(false);
  const [showDebtModal, setShowDebtModal] = useState(false);
  const [creatingDebt, setCreatingDebt] = useState(false);
  const [debtError, setDebtError] = useState('');
  const [nearbyPayments, setNearbyPayments] = useState<SupabasePayment[]>([]);
  const [loadingPayments, setLoadingPayments] = useState(false);
  const [paymentSearch, setPaymentSearch] = useState('');
  /** Reparto del pago nuevo según Postgres; `key` dice para qué parámetros vale. */
  const [preview, setPreview] = useState<{ key: string; data: PaymentPreview } | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const queryClient = useQueryClient();

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
                felicidad: t.felicidad,
                deuda_id: t.deuda_id || '',
                pago_id: t.pago_id || ''
            }));
            setSplits(loadedSplits);
            setSelectedSplitIndex(0);
            setDebtDrafts(loadedSplits.map(s => nuevoDraft(
                s.nombre_limpio || transaction.DESCRIPCION,
                s.monto,
                transaction.MONTO > 0,
                s.deuda_id || '',
                s.pago_id || '',
                !!s.es_reembolsable
            )));

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
                nombre_limpio: transaction.nombre_limpio,
                deuda_id: transaction.deuda_id || '',
                pago_id: transaction.pago_id || ''
            }]);
            setDebtDrafts([nuevoDraft(
                transaction.nombre_limpio || transaction.DESCRIPCION,
                transaction.MONTO,
                transaction.MONTO > 0,
                transaction.deuda_id ? String(transaction.deuda_id) : '',
                transaction.pago_id ? String(transaction.pago_id) : '',
                !!transaction.es_reembolsable
            )]);

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

        // Estado de la sección de deuda
        setDebtError('');
        setPersonSearch('');
        setDebtSearch('');
        setNearbyDebts([]);
        setNearbyPayments([]);
        setPaymentSearch('');
        setPreview(null);
        setShowDebtModal(false);
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
                      const tagsList = parseTags(rule.tags);
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

                  // La regla solo rellena huecos: nunca pisa lo que ya está etiquetado,
                  // si no el modal mostraría algo distinto a lo guardado (y lo reescribiría al guardar).
                  const vacio = (v?: string | null) => {
                      const s = (v || '').trim();
                      return !s || s === '---';
                  };
                  setFormData(prev => ({
                      ...prev,
                      categoria: vacio(prev.categoria) ? (rule.categoria || tagRuleData.categoria || prev.categoria) : prev.categoria,
                      tags: vacio(prev.tags) ? (rule.tags || prev.tags) : prev.tags,
                      prioridad: vacio(prev.prioridad) ? (rule.prioridad || tagRuleData.prioridad || prev.prioridad) : prev.prioridad,
                      es_fijo: transaction?.revisado
                          ? prev.es_fijo
                          : (rule.es_fijo !== undefined ? rule.es_fijo : (tagRuleData.es_fijo !== undefined ? tagRuleData.es_fijo : prev.es_fijo)),
                      nota: vacio(prev.nota) ? (rule.nota || tagRuleData.nota || prev.nota) : prev.nota
                  }));
              }
          } catch (e) {
              // Ignore
          }
      };

      const timer = setTimeout(fetchRule, 500);
      return () => clearTimeout(timer);
  }, [formData.nombre_limpio, isOpen, transaction]);

  // Las personas se cargan al abrir: "¿De quién es?" también las usa.
  useEffect(() => {
      if (!isOpen || deudores.length) return;
      let cancelled = false;
      api.getDeudores()
         .then(ds => { if (!cancelled) setDeudores(ds); })
         .catch(() => { /* silencioso: la sección funciona sin datos remotos */ });
      return () => { cancelled = true; };
      // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  // Deudas del día del gasto: las únicas candidatas para asociar.
  useEffect(() => {
      if (!isOpen || !transaction || !formData.es_reembolsable || nearbyDebts.length) return;
      let cancelled = false;
      const day = fechaDia(transaction.FECHA);
      setLoadingDebts(true);
      api.getSupabaseDebts(day, day)
         .then(debts => { if (!cancelled) setNearbyDebts(debts); })
         .catch(() => { /* silencioso */ })
         .finally(() => { if (!cancelled) setLoadingDebts(false); });
      return () => { cancelled = true; };
      // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, transaction, formData.es_reembolsable]);

  // Pagos del día del movimiento, sin cruces: los únicos candidatos para asociar.
  useEffect(() => {
      if (!isOpen || !transaction || !formData.es_reembolsable || nearbyPayments.length) return;
      let cancelled = false;
      const day = fechaDia(transaction.FECHA);
      setLoadingPayments(true);
      api.getSupabasePayments(undefined, day, day)
         .then(pagos => { if (!cancelled) setNearbyPayments(pagos); })
         .catch(() => { /* silencioso */ })
         .finally(() => { if (!cancelled) setLoadingPayments(false); });
      return () => { cancelled = true; };
      // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, transaction, formData.es_reembolsable]);

  // Prellenar la persona del borrador: por la deuda ya vinculada o por el nombre guardado.
  useEffect(() => {
      if (!deudores.length || !debtDrafts.length) return;
      setDebtDrafts(prev => {
          let changed = false;
          const next = prev.map((draft, i) => {
              if (draft.deudorId) return draft;
              const linked = draft.deudaId
                  ? nearbyDebts.find(d => String(d.ID) === draft.deudaId)
                  : undefined;
              const linkedPago = draft.pagoId
                  ? nearbyPayments.find(p => String(p.id) === draft.pagoId)
                  : undefined;
              if (draft.pagoId && linkedPago) {
                  changed = true;
                  return { ...draft, deudorId: String(linkedPago.deudor_id), esMiPago: !!linkedPago.es_mi_pago };
              }
              const nombre = linked?.DEUDOR_NOMBRE || splits[i]?.deudor || (i === 0 ? transaction?.deudor : '') || '';
              const match = deudores.find(d => d.nombre.toLowerCase() === String(nombre).toLowerCase());
              if (!match) return draft;
              changed = true;
              return {
                  ...draft,
                  deudorId: String(match.id),
                  esMiDeuda: linked ? !!linked.ES_MI_DEUDA : draft.esMiDeuda,
              };
          });
          return changed ? next : prev;
      });
      // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deudores, nearbyDebts, nearbyPayments, debtDrafts.length]);


  const [selectedSplitIndex, setSelectedSplitIndex] = useState<number>(0);

  // Vista previa del pago nuevo: el reparto lo decide Postgres, aquí solo se muestra.
  const draftActivo = debtDrafts[isSplitting ? selectedSplitIndex : 0];
  const previewKey = draftActivo && formData.es_reembolsable && draftActivo.kind === 'pago'
      && draftActivo.pagoMode === 'create' && draftActivo.deudorId && draftActivo.pagoMonto > 0.009
      ? JSON.stringify([draftActivo.deudorId, draftActivo.pagoMonto, draftActivo.esMiPago, draftActivo.pagoDeudasIds])
      : '';
  useEffect(() => {
      if (!previewKey || !draftActivo) return;
      let cancelled = false;
      const timer = setTimeout(() => {
          setLoadingPreview(true);
          api.previewSupabasePayment({
              deudor_id: draftActivo.deudorId,
              monto: draftActivo.pagoMonto,
              es_mi_pago: draftActivo.esMiPago,
              deudas_ids: draftActivo.pagoDeudasIds,
          })
             .then(data => { if (!cancelled) setPreview({ key: previewKey, data }); })
             .catch(() => { if (!cancelled) setPreview(null); })
             .finally(() => { if (!cancelled) setLoadingPreview(false); });
      }, 350);
      return () => { cancelled = true; clearTimeout(timer); };
      // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewKey]);

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
    setDebtDrafts(prev => [...prev, nuevoDraft('', newSplit.monto, (transaction?.MONTO || 0) > 0, '', '', true)]);
    setSelectedSplitIndex(newSplits.length - 1); // Select the new one
  };

  const handleRemoveSplit = (e: React.MouseEvent, index: number) => {
      e.stopPropagation();
      if (splits.length <= 1) return;
      const newSplits = [...splits];
      newSplits.splice(index, 1);
      setSplits(newSplits);
      setDebtDrafts(prev => prev.filter((_, i) => i !== index));
      if (selectedSplitIndex >= index && selectedSplitIndex > 0) {
          setSelectedSplitIndex(selectedSplitIndex - 1);
      }
  };

  const handleClose = () => {
    setIsClosing(true);
    setTimeout(onClose, 200);
  };

  /** Qué le falta a un borrador para poder guardarse. `null` = está listo. */
  const validarDraft = (draft: DebtDraft | undefined): string | null => {
    if (!draft) return null;
    if (draft.kind === 'pago') {
      if (draft.pagoMode === 'associate') return draft.pagoId ? null : 'elige el pago al que se asocia';
      if (!draft.deudorId) return 'elige con quién es el pago';
      if (!(draft.pagoMonto > 0.009)) return 'el monto del pago debe ser mayor a 0';
      return null;
    }
    if (draft.mode === 'none') return null;
    if (draft.mode === 'associate') {
      return draft.deudaId ? null : 'elige la deuda a la que se asocia';
    }
    if (!draft.deudorId) return 'elige con quién es la deuda';
    if (!draft.titulo.trim()) return 'ponle un nombre a la deuda';
    if (!(draft.monto > 0.009)) return 'el monto de la deuda debe ser mayor a 0';
    return null;
  };

  /** Devuelve el vínculo final de una parte, creando la deuda o el pago si hace falta. */
  const resolverDraft = async (draft: DebtDraft | undefined, fallbackTitulo: string): Promise<VinculoDeudas> => {
    if (!draft) return SIN_VINCULO;
    if (draft.kind === 'pago') {
      if (draft.pagoMode === 'associate') return { deuda_id: '', pago_id: draft.pagoId || '' };
      const pago = await api.createSupabasePayment({
        deudor_id: draft.deudorId,
        monto: Math.abs(draft.pagoMonto),
        es_mi_pago: draft.esMiPago,
        fecha_pago: fechaDia(transaction!.FECHA),
        idem_key: draft.idemKey,
        deudas_ids: draft.pagoDeudasIds,
      });
      return { deuda_id: '', pago_id: String(pago.pago_id) };
    }
    if (draft.mode === 'none') return SIN_VINCULO;
    if (draft.mode === 'associate') return { deuda_id: draft.deudaId || '', pago_id: '' };
    const created = await api.createSupabaseDebt({
      titulo: (draft.titulo || fallbackTitulo || transaction!.DESCRIPCION).trim(),
      monto: Math.abs(draft.monto),
      deudor_id: draft.deudorId,
      fecha_gasto: fechaDia(transaction!.FECHA),
      es_mi_deuda: draft.esMiDeuda,
    });
    return { deuda_id: String(created.id), pago_id: '' };
  };

  /** ¿Algún borrador escribe en Supabase? Entonces las vistas de deudas quedan viejas. */
  const escribeEnSupabase = (drafts: (DebtDraft | undefined)[]) =>
    drafts.some(d => d && (d.kind === 'pago' ? d.pagoMode === 'create' : d.mode === 'create'));

  const refrescarDeudas = () => {
    for (const key of ['supabase-payments', 'supabase-debts', 'deudores', 'estado-cuenta']) {
      queryClient.invalidateQueries({ queryKey: [key] });
    }
  };

  /**
   * Un pago nuevo a deudas elegidas que no alcanza a gastarse deja saldo a favor. Es
   * legítimo, pero conviene que sea a propósito: la app pide lo mismo antes de guardar.
   */
  const confirmarSobrantes = async (drafts: (DebtDraft | undefined)[]): Promise<boolean> => {
    for (const d of drafts) {
      if (!d || d.kind !== 'pago' || d.pagoMode !== 'create' || !d.pagoDeudasIds.length) continue;
      const plan = await api.previewSupabasePayment({
        deudor_id: d.deudorId, monto: d.pagoMonto, es_mi_pago: d.esMiPago, deudas_ids: d.pagoDeudasIds,
      });
      if (plan.sobrante > 0.01) {
        const persona = deudores.find(x => String(x.id) === d.deudorId)?.nombre || 'la persona';
        const quien = d.esMiPago ? 'tuyo' : `de ${persona}`;
        if (!window.confirm(`Las deudas elegidas no alcanzan: quedarán ${money(plan.sobrante)} como saldo a favor ${quien}. ¿Registrar el pago igual?`)) {
          return false;
        }
      }
    }
    return true;
  };

  const handleSave = async () => {
    if (!transaction) return;
    setDebtError('');

    if (isSplitting && splits.length > 1) {
        // Validation: Sum must match or warn?
        // Let's enforce it matches within a small margin
        if (Math.abs(remainingAmount) > 0.01) {
            alert(`El total dividido (${totalSplitAmount.toFixed(2)}) no coincide con el monto original (${Math.abs(transaction.MONTO).toFixed(2)})`);
            return;
        }

        // Cada parte reembolsable lleva su propia deuda: valida todas antes de escribir nada.
        for (let i = 0; i < splits.length; i++) {
            if (!splits[i].es_reembolsable) continue;
            const err = validarDraft(debtDrafts[i]);
            if (err) {
                setSelectedSplitIndex(i);
                setDebtError(`Parte ${i + 1} ("${splits[i].nombre_limpio || 'sin nombre'}"): ${err}.`);
                setShowDebtModal(true);
                return;
            }
        }

        const multiplier = transaction.MONTO < 0 ? -1 : 1;
        const activos = splits.map((sp, i) => (sp.es_reembolsable ? debtDrafts[i] : undefined));
        setCreatingDebt(true);
        const processedSplits: SplitItem[] = [];
        try {
            if (!(await confirmarSobrantes(activos))) {
                setCreatingDebt(false);
                return;
            }
            for (let i = 0; i < splits.length; i++) {
                const split = splits[i];
                const vinculo = split.es_reembolsable
                    ? await resolverDraft(debtDrafts[i], split.nombre_limpio || '')
                    : SIN_VINCULO;
                processedSplits.push({
                    ...split,
                    monto: split.monto * multiplier,
                    revisado: true,
                    ...vinculo,
                });
            }
        } catch (e) {
            setCreatingDebt(false);
            if (escribeEnSupabase(activos)) refrescarDeudas();
            setDebtError('No se pudo registrar en Supabase. Revisa la conexión e intenta de nuevo.');
            return;
        }
        if (escribeEnSupabase(activos)) refrescarDeudas();

        try {
            await api.splitTransaction(transaction.id, processedSplits);
        } finally {
            setCreatingDebt(false);
        }
        onSave(transaction.id, {}); // Trigger refresh
    } else {
        const updates: TransactionUpdate = { ...formData };

        if (formData.es_reembolsable) {
            const err = validarDraft(debtDrafts[0]);
            if (err) {
                setDebtError(`Para guardar, ${err}.`);
                setShowDebtModal(true);
                return;
            }
            setCreatingDebt(true);
            try {
                if (!(await confirmarSobrantes([debtDrafts[0]]))) {
                    setCreatingDebt(false);
                    return;
                }
                Object.assign(updates, await resolverDraft(debtDrafts[0], formData.nombre_limpio || ''));
            } catch (e) {
                // Un reintento con la misma idem_key no duplica el pago si sí llegó a crearse.
                if (escribeEnSupabase([debtDrafts[0]])) refrescarDeudas();
                setDebtError('No se pudo registrar en Supabase. Revisa la conexión e intenta de nuevo.');
                setCreatingDebt(false);
                return; // aborta el guardado
            }
            if (escribeEnSupabase([debtDrafts[0]])) refrescarDeudas();
            setCreatingDebt(false);
        } else {
            // Ya no es reembolsable: desvincular cualquier deuda o pago previo
            Object.assign(updates, SIN_VINCULO);
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
  const currentTags = parseTags(formData.tags);
  const perteneceOptions = Array.from(new Set([
    ...PERTENECE_BASE,
    ...deudores.map(d => d.nombre),
    ...(formData.pertenece_a ? [formData.pertenece_a] : []),
  ]));

  // Hora real del consumo: la del correo del banco para tarjeta, la del extracto
  // para banca. Null cuando ninguna la respalda.
  const hora = horaEfectiva(transaction);

  // ── Sección de reembolso ────────────────────────────────────────────────────
  // El borrador vive por parte: sin división solo existe el índice 0.
  const dia = fechaDia(transaction.FECHA);
  const draftIndex = isSplitting ? selectedSplitIndex : 0;
  const montoParte = isSplitting
    ? Math.abs(splits[selectedSplitIndex]?.monto || 0)
    : Math.abs(transaction.MONTO);
  const draft: DebtDraft = debtDrafts[draftIndex]
    ?? nuevoDraft(formData.nombre_limpio || transaction.DESCRIPCION, montoParte, transaction.MONTO > 0);

  const actualizarDraft = (patch: Partial<DebtDraft>) => {
    setDebtError('');
    setDebtDrafts(prev => {
      const next = [...prev];
      while (next.length <= draftIndex) {
        next.push(nuevoDraft(formData.nombre_limpio || transaction.DESCRIPCION, montoParte, transaction.MONTO > 0));
      }
      next[draftIndex] = { ...next[draftIndex], ...patch };
      return next;
    });
  };

  const personasFiltradas = deudores.filter(d =>
    d.nombre.toLowerCase().includes(personSearch.trim().toLowerCase())
  );

  const elegirPersona = (p: SupabaseDeudor) => {
    actualizarDraft({ deudorId: String(p.id) });
    setFormData(prev => ({ ...prev, deudor: p.nombre }));
  };

  const crearPersona = async () => {
    const nombre = personSearch.trim();
    if (!nombre || creatingPerson) return;
    setCreatingPerson(true);
    try {
      const nuevo = await api.createDeudor(nombre);
      setDeudores(prev => [...prev, nuevo]);
      elegirPersona(nuevo);
      setPersonSearch('');
    } catch (e) {
      setDebtError(`No se pudo crear la persona "${nombre}".`);
    } finally {
      setCreatingPerson(false);
    }
  };

  const personaElegida = deudores.find(d => String(d.id) === draft.deudorId);

  const deudasCandidatas = nearbyDebts
    .filter(d => {
      if (!draft.deudorId) return true;
      if (d.DEUDOR_ID) return String(d.DEUDOR_ID) === draft.deudorId;
      return d.DEUDOR_NOMBRE === personaElegida?.nombre;
    })
    .filter(d => {
      const q = debtSearch.trim().toLowerCase();
      if (!q) return true;
      return (d.DESCRIPCION || '').toLowerCase().includes(q)
          || d.MONTO.toFixed(2).includes(q)
          || (d.DEUDOR_NOMBRE || '').toLowerCase().includes(q);
    })
    // Mismo monto primero: es la coincidencia que casi siempre buscas.
    .sort((a, b) => Math.abs(a.MONTO - montoParte) - Math.abs(b.MONTO - montoParte));

  const elegirDeuda = (d: SupabaseDebt) => {
    const nombre = d.DEUDOR_NOMBRE;
    const persona = deudores.find(x => x.nombre === nombre);
    actualizarDraft({
      deudaId: String(d.ID),
      esMiDeuda: !!d.ES_MI_DEUDA,
      ...(persona ? { deudorId: String(persona.id) } : {}),
    });
    if (nombre) setFormData(prev => ({ ...prev, deudor: nombre }));
  };

  const deudaVinculada = draft.deudaId
    ? nearbyDebts.find(d => String(d.ID) === draft.deudaId)
    : undefined;

  const draftError = formData.es_reembolsable ? validarDraft(draft) : null;
  const esPago = draft.kind === 'pago';

  // ── Pagos ──
  const pagosCandidatos = nearbyPayments
    .filter(p => !draft.deudorId || String(p.deudor_id) === draft.deudorId)
    .filter(p => {
      const q = paymentSearch.trim().toLowerCase();
      if (!q) return true;
      return (p.deudor_nombre || '').toLowerCase().includes(q)
          || p.monto_total.toFixed(2).includes(q)
          || (p.deudas ?? []).some(d => (d.titulo || '').toLowerCase().includes(q));
    })
    .sort((a, b) => Math.abs(a.monto_total - montoParte) - Math.abs(b.monto_total - montoParte));

  const pagoVinculado = draft.pagoId
    ? nearbyPayments.find(p => String(p.id) === draft.pagoId)
    : undefined;

  const elegirPago = (p: SupabasePayment) => {
    actualizarDraft({ pagoId: String(p.id), esMiPago: !!p.es_mi_pago, deudorId: String(p.deudor_id) });
    if (p.deudor_nombre) setFormData(prev => ({ ...prev, deudor: p.deudor_nombre }));
  };

  const vistaPrevia = preview && preview.key === previewKey ? preview.data : null;
  // Deudas que puede abonar el pago: las pendientes del lado de quien paga.
  const deudasAbonables = (vistaPrevia?.deudas ?? [])
    .filter(d => d.es_mi_deuda === draft.esMiPago && (d.saldo_real > 0.01 || d.pago_planeado > 0.009));

  const alternarDeudaDelPago = (id: string) => {
    const ya = draft.pagoDeudasIds.includes(id);
    actualizarDraft({ pagoDeudasIds: ya ? draft.pagoDeudasIds.filter(x => x !== id) : [...draft.pagoDeudasIds, id] });
  };

  const detallePago = (p: SupabasePayment) =>
    (p.deudas ?? []).map(d => d.titulo).join(', ') || 'sin deudas abonadas';

  const direccionPago = (esMio: boolean, nombre: string) => (esMio ? `le pagaste a ${nombre}` : `${nombre} te pagó`);

  /** Cambia entre nada, deuda y pago. Elegir uno abre su detalle: siempre hay algo que decidir. */
  const elegirTipo = (tipo: 'nada' | DebtKind) => {
    if (tipo === 'nada') {
      setFormData(prev => ({ ...prev, es_reembolsable: false }));
      setShowDebtModal(false);
      return;
    }
    setFormData(prev => ({ ...prev, es_reembolsable: true }));
    actualizarDraft({ kind: tipo });
    setShowDebtModal(true);
  };

  const tipoActual: 'nada' | DebtKind = formData.es_reembolsable ? draft.kind : 'nada';

  const resumenDeuda = draftError
    ? `Al guardar falta un paso: ${draftError}.`
    : esPago
      ? draft.pagoMode === 'create'
        ? `Al guardar se registrará un pago de ${money(draft.pagoMonto)}: ${draft.esMiPago ? `le pagas a ${personaElegida?.nombre || '—'}` : `${personaElegida?.nombre || '—'} te paga`}${
            draft.pagoDeudasIds.length
              ? `, abonando ${draft.pagoDeudasIds.length} deuda${draft.pagoDeudasIds.length > 1 ? 's' : ''} elegida${draft.pagoDeudasIds.length > 1 ? 's' : ''}.`
              : ', repartido automáticamente como en la app.'}`
        : `Se vinculará con el pago de ${pagoVinculado?.deudor_nombre || 'la persona'}${pagoVinculado ? ` (${money(pagoVinculado.monto_total)} · ${detallePago(pagoVinculado)})` : ''}.`
    : draft.mode === 'none'
      ? 'Se marcará como reembolsable, pero no se registrará ninguna deuda.'
      : draft.mode === 'create'
        ? `Al guardar se creará la deuda "${draft.titulo || '(sin nombre)'}" de ${money(draft.monto)} con ${personaElegida?.nombre || '—'}: ${draft.esMiDeuda ? 'tú la debes' : 'te la deben'}.`
        : `Se vinculará con "${deudaVinculada?.DESCRIPCION || 'la deuda elegida'}"${deudaVinculada ? ` (${money(deudaVinculada.MONTO)} · ${deudaVinculada.DEUDOR_NOMBRE})` : ''}.`;

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
    <div className={`fixed inset-0 z-[70] flex items-center justify-center p-4 transition-all duration-200 ${isClosing ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}>
      
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
                    {hora && (
                      <>
                        <span className="opacity-40">•</span>
                        <span className="text-primary-400">{hora}</span>
                      </>
                    )}
                  </span>
              </div>
              <h1 className="text-xl font-bold text-white line-clamp-1 max-w-md tracking-tight">
                {transaction.DESCRIPCION}
              </h1>
            </div>
          </div>
          
          <div className="flex items-center gap-6">
             {/* Botón Recordar Momento (información) */}
             {transaction.FECHA && (
               <a
                 href={urlRecordarMomento(transaction)}
                 target="_blank"
                 rel="noreferrer"
                 className="px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-wider border border-purple-500/30 bg-purple-500/10 text-purple-300 hover:bg-purple-500/20 hover:text-white transition-all flex items-center gap-2 shadow-sm"
                 title={hora
                   ? `Ver el momento de las ${hora} en el timeline unificado`
                   : 'Ver el día en el timeline unificado (esta transacción no tiene hora conocida)'}
               >
                 <Clock size={14} className="text-purple-400" />
                 Recordar Momento
               </a>
             )}

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
                  {isExpense ? '-' : '+'}{money(Math.abs(transaction.MONTO))}
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
                                 Restan: {money(remainingAmount)}
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
                                        {money((split.monto || 0))}
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
                                      const prevVal = splits[selectedSplitIndex]?.monto || 0;
                                      const newSplits = [...splits];
                                      newSplits[selectedSplitIndex] = { ...newSplits[selectedSplitIndex], monto: val };
                                      setSplits(newSplits);
                                      // El monto de la deuda sigue al de la parte mientras no lo hayas tocado.
                                      setDebtDrafts(prev => prev.map((d, i) => (
                                          i === selectedSplitIndex && Math.abs(d.monto - prevVal) < 0.005
                                              ? { ...d, monto: val }
                                              : d
                                      )));
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
                        onChange={e => {
                          const val = e.target.value;
                          const prevVal = formData.nombre_limpio || '';
                          setFormData({...formData, nombre_limpio: val});
                          // El nombre de la deuda sigue al comercial mientras no lo hayas tocado.
                          setDebtDrafts(prev => prev.map((d, i) => (
                            i === (isSplitting ? selectedSplitIndex : 0) && (!d.titulo || d.titulo === prevVal)
                              ? { ...d, titulo: val }
                              : d
                          )));
                        }}
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

                  {/* Deudas: nada, una deuda o un pago — el detalle vive en su propio modal */}
                  <div className={`
                     rounded-3xl border overflow-hidden transition-colors duration-300
                     ${tipoActual === 'pago'
                        ? 'border-sky-500/30 bg-sky-500/[0.06]'
                        : tipoActual === 'deuda'
                           ? 'border-purple-500/30 bg-purple-500/[0.06]'
                           : 'border-white/5 bg-surface-800/20 hover:border-white/10'}
                  `}>
                     <div className="p-5 space-y-3">
                        <div className="flex items-center gap-3 min-w-0">
                           <div className={`p-2 rounded-lg ${
                              tipoActual === 'pago' ? 'bg-sky-500/20 text-sky-300'
                                 : tipoActual === 'deuda' ? 'bg-purple-500/20 text-purple-300'
                                 : 'bg-surface-800 text-surface-500'}`}>
                              {tipoActual === 'pago' ? <Banknote size={20} /> : <CreditCard size={20} />}
                           </div>
                           <div className="min-w-0">
                              <div className={`text-sm font-bold ${
                                 tipoActual === 'pago' ? 'text-sky-200' : tipoActual === 'deuda' ? 'text-purple-200' : 'text-surface-300'}`}>Deudas</div>
                              <div className="text-[10px] text-surface-500 truncate">¿Nace una cuenta con alguien, o se salda?</div>
                           </div>
                        </div>

                        <div className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-surface-900 border border-white/5" role="radiogroup" aria-label="Relación con deudas">
                           {([
                              { val: 'nada', icon: Ban, label: 'Nada', on: 'bg-surface-700 text-white' },
                              { val: 'deuda', icon: HandCoins, label: 'Deuda', on: 'bg-purple-600 text-white' },
                              { val: 'pago', icon: Banknote, label: 'Pago', on: 'bg-sky-600 text-white' },
                           ] as const).map(opt => (
                              <button
                                 type="button"
                                 key={opt.val}
                                 role="radio"
                                 aria-checked={tipoActual === opt.val}
                                 onClick={() => elegirTipo(opt.val)}
                                 className={`flex items-center justify-center gap-1.5 px-2 py-2 rounded-lg text-[11px] font-bold uppercase tracking-wider transition-colors ${
                                    tipoActual === opt.val ? opt.on : 'text-surface-400 hover:text-white hover:bg-surface-800'
                                 }`}
                              >
                                 <opt.icon size={13} /> {opt.label}
                              </button>
                           ))}
                        </div>
                     </div>

                     {formData.es_reembolsable && (
                        <div className="px-5 pb-5 space-y-2.5 animate-fade-in">
                           <div className={`h-px w-full ${esPago ? 'bg-sky-500/20' : 'bg-purple-500/20'}`} />

                           <button
                              type="button"
                              onClick={() => setShowDebtModal(true)}
                              className={`w-full flex items-center justify-between gap-3 px-3.5 py-3 rounded-xl bg-surface-900 border border-white/5 hover:bg-surface-800 transition-all text-left group/deuda ${esPago ? 'hover:border-sky-500/40' : 'hover:border-purple-500/40'}`}
                           >
                              <div className="min-w-0">
                                 <div className="flex items-center gap-1.5 mb-1">
                                    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border ${
                                       !esPago && draft.mode === 'none'
                                          ? 'bg-surface-800 text-surface-400 border-white/5'
                                          : draftError
                                             ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                                             : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                                    }`}>
                                       {!esPago && draft.mode === 'none'
                                          ? <><Ban size={9} /> Sin deuda</>
                                          : draftError
                                             ? <><AlertCircle size={9} /> Falta info</>
                                             : (esPago ? draft.pagoMode === 'create' : draft.mode === 'create')
                                                ? <><Plus size={9} /> Se creará</>
                                                : <><Link2 size={9} /> {esPago ? 'Vinculado' : 'Vinculada'}</>}
                                    </span>
                                    {(esPago || draft.mode !== 'none') && !draftError && (
                                       <span className="text-[10px] font-mono font-bold text-surface-300">
                                          {esPago
                                             ? money(draft.pagoMode === 'create' ? draft.pagoMonto : (pagoVinculado?.monto_total ?? 0))
                                             : money(draft.mode === 'create' ? draft.monto : (deudaVinculada?.MONTO ?? draft.monto))}
                                       </span>
                                    )}
                                 </div>
                                 <div className="text-xs text-surface-400 truncate">
                                    {!esPago && draft.mode === 'none'
                                       ? 'No se registrará deuda'
                                       : draftError
                                          ? `Falta: ${draftError}`
                                          : esPago
                                             ? <>
                                                 <span className="text-surface-200 font-bold">{personaElegida?.nombre || pagoVinculado?.deudor_nombre || '—'}</span>
                                                 {' · '}
                                                 {draft.esMiPago ? 'le pagaste' : 'te pagó'}
                                               </>
                                             : <>
                                                 <span className="text-surface-200 font-bold">{personaElegida?.nombre || deudaVinculada?.DEUDOR_NOMBRE || '—'}</span>
                                                 {' · '}
                                                 {draft.esMiDeuda ? 'tú lo debes' : 'te lo deben'}
                                               </>}
                                 </div>
                              </div>
                              <div className={`flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-surface-500 transition-colors shrink-0 ${esPago ? 'group-hover/deuda:text-sky-300' : 'group-hover/deuda:text-purple-300'}`}>
                                 <Settings2 size={14} /> Configurar
                              </div>
                           </button>

                           {debtError && (
                              <div className="text-[11px] text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-xl px-3 py-2 flex items-start gap-2">
                                 <AlertCircle size={13} className="mt-0.5 shrink-0" /> {debtError}
                              </div>
                           )}
                        </div>
                     )}
                  </div>

                </div>
              </div>
            </div>
        </div>


        {/* --- Modal de la deuda: el detalle necesita aire, la tarjeta de la esquina no --- */}
        {showDebtModal && formData.es_reembolsable && (
          <div className="absolute inset-0 z-40 flex items-center justify-center p-6 animate-fade-in">
            <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setShowDebtModal(false)} />
            <div className={`relative w-full max-w-4xl max-h-full flex flex-col bg-surface-950 border rounded-3xl shadow-2xl overflow-hidden ${esPago ? 'border-sky-500/25' : 'border-purple-500/25'}`}>
              <header className="flex-none px-6 py-5 border-b border-white/5 bg-surface-900/60 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`p-2.5 rounded-xl border ${esPago ? 'bg-sky-500/20 text-sky-200 border-sky-500/30' : 'bg-purple-500/20 text-purple-200 border-purple-500/30'}`}>
                    {esPago ? <Banknote size={20} /> : <CreditCard size={20} />}
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-base font-bold text-white tracking-tight">{esPago ? 'Pago de deudas' : 'Reembolso · Deuda'}</h2>
                    <p className="text-[11px] text-surface-500 leading-tight">
                      {esPago
                        ? 'Este dinero salda una cuenta: alguien te devolvió, o le devolviste tú.'
                        : 'Este dinero no es tuyo del todo: queda una cuenta pendiente con alguien.'}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowDebtModal(false)}
                  className="p-2 rounded-xl bg-surface-800 hover:bg-surface-700 text-surface-400 hover:text-white transition-colors border border-white/5 shrink-0"
                >
                  <X size={18} />
                </button>
              </header>

              <div className="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-5">

                {isSplitting && (
                   <div className="flex items-center gap-2 text-[11px] text-purple-200/80 bg-purple-500/10 border border-purple-500/20 rounded-xl px-3.5 py-2.5">
                      <Scissors size={13} className="shrink-0" />
                      Estás configurando {esPago ? 'el pago' : 'la deuda'} de la parte <strong className="text-white mx-1">{selectedSplitIndex + 1}</strong>
                      ({splits[selectedSplitIndex]?.nombre_limpio || 'sin nombre'} · {money(splits[selectedSplitIndex]?.monto || 0)}).
                      Cada parte lleva su propio vínculo.
                   </div>
                )}

                <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">

                   {/* ── Paso 1 + 2: con quién y en qué dirección ── */}
                   <div className="space-y-5 bg-surface-900/40 border border-white/5 rounded-2xl p-4">
                      <div className="space-y-2.5">
                         <StepLabel n={1} title="¿Con quién?" hint={esPago ? 'La persona con la que se salda la cuenta' : 'La persona con la que queda la cuenta'} />

                         <div className="relative">
                            <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" />
                            <input
                               value={personSearch}
                               onChange={e => setPersonSearch(e.target.value)}
                               placeholder="Buscar persona…"
                               className="w-full bg-surface-900 border border-white/5 rounded-xl pl-9 pr-3 py-2.5 text-sm text-surface-50 placeholder:text-surface-600 focus:outline-none focus:border-purple-500/40 transition-colors"
                            />
                         </div>

                         <div className="max-h-52 overflow-y-auto custom-scrollbar space-y-1.5 pr-1">
                            {personasFiltradas.map(p => {
                               const active = draft.deudorId === String(p.id);
                               const neto = p.neto || 0;
                               return (
                                  <button
                                     type="button"
                                     key={String(p.id)}
                                     onClick={() => elegirPersona(p)}
                                     className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border text-left transition-all ${
                                        active
                                           ? 'bg-purple-500/15 border-purple-500/50'
                                           : 'bg-surface-900 border-white/5 hover:border-white/15 hover:bg-surface-800'
                                     }`}
                                  >
                                     <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 ${active ? 'bg-purple-500/30 text-purple-100' : 'bg-surface-800 text-surface-400'}`}>
                                        {p.nombre.slice(0, 1).toUpperCase()}
                                     </div>
                                     <div className="min-w-0 flex-1">
                                        <div className="text-sm font-bold text-surface-100 truncate">{p.nombre}</div>
                                        <div className="text-[10px] text-surface-500">
                                           {Math.abs(neto) < 0.01
                                              ? 'En cero'
                                              : neto > 0
                                                 ? <>Te debe <span className="text-emerald-400 font-bold">{money(neto)}</span></>
                                                 : <>Le debes <span className="text-rose-400 font-bold">{money(Math.abs(neto))}</span></>}
                                        </div>
                                     </div>
                                     {active && <CheckCircle2 size={16} className="text-purple-300 shrink-0" />}
                                  </button>
                               );
                            })}

                            {personasFiltradas.length === 0 && (
                               <div className="text-center py-3 space-y-2">
                                  <div className="text-xs text-surface-500 flex items-center justify-center gap-1.5">
                                     <Users size={13} /> {deudores.length ? 'Nadie coincide' : 'Sin personas registradas'}
                                  </div>
                                  {personSearch.trim() && (
                                     <button
                                        type="button"
                                        onClick={crearPersona}
                                        disabled={creatingPerson}
                                        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-purple-500/15 border border-purple-500/30 text-purple-200 text-xs font-bold hover:bg-purple-500/25 transition-colors disabled:opacity-50"
                                     >
                                        {creatingPerson ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                                        Crear "{personSearch.trim()}"
                                     </button>
                                  )}
                               </div>
                            )}
                         </div>
                      </div>

                      {!esPago ? (
                      <div className="space-y-2.5">
                         <StepLabel n={2} title="¿Quién le debe a quién?" hint="Define el signo de la cuenta" />
                         <div className="grid grid-cols-2 gap-2">
                            {([
                               { val: false, icon: HandCoins, title: 'Me lo deben', hint: 'Pagaste tú por otro', on: 'bg-emerald-500/15 border-emerald-500/40 text-emerald-200' },
                               { val: true, icon: Wallet, title: 'Yo lo debo', hint: 'Te lo cubrieron a ti', on: 'bg-rose-500/15 border-rose-500/40 text-rose-200' },
                            ] as const).map(opt => {
                               const active = draft.esMiDeuda === opt.val;
                               const bloqueado = draft.mode === 'associate';
                               return (
                                  <button
                                     type="button"
                                     key={String(opt.val)}
                                     disabled={bloqueado}
                                     onClick={() => actualizarDraft({ esMiDeuda: opt.val })}
                                     className={`px-3 py-3 rounded-xl border text-left transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                                        active ? opt.on : 'bg-surface-900 border-white/5 text-surface-400 hover:border-white/15'
                                     }`}
                                  >
                                     <opt.icon size={16} className="mb-1.5" />
                                     <div className="text-xs font-bold uppercase tracking-wider">{opt.title}</div>
                                     <div className="text-[10px] text-surface-500 leading-tight mt-0.5">{opt.hint}</div>
                                  </button>
                               );
                            })}
                         </div>
                         {draft.mode === 'associate' && (
                            <div className="text-[10px] text-surface-500 flex items-center gap-1.5">
                               <AlertCircle size={11} /> La dirección la manda la deuda que elegiste.
                            </div>
                         )}
                      </div>
                      ) : (
                      <div className="space-y-2.5">
                         <StepLabel n={2} title="¿Quién pagó?" hint="La dirección del dinero" />
                         <div className="grid grid-cols-2 gap-2">
                            {([
                               { val: false, icon: HandCoins, title: 'Me pagaron', hint: 'Te devolvieron lo que te debían', on: 'bg-emerald-500/15 border-emerald-500/40 text-emerald-200' },
                               { val: true, icon: Wallet, title: 'Pagué yo', hint: 'Devolviste lo que debías', on: 'bg-sky-500/15 border-sky-500/40 text-sky-200' },
                            ] as const).map(opt => {
                               const active = draft.esMiPago === opt.val;
                               const bloqueado = draft.pagoMode === 'associate';
                               return (
                                  <button
                                     type="button"
                                     key={String(opt.val)}
                                     disabled={bloqueado}
                                     onClick={() => actualizarDraft({ esMiPago: opt.val, pagoDeudasIds: [] })}
                                     className={`px-3 py-3 rounded-xl border text-left transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                                        active ? opt.on : 'bg-surface-900 border-white/5 text-surface-400 hover:border-white/15'
                                     }`}
                                  >
                                     <opt.icon size={16} className="mb-1.5" />
                                     <div className="text-xs font-bold uppercase tracking-wider">{opt.title}</div>
                                     <div className="text-[10px] text-surface-500 leading-tight mt-0.5">{opt.hint}</div>
                                  </button>
                               );
                            })}
                         </div>
                         {draft.pagoMode === 'associate' && (
                            <div className="text-[10px] text-surface-500 flex items-center gap-1.5">
                               <AlertCircle size={11} /> La dirección la manda el pago que elegiste.
                            </div>
                         )}
                      </div>
                      )}

                      <div className="space-y-1.5 pt-1 border-t border-white/5">
                         <label className="text-[10px] uppercase font-bold text-purple-300/70 ml-1 pt-3 block">¿De quién es el gasto?</label>
                         <SearchableSelect
                            value={formData.pertenece_a || '---'}
                            onChange={val => setFormData({ ...formData, pertenece_a: val })}
                            options={perteneceOptions}
                            icon={User}
                            placeholder="Buscar persona…"
                         />
                      </div>
                   </div>

                   {!esPago ? (
                   <>
                   {/* ── Paso 3: cómo se registra en el sistema de deudas ── */}
                   <div className="space-y-3 bg-surface-900/40 border border-white/5 rounded-2xl p-4">
                      <StepLabel n={3} title="¿Cómo se registra?" hint="Qué pasa en el sistema de deudas al guardar" />

                      <div className="grid grid-cols-3 gap-2">
                         {([
                            { val: 'create', icon: Plus, label: 'Crear nueva' },
                            { val: 'associate', icon: Link2, label: 'Asociar' },
                            { val: 'none', icon: Ban, label: 'Sin deuda' },
                         ] as const).map(opt => (
                            <button
                               type="button"
                               key={opt.val}
                               onClick={() => actualizarDraft({ mode: opt.val })}
                               className={`flex items-center justify-center gap-1.5 px-2 py-2.5 rounded-xl border text-[11px] font-bold uppercase tracking-wider transition-all ${
                                  draft.mode === opt.val
                                     ? 'bg-purple-500/15 border-purple-500/40 text-purple-200'
                                     : 'bg-surface-900 border-white/5 text-surface-400 hover:text-white hover:border-white/15'
                               }`}
                            >
                               <opt.icon size={13} /> {opt.label}
                            </button>
                         ))}
                      </div>

                      {draft.mode === 'create' && (
                         <div className="space-y-3 animate-fade-in">
                            <div className="space-y-1.5">
                               <label className="text-[10px] uppercase font-bold text-purple-300/70 ml-1">Nombre de la deuda</label>
                               <ConsoleInput
                                  value={draft.titulo}
                                  onChange={e => actualizarDraft({ titulo: e.target.value })}
                                  placeholder="Ej: 4 almuerzos"
                               />
                            </div>

                            <div className="space-y-1.5">
                               <div className="flex items-center justify-between ml-1">
                                  <label className="text-[10px] uppercase font-bold text-purple-300/70">Monto a cobrar</label>
                                  <div className="flex gap-1">
                                     {([
                                        { label: 'Todo', factor: 1 },
                                        { label: '½', factor: 1 / 2 },
                                        { label: '⅓', factor: 1 / 3 },
                                     ]).map(q => (
                                        <button
                                           type="button"
                                           key={q.label}
                                           onClick={() => actualizarDraft({ monto: Math.round(montoParte * q.factor * 100) / 100 })}
                                           className="px-2 py-0.5 rounded-md bg-surface-800 border border-white/5 text-[10px] font-bold text-surface-400 hover:text-white hover:border-white/20 transition-colors"
                                        >
                                           {q.label}
                                        </button>
                                     ))}
                                  </div>
                               </div>
                               <div className="relative">
                                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-surface-500">$</span>
                                  <input
                                     type="number"
                                     step="0.01"
                                     min="0"
                                     value={draft.monto}
                                     onChange={e => actualizarDraft({ monto: parseFloat(e.target.value) || 0 })}
                                     className="w-full bg-surface-900 border border-white/5 rounded-xl pl-8 pr-4 py-3.5 text-surface-50 font-mono font-bold focus:outline-none focus:border-purple-500/50 focus:bg-surface-800 shadow-[inset_0_2px_4px_rgba(0,0,0,0.3)] transition-all"
                                  />
                               </div>
                               <div className="text-[10px] text-surface-500 ml-1">
                                  De {money(montoParte)} {isSplitting ? 'de esta parte' : 'de la transacción'}
                                  {draft.monto > montoParte + 0.01 && (
                                     <span className="text-amber-300/90 ml-1">· estás cobrando más de lo que gastaste</span>
                                  )}
                               </div>
                            </div>

                            {draft.deudaId && (
                               <div className="text-[11px] text-amber-300/90 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2 flex items-start gap-2">
                                  <AlertCircle size={13} className="mt-0.5 shrink-0" />
                                  Esta transacción ya estaba vinculada a una deuda. Al guardar se creará otra y la anterior quedará suelta.
                               </div>
                            )}
                         </div>
                      )}

                      {draft.mode === 'associate' && (
                         <div className="space-y-2 animate-fade-in">
                            <div className="relative">
                               <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" />
                               <input
                                  value={debtSearch}
                                  onChange={e => setDebtSearch(e.target.value)}
                                  placeholder="Buscar por nombre o monto…"
                                  className="w-full bg-surface-900 border border-white/5 rounded-xl pl-9 pr-3 py-2.5 text-sm text-surface-50 placeholder:text-surface-600 focus:outline-none focus:border-purple-500/40 transition-colors"
                               />
                            </div>

                            <div className="text-[10px] text-surface-500 ml-1">
                               {loadingDebts
                                  ? 'Cargando deudas…'
                                  : `Deudas del ${dia}${draft.deudorId ? ', de la persona elegida' : ''}`}
                            </div>

                            <div className="space-y-2 max-h-64 overflow-y-auto custom-scrollbar pr-1">
                               {deudasCandidatas.map(d => {
                                  const id = String(d.ID);
                                  const active = draft.deudaId === id;
                                  return (
                                     <button
                                        type="button"
                                        key={id}
                                        onClick={() => elegirDeuda(d)}
                                        className={`w-full flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-xl border text-left transition-all ${
                                           active ? 'bg-purple-500/15 border-purple-500/50' : 'bg-surface-900 border-white/5 hover:border-white/15'
                                        }`}
                                     >
                                        <div className="min-w-0">
                                           <div className="text-sm font-bold text-surface-100 truncate">{d.DESCRIPCION || '(sin título)'}</div>
                                           <div className="text-[10px] text-surface-500 flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5">
                                              <span className="text-sky-300">{d.DEUDOR_NOMBRE}</span>
                                              <span>{d.ES_MI_DEUDA ? 'tú debes' : 'te deben'}</span>
                                              <span className={d.PAGADA ? 'text-emerald-400' : 'text-rose-400'}>{d.PAGADA ? 'PAGADA' : 'PENDIENTE'}</span>
                                              {Math.abs(d.MONTO - montoParte) < 0.01 && (
                                                 <span className="text-purple-300">mismo monto</span>
                                              )}
                                           </div>
                                        </div>
                                        <div className="flex items-center gap-2 shrink-0">
                                           <span className="font-mono font-bold text-white text-sm">{money(d.MONTO)}</span>
                                           {active && <CheckCircle2 size={16} className="text-purple-300" />}
                                        </div>
                                     </button>
                                  );
                               })}

                               {!loadingDebts && deudasCandidatas.length === 0 && (
                                  <div className="text-xs text-surface-500 bg-surface-900/50 border border-dashed border-white/10 rounded-xl px-4 py-4 text-center">
                                     No hay deudas del {dia} que coincidan.
                                     <button
                                        type="button"
                                        onClick={() => actualizarDraft({ mode: 'create' })}
                                        className="block mx-auto mt-2 text-purple-300 font-bold hover:text-purple-200"
                                     >
                                        Crear una nueva →
                                     </button>
                                  </div>
                               )}
                            </div>

                            {draft.deudaId && (
                               <button
                                  type="button"
                                  onClick={() => actualizarDraft({ deudaId: '' })}
                                  className="inline-flex items-center gap-1.5 text-[11px] font-bold text-surface-400 hover:text-rose-300 transition-colors"
                               >
                                  <Unlink size={12} /> Quitar el vínculo
                               </button>
                            )}
                         </div>
                      )}

                      {draft.mode === 'none' && (
                         <div className="text-xs text-surface-400 bg-surface-900/50 border border-dashed border-white/10 rounded-xl px-4 py-4 leading-relaxed animate-fade-in">
                            Se marca como reembolsable para los reportes (queda fuera de tus gastos reales),
                            pero <strong className="text-surface-200">no se registra ninguna deuda</strong> en Supabase.
                         </div>
                      )}
                   </div>
                   </>
                   ) : (
                   // ── Paso 3 (pago): enganchar uno registrado o registrarlo ──
                   <div className="space-y-3 bg-surface-900/40 border border-white/5 rounded-2xl p-4">
                      <StepLabel n={3} title="¿Cómo se registra?" hint="Qué pasa en el sistema de deudas al guardar" />

                      <div className="grid grid-cols-2 gap-2">
                         {([
                            { val: 'associate', icon: Link2, label: 'Asociar' },
                            { val: 'create', icon: Plus, label: 'Registrar nuevo' },
                         ] as const).map(opt => (
                            <button
                               type="button"
                               key={opt.val}
                               onClick={() => actualizarDraft({ pagoMode: opt.val })}
                               className={`flex items-center justify-center gap-1.5 px-2 py-2.5 rounded-xl border text-[11px] font-bold uppercase tracking-wider transition-all ${
                                  draft.pagoMode === opt.val
                                     ? 'bg-sky-500/15 border-sky-500/40 text-sky-200'
                                     : 'bg-surface-900 border-white/5 text-surface-400 hover:text-white hover:border-white/15'
                               }`}
                            >
                               <opt.icon size={13} /> {opt.label}
                            </button>
                         ))}
                      </div>

                      {draft.pagoMode === 'associate' && (
                         <div className="space-y-2 animate-fade-in">
                            <div className="relative">
                               <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" />
                               <input
                                  value={paymentSearch}
                                  onChange={e => setPaymentSearch(e.target.value)}
                                  placeholder="Buscar por persona, monto o deuda…"
                                  className="w-full bg-surface-900 border border-white/5 rounded-xl pl-9 pr-3 py-2.5 text-sm text-surface-50 placeholder:text-surface-600 focus:outline-none focus:border-sky-500/40 transition-colors"
                               />
                            </div>

                            <div className="text-[10px] text-surface-500 ml-1">
                               {loadingPayments
                                  ? 'Cargando pagos…'
                                  : `Pagos del ${dia}${draft.deudorId ? ', de la persona elegida' : ''}`}
                            </div>

                            <div className="space-y-2 max-h-64 overflow-y-auto custom-scrollbar pr-1">
                               {pagosCandidatos.map(p => {
                                  const id = String(p.id);
                                  const active = draft.pagoId === id;
                                  return (
                                     <button
                                        type="button"
                                        key={id}
                                        onClick={() => elegirPago(p)}
                                        className={`w-full flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-xl border text-left transition-all ${
                                           active ? 'bg-sky-500/15 border-sky-500/50' : 'bg-surface-900 border-white/5 hover:border-white/15'
                                        }`}
                                     >
                                        <div className="min-w-0">
                                           <div className="text-sm font-bold text-surface-100 truncate">{direccionPago(!!p.es_mi_pago, p.deudor_nombre)}</div>
                                           <div className="text-[10px] text-surface-500 flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5">
                                              <span className="truncate max-w-[16rem]">{detallePago(p)}</span>
                                              {(p.sobrante ?? 0) > 0.01 && <span className="text-sky-300">saldo a favor {money(p.sobrante ?? 0)}</span>}
                                              {Math.abs(p.monto_total - montoParte) < 0.01 && (
                                                 <span className="text-sky-300">mismo monto</span>
                                              )}
                                           </div>
                                        </div>
                                        <div className="flex items-center gap-2 shrink-0">
                                           <span className="font-mono font-bold text-white text-sm">{money(p.monto_total)}</span>
                                           {active && <CheckCircle2 size={16} className="text-sky-300" />}
                                        </div>
                                     </button>
                                  );
                               })}

                               {!loadingPayments && pagosCandidatos.length === 0 && (
                                  <div className="text-xs text-surface-500 bg-surface-900/50 border border-dashed border-white/10 rounded-xl px-4 py-4 text-center">
                                     No hay pagos del {dia} que coincidan.
                                     <button
                                        type="button"
                                        onClick={() => actualizarDraft({ pagoMode: 'create' })}
                                        className="block mx-auto mt-2 text-sky-300 font-bold hover:text-sky-200"
                                     >
                                        Registrar uno nuevo →
                                     </button>
                                  </div>
                               )}
                            </div>

                            {draft.pagoId && (
                               <button
                                  type="button"
                                  onClick={() => actualizarDraft({ pagoId: '' })}
                                  className="inline-flex items-center gap-1.5 text-[11px] font-bold text-surface-400 hover:text-rose-300 transition-colors"
                               >
                                  <Unlink size={12} /> Quitar el vínculo
                               </button>
                            )}
                         </div>
                      )}

                      {draft.pagoMode === 'create' && (
                         <div className="space-y-3 animate-fade-in">
                            <div className="space-y-1.5">
                               <div className="flex items-center justify-between ml-1">
                                  <label className="text-[10px] uppercase font-bold text-sky-300/70">Monto del pago</label>
                                  <button
                                     type="button"
                                     onClick={() => actualizarDraft({ pagoMonto: montoParte })}
                                     className="px-2 py-0.5 rounded-md bg-surface-800 border border-white/5 text-[10px] font-bold text-surface-400 hover:text-white hover:border-white/20 transition-colors"
                                  >
                                     Todo
                                  </button>
                               </div>
                               <div className="relative">
                                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-surface-500">$</span>
                                  <input
                                     type="number"
                                     step="0.01"
                                     min="0"
                                     value={draft.pagoMonto}
                                     onChange={e => actualizarDraft({ pagoMonto: parseFloat(e.target.value) || 0 })}
                                     className="w-full bg-surface-900 border border-white/5 rounded-xl pl-8 pr-4 py-3.5 text-surface-50 font-mono font-bold focus:outline-none focus:border-sky-500/50 focus:bg-surface-800 shadow-[inset_0_2px_4px_rgba(0,0,0,0.3)] transition-all"
                                  />
                               </div>
                               <div className="text-[10px] text-surface-500 ml-1">
                                  De {money(montoParte)} {isSplitting ? 'de esta parte' : 'de la transacción'} · fecha del pago: {dia}
                               </div>
                            </div>

                            <div className="space-y-1.5">
                               <label className="text-[10px] uppercase font-bold text-sky-300/70 ml-1 block">¿A qué deudas va? <span className="normal-case font-medium text-surface-500">(opcional)</span></label>
                               {!draft.deudorId ? (
                                  <div className="text-xs text-surface-500 bg-surface-900/50 border border-dashed border-white/10 rounded-xl px-4 py-3">
                                     Elige primero con quién es el pago.
                                  </div>
                               ) : loadingPreview && !vistaPrevia ? (
                                  <div className="text-xs text-surface-500 flex items-center gap-2 px-1 py-2"><Loader2 size={13} className="animate-spin" /> Calculando el reparto…</div>
                               ) : deudasAbonables.length === 0 ? (
                                  <div className="text-xs text-surface-500 bg-surface-900/50 border border-dashed border-white/10 rounded-xl px-4 py-3">
                                     {draft.esMiPago ? 'No le debes nada pendiente.' : 'No te debe nada pendiente.'} Todo el pago quedará como saldo a favor.
                                  </div>
                               ) : (
                                  <div className="space-y-1.5 max-h-56 overflow-y-auto custom-scrollbar pr-1">
                                     {deudasAbonables.map(d => {
                                        const elegida = draft.pagoDeudasIds.includes(d.deuda_id);
                                        return (
                                           <button
                                              type="button"
                                              key={d.deuda_id}
                                              role="checkbox"
                                              aria-checked={elegida}
                                              onClick={() => alternarDeudaDelPago(d.deuda_id)}
                                              className={`w-full flex items-center justify-between gap-3 px-3 py-2 rounded-xl border text-left transition-all ${
                                                 elegida ? 'bg-sky-500/15 border-sky-500/40' : 'bg-surface-900 border-white/5 hover:border-white/15'
                                              }`}
                                           >
                                              <div className="flex items-center gap-2.5 min-w-0">
                                                 <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${elegida ? 'bg-sky-500 border-sky-400' : 'border-white/20'}`}>
                                                    {elegida && <Check size={11} className="text-white stroke-[3]" />}
                                                 </div>
                                                 <div className="min-w-0">
                                                    <div className="text-xs font-bold text-surface-100 truncate">{d.titulo}</div>
                                                    <div className="text-[10px] text-surface-500">{(d.fecha_gasto || '').slice(0, 10)} · falta {money(d.saldo_real)}</div>
                                                 </div>
                                              </div>
                                              {elegida && d.pago_planeado > 0.009 && (
                                                 <span className="font-mono text-xs font-bold text-sky-300 shrink-0">+{money(d.pago_planeado)}</span>
                                              )}
                                           </button>
                                        );
                                     })}
                                  </div>
                               )}
                            </div>

                            {draft.deudorId && vistaPrevia && (
                               <div className={`text-[11px] rounded-xl px-3 py-2.5 border leading-relaxed ${
                                  draft.pagoDeudasIds.length && vistaPrevia.sobrante > 0.01
                                     ? 'bg-amber-500/10 border-amber-500/20 text-amber-200'
                                     : 'bg-surface-900/60 border-white/5 text-surface-300'
                               }`}>
                                  {draft.pagoDeudasIds.length ? (
                                     <>
                                        Va {money(vistaPrevia.asignado)} a las deudas elegidas
                                        {vistaPrevia.sobrante > 0.01
                                           ? <> y quedan <strong>{money(vistaPrevia.sobrante)}</strong> como saldo a favor.</>
                                           : '.'}
                                        {vistaPrevia.cruce_monto > 0.01 && <> Después se aplica el cruce disponible.</>}
                                     </>
                                  ) : (
                                     <>
                                        Reparto automático, como en la app: {vistaPrevia.cruce_monto > 0.01
                                           ? <>primero se cruzan {money(vistaPrevia.cruce_monto)} entre las dos cuentas, </>
                                           : null}
                                        luego el pago va a las deudas más antiguas y lo que sobre queda como saldo a favor.
                                     </>
                                  )}
                               </div>
                            )}

                            {draft.pagoId && (
                               <div className="text-[11px] text-amber-300/90 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2 flex items-start gap-2">
                                  <AlertCircle size={13} className="mt-0.5 shrink-0" />
                                  Esta transacción ya estaba vinculada a un pago. Al guardar se registrará otro y el anterior quedará suelto.
                               </div>
                            )}
                         </div>
                      )}
                   </div>
                   )}
                </div>

                {/* Resumen de lo que pasará al guardar */}
                <div className={`rounded-2xl px-4 py-3 text-xs flex items-start gap-2.5 border ${
                   draftError
                      ? 'bg-amber-500/10 border-amber-500/25 text-amber-200'
                      : 'bg-surface-900/60 border-white/5 text-surface-300'
                }`}>
                   {draftError ? <AlertCircle size={15} className="mt-0.5 shrink-0" /> : <Check size={15} className="mt-0.5 shrink-0 text-emerald-400" />}
                   <span className="leading-relaxed">{resumenDeuda}</span>
                </div>

                {debtError && (
                   <div className="text-xs text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-xl px-3 py-2.5 flex items-center gap-2">
                      <AlertCircle size={14} /> {debtError}
                   </div>
                )}
              </div>

              <footer className="flex-none px-6 py-4 border-t border-white/5 bg-surface-900/60 flex justify-end">
                <button
                  onClick={() => setShowDebtModal(false)}
                  className={`px-6 py-3 rounded-xl text-xs font-bold uppercase tracking-wider text-white transition-colors border border-white/10 flex items-center gap-2 ${esPago ? 'bg-sky-600 hover:bg-sky-500' : 'bg-purple-600 hover:bg-purple-500'}`}
                >
                  <Check size={16} className="stroke-[3]" /> Listo
                </button>
              </footer>
            </div>
          </div>
        )}

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
