# KM Trading: Fruits & Vegetables Branch Receiving & Variance Control

A mobile-friendly full-stack web app (installable PWA) that records fruits and vegetables transferred from the Central Warehouse to KM Trading's 10 Oman branches, compares what was sent with what was actually received, and gives management a same-day view of shortages, wastage and weight loss.

> **Symbol of Confidence**: KM Trading, Oman

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Key Features](#key-features)
3. [Tech Stack](#tech-stack)
4. [Roles & Access](#roles--access)
5. [Inputs](#inputs)
6. [How It Works (Process)](#how-it-works-process)
7. [Outputs & Reports](#outputs--reports)
8. [Security](#security)
9. [Database Schema](#database-schema)
10. [Scope Constraints](#scope-constraints)
11. [Getting Started](#getting-started)
12. [Project at a Glance](#project-at-a-glance)

---

## Problem Statement

Fresh produce moving from the Central Warehouse to 10 retail branches (Al Amerat, Ruwi, Salalah and others) suffers physical shortages, bruising, spoilage and moisture weight loss in transit. Before this system:

| # | Gap | Impact |
|---|-----|--------|
| 1 | **Unmonitored shrinkage** | Transit loss hid inside branch inventory adjustments. |
| 2 | **Delayed paper and spreadsheet reconciliation** | Head Office could not catch repeated receiving mistakes on the same day. |
| 3 | **No variance accountability** | No root-cause classification or financial value for each unit lost. |
| 4 | **Mutable history and price drift** | Daily price changes or reopened sheets could alter past variance figures. |
| 5 | **Weak branch isolation and device security** | Branches needed fast mobile access to their own outlet only; managers needed cross-branch analytics. |

## Key Features

- **Daily receiving ledger** with live calculation of difference quantity, transferred value, received value and difference value.
- **Mandatory reason** for every non-zero difference; save is blocked without one.
- **Color-coded rows:** Shortage (red), Excess (orange), Exact Match (green).
- **Mandatory unit price** per row, highlighted in light red for manual verification.
- **Immutable snapshots** of barcode, product name, unit, category and price on every saved row.
- **Day-end locking:** past dates lock automatically; only Admin can reopen, with an audited reason.
- **Variance monitoring dashboard** with configurable alert threshold (default 5%).
- **Daily, consolidated and monthly reports** with date, branch, product and reason filters.
- **Export to PDF, Excel (.xlsx), CSV and Print**, plus a branded landscape A4 print preview with three signature blocks.
- **Master data upload** (Excel or CSV) with row-by-row validation and a failed-rows report.
- **Full audit log** of data and authentication events with old/new JSON diffs.
- **Installable PWA** with service-worker caching.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Tailwind CSS v4, Lucide Icons |
| Exports | SheetJS (xlsx), jsPDF + jspdf-autotable |
| PWA | VitePWA service worker |
| Backend | Node.js, Express |
| Database | SQLite via better-sqlite3 (WAL mode) |
| Testing | Automated branch-isolation and authentication security tests |

## Roles & Access

The seeded data contains **3 role tiers and 12 accounts** (Admin, Manager and one login per branch).

| Role | Can do |
|------|--------|
| **Admin** | Manage master data, branches, reasons and users; upload master data; select any branch; close a day; **reopen a locked day**; configure the alert threshold; view the audit log. |
| **Manager** | View cross-branch reports and the dashboard; close a day; print and sign off. |
| **Branch user** | Enter and edit receiving rows for **their own branch only**, while the day is Open. |

Branch isolation is enforced **server-side** on every receiving and report API, not just in the UI.

## Inputs

All transaction data is typed manually. There is no scanner.

| Stage | Actor | Format | Captured fields |
|-------|-------|--------|-----------------|
| **1. Master data and catalog** | Admin | Excel (.xlsx), CSV or form | `barcode`, `product_name`, `unit` (kg / pcs / pack), `default_price`, `category` (Fruit / Vegetable), `active`, plus branches, reasons and staff accounts |
| **2. Authentication** | Admin / Manager / Branch user | Credentials or 30-minute reset token | username or email, password (8+ chars with a letter and a number), `rememberMe`, server-bound `branch_id` |
| **3. Daily receiving row** | Branch receiver / Admin | Keyboard entry | `entry_date`, `branch_id`, `document_number` (GRN), `barcode`, `product_id`, `unit`, `transferred_qty`, `received_qty`, mandatory `unit_price`, optional value override, `reason_id`, remarks |
| **4. Day lock and governance** | Manager / Admin | Workflow action plus audit note | Close Day, Admin Reopen reason (min 3 chars), `alert_threshold_pct` (default 5%) |

Default variance reasons: *Shortage*, *Wastage or damage*, *Weight loss or drying*, *Quality rejection*, *Wrong item sent*, *Other*.

## How It Works (Process)

The Express API and SQLite database run every transfer row through a five-stage pipeline:

1. **Catalog resolution and snapshotting.** Typing a barcode resolves the active product, unit and default price (or lets staff quick-create a new SKU inline). On save, barcode, name, unit and category are written as immutable snapshots onto `receiving_items`.
2. **Deterministic variance and value calculation.** Quantities round to 3 decimals and currency to 2.
3. **Server-side validation and branch isolation.** Rejects missing unit prices, non-zero differences without an active reason, access to another branch's `branch_id`, and edits on locked dates.
4. **Day-end locking and audit trail.** Closing a date records `locked` in `daily_lock`. Every CREATE, UPDATE, DELETE, LOCK_DAY, REOPEN_DAY, MASTER_UPLOAD and auth action stores old/new JSON diffs in `audit_log`.
5. **Multi-branch aggregation and threshold alerting.** SQL rollups per branch, product, reason and day, flagging any entry or branch whose absolute Loss % exceeds the Admin threshold.

### Formulas

```
Difference Qty      = Transferred Qty - Received Qty
Transferred Value   = Transferred Qty x Unit Price
Received Value      = Received Qty x Unit Price
Difference Value    = Difference Qty x Unit Price      (or manual override)
Loss %              = (Difference Qty / Transferred Qty) x 100
Alert               = |Loss %| > alert_threshold_pct
```

### Worked example

Onion, 10 kg transferred, 8 kg received, unit price 2.50, threshold 5%:

| Result | Value |
|--------|-------|
| Classification | Shortage |
| Difference Qty | 2 |
| Transferred / Received Value | 25.00 / 20.00 |
| Difference Value (loss) | 5.00 |
| Loss % | 20.00% (alert triggered) |
| Reason | Mandatory; save blocked without it |

## Outputs & Reports

| Output | Audience | Description |
|--------|----------|-------------|
| **Color-coded daily receiving ledger** | Branch staff, Admin | Live entry table with inline edit/delete while the day is Open. |
| **Branded print preview** | Branch Incharge, Management | Landscape A4 sheet with KM Trading logo, document totals, variance breakdown, and Prepared / Branch Incharge / Management signature lines. |
| **Variance monitoring dashboard** | Head Office | Today's total loss value, branches ranked by loss %, threshold breaches, top repeated shortage products (30 days) and top reasons. |
| **Daily, consolidated and monthly reports** | Finance, Operations | Per branch, per product, per reason and per day, filterable, exported to PDF, XLSX, CSV or print. |
| **Audit log and upload validation report** | Admin | Searchable compliance log, bulk-upload counts (added / updated / failed) and a downloadable failed-rows sheet. |

## Security

- Passwords hashed with **PBKDF2-SHA512**; policy of 8+ characters with at least one letter and one number.
- **HttpOnly cookies** and Bearer tokens for sessions.
- **5-attempt, 15-minute lockout** after failed sign-ins.
- **Forced password change** when a temporary password is issued.
- **Forgot Password** request workflow with **30-minute, one-time reset links**.
- **Remember Me** vs. **30-minute idle timeout** for shared devices.
- Strict **server-side RBAC and branch isolation**, covered by an automated test suite.

## Database Schema

SQLite in WAL mode, 13 relational tables:

`branches` · `users` · `products` · `reasons` · `receiving_documents` · `receiving_items` · `daily_lock` · `settings` · `master_upload_log` · `audit_log` · `password_reset_requests` · `password_reset_tokens` · `sessions`

Seeded data: **10 branches**, **762 produce SKUs** (kg, pcs and pack), the default reasons, and the 12 starter accounts.

## Scope Constraints

- **No barcode scanning** (no camera scanner or scanner integration).
- **No document, PDF or image attachments** on transactions.
- All transaction data is typed by hand.
- The **only file upload** is Master Data Upload (Excel .xlsx or CSV).
- Master price edits apply to **new entries only**; locked reports keep their saved snapshot prices.
- Products can be deleted **only if they have zero transactions**.

## Getting Started

> Adjust the commands below to match the scripts in this repository's `package.json`.

```bash
# 1. Clone
git clone https://github.com/anzansar0-coder/miniature-goggles.git
cd miniature-goggles

# 2. Install dependencies
npm install

# 3. Start the app (API + frontend)
npm run dev
```

On first run the database is created and seeded with the branches, product catalog, reasons and starter accounts. Change all seeded passwords on first sign-in; temporary passwords force a rotation.

## Project at a Glance

| | |
|---|---|
| **Branches** | 10, strictly isolated per login |
| **Seeded SKUs** | 762 |
| **Database tables** | 13 (WAL mode, with audit log) |
| **Role tiers / accounts** | 3 / 12 |
| **Default alert threshold** | 5% (Admin-configurable) |
| **Export formats** | PDF, XLSX, CSV, Print |

---

© KM Trading, Oman. Internal operations software.
