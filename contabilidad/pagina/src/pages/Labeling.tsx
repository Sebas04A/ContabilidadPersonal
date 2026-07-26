import { useState } from 'react';
import { DailyLabeling } from './labeling/DailyLabeling';
import { BulkLabeling } from './labeling/BulkLabeling';
import { RulesManager } from './labeling/RulesManager';
import { CalendarDays, Layers, Wand2 } from 'lucide-react';

type LabelingTab = 'diario' | 'masivo' | 'reglas';

const TABS: { id: LabelingTab; label: string; icon: JSX.Element; accent: string }[] = [
  { id: 'diario', label: 'Diario', icon: <CalendarDays size={17} />, accent: 'from-blue-600 to-cyan-500' },
  { id: 'masivo', label: 'Masivo', icon: <Layers size={17} />, accent: 'from-emerald-600 to-teal-500' },
  { id: 'reglas', label: 'Reglas', icon: <Wand2 size={17} />, accent: 'from-purple-600 to-pink-500' },
];

export function Labeling() {
  const [tab, setTab] = useState<LabelingTab>('diario');

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden relative">
      <div className="flex justify-center pt-5 pb-1 shrink-0 z-30">
        <div className="p-1.5 bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl flex items-center gap-1 shadow-2xl">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`
                flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-300 relative overflow-hidden
                ${tab === t.id ? 'text-white scale-[1.02]' : 'text-slate-400 hover:text-white hover:bg-white/5'}
              `}
            >
              {tab === t.id && (
                <div
                  className={`absolute inset-0 bg-gradient-to-r ${t.accent} rounded-xl -z-10 animate-in fade-in zoom-in-95 duration-300`}
                ></div>
              )}
              {t.icon}
              <span>{t.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col overflow-hidden animate-in fade-in duration-300">
        {tab === 'diario' ? <DailyLabeling /> : tab === 'masivo' ? <BulkLabeling /> : <RulesManager />}
      </div>
    </div>
  );
}
