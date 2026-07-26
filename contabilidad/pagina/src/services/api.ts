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
  // UI Only
  subTransactions?: Transaction[];
  nota: string;
  split_group_id: string;
  group_id?: string;
  fondo_id?: string;
  deuda_id?: string;
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
  PAGADA: boolean;
  FECHA_PAGO: string | null;
  FECHA_CREACION: string;
  ID: string | number;
}

export interface SupabasePayment {
  id: string | number;
  fecha_pago: string;
  monto_total: number;
  deudor_id: string;
  deudor_nombre: string;
}

export interface SupabaseDeudor {
  id: string;
  nombre: string;
}

export interface CreateDebtRequest {
  titulo: string;
  monto: number;
  deudor_id: string;
  fecha_gasto: string; // YYYY-MM-DD
}

export interface EstadoCuentaDeuda {
  id: string;
  titulo: string;
  fecha_gasto: string | null;
  monto_original: number;
  monto_pagado: number;
  saldo_pendiente: number;
  estado: string; // PAGADA | PENDIENTE | PARCIAL
  es_tu_deuda: boolean;
  pagos: { pago_id: string; fecha_pago: string | null; monto_asignado: number }[];
}

export interface EstadoCuentaPago {
  id: string;
  fecha_pago: string | null;
  monto_total: number;
  asignado: number;
  sobrante: number;
  deudas: { deuda_id: string; titulo: string; monto_asignado: number }[];
}

export interface EstadoCuentaMovimiento {
  fecha: string | null;
  tipo: 'deuda' | 'pago';
  id: string;
  concepto: string;
  es_tu_deuda: boolean;
  delta: number;
  saldo_acumulado: number;
  sobrante?: number;
  es_compensacion?: boolean;
  monto_total?: number;
  detalle: { titulo: string; monto: number }[];
  parciales?: { deuda_id: string; titulo: string; monto_original: number; pagado_acumulado: number; saldo: number }[];
}

export interface EstadoCuenta {
  deudas: EstadoCuentaDeuda[];
  pagos: EstadoCuentaPago[];
  movimientos: EstadoCuentaMovimiento[];
  resumen: {
    total_original: number;
    total_pagado: number;
    total_pendiente: number;
    total_te_deben: number;
    total_tu_debes: number;
    neto: number;
    saldo_favor: number;
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
  getTransactions: async (date?: string, pendingOnly?: boolean, esReembolsable?: boolean, startDate?: string, endDate?: string, debtor?: string, search?: string, category?: string, tag?: string): Promise<Transaction[]> => {
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
    const res = await axios.get(`${API_BASE}/transactions?${params}`);
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

  getSupabasePayments: async (debtor?: string): Promise<SupabasePayment[]> => {
    const params = new URLSearchParams();
    if (debtor) params.append('deudor', debtor);
    const res = await axios.get(`${API_BASE}/supabase-debts/payments?${params}`);
    return res.data;
  },

  getDeudores: async (): Promise<SupabaseDeudor[]> => {
    const res = await axios.get(`${API_BASE}/supabase-debts/deudores`);
    return res.data;
  },

  createSupabaseDebt: async (req: CreateDebtRequest): Promise<{ id: string | number }> => {
    const res = await axios.post(`${API_BASE}/supabase-debts/`, req);
    return res.data;
  },

  getEstadoCuenta: async (deudorId: string): Promise<EstadoCuenta> => {
    const res = await axios.get(`${API_BASE}/supabase-debts/estado-cuenta`, { params: { deudor_id: deudorId } });
    return res.data;
  },


  getSyncStatus: async () => {
    const res = await axios.get(`${API_BASE}/sync/status`);
    return res.data;
  },

  // Dashboard
  getDashboardChartData: async (): Promise<DashboardResponse> => {
    const res = await axios.get(`${API_BASE}/dashboard/chart-data`);
    console.log(res.data);
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
  getVariationsAnalysis: async (): Promise<DailyVariation[]> => {
    const res = await axios.get(`${API_BASE}/dashboard/variations`);
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
  getFunds: async (): Promise<FundListItem[]> => {
    const res = await axios.get(`${API_BASE}/funds/`);
    return res.data;
  },

  getFund: async (id: string, from?: string): Promise<FundDetail> => {
    const params = from ? `?from=${from}` : '';
    const res = await axios.get(`${API_BASE}/funds/${id}${params}`);
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
}

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
