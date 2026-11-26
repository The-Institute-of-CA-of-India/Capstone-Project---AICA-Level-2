"""TDS: suggested-section detection (never auto-applied), CA decision, 26Q return-data preparation.

Mirrors gst_service.py's safety pattern exactly: nothing is ever deducted/filed automatically, and this
app never claims a return was filed — only prepares the data and lets a human record the government
portal's acknowledgement number after filing it themselves there.
"""
from __future__ import annotations

import datetime as dt
import io
from collections import defaultdict
from decimal import Decimal

from services.audit_service import audit
from services.db import get_db, now_iso
from services.tds_rules import get_rules, suggest_section
from services.tenancy import AuthContext, require_client, scoped_get
from utils.helpers import D, ZERO, normalize_name

QUARTER_MONTHS = {"Q1": (4, 5, 6), "Q2": (7, 8, 9), "Q3": (10, 11, 12), "Q4": (1, 2, 3)}


def quarter_for(year: int, month: int) -> tuple[str, str]:
    """Returns (quarter_code, fy_label) for a calendar (year, month), e.g. (2026, 11) -> ('Q3', '2026-27')."""
    for q, months in QUARTER_MONTHS.items():
        if month in months:
            fy_start = year if month >= 4 else year - 1
            return q, f"{fy_start}-{str(fy_start + 1)[-2:]}"
    raise ValueError("invalid month")


def quarter_bounds(quarter: str, fy_label: str) -> tuple[dt.date, dt.date]:
    start_year = int(fy_label[:4])
    months = QUARTER_MONTHS[quarter]
    year = start_year if months[0] >= 4 else start_year + 1
    start = dt.date(year, months[0], 1)
    from utils.helpers import month_end

    end = month_end(year if months[-1] >= 4 else year + (1 if year == start_year else 0), months[-1])
    # Q4 spans Jan-Mar of the FY's second calendar year
    if quarter == "Q4":
        end_year = start_year + 1
        start = dt.date(end_year, 1, 1)
        end = month_end(end_year, 3)
    return start, end


def suggest_tds_for_invoice(client: dict, invoice_data: dict, existing_vendor_total_this_fy: Decimal,
                           rules_version: str | None = None) -> dict:
    """Called at document-approval time for a purchase/expense invoice. Returns a dict merged into the
    invoice's suggested fields; never a final decision — the CA always confirms via set_tds_decision."""
    out = {"tds_status": "not_applicable", "tds_section": None, "tds_rate": "0.00"}
    if not client.get("is_tds_deductor"):
        return out
    if invoice_data.get("category") not in ("purchase", "expense"):
        return out
    rules = get_rules(rules_version or "2025.1")
    amount = D(invoice_data.get("taxable_value"))
    cumulative = existing_vendor_total_this_fy + amount
    description = f"{invoice_data.get('party_name') or ''} {invoice_data.get('expense_head') or ''}"
    section_key = suggest_section(rules, description)
    if not section_key:
        out["tds_status"] = "pending"  # a TDS deductor's purchase/expense invoice always needs a human decision
        return out
    sec = rules["sections"][section_key]
    threshold_crossed = cumulative > sec["annual_limit"] or (sec["single_limit"] and amount > sec["single_limit"])
    out["tds_section"] = section_key
    out["tds_rate"] = str(sec["rate"])
    out["tds_status"] = "pending"
    out["_tds_suggestion_note"] = (
        f"Suggested: {sec['label']} — cumulative payments to this vendor this FY: ₹{cumulative} "
        f"({'over' if threshold_crossed else 'under'} the ₹{sec['annual_limit']} threshold). Confirm before relying on this.")
    return out


def vendor_payments_this_fy(client_id: str, party_gstin: str | None, party_name: str, fy_label: str,
                            before_date: dt.date) -> Decimal:
    """Sum of approved purchase/expense invoice taxable values to the same vendor, earlier in the FY."""
    from utils.helpers import fy_bounds

    db = get_db()
    start, _ = fy_bounds(fy_label)
    rows = db.fetchall("select taxable_value, party_gstin, party_name, note_type from invoices where client_id = ? "
                       "and category in ('purchase','expense') and status = 'approved' and invoice_date >= ? and invoice_date < ?",
                       [client_id, start, before_date])
    total = ZERO
    for r in rows:
        same = (party_gstin and r["party_gstin"] == party_gstin) or (not party_gstin and normalize_name(r["party_name"]) == normalize_name(party_name))
        if same:
            total += D(r["taxable_value"]) * (Decimal(-1) if r["note_type"] == "credit_note" else Decimal(1))
    return total


def set_tds_decision(ctx: AuthContext, invoice_id: str, *, deduct: bool, section: str | None = None,
                     rate: Decimal | None = None, rules_version: str | None = None) -> None:
    from services.period_service import assert_period_open
    from utils.helpers import to_date

    inv = scoped_get(ctx, "invoices", invoice_id, "prepare_vouchers")
    if inv["category"] not in ("purchase", "expense"):
        raise ValueError("TDS applies to the client's own payments (purchase/expense invoices) only")
    assert_period_open(inv["client_id"], to_date(inv["invoice_date"]))
    db = get_db()
    if not deduct:
        db.update("invoices", invoice_id, {"tds_status": "not_deducted", "tds_section": None, "tds_rate": ZERO, "tds_amount": ZERO})
    else:
        rules = get_rules(rules_version or "2025.1")
        if section not in rules["sections"]:
            raise ValueError("Unknown TDS section")
        rate = D(rate) if rate is not None else rules["sections"][section]["rate"]
        amount = (D(inv["taxable_value"]) * rate / 100).quantize(Decimal("0.01"))
        db.update("invoices", invoice_id, {"tds_status": "deducted", "tds_section": section, "tds_rate": rate, "tds_amount": amount})
    audit(ctx, "invoice.tds_decision", "invoices", invoice_id, client_id=inv["client_id"],
          after={"deduct": deduct, "section": section})


def list_sections(rules_version: str = "2025.1") -> dict:
    return get_rules(rules_version)["sections"]


def tds_summary(ctx: AuthContext, client_id: str, start: dt.date, end: dt.date) -> dict:
    require_client(ctx, client_id, "view")
    db = get_db()
    rows = db.fetchall("select tds_section, tds_amount, taxable_value, note_type from invoices where client_id = ? "
                       "and status = 'approved' and tds_status = 'deducted' and invoice_date between ? and ?",
                       [client_id, start, end])
    by_section: dict[str, Decimal] = defaultdict(lambda: ZERO)
    total = ZERO
    for r in rows:
        sign = Decimal(-1) if r["note_type"] == "credit_note" else Decimal(1)
        amt = sign * D(r["tds_amount"])
        by_section[r["tds_section"] or "unspecified"] += amt
        total += amt
    pending = db.scalar("select count(*) from invoices where client_id = ? and status = 'approved' and tds_status = 'pending' "
                        "and invoice_date between ? and ?", [client_id, start, end])
    return {"by_section": dict(by_section), "total": total, "pending_decisions": pending or 0, "count": len(rows)}


def prepare_26q(ctx: AuthContext, client_id: str, quarter: str, fy_label: str, rules_version: str | None = None) -> dict:
    client = require_client(ctx, client_id, "gst_prepare" if ctx.can("gst_prepare") else "prepare_vouchers")
    rules = get_rules(rules_version or "2025.1")
    start, end = quarter_bounds(quarter, fy_label)
    db = get_db()
    rows = db.fetchall("select * from invoices where client_id = ? and status = 'approved' and tds_status = 'deducted' "
                       "and invoice_date between ? and ?", [client_id, start, end])
    warnings = []
    if not client.get("tan"):
        warnings.append("Client has no TAN on file — required to actually file Form 26Q")
    deductees: dict[tuple, dict] = {}
    for r in rows:
        sign = Decimal(-1) if r["note_type"] == "credit_note" else Decimal(1)
        key = (r.get("party_gstin") or "", normalize_name(r["party_name"]))
        d = deductees.setdefault(key, {"party_name": r["party_name"], "pan": None, "section": r["tds_section"],
                                       "amount_paid": ZERO, "tds_deducted": ZERO, "invoice_count": 0})
        d["amount_paid"] += sign * D(r["taxable_value"])
        d["tds_deducted"] += sign * D(r["tds_amount"])
        d["invoice_count"] += 1
        if not d["pan"] and r.get("party_gstin") and len(r["party_gstin"]) == 15:
            d["pan"] = r["party_gstin"][2:12]
    deductee_rows = list(deductees.values())
    if any(not d["pan"] for d in deductee_rows):
        warnings.append("Some deductees have no PAN on file — required to file 26Q (and Sec 206AA higher-rate TDS "
                        "applies if genuinely PAN-less)")
    total_tds = sum((d["tds_deducted"] for d in deductee_rows), ZERO)
    return {"return_type": "26Q", "quarter": quarter, "fy": fy_label, "tan": client.get("tan"), "rules_version": rules_version or "2025.1",
            "period_from": start, "period_to": end, "deductees": deductee_rows, "total_tds": total_tds,
            "total_invoices": sum(d["invoice_count"] for d in deductee_rows), "warnings": warnings}


def _jsonable(o):
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()
    return o


def save_return(ctx: AuthContext, client_id: str, prep: dict) -> str:
    client = require_client(ctx, client_id, "prepare_vouchers")
    db = get_db()
    row = db.fetchone("select * from tds_returns where client_id = ? and return_type = ? and quarter = ?",
                      [client_id, prep["return_type"], f"{prep['quarter']}-{prep['fy']}"])
    if row and row["status"] in ("approved", "filed_externally"):
        raise ValueError(f"{prep['return_type']} {prep['quarter']}-{prep['fy']} is {row['status']}; unapprove it before re-preparing")
    vals = {"data": _jsonable(prep), "warnings": prep.get("warnings", []), "status": "prepared", "prepared_by": ctx.user_id,
            "rules_version": prep["rules_version"]}
    if row:
        db.update("tds_returns", row["id"], vals)
        rid = row["id"]
    else:
        rid = db.insert("tds_returns", {"firm_id": client["firm_id"], "client_id": client_id, "return_type": prep["return_type"],
                                        "quarter": f"{prep['quarter']}-{prep['fy']}", "created_at": now_iso(), **vals})
    audit(ctx, "tds.prepared", "tds_returns", rid, client_id=client_id, after={"quarter": prep["quarter"], "fy": prep["fy"]})
    return rid


def approve_return(ctx: AuthContext, return_id: str) -> None:
    r = scoped_get(ctx, "tds_returns", return_id, "gst_approve" if ctx.can("gst_approve") else "approve_vouchers")
    if r["status"] != "prepared":
        raise ValueError("Only prepared returns can be approved")
    get_db().update("tds_returns", return_id, {"status": "approved", "approved_by": ctx.user_id, "approved_at": now_iso()})
    audit(ctx, "tds.approved", "tds_returns", return_id, client_id=r["client_id"])


def record_external_filing(ctx: AuthContext, return_id: str, ack_no: str) -> None:
    r = scoped_get(ctx, "tds_returns", return_id, "approve_vouchers")
    if r["status"] != "approved":
        raise ValueError("Approve the prepared data first")
    if not ack_no or len(ack_no.strip()) < 6:
        raise ValueError("Enter the acknowledgement number shown by the TRACES/NSDL portal")
    get_db().update("tds_returns", return_id, {"status": "filed_externally", "external_ack_no": ack_no.strip()})
    audit(ctx, "tds.marked_filed_externally", "tds_returns", return_id, client_id=r["client_id"], after={"ack": ack_no.strip()})


def list_returns(ctx: AuthContext, client_id: str) -> list[dict]:
    require_client(ctx, client_id, "view")
    return get_db().fetchall("select id, return_type, quarter, status, external_ack_no, approved_at, created_at "
                             "from tds_returns where client_id = ? order by quarter desc", [client_id])


def to_excel(prep: dict) -> bytes:
    import pandas as pd

    rows = [{"party_name": d["party_name"], "pan": d["pan"], "section": d["section"], "amount_paid": float(d["amount_paid"]),
            "tds_deducted": float(d["tds_deducted"]), "invoices": d["invoice_count"]} for d in prep["deductees"]]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        (pd.DataFrame(rows) if rows else pd.DataFrame({"note": ["No TDS deductions this quarter"]})).to_excel(
            xw, sheet_name="26Q Deductees", index=False)
        pd.DataFrame({"warnings": prep["warnings"] or ["none"]}).to_excel(xw, sheet_name="warnings", index=False)
    return buf.getvalue()
