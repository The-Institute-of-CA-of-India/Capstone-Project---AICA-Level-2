/**
 * Invoice arithmetic. The legacy Apps Script computed totals on the server; Firestore has no server
 * code here, so this module is the single source of truth and is unit-tested (tests/calc.test.ts),
 * including a parity test against the original calcVisit_ function.
 *
 * Differences from the original: (1) tax can apply to some lines only ("taxable" flag - with every
 * line taxable the results are identical to the original), (2) tax is broken up into the country's
 * components (VAT | CGST+SGST | IGST).
 */
import { country } from '../config/countries';
import type { CountryCode, InvoiceLine, InvoiceStatus, Payment, Supply, TaxLine } from '../types';
import { newShortId } from './ids';

export const round2 = (n: unknown) => Math.round((Number(n) || 0) * 100 + 1e-9) / 100;

export interface CalcInput {
  lines: Partial<InvoiceLine>[];
  discount: unknown;
  taxEnabled: boolean;
  taxRate: number;
  taxInclusive: boolean;
  supply: Supply;
  country: CountryCode;
  payments: Partial<Payment>[];
  void?: boolean;
  defaultDate: string;
  defaultMethod?: string;
}
export interface CalcResult {
  lines: InvoiceLine[];
  subtotal: number;
  discount: number;
  taxableValue: number;
  tax: number;
  taxBreakup: TaxLine[];
  total: number;
  payments: Payment[];
  paid: number;
  balance: number;
  status: InvoiceStatus;
}

export function calcInvoice(v: CalcInput): CalcResult {
  const lines: InvoiceLine[] = (v.lines || []).map((l) => {
    const qty = Number(l.qty) || 0, rate = Number(l.rate) || 0;
    return {
      name: String(l.name || '').slice(0, 160), category: String(l.category || ''),
      qty, rate, amount: round2(qty * rate), taxable: l.taxable !== false, code: String(l.code || '').slice(0, 20)
    };
  }).filter((l) => l.name);

  const subtotal = round2(lines.reduce((a, l) => a + l.amount, 0));
  const discount = Math.min(Math.max(round2(v.discount), 0), subtotal);
  const net = round2(subtotal - discount);
  const rate = Number(v.taxRate) || 0;

  let tax = 0, total = net, taxableValue = net;
  let taxBreakup: TaxLine[] = [];
  if (v.taxEnabled && rate > 0) {
    // Discount is shared between taxable and non-taxable lines in proportion to their value.
    const taxableGross = round2(lines.filter((l) => l.taxable).reduce((a, l) => a + l.amount, 0));
    const share = subtotal > 0 ? taxableGross / subtotal : 0;
    const base = round2(taxableGross - round2(discount * share));
    if (v.taxInclusive) { tax = round2((base * rate) / (100 + rate)); taxableValue = round2(base - tax); total = net; }
    else { tax = round2((base * rate) / 100); taxableValue = base; total = round2(net + tax); }

    const comps = country(v.country).tax.components(rate, v.supply);
    let left = tax;
    taxBreakup = comps.map((c, i) => {
      const amt = i === comps.length - 1 ? round2(left) : round2((tax * c.rate) / rate);
      left = round2(left - amt);
      return { label: c.label, rate: c.rate, amount: amt };
    });
  }

  const payments: Payment[] = (v.payments || []).map((p) => ({
    id: String(p.id || newShortId()),
    date: String(p.date || v.defaultDate).slice(0, 10),
    method: String(p.method || v.defaultMethod || 'Cash').slice(0, 40),
    amount: round2(p.amount),
    ref: String(p.ref || '').slice(0, 60)
  })).filter((p) => p.amount > 0);
  const paid = round2(payments.reduce((a, p) => a + p.amount, 0));
  const balance = round2(total - paid);
  const status: InvoiceStatus = v.void ? 'Void'
    : total <= 0 ? 'No charge'
    : balance <= 0.005 ? 'Paid'
    : paid > 0 ? 'Part-paid' : 'Unpaid';

  return { lines, subtotal, discount, taxableValue, tax, taxBreakup, total, payments, paid, balance, status };
}
