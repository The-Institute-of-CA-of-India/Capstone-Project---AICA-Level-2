# AppealIQ — Phase-wise Prompts for Claude Code

**How to use this file**

1. Create an empty folder (e.g. `D:\AppealIQ`). Copy `CLAUDE.md` to the root, and copy `docs/SPEC.md` and `docs/PROMPTS.md` into `docs\`.
2. Open the folder in Claude Code. Run `git init` first.
3. Paste **one phase prompt at a time**, in order. Do not paste the next phase until the current phase's acceptance checks pass.
4. At the end of each phase:
   - run the app or tests yourself;
   - review what was built;
   - commit (`git add . && git commit -m "<message Claude suggests>"`).
5. Keep the conversation focused. Start a **new Claude Code session for each phase** (CLAUDE.md carries the context). This keeps quality high.
6. Copy each prompt and a one-line outcome into `docs/PROMPT_LOG.md`. ICAI evaluators value this record of how AI was used to build the tool.

Text inside `<< >>` is for you to fill in before pasting.

---

## Phase 0 — Kick-off and plan (no code)

```
Read CLAUDE.md and docs/SPEC.md completely. Do not write any code yet.

Then:
1. Summarise the product in 10 bullet points to confirm your understanding.
2. List any ambiguities, contradictions or risks you see in SPEC.md, with your proposed resolution for each.
3. Produce a build plan matching the phases in docs/PROMPTS.md. For each phase, list the files to create, the key functions, and the tests.
4. List every legal value in SPEC.md that is marked verified: false, as a checklist for me.
Wait for my confirmation before starting Phase 1.
```

---

## Phase 1 — Scaffold, configuration, theme skeleton

```
Implement Phase 1 per CLAUDE.md §4 and SPEC.md §4, §10.1, §10.2, §12.4, §14.

Deliver:
- The folder structure in CLAUDE.md §4, with __init__.py files and module stubs that have docstrings.
- requirements.txt (runtime) and requirements-dev.txt (pytest, pytest-cov, reportlab, ruff), with versions pinned to current stable releases compatible with Python 3.12.
- .streamlit/config.toml: theme colours from SPEC §10.1, server.address=127.0.0.1, gatherUsageStats=false, headless=true.
- appealiq/config.py: load/save config/settings.yaml (firm name, reviewers, RAG thresholds, materiality, LM Studio URL/timeout/max_tokens, cloud model). Use pydantic settings models with defaults.
- appealiq/ui/theme.py: CSS injection implementing the design tokens, top bar, cards, KPI tiles, RAG badges, status chips, stepper component, and hiding the Streamlit chrome. Use the system font stack only; no external assets.
- app.py with sidebar navigation (Home, New Analysis, Case Register, Settings, Help & About) and placeholder pages that already use the theme components.
- Logging setup (rotating file in data/logs).
- setup.bat, run.bat, setup.sh, run.sh per SPEC §14.
- .gitignore (data/, .venv/, .env, __pycache__, models/*.joblib except a .gitkeep).
- tests/test_security.py: asserts that config.toml binds to 127.0.0.1 and that no source file contains http(s) URLs other than localhost/127.0.0.1 and api.anthropic.com.

Acceptance: `run.bat` opens a themed app with working navigation; `pytest -q` passes; `ruff check .` is clean.
Update docs/PROMPT_LOG.md and suggest a commit message.
```

---

## Phase 2 — Synthetic samples and golden files

```
Implement scripts/make_samples.py per SPEC §13.1 using reportlab.

Requirements:
- Generate S1–S6 into samples/, realistic in layout and language of Indian income-tax orders (title block, DIN line, NFAC/CIT(A) headings, numbered paras, "Ground No." headings, findings with operative sentences, computation table in S1). All names, PANs, DINs and addresses must be obviously fictitious.
- S6 = S2 rendered as images (rasterise each page with PyMuPDF at 150 dpi and rebuild the PDF), so it has no text layer.
- Write samples/expected/S1.json … S5.json conforming to the pydantic models in SPEC §6 (create models.py now, fully, per §6). The expected values must match exactly what the PDFs contain.
- tests/test_samples.py: the script runs, all files exist, and the expected JSON validates against the models.

Acceptance: `python scripts/make_samples.py` creates 6 PDFs; I can open them and they read like genuine orders; tests pass.
```

---

## Phase 3 — Ingestion, OCR, segmentation

```
Implement appealiq/ingest.py and appealiq/segment.py per SPEC §5, §8.1, §8.2, and the pipeline skeleton in appealiq/pipeline.py (StageResult, progress callback, per-stage try/except, CaseFile autosave).

Details:
- Tesseract detection: pytesseract.get_tesseract_version(); on Windows also look in "C:\Program Files\Tesseract-OCR\tesseract.exe". If not found, OCR pages are flagged NO_TEXT with a clear message (no crash).
- Header/footer stripping and para detection exactly as in §8.2. Keep page and para_no on every Para.
- An abbreviation-aware sentence splitter (list in §8.2).

Tests: tests/test_ingest.py and tests/test_segment.py covering validation errors (non-PDF, encrypted, too large), S2 para count and para numbers, header/footer removal, S6 OCR path (skip the test with a reason if Tesseract is unavailable), and the abbreviations not splitting sentences.

Acceptance: a small debug script `scripts/dump_paras.py <pdf>` prints page/para/text for inspection; tests pass.
```

---

## Phase 4 — Knowledge base and rules engine

```
Implement rules/*.yaml (SPEC §7.1–§7.8), appealiq/rules_engine.py and appealiq/tax_effect.py (SPEC §8.7, §8.8).

Requirements:
- Every YAML has a meta block, plus source and verified fields per entry. Load the YAML with pydantic models; report validation problems in the health check, not as crashes.
- Limitation per SPEC v1.1 §7.1: the `act`-keyed blocks, the months_from_month_end method (calendar_days 60 only before 01-10-2024), the weekend/holiday note (no auto-shift), the cross-objection date, RAG with an injected `today`, the expired → condonation note.
- Fee slabs per §7.2, including the stay application fee.
- Validity checks per §7.4 (implement the functions now; they take OrderHeader, issues and the Document so they can search the cue phrases).
- Tax effect per §8.8 using Decimal, with rounding to the nearest rupee (ROUND_HALF_UP), and the likelihood bands and exception keyword flags.
- Per-issue rate (CR-004): issues u/s 68, 69, 69A, 69B, 69C, 69D use the `special_rates` s. 115BBE rate (78%, verified: false) from rates.yaml; all others use the selected rate. Record `rate` and `rate_basis` on every TaxEffectLine.
- Indian currency formatting helper (₹12,34,567) in appealiq/outputs/styles.py or a utils module.

Tests: every row and boundary listed in SPEC §13.2 for rules_engine and tax_effect, including the exact S2 figures at the 25.168% preset (CR-004): Department ₹37,11,344 (₹35,10,000 for s. 68 at 78% + ₹2,01,344 for the s. 40(a)(ia) relief of ₹8,00,000) → UNLIKELY (61.9% of the ₹60 lakh limit); assessee ₹3,02,016.

Acceptance: pytest passes. Print a list of all verified: false entries for me.
```

---

## Phase 5 — Standard engine: classification and extraction

```
Implement appealiq/engines/base.py (Engine protocol, SPEC §9.1), appealiq/engines/standard.py, appealiq/classify.py, appealiq/extract_header.py, appealiq/extract_issues.py, rules/patterns.yaml, and scripts/train_classifier.py, per SPEC §8.3 and §8.4.

Requirements:
- Classification: the rule score and the TF-IDF + LogisticRegression model, combined 0.6/0.4; UNKNOWN below 0.55; Act detection with the 2025 banner flag.
- train_classifier.py: build a training corpus from the synthetic samples plus template-based paraphrases (at least 40 docs per class, generated programmatically); save models/classifier.joblib; print a classification report.
- Header extraction with label proximity; amounts in lakh/crore/commas; AY normalisation.
- Issue blocks per family; sentence roles by cue phrases plus TextRank top-3; outcome detection with operative weighting; amount logic for ALLOWED / PARTLY_ALLOWED.
- Every extracted value is wrapped in Field / Evidence with page, para_no and a verbatim snippet (≤ 400 chars).

Tests: golden tests for S1–S5 vs. samples/expected with the thresholds in SPEC §13.2; unit tests for amount parsing (e.g. "Rs. 45,00,000/-", "₹ 45 lakh", "Rs.4.5 crore"), AY parsing and outcome cues.

Acceptance: `python scripts/evaluate.py` (create a first version) shows field accuracy per sample; thresholds met.
```

---

## Phase 6 — Issue trail linking and verification

```
Implement appealiq/link.py (SPEC §8.5) and appealiq/verify.py (SPEC §8.6), and wire them into pipeline.py.

Requirements:
- Matching weights 0.5/0.3/0.2, acceptance ≥ 0.6, one-to-one assignment (greedy on the highest score). Fill amount_ao from the AO order if missing. Produce the "Addition not found in appellate order" observations.
- Verification normalisation and thresholds exactly as specified; reference auto-correction with logging; build verification_log entries in plain English (e.g. "Issue I3 – appellate finding extract not found on p.21 ¶9.5; found on p.22 ¶9.6 (reference corrected)").

Tests: S1+S2 produce a trail of 3 linked issues plus 1 unlinked legal ground, with correct references; a fabricated snippet is marked UNVERIFIED; a moved snippet is corrected.
```

---

## Phase 7 — Decision matrix, action plan, grounds, paper book

```
Implement appealiq/decide.py (SPEC §8.9, §7.5) and the deterministic grounds and paper book builders (SPEC §8.10, §8.11) as pure functions returning data models (the document rendering comes in Phase 9).

Requirements:
- The decision rules in strict priority order, with templated rationales.
- The action plan from actions.yaml, with dates from the LimitationResult.
- Grounds template, legal-ground template and the "craves leave" ground; concise, no argument.
- The paper book skeleton plus detected entries; the Rule 29 additional evidence heading where relevant.

Tests: one test per decision row; S2 expected decisions (legal ground → APPEAL; s. 68 → MONITOR/ACCEPT per likelihood; s. 14A → APPEAL; s. 40(a)(ia) → APPEAL_BALANCE); grounds text contains the correct amounts and sections.
```

---

## Phase 8 — LLM engines (LM Studio and Claude)

```
Implement appealiq/engines/lmstudio.py, appealiq/engines/claude.py and appealiq/engines/prompts/*.md per SPEC §9.2–§9.4.

Requirements:
- JSON schema generated from the pydantic models; strict validation; one retry with the error; then fall back to Standard per issue, recording engine_fallbacks.
- Para markers [p{page} ¶{para_no}] in the input; deterministic fields (header, amounts, dates) always come from Standard and override the LLM.
- strategy_note ≤ 80 words, labelled "AI-generated", rejected if it contains anything that looks like a citation (regex for "v.", "vs", "ITR", "SC", "ITAT", "(\d{4})").
- Availability checks with short timeouts; the UI-facing status text.
- Claude: lazy import, key from .env/settings, never logged; confidentiality acknowledgement flag required on the CaseFile before any call.

Tests: a mock LM Studio server (pytest fixture with http.server or respx) covering valid output, invalid → retry → fallback, timeout, and a citation-containing strategy note rejected. No real network calls in the tests.
```

---

## Phase 9 — Output documents

```
Implement appealiq/outputs/* per SPEC §11.

Requirements:
- styles.py: shared helpers (set cell shading, header row repeat, borders, zebra rows, right-align numbers, RAG fill, page X of Y field codes, header/footer with firm name and logo if set).
- report_docx.py: all 13 sections in §11.2, in order, using the CaseFile. Verbatim extracts in italic with [p/¶] references. AI content visibly labelled.
- grounds_docx.py, paperbook_docx.py per §11.3–§11.4.
- register_xlsx.py per §11.5, with the Indian number format and conditional formatting.
- pdf_convert.py: docx2pdf → LibreOffice → graceful notice.
- Outputs refuse to build unless casefile.approved_by is set.

Tests: generate all outputs for S1+S2, reopen them with python-docx/openpyxl, and assert the headings, table row counts, amounts and footer text.
Then render the report to PDF if possible and show me screenshots of pages 1–3 (or describe the layout if rendering is unavailable).
```

---

## Phase 10 — Full user interface

```
Implement the complete UI per SPEC §3 and §10.3–§10.4: Home, the New Analysis wizard (4 steps), Case Register (appealiq/register.py with SQLite), Settings (including "Test connection" for LM Studio and Cloud, and the health check panel from SPEC §12.1), and Help & About.

Requirements:
- The stepper, a summary strip and 6 review tabs exactly as specified; st.data_editor with select columns for outcome and recommendation; edits set USER_EDITED and instantly recompute rules/tax effect/decisions.
- The processing screen with live stage statuses, durations, log expander and cancel.
- The approval gate and output cards with download buttons.
- Friendly error callouts with a technical-details expander.
- Indian number and date formats everywhere.
- State persistence across steps and autosave of the CaseFile.
- setup.bat creates the "AppealIQ" desktop shortcut (custom icon, silent start, Edge app mode) per SPEC v1.1 §14.

Acceptance: I can run S1+S2 end to end in Standard mode, edit an outcome and see the tax effect and decisions update, approve, and download all 5 outputs. Take screenshots of each screen (Playwright, headless) into docs/screenshots/ and show them to me.
Also create a Windows desktop shortcut (via a script run by setup.bat) named ‘AppealIQ’ with a custom icon that starts the app silently and opens it in Microsoft Edge app mode (--app=http://localhost:8501), so it looks like a standalone desktop application. Closing the window should stop the app.
```

---

## Phase 11 — Hardening and polish

```
Act as a senior QA engineer and UX reviewer. Do the following:

1. Run the full app flow with every sample (S1–S6), and with deliberately bad inputs: a non-PDF, an encrypted PDF, a blank PDF, a 300-page PDF (generate one), a missing date of service, LM Studio offline, an invalid cloud key.
2. Fix every crash, unclear message, slow step (> SPEC §12.2 targets) or layout glitch you find.
3. UI polish pass against SPEC §10.1: spacing, alignment, consistent badges, number alignment, empty states, loading states, contrast. Remove any default Streamlit look that remains.
4. Run ruff and pytest with coverage. Raise the coverage of appealiq/ (excluding ui/) to ≥ 80%.
5. Give me a table of the issues found → fixes made.
6. (From the Phase 7 review) s. 263 issue titles should describe the PCIT's objection (e.g. "Non-examination of applicability of s. 43CA") rather than the nature + section fallback ("Addition u/s 43CA").
```

---

## Phase 12 — Evaluation and documentation

```
1. Finalise scripts/evaluate.py per SPEC §13.3 and generate docs/EVALUATION.md (include the Standard results, and LM Studio results if it is reachable on this machine).
2. Write README.md per SPEC §14 (with a Mermaid architecture diagram, Windows installation steps including Tesseract and LM Studio, the 6-step usage guide with screenshots from docs/screenshots, the evaluation table, controls, limitations, future scope, course modules applied, disclaimer, and author/batch/video placeholders).
3. Write docs/ARCHITECTURE.md (layers, pipeline, data model diagram) and docs/DEMO_SCRIPT.md (a 5–7 minute script per SPEC §14).
4. Complete docs/PROMPT_LOG.md.
5. Do a final clean-clone test: clone into a temp folder, run setup and tests, and confirm the app starts.
```

---

## Phase 13 — ICAI submission packaging

```
Prepare the repository for ICAI submission:
- Rename the instructions so the submission folder is AICA-L2-Batch-(<<BATCH>>)-<<FIRSTNAME>>-<<SURNAME>>.
- Ensure no real data, no .env, no logs, no large binaries (> 10 MB) are committed; samples are present.
- Add the video link placeholder <<VIDEO_LINK>> to the README.
- Give me the exact git commands for: fork aiinicai/AICA-Level-2-Projects, add my folder, commit, push to my fork, and open the pull request (title "Add AICA Level 2 Project - <<NAME>>" with a short description).
```

---

## Utility prompts (use any time)

**A. Bug fix**
```
Bug: <<what happened, steps, screenshot or error text>>.
Expected: <<what should happen>>.
Find the root cause first and explain it in 3 lines, then fix it. Add a regression test. Do not change unrelated code.
```

**B. Independent code review (use in a fresh session before submission)**
```
Review this repository against CLAUDE.md and docs/SPEC.md as a strict senior reviewer. Report, ranked by severity: spec deviations, legal-logic errors, places where an LLM could influence a deterministic value, unverified data reaching outputs, privacy leaks, unhandled errors, UX inconsistencies, and missing tests. Do not fix anything yet — give me the list first.
```

**C. UI refinement**
```
Here is a screenshot of <<screen>>: <<attach>>. Refine it to look like a premium advisory-firm product: tighten the spacing to the 8 px grid, align the numbers, use the design tokens in SPEC §10.1, improve the visual hierarchy, and keep it accessible. Show before/after screenshots.
```

**D. Legal value update**
```
Update rules/<<file>>.yaml: <<provision, new value, source/circular, date>>. Set verified: true with source and reviewer <<name>>. Update the affected tests and the rules annexure in the report.
```
