import { useState, useRef, useEffect } from 'react';
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon } from 'lucide-react';

interface CalendarPopoverProps {
  selectedDate: string;
  onDateSelect: (date: string) => void;
  availableDates: string[];
}

export function CalendarPopover({ selectedDate, onDateSelect, availableDates }: CalendarPopoverProps) {
  const [isOpen, setIsOpen] = useState(false);
  const date = new Date(selectedDate + 'T00:00:00');
  const [currentMonth, setCurrentMonth] = useState(date);
  const containerRef = useRef<HTMLDivElement>(null);
  // Close when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Sync internal month state when selectedDate changes externally
  useEffect(() => {
    setCurrentMonth(date);
  }, [selectedDate]);

  const daysInMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0).getDate();
  const firstDayOfMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1).getDay(); // 0 = Sunday

  // Adjust for Monday start if desired (Optional, keeping Sunday start for standard view)
  const startingEmptyCells = Array(firstDayOfMonth).fill(null);
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);

  const prevMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
  };

  const nextMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
  };

  const handleDateClick = (day: number) => {
    const newDate = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), day);
    // Format as YYYY-MM-DD manually to avoid timezone issues
    const year = newDate.getFullYear();
    const month = String(newDate.getMonth() + 1).padStart(2, '0');
    const d = String(day).padStart(2, '0');
    const dateString = `${year}-${month}-${d}`;
    
    onDateSelect(dateString);
    setIsOpen(false);
  };

  const isDateWithData = (day: number) => {
    // Check if this specific day exists in availableDates
    const year = currentMonth.getFullYear();
    const month = String(currentMonth.getMonth() + 1).padStart(2, '0');
    const d = String(day).padStart(2, '0');
    const checkDate = `${year}-${month}-${d}`;
    return availableDates.includes(checkDate);
  };

  const isSelected = (day: number) => {
    const selected = date;
    return (
      selected.getDate() === day &&
      selected.getMonth() === currentMonth.getMonth() &&
      selected.getFullYear() === currentMonth.getFullYear()
    );
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl transition-all text-white font-medium group"
      >
        <CalendarIcon size={16} className="text-blue-400 group-hover:text-blue-300" />
        <span className="capitalize">
          {date.toLocaleDateString('es-EC', {
            weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
          })}
        </span>
      </button>

      {isOpen && (
        <div className="absolute top-full mt-2 left-0 transform -translate-x-1/4 sm:translate-x-0 z-50 w-72 bg-[#121218] border border-white/10 rounded-2xl shadow-2xl p-4 animate-fade-in backdrop-blur-3xl">
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <button onClick={prevMonth} className="p-1 hover:bg-white/10 rounded-lg text-gray-400 hover:text-white transition-colors">
              <ChevronLeft size={20} />
            </button>
            <span className="font-bold text-white capitalize">
              {currentMonth.toLocaleDateString('es-EC', { month: 'long', year: 'numeric' })}
            </span>
            <button onClick={nextMonth} className="p-1 hover:bg-white/10 rounded-lg text-gray-400 hover:text-white transition-colors">
              <ChevronRight size={20} />
            </button>
          </div>

          {/* User Hint */}
          <div className="text-xs text-center text-gray-500 mb-2 flex items-center justify-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span> Con datos
          </div>

          {/* Days Grid */}
          <div className="grid grid-cols-7 gap-1 text-center mb-2">
            {['Do', 'Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sa'].map(d => (
              <span key={d} className="text-xs text-gray-500 font-medium">{d}</span>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {startingEmptyCells.map((_, i) => (
              <div key={`empty-${i}`} />
            ))}
            {days.map(day => {
              const hasData = isDateWithData(day);
              const selected = isSelected(day);
              
              return (
                <button
                  key={day}
                  onClick={() => handleDateClick(day)}
                  disabled={!hasData && !selected} // Optional: Disable days without data? Or keep open for adding new? User asked for "Nav to days with data", let's keep it clickable but visually distinct
                  className={`
                    h-8 w-8 rounded-full flex items-center justify-center text-sm relative transition-all
                    ${selected 
                      ? 'bg-blue-600 text-white font-bold shadow-lg shadow-blue-900/50' 
                      : 'hover:bg-white/10 text-gray-300'}
                    ${!hasData && !selected ? 'opacity-30' : ''}
                  `}
                >
                  {day}
                  {hasData && !selected && (
                    <span className="absolute bottom-1 w-1 h-1 rounded-full bg-blue-500"></span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
