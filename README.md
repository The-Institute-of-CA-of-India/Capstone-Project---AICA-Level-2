# FS Hard Copy Review Tool

**AICA Level 2 – Capstone Project**
**Author:** Rohit Boraniya, Chartered Accountant (UAE) – [linkedin.com/in/rohitca](https://www.linkedin.com/in/rohitca) · *CA Ro Bo*

A desktop tool that runs a 19-point **hard copy review checklist** on a draft set of
**financial statements (FS) and auditor's report (AR)** in PDF and produces a ready-to-use
**Word findings report**: what is wrong, where (page reference), the exact wording found and
the correction required.

---

## 1. Problem statement

Before a set of audited financial statements is issued, a reviewer reads the printed draft
("hard copy") against a standard checklist: company name, dates, currency, page numbers,
casting, cross-references between statements and notes, cash flow captions, spelling and so on.

This review is:

- **Manual and time-consuming** – a single FS can take 1–3 hours to check line by line.
- **Error-prone** – arithmetic and cross-reference errors are easy to miss when reading repetitive pages.
- **Inconsistent** – different reviewers report findings in different formats and depth.

## 2. Solution

The tool automates the first pass of the review. The reviewer uploads the draft FS PDF
(and, optionally, last year's signed FS) and receives a Word report organised by the 19
checklist points within a few minutes. The reviewer then focuses on judgment and sign-off
instead of mechanical checking.

### How it works – hybrid engine

| Layer | What it does |
|---|---|
| **Python (rules)** | Extracts text and layout from every page, classifies pages (AR, SOFP, P&L, SOCE, CFS, notes), recomputes **all arithmetic** (casting, cross-casting, statement-to-note links), and runs rule-based checks (company name variants, dates, currency, page sequence, note numbering, coloured text, etc.). |
| **AI (optional)** | Reviews the judgment-based points (policy wording, consistency of disclosures, spelling/grammar in context), verifies the rule candidates against page images, and writes the final findings following the checklist rules. Supported: Claude, ChatGPT, Gemini or any OpenAI-compatible endpoint. |
| **Report builder** | Creates a landscape Word report: one row per checklist point with findings, page references and corrections, plus a "Critical points" summary. |

Without an API key the tool runs in **rules-only mode** and marks the judgment points it
could not check as "Not verifiable" – no data leaves the computer in that mode.

All figures are recomputed in Python; the AI is never relied on for arithmetic.

## 3. The 19 checklist points

| # | Checklist point |
|---|---|
| 1 | Overall reading of hard copy AR & FS |
| 2 | Comparison of PY figures with acknowledged hard copy in file |
| 3 | Comparison of PY notes with acknowledged hard copy in file |
| 4 | Header & footer accuracy checking |
| 5 | Page numbers accuracy checking |
| 6 | Company name checking |
| 7 | Year / date checking |
| 8 | Check accuracy of currency written throughout the report |
| 9 | Totaling verification |
| 10 | Checking of accuracy of link of various figures |
| 11 | Sequence accuracy (note no. / pages etc.) |
| 12 | Format of various pages (BS / PL / CFS / SOCE and notes) |
| 13 | Cash flow statement verification with non-cash items accuracy |
| 14 | Financial assets and financial liability figure correctness |
| 15 | Check whether any paragraph is cut in the print out |
| 16 | Consistent use of "Establishment" or "Company" throughout |
| 17 | Increase / decrease & used in / generated from in cash flow |
| 18 | Spelling check |
| 19 | "Due to" / "due from" related party balances under investing / financing activities |

## 4. Key features

- Simple light-themed desktop interface (PySide6 / Qt) – two upload boxes: **draft FS** and **prior-year FS** (optional).
- Draft FS: text-based PDF. Prior-year FS: text-based **or scanned** (built-in OCR).
- Page references follow the **printed page numbers** of the FS.
- Each finding is reported under exactly one checklist point – no duplicates.
- Word report saved automatically to the user's **Downloads** folder.
- AI provider and model selectable in **Settings**; Settings can be **password-locked**, with an AI on/off switch on the main screen.
- API keys are never shown or stored in plain text (Windows DPAPI / macOS Keychain). The settings password is stored only as a salted PBKDF2 hash.
- Runs on **Windows** and **macOS**; can be packaged as a single `.exe` / `.app` to share with colleagues who have no Python installed.
- Optional command-line mode for batch use.

## 5. Sample output

[`Sample_Hard_Copy_Review_Findings_Report.docx`](Sample_Hard_Copy_Review_Findings_Report.docx)
is a real report produced by the tool on a draft FS (year ended 31 December 2025) with the
prior-year signed FS supplied as a scanned PDF. Company names, related-party names, people's
names and file names have been replaced with placeholders for confidentiality.

The report contains:
- engagement details (client, period, documents reviewed, date of review);
- **Critical points to correct before issue** – a short summary for the reviewer;
- the **checklist findings table** – one row per point (1–19) with status
  (Exception / Query / OK / N/A / Not verifiable) and each finding with its page reference,
  the exact wording found and the correction required.

## 6. Folder structure

```
Rohit-Boraniya-FS-Hard-Copy-Review-Tool/
├── README.md                                  – this file
├── fs_hard_copy_review.py                     – the application (single Python file)
├── requirements.txt                           – Python package list
├── run_tool.bat                               – Windows: first-run setup + launch
├── build_exe.bat                              – Windows: build a self-contained .exe
├── Sample_Hard_Copy_Review_Findings_Report.docx – sample output (client details masked)
├── .gitignore
└── macos/
    ├── fs_hard_copy_review.py                 – same application
    ├── requirements.txt
    ├── run_tool_mac.command                   – macOS: first-run setup + launch
    ├── build_app_mac.command                  – macOS: build a shareable .app
    └── README_mac.txt                         – macOS instructions
```

## 7. Installation and use

### Requirements
- Python **3.10 – 3.12** (3.13+ works, but without OCR for scanned prior-year PDFs)
- Internet connection on the first run (to install packages) and when AI mode is used

### Windows
1. Download or clone this folder.
2. Double-click **`run_tool.bat`**. The first run creates a private Python environment (`.venv`) and installs the packages; later runs open the tool directly.
3. *(Optional)* Open **Settings**, choose the AI provider, paste the API key and set a settings password.
4. Select the draft FS PDF (and prior-year FS if available) and click **Run hard copy review**.
5. The Word report is saved to your Downloads folder – click **Open report** to view it.

To create a single shareable file, double-click **`build_exe.bat`** → `dist\FS_Hard_Copy_Review.exe`.

### macOS
See [`macos/README_mac.txt`](macos/README_mac.txt). In short: `chmod +x *.command`, then double-click `run_tool_mac.command`.

### Command line (optional)
```
python fs_hard_copy_review.py --cli "draft_fs.pdf" ["prior_year_fs.pdf"]
```

## 8. Technology used

| Purpose | Library / service |
|---|---|
| Desktop UI | PySide6 (Qt) |
| PDF text and layout extraction | pdfplumber |
| Page rendering | pypdfium2, Pillow |
| OCR for scanned PDFs | RapidOCR (ONNX Runtime) |
| Word report | python-docx |
| AI calls | requests (Claude / OpenAI / Gemini APIs) |
| Packaging | PyInstaller |

## 9. AI usage and data privacy

- AI mode is **optional** and switched off when no key is configured.
- In AI mode, page text and page images of the uploaded FS are sent to the selected AI provider. Use it only in line with your firm's client confidentiality policy and the provider's data terms.
- Each user enters their own API key; no key is included in this repository.

## 10. Limitations

- The draft FS must be a text-based PDF (exported from Word / Excel), not a scan.
- Points 2 and 3 need the prior-year signed FS; without it they are reported as "Not verifiable".
- The tool supports the reviewer – it does not replace professional judgment or partner review.

## 11. Disclaimer

Built for learning purposes as part of the ICAI **AI for Chartered Accountants (AICA) Level 2**
course. Findings should be checked by a qualified reviewer before the financial statements are issued.
