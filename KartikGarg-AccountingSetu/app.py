"""Accounting Setu — Streamlit entry point.

    streamlit run app.py

Identity is resolved on every rerun from the stored user id via membership tables
(auth_service.build_context), so suspensions, role and permission changes apply immediately.
"""
from __future__ import annotations

import datetime as dt
import time

import streamlit as st

st.set_page_config(page_title="Accounting Setu", page_icon="📘", layout="wide", initial_sidebar_state="expanded")

from config import settings  # noqa: E402
from services import auth_service, firm_service, notification_service  # noqa: E402
from services.auth_service import AuthError  # noqa: E402
from services.db import get_db  # noqa: E402
from services.tenancy import list_clients  # noqa: E402
from ui.common import inject_css  # noqa: E402
from utils.helpers import fy_label_for  # noqa: E402

inject_css()


@st.cache_resource
def _bootstrap() -> str | None:
    try:
        get_db()
        auth_service.ensure_bootstrap()
        if settings.load_demo_data:
            from scripts import seed_demo

            seed_demo.seed(quiet=True)
        return None
    except Exception as exc:  # configuration problems are shown on screen
        return str(exc)


err = _bootstrap()
if err:
    st.error(f"Startup failed: {err}")
    st.info("Check your .env configuration (see README → Configuration).")
    st.stop()


def logout():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()


def _session_ctx():
    uid = st.session_state.get("user_id")
    if not uid:
        return None
    now = time.time()
    last = st.session_state.get("last_seen", now)
    if now - last > settings.session_timeout_minutes * 60:
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.warning("Your session expired. Please sign in again.")
        return None
    st.session_state["last_seen"] = now
    auth_service.activate_request_identity(None)  # resolve membership as system, then bind the user's RLS identity
    try:
        c = auth_service.build_context(uid, st.session_state.get("firm_pref"))
    except AuthError as exc:
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.error(str(exc))
        return None
    auth_service.activate_request_identity(c)
    st.session_state["ctx"] = c
    return c


def _cached_logo(c):
    """Fetching the logo from Storage on every click is the single slowest thing on a remote (Supabase) backend;
    cache the bytes in this browser session and only re-fetch when the stored path actually changes."""
    firm = get_db().get("firms", c.firm_id)
    path = (firm or {}).get("logo_path")
    cache = st.session_state.get("_logo_cache")
    if cache and cache[0] == path:
        return cache[1]
    data = firm_service.firm_logo_bytes(c) if path else None
    st.session_state["_logo_cache"] = (path, data)
    return data


def sidebar(c):
    with st.sidebar:
        st.markdown("<div class='as-brand'>Accounting <span>Setu</span></div><div class='as-tag'>From Documents to Complete Accounting.</div>",
                    unsafe_allow_html=True)
        if c.firm_id and not c.is_super_admin:
            logo = _cached_logo(c)
            if logo:
                st.image(logo, width=120)
            st.markdown(f"**{c.firm_name}**")
        st.caption(f"{c.full_name} · {c.role.replace('_', ' ').title() if c.role else c.kind.replace('_', ' ').title()}")
        unread = len(notification_service.list_notifications(c, unread_only=True))
        if unread:
            st.caption(f"🔔 {unread} unread notification(s)")
        if c.is_staff and c.firm_status == "active":
            clients = list_clients(c)
            if clients:
                ids = [x["id"] for x in clients]
                names = {x["id"]: x["name"] for x in clients}
                cur = st.session_state.get("client_id")
                idx = ids.index(cur) if cur in ids else 0
                st.session_state["client_id"] = st.selectbox("Client", ids, index=idx, format_func=lambda i: names[i])
                client = next(x for x in clients if x["id"] == st.session_state["client_id"])
                fys = firm_service.list_financial_years(c, client["id"])
                st.session_state["fy"] = st.selectbox("Financial year", fys, index=0)
                from utils.helpers import fy_months
                months = fy_months(st.session_state["fy"], client.get("fy_start_month") or 4)
                today = dt.date.today()
                default = next((i for i, ym in enumerate(months) if ym == (today.year, today.month)), len(months) - 1)
                ym = st.selectbox("Month", months, index=default, format_func=lambda t: dt.date(t[0], t[1], 1).strftime("%b %Y"))
                st.session_state["year"], st.session_state["month"] = ym
            else:
                st.session_state["client_id"] = None
                st.caption("No clients yet.")
        st.divider()
        if st.button("Sign out", width="stretch"):
            logout()


def build_pages(c):
    from views import (accounting, assistant, bank, client_portal, client_workspace, clients, dashboard, documents,
                       finalization, firm_settings, gst, reports, staff, super_admin, tally, activity)
    from views.auth_views import change_password_page

    P = st.Page
    account = [P(change_password_page, title="Change password", icon="🔑", url_path="password"),
               P(activity.notifications_page, title="Notifications", icon="🔔", url_path="notifications")]
    if c.is_super_admin:
        return {"Platform": [P(super_admin.overview, title="Overview", icon="📊", url_path="overview", default=True),
                             P(super_admin.firms_page, title="CA Firms", icon="🏢", url_path="firms"),
                             P(super_admin.plans_page, title="Plans & Billing", icon="💳", url_path="plans"),
                             P(super_admin.settings_page, title="Platform Settings", icon="⚙️", url_path="platform-settings"),
                             P(super_admin.logs_page, title="System Logs & Audit", icon="🧾", url_path="logs")],
                "Account": account}
    if c.is_client:
        return {"My Business": [P(client_portal.dashboard, title="Dashboard", icon="🏠", url_path="home", default=True),
                                P(client_portal.submit_page, title="Submit Documents", icon="📤", url_path="submit"),
                                P(client_portal.my_documents, title="My Documents", icon="📁", url_path="my-documents"),
                                P(client_portal.reports_page, title="Reports", icon="📑", url_path="my-reports"),
                                P(client_portal.clarifications_page, title="Questions from CA", icon="💬", url_path="questions"),
                                P(assistant.page, title="Ask Setu (AI)", icon="✨", url_path="assistant"),
                                P(client_portal.profile_page, title="Business Profile", icon="🪪", url_path="profile")],
                "Account": account}
    if c.firm_status != "active":
        return {"Workspace": [P(dashboard.inactive_page, title="Workspace status", icon="⏳", url_path="status", default=True)],
                "Account": account}
    can = c.can
    work = [P(client_workspace.page, title="Client Workspace", icon="🏢", url_path="workspace", default=True),
           P(dashboard.page, title="Firm Dashboard (all clients)", icon="📊", url_path="dashboard")]
    if can("review_documents") or can("upload_documents"):
        work.append(P(documents.page, title="Documents & Review", icon="🗂️", url_path="documents"))
    work.append(P(accounting.page, title="Accounting", icon="📒", url_path="accounting"))
    if can("bank_reconcile") or can("view"):
        work.append(P(bank.page, title="Bank Reconciliation", icon="🏦", url_path="bank"))
    work.append(P(gst.page, title="GST", icon="🧮", url_path="gst"))
    work.append(P(reports.page, title="Reports", icon="📑", url_path="reports"))
    if can("export_tally"):
        work.append(P(tally.page, title="Tally Export", icon="📤", url_path="tally"))
    work.append(P(finalization.page, title="Month Finalization", icon="🔒", url_path="finalize"))
    work.append(P(assistant.page, title="Ask Setu (AI)", icon="✨", url_path="assistant"))
    admin = [P(clients.page, title="Clients", icon="👥", url_path="clients")]
    if can("manage_staff") or can("view"):
        admin.append(P(staff.page, title="Staff", icon="🧑‍💼", url_path="staff"))
    if can("manage_firm"):
        admin.append(P(firm_settings.page, title="Firm Settings", icon="⚙️", url_path="firm-settings"))
    if can("view_audit"):
        admin.append(P(activity.audit_page, title="Audit Trail", icon="🧾", url_path="audit"))
    return {"Work": work, "Firm": admin, "Account": account}


c = _session_ctx()
if c is None:
    from views.auth_views import first_run_setup, login_page

    if not auth_service.super_admin_exists():
        st.navigation([st.Page(first_run_setup, title="Setup", url_path="setup")], position="hidden").run()
    else:
        st.navigation([st.Page(login_page, title="Sign in", url_path="login")], position="hidden").run()
    st.stop()

sidebar(c)
if auth_service.must_change_password(c):
    from views.auth_views import change_password_page

    st.navigation([st.Page(change_password_page, title="Change password", url_path="password")], position="hidden").run()
    st.stop()

st.navigation(build_pages(c)).run()
