import { describe, it, expect } from 'vitest';
import { renderToString as rts } from 'react-dom/server';
const renderToString = (el: Parameters<typeof rts>[0]) => rts(el).replace(/<!-- -->/g, '');
import { InvoiceDoc, ReceiptDoc, PrescriptionDoc } from '../src/components/Docs';
import { SetupRequired } from '../src/pages/Gates';
import { defaultSettings } from '../src/config/defaults';
import { country } from '../src/config/countries';
import { calcInvoice } from '../src/lib/calc';
import { toPublicInvoice } from '../src/lib/publicView';
import type { Visit } from '../src/types';

function visit(cc: 'KE' | 'IN', supply: 'intra' | 'inter' = 'intra'): { v: Visit; s: ReturnType<typeof defaultSettings> } {
  const s = defaultSettings(cc, 'Green Leaf Clinic');
  s.address = '12 Example Road'; s.phone1 = '+254 712 345 678'; s.taxIds = cc === 'KE' ? { kraPin: 'P051234567A' } : { gstin: '27ABCDE1234F1Z5' };
  s.paymentDetails = cc === 'KE' ? { mpesaType: 'Paybill', mpesaNumber: '123456' } : { upiId: 'clinic@bank' };
  const c = calcInvoice({
    lines: [{ name: 'Consultation', qty: 1, rate: 1000, taxable: false, code: '' }, { name: 'Product', qty: 2, rate: 500, taxable: true, code: '3004' }],
    discount: 0, taxEnabled: true, taxRate: cc === 'KE' ? 16 : 18, taxInclusive: false, supply, country: cc,
    payments: [{ id: 'p1', method: cc === 'KE' ? 'M-Pesa' : 'UPI', amount: 500, ref: 'ABC123', date: '2026-11-04' }], defaultDate: '2026-11-04'
  });
  const v = { id: 'v1', invoiceNo: 'INV-2026-0001', shareKey: 'a'.repeat(40), date: '2026-11-04', patientId: 'FN-0001', patientName: 'Asha Patel',
    currency: s.currency, country: cc, taxEnabled: true, taxRate: 16, taxInclusive: false, supply, ...c } as unknown as Visit;
  return { v, s };
}

describe('documents render for both countries', () => {
  it('Kenya invoice: KES, VAT, KRA PIN, M-Pesa, clinic name', () => {
    const { v, s } = visit('KE'); const p = toPublicInvoice(v, s);
    const html = renderToString(<InvoiceDoc clinic={p.clinic} inv={p.invoice} />);
    for (const t of ['Green Leaf Clinic', 'Tax Invoice', 'KES', 'VAT @ 16%', 'KRA PIN: P051234567A', 'M-Pesa Paybill: 123456', 'INV-2026-0001', 'Not subject to tax']) expect(html).toContain(t);
    expect(html).not.toMatch(/GST|GSTIN|₹/);
  });
  it('India invoice: INR, CGST+SGST, GSTIN, UPI', () => {
    const { v, s } = visit('IN'); const p = toPublicInvoice(v, s);
    const html = renderToString(<InvoiceDoc clinic={p.clinic} inv={p.invoice} />);
    for (const t of ['₹', 'CGST @ 9%', 'SGST @ 9%', 'GSTIN: 27ABCDE1234F1Z5', 'UPI: clinic@bank', 'HSN/SAC']) expect(html).toContain(t);
    expect(html).not.toMatch(/KRA|M-Pesa|VAT/);
  });
  it('India inter-state shows IGST only', () => {
    const { v, s } = visit('IN', 'inter'); const p = toPublicInvoice(v, s);
    const html = renderToString(<InvoiceDoc clinic={p.clinic} inv={p.invoice} />);
    expect(html).toContain('IGST @ 18%'); expect(html).not.toContain('CGST');
  });
  it('receipt and prescription render with the clinic name', () => {
    const { v, s } = visit('KE'); const p = toPublicInvoice(v, s);
    const r = renderToString(<ReceiptDoc clinic={p.clinic} inv={p.invoice} payment={p.invoice.payments[0]} />);
    expect(r).toContain('Payment Receipt'); expect(r).toContain('INV-2026-0001-R1'); expect(r).toContain('Green Leaf Clinic');
    const rx = renderToString(<PrescriptionDoc regLabel={country('KE').registration.practitioner} clinic={p.clinic}
      rx={{ id: 'v1', visitId: 'v1', patientId: 'FN-0001', patientName: 'Asha Patel', patientAge: '34', patientGender: 'Female', date: '2026-11-04',
        items: [{ medicine: 'Paracetamol 500mg', dose: '1 tab', frequency: 'TDS', duration: '3 days', instructions: 'after food' }], notes: 'Rest', prescriberName: 'Dr A', prescriberReg: '12345', createdAt: '', createdBy: '', updatedAt: '', updatedBy: '' }} />);
    expect(rx).toContain('Paracetamol 500mg'); expect(rx).toContain('KMPDC registration no.: 12345');
  });
  it('shows the setup screen (and no real keys) when Firebase is not configured', () => {
    const html = renderToString(<SetupRequired />);
    expect(html).toContain('VITE_FIREBASE_API_KEY'); expect(html).toContain('connect your Firebase project');
  });
});
