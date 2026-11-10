const SYMBOL: Record<string, string> = { INR: '₹', USD: '$', EUR: '€', GBP: '£' };

/** Formats an amount for display, e.g. "KES 12,500.00" (en-KE) or "₹1,25,000.00" (en-IN). */
export function fmtMoney(n: number, currency: string, locale: string): string {
  const v = Math.round((Number(n) || 0) * 100 + 1e-9) / 100;
  const neg = v < 0;
  let body: string;
  try {
    body = new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Math.abs(v));
  } catch {
    body = Math.abs(v).toFixed(2);
  }
  const sym = SYMBOL[currency];
  return (neg ? '-' : '') + (sym ? sym + body : `${currency}\u00A0${body}`);
}

/** Plain number with 2 decimals and no currency (for inputs / CSV). */
export const num2 = (n: number) => (Math.round((Number(n) || 0) * 100 + 1e-9) / 100).toFixed(2);
