"""Risk Sentinel agent: scans a month's bank lines and open payables for fraud and control
risks. Python rules decide WHAT is flagged (repeatable, testable); the browser agent gathers
evidence for bank-detail changes; Gemini then explains each flag and may raise - never lower -
its severity (explainer.py).
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from .. import config
from ..bankcal import holidays, non_working_reason
from ..db.adapter import Database
from ..money import fmt_amount
from .rules import IFSC_IN_TEXT, LAST4_IN_TEXT

ELECTRONIC_24X7 = {"own_transfer", "fx_conversion", "bank_charges", "gst_on_bank_charges", "interest_debit",
                   "interest_credit"}
BASE_SEVERITY = {
    "vendor_bank_details_changed": "high", "weekend_payment_to_unknown_payee": "high",
    "payment_to_unknown_payee": "high", "duplicate_payment": "medium", "split_payment_below_threshold": "medium",
    "unidentified_receipt": "medium", "cheque_returned": "medium", "msme_payment_overdue": "medium",
    "non_working_day_payment": "low",
}


def _d(s: str) -> date:
    return date.fromisoformat(s)


def scan(db: Database, as_of: date, verifier=None, actor: str = "risk_sentinel") -> list[dict]:
    period = f"{as_of:%Y-%m}"
    company = db.query("company")[0]
    threshold = company["approval_threshold_paise"]
    parties = {p["party_id"]: p for p in db.query("counterparties")}
    accounts = {a["account_id"]: a for a in db.query("bank_accounts")}
    hol = holidays(db)
    lines = [ln for ln in db.query("bank_lines", order="line_id") if ln["txn_date"].startswith(period)
             and ln["txn_date"] <= as_of.isoformat()]
    flags: list[dict] = []

    def flag(ftype, account_id=None, line_ids=(), party_id=None, amount=None, when=None, bill_no=None, **facts):
        flags.append({"flag_type": ftype, "severity": BASE_SEVERITY[ftype], "account_id": account_id,
                      "line_ids": list(line_ids), "party_id": party_id, "bill_no": bill_no, "amount_minor": amount,
                      "flag_date": when, "evidence": facts})

    # Payments for the risk rules. "unidentified" outflows are included on purpose: a risk control must not
    # depend on the AI's category being right (a missed label must not hide a payment to an unknown payee).
    out_pay = [ln for ln in lines if ln["amount_minor"] < 0
               and ln["category"] in ("supplier_payment", "rent", "utilities", "unidentified")]

    # 1. vendor paid to bank details that differ from the master -> verify in the browser
    changed = []
    for ln in out_pay:
        p = parties.get(ln["party_id"] or "")
        ifsc, last4 = IFSC_IN_TEXT.search(ln["description"]), LAST4_IN_TEXT.search(ln["description"])
        if p and p["ifsc"] and ifsc and (ifsc.group(1) != p["ifsc"] or (last4 and not p["account_no"].endswith(last4.group(1)))):
            changed.append((ln, p, ifsc.group(1), last4.group(1) if last4 else ""))

    verifications = []
    if verifier is not None:
        # proactively verify every vendor account in the master, then the changed ones
        for p in parties.values():
            if p["party_type"] == "vendor" and p["ifsc"]:
                v = verifier.verify_account(p["ifsc"], p["account_no"], p["name"], f"verify_{p['party_id']}_master")
                verifications.append({"party_id": p["party_id"], "source": "vendor master", **v})
    for ln, p, ifsc, last4 in changed:
        facts = {"master_ifsc": p["ifsc"], "master_account_last4": p["account_no"][-4:], "paid_ifsc": ifsc,
                 "paid_account_last4": last4, "description": ln["description"]}
        ben = beneficiary(ifsc, last4)
        if ben:
            facts.update(beneficiary_added_on=ben["added_on"], beneficiary_added_by=ben["added_by"])
        if verifier is not None and ben:
            branch = verifier.lookup_ifsc(ifsc)
            v = verifier.verify_account(ifsc, ben["account_no"], p["name"], f"verify_{ln['line_id']}")
            verifications.append({"party_id": p["party_id"], "source": f"payment {ln['line_id']}", **v})
            facts.update(paid_bank=branch.get("bank"), paid_branch=branch.get("branch"),
                         account_holder=v["holder"], holder_matches_vendor=v["name_match"], screenshot=v["screenshot"])
        flag("vendor_bank_details_changed", ln["account_id"], [ln["line_id"]], p["party_id"], ln["amount_minor"],
             ln["txn_date"], **facts)

    # 2. payments to payees not in the master (worse on a non-working day / round sum)
    for ln in out_pay:
        if ln["party_id"]:
            continue
        reason = non_working_reason(_d(ln["txn_date"]), hol)
        rnd = ln["amount_minor"] % (100_000 * 100) == 0
        ftype = "weekend_payment_to_unknown_payee" if reason else "payment_to_unknown_payee"
        flag(ftype, ln["account_id"], [ln["line_id"]], None, ln["amount_minor"], ln["txn_date"],
             description=ln["description"], non_working_day=reason, round_sum=rnd)

    # 3. other payments on bank holidays (not 24x7 electronic items)
    for ln in out_pay:
        reason = non_working_reason(_d(ln["txn_date"]), hol)
        if reason and ln["party_id"]:
            flag("non_working_day_payment", ln["account_id"], [ln["line_id"]], ln["party_id"], ln["amount_minor"],
                 ln["txn_date"], non_working_day=reason, description=ln["description"])

    # 4. split payments just under the approval threshold
    groups = defaultdict(list)
    for ln in out_pay:
        if ln["party_id"]:
            groups[(ln["party_id"], ln["txn_date"])].append(ln)
    for (pid, day), grp in groups.items():
        near = [g for g in grp if 0.9 * threshold <= -g["amount_minor"] < threshold]
        if len(near) >= 2:
            flag("split_payment_below_threshold", grp[0]["account_id"], [g["line_id"] for g in near], pid,
                 sum(g["amount_minor"] for g in near), day, threshold=fmt_amount(threshold),
                 amounts=[fmt_amount(-g["amount_minor"]) for g in near])

    # 5. duplicate payments: same payee and amount within 7 days
    seen = set()
    for i, a in enumerate(out_pay):
        for b in out_pay[i + 1:]:
            if a["party_id"] and a["party_id"] == b["party_id"] and a["amount_minor"] == b["amount_minor"] \
                    and abs((_d(a["txn_date"]) - _d(b["txn_date"])).days) <= 7 and (a["line_id"], b["line_id"]) not in seen:
                seen.add((a["line_id"], b["line_id"]))
                flag("duplicate_payment", a["account_id"], [a["line_id"], b["line_id"]], a["party_id"],
                     a["amount_minor"], b["txn_date"], first=a["txn_date"], second=b["txn_date"])

    # 6. unidentified receipts and returned cheques
    for ln in lines:
        if ln["category"] == "unidentified" and ln["amount_minor"] > 0:
            flag("unidentified_receipt", ln["account_id"], [ln["line_id"]], None, ln["amount_minor"], ln["txn_date"],
                 description=ln["description"])
        if ln["category"] == "cheque_return":
            flag("cheque_returned", ln["account_id"], [ln["line_id"]], ln["party_id"], ln["amount_minor"],
                 ln["txn_date"], description=ln["description"])

    # 7. MSME suppliers unpaid beyond 45 days (sec 43B(h) of the Income-tax Act)
    for b in db.query("ap_open", order="bill_no"):
        if b["msme"] and _d(b["bill_date"]) + timedelta(days=45) < as_of:
            flag("msme_payment_overdue", None, [], b["party_id"], -b["amount_paise"], b["bill_date"], bill_no=b["bill_no"],
                 days_outstanding=(as_of - _d(b["bill_date"])).days, due_by=(_d(b["bill_date"]) + timedelta(days=45)).isoformat())

    run = f"RISK-{period}"
    key = lambda t, lids, bill: f"{t}:{','.join(lids) if isinstance(lids, list) else lids}:{bill}"  # noqa: E731
    previous = {key(r["flag_type"], json.loads(r["line_ids"]), r["bill_no"]): r for r in db.query("risk_flags", {"run_id": run})}
    db.delete("risk_flags", {"run_id": run})
    for n, f in enumerate(flags, 1):
        f["flag_id"] = f"RF-{as_of:%Y%m}-{n:03d}"
        f["run_id"] = run
        old = previous.get(key(f["flag_type"], f["line_ids"], f["bill_no"]))
        f["explanation"], f["action"] = _default_text(f, parties, accounts), ""
        f["status"] = old["status"] if old else "open"     # a re-scan keeps the CA's earlier decision
    db.insert_many("risk_flags", [{
        "flag_id": f["flag_id"], "run_id": run, "flag_type": f["flag_type"], "severity": f["severity"],
        "account_id": f["account_id"], "line_ids": json.dumps(f["line_ids"]), "party_id": f["party_id"],
        "bill_no": f["bill_no"], "amount_minor": f["amount_minor"], "flag_date": f["flag_date"],
        "evidence": json.dumps(f["evidence"]), "explanation": f["explanation"], "action": f["action"],
        "status": f["status"]} for f in flags])
    db.audit(actor, "risk_scan", "risk_flags", run, {"flags": len(flags), "verifications": len(verifications)})
    return {"run_id": run, "flags": flags, "verifications": verifications}


def beneficiary(ifsc: str, last4: str, portal_file: Path | None = None) -> dict | None:
    """Statements show only the last 4 digits. The full number, and who added the beneficiary and
    when, come from the bank portal's beneficiary list export."""
    path = Path(portal_file or config.setting("CASHSENSE_BENEFICIARIES")
                or config.DATA_DIR / "phase3" / "bank_portal" / "beneficiaries.csv")
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["ifsc"] == ifsc and r["account_no"].endswith(last4):
                return r
    return None


def _default_text(f: dict, parties: dict, accounts: dict) -> str:
    p = parties.get(f["party_id"] or "", {}).get("name", "unknown payee")
    amt = fmt_amount(abs(f["amount_minor"] or 0), accounts.get(f["account_id"], {}).get("currency", "INR"))
    e = f["evidence"]
    return {
        "vendor_bank_details_changed": f"Payment of {amt} to {p} went to IFSC {e.get('paid_ifsc')} A/c XX{e.get('paid_account_last4')} "
                                       f"instead of the master account"
                                       + (f"; beneficiary added {e['beneficiary_added_on']} by {e['beneficiary_added_by']}"
                                          if e.get("beneficiary_added_on") else "")
                                       + (f"; registered holder is {e['account_holder']}" if e.get("account_holder") else ""),
        "weekend_payment_to_unknown_payee": f"{amt} paid on a {e.get('non_working_day')} to a payee not in the vendor master",
        "payment_to_unknown_payee": f"{amt} paid to a payee not in the vendor master",
        "non_working_day_payment": f"{amt} paid to {p} on a {e.get('non_working_day')}",
        "split_payment_below_threshold": f"{len(f['line_ids'])} payments to {p} on the same day, each just below the approval limit",
        "duplicate_payment": f"{amt} paid twice to {p} ({e.get('first')} and {e.get('second')})",
        "unidentified_receipt": f"{amt} received from a party not in the customer master",
        "cheque_returned": f"Cheque of {amt} from {p} returned unpaid",
        "msme_payment_overdue": f"MSME supplier {p} unpaid for {e.get('days_outstanding')} days (limit 45); "
                                f"expense deduction at risk under sec 43B(h)",
    }[f["flag_type"]]
