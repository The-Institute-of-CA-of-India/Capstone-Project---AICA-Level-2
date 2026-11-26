"""CA firm dashboard."""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from services import admin_service, auth_service, firm_service
from services.tenancy import list_clients
from ui.common import ctx, kpi, page_header, selected_period, table


def inactive_page():
    c = ctx()
    page_header("Workspace status")
    if c.firm_status == "pending":
        st.info("Your firm registration has been received and is awaiting approval by the platform administrator. "
                "You will be able to add clients and staff once it is approved.")
    else:
        st.error(f"Your firm workspace is **{c.firm_status}**. Contact the platform administrator.")


def page():
    c = ctx()
    y, m = selected_period()
    page_header("Firm dashboard", f"{c.firm_name} · period {m:02d}/{y}")
    ann = None
    try:
        from services.db import get_db

        row = get_db().fetchone("select value from platform_settings where key = 'announcement'")
        ann = (row or {}).get("value", {}).get("text") if row else None
    except Exception:
        pass
    if ann:
        st.info(ann)
    sub = admin_service.current_subscription(c.firm_id)
    if sub and sub["status"] == "trial":
        st.caption(f"Plan: {sub['plan_name']} until {sub['end_date']}")
    from services import firm_service as _fs

    firm = _fs.get_firm(c)
    if firm.get("client_code"):
        st.info(f"**Your secret client code: `{firm['client_code']}`** · Firm serial no. {firm.get('serial_no')}  \n"
                "Share this code with your clients. They enter it once while registering, and it connects them to your firm.")
    clients = list_clients(c)
    f1, f2 = st.columns(2)
    names = {x["id"]: x["name"] for x in clients}
    sel = f1.multiselect("Filter clients", list(names), format_func=lambda i: names[i])
    staff = auth_service.list_staff(c) if c.can("view_all_clients") else []
    staff_names = {s["id"]: s["full_name"] for s in staff}
    staff_sel = f2.selectbox("Filter by staff member", [None] + list(staff_names), format_func=lambda i: "All staff" if i is None else staff_names[i])
    d = firm_service.firm_dashboard(c, y, m, sel or None, staff_sel)
    row1 = st.columns(5)
    kpi(row1[0], "Total clients", d["total_clients"])
    kpi(row1[1], "Active clients", d["active_clients"])
    kpi(row1[2], "Pending submissions", d["pending_submissions"])
    kpi(row1[3], "Awaiting processing", d["awaiting_processing"])
    kpi(row1[4], "Needs review", d["needs_review"])
    row2 = st.columns(4)
    kpi(row2[0], "Unapproved vouchers", d["unapproved_vouchers"])
    kpi(row2[1], "Unmatched bank txns", d["unmatched_bank"])
    kpi(row2[2], "GST recon issues", d["gst_issues"])
    kpi(row2[3], "Finalized months", d["finalized_months"])
    st.subheader("Monthly accounting progress")
    rows = d["per_client"]
    status_f = st.segmented_control("Show", ["all", "not submitted", "needs review", "open"], default="all")
    if status_f == "not submitted":
        rows = [r for r in rows if r["submission"] == "not submitted"]
    elif status_f == "needs review":
        rows = [r for r in rows if r["pending_review"]]
    elif status_f == "open":
        rows = [r for r in rows if r["month_status"] != "finalized"]
    table(rows)
    if rows:
        fig = px.bar([{"client": r["client"], "progress %": r["progress_pct"]} for r in rows], x="client", y="progress %",
                     range_y=[0, 100], color_discrete_sequence=["#0B2545"])
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")
    st.subheader("Staff activity (last 7 days)")
    table(firm_service.staff_activity(c))
