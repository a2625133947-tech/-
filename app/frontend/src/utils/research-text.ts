/** Reading copy only. Keep the stored claim and citation quote verbatim. */
export function formatResearchText(text: string): string {
  return text
    // PDF bullet fonts can be extracted as private-use glyphs.
    .replace(/^\s*[\uF06C•●]\s*/u, '')
    .replace(/\s+/gu, ' ')
    .trim()
    // Join Chinese text split by PDF column spacing or physical line breaks.
    // Keep separators between Latin words and between separate numeric values.
    .replace(/([\p{Script=Han}，。；：！？、“‘（《【]) +/gu, '$1')
    .replace(/ +([\p{Script=Han}，。；：！？、”’）》】])/gu, '$1');
}
