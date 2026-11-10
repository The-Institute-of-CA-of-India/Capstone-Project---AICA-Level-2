import { useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { can } from '../auth/permissions';
import { useSettings } from '../context/SettingsContext';
import { useData } from '../context/DataContext';
import { useToast } from '../context/ToastContext';
import { deletePatientFile, fileUrl, uploadPatientFile } from '../data/db';
import { useApptsForPatient, usePatientFiles, usePrescriptionsForPatient, useVisitsForPatient } from '../data/hooks';
import { isoToDate, time12 } from '../lib/dates';
import { showPhone, waDigits } from '../lib/phone';
import { toPublicClinic } from '../lib/publicView';
import { waLink } from '../lib/messaging';
import ApptForm from '../components/ApptForm';
import { DocModal, PrescriptionDoc } from '../components/Docs';
import InvoiceViewer, { PayModal } from '../components/InvoiceViewer';
import PatientForm from '../components/PatientForm';
import VisitForm from '../components/VisitForm';
import { ConfirmModal, Empty, Icon, Pill, Spinner } from '../components/ui';
import type { PatientFile, Prescription, Visit } from '../types';

const fmtSize = (n: number) => (n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB');

export default function PatientDetail() {
  const { id = '' } = useParams();
  const { state } = useAuth();
  const { settings, cfg, tz, locale, date, money } = useSettings();
  const { patientById, loading } = useData();
  const toast = useToast();
  const role = state.kind === 'ready' ? state.profile.role : undefined;
  const p = patientById(id);

  const visits = useVisitsForPatient(id);
  const appts = useApptsForPatient(id);
  const rxs = usePrescriptionsForPatient(id, settings.features.prescriptions);
  const files = usePatientFiles(id);

  const [edit, setEdit] = useState(false);
  const [visitFor, setVisitFor] = useState<{ visit?: Visit } | null>(null);
  const [viewInv, setViewInv] = useState<string | null>(null);
  const [pay, setPay] = useState<Visit | null>(null);
  const [book, setBook] = useState(false);
  const [rx, setRx] = useState<Prescription | null>(null);
  const [delFile, setDelFile] = useState<PatientFile | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const sorted = useMemo(() => [...visits.data].sort((a, b) => b.date.localeCompare(a.date) || b.createdAt.localeCompare(a.createdAt)), [visits.data]);
  const rxByVisit = useMemo(() => new Map(rxs.data.map((r) => [r.visitId, r])), [rxs.data]);
  const upcoming = useMemo(() => appts.data.filter((a) => a.status === 'Scheduled').sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time)), [appts.data]);

  if (loading) return <Spinner />;
  if (!p) return <div className="card"><Empty title="Health card not found" action={<Link className="btn" to="/patients">Back to patients</Link>} /></div>;

  const canWrite = can(role, 'patients.write');
  const totalBilled = sorted.filter((v) => !v.void).reduce((a, v) => a + v.total, 0);
  const totalDue = sorted.filter((v) => !v.void).reduce((a, v) => a + v.balance, 0);
  const latest = sorted.find((v) => v.weight || v.bp || v.pulse);
  const vitals = { weight: latest?.weight || p.weight, bp: latest?.bp || p.bp, pulse: latest?.pulse || p.pulse };
  const actor = state.kind === 'ready' ? { uid: state.user.uid, name: state.profile.displayName } : null;

  const upload = async (list: FileList | null) => {
    if (!list?.length || !actor) return;
    setUploading(true);
    try {
      for (const f of Array.from(list)) {
        if (f.size > 10 * 1024 * 1024) { toast(`${f.name} is larger than 10 MB.`, 'err'); continue; }
        if (!/^(image\/|application\/pdf)/.test(f.type)) { toast(`${f.name}: only images and PDFs can be uploaded.`, 'err'); continue; }
        await uploadPatientFile(p.id, f, actor);
      }
      toast('Upload complete');
    } catch (e) { toast(e instanceof Error ? e.message : 'Upload failed.', 'err'); }
    finally { setUploading(false); if (fileInput.current) fileInput.current.value = ''; }
  };
  const open = async (f: PatientFile) => { try { window.open(await fileUrl(f.path), '_blank', 'noopener'); } catch { toast('Could not open the file.', 'err'); } };

  const hf = (k: string, v: string, cls = '') => <div className={'hf ' + cls}><span className="k">{k}</span><span className={'v' + (v ? '' : ' empty-v')}>{v || '—'}</span></div>;

  return (
    <>
      <div className="page-h">
        <div><Link to="/patients" className="small back">← Patients</Link><h1>{p.name}</h1></div>
        <div className="actions">
          {p.mobile && <a className="btn" href={waLink(waDigits(p.mobile), '')} target="_blank" rel="noopener noreferrer"><Icon n="whatsapp" size={16} />WhatsApp</a>}
          {p.mobile && <a className="btn" href={`tel:${p.mobile}`}><Icon n="phone" size={16} />Call</a>}
          {canWrite && <button className="btn" onClick={() => setEdit(true)}><Icon n="edit" size={16} />Edit</button>}
          {canWrite && <button className="btn" onClick={() => setBook(true)}><Icon n="calendar" size={16} />Book</button>}
          {can(role, 'billing.write') && <button className="btn primary" onClick={() => setVisitFor({})}><Icon n="plus" size={16} />New visit</button>}
        </div>
      </div>

      <div className="detail-grid">
        <section className="hcard" aria-label="Health card">
          <div className="hcard-top">
            <div className="org">{settings.clinicName}<small>Health card</small></div>
            <div className="fn"><small>File no.</small><b>{p.id}</b></div>
          </div>
          <div className="hgrid">
            {hf('Name', p.name, 'c8')}{hf('Age', p.age, 'c2')}{hf('Sex', p.gender, 'c2')}
            {hf('Mobile', showPhone(p.mobile, settings.country), 'c5')}{hf('Email', p.email, 'c7')}
            {hf('Address', p.address, 'c12')}
            {hf('Occupation', p.occupation, 'c6')}{hf('Nationality', p.nationality, 'c6')}
            {hf('Main complaint', p.disease, 'c12')}
            {settings.features.constitution && <div className="hf c12"><span className="k">Constitution</span>
              <span className="dosha">{['Vata', 'Pitta', 'Kapha'].map((d) => <span key={d} className={p.constitution?.includes(d) ? 'on' : ''}>{d}</span>)}</span></div>}
            {hf('Weight', vitals.weight ? vitals.weight + ' kg' : '', 'c4')}{hf('BP', vitals.bp, 'c4')}{hf('Pulse', vitals.pulse, 'c4')}
            {p.allergies && <div className="hf c12"><span className="alert-chip"><Icon n="alert" size={14} />Allergies: {p.allergies}</span></div>}
          </div>
        </section>

        <aside className="card">
          <div className="card-h"><h2>Summary</h2></div>
          <div className="card-b">
            <dl className="facts">
              <div><dt>Visits</dt><dd>{sorted.filter((v) => !v.void).length}</dd></div>
              <div><dt>Total billed</dt><dd className="money">{money(totalBilled)}</dd></div>
              <div><dt>Balance due</dt><dd className={'money' + (totalDue > 0.005 ? ' neg' : '')}>{money(totalDue)}</dd></div>
              <div><dt>Registered</dt><dd>{isoToDate(p.createdAt, tz, locale)}</dd></div>
              <div><dt>Consent</dt><dd>{p.consent ? 'Given ' + isoToDate(p.consentAt || p.createdAt, tz, locale) : <span className="neg">Not recorded</span>}</dd></div>
            </dl>
            {upcoming.length > 0 && <div className="next-appt"><b>Next appointment</b><div>{date(upcoming[0].date)} at {time12(upcoming[0].time)}</div></div>}
          </div>
        </aside>
      </div>

      <section className="card section-gap">
        <div className="card-h"><h2>Medical background</h2></div>
        <div className="card-b">
          {[['Medical history', p.history], ['Current medication', p.medications], ['Lifestyle & diet', p.lifestyle], ['Height', p.height ? p.height + ' cm' : ''],
            [cfg.patientIdLabel.replace(' (optional)', ''), p.idNumber], ['Emergency contact', [p.emergencyName, showPhone(p.emergencyPhone, settings.country)].filter(Boolean).join(' · ')]]
            .filter(([, v]) => v).map(([k, v]) => <div className="bg-row" key={k}><div className="lbl">{k}</div><div className="pre">{v}</div></div>)}
          {!p.history && !p.medications && !p.lifestyle && <p className="muted">Nothing recorded yet. Use Edit to add history and medication.</p>}
        </div>
      </section>

      <section className="card section-gap">
        <div className="card-h"><h2>Visit history</h2>
          {can(role, 'billing.write') && <button className="btn sm primary" onClick={() => setVisitFor({})}><Icon n="plus" size={15} />New visit</button>}</div>
        {visits.loading ? <Spinner /> : sorted.length === 0 ? (
          <Empty title="No visits yet" action={can(role, 'billing.write') ? <button className="btn primary" onClick={() => setVisitFor({})}>Record today’s visit</button> : undefined}>Record the first visit to start the history and raise the first invoice.</Empty>
        ) : (
          <table className="tbl stack">
            <thead><tr><th>Date</th><th>Visit</th><th className="r">Total</th><th>Status</th><th aria-hidden="true" /></tr></thead>
            <tbody>
              {sorted.map((v) => {
                const r = rxByVisit.get(v.id);
                return (
                  <tr key={v.id} className={v.void ? 'void' : ''}>
                    <td data-l="Date" className="nw">{date(v.date)}<div className="small muted">{v.invoiceNo}</div></td>
                    <td data-l="Visit" className="notes-cell">
                      <div>{v.lines.map((l) => l.name + (l.qty !== 1 ? ' ×' + l.qty : '')).join(', ') || <span className="muted">No charges</span>}</div>
                      {v.complaint && <div className="small"><b>Complaint:</b> {v.complaint}</div>}
                      {v.notes && <div className="small pre">{v.notes}</div>}
                      {v.advice && <div className="small"><b>Advice:</b> {v.advice}</div>}
                      {(v.weight || v.bp || v.pulse || v.temp || v.spo2) && <div className="small muted">{[v.weight && v.weight + ' kg', v.bp && 'BP ' + v.bp, v.pulse && 'pulse ' + v.pulse, v.temp && v.temp + ' °C', v.spo2 && 'SpO₂ ' + v.spo2 + '%'].filter(Boolean).join(' · ')}</div>}
                    </td>
                    <td data-l="Total" className="r nw money">{money(v.total, v.currency)}{v.balance > 0.005 && !v.void && <div className="small neg">due {money(v.balance, v.currency)}</div>}</td>
                    <td data-l="Status"><Pill kind={v.status}>{v.status}</Pill></td>
                    <td className="row-actions">
                      <button className="btn sm" onClick={() => setViewInv(v.id)}>Invoice</button>
                      {!v.void && v.balance > 0.005 && can(role, 'billing.write') && <button className="btn sm" onClick={() => setPay(v)}>Pay</button>}
                      {r && <button className="btn sm" onClick={() => setRx(r)}><Icon n="pill" size={14} />Rx</button>}
                      {can(role, 'billing.write') && (!v.void || role === 'owner') && <button className="btn sm" onClick={() => setVisitFor({ visit: v })}>Edit</button>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <div className="grid-2 section-gap">
        <section className="card">
          <div className="card-h"><h2>Appointments</h2>{canWrite && <button className="btn sm" onClick={() => setBook(true)}><Icon n="plus" size={15} />Book</button>}</div>
          <div className="card-b flush">
            {[...appts.data].sort((a, b) => (b.date + b.time).localeCompare(a.date + a.time)).slice(0, 8).map((a) => (
              <div className="list-row" key={a.id}><span className="t">{date(a.date)}</span><span className="grow">{time12(a.time)} · {a.service || 'Appointment'}</span><Pill kind={a.status}>{a.status}</Pill></div>
            ))}
            {!appts.data.length && <Empty title="No appointments" />}
          </div>
        </section>

        <section className="card">
          <div className="card-h"><h2>Documents</h2>
            {canWrite && <>
              <input ref={fileInput} type="file" accept="image/*,application/pdf" multiple hidden onChange={(e) => void upload(e.target.files)} />
              <button className="btn sm" disabled={uploading} onClick={() => fileInput.current?.click()}><Icon n="upload" size={15} />{uploading ? 'Uploading…' : 'Upload'}</button></>}
          </div>
          <div className="card-b flush">
            {[...files.data].sort((a, b) => b.uploadedAt.localeCompare(a.uploadedAt)).map((f) => (
              <div className="list-row" key={f.id}>
                <Icon n="file" /><span className="grow"><button className="link" onClick={() => void open(f)}>{f.name}</button><small className="muted block">{fmtSize(f.size)} · {isoToDate(f.uploadedAt, tz, locale)}</small></span>
                {can(role, 'files.delete') && <button className="icon-btn" aria-label={`Delete ${f.name}`} onClick={() => setDelFile(f)}><Icon n="trash" size={16} /></button>}
              </div>
            ))}
            {!files.data.length && <Empty title="No documents">Lab reports, scans or referral letters (images or PDF, up to 10 MB).</Empty>}
          </div>
        </section>
      </div>

      {edit && <PatientForm patient={p} onClose={() => setEdit(false)} onSaved={() => setEdit(false)} />}
      {visitFor && <VisitForm patient={p} visit={visitFor.visit} onClose={() => setVisitFor(null)} onSaved={(v) => { setVisitFor(null); setViewInv(v.id); }} />}
      {viewInv && <InvoiceViewer visitId={viewInv} onClose={() => setViewInv(null)} />}
      {pay && <PayModal visit={pay} onClose={() => setPay(null)} />}
      {book && <ApptForm patientId={p.id} onClose={() => setBook(false)} onSaved={() => setBook(false)} />}
      {rx && <DocModal title="Prescription" onClose={() => setRx(null)} doc={<PrescriptionDoc clinic={toPublicClinic(settings)} rx={rx} regLabel={cfg.registration.practitioner} />} />}
      {delFile && actor && <ConfirmModal danger title="Delete this document?" confirmLabel="Delete" body={<>“{delFile.name}” will be permanently removed.</>}
        onClose={() => setDelFile(null)} onConfirm={async () => { await deletePatientFile(p.id, delFile, actor); setDelFile(null); toast('Document deleted'); }} />}
    </>
  );
}
