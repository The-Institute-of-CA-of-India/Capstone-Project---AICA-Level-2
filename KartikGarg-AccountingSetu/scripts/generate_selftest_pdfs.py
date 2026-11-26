"""Generate test PDFs for the self-test demo client 'Om Traders' (state Haryana, code 06).
Same shape as generate_5_pdfs.py but for a fresh entity and the CURRENT month, so no month-switch is
needed in the UI during the demo recording.

    python -m scripts.generate_selftest_pdfs

Files land in scripts/_selftest_demo/.
"""
from __future__ import annotations

import datetime as dt
import random
from decimal import Decimal
from pathlib import Path

from reportlab.pdfgen import canvas

from utils.validators import make_gstin

OUT = Path(__file__).with_name("_selftest_demo")
today = dt.date.today()
YEAR, MONTH = today.year, today.month
SELLER_NAME, SELLER_GSTIN = "Om Traders", make_gstin("06", "AAEPT1234F")
BUYER_NAME, BUYER_GSTIN = "Om Traders", make_gstin("06", "AAEPT1234F")
POS = "06"  # Haryana — must match the client's own state for these intra-state (CGST/SGST) test invoices
CUSTOMERS = ["Arora Enterprises", "Singh Retail Stores", "Bansal Hardware Mart", "Goyal General Stores",
            "Khanna Traders", "Malhotra Electronics", "Chopra & Sons", "Walk-in Customer"]
SUPPLIERS = [("Haryana Steel Suppliers Pvt Ltd", "AABCH1111A"), ("Gupta Hardware Distributors", "AABCG2222B"),
            ("Panipat Textile Co", "AABCP3333C"), ("National Stationery Supplies", "AABCN5555E")]
ITEMS = [("General Merchandise", "4819"), ("Hardware Fittings", "8302"), ("Electrical Goods", "8536"),
        ("Office Stationery", "4820"), ("Packaging Material", "3923")]


def invoice_lines(supplier_name, supplier_gstin, customer_name, customer_gstin, invoice_no, date, taxable):
    item_desc, hsn = random.choice(ITEMS)
    qty = random.choice([1, 2, 5, 10])
    rate = (taxable / qty).quantize(Decimal("0.01"))
    tax = (taxable * Decimal("18") / 100).quantize(Decimal("0.01"))
    half = (tax / 2).quantize(Decimal("0.01"))
    total = taxable + 2 * half
    lines = [supplier_name, "TAX INVOICE", f"GSTIN: {supplier_gstin}", f"Invoice No: {invoice_no}",
            f"Invoice Date: {date:%d/%m/%Y}", f"Place of Supply: {POS}", "Reverse Charge: No", "Bill To:", customer_name]
    if customer_gstin:
        lines.append(f"Buyer GSTIN: {customer_gstin}")
    lines += ["Description HSN Qty Rate Amount GST%", f"{item_desc} {hsn} {qty} {rate} {taxable:.2f} 18%",
             f"Taxable Value: {taxable:.2f}", f"CGST @ 9%: {half:.2f}", f"SGST @ 9%: {half:.2f}", f"Grand Total: {total:.2f}"]
    return lines


def multi_invoice_pdf(path: Path, count: int, *, as_seller: bool):
    c = canvas.Canvas(str(path))
    for i in range(1, count + 1):
        date = dt.date(YEAR, MONTH, min(1 + (i * 2) % 27, 28))
        taxable = Decimal(random.choice([1500, 2500, 4200, 6800, 9500, 15000, 22000, 35000]))
        if as_seller:
            customer = random.choice(CUSTOMERS)
            lines = invoice_lines(SELLER_NAME, SELLER_GSTIN, customer, None, f"OMT/{YEAR}/{i:04d}", date, taxable)
        else:
            supplier, pan_body = random.choice(SUPPLIERS)
            supplier_gstin = make_gstin(POS, pan_body)
            lines = invoice_lines(supplier, supplier_gstin, BUYER_NAME, BUYER_GSTIN,
                                  f"{supplier[:3].upper()}/{YEAR}{MONTH:02d}/{i:03d}", date, taxable)
        y = 800
        for ln in lines:
            c.drawString(50, y, ln)
            y -= 18
        c.showPage()
    c.save()


def bank_statement_pdf(path: Path):
    bal = Decimal("200000.00")
    lines = [f"Opening Balance: {bal:.2f}"]
    for i, day in enumerate([3, 6, 9, 12, 15, 18, 21, 24, 27], start=1):
        if i % 3 == 0:
            amt = Decimal(random.choice([5900, 11800, 23600]))
            bal += amt
            lines.append(f"{day:02d}/{MONTH:02d}/{YEAR} NEFT-CUSTOMER PAYMENT INV{i:03d} {amt:.2f} {bal:.2f}")
        else:
            amt = Decimal(random.choice([3540, 7080, 10620]))
            bal -= amt
            lines.append(f"{day:02d}/{MONTH:02d}/{YEAR} RTGS-SUPPLIER PAYMENT {amt:.2f} {bal:.2f}")
    bal -= Decimal("354.00")
    lines.append(f"28/{MONTH:02d}/{YEAR} BANK CHARGES QTR {354.00:.2f} {bal:.2f}")
    c = canvas.Canvas(str(path))
    y = 800
    for ln in lines:
        c.drawString(50, y, ln)
        y -= 18
    c.save()


def expense_bill_pdf(path: Path, seller_name: str, seller_gstin: str, invoice_no: str, description: str, hsn: str, amount: Decimal):
    date = dt.date(YEAR, MONTH, 20)
    tax = (amount * Decimal("18") / 100).quantize(Decimal("0.01"))
    half = (tax / 2).quantize(Decimal("0.01"))
    lines = [seller_name, "TAX INVOICE", f"GSTIN: {seller_gstin}", f"Invoice No: {invoice_no}",
            f"Invoice Date: {date:%d/%m/%Y}", f"Place of Supply: {POS}", "Bill To:", BUYER_NAME, f"Buyer GSTIN: {BUYER_GSTIN}",
            "Description HSN Qty Rate Amount GST%", f"{description} {hsn} 1 {amount:.2f} {amount:.2f} 18%",
            f"Taxable Value: {amount:.2f}", f"CGST @ 9%: {half:.2f}", f"SGST @ 9%: {half:.2f}",
            f"Grand Total: {(amount + 2 * half):.2f}"]
    c = canvas.Canvas(str(path))
    y = 800
    for ln in lines:
        c.drawString(50, y, ln)
        y -= 18
    c.save()


def main():
    random.seed(42)
    OUT.mkdir(exist_ok=True)
    multi_invoice_pdf(OUT / "Sales_40_Invoices.pdf", 40, as_seller=True)
    multi_invoice_pdf(OUT / "Purchase_20_Invoices.pdf", 20, as_seller=False)
    bank_statement_pdf(OUT / "Bank_Statement.pdf")
    expense_bill_pdf(OUT / "Electricity_Bill.pdf", "Haryana State Electricity Distribution Co. Ltd.",
                     make_gstin(POS, "AAACH1234E"), f"HSEDC/{YEAR}{MONTH:02d}/77213", "Electricity Charges", "9969",
                     Decimal("7200.00"))
    expense_bill_pdf(OUT / "Other_Expense_Internet_Bill.pdf", "Airtel Business Services",
                     make_gstin(POS, "AABCA9988K"), f"ABS/{YEAR}{MONTH:02d}/44120", "Internet & Broadband Services", "9984",
                     Decimal("2800.00"))
    print(f"Wrote 5 PDFs to {OUT}")


if __name__ == "__main__":
    main()
