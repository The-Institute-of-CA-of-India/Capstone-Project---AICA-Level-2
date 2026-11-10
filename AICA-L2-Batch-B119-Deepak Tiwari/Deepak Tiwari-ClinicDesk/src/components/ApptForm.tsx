import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { useData } from '../context/DataContext';
import { useSettings } from '../context/SettingsContext';
import { useToast } from '../context/ToastContext';
import { saveAppointment } from '../data/db';
import { isYmd } from '../lib/dates';
import type { Appointment, ApptStatus } from '../types';
import PatientPicker from './PatientPicker';
import { Check, Field, Modal, Notice } from './ui';

const STATUSES: ApptStatus[] = ['Scheduled', 'Completed', 'Cancelled', 'No-show'];

export default function ApptForm({ appt, patientId, defaultDate, onClose, onSaved }: {
  appt?: Appointment; patientId?: string; defaultDate?: string; onClose: () => void; onSaved: (a: Appointment) => void;
}) {
  const { state } = useAuth();
  const { services, patientById } = useData();
  const { today } = useSettings();
  const toast = useToast();
  const [pid, setPid] = useState(appt?.patientId || patientId || '');
  const [date, setDate] = useState(appt?.date || defaultDate || today());
  const [time, setTime] = useState(appt?.time || '10:00');
  const [service, setService] = useState(appt?.service || '');
  const [notes, setNotes] = useState(appt?.notes || '');
  const [status, setStatus] = useState<ApptStatus>(appt?.status || 'Scheduled');
  const p0 = patientById(pid);
  const [rE, setRE] = useState(appt ? appt.remindEmail : (p0?.remindEmail ?? true));
  const [rW, setRW] = useState(appt ? appt.remindWhatsApp : (p0?.remindWhatsApp ?? true));
  const [rS, setRS] = useState(appt ? appt.remindSms : (p0?.remindSms ?? false));
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);

  const pick = (id: string) => {
    setPid(id);
    const p = patientById(id);
    if (p && !appt) { setRE(p.remindEmail); setRW(p.remindWhatsApp); setRS(p.remindSms); }
  };
  const save = async () => {
    const p = patientById(pid);
    if (!p) return setErr('Choose the patient.');
    if (!isYmd(date)) return setErr('Enter the appointment date.');
    if (!/^\d{2}:\d{2}$/.test(time)) return setErr('Enter the appointment time.');
    if (state.kind !== 'ready') return;
    setBusy(true); setErr('');
    try {
      const moved = !!appt && (appt.date !== date || appt.time !== time);
      const a = await saveAppointment({ ...appt, patientId: p.id, patientName: p.name, date, time, service, notes, status, remindEmail: rE, remindWhatsApp: rW, remindSms: rS },
        { uid: state.user.uid, name: state.profile.displayName }, moved);
      toast('Appointment saved'); onSaved(a);
    } catch (e) { setErr(e instanceof Error ? e.message : 'Could not save.'); setBusy(false); }
  };
  return (
    <Modal title={appt ? 'Edit appointment' : 'Book an appointment'} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy} onClick={() => void save()}>Save appointment</button></>}>
      {err && <Notice kind="err">{err}</Notice>}
      {appt ? <p><b>{appt.patientName}</b></p> : <PatientPicker value={pid} onChange={pick} autoFocus={!patientId} />}
      <div className="grid g2">
        <Field label="Date" htmlFor="ap-d"><input id="ap-d" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
        <Field label="Time" htmlFor="ap-t"><input id="ap-t" type="time" value={time} onChange={(e) => setTime(e.target.value)} /></Field>
        <Field label="Service" span="all" htmlFor="ap-s">
          <input id="ap-s" list="ap-services" value={service} onChange={(e) => setService(e.target.value)} placeholder="Choose or type" />
          <datalist id="ap-services">{services.filter((s) => s.active).map((s) => <option key={s.id} value={s.name} />)}</datalist>
        </Field>
        {appt && <Field label="Status" htmlFor="ap-st"><select id="ap-st" value={status} onChange={(e) => setStatus(e.target.value as ApptStatus)}>{STATUSES.map((s) => <option key={s}>{s}</option>)}</select></Field>}
        <Field label="Notes" span="all" htmlFor="ap-n"><input id="ap-n" value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
      </div>
      <div className="checks">
        <Check checked={rW} onChange={setRW}>WhatsApp reminder</Check>
        <Check checked={rS} onChange={setRS}>SMS reminder</Check>
        <Check checked={rE} onChange={setRE}>Email reminder</Check>
      </div>
      {appt && (appt.date !== date || appt.time !== time) && <p className="muted small">Moving the appointment resets its reminders, so the patient is reminded of the new time.</p>}
    </Modal>
  );
}
