"""Rule-based categoriser. Runs alongside the AI as an independent cross-check, and on its own
when the AI is unavailable. Deterministic and explainable."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..db.adapter import Database

IFSC_IN_TEXT = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
LAST4_IN_TEXT = re.compile(r"A/C XX(\d{4})")


def norm(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9 ]", " ", (text or "").replace("(SAMPLE)", "")).upper()
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class Context:
    own_ifsc: set
    own_last4: set
    parties: list[dict]
    party_ids: set


def build_context(db: Database) -> Context:
    accounts = db.query("bank_accounts")
    parties = db.query("counterparties", order="party_id")
    for p in parties:
        p["_key"] = norm(p["name"])[:20].strip()
    return Context({a["ifsc"] for a in accounts}, {a["account_no"][-4:] for a in accounts}, parties,
                   {p["party_id"] for p in parties})


def match_party(desc: str, ctx: Context, types: tuple[str, ...]) -> tuple[str | None, bool | None]:
    """Return (party_id, bank_details_match). bank_details_match is None when it cannot be checked."""
    text = norm(desc).replace(" ", "")
    ifsc = IFSC_IN_TEXT.search(desc or "")
    last4 = LAST4_IN_TEXT.search(desc or "")
    best = None
    for p in ctx.parties:
        if p["party_type"] not in types or not p["_key"]:
            continue
        if p["_key"].replace(" ", "") in text:
            if best is None or len(p["_key"]) > len(best["_key"]):
                best = p
    if best is None and ifsc:  # fall back to bank details alone
        for p in ctx.parties:
            if p["party_type"] in types and p["ifsc"] == ifsc.group(1) and \
                    (not last4 or p["account_no"].endswith(last4.group(1))):
                return p["party_id"], True
    if best is None:
        return None, None
    if best["ifsc"] and ifsc:
        same = best["ifsc"] == ifsc.group(1) and (not last4 or best["account_no"].endswith(last4.group(1)))
        return best["party_id"], same
    return best["party_id"], None


CHQ_RTN = re.compile(r"CHQ RTN-(\d{6})")


def cheque_return_party(line: dict, account_lines: list[dict], ctx: Context) -> str | None:
    """A returned cheque names only the cheque number: find the earlier deposit of that cheque."""
    m = CHQ_RTN.search((line.get("description") or "").upper())
    if not m:
        return None
    for ln in account_lines:
        d = (ln.get("description") or "").upper()
        if ln["amount_minor"] > 0 and f"CHQ {m.group(1)}" in d and ln["txn_date"] <= line["txn_date"]:
            return match_party(d, ctx, ("customer",))[0]
    return None


def rule_categorise(line: dict, ctx: Context) -> dict:
    d = (line.get("description") or "").upper()
    amt = line["amount_minor"]
    out = amt < 0

    def res(cat, conf, reason, party=None, bank_ok=None):
        return {"category": cat, "party_id": party, "confidence": conf, "reason": reason, "bank_match": bank_ok}

    ifsc = IFSC_IN_TEXT.search(d)
    if "OWN AC TRF" in d and (not ifsc or ifsc.group(1) in ctx.own_ifsc):
        return res("own_transfer", 0.97, "Own account transfer (company IFSC)")
    if d.startswith("FX CONV"):
        return res("fx_conversion", 0.97, "EEFC foreign currency conversion")
    if d.startswith("GST @") and "CHGS" in d:
        return res("gst_on_bank_charges", 0.97, "GST on bank charges (input tax credit)")
    if "CHQ RTN" in d and "CHGS" not in d:
        return res("cheque_return", 0.95, "Deposited cheque returned unpaid")
    if "CHGS" in d or "CHARGES" in d:
        return res("bank_charges", 0.95, "Charges levied by the bank")
    if "INT DEBITED" in d:
        return res("interest_debit", 0.97, "Interest debited on cash credit")
    if "INT CR" in d:
        return res("interest_credit", 0.95, "Interest credited (FD)")
    if "ITNS280" in d:
        return res("advance_tax", 0.97, "Advance tax challan ITNS 280", "GOV-CBDT")
    if "ITNS281" in d:
        return res("tds_payment", 0.97, "TDS challan ITNS 281", "GOV-CBDT")
    if "GST PMT" in d or "CPIN" in d:
        return res("gst_payment", 0.97, "GST cash ledger payment (CPIN)", "GOV-GST")
    if "EPFO" in d:
        return res("pf_esi", 0.97, "EPFO PF contribution", "GOV-EPFO")
    if "ESIC" in d:
        return res("pf_esi", 0.97, "ESIC contribution", "GOV-ESIC")
    if "BULK NEFT" in d and ("SALARY" in d or "BONUS" in d):
        return res("salary", 0.97, "Bulk salary / bonus payout", "EMP-PAYROLL")
    if d.startswith("ACH DR") and "EMI" in d:
        return res("loan_emi", 0.95, "Term loan EMI by ACH", "BANK-TL")
    if "INWARD REMIT" in d:
        pid, _ = match_party(d, ctx, ("customer",))
        return res("export_receipt", 0.95 if pid else 0.7, "Inward foreign remittance" + ("" if pid else " - payer not in master"), pid)
    if not out:
        pid, bank_ok = match_party(d, ctx, ("customer",))
        if pid:
            return res("customer_receipt", 0.93, "Receipt from known customer", pid, bank_ok)
        return res("unidentified", 0.5, "Credit from a party not in the customer master")
    pid, bank_ok = match_party(d, ctx, ("vendor", "lender"))
    if pid:
        cat = next(p["category"] for p in ctx.parties if p["party_id"] == pid)
        category = {"rent": "rent", "utilities": "utilities"}.get(cat, "supplier_payment")
        reason = "Payment to known vendor"
        if bank_ok is False:
            reason += " - IFSC / account differs from vendor master"
        return res(category, 0.93 if bank_ok is not False else 0.75, reason, pid, bank_ok)
    return res("supplier_payment", 0.55, "Outgoing payment to a payee not in the vendor master")
