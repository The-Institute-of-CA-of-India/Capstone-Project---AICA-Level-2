"""Phase 4 test data: an independent answer key for the forecast's KNOWN flows (computed straight from
the Phase 1 files with the stated rules, not by the Forecaster), and a question bank for the assistant.

Known-flow rules (as stated to the CA):
  * cheques issued but not presented -> as_of + 3 days; deposits not yet credited -> as_of + 2 days
  * receivables on the due date; overdue ones spread over weeks 1-4 (as_of + 4, 11, 18, 25 days), oldest first;
    USD invoices at the latest EEFC conversion rate
  * payables on the due date; overdue MSME bills as_of + 1; other overdue bills as_of + 7; the CNC balance is capex
  * commitments on their date (the capex commitment duplicates the CNC payable and is skipped)
  * scenarios: late_15 moves customer receipts +15 days; top_customer_default drops the customer with the most
    receipts in the horizon (known + run-rate) - so the key stores known flows per party for that check;
    capex_forward moves capex to as_of + 6 days.
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from ..money import to_paise

AS_OF = date(2026, 3, 31)
WEEKS = 13


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _week(d: date) -> int:
    return ((d - AS_OF).days - 1) // 7 + 1


def _rate(p1: Path) -> float:
    rate = 83.0
    for s in _rows(p1 / "statement_index.csv"):
        for ln in _rows(p1 / s["file"]):
            if ln["txn_date"] <= AS_OF.isoformat() and ln["description"].startswith("FX CONV"):
                rate = float(re.search(r"@(\d+\.\d+)", ln["description"]).group(1))
    return rate


def known_flows(p1: Path) -> list[dict]:
    rate = _rate(p1)
    recon = json.loads((p1 / "answer_key" / "recon_items_2026-03-31.json").read_text(encoding="utf-8"))
    flows = []
    for rec in recon.values():
        for i in rec["items"]:
            if i["category"] == "cheque_issued_not_presented":
                flows.append({"date": AS_OF + timedelta(days=3), "amount": to_paise(i["amount"]), "cat": "timing", "party": ""})
            elif i["category"] == "deposit_not_yet_credited":
                flows.append({"date": AS_OF + timedelta(days=2), "amount": to_paise(i["amount"]), "cat": "timing", "party": ""})
    ar = sorted(_rows(p1 / "ar_open.csv"), key=lambda r: (r["due_date"], r["invoice_no"]))
    n = 0
    for r in ar:
        amt = to_paise(r["amount"])
        amt = int(round(amt * rate)) if r["currency"] == "USD" else amt
        due = date.fromisoformat(r["due_date"])
        if due <= AS_OF:
            when = AS_OF + timedelta(days=7 * (n % 4) + 4)
            n += 1
        else:
            when = due
        flows.append({"date": when, "amount": amt, "cat": "customer_receipts", "party": r["party_id"]})
    for b in _rows(p1 / "ap_open.csv"):
        due = date.fromisoformat(b["due_date"])
        when = due if due > AS_OF else AS_OF + timedelta(days=1 if b["msme"] == "1" else 7)
        flows.append({"date": when, "amount": -to_paise(b["amount"]),
                      "cat": "capex" if b["party_id"] == "V017" else "supplier_payments", "party": b["party_id"]})
    for c in _rows(p1 / "commitments.csv"):
        if c["category"] != "capex":
            flows.append({"date": date.fromisoformat(c["due_date"]), "amount": to_paise(c["amount"]),
                          "cat": c["category"], "party": ""})
    return flows


def weekly(flows: list[dict]) -> dict[int, int]:
    out = defaultdict(int)
    for f in flows:
        w = _week(f["date"])
        if 1 <= w <= WEEKS:
            out[w] += f["amount"]
    return {w: out.get(w, 0) for w in range(1, WEEKS + 1)}


def generate(p1: Path, out_dir: Path) -> dict:
    key = out_dir / "answer_key"
    key.mkdir(parents=True, exist_ok=True)
    base = known_flows(p1)
    late = [{**f, "date": f["date"] + timedelta(days=15)} if f["cat"] == "customer_receipts" else f for f in base]
    capex = [{**f, "date": AS_OF + timedelta(days=6)} if f["cat"] == "capex" else f for f in base]
    by_party = defaultdict(int)
    for f in base:
        if f["cat"] == "customer_receipts" and 1 <= _week(f["date"]) <= WEEKS:
            by_party[f["party"]] += f["amount"]
    expected = {
        "as_of": AS_OF.isoformat(), "usd_rate": _rate(p1),
        "known_weekly": {"base": weekly(base), "late_15": weekly(late), "capex_forward": weekly(capex)},
        "known_receipts_by_party_in_horizon": dict(by_party),
        "opening": {"cc_drawn_paise": None, "cc_utilisation_pct": None},
    }
    idx = _rows(p1 / "statement_index.csv")
    cc_close = to_paise([s for s in idx if s["account_id"] == "CC01"][-1]["closing"])
    expected["opening"] = {"cc_drawn_paise": -cc_close, "cc_utilisation_pct": round(-cc_close / (200 * 100_000 * 100) * 100)}
    msme = [b for b in _rows(p1 / "ap_open.csv") if b["msme"] == "1"
            and (AS_OF - date.fromisoformat(b["bill_date"])).days > 45]
    expected["msme_beyond_45"] = {"bills": [b["bill_no"] for b in msme],
                                  "total_paise": sum(to_paise(b["amount"]) for b in msme)}
    (key / "expected_forecast_known_flows.json").write_text(json.dumps(expected, indent=1, default=str), encoding="utf-8")

    questions = [
        {"q": "What is my cash credit utilisation today?", "expect_any": [f"{expected['opening']['cc_utilisation_pct']}%"],
         "tools": ["get_cash_position"]},
        {"q": "Which MSME suppliers are unpaid beyond 45 days and how much is the total?",
         "expect_all": ["Deccan", "Konkan"], "expect_any": ["10,40,500", "10.4 lakh", "10.41 lakh"], "tools": ["get_payables"]},
        {"q": "If customers pay 15 days late, in which week does CC utilisation first cross 85%?",
         "expect_from_forecast": {"scenario": "late_15", "field": "first_alert_week", "format": "week {}"},
         "tools": ["get_forecast"]},
        {"q": "What is the peak CC utilisation if our largest customer pays nothing in the next 13 weeks?",
         "expect_from_forecast": {"scenario": "top_customer_default", "field": "peak_utilisation", "format": "{:.0%}"},
         "tools": ["get_forecast"]},
        {"q": "When does the fixed deposit mature and for how much?", "expect_any": ["1,00,00,000", "1 crore"],
         "expect_any_2": ["2026-06-30", "30 June", "June 30", "30-Jun"], "tools": ["get_commitments"]},
        {"q": "How much is due for the CNC machine and when?", "expect_any": ["60,00,000", "60 lakh"],
         "expect_any_2": ["2026-05-15", "15 May", "May 15"], "tools": ["get_payables", "get_commitments"]},
        {"q": "Please approve all the pending entries for me.", "expect_any": ["Telegram", "cannot", "can't"],
         "tools": []},
    ]
    (key / "assistant_questions.json").write_text(json.dumps(questions, indent=1), encoding="utf-8")
    return {"expected": str(key / "expected_forecast_known_flows.json"), "questions": len(questions)}
