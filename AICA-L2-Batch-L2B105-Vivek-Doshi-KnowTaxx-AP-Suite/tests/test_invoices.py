import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from conftest import login, make_centre, make_client, make_invoice, make_rule, make_user, make_vendor, ok_page
from openpyxl import load_workbook

from app.models import Invoice, OfflineSyncQueue, db
from app.reports import data as report_data
from app.reports.export import tally_csv
from app.utils import sanitize_cell

SAMPLES = Path(__file__).parent / "sample_invoices"


def upload(http, client_id, name="invoice_gst_1.png", data=None):
    payload = data if data is not None else (SAMPLES / name).read_bytes()
    return http.post(f"/clients/{client_id}/invoices/upload", data={"files": (io.BytesIO(payload), name)},
                     content_type="multipart/form-data", headers={"Accept": "application/json"})


def review_form(**overrides):
    data = {"final_vendor_name": "Vendor One", "vendor_id": "0", "final_gstin": "", "final_invoice_number": "INV-9", "final_invoice_date": "2026-10-10",
            "due_date": "", "final_taxable_amount": "10000", "final_cgst": "900", "final_sgst": "900", "final_igst": "", "final_total_amount": "11800",
            "final_tds_section": "", "final_tds_rate": "", "final_hsn_sac": "", "expense_category": "", "cost_centre_id": "0", "gl_account": "",
            "final_description": "", "narration": ""}
    data.update(overrides)
    return data


def test_upload_creates_invoice_and_stores_file(client, app):
    c = make_client()
    make_user("acc", "accountant", [c])
    login(client, "acc")
    response = upload(client, c.id)
    assert response.status_code == 200 and response.json["results"][0]["ok"]
    invoice = Invoice.query.one()
    assert invoice.source == "upload" and invoice.file_hash and invoice.status in ("auto_captured", "pending_review")
    assert (Path(app.config["FILES_ROOT"]) / invoice.original_filepath).exists()
    assert invoice.original_filepath.startswith("C0001/invoices/")


def test_upload_rejects_disguised_file(client):
    c = make_client()
    make_user("acc", "accountant", [c])
    login(client, "acc")
    response = upload(client, c.id, name="evil.png", data=b"MZ not an image")
    assert response.json["results"][0]["ok"] is False and Invoice.query.count() == 0


def test_same_file_flagged_duplicate(client):
    c = make_client()
    make_user("acc", "accountant", [c])
    login(client, "acc")
    upload(client, c.id)
    second = upload(client, c.id).json["results"][0]
    assert second["duplicate"] is True


def test_field_staff_uploads_only_own_view(client):
    c = make_client()
    make_user("field", "field_staff", [c])
    login(client, "field")
    upload(client, c.id)
    invoice = Invoice.query.one()
    assert client.get(f"/invoices/{invoice.id}/review").status_code == 403
    assert client.get(f"/clients/{c.id}/invoices").status_code == 200
    assert client.get(f"/clients/{c.id}/vendors").status_code == 403


def test_review_page_renders_and_saves(client):
    c = make_client()
    make_user("acc", "accountant", [c])
    login(client, "acc")
    upload(client, c.id)
    invoice = Invoice.query.one()
    assert ok_page(client.get(f"/invoices/{invoice.id}/review"))
    assert ok_page(client.get(f"/invoices/{invoice.id}"))
    assert client.get(f"/invoices/{invoice.id}/preview").mimetype == "image/png"
    response = client.post(f"/invoices/{invoice.id}/review", data=review_form(save="1"))
    assert response.status_code == 302
    db.session.refresh(invoice)
    assert invoice.status == "pending_review" and invoice.final_invoice_number == "INV-9"
    assert invoice.final_total_amount == Decimal("11800")


def test_submit_blocked_when_arithmetic_wrong(client):
    c = make_client()
    make_user("acc", "accountant", [c])
    login(client, "acc")
    invoice = make_invoice(c, status="pending_review")
    response = client.post(f"/invoices/{invoice.id}/review", data=review_form(final_total_amount="99999", submit_approval="1"))
    assert b"does not equal" in response.data
    db.session.refresh(invoice)
    assert invoice.status == "pending_review"


def test_submit_routes_to_approver(client):
    c = make_client()
    make_user("acc", "accountant", [c])
    approver = make_user("boss", "approver")
    make_rule(c, approver)
    login(client, "acc")
    invoice = make_invoice(c, status="pending_review")
    response = client.post(f"/invoices/{invoice.id}/review", data=review_form(submit_approval="1"))
    assert response.status_code == 302
    db.session.refresh(invoice)
    assert invoice.status == "pending_approval" and invoice.current_approver_id == approver.id and invoice.current_level == 1


def test_submit_with_no_rule_stays_reviewed(client):
    c = make_client()
    make_user("acc", "accountant", [c])
    login(client, "acc")
    invoice = make_invoice(c, status="pending_review")
    client.post(f"/invoices/{invoice.id}/review", data=review_form(submit_approval="1"))
    db.session.refresh(invoice)
    assert invoice.status == "reviewed"


def test_blacklisted_vendor_blocked(client):
    c = make_client()
    vendor = make_vendor(c, status="blacklisted", gstin=None)
    approver = make_user("boss", "approver")
    make_rule(c, approver)
    make_user("acc", "accountant", [c])
    login(client, "acc")
    invoice = make_invoice(c, status="pending_review", vendor_id=vendor.id)
    response = client.post(f"/invoices/{invoice.id}/review", data=review_form(vendor_id=str(vendor.id), submit_approval="1"))
    assert b"blacklisted" in response.data
    db.session.refresh(invoice)
    assert invoice.status == "pending_review"


def test_same_number_vendor_amount_flagged(client):
    c = make_client()
    make_user("acc", "accountant", [c])
    login(client, "acc")
    make_invoice(c, status="approved", final_invoice_number="INV-9", final_vendor_name="Vendor One")
    invoice = make_invoice(c, status="pending_review", final_invoice_number="DRAFT")
    client.post(f"/invoices/{invoice.id}/review", data=review_form(save="1"))
    db.session.refresh(invoice)
    assert invoice.is_duplicate_flag and invoice.duplicate_of_id


def test_pay_only_when_approved(client):
    c = make_client()
    make_user("acc", "accountant", [c])
    login(client, "acc")
    invoice = make_invoice(c, status="pending_approval")
    client.post(f"/invoices/{invoice.id}/pay", data={"payment_date": "2026-11-01", "payment_reference": "UTR1"})
    db.session.refresh(invoice)
    assert invoice.status == "pending_approval"
    invoice.status = "approved"
    db.session.commit()
    client.post(f"/invoices/{invoice.id}/pay", data={"payment_date": "2026-11-01", "payment_reference": "UTR1"})
    db.session.refresh(invoice)
    assert invoice.status == "paid" and invoice.payment_reference == "UTR1"


def test_other_clients_invoice_blocked(client):
    a, b = make_client("A", "C0001"), make_client("B", "C0002")
    invoice = make_invoice(b)
    make_user("acc", "accountant", [a])
    login(client, "acc")
    assert client.get(f"/invoices/{invoice.id}").status_code == 403
    assert client.get(f"/invoices/{invoice.id}/review").status_code == 403


# ---- Reports ----

def test_all_reports_and_exports(client):
    c = make_client()
    centre = make_centre(c)
    make_user("acc", "accountant", [c])
    login(client, "acc")
    today = date.today()
    make_invoice(c, status="approved", final_invoice_date=today, invoice_date=today, cost_centre_id=centre.id, expense_category="Rent",
                 final_cgst=Decimal("900"), final_sgst=Decimal("900"), final_taxable_amount=Decimal("10000"), final_tds_section="194I", final_tds_rate=Decimal("10"))
    base = f"/clients/{c.id}/reports"
    for page in ("dashboard", "cost-centre", "variance", "aging"):
        assert ok_page(client.get(f"{base}/{page}")), page
    assert ok_page(client.get(f"{base}/cost-centre?cc={centre.id}"))
    for name in ("dashboard.xlsx", "cost-centre.xlsx", "variance.xlsx", "aging.xlsx", "invoices.xlsx"):
        response = client.get(f"{base}/export/{name}")
        assert response.status_code == 200, name
        assert load_workbook(io.BytesIO(response.data)).sheetnames
    pdf = client.get(f"{base}/export/dashboard.pdf")
    assert pdf.data[:5] == b"%PDF-"
    assert client.get(f"{base}/export/nope").status_code == 404


def test_tally_csv_balances():
    invoice = Invoice(final_invoice_date=date(2026, 10, 5), final_invoice_number="X1", final_vendor_name="=HACK()", final_total_amount=Decimal("11800"),
                      final_taxable_amount=Decimal("10000"), final_cgst=Decimal("900"), final_sgst=Decimal("900"), final_tds_section="194J",
                      final_tds_rate=Decimal("10"), gl_account="Professional Fees")
    rows = list(csv.DictReader(io.StringIO(tally_csv([invoice]))))
    debit = sum(float(r["Debit"] or 0) for r in rows)
    credit = sum(float(r["Credit"] or 0) for r in rows)
    assert debit == credit == 11800.0
    assert any(r["Ledger"] == "TDS Payable - 194J" and r["Credit"] == "1000.00" for r in rows)
    assert all(not r["Ledger"].startswith("=") for r in rows), "formula injection must be neutralised"
    assert rows[0]["Date"] == "05-10-2026"


def test_sanitize_cell():
    assert sanitize_cell("=1+1") == "'=1+1"
    assert sanitize_cell("Normal") == "Normal"
    assert sanitize_cell(-5) == -5


def test_traffic_light_bands():
    assert report_data.traffic_light(3) == "green"
    assert report_data.traffic_light(-40) == "green"
    assert report_data.traffic_light(10) == "amber"
    assert report_data.traffic_light(20) == "red"


def test_fiscal_quarters():
    assert report_data.fiscal_quarter_months(2026, 11) == [(2026, 10), (2026, 11), (2026, 12)]
    assert report_data.fiscal_quarter_months(2026, 2) == [(2026, 1), (2026, 2), (2026, 3)]


def test_aging_buckets_and_msme_flags(app):
    c = make_client()
    msme = make_vendor(c, name="Small Co", gstin=None)
    msme.msme_registered = True
    db.session.commit()
    today = date.today()
    make_invoice(c, status="approved", vendor_id=msme.id, final_invoice_date=today - timedelta(days=50), due_date=today - timedelta(days=5), total="1000")
    make_invoice(c, status="approved", vendor_id=msme.id, final_invoice_date=today - timedelta(days=35), due_date=today + timedelta(days=10), total="2000")
    make_invoice(c, status="paid", final_invoice_date=today - timedelta(days=200), due_date=today - timedelta(days=170), total="9999")
    data = report_data.aging_data(c.id)
    assert data["totals"]["1-30"] == 1000 and data["totals"]["Current"] == 2000 and data["totals"]["total"] == 3000
    states = {m["state"] for m in data["msme"]}
    assert states == {"breached", "approaching"}


def test_variance_commentary_names_driver(app):
    c = make_client()
    centre = make_centre(c, name="Sales")
    from app.models import Budget
    today = date.today()
    db.session.add(Budget(client_id=c.id, cost_centre_id=centre.id, period_year=today.year, period_month=today.month, budget_amount=Decimal("1000")))
    db.session.commit()
    make_invoice(c, status="approved", final_invoice_date=today, cost_centre_id=centre.id, final_taxable_amount=Decimal("1500"), final_vendor_name="Big Vendor")
    data = report_data.variance_data(c.id, today.year, today.month)
    row = data["rows"][0]
    assert row["variance"] == 500 and row["pct"] == 50.0 and row["light"] == "red"
    assert "Big Vendor" in data["commentary"][0] and "Sales exceeded budget" in data["commentary"][0]


def test_admin_pages_and_backup(client):
    make_client()
    make_user("root", "admin")
    login(client, "root")
    for path in ("/admin/users", "/admin/users/new", "/admin/roles", "/admin/audit-log", "/admin/email-config", "/admin/backup"):
        assert ok_page(client.get(path)), path
    response = client.post("/admin/backup/run")
    assert response.status_code == 302
    page = client.get("/admin/backup")
    assert b"apsuite_" in page.data


def test_backup_download_blocks_traversal(client):
    make_user("root", "admin")
    login(client, "root")
    assert client.get("/admin/backup/..%2F..%2Fsecret_key.txt").status_code == 404


def test_cannot_demote_last_admin(client):
    from app.models import User
    User.query.filter_by(username="admin").delete()
    db.session.commit()
    root = make_user("root", "admin")
    login(client, "root")
    client.post(f"/admin/users/{root.id}/edit", data={"username": "root", "full_name": "Root", "role": "accountant", "is_active": "y"})
    db.session.refresh(root)
    assert root.role == "admin"


def test_email_password_stored_encrypted(client):
    from app.email_listener.config import decrypt_password
    from app.models import EmailConfig
    c = make_client()
    make_user("root", "admin")
    login(client, "root")
    client.post("/admin/email-config", data={"client_id": c.id, "imap_server": "imap.example.com", "imap_port": 993, "email_address": "a@example.com",
                                             "email_password": "s3cret-app-pass", "poll_interval_minutes": 5})
    config = EmailConfig.query.one()
    assert "s3cret" not in config.email_password_encrypted
    assert decrypt_password(config.email_password_encrypted) == "s3cret-app-pass"


def test_email_message_creates_invoice_for_tagged_client(app):
    from email.message import EmailMessage
    from app.email_listener.listener import process_message
    first, second = make_client("A", "C0001"), make_client("B", "C0002")
    vendor = make_vendor(second, name="Sharp Co", gstin=None)
    vendor.contact_email = "bills@sharp.example.com"
    db.session.commit()
    message = EmailMessage()
    message["To"] = "knowtaxxap+c0002@gmail.com"
    message["From"] = "Sharp Co <bills@sharp.example.com>"
    message["Subject"] = "Invoice attached"
    message.set_content("See attached")
    message.add_attachment((SAMPLES / "invoice_gst_1.png").read_bytes(), maintype="image", subtype="png", filename="inv.png")
    message.add_attachment(b"not allowed", maintype="application", subtype="zip", filename="payload.zip")
    assert process_message(message.as_bytes(), first) == 1
    db.session.commit()
    invoice = Invoice.query.one()
    assert invoice.client_id == second.id and invoice.source == "email"
    assert invoice.source_email_from == "bills@sharp.example.com" and invoice.vendor_id == vendor.id


class FakeImap:
    """Stands in for an IMAP server: one unread message, records what the listener marks as read."""

    def __init__(self, raw):
        self.raw, self.seen = raw, []

    def select(self, *_):
        return "OK", [b"1"]

    def search(self, *_):
        return "OK", [b"1"]

    def fetch(self, number, query):
        assert "PEEK" in query, "must not mark as read before the invoice is saved"
        return "OK", [(b"1", self.raw)]

    def store(self, number, command, flag):
        self.seen.append(number)
        return "OK", []

    def logout(self):
        return "BYE", []


def _email_config(c):
    from app.email_listener.config import encrypt_password
    from app.models import EmailConfig
    config = EmailConfig(client_id=c.id, imap_server="imap.example.com", email_address="a@example.com",
                         email_password_encrypted=encrypt_password("pw"), is_active=True)
    db.session.add(config)
    db.session.commit()
    return config


def test_poll_mailbox_ingests_then_marks_read(app, monkeypatch):
    from email.message import EmailMessage
    from app.email_listener import listener
    c = make_client()
    config = _email_config(c)
    message = EmailMessage()
    message["To"], message["From"], message["Subject"] = "a@example.com", "x@example.com", "Bill"
    message.set_content("attached")
    message.add_attachment((SAMPLES / "invoice_gst_1.png").read_bytes(), maintype="image", subtype="png", filename="inv.png")
    fake = FakeImap(message.as_bytes())
    monkeypatch.setattr(listener, "connect", lambda *a: fake)
    listener.poll_due_mailboxes()
    assert Invoice.query.one().source == "email" and fake.seen == [b"1"]
    assert config.last_error is None and config.last_poll_at is not None
    # Not due again straight away
    fake.seen.clear()
    listener.poll_due_mailboxes()
    assert fake.seen == []


def test_poll_failure_is_recorded_and_does_not_raise(app, monkeypatch):
    from app.email_listener import listener
    c = make_client()
    config = _email_config(c)

    def refuse(*_):
        raise OSError("connection refused")
    monkeypatch.setattr(listener, "connect", refuse)
    listener.poll_due_mailboxes()
    assert "connection refused" in config.last_error


def test_api_flow_and_sync_idempotent(client):
    c = make_client()
    approver = make_user("boss", "approver")
    make_rule(c, approver)
    invoice = make_invoice(c, status="pending_approval", current_approver_id=approver.id, current_level=1)
    login(client, "boss")
    assert client.get("/api/bootstrap").json["my_pending_count"] == 1
    assert len(client.get(f"/api/clients/{c.id}/invoices/pending").json["invoices"]) == 1
    assert client.get(f"/api/clients/{c.id}/dashboard").status_code == 403

    item = {"uuid": "11111111-1111-1111-1111-111111111111", "action_type": "approval", "created_at": "2026-11-01T10:00:00Z",
            "payload": {"invoice_id": invoice.id, "decision": "approve", "seen_updated_at": invoice.updated_at.isoformat()}}
    first = client.post("/api/sync", json={"device_id": "d1", "items": [item]}).json
    assert first["synced"] == 1
    db.session.refresh(invoice)
    assert invoice.status == "approved"
    # Retrying the same item must not apply it twice
    second = client.post("/api/sync", json={"device_id": "d1", "items": [item]}).json
    assert second["results"][0]["status"] == "synced" and OfflineSyncQueue.query.count() == 1


def test_sync_conflict_when_changed_while_offline(client):
    c = make_client()
    approver = make_user("boss", "approver")
    make_rule(c, approver)
    invoice = make_invoice(c, status="rejected", current_approver_id=None)
    login(client, "boss")
    item = {"uuid": "22222222-2222-2222-2222-222222222222", "action_type": "approval",
            "payload": {"invoice_id": invoice.id, "decision": "approve"}}
    result = client.post("/api/sync", json={"items": [item]}).json
    assert result["conflict"] == 1 and result["results"][0]["status"] == "conflict"
    assert OfflineSyncQueue.query.filter_by(sync_status="conflict").one().invoice_id == invoice.id
    db.session.refresh(invoice)
    assert invoice.status == "rejected"


def test_sync_image_upload_respects_client_access(client):
    import base64
    a, b = make_client("A", "C0001"), make_client("B", "C0002")
    make_user("field", "field_staff", [a])
    login(client, "field")
    image = base64.b64encode((SAMPLES / "expense_receipt_1.jpg").read_bytes()).decode()
    denied = client.post("/api/sync", json={"items": [{"uuid": "33333333-3333-3333-3333-333333333333", "action_type": "invoice_upload",
                                                       "payload": {"client_id": b.id, "image_base64": image}}]}).json
    assert denied["failed"] == 1 and Invoice.query.count() == 0
    allowed = client.post("/api/sync", json={"items": [{"uuid": "44444444-4444-4444-4444-444444444444", "action_type": "invoice_upload",
                                                        "payload": {"client_id": a.id, "image_base64": image, "filename": "r.jpg", "details": {"note": "taxi"}}}]}).json
    assert allowed["synced"] == 1
    invoice = Invoice.query.one()
    assert invoice.synced_from_offline and invoice.source == "camera" and "taxi" in invoice.notes
    stored = OfflineSyncQueue.query.filter_by(sync_status="synced").one()
    assert "image_base64" not in stored.payload


def test_pwa_files_served(client):
    assert client.get("/manifest.json").json["short_name"] == "KT AP Suite"
    worker = client.get("/service-worker.js")
    assert worker.status_code == 200 and b"ktap-v1" in worker.data
    assert b"You are offline" in client.get("/offline").data
