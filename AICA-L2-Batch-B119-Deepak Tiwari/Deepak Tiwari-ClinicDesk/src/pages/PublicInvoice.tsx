import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { doc, getDoc } from 'firebase/firestore';
import { getDb } from '../firebase/client';
import { C } from '../data/db';
import { InvoiceDoc } from '../components/Docs';
import { Spinner } from '../components/ui';
import type { PublicInvoice } from '../types';

/** What a patient sees when they open the link from WhatsApp / email. No sign-in, no clinical data. */
export default function PublicInvoicePage() {
  const { key = '' } = useParams();
  const [data, setData] = useState<PublicInvoice | null>(null);
  const [state, setState] = useState<'loading' | 'ok' | 'bad'>('loading');
  useEffect(() => {
    const m = document.createElement('meta'); m.name = 'robots'; m.content = 'noindex,nofollow'; document.head.appendChild(m);
    if (!/^[a-f0-9]{40}$/.test(key)) { setState('bad'); return () => { m.remove(); }; }
    getDoc(doc(getDb(), C.publicInvoices, key)).then((s) => {
      if (s.exists()) { setData(s.data() as PublicInvoice); setState('ok'); } else setState('bad');
    }).catch(() => setState('bad'));
    return () => { m.remove(); };
  }, [key]);
  if (state === 'loading') return <Spinner label="Loading invoice…" />;
  if (state === 'bad' || !data) return <div className="gate"><main className="gate-card" id="main"><h1>Invoice not found</h1><p className="lead">This invoice link is not valid.</p></main></div>;
  return (
    <main className="public" id="main">
      <div className="public-bar no-print"><span>{data.clinic.name}</span><button className="btn primary sm" onClick={() => window.print()}>Print / Save as PDF</button></div>
      <InvoiceDoc clinic={data.clinic} inv={data.invoice} />
    </main>
  );
}
