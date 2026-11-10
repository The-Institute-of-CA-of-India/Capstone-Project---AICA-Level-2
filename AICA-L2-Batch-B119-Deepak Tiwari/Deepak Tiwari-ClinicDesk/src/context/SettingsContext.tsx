import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { doc, onSnapshot } from 'firebase/firestore';
import { getDb } from '../firebase/client';
import { C } from '../data/db';
import { country, type CountryConfig } from '../config/countries';
import { defaultSettings } from '../config/defaults';
import { fmtMoney } from '../lib/money';
import { fmtDate, todayIn } from '../lib/dates';
import { isHexColor } from '../lib/validators';
import type { ClinicSettings } from '../types';

interface SettingsApi {
  settings: ClinicSettings;
  loaded: boolean;
  cfg: CountryConfig;
  locale: string;
  tz: string;
  today: () => string;
  money: (n: number, currency?: string) => string;
  date: (ymd: string) => string;
}
const Ctx = createContext<SettingsApi | null>(null);
export const useSettings = () => {
  const v = useContext(Ctx);
  if (!v) throw new Error('useSettings outside provider');
  return v;
};

export function SettingsProvider({ children, enabled }: { children: ReactNode; enabled: boolean }) {
  const [settings, setSettings] = useState<ClinicSettings>(() => defaultSettings('KE'));
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    return onSnapshot(doc(getDb(), C.settings, 'clinic'), (s) => {
      if (s.exists()) {
        // merge over defaults so settings saved by an older version still have every field
        const d = s.data() as Partial<ClinicSettings>;
        const base = defaultSettings(d.country || 'KE');
        setSettings({
          ...base, ...d,
          tax: { ...base.tax, ...(d.tax || {}) },
          titles: { ...base.titles, ...(d.titles || {}) },
          templates: { ...base.templates, ...(d.templates || {}) },
          features: { ...base.features, ...(d.features || {}) },
          taxIds: d.taxIds || {}, paymentDetails: d.paymentDetails || {},
          paymentMethods: d.paymentMethods?.length ? d.paymentMethods : base.paymentMethods
        });
      }
      setLoaded(true);
    }, () => setLoaded(true));
  }, [enabled]);

  const cfg = country(settings.country);

  // branding: the clinic's colour and name apply across the whole app
  useEffect(() => {
    if (isHexColor(settings.brandColor)) document.documentElement.style.setProperty('--primary', settings.brandColor);
    document.title = settings.clinicName ? `${settings.clinicName} · Clinic` : 'Clinic';
  }, [settings.brandColor, settings.clinicName]);

  const api = useMemo<SettingsApi>(() => ({
    settings, loaded, cfg, locale: cfg.locale, tz: cfg.timezone,
    today: () => todayIn(cfg.timezone),
    money: (n, currency) => fmtMoney(n, currency || settings.currency, cfg.locale),
    date: (ymd) => fmtDate(ymd, cfg.locale)
  }), [settings, loaded, cfg]);

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}
