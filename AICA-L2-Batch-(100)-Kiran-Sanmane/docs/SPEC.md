# AppealIQ — Product & Technical Specification (v1.1)

> Source of truth for building AppealIQ. Section numbers (§) are referenced in `CLAUDE.md` and `docs/PROMPTS.md`.
> Legal values are under the **Income-tax Act, 1961**, as generally applied. Every legal value lives in `rules/*.yaml` with `verified` and `source` fields. **The firm must verify each value before production use.** Provisions under the Income-tax Act, 2025 are added only as separate blocks keyed by `act`, and stay `verified: false` until the firm confirms them.

### Change note — v1.1 (CR-001, 31-10-2026)

Decisions taken after the Phase 0 review (full record in `docs/PROMPT_LOG.md`, CR-001):

| Ref | Change | Sections |
|---|---|---|
| L1 | v1 handles orders for tax years governed by the Income-tax Act, 1961 (saved by s. 536 of the 2025 Act). Reliable Act detection with a prominent banner for 2025-Act orders. `forum_limitation.yaml` and `fees.yaml` are keyed by `act`; a 2025 block (s. 362, Form 115 / Form 116) is seeded `verified: false`. | §2.2, §7, §8.3 |
| L2 | Limitation is two months from the end of the month in which the order is communicated (s. 253(3) as amended by the Finance (No. 2) Act, 2024, w.e.f. 01-10-2024; s. 362(3) of the 2025 Act). 60 calendar days only for orders communicated before 01-10-2024. Cross-objections: 30 days from receipt of the notice of appeal. | §1, §7.1, §8.7, §13.2 |
| L3 | Department-appeal likelihood and decision rules 7–9 apply only to `CITA_250` (which includes JCIT(A) orders). Other families show "Not applicable". | §2.1, §8.8, §8.9 |
| L4 | New decision rule 0 for 263 and CIT(E) orders; each addition in a DRP final order is treated as `DISMISSED`. | §8.9 |
| L5 | Exception keywords are matched as whole words / phrases and shown with evidence; the reviewer can clear them. | §8.8 |
| L6 | Non-working-day note asks the user to verify the ITAT bench holiday list. | §7.1, §7.7 |
| S2–S4 | `Field[T]` renamed `ExtractedField[T]` (`Generic[T]`). Added `OrderFamily`, `Act`, `ClassificationResult`, `StageResult`, `MatterInputs`, `PaperBookEntry` and extra `CaseFile` fields. | §6 |
| S5–S14, S16–S18 | Clarifications: blocking service-date error, amount rules per outcome, injectable `today`, linking of legal issues, penalty detection, `ASSESSMENT_AO` as main order blocked, role model, rule-score normalisation, golden-file schema, security-scan scope, cancellable worker thread, matter-ID sanitising, early minimal register. | §5–§8, §10, §12, §13 |
| S15 | Playwright added as a dev-only dependency (README screenshots). | §13, §14 |
| (a) | Stay of demand application fee ₹500 (`verified: false`). | §7.2 |
| (b) | ITAT e-filing mandatory from 01-10-2026 (ITAT Practice Note dated 30-09-2026): appeals, paper books and stay applications filed on the ITAT e-filing portal with a digital signature (`verified: false`). | §7.5, §8.11 |
| (c) | `setup.bat` creates a Windows desktop shortcut "AppealIQ" that starts the app silently in Microsoft Edge app mode (delivered in Phase 10). | §14 |

### Change note — CR-004 (31-10-2026)

| Ref | Change | Sections |
|---|---|---|
| CR-004.1 | Tax effect uses a **per-issue rate**: additions u/s 68, 69, 69A, 69B, 69C and 69D take the s. 115BBE rate (60% + surcharge 25% + cess 4% = 78%, `verified: false`) from a new `special_rates` block in `rates.yaml`; all other issues use the selected effective rate. The rate and its basis are shown per issue in the Tax Effect tab, the report and the register. `TaxEffectLine` gains `rate_basis`. | §6.4, §7.8, §8.8, §10.3, §11.2, §11.5 |
| CR-004.2 | Sample S1 computation made internally consistent (normal income at 25.168%, s. 68 addition u/s 115BBE at 78%, illustrative interest u/s 234B). | §13.1 |
| CR-004.3 | Phase 4 expected S2 figures: Department ₹37,11,344 → UNLIKELY; assessee ₹3,02,016. | §13.2 |

### Change note — CR-005 (31-10-2026, Phase 7 review)

| Ref | Change | Sections |
|---|---|---|
| CR-005.1 | `Issue.title` is a clean label (≤ 80 characters, never a cut-off sentence), built from the main clause of the heading or from nature + section (e.g. "Disallowance u/s 14A"). New field `Issue.title_evidence` holds the full heading sentence verbatim and is verified like other evidence. | §6.3, §8.6 |
| CR-005.2 | Ex parte orders: when the EX_PARTE flag is raised, every adverse issue is appealed (priority by its own tax effect) so the whole order can be restored; the natural-justice ground comes first, with a prayer for restoration to the CIT(A) / JCIT(A). | §8.9, §8.10 |

### Change note — CR-006 (01-11-2026, Phase 9 review)

Report refinements after a senior tax-litigation review (full record in `docs/PROMPT_LOG.md`, CR-006). They supersede §11.1 (header text: "Privileged & Confidential — prepared in contemplation of litigation"), §11.2 (16 sections: adds Consequential matters, Proposed grounds of appeal and Sign-off; landscape issue trail and tax effect; "Revenue" wording; provisions-applied annexure) and §8.11 (issue-specific evidence from `rules/evidence_checklists.yaml`, Rule 18 certification). New rules files `legal_checklists.yaml`, `evidence_checklists.yaml` and `consequential.yaml` are seeded `verified: false`. Order giving effect: estimated revised tax = tax on additions sustained at the per-issue rates, plus consequential interest recomputed by the AO.

### Change note — CR-007 (01-11-2026, Phase 10 review)

Additions approved after the Phase 10 review (full record in `docs/PROMPT_LOG.md`, CR-007).

| Ref | Change | Sections |
|---|---|---|
| CR-007.1 | `Decision.status` (`FieldStatus`, default `OK`; `USER_EDITED` when the reviewer overrides the recommendation or priority) and `Decision.original_recommendation` (the rule-based recommendation, kept while overridden). An override survives every re-run of §8.7–§8.9 and is noted in the rationale. | §6.4, §8.9, §10.3 |
| CR-007.2 | `CaseFile.grounds_edited` and `CaseFile.paper_book_edited` (`bool`, default `False`): reviewer edits to the grounds or paper book index are kept when the rules re-run, until the reviewer restores the generated version. | §6.4, §8.10, §8.11, §10.3 |
| CR-007.3 | `outputs/matters_xlsx.py`: Excel export of the case register (one "Matters" sheet; same styling as §11.5, with days left and RAG for the current date). | §4, §10.3, §11 |
| CR-007.4 | Issue Trail: each issue panel also has an Outcome dropdown (with the AO amount and the amount sustained for a partly allowed issue). It makes the same edit as the grid and is keyboard-friendly. | §10.3, §10.4 |

### Change note — CR-008 (01-11-2026, Phase 11 review)

Approved after Phase 11, hardening and the owner's UI findings U1–U7 (full record in `docs/PROMPT_LOG.md`, CR-008).

| Ref | Change | Sections |
|---|---|---|
| CR-008.1 | The Issue Trail grid is a wrapping table (Issue · Ground · Title · Section · AO amount · Outcome · Relief · Sustained · Refs · Status), not `st.data_editor`: data_editor cells cannot wrap, and titles must not be truncated or scroll sideways at 1366 px. The AO and appellate references share one "Refs" column. Title, section, outcome and amounts are edited in each issue panel. | §10.3 |
| CR-008.2 | Every §5 validation message keeps its text and adds a suggested fix. A PDF with no readable text on any page stops at ingest with its own message (and the OCR status when Tesseract is unavailable). Every user-facing message, including AI-note failures, is plain English with a suggested fix. | §5, §10.4 |
| CR-008.3 | Streamlit's page list is hidden. The sidebar is drawn by `ui/nav.py`: the AppealIQ wordmark and version at the top, the five pages, and a badge at the bottom ("Offline · Data stays on this computer", or "Cloud mode on" when the cloud engine is used for the current matter). Home is served at the root URL; "/home" is an alias. | §4, §10.2 |
| CR-008.4 | s. 263 issue titles state the PCIT's objection (e.g. "Non-examination of applicability of s. 43CA", "Non-verification of sub-contract expenses …"). A title that would otherwise be "Addition u/s X" becomes "Objection relating to s. X". | §6.3 |
| CR-008.5 | `monetary_limits.yaml` `circular` reworded without nested brackets: "CBDT Circular No. 9/2024 dated 17-09-2024, amending Circular No. 5/2024". Wording only; the entry stays `verified: true`. | §7.3 |

---

## §1 Purpose and problem statement

When an order appealable to the ITAT is received, the practitioner has until the end of the second month after the month of communication (s. 253(3), as amended w.e.f. 01-10-2024) to do the following:

- trace each addition or disallowance from the AO's order to its appellate outcome;
- decide which issues to carry to the ITAT;
- judge whether the Department is likely to appeal (monetary limits);
- decide on cross-objections;
- draft concise grounds;
- assemble the paper book.

Today this is done by hand across 50–150 pages of orders, so issues get missed, limitation dates slip, and the work is inconsistent from one matter to the next.

**AppealIQ** turns these orders into a verified, para-referenced decision report and filing kit, offline, in minutes. A professional reviews the output before it is used.

**Users:** CA partners and managers in tax litigation, article assistants (preparing first drafts), and reviewing partners.

---

## §2 Scope

### §2.1 Version 1 (must deliver)

| # | Capability |
|---|---|
| 1 | Upload the main order (PDF); optionally upload the AO's order (PDF) |
| 2 | Text extraction with an OCR fallback for scanned pages |
| 3 | Order-family classification: `CITA_250` (orders of the CIT(A), NFAC or JCIT(A) u/s 250), `REVISION_263`, `CITE_12AB_80G`, `DRP_FINAL_144C13`, `ASSESSMENT_AO` (input only), `UNKNOWN` |
| 4 | Header extraction (§6.2) |
| 5 | Issue / ground extraction with roles and outcomes (§6.3) |
| 6 | Issue trail linking the AO's order with the appellate order (§8.5) |
| 7 | Snippet verification and confidence (§8.6) |
| 8 | Rules engine: forum, form, limitation, cross-objection window, fee, validity checks, RAG status (§7, §8.7) |
| 9 | Tax effect and monetary-limit assessment (§8.8) |
| 10 | Decision matrix and action plan (§8.9) |
| 11 | Review and edit UI with an approval gate (§10) |
| 12 | Outputs: report (DOCX / PDF), draft grounds (DOCX), paper book index (DOCX), issue register (XLSX) (§11) |
| 13 | Matter register (SQLite) with a due-date dashboard |
| 14 | Three engines: Standard (always), LM Studio (local), Claude (cloud, optional) (§9) |
| 15 | Synthetic samples, tests, evaluation script, setup and run scripts, README (§13–§14) |

### §2.2 Out of scope (list in README under "Future scope")

- Case-law library and RAG
- Income-tax Act, 2025 provision mapping. v1 handles orders for tax years governed by the Income-tax Act, 1961 (saved by s. 536 of the 2025 Act). A 2025-Act order is detected and flagged with a prominent banner (§8.3); its forum, limitation and fee come from the seeded, unverified 2025 blocks and must be checked manually.
- High Court appeal stage (s. 260A)
- Portal filing
- Cause-list tracking
- Multi-user login
- MCP server wrapper
- Slab-wise tax computation (v1 uses an effective-rate input)

---

## §3 User journey

```
Launch (run.bat) → Home dashboard → New Analysis wizard:
  Step 1 Upload & Details → Step 2 Processing → Step 3 Review & Edit → Step 4 Approve & Download
→ Matter saved in Register
```

| Step | Inputs | System behaviour |
|---|---|---|
| Launch | — | Streamlit starts on `localhost:8501`. Telemetry is off. Health check runs (§12.1). |
| Upload & Details | Matter ID, client name, main order PDF, optional AO order PDF, **date of service (mandatory)**, "Department's appeal received?" (Y/N + date of receipt), assessee status / effective tax rate (§8.8), engine choice | Validate inputs. The **Process** button stays disabled until the mandatory fields are filled. |
| Processing | — | Stage-by-stage progress (§8), with a live log panel. Can be cancelled. |
| Review & Edit | Edits in 6 tabs | Re-runs the rules, tax effect and decision stages whenever the data changes |
| Approve & Download | Reviewer name and approval checkbox | Generates the outputs and saves the matter to the register |

---

## §4 Architecture

| Layer | Modules | Notes |
|---|---|---|
| L1 UI | `app.py`, `appealiq/ui/*` | Streamlit with a custom theme. Only UI code imports Streamlit. |
| L2 Orchestration | `pipeline.py` | Runs the stages in order, passes a `CaseFile` object, and reports `StageResult`s to a progress callback |
| L3 Processing | `ingest, segment, classify, extract_header, extract_issues, link, verify, rules_engine, tax_effect, decide` | Pure functions taking and returning pydantic models |
| L4 Engines | `engines/standard, lmstudio, claude` | Common `Engine` protocol (§9.1) |
| L5 Knowledge base | `rules/*.yaml` | Loaded once, validated by pydantic, cached |
| L6 Outputs | `outputs/*` | Built from an approved `CaseFile` only |
| L7 Storage | `register.py`, `data/` | SQLite plus the file system |

**Pipeline order:** `ingest → segment → classify → extract_header → extract_issues → link → verify → rules → tax_effect → decide`.
If the AO's order is uploaded, it is ingested, segmented, classified and its header and issues extracted in parallel with the main order, before `link`.

---

## §5 Inputs and validation

| Check | Rule | Error message |
|---|---|---|
| File type | `.pdf` only | "Please upload a PDF file." + fix: download the order again from the e-filing portal (or print it to PDF) and upload that file (CR-008.2) |
| Size | ≤ 50 MB | "File exceeds 50 MB." + fix: upload the order without annexures, or re-save the PDF at a lower image resolution |
| Encrypted | Try an empty password; otherwise reject | "This PDF is password-protected. Please remove the password and upload again." |
| Pages | 1–400 | "PDF must have between 1 and 400 pages." + fix: upload the order itself, without long annexures or paper books |
| Readable text | At least one page with text (text layer or OCR); otherwise stop at ingest | "No readable text was found in this PDF …" + fix: upload the text PDF from the e-filing portal or a clearer scan (300 dpi); the OCR status is added when Tesseract is unavailable (CR-008.2) |
| Duplicate | SHA-256 hash matches an existing matter (a minimal `register.py` with `find_by_sha()` exists from Phase 3) | Warning naming the existing matter, with the fix "open it from the Case Register" (not a block) |
| Date of service | Mandatory; not in the future; not before the date of the order (checked after header extraction). Service before the order date is a **blocking error** stored in `CaseFile.blocking_errors`; approval is disabled until it is fixed. | Inline validation |
| Matter ID | Required; sanitised to `[A-Za-z0-9_-]` before it is used in a path (`data/matters/{matter_id}`) | "Case ID may contain letters, digits, hyphens and underscores only." |
| Main order family | If the main order classifies as `ASSESSMENT_AO` → block | "This is an assessment order — appeal lies to the CIT(A), not the ITAT. Upload it in the optional AO order slot." |
| Text yield | A page with < 50 characters of text → OCR. If Tesseract is missing → page flagged `NO_TEXT` | Notice in the verification log |

---

## §6 Data model (`appealiq/models.py`, pydantic v2)

### §6.1 Core containers

```python
class Para(BaseModel):
    doc_id: str            # "MAIN" | "AO"
    page: int              # 1-based
    para_no: str | None    # e.g. "5.3", "7(a)", None if unnumbered
    idx: int               # running index within doc
    text: str
    ocr: bool = False
    ocr_confidence: float | None = None

class Document(BaseModel):
    doc_id: str
    filename: str
    sha256: str
    pages: int
    paras: list[Para]
    ocr_pages: list[int] = []
    no_text_pages: list[int] = []

class Evidence(BaseModel):
    doc_id: str
    page: int
    para_no: str | None
    source_snippet: str           # verbatim, ≤ 400 chars
    verified: bool = False
    match_score: float | None = None

class ExtractedField(BaseModel, Generic[T]):   # generic wrapper used for header values
    value: T | None                            # (named to avoid clashing with pydantic.Field)
    evidence: Evidence | None
    confidence: float             # 0–1
    status: Literal["OK","LOW_CONFIDENCE","UNVERIFIED","NOT_FOUND","USER_EDITED"]

class OrderFamily(StrEnum):
    CITA_250 = "CITA_250"; REVISION_263 = "REVISION_263"; CITE_12AB_80G = "CITE_12AB_80G"
    DRP_FINAL_144C13 = "DRP_FINAL_144C13"; ASSESSMENT_AO = "ASSESSMENT_AO"; UNKNOWN = "UNKNOWN"

class Act(StrEnum):
    IT_ACT_1961 = "IT_ACT_1961"; IT_ACT_2025 = "IT_ACT_2025"; UNKNOWN = "UNKNOWN"

class ClassificationResult(BaseModel):
    family: OrderFamily
    rule_scores: dict[OrderFamily, float]; ml_scores: dict[OrderFamily, float]
    final_scores: dict[OrderFamily, float]; confidence: float
    act: Act; act_evidence: Evidence | None
    needs_user_choice: bool                    # top score < 0.55

class StageResult(BaseModel):
    stage: str; status: Literal["ok","warn","failed"]
    message: str; duration_ms: int
```

Header values that are user inputs (e.g. `date_of_service`) are wrapped with `evidence=None`, `confidence=1.0` and status `OK` (or `USER_EDITED` after a change).

### §6.2 Header (`OrderHeader`)

| Field | Type | Notes |
|---|---|---|
| order_family | enum (§2.1 item 3) | |
| section | str | e.g. "250", "263", "12AB", "143(3) r.w.s. 144C(13)" |
| act | enum `IT_ACT_1961` / `IT_ACT_2025` / `UNKNOWN` | |
| authority | str | e.g. "CIT(A)", "NFAC", "PCIT", "CIT(E)" |
| authority_location | str | |
| din | str | Pattern: `ITBA/` prefix with a number, or a numeric-only DIN. Keep the regex in `rules/patterns.yaml`. |
| pan | str | Regex `[A-Z]{5}[0-9]{4}[A-Z]` |
| assessee_name | str | |
| assessment_year | str | Normalised "YYYY-YY" |
| appeal_no | str | CIT(A) / NFAC appeal number |
| date_of_order | date | |
| date_of_service | date | **User input only** |
| original_order_section | str | For CIT(A) / 263: section of the order under appeal or revision |
| original_order_date | date | Needed for the s. 263(2) limitation check |
| returned_income, assessed_income | int | |
| demand | int | |
| ex_parte | bool | Decided without the appellant's representation |
| rule_46a_invoked | bool | Additional evidence admitted / remand report |

Each value is wrapped in `ExtractedField[...]`.

### §6.3 Issue (`Issue`)

| Field | Type | Notes |
|---|---|---|
| issue_id | str | "I1", "I2"… |
| ground_nos | list[str] | Grounds as numbered by the appellate authority |
| title | str | Short label, e.g. "Unexplained cash credit u/s 68": ≤ 80 characters, never a cut-off sentence; from the main clause of the heading, else nature + section (CR-005.1). For s. 263 orders, the PCIT's objection, e.g. "Non-examination of applicability of s. 43CA"; else "Objection relating to s. X" (CR-008.4) |
| title_evidence | Evidence \| None | The full heading sentence the title was built from, verbatim; verified in §8.6 (CR-005.1) |
| section | str \| None | Normalised, e.g. "68", "14A", "40(a)(ia)" |
| nature | enum `ADDITION` / `DISALLOWANCE` / `LEGAL_JURISDICTIONAL` / `PROCEDURAL` / `PENALTY` / `OTHER` | Legal grounds include reopening validity, limitation, DIN, jurisdiction, natural justice |
| amount_ao | int \| None | Addition made by the AO |
| amount_relief | int \| None | Relief granted by the appellate authority |
| amount_sustained | int \| None | = amount_ao − amount_relief, where both are known |
| outcome | enum `ALLOWED` / `PARTLY_ALLOWED` / `DISMISSED` / `RESTORED_TO_AO` / `NOT_ADJUDICATED` / `INFRUCTUOUS` / `UNKNOWN` | |
| ao_contention | list[Evidence] | |
| assessee_submission | list[Evidence] | |
| appellate_finding | list[Evidence] | |
| summary | str \| None | Only in Local / Cloud mode; always shown with its evidence |
| ao_evidence_link | Evidence \| None | Location in the AO's order (from `link.py`) |
| confidence | float | |
| status | as in `ExtractedField.status` | |

**Amounts by outcome (v1.1):**

| Outcome | amount_relief | amount_sustained | In tax effect? |
|---|---|---|---|
| ALLOWED | = amount_ao | 0 | Department side |
| PARTLY_ALLOWED | ao − X ("restricted to X") | X | Both sides |
| DISMISSED, NOT_ADJUDICATED | 0 | = amount_ao | Assessee side |
| RESTORED_TO_AO, INFRUCTUOUS, UNKNOWN | None | None | Excluded, with a verification-log entry |

For `DRP_FINAL_144C13`, each addition in the final order is treated as `DISMISSED`. A penalty matter is recognised by `nature = PENALTY`; its amount is the penalty in dispute.

### §6.4 Derived models

```python
class LimitationResult(BaseModel):
    act: Act; forum: str; form: str; provision: str
    method: Literal["months_from_month_end","calendar_days"]
    start_date: date; period: int              # months or days, per method
    due_date: date
    days_remaining: int; rag: Literal["RED","AMBER","GREEN","EXPIRED"]   # relative to `today`
    cross_objection_due: date | None
    notes: list[str]; verified: bool

class FeeResult(BaseModel): amount: int; basis: str; verified: bool

class ValidityFlag(BaseModel):
    code: str; title: str; severity: Literal["HIGH","MEDIUM","INFO"]
    observation: str; evidence: Evidence | None; basis: str

class TaxEffectLine(BaseModel):
    issue_id: str; side: Literal["ASSESSEE","DEPARTMENT"]
    income_in_dispute: int; rate: Decimal; tax_effect: int
    rate_basis: str                            # CR-004: "s. 115BBE" or the selected preset

class TaxEffectSummary(BaseModel):
    lines: list[TaxEffectLine]
    dept_total: int; assessee_total: int
    itat_limit: int
    dept_appeal_likelihood: Literal["UNLIKELY","POSSIBLE","LIKELY","NOT_APPLICABLE"]
    exception_flags: list[str]; rate_basis: str

class Decision(BaseModel):
    issue_id: str
    recommendation: Literal["APPEAL","APPEAL_BALANCE","CROSS_OBJECT","MONITOR",
                            "PURSUE_SET_ASIDE","ACCEPT","EVALUATE"]
    rationale: str; priority: Literal["HIGH","MEDIUM","LOW"]
    status: FieldStatus = "OK"                     # CR-007: USER_EDITED when overridden
    original_recommendation: str | None = None     # CR-007: rule-based value, if overridden

class Action(BaseModel):
    action: str; form: str | None; due_date: date | None
    documents: list[str]; priority: str; owner: str | None

class MatterInputs(BaseModel):                 # Step 1 inputs (§3)
    date_of_service: date
    dept_appeal_received: bool = False; dept_appeal_receipt_date: date | None = None
    rate_preset: str; rate: Decimal; rate_basis: str
    engine: Literal["standard","lmstudio","claude"]

class PaperBookEntry(BaseModel):               # §8.11
    s_no: int; particulars: str
    filed_before: Literal["AO","CIT(A)","NEW_RULE_29"] | None
    pages: str | None; detected_from: Evidence | None

class CaseFile(BaseModel):
    matter_id: str; client: str; created: datetime
    inputs: MatterInputs
    engine_used: str; engine_fallbacks: list[str]
    cloud_ack: bool = False; cloud_used: bool = False      # §9.3
    main: Document; ao: Document | None
    classification: ClassificationResult | None
    header: OrderHeader; ao_header: OrderHeader | None
    issues: list[Issue]
    unmatched_ao: list[Issue] = []                         # §8.5
    limitation: LimitationResult | None; fee: FeeResult | None
    validity: list[ValidityFlag]; tax_effect: TaxEffectSummary | None
    decisions: list[Decision]; actions: list[Action]
    grounds: list[str] = []; paper_book: list[PaperBookEntry] = []
    grounds_edited: bool = False; paper_book_edited: bool = False   # CR-007: kept on re-run
    blocking_errors: list[str] = []                        # e.g. SERVICE_BEFORE_ORDER
    stage_results: list[StageResult] = []
    verification_log: list[str]; approved_by: str | None; approved_at: datetime | None
```

---

## §7 Knowledge base (`rules/`)

Every YAML file has a top-level `meta: {version, last_reviewed, reviewer, act}`, and every legal entry has `source` and `verified: true|false`. Loading fails loudly (but not with a crash) if the schema is invalid.

### §7.1 `forum_limitation.yaml`

The file is keyed by `act` (`IT_ACT_1961`, `IT_ACT_2025`), so a verified 2025 block can replace the seed later without code changes. Every entry has `source` and `verified`.

**IT Act, 1961 block**

| order_family | forum | provision | form | start | cross-objection |
|---|---|---|---|---|---|
| CITA_250 (incl. JCIT(A)) | ITAT | s. 253(1)(a) | Form 36 | date of service | 30 days from receipt of the notice of the other side's appeal — s. 253(4), Form 36A |
| REVISION_263 | ITAT | s. 253(1)(c) | Form 36 | date of service | n/a |
| CITE_12AB_80G | ITAT | s. 253(1)(c) | Form 36 | date of service | n/a |
| DRP_FINAL_144C13 | ITAT | s. 253(1)(d) | Form 36 | date of service | s. 253(4) — `verified: false` (the Department does not appeal DRP-directed orders; shown as n/a unless confirmed) |

**Limitation methods (s. 253(3))**

| Method | Applies when | Rule |
|---|---|---|
| `months_from_month_end` | date of communication ≥ 01-10-2024 (Finance (No. 2) Act, 2024) | `due_date` = last day of the month in which the order is communicated, plus 2 months, clamped to the last day of that month |
| `calendar_days` | date of communication < 01-10-2024 | `due_date` = date of communication + 60 calendar days |

The date of service entered by the user is taken as the date of communication. The method, period, switch-over date and source live in the YAML (`verified: false` until the firm confirms).

Worked examples (also test cases):

| Date of service | Method | Due date | Note |
|---|---|---|---|
| 20-10-2026 | months_from_month_end | 31-12-2026 | — |
| 15-12-2026 | months_from_month_end | 28-02-2027 | Sunday → non-working-day note; date **not** shifted |
| 30-09-2024 | calendar_days | 29-11-2024 | — |

**IT Act, 2025 block (seed, all `verified: false`)**

| order_family | forum | provision | form (appeal) | form (cross-objections) | limitation |
|---|---|---|---|---|---|
| all ITAT-appealable families | ITAT | s. 362 | Form 115 | Form 116 | `months_from_month_end`, 2 months (s. 362(3)) |

Cross-objections: 30 days from receipt of the notice of appeal (s. 253(4); same in the 2025 block). If the due date falls on a Saturday, Sunday or a holiday in `holidays.yaml`, add the note "Due date falls on a non-working day — verify against the ITAT bench holiday list". **Do not shift the date automatically.** Condonation note if expired: "Limitation expired — consider a condonation application u/s 253(5) with an affidavit explaining sufficient cause."

### §7.2 `fees.yaml` — s. 253(6), all `verified: false` until the firm confirms

Keyed by `act` like §7.1. The 2025 block is seeded empty, with a note that fees must be entered and verified before use.

| Condition | Fee |
|---|---|
| Assessed income ≤ ₹1,00,000 | ₹500 |
| > ₹1,00,000 and ≤ ₹2,00,000 | ₹1,500 |
| > ₹2,00,000 | 1% of assessed income, max ₹10,000 |
| Appeal not relating to assessed income (e.g., 263 / 12AB / 80G) | ₹500 |
| Memorandum of cross-objections | Nil |
| Application for stay of demand | ₹500 |

### §7.3 `monetary_limits.yaml`

```yaml
circular: "CBDT Circular No. 9/2024 dated 17-09-2024, amending Circular No. 5/2024"
limits: { ITAT: 6000000, HIGH_COURT: 20000000, SUPREME_COURT: 50000000 }
tax_effect_definition: >
  Difference between tax on total income assessed and tax that would have been chargeable had
  such income been reduced by the disputed issues; tax includes surcharge and cess, excludes interest
  (except where interest itself is disputed). Penalty orders: tax effect = penalty in dispute.
  Computed separately for each assessment year.
exceptions_note: >
  Para 3.1/3.2 of Circular 5/2024 lists cases where appeal is decided on merits irrespective of tax
  effect (e.g., constitutional validity, audit objections, organised tax evasion, etc.) – flag for review.
verified: false
```

### §7.4 `validity_checks.yaml`

| code | applies to | logic | severity |
|---|---|---|---|
| DIN_MISSING | all | DIN not found in the main order | HIGH. Basis: CBDT Circular No. 19/2019 |
| EX_PARTE | CITA_250 | Cue phrases: "none appeared", "no compliance", "ex parte", "decided on the basis of material on record", "dismissed for non-prosecution" | HIGH — "Consider seeking restoration before the ITAT for fresh adjudication" |
| NOT_ADJUDICATED | CITA_250 | Any issue with outcome `NOT_ADJUDICATED` | HIGH |
| RULE_46A | CITA_250 | Additional evidence admitted without a reference to a remand report, or rejected | MEDIUM |
| R263_LIMITATION | REVISION_263 | `date_of_order` > end of the FY in which `original_order_date` falls, plus 2 years (s. 263(2)) | HIGH, if computable; otherwise INFO "Original order date not found" |
| R263_TWIN | REVISION_263 | Cue phrases "erroneous" AND "prejudicial to the interests of the revenue" found in the operative part | INFO, with evidence. If one is missing → HIGH |
| R263_HEARING | REVISION_263 | No reference to a show-cause notice or opportunity of hearing | HIGH |
| CITE_HEARING | CITE_12AB_80G | No reference to a hearing or opportunity | HIGH |
| SERVICE_BEFORE_ORDER | all | Date of service earlier than date of order | Blocking validation error — recorded in `CaseFile.blocking_errors`, not as a `ValidityFlag`; approval stays disabled until fixed |

### §7.5 `actions.yaml` — action library (templated, deterministic)

ITAT e-filing is mandatory from 01-10-2026 (ITAT Practice Note dated 30-09-2026; `verified: false`): appeals, cross-objections, paper books and stay applications are filed on the ITAT e-filing portal and signed with a digital signature. The action texts below reflect this; the `form` column uses the form for the detected Act (§7.1).

| trigger | action text (templated) | form | due |
|---|---|---|---|
| any APPEAL / APPEAL_BALANCE | "E-file the appeal on the ITAT e-filing portal against {issue_titles}, signed with a digital signature; upload the order appealed against and the order of the lower authority" | Form 36 | limitation.due_date |
| always (if appealing) | "Pay appeal fee of ₹{fee} and upload the challan with the e-filed appeal" | Challan | due_date |
| CROSS_OBJECT and Department's appeal received | "E-file the memorandum of cross-objections on the ITAT e-filing portal, supporting the order on issues decided in favour" | Form 36A | cross_objection_due |
| dept_appeal_likelihood ∈ {POSSIBLE, LIKELY} and not received | "Diarise: monitor receipt of the Department's appeal; cross-objections within 30 days of receipt" | — | — |
| demand outstanding | "Evaluate a stay of demand application before the ITAT u/s 254(2A), to be e-filed with a digital signature (fee ₹{stay_fee}; verify current deposit conditions)" | Stay petition | — |
| ex_parte flag | "Prepare an affidavit explaining non-appearance; seek restoration / remand" | — | — |
| always | "Prepare the paper book (see index) and an issue-wise synopsis as indexed, paginated PDFs for upload on the ITAT e-filing portal" | — | 7 days before the hearing |
| REVISION_263 / CITE_12AB_80G | "Ground on the twin conditions / grounds of rejection; challenge the assumption of jurisdiction" | Form 36 | due_date |

The e-filing requirement and its effective date are an entry in `actions.yaml` with `source` and `verified: false`.

### §7.6 `patterns.yaml`

Regexes for DIN, PAN, AY, dates (DD.MM.YYYY, DD/MM/YYYY, DD-MM-YYYY, "15th October, 2026"), amounts (₹ / Rs. / INR, lakh, crore, with commas, "/-"), section references (`(?:u/s|section|sec\.?)\s*\d+[A-Z]*(?:\(\w+\))*`), para numbering, and outcome cue phrases (§8.4.4). Also: the classification cue dictionary with weights per family (§8.3), and `act_2025_markers` (title phrases such as "Income-tax Act, 2025" and the 2025-Act section style) used for Act detection.

### §7.7 `holidays.yaml`

The national gazetted holidays list for the current year, editable by the user. ITAT benches publish their own holiday lists, so the non-working-day note always asks the user to verify against the bench list.

### §7.8 `rates.yaml` — effective rate presets (incl. surcharge and cess), `verified: false`

| Preset | Rate |
|---|---|
| Domestic company s. 115BAA | 25.168% |
| Domestic company (normal, 25% rate, income ₹1–10 cr: SC 7%) | 27.82% |
| Firm / LLP (income > ₹1 cr) | 34.944% |
| Firm / LLP (income ≤ ₹1 cr) | 31.2% |
| Individual (top slab, old regime, without surcharge) | 31.2% |
| Custom | user input |

The UI must show: "Effective marginal rate is used for tax effect; verify for surcharge thresholds and the regime applicable."

**Rate table (CR-009 Session C).** `rates.yaml` v2.0.0 lists 33 presets, each with `category` → `regime` → `band` (income band for the surcharge). The selector picks Category → Regime / section → Income band. Effective rate = statutory rate × (1 + surcharge) × 1.04 (Health and Education Cess):

| Category | Regimes / sections | Bands (surcharge) |
|---|---|---|
| Company | s. 115BAA 22% (SC 10%) · normal 25% (turnover up to ₹400 crore) · normal 30% · s. 115BAB 15% (SC 10%) | up to ₹1 crore (nil) · ₹1–10 crore (7%) · above ₹10 crore (12%) |
| Firm / LLP | normal 30% | up to ₹1 crore (nil) · above ₹1 crore (12%) |
| Individual / HUF | old regime (top slab 30%) · new regime s. 115BAC (surcharge capped at 25%) | up to ₹50 lakh · ₹50 lakh–1 crore (10%) · ₹1–2 crore (15%) · ₹2–5 crore (25%) · above ₹5 crore (37%, old regime) |
| Co-operative society | normal (top slab 30%) · s. 115BAD 22% (SC 10%) · s. 115BAE 15% (SC 10%) | as for companies (normal) |
| AOP / BOI | old regime · new regime s. 115BAC | as for individuals |

The five v1 presets keep their codes (saved cases still open) and their `verified: true`; every other entry is `verified: false`. Marginal relief, the lower surcharge caps on s. 111A / 112 / 112A gains and dividends, and AOPs of companies only are not modelled: the reviewer uses the **per-issue rate override** in the Tax Effect tab (`Issue.rate_override` / `rate_override_basis`), which takes precedence over the special and selected rates.

**Special rates (CR-004).** A `special_rates` block overrides the selected preset for issues whose normalised `section` is in its list. It is applied by section only, never by keywords in the text:

```yaml
special_rates:
  - code: S115BBE
    provision: "115BBE"
    sections: ["68", "69", "69A", "69B", "69C", "69D"]
    rate: "0.78"            # 60% + surcharge 25% + cess 4% (60 × 1.25 × 1.04)
    basis: "s. 115BBE: 60% + SC 25% + cess 4% = 78%"
    source: "Income-tax Act, 1961, s. 115BBE; surcharge and cess per the Finance Act for the AY"
    verified: false
```

---

## §8 Processing pipeline (stage by stage)

Every stage returns `StageResult(stage, status: "ok"|"warn"|"failed", message, duration_ms)`. The pipeline continues after a `warn`. A `failed` stage stops the dependent stages and shows a friendly error with a "Download diagnostic log" button.

### §8.1 Ingest
- Open with PyMuPDF and validate (§5).
- Use `page.get_text("text", sort=True)` per page.
- If a page yields < 50 characters and Tesseract is available: render at 300 dpi with `page.get_pixmap(dpi=300)` and OCR with `lang="eng+hin"`. Record the mean word confidence.

### §8.2 Segment
- Strip repeating headers and footers: lines that appear on ≥ 60% of pages within the top or bottom 3 lines, plus page-number lines.
- Para detection: a line starting with a para number (`^\s*(\d{1,3}(\.\d{1,2}){0,2})[.)]?\s+`, `^\(?[a-z]\)`, `^\(?[ivx]+\)`, `^Para\s+\d+`). Join wrapped lines until the next para start.
- Unnumbered paras are split on blank lines. Long blocks (> 1,200 characters) are split at sentence boundaries; the sub-paras keep the same `para_no`.
- Sentences: a regex splitter that is aware of abbreviations (`u/s.`, `Rs.`, `No.`, `vs.`, `i.e.`, `viz.`, `M/s.`, `Ltd.`, `Pvt.`, `w.e.f.`, `r.w.s.`).

### §8.3 Classify
1. **Rule score:** a keyword and section dictionary per family, from the first 2 pages plus the last page. Examples: "under section 250", "Commissioner of Income-tax (Appeals)", "Joint Commissioner (Appeals)", "NFAC"; "section 263", "erroneous", "prejudicial"; "12AB", "80G(5)", "registration"; "144C(13)", "Dispute Resolution Panel"; "143(3)", "assessment order", "computation of income". Each cue has a weight in `patterns.yaml`; a family's rule score = sum of the weights of the cues found ÷ the family's total cue weight, capped at 1.
2. **ML score:** a TF-IDF (word 1–2 grams) + LogisticRegression classifier trained by `scripts/train_classifier.py` on the synthetic corpus (augmented by paraphrase templates). Saved to `models/classifier.joblib`.
3. Final score = 0.6 × rule + 0.4 × ML. If the top score is < 0.55 → `UNKNOWN`, and the UI asks the user to choose. If the main order is `ASSESSMENT_AO`, processing is blocked (§5).
4. Act detection: the `act_2025_markers` in `patterns.yaml` ("Income-tax Act, 2025" in the title or operative part, the 2025-Act section style, "tax year" in place of "assessment year") → `IT_ACT_2025`; explicit 1961-Act markers → `IT_ACT_1961`; neither or both → `UNKNOWN` (the user confirms). The evidence snippet is stored on `ClassificationResult.act_evidence`. If 2025 (or UNKNOWN) is detected, show a **prominent red banner on every step and on the report cover**: "Income-tax Act, 2025 order — v1 is built for orders governed by the Income-tax Act, 1961. Forum, limitation (s. 362) and fee are from unverified seed rules and must be verified manually."

### §8.4 Extract (Standard engine)

#### §8.4.1 Header
Run the regex patterns over the first 3 pages plus the last 2 pages. Pick the candidate nearest to its label ("DIN", "PAN", "A.Y.", "Assessment Year", "Date of Order", "Appeal No."). Assessed and returned income: amounts near "assessed income", "total income", "returned income".

#### §8.4.2 Issue blocks
- **CIT(A):** detect ground headings ("Ground No. 1", "Grounds 2 to 4", "Ground of appeal No."), decision headings ("Decision", "Findings", "I have considered"), and section mentions. Each block runs from one ground heading to the next.
- **AO order:** headings like "Addition on account of", "Disallowance u/s", "Issue No.", and the computation table at the end ("Add:" lines), from which the amounts are taken.
- **263:** points listed as "the following issues", "(i)…(ii)…" in the show-cause notice part, plus "directions".
- **CIT(E):** reasons for rejection, as a numbered list after "reasons" or "deficiencies".

#### §8.4.3 Sentence roles
Cue phrase rules, with a TF-IDF + LogisticRegression model as the tie-breaker:

| Role | Cue phrases (examples) |
|---|---|
| AO_CONTENTION | "the AO observed", "Assessing Officer held", "AO noted", "in the assessment order" |
| ASSESSEE_SUBMISSION | "the appellant submitted", "it was contended", "AR of the appellant", "written submissions" |
| APPELLATE_FINDING | "I have considered", "I find", "in my considered view", "accordingly", "therefore", "is deleted", "is confirmed", "is directed" |
| FACT | default |

For each role, pick the top-3 sentences by TextRank within the block (TF-IDF cosine graph, power iteration, damping 0.85). Store each as `Evidence`.

The tie-breaker model is trained by `scripts/train_classifier.py` on cue-labelled synthetic sentences and saved to `models/roles.joblib`. If the model file is missing, cue phrases alone decide and the default is FACT.

#### §8.4.4 Outcome detection (operative sentences — last 30% of the block weighted ×2)

| Outcome | Cue phrases |
|---|---|
| ALLOWED | "ground is allowed", "addition is deleted", "AO is directed to delete", "stands deleted" |
| PARTLY_ALLOWED | "partly allowed", "restricted to", "sustained to the extent", "allowed in part" |
| DISMISSED | "ground is dismissed", "addition is confirmed", "upheld", "sustained", "no infirmity" |
| RESTORED_TO_AO | "restored to the file of the AO", "remanded", "set aside to the AO", "for fresh adjudication" |
| NOT_ADJUDICATED | "not pressed", "general in nature", "consequential", "premature" → (sub-types noted) |
| INFRUCTUOUS | "infructuous", "academic" |

Conflicting cues → the one in the last operative sentence wins; confidence × 0.7.

#### §8.4.5 Amounts
Parse ₹ / Rs. amounts, lakh and crore words, and "/-". Relief and sustained amounts follow the table in §6.3 (ALLOWED → relief = amount_ao; PARTLY_ALLOWED → "restricted to X" gives sustained = X, relief = ao − X; DISMISSED / NOT_ADJUDICATED → sustained = amount_ao). If unknown, leave `None` and set the status to `LOW_CONFIDENCE`.

### §8.5 Link (AO order ↔ appellate order)
For each appellate issue, find the best AO issue using:
- section equality (weight 0.5);
- RapidFuzz `token_set_ratio` on the titles (0.3);
- amount equality within ±1% (0.2).

A match is accepted if its score is ≥ 0.6; assignment is one-to-one, greedy on the highest score. The result sets `ao_evidence_link` and `amount_ao` (if missing). Unmatched AO additions are stored in `CaseFile.unmatched_ao` and shown as "Addition not found in appellate order — check whether a ground was raised". This is a valuable check. Appellate issues with `nature = LEGAL_JURISDICTIONAL` (or with no amount) have no AO counterpart: they stay unlinked and are **not** flagged. Example: S1 + S2 give 3 linked issues plus 1 unlinked legal ground.

### §8.6 Verify
For every `Evidence`:
- normalise both strings (lowercase, collapse whitespace, strip punctuation, convert Devanagari digits);
- take `rapidfuzz.fuzz.partial_ratio` against the stated para, then the ±2 neighbouring paras, then the whole page.

| Best score | Result |
|---|---|
| ≥ 90 | `verified = True` |
| 75–89 | `verified = True`, `LOW_CONFIDENCE` |
| < 75 | `UNVERIFIED` |

If the snippet is found on a different page or para, correct the reference and log it. The verification log lists everything that is not OK.

### §8.7 Rules
- Compute the limitation (§7.1, using the block for the detected Act and the method for the date of service), fee (§7.2) and validity flags (§7.4).
- RAG on days_remaining: EXPIRED (< 0), RED (≤ 7), AMBER (8–21), GREEN (> 21). Thresholds are configurable in settings.
- Every function that depends on the current date takes a `today: date` parameter (the UI passes the system date), so results are reproducible in tests.

### §8.8 Tax effect
- Rate **per issue** (CR-004), as a `Decimal`: if the issue's `section` is listed in a `special_rates` entry (§7.8; s. 115BBE for 68, 69, 69A, 69B, 69C, 69D), that entry's rate applies; otherwise the selected preset or custom rate. Each `TaxEffectLine` records the `rate` and `rate_basis` used, and both are shown per issue in the Tax Effect tab, the report (§11.2 item 6) and the register (`TaxEffect` sheet). If the issue's section is unknown, the selected rate applies and the verification log notes it.
- **Department side:** for each issue with relief > 0, `tax_effect = round(relief × issue rate)` (ROUND_HALF_UP to the rupee). Sum per AY (v1 handles one AY per matter) → `dept_total`.
- **Assessee side:** for each issue with sustained > 0, likewise → `assessee_total`.
- **Penalty matters** (issues with `nature = PENALTY`): the penalty amount in dispute is taken directly.
- Department appeal likelihood — computed **only for `CITA_250`** (including JCIT(A) orders). For `REVISION_263`, `CITE_12AB_80G` and `DRP_FINAL_144C13` the likelihood is `NOT_APPLICABLE` and the UI and report show "Not applicable" (the Department does not appeal these orders to the ITAT):

| Condition | Likelihood |
|---|---|
| dept_total < 0.8 × limit, and no exception flag | UNLIKELY |
| 0.8 × limit ≤ dept_total < limit | POSSIBLE |
| ≥ limit, or an exception flag | LIKELY |

- Exception flags (keyword hints, for review only): "search u/s 132", "survey u/s 133A", "s. 132", "organised tax evasion", "audit objection", "constitutional validity", "black money". Match whole words / phrases (case-insensitive) and store each flag with its evidence snippet. The reviewer can clear a flag in the Tax Effect tab (marked `USER_EDITED`), which recomputes the likelihood.
- Always display: "Monetary limits are a CBDT instruction to the Department; the Department may still appeal in excepted cases. Verify."

### §8.9 Decide (decision matrix)
Rules in priority order:

| # | Condition | Recommendation | Priority |
|---|---|---|---|
| 0 | family ∈ {REVISION_263, CITE_12AB_80G} | APPEAL the whole order, with a legal ground on jurisdiction / grounds of rejection | HIGH |
| 1 | nature = LEGAL_JURISDICTIONAL and outcome ∈ {DISMISSED, NOT_ADJUDICATED} | APPEAL | HIGH |
| 2 | outcome = DISMISSED and sustained tax effect ≥ materiality (settings, default ₹50,000) | APPEAL | HIGH |
| 3 | outcome = DISMISSED and below materiality | EVALUATE ("low tax effect — weigh cost and precedent value") | LOW |
| 4 | outcome = PARTLY_ALLOWED | APPEAL_BALANCE | MEDIUM |
| 5 | outcome = NOT_ADJUDICATED | APPEAL ("seek adjudication / restoration") | HIGH |
| 6 | outcome = RESTORED_TO_AO | PURSUE_SET_ASIDE ("appeal only if the directions are adverse") | MEDIUM |
| 7 | outcome = ALLOWED and Department's appeal received | CROSS_OBJECT | HIGH |
| 8 | outcome = ALLOWED and likelihood ≠ UNLIKELY | MONITOR (+ prepare cross-objections) | MEDIUM |
| 9 | outcome = ALLOWED and UNLIKELY | ACCEPT ("monitor"; no action) | LOW |
| 10 | outcome = INFRUCTUOUS / UNKNOWN | EVALUATE | MEDIUM |

**Ex parte orders (CR-005.2):** when the EX_PARTE flag is raised, every adverse issue (DISMISSED, PARTLY_ALLOWED, NOT_ADJUDICATED) is APPEAL, with priority HIGH if its tax effect ≥ materiality, LOW if below, MEDIUM if not computable; the rationale ends "Included as the whole order is sought to be restored for fresh adjudication."

Rules 7–9 apply only to `CITA_250`. For `DRP_FINAL_144C13`, each addition in the final order is treated as `DISMISSED` (§6.3), so rules 1–3 apply. Where rules 7–9 do not apply, an ALLOWED issue falls through to EVALUATE with the rationale "Department appeal — not applicable for this order type".

The rationale is a templated sentence. In Local / Cloud mode, the engine may add an optional "Strategy note" (≤ 80 words, clearly labelled AI-generated, with no citations).

### §8.10 Draft grounds (deterministic template + optional AI polish)
Template per issue with recommendation ∈ {APPEAL, APPEAL_BALANCE}:

```
{n}. On the facts and in the circumstances of the case and in law, the learned {authority} erred in
     {confirming/sustaining} the {addition/disallowance} of ₹{amount} made by the learned AO u/s {section}
     on account of {title}.
```

Legal ground template: "…erred in upholding the {assumption of jurisdiction / reopening / order} which is bad in law and void ab initio."

Always end with: "The appellant craves leave to add, alter, amend or withdraw any ground of appeal at or before the time of hearing."

The grounds must be concise and under distinct heads, without argument or narrative (Rule 8, ITAT Rules, 1963). The AI may only rephrase titles. It must keep the amount, section and authority unchanged; validate this by regex after AI output, and if validation fails, use the template.

### §8.11 Paper book index
Fixed skeleton plus entries detected from the orders ("submissions dated", "copy of", "confirmation", "ledger", "bank statement", "remand report", "affidavit"):

| S. No. | Particulars | Filed before (AO / CIT(A) / New – Rule 29 application) | Pages |

Default rows:
1. Copy of ITR and computation
2. Audited financial statements
3. Submissions before the AO
4. Submissions before the CIT(A)
5. Remand report and rejoinder (if Rule 46A)
6. Evidence for each issue

Any new evidence must be shown under a separate heading, "Additional evidence — application under Rule 29 of ITAT Rules (verify)".

E-filing guidance (from 01-10-2026, `verified: false`, see §7.5): the paper book is prepared as indexed, paginated PDF(s) and uploaded on the ITAT e-filing portal with a digital signature. The index output carries this note, and the Pages column refers to the PDF page numbers.

---

## §9 Engines

### §9.1 Protocol

```python
class Engine(Protocol):
    name: str
    def available(self) -> tuple[bool, str]: ...
    def classify(self, doc: Document) -> ClassificationResult: ...
    def extract_header(self, doc: Document, family: OrderFamily) -> OrderHeader: ...
    def extract_issues(self, doc: Document, family: OrderFamily) -> list[Issue]: ...
    def strategy_note(self, issue: Issue, family: OrderFamily) -> str | None: ...
```

`StandardEngine` implements everything. The LLM engines implement `extract_issues` (+ `strategy_note`) and **delegate the header, regex and amount parsing to Standard**, then merge, so the deterministic fields always win.

### §9.2 LM Studio adapter
- Base URL from settings, default `http://localhost:1234/v1`. Check `GET /models` (timeout 3 s). The UI shows the loaded model name.
- `POST /chat/completions` with `response_format: {"type":"json_schema","json_schema":{...}}`, generated from the pydantic model. Settings: `temperature: 0.1`, `max_tokens` from settings.
- Chunking: one issue block per call. If a block exceeds 6,000 tokens (≈ 4 characters per token estimate), split by paragraph with a 1-para overlap and merge the results.
- Validate with pydantic. On failure, retry once with the error message appended. On a second failure → Standard for that issue, and record the fallback.
- Timeouts: 120 s per call (configurable). Cancel-safe.
- Recommend these models in the README: an instruction-tuned model of 3–8B parameters (e.g., Qwen 2.5 7B Instruct, Llama 3.1 8B Instruct, Gemma 3 4B) in a Q4 quantisation for 8–16 GB RAM laptops.

### §9.3 Claude adapter (optional)
- Lazy import of `anthropic`. API key from `.env` or the settings field (stored locally; masked in the UI).
- Default model `claude-sonnet-5-5`, configurable. Use tool use / structured output with the same JSON schema.
- A confidentiality warning modal must be accepted for each matter. Log the "Cloud mode used" flag in the CaseFile and print it on the report.

### §9.4 Prompt templates (`engines/prompts/*.md`)
Each template contains:
- role ("You are assisting a Chartered Accountant reviewing an Indian income-tax appellate order");
- strict rules: use only the given text; quote verbatim in `source_snippet`; give page and para exactly as given in the input markers; output "Not found" rather than guessing; never compute dates or tax; never cite judgments; follow the JSON schema;
- the input format, in which each para is prefixed with `[p{page} ¶{para_no}]`;
- one short synthetic few-shot example.

---

## §10 UI specification (professional advisory-firm style)

### §10.1 Design system (`ui/theme.py` + `.streamlit/config.toml`)

| Token | Value | Use |
|---|---|---|
| `--primary` | `#0B2545` (deep navy) | Header bar, primary buttons, table headers |
| `--accent` | `#13807A` (teal) | Active step, links, focus ring |
| `--ink` | `#1F2933` | Body text |
| `--muted` | `#616E7C` | Secondary text |
| `--bg` | `#F5F7FA` | App background |
| `--surface` | `#FFFFFF` | Cards |
| `--border` | `#E4E7EB` | Card and table borders |
| `--red` / `--amber` / `--green` | `#B42318` / `#B54708` / `#027A48` | RAG badges (with light tints `#FEF3F2` / `#FFFAEB` / `#ECFDF3`) |

- **Typography:** system font stack only (offline): `"Segoe UI", -apple-system, "Helvetica Neue", Arial, sans-serif`. Base 14 px; H1 24/600; H2 18/600; table 13 px. Numbers right-aligned with tabular figures.
- **Layout:** wide mode; max content width 1280 px; 8 px spacing grid; cards with 8 px radius and a subtle shadow; no emojis in the UI. Use small inline SVG icons (stored locally) or none.
- Hide the Streamlit default menu, footer and "Deploy" button via CSS. Custom top bar: app name "AppealIQ", a subtitle "ITAT Appeal Readiness Analyser", the firm name on the right, and an engine status pill (Standard / Local: {model} / Cloud).

### §10.2 Navigation (sidebar, in this order)
Home · New Analysis · Case Register · Settings · Help & About

The sidebar is drawn by `ui/nav.py`, and Streamlit's own page list is hidden (CR-008.3). It has the AppealIQ wordmark and version at the top and a badge at the bottom: "Offline · Data stays on this computer", or "Cloud mode on" when the cloud engine is used for the current matter. Home is the root URL ("/"); "/home" opens Home as an alias.

### §10.3 Screens

- **Home:**
  - 4 KPI cards: Open matters · Due ≤ 7 days (red) · Due 8–21 days (amber) · Analyses this month;
  - a table "Upcoming deadlines" (Matter, Client, AY, Order, Form 36 due, Days left with a RAG badge, Status);
  - a primary button "Start new analysis".
- **New Analysis:** a horizontal **stepper** (1 Upload & Details → 2 Processing → 3 Review → 4 Approve & Download). Disabled steps are greyed out.
  - **Step 1:**
    - two-column form;
    - drag-and-drop zones labelled "Order appealed against (required)" and "Assessment order of AO (optional — enables issue trail)";
    - up to three optional supporting documents, each with a type: Form 35 / grounds of appeal, statement of facts, submissions before the AO, submissions before the CIT(A), other (CR-009 C). Form 35 grounds are used when the order lists none; submissions supply "Assessee's submission" extracts with [Sub p.x ¶y] references; every supporting document is listed in the paper book index;
    - date of service picker, with the helper text "Limitation runs from the date of service, not the date of the order";
    - Department's appeal received toggle (+ date);
    - tax rate selector: Category → Regime / section → Income band (§7.8);
    - engine selector, with an availability check.
  - **Step 2:**
    - a stage list with status icons (pending / running / done / warning / failed) and durations;
    - an overall progress bar;
    - an expandable "Processing log";
    - a "Cancel" button. The pipeline runs in a worker thread with a cancel `threading.Event`, checked between stages; the page polls its progress with `st.fragment(run_every=…)`, so the UI never freezes.
    - When finished, auto-advance after a summary card ("4 issues · 41/43 extracts verified · Form 36 due 31-12-2026 (61 days)") — only if no stage warned or failed. Otherwise each warned / failed stage shows a plain-English corrective action ("Install Tesseract…", "Upload a text PDF…", "Add the AO order to enable the issue trail") and a "Retry this step" button; retry runs processing again with the same inputs (CR-009 C).
  - On every step, if the Act is `IT_ACT_2025` or `UNKNOWN`, the red banner from §8.3 is shown above the stepper.
  - **Step 3:** a top summary strip (Order, AY, Authority, DIN, Service date, Due date + RAG — or "Filed on" and the next hearing once filed —, Engine), a "Reprocess case" button (reads the saved uploads again; keeps case notes, reviewer comments, hearings and issues added by the reviewer; asks before discarding outcome edits), then 9 tabs:
    1. *Order Details* — editable key–value grid; the status chip per field (OK / Low confidence / Unverified / Not found / Edited).
    2. *Issue Trail* — a wrapping table (CR-008.1): Issue · Ground · Title · Section · AO amount · Outcome · Relief · Sustained · Refs (appellate page and para, then the AO's) · Status. There is no truncation and no horizontal scroll at 1366 px. One panel per issue holds the edits (title, section, outcome, AO amount, amount sustained), the verbatim extracts with references, and the AI summary if any (labelled). The open tab and the open issue panel stay open after an edit or an AI note.
    3. *Tax Effect* — a rate selector; the issue-wise table for both sides, with the rate and rate basis used for each issue (s. 115BBE issues marked); a callout for the Department appeal likelihood (badge, or "Not applicable" outside `CITA_250`) with the circular reference and disclaimer; exception flags with their evidence and a "Clear" control.
    4. *Decision Matrix* — Issue · Recommendation (select, overridable) · Priority · Rationale; an Action Plan table below it.
    5. *Grounds & Paper Book* — editable text area for the grounds (numbered) and an editable index table.
    6. *Case Notes* (CR-009 C) — points, pending points (with a done tick), remarks, arguments and case laws (free text with case name, citation, court and proposition). Internal: exported to the Excel issue register (sheet "CaseNotes") and to the report only as an optional internal annexure (off by default). Each issue panel also has "Reviewer comments" (same treatment).
    7. *Case Laws in Orders* (CR-009 C) — citations found in the AO order, the appellate order and uploaded submissions ("v." / "vs"; ITR / Taxmann / SOT / TTJ / ITD / DTR / CTR / SCC; (year) volume page; SC / HC / ITAT bench in brackets or in the sentence): case name, citation, court, relied on by (AO / CIT(A) / assessee, from the document and the para's roles), document / page / para, and the document's own sentence(s) as the brief. No AI summaries; patterns in `patterns.yaml` (`case_law`).
    8. *Hearings* (CR-009 B).
    9. *Verification Log* — filterable list; the count shows as a badge on the tab title.

    Issues added by the reviewer ("Add issue manually") carry `origin = USER_ADDED` and are included in the tax effect, decisions, grounds and report.

    Any edit marks the field `USER_EDITED` and re-runs §8.7–§8.9 instantly.
  - **Step 4:**
    - a checklist (all UNVERIFIED items resolved or acknowledged; reviewer name; approval checkbox);
    - "Include case notes and reviewer comments in the report as an internal annexure (not for the client)" — off by default;
    - output cards (Report DOCX, Report PDF, Grounds DOCX, Paper Book Index DOCX, Issue Register XLSX), each with a download button;
    - a "Save to Register" action (automatic on generation).
- **Case Register:** a searchable and filterable table with RAG; clicking a case ID opens the case in Review (also from the Home tables); edit (client, AY, status, date of filing, ITA No.) and delete any case, with a confirmation that offers "Delete record only" or "Delete record and files"; read-only view of the last CaseFile JSON plus re-download; export to Excel. Statuses: Analysis open · Appeal filed · Cross-objection filed · Pending for hearing · Heard – order awaited · Decided – in favour · Decided – partly allowed · Decided – against · Restored / set aside · Closed (the old "Open" reads as "Analysis open"). From "Appeal filed" to "Restored / set aside" the date of filing is required, the days-left / expired badge is hidden and the next hearing date is shown instead; a "Next hearing" column comes from the case's hearing log (Hearings tab: date, bench, purpose, outcome adjourned / part-heard / heard, next date, remarks). Home adds the KPI "Hearings in next 7 days" and an "Upcoming hearings" table (CR-009 Session B).
- **Settings:**
  - firm name, address line, logo upload, report colour (preset: Navy);
  - reviewer list;
  - RAG thresholds and materiality;
  - LM Studio URL, timeout, max tokens; "Test connection";
  - Cloud: API key (masked), model, "Test connection";
  - "Advanced (administrator)", collapsed (CR-009 C): the health check and the knowledge base (rules file versions, `verified: false` entries).
- **Help & About:** how it works (6 steps), engines explained, a data-privacy statement, the disclaimer and a version number.

### §10.4 UX rules
- Every long action shows a spinner with the stage name. No frozen screens.
- Errors appear as a red callout with plain-English text and a suggested fix. The technical detail goes in an expander.
- Use the Indian number format everywhere; dates DD-MM-YYYY; amounts right-aligned.
- Keyboard and tab order is sensible; contrast is at least WCAG AA.
- State survives the step navigation (`st.session_state`), and the CaseFile is autosaved to `data/matters/{matter_id}/casefile.json` after each step (`matter_id` sanitised per §5).

---

## §11 Outputs

### §11.1 Common styling (`outputs/styles.py`)

- **Page and type:** A4, 2 cm margins. Font Calibri (fallback Arial) 10 pt; headings in the primary colour.
- **Header:**
  - left: firm name;
  - right: "Privileged & Confidential — Prepared for professional review".
- **Footer:**
  - left: Matter ID · AY;
  - centre: "Page X of Y" (field codes);
  - right: "Generated by AppealIQ v1.0 on DD-MM-YYYY".
- **Tables:** header row in navy with white bold text, repeated on each page; zebra rows `#F5F7FA`; 0.5 pt borders `#D0D5DD`; amounts right-aligned; RAG cells shaded with the tint colours and bold text.

### §11.2 ITAT Appeal Readiness Report (DOCX → PDF)

0. Cover block: title, client, AY, order appealed against, matter ID, prepared by, reviewed by, date, engine used (+ "Cloud processing used: Yes/No")
1. Executive summary: a 5-row table (Total issues · Adverse · Favourable · Form 36 due + RAG · Department appeal likelihood), plus 3 bullet takeaways (templated)
2. Order details (two-column table)
3. Critical dates and fee (Due date, Days remaining, Cross-objection window, Fee, Notes)
4. Issue trail (main matrix)
5. Issue-wise analysis: per issue, a block with the AO's contention, the assessee's submission, and the appellate finding (verbatim extracts in italic with [p/¶] references), and the AI summary if any (labelled)
6. Tax effect and monetary-limit assessment (both sides, with the rate and rate basis per issue, and the disclaimer)
7. Validity and procedural observations (severity-coloured)
8. Decision matrix
9. Action plan
10. Verification log
11. Annexure: basis of rules applied (YAML versions, `verified` status)
12. Disclaimer

### §11.3 Draft grounds (DOCX)
Title "Grounds of Appeal before the Income Tax Appellate Tribunal", the assessee, AY, and the order appealed against. Numbered grounds, then the "craves leave" ground. Single-spaced, justified. The note "DRAFT — for professional review" appears in the header.

### §11.4 Paper book index (DOCX)
Title block (In the ITAT, ___ Bench; ITA No. ___ ; Assessee v. Revenue; AY). Index table (§8.11). A certification line placeholder.

### §11.5 Issue register (XLSX, openpyxl)
Sheets:
- `Summary` (KPIs);
- `Issues` (all Issue fields flattened);
- `TaxEffect` (one row per line, including the rate and rate basis);
- `Decisions`;
- `Actions`;
- `Verification`.

Formatting:
- frozen header row;
- auto-filter;
- column widths set;
- Indian number format `[>=10000000]##\,##\,##\,##0;[>=100000]##\,##\,##0;##,##0`;
- conditional formatting for RAG and outcome (green ALLOWED, amber PARTLY, red DISMISSED).

### §11.6 PDF conversion
Try docx2pdf (Windows + Word), then `soffice --headless --convert-to pdf`. If both fail, show "PDF conversion unavailable — DOCX provided".

---

## §12 Non-functional requirements

### §12.1 Health check (on start; shown in Settings)
Report the status of each of the following:
- Python version;
- packages importable;
- Tesseract found (path) and languages available;
- `data/` writable;
- rules files valid (and the count of `verified: false` entries);
- classifier model present;
- LM Studio reachable (optional);
- Word / LibreOffice available for PDF.

### §12.2 Performance (8 GB RAM, Core i3)
- Standard mode: ≤ 30 s for a 40-page text PDF.
- OCR: ≤ 6 s per page.
- The UI never blocks without a spinner.

### §12.3 Reliability
- No unhandled exceptions reach the UI.
- Each stage is wrapped.
- CaseFile autosave.
- Logs rotate at 2 MB × 5 files.

### §12.4 Security and privacy
- Bind Streamlit to `127.0.0.1` only (`server.address`).
- `gatherUsageStats=false`.
- No external fonts or CDNs.
- The API key is never logged.
- A test asserts that there are no hard-coded URLs other than localhost / 127.0.0.1 / ::1 and the Anthropic API host. It scans `app.py`, `appealiq/`, `scripts/`, `tests/`, `rules/`, `config/`, `.streamlit/` and the setup/run scripts. `docs/` and `README.md` are not scanned, because they may cite external references such as download pages. OOXML namespaces are built with `docx.oxml.ns.qn`, so no namespace URIs are hard-coded.

### §12.5 Portability
- Paths via `pathlib`.
- Windows batch scripts plus shell scripts.
- No admin rights needed, except for installing Tesseract (optional).

---

## §13 Synthetic samples and testing

### §13.1 `scripts/make_samples.py` (reportlab)
Generates realistic but **fictitious** orders (fictional assessees, PANs like `ABCDE1234F`, a DIN format, NFAC style), all under the Income-tax Act, 1961 and dated so that the date of service falls on or after 01-10-2024. Each has an expected JSON in `samples/expected/`, validated by an `ExpectedSample` model built from §6 types (header values; per issue the section, nature, amounts, outcome and para refs). Golden tests compare at field level and do not compare confidence values or exact snippets.

| Sample | Content |
|---|---|
| S1 AO order AY 2022-23 | 3 additions: s. 68 ₹45,00,000; s. 14A ₹8,00,000; s. 40(a)(ia) ₹12,00,000; computation table (normal income at 25.168%, s. 68 addition u/s 115BBE at 78%, illustrative interest u/s 234B) |
| S2 CIT(A) order (same assessee) | Ground 1 legal (reopening validity) dismissed; s. 68 deleted; s. 14A confirmed; s. 40(a)(ia) restricted to ₹4,00,000; DIN present |
| S3 CIT(A) order, ex parte | 2 grounds dismissed for non-prosecution; DIN missing |
| S4 s. 263 order | PCIT; twin conditions recorded; original order date given; directions to the AO |
| S5 CIT(E) 12AB rejection | 3 reasons for rejection |
| S6 S2 as a scanned image PDF | Rasterised, for the OCR test |

### §13.2 Tests (pytest)

| Area | Examples |
|---|---|
| rules_engine | Due date by method: service 20-10-2026 → 31-12-2026; 15-12-2026 → 28-02-2027 (Sunday note, not shifted); 30-09-2024 → 29-11-2024 (60 days); switch-over at 01-10-2024; RAG thresholds with injected `today`; cross-objection date; fee slabs at boundaries (₹1,00,000; ₹1,00,001; ₹2,00,000; ₹10,00,000 → ₹10,000 cap); stay fee; 2025-Act block selected and flagged unverified |
| tax_effect | S2 (CR-004, preset 25.168%) → Department: s. 68 relief ₹45,00,000 × 78% (s. 115BBE) = ₹35,10,000 + s. 40(a)(ia) relief ₹8,00,000 × 25.168% = ₹2,01,344 → ₹37,11,344 → UNLIKELY (61.9% of the ₹60 lakh limit); assessee: ₹12,00,000 (s. 14A ₹8,00,000 + s. 40(a)(ia) ₹4,00,000) × 25.168% = ₹3,02,016; per-issue rate selection for each 115BBE section and a non-listed section; `rate_basis` recorded per line; boundary at 0.8 × and 1.0 × limit; NOT_APPLICABLE outside CITA_250; exception phrase matching |
| decide | Each row of §8.9, including rule 0, DRP additions as DISMISSED, and rules 7–9 skipped outside CITA_250 |
| verify | Exact, near and fabricated snippets; reference correction |
| segment | Para numbering variants; header/footer stripping |
| classify | All 6 samples classified correctly |
| extract (golden) | S1–S5 vs. the expected JSON; field-level precision/recall thresholds: header ≥ 95%, issues ≥ 90%, outcomes ≥ 90% |
| engines | LM Studio adapter with a mocked HTTP server: valid JSON, invalid → retry → fallback, timeout |
| outputs | Files created, open with python-docx / openpyxl, contain the expected headings and row counts |
| security | No disallowed URLs in the source; Streamlit config binds to localhost; only `ui/` imports Streamlit |
| link | S1 + S2 → 3 linked issues + 1 unlinked legal ground (not flagged) |

Dev-only: Playwright (headless Chromium) takes the README screenshots in `docs/screenshots/`. It is not a runtime dependency.

### §13.3 `scripts/evaluate.py`
Runs all samples through the Standard engine (and LM Studio if available). Writes `docs/EVALUATION.md`:
- field accuracy table;
- verification rate;
- time per document;
- manual baseline (user-entered) vs. tool time.

---

## §14 Packaging and ICAI submission

- `setup.bat`:
  - check Python 3.12 (`py -3.12`); if it is missing, fall back to the newest installed Python ≥ 3.12 with a warning;
  - create `.venv`;
  - `pip install -r requirements.txt`;
  - check Tesseract (print guidance if missing);
  - run `scripts/make_samples.py` and `scripts/train_classifier.py` if the models are missing;
  - (Phase 10) create a Windows desktop shortcut **"AppealIQ"** with a custom icon (`assets/appealiq.ico`). It starts the app silently (no console window) and opens it in Microsoft Edge app mode (`msedge --app=http://127.0.0.1:8501`), so it looks like a standalone desktop application. If Edge is not found, fall back to the default browser.
- `run.bat`: activate the venv; `streamlit run app.py --server.address 127.0.0.1`; open the browser.
- `requirements-dev.txt` includes Playwright for README screenshots (dev only).
- `README.md` sections:
  1. Problem statement
  2. Solution
  3. Key features
  4. Architecture diagram (Mermaid)
  5. Three engines and privacy
  6. Installation (Windows, step by step, with screenshots)
  7. Using the app (6 steps)
  8. Sample walkthrough (S2)
  9. Evaluation results
  10. Controls and limitations
  11. Future scope
  12. Course modules applied (AICA L2: offline LLMs / LM Studio, computer vision / OCR, Python, AI-assisted development, optional MCP)
  13. Disclaimer
  14. Author, batch, video link
- Submission folder name: `AICA-L2-Batch-(XXX)-Name-Surname` (replace the placeholders).
- `docs/PROMPT_LOG.md`: the prompts used, iterations and lessons, from this build.
- Demo video script (in `docs/DEMO_SCRIPT.md`, 5–7 minutes):
  1. Face intro
  2. Problem
  3. Live run on S1+S2
  4. Review tabs
  5. Outputs
  6. Offline / LM Studio switch
  7. Controls
  8. Close

---

## §15 Disclaimer text (use verbatim in the app and the report)

"AppealIQ is a decision-support tool. Its outputs are drafts for review by a qualified professional. They do not constitute legal or tax advice. Statutory provisions, limitation periods, fees and CBDT instructions applied by the tool are configurable and must be verified against the current law before reliance. All sample data in this repository is fictitious."
