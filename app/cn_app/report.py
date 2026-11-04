"""Excel workbook (and CSV / JSON) built from the database."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import tradebook
from .models import CHARGE_KEYS, CHARGE_LABELS
from .utils import ISSUER_TYPES, SECURITY_TYPES, decode_isin, default_asset_class

NAVY, TEAL, LIGHT, PALE = "1F3A5F", "2A7F8F", "EAF2F8", "F7FAFC"
HDR_FONT = Font(bold=True, color="FFFFFF", name="Calibri", size=10)
TITLE_FONT = Font(bold=True, size=14, color=NAVY, name="Calibri")
THIN = Side(style="thin", color="D0D7DE")
MONEY = "#,##,##0.00;[Red]-#,##,##0.00"
RUPEE = "#,##,##0;[Red]-#,##,##0"
QTY = "#,##,##0.####"


# --------------------------------------------------------------------------- data frames

def _master(store) -> dict:
    return {r["isin"]: r for r in store.query("SELECT * FROM scrip_master")}


def scrip_frame(store) -> pd.DataFrame:
    rows = store.query("SELECT s.*, n.cn_no, n.trade_date, n.settlement_date, n.broker, n.client_name, n.pan, n.ucc, "
                       "n.source_file FROM scrips s JOIN notes n ON n.id = s.note_id ORDER BY n.trade_date, n.cn_no, s.id")
    master = _master(store)
    out = []
    for r in rows:
        m, d = master.get(r["isin"], {}), decode_isin(r["isin"])
        basis = json.loads(r["basis"] or "{}")
        rec = {
            "Contract Note No": r["cn_no"], "Trade Date": r["trade_date"], "Settlement Date": r["settlement_date"],
            "Broker": r["broker"], "Client / Account": r["client_name"], "PAN": r["pan"], "UCC": r["ucc"],
            "Exchange": r["exchanges"], "ISIN": r["isin"], "Country": d["Country"],
            "Issuer Type (ISIN 3rd char)": d["Issuer Type"], "Security Type Code (ISIN 8-9)": d["Security Type Code"],
            "Security Type": d["Security Type"],
            "Asset Class": m.get("asset_class") or default_asset_class(r["isin"]),
            "Sub Category": m.get("sub_category") or "", "Industry": m.get("industry") or "",
            "Script": r["symbol"], "Name of Company": m.get("company_name") or r["name_on_note"] or "",
            "Side": r["side"], "Quantity": r["qty"], "Avg Gross Rate": r["gross"] / r["qty"] if r["qty"] else 0,
            "Gross Value": round(r["gross"], 2),
        }
        for k in CHARGE_KEYS:
            rec[CHARGE_LABELS[k]] = r[f"a_{k}"]
        rec.update({
            "Total Charges": r["total_charges"],
            "Net Value (exact)": r["net_exact"],
            "Net Cost / Proceeds (Rs)": r["net_rupees"],
            "Rounding (Rs)": r["rounding"],
            "Net Rate per Unit (Rs)": round(r["net_rupees"] / r["qty"], 4) if r["qty"] else 0,
            "Brokerage Basis": basis.get("brokerage", ""),
            "STT / Stamp Basis": basis.get("stt_stamp", ""),
            "Source File": r["source_file"],
            "_sid": r["id"], "_nid": r["note_id"],
        })
        out.append(rec)
    return pd.DataFrame(out)


def daily_frame(sf: pd.DataFrame) -> pd.DataFrame:
    if sf.empty:
        return sf
    keys = ["Trade Date", "PAN", "Client / Account", "ISIN", "Side"]
    first = ["Country", "Security Type Code (ISIN 8-9)", "Security Type", "Asset Class", "Sub Category",
             "Industry", "Script", "Name of Company"]
    sums = ["Quantity", "Gross Value", *[CHARGE_LABELS[k] for k in CHARGE_KEYS], "Total Charges",
            "Net Cost / Proceeds (Rs)"]
    agg = {**{c: "first" for c in first}, **{c: "sum" for c in sums},
           "Broker": lambda s: ", ".join(sorted(set(s))),
           "UCC": lambda s: ", ".join(sorted(set(s))),
           "Contract Note No": lambda s: ", ".join(sorted(set(s)))}
    d = sf.groupby(keys, sort=True).agg(agg).reset_index()
    d["Avg Gross Rate"] = d["Gross Value"] / d["Quantity"]
    d["Net Rate per Unit (Rs)"] = (d["Net Cost / Proceeds (Rs)"] / d["Quantity"]).round(4)
    order = ["Trade Date", "Client / Account", "PAN", "UCC", "Broker", "ISIN", *first, "Side", "Contract Note No",
             "Quantity", "Avg Gross Rate", "Gross Value", *[CHARGE_LABELS[k] for k in CHARGE_KEYS],
             "Total Charges", "Net Cost / Proceeds (Rs)", "Net Rate per Unit (Rs)"]
    return d[order]


def notes_frame(store) -> pd.DataFrame:
    rows = store.query(
        "SELECT n.*, (SELECT COUNT(*) FROM scrips s WHERE s.note_id=n.id) AS rows_, "
        "(SELECT COALESCE(SUM(qty),0) FROM scrips s WHERE s.note_id=n.id AND side='BUY') AS bq, "
        "(SELECT COALESCE(SUM(gross),0) FROM scrips s WHERE s.note_id=n.id AND side='BUY') AS bg, "
        "(SELECT COALESCE(SUM(qty),0) FROM scrips s WHERE s.note_id=n.id AND side='SELL') AS sq, "
        "(SELECT COALESCE(SUM(gross),0) FROM scrips s WHERE s.note_id=n.id AND side='SELL') AS sg "
        "FROM notes n ORDER BY trade_date, broker, cn_no")
    out = []
    for r in rows:
        net = r["net_amount"]
        rec = {"Contract Note No": r["cn_no"], "Trade Date": r["trade_date"], "Settlement Date": r["settlement_date"],
               "Settlement No": r["settlement_no"], "Broker": r["broker"], "Client / Account": r["client_name"],
               "PAN": r["pan"], "UCC": r["ucc"], "Script Rows": r["rows_"], "Buy Quantity": r["bq"],
               "Gross Purchase Value": round(r["bg"], 2), "Sell Quantity": r["sq"],
               "Gross Sale Value": round(r["sg"], 2)}
        for k in CHARGE_KEYS:
            rec[CHARGE_LABELS[k]] = r[k]
        rec.update({
            "Total Charges": round(sum(r[k] for k in CHARGE_KEYS), 2),
            "Net Amount (as printed)": abs(net),
            "Direction": "Payable by client (Dr)" if net >= 0 else "Receivable by client (Cr)",
            "Net Amount (Rs, rounded)": int(abs(net) + 0.5),
            "Reconciliation Diff": r["recon_diff"],
            "Status": "Reconciled" if abs(r["recon_diff"] or 0) <= 0.05 else "Check",
            "Combined Charges": "Yes" if r["combined_charges"] else "",
            "Format": r["format"], "Source File": r["source_file"], "Remarks": r["remarks"],
            "_nid": r["id"],
        })
        out.append(rec)
    return pd.DataFrame(out)


def recon_frame(nf: pd.DataFrame) -> pd.DataFrame:
    if nf.empty:
        return nf
    r = nf[["Contract Note No", "Trade Date", "Broker", "Client / Account", "Gross Purchase Value",
            "Gross Sale Value", "Total Charges"]].copy()
    r["Computed Net (Buy - Sell + Charges)"] = (r["Gross Purchase Value"] - r["Gross Sale Value"] + r["Total Charges"]).round(2)
    r["Printed Net (+ payable / - receivable)"] = nf.apply(
        lambda x: x["Net Amount (as printed)"] if x["Direction"].startswith("Payable") else -x["Net Amount (as printed)"], axis=1)
    r["Difference"] = (r["Computed Net (Buy - Sell + Charges)"] - r["Printed Net (+ payable / - receivable)"]).round(2)
    r["Status"] = nf["Status"]
    return r


def trades_frame(store) -> pd.DataFrame:
    rows = store.query("SELECT t.cn_no AS 'Contract Note No', t.trade_date AS 'Trade Date', t.broker AS Broker, "
                       "t.exchange AS Exchange, t.order_no AS 'Order No', t.order_time AS 'Order Time', "
                       "t.trade_no AS 'Trade No', t.trade_time AS 'Trade Time', t.symbol AS Script, t.isin AS ISIN, "
                       "t.side AS Side, t.qty AS Quantity, t.rate AS 'Gross Rate', "
                       "ROUND(t.qty * t.rate, 2) AS 'Gross Value', t.brokerage_per_unit AS 'Brokerage per Unit' "
                       "FROM trades t ORDER BY t.trade_date, t.cn_no, t.line_no")
    return pd.DataFrame(rows)


def master_frame(store) -> pd.DataFrame:
    rows = store.query("SELECT isin, symbol, company_name, industry, asset_class, sub_category, face_value, source "
                       "FROM scrip_master ORDER BY symbol")
    df = pd.DataFrame(rows, columns=["isin", "symbol", "company_name", "industry", "asset_class",
                                     "sub_category", "face_value", "source"])
    df["asset_class"] = [a or default_asset_class(i) for i, a in zip(df["isin"], df["asset_class"])]
    df.columns = ["ISIN", "Script", "Name of Company", "Industry", "Asset Class", "Sub Category",
                  "Face Value", "Source"]
    return df


# --------------------------------------------------------------------------- workbook

def _public(df):
    """Drop internal id columns (names starting with '_') before writing a file."""
    return df[[c for c in df.columns if not str(c).startswith("_")]] if len(df.columns) else df


def _sheet(wb, title, df, subtitle, money=(), rupee=(), qty=(), widths=None):
    df = _public(df)
    ws = wb.create_sheet(title)
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    ws["A2"] = subtitle
    ws["A2"].font = Font(italic=True, color="555555", size=9)
    hdr = 4
    for j, col in enumerate(df.columns, 1):
        c = ws.cell(row=hdr, column=j, value=col)
        c.font, c.fill = HDR_FONT, PatternFill("solid", fgColor=NAVY)
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        c.border = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)
    ws.row_dimensions[hdr].height = 42
    for i, row in enumerate(df.itertuples(index=False), hdr + 1):
        fill = PatternFill("solid", fgColor=PALE if i % 2 else "FFFFFF")
        for j, val in enumerate(row, 1):
            if isinstance(val, float) and pd.isna(val):
                val = None
            is_date = "Date" in df.columns[j - 1] and isinstance(val, str) and len(val) == 10 and val[4] == "-"
            if is_date:
                val = datetime.strptime(val, "%Y-%m-%d")
            c = ws.cell(row=i, column=j, value=val)
            if is_date:
                c.number_format = "DD-MM-YYYY"
            c.fill, c.border = fill, Border(bottom=THIN)
            c.font = Font(size=10)
            name = df.columns[j - 1]
            if name in money:
                c.number_format = MONEY
            elif name in rupee:
                c.number_format = RUPEE
            elif name in qty:
                c.number_format = QTY
    # totals row for money columns
    if len(df):
        tr = hdr + len(df) + 1
        ws.cell(row=tr, column=1, value="Total").font = Font(bold=True)
        for j, name in enumerate(df.columns, 1):
            if name in money or name in rupee:
                L = get_column_letter(j)
                c = ws.cell(row=tr, column=j, value=f"=SUBTOTAL(9,{L}{hdr + 1}:{L}{tr - 1})")
                c.font, c.number_format = Font(bold=True), (MONEY if name in money else RUPEE)
                c.fill = PatternFill("solid", fgColor=LIGHT)
    for j, name in enumerate(df.columns, 1):
        w = (widths or {}).get(name)
        if w is None:
            sample = [len(str(name)) * 0.6] + [len(str(v)) for v in df.iloc[:200, j - 1].tolist()]
            w = min(max(10, max(sample) + 2), 45)
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(row=hdr + 1, column=3)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{hdr}:{hdr}"
    if len(df.columns):
        ws.auto_filter.ref = f"A{hdr}:{get_column_letter(len(df.columns))}{hdr + len(df)}"
    return ws


def frames(store, pan: str | None = None, d_from: str | None = None, d_to: str | None = None) -> dict:
    """All report tables, optionally for one client (PAN) and a period (ISO dates, inclusive)."""
    nf, sf, tf = notes_frame(store), scrip_frame(store), trades_frame(store)

    def keep(df):
        if not len(df):
            return df
        m = pd.Series(True, index=df.index)
        if pan:
            m &= df["PAN"] == pan
        if d_from:
            m &= df["Trade Date"] >= d_from
        if d_to:
            m &= df["Trade Date"] <= d_to
        return df[m].reset_index(drop=True)

    if pan or d_from or d_to:
        nf, sf = keep(nf), keep(sf)
        if len(tf):
            tf = tf[tf["Contract Note No"].isin(set(nf["Contract Note No"]))].reset_index(drop=True)
    return {"notes": nf, "scrips": sf, "daily": daily_frame(sf), "trades": tf, "recon": recon_frame(nf)}


def build_workbook(store, path: Path, pan: str | None = None, d_from: str | None = None,
                   d_to: str | None = None) -> dict:
    fr = frames(store, pan, d_from, d_to)
    nf, sf, df_daily, tf = fr["notes"], fr["scrips"], fr["daily"], fr["trades"]
    mf = master_frame(store)
    rf = recon_frame(nf)
    tb = pd.DataFrame(tradebook.cross_check(store))
    log = pd.DataFrame(store.query("SELECT at AS 'Time', source AS 'Source', status AS 'Status', message AS 'Message' "
                                   "FROM import_log ORDER BY id"))
    charges = [CHARGE_LABELS[k] for k in CHARGE_KEYS]

    wb = Workbook()
    wb.remove(wb.active)
    _readme(wb, nf, sf, tf)
    _sheet(wb, "Contract Notes", nf, "One row per contract note with every levy as printed. Net amount reconciled to the note.",
           money=["Gross Purchase Value", "Gross Sale Value", *charges, "Total Charges", "Net Amount (as printed)",
                  "Reconciliation Diff"], rupee=["Net Amount (Rs, rounded)"], qty=["Buy Quantity", "Sell Quantity"])
    _sheet(wb, "Script by Note", sf, "One row per contract note, ISIN and side. Same-day BUY and SELL stay separate. "
           "Charges in paise; final Net Cost / Proceeds in whole rupees.",
           money=["Avg Gross Rate", "Gross Value", *charges, "Total Charges", "Net Value (exact)", "Rounding (Rs)",
                  "Net Rate per Unit (Rs)"], rupee=["Net Cost / Proceeds (Rs)"], qty=["Quantity"])
    _sheet(wb, "Daily Script Summary", df_daily, "One row per client, trade date, ISIN and side across all notes "
           "(average price). BUY and SELL never netted.",
           money=["Avg Gross Rate", "Gross Value", *charges, "Total Charges", "Net Rate per Unit (Rs)"],
           rupee=["Net Cost / Proceeds (Rs)"], qty=["Quantity"])
    _sheet(wb, "Trades", tf, "Every execution line exactly as printed on the contract note or annexure.",
           money=["Gross Rate", "Gross Value"], qty=["Quantity"])
    _sheet(wb, "Reconciliation", rf, "Gross purchase - gross sale + all levies must equal the printed net amount "
           "(tolerance 5 paise). Notes that fail are not saved.",
           money=["Gross Purchase Value", "Gross Sale Value", "Total Charges", "Computed Net (Buy - Sell + Charges)",
                  "Printed Net (+ payable / - receivable)", "Difference"])
    if not tb.empty:
        tb.columns = ["UCC", "Trade Date", "Exchange", "Trade ID", "Script", "ISIN", "Side", "Quantity", "Price",
                      "Status", "Contract Note No"]
        _sheet(wb, "Tradebook Check", tb, "Broker tradebook trades matched to contract-note trades by Trade ID. "
               "Tradebooks carry no charges and are never used for cost.", money=["Price"], qty=["Quantity"])
    _sheet(wb, "Scrip Master", mf, "Fill Name of Company, Industry, Asset Class and Sub Category, then import with: "
           "python main.py master <this file>. Existing rows are updated, never duplicated.",
           widths={"Name of Company": 40, "Industry": 28})
    codes = pd.DataFrame([{"Code": k, "Meaning": v, "Position": "ISIN characters 8-9"} for k, v in SECURITY_TYPES.items()] +
                         [{"Code": k, "Meaning": v, "Position": "ISIN character 3"} for k, v in ISSUER_TYPES.items()])
    _sheet(wb, "ISIN Codes", codes, "Code definitions used to decode every ISIN.")
    _sheet(wb, "Import Log", log, "Every file seen, with duplicates and errors.", widths={"Message": 70, "Source": 60})
    wb.save(path)
    return fr


def _readme(wb, nf, sf, tf):
    ws = wb.create_sheet("Read Me")
    ws.page_setup.orientation = "landscape"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 120
    ws["A1"] = "Contract Note Register"
    ws["A1"].font = Font(bold=True, size=16, color=NAVY)
    brokers = ", ".join(f"{b}: {n}" for b, n in nf.groupby("Broker").size().items()) if len(nf) else ""
    info = [
        ("Coverage", f"{len(nf)} contract notes ({brokers}); {len(sf)} script/side rows; {len(tf)} trade lines."),
        ("Reconciliation", "Every saved note satisfies: gross purchase - gross sale + all levies = printed net amount, "
                           "within 5 paise. Notes that fail are listed in the import log and not saved."),
        ("Same-day buy and sell", "Kept as separate BUY and SELL rows and never netted. The investor sells from holdings, "
                                  "so nothing is treated as speculative; all quantity goes to holdings / FIFO."),
        ("STT and stamp duty", "Allocated on the broker's own basis: for an ISIN bought and sold on the same note, the "
                               "matched quantity carries STT 0.025% on sell and stamp 0.003% on buy; the rest carries "
                               "delivery rates (STT 0.1% both sides, stamp 0.015% on buy). Statutory amounts are used as "
                               "weights and scaled to the printed totals. Per-scrip STT printed on the note is used directly."),
        ("Brokerage", "Taken from the per-unit brokerage on the note where shown; otherwise allocated by turnover."),
        ("Other levies", "Exchange, clearing, SEBI fees, IPF and other charges by turnover. GST in proportion to each "
                         "row's taxable charges (brokerage + exchange + clearing + SEBI + IPF)."),
        ("Rounding", "Each charge is kept in paise (largest-remainder rounding so totals tie). Final Net Cost / Proceeds "
                     "per row is in whole rupees and the rows add up to the note's net amount rounded to the rupee. "
                     "The Rounding (Rs) column shows the adjustment."),
        ("Duplicates", "Blocked at three levels: identical file (SHA-256), same broker + client + contract note number, "
                       "and the same exchange trade number on the same date under another note."),
        ("Kotak", "Kotak prints transaction charges + SEBI fees + IPF as one figure; it is shown under Exchange Txn "
                  "Charges and flagged in Contract Notes > Combined Charges."),
        ("Zerodha", "Exchange transaction charges include IPF as printed by Zerodha."),
        ("Company name / industry", "Filled from the Scrip Master. Complete that sheet (or import NSE EQUITY_L.csv) "
                                    "and re-run the report."),
    ]
    for i, (a, b) in enumerate(info, 3):
        ws.cell(row=i, column=1, value=a).font = Font(bold=True, color=TEAL)
        c = ws.cell(row=i, column=2, value=b)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = 15 * (len(b) // 105 + 1) + 4


def export_flat(frames: dict, out_dir: Path, fmt: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, df in frames.items():
        df = _public(df)
        p = out_dir / f"{name}.{fmt}"
        if fmt == "csv":
            df.to_csv(p, index=False)
        else:
            df.to_json(p, orient="records", indent=2, force_ascii=False)
        paths.append(p)
    return paths


def last_imported(store, pan: str | None = None) -> pd.DataFrame:
    """Person- and broker-wise: how far contract notes have been imported."""
    where, args = ("WHERE n.pan=?", (pan,)) if pan else ("", ())
    rows = store.query(
        "SELECT n.client_name, n.pan, n.broker, GROUP_CONCAT(DISTINCT n.ucc) ucc, COUNT(*) notes, "
        "MIN(n.trade_date) first_date, MAX(n.trade_date) last_date, MAX(n.imported_at) imported_at "
        f"FROM notes n {where} GROUP BY n.pan, n.broker ORDER BY n.client_name, n.broker", args)
    out = []
    for r in rows:
        last = store.query("SELECT cn_no FROM notes WHERE pan=? AND broker=? AND trade_date=? ORDER BY cn_no DESC",
                           (r["pan"], r["broker"], r["last_date"]))
        out.append({"Person": r["client_name"], "PAN": r["pan"], "Broker": r["broker"], "Client Code": r["ucc"],
                    "Imported up to (Trade Date)": r["last_date"],
                    "Last contract note": ", ".join(x["cn_no"] for x in last),
                    "From Date": r["first_date"], "Notes": r["notes"], "Last import on": (r["imported_at"] or "")[:16].replace("T", " ")})
    cols = ["Person", "PAN", "Broker", "Client Code", "Imported up to (Trade Date)", "Last contract note", "From Date",
            "Notes", "Last import on"]
    return pd.DataFrame(out, columns=cols)
