"""Shared fixtures: an isolated SQLite database + storage per test, two firms, staff and clients."""
from __future__ import annotations

import datetime as dt
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import os  # noqa: E402

# Tests must NEVER touch a live project: force the local backend regardless of .env.
os.environ["DATA_BACKEND"] = "local"
from config import settings as _settings  # noqa: E402

_settings.backend = "local"
_settings.anthropic_api_key = ""

from services import ai_service, auth_service, admin_service, firm_service, ocr_service  # noqa: E402
from services.db import SQLiteDatabase, set_db  # noqa: E402
from services.storage_service import LocalStorage, set_storage  # noqa: E402
from utils.validators import make_gstin  # noqa: E402

PW = "Passw0rd!x"
CLIENT_A1_GSTIN = make_gstin("27", "AAACA1111A")   # Maharashtra
CLIENT_A2_GSTIN = make_gstin("29", "AAACA2222B")   # Karnataka
CLIENT_B1_GSTIN = make_gstin("07", "AAACB3333C")   # Delhi
SUPPLIER_MH = make_gstin("27", "BBBCS4444D")
SUPPLIER_KA = make_gstin("29", "BBBCS5555E")
CUSTOMER_MH = make_gstin("27", "CCCCC6666F")
CUSTOMER_DL = make_gstin("07", "CCCCC7777G")


@pytest.fixture()
def env(tmp_path):
    db = SQLiteDatabase(tmp_path / "test.db")
    db.migrate()
    set_db(db)
    set_storage(LocalStorage(tmp_path / "storage"))
    ocr_service.set_ocr(ocr_service.OCRProvider())          # no OCR engine
    ai_service.set_provider(ai_service.LocalRulesProvider())  # deterministic extraction
    admin_service.ensure_default_plans()

    auth_service.create_super_admin("owner@platform.test", PW, "Owner")
    sa = auth_service.login("owner@platform.test", PW)

    fa = auth_service.register_firm(firm_name="Alpha & Co", email="alpha@firm.test", phone="1", admin_name="Alpha Admin",
                                    admin_email="admin@alpha.test", password=PW, state_code="27")
    fb = auth_service.register_firm(firm_name="Beta Associates", email="beta@firm.test", phone="2", admin_name="Beta Admin",
                                    admin_email="admin@beta.test", password=PW, state_code="07")
    admin_service.set_firm_status(sa, fa, "active")
    admin_service.set_firm_status(sa, fb, "active")
    admin_service.assign_plan(sa, fa, "professional")
    admin_service.assign_plan(sa, fb, "professional")
    a_admin = auth_service.login("admin@alpha.test", PW)
    b_admin = auth_service.login("admin@beta.test", PW)

    c_a1 = firm_service.create_client(a_admin, {"name": "Client A1 Traders", "gstin": CLIENT_A1_GSTIN})
    c_a2 = firm_service.create_client(a_admin, {"name": "Client A2 Services", "gstin": CLIENT_A2_GSTIN})
    c_b1 = firm_service.create_client(b_admin, {"name": "Client B1 Exports", "gstin": CLIENT_B1_GSTIN})

    auth_service.create_staff(a_admin, email="acct@alpha.test", full_name="Accountant A", role="accountant", temp_password=PW)
    auth_service.create_staff(a_admin, email="rev@alpha.test", full_name="Reviewer A", role="reviewer", temp_password=PW)
    auth_service.create_staff(a_admin, email="ro@alpha.test", full_name="ReadOnly A", role="read_only", temp_password=PW)
    acct = auth_service.login("acct@alpha.test", PW)
    rev = auth_service.login("rev@alpha.test", PW)
    firm_service.assign_staff(a_admin, c_a1, [acct.staff_id, rev.staff_id])

    auth_service.create_client_user(a_admin, c_a1, email="owner@clienta1.test", full_name="A1 Owner", temp_password=PW)
    auth_service.create_client_user(a_admin, c_a2, email="owner@clienta2.test", full_name="A2 Owner", temp_password=PW)
    auth_service.create_client_user(b_admin, c_b1, email="owner@clientb1.test", full_name="B1 Owner", temp_password=PW)

    class E:
        pass

    e = E()
    e.db, e.sa, e.firm_a, e.firm_b = db, sa, fa, fb
    e.a_admin, e.b_admin, e.acct, e.rev = a_admin, b_admin, acct, rev
    e.ro = auth_service.login("ro@alpha.test", PW)
    e.c_a1, e.c_a2, e.c_b1 = c_a1, c_a2, c_b1
    e.cu_a1 = auth_service.login("owner@clienta1.test", PW)
    e.cu_a2 = auth_service.login("owner@clienta2.test", PW)
    e.cu_b1 = auth_service.login("owner@clientb1.test", PW)
    yield e


# ------------------------------------------------------------------ document builders
def invoice_text(inv: dict) -> list[str]:
    lines = [inv.get("supplier_name", "Sharma Steel Suppliers Pvt Ltd"), "TAX INVOICE",
             f"GSTIN: {inv['supplier_gstin']}",
             f"Invoice No: {inv['invoice_no']}", f"Invoice Date: {inv['date']}",
             f"Place of Supply: {inv.get('pos', '27-Maharashtra')}", f"Reverse Charge: {inv.get('rcm', 'No')}",
             "Bill To:", inv.get("customer_name", "Client A1 Traders"), f"Buyer GSTIN: {inv['customer_gstin']}",
             "Description HSN Qty Rate Amount",
             f"{inv.get('item', 'MS Steel Sheets')} {inv.get('hsn', '7208')} 10 {inv['taxable'] / 10:.2f} {inv['taxable']:.2f}",
             f"Taxable Value: {inv['taxable']:.2f}"]
    if inv.get("igst"):
        lines.append(f"IGST @ 18%: {inv['igst']:.2f}")
    else:
        lines += [f"CGST @ 9%: {inv.get('cgst', 0):.2f}", f"SGST @ 9%: {inv.get('sgst', 0):.2f}"]
    if inv.get("round_off"):
        lines.append(f"Round Off: {inv['round_off']:.2f}")
    lines.append(f"Grand Total: {inv['total']:.2f}")
    return lines


def make_pdf(invoices: list[dict], blank_pages: int = 0) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for inv in invoices:
        y = 800
        for ln in invoice_text(inv):
            c.drawString(50, y, ln)
            y -= 18
        c.showPage()
    for _ in range(blank_pages):
        c.rect(50, 50, 200, 200, fill=1)
        c.showPage()
    c.save()
    return buf.getvalue()


def make_png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(buf, "PNG")
    return buf.getvalue()


def purchase(no="PI-1001", taxable=10000, date=None, supplier=SUPPLIER_MH, customer=CLIENT_A1_GSTIN, interstate=False):
    date = date or dt.date.today().replace(day=1)
    tax = taxable * 18 / 100
    inv = {"invoice_no": no, "date": date.strftime("%d/%m/%Y"), "supplier_gstin": supplier, "customer_gstin": customer,
           "taxable": float(taxable), "total": float(taxable + tax)}
    if interstate:
        inv["igst"] = float(tax)
        inv["pos"] = "27-Maharashtra"
    else:
        inv["cgst"] = inv["sgst"] = float(tax / 2)
    return inv
