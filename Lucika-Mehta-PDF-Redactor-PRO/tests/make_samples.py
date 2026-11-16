"""Create synthetic test documents (all values fictitious)."""
import io
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from redact.detect import _VERHOEFF_D, _VERHOEFF_P, luhn_ok  # noqa: E402

_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def aadhaar(base11: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(base11)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][int(ch)]]
    return base11 + str(_INV[c])


def card(base15: str) -> str:
    for d in "0123456789":
        if luhn_ok(base15 + d):
            return base15 + d


AADHAAR = aadhaar("43216789012")
CARD = card("453201511283036")
PAN = "AAKCS1234F"
DOB = "15/04/1980"

STATEMENT = [
    "STATE BANK OF INDIA - Statement of Account",
    "Account Name : M/s Sample Traders Private Limited",
    "Address : Plot 12, Sector 5, Kothrud",
    "          Pune 411038",
    "Account No : 32014567891234      Branch IFSC : SBIN0004567   MICR : 411002034",
    "Customer ID : 88412233  CIN : U51909PN2015PTC123456",
    "PAN of holder: AAKCS1234F   GSTIN: 27AAKCS1234F1Z5   TAN: PNES12345B",
    "Date        Narration                                         Debit        Credit       Balance",
    "01-04-2025  NEFT/UTR SBIN525091234567/RAMESH KUMAR             1,25,000.00               3,75,000.00",
    "03-04-2025  UPI/512345678901/sampletraders@okaxis/Payment                  48,500.00   4,23,500.00",
    "07-04-2025  CARD " + " ".join([CARD[:4], CARD[4:8], CARD[8:12], CARD[12:]]) + " POS PURCHASE  12,450.00             4,11,050.00",
    "10-04-2025  IMPS/P2A/409912345678/Linked A/c XXXXXXXX7788      5,000.00               4,06,050.00",
    "12-04-2025  UPI-SURESH PATIL-suresh@ybl-PAYMENT                            75,000.00   4,81,050.00",
    "15-04-2025  Interest credit on FD                                          1,500.00   4,82,550.00",
    "Director DIN: 08123456   Aadhaar: " + " ".join([AADHAAR[:4], AADHAAR[4:8], AADHAAR[8:]]),
    "Mobile: +91 98220 12345   Email: accounts@sampletraders.in",
]

NOTICE = [
    "Government of India - Income Tax Department",
    "Notice under section 142(1) of the ITA, 1961",
    "DIN: ITBA/AST/F/142(1)/2025-26/1076543210(1)",
    "To,",
    "Sample Traders Pvt Ltd",
    "Plot 12, Sector 5, Kothrud",
    "Pune - 411038",
    "PAN: AAKCS1234F        Assessment Year: 2024-25",
    "Please furnish details of cash deposit of Rs. 25,00,000 made in your account",
    "ending 7788 and in Account 50100123456789 with HDFC0001234.",
    "Funds received from Ramesh Kumar and Suresh Patil are also to be explained.",
]

OTHER_STATEMENT = [
    "HDFC BANK - Account Statement",
    "Customer Name : SAMPLE TRADERS PRIVATE LIMITED",
    "Account Number: 50100123456789",
    "Date        Narration                                  Withdrawal     Deposit       Balance",
    "02-04-2025  NEFT-SBIN0004567-SAMPLE TRADERS PVT LTD-32014567891234   5,00,000.00   5,10,000.00",
    "05-04-2025  CASH DEPOSIT BY SELF                                     25,00,000.00  30,10,000.00",
]


def text_pdf(lines, rotate=0, title="x"):
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    y = 50
    for ln in lines:
        page.insert_text((36, y), ln, fontsize=9.5, fontname="cour")
        y += 17
    if rotate:
        page.set_rotation(rotate)
    doc.set_metadata({"author": "Ramesh Kumar", "title": title})
    return doc


def qr_png(text: str) -> bytes:
    import cv2
    enc = cv2.QRCodeEncoder.create()
    img = enc.encode(text)
    img = cv2.resize(img, (img.shape[1] * 8, img.shape[0] * 8), interpolation=cv2.INTER_NEAREST)
    img = cv2.copyMakeBorder(img, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=255)
    return cv2.imencode(".png", img)[1].tobytes()


def main(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    d = text_pdf(STATEMENT)
    d.save(out / "01_sbi_statement_digital.pdf")

    pix = d[0].get_pixmap(dpi=200)
    sc = pymupdf.open()
    p = sc.new_page(width=d[0].rect.width, height=d[0].rect.height)
    p.insert_image(p.rect, stream=pix.tobytes("png"))
    sc.save(out / "02_sbi_statement_scanned.pdf")

    pymupdf.open(out / "01_sbi_statement_digital.pdf").save(
        out / "03_statement_locked_bankpw.pdf", encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="SAMP1504", owner_pw="o")

    n = text_pdf(NOTICE)
    n[0].insert_image(pymupdf.Rect(700, 40, 800, 140), stream=qr_png(f"PAN:{PAN}|DIN:ITBA/AST/F/142(1)/2025-26/1076543210(1)"))
    n.save(out / "04_notice_142_1_with_qr.pdf")
    text_pdf(NOTICE, rotate=90).save(out / "05_notice_rotated.pdf")
    pix.save(out / "06_photo_of_statement.png")

    # 26AS-style file locked with PAN (lower case) + date of birth
    a = text_pdf(["Annual Tax Statement (Form 26AS)", f"PAN: {PAN}", "Name of Assessee: SAMPLE TRADERS PRIVATE LIMITED",
                  "Assessment Year 2025-26", "TAN of Deductor: MUMR12345C   Amount paid/credited 4,50,000.00"])
    a.save(out / "07_26AS_locked.pdf", encryption=pymupdf.PDF_ENCRYPT_AES_256,
           user_pw=PAN.lower() + "15041980", owner_pw="o")

    text_pdf(OTHER_STATEMENT).save(out / "08_hdfc_statement.pdf")

    # KYC copy with photograph (needs scikit-image for a sample face; skipped otherwise)
    try:
        from skimage import data
    except ImportError:
        data = None
    import cv2
    face = cv2.imencode(".png", cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR))[1].tobytes() if data else None
    k = pymupdf.open()
    kp = k.new_page(width=595, height=420)
    kp.insert_text((40, 50), "Government of India - Unique Identification Authority of India", fontsize=11)
    if face:
        kp.insert_image(pymupdf.Rect(40, 70, 190, 220), stream=face)
    kp.insert_text((210, 100), "Name: Ramesh Kumar Shah", fontsize=11)
    kp.insert_text((210, 120), "Date of Birth: 15/04/1980", fontsize=11)
    kp.insert_text((210, 160), "Aadhaar No: " + " ".join([AADHAAR[:4], AADHAAR[4:8], AADHAAR[8:]]), fontsize=11)
    kp.insert_text((210, 330), "Signature of holder", fontsize=9)
    kp.draw_bezier((215, 312), (240, 280), (270, 330), (320, 300), color=(0, 0, 0.6), width=1.5)
    k.save(out / "09_kyc_aadhaar_copy.pdf")

    # Excel statement: account numbers as numbers, PAN in a hidden sheet
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Statement"
    ws.append(["Account Name", "M/s Sample Traders Private Limited"])
    ws.append(["Account No", 32014567891234])
    ws.append(["Date", "Narration", "Debit", "Credit"])
    ws.append(["01-04-2025", "NEFT/UTR SBIN525091234567/RAMESH KUMAR", 125000, None])
    ws.append(["12-04-2025", "UPI-SURESH PATIL-suresh@ybl-PAYMENT", None, 75000])
    h = wb.create_sheet("KYC")
    h.sheet_state = "hidden"
    h.append(["PAN", PAN])
    wb.properties.creator = "Ramesh Kumar"
    wb.save(out / "10_statement.xlsx")

    (out / "11_ledger.csv").write_text(
        "Date,Party,Account,Amount\n01-04-2025,Ramesh Kumar,32014567891234,125000\n"
        "02-04-2025,Sample Traders Pvt Ltd,50100123456789,500000\n", encoding="utf-8")

    import docx
    w = docx.Document()
    w.add_paragraph("To,")
    w.add_paragraph("The Assessing Officer")
    p = w.add_paragraph("Subject: Reply on behalf of Sample Traders Private Limited, PAN ")
    p.add_run("AAKCS").bold = True
    p.add_run("1234F")
    w.add_paragraph("The cash of Rs. 25,00,000 was deposited in account 50100123456789.")
    t = w.add_table(rows=1, cols=2)
    t.cell(0, 0).text = "Aadhaar of director"
    t.cell(0, 1).text = " ".join([AADHAAR[:4], AADHAAR[4:8], AADHAAR[8:]])
    w.core_properties.author = "Ramesh Kumar"
    w.save(out / "12_draft_reply.docx")
    print("Aadhaar", AADHAAR, "Card", CARD)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
