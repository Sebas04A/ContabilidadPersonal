import axios from 'axios';

const API_BASE = '/api/investments';

// --- Types ---
export interface AccountInvestment {
  fecha: string;
  descripcion: string;
  monto: number;
  tipo: 'iniciada' | 'finalizada';
  // For finalizadas
  plazo_fijo?: number;
  interes?: number;
  impuesto?: number;
  total?: number;
}

export interface InvestmentsFromAccountsResponse {
  iniciadas: AccountInvestment[];
  finalizadas: AccountInvestment[];
}

export interface Investment {
  id: string;
  amount: number;
  start_date: string;
  end_date?: string;
  note?: string;
  type: string;
  active: boolean;
}

// --- API Client ---
export const investmentsApi = {
  // Get investments extracted from account data
  getFromAccounts: async (): Promise<InvestmentsFromAccountsResponse> => {
    const res = await axios.get(`${API_BASE}/from-accounts`);
    return res.data;
  },

  // Manual investments CRUD
  getAll: async (): Promise<Investment[]> => {
    const res = await axios.get(`${API_BASE}/`);
    return res.data;
  },

  create: async (investment: Omit<Investment, 'id'>): Promise<Investment> => {
    const res = await axios.post(`${API_BASE}/`, investment);
    return res.data;
  },

  update: async (id: string, investment: Partial<Investment>): Promise<Investment> => {
    const res = await axios.put(`${API_BASE}/${id}`, investment);
    return res.data;
  },

  delete: async (id: string): Promise<void> => {
    await axios.delete(`${API_BASE}/${id}`);
  },

  // Chart data
  getChartData: async (): Promise<ChartData> => {
    const res = await axios.get(`${API_BASE}/chart-data`);
    return res.data;
  },
};

export interface ChartData {
  dates: string[];
  saldo: number[];
  inversion: number[];
  investment_periods: InvestmentPeriod[];
}

export interface InvestmentPeriod {
  index: number;
  amount: number;
  start_date: string;
  end_date: string;
  group_name: string;
  note: string;
}
