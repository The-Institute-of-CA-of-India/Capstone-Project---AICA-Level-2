# GST Automation Tool for a Mid-size CA Firm

**AICA Level 2 Capstone Project** · CA Janhavi Deshpande · Batch 100 · Pune

This tool takes a CA firm's monthly and year-end GST work from the GST portal to the GSTR-9 working paper:

1. **Download** GSTR-1, GSTR-3B and GSTR-2B for a year with a Chrome extension.
2. **Reconcile the returns**: GSTR-1 against 3B, 3B ITC against 2B, and 12 months of 2B in one workbook.
3. **Match the purchase register with GSTR-2B** into three groups: Matched, Likely matched (only the invoice number or date differs), or Unmatched. Each line carries the reason.
4. **Email vendors**: one draft per vendor listing only that vendor's invoices. Nothing is sent automatically.
5. **Prepare the GSTR-9 working paper**:
   - Tables 4–8, 12, 13 and 18
   - Table 8D explained invoice by invoice
   - Risk flags for 17(5), 16(4), Rule 37, RCM, and 3B against books

**Offline:** only the download step goes online, to the GST portal. Everything else runs inside the browser from one HTML file, and a browser test recorded no network requests. Client data never leaves the computer.

> Everything in this repository uses **made-up demo data**. The client "Kaveri Foods Private Limited" and every GSTIN in it are fictional. The repository contains no passwords, API keys or tokens.

## Video and presentation

- **Video (unlisted):** https://youtu.be/842Hn1RyBLE
- **Presentation:** `docs/Presentation.pdf` (export it from the deck)

---

## Folder contents

| Path | What it is |
|---|---|
| `tools/gst-returns-downloader-v2.5.4.zip` | Chrome extension (stage 1: download) |
| `tools/GST_Reconciliation.html` | Offline reconciliation page (stages 2–5), single file |
| `tools/Purchase_Register_Format.xlsx` | Recommended purchase register format, with an instructions sheet |
| `demo-data/Demo_GST_Data.zip` | Made-up demo data: a Q1 quick demo and a full year FY 2024-25 with planted errors |
| `sample-outputs/GST_Reconciliation_27AABCK1234L1ZM_FY2024-25.xlsx` | Returns reconciliation (GSTR-1 vs 3B, GSTR-2B vs 3B ITC) the tool produced from the full-year demo data |
| `sample-outputs/GSTR2B_Combined_27AABCK1234L1ZM_Apr2024-Mar2025.xlsx` | Combined GSTR-2B for April 2024 to March 2025 |
| `sample-outputs/Sample_GSTR9_working_paper_demo.xlsx` | GSTR-9 working paper the tool produced from the demo data |
| `screenshots/` | Screens of each step, on demo data |
| `docs/GST_Automation_Tool_Handover.md` / `.docx` | Full technical and user documentation |
| `PROJECT_SUMMARY.md` | One-page summary of the project |
| `PROMPTS.md` | The key prompts used to build the tool with AI |
| `VIDEO_SCRIPT.md` | Scene-by-scene script of the demo video |

## Requirements

- Google Chrome or Microsoft Edge on Windows or macOS
- No installation, Python or internet connection for the reconciliation page
- A GST portal login, only for the download step

## Quick start with the demo data (no portal login needed)

1. Unzip `demo-data/Demo_GST_Data.zip`.
2. Double-click `tools/GST_Reconciliation.html`. It opens in Chrome.
3. **Step 1:** from `Demo_GST_Data/Full_year_FY2024-25/`, drag in the GSTR-1 and GSTR-3B PDFs and the GSTR-2B files for April 2024 to March 2025. (Add the later GSTR-2B files too when you go on to step 6, for Tables 8A and 8C.)
4. **Steps 2–3:** check the files it found, then download the returns report and the combined GSTR-2B.
5. **Step 4:** choose the purchase register from the same folder, check the column mapping, and click **Reconcile**. Review the Likely matched and Unmatched lines, then download the Excel report.
6. **Step 5:** enter the firm's name, then click **Compose** for a vendor and press **Ctrl+V** in the mail body to paste the invoice table. Or download all drafts as a ZIP.
7. **Step 6:** choose FY 2024-25, confirm the ledger categories, set the "as on" date to 30-11-2025, and download the GSTR-9 working paper.

For a quicker look, use `Q1_quick_demo/`. It gives 46 matched, 3 likely matched and 9 unmatched invoices.

## Using the extension on the live portal

1. Unzip `tools/gst-returns-downloader-v2.5.4.zip`.
2. Open `chrome://extensions`, turn on **Developer mode**, click **Load unpacked**, and choose the `gst-returns-downloader` folder.
3. In the extension's **Details**, turn on **Allow access to file URLs**.
4. Open `chrome://settings/content/automaticDownloads` and allow `https://return.gst.gov.in` and `https://gstr2b.gst.gov.in`.
5. Close other GST portal tabs, because the portal allows one session per login.
6. Open the extension and enter the username. Choose the year, the returns and the quarters, then click **Start**.
7. Type the captcha yourself, and don't use that tab until the run finishes. A ZIP of the returns is saved in the chosen folder.

The password is used only for the login and is held in memory until then. The extension never stores it. Files that were already downloaded are skipped.

## Purchase register

Use `tools/Purchase_Register_Format.xlsx`, or any Excel or CSV export, such as one from Tally. The page maps the columns once and remembers the mapping. The columns are:

- Supplier GSTIN, Supplier Name, Invoice No, Invoice Date, Document Type
- HSN/SAC, Description, Ledger Head
- Taxable Value, IGST, CGST, SGST, Cess
- Reverse Charge, ITC Claimed in GSTR-3B (Month), Payment Date, Vendor Email

## Limitations

- The extension follows the portal's screens, so a portal redesign may need an update.
- It handles one client at a time.
- It has been tested on demo data, and the downloads on the live portal. A full year of real client data is still to be tested.
- Very large purchase registers have not been stress-tested in the browser. A Python version is planned for that.
- Mail drafts have not been tested in Outlook.

See `docs/GST_Automation_Tool_Handover.md` for full details.

## Disclaimer

This tool is a working aid. Results, especially Likely matches and GSTR-9 figures, must be reviewed by a qualified professional before filing or communicating with vendors.
