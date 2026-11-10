import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { ROLE_HELP, ROLE_LABEL } from '../auth/permissions';
import { useSettings } from '../context/SettingsContext';
import { useToast } from '../context/ToastContext';
import { removeInvite, saveInvite, setUserAccess } from '../data/db';
import { useActivityLive, useInvitesLive, useUsersLive } from '../data/hooks';
import { normalizePhone } from '../lib/phone';
import { isEmail } from '../lib/validators';
import { isoToDate } from '../lib/dates';
import { Field, Notice, Pill, Spinner } from '../components/ui';
import type { Role } from '../types';

export default function Users() {
  const { state } = useAuth();
  const { settings, tz, locale } = useSettings();
  const toast = useToast();
  const users = useUsersLive(true), invites = useInvitesLive(true), log = useActivityLive(true);
  const [who, setWho] = useState(''); const [role, setRole] = useState<'doctor' | 'reception' | 'owner'>('reception'); const [note, setNote] = useState('');
  const [err, setErr] = useState('');
  if (state.kind !== 'ready') return null;
  const me = state.user.uid; const actor = { uid: me, name: state.profile.displayName };
  const act = async (fn: () => Promise<void>, ok: string) => { try { await fn(); toast(ok); } catch (e) { toast(e instanceof Error ? e.message : 'Failed', 'err'); } };

  const invite = async () => {
    setErr('');
    const v = who.trim(); let key = '';
    if (isEmail(v)) key = v.toLowerCase();
    else { const p = normalizePhone(v, settings.country); if (p.ok && p.e164) key = p.e164; else return setErr('Enter a valid email address or mobile number.'); }
    await act(async () => { await saveInvite(key, role, note, actor); setWho(''); setNote(''); }, `Invited ${key}`);
  };
  const list = users.data.filter((u) => u.status !== 'pending');
  const pending = users.data.filter((u) => u.status === 'pending');
  const roleSel = (u: (typeof list)[number]) => (
    <select aria-label={`Role for ${u.displayName}`} value={u.role} disabled={u.uid === me} onChange={(e) => void act(() => setUserAccess(u.uid, e.target.value as Role, u.status === 'pending' ? 'active' : u.status, actor), 'Role updated')}>
      {(['owner', 'doctor', 'reception'] as Role[]).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
    </select>);

  return (
    <>
      <div className="page-h"><div><h1>Team</h1><p className="muted">Who can sign in, and what they can do</p></div></div>
      {pending.length > 0 && (
        <section className="card section-gap"><div className="card-h"><h2>Waiting for approval ({pending.length})</h2></div><div className="card-b flush">
          {pending.map((u) => (
            <div className="list-row wrap" key={u.uid}><span className="grow"><b>{u.displayName}</b><small className="muted block">{u.email || u.phone}</small></span>
              <button className="btn sm primary" onClick={() => void act(() => setUserAccess(u.uid, 'reception', 'active', actor), 'Approved as front desk')}>Approve as front desk</button>
              <button className="btn sm" onClick={() => void act(() => setUserAccess(u.uid, 'doctor', 'active', actor), 'Approved as doctor')}>As doctor</button>
              <button className="btn sm danger-o" onClick={() => void act(() => setUserAccess(u.uid, 'none', 'disabled', actor), 'Request declined')}>Decline</button></div>))}
        </div></section>)}

      <section className="card section-gap"><div className="card-h"><h2>Invite someone</h2></div><div className="card-b">
        {err && <Notice kind="err">{err}</Notice>}
        <p className="muted small">They sign in with this email (Google or password) or this mobile number and get the role below automatically. Nothing is sent — tell them to open the app.</p>
        <div className="grid g4">
          <Field label="Email or mobile number" span={2} htmlFor="iv-w"><input id="iv-w" value={who} onChange={(e) => setWho(e.target.value)} /></Field>
          <Field label="Role" htmlFor="iv-r"><select id="iv-r" value={role} onChange={(e) => setRole(e.target.value as typeof role)}>{(['reception', 'doctor', 'owner'] as const).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select></Field>
          <Field label="Note (optional)" htmlFor="iv-n"><input id="iv-n" value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        </div>
        <p className="muted small">{ROLE_HELP[role]}</p>
        <button className="btn primary" onClick={() => void invite()}>Add invitation</button>
        {invites.data.length > 0 && <div className="invites">{invites.data.map((i) => (
          <span className="chip static" key={i.id}>{i.id} · {ROLE_LABEL[i.role]} <button aria-label={`Remove invitation for ${i.id}`} className="x" onClick={() => void act(() => removeInvite(i.id, actor), 'Invitation removed')}>×</button></span>))}</div>}
      </div></section>

      <section className="card section-gap"><div className="card-h"><h2>People with access</h2></div>
        {users.loading ? <Spinner /> : (
          <table className="tbl stack"><thead><tr><th>Name</th><th>Sign-in</th><th>Role</th><th>Status</th><th>Last sign-in</th><th aria-hidden="true" /></tr></thead>
            <tbody>{list.map((u) => (
              <tr key={u.uid}><td data-l="Name"><b>{u.displayName}</b>{u.uid === me && <span className="muted"> (you)</span>}</td><td data-l="Sign-in">{u.email || u.phone}</td>
                <td data-l="Role">{roleSel(u)}</td><td data-l="Status"><Pill kind={u.status}>{u.status}</Pill></td><td data-l="Last sign-in" className="muted">{isoToDate(u.lastLoginAt, tz, locale)}</td>
                <td className="row-actions">{u.uid !== me && (u.status === 'active'
                  ? <button className="btn sm danger-o" onClick={() => void act(() => setUserAccess(u.uid, u.role, 'disabled', actor), 'Access switched off')}>Switch off</button>
                  : <button className="btn sm" onClick={() => void act(() => setUserAccess(u.uid, u.role === 'none' ? 'reception' : u.role, 'active', actor), 'Access restored')}>Restore</button>)}</td></tr>))}</tbody></table>)}
      </section>

      <section className="card section-gap"><div className="card-h"><h2>Recent activity</h2></div><div className="card-b flush">
        {log.data.map((e) => <div className="list-row" key={e.id}><span className="t">{isoToDate(e.at, tz, locale)}</span><span className="grow"><b>{e.kind}</b> <span className="muted">{e.ref} {e.detail}</span></span><span className="muted small">{e.byName}</span></div>)}
        {!log.data.length && <p className="muted pad">Nothing yet.</p>}</div></section>
    </>
  );
}
