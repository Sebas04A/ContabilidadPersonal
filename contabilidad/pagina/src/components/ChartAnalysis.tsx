
import { X, TrendingUp, TrendingDown, ArrowRight } from 'lucide-react';

interface Point {
  date: string;
  value: number;
}

export interface Curve {
    id: string;
    start: Point;
    end: Point;
}

interface ChartAnalysisProps {
  curves: Curve[];
  onRemove: (id: string) => void;
}

export function ChartAnalysis({ curves, onRemove }: ChartAnalysisProps) {
  if (!curves || curves.length === 0) {
    return (
      <div className="mt-4 text-center p-4 rounded-xl border border-dashed border-white/10 text-gray-500 text-sm">
        Activa el modo de selección y haz clic en dos puntos para agregar un nuevo análisis.
      </div>
    );
  }

  return (
    <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 animate-in fade-in slide-in-from-bottom-4">
        {curves.map((curve) => {
            const days = (new Date(curve.end.date).getTime() - new Date(curve.start.date).getTime()) / (1000 * 3600 * 24);
            const diff = curve.end.value - curve.start.value;
            const slope = days > 0 ? diff / days : 0;
            
            return (
                <div key={curve.id} className="bg-slate-900/50 p-5 rounded-2xl border border-white/10 shadow-lg backdrop-blur-sm relative group hover:border-blue-500/30 transition-all">
                    <button 
                        onClick={() => onRemove(curve.id)} 
                        className="absolute top-3 right-3 p-1.5 text-gray-500 hover:text-white hover:bg-white/10 rounded-full opacity-0 group-hover:opacity-100 transition-all z-10"
                    >
                        <X size={16} />
                    </button>

                    <div className="flex items-center justify-between mb-4">
                        <span className="text-xs font-semibold text-blue-400 uppercase tracking-wider bg-blue-500/10 px-2 py-1 rounded-md">
                            {Math.round(days)} días
                        </span>
                        
                        <div className="flex items-center gap-2 text-xs text-gray-400 font-mono">
                           <span>{new Date(curve.start.date).toLocaleDateString(undefined, {month:'short', day:'numeric'})}</span>
                           <ArrowRight size={12} />
                           <span>{new Date(curve.end.date).toLocaleDateString(undefined, {month:'short', day:'numeric'})}</span>
                        </div>
                    </div>

                    <div className="flex flex-col gap-4">
                         {/* Slope Main */}
                         <div className="flex items-center justify-between">
                             <div className="flex items-center gap-3">
                                {slope >= 0 ? <TrendingUp className="text-green-500" size={24} /> : <TrendingDown className="text-red-500" size={24} />}
                                <div className="flex flex-col">
                                    <span className="text-xs text-gray-500">Velocidad</span>
                                    <span className="text-xl font-bold text-white tracking-tight">
                                        {slope.toLocaleString('en-US', { style: 'currency', currency: 'USD' })}
                                        <span className="text-xs text-gray-500 font-medium">/día</span>
                                    </span>
                                </div>
                             </div>
                         </div>
                         
                         {/* Total Diff */}
                         <div className="pt-3 border-t border-white/5 flex justify-between items-center text-sm">
                             <span className="text-gray-500">Variación Total</span>
                             <span className={`font-bold ${diff >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {diff > 0 ? '+' : ''}{diff.toLocaleString('en-US', { style: 'currency', currency: 'USD' })}
                             </span>
                         </div>
                    </div>
                </div>
            );
        })}
    </div>
  );
}
