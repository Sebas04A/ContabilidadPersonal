import { useState, useEffect, Dispatch, SetStateAction } from 'react';

/**
 * useState guardado en localStorage como JSON. `initial` se usa cuando no hay nada
 * guardado o no se puede leer; si es una función, se llama solo en ese caso.
 *
 * Para valores de texto también acepta lo guardado sin JSON (`all` en vez de `"all"`),
 * que es como se guardaban antes los filtros del presupuesto.
 */
export function usePersistentState<T>(key: string, initial: T | (() => T)): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    const fallback = initial instanceof Function ? initial() : initial;
    let saved: string | null = null;
    try {
      saved = localStorage.getItem(key);
    } catch {
      return fallback;
    }
    if (saved === null) return fallback;
    try {
      return JSON.parse(saved) as T;
    } catch {
      return typeof fallback === 'string' ? (saved as T) : fallback;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Sin almacenamiento el filtro sigue funcionando, solo no se recuerda.
    }
  }, [key, value]);

  return [value, setValue];
}
