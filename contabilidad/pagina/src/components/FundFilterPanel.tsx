import { Check, PiggyBank } from 'lucide-react';
import { FundListItem } from '../services/api';
import { SIN_FONDO, activeFundIds, toggleFund } from '../utils/transactionFilters';

interface FundFilterPanelProps {
  funds: FundListItem[] | undefined;
  /** null = todos los fondos y lo que no tiene fondo. */
  selectedFunds: string[] | null;
  onChange: (next: string[] | null) => void;
  onClose: () => void;
}

/** Texto del botón que abre el panel. */
export function fundFilterLabel(selectedFunds: string[] | null, funds: FundListItem[] | undefined): string {
  if (selectedFunds === null) return 'Todos los fondos';
  const total = (funds ?? []).length + 1;
  if (selectedFunds.length === 0) return 'Ningún fondo';
  if (selectedFunds.length === 1) {
    if (selectedFunds[0] === SIN_FONDO) return 'Solo sin fondo';
    const fund = (funds ?? []).find(f => f.id === selectedFunds[0]);
    if (fund) return fund.name;
  }
  return `Fondos (${selectedFunds.length}/${total})`;
}

/**
 * Panel desplegable para elegir fondos, con "Sin fondo" como una opción más.
 * Se coloca dentro de un contenedor `relative` junto al botón que lo abre.
 */
export function FundFilterPanel({ funds, selectedFunds, onChange, onClose }: FundFilterPanelProps) {
  const fundList = funds ?? [];
  const active = activeFundIds(selectedFunds, funds);

  const row = (id: string, label: string, tag?: string | null) => {
    const checked = active.includes(id);
    return (
      <button
        key={id}
        onClick={() => onChange(toggleFund(id, selectedFunds, funds))}
        className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left text-sm transition-all border ${
          checked ? 'bg-teal-500/15 text-teal-200 border-teal-500/30' : 'text-surface-400 hover:bg-white/5 border-transparent'
        }`}
      >
        <div className="flex items-center gap-2.5 truncate pr-2">
          <span className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors ${
            checked ? 'bg-teal-500 border-teal-500 text-surface-950' : 'border-white/20'
          }`}>
            {checked && <Check size={12} strokeWidth={3} />}
          </span>
          <span className="truncate font-medium">{label}</span>
        </div>
        {tag && (
          <span className="text-[10px] bg-white/5 text-surface-400 px-1.5 py-0.5 rounded border border-white/5 shrink-0">
            #{tag}
          </span>
        )}
      </button>
    );
  };

  return (
    <>
      <div className="fixed inset-0 z-30" onClick={onClose} />
      <div className="absolute z-40 mt-2 w-72 right-0 bg-surface-900 border border-white/10 rounded-xl shadow-2xl p-3 space-y-2 backdrop-blur-xl">
        <div className="flex justify-between items-center px-1 pb-2 border-b border-white/10">
          <div className="flex items-center gap-1.5">
            <PiggyBank size={14} className="text-teal-400" />
            <span className="text-xs font-bold uppercase tracking-wider text-surface-300">Filtrar por fondo</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => onChange(null)} className="text-[11px] text-teal-400 hover:text-teal-300 font-semibold transition-colors">
              Todos
            </button>
            <span className="text-surface-600">|</span>
            <button onClick={() => onChange([])} className="text-[11px] text-surface-400 hover:text-surface-200 font-semibold transition-colors">
              Ninguno
            </button>
          </div>
        </div>

        <div className="max-h-64 overflow-y-auto custom-scrollbar space-y-1 pr-0.5">
          {row(SIN_FONDO, '⚪ Sin fondo asignado')}
          <div className="border-t border-white/5 my-1" />
          {fundList.length === 0 && (
            <p className="text-xs text-surface-500 italic px-1 py-2 text-center">No hay fondos configurados.</p>
          )}
          {fundList.map(f => row(f.id, f.name, f.tag_vinculado))}
        </div>
      </div>
    </>
  );
}
