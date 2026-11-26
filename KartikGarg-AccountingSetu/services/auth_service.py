"""Authentication, registration, invitations, password reset and context building.

Local backend: passwords hashed with scrypt (stdlib) in user_profiles.password_hash.
Supabase backend: credentials are verified by Supabase Auth (GoTrue); user_profiles.id = auth.users.id.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import re
import secrets

from config import settings
from services.audit_service import audit
from services.db import IntegrityError, current_user_id, get_db, now_iso, system_identity
from services.tenancy import AuthContext, require_client, require_firm
from utils.helpers import hash_token, is_past, new_token
from utils.permissions import CLIENT_PERMISSIONS, PermissionDenied, ROLES, effective_permissions

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    pass


# ----------------------------------------------------------------- passwords
MIN_PASSWORD_LEN = 6  # Supabase Auth's own minimum; no other composition rules


def validate_password(pw: str) -> None:
    """Any letters/digits/symbols are allowed. Blank passwords and spaces are not."""
    if not pw or not pw.strip():
        raise AuthError("Password cannot be blank.")
    if re.search(r"\s", pw):
        raise AuthError("Password cannot contain spaces.")
    if len(pw) < MIN_PASSWORD_LEN:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LEN} characters.")


_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I, which are easy to mistype


def generate_first_password() -> str:
    """System-generated first password, e.g. Setu-7K3M9Q. The user replaces it at first sign-in."""
    return "Setu-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = 2**14, 8, 1
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(pw: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    _, n, r, p, salt, dk = stored.split("$")
    test = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
    return hmac.compare_digest(test, base64.b64decode(dk))


def _normalize_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not EMAIL_RE.match(e):
        raise AuthError("Enter a valid email address.")
    return e


# ----------------------------------------------------------------- supabase adapter
def _supabase():
    from supabase import create_client

    if not (settings.supabase_url and settings.supabase_anon_key):
        raise AuthError("Supabase is not configured (SUPABASE_URL / SUPABASE_ANON_KEY).")
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def _supabase_admin():
    from supabase import create_client

    if not settings.supabase_service_role_key:
        raise AuthError("SUPABASE_SERVICE_ROLE_KEY is required server-side to create users.")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _create_identity(email: str, password: str, full_name: str, *, must_change: bool = False,
                     is_super_admin: bool = False) -> str:
    """Create the login identity + profile row. Returns user id."""
    db = get_db()
    if db.fetchone("select id from user_profiles where email = ?", [email]):
        raise AuthError("An account with this email already exists.")
    validate_password(password)
    if settings.backend == "supabase":
        try:
            res = _supabase_admin().auth.admin.create_user({"email": email, "password": password, "email_confirm": True,
                                                             "user_metadata": {"full_name": full_name}})
        except Exception as exc:
            # A double-click (or a slow page retried by an impatient click) can send this request twice; the first
            # one wins and the second lands here. Supabase's own uniqueness check catches it before ours does.
            if "already" in str(exc).lower() and "registered" in str(exc).lower():
                raise AuthError("This email was just registered a moment ago (perhaps by a double-click). "
                                "Please use the 'Sign in' tab instead, or try again with the first password you "
                                "were shown.") from exc
            raise
        uid = res.user.id
        pw_hash = None
    else:
        uid = None
        pw_hash = hash_password(password)
    # Authorization for creating identities is enforced by callers (require_firm / require_client);
    # the profile row is written as the system identity because RLS has no user-facing insert policy on profiles.
    with system_identity():
        return _insert_profile(db, uid, email, full_name, pw_hash, is_super_admin, must_change)


def _insert_profile(db, uid, email, full_name, pw_hash, is_super_admin, must_change) -> str:
    return db.insert("user_profiles", {
        **({"id": uid} if uid else {}),
        "email": email, "full_name": full_name.strip(), "password_hash": pw_hash,
        "is_super_admin": is_super_admin, "must_change_password": must_change,
        "created_at": now_iso(),
    })


# ----------------------------------------------------------------- bootstrap
def super_admin_exists() -> bool:
    return get_db().fetchone("select id from user_profiles where is_super_admin = ?", [True]) is not None


def create_super_admin(email: str, password: str, full_name: str) -> str:
    """First-run only: creates the platform owner. Refuses if one already exists."""
    if super_admin_exists():
        raise PermissionDenied("A Super Admin already exists. Additional admins must be created by the owner.")
    email = _normalize_email(email)
    uid = _create_identity(email, password, full_name, is_super_admin=True)
    audit(None, "super_admin.created", "user_profiles", uid, after={"email": email})
    return uid


def ensure_bootstrap() -> None:
    """Create default plans; create super admin from env if configured and none exists."""
    from services import admin_service

    admin_service.ensure_default_plans()
    ensure_firm_codes()
    if settings.super_admin_email and settings.super_admin_password and not super_admin_exists():
        create_super_admin(settings.super_admin_email, settings.super_admin_password, "Platform Owner")


# ----------------------------------------------------------------- login
PORTAL_KINDS = {"firm": {"staff"}, "client": {"client"}, "admin": {"super_admin"}}
PORTAL_HINT = {"staff": "This is a CA firm account. Please use 'Login as CA Firm'.",
               "client": "This is a client account. Please use 'Login as Client'.",
               "super_admin": "This is the platform administrator account. Use 'Platform admin' at the bottom of the page."}


def login(email: str, password: str, portal: str | None = None) -> AuthContext:
    """portal: 'firm' | 'client' | 'admin', the door chosen on the first screen (None = any)."""
    db = get_db()
    email = _normalize_email(email)
    user = db.fetchone("select * from user_profiles where email = ?", [email])
    generic = AuthError("Invalid email or password.")
    if user is None:
        verify_password(password, hash_password("dummy-timing-pw1"))  # keep timing similar
        raise generic
    if user.get("locked_until") and not is_past(user["locked_until"]):
        raise AuthError("Account temporarily locked after repeated failed logins. Try again later.")
    if not user["is_active"]:
        raise AuthError("This account is deactivated.")
    if settings.backend == "supabase":
        try:
            res = _supabase().auth.sign_in_with_password({"email": email, "password": password})
            ok = res.user is not None and res.user.id == user["id"]
        except Exception:
            ok = False
    else:
        ok = verify_password(password, user.get("password_hash"))
    if not ok:
        fails = int(user.get("failed_logins") or 0) + 1
        upd = {"failed_logins": fails}
        if fails >= MAX_FAILED_LOGINS:
            upd["locked_until"] = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=LOCKOUT_MINUTES)).replace(microsecond=0).isoformat()
            upd["failed_logins"] = 0
        db.update("user_profiles", user["id"], upd)
        raise generic
    db.update("user_profiles", user["id"], {"failed_logins": 0, "locked_until": None, "last_login_at": now_iso()})
    ctx = build_context(user["id"])
    if portal and ctx.kind not in PORTAL_KINDS[portal]:
        raise AuthError(PORTAL_HINT[ctx.kind])
    audit(ctx, "auth.login", "user_profiles", user["id"])
    return ctx


def build_context(user_id: str, prefer_firm_id: str | None = None) -> AuthContext:
    """Resolve the tenant identity strictly from membership tables."""
    db = get_db()
    user = db.get("user_profiles", user_id)
    if user is None or not user["is_active"]:
        raise AuthError("Account not found or inactive.")
    base = dict(user_id=user["id"], email=user["email"], full_name=user["full_name"])
    if user["is_super_admin"]:
        return AuthContext(kind="super_admin", permissions=frozenset({"platform_admin"}), **base)
    staff_rows = db.fetchall(
        "select fs.*, f.name as firm_name, f.status as firm_status from firm_staff fs join firms f on f.id = fs.firm_id "
        "where fs.user_id = ? and fs.is_active = ? order by fs.created_at", [user_id, True])
    if prefer_firm_id:
        staff_rows = [r for r in staff_rows if r["firm_id"] == prefer_firm_id] or staff_rows
    if staff_rows:
        s = staff_rows[0]
        return AuthContext(kind="staff", firm_id=s["firm_id"], firm_name=s["firm_name"], firm_status=s["firm_status"],
                           staff_id=s["id"], role=s["role"],
                           permissions=frozenset(effective_permissions(s["role"], s.get("permissions") or {})), **base)
    cu = db.fetchone(
        "select cu.*, f.name as firm_name, f.status as firm_status, c.status as client_status from client_users cu "
        "join firms f on f.id = cu.firm_id join clients c on c.id = cu.client_id "
        "where cu.user_id = ? and cu.is_active = ? order by cu.created_at", [user_id, True])
    if cu:
        if cu["firm_status"] != "active":
            raise AuthError("Your CA firm's workspace is not active. Please contact your CA.")
        if cu["client_status"] != "active":
            raise AuthError("Your client account is inactive. Please contact your CA.")
        return AuthContext(kind="client", firm_id=cu["firm_id"], firm_name=cu["firm_name"], firm_status=cu["firm_status"],
                           client_id=cu["client_id"], permissions=frozenset(CLIENT_PERMISSIONS), **base)
    raise AuthError("Your account is not linked to any firm or client yet.")


def activate_request_identity(ctx: AuthContext | None) -> None:
    """Bind the user id for DB-level RLS (Supabase backend) for the current request."""
    current_user_id.set(ctx.user_id if ctx else None)


# ----------------------------------------------------------------- firm serial number & client code
def _new_serial(db) -> str:
    rows = db.fetchall("select serial_no from firms where serial_no is not null")
    n = max((int(r["serial_no"][3:]) for r in rows if r["serial_no"][3:].isdigit()), default=0)
    return f"CAF{n + 1:05d}"


def _new_client_code(db) -> str:
    while True:
        raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        code = f"{raw[:4]}-{raw[4:]}"
        if not db.fetchone("select id from firms where client_code = ?", [code]):
            return code


def normalize_code(code: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9]", "", code or "").upper()
    return f"{raw[:4]}-{raw[4:]}" if len(raw) == 8 else raw


def ensure_firm_codes() -> None:
    """Back-fill serial numbers and client codes for firms created before migration 005."""
    db = get_db()
    with system_identity():
        for f in db.fetchall("select id, serial_no, client_code from firms where serial_no is null or client_code is null "
                             "order by created_at"):
            upd = {}
            if not f.get("serial_no"):
                upd["serial_no"] = _new_serial(db)
            if not f.get("client_code"):
                upd["client_code"] = _new_client_code(db)
                upd["client_code_updated_at"] = now_iso()
            db.update("firms", f["id"], upd)


def firm_approval_required() -> bool:
    """Every new CA firm needs the Super Admin's approval before it can work, unless explicitly turned off in
    Platform Settings. This is the default and the expected behavior."""
    from services.admin_service import feature_enabled

    return feature_enabled("require_firm_approval", default=True)


def regenerate_client_code(ctx: AuthContext) -> str:
    """New code for future client sign-ups; clients who already joined stay connected."""
    firm_id = require_firm(ctx, "manage_firm")
    db = get_db()
    code = _new_client_code(db)
    old = db.get("firms", firm_id).get("client_code")
    db.update("firms", firm_id, {"client_code": code, "client_code_updated_at": now_iso()})
    audit(ctx, "firm.client_code_regenerated", "firms", firm_id, before={"code": old}, after={"code": code})
    return code


def firm_by_code(code: str) -> dict | None:
    """Lookup used on the client sign-up screen. Returns only the firm's name and city."""
    norm = normalize_code(code)
    if len(norm) != 9:
        return None
    with system_identity():
        f = get_db().fetchone("select id, name, city, status from firms where client_code = ?", [norm])
    if not f or f["status"] != "active":
        return None
    return f


# ----------------------------------------------------------------- self sign-up: CA firm
def signup_firm(*, firm_name: str, email: str, phone: str, admin_name: str = "", frn: str = "", address: str = "",
                city: str = "", state_code: str = "", gstin: str = "", pan: str = "") -> dict:
    """'Login as CA Firm → Register'. The firm email is the login ID; a first password is generated."""
    from services.admin_service import feature_enabled
    from services.notification_service import notify_super_admins, send_email

    if not feature_enabled("registrations", default=True):
        raise AuthError("New CA firm registrations are currently closed. Please contact the platform administrator.")
    first_pw = generate_first_password()
    login_email = _normalize_email(email)
    with system_identity():
        fid = register_firm(firm_name=firm_name, email=login_email, phone=phone, admin_name=(admin_name or firm_name).strip(),
                            admin_email=login_email, password=first_pw, address=address, city=city, state_code=state_code,
                            frn=frn, gstin=gstin, pan=pan, must_change=True)
        f = get_db().get("firms", fid)
        if f["status"] == "pending":
            notify_super_admins("New CA firm wants to join", f"{firm_name} ({f['serial_no']}) is waiting for your approval.")
    pending_note = ("\n\nYour firm is waiting for the platform administrator's approval before it becomes active."
                    if f["status"] == "pending" else "")
    send_email(login_email, "Welcome to Accounting Setu",
               f"Your CA firm '{firm_name}' is registered.\nSerial number: {f['serial_no']}\n"
               f"Secret client code (give this to your clients): {f['client_code']}\nLogin ID: {login_email}\n"
               f"First password: {first_pw}\nYou will set your own password at first sign-in.{pending_note}")
    return {"firm_id": fid, "serial_no": f["serial_no"], "client_code": f["client_code"], "status": f["status"],
            "login_email": login_email, "first_password": first_pw}


# ----------------------------------------------------------------- self sign-up: client (with firm code)
_AAD_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
          [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
          [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
          [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_AAD_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
          [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
          [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]
INDIVIDUAL_TYPES = {"Individual", "Proprietorship", "HUF"}


def validate_aadhaar(number: str) -> str:
    """Check format + Verhoeff checksum and return the masked form. The full number is never stored."""
    digits = re.sub(r"\D", "", number or "")
    if len(digits) != 12 or digits[0] in "01":
        raise AuthError("Aadhaar must be 12 digits and cannot start with 0 or 1.")
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _AAD_D[c][_AAD_P[i % 8][int(ch)]]
    if c != 0:
        raise AuthError("This Aadhaar number is not valid. Please re-check it.")
    return f"XXXX-XXXX-{digits[-4:]}"


def signup_client(*, firm_code: str, business_name: str, contact_person: str, email: str, mobile: str, pan: str,
                  aadhaar: str = "", business_type: str = "Proprietorship", gstin: str = "", address: str = "",
                  state_code: str = "") -> dict:
    """'Login as Client → Register'. The CA firm's secret code links the client to that firm (asked only once)."""
    import datetime as _dt

    from services import admin_service, firm_service
    from services.accounting_engine import ensure_chart_of_accounts
    from services.notification_service import notify_firm, send_email
    from utils.helpers import fy_label_for
    from utils.validators import validate_gstin, validate_pan

    firm = firm_by_code(firm_code)
    if not firm:
        raise AuthError("CA firm code not found. Please check the code your CA firm gave you.")
    if not (business_name or "").strip():
        raise AuthError("Business name / your name is required.")
    pan = (pan or "").strip().upper()
    if not validate_pan(pan):
        raise AuthError("PAN must look like ABCDE1234F.")
    aadhaar_masked = None
    if business_type in INDIVIDUAL_TYPES or (aadhaar or "").strip():
        if not (aadhaar or "").strip():
            raise AuthError("Aadhaar is required for individuals, proprietors and HUFs.")
        aadhaar_masked = validate_aadhaar(aadhaar)
    gstin = (gstin or "").strip().upper()
    if gstin:
        ok, msg = validate_gstin(gstin)
        if not ok:
            raise AuthError(f"GSTIN: {msg}")
        if gstin[2:12] != pan:
            raise AuthError("This GSTIN does not belong to this PAN (GSTIN characters 3 to 12 must equal the PAN).")
    mobile = re.sub(r"\D", "", mobile or "")[-10:]
    if len(mobile) != 10:
        raise AuthError("Enter a 10-digit mobile number.")
    email = _normalize_email(email)
    first_pw = generate_first_password()
    db = get_db()
    with system_identity():
        admin_service.check_plan_limit(firm["id"], "clients")
        with db.transaction():
            cid = db.insert("clients", {
                "firm_id": firm["id"], "name": business_name.strip(), "legal_name": business_name.strip(),
                "contact_person": (contact_person or "").strip() or None, "pan": pan, "gstin": gstin or None,
                "aadhaar_masked": aadhaar_masked, "business_type": business_type, "email": email, "phone": mobile,
                "address": address or None, "state_code": (gstin[:2] if gstin else state_code) or None,
                "signup_source": "self", "created_at": now_iso(), "updated_at": now_iso()})
            ensure_chart_of_accounts(firm["id"], cid)
            firm_service.ensure_financial_year(firm["id"], cid, fy_label_for(_dt.date.today()), 4)
            uid = _create_identity(email, first_pw, (contact_person or business_name).strip(), must_change=True)
            db.insert("client_users", {"firm_id": firm["id"], "client_id": cid, "user_id": uid, "is_primary": True,
                                       "created_at": now_iso()})
            audit(None, "client.self_registered", "clients", cid, firm_id=firm["id"], client_id=cid,
                  after={"name": business_name.strip(), "pan": pan, "email": email})
        notify_firm(firm["id"], "New client joined with your code", f"{business_name.strip()} (PAN {pan})",
                    permission="manage_clients")
    send_email(email, "Your Accounting Setu login",
               f"You are now connected to {firm['name']}.\nLogin ID: {email}\nFirst password: {first_pw}\n"
               "Choose 'Login as Client'. You will set your own password at first sign-in.")
    return {"client_id": cid, "firm_name": firm["name"], "login_email": email, "first_password": first_pw}


# ----------------------------------------------------------------- firm registration
def register_firm(*, firm_name: str, email: str, phone: str, admin_name: str, admin_email: str, password: str,
                  address: str = "", city: str = "", state_code: str = "", frn: str = "", gstin: str = "",
                  pan: str = "", must_change: bool = False) -> str:
    from services import admin_service

    db = get_db()
    if not firm_name.strip():
        raise AuthError("Firm name is required.")
    firm_email = _normalize_email(email)
    admin_email = _normalize_email(admin_email)
    with db.transaction():
        uid = _create_identity(admin_email, password, admin_name, must_change=must_change)
        firm_id = db.insert("firms", {
            "serial_no": _new_serial(db), "client_code": _new_client_code(db), "client_code_updated_at": now_iso(),
            "name": firm_name.strip(), "legal_name": firm_name.strip(), "email": firm_email, "phone": phone,
            "address": address, "city": city, "state_code": state_code or None, "frn": frn, "gstin": gstin or None,
            "pan": pan or None, "status": "pending" if firm_approval_required() else "active", "created_by": uid,
            "settings": {"submission_deadline_day": 5, "auto_process_on_submit": True, "retention_years": 8},
            "created_at": now_iso(), "updated_at": now_iso(),
        })
        db.insert("firm_staff", {"firm_id": firm_id, "user_id": uid, "role": "firm_admin", "designation": "Firm Admin",
                                 "created_at": now_iso()})
        admin_service.start_trial(firm_id)
        audit(None, "firm.registered", "firms", firm_id, firm_id=firm_id, after={"name": firm_name, "admin": admin_email})
    return firm_id


# ----------------------------------------------------------------- staff
def create_staff(ctx: AuthContext, *, email: str, full_name: str, role: str, temp_password: str,
                 designation: str = "", permissions: dict | None = None) -> str:
    from services import admin_service

    firm_id = require_firm(ctx, "manage_staff")
    if role not in ROLES:
        raise AuthError("Unknown role.")
    if role == "firm_admin" and ctx.role != "firm_admin":
        raise PermissionDenied("Only a Firm Admin can create another Firm Admin.")
    admin_service.check_plan_limit(firm_id, "staff")
    db = get_db()
    email = _normalize_email(email)
    with db.transaction():
        existing = db.fetchone("select id from user_profiles where email = ?", [email])
        if existing:
            raise AuthError("This email already has an account. Each staff member needs a unique login.")
        uid = _create_identity(email, temp_password, full_name, must_change=True)
        sid = db.insert("firm_staff", {"firm_id": firm_id, "user_id": uid, "role": role, "designation": designation,
                                       "permissions": permissions or {}, "created_at": now_iso()})
        audit(ctx, "staff.created", "firm_staff", sid, after={"email": email, "role": role})
    return sid


def update_staff(ctx: AuthContext, staff_id: str, *, role: str | None = None, is_active: bool | None = None,
                 permissions: dict | None = None, designation: str | None = None) -> None:
    firm_id = require_firm(ctx, "manage_staff")
    db = get_db()
    s = db.get("firm_staff", staff_id)
    if not s or s["firm_id"] != firm_id:
        raise PermissionDenied("Staff member not found in your firm.")
    if s["user_id"] == ctx.user_id and (is_active is False or (role and role != s["role"])):
        raise PermissionDenied("You cannot deactivate or change the role of your own account.")
    upd = {}
    if role is not None:
        if role not in ROLES:
            raise AuthError("Unknown role.")
        if role == "firm_admin" and ctx.role != "firm_admin":
            raise PermissionDenied("Only a Firm Admin can grant Firm Admin.")
        upd["role"] = role
    if is_active is not None:
        upd["is_active"] = is_active
    if permissions is not None:
        upd["permissions"] = permissions
    if designation is not None:
        upd["designation"] = designation
    db.update("firm_staff", staff_id, upd)
    audit(ctx, "staff.updated", "firm_staff", staff_id, before={k: s.get(k) for k in upd}, after=upd)


def list_staff(ctx: AuthContext) -> list[dict]:
    firm_id = require_firm(ctx, "view")
    return get_db().fetchall(
        "select fs.*, u.email, u.full_name, u.last_login_at from firm_staff fs join user_profiles u on u.id = fs.user_id "
        "where fs.firm_id = ? order by u.full_name", [firm_id])


# ----------------------------------------------------------------- client users & invitations
def create_client_user(ctx: AuthContext, client_id: str, *, email: str, full_name: str, temp_password: str) -> str:
    client = require_client(ctx, client_id, "manage_clients")
    db = get_db()
    email = _normalize_email(email)
    with db.transaction():
        uid = _create_identity(email, temp_password, full_name, must_change=True)
        db.insert("client_users", {"firm_id": client["firm_id"], "client_id": client_id, "user_id": uid,
                                   "is_primary": True, "created_at": now_iso()})
        audit(ctx, "client_user.created", "client_users", uid, client_id=client_id, after={"email": email})
    return uid


def invite_client_user(ctx: AuthContext, client_id: str, email: str) -> str:
    """Creates an invitation and emails the link. Returns the raw token (shown only to the inviter)."""
    from services.notification_service import send_email

    client = require_client(ctx, client_id, "manage_clients")
    email = _normalize_email(email)
    token = new_token()
    db = get_db()
    db.insert("client_invitations", {
        "firm_id": client["firm_id"], "client_id": client_id, "email": email, "token_hash": hash_token(token),
        "invited_by": ctx.user_id, "created_at": now_iso(),
        "expires_at": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)).replace(microsecond=0).isoformat(),
    })
    link = f"{settings.app_base_url}/?invite={token}"
    send_email(email, f"{ctx.firm_name} invited you to Accounting Setu",
               f"Hello,\n\n{ctx.firm_name} has invited you to submit documents for {client['name']} on Accounting Setu.\n"
               f"Open this link to set your password (valid 7 days):\n{link}\n")
    audit(ctx, "client_user.invited", "client_invitations", None, client_id=client_id, after={"email": email})
    return token


def get_invitation(token: str) -> dict | None:
    db = get_db()
    inv = db.fetchone("select i.*, c.name as client_name, f.name as firm_name from client_invitations i "
                      "join clients c on c.id = i.client_id join firms f on f.id = i.firm_id where i.token_hash = ?",
                      [hash_token(token)])
    if not inv or inv.get("accepted_at") or is_past(inv["expires_at"]):
        return None
    return inv


def accept_invitation(token: str, full_name: str, password: str) -> str:
    inv = get_invitation(token)
    if not inv:
        raise AuthError("This invitation link is invalid or has expired.")
    db = get_db()
    with db.transaction():
        uid = _create_identity(inv["email"], password, full_name)
        db.insert("client_users", {"firm_id": inv["firm_id"], "client_id": inv["client_id"], "user_id": uid,
                                   "created_at": now_iso()})
        db.update("client_invitations", inv["id"], {"accepted_at": now_iso()})
        audit(None, "client_user.invitation_accepted", "client_users", uid, firm_id=inv["firm_id"],
              client_id=inv["client_id"])
    return uid


# ----------------------------------------------------------------- password reset / change
def request_password_reset(email: str) -> None:
    """Always behaves the same whether or not the account exists (no user enumeration)."""
    from services.notification_service import send_email

    try:
        email = _normalize_email(email)
    except AuthError:
        return
    db = get_db()
    user = db.fetchone("select * from user_profiles where email = ? and is_active = ?", [email, True])
    if not user:
        return
    if settings.backend == "supabase":
        _supabase().auth.reset_password_for_email(email, {"redirect_to": settings.app_base_url})
        return
    token = new_token()
    db.insert("password_reset_tokens", {
        "user_id": user["id"], "token_hash": hash_token(token), "created_at": now_iso(),
        "expires_at": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).replace(microsecond=0).isoformat(),
    })
    send_email(email, "Reset your Accounting Setu password",
               f"Use this link within 1 hour to reset your password:\n{settings.app_base_url}/?reset={token}\n\n"
               "If you did not request this, ignore this email.")


def reset_password(token: str, new_password: str) -> None:
    validate_password(new_password)
    db = get_db()
    row = db.fetchone("select * from password_reset_tokens where token_hash = ?", [hash_token(token)])
    if not row or row.get("used_at") or is_past(row["expires_at"]):
        raise AuthError("Reset link is invalid or has expired.")
    with db.transaction():
        db.update("user_profiles", row["user_id"], {"password_hash": hash_password(new_password),
                                                    "must_change_password": False, "failed_logins": 0, "locked_until": None})
        db.update("password_reset_tokens", row["id"], {"used_at": now_iso()})
        audit(None, "auth.password_reset", "user_profiles", row["user_id"])


def change_password(ctx: AuthContext, old_password: str, new_password: str) -> None:
    validate_password(new_password)
    db = get_db()
    user = db.get("user_profiles", ctx.user_id)
    if old_password == new_password:
        raise AuthError("New password must be different from the current one.")
    if settings.backend == "supabase":
        try:  # verify the current password with Supabase Auth, then set the new one server-side
            res = _supabase().auth.sign_in_with_password({"email": user["email"], "password": old_password})
            ok = res.user is not None and res.user.id == ctx.user_id
        except Exception:
            ok = False
        if not ok:
            raise AuthError("Current password is incorrect.")
        _supabase_admin().auth.admin.update_user_by_id(ctx.user_id, {"password": new_password})
        db.update("user_profiles", ctx.user_id, {"must_change_password": False})
    else:
        if not verify_password(old_password, user.get("password_hash")):
            raise AuthError("Current password is incorrect.")
        db.update("user_profiles", ctx.user_id, {"password_hash": hash_password(new_password), "must_change_password": False})
    audit(ctx, "auth.password_changed", "user_profiles", ctx.user_id)


def must_change_password(ctx: AuthContext) -> bool:
    u = get_db().get("user_profiles", ctx.user_id)
    return bool(u and u.get("must_change_password"))


__all__ = ["AuthError", "IntegrityError"]
