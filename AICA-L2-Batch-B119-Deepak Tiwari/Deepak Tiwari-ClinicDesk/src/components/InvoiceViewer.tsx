import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { can } from '../auth/permissions';
import { useSettings } from '../context/SettingsContext';
import { useData } from '../context/DataContext';
import { useToast } from '../context/ToastContext';
import { addPayment, markVisitSent, setVoid } from '../data/db';
import { useVisitDoc } from '../data/hooks';
import { fill } from '../lib/template';
import { mailtoLink, openExternal, waLink } from '../lib/messaging';
import { waDigits } from '../lib/phone';
import { round2 } from '../lib/calc';
import { toPublicInvoice } from '../lib/publicView';
import { isEmail } from '../lib/validators';
import type { Visit } from '../types';
import { DocModal, InvoiceDoc, ReceiptDoc, receiptNo } from './Docs';
import VisitForm from './VisitForm';
import { Field, Icon, Modal, Notice, Spinner } from './ui';

export function publicLink(shareKey: string) {
  return `${window.location.origin}${window.location.pathname}#/inv/${shareKey}`;
}

export function PayModal({ visit, onClose }: { visit: Visit; onClose: () => void }) {
  const { state } = useAuth();
  const { settings, today, money } = useSettings();
  const toast = useToast();
  const due = Math.max(0, round2(visit.balance));
  const [method, setMethod] = useState(settings.paymentMethods[0] || 'Cash');
  const [amount, setAmount] = useState(String(due));
  const [ref, setRef] = useState('');
  const [date, setDate] = useState(today());
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const go = async () => {
    const a = round2(Number(amount));
    if (!(a > 0)) return setErr('Enter the amount received.');
    if (a > due + 0.005) return setErr(`That is more than the balance (${money(due, visit.currency)}).`);
    if (state.kind !== 'ready') return;
    setBusy(true); setErr('');
    try {
      await addPayment(visit.id, { method, amount: a, ref: ref.trim(), date }, { uid: state.user.uid, name: state.profile.displayName }, settings);
      toast('Payment recorded'); onClose();
    } catch (e) { setErr(e instanceof Error ? e.message : 'Could not record the payment.'); setBusy(false); }
  };
  return (
    <Modal title="Record a payment" sub={`${visit.patientName} · ${visit.invoiceNo}`} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy} onClick={() => void go()}>Record payment</button></>}>
      {err && <Notice kind="err">{err}</Notice>}
      <p>Balance due: <b className="money">{money(due, visit.currency)}</b></p>
      <div className="grid g2">
        <Field label="Method" htmlFor="pm-m"><select id="pm-m" value={method} onChange={(e) => setMethod(e.target.value)}>{settings.paymentMethods.map((x) => <option key={x}>{x}</option>)}</select></Field>
        <Field label="Amount" htmlFor="pm-a"><input id="pm-a" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus /></Field>
        <Field label="Date" htmlFor="pm-d"><input id="pm-d" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
        <Field label="Reference / transaction code" htmlFor="pm-r"><input id="pm-r" value={ref} onChange={(e) => setRef(e.target.value)} /></Field>
      </div>
    </Modal>
  );
}

export default function InvoiceViewer({ visitId, onClose }: { visitId: string; onClose: () => void }) {
  const { state } = useAuth();
  const { settings } = useSettings();
  const { patientById } = useData();
  const toast = useToast();
  const { visit, loading } = useVisitDoc(visitId);
  const [pay, setPay] = useState(false);
  const [edit, setEdit] = useState(false);
  const [receipt, setReceipt] = useState<string | null>(null);
  const [voiding, setVoiding] = useState(false);
  const [reason, setReason] = useState('');
  const role = state.kind === 'ready' ? state.profile.role : undefined;

  if (loading) return <Modal title="Invoice" onClose={onClose}><Spinner /></Modal>;
  if (!visit || state.kind !== 'ready') return <Modal title="Invoice" onClose={onClose}><p>This invoice could not be found.</p></Modal>;
  const patient = patientById(visit.patientId);
  const pub = toPublicInvoice(visit, settings);
  const link = publicLink(visit.shareKey);
  const actor = { uid: state.user.uid, name: state.profile.displayName };
  const vars = { clinic: settings.clinicName, link, name: visit.patientName, number: visit.invoiceNo, total: '', practitioner: settings.practitioner, phone: settings.phone1 };

  const sendWa = () => {
    if (!patient?.mobile) return toast('This patient has no mobile number on their card.', 'err');
    const text = fill(settings.templates.waInvoice, { clinic: settings.clinicName, link });
    openExternal(waLink(waDigits(patient.mobile), text));
    void markVisitSent(visit, 'wa', actor);
  };
  const sendMail = () => {
    if (!patient || !isEmail(patient.email)) return toast('This patient has no valid email on their card.', 'err');
    const total = new Intl.NumberFormat(pub.clinic.locale, { style: 'decimal', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(visit.total);
    const map = { ...vars, total: `${visit.currency} ${total}` };
    openExternal(mailtoLink(patient.email, fill(settings.templates.emailInvoiceSubject, map), fill(settings.templates.emailInvoiceBody, map)));
    void markVisitSent(visit, 'email', actor);
  };
  const copy = async () => { try { await navigator.clipboard.writeText(link); toast('Invoice link copied'); } catch { toast(link, 'info'); } };

  const doVoid = async (on: boolean) => {
    try { await setVoid(visit.id, on, reason, actor, settings); toast(on ? 'Invoice voided' : 'Invoice restored'); setVoiding(false); setReason(''); }
    catch (e) { toast(e instanceof Error ? e.message : 'Could not change the invoice.', 'err'); }
  };

  if (edit && patient) return <VisitForm patient={patient} visit={visit} onClose={() => setEdit(false)} onSaved={() => setEdit(false)} />;
  const rec = receipt ? visit.payments.find((p) => p.id === receipt) : null;
  if (rec) return (
    <DocModal title="Payment receipt" onClose={() => setReceipt(null)} doc={<ReceiptDoc clinic={pub.clinic} inv={pub.invoice} payment={rec} />} />
  );

  return (
    <>
      <DocModal title={visit.invoiceNo} onClose={onClose}
        doc={<InvoiceDoc clinic={pub.clinic} inv={pub.invoice} />}
        actions={<div className="doc-actions">
          {!visit.void && visit.balance > 0.005 && <button className="btn" onClick={() => setPay(true)}><Icon n="card" size={16} />Add payment</button>}
          <button className="btn" onClick={sendWa}><Icon n="whatsapp" size={16} />WhatsApp</button>
          <button className="btn" onClick={sendMail}><Icon n="mail" size={16} />Email</button>
          <button className="btn" onClick={() => void copy()}><Icon n="link" size={16} />Copy link</button>
          {can(role, 'billing.write') && (!visit.void || role === 'owner') && <button className="btn" onClick={() => setEdit(true)}><Icon n="edit" size={16} />Edit</button>}
          {can(role, 'void') && (visit.void
            ? <button className="btn" onClick={() => void doVoid(false)}>Restore invoice</button>
            : <button className="btn danger-o" onClick={() => setVoiding(true)}><Icon n="ban" size={16} />Void</button>)}
        </div>}
        below={visit.payments.length > 0 ? (
          <div className="receipts no-print">
            <b>Receipts</b>
            {visit.payments.map((p) => (
              <button key={p.id} className="btn sm" onClick={() => setReceipt(p.id)}><Icon n="receipt" size={15} />{receiptNo(visit.invoiceNo, visit.payments, p.id)} · {p.method}</button>
            ))}
          </div>) : null} />
      {pay && <PayModal visit={visit} onClose={() => setPay(false)} />}
      {voiding && (
        <Modal title="Void this invoice?" onClose={() => setVoiding(false)}
          footer={<><button className="btn" onClick={() => setVoiding(false)}>Keep invoice</button><button className="btn danger" onClick={() => void doVoid(true)}>Void invoice</button></>}>
          <p>A void invoice drops out of totals and cannot be sent. Only the owner can restore it. The record is kept for the audit trail.</p>
          <Field label="Reason" htmlFor="void-r"><input id="void-r" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. entered in error" autoFocus /></Field>
        </Modal>
      )}
    </>
  );
}
