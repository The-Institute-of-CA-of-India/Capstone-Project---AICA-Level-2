import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSettings } from '../context/SettingsContext';
import { useAuth } from '../auth/AuthContext';
import { can } from '../auth/permissions';
import { useVisitsRange } from '../data/hooks';
import { addDays, monthEnd, monthStart } from '../lib/dates';
import { round2 } from '../lib/calc';
import { downloadText, toCsv } from '../lib/csv';
import InvoiceViewer, { PayModal } from '../components/InvoiceViewer';
import { Empty, Icon, Pill, Spinner } from '../components/ui';
import type { Visit } from '../types';

export default function Billing() {
  const { state } = useAuth();
  const { today, money, date, settings } = useSettings();
  const t = today();
  const [from, setFrom] = useState(monthStart(t));
  const [to, setTo] = useState(monthEnd(t));
  const [status, setStatus] = useState('all');
  const [q, setQ] = useState('');
  const [view, setView] = useState<string | null>(null);
  const [pay, setPay] = useState<Visit | null>(null);
  const role = state.kind === 'ready' ? state.profile.role : undefined;
  const { data, loading, error } = useVisitsRange(from, to);

  const list = useMemo(() => {
    const s = q.trim().toLowerCase();
    return data.filter((v) => (status === 'all' || v.status === status) &&
      (!s || v.invoiceNo.toLowerCase().includes(s) || v.patientName.toLowerCase().includes(s) || v.patientId.toLowerCase().includes(s)))
      .sort((a, b) => b.date.localeCompare(a.date) || b.invoiceNo.localeCompare(a.invoiceNo));
  }, [data, status, q]);
  const live = list.filter((v) => !v.void && v.currency === settings.currency);
  const sum = (k: 'total' | 'paid' | 'balance') => round2(live.reduce((a, v) => a + v[k], 0));

  const exportCsv = () => downloadText(`invoices-${from}-to-${to}.csv`, toCsv([
    ['Invoice', 'Date', 'File no', 'Patient', 'Currency', 'Subtotal', 'Discount', 'Tax', 'Total', 'Paid', 'Balance', 'Status'],
    ...list.map((v) => [v.invoiceNo, v.date, v.patientId, v.patientName, v.currency, v.subtotal, v.discount, v.tax, v.total, v.paid, v.balance, v.status])
  ]));

  return (
    <>
      <div className="page-h"><div><h1>Billing</h1><p className="muted">Invoices and payments</p></div>
        <button className="btn" onClick={exportCsv} disabled={!list.length}><Icon n="download" size={16} />Export CSV</button></div>
      <div className="toolbar wrap">
        <label className="inl">From <input type="date" value={from} onChange={(e) => e.target.value && setFrom(e.target.value)} /></label>
        <label className="inl">To <input type="date" value={to} onChange={(e) => e.target.value && setTo(e.target.value)} /></label>
        <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
          {['all', 'Unpaid', 'Part-paid', 'Paid', 'No charge', 'Void'].map((s) => <option key={s} value={s}>{s === 'all' ? 'All statuses' : s}</option>)}
        </select>
        <div className="search"><Icon n="search" size={17} /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Invoice no. or patient" aria-label="Search invoices" /></div>
        <button className="btn sm" onClick={() => { setFrom(addDays(t, -30)); setTo(t); }}>Last 30 days</button>
      </div>
      {error && <div className="notice err">{error}</div>}
      <div className="kpis three">
        <div className="kpi"><span className="k">Invoiced</span><span className="v">{money(sum('total'))}</span></div>
        <div className="kpi good"><span className="k">Collected</span><span className="v">{money(sum('paid'))}</span></div>
        <div className="kpi warn"><span className="k">Outstanding</span><span className="v">{money(sum('balance'))}</span></div>
      </div>
      <section className="card">
        {loading ? <Spinner /> : !list.length ? <Empty title="No invoices in this period">Change the dates or filters.</Empty> : (
          <table className="tbl stack">
            <thead><tr><th>Date</th><th>Invoice</th><th>Patient</th><th className="r">Total</th><th className="r">Balance</th><th>Status</th><th aria-hidden="true" /></tr></thead>
            <tbody>{list.map((v) => (
              <tr key={v.id} className={v.void ? 'void' : ''}>
                <td data-l="Date" className="nw">{date(v.date)}</td>
                <td data-l="Invoice" className="fileno">{v.invoiceNo}</td>
                <td data-l="Patient"><Link to={`/patient/${encodeURIComponent(v.patientId)}`}>{v.patientName}</Link></td>
                <td data-l="Total" className="r money">{money(v.total, v.currency)}</td>
                <td data-l="Balance" className={'r money' + (v.balance > 0.005 && !v.void ? ' neg' : '')}>{v.void ? '—' : money(v.balance, v.currency)}</td>
                <td data-l="Status"><Pill kind={v.status}>{v.status}</Pill></td>
                <td className="row-actions">
                  <button className="btn sm" onClick={() => setView(v.id)}>View</button>
                  {!v.void && v.balance > 0.005 && can(role, 'billing.write') && <button className="btn sm primary" onClick={() => setPay(v)}>Pay</button>}
                </td>
              </tr>))}
            </tbody>
          </table>)}
      </section>
      {view && <InvoiceViewer visitId={view} onClose={() => setView(null)} />}
      {pay && <PayModal visit={pay} onClose={() => setPay(null)} />}
    </>
  );
}
