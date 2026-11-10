import { useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { can, ROLE_LABEL, type Perm } from '../auth/permissions';
import { useSettings } from '../context/SettingsContext';
import { useData } from '../context/DataContext';
import { useInstall } from '../lib/pwa';
import { Icon, Modal, initials } from './ui';

export const DEFAULT_LOGO = import.meta.env.BASE_URL + 'icons/logo.png';

export function BrandMark({ size = 40 }: { size?: number }) {
  const { settings } = useSettings();
  return (
    <span className="brand-mark" style={{ width: size, height: size }}>
      <img src={settings.logoUrl || DEFAULT_LOGO} alt="" onError={(e) => { (e.target as HTMLImageElement).src = DEFAULT_LOGO; }} />
    </span>
  );
}

interface NavItem { to: string; label: string; icon: string; perm?: Perm; mobile?: boolean }
const NAV: NavItem[] = [
  { to: '/', label: 'Home', icon: 'home', mobile: true },
  { to: '/patients', label: 'Patients', icon: 'users', mobile: true },
  { to: '/appointments', label: 'Appointments', icon: 'calendar', mobile: true },
  { to: '/billing', label: 'Billing', icon: 'receipt', mobile: true },
  { to: '/services', label: 'Services & prices', icon: 'tag' },
  { to: '/reports', label: 'Reports', icon: 'chart', perm: 'reports' },
  { to: '/users', label: 'Team', icon: 'shield', perm: 'users' },
  { to: '/settings', label: 'Settings', icon: 'settings', perm: 'settings' }
];

function QuickSearch({ onPick }: { onPick?: () => void }) {
  const { patients } = useData();
  const { cfg } = useSettings();
  const nav = useNavigate();
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(t.tagName) && !t.isContentEditable) { e.preventDefault(); input.current?.focus(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const results = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (s.length < 2) return [];
    const digits = s.replace(/\D/g, '');
    return patients.filter((p) =>
      p.name.toLowerCase().includes(s) || p.id.toLowerCase().includes(s) || (p.email || '').includes(s) ||
      (digits.length >= 4 && [p.mobile, p.altMobile].some((m) => (m || '').replace(/\D/g, '').includes(digits)))
    ).slice(0, 8);
  }, [q, patients]);

  const pick = (id: string) => { setQ(''); setOpen(false); input.current?.blur(); nav('/patient/' + encodeURIComponent(id)); onPick?.(); };

  return (
    <div className="qsearch" role="search">
      <Icon n="search" size={17} />
      <input ref={input} value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)} placeholder="Find a patient — name, file no. or phone" aria-label="Find a patient"
        autoComplete="off" onKeyDown={(e) => { if (e.key === 'Enter' && results[0]) pick(results[0].id); if (e.key === 'Escape') { setQ(''); input.current?.blur(); } }} />
      <kbd className="kbd" aria-hidden="true">/</kbd>
      {open && q.trim().length >= 2 && (
        <div className="qresults">
          {results.length ? results.map((p) => (
            <button key={p.id} onMouseDown={(e) => e.preventDefault()} onClick={() => pick(p.id)}>
              <span className="fn">{p.id}</span><span className="nm">{p.name}</span>
              <span className="ph">{p.mobile || p.email}</span>
            </button>
          )) : <div className="none">No match. <button onMouseDown={(e) => e.preventDefault()} onClick={() => { setOpen(false); nav('/patients?new=1&name=' + encodeURIComponent(q.trim())); }}>Create a new health card</button></div>}
        </div>
      )}
      <span className="sr-only">{cfg.name}</span>
    </div>
  );
}

export default function Layout() {
  const { state, signOut } = useAuth();
  const { settings } = useSettings();
  const inst = useInstall();
  const loc = useLocation();
  const [more, setMore] = useState(false);
  const [iosHelp, setIosHelp] = useState(false);
  const role = state.kind === 'ready' ? state.profile.role : undefined;
  const name = state.kind === 'ready' ? state.profile.displayName : '';
  const items = NAV.filter((n) => !n.perm || can(role, n.perm));
  const mobileMain = items.filter((n) => n.mobile);
  const mobileMore = items.filter((n) => !n.mobile);

  useEffect(() => { setMore(false); window.scrollTo(0, 0); }, [loc.pathname]);

  return (
    <div className="shell">
      <a className="skip" href="#main">Skip to content</a>
      <aside className="side" aria-label="Main navigation">
        <div className="side-brand">
          <BrandMark size={46} />
          <div className="side-name"><b>{settings.clinicName}</b>{settings.tagline && <small>{settings.tagline}</small>}</div>
        </div>
        <nav className="nav">
          {items.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} title={n.label} className={({ isActive }) => (isActive ? 'on' : '')}>
              <Icon n={n.icon} /><span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="side-foot">
          {!inst.installed && (inst.canPrompt || inst.showIosHint) && (
            <button className="btn ghost-light sm" onClick={() => (inst.canPrompt ? void inst.install() : setIosHelp(true))} title="Install app">
              <Icon n="download" size={16} /><span>Install app</span>
            </button>
          )}
          <div className="who" title={`${name} (${role ? ROLE_LABEL[role] : ''})`}>
            <span className="avatar">{initials(name)}</span>
            <span className="who-t"><b>{name}</b><small>{role ? ROLE_LABEL[role] : ''}</small></span>
            <button className="icon-btn light" onClick={() => void signOut()} aria-label="Sign out" title="Sign out"><Icon n="logout" size={17} /></button>
          </div>
        </div>
      </aside>

      <div className="main-col">
        <header className="top">
          <span className="top-brand"><BrandMark size={34} /><b>{settings.clinicName}</b></span>
          <QuickSearch />
          <button className="icon-btn top-user" onClick={() => setMore(true)} aria-label="Menu"><span className="avatar sm">{initials(name)}</span></button>
        </header>
        <main id="main" className="content" tabIndex={-1}><Outlet /></main>
      </div>

      <nav className="tabbar" aria-label="Main">
        {mobileMain.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.to === '/'} className={({ isActive }) => (isActive ? 'on' : '')}>
            <Icon n={n.icon} size={22} /><span>{n.label === 'Appointments' ? 'Appts' : n.label}</span>
          </NavLink>
        ))}
        <button onClick={() => setMore(true)} className={more ? 'on' : ''}><Icon n="more" size={22} /><span>More</span></button>
      </nav>

      {more && (
        <Modal title={name || 'Menu'} sub={role ? ROLE_LABEL[role] : ''} onClose={() => setMore(false)}>
          <div className="menu-list">
            {mobileMore.map((n) => <NavLink key={n.to} to={n.to} onClick={() => setMore(false)}><Icon n={n.icon} />{n.label}</NavLink>)}
            {!inst.installed && inst.canPrompt && <button onClick={() => { void inst.install(); setMore(false); }}><Icon n="download" />Install app</button>}
            {!inst.installed && !inst.canPrompt && inst.showIosHint && <button onClick={() => { setMore(false); setIosHelp(true); }}><Icon n="download" />Add to Home Screen</button>}
            <button onClick={() => void signOut()}><Icon n="logout" />Sign out</button>
          </div>
        </Modal>
      )}
      {iosHelp && (
        <Modal title="Add to Home Screen" onClose={() => setIosHelp(false)}>
          <p>On iPhone or iPad, open this page in <b>Safari</b>, tap the <b>Share</b> button, then choose <b>Add to Home Screen</b>. The app will open full-screen like any other app.</p>
        </Modal>
      )}
    </div>
  );
}
