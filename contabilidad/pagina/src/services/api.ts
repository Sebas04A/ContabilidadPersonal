import axios from 'axios';

// Use relative URL since we have a proxy configured in vite.config.ts
const API_BASE = '/api';

// --- Types ---
export interface Transaction {
  id: string;
  FECHA: string;
  DESCRIPCION: string;
  MONTO: number;
  TIPO: string;
  nombre_limpio: string;
  categoria: string;
  tags: string;
  prioridad: string;
  es_fijo: boolean;
  pertenece_a: string;
  es_reembolsable: boolean;
  deudor: string;
  felicidad: number;
  revisado: boolean;
  // 'HH:MM' when known, '' when not. Two origins: BANCA carries it in the
  // statement itself; TARJETA has it recovered from the bank's consumption emails.
  HORA?: string | null;
  // UI Only
  subTransactions?: Transaction[];
  nota: string;
  split_group_id: string;
  group_id?: string;
  fondo_id?: string;
  deuda_id?: string;
  /** Pago de deudas de Supabase al que corresponde esta transacción. */
  pago_id?: string;
}

export interface HourlyBucket {
  hora: number;
  total: number;
  count: number;
  promedio: number;
}

export interface HourlyAnalysis {
  cobertura: {
    total_gastos: number;
    total_tarjeta: number;
    con_hora: number;
    porcentaje: number;
  };
  por_hora: HourlyBucket[];
  heatmap: { dia: number; hora: number; total: number; count: number }[];
  franjas: { nombre: string; rango: string; total: number; count: number; promedio: number }[];
  destacados: {
    hora_mas_gasto: number;
    hora_mas_gasto_total: number;
    hora_mas_frecuente: number;
    hora_mas_frecuente_count: number;
    ticket_mayor: { descripcion: string; monto: number; hora: string; fecha: string };
  } | null;
}

export interface TransactionUpdate {
  nombre_limpio?: string;
  categoria?: string;
  tags?: string;
  prioridad?: string;
  es_fijo?: boolean;
  pertenece_a?: string;
  es_reembolsable?: boolean;
  deudor?: string;
  felicidad?: number;
  revisado?: boolean;
  nota?: string;
  fondo_id?: string;
  deuda_id?: string;
  pago_id?: string;
}

export interface TransactionFilters {
  startDate?: string;
  endDate?: string;
  pendingOnly?: boolean;
  search?: string;
  category?: string;
  tag?: string;
  sourceType?: 'BANCA' | 'TARJETA';
}

export interface BulkUpdateRequest {
  transactionIds: string[];
  updates: TransactionUpdate;
  overwrite?: boolean;
  tagsMode?: 'append' | 'replace';
  propagateGroups?: boolean;
  saveAsRule?: boolean;
  ruleEntities?: string[];
  ruleTags?: string[];
}

export interface BulkUpdateResponse {
  status: string;
  requested: number;
  affected: number;
  updated: number;
  applied_fields: Record<string, number>;
  skipped_fields: Record<string, number>;
  rules_saved: { type: string; key: string }[];
  undo_id: string;
}

export interface EntityRule {
  categoria?: string;
  prioridad?: string;
  es_fijo?: boolean;
  tags?: string;
  nota?: string;
}

export interface TagRule {
  categoria?: string;
  prioridad?: string;
  es_fijo?: boolean;
  nota?: string;
}

export interface RulesBook {
  description_map: Record<string, string>;
  entity_data: Record<string, EntityRule>;
  tag_data: Record<string, TagRule>;
  counts: { description_map: number; entity_data: number; tag_data: number };
}

export interface Stats {
  total_monto: number;
  count: number;
  pending: number;
  reviewed: number;
}

export interface SyncRequest {
  fecha_inicio: string;
  overwrite: boolean;
}

export interface DashboardDataPoint {
  date: string;
  total: number;
  saldo: number;
  saldo_sin_inversion: number;
  tarjeta: number;
  inversion: number;
  notion: number;
  diff_total: number;
  diff_tarjeta: number;
  diff_saldo_sin_inversion: number;
  diff_notion: number;
}

export interface DashboardResponse {
  data: DashboardDataPoint[];
  highlighted_days: string[];
  metadata?: {
    total_days?: number;
    /** Si el patrimonio de esta respuesta ya trae sumado el capital invertido. */
    incluir_inversiones?: boolean;
    /** Capital propio que está dentro de una posición hoy. Se informa siempre. */
    capital_invertido?: number;
    date_range?: { start: string; end: string };
  };
}

export interface SyncResponse {
  status: string;
  records_added: number;
  message: string | null;
}

export interface SupabaseDebt {
  FECHA: string;
  DESCRIPCION: string;
  MONTO: number;
  TIPO: string;
  DEUDOR_NOMBRE: string;
  DEUDOR_ID?: string;
  PAGADA: boolean;
  FECHA_PAGO: string | null;
  FECHA_CREACION: string;
  ID: string | number;
  /** true = tú debes; false = te deben. */
  ES_MI_DEUDA?: boolean;
  SALDO_PENDIENTE?: number;
}

/**
 * Una deuda mía, con el estado de su etiqueta.
 *
 * Devengar una deuda es decir "esto lo consumí yo": pasa a contar como gasto en
 * su `FECHA`, aunque la plata la haya puesto otro. Ver PLAN_DEUDAS_COMO_GASTO.md.
 */
export interface DeudaDevengada {
  ID: string;
  FECHA: string;
  DESCRIPCION: string;
  MONTO: number;
  DEUDOR_NOMBRE: string;
  PAGADA: boolean;
  /** true = ya se decidió que es gasto y tiene etiqueta. */
  devengada: boolean;
  /** Hay una transacción mía apuntando a esta deuda: su gasto ya está contado ahí. */
  tiene_transaccion?: boolean;
  categoria?: string | null;
  tags?: string | null;
  prioridad?: string | null;
  felicidad?: number | null;
  nombre_limpio?: string | null;
  nota?: string | null;
}

/** Qué mueve el modo devengo, para poder explicarlo antes de encenderlo. */
export interface ResumenDevengo {
  deudas_devengadas: number;
  monto_devengado: number;
  liquidaciones_ajustadas: number;
  monto_descontado: number;
  /** Liquidaciones que no se pudieron ajustar por falta de detalle en Supabase. */
  liquidaciones_sin_detalle: number;
}

export interface SupabasePayment {
  id: string | number;
  fecha_pago: string;
  monto_total: number;
  deudor_id: string;
  deudor_nombre: string;
  /** true = pagaste tú; false = te pagaron. */
  es_mi_pago?: boolean;
  /** Pago virtual de un cruce: no es dinero que se movió. */
  es_compensacion?: boolean;
  cruce_id?: string | null;
  nota?: string | null;
  /** Lo que no se asignó a ninguna deuda: saldo a favor de quien pagó. */
  sobrante?: number;
  deudas?: { deuda_id: string; titulo: string; monto_asignado: number }[];
}

export interface SupabaseDeudor {
  id: string;
  nombre: string;
  neto?: number;
  total_pendiente?: number;
  saldo_favor?: number;
}

export interface CreateDebtRequest {
  titulo: string;
  monto: number;
  deudor_id: string;
  fecha_gasto: string; // YYYY-MM-DD
  /** false = te deben (pagaste tú); true = tú debes (pagaron por ti). */
  es_mi_deuda?: boolean;
}

export interface CreatePaymentRequest {
  deudor_id: string;
  monto: number;
  /** false = te pagaron; true = pagaste tú. */
  es_mi_pago: boolean;
  fecha_pago: string; // YYYY-MM-DD
  /** Clave del borrador: reintentar el guardado no duplica el pago. */
  idem_key?: string;
  /** Vacío = reparto automático (cruce primero, luego las más antiguas). */
  deudas_ids?: string[];
}

export interface CreatePaymentResponse {
  pago_id: string;
  sobrante: number;
  repetido: boolean;
}

export interface PaymentPreview {
  asignado: number;
  sobrante: number;
  cruce_monto: number;
  deudas: {
    deuda_id: string;
    titulo: string;
    fecha_gasto: string;
    es_mi_deuda: boolean;
    saldo_real: number;
    pago_planeado: number;
  }[];
}

export interface EstadoCuentaDeuda {
  id: string;
  titulo: string;
  fecha_gasto: string | null;
  /** `created_at`: el orden en que se registró, no la fecha del gasto. */
  creado?: string;
  monto_original: number;
  monto_pagado: number;
  saldo_pendiente: number;
  /** Parte del saldo_pendiente cubierta con saldo a favor (pago entregado sin asignar). */
  abono_saldo_favor: number;
  /** saldo_pendiente − abono_saldo_favor: lo que falta de verdad. */
  saldo_real: number;
  estado: string; // PAGADA | PENDIENTE | PARCIAL
  es_tu_deuda: boolean;
  /** Cuánto de esta deuda se saldaría si se aplicara el cruce disponible. */
  cruce_sugerido: number;
  pagos: { pago_id: string; fecha_pago: string | null; monto_asignado: number }[];
}

export interface EstadoCuentaPago {
  id: string;
  fecha_pago: string | null;
  /** `created_at`: el orden en que se registró. */
  creado?: string;
  monto_total: number;
  asignado: number;
  sobrante: number;
  es_mi_pago: boolean;
  /** Pago virtual de un cruce de cuentas: no movió dinero real. */
  es_compensacion: boolean;
  /** Los dos pagos virtuales de un mismo cruce comparten este id. */
  cruce_id?: string | null;
  /** Texto libre del pago: de qué fue, cómo se entregó. */
  nota?: string | null;
  deudas: { deuda_id: string; titulo: string; monto_asignado: number }[];
}

/** Resultado de editar la fecha y/o la nota de un pago. */
export interface EdicionPago {
  pago_id: string;
  deudor_id: string;
  fecha: string;
  nota: string | null;
  /** El pago real más los dos del cruce que lo acompañaron, si la fecha cambió. */
  pagos_movidos: number;
  repetido: boolean;
}

/** Una deuda tocada por un pago o un cruce: con cuánto llegaba y con cuánto queda. */
export interface MovimientoItem {
  deuda_id: string;
  titulo: string;
  fecha_gasto: string | null;
  es_tu_deuda: boolean;
  /** Lo que valía la deuda al nacer. */
  monto_original: number;
  saldo_antes: number;
  /** Lo que este pago/cruce le aplicó. */
  aplicado: number;
  /** Total abonado a la deuda hasta aquí (incluye pagos anteriores). */
  pagado_acumulado: number;
  /** Lo que le falta después de este movimiento. */
  saldo_despues: number;
  cerrada: boolean;
  /** De ese faltante, cuánto lo cubre después el saldo a favor. */
  abono_saldo_favor: number;
}

export interface EstadoCuentaMovimiento {
  fecha: string | null;
  /** `created_at`: desempata el orden dentro del mismo día (la fecha es solo DATE). */
  orden?: string;
  /** `cruce` = los dos pagos virtuales de una compensación, ya fundidos en un evento. */
  tipo: 'deuda' | 'pago' | 'cruce';
  id: string;
  concepto: string;
  es_tu_deuda: boolean;
  delta: number;
  saldo_acumulado: number;
  sobrante?: number;
  /** Solo en pagos: la nota que se le puso. */
  nota?: string | null;
  es_mi_pago?: boolean;
  es_compensacion?: boolean;
  monto_total?: number;
  detalle: { deuda_id?: string; titulo: string; monto: number }[];
  /** Deudas que este movimiento tocó, saldadas y no saldadas. */
  items?: MovimientoItem[];
  parciales?: { deuda_id: string; titulo: string; monto_original: number; pagado_acumulado: number; saldo: number }[];
  /* Solo en tipo === 'cruce' */
  monto_cruzado?: number;
  pago_ids?: string[];
  lados?: {
    te_deben: { total: number; items: MovimientoItem[] };
    tu_debes: { total: number; items: MovimientoItem[] };
  };
  /** Pago físico del mismo día que disparó el cruce, si lo hubo. */
  pago_vinculado?: { id: string; concepto: string; monto_total: number; fecha: string | null } | null;
  /** Los dos pagos virtuales del cruce comparten este id. */
  cruce_id?: string | null;
  /** Es el cruce de la última operación: se le pueden sacar deudas. */
  editable?: boolean;
}

/** Una deuda del cruce en la vista previa (o el resultado) de editarlo. */
export interface EdicionCruceItem {
  deuda_id: string;
  titulo: string;
  fecha_gasto: string | null;
  es_tu_deuda: boolean;
  excluida: boolean;
  /** Lo que el cruce le aplicaba. */
  antes: number;
  /** Lo que le aplica tras la edición. */
  despues: number;
  /** Con cuánto queda la deuda de verdad. */
  saldo_real: number;
  /** De lo que se reabre, cuánto vuelve a cubrir el saldo a favor. */
  abono_saldo_favor: number;
}

export interface EdicionCruce {
  cruce_id: string;
  monto_antes: number;
  monto_despues: number;
  /** El cruce quedó en $0 y se borró. */
  eliminado: boolean;
  simulado: boolean;
  repetido: boolean;
  neto: number;
  /** Lo que queda por cruzar: se aplica en el siguiente pago. */
  cruce_disponible: number;
  items: EdicionCruceItem[];
}

/** Cruce que todavía se puede aplicar. Derivado: no está escrito en ningún lado. */
export interface CruceSugerido {
  monto: number;
  lados: {
    te_deben: { total: number; items: MovimientoItem[] };
    tu_debes: { total: number; items: MovimientoItem[] };
  };
}

export interface EstadoCuenta {
  deudas: EstadoCuentaDeuda[];
  pagos: EstadoCuentaPago[];
  movimientos: EstadoCuentaMovimiento[];
  cruce_sugerido: CruceSugerido;
  resumen: {
    /** min(Σ te deben, Σ tú debes) sobre el saldo real: lo que se puede cruzar hoy. */
    monto_ideal_a_cruzar: number;
    total_original: number;
    total_pagado: number;
    total_pendiente: number;
    total_te_deben: number;
    total_tu_debes: number;
    neto: number;
    /** Crédito del deudor que quedó sin abonar a ninguna deuda. */
    saldo_favor: number;
    /** Crédito tuyo que quedó sin abonar a ninguna deuda. */
    saldo_favor_owner: number;
    count: number;
    count_pagadas: number;
    count_pendientes: number;
  };
}

export interface InterpolationGroup {
  id: string;
  name: string;
  description: string;
  type: string;
}

export interface InterpolatedPayment {
  id: string;
  group_id: string;
  amount: number;
  start_date: string;
  end_date: string;
  note: string;
}

export interface BudgetConfig {
  tracked_tags: string[];
}


export interface BankProcessResponse {
  status: string;
  message: string;
  files_processed: string[];
  total_rows: number;
  validation_report?: string;
  chart_data?: {
    date: string;
    saldo: number;
    monto: number;
  }[];
  date_range?: {
    min: string | null;
    max: string | null;
  };
}

export interface SourceItemSummary {
  file_name: string;
  source_type: 'bank' | 'card';
  total_rows: number;
  min_date: string | null;
  max_date: string | null;
  chart_data: {
    date: string;
    count: number;
    monto: number;
  }[];
  error: string | null;
}

export interface SourcesSummaryResponse {
  bank_sources: SourceItemSummary[];
  card_sources: SourceItemSummary[];
}

// --- API Client ---

export const api = {
  // Transactions
  /**
   * `devengo` cambia la pregunta: en vez de "qué plata se movió" responde "qué
   * consumí". Entran las deudas mías etiquetadas y las liquidaciones pierden la
   * parte que ya se contó. Apagado, la respuesta es la de siempre.
   */
  getTransactions: async (date?: string, pendingOnly?: boolean, esReembolsable?: boolean, startDate?: string, endDate?: string, debtor?: string, search?: string, category?: string, tag?: string, devengo?: boolean): Promise<Transaction[]> => {
    const params = new URLSearchParams();
    if (date) params.append('date', date);
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (pendingOnly) params.append('pending_only', 'true');
    if (esReembolsable) params.append('es_reembolsable', 'true');
    if (debtor) params.append('deudor', debtor);
    if (search) params.append('search', search);
    if (category) params.append('category', category);
    if (tag) params.append('tag', tag);
    if (devengo) params.append('devengo', 'true');
    const res = await axios.get(`${API_BASE}/transactions?${params}`);
    return res.data;
  },

  /** Qué cambiaría el modo devengo, sin pedir las transacciones. */
  getResumenDevengo: async (): Promise<ResumenDevengo> => {
    const res = await axios.get(`${API_BASE}/transactions/devengo/resumen`);
    return res.data;
  },

  // Filter-object variant of getTransactions, used by the bulk labeling tab.
  queryTransactions: async (filters: TransactionFilters): Promise<Transaction[]> => {
    const params = new URLSearchParams();
    if (filters.startDate) params.append('start_date', filters.startDate);
    if (filters.endDate) params.append('end_date', filters.endDate);
    if (filters.pendingOnly) params.append('pending_only', 'true');
    if (filters.search) params.append('search', filters.search);
    if (filters.category) params.append('category', filters.category);
    if (filters.tag) params.append('tag', filters.tag);
    if (filters.sourceType) params.append('source_type', filters.sourceType);
    const res = await axios.get(`${API_BASE}/transactions?${params}`);
    return res.data;
  },

  bulkUpdateTransactions: async (req: BulkUpdateRequest): Promise<BulkUpdateResponse> => {
    const res = await axios.post(`${API_BASE}/transactions/bulk-update`, {
      transaction_ids: req.transactionIds,
      updates: req.updates,
      overwrite: req.overwrite ?? false,
      tags_mode: req.tagsMode ?? 'append',
      propagate_groups: req.propagateGroups ?? true,
      save_as_rule: req.saveAsRule ?? false,
      rule_entities: req.ruleEntities ?? [],
      rule_tags: req.ruleTags ?? [],
    });
    return res.data;
  },

  undoBulkUpdate: async (undoId: string): Promise<{ restored: number; rules_restored: number }> => {
    const res = await axios.post(`${API_BASE}/transactions/bulk-undo/${encodeURIComponent(undoId)}`);
    return res.data;
  },

  getAnalysisChartData: async (category?: string, tag?: string, startDate?: string, endDate?: string, groupId?: string): Promise<any> => {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    if (tag) params.append('tag', tag);
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (groupId) params.append('group_id', groupId);
    
    const res = await axios.get(`${API_BASE}/transactions/analysis-chart?${params}`);
    return res.data;
  },

  getHourlyAnalysis: async (
    startDate?: string,
    endDate?: string,
    category?: string,
    tag?: string,
  ): Promise<HourlyAnalysis> => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (category) params.append('category', category);
    if (tag) params.append('tag', tag);

    const res = await axios.get(`${API_BASE}/transactions/hourly-analysis?${params}`);
    return res.data;
  },

  getDates: async (): Promise<string[]> => {
    const res = await axios.get(`${API_BASE}/transactions/dates`);
    return res.data;
  },

  getStats: async (date?: string): Promise<Stats> => {
    const params = date ? `?date=${date}` : '';
    const res = await axios.get(`${API_BASE}/transactions/stats${params}`);
    return res.data;
  },

  getCategories: async (): Promise<string[]> => {
    const res = await axios.get(`${API_BASE}/transactions/categories`);
    return res.data;
  },

  getTags: async (): Promise<string[]> => {
    const res = await axios.get(`${API_BASE}/transactions/tags`);
    return res.data;
  },

  updateTransaction: async (id: string, updates: TransactionUpdate): Promise<void> => {
    await axios.put(`${API_BASE}/transactions/${encodeURIComponent(id)}`, updates);
  },

  markAsReviewed: async (id: string): Promise<void> => {
    await axios.post(`${API_BASE}/transactions/${encodeURIComponent(id)}/mark-reviewed`);
  },

  // Sync
  syncData: async (request: SyncRequest): Promise<SyncResponse> => {
    const res = await axios.post(`${API_BASE}/sync`, request);
    return res.data;
  },

  // Supabase Debts
  getSupabaseDebts: async (startDate?: string, endDate?: string, pendingOnly?: boolean, debtor?: string): Promise<SupabaseDebt[]> => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (pendingOnly) params.append('pending_only', 'true');
    if (debtor) params.append('deudor', debtor);
    const res = await axios.get(`${API_BASE}/supabase-debts/?${params}`);
    return res.data;
  },

  getSupabasePayments: async (debtor?: string, startDate?: string, endDate?: string, incluirCruces?: boolean): Promise<SupabasePayment[]> => {
    const params = new URLSearchParams();
    if (debtor) params.append('deudor', debtor);
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (incluirCruces) params.append('incluir_cruces', 'true');
    const res = await axios.get(`${API_BASE}/supabase-debts/payments?${params}`);
    return res.data;
  },

  createSupabasePayment: async (req: CreatePaymentRequest): Promise<CreatePaymentResponse> => {
    const res = await axios.post(`${API_BASE}/supabase-debts/payments`, req);
    return res.data;
  },

  previewSupabasePayment: async (req: Omit<CreatePaymentRequest, 'fecha_pago' | 'idem_key'>): Promise<PaymentPreview> => {
    const res = await axios.post(`${API_BASE}/supabase-debts/payments/preview`, req);
    return res.data;
  },

  getDeudores: async (): Promise<SupabaseDeudor[]> => {
    const res = await axios.get(`${API_BASE}/supabase-debts/deudores`);
    return res.data;
  },

  createDeudor: async (nombre: string): Promise<SupabaseDeudor> => {
    const res = await axios.post(`${API_BASE}/supabase-debts/deudores`, { nombre });
    return res.data;
  },

  createSupabaseDebt: async (req: CreateDebtRequest): Promise<{ id: string | number }> => {
    const res = await axios.post(`${API_BASE}/supabase-debts/`, req);
    return res.data;
  },

  // ── Devengo: una deuda mía también es un gasto ──────────────────────────
  // Escriben en etiquetas.csv, no en Supabase: la deuda y el cruce no se tocan.

  /** Deudas mías con el estado de su etiqueta; `soloPendientes` deja la bandeja. */
  getDeudasPorDevengar: async (soloPendientes?: boolean): Promise<DeudaDevengada[]> => {
    const params = new URLSearchParams();
    if (soloPendientes) params.append('solo_pendientes', 'true');
    const res = await axios.get(`${API_BASE}/supabase-debts/devengo/pendientes?${params}`);
    return res.data;
  },

  /** Etiqueta una deuda mía: con esto pasa a ser un gasto, fechado en el consumo. */
  etiquetarDeuda: async (deudaId: string, updates: TransactionUpdate): Promise<{ status: string }> => {
    const res = await axios.put(`${API_BASE}/supabase-debts/${deudaId}/etiqueta`, updates);
    return res.data;
  },

  /** Saca la deuda del gasto. La deuda sigue viva en Supabase; deja de ser consumo. */
  quitarDevengo: async (deudaId: string): Promise<{ status: string }> => {
    const res = await axios.delete(`${API_BASE}/supabase-debts/${deudaId}/etiqueta`);
    return res.data;
  },

  getEstadoCuenta: async (deudorId: string): Promise<EstadoCuenta> => {
    const res = await axios.get(`${API_BASE}/supabase-debts/estado-cuenta`, { params: { deudor_id: deudorId } });
    return res.data;
  },

  /** Cómo quedaría el cruce sin esas deudas. No escribe nada. */
  previewEditarCruce: async (cruceId: string, excluir: string[]): Promise<EdicionCruce> => {
    const res = await axios.post(`${API_BASE}/supabase-debts/cruces/${cruceId}/editar/preview`, { excluir });
    return res.data;
  },

  /** Saca deudas del cruce de la última operación; el pago real no se toca. */
  editarCruce: async (cruceId: string, excluir: string[], idemKey: string): Promise<EdicionCruce> => {
    const res = await axios.post(`${API_BASE}/supabase-debts/cruces/${cruceId}/editar`, { excluir, idem_key: idemKey });
    return res.data;
  },

  /** Cambia la fecha y/o la nota de un pago. `undefined` no toca el campo; nota '' la borra. */
  editarPago: async (
    pagoId: string,
    cambios: { fecha_pago?: string; nota?: string },
    idemKey: string,
  ): Promise<EdicionPago> => {
    const res = await axios.post(`${API_BASE}/supabase-debts/payments/${pagoId}/editar`, { ...cambios, idem_key: idemKey });
    return res.data;
  },


  getSyncStatus: async () => {
    const res = await axios.get(`${API_BASE}/sync/status`);
    return res.data;
  },

  // Dashboard
  // `filtros` son los query params ya serializados por `filtrosAQuery()`. Van
  // vacíos cuando no hay filtro puesto, así la petición queda igual a la de
  // siempre y reutiliza el caché del backend.
  getDashboardChartData: async (
    incluirInversiones = false,
    filtros: Record<string, string> = {},
  ): Promise<DashboardResponse> => {
    const res = await axios.get(`${API_BASE}/dashboard/chart-data`, {
      params: { incluir_inversiones: incluirInversiones, ...filtros },
    });
    return res.data;
  },

  // Rules
  getAllRules: async (): Promise<RulesBook> => {
    const res = await axios.get(`${API_BASE}/rules/`);
    return res.data;
  },

  deleteEntityRule: async (name: string): Promise<void> => {
    await axios.delete(`${API_BASE}/rules/entity/${encodeURIComponent(name)}`);
  },

  renameEntityRule: async (oldName: string, newName: string): Promise<void> => {
    await axios.post(`${API_BASE}/rules/entity/rename`, { old_name: oldName, new_name: newName });
  },

  deleteTagRule: async (tag: string): Promise<void> => {
    await axios.delete(`${API_BASE}/rules/tag/${encodeURIComponent(tag)}`);
  },

  deleteMapRule: async (original: string): Promise<void> => {
    await axios.delete(`${API_BASE}/rules/map?original=${encodeURIComponent(original)}`);
  },

  getEntityRule: async (name: string): Promise<any> => {
    const res = await axios.get(`${API_BASE}/rules/entity/${encodeURIComponent(name)}`);
    return res.data;
  },

  saveEntityRule: async (name: string, rule: any): Promise<void> => {
    await axios.post(`${API_BASE}/rules/entity?name=${encodeURIComponent(name)}`, rule);
  },

  saveMapRule: async (original: string, clean: string): Promise<void> => {
    await axios.post(`${API_BASE}/rules/map`, { original, clean });
  },

  getTagRule: async (tag: string): Promise<any> => {
    const res = await axios.get(`${API_BASE}/rules/tag/${encodeURIComponent(tag)}`);
    return res.data;
  },

  saveTagRule: async (tag: string, rule: any): Promise<void> => {
    await axios.post(`${API_BASE}/rules/tag?tag=${encodeURIComponent(tag)}`, rule);
  },

  // Sources
  processBankSource: async (): Promise<BankProcessResponse> => {

    const res = await axios.post(`${API_BASE}/sources/bank/process`);
    return res.data;
  },

  processCardSource: async (): Promise<BankProcessResponse> => {
    const res = await axios.post(`${API_BASE}/sources/card/process`);
    return res.data;
  },

  getSourcesSummary: async (): Promise<SourcesSummaryResponse> => {
    const res = await axios.get(`${API_BASE}/sources/summary`);
    return res.data;
  },


  // Variations
  // Tiene que ir con el mismo flag Y los mismos filtros que getDashboardChartData:
  // el desglose diario se contrasta contra el mismo total, y si no coinciden el
  // descuadre aparece como "diferencia sin explicar".
  getVariationsAnalysis: async (
    incluirInversiones = false,
    filtros: Record<string, string> = {},
  ): Promise<DailyVariation[]> => {
    const res = await axios.get(`${API_BASE}/dashboard/variations`, {
      params: { incluir_inversiones: incluirInversiones, ...filtros },
    });
    return res.data;
  },

  // Cards
  getCardsAnalysis: async (): Promise<any> => {
    const res = await axios.get(`${API_BASE}/variables/cards`);
    return res.data;
  },

  refreshCache: async () => {
      // Call both global invalidate (for other modules) and dashboard specific (for dashboard.py instance)
      await axios.post(`${API_BASE}/cache/invalidate`, null, { params: { scope: 'all' } });
      const res = await axios.post(`${API_BASE}/dashboard/invalidate`);
      return res.data;
  },

  // Grouping
  groupTransactions: async (ids: string[], masterData?: TransactionUpdate): Promise<void> => {
     await axios.post(`${API_BASE}/transactions/group`, { transaction_ids: ids, master_data: masterData });
  },
  
  ungroupTransaction: async (id: string): Promise<void> => {
     await axios.post(`${API_BASE}/transactions/ungroup/${encodeURIComponent(id)}`);
  },

  // Splitting
  splitTransaction: async (id: string, splits: SplitItem[]): Promise<void> => {
      await axios.post(`${API_BASE}/transactions/${encodeURIComponent(id)}/split`, { splits });
  },

  // Interpolated / Fixed Groups
  getGroups: async (type?: string): Promise<InterpolationGroup[]> => {
      const params = type ? `?type=${type}` : '';
      const res = await axios.get(`${API_BASE}/payments/groups${params}`);
      return res.data;
  },
  
  getGroupPayments: async (groupId: string): Promise<InterpolatedPayment[]> => {
      const res = await axios.get(`${API_BASE}/groups/${groupId}/payments`);
      return res.data;
  },

  // Budget
  getBudget: async (): Promise<BudgetConfig> => {
      const res = await axios.get(`${API_BASE}/budget`);
      return res.data;
  },

  saveBudget: async (config: BudgetConfig): Promise<void> => {
      await axios.post(`${API_BASE}/budget`, config);
  },

  // Funds (Fondos)
  getFunds: async (from?: string, to?: string): Promise<FundListItem[]> => {
    const params = new URLSearchParams();
    if (from) params.append('from', from);
    if (to) params.append('to', to);
    const queryString = params.toString() ? `?${params.toString()}` : '';
    const res = await axios.get(`${API_BASE}/funds/${queryString}`);
    return res.data;
  },

  getFund: async (id: string, from?: string, to?: string): Promise<FundDetail> => {
    const params = new URLSearchParams();
    if (from) params.append('from', from);
    if (to) params.append('to', to);
    const queryString = params.toString() ? `?${params.toString()}` : '';
    const res = await axios.get(`${API_BASE}/funds/${id}${queryString}`);
    return res.data;
  },

  createFund: async (fund: FundCreate): Promise<FundConfig> => {
    const res = await axios.post(`${API_BASE}/funds/`, fund);
    return res.data;
  },

  updateFund: async (id: string, updates: Partial<FundCreate> & { es_fondo?: boolean }): Promise<FundConfig> => {
    const res = await axios.put(`${API_BASE}/funds/${id}`, updates);
    return res.data;
  },

  deleteFund: async (id: string): Promise<void> => {
    await axios.delete(`${API_BASE}/funds/${id}`);
  },

  assignToFund: async (id: string, parts: FundPartRef[]): Promise<void> => {
    await axios.post(`${API_BASE}/funds/${id}/assign`, { parts });
  },

  unassignFromFund: async (id: string, parts: FundPartRef[]): Promise<void> => {
    await axios.post(`${API_BASE}/funds/${id}/unassign`, { parts });
  },

  generateFundPayments: async (
    id: string,
    payments: GeneratedPaymentInput[],
  ): Promise<{ status: string; group: FundConfig; count: number }> => {
    const res = await axios.post(`${API_BASE}/funds/${id}/generate-payments`, { payments });
    return res.data;
  },
};

// One flattened income→expense pair to materialize as a fixed payment.
export interface GeneratedPaymentInput {
  start: string;
  end: string;
  amount: number;
  note?: string;
  /** Ciclo del emparejamiento, para poder agrupar y regenerar por período. */
  ciclo_id?: string | null;
}

// Reference to the payments group generated from a fund.
export interface GeneratedPaymentsInfo {
  id: string;
  name: string;
  payment_count: number;
}

// A fund member: a whole transaction, or a single split part.
export interface FundPartRef {
  transaction_id: string;
  split_group_id?: string | null;
}

// --- Fund types ---

export interface FundProjection {
  status: 'surplus' | 'deficit';
  weeks_left: number;
  runs_out_on: string | null;
}

export interface FundSummary {
  total_in: number;
  total_out: number;
  balance: number;
  saldo_inicial: number;
  first_date: string | null;
  last_date: string | null;
  movement_count: number;
  burn_rate_weekly: number | null;
  projection: FundProjection | null;
}

export interface FundMovement {
  id: string;
  date: string;
  amount: number;
  note: string;
  source: 'transaction' | 'manual' | 'tag';
  reviewed: boolean;
  running_balance: number;
  /** Ciclo al que pertenece. `null` en fondos que no usan ciclos. */
  ciclo_id: string | null;
}

/**
 * Un período del fondo. Las fronteras vienen guardadas (`ciclos.csv`); los números
 * se recalculan siempre desde los movimientos, nunca se guardan.
 */
export interface FundCiclo {
  id: string;
  group_id: string;
  inicio: string;   // inclusivo
  fin: string;      // exclusivo
  nota: string;
  movimientos: number;
  credito: number;
  gasto: number;
  cubierto: number;
  sin_cubrir: number;
  sobrante: number;
  en_curso: boolean;
}

export type FundCicloModo = 'ingreso' | 'mensual' | 'ninguno';

export interface FundListItem {
  id: string;
  name: string;
  description: string;
  tag_vinculado: string | null;
  fecha_inicio: string | null;
  summary: FundSummary;
  sparkline: number[];
}

export interface FundDetail {
  id: string;
  name: string;
  description: string;
  es_fondo: boolean;
  tag_vinculado: string | null;
  fecha_inicio: string | null;
  fecha_inicio_auto: boolean;
  view_start: string | null;
  ciclo: FundCicloModo;
  dia_corte_default: number;
  ciclos: FundCiclo[];
  summary: FundSummary;
  movements: FundMovement[];
  generated_payments: GeneratedPaymentsInfo | null;
}

export interface FundConfig {
  id: string;
  name: string;
  description: string;
  type: string;
  es_fondo: boolean;
  fecha_inicio: string | null;
  saldo_inicial: number;
  tag_vinculado: string | null;
}

export interface FundCreate {
  name: string;
  description?: string;
  fecha_inicio?: string | null;
  saldo_inicial?: number;
  tag_vinculado?: string | null;
  ciclo?: FundCicloModo | null;
  dia_corte_default?: number | null;
}

export interface SplitItem {
    monto: number;
    categoria?: string;
    tags?: string;
    nota?: string;
    nombre_limpio?: string; // Optional override
    prioridad?: string;
    es_fijo?: boolean;
    pertenece_a?: string;
    es_reembolsable?: boolean;
    deudor?: string;
    felicidad?: number;
    revisado?: boolean;
    deuda_id?: string;
    pago_id?: string;
}

export enum ComponentType {
    BANCA='BANCA',
    TARJETA='TARJETA',
    DEUDA='DEUDA',
    INVERSION='INVERSION',
    PAGOS_FIJO='PAGOS_FIJO',
    INTERPOLADOS='INTERPOLADOS',
    OTROS='OTROS'
}

export interface TransactionDriver {
  description: string;
  amount: number;
  // type: string;
  // category: string;
  // account?: string;
  source: ComponentType;
  date: string;
}

export interface DailyVariation {
  date: string;
  total_change: number;
  
  // Components
  diff_saldo_neto: number;
  diff_tarjeta: number;
  diff_notion: number;
  diff_deuda_acumulada: number;
  diff_pagos_fijos: number;
  diff_interpolados: number;

  // Analysis
  top_drivers: TransactionDriver[];
  income_total: number;
  expense_total: number;
  unexplained_difference: number;
}
