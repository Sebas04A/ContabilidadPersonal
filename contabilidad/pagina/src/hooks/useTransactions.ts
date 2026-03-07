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
