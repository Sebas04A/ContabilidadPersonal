/** Texto para comparar: sin acentos, sin espacios a los lados y en minúsculas. */
export function normalizeText(s: string | null | undefined): string {
  if (!s) return '';
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').trim().toLowerCase();
}
