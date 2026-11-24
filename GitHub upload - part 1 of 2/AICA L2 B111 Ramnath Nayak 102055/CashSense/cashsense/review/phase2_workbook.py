"""Builds Phase2_Review_SAMPLE.xlsx from the Phase 2 run results."""
from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .phase1_workbook import NOTE_FONT, _sheet

OK_FILL = PatternFill("solid", fgColor="E2EFDA")
BAD_FILL = PatternFill("solid", fgColor="FCE4D6")


def build(results_file: Path, out_file: Path) -> Path:
    res = json.loads(results_file.read_text(encoding="utf-8"))
    wb = Workbook()
    ws = wb.active
    ws.title = "README"
    cat = res["categories"]
    lines = [
        ("CashSense - Phase 2 review workbook (SAMPLE DATA)", Font(bold=True, size=14)),
        (f"Run at {res['run_at']}  |  AI engine: {res['ai_engine']}", None),
        ("", None),
        ("Results", Font(bold=True)),
    ]
    for r in res["readers"]:
        lines.append((f"{r['account_id']} {r['period']} ({r['format']}): {r['status_text']}", None))
    lines += [
        (f"Categories ({cat['scope']}): {cat['score']['category_correct']}/{cat['score']['lines']} correct "
         f"({cat['score']['category_accuracy']:.1%}); counterparties {cat['score']['party_correct']}/"
         f"{cat['score']['lines']}; source: {cat['ai']} by AI, {cat['rules']} by rules; "
         f"{cat['review']} sent to review.", None),
        ("", None),
        ("Sheets", Font(bold=True)),
        ("Reader Results - one row per rendered statement file, with checks, issues and any balance-proven repairs.", None),
        ("Line Check - every line read vs the answer key (green = exact).", None),
        ("Categories - March 2026 lines: true vs assigned category and counterparty, source, review flags.", None),
        ("Accuracy - by category.  Review Queue - lines a human must look at.", None),
        ("", None),
        ("Answer key files are used only to measure the agents; the agents never see them.", NOTE_FONT),
    ]
    if res.get("ai_note"):
        lines.append((res["ai_note"], Font(bold=True, color="C00000")))
    for text, font in lines:
        ws.append([text])
        if font:
            ws.cell(ws.max_row, 1).font = font
    ws.column_dimensions["A"].width = 130

    _sheet(wb, "Reader Results", ["Account", "Period", "Format", "Files", "Expected lines", "Read lines",
                                  "Exact lines", "Opening OK", "Closing OK", "Account OK", "Status", "Model",
                                  "Issues / repairs"],
           [[r["account_id"], r["period"], r["format"], ", ".join(r["files"]), r.get("expected_lines"),
             r.get("read_lines"), r.get("exact_lines"), r.get("opening_ok"), r.get("closing_ok"), r.get("account_ok"),
             r["status_text"], r.get("model", ""), "; ".join(r.get("issues", []) + r.get("repairs", []))]
            for r in res["readers"]], widths={4: 45, 11: 30, 13: 80})

    lc = _sheet(wb, "Line Check", ["File", "Line", "Expected description", "Read description", "Expected amount",
                                   "Read amount", "Exact", "Failed checks"],
                [[f"{r['account_id']} {r['period']}", row["n"], row["expected"], row["read"], row["expected_amount"],
                  row["read_amount"], "yes" if row["ok"] else "NO", ", ".join(row["failed"])]
                 for r in res["readers"] for row in r.get("rows", [])], num_cols=(5, 6), widths={3: 60, 4: 60})
    for i in range(2, lc.max_row + 1):
        lc[f"G{i}"].fill = OK_FILL if lc[f"G{i}"].value == "yes" else BAD_FILL

    cs = _sheet(wb, "Categories", ["Line", "Date", "Description", "Amount", "True category", "Assigned",
                                   "Source", "True party", "Assigned party", "Category OK", "Party OK", "Review",
                                   "Reason / flags"],
                [[c["line_id"], c["date"], c["description"], c["amount"], c["truth"], c["category"], c["source"],
                  c["truth_party"], c["party_id"] or "", "yes" if c["truth"] == c["category"] else "NO",
                  "yes" if c["truth_party"] == (c["party_id"] or "") else "NO", c["review_status"], c["reason"]]
                 for c in cat["lines"]], num_cols=(4,), widths={3: 62, 13: 80})
    for i in range(2, cs.max_row + 1):
        for col in ("J", "K"):
            cs[f"{col}{i}"].fill = OK_FILL if cs[f"{col}{i}"].value == "yes" else BAD_FILL

    _sheet(wb, "Accuracy", ["True category", "Lines", "Correct", "Accuracy"],
           [[k, v["lines"], v["correct"], round(v["correct"] / v["lines"], 4)]
            for k, v in cat["score"]["by_category"].items()], widths={1: 28})

    _sheet(wb, "Review Queue", ["Line", "Date", "Description", "Amount", "Assigned", "Party", "Why it needs a human"],
           [[c["line_id"], c["date"], c["description"], c["amount"], c["category"], c["party_id"] or "",
             "; ".join(c["flags"])] for c in cat["lines"] if c["review_status"] == "review"],
           num_cols=(4,), widths={3: 62, 7: 70})
    out_file.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_file)
    return out_file
