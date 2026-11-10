import { useEffect, useState } from 'react';
import { authErrorMessage, useAuth } from '../auth/AuthContext';
import { COUNTRY_LIST } from '../config/countries';
import { missingConfig } from '../firebase/config';
import { useProfileDoc } from '../data/hooks';
import { Check, Field, Notice } from '../components/ui';
import type { CountryCode } from '../types';

const LOGO = import.meta.env.BASE_URL + 'icons/logo.png';

function Panel({ children, wide }: { children: React.ReactNode; wide?: boolean }) {
  return (
    <div className="gate">
      <main className={'gate-card' + (wide ? ' wide' : '')} id="main">
        <img className="gate-logo" src={LOGO} alt="" />
        {children}
      </main>
    </div>
  );
}

export function SetupRequired() {
  return (
    <Panel wide>
      <h1>One more step: connect your Firebase project</h1>
      <p className="lead">This app stores its data in <b>your own</b> Firebase project. It does not contain anyone else’s keys. The following settings are missing:</p>
      <ul className="code-list">{missingConfig.map((m) => <li key={m}><code>{m}</code></li>)}</ul>
      <ol className="steps">
        <li>In the Firebase console, open <b>Project settings → Your apps → Web app</b> and copy the configuration values.</li>
        <li>Put them in a file named <code>.env.local</code> (see <code>.env.example</code>), <i>or</i> in <code>src/config/firebase.config.json</code> (see the example file next to it).</li>
        <li>Restart the dev server (or rebuild), then reload this page.</li>
      </ol>
      <p className="muted small">Full instructions are in README.md, step 4.</p>
    </Panel>
  );
}

export function VerifyEmail({ email }: { email: string }) {
  const { sendVerification, recheck, signOut } = useAuth();
  const [msg, setMsg] = useState(''); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const act = async (fn: () => Promise<void>, ok: string) => {
    setErr(''); setMsg(''); setBusy(true);
    try { await fn(); setMsg(ok); } catch (e) { setErr(authErrorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Panel>
      <h1>Check your email</h1>
      <p className="lead">We sent a verification link to <b>{email}</b>. Open it, then come back and press the button below.</p>
      {err && <Notice kind="err">{err}</Notice>}
      {msg && <Notice kind="ok">{msg}</Notice>}
      <div className="stack">
        <button className="btn primary block" disabled={busy} onClick={() => void act(async () => { await recheck(); }, '')}>I’ve verified my email</button>
        <button className="btn block" disabled={busy} onClick={() => void act(sendVerification, 'Verification email sent again.')}>Send the email again</button>
        <button className="link small" onClick={() => void signOut()}>Use a different account</button>
      </div>
    </Panel>
  );
}

export function FirstRun({ defaultName }: { defaultName: string }) {
  const { completeFirstRun, signOut } = useAuth();
  const [cc, setCc] = useState<CountryCode | ''>('');
  const [clinic, setClinic] = useState('');
  const [sample, setSample] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const go = async () => {
    if (!cc) return setErr('Choose the country the clinic operates in.');
    if (!clinic.trim()) return setErr('Enter the clinic’s name.');
    setErr(''); setBusy(true);
    try { await completeFirstRun(cc, clinic, sample); }
    catch (e) { setErr(authErrorMessage(e)); setBusy(false); }
  };

  return (
    <Panel wide>
      <h1>Set up your clinic</h1>
      <p className="lead">Welcome{defaultName ? `, ${defaultName.split(' ')[0]}` : ''}. You are the first person to sign in, so you will be the <b>owner</b> of this system. You can change everything later in Settings.</p>
      {err && <Notice kind="err">{err}</Notice>}
      <fieldset className="country-pick">
        <legend>Where is the clinic?</legend>
        {COUNTRY_LIST.map((c) => (
          <label key={c.code} className={'country-card' + (cc === c.code ? ' on' : '')}>
            <input type="radio" name="cc" value={c.code} checked={cc === c.code} onChange={() => setCc(c.code)} />
            <b>{c.name}</b>
            <span>{c.currency} · {c.tax.label} · +{c.dialCode}</span>
          </label>
        ))}
      </fieldset>
      <Field label="Clinic name" htmlFor="fr-name" hint="Shown in the header, invoices, receipts and reports.">
        <input id="fr-name" value={clinic} onChange={(e) => setClinic(e.target.value)} autoComplete="organization" />
      </Field>
      <Check checked={sample} onChange={setSample}>Add a few sample services so I can try billing (I’ll set real prices later)</Check>
      <Notice kind="warn">Tax and regulatory settings come with sensible starting defaults for the chosen country (tax starts switched <b>off</b>). They are not legal or tax advice — have a qualified professional review them.</Notice>
      <div className="row-end">
        <button className="link small" onClick={() => void signOut()}>Cancel and sign out</button>
        <button className="btn primary" disabled={busy} onClick={() => void go()}>Create my clinic</button>
      </div>
    </Panel>
  );
}

export function Pending({ uid, name }: { uid: string; name: string }) {
  const { signOut, recheck } = useAuth();
  const live = useProfileDoc(uid);
  useEffect(() => { if (live && live.status === 'active' && live.role !== 'none') void recheck(); }, [live, recheck]);
  return (
    <Panel>
      <h1>Waiting for approval</h1>
      <p className="lead">Hello{name ? `, ${name}` : ''}. Your access request has been sent to the clinic owner. This page will continue by itself as soon as you are approved.</p>
      <Notice>Tell the owner which sign-in you used (your email or mobile number) so they can approve the right request under <b>Team</b>.</Notice>
      <button className="btn block" onClick={() => void signOut()}>Sign out</button>
    </Panel>
  );
}

export function Disabled() {
  const { signOut } = useAuth();
  return (
    <Panel>
      <h1>Access switched off</h1>
      <p className="lead">The clinic owner has disabled this account. If you think this is a mistake, please contact them.</p>
      <button className="btn block" onClick={() => void signOut()}>Sign out</button>
    </Panel>
  );
}

export function ErrorScreen({ message }: { message: string }) {
  const { signOut, recheck } = useAuth();
  return (
    <Panel>
      <h1>We couldn’t load your account</h1>
      <Notice kind="err">{message}</Notice>
      <p className="muted small">If this keeps happening, check that the Firestore rules in this repository have been published to your Firebase project (README step 7).</p>
      <div className="stack">
        <button className="btn primary block" onClick={() => void recheck().catch(() => window.location.reload())}>Try again</button>
        <button className="link small" onClick={() => void signOut()}>Sign out</button>
      </div>
    </Panel>
  );
}
