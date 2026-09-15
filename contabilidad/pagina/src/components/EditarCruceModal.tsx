import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { X, RefreshCw, AlertTriangle, Undo2, Calendar, Info } from 'lucide-react';
import { api } from '../services/api';
import type { EdicionCruce, EstadoCuentaMovimiento } from '../services/api';
import { fmt } from '../utils/format';

const fecha = (s: string | null) =>
  s ? new Date(`${s.slice(0, 10)}T00:00:00`).toLocaleDateString('es-EC', { day: '2-digit', month: 'short' }) : '—';

const nuevaIdemKey = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = (Math.random() * 16) | 0;
        return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
      });

const detalleError = (e: unknown) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  ?? (e instanceof Error ? e.message : 'Error desconocido');

/**
 * Sacar deudas del cruce de la última operación.
 *
 * Las deudas marcadas salen del cruce y quedan pendientes; el cruce se recorta para que
 * los dos lados sigan sumando lo mismo. El pago real no se toca. Lo que se reabre se
 * vuelve a cruzar en el siguiente pago.
 */
export function EditarCruceModal({ cruce, nombre, onClose }: {
  cruce: EstadoCuentaMovimiento; nombre: string; onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const cruceId = cruce.cruce_id!;
  const [excluidas, setExcluidas] = useState<Set<string>>(new Set());
  const [vista, setVista] = useState<EdicionCruce | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);
  // Una por apertura del modal: reintentar el guardado no repite la edición.
  const [idemKey] = useState(nuevaIdemKey);

  const lados = useMemo(() => ({
    teDeben: cruce.lados?.te_deben.items ?? [],
    tuDebes: cruce.lados?.tu_debes.items ?? [],
  }), [cruce]);
  const todas = useMemo(() => [...lados.teDeben, ...lados.tuDebes].map(i => i.deuda_id), [lados]);

  // Vista previa: el mismo RPC que guarda, en modo simulación.
  useEffect(() => {
    setError(null);
    if (excluidas.size === 0) { setVista(null); setCargando(false); return; }
    let vigente = true;
    setCargando(true);
    const t = setTimeout(() => {
      api.previewEditarCruce(cruceId, [...excluidas])
        .then(v => { if (vigente) setVista(v); })
        .catch(e => { if (vigente) { setVista(null); setError(detalleError(e)); } })
        .finally(() => { if (vigente) setCargando(false); });
    }, 250);
    return () => { vigente = false; clearTimeout(t); };
  }, [cruceId, excluidas]);

  const alternar = (id: string) => setExcluidas(prev => {
    const s = new Set(prev);
    if (s.has(id)) s.delete(id); else s.add(id);
    return s;
  });

  const guardar = async () => {
    setGuardando(true);
    setError(null);
    try {
      await api.editarCruce(cruceId, [...excluidas], idemKey);
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

  const porId = new Map((vista?.items ?? []).map(i => [i.deuda_id, i]));
  const cubiertasPorFavor = (vista?.items ?? [])
    .filter(i => i.excluida && i.saldo_real <= 0.01 && i.abono_saldo_favor > 0.01);
  const recortadas = (vista?.items ?? []).filter(i => !i.excluida && i.despues < i.antes - 0.01);
  const montoAntes = cruce.monto_cruzado ?? 0;
  const deshaceTodo = excluidas.size === todas.length;

  const lado = (titulo: string, tone: 'indigo' | 'rose', items: typeof lados.teDeben) => {
    const text = tone === 'indigo' ? 'text-indigo-300' : 'text-rose-300';
    return (
      <div className="rounded-xl bg-surface-950/40 border border-white/5 p-3">
        <div className={`text-[10px] font-bold uppercase tracking-wider mb-2 ${text}`}>{titulo}</div>
        {items.length === 0 ? (
          <div className="text-[11px] text-surface-600 py-1">Sin deudas de este lado</div>
        ) : (
          <div className="space-y-1">
            {items.map(it => {
              const fuera = excluidas.has(it.deuda_id);
              const v = porId.get(it.deuda_id);
              const recortada = !!v && !v.excluida && v.despues < v.antes - 0.01;
              return (
                <label
                  key={it.deuda_id}
                  className={`flex items-center gap-2.5 px-2 py-1.5 rounded-lg cursor-pointer transition-colors border ${
                    fuera ? 'bg-amber-500/[0.08] border-amber-500/30' : 'border-transparent hover:bg-white/[0.03]'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={fuera}
                    onChange={() => alternar(it.deuda_id)}
                    className="accent-amber-400 shrink-0"
                  />
                  <div className="min-w-0 flex-1">
                    <div className={`text-xs font-semibold truncate ${fuera ? 'text-amber-200' : 'text-surface-200'}`}>{it.titulo}</div>
                    <div className="text-[10px] text-surface-500 flex items-center gap-1">
                      <Calendar size={9} />{fecha(it.fecha_gasto)}
                      {fuera && v && <span className="text-amber-300/90">· queda pendiente ${fmt(v.saldo_real)}</span>}
                      {recortada && <span className="text-sky-300/90">· recortada</span>}
                    </div>
                  </div>
                  <div className="text-right shrink-0 font-mono text-[11px]">
                    {v && Math.abs(v.despues - v.antes) > 0.01 ? (
                      <>
                        <span className="text-surface-500 line-through mr-1.5">${fmt(it.aplicado)}</span>
                        <span className={v.despues > 0.01 ? text : 'text-surface-400'}>${fmt(v.despues)}</span>
                      </>
                    ) : (
                      <span className={text}>${fmt(it.aplicado)}</span>
                    )}
                  </div>
                </label>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={guardando ? undefined : onClose} />
      <div className="relative w-full max-w-3xl max-h-[88vh] flex flex-col bg-surface-950 border border-white/10 rounded-3xl shadow-2xl overflow-hidden">
        <header className="flex-none px-6 py-4 border-b border-white/5 bg-surface-900/50 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-2.5 rounded-xl bg-sky-500/15 text-sky-300 shrink-0"><RefreshCw size={20} /></div>
            <div className="min-w-0">
              <h2 className="text-lg font-bold text-white">Editar cruce con {nombre}</h2>
              <p className="text-xs text-surface-400">
                {fecha(cruce.fecha)} · ${fmt(montoAntes)} cruzados · marca las deudas que no querías cruzar todavía
              </p>
            </div>
          </div>
          <button onClick={onClose} disabled={guardando} className="p-2 rounded-xl bg-surface-800 hover:bg-surface-700 text-surface-400 hover:text-white border border-white/5">
            <X size={18} />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-4">
          <div className="flex items-start gap-2 text-[11px] text-surface-400 bg-surface-900/40 border border-white/5 rounded-xl px-3 py-2">
            <Info size={13} className="text-sky-300 shrink-0 mt-px" />
            <span>
              Las deudas que saques quedan pendientes y se vuelven a cruzar en el siguiente pago.
              El pago no cambia. Un cruce tiene que cuadrar: el otro lado se recorta por la
              deuda más reciente.
            </span>
          </div>

          <div className="flex items-center justify-end">
            <button
              onClick={() => setExcluidas(deshaceTodo ? new Set() : new Set(todas))}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-surface-300 hover:text-white border border-white/5 flex items-center gap-1.5"
            >
              <Undo2 size={13} />{deshaceTodo ? 'Quitar selección' : 'Deshacer el cruce entero'}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {lado('Te deben', 'indigo', lados.teDeben)}
            {lado('Tú debes', 'rose', lados.tuDebes)}
          </div>

          {/* Resultado */}
          <div className="rounded-xl border border-sky-500/20 bg-sky-500/[0.04] px-4 py-3 space-y-2 min-h-[64px]">
            {excluidas.size === 0 ? (
              <div className="text-xs text-surface-500">Marca al menos una deuda para ver cómo queda.</div>
            ) : cargando && !vista ? (
              <div className="text-xs text-surface-500">Calculando…</div>
            ) : vista ? (
              <>
                <div className="flex items-end justify-between gap-3">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-sky-400/80">
                    {vista.eliminado ? 'El cruce se deshace' : 'El cruce queda en'}
                  </span>
                  <div className={`font-mono font-bold text-xl ${cargando ? 'opacity-50' : ''}`}>
                    <span className="text-surface-500 line-through text-sm mr-2">${fmt(vista.monto_antes)}</span>
                    <span className="text-sky-300">${fmt(vista.monto_despues)}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between text-[11px] text-surface-400">
                  <span>Por cruzar en el siguiente pago</span>
                  <span className="font-mono text-sky-300/90">${fmt(vista.cruce_disponible)}</span>
                </div>
                {recortadas.length > 0 && (
                  <div className="text-[11px] text-surface-400">
                    Para cuadrar se recorta: {recortadas.map(i => `${i.titulo} ($${fmt(i.antes)} → $${fmt(i.despues)})`).join(', ')}.
                  </div>
                )}
                {cubiertasPorFavor.length > 0 && (
                  <div className="flex items-start gap-1.5 text-[11px] text-amber-300 bg-amber-500/[0.08] border border-amber-500/25 rounded-lg px-2.5 py-1.5">
                    <AlertTriangle size={12} className="shrink-0 mt-px" />
                    <span>
                      {cubiertasPorFavor.map(i => i.titulo).join(', ')} {cubiertasPorFavor.length === 1 ? 'se sigue viendo saldada' : 'se siguen viendo saldadas'}:
                      el saldo a favor de quien pagó la vuelve a cubrir.
                    </span>
                  </div>
                )}
              </>
            ) : null}
            {error && (
              <div className="flex items-start gap-1.5 text-[11px] text-rose-300">
                <AlertTriangle size={12} className="shrink-0 mt-px" />{error}
              </div>
            )}
          </div>
        </div>

        <footer className="flex-none px-6 py-4 border-t border-white/5 bg-surface-900/50 flex items-center justify-end gap-2">
          <button onClick={onClose} disabled={guardando} className="px-4 py-2 rounded-xl text-sm font-semibold text-surface-300 hover:text-white bg-surface-800 hover:bg-surface-700 border border-white/5">
            Cancelar
          </button>
          <button
            onClick={guardar}
            disabled={!vista || cargando || guardando || excluidas.size === 0}
            className="px-4 py-2 rounded-xl text-sm font-bold bg-sky-500/90 hover:bg-sky-400 text-surface-950 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {guardando ? 'Guardando…' : vista?.eliminado ? 'Deshacer cruce' : 'Guardar cruce'}
          </button>
        </footer>
      </div>
    </div>
  );
}
