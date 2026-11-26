"""Super Admin (platform owner) pages."""
from __future__ import annotations

from decimal import Decimal

import plotly.express as px
import streamlit as st

from services import admin_service, audit_service
from ui.common import action, badge, ctx, kpi, page_header, table


def overview():
    page_header("Platform overview", "Aggregate usage across all CA firms. Tenant financial data is not visible here by design.")
    m = admin_service.platform_metrics(ctx())
    if m["pending_firms"]:
        st.markdown(f"<div class='as-warn'>🔔 <b>{m['pending_firms']} CA firm(s) waiting for your approval.</b> "
                    "Open <b>CA Firms</b> from the sidebar to review and approve them.</div>", unsafe_allow_html=True)
        st.write("")
    cols = st.columns(4)
    kpi(cols[0], "CA firms", f"{m['firms']} ({m['active_firms']} active)")
    kpi(cols[1], "Pending approvals", m["pending_firms"])
    kpi(cols[2], "Clients", m["clients"])
    kpi(cols[3], "Users", m["users"])
    cols = st.columns(4)
    kpi(cols[0], "Staff accounts", m["staff"])
    kpi(cols[1], "Documents", m["documents"])
    kpi(cols[2], "Vouchers", m["vouchers"])
    kpi(cols[3], "Errors (7 days)", m["errors_7d"])
    firms = admin_service.list_firms(ctx())
    if firms:
        st.subheader("Usage by firm")
        fig = px.bar([{"firm": f["name"], "clients": f["client_count"], "documents": f["document_count"]} for f in firms],
                     x="firm", y=["clients", "documents"], barmode="group", color_discrete_sequence=["#0B2545", "#C9A227"])
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), legend_title=None)
        st.plotly_chart(fig, width="stretch")


def firms_page():
    page_header("CA firms", "Approve, suspend, activate or deactivate firm workspaces and manage their subscription.")
    firms = admin_service.list_firms(ctx())
    pending_count = sum(1 for f in firms if f["status"] == "pending")
    if pending_count:
        st.markdown(f"<div class='as-warn'>🔔 <b>{pending_count} CA firm(s) are waiting for approval</b> before they can "
                    "work. Review each one below and click <b>Approve / Activate</b>.</div>", unsafe_allow_html=True)
        st.write("")
    default_filter = "pending" if pending_count else "all"
    status_filter = st.segmented_control("Status", ["all", "pending", "active", "suspended", "deactivated"], default=default_filter)
    for f in firms:
        if status_filter not in (None, "all") and f["status"] != status_filter:
            continue
        with st.expander(f"{f['name']} — {f['status'].upper()} · {f['plan']} ({f['subscription_status']})",
                         expanded=(f["status"] == "pending")):
            st.markdown(badge(f["status"]), unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Email:** {f['email']}  \n**Phone:** {f.get('phone') or '—'}  \n**FRN:** {f.get('frn') or '—'}")
            c2.write(f"**Clients:** {f['client_count']}  \n**Staff:** {f['staff_count']}  \n**Documents:** {f['document_count']}")
            c3.write(f"**Registered:** {str(f['created_at'])[:10]}  \n**Subscription ends:** {f.get('subscription_end') or '—'}")
            reason = st.text_input("Reason / note", key=f"r_{f['id']}")
            b = st.columns(4)
            for i, (label, status) in enumerate([("Approve / Activate", "active"), ("Suspend", "suspended"),
                                                 ("Deactivate", "deactivated"), ("Mark pending", "pending")]):
                if f["status"] != status and b[i].button(label, key=f"{status}_{f['id']}"):
                    with action(f"Firm set to {status}"):
                        admin_service.set_firm_status(ctx(), f["id"], status, reason)
                        st.rerun()
            st.markdown("**Subscription**")
            plans = admin_service.list_plans()
            p1, p2, p3, p4 = st.columns(4)
            code = p1.selectbox("Plan", [p["code"] for p in plans], key=f"plan_{f['id']}")
            st_ = p2.selectbox("Status", ["active", "trial", "past_due"], key=f"ps_{f['id']}")
            months = p3.number_input("Months", 1, 36, 12, key=f"pm_{f['id']}")
            if p4.button("Assign plan", key=f"pa_{f['id']}"):
                with action("Plan assigned"):
                    admin_service.assign_plan(ctx(), f["id"], code, st_, int(months))
                    st.rerun()


def plans_page():
    page_header("Subscription plans & billing", "Plan limits are enforced when firms add clients, staff and documents.")
    plans = admin_service.list_plans()
    table(plans, drop_ids=True)
    st.subheader("Create or update a plan")
    with st.form("plan"):
        c1, c2, c3 = st.columns(3)
        code = c1.text_input("Code (unique)")
        name = c2.text_input("Name")
        price = c3.number_input("Price per month (₹)", 0.0, step=100.0)
        mc = c1.number_input("Max clients", 1, 100000, 25)
        ms = c2.number_input("Max staff", 1, 10000, 5)
        md = c3.number_input("Max documents / month", 1, 10000000, 2000)
        active = st.checkbox("Active", True)
        if st.form_submit_button("Save plan", type="primary"):
            with action("Plan saved"):
                admin_service.upsert_plan(ctx(), code.strip(), name.strip(), int(mc), int(ms), int(md), Decimal(str(price)), active)
    st.subheader("Billing records")
    st.caption("Payment collection is not integrated; subscription amounts are recorded for billing follow-up.")
    rows = []
    for f in admin_service.list_firms(ctx()):
        sub = admin_service.current_subscription(f["id"])
        if sub:
            rows.append({"firm": f["name"], "plan": sub["plan_name"], "status": sub["status"], "start": sub["start_date"],
                         "end": sub["end_date"], "amount": sub["amount"]})
    table(rows)


def settings_page():
    page_header("Platform settings", "Global configuration and feature switches for all firms.")
    current = admin_service.get_platform_settings(ctx())
    feats = current.get("features", {}) if isinstance(current.get("features"), dict) else {}
    with st.form("features"):
        st.markdown("**Feature switches**")
        ai = st.checkbox("AI financial assistant", feats.get("assistant", True))
        tally = st.checkbox("Tally export", feats.get("tally_export", True))
        gst = st.checkbox("GST module", feats.get("gst", True))
        reg = st.checkbox("Allow new firm registrations", feats.get("registrations", True))
        appr = st.checkbox("New CA firms need my approval before they can work", feats.get("require_firm_approval", True))
        notice = st.text_area("Announcement shown to all firms", current.get("announcement", {}).get("text", "")
                              if isinstance(current.get("announcement"), dict) else "")
        if st.form_submit_button("Save", type="primary"):
            with action("Settings saved"):
                admin_service.set_platform_setting(ctx(), "features", {"assistant": ai, "tally_export": tally, "gst": gst,
                                                                       "registrations": reg, "require_firm_approval": appr})
                admin_service.set_platform_setting(ctx(), "announcement", {"text": notice})
    from config import settings as cfg

    st.subheader("Runtime configuration")
    st.write(f"Backend: **{cfg.backend}** · AI provider: **{'Anthropic Claude' if cfg.anthropic_enabled else 'local rules'}** · "
             f"OCR: **{'Tesseract' if cfg.tesseract_available else 'not installed'}** · GST rules: **{cfg.gst_rules_version}**")
    missing = cfg.missing_configuration()
    if missing:
        st.markdown("<div class='as-warn'><b>Missing / optional configuration</b><br>" + "<br>".join(missing) + "</div>",
                    unsafe_allow_html=True)


def logs_page():
    page_header("System logs & audit", "Errors captured by the application and privileged platform actions.")
    t1, t2 = st.tabs(["Error reports", "Audit trail"])
    with t1:
        logs = admin_service.list_system_logs(ctx())
        for lg in logs[:200]:
            with st.expander(f"{str(lg['created_at'])[:19]} · {lg['level']} · {lg['source']} · {lg['message'][:90]}"):
                st.json(lg.get("context") or {})
        if not logs:
            st.success("No errors recorded.")
    with t2:
        table(audit_service.list_audit(ctx(), limit=500), drop_ids=False)
