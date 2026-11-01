# Prompts Used – Vendor Registration & Validation App

**AICA Level-2 Capstone Project**
Prompts are grouped in the order the project was built. Part A covers the prompts used to design and generate the code and outputs. Part B covers the prompts the app itself sends to the AI at run time.

---

## PART A – Prompts used to BUILD the project

### A1. Project ideation

> I am a Chartered Accountant practising in Income Tax, GST and Companies Act, with some management consultancy clients. I am interested in Python and Excel macros. Suggest a capstone project area for the AICA Level-2 course. Look at projects already submitted on GitHub (aiinicai/AICA-Level-2-Projects) so that my idea is different.

### A2. Feasibility check

> I want to build a vendor registration and validation app. It takes vendor data in Excel, checks whether the PAN and GSTIN are valid, and gives the MSME major activity, enterprise type and classification date. Check feasibility and give your opinion.

### A3. Master build prompt (functional specification)

> Build a Windows desktop app in Python for vendor registration and validation.
> 1. **Input:** an Excel file with Sr No, Vendor Code, Vendor Name (as per PAN), Constitution, Authorised Person, Email ID, Address, State, PAN, GSTIN, Udyam No.
> 2. **Offline validation first**, for all three registrations:
>    - PAN: structure, holder type (4th character), name initial (5th character), and constitution vs PAN.
>    - GSTIN: length, structure, state code, 14th character, mod-36 check digit, and PAN embedded in the GSTIN.
>    - Udyam: format UDYAM-XX-00-0000000, state code, the old Udyog Aadhaar number, and a state mismatch with the GSTIN.
>    - Duplicates in the vendor master.
> 3. **Then online validation, one department at a time** (PAN → GST → Udyam), vendor by vendor, on the official portals. Open a visible browser, prefill the number, and let the user type the captcha / OTP. Read the result automatically and move to the next vendor. Captcha must never be bypassed.
> 4. **Fetch:**
>    - GST: legal name, trade name, status, registration date, cancellation date, constitution.
>    - Udyam: enterprise name, major activity, organisation type, enterprise type with classification year and classification date, and NIC codes.
>    - PAN: status and name/DOB match.
> 5. **Decide Sec. 43B(h) / Sec. 37(2)(g) (IT Act 2025) applicability.** Micro/Small = Yes; Medium = No; trading NIC codes 45/46/47 = Review.
> 6. **Output:** a colour-coded Excel report in medium-light colours. Highlight the failed field itself in colour.
> 7. **Package** as a single .exe file.

### A4. Module prompts

**Offline rules (validators.py)**

> Write Python functions validate_pan, validate_gstin and validate_udyam. Each returns a list of CheckResult (department, field, check, status PASS/WARNING/FAIL/NOT PROVIDED, message), so that the report can colour the exact Excel field that failed.
> - Implement the GSTN mod-36 check-digit algorithm.
> - Map the PAN 4th character to the holder type, and map the declared constitution to the allowed PAN types.
> - Add a function that decides 43B(h) applicability from the Udyam enterprise-type history, using the classification row applicable on the invoice date.

**Online portal automation (online.py)**

> Using Playwright (sync API), open Microsoft Edge (fall back to Chrome) in visible mode.
> - **GST** (services.gst.gov.in/services/searchtp): type the GSTIN in #for_gstin so the captcha appears, and focus the captcha box. Capture the JSON response of /api/search/taxpayerDetails and map lgnm, tradeNam, sts, rgdt, cxdt, ctb, dty, pradr.adr.
> - **Udyam** (Udyam_Verify.aspx): fill the Udyam number and focus the code box. After the user clicks Verify, parse "Name of Enterprise", "Major Activity", "Organisation Type", "Date of Udyam Registration", the enterprise-type table (year / type / date) and the NIC table.
> - **PAN**: the e-Filing portal blocks automated browsers ("Permission Denied"), so do not automate it and do not try to get around the block. Use **Know Your AO** in operator-confirmation mode instead:
>   - open the page in the user's normal default browser and copy the PAN to the clipboard;
>   - the operator pastes the PAN, enters their mobile number and the OTP, reads the result, and clicks **VALID** or **INVALID** in the assistant window;
>   - if the operator copied the result page (Ctrl+A, Ctrl+C), parse the name, PAN status and jurisdictional AO from it as audit evidence.
> - **Fallback:** if any portal shows "Permission Denied" to the automated browser, switch that department to the same operator-confirmation mode automatically.
> - Poll every 0.6 s. Support Skip, Not-found and Stop buttons, and a 5-minute timeout per vendor.
> - Use label-based parsing so that small layout changes on the portals do not break the app.

**Excel report (report.py)**

> Use openpyxl to create the colour-coded report.
> - Palette:
>   - header: medium-light blue #9DC3E6
>   - section: #DDEBF7
>   - pass: #C6E0B4
>   - warning: #FFE699
>   - fail: #F4B183
>   - not provided: #D9D9D9
>   - portal data: #E4DFEC
> - Sheets:
>   - **Summary:** counts by department and stage, overall result, AI summary, colour legend.
>   - **Validation Report:** one row per vendor, grouped section headers, and the failed input cells coloured.
>   - **Check Details**
>   - **MSME Register:** year-wise enterprise type and the 43B(h) flag.
>   - **Portal Data:** audit trail.
> - Freeze panes, add filters, landscape fit-to-width.
> - Also create an input template with a constitution drop-down and dummy sample rows, each demonstrating a different error.

**GUI (app.py)**

> Build a Tkinter GUI in medium-light colours.
> - Steps: ① Offline Validation, ② Online Validation (PAN/GST/Udyam checkboxes), ③ AI Remarks & Excel Report.
> - Show a vendor grid with rows coloured by overall result. Double-click a row to see check-wise details.
> - Add an always-on-top "Online validation assistant" window that tells the user what to type in the browser.
> - Run the online work in a background thread with a queue to the GUI.
> - Add a Settings window for the verifier mobile number and an optional AI provider and key.

**AI remarks (ai_remarks.py)**

> Write an AI layer that only drafts remarks and never changes a validation result.
> - Mask PAN, GSTIN and Udyam numbers before sending anything.
> - Support Gemini and OpenAI through urllib, asking for a JSON-only response.
> - Batch vendors in groups of 25.
> - Fall back to rule-based remarks when there is no key or the AI call fails.

**Packaging**

> Package the app with PyInstaller as a single windowed .exe (--onefile --windowed --collect-all playwright). It should use the Edge/Chrome already installed on Windows, so no browser download is needed. Also give RUN.bat and BUILD_EXE.bat for running from source.

### A4a. Change request after live testing

> While validating on Income Tax, "Permission Denied" is shown. Use https://eportal.incometax.gov.in/iec/foservices/#/pre-login/knowYourAO to validate PAN. It provides the required data, and the operator needs to confirm the validation.

### A4b. Change request after live testing

> While validating the Udyam, it goes to the home page. Use https://udyamregistration.gov.in/Udyam_Verify.aspx to access the relevant page directly. In the input file, remove DOB / DOI. Add address, email id and authorised person in the input sheet to look more relevant.

Changes made as a result:
- Open Udyam_Verify.aspx directly. If the site redirects to the home page, load the URL again once the session is set, or click the Verify link. If that still fails, switch to operator-confirmation mode.
- Remove DOB/DOI.
- Add offline checks: authorised person present, email format, and a 6-digit PIN code in the address.
- Online, compare the address PIN code with the GST principal place of business.

### A5. Sample data prompt

> Create dummy vendor rows for the template. Each row should demonstrate one check: a clean vendor, a duplicate PAN, a constitution mismatch, a wrong PAN length, an old Udyog Aadhaar number, a wrong GSTIN check digit, a GSTIN belonging to another PAN, a state mismatch, and a missing DOB.

### A6. Documentation prompts

> Write a README covering the problem statement, features, installation, usage steps, colour legend, the design principle "AI drafts, rules decide", limitations and future scope.

> List all the prompts used to generate each output of this project in a PROMPTS.md file, for the capstone submission.

---

## PART B – Prompts the app sends to the AI at run time

These are used in step ③ when an AI provider is configured in Settings. The text is the same as in `ai_remarks.py`.

### B1. System prompt

```
You are an audit assistant working for a Chartered Accountant firm in India.
You draft short, professional remarks for a VENDOR MASTER VALIDATION report covering
PAN (Income-tax Act), GSTIN (CGST Act, 2017) and Udyam Registration (MSMED Act, 2006).

Strict rules:
1. The validation results given to you are FINAL. Never change PASS / WARNING / FAIL.
2. Do not invent facts, sections, dates or numbers that are not in the input.
3. For each vendor write:
   - "remark": one or two sentences (max 45 words) stating what is wrong or that all is in order.
   - "action": the follow-up the accounts team should take with the vendor (max 25 words),
     e.g. "Obtain corrected GST certificate", "Collect Udyam certificate", "No action".
4. Where relevant mention the compliance impact in plain words: higher TDS u/s 206AA
   for missing/inoperative PAN, ITC risk for cancelled/invalid GSTIN, Sec. 43B(h)
   (Sec. 37(2)(g) of Income-tax Act, 2025) 45-day payment rule for Micro/Small enterprises.
5. Identifiers are masked; refer to them as "PAN", "GSTIN", "Udyam number".
6. Reply ONLY with valid JSON, no markdown.
```

### B2. User prompt template

```
Write remarks for the following vendors.

Return JSON in exactly this shape:
{"vendors": [{"vendor_code": "...", "remark": "...", "action": "..."}],
 "summary": "A 4-6 sentence summary for the partner covering how many vendors are approved,
             need review or must be fixed, the most common problems, and MSME (43B(h)) exposure."}

Validation data (JSON):
{payload}
```

`{payload}` is a list of vendors with their FAIL/WARNING checks only. All PAN, GSTIN and Udyam numbers are replaced with `[PAN]`, `[GSTIN]` and `[UDYAM]`.

### B3. Example payload sent (masked)

```json
[{"vendor_code": "V008", "vendor_name": "Kaveri Agro Foods Limited",
  "constitution": "Public Limited Company", "overall": "REJECT / FIX",
  "msme_type": "", "sec_43bh": "",
  "issues": [{"stage": "Offline", "dept": "GST", "field": "GSTIN", "check": "Check digit",
              "result": "FAIL",
              "detail": "Check digit should be 'X' but is '0' - GSTIN is mistyped / invalid."}]}]
```

---

## Responsible-AI notes (for the presentation)

- **Rules decide, AI drafts.** Pass/fail comes from deterministic Python rules and government portal data, never from the AI.
- **Confidentiality** (ICAI Code of Ethics): identifiers are masked before any text leaves the computer, and the AI step is optional.
- **Human in the loop:** captcha and OTP are always entered by the CA. The app does not bypass portal security. Where a portal blocks automated browsers (e-Filing), the CA confirms the result and the app records it as "confirmed by operator".
- **Audit trail:** the raw portal data and every check are kept in the report.
