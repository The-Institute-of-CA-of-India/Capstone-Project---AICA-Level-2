# Investor Manager

An offline Windows application for Indian investors and their Chartered Accountants. It reads broker
contract notes, works out the cost of every script held, values the holdings at market prices, reconciles
them with holding statements and Tally, and posts the entries to Tally Prime.

Everything runs on your own computer. No data leaves it, except the downloads you ask for (security
masters, market prices, broker portals).

Developed by **CA Atul Mathuria**, Mumbai.

## What it does

- **Reads contract notes** from IIFL, Zerodha, PhillipCapital and Kotak: PDF (including password-protected
  ones), scanned images (OCR), HTML, Excel and ZIP files. Every note is checked against its printed net
  amount before it is saved, and the same note, trade or file can never be saved twice.
- **Allocates charges** (brokerage, STT, stamp duty, exchange and SEBI fees, GST) to each script, keeps
  purchases and sales of the same day separate, and keeps cost in whole rupees.
- **Investment statement**: every script held, with quantity, FIFO cost, market price, market value and
  gain or loss in rupees and %, on any date. The Dashboard shows the totals and charts first.
- **Opening holdings** from your own Excel sheet, with PAN and ISIN found automatically. When a sale has
  no purchase on record, the app adds an "Assumed" past purchase so that cost can still be worked out.
- **Masters and prices**: BSE, NSE, Nifty and AMFI lists (names, ISIN, industry), NSE / BSE closing prices
  (bhavcopy), AMFI NAVs, live prices from Yahoo Finance, and the grandfathering FMV of 31-Jan-2018.
- **Reconciliations**: contract notes against their printed totals, holdings against a holding statement,
  and FIFO cost against Tally ledger balances.
- **Tally Prime**: imports your ledger names and matches each script to its ledger even when the names
  differ (TATATECH = "Tata Tech"), creates missing ledgers after asking you, and sends one voucher per
  contract note: purchases at cost, sales at FIFO cost with short or long term gain, and the broker's net amount.
- **Reports and exports** in Excel, PDF, CSV, JSON and XML.
- **Data care**: weekly backups with restore, clean-up of source files, and a Delete Data screen with undo.

See [docs/How to use Investor Manager.md](docs/How%20to%20use%20Investor%20Manager.md) for every screen.

## Download and run (no Python needed)

1. Open **Releases** on the right of this page and download the latest version: the
   `Investor Manager_vX.Y.exe` file and the `App Files` zip.
2. Put the exe and the `App Files` folder (unzipped) together in one folder.
3. Double-click the exe. The first run takes a minute or two while it sets itself up. Your data is kept
   in a `Data` folder next to the exe.

If Windows shows "Windows protected your PC", click **More info** and then **Run anyway**.

## For developers

The app is pure Python:

- **Screens**: [NiceGUI](https://nicegui.io) (Quasar and Vue in a browser window), AG Grid tables and
  ECharts charts, shown in an Edge or Chrome app window.
- **Behind the screens**: a local NiceGUI / FastAPI server on 127.0.0.1, a SQLite database, pandas,
  pdfplumber, pdfminer and pypdfium2 for PDFs, Tesseract OCR, openpyxl and ReportLab for reports, and the
  Tally XML interface on port 9000.
- **Launcher**: a small C program (`launcher/launcher.c`) that unpacks the bundled Python the first time
  and then starts the app without a console window.

To run from source:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app\run.py
```

Scanned contract notes need [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) installed;
set `CNM_TESSERACT` to the path of `tesseract.exe`. See [BUILDING.md](BUILDING.md) to build the exe and
the release files.

### Folder layout

| Folder | What it holds |
|---|---|
| `app/run.py` | Starts the local server and the app window; one copy at a time |
| `app/cnm_ui.py` | All the screens |
| `app/cn_app/` | Reading notes (`extract.py`, `parsers/`), charges (`allocate.py`), database (`store.py`), FIFO (`fifo.py`), prices, masters, reconciliations, Tally (`tally_*.py`), backups and more |
| `launcher/` | Source of the Windows launcher exe |
| `installer/` | `setup.cmd` (first-run setup) and the Start .bat |
| `docs/` | User guide |

## Privacy

Never commit a `Data` folder, contract notes, holding statements or Tally exports: they hold PANs and
client details. The `.gitignore` keeps them out.

## Licence

MIT: free to use, copy, change and share, keeping the copyright notice. See [LICENSE](LICENSE).
The software comes without any warranty; check figures before relying on them for tax or accounts.

## Contact

CA Atul Mathuria, Mumbai. Email: atul@atulmathuria.com
