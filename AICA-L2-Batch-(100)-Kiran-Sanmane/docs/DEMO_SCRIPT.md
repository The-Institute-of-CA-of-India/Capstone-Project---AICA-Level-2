# AppealIQ — Demo Video Script (6–7 minutes)

Presenter: CA Kiran Sanmane. Data: fictitious samples S2 (CIT(A) order) and S1 (AO order) only — never a client file on screen.

## Before recording

- [ ] Run `setup.bat` once; the **AppealIQ** icon is on the desktop.
- [ ] Settings: firm name "K. B. Sanmane & Co.", reviewer "CA Kiran Sanmane".
- [ ] Delete any earlier demo case (Case Register → Delete → record and files), so the run is fresh. Use case ID **DEMO-2022-23**.
- [ ] LM Studio running with `gemma-3-12b-it` loaded (Settings → Local AI → Test connection = green). A note takes 60–100 s: start it early (see 6) or cut the wait in editing.
- [ ] Screen 1366 × 768 or 1920 × 1080, notifications off, Wi-Fi **off** (to show it works offline; LM Studio is local).
- [ ] Have `samples\S2_CITA_order_AY2022-23.pdf` and `samples\S1_assessment_order_AY2022-23.pdf` in an open Explorer window.

## Script

| Time | Section | On screen | Say (key lines) |
|---|---|---|---|
| **0:00–1:00** | **1. Face intro and problem** | Camera on presenter; then the Home screen title card | "I'm CA Kiran Sanmane of K. B. Sanmane & Co., AICA Level 2, Batch 100, Pune. When a CIT(A) order comes in, we have two months from the end of the month of service to decide what goes to the ITAT. That means tracing every addition from the AO's order to the CIT(A)'s finding, working out the tax effect on both sides, checking whether the Department can even appeal under the CBDT monetary limit, drafting grounds and building the paper book — by hand, across a hundred pages. Things get missed. AppealIQ does the first draft of all of this, offline, and I review it." |
| **1:00–3:00** | **2. Live run S2 + S1 from the desktop icon** | Double-click the desktop icon → app window opens → New Analysis | "It runs on this laptop like a desktop app — no internet." **Step 1:** drop S2 as the order appealed against, S1 as the AO's order. Case ID DEMO-2022-23, client "Kalpanik Traders Pvt. Ltd." (fictitious), date of service **20-10-2026**, rate: Company → s. 115BAA. Point at the limitation helper: "Form 36 due 31-12-2026." Engine: Standard. Click **Process**. **Step 2:** "Each stage — reading, OCR if needed, classification, extraction, linking, verification, rules — with its time. Under a second." Summary card: "4 issues, every extract verified, Form 36 due 31-12-2026." |
| **3:00–4:30** | **3. Review tabs** | Issue Trail → Tax Effect → Decision Matrix → Case Laws in Orders | **Issue Trail:** "Ground 1, reopening, dismissed; s. 68, ₹45 lakh, deleted; s. 14A, ₹8 lakh, confirmed; s. 40(a)(ia) restricted to ₹4 lakh. Every line has its page and para — open one: the extract is verbatim from the order." **Tax Effect:** "Our side ₹3,02,016. The Revenue's side ₹37,11,344 — the s. 68 relief is taxed at 78% u/s 115BBE — that is 62% of the ₹60 lakh ITAT limit, so a Department appeal is unlikely." **Edit:** change s. 14A to *Allowed* in its panel → "Watch: our tax effect drops to ₹1,00,672, the Revenue's rises to ₹39,12,688, and the decision changes to Accept — recomputed by rules, not by AI." Change it back. **Decision Matrix:** "Appeal on the legal ground and s. 14A, appeal the balance of s. 40(a)(ia), accept s. 68 — each with a reason and priority I can override." **Case Laws in Orders:** "Judgments cited in the orders, quoted with page and para. AppealIQ never writes or suggests case law." |
| **4:30–5:30** | **4. Outputs** | Step 4 → tick approval, enter reviewer → five output cards → open the report, then the grounds, then the Excel register | "Nothing is generated until a named reviewer approves." Open the **report**: executive summary, issue trail, tax effect, decision matrix, action plan with dates, paper book index, verification log, provisions applied, disclaimer. Open **Draft Grounds**: "Legal ground first, exact amounts and sections." Open the **Issue Register** (Excel): "Filterable, with every reference." |
| **5:30–6:00** | **5. Case Register with a hearing date** | Case Register → click DEMO-2022-23 → Hearings tab | Set status *Appeal filed*, date of filing, ITA No. "999/PUN/2026"; add a hearing on a date next week. Back to Home: "Hearings in next 7 days: 1 — the register is the firm's appeal diary." |
| **6:00–6:30** | **6. Local AI note and offline badge** | Sidebar badge "Offline · Data stays on this computer"; Issue Trail → s. 14A → *Generate AI note* (pre-generated, or cut the wait) | "This note comes from a model running on this laptop through LM Studio — the order never leaves the machine. It is labelled AI-generated, it is advisory, and it can't change an outcome, an amount or a date." |
| **6:30–7:00** | **7. Honest limitation and close** | README → Known limitations; then camera | "To be clear about where it stands: the accuracy scores are on synthetic orders. On one real redacted NFAC order, automatic issue detection did not work — that is open as DF-001. The workaround is in the app: add the issues manually or upload Form 35, and everything downstream still works. The next step is a layout library built from masked diagnostics. AppealIQ is a decision-support tool — the professional judgement stays with us. Thank you." |

## Backup lines (if something goes wrong)

- LM Studio not responding: "If the local model is off, the app says so and the Standard analysis is unaffected." Show the notice and move on.
- PDF conversion unavailable: "Without Word or LibreOffice, it gives the DOCX and says so."
