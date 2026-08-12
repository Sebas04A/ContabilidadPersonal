import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDownLeft, ArrowUpRight, ChevronDown, Landmark, Pencil, Trash2, TrendingUp } from 'lucide-react';
import {
  investmentsApi,
  type FlowDirection,
  type Portfolio,
  type Position,
} from '../../services/investments';
import { Badge, EmptyState, Section, Spinner, fmt, money, pct } from './shared';

const TIPO_LABEL: Record<string, string> = {
  plazo_fijo: 'Plazo fijo',
  valuada: 'Valuada',
  ajuste: 'Ajuste',
  flujo: 'Flujo',
};

/**
 * The master table. Open positions come first because they are the ones that still need
 * a decision; within each group the most recent leads.
 */
export function PositionsTab({ portfolios }: { portfolios: Portfolio[] }) {
  const [portafolio, setPortafolio] = useState('');
  const [estado, setEstado] = useState('');
  const [abierta, setAbierta] = useState<string | null>(null);
  const [registrando, setRegistrando] = useState(false);

  const { data: positions, isLoading } = useQuery({
    queryKey: ['inv-positions', portafolio, estado],
    queryFn: () => investmentsApi.getPositions({
      portafolio_id: portafolio || undefined,
      estado: estado || undefined,
    }),
  });

  const nombres = useMemo(
    () => Object.fromEntries(portfolios.map(p => [p.id, p.name])),
    [portfolios],
  );
  const custodia = useMemo(
    () => new Set(portfolios.filter(p => p.es_custodia).map(p => p.id)),
    [portfolios],
  );

  const ordenadas = useMemo(() => {
    if (!positions) return [];
    return [...positions].sort((a, b) => {
      if (a.estado !== b.estado) return a.estado === 'abierta' ? -1 : 1;
      return (b.fecha_apertura || b.fecha_cierre || '').localeCompare(a.fecha_apertura || a.fecha_cierre || '');
    });
  }, [positions]);

  return (
    <Section
      title="Posiciones"
      subtitle={`${ordenadas.length} guardadas`}
      action={
        <div className="flex gap-2">
          <select
            value={portafolio}
            onChange={e => setPortafolio(e.target.value)}
            className="h-9 bg-surface-900/60 border border-white/10 rounded-lg px-2.5 text-surface-200 text-xs focus:ring-0"
          >
            <option value="">Todos los portafolios</option>
            {portfolios.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <select
            value={estado}
            onChange={e => setEstado(e.target.value)}
            className="h-9 bg-surface-900/60 border border-white/10 rounded-lg px-2.5 text-surface-200 text-xs focus:ring-0"
          >
            <option value="">Abiertas y cerradas</option>
            <option value="abierta">Solo abiertas</option>
            <option value="cerrada">Solo cerradas</option>
          </select>
          <button
            onClick={() => setRegistrando(v => !v)}
            className={`h-9 px-3 rounded-lg text-xs font-semibold transition-colors border
              ${registrando
                ? 'bg-amber-500/15 border-amber-400/30 text-amber-300'
                : 'bg-surface-900/60 border-white/10 text-surface-300 hover:text-white hover:border-white/20'}`}
          >
            Registrar salida
          </button>
        </div>
      }
    >
      {registrando && (
        <FlowForm
          portfolios={portfolios}
          portafolioPorDefecto={portafolio}
          onListo={() => setRegistrando(false)}
        />
      )}

      {isLoading ? (
        <Spinner />
      ) : ordenadas.length === 0 ? (
        <EmptyState icon={<TrendingUp size={28} />}>
          No hay posiciones guardadas. Corre la conciliación para traerlas del extracto.
        </EmptyState>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[900px]">
            <thead>
              <tr className="text-[11px] uppercase tracking-wider text-surface-500 border-b border-white/[0.06]">
                <th className="text-left font-semibold px-4 py-2.5">Portafolio</th>
                <th className="text-left font-semibold px-3 py-2.5">Apertura</th>
                <th className="text-left font-semibold px-3 py-2.5">Cierre</th>
                <th className="text-right font-semibold px-3 py-2.5">Días</th>
                <th className="text-right font-semibold px-3 py-2.5">Capital</th>
                <th className="text-right font-semibold px-3 py-2.5">Interés</th>
                <th className="text-right font-semibold px-3 py-2.5">Ret.</th>
                <th className="text-right font-semibold px-3 py-2.5">Neto</th>
                <th className="text-right font-semibold px-4 py-2.5">TNA</th>
              </tr>
            </thead>
            <tbody>
              {ordenadas.map(p => (
                <PositionRow
                  key={p.id}
                  position={p}
                  portfolios={portfolios}
                  nombre={p.portafolio_id ? nombres[p.portafolio_id] ?? '—' : null}
                  esCustodia={!!p.portafolio_id && custodia.has(p.portafolio_id)}
                  abierta={abierta === p.id}
                  onToggle={() => setAbierta(abierta === p.id ? null : p.id)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

/**
 * Registrar dinero que entra o sale del portafolio sin pasar por una inversión.
 *
 * Existe por un caso concreto: cada vez que vence un certificado de `Inversiones_Uni`
 * salen ~3.200 que se van en matrícula y no se reinvierten. Eso antes solo quedaba
 * anotado como la fecha de fin de un pago fijo —invisible para el generador de la
 * neutralización, que por eso seguía arrastrando plata que ya no estaba.
 *
 * El residual antes/después no es decoración: es la única forma de ver, antes de
 * escribir, si el monto tiene sentido. Un residual negativo después significa que falta
 * registrar algo antes o que el monto está mal.
 */
function FlowForm({ portfolios, portafolioPorDefecto, onListo }: {
  portfolios: Portfolio[];
  portafolioPorDefecto: string;
  onListo: () => void;
}) {
  const queryClient = useQueryClient();
  const [portafolioId, setPortafolioId] = useState(portafolioPorDefecto || portfolios[0]?.id || '');
  const [fecha, setFecha] = useState(() => new Date().toISOString().slice(0, 10));
  const [monto, setMonto] = useState('');
  const [direccion, setDireccion] = useState<FlowDirection>('salida');
  const [nota, setNota] = useState('');

  useEffect(() => {
    if (portafolioPorDefecto) setPortafolioId(portafolioPorDefecto);
  }, [portafolioPorDefecto]);

  const importe = Number(monto) || 0;
  const listo = !!portafolioId && !!fecha && importe > 0;

  const { data: preview } = useQuery({
    queryKey: ['inv-flow-preview', portafolioId, fecha, importe, direccion],
    queryFn: () => investmentsApi.previewFlujo({
      portafolio_id: portafolioId, fecha, monto: importe, direccion,
    }),
    enabled: !!portafolioId && !!fecha,
  });

  const registrar = useMutation({
    mutationFn: () => investmentsApi.registrarFlujo({
      portafolio_id: portafolioId, fecha, monto: importe, direccion, nota: nota || undefined,
    }),
    onSuccess: () => {
      // La neutralización y el resumen dependen de esto, no solo la tabla.
      queryClient.invalidateQueries({ queryKey: ['inv-positions'] });
      queryClient.invalidateQueries({ queryKey: ['inv-summary'] });
      queryClient.invalidateQueries({ queryKey: ['inv-neutralization'] });
      queryClient.invalidateQueries({ queryKey: ['inv-timeline'] });
      setMonto('');
      setNota('');
      onListo();
    },
  });

  const dejaNegativo = preview !== undefined && preview.residual_despues < -0.01;

  return (
    <div className="mb-4 p-4 rounded-xl bg-surface-900/50 border border-amber-400/20 flex flex-col gap-3">
      <div className="flex items-center gap-1.5 p-1 bg-surface-950/60 rounded-lg w-fit">
        {(['salida', 'entrada'] as const).map(d => (
          <button
            key={d}
            onClick={() => setDireccion(d)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-colors
              ${direccion === d ? 'bg-amber-500/20 text-amber-300' : 'text-surface-400 hover:text-white'}`}
          >
            {d === 'salida' ? <ArrowUpRight size={13} /> : <ArrowDownLeft size={13} />}
            {d === 'salida' ? 'Sale del portafolio' : 'Entra al portafolio'}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Campo label="Portafolio">
          <select
            value={portafolioId}
            onChange={e => setPortafolioId(e.target.value)}
            className="w-full h-9 bg-surface-950/60 border border-white/10 rounded-lg px-2.5 text-surface-200 text-xs focus:ring-0"
          >
            {portfolios.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </Campo>
        <Campo label="Fecha">
          <input
            type="date"
            value={fecha}
            onChange={e => setFecha(e.target.value)}
            className="w-full h-9 bg-surface-950/60 border border-white/10 rounded-lg px-2.5 text-surface-200 text-xs focus:ring-0"
          />
        </Campo>
        <Campo label="Monto">
          <input
            type="number"
            step="0.01"
            min="0"
            value={monto}
            onChange={e => setMonto(e.target.value)}
            placeholder="3213.74"
            className="w-full h-9 bg-surface-950/60 border border-white/10 rounded-lg px-2.5 text-surface-200 text-xs font-mono focus:ring-0"
          />
        </Campo>
        <Campo label="Motivo">
          <input
            value={nota}
            onChange={e => setNota(e.target.value)}
            placeholder="Matrícula 2025-1"
            className="w-full h-9 bg-surface-950/60 border border-white/10 rounded-lg px-2.5 text-surface-200 text-xs focus:ring-0"
          />
        </Campo>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-[11px] text-surface-400 font-mono tabular-nums">
          {preview ? (
            <>
              Residual del portafolio: <span className="text-surface-200">{money(preview.residual_antes)}</span>
              {' → '}
              <span className={dejaNegativo ? 'text-rose-400' : 'text-emerald-400'}>
                {money(preview.residual_despues)}
              </span>
            </>
          ) : (
            <span className="text-surface-500">Elige portafolio y fecha para ver el residual</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onListo}
            className="h-9 px-3 rounded-lg text-xs font-semibold text-surface-400 hover:text-white"
          >
            Cancelar
          </button>
          <button
            onClick={() => registrar.mutate()}
            disabled={!listo || registrar.isPending}
            className="h-9 px-4 rounded-lg text-xs font-semibold bg-amber-500/20 border border-amber-400/30 text-amber-300 hover:bg-amber-500/30 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {registrar.isPending ? 'Registrando…' : 'Registrar'}
          </button>
        </div>
      </div>

      {dejaNegativo && (
        <p className="text-[11px] text-amber-400/80 leading-snug">
          Con este monto el portafolio queda en negativo. Eso significa que falta registrar
          algo antes de esta fecha, o que el monto no es el correcto.
        </p>
      )}
      {registrar.isError && (
        <p className="text-[11px] text-rose-400 leading-snug">
          No se pudo registrar: {(registrar.error as any)?.response?.data?.detail ?? 'error inesperado'}
        </p>
      )}
    </div>
  );
}

function Campo({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-surface-500 font-semibold">{label}</span>
      {children}
    </label>
  );
}

function PositionRow({ position, portfolios, nombre, esCustodia, abierta, onToggle }: {
  position: Position;
  portfolios: Portfolio[];
  nombre: string | null;
  esCustodia: boolean;
  abierta: boolean;
  onToggle: () => void;
}) {
  const viva = position.estado === 'abierta';
  return (
    <>
      <tr
        onClick={onToggle}
        className={`border-b border-white/[0.03] cursor-pointer transition-colors hover:bg-white/[0.03] ${viva ? 'bg-emerald-500/[0.04]' : ''}`}
      >
        <td className="px-4 py-2.5">
          <div className="flex items-center gap-2">
            <ChevronDown size={14} className={`text-surface-500 transition-transform ${abierta ? '' : '-rotate-90'}`} />
            <span className={nombre ? 'text-surface-200' : 'text-amber-400'}>{nombre ?? 'Sin asignar'}</span>
            {esCustodia && <Badge tone="sky">custodia</Badge>}
            {position.tipo !== 'plazo_fijo' && <Badge tone="amber">{TIPO_LABEL[position.tipo]}</Badge>}
            {position.origen === 'manual' && <Badge>manual</Badge>}
          </div>
        </td>
        <td className="px-3 py-2.5 text-surface-300 font-mono text-xs">{position.fecha_apertura ?? '—'}</td>
        <td className="px-3 py-2.5 font-mono text-xs">
          {position.fecha_cierre
            ? <span className="text-surface-300">{position.fecha_cierre}</span>
            : <span className="text-emerald-400">abierta</span>}
        </td>
        <td className="px-3 py-2.5 text-right text-surface-400 font-mono text-xs">
          {viva && position.dias_restantes !== null
            ? `faltan ${position.dias_restantes}`
            : position.dias ?? '—'}
        </td>
        <td className="px-3 py-2.5 text-right font-mono text-surface-100">{money(position.capital)}</td>
        <td className="px-3 py-2.5 text-right font-mono text-emerald-400">
          {viva
            ? (position.interes_devengado !== null
                ? <span title="Interés devengado estimado">≈{money(position.interes_devengado)}</span>
                : <span className="text-surface-600">—</span>)
            : money(position.interes)}
        </td>
        <td className="px-3 py-2.5 text-right font-mono text-rose-400/80">
          {position.retencion ? money(position.retencion) : '—'}
        </td>
        <td className="px-3 py-2.5 text-right font-mono text-surface-200">{position.neto ? money(position.neto) : '—'}</td>
        <td className="px-4 py-2.5 text-right font-mono text-primary-300">
          {pct(position.tna_pactada ?? position.tna)}
        </td>
      </tr>
      {abierta && (
        <tr>
          <td colSpan={9} className="px-4 pb-4 bg-surface-950/40">
            <PositionDetail position={position} portfolios={portfolios} />
          </td>
        </tr>
      )}
    </>
  );
}

const MOVIMIENTO_TONE: Record<string, string> = {
  aporte: 'text-rose-300',
  retiro: 'text-emerald-300',
  interes: 'text-emerald-400',
  dividendo: 'text-emerald-400',
  retencion: 'text-amber-400',
  comision: 'text-amber-400',
};

function PositionDetail({ position, portfolios }: { position: Position; portfolios: Portfolio[] }) {
  const queryClient = useQueryClient();
  const [editando, setEditando] = useState(false);
  const [form, setForm] = useState({
    portafolio_id: position.portafolio_id ?? '',
    plazo_pactado_dias: position.plazo_pactado_dias?.toString() ?? '',
    tasa_pactada: position.tasa_pactada?.toString() ?? '',
    nota: position.nota ?? '',
  });

  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ['inv-positions'] });
    queryClient.invalidateQueries({ queryKey: ['inv-summary'] });
    queryClient.invalidateQueries({ queryKey: ['inv-timeline'] });
    queryClient.invalidateQueries({ queryKey: ['inv-portfolios'] });
  };

  const guardar = useMutation({
    mutationFn: () => investmentsApi.updatePosition(position.id, {
      portafolio_id: form.portafolio_id || null,
      plazo_pactado_dias: form.plazo_pactado_dias === '' ? null : Number(form.plazo_pactado_dias),
      tasa_pactada: form.tasa_pactada === '' ? null : Number(form.tasa_pactada),
      nota: form.nota,
    }),
    onSuccess: () => { setEditando(false); invalidar(); },
  });

  const borrar = useMutation({
    mutationFn: () => investmentsApi.deletePosition(position.id),
    onSuccess: invalidar,
  });

  return (
    <div className="grid md:grid-cols-2 gap-4 pt-3">
      <div className="rounded-xl bg-surface-900/60 border border-white/[0.06] overflow-hidden">
        <div className="px-4 py-2 text-[11px] font-bold uppercase tracking-wider text-surface-400 border-b border-white/[0.06]">
          Movimientos
        </div>
        <table className="w-full text-xs">
          <tbody>
            {position.movimientos.map((m, i) => (
              <tr key={m.id ?? i} className="border-b border-white/[0.03] last:border-0">
                <td className="px-4 py-1.5 font-mono text-surface-400">{m.fecha}</td>
                <td className={`px-2 py-1.5 font-semibold ${MOVIMIENTO_TONE[m.tipo] ?? 'text-surface-300'}`}>{m.tipo}</td>
                <td className="px-2 py-1.5 text-right font-mono text-surface-100">{money(m.monto)}</td>
                <td className="px-4 py-1.5 text-surface-500 truncate max-w-[220px]" title={m.nota || m.tx_id || ''}>
                  {m.nota || (m.tx_id ? `tx ${m.tx_id.slice(0, 8)}` : '')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-xl bg-surface-900/60 border border-white/[0.06] p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold uppercase tracking-wider text-surface-400">Datos pactados</span>
          <div className="flex gap-1.5">
            <button
              onClick={() => setEditando(!editando)}
              className="p-1.5 rounded-lg bg-surface-800 hover:bg-primary-600/20 text-surface-300 hover:text-primary-300 transition-all"
              title="Editar"
            >
              <Pencil size={13} />
            </button>
            <button
              onClick={() => { if (confirm('¿Borrar esta posición?')) borrar.mutate(); }}
              className="p-1.5 rounded-lg bg-surface-800 hover:bg-rose-600/20 text-surface-300 hover:text-rose-300 transition-all"
              title="Borrar"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>

        {editando ? (
          <div className="space-y-2">
            <select
              value={form.portafolio_id}
              onChange={e => setForm({ ...form, portafolio_id: e.target.value })}
              className="w-full h-9 bg-surface-950/60 border border-white/10 rounded-lg px-2.5 text-surface-200 text-xs focus:ring-0"
            >
              <option value="">Sin portafolio</option>
              {portfolios.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <div className="grid grid-cols-2 gap-2">
              <input
                value={form.plazo_pactado_dias}
                onChange={e => setForm({ ...form, plazo_pactado_dias: e.target.value })}
                placeholder="Plazo pactado (días)"
                inputMode="numeric"
                className="h-9 bg-surface-950/60 border border-white/10 rounded-lg px-2.5 text-surface-200 text-xs focus:ring-0"
              />
              <input
                value={form.tasa_pactada}
                onChange={e => setForm({ ...form, tasa_pactada: e.target.value })}
                placeholder="Tasa pactada (%)"
                inputMode="decimal"
                className="h-9 bg-surface-950/60 border border-white/10 rounded-lg px-2.5 text-surface-200 text-xs focus:ring-0"
              />
            </div>
            <input
              value={form.nota}
              onChange={e => setForm({ ...form, nota: e.target.value })}
              placeholder="Nota"
              className="w-full h-9 bg-surface-950/60 border border-white/10 rounded-lg px-2.5 text-surface-200 text-xs focus:ring-0"
            />
            <button
              onClick={() => guardar.mutate()}
              disabled={guardar.isPending}
              className="w-full h-9 rounded-lg bg-primary-600 hover:bg-primary-500 text-white text-xs font-bold disabled:opacity-50"
            >
              Guardar
            </button>
          </div>
        ) : (
          <dl className="grid grid-cols-2 gap-y-2 gap-x-3 text-xs">
            <Dato label="Institución" valor={position.institucion ?? '—'} />
            <Dato label="Plazo pactado" valor={position.plazo_pactado_dias ? `${position.plazo_pactado_dias} días` : 'sin capturar'} />
            <Dato label="Tasa pactada" valor={position.tasa_pactada ? `${fmt(position.tasa_pactada)} %` : 'sin capturar'} />
            <Dato label="TNA calendario" valor={pct(position.tna)} />
            <Dato label="TNA liquidada" valor={pct(position.tna_pactada)} />
            <Dato label="Vencimiento" valor={position.fecha_vencimiento ?? '—'} />
            {position.nota && (
              <div className="col-span-2">
                <dt className="text-surface-500 flex items-center gap-1.5"><Landmark size={11} /> Nota</dt>
                <dd className="text-surface-300 mt-0.5">{position.nota}</dd>
              </div>
            )}
          </dl>
        )}

        {!position.plazo_pactado_dias && position.estado === 'cerrada' && (
          <p className="text-[11px] text-amber-400/80 leading-snug">
            Sin el plazo pactado, la TNA que ves usa días calendario y base 365. El banco
            liquida sobre el plazo pactado y base 360, así que la tasa real es un poco mayor.
          </p>
        )}
      </div>
    </div>
  );
}

function Dato({ label, valor }: { label: string; valor: string }) {
  return (
    <div>
      <dt className="text-surface-500">{label}</dt>
      <dd className="text-surface-200 font-mono">{valor}</dd>
    </div>
  );
}
