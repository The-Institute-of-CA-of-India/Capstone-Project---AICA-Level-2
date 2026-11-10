# Migration note: Apps Script + Google Sheet + Netlify → Firebase PWA

## What changed

| Original | Now |
|---|---|
| Google Apps Script (`Code.gs`) as the API | No server. The React app talks straight to Firestore, protected by security rules. Business logic moved to `src/lib/calc.ts` and `src/data/db.ts`. |
| Google Sheet as the database | Firestore (collections in `DATA_MODEL.md`). |
| Two shared passwords (owner / front desk) held in the script | Real accounts: Google, email + password, or mobile SMS code, with roles Owner / Doctor / Front desk, invitations and approval. 15-failure lockout replaced by Firebase's own throttling. |
| Hard-coded clinic identity (name, doctor, phones, address, email, PIN, prices) | Removed. Everything is configurable in Settings; sample services only. |
| Kenya only (KES, VAT, M-Pesa) | Kenya **and** India selectable (currency, phone rules, tax label/rate/split, tax IDs, payment methods, wording). |
| Netlify static hosting | Firebase Hosting or Google AI Studio deployment. |
| Logo pasted into settings | Logo upload to Firebase Storage; shown on header, invoices, receipts, prescriptions, reports. |
| Server-side invoice maths | Same arithmetic in the browser (verified identical to the original on 500 random invoices), plus per-line taxable flag and CGST/SGST/IGST. |
| PDF e-mailed by `MailApp` from the owner's Google account | Invoice opens the staff member's email app with a private link; recipient can Save as PDF. |
| 8 am daily reminder trigger | Reminder queue with one-tap WhatsApp / SMS / email; unattended sending needs a Cloud Function (not included). |
| Public invoice endpoint (`?inv=`) | `publicInvoices/{key}` read-only snapshot, same privacy rule (no clinical data). |
| Message Log tab | `activityLog` (append-only) |
| Service worker never caching API calls | Same; Firebase traffic is cross-origin and ignored by the service worker; Firestore uses a memory-only cache. |

## Kept as it was
Single practice, one visit = one invoice, invoice numbers per year, file numbers, patient consent recording,
duplicate warning, part payments, void by owner only, WhatsApp privacy rule (clinic name + link only), no offline
patient data, "VAT starts off".

## New
Doctor role, prescriptions, receipts, patient documents, temperature/SpO₂, emergency contact, per-line tax,
reports with tax and ageing, CSV export, idle sign-out, installable PWA with phone/tablet layout, audit log,
optimistic-concurrency check on invoice edits.

## Not migrated
- **Existing data** (patients, visits) is not imported. A one-off import (export Sheet → CSV → script using the
  Firebase Admin SDK) can be written if you want the history moved.
- **Automatic server-side reminders and emailed PDF attachments** (see above).
- **Old passwords** no longer exist; the originals in the supplied `Code.gs` should be treated as exposed and
  changed anywhere they are still used.
