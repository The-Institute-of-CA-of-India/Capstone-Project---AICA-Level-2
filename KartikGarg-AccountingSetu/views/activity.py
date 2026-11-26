"""Notifications and audit trail pages."""
from __future__ import annotations

import streamlit as st

from services import audit_service, notification_service
from ui.common import ctx, page_header, selected_client_id, table


def notifications_page():
    page_header("Notifications")
    c = ctx()
    if st.button("Mark all as read"):
        notification_service.mark_read(c)
        st.rerun()
    items = notification_service.list_notifications(c, limit=100)
    if not items:
        st.info("No notifications.")
    for n in items:
        icon = "🔵" if not n["is_read"] else "⚪"
        st.markdown(f"{icon} **{n['title']}** — {n.get('body') or ''}  \n<span style='color:#64748B;font-size:.8rem'>{str(n['created_at'])[:16]}</span>",
                    unsafe_allow_html=True)


def audit_page():
    page_header("Audit trail", "Append-only log of privileged operations in your firm.")
    scope = st.radio("Scope", ["Whole firm", "Selected client"], horizontal=True)
    rows = audit_service.list_audit(ctx(), client_id=selected_client_id() if scope == "Selected client" else None)
    action_f = st.text_input("Filter by action (e.g. voucher, period, document)")
    if action_f:
        rows = [r for r in rows if action_f.lower() in r["action"].lower()]
    table([{"time": str(r["created_at"])[:19], "action": r["action"], "entity": r["entity_type"], "entity_ref": r.get("entity_id"),
            "before": r.get("before_data"), "after": r.get("after_data")} for r in rows])
