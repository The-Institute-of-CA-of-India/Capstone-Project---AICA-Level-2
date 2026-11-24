"""Reconciler agent: matches bank lines to book entries and prepares the bank reconciliation
statement (BRS). Matching and arithmetic are deterministic Python; Gemini only explains the
exceptions afterwards (see explainer.py). Exact matches are accepted and logged automatically;
everything else becomes a reconciliation item, and items that need an entry are proposed for
approval.

Approval rules agreed with the CA (Phase 3):
  * exact bank-to-book matches: auto-accepted and logged
  * suggested entries, fuzzy matches and every risk flag: need the CA's Approve tap
  * nothing is posted to the books without approval
"""
from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from datetime import date

from .. import config
from ..db.adapter import Database
from ..money import fmt_amount

DATE_WINDOW = 5          # days allowed between book date and bank date for an amount match
FUZZY_WINDOW = 3
FUZZY_PCT = 0.02

BANK_ONLY = {
    "bank_charges": "bank_charges_not_booked",
    "gst_on_bank_charges": "gst_on_bank_charges_not_booked",
    "interest_debit": "interest_debited_not_booked",
    "interest_credit": "interest_credited_not_booked",
    "cheque_return": "cheque_returned",
    "unidentified": "unidentified_receipt",
}
LABEL = {
    "cheque_issued_not_presented": "Cheque issued but not yet presented",
    "deposit_not_yet_credited": "Cheque deposited, not yet credited by bank",
    "bank_charges_not_booked": "Bank charges not yet booked",
    "gst_on_bank_charges_not_booked": "GST on bank charges not yet booked",
    "interest_debited_not_booked": "Interest debited by bank, not yet booked",
    "interest_credited_not_booked": "Interest credited by bank, not yet booked",
    "cheque_returned": "Customer cheque returned unpaid",
    "unidentified_receipt": "Receipt from an unidentified party",
    "duplicate_debit": "Duplicate debit - same payee and amount paid again",
    "amount_mismatch": "Amount in books differs from bank",
    "unexplained_bank_item": "Bank item with no book entry",
    "unexplained_book_item": "Book entry with no bank line",
}
TIMING = {"cheque_issued_not_presented", "deposit_not_yet_credited"}


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _days(a: str, b: str) -> int:
    return abs((_d(a) - _d(b)).days)


def _transposed(a: int, b: int) -> bool:
    return sorted(str(abs(a))) == sorted(str(abs(b))) and a != b


def _party_name(db: Database, party_id: str | None) -> str:
    if not party_id:
        return ""
    rows = db.query("counterparties", {"party_id": party_id})
    return rows[0]["name"] if rows else party_id


def _fx_rate(lines: list[dict], upto: str) -> float | None:
    """Latest USD rate printed on an EEFC conversion line on or before a date."""
    rate = None
    for ln in lines:
        if ln["txn_date"] <= upto and ln["description"].startswith("FX CONV"):
            m = re.search(r"@(\d+\.\d+)", ln["description"])
            if m:
                rate = float(m.group(1))
    return rate


def suggestion_for(db: Database, category: str, line: dict, acc: dict, all_lines: list[dict]) -> dict:
    """Template entry that would bring the books in line with the bank (Python decides the ledgers)."""
    amt, cur = line["amount_minor"], acc["currency"]
    bank_ledger = f"Bank: {acc['account_id']} {acc['name']}"
    party = _party_name(db, line.get("party_id"))
    s = {"action": "post_entry", "date": line["txn_date"], "account_id": acc["account_id"], "currency": cur,
         "bank_line_ids": [line["line_id"]], "bank_amount_minor": amt}
    if category == "bank_charges_not_booked":
        s.update(counter_ledger="Bank Charges", narration=f"Bank charges per statement: {line['description']}")
    elif category == "gst_on_bank_charges_not_booked":
        s.update(counter_ledger="Input GST on bank charges (ITC)",
                 narration=f"GST charged by bank (input tax credit): {line['description']}")
    elif category == "interest_debited_not_booked":
        s.update(counter_ledger="Interest on Cash Credit", narration=f"CC interest debited: {line['description']}")
    elif category == "interest_credited_not_booked":
        m = re.search(r"NET OF TDS\s*([\d.]+)", line["description"])
        tds = int(round(float(m.group(1)) * 100)) if m else 0
        s.update(counter_ledger="Interest Income - FD", narration=f"FD interest credited net of TDS: {line['description']}",
                 extra_lines=[{"ledger": "TDS Receivable (on FD interest)", "dr_minor": tds},
                              {"ledger": "Interest Income - FD", "cr_minor": amt + tds}])
    elif category == "cheque_returned":
        s.update(counter_ledger=f"Sundry Debtors: {party}" if party else "Sundry Debtors",
                 narration=f"Customer cheque returned unpaid - reinstate receivable: {line['description']}")
    elif category == "unidentified_receipt":
        s.update(counter_ledger="Suspense - unidentified receipts",
                 narration=f"Unidentified receipt parked in suspense pending enquiry: {line['description']}")
    elif category == "duplicate_debit":
        s.update(counter_ledger=f"Recoverable from supplier: {party}" if party else "Recoverable from supplier",
                 narration=f"Duplicate payment - recover from supplier: {line['description']}")
    else:
        s.update(action="investigate", counter_ledger="", narration="No automatic entry - needs investigation")
    if cur != "INR" and s["action"] == "post_entry":
        rate = _fx_rate(all_lines, line["txn_date"])
        s["inr_amount_paise"] = int(round(amt * rate)) if rate else None
        s["fx_rate"] = rate
    s["bank_ledger"] = bank_ledger
    return s


def reconcile(db: Database, account_id: str, as_of: date, actor: str = "reconciler") -> dict:
    from .categoriser import categorise

    acc = db.query("bank_accounts", {"account_id": account_id})[0]
    cut = as_of.isoformat()
    lines = [ln for ln in db.query("bank_lines", {"account_id": account_id}, order="line_id") if ln["txn_date"] <= cut]
    missing = [ln for ln in lines if not ln["category"]]
    if missing:  # categorise anything not yet categorised (rules only - fast, free)
        categorise(db, missing, None, use_ai=False, actor=actor)
        lines = [ln for ln in db.query("bank_lines", {"account_id": account_id}, order="line_id")
                 if ln["txn_date"] <= cut]
    entries = [e for e in db.query("book_entries", {"account_id": account_id}, order="entry_id")
               if e["entry_date"] <= cut]
    links = db.query("recon_links", {"account_id": account_id})
    linked_lines = {lk["line_id"] for lk in links}
    linked_entries = {lk["entry_id"] for lk in links}
    run_id = f"RUN-{account_id}-{cut}-{uuid.uuid4().hex[:6]}"
    now = config.now_ist().isoformat(timespec="seconds")
    new_links = []

    def link(line, entry, rule):
        linked_lines.add(line["line_id"])
        linked_entries.add(entry["entry_id"])
        new_links.append({"link_id": uuid.uuid4().hex, "account_id": account_id, "line_id": line["line_id"],
                          "entry_id": entry["entry_id"], "link_type": "auto_exact", "rule": rule,
                          "run_id": run_id, "created_at": now})

    open_lines = lambda: [ln for ln in lines if ln["line_id"] not in linked_lines]  # noqa: E731

    # pass 1: cheques by number and amount
    for e in entries:
        if e["entry_id"] in linked_entries or not e["instrument_no"]:
            continue
        no = e["instrument_no"]
        for ln in open_lines():
            if ln["amount_minor"] == e["amount_minor"] and (f"CHQ PAID-{no}" in ln["description"]
                                                             or f"CHQ {no}" in ln["description"]):
                link(ln, e, "cheque number + amount")
                break

    # pass 2: amount + date window (+ party when both known); closest date must be unique
    by_amount = defaultdict(list)
    for ln in lines:
        if "CHQ PAID-" not in ln["description"] and "CLG CR-CHQ" not in ln["description"]:
            by_amount[ln["amount_minor"]].append(ln)
    for window in (0, 1, 3, DATE_WINDOW):
        for e in entries:
            if e["entry_id"] in linked_entries or e["instrument_no"]:
                continue
            cands = []
            for ln in by_amount.get(e["amount_minor"], []):
                if ln["line_id"] in linked_lines or _days(ln["txn_date"], e["entry_date"]) > window:
                    continue
                if e["party_id"] and ln["party_id"] and e["party_id"] != ln["party_id"]:
                    continue
                cands.append(ln)
            if not cands:
                continue
            best = min(_days(c["txn_date"], e["entry_date"]) for c in cands)
            top = [c for c in cands if _days(c["txn_date"], e["entry_date"]) == best]
            if len(top) == 1:
                rule = "amount + date" + (" + party" if e["party_id"] and top[0]["party_id"] else "")
                link(top[0], e, rule)

    # fuzzy: same party, close date, amount close or digits transposed -> proposed, not linked
    items = []
    fuzzy_lines = set()
    for e in entries:
        if e["entry_id"] in linked_entries or not e["party_id"]:
            continue
        for ln in open_lines():
            if ln["line_id"] in fuzzy_lines or ln["party_id"] != e["party_id"]:
                continue
            if _days(ln["txn_date"], e["entry_date"]) > FUZZY_WINDOW or (ln["amount_minor"] > 0) != (e["amount_minor"] > 0):
                continue
            diff = ln["amount_minor"] - e["amount_minor"]
            if abs(diff) <= abs(e["amount_minor"]) * FUZZY_PCT or _transposed(ln["amount_minor"], e["amount_minor"]):
                fuzzy_lines.add(ln["line_id"])
                linked_entries.add(e["entry_id"])     # reserved for this proposal in this run only
                why = "digits transposed" if _transposed(ln["amount_minor"], e["amount_minor"]) else "small difference"
                items.append({"category": "amount_mismatch", "side": "both", "line_id": ln["line_id"],
                              "entry_id": e["entry_id"], "item_date": ln["txn_date"], "amount_minor": ln["amount_minor"],
                              "adjust_minor": diff, "description": ln["description"], "needs_approval": 1,
                              "suggestion": {"action": "confirm_match_and_correct", "account_id": account_id,
                                             "currency": acc["currency"], "date": ln["txn_date"],
                                             "bank_line_ids": [ln["line_id"]], "entry_id": e["entry_id"],
                                             "book_amount_minor": e["amount_minor"],
                                             "bank_amount_minor": ln["amount_minor"], "correction_minor": diff,
                                             "counter_ledger": e["counter_ledger"],
                                             "bank_ledger": f"Bank: {account_id} {acc['name']}",
                                             "narration": f"Correction: books {fmt_amount(abs(e['amount_minor']), acc['currency'])}"
                                                          f", bank {fmt_amount(abs(ln['amount_minor']), acc['currency'])} ({why})"}})
                break

    # leftovers on the bank side
    linked_by_line = {lk["line_id"] for lk in links} | {lk["line_id"] for lk in new_links}
    for ln in open_lines():
        if ln["line_id"] in fuzzy_lines:
            continue
        cat = BANK_ONLY.get(ln["category"])
        if cat is None and ln["amount_minor"] < 0 and ln["party_id"]:
            twin = [o for o in lines if o["line_id"] != ln["line_id"] and o["line_id"] in linked_by_line
                    and o["party_id"] == ln["party_id"] and o["amount_minor"] == ln["amount_minor"]
                    and _days(o["txn_date"], ln["txn_date"]) <= 7]
            cat = "duplicate_debit" if twin else None
        cat = cat or "unexplained_bank_item"
        sug = suggestion_for(db, cat, ln, acc, lines)
        items.append({"category": cat, "side": "bank_only", "line_id": ln["line_id"], "entry_id": None,
                      "item_date": ln["txn_date"], "amount_minor": ln["amount_minor"], "adjust_minor": ln["amount_minor"],
                      "description": ln["description"], "needs_approval": int(sug["action"] == "post_entry"),
                      "suggestion": sug})

    # leftovers on the book side
    for e in entries:
        if e["entry_id"] in linked_entries:
            continue
        if e["mode"] == "CHQ":
            cat = "cheque_issued_not_presented" if e["amount_minor"] < 0 else "deposit_not_yet_credited"
            sug = {"action": "none", "note": "Timing difference - clears when the bank processes the cheque"}
        else:
            cat, sug = "unexplained_book_item", {"action": "investigate"}
        items.append({"category": cat, "side": "books_only", "line_id": None, "entry_id": e["entry_id"],
                      "item_date": e["entry_date"], "amount_minor": e["amount_minor"], "adjust_minor": -e["amount_minor"],
                      "description": e["narration"], "needs_approval": 0, "suggestion": sug})

    book_bal = acc["opening_balance_minor"] + sum(e["amount_minor"] for e in entries)
    bank_bal = lines[-1]["balance_minor"] if lines else acc["opening_balance_minor"]
    computed = book_bal + sum(i["adjust_minor"] for i in items)
    status = "agreed" if computed == bank_bal else "difference"
    counts = defaultdict(int)
    for i in items:
        counts[i["category"]] += 1
    summary = {"lines": len(lines), "entries": len(entries), "linked_before": len(links),
               "auto_matched_now": len(new_links), "items": dict(counts),
               "timing_only": all(i["category"] in TIMING for i in items)}
    db.insert_many("recon_links", new_links)
    db.insert_many("recon_runs", [{
        "run_id": run_id, "account_id": account_id, "as_of": cut, "created_at": now, "book_balance_minor": book_bal,
        "bank_balance_minor": bank_bal, "computed_bank_minor": computed, "status": status,
        "auto_matched": len(new_links), "summary": json.dumps(summary), "commentary": ""}])
    for n, i in enumerate(items, 1):
        i["item_id"] = f"{run_id}-I{n:03d}"
        i["explanation"] = LABEL.get(i["category"], i["category"])
    db.insert_many("recon_items", [{
        "item_id": i["item_id"], "run_id": run_id, "account_id": account_id, "category": i["category"],
        "side": i["side"], "line_id": i["line_id"], "entry_id": i["entry_id"], "item_date": i["item_date"],
        "amount_minor": i["amount_minor"], "adjust_minor": i["adjust_minor"], "description": i["description"],
        "explanation": i["explanation"], "suggestion": json.dumps(i["suggestion"]),
        "needs_approval": i["needs_approval"]} for i in items])
    result = {"run_id": run_id, "account_id": account_id, "currency": acc["currency"], "as_of": cut,
              "book_balance_minor": book_bal, "bank_balance_minor": bank_bal, "computed_bank_minor": computed,
              "status": status, "summary": summary, "items": items, "new_links": new_links}
    db.audit(actor, "reconcile", "recon_runs", run_id,
             {"status": status, "auto_matched": len(new_links), "items": dict(counts)})
    return result
