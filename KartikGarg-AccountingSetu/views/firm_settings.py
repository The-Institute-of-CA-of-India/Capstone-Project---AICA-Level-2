"""Firm profile, branding and accounting preferences."""
from __future__ import annotations

import streamlit as st

from services import admin_service, firm_service
from ui.common import action, ctx, page_header
from utils.validators import STATE_CODES


def page():
    c = ctx()
    page_header("Firm settings", "Profile, branding, deadlines and accounting preferences.")
    firm = firm_service.get_firm(c)
    with st.container(border=True):
        a, b, d = st.columns([1, 1, 1])
        a.markdown(f"**Firm serial number**  \n`{firm.get('serial_no') or '—'}`")
        b.markdown("**Secret client code**")
        b.code(firm.get("client_code") or "—", language=None)
        d.caption("Clients enter this code once, when they register, to connect to your firm. A new code stops "
                  "new sign-ups with the old one; clients who already joined stay connected.")
        if d.button("Generate new code"):
            from services import auth_service

            with action():
                st.success(f"New code: {auth_service.regenerate_client_code(c)}")
                st.rerun()
    t1, t2, t3 = st.tabs(["Profile", "Branding", "Preferences"])
    with t1:
        with st.form("firm_profile"):
            a, b = st.columns(2)
            vals = {"name": a.text_input("Firm name", firm["name"]), "legal_name": b.text_input("Legal name", firm.get("legal_name") or ""),
                    "frn": a.text_input("FRN", firm.get("frn") or ""), "gstin": b.text_input("GSTIN", firm.get("gstin") or ""),
                    "pan": a.text_input("PAN", firm.get("pan") or ""), "email": b.text_input("Email", firm["email"]),
                    "phone": a.text_input("Phone", firm.get("phone") or ""), "address": b.text_input("Address", firm.get("address") or ""),
                    "city": a.text_input("City", firm.get("city") or ""), "pincode": b.text_input("PIN code", firm.get("pincode") or "")}
            states = [""] + list(STATE_CODES)
            vals["state_code"] = a.selectbox("State", states, index=states.index(firm.get("state_code") or ""),
                                             format_func=lambda s: f"{s} - {STATE_CODES[s]}" if s else "—") or None
            if st.form_submit_button("Save profile", type="primary"):
                with action("Profile saved"):
                    firm_service.update_firm(c, vals)
        sub = admin_service.current_subscription(c.firm_id)
        if sub:
            st.caption(f"Subscription: {sub['plan_name']} ({sub['status']}) until {sub['end_date']} · up to {sub['max_clients']} clients, "
                       f"{sub['max_staff']} staff, {sub['max_documents_per_month']} documents/month")
    with t2:
        logo = firm_service.firm_logo_bytes(c)
        if logo:
            st.image(logo, width=180)
        up = st.file_uploader("Upload firm logo (PNG/JPG, ≤2 MB)", type=["png", "jpg", "jpeg"])
        if up and st.button("Save logo", type="primary"):
            with action("Logo updated"):
                firm_service.upload_logo(c, up.name, up.getvalue())
                st.session_state.pop("_logo_cache", None)  # force the sidebar to re-fetch the new logo
                st.rerun()
    with t3:
        s = firm.get("settings") or {}
        with st.form("prefs"):
            day = st.number_input("Monthly document submission deadline (day of following month)", 1, 28, int(s.get("submission_deadline_day", 5)))
            auto = st.checkbox("Process documents automatically when a client submits", bool(s.get("auto_process_on_submit", True)))
            ret = st.number_input("Document retention (years)", 1, 20, int(s.get("retention_years", 8)),
                                  help="Section 36 CGST Act requires records for 72 months from the annual return due date")
            if st.form_submit_button("Save preferences", type="primary"):
                with action("Preferences saved"):
                    firm_service.update_firm_settings(c, {"submission_deadline_day": int(day), "auto_process_on_submit": auto,
                                                          "retention_years": int(ret)})
