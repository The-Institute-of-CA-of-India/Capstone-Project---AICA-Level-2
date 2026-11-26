"""In-app notifications + optional email delivery.

Email uses SMTP when configured. Without SMTP, messages are written to data/outbox/ as .eml files
(clearly a local-development fallback — nothing is sent anywhere).
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from config import BASE_DIR, settings
from services.db import get_db, now_iso, system_identity

OUTBOX = BASE_DIR / "data" / "outbox"


def notify_user(user_id: str, title: str, body: str = "", *, firm_id=None, client_id=None, link=None) -> None:
    get_db().insert("notifications", {"user_id": user_id, "firm_id": firm_id, "client_id": client_id,
                                      "audience": "user", "title": title, "body": body, "link": link,
                                      "created_at": now_iso()})


def notify_firm(firm_id: str, title: str, body: str = "", *, client_id=None, permission: str = "review_documents",
                link=None) -> int:
    """Notify every active staff member of the firm who can access the client (and has ``permission``)."""
    from utils.permissions import effective_permissions

    with system_identity():  # recipients are resolved server-side; callers are already authorized for the client
        return _notify_firm(firm_id, title, body, client_id, permission, link, effective_permissions)


def _notify_firm(firm_id, title, body, client_id, permission, link, effective_permissions) -> int:
    db = get_db()
    staff = db.fetchall("select * from firm_staff where firm_id = ? and is_active = ?", [firm_id, True])
    n = 0
    for s in staff:
        perms = effective_permissions(s["role"], s.get("permissions") or {})
        if permission not in perms:
            continue
        if client_id and "view_all_clients" not in perms:
            assigned = db.fetchone("select 1 as x from client_staff_assignments where staff_id = ? and client_id = ?",
                                   [s["id"], client_id])
            if not assigned:
                continue
        notify_user(s["user_id"], title, body, firm_id=firm_id, client_id=client_id, link=link)
        n += 1
    return n


def notify_super_admins(title: str, body: str = "", *, link=None) -> int:
    """Notify every active Super Admin — used for platform-level events (e.g. a new CA firm awaiting approval)."""
    with system_identity():
        return _notify_super_admins(title, body, link)


def _notify_super_admins(title, body, link) -> int:
    db = get_db()
    admins = db.fetchall("select id from user_profiles where is_super_admin = ? and is_active = ?", [True, True])
    for a in admins:
        notify_user(a["id"], title, body, link=link)
    return len(admins)


def notify_client_users(client_id: str, title: str, body: str = "", *, link=None) -> int:
    with system_identity():
        return _notify_client_users(client_id, title, body, link)


def _notify_client_users(client_id, title, body, link) -> int:
    db = get_db()
    users = db.fetchall("select * from client_users where client_id = ? and is_active = ?", [client_id, True])
    for u in users:
        notify_user(u["user_id"], title, body, firm_id=u["firm_id"], client_id=client_id, link=link)
    return len(users)


def list_notifications(ctx, unread_only: bool = False, limit: int = 50) -> list[dict]:
    sql = "select * from notifications where user_id = ?"
    if unread_only:
        sql += " and is_read = 0" if get_db().dialect == "sqlite" else " and is_read = false"
    return get_db().fetchall(sql + " order by created_at desc limit ?", [ctx.user_id, limit])


def mark_read(ctx, notification_id: str | None = None) -> None:
    db = get_db()
    if notification_id:
        db.execute("update notifications set is_read = ? where id = ? and user_id = ?", [True, notification_id, ctx.user_id])
    else:
        db.execute("update notifications set is_read = ? where user_id = ?", [True, ctx.user_id])


def send_email(to: str, subject: str, body: str) -> str:
    """Send an email. Returns 'smtp' or the outbox file path used in local fallback."""
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or "no-reply@accounting-setu.local"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if settings.smtp_host:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
            s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)
        return "smtp"
    OUTBOX.mkdir(parents=True, exist_ok=True)
    path = OUTBOX / f"{now_iso().replace(':', '')}_{to.replace('@', '_at_')}.eml"
    Path(path).write_bytes(bytes(msg))
    return str(path)
