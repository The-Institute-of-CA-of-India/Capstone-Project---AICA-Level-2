import type { ClinicSettings, CountryCode, MessageTemplates } from '../types';
import { country } from './countries';

export const DEFAULT_TEMPLATES: MessageTemplates = {
  // Privacy rule carried over from the original system: a WhatsApp invoice message carries only the
  // clinic name and the link - never the patient's name, amount or any clinical detail.
  waInvoice: '{clinic} — your invoice: {link}',
  waRemind: 'Hello {name}, this is a reminder of your appointment at {clinic} on {date} at {time}. To reschedule please call {phone}. Thank you.',
  smsRemind: 'Reminder: appointment at {clinic} on {date} at {time}. Call {phone} to reschedule.',
  emailInvoiceSubject: 'Your invoice {number} from {clinic}',
  emailInvoiceBody: 'Dear {name},\n\nThank you for visiting {clinic}. Your invoice {number} for {total} is available online here:\n{link}\n\nWith best wishes for your health,\n{practitioner}\n{clinic}\n{phone}',
  emailRemindSubject: 'Appointment reminder — {date} at {time}',
  emailRemindBody: 'Dear {name},\n\nThis is a friendly reminder of your appointment at {clinic} on {date} at {time}.\n\nAddress: {address}\nIf you need to reschedule, please call {phone} or reply to this email.\n\nWarm regards,\n{clinic}'
};

export type CountryDefaults = Pick<ClinicSettings,
  'country' | 'currency' | 'tax' | 'paymentMethods' | 'titles' | 'invoiceFooter' | 'disclaimer' | 'consentText'>;

/** Country-specific values. Used by first-run setup and by "Apply country defaults" in Settings. */
export function countryDefaults(code: CountryCode): CountryDefaults {
  const c = country(code);
  return {
    country: code,
    currency: c.currency,
    tax: { enabled: false, rate: c.tax.defaultRate, inclusive: false, defaultSupply: 'intra' },
    paymentMethods: [...c.paymentMethods],
    titles: { ...c.titles },
    invoiceFooter: c.footer,
    disclaimer: c.disclaimer,
    consentText: c.consentText
  };
}

export function defaultSettings(code: CountryCode = 'KE', clinicName = ''): ClinicSettings {
  return {
    setupComplete: true,
    ...countryDefaults(code),
    clinicName: clinicName || 'Your Clinic Name',
    tagline: '',
    practitioner: '',
    practitionerReg: '',
    logoUrl: '',
    logoPath: '',
    brandColor: '#1766b3',
    address: '',
    phone1: '',
    phone2: '',
    email: '',
    website: '',
    hours: '',
    registrationNo: '',
    taxIds: {},
    invoicePrefix: 'INV',
    filePrefix: 'FN',
    paymentDetails: {},
    templates: { ...DEFAULT_TEMPLATES },
    features: { constitution: false, prescriptions: true },
    idleMinutes: 30
  };
}
