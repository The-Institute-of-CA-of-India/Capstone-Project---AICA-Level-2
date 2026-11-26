"""Generate and upload a realistic October document set for client 'Royal Traders' (Sharma & Associates).

    python -m scripts.generate_october_demo

Creates 50 sales invoice PDFs, 15 purchase invoice PDFs, 1 bank statement PDF and 1 electricity-bill PDF,
saves them to scripts/_generated_october/, uploads them to the client's October submission (as the client
user), and submits the batch — which triggers the firm's normal auto-process-on-submit pipeline.

Runs against whatever DATA_BACKEND is set in .env (local or live Supabase) — uses the real app code paths.
"""
from __future__ import annotations

import datetime as dt
import io
import random
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reportlab.pdfgen import canvas  # noqa: E402

from config import settings  # noqa: E402
from services import auth_service, document_service as ds  # noqa: E402
from services.db import get_db  # noqa: E402
from utils.validators import make_gstin  # noqa: E402

YEAR, MONTH = 2026, 10
CLIENT_NAME = "Royal Traders"
CLIENT_GSTIN = "27ABCPT1234D1Z0"
CLIENT_EMAIL = "royal.traders.test@gmail.com"
CLIENT_PASSWORD = "Setu-Reset1"
OUT_DIR = Path(__file__).with_name("_generated_october")

MH_CUSTOMERS = ["Rohan Enterprises", "Mehta Retail Stores", "Patil Hardware Mart", "Sunrise General Stores",
                "Kapoor Traders", "Verma Electronics", "Deshmukh & Sons", "Aggarwal Textiles", "Joshi Stationery",
                "Walk-in Customer"]
MH_SUPPLIERS = [("Sharma Steel Suppliers Pvt Ltd", "AABCS1111A"), ("Patel Hardware Distributors", "AABCP2222B"),
                ("Mumbai Packaging Co", "AABCM3333C"), ("Shree Balaji Traders", "AABCB4444D"),
                ("National Stationery Supplies", "AABCN5555E")]
ITEMS = [("General Merchandise", "4819"), ("Hardware Fittings", "8302"), ("Electrical Goods", "8536"),
         ("Office Stationery", "4820"), ("Packaging Material", "3923"), ("Steel Items", "7308")]


def _pdf(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for ln in lines:
        c.drawString(50, y, ln)
        y -= 18
    c.save()
    return buf.getvalue()


def _invoice_pdf(*, supplier_name, supplier_gstin, customer_name, customer_gstin, invoice_no, date, taxable,
                 interstate=False, pos="27") -> bytes:
    item_desc, hsn = random.choice(ITEMS)
    qty = random.choice([1, 2, 5, 10])
    rate = (taxable / qty).quantize(Decimal("0.01"))
    tax = (taxable * Decimal("18") / 100).quantize(Decimal("0.01"))
    lines = [supplier_name, "TAX INVOICE", f"GSTIN: {supplier_gstin}", f"Invoice No: {invoice_no}",
             f"Invoice Date: {date:%d/%m/%Y}", f"Place of Supply: {pos}", "Reverse Charge: No", "Bill To:",
             customer_name]
    if customer_gstin:
        lines.append(f"Buyer GSTIN: {customer_gstin}")
    lines += [f"Description HSN Qty Rate Amount GST%", f"{item_desc} {hsn} {qty} {rate} {taxable:.2f} 18%",
              f"Taxable Value: {taxable:.2f}"]
    if interstate:
        lines.append(f"IGST @ 18%: {tax:.2f}")
        total = taxable + tax
    else:
        half = (tax / 2).quantize(Decimal("0.01"))
        lines += [f"CGST @ 9%: {half:.2f}", f"SGST @ 9%: {half:.2f}"]
        total = taxable + 2 * half
    lines.append(f"Grand Total: {total:.2f}")
    return _pdf(lines), total


def _electricity_bill_pdf(date: dt.date, amount: Decimal) -> bytes:
    gstin = make_gstin("27", "AAACM1234E")
    lines = ["Maharashtra State Electricity Distribution Co. Ltd.", "ELECTRICITY BILL", f"GSTIN: {gstin}",
             f"Invoice No: MSEDCL/{date:%Y%m}/88213", f"Invoice Date: {date:%d/%m/%Y}", "Place of Supply: 27",
             "Bill To:", CLIENT_NAME, f"Buyer GSTIN: {CLIENT_GSTIN}", "Description HSN Qty Rate Amount GST%",
             f"Electricity Charges 9969 1 {amount:.2f} {amount:.2f} 18%", f"Taxable Value: {amount:.2f}"]
    tax = (amount * Decimal("18") / 100).quantize(Decimal("0.01"))
    half = (tax / 2).quantize(Decimal("0.01"))
    lines += [f"CGST @ 9%: {half:.2f}", f"SGST @ 9%: {half:.2f}", f"Grand Total: {(amount + 2 * half):.2f}"]
    return _pdf(lines), amount + 2 * half


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    random.seed(42)

    sales, purchases = [], []
    day_cycle = list(range(1, 29)) * 3
    random.shuffle(day_cycle)

    for i in range(1, 51):
        day = day_cycle[i - 1]
        date = dt.date(YEAR, MONTH, day)
        taxable = Decimal(random.choice([1500, 2200, 3500, 4800, 6200, 8900, 12000, 15500, 22000, 35000, 48000, 65000]))
        b2b = i % 5 == 0  # 1 in 5 sales invoices is a registered B2B customer
        customer = random.choice(MH_CUSTOMERS[:-1]) if b2b else random.choice(MH_CUSTOMERS)
        customer_gstin = make_gstin("27", f"AABC{chr(65 + i % 26)}{i:04d}"[:10].ljust(10, "X")) if b2b else None
        pdf, total = _invoice_pdf(supplier_name=CLIENT_NAME, supplier_gstin=CLIENT_GSTIN, customer_name=customer,
                                  customer_gstin=customer_gstin, invoice_no=f"RT/{YEAR}/{i:04d}", date=date, taxable=taxable)
        fname = f"Sales_RT-{YEAR}-{i:04d}.pdf"
        (OUT_DIR / fname).write_bytes(pdf)
        sales.append((fname, pdf, date, customer, total))

    for i in range(1, 16):
        day = day_cycle[49 + i - 1] if 49 + i - 1 < len(day_cycle) else random.randint(1, 28)
        date = dt.date(YEAR, MONTH, day)
        supplier, pan_body = random.choice(MH_SUPPLIERS)
        supplier_gstin = make_gstin("27", pan_body)
        taxable = Decimal(random.choice([3000, 5500, 8200, 11000, 16500, 24000, 32000, 45000, 58000]))
        pdf, total = _invoice_pdf(supplier_name=supplier, supplier_gstin=supplier_gstin, customer_name=CLIENT_NAME,
                                  customer_gstin=CLIENT_GSTIN, invoice_no=f"{supplier[:3].upper()}/{YEAR}{MONTH:02d}/{i:03d}",
                                  date=date, taxable=taxable)
        fname = f"Purchase_{i:02d}_{supplier.split()[0]}.pdf"
        (OUT_DIR / fname).write_bytes(pdf)
        purchases.append((fname, pdf, date, supplier, total))

    elec_date = dt.date(YEAR, MONTH, 20)
    elec_amount = Decimal("8400.00")
    elec_pdf, elec_total = _electricity_bill_pdf(elec_date, elec_amount)
    (OUT_DIR / "Electricity_Bill_Oct.pdf").write_bytes(elec_pdf)

    # ---------------- bank statement (matches a handful of the sales/purchases above + routine entries) ----------------
    bal = Decimal("150000.00")
    stmt_lines = [f"Opening Balance: {bal:.2f}"]
    txns = []
    for fname, _, date, customer, total in sales[:12]:
        bal += total
        txns.append((date, f"NEFT-{customer.upper().replace(' ', '')}-{fname.split('.')[0]}", total, bal))
    for fname, _, date, supplier, total in purchases[:6]:
        bal -= total
        txns.append((date, f"RTGS-{supplier.upper().replace(' ', '')[:20]}", -total, bal))
    bal -= elec_total
    txns.append((elec_date, "MSEDCL ELECTRICITY BILL PAYMENT", -elec_total, bal))
    bal -= Decimal("354.00")
    txns.append((dt.date(YEAR, MONTH, 5), "BANK CHARGES QTR", -Decimal("354.00"), bal))
    bal -= Decimal("22000.00")
    txns.append((dt.date(YEAR, MONTH, 28), "SALARY FOR THE MONTH", -Decimal("22000.00"), bal))
    txns.sort(key=lambda t: t[0])
    for date, narr, amt, running in txns:
        stmt_lines.append(f"{date:%d/%m/%Y} {narr} {abs(amt):.2f} {running:.2f}")
    bank_pdf = _pdf(stmt_lines)
    (OUT_DIR / "Bank_Statement_Oct.pdf").write_bytes(bank_pdf)

    print(f"Generated {len(sales)} sales + {len(purchases)} purchase invoices + 1 electricity bill + "
          f"1 bank statement in {OUT_DIR}")

    # ---------------- upload into the running app (as the client), then submit the batch ----------------
    # Build the client's context directly by user id (no password needed) — the test password may have
    # already been changed by hand in the browser; this is the same internal call the app itself uses once
    # a session is known, not a login bypass exposed anywhere in the UI.
    row = get_db().fetchone("select id from user_profiles where email = ?", [CLIENT_EMAIL])
    if not row:
        raise SystemExit(f"No account found for {CLIENT_EMAIL} — has the client finished registering?")
    ctx = auth_service.build_context(row["id"])
    auth_service.activate_request_identity(ctx)
    client_id = ctx.client_id
    sub = ds.get_or_create_submission(ctx, client_id, YEAR, MONTH)
    for fname, pdf, *_ in sales:
        ds.upload_document(ctx, client_id, YEAR, MONTH, fname, pdf, "sales_invoice", submission_id=sub["id"])
    for fname, pdf, *_ in purchases:
        ds.upload_document(ctx, client_id, YEAR, MONTH, fname, pdf, "purchase_invoice", submission_id=sub["id"])
    ds.upload_document(ctx, client_id, YEAR, MONTH, "Bank_Statement_Oct.pdf", bank_pdf, "bank_statement", submission_id=sub["id"])
    ds.upload_document(ctx, client_id, YEAR, MONTH, "Electricity_Bill_Oct.pdf", elec_pdf, "expense_bill", submission_id=sub["id"])
    print(f"Uploaded {len(sales) + len(purchases) + 2} documents to submission {sub['id']}")

    ref = ds.submit_documents(ctx, sub["id"], "October bulk demo upload")
    print(f"Submitted. Reference: {ref}")

    docs = ds.list_documents(ctx, client_id, year=YEAR, month=MONTH)
    by_status = {}
    for d in docs:
        by_status[d["status"]] = by_status.get(d["status"], 0) + 1
    print("Status breakdown after auto-processing:", by_status)


if __name__ == "__main__":
    main()
