import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { COUNTRY_LIST, CURRENCIES, country } from '../config/countries';
import { countryDefaults, DEFAULT_TEMPLATES } from '../config/defaults';
import { useSettings } from '../context/SettingsContext';
import { useToast } from '../context/ToastContext';
import { removeLogoFile, saveSettings, uploadLogo } from '../data/db';
import { resizeImage } from '../lib/image';
import { normalizePhone } from '../lib/phone';
import { waInvoiceTemplateError } from '../lib/template';
import { isEmail, isHexColor, validateTaxId } from '../lib/validators';
import { Check, Field, Icon, Modal, Notice, Toggle } from '../components/ui';
import { DEFAULT_LOGO } from '../components/Layout';
import type { ClinicSettings, CountryCode } from '../types';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

export default function Settings() {
  const { state } = useAuth();
  const { settings } = useSettings();
  const toast = useToast();
  const [d, setD] = useState<ClinicSettings>(() => clone(settings));
  const [dirty, setDirty] = useState(false);
  const [errs, setErrs] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [switchTo, setSwitchTo] = useState<CountryCode | null>(null);
  const [logoBusy, setLogoBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => { if (!dirty) setD(clone(settings)); }, [settings, dirty]);

  if (state.kind !== 'ready') return null;
  const actor = { uid: state.user.uid, name: state.profile.displayName };
  const c = country(d.country);
  const up = (p: Partial<ClinicSettings>) => { setDirty(true); setD((x) => ({ ...x, ...p })); };
  const upTax = (p: Partial<ClinicSettings['tax']>) => up({ tax: { ...d.tax, ...p } });
  const upTpl = (k: keyof ClinicSettings['templates'], v: string) => up({ templates: { ...d.templates, [k]: v } });

  const applyCountry = (cc: CountryCode, withText: boolean) => {
    const def = countryDefaults(cc);
    setDirty(true);
    setD((x) => ({
      ...x, country: cc, currency: def.currency, tax: def.tax, paymentMethods: def.paymentMethods, taxIds: {}, paymentDetails: {},
      ...(withText ? { titles: def.titles, invoiceFooter: def.invoiceFooter, disclaimer: def.disclaimer, consentText: def.consentText } : {})
    }));
    setSwitchTo(null);
  };

  const pickLogo = async (f: File | undefined) => {
    if (!f) return;
    setLogoBusy(true);
    try {
      const blob = await resizeImage(f, 512);
      const { url, path } = await uploadLogo(blob, settings.logoPath);
      await saveSettings({ ...settings, logoUrl: url, logoPath: path }, actor);   // saves only the logo, not unsaved edits
      setD((x) => ({ ...x, logoUrl: url, logoPath: path }));
      toast('Logo updated');
    } catch (e) { toast(e instanceof Error ? e.message : 'Could not upload the logo.', 'err'); }
    finally { setLogoBusy(false); if (fileRef.current) fileRef.current.value = ''; }
  };
  const dropLogo = async () => {
    try { await removeLogoFile(settings.logoPath); await saveSettings({ ...settings, logoUrl: '', logoPath: '' }, actor); setD((x) => ({ ...x, logoUrl: '', logoPath: '' })); toast('Logo removed'); }
    catch (e) { toast(e instanceof Error ? e.message : 'Could not remove the logo.', 'err'); }
  };

  const save = async () => {
    const e: string[] = [];
    if (!d.clinicName.trim()) e.push('Enter the clinic name.');
    if (d.email && !isEmail(d.email)) e.push('The clinic email address does not look right.');
    for (const k of ['phone1', 'phone2'] as const) { if (d[k]) { const r = normalizePhone(d[k], d.country); if (!r.ok) e.push(`${k === 'phone1' ? 'Phone' : 'Second phone'}: ${r.error}`); } }
    c.taxIds.forEach((t) => { const m = validateTaxId(t, d.taxIds[t.key] || ''); if (m) e.push(m); });
    if (!isHexColor(d.brandColor)) e.push('Choose a valid brand colour.');
    if (!(d.tax.rate >= 0 && d.tax.rate <= 100)) e.push(`${c.tax.label} rate must be between 0 and 100.`);
    const w = waInvoiceTemplateError(d.templates.waInvoice); if (w) e.push(w);
    if (!/^[A-Za-z0-9]{1,8}$/.test(d.invoicePrefix) || !/^[A-Za-z0-9]{1,8}$/.test(d.filePrefix)) e.push('Prefixes may use letters and digits only (up to 8).');
    if (!d.paymentMethods.length) e.push('Keep at least one payment method.');
    setErrs(e);
    if (e.length) { window.scrollTo({ top: 0, behavior: 'smooth' }); return; }
    setBusy(true);
    try {
      const normalized = { ...d, taxIds: Object.fromEntries(Object.entries(d.taxIds).map(([k, v]) => [k, v.trim().toUpperCase()])), clinicName: d.clinicName.trim() };
      await saveSettings(normalized, actor); setDirty(false); toast('Settings saved');
    } catch (x) { toast(x instanceof Error ? x.message : 'Could not save.', 'err'); } finally { setBusy(false); }
  };

  const txt = (k: keyof ClinicSettings, label: string, p: { span?: 2 | 3 | 'all'; ph?: string; type?: string } = {}) => (
    <Field label={label} span={p.span} htmlFor={'s-' + k}>
      <input id={'s-' + k} type={p.type || 'text'} placeholder={p.ph} value={String(d[k] ?? '')} onChange={(e) => up({ [k]: e.target.value } as Partial<ClinicSettings>)} />
    </Field>);

  return (
    <>
      <div className="page-h"><div><h1>Settings</h1><p className="muted">Clinic details, country, tax and documents</p></div>
        <button className="btn primary" disabled={!dirty || busy} onClick={() => void save()}>Save settings</button></div>
      {errs.length > 0 && <Notice kind="err"><b>Please fix:</b><ul className="tight">{errs.map((x) => <li key={x}>{x}</li>)}</ul></Notice>}
      <Notice kind="warn"><b>Not legal or tax advice.</b> Tax rates, tax identifiers and document wording here are starting defaults only. Have a qualified accountant or lawyer review them for your clinic before you issue invoices.</Notice>

      <section className="card section-gap"><div className="card-h"><h2>Clinic profile</h2></div><div className="card-b">
        <div className="logo-row">
          <span className="logo-box"><img src={d.logoUrl || DEFAULT_LOGO} alt="Current logo" /></span>
          <div>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(e) => void pickLogo(e.target.files?.[0])} />
            <button className="btn" disabled={logoBusy} onClick={() => fileRef.current?.click()}><Icon n="upload" size={16} />{logoBusy ? 'Uploading…' : 'Upload logo'}</button>
            {d.logoUrl && <button className="btn" onClick={() => void dropLogo()}>Remove</button>}
            <p className="muted small">PNG, JPG or WebP. Shown in the header, on invoices, receipts, prescriptions and reports. It is saved as soon as you upload it.</p>
          </div>
        </div>
        <div className="grid g3">
          {txt('clinicName', 'Clinic / company name', { span: 2 })}
          <Field label="Brand colour" htmlFor="s-color"><div className="color-row"><input id="s-color" type="color" value={isHexColor(d.brandColor) ? d.brandColor : '#1766b3'} onChange={(e) => up({ brandColor: e.target.value })} /><code>{d.brandColor}</code></div></Field>
          {txt('tagline', 'Tagline (optional)', { span: 'all' })}
          {txt('practitioner', 'Main practitioner (printed on prescriptions)', { span: 2 })}
          {txt('practitionerReg', c.registration.practitioner)}
          {txt('address', 'Address', { span: 'all' })}
          {txt('phone1', 'Phone / mobile', { ph: c.phone.example })}
          {txt('phone2', 'Second phone (optional)', { ph: c.phone.example })}
          {txt('email', 'Email address', { type: 'email' })}
          {txt('website', 'Website (optional)', { span: 2 })}
          {txt('registrationNo', c.registration.clinic + ' (optional)')}
          {txt('hours', 'Opening hours (optional)', { span: 'all' })}
        </div></div></section>

      <section className="card section-gap"><div className="card-h"><h2>Country, currency and tax</h2></div><div className="card-b">
        <div className="grid g3">
          <Field label="Country" htmlFor="s-cc" hint="Changes currency, phone rules, tax labels, payment methods and wording.">
            <select id="s-cc" value={d.country} onChange={(e) => setSwitchTo(e.target.value as CountryCode)}>{COUNTRY_LIST.map((x) => <option key={x.code} value={x.code}>{x.name}</option>)}</select></Field>
          <Field label="Currency" htmlFor="s-cur" hint="Existing invoices keep the currency they were issued in.">
            <select id="s-cur" value={d.currency} onChange={(e) => up({ currency: e.target.value })}>{[...new Set([c.currency, ...CURRENCIES])].map((x) => <option key={x}>{x}</option>)}</select></Field>
        </div>
        <Notice>{c.tax.help}</Notice>
        <div className="grid g3">
          <div className="span-all"><Toggle checked={d.tax.enabled} onChange={(v) => upTax({ enabled: v })} label={`Charge ${c.tax.label} by default on new invoices`} help="It can still be switched on or off for each invoice." /></div>
          <Field label={`${c.tax.label} rate (%)`} htmlFor="s-rate"><input id="s-rate" list="s-rates" inputMode="decimal" value={d.tax.rate} onChange={(e) => upTax({ rate: Number(e.target.value) })} />
            <datalist id="s-rates">{c.tax.presets.map((p) => <option key={p} value={p} />)}</datalist></Field>
          <div className="field span-2"><label>&nbsp;</label><Check checked={d.tax.inclusive} onChange={(v) => upTax({ inclusive: v })}>Prices already include {c.tax.label}</Check></div>
          {c.tax.supportsSupplySplit && <Field label="Default place of supply" span="all">
            <select value={d.tax.defaultSupply} onChange={(e) => upTax({ defaultSupply: e.target.value as 'intra' | 'inter' })}><option value="intra">Same state — CGST + SGST</option><option value="inter">Other state — IGST</option></select></Field>}
        </div>
        <h3 className="sub-h">Tax identifiers</h3>
        <div className="grid g3">{c.taxIds.map((t) => (
          <Field key={t.key} label={t.label} htmlFor={'t-' + t.key} hint={t.help} error={validateTaxId(t, d.taxIds[t.key] || '')}>
            <input id={'t-' + t.key} value={d.taxIds[t.key] || ''} placeholder={t.placeholder} onChange={(e) => up({ taxIds: { ...d.taxIds, [t.key]: e.target.value } })} /></Field>))}</div>
        <h3 className="sub-h">Regulatory notes for {c.name}</h3>
        <ul className="tight">{c.regulatoryNotes.map((n) => <li key={n}>{n}</li>)}</ul>
      </div></section>

      <section className="card section-gap"><div className="card-h"><h2>Invoices and receipts</h2></div><div className="card-b">
        <div className="grid g3">
          {txt('invoicePrefix', 'Invoice number prefix')}{txt('filePrefix', 'Patient file number prefix')}
          <Field label="Invoice title" htmlFor="s-ti"><input id="s-ti" value={d.titles.invoice} onChange={(e) => up({ titles: { ...d.titles, invoice: e.target.value } })} /></Field>
          <Field label={`Title when ${c.tax.label} is charged`} htmlFor="s-tt"><input id="s-tt" value={d.titles.taxInvoice} onChange={(e) => up({ titles: { ...d.titles, taxInvoice: e.target.value } })} /></Field>
          <Field label="Receipt title" htmlFor="s-tr"><input id="s-tr" value={d.titles.receipt} onChange={(e) => up({ titles: { ...d.titles, receipt: e.target.value } })} /></Field>
          <Field label="Prescription title" htmlFor="s-tp"><input id="s-tp" value={d.titles.prescription} onChange={(e) => up({ titles: { ...d.titles, prescription: e.target.value } })} /></Field>
          <Field label="Footer text" span="all" htmlFor="s-foot"><input id="s-foot" value={d.invoiceFooter} onChange={(e) => up({ invoiceFooter: e.target.value })} /></Field>
          <Field label="Disclaimer / confidentiality line" span="all" htmlFor="s-dis"><textarea id="s-dis" rows={2} value={d.disclaimer} onChange={(e) => up({ disclaimer: e.target.value })} /></Field>
          <Field label="Patient consent wording (new health cards)" span="all" htmlFor="s-con"><textarea id="s-con" rows={2} value={d.consentText} onChange={(e) => up({ consentText: e.target.value })} /></Field>
        </div>
        <h3 className="sub-h">Payment methods</h3>
        <div className="grid g3"><Field label="Accepted methods (comma separated)" span="all" htmlFor="s-pm">
          <input id="s-pm" value={d.paymentMethods.join(', ')} onChange={(e) => up({ paymentMethods: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) })} /></Field></div>
        <h3 className="sub-h">Payment details (printed on unpaid invoices)</h3>
        <div className="grid g3">{c.paymentFields.map((f) => (
          <Field key={f.key} label={f.label} htmlFor={'pd-' + f.key}>
            {f.options ? <select id={'pd-' + f.key} value={d.paymentDetails[f.key] || f.options[0]} onChange={(e) => up({ paymentDetails: { ...d.paymentDetails, [f.key]: e.target.value } })}>{f.options.map((o) => <option key={o}>{o}</option>)}</select>
              : <input id={'pd-' + f.key} placeholder={f.placeholder} value={d.paymentDetails[f.key] || ''} onChange={(e) => up({ paymentDetails: { ...d.paymentDetails, [f.key]: e.target.value } })} />}</Field>))}</div>
      </div></section>

      <section className="card section-gap"><div className="card-h"><h2>Messages</h2></div><div className="card-b">
        <p className="muted small">Placeholders: {'{clinic} {name} {date} {time} {phone} {address} {number} {total} {link} {practitioner}'}. The WhatsApp invoice message may only use {'{clinic}'} and {'{link}'} so no patient detail is ever sent through it.</p>
        <div className="grid g2">
          <Field label="WhatsApp invoice message" span="all" htmlFor="m1"><input id="m1" value={d.templates.waInvoice} onChange={(e) => upTpl('waInvoice', e.target.value)} /></Field>
          <Field label="WhatsApp reminder" span="all" htmlFor="m2"><textarea id="m2" rows={2} value={d.templates.waRemind} onChange={(e) => upTpl('waRemind', e.target.value)} /></Field>
          <Field label="SMS reminder" span="all" htmlFor="m3"><textarea id="m3" rows={2} value={d.templates.smsRemind} onChange={(e) => upTpl('smsRemind', e.target.value)} /></Field>
          <Field label="Email invoice subject" htmlFor="m4"><input id="m4" value={d.templates.emailInvoiceSubject} onChange={(e) => upTpl('emailInvoiceSubject', e.target.value)} /></Field>
          <Field label="Email reminder subject" htmlFor="m5"><input id="m5" value={d.templates.emailRemindSubject} onChange={(e) => upTpl('emailRemindSubject', e.target.value)} /></Field>
          <Field label="Email invoice body" htmlFor="m6"><textarea id="m6" rows={5} value={d.templates.emailInvoiceBody} onChange={(e) => upTpl('emailInvoiceBody', e.target.value)} /></Field>
          <Field label="Email reminder body" htmlFor="m7"><textarea id="m7" rows={5} value={d.templates.emailRemindBody} onChange={(e) => upTpl('emailRemindBody', e.target.value)} /></Field>
        </div>
        <button className="btn sm" onClick={() => up({ templates: { ...DEFAULT_TEMPLATES } })}>Reset messages to defaults</button>
      </div></section>

      <section className="card section-gap"><div className="card-h"><h2>Features and security</h2></div><div className="card-b stack">
        <Toggle checked={d.features.prescriptions} onChange={(v) => up({ features: { ...d.features, prescriptions: v } })} label="Prescriptions" help="Doctors and the owner can write printable prescriptions on a visit." />
        <Toggle checked={d.features.constitution} onChange={(v) => up({ features: { ...d.features, constitution: v } })} label="Ayurvedic constitution (prakriti) field" help="For Ayurveda / naturopathy practices. Adds Vata / Pitta / Kapha to health cards." />
        <Field label="Sign out after inactivity (minutes, 0 = never)" htmlFor="s-idle" hint="Recommended on shared front-desk tablets and computers."><input id="s-idle" className="num" inputMode="numeric" value={d.idleMinutes} onChange={(e) => up({ idleMinutes: Math.max(0, Math.min(600, parseInt(e.target.value, 10) || 0)) })} /></Field>
      </div></section>

      {dirty && <div className="savebar"><span>You have unsaved changes</span><button className="btn" onClick={() => { setD(clone(settings)); setDirty(false); setErrs([]); }}>Discard</button><button className="btn primary" disabled={busy} onClick={() => void save()}>Save settings</button></div>}

      {switchTo && (
        <Modal title={`Switch to ${country(switchTo).name}?`} onClose={() => setSwitchTo(null)}
          footer={<><button className="btn" onClick={() => setSwitchTo(null)}>Cancel</button><button className="btn" onClick={() => applyCountry(switchTo, false)}>Keep my wording</button><button className="btn primary" onClick={() => applyCountry(switchTo, true)}>Replace wording too</button></>}>
          <p>This sets the currency to <b>{country(switchTo).currency}</b>, the tax to <b>{country(switchTo).tax.label}</b> (switched off) and the payment methods, and clears the tax identifiers and payment details of the old country.</p>
          <p>Should your invoice titles, footer, disclaimer and consent wording also be replaced with {country(switchTo).name}’s defaults? You can review everything before saving.</p>
        </Modal>
      )}
    </>
  );
}
