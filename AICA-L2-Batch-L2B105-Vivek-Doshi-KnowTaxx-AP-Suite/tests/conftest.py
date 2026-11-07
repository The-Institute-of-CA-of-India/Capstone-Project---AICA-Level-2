import os
import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest

os.environ["KTAP_NO_LISTENER"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.models import ApprovalMatrix, Client, CostCentre, Invoice, User, Vendor, db  # noqa: E402

PASSWORD = "Testpass123"


@pytest.fixture
def app(tmp_path):
    application = create_app({
        "TESTING": True, "EMAIL_LISTENER_ENABLED": False, "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp_path / "test.db").as_posix(),
        "FILES_ROOT": str(tmp_path / "files"), "BACKUP_ROOT": str(tmp_path / "backups"),
    })
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def make_user(username, role, clients=()):
    user = User(username=username, full_name=username.title(), role=role, must_change_password=False)
    user.set_password(PASSWORD)
    user.clients = list(clients)
    db.session.add(user)
    db.session.commit()
    return user


def login(http, username, password=PASSWORD):
    return http.post("/auth/login", data={"username": username, "password": password})


def make_client(name="Acme Ltd", code="C0001"):
    record = Client(code=code, name=name, email_alias=code.lower(), gstin=None)
    db.session.add(record)
    db.session.commit()
    return record


def make_vendor(client_record, name="Vendor One", pan="AAAPL1234C", gstin="27AAAPL1234C1Z5", status="active", code="V0001"):
    vendor = Vendor(client_id=client_record.id, code=code, trade_name=name, pan=pan, gstin=gstin, status=status)
    db.session.add(vendor)
    db.session.commit()
    return vendor


def make_rule(client_record, approver, low=0, high=None, level=1, category=None, centre=None):
    rule = ApprovalMatrix(client_id=client_record.id, min_amount=Decimal(str(low)), max_amount=Decimal(str(high)) if high is not None else None,
                          approver_id=approver.id, approval_level=level, expense_category=category,
                          cost_centre_id=centre.id if centre else None)
    db.session.add(rule)
    db.session.commit()
    return rule


def make_invoice(client_record, total="11800", status="reviewed", **kwargs):
    defaults = dict(client_id=client_record.id, status=status, final_vendor_name="Vendor One", final_invoice_number="INV-1",
                    final_total_amount=Decimal(total), final_taxable_amount=Decimal(total), invoice_number="INV-1")
    defaults.update(kwargs)
    invoice = Invoice(**defaults)
    db.session.add(invoice)
    db.session.commit()
    return invoice


def make_centre(client_record, code="CC01", name="Admin"):
    centre = CostCentre(client_id=client_record.id, code=code, name=name)
    db.session.add(centre)
    db.session.commit()
    return centre


def ok_page(response):
    return response.status_code == 200 and not re.search(rb"Traceback", response.data)
