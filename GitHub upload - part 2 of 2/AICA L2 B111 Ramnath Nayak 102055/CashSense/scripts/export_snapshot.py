"""Export a read-only snapshot of the whole CashSense database for the ICAI reviewers - no password needed.

    python scripts/export_snapshot.py

Writes:
  database_snapshot/CashSense_Database_Snapshot.xlsx   one sheet per table + a README sheet with row counts
  data/db_snapshot/<table>.csv                          the same tables as CSV (packed into data.zip)

Only data is exported - no keys, passwords or connection details. Amount columns ending in _minor / _paise are
integers in paise (INR) or cents (USD); the workbook adds a rupee/dollar column next to each for reading.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cashsense import config  # noqa: E402
from cashsense.db import get_database  # noqa: E402
from cashsense.db.adapter import TABLES  # noqa: E402

XLSX = ROOT / "database_snapshot" / "CashSense_Database_Snapshot.xlsx"
CSV_DIR = ROOT / "data" / "db_snapshot"
DESCRIPTIONS = {
    "company": "The SAMPLE company and its approval limit",
    "bank_accounts": "Four bank accounts (current, cash credit, collections, EEFC USD)",
    "counterparties": "Vendors, customers and statutory payees (master data)",
    "bank_holidays": "Illustrative Maharashtra bank holidays",
    "book_entries": "Bank ledger entries in the books, incl. entries posted after the CA's approval (APPROVED-JV)",
    "statement_imports": "Each imported bank statement: format, status, issues",
    "bank_lines": "Every bank statement line with its category, counterparty, confidence and review status",
    "ar_open": "Open customer invoices",
    "ap_open": "Open supplier bills (MSME flag for sec 43B(h))",
    "commitments": "Known future payments and receipts used by the forecast",
    "recon_links": "Bank line <-> book entry matches (automatic and approved)",
    "recon_runs": "Each reconciliation run with book / bank balances and status",
    "recon_items": "Reconciling items with Gemini explanations and proposed entries",
    "risk_flags": "Risk Sentinel flags with severity, evidence, explanation and the CA's decision",
    "approvals": "Approval cards sent to Telegram and the CA's decisions",
    "app_state": "Small app settings (Telegram position, cached forecast commentary)",
    "audit_log": "Audit trail of every run, import, decision and sign-in",
}
MAX_CELL = 32000  # Excel's cell limit is 32,767 characters


def private_values() -> list[str]:
    """Values from .env that must never leave the laptop (keys, tokens, secrets, passwords, chat ID, URLs)."""
    env = ROOT / ".env"
    out = []
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                if any(s in k for s in ("KEY", "TOKEN", "SECRET", "PASSWORD", "CHAT_ID", "SUPABASE_URL",
                                        "APPS_SCRIPT_URL")) and len(v.strip()) >= 6:
                    out.append(v.strip())
    return out


def redact(value, secrets: list[str]):
    if isinstance(value, str):
        for s in secrets:
            if s in value:
                value = value.replace(s, "[redacted]")
    return value


def main() -> None:
    db = get_database()
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    readme = wb.active
    readme.title = "README"
    stamp = config.now_ist().strftime("%d-%b-%Y %H:%M IST")
    readme.append(["CashSense - database snapshot (SAMPLE DATA)"])
    readme["A1"].font = Font(bold=True, size=14)
    readme.append([f"Exported {stamp} from the live CashSense database ({config.db_backend()}). Read-only copy; "
                   "no passwords, keys or connection details are included; private values are shown as [redacted]."])
    readme.append(["Amounts ending _minor / _paise are integers in paise (INR) or cents (USD); a readable column "
                   "(ending _amount) is added next to each."])
    readme.append([])
    readme.append(["Sheet / table", "Rows", "What it holds"])
    for c in readme[5]:
        c.font = Font(bold=True)
    counts = {}
    secrets = private_values()
    for table in TABLES:
        rows = [{k: redact(v, secrets) for k, v in r.items()} for r in db.query(table)]
        counts[table] = len(rows)
        cols = list(rows[0].keys()) if rows else []
        with (CSV_DIR / f"{table}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            w.writerows([[r[c] for c in cols] for r in rows])
        ws = wb.create_sheet(table[:31])
        money = [c for c in cols if c.endswith(("_minor", "_paise"))]
        header = []
        for c in cols:
            header.append(c)
            if c in money:
                header.append(c.rsplit("_", 1)[0] + "_amount")
        ws.append(header)
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F3864")
        for r in rows:
            out = []
            for c in cols:
                v = r[c]
                if isinstance(v, str) and len(v) > MAX_CELL:
                    v = v[:MAX_CELL] + " ...[truncated - see CSV]"
                out.append(v)
                if c in money:
                    out.append(round(v / 100, 2) if isinstance(v, (int, float)) else None)
            ws.append(out)
        for i, h in enumerate(header, 1):
            ws.column_dimensions[get_column_letter(i)].width = min(60, max(12, len(h) + 4))
            if h.endswith("_amount"):
                for col in ws.iter_cols(min_col=i, max_col=i, min_row=2):
                    for cell in col:
                        cell.number_format = "#,##0.00"
        ws.freeze_panes = "A2"
        readme.append([table, len(rows), DESCRIPTIONS.get(table, "")])
    readme.column_dimensions["A"].width = 22
    readme.column_dimensions["B"].width = 8
    readme.column_dimensions["C"].width = 110
    wb.save(XLSX)
    print(f"Snapshot: {XLSX}")
    print(f"CSV:      {CSV_DIR}")
    print("Rows:", ", ".join(f"{t} {n}" for t, n in counts.items()))


if __name__ == "__main__":
    main()
