/** Tags de un texto separado por comas, sin espacios, vacíos ni '---'. */
export function parseTags(tags: string | null | undefined): string[] {
  return (tags || '').split(',').map(tag => tag.trim()).filter(tag => tag !== '' && tag !== '---');
}
