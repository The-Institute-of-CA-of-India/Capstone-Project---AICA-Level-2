# PDF Redactor PRO v2.3.3

*by CA Lucika Mehta · +91 90190 79090 · orsshah@gmail.com*

**Capstone project, AICA Level 2.** A desktop tool that redacts client identifiers from bank statements, notices, KYC copies, Excel and Word files in bulk, on the user's own computer, so that the documents can be analysed with AI tools without exposing confidential client data.

**Start here:** install with `PDF-Redactor-PRO-Setup-<version>.exe` (built with `Build_Installer_Windows.bat`), or run from source with `Start_Redactor_Windows.bat`. Try it on the fictitious files in `sample_documents/`. A one-line explanation of every feature is in `docs/PDF_Redactor_PRO_Feature_Guide.docx`.

A local tool that de-identifies bank statements, income-tax notices and orders, KYC copies, Excel and Word files in bulk, so that they can be analysed with AI tools (Claude, ChatGPT etc.) without exposing confidential client identifiers.

All processing happens on your own computer. The app listens only on `127.0.0.1` (no other computer can reach it), uses no online fonts or scripts, and sends no file anywhere.

## For colleagues: install and use (no Python needed)

Run **PDF-Redactor-PRO-Setup-2.3.3.exe**, click *Next* to the end, and open *PDF Redactor PRO* from the Start menu or desktop. Nothing else needs installing: OCR (English, Hindi, Marathi) and every library are inside. No administrator rights are needed. If Windows shows *Windows protected your PC*, click **More info → Run anyway** (the program is not code-signed).

Updates install over the old version; settings are kept in `%APPDATA%\PDF Redactor PRO`.

The program opens in its own window (Microsoft Edge in app mode, with a private profile, so no address bar, tabs or browsing history) and stops by itself when that window is closed. Opening it again while it is running just opens another window.

**If it does not open:** any start-up problem is shown in a message box, and every start, stop and error is written to `%APPDATA%\PDF Redactor PRO\app.log`. Send that file to the publisher.

## For the publisher: building the installer

See **BUILDING.md**. In short: install Python 3.11+ and Inno Setup once (`winget install JRSoftware.InnoSetup`), then double-click **Build_Installer_Windows.bat** (or run `python packaging\build.py`). The result is `dist\PDF-Redactor-PRO-Setup-<version>.exe`. To release an update, raise `VERSION` in `redact/model.py` and build again.

## Running from source (developers)

### One-time setup

1. **Python 3.11 or later** – <https://www.python.org/downloads/> (on Windows, tick *Add python.exe to PATH*).
2. **Tesseract OCR** – needed for scanned pages and photographs.
   - Windows: UB Mannheim build – <https://github.com/UB-Mannheim/tesseract/wiki>. During installation, open *Additional language data* and tick **Hindi** and **Marathi** for bilingual notices.
   - macOS: `brew install tesseract tesseract-lang`
   - If installed elsewhere, set `TESSDATA_PREFIX` to its `tessdata` folder.

### Starting

- Windows: double-click **Start_Redactor_Windows.bat**
- macOS: double-click **Start_Redactor_Mac.command** (first time: right-click → Open)

The launcher installs or updates the libraries whenever `requirements.txt` changes, then opens the app in your browser at <http://127.0.0.1:8501>. Keep the black launcher window open while you work; close it to stop the app.

## Using it

**Appearance and contact.** *Settings* (gear, top right) has light / dark / system theme, text size (A− / A+), where files open, and *Restore all defaults*. *Contact* (top right, and on the start screen) shows the publisher's phone and e-mail.

**1. Prepare a batch.** Drop files (or enter a folder path), fill in the client's PAN, date of birth/incorporation and name so locked 26AS, AIS, ITR-V and bank statements open automatically, add any words to redact, and press **Redact**. *Settings* (top right) controls the document type, labelled or black boxes, what to redact and OCR; it is remembered on this computer.

**2. Review in the workstation.**

| Area | What it does |
|---|---|
| Files (left) | Every file with its type, page count, items and re-check status. Filter to *To check* or *Edited*. |
| Viewer (centre) | *Redacted* shows the result; *Original* shows the original with each redaction as an ink bar coloured by category; *Side by side* shows both. Zoom with + / − or Ctrl + mouse wheel. |
| Items (right) | Everything redacted in the file, grouped by type, with its label. Untick to leave a value visible; hover to see it on the page; double-click to show the full value; ⋯ for *Leave visible in all files* or *Redact this text in all files*. |
| Add | Redact text in this file or all files; lists your boxes and words. |
| Details | Re-check result, anything still detected, fingerprints, single-file download. |

**Manual redaction**
- Click any bar on the page to switch it off (it turns blue and dashed) or back on.
- Press **D** (Draw box) and drag over anything missed. If there is text under the box, you are offered **Every match in this file** or **In all files**, so one drag redacts every occurrence.
- Changes collect in the bar above the page; **Apply** (Ctrl+Enter) or **Discard**. Labels stay consistent.

**3. Download.** **Download** gives a single redacted file as it is (with its text version and transaction table as separate files, if ticked); several files come as one ZIP (with optional text versions, transaction tables and one combined PDF). **Records** gives the A4 *Certificate of Redaction of Client Documents*, the log and the label key: keep these on your computer.

**Transaction table (CSV).** For bank statements, *Download* can add `<file>_transactions.csv` with Date, Value date, Narration, Chq / Ref no., Debit, Credit, Balance and *Balance check*. Debit and credit are decided from the running balance (previous balance − debit + credit = balance), so *Balance check = OK* means the row is arithmetically verified; *Mismatch* or *Not checked* rows deserve a glance. Each transaction is assembled from all the lines of its row, wherever the date sits in the row (top line as in HDFC/SBI, or the middle of a multi-line cell as in ICICI); row separator lines are used when the statement has them, and page footers are left out. Handles separate Withdrawal/Deposit columns, a single Amount column marked Dr/Cr (attached or in its own column), balances marked Cr/Dr, whole-rupee amounts, S No. columns (kept in the CSV for cross-checking), value dates and cheque/ref numbers in their own columns, narrations before or after the amounts, two-line headers, multi-page tables, and dates such as 01/04/25, 01.04.2022, 1 Apr 2025 or 01-APR-25. Excel statements get `<file>_table.csv`. If no table is recognised, the app says so.

**The certificate** is an A4 portrait report: particulars (client reference and AI tool, or blank lines), summary, procedure applied, schedule of documents, the statutory framework under the Information Technology Act, 2000 (ss. 43A and 72A, SPDI Rules, 2011) and the Digital Personal Data Protection Act, 2023 and Rules, 2025 (with each provision's status on the date of issue), limitations, a signature block with blank lines for firm, FRN, name, membership number, UDIN, place and date, and Annexure A with SHA-256 fingerprints of every original and redacted copy.

**Keyboard:** D draw, V select, R / O / S views, M outlines, ← → pages, J / K next or previous file, + / − / 0 zoom, Delete removes a selected box, Ctrl+Enter applies, Esc cancels.

## OCR not working?

The installed program already contains OCR. When running from source, scanned pages need **Tesseract OCR**, a free program installed once.

1. Open the app. If OCR is missing, a yellow card on the start screen and in *Settings* says *Scanned pages can't be read yet*.
2. Download the Windows installer from <https://github.com/UB-Mannheim/tesseract/wiki> and install it in the default folder (`C:\Program Files\Tesseract-OCR`). On *Choose Components*, open *Additional language data* and tick **Hindi** and **Marathi**.
3. Press **Check again** on the card. No restart is needed; the card turns green.
4. Installed elsewhere? Open *Installed in a different folder?*, paste the Tesseract folder and press *Use this folder*. The location is remembered with your settings.

If OCR is ready but a scanned file still shows no OCR pages, the scan probably carries a hidden text layer. Choose *Every page with an image* under *Settings → Scanned pages*.

## What is detected

| Group | Items |
|---|---|
| Tax / KYC | PAN, GSTIN, TAN, Aadhaar (check-digit validated), VID, CIN, LLPIN, Director DIN, passport, voter ID, date of birth |
| Banking | Account numbers (labelled, masked XXXX1234), cards (Luhn-validated), any 9–18 digit number (UTR, references), IFSC, MICR, UPI IDs, customer/CIF IDs |
| Names and addresses | Names next to labels (Account Name:, Name of Assessee:), addresses (Address:, Regd. Office:) including continuation lines, the "To," block of letters and notices (authorities such as "The Assessing Officer" stay visible), counterparties in UPI/NEFT/IMPS narrations |
| Contact (off by default) | Mobile numbers, e-mail addresses |
| Images | QR codes and barcodes; photographs and signatures (switched on automatically for KYC documents) |

Amounts, dates, assessment years, sections and income-tax notice DINs (`ITBA/…`) stay visible.

## Key features

- **Document type detection** – each file is classified as bank statement, IT notice/order, KYC document or other, and settings are adjusted (e.g. long reference numbers stay visible in notices).
- **Labelled boxes** – `[ACCT-1]`, `[NAME-1]`, `[PARTY-3]`: the same value gets the same label in every file, so the AI can trace inter-account transfers, repeat counterparties and self-transfers. A masked number (XXXX7788) takes the label of the full account ending 7788.
- **Batch-wide redaction** – a value found in any file is redacted wherever it appears in every file, tolerant of spacing and common OCR misreads.
- **True redaction** – text under each box is deleted and image pixels blanked; metadata, attachments, links and form data are removed; passwords are removed from outputs.
- **Scanned pages** – OCR (English, Hindi, Marathi), re-checked after redaction, with an invisible text layer added so the AI can read them as text.
- **Excel, CSV and Word** – cells (including hidden sheets and account numbers stored as numbers), paragraphs, tables, headers and footers; document properties cleared.
- **Re-check** – every output is read again; anything still detectable is listed in the review panel. A safety check also flags any page where text moved during redaction.
- **Parallel processing** across processor cores.

## Command line (folder mode)

```
python redact_folder.py "D:\Clients\Sample Traders\AY 2024-25" --subfolders --labels --pan AAKCS1234F --dob 15/04/1980 --name "Sample Traders"
```
Run `python redact_folder.py --help` for all options.

## Limitations

- Detection is pattern-based. Unusual formats, handwriting and very poor scans can be missed – always skim the review panel before sharing.
- Counterparty and address detection are heuristics; untick false alarms in the review panel.
- Signature detection relies on a nearby "Signature"/"Signatory" label.
- Pictures inside Excel and Word files are not scanned, and charts in Excel are not carried over to the redacted copy.
- `pymupdf` is pinned to 1.28.2: version 2.0 moves neighbouring text when redacting. The app tests this at start-up and warns if an unsuitable version is installed.
- NumPy 2.4 or later is required: older NumPy versions fail to import on some Windows computers ("OverflowError: cannot convert longdouble infinity to integer").

## Files

| File | Purpose |
|---|---|
| `app_main.py` | Desktop entry point: app window (Microsoft Edge app mode, private profile), browser fallback, crash log, `--selftest` |
| `server.py` | Local app server (127.0.0.1 only) |
| `packaging/` | `build.py` (one-command build), PyInstaller spec, Inno Setup script, build requirements, icon |
| `Build_Installer_Windows.bat` | Double-click build on Windows |
| `BUILDING.md` | Building, releasing updates, licences |
| `redact/certificate.py` | A4 Certificate of Redaction with statutory references |
| `static/` | Interface (HTML, CSS, JavaScript; no external libraries). Colours follow the Income Tax e-Filing portal; Roboto font bundled under the SIL Open Font Licence |
| `redact/` | Engine: `detect` (detectors), `pdf`, `office`, `batch` (labels, propagation, passwords, parallel), `outputs` (ZIPs, extracts, certificate, folder mode) |
| `redact_folder.py` | Command-line folder mode |
| `sample_documents/` | Fictitious samples (bank password `SAMP1504`; 26AS password = PAN in lower case + 15041980), including three specimen PDFs (bank statement, GST invoice, rent agreement) with PANs, addresses and mobile numbers |
| `docs/` | Feature guide for the presentation (one line per feature, demo flow, likely questions) |
| `tests/` | `test_detectors.py` (unit tests), `test_statements.py` (CSV extractor across eleven bank layouts, before and after redaction), `run_batch.py`, `browser_test.py` (end-to-end in a real browser, needs Playwright) |
