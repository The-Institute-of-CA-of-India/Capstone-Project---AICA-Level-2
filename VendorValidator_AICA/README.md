# Vendor Registration & Validation App
### PAN · GSTIN · Udyam — offline and online validation
**AICA Level-2 Capstone Project**

---

## 1. Problem statement

Every CA firm, auditor and corporate accounts team onboards vendors. A vendor master with wrong data causes three problems:

- **Wrong or inoperative PAN** → TDS at the higher rate u/s 206AA / 206AB, and defaults in TDS returns.
- **Mistyped, cancelled or other-PAN GSTIN** → ITC is denied and GSTR-2B mismatches appear.
- **MSME status not captured** → the 45-day payment rule of **Sec. 43B(h)** of the Income-tax Act, 1961 (**Sec. 37(2)(g)** of the Income-tax Act, 2025) is missed. This leads to disallowance and incorrect tax audit / MSME Form-1 reporting.

Checking each vendor manually on three government portals is slow and error-prone.

## 2. Solution

A one-click Windows app that reads the vendor master from Excel and works in four steps.

| Step | What happens |
|---|---|
| **① Offline validation** | Instant rule checks without internet:<br>• **Contact details:** authorised person given, email format valid, 6-digit PIN code in the address.<br>• **PAN:** structure, holder type (4th character), name initial (5th character), constitution vs PAN.<br>• **GSTIN:** length, state code, **mod-36 check digit**, PAN inside the GSTIN.<br>• **Udyam:** format, state code, old Udyog Aadhaar number.<br>• Duplicates across the master. |
| **② Online validation** | PAN → GST → Udyam, vendor by vendor, on the **official portals**. The app opens the portal and fills in the number. **You type the captcha / OTP**, and the app reads the result and moves to the next vendor. |
| **③ AI remarks** | The AI drafts a vendor-wise remark and follow-up action, plus a partner summary. Identifiers are masked before sending. If no AI key is set, rule-based remarks are used. |
| **④ Excel report** | A colour-coded workbook. **The failed field itself is highlighted.** |

### Data fetched online

| Portal | Fields captured |
|---|---|
| GST (services.gst.gov.in) | Legal name, trade name, GSTIN status, registration date, cancellation date, constitution, taxpayer type, address (PIN code compared with input address) |
| Udyam (udyamregistration.gov.in) | Enterprise name, **major activity**, organisation type, **enterprise type (year-wise) with classification date**, date of Udyam registration, NIC codes |
| PAN (e-Filing "Know Your AO") | PAN validity confirmed by the operator. If the result page is copied: name, PAN status and jurisdictional AO (area code / AO type / range / AO no.) |

### 43B(h) / 37(2)(g) logic

| Udyam result | Applicable? |
|---|---|
| Micro or Small, manufacturing/services | **Yes**: pay within 15/45 days |
| Medium | **No** |
| Micro/Small but NIC codes only trading (45/46/47) | **Review**: traders are not covered under MSMED Act Sec. 15 |
| Invoice date before the first classification date | **No**: registration is prospective |

## 3. Colour legend (medium-light)

| Colour | Meaning |
|---|---|
| ![](https://placehold.co/15x15/9DC3E6/9DC3E6.png) `#9DC3E6` | Header |
| ![](https://placehold.co/15x15/C6E0B4/C6E0B4.png) `#C6E0B4` | PASS / Approved |
| ![](https://placehold.co/15x15/FFE699/FFE699.png) `#FFE699` | WARNING / Review |
| ![](https://placehold.co/15x15/F4B183/F4B183.png) `#F4B183` | FAIL / Reject; the failed field is shown in this colour with bold red text |
| ![](https://placehold.co/15x15/D9D9D9/D9D9D9.png) `#D9D9D9` | Not provided |
| ![](https://placehold.co/15x15/E4DFEC/E4DFEC.png) `#E4DFEC` | Data fetched from the portal |

## 4. Report sheets

1. **Summary:** counts by department (offline / online), overall result, AI summary, legend.
2. **Validation Report:** one row per vendor (input → offline → PAN online → GST online → Udyam online → result).
3. **Check Details:** every check with its result and message (audit trail).
4. **MSME Register:** year-wise enterprise type, classification date and 43B(h) flag.
5. **Portal Data:** raw data captured from each portal.

## 5. How to use

**Option A: ready-made exe**
1. Double-click `VendorValidator.exe`. The first start takes about 10–15 seconds while it unpacks.
2. Click **Create input template**, or **Browse…** to pick your Excel.
3. Click **① Offline Validation** and review the coloured grid. Double-click a row for details.
4. Tick PAN / GST / Udyam and click **② Online Validation**. Edge opens with the number already filled in.
   - **GST:** type the 6-digit captcha → **SEARCH**
   - **Udyam:** type the verification code → **VERIFY**
   - **PAN:** the e-Filing portal blocks automated browsers, so **Know Your AO** opens in your normal browser with the PAN already copied. Press Ctrl+V, enter *your* mobile number, click **Continue** and enter the OTP. Optionally press Ctrl+A, Ctrl+C on the result page to save its details. Then click **✔ VALID** or **✖ INVALID** in the assistant window.

   The small *assistant* window on the right tells you what to do and has **Skip**, **Not found / Invalid** and **Stop** buttons.
5. Click **③ AI Remarks & Excel Report**. The report is saved next to your input file.

Requires Windows 10/11 with Microsoft Edge (pre-installed) or Google Chrome.

**Option B: from source**
```
pip install -r requirements.txt
python app.py              (or double-click RUN.bat)
BUILD_EXE.bat              (rebuilds dist\VendorValidator.exe)
```

**Optional AI:** in ⚙ Settings choose `gemini` or `openai` and paste your API key. Settings are stored in `%APPDATA%\VendorValidator\config.json`.

## 6. Design principles

- **Rules decide, AI drafts.** Validity comes only from deterministic rules and portal data.
- **Human in the loop.** The captcha and OTP are always typed by the user; nothing is bypassed or scraped in bulk. Where a portal refuses automated browsers (e-Filing), the app switches to operator-confirmation mode rather than evading the block.
- **Confidentiality.** PAN, GSTIN and Udyam numbers are masked before any AI call, and the AI step is optional.
- **Resilient to portal changes.** Results are read by label text and by the GST JSON response, not by fixed screen positions.

## 7. Project files

| File | Purpose |
|---|---|
| `app.py` | Tkinter GUI, workflow, threading |
| `validators.py` | Offline rules for PAN / GSTIN / Udyam, 43B(h) logic |
| `online.py` | Playwright automation of the three portals, parsers, online checks |
| `report.py` | Excel template and colour-coded report (openpyxl) |
| `ai_remarks.py` | AI prompts, masking, Gemini/OpenAI calls, rule-based fallback |
| `Vendor_Input_Template.xlsx` | Input format (Vendor Name, Constitution, Authorised Person, Email ID, Address, State, PAN, GSTIN, Udyam No) with 9 dummy rows showing each type of error |
| `PROMPTS.md` | All prompts used to build the project and used by the app |
| `RUN.bat` / `BUILD_EXE.bat` | Run from source / build the exe |

## 8. Limitations and future scope

- The government portals may change their screens. The parsers use labels and have fallbacks, but selectors may need updating.
- The PAN check needs one OTP per PAN on Know Your AO, and the operator confirms each result.
- **Future scope:**
  - licensed KYB APIs (no captcha) for bulk runs;
  - GST return-filing status (GSTR-1/3B) for vendor rating;
  - PAN–Aadhaar link status (Sec. 206AA);
  - direct import/export of the Tally vendor master;
  - scheduled re-validation of active vendors every quarter.

---
*Built by a CA, for CAs. AI does the repetitive groundwork; the Chartered Accountant keeps professional judgement.*
