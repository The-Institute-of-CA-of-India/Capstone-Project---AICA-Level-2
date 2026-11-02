# AppealIQ — User Acceptance Test Checklist

## Real-order trial (private, on this computer only)

Purpose: check AppealIQ on real orders from the practice before relying on it, **without any client data leaving this computer or entering the repository**.

### Before you start

- [ ] Engine set to **Standard** or **Local AI** for every trial matter. Do not use Cloud AI with real client orders unless the engagement terms permit it.
- [ ] The sidebar badge reads **"Offline · Data stays on this computer"**.
- [ ] Real orders are stored only in `data/` (git-ignored). Run `git status` before any commit: nothing under `data/`, no PDFs, DOCX or XLSX outside `docs/sample_outputs/` may appear.
- [ ] Use trial matter IDs that do not identify the client: `UAT-01`, `UAT-02`, … Put "Trial" in the Client field, not the client's name.
- [ ] Keep a blank copy of the problem log below in a separate file **outside** the repository (e.g. `Documents\AppealIQ_UAT_log.xlsx`).

### Orders to try (aim for 8–10)

| # | Order type | Why |
|---|---|---|
| 1–3 | CIT(A) / NFAC orders u/s 250 (one with the AO order uploaded) | Core flow, issue trail |
| 4 | JCIT(A) order, ideally ex parte | Ex parte ground, restoration prayer |
| 5 | Revision order u/s 263 | Objection-style titles, rule 0 |
| 6 | CIT(E) rejection / cancellation u/s 12AB or 80G(5) | Rule 0, natural-justice check |
| 7 | Final order u/s 143(3) r.w.s. 144C(13) | DRP route, every addition treated as dismissed |
| 8 | A scanned order (no text layer) | OCR quality and speed |
| 9 | A long order (40+ pages) | Speed, para numbering across pages |

### What to check on each screen

**Step 1 — Upload & Details**
- [ ] Process stays disabled until matter ID, client, order and date of service are filled; the reason is shown.
- [ ] A wrong file (Word document, password-protected PDF) gives a plain-English message with what to do.

**Step 2 — Processing**
- [ ] Every stage shows a status and a duration; nothing freezes. Note the total time and the page count.
- [ ] Warnings (OCR used, low confidence, duplicate upload) are understandable.

**Step 3 — Review** (compare with the order itself, page by page)
- [ ] *Summary strip*: order type, AY, authority, DIN and service date match the order; due date and days left are right.
- [ ] *Order Details*: every value matches the order; the `[p/¶]` reference points to the right page and para; "Not found" only where the order really does not state the value.
- [ ] *Limitation*: Form 36 due date = two months from the end of the month of service (s. 253(3)); fee per s. 253(6); cross-objection date only when the Revenue's appeal is received.
- [ ] *Issue Trail*: every ground / issue is listed once; titles are fair; sections right; AO amount, relief and sustained amounts right; outcome right; Refs point to the right paras; nothing missing compared with the order (also check the "not found in the appellate order" notice).
- [ ] *Issue panels*: the verbatim extracts really are in the order at the stated page and para; nothing invented.
- [ ] *Tax Effect*: rate preset sensible for the assessee; s. 115BBE applied only to ss. 68–69D; Revenue appeal likelihood (CIT(A) orders only) and the circular citation are right.
- [ ] *Decision Matrix*: each recommendation matches what you would advise; note every override you make and why (in general terms).
- [ ] *Grounds & Paper Book*: grounds concise, legal grounds first, amounts and sections exact; paper book index complete for the issues.
- [ ] *Verification Log*: every unverified item is genuinely not in the order (or is an OCR error).
- [ ] Generate one AI note (Local AI): it is shaded and labelled, cites no case law, names no wrong section, and the page stays on the same tab and issue.

**Step 4 — Approve & Download**
- [ ] Approval needs the reviewer name and the checkbox; outputs unlock only then.
- [ ] Each output card shows the document type, format and size; every Download works.

### What to check in each output

- [ ] **Report (DOCX / PDF)**: cover, executive summary, dates and fee, issue trail, issue-wise analysis with references, tax effect, consequential matters, decision matrix, action plan, grounds, paper book index, verification log, annexure, disclaimer; header/footer and page numbers; landscape tables readable.
- [ ] **Draft grounds**: numbered, "DRAFT — for professional review" header, craves-leave ground last.
- [ ] **Paper book index**: blanks for bench and ITA No.; certification line.
- [ ] **Issue register (XLSX)**: six sheets, Indian number format, filters and colour coding work.
- [ ] **Case Register / Home**: the trial matter appears with the right due date and RAG; status update and Excel export work.

### How to record a problem — without copying client data

Record each problem as one row in your private log (outside the repository):

| Field | What to write | Example |
|---|---|---|
| Ref | UAT-matter + number | UAT-03-2 |
| Order type / pages / text or scan | Generic description | CIT(A) u/s 250, 14 pages, text |
| Screen / output | Where you saw it | Issue Trail, I2 |
| What AppealIQ showed | Describe the **kind** of value, not the value | "Sustained amount shown as relief" |
| What the order says | Location and kind only | "p.9 ¶6.3 restricts the addition to a lower amount" |
| Severity | High (wrong date, amount, outcome or forum) / Medium (missing or wrong reference, wrong title) / Low (wording, layout) | High |
| Pattern hint | The **generic wording** that confused it, paraphrased | "'is sustained to the extent of' phrasing" |

Never write in the log, an issue, a commit message or a chat: the assessee's name, PAN, DIN, address, appeal number, exact amounts, or verbatim sentences from the order. Do not attach screenshots or the casefile JSON. If an example is needed to fix a pattern, re-type it as a **synthetic** sentence with fictitious names and round amounts, and add it to `scripts/make_samples.py` so it becomes a test.

### After the trial

- [ ] Delete the trial matters: remove `data/matters/UAT-*`, `data/uploads/UAT-*` and `data/outputs/UAT-*`, and set their register status to Closed (or delete `data/appealiq.db` if it holds only trial data).
- [ ] Summarise the log as counts per screen and severity, plus the generic pattern hints — this summary (no client data) is what goes into the next phase's prompt.
