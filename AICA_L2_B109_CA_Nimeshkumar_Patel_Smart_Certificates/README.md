# Smart Certificates — CA Certificate Automation (V54)

**ICAI AICA Level-2 Capstone Project**  
**Candidate:** CA Nimeshkumar Maheshbhai Patel  
**Membership:** 165969  
**Batch:** AICA-L2B109-GANDHINAGAR (Google Form batch entry: **109**)

## Problem and objective
Chartered Accountants spend time manually extracting information from ITR and GST returns, compiling turnover/net worth workings, and drafting certificates. Smart Certificates is a **desktop-based, rule-driven automation tool** that helps import supported records, organise client data, review extracted values and generate editable Word certificates and management representation letters. All figures require CA verification before issuance.

## Features
- Local SQLite client database and CA signatory profiles
- ITR-3, ITR-4, ITR-5 JSON support; supported PDF ITR extraction
- ITR acknowledgement and financial information extraction
- Turnover from ITR and GSTR-1/GSTR-3B; financial-year mapping
- Business net worth via owner/partner capital or assets minus outside liabilities, as applicable
- Turnover, Net Worth, Combined, and ITR Acknowledgement Verification certificates
- Word certificate/MRL and Excel working export
- Separate user-guide tab and simplified V54 interface

## Technology
Python, PyQt6, SQLite (`sqlite3`), PyMuPDF, JSON, python-docx, openpyxl, Pillow, pytesseract (optional OCR), PyInstaller, ChatGPT (development assistance), GitHub (submission/version control). **The running application is not a live AI model.**

## Running from Python
Windows 10/11 64-bit, Python 3.10+ installed. Double-click `RUN_PYTHON_WINDOWS.bat`; the Python application attempts to install missing packages using pip when online. Alternatively `pip install -r requirements.txt` then `python src/Smart_Certificates_V54.py`.

## Building an EXE
On Windows with Python and internet, double-click `BUILD_WINDOWS_EXE.bat`. Share the **entire** `dist/SmartCertificates/` folder; recipients need no Python or pip installation. **This repository contains a builder, not a precompiled EXE.** Optional scanned-image OCR may require a separately installed Tesseract executable.

## Privacy and limitations
Never upload client tax returns, PAN/GSTIN details, SQLite databases, UDIN records or actual certificates to public GitHub. Use anonymised demonstration data. Business equity is not automatically personal net worth. Test on Windows and review all outputs before use.

## Documentation
- [Project report](docs/PROJECT_REPORT.md)
- [User guide](docs/USER_GUIDE.md)
- [Official ICAI submission procedure](docs/ICAI_GITHUB_AND_FORM_GUIDE.md)
- [EXE distribution](docs/EXE_GUIDE.md)
- [Video script](docs/VIDEO_SCRIPT.md)
- [Form answers](docs/GOOGLE_FORM_ANSWERS.md)
