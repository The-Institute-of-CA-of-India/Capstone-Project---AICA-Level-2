import { useMemo, useState } from 'react';
import { useSettings } from '../context/SettingsContext';
import { useOutstanding, useVisitsRange } from '../data/hooks';
import { monthEnd, monthLabel, monthStart, addDays } from '../lib/dates';
import { round2 } from '../lib/calc';
import { downloadText, toCsv } from '../lib/csv';
import { toPublicClinic } from '../lib/publicView';
import { Letterhead, PrintPortal } from '../components/Docs';
import { Icon, Notice, Seg, Spinner } from '../components/ui';

type Preset = 'month' | 'last' | 'year' | 'custom';

export default function Reports() {
  const { settings, today, money, date, locale } = useSettings();
  const t = today();
  const [preset, setPreset] = useState<Preset>('month');
  const [from, setFrom] = useState(monthStart(t));
  const [to, setTo] = useState(monthEnd(t));
  const choose = (p: Preset) => {
    setPreset(p);
    if (p === 'month') { setFrom(monthStart(t)); setTo(monthEnd(t)); }
    if (p === 'last') { const l = addDays(monthStart(t), -1); setFrom(monthStart(l)); setTo(monthEnd(l)); }
    if (p === 'year') { setFrom(t.slice(0, 4) + '-01-01'); setTo(t.slice(0, 4) + '-12-31'); }
  };
  const { data, loading } = useVisitsRange(from, to);
  const owed = useOutstanding();

  const r = useMemo(() => {
    const cur = data.filter((v) => !v.void);
    const rows = cur.filter((v) => v.currency === settings.currency);
    const other = cur.length - rows.length;
    const sum = (f: (v: (typeof rows)[number]) => number) => round2(rows.reduce((a, v) => a + f(v), 0));
    const svc = new Map<string, { qty: number; amount: number }>();
    const method = new Map<string, number>();
    const tax = new Map<string, number>();
    const month = new Map<string, { n: number; invoiced: number; collected: number }>();
    rows.forEach((v) => {
      v.lines.forEach((l) => { const x = svc.get(l.name) || { qty: 0, amount: 0 }; x.qty += l.qty; x.amount = round2(x.amount + l.amount); svc.set(l.name, x); });
      v.payments.forEach((p) => method.set(p.method, round2((method.get(p.method) || 0) + p.amount)));
      v.taxBreakup.forEach((b) => tax.set(`${b.label} @ ${b.rate}%`, round2((tax.get(`${b.label} @ ${b.rate}%`) || 0) + b.amount)));
      const ym = v.date.slice(0, 7); const m = month.get(ym) || { n: 0, invoiced: 0, collected: 0 };
      m.n++; m.invoiced = round2(m.invoiced + v.total); m.collected = round2(m.collected + v.paid); month.set(ym, m);
    });
    return {
      rows, other, voided: data.length - cur.length, count: rows.length,
      subtotal: sum((v) => v.subtotal), discount: sum((v) => v.discount), tax: sum((v) => v.tax), total: sum((v) => v.total), paid: sum((v) => v.paid), balance: sum((v) => v.balance),
      svc: [...svc.entries()].sort((a, b) => b[1].amount - a[1].amount), method: [...method.entries()].sort((a, b) => b[1] - a[1]),
      tax_: [...tax.entries()], month: [...month.entries()].sort(([a], [b]) => a.localeCompare(b))
    };
  }, [data, settings.currency]);

  const ageing = useMemo(() => {
    const b = [0, 0, 0, 0];
    owed.data.filter((v) => !v.void && v.currency === settings.currency).forEach((v) => {
      const days = Math.max(0, Math.round((Date.parse(t) - Date.parse(v.date)) / 86400000));
      b[days <= 30 ? 0 : days <= 60 ? 1 : days <= 90 ? 2 : 3] += v.balance;
    });
    return b.map(round2);
  }, [owed.data, t, settings.currency]);

  const exportCsv = () => downloadText(`report-${from}-to-${to}.csv`, toCsv([
    ['Section', 'Item', 'Count / Qty', 'Amount'],
    ['Summary', 'Invoices', r.count, ''], ['Summary', 'Subtotal', '', r.subtotal], ['Summary', 'Discounts', '', r.discount],
    ['Summary', 'Tax charged', '', r.tax], ['Summary', 'Total invoiced', '', r.total], ['Summary', 'Collected', '', r.paid], ['Summary', 'Outstanding', '', r.balance],
    ...r.month.map(([k, v]) => ['Month', k, v.n, v.invoiced]),
    ...r.svc.map(([k, v]) => ['Service', k, v.qty, v.amount]),
    ...r.method.map(([k, v]) => ['Payment method', k, '', v]),
    ...r.tax_.map(([k, v]) => ['Tax', k, '', v])
  ]));

  const Table = ({ rows, head }: { rows: (string | number)[][]; head: string[] }) => (
    <table className="tbl rep"><thead><tr>{head.map((h, i) => <th key={h} className={i ? 'r' : ''}>{h}</th>)}</tr></thead>
      <tbody>{rows.map((row, i) => <tr key={i}>{row.map((c, k) => <td key={k} className={k ? 'r money' : ''}>{c}</td>)}</tr>)}</tbody></table>
  );
  const body = (
    <>
      <div className="kpis">
        <div className="kpi"><span className="k">Invoices</span><span className="v">{r.count}</span></div>
        <div className="kpi"><span className="k">Total invoiced</span><span className="v">{money(r.total)}</span></div>
        <div className="kpi good"><span className="k">Collected</span><span className="v">{money(r.paid)}</span></div>
        <div className="kpi warn"><span className="k">Outstanding</span><span className="v">{money(r.balance)}</span></div>
      </div>
      <div className="grid-2">
        <section className="card"><div className="card-h"><h2>Summary</h2></div><div className="card-b">
          <Table head={['Item', 'Amount']} rows={[['Subtotal', money(r.subtotal)], ['Discounts', '−' + money(r.discount)], ...r.tax_.map(([k, v]) => [k, money(v)]), ['Total invoiced', money(r.total)]]} /></div></section>
        <section className="card"><div className="card-h"><h2>Payments received, by method</h2></div><div className="card-b">
          {r.method.length ? <Table head={['Method', 'Amount']} rows={r.method.map(([k, v]) => [k, money(v)])} /> : <p className="muted">No payments on these invoices.</p>}</div></section>
      </div>
      <section className="card section-gap"><div className="card-h"><h2>By service</h2></div><div className="card-b">
        {r.svc.length ? <Table head={['Service', 'Qty', 'Amount']} rows={r.svc.map(([k, v]) => [k, v.qty, money(v.amount)])} /> : <p className="muted">No services billed.</p>}</div></section>
      {r.month.length > 1 && <section className="card section-gap"><div className="card-h"><h2>By month</h2></div><div className="card-b">
        <Table head={['Month', 'Invoices', 'Invoiced', 'Collected']} rows={r.month.map(([k, v]) => [monthLabel(k, locale, true) + ' ' + k.slice(0, 4), v.n, money(v.invoiced), money(v.collected)])} /></div></section>}
      <section className="card section-gap"><div className="card-h"><h2>Unpaid invoices by age (all time)</h2></div><div className="card-b">
        <Table head={['Age', 'Balance']} rows={[['0–30 days', money(ageing[0])], ['31–60 days', money(ageing[1])], ['61–90 days', money(ageing[2])], ['Over 90 days', money(ageing[3])]]} /></div></section>
    </>
  );

  return (
    <>
      <div className="page-h"><div><h1>Reports</h1><p className="muted">{date(from)} – {date(to)}</p></div>
        <div className="actions"><button className="btn" onClick={exportCsv}><Icon n="download" size={16} />Export CSV</button><button className="btn" onClick={() => window.print()}><Icon n="printer" size={16} />Print</button></div></div>
      <div className="toolbar wrap">
        <Seg label="Period" value={preset} onChange={choose} options={[{ v: 'month', l: 'This month' }, { v: 'last', l: 'Last month' }, { v: 'year', l: 'This year' }, { v: 'custom', l: 'Custom' }]} />
        {preset === 'custom' && <><label className="inl">From <input type="date" value={from} onChange={(e) => e.target.value && setFrom(e.target.value)} /></label>
          <label className="inl">To <input type="date" value={to} onChange={(e) => e.target.value && setTo(e.target.value)} /></label></>}
      </div>
      {r.other > 0 && <Notice kind="warn">{r.other} invoice{r.other === 1 ? ' was' : 's were'} issued in a different currency and {r.other === 1 ? 'is' : 'are'} not included in these totals.</Notice>}
      {r.voided > 0 && <p className="muted small">{r.voided} void invoice{r.voided === 1 ? '' : 's'} excluded.</p>}
      {loading ? <Spinner /> : body}
      <PrintPortal><article className="doc" style={{ ['--doc-accent' as string]: settings.brandColor }}>
        <Letterhead c={toPublicClinic(settings)} right={<><div className="doc-title">Report</div><div className="muted">{date(from)} – {date(to)}</div></>} />
        {body}</article></PrintPortal>
    </>
  );
}
