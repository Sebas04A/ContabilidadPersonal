import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, TransactionUpdate, SplitItem } from '../services/api';

// Hook for fetching available dates
export function useDates() {
  return useQuery({
    queryKey: ['dates'],
    queryFn: api.getDates,
  });
}

// Hook for fetching transactions
export function useTransactions(date?: string, pendingOnly?: boolean) {
  return useQuery({
    queryKey: ['transactions', date, pendingOnly],
    queryFn: () => api.getTransactions(date, pendingOnly),
    enabled: !!date,
  });
}

// Hook for fetching ALL transactions (used by the Verification tab)
export function useAllTransactions() {
  return useQuery({
    queryKey: ['transactions', 'all'],
    queryFn: () => api.getTransactions(),
  });
}

// Hook for searching transactions
export function useSearchTransactions(query: string) {
  return useQuery({
    queryKey: ['transactions', 'search', query],
    queryFn: () => api.getTransactions(undefined, undefined, undefined, undefined, undefined, undefined, query),
    enabled: !!query && query.length > 2,
    staleTime: 500,
  });
}

// Hook for fetching refundable transactions
export function useRefundableTransactions(filters?: { startDate?: string; endDate?: string; debtor?: string }) {
  return useQuery({
    queryKey: ['transactions', 'refundable', filters],
    queryFn: () => api.getTransactions(undefined, undefined, true, filters?.startDate, filters?.endDate, filters?.debtor),
  });
}

// Hook for fetching Supabase debts
export function useSupabaseDebts(filters?: { startDate?: string; endDate?: string; pendingOnly?: boolean; debtor?: string }) {
  return useQuery({
    queryKey: ['supabase-debts', filters],
    queryFn: () => api.getSupabaseDebts(filters?.startDate, filters?.endDate, filters?.pendingOnly, filters?.debtor),
  });
}

// Hook for fetching Supabase payments
export function useSupabasePayments(debtor?: string) {
  return useQuery({
    queryKey: ['supabase-payments', debtor],
    queryFn: () => api.getSupabasePayments(debtor),
  });
}


// ── Funds (Fondos) ──────────────────────────────────────────────────────────

export function useFunds() {
  return useQuery({
    queryKey: ['funds'],
    queryFn: api.getFunds,
  });
}

export function useFund(id?: string, viewStart?: string) {
  return useQuery({
    queryKey: ['fund', id, viewStart],
    queryFn: () => api.getFund(id!, viewStart || undefined),
    enabled: !!id,
  });
}

export function useAssignToFund() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ fundId, parts, assign }: { fundId: string; parts: import('../services/api').FundPartRef[]; assign: boolean }) =>
      assign ? api.assignToFund(fundId, parts) : api.unassignFromFund(fundId, parts),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['funds'] });
      queryClient.invalidateQueries({ queryKey: ['fund'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
}

export function useCreateFund() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createFund,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['funds'] }),
  });
}

export function useGenerateFundPayments() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ fundId, payments }: { fundId: string; payments: import('../services/api').GeneratedPaymentInput[] }) =>
      api.generateFundPayments(fundId, payments),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ['funds'] });
      queryClient.invalidateQueries({ queryKey: ['fund', vars.fundId] });
      // The generated group feeds the dashboard fixed-payment offset.
      queryClient.invalidateQueries({ queryKey: ['dashboard-chart'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-variations'] });
    },
  });
}

export function useUpdateFund() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: Partial<import('../services/api').FundCreate> & { es_fondo?: boolean } }) =>
      api.updateFund(id, updates),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ['funds'] });
      queryClient.invalidateQueries({ queryKey: ['fund', vars.id] });
    },
  });
}

// Hook for fetching stats
export function useStats(date?: string) {
  return useQuery({
    queryKey: ['stats', date],
    queryFn: () => api.getStats(date),
    enabled: !!date,
  });
}

// Hook for fetching categories
export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: api.getCategories,
  });
}

// Hook for fetching tags
export function useTags() {
  return useQuery({
    queryKey: ['tags'],
    queryFn: api.getTags,
  });
}

// Hook for updating a transaction
export function useUpdateTransaction() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: TransactionUpdate }) =>
      api.updateTransaction(id, updates),
    onSuccess: () => {
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });
}

// Hook for marking as reviewed
export function useMarkAsReviewed() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => api.markAsReviewed(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });
}

// Hook for syncing data
export function useSyncData() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.syncData,
    onSuccess: () => {
      // Refresh everything after sync
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['dates'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      queryClient.invalidateQueries({ queryKey: ['tags'] });
    },
  });
}

// Hook for grouping transactions
export function useGroupTransactions() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ ids, masterData }: { ids: string[]; masterData?: TransactionUpdate }) =>
      api.groupTransactions(ids, masterData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });
}

// Hook for ungrouping transactions
export function useUngroupTransaction() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => api.ungroupTransaction(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });
}

// Hook for splitting transactions
export function useSplitTransaction() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, splits }: { id: string; splits: SplitItem[] }) =>
      api.splitTransaction(id, splits),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });
}
