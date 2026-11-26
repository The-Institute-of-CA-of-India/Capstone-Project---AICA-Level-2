# Accounting Setu
**From Documents to Complete Accounting.** — a multi-tenant accounting, GST and financial-automation SaaS for CA firms, built with Python + Streamlit.

Platform owner (Super Admin) → CA firms (own branded workspace, staff, roles) → business clients (simple upload portal).
Clients upload documents; OCR/AI reads them; a deterministic Python engine produces double-entry vouchers; CA staff review and approve;
bank statements are reconciled; GST returns are prepared; reports are generated; vouchers export to Tally; months are finalized and locked.

---

## 1. Quick start (local, no external services)

```powershell
pip install -r requirements.txt
copy .env.example .env
python -m scripts.seed_demo      # optional demo data
streamlit run app.py
```
Open http://localhost:8501. Without demo data, the first visit shows a one-time **Super Admin setup** screen.

### Who signs up, who approves

The first screen asks **"Login as CA Firm"** or **"Login as Client"**.

* **A CA firm registers itself** (under "Login as CA Firm → Register new CA firm"). On submit, the system generates a
  **serial number**, a **secret client code**, a **login ID** and a **first password** — shown once and emailed. The firm
  is created with status **`pending`** and **cannot do anything** until the **Super Admin (platform owner) approves it**.
  The Super Admin is notified in-app (🔔 in the sidebar, plus a banner on Overview / CA Firms) and approves from the
  **CA Firms** page with one click. This is the default (`require_firm_approval`, Super Admin → Platform Settings — can be
  turned off there if you want firms to start instantly).
* **A client registers itself** (under "Login as Client → Register") by entering their own details (PAN, Aadhaar where
  required, GSTIN if any) **and the CA firm's secret client code** — the code is asked only once, at this step, and links
  the client to that firm for good. A client can only join a firm that is **active** (i.e. already approved).
* Both get a **system-generated first password** and must set their own password at first sign-in. Passwords can be any
  characters (letters/digits/symbols), at least 6, no spaces — there is no other composition rule.
* **Isolation**: the Super Admin's dashboard lists CA firms only — never a client, never a firm's documents or books. A CA
  firm's own dashboard shows only its own clients and data; no firm can see another firm's firms, clients or data.

### Demo accounts (local demo data only)
All demo accounts share the password in `scripts/seed_demo.py` (`DEMO_PASSWORD`).

| Role | Login |
|---|---|
| Super Admin | owner@setu.demo |
| Firm Admin — Kapoor & Associates | admin@kapoorca.demo |
| Accountant (assigned to Shree Ganesh Traders) | accountant@kapoorca.demo |
| Partner | partner@kapoorca.demo |
| Client — Shree Ganesh Traders | owner@ganeshtraders.demo |
| Firm Admin — Mehta CA (second tenant) | admin@mehtaca.demo |

The demo client has already submitted last month's documents (a 2-invoice purchase PDF that the pipeline splits, a sales invoice and a bank CSV).
Select **last month** in the sidebar to review them. (The demo seed creates and approves both firms directly, as a
shortcut; real firms go through self-signup + Super Admin approval — see below.)

## 2. Run the tests
```powershell
python -m pytest -q
```
Last run: **116 passed** (see §9). These always run on an isolated local SQLite database — `tests/conftest.py` forces
`DATA_BACKEND=local` regardless of `.env`, so running the suite never touches your Supabase project.

To check the **live Supabase project** instead (reads `.env`, needs `DATA_BACKEND=supabase`):
```powershell
python -m scripts.apply_migrations --check   # read-only: lists existing tables
python -m scripts.apply_migrations           # applies 001–005 (refuses a project with foreign tables)
python -m scripts.rls_check                  # cross-tenant RLS test in one rolled-back transaction
python -m scripts.supabase_e2e               # full signup→approval→documents→voucher→cross-tenant check; cleans up after itself
```

## 3. Project structure
```
app.py                    Streamlit entry: session, tenant resolution, role-based navigation
config.py                 Settings from environment (.env)
database/
  migrations/001_schema.sql   44 tables (single source of truth; SQLite translated automatically)
  migrations/002_rls.sql      Row Level Security, helper functions, locked-period & balance triggers, append-only audit
  migrations/003_storage.sql  Private storage bucket + tenant path policies
  migrations/004_grants.sql   Table privileges for the 'authenticated' API role (RLS policies then filter rows)
  migrations/005_firm_codes.sql  Firm serial number + secret client code; client self-signup fields (PAN/Aadhaar/GSTIN)
  schema.sql / policies.sql   Concatenated copies for reading / manual application
services/
  db.py                   SQLite + Postgres(pg8000, RLS identity per transaction) backends
  tenancy.py              AuthContext, require_client / scoped_get — server-side authorization
  auth_service.py         Login (scrypt / Supabase Auth), lockout, registration, staff, invitations, password reset
  admin_service.py        Super Admin: firms, plans, limits, platform settings, metrics, logs
  firm_service.py         Firm profile/logo/settings, clients, staff assignment, deadlines, dashboard
  storage_service.py      Private storage (local FS / Supabase Storage), tenant-scoped paths
  ocr_service.py          PDF text (PyMuPDF), Tesseract OCR adapter, table reading, page rendering
  invoice_parser.py       Local rule-based extraction, multi-invoice splitting, register import
  ai_service.py           Provider interface: Anthropic Claude adapter + local rules fallback
  document_service.py     Upload → validate → extract → validate → review → approve pipeline, clarifications
  accounting_engine.py    Chart of accounts, ledger mapping, invoice→voucher rules, numbering, approval, balances
  bank_service.py         Statement parsing, classification, auto/manual matching, bank vouchers, BRS
  gst_service.py, gst_rules.py   GSTR-1, GSTR-3B (Rule 88A set-off), GSTR-2B reconciliation, versioned rules
  tally_service.py        Tally XML (masters + vouchers), preview/validation, duplicate-export tracking
  report_service.py       TB, P&L, Balance Sheet (provisional checks), registers, ledgers, ageing, PDF/Excel
  period_service.py       Month finalization, snapshot + hash, locking, reopen with reason
  assistant_service.py    AI assistant: intent → deterministic Python query
  notification_service.py In-app notifications, SMTP or local outbox email
  audit_service.py        Append-only audit log, system error log
views/                    One module per screen (super admin, firm, client portal)
ui/common.py              Theme (navy/white/grey/gold), badges, tables, error handling
utils/                    Decimal helpers, GSTIN/invoice/tax validators, role permissions
scripts/seed_demo.py      Demo data loader (local only)
scripts/apply_migrations.py  Applies database/migrations/*.sql to SUPABASE_DB_URL (idempotent, refuses foreign tables)
scripts/rls_check.py      Live cross-tenant RLS test against Supabase, rolled back in one transaction
scripts/supabase_e2e.py   Full live check: signup → Super Admin approval → documents → voucher → cross-tenant denial
tests/                    116 automated tests incl. UI smoke tests for every page and role (always local, never live)
```
(`views/` is used instead of `pages/` so Streamlit's automatic multipage discovery doesn't bypass the role-based `st.navigation`.)

## 4. Security model
* **Tenant identity is never taken from the UI.** Each rerun rebuilds `AuthContext` from the logged-in user id via `firm_staff` / `client_users`
  (`auth_service.build_context`). Every service call re-checks the client with `tenancy.require_client` or `scoped_get`;
  out-of-scope records raise `NotFound`, so other tenants' records are not even confirmed to exist.
* **Roles**: Firm Admin, CA/Partner, Accountant, Audit Staff, GST Executive, Reviewer, Read-Only, with per-user grant/revoke overrides
  (`utils/permissions.py`, mirrored in SQL `has_permission`). Non-admin staff see only assigned clients.
* **Super Admin** sees firms, plans, usage counts and logs — not client documents or books.
* **Database RLS (Supabase)**: every table has RLS enabled and forced; policies use `auth.uid()` through SECURITY DEFINER helpers.
  App queries for a user run as role `authenticated` with `request.jwt.claims` set, so Postgres enforces isolation *in addition* to Python checks.
  Triggers block changes in finalized periods, approval of unbalanced vouchers, and any update/delete of `audit_logs`.
* **Firm approval**: every self-registered CA firm starts `pending` and has no working permissions until the Super Admin
  approves it (`require_firm_approval`, on by default — Super Admin → Platform Settings to turn off). A client can only
  join a firm that is already `active`; a firm's secret client code is rejected for a pending firm.
* **Files**: private bucket, path `{firm_id}/{client_id}/…`, storage policies check the path against membership; bytes are only served after
  authorization (`document_service.read_document_bytes`). Uploads are checked for extension, size and magic bytes (disguised files rejected,
  macro-enabled XLSX rejected). Originals are immutable.
* Passwords: scrypt (local) / Supabase Auth; 5 failed logins → 15 min lockout; generic login errors; single-use 1-hour reset tokens;
  no account enumeration on reset; temporary passwords must be changed; session timeout (`SESSION_TIMEOUT_MINUTES`).
* Secrets only in `.env` (never committed). The service-role key is used only by the server process.

## 5. Supabase setup (DATA_BACKEND=supabase)
1. Create a Supabase project (region near your users, e.g. `ap-south-1`).
2. Put `SUPABASE_DB_URL` in `.env`, then `python -m scripts.apply_migrations --check` (read-only) and
   `python -m scripts.apply_migrations` (applies 001–005, tracked in `schema_migrations`; refuses to run on a database
   that has tables it didn't create). Then `python -m scripts.rls_check` runs a rolled-back live cross-tenant test.
3. Authentication → Providers → Email enabled; set Site URL to `APP_BASE_URL`; configure SMTP for reset emails.
4. Fill `.env`: `SUPABASE_URL`, `SUPABASE_ANON_KEY` (Publishable key), `SUPABASE_SERVICE_ROLE_KEY` (Secret key — keep
   private, server-side only), `SUPABASE_DB_URL` (session pooler URI), `DATA_BACKEND=supabase`. Both the legacy
   (`anon`/`service_role`) and the newer (`sb_publishable_…`/`sb_secret_…`) API key formats work.
5. Start the app; the first visit asks you to create the Super Admin (that's you — the one who approves CA firms).
6. Backups: enable Supabase daily backups / PITR; storage objects are retained (no delete policy).

> **Verified live** on a real Supabase project (ap-south-1), end to end, with every row cleaned up afterwards:
> - `scripts/apply_migrations.py` — 001–005 applied; 45 tables, every one RLS-enabled; the 004 grants fix (see below).
> - `scripts/rls_check.py` — **16/16**: firm↔firm, client↔client, unassigned staff, Super Admin blocked from tenant data,
>   cross-firm insert/update blocked, audit log append-only, locked-period and unbalanced-voucher triggers.
> - `scripts/supabase_e2e.py` — **21/21**: CA firm self-signup (serial number + secret code + first password) → stays
>   `pending` and its code is rejected until the Super Admin approves it → Super Admin is notified in-app → sign-in through
>   real Supabase Auth → first-login password change (old password stops working) → client self-signup with the firm's
>   code → upload to private Supabase Storage → download after authorization → OCR/extraction → approval → balanced
>   voucher → firm B denied the client, the document and the voucher, including a raw SQL query blocked by Postgres RLS.
>
> One real bug was found and fixed this way: a freshly created Supabase project with "auto-grant API access" off left
> every table with zero privileges for the `authenticated` role, so RLS was never even reached (everyone blocked, not
> just other tenants) — fixed by `004_grants.sql`.

## 6. OCR and AI configuration
| Capability | Without configuration | With configuration |
|---|---|---|
| Digital PDFs, CSV/XLSX | Fully supported (PyMuPDF / pandas) | — |
| Scanned PDFs & photos | Routed to **Needs Review** with an explicit message; values entered manually from the original | Install Tesseract (`TESSERACT_CMD`) **or** set `ANTHROPIC_API_KEY` (Claude reads PDFs/images directly) |
| Field extraction | Local rule-based parser with per-field confidence | Claude (`ANTHROPIC_MODEL`, default `claude-opus-5-5`) with structured JSON output and per-field confidence; falls back to rules on any error (logged) |
| Assistant | Keyword intent matching | Claude maps the question to an intent; numbers always come from Python |

Tesseract on Windows: install from the UB Mannheim build, then set `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`.
The Claude adapter enables the server-side refusal fallback (`fallbacks: "default"`) — drop it in `ai_service.py` if you prefer a hard failure.

## 7. Feature notes and important qualifications
* **Accounting**: Decimal arithmetic throughout; vouchers are created as drafts; unbalanced vouchers cannot be saved or approved;
  uncertain classifications (pending ITC, defaulted expense head, RCM, missing GSTIN, total mismatch) are flagged and need explicit
  acknowledgement by a user with `approve_vouchers`. Accountants prepare; they cannot approve or finalize by default.
* **ITC is never assumed.** New purchases start as `pending`; pending ITC is excluded from GSTR-3B until decided. Blocked (17(5)) credit is shown
  in 4(A) and reversed in 4(B)(1); ineligible (16(4)/POS) in 4(D)(2) — per `gst_rules.py` version `2025.1`. B2CL threshold is versioned
  (₹1,00,000 from 1 Aug 2024).
* **GST filing**: the app **prepares** GSTR-1 (JSON in the GSTN offline-tool layout + Excel) and GSTR-3B tables. It never files.
  "Filed" status can only be recorded by a user entering the ARN from the portal. **Verify the JSON against the current GSTN schema before upload.**
* **Balance Sheet** is labelled *PROVISIONAL / INCOMPLETE* unless opening balances tally, closing stock is entered, depreciation is posted,
  no drafts or suspense balances remain and months are finalized. Even then it is "prepared from records (unaudited)".
* **Tally**: two files — ledger masters (`All Masters`) and vouchers (`Vouchers`) using Tally's sign convention, REMOTEID per voucher,
  bill allocations for party ledgers. Import instructions are on the Tally page. Not tested against a live TallyPrime instance — validate on a test company first.
* **Bank matching**: only exact, unambiguous full-amount matches (score ≥ 85) are auto-matched; others are suggestions. Bank vouchers are drafts;
  unidentified amounts go to Suspense and are flagged.
* **Finalization** saves a snapshot (vouchers, entries, trial balance) with SHA-256 hash; locked months reject voucher/document/opening-balance
  changes; reopening needs `reopen_period` and a written reason (audited).

## 8. Deployment
* **Single server / VM**: `streamlit run app.py --server.port 8501 --server.headless true` behind Nginx/Caddy with HTTPS;
  set `APP_BASE_URL` to the public URL. Use `DATA_BACKEND=supabase` for multi-user production (SQLite is for development/single-node use).
* **Docker** (example): `FROM python:3.12-slim`, `apt-get install tesseract-ocr`, `pip install -r requirements.txt`, `CMD streamlit run app.py --server.address 0.0.0.0`.
* **Streamlit Community Cloud** is not recommended for client financial data (shared infrastructure, secrets management limits).
* Keep `.streamlit/config.toml` `showErrorDetails = false` in production; errors are logged to `system_logs` (Super Admin → System Logs).

## 9. Test results (local backend)
`python -m pytest -q` → **116 passed** (≈2 min). Coverage:
* Authentication: super admin / firm / staff / client login, wrong password, lockout, generic errors, password policy (any
  characters, 6+, no spaces), reset token single-use, invitations, pending/suspended firms.
* Self-signup: CA firm signup generates a unique serial number + secret client code + system password; stays `pending`
  and is notified to the Super Admin until approved; a pending firm's code is rejected for client signup; client signup
  validates PAN, Aadhaar (Verhoeff checksum, masked storage), GSTIN-vs-PAN, mobile; wrong-portal login is refused; firm
  code can be regenerated without breaking already-linked clients; registrations/approval can be switched off by the
  Super Admin.
* Multi-tenant: firm A ↔ firm B, client A ↔ client B, unassigned staff, read-only staff, permission overrides, cross-tenant storage downloads,
  foreign ledgers in vouchers, assistant tenancy, super admin cannot read tenant books, audit entries.
* Documents: file validation (type, empty, disguised), digital PDF extraction, sales/purchase direction from GSTIN, multi-invoice PDF split,
  scanned PDF without OCR → review, image + scanned PDF with OCR engine (stubbed), duplicate file, duplicate invoice, missing fields,
  low-confidence values not guessed, AI failure fallback, inter-state tax mismatch, versioned corrections, approval → voucher, submission, clarifications,
  register import.
* Accounting: purchase/sales/credit note/RCM/expense entries, ineligible ITC capitalised, balance validation, unbalanced approval blocked, duplicate
  vouchers, numbering, review acknowledgement & role, ledger mapping, period lock/reopen, TB/P&L figures, Balance Sheet tally with opening balances & stock.
* Bank: CSV with preamble, classification, exact/partial/unmatched/suspense, manual match, over-allocation blocked, vouchers, BRS (tallied and with
  reconciling items), duplicates, continuity warnings, PDF statement parsing, statement document flow.
* GST: GSTIN checksum, Rule 46 invoice numbers, tax checks, GSTR-1 categorisation (B2B/B2CL/B2CS/CDNR/EXP/NIL/HSN) + JSON + Excel, GSTR-3B tables and
  ITC exceptions, Rule 88A set-off, GSTR-2B statuses (matched, amount/GSTIN/period mismatch, missing either side), filing never claimed.
* Tally: XML structure, Tally sign convention, balance, XML escaping, masters, re-export prevention, unbalanced blocked, permission.
* UI: every page renders without exceptions for Firm Admin, Accountant, Client and Super Admin (Streamlit AppTest), and a foreign firm cannot render another firm's client.

## 10. Known limitations
* Tesseract OCR and Claude extraction are implemented but not exercised against live services here (no OCR binary /
  API key available in this environment). The Supabase backend itself **has** been exercised live — see §5.
* The local rule-based parser handles clearly labelled invoices; complex table layouts, handwriting and photos need Claude or Tesseract plus review.
  Line-item extraction is heuristic.
* GSTR-3B tables 3.1.1 (e-commerce), 4(A)(1)/(2) imports and 4(A)(4) ISD are not derived from documents; enter manually. Composition/UIN
  breakdowns in 3.2 are not tracked. Interest/late fee (5.1) are user inputs.
* GSTR-1 JSON follows the offline-tool layout as understood; validate against the current schema before upload. No GSP/e-invoice/IRN integration.
* No inventory/stock-item accounting (closing stock is entered as a value); fixed-asset register and depreciation schedules are manual journals.
* Billing records subscriptions but does not collect payments. Email uses SMTP if configured, otherwise `data/outbox/`.
* Document processing runs synchronously in the request; very large batches would benefit from a background worker (the `processing_jobs`
  table is ready for it).
* SQLite backend is intended for development / single-node use.
