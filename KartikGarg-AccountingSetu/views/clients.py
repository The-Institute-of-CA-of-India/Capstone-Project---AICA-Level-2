"""Client management: create/edit, client logins & invitations, staff assignment."""
from __future__ import annotations

import streamlit as st

from services import auth_service, firm_service
from services.tenancy import list_clients
from ui.common import action, badge, ctx, page_header, table
from utils.validators import STATE_CODES

BUSINESS_TYPES = ["Proprietorship", "Partnership", "LLP", "Private Limited", "Public Limited", "HUF", "Trust", "Other"]


def _client_form(prefix: str, defaults: dict | None = None) -> dict:
    d = defaults or {}
    c1, c2, c3 = st.columns(3)
    vals = {
        "name": c1.text_input("Business name *", d.get("name", ""), key=f"{prefix}_name"),
        "legal_name": c2.text_input("Legal name", d.get("legal_name") or "", key=f"{prefix}_legal"),
        "business_type": c3.selectbox("Constitution", BUSINESS_TYPES, index=BUSINESS_TYPES.index(d["business_type"])
                                      if d.get("business_type") in BUSINESS_TYPES else 0, key=f"{prefix}_bt"),
        "gstin": c1.text_input("GSTIN", d.get("gstin") or "", key=f"{prefix}_gstin").strip().upper(),
        "pan": c2.text_input("PAN", d.get("pan") or "", key=f"{prefix}_pan").strip().upper(),
        "gst_registration_type": c3.selectbox("GST registration", ["regular", "composition", "unregistered", "sez"],
                                              index=["regular", "composition", "unregistered", "sez"].index(d.get("gst_registration_type") or "regular"),
                                              key=f"{prefix}_grt"),
        "email": c1.text_input("Email", d.get("email") or "", key=f"{prefix}_email"),
        "phone": c2.text_input("Phone", d.get("phone") or "", key=f"{prefix}_phone"),
        "address": c3.text_input("Address", d.get("address") or "", key=f"{prefix}_addr"),
    }
    states = [""] + list(STATE_CODES)
    vals["state_code"] = c1.selectbox("State (if no GSTIN)", states, index=states.index(d.get("state_code") or ""),
                                      format_func=lambda s: f"{s} - {STATE_CODES[s]}" if s else "—", key=f"{prefix}_state") or None
    vals["fy_start_month"] = c2.selectbox("Financial year starts", [4, 1], index=0 if (d.get("fy_start_month") or 4) == 4 else 1,
                                          format_func=lambda m: "April" if m == 4 else "January", key=f"{prefix}_fy")
    dd = c3.number_input("Document deadline day (blank = firm default)", 0, 28, int(d.get("submission_deadline_day") or 0),
                         key=f"{prefix}_dd", help="0 uses the firm's default deadline")
    vals["submission_deadline_day"] = int(dd) or None
    st.markdown("**TDS**")
    c1, c2 = st.columns(2)
    vals["is_tds_deductor"] = c1.checkbox("This client must deduct TDS on vendor payments", bool(d.get("is_tds_deductor")),
                                         key=f"{prefix}_tdsflag",
                                         help="Depends on the client's turnover/audit status in the preceding year — set this only "
                                              "once you've confirmed it applies to them.")
    vals["tan"] = c2.text_input("TAN", d.get("tan") or "", key=f"{prefix}_tan", help="Required to actually file Form 26Q")
    return vals


def page():
    c = ctx()
    page_header("Clients", "Create and manage business clients, their logins and assigned staff.")
    if c.can("manage_clients"):
        with st.expander("➕ Add a new client", expanded=not list_clients(c)):
            with st.form("new_client"):
                vals = _client_form("new")
                if st.form_submit_button("Create client", type="primary"):
                    with action("Client created with default chart of accounts"):
                        firm_service.create_client(c, vals)
                        st.rerun()
    clients = list_clients(c)
    q = st.text_input("Search clients")
    for cl in clients:
        if q and q.lower() not in (cl["name"] + (cl.get("gstin") or "")).lower():
            continue
        with st.expander(f"{cl['name']}  ·  {cl.get('gstin') or 'no GSTIN'}"):
            st.markdown(badge(cl["status"]), unsafe_allow_html=True)
            t1, t2, t3 = st.tabs(["Profile", "Client logins", "Assigned staff"])
            with t1:
                if c.can("manage_clients"):
                    with st.form(f"edit_{cl['id']}"):
                        vals = _client_form(cl["id"], cl)
                        vals["status"] = st.selectbox("Status", ["active", "inactive"], index=0 if cl["status"] == "active" else 1,
                                                      key=f"st_{cl['id']}")
                        if st.form_submit_button("Save changes"):
                            with action("Client updated"):
                                firm_service.update_client(c, cl["id"], vals)
                                st.rerun()
                else:
                    st.json({k: cl.get(k) for k in ("name", "gstin", "pan", "business_type", "email", "phone", "state_code")})
            with t2:
                table(firm_service.client_users(c, cl["id"]))
                if c.can("manage_clients"):
                    st.markdown("**Invite by email** (client sets their own password)")
                    ic1, ic2 = st.columns([3, 1])
                    email = ic1.text_input("Client email", key=f"inv_{cl['id']}")
                    if ic2.button("Send invitation", key=f"invb_{cl['id']}"):
                        with action():
                            token = auth_service.invite_client_user(c, cl["id"], email)
                            from config import settings

                            st.success("Invitation sent.")
                            st.code(f"{settings.app_base_url}/?invite={token}", language=None)
                            st.caption("Share this link only with the client if email delivery is not configured.")
                    st.markdown("**Or create a login directly** (temporary password; the client must change it at first sign-in)")
                    with st.form(f"cu_{cl['id']}"):
                        a, b, d = st.columns(3)
                        nm = a.text_input("Name")
                        em = b.text_input("Email")
                        pw = d.text_input("Temporary password", type="password")
                        if st.form_submit_button("Create client login"):
                            with action("Client login created"):
                                auth_service.create_client_user(c, cl["id"], email=em, full_name=nm, temp_password=pw)
            with t3:
                staff = auth_service.list_staff(c)
                current = firm_service.assigned_staff_ids(c, cl["id"])
                names = {s["id"]: f"{s['full_name']} ({s['role']})" for s in staff if s["is_active"]}
                chosen = st.multiselect("Staff assigned to this client", list(names), default=[x for x in current if x in names],
                                        format_func=lambda i: names[i], key=f"as_{cl['id']}", disabled=not c.can("manage_clients"))
                st.caption("Firm Admin and Partners can access all clients regardless of assignment.")
                if c.can("manage_clients") and st.button("Save assignment", key=f"asb_{cl['id']}"):
                    with action("Assignment saved"):
                        firm_service.assign_staff(c, cl["id"], chosen)
