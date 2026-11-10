import { describe, it, expect } from 'vitest';
import { calcInvoice, round2 } from '../src/lib/calc';
// @ts-ignore - plain JS fixture
import { calcVisit_ } from './legacy-calc.js';

// small seeded PRNG so failures are reproducible
function rng(seed: number) { return () => (seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296; }

const base = { supply: 'intra' as const, country: 'KE' as const, payments: [], defaultDate: '2026-11-04' };

describe('parity with the original Apps Script arithmetic', () => {
  it('gives identical subtotal / tax / total / balance / status on 500 random invoices', () => {
    const r = rng(42);
    for (let i = 0; i < 500; i++) {
      const lines = Array.from({ length: 1 + Math.floor(r() * 5) }, (_, k) => ({
        name: 'S' + k, qty: 1 + Math.floor(r() * 3), rate: Math.round(r() * 900000) / 100
      }));
      const discount = r() < 0.4 ? Math.round(r() * 200000) / 100 : 0;
      const vatOn = r() < 0.6, vatRate = [0, 8, 16][Math.floor(r() * 3)], inclusive = r() < 0.5;
      const payments = r() < 0.6 ? [{ method: 'Cash', amount: Math.round(r() * 1500000) / 100 }] : [];
      const old = calcVisit_({ lines: lines.map((l) => ({ ...l })), discount, vatOn, vatRate, vatInclusive: inclusive, payments, date: '2026-11-04' });
      const nu = calcInvoice({
        ...base, lines: lines.map((l) => ({ ...l })), discount, taxEnabled: vatOn, taxRate: vatRate,
        taxInclusive: inclusive, payments
      });
      expect(nu.subtotal).toBe(old.subtotal);
      expect(nu.discount).toBe(old.discount);
      expect(nu.tax).toBe(old.vat);
      expect(nu.taxableValue).toBe(old.taxable);
      expect(nu.total).toBe(old.total);
      expect(nu.paid).toBe(old.paid);
      expect(nu.balance).toBe(old.balance);
      expect(nu.status).toBe(old.status);
    }
  });
});

describe('tax behaviour', () => {
  const line = (name: string, rate: number, taxable?: boolean) => ({ name, qty: 1, rate, taxable });

  it('applies tax only to taxable lines and shares the discount proportionally', () => {
    // 1000 non-taxable consultation + 1000 taxable product, 200 discount -> 100 off each side
    const r = calcInvoice({ ...base, lines: [line('Consult', 1000, false), line('Product', 1000, true)], discount: 200, taxEnabled: true, taxRate: 16, taxInclusive: false });
    expect(r.subtotal).toBe(2000);
    expect(r.taxableValue).toBe(900);
    expect(r.tax).toBe(144);
    expect(r.total).toBe(1944);
  });

  it('inclusive tax does not change the total', () => {
    const r = calcInvoice({ ...base, lines: [line('A', 1160, true)], discount: 0, taxEnabled: true, taxRate: 16, taxInclusive: true });
    expect(r.total).toBe(1160);
    expect(r.tax).toBe(160);
    expect(r.taxableValue).toBe(1000);
  });

  it('Kenya shows a single VAT line', () => {
    const r = calcInvoice({ ...base, lines: [line('A', 1000)], discount: 0, taxEnabled: true, taxRate: 16, taxInclusive: false });
    expect(r.taxBreakup).toEqual([{ label: 'VAT', rate: 16, amount: 160 }]);
  });

  it('India intra-state splits GST into CGST + SGST that add up exactly', () => {
    const r = calcInvoice({ ...base, country: 'IN', supply: 'intra', lines: [line('A', 333.33)], discount: 0, taxEnabled: true, taxRate: 18, taxInclusive: false });
    expect(r.taxBreakup.map((t) => t.label)).toEqual(['CGST', 'SGST']);
    expect(r.taxBreakup.map((t) => t.rate)).toEqual([9, 9]);
    expect(round2(r.taxBreakup[0].amount + r.taxBreakup[1].amount)).toBe(r.tax);
  });

  it('India inter-state uses a single IGST line', () => {
    const r = calcInvoice({ ...base, country: 'IN', supply: 'inter', lines: [line('A', 1000)], discount: 0, taxEnabled: true, taxRate: 18, taxInclusive: false });
    expect(r.taxBreakup).toEqual([{ label: 'IGST', rate: 18, amount: 180 }]);
    expect(r.total).toBe(1180);
  });

  it('no tax when disabled, rate 0, or no taxable lines', () => {
    expect(calcInvoice({ ...base, lines: [line('A', 500)], discount: 0, taxEnabled: false, taxRate: 16, taxInclusive: false }).tax).toBe(0);
    expect(calcInvoice({ ...base, lines: [line('A', 500)], discount: 0, taxEnabled: true, taxRate: 0, taxInclusive: false }).tax).toBe(0);
    const r = calcInvoice({ ...base, lines: [line('A', 500, false)], discount: 0, taxEnabled: true, taxRate: 16, taxInclusive: false });
    expect(r.tax).toBe(0); expect(r.total).toBe(500);
  });
});

describe('payments and status', () => {
  const mk = (amount: number, pay: number, v = false) => calcInvoice({
    ...base, lines: [{ name: 'A', qty: 1, rate: amount }], discount: 0, taxEnabled: false, taxRate: 0, taxInclusive: false,
    payments: pay ? [{ method: 'UPI', amount: pay }] : [], void: v
  });
  it('Unpaid / Part-paid / Paid / No charge / Void', () => {
    expect(mk(100, 0).status).toBe('Unpaid');
    expect(mk(100, 40).status).toBe('Part-paid');
    expect(mk(100, 100).status).toBe('Paid');
    expect(mk(0, 0).status).toBe('No charge');
    expect(mk(100, 100, true).status).toBe('Void');
  });
  it('keeps the payment method it is given (methods are configurable per country)', () => {
    expect(mk(100, 100).payments[0].method).toBe('UPI');
  });
  it('drops blank lines and zero payments, caps discount at the subtotal', () => {
    const r = calcInvoice({ ...base, lines: [{ name: '', qty: 1, rate: 50 }, { name: 'X', qty: 2, rate: 10 }], discount: 999, taxEnabled: false, taxRate: 0, taxInclusive: false, payments: [{ amount: 0 }] });
    expect(r.lines).toHaveLength(1); expect(r.discount).toBe(20); expect(r.total).toBe(0); expect(r.payments).toHaveLength(0);
  });
});
