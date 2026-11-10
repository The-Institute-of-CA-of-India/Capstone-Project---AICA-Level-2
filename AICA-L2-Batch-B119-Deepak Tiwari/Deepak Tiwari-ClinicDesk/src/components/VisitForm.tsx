import { useEffect, useMemo, useState } from 'react';
import { doc, getDoc } from 'firebase/firestore';
import { useAuth } from '../auth/AuthContext';
import { can } from '../auth/permissions';
import { useSettings } from '../context/SettingsContext';
import { useData } from '../context/DataContext';
import { useToast } from '../context/ToastContext';
import { C, saveAppointment, savePrescription, saveVisit, setApptStatus } from '../data/db';
import { getDb } from '../firebase/client';
import { calcInvoice, round2 } from '../lib/calc';
import { isYmd } from '../lib/dates';
import type { Patient, Payment, Prescription, RxItem, Supply, Visit } from '../types';
import { Check, Field, Icon, Modal, Notice, Seg } from './ui';

interface Line { key: string; name: string; category: string; qty: string; rate: string; taxable: boolean; code: string; custom: boolean }
const uid = () => Math.random().toString(36).slice(2, 9);
const blankRx = (): RxItem => ({ medicine: '', dose: '', frequency: '', duration: '', instructions: '' });

export default function VisitForm({ patient, visit, prefillService, apptId, onClose, onSaved }: {
  patient: Patient; visit?: Visit; prefillService?: string; apptId?: string; onClose: () => void; onSaved: (v: Visit) => void;
}) {
  const { state } = useAuth();
  const { settings, cfg, today, money } = useSettings();
  const { services } = useData();
  const toast = useToast();
  const role = state.kind === 'ready' ? state.profile.role : undefined;
  const isNew = !visit;
  const currency = visit?.currency || settings.currency;
  const ccode = visit?.country || settings.country;
  const taxLabel = cfg.tax.label;

  // ---- clinical
  const [date, setDate] = useState(visit?.date || today());
  const [weight, setWeight] = useState(visit?.weight || '');
  const [bp, setBp] = useState(visit?.bp || '');
  const [pulse, setPulse] = useState(visit?.pulse || '');
  const [temp, setTemp] = useState(visit?.temp || '');
  const [spo2, setSpo2] = useState(visit?.spo2 || '');
  const [complaint, setComplaint] = useState(visit?.complaint || '');
  const [notes, setNotes] = useState(visit?.notes || '');
  const [advice, setAdvice] = useState(visit?.advice || '');

  // ---- billing
  const [lines, setLines] = useState<Line[]>(() => {
    if (visit) return visit.lines.map((l) => ({ key: uid(), name: l.name, category: l.category, qty: String(l.qty), rate: String(l.rate), taxable: l.taxable !== false, code: l.code || '', custom: !services.some((s) => s.name === l.name) }));
    if (prefillService) {
      const s = services.find((x) => x.name === prefillService && x.active);
      return [s ? { key: uid(), name: s.name, category: s.category, qty: '1', rate: String(s.price), taxable: s.taxable, code: s.code, custom: false }
        : { key: uid(), name: prefillService, category: '', qty: '1', rate: '0', taxable: true, code: '', custom: true }];
    }
    return [];
  });
  const [discount, setDiscount] = useState(visit?.discount ? String(visit.discount) : '');
  const [taxEnabled, setTaxEnabled] = useState(visit ? visit.taxEnabled : settings.tax.enabled);
  const [taxRate, setTaxRate] = useState(String(visit ? visit.taxRate : settings.tax.rate));
  const [inclusive, setInclusive] = useState(visit ? visit.taxInclusive : settings.tax.inclusive);
  const [supply, setSupply] = useState<Supply>(visit?.supply || settings.tax.defaultSupply);
  const [kept, setKept] = useState<Payment[]>(visit?.payments || []);
  const [payMethod, setPayMethod] = useState(settings.paymentMethods[0] || 'Cash');
  const [payAmount, setPayAmount] = useState('');
  const [payRef, setPayRef] = useState('');

  // ---- prescription (doctor / owner)
  const canRx = settings.features.prescriptions && can(role, 'prescribe');
  const [rx, setRx] = useState<RxItem[]>([]);
  const [rxNotes, setRxNotes] = useState('');
  const [rxMeta, setRxMeta] = useState<Pick<Prescription, 'createdAt' | 'createdBy'> | null>(null);
  useEffect(() => {
    if (!visit || !canRx) return;
    void getDoc(doc(getDb(), C.prescriptions, visit.id)).then((s) => {
      if (s.exists()) { const d = s.data() as Prescription; setRx(d.items); setRxNotes(d.notes || ''); setRxMeta({ createdAt: d.createdAt, createdBy: d.createdBy }); }
    }).catch(() => {});
  }, [visit, canRx]);

  // ---- next appointment (new visits)
  const [nextDate, setNextDate] = useState('');
  const [nextTime, setNextTime] = useState('10:00');

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const calc = useMemo(() => calcInvoice({
    lines: lines.map((l) => ({ name: l.name, category: l.category, qty: Number(l.qty), rate: Number(l.rate), taxable: l.taxable, code: l.code })),
    discount: Number(discount) || 0, taxEnabled, taxRate: Number(taxRate) || 0, taxInclusive: inclusive, supply, country: ccode,
    payments: kept, void: !!visit?.void, defaultDate: date
  }), [lines, discount, taxEnabled, taxRate, inclusive, supply, ccode, kept, visit?.void, date]);

  const newPay = round2(Number(payAmount) || 0);
  const dueAfter = round2(calc.total - calc.paid - newPay);

  const catalog = useMemo(() => {
    const g: Record<string, typeof services> = {};
    services.filter((s) => s.active).forEach((s) => { (g[s.category || 'Other'] ||= []).push(s); });
    return Object.entries(g).sort(([a], [b]) => a.localeCompare(b));
  }, [services]);

  const addService = (id: string) => {
    const s = services.find((x) => x.id === id); if (!s) return;
    setLines((ls) => {
      const at = ls.findIndex((l) => !l.custom && l.name === s.name);
      if (at >= 0) return ls.map((l, i) => (i === at ? { ...l, qty: String((Number(l.qty) || 0) + 1) } : l));
      return [...ls, { key: uid(), name: s.name, category: s.category, qty: '1', rate: String(s.price), taxable: s.taxable, code: s.code, custom: false }];
    });
  };
  const setLine = (k: string, p: Partial<Line>) => setLines((ls) => ls.map((l) => (l.key === k ? { ...l, ...p } : l)));

  const save = async () => {
    setErr('');
    if (!isYmd(date)) return setErr('Enter the visit date.');
    if (taxEnabled && !(Number(taxRate) >= 0 && Number(taxRate) <= 100)) return setErr(`Enter a ${taxLabel} rate between 0 and 100.`);
    if (newPay < 0) return setErr('The payment cannot be negative.');
    if (newPay > round2(calc.total - calc.paid) + 0.005) return setErr('That payment is more than the amount due.');
    if (state.kind !== 'ready') return;
    const actor = { uid: state.user.uid, name: state.profile.displayName };
    setBusy(true);
    try {
      const payments: Partial<Payment>[] = [...kept];
      if (newPay > 0) payments.push({ method: payMethod, amount: newPay, ref: payRef.trim(), date });
      const v = await saveVisit({
        id: visit?.id, baseUpdatedAt: visit?.updatedAt, date, patientId: patient.id, patientName: patient.name,
        weight, bp, pulse, temp, spo2, complaint, notes, advice,
        lines: calc.lines, discount: calc.discount, taxEnabled, taxRate: Number(taxRate) || 0, taxInclusive: inclusive, supply, payments
      }, actor, settings, role || 'none');

      if (canRx) {
        await savePrescription({
          visitId: v.id, patientId: patient.id, patientName: patient.name, patientAge: patient.age, patientGender: patient.gender,
          date: v.date, items: rx, notes: rxNotes, prescriberName: settings.practitioner || state.profile.displayName,
          prescriberReg: settings.practitionerReg, createdAt: rxMeta?.createdAt, createdBy: rxMeta?.createdBy
        }, actor);
      }
      if (isNew && nextDate && isYmd(nextDate)) {
        await saveAppointment({
          patientId: patient.id, patientName: patient.name, date: nextDate, time: nextTime, service: calc.lines[0]?.name || '', status: 'Scheduled',
          remindEmail: patient.remindEmail, remindWhatsApp: patient.remindWhatsApp, remindSms: patient.remindSms
        }, actor);
      }
      if (apptId) await setApptStatus(apptId, 'Completed', actor);
      toast(isNew ? `Visit saved · invoice ${v.invoiceNo}` : 'Changes saved');
      onSaved(v);
    } catch (e) { setErr(e instanceof Error ? e.message : 'Could not save the visit.'); setBusy(false); }
  };

  const m = (n: number) => money(n, currency);
  const methodNeedsRef = !['Cash'].includes(payMethod);

  return (
    <Modal wide title={isNew ? 'New visit' : 'Edit visit'} sub={<>{patient.name} · <span className="fileno">{patient.id}</span>{visit && <> · {visit.invoiceNo}</>}</>} onClose={onClose}
      footer={<>
        <span className="foot-total">{m(calc.total)}{(calc.paid + newPay) > 0 && <small> · due {m(Math.max(0, dueAfter))}</small>}</span>
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn primary" disabled={busy} onClick={() => void save()}>{isNew ? 'Save visit and invoice' : 'Save changes'}</button>
      </>}>
      {err && <Notice kind="err">{err}</Notice>}
      {patient.allergies && <Notice kind="warn"><b>Allergies:</b> {patient.allergies}</Notice>}
      {visit?.void && <Notice kind="warn">This invoice is void. Only the owner can change it.</Notice>}

      <fieldset className="fs"><legend>Visit</legend>
        <div className="grid g6">
          <Field label="Date" span={2} htmlFor="v-date"><input id="v-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
          <Field label="Weight (kg)" htmlFor="v-wt"><input id="v-wt" inputMode="decimal" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder={patient.weight} /></Field>
          <Field label="BP" htmlFor="v-bp"><input id="v-bp" value={bp} onChange={(e) => setBp(e.target.value)} placeholder={patient.bp || '120/80'} /></Field>
          <Field label="Pulse" htmlFor="v-pu"><input id="v-pu" inputMode="numeric" value={pulse} onChange={(e) => setPulse(e.target.value)} placeholder={patient.pulse} /></Field>
          <Field label="Temp (°C)" htmlFor="v-tp"><input id="v-tp" inputMode="decimal" value={temp} onChange={(e) => setTemp(e.target.value)} /></Field>
          <Field label="SpO₂ (%)" htmlFor="v-sp"><input id="v-sp" inputMode="numeric" value={spo2} onChange={(e) => setSpo2(e.target.value)} /></Field>
          <Field label="Complaint today" span="all" htmlFor="v-comp"><input id="v-comp" value={complaint} onChange={(e) => setComplaint(e.target.value)} /></Field>
          <Field label="Observations and treatment given" span="all" htmlFor="v-notes"><textarea id="v-notes" rows={5} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Findings, diagnosis, treatment, response to treatment" /></Field>
          <Field label="Advice to patient" span="all" htmlFor="v-adv"><textarea id="v-adv" rows={2} value={advice} onChange={(e) => setAdvice(e.target.value)} /></Field>
        </div>
      </fieldset>

      {canRx && (
        <fieldset className="fs"><legend>Prescription</legend>
          {rx.map((r, i) => (
            <div className="rx-row" key={i}>
              <input aria-label="Medicine" placeholder="Medicine" value={r.medicine} onChange={(e) => setRx(rx.map((x, k) => (k === i ? { ...x, medicine: e.target.value } : x)))} />
              <input aria-label="Dose" placeholder="Dose" value={r.dose} onChange={(e) => setRx(rx.map((x, k) => (k === i ? { ...x, dose: e.target.value } : x)))} />
              <input aria-label="Frequency" placeholder="Frequency" value={r.frequency} onChange={(e) => setRx(rx.map((x, k) => (k === i ? { ...x, frequency: e.target.value } : x)))} />
              <input aria-label="Duration" placeholder="Duration" value={r.duration} onChange={(e) => setRx(rx.map((x, k) => (k === i ? { ...x, duration: e.target.value } : x)))} />
              <input aria-label="Instructions" placeholder="Instructions (e.g. after food)" value={r.instructions} onChange={(e) => setRx(rx.map((x, k) => (k === i ? { ...x, instructions: e.target.value } : x)))} />
              <button type="button" className="icon-btn" aria-label="Remove medicine" onClick={() => setRx(rx.filter((_, k) => k !== i))}><Icon n="x" size={16} /></button>
            </div>
          ))}
          <button type="button" className="btn sm" onClick={() => setRx([...rx, blankRx()])}><Icon n="pill" size={16} />Add medicine</button>
          {rx.length > 0 && <Field label="Prescription notes" htmlFor="rx-n"><input id="rx-n" value={rxNotes} onChange={(e) => setRxNotes(e.target.value)} /></Field>}
        </fieldset>
      )}

      <fieldset className="fs"><legend>Services and charges</legend>
        {catalog.length === 0 && <p className="muted small">No services yet. Add them under Services & prices, or use “Add a custom charge”.</p>}
        {catalog.map(([cat, list]) => (
          <div className="chip-group" key={cat}>
            <div className="g">{cat}</div>
            <div className="chips">{list.map((s) => <button type="button" className="chip" key={s.id} onClick={() => addService(s.id)}>{s.name} · {m(s.price)}</button>)}</div>
          </div>
        ))}
        <button type="button" className="btn sm" onClick={() => setLines([...lines, { key: uid(), name: '', category: '', qty: '1', rate: '', taxable: true, code: '', custom: true }])}><Icon n="plus" size={16} />Add a custom charge</button>

        {lines.length > 0 && (
          <div className="lines" role="table" aria-label="Charges">
            {lines.map((l) => (
              <div className="line" role="row" key={l.key}>
                <div className="ln-name">{l.custom
                  ? <input aria-label="Description" placeholder="Description" value={l.name} onChange={(e) => setLine(l.key, { name: e.target.value })} />
                  : <span>{l.name}</span>}</div>
                <label className="ln-q"><span>Qty</span><input inputMode="decimal" value={l.qty} onChange={(e) => setLine(l.key, { qty: e.target.value })} /></label>
                <label className="ln-r"><span>Rate</span><input inputMode="decimal" value={l.rate} onChange={(e) => setLine(l.key, { rate: e.target.value })} /></label>
                <div className="ln-a money">{m(round2((Number(l.qty) || 0) * (Number(l.rate) || 0)))}</div>
                {taxEnabled && <label className="ln-t" title={`${taxLabel} applies to this line`}><input type="checkbox" checked={l.taxable} onChange={(e) => setLine(l.key, { taxable: e.target.checked })} /><span>{taxLabel}</span></label>}
                <button type="button" className="icon-btn" aria-label={`Remove ${l.name || 'charge'}`} onClick={() => setLines(lines.filter((x) => x.key !== l.key))}><Icon n="x" size={16} /></button>
              </div>
            ))}
          </div>
        )}

        <div className="bill-grid">
          <div className="bill-left">
            <Field label="Discount" htmlFor="v-disc"><input id="v-disc" inputMode="decimal" value={discount} onChange={(e) => setDiscount(e.target.value)} placeholder="0" /></Field>
            <label className="toggle compact">
              <input type="checkbox" checked={taxEnabled} onChange={(e) => setTaxEnabled(e.target.checked)} />
              <span className="track" aria-hidden="true"><span className="thumb" /></span>
              <span className="tl"><b>Charge {taxLabel}</b><small>Only if the clinic is registered / the service is taxable</small></span>
            </label>
            {taxEnabled && (
              <div className="tax-box">
                <Field label={`${taxLabel} rate (%)`} htmlFor="v-tr">
                  <input id="v-tr" list="rates" inputMode="decimal" value={taxRate} onChange={(e) => setTaxRate(e.target.value)} />
                  <datalist id="rates">{cfg.tax.presets.map((p) => <option key={p} value={p} />)}</datalist>
                </Field>
                <Check checked={inclusive} onChange={setInclusive}>Prices already include {taxLabel}</Check>
                {cfg.tax.supportsSupplySplit && (
                  <Field label="Place of supply">
                    <Seg label="Place of supply" value={supply} onChange={setSupply} options={[{ v: 'intra', l: 'Same state (CGST + SGST)' }, { v: 'inter', l: 'Other state (IGST)' }]} />
                  </Field>
                )}
              </div>
            )}
          </div>
          <div className="totals">
            <div className="row"><span>Subtotal</span><span className="money">{m(calc.subtotal)}</span></div>
            {calc.discount > 0 && <div className="row"><span>Discount</span><span className="money">−{m(calc.discount)}</span></div>}
            {taxEnabled && calc.tax > 0 && calc.taxBreakup.map((t) => <div className="row" key={t.label}><span>{t.label} @ {t.rate}%</span><span className="money">{m(t.amount)}</span></div>)}
            <div className="row big"><span>Total</span><span className="money">{m(calc.total)}</span></div>
            {calc.paid > 0 && <div className="row"><span>Already paid</span><span className="money">{m(calc.paid)}</span></div>}
            {newPay > 0 && <div className="row"><span>Paying now</span><span className="money">{m(newPay)}</span></div>}
            <div className={'row bal' + (dueAfter > 0.005 ? ' due' : '')}><span>Balance</span><span className="money">{m(Math.max(0, dueAfter))}</span></div>
          </div>
        </div>
      </fieldset>

      <fieldset className="fs"><legend>Payment</legend>
        {kept.length > 0 && (
          <ul className="paylist">{kept.map((p) => (
            <li key={p.id}><span>{p.date} · {p.method}{p.ref ? ` · ${p.ref}` : ''}</span><b className="money">{m(p.amount)}</b>
              {role === 'owner' && <button type="button" className="icon-btn" aria-label="Remove this payment" onClick={() => setKept(kept.filter((x) => x.id !== p.id))}><Icon n="trash" size={15} /></button>}
            </li>))}</ul>
        )}
        <div className="grid g4">
          <Field label="Method" htmlFor="v-pm"><select id="v-pm" value={payMethod} onChange={(e) => setPayMethod(e.target.value)}>{settings.paymentMethods.map((x) => <option key={x}>{x}</option>)}</select></Field>
          <Field label="Amount received now" htmlFor="v-pa" hint={calc.total - calc.paid > 0 ? <button type="button" className="link" onClick={() => setPayAmount(String(round2(calc.total - calc.paid)))}>Full amount ({m(round2(calc.total - calc.paid))})</button> : undefined}>
            <input id="v-pa" inputMode="decimal" value={payAmount} onChange={(e) => setPayAmount(e.target.value)} placeholder="0" /></Field>
          <Field label={methodNeedsRef ? 'Reference / transaction code' : 'Reference (optional)'} span={2} htmlFor="v-pr"><input id="v-pr" value={payRef} onChange={(e) => setPayRef(e.target.value)} /></Field>
        </div>
      </fieldset>

      {isNew && (
        <fieldset className="fs"><legend>Next session (optional)</legend>
          <div className="grid g4">
            <Field label="Date" htmlFor="v-nd"><input id="v-nd" type="date" min={date} value={nextDate} onChange={(e) => setNextDate(e.target.value)} /></Field>
            <Field label="Time" htmlFor="v-nt"><input id="v-nt" type="time" value={nextTime} onChange={(e) => setNextTime(e.target.value)} /></Field>
          </div>
        </fieldset>
      )}
    </Modal>
  );
}
