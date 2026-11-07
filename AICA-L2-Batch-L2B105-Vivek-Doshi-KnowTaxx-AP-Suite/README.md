# KnowTaxx AP & Expense Intelligence Suite

**KnowTaxx** · *Knowledge Backed Innovative Solutions*

An AI-powered Accounts Payable, expense approval, vendor management and cost analytics platform for Indian CA firms and mid-size enterprises. It reads invoices with offline OCR, validates GST details, routes invoices through configurable approval rules, and reports on spend, budgets, aging and MSMED compliance. It runs on your own network, works on phones as an installable app, and processes invoices locally with no cloud service.

## Key features

- **Invoice OCR:** GSTIN with check-digit validation and repair, invoice number, Indian date formats, tax split, line items, and a confidence score per field
- **Human review:** the document beside the extracted fields, colour-coded by confidence, with an arithmetic check
- **Vendor portal:** a public self-registration link, document upload, duplicate detection by PAN, GSTIN and fuzzy name
- **Approval workflow:** multi-level rules by amount, category and cost centre; mobile cards with swipe; SLA tracking
- **Email ingestion:** IMAP listener with plus-addressing that routes mail to each client
- **Analytics:** dashboards, cost centre tree, budget variance with rule-based commentary, AP aging, MSMED 45-day view
- **Exports:** formatted Excel, PDF dashboard, Tally-ready CSV
- **PWA and offline:** installable on Android and iOS, camera capture, an offline queue with conflict detection
- **Administration:** five roles, client-level access, audit log, encrypted mail credentials, online backup

## Screenshots

See [docs/screenshots/](docs/screenshots/). For example: [dashboard](docs/screenshots/dashboard.png), [OCR review](docs/screenshots/review.png), [mobile approvals](docs/screenshots/mobile_approvals.png), [variance](docs/screenshots/variance.png).

## Tech stack

| Layer | Technology |
|---|---|
| Back end | Python 3.11+, Flask, Waitress |
| Database | SQLite (WAL mode), Flask-SQLAlchemy |
| Auth and forms | Flask-Login, PBKDF2 hashing, Flask-WTF with CSRF protection |
| OCR | Tesseract 5, pytesseract, Pillow, pdf2image with a pypdfium2 fallback |
| Front end | HTML, CSS, vanilla JavaScript, Chart.js 4 (bundled locally) |
| Exports | openpyxl, fpdf2 |
| PWA | Web manifest, service worker, IndexedDB |
| Packaging | PyInstaller, NSIS, WinSW |

## Installation

### Development

```bash
git clone https://github.com/The-Institute-of-CA-of-India/Capstone-Project---AICA-Level-2.git
cd "Capstone-Project---AICA-Level-2/AICA-L2-Batch-L2B105-Vivek-Doshi-KnowTaxx-AP-Suite"
pip install -r requirements.txt
python run.py
```

Open http://localhost:5000. On an empty database the app creates the user `admin` with the temporary password `Admin@123`, and forces a change at first login.

**OCR needs Tesseract 5**, which pip cannot install. Choose one:

- Windows: `winget install UB-Mannheim.TesseractOCR`
- Portable: place it in `tools/tesseract/` so that `tools/tesseract/tesseract.exe` exists (this folder is git-ignored)
- Elsewhere: set the `TESSERACT_CMD` environment variable to its full path

Without Tesseract the app still runs, stores files, and asks for fields to be typed in. **Backup & system** shows whether it was found.

### Production (Windows)

1. Run `KnowTaxx_AP_Suite_Server_Setup.exe` on the server: installs the service, opens the firewall port, creates shortcuts.
2. Optionally run `KnowTaxx_AP_Suite_Client_Setup.exe` on client computers: adds a shortcut to the server.

The installers are not stored in this repository. Build them with `python installer/build_installer.py`; its header lists the prerequisites.

### Phones and HTTPS

Browsers allow PWA install and offline mode only on HTTPS or localhost. For phones on your LAN:

```bash
python run.py --https
```

This creates a self-signed certificate for the server's LAN IP. Phones show a warning the first time, and iOS requires installing and trusting the certificate. A certificate from your own CA avoids the warning. All online features work over plain HTTP.

## Quick start

1. Load demo data (optional): `python scripts/seed_demo_data.py`
2. Sign in and create a client under **Clients → New client**
3. Share the vendor registration link from the client overview
4. Upload an invoice, for example from `tests/sample_invoices/`, and review the OCR result
5. Add an approval rule, submit the invoice, approve it, and open the dashboard

### Demo accounts (after seeding)

| Username | Password | Role | Clients |
|---|---|---|---|
| admin | Admin@123 | Admin | All |
| accountant1 | Demo@1234 | Accountant | C0001, C0002 |
| accountant2 | Demo@1234 | Accountant | C0002, C0003 |
| approver1 | Demo@1234 | Approver | Own queue |
| field1 | Demo@1234 | Field staff | C0001, C0002, C0003 |

These are for demonstration only. Do not seed a production system. For real use, start from an empty database.

## Project structure

```
app/
  auth/ clients/ vendors/ invoices/ approvals/   feature modules
  email_listener/ reports/ admin/ api/
  models.py  utils.py                            data model, shared helpers
  static/ templates/                             front end, PWA files
docs/          User Guide, Quick Start, screenshots (sources in docs/src/)
presentation/  Capstone slideshow (source in presentation/src/)
installer/     PyInstaller and NSIS packaging, WinSW service
scripts/       demo data, sample invoices, OCR benchmark, screenshots, doc build
tests/         pytest suite and sample invoices
```

## API

All routes return JSON and need a signed-in session cookie, except `/api/health`. Requests that change data need an `X-CSRFToken` header from `GET /api/csrf`.

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | `{status: "ok", version: "1.0.0"}` |
| POST | `/api/sync` | Apply a batch of offline actions (safe to retry) |
| GET | `/api/clients/<id>/invoices?status=` | Invoice list |
| GET | `/api/clients/<id>/invoices/pending` | Pending approvals |
| POST | `/api/clients/<id>/invoices` | Create an invoice (multipart, `file`) |
| PATCH | `/api/invoices/<id>/approve` | Approve |
| PATCH | `/api/invoices/<id>/reject` | Reject, with `{"reason": "..."}` |
| GET | `/api/clients/<id>/vendors` | Vendor list |
| GET | `/api/clients/<id>/dashboard` | Dashboard KPIs |
| GET | `/api/bootstrap`, `/api/csrf` | PWA offline cache and CSRF token |

## Testing

```bash
pip install -r requirements.txt
python scripts/generate_sample_invoices.py
python -m pytest tests
python scripts/ocr_benchmark.py
```

End-to-end browser checks, which also regenerate the screenshots (needs `pip install playwright` and Microsoft Edge):

```bash
python scripts/capture_screenshots.py
```

After changing docs or screenshots, rebuild with `python scripts/build_docs.py --repo-url <your repository URL>` (the QR code needs `pip install qrcode`).

## Configuration

Environment variables: `KTAP_HOST`, `KTAP_PORT`, `KTAP_DATA_DIR`, `KTAP_SECRET_KEY`, `TESSERACT_CMD`. See [config.py](config.py).

The database and uploaded files live in `instance/` and `data/`, and both are git-ignored. Keep `instance/secret_key.txt` safe: without it, saved mail passwords cannot be decrypted.

## Contributing

1. Fork the repository and create a feature branch.
2. Add tests for your change, and make sure `python -m pytest tests` passes.
3. Never commit real invoices, vendor data, credentials, or the `instance/` and `data/` folders.
4. Open a pull request describing the change and why it is needed.

## License

[MIT](LICENSE)

## Credits

Built as a capstone project for the ICAI AI Committee Level 2 course (AICA Level 2, batch L2B105) by CA Vivek Doshi, KnowTaxx Consultancy.
