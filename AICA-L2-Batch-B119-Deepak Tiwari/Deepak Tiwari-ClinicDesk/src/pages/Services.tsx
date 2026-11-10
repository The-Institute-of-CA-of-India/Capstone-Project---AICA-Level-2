import { useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { can } from '../auth/permissions';
import { useData } from '../context/DataContext';
import { useSettings } from '../context/SettingsContext';
import { useToast } from '../context/ToastContext';
import { newId, saveServices, C } from '../data/db';
import { Empty, Icon, Notice } from '../components/ui';
import type { Service } from '../types';

export default function Services() {
  const { state } = useAuth();
  const { services } = useData();
  const { cfg, money } = useSettings();
  const toast = useToast();
  const role = state.kind === 'ready' ? state.profile.role : undefined;
  const edit = can(role, 'services.edit');
  const [rows, setRows] = useState<Service[]>([]);
  const [removed, setRemoved] = useState<string[]>([]);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (!dirty) setRows([...services].sort((a, b) => a.category.localeCompare(b.category) || a.name.localeCompare(b.name))); }, [services, dirty]);

  const upd = (id: string, p: Partial<Service>) => { setDirty(true); setRows((r) => r.map((x) => (x.id === id ? { ...x, ...p } : x))); };
  const add = () => { setDirty(true); setRows((r) => [...r, { id: newId(C.services), name: '', category: 'Consultation', price: 0, minutes: 15, taxable: false, code: '', active: true }]); };
  const del = (id: string) => { setDirty(true); setRows((r) => r.filter((x) => x.id !== id)); setRemoved((x) => [...x, id]); };
  const save = async () => {
    if (state.kind !== 'ready') return;
    const clean = rows.filter((r) => r.name.trim());
    setBusy(true);
    try { await saveServices(clean, removed.filter((id) => !clean.some((c) => c.id === id)), { uid: state.user.uid, name: state.profile.displayName }); setDirty(false); setRemoved([]); toast('Price list saved'); }
    catch (e) { toast(e instanceof Error ? e.message : 'Could not save.', 'err'); } finally { setBusy(false); }
  };

  return (
    <>
      <div className="page-h"><div><h1>Services & prices</h1><p className="muted">{edit ? 'Edit the price list, then press Save.' : 'Only the owner can change prices.'}</p></div>
        {edit && <div className="actions"><button className="btn" onClick={add}><Icon n="plus" size={16} />Add service</button><button className="btn primary" disabled={!dirty || busy} onClick={() => void save()}>Save price list</button></div>}</div>
      {edit && <Notice kind="warn">Starting prices are samples. Replace them with your real prices. “Taxable” decides whether {cfg.tax.label} applies to that line when {cfg.tax.label} is switched on for an invoice.</Notice>}
      <section className="card">
        {!rows.length ? <Empty title="No services yet">Add your first service.</Empty> : (
          <table className="tbl stack svc">
            <thead><tr><th>Service</th><th>Category</th><th className="r">Price</th><th>Min</th><th>Taxable</th>{cfg.tax.codeLabel && <th>{cfg.tax.codeLabel}</th>}<th>Active</th>{edit && <th aria-hidden="true" />}</tr></thead>
            <tbody>{rows.map((r) => edit ? (
              <tr key={r.id}>
                <td data-l="Service"><input aria-label="Service name" value={r.name} onChange={(e) => upd(r.id, { name: e.target.value })} /></td>
                <td data-l="Category"><input aria-label="Category" value={r.category} onChange={(e) => upd(r.id, { category: e.target.value })} /></td>
                <td data-l="Price"><input aria-label="Price" inputMode="decimal" className="num" value={r.price} onChange={(e) => upd(r.id, { price: e.target.value as unknown as number })} /></td>
                <td data-l="Min"><input aria-label="Minutes" inputMode="numeric" className="num sm" value={r.minutes} onChange={(e) => upd(r.id, { minutes: e.target.value as unknown as number })} /></td>
                <td data-l="Taxable"><input type="checkbox" aria-label="Taxable" checked={r.taxable} onChange={(e) => upd(r.id, { taxable: e.target.checked })} /></td>
                {cfg.tax.codeLabel && <td data-l={cfg.tax.codeLabel}><input aria-label={cfg.tax.codeLabel} className="num" value={r.code} onChange={(e) => upd(r.id, { code: e.target.value })} /></td>}
                <td data-l="Active"><input type="checkbox" aria-label="Active" checked={r.active} onChange={(e) => upd(r.id, { active: e.target.checked })} /></td>
                <td><button className="icon-btn" aria-label={`Delete ${r.name || 'service'}`} onClick={() => del(r.id)}><Icon n="trash" size={16} /></button></td>
              </tr>) : (
              <tr key={r.id}><td data-l="Service"><b>{r.name}</b></td><td data-l="Category">{r.category}</td><td data-l="Price" className="r money">{money(r.price)}</td><td data-l="Min">{r.minutes}</td><td data-l="Taxable">{r.taxable ? 'Yes' : 'No'}</td>{cfg.tax.codeLabel && <td data-l={cfg.tax.codeLabel}>{r.code}</td>}<td data-l="Active">{r.active ? 'Yes' : 'No'}</td></tr>))}
            </tbody>
          </table>)}
      </section>
    </>
  );
}
