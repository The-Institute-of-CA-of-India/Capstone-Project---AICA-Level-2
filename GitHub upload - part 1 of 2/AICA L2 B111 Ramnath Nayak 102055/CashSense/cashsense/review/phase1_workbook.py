"""Builds Phase1_Review_SAMPLE.xlsx so a CA can inspect the Phase 1 test data in Excel.
Check columns are live Excel formulas, so the workbook proves itself when opened."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

NUM = "#,##0.00"
HEAD_FILL = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(bold=True, color="FFFFFF")
NOTE_FONT = Font(italic=True, color="7F7F7F")


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _num(v: str):
    return float(v) if v not in ("", None) else None


def _sheet(wb: Workbook, title: str, header: list[str], rows: list[list], num_cols=(), widths=None):
    ws = wb.create_sheet(title)
    ws.append(header)
    for c in ws[1]:
        c.fill, c.font = HEAD_FILL, HEAD_FONT
    for r in rows:
        ws.append(r)
    for col in num_cols:
        for cell in ws.iter_cols(min_col=col, max_col=col, min_row=2):
            for c in cell:
                c.number_format = NUM
    for i, h in enumerate(header, 1):
        default = 20 if i in num_cols else max(12, min(45, len(h) + 4))
        ws.column_dimensions[get_column_letter(i)].width = (widths or {}).get(i, default)
    ws.freeze_panes = "A2"
    return ws


def build(data_dir: Path, out_file: Path) -> Path:
    company = json.loads((data_dir / "company.json").read_text(encoding="utf-8"))
    accounts = _rows(data_dir / "bank_accounts.csv")
    index = _rows(data_dir / "statement_index.csv")
    key = json.loads((data_dir / "answer_key" / "recon_items_2026-03-31.json").read_text(encoding="utf-8"))
    risks = json.loads((data_dir / "answer_key" / "risk_flags.json").read_text(encoding="utf-8"))

    wb = Workbook()
    ws = wb.active
    ws.title = "README"
    lines = [
        ("CashSense - Phase 1 review workbook (SAMPLE DATA)", Font(bold=True, size=14)),
        (f"Company: {company['name']}  |  FY {company['fy_start']} to {company['fy_end']}", None),
        ("All names, account numbers and IFSC codes are fictitious. IFSC bank codes start with ZZ.", NOTE_FONT),
        ("", None),
        ("What to check", Font(bold=True)),
        ("1. Statement Summary: every 'Check' cell is 0 and every 'Continuity' cell says OK.", None),
        ("2. BRS 31-Mar-2026: each account shows 'Agreed' (books + reconciling items = bank).", None),
        ("3. Answer Key sheets: the deliberate differences and risk items the agents must find in Phases 3-4.", None),
        ("4. Masters, books and bank lines: look realistic for an auto-component manufacturer in Pune.", None),
        ("", None),
        ("Sheets", Font(bold=True)),
        ("Company & Accounts, Counterparties, Statement Summary, Bank Lines, Book Entries, GST ITC on Bank Charges,", None),
        ("Bank Holidays, BRS 31-Mar-2026, Key - Recon Items, Key - Risk Flags, AR Open, AP Open, Commitments.", None),
        ("EF01 is a USD EEFC account: its statement, books and BRS are in USD; book entries also carry the INR value.",
         NOTE_FONT),
        ("", None),
        ("The answer key is never loaded into the app; it is used only to measure the agents.", NOTE_FONT),
    ]
    for text, font in lines:
        ws.append([text])
        if font:
            ws.cell(ws.max_row, 1).font = font
    ws.column_dimensions["A"].width = 110

    acc_cols = ["account_id", "name", "account_type", "currency", "bank_name", "ifsc", "account_no",
                "opening_balance_minor", "limit_minor", "interest_rate", "min_balance_minor", "statement_format"]
    _sheet(wb, "Company & Accounts", ["Account", "Name", "Type", "Currency", "Bank", "IFSC", "Account no", "Opening",
                                      "Limit", "Rate %", "Min balance", "Statement format"],
           [[a[c] if "minor" not in c else int(a[c]) / 100 for c in acc_cols] for a in accounts],
           num_cols=(8, 9, 11), widths={2: 32, 5: 32})

    parties = _rows(data_dir / "counterparties.csv")
    _sheet(wb, "Counterparties", list(parties[0].keys()), [list(p.values()) for p in parties], widths={3: 48})

    # statement summary with live checks
    ss = _sheet(wb, "Statement Summary", ["Account", "Period", "Opening", "Debits", "Credits", "Closing", "Lines",
                                          "Check (should be 0)", "Continuity", "Currency"],
                [[r["account_id"], r["period"], _num(r["opening"]), _num(r["debits"]), _num(r["credits"]),
                  _num(r["closing"]), int(r["line_count"]), None, None, r["currency"]] for r in index],
                num_cols=(3, 4, 5, 6, 8))
    for i in range(2, ss.max_row + 1):
        ss[f"H{i}"] = f"=ROUND(C{i}-D{i}+E{i}-F{i},2)"
        ss[f"H{i}"].number_format = NUM
        ss[f"I{i}"] = f'=IF(A{i}<>A{i - 1},"OK (first month)",IF(ROUND(F{i - 1}-C{i},2)=0,"OK","BREAK"))' if i > 2 \
            else '="OK (first month)"'

    bank_rows = []
    for r in index:
        for j, line in enumerate(_rows(data_dir / r["file"]), 1):
            bank_rows.append([f"{r['account_id']}-{r['period'].replace('-', '')}-{j:04d}", r["account_id"],
                              line["txn_date"], line["description"], line["ref_no"], _num(line["debit"]),
                              _num(line["credit"]), _num(line["balance"])])
    _sheet(wb, "Bank Lines", ["Line ID", "Account", "Date", "Description", "Ref", "Debit", "Credit", "Balance"],
           bank_rows, num_cols=(6, 7, 8), widths={4: 70, 5: 20})

    books = _rows(data_dir / "book_entries.csv")
    _sheet(wb, "Book Entries", ["Entry", "Voucher", "Type", "Date", "Account", "Counter ledger", "Party",
                                "Narration", "Amount (+ in / - out)", "Mode", "Instrument", "Currency", "INR amount"],
           [[b["entry_id"], b["voucher_no"], b["voucher_type"], b["entry_date"], b["account_id"], b["counter_ledger"],
             b["party_id"], b["narration"], _num(b["amount"]), b["mode"], b["instrument_no"], b["currency"],
             _num(b["inr_amount"])] for b in books],
           num_cols=(9, 13), widths={6: 50, 8: 50})

    # GST input tax credit on bank charges, by month (from the books)
    itc: dict[str, list[float]] = {}
    for b in books:
        month = b["entry_date"][:7]
        if b["counter_ledger"] == "Bank Charges":
            itc.setdefault(month, [0.0, 0.0])[0] += -float(b["inr_amount"])
        elif b["counter_ledger"].startswith("Input GST on bank charges"):
            itc.setdefault(month, [0.0, 0.0])[1] += -float(b["inr_amount"])
    gs = _sheet(wb, "GST ITC on Bank Charges", ["Month", "Charges booked (Rs)", "GST booked = ITC (Rs)",
                                                 "GST % (should be 18)"],
                [[m, round(v[0], 2), round(v[1], 2)] for m, v in sorted(itc.items())], num_cols=(2, 3))
    for i in range(2, gs.max_row + 1):
        gs[f"D{i}"] = f"=IF(B{i}=0,0,ROUND(C{i}/B{i}*100,2))"
    gs.cell(gs.max_row + 2, 1, "March 2026 charges and GST are not yet booked (seeded difference); the "
                               "reconciliation in Phase 3 should surface them so the ITC is not missed.").font = NOTE_FONT

    hol = _rows(data_dir / "bank_holidays.csv")
    _sheet(wb, "Bank Holidays", ["Date", "Holiday (illustrative, Maharashtra)"], [[h["date"], h["holiday"]] for h in hol],
           widths={2: 45})

    # BRS with formulas
    brs = wb.create_sheet("BRS 31-Mar-2026")
    brs.column_dimensions["A"].width = 34
    brs.column_dimensions["B"].width = 24
    brs.column_dimensions["C"].width = 14
    brs.column_dimensions["D"].width = 20
    row = 1
    brs.cell(row, 1, "Bank reconciliation as at 31-Mar-2026 (SAMPLE)").font = Font(bold=True, size=13)
    row += 2
    for aid, rec in key.items():
        brs.cell(row, 1, f"{aid} - {next(a['name'] for a in accounts if a['account_id'] == aid)} "
                         f"(amounts in {rec['currency']})").font = Font(bold=True)
        row += 1
        brs.cell(row, 1, "Balance as per books")
        brs.cell(row, 4, float(rec["balance_per_books"])).number_format = NUM
        books_row = row
        row += 1
        first = row
        for item in rec["items"]:
            brs.cell(row, 1, item["category"].replace("_", " "))
            brs.cell(row, 2, item.get("line_id") or item.get("voucher_no") or "")
            brs.cell(row, 3, item["date"])
            brs.cell(row, 4, float(item["adjust_to_reach_bank"])).number_format = NUM
            row += 1
        last = row - 1
        brs.cell(row, 1, "Computed balance as per bank").font = Font(bold=True)
        brs.cell(row, 4, f"=D{books_row}+SUM(D{first}:D{last})").number_format = NUM
        comp = row
        row += 1
        brs.cell(row, 1, "Closing balance per bank statement")
        brs.cell(row, 4, float(rec["balance_per_bank"])).number_format = NUM
        actual = row
        row += 1
        brs.cell(row, 1, "Status").font = Font(bold=True)
        brs.cell(row, 4, f'=IF(ROUND(D{comp}-D{actual},2)=0,"Agreed","CHECK")').font = Font(bold=True)
        brs.cell(row, 4).alignment = Alignment(horizontal="right")
        row += 3

    items = [[aid, i["category"], i["side"], i.get("line_id", ""), i.get("entry_id", ""), i["date"],
              _num(i.get("amount") or i.get("bank_amount")), _num(i["adjust_to_reach_bank"]), i["tag"]]
             for aid, rec in key.items() for i in rec["items"]]
    _sheet(wb, "Key - Recon Items", ["Account", "Category", "Side", "Bank line", "Book entry", "Date", "Amount",
                                     "Adjustment to reach bank", "Tag"], items, num_cols=(7, 8), widths={2: 32})
    _sheet(wb, "Key - Risk Flags", ["Flag", "Type", "Party", "Line / bill", "Why"],
           [[r["flag_id"], r["type"], r["party_id"],
             r.get("line_id") or r.get("bill_no") or ", ".join(x["line_id"] for x in r.get("lines", [])), r["why"]]
            for r in risks], widths={2: 34, 4: 30, 5: 100})

    for name, fname in (("AR Open", "ar_open.csv"), ("AP Open", "ap_open.csv"), ("Commitments", "commitments.csv")):
        rows = _rows(data_dir / fname)
        hdr = list(rows[0].keys())
        amt_col = hdr.index("amount") + 1
        _sheet(wb, name, hdr, [[_num(v) if k == "amount" else v for k, v in r.items()] for r in rows],
               num_cols=(amt_col,), widths={hdr.index(h) + 1: 50 for h in hdr if h in ("note", "description")})

    out_file.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_file)
    return out_file
