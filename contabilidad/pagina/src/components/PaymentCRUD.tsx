import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Edit2, ChevronRight, Calculator, DollarSign } from 'lucide-react';
import { 
  getGroups, createGroup, updateGroup, deleteGroup, 
  getPayments, createPayment, updatePayment, deletePayment,
  InterpolationGroup, InterpolatedPayment 
} from '../services/interpolated';


interface PaymentCRUDProps {
  groupType?: 'interpolated' | 'fixed';
  onDataChange?: () => void;
}

/**
 * `type` no dice qué es un grupo, dice **cómo se ejecuta**: al patrimonio solo se aplican
 * `fixed` e `interpolated`, así que un fondo, un portafolio de inversión y una serie que
 * generó una máquina acaban todos marcados `fixed` y esta pantalla los enseñaba mezclados
 * con los tres pagos fijos que el usuario sí escribió a mano.
 *
 * `origen` los separa. Y se **etiquetan en vez de esconderse**: un grupo invisible que
 * existe y se puede borrar es exactamente lo que hizo desaparecer los tres portafolios de
 * inversión el 2026-08-14.
 */
const ETIQUETA_ORIGEN: Record<string, string> = {
  fondo: 'fondo',
  inversion: 'inversión',
  generado: 'generado',
};

const DUENO_ORIGEN: Record<string, string> = {
  fondo: 'la pestaña de Fondos',
  inversion: 'el módulo de Inversiones',
  generado: 'la pantalla que lo genera',
};

/**
 * El color viene de **la familia, no del origen**: violeta es Inversiones y esmeralda es
 * Fondos, los mismos colores con los que se pinta cada módulo en su propia pantalla. Un
 * grupo generado hereda el color de quien lo generó —atenuado, y sangrado bajo él— así que
 * de un vistazo se ve de quién es sin leer un solo nombre.
 */
type Familia = 'inversion' | 'fondo' | 'manual';

const COLOR_FAMILIA: Record<Familia, { punto: string; chip: string }> = {
  inversion: { punto: 'bg-primary-400', chip: 'bg-primary-500/10 text-primary-300 border-primary-500/25' },
  fondo: { punto: 'bg-emerald-400', chip: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/25' },
  manual: { punto: 'bg-surface-500', chip: 'bg-surface-800/80 text-surface-400 border-white/10' },
};

const PaymentCRUD: React.FC<PaymentCRUDProps> = ({ groupType = 'interpolated', onDataChange }) => {
  const [groups, setGroups] = useState<InterpolationGroup[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<InterpolationGroup | null>(null);
  const [payments, setPayments] = useState<InterpolatedPayment[]>([]);
  const [loading, setLoading] = useState(true);

  const isFixed = groupType === 'fixed';
  const titleLabel = isFixed ? 'Inversiones' : 'Interpolaciones';
  const itemLabel = isFixed ? 'Inversión' : 'Interpolación';

  // Modal states
  const [isGroupModalOpen, setIsGroupModalOpen] = useState(false);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  
  // Form states
  const [groupForm, setGroupForm] = useState({ name: '', description: '' });
  const [paymentForm, setPaymentForm] = useState({ amount: '', start_date: '', end_date: '', note: '' });
  const [editingId, setEditingId] = useState<string | null>(null);

  // Por defecto, solo lo que el usuario escribió a mano. Los demás siguen alcanzables.
  const [verGenerados, setVerGenerados] = useState(false);

  useEffect(() => {
    fetchGroups();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groupType, verGenerados]);

  useEffect(() => {
    if (selectedGroup) {
      fetchPayments(selectedGroup.id);
    } else {
      setPayments([]);
    }
  }, [selectedGroup]);

  const fetchGroups = async () => {
    try {
      const data = await getGroups(groupType, verGenerados ? undefined : 'manual');
      // Alfabético, y no es cosmética: los grupos generados se llaman «X Pagos», así que
      // ordenar por nombre es lo que los deja pegados al grupo que los genera. El CSV
      // viene en orden de inserción, que los separa por toda la lista.
      data.sort((a, b) => a.name.localeCompare(b.name, 'es'));
      setGroups(data);
      // Si el grupo elegido desaparece al cambiar el filtro, hay que soltarlo: si no, el
      // panel de la derecha sigue enseñando los pagos de algo que ya no está en la lista.
      setSelectedGroup(previo => {
        if (previo && data.some(g => g.id === previo.id)) return previo;
        return data[0] ?? null;
      });
    } catch (error) {
      console.error('Error fetching groups:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchPayments = async (groupId: string) => {
    try {
      const data = await getPayments(groupId);
      // Ordenar por fecha de vencimiento (end_date) de forma descendente (más recientes primero)
      // Un `end_date` vacío significa «para siempre», así que es el más reciente de todos.
      // Sin esto, `new Date(null)` da NaN y el orden se vuelve indefinido.
      const alFinal = (f: string | null) => (f ? new Date(f).getTime() : Number.MAX_SAFE_INTEGER);
      const sortedData = data.sort((a, b) => alFinal(b.end_date) - alFinal(a.end_date));
      setPayments(sortedData);
    } catch (error) {
      console.error('Error fetching payments:', error);
    }
  };

  const handleCreateGroup = async () => {
    try {
      if (editingId) {
        await updateGroup(editingId, groupForm);
      } else {
        await createGroup({ ...groupForm, type: groupType });
      }
      setIsGroupModalOpen(false);
      setGroupForm({ name: '', description: '' });
      setEditingId(null);
      fetchGroups();
      if (onDataChange) onDataChange();
    } catch (error) {
      console.error('Error saving group:', error);
    }
  };

  const handleDeleteGroup = async (id: string) => {
    if (!confirm('Are you sure? This will delete all associated payments.')) return;
    try {
      await deleteGroup(id);
      if (selectedGroup?.id === id) setSelectedGroup(null);
      fetchGroups();
      if (onDataChange) onDataChange();
    } catch (error) {
      console.error('Error deleting group:', error);
    }
  };

  const handleCreatePayment = async () => {
    if (!selectedGroup) return;
    try {
      const paymentData = {
        amount: parseFloat(paymentForm.amount),
        start_date: paymentForm.start_date || null,
        end_date: paymentForm.end_date || null,
        note: paymentForm.note
      };

      if (editingId) {
        await updatePayment(editingId, paymentData);
      } else {
        await createPayment(selectedGroup.id, paymentData);
      }
      setIsPaymentModalOpen(false);
      setPaymentForm({ amount: '', start_date: '', end_date: '', note: '' });
      setEditingId(null);
      fetchPayments(selectedGroup.id);
      if (onDataChange) onDataChange();
    } catch (error) {
      console.error('Error saving payment:', error);
    }
  };

  const handleDeletePayment = async (id: string) => {
    if (!confirm('Are you sure?')) return;
    try {
      await deletePayment(id);
      if (selectedGroup) fetchPayments(selectedGroup.id);
      if (onDataChange) onDataChange();
    } catch (error) {
      console.error('Error deleting payment:', error);
    }
  };

  const openGroupModal = (group?: InterpolationGroup) => {
    if (group) {
      setGroupForm({ name: group.name, description: group.description || '' });
      setEditingId(group.id);
    } else {
      setGroupForm({ name: '', description: '' });
      setEditingId(null);
    }
    setIsGroupModalOpen(true);
  };

  const openPaymentModal = (payment?: InterpolatedPayment) => {
    if (payment) {
      // El formulario usa cadena vacía para «sin fecha»; el `null` es cosa de la API.
      setPaymentForm({
        amount: payment.amount.toString(),
        start_date: payment.start_date || '',
        end_date: payment.end_date || '',
        note: payment.note || ''
      });
      setEditingId(payment.id);
    } else {
      setPaymentForm({ amount: '', start_date: '', end_date: '', note: '' });
      setEditingId(null);
    }
    setIsPaymentModalOpen(true);
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
  };

  return (
    <div className="flex h-full bg-surface-950 rounded-xl overflow-hidden border border-white/[0.06]">
      {/* Sidebar for Groups */}
      <div className="w-72 border-r border-white/[0.06] bg-surface-900/50 backdrop-blur-xl flex flex-col">
        <div className="p-4 border-b border-white/[0.06] flex justify-between items-center">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-primary-500/10">
              <Calculator className="w-4 h-4 text-primary-400" />
            </div>
            {titleLabel}
          </h2>
          <button
            onClick={() => openGroupModal()}
            className="p-1.5 hover:bg-white/[0.06] rounded-lg text-surface-400 hover:text-white transition-all"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
        {isFixed && (
          <label className="px-4 py-2.5 border-b border-white/[0.06] flex items-center gap-2 cursor-pointer text-[11px] text-surface-400 hover:text-surface-200 transition-colors">
            <input
              type="checkbox"
              checked={verGenerados}
              onChange={e => setVerGenerados(e.target.checked)}
              className="accent-primary-500"
            />
            Ver los que gestionan otras pantallas
          </label>
        )}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {groups.length === 0 && (
            <p className="text-[11px] text-surface-500 px-1 py-3 leading-relaxed">
              No hay ninguno escrito a mano.
              {isFixed && ' Marca la casilla de arriba para ver los que gestionan Fondos e Inversiones.'}
            </p>
          )}
          {groups.map(group => {
            const generado = group.origen === 'generado';
            // Un generado toma la familia de su padre; si el padre no está en la lista
            // (filtro activo) se queda en la suya, que es la neutra.
            const padre = generado
              ? groups.find(g => g.id === group.fondo_origen)
              : undefined;
            const familia: Familia = (generado
              ? (padre?.origen === 'inversion' || padre?.origen === 'fondo' ? padre.origen : 'manual')
              : (group.origen === 'inversion' || group.origen === 'fondo' ? group.origen : 'manual'));
            const color = COLOR_FAMILIA[familia];
            return (
            <div
              key={group.id}
              onClick={() => setSelectedGroup(group)}
              className={`p-3 rounded-lg cursor-pointer transition-all border ${
                generado ? 'ml-4' : ''
              } ${
                selectedGroup?.id === group.id
                  ? 'bg-primary-500/10 border-primary-500/30 shadow-sm'
                  : 'hover:bg-surface-800/70 border-transparent hover:border-white/[0.05]'
              }`}
            >
              <div className="flex justify-between items-start group">
                <div className="flex-1 min-w-0">
                  <h3 className={`font-medium text-sm flex items-center gap-2 flex-wrap ${selectedGroup?.id === group.id ? 'text-primary-300' : 'text-white'}`}>
                    <span
                      className={`w-2 h-2 rounded-sm shrink-0 ${color.punto} ${generado ? 'opacity-40' : ''}`}
                      aria-hidden="true"
                    />
                    {group.name}
                    {group.origen && group.origen !== 'manual' && (
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wide border ${
                        generado ? COLOR_FAMILIA.manual.chip : color.chip
                      }`}>
                        {ETIQUETA_ORIGEN[group.origen]}
                      </span>
                    )}
                  </h3>
                  {group.description && (
                    <p className="text-xs text-surface-500 mt-1 line-clamp-2">
                      {group.description}
                    </p>
                  )}
                  {group.origen && group.origen !== 'manual' && (
                    <p className="text-[10px] text-surface-500 mt-1">
                      Lo gestiona {DUENO_ORIGEN[group.origen]}; aquí es solo de lectura.
                    </p>
                  )}
                </div>
                <div className={`flex gap-1 transition-opacity ${
                  group.origen && group.origen !== 'manual'
                    ? 'hidden'
                    : 'opacity-0 group-hover:opacity-100'
                }`}>
                  <button
                    onClick={(e) => { e.stopPropagation(); openGroupModal(group); }}
                    className="p-1 hover:bg-white/[0.08] rounded text-surface-400 hover:text-white transition-all"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteGroup(group.id); }}
                    className="p-1 hover:bg-red-500/10 rounded text-surface-400 hover:text-red-400 transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
            );
          })}
          {groups.length === 0 && !loading && (
            <div className="text-center py-10 text-surface-600 text-sm">
              No hay grupos creados
            </div>
          )}
        </div>
      </div>

      {/* Main Content for Payments */}
      <div className="flex-1 overflow-y-auto bg-surface-950">
        {selectedGroup ? (
          <div className="p-6 max-w-5xl mx-auto">
            <div className="flex justify-between items-center mb-6">
              <div>
                <h1 className="text-xl font-bold text-white mb-1">
                  {selectedGroup.name}
                </h1>
                <p className="text-sm text-surface-400">
                  {selectedGroup.description || 'Sin descripción'}
                </p>
              </div>
              <button
                onClick={() => openPaymentModal()}
                className="px-4 py-2 bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600 text-white text-sm font-medium rounded-lg transition-all flex items-center gap-2 shadow-md shadow-primary-900/20"
              >
                <Plus className="w-4 h-4" />
                Nueva {itemLabel}
              </button>
            </div>

            <div className="space-y-2">
              {payments.map(payment => (
                  <div
                    key={payment.id}
                    className="group bg-surface-900/40 backdrop-blur-sm rounded-lg px-4 py-3 border border-white/[0.04] hover:border-primary-500/30 hover:bg-surface-800/60 transition-all duration-200 flex items-center justify-between gap-4"
                  >
                    {/* Horizontal Layout: Icon | Amount | Note | Dates | Actions */}
                    
                    {/* Left: Icon + Amount */}
                    <div className="flex items-center gap-3">
                      <div className="flex-shrink-0 w-8 h-8 rounded bg-primary-500/10 text-primary-400 flex items-center justify-center">
                        <DollarSign className="w-4 h-4" />
                      </div>
                      <div className="font-mono text-sm font-bold text-white min-w-[80px]">
                        {formatCurrency(payment.amount)}
                      </div>
                    </div>

                    {/* Middle: Note (Flex grow) */}
                    <div className="flex-1 min-w-0 flex items-center">
                      {payment.note ? (
                        <span className="text-xs text-surface-400 truncate border-l border-white/[0.06] pl-4 max-w-full block">
                          {payment.note}
                        </span>
                      ) : (
                        <span className="text-xs text-surface-600 italic border-l border-white/[0.06] pl-4">
                          Sin nota
                        </span>
                      )}
                    </div>

                    {/* Right: Dates + Actions */}
                    <div className="flex items-center gap-4 flex-shrink-0">
                      <div className="flex items-center gap-1.5 text-[11px] text-surface-500 font-medium bg-surface-950/30 px-2 py-1 rounded">
                        <span className={payment.start_date ? '' : 'italic text-surface-600'}>
                          {payment.start_date || 'desde siempre'}
                        </span>
                        <ChevronRight className="w-2.5 h-2.5 text-surface-600" />
                        <span className={payment.end_date ? '' : 'italic text-surface-600'}>
                          {payment.end_date || 'para siempre'}
                        </span>
                      </div>
                      
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => openPaymentModal(payment)}
                          className="p-1.5 hover:bg-white/[0.08] rounded text-surface-400 hover:text-white transition-all"
                          title="Editar"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeletePayment(payment.id)}
                          className="p-1.5 hover:bg-red-500/10 rounded text-surface-400 hover:text-red-400 transition-all"
                          title="Eliminar"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
              ))}

              {payments.length === 0 && (
                <div className="text-center py-20 bg-surface-900/50 backdrop-blur-xl rounded-xl border border-white/[0.06] border-dashed shadow-lg shadow-black/20">
                  <div className="w-16 h-16 rounded-2xl bg-surface-800/50 flex items-center justify-center mx-auto mb-4">
                    <Calculator className="w-8 h-8 text-surface-600" />
                  </div>
                  <p className="text-surface-500 text-sm mb-4">No hay pagos en este grupo</p>
                  <button
                    onClick={() => openPaymentModal()}
                    className="text-primary-400 hover:text-primary-300 text-sm font-medium transition-colors"
                  >
                    Crear el primero
                  </button>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-surface-600">
            <div className="w-16 h-16 rounded-2xl bg-surface-800/50 flex items-center justify-center mb-4">
              <Calculator className="w-8 h-8 opacity-40" />
            </div>
            <p className="text-sm">Selecciona un grupo para ver sus interpolaciones</p>
          </div>
        )}
      </div>

      {/* Group Modal */}
      {isGroupModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setIsGroupModalOpen(false)}>
          <div className="bg-surface-900/95 backdrop-blur-xl rounded-xl shadow-2xl w-full max-w-md border border-white/[0.08] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="p-5 border-b border-white/[0.06]">
              <h3 className="text-lg font-bold text-white">
                {editingId ? 'Editar Grupo' : 'Nuevo Grupo'}
              </h3>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-2">Nombre</label>
                <input
                  type="text"
                  value={groupForm.name}
                  onChange={e => setGroupForm({ ...groupForm, name: e.target.value })}
                  className="w-full px-3 py-2.5 bg-surface-800/50 border border-white/[0.08] rounded-lg text-white placeholder-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all"
                  placeholder="Ej: Pagos Mamá"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-2">Descripción</label>
                <textarea
                  value={groupForm.description}
                  onChange={e => setGroupForm({ ...groupForm, description: e.target.value })}
                  className="w-full px-3 py-2.5 bg-surface-800/50 border border-white/[0.08] rounded-lg text-white placeholder-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all min-h-[100px] resize-none"
                  placeholder="Descripción opcional..."
                />
              </div>
            </div>
            <div className="p-4 bg-surface-950/50 flex justify-end gap-3 border-t border-white/[0.06]">
              <button
                onClick={() => setIsGroupModalOpen(false)}
                className="px-4 py-2 text-sm font-medium text-surface-300 hover:text-white hover:bg-white/[0.06] rounded-lg transition-all"
              >
                Cancelar
              </button>
              <button
                onClick={handleCreateGroup}
                className="px-4 py-2 bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600 text-white text-sm font-medium rounded-lg transition-all shadow-md shadow-primary-900/20 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!groupForm.name}
              >
                Guardar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Payment Modal */}
      {isPaymentModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setIsPaymentModalOpen(false)}>
          <div className="bg-surface-900/95 backdrop-blur-xl rounded-xl shadow-2xl w-full max-w-md border border-white/[0.08] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="p-5 border-b border-white/[0.06]">
              <h3 className="text-lg font-bold text-white">
                {editingId ? 'Editar Pago' : 'Nuevo Pago'}
              </h3>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-2">Monto</label>
                <input
                  type="number"
                  step="0.01"
                  value={paymentForm.amount}
                  onChange={e => setPaymentForm({ ...paymentForm, amount: e.target.value })}
                  className="w-full px-3 py-2.5 bg-surface-800/50 border border-white/[0.08] rounded-lg text-white placeholder-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all"
                  placeholder="0.00"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-2">
                    Desde{isFixed && <span className="ml-1 text-surface-500 font-normal">· vacío = siempre</span>}
                  </label>
                  <input
                    type="date"
                    value={paymentForm.start_date}
                    onChange={e => setPaymentForm({ ...paymentForm, start_date: e.target.value })}
                    className="w-full px-3 py-2.5 bg-surface-800/50 border border-white/[0.08] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-2">
                    Hasta{isFixed && <span className="ml-1 text-surface-500 font-normal">· vacío = siempre</span>}
                  </label>
                  <input
                    type="date"
                    value={paymentForm.end_date}
                    onChange={e => setPaymentForm({ ...paymentForm, end_date: e.target.value })}
                    className="w-full px-3 py-2.5 bg-surface-800/50 border border-white/[0.08] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-2">Nota</label>
                <input
                  type="text"
                  value={paymentForm.note}
                  onChange={e => setPaymentForm({ ...paymentForm, note: e.target.value })}
                  className="w-full px-3 py-2.5 bg-surface-800/50 border border-white/[0.08] rounded-lg text-white placeholder-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all"
                  placeholder="Nota opcional..."
                />
              </div>
            </div>
            <div className="p-4 bg-surface-950/50 flex justify-end gap-3 border-t border-white/[0.06]">
              <button
                onClick={() => setIsPaymentModalOpen(false)}
                className="px-4 py-2 text-sm font-medium text-surface-300 hover:text-white hover:bg-white/[0.06] rounded-lg transition-all"
              >
                Cancelar
              </button>
              <button
                onClick={handleCreatePayment}
                className="px-4 py-2 bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600 text-white text-sm font-medium rounded-lg transition-all shadow-md shadow-primary-900/20 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!paymentForm.amount || (!isFixed && (!paymentForm.start_date || !paymentForm.end_date))}
              >
                Guardar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PaymentCRUD;
