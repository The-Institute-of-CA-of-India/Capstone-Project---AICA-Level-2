import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useSettings } from '../context/SettingsContext';
import { useData } from '../context/DataContext';
import { useToast } from '../context/ToastContext';
import { blankPatient, savePatient } from '../data/db';
import { normalizePhone } from '../lib/phone';
import { isEmail } from '../lib/validators';
import { Check, Field, Modal, Notice, PhoneInput } from './ui';
import type { Patient } from '../types';

const DOSHAS = ['Vata', 'Pitta', 'Kapha'];

export default function PatientForm({ patient, initialName, onClose, onSaved }: {
  patient?: Patient; initialName?: string; onClose: () => void; onSaved: (p: Patient) => void;
}) {
  const { state } = useAuth();
  const { settings, cfg } = useSettings();
  const { patients } = useData();
  const toast = useToast();
  const [f, setF] = useState(() => ({ ...blankPatient(), ...(patient || {}), name: patient?.name || initialName || '' }));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const isNew = !patient;
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));

  const mobile = normalizePhone(f.mobile, settings.country);
  const dup = useMemo(() => {
    const m = mobile.ok ? mobile.e164 : '';
    const em = f.email.trim().toLowerCase();
    return patients.find((p) => p.id !== patient?.id && ((m && p.mobile === m) || (em && p.email === em)));
  }, [patients, mobile, f.email, patient?.id]);

  const save = async () => {
    setErr('');
    if (!f.name.trim()) return setErr('Enter the patient’s name.');
    const m = normalizePhone(f.mobile, settings.country), a = normalizePhone(f.altMobile, settings.country), e = normalizePhone(f.emergencyPhone, settings.country);
    if (!m.ok) return setErr('Mobile: ' + m.error);
    if (!a.ok) return setErr('Alternative mobile: ' + a.error);
    if (!e.ok) return setErr('Emergency contact phone: ' + e.error);
    if (f.email.trim() && !isEmail(f.email)) return setErr('That email address does not look right.');
    if (!m.e164 && !f.email.trim()) return setErr('Enter a mobile number or an email address so the patient can receive invoices and reminders.');
    if (isNew && !f.consent) return setErr('Tick the consent box once the patient has agreed.');
    if (state.kind !== 'ready') return;
    setBusy(true);
    try {
      const out = await savePatient({
        ...f, id: patient?.id, mobile: m.e164, altMobile: a.e164, emergencyPhone: e.e164,
        consentAt: f.consent && !patient?.consent ? new Date().toISOString() : patient?.consentAt
      }, { uid: state.user.uid, name: state.profile.displayName }, settings.filePrefix);
      toast(isNew ? `Health card ${out.id} created` : 'Changes saved');
      onSaved(out);
    } catch (x) { setErr(x instanceof Error ? x.message : 'Could not save.'); setBusy(false); }
  };

  return (
    <Modal wide title={isNew ? 'New health card' : 'Edit health card'} sub={patient ? <span className="fileno">{patient.id}</span> : undefined} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy} onClick={() => void save()}>{isNew ? 'Create health card' : 'Save changes'}</button></>}>
      {err && <Notice kind="err">{err}</Notice>}
      {dup && <Notice kind="warn">Someone with this mobile number or email is already on file: <Link to={`/patient/${encodeURIComponent(dup.id)}`} onClick={onClose}><b>{dup.name}</b> ({dup.id})</Link>. Check you are not creating a duplicate.</Notice>}

      <fieldset className="fs"><legend>Patient</legend>
        <div className="grid g3">
          <Field label="Full name" span={2} htmlFor="p-name"><input id="p-name" value={f.name} onChange={(e) => set('name', e.target.value)} autoComplete="off" autoFocus={isNew} /></Field>
          <Field label="Gender" htmlFor="p-g">
            <select id="p-g" value={f.gender} onChange={(e) => set('gender', e.target.value)}>
              <option value="">—</option><option>Female</option><option>Male</option><option>Other</option>
            </select>
          </Field>
          <Field label="Age" htmlFor="p-age"><input id="p-age" inputMode="numeric" value={f.age} onChange={(e) => set('age', e.target.value)} /></Field>
          <PhoneInput label="Mobile (WhatsApp / SMS)" cc={settings.country} value={f.mobile} onChange={(v) => set('mobile', v)} />
          <Field label="Email" htmlFor="p-email"><input id="p-email" type="email" inputMode="email" value={f.email} onChange={(e) => set('email', e.target.value)} /></Field>
          <PhoneInput label="Alternative mobile" cc={settings.country} value={f.altMobile} onChange={(v) => set('altMobile', v)} />
          <Field label="Nationality" htmlFor="p-nat"><input id="p-nat" value={f.nationality} onChange={(e) => set('nationality', e.target.value)} /></Field>
          <Field label="Occupation" htmlFor="p-occ"><input id="p-occ" value={f.occupation} onChange={(e) => set('occupation', e.target.value)} /></Field>
          <Field label={cfg.patientIdLabel} htmlFor="p-id"><input id="p-id" value={f.idNumber} onChange={(e) => set('idNumber', e.target.value)} /></Field>
          <Field label="Address" span={2} htmlFor="p-addr"><input id="p-addr" value={f.address} onChange={(e) => set('address', e.target.value)} autoComplete="street-address" /></Field>
          <Field label="Emergency contact" htmlFor="p-en"><input id="p-en" value={f.emergencyName} onChange={(e) => set('emergencyName', e.target.value)} /></Field>
          <PhoneInput label="Emergency contact phone" cc={settings.country} value={f.emergencyPhone} onChange={(v) => set('emergencyPhone', v)} />
        </div>
      </fieldset>

      <fieldset className="fs"><legend>Health</legend>
        <div className="grid g3">
          <Field label="Main complaint" span="all" htmlFor="p-dis"><input id="p-dis" value={f.disease} onChange={(e) => set('disease', e.target.value)} placeholder="e.g. Lower back pain" /></Field>
          {settings.features.constitution && (
            <Field label="Constitution (prakriti)" span="all">
              <div className="chips">{DOSHAS.map((d) => (
                <label key={d} className={'chip-check' + (f.constitution.includes(d) ? ' on' : '')}>
                  <input type="checkbox" checked={f.constitution.includes(d)} onChange={(e) => set('constitution', e.target.checked ? [...f.constitution, d] : f.constitution.filter((x) => x !== d))} />{d}
                </label>))}</div>
            </Field>
          )}
          <Field label="Weight (kg)" htmlFor="p-wt"><input id="p-wt" inputMode="decimal" value={f.weight} onChange={(e) => set('weight', e.target.value)} /></Field>
          <Field label="Height (cm)" htmlFor="p-ht"><input id="p-ht" inputMode="decimal" value={f.height} onChange={(e) => set('height', e.target.value)} /></Field>
          <Field label="Blood pressure" htmlFor="p-bp"><input id="p-bp" value={f.bp} placeholder="120/80" onChange={(e) => set('bp', e.target.value)} /></Field>
          <Field label="Pulse (bpm)" htmlFor="p-pu"><input id="p-pu" inputMode="numeric" value={f.pulse} onChange={(e) => set('pulse', e.target.value)} /></Field>
          <Field label="Allergies" span={2} htmlFor="p-al"><input id="p-al" value={f.allergies} onChange={(e) => set('allergies', e.target.value)} placeholder="Drug, food or other allergies" /></Field>
          <Field label="Medical history" span="all" htmlFor="p-hist"><textarea id="p-hist" rows={3} value={f.history} onChange={(e) => set('history', e.target.value)} placeholder="Past illness, surgery, long-term conditions" /></Field>
          <Field label="Current medication" span={2} htmlFor="p-med"><textarea id="p-med" rows={2} value={f.medications} onChange={(e) => set('medications', e.target.value)} /></Field>
          <Field label="Lifestyle & diet" htmlFor="p-life"><textarea id="p-life" rows={2} value={f.lifestyle} onChange={(e) => set('lifestyle', e.target.value)} /></Field>
        </div>
      </fieldset>

      <fieldset className="fs"><legend>Reminders and consent</legend>
        <div className="checks">
          <Check checked={f.remindWhatsApp} onChange={(v) => set('remindWhatsApp', v)}>WhatsApp reminders</Check>
          <Check checked={f.remindSms} onChange={(v) => set('remindSms', v)}>SMS reminders</Check>
          <Check checked={f.remindEmail} onChange={(v) => set('remindEmail', v)}>Email reminders</Check>
        </div>
        <Check checked={f.consent} onChange={(v) => set('consent', v)}>{settings.consentText}</Check>
      </fieldset>
    </Modal>
  );
}
