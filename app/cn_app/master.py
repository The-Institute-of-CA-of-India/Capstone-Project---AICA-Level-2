"""Scrip Master import and the opening-holdings template."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

ALIASES = {
    "isin": ["isin", "isin number", "isin no", "isin code"],
    "symbol": ["script", "symbol", "scrip", "scrip code", "security id"],
    "company_name": ["name of company", "company name", "security name", "issuer name", "name"],
    "industry": ["industry", "sector", "industry new name"],
    "asset_class": ["asset class", "instrument", "segment"],
    "sub_category": ["sub category", "subcategory", "category"],
    "face_value": ["face value", "face_value", "facevalue"],
}


def _read_any(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str)
    # our own report: the Scrip Master sheet has its header on row 4
    xl = pd.ExcelFile(path)
    sheet = "Scrip Master" if "Scrip Master" in xl.sheet_names else xl.sheet_names[0]
    raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str)
    hdr = next(i for i, row in raw.iterrows() if any(str(v).strip().lower() in ALIASES["isin"] for v in row.values))
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[hdr]]
    return df


def import_master(path: Path, store) -> int:
    df = _read_any(Path(path))
    cols = {str(c).strip().lower(): c for c in df.columns}
    pick = {k: next((cols[a] for a in names if a in cols), None) for k, names in ALIASES.items()}
    if not pick["isin"]:
        raise ValueError("No ISIN column found")
    rows = []
    for _, r in df.iterrows():
        rec = {k: (str(r[c]).strip() if c and pd.notna(r[c]) else "") for k, c in pick.items()}
        if rec.get("face_value"):
            try:
                rec["face_value"] = float(rec["face_value"])
            except ValueError:
                rec["face_value"] = ""
        rows.append(rec)
    return store.upsert_master(rows, f"Imported: {Path(path).name}")


OPENING_COLUMNS = [
    ("Holder Name", 28, "As per demat / PAN"),
    ("PAN", 13, "10 characters, e.g. ABCDE1234F"),
    ("Intermediary / Broker", 24, "Broker or DP through which held"),
    ("Date of Purchase", 14, "DD/MM/YYYY (original acquisition date for FIFO and holding period)"),
    ("ISIN", 15, "12 characters starting IN"),
    ("Script", 16, "Exchange symbol"),
    ("Name of Company", 32, "Full name"),
    ("Quantity", 11, "Number of units"),
    ("Total Cost (Rs)", 15, "Total cost including charges, in whole rupees"),
    ("Mode of Acquisition", 18, "Purchase / IPO / Rights / Bonus / Gift / Merger / Split"),
    ("FMV on 31-01-2018 (Rs per unit)", 18, "Only for grandfathered equity bought before 01-02-2018"),
    ("Remarks", 30, ""),
]


def opening_template(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Opening Holdings"
    ws["A1"] = "Opening Holdings Template"
    ws["A1"].font = Font(bold=True, size=14, color="1F3A5F")
    ws["A2"] = "One row per purchase lot (not per scrip) so FIFO uses the right dates. Do not change the header row."
    ws["A2"].font = Font(italic=True, size=9, color="555555")
    for j, (name, width, hint) in enumerate(OPENING_COLUMNS, 1):
        c = ws.cell(row=4, column=j, value=name)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3A5F")
        c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
        h = ws.cell(row=5, column=j, value=hint)
        h.font = Font(italic=True, size=8, color="777777")
        h.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[c.column_letter].width = width
    ws.row_dimensions[4].height = 36
    ws.row_dimensions[5].height = 40
    sample = ["RAMESH KUMAR HUF", "ABCDE1234F", "IIFL Capital Services", "15/06/2019", "INE002A01018",
              "RELIANCE", "Reliance Industries Ltd", 100, 125000, "Purchase", "", "Sample row - delete"]
    for j, v in enumerate(sample, 1):
        ws.cell(row=6, column=j, value=v).font = Font(color="999999", italic=True)
    dv = DataValidation(type="list", formula1='"Purchase,IPO,Rights,Bonus,Gift,Merger,Split,Inheritance"',
                        allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("J6:J5000")
    ws.freeze_panes = "A6"
    wb.save(path)
