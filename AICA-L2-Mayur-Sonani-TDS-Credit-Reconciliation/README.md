# TDS Credit Reconciliation Assistant

**AICA Level 2 – Capstone Project** · Submitted by **CA Mayur Sonani**

An offline, browser-based tool that reconciles a client's TDS credit across **Form 16A certificates, Form 26AS and the client's books**. It flags every mismatch and drafts follow-up emails to deductors, then tracks each one until it is resolved.

> **Design principle: rules calculate · AI reads & drafts · CA decides.**
> AI never computes an amount. Every figure comes from deterministic rules, and anything AI writes is checked against those figures before it is used.

---

## The problem: TDS credit on the customer's side

When customers pay a business, they deduct TDS and must deposit and report it against the business's PAN. The business (the deductee) gets credit only for what appears in its **Form 26AS**, and should hold a **Form 16A** for each customer and quarter. Any credit not corrected by the customer before the return is filed is lost.

Today a CA team types every Form 16A into Excel, matches books, 26AS and certificates line by line, and chases customers by email. The costly problems are the quiet ones:

| # | Customer-side problem | How the tool detects it | Who acts |
|---|---|---|---|
| 1 | Form 16A not received | 26AS shows credit, but there is no certificate for that TAN and quarter | Customer |
| 2 | Form 16A and 26AS don't match (return revised) | Certificate amount vs 26AS amount | Customer |
| 3 | TDS withheld from our payment but never deposited or reported | Invoice + GST − amount received vs 26AS | Customer |
| 4 | Reported short, or under another PAN | Books vs 26AS by deductor and quarter | Customer |
| 5 | Challan not matched (booking status U/P/O) | 26AS booking status is not "F" | Customer |
| 6 | Books at 10% (194J), customer reported 2% (194C) | Rate and section, books vs 26AS, plus amount withheld | Customer |
| 7 | Deducted at 20% (PAN treated as missing, s. 206AA) | Effective 26AS rate of 20% or more | Customer (cash flow) |
| 8 | TDS deducted on the amount including GST | 26AS base = taxable value + GST | Customer (cash flow) |
| 9 | Customer deducted 2% and reported 2%, but our books assumed 10% | Amount withheld = amount reported | Our books |
| 10 | Customer paid in full (no TDS), books still show TDS receivable | Amount withheld is nil | Our books |
| 11 | Quarter timing difference | Quarters differ, but the yearly total agrees | Our review |
| 12 | March invoice whose TDS may appear in next year's 26AS | Invoice month | Our review |
| 13 | Credit in 26AS but not in our books | 26AS entry with no matching invoice | Our review |

Using the **amount received**, the tool tells *who* is wrong. If the customer withheld 10% but reported 2%, the customer must revise its return. If it withheld only 2%, our books need correcting.

## The solution

One HTML file. Double-click it to open it in Chrome or Edge. **Nothing to install, and no data is uploaded.**

| Step | What happens | Done by |
|---|---|---|
| 1. Extract | Reads all Form 16A PDFs: certificate no., deductor, TAN, period, section, amount paid, TDS deposited | Rules (pdf.js) |
| 1a. Fix | Fills fields the rules couldn't read. A value is accepted **only if it appears word-for-word in the PDF** | AI (verified) |
| 2. Parse | Reads Form 26AS (TRACES text export or Excel) and the books / customer master (Excel) | Rules |
| 2a. Map | Suggests TANs for customer names in the books that don't match the master | AI suggests, CA accepts |
| 3. Reconcile | Compares Books, 26AS and Form 16A for each **deductor TAN and quarter**, and classifies 10 exception types | Rules |
| 4. Explain | Explains each exception in plain English: what it means, the likely cause, the next step | AI (labelled draft) |
| 5. Follow up | One email per deductor covering all open items: Form 16A requests, 26AS mismatch queries, wrong section, unmatched challans | Rules draft + AI polish |
| 5a. Guardrail | If an AI-polished email contains an amount that doesn't match the reconciliation, it is **rejected** and the rule-based draft is kept | Rules |
| 6. Send & track | Opens the email in Outlook/Gmail or downloads Outlook drafts (.eml), then tracks Not sent → Sent → Reminder due → Reply received → Resolved | CA |
| 6a. Inbox sync | Reads the mailbox for mails tagged `[Ref TDS/PAN/TAN/FY]`: sent mails mark the deductor **Sent** (repeat sends count as reminders), replies mark it **Reply received**, and an inbox activity table fills in | n8n workflow or Google Apps Script |
| 6b. Read replies | Summarises each reply, records what the deductor promised and by when, and suggests whether it is resolved | AI (CA accepts) |
| 6c. Attachments | A Form 16A attached to a reply is extracted, the reconciliation re-runs, and the deductor is **auto-resolved** if everything now matches | Rules |
| 7. Report | Excel workbook: Summary, Reconciliation, Follow-ups, Form 16A extract, 26AS detail, Books. Plus an AI review note for the partner | Rules + AI |

### Exception statuses in the tool

Form 16A pending · 16A ≠ 26AS · Withheld, not deposited · Not in 26AS · Short in 26AS · Booking status U/P/O · Rate differs · Section mismatch · Deducted at 20% (206AA) · TDS on amount incl. GST · Correct TDS in books · Timing difference · Check next FY 26AS · Not in books · Excess in 26AS · TAN not mapped (16 in all). Each one is marked either *customer action* (goes into the follow-up email) or *internal review*.

## AI used (course modules applied)

- **Offline LLMs – LM Studio / Ollama (Module 5):** the recommended setup. The model runs on the laptop, so client PANs and amounts never leave the machine.
- **Prompt engineering (Module 1):** structured JSON prompts with a system role, explicit "never invent amounts" instructions, and low temperature.
- **AI-enabled application development (Modules 6–7):** a single-file HTML application with an AI layer behind any OpenAI-compatible endpoint (LM Studio, Ollama, OpenAI, Gemini).
- **Data confidentiality and governance (Module 2):** PAN/TAN masking before any prompt; a visible privacy badge (local vs cloud); cloud AI needs explicit confirmation; API keys are kept in memory unless the user chooses "remember".
- **Human in the loop:** AI output is always labelled as a draft, the CA accepts or rejects mapping suggestions, and nothing is ever emailed automatically.

## Inbox sync: automatic reply tracking (n8n / Apps Script)

Every follow-up subject carries a reference tag, e.g. `[Ref TDS/AAQFS1234K/PNED40004D/2025-26]`. Replies keep the subject, so they can be matched to the deductor without guessing.

```
Tool ──GET ?key&pan&days──▶ n8n webhook / Apps Script ──▶ Gmail / Outlook search "Ref TDS/<PAN>"
  ◀── JSON: sent mails, replies (quoted history removed), PDF attachments ──┘
Tool: Sent / Reply received / Resolved · AI summary & promise · Form 16A from attachment → re-reconcile
```

Two interchangeable backends are in `inbox_sync/`:

- **`n8n_TDS_Inbox_Sync_workflow.json`** (Module 9, workflow automation). Supports Gmail and Outlook. Import it into n8n, set your own key in the Webhook's *Only run if* condition, connect Gmail and/or Outlook (enable the *Search Outlook* node), and activate it.
- **`Gmail_AppsScript_InboxSync.gs`** (Module 4, Google Apps Script). Free and Gmail only. Paste it into script.google.com, set `ACCESS_KEY`, and deploy as a web app (Execute as: Me, Access: Anyone).

In the tool, go to tab 4 → *Inbox sync settings*, paste the URL and key, and tick *Sync automatically after each reconciliation*. The sync service stores nothing; email content goes only to the tool on your computer.

## How to run

1. Download `TDS_Credit_Reconciliation_Assistant.html` and open it in Chrome or Edge. An internet connection is needed the first time to load three open-source libraries (pdf.js, SheetJS, JSZip). After that the browser caches them.
2. **Tab 1:** upload the files in `sample_data/`:
   - `Form16A_PDFs/*.pdf` (select all)
   - `Form26AS_AAQFS1234K_2025-26.txt`
   - `Books_and_Customers_FY2025-26.xlsx` (Books sheet: invoice, section, taxable amount, GST, amount received, TDS expected; Customers sheet: TAN, contact, email)
3. Click **Run reconciliation**, then look at tabs 2–4.
4. **AI (optional):** in tab 5, choose *LM Studio*, load a model (e.g. Qwen 2.5 7B Instruct), start the server with **CORS enabled**, and click *Test connection*. Then use the purple **AI** buttons.

The tool works fully without AI: the rules-only reconciliation and emails are complete. AI adds explanations, better wording, extraction fallback and name matching.

## Sample data (fictitious)

All names, PANs, TANs, email addresses and amounts are **made up**. The 15 sample customers cover every problem in the table above: 3 matched, plus one customer for each scenario (certificate pending, withheld but not deposited, 10% vs 2%, 206AA, GST base, our books wrong, timing, year-end, challan unmatched, not in books).

Expected result: books ₹3,29,000 · 26AS ₹2,77,200 · Form 16A ₹2,39,200 · **credit at risk ₹61,600** across 5 customers · 9 customer follow-ups · 2 items where our own books need correcting.

Measured on a laptop: 100 Form 16A PDFs read in about 12 seconds; the full sample reconciled with all emails drafted in under 2 seconds.

`generate_sample_data.py` rebuilds the sample data (needs `reportlab` and `openpyxl`).

## Files

```
TDS_Credit_Reconciliation_Assistant.html   the application (single file)
sample_data/                                fictitious Form 16A PDFs, 26AS text file, books workbook
generate_sample_data.py                     script that generates the sample data
inbox_sync/                                 n8n workflow (Gmail + Outlook) and Google Apps Script (Gmail) for reply tracking
docs/screenshots/                           screenshots of each step
docs/Capstone_Presentation.pdf              the presentation slides
docs/RECORDING_GUIDE.md                     how the capstone video was recorded, with timeline
```

## Limitations

- Extraction is tuned to the TRACES Form 16A layout. Check a few rows against the PDFs when using a new deductor's format.
- Matching is done by TAN and quarter. Books are assigned to a quarter by invoice date unless a Quarter column is given.
- The tool is a reconciliation aid, not tax advice. Final judgement rests with the CA.

*Built during the ICAI AICA Level 2 programme.*
