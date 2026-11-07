"""Populate demo data for the capstone presentation. All businesses and numbers are fictional.

Run:   python scripts/seed_demo_data.py          (refuses if demo clients already exist)
       python scripts/seed_demo_data.py --reset  (ERASES every record first)
"""
import argparse
import json
import os
import random
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

os.environ["KTAP_NO_LISTENER"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.models import (SPEND_STATUSES, ApprovalLog, ApprovalMatrix, AuditLog, Budget, Client, CostCentre,  # noqa: E402
                        Invoice, InvoiceLineItem, User, Vendor, db, utcnow)
from app.utils import gstin_check_digit  # noqa: E402

DEMO_PASSWORD = "Demo@1234"
rng = random.Random(2026)


def make_gstin(state, pan):
    body = f"{state}{pan}1Z"
    return body + gstin_check_digit(body)


USERS = [
    ("accountant1", "Priya Kulkarni", "accountant", ["C0001", "C0002"]),
    ("accountant2", "Rahul Mehta", "accountant", ["C0002", "C0003"]),
    ("approver1", "Anita Deshpande", "approver", []),
    ("field1", "Sandeep Patil", "field_staff", ["C0001", "C0002", "C0003"]),
]

CLIENTS = [
    ("ABC Manufacturing Pvt Ltd", "company", "AABCA1234C", "27", "Plot 14, MIDC Bhosari, Pune 411026", "Meena Joshi", "U28100MH2012PTC123456", None),
    ("XYZ Trading LLP", "llp", "AAAFX5678D", "24", "305 Ashram Road, Ahmedabad 380009", "Karan Shah", None, "AAB-1234"),
    ("PQR Professional Services", "firm", "AAAFP9012E", "29", "88 Residency Road, Bengaluru 560025", "Lakshmi Rao", None, None),
]

# trade name, PAN, state, category, MSME, expense category, GL ledger, description, HSN/SAC, GST rate, TDS section, TDS rate
VENDORS = {
    "C0001": [
        ("Sharma Steel Traders", "AAFFS1234K", "27", "goods", True, "Raw Materials", "Raw Material Purchases", "MS steel sheets", "7208", 18, None, None),
        ("Mahalaxmi Packaging Industries", "AAIFM7890R", "27", "goods", True, "Raw Materials", "Packing Material", "Corrugated boxes", "4819", 12, None, None),
        ("Sunrise Estates", "AAKFS4411T", "27", "services", False, "Rent", "Rent - Factory", "Monthly factory rent", "997212", 18, "194I", 10),
        ("Greenfield Facility Services", "AAGCG9012P", "27", "contractor", False, "Contractor Services", "Housekeeping Charges", "Housekeeping and security", "998533", 18, "194C", 2),
        ("Patel Consultancy Services", "AACFP5678M", "24", "professional", False, "Professional Fees", "Professional Fees", "GST advisory retainer", "998231", 18, "194J", 10),
    ],
    "C0002": [
        ("Gujarat Freight Carriers", "AAGFG2201L", "24", "services", True, "Freight & Logistics", "Freight Outward", "Road freight", "996511", 12, "194C", 2),
        ("Nexa Cloud Technologies", "AAHCN3456Q", "29", "services", False, "IT & Software", "Software Subscriptions", "ERP subscription", "997331", 18, None, None),
        ("Rajhans Office Mart", "AARFR7719B", "24", "goods", True, "Office Supplies", "Printing & Stationery", "Stationery and toner", "4820", 12, None, None),
        ("Adwise Media Solutions", "AAECA6612H", "24", "services", False, "Marketing", "Advertisement", "Digital campaign", "998361", 18, None, None),
        ("Torrent Energy Distribution", "AABCT4471F", "24", "services", False, "Utilities", "Electricity Charges", "Electricity bill", "998631", 18, None, None),
    ],
    "C0003": [
        ("Skyline Business Centre", "AAECS8821J", "29", "services", False, "Rent", "Rent - Office", "Office rent", "997212", 18, "194I", 10),
        ("Airlink Broadband Pvt Ltd", "AADCA5503N", "29", "services", False, "Telecom & Internet", "Internet Charges", "Leased line", "998422", 18, None, None),
        ("Bharat Travels", "AAPFB3390C", "29", "services", True, "Travel & Conveyance", "Travel Expenses", "Air tickets and cabs", "998551", 5, None, None),
        ("LexCounsel Associates", "AAEFL1178G", "27", "professional", False, "Professional Fees", "Legal Fees", "Legal retainer", "998212", 18, "194J", 10),
        ("TechServe Hardware Solutions", "AAFCT9045D", "29", "goods", True, "IT & Software", "Computer Maintenance", "Laptop repairs and AMC", "998713", 18, None, None),
    ],
}

COST_CENTRES = {"C0001": ("Administration", "Sales", "Manufacturing", "R&D"),
                "C0002": ("Administration", "Sales", "Operations", "R&D"),
                "C0003": ("Administration", "Sales", "Operations", "R&D")}
BUDGET_BY_CENTRE = {"C0001": (90000, 80000, 400000, 60000), "C0002": (70000, 120000, 150000, 30000), "C0003": (150000, 60000, 90000, 25000)}
# status mix: paid and approved dominate older months; the current month is still in progress
OLD_STATUSES = ["paid", "paid", "paid", "approved", "approved", "approved", "pending_approval", "rejected", "reviewed"]
NEW_STATUSES = ["approved", "approved", "pending_approval", "pending_approval", "pending_approval", "pending_review", "auto_captured", "reviewed"]


def month_shift(day, months_back):
    year, month = day.year, day.month - months_back
    while month < 1:
        year, month = year - 1, month + 12
    return year, month


def random_day(year, month, today):
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    latest = today.day if (year, month) == (today.year, today.month) else last
    return date(year, month, rng.randint(1, max(latest, 1)))


def reset_database():
    db.drop_all()
    db.create_all()


def create_users():
    admin = User.query.filter_by(username="admin").first()
    if admin is None:
        admin = User(username="admin", full_name="System Administrator", role="admin")
        db.session.add(admin)
    admin.set_password("Admin@123")
    admin.must_change_password = False
    admin.email = "admin@example.com"
    users = {"admin": admin}
    for username, name, role, _ in USERS:
        user = User(username=username, full_name=name, role=role, must_change_password=False, email=f"{username}@example.com")
        user.set_password(DEMO_PASSWORD)
        db.session.add(user)
        users[username] = user
    db.session.flush()
    return users


def create_invoice(client, vendor_row, vendor, centres, users, status, day, index):
    (_, _, _, _, msme, category, ledger, description, hsn, rate, tds_section, tds_rate) = vendor_row
    today = date.today()
    taxable = Decimal(rng.randrange(4000, 150000, 500))
    interstate = vendor.gstin[:2] != client.gstin[:2]
    tax = (taxable * rate / 100).quantize(Decimal("0.01"))
    cgst = sgst = None
    igst = None
    if interstate:
        igst = tax
    else:
        cgst = (tax / 2).quantize(Decimal("0.01"))
        sgst = tax - cgst
    total = taxable + tax
    number = f"{vendor.code}/{day.strftime('%y%m')}/{index:03d}"
    centre = centres[{"Raw Materials": 2, "Rent": 0, "Marketing": 1, "Freight & Logistics": 1, "IT & Software": 3}.get(category, rng.randrange(4))]
    confidence = round(rng.uniform(0.62, 0.98), 2)
    terms = 45 if msme else rng.choice((15, 30))
    fields = dict(vendor_name=vendor.trade_name, gstin=vendor.gstin)

    invoice = Invoice(
        client_id=client.id, vendor_id=vendor.id, invoice_number=number, invoice_date=day, due_date=day + timedelta(days=terms),
        source=rng.choice(("upload", "upload", "email", "camera")), ocr_vendor_name=fields["vendor_name"], ocr_gstin=fields["gstin"],
        ocr_invoice_number=number, ocr_invoice_date=day, ocr_total_amount=total, ocr_taxable_amount=taxable, ocr_cgst=cgst, ocr_sgst=sgst, ocr_igst=igst,
        ocr_tds_applicable=bool(tds_section), ocr_tds_section=tds_section, ocr_tds_rate=tds_rate, ocr_confidence_score=confidence,
        ocr_raw_text="(Demo record: created by seed script, no source document.)",
        ocr_field_confidence=json.dumps({k: confidence for k in ("vendor_name", "gstin", "invoice_number", "invoice_date", "total_amount", "taxable_amount", "cgst", "sgst", "igst")}),
        ocr_warnings="[]", expense_category=category, final_hsn_sac=hsn, status=status, uploaded_by=users["field1"].id,
    )
    invoice.created_at = datetime.combine(day, datetime.min.time()) + timedelta(hours=5)
    db.session.add(invoice)
    db.session.flush()
    db.session.add(InvoiceLineItem(invoice_id=invoice.id, description=description, hsn_sac=hsn, quantity=Decimal(1), unit_price=taxable, taxable_amount=taxable, total_amount=total))

    if status in ("auto_captured", "pending_review"):
        return invoice

    reviewer = users["accountant1"] if client.code in ("C0001",) else users["accountant2"]
    invoice.final_vendor_name, invoice.final_gstin, invoice.final_invoice_number, invoice.final_invoice_date = vendor.trade_name, vendor.gstin, number, day
    invoice.final_total_amount, invoice.final_taxable_amount, invoice.final_cgst, invoice.final_sgst, invoice.final_igst = total, taxable, cgst, sgst, igst
    invoice.final_tds_section, invoice.final_tds_rate, invoice.final_description = tds_section, tds_rate, description
    invoice.cost_centre_id, invoice.gl_account = centre.id, ledger
    invoice.narration = f"Being {description.lower()} from {vendor.trade_name}, invoice {number}"
    invoice.reviewed_by = reviewer.id
    submitted = min(invoice.created_at + timedelta(hours=rng.randint(2, 30)), utcnow() - timedelta(hours=rng.randint(1, 6)))
    invoice.reviewed_at = submitted
    if status == "reviewed":
        return invoice

    invoice.submitted_at = invoice.level_entered_at = submitted
    invoice.current_level = 1
    db.session.add(ApprovalLog(invoice_id=invoice.id, action="submitted", actor_id=reviewer.id, actor_role=reviewer.role, acted_at=submitted))
    needs_level_two = total > 100000
    approver = users["approver1"]

    if status == "pending_approval":
        invoice.current_approver_id = approver.id
        # Spread the waiting time so the SLA figures have something to show
        invoice.submitted_at = invoice.level_entered_at = utcnow() - timedelta(hours=rng.choice((3, 10, 30, 52, 80)))
        return invoice

    decided = min(submitted + timedelta(hours=rng.randint(3, 40)), utcnow() - timedelta(minutes=30))
    if status == "rejected":
        invoice.rejected_by, invoice.rejected_at = approver.id, decided
        invoice.rejection_reason = "Purchase order not matched. Please confirm the rate with the department."
        db.session.add(ApprovalLog(invoice_id=invoice.id, action="rejected", actor_id=approver.id, actor_role=approver.role, level=1, comments=invoice.rejection_reason, acted_at=decided))
        return invoice

    db.session.add(ApprovalLog(invoice_id=invoice.id, action="approved", actor_id=approver.id, actor_role=approver.role, level=1, acted_at=decided))
    final_approver = approver
    if needs_level_two:
        final_approver = users["admin"]
        decided = min(decided + timedelta(hours=rng.randint(2, 24)), utcnow() - timedelta(minutes=10))
        invoice.current_level = 2
        db.session.add(ApprovalLog(invoice_id=invoice.id, action="approved", actor_id=final_approver.id, actor_role=final_approver.role, level=2, acted_at=decided))
    invoice.approved_by, invoice.approved_at = final_approver.id, decided

    if status == "paid":
        invoice.payment_date = min(day + timedelta(days=rng.randint(7, terms)), today)
        invoice.payment_reference = f"UTR{rng.randint(10**11, 10**12 - 1)}"
    return invoice


def seed_client(index, row, users):
    name, entity, pan, state, address, contact, cin, llpin = row
    code = f"C{index:04d}"
    client = Client(code=code, name=name, entity_type=entity, pan=pan, gstin=make_gstin(state, pan), cin=cin, llpin=llpin, address=address,
                    contact_person=contact, contact_email=f"accounts@{code.lower()}.example.com", contact_phone=f"98{index:02d}0012{index:02d}", email_alias=code.lower())
    db.session.add(client)
    db.session.flush()
    db.session.add(AuditLog(user_id=users["admin"].id, action="create", entity_type="client", entity_id=client.id, details=json.dumps({"seed": True, "code": code}), timestamp=utcnow()))

    centres = []
    for position, centre_name in enumerate(COST_CENTRES[code], 1):
        centre = CostCentre(client_id=client.id, code=f"CC{position:02d}", name=centre_name)
        db.session.add(centre)
        centres.append(centre)
    db.session.flush()

    vendors = []
    for position, vendor_row in enumerate(VENDORS[code], 1):
        v_name, v_pan, v_state, category, msme = vendor_row[:5]
        vendor = Vendor(client_id=client.id, code=f"V{position:04d}", trade_name=v_name, legal_name=v_name, pan=v_pan, gstin=make_gstin(v_state, v_pan),
                        msme_registered=msme, udyam_number=f"UDYAM-{ {'27': 'MH', '24': 'GJ', '29': 'KR'}[v_state] }-{position + 10:02d}-{1000000 + position * 137:07d}" if msme else None,
                        bank_account_no=f"00{index}{position}1234567{position}", bank_ifsc="HDFC0001234", bank_branch="HDFC Bank, Main Branch",
                        contact_person="Accounts Desk", contact_email=f"accounts@{v_name.split()[0].lower()}.example.com", contact_phone=f"99{index}{position}001122",
                        category=category, status="active", registered_by="internal", approved_by=users["admin"].id, approved_at=utcnow())
        db.session.add(vendor)
        vendors.append(vendor)
    db.session.flush()

    # One self-registered vendor awaiting verification, so the demo shows that queue
    pending_pan = {"C0001": "AAPFN1122A", "C0002": "AAPFO3344B", "C0003": "AAPFQ5566C"}[code]
    db.session.add(Vendor(client_id=client.id, code="V0006", trade_name=f"Navkar Enterprises {index}", pan=pending_pan, gstin=make_gstin(state, pending_pan),
                          category="goods", status="pending", registered_by="self", bank_account_no="55667788990", bank_ifsc="ICIC0004321",
                          contact_person="Navkar Accounts", contact_email="navkar@example.com", contact_phone="9000011111"))

    today = date.today()
    this_year, this_month = today.year, today.month
    last_year, last_month = month_shift(today, 1)
    count = rng.randint(15, 20)
    for number in range(1, count + 1):
        recent = number % 2 == 0
        year, month = (this_year, this_month) if recent else (last_year, last_month)
        position = rng.randrange(5)
        status = rng.choice(NEW_STATUSES if recent else OLD_STATUSES)
        day = random_day(year, month, today)
        create_invoice(client, VENDORS[code][position], vendors[position], centres, users, status, day, number)
    db.session.flush()

    # Budgets set around actual spend, so the variance report shows a realistic green/amber/red mix.
    # Budget = actual / (1 + planned overspend). A centre with no spend gets its default figure.
    overspend = (0.22, 0.03, 0.10, -0.15)
    for centre, default, planned in zip(centres, BUDGET_BY_CENTRE[code], overspend):
        for year, month in ((last_year, last_month), (this_year, this_month)):
            first = date(year, month, 1)
            last = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
            actual = sum(float(i.final_taxable_amount or 0) for i in Invoice.query.filter(
                Invoice.cost_centre_id == centre.id, Invoice.status.in_(SPEND_STATUSES), Invoice.final_invoice_date >= first, Invoice.final_invoice_date <= last))
            amount = round(actual / (1 + planned), -3) if actual else default
            db.session.add(Budget(client_id=client.id, cost_centre_id=centre.id, period_year=year, period_month=month,
                                  budget_amount=Decimal(str(amount)), notes="Demo budget"))

    rules = [(0, 50000, users["approver1"], 1), (50000.01, 100000, users["approver1"], 1), (100000.01, None, users["approver1"], 1), (100000.01, None, users["admin"], 2)]
    for low, high, approver, level in rules:
        db.session.add(ApprovalMatrix(client_id=client.id, min_amount=Decimal(str(low)), max_amount=Decimal(str(high)) if high else None,
                                      approver_id=approver.id, approval_level=level))
    return client, count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="ERASE every record first")
    args = parser.parse_args()
    app = create_app({"EMAIL_LISTENER_ENABLED": False})
    with app.app_context():
        if args.reset:
            reset_database()
        elif Client.query.filter_by(code="C0001").first():
            print("Demo data already exists. Use --reset to erase everything and start again.")
            return
        users = create_users()
        total = 0
        clients = {}
        for index, row in enumerate(CLIENTS, 1):
            client, count = seed_client(index, row, users)
            clients[client.code] = client
            total += count
        for username, _, _, codes in USERS:
            users[username].clients = [clients[c] for c in codes]
        db.session.add(AuditLog(user_id=users["admin"].id, action="create", entity_type="seed", details=json.dumps({"invoices": total}), timestamp=utcnow()))
        db.session.commit()
        print(f"Seeded {len(clients)} clients, {total} invoices. Sign in with the demo users listed in the README.")


if __name__ == "__main__":
    main()
