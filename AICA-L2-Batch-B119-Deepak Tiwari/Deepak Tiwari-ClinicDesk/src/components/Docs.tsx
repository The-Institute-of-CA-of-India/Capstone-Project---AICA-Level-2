import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { fmtMoney } from '../lib/money';
import { fmtDate } from '../lib/dates';
import { isHexColor } from '../lib/validators';
import type { InvoiceStatus, Payment, Prescription, PublicClinic, PublicInvoice } from '../types';
import { DEFAULT_LOGO } from './Layout';
import { Modal } from './ui';

/** Renders children into #print-root so that window.print() prints only the document. */
export function PrintPortal({ children }: { children: ReactNode }) {
  const [el, setEl] = useState<HTMLElement | null>(null);
  useEffect(() => {
    let r = document.getElementById('print-root');
    if (!r) { r = document.createElement('div'); r.id = 'print-root'; document.body.appendChild(r); }
    setEl(r);
  }, []);
  return el ? createPortal(children, el) : null;
}

/** A modal that shows a document and offers Print / Save as PDF (plus any extra buttons). */
export function DocModal({ title, doc, actions, below, onClose }: { title: string; doc: ReactNode; actions?: ReactNode; below?: ReactNode; onClose: () => void }) {
  return (
    <>
      <Modal title={title} wide onClose={onClose}
        footer={<>{actions}<button className="btn primary" onClick={() => window.print()}>Print / Save as PDF</button></>}>
        <div className="doc-scroll">{doc}</div>
        {below}
      </Modal>
      <PrintPortal>{doc}</PrintPortal>
    </>
  );
}

const accent = (c: PublicClinic): CSSProperties => ({ ['--doc-accent' as string]: isHexColor(c.brandColor) ? c.brandColor : '#1766b3' });

export function Letterhead({ c, right }: { c: PublicClinic; right?: ReactNode }) {
  const contact = [c.phone1, c.phone2].filter(Boolean).join(' · ');
  return (
    <header className="doc-head">
      <div className="doc-brand">
        <img className="doc-logo" src={c.logoUrl || DEFAULT_LOGO} alt="" onError={(e) => { (e.target as HTMLImageElement).src = DEFAULT_LOGO; }} />
        <div>
          <h1 className="doc-clinic">{c.name}</h1>
          {c.tagline && <div className="doc-tag">{c.tagline}</div>}
          <div className="doc-addr">
            {c.address && <div>{c.address}</div>}
            {contact && <div>{contact}</div>}
            {(c.email || c.website) && <div>{[c.email, c.website].filter(Boolean).join(' · ')}</div>}
            {c.registrationNo && <div>Reg. {c.registrationNo}</div>}
            {c.taxIdLines.map((t) => <div key={t.label}>{t.label}: {t.value}</div>)}
          </div>
        </div>
      </div>
      {right && <div className="doc-title-block">{right}</div>}
    </header>
  );
}

const STAMP: Partial<Record<InvoiceStatus, string>> = { Paid: 'PAID', Void: 'VOID', 'Part-paid': 'PART-PAID', Unpaid: 'UNPAID' };

export function InvoiceDoc({ clinic: c, inv }: { clinic: PublicClinic; inv: PublicInvoice['invoice'] }) {
  const m = (n: number) => fmtMoney(n, inv.currency, c.locale);
  const title = inv.taxEnabled ? c.titles.taxInvoice : c.titles.invoice;
  const anyCode = inv.lines.some((l) => l.code);
  const mixed = inv.taxEnabled && inv.lines.some((l) => !l.taxable) && inv.lines.some((l) => l.taxable);
  const exemptOnly = inv.taxEnabled && !inv.lines.some((l) => l.taxable);
  const stamp = STAMP[inv.status];
  return (
    <article className="doc invoice-doc" style={accent(c)}>
      <Letterhead c={c} right={<>
        <div className="doc-title">{title}</div>
        <dl className="doc-meta">
          <div><dt>No.</dt><dd>{inv.invoiceNo}</dd></div>
          <div><dt>Date</dt><dd>{fmtDate(inv.date, c.locale)}</dd></div>
        </dl>
        {stamp && <div className={'stamp ' + inv.status.toLowerCase().replace(/[^a-z]/g, '')}>{stamp}</div>}
      </>} />

      <section className="doc-bill">
        <div className="lbl">Billed to</div>
        <div className="bill-name">{inv.patientName}</div>
        <div className="muted">File no. {inv.fileNo}</div>
      </section>

      <table className="doc-table">
        <thead>
          <tr><th>Description</th>{anyCode && <th>HSN/SAC</th>}<th className="r">Qty</th><th className="r">Rate</th><th className="r">Amount</th></tr>
        </thead>
        <tbody>
          {inv.lines.map((l, i) => (
            <tr key={i}>
              <td>{l.name}{mixed && !l.taxable ? <sup title="Not subject to tax"> †</sup> : null}</td>
              {anyCode && <td>{l.code || ''}</td>}
              <td className="r">{l.qty}</td><td className="r">{m(l.rate)}</td><td className="r">{m(l.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <table className="doc-totals">
        <tbody>
          <tr><td>Subtotal</td><td>{m(inv.subtotal)}</td></tr>
          {inv.discount > 0 && <tr><td>Discount</td><td>−{m(inv.discount)}</td></tr>}
          {inv.taxEnabled && inv.tax > 0 && <>
            <tr className="sub"><td>Taxable value</td><td>{m(inv.taxableValue)}</td></tr>
            {inv.taxBreakup.map((t) => <tr key={t.label}><td>{t.label} @ {t.rate}%</td><td>{m(t.amount)}</td></tr>)}
          </>}
          <tr className="grand"><td>Total</td><td>{m(inv.total)}</td></tr>
          {inv.paid > 0 && <tr><td>Paid</td><td>{m(inv.paid)}</td></tr>}
          {inv.status !== 'Void' && inv.total > 0 && <tr className={'bal' + (inv.balance > 0.005 ? ' due' : '')}><td>Balance due</td><td>{m(Math.max(0, inv.balance))}</td></tr>}
        </tbody>
      </table>
      {inv.taxEnabled && inv.tax > 0 && inv.taxInclusive && <p className="doc-note">Amounts include tax.</p>}
      {mixed && <p className="doc-note">† Not subject to tax.</p>}
      {exemptOnly && <p className="doc-note">No tax is charged on these items.</p>}

      {inv.payments.length > 0 && (
        <section className="doc-pay">
          <div className="lbl">Payments received</div>
          <table className="doc-mini"><tbody>
            {inv.payments.map((p) => (
              <tr key={p.id}><td>{fmtDate(p.date, c.locale)}</td><td>{p.method}{p.ref ? ` · ${p.ref}` : ''}</td><td className="r">{m(p.amount)}</td></tr>
            ))}
          </tbody></table>
        </section>
      )}

      {inv.balance > 0.005 && inv.status !== 'Void' && c.paymentLines.length > 0 && (
        <section className="doc-pay">
          <div className="lbl">How to pay</div>
          {c.paymentLines.map((l, i) => <div key={i}>{l}</div>)}
        </section>
      )}

      <footer className="doc-foot">
        {c.footer && <div className="thanks">{c.footer}</div>}
        {c.disclaimer && <div className="fine">{c.disclaimer}</div>}
      </footer>
    </article>
  );
}

export function receiptNo(invoiceNo: string, payments: Payment[], id: string) {
  const i = payments.findIndex((p) => p.id === id);
  return `${invoiceNo}-R${i + 1}`;
}

export function ReceiptDoc({ clinic: c, inv, payment }: { clinic: PublicClinic; inv: PublicInvoice['invoice']; payment: Payment }) {
  const m = (n: number) => fmtMoney(n, inv.currency, c.locale);
  return (
    <article className="doc receipt-doc" style={accent(c)}>
      <Letterhead c={c} right={<>
        <div className="doc-title">{c.titles.receipt}</div>
        <dl className="doc-meta">
          <div><dt>No.</dt><dd>{receiptNo(inv.invoiceNo, inv.payments, payment.id)}</dd></div>
          <div><dt>Date</dt><dd>{fmtDate(payment.date, c.locale)}</dd></div>
        </dl>
      </>} />
      <section className="doc-bill">
        <div className="lbl">Received from</div>
        <div className="bill-name">{inv.patientName}</div>
        <div className="muted">File no. {inv.fileNo}</div>
      </section>
      <div className="receipt-amount">
        <span>Amount received</span><b>{m(payment.amount)}</b>
      </div>
      <table className="doc-mini receipt-rows"><tbody>
        <tr><td>Payment method</td><td>{payment.method}</td></tr>
        {payment.ref && <tr><td>Reference</td><td>{payment.ref}</td></tr>}
        <tr><td>Towards invoice</td><td>{inv.invoiceNo} ({fmtDate(inv.date, c.locale)})</td></tr>
        <tr><td>Invoice total</td><td>{m(inv.total)}</td></tr>
        <tr><td>Total paid so far</td><td>{m(inv.paid)}</td></tr>
        <tr><td>Balance remaining</td><td><b>{m(Math.max(0, inv.balance))}</b></td></tr>
      </tbody></table>
      <footer className="doc-foot">
        {c.footer && <div className="thanks">{c.footer}</div>}
        {c.disclaimer && <div className="fine">{c.disclaimer}</div>}
      </footer>
    </article>
  );
}

export function PrescriptionDoc({ clinic: c, rx, regLabel }: { clinic: PublicClinic; rx: Prescription; regLabel: string }) {
  return (
    <article className="doc rx-doc" style={accent(c)}>
      <Letterhead c={c} right={<>
        <div className="doc-title">{c.titles.prescription}</div>
        <dl className="doc-meta"><div><dt>Date</dt><dd>{fmtDate(rx.date, c.locale)}</dd></div></dl>
      </>} />
      <section className="doc-bill rx-patient">
        <div><div className="lbl">Patient</div><div className="bill-name">{rx.patientName}</div></div>
        <div className="muted">
          {[rx.patientAge && `Age ${rx.patientAge}`, rx.patientGender, `File no. ${rx.patientId}`].filter(Boolean).join(' · ')}
        </div>
      </section>
      <div className="rx-mark" aria-hidden="true">℞</div>
      <table className="doc-table rx-table">
        <thead><tr><th>Medicine</th><th>Dose</th><th>Frequency</th><th>Duration</th></tr></thead>
        <tbody>
          {rx.items.map((i, k) => (
            <tr key={k}>
              <td><b>{i.medicine}</b>{i.instructions && <div className="muted">{i.instructions}</div>}</td>
              <td>{i.dose}</td><td>{i.frequency}</td><td>{i.duration}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rx.notes && <p className="rx-notes"><b>Advice: </b>{rx.notes}</p>}
      <div className="rx-sign">
        <div className="line" />
        <div>{rx.prescriberName || 'Practitioner'}</div>
        {rx.prescriberReg && <div className="muted">{regLabel}: {rx.prescriberReg}</div>}
      </div>
      <footer className="doc-foot">{c.disclaimer && <div className="fine">{c.disclaimer}</div>}</footer>
    </article>
  );
}
