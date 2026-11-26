import datetime as dt

import pytest

from services import (accounting_engine as ae, admin_service, assistant_service, auth_service, document_service,
                      firm_service, report_service, tenancy)
from services.auth_service import AuthError
from services.db import get_db
from tests.conftest import PW, make_pdf, purchase
from utils.permissions import NotFound, PermissionDenied


# ---------------------------------------------------------------- authentication
def test_super_admin_login(env):
    assert env.sa.is_super_admin and env.sa.firm_id is None


def test_firm_admin_staff_and_client_login(env):
    assert env.a_admin.kind == "staff" and env.a_admin.role == "firm_admin" and env.a_admin.firm_id == env.firm_a
    assert env.acct.role == "accountant" and "approve_vouchers" not in env.acct.permissions
    assert env.cu_a1.kind == "client" and env.cu_a1.client_id == env.c_a1 and env.cu_a1.firm_id == env.firm_a


def test_wrong_password_and_lockout(env):
    for _ in range(auth_service.MAX_FAILED_LOGINS):
        with pytest.raises(AuthError):
            auth_service.login("acct@alpha.test", "wrong-password1")
    with pytest.raises(AuthError, match="locked"):
        auth_service.login("acct@alpha.test", PW)


def test_unknown_user_gets_generic_error(env):
    with pytest.raises(AuthError, match="Invalid email or password"):
        auth_service.login("nobody@x.test", PW)


def test_second_super_admin_refused(env):
    with pytest.raises(PermissionDenied):
        auth_service.create_super_admin("x@y.test", PW, "X")


def test_password_policy(env):
    for bad in ("", "      ", "has space", "abc"):
        with pytest.raises(AuthError):
            auth_service.validate_password(bad)
    for good in ("onlyletters", "123456", "Kartik@1", "##$$%%"):
        auth_service.validate_password(good)


def test_pending_firm_has_no_access(env):
    admin_service.set_platform_setting(env.sa, "features", {"require_firm_approval": True})
    fid = auth_service.register_firm(firm_name="Gamma", email="g@f.test", phone="3", admin_name="G", admin_email="g@g.test",
                                     password=PW)
    ctx = auth_service.login("g@g.test", PW)
    assert ctx.firm_status == "pending"
    with pytest.raises(PermissionDenied):
        firm_service.create_client(ctx, {"name": "X"})
    assert tenancy.accessible_client_ids(ctx) == []
    admin_service.set_firm_status(env.sa, fid, "suspended")
    with pytest.raises(PermissionDenied):
        tenancy.require_firm(auth_service.login("g@g.test", PW), "manage_clients")


def test_suspended_firm_blocks_client_login(env):
    admin_service.set_firm_status(env.sa, env.firm_b, "suspended")
    with pytest.raises(AuthError, match="not active"):
        auth_service.login("owner@clientb1.test", PW)


def test_password_reset_flow(env, monkeypatch):
    sent = {}
    monkeypatch.setattr("services.notification_service.send_email", lambda to, subj, body: sent.update(body=body) or "x")
    auth_service.request_password_reset("acct@alpha.test")
    token = sent["body"].split("reset=")[1].split()[0]
    auth_service.reset_password(token, "NewPassw0rd")
    assert auth_service.login("acct@alpha.test", "NewPassw0rd").role == "accountant"
    with pytest.raises(AuthError):
        auth_service.reset_password(token, "Another1pw")  # single use
    auth_service.request_password_reset("nobody@nowhere.test")  # no error, no enumeration


def test_client_invitation(env, monkeypatch):
    monkeypatch.setattr("services.notification_service.send_email", lambda *a: "x")
    token = auth_service.invite_client_user(env.a_admin, env.c_a2, "accounts@clienta2.test")
    assert auth_service.get_invitation(token)["client_id"] == env.c_a2
    auth_service.accept_invitation(token, "A2 Accounts", PW)
    ctx = auth_service.login("accounts@clienta2.test", PW)
    assert ctx.is_client and ctx.client_id == env.c_a2
    with pytest.raises(AuthError):
        auth_service.accept_invitation(token, "again", PW)


def test_super_admin_cannot_read_tenant_financial_data(env):
    with pytest.raises(NotFound):
        tenancy.require_client(env.sa, env.c_a1)
    with pytest.raises(NotFound):
        report_service.trial_balance(env.sa, env.c_a1, dt.date(2025, 4, 1), dt.date(2025, 4, 30))
    assert admin_service.platform_metrics(env.sa)["firms"] == 2


def test_non_admin_cannot_use_super_admin_functions(env):
    with pytest.raises(PermissionDenied):
        admin_service.list_firms(env.a_admin)
    with pytest.raises(PermissionDenied):
        admin_service.set_firm_status(env.a_admin, env.firm_b, "suspended")


# ---------------------------------------------------------------- multi-tenant isolation
def test_firm_a_cannot_access_firm_b(env):
    with pytest.raises(NotFound):
        tenancy.require_client(env.a_admin, env.c_b1)
    assert env.c_b1 not in {c["id"] for c in tenancy.list_clients(env.a_admin)}
    with pytest.raises(NotFound):
        ae.list_ledgers(env.a_admin, env.c_b1)
    with pytest.raises(NotFound):
        firm_service.update_client(env.a_admin, env.c_b1, {"name": "hacked"})


def test_client_a_cannot_access_client_b(env):
    with pytest.raises(NotFound):
        tenancy.require_client(env.cu_a1, env.c_a2)
    with pytest.raises(NotFound):
        document_service.upload_document(env.cu_a1, env.c_a2, 2025, 4, "x.pdf", make_pdf([purchase()]), "purchase_invoice")
    with pytest.raises(NotFound):
        document_service.list_documents(env.cu_a1, env.c_b1)


def test_client_cannot_perform_staff_actions(env):
    with pytest.raises(PermissionDenied):
        tenancy.require_client(env.cu_a1, env.c_a1, "approve_vouchers")
    with pytest.raises(PermissionDenied):
        ae.create_ledger(env.cu_a1, env.c_a1, "My ledger", "Indirect Expenses")


def test_staff_cannot_access_unassigned_client(env):
    ids = tenancy.accessible_client_ids(env.acct)
    assert env.c_a1 in ids and env.c_a2 not in ids
    with pytest.raises(NotFound):
        tenancy.require_client(env.acct, env.c_a2)
    # firm admin sees all firm clients
    assert set(tenancy.accessible_client_ids(env.a_admin)) == {env.c_a1, env.c_a2}


def test_read_only_staff_cannot_write(env):
    firm_service.assign_staff(env.a_admin, env.c_a1, [env.acct.staff_id, env.rev.staff_id, env.ro.staff_id])
    tenancy.require_client(env.ro, env.c_a1, "view")
    with pytest.raises(PermissionDenied):
        tenancy.require_client(env.ro, env.c_a1, "prepare_vouchers")


def test_permission_overrides(env):
    auth_service.update_staff(env.a_admin, env.acct.staff_id, permissions={"grant": ["approve_vouchers"], "revoke": ["export_tally"]})
    ctx = auth_service.build_context(env.acct.user_id)
    assert ctx.can("approve_vouchers") and not ctx.can("export_tally")


def test_storage_download_blocked_across_tenants(env):
    y, m = dt.date.today().year, dt.date.today().month
    doc_id = document_service.upload_document(env.cu_a1, env.c_a1, y, m, "inv.pdf", make_pdf([purchase()]), "purchase_invoice")
    data, _ = document_service.read_document_bytes(env.cu_a1, doc_id)
    assert data.startswith(b"%PDF")
    for intruder in (env.cu_a2, env.cu_b1, env.b_admin):
        with pytest.raises(NotFound):
            document_service.read_document_bytes(intruder, doc_id)
    # staff not assigned to... (acct is assigned to A1) can read; super admin cannot
    document_service.read_document_bytes(env.acct, doc_id)
    with pytest.raises(NotFound):
        document_service.read_document_bytes(env.sa, doc_id)


def test_voucher_cannot_use_other_clients_ledger(env):
    led_b = ae.list_ledgers(env.b_admin, env.c_b1)[0]
    led_a = ae.list_ledgers(env.a_admin, env.c_a1)[0]
    draft = ae.VoucherDraft("Journal", dt.date.today(), [ae.Line(led_a["id"], "Dr", ae.D("100")), ae.Line(led_b["id"], "Cr", ae.D("100"))])
    with pytest.raises(PermissionDenied):
        ae.create_voucher(env.a_admin, env.c_a1, draft)


def test_assistant_respects_tenancy(env):
    with pytest.raises(NotFound):
        assistant_service.answer(env.cu_a1, "What were my sales this month?", env.c_b1)
    r = assistant_service.answer(env.cu_a1, "Which clients have not submitted documents?", env.c_a1)
    assert "staff only" in r["answer"]


def test_audit_log_written_for_privileged_actions(env):
    actions = {r["action"] for r in get_db().fetchall("select action from audit_logs")}
    assert {"firm.registered", "firm.active", "client.created", "staff.created", "auth.login"} <= actions
