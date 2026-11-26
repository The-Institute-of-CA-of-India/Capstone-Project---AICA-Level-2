"""Login, firm registration, password reset, invitation acceptance, first-run setup."""
from __future__ import annotations

import streamlit as st

from config import settings
from services import auth_service
from services.auth_service import AuthError
from ui.common import action
from utils.validators import STATE_CODES


def _brand():
    st.markdown(f"<h1 style='border:none;margin-bottom:0'>Accounting <span style='color:#C9A227'>Setu</span></h1>"
                f"<p style='color:#64748B;margin-top:0'>{settings.tagline}</p>", unsafe_allow_html=True)


def first_run_setup():
    _brand()
    st.subheader("First-time setup: create the platform owner (Super Admin)")
    st.caption("This screen appears only while no Super Admin exists.")
    with st.form("setup"):
        name = st.text_input("Full name")
        email = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        pw2 = st.text_input("Confirm password", type="password")
        if st.form_submit_button("Create Super Admin", type="primary"):
            if pw != pw2:
                st.error("Passwords do not match")
            else:
                with action():
                    auth_service.create_super_admin(email, pw, name)
                    st.success("Super Admin created. Please sign in.")
                    st.rerun()


def login_page():
    params = st.query_params
    if params.get("invite"):
        return accept_invite(params["invite"])
    if params.get("reset"):
        return reset_password(params["reset"])
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        _brand()
        portal = st.session_state.get("portal")
        if portal is None:
            _choose_portal()
        else:
            if st.button("← Back", key="back_portal"):
                st.session_state.pop("portal", None)
                st.session_state.pop("signup_result", None)
                st.session_state.pop("verified_firm", None)
                st.rerun()
            {"firm": _firm_portal, "client": _client_portal, "admin": _admin_portal}[portal]()


# ---------------------------------------------------------------- first screen: choose CA firm or client
def _choose_portal():
    st.markdown("### How do you want to continue?")
    a, b = st.columns(2)
    with a.container(border=True):
        st.markdown("#### 🏢 CA Firm")
        st.caption("For chartered accountants and their staff.")
        if st.button("Login as CA Firm", type="primary", width="stretch", key="go_firm"):
            st.session_state["portal"] = "firm"
            st.rerun()
    with b.container(border=True):
        st.markdown("#### 👤 Client")
        st.caption("For businesses and individuals who send documents to their CA.")
        if st.button("Login as Client", type="primary", width="stretch", key="go_client"):
            st.session_state["portal"] = "client"
            st.rerun()
    st.write("")
    if st.button("Platform admin", key="go_admin", type="tertiary"):
        st.session_state["portal"] = "admin"
        st.rerun()


def _sign_in_form(portal: str, key: str):
    with st.form(key):
        email = st.text_input("Login ID (email)")
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in", type="primary", width="stretch"):
            try:
                c = auth_service.login(email, pw, portal=portal)
                st.session_state["user_id"] = c.user_id
                for k in ("client_id", "portal", "signup_result", "verified_firm"):
                    st.session_state.pop(k, None)
                st.rerun()
            except AuthError as exc:
                st.error(str(exc))


def _forgot_form(key: str):
    with st.form(key):
        email = st.text_input("Login ID (email)")
        if st.form_submit_button("Send reset link"):
            with action():
                auth_service.request_password_reset(email)
            st.info("If an account exists for this email, a reset link has been sent."
                    + (" (Local mode without SMTP: the email is saved in data/outbox/.)" if not settings.smtp_host else ""))


def _show_credentials(res: dict, kind: str):
    st.success("Registration successful! Save these details now. They have also been emailed to you.")
    with st.container(border=True):
        if kind == "firm":
            st.markdown(f"**Firm serial number:** `{res['serial_no']}`")
            st.markdown("**Secret client code.** Give this code to your clients so they can connect to your firm:")
            st.code(res["client_code"], language=None)
        else:
            st.markdown(f"**Connected to CA firm:** {res['firm_name']}")
        st.markdown("**Login ID:**")
        st.code(res["login_email"], language=None)
        st.markdown("**First password.** You will set your own password the first time you sign in:")
        st.code(res["first_password"], language=None)
    if kind == "firm" and res.get("status") == "pending":
        st.info("Your firm will be activated after the platform administrator approves it.")
    st.caption("Now open the **Sign in** tab and sign in with the details above.")


# ---------------------------------------------------------------- CA firm
def _firm_portal():
    st.markdown("### 🏢 CA Firm")
    t_in, t_reg, t_forgot = st.tabs(["Sign in", "Register new CA firm", "Forgot password"])
    with t_in:
        _sign_in_form("firm", "login_firm")
    with t_reg:
        res = st.session_state.get("signup_result")
        if res and res.get("kind") == "firm":
            _show_credentials(res, "firm")
        else:
            with st.form("register_firm"):
                c1, c2 = st.columns(2)
                firm = c1.text_input("CA firm name *")
                frn = c2.text_input("Firm registration no. (FRN)")
                person = c1.text_input("Your name (partner / proprietor) *")
                phone = c2.text_input("Mobile *")
                email = c1.text_input("Email *: this becomes your Login ID")
                city = c2.text_input("City")
                address = st.text_input("Office address")
                c3, c4 = st.columns(2)
                state = c3.selectbox("State", [""] + [f"{k} - {v}" for k, v in STATE_CODES.items()])
                gstin = c4.text_input("Firm GSTIN (optional)")
                if st.form_submit_button("Register CA firm", type="primary"):
                    if not firm.strip() or not person.strip() or not phone.strip():
                        st.error("Please fill all fields marked *")
                    else:
                        with action():
                            out = auth_service.signup_firm(firm_name=firm, email=email, phone=phone, admin_name=person,
                                                           frn=frn, address=address, city=city,
                                                           state_code=state[:2] if state else "", gstin=gstin.strip().upper())
                            st.session_state["signup_result"] = {**out, "kind": "firm"}
                            st.rerun()
    with t_forgot:
        _forgot_form("forgot_firm")


# ---------------------------------------------------------------- client
def _client_portal():
    st.markdown("### 👤 Client")
    t_in, t_reg, t_forgot = st.tabs(["Sign in", "New client? Register", "Forgot password"])
    with t_in:
        _sign_in_form("client", "login_client")
    with t_reg:
        res = st.session_state.get("signup_result")
        if res and res.get("kind") == "client":
            _show_credentials(res, "client")
            return
        firm = st.session_state.get("verified_firm")
        st.markdown("**Step 1: Enter your CA firm's secret code**")
        st.caption("Your CA firm gives you this code. You need it only once, at registration.")
        a, b = st.columns([3, 1])
        code = a.text_input("CA firm code", value=firm["code"] if firm else "", placeholder="ABCD-EFGH",
                            label_visibility="collapsed")
        if b.button("Verify code", width="stretch"):
            f = auth_service.firm_by_code(code)
            if f:
                st.session_state["verified_firm"] = {"code": auth_service.normalize_code(code), "name": f["name"],
                                                     "city": f.get("city") or ""}
                st.rerun()
            else:
                st.session_state.pop("verified_firm", None)
                st.error("Code not found. Please check the code with your CA firm.")
        if not firm:
            return
        st.success(f"✔ You will be connected to **{firm['name']}**{(', ' + firm['city']) if firm['city'] else ''}")
        st.markdown("**Step 2: Your details**")
        with st.form("register_client"):
            types = ["Proprietorship", "Individual", "Partnership", "LLP", "Private Limited", "Public Limited", "HUF",
                     "Trust", "Other"]
            c1, c2 = st.columns(2)
            btype = c1.selectbox("Type of business *", types)
            name = c2.text_input("Business name (or your name) *")
            person = c1.text_input("Contact person *")
            mobile = c2.text_input("Mobile *")
            email = c1.text_input("Email *: this becomes your Login ID")
            pan = c2.text_input("PAN *", max_chars=10)
            aadhaar = c1.text_input("Aadhaar (needed for individuals, proprietors and HUFs)", max_chars=14,
                                    help="Only the last 4 digits are stored, as XXXX-XXXX-1234")
            gstin = c2.text_input("GSTIN (if registered)", max_chars=15)
            address = st.text_input("Address")
            state = st.selectbox("State", [""] + [f"{k} - {v}" for k, v in STATE_CODES.items()])
            if st.form_submit_button("Register & connect to my CA", type="primary"):
                if not name.strip() or not person.strip():
                    st.error("Please fill all fields marked *")
                else:
                    with action():
                        out = auth_service.signup_client(firm_code=firm["code"], business_name=name, contact_person=person,
                                                         email=email, mobile=mobile, pan=pan, aadhaar=aadhaar,
                                                         business_type=btype, gstin=gstin, address=address,
                                                         state_code=state[:2] if state else "")
                        st.session_state["signup_result"] = {**out, "kind": "client"}
                        st.session_state.pop("verified_firm", None)
                        st.rerun()
    with t_forgot:
        _forgot_form("forgot_client")


# ---------------------------------------------------------------- platform admin
def _admin_portal():
    st.markdown("### Platform admin")
    _sign_in_form("admin", "login_admin")


def reset_password(token: str):
    _brand()
    st.subheader("Set a new password")
    with st.form("reset"):
        pw = st.text_input("New password", type="password")
        pw2 = st.text_input("Confirm", type="password")
        if st.form_submit_button("Update password", type="primary"):
            if pw != pw2:
                st.error("Passwords do not match")
            else:
                with action():
                    auth_service.reset_password(token, pw)
                    st.success("Password updated. Sign in with your new password.")
                    st.query_params.clear()


def accept_invite(token: str):
    _brand()
    inv = auth_service.get_invitation(token)
    if not inv:
        st.error("This invitation link is invalid or has expired. Ask your CA to send a new one.")
        if st.button("Go to sign in"):
            st.query_params.clear()
            st.rerun()
        return
    st.subheader(f"{inv['firm_name']} invited you to submit documents for {inv['client_name']}")
    with st.form("accept"):
        st.text_input("Email", value=inv["email"], disabled=True)
        name = st.text_input("Your name")
        pw = st.text_input("Choose a password", type="password")
        pw2 = st.text_input("Confirm password", type="password")
        if st.form_submit_button("Create my account", type="primary"):
            if pw != pw2:
                st.error("Passwords do not match")
            else:
                with action():
                    auth_service.accept_invitation(token, name, pw)
                    st.success("Account created. Please sign in.")
                    st.query_params.clear()


def change_password_page():
    st.title("Change password")
    from ui.common import ctx

    first = auth_service.must_change_password(ctx())
    if first:
        st.info("Welcome! You signed in with the first password we gave you. Now choose your own password. "
                "It can be any letters, numbers or symbols (at least 6, no spaces).")
    with st.form("chpw"):
        old = st.text_input("First password (the one we gave you)" if first else "Current password", type="password")
        new = st.text_input("Your new password", type="password")
        new2 = st.text_input("Type the new password again", type="password")
        if st.form_submit_button("Change password", type="primary"):
            if new != new2:
                st.error("Passwords do not match")
            else:
                with action():
                    auth_service.change_password(ctx(), old, new)
                    st.success("Password changed.")
                    st.rerun()
