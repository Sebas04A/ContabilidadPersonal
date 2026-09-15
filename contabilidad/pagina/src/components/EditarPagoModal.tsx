import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { X, Pencil, AlertTriangle, Info, Calendar, StickyNote } from 'lucide-react';
import { api } from '../services/api';
import { fmt } from '../utils/format';
import { nuevaIdemKey, detalleError } from '../utils/requests';

const MAX_NOTA = 500;

/** Lo mínimo del pago que el modal necesita: sirve para el ledger y para la lista de pagos. */
export interface PagoEditable {
  id: string;
  fecha: string | null;
  nota?: string | null;
  monto: number;
  esMiPago: boolean;
}

/**
 * Cambiar la fecha y la nota de un pago.
 *
 * El monto y el reparto no se tocan. Si el pago disparó un cruce, el cruce se mueve con
 * él a la fecha nueva.
 */
export function EditarPagoModal({ pago, nombre, onClose }: {
  pago: PagoEditable; nombre: string; onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const fechaInicial = (pago.fecha ?? '').slice(0, 10);
  const notaInicial = pago.nota ?? '';
  const [fecha, setFecha] = useState(fechaInicial);
  const [nota, setNota] = useState(notaInicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Una por apertura del modal: reintentar el guardado no repite la edición.
  const [idemKey] = useState(nuevaIdemKey);

  const cambiaFecha = !!fecha && fecha !== fechaInicial;
  const cambiaNota = nota.trim() !== notaInicial.trim();
  const hayCambios = cambiaFecha || cambiaNota;

  const guardar = async () => {
    setGuardando(true);
    setError(null);
    try {
      await api.editarPago(pago.id, {
        ...(cambiaFecha ? { fecha_pago: fecha } : {}),
        ...(cambiaNota ? { nota: nota.trim() } : {}),
      }, idemKey);
      for (const key of ['supabase-payments', 'supabase-debts', 'deudores', 'estado-cuenta',
                         'dashboard-chart', 'dashboard-variations']) {
        queryClient.invalidateQueries({ queryKey: [key] });
      }
      onClose();
    } catch (e) {
      setError(detalleError(e));
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={guardando ? undefined : onClose} />
      <div className="relative w-full max-w-lg flex flex-col bg-surface-950 border border-white/10 rounded-3xl shadow-2xl overflow-hidden">
        <header className="flex-none px-6 py-4 border-b border-white/5 bg-surface-900/50 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-2.5 rounded-xl bg-emerald-500/15 text-emerald-300 shrink-0"><Pencil size={20} /></div>
            <div className="min-w-0">
              <h2 className="text-lg font-bold text-white truncate">
                Editar {pago.esMiPago ? `pago a ${nombre}` : `pago de ${nombre}`}
              </h2>
              <p className="text-xs text-surface-400">${fmt(pago.monto)} · el monto y a qué deudas fue no cambian</p>
            </div>
          </div>
          <button onClick={onClose} disabled={guardando} className="p-2 rounded-xl bg-surface-800 hover:bg-surface-700 text-surface-400 hover:text-white border border-white/5">
            <X size={18} />
          </button>
        </header>

        <div className="p-6 space-y-4">
          <label className="block">
            <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1.5">
              <Calendar size={11} />Fecha del pago
            </span>
            <input
              type="date"
              value={fecha}
              onChange={e => setFecha(e.target.value)}
              className="w-full h-10 bg-surface-900/60 border border-white/10 rounded-xl px-3 text-sm text-surface-100 focus:outline-none focus:border-emerald-500/40 [color-scheme:dark]"
            />
          </label>

          <label className="block">
            <span className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-surface-400 mb-1.5">
              <span className="flex items-center gap-1.5"><StickyNote size={11} />Nota</span>
              <span className={`font-mono normal-case tracking-normal ${nota.length > MAX_NOTA ? 'text-rose-300' : 'text-surface-600'}`}>
                {nota.length}/{MAX_NOTA}
              </span>
            </span>
            <textarea
              value={nota}
              onChange={e => setNota(e.target.value)}
              rows={3}
              placeholder="Ej.: transferencia del almuerzo, en efectivo…"
              className="w-full bg-surface-900/60 border border-white/10 rounded-xl px-3 py-2 text-sm text-surface-100 placeholder:text-surface-600 focus:outline-none focus:border-emerald-500/40 resize-none"
            />
          </label>

          {cambiaFecha && (
            <div className="flex items-start gap-2 text-[11px] text-surface-400 bg-surface-900/40 border border-white/5 rounded-xl px-3 py-2">
              <Info size={13} className="text-sky-300 shrink-0 mt-px" />
              <span>
                Cambia dónde se ve el pago y qué día cuenta en el dashboard. Ningún saldo se mueve.
                Si este pago hizo un cruce, el cruce pasa a la misma fecha.
              </span>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-1.5 text-[11px] text-rose-300">
              <AlertTriangle size={12} className="shrink-0 mt-px" />{error}
            </div>
          )}
        </div>

        <footer className="flex-none px-6 py-4 border-t border-white/5 bg-surface-900/50 flex items-center justify-end gap-2">
          <button onClick={onClose} disabled={guardando} className="px-4 py-2 rounded-xl text-sm font-semibold text-surface-300 hover:text-white bg-surface-800 hover:bg-surface-700 border border-white/5">
            Cancelar
          </button>
          <button
            onClick={guardar}
            disabled={!hayCambios || guardando || !fecha || nota.length > MAX_NOTA}
            className="px-4 py-2 rounded-xl text-sm font-bold bg-emerald-500/90 hover:bg-emerald-400 text-surface-950 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {guardando ? 'Guardando…' : 'Guardar'}
          </button>
        </footer>
      </div>
    </div>
  );
}
