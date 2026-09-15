import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  GitBranch,
  RefreshCw,
  Scissors,
  Sparkles,
} from 'lucide-react';
import {
  investmentsApi,
  type DetectedPosition,
  type Portfolio,
  type PortfolioSuggestion,
} from '../../services/investments';
import { Badge, EmptyState, Section, Spinner, money, pct } from './shared';

/**
 * The reconciliation screen: what the bank says vs. what is saved. Nothing here writes
 * until you press a button — `POST /detect` is read-only by design.
 */
export function ReconcileTab({ portfolios }: { portfolios: Portfolio[] }) {
  const queryClient = useQueryClient();
  const [asignaciones, setAsignaciones] = useState<Record<string, string>>({});
  const [mensajeRegeneracion, setMensajeRegeneracion] = useState<string | null>(null);
  const [errorRegeneracion, setErrorRegeneracion] = useState<string | null>(null);
  const [mostrarDetalleReg, setMostrarDetalleReg] = useState(false);

  const { data: diff, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['inv-detect'],
    queryFn: investmentsApi.detect,
  });

  const { data: regPreview } = useQuery({
    queryKey: ['inv-regeneration-preview'],
    queryFn: () => investmentsApi.previewRegeneration(),
  });

  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ['inv-detect'] });
    queryClient.invalidateQueries({ queryKey: ['inv-positions'] });
    queryClient.invalidateQueries({ queryKey: ['inv-summary'] });
    queryClient.invalidateQueries({ queryKey: ['inv-timeline'] });
    queryClient.invalidateQueries({ queryKey: ['inv-portfolios'] });
    queryClient.invalidateQueries({ queryKey: ['inv-regeneration-preview'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
  };

  const regenerarMut = useMutation({
    mutationFn: (portafolioId?: string) => investmentsApi.regeneratePayments(portafolioId),
    onSuccess: (res) => {
      invalidar();
      setErrorRegeneracion(null);
      const borrados = res.pagos_borrados ?? 0;
      const escritos = res.pagos_escritos ?? 0;
      setMensajeRegeneracion(
        `Pagos fijos regenerados con éxito: ${borrados} pagos anteriores reemplazados por ${escritos} pagos actuales. El Dashboard y el patrimonio quedaron sincronizados.`
      );
      setTimeout(() => setMensajeRegeneracion(null), 9000);
    },
    onError: (err: any) => {
      setErrorRegeneracion(err?.response?.data?.detail || err?.message || 'Error al regenerar los pagos.');
      setTimeout(() => setErrorRegeneracion(null), 9000);
    },
  });

  const confirmar = useMutation({
    mutationFn: (req: Parameters<typeof investmentsApi.applyDetection>[0]) =>
      investmentsApi.applyDetection(req),
    onSuccess: () => {
      setAsignaciones({});
      invalidar();
      // Regenerar automáticamente los pagos fijos tras confirmar posiciones
      regenerarMut.mutate(undefined);
    },
  });

  if (isLoading) return <Spinner />;
  if (!diff) return <EmptyState>No se pudo correr la conciliación.</EmptyState>;

  const { resumen } = diff;
  const todoAlDia = resumen.nuevas === 0 && resumen.cambiadas === 0 && resumen.huerfanas === 0
    && resumen.solo_guardadas === 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex gap-2 flex-wrap">
          <Chip label="Detectadas" valor={resumen.detectadas} />
          <Chip label="Guardadas" valor={resumen.guardadas} />
          <Chip label="Al día" valor={resumen.iguales} tone={resumen.iguales ? 'emerald' : 'neutral'} />
          <Chip label="Nuevas" valor={resumen.nuevas} tone={resumen.nuevas ? 'violet' : 'neutral'} />
          <Chip label="Cambiadas" valor={resumen.cambiadas} tone={resumen.cambiadas ? 'amber' : 'neutral'} />
          <Chip label="Huérfanas" valor={resumen.huerfanas} tone={resumen.huerfanas ? 'amber' : 'neutral'} />
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-3.5 h-9 rounded-lg bg-surface-800 hover:bg-primary-600/20 text-surface-300 hover:text-primary-300 text-xs font-bold transition-all disabled:opacity-50"
        >
          <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
          Volver a conciliar
        </button>
      </div>

      {todoAlDia && (
        <div className="p-4 rounded-xl bg-emerald-500/[0.06] border border-emerald-500/20 flex items-center gap-3">
          <Check size={18} className="text-emerald-400 shrink-0" />
          <p className="text-sm text-emerald-200">
            Todo cuadra: las {resumen.detectadas} posiciones del extracto están guardadas y sin
            cancelaciones sueltas.
          </p>
        </div>
      )}

      {/* Aviso / Feedback de regeneración exitosa */}
      {mensajeRegeneracion && (
        <div className="p-4 rounded-xl bg-emerald-500/[0.08] border border-emerald-500/25 flex items-center justify-between gap-3 text-xs text-emerald-200 animate-in fade-in duration-200">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
            <span>{mensajeRegeneracion}</span>
          </div>
          <button
            onClick={() => setMensajeRegeneracion(null)}
            className="text-emerald-400/60 hover:text-emerald-300 font-bold px-1"
          >
            ✕
          </button>
        </div>
      )}

      {/* Error si algo falló */}
      {errorRegeneracion && (
        <div className="p-4 rounded-xl bg-rose-500/[0.08] border border-rose-500/25 flex items-center justify-between gap-3 text-xs text-rose-200 animate-in fade-in duration-200">
          <div className="flex items-center gap-2.5">
            <AlertTriangle size={16} className="text-rose-400 shrink-0" />
            <span>{errorRegeneracion}</span>
          </div>
          <button
            onClick={() => setErrorRegeneracion(null)}
            className="text-rose-400/60 hover:text-rose-300 font-bold px-1"
          >
            ✕
          </button>
        </div>
      )}

      {/* Alerta de pagos desactualizados en el Dashboard */}
      {regPreview && !regPreview.sin_cambios && (
        <div className="p-5 rounded-2xl bg-amber-500/[0.07] border border-amber-500/25 shadow-lg relative overflow-hidden">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex items-start gap-3 max-w-2xl">
              <div className="p-2.5 rounded-xl bg-amber-500/20 text-amber-300 shrink-0 mt-0.5">
                <AlertTriangle size={18} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  Pagos fijos de inversión desactualizados en el Dashboard
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    Requiere regenerar
                  </span>
                </h3>
                <p className="text-xs text-surface-300 mt-1 leading-relaxed">
                  Las posiciones guardadas difieren de las cadenas de pagos fijos que lee el Dashboard.
                  Regenerar actualizará los tramos en <code className="font-mono text-amber-200/90 text-[11px]">grupos.csv</code> sin tocar los extractos bancarios.
                </p>

                {/* Portafolios con cambios */}
                <div className="mt-3 flex flex-wrap gap-2">
                  {regPreview.por_portafolio
                    .filter(p => !p.sin_cambios)
                    .map(p => (
                      <div
                        key={p.portafolio_id}
                        className="px-3 py-1.5 rounded-lg bg-surface-950/60 border border-amber-500/30 text-xs flex items-center gap-2"
                      >
                        <span className="font-bold text-white">{p.portafolio}:</span>
                        <span className="text-surface-300">
                          {p.pagos_ahora} → <span className="text-emerald-400 font-semibold">{p.pagos_nuevos}</span> pagos
                        </span>
                        <span className="text-surface-500 font-mono">·</span>
                        <span className="text-amber-300 font-mono text-[11px]">
                          {p.dias_que_cambian} días afectados
                        </span>
                        {p.max_desvio !== undefined && p.max_desvio > 0 && (
                          <span className="text-surface-400 text-[11px]">
                            (máx ±{money(p.max_desvio)})
                          </span>
                        )}
                      </div>
                    ))}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0 self-center">
              <button
                onClick={() => setMostrarDetalleReg(!mostrarDetalleReg)}
                className="px-3 py-2 rounded-xl bg-surface-800 hover:bg-surface-700 text-surface-300 text-xs font-semibold flex items-center gap-1.5 transition-all"
              >
                {mostrarDetalleReg ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                {mostrarDetalleReg ? 'Ocultar detalle' : 'Ver detalle'}
              </button>
              <button
                onClick={() => regenerarMut.mutate(undefined)}
                disabled={regenerarMut.isPending}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-surface-950 font-bold text-xs shadow-lg shadow-amber-500/20 transition-all disabled:opacity-50"
              >
                <RefreshCw size={14} className={regenerarMut.isPending ? 'animate-spin' : ''} />
                {regenerarMut.isPending ? 'Regenerando pagos...' : 'Regenerar pagos del Dashboard'}
              </button>
            </div>
          </div>

          {/* Detalle expandible */}
          {mostrarDetalleReg && (
            <div className="mt-4 pt-4 border-t border-white/[0.06] text-xs space-y-3 animate-in fade-in duration-150">
              <h4 className="font-semibold text-surface-200">Días con mayor desvío detectados en la previa:</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 max-h-48 overflow-y-auto custom-scrollbar">
                {regPreview.por_portafolio
                  .filter(p => !p.sin_cambios && p.peores_dias && p.peores_dias.length > 0)
                  .flatMap(p =>
                    (p.peores_dias || []).map((dia, idx) => (
                      <div
                        key={`${p.portafolio_id}-${idx}`}
                        className="bg-surface-950/70 border border-white/5 rounded-lg px-3 py-1.5 flex items-center justify-between text-[11px]"
                      >
                        <span className="text-surface-400 font-mono">{dia.fecha} ({p.portafolio})</span>
                        <span className="font-mono text-amber-300 font-bold">±{money(dia.desvio)}</span>
                      </div>
                    ))
                  )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Si los pagos ya están al día */}
      {regPreview && regPreview.sin_cambios && !mensajeRegeneracion && (
        <div className="px-4 py-2.5 rounded-xl bg-surface-900/40 border border-white/[0.05] flex items-center justify-between gap-3 text-xs text-surface-400 flex-wrap">
          <div className="flex items-center gap-2">
            <Check size={14} className="text-emerald-400 shrink-0" />
            <span>
              Pagos fijos de inversión al día en el Dashboard{' '}
              <span className="text-surface-500 font-mono">
                ({regPreview.por_portafolio.map(p => `${p.portafolio}: ${p.pagos_ahora ?? 0}`).join(' · ')})
              </span>
            </span>
          </div>
          <button
            onClick={() => regenerarMut.mutate(undefined)}
            disabled={regenerarMut.isPending}
            title="Reescribe los pagos fijos de forma idempotente en su sitio"
            className="text-[11px] text-surface-400 hover:text-surface-200 underline transition-colors"
          >
            {regenerarMut.isPending ? 'Regenerando...' : 'Forzar regeneración'}
          </button>
        </div>
      )}

      {diff.nuevas.length > 0 && (
        <Section
          title="Posiciones nuevas en el extracto"
          subtitle="El portafolio sugerido sale de las cadenas de pagos fijos que ya llevas a mano"
          action={
            <button
              onClick={() => confirmar.mutate({ usar_sugerencias: true, asignaciones })}
              disabled={confirmar.isPending}
              className="flex items-center gap-2 px-3.5 h-9 rounded-lg bg-primary-600 hover:bg-primary-500 text-white text-xs font-bold disabled:opacity-50"
            >
              <Sparkles size={14} />
              Confirmar todas con su sugerencia
            </button>
          }
        >
          <div className="divide-y divide-white/[0.04]">
            {diff.nuevas.map(n => (
              <NuevaFila
                key={n.detectada.tx_apertura_id}
                detectada={n.detectada}
                sugerencia={n.sugerencia}
                portfolios={portfolios}
                asignado={asignaciones[n.detectada.tx_apertura_id] ?? ''}
                onAsignar={v => setAsignaciones({ ...asignaciones, [n.detectada.tx_apertura_id]: v })}
                onConfirmar={() => confirmar.mutate({
                  tx_apertura_ids: [n.detectada.tx_apertura_id],
                  asignaciones,
                  usar_sugerencias: true,
                })}
                confirmando={confirmar.isPending}
              />
            ))}
          </div>
        </Section>
      )}

      {diff.cambiadas.length > 0 && (
        <Section
          title="Posiciones que ya no coinciden"
          subtitle="Suele pasar tras reprocesar el extracto: apareció interés que antes faltaba"
          action={
            <button
              onClick={() => confirmar.mutate({ incluir_cambiadas: true })}
              disabled={confirmar.isPending}
              className="px-3.5 h-9 rounded-lg bg-amber-600/80 hover:bg-amber-500 text-white text-xs font-bold disabled:opacity-50"
            >
              Actualizar con lo del banco
            </button>
          }
        >
          <div className="divide-y divide-white/[0.04]">
            {diff.cambiadas.map(c => (
              <div key={c.posicion_id} className="px-5 py-3 text-sm">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="font-mono text-surface-300">{c.detectada.fecha_apertura}</span>
                  <span className="text-surface-500">→</span>
                  <span className="font-mono text-surface-300">{c.detectada.fecha_cierre ?? 'abierta'}</span>
                  <span className="font-mono text-surface-100">{money(c.detectada.capital)}</span>
                  {c.origen === 'manual' && <Badge tone="amber">manual · no se toca</Badge>}
                  {c.posicion_ids.length > 1 && <Badge tone="sky">{c.posicion_ids.length} partes</Badge>}
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                  {Object.entries(c.cambios).map(([campo, v]) => (
                    <span key={campo} className="text-surface-400">
                      {campo}: <span className="text-rose-400 line-through">{String(v.guardado ?? '—')}</span>
                      {' → '}
                      <span className="text-emerald-400">{String(v.detectado ?? '—')}</span>
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {diff.huerfanas.length > 0 && (
        <Section
          title="Cancelaciones sin apertura"
          subtitle="Inversiones abiertas antes de que empiece el historial: hay que sembrarlas a mano"
        >
          <div className="divide-y divide-white/[0.04]">
            {diff.huerfanas.map(h => (
              <div key={h.fecha} className="px-5 py-3 flex items-center gap-3 text-sm">
                <AlertTriangle size={15} className="text-amber-400 shrink-0" />
                <span className="font-mono text-surface-300">{h.fecha}</span>
                <span className="font-mono text-surface-100">{money(h.capital_sugerido)}</span>
                <span className="text-xs text-surface-500">
                  interés sugerido {money(h.interes_sugerido)} · retención {money(h.retencion)}
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {diff.solo_guardadas.length > 0 && (
        <Section
          title="Guardadas que el banco ya no reporta"
          subtitle="El extracto cambió debajo; míralas antes de borrar nada"
        >
          <div className="divide-y divide-white/[0.04]">
            {diff.solo_guardadas.map(s => (
              <div key={s.posicion_id} className="px-5 py-3 flex items-center gap-3 text-sm">
                <GitBranch size={15} className="text-surface-500 shrink-0" />
                <span className="font-mono text-surface-300">{s.fecha_apertura ?? '—'}</span>
                <span className="font-mono text-surface-100">{money(s.capital)}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {confirmar.data && confirmar.data.omitidas.length > 0 && (
        <div className="p-3 rounded-xl bg-surface-900/60 border border-white/[0.06] text-xs text-surface-400">
          {confirmar.data.omitidas.length} posición(es) se dejaron intactas por ser manuales.
        </div>
      )}
    </div>
  );
}

function NuevaFila({ detectada, sugerencia, portfolios, asignado, onAsignar, onConfirmar, confirmando }: {
  detectada: DetectedPosition;
  sugerencia: PortfolioSuggestion | null;
  portfolios: Portfolio[];
  asignado: string;
  onAsignar: (v: string) => void;
  onConfirmar: () => void;
  confirmando: boolean;
}) {
  const sugerido = sugerencia?.sugerido
    ? portfolios.find(p => p.id === sugerencia.sugerido)?.name
    : null;

  return (
    <div className="px-5 py-3 flex flex-wrap items-center gap-3 text-sm hover:bg-white/[0.02]">
      <div className="flex items-center gap-2 min-w-[260px]">
        <span className="font-mono text-surface-300">{detectada.fecha_apertura}</span>
        <span className="text-surface-600">→</span>
        <span className="font-mono text-surface-300">{detectada.fecha_cierre ?? 'abierta'}</span>
        {detectada.ambiguo && <Badge tone="amber">interés prorrateado</Badge>}
      </div>

      <div className="flex items-center gap-3 text-xs font-mono">
        <span className="text-surface-100">{money(detectada.capital)}</span>
        <span className="text-emerald-400">+{money(detectada.interes)}</span>
        <span className="text-primary-300">{pct(detectada.tna)}</span>
      </div>

      <div className="flex items-center gap-2 ml-auto">
        {sugerencia?.reparto ? (
          <span className="flex items-center gap-1.5 text-xs text-amber-300">
            <Scissors size={13} />
            Junta {sugerencia.reparto_sugerido.map(r => `${r.nombre} ${money(r.capital)}`).join(' + ')}
          </span>
        ) : sugerido ? (
          <span className="text-xs text-surface-400">
            sugerido <span className="text-primary-300 font-semibold">{sugerido}</span>
          </span>
        ) : (
          <span className="text-xs text-amber-400">sin sugerencia</span>
        )}

        <select
          value={asignado}
          onChange={e => onAsignar(e.target.value)}
          className="h-8 bg-surface-950/60 border border-white/10 rounded-lg px-2 text-surface-200 text-xs focus:ring-0"
        >
          <option value="">{sugerido ? `Usar sugerencia` : 'Sin portafolio'}</option>
          {portfolios.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>

        <button
          onClick={onConfirmar}
          disabled={confirmando}
          className="px-3 h-8 rounded-lg bg-surface-800 hover:bg-emerald-600/20 text-surface-300 hover:text-emerald-300 text-xs font-bold transition-all disabled:opacity-50"
        >
          Confirmar
        </button>
      </div>
    </div>
  );
}

function Chip({ label, valor, tone = 'neutral' }: {
  label: string;
  valor: number;
  tone?: 'neutral' | 'violet' | 'emerald' | 'amber';
}) {
  const tones = {
    neutral: 'bg-surface-900/60 border-white/[0.06] text-surface-400',
    violet: 'bg-primary-500/10 border-primary-500/20 text-primary-300',
    emerald: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300',
    amber: 'bg-amber-500/10 border-amber-500/20 text-amber-300',
  };
  return (
    <div className={`px-3 py-1.5 rounded-lg border text-xs font-semibold ${tones[tone]}`}>
      {label} <span className="font-mono font-bold ml-1">{valor}</span>
    </div>
  );
}
