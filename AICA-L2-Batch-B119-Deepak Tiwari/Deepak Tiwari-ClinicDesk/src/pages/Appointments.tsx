import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { can } from '../auth/permissions';
import { useData } from '../context/DataContext';
import { useSettings } from '../context/SettingsContext';
import { useToast } from '../context/ToastContext';
import { markReminded, setApptStatus } from '../data/db';
import { useApptsRange } from '../data/hooks';
import { addDays, longDate, time12 } from '../lib/dates';
import { mailtoLink, openExternal, smsLink, waLink } from '../lib/messaging';
import { waDigits } from '../lib/phone';
import { fill } from '../lib/template';
import { isEmail } from '../lib/validators';
import ApptForm from '../components/ApptForm';
import VisitForm from '../components/VisitForm';
import InvoiceViewer from '../components/InvoiceViewer';
import { Empty, Icon, Pill, Spinner } from '../components/ui';
import type { Appointment, Patient } from '../types';

type Channel = 'wa' | 'sms' | 'email';

export default function Appointments() {
  const { state } = useAuth();
  const { settings, today, locale, date: fmt } = useSettings();
  const { patientById } = useData();
  const toast = useToast();
  const t = today();
  const [day, setDay] = useState(t);
  const [form, setForm] = useState<{ appt?: Appointment } | null>(null);
  const [checkin, setCheckin] = useState<Appointment | null>(null);
  const [inv, setInv] = useState<string | null>(null);
  const role = state.kind === 'ready' ? state.profile.role : undefined;
  const actor = state.kind === 'ready' ? { uid: state.user.uid, name: state.profile.displayName } : null;
  const canWrite = can(role, 'patients.write');

  const dayList = useApptsRange(day, day);
  const tmr = addDays(t, 1);
  const queue = useApptsRange(tmr, tmr);

  const sorted = [...dayList.data].sort((a, b) => a.time.localeCompare(b.time));
  const due = queue.data.filter((a) => a.status === 'Scheduled').sort((a, b) => a.time.localeCompare(b.time));

  const message = (a: Appointment, p: Patient, ch: Channel) => {
    const map = { name: p.name, date: longDate(a.date, locale), time: time12(a.time), service: a.service, clinic: settings.clinicName, phone: settings.phone1, address: settings.address, practitioner: settings.practitioner };
    return ch === 'wa' ? fill(settings.templates.waRemind, map) : ch === 'sms' ? fill(settings.templates.smsRemind, map)
      : { subject: fill(settings.templates.emailRemindSubject, map), body: fill(settings.templates.emailRemindBody, map) };
  };
  const remind = async (a: Appointment, ch: Channel) => {
    const p = patientById(a.patientId); if (!p) return;
    if (a.status !== 'Scheduled') return toast('Only scheduled appointments get reminders.', 'err');
    if (ch === 'email') {
      if (!isEmail(p.email)) return toast('This patient has no valid email on their card.', 'err');
      const m = message(a, p, 'email') as { subject: string; body: string };
      openExternal(mailtoLink(p.email, m.subject, m.body));
    } else {
      if (!p.mobile) return toast('This patient has no mobile number on their card.', 'err');
      const text = message(a, p, ch) as string;
      openExternal(ch === 'wa' ? waLink(waDigits(p.mobile), text) : smsLink(p.mobile, text));
    }
    await markReminded(a.id, ch);
  };
  const status = async (a: Appointment, s: Appointment['status']) => { if (actor) { await setApptStatus(a.id, s, actor); toast(`Marked ${s.toLowerCase()}`); } };

  const chans = (a: Appointment) => ([
    ['wa', 'whatsapp', 'WhatsApp', a.remindWhatsApp, a.waRemindedAt], ['sms', 'sms', 'SMS', a.remindSms, a.smsRemindedAt], ['email', 'mail', 'Email', a.remindEmail, a.emailRemindedAt]
  ] as const).filter(([, , , on]) => on);

  const ReminderButtons = ({ a }: { a: Appointment }) => (
    <span className="rem">{chans(a).map(([ch, icon, label, , at]) => (
      <button key={ch} className={'btn sm rem-btn' + (at ? ' done' : '')} onClick={() => void remind(a, ch)} title={at ? `${label} reminder opened — press to send again` : `Send ${label} reminder`} disabled={a.status !== 'Scheduled'}>
        <Icon n={at ? 'check' : icon} size={14} />{label}
      </button>))}
      {!chans(a).length && <span className="muted small">No reminders chosen</span>}</span>
  );

  return (
    <>
      <div className="page-h">
        <div><h1>Appointments</h1><p className="muted">{longDate(day, locale)}</p></div>
        {canWrite && <button className="btn primary" onClick={() => setForm({})}><Icon n="plus" size={17} />Book appointment</button>}
      </div>

      <div className="toolbar">
        <div className="daynav">
          <button className="btn icon" onClick={() => setDay(addDays(day, -1))} aria-label="Previous day"><Icon n="chev" size={16} className="flip" /></button>
          <input type="date" value={day} onChange={(e) => e.target.value && setDay(e.target.value)} aria-label="Choose a date" />
          <button className="btn icon" onClick={() => setDay(addDays(day, 1))} aria-label="Next day"><Icon n="chev" size={16} /></button>
          {day !== t && <button className="btn sm" onClick={() => setDay(t)}>Today</button>}
        </div>
      </div>

      <section className="card">
        {dayList.loading ? <Spinner /> : !sorted.length ? <Empty title="Nothing booked for this day">Book from here, from a patient’s card, or as the next session when saving a visit.</Empty> : (
          <table className="tbl stack">
            <thead><tr><th>Time</th><th>Patient</th><th>Service</th><th>Status</th><th>Reminders</th><th aria-hidden="true" /></tr></thead>
            <tbody>{sorted.map((a) => (
              <tr key={a.id}>
                <td data-l="Time" className="nw"><b>{time12(a.time)}</b></td>
                <td data-l="Patient"><Link to={`/patient/${encodeURIComponent(a.patientId)}`}><b>{a.patientName}</b></Link></td>
                <td data-l="Service">{a.service || '—'}{a.notes && <div className="small muted">{a.notes}</div>}</td>
                <td data-l="Status"><Pill kind={a.status}>{a.status}</Pill></td>
                <td data-l="Reminders"><ReminderButtons a={a} /></td>
                <td className="row-actions">
                  {canWrite && a.status === 'Scheduled' && can(role, 'billing.write') && <button className="btn sm primary" onClick={() => setCheckin(a)}>Check in</button>}
                  {canWrite && a.status === 'Scheduled' && <button className="btn sm" onClick={() => void status(a, 'No-show')}>No-show</button>}
                  {canWrite && a.status === 'Scheduled' && <button className="btn sm" onClick={() => void status(a, 'Cancelled')}>Cancel</button>}
                  {canWrite && <button className="btn sm" onClick={() => setForm({ appt: a })}>Edit</button>}
                </td>
              </tr>))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card section-gap">
        <div className="card-h"><h2>Reminders for tomorrow</h2><span className="muted small">{fmt(tmr)}</span></div>
        <div className="card-b flush">
          {queue.loading ? <Spinner /> : due.length ? due.map((a) => (
            <div className="list-row wrap" key={a.id}>
              <span className="t">{time12(a.time)}</span>
              <span className="grow"><b>{a.patientName}</b><small className="muted block">{a.service || 'Appointment'}</small></span>
              <ReminderButtons a={a} />
            </div>
          )) : <Empty title="No appointments tomorrow" />}
        </div>
        <div className="card-f small muted">Each button opens WhatsApp, your SMS app or your email app with the message ready — a person presses Send. Fully automatic reminders need a server-side add-on (see README, “Automatic reminders”).</div>
      </section>

      {form && <ApptForm appt={form.appt} defaultDate={day} onClose={() => setForm(null)} onSaved={() => setForm(null)} />}
      {checkin && patientById(checkin.patientId) && (
        <VisitForm patient={patientById(checkin.patientId)!} prefillService={checkin.service} apptId={checkin.id} onClose={() => setCheckin(null)} onSaved={(v) => { setCheckin(null); setInv(v.id); }} />
      )}
      {inv && <InvoiceViewer visitId={inv} onClose={() => setInv(null)} />}
    </>
  );
}
