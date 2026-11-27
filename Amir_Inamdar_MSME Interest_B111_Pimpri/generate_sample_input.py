#!/usr/bin/env python3
"""
Generate Sample_MSME_Input.xlsx - a sample input file for the MSME Interest Calculator.

It deliberately mixes good rows with rows the validator must FLAG, so every feature
can be tried in the GUI:
    * the mandatory statutory test case (Rs.1,00,000 dated 01-04-2026, paid 30-06-2026)
    * paid within time, unpaid overdue, part payments (repeated invoice rows)
    * agreed credit days blank / 30 / 60 (capped at 45)
    * Medium enterprise and Trader (no Sec. 16 interest)
    * dates as real Excel dates, DD-MM-YYYY text, DD/MM/YYYY text and Excel serials
    * invalid date, zero amount, payment before invoice date (flagged, not dropped)

Usage:  python generate_sample_input.py [output.xlsx]
"""

import datetime as dt
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADERS = ["Party Name", "Invoice Number", "Invoice Date", "Invoice Amount",
           "Acceptance/Delivery Date", "Payment Date", "Amount Paid", "Agreed Credit Days",
           "MSE Category", "Udyam No."]

D = dt.date
ROWS = [
    # Mandatory test case: No agreement -> 3,576.47 | Agreement (days blank) -> 2,108.65
    ["Shree Ganesh Engineering", "SGE/001", D(2026, 4, 1), 100000, D(2026, 4, 1), D(2026, 6, 30), None,
     None, "Micro", "UDYAM-MH-26-0012345"],
    # Paid within 15 days
    ["Shree Ganesh Engineering", "SGE/014", D(2026, 5, 5), 45000, None, D(2026, 5, 15), 45000,
     30, "Micro", "UDYAM-MH-26-0012345"],
    # Unpaid, overdue up to As-on Date; agreed 30 days
    ["Krishna Packaging Pvt Ltd", "KP-2026-118", D(2026, 6, 10), 275000, D(2026, 6, 12), None, None,
     30, "Small", "UDYAM-GJ-01-0098765"],
    # Part payments: same Party + Invoice repeated, one row per payment
    ["Krishna Packaging Pvt Ltd", "KP-2026-131", D(2026, 7, 1), 500000, None, D(2026, 7, 20), 200000,
     45, "Small", "UDYAM-GJ-01-0098765"],
    ["Krishna Packaging Pvt Ltd", "KP-2026-131", D(2026, 7, 1), 500000, None, D(2026, 9, 30), 150000,
     45, "Small", "UDYAM-GJ-01-0098765"],
    # Agreed 60 days -> capped at 45 and flagged
    ["Om Sai Castings", "OSC/77", "15-03-2026", "1,25,000.00", "18-03-2026", "20-06-2026", None,
     60, "Micro", "UDYAM-KA-03-0045678"],
    # DD/MM/YYYY text dates, category not given
    ["Lakshmi Textiles", "LT/2026/09", "10/08/2026", 85000, "12/08/2026", "05/10/2026", 85000,
     None, None, None],
    # Excel serial dates (46113 = 01-04-2026, 46204 = 01-07-2026)
    ["Vardhman Tools", "VT-555", 46113, 60000, None, 46204, 60000, 15, "Micro", "UDYAM-PB-07-0011223"],
    # Medium enterprise -> Sec. 15-16 not applicable
    ["Bharat Heavy Fabricators", "BHF-901", D(2026, 2, 1), 900000, None, None, None,
     30, "Medium", "UDYAM-TN-02-0077889"],
    # Trader -> excluded by MoMSME OM 02-07-2021
    ["City Trading Co.", "CTC/45", D(2026, 3, 15), 150000, None, D(2026, 8, 31), None,
     None, "Trader", "UDYAM-DL-05-0033445"],
    # --- rows the validator must FLAG (kept, not dropped) ---
    ["Error Case – Bad Date", "ERR-1", "31-02-2026", 50000, None, None, None, None, "Micro", None],
    ["Error Case – Zero Amount", "ERR-2", D(2026, 4, 10), 0, None, None, None, None, "Small", None],
    ["Error Case – Payment Before Invoice", "ERR-3", D(2026, 5, 20), 40000, None, D(2026, 5, 1), 40000,
     None, "Micro", "UDYAM-MH-26-0099999"],
]

DATE_COLS = (3, 5, 6)      # 1-based
MONEY_COLS = (4, 7)
INR = r"[>=10000000]##\,##\,##\,##0.00;[>=100000]##\,##\,##0.00;##,##0.00"


def main(path: str = "Sample_MSME_Input.xlsx") -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Invoices"
    for c, h in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="C00000" if c <= 4 else "1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(c)].width = 34 if c == 1 else max(16, len(h) + 4)
    for r, row in enumerate(ROWS, start=2):
        for c, val in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            if c in DATE_COLS and isinstance(val, dt.date):
                cell.number_format = "DD-MM-YYYY"
            if c in MONEY_COLS and isinstance(val, (int, float)):
                cell.number_format = INR
    ws.freeze_panes = "A2"
    wb.save(path)
    print(f"Sample input written: {path} ({len(ROWS)} rows)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Sample_MSME_Input.xlsx")
