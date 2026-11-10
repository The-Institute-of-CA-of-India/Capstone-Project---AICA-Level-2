import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { normalizePhone } from '../lib/phone';
import { country } from '../config/countries';
import type { CountryCode } from '../types';

/* ------------------------------------------------------------------ icons */
const P: Record<string, string> = {
  home: 'M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z',
  users: 'M16 19v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 17.5V19 M10 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z M20 19v-1.5a3.5 3.5 0 0 0-2.5-3.35 M15.5 4.2a3.5 3.5 0 0 1 0 6.6',
  calendar: 'M7 3v3 M17 3v3 M4 8h16 M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z',
  receipt: 'M6 3h12v18l-3-2-3 2-3-2-3 2z M9 8h6 M9 12h6',
  tag: 'M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z M8 8h.01',
  chart: 'M4 20V10 M10 20V4 M16 20v-7 M22 20H2',
  settings: 'M4 6h9 M17 6h3 M4 12h3 M11 12h9 M4 18h11 M19 18h1 M15 4v4 M9 10v4 M17 16v4',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z M9 12l2 2 4-4',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z M20 20l-4-4',
  plus: 'M12 5v14 M5 12h14',
  x: 'M6 6l12 12 M18 6L6 18',
  check: 'M5 12l5 5 9-10',
  printer: 'M7 9V3h10v6 M6 17H4a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-2 M7 14h10v7H7z',
  whatsapp: 'M4 20l1.3-4A8 8 0 1 1 8.2 18.8z M9.5 9c.4 2 2.6 4.2 5 5l1-1.2-1.6-.9-.9.7c-.7-.3-1.5-1.1-1.8-1.8l.7-.9-.9-1.6z',
  mail: 'M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z M3 7l9 6 9-6',
  sms: 'M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z M8.5 12h.01 M12 12h.01 M15.5 12h.01',
  link: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1 M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
  upload: 'M12 16V4 M7 9l5-5 5 5 M4 20h16',
  download: 'M12 4v12 M7 11l5 5 5-5 M4 20h16',
  trash: 'M4 7h16 M9 7V4h6v3 M6 7l1 13h10l1-13',
  logout: 'M10 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h5 M15 8l4 4-4 4 M19 12H9',
  alert: 'M12 3l10 18H2z M12 10v5 M12 18h.01',
  chev: 'M9 6l6 6-6 6',
  phone: 'M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1z',
  edit: 'M4 20h4L19 9l-4-4L4 16z M14 6l4 4',
  clock: 'M12 7v5l3 2 M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z',
  file: 'M6 3h8l4 4v14H6z M14 3v4h4',
  pill: 'M10.5 20.5a4.95 4.95 0 0 1-7-7l10-10a4.95 4.95 0 0 1 7 7z M8.5 8.5l7 7',
  menu: 'M4 6h16 M4 12h16 M4 18h16',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 20a8 8 0 0 1 16 0',
  more: 'M5 12h.01 M12 12h.01 M19 12h.01',
  ban: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M5.6 5.6l12.8 12.8',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 11v5 M12 8h.01',
  copy: 'M9 9h10v11H9z M5 15V4h10',
  lock: 'M6 11h12v9H6z M8 11V8a4 4 0 0 1 8 0v3',
  card: 'M3 6h18v12H3z M3 10h18 M7 15h3'
};
export function Icon({ n, size = 18, className = '' }: { n: keyof typeof P | string; size?: number; className?: string }) {
  return (
    <svg className={'ic ' + className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {(P[n] || '').split(' M').map((d, i) => <path key={i} d={(i ? 'M' : '') + d} />)}
    </svg>
  );
}
export function GoogleG({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z" />
      <path fill="#FBBC05" d="M10.5 28.7a14.5 14.5 0 0 1 0-9.4l-7.9-6.1a24 24 0 0 0 0 21.6z" />
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
    </svg>
  );
}

/* ------------------------------------------------------------------ modal (native <dialog>: focus trap + Esc for free) */
export function Modal({ title, sub, onClose, children, wide = false, footer }: {
  title: ReactNode; sub?: ReactNode; onClose: () => void; children: ReactNode; wide?: boolean; footer?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
    document.body.classList.add('modal-open');
    return () => { document.body.classList.remove('modal-open'); };
  }, []);
  return (
    <dialog ref={ref} className={'modal' + (wide ? ' wide' : '')} onCancel={(e) => { e.preventDefault(); onClose(); }}
      onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      <div className="modal-card">
        <header className="modal-h">
          <div className="modal-t"><h2>{title}</h2>{sub && <div className="sub">{sub}</div>}</div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close"><Icon n="x" /></button>
        </header>
        <div className="modal-b">{children}</div>
        {footer && <footer className="modal-f">{footer}</footer>}
      </div>
    </dialog>
  );
}

export function ConfirmModal({ title, body, confirmLabel = 'Confirm', danger, onConfirm, onClose }: {
  title: string; body: ReactNode; confirmLabel?: string; danger?: boolean; onConfirm: () => void | Promise<void>; onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <Modal title={title} onClose={onClose}
      footer={<>
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className={'btn ' + (danger ? 'danger' : 'primary')} disabled={busy}
          onClick={async () => { setBusy(true); try { await onConfirm(); } finally { setBusy(false); } }}>{confirmLabel}</button>
      </>}>
      <div className="prose">{body}</div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ form bits */
export function Field({ label, hint, error, children, span, htmlFor }: {
  label: ReactNode; hint?: ReactNode; error?: string; children: ReactNode; span?: 2 | 3 | 'all'; htmlFor?: string;
}) {
  return (
    <div className={'field' + (span ? ' span-' + span : '') + (error ? ' has-err' : '')}>
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {error ? <div className="err" role="alert">{error}</div> : hint ? <div className="hint">{hint}</div> : null}
    </div>
  );
}

/** A text input with a stable id so a <Field label> is properly associated. */
export function useFieldId() { return useId(); }

/** Mobile number input for the selected country; stores what the user typed, reports validity on blur. */
export function PhoneInput({ value, onChange, cc, label, required, hint, id }: {
  value: string; onChange: (v: string) => void; cc: CountryCode; label: ReactNode; required?: boolean; hint?: string; id?: string;
}) {
  const gen = useId();
  const fid = id || gen;
  const c = country(cc);
  const [touched, setTouched] = useState(false);
  const r = normalizePhone(value, cc);
  const error = touched && !r.ok ? r.error : required && touched && !value.trim() ? 'Enter a mobile number.' : '';
  return (
    <Field label={label} htmlFor={fid} error={error} hint={hint || (r.ok && r.e164 ? `Will be saved as ${r.display}` : `${c.name} number, e.g. ${c.phone.example}`)}>
      <input id={fid} type="tel" inputMode="tel" autoComplete="tel" value={value} placeholder={c.phone.example}
        onChange={(e) => onChange(e.target.value)} onBlur={() => setTouched(true)} />
    </Field>
  );
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return <div className="spinner-wrap" role="status"><span className="spinner" aria-hidden="true" />{label}</div>;
}
export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="empty"><b>{title}</b>{children && <p>{children}</p>}{action}</div>;
}
export function Pill({ kind, children }: { kind: string; children: ReactNode }) {
  return <span className={'pill ' + kind.toLowerCase().replace(/[^a-z]+/g, '-')}>{children}</span>;
}
export function Seg<T extends string>({ value, options, onChange, label }: {
  value: T; options: { v: T; l: string }[]; onChange: (v: T) => void; label: string;
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => <button type="button" key={o.v} className={o.v === value ? 'on' : ''} aria-pressed={o.v === value} onClick={() => onChange(o.v)}>{o.l}</button>)}
    </div>
  );
}
export function Notice({ kind = 'info', children }: { kind?: 'info' | 'warn' | 'err' | 'ok'; children: ReactNode }) {
  return <div className={'notice ' + kind} role={kind === 'err' ? 'alert' : undefined}><Icon n={kind === 'ok' ? 'check' : kind === 'info' ? 'info' : 'alert'} size={16} /><div>{children}</div></div>;
}
export function Toggle({ checked, onChange, label, help }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; help?: ReactNode }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="track" aria-hidden="true"><span className="thumb" /></span>
      <span className="tl"><b>{label}</b>{help && <small>{help}</small>}</span>
    </label>
  );
}
export function Check({ checked, onChange, children }: { checked: boolean; onChange: (v: boolean) => void; children: ReactNode }) {
  return <label className="check"><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} /><span>{children}</span></label>;
}

export const initials = (n: string) => n.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join('') || '?';
