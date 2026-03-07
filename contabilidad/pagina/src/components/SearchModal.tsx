import { useState, useEffect } from 'react';
import { Search, X, Tag, Loader2, ArrowRight } from 'lucide-react';
import { useSearchTransactions } from '../hooks/useTransactions';
import { Transaction } from '../services/api';

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectDate: (date: string) => void;
}

export function SearchModal({ isOpen, onClose, onSelectDate }: SearchModalProps) {
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  
  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
    }, 500);
    return () => clearTimeout(timer);
  }, [query]);

  const { data: results, isLoading } = useSearchTransactions(debouncedQuery);

  if (!isOpen) return null;

  const handleResultClick = (date: string) => {
    // Extract date part YYYY-MM-DD from "YYYY-MM-DD HH:MM:SS"
    const datePart = date.split(' ')[0];
    onSelectDate(datePart);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" 
        onClick={onClose}
      />

      {/* Modal Content */}
      <div className="relative w-full max-w-2xl bg-[#0f172a] border border-white/10 rounded-2xl shadow-2xl overflow-hidden animate-slide-up flex flex-col max-h-[80vh]">
        
        {/* Header / Input */}
        <div className="p-4 border-b border-white/10 flex items-center gap-3 bg-white/[0.02]">
          <Search className="text-gray-400" size={20} />
          <input
            type="text"
            placeholder="Buscar transacciones..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-transparent border-none outline-none text-white placeholder-gray-500 text-lg"
            autoFocus
          />
          <button 
            onClick={onClose}
            className="p-1 hover:bg-white/10 rounded-full transition-colors text-gray-400 hover:text-white"
          >
            <X size={20} />
          </button>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-2">
            
          {isLoading ? (
            <div className="py-12 flex flex-col items-center justify-center text-gray-400">
              <Loader2 className="animate-spin mb-2" size={24} />
              <p>Buscando...</p>
            </div>
          ) : query.length > 2 && results?.length === 0 ? (
             <div className="py-12 text-center text-gray-500">
               <p>No se encontraron resultados para "{query}"</p>
             </div>
          ) : !query || query.length <= 2 ? (
             <div className="py-12 text-center text-gray-600">
               <p>Escribe al menos 3 caracteres para buscar</p>
             </div>
          ) : (
            <div className="space-y-1">
              {results?.map((tx: Transaction) => (
                <button
                  key={tx.id}
                  onClick={() => handleResultClick(tx.FECHA)}
                  className="w-full text-left p-3 rounded-xl hover:bg-white/5 transition-colors group flex items-start gap-4 border border-transparent hover:border-white/5"
                >
                  {/* Date Box */}
                  <div className="flex flex-col items-center justify-center p-2 bg-white/5 rounded-lg border border-white/5 min-w-[60px]">
                    <span className="text-xs text-gray-400 uppercase font-bold">
                        {new Date(tx.FECHA).toLocaleString('es-ES', { month: 'short' })}
                    </span>
                    <span className="text-lg font-bold text-white leading-none">
                        {new Date(tx.FECHA).getDate()}
                    </span>
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                         <h4 className="font-medium text-white truncate max-w-[300px]" title={tx.nombre_limpio || tx.DESCRIPCION}>
                             {tx.nombre_limpio || tx.DESCRIPCION}
                         </h4>
                         <span className={`font-mono font-bold ${tx.MONTO >= 0 ? 'text-emerald-400' : 'text-gray-300'}`}>
                             ${tx.MONTO.toFixed(2)}
                         </span>
                    </div>
                    
                    <div className="flex items-center gap-3 text-xs text-gray-400">
                        {tx.categoria && (
                            <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-300 border border-blue-500/20">
                                {tx.categoria}
                            </span>
                        )}
                        {tx.tags && (
                             <div className="flex items-center gap-1">
                                 <Tag size={10} />
                                 <span className="truncate max-w-[150px]">{tx.tags.replace(/,/g, ', ')}</span>
                             </div>
                        )}
                        {!tx.revisado && (
                            <span className="text-orange-400 flex items-center gap-1">
                                ● Pendiente
                            </span>
                        )}
                    </div>
                     <div className="text-[10px] text-gray-600 truncate mt-1">
                         {tx.DESCRIPCION}
                     </div>
                  </div>
                  
                  <div className="self-center opacity-0 group-hover:opacity-100 transition-opacity">
                      <ArrowRight size={16} className="text-gray-500" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
