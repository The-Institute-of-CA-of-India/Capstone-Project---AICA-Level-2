/**
 * All Firestore / Storage writes live here (reads that need live updates are in hooks.ts).
 * This replaces the Apps Script `doPost` switch from the original system.
 *
 * Rules of thumb used throughout:
 *  - sequential numbers (file numbers, invoice numbers) are taken inside a transaction;
 *  - an invoice edit checks `updatedAt` so two people cannot silently overwrite each other;
 *  - a payment is added by reading the latest invoice inside a transaction, never from stale screen data;
 *  - every invoice write also refreshes its public snapshot (publicInvoices/{shareKey}).
 */
import {
  addDoc, collection, deleteDoc, doc, getDoc, runTransaction, setDoc, updateDoc, writeBatch,
  type Transaction
} from 'firebase/firestore';
import { deleteObject, getDownloadURL, ref as sref, uploadBytes } from 'firebase/storage';
import { getDb, getStore } from '../firebase/client';
import { calcInvoice } from '../lib/calc';
import { newShareKey, pad } from '../lib/ids';
import { toPublicInvoice } from '../lib/publicView';
import { country } from '../config/countries';
import type {
  Appointment, ApptStatus, ClinicSettings, Invite, Patient, PatientFile, Payment, Prescription, Role,
  Service, Supply, UserProfile, UserStatus, Visit
} from '../types';

export const C = {
  users: 'users', invites: 'invites', settings: 'settings', meta: 'meta', counters: 'counters',
  patients: 'patients', visits: 'visits', appointments: 'appointments', services: 'services',
  prescriptions: 'prescriptions', publicInvoices: 'publicInvoices', activityLog: 'activityLog'
} as const;

const col = (n: string) => collection(getDb(), n);
const dref = (n: string, id: string) => doc(getDb(), n, id);
const now = () => new Date().toISOString();
export const newId = (c: string) => doc(col(c)).id;

export interface Actor { uid: string; name: string }

/* ---------------------------------------------------------------- numbering */
async function takeNumber(tx: Transaction, key: string): Promise<number> {
  const r = dref(C.counters, key);
  const s = await tx.get(r);
  if (s.exists()) {
    const n = Number(s.data().next) || 1;
    tx.update(r, { next: n + 1 });
    return n;
  }
  tx.set(r, { next: 2 });
  return 1;
}

/* ---------------------------------------------------------------- activity log (append-only) */
export async function logActivity(actor: Actor, kind: string, refText: string, detail = ''): Promise<void> {
  try {
    await addDoc(col(C.activityLog), { at: now(), by: actor.uid, byName: actor.name, kind, ref: refText, detail: detail.slice(0, 300) });
  } catch { /* the audit trail must never block real work */ }
}

/* ---------------------------------------------------------------- users, invites, first-run */
export async function isInitialised(): Promise<boolean> {
  return (await getDoc(dref(C.meta, 'init'))).exists();
}
export async function getProfile(uid: string): Promise<UserProfile | null> {
  const s = await getDoc(dref(C.users, uid));
  return s.exists() ? ({ ...(s.data() as UserProfile), uid }) : null;
}
export async function getInvite(key: string): Promise<Invite | null> {
  if (!key) return null;
  try {
    const s = await getDoc(dref(C.invites, key));
    return s.exists() ? ({ ...(s.data() as Invite), id: key }) : null;
  } catch { return null; }
}
export interface Identity { uid: string; displayName: string; email: string; phone: string }

export async function createProfile(id: Identity, role: Role, status: UserStatus): Promise<UserProfile> {
  const p: UserProfile = {
    uid: id.uid, displayName: id.displayName || id.email || id.phone || 'User', email: id.email, phone: id.phone,
    role, status, createdAt: now(), lastLoginAt: now()
  };
  await setDoc(dref(C.users, id.uid), p);
  return p;
}
export async function touchLogin(uid: string): Promise<void> {
  try { await updateDoc(dref(C.users, uid), { lastLoginAt: now() }); } catch { /* not important */ }
}

/** The very first person to sign in becomes the owner. User, init marker and settings go in ONE batch. */
export async function bootstrapClinic(id: Identity, settings: ClinicSettings, sampleServices: boolean): Promise<UserProfile> {
  const db = getDb();
  const profile: UserProfile = {
    uid: id.uid, displayName: id.displayName || id.email || id.phone || 'Owner', email: id.email, phone: id.phone,
    role: 'owner', status: 'active', createdAt: now(), lastLoginAt: now()
  };
  const b = writeBatch(db);
  b.set(dref(C.users, id.uid), profile);
  b.set(dref(C.meta, 'init'), { ownerUid: id.uid, at: now() });
  b.set(dref(C.settings, 'clinic'), { ...settings, updatedAt: now(), updatedBy: id.uid });
  await b.commit();
  if (sampleServices) await seedServices(settings.country);
  return profile;
}

export async function seedServices(cc: ClinicSettings['country']): Promise<void> {
  const b = writeBatch(getDb());
  country(cc).sampleServices.forEach((s) => {
    const id = newId(C.services);
    b.set(dref(C.services, id), { id, ...s, active: true } satisfies Service);
  });
  await b.commit();
}

export async function setUserAccess(uid: string, role: Role, status: UserStatus, actor: Actor): Promise<void> {
  await updateDoc(dref(C.users, uid), { role, status });
  void logActivity(actor, 'User access changed', uid, `${role} / ${status}`);
}
export async function saveInvite(key: string, role: Invite['role'], note: string, actor: Actor): Promise<void> {
  await setDoc(dref(C.invites, key), { role, note: note.slice(0, 120), createdBy: actor.uid, createdAt: now() });
  void logActivity(actor, 'User invited', key, role);
}
export async function removeInvite(key: string, actor: Actor): Promise<void> {
  await deleteDoc(dref(C.invites, key));
  void logActivity(actor, 'Invite removed', key);
}

/* ---------------------------------------------------------------- settings */
export async function saveSettings(s: ClinicSettings, actor: Actor): Promise<void> {
  await setDoc(dref(C.settings, 'clinic'), { ...s, updatedAt: now(), updatedBy: actor.uid });
  void logActivity(actor, 'Settings saved', 'clinic');
}

export async function uploadLogo(blob: Blob, oldPath: string): Promise<{ url: string; path: string }> {
  const path = `branding/logo-${Date.now()}.png`;
  const r = sref(getStore(), path);
  await uploadBytes(r, blob, { contentType: 'image/png', cacheControl: 'public,max-age=86400' });
  const url = await getDownloadURL(r);
  if (oldPath && oldPath !== path) { try { await deleteObject(sref(getStore(), oldPath)); } catch { /* already gone */ } }
  return { url, path };
}
export async function removeLogoFile(path: string): Promise<void> {
  if (!path) return;
  try { await deleteObject(sref(getStore(), path)); } catch { /* already gone */ }
}

/* ---------------------------------------------------------------- patients */
const tidy = (s: unknown) => String(s ?? '').trim();

export function blankPatient(): Omit<Patient, 'id' | 'createdAt' | 'createdBy' | 'updatedAt' | 'updatedBy'> {
  return {
    name: '', mobile: '', altMobile: '', email: '', gender: '', age: '', nationality: '', occupation: '', idNumber: '',
    address: '', emergencyName: '', emergencyPhone: '', disease: '', constitution: [], weight: '', height: '', bp: '', pulse: '',
    history: '', medications: '', allergies: '', lifestyle: '', remindEmail: true, remindWhatsApp: true, remindSms: false,
    consent: false
  };
}

export async function savePatient(input: Partial<Patient>, actor: Actor, filePrefix: string): Promise<Patient> {
  const t = now();
  const clean = {
    ...blankPatient(), ...input,
    name: tidy(input.name).replace(/\s+/g, ' '),
    email: tidy(input.email).toLowerCase()
  };
  if (input.id) {
    const p = { ...clean, id: input.id, createdAt: input.createdAt || t, createdBy: input.createdBy || actor.uid, updatedAt: t, updatedBy: actor.uid } as Patient;
    await setDoc(dref(C.patients, p.id), p);
    return p;
  }
  return runTransaction(getDb(), async (tx) => {
    const n = await takeNumber(tx, 'patients');
    const id = `${filePrefix || 'FN'}-${pad(n, 4)}`;
    const p = { ...clean, id, createdAt: t, createdBy: actor.uid, updatedAt: t, updatedBy: actor.uid } as Patient;
    tx.set(dref(C.patients, id), p);
    return p;
  });
}

export async function uploadPatientFile(patientId: string, file: File, actor: Actor): Promise<void> {
  const id = newId('files');
  const safe = file.name.replace(/[^\w.\- ]+/g, '_').slice(0, 80);
  const path = `patients/${patientId}/${id}-${safe}`;
  await uploadBytes(sref(getStore(), path), file, { contentType: file.type || 'application/octet-stream' });
  const rec: PatientFile = { id, name: safe, path, size: file.size, contentType: file.type, uploadedBy: actor.uid, uploadedAt: now() };
  await setDoc(doc(getDb(), C.patients, patientId, 'files', id), rec);
  void logActivity(actor, 'File uploaded', patientId, safe);
}
export async function fileUrl(path: string): Promise<string> { return getDownloadURL(sref(getStore(), path)); }
export async function deletePatientFile(patientId: string, f: PatientFile, actor: Actor): Promise<void> {
  try { await deleteObject(sref(getStore(), f.path)); } catch { /* already gone */ }
  await deleteDoc(doc(getDb(), C.patients, patientId, 'files', f.id));
  void logActivity(actor, 'File deleted', patientId, f.name);
}

/* ---------------------------------------------------------------- visits & invoices */
export interface VisitDraft {
  id?: string;
  baseUpdatedAt?: string;
  date: string;
  patientId: string;
  patientName: string;
  weight: string; bp: string; pulse: string; temp: string; spo2: string;
  complaint: string; notes: string; advice: string;
  lines: Partial<Visit['lines'][number]>[];
  discount: number;
  taxEnabled: boolean; taxRate: number; taxInclusive: boolean; supply: Supply;
  payments: Partial<Payment>[];
}

function recalc(v: Visit): Visit {
  const r = calcInvoice({
    lines: v.lines, discount: v.discount, taxEnabled: v.taxEnabled, taxRate: v.taxRate, taxInclusive: v.taxInclusive,
    supply: v.supply, country: v.country, payments: v.payments, void: !!v.void, defaultDate: v.date
  });
  return { ...v, ...r };
}

export async function saveVisit(d: VisitDraft, actor: Actor, s: ClinicSettings, role: Role): Promise<Visit> {
  const t = now();
  const fields = {
    date: d.date, patientId: d.patientId, patientName: d.patientName,
    weight: tidy(d.weight), bp: tidy(d.bp), pulse: tidy(d.pulse), temp: tidy(d.temp), spo2: tidy(d.spo2),
    complaint: tidy(d.complaint).slice(0, 500), notes: String(d.notes || '').slice(0, 8000), advice: String(d.advice || '').slice(0, 2000),
    lines: d.lines as Visit['lines'], discount: d.discount,
    taxEnabled: d.taxEnabled, taxRate: d.taxRate, taxInclusive: d.taxInclusive, supply: d.supply,
    payments: d.payments as Payment[]
  };

  if (!d.id) {
    return runTransaction(getDb(), async (tx) => {
      const year = d.date.slice(0, 4);
      const n = await takeNumber(tx, 'invoice-' + year);
      const id = newId(C.visits);
      const v0: Visit = {
        ...(fields as unknown as Visit),
        id, invoiceNo: `${s.invoicePrefix || 'INV'}-${year}-${pad(n, 4)}`, shareKey: newShareKey(),
        currency: s.currency, country: s.country,
        subtotal: 0, taxableValue: 0, tax: 0, taxBreakup: [], total: 0, paid: 0, balance: 0, status: 'Unpaid',
        createdAt: t, createdBy: actor.uid, updatedAt: t, updatedBy: actor.uid
      };
      const v = recalc(v0);
      tx.set(dref(C.visits, id), v);
      tx.set(dref(C.publicInvoices, v.shareKey), toPublicInvoice(v, s));
      return v;
    });
  }

  return runTransaction(getDb(), async (tx) => {
    const r = dref(C.visits, d.id!);
    const snap = await tx.get(r);
    if (!snap.exists()) throw new Error('That visit no longer exists.');
    const ex = snap.data() as Visit;
    if (d.baseUpdatedAt && ex.updatedAt !== d.baseUpdatedAt)
      throw new Error('This invoice was changed by someone else while you were editing. Close it and open it again to see the latest version.');
    if (ex.void && role !== 'owner') throw new Error('This invoice is void. Only the owner can change it.');
    const v = recalc({ ...ex, ...fields, updatedAt: t, updatedBy: actor.uid });
    tx.set(r, v);
    tx.set(dref(C.publicInvoices, v.shareKey), toPublicInvoice(v, s));
    return v;
  });
}

export async function addPayment(
  visitId: string, p: { method: string; amount: number; ref: string; date: string }, actor: Actor, s: ClinicSettings
): Promise<Visit> {
  return runTransaction(getDb(), async (tx) => {
    const r = dref(C.visits, visitId);
    const snap = await tx.get(r);
    if (!snap.exists()) throw new Error('Invoice not found.');
    const ex = snap.data() as Visit;
    if (ex.void) throw new Error('This invoice is void.');
    const pay: Payment = { id: newId('p').slice(0, 8), date: p.date, method: p.method, amount: p.amount, ref: p.ref };
    const v = recalc({ ...ex, payments: [...ex.payments, pay], updatedAt: now(), updatedBy: actor.uid });
    tx.set(r, v);
    tx.set(dref(C.publicInvoices, v.shareKey), toPublicInvoice(v, s));
    return v;
  });
}

export async function setVoid(visitId: string, on: boolean, reason: string, actor: Actor, s: ClinicSettings): Promise<Visit> {
  const v = await runTransaction(getDb(), async (tx) => {
    const r = dref(C.visits, visitId);
    const snap = await tx.get(r);
    if (!snap.exists()) throw new Error('Invoice not found.');
    const ex = { ...(snap.data() as Visit) };
    if (on) { ex.void = true; ex.voidReason = reason.slice(0, 300); ex.voidAt = now(); ex.voidBy = actor.uid; }
    else { ex.void = false; ex.voidReason = ''; ex.voidAt = ''; ex.voidBy = ''; }
    const v2 = recalc({ ...ex, updatedAt: now(), updatedBy: actor.uid });
    tx.set(r, v2);
    tx.set(dref(C.publicInvoices, v2.shareKey), toPublicInvoice(v2, s));
    return v2;
  });
  void logActivity(actor, on ? 'Invoice voided' : 'Invoice restored', v.invoiceNo, reason);
  return v;
}

export async function markVisitSent(v: Visit, channel: 'email' | 'wa', actor: Actor): Promise<void> {
  const patch = channel === 'email' ? { emailedAt: now() } : { waSentAt: now() };
  await updateDoc(dref(C.visits, v.id), patch);
  void logActivity(actor, channel === 'email' ? 'Invoice e-mail opened' : 'Invoice WhatsApp opened', v.invoiceNo, 'link only');
}

/* ---------------------------------------------------------------- prescriptions */
export async function savePrescription(
  rx: Omit<Prescription, 'id' | 'createdAt' | 'createdBy' | 'updatedAt' | 'updatedBy'> & { createdAt?: string; createdBy?: string },
  actor: Actor
): Promise<void> {
  const items = rx.items.filter((i) => i.medicine.trim());
  const r = dref(C.prescriptions, rx.visitId);
  if (!items.length && !rx.notes.trim()) { try { await deleteDoc(r); } catch { /* none existed */ } return; }
  const t = now();
  await setDoc(r, { ...rx, items, id: rx.visitId, createdAt: rx.createdAt || t, createdBy: rx.createdBy || actor.uid, updatedAt: t, updatedBy: actor.uid });
}

/* ---------------------------------------------------------------- appointments */
export async function saveAppointment(
  d: Partial<Appointment> & { patientId: string; patientName: string; date: string; time: string },
  actor: Actor,
  moved = false
): Promise<Appointment> {
  const t = now();
  const id = d.id || newId(C.appointments);
  const a: Appointment = {
    id, date: d.date, time: d.time, patientId: d.patientId, patientName: d.patientName,
    service: tidy(d.service), status: d.status || 'Scheduled', notes: String(d.notes || '').slice(0, 2000),
    remindEmail: !!d.remindEmail, remindWhatsApp: !!d.remindWhatsApp, remindSms: !!d.remindSms,
    // moving an appointment to a new day/time means the old reminder no longer applies
    emailRemindedAt: moved ? '' : d.emailRemindedAt || '', waRemindedAt: moved ? '' : d.waRemindedAt || '', smsRemindedAt: moved ? '' : d.smsRemindedAt || '',
    createdAt: d.createdAt || t, createdBy: d.createdBy || actor.uid, updatedAt: t, updatedBy: actor.uid
  };
  await setDoc(dref(C.appointments, id), a);
  return a;
}
export async function setApptStatus(id: string, status: ApptStatus, actor: Actor): Promise<void> {
  await updateDoc(dref(C.appointments, id), { status, updatedAt: now(), updatedBy: actor.uid });
}
export async function markReminded(id: string, channel: 'email' | 'wa' | 'sms'): Promise<void> {
  const k = channel === 'email' ? 'emailRemindedAt' : channel === 'wa' ? 'waRemindedAt' : 'smsRemindedAt';
  await updateDoc(dref(C.appointments, id), { [k]: now() });
}

/* ---------------------------------------------------------------- services (price list) */
export async function saveServices(list: Service[], removedIds: string[], actor: Actor): Promise<void> {
  const b = writeBatch(getDb());
  list.forEach((s) => b.set(dref(C.services, s.id), {
    id: s.id, name: tidy(s.name).slice(0, 120), category: tidy(s.category || 'Other').slice(0, 60),
    price: Math.round((Number(s.price) || 0) * 100) / 100, minutes: Math.max(0, parseInt(String(s.minutes), 10) || 0),
    taxable: s.taxable !== false, code: tidy(s.code).slice(0, 20), active: s.active !== false
  } satisfies Service));
  removedIds.forEach((id) => b.delete(dref(C.services, id)));
  await b.commit();
  void logActivity(actor, 'Price list saved', 'services', `${list.length} services`);
}
