# CashSense - master prompt

Use this single prompt in Claude Code (desktop app, Code tab) in an empty folder to rebuild the whole CashSense
project. It combines every instruction, decision and lesson from the five phases.

# Role and working rules

You are building "CashSense", my individual capstone for the ICAI AI for CA Level 2 course. I am a Chartered
Accountant. Build it in 5 phases. For each phase create the test data file (with an answer key the app never
loads), build, test against the answer key, update `docs/BUILD_LOG.md`, demonstrate, ask me questions, suggest
enhancements and wait for my approval. Never implement an enhancement I have not approved. Use AI (Google Gemini)
as much as possible, but put Python checks after every AI step. Spend no money: free tiers only. Use only
fictitious SAMPLE data, clearly marked. Never type my passwords or API keys and never print them - tell me where to
paste them (`.env`). Do not change antivirus, firewall or security settings and do not bypass security blocks
(on this laptop Avast scans HTTPS: use the `truststore` package and Node's system CA option, keep verification on).
Ask before downloads or installs. It must not overlap my earlier "Pocket CA" project (compliance calendar, notices,
GST bills, Excel books): CashSense is about banks, cash and treasury.

# What CashSense is

An AI bank and treasury agent for an Indian business: reads bank statements (CSV, digital PDF, phone photos),
categorises every line, reconciles bank with books, flags fraud and control risks (with an offline browser agent
verifying beneficiary accounts), forecasts cash for 13 weeks with scenarios, answers questions by text and voice,
and sends approvals to the CA on Telegram - nothing is posted without the CA's tap.

# Technology (all free)

Python 3 + FastAPI (API on 127.0.0.1:8765, key header `X-CashSense-Key`); database behind an adapter - SQLite
first, then Supabase (Postgres via REST, secret key server-side, Row Level Security on every table with no
policies); Google Gemini free tier over REST with JSON schemas, function calling, vision, audio and TTS, trying free
flash models in turn (lite first for text, full first for images, per-try time limit and overall budget, model
pinned within a tool conversation); Telegram bot (BotFather; capture the chat ID from the CA's first message; only
that chat is obeyed); n8n Community Edition run locally (`npm install -g n8n`; n8n 2.x "publishes" workflows; its
Local File Trigger is disabled by default - do not re-enable it); Playwright driving the Microsoft Edge already on
Windows; ffmpeg from the imageio-ffmpeg wheel; Google Apps Script; Cloudflare quick tunnel for a temporary phone
link; Power BI Desktop (free) via a CSV star schema; Claude plugin with skills, commands and a stdlib MCP server.
India time (UTC+5:30); demo "today" = 31-Mar-2026 (`CASHSENSE_AS_OF`).

# Phase 1 - foundation and data (no AI)

- Deterministic generator (seed 2026): "Sample Precision Components Pvt Ltd (SAMPLE)", auto-components, Pune,
  FY 2025-26. Accounts: CA01 current (Rs 45 lakh opening, keep >= 10 lakh), CC01 cash credit (Rs 2 crore limit,
  10.5% on daily drawn balance), CL01 collections with a Rs 1 crore FD (7.1%, quarterly interest net of 10% TDS),
  EF01 EEFC in USD (export receipts credited in USD, ~80% converted to INR around the 26th at the bank's buying rate).
  Fictitious IFSC codes start with ZZ. 17 vendors (5 MSME), 14 customers (2 exporters), statutory / payroll /
  utility payees.
- A year of activity: receipts, NEFT/RTGS/cheque payments, salary + Diwali bonus, TDS (7th), PF/ESI (15th), GST
  (20th), advance tax (Jun/Sep/Dec/Mar), rent and EMI (5th), power, capex advance, bank charges with a separate 18%
  GST line, FD interest. Daily treasury simulation: CC funds CA01 below Rs 10 lakh, Friday sweeps to CC.
  Bank-holiday calendar: Sundays, 2nd/4th Saturdays, illustrative Maharashtra holidays; cheque clearing and
  statutory/payroll debits only on working days; NEFT/RTGS 24x7.
- Seed March 2026: 3 cheques not presented, a deposit credited in April, a book amount keyed wrongly
  (1,85,400 vs 1,84,500), a duplicate debit, an unidentified receipt, a returned cheque + charges, unbooked March
  charges/GST/CC interest/FD interest/USD remittance charge; risks: vendor paid to changed bank details (beneficiary
  added 27-Feb by "ops.user2", account held by DEEPAK TRADING COMPANY), Rs 5 lakh Sunday IMPS to an unknown payee,
  split payments just under the Rs 5 lakh approval limit, 2 MSME bills beyond 45 days (sec 43B(h)).
- Open AR/AP and Apr-Jun 2026 commitments (salary, statutory, insurance, Rs 60 lakh CNC capex on 15 May, FD maturity
  30 June). Schema, SQLite + Supabase adapters, audit log, ERP adapter (mock; Dynamics 365 placeholder), Excel review
  workbook with live check formulas (BRS "Agreed" for all accounts, GST 18%, continuity), tests.

# Phase 2 - statement reading and Categoriser agent

- Render Oct-2025 and Mar-2026 statements as: a bank CSV export (CA01), digital PDFs (CC01, EF01 in USD) and phone
  photos (CL01: tilt, shadow, noise, SAMPLE watermark; pages break by printed height). Answer key: exact lines.
- Readers: CSV (header found by keywords), PDF (pdfplumber tables, Dr/Cr balances), photos (Gemini vision with the
  `statement-reader` skill). Photo statements are read twice; if readings differ a third read decides by majority;
  a bank profile checks reference format (Sample Kaveri Bank: letter + 14 digits). Python checks: running balance on
  every line, closing balance, dates in period and in order, continuity with last month, currency, account number;
  for photos only, a single value is repaired when balances on both sides prove it. Guarantee: dates, amounts and
  balances exact; descriptions best-effort (>= 95%).
- Categoriser (`bank-categoriser` skill): 19 categories; Gemini returns category, counterparty, confidence, reason in
  batches of 40; a rule-based categoriser runs alongside; on disagreement the rule category is stored and the line
  goes to review (AI overrides only when the rule is unsure and the AI >= 0.9); a customer/supplier category needs a
  counterparty from the master; returned cheques are linked to the customer through the original deposit.

# Phase 3 - Reconciler, approvals, Risk Sentinel, browser agent, n8n

- Reconciler: cheque number + amount, then amount + date window (+ party), unique closest date; incremental links;
  fuzzy proposals (same party, close date, small difference or transposed digits); leftovers classified; BRS per
  account; Python template entry for each difference.
- Risk Sentinel: changed vendor bank details, unknown payees (worse on bank holidays), split payments, duplicates,
  unidentified receipts, returned cheques, MSME > 45 days; unidentified outflows also count as payments (controls must
  not depend on AI labels); re-scans keep the CA's decisions.
- Offline browser agent: local IFSC-lookup and beneficiary-verification pages; Playwright + Edge types, clicks, reads
  and saves a screenshot; full account numbers come from the bank-portal beneficiary export.
- Gemini explainer (`treasury-explainer` skill): explanations, proposed ledgers (template wins; disagreements shown),
  may raise never lower severity, facts vs "suspected".
- Approvals: exact matches auto-accepted and logged; entries (charges + GST grouped), fuzzy matches and every risk need
  the CA's Telegram tap (Approve / Reject, Reviewed / Escalate); idempotent; postings `JV/25-26/<approval>`; audited.
- Telegram: cards with buttons, daily summary, /status /risks /pending /help, statement uploads; network blips must not
  lose or repeat a decision (offset saved per update).
- n8n workflows (API key in n8n's encrypted credential store): Telegram inbox every 10 s; daily run 08:00 IST with IF
  high risks -> urgent alert; drop-folder scan every 30 s via the API.

# Phase 4 - Forecaster, assistant, voice, dashboard, Power BI

- 13-week forecast: known flows (uncleared cheques; receivables on due date, overdue spread over weeks 1-4; payables
  on due date, overdue MSME at once; commitments) + same-month-last-year run rate per party + CC interest; pooled
  funding above Rs 15 lakh; scenarios base / customers 15 days late / largest customer pays nothing / capex in week 1;
  alert above 85%. Answer key computed independently for known flows.
- Gemini commentary (`treasury-forecaster` skill) with a check that rejects any amount not in the facts.
- Assistant (`cashsense-assistant` skill): Gemini function calling over 8 read-only tools; as-of date sent with each
  question; amounts in answers checked; cannot approve. Question bank of 7 with expected facts.
- Voice: Telegram voice note -> Gemini transcription -> assistant -> Gemini TTS -> OGG/Opus voice reply (Windows
  offline voice as fallback); typed questions answered too. Before anything is spoken, convert every rupee amount
  to Indian words (Rs 1,26,32,553.34 -> "1 crore 26 lakh 32 thousand 553 rupees", paise rounded; "Rs 10.41 lakh" ->
  "10.41 lakh rupees") - the same logic in Python and in the dashboard's JavaScript - so the voice never says
  "million"; verify by transcribing the generated audio with numbers in words. Dashboard: password sign-in (generated), signed session
  cookie, lock-out after 10 failures, KPI cards, scenario chart with 85%/100% lines, commentary, BRS, risks, Ask box
  with microphone and spoken answers; read-only. Power BI: star schema CSVs + DAX measures + build guide.

# Phase 5 - go live

- Supabase: run `db/supabase_setup.sql` (schema + RLS), paste URL and secret key into `.env` (accept the URL with or
  without `/rest/v1/` - the Connect panel shows the REST form), `cli migrate-to-supabase` copies and verifies every
  table and switches `.env`.
- n8n start script re-publishes the CashSense workflows before every start (they can come back unpublished after an
  abrupt shutdown); start order for a demo: API, then n8n, then the tunnel. One-click `Start_CashSense.cmd` starts all
  three and opens the dashboard.
- Install n8n into a folder on D: (`npm.cmd install -g n8n --prefix "<project>\..\n8n-runtime"`), not the default
  AppData location: installs made from the Claude desktop app land in its private (virtualised) AppData and are
  invisible to the user's own windows. Start scripts reload the saved PATH and look in n8n-runtime first. Always
  verify "as the user" by launching through Explorer.
- Google Apps Script (`apps_script/Code.gs`): web app receives the daily briefing (shared secret), logs to a Sheet,
  emails the account running it; triggers: 18:00 reminder, 10:00 stale-run alert, Monday digest.
- Cloudflare quick tunnel (`scripts/start_tunnel.py`) sends a temporary dashboard link to Telegram.
- Claude plugin `cashsense` (local marketplace): 6 skills, commands cash-position / treasury-briefing / risk-review /
  forecast, MCP server on JSON-RPC 2.0 over stdio (stdlib) calling the API read-only.
- `scripts/build_upload.py`: upload folder with LICENSE (all rights reserved, evaluation only), data.zip, secret scan.
  Video script, submission checklist, this master prompt, final build log.
- Make the upload runnable by a reviewer with only Python: complete `requirements.txt`; `Setup_For_Reviewers.cmd`
  runs `cli reviewer-setup` (unpack data.zip, `.env` from `.env.example`, local SQLite database, rules-only daily
  run, dashboard password generated on their computer - never shipped); `Start_CashSense.cmd` refuses to start
  before setup, skips n8n and the tunnel with a polite note when not installed, honours `CASHSENSE_PORT`;
  `docs/Reviewer_Guide.md` lists what to install and what is optional. Test on a fresh copy of the upload launched
  from Explorer.
- One-page explainer for the ICAI reviewers: `docs/CashSense_Explainer.html` (self-contained, offline, light/dark,
  phone layout with a swipeable flow diagram: inputs -> read/verify/store -> three agents -> Gemini explains, Python
  guards, CA approves -> outputs; sections on data input, processing, controls, outputs, a day with CashSense, course
  topics, where things live) and a PDF copy exported with headless Edge; linked as "Start here" in the README.

# Acceptance checks
- All automated tests pass (70+); Excel review workbooks recalculate with zero errors and "Agreed" BRS.
- Readers and categoriser match the Phase 2 answer key; reconciliation items and risk flags match the Phase 3 key
  (8/8, no false positives); known forecast flows match the Phase 4 key; assistant passes the question bank.
- Live: n8n daily run sends the summary and approval cards; taps post / reject / escalate and are audited; voice note
  answered in voice with amounts in crore and lakh; dashboard opens on the phone via the tunnel; briefing email
  arrives; Claude plugin answers; the explainer renders correctly on desktop, phone and in dark mode.
