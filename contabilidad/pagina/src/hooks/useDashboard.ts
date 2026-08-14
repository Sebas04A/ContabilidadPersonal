import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';
import {
  DashboardFilters,
  FILTROS_VACIOS,
  claveDeFiltros,
  filtrosAQuery,
} from './useDashboardFilters';

// `incluirInversiones` va en la queryKey: las dos vistas del patrimonio son respuestas
// distintas del backend, no un filtro de cliente, así que cada una tiene su propio caché.
//
// Los filtros van igual, por el mismo motivo: el backend los aplica transacción por
// transacción antes de agrupar por día, así que cada combinación es otra respuesta.
// La clave sale de `claveDeFiltros` y no del objeto crudo para que dos estados que
// producen la misma petición compartan caché.

export function useDashboardChartData(
  incluirInversiones = false,
  filters: DashboardFilters = FILTROS_VACIOS,
) {
  return useQuery({
    queryKey: ['dashboard-chart', incluirInversiones, claveDeFiltros(filters)],
    queryFn: () => api.getDashboardChartData(incluirInversiones, filtrosAQuery(filters)),
    staleTime: 0,
    gcTime: 0,
  });
}

export function useVariations(
  incluirInversiones = false,
  filters: DashboardFilters = FILTROS_VACIOS,
) {
  return useQuery({
    queryKey: ['dashboard-variations', incluirInversiones, claveDeFiltros(filters)],
    queryFn: () => api.getVariationsAnalysis(incluirInversiones, filtrosAQuery(filters)),
  });
}
