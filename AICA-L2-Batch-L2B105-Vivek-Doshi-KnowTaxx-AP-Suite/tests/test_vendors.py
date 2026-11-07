import io
from pathlib import Path

from conftest import login, make_client, make_user, make_vendor

from app.models import Client, Vendor, VendorDocument
from app.utils import gstin_check_digit
from app.vendors.routes import find_duplicates

PNG = (Path(__file__).parent / "sample_invoices" / "invoice_gst_1.png")


def valid_gstin_for(pan, state="27"):
    body = f"{state}{pan}1Z"
    return body + gstin_check_digit(body)


def form(**overrides):
    data = {"trade_name": "Acme Supplies", "pan": "AAFFS1111K", "category": "goods", "gstin": "", "bank_ifsc": "", "udyam_number": ""}
    data.update(overrides)
    return data


def test_create_vendor_autocode(client):
    c = make_client()
    make_user("acc", "accountant", [c])
    login(client, "acc")
    response = client.post(f"/clients/{c.id}/vendors/new", data=form())
    assert response.status_code == 302
    vendor = Vendor.query.one()
    assert vendor.code == "V0001" and vendor.status == "active" and vendor.registered_by == "internal"


def test_invalid_pan_rejected(client):
    c = make_client()
    make_user("acc", "accountant", [c])
    login(client, "acc")
    response = client.post(f"/clients/{c.id}/vendors/new", data=form(pan="BAD"))
    assert response.status_code == 200
    assert Vendor.query.count() == 0


def test_gstin_must_contain_pan(client):
    c = make_client()
    make_user("acc", "accountant", [c])
    login(client, "acc")
    response = client.post(f"/clients/{c.id}/vendors/new", data=form(gstin=valid_gstin_for("AAFFS2222K")))
    assert b"does not match" in response.data
    assert Vendor.query.count() == 0


def test_duplicate_detection_rules(app):
    c = make_client()
    existing = make_vendor(c, name="Sharma Steel Traders", pan="AAFFS1234K", gstin="27AAFFS1234K1Z5")
    assert find_duplicates(c.id, "AAFFS1234K", None, "Something Else")[0][0].id == existing.id
    assert "same GSTIN" in find_duplicates(c.id, None, "27AAFFS1234K1Z5", "Other")[0][1]
    assert "name match" in find_duplicates(c.id, None, None, "Sharma Steel Trader")[0][1]
    assert find_duplicates(c.id, "ZZZZZ9999Z", None, "Totally Different") == []


def test_duplicate_warning_then_override(client):
    c = make_client()
    make_vendor(c, name="Acme Supplies", pan="AAFFS1111K", gstin=None)
    make_user("acc", "accountant", [c])
    login(client, "acc")
    url = f"/clients/{c.id}/vendors/new"
    response = client.post(url, data=form(trade_name="Acme Supplies Co"))
    assert b"Possible duplicates" in response.data and Vendor.query.count() == 1
    response = client.post(url, data=form(trade_name="Acme Supplies Co", confirm_duplicate="y"))
    assert response.status_code == 302 and Vendor.query.count() == 2


def public_form(**overrides):
    png = PNG.read_bytes()
    data = form(contact_person="Raj", contact_email="raj@example.com", contact_phone="9999999999",
                bank_account_no="1234567890", bank_ifsc="HDFC0001234")
    data.update(doc_pan=(io.BytesIO(png), "pan.png"), doc_cheque=(io.BytesIO(png), "cheque.png"))
    data.update(overrides)
    return data


def test_public_registration_no_login_creates_pending(client):
    c = make_client()
    response = client.post(f"/vendor/register/{c.vendor_registration_token}", data=public_form(), content_type="multipart/form-data")
    assert response.status_code == 200 and b"Registration received" in response.data
    vendor = Vendor.query.one()
    assert vendor.status == "pending" and vendor.registered_by == "self"
    assert VendorDocument.query.filter_by(vendor_id=vendor.id).count() == 2


def test_public_registration_requires_documents(client):
    c = make_client()
    data = public_form()
    data.pop("doc_cheque")
    response = client.post(f"/vendor/register/{c.vendor_registration_token}", data=data, content_type="multipart/form-data")
    assert b"cancelled cheque" in response.data and Vendor.query.count() == 0


def test_public_registration_rejects_non_documents(client):
    c = make_client()
    data = public_form(doc_pan=(io.BytesIO(b"<script>alert(1)</script>"), "pan.png"))
    response = client.post(f"/vendor/register/{c.vendor_registration_token}", data=data, content_type="multipart/form-data")
    assert b"Only PDF, JPG and PNG" in response.data and Vendor.query.count() == 0


def test_public_form_never_reveals_existing_vendors(client):
    c = make_client()
    make_vendor(c, name="Secret Vendor Name", pan="AAFFS1111K", gstin=None)
    response = client.post(f"/vendor/register/{c.vendor_registration_token}", data=public_form(trade_name="Secret Vendor Nam"), content_type="multipart/form-data")
    assert b"Registration received" in response.data and b"Secret Vendor Name" not in response.data
    new = Vendor.query.filter_by(registered_by="self").one()
    assert "V0001" in new.notes


def test_bad_token_and_archived_client_404(client):
    c = make_client()
    assert client.get("/vendor/register/not-a-token").status_code == 404
    c.is_archived = True
    from app.models import db
    db.session.commit()
    assert client.get(f"/vendor/register/{Client.query.first().vendor_registration_token}").status_code == 404


def test_approve_pending_vendor(client):
    c = make_client()
    vendor = make_vendor(c, status="pending", gstin=None)
    make_user("acc", "accountant", [c])
    login(client, "acc")
    client.post(f"/clients/{c.id}/vendors/{vendor.id}/status", data={"action": "approve"})
    assert Vendor.query.one().status == "active" and Vendor.query.one().approved_at is not None


def test_blacklist_needs_reason(client):
    c = make_client()
    vendor = make_vendor(c, gstin=None)
    make_user("acc", "accountant", [c])
    login(client, "acc")
    client.post(f"/clients/{c.id}/vendors/{vendor.id}/status", data={"action": "blacklist", "reason": ""})
    assert Vendor.query.one().status == "active"
    client.post(f"/clients/{c.id}/vendors/{vendor.id}/status", data={"action": "blacklist", "reason": "Fraud"})
    assert Vendor.query.one().status == "blacklisted"


def test_vendor_of_other_client_not_reachable(client):
    a, b = make_client("A", "C0001"), make_client("B", "C0002")
    vendor = make_vendor(b, gstin=None)
    make_user("acc", "accountant", [a])
    login(client, "acc")
    assert client.get(f"/clients/{a.id}/vendors/{vendor.id}").status_code == 404
    assert client.get(f"/clients/{b.id}/vendors/{vendor.id}").status_code == 403
