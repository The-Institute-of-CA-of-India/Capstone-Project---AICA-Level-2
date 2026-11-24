"""Builds Phase3_Review_SAMPLE.xlsx: BRS with live formulas, matching summary, reconciliation items with
Gemini explanations, approvals, risk register, browser verifications and accuracy against the answer key."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from ..db.adapter import Database
from .phase1_workbook import NOTE_FONT, NUM, _sheet
from .phase2_workbook import BAD_FILL, OK_FILL


def build(db: Database, result: dict, accuracy: dict, out_file: Path) -> Path:
    runs = {r["run_id"]: r for r in db.query("recon_runs")}
    cur = {a["account_id"]: a["currency"] for a in db.query("bank_accounts")}
    names = {a["account_id"]: a["name"] for a in db.query("bank_accounts")}
    run_ids = result["run_ids"]
    items = [i for rid in run_ids for i in db.query("recon_items", {"run_id": rid}, order="item_id")]
    approvals = db.query("approvals", order="approval_id")
    flags = db.query("risk_flags", order="flag_id")

    wb = Workbook()
    ws = wb.active
    ws.title = "README"
    lines = [
        ("CashSense - Phase 3 review workbook (SAMPLE DATA)", Font(bold=True, size=14)),
        (f"As at {result['as_of']}  |  AI: {result['ai'].get('model') or 'not used'}", None),
        ("", None),
        ("Results", Font(bold=True)),
        (f"Reconciliation: {', '.join(r['account_id'] + ' ' + r['status'] for r in result['reconciliations'])}", None),
        (f"Automatic matches: {sum(r['auto_matched_now'] for r in result['reconciliations'])}  |  "
         f"accuracy vs answer key: {accuracy['links_correct']}/{accuracy['links_made']} correct, "
         f"{accuracy['links_missed_non_fuzzy']} true matches missed (excluding the proposed fuzzy match)", None),
        (f"Reconciliation items identical to answer key: {accuracy['items_match']}", None),
        (f"Risk flags: {result['risk_flags']} raised, {accuracy['risks_found']}/{accuracy['risks_expected']} expected found, "
         f"{accuracy['risk_false_positives']} false positives", None),
        (f"Browser verifications: {result['verifications']} accounts, mismatches: "
         f"{', '.join(v['holder'] for v in result['verification_mismatches']) or 'none'}", None),
        (f"Approvals proposed: {len(approvals)} (pending {sum(a['status'] == 'pending' for a in approvals)})", None),
        (f"Gemini ledger disagreements: {len(result['ai'].get('ledger_disagreements', []))}; severities raised: "
         f"{len(result['ai'].get('severity_raised', []))}", None),
        ("", None),
        ("Commentary (Gemini)", Font(bold=True)),
        (result.get("commentary") or "(none)", None),
        ("", None),
        ("Approval rules: exact matches auto-accepted and logged; entries, fuzzy matches and risk flags need the CA's "
         "Telegram approval; nothing is posted without approval.", NOTE_FONT),
    ]
    for text, font in lines:
        ws.append([text])
        if font:
            ws.cell(ws.max_row, 1).font = font
    ws.column_dimensions["A"].width = 140

    # BRS with formulas
    brs = wb.create_sheet("BRS")
    for col, w in zip("ABCDE", (44, 22, 14, 20, 60)):
        brs.column_dimensions[col].width = w
    row = 1
    brs.cell(row, 1, f"Bank reconciliation statements as at {result['as_of']} (SAMPLE)").font = Font(bold=True, size=13)
    row += 2
    for rid in run_ids:
        run = runs[rid]
        aid = run["account_id"]
        brs.cell(row, 1, f"{aid} - {names[aid]} ({cur[aid]})").font = Font(bold=True)
        row += 1
        brs.cell(row, 1, "Balance as per books")
        brs.cell(row, 4, run["book_balance_minor"] / 100).number_format = NUM
        b = row
        row += 1
        first = row
        for i in [x for x in items if x["run_id"] == rid]:
            brs.cell(row, 1, i["category"].replace("_", " "))
            brs.cell(row, 2, i["line_id"] or i["entry_id"])
            brs.cell(row, 3, i["item_date"])
            brs.cell(row, 4, i["adjust_minor"] / 100).number_format = NUM
            brs.cell(row, 5, (i["explanation"] or "")[:200])
            row += 1
        last = row - 1
        brs.cell(row, 1, "Computed balance as per bank").font = Font(bold=True)
        brs.cell(row, 4, f"=D{b}+SUM(D{first}:D{last})" if last >= first else f"=D{b}").number_format = NUM
        comp = row
        row += 1
        brs.cell(row, 1, "Closing balance per bank statement")
        brs.cell(row, 4, run["bank_balance_minor"] / 100).number_format = NUM
        act = row
        row += 1
        brs.cell(row, 1, "Status").font = Font(bold=True)
        brs.cell(row, 4, f'=IF(ROUND(D{comp}-D{act},2)=0,"Agreed","CHECK")').font = Font(bold=True)
        row += 3

    links = db.query("recon_links")
    rules = Counter((lk["account_id"], lk["rule"] or lk["link_type"]) for lk in links)
    _sheet(wb, "Matching", ["Account", "Match rule", "Matches"], [[a, r, n] for (a, r), n in sorted(rules.items())],
           widths={2: 40})

    _sheet(wb, "Recon Items", ["Item", "Account", "Category", "Side", "Bank line", "Book entry", "Date", "Amount",
                               "Adjustment", "Gemini explanation", "Proposed entry / action"],
           [[i["item_id"].rsplit("-", 1)[-1], i["account_id"], i["category"], i["side"], i["line_id"] or "",
             i["entry_id"] or "", i["item_date"], i["amount_minor"] / 100, i["adjust_minor"] / 100, i["explanation"],
             _entry_text(json.loads(i["suggestion"]))] for i in items],
           num_cols=(8, 9), widths={3: 30, 10: 80, 11: 70})

    ap = _sheet(wb, "Approvals", ["Approval", "Kind", "Title", "Status", "Decided by", "Decided at", "Telegram msg"],
                [[a["approval_id"], a["kind"], a["title"], a["status"], a["decided_by"] or "", a["decided_at"] or "",
                  a["channel_message_id"] or ""] for a in approvals], widths={3: 100})
    for r in range(2, ap.max_row + 1):
        if ap[f"D{r}"].value in ("approved", "rejected"):
            ap[f"D{r}"].fill = OK_FILL if ap[f"D{r}"].value == "approved" else BAD_FILL

    _sheet(wb, "Risk Register", ["Flag", "Type", "Severity", "Account", "Lines / bill", "Amount", "Date",
                                 "Explanation (Gemini)", "Recommended action", "Evidence", "Status"],
           [[f["flag_id"], f["flag_type"], f["severity"], f["account_id"] or "",
             ", ".join(json.loads(f["line_ids"])) or f["bill_no"], abs(f["amount_minor"] or 0) / 100, f["flag_date"],
             f["explanation"], f["action"], f["evidence"][:300], f["status"]] for f in flags],
           num_cols=(6,), widths={2: 32, 8: 80, 9: 70, 10: 60})

    vs = _sheet(wb, "Browser Verifications", ["Vendor", "Source", "IFSC", "A/c last 4", "Registered holder",
                                              "Expected", "Match", "Screenshot"],
                [[v["party_id"], v["source"], v["ifsc"], v["account_last4"], v["holder"], v["expected"],
                  "yes" if v["name_match"] else "NO", v["screenshot"]] for v in result["verification_results"]],
                widths={5: 36, 6: 40, 8: 60})
    for r in range(2, vs.max_row + 1):
        vs[f"G{r}"].fill = OK_FILL if vs[f"G{r}"].value == "yes" else BAD_FILL

    _sheet(wb, "Accuracy", ["Measure", "Result"], [[k.replace("_", " "), str(v)] for k, v in accuracy.items()],
           widths={1: 40, 2: 40})
    out_file.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_file)
    return out_file


def _entry_text(s: dict) -> str:
    if s.get("action") == "none":
        return s.get("note", "No entry - timing difference")
    if s.get("action") == "investigate":
        return "Investigate"
    amt = s.get("correction_minor", s.get("bank_amount_minor", 0))
    dr, cr = (s.get("bank_ledger"), s.get("counter_ledger")) if amt > 0 else (s.get("counter_ledger"), s.get("bank_ledger"))
    return f"Dr {dr} / Cr {cr}: {abs(amt) / 100:,.2f} {s.get('currency', '')}"
