import { useMemo, useState } from 'react';
import { useData } from '../context/DataContext';
import { Field } from './ui';

/** Type-ahead patient chooser (used when booking an appointment or starting a visit). */
export default function PatientPicker({ value, onChange, label = 'Patient', autoFocus }: {
  value: string; onChange: (id: string) => void; label?: string; autoFocus?: boolean;
}) {
  const { patients, patientById } = useData();
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const chosen = value ? patientById(value) : undefined;
  const results = useMemo(() => {
    const s = q.trim().toLowerCase(); if (s.length < 1) return patients.slice(0, 6);
    const d = s.replace(/\D/g, '');
    return patients.filter((p) => p.name.toLowerCase().includes(s) || p.id.toLowerCase().includes(s) || (d.length >= 3 && (p.mobile || '').replace(/\D/g, '').includes(d))).slice(0, 8);
  }, [q, patients]);

  if (chosen && !open) {
    return (
      <Field label={label}>
        <div className="picked">
          <span><b>{chosen.name}</b> <span className="fileno">{chosen.id}</span></span>
          <button type="button" className="link small" onClick={() => { onChange(''); setQ(''); setOpen(true); }}>Change</button>
        </div>
      </Field>
    );
  }
  return (
    <Field label={label} htmlFor="pp-q" hint="Start typing a name, file number or phone number">
      <div className="picker">
        <input id="pp-q" value={q} autoFocus={autoFocus} autoComplete="off" onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} />
        {open && (
          <div className="qresults inline">
            {results.map((p) => (
              <button type="button" key={p.id} onClick={() => { onChange(p.id); setOpen(false); setQ(''); }}>
                <span className="fn">{p.id}</span><span className="nm">{p.name}</span><span className="ph">{p.mobile}</span>
              </button>
            ))}
            {!results.length && <div className="none">No matching patient.</div>}
          </div>
        )}
      </div>
    </Field>
  );
}
