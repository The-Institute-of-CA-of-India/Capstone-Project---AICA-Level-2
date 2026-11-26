"""Tally export: select period, preview, validate, generate XML, download, import instructions."""
from __future__ import annotations

import streamlit as st

from services import tally_service as ts
from services.db import get_db
from ui.common import action, ctx, page_header, require_client_selected, selected_period, table
from utils.helpers import month_bounds


def page():
    c = ctx()
    cid = require_client_selected()
    y, m = selected_period()
    page_header("Tally export", "Approved vouchers → Tally-compatible XML")
    a, b = st.columns(2)
    s, e = month_bounds(y, m)
    start = a.date_input("From", s, format="DD/MM/YYYY")
    end = b.date_input("To", e, format="DD/MM/YYYY")
    company = st.text_input("Company name exactly as in TallyPrime", get_db().get("clients", cid)["name"])
    pv = ts.preview(c, cid, start, end)
    for i in pv["issues"]:
        st.warning(i)
    st.subheader(f"Preview — {len(pv['vouchers'])} approved voucher(s)")
    table(pv["vouchers"])
    a, b = st.columns(2)
    masters = a.checkbox("Also generate ledger masters file", True)
    skip = b.checkbox("Skip vouchers already exported", True)
    if st.button("Generate export", type="primary", disabled=pv["blocking"] or not pv["vouchers"]):
        with action():
            xml, info = ts.export(c, cid, start, end, include_masters=masters, skip_already_exported=skip, company_name=company)
            st.session_state["tally_xml"] = (xml, info)
            st.success(f"Exported {info['count']} voucher(s)")
    if "tally_xml" in st.session_state:
        xml, info = st.session_state["tally_xml"]
        a, b = st.columns(2)
        if info.get("masters_xml"):
            a.download_button("⬇ 1. Ledger masters XML", info["masters_xml"], file_name=f"tally_masters_{start}_{end}.xml", mime="application/xml")
        b.download_button("⬇ 2. Vouchers XML", xml, file_name=f"tally_vouchers_{start}_{end}.xml", mime="application/xml")
    with st.expander("How to import into TallyPrime"):
        st.text(ts.IMPORT_INSTRUCTIONS)
