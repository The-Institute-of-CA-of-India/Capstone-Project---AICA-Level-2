"""Generate fictitious sample data for the TDS Credit Reconciliation Assistant.
All names, PANs, TANs, emails and amounts are invented for demonstration."""
import os, sys
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

OUT = sys.argv[1] if len(sys.argv) > 1 else "sample_data"
os.makedirs(f"{OUT}/Form16A_PDFs", exist_ok=True)

DEDUCTEE = ("SHREE SAMPLE CONSULTANTS LLP", "AAQFS1234K")
AY = "2026-27"
Q = {"Q1": ("01-Apr-2025", "30-Jun-2025"), "Q2": ("01-Jul-2025", "30-Sep-2025")}

# name, TAN, PAN, contact, email
CUST = {
 "MUMA10001A": ("ALPHA MEDIA SOLUTIONS PRIVATE LIMITED", "AABCA1001A", "Ritu Sharma", "accounts@alphamedia.example"),
 "MUMB20002B": ("BRIGHTWAVE (INDIA) PRIVATE LIMITED", "AABCB2002B", "Kiran Desai", "tds@brightwave.example"),
 "DELC30003C": ("CEDAR RETAIL LIMITED", "AABCC3003C", "Amit Verma", "payables@cedarretail.example"),
 "PNED40004D": ("DELTA INFRA PROJECTS LTD", "AABCD4004D", "Sneha Kulkarni", "finance@deltainfra.example"),
 "MUME50005E": ("EVEREST FINSERV LIMITED", "AABCE5005E", "Rahul Mehta", "tds.team@everestfinserv.example"),
 "BLRF60006F": ("FALCON LOGISTICS PRIVATE LIMITED", "AABCF6006F", "Lakshmi Iyer", "ap@falconlogistics.example"),
 "MUMG70007G": ("GALAXY TELECOM LIMITED", "AABCG7007G", "Vikram Shah", "taxdesk@galaxytelecom.example"),
 "AHMH80008H": ("HORIZON PHARMA LIMITED", "AABCH8008H", "Nisha Patel", "accounts@horizonpharma.example"),
 "MUMI90009I": ("IRIS EDUCATION SERVICES LIMITED", "AABCI9009I", "Farhan Khan", "finance@iriseducation.example"),
 "CHEJ10010J": ("JUPITER HOTELS LIMITED", "AABCJ1010J", "Deepa Nair", "tds@jupiterhotels.example"),
 "PNEK11011K": ("KAPPA ENGINEERING WORKS PRIVATE LIMITED", "AABCK1011K", "Suresh Pillai", "accounts@kappaeng.example"),
 "DELL12012L": ("LOTUS FOODS LIMITED", "AABCL1012L", "Meera Joshi", "tds@lotusfoods.example"),
 "MUMM13013M": ("MAPLE CONSULTING LLP", "AAKFM1013M", "Arjun Rao", "finance@mapleconsulting.example"),
 "BLRN14014N": ("NOVA RETAIL PRIVATE LIMITED", "AABCN1014N", "Pooja Menon", "payables@novaretail.example"),
 "HYDO15015O": ("OMEGA SERVICES LIMITED", "AABCO1015O", "Ravi Kumar", "ap@omegaservices.example"),
}

# Books: TAN, invoice, date, section, taxable amount, TDS expected, TDS actually withheld from our receipt
BOOKS = [
 ("MUMA10001A","INV-2501","15-May-2025","194J",500000,50000,50000),
 ("MUMA10001A","INV-2511","12-Aug-2025","194J",300000,30000,30000),
 ("MUMB20002B","INV-2503","20-Jun-2025","194J",250000,25000,25000),
 ("DELC30003C","INV-2504","05-May-2025","194J",400000,40000,40000),
 ("PNED40004D","INV-2505","18-Jun-2025","194J",600000,60000,60000),
 ("MUME50005E","INV-2512","22-Aug-2025","194J",200000,20000,20000),
 ("BLRF60006F","INV-2506","10-Jun-2025","194J",120000,12000,12000),
 ("AHMH80008H","INV-2513","09-Sep-2025","194J",200000,20000,20000),
 ("MUMI90009I","INV-2507","28-Jun-2025","194J",100000,10000,10000),
 ("CHEJ10010J","INV-2514","14-Jul-2025","194J",80000,8000,8000),
 ("PNEK11011K","INV-2515","04-Aug-2025","194J",100000,10000,20000),
 ("DELL12012L","INV-2516","19-Aug-2025","194J",100000,10000,11800),
 ("MUMM13013M","INV-2517","25-Sep-2025","194J",100000,10000,2000),
 ("BLRN14014N","INV-2540","20-Mar-2026","194J",150000,15000,15000),
 ("HYDO15015O","INV-2541","11-Nov-2025","194J",90000,9000,0),
]

# 26AS: TAN -> list of (section, txn date, booking status, booking date, paid, deducted, deposited)
AS26 = {
 "MUMA10001A":[("194J","15-May-2025","F","31-Jul-2025",500000,50000,50000),("194J","12-Aug-2025","F","31-Oct-2025",300000,30000,30000)],
 "MUMB20002B":[("194J","20-Jun-2025","F","31-Jul-2025",250000,25000,25000)],
 "DELC30003C":[("194J","05-May-2025","F","31-Jul-2025",400000,40000,40000)],
 "PNED40004D":[("194J","18-Jun-2025","F","31-Jul-2025",450000,45000,45000)],
 "BLRF60006F":[("194C","10-Jun-2025","F","31-Jul-2025",120000,2400,2400)],
 "MUMG70007G":[("194J","25-Sep-2025","F","31-Oct-2025",150000,15000,15000)],
 "AHMH80008H":[("194J","09-Sep-2025","F","31-Oct-2025",180000,18000,18000)],
 "MUMI90009I":[("194J","02-Jul-2025","F","31-Oct-2025",100000,10000,10000)],
 "CHEJ10010J":[("194J","14-Jul-2025","U","31-Oct-2025",80000,8000,8000)],
 "PNEK11011K":[("194J","04-Aug-2025","F","31-Oct-2025",100000,20000,20000)],
 "DELL12012L":[("194J","19-Aug-2025","F","31-Oct-2025",118000,11800,11800)],
 "MUMM13013M":[("194C","25-Sep-2025","F","31-Oct-2025",100000,2000,2000)],
}

# Certificates: (TAN, quarter, cert no, last updated, payments[(amt, section, date)], deducted, challans[(amt,bsr,date,serial)])
CERTS = [
 ("MUMA10001A","Q1","KQWERTA","10-Aug-2025",[(500000,"194J","15-May-2025")],50000,[(50000,"0510308","07-Jun-2025","10231")]),
 ("MUMA10001A","Q2","KQWERTB","12-Nov-2025",[(300000,"194J","12-Aug-2025")],30000,[(30000,"0510308","06-Sep-2025","20777")]),
 ("MUMB20002B","Q1","BRWIDXC","11-Aug-2025",[(150000,"194J","20-Jun-2025"),(100000,"194J","20-Jun-2025")],25000,[(15000,"0180002","07-Jul-2025","57843"),(10000,"0180002","07-Jul-2025","57844")]),
 ("PNED40004D","Q1","DLTPNQZ","09-Aug-2025",[(450000,"194J","18-Jun-2025")],45000,[(45000,"0002390","05-Jul-2025","33012")]),
 ("BLRF60006F","Q1","FLCNBLR","08-Aug-2025",[(120000,"194C","10-Jun-2025")],2400,[(2400,"6390009","07-Jul-2025","11587")]),
 ("MUMG70007G","Q2","GLXTMUM","15-Nov-2025",[(150000,"194J","25-Sep-2025")],15000,[(15000,"0510308","07-Oct-2025","40012")]),
 ("AHMH80008H","Q2","HRZNAHD","14-Nov-2025",[(200000,"194J","09-Sep-2025")],20000,[(20000,"0410013","07-Oct-2025","50981")]),
 ("MUMI90009I","Q2","IRSEDUQ","16-Nov-2025",[(100000,"194J","02-Jul-2025")],10000,[(10000,"0510308","07-Aug-2025","60233")]),
 ("CHEJ10010J","Q2","JPTRCHN","18-Nov-2025",[(80000,"194J","14-Jul-2025")],8000,[(8000,"0240020","07-Aug-2025","70451")]),
 ("PNEK11011K","Q2","KPPAENG","17-Nov-2025",[(100000,"194J","04-Aug-2025")],20000,[(20000,"0510308","06-Sep-2025","81122")]),
 ("DELL12012L","Q2","LTSFDQW","17-Nov-2025",[(118000,"194J","19-Aug-2025")],11800,[(11800,"0180002","05-Sep-2025","91233")]),
 ("MUMM13013M","Q2","MPLCNSL","18-Nov-2025",[(100000,"194C","25-Sep-2025")],2000,[(2000,"0002390","07-Oct-2025","12090")]),
]

def money(v): return f"{v:.2f}"

def make_cert(t):
    tan, q, certno, upd, pays, ded, challans = t
    name, pan = CUST[tan][0], CUST[tan][1]
    fn = f"{OUT}/Form16A_PDFs/{DEDUCTEE[1]}_{q}_{tan}.pdf"
    c = canvas.Canvas(fn, pagesize=A4)
    W, H = A4
    y = H - 50
    def line(items, dy=16, size=9, bold=False):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        for x, s in items:
            c.drawString(x, y, s)
        y -= dy
    line([(240, "FORM NO. 16A")], 14, 12, True)
    line([(250, "[See rule 31(1)(b)]")])
    line([(110, "Certificate under section 203 of the Income-tax Act, 1961 for tax deducted at source")], 22)
    line([(40, f"Certificate No. {certno}"), (380, f"Last updated on {upd}")], 22)
    line([(40, "Name and address of the deductor"), (310, "Name and address of the deductee")], 14, 9, True)
    line([(40, name), (310, DEDUCTEE[0])])
    line([(40, "12, Sample Business Park, Andheri East"), (310, "4th Floor, Example Chambers, Fort")])
    line([(40, "MUMBAI - 400093, Maharashtra"), (310, "MUMBAI - 400001, Maharashtra")], 22)
    line([(40, "PAN of the deductor"), (200, "TAN of the deductor"), (380, "PAN of the deductee")], 14, 9, True)
    line([(40, pan), (200, tan), (380, DEDUCTEE[1])], 22)
    line([(40, "CIT (TDS)"), (300, "Assessment Year"), (420, "Period"), ], 14, 9, True)
    line([(420, "From"), (490, "To")], 14)
    line([(40, "The Commissioner of Income Tax (TDS)"), (300, AY), (420, Q[q][0]), (490, Q[q][1])], 22)
    line([(40, "Summary of payment")], 14, 10, True)
    line([(40, "Sl. No."), (90, "Amount paid/credited"), (230, "Nature of payment**"), (350, "Deductee Reference No."), (470, "Date of payment/credit")], 14, 8, True)
    tot = 0
    for i, (a, s, d) in enumerate(pays, 1):
        tot += a
        line([(40, str(i)), (90, money(a)), (230, s), (470, d)])
    line([(40, "Total (Rs.)"), (90, money(tot))], 22, 9, True)
    line([(40, "Summary of tax deducted at source in respect of deductee")], 14, 10, True)
    line([(40, "Quarter"), (110, "Receipt Numbers of Original Quarterly Statements"), (330, "Amount of Tax Deducted"), (450, "Amount of Tax Deposited")], 14, 8, True)
    line([(40, q), (110, "QRSTUVWX"), (330, money(ded)), (450, money(sum(x[0] for x in challans)))])
    line([(40, "Total (Rs.)"), (330, money(ded)), (450, money(sum(x[0] for x in challans)))], 22, 9, True)
    line([(40, "I. DETAILS OF TAX DEDUCTED AND DEPOSITED IN THE CENTRAL GOVERNMENT ACCOUNT THROUGH BOOK ADJUSTMENT")], 14, 8, True)
    line([(40, "Total (Rs.)")], 22, 9, True)
    line([(40, "II. DETAILS OF TAX DEDUCTED AND DEPOSITED IN THE CENTRAL GOVERNMENT ACCOUNT THROUGH CHALLAN")], 14, 8, True)
    line([(40, "Sl. No."), (90, "Tax Deposited in respect of the deductee (Rs.)"), (300, "BSR Code"), (370, "Date"), (440, "Challan Serial"), (510, "Status")], 14, 8, True)
    for i, (a, b, d, s) in enumerate(challans, 1):
        line([(40, str(i)), (90, money(a)), (300, b), (370, d), (440, s), (510, "F")])
    line([(40, "Total (Rs.)"), (90, money(sum(x[0] for x in challans)))], 26, 9, True)
    line([(40, "Verification")], 14, 10, True)
    line([(40, f"I, AUTHORISED SIGNATORY, certify that a sum of Rs. {money(ded)} has been deducted and deposited.")])
    line([(40, "SAMPLE DATA - FICTITIOUS CERTIFICATE FOR DEMONSTRATION ONLY")], 14, 8, True)
    c.setFont("Helvetica", 8)
    c.drawString(40, 30, f"Certificate No. {certno}")
    c.drawString(480, 30, "Page 1 of 1")
    c.save()

for t in CERTS:
    make_cert(t)

# --- 26AS text file (TRACES caret-delimited style) ---
L = []
L.append("File Creation Date^15-11-2025^^^^^^^^")
L.append("Permanent Account Number (PAN)^Current Status of PAN^Financial Year^Assessment Year^^^^^^")
L.append(f"{DEDUCTEE[1]}^Active^2025-26^{AY}^^^^^^")
L.append(f"Name of Assessee^{DEDUCTEE[0]}^^^^^^^^")
L.append("^^^^^^^^^")
L.append("PART-I - Details of Tax Deducted at Source^^^^^^^^^")
L.append("Sr. No.^Name of Deductor^TAN of Deductor^^^^^Total Amount Paid / Credited^Total Tax Deducted #^Total TDS Deposited")
for n, (tan, rows) in enumerate(AS26.items(), 1):
    L.append(f"{n}^{CUST[tan][0]}^{tan}^^^^^{money(sum(r[4] for r in rows))}^{money(sum(r[5] for r in rows))}^{money(sum(r[6] for r in rows))}")
    L.append("^Sr. No.^Section ^Transaction Date^Status of Booking*^Date of Booking^Remarks**^Amount Paid / Credited^Tax Deducted ##^TDS Deposited")
    for i, r in enumerate(rows, 1):
        L.append(f"^{i}^{r[0]}^{r[1]}^{r[2]}^{r[3]}^-^{money(r[4])}^{money(r[5])}^{money(r[6])}")
L.append("^^^^^^^^^")
L.append("PART-II - Details of Tax Deducted at Source for 15G / 15H^^^^^^^^^")
L.append("No Transactions Present^^^^^^^^^")
open(f"{OUT}/Form26AS_{DEDUCTEE[1]}_2025-26.txt", "w").write("\n".join(L) + "\n")

# --- Books workbook ---
wb = Workbook()
hdr = Font(bold=True, color="FFFFFF"); fill = PatternFill("solid", fgColor="1F4E79")
ws = wb.active; ws.title = "Books"
cols = ["Customer Name", "TAN", "Invoice No", "Invoice Date", "Section", "Taxable Amount", "GST", "Amount Received", "TDS Expected", "Quarter (optional)"]
ws.append(cols)
for tan, inv, d, s, a, t, w in BOOKS:
    gst = round(a * 0.18)
    ws.append([CUST[tan][0], tan, inv, d, s, a, gst, a + gst - w, t, ""])
ws2 = wb.create_sheet("Customers")
ws2.append(["Customer Name", "TAN", "PAN", "Contact Person", "Email"])
for tan, (n, p, cp, em) in CUST.items():
    ws2.append([n, tan, p, cp, em])
for w in (ws, ws2):
    for c in w[1]: c.font = hdr; c.fill = fill
    for col in w.columns:
        w.column_dimensions[col[0].column_letter].width = max(12, max(len(str(c.value or "")) for c in col) + 2)
wb.save(f"{OUT}/Books_and_Customers_FY2025-26.xlsx")
print("done", len(CERTS), "certs")
