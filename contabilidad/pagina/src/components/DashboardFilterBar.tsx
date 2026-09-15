import { useEffect, useState } from 'react';
import { Filter, PiggyBank, X, Info, CreditCard } from 'lucide-react';
import { api } from '../services/api';
import { useFunds } from '../hooks/useTransactions';
import { DashboardFilters, contarFiltros, hayFiltroActivo } from '../hooks/useDashboardFilters';
import { money } from '../utils/format';

// La misma lista que usa el presupuesto (MonthlyBudget.tsx). 'Sin Categoría' se
// agrega aparte porque no es una categoría sino su ausencia.
const CATEGORIAS = [
  'Alimentación', 'Transporte', 'Ocio', 'Salud', 'Subscripciones', 'Mensual',
  'Inversion', 'Regalo', 'Mujeres', 'Aseo', 'Deudas', 'Tarjeta', 'Ropa',
  'Viajes', 'Otro',
];

interface Props {
  filters: DashboardFilters;
  onChange: (f: DashboardFilters) => void;
  onClear: () => void;
  /** Lo que el backend informó del último filtro aplicado, para ser honestos sobre su alcance. */
  resumen?: {
    excluidas_banca?: number;
    excluidas_tarjeta?: number;
    excluidas_tarjeta_antes_del_ancla?: number;
    monto_excluido_banca?: number;
    consumo_excluido_tarjeta?: number;
    pagos_tarjeta_excluidos?: number;
  } | null;
}

const SELECT_CLS =
  'bg-slate-900/70 border border-white/10 text-slate-200 text-sm rounded-xl px-3 py-2 ' +
  'outline-none focus:ring-2 focus:ring-blue-500/50 [&>option]:bg-slate-900';

const SELECT_ACTIVO = 'border-amber-400/60 ring-1 ring-amber-400/40';

/** Un popover con su fondo de cierre. Los tres desplegables de la barra lo comparten. */
function Popover({ abierto, onCerrar, children }: {
  abierto: boolean; onCerrar: () => void; children: React.ReactNode;
}) {
  if (!abierto) return null;
  return (
    <>
      <div className='fixed inset-0 z-30' onClick={onCerrar} />
      <div className='absolute z-40 mt-2 right-0 w-80 bg-slate-900 border border-white/10 rounded-2xl shadow-2xl p-3 backdrop-blur-xl'>
        {children}
      </div>
    </>
  );
}

export function DashboardFilterBar({ filters, onChange, onClear, resumen }: Props) {
  const { data: funds } = useFunds();
  const [tags, setTags] = useState<string[]>([]);
  const [abierto, setAbierto] = useState<'cats' | 'fondos' | null>(null);

  useEffect(() => {
    api.getTags().then(setTags).catch(e => console.error('Error cargando tags', e));
  }, []);

  const activo = hayFiltroActivo(filters);
  const cantidad = contarFiltros(filters);

  const set = <K extends keyof DashboardFilters>(k: K, v: DashboardFilters[K]) =>
    onChange({ ...filters, [k]: v });

  const alternar = (lista: string[], valor: string) =>
    lista.includes(valor) ? lista.filter(x => x !== valor) : [...lista, valor];

  const listaFondos = funds || [];
  // null = todos. Se materializa solo al tocar algo, para no fijar una lista que
  // quedaría vieja si después se crea un fondo nuevo.
  const fondosActivos = filters.fondos ?? listaFondos.map(f => f.id);

  const nExcluidas = (filters.categoriasExcluidas.length + filters.tagsExcluidos.length);

  return (
    <div className='w-full flex flex-col gap-2'>
      <div className='flex flex-wrap items-center gap-2 bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl px-3 py-2.5 shadow-xl'>
        <div className='flex items-center gap-2 text-slate-400 pr-1'>
          <Filter size={16} className={activo ? 'text-amber-400' : ''} />
          <span className='text-xs font-bold uppercase tracking-wider'>Filtros</span>
          {cantidad > 0 && (
            <span className='bg-amber-400 text-slate-950 font-bold text-[10px] px-1.5 rounded-full'>
              {cantidad}
            </span>
          )}
        </div>

        <select
          value={filters.etiquetado}
          onChange={e => set('etiquetado', e.target.value as DashboardFilters['etiquetado'])}
          className={`${SELECT_CLS} ${filters.etiquetado !== 'all' ? SELECT_ACTIVO : ''}`}
        >
          <option value='all'>Todas las transacciones</option>
          <option value='labeled'>Solo etiquetadas</option>
          <option value='unlabeled'>No etiquetadas</option>
        </select>

        <select
          value={filters.reembolsable}
          onChange={e => set('reembolsable', e.target.value as DashboardFilters['reembolsable'])}
          className={`${SELECT_CLS} ${filters.reembolsable !== 'all' ? SELECT_ACTIVO : ''}`}
        >
          <option value='all'>Incl. reembolsables</option>
          <option value='excluded'>Sin reembolsables</option>
          <option value='included'>Solo reembolsables</option>
        </select>

        <select
          value={filters.prioridad}
          onChange={e => set('prioridad', e.target.value as DashboardFilters['prioridad'])}
          className={`${SELECT_CLS} ${filters.prioridad !== 'all' ? SELECT_ACTIVO : ''}`}
          title='Solo afecta a los gastos: los ingresos no se clasifican como necesidad o deseo'
        >
          <option value='all'>Necesidades y deseos</option>
          <option value='needs'>Solo necesidades</option>
          <option value='wants'>Solo deseos</option>
          <option value='rated'>Solo clasificadas</option>
        </select>

        {/* Categorías y etiquetas excluidas */}
        <div className='relative'>
          <button
            onClick={() => setAbierto(a => (a === 'cats' ? null : 'cats'))}
            className={`text-sm rounded-xl px-3 py-2 border transition-all flex items-center gap-2 ${
              nExcluidas > 0
                ? 'bg-rose-500/15 border-rose-500/40 text-rose-300'
                : 'bg-slate-900/70 border-white/10 text-slate-300 hover:bg-white/5'
            }`}
          >
            <X size={14} />
            <span>Excluir</span>
            {nExcluidas > 0 && (
              <span className='bg-rose-500 text-slate-950 font-bold text-[10px] px-1.5 rounded-full'>
                {nExcluidas}
              </span>
            )}
          </button>

          <Popover abierto={abierto === 'cats'} onCerrar={() => setAbierto(null)}>
            <div className='flex justify-between items-center pb-2 mb-2 border-b border-white/10'>
              <span className='text-xs font-bold uppercase tracking-wider text-slate-300'>Categorías</span>
              <button
                onClick={() => set('categoriasExcluidas', [])}
                className='text-[11px] text-rose-400 hover:text-rose-300 font-semibold'
              >
                Limpiar
              </button>
            </div>
            <div className='flex flex-wrap gap-1.5 mb-3'>
              {[...CATEGORIAS, 'Sin Categoría'].map(cat => {
                const fuera = filters.categoriasExcluidas.includes(cat);
                return (
                  <button
                    key={cat}
                    onClick={() => set('categoriasExcluidas', alternar(filters.categoriasExcluidas, cat))}
                    className={`text-xs px-2 py-1 rounded-lg border transition-colors ${
                      fuera
                        ? 'bg-rose-500/15 border-rose-500/40 text-rose-300 line-through'
                        : 'bg-slate-950 border-white/5 text-slate-300 hover:bg-slate-800'
                    }`}
                  >
                    {cat}
                  </button>
                );
              })}
            </div>

            <div className='flex justify-between items-center pb-2 mb-2 border-b border-white/10'>
              <span className='text-xs font-bold uppercase tracking-wider text-slate-300'>Etiquetas</span>
              <button
                onClick={() => set('tagsExcluidos', [])}
                className='text-[11px] text-rose-400 hover:text-rose-300 font-semibold'
              >
                Limpiar
              </button>
            </div>
            <div className='flex flex-wrap gap-1.5 max-h-48 overflow-y-auto custom-scrollbar'>
              {[...tags, 'Sin Etiqueta'].map(tag => {
                const fuera = filters.tagsExcluidos.includes(tag);
                return (
                  <button
                    key={tag}
                    onClick={() => set('tagsExcluidos', alternar(filters.tagsExcluidos, tag))}
                    className={`text-xs px-2 py-1 rounded-lg border transition-colors ${
                      fuera
                        ? 'bg-rose-500/15 border-rose-500/40 text-rose-300 line-through'
                        : 'bg-slate-950 border-white/5 text-slate-300 hover:bg-slate-800'
                    }`}
                  >
                    {tag}
                  </button>
                );
              })}
            </div>
          </Popover>
        </div>

        {/* Fondos */}
        <div className='relative'>
          <button
            onClick={() => setAbierto(a => (a === 'fondos' ? null : 'fondos'))}
            className={`text-sm rounded-xl px-3 py-2 border transition-all flex items-center gap-2 ${
              filters.fondos !== null
                ? 'bg-teal-500/15 border-teal-500/40 text-teal-300'
                : 'bg-slate-900/70 border-white/10 text-slate-300 hover:bg-white/5'
            }`}
          >
            <PiggyBank size={14} />
            <span>
              {filters.fondos === null
                ? 'Todos los fondos'
                : `Fondos (${fondosActivos.length}/${listaFondos.length})`}
            </span>
          </button>

          <Popover abierto={abierto === 'fondos'} onCerrar={() => setAbierto(null)}>
            <div className='flex justify-between items-center pb-2 mb-2 border-b border-white/10'>
              <span className='text-xs font-bold uppercase tracking-wider text-slate-300'>Filtrar por fondo</span>
              <div className='flex items-center gap-2'>
                <button
                  onClick={() => set('fondos', null)}
                  className='text-[11px] text-teal-400 hover:text-teal-300 font-semibold'
                >
                  Todos
                </button>
                <span className='text-slate-600'>|</span>
                <button
                  onClick={() => set('fondos', [])}
                  className='text-[11px] text-slate-400 hover:text-slate-200 font-semibold'
                >
                  Ninguno
                </button>
              </div>
            </div>
            <div className='max-h-56 overflow-y-auto custom-scrollbar space-y-1'>
              {listaFondos.length === 0 && (
                <p className='text-xs text-slate-500 italic py-2 text-center'>No hay fondos configurados.</p>
              )}
              {listaFondos.map(f => {
                const marcado = fondosActivos.includes(f.id);
                return (
                  <button
                    key={f.id}
                    onClick={() => set('fondos', alternar(fondosActivos, f.id))}
                    className={`w-full text-left text-sm px-2 py-1.5 rounded-lg flex items-center gap-2 transition-colors ${
                      marcado ? 'bg-teal-500/10 text-teal-200' : 'text-slate-400 hover:bg-white/5'
                    }`}
                  >
                    <span className={`w-3.5 h-3.5 rounded border flex-shrink-0 ${
                      marcado ? 'bg-teal-500 border-teal-500' : 'border-slate-600'
                    }`} />
                    <span className='truncate'>{f.name}</span>
                  </button>
                );
              })}
            </div>
            <p className='text-[10px] text-slate-500 mt-2 pt-2 border-t border-white/10 leading-relaxed'>
              Lo que no pertenece a ningún fondo se muestra siempre, esté como esté esta lista.
            </p>
          </Popover>
        </div>

        {activo && (
          <button
            onClick={onClear}
            className='flex items-center gap-1 text-xs text-rose-400 hover:text-rose-300 px-3 py-2 bg-rose-500/10 rounded-xl border border-rose-500/20 transition-colors ml-auto'
          >
            <X size={14} /> Limpiar
          </button>
        )}
      </div>

      {/* Alcance real del filtro. Se dice siempre que hay filtro puesto, porque un
          gráfico filtrado a medias que no lo avisa es peor que uno sin filtrar. */}
      {activo && (
        <div className='flex flex-wrap items-start gap-x-4 gap-y-1 text-[11px] text-slate-500 px-3 leading-relaxed'>
          <span className='flex items-center gap-1.5'>
            <Info size={12} className='text-slate-600 flex-shrink-0' />
            El filtro descuenta del <strong className='text-slate-400 font-semibold'>saldo del banco</strong> y
            de la <strong className='text-slate-400 font-semibold'>deuda de tarjeta</strong>.
            La deuda con personas, los pagos fijos y los interpolados no salen de transacciones
            etiquetadas, así que no los toca.
          </span>
          {!!resumen?.pagos_tarjeta_excluidos && (
            <span className='flex items-center gap-1.5 text-slate-500'>
              <CreditCard size={12} className='flex-shrink-0' />
              Incluye {money(resumen.pagos_tarjeta_excluidos)} en
              pagos de tarjeta: al excluirlos sube el saldo y sube la deuda por igual, así que el
              patrimonio no se mueve.
            </span>
          )}
          {!!resumen?.excluidas_tarjeta_antes_del_ancla && (
            <span className='flex items-center gap-1.5 text-amber-500/80'>
              <CreditCard size={12} className='flex-shrink-0' />
              {resumen.excluidas_tarjeta_antes_del_ancla} consumo(s) anteriores al arranque de la
              serie de tarjeta no se descuentan: esa deuda nunca entró al gráfico.
            </span>
          )}
        </div>
      )}
    </div>
  );
}
