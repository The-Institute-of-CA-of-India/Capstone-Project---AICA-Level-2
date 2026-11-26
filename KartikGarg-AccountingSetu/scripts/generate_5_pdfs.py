"""Generate 5 standalone PDFs for manual upload/testing:
  1. One PDF with 50 sales invoices inside it (tests multi-invoice splitting)
  2. One PDF with 30 purchase invoices inside it
  3. One bank statement PDF
  4. One electricity bill PDF
  5. One other-expense bill PDF (internet/office expense)

    python -m scripts.generate_5_pdfs

Files are written to scripts/_generated_5pdfs/. Nothing is uploaded anywhere — these are plain files
for you to upload yourself through the app.
"""
from __future__ import annotations

import datetime as dt
import random
from decimal import Decimal
from pathlib import Path

from reportlab.pdfgen import canvas

from utils.validators import make_gstin

OUT = Path(__file__).with_name("_generated_5pdfs")
YEAR, MONTH = 2026, 10  # October
SELLER_NAME, SELLER_GSTIN = "Capital Infotech Pvt Ltd", "07AABCD4321F1Z6"
BUYER_NAME, BUYER_GSTIN = "Capital Infotech Pvt Ltd", "07AABCD4321F1Z6"  # same entity receives purchases
POS = "07"  # Delhi — must match the client's own state for these intra-state (CGST/SGST) test invoices
CUSTOMERS = ["Rohan Enterprises", "Mehta Retail Stores", "Patil Hardware Mart", "Sunrise General Stores",
            "Kapoor Traders", "Verma Electronics", "Deshmukh & Sons", "Walk-in Customer"]
SUPPLIERS = [("Sharma Steel Suppliers Pvt Ltd", "AABCS1111A"), ("Patel Hardware Distributors", "AABCP2222B"),
            ("Mumbai Packaging Co", "AABCM3333C"), ("National Stationery Supplies", "AABCN5555E")]
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
            lines = invoice_lines(SELLER_NAME, SELLER_GSTIN, customer, None, f"SGT/{YEAR}/{i:04d}", date, taxable)
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
    bal = Decimal("150000.00")
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
    random.seed(7)
    OUT.mkdir(exist_ok=True)
    multi_invoice_pdf(OUT / "Sales_50_Invoices.pdf", 50, as_seller=True)
    multi_invoice_pdf(OUT / "Purchase_30_Invoices.pdf", 30, as_seller=False)
    bank_statement_pdf(OUT / "Bank_Statement.pdf")
    expense_bill_pdf(OUT / "Electricity_Bill.pdf", "Maharashtra State Electricity Distribution Co. Ltd.",
                     make_gstin(POS, "AAACM1234E"), f"MSEDCL/{YEAR}{MONTH:02d}/88213", "Electricity Charges", "9969",
                     Decimal("8400.00"))
    expense_bill_pdf(OUT / "Other_Expense_Internet_Bill.pdf", "Jio Fiber Business Services",
                     make_gstin(POS, "AABCJ9988K"), f"JIO/{YEAR}{MONTH:02d}/55120", "Internet & Broadband Services", "9984",
                     Decimal("3200.00"))
    print(f"Wrote 5 PDFs to {OUT}")


if __name__ == "__main__":
    main()
