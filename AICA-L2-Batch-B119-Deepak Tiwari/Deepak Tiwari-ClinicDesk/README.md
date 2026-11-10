> **AICA Level 2 capstone submission** by Deepak Tiwari. Built with Claude (design and code), Firebase (backend) and Google AI Studio (publishing).
> See [`AI-USAGE.md`](AI-USAGE.md) for how AI was used and what I did myself. No keys or private data are included.

# Clinic Manager (Kenya & India) — Firebase PWA

A clinic management web app that installs like a phone app (PWA) and works on phones, tablets and computers.
Patients and health cards, appointments and reminders, visits with clinical notes, prescriptions, invoices and
receipts, payments, reports, price list, team roles and clinic branding — for clinics in **Kenya (KES, VAT)** or
**India (INR, GST)**.

It is a plain **Vite + React + TypeScript** project. The backend is **your own Firebase project**
(Authentication, Firestore, Storage, optional Hosting). There is no server code to run and **no one else's keys,
project, or data are included**.

> **Not legal or tax advice.** Tax rates, tax identifiers and document wording are starting defaults, editable in
> Settings. Have a qualified accountant or lawyer review them before issuing invoices.

---

## What you get

| Area | Details |
|---|---|
| **Sign-in** | Google, email + password (with email verification and password reset), or mobile number (SMS code). |
| **Roles** | **Owner** (everything), **Doctor** (clinical + billing + reports), **Front desk** (patients, appointments, visits, payments). The first person to sign in becomes the owner; others are invited or approved by the owner. |
| **Patients** | Health cards with auto file numbers, vitals, history, allergies, consent, reminders preferences, duplicate warning, document uploads (Storage). |
| **Visits & invoices** | Clinical notes, vitals, service picker, discount, tax (per-line taxable flag), part payments, auto invoice numbers per year, void/restore (owner only). |
| **Prescriptions** | Medicine table on a visit, printable with clinic letterhead. |
| **Appointments** | Day view, check-in (opens the visit with the service added), no-show/cancel, one-tap WhatsApp / SMS / email reminders. |
| **Documents** | Invoice, payment receipt, prescription, report — all with the clinic's logo, name, tax IDs and footer; Print / Save as PDF. |
| **Patient invoice link** | A private link (40 random characters) opens a read-only invoice — no sign-in, no clinical data. WhatsApp messages carry only the clinic name and that link. |
| **Reports** | Revenue by period, service, payment method, tax collected, unpaid-invoice ageing, CSV export. |
| **Settings** | Clinic name, logo, address, phone, email, website, registration number, brand colour, **country**, currency, tax rules, tax IDs, payment details, titles, footer, disclaimers, message templates, idle sign-out. |
| **PWA** | Installable, app icons (from the supplied logo), never caches patient data. |

### Country packs (Kenya / India)

Choosing the country in Settings switches, from one file (`src/config/countries.ts`):

| | Kenya | India |
|---|---|---|
| Currency | KES | INR (lakh-style grouping, ₹) |
| Phone | `07xx`/`01xx` → `+254…` | 10 digits starting 6–9 → `+91…` |
| Tax | VAT (default 16 %, **off**) | GST (default 18 %, **off**) split into **CGST + SGST** or **IGST** |
| Tax IDs | KRA PIN | GSTIN, PAN (optional) |
| Registration labels | KMPDC no., facility licence | Medical council no., clinical-establishment no. |
| Payments | Cash, M-Pesa (Paybill/Till), Card, Bank, Insurance | Cash, UPI, Card, Bank, Cheque, Insurance |
| Wording | Data Protection Act, 2019 consent/disclaimer | Indian data-protection wording |

All rates, titles and wording are editable. Existing invoices keep the currency and tax they were issued with.

---

## Project layout

```
clinicdesk/
├─ index.html                 PWA meta, fonts
├─ public/                    manifest.webmanifest, sw.js (service worker), icons/
├─ src/
│  ├─ main.tsx · App.tsx      entry, routes, sign-in gate, idle sign-out
│  ├─ styles.css              all styling (responsive: phone / tablet / desktop, print)
│  ├─ config/                 countries.ts (Kenya/India packs), defaults.ts, firebase.config.example.json
│  ├─ firebase/               config.ts (reads your keys), client.ts
│  ├─ auth/                   AuthContext.tsx (Google / email / phone), permissions.ts
│  ├─ context/                Settings, Data, Toast
│  ├─ data/                   db.ts (all writes), hooks.ts (live queries)
│  ├─ lib/                    calc.ts (invoice maths), phone.ts, money.ts, dates.ts, csv.ts, …
│  ├─ components/             Layout, Docs (invoice/receipt/Rx), VisitForm, PatientForm, …
│  └─ pages/                  Login, Dashboard, Patients, PatientDetail, Appointments,
│                             Billing, Services, Reports, Users, Settings, PublicInvoice
├─ tests/                     unit tests (incl. parity with the original invoice maths)
├─ firestore.rules · storage.rules · firestore.indexes.json · firebase.json
├─ scripts/make-icons.mjs     regenerate app icons from your logo
└─ docs/                      DATA_MODEL.md · SECURITY.md · MIGRATION.md
```

---

## Setup, step by step

You need **Node.js 20+** and a Google account. Everything below can be done in a browser except step 6/9
(a terminal).

### 1. Create a Firebase project
1. Go to <https://console.firebase.google.com> → **Add project** → name it (e.g. `my-clinic`).
2. Google Analytics is not needed; you can switch it off.

### 2. Turn on Authentication
**Build → Authentication → Get started → Sign-in method**, then enable:
- **Google** (choose a support email).
- **Email/Password** (leave "Email link" off).
- **Phone** — see the note below.

**Settings → Authorized domains:** `localhost` is there already. **Add every address you will serve the app from**
(your `*.web.app` / `*.firebaseapp.com` are added automatically; add your own domain, and any AI Studio / Cloud Run
address). If you skip this, sign-in fails with "unauthorized domain".

> **Phone sign-in notes.** SMS costs money, so Firebase limits it: new projects get a small free daily quota and
> heavier use needs the **Blaze (pay-as-you-go)** plan. Check *Authentication → Settings → SMS region policy* and
> allow **Kenya** and/or **India**. While developing you can add **test phone numbers** (Authentication → Sign-in
> method → Phone → *Phone numbers for testing*) that need no SMS. Clinics that want to avoid SMS can simply rely on
> Google / email sign-in.

### 3. Create the Firestore database
**Build → Firestore Database → Create database** → choose a location near you (e.g. `africa-south1`
Johannesburg for Kenya, `asia-south1` Mumbai for India — the location cannot be changed later) → **Start in
production mode**. You will publish the real rules in step 7.

### 4. Turn on Storage
**Build → Storage → Get started** (production mode, same location). Storage holds the logo and patient documents.
Firebase may require the Blaze plan to create a storage bucket; the free monthly allowance is generous for a
small clinic, and you can set a budget alert.

### 5. Add a web app and copy its configuration
**Project settings (gear) → General → Your apps → Add app → Web (`</>`)** → register (no Hosting needed here) →
copy the `firebaseConfig` values.

### 6. Put the configuration in the project
Either create **`.env.local`** (copy `.env.example`):

```
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_STORAGE_BUCKET=...
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...
```

…or copy `src/config/firebase.config.example.json` to `src/config/firebase.config.json` and fill it in
(this file is git-ignored). If your AI Studio / Firebase integration generates a `firebase-applet-config.json`
in the project root, the app reads that too. If you use a *named* Firestore database, set
`VITE_FIREBASE_FIRESTORE_DB_ID` (the security rules in this repo are written for the `(default)` database).

These values are **not secrets** — they identify your project to the browser. Never put a service-account key
in this project.

Then run it:

```bash
npm install
npm run dev          # http://localhost:3000
npm test             # optional: unit tests
npm run build        # production build into dist/
```

### 7. Publish the security rules (do this before real use)
With the Firebase CLI:

```bash
npm install -g firebase-tools
firebase login
cp .firebaserc.example .firebaserc        # then edit: your project ID
firebase deploy --only firestore:rules,firestore:indexes,storage
```

Or paste the contents of `firestore.rules` and `storage.rules` into the console (**Firestore → Rules**,
**Storage → Rules**) and press **Publish**.

**Storage + Firestore link.** `storage.rules` looks up the user's role in Firestore. The first time you publish
them, Firebase asks to grant Storage permission to read Firestore — accept. If uploads later fail with
"permission denied" for a signed-in staff member, re-publish the Storage rules and confirm that prompt.

### 8. First sign-in = owner
**Open the app yourself, immediately after publishing the rules, and sign in.** The first person to sign in is
asked for the country and clinic name and becomes the **owner**. Do this before you share the address with anyone.
Then in the app:

1. **Settings** — clinic name, upload the logo, address, phone, email, registration number, tax IDs, payment
   details. Check the country/currency/tax (tax is **off** until you switch it on). **Save.**
2. **Services & prices** — replace the sample prices.
3. **Team** — invite staff by email or mobile number, choosing Doctor or Front desk. When they sign in with that
   email (Google or password) or number, they get that role automatically. Anyone else who signs in lands on
   "waiting for approval" and appears under *Waiting for approval*.
4. Create a test patient with your own phone/email, record a visit, open the invoice, try WhatsApp / Email / Print.
   Void the test invoice afterwards.

### 9. Deploy

**Option A — Firebase Hosting (recommended; one address for the app and sign-in).**

```bash
npm run build
firebase deploy --only hosting       # or:  npm run deploy   (rules + hosting)
```

Your app is at `https://YOUR-PROJECT-ID.web.app`. `firebase.json` already has the single-page-app rewrite,
cache headers (so updates are picked up) and security headers.

**Option B — build and publish from Google AI Studio.**
AI Studio's Build mode changes often, so treat these as the outline and check its current help:
1. Create a new app in AI Studio **Build** and bring this project in (upload the folder / import from GitHub, or
   paste the files). It is a standard Vite + React + TypeScript app (`npm run dev` / `npm run build`).
2. Add the six `VITE_FIREBASE_*` values as environment variables / secrets for the app, or add
   `src/config/firebase.config.json`.
3. Run it in the preview and test sign-in. In preview and embedded frames, pop-ups can be blocked — the app falls
   back to a full-page Google redirect automatically.
4. Use AI Studio's **Deploy** to publish. **Then add the published address to Firebase
   *Authentication → Settings → Authorized domains*.** Without this, Google/phone sign-in fails on the published app.
5. Still publish the rules (step 7) — rules are enforced by Firebase, not by where the app is hosted.

For Safari / iPhone installed apps, sign-in is most reliable when the app and `authDomain` share a domain: with
Firebase Hosting, set `VITE_FIREBASE_AUTH_DOMAIN` to your own hosted domain (e.g. `my-clinic.web.app`).

### 10. Install it on phones and tablets
Open the address in Chrome/Edge (Android, Windows) → **Install app** (or the install button in the app's
menu). On iPhone/iPad open it in **Safari → Share → Add to Home Screen**.

---

## Customising

- **Names, address, logo, colours, tax, wording:** all in the app under **Settings** — no code changes.
- **Installed-app icon:** the home-screen icon is static. To change it, run
  `npm run icons -- path/to/your-logo.png` (use a PNG with a *real* transparent background) and redeploy.
  Also edit `name` / `short_name` in `public/manifest.webmanifest` and the `<title>` in `index.html`.
- **Another country:** copy a pack in `src/config/countries.ts`, add its code to `CountryCode` in `src/types.ts`.
- **Constitution (Ayurveda) field / prescriptions:** switch on or off in Settings → Features.
- **Fonts:** loaded from Google Fonts in `index.html`; remove that line to use system fonts only.

## Automatic reminders & email (what replaced the Apps Script jobs)

The original system emailed from the owner's Google account and had an 8 am trigger. A browser app has no
background server, so:

- **Reminders** — the Appointments page lists tomorrow's appointments with one-tap **WhatsApp / SMS / Email**
  buttons. Each opens the device's own app with the message ready; a person presses Send. This also keeps
  patient messages inside the clinic's own phone/mail accounts.
- **Invoices by email** — opens your email app with the message and the private invoice link (no attachment;
  the patient opens the link and can Save as PDF).
- **Truly automatic reminders/emails** need server code. The usual route is a scheduled **Cloud Function**
  (Blaze plan) that reads tomorrow's appointments with the Admin SDK and sends through an email/SMS provider,
  or Firebase's *Trigger Email from Firestore* extension. This is **not included** — it adds cost and provider
  accounts, and should be set up by someone comfortable with Firebase.

## Backups & data protection

- Turn on **Firestore scheduled backups / point-in-time recovery** (Firestore → Disaster recovery) or export
  regularly with `gcloud firestore export`.
- Patient records and invoices **cannot be deleted from the app** (financial and clinical record-keeping). For a
  legal erasure request, an owner/administrator removes data in the Firebase console.
- Patient data is held in memory only on the device (no offline disk cache), and the app signs people out after
  inactivity (default 30 minutes, configurable).
- File download links from Storage are long, unguessable links; anyone with a link can open that file. Revoke
  a token in the console if a link leaks.
- Health data is sensitive personal data in both countries. Register / comply as your local law requires
  (Kenya: Data Protection Act 2019; India: DPDP Act 2023). See `docs/SECURITY.md`.

## Known limits

- **Totals are calculated in the browser.** Firestore rules cannot recompute an invoice, so a technically
  skilled *signed-in staff member* could write wrong totals. Staff are trusted users; every void/restore and
  settings change is logged. Hardening option: move invoice saving into a Cloud Function.
- **All patients load at sign-in** (like the original). Comfortable for thousands of patients; for tens of
  thousands, add server-side search/paging.
- **Not an e-invoicing system.** Documents are not KRA eTIMS invoices and not GST e-invoices (IRN/QR).
- Front desk can read clinical notes (as in the original system). Separate collections would be needed for
  stricter confidentiality.
- Two people editing one invoice at once: the second save is refused with a clear message (no silent overwrite).

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Connect your Firebase project" screen | Step 6 — keys missing; restart `npm run dev` after creating `.env.local`. |
| "Unauthorized domain" on sign-in | Add the address under Authentication → Settings → Authorized domains. |
| "This sign-in method is not switched on" | Step 2 — enable that provider. |
| Phone: "billing not enabled" / quota | Use test numbers, Google/email sign-in, or upgrade to Blaze. |
| "Missing or insufficient permissions" everywhere | Rules not published (step 7), or the user's role is `none`/pending — approve them under Team. |
| Logo/document upload fails | Re-publish `storage.rules` and accept the Firestore link prompt; file must be PNG/JPG/WebP (logo) or image/PDF ≤ 10 MB. |
| New version not showing | Hard-reload once; the service worker fetches pages network-first. |
| Locked out as owner | In the Firestore console set your `users/{uid}` document to `role: owner`, `status: active`. |

## Commands

```
npm run dev        local development
npm run build      type-check + production build
npm test           unit tests (invoice maths, phones, documents)
npm run icons      regenerate app icons
npm run deploy     build + firebase deploy
```
