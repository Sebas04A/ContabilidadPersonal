import { LayoutDashboard, Tag, ChevronLeft, PieChart, User, Calculator, Wallet, Database, Search, Sparkles, PiggyBank, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

interface SidebarProps {
  currentView: string;
  onViewChange: (view: string) => void;
}

export function Sidebar({ currentView, onViewChange }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);

  const navItems = [
    { id: 'sources', icon: <Database size={20} />, label: 'Fuentes' },
    { id: 'explorer', icon: <Search size={20} />, label: 'Explorar' },
    { id: 'etiquetado', icon: <Tag size={20} />, label: 'Etiquetado' },
    { id: 'deudas', icon: <Wallet size={20} />, label: 'Deudas' },
    { id: 'fondos', icon: <PiggyBank size={20} />, label: 'Fondos' },
    { id: 'variables', icon: <Calculator size={20} />, label: 'Variables' },
    { id: 'dashboard', icon: <LayoutDashboard size={20} />, label: 'Dashboard' },
    { id: 'verificacion', icon: <ShieldCheck size={20} />, label: 'Verificación' },
    { id: 'presupuesto', icon: <PieChart size={20} />, label: 'Presupuesto' },
    { id: 'advanced', icon: <Sparkles size={20} className="text-pink-400" />, label: 'Analíticas Avanzadas' },
    // { id: 'reportes', icon: <PieChart size={20} />, label: 'Reportes' },
    // { id: 'cuentas', icon: <CreditCard size={20} />, label: 'Cuentas' },
    // { id: 'configuracion', icon: <Settings size={20} />, label: 'Configuración' },
  ];

  return (
    <aside 
      className={`
        relative z-30 transition-all duration-500 ease-[cubic-bezier(0.25,1,0.5,1)]
        ${collapsed ? 'w-24' : 'w-80'}
        flex flex-col h-screen
        bg-surface-950/90 backdrop-blur-2xl border-r border-white/5 shadow-2xl
      `}
    >
      {/* Background Glow - Subtle Ambient Light */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none -z-10">
        <div className="absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-primary-900/10 to-transparent opacity-50" />
      </div>

      {/* Toggle Button */}
      <button 
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-4 top-12 w-8 h-8 bg-surface-800 hover:bg-primary-600 text-white rounded-full flex items-center justify-center shadow-lg transition-all hover:scale-110 z-50 ring-4 ring-surface-950 border border-white/10"
      >
        <div className={`transition-transform duration-500 ${collapsed ? 'rotate-180' : 'rotate-0'}`}>
          <ChevronLeft size={16} />
        </div>
      </button>

      {/* Header */}
      <div className={`p-8 mb-4 flex items-center transition-all duration-500 ${collapsed ? 'justify-center px-4' : ''}`}>
        <div className="flex items-center gap-4">
          <div className="relative group cursor-pointer shrink-0">
            <div className="absolute -inset-1 bg-gradient-to-r from-primary-500 to-secondary-500 rounded-2xl blur opacity-20 group-hover:opacity-60 transition duration-500"></div>
            <div className="relative w-12 h-12 rounded-2xl bg-surface-900 border border-white/10 flex items-center justify-center text-white font-bold text-xl shadow-xl overflow-hidden">
              <span className="bg-clip-text text-transparent bg-gradient-to-tr from-primary-400 to-secondary-400 z-10">C</span>
            </div>
          </div>
          
          <div className={`overflow-hidden transition-all duration-500 ${collapsed ? 'w-0 opacity-0' : 'w-auto opacity-100'}`}>
            <h1 className="text-xl font-bold text-white tracking-tight whitespace-nowrap">Contabilidad</h1>
            <p className="text-xs text-surface-500 font-medium tracking-widest uppercase">Personal Pro</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 space-y-2 overflow-y-auto custom-scrollbar">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onViewChange(item.id)}
            className={`
              w-full flex items-center gap-4 p-4 rounded-xl transition-all duration-300 group relative overflow-hidden
              ${currentView === item.id 
                ? 'text-white bg-white/5 border border-white/5' 
                : 'text-surface-400 hover:text-white hover:bg-white/[0.03]'
              }
              ${collapsed ? 'justify-center px-0' : ''}
            `}
          >
            {/* Active State Indicator */}
            {currentView === item.id && (
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-primary-500 rounded-r-full shadow-[0_0_12px_#8b5cf680]" />
            )}

            <span className={`relative z-10 transition-transform duration-300 shrink-0 ${currentView === item.id ? 'scale-110 text-primary-400' : 'group-hover:scale-110 group-hover:text-surface-200'}`}>
              {item.icon}
            </span>
            
            <div className={`relative z-10 overflow-hidden transition-all duration-500 origin-left ${collapsed ? 'w-0 opacity-0 scale-x-0' : 'w-auto opacity-100 scale-x-100'}`}>
              <span className="font-medium text-[15px] whitespace-nowrap">
                {item.label}
              </span>
            </div>

            {/* Tooltip */}
            {collapsed && (
              <div className="absolute left-full ml-4 px-3 py-1.5 bg-surface-800 border border-white/10 text-white text-xs font-semibold rounded-lg opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-all duration-200 translate-x-2 group-hover:translate-x-0 shadow-xl">
                {item.label}
              </div>
            )}
          </button>
        ))}
      </nav>

      {/* Footer / User Profile */}
      <div className="p-4 mx-4 mb-4 rounded-2xl bg-surface-900/50 border border-white/[0.05]">
        <button className={`w-full flex items-center gap-4 transition-all duration-300 group ${collapsed ? 'justify-center' : ''}`}>
          <div className="relative shrink-0">
             <div className="w-10 h-10 rounded-full bg-surface-800 border border-white/10 flex items-center justify-center shadow-lg group-hover:border-primary-500/50 transition-colors">
               <User size={18} className="text-surface-400 group-hover:text-white transition-colors" />
             </div>
             <div className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-emerald-500 border-2 border-surface-950 rounded-full"></div>
          </div>
          
          <div className={`overflow-hidden transition-all duration-500 text-left ${collapsed ? 'w-0 opacity-0' : 'w-auto opacity-100'}`}>
            <p className="text-sm font-bold text-white truncate group-hover:text-primary-400 transition-colors">Usuario</p>
            <p className="text-[10px] text-surface-500 font-medium tracking-wider uppercase truncate">Online</p>
          </div>
        </button>
      </div>
    </aside>
  );
}

