"""Month finalization & locking with pre-checks, snapshot, reopen with reason."""
from __future__ import annotations

import streamlit as st

from services import period_service as ps
from ui.common import action, badge, ctx, kpi, page_header, require_client_selected, rupees, selected_period, table


def page():
    c = ctx()
    cid = require_client_selected()
    y, m = selected_period()
    page_header("Month finalization", f"{m:02d}/{y}")
    chk = ps.pre_finalization_checks(c, cid, y, m)
    st.markdown(f"Current status: {badge(chk['status'])}", unsafe_allow_html=True)
    cols = st.columns(4)
    kpi(cols[0], "Total sales", rupees(chk["total_sales"]))
    kpi(cols[1], "Total purchases", rupees(chk["total_purchases"]))
    kpi(cols[2], "Total expenses", rupees(chk["total_expenses"]))
    kpi(cols[3], "Bank transactions", chk["bank_transactions"])
    cols = st.columns(4)
    kpi(cols[0], "Pending documents", chk["pending_documents"])
    kpi(cols[1], "Unapproved vouchers", chk["unapproved_vouchers"])
    kpi(cols[2], "Unmatched bank txns", chk["unmatched_bank"])
    kpi(cols[3], "GST recon differences", chk["gst_differences"])
    st.write("")
    for w in chk["warnings"]:
        st.warning(w)
    if chk["status"] != "finalized":
        if chk["blocking"]:
            st.error("Approve or reject all vouchers of this month before finalizing.")
        override = st.checkbox("I have reviewed the unresolved warnings and want to finalize anyway") if chk["warnings"] else True
        if st.button("🔒 FINALIZE & LOCK MONTH", type="primary", disabled=not c.can("finalize_period") or chk["blocking"] or not override):
            with action("Month finalized and locked; snapshot saved"):
                ps.finalize_month(c, cid, y, m, override_warnings=bool(override))
                st.rerun()
        if not c.can("finalize_period"):
            st.caption("You do not have permission to finalize months.")
    else:
        p = chk["period"]
        st.success(f"Finalized on {str(p['finalized_at'])[:16]} · snapshot hash {p['snapshot_hash'][:16]}…")
        if c.can("reopen_period"):
            reason = st.text_area("Reason for reopening (recorded in the audit trail)")
            if st.button("Reopen month"):
                with action("Month reopened"):
                    ps.reopen_month(c, cid, y, m, reason)
                    st.rerun()
    st.subheader("Period history")
    table(ps.list_periods(c, cid))
