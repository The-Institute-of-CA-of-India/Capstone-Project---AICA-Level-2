# CashSense - AI bank and treasury agent (SAMPLE data)

**Start here:** `docs/CashSense_Explainer.html` (or `docs/CashSense_Explainer.pdf`) - how the whole app works,
how data comes in and how every output is produced, on one page.
**To run it on your computer (reviewers):** follow `docs/Reviewer_Guide.md` - install Python, double-click
`Setup_For_Reviewers.cmd` once, then `Start_CashSense.cmd`. No accounts or keys needed; n8n, Telegram and Gemini
are optional extras.
**To use it day to day:** `docs/User_Guide.md` (desktop, uploading statements, mobile) - written in plain language.
**The data:** `database_snapshot/CashSense_Database_Snapshot.xlsx` is a read-only copy of every table in the live
database (also as CSV in `data.zip > data/db_snapshot`). No database password is shared - none is needed to review
the data, and the app also runs on a local database file without one. Refresh with `python scripts\export_snapshot.py`.

CashSense reads a company's bank statements, categorises every line with AI, reconciles the bank
with the books, flags risky payments, forecasts cash for 13 weeks and answers treasury questions
by voice, with a human approving every action that changes data.

Built for the ICAI AICA Level 2 capstone. All data is fictitious and marked SAMPLE.

## Status

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundation: sample company, masters, books, bank statements, database + ERP adapters, tests | Approved (+ holidays, EEFC, GST on charges) |
| 2 | Statement reading (CSV / PDF / photo) and AI Categoriser agent | Approved |
| 3 | Reconciler agent, Telegram approvals via n8n, Risk Sentinel, offline browser checks | Approved |
| 4 | 13-week Forecaster, mobile dashboard, voice Q&A agent, Power BI export | Approved |
| 5 | Apps Script briefing + schedulers, Supabase, phone tunnel, Claude plugin + MCP, ICAI upload, master prompt | Approved - live |

## Quick start (Phase 1)

```powershell
cd cashsense
python -m cashsense.cli phase1
python -m unittest discover -s tests -t . -v
```

`phase1` generates the sample data into `data/phase1/`, loads it into a local SQLite database
(`cashsense.db`) and builds `data/phase1/Phase1_Review_SAMPLE.xlsx` for review in Excel.

## Phase 2

```powershell
python -m cashsense.cli gemini-check     # after pasting GEMINI_API_KEY into .env
python -m cashsense.cli phase2           # render, read, import March 2026, categorise, measure
```

`phase2` renders statements as a bank CSV, digital PDFs and phone photos (`data/phase2/statements/`),
reads them back, imports March 2026, categorises all March lines and writes
`data/phase2/Phase2_Review_SAMPLE.xlsx`. Without a Gemini key, photos are skipped and the categoriser
runs on rules only.

## Phase 3

```powershell
python -m cashsense.cli phase3                                     # measure: reconcile, risks, approvals
powershell -ExecutionPolicy Bypass -File scripts\start_cashsense.ps1  # local API for n8n (127.0.0.1:8765)
powershell -ExecutionPolicy Bypass -File scripts\start_n8n.ps1        # n8n at http://localhost:5678
python scripts\setup_n8n.py                                        # one-time: import credential + workflows
```

Then activate the three CashSense workflows in n8n. Approvals arrive in Telegram; tap Approve / Reject.

## Phase 4

```powershell
python -m cashsense.cli phase4      # forecast, Gemini commentary, assistant question bank, Power BI export, workbook
```

Dashboard: start the API (`scripts\start_cashsense.ps1`), open http://127.0.0.1:8765/dashboard and sign in with
`DASHBOARD_PASSWORD` from `.env`. In Telegram, type a question or send a voice note. Power BI: `docs/PowerBI_Guide.md`.

## Phase 5

```powershell
python -m cashsense.cli migrate-to-supabase   # after running cashsense\db\supabase_setup.sql in Supabase
python -m cashsense.cli briefing --ping        # check the Apps Script web app (APPS_SCRIPT_URL, APPS_SCRIPT_SECRET)
python scripts\start_tunnel.py                 # temporary phone link to the dashboard, sent to Telegram
python scripts\build_plugin.py                 # Claude plugin: /plugin marketplace add <cashsense>/plugin
python scripts\build_upload.py                 # ICAI upload folder with secret scan
```

Docs: `docs/Video_Script.md`, `docs/Submission_Checklist.md`, `docs/Master_Prompt.md`, `docs/PowerBI_Guide.md`.

## Layout

```
cashsense/
  config.py          settings from .env (database, ERP, as-of date)
  money.py           integer-paise money helpers, Indian number format
  categories.py      the 19 bank-line categories
  datagen/           phase1.py data generator (seed 2026); phase2.py CSV / PDF / photo renderer
  db/                schema.sql, SQLite + Supabase adapters, loader
  erp/               ERP adapter interface, mock ERP, Dynamics 365 placeholder
  ai/gemini.py       Gemini free-tier REST client (JSON schema, model fallback, time limits)
  ingest/            CSV, PDF and photo readers; Python checks; importer
  agents/            categoriser (AI + checks) and rules cross-check
  evaluation.py      scoring against the answer keys
  review/            Excel review workbooks
skills/              statement-reader and bank-categoriser instructions (also used by the plugin)
data/phase1/         generated test data (answer_key/ is never loaded by the app)
tests/               acceptance tests per phase
docs/BUILD_LOG.md    decisions, results and prompts per phase
```

## Safety rules

- Only fictitious SAMPLE data; fictitious IFSC codes start with `ZZ`.
- No secrets in the repository; keys go in `.env` (see `.env.example`).
- The answer key is used only by tests, never by the agents.
