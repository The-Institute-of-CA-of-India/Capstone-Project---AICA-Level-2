import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useSettings } from '../context/SettingsContext';
import { useData } from '../context/DataContext';
import { useApptsRange, useOutstanding, useVisitsRange } from '../data/hooks';
import { addDays, longDate, monthLabel, time12 } from '../lib/dates';
import { round2 } from '../lib/calc';
import { Empty, Icon, Pill, Spinner } from '../components/ui';

export default function Dashboard() {
  const { state } = useAuth();
  const { settings, today, money, locale, date } = useSettings();
  const { patients, patientById } = useData();
  const t = today();
  const [year, setYear] = useState(t.slice(0, 4));
  const [month, setMonth] = useState(t.slice(0, 7));
  const visits = useVisitsRange(`${year}-01-01`, `${year}-12-31`);
  const outstanding = useOutstanding();
  const appts = useApptsRange(t, addDays(t, 1));

  const first = state.kind === 'ready' ? state.profile.displayName.split(' ')[0] : '';
  const hour = Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hour12: false, timeZone: settings.country === 'IN' ? 'Asia/Kolkata' : 'Africa/Nairobi' }).format(new Date()));
  const greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const stats = useMemo(() => {
    const live = visits.data.filter((v) => !v.void && v.currency === settings.currency);
    const byMonth: { ym: string; invoiced: number; collected: number }[] = [];
    for (let m = 1; m <= 12; m++) {
      const ym = `${year}-${String(m).padStart(2, '0')}`;
      const rows = live.filter((v) => v.date.startsWith(ym));
      byMonth.push({ ym, invoiced: round2(rows.reduce((a, v) => a + v.total, 0)), collected: round2(rows.reduce((a, v) => a + v.paid, 0)) });
    }
    const cur = live.filter((v) => v.date.startsWith(month));
    return {
      byMonth,
      invoiced: round2(cur.reduce((a, v) => a + v.total, 0)),
      collected: round2(cur.reduce((a, v) => a + v.paid, 0)),
      count: cur.length,
      max: Math.max(1, ...byMonth.map((b) => Math.max(b.invoiced, b.collected)))
    };
  }, [visits.data, year, month, settings.currency]);

  const owed = round2(outstanding.data.filter((v) => !v.void && v.currency === settings.currency).reduce((a, v) => a + v.balance, 0));
  const todays = appts.data.filter((a) => a.date === t).sort((a, b) => a.time.localeCompare(b.time));
  const tomorrow = appts.data.filter((a) => a.date === addDays(t, 1) && a.status === 'Scheduled');
  const years = [...new Set([t.slice(0, 4), String(Number(t.slice(0, 4)) - 1), String(Number(t.slice(0, 4)) - 2)])];

  return (
    <>
      <div className="page-h">
        <div><h1>{greet}{first ? `, ${first}` : ''}</h1><p className="muted">{longDate(t, locale)}</p></div>
        <div className="filters">
          <label className="sr-only" htmlFor="d-year">Year</label>
          <select id="d-year" value={year} onChange={(e) => { setYear(e.target.value); setMonth(e.target.value + '-' + month.slice(5)); }}>
            {years.map((y) => <option key={y}>{y}</option>)}
          </select>
          <label className="sr-only" htmlFor="d-month">Month</label>
          <select id="d-month" value={month} onChange={(e) => setMonth(e.target.value)}>
            {Array.from({ length: 12 }, (_, i) => { const ym = `${year}-${String(i + 1).padStart(2, '0')}`; return <option key={ym} value={ym}>{monthLabel(ym, locale, true)}</option>; })}
          </select>
        </div>
      </div>

      <div className="kpis">
        <div className="kpi"><span className="k">Invoiced in {monthLabel(month, locale, true)}</span><span className="v">{money(stats.invoiced)}</span></div>
        <div className="kpi good"><span className="k">Collected on those invoices</span><span className="v">{money(stats.collected)}</span></div>
        <div className="kpi warn"><span className="k">Outstanding, all time</span><span className="v">{money(owed)}</span>
          <Link to="/billing" className="small">See unpaid invoices</Link></div>
        <div className="kpi"><span className="k">Visits this month</span><span className="v">{stats.count}</span><span className="small muted">{patients.length} patients on file</span></div>
      </div>

      <div className="grid-2">
        <section className="card">
          <div className="card-h"><h2>Invoiced and collected, {year}</h2>
            <span className="legend"><i className="sw a" />Invoiced<i className="sw b" />Collected</span></div>
          <div className="card-b">
            {visits.loading ? <Spinner /> : (
              <div className="bars" role="img" aria-label={`Monthly invoiced and collected amounts for ${year}`}>
                {stats.byMonth.map((b) => (
                  <div className="bar-col" key={b.ym} title={`${monthLabel(b.ym, locale, true)}: invoiced ${money(b.invoiced)}, collected ${money(b.collected)}`}>
                    <div className="bar-pair">
                      <span className="bar a" style={{ height: `${(b.invoiced / stats.max) * 100}%` }} />
                      <span className="bar b" style={{ height: `${(b.collected / stats.max) * 100}%` }} />
                    </div>
                    <span className="bar-l">{monthLabel(b.ym, locale)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="card">
          <div className="card-h"><h2>Today</h2><Link className="btn sm" to="/appointments">Appointments</Link></div>
          <div className="card-b flush">
            {todays.length ? todays.map((a) => (
              <Link key={a.id} to={`/patient/${encodeURIComponent(a.patientId)}`} className="list-row">
                <span className="t">{time12(a.time)}</span>
                <span className="grow"><b>{a.patientName}</b><small className="muted block">{a.service || 'Appointment'}</small></span>
                <Pill kind={a.status}>{a.status}</Pill>
              </Link>
            )) : <Empty title="Nothing booked for today">Book from Appointments, or from a patient’s card.</Empty>}
          </div>
          <div className="card-f small">{tomorrow.length} appointment{tomorrow.length === 1 ? '' : 's'} tomorrow{tomorrow.length ? <> · <Link to="/appointments">send reminders</Link></> : null}</div>
        </section>
      </div>

      <section className="card section-gap">
        <div className="card-h"><h2>Largest unpaid balances</h2><Link className="btn sm" to="/billing">All invoices</Link></div>
        <div className="card-b flush">
          {outstanding.data.filter((v) => !v.void).sort((a, b) => b.balance - a.balance).slice(0, 5).map((v) => (
            <Link key={v.id} to={`/patient/${encodeURIComponent(v.patientId)}`} className="list-row">
              <span className="grow"><b>{patientById(v.patientId)?.name || v.patientName}</b><small className="muted block">{v.invoiceNo} · {date(v.date)}</small></span>
              <b className="money neg">{money(v.balance, v.currency)}</b><Icon n="chev" size={16} />
            </Link>
          ))}
          {!outstanding.loading && !outstanding.data.some((v) => !v.void) && <Empty title="All caught up">Every invoice is paid.</Empty>}
        </div>
      </section>
    </>
  );
}
