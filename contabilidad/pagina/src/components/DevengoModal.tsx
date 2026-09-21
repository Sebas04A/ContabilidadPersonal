import { useEffect, useMemo, useState } from 'react';
import { X, Trash2, Flame, Sparkles, Tag as TagIcon, AlertCircle, Info } from 'lucide-react';
import type { SupabaseDebt, TransactionUpdate } from '../services/api';
import { useEtiquetarDeuda, useQuitarDevengo, useTags } from '../hooks/useTransactions';
import { CATEGORIAS_CON_VACIO } from '../utils/categorias';
import { parseTags } from '../utils/tags';
import { money } from '../utils/format';
import { detalleError } from '../utils/requests';

const fecha = (s: string) =>
  new Date(`${(s || '').slice(0, 10)}T00:00:00`).toLocaleDateString('es-EC', {
    day: '2-digit', month: 'long', year: 'numeric',
  });

/**
 * Etiquetar una deuda mía para que cuente como gasto (devengo).
 *
 * Cuando alguien paga algo por mí no hay movimiento en mis cuentas, así que no
 * hay transacción que etiquetar y ese consumo no existe en el análisis. Acá se
 * le pone la etiqueta a la deuda misma, y el gasto queda fechado el día del
 * consumo, no el día en que le devuelva la plata.
 *
 * Lo que este modal **no** toca: la deuda en Supabase, su monto, el cruce de
 * cuentas ni el patrimonio. Lo que debo ya pesa en `DEUDA_ACUMULADA`; lo único
 * que se decide acá es si además fue un gasto mío.
 */
export function DevengoModal({ deuda, devengada, tieneTransaccion, onClose }: {
  deuda: SupabaseDebt;
  /** Hay una transacción mía apuntando a esta deuda: su gasto ya está contado ahí. */
  tieneTransaccion?: boolean;
  /** Si ya tenía etiqueta: habilita "quitar del gasto". */
  devengada?: { categoria?: string | null; tags?: string | null; prioridad?: string | null;
                felicidad?: number | null; nombre_limpio?: string | null; nota?: string | null } | null;
  onClose: () => void;
}) {
  const deudaId = String(deuda.ID);
  const etiquetar = useEtiquetarDeuda();
  const quitar = useQuitarDevengo();
  const { data: tagsExistentes } = useTags();

  const [form, setForm] = useState<TransactionUpdate>({});
  const [tagInput, setTagInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [confirmandoBaja, setConfirmandoBaja] = useState(false);

  useEffect(() => {
    setForm({
      nombre_limpio: devengada?.nombre_limpio || deuda.DESCRIPCION || '',
      categoria: devengada?.categoria || '---',
      tags: devengada?.tags || '',
      prioridad: devengada?.prioridad || '---',
      felicidad: devengada?.felicidad ?? 0,
      nota: devengada?.nota || '',
      revisado: true,
    });
    setError(null);
    setConfirmandoBaja(false);
  }, [deudaId]); // eslint-disable-line react-hooks/exhaustive-deps

  const tags = useMemo(() => parseTags(form.tags), [form.tags]);
  const sugerencias = useMemo(() => {
    const q = tagInput.trim().toLowerCase();
    if (!q) return [];
    return (tagsExistentes ?? [])
      .filter(t => t.toLowerCase().includes(q) && !tags.includes(t))
      .slice(0, 6);
  }, [tagInput, tagsExistentes, tags]);

  const setTags = (lista: string[]) => setForm(f => ({ ...f, tags: lista.join(', ') }));
  const agregarTag = (t: string) => {
    const tag = t.trim();
    if (tag && !tags.includes(tag)) setTags([...tags, tag]);
    setTagInput('');
  };

  const guardar = async () => {
    setError(null);
    try {
      await etiquetar.mutateAsync({ deudaId, updates: form });
      onClose();
    } catch (e) {
      setError(detalleError(e));
    }
  };

  const quitarDelGasto = async () => {
    setError(null);
    try {
      await quitar.mutateAsync(deudaId);
      onClose();
    } catch (e) {
      setError(detalleError(e));
    }
  };

  const ocupado = etiquetar.isPending || quitar.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-3xl border border-white/10 bg-surface-900 shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Cabecera: qué deuda es */}
        <div className="sticky top-0 z-10 flex items-start gap-3 p-5 border-b border-white/5 bg-surface-900">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <Sparkles size={14} className="text-amber-400 shrink-0" />
              <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400">Deuda como gasto</span>
            </div>
            <h2 className="text-lg font-bold text-white truncate">{deuda.DESCRIPCION}</h2>
            <p className="text-xs text-surface-400 mt-0.5">
              {money(deuda.MONTO)} · {fecha(deuda.FECHA)} · pagó <span className="text-surface-200">{deuda.DEUDOR_NOMBRE}</span>
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-surface-400 hover:text-white hover:bg-white/5 transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {tieneTransaccion && (
            <div className="flex gap-2.5 p-3 rounded-xl bg-amber-500/[0.08] border border-amber-500/30">
              <AlertCircle size={15} className="text-amber-400 shrink-0 mt-0.5" />
              <p className="text-[11.5px] leading-relaxed text-amber-100/90">
                <span className="font-semibold">Ojo:</span> ya hay una transacción tuya vinculada a esta deuda.
                Esa plata pasó por tu cuenta, así que el gasto probablemente ya está contado ahí.
                Contarla otra vez acá la duplicaría.
              </p>
            </div>
          )}

          {/* Qué significa esto, en una línea */}
          <div className="flex gap-2.5 p-3 rounded-xl bg-sky-500/[0.06] border border-sky-500/20">
            <Info size={15} className="text-sky-400 shrink-0 mt-0.5" />
            <p className="text-[11.5px] leading-relaxed text-surface-300">
              Este consumo cuenta como gasto el <span className="text-white font-semibold">{fecha(deuda.FECHA)}</span>,
              el día en que pasó. La deuda no cambia: sigue viva, se sigue cruzando y sigue pesando en tu patrimonio igual que ahora.
            </p>
          </div>

          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-surface-400 mb-1.5">Nombre</label>
            <input
              type="text"
              value={form.nombre_limpio || ''}
              onChange={e => setForm(f => ({ ...f, nombre_limpio: e.target.value }))}
              placeholder={deuda.DESCRIPCION}
              className="w-full px-3 py-2 rounded-xl bg-surface-800/60 border border-white/10 text-sm text-white placeholder-surface-600 focus:outline-none focus:border-indigo-500/60"
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-surface-400 mb-1.5">Categoría</label>
            <select
              value={form.categoria || '---'}
              onChange={e => setForm(f => ({ ...f, categoria: e.target.value }))}
              className="w-full px-3 py-2 rounded-xl bg-surface-800/60 border border-white/10 text-sm text-white focus:outline-none focus:border-indigo-500/60"
            >
              {CATEGORIAS_CON_VACIO.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          {/* Tags */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-surface-400 mb-1.5">Tags</label>
            {tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {tags.map(t => (
                  <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-[11px] font-medium text-indigo-200">
                    <TagIcon size={10} />
                    {t}
                    <button onClick={() => setTags(tags.filter(x => x !== t))} className="ml-0.5 text-indigo-300/60 hover:text-white">
                      <X size={11} />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <input
              type="text"
              value={tagInput}
              onChange={e => setTagInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); agregarTag(tagInput); } }}
              placeholder="Brasil_2026…  (Enter para agregar)"
              className="w-full px-3 py-2 rounded-xl bg-surface-800/60 border border-white/10 text-sm text-white placeholder-surface-600 focus:outline-none focus:border-indigo-500/60"
            />
            {sugerencias.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {sugerencias.map(t => (
                  <button key={t} onClick={() => agregarTag(t)}
                    className="px-2 py-0.5 rounded-lg bg-white/5 border border-white/10 text-[11px] text-surface-300 hover:border-indigo-500/40 hover:text-white transition-colors">
                    {t}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Prioridad */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-surface-400 mb-1.5">¿Necesidad o deseo?</label>
            <div className="grid grid-cols-2 gap-2">
              {(['Necesidad', 'Deseo'] as const).map(p => (
                <button
                  key={p}
                  onClick={() => setForm(f => ({ ...f, prioridad: f.prioridad === p ? '---' : p }))}
                  className={`flex items-center justify-center gap-2 py-2 rounded-xl border transition-all ${
                    form.prioridad === p
                      ? 'bg-amber-500/15 border-amber-400/50 text-amber-200'
                      : 'bg-surface-800/40 border-white/10 text-surface-400 hover:text-white hover:border-white/20'
                  }`}
                >
                  <Flame size={15} className={form.prioridad === p ? 'fill-current text-amber-400' : ''} />
                  <span className="text-xs font-bold uppercase tracking-wider">{p}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Felicidad */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-[11px] font-bold uppercase tracking-wider text-surface-400">Felicidad</label>
              <span className="text-xs font-mono font-bold text-surface-400 bg-white/5 px-2 py-0.5 rounded">{form.felicidad ?? 0}/9</span>
            </div>
            <input
              type="range" min={0} max={9} step={1}
              value={form.felicidad ?? 0}
              onChange={e => setForm(f => ({ ...f, felicidad: parseInt(e.target.value) }))}
              className={`w-full h-2 rounded-lg appearance-none cursor-pointer ${
                (form.felicidad ?? 0) >= 6 ? 'bg-emerald-500/20 accent-emerald-500'
                  : (form.felicidad ?? 0) === 5 ? 'bg-surface-600/20 accent-surface-500'
                  : (form.felicidad ?? 0) > 0 ? 'bg-rose-500/20 accent-rose-500'
                  : 'bg-white/10 accent-surface-400'}`}
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-surface-400 mb-1.5">Nota</label>
            <textarea
              value={form.nota || ''}
              onChange={e => setForm(f => ({ ...f, nota: e.target.value }))}
              rows={2}
              placeholder="Qué fue, con quién…"
              className="w-full px-3 py-2 rounded-xl bg-surface-800/60 border border-white/10 text-sm text-white placeholder-surface-600 resize-none focus:outline-none focus:border-indigo-500/60"
            />
          </div>

          {error && (
            <div className="flex items-start gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30">
              <AlertCircle size={15} className="text-rose-400 shrink-0 mt-0.5" />
              <p className="text-xs text-rose-200">{error}</p>
            </div>
          )}
        </div>

        {/* Pie */}
        <div className="sticky bottom-0 flex items-center gap-2 p-4 border-t border-white/5 bg-surface-900">
          {devengada && (
            confirmandoBaja ? (
              <button
                onClick={quitarDelGasto}
                disabled={ocupado}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-rose-500/20 border border-rose-500/40 text-xs font-bold text-rose-200 hover:bg-rose-500/30 transition-colors disabled:opacity-50"
              >
                <Trash2 size={14} />
                ¿Seguro? Quitar
              </button>
            ) : (
              <button
                onClick={() => setConfirmandoBaja(true)}
                disabled={ocupado}
                title="Deja de contar como gasto. La deuda no se borra."
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-white/10 text-xs font-semibold text-surface-400 hover:text-rose-200 hover:border-rose-500/40 transition-colors disabled:opacity-50"
              >
                <Trash2 size={14} />
                Quitar del gasto
              </button>
            )
          )}
          <div className="flex-1" />
          <button onClick={onClose} className="px-4 py-2 rounded-xl text-xs font-semibold text-surface-400 hover:text-white transition-colors">
            Cancelar
          </button>
          <button
            onClick={guardar}
            disabled={ocupado}
            className="px-5 py-2 rounded-xl bg-indigo-500 text-xs font-bold text-white hover:bg-indigo-400 transition-colors disabled:opacity-50"
          >
            {etiquetar.isPending ? 'Guardando…' : devengada ? 'Guardar' : 'Contar como gasto'}
          </button>
        </div>
      </div>
    </div>
  );
}
