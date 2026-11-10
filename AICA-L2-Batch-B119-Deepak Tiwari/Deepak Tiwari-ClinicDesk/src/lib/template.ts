/** Replaces {placeholders}. Unknown placeholders are left as they are. */
export function fill(tpl: string, map: Record<string, string>): string {
  return String(tpl || '').replace(/\{(\w+)\}/g, (m, k) => (Object.prototype.hasOwnProperty.call(map, k) ? String(map[k]) : m));
}
/** The WhatsApp invoice message may carry only the clinic name and the link. */
export function waInvoiceTemplateError(tpl: string): string {
  const bad = (tpl.match(/\{(\w+)\}/g) || []).map((x) => x.slice(1, -1)).filter((k) => k !== 'clinic' && k !== 'link');
  return bad.length
    ? `For privacy the WhatsApp invoice message may only use {clinic} and {link} (remove {${[...new Set(bad)].join('}, {')}}).`
    : (tpl.includes('{link}') ? '' : 'The WhatsApp invoice message must include {link}.');
}
