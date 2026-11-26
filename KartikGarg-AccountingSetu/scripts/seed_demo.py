"""Load demo data into the LOCAL backend for evaluation.

    python -m scripts.seed_demo

Creates a platform owner, two CA firms, staff, clients, client logins, sample invoices (processed through
the real pipeline), a bank statement and approved vouchers. Demo-only passwords are listed in DEMO_ACCOUNTS
below and in README.md. Never run against production.
"""
from __future__ import annotations

import datetime as dt
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings  # noqa: E402
from services import (admin_service, auth_service, bank_service, document_service as ds, firm_service)  # noqa: E402
from services.db import get_db  # noqa: E402
from utils.validators import make_gstin  # noqa: E402

DEMO_PASSWORD = "Demo@12345"
DEMO_ACCOUNTS = {
    "Super Admin": "owner@setu.demo",
    "Firm Admin (Kapoor & Associates)": "admin@kapoorca.demo",
    "Accountant": "accountant@kapoorca.demo",
    "Reviewer / Partner": "partner@kapoorca.demo",
    "Client (Shree Ganesh Traders)": "owner@ganeshtraders.demo",
    "Second firm admin (Mehta CA)": "admin@mehtaca.demo",
}


def _pdf(lines_list: list[list[str]]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for lines in lines_list:
        y = 800
        for ln in lines:
            c.drawString(50, y, ln)
            y -= 18
        c.showPage()
    c.save()
    return buf.getvalue()


def _invoice(supplier, sgstin, customer, cgstin, no, date, item, hsn, taxable, inter=False):
    tax = taxable * 18 / 100
    lines = [supplier, "TAX INVOICE", f"GSTIN: {sgstin}", f"Invoice No: {no}", f"Invoice Date: {date:%d/%m/%Y}",
             f"Place of Supply: {cgstin[:2]}", "Reverse Charge: No", "Bill To:", customer, f"Buyer GSTIN: {cgstin}",
             "Description HSN Qty Rate Amount", f"{item} {hsn} 10 {taxable / 10:.2f} {taxable:.2f} 18%",
             f"Taxable Value: {taxable:.2f}"]
    lines += [f"IGST @ 18%: {tax:.2f}"] if inter else [f"CGST @ 9%: {tax / 2:.2f}", f"SGST @ 9%: {tax / 2:.2f}"]
    return lines + [f"Grand Total: {taxable + tax:.2f}"]


def seed(quiet: bool = False) -> None:
    if settings.backend != "local":
        raise SystemExit("Demo seed runs only on the local backend")
    db = get_db()
    if db.fetchone("select id from user_profiles where email = ?", [DEMO_ACCOUNTS["Super Admin"]]):
        if not quiet:
            print("Demo data already present.")
        return
    admin_service.ensure_default_plans()
    if not auth_service.super_admin_exists():
        auth_service.create_super_admin(DEMO_ACCOUNTS["Super Admin"], DEMO_PASSWORD, "Platform Owner")
    sa = auth_service.login(DEMO_ACCOUNTS["Super Admin"], DEMO_PASSWORD)
    fa = auth_service.register_firm(firm_name="Kapoor & Associates, Chartered Accountants", email="office@kapoorca.demo", phone="02240000000",
                                    admin_name="CA Rohit Kapoor", admin_email=DEMO_ACCOUNTS["Firm Admin (Kapoor & Associates)"],
                                    password=DEMO_PASSWORD, city="Mumbai", state_code="27", frn="123456W")
    fb = auth_service.register_firm(firm_name="Mehta CA & Co", email="office@mehtaca.demo", phone="01140000000", admin_name="CA Neha Mehta",
                                    admin_email=DEMO_ACCOUNTS["Second firm admin (Mehta CA)"], password=DEMO_PASSWORD, state_code="07")
    for f in (fa, fb):
        admin_service.set_firm_status(sa, f, "active", "Demo approval")
        admin_service.assign_plan(sa, f, "professional")
    admin = auth_service.login(DEMO_ACCOUNTS["Firm Admin (Kapoor & Associates)"], DEMO_PASSWORD)
    client_gstin = make_gstin("27", "AAKFS1234G")
    cid = firm_service.create_client(admin, {"name": "Shree Ganesh Traders", "gstin": client_gstin, "business_type": "Partnership",
                                             "email": "accounts@ganeshtraders.demo"})
    cid2 = firm_service.create_client(admin, {"name": "Sunrise Software Services LLP", "gstin": make_gstin("29", "AAXFS7777K"),
                                              "business_type": "LLP"})
    sid = auth_service.create_staff(admin, email=DEMO_ACCOUNTS["Accountant"], full_name="Priya Sharma", role="accountant",
                                    temp_password=DEMO_PASSWORD, designation="Senior Accountant")
    pid = auth_service.create_staff(admin, email=DEMO_ACCOUNTS["Reviewer / Partner"], full_name="CA Anil Desai", role="partner",
                                    temp_password=DEMO_PASSWORD, designation="Partner")
    firm_service.assign_staff(admin, cid, [sid, pid])
    auth_service.create_client_user(admin, cid, email=DEMO_ACCOUNTS["Client (Shree Ganesh Traders)"], full_name="Suresh Agarwal",
                                    temp_password=DEMO_PASSWORD)
    db.execute("update user_profiles set must_change_password = ? where email like ?", [False, "%.demo"])
    mb = auth_service.login(DEMO_ACCOUNTS["Second firm admin (Mehta CA)"], DEMO_PASSWORD)
    firm_service.create_client(mb, {"name": "Delhi Exports Pvt Ltd", "gstin": make_gstin("07", "AADCD5555H")})

    # documents for previous month, uploaded by the client and submitted
    today = dt.date.today()
    y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    d = lambda day: dt.date(y, m, day)  # noqa: E731
    client_ctx = auth_service.login(DEMO_ACCOUNTS["Client (Shree Ganesh Traders)"], DEMO_PASSWORD)
    sup1, sup2, cus1 = make_gstin("27", "AABCS1111A"), make_gstin("24", "AABCG2222B"), make_gstin("27", "AABCR3333C")
    purchases = _pdf([_invoice("Sharma Steel Suppliers Pvt Ltd", sup1, "Shree Ganesh Traders", client_gstin, "SSS/101", d(3), "MS Sheets", "7208", 50000),
                      _invoice("Gujarat Pipes Ltd", sup2, "Shree Ganesh Traders", client_gstin, "GPL-2201", d(6), "GI Pipes", "7306", 80000, inter=True)])
    sales = _pdf([_invoice("Shree Ganesh Traders", client_gstin, "Royal Builders", cus1, "SGT/045", d(10), "MS Sheets", "7208", 90000)])
    bank_csv = (f"Date,Narration,Chq/Ref No,Withdrawal Amt,Deposit Amt,Closing Balance\n"
                f"{d(12):%d/%m/%Y},NEFT-ROYAL BUILDERS-SGT/045,N0045,,106200.00,306200.00\n"
                f"{d(15):%d/%m/%Y},RTGS-SHARMA STEEL SUPPLIERS,R0101,59000.00,,247200.00\n"
                f"{d(20):%d/%m/%Y},BANK CHARGES,,354.00,,246846.00\n"
                f"{d(25):%d/%m/%Y},SALARY FOR THE MONTH,,45000.00,,201846.00\n").encode()
    sub = ds.get_or_create_submission(client_ctx, cid, y, m)
    ds.upload_document(client_ctx, cid, y, m, "purchase_bills.pdf", purchases, "purchase_invoice", sub["id"])
    ds.upload_document(client_ctx, cid, y, m, "sales_invoice_SGT045.pdf", sales, "sales_invoice", sub["id"])
    ds.upload_document(client_ctx, cid, y, m, "hdfc_statement.csv", bank_csv, "bank_statement", sub["id"])
    ds.submit_documents(client_ctx, sub["id"], "All bills for the month")
    bank_service.create_bank_account(admin, cid, "HDFC Bank", "50100099991234", "HDFC0000123")
    if not quiet:
        print("Demo data loaded. Accounts (password for all: see DEMO_PASSWORD in scripts/seed_demo.py):")
        for k, v in DEMO_ACCOUNTS.items():
            print(f"  {k:40s} {v}")


if __name__ == "__main__":
    seed()
