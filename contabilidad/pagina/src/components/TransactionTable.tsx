import { Transaction } from '../services/api';
import { CheckCircle2, Circle, Edit2, StickyNote, Tag as TagIcon, Clock, Link2, Square, CheckSquare, Landmark, CreditCard } from 'lucide-react';

interface TransactionRowProps {
  transaction: Transaction;
  onEdit: (transaction: Transaction) => void;
  onQuickReview: (id: string) => void;
  index: number;
  isSelected: boolean;
  onToggleSelect: (id: string) => void;
}

export function TransactionRow({ transaction, onEdit, onQuickReview, index, isSelected, onToggleSelect }: TransactionRowProps) {
  const isExpense = transaction.MONTO < 0;
  
  return (
    <div 
      onClick={() => onEdit(transaction)}
      className={`group relative flex items-center gap-4 p-4 md:p-5 rounded-2xl transition-all duration-300 cursor-pointer border
        ${isSelected 
          ? 'bg-primary-500/10 border-primary-500/30 shadow-[0_0_15px_rgba(59,130,246,0.15)]' 
          : 'glass-card hover:bg-surface-800/80 hover:scale-[1.01] hover:shadow-xl border-white/5'}
      `}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      {/* 0. Group Indicator */}
      {transaction.group_id && (
        <div className="absolute -left-1 top-1/2 -translate-y-1/2 p-1.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-lg" title="Transacción agrupada">
           <Link2 size={12} />
        </div>
      )}

      {/* 0.5 Selection Checkbox */}
      <div className="flex-none -ml-1">
         <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleSelect(transaction.id);
            }}
            className={`p-2 rounded-lg transition-colors ${isSelected ? 'text-primary-400' : 'text-surface-600 group-hover:text-surface-400'}`}
         >
            {isSelected ? <CheckSquare size={20} /> : <Square size={20} />}
         </button>
      </div>

      {/* 1. Status Indicator (Left Edge) */}
      <div className={`absolute left-0 top-6 bottom-6 w-1 rounded-r-full transition-colors duration-300 ${
        transaction.revisado 
          ? 'bg-emerald-500' 
          : isExpense ? 'bg-rose-500/50 group-hover:bg-rose-500' : 'bg-emerald-500/50 group-hover:bg-emerald-500'
      }`} />

      {/* 2. Check/Review Button */}
      <div className="flex-none pl-2">
        <button 
          onClick={(e) => {
            e.stopPropagation();
            onQuickReview(transaction.id);
          }}
          className={`
            p-2.5 rounded-xl transition-all duration-300 flex items-center justify-center
            ${transaction.revisado 
              ? 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/30' 
              : 'bg-surface-800 text-surface-500 hover:bg-emerald-500/10 hover:text-emerald-400'}
          `}
          title={transaction.revisado ? "Revisado" : "Marcar como revisado"}
        >
          {transaction.revisado ? <CheckCircle2 size={20} /> : <Circle size={20} />}
        </button>
      </div>

      {/* 3. Main Content Grid */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
        
        {/* Identity: Name & Time (Col 1-5) */}
        <div className="md:col-span-5 flex flex-col gap-1.5 min-w-0">
           <div className="flex items-center gap-2 mb-0.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-surface-500 bg-surface-800/50 px-2 py-0.5 rounded flex items-center gap-1">
                {transaction.TIPO === 'BANCA' ? <Landmark size={10} /> : <CreditCard size={10} />}
                {transaction.TIPO}
              </span>
              {new Date(transaction.FECHA).getHours() !== 0 && new Date(transaction.FECHA).getMinutes() !== 0 && (
                <span className="text-[10px] font-bold uppercase tracking-wider text-surface-500 bg-surface-800/50 px-2 py-0.5 rounded flex items-center gap-1">
                  <Clock size={10} />
                  {new Date(transaction.FECHA).toLocaleTimeString('es-EC', {hour: '2-digit', minute:'2-digit'})}
                </span>
              )}
           </div>
           
           <h3 className={`text-base font-bold truncate tracking-tight transition-colors ${
             transaction.revisado ? 'text-surface-500' : 'text-surface-50 group-hover:text-primary-200'
           }`}>
             {transaction.nombre_limpio || transaction.DESCRIPCION}
           </h3>

           <div className="flex items-center gap-2 mt-1">
             {transaction.nota && (
                <div className="flex items-center gap-1 text-xs text-blue-400 font-medium px-2 py-0.5 rounded-md bg-blue-500/5 border border-blue-500/10">
                  <StickyNote size={12} />
                  <span className="truncate max-w-[200px]">{transaction.nota}</span>
                </div>
             )}
           </div>
        </div>

        {/* Branding/Context: Category & Tags (Col 6-9 - Hidden on small mobile) */}
        <div className="hidden md:flex md:col-span-4 flex-wrap gap-2 content-center opacity-60 group-hover:opacity-100 transition-opacity justify-start md:justify-center">
           {transaction.categoria && transaction.categoria !== '---' && (
             <span className="px-2 py-1 rounded-lg bg-primary-500/10 text-primary-300 border border-primary-500/10 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
               <TagIcon size={10} />
               {transaction.categoria}
             </span>
           )}
           {transaction.tags ? transaction.tags.split(',').map((tag, i) => (
             <span key={i} className="px-2 py-1 rounded-lg bg-surface-800 border border-white/5 text-[10px] uppercase font-bold tracking-wider text-surface-400 flex items-center gap-1 hover:bg-surface-700 hover:text-surface-200 transition-colors cursor-default">
               <TagIcon size={10} />
               {tag.trim()}
             </span>
           )) : (!transaction.categoria || transaction.categoria === '---') && (
             <span className="text-[10px] uppercase font-bold tracking-wider text-surface-600 select-none">Sin clasificación</span>
           )}
        </div>

        {/* Financials: Amount & Refundable (Col 10-12) */}
        <div className="md:col-span-3 flex flex-col items-end justify-center text-right mt-2 md:mt-0 pt-2 md:pt-0 border-t md:border-t-0 border-white/5 w-full md:w-auto relative">
           <div className="md:hidden text-[10px] font-bold uppercase tracking-widest text-surface-600 mb-1">Total</div>
           
           <div className={`text-2xl font-mono font-bold tracking-tighter flex items-center gap-1 ${
             isExpense 
               ? 'text-rose-400 text-shadow-sm' 
               : 'text-emerald-400 text-shadow-sm'
           }`}>
             {isExpense ? '-' : '+'}${Math.abs(transaction.MONTO).toFixed(2)}
           </div>

           {transaction.es_reembolsable && (
             <span className="mt-1 text-[9px] font-bold uppercase tracking-wider text-amber-300 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/10">
               Reembolsable
             </span>
           )}

           {/* Split Indicator */}
           {transaction.subTransactions && transaction.subTransactions.length > 1 && (
              <span className="mt-1 text-[9px] font-bold uppercase tracking-wider text-purple-300 bg-purple-500/10 px-1.5 py-0.5 rounded border border-purple-500/10 flex items-center gap-1 group/split" title="Transacción dividida">
                <Link2 size={8} className="rotate-45" />
                {transaction.subTransactions.length} partes
              </span>
           )}
           
           {/* Edit Icon (Visible on Hover) */}
           <div className="absolute right-full mr-4 top-1/2 -translate-y-1/2 flex items-center gap-2 opacity-0 translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300 pointer-events-none">
             <button
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit(transaction);
                }}
                className="w-8 h-8 rounded-lg bg-surface-700 hover:bg-surface-600 text-white flex items-center justify-center shadow-lg pointer-events-auto transition-colors"
             >
                <Edit2 size={14} />
             </button>
           </div>
        </div>

      </div>
    </div>
  );
}

interface TransactionTableProps {
  transactions: Transaction[];
  onEdit: (transaction: Transaction) => void;
  onQuickReview: (id: string) => void;
  isLoading: boolean;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
}

export function TransactionTable({ transactions, onEdit, onQuickReview, isLoading, selectedIds, onToggleSelect }: TransactionTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-4 p-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-28 bg-surface-900/50 rounded-2xl border border-white/5 animate-pulse" />
        ))}
      </div>
    );
  }

  if (transactions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-20 text-center h-full min-h-[400px]">
        <div className="relative mb-6 group">
           <div className="absolute inset-0 bg-primary-500/20 blur-3xl rounded-full opacity-50 group-hover:opacity-80 transition-opacity duration-1000"></div>
           <div className="relative w-24 h-24 bg-surface-900 rounded-full border border-white/10 shadow-2xl flex items-center justify-center group-hover:scale-105 transition-transform duration-500">
             <CheckCircle2 size={40} className="text-surface-600 group-hover:text-primary-400 transition-colors duration-500" />
           </div>
        </div>
        <h3 className="text-2xl font-bold text-white mb-2 tracking-tight">Todo al día</h3>
        <p className="text-surface-500 max-w-xs font-medium leading-relaxed">
          No hay transacciones por procesar.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 pb-8 animate-fade-in px-1">
      {transactions.map((transaction, index) => (
        <TransactionRow
          key={transaction.id}
          transaction={transaction}
          onEdit={onEdit}
          onQuickReview={onQuickReview}
          index={index}
          isSelected={selectedIds.has(transaction.id)}
          onToggleSelect={onToggleSelect}
        />
      ))}
    </div>
  );
}
