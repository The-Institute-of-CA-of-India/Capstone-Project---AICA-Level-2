import { describe, it, expect } from 'vitest';
import { normalizePhone, waDigits } from '../src/lib/phone';
import { fmtMoney } from '../src/lib/money';
import { toCsv } from '../src/lib/csv';
import { fill, waInvoiceTemplateError } from '../src/lib/template';
import { todayIn, addDays, monthEnd, time12, fmtDate } from '../src/lib/dates';
import { validateTaxId } from '../src/lib/validators';
import { country, COUNTRY_LIST } from '../src/config/countries';
import { toPublicInvoice } from '../src/lib/publicView';
import { defaultSettings } from '../src/config/defaults';

describe('Kenya phone numbers', () => {
  const ok = (s: string, e: string) => { const r = normalizePhone(s, 'KE'); expect(r.ok && r.e164).toBe(e); };
  it('accepts the usual ways of typing a Kenyan mobile', () => {
    ok('0712345678', '+254712345678');
    ok('0712 345 678', '+254712345678');
    ok('+254712345678', '+254712345678');
    ok('254712345678', '+254712345678');
    ok('712345678', '+254712345678');
    ok('0112345678', '+254112345678');       // 01x numbers
    ok('+254 0712 345 678', '+254712345678');
    ok('00254712345678', '+254712345678');
  });
  it('rejects bad numbers with a helpful message', () => {
    for (const s of ['071234567', '07123456789', '0212345678', 'abc', '+254812345678']) {
      const r = normalizePhone(s, 'KE'); expect(r.ok).toBe(false);
      if (!r.ok) expect(r.error.length).toBeGreaterThan(10);
    }
  });
  it('shows a readable format and builds WhatsApp digits', () => {
    const r = normalizePhone('0712345678', 'KE');
    expect(r.ok && r.display).toBe('+254 712 345 678');
    expect(waDigits('+254712345678')).toBe('254712345678');
  });
});

describe('India phone numbers', () => {
  const ok = (s: string, e: string) => { const r = normalizePhone(s, 'IN'); expect(r.ok && r.e164).toBe(e); };
  it('accepts 10-digit mobiles starting 6-9', () => {
    ok('9876543210', '+919876543210');
    ok('09876543210', '+919876543210');
    ok('+91 98765 43210', '+919876543210');
    ok('919876543210', '+919876543210');
    ok('6000000000', '+916000000000');
  });
  it('rejects numbers starting 0-5, wrong length and junk', () => {
    for (const s of ['5876543210', '987654321', '98765432100', '1234567890', '++91']) expect(normalizePhone(s, 'IN').ok).toBe(false);
  });
  it('accepts a foreign number in E.164 form and treats empty as valid', () => {
    const r = normalizePhone('+447911123456', 'IN'); expect(r.ok && r.e164).toBe('+447911123456');
    const e = normalizePhone('', 'IN'); expect(e.ok && e.e164).toBe('');
  });
  it('display groups 5-5', () => { const r = normalizePhone('9876543210', 'IN'); expect(r.ok && r.display).toBe('+91 98765 43210'); });
});

describe('money, dates, csv, templates', () => {
  it('formats KES and INR (lakh grouping) correctly', () => {
    expect(fmtMoney(1234567.5, 'KES', 'en-KE')).toBe('KES\u00A01,234,567.50');
    expect(fmtMoney(1234567.5, 'INR', 'en-IN')).toBe('₹12,34,567.50');
    expect(fmtMoney(-5, 'USD', 'en-US')).toBe('-$5.00');
  });
  it('uses the clinic time zone for "today"', () => {
    const t = new Date('2026-11-04T22:30:00Z');       // already 5 Nov in Nairobi (+3) and in Kolkata (+5:30)
    expect(todayIn('Africa/Nairobi', t)).toBe('2026-11-05');
    expect(todayIn('Asia/Kolkata', t)).toBe('2026-11-05');
    expect(todayIn('UTC', t)).toBe('2026-11-04');
  });
  it('date helpers', () => {
    expect(addDays('2026-02-27', 3)).toBe('2026-03-02');
    expect(monthEnd('2028-02-10')).toBe('2028-02-29');
    expect(time12('00:05')).toBe('12:05 am'); expect(time12('13:30')).toBe('1:30 pm');
    expect(fmtDate('2026-11-04', 'en-KE')).toMatch(/4\s+Nov(ember)?\s+2026/);
  });
  it('csv quotes values and neutralises formula injection', () => {
    const out = toCsv([['a,b', 'say "hi"', '=HYPERLINK("x")', '-12.5', '+cmd']]);
    expect(out).toBe(`"a,b","say ""hi""","'=HYPERLINK(""x"")",-12.5,'+cmd`);
  });
  it('template filling and the WhatsApp privacy rule', () => {
    expect(fill('Hi {name}, {x}', { name: 'Asha' })).toBe('Hi Asha, {x}');
    expect(waInvoiceTemplateError('{clinic} — {link}')).toBe('');
    expect(waInvoiceTemplateError('Hi {name} {link}')).toMatch(/\{name\}/);
    expect(waInvoiceTemplateError('no link here {clinic}')).toMatch(/\{link\}/);
  });
});

describe('country packs', () => {
  it('Kenya = KES + VAT; India = INR + GST with CGST/SGST/IGST', () => {
    const k = country('KE'), i = country('IN');
    expect([k.currency, k.tax.label, k.dialCode]).toEqual(['KES', 'VAT', '254']);
    expect([i.currency, i.tax.label, i.dialCode]).toEqual(['INR', 'GST', '91']);
    expect(i.tax.components(18, 'intra').map((c) => c.label)).toEqual(['CGST', 'SGST']);
    expect(i.tax.components(18, 'inter').map((c) => c.label)).toEqual(['IGST']);
  });
  it('tax identifiers validate', () => {
    const pin = country('KE').taxIds[0], gstin = country('IN').taxIds[0], pan = country('IN').taxIds[1];
    expect(validateTaxId(pin, 'P051234567A')).toBe(''); expect(validateTaxId(pin, 'X123')).not.toBe('');
    expect(validateTaxId(gstin, '27ABCDE1234F1Z5')).toBe(''); expect(validateTaxId(gstin, '27ABCDE1234F1Z')).not.toBe('');
    expect(validateTaxId(pan, 'ABCDE1234F')).toBe(''); expect(validateTaxId(pan, '1234')).not.toBe('');
    expect(validateTaxId(pin, '')).toBe('');
  });
  it('both countries ship tax OFF by default and no clinic-specific text', () => {
    for (const c of COUNTRY_LIST) {
      const s = defaultSettings(c.code);
      expect(s.tax.enabled).toBe(false);
      expect(JSON.stringify(s).toLowerCase()).not.toMatch(/shiva|shyam|parklands|naturopath|@gmail|\+254 7/);
    }
  });
});

describe('public invoice snapshot', () => {
  it('contains no clinical data or patient contact details', () => {
    const s = defaultSettings('KE', 'Test Clinic');
    const v: any = {
      shareKey: 'k'.repeat(40), invoiceNo: 'INV-2026-0001', date: '2026-11-04', patientId: 'FN-0001', patientName: 'Asha',
      currency: 'KES', country: 'KE', taxEnabled: false, taxInclusive: false, supply: 'intra',
      lines: [{ name: 'Consult', category: 'c', qty: 1, rate: 100, amount: 100, taxable: false }],
      subtotal: 100, discount: 0, taxableValue: 100, tax: 0, taxBreakup: [], total: 100, paid: 0, balance: 100, status: 'Unpaid', payments: [],
      notes: 'SECRET NOTES', advice: 'SECRET ADVICE', bp: '120/80', weight: '70', mobile: '+254700000000'
    };
    const p = JSON.stringify(toPublicInvoice(v, s));
    for (const bad of ['SECRET', '120/80', '+254700000000', 'notes', 'advice']) expect(p).not.toContain(bad);
  });
});
