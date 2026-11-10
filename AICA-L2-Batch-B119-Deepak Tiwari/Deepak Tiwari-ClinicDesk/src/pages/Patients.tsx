import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { can } from '../auth/permissions';
import { useAuth } from '../auth/AuthContext';
import { useData } from '../context/DataContext';
import { useSettings } from '../context/SettingsContext';
import PatientForm from '../components/PatientForm';
import { Empty, Icon, Spinner } from '../components/ui';
import { showPhone } from '../lib/phone';
import { isoToDate } from '../lib/dates';

const PAGE = 50;

export default function Patients() {
  const { state } = useAuth();
  const { patients, loading, error } = useData();
  const { settings, tz, locale } = useSettings();
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState('');
  const [limit, setLimit] = useState(PAGE);
  const [showForm, setShowForm] = useState(false);
  const [seedName, setSeedName] = useState('');
  const role = state.kind === 'ready' ? state.profile.role : undefined;

  useEffect(() => {
    if (sp.get('new') === '1') { setSeedName(sp.get('name') || ''); setShowForm(true); setSp({}, { replace: true }); }
  }, [sp, setSp]);

  const list = useMemo(() => {
    const s = q.trim().toLowerCase(); const d = s.replace(/\D/g, '');
    return (s ? patients.filter((p) => p.name.toLowerCase().includes(s) || p.id.toLowerCase().includes(s) || (p.email || '').includes(s) || (d.length >= 3 && [p.mobile, p.altMobile].some((m) => (m || '').replace(/\D/g, '').includes(d)))) : patients);
  }, [patients, q]);

  return (
    <>
      <div className="page-h">
        <div><h1>Patients</h1><p className="muted">{patients.length} health card{patients.length === 1 ? '' : 's'}</p></div>
        {can(role, 'patients.write') && <button className="btn primary" onClick={() => { setSeedName(''); setShowForm(true); }}><Icon n="plus" size={17} />New health card</button>}
      </div>

      <div className="toolbar">
        <div className="search"><Icon n="search" size={17} />
          <input value={q} onChange={(e) => { setQ(e.target.value); setLimit(PAGE); }} placeholder="Search by name, file no., phone or email" aria-label="Search patients" /></div>
      </div>

      {error && <div className="notice err">{error}</div>}
      {loading ? <Spinner /> : !list.length ? (
        <div className="card"><Empty title={q ? 'No patient matches your search' : 'No patients yet'}>{q ? 'Try fewer letters, or create a new health card.' : 'Create the first health card to get started.'}</Empty></div>
      ) : (
        <div className="card">
          <table className="tbl stack">
            <thead><tr><th>File no.</th><th>Name</th><th>Mobile</th><th>Email</th><th>Registered</th><th aria-hidden="true" /></tr></thead>
            <tbody>
              {list.slice(0, limit).map((p) => (
                <tr key={p.id} className="click" tabIndex={0} onClick={() => nav('/patient/' + encodeURIComponent(p.id))}
                  onKeyDown={(e) => { if (e.key === 'Enter') nav('/patient/' + encodeURIComponent(p.id)); }}>
                  <td data-l="File no." className="fileno">{p.id}</td>
                  <td data-l="Name"><b>{p.name}</b>{p.allergies && <span className="alert-chip sm" title={p.allergies}>Allergy</span>}</td>
                  <td data-l="Mobile">{showPhone(p.mobile, settings.country)}</td>
                  <td data-l="Email" className="muted">{p.email}</td>
                  <td data-l="Registered" className="muted">{isoToDate(p.createdAt, tz, locale)}</td>
                  <td className="chev"><Icon n="chev" size={16} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {list.length > limit && <div className="card-f center"><button className="btn" onClick={() => setLimit(limit + PAGE)}>Show more ({list.length - limit} left)</button></div>}
        </div>
      )}

      {showForm && <PatientForm initialName={seedName} onClose={() => setShowForm(false)} onSaved={(p) => { setShowForm(false); nav('/patient/' + encodeURIComponent(p.id)); }} />}
    </>
  );
}
