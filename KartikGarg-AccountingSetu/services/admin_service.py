"""Super Admin (platform owner) operations and subscription/plan management.

Super Admin sees firm metadata, subscriptions and aggregate usage only — never a client's
financial documents or books (tenant data stays private to the CA firm).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from services.audit_service import audit
from services.db import get_db, now_iso, system_identity
from utils.permissions import PermissionDenied

DEFAULT_PLANS = [
    {"code": "trial", "name": "Trial (30 days)", "max_clients": 5, "max_staff": 3, "max_documents_per_month": 300,
     "price_monthly": Decimal("0.00")},
    {"code": "starter", "name": "Starter", "max_clients": 25, "max_staff": 5, "max_documents_per_month": 2000,
     "price_monthly": Decimal("2999.00")},
    {"code": "professional", "name": "Professional", "max_clients": 100, "max_staff": 20,
     "max_documents_per_month": 10000, "price_monthly": Decimal("7999.00")},
    {"code": "enterprise", "name": "Enterprise", "max_clients": 1000, "max_staff": 200,
     "max_documents_per_month": 100000, "price_monthly": Decimal("24999.00")},
]


class PlanLimitExceeded(Exception):
    pass


def ensure_default_plans() -> None:
    db = get_db()
    for p in DEFAULT_PLANS:
        if not db.fetchone("select id from subscription_plans where code = ?", [p["code"]]):
            db.insert("subscription_plans", {**p, "features": {}, "created_at": now_iso()})


def start_trial(firm_id: str) -> None:
    db = get_db()
    ensure_default_plans()
    plan = db.fetchone("select * from subscription_plans where code = 'trial'")
    today = dt.date.today()
    db.insert("firm_subscriptions", {"firm_id": firm_id, "plan_id": plan["id"], "status": "trial", "start_date": today,
                                     "end_date": today + dt.timedelta(days=30), "amount": Decimal("0.00"),
                                     "created_at": now_iso()})


def current_subscription(firm_id: str) -> dict | None:
    with system_identity():  # platform metadata; callers are already scoped to their own firm
        return _current_subscription(firm_id)


def _current_subscription(firm_id: str) -> dict | None:
    return get_db().fetchone(
        "select s.*, p.code as plan_code, p.name as plan_name, p.max_clients, p.max_staff, p.max_documents_per_month "
        "from firm_subscriptions s join subscription_plans p on p.id = s.plan_id where s.firm_id = ? "
        "and s.status in ('trial','active','past_due') order by s.created_at desc", [firm_id])


def check_plan_limit(firm_id: str, kind: str) -> None:
    with system_identity():  # counts across the firm, independent of the caller's row visibility
        _check_plan_limit(firm_id, kind)


def _check_plan_limit(firm_id: str, kind: str) -> None:
    sub = _current_subscription(firm_id)
    if not sub:
        raise PlanLimitExceeded("No active subscription. Contact the platform administrator.")
    db = get_db()
    if kind == "clients":
        n = db.scalar("select count(*) as n from clients where firm_id = ?", [firm_id])
        if n >= sub["max_clients"]:
            raise PlanLimitExceeded(f"Plan limit reached: {sub['max_clients']} clients on {sub['plan_name']}.")
    elif kind == "staff":
        n = db.scalar("select count(*) as n from firm_staff where firm_id = ? and is_active = ?", [firm_id, True])
        if n >= sub["max_staff"]:
            raise PlanLimitExceeded(f"Plan limit reached: {sub['max_staff']} staff on {sub['plan_name']}.")
    elif kind == "documents":
        start = dt.date.today().replace(day=1).isoformat()
        n = db.scalar("select count(*) as n from documents where firm_id = ? and uploaded_at >= ?", [firm_id, start])
        if n >= sub["max_documents_per_month"]:
            raise PlanLimitExceeded("Monthly document limit reached for your plan.")


# ------------------------------------------------------------------ super admin
def list_firms(ctx) -> list[dict]:
    ctx.require_super_admin()
    with system_identity():  # aggregate counts only; no tenant records are returned
        return _list_firms()


def _list_firms() -> list[dict]:
    # A handful of bulk, grouped queries instead of ~4 round trips per firm (each one costs a network hop on Supabase).
    db = get_db()
    firms = db.fetchall("select * from firms order by created_at desc")
    if not firms:
        return firms
    ids = [f["id"] for f in firms]
    marks = ",".join("?" for _ in ids)
    clients = {r["firm_id"]: r["n"] for r in db.fetchall(f"select firm_id, count(*) as n from clients where firm_id in ({marks}) group by firm_id", ids)}
    staff = {r["firm_id"]: r["n"] for r in db.fetchall(f"select firm_id, count(*) as n from firm_staff where firm_id in ({marks}) group by firm_id", ids)}
    docs = {r["firm_id"]: r["n"] for r in db.fetchall(f"select firm_id, count(*) as n from documents where firm_id in ({marks}) group by firm_id", ids)}
    subs = {}
    for s in db.fetchall(
            f"select s.firm_id, s.status, s.end_date, p.name as plan_name, s.created_at from firm_subscriptions s "
            f"join subscription_plans p on p.id = s.plan_id where s.firm_id in ({marks}) and s.status in "
            f"('trial','active','past_due') order by s.created_at", ids):
        subs[s["firm_id"]] = s  # keep the latest (rows are ordered oldest→newest, so the last write wins)
    for f in firms:
        f["client_count"] = clients.get(f["id"], 0)
        f["staff_count"] = staff.get(f["id"], 0)
        f["document_count"] = docs.get(f["id"], 0)
        sub = subs.get(f["id"])
        f["plan"] = sub["plan_name"] if sub else "—"
        f["subscription_status"] = sub["status"] if sub else "none"
        f["subscription_end"] = sub["end_date"] if sub else None
    return firms


def set_firm_status(ctx, firm_id: str, status: str, reason: str = "") -> None:
    ctx.require_super_admin()
    if status not in {"active", "suspended", "deactivated", "pending"}:
        raise ValueError("invalid status")
    db = get_db()
    firm = db.get("firms", firm_id)
    if not firm:
        raise ValueError("Firm not found")
    db.update("firms", firm_id, {"status": status, "updated_at": now_iso()})
    audit(ctx, f"firm.{status}", "firms", firm_id, firm_id=firm_id, before={"status": firm["status"]},
          after={"status": status, "reason": reason})
    from services.notification_service import notify_firm

    notify_firm(firm_id, f"Workspace status changed to {status}", reason or "", permission="view")


def assign_plan(ctx, firm_id: str, plan_code: str, status: str = "active", months: int = 12,
                amount: Decimal | None = None, notes: str = "") -> None:
    ctx.require_super_admin()
    db = get_db()
    plan = db.fetchone("select * from subscription_plans where code = ?", [plan_code])
    if not plan:
        raise ValueError("Unknown plan")
    with db.transaction():
        db.execute("update firm_subscriptions set status = 'cancelled' where firm_id = ? and status in ('trial','active','past_due')",
                   [firm_id])
        today = dt.date.today()
        end = today + dt.timedelta(days=30 * months)
        db.insert("firm_subscriptions", {"firm_id": firm_id, "plan_id": plan["id"], "status": status, "start_date": today,
                                         "end_date": end, "amount": amount if amount is not None else plan["price_monthly"] * months,
                                         "notes": notes, "created_at": now_iso()})
        audit(ctx, "subscription.assigned", "firm_subscriptions", firm_id, firm_id=firm_id,
              after={"plan": plan_code, "status": status, "months": months})


def list_plans(ctx=None) -> list[dict]:
    return get_db().fetchall("select * from subscription_plans order by price_monthly")


def upsert_plan(ctx, code: str, name: str, max_clients: int, max_staff: int, max_docs: int, price: Decimal,
                is_active: bool = True) -> None:
    ctx.require_super_admin()
    db = get_db()
    existing = db.fetchone("select id from subscription_plans where code = ?", [code])
    vals = {"name": name, "max_clients": max_clients, "max_staff": max_staff, "max_documents_per_month": max_docs,
            "price_monthly": price, "is_active": is_active}
    if existing:
        db.update("subscription_plans", existing["id"], vals)
    else:
        db.insert("subscription_plans", {"code": code, **vals, "features": {}, "created_at": now_iso()})
    audit(ctx, "plan.upserted", "subscription_plans", code, after={k: str(v) for k, v in vals.items()})


def platform_metrics(ctx) -> dict:
    ctx.require_super_admin()
    with system_identity():
        return _platform_metrics()


def _platform_metrics() -> dict:
    # One round trip for every count instead of nine separate ones (each one costs a full network hop on Supabase).
    db = get_db()
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).isoformat()
    row = db.fetchone(
        "select (select count(*) from firms) as firms, "
        "(select count(*) from firms where status = 'active') as active_firms, "
        "(select count(*) from firms where status = 'pending') as pending_firms, "
        "(select count(*) from user_profiles) as users, (select count(*) from firm_staff) as staff, "
        "(select count(*) from clients) as clients, (select count(*) from documents) as documents, "
        "(select count(*) from accounting_vouchers) as vouchers, "
        "(select count(*) from system_logs where created_at >= ?) as errors_7d", [since])
    return {k: v or 0 for k, v in row.items()}


def get_platform_settings(ctx) -> dict:
    ctx.require_super_admin()
    rows = get_db().fetchall("select * from platform_settings")
    return {r["key"]: r["value"] for r in rows}


def set_platform_setting(ctx, key: str, value: dict) -> None:
    ctx.require_super_admin()
    db = get_db()
    if db.fetchone("select key from platform_settings where key = ?", [key]):
        db.update("platform_settings", key, {"value": value, "updated_by": ctx.user_id, "updated_at": now_iso()}, key="key")
    else:
        db.insert("platform_settings", {"key": key, "value": value, "updated_by": ctx.user_id, "updated_at": now_iso()})
    audit(ctx, "platform.setting", "platform_settings", key, after=value)


def feature_enabled(key: str, default: bool = True) -> bool:
    with system_identity():
        row = get_db().fetchone("select value from platform_settings where key = 'features'")
    if not row or not isinstance(row["value"], dict):
        return default
    return bool(row["value"].get(key, default))


def list_system_logs(ctx, limit: int = 300) -> list[dict]:
    ctx.require_super_admin()
    return get_db().fetchall("select * from system_logs order by created_at desc limit ?", [limit])


def require_not_super_admin(ctx) -> None:
    if ctx.is_super_admin:
        raise PermissionDenied("Super Admin does not access tenant financial data.")
