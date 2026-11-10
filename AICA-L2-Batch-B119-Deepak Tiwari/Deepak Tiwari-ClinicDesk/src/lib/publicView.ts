import { country } from '../config/countries';
import type { ClinicSettings, PublicClinic, PublicInvoice, Visit } from '../types';

/** The part of the clinic profile that is safe to print on documents and to publish with an invoice link. */
export function toPublicClinic(s: ClinicSettings): PublicClinic {
  const c = country(s.country);
  return {
    name: s.clinicName, tagline: s.tagline, logoUrl: s.logoUrl, brandColor: s.brandColor,
    address: s.address, phone1: s.phone1, phone2: s.phone2, email: s.email, website: s.website,
    registrationNo: s.registrationNo, practitioner: s.practitioner, practitionerReg: s.practitionerReg,
    taxIdLines: c.taxIds.map((d) => ({ label: d.label.replace(/\s*\(optional\)/i, ''), value: s.taxIds?.[d.key] || '' })).filter((x) => x.value),
    footer: s.invoiceFooter, disclaimer: s.disclaimer,
    paymentLines: c.paymentLines(s.paymentDetails || {}),
    titles: s.titles, locale: c.locale
  };
}

/** Snapshot published at /publicInvoices/{shareKey}: only what belongs on an invoice. */
export function toPublicInvoice(v: Visit, s: ClinicSettings): PublicInvoice {
  return {
    key: v.shareKey,
    clinic: toPublicClinic(s),
    invoice: {
      invoiceNo: v.invoiceNo, date: v.date, patientName: v.patientName, fileNo: v.patientId,
      currency: v.currency, taxEnabled: v.taxEnabled, taxInclusive: v.taxInclusive, supply: v.supply,
      lines: v.lines.map((l) => ({ name: l.name, category: l.category, qty: l.qty, rate: l.rate, amount: l.amount, taxable: l.taxable, code: l.code || '' })),
      subtotal: v.subtotal, discount: v.discount, taxableValue: v.taxableValue, tax: v.tax, taxBreakup: v.taxBreakup,
      total: v.total, paid: v.paid, balance: v.balance, status: v.status,
      payments: v.payments.map((p) => ({ id: p.id, date: p.date, method: p.method, amount: p.amount, ref: p.ref }))
    },
    updatedAt: new Date().toISOString()
  };
}
