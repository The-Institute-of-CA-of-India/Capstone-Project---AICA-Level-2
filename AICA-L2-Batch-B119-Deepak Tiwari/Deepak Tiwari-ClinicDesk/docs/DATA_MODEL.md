# Firestore data model

Dates are ISO strings (`2026-11-04`, `2026-11-04T09:30:00.000Z`). Money is a number with 2 decimals in the
invoice's own currency. All collections are top-level unless noted. No composite indexes are needed.

| Collection / doc | Key | Written by | Purpose |
|---|---|---|---|
| `meta/init` | fixed | first owner (once) | Marks the clinic as initialised; stops anyone else becoming owner. |
| `users/{uid}` | Firebase Auth uid | self (create), owner (role/status) | `displayName, email, phone, role (owner/doctor/reception/none), status (active/pending/disabled), createdAt, lastLoginAt` |
| `invites/{emailOrE164}` | lower-case verified email, or `+E.164` phone | owner | `role, note, createdBy, createdAt` — gives that role on first sign-in. |
| `settings/clinic` | fixed | owner | Whole clinic profile: country, currency, name, logo URL/path, contacts, `taxIds`, `tax {enabled, rate, inclusive, defaultSupply}`, prefixes, payment methods/details, titles, footer, disclaimer, consent text, message templates, features, `idleMinutes`. |
| `services/{id}` | auto id | owner | Price list: `name, category, price, minutes, taxable, code (HSN/SAC), active`. |
| `counters/{name}` | `patients`, `invoice-YYYY` | staff (transaction) | `{ next }` — only ever increases by exactly 1 (enforced by rules). |
| `patients/{FN-0001}` | file number | staff | Health card: identity, contacts (E.164), `idNumber`, emergency contact, vitals, history, medication, allergies, reminder preferences, consent + time. |
| `patients/{id}/files/{fileId}` | auto id | staff / clinician delete | Metadata for an uploaded document: `name, path (Storage), size, contentType, uploadedBy/At`. |
| `visits/{id}` | auto id | staff | One visit = one invoice (as in the original). Clinical: `weight, bp, pulse, temp, spo2, complaint, notes, advice`. Billing: `invoiceNo, shareKey, currency, country, lines[], discount, taxEnabled, taxRate, taxInclusive, supply, subtotal, taxableValue, tax, taxBreakup[], total, payments[], paid, balance, status, void*`. |
| `prescriptions/{visitId}` | the visit id | doctor / owner | `items[{medicine,dose,frequency,duration,instructions}], notes, prescriberName, prescriberReg`, patient snapshot. |
| `appointments/{id}` | auto id | staff | `date, time, patientId, service, status, notes, remindEmail/WhatsApp/Sms, *RemindedAt`. |
| `publicInvoices/{shareKey}` | 40 hex chars | staff (with each invoice save) | Snapshot behind the patient link: clinic letterhead, lines, totals, payments. **No clinical data, no patient phone/email.** Readable by `get` only (no listing). |
| `activityLog/{id}` | auto id | staff (append-only) | Audit trail: voids, settings saved, price list saved, users invited/changed, uploads, invoice messages opened. Owner reads. |

Storage layout: `branding/logo-<timestamp>.png` (public read, owner write) and
`patients/{patientId}/{fileId}-{name}` (staff only).

## Legacy → new mapping

| Legacy sheet tab | New |
|---|---|
| Patients | `patients` |
| Visits (invoice per visit) | `visits` (+ `publicInvoices` snapshot, + `prescriptions`) |
| Appointments | `appointments` |
| Services | `services` |
| Settings | `settings/clinic` |
| Message Log | `activityLog` |
| Script Properties (passwords, sequence counters) | Firebase Auth + `users` roles; `counters` |
