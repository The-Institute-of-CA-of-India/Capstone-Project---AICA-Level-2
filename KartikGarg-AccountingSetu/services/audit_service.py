"""Append-only audit trail and system error log."""
from __future__ import annotations

import logging
import traceback

from services.db import get_db, now_iso

log = logging.getLogger("accounting_setu")


def audit(ctx, action: str, entity_type: str, entity_id: str | None = None, *, before=None, after=None,
          firm_id: str | None = None, client_id: str | None = None) -> None:
    db = get_db()
    db.insert("audit_logs", {
        "firm_id": firm_id if firm_id is not None else getattr(ctx, "firm_id", None),
        "client_id": client_id,
        "user_id": getattr(ctx, "user_id", None),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "before_data": before,
        "after_data": after,
        "created_at": now_iso(),
    })


def log_error(source: str, exc: BaseException | str, *, context: dict | None = None, firm_id=None, user_id=None,
              level: str = "ERROR") -> None:
    msg = str(exc)
    ctx = dict(context or {})
    if isinstance(exc, BaseException):
        ctx["traceback"] = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-4000:]
    log.error("%s: %s", source, msg)
    try:
        get_db().insert("system_logs", {"level": level, "source": source, "message": msg[:2000], "context": ctx,
                                        "firm_id": firm_id, "user_id": user_id, "created_at": now_iso()})
    except Exception:  # never let logging break the caller
        log.exception("failed to write system log")


def list_audit(ctx, *, client_id: str | None = None, limit: int = 500) -> list[dict]:
    from services.tenancy import require_client

    db = get_db()
    if ctx.is_super_admin:
        if client_id:
            return []
        return db.fetchall("select * from audit_logs order by created_at desc limit ?", [limit])
    ctx.require("view_audit")
    if client_id:
        require_client(ctx, client_id, "view_audit")
        return db.fetchall("select * from audit_logs where firm_id = ? and client_id = ? order by created_at desc limit ?",
                           [ctx.firm_id, client_id, limit])
    return db.fetchall("select * from audit_logs where firm_id = ? order by created_at desc limit ?", [ctx.firm_id, limit])
