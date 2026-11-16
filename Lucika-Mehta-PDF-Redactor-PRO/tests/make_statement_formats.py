"""
Builds fictitious bank statements in the layouts of the main Indian banks, to test the
transaction-table (CSV) extractor:   python tests/make_statement_formats.py <out_folder>

Each statement has a known list of transactions (returned by EXPECTED) so the test can
check every date, debit, credit and balance.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

FONT = "helv"


def _put(page, x, y, text, size=7.5, right=False, bold=False):
    font = "hebo" if bold else FONT
    if right:
        x -= pymupdf.get_text_length(text, fontname=font, fontsize=size)
    page.insert_text((x, y), text, fontsize=size, fontname=font)


def inr(v: float) -> str:
    """Indian digit grouping: 1234567.5 -> 12,34,567.50"""
    s = f"{abs(v):.2f}"
    whole, dec = s.split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return whole + "." + dec


# date, narration lines, debit, credit   (balances are computed)
TXNS = [
    ("01/04/2025", ["NEFT CR-SBIN0001234-ACME SUPPLIERS PVT", "LTD-N091250012345"], 0, 250000.00),
    ("03/04/2025", ["UPI-RAHUL KUMAR-rahul@okaxis-UPI REF", "509312345678"], 1850.00, 0),
    ("05/04/2025", ["CHQ PAID-000123-MUNICIPAL CORPORATION"], 12500.00, 0),
    ("08/04/2025", ["ATM WDL 1234 PUNE KOTHRUD"], 10000.00, 0),
    ("12/04/2025", ["INT. PD 01-01-25 TO 31-03-25"], 0, 1234.56),
    ("15/04/2025", ["RTGS DR-HDFC0000123-BETA TRADING CO", "-UTR HDFCR52025041512345678", "PAYMENT AGAINST INV 45"], 300000.00, 0),
    ("18/04/2025", ["CASH DEPOSIT BY SELF"], 0, 49000.00),
    ("22/04/2025", ["ACH D- LIC OF INDIA-POLICY 987654321"], 4560.75, 0),
    ("25/04/2025", ["IMPS-512345678901-SUNIL-OK"], 0, 7500.00),
    ("30/04/2025", ["SMS CHARGES QTR"], 17.70, 0),
]
OPENING = 125000.00


def expected():
    bal = OPENING
    out = []
    for d, n, dr, cr in TXNS:
        bal = round(bal - dr + cr, 2)
        out.append((d, dr, cr, bal))
    return out


EXPECTED = expected()


def _fmt_date(d: str, style: str) -> str:
    dd, mm, yyyy = d.split("/")
    mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][int(mm) - 1]
    return {"dd/mm/yy": f"{dd}/{mm}/{yyyy[2:]}", "dd/mm/yyyy": d, "d Mon yyyy": f"{int(dd)} {mon} {yyyy}",
            "dd-Mon-yy": f"{dd}-{mon}-{yyyy[2:]}", "dd-mm-yyyy": d.replace("/", "-"),
            "yyyy-mm-dd": f"{yyyy}-{mm}-{dd}", "dd Mon yyyy": f"{dd} {mon} {yyyy}"}[style]


def hdfc(path):
    """Date | Narration | Chq./Ref.No. | Value Dt | Withdrawal Amt. | Deposit Amt. | Closing Balance (dd/mm/yy)"""
    d = pymupdf.open()
    p = d.new_page(width=842, height=595)
    _put(p, 30, 40, "HDFC BANK LTD   Statement of account", 11, bold=True)
    _put(p, 30, 58, "Account No : 50100123456789     Cust ID : 12345678     A/C Open Date : 01/01/2020")
    _put(p, 30, 70, "Statement From : 01/04/2025  To : 30/04/2025")
    y = 95
    cols = [(30, "Date"), (80, "Narration"), (330, "Chq./Ref.No."), (430, "Value Dt")]
    for x, t in cols:
        _put(p, x, y, t, bold=True)
    for x, t in [(620, "Withdrawal Amt."), (710, "Deposit Amt."), (800, "Closing Balance")]:
        _put(p, x, y, t, right=True, bold=True)
    y += 16
    for (dt, lines, dr, cr), (_, _, _, bal) in zip(TXNS, EXPECTED):
        _put(p, 30, y, _fmt_date(dt, "dd/mm/yy"))
        _put(p, 80, y, lines[0])
        _put(p, 330, y, "0000" + dt.replace("/", "")[:6])
        _put(p, 430, y, _fmt_date(dt, "dd/mm/yy"))
        if dr:
            _put(p, 620, y, inr(dr), right=True)
        if cr:
            _put(p, 710, y, inr(cr), right=True)
        _put(p, 800, y, inr(bal), right=True)
        for extra in lines[1:]:
            y += 10
            _put(p, 80, y, extra)
        y += 13
    y += 10
    _put(p, 30, y, "STATEMENT SUMMARY :-", bold=True)
    _put(p, 30, y + 12, f"Opening Balance  {inr(OPENING)}    Dr Count 6    Cr Count 4    Closing Bal  {inr(EXPECTED[-1][3])}")
    d.save(path)


def icici(path):
    """S No. | Value Date | Transaction Date | Cheque Number | Transaction Remarks | Withdrawal | Deposit | Balance
    with a two-line header and remarks wrapping above and below the amounts."""
    d = pymupdf.open()
    p = d.new_page(width=842, height=595)
    _put(p, 30, 40, "ICICI Bank   DETAILED STATEMENT", 11, bold=True)
    _put(p, 30, 58, "Account Number 000401234567 - INR - SAMPLE TRADERS")
    y = 90
    for x, t in [(30, "S No."), (60, "Value Date"), (120, "Transaction"), (195, "Cheque"), (250, "Transaction Remarks")]:
        _put(p, x, y, t, bold=True)
    for x, t in [(640, "Withdrawal Amount"), (720, "Deposit Amount"), (800, "Balance (INR )")]:
        _put(p, x, y, t, right=True, bold=True)
    _put(p, 120, y + 9, "Date", bold=True)
    _put(p, 195, y + 9, "Number", bold=True)
    _put(p, 640, y + 9, "(INR )", right=True, bold=True)
    _put(p, 720, y + 9, "(INR )", right=True, bold=True)
    y += 26
    for i, ((dt, lines, dr, cr), (_, _, _, bal)) in enumerate(zip(TXNS, EXPECTED), 1):
        _put(p, 30, y, str(i))
        _put(p, 60, y, _fmt_date(dt, "dd/mm/yyyy"))
        _put(p, 120, y, _fmt_date(dt, "dd/mm/yyyy"))
        _put(p, 195, y, "-")
        _put(p, 250, y, lines[0])
        _put(p, 640, y, inr(dr), right=True)          # ICICI prints 0.00 in the empty column
        _put(p, 720, y, inr(cr), right=True)
        _put(p, 800, y, inr(bal), right=True)
        for extra in lines[1:]:
            y += 10
            _put(p, 250, y, extra)
        y += 14
    _put(p, 30, y + 10, "Page 1 of 1")
    d.save(path)


def sbi(path):
    """Txn Date | Value Date | Description | Ref No./Cheque No. | Debit | Credit | Balance  ('1 Apr 2025')"""
    d = pymupdf.open()
    p = d.new_page(width=842, height=595)
    _put(p, 30, 40, "State Bank of India", 11, bold=True)
    _put(p, 30, 58, "Account Number : 00000032014567891     IFS Code : SBIN0004567")
    _put(p, 30, 70, f"Balance as on 1 Apr 2025 : {inr(OPENING)}")
    y = 95
    for x, t in [(30, "Txn Date"), (95, "Value"), (160, "Description"), (420, "Ref No./Cheque")]:
        _put(p, x, y, t, bold=True)
    for x, t in [(640, "Debit"), (720, "Credit"), (800, "Balance")]:
        _put(p, x, y, t, right=True, bold=True)
    _put(p, 95, y + 9, "Date", bold=True)
    _put(p, 420, y + 9, "No.", bold=True)
    y += 24
    for (dt, lines, dr, cr), (_, _, _, bal) in zip(TXNS, EXPECTED):
        _put(p, 30, y, _fmt_date(dt, "d Mon yyyy"))
        _put(p, 95, y, _fmt_date(dt, "d Mon yyyy"))
        _put(p, 160, y, lines[0][:40])
        _put(p, 420, y, "TRANSFER")
        if dr:
            _put(p, 640, y, inr(dr), right=True)
        if cr:
            _put(p, 720, y, inr(cr), right=True)
        _put(p, 800, y, inr(bal), right=True)
        rest = lines[0][40:]
        for extra in ([rest] if rest else []) + lines[1:]:
            y += 10
            _put(p, 160, y, extra)
        y += 14
    _put(p, 30, y + 10, "**This is a computer generated statement and does not require a signature.")
    d.save(path)


def kotak(path):
    """Date | Narration | Chq/Ref No | Withdrawal (Dr)/ Deposit (Cr) | Balance  - one amount column with (Dr)/(Cr)"""
    d = pymupdf.open()
    p = d.new_page(width=842, height=595)
    _put(p, 30, 40, "Kotak Mahindra Bank   Account Statement", 11, bold=True)
    _put(p, 30, 58, "Account No. 1234567890   Period 01-Apr-25 to 30-Apr-25")
    y = 95
    for x, t in [(30, "Date"), (90, "Narration"), (400, "Chq/Ref No")]:
        _put(p, x, y, t, bold=True)
    for x, t in [(680, "Withdrawal (Dr)/ Deposit (Cr)"), (800, "Balance")]:
        _put(p, x, y, t, right=True, bold=True)
    y += 16
    _put(p, 90, y, "OPENING BALANCE")
    _put(p, 800, y, inr(OPENING) + "(Cr)", right=True)
    y += 13
    for (dt, lines, dr, cr), (_, _, _, bal) in zip(TXNS, EXPECTED):
        _put(p, 30, y, _fmt_date(dt, "dd-Mon-yy"))
        _put(p, 90, y, " ".join(lines)[:55])
        _put(p, 400, y, "UPI-" + dt.replace("/", ""))
        _put(p, 680, y, inr(dr or cr) + ("(Dr)" if dr else "(Cr)"), right=True)
        _put(p, 800, y, inr(bal) + "(Cr)", right=True)
        y += 13
    d.save(path)


def axis_single_amount(path):
    """Tran Date | Chq No | Particulars | Amount | Dr/Cr | Balance  - a separate DR/CR column, ISO-like dates"""
    d = pymupdf.open()
    p = d.new_page(width=842, height=595)
    _put(p, 30, 40, "AXIS BANK", 11, bold=True)
    _put(p, 30, 58, "Statement of Account No :917010012345678 for the period (From : 01-04-2025 To : 30-04-2025)")
    y = 95
    for x, t in [(30, "Tran Date"), (100, "Chq No"), (160, "Particulars"), (620, "Dr/Cr")]:
        _put(p, x, y, t, bold=True)
    for x, t in [(600, "Amount(INR)"), (760, "Balance(INR)")]:
        _put(p, x, y, t, right=True, bold=True)
    y += 16
    _put(p, 160, y, "OPENING BALANCE")
    _put(p, 760, y, inr(OPENING), right=True)
    y += 13
    for (dt, lines, dr, cr), (_, _, _, bal) in zip(TXNS, EXPECTED):
        _put(p, 30, y, _fmt_date(dt, "dd-mm-yyyy"))
        _put(p, 160, y, lines[0])
        _put(p, 600, y, inr(dr or cr), right=True)
        _put(p, 620, y, "DR" if dr else "CR")
        _put(p, 760, y, inr(bal), right=True)
        for extra in lines[1:]:
            y += 10
            _put(p, 160, y, extra)
        y += 13
    d.save(path)


def multipage(path):
    """HDFC layout across two pages with the header repeated, and a page footer."""
    d = pymupdf.open()
    bal_rows = list(zip(TXNS, EXPECTED))
    for half in (bal_rows[:5], bal_rows[5:]):
        p = d.new_page(width=842, height=595)
        y = 60
        for x, t in [(30, "Date"), (80, "Narration"), (430, "Value Dt")]:
            _put(p, x, y, t, bold=True)
        for x, t in [(620, "Withdrawal Amt."), (710, "Deposit Amt."), (800, "Closing Balance")]:
            _put(p, x, y, t, right=True, bold=True)
        y += 16
        for (dt, lines, dr, cr), (_, _, _, bal) in half:
            _put(p, 30, y, _fmt_date(dt, "dd/mm/yy"))
            _put(p, 80, y, lines[0])
            _put(p, 430, y, _fmt_date(dt, "dd/mm/yy"))
            if dr:
                _put(p, 620, y, inr(dr), right=True)
            if cr:
                _put(p, 710, y, inr(cr), right=True)
            _put(p, 800, y, inr(bal), right=True)
            for extra in lines[1:]:
                y += 10
                _put(p, 80, y, extra)
            y += 13
        _put(p, 380, 570, f"Page {p.number + 1} of 2")
    d.save(path)


def _rule(page, y, x0=25, x1=817):
    page.draw_line((x0, y), (x1, y), color=(0.75, 0.75, 0.75), width=0.5)


def icici_new(path, rules=True):
    """ICICI's current layout: S No. | Transaction Date | Cheque Number | Transaction Remarks | Withdrawal |
    Deposit | Balance, where each remarks cell has a bold first line and the date sits on its second line,
    rows separated by thin lines (rules=False: the same without lines), remarks wrapped at a fixed width."""
    d = pymupdf.open()
    p = d.new_page(width=595, height=842)
    _put(p, 30, 40, "Statement of Transactions in Saving Account no. 147801500000 in INR", 9, bold=True)
    y = 80
    for x, t in [(30, "S No."), (70, "Transaction"), (130, "Cheque Number"), (230, "Transaction Remarks")]:
        _put(p, x, y, t, bold=True)
    for x, t in [(450, "Withdrawal"), (510, "Deposit"), (565, "Balance")]:
        _put(p, x, y, t, right=True, bold=True)
    _put(p, 70, y + 9, "Date", bold=True)
    for x, t in [(450, "Amount (INR)"), (510, "Amount (INR)"), (565, "(INR)")]:
        _put(p, x, y + 9, t, right=True, bold=True)
    y += 16
    if rules:
        _rule(p, y, 25, 570)
    width = 38                                     # characters per remarks line (ICICI wraps mid-word)
    for i, ((dt, lines, dr, cr), (_, _, _, bal)) in enumerate(zip(TXNS, EXPECTED), 1):
        text = "".join(lines)
        head = text.split("-")[0][:20]
        chunks = [text[k:k + width] for k in range(0, len(text), width)]
        y += 10
        _put(p, 190, y, head, bold=True)
        y += 10
        _put(p, 30, y, str(i))
        _put(p, 70, y, _fmt_date(dt, "dd/mm/yyyy").replace("/", "."))
        _put(p, 190, y, chunks[0])
        if dr:
            _put(p, 450, y, f"{dr:.2f}", right=True)
        if cr:
            _put(p, 510, y, f"{cr:.2f}", right=True)
        _put(p, 565, y, f"{bal:.2f}", right=True)
        for c in chunks[1:]:
            y += 10
            _put(p, 190, y, c)
        y += 6
        if rules:
            _rule(p, y, 25, 570)
    _put(p, 200, 800, "www.examplebank.in    Dial your Bank 1800-000-000")
    _put(p, 150, 815, "Never share your OTP, CVV or passwords with anyone.")
    d.save(path)


def icici_new_plain(path):
    icici_new(path, rules=False)


def pnb(path):
    """Date | Instrument ID | Amount | Type | Balance | Remarks style is rarer; this is PNB/Union style:
    Txn Date | Cheque No. | Withdrawal | Deposit | Balance | Narration, balances with 'Cr.', narration LAST."""
    d = pymupdf.open()
    p = d.new_page(width=842, height=595)
    _put(p, 30, 40, "Punjab National Bank   Account Statement", 11, bold=True)
    y = 80
    for x, t in [(30, "Txn Date"), (100, "Cheque No."), (430, "Narration")]:
        _put(p, x, y, t, bold=True)
    for x, t in [(240, "Withdrawal"), (310, "Deposit"), (410, "Balance")]:
        _put(p, x, y, t, right=True, bold=True)
    y += 16
    for (dt, lines, dr, cr), (_, _, _, bal) in zip(TXNS, EXPECTED):
        _put(p, 30, y, _fmt_date(dt, "dd-mm-yyyy"))
        if dr:
            _put(p, 240, y, inr(dr), right=True)
        if cr:
            _put(p, 310, y, inr(cr), right=True)
        _put(p, 410, y, inr(bal) + " Cr.", right=True)
        _put(p, 430, y, lines[0][:45])
        rest = (lines[0][45:] + " " + " ".join(lines[1:])).strip()
        if rest:
            y += 10
            _put(p, 430, y, rest[:60])
        y += 13
    d.save(path)


def federal(path):
    """Date | Value Date | Particulars | Tran Type | Withdrawals | Deposits | Balance | DR/CR (separate column)."""
    d = pymupdf.open()
    p = d.new_page(width=842, height=595)
    _put(p, 30, 40, "THE FEDERAL BANK LTD", 11, bold=True)
    y = 80
    for x, t in [(30, "Date"), (85, "Value Date"), (150, "Particulars"), (430, "Tran Type"), (790, "DR/CR")]:
        _put(p, x, y, t, bold=True)
    for x, t in [(600, "Withdrawals"), (680, "Deposits"), (770, "Balance")]:
        _put(p, x, y, t, right=True, bold=True)
    y += 16
    _put(p, 150, y, "Opening Balance")
    _put(p, 770, y, inr(OPENING), right=True)
    _put(p, 790, y, "Cr")
    y += 13
    for (dt, lines, dr, cr), (_, _, _, bal) in zip(TXNS, EXPECTED):
        _put(p, 30, y, _fmt_date(dt, "dd-Mon-yy").upper())
        _put(p, 85, y, _fmt_date(dt, "dd-Mon-yy").upper())
        _put(p, 150, y, lines[0][:45])
        _put(p, 430, y, "TFR")
        if dr:
            _put(p, 600, y, inr(dr), right=True)
        if cr:
            _put(p, 680, y, inr(cr), right=True)
        _put(p, 770, y, inr(bal), right=True)
        _put(p, 790, y, "Cr")
        y += 13
    d.save(path)


def amounts_last_line(path):
    """Date on the first line, narration over several lines, amounts printed on the LAST line of the row."""
    d = pymupdf.open()
    p = d.new_page(width=842, height=595)
    _put(p, 30, 40, "CO-OPERATIVE BANK LTD   Statement", 11, bold=True)
    y = 80
    for x, t in [(30, "Date"), (100, "Particulars")]:
        _put(p, x, y, t, bold=True)
    for x, t in [(600, "Debit"), (690, "Credit"), (800, "Balance")]:
        _put(p, x, y, t, right=True, bold=True)
    y += 16
    for (dt, lines, dr, cr), (_, _, _, bal) in zip(TXNS, EXPECTED):
        _put(p, 30, y, _fmt_date(dt, "dd Mon yyyy"))
        _put(p, 100, y, lines[0])
        for extra in lines[1:]:
            y += 10
            _put(p, 100, y, extra)
        y += 10
        _put(p, 100, y, "(TRANSFER)")
        if dr:
            _put(p, 600, y, f"{dr:.2f}", right=True)
        if cr:
            _put(p, 690, y, f"{cr:.2f}", right=True)
        _put(p, 800, y, f"{bal:.2f}", right=True)
        y += 14
    d.save(path)


FORMATS = {"hdfc": hdfc, "icici": icici, "sbi": sbi, "kotak": kotak, "axis": axis_single_amount, "multipage": multipage,
           "icici_new": icici_new, "icici_new_plain": icici_new_plain, "pnb": pnb, "federal": federal,
           "amounts_last_line": amounts_last_line}


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "statement_formats")
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in FORMATS.items():
        fn(str(out / f"{name}_statement.pdf"))
    print("written to", out)
