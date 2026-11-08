# BG Tracker: Bank Guarantee Tracking & Reminder Dashboard

An AI-training (Level 2) project for Chartered Accountants and finance teams in India. It tracks Bank Guarantees (BGs) through their full lifecycle and drafts the reminder emails that should go to the client, the beneficiary and the bank, so no expiry is missed and no margin or FDR stays blocked after a contract ends.

> **Demo only.** All companies, banks' contacts and emails in this repository are fictional (`example.com`). Emails are **simulated**, not sent. Do not load real client data into this version.

## The problem

In most CA and finance offices, BGs are tracked in Excel and memory. Two things go wrong:

1. **A BG lapses before renewal**, putting a contract at risk.
2. **A BG is never released after the contract ends.** The beneficiary keeps the original, the bank keeps the margin or FDR under lien, and commission keeps accruing.

The second one is easy to miss because nothing "expires". A BG usually carries a **claim period** after its validity date, and the bank cannot treat it as discharged until the original is returned or a written release is given.

## What the tool does

- **Dashboard:** total exposure, margin and FDR blocked, BGs expiring in 30 days, overdue releases, commission due in 15 days, charts by bank, status, type and a 12-month expiry timeline, plus a 90-day expiry heat strip.
- **BG Register:** search, filter and sort, CSV export, Add/Edit forms with validation, and a detail drawer with lifecycle timeline, amendment history, linked reminders and audit entries. One-click actions: record extension, mark original returned, request release, mark discharged.
- **Reminders approval queue:** a "Run daily check" button applies the rules below, creates draft emails (no duplicates), and a human edits, approves or dismisses each one.
- **Audit log:** every action is recorded.

### Reminder rules

| Trigger | Sent to | Purpose |
|---|---|---|
| 60 / 30 / 15 / 7 days before expiry | Internal team and client | Decide: renew, extend or let lapse |
| Expiry date | Client | Confirm whether the BG was extended |
| After expiry, original not returned | Beneficiary | Request return of the original or a release letter |
| Release letter received | Bank | Request cancellation, release of margin/FDR lien, closure confirmation |
| Claim expiry within 15 days, original not returned | Internal team | Escalate |

A reminder of the same type to the same recipient for a BG is created only once.

## Tech stack

- Built with **Lovable** (React + TypeScript, TanStack Router, Tailwind CSS, shadcn/ui, Recharts)
- **Supabase** (PostgreSQL) for data, with a `reset_demo_data()` SQL function that seeds fictional data using dates relative to today
- **Vitest** unit tests for the reminder rules and the form validation rules

## Data model

`bank_guarantees`, `bg_amendments` (extension history), `reminders`, `audit_log`. See the migration in the repository for columns.

## Demo data

27 fictional BGs across 8 banks and 6 fictional clients, covering: expiring in 7 / 30 / 60 / 90 days, expired but inside the claim period, one past its claim period, extended with amendment history, invoked, release requested and discharged. Use **Settings → Reset demo data** to reload it with fresh dates.

## Running it

1. Export or sync the project to GitHub from Lovable, then clone it.
2. Install dependencies and start the dev server (check `package.json` for the exact scripts).
3. Connect your own Supabase project, apply the migration, and set the Supabase URL and anon key in your environment.
4. Open the app. It seeds itself on first load if the table is empty.

## Limitations and disclaimer

- **No login, and open access policies.** The database policies are intentionally permissive for the demo. Before any real use you must add authentication and per-firm row-level security.
- **Emails are simulated.** "Approve & send" only marks a reminder as sent and writes to the audit log.
- **Not legal or banking advice.** Drafted emails and claim-period logic are templates. A qualified professional must review every communication and confirm the terms in the actual BG and contract.
- Reminder generation currently runs when you click the button, not on a schedule.

## Roadmap

- Run the daily check on a schedule (for example with n8n) and send approved emails through Gmail or a transactional email service
- Upload a scanned BG or amendment letter and extract the number, amount and dates with an LLM, for a human to verify
- Contingent-liability view for financial statement disclosure, and commission accrual tracking
- Login, roles and multi-client separation

## Screenshots

Add screenshots of the Dashboard, BG Register drawer and Reminders queue here.
