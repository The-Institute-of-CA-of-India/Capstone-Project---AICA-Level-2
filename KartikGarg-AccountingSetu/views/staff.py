"""Staff management with role-based and per-user permission overrides."""
from __future__ import annotations

import streamlit as st

from services import auth_service
from ui.common import action, ctx, page_header, table
from utils.permissions import PERMISSIONS, ROLE_PERMISSIONS, ROLES, effective_permissions


def page():
    c = ctx()
    page_header("Staff", "Add employees, assign roles and fine-tune permissions.")
    staff = auth_service.list_staff(c)
    table([{"name": s["full_name"], "email": s["email"], "role": ROLES.get(s["role"], s["role"]), "designation": s.get("designation"),
            "active": "Yes" if s["is_active"] else "No", "last login": str(s.get("last_login_at") or "—")[:16]} for s in staff])
    with st.expander("Role permission matrix"):
        st.dataframe([{"permission": p, **{ROLES[r]: ("✔" if p in ROLE_PERMISSIONS[r] else "") for r in ROLES}} for p in PERMISSIONS],
                     hide_index=True, width="stretch")
    if not c.can("manage_staff"):
        st.info("Only users with the 'manage staff' permission can add or edit staff.")
        return
    st.subheader("Add staff member")
    with st.form("add_staff"):
        a, b, d = st.columns(3)
        name = a.text_input("Full name")
        email = b.text_input("Login email")
        role = d.selectbox("Role", list(ROLES), format_func=lambda r: ROLES[r], index=2)
        desig = a.text_input("Designation")
        pw = b.text_input("Temporary password", type="password", help="The staff member must change it at first sign-in")
        if st.form_submit_button("Create staff account", type="primary"):
            with action("Staff account created"):
                auth_service.create_staff(c, email=email, full_name=name, role=role, temp_password=pw, designation=desig)
                st.rerun()
    st.subheader("Edit staff")
    for s in staff:
        with st.expander(f"{s['full_name']} — {ROLES.get(s['role'])}{'' if s['is_active'] else ' (inactive)'}"):
            with st.form(f"edit_{s['id']}"):
                role = st.selectbox("Role", list(ROLES), index=list(ROLES).index(s["role"]), format_func=lambda r: ROLES[r])
                active = st.checkbox("Active", s["is_active"])
                ov = s.get("permissions") or {}
                base = ROLE_PERMISSIONS[role]
                grant = st.multiselect("Extra permissions (grant)", [p for p in PERMISSIONS if p not in base], default=[p for p in ov.get("grant", []) if p not in base])
                revoke = st.multiselect("Remove permissions (revoke)", sorted(base), default=[p for p in ov.get("revoke", []) if p in base])
                st.caption("Effective: " + ", ".join(sorted(effective_permissions(role, {"grant": grant, "revoke": revoke}))))
                if st.form_submit_button("Save"):
                    with action("Staff updated"):
                        auth_service.update_staff(c, s["id"], role=role, is_active=active, permissions={"grant": grant, "revoke": revoke})
                        st.rerun()
