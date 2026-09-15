import { useState } from 'react';
import { ChevronRight, StickyNote, Scissors, ArrowLeftRight, Pin, Pencil, Heart, PiggyBank } from 'lucide-react';
import { Transaction, FundListItem } from '../../services/api';
import { parseTags } from '../../utils/tags';

interface BudgetTransactionRowProps {
  /** Fila a mostrar. En un split parcial su MONTO puede ser solo el de las partes visibles. */
  tx: Transaction;
  /** Todas las partes de la transacción original (incluidas las que no entraron al filtro). */
  parts?: Transaction[];
  onClick?: (tx: Transaction) => void;
  formatCurrency: (val: number) => string;
  /** Fondo al que pertenece la transacción, si hay alguno. */
  fund?: FundListItem | null;
}

const happinessColor = (n: number) => {
  if (n >= 8) return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25';
  if (n >= 6) return 'bg-lime-500/15 text-lime-300 border-lime-500/25';
  if (n >= 5) return 'bg-amber-500/15 text-amber-300 border-amber-500/25';
  return 'bg-rose-500/15 text-rose-300 border-rose-500/25';
};

export function BudgetTransactionRow({ tx, parts, onClick, formatCurrency, fund }: BudgetTransactionRowProps) {
  const [expanded, setExpanded] = useState(false);

  const allParts = parts && parts.length > 1 ? parts : (tx.subTransactions || []);
  const isSplit = allParts.length > 1;
  const tags = parseTags(tx.tags);
  const hasDetail = !!tx.nota || isSplit;

  return (
    <div
      onClick={() => onClick?.(tx)}
      className="p-4 bg-surface-950/50 hover:bg-surface-800 rounded-xl border border-white/5 transition-colors group cursor-pointer"
    >
      <div className="flex justify-between items-start gap-3">
        {/* Chevron de detalle */}
        {hasDetail && (
          <button
            onClick={(e) => { e.stopPropagation(); setExpanded(v => !v); }}
            className="mt-0.5 text-surface-500 hover:text-white transition-colors shrink-0"
            title={expanded ? 'Ocultar detalle' : 'Ver detalle'}
          >
            <ChevronRight size={14} className={`transition-transform ${expanded ? 'rotate-90' : ''}`} />
          </button>
        )}

        <div className="flex flex-col gap-1.5 min-w-0 flex-1">
          {/* Línea 1: nombre + badges */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-white group-hover:text-primary-300 transition-colors uppercase text-sm truncate max-w-md">
              {tx.nombre_limpio || tx.DESCRIPCION}
            </span>

            {tx.prioridad && tx.prioridad !== '---' && (
              <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border shrink-0 ${
                tx.prioridad === 'Necesidad'
                  ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                  : 'bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/20'
              }`}>
                {tx.prioridad}
              </span>
            )}

            {fund && (
              <span
                title={tx.fondo_id === fund.id
                  ? `Asignada al fondo ${fund.name}`
                  : `Pertenece al fondo ${fund.name} por su tag #${fund.tag_vinculado}`}
                className="flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded bg-teal-500/15 text-teal-300 border border-teal-500/25 shrink-0 uppercase tracking-wider"
              >
                <PiggyBank size={9} /> {fund.name}
              </span>
            )}

            {isSplit && (
              <span className="flex items-center gap-0.5 text-[9px] font-bold px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300 shrink-0">
                <Scissors size={9} /> {allParts.length}
              </span>
            )}

            {tx.es_reembolsable && (
              <span className="flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/25 shrink-0 uppercase tracking-wider">
                <ArrowLeftRight size={9} /> Reemb.{tx.deudor ? ` · ${tx.deudor}` : ''}
              </span>
            )}

            {tx.es_fijo && (
              <span className="flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-300 border border-sky-500/25 shrink-0 uppercase tracking-wider">
                <Pin size={9} /> Fijo
              </span>
            )}

            {tx.felicidad > 0 && (
              <span
                title={`Felicidad: ${tx.felicidad} de 9`}
                className={`flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded border shrink-0 ${happinessColor(tx.felicidad)}`}
              >
                <Heart size={9} /> {tx.felicidad}/9
              </span>
            )}

            {tx.nota && <StickyNote size={11} className="text-amber-300/70 shrink-0" />}
          </div>

          {/* Línea 2: fecha · categoría · prioridad · tags */}
          <div className="flex items-center gap-1.5 flex-wrap text-xs text-surface-500">
            <span>{new Date(tx.FECHA).toLocaleDateString('es-CO')}</span>
            <span className="text-surface-700">&bull;</span>

            {tx.categoria && tx.categoria !== '---' ? (
              <span className="px-2 py-0.5 bg-surface-800 border border-white/10 rounded-md text-[11px] font-medium text-surface-200">
                {tx.categoria}
              </span>
            ) : (
              <span className="italic text-surface-600 text-[11px]">Sin categoría</span>
            )}

            {tags.length > 0 ? (
              tags.map((tg, i) => (
                <span key={i} className="px-2 py-0.5 bg-violet-500/10 border border-violet-500/20 rounded-md text-[11px] font-semibold text-violet-300">
                  #{tg}
                </span>
              ))
            ) : (
              <span className="italic text-surface-700 text-[11px]">Sin etiquetas</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <span className={`font-mono font-bold ${tx.MONTO > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {tx.MONTO > 0 ? '+' : ''}{formatCurrency(tx.MONTO)}
          </span>
          <Pencil size={13} className="text-surface-600 group-hover:text-primary-300 transition-colors" />
        </div>
      </div>

      {/* Detalle expandido */}
      {expanded && hasDetail && (
        <div className="mt-3 pt-3 border-t border-white/5 flex flex-col gap-2">
          {tx.nombre_limpio && tx.nombre_limpio !== tx.DESCRIPCION && (
            <p className="text-[11px] text-surface-500 truncate">{tx.DESCRIPCION}</p>
          )}

          {tx.nota && (
            <p className="text-[11px] text-amber-300/80 italic">Nota: {tx.nota}</p>
          )}

          {isSplit && (
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-surface-500">
                Partes del split
              </span>
              {allParts.map((p, i) => (
                <div key={i} className="flex justify-between items-center gap-2 text-[11px] bg-surface-900/60 rounded-lg px-3 py-1.5">
                  <div className="flex items-center gap-1.5 flex-wrap min-w-0">
                    <span className="text-surface-300 font-medium truncate">
                      {p.nombre_limpio || p.DESCRIPCION}
                    </span>
                    <span className="text-surface-500">
                      {p.categoria && p.categoria !== '---' ? p.categoria : 'Sin categoría'}
                    </span>
                    {parseTags(p.tags).map((tg, j) => (
                      <span key={j} className="text-violet-300/80">#{tg}</span>
                    ))}
                  </div>
                  <span className={`font-mono font-bold shrink-0 ${p.MONTO > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {p.MONTO > 0 ? '+' : ''}{formatCurrency(p.MONTO)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
