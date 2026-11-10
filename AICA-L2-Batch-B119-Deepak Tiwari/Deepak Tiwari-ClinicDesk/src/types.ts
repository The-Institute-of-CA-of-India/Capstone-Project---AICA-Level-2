/* Shared data types. Dates are stored as ISO strings ("2026-11-04", "2026-11-04T09:30:00.000Z")
   so the data is readable in the Firebase console and easy to export. */

export type CountryCode = 'KE' | 'IN';
export type Role = 'owner' | 'doctor' | 'reception' | 'none';
export type UserStatus = 'active' | 'pending' | 'disabled';
export type Supply = 'intra' | 'inter';

export interface UserProfile {
  uid: string;
  displayName: string;
  email: string;
  phone: string;
  role: Role;
  status: UserStatus;
  createdAt: string;
  lastLoginAt: string;
}

export interface Invite {
  id: string;            // the e-mail address (lower-case) or the phone number (E.164)
  role: 'doctor' | 'reception' | 'owner';
  note?: string;
  createdBy: string;
  createdAt: string;
}

export interface TaxSettings {
  enabled: boolean;
  rate: number;          // total rate in percent (VAT 16, GST 18 ...)
  inclusive: boolean;    // prices already include tax
  defaultSupply: Supply; // India: intra-state (CGST+SGST) or inter-state (IGST)
}

export interface MessageTemplates {
  waInvoice: string;
  waRemind: string;
  smsRemind: string;
  emailInvoiceSubject: string;
  emailInvoiceBody: string;
  emailRemindSubject: string;
  emailRemindBody: string;
}

export interface ClinicSettings {
  setupComplete: boolean;
  country: CountryCode;
  currency: string;
  // identity & branding
  clinicName: string;
  tagline: string;
  practitioner: string;
  practitionerReg: string;       // practitioner's medical-council registration no.
  logoUrl: string;
  logoPath: string;
  brandColor: string;
  // contact
  address: string;
  phone1: string;
  phone2: string;
  email: string;
  website: string;
  hours: string;
  registrationNo: string;        // clinic registration / licence (optional)
  taxIds: Record<string, string>;
  // billing
  tax: TaxSettings;
  invoicePrefix: string;
  filePrefix: string;
  paymentMethods: string[];
  paymentDetails: Record<string, string>;
  titles: { invoice: string; taxInvoice: string; receipt: string; prescription: string };
  invoiceFooter: string;
  disclaimer: string;
  consentText: string;
  templates: MessageTemplates;
  // behaviour
  features: { constitution: boolean; prescriptions: boolean };
  idleMinutes: number;           // auto sign-out after inactivity (0 = never)
  updatedAt?: string;
  updatedBy?: string;
}

export interface Patient {
  id: string;                    // file number, e.g. FN-0001
  name: string;
  mobile: string;                // E.164
  altMobile: string;
  email: string;
  gender: string;
  age: string;
  nationality: string;
  occupation: string;
  idNumber: string;
  address: string;
  emergencyName: string;
  emergencyPhone: string;
  disease: string;               // main complaint
  constitution: string[];        // optional Ayurvedic prakriti
  weight: string;
  height: string;
  bp: string;
  pulse: string;
  history: string;
  medications: string;
  allergies: string;
  lifestyle: string;
  remindEmail: boolean;
  remindWhatsApp: boolean;
  remindSms: boolean;
  consent: boolean;
  consentAt?: string;
  archived?: boolean;
  createdAt: string;
  createdBy: string;
  updatedAt: string;
  updatedBy: string;
}

export interface InvoiceLine {
  name: string;
  category: string;
  qty: number;
  rate: number;
  amount: number;
  taxable: boolean;
  code?: string;                 // HSN / SAC code (optional)
}

export interface Payment {
  id: string;
  date: string;
  method: string;
  amount: number;
  ref: string;
}

export interface TaxLine { label: string; rate: number; amount: number }
export type InvoiceStatus = 'Unpaid' | 'Part-paid' | 'Paid' | 'No charge' | 'Void';

export interface Visit {
  id: string;
  invoiceNo: string;
  shareKey: string;
  date: string;
  patientId: string;
  patientName: string;
  // clinical
  weight: string; bp: string; pulse: string; temp: string; spo2: string;
  complaint: string;
  notes: string;
  advice: string;
  // billing
  currency: string;
  country: CountryCode;
  lines: InvoiceLine[];
  discount: number;
  taxEnabled: boolean;
  taxRate: number;
  taxInclusive: boolean;
  supply: Supply;
  subtotal: number;
  taxableValue: number;
  tax: number;
  taxBreakup: TaxLine[];
  total: number;
  payments: Payment[];
  paid: number;
  balance: number;
  status: InvoiceStatus;
  void?: boolean;
  voidReason?: string;
  voidAt?: string;
  voidBy?: string;
  emailedAt?: string;
  waSentAt?: string;
  createdAt: string; createdBy: string; updatedAt: string; updatedBy: string;
}

export type ApptStatus = 'Scheduled' | 'Completed' | 'Cancelled' | 'No-show';
export interface Appointment {
  id: string;
  date: string;
  time: string;
  patientId: string;
  patientName: string;
  service: string;
  status: ApptStatus;
  notes: string;
  remindEmail: boolean; remindWhatsApp: boolean; remindSms: boolean;
  emailRemindedAt?: string; waRemindedAt?: string; smsRemindedAt?: string;
  createdAt: string; createdBy: string; updatedAt: string; updatedBy: string;
}

export interface Service {
  id: string;
  name: string;
  category: string;
  price: number;
  minutes: number;
  taxable: boolean;
  code: string;
  active: boolean;
}

export interface RxItem { medicine: string; dose: string; frequency: string; duration: string; instructions: string }
export interface Prescription {
  id: string;
  visitId: string;
  patientId: string;
  patientName: string;
  patientAge: string;
  patientGender: string;
  date: string;
  items: RxItem[];
  notes: string;
  prescriberName: string;
  prescriberReg: string;
  createdAt: string; createdBy: string; updatedAt: string; updatedBy: string;
}

export interface PatientFile {
  id: string;
  name: string;
  path: string;
  size: number;
  contentType: string;
  uploadedBy: string;
  uploadedAt: string;
}

/** What the public invoice link (and the print view) needs. No clinical data, no patient contact details. */
export interface PublicClinic {
  name: string; tagline: string; logoUrl: string; brandColor: string;
  address: string; phone1: string; phone2: string; email: string; website: string;
  registrationNo: string; practitioner: string; practitionerReg: string;
  taxIdLines: { label: string; value: string }[];
  footer: string; disclaimer: string;
  paymentLines: string[];
  titles: { invoice: string; taxInvoice: string; receipt: string; prescription: string };
  locale: string;
}
export interface PublicInvoice {
  key: string;
  clinic: PublicClinic;
  invoice: {
    invoiceNo: string; date: string; patientName: string; fileNo: string;
    currency: string; taxEnabled: boolean; taxInclusive: boolean; supply: Supply;
    lines: InvoiceLine[]; subtotal: number; discount: number; taxableValue: number; tax: number;
    taxBreakup: TaxLine[]; total: number; paid: number; balance: number; status: InvoiceStatus;
    payments: Payment[];
  };
  updatedAt: string;
}
export interface LogEntry {
  id: string; at: string; by: string; byName: string; kind: string; ref: string; detail: string;
}
