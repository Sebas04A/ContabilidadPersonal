import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';

// `incluirInversiones` va en la queryKey: las dos vistas del patrimonio son respuestas
// distintas del backend, no un filtro de cliente, así que cada una tiene su propio caché.

export function useDashboardChartData(incluirInversiones = false) {
  return useQuery({
    queryKey: ['dashboard-chart', incluirInversiones],
    queryFn: () => api.getDashboardChartData(incluirInversiones),
    staleTime: 0,
    gcTime: 0,
  });
}

export function useVariations(incluirInversiones = false) {
  return useQuery({
    queryKey: ['dashboard-variations', incluirInversiones],
    queryFn: () => api.getVariationsAnalysis(incluirInversiones),
  });
}
