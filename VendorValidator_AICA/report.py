"""
report.py - Excel input reader and colour-coded Excel report writer.

Colour scheme (medium-light tones):
    Header            : medium-light blue   #9DC3E6
    Section header    : light blue          #DDEBF7
    PASS              : light green         #C6E0B4
    WARNING / REVIEW  : light amber         #FFE699
    FAIL              : light red / salmon  #F4B183
    NOT PROVIDED      : light grey          #D9D9D9
    Online data cols  : light lavender      #E4DFEC
"""
from __future__ import annotations

from datetime import datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from validators import FAIL, NA, PASS, WARN, Vendor, clean, CONSTITUTION_TO_PAN

C_HEADER, C_SECTION = "9DC3E6", "DDEBF7"
C_PASS, C_WARN, C_FAIL, C_NA, C_ONLINE = "C6E0B4", "FFE699", "F4B183", "D9D9D9", "E4DFEC"
FILL = {PASS: C_PASS, WARN: C_WARN, FAIL: C_FAIL, NA: C_NA,
        "APPROVED": C_PASS, "REVIEW": C_WARN, "REJECT / FIX": C_FAIL,
        "Yes": C_FAIL, "No": C_PASS, "Review": C_WARN}
thin = Side(style="thin", color="A6A6A6")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

INPUT_COLUMNS = ["Sr No", "Vendor Code", "Vendor Name", "Constitution", "Authorised Person", "Email ID",
                 "Address", "State", "PAN", "GSTIN", "Udyam No"]
ALIASES = {
    "sr no": "Sr No", "s no": "Sr No", "sl no": "Sr No",
    "vendor code": "Vendor Code", "code": "Vendor Code",
    "vendor name": "Vendor Name", "vendor name (as per pan)": "Vendor Name", "name": "Vendor Name",
    "constitution": "Constitution", "type of entity": "Constitution",
    "authorised person": "Authorised Person", "authorized person": "Authorised Person",
    "contact person": "Authorised Person", "email id": "Email ID", "email": "Email ID", "e-mail": "Email ID",
    "address": "Address", "registered address": "Address",
    "pan": "PAN", "pan no": "PAN", "gstin": "GSTIN", "gst no": "GSTIN", "gstin/uin": "GSTIN",
    "udyam no": "Udyam No", "udyam registration no": "Udyam No", "udyam": "Udyam No",
    "udyam registration number": "Udyam No", "state": "State",
}


def fill(color):
    return PatternFill("solid", start_color=color, end_color=color)


def style_header(ws, row=1, color=C_HEADER):
    for c in ws[row]:
        if c.value is not None:
            c.fill = fill(color)
            c.font = Font(bold=True, color="1F3864")
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = BORDER


def autosize(ws, widths=None, default=16, maxw=60):
    for i, col in enumerate(ws.iter_cols(1, ws.max_column), start=1):
        letter = get_column_letter(i)
        if widths and letter in widths:
            ws.column_dimensions[letter].width = widths[letter]
            continue
        longest = max((len(str(c.value)) for c in col if c.value is not None), default=default)
        ws.column_dimensions[letter].width = min(max(10, longest + 2), maxw)


# ---------------------------------------------------------------- input
def read_input(path: str) -> list[Vendor]:
    wb = load_workbook(path, data_only=True)
    ws = wb["Vendors"] if "Vendors" in wb.sheetnames else wb.worksheets[0]
    header_row, mapping = None, {}
    for r in range(1, 11):
        vals = [clean(c.value).lower() for c in ws[r]]
        hits = {i: ALIASES[v] for i, v in enumerate(vals) if v in ALIASES}
        if "PAN" in hits.values():
            header_row, mapping = r, hits
            break
    if not header_row:
        raise ValueError("Could not find a header row containing 'PAN'. Use the template provided.")
    vendors = []
    for r in range(header_row + 1, ws.max_row + 1):
        row = {mapping[i]: ws.cell(r, i + 1).value for i in mapping}
        if not any(clean(x) for x in row.values()):
            continue
        vendors.append(Vendor(
            row=r, sr_no=clean(row.get("Sr No")), vendor_code=clean(row.get("Vendor Code")),
            name=clean(row.get("Vendor Name")), constitution=clean(row.get("Constitution")),
            auth_person=clean(row.get("Authorised Person")), email=clean(row.get("Email ID")),
            address=clean(row.get("Address")),
            pan=clean(row.get("PAN")).upper().replace(" ", ""),
            gstin=clean(row.get("GSTIN")).upper().replace(" ", ""),
            udyam=clean(row.get("Udyam No")).upper().replace(" ", ""),
            state=clean(row.get("State"))))
    return vendors


def create_template(path: str, sample: bool = True) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Vendors"
    ws.append(INPUT_COLUMNS)
    style_header(ws)
    if sample:
        from validators import gstin_check_digit
        ok = lambda g14: g14 + gstin_check_digit(g14)          # dummy GSTIN with correct check digit
        rows = [   # DUMMY data - each row demonstrates a different validation
            (1, "V001", "Ravi Kumar Sharma", "Proprietorship", "Ravi Kumar Sharma", "ravi.sharma@example.com",
             "Shop 12, Laxmi Road, Pune 411030", "Maharashtra", "ABCPS1234K", ok("27ABCPS1234K1Z"), "UDYAM-MH-26-0012345"),
            (2, "V002", "Shree Ganesh Traders", "Partnership Firm", "Sunil Joshi (Partner)", "accounts@ganeshtraders.example",
             "45 Market Yard, Gultekdi, Pune 411037", "Maharashtra", "AAKFS5678L", ok("27AAKFS5678L1Z"), "UDYAM-MH-26-0054321"),
            (3, "V003", "Pune Precision Tools Pvt Ltd", "Private Limited Company", "Anil Kulkarni (Director)", "finance@ppt.example.in",
             "Plot D-14, MIDC Bhosari, Pune 411026", "Maharashtra", "AADCP4321Q", ok("27AADCP4321Q1Z"), "UDYAM-MH-26-0098765"),
            (4, "V004", "Sunrise Packaging LLP", "LLP", "Meena Shah (Designated Partner)", "meena@sunrisepack.example",
             "GIDC Estate, Vatva, Ahmedabad 382445", "Gujarat", "ABPFS9876M", ok("24ABPFS9876M1Z"), "UDYAM-GJ-01-0011223"),
            (5, "V005", "Mahesh Patil", "Partnership Firm", "Mahesh Patil", "mahesh.patil@example",
             "Sr No 34, Hadapsar, Pune 411028", "Maharashtra", "AQKPP2468H", ok("27AQKPP2468H1Z"), ""),
            (6, "V006", "Deccan Logistics", "Proprietorship", "", "deccanlogistics@example.com",
             "Near Swargate Bus Stand, Pune", "Maharashtra", "ABCD1234E", ok("27ABCDE1234F1Z"), "MH12A0012345"),
            (7, "V007", "Ravi Kumar Sharma", "Proprietorship", "Ravi Kumar Sharma", "ravi.sharma@example.com",
             "Shop 12, Laxmi Road, Pune 411030", "Maharashtra", "ABCPS1234K", "", ""),
            (8, "V008", "Kaveri Agro Foods Limited", "Public Limited Company", "R. Narayan (CFO)", "cfo@kaveriagro.example.in",
             "No. 7, Peenya Industrial Area, Bengaluru 560058", "Karnataka", "AABCK1111R", "29AABCK1111R1Z0", "UDYAM-KR-03-0004567"),
            (9, "V009", "Om Sai Enterprises", "Proprietorship", "Sai Prasad", "",
             "Ring Road, Surat 395002", "Gujarat", "BXZPS7788C", ok("27AAKFS5678L1Z"), "UDYAM-MH-26-0076543"),
        ]
        for r in rows:
            ws.append(r)
    dv = DataValidation(type="list", formula1='"' + ",".join(k.title() if k not in ("HUF", "LLP", "AOP / BOI") else k
                                                             for k in CONSTITUTION_TO_PAN) + '"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("D2:D1000")
    for col in "ABCDEFGHIJK":
        for c in ws[col][1:]:
            c.border = BORDER
    autosize(ws, {"A": 7, "B": 12, "C": 30, "D": 24, "E": 28, "F": 30, "G": 42, "H": 14, "I": 13, "J": 18, "K": 22})
    ws.freeze_panes = "A2"

    n = wb.create_sheet("Instructions")
    notes = [
        "VENDOR REGISTRATION & VALIDATION - INPUT TEMPLATE",
        "",
        "1. Enter one vendor per row in sheet 'Vendors'. Do not change the header names.",
        "2. Vendor Name must be exactly as per PAN (used for PAN, GST & Udyam name matching).",
        "3. Authorised Person, Email ID and Address (with 6-digit PIN code) are checked offline; the PIN code is also compared with the GST principal place of business.",
        "4. GSTIN and Udyam No may be left blank for unregistered / non-MSME vendors.",
        "5. Udyam No format: UDYAM-MH-26-0012345 (old Udyog Aadhaar numbers are flagged).",
        "6. Constitution: choose from the drop-down list.",
        "",
        "Rows 1-8 contain dummy sample data for demonstration - replace with real vendor data.",
    ]
    for t in notes:
        n.append([t])
    n["A1"].font = Font(bold=True, size=13, color="1F3864")
    n["A1"].fill = fill(C_HEADER)
    n.column_dimensions["A"].width = 120
    wb.save(path)


# ---------------------------------------------------------------- output
REPORT_COLS = (
    INPUT_COLUMNS
    + ["Contact Details", "PAN Offline", "GST Offline", "Udyam Offline",
       "PAN Online", "PAN Status (Portal)", "PAN Name / Jurisdictional AO",
       "GST Online", "GST Legal Name", "GST Trade Name", "GSTIN Status", "GST Reg. Date", "GST Cancel Date",
       "GST Constitution", "Taxpayer Type",
       "Udyam Online", "Udyam Enterprise Name", "Major Activity", "Organisation Type",
       "Enterprise Type", "Classification Year", "Classification Date", "Date of Udyam Regn",
       "43B(h) / 37(2)(g) Applicable", "Overall Result", "Remarks / Action"]
)
ONLINE_START = None  # set below
STATUS_COLS = {"Contact Details", "PAN Offline", "GST Offline", "Udyam Offline", "PAN Online", "GST Online", "Udyam Online",
               "Overall Result", "43B(h) / 37(2)(g) Applicable"}


ONLINE_START = REPORT_COLS.index("PAN Online") + 1


def write_report(path: str, vendors: list[Vendor], remarks: dict | None = None, summary_text: str = "",
                 ai_used: str = "Rule-based") -> None:
    remarks = remarks or {}
    wb = Workbook()

    # ---------------- Summary
    s = wb.active
    s.title = "Summary"
    s["A1"] = "VENDOR REGISTRATION & VALIDATION REPORT"
    s["A1"].font = Font(bold=True, size=14, color="1F3864")
    s["A1"].fill = fill(C_HEADER)
    s.merge_cells("A1:F1")
    s["A2"] = f"Generated on {datetime.now():%d-%m-%Y %H:%M}   |   Vendors: {len(vendors)}   |   Remarks by: {ai_used}"
    s.append([])
    s.append(["Department", "PASS", "WARNING", "FAIL", "NOT PROVIDED", "Not run"])
    style_header(s, 4)
    for dept, label in (("GENERAL", "Contact details"), ("PAN", "PAN"), ("GST", "GSTIN"), ("UDYAM", "Udyam")):
        for stage in (("Offline",) if dept == "GENERAL" else ("Offline", "Online")):
            cnt = {PASS: 0, WARN: 0, FAIL: 0, NA: 0, "": 0}
            for v in vendors:
                cnt[v.status_of(dept, stage)] = cnt.get(v.status_of(dept, stage), 0) + 1
            s.append([f"{label} - {stage}", cnt[PASS], cnt[WARN], cnt[FAIL], cnt[NA], cnt[""]])
    res = {"APPROVED": 0, "REVIEW": 0, "REJECT / FIX": 0}
    for v in vendors:
        res[v.overall()] += 1
    s.append([])
    s.append(["Overall result", "APPROVED", "REVIEW", "REJECT / FIX"])
    style_header(s, s.max_row)
    s.append(["Vendors", res["APPROVED"], res["REVIEW"], res["REJECT / FIX"]])
    for r in s.iter_rows(min_row=5, max_row=s.max_row):
        for c in r:
            if c.value is not None:
                c.border = BORDER
    for col, st in zip("BCDE", (PASS, WARN, FAIL, NA)):
        for r in range(5, 12):
            if s[f"{col}{r}"].value:
                s[f"{col}{r}"].fill = fill(FILL[st])
    last = s.max_row
    for col, st in zip("BCD", ("APPROVED", "REVIEW", "REJECT / FIX")):
        s[f"{col}{last}"].fill = fill(FILL[st])
    if summary_text:
        s.append([])
        s.append(["Summary for the Partner / Client"])
        s.cell(s.max_row, 1).font = Font(bold=True, color="1F3864")
        s.cell(s.max_row, 1).fill = fill(C_SECTION)
        s.append([summary_text])
        s.merge_cells(start_row=s.max_row, start_column=1, end_row=s.max_row, end_column=8)
        s.cell(s.max_row, 1).alignment = Alignment(wrap_text=True, vertical="top")
        s.row_dimensions[s.max_row].height = 120
    s.append([])
    s.append(["Colour legend"])
    s.cell(s.max_row, 1).font = Font(bold=True)
    for st, txt in ((PASS, "Pass / verified"), (WARN, "Warning - review needed"), (FAIL, "Failed - field highlighted"),
                    (NA, "Not provided"), ("online", "Data fetched from government portal")):
        s.append([st.upper() if st != "online" else "PORTAL DATA", txt])
        s.cell(s.max_row, 1).fill = fill(FILL.get(st, C_ONLINE))
        s.cell(s.max_row, 1).border = BORDER
    autosize(s, {"A": 26, "B": 14, "C": 14, "D": 14, "E": 16, "F": 12})

    # ---------------- Validation Report (one row per vendor)
    ws = wb.create_sheet("Validation Report")
    ws.append(REPORT_COLS)
    style_header(ws)
    field_by_col = {"Vendor Name": "Vendor Name", "Constitution": "Constitution",
                    "Authorised Person": "Authorised Person", "Email ID": "Email ID", "Address": "Address",
                    "PAN": "PAN", "GSTIN": "GSTIN", "Udyam No": "Udyam No", "State": "State"}
    for v in vendors:
        p = (v.online.get("PAN") or {}).get("data") or {}
        g = (v.online.get("GST") or {}).get("data") or {}
        u = (v.online.get("UDYAM") or {}).get("data") or {}
        row = [v.sr_no, v.vendor_code, v.name, v.constitution, v.auth_person, v.email, v.address, v.state,
               v.pan, v.gstin, v.udyam,
               v.status_of("GENERAL", "Offline"), v.status_of("PAN", "Offline"), v.status_of("GST", "Offline"), v.status_of("UDYAM", "Offline"),
               v.status_of("PAN", "Online"), p.get("pan_status", ""), " | ".join(x for x in (p.get("name", ""), p.get("ao_details", "")) if x),
               v.status_of("GST", "Online"), g.get("legal_name", ""), g.get("trade_name", ""), g.get("status", ""),
               g.get("registration_date", ""), g.get("cancellation_date", ""), g.get("constitution", ""),
               g.get("taxpayer_type", ""),
               v.status_of("UDYAM", "Online"), u.get("enterprise_name", ""), u.get("major_activity", ""),
               u.get("organisation_type", ""), u.get("enterprise_type", ""), u.get("classification_year", ""),
               u.get("classification_date", ""), u.get("date_of_udyam_registration", ""),
               u.get("sec_43bh", ""), v.overall(), remarks.get(v.vendor_code or str(v.row), "")]
        ws.append(row)
        r = ws.max_row
        for ci, col in enumerate(REPORT_COLS, start=1):
            c = ws.cell(r, ci)
            c.border = BORDER
            c.alignment = Alignment(vertical="top", wrap_text=col in ("Remarks / Action", "GST Legal Name",
                                                                      "Udyam Enterprise Name"))
            if col in field_by_col:
                st = v.field_status(field_by_col[col])
                if st in (FAIL, WARN):                     # highlight the failed / doubtful field
                    c.fill = fill(FILL[st])
                    if st == FAIL:
                        c.font = Font(bold=True, color="9C0006")
            elif col in STATUS_COLS and c.value in FILL:
                c.fill = fill(FILL[c.value])
                c.alignment = Alignment(horizontal="center", vertical="top")
            elif ci > ONLINE_START and c.value not in (None, ""):
                c.fill = fill(C_ONLINE)
    # group header row above sections
    ws.insert_rows(1)
    idx = lambda name: REPORT_COLS.index(name) + 1
    sections = [(1, len(INPUT_COLUMNS), "VENDOR DATA (INPUT)"),
                (idx("Contact Details"), idx("Udyam Offline"), "OFFLINE VALIDATION"),
                (idx("PAN Online"), idx("GST Online") - 1, "PAN - ONLINE"),
                (idx("GST Online"), idx("Udyam Online") - 1, "GST - ONLINE"),
                (idx("Udyam Online"), idx("Overall Result") - 1, "UDYAM - ONLINE"),
                (idx("Overall Result"), len(REPORT_COLS), "RESULT")]
    for a, b, t in sections:
        ws.merge_cells(start_row=1, start_column=a, end_row=1, end_column=b)
        c = ws.cell(1, a, t)
        c.fill = fill(C_SECTION)
        c.font = Font(bold=True, color="1F3864")
        c.alignment = Alignment(horizontal="center")
    L = lambda name: get_column_letter(REPORT_COLS.index(name) + 1)
    autosize(ws, {"A": 6, "B": 10, "C": 30, "D": 20, "E": 24, "F": 26, "G": 36, "H": 13, "I": 13, "J": 18,
                  "K": 22, L("GST Legal Name"): 30, L("GST Trade Name"): 24, L("Udyam Enterprise Name"): 30,
                  L("Remarks / Action"): 60})
    ws.freeze_panes = "D3"
    ws.auto_filter.ref = f"A2:{get_column_letter(len(REPORT_COLS))}{ws.max_row}"

    # ---------------- Check-wise detail
    d = wb.create_sheet("Check Details")
    d.append(["Vendor Code", "Vendor Name", "Stage", "Department", "Field", "Check", "Result", "Message"])
    style_header(d)
    for v in vendors:
        for c in v.checks:
            d.append([v.vendor_code, v.name, c.stage, c.department, c.field, c.check, c.status, c.message])
            d.cell(d.max_row, 7).fill = fill(FILL.get(c.status, "FFFFFF"))
            for cell in d[d.max_row]:
                cell.border = BORDER
    autosize(d, {"B": 28, "F": 30, "H": 90})
    d.freeze_panes = "A2"
    d.auto_filter.ref = f"A1:H{d.max_row}"

    # ---------------- MSME register (enterprise type history)
    m = wb.create_sheet("MSME Register")
    m.append(["Vendor Code", "Vendor Name", "Udyam No", "Major Activity", "Classification Year",
              "Enterprise Type", "Classification Date", "NIC (2-digit)", "43B(h)/37(2)(g)", "Reason"])
    style_header(m)
    for v in vendors:
        u = (v.online.get("UDYAM") or {}).get("data")
        if not u:
            continue
        hist = u.get("enterprise_types") or [{}]
        for h in hist:
            m.append([v.vendor_code, v.name, v.udyam, u.get("major_activity", ""), h.get("classification_year", ""),
                      h.get("enterprise_type", ""), h.get("classification_date", ""),
                      ", ".join(u.get("nic_2digit", [])), u.get("sec_43bh", ""), u.get("sec_43bh_reason", "")])
            m.cell(m.max_row, 9).fill = fill(FILL.get(u.get("sec_43bh", ""), "FFFFFF"))
            for cell in m[m.max_row]:
                cell.border = BORDER
    if m.max_row == 1:
        m.append(["Run online Udyam validation to populate this register."])
    autosize(m, {"B": 28, "J": 70})

    # ---------------- Portal raw data (audit trail)
    a = wb.create_sheet("Portal Data")
    a.append(["Vendor Code", "Department", "Result", "Field", "Value"])
    style_header(a)
    for v in vendors:
        for dept, r in v.online.items():
            if not r.get("data"):
                a.append([v.vendor_code, dept, "Not verified" if r.get("ok") is None else "Not found", "error",
                          r.get("error", "")])
                continue
            for k, val in r["data"].items():
                if isinstance(val, list):
                    val = "; ".join(" ".join(str(x) for x in i.values()) if isinstance(i, dict) else str(i)
                                    for i in val)
                a.append([v.vendor_code, dept, "Found", k, str(val)])
    autosize(a, {"E": 80})
    for sh in wb.worksheets:                      # print-ready: landscape, fit to one page wide
        sh.page_setup.orientation = "landscape"
        sh.page_setup.paperSize = sh.PAPERSIZE_A4
        sh.sheet_properties.pageSetUpPr.fitToPage = True
        sh.page_setup.fitToWidth = 1
        sh.page_setup.fitToHeight = 0
    wb.save(path)
