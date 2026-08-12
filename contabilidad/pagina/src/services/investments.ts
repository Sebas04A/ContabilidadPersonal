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

export type PositionType = 'plazo_fijo' | 'valuada' | 'ajuste' | 'flujo';

/** Salida: la plata se fue del portafolio y no vuelve. Entrada: llegó de fuera. */
export type FlowDirection = 'salida' | 'entrada';

export interface FlowIn {
  portafolio_id: string;
  fecha: string;
  /** Siempre positivo: el signo lo da `direccion`. */
  monto: number;
  direccion: FlowDirection;
  nota?: string;
  tx_id?: string | null;
}

export interface FlowPreview {
  fecha: string;
  residual_antes: number;
  residual_despues: number;
}
export type MovementType = 'aporte' | 'retiro' | 'interes' | 'retencion' | 'comision' | 'dividendo';

export interface Movement {
  id?: string;
  posicion_id?: string;
  fecha: string;
  tipo: MovementType;
  monto: number;
  tx_id?: string | null;
  nota?: string;
}

/** A saved position, with every derived amount already computed by the backend. */
export interface Position {
  id: string;
  portafolio_id: string | null;
  tipo: PositionType;
  fecha_apertura: string | null;
  fecha_cierre: string | null;
  estado: 'abierta' | 'cerrada';
  origen: 'detectado' | 'manual';
  plazo_pactado_dias: number | null;
  tasa_pactada: number | null;
  institucion: string | null;
  moneda: string;
  nota: string;
  tx_apertura_id: string | null;
  tx_cierre_id: string | null;
  // Derived
  capital: number;
  capital_vigente: number;
  retirado: number;
  interes: number;
  dividendos: number;
  retencion: number;
  comisiones: number;
  neto: number;
  dias: number | null;
  tna: number | null;
  tna_pactada: number | null;
  interes_devengado: number | null;
  dias_restantes: number | null;
  fecha_vencimiento: string | null;
  movimientos: Movement[];
}

export interface Portfolio {
  id: string;
  name: string;
  description: string;
  es_inversion: boolean;
  /** Somebody else's money living in the user's account: tracked, never own net worth. */
  es_custodia: boolean;
  posiciones: number;
}

export interface Kpis {
  capital_invertido: number;
  residual_suelto: number;
  capital_rotado: number;
  interes_cobrado: number;
  retencion: number;
  interes_neto: number;
  interes_devengado: number;
  tna_ponderada: number | null;
  capital_dia: number;
  xirr: number | null;
  posiciones: number;
  abiertas: number;
  cerradas: number;
  sin_apertura: number;
  proximo_vencimiento: string | null;
}

export interface PortfolioKpis extends Kpis {
  portafolio_id: string;
  nombre: string;
  es_custodia: boolean;
}

export interface YearRow {
  anio: number;
  posiciones: number;
  capital_medio: number;
  interes: number;
  tna_ponderada: number | null;
}

export interface InvestmentSummary {
  fecha: string;
  global: Kpis;
  propio: Kpis;
  custodia: Kpis;
  por_portafolio: PortfolioKpis[];
  sin_portafolio: number;
  por_anio: YearRow[];
}

export interface TimelineEvent {
  fecha: string;
  tipo: 'apertura' | 'cierre';
  capital: number;
  interes?: number;
  tna?: number | null;
  posicion_id: string;
  portafolio: string;
}

export interface InvestmentTimeline {
  fechas: string[];
  capital: number[];
  interes_acumulado: number[];
  eventos: TimelineEvent[];
  por_portafolio: { portafolio_id: string; nombre: string; capital: number[] }[];
}

export interface PortfolioSuggestion {
  candidatos: { portafolio_id: string; nombre: string; score: number; fronteras: string[]; aporte_estimado: number }[];
  sugerido: string | null;
  /** True when the certificate pooled money from more than one portfolio. */
  reparto: boolean;
  reparto_sugerido: { portafolio_id: string; nombre: string; capital: number }[];
}

export interface DetectedPosition {
  capital: number;
  fecha_apertura: string;
  fecha_cierre: string | null;
  tx_apertura_id: string;
  tx_cierre_id: string | null;
  interes: number;
  retencion: number;
  neto: number;
  total_devuelto: number;
  estado: string;
  dias: number | null;
  tna: number | null;
  ambiguo: boolean;
}

export interface OrphanClosing {
  fecha: string;
  capital_sugerido: number;
  interes_sugerido: number;
  retencion: number;
  tx_ids: string[];
}

export interface ReconcileDiff {
  nuevas: { detectada: DetectedPosition; sugerencia: PortfolioSuggestion | null }[];
  cambiadas: {
    posicion_id: string;
    posicion_ids: string[];
    portafolio_id: string | null;
    origen: string;
    detectada: DetectedPosition;
    cambios: Record<string, { guardado: unknown; detectado: unknown }>;
  }[];
  iguales: unknown[];
  huerfanas: OrphanClosing[];
  solo_guardadas: { posicion_id: string; fecha_apertura: string | null; capital: number }[];
  resumen: {
    detectadas: number; guardadas: number; nuevas: number; cambiadas: number;
    iguales: number; huerfanas: number; solo_guardadas: number;
  };
}

export interface GeneratedPayment {
  portafolio_id: string;
  portafolio: string;
  amount: number;
  start: string;
  end: string | null;
  /** Which event opened the segment ("abre 27.000", "cierra 28.304", "saldo inicial"). */
  motivo: string;
}

export interface CurrentPayment {
  id: string;
  portafolio_id: string;
  portafolio: string;
  amount: number;
  start: string | null;
  end: string | null;
  nota: string;
  /** False for rows without start_date: they sit in the CSV and the dashboard ignores them. */
  aplica: boolean;
}

export interface MismatchRun {
  desde: string;
  hasta: string;
  dias: number;
  monto: number;
}

export interface StepComparison {
  fechas: string[];
  actual: number[];
  generado: number[];
  diferencia: number[];
  dias: number;
  dias_descuadrados: number;
  /** Days off by more than hand-rounding explains — the ones that actually matter. */
  dias_materiales: number;
  max_desvio: number;
  primer_descuadre: string | null;
  cuadra: boolean;
  tramos: MismatchRun[];
}

export interface PortfolioComparison extends StepComparison {
  portafolio_id: string;
  nombre: string;
  es_custodia: boolean;
  saldo_inicial_sugerido: number;
  pagos_actuales: number;
  pagos_generados: number;
}

export interface NeutralizationPreview {
  fecha: string;
  global: StepComparison;
  por_portafolio: PortfolioComparison[];
  pagos_generados: GeneratedPayment[];
  pagos_actuales: CurrentPayment[];
  resumen: {
    pagos_generados: number;
    pagos_actuales: number;
    pagos_actuales_ignorados: number;
    siembra_total: number;
    dias: number;
    dias_descuadrados: number;
    dias_materiales: number;
    max_desvio: number;
    primer_descuadre: string | null;
    cuadra: boolean;
    portafolios_que_cuadran: number;
    portafolios: number;
  };
}

export interface ApplyDetectionRequest {
  tx_apertura_ids?: string[] | null;
  asignaciones?: Record<string, string>;
  portafolio_id?: string | null;
  incluir_cambiadas?: boolean;
  usar_sugerencias?: boolean;
}

export interface SplitPart {
  portafolio_id: string | null;
  capital: number;
  interes?: number | null;
  retencion?: number | null;
  nota?: string | null;
}

// --- API Client ---
export const investmentsApi = {
  // Get investments extracted from account data
  getFromAccounts: async (): Promise<InvestmentsFromAccountsResponse> => {
    const res = await axios.get(`${API_BASE}/from-accounts`);
    return res.data;
  },

  // Chart data (legacy audit view: balance vs. investment)
  getChartData: async (): Promise<ChartData> => {
    const res = await axios.get(`${API_BASE}/chart-data`);
    return res.data;
  },

  // --- Saved positions ---
  getPositions: async (params?: { portafolio_id?: string; estado?: string; tipo?: string }): Promise<Position[]> => {
    const res = await axios.get(`${API_BASE}/positions`, { params });
    return res.data;
  },

  getPortfolios: async (): Promise<Portfolio[]> => {
    const res = await axios.get(`${API_BASE}/portfolios`);
    return res.data;
  },

  getSummary: async (): Promise<InvestmentSummary> => {
    const res = await axios.get(`${API_BASE}/summary`);
    return res.data;
  },

  getTimeline: async (): Promise<InvestmentTimeline> => {
    const res = await axios.get(`${API_BASE}/timeline`);
    return res.data;
  },

  /** Read-only: the fixed payments the positions would produce, vs. the ones written by hand. */
  getNeutralizationPreview: async (): Promise<NeutralizationPreview> => {
    const res = await axios.get(`${API_BASE}/neutralization/preview`);
    return res.data;
  },

  /** Registra dinero que entró o salió del portafolio sin pasar por una inversión. */
  registrarFlujo: async (flujo: FlowIn): Promise<Position> => {
    const res = await axios.post(`${API_BASE}/flows`, flujo);
    return res.data;
  },

  /** El residual del portafolio antes y después del flujo. No escribe nada. */
  previewFlujo: async (params: {
    portafolio_id: string; fecha: string; monto: number; direccion: FlowDirection;
  }): Promise<FlowPreview> => {
    const res = await axios.get(`${API_BASE}/flows/preview`, { params });
    return res.data;
  },

  createPosition: async (position: Partial<Position> & { movimientos?: Movement[] }): Promise<Position> => {
    const res = await axios.post(`${API_BASE}/positions`, position);
    return res.data;
  },

  updatePosition: async (id: string, updates: Partial<Position> & { movimientos?: Movement[] }): Promise<Position> => {
    const res = await axios.put(`${API_BASE}/positions/${id}`, updates);
    return res.data;
  },

  deletePosition: async (id: string): Promise<void> => {
    await axios.delete(`${API_BASE}/positions/${id}`);
  },

  splitPosition: async (id: string, partes: SplitPart[]): Promise<{ partes: Position[] }> => {
    const res = await axios.post(`${API_BASE}/positions/${id}/split`, { partes });
    return res.data;
  },

  // --- Reconciliation ---
  detect: async (): Promise<ReconcileDiff> => {
    const res = await axios.post(`${API_BASE}/detect`);
    return res.data;
  },

  applyDetection: async (req: ApplyDetectionRequest = {}): Promise<{
    resumen: { creadas: number; actualizadas: number; omitidas: number };
    omitidas: { posicion_id: string; motivo: string }[];
  }> => {
    const res = await axios.post(`${API_BASE}/detect/apply`, req);
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
