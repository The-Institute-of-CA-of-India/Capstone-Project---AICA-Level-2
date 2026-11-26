"""Month finalization, period locking, reopening and snapshots."""
from __future__ import annotations

import datetime as dt
import hashlib
import json

from services.audit_service import audit
from services.db import get_db, now_iso
from services.tenancy import AuthContext, require_client
from utils.helpers import D, ZERO, fy_label_for, month_bounds, to_date


class PeriodLocked(Exception):
    pass


def period_row(client_id: str, year: int, month: int) -> dict | None:
    return get_db().fetchone("select * from accounting_periods where client_id = ? and year = ? and month = ?",
                             [client_id, year, month])


def is_locked(client_id: str, date: dt.date) -> bool:
    d = to_date(date)
    if d is None:
        return False
    row = period_row(client_id, d.year, d.month)
    return bool(row and row["status"] == "finalized")


def assert_period_open(client_id: str, date) -> None:
    d = to_date(date)
    if d and is_locked(client_id, d):
        raise PeriodLocked(f"{d:%b %Y} is finalized and locked. An authorised user must reopen it first.")


def pre_finalization_checks(ctx: AuthContext, client_id: str, year: int, month: int) -> dict:
    """Summary + blocking issues shown before FINALIZE & LOCK MONTH."""
    require_client(ctx, client_id, "view")
    db = get_db()
    start, end = month_bounds(year, month)

    def inv_total(cat, note="invoice"):
        rows = db.fetchall("select total from invoices where client_id = ? and category = ? and note_type = ? and status = 'approved' "
                           "and invoice_date between ? and ?", [client_id, cat, note, start, end])
        return sum((D(r["total"]) for r in rows), ZERO)

    pending_docs = db.scalar("select count(*) from documents where client_id = ? and period_year = ? and period_month = ? "
                             "and status in ('uploaded','processing','processed','needs_review')", [client_id, year, month])
    unapproved = db.scalar("select count(*) from accounting_vouchers where client_id = ? and voucher_date between ? and ? "
                           "and status = 'draft'", [client_id, start, end])
    unmatched = db.scalar("select count(*) from bank_transactions where client_id = ? and txn_date between ? and ? "
                          "and match_status in ('unmatched','needs_review','suspense')", [client_id, start, end])
    bank_count = db.scalar("select count(*) from bank_transactions where client_id = ? and txn_date between ? and ?",
                           [client_id, start, end])
    open_clar = db.scalar("select count(*) from clarification_requests where client_id = ? and status = 'open'", [client_id])
    recon = db.fetchone("select summary from gst_reconciliations where client_id = ? and period = ? order by created_at desc",
                        [client_id, f"{month:02d}{year}"])
    gst_diffs = 0
    if recon and isinstance(recon["summary"], dict):
        gst_diffs = sum(v for k, v in recon["summary"].get("counts", {}).items() if k != "matched")
    warnings = []
    if pending_docs:
        warnings.append(f"{pending_docs} document(s) still pending review/approval")
    if unapproved:
        warnings.append(f"{unapproved} voucher(s) not approved")
    if unmatched:
        warnings.append(f"{unmatched} bank transaction(s) unmatched / in suspense")
    if gst_diffs:
        warnings.append(f"{gst_diffs} GSTR-2B reconciliation difference(s)")
    if not recon:
        warnings.append("GSTR-2B reconciliation not performed for this month")
    if open_clar:
        warnings.append(f"{open_clar} open clarification request(s) with the client")
    row = period_row(client_id, year, month)
    return {
        "total_sales": inv_total("sales"), "total_purchases": inv_total("purchase"), "total_expenses": inv_total("expense"),
        "bank_transactions": bank_count, "pending_documents": pending_docs, "unapproved_vouchers": unapproved,
        "unmatched_bank": unmatched, "gst_differences": gst_diffs, "open_clarifications": open_clar,
        "warnings": warnings, "blocking": unapproved > 0,
        "status": row["status"] if row else "open", "period": row,
    }


def _snapshot(client_id: str, year: int, month: int) -> dict:
    from services import report_service

    db = get_db()
    start, end = month_bounds(year, month)
    vouchers = db.fetchall("select id, voucher_no, voucher_type, voucher_date, total_amount from accounting_vouchers "
                           "where client_id = ? and status = 'approved' and voucher_date between ? and ? order by voucher_no",
                           [client_id, start, end])
    entries = db.fetchall("select e.voucher_id, e.ledger_id, e.dr_cr, e.amount from accounting_voucher_entries e "
                          "join accounting_vouchers v on v.id = e.voucher_id where v.client_id = ? and v.status = 'approved' "
                          "and v.voucher_date between ? and ? order by e.voucher_id, e.line_no", [client_id, start, end])
    tb = report_service.trial_balance_rows(client_id, start, end)
    snap = {
        "period": f"{year}-{month:02d}", "taken_at": now_iso(),
        "vouchers": [{k: str(v[k]) for k in v} for v in vouchers],
        "entries": [{k: str(e[k]) for k in e} for e in entries],
        "trial_balance": [{"ledger": r["ledger"], "debit": str(r["debit"]), "credit": str(r["credit"])} for r in tb],
    }
    return snap


def finalize_month(ctx: AuthContext, client_id: str, year: int, month: int, *, override_warnings: bool = False) -> str:
    client = require_client(ctx, client_id, "finalize_period")
    checks = pre_finalization_checks(ctx, client_id, year, month)
    if checks["blocking"]:
        raise PeriodLocked("Cannot finalize: there are unapproved vouchers in this month.")
    if checks["warnings"] and not override_warnings:
        raise PeriodLocked("Unresolved warnings: " + "; ".join(checks["warnings"]) + ". Confirm to finalize anyway.")
    db = get_db()
    snap = _snapshot(client_id, year, month)
    digest = hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest()
    start, end = month_bounds(year, month)
    with db.transaction():
        row = period_row(client_id, year, month)
        vals = {"status": "finalized", "finalized_by": ctx.user_id, "finalized_at": now_iso(), "snapshot": snap,
                "snapshot_hash": digest}
        if row:
            if row["status"] == "finalized":
                raise PeriodLocked("Month is already finalized")
            db.update("accounting_periods", row["id"], vals)
            pid = row["id"]
        else:
            pid = db.insert("accounting_periods", {"firm_id": client["firm_id"], "client_id": client_id,
                                                   "fy_label": fy_label_for(start, client.get("fy_start_month") or 4),
                                                   "year": year, "month": month, "created_at": now_iso(), **vals})
        db.execute("update documents set status = 'finalized' where client_id = ? and period_year = ? and period_month = ? "
                   "and status = 'approved'", [client_id, year, month])
        audit(ctx, "period.finalized", "accounting_periods", pid, client_id=client_id,
              after={"period": f"{year}-{month:02d}", "snapshot_hash": digest, "warnings_overridden": checks["warnings"]})
    return pid


def reopen_month(ctx: AuthContext, client_id: str, year: int, month: int, reason: str) -> None:
    require_client(ctx, client_id, "reopen_period")
    if not reason or len(reason.strip()) < 10:
        raise ValueError("A reason (at least 10 characters) is required to reopen a finalized month.")
    row = period_row(client_id, year, month)
    if not row or row["status"] != "finalized":
        raise ValueError("Month is not finalized")
    get_db().update("accounting_periods", row["id"], {"status": "reopened", "reopened_by": ctx.user_id,
                                                      "reopened_at": now_iso(), "reopen_reason": reason.strip()})
    audit(ctx, "period.reopened", "accounting_periods", row["id"], client_id=client_id,
          before={"status": "finalized", "snapshot_hash": row.get("snapshot_hash")}, after={"reason": reason.strip()})


def list_periods(ctx: AuthContext, client_id: str) -> list[dict]:
    require_client(ctx, client_id, "view")
    return get_db().fetchall("select id, year, month, status, finalized_at, finalized_by, reopened_at, reopen_reason, snapshot_hash "
                             "from accounting_periods where client_id = ? order by year desc, month desc", [client_id])
