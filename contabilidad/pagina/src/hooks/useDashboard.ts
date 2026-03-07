import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';

export function useDashboardChartData() {
  return useQuery({
    queryKey: ['dashboard-chart'],
    queryFn: api.getDashboardChartData,
    staleTime: 0,
    gcTime: 0,
  });
}

export function useVariations() {
  return useQuery({
    queryKey: ['dashboard-variations'],
    queryFn: api.getVariationsAnalysis,
  });
}
