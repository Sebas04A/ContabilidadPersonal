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
  getEntityRule: async (name: string): Promise<any> => {
    const res = await axios.get(`${API_BASE}/transactions/rules/entity/${encodeURIComponent(name)}`);
    return res.data;
  },

  saveEntityRule: async (name: string, rule: any): Promise<void> => {
    await axios.post(`${API_BASE}/transactions/rules/entity?name=${encodeURIComponent(name)}`, rule);
  },

  saveMapRule: async (original: string, clean: string): Promise<void> => {
    await axios.post(`${API_BASE}/transactions/rules/map`, { original, clean });
  },

  getTagRule: async (tag: string): Promise<any> => {
    const res = await axios.get(`${API_BASE}/transactions/rules/tag/${encodeURIComponent(tag)}`);
    return res.data;
  },

  saveTagRule: async (tag: string, rule: any): Promise<void> => {
    await axios.post(`${API_BASE}/transactions/rules/tag?tag=${encodeURIComponent(tag)}`, rule);
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
      const res = await axios.get(`${API_BASE}/groups${params}`);
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
  }
};

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
