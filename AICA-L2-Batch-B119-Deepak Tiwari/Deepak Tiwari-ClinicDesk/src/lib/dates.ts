/** All "today" logic uses the clinic's time zone, not the device's. */
export function todayIn(tz: string, now: Date = new Date()): string {
  try {
    return new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
  } catch {
    return now.toISOString().slice(0, 10);
  }
}
const noon = (ymd: string) => new Date(ymd + 'T12:00:00Z');
export function addDays(ymd: string, n: number): string {
  const d = noon(ymd); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10);
}
export function monthStart(ymd: string) { return ymd.slice(0, 7) + '-01'; }
export function monthEnd(ymd: string) {
  const [y, m] = ymd.split('-').map(Number);
  return new Date(Date.UTC(y, m, 0)).toISOString().slice(0, 10);
}
export const isYmd = (s: unknown): s is string => typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s);
export function fmtDate(ymd: string, locale: string): string {
  if (!isYmd(ymd)) return ymd || '';
  try { return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(noon(ymd)); }
  catch { return ymd; }
}
export function longDate(ymd: string, locale: string): string {
  if (!isYmd(ymd)) return ymd || '';
  try { return new Intl.DateTimeFormat(locale, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(noon(ymd)); }
  catch { return ymd; }
}
export function monthLabel(ym: string, locale: string, long = false): string {
  try { return new Intl.DateTimeFormat(locale, { month: long ? 'long' : 'short', timeZone: 'UTC' }).format(noon(ym + '-01')); }
  catch { return ym; }
}
export function time12(hm: string): string {
  const p = String(hm || '').split(':'); const h = parseInt(p[0], 10);
  if (isNaN(h)) return hm || '';
  return `${(h % 12) || 12}:${p[1] || '00'} ${h < 12 ? 'am' : 'pm'}`;
}
/** ISO timestamp -> "4 Nov 2026" in the clinic's time zone. */
export function isoToDate(iso: string | undefined, tz: string, locale: string): string {
  if (!iso) return '';
  const d = new Date(iso); if (isNaN(+d)) return '';
  return fmtDate(todayIn(tz, d), locale);
}
