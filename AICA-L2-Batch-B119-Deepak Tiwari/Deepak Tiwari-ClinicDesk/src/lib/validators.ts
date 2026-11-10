import type { TaxIdDef } from '../config/countries';
export const isEmail = (e: unknown) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(e || '').trim());
export function validateTaxId(def: TaxIdDef, value: string): string {
  const v = String(value || '').trim().toUpperCase();
  if (!v) return '';
  if (def.pattern && !def.pattern.test(v)) return def.patternHint || `${def.label} looks wrong.`;
  return '';
}
export const isHexColor = (c: string) => /^#[0-9a-fA-F]{6}$/.test(c);
