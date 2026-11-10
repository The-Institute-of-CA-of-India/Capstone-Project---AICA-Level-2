import { country } from '../config/countries';
import type { CountryCode } from '../types';

export type PhoneResult =
  | { ok: true; e164: string; display: string }
  | { ok: false; error: string };

const done = (digits: string, cc: CountryCode): PhoneResult => {
  const c = country(cc);
  if (digits.startsWith(c.dialCode)) {
    let rest = digits.slice(c.dialCode.length);
    const parts: string[] = [];
    for (const g of c.phone.group) { parts.push(rest.slice(0, g)); rest = rest.slice(g); }
    return { ok: true, e164: '+' + digits, display: `+${c.dialCode} ${parts.filter(Boolean).join(' ')}` };
  }
  return { ok: true, e164: '+' + digits, display: '+' + digits };
};

/**
 * Validates a mobile number against the selected country's rules and returns it in E.164 form
 * (+254712345678). Numbers from other countries are accepted if they look like valid E.164, so a
 * visiting patient can still be recorded. An empty string is valid (callers decide if it is required).
 */
export function normalizePhone(raw: string, cc: CountryCode): PhoneResult {
  const c = country(cc);
  let s = String(raw || '').trim();
  if (!s) return { ok: true, e164: '', display: '' };
  s = s.replace(/[\s().-]/g, '');
  if (!/^\+?\d+$/.test(s)) return { ok: false, error: 'Use digits only (spaces, dashes and a leading + are fine).' };
  if (s.startsWith('00')) s = '+' + s.slice(2);

  if (s.startsWith('+')) {
    const d = s.slice(1);
    if (d.startsWith(c.dialCode)) {
      let nat = d.slice(c.dialCode.length);
      if (nat.startsWith('0')) nat = nat.slice(1);          // "+254 0712..." typed by habit
      return c.phone.national.test(nat) ? done(c.dialCode + nat, cc) : { ok: false, error: c.phone.hint };
    }
    return /^[1-9]\d{6,14}$/.test(d) ? done(d, cc) : { ok: false, error: 'That international number does not look right.' };
  }
  if (c.phone.national.test(s)) return done(c.dialCode + s, cc);                     // 9876543210
  if (s.startsWith('0') && c.phone.national.test(s.slice(1))) return done(c.dialCode + s.slice(1), cc); // 0712345678
  if (s.startsWith(c.dialCode) && c.phone.national.test(s.slice(c.dialCode.length))) return done(s, cc); // 254712345678
  return { ok: false, error: c.phone.hint };
}

/** Digits only, as WhatsApp's wa.me links need ("254712345678"). */
export const waDigits = (e164: string) => String(e164 || '').replace(/\D/g, '');

/** Pretty-print any stored number for display. */
export function showPhone(e164: string, cc: CountryCode): string {
  if (!e164) return '';
  const r = normalizePhone(e164, cc);
  return r.ok ? r.display : e164;
}
