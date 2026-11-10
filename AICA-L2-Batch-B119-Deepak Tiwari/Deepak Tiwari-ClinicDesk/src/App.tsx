import { lazy, Suspense, useEffect, useRef } from 'react';
import { HashRouter, Route, Routes, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { isConfigured } from './firebase/config';
import { SettingsProvider, useSettings } from './context/SettingsContext';
import { DataProvider } from './context/DataContext';
import { ToastProvider } from './context/ToastContext';
import Layout from './components/Layout';
import { Spinner } from './components/ui';
import Login from './pages/Login';
import { Disabled, ErrorScreen, FirstRun, Pending, SetupRequired, VerifyEmail } from './pages/Gates';
import Dashboard from './pages/Dashboard';
import Patients from './pages/Patients';
import PatientDetail from './pages/PatientDetail';
import Appointments from './pages/Appointments';
import Billing from './pages/Billing';
import PublicInvoicePage from './pages/PublicInvoice';

// Rarely-used screens are loaded on demand to keep the first load fast on mobile data.
const Services = lazy(() => import('./pages/Services'));
const Reports = lazy(() => import('./pages/Reports'));
const Users = lazy(() => import('./pages/Users'));
const Settings = lazy(() => import('./pages/Settings'));

/** Signs people out after a period of inactivity (a shared front-desk tablet should not stay signed in). */
function IdleGuard() {
  const { settings } = useSettings();
  const { signOut } = useAuth();
  const last = useRef(Date.now());
  useEffect(() => {
    const mins = settings.idleMinutes;
    if (!mins || mins < 1) return;
    const bump = () => { last.current = Date.now(); };
    const evts = ['pointerdown', 'keydown', 'touchstart', 'scroll'] as const;
    evts.forEach((e) => window.addEventListener(e, bump, { passive: true }));
    const t = setInterval(() => { if (Date.now() - last.current > mins * 60_000) void signOut(); }, 20_000);
    return () => { evts.forEach((e) => window.removeEventListener(e, bump)); clearInterval(t); };
  }, [settings.idleMinutes, signOut]);
  return null;
}

function Shell() {
  const { loaded } = useSettings();
  if (!loaded) return <Spinner label="Loading your clinic…" />;
  return (
    <DataProvider>
      <IdleGuard />
      <Suspense fallback={<Spinner />}>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="patients" element={<Patients />} />
            <Route path="patient/:id" element={<PatientDetail />} />
            <Route path="appointments" element={<Appointments />} />
            <Route path="billing" element={<Billing />} />
            <Route path="services" element={<Services />} />
            <Route path="reports" element={<Reports />} />
            <Route path="users" element={<Users />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </DataProvider>
  );
}

function Gate() {
  const { state } = useAuth();
  switch (state.kind) {
    case 'loading': return <Spinner label="Starting…" />;
    case 'signedOut': return <Login />;
    case 'needsVerify': return <VerifyEmail email={state.user.email || ''} />;
    case 'firstRun': return <FirstRun defaultName={state.identity.displayName} />;
    case 'pending': return <Pending uid={state.user.uid} name={state.profile.displayName} />;
    case 'disabled': return <Disabled />;
    case 'error': return <ErrorScreen message={state.message} />;
    case 'ready': return <SettingsProvider enabled><Shell /></SettingsProvider>;
  }
}

export default function App() {
  if (!isConfigured) return <SetupRequired />;
  return (
    <ToastProvider>
      <HashRouter>
        <Routes>
          {/* public: the invoice a patient opens from a WhatsApp / e-mail link. No sign-in. */}
          <Route path="/inv/:key" element={<PublicInvoicePage />} />
          <Route path="*" element={<AuthProvider><Gate /></AuthProvider>} />
        </Routes>
      </HashRouter>
    </ToastProvider>
  );
}
