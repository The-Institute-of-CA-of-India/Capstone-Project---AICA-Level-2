"""CA firm workspace: profile/branding, clients, staff assignments, deadlines, dashboard."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from services import admin_service
from services.accounting_engine import ensure_chart_of_accounts
from services.audit_service import audit
from services.db import get_db, now_iso
from services.storage_service import get_storage
from services.tenancy import AuthContext, accessible_client_ids, require_client, require_firm
from utils.helpers import fy_bounds, fy_label_for, month_bounds
from utils.permissions import PermissionDenied
from utils.validators import validate_gstin, validate_pan

FIRM_EDITABLE = ("name", "legal_name", "frn", "gstin", "pan", "email", "phone", "address", "city", "state", "state_code",
                 "pincode")


def get_firm(ctx: AuthContext) -> dict:
    if not ctx.firm_id:
        raise PermissionDenied("No firm")
    return get_db().get("firms", ctx.firm_id)


def update_firm(ctx: AuthContext, values: dict) -> None:
    firm_id = require_firm(ctx, "manage_firm")
    upd = {k: (v.strip() if isinstance(v, str) else v) for k, v in values.items() if k in FIRM_EDITABLE}
    if upd.get("gstin"):
        ok, msg = validate_gstin(upd["gstin"])
        if not ok:
            raise ValueError(f"Firm GSTIN: {msg}")
    before = get_db().get("firms", firm_id)
    upd["updated_at"] = now_iso()
    get_db().update("firms", firm_id, upd)
    audit(ctx, "firm.updated", "firms", firm_id, before={k: before.get(k) for k in upd}, after=upd)


def update_firm_settings(ctx: AuthContext, settings_patch: dict) -> None:
    firm_id = require_firm(ctx, "manage_firm")
    firm = get_db().get("firms", firm_id)
    s = dict(firm.get("settings") or {})
    s.update(settings_patch)
    if not 1 <= int(s.get("submission_deadline_day", 5)) <= 28:
        raise ValueError("Deadline day must be between 1 and 28")
    get_db().update("firms", firm_id, {"settings": s, "updated_at": now_iso()})
    audit(ctx, "firm.settings", "firms", firm_id, after=settings_patch)


def upload_logo(ctx: AuthContext, filename: str, data: bytes) -> str:
    firm_id = require_firm(ctx, "manage_firm")
    ext = Path(filename).suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        raise ValueError("Logo must be PNG or JPG")
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("Logo must be under 2 MB")
    path = get_storage().put_overwrite(f"{firm_id}/_firm/logo{ext}", data)
    get_db().update("firms", firm_id, {"logo_path": path, "updated_at": now_iso()})
    audit(ctx, "firm.logo", "firms", firm_id)
    return path


def firm_logo_bytes(ctx: AuthContext) -> bytes | None:
    if not ctx.firm_id:
        return None
    firm = get_db().get("firms", ctx.firm_id)
    if not firm or not firm.get("logo_path"):
        return None
    try:
        return get_storage().get(firm["logo_path"])
    except Exception:
        return None


# ------------------------------------------------------------------ clients
CLIENT_FIELDS = ("name", "legal_name", "gstin", "pan", "business_type", "gst_registration_type", "state_code", "email",
                 "phone", "address", "fy_start_month", "submission_deadline_day", "status", "tan", "is_tds_deductor")


def _validate_client(values: dict) -> dict:
    v = {k: (val.strip() if isinstance(val, str) else val) for k, val in values.items() if k in CLIENT_FIELDS}
    if "name" in v and not v["name"]:
        raise ValueError("Client name is required")
    if v.get("gstin"):
        v["gstin"] = v["gstin"].upper()
        ok, msg = validate_gstin(v["gstin"])
        if not ok:
            raise ValueError(f"GSTIN: {msg}")
        v["state_code"] = v["gstin"][:2]
        v.setdefault("pan", v["gstin"][2:12])
    if v.get("pan") and not validate_pan(v["pan"]):
        raise ValueError("PAN format invalid")
    if v.get("tan"):
        v["tan"] = v["tan"].strip().upper()
    for k in ("gstin", "pan", "email", "phone", "address", "legal_name", "business_type", "tan"):
        if k in v and v[k] == "":
            v[k] = None
    return v


def create_client(ctx: AuthContext, values: dict) -> str:
    firm_id = require_firm(ctx, "manage_clients")
    admin_service.check_plan_limit(firm_id, "clients")
    v = _validate_client(values)
    db = get_db()
    with db.transaction():
        cid = db.insert("clients", {"firm_id": firm_id, **v, "created_at": now_iso(), "updated_at": now_iso()})
        ensure_chart_of_accounts(firm_id, cid)
        ensure_financial_year(firm_id, cid, fy_label_for(dt.date.today(), int(v.get("fy_start_month") or 4)),
                              int(v.get("fy_start_month") or 4))
        # Staff who create a client but cannot see all clients get assigned automatically.
        if not ctx.can("view_all_clients"):
            db.insert("client_staff_assignments", {"firm_id": firm_id, "client_id": cid, "staff_id": ctx.staff_id,
                                                   "created_at": now_iso()})
        audit(ctx, "client.created", "clients", cid, client_id=cid, after={"name": v["name"], "gstin": v.get("gstin")})
    return cid


def update_client(ctx: AuthContext, client_id: str, values: dict) -> None:
    client = require_client(ctx, client_id, "manage_clients")
    v = _validate_client(values)
    v["updated_at"] = now_iso()
    get_db().update("clients", client_id, v)
    audit(ctx, "client.updated", "clients", client_id, client_id=client_id,
          before={k: client.get(k) for k in v}, after=v)


def ensure_financial_year(firm_id: str, client_id: str, label: str, start_month: int = 4) -> str:
    db = get_db()
    row = db.fetchone("select id from financial_years where client_id = ? and label = ?", [client_id, label])
    if row:
        return row["id"]
    start, end = fy_bounds(label, start_month)
    return db.insert("financial_years", {"firm_id": firm_id, "client_id": client_id, "label": label, "start_date": start,
                                         "end_date": end, "created_at": now_iso()})


def list_financial_years(ctx: AuthContext, client_id: str) -> list[str]:
    client = require_client(ctx, client_id, "view")
    db = get_db()
    labels = [r["label"] for r in db.fetchall("select label from financial_years where client_id = ? order by label desc",
                                              [client_id])]
    cur = fy_label_for(dt.date.today(), client.get("fy_start_month") or 4)
    if cur not in labels:
        labels.insert(0, cur)
    return labels


def add_financial_year(ctx: AuthContext, client_id: str, label: str) -> None:
    client = require_client(ctx, client_id, "manage_clients")
    ensure_financial_year(client["firm_id"], client_id, label, client.get("fy_start_month") or 4)


def assign_staff(ctx: AuthContext, client_id: str, staff_ids: list[str]) -> None:
    client = require_client(ctx, client_id, "manage_clients")
    db = get_db()
    valid = {r["id"] for r in db.fetchall("select id from firm_staff where firm_id = ?", [client["firm_id"]])}
    if any(s not in valid for s in staff_ids):
        raise PermissionDenied("Staff member does not belong to your firm")
    with db.transaction():
        db.execute("delete from client_staff_assignments where client_id = ?", [client_id])
        for sid in staff_ids:
            db.insert("client_staff_assignments", {"firm_id": client["firm_id"], "client_id": client_id, "staff_id": sid,
                                                   "created_at": now_iso()})
    audit(ctx, "client.staff_assigned", "clients", client_id, client_id=client_id, after={"staff_ids": staff_ids})


def assigned_staff_ids(ctx: AuthContext, client_id: str) -> list[str]:
    require_client(ctx, client_id, "view")
    return [r["staff_id"] for r in get_db().fetchall("select staff_id from client_staff_assignments where client_id = ?",
                                                     [client_id])]


def client_users(ctx: AuthContext, client_id: str) -> list[dict]:
    require_client(ctx, client_id, "view")
    return get_db().fetchall("select cu.*, u.email, u.full_name, u.last_login_at from client_users cu "
                             "join user_profiles u on u.id = cu.user_id where cu.client_id = ?", [client_id])


def deadline_for(client: dict, year: int, month: int) -> dt.date:
    """Documents for month M are due on day N of month M+1."""
    firm = get_db().get("firms", client["firm_id"])
    day = client.get("submission_deadline_day") or (firm.get("settings") or {}).get("submission_deadline_day", 5)
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    return dt.date(ny, nm, int(day))


# ------------------------------------------------------------------ dashboard
def firm_dashboard(ctx: AuthContext, year: int, month: int, client_filter: list[str] | None = None,
                   staff_filter: str | None = None) -> dict:
    require_firm(ctx, "view")
    db = get_db()
    ids = accessible_client_ids(ctx)
    if staff_filter:
        ids = [r["client_id"] for r in db.fetchall("select client_id from client_staff_assignments where staff_id = ?",
                                                   [staff_filter]) if r["client_id"] in ids]
    if client_filter:
        ids = [i for i in ids if i in client_filter]
    out = {"total_clients": len(ids), "active_clients": 0, "pending_submissions": 0, "awaiting_processing": 0,
           "needs_review": 0, "unapproved_vouchers": 0, "unmatched_bank": 0, "gst_issues": 0, "finalized_months": 0,
           "per_client": []}
    if not ids:
        return out
    marks = ",".join("?" for _ in ids)
    start, end = month_bounds(year, month)
    clients = db.fetchall(f"select * from clients where id in ({marks}) order by name", ids)
    for c in clients:
        cid = c["id"]
        sub = db.fetchone("select status, submitted_at from document_submissions where client_id = ? and period_year = ? "
                          "and period_month = ? and status <> 'draft' order by submitted_at desc", [cid, year, month])
        counts = {r["status"]: r["n"] for r in db.fetchall(
            "select status, count(*) as n from documents where client_id = ? and period_year = ? and period_month = ? "
            "group by status", [cid, year, month])}
        unapproved = db.scalar("select count(*) from accounting_vouchers where client_id = ? and status = 'draft'", [cid])
        unmatched = db.scalar("select count(*) from bank_transactions where client_id = ? and match_status in "
                              "('unmatched','needs_review','suspense')", [cid])
        recon = db.fetchone("select summary from gst_reconciliations where client_id = ? and period = ? order by created_at desc",
                            [cid, f"{month:02d}{year}"])
        gst_issues = 0
        if recon and isinstance(recon["summary"], dict):
            gst_issues = sum(v for k, v in recon["summary"].get("counts", {}).items() if k != "matched")
        period = db.fetchone("select status from accounting_periods where client_id = ? and year = ? and month = ?",
                             [cid, year, month])
        total_docs = sum(counts.values())
        done = counts.get("approved", 0) + counts.get("finalized", 0) + counts.get("rejected", 0)
        if c["status"] == "active":
            out["active_clients"] += 1
        if not sub:
            out["pending_submissions"] += 1
        out["awaiting_processing"] += counts.get("uploaded", 0) + counts.get("processing", 0)
        out["needs_review"] += counts.get("needs_review", 0) + counts.get("processed", 0)
        out["unapproved_vouchers"] += unapproved
        out["unmatched_bank"] += unmatched
        out["gst_issues"] += gst_issues
        out["finalized_months"] += db.scalar("select count(*) from accounting_periods where client_id = ? and status = 'finalized'",
                                             [cid])
        out["per_client"].append({
            "client_id": cid, "client": c["name"], "submission": sub["status"] if sub else "not submitted",
            "submitted_at": sub["submitted_at"] if sub else None, "documents": total_docs,
            "pending_review": counts.get("needs_review", 0) + counts.get("processed", 0),
            "progress_pct": round(100 * done / total_docs) if total_docs else 0,
            "unapproved_vouchers": unapproved, "unmatched_bank": unmatched, "gst_issues": gst_issues,
            "month_status": period["status"] if period else "open", "deadline": deadline_for(c, year, month),
        })
    return out


def staff_activity(ctx: AuthContext, days: int = 7) -> list[dict]:
    firm_id = require_firm(ctx, "view")
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
    return get_db().fetchall(
        "select u.full_name, a.action, count(*) as n from audit_logs a join user_profiles u on u.id = a.user_id "
        "where a.firm_id = ? and a.created_at >= ? group by u.full_name, a.action order by n desc", [firm_id, since])
