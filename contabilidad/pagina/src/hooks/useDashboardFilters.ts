import { useCallback, useEffect, useMemo, useState } from 'react';

/**
 * Filtros del dashboard, compartidos por Evolución y Variaciones.
 *
 * No se aplican en el navegador: los dos gráficos reciben series ya agregadas por
 * día, así que el filtro viaja al backend, que lo aplica transacción por
 * transacción **antes** de agrupar (ver `dashboard_filters.py`).
 *
 * Los campos son los mismos del presupuesto a propósito. Si acá aparece uno
 * nuevo, tiene que aparecer también allá y en `TxFilter`, o las dos pantallas
 * empiezan a responder preguntas distintas con la misma cara.
 */
export interface DashboardFilters {
  categoriasExcluidas: string[];
  tagsExcluidos: string[];
  etiquetado: 'all' | 'labeled' | 'unlabeled';
  reembolsable: 'all' | 'included' | 'excluded';
  prioridad: 'all' | 'needs' | 'wants' | 'rated';
  /** null = todos los fondos. [] = solo lo que no pertenece a ningún fondo. */
  fondos: string[] | null;
}

export const FILTROS_VACIOS: DashboardFilters = {
  categoriasExcluidas: [],
  tagsExcluidos: [],
  etiquetado: 'all',
  reembolsable: 'all',
  prioridad: 'all',
  fondos: null,
};

const STORAGE_KEY = 'dashboard_filters';

export function hayFiltroActivo(f: DashboardFilters): boolean {
  return (
    f.categoriasExcluidas.length > 0 ||
    f.tagsExcluidos.length > 0 ||
    f.etiquetado !== 'all' ||
    f.reembolsable !== 'all' ||
    f.prioridad !== 'all' ||
    f.fondos !== null
  );
}

/** Cuántos filtros distintos están puestos. Para el contador de la barra. */
export function contarFiltros(f: DashboardFilters): number {
  return (
    (f.categoriasExcluidas.length > 0 ? 1 : 0) +
    (f.tagsExcluidos.length > 0 ? 1 : 0) +
    (f.etiquetado !== 'all' ? 1 : 0) +
    (f.reembolsable !== 'all' ? 1 : 0) +
    (f.prioridad !== 'all' ? 1 : 0) +
    (f.fondos !== null ? 1 : 0)
  );
}

/**
 * Los filtros como query params. Se omite todo lo que está en su valor neutro
 * para que la petición sin filtros sea idéntica a la de antes de esta feature
 * (y reutilice su caché en el backend).
 *
 * `fondos` es el caso especial: ausente significa "todos" y la cadena vacía
 * significa "ninguno", así que null no puede colapsarse con [].
 */
export function filtrosAQuery(f: DashboardFilters): Record<string, string> {
  const q: Record<string, string> = {};
  if (f.categoriasExcluidas.length) q.categorias_excluidas = f.categoriasExcluidas.join(',');
  if (f.tagsExcluidos.length) q.tags_excluidos = f.tagsExcluidos.join(',');
  if (f.etiquetado !== 'all') q.etiquetado = f.etiquetado;
  if (f.reembolsable !== 'all') q.reembolsable = f.reembolsable;
  if (f.prioridad !== 'all') q.prioridad = f.prioridad;
  if (f.fondos !== null) q.fondos = f.fondos.join(',');
  return q;
}

/**
 * Clave estable para react-query. Se construye desde `filtrosAQuery` y no desde
 * el objeto crudo para que dos estados que producen la misma petición compartan
 * caché en vez de pedir dos veces lo mismo.
 */
export function claveDeFiltros(f: DashboardFilters): string {
  const q = filtrosAQuery(f);
  return Object.keys(q).sort().map(k => `${k}=${q[k]}`).join('&');
}

export function useDashboardFilters() {
  const [filters, setFilters] = useState<DashboardFilters>(() => {
    try {
      const guardado = localStorage.getItem(STORAGE_KEY);
      // Con spread sobre los vacíos: un filtro guardado por una versión vieja
      // sin algún campo se completa en vez de llegar como undefined.
      return guardado ? { ...FILTROS_VACIOS, ...JSON.parse(guardado) } : FILTROS_VACIOS;
    } catch {
      return FILTROS_VACIOS;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
    } catch {
      /* localStorage lleno o bloqueado: el filtro sigue vivo en memoria */
    }
  }, [filters]);

  const limpiar = useCallback(() => setFilters(FILTROS_VACIOS), []);

  const activo = useMemo(() => hayFiltroActivo(filters), [filters]);
  const cantidad = useMemo(() => contarFiltros(filters), [filters]);
  const clave = useMemo(() => claveDeFiltros(filters), [filters]);

  return { filters, setFilters, limpiar, activo, cantidad, clave };
}
