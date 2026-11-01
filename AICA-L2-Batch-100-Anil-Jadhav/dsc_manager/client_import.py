"""Excel template for importing clients in bulk, and reading a filled-in template.

Uses openpyxl (pip install openpyxl). Only the app's own template is accepted:
the "Clients" sheet with the column headings below in its first row.
"""
from . import firm_info

# (heading in the template, field); * marks the columns that must be filled in.
COLUMNS = [
    ("DSC Holder Name *", "holder_name", 30),
    ("Mobile Number *", "mobile", 18),
    ("Firm/Company Name", "firm_name", 34),
    ("PAN", "pan", 14),
    ("Email", "email", 30),
    ("Remarks", "remarks", 34),
]
REQUIRED = ("holder_name", "mobile")
SHEET = "Clients"

INSTRUCTIONS = [
    "How to fill this template",
    "",
    "1. Enter one client (DSC holder) per row on the 'Clients' sheet, starting from row 2. "
    "Do not change or move the headings in row 1.",
    "2. DSC Holder Name and Mobile Number must be filled in. A row without either is not imported.",
    "3. Mobile Number: 10 digits starting with 6, 7, 8 or 9 (a +91 or 0 in front is fine). "
    "A row with an invalid mobile number is not imported.",
    "4. The same mobile number may be used for more than one DSC holder only if the names are different. "
    "A client already in the app with the same name and mobile number is skipped.",
    "5. PAN is optional. If given, it must be the individual DSC holder's PAN (4th character 'P'). "
    "A PAN already in the app is skipped; an invalid PAN is left out and the client imported without it.",
    "6. Firm/Company Name, Email and Remarks are optional.",
    "7. Save the file, then use Clients > Import from Excel. You will see what will be imported and what "
    "will be skipped (with the reason) before anything is saved.",
    "",
    "Example rows (type your own on the Clients sheet):",
]
EXAMPLES = [
    ["Rajesh Kumar Sharma", "9820012345", "Sharma Traders", "ABCPS1234K", "rajesh@example.com", "Proprietor"],
    ["Neha Sharma", "9820012345", "Sharma Traders", "", "", "Partner - same mobile, different name"],
]


class TemplateError(Exception):
    """The chosen file is not a usable client import template."""


def _openpyxl():
    try:
        import openpyxl
        return openpyxl
    except ImportError:
        raise TemplateError("Excel support is not installed. Install it with:  pip install openpyxl") from None


def make_template(path):
    openpyxl = _openpyxl()
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SHEET
    head_fill = PatternFill("solid", fgColor="1B2A41")
    for col, (heading, _, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col, value=heading)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[cell.column_letter].width = width
    for col in range(1, len(COLUMNS) + 1):  # whole columns as text, so Excel keeps mobiles and PANs as typed
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].number_format = "@"
    ws.freeze_panes = "A2"

    info = wb.create_sheet("Instructions")
    title = f"Client import template{' - ' + firm_info.FIRM_NAME if firm_info.FIRM_NAME else ''}"
    info.cell(row=1, column=1, value=title).font = Font(bold=True, size=13)
    for i, line in enumerate(INSTRUCTIONS, start=3):
        info.cell(row=i, column=1, value=line).font = Font(bold=(i == 3))
    start = 3 + len(INSTRUCTIONS) + 1
    for col, (heading, _, width) in enumerate(COLUMNS, start=1):
        cell = info.cell(row=start, column=col, value=heading)
        cell.font = Font(bold=True)
        info.column_dimensions[cell.column_letter].width = max(width, 18)
    for r, example in enumerate(EXAMPLES, start=start + 1):
        for col, value in enumerate(example, start=1):
            info.cell(row=r, column=col, value=value)
    info.column_dimensions["A"].width = 30
    wb.save(path)
    return path


def _key(heading):
    return "".join(ch for ch in str(heading or "").lower() if ch.isalnum())


def _text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # a mobile number Excel stored as a number
    return str(value).strip()


def read_rows(path):
    """Rows of a filled-in template: [(excel row number, {field: text}), ...]; empty rows are left out."""
    openpyxl = _openpyxl()
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise TemplateError(f"The file could not be opened as an Excel workbook:\n{exc}") from None
    try:
        if SHEET not in wb.sheetnames:
            raise TemplateError(f"This is not the client import template: it has no '{SHEET}' sheet.\n"
                                "Download the template from the Clients screen and fill that in.")
        rows = wb[SHEET].iter_rows(values_only=True)
        header = next(rows, None) or ()
        positions = {}
        wanted = {_key(heading): field for heading, field, _ in COLUMNS}
        for i, heading in enumerate(header):
            field = wanted.get(_key(heading))
            if field and field not in positions:
                positions[field] = i
        missing = [h for h, field, _ in COLUMNS if field in REQUIRED and field not in positions]
        if missing:
            raise TemplateError("This is not the client import template: column "
                                f"'{missing[0]}' was not found in row 1 of the '{SHEET}' sheet.")
        out = []
        for row_no, values in enumerate(rows, start=2):
            record = {field: _text(values[i]) if i < len(values) else "" for field, i in positions.items()}
            if any(record.values()):
                out.append((row_no, record))
        return out
    finally:
        wb.close()
