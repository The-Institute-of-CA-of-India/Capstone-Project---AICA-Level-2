# LedgerDesk — local accounting workspace

JavaScript interface + Python processing + SQLite. Built for Windows, Python 3.10 or newer (tested with Python 3.14.8). No third-party packages, pip downloads, Node installation, cloud account, or virtual environment are needed to run it.

## Start

1. Extract the complete LedgerDesk.zip to a normal writable folder. Do not run inside the ZIP.
2. Double-click START_LEDGERDESK.bat.
3. The launcher checks Python and its built-in dependencies, starts the server, and opens your default browser.
4. Keep the launcher window open. If the browser does not open, copy the local address printed in the window (normally http://127.0.0.1:8765).
5. Create your company, choose its base currency and books start date, then add contacts and accounts.
6. To stop, press Ctrl+C in the launcher window. Closing the browser alone does not stop the server.

For a separate fictional sample, double-click TRY_DEMO.bat. Demo books are stored in data/demo.sqlite3. Your own books are stored in data/ledgerdesk.sqlite3. The demo does not write into your own books. The two launchers may select different ports if run together.

If Python is missing, install Python 3.10+ from https://www.python.org/downloads/windows/ and enable Add Python to PATH. Your existing Python 3.14 works. The launcher deliberately does not download or change your Python installation.

## Included workflows

- Create/load separate companies; independent accounts, contacts, transactions, base currency, country, address and tax ID.
- Sales invoices, purchase bills, cash expenses, cash income, asset purchases, receipts, payments, customer credit notes, supplier debit notes, manual journals and opening balances.
- Multi-line documents with quantity, unit price, percentage discount and configurable tax percentage.
- Server-generated journal preview; validated draft saving; separate posting; immutable posted vouchers and dated reversals.
- Customer/supplier contacts, item/price catalogue, and extensible chart of accounts.
- Foreign-currency source invoices and settlements; manual dated transaction rates; partial allocations and realised FX gains/losses.
- Fixed-asset register tied to already-posted account 1500 acquisition costs; residual values; daily straight-line depreciation over calendar-month useful lives; depreciation journals and current NBVs.
- Manual bank reconciliation of selected ledger entries against a statement closing balance.
- Trial balance, P&L, balance sheet, direct cash-movement summary, general ledger, invoice aging, and VAT control-account movement summary.
- Company group management aggregation using one entered translation rate per entity.
- Printable accounting documents and reports (browser Print > Save as PDF), CSV report exports, database backup, forward-only period locking and activity log.

## First company: recommended sequence

1. Set the books start date to your migration date. It is the earliest permitted posting date; it is not a financial-year reset. Reports accept any date range. The base currency and books start date cannot be changed through this version's UI.
2. Add or review the chart of accounts. Cash/bank accounts must be Asset accounts flagged Cash/bank. Default control codes 1100, 1300, 1500, 1590, 2000 and 2100 are used by automatic postings.
3. Enter a balanced Opening balance journal based on an approved migration trial balance. Enter cash funding with the appropriate financing classification. Do not post unbalanced suspense entries to force a migration.
4. Add customer and supplier records. Create invoices/bills as drafts, review journals, and post. Drafts never affect financial reports.
5. Receipts and Payments: choose the original invoice/bill to allocate a payment. Amounts are in that document's currency. Enter the actual settlement exchange rate; the system calculates realised FX. Without a source, the voucher is a direct transaction against the selected counter-account.
6. Credit note means a reduction of a customer invoice; Debit note means a reduction of a supplier bill. Select the matching source and use its original rate. Notes are limited to the unsettled amount. Additional charges use a new invoice/bill; refunds of fully settled invoices require reviewed manual journals in this release.
7. Check the trial balance, balance sheet and cash-flow reconciliation differences. Reconcile AR/AP aging to control-account ledgers and investigate differences.
8. Back up before closing a period; then apply the lock. Locks cannot be moved backwards through the app.

## Accounting assumptions and practical limits

This is a functional first-release accounting application, not a full Tally/Zoho replacement or production-certified multinational ERP. See FEATURE_MATRIX.md for the explicit coverage and development backlog.

Money: integer cents in SQLite, Python Decimal and ROUND_HALF_UP for calculations. Each document line is rounded to two decimals, then its tax is rounded, then those amounts are converted to base currency. Small currencies with zero or three minor-unit decimals are not supported. Several common non-two-decimal currencies are rejected explicitly; you must select a valid two-decimal currency. No live FX feed or period-end revaluation is supplied. Catalogue prices are suggested numbers: adjust prices if entering a foreign-currency document.

Tax: defaults to 0% until you choose a rate. A 5% line is a mathematical calculation, not a determination of the correct tax treatment. Input VAT is assumed fully recoverable; for nonrecoverable tax, include it in cost and use tax 0%. VAT report is a ledger movement summary, not a return or tax-engine validation. No Corporate Tax computation, FTA filing, e-invoicing integration, reverse-charge workflow or statutory certification is included. Validate jurisdiction-specific requirements before external invoice issue.

AR/AP: aging is invoice-level and reflects allocations and reversals as at the report end date. Manual journals into receivable/payable controls do not create aging records. Opening AR/AP invoice migration is not automated. Do not book opening invoices as new sales without an accountant-designed migration offset. Customer/supplier statements, advance allocation and many-to-many allocations are a later phase.

Cash flow: the report reconciles movements in flagged cash/bank accounts using one Operating/Investing/Financing category per voucher. It does not infer categories from accrual transactions, produce an indirect-method statement, or separate an FX effect on cash. Split mixed-category cash vouchers and classify cash transfers consistently. This is a management cash-flow summary, not complete IAS 7 statutory disclosure.

Balance sheet: cumulative unclosed profit/loss is included within equity. No automatic year-end closing journal is posted. Avoid manual profit-closing journals inside a period whose P&L you are reporting without accounting for their impact.

Assets: fixed acquisition cost and residual value; daily straight-line through the chosen date inclusive, capped at depreciable cost. The useful-life interval ends at the same calendar date after the chosen month count. Last-date tracking prevents duplicate depreciation. The first depreciation posting must be after the available-for-use date. The register is current, not a historical snapshot. No disposals, revaluations, impairment, components, pre-migration accumulated depreciation workflow, or asset-policy changes are automated. Depreciation/acquisitions linked to registered assets cannot be reversed using the generic reversal button.

Group overview: translated management aggregation only. One rate per entity is applied to both income and balance-sheet amounts. Same chart codes and account classifications must mean the same thing across companies. No average/closing/historical-rate distinction, translation reserve, intercompany elimination, NCI, ownership, purchase accounting, or IFRS 10/IAS 21 statutory consolidation is performed. Keep consolidation adjustments in a separate reviewed working paper until that module is implemented.

Controls: single trusted operator on one computer. The server binds to 127.0.0.1, validates Host/origin, and requires a per-run request token for APIs. It is not a public or LAN server. No login, multi-user roles, approval segregation, encryption, audit immutability, attachments or document retention workflow is included. Anyone with Windows access to the database can modify it outside the app. Do not put the live database on a shared or synchronised drive. Backups contain all companies and should be protected accordingly.

## Backup and restore

Download a consistent backup from Controls & backup. For restoration:

1. Stop every LedgerDesk launcher/server process.
2. Copy the existing data/ledgerdesk.sqlite3 to a dated safety filename. Keep the original backup separately too.
3. Copy the chosen backup into data and name it ledgerdesk.sqlite3. For demo restoration use demo.sqlite3 instead.
4. Restart, select the company, and verify its latest voucher date, trial balance and control totals.

Never overwrite an open database. Do not restore untrusted database files. This version uses SQLite's default rollback journal, not WAL mode.

## Technical files

- server.py: loopback-only HTTP API and static-file server.
- accounting.py: database schema, double-entry engine, reports and controls.
- static/index.html, app.js, style.css: local JavaScript interface, no CDN dependencies.
- demo.py: fictional isolated demo seed.
- test_accounting.py, test_api.py: independent temporary-database tests.
- test_frontend.cjs and qa/: developer-only render checks; Node is not needed to run LedgerDesk.

Run backend checks with: python -m unittest test_accounting test_api -v
Run frontend syntax check, if Node is installed: node --check static/app.js
Run rendering checks: python -c "exec(open('qa/make_fixture.py',encoding='utf-8-sig').read())" then node test_frontend.cjs

## Validation completed

15 automated backend/API-handler tests passed on Python 3.14.8. They cover posting balance, draft exclusion, duplicate posting, rounding, FX allocations, notes, historical reversals/aging, isolation, period locks, depreciation, reconciliation, group totals, request-token/host checks, backups and static routes. JavaScript syntax passed; 16 view/report unit-render checks, 5 form renders and HTML escaping passed. The demo produces a balanced ledger.

A live browser end-to-end check could not be completed because the build environment blocks local loopback sockets (WinError 10013). Server startup succeeded. API route tests run in-process rather than through network sockets. Perform user acceptance testing in the normal Windows session before relying on real books.

## Design references

Coverage was compared with these official Zoho Books descriptions, accessed 24 October 2026. This is an independent implementation, not affiliated with Zoho or Tally:
- https://www.zoho.com/ae/books/help/settings/
- https://www.zoho.com/in/books/help/reports/
- https://www.zoho.com/uk/books/help/accountant/accountant.html
