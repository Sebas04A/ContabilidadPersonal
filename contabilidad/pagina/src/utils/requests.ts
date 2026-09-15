/** Clave de idempotencia para una escritura: reintentar con la misma no la repite. */
export const nuevaIdemKey = (): string =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = (Math.random() * 16) | 0;
        return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
      });

/** El mensaje de error del backend (`detail` de FastAPI) o, si no hay, el de la excepción. */
export const detalleError = (e: unknown): string =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  ?? (e instanceof Error ? e.message : 'Error desconocido');
