"""End-to-end check of the app against the LIVE Supabase project (Auth + Postgres RLS + Storage).

    python -m scripts.supabase_e2e

Creates two throw-away firms (emails *@e2e-setu.test), signs in through Supabase Auth, uploads a document to
private Storage, processes and approves it into a voucher, verifies cross-tenant denial, then deletes everything
it created (auth users, rows, storage objects).
"""
from __future__ import annotations

import datetime as dt
import sys
import traceback
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings  # noqa: E402

assert settings.backend == "supabase", "Set DATA_BACKEND=supabase in .env"

from services import accounting_engine as ae, admin_service, ai_service, auth_service, document_service as ds, firm_service, notification_service, ocr_service  # noqa: E402
from services.db import current_user_id, get_db, system_identity  # noqa: E402
from utils.permissions import NotFound  # noqa: E402
from utils.validators import make_gstin  # noqa: E402

TAG = uuid.uuid4().hex[:6]
PW = "E2e-" + uuid.uuid4().hex[:12] + "9"
EMAILS = [f"{r}-{TAG}@e2e-setu.test" for r in ("admina", "adminb", "clienta")]
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)[:200]))
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))


def as_system():
    current_user_id.set(None)


def login(email):
    as_system()
    ctx = auth_service.login(email, PW)
    auth_service.activate_request_identity(ctx)
    return ctx


def pdf_invoice(client_gstin):
    import io

    from reportlab.pdfgen import canvas

    sup = make_gstin("27", "AABCS1111A")
    lines = ["Sharma Steel Suppliers", "TAX INVOICE", f"GSTIN: {sup}", "Invoice No: E2E-001",
             f"Invoice Date: {dt.date.today().replace(day=1):%d/%m/%Y}", "Place of Supply: 27", "Bill To:", "E2E Client",
             f"Buyer GSTIN: {client_gstin}", "Taxable Value: 10000.00", "CGST @ 9%: 900.00", "SGST @ 9%: 900.00",
             "Grand Total: 11800.00"]
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i, ln in enumerate(lines):
        c.drawString(50, 800 - 18 * i, ln)
    c.save()
    return buf.getvalue()


OWNER_EMAIL = f"owner-{TAG}@e2e-setu.test"


def ensure_platform_owner():
    """Reuse an existing Super Admin to check the pending-firm notification, or create a temporary one
    (cleaned up at the end) if this live project has none yet."""
    as_system()
    if auth_service.super_admin_exists():
        row = get_db().fetchone("select id from user_profiles where is_super_admin = ? limit 1", [True])
        return row["id"], False
    uid = auth_service.create_super_admin(OWNER_EMAIL, PW, "E2E Temp Owner")
    return uid, True


def cleanup(firm_ids, storage_paths):
    as_system()
    db = get_db()
    from services.storage_service import get_storage

    st = get_storage()
    for p in storage_paths:
        try:
            st.client.storage.from_(st.bucket).remove([p])
        except Exception as exc:  # noqa: BLE001
            print("storage cleanup:", exc)
    # matches every test email this run created, including the temporary platform owner (if any)
    uids = [r["id"] for r in db.fetchall(f"select id from user_profiles where email like '%-{TAG}@e2e-setu.test'")]
    with db.transaction():
        db.execute("alter table audit_logs disable trigger trg_audit_immutable")
        db.execute("alter table accounting_vouchers disable trigger trg_guard_locked_voucher")
        db.execute("delete from notifications where body like ?", [f"%{TAG}%"])  # may be on a real super admin's account
        if firm_ids:
            marks = ",".join("?" for _ in firm_ids)
            db.execute(f"delete from audit_logs where firm_id in ({marks})", firm_ids)
            db.execute(f"delete from notifications where firm_id in ({marks})", firm_ids)
            db.execute(f"delete from firms where id in ({marks})", firm_ids)
        if uids:
            marks = ",".join("?" for _ in uids)
            db.execute(f"delete from audit_logs where user_id in ({marks})", uids)
            db.execute(f"delete from audit_logs where entity_id in ({marks})", uids)  # e.g. super_admin.created
            db.execute(f"delete from user_profiles where id in ({marks})", uids)
        db.execute("alter table audit_logs enable trigger trg_audit_immutable")
        db.execute("alter table accounting_vouchers enable trigger trg_guard_locked_voucher")
    admin = auth_service._supabase_admin()
    # also remove auth users whose profile row was never written
    from scripts.apply_migrations import connect

    uids = list(set(uids) | {str(r[0]) for r in connect().run(
        "select id from auth.users where email like :p", p=f"%-{TAG}@e2e-setu.test")})
    for uid in uids:
        try:
            admin.auth.admin.delete_user(uid)
        except Exception as exc:  # noqa: BLE001
            print("auth cleanup:", exc)
    left = db.scalar(f"select count(*) from user_profiles where email like '%-{TAG}@e2e-setu.test'")
    print(f"cleanup done (test users left: {left})")


def main():
    ocr_service.set_ocr(ocr_service.OCRProvider())
    ai_service.set_provider(ai_service.LocalRulesProvider())
    firm_ids, paths = [], []
    try:
        as_system()
        admin_service.ensure_default_plans()
        owner_id, owner_created = ensure_platform_owner()
        ra = auth_service.signup_firm(firm_name=f"E2E Firm A {TAG}", email=EMAILS[0], phone="9876543210",
                                      admin_name="Admin A", state_code="27")
        rb = auth_service.signup_firm(firm_name=f"E2E Firm B {TAG}", email=EMAILS[1], phone="9876543211",
                                      admin_name="Admin B", state_code="07")
        fa, fb = ra["firm_id"], rb["firm_id"]
        firm_ids += [fa, fb]
        check("CA firm sign-up: serial no + secret code + first password", ra["serial_no"].startswith("CAF")
              and len(ra["client_code"]) == 9 and ra["first_password"].startswith("Setu-"), ra["serial_no"])
        check("New firm is pending until Super Admin approves (live default)", ra["status"] == "pending", ra["status"])
        check("Pending firm's code does not yet work for clients", auth_service.firm_by_code(ra["client_code"]) is None)
        notif = get_db().fetchone("select id from notifications where user_id = ? and title like ? order by created_at desc",
                                  [owner_id, "%CA firm%"])
        check("Super Admin was notified of the new firm", notif is not None, notif)
        # the platform owner reviews and approves both firms, exactly as on the CA Firms page
        as_system()
        get_db().execute("update firms set status = 'active' where id in (?, ?)", [fa, fb])
        check("Firm is active once Super Admin approves it", auth_service.firm_by_code(ra["client_code"]) is not None)
        a = auth_service.login(EMAILS[0], ra["first_password"], portal="firm")
        auth_service.activate_request_identity(a)
        check("First login (Supabase Auth) asks to set own password", auth_service.must_change_password(a))
        auth_service.change_password(a, ra["first_password"], PW)
        check("Own password set on Supabase; first password retired", not auth_service.must_change_password(a))
        as_system()
        try:
            auth_service.login(EMAILS[0], ra["first_password"])
            check("Old first password no longer works", False, "still works")
        except auth_service.AuthError:
            check("Old first password no longer works", True)
        b0 = auth_service.login(EMAILS[1], rb["first_password"])
        auth_service.activate_request_identity(b0)
        auth_service.change_password(b0, rb["first_password"], PW)
        a = login(EMAILS[0])
        check("Sign-in through Supabase Auth (firm admin A)", a.kind == "staff" and a.firm_id == fa, a)
        gst = make_gstin("27", "AAKFE1234G")
        as_system()
        rc = auth_service.signup_client(firm_code=ra["client_code"], business_name="E2E Client", contact_person="E2E",
                                        email=EMAILS[2], mobile="9876500000", pan=gst[2:12], aadhaar="234123412346",
                                        business_type="Proprietorship", gstin=gst)
        cid = rc["client_id"]
        check("Client sign-up with firm code links to firm A", rc["firm_name"] == f"E2E Firm A {TAG}")
        a = login(EMAILS[0])
        check("Firm A sees the new client with chart of accounts", len(ae.list_ledgers(a, cid)) > 30)
        as_system()
        cu = auth_service.login(EMAILS[2], rc["first_password"], portal="client")
        auth_service.activate_request_identity(cu)
        auth_service.change_password(cu, rc["first_password"], PW)
        cu = login(EMAILS[2])
        check("Client user signs in, scoped to own client", cu.is_client and cu.client_id == cid)
        today = dt.date.today()
        doc = ds.upload_document(cu, cid, today.year, today.month, "e2e.pdf", pdf_invoice(gst), "purchase_invoice")
        d = get_db().get("documents", doc)
        paths.append(d["storage_path"])
        check("Upload to private Supabase Storage", d["storage_path"].startswith(f"{fa}/{cid}/"), d["storage_path"])
        data, _ = ds.read_document_bytes(cu, doc)
        check("Download original after authorization", data.startswith(b"%PDF"))
        a = login(EMAILS[0])
        status = ds.process_document(a, doc)
        ext = ds.current_extraction(a, doc)
        check("Extraction pipeline on Supabase", ext and ext["data"].get("invoice_no") == "E2E-001", status)
        ds.save_correction(a, doc, {"itc_eligibility": "eligible"})
        res = ds.approve_document(a, doc, acknowledge_warnings=True)
        check("Approval creates invoice + draft voucher", res.get("voucher_id"), res)
        ae.approve_voucher(a, res["voucher_id"], acknowledge_review=True)
        v = get_db().get("accounting_vouchers", res["voucher_id"])
        check("Voucher approved (balanced trigger passed)", v["status"] == "approved", v["status"])
        b = login(EMAILS[1])
        for label, fn in (("Firm B cannot open firm A client", lambda: firm_service.update_client(b, cid, {"name": "x"})),
                          ("Firm B cannot download firm A document", lambda: ds.read_document_bytes(b, doc)),
                          ("Firm B cannot list firm A vouchers", lambda: ae.list_vouchers(b, cid))):
            try:
                fn()
                check(label, False, "allowed!")
            except NotFound:
                check(label, True)
        rows = get_db().fetchall("select id from accounting_vouchers")  # raw query as firm B, filtered by Postgres RLS
        check("Postgres RLS hides firm A vouchers from firm B (raw SQL)", rows == [], rows)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        check("Unexpected error", False, exc)
    finally:
        cleanup(firm_ids, paths)
    ok = sum(r[1] for r in results)
    print(f"\n{ok}/{len(results)} passed")
    raise SystemExit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    main()
