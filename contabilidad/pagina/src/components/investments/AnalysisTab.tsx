import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as echarts from 'echarts';
import {
  Activity, CalendarClock, Coins, Hourglass, LineChart, Microscope, Minus, Percent, PiggyBank,
  Pencil, Timer, TrendingDown, TrendingUp, TriangleAlert, Wallet, X,
} from 'lucide-react';
import {
  investmentsApi,
  type CertificateSummary,
  type EarningsProjection,
  type MovementType,
  type PortfolioAnalysis,
  type PortfolioPositionRow,
  type PositionAnalysis,
  type Portfolio,
  type RateTrend,
} from '../../services/investments';
import {
  Badge, Chart, EJE, EmptyState, GRID, KpiCard, Section, Spinner, SubTabs, TOOLTIP, fmt, money, pct,
} from './shared';

type Subseccion = 'general' | 'proyeccion' | 'certificados';

const SUBSECCIONES: { id: Subseccion; label: string; icon: ReactNode }[] = [
  { id: 'general', label: 'Resumen general', icon: <Activity size={14} /> },
  { id: 'proyeccion', label: 'Proyección', icon: <LineChart size={14} /> },
  { id: 'certificados', label: 'Por certificado', icon: <Microscope size={14} /> },
];

/** Qué se está mirando: un portafolio siempre, y opcionalmente uno de sus certificados. */
export interface AnalysisSelection {
  portafolioId: string | null;
  posicionId: string | null;
}

/**
 * Una inversión, entendida como el usuario la entiende: **el bolsillo**, no el certificado.
 *
 * `Inversiones_Uni` no son doce plazos fijos sueltos; es el mismo dinero rodando de uno a
 * otro, con matrículas saliendo por el camino. Por eso la pantalla empieza en el
 * portafolio y el certificado es el detalle al que se baja, no al revés.
 */
export function AnalysisTab({ portfolios, cargando, error, seleccion, onSeleccionar }: {
  portfolios: Portfolio[];
  /** Mientras la consulta está en vuelo la lista llega vacía, y vacío no es «no hay». */
  cargando?: boolean;
  error?: boolean;
  seleccion: AnalysisSelection;
  onSeleccionar: (seleccion: AnalysisSelection) => void;
}) {
  const [sub, setSub] = useState<Subseccion>('general');
  const [editandoSaldo, setEditandoSaldo] = useState(false);
  const activo = portfolios.find(p => p.id === seleccion.portafolioId) ?? null;

  // Llegar desde Posiciones con un certificado ya elegido tiene que aterrizar donde ese
  // certificado se ve, no en el resumen.
  useEffect(() => {
    if (seleccion.posicionId) setSub('certificados');
  }, [seleccion.posicionId]);

  // Entrar sin nada elegido no debería enseñar una pantalla vacía.
  useEffect(() => {
    if (!seleccion.portafolioId && portfolios.length) {
      onSeleccionar({ portafolioId: portfolios[0].id, posicionId: null });
    }
  }, [seleccion.portafolioId, portfolios, onSeleccionar]);

  if (cargando) return <Spinner />;

  if (error) {
    return (
      <EmptyState icon={<TriangleAlert size={28} />}>
        No se pudieron cargar los portafolios. Comprueba que el backend esté levantado y
        vuelve a entrar.
      </EmptyState>
    );
  }

  if (!portfolios.length) {
    return (
      <EmptyState icon={<TrendingUp size={28} />}>
        Todavía no hay portafolios de inversión. Un grupo cuenta como portafolio cuando está
        marcado <b className="text-surface-300">es_inversion</b> o cuando ya tiene posiciones
        apuntándole.
      </EmptyState>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
      <nav className="flex flex-wrap gap-2" aria-label="Portafolios">
        {portfolios.map(p => {
          const activo = p.id === seleccion.portafolioId;
          return (
            <button
              key={p.id}
              aria-pressed={activo}
              onClick={() => onSeleccionar({ portafolioId: p.id, posicionId: null })}
              className={`group flex items-center gap-2.5 pl-3 pr-4 py-2 rounded-xl border text-left transition-colors
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/70 ${
                activo
                  ? 'bg-primary-600/15 border-primary-500/40'
                  : 'bg-surface-900/40 border-white/[0.06] hover:border-white/15 hover:bg-surface-900/70'
              }`}
            >
              <Wallet
                size={16}
                className={activo ? 'text-primary-300' : 'text-surface-500 group-hover:text-surface-300'}
              />
              <span>
                <span className={`block text-sm font-bold leading-tight ${activo ? 'text-white' : 'text-surface-300 group-hover:text-white'}`}>
                  {p.name}
                </span>
                <span className="block text-[11px] leading-tight text-surface-400">
                  {p.posiciones} {p.posiciones === 1 ? 'certificado' : 'certificados'}
                </span>
              </span>
              {p.es_custodia && <Badge tone="sky">custodia</Badge>}
            </button>
          );
        })}
      </nav>

      {activo && (
        <button
          onClick={() => setEditandoSaldo(true)}
          className="flex items-center gap-2 px-3 py-2 rounded-xl border border-white/[0.06] bg-surface-900/40
            text-xs font-bold text-surface-300 hover:text-white hover:border-white/15 transition-colors
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/70"
        >
          <Pencil size={13} />
          Saldo inicial
          <span className={`font-mono ${activo.saldo_inicial_configurado ? 'text-surface-100' : 'text-amber-300'}`}>
            {activo.saldo_inicial_configurado ? money(activo.saldo_inicial) : 'deducido'}
          </span>
        </button>
      )}
      </div>

      {editandoSaldo && activo && (
        <SaldoInicialModal portafolio={activo} onCerrar={() => setEditandoSaldo(false)} />
      )}

      {seleccion.portafolioId && (
        <PortafolioDetalle
          key={seleccion.portafolioId}
          portafolioId={seleccion.portafolioId}
          posicionId={seleccion.posicionId}
          sub={sub}
          onSub={setSub}
          onVerPosicion={id => onSeleccionar({ portafolioId: seleccion.portafolioId, posicionId: id })}
        />
      )}
    </div>
  );
}

/**
 * El orden de las secciones cuenta una historia y no es casual: qué hay (KPIs), cómo llegó
 * a haberlo (la curva), qué dicen esos días (las estadísticas), a dónde va (la proyección),
 * de qué certificados salió (la lista y su detalle) y, al final, el contexto que no depende
 * del usuario — las tasas las pone el banco, así que cierran en vez de abrir.
 */
function PortafolioDetalle({ portafolioId, posicionId, sub, onSub, onVerPosicion }: {
  portafolioId: string;
  posicionId: string | null;
  sub: Subseccion;
  onSub: (sub: Subseccion) => void;
  onVerPosicion: (id: string | null) => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['inv-portfolio-analysis', portafolioId],
    queryFn: () => investmentsApi.getPortfolioAnalysis(portafolioId),
  });

  if (isLoading || !data) return <Spinner />;
  if (!data.apto) return <EmptyState>{data.motivo}</EmptyState>;

  const { kpis } = data;
  // El mismo corte que usa el backend para no proyectar: por debajo del umbral material
  // lo que queda es residuo de redondeo, no plata que dé para nada.
  const vacio = kpis.total_hoy < (data.estadisticas.umbral_material ?? 1);

  return (
    <div className="space-y-4">
      <SubTabs items={SUBSECCIONES} value={sub} onChange={onSub} label="Secciones del detalle" />

      {sub === 'general' && (
        <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          label="Hay ahora"
          value={money(kpis.total_hoy)}
          hint={kpis.dentro_hoy > 0
            ? `${money(kpis.dentro_hoy)} rindiendo · ${money(kpis.suelto_hoy)} suelto`
            : 'nada dentro de un certificado ahora mismo'}
          icon={<Wallet size={13} />}
        />
        <KpiCard
          label="Ha ganado"
          value={money(kpis.ganancia_acumulada)}
          tone="good"
          hint={kpis.retencion
            ? `${money(kpis.interes_cobrado)} de interés menos ${money(kpis.retencion)} de retención`
            : 'interés cobrado en toda su historia'}
          icon={<Coins size={13} />}
        />
        <KpiCard
          label="Rinde al"
          value={pct(kpis.tna_ponderada)}
          hint={kpis.xirr !== null ? `TIR ${fmt(kpis.xirr)} % · ${kpis.certificados} certificados` : 'anual, ponderado por capital-día'}
          icon={<Percent size={13} />}
        />
        {kpis.salidas > 0 ? (
          <KpiCard
            label="Ha salido"
            value={money(kpis.salidas)}
            tone="warn"
            hint={kpis.entradas > 0 ? `y han entrado ${money(kpis.entradas)} de fuera` : 'plata que salió y no volvió'}
            icon={<PiggyBank size={13} />}
          />
        ) : (
          <KpiCard
            label="Plata parada"
            value={`${kpis.dias_con_plata_parada} días`}
            tone={kpis.dias_con_plata_parada > kpis.dias / 3 ? 'warn' : 'default'}
            hint={`de ${kpis.dias} · fuera de todo certificado, sin rendir`}
            icon={<Hourglass size={13} />}
          />
        )}
      </div>

          {!data.saldo_inicial_configurado && (
            <Aviso>
              Este portafolio no tiene saldo inicial configurado, así que la curva arranca en
              cero y el total de hoy se queda corto en lo que ya hubiera antes del primer
              movimiento. Se configura en el botón <b>Saldo inicial</b>, aquí arriba.
            </Aviso>
          )}

          <Section
            title="Cómo ha ido creciendo"
            subtitle="Arriba, toda la plata del portafolio: morado la que está dentro de un certificado rindiendo, ámbar la que está suelta sin rendir. Abajo, lo que lleva ganado. Mismo eje de tiempo: al hacer zoom se mueven los dos"
          >
            <CurvaPortafolio analisis={data} />
          </Section>

          <Estadisticas analisis={data} />
        </div>
      )}

      {sub === 'proyeccion' && (
        <div className="space-y-4">
          <ProyeccionGanancia
            proyeccion={data.proyeccion_ganancia}
            tasas={data.tasas}
            vacio={vacio}
          />

          <TendenciaTasas
            tasas={data.tasas}
            mejor={data.estadisticas.mejor}
            peor={data.estadisticas.peor}
          />
        </div>
      )}

      {sub === 'certificados' && (
        <Certificados
          posiciones={data.posiciones}
          posicionId={posicionId}
          onVerPosicion={onVerPosicion}
        />
      )}
    </div>
  );
}

/**
 * Lo que la serie diaria sabe y los totales no cuentan.
 *
 * La barra parte la ventana en tres estados y las cifras se parten con ella: a la izquierda
 * lo que pasó mientras la plata trabajaba, a la derecha lo que costó que no lo hiciera. Ese
 * corte es el argumento de la sección — la tasa la pone el banco, los días fuera de un
 * certificado los pone uno — así que la lectura lo lleva encima en vez de dejarlo en una
 * rejilla plana de ocho cifras donde el usuario tenía que emparejarlas de memoria.
 */
function Estadisticas({ analisis }: { analisis: PortfolioAnalysis }) {
  const e = analisis.estadisticas;
  if (!e.dias_totales) return null;

  const pctVacio = Math.max(0, 100 - e.pct_rindiendo - e.pct_parada);
  const mejorRacha = e.racha_rindiendo[0];
  const peorRacha = e.racha_parada[0];
  const costoRelativo = e.lucro_cesante !== null && e.ganancia > 0
    ? e.lucro_cesante / e.ganancia * 100
    : null;

  return (
    <Section
      title="Lo que dicen los números"
      subtitle={`Sobre ${e.dias_totales} días, del ${e.desde} al ${e.hasta}`}
    >
      <div className="p-5 space-y-6">
        {/* La barra del tiempo: los tres estados parten la ventana y cierran en 100 %. */}
        <div>
          <div className="flex h-7 rounded-lg overflow-hidden border border-white/[0.06]">
            <Tramo pct={e.pct_rindiendo} color="bg-primary-500/70" etiqueta="rindiendo" />
            <Tramo pct={e.pct_parada} color="bg-amber-500/60" etiqueta="parada" />
            <Tramo pct={pctVacio} color="bg-surface-700/60" etiqueta="sin plata" />
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-1 mt-2 text-[11px] text-surface-400">
            {e.dias_rindiendo > 0 && (
              <Leyenda color="bg-primary-500/70" texto={`${e.dias_rindiendo} días dentro de un certificado`} />
            )}
            {e.dias_parada > 0 && (
              <Leyenda color="bg-amber-500/60" texto={`${e.dias_parada} días con la plata quieta`} />
            )}
            {e.dias_vacio > 0 && (
              <Leyenda color="bg-surface-700/60" texto={`${e.dias_vacio} días sin plata en el portafolio`} />
            )}
          </div>
        </div>

        <div className="grid gap-x-8 gap-y-7 lg:grid-cols-2 lg:divide-x lg:divide-white/10">
          <div className="space-y-4">
            <Rotulo color="bg-primary-500/70">Mientras trabajaba</Rotulo>
            <div className="grid grid-cols-2 gap-x-6 gap-y-4">
              <Dato
                label="Ganó"
                valor={money(e.ganancia)}
                tono="text-emerald-400"
                nota={`${money(e.ganancia_por_mes)} al mes de media`}
              />
              <Dato
                label="Por día trabajado"
                valor={e.ganancia_por_dia_rindiendo !== null ? `$${fmt(e.ganancia_por_dia_rindiendo)}` : '—'}
                nota={`$${fmt(e.ganancia_por_dia)} si se reparte entre los ${e.dias_totales} días`}
              />
              <Dato
                label="Certificado medio"
                valor={money(e.capital_medio)}
                nota={e.duracion_media ? `${e.duracion_media} días de plazo` : 'sin plazos conocidos'}
              />
              <Dato
                label="Racha más larga"
                valor={mejorRacha ? `${mejorRacha.dias} días` : '—'}
                nota={mejorRacha ? `desde ${mejorRacha.desde}` : 'nunca estuvo invertido'}
              />
            </div>
          </div>

          <div className="space-y-4 lg:pl-8">
            <Rotulo color="bg-amber-500/60">Mientras estaba quieta</Rotulo>
            <div className="grid grid-cols-2 gap-x-6 gap-y-4">
              <Dato
                label="Dejó de ganar"
                valor={e.lucro_cesante !== null ? money(e.lucro_cesante) : '—'}
                tono="text-amber-400"
                nota={`lo que los ${money(e.suelto_medio_parado)} quietos habrían dado a tu propia tasa`}
              />
              <Dato
                label="Tarda en reinvertir"
                valor={e.dias_para_reinvertir_medio !== null ? `${fmt(e.dias_para_reinvertir_medio, 1)} días` : '—'}
                nota={`de media, en ${e.huecos} ${e.huecos === 1 ? 'reinversión' : 'reinversiones'}`}
              />
              <Dato
                label="Peor parón"
                valor={peorRacha ? `${peorRacha.dias} días` : '—'}
                tono={peorRacha && peorRacha.dias > 60 ? 'text-amber-400' : undefined}
                nota={peorRacha ? `del ${peorRacha.desde} al ${peorRacha.hasta}` : 'nunca estuvo quieta'}
              />
            </div>

            {costoRelativo !== null && costoRelativo > 25 && (
              <p className="text-[12px] text-amber-200/80 leading-relaxed">
                La plata quieta costó el equivalente al{' '}
                <b className="text-amber-300 font-mono tabular-nums">{fmt(costoRelativo, 0)} %</b>{' '}
                de lo que este portafolio llegó a ganar. La tasa la pone el banco; los días
                fuera de un certificado, no.
              </p>
            )}
          </div>
        </div>

        {analisis.por_anio.length > 0 && (
          <div className="-mx-5 px-5 pt-5 border-t border-white/[0.06] space-y-3">
            <Rotulo>Año a año</Rotulo>
            {/* Cinco columnas no caben en un teléfono: la tabla se desplaza dentro de su
                caja en vez de estirar la página entera. */}
            <div className="overflow-x-auto custom-scrollbar">
            <table className="w-full min-w-[460px] text-sm">
              <thead>
                <tr className="text-[11px] uppercase tracking-wider text-surface-400 border-b border-white/[0.06]">
                  <th scope="col" className="text-left font-semibold py-2">Año</th>
                  <th scope="col" className="text-right font-semibold px-3 py-2">Certificados</th>
                  <th scope="col" className="text-right font-semibold px-3 py-2">Capital medio</th>
                  <th scope="col" className="text-right font-semibold px-3 py-2">Interés</th>
                  <th scope="col" className="text-right font-semibold py-2">TNA</th>
                </tr>
              </thead>
              <tbody>
                {analisis.por_anio.map(a => (
                  <tr key={a.anio} className="border-b border-white/[0.04] last:border-0">
                    <th scope="row" className="py-2 text-left text-surface-300 font-semibold">{a.anio}</th>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-xs text-surface-400">{a.posiciones}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-surface-200">{money(a.capital_medio)}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-emerald-400">{money(a.interes)}</td>
                    <td className="py-2 text-right font-mono tabular-nums text-primary-300">{pct(a.tna_ponderada)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        )}
      </div>
    </Section>
  );
}

// ── Los certificados y el que se esté mirando ────────────────────────────────
//
// La lista y el detalle viven lado a lado en pantalla ancha a propósito: antes el detalle
// se abría *debajo* de una lista con scroll propio, así que clicar una fila mandaba la
// respuesta fuera de la vista y había que ir a buscarla. Puestos en columnas, la lista
// sigue siendo el índice mientras el detalle cambia al lado.

function Certificados({ posiciones, posicionId, onVerPosicion }: {
  posiciones: PortfolioPositionRow[];
  posicionId: string | null;
  onVerPosicion: (id: string | null) => void;
}) {
  const abiertos = posiciones.filter(p => p.estado === 'abierta').length;

  return (
    <div className="grid gap-4 items-start xl:grid-cols-[minmax(300px,360px)_minmax(0,1fr)]">
      <Section
        title="Sus certificados"
        subtitle={posiciones.length
          ? `${posiciones.length} en total${abiertos ? `, ${abiertos} todavía abiertos` : ', todos cerrados'} · clic en uno para verlo de cerca`
          : 'todavía ninguno'}
      >
        {posiciones.length === 0 ? (
          <EmptyState>Este portafolio aún no tiene certificados registrados.</EmptyState>
        ) : (
          <ul className="max-h-[540px] overflow-y-auto py-1 custom-scrollbar">
            {posiciones.map(p => {
              const activo = p.id === posicionId;
              return (
                <li key={p.id}>
                  <button
                    aria-pressed={activo}
                    onClick={() => onVerPosicion(activo ? null : p.id)}
                    className={`w-full text-left px-4 py-2.5 transition-colors focus-visible:outline-none
                      focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary-400/70 ${
                      activo
                        ? 'bg-primary-600/15 ring-1 ring-inset ring-primary-500/30'
                        : 'hover:bg-white/[0.04]'
                    }`}
                  >
                    <span className="flex items-baseline justify-between gap-3">
                      <span className={`font-mono text-[11px] ${activo ? 'text-primary-200' : 'text-surface-300'}`}>
                        {p.fecha_apertura ?? '¿?'} → {p.fecha_cierre ?? 'abierta'}
                      </span>
                      <span className="font-mono tabular-nums text-sm text-surface-100">{money(p.capital)}</span>
                    </span>
                    <span className="flex items-baseline justify-between gap-3 mt-1 text-[11px]">
                      <span className="flex items-center gap-1.5 text-surface-400">
                        {p.dias !== null ? `${p.dias} días` : 'sin plazo'}
                        {p.estado === 'abierta' && <Badge tone="emerald">viva</Badge>}
                      </span>
                      <span className="font-mono tabular-nums">
                        <span className="text-emerald-400">{p.interes ? `+${money(p.interes)}` : '—'}</span>
                        <span className="text-primary-300 ml-2">{pct(p.tna)}</span>
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      {posicionId ? (
        <DetallePosicion
          key={posicionId}
          posicionId={posicionId}
          onCerrar={() => onVerPosicion(null)}
        />
      ) : (
        <div className="hidden xl:block">
          <Section title="Un certificado de cerca" subtitle="Elige uno de la lista">
            <EmptyState icon={<Microscope size={26} />}>
              Cada certificado trae su propia curva: cuánto capital entró, cómo fue corriendo
              el interés día a día y qué movimientos lo cerraron.
            </EmptyState>
          </Section>
        </div>
      )}
    </div>
  );
}

const DIRECCION: Record<string, { texto: string; tono: string; icono: typeof TrendingUp }> = {
  bajando: { texto: 'Las tasas van a la baja', tono: 'text-rose-400', icono: TrendingDown },
  subiendo: { texto: 'Las tasas van al alza', tono: 'text-emerald-400', icono: TrendingUp },
  estable: { texto: 'Las tasas están estables', tono: 'text-surface-200', icono: Minus },
  irregular: { texto: 'Las tasas se mueven sin patrón claro', tono: 'text-amber-400', icono: Minus },
  insuficiente: { texto: 'Faltan certificados para hablar de tendencia', tono: 'text-surface-400', icono: Minus },
  sin_datos: { texto: 'Todavía no hay tasas que comparar', tono: 'text-surface-400', icono: Minus },
};

/**
 * Cada certificado como un punto el día que cerró, y la recta que los ajusta.
 *
 * La recta viene **con su R²** y el titular cambia con él: por debajo de 0,30 no se dice
 * «bajando» sino «sin patrón claro», porque una pendiente sin bondad de ajuste es una
 * flecha dibujada a mano. El tramo futuro va punteado y se corta a dos años: más allá,
 * una recta ajustada sobre dos años y medio de historia no dice nada.
 *
 * Cierra la pestaña porque es la única sección que **no** habla de decisiones del usuario:
 * la tasa la pone el banco y se lee como contexto de todo lo anterior, no como titular.
 */
function TendenciaTasas({ tasas, mejor, peor }: {
  tasas: RateTrend;
  mejor: CertificateSummary | null;
  peor: CertificateSummary | null;
}) {
  const option = useMemo<echarts.EChartsOption>(() => {
    if (!tasas.puntos.length) return {};
    const fechas = Array.from(new Set([
      ...tasas.puntos.map(p => p.fecha),
      ...tasas.proyeccion.map(p => p.fecha),
    ])).sort();
    const enEje = (fecha: string) => fecha;
    const recta = (futuro: boolean) => fechas.map(f => {
      const punto = tasas.proyeccion.find(p => p.fecha === f);
      if (!punto || punto.futuro !== futuro) return null;
      return punto.tasa;
    });
    // El último punto del tramo pasado se repite en el futuro para que las dos mitades
    // de la recta se toquen en vez de dejar un hueco donde empieza la extrapolación.
    const pasado = recta(false);
    const futuro = recta(true);
    let corte = -1;
    pasado.forEach((v, i) => { if (v !== null) corte = i; });
    if (corte >= 0) futuro[corte] = pasado[corte];

    return {
      grid: { ...GRID, right: 30, top: 34 },
      tooltip: {
        trigger: 'item',
        ...TOOLTIP,
        formatter: (p: any) => (p.seriesType === 'scatter'
          ? `${p.value[0]}<br/>TNA <b>${fmt(p.value[1])} %</b><br/>capital ${money(p.value[2])}`
          : `${p.name}<br/>tendencia <b>${fmt(p.value)} %</b>`),
      },
      legend: {
        data: ['Este portafolio', 'Otros portafolios', 'Tendencia', 'Extrapolación'],
        textStyle: { color: '#a1a1aa', fontSize: 11 }, top: 2, itemWidth: 12, itemHeight: 8,
      },
      xAxis: { type: 'category', data: fechas, ...EJE },
      yAxis: {
        type: 'value', min: 0, name: 'TNA %',
        nameTextStyle: { color: '#71717a', fontSize: 10 }, ...EJE,
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
      },
      series: [
        {
          name: 'Este portafolio',
          type: 'scatter',
          data: tasas.puntos.filter(p => p.propio).map(p => [enEje(p.fecha), p.tasa, p.capital]),
          // El tamaño es el capital: una tasa alta sobre 4.000 no pesa lo mismo que sobre 28.000.
          symbolSize: (v: number[]) => Math.max(9, Math.sqrt(Number(v[2])) / 11),
          itemStyle: { color: '#8b5cf6' },
        },
        {
          name: 'Otros portafolios',
          type: 'scatter',
          data: tasas.puntos.filter(p => !p.propio).map(p => [enEje(p.fecha), p.tasa, p.capital]),
          symbolSize: (v: number[]) => Math.max(9, Math.sqrt(Number(v[2])) / 11),
          itemStyle: { color: 'rgba(161,161,170,0.45)' },
        },
        {
          name: 'Tendencia',
          type: 'line',
          data: pasado,
          symbol: 'none',
          connectNulls: true,
          itemStyle: { color: '#f59e0b' },
          lineStyle: { color: '#f59e0b', width: 2 },
        },
        {
          name: 'Extrapolación',
          type: 'line',
          data: futuro,
          symbol: 'none',
          connectNulls: true,
          itemStyle: { color: '#f59e0b' },
          lineStyle: { color: '#f59e0b', width: 2, type: 'dashed', opacity: 0.7 },
        },
      ],
    };
  }, [tasas]);

  if (!tasas.puntos.length) {
    return (
      <Section title="Cómo han ido las tasas" subtitle="Cada certificado, el día que cerró">
        <EmptyState>Todavía no hay certificados cerrados con tasa calculable.</EmptyState>
      </Section>
    );
  }

  const d = DIRECCION[tasas.direccion] ?? DIRECCION.sin_datos;
  const Icono = d.icono;
  const fiable = tasas.direccion === 'bajando' || tasas.direccion === 'subiendo' || tasas.direccion === 'estable';

  return (
    <Section
      title="Cómo han ido las tasas"
      subtitle={`${tasas.puntos.length} certificados cerrados, ${tasas.propios} de este portafolio. La tasa la pone el banco, así que la tendencia se ajusta sobre todos`}
    >
      <div className="px-5 pt-4 pb-1 flex flex-wrap items-start gap-x-8 gap-y-4">
        <div className="flex items-center gap-2.5">
          <Icono size={22} className={d.tono} />
          <div>
            <div className={`text-sm font-bold ${d.tono}`}>{d.texto}</div>
            <div className="text-[11px] text-surface-400">
              {tasas.pendiente_anual !== null && fiable
                ? `${tasas.pendiente_anual > 0 ? '+' : ''}${fmt(tasas.pendiente_anual)} puntos por año · R² ${fmt(tasas.r2, 2)}`
                : tasas.r2 !== null ? `R² ${fmt(tasas.r2, 2)}: la recta no explica los datos` : 'sin ajuste'}
            </div>
          </div>
        </div>
        <Dato label="Primera" valor={`${fmt(tasas.primera.tasa)} %`} nota={tasas.primera.fecha} />
        <Dato
          label="Última"
          valor={`${fmt(tasas.ultima.tasa)} %`}
          tono={tasas.ultima.tasa < tasas.primera.tasa ? 'text-rose-400' : 'text-emerald-400'}
          nota={tasas.ultima.fecha}
        />
        <Dato label="Media" valor={`${fmt(tasas.tasa_media)} %`} nota="de todo el historial" />
        {mejor && peor && (
          <Dato
            label="Mejor y peor"
            valor={`${fmt(mejor.tna)} / ${fmt(peor.tna)} %`}
            nota={`de este portafolio · ${mejor.fecha_cierre} vs ${peor.fecha_cierre}`}
          />
        )}
      </div>
      <Chart option={option} height={320} />
    </Section>
  );
}

const COLOR_ESCENARIO: Record<string, string> = {
  actual: '#8b5cf6',
  tendencia: '#f59e0b',
  media: '#34d399',
};

/**
 * Cuánto seguiría dando la plata bajo tres supuestos, dibujados juntos a propósito.
 *
 * La horquilla entre las tres líneas **es** la respuesta; cualquiera de ellas por separado
 * se leería como una promesa. La de la tendencia se corta a los dos años porque ahí se
 * acaba lo que los datos sostienen: que la línea termine antes es información, no un fallo.
 */
function ProyeccionGanancia({ proyeccion, tasas, vacio }: {
  proyeccion: EarningsProjection;
  tasas: RateTrend;
  vacio: boolean;
}) {
  const option = useMemo<echarts.EChartsOption>(() => {
    if (!proyeccion.escenarios.length) return {};
    return {
      grid: { ...GRID, right: 30, top: 34 },
      tooltip: {
        trigger: 'axis',
        ...TOOLTIP,
        valueFormatter: (v: unknown) => (v === null || v === undefined ? 'sin proyectar' : money(Number(v))),
      },
      legend: {
        data: proyeccion.escenarios.map(e => e.nombre),
        textStyle: { color: '#a1a1aa', fontSize: 11 }, top: 2, itemWidth: 12, itemHeight: 8,
      },
      xAxis: { type: 'category', data: proyeccion.meses, ...EJE, boundaryGap: false },
      yAxis: {
        type: 'value', scale: true, ...EJE,
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
      },
      series: proyeccion.escenarios.map(e => ({
        name: e.nombre,
        type: 'line' as const,
        data: e.valores,
        symbol: 'none',
        connectNulls: false,
        itemStyle: { color: COLOR_ESCENARIO[e.clave] },
        lineStyle: {
          color: COLOR_ESCENARIO[e.clave],
          width: 2,
          type: e.clave === 'actual' ? 'solid' as const : 'dashed' as const,
        },
      })),
    };
  }, [proyeccion]);

  if (vacio || !proyeccion.escenarios.length) {
    return (
      <Section title="Si todo sigue así" subtitle="Cuánto seguiría dando la plata que hay hoy">
        <EmptyState>
          {vacio
            ? 'Ahora mismo no queda plata en este portafolio, así que no hay nada que proyectar.'
            : 'Sin tasas conocidas no hay proyección que calcular.'}
        </EmptyState>
      </Section>
    );
  }

  return (
    <Section
      title="Si todo sigue así"
      subtitle={`Partiendo de los ${money(proyeccion.base)} que hay hoy, reinvirtiendo capital e interés. Tres supuestos: la horquilla entre ellos es la respuesta`}
    >
      <Chart option={option} height={320} />
      <div className="px-5 pb-5 space-y-3">
        <div className="overflow-x-auto custom-scrollbar">
        <table className="w-full min-w-[620px] text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wider text-surface-400 border-b border-white/[0.06]">
              <th scope="col" className="text-left font-semibold py-2">Supuesto</th>
              <th scope="col" className="text-right font-semibold px-3 py-2">Tasa</th>
              <th scope="col" className="text-right font-semibold px-3 py-2">1 año</th>
              <th scope="col" className="text-right font-semibold px-3 py-2">3 años</th>
              <th scope="col" className="text-right font-semibold py-2">5 años</th>
            </tr>
          </thead>
          <tbody>
            {proyeccion.escenarios.map(e => {
              const hito = (anios: number) => e.hitos.find(h => h.anios === anios);
              return (
                <tr key={e.clave} className="border-b border-white/[0.04] last:border-0">
                  <th scope="row" className="py-2 pr-3 text-left font-normal whitespace-nowrap">
                    <span className="flex items-center gap-2 text-surface-200">
                      <span
                        className="w-2.5 h-2.5 rounded-sm shrink-0"
                        style={{ backgroundColor: COLOR_ESCENARIO[e.clave] }}
                      />
                      {e.nombre}
                    </span>
                  </th>
                  <td className="px-3 py-2 text-right font-mono tabular-nums text-xs text-primary-300 whitespace-nowrap">
                    {e.tasa_final !== e.tasa_inicial
                      ? `${fmt(e.tasa_inicial)} → ${fmt(e.tasa_final)} %`
                      : `${fmt(e.tasa_inicial)} %`}
                  </td>
                  {[1, 3, 5].map(anios => {
                    const h = hito(anios);
                    return (
                      <td key={anios} className={`py-2 text-right font-mono tabular-nums ${anios === 5 ? '' : 'px-3'}`}>
                        {h ? (
                          <>
                            <span className="text-surface-100">{money(h.valor)}</span>
                            <span className="text-emerald-400 text-[11px] ml-1.5">+{fmt(h.ganancia)}</span>
                          </>
                        ) : (
                          <span className="text-surface-500 text-[11px]">sin proyectar</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>

        <p className="text-[11px] text-surface-400 leading-snug">
          {tasas.direccion === 'bajando' && (
            <>
              Con la tendencia actual la tasa llegaría a cero antes de dos años, así que esa
              línea <b>se corta ahí</b>: extrapolar más lejos afirmaría que el banco deja de
              pagar intereses para siempre, y eso los datos no lo dicen.{' '}
            </>
          )}
          Ninguno de los tres es una predicción. Son la misma plata bajo tres supuestos
          distintos sobre algo que decide el banco, no tú — lo que sí decides es cuántos días
          está dentro de un certificado.
        </p>
      </div>
    </Section>
  );
}

/**
 * El residual de partida del portafolio: la plata que ya tenía suelta antes de que empiece
 * el historial derivable.
 *
 * Vivía en Resumen, en una lista con los tres portafolios a la vez, lejos de la única
 * pantalla donde el número se nota. Aquí edita **el portafolio que se está mirando**, y al
 * guardar la curva de al lado cambia: es el sitio donde se puede comprobar que el número
 * era el correcto.
 *
 * Vacío y cero no son lo mismo, y por eso hay dos acciones distintas: «volver a deducir»
 * borra la configuración, guardar un 0 afirma que arranca vacío.
 */
function SaldoInicialModal({ portafolio, onCerrar }: {
  portafolio: Portfolio;
  onCerrar: () => void;
}) {
  const qc = useQueryClient();
  const guardado = portafolio.saldo_inicial_configurado ? String(portafolio.saldo_inicial) : '';
  const [valor, setValor] = useState(guardado);

  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => { if (e.key === 'Escape') onCerrar(); };
    window.addEventListener('keydown', alTeclear);
    return () => window.removeEventListener('keydown', alTeclear);
  }, [onCerrar]);

  const guardar = useMutation({
    mutationFn: (saldo: number | null) => investmentsApi.setSaldoInicial(portafolio.id, saldo),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inv-portfolios'] });
      qc.invalidateQueries({ queryKey: ['inv-portfolio-analysis'] });
      qc.invalidateQueries({ queryKey: ['inv-summary'] });
      onCerrar();
    },
  });

  const invalido = valor.trim() !== '' && Number.isNaN(Number(valor));
  const sucio = valor.trim() !== guardado;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-surface-950/70 backdrop-blur-sm"
      onClick={onCerrar}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Saldo inicial de ${portafolio.name}`}
        onClick={e => e.stopPropagation()}
        className="w-full max-w-md rounded-2xl bg-surface-900 border border-white/10 shadow-2xl overflow-hidden"
      >
        <header className="px-5 py-3.5 border-b border-white/[0.06] flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-white">Saldo inicial</h2>
            <p className="text-[11px] text-surface-400 mt-0.5">
              Con cuánta plata suelta arranca {portafolio.name}, antes del primer movimiento derivable
            </p>
          </div>
          <button
            onClick={onCerrar}
            aria-label="Cerrar"
            className="p-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-surface-300 hover:text-white transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/70"
          >
            <X size={14} />
          </button>
        </header>

        <div className="p-5 space-y-4">
          <label className="flex items-center gap-2">
            <span className="text-surface-400 text-sm font-mono">$</span>
            <input
              autoFocus
              type="text"
              inputMode="decimal"
              value={valor}
              placeholder="deducir de los pagos a mano"
              onChange={e => setValor(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && sucio && !invalido) {
                  guardar.mutate(valor.trim() === '' ? null : Number(valor));
                }
              }}
              className={`flex-1 px-3 py-2 rounded-lg bg-surface-950 border text-sm font-mono text-right
                text-surface-100 focus:outline-none focus:ring-2 ${
                invalido
                  ? 'border-rose-500/50 focus:ring-rose-500/40'
                  : 'border-white/[0.08] focus:ring-primary-500/40'
              }`}
            />
          </label>

          {invalido && <p className="text-[11px] text-rose-300">Eso no es un número.</p>}

          <p className="text-[11px] text-surface-400 leading-relaxed">
            Dejarlo vacío significa <b className="text-surface-300">dedúcelo de los pagos escritos
            a mano</b>, que es lo que pasa hoy. Un valor escrito manda sobre la deducción — y
            cero es un valor, no un hueco.
          </p>

          {guardar.isError && (
            <p className="text-[11px] text-rose-300">No se pudo guardar. Vuelve a intentarlo.</p>
          )}

          <div className="flex items-center justify-between gap-2 pt-1">
            <button
              disabled={!portafolio.saldo_inicial_configurado || guardar.isPending}
              onClick={() => guardar.mutate(null)}
              className="px-3 py-2 rounded-lg text-xs font-bold text-surface-300 hover:text-white
                disabled:opacity-30 disabled:cursor-not-allowed transition-colors
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/70"
            >
              Volver a deducir
            </button>
            <div className="flex gap-2">
              <button
                onClick={onCerrar}
                className="px-3 py-2 rounded-lg text-xs font-bold text-surface-300 hover:text-white transition-colors
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/70"
              >
                Cancelar
              </button>
              <button
                disabled={!sucio || invalido || guardar.isPending}
                onClick={() => guardar.mutate(valor.trim() === '' ? null : Number(valor))}
                className="px-4 py-2 rounded-lg bg-primary-600 text-white text-xs font-bold
                  hover:bg-primary-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/70"
              >
                {guardar.isPending ? 'Guardando…' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Aviso({ children }: { children: ReactNode }) {
  return (
    <div className="px-4 py-3 rounded-xl bg-amber-500/[0.07] border border-amber-400/20 text-[12px] text-amber-200/90 leading-relaxed">
      {children}
    </div>
  );
}

function Tramo({ pct, color, etiqueta }: { pct: number; color: string; etiqueta: string }) {
  if (pct <= 0) return null;
  return (
    <div
      className={`${color} flex items-center justify-center overflow-hidden`}
      style={{ width: `${pct}%` }}
      title={`${etiqueta}: ${pct} %`}
    >
      {pct > 12 && <span className="text-[10px] font-bold text-white/90 tabular-nums">{Math.round(pct)} %</span>}
    </div>
  );
}

function Leyenda({ color, texto }: { color: string; texto: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-2.5 h-2.5 rounded-sm ${color}`} />
      {texto}
    </span>
  );
}

/** Rótulo de subgrupo: el punto de color lo ata al tramo de la barra del que habla. */
function Rotulo({ children, color }: { children: ReactNode; color?: string }) {
  return (
    <h3 className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-surface-300">
      {color && <span className={`w-2.5 h-2.5 rounded-sm ${color}`} />}
      {children}
    </h3>
  );
}

function Dato({ label, valor, nota, tono }: {
  label: string;
  valor: string;
  nota?: string;
  tono?: string;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-surface-400 font-semibold">{label}</div>
      <div className={`text-lg font-bold font-mono tabular-nums ${tono ?? 'text-surface-100'}`}>{valor}</div>
      {nota && <div className="text-[11px] text-surface-400 leading-snug mt-0.5">{nota}</div>}
    </div>
  );
}

/**
 * Dos paneles con un solo eje de tiempo: dónde está la plata, y cuánto lleva ganado.
 *
 * Empezó siendo un gráfico único con la ganancia en un eje secundario y **no se entendía**:
 * dos escalas en la misma caja obligan a echarts a cuadrar los ticks de las dos, y el eje
 * izquierdo acababa bajando a −5.000 aunque el portafolio nunca estuvo en negativo. Son
 * dos preguntas distintas, así que son dos cajas — pero **una sola instancia de echarts**
 * con dos `grid`, para que el zoom y la línea del cursor sigan siendo los mismos en las
 * dos. Dos gráficos separados se desincronizan en cuanto tocas uno.
 *
 * Tres decisiones más, todas por legibilidad:
 *
 * - **`step: 'end'`**: la plata se mueve el día que se mueve. Entre dos eventos la cifra
 *   es constante, y la interpolación diagonal dibujaba rampas de días que sugerían un
 *   goteo que no existe.
 * - **`itemStyle` explícito en cada serie**: sin él, la bolita de la leyenda sale de la
 *   paleta por defecto de echarts y no coincide con el color del área. Era el motivo de
 *   que la leyenda dijera azul/amarillo/gris y el gráfico pintara morado/ámbar/verde.
 * - **Ámbar para lo suelto**: no es un color decorativo. Esa es la plata que existe y no
 *   rinde, y es lo que la pantalla quiere que se vea de un vistazo.
 */
function CurvaPortafolio({ analisis }: { analisis: PortfolioAnalysis }) {
  const option = useMemo<echarts.EChartsOption>(() => {
    const { serie } = analisis;
    // Una serie que vale cero todos los días solo ocupa sitio en la leyenda. Hoy los tres
    // portafolios están sin certificados vivos, así que el devengo no existe.
    const hayDevengo = serie.devengado.some(v => v > 0);

    const capa = (nombre: string, datos: number[], color: string, relleno: string) => ({
      name: nombre,
      type: 'line' as const,
      stack: 'plata',
      step: 'end' as const,
      data: datos,
      symbol: 'none',
      itemStyle: { color },
      lineStyle: { color, width: 1 },
      areaStyle: { color: relleno },
    });

    const capas = [
      capa('Rindiendo', serie.dentro, '#8b5cf6', 'rgba(139,92,246,0.45)'),
      capa('Suelto', serie.suelto, '#f59e0b', 'rgba(245,158,11,0.22)'),
      ...(hayDevengo ? [capa('Devengado', serie.devengado, '#34d399', 'rgba(52,211,153,0.35)')] : []),
    ];
    const nombresApilados = capas.map(c => c.name);

    return {
      // Dos cajas, una encima de otra, compartiendo el eje de tiempo de abajo.
      grid: [
        { left: 72, right: 24, top: 34, height: '46%' },
        { left: 72, right: 24, top: '68%', height: '17%' },
      ],
      tooltip: {
        trigger: 'axis',
        ...TOOLTIP,
        axisPointer: { type: 'line', lineStyle: { color: 'rgba(255,255,255,0.25)' } },
        formatter: (params: any) => {
          const filas = Array.isArray(params) ? params : [params];
          if (!filas.length) return '';
          const total = filas
            .filter(f => nombresApilados.includes(f.seriesName))
            .reduce((suma, f) => suma + (Number(f.value) || 0), 0);
          const cuerpo = filas.map(f =>
            `<div style="display:flex;gap:12px;justify-content:space-between">
               <span>${f.marker} ${f.seriesName}</span>
               <b style="font-variant-numeric:tabular-nums">${money(Number(f.value))}</b>
             </div>`).join('');
          return `<div style="font-weight:600;margin-bottom:4px">${filas[0].axisValue}</div>${cuerpo}
            <div style="display:flex;gap:12px;justify-content:space-between;margin-top:4px;
                        padding-top:4px;border-top:1px solid rgba(255,255,255,0.12)">
              <span>En el portafolio</span>
              <b style="font-variant-numeric:tabular-nums">${money(total)}</b>
            </div>`;
        },
      },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      legend: {
        data: [...nombresApilados, 'Ganancia acumulada'],
        textStyle: { color: '#a1a1aa', fontSize: 11 },
        top: 2,
        itemWidth: 12,
        itemHeight: 8,
      },
      xAxis: [
        // El de arriba no dibuja etiquetas: son las mismas fechas que el de abajo.
        { type: 'category', data: serie.fechas, gridIndex: 0, boundaryGap: false, ...EJE,
          axisLabel: { show: false } },
        { type: 'category', data: serie.fechas, gridIndex: 1, boundaryGap: false, ...EJE },
      ],
      yAxis: [
        { type: 'value', gridIndex: 0, min: 0, name: 'En el portafolio',
          nameTextStyle: { color: '#71717a', fontSize: 10 }, ...EJE,
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } } },
        { type: 'value', gridIndex: 1, min: 0, name: 'Ganancia',
          nameTextStyle: { color: '#71717a', fontSize: 10 }, ...EJE,
          splitNumber: 2, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } } },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1] },
        { type: 'slider', xAxisIndex: [0, 1], height: 16, bottom: 8, borderColor: 'transparent',
          fillerColor: 'rgba(139,92,246,0.15)', handleStyle: { color: '#8b5cf6' },
          textStyle: { color: '#71717a', fontSize: 10 } },
      ],
      series: [
        ...capas,
        {
          name: 'Ganancia acumulada',
          type: 'line',
          step: 'end',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: serie.ganancia,
          symbol: 'none',
          itemStyle: { color: '#34d399' },
          lineStyle: { color: '#34d399', width: 2 },
          areaStyle: { color: 'rgba(52,211,153,0.12)' },
        },
      ],
    };
  }, [analisis]);

  const { kpis } = analisis;
  return (
    <>
      <Chart option={option} height={440} />
      <div className="px-5 pb-4 flex flex-wrap gap-x-6 gap-y-1 text-[11px] text-surface-400">
        <span>
          Empezó con <span className="font-mono tabular-nums text-surface-200">{money(analisis.saldo_inicial)}</span>
        </span>
        <span>
          Hoy hay <span className="font-mono tabular-nums text-surface-200">{money(kpis.total_hoy)}</span>, de los que{' '}
          <span className="font-mono tabular-nums text-emerald-300">{money(kpis.ganancia_acumulada)}</span> los puso el banco
        </span>
        <span>
          Plata parada <span className="font-mono tabular-nums text-amber-300">{kpis.dias_con_plata_parada}</span> de {kpis.dias} días
        </span>
      </div>
    </>
  );
}

// ── El detalle de un certificado suelto ──────────────────────────────────────
//
// Era la pantalla entera antes de que quedara claro que «una inversión» es el bolsillo y
// no el certificado. Se conserva como drill-down: aquí es donde se ve por qué un plazo
// fijo concreto rindió lo que rindió.

const MOVIMIENTO: Record<MovementType, { etiqueta: string; tono: 'neutral' | 'violet' | 'emerald' | 'amber'; monto: string }> = {
  aporte: { etiqueta: 'aporte', tono: 'violet', monto: 'text-surface-100' },
  retiro: { etiqueta: 'retiro', tono: 'neutral', monto: 'text-surface-100' },
  interes: { etiqueta: 'interés', tono: 'emerald', monto: 'text-emerald-400' },
  dividendo: { etiqueta: 'dividendo', tono: 'emerald', monto: 'text-emerald-400' },
  retencion: { etiqueta: 'retención', tono: 'amber', monto: 'text-amber-400' },
  comision: { etiqueta: 'comisión', tono: 'amber', monto: 'text-amber-400' },
};

function DetallePosicion({ posicionId, onCerrar }: { posicionId: string; onCerrar: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['inv-analysis', posicionId],
    queryFn: () => investmentsApi.getPositionAnalysis(posicionId),
  });

  if (isLoading || !data) {
    return (
      <Section title="Un certificado de cerca" subtitle="Cargando su curva y sus movimientos">
        <Spinner />
      </Section>
    );
  }

  const { ganancia, proyeccion } = data;
  const viva = data.estado === 'abierta';
  const dias = data.serie.fechas.length ? data.serie.fechas.length - 1 : null;

  return (
    <div className="animate-panel-in motion-reduce:animate-none">
      <Section
        title={`El certificado de ${money(ganancia.capital)}`}
        subtitle={
          <span className="flex items-center gap-2">
            <span className="font-mono">{data.fecha_apertura ?? '¿?'} → {data.fecha_cierre ?? 'sigue abierto'}</span>
            {viva ? <Badge tone="emerald">viva</Badge> : <Badge>cerrada</Badge>}
          </span>
        }
        action={
          <button
            onClick={onCerrar}
            className="p-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-surface-300 hover:text-white transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/70"
            aria-label="Cerrar el detalle del certificado"
          >
            <X size={14} />
          </button>
        }
      >
        <div className="p-4 pb-0 grid grid-cols-2 lg:grid-cols-4 gap-3">
          <KpiCard
            label={ganancia.realizado ? 'Ganancia neta' : 'Lleva ganado'}
            value={money(ganancia.interes_neto)}
            tone="good"
            hint={ganancia.retencion
              ? `${money(ganancia.interes_bruto)} menos ${money(ganancia.retencion)} de retención`
              : ganancia.realizado ? 'ya cobrado' : 'devengado, todavía no cobrado'}
            icon={<Coins size={13} />}
          />
          <KpiCard
            label="Rendimiento"
            value={pct(ganancia.rendimiento_pct)}
            hint={data.tasa_devengo
              ? `${fmt(data.tasa_devengo)} % anual ${data.tasa_origen === 'liquidada' ? 'liquidado' : 'pactado'}`
              : 'sobre el capital'}
            icon={<Percent size={13} />}
          />
          <KpiCard
            label="Rinde por día"
            value={ganancia.interes_por_dia !== null ? `$${fmt(ganancia.interes_por_dia)}` : '—'}
            hint={dias !== null ? `durante ${dias} días` : 'sin fechas conocidas'}
            icon={<Timer size={13} />}
          />
          {viva && proyeccion ? (
            <KpiCard
              label="Al vencimiento"
              value={money(proyeccion.valor_al_vencimiento)}
              tone="warn"
              hint={`${proyeccion.fecha_vencimiento} · faltan ${proyeccion.dias_restantes} días`}
              icon={<CalendarClock size={13} />}
            />
          ) : (
            <KpiCard
              label="Capital"
              value={money(ganancia.capital)}
              hint={data.plazo_efectivo ? `${data.plazo_efectivo} días de plazo` : 'sin plazo conocido'}
              icon={<PiggyBank size={13} />}
            />
          )}
        </div>

        {data.motivo && <div className="p-4 pb-0"><Aviso>{data.motivo}</Aviso></div>}

        {data.apto && (
          <>
            <p className="px-5 pt-5 text-[12px] text-surface-400 leading-relaxed max-w-[80ch]">
              {data.tasa_origen === 'liquidada'
                ? 'El interés se cobró de golpe al cierre, pero la plata rindió todos los días: la curva lo reparte con la tasa que se despeja del interés real, así que termina exactamente en lo que pagó el banco.'
                : 'Devengo con la tasa pactada. El capital ya está adentro y la tasa ya está fijada: lo punteado no es un pronóstico, es lo que falta por correr.'}
            </p>
            <CurvaCertificado analisis={data} />
          </>
        )}

        <div className="border-t border-white/[0.06]">
          <h3 className="px-5 py-2.5 text-[11px] font-bold uppercase tracking-wider text-surface-300">
            Movimientos
          </h3>
          <table className="w-full text-xs">
            <thead className="sr-only">
              <tr>
                <th scope="col">Fecha</th>
                <th scope="col">Tipo</th>
                <th scope="col">Monto</th>
              </tr>
            </thead>
            <tbody>
              {data.movimientos.map((m, i) => {
                const mov = MOVIMIENTO[m.tipo];
                return (
                  <tr key={m.id ?? i} className="border-t border-white/[0.04]">
                    <td className="pl-5 pr-2 py-2.5 font-mono text-surface-400 align-top w-px whitespace-nowrap">{m.fecha}</td>
                    <td className="px-2 py-2.5 align-top w-px">
                      <Badge tone={mov?.tono ?? 'neutral'}>{mov?.etiqueta ?? m.tipo}</Badge>
                    </td>
                    <td className="px-2 py-2.5 align-top text-surface-500 leading-snug">{m.nota ?? ''}</td>
                    <td className={`pr-5 pl-2 py-2.5 text-right font-mono tabular-nums text-sm align-top whitespace-nowrap ${mov?.monto ?? 'text-surface-100'}`}>
                      {money(m.monto)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}

/**
 * Valor del certificado día a día: el área es el capital, lo que sobresale es el interés.
 *
 * Lo real y lo proyectado son dos series sobre el mismo eje, no una sola con estilos
 * distintos: así el punteado empieza exactamente donde termina lo medido y no hay forma
 * de confundir una cosa con la otra.
 */
function CurvaCertificado({ analisis }: { analisis: PositionAnalysis }) {
  const option = useMemo<echarts.EChartsOption>(() => {
    const { serie, proyeccion } = analisis;
    const fechas = [...serie.fechas, ...(proyeccion ? proyeccion.fechas.slice(1) : [])];

    // El primer punto de la proyección es el último de lo real: se repite a propósito
    // para que las dos líneas se toquen en vez de dejar un salto de un día.
    const proyectado = proyeccion
      ? [...Array(serie.fechas.length - 1).fill(null), ...proyeccion.valor]
      : [];

    return {
      grid: GRID,
      tooltip: { trigger: 'axis', ...TOOLTIP, valueFormatter: (v: unknown) => (v === null ? '—' : money(Number(v))) },
      legend: {
        data: ['Valor', 'Capital', ...(proyeccion ? ['Proyección'] : [])],
        textStyle: { color: '#a1a1aa', fontSize: 11 },
        top: 6,
      },
      xAxis: { type: 'category', data: fechas, ...EJE, boundaryGap: false },
      yAxis: {
        type: 'value',
        scale: true,
        ...EJE,
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
      },
      dataZoom: [{ type: 'inside' }],
      series: [
        {
          name: 'Valor',
          type: 'line',
          data: serie.valor,
          symbol: 'none',
          // `itemStyle` no es redundante: sin él la bolita de la leyenda sale de la
          // paleta por defecto de echarts y no coincide con el color de la línea.
          itemStyle: { color: '#8b5cf6' },
          lineStyle: { color: '#8b5cf6', width: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(139,92,246,0.30)' },
              { offset: 1, color: 'rgba(139,92,246,0.02)' },
            ]),
          },
        },
        {
          name: 'Capital',
          type: 'line',
          data: serie.capital,
          symbol: 'none',
          itemStyle: { color: '#52525b' },
          lineStyle: { color: '#52525b', width: 1.5, type: 'dashed' },
        },
        ...(proyeccion ? [{
          name: 'Proyección',
          type: 'line' as const,
          data: proyectado,
          symbol: 'none',
          connectNulls: false,
          itemStyle: { color: '#f59e0b' },
          lineStyle: { color: '#f59e0b', width: 2, type: 'dashed' as const },
          markPoint: {
            symbolSize: 44,
            itemStyle: { color: 'rgba(245,158,11,0.25)' },
            label: { color: '#fbbf24', fontSize: 10, formatter: 'vence' },
            data: [{
              name: 'vence',
              coord: [proyeccion.fecha_vencimiento, proyeccion.valor_al_vencimiento],
            }],
          },
        }] : []),
      ],
    };
  }, [analisis]);

  return (
    <>
      <Chart option={option} height={300} />
      <div className="px-5 pb-5 flex flex-wrap gap-x-6 gap-y-1 text-[11px] text-surface-400">
        <span>
          De <span className="font-mono tabular-nums text-surface-200">{money(analisis.ganancia.capital)}</span> a{' '}
          <span className="font-mono tabular-nums text-emerald-300">{money(analisis.ganancia.valor_final)}</span>
        </span>
        {analisis.proyeccion && (
          <span>
            Falta por devengar{' '}
            <span className="font-mono tabular-nums text-amber-300">{money(analisis.proyeccion.falta_por_devengar)}</span>
          </span>
        )}
      </div>
    </>
  );
}
