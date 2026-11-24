# CashSense build log

## Project decisions (agreed 22-Nov-2026)

| Topic | Decision |
|---|---|
| Purpose | ICAI AICA Level 2 capstone; must not overlap the earlier "Pocket CA" presentation project |
| Domain | Bank, cash and treasury (not compliance, notices or GST bills) |
| AI engine | Google Gemini free tier only (no local model) |
| Database | Local SQLite first behind an adapter; switch to Supabase free tier in Phase 5 |
| Front end | Telegram bot (uploads, approvals, alerts via n8n) + mobile web dashboard |
| Sample business | Fictitious auto-component manufacturer in Pune with 3 bank accounts, FY 2025-26 |
| Cost | Free tiers only |
| Process | 5 phases; each phase has its own test data file and waits for approval |

## Phase 1 - foundation and data (no AI)

### Built
- Deterministic generator (`cashsense/datagen/phase1.py`, seed 2026) for **Sample Precision Components Pvt Ltd (SAMPLE)**:
  - 3 bank accounts: CA01 current (Rs 45 lakh opening), CC01 cash credit (Rs 2 crore limit, 10.5%), CL01 collections with a Rs 1 crore FD.
  - 17 vendors (5 MSME raw-material suppliers), 14 customers (2 exporters paying in USD), 9 statutory / payroll / utility payees.
  - A year of activity: customer receipts, supplier payments (NEFT / RTGS / cheques), salary and Diwali bonus, TDS, GST, PF, ESI, advance tax, rent, term-loan EMI, power, capex advance, FD interest net of TDS, bank charges.
  - Daily treasury simulation: CC funds the current account when it falls below Rs 10 lakh, Friday sweeps move surplus and collections to CC, CC interest is computed on daily drawn balances.
  - Open receivables, open payables and Apr-Jun 2026 commitments (salary, statutory, insurance, Rs 60 lakh capex, FD maturity) for the forecast phase.
- Seeded March 2026 differences and risk items, written to an answer key that the app never loads.
- Database schema (SQLite / PostgreSQL), SQLite adapter, Supabase REST adapter (untested until Phase 5), audit log.
- ERP adapter interface + mock ERP; Dynamics 365 placeholder.
- Excel review workbook with live check formulas.
- 14 automated tests.

### Test data file
`data/phase1/` - `Phase1_Review_SAMPLE.xlsx` (review), statements per account per month, `book_entries.csv`,
masters, open items, commitments, and `answer_key/` (`recon_items_2026-03-31.json`, `risk_flags.json`, `matches.csv`).

| Item | Count |
|---|---|
| Bank statement lines | 897 (36 monthly statements) |
| Book entries | 893 |
| Counterparties | 40 |
| Open receivables / payables | 34 / 33 |
| Commitments Apr-Jun 2026 | 29 |

### Seeded items (answer key)
| Account | Item |
|---|---|
| CA01 | 3 cheques issued 27-30 Mar not presented; amount keyed wrongly (books 1,85,400 vs bank 1,84,500); duplicate debit 3,48,720; March charges not booked |
| CC01 | March CC interest not booked |
| CL01 | Cheque deposited 31 Mar credited in April; unidentified receipt 2,36,000; customer cheque 4,12,300 returned; March FD interest and two charges not booked |
| Risk only | Vendor paid to a changed bank account; Rs 5 lakh Sunday IMPS to an unknown payee; split payments under the Rs 5 lakh approval limit; 2 MSME bills overdue beyond 45 days (sec 43B(h)) |

### Results (22-Nov-2026)
- 14/14 tests pass: running balances, month continuity, limits, BRS closes for all accounts, seeded counts, one-to-one matches, masters, SAMPLE marking, determinism, SQLite load, mock ERP balances, SQL-injection guard.
- Excel recalculation: BRS status "Agreed" for CA01, CC01 and CL01; 36/36 statement checks = 0; 0 continuity breaks; 0 formula errors.
- Book balances at 31-Mar-2026: CA01 Rs 46,88,844.00; CC01 -Rs 1,57,83,217.77 (drawn); CL01 Rs 66,90,925.09.

### Prompt log
1. Build CashSense in 5 phases with a test data file per phase, approval between phases, questions for clarification, and a master prompt at the end.
2. Choices: Gemini only; local first, Supabase later; Telegram + mobile web; manufacturer with 3 bank accounts.

### Approval and enhancements (approved with Phase 1)
- Phase 1 approved. Gemini key to be provided during Phase 2. Statement formats OK. Category list OK. Markdown documentation is enough.
- All three suggested enhancements approved and built into the Phase 1 data:
  - **Bank-holiday calendar**: Sundays, 2nd/4th Saturdays and an illustrative Maharashtra holiday list (`bank_holidays.csv`). Cheque clearing, statutory and payroll debits fall only on working days; NEFT/RTGS transfers run 24x7.
  - **EEFC account (EF01, USD)**: export receipts are credited in USD; about 80% is converted to INR each month around the 26th at the bank's buying rate. Books carry the USD amount and the INR value. March has an unbooked USD 15 inward-remittance charge.
  - **GST on bank charges**: every charge has a separate 18% GST line on the statement and is booked to "Input GST on bank charges (ITC)"; the workbook has a monthly ITC sheet.
- Re-test after enhancements: 966 bank lines, 958 book entries, 4 accounts; 17/17 tests; Excel: 4/4 BRS "Agreed", GST 18% every month, 0 errors.

## Phase 2 - statement reading and Categoriser agent

### Built
- **Test data** (`cashsense/datagen/phase2.py`): the Phase 1 statements for October 2025 and March 2026 rendered as
  a Sample Bank of India CSV export (CA01), Sample Heritage Bank digital PDFs (CC01), Sample Kaveri Bank USD PDFs (EF01)
  and phone photos of a printed Sample Kaveri Bank statement (CL01: tilt, shadow, noise, SAMPLE watermark, 2 pages).
  Answer key: exact expected lines per file and the true category / counterparty of all 966 lines.
- **Readers**: CSV (finds the header by keywords, handles metadata rows), digital PDF (pdfplumber tables, Dr/Cr balances),
  photo (Gemini vision with the `statement-reader` skill and a JSON schema).
- **Python checks after every reading**: running balance on every line, closing balance, dates inside the period and in
  order, continuity with last month's closing, currency, account number. For photos only, a single misread value is
  repaired when the printed balances on both sides prove it (side swap, balance digit, amount digit); every repair is
  recorded. Anything else sends the statement to review.
- **Importer**: matches the account by number, refuses duplicates unless replace is asked for, stores status and issues,
  marks lines of unverified statements, writes the audit log.
- **Gemini client**: REST, JSON-schema output, auto-selects free flash models (lite first for text, full first for images),
  per-try time limit and overall budget, falls through busy models, never logs the key.
- **Categoriser agent** (`bank-categoriser` skill): Gemini categorises lines in batches of 40 with counterparty,
  confidence and reason; a rule-based categoriser runs alongside. Python checks: allowed category, money direction,
  party exists in master, confidence >= 0.7, AI vs rules agreement, unidentified lines, vendor bank details vs master.
  Returned cheques are linked to the customer through the original deposit. If Gemini is unavailable, rules are used.
- `cli phase2`, `cli import`, `cli categorise`, `cli gemini-check`; review workbook `data/phase2/Phase2_Review_SAMPLE.xlsx`.

### Results (22-Nov-2026, with Gemini free tier)
| Check | Result |
|---|---|
| CSV statements (CA01 Oct, Mar) | verified, 39/39 and 46/46 lines exact |
| PDF statements (CC01, EF01 Oct, Mar) | verified, 12/12, 13/13, 5/5, 7/7 lines exact |
| Photo statements (CL01 Oct, Mar - 2 pages each), Gemini 3.6 Flash | verified, 27/27 and 33/33 lines exact, no repairs needed |
| AI categories, March 2026 (99 lines), Gemini 3.5 Flash-Lite | 99/99 correct, counterparties 99/99 |
| Rules categories, full year (966 lines) | 966/966, counterparties 966/966 |
| Review queue | 3 lines: unidentified receipt, vendor paid to changed bank account, Sunday IMPS to unknown payee |
| Tests | 30/30 pass, including the live Gemini photo test |

### Issues found and fixed during the Gemini run
1. **HTTPS blocked by antivirus inspection**: Avast Web/Mail Shield re-signs HTTPS with its own root, which Windows
   trusts but Python did not. Fixed with `truststore` (Python uses the Windows certificate store). Certificate
   verification stays on; no antivirus or security setting was changed.
2. **Photo page overflow (test-data bug)**: the last row of the October photo ran off the paper, so Gemini read half a
   description (balances still agreed, so the checks could not catch it). Pages now break by printed height.
3. **Skill wording**: the first AI run scored 97/99 - both misses were already sent to review by the Python checks
   (AI vs rules disagreement). The categoriser skill now states that a credit from a party not in the customer master
   is `unidentified`, and a payment to a payee not in the vendor master is `supplier_payment` with no party. The
   statement-reader skill now says to join descriptions that wrap onto a second line.
4. The Phase 2 manifest no longer fingerprints run results (only statements and answer key).

### Telegram set-up (start of Phase 3 preparation)
- WhatsApp Cloud API was considered (free test number, official API) but Telegram kept: no Meta app, no public webhook
  needed on a laptop, no 24-hour messaging window. Messaging sits behind an adapter so WhatsApp can be added later.
- Bot **@cashsense_rn_bot** created with BotFather; token in `.env` (never logged - client errors omit the URL).
  `cli telegram-check [--wait N]` verifies the token, captures the chat ID from the user's first message, saves it to
  `.env` as `TELEGRAM_CHAT_ID` and sends a test message. Test message received.
- Lesson: the first token belonged to a different bot (@Cashsence_rn_bot) than the one messaged; `telegram-check`
  shows the bot username so the mismatch is visible.
- 5 offline Telegram tests (buttons, chat discovery, token never in errors, .env update).

## Phase 3 - Reconciler, approvals, Risk Sentinel, browser agent, n8n

### Decisions (22-Nov-2026)
- Phase 2 approved. n8n Community Edition runs locally (`npm install -g n8n`, v2.48.7). Approval rules as proposed:
  exact matches auto-accepted and logged; entries, fuzzy matches and every risk flag need the CA's Telegram tap;
  nothing is posted without approval. Browser agent: Playwright driving the Microsoft Edge already on Windows.

### Built
- **Reconciler agent** (`agents/reconciler.py`): matches by cheque number + amount, then amount + date window (+ party),
  unique closest date only; incremental (matches are stored as links, a re-run only looks at open items); fuzzy
  proposals (same party, close date, small difference or transposed digits); classifies leftovers (charges, GST,
  interest, cheque returns, unidentified, duplicates, timing items); BRS per account with a Python template entry for
  each difference.
- **Risk Sentinel** (`agents/risk.py`): vendor paid to changed bank details, payments to unknown payees (worse on a
  bank holiday), split payments just under the Rs 5 lakh approval limit, duplicates within 7 days, unidentified
  receipts, returned cheques, MSME bills beyond 45 days (sec 43B(h)). A re-scan keeps the CA's earlier decisions.
- **Offline browser agent** (`agents/browser_verify.py`): Playwright + headless Edge operates local IFSC-lookup and
  account-verification pages (type, click, read, screenshot as evidence). Verifies every vendor master account and
  every changed account; the full account number and who added the beneficiary come from the bank-portal
  beneficiary export.
- **Gemini explainer** (`agents/explainer.py`, skill `treasury-explainer`): one call explains every reconciliation item
  and risk, proposes ledgers and writes the Telegram commentary. Guard-rails: only known IDs, length limits, the Python
  template entry is what gets posted (AI ledger disagreements are shown), AI may raise but never lower a risk severity,
  facts vs suspicions wording.
- **Approval service** (`approvals.py`): proposals grouped (charges + GST per account and date), idempotent, posting
  creates bank-ledger rows `JV/25-26/<approval id>` and links them to the bank lines; fuzzy approval links the pair and
  posts the correction; risk approval = Reviewed / Escalate; every decision audited; decisions are final.
- **Telegram** (`notify.py`): approval cards with buttons, daily summary, /status /risks /pending /help, statement
  uploads (document or photo album) -> read, verify, import, categorise, reconcile. Only the CA's chat is obeyed.
- **Local API** (`api.py`, FastAPI on 127.0.0.1:8765, header key `X-CashSense-Key` generated into `.env`):
  /api/telegram/poll, /api/run/daily, /api/notify/escalation, /api/import-file (data/inbox only), /api/approvals,
  /api/risks, /api/health.
- **n8n workflows** (`n8n/*.json`, imported by `scripts/setup_n8n.py`; the API key is held in n8n's encrypted
  credential store, not in the workflow files):
  1. Telegram inbox - every 10 s -> /api/telegram/poll -> IF anything decided/imported -> log.
  2. Daily treasury run - 08:00 IST (+ manual "Run now") -> /api/run/daily -> IF high risks -> URGENT alert, else all clear.
  3. Statement drop folder - Local File Trigger on data/inbox/drop -> /api/import-file.
- Review workbook `data/phase3/Phase3_Review_SAMPLE.xlsx`: BRS with formulas, matching rules, items with Gemini
  explanations, approvals, risk register, browser verifications, accuracy.

### Results (fresh run, Gemini free tier)
| Measure | Result |
|---|---|
| Automatic matches | 953 made, 953 correct, 0 true matches missed (the one fuzzy pair is proposed for approval) |
| Reconciliation items vs answer key | 17/17 identical; all 4 BRS "Agreed" |
| Risk flags | 8/8 expected found, 0 false positives; 2 high |
| Browser verifications | 21 accounts; only mismatch: payment account registered to DEEPAK TRADING COMPANY (beneficiary added 27-Feb-2026 by ops.user2) |
| Approvals | 18 proposed (9 entries, 1 fuzzy match, 8 risks); approving all leaves only the 4 timing items |
| Gemini explanations | 0 ledger disagreements with the Python templates |
| Tests | Phase 3: 13 tests pass (incl. browser agent); full suite below |

### Issues found and fixed
1. **AI label variation reached the controls.** Different free Gemini models labelled two unknown-party lines
   differently from the rules (credit from "M S Raj Traders" as customer receipt; Sunday IMPS as unidentified). The
   categoriser already sent both to review, but the Reconciler and Risk Sentinel used the AI label, so one run found
   7/8 risks. Fix: on disagreement the deterministic rule category is stored (the AI view is kept in the reason and the
   line goes to review); the AI overrides only when the rule is unsure and the AI is >= 0.9 confident; a customer /
   supplier category needs a counterparty from the master; the Risk Sentinel also treats unidentified outflows as
   payments. Two regression tests added.
2. Over-assertive wording ("fraudulent account"): skill now requires facts vs "suspected/possible".
3. n8n readiness check: n8n listens on 127.0.0.1 only; "localhost" may resolve to IPv6.
4. Free-tier limits: live tests hit "all models busy" after many calls in a short time. The client falls through
   models; heavy use can exhaust the free quota for a while. The live test now reports "skipped" (not failed) when
   Gemini is unavailable; every agent falls back to rules / rule wording in that case.
5. **Photo reference misread by a fallback model.** With the newer models busy, Gemini 3.5 Flash-Lite once copied two
   digits of a UTR twice (balances were right, so the balance checks could not catch it); an immediate re-read was
   exact. Fix: **consensus reading** - every photo statement is read twice independently; if the readings differ
   anywhere, a third read decides by majority per line; no majority -> the line is marked for human review.
   Regression test added. Full suite: 49 tests, 48 pass, 1 skipped while the free quota resets.
6. **Same slip in two readings.** A later live run had two lite-model readings agree on the same reference digit
   slip. Fix: a **bank statement profile** (`ingest/profiles.py`) - Sample Kaveri Bank references are one letter +
   14 digits; a wrong length triggers a third read, the consensus prefers readings with a valid reference, and a
   reference that is still malformed is flagged for review. Same-length digit swaps cannot be detected; this does not
   affect any control, because matching uses amount, date, party and cheque numbers, and a broken cheque link would
   surface in the BRS as an unexplained item.
   **Stated guarantee for photo statements:** dates, amounts and balances exact (proved by the balance checks);
   descriptions best-effort (>= 95% exact), malformed references flagged. The live test now checks exactly this.
   Full suite: 50 tests pass (including the live Gemini photo test).

### Live demo (22-Nov-2026, evening)
- n8n 2.x calls activation "publish": the three workflows were published with `n8n publish:workflow`
  (`scripts/setup_n8n.py` now imports idempotently - same-name workflows are overwritten - and publishes).
- n8n 2.x disables the Local File Trigger node by default for security; it was NOT re-enabled. The drop-folder
  workflow now polls `/api/inbox/scan` every 30 s; processed files move to `drop/processed`, failures to `drop/failed`.
- `n8n execute` of "Daily treasury run" (Run now): success in 46 s - reconcile 4 accounts (all agreed), risk scan with
  21 browser verifications, Gemini commentary, 18 approval cards + summary + URGENT alert (2 high risks) on Telegram.
- The CA tapped on the phone; n8n's 10-second inbox workflow processed every tap:
  AP0003 bank charges + GST **approved** -> `JV/25-26/AP0003` posted (Bank Charges 1,500.00; Input GST (ITC) 270.00);
  AP0009 FD interest and AP0010 EEFC charge **rejected** (nothing posted); AP0017 MSME risk **escalated**;
  AP0018 MSME risk **reviewed**. All decisions audited as `telegram:Ramnath`.
- One of 71 polls hit "Cannot reach Telegram (ConnectionError)" while fetching updates (nothing lost - the next poll
  picked the taps up). Hardened: a failed fetch returns a clean "will retry" response; the Telegram position is saved
  after every update; a failed chat reply after a decision is logged without undoing or repeating the decision;
  commands are audited. Regression test added.

## Phase 4 - Forecaster, voice and chat assistant, mobile dashboard, Power BI

### Decisions (22-Nov-2026)
- Phase 3 approved (answers to the Phase 4 questions taken as approval). Scenarios as proposed + 85% CC alert.
- Power BI Desktop was not installed: installed with the CA's permission (`winget install Microsoft.PowerBI`,
  v2.159.1231.0). Voice: both Telegram voice notes and a dashboard microphone.

### Built
- **Forecaster** (`agents/forecaster.py`): 13 weeks from 1-Apr-2026. Known flows (uncleared cheques, open receivables -
  overdue ones spread over weeks 1-4 - open payables with overdue MSME bills paid at once, commitments) + run-rate
  (same month last year per party, on credit terms) + CC interest; pooled funding (cash above Rs 15 lakh swept to CC).
  Scenarios: base, customers 15 days late, largest customer pays nothing, CNC capex in week 1. Alert above 85%.
- **Forecast commentary** (skill `treasury-forecaster`): Gemini headline, per-scenario comments and actions; Python
  extracts every amount in the text (Rs / lakh / crore) and lists any that is not in the facts (1% tolerance).
- **Assistant agent** (`agents/assistant.py`, skill `cashsense-assistant`): Gemini **function calling** over 8
  READ-ONLY tools (cash position, forecast, reconciliation, risks, pending approvals, receivables, payables,
  commitments); the model chosen for the first step is pinned for the conversation (thought signatures); every amount
  in the answer is checked against the tool results; it cannot approve or change anything.
- **Voice** (`voice.py`): Telegram voice note -> Gemini transcription -> assistant -> Gemini TTS
  (gemini-3.8-flash-lite-tts) -> OGG/Opus via ffmpeg (imageio-ffmpeg) -> Telegram voice reply; offline fallback:
  Windows System.Speech. Any typed text in Telegram is also answered by the assistant.
- **Mobile dashboard** (`/dashboard`, `web/dashboard.html`): password sign-in (generated into `.env`), signed
  HttpOnly session cookie (12 h), lock-out after 10 wrong passwords in 10 minutes, audit of sign-ins. KPI cards, 13-week
  CC-utilisation chart with 85% / 100% lines for all scenarios, weekly table, Gemini commentary, BRS status, risk
  flags, Ask box with microphone (browser speech recognition, en-IN) and spoken answers (browser voice or Gemini voice).
  Read-only: approvals stay in Telegram. Light / dark themes, phone layout.
- **Power BI** (`powerbi.py`, `docs/PowerBI_Guide.md`): star schema CSVs (dims: account, party, date; facts: bank
  lines, forecast weeks, forecast flows, reconciliation items, risks) + `measures.dax` + a 15-minute build guide.
  A .pbix cannot be generated reliably from code (binary model), so the report is built in Power BI Desktop by hand.
- `cli phase4`, review workbook `data/phase4/Phase4_Review_SAMPLE.xlsx` (scenario summary, weekly sheets with a live
  roll-forward check, flows, commentary, assistant Q&A, Power BI export).

### Test data (data/phase4/answer_key)
- `expected_forecast_known_flows.json`: known flows per week for base / late_15 / capex_forward, computed
  independently from the Phase 1 files with the stated rules; opening CC position; MSME > 45 days total.
- `assistant_questions.json`: 7 questions with expected facts (including a refusal to approve).

### Results
| Measure | Result |
|---|---|
| Known flows vs independent key | 39/39 scenario-weeks identical |
| Base case | peak CC use 60% (week 10), no 85% alert |
| Customers 15 days late | peak 109% (Rs 2,17,24,044.06) in week 10; 85% alert first in week 2 |
| Largest customer pays nothing | peak 88% in week 10; alert in week 10 |
| CNC capex in week 1 | peak 60% in week 1, no alert |
| Gemini commentary | generated; 0 unverified amounts |
| Assistant question bank (live Gemini) | 7/7 (over two runs - the free tier throttled mid-run) |
| Voice | Gemini TTS -> OGG 4.8 s; Gemini transcription of that audio word-perfect; Windows fallback OK |
| Dashboard | signed in at phone size; assistant answered "week 10, 88%" from the forecast tool |
| Tests | 65 pass (including live assistant and live photo tests) |

### Issues found and fixed
1. Overdue receivables all landed in week 1 (unrealistic): now spread over weeks 1-4, oldest first.
2. Assistant summed two amounts itself ("about Rs 10.41 lakh") -> flagged by the amount check; the payables tool now
   returns the sec 43B(h) total so the AI can quote it.
3. Assistant missed the FD maturity and the CNC balance: it did not know CashSense's "today" (as-of date now sent with
   every question) and the payables tool cut its list at 25 bills (now all bills, with notes).
4. Commentary named the largest payer as an "overdue" customer: the facts now include the largest overdue
   receivables separately.
5. Dashboard header unreadable in dark mode; "open risks" ignored escalated flags - both fixed.
6. winget needed `--source winget` for Power BI; free Gemini quota throttles bursts (handled by fallbacks/skips).

## Phase 5 - go live

### Decisions (22-Nov-2026)
- Phase 4 approved. Phone access by Cloudflare quick tunnel (free, temporary link; `cloudflared` installed with winget).
  Switch to Supabase now. Briefing emailed to the Google account running the Apps Script. Licence for the ICAI copy:
  all rights reserved (evaluation only).

### Built
- **Supabase adapter hardened**: new `sb_secret_` keys in the apikey header only (legacy JWTs also as Bearer),
  limit/offset paging, 20-second read cache cleared on every write, clear error messages without the key;
  `db/supabase_setup.sql` = schema + Row Level Security on all 17 tables with no policies (the public key reads
  nothing); `cli migrate-to-supabase` copies every table (parents first), verifies row counts, switches `.env`.
- **Google Apps Script** (`apps_script/Code.gs`, `appsscript.json`): web app `doPost` checks the shared secret, logs to
  the Sheet "CashSense Briefings", emails an HTML briefing to the account running it; `setup()` installs triggers -
  eveningReminder 18:00 (approvals / high risks waiting), staleCheck 10:00 (no briefing for 26 h), weeklyDigest
  Monday 09:00. CashSense side: `briefing.py` (payload: cash, CC use, BRS, risks, approvals, scenarios, Gemini
  headline/actions), sent after every daily run when `APPS_SCRIPT_URL` is set; `cli briefing [--ping|--secret]`.
- **Phone access**: `scripts/start_tunnel.py` starts a Cloudflare quick tunnel to the API and sends the dashboard link
  to Telegram; the dashboard still needs its password, every API route its key.
- **Claude plugin** (`plugin/`): local marketplace `cashsense-local`, plugin `cashsense` with 6 skills (copied from the
  single source by `scripts/build_plugin.py`, incl. new `cashsense-operator`), 4 commands (cash-position,
  treasury-briefing, risk-review, forecast) and an MCP server (`mcp/cashsense_mcp.py`, JSON-RPC 2.0 over stdio, stdlib
  only, 9 read-only tools incl. `ask`) calling new key-protected API routes `/api/tool/{name}` and `/api/ask`.
- **ICAI upload** (`scripts/build_upload.py`): copies code, skills, plugin, workflows, Apps Script, tests, docs,
  LICENSE; packs sample data as data.zip; scans every file for the real `.env` values and key patterns and stops if
  any is found. Result: 102 files, 2.8 MB, scan clean.
- Docs: `Video_Script.md` (10-minute Zoom script with face, backup plan), `Submission_Checklist.md` (fork + PR, video
  link sharing, Google Form), `Master_Prompt.md`, `PowerBI_Guide.md`.

### Results so far
- MCP server tested live against the API: initialize, 9 tools, cash_position (63%), forecast late_15 (109%, week 2),
  unknown method -32601.
- Phase 5 tests: 9/9 (Supabase adapter offline, RLS SQL, database copy, briefing, Apps Script code, MCP protocol,
  plugin integrity, tool API, upload secret scan).
### Go-live results (23-Nov-2026)
| Check | Result |
|---|---|
| Supabase migration | all 17 tables copied and row counts verified (966 bank lines, 967 book entries, 18 approvals with decisions, 137 audit entries); `.env` switched to Supabase |
| API on Supabase | cash position 63% (5 s), forecast late_15 109% / week 2 (3.8 s), 13 approved decisions read back |
| Apps Script | ping accepted the shared secret; briefing for 31-Mar-2026 received (email + Sheet row) |
| Phone tunnel | public https link sent to Telegram; over the tunnel: health OK, API without key 401, dashboard without sign-in -> /login |
| Tests | 74 tests: OK, 1 skipped in the full run (a live Gemini test - free tier busy) |

### Issues found and fixed
- The Supabase "Connect" panel gives the REST URL (`.../rest/v1/`); the adapter now accepts both forms.
- After the overnight restart the API and n8n were not running; restarted with the start scripts (the video
  checklist starts them first).

### Prompt log (Phase 5)
10. "Approve, start Phase 5"; choices: Cloudflare tunnel, Supabase now, email to the script's account, all rights
    reserved.
11. "Where is project URL?" (Supabase) - Connect button or Data API page; "both done" - go-live checks above.
12. "Email arrived, approve" - briefing email confirmed by the CA; **Phase 5 approved - project complete (23-Nov-2026)**.
13. "The voice says numbers in millions instead of lakhs and crores" - fixed: before speaking, every rupee amount is
    turned into Indian words (Rs 1,26,32,553.34 -> "1 crore 26 lakh 32 thousand 553 rupees"; paise rounded;
    "Rs 10.41 lakh" -> "10.41 lakh rupees"; bare Indian-grouped numbers too; USD left as is). Same logic in Python
    (Telegram voice replies, Gemini TTS and the Windows fallback) and JavaScript (dashboard browser voice); both give
    identical text on the test cases. Live check: Gemini TTS audio transcribed verbatim as "one crore twenty six lakh
    thirty two thousand five hundred fifty three rupees ... two crore rupees" - no "million".
14. "Take me through entire app..." then "Do so and save in the folder for icai review" - one-page explainer
    `docs/CashSense_Explainer.html` (self-contained, works offline, light/dark, phone layout with a swipeable diagram)
    and `docs/CashSense_Explainer.pdf` (A4, 7 pages, exported with headless Edge by `scripts/export_explainer.py`);
    linked as "Start here" in the README; included in the ICAI upload.
15. "continue" (24-Nov-2026) - services restarted after the laptop session ended. n8n came back with its 3 workflows
    unpublished (0 calls to CashSense); re-published with `setup_n8n.py`, after which n8n polled Telegram and the drop
    folder with no errors. Fix: `start_n8n.ps1` now runs `setup_n8n.py --publish-only` before every start. Tunnel
    restarted and the new dashboard link sent to Telegram.
16. "Guide me to launch this app on desktop, upload the data and similarly on mobile step by step in a layman's
    terms" - added `Start_CashSense.cmd` (one double-click starts the app, n8n and the phone link, then opens the
    dashboard) and `docs/User_Guide.md` (plain-language: start, sign in, upload by drop folder or Telegram, run the
    daily check, use Telegram / dashboard / email on the phone, troubleshooting). Tested: launcher started all three
    services and n8n called CashSense; a sample PDF dropped in `data/inbox/drop` was imported, verified,
    categorised and reconciled in under a minute; dropping it again was refused as a duplicate (moved to `failed`).
17. "The database password should be shared with ICAI in the folder" - advised against it: the upload goes to ICAI's
    GitHub (possibly public; history keeps it), the password gives full read/write/delete control, the secret scan
    would block it, and reviewers do not need it. The CA chose a **database snapshot** instead:
    `scripts/export_snapshot.py` exports every table of the live database to
    `database_snapshot/CashSense_Database_Snapshot.xlsx` (README sheet + one sheet per table, readable amount columns
    next to paise/cents) and to CSV in `data/db_snapshot` (inside data.zip). 17 tables; row counts verified against
    Supabase (966 bank lines, 967 book entries, 18 approval decisions, 8 risk flags, 156 audit entries).
    The secret scan then **stopped the build**: the CA's Telegram chat ID had been written to the audit log when
    /status, /risks and /pending were used. Fixes: the snapshot replaces every private .env value with [redacted];
    the audit log no longer stores chat IDs ("ca_chat" / "unknown_chat"); the scan now also looks inside
    .xlsx/.docx/.pptx files (it could not see into the compressed Excel file before - regression test added).
    Rebuilt: 113 files, scan clean.
18. "What is this error" (n8n not recognised when the CA started it) - the window had an out-of-date copy of the
    Windows PATH (opened by a program that started before the npm folder was added), so neither `n8n` nor `node`
    was visible; it worked in testing only because the test inherited a fresh PATH. Fix: `start_n8n.ps1` and
    `setup_n8n.py` now reload the saved Machine + User PATH and add the npm global folder and the Node.js install
    folder (from the registry) before looking for n8n. Tested from a window whose PATH had neither: n8n started,
    the workflows were active, and a file dropped in `data/inbox/drop` was picked up in 27 s.
19. "Still an error" ("n8n was not found") - real root cause: the Claude desktop app is a packaged Windows app, and
    Windows gives packaged apps (and every process they start, sandboxed or not) a private copy of AppData. Both
    `npm install -g n8n` runs made from the app went into that private copy, so n8n existed for the app but not for
    the CA's own windows; the earlier "fixed" test had also run inside the app's view. Confirmed by checking from
    Explorer (the CA's real view): n8n missing; n8n's data in `~/.n8n`, the Python packages, cloudflared and Power BI
    present. Fix: n8n installed with `npm.cmd install -g n8n --prefix "...\n8n-runtime"` on D: (D: is not
    virtualised), and `start_n8n.ps1` / `setup_n8n.py` look there first. Verified from Explorer: `Start_CashSense.cmd`
    started the app, n8n and the phone link in 39 s, and n8n picked up a file from the drop folder in 33 s.
    Lessons: test "as the user" by launching through Explorer, not from the app's shell; use `npm.cmd` (Windows
    blocks the `npm.ps1` script by default) - likely why the CA's own install attempt failed.
20. "For ICAI do they need to download npm separately as it returns the same error if I run .cmd from icai folder" -
    yes: Node.js and n8n are separate programs that cannot go into a GitHub upload. A fresh copy also had no
    unpacked data, no `.env`, no database and an incomplete `requirements.txt`. Fixes: complete `requirements.txt`;
    `cli reviewer-setup` (unpacks data.zip, creates `.env` from `.env.example`, builds a local SQLite database, rule
    categorisation, daily run without AI, generates the dashboard password locally); `Setup_For_Reviewers.cmd`
    (checks Python, installs packages, runs the setup); `Start_CashSense.cmd` stops with a message if setup was not
    run, skips n8n and the phone link politely when they are not installed, and honours `CASHSENSE_PORT`;
    `docs/Reviewer_Guide.md` (what to install, steps, what works without keys, optional AI / Telegram / n8n).
    Tested on a fresh copy of the upload, launched from Explorer on port 8766: setup gave all 4 accounts "agreed",
    17 reconciliation items and 8 risk flags (2 high) - same as the answer key - with no keys; launcher skipped n8n,
    started the app and the tunnel; wrong password 401, right password signed in, dashboard data with 4 accounts, 4
    scenarios and 8 risks. 74 tests OK.

### Prompt log (Phase 4)
9. "1) ok 2) needs to be installed 3) c"; Power BI install approved.

### Prompt log (Phase 3)
5. "Can you use whatsapp instead of telegram?" - compared; then "How to proceed with telegram bot token?" - Telegram kept.
6. "token added", "Start sent", "done start", "I have changed the bot token" - bot connected (@cashsense_rn_bot).
7. Phase 2 approved; n8n local; proposed approval rules; Playwright.
8. "Owner account created", "Done tapping" - live n8n + Telegram demo above.

### Prompt log (Phase 2)
3. "1) I will get it in Phase 2 2) Ok 3) All good 4) Md good enough. All suggested enhancements good."
4. "Key added" - Gemini run, fixes above.
