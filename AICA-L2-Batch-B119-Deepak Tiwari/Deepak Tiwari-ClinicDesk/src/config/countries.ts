/**
 * Country packs.  Everything that differs between Kenya and India lives here, so the rest of the
 * app never contains a hard-coded currency, tax label, phone rule or tax identifier.
 *
 * IMPORTANT: the tax rates, identifiers and wording below are *starting defaults only*. They are
 * editable in Settings and must be reviewed by a qualified accountant / lawyer before use.
 * To add a country, copy one pack and register it in COUNTRIES (and in the CountryCode type).
 */
import type { CountryCode, Supply } from '../types';

export interface TaxComponent { label: string; rate: number }
export interface TaxIdDef {
  key: string; label: string; placeholder: string;
  pattern?: RegExp; patternHint?: string; help?: string;
}
export interface PaymentField {
  key: string; label: string; placeholder?: string; options?: string[];
}

export interface CountryConfig {
  code: CountryCode;
  name: string;
  currency: string;
  locale: string;
  timezone: string;
  dialCode: string;                 // digits only, no "+"
  phone: {
    national: RegExp;               // national significant number (no trunk 0, no country code)
    example: string;
    group: number[];                // how to group the national number when displaying
    hint: string;
  };
  tax: {
    label: string;                  // "VAT" | "GST"
    defaultRate: number;
    presets: number[];
    supportsSupplySplit: boolean;   // India: CGST+SGST vs IGST
    components: (rate: number, supply: Supply) => TaxComponent[];
    codeLabel: string;              // "HSN / SAC code" for India, "" when not used
    help: string;
  };
  taxIds: TaxIdDef[];
  registration: { clinic: string; practitioner: string };
  patientIdLabel: string;
  paymentMethods: string[];
  paymentFields: PaymentField[];
  paymentLines: (d: Record<string, string>) => string[];
  titles: { invoice: string; taxInvoice: string; receipt: string; prescription: string };
  footer: string;
  disclaimer: string;
  consentText: string;
  regulatoryNotes: string[];
  sampleServices: { name: string; category: string; price: number; minutes: number; taxable: boolean; code: string }[];
}

const j = (parts: (string | undefined)[], sep = ' · ') => parts.filter(Boolean).join(sep);

const KENYA: CountryConfig = {
  code: 'KE',
  name: 'Kenya',
  currency: 'KES',
  locale: 'en-KE',
  timezone: 'Africa/Nairobi',
  dialCode: '254',
  phone: {
    national: /^[17]\d{8}$/,
    example: '0712 345 678',
    group: [3, 3, 3],
    hint: 'Kenyan mobile numbers have 10 digits and start with 07 or 01, e.g. 0712 345 678.'
  },
  tax: {
    label: 'VAT',
    defaultRate: 16,
    presets: [16, 8, 0],
    supportsSupplySplit: false,
    components: (rate) => [{ label: 'VAT', rate }],
    codeLabel: '',
    help: 'VAT starts switched OFF. Many medical services are VAT-exempt in Kenya, and charging VAT while not VAT-registered is an offence. Switch it on only after your accountant confirms it applies.'
  },
  taxIds: [
    {
      key: 'kraPin', label: 'KRA PIN', placeholder: 'P051234567A',
      pattern: /^[AP]\d{9}[A-Z]$/, patternHint: 'A KRA PIN is 11 characters: a letter, 9 digits, a letter (e.g. P051234567A).'
    }
  ],
  registration: {
    clinic: 'Facility / business licence no.',
    practitioner: 'KMPDC registration no.'
  },
  patientIdLabel: 'National ID / passport no. (optional)',
  paymentMethods: ['Cash', 'M-Pesa', 'Card', 'Bank Transfer', 'Insurance'],
  paymentFields: [
    { key: 'mpesaType', label: 'M-Pesa type', options: ['Paybill', 'Till'] },
    { key: 'mpesaNumber', label: 'Paybill / Till number', placeholder: '123456' },
    { key: 'mpesaAccount', label: 'Paybill account name (if any)' },
    { key: 'bankName', label: 'Bank' },
    { key: 'bankAccName', label: 'Account name' },
    { key: 'bankAccNo', label: 'Account number' },
    { key: 'bankBranch', label: 'Branch' },
    { key: 'bankSwift', label: 'SWIFT / BIC (optional)' }
  ],
  paymentLines: (d) => [
    d.mpesaNumber
      ? 'M-Pesa ' + j([`${d.mpesaType || 'Paybill'}: ${d.mpesaNumber}`, d.mpesaAccount ? `Account: ${d.mpesaAccount}` : ''])
      : '',
    d.bankName || d.bankAccNo
      ? 'Bank: ' + j([d.bankName, d.bankAccName ? `A/c name: ${d.bankAccName}` : '', d.bankAccNo ? `A/c no: ${d.bankAccNo}` : '', d.bankBranch ? `Branch: ${d.bankBranch}` : '', d.bankSwift ? `SWIFT: ${d.bankSwift}` : ''])
      : ''
  ].filter(Boolean),
  titles: { invoice: 'Invoice', taxInvoice: 'Tax Invoice', receipt: 'Payment Receipt', prescription: 'Prescription' },
  footer: 'Thank you for visiting us. Wishing you good health.',
  disclaimer: 'Your health information is confidential and is handled in line with the Data Protection Act, 2019.',
  consentText: 'The patient agrees that the clinic may keep this health information to provide treatment, issue invoices and send reminders, in line with the Kenya Data Protection Act, 2019.',
  regulatoryNotes: [
    'Patient records are sensitive personal data under the Data Protection Act, 2019. Clinics that process personal data are generally expected to register with the Office of the Data Protection Commissioner — please confirm with your adviser.',
    'Documents produced by this app are NOT KRA eTIMS tax invoices. If you are VAT-registered or need eTIMS-compliant invoices, use an approved eTIMS solution alongside this app.',
    'The KMPDC registration number shown on prescriptions is whatever you enter in Settings; the app does not verify it.'
  ],
  sampleServices: [
    { name: 'General consultation', category: 'Consultation', price: 1500, minutes: 20, taxable: false, code: '' },
    { name: 'Follow-up consultation', category: 'Consultation', price: 1000, minutes: 15, taxable: false, code: '' },
    { name: 'Injection / IV administration', category: 'Procedures', price: 500, minutes: 10, taxable: false, code: '' },
    { name: 'Wound dressing', category: 'Procedures', price: 800, minutes: 15, taxable: false, code: '' },
    { name: 'Medical certificate', category: 'Documents', price: 1000, minutes: 10, taxable: false, code: '' },
    { name: 'Medicine / product (dispensed)', category: 'Products', price: 0, minutes: 0, taxable: true, code: '' }
  ]
};

const INDIA: CountryConfig = {
  code: 'IN',
  name: 'India',
  currency: 'INR',
  locale: 'en-IN',
  timezone: 'Asia/Kolkata',
  dialCode: '91',
  phone: {
    national: /^[6-9]\d{9}$/,
    example: '98765 43210',
    group: [5, 5],
    hint: 'Indian mobile numbers have 10 digits and start with 6, 7, 8 or 9, e.g. 98765 43210.'
  },
  tax: {
    label: 'GST',
    defaultRate: 18,
    presets: [0, 5, 18],
    supportsSupplySplit: true,
    components: (rate, supply) =>
      supply === 'inter'
        ? [{ label: 'IGST', rate }]
        : [{ label: 'CGST', rate: rate / 2 }, { label: 'SGST', rate: rate / 2 }],
    codeLabel: 'HSN / SAC code',
    help: 'GST starts switched OFF. Healthcare services by clinical establishments are generally exempt, but some supplies (certain products or non-clinical services) can be taxable, and rates change. Mark each service "Taxable" or not so only the right lines carry GST, and confirm with a Chartered Accountant.'
  },
  taxIds: [
    {
      key: 'gstin', label: 'GSTIN', placeholder: '27ABCDE1234F1Z5',
      pattern: /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/, patternHint: 'A GSTIN is 15 characters, e.g. 27ABCDE1234F1Z5.',
      help: 'Only needed if the clinic is registered for GST.'
    },
    {
      key: 'pan', label: 'PAN (optional)', placeholder: 'ABCDE1234F',
      pattern: /^[A-Z]{5}\d{4}[A-Z]$/, patternHint: 'A PAN is 10 characters, e.g. ABCDE1234F.'
    }
  ],
  registration: {
    clinic: 'Clinical establishment registration no.',
    practitioner: 'Medical council registration no.'
  },
  patientIdLabel: 'ABHA / ID no. (optional)',
  paymentMethods: ['Cash', 'UPI', 'Card', 'Bank Transfer', 'Cheque', 'Insurance'],
  paymentFields: [
    { key: 'upiId', label: 'UPI ID', placeholder: 'clinic@bank' },
    { key: 'bankName', label: 'Bank' },
    { key: 'bankAccName', label: 'Account name' },
    { key: 'bankAccNo', label: 'Account number' },
    { key: 'bankIfsc', label: 'IFSC code', placeholder: 'ABCD0123456' },
    { key: 'bankBranch', label: 'Branch' }
  ],
  paymentLines: (d) => [
    d.upiId ? `UPI: ${d.upiId}` : '',
    d.bankName || d.bankAccNo
      ? 'Bank: ' + j([d.bankName, d.bankAccName ? `A/c name: ${d.bankAccName}` : '', d.bankAccNo ? `A/c no: ${d.bankAccNo}` : '', d.bankIfsc ? `IFSC: ${d.bankIfsc}` : '', d.bankBranch ? `Branch: ${d.bankBranch}` : ''])
      : ''
  ].filter(Boolean),
  titles: { invoice: 'Invoice', taxInvoice: 'Tax Invoice', receipt: 'Payment Receipt', prescription: 'Prescription' },
  footer: 'Thank you for visiting us. Wishing you good health.',
  disclaimer: 'Your health information is confidential and is handled in line with applicable Indian data-protection law.',
  consentText: 'The patient agrees that the clinic may keep and process this health information to provide treatment, issue bills and send reminders, as permitted by applicable Indian data-protection law.',
  regulatoryNotes: [
    'Digital personal data in India is governed by the Digital Personal Data Protection Act, 2023 and its rules. Collect valid consent, keep records secure and confirm your obligations with your adviser.',
    'Whether GST applies to a particular service or product, and at what rate, is a professional judgement. Rates and slabs change — verify the current position before switching GST on.',
    'Clinical-establishment and medical-council registration numbers are printed exactly as you enter them; the app does not verify them. Check your State’s rules for what a prescription or bill must show.'
  ],
  sampleServices: [
    { name: 'General consultation', category: 'Consultation', price: 500, minutes: 20, taxable: false, code: '' },
    { name: 'Follow-up consultation', category: 'Consultation', price: 300, minutes: 15, taxable: false, code: '' },
    { name: 'Injection / IV administration', category: 'Procedures', price: 200, minutes: 10, taxable: false, code: '' },
    { name: 'Wound dressing', category: 'Procedures', price: 300, minutes: 15, taxable: false, code: '' },
    { name: 'Medical certificate', category: 'Documents', price: 300, minutes: 10, taxable: false, code: '' },
    { name: 'Medicine / product (dispensed)', category: 'Products', price: 0, minutes: 0, taxable: true, code: '' }
  ]
};

export const COUNTRIES: Record<CountryCode, CountryConfig> = { KE: KENYA, IN: INDIA };
export const COUNTRY_LIST: CountryConfig[] = [KENYA, INDIA];
export const CURRENCIES = ['KES', 'INR', 'USD', 'EUR', 'GBP'];

export function country(code: CountryCode | undefined): CountryConfig {
  return COUNTRIES[code || 'KE'] || KENYA;
}
