import { useRef, useState, type FormEvent } from 'react';
import { authErrorMessage, useAuth } from '../auth/AuthContext';
import { COUNTRY_LIST, country } from '../config/countries';
import { normalizePhone } from '../lib/phone';
import { isEmail } from '../lib/validators';
import { GoogleG, Icon, Notice, Seg } from '../components/ui';
import type { CountryCode } from '../types';

const DEFAULT_LOGO = import.meta.env.BASE_URL + 'icons/logo.png';

function guessCountry(): CountryCode {
  try {
    const saved = localStorage.getItem('cd.cc');
    if (saved === 'KE' || saved === 'IN') return saved;
  } catch { /* storage may be blocked */ }
  return /-IN$/i.test(navigator.language) || /Kolkata|Calcutta/i.test(Intl.DateTimeFormat().resolvedOptions().timeZone) ? 'IN' : 'KE';
}

export default function Login() {
  const auth = useAuth();
  const [mode, setMode] = useState<'email' | 'phone'>('email');
  const [err, setErr] = useState('');
  const [info, setInfo] = useState('');
  const [busy, setBusy] = useState(false);

  // email
  const [signup, setSignup] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');

  // phone
  const [cc, setCc] = useState<CountryCode>(guessCountry);
  const [num, setNum] = useState('');
  const [code, setCode] = useState('');
  const [sent, setSent] = useState('');
  const captcha = useRef<HTMLDivElement>(null);

  const run = async (fn: () => Promise<void>) => {
    setErr(''); setInfo(''); setBusy(true);
    try { await fn(); } catch (e) { setErr(authErrorMessage(e)); } finally { setBusy(false); }
  };

  const submitEmail = (e: FormEvent) => {
    e.preventDefault();
    if (!isEmail(email)) return setErr('Enter a valid email address.');
    if (signup && !name.trim()) return setErr('Enter your name.');
    if (pw.length < 8) return setErr('Use a password of at least 8 characters.');
    void run(async () => {
      if (signup) { await auth.signUpEmail(name, email, pw); }
      else await auth.signInEmail(email, pw);
    });
  };
  const forgot = () => {
    if (!isEmail(email)) return setErr('Type your email address above first, then press "Forgot password".');
    void run(async () => { await auth.resetPassword(email); setInfo('If an account exists for that address, a reset link is on its way.'); });
  };

  const sendCode = (e: FormEvent) => {
    e.preventDefault();
    const r = normalizePhone(num, cc);
    if (!r.ok) return setErr(r.error);
    if (!r.e164) return setErr('Enter your mobile number.');
    try { localStorage.setItem('cd.cc', cc); } catch { /* ignore */ }
    void run(async () => { await auth.startPhone(r.e164, captcha.current!); setSent(r.display); setCode(''); });
  };
  const confirm = (e: FormEvent) => {
    e.preventDefault();
    if (!/^\d{6}$/.test(code.trim())) return setErr('Enter the 6-digit code from the SMS.');
    void run(async () => { await auth.confirmPhone(code); });
  };

  return (
    <div className="login">
      <section className="login-art" aria-hidden="true">
        <div className="art-tile"><img src={DEFAULT_LOGO} alt="" /></div>
        <h2>Patients, visits and billing — calmly in one place.</h2>
        <p>Works on your phone, tablet or computer. Your clinic’s records stay in your own Firebase project.</p>
      </section>

      <main className="login-card" id="main">
        <div className="login-brand"><img src={DEFAULT_LOGO} alt="" /><span>Clinic sign-in</span></div>
        <h1>Welcome back</h1>
        <p className="lead">Sign in to manage your clinic.</p>

        {err && <Notice kind="err">{err}</Notice>}
        {info && <Notice kind="ok">{info}</Notice>}

        <button className="btn google" disabled={busy} onClick={() => void run(auth.signInGoogle)}>
          <GoogleG /> Continue with Google
        </button>

        <div className="or"><span>or</span></div>

        <Seg label="Sign-in method" value={mode} onChange={(m) => { setMode(m); setErr(''); setInfo(''); }}
          options={[{ v: 'email', l: 'Email' }, { v: 'phone', l: 'Mobile number' }]} />

        {mode === 'email' ? (
          <form onSubmit={submitEmail} className="stack" noValidate>
            {signup && (
              <div className="field"><label htmlFor="lg-name">Your name</label>
                <input id="lg-name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></div>
            )}
            <div className="field"><label htmlFor="lg-email">Email address</label>
              <input id="lg-email" type="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></div>
            <div className="field"><label htmlFor="lg-pw">Password</label>
              <input id="lg-pw" type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete={signup ? 'new-password' : 'current-password'} /></div>
            <button className="btn primary block" disabled={busy}>{signup ? 'Create account' : 'Sign in'}</button>
            <div className="row-between small">
              <button type="button" className="link" onClick={() => { setSignup(!signup); setErr(''); }}>{signup ? 'I already have an account' : 'Create an account'}</button>
              {!signup && <button type="button" className="link" onClick={forgot}>Forgot password?</button>}
            </div>
          </form>
        ) : !sent ? (
          <form onSubmit={sendCode} className="stack" noValidate>
            <div className="field"><label htmlFor="lg-cc">Country</label>
              <select id="lg-cc" value={cc} onChange={(e) => setCc(e.target.value as CountryCode)}>
                {COUNTRY_LIST.map((c) => <option key={c.code} value={c.code}>{c.name} (+{c.dialCode})</option>)}
              </select></div>
            <div className="field"><label htmlFor="lg-num">Mobile number</label>
              <input id="lg-num" type="tel" inputMode="tel" value={num} onChange={(e) => setNum(e.target.value)} placeholder={country(cc).phone.example} autoComplete="tel" />
              <div className="hint">We’ll text you a 6-digit code. Standard SMS rates may apply.</div></div>
            <button className="btn primary block" disabled={busy}><Icon n="sms" size={17} /> Send code</button>
          </form>
        ) : (
          <form onSubmit={confirm} className="stack" noValidate>
            <Notice>Code sent to <b>{sent}</b>.</Notice>
            <div className="field"><label htmlFor="lg-code">6-digit code</label>
              <input id="lg-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} className="otp" /></div>
            <button className="btn primary block" disabled={busy}>Verify and sign in</button>
            <button type="button" className="link small" onClick={() => { setSent(''); setErr(''); }}>Use a different number</button>
          </form>
        )}
        <div ref={captcha} className="captcha-holder" />

        <p className="fine-print">
          By signing in you agree to use patient information only for care and billing. Access is limited to people the clinic owner has approved.
        </p>
      </main>
    </div>
  );
}
