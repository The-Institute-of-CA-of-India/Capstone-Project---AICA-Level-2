"""CA firm / client self-registration with firm serial number and secret client code.

Default behaviour (as decided by the platform owner): every new CA firm must be approved by the
Super Admin before it is active; the Super Admin is notified when one signs up.
"""
import re

import pytest

from services import admin_service, auth_service, document_service, notification_service, tenancy
from services.auth_service import AuthError
from services.db import get_db
from utils.permissions import NotFound

AADHAAR_OK = "234123412346"   # valid Verhoeff test number
PAN = "ABCPK1234F"


def _firm(**kw):
    args = dict(firm_name="Kapoor & Associates", email="office@kapoor.test", phone="9876543210", admin_name="CA Rohit Kapoor",
                city="Mumbai", state_code="27")
    args.update(kw)
    return auth_service.signup_firm(**args)


def _approve(env, firm_id):
    admin_service.set_firm_status(env.sa, firm_id, "active")


def _active_firm(env, **kw):
    res = _firm(**kw)
    _approve(env, res["firm_id"])
    return res


def _client(code, **kw):
    args = dict(firm_code=code, business_name="Shree Ganesh Traders", contact_person="Suresh", email="suresh@ganesh.test",
                mobile="+91 98765 43210", pan=PAN, aadhaar=AADHAAR_OK, business_type="Proprietorship")
    args.update(kw)
    return auth_service.signup_client(**args)


def test_firm_signup_is_pending_until_super_admin_approves(env):
    res = _firm()
    assert re.fullmatch(r"CAF\d{5}", res["serial_no"])
    assert re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}", res["client_code"])
    assert res["first_password"].startswith("Setu-") and " " not in res["first_password"]
    assert res["status"] == "pending"                       # every new firm waits for approval by default
    # the Super Admin is notified
    notes = notification_service.list_notifications(env.sa, unread_only=True)
    assert any("Kapoor & Associates" in n["title"] + (n.get("body") or "") for n in notes)
    # the firm admin can sign in, but has no working permissions until approved
    ctx = auth_service.login(res["login_email"], res["first_password"], portal="firm")
    assert ctx.is_staff and ctx.role == "firm_admin" and ctx.firm_status == "pending"
    assert not ctx.can("manage_clients")
    assert auth_service.must_change_password(ctx)           # first login → must choose own password
    auth_service.change_password(ctx, res["first_password"], "mynewpass")
    assert not auth_service.must_change_password(ctx)
    ctx = auth_service.login(res["login_email"], "mynewpass", portal="firm")
    # Super Admin approves it, exactly as on the CA Firms page
    admin_service.set_firm_status(env.sa, res["firm_id"], "active")
    ctx = auth_service.login(res["login_email"], "mynewpass", portal="firm")
    assert ctx.firm_status == "active" and ctx.can("manage_clients")


def test_serial_numbers_and_codes_are_unique(env):
    a, b = _firm(), _firm(firm_name="Mehta CA", email="office@mehta.test")
    assert a["serial_no"] != b["serial_no"] and a["client_code"] != b["client_code"]
    serials = [r["serial_no"] for r in get_db().fetchall("select serial_no from firms")]
    assert len(serials) == len(set(serials)) and all(serials)   # fixture firms were back-filled too


def test_client_signup_with_code_links_to_that_firm_only(env):
    f = _active_firm(env)
    res = _client(f["client_code"].lower().replace("-", " "))   # code is forgiving about case/spaces
    assert res["firm_name"] == "Kapoor & Associates"
    c = auth_service.login(res["login_email"], res["first_password"], portal="client")
    assert c.is_client and c.firm_id == f["firm_id"] and c.client_id == res["client_id"]
    assert auth_service.must_change_password(c)
    client = get_db().get("clients", res["client_id"])
    assert client["aadhaar_masked"] == "XXXX-XXXX-2346" and AADHAAR_OK not in str(client)   # full Aadhaar never stored
    assert client["signup_source"] == "self" and client["pan"] == PAN
    # the firm that owns the code sees the client; another firm does not
    firm_ctx = auth_service.login(f["login_email"], f["first_password"])
    assert res["client_id"] in tenancy.accessible_client_ids(firm_ctx)
    with pytest.raises(NotFound):
        tenancy.require_client(env.a_admin, res["client_id"])
    # client dashboard data works for the new client
    assert document_service.list_documents(c, res["client_id"]) == []


def test_client_cannot_join_a_firm_still_pending_approval(env):
    f = _firm()  # not approved yet
    with pytest.raises(AuthError, match="code not found"):
        _client(f["client_code"])
    _approve(env, f["firm_id"])
    _client(f["client_code"])   # works once approved


def test_client_signup_validation(env):
    code = _active_firm(env)["client_code"]
    with pytest.raises(AuthError, match="code not found"):
        _client("ZZZZ-ZZZZ")
    with pytest.raises(AuthError, match="PAN"):
        _client(code, pan="12345")
    with pytest.raises(AuthError, match="Aadhaar"):
        _client(code, aadhaar="234123412345")              # checksum fails
    with pytest.raises(AuthError, match="Aadhaar is required"):
        _client(code, aadhaar="")
    _client(code, business_type="Private Limited", aadhaar="", email="pvt@x.test")   # companies need no Aadhaar
    with pytest.raises(AuthError, match="GSTIN does not belong"):
        _client(code, gstin="27AAPFU0939F1ZV", email="g@x.test")
    with pytest.raises(AuthError, match="mobile"):
        _client(code, mobile="123", email="m@x.test")


def test_wrong_portal_is_refused(env):
    f = _active_firm(env)
    with pytest.raises(AuthError, match="CA firm account"):
        auth_service.login(f["login_email"], f["first_password"], portal="client")
    r = _client(f["client_code"])
    with pytest.raises(AuthError, match="client account"):
        auth_service.login(r["login_email"], r["first_password"], portal="firm")
    with pytest.raises(AuthError, match="administrator"):
        auth_service.login("owner@platform.test", "Passw0rd!x", portal="firm")


def test_regenerated_code_keeps_existing_clients(env):
    f = _active_firm(env)
    r = _client(f["client_code"])
    ctx = auth_service.login(f["login_email"], f["first_password"])
    new = auth_service.regenerate_client_code(ctx)
    assert new != f["client_code"]
    assert auth_service.firm_by_code(f["client_code"]) is None        # old code no longer accepts sign-ups
    assert auth_service.firm_by_code(new)["id"] == f["firm_id"]
    assert auth_service.login(r["login_email"], r["first_password"]).client_id == r["client_id"]
    with pytest.raises(Exception):
        auth_service.regenerate_client_code(env.cu_a1)               # clients cannot change firm codes


def test_super_admin_can_switch_approval_off(env):
    admin_service.set_platform_setting(env.sa, "features", {"require_firm_approval": False})
    res = _firm(email="instant@x.test")
    assert res["status"] == "active"                        # immediately usable when the owner disables approval
    _client(res["client_code"])                              # clients can join right away too


def test_registrations_can_be_closed(env):
    admin_service.set_platform_setting(env.sa, "features", {"registrations": False})
    with pytest.raises(AuthError, match="closed"):
        _firm(email="late@x.test")
    # turning registrations off does not silently disable the approval requirement
    admin_service.set_platform_setting(env.sa, "features", {"registrations": True})
    assert _firm(email="late2@x.test")["status"] == "pending"
