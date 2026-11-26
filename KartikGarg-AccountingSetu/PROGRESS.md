# Development progress log

## Status: all 10 phases implemented and now verified LIVE on Supabase — 116 local tests + 16 RLS checks + 21 e2e checks passing (2026-11-25)

| Phase | Status | Notes |
|---|---|---|
| 1 Foundation | ✅ | Config, 45-table schema, RLS + storage + grants policies, dual DB backend, auth, tenancy, role navigation |
| 2 Firm & client mgmt | ✅ | Self-signup for both CA firms and clients (serial number + secret client code + first password); every new firm is `pending` until the Super Admin approves it (notified in-app); client signup validates PAN/Aadhaar/GSTIN and needs the firm's code; profile/logo/settings, staff + permission overrides, invitations, assignments, plan limits |
| 3 Document intelligence | ✅ | Validation, private storage, PDF text, OCR adapter, Claude adapter, rules parser, splitting, confidence, validation, review UI, versioned corrections |
| 4 Accounting engine | ✅ | CoA + mapping, invoice→voucher rules (sales/purchase/expense/notes/RCM/ITC), numbering, approval, manual journals, opening balances, closing stock |
| 5 Bank | ✅ | CSV/XLSX/PDF parsing, classification, auto + manual + multi-invoice matching, bank vouchers, BRS |
| 6 GST | ✅ | GSTR-1 (+JSON/Excel), GSTR-3B (Rule 88A), GSTR-2B import & reconciliation, ITC decisions, approval, ARN recording |
| 7 Tally | ✅ | Preview/validation, masters + vouchers XML, re-export tracking, import instructions |
| 8 Reports & AI | ✅ | TB, P&L, BS (provisional checks), registers, books, ledgers, debtors/creditors ageing, GST summary, voucher register, charts, comparisons, PDF/Excel, approve & share; assistant |
| 9 Finalization & audit | ✅ | Pre-checks, snapshot + hash, lock, reopen with reason, notifications, audit trail |
| 10 Testing & delivery | ✅ | 116 local tests + live Supabase verification (below); app launched and pages verified in browser; README/deployment docs |

## Live Supabase verification (project `accounting-setu`, ap-south-1) — 2026-11-25
- [x] Migrations 001–005 applied (schema, RLS, storage policies, API-role grants, firm codes). Refuses to run on a
  database with foreign tables.
- [x] `scripts/rls_check.py` — 16/16, rolled back.
- [x] `scripts/supabase_e2e.py` — 21/21: self-signup → pending → Super Admin notified → approved → Supabase Auth
  sign-in → first-login password change → client self-signup with firm code → Storage upload/download → OCR/extraction
  → approval → balanced voucher → firm B denied everywhere, including a raw-SQL RLS check. Cleans up everything it
  creates; confirmed 0 rows left in every table afterwards.
- [x] Bug found and fixed live: a fresh Supabase project with auto-API-grant off left `authenticated` with zero table
  privileges (RLS never reached) — fixed in `004_grants.sql`.
- Still unverified: Tesseract OCR and Claude extraction against real files/API (no binary/key available here); GSTR-1
  JSON against the current GSTN offline tool; Tally XML import on a real TallyPrime company.

## Pending / next steps
- [ ] Validate GSTR-1 JSON with the current GSTN offline tool; validate Tally XML import on a TallyPrime test company.
- [ ] Configure `ANTHROPIC_API_KEY` and/or Tesseract and evaluate extraction accuracy on real scanned invoices.
- [ ] Background worker for large document batches (processing_jobs table already present).
- [ ] Payment gateway for subscriptions; e-invoice/IRN and GSP integrations (only with authorised providers).
