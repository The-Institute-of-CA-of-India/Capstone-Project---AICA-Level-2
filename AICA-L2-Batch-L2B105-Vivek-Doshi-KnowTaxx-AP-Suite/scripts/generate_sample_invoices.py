"""Create dummy GST invoices for OCR testing and the demo. Every party and number here is fictional.

Run: python scripts/generate_sample_invoices.py
Output: tests/sample_invoices/ (five PNGs, one PDF, one JPG receipt, and expected.json with the true values)
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "tests" / "sample_invoices"
BUYER_GSTIN_PAN = "AABCA1234C"
_B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin(state, pan):
    body = f"{state}{pan}1Z"
    total = 0
    for i, ch in enumerate(body):
        product = _B36.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return body + _B36[(36 - total % 36) % 36]


def font(size, bold=False):
    names = ("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def money(value):
    whole, frac = f"{value:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return f"{whole}.{frac}"


NAVY = (30, 58, 110)
INK = (25, 25, 25)
LINE = (120, 120, 120)

BUYER = {"name": "ABC Manufacturing Pvt Ltd", "gstin": gstin("27", BUYER_GSTIN_PAN), "address": "Plot 14, MIDC Bhosari, Pune 411026"}

today = date.today()
SAMPLES = [
    {"file": "invoice_gst_1.png", "vendor": "Sharma Steel Traders", "pan": "AAFFS1234K", "state": "27", "number": "SST/26-27/0451",
     "date": today - timedelta(days=12), "terms": 30, "address": "22 Industrial Estate, Chakan, Pune 410501",
     "items": [("MS Steel Sheets 2mm", "7208", 40, 1850.00), ("Steel Angles 50x50", "7216", 25, 980.00)], "rate": 18, "inter": False},
    {"file": "invoice_gst_2.png", "vendor": "Patel Consultancy Services", "pan": "AACFP5678M", "state": "24", "number": "PCS-1187",
     "date": today - timedelta(days=20), "terms": 15, "address": "401 Shivalik Plaza, Ahmedabad 380015",
     "items": [("Professional fees for GST advisory", "998231", 1, 45000.00)], "rate": 18, "inter": True},
    {"file": "invoice_gst_3.png", "vendor": "Greenfield Facility Services", "pan": "AAGCG9012P", "state": "27", "number": "GFS/2627/0093",
     "date": today - timedelta(days=5), "terms": 30, "address": "Unit 7, Baner Road, Pune 411045",
     "items": [("Housekeeping services monthly", "998533", 1, 32000.00), ("Security service guards", "998525", 2, 18500.00)], "rate": 18, "inter": False},
    {"file": "invoice_gst_4.png", "vendor": "Nexa Cloud Technologies", "pan": "AAHCN3456Q", "state": "29", "number": "NCT-INV-20764",
     "date": today - timedelta(days=30), "terms": 30, "address": "12th Floor, Prestige Tower, Bengaluru 560001",
     "items": [("Cloud hosting subscription", "998315", 12, 8500.00), ("Software licence renewal", "997331", 5, 3200.00)], "rate": 18, "inter": True},
    {"file": "invoice_gst_5.png", "vendor": "Mahalaxmi Packaging Industries", "pan": "AAIFM7890R", "state": "27", "number": "MPI/0782",
     "date": today - timedelta(days=38), "terms": 45, "address": "Gat No. 218, Talegaon, Pune 410507",
     "items": [("Corrugated packaging boxes", "4819", 2000, 18.50), ("Packing material tape rolls", "3919", 150, 62.00)], "rate": 12, "inter": False},
]


def totals(sample):
    taxable = round(sum(q * r for _, _, q, r in sample["items"]), 2)
    tax = round(taxable * sample["rate"] / 100, 2)
    if sample["inter"]:
        cgst, sgst, igst = 0.0, 0.0, tax
    else:
        cgst = sgst = round(tax / 2, 2)
        igst = 0.0
    return taxable, cgst, sgst, igst, round(taxable + cgst + sgst + igst, 2)


def draw_invoice(sample):
    W, H = 1654, 2200
    image = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(image)
    m = 90
    seller_gstin = gstin(sample["state"], sample["pan"])

    d.text((m, 70), sample["vendor"], fill=NAVY, font=font(52, True))
    d.text((m, 138), sample["address"], fill=INK, font=font(28))
    d.text((m, 178), f"GSTIN: {seller_gstin}", fill=INK, font=font(30, True))
    d.text((m, 218), f"PAN: {sample['pan']}", fill=INK, font=font(28))
    d.line((m, 270, W - m, 270), fill=NAVY, width=4)
    d.text((m, 290), "TAX INVOICE", fill=NAVY, font=font(42, True))

    y = 370
    d.text((m, y), f"Invoice No: {sample['number']}", fill=INK, font=font(30, True))
    d.text((980, y), f"Invoice Date: {sample['date'].strftime('%d/%m/%Y')}", fill=INK, font=font(30))
    y += 46
    d.text((980, y), f"Due Date: {(sample['date'] + timedelta(days=sample['terms'])).strftime('%d/%m/%Y')}", fill=INK, font=font(30))
    y += 70
    d.text((m, y), "Bill To:", fill=NAVY, font=font(30, True))
    y += 42
    d.text((m, y), BUYER["name"], fill=INK, font=font(30))
    y += 40
    d.text((m, y), BUYER["address"], fill=INK, font=font(28))
    y += 40
    d.text((m, y), f"Buyer GSTIN: {BUYER['gstin']}", fill=INK, font=font(28))
    y += 80

    columns = [m + 10, 780, 960, 1130, 1340]
    headers = ["Description", "HSN/SAC", "Qty", "Rate", "Amount"]
    d.rectangle((m, y, W - m, y + 56), fill=(230, 235, 245))
    for x, header in zip(columns, headers):
        d.text((x, y + 12), header, fill=NAVY, font=font(28, True))
    y += 72
    for description, hsn, quantity, rate in sample["items"]:
        d.text((columns[0], y), description, fill=INK, font=font(28))
        d.text((columns[1], y), hsn, fill=INK, font=font(28))
        d.text((columns[2], y), str(quantity), fill=INK, font=font(28))
        d.text((columns[3], y), money(rate), fill=INK, font=font(28))
        d.text((columns[4], y), money(quantity * rate), fill=INK, font=font(28))
        y += 52
    d.line((m, y + 10, W - m, y + 10), fill=LINE, width=2)
    y += 40

    taxable, cgst, sgst, igst, total = totals(sample)
    half = sample["rate"] / 2
    rows = [("Taxable Value", taxable)]
    rows += [(f"IGST @ {sample['rate']}%", igst)] if sample["inter"] else [(f"CGST @ {half:g}%", cgst), (f"SGST @ {half:g}%", sgst)]
    for label, value in rows:
        d.text((900, y), label, fill=INK, font=font(30))
        d.text((1340, y), money(value), fill=INK, font=font(30))
        y += 50
    d.line((880, y + 4, W - m, y + 4), fill=NAVY, width=3)
    y += 22
    d.text((900, y), "Grand Total", fill=NAVY, font=font(34, True))
    d.text((1340, y), money(total), fill=NAVY, font=font(34, True))
    y += 110
    d.text((m, y), "Bank: Fictional Bank Ltd, A/c 000123456789, IFSC FICT0001234", fill=INK, font=font(26))
    y += 40
    d.text((m, y), "This is a fictional sample invoice for demonstration only.", fill=LINE, font=font(24))
    return image


def draw_receipt():
    W, H = 760, 1120
    image = Image.new("RGB", (W, H), (252, 251, 247))
    d = ImageDraw.Draw(image)
    pan = "AAJFK2345S"
    seller = gstin("27", pan)
    y = 40
    d.text((60, y), "Hotel Konkan Residency", fill=INK, font=font(36, True)); y += 56
    d.text((60, y), "MG Road, Ratnagiri 415612", fill=INK, font=font(22)); y += 34
    d.text((60, y), f"GSTIN: {seller}", fill=INK, font=font(24, True)); y += 60
    d.text((60, y), "Bill No: HKR-5521", fill=INK, font=font(26)); y += 40
    when = today - timedelta(days=3)
    d.text((60, y), f"Date: {when.strftime('%d-%m-%Y')}", fill=INK, font=font(26)); y += 60
    d.line((60, y, W - 60, y), fill=LINE, width=2); y += 24
    d.text((60, y), "Hotel room stay 1 night", fill=INK, font=font(26)); y += 70
    for label, value in (("Taxable Value", 3500.00), ("CGST @ 6%", 210.00), ("SGST @ 6%", 210.00)):
        d.text((60, y), label, fill=INK, font=font(26))
        d.text((520, y), money(value), fill=INK, font=font(26)); y += 46
    d.line((60, y, W - 60, y), fill=LINE, width=2); y += 20
    d.text((60, y), "Grand Total", fill=INK, font=font(30, True))
    d.text((520, y), money(3920.00), fill=INK, font=font(30, True))
    return image, {"file": "expense_receipt_1.jpg", "vendor": "Hotel Konkan Residency", "gstin": seller, "number": "HKR-5521",
                   "date": when.isoformat(), "taxable": 3500.00, "cgst": 210.00, "sgst": 210.00, "igst": 0.0, "total": 3920.00}


def expected_row(sample, filename=None):
    taxable, cgst, sgst, igst, total = totals(sample)
    return {"file": filename or sample["file"], "vendor": sample["vendor"], "gstin": gstin(sample["state"], sample["pan"]),
            "number": sample["number"], "date": sample["date"].isoformat(), "taxable": taxable, "cgst": cgst, "sgst": sgst,
            "igst": igst, "total": total, "buyer_gstin": BUYER["gstin"]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    expected = []
    for sample in SAMPLES:
        draw_invoice(sample).save(OUT / sample["file"], dpi=(200, 200))
        expected.append(expected_row(sample))
    # The PDF named in the project structure: same content as sample 2, in PDF form
    draw_invoice(SAMPLES[1]).save(OUT / "invoice_gst_2.pdf", "PDF", resolution=200.0)
    expected.append(expected_row(SAMPLES[1], "invoice_gst_2.pdf"))
    receipt, row = draw_receipt()
    receipt.save(OUT / "expense_receipt_1.jpg", quality=90)
    expected.append(row)
    (OUT / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    print(f"Wrote {len(expected)} sample documents to {OUT}")


if __name__ == "__main__":
    main()
