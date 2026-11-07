"""Excel, PDF and Tally CSV exports."""
import csv
import io

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..utils import inr, sanitize_cell

NAVY = "1E3A6E"
GOLD = "E8A020"
# Indian digit grouping in Excel
INR_FORMAT = '[>=10000000]##\\,##\\,##\\,##0.00;[>=100000]##\\,##\\,##0.00;##,##0.00'


def _sheet(workbook, title, client, subtitle, headers, rows, money_columns=(), total_row=None, first=False):
    sheet = workbook.active if first else workbook.create_sheet()
    sheet.title = title[:31]
    sheet["A1"] = sanitize_cell(f"{client.name} ({client.code})")
    sheet["A1"].font = Font(bold=True, size=14, color=NAVY)
    sheet["A2"] = sanitize_cell(subtitle)
    sheet["A2"].font = Font(color="6B7280")
    header_row = 4
    fill = PatternFill("solid", fgColor=NAVY)
    for col, header in enumerate(headers, 1):
        cell = sheet.cell(row=header_row, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    row_number = header_row
    for row in rows:
        row_number += 1
        for col, value in enumerate(row, 1):
            cell = sheet.cell(row=row_number, column=col, value=sanitize_cell(value))
            if col - 1 in money_columns:
                cell.number_format = INR_FORMAT
    if total_row:
        row_number += 1
        for col, value in enumerate(total_row, 1):
            cell = sheet.cell(row=row_number, column=col, value=sanitize_cell(value))
            cell.font = Font(bold=True)
            cell.border = Border(top=Side(style="thin", color=NAVY), bottom=Side(style="double", color=NAVY))
            if col - 1 in money_columns:
                cell.number_format = INR_FORMAT
    for col in range(1, len(headers) + 1):
        longest = max([len(str(headers[col - 1]))] + [len(str(r[col - 1])) for r in rows if r[col - 1] is not None])
        sheet.column_dimensions[get_column_letter(col)].width = min(max(longest + 3, 12), 48)
    sheet.freeze_panes = sheet.cell(row=header_row + 1, column=1)
    return sheet


def _save(workbook):
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def dashboard_xlsx(client, data):
    wb = Workbook()
    k = data["kpis"]
    _sheet(wb, "KPIs", client, "Current month", ["Measure", "Value"],
           [["Invoices this month", k["invoice_count"]], ["Total amount this month (Rs)", k["total_amount"]],
            ["Pending approvals", k["pending_approvals"]], ["Overdue payments (count)", k["overdue_count"]],
            ["Overdue payments (Rs)", k["overdue_amount"]]], first=True)
    _sheet(wb, "Monthly trend", client, "Last 12 months, including GST", ["Month", "Spend (Rs)"],
           [list(r) for r in zip(data["trend"]["labels"], data["trend"]["values"])], (1,),
           ["Total", sum(data["trend"]["values"])])
    _sheet(wb, "By category", client, "Last 12 months, including GST", ["Category", "Spend (Rs)"],
           [list(r) for r in zip(data["category"]["labels"], data["category"]["values"])], (1,),
           ["Total", sum(data["category"]["values"])])
    _sheet(wb, "Top vendors", client, "Last 12 months, including GST", ["Vendor", "Spend (Rs)"],
           [list(r) for r in zip(data["vendors"]["labels"], data["vendors"]["values"])], (1,))
    return _save(wb)


def cost_centre_xlsx(client, rows, unallocated, label):
    wb = Workbook()
    body = [["    " * r["depth"] + r["centre"].name, r["centre"].code, r["count"], r["own"], r["total"]] for r in rows]
    if unallocated["count"]:
        body.append(["Unallocated", "", unallocated["count"], unallocated["amount"], unallocated["amount"]])
    top_total = sum(r["total"] for r in rows if r["depth"] == 0) + unallocated["amount"]
    _sheet(wb, "Cost centres", client, f"Period: {label}. Taxable value, excluding GST.",
           ["Cost centre", "Code", "Invoices", "Own spend (Rs)", "With children (Rs)"], body, (3, 4),
           ["Total", "", sum(r[2] for r in body), None, top_total], first=True)
    return _save(wb)


def variance_xlsx(client, data, label):
    wb = Workbook()
    body = [[r["centre"].name if r["centre"] else "Unallocated", r["budget"], r["actual"], r["variance"],
             r["pct"] if r["pct"] is not None else "n/a", {"green": "Green", "amber": "Amber", "red": "Red"}.get(r["light"], "-")]
            for r in data["rows"]]
    t = data["totals"]
    sheet = _sheet(wb, "Budget vs actual", client, f"Period: {label}. Actual is taxable value, excluding GST.",
                   ["Cost centre", "Budget (Rs)", "Actual (Rs)", "Variance (Rs)", "Variance (%)", "Status"], body, (1, 2, 3),
                   ["Total", t["budget"], t["actual"], t["variance"], t["pct"] if t["pct"] is not None else "n/a", ""], first=True)
    colours = {"Green": "D1FAE5", "Amber": "FEF3C7", "Red": "FEE2E2"}
    for row in sheet.iter_rows(min_row=5, min_col=6, max_col=6):
        if row[0].value in colours:
            row[0].fill = PatternFill("solid", fgColor=colours[row[0].value])
    if data["commentary"]:
        start = sheet.max_row + 2
        sheet.cell(row=start, column=1, value="Commentary (rule-based)").font = Font(bold=True, color=NAVY)
        for offset, text in enumerate(data["commentary"], 1):
            sheet.cell(row=start + offset, column=1, value=sanitize_cell(text))
    l = data["labels"]
    _sheet(wb, "Period comparison", client, "Taxable value, excluding GST",
           ["Cost centre", l["this_month"], l["last_month"], l["this_quarter"], l["py_quarter"]],
           [[c["centre"].name, c["this_month"], c["last_month"], c["this_quarter"], c["py_quarter"]] for c in data["comparison"]],
           (1, 2, 3, 4))
    return _save(wb)


def aging_xlsx(client, data):
    wb = Workbook()
    buckets = list(data["buckets"])
    headers = ["Name"] + buckets + ["Total"]
    money = tuple(range(1, len(headers)))
    totals = data["totals"]
    total_row = ["Total"] + [totals[b] for b in buckets] + [totals["total"]]
    subtitle = f"As of {data['as_of'].strftime('%d-%m-%Y')}. Days past due date."
    for title, key, first in (("By vendor", "by_vendor", True), ("By cost centre", "by_centre", False)):
        _sheet(wb, title, client, subtitle, headers, [[r["name"]] + [r[b] for b in buckets] + [r["total"]] for r in data[key]],
               money, total_row, first=first)
    _sheet(wb, "MSMED 45-day", client, "Invoices to MSME vendors. MSMED Act s.15: pay within 45 days at most.",
           ["Vendor", "Invoice no", "Invoice date", "Age (days)", "45-day limit", "Days left", "Amount (Rs)", "State"],
           [[m["invoice"].display_vendor, m["invoice"].display_number, m["invoice"].display_date.strftime("%d-%m-%Y"), m["age"],
             m["limit_date"].strftime("%d-%m-%Y"), m["days_left"], m["amount"], m["state"].title()] for m in data["msme"]], (6,))
    return _save(wb)


def invoices_xlsx(client, invoices):
    wb = Workbook()
    rows = [[i.display_number, i.display_date.strftime("%d-%m-%Y") if i.display_date else "", i.display_vendor,
             i.final_gstin or i.ocr_gstin or "", i.expense_category or "", i.cost_centre.name if i.cost_centre else "",
             float(i.final_taxable_amount or 0), float(i.final_cgst or 0), float(i.final_sgst or 0), float(i.final_igst or 0),
             float(i.amount or 0), i.status.replace("_", " ").title()] for i in invoices]
    total = lambda col: sum(r[col] for r in rows)  # noqa: E731
    _sheet(wb, "Invoices", client, "Invoice register",
           ["Invoice no", "Date", "Vendor", "GSTIN", "Category", "Cost centre", "Taxable (Rs)", "CGST (Rs)", "SGST (Rs)", "IGST (Rs)", "Total (Rs)", "Status"],
           rows, (6, 7, 8, 9, 10), ["Total", "", "", "", "", "", total(6), total(7), total(8), total(9), total(10), ""], first=True)
    return _save(wb)


def tally_csv(invoices):
    """Tally-ready rows: Date, Ledger, Debit, Credit, Narration. Debits equal credits per invoice."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(["Date", "Ledger", "Debit", "Credit", "Narration"])
    for invoice in invoices:
        when = (invoice.final_invoice_date or invoice.invoice_date).strftime("%d-%m-%Y")
        narration = sanitize_cell(invoice.narration or f"Being invoice {invoice.display_number} of {invoice.display_vendor}")
        expense = sanitize_cell(invoice.gl_account or invoice.expense_category or "Purchases / Expenses")
        total, taxable = float(invoice.final_total_amount or 0), float(invoice.final_taxable_amount or 0)
        cgst, sgst, igst = (float(v or 0) for v in (invoice.final_cgst, invoice.final_sgst, invoice.final_igst))
        tds = invoice.tds_amount
        round_off = round(total - taxable - cgst - sgst - igst, 2)

        def line(ledger, debit=None, credit=None):
            writer.writerow([when, ledger, f"{debit:.2f}" if debit else "", f"{credit:.2f}" if credit else "", narration])

        line(expense, debit=taxable or total)
        for ledger, amount in (("Input CGST", cgst), ("Input SGST", sgst), ("Input IGST", igst)):
            if amount:
                line(ledger, debit=amount)
        if taxable and round_off > 0:
            line("Round Off", debit=round_off)
        elif taxable and round_off < 0:
            line("Round Off", credit=-round_off)
        line(sanitize_cell(invoice.display_vendor), credit=round(total - tds, 2))
        if tds:
            line(f"TDS Payable - {invoice.final_tds_section or 'Other'}", credit=tds)
    return buffer.getvalue()


class _DashboardPDF(FPDF):
    def header(self):
        self.set_fill_color(30, 58, 110)
        self.rect(0, 0, 210, 18, "F")
        self.set_xy(10, 4)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 14)
        self.cell(60, 6, "KnowTaxx")
        self.set_xy(10, 10)
        self.set_text_color(232, 160, 32)
        self.set_font("Helvetica", "", 7)
        self.cell(90, 5, "Knowledge Backed Innovative Solutions")
        self.set_y(24)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(107, 114, 128)
        self.cell(0, 6, f"KnowTaxx AP Suite | Page {self.page_no()}", align="C")


def _latin(text):
    return str(text).replace("₹", "Rs ").encode("latin-1", "replace").decode("latin-1")


def _money_pdf(value):
    return "Rs " + inr(value, symbol=False, decimals=0)


def dashboard_pdf(client, data, sla):
    pdf = _DashboardPDF()
    pdf.set_auto_page_break(True, margin=16)
    pdf.add_page()
    pdf.set_text_color(31, 41, 55)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 7, _latin(f"{client.name} ({client.code}) - AP Dashboard"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    k = data["kpis"]
    tiles = [("Invoices this month", str(k["invoice_count"])), ("Amount this month", _money_pdf(k["total_amount"])),
             ("Pending approvals", str(k["pending_approvals"])), ("Overdue payments", f"{k['overdue_count']} / {_money_pdf(k['overdue_amount'])}")]
    x, y = pdf.get_x(), pdf.get_y()
    for index, (label, value) in enumerate(tiles):
        pdf.set_xy(x + index * 47.5, y)
        pdf.set_fill_color(248, 249, 252)
        pdf.rect(x + index * 47.5, y, 45.5, 18, "F")
        pdf.set_fill_color(232, 160, 32)
        pdf.rect(x + index * 47.5, y, 1, 18, "F")
        pdf.set_xy(x + index * 47.5 + 2, y + 2)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(42, 4, label)
        pdf.set_xy(x + index * 47.5 + 2, y + 8)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 58, 110)
        pdf.cell(42, 6, _latin(value))
    pdf.set_xy(x, y + 22)

    def bars(title, labels, values):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 58, 110)
        pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        top = max(values) if values and max(values) else 1
        for label, value in zip(labels, values):
            if pdf.get_y() > 270:
                pdf.add_page()
            row_y = pdf.get_y()
            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(31, 41, 55)
            pdf.cell(55, 5, _latin(label)[:38])
            pdf.set_fill_color(30, 58, 110)
            pdf.rect(66, row_y + 1, max(0.3, 100 * value / top), 3, "F")
            pdf.set_xy(168, row_y)
            pdf.cell(32, 5, _latin(_money_pdf(value)), align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    bars("Monthly spend, last 12 months (incl. GST)", data["trend"]["labels"], data["trend"]["values"])
    bars("Spend by category", data["category"]["labels"], data["category"]["values"])
    bars("Top vendors by spend", data["vendors"]["labels"], data["vendors"]["values"])

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 58, 110)
    pdf.cell(0, 7, "Approval turnaround", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(31, 41, 55)
    average = f"{sla['avg_hours']} hours" if sla["avg_hours"] is not None else "not enough data"
    pdf.cell(0, 5, f"Average approval time: {average}.  Waiting over 24h: {sla['over_24']},  over 48h: {sla['over_48']},  over 72h: {sla['over_72']}.",
             new_x="LMARGIN", new_y="NEXT")
    return io.BytesIO(bytes(pdf.output()))
