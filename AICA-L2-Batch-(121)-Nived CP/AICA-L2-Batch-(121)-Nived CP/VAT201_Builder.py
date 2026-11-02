# -*- coding: utf-8 -*-
"""
===============================================================================
 UAE VAT 201 SCHEDULE BUILDER  (v3)
===============================================================================
 HOW TO RUN:  open this file in IDLE and press F5.

 1. Click "Browse VAT register(s)" - one file per entity (select several at once).
 2. For each entity click "Select TB..." and attach its trial balance for the period.
 3. Check the period, entity name and TRN. Everything else is auto-detected.
 4. Click "Generate VAT 201 workbooks".

 Output (one Excel workbook per entity)
 --------------------------------------
   VAT 201 Summary      - FTA layout, every line linked by formula to its schedule
   P&L & VAT Recon      - IFRS statement of profit or loss, GL by GL:
                            Per TB (from the trial balance) | Per VAT register |
                            Discrepancy | Standard | RCM | Import | Out of scope |
                            Total | Check | VAT columns
                          P&L amounts come from the TB; the VAT split comes from the
                          VAT register. Everything is a SUMIF / SUMIFS on the data tabs.
   1a ... 10, Out of Scope - one supporting schedule per VAT 201 box
   VAT Data / TB Data   - the VAT register lines and the trial balance used
   Checks & Exceptions  - control totals and lines that need your review

 Missing libraries (pandas, numpy, openpyxl, xlrd) are installed automatically
 the first time you run the script.
===============================================================================
"""
import sys
import subprocess
import importlib
import os
import re
import datetime as dt
from collections import OrderedDict

# ----------------------------------------------------------------------------
# 0. Install missing libraries automatically
# ----------------------------------------------------------------------------
REQUIRED = [("pandas", "pandas", True), ("numpy", "numpy", True),
            ("openpyxl", "openpyxl", True), ("xlrd", "xlrd", False)]   # xlrd: old .xls files only


def _pip_install(pipname):
    base = [sys.executable, "-m", "pip", "install", pipname]
    for extra in ([], ["--user"], ["--break-system-packages"]):
        try:
            subprocess.check_call(base + extra)
            return True
        except Exception:
            continue
    return False


def _ensure_libs():
    for mod, pipname, mandatory in REQUIRED:
        try:
            importlib.import_module(mod)
        except ImportError:
            print("Installing %s ..." % pipname)
            ok = _pip_install(pipname)
            importlib.invalidate_caches()
            if not ok and mandatory:
                raise SystemExit("Could not install %s. Run:  python -m pip install %s" % (pipname, pipname))
            if not ok:
                print("Optional library %s not installed (only needed for .xls files)." % pipname)


_ensure_libs()

import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule, CellIsRule

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:
    tk = None

# ----------------------------------------------------------------------------
# 1. Settings you may want to change
# ----------------------------------------------------------------------------
VAT_RATE = 0.05
TOLERANCE = 0.10               # AED tolerance when testing VAT = 5% x net
IMPORT_ALSO_IN_BOX9 = True     # only used when "Goods imported - Box 6" mode is chosen
CALC_RCM_VAT_IF_ZERO = True    # RCM lines with no VAT amount -> compute 5% of net
TB_AUTO_SIGN = True             # check the TB sign vs the VAT register (income / expense GLs separately)
PL_START_DIGIT = 4              # GL codes starting 1-3 = balance sheet, 4 and above = P&L (None = off)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
GL_MAP_FILE = os.path.join(SCRIPT_DIR, "GL_IFRS_Mapping.xlsx")
TICK = "\u2713"

# ----------------------------------------------------------------------------
# 2. Constants
# ----------------------------------------------------------------------------
T_STD = "Standard Rated 5%"
T_ZERO = "Zero Rated 0%"
T_EXEMPT = "Exempt"
T_RCM = "Reverse Charge (RCM)"
T_IMPORT = "Import"
T_OOS = "Out of Scope / No VAT"
TREATMENTS = [T_STD, T_ZERO, T_EXEMPT, T_RCM, T_IMPORT, T_OOS]

IMPORT_MODES = OrderedDict([
    ("Not reported in VAT 201 - flag for review (as in my sample)", "not_reported"),
    ("Reverse charge - Box 3 and Box 10 (5% self-assessed)", "rcm"),
    ("Goods imported - Box 6 and Box 9", "box6"),
])

EMIRATES = OrderedDict([("Abu Dhabi", "1a"), ("Dubai", "1b"), ("Sharjah", "1c"),
                        ("Ajman", "1d"), ("Umm Al Quwain", "1e"),
                        ("Ras Al Khaimah", "1f"), ("Fujairah", "1g")])

BOX_INFO = OrderedDict([
    ("1a", ("1a Abu Dhabi", "Standard Rated Supplies in Abu Dhabi")),
    ("1b", ("1b Dubai", "Standard Rated Supplies in Dubai")),
    ("1c", ("1c Sharjah", "Standard Rated Supplies in Sharjah")),
    ("1d", ("1d Ajman", "Standard Rated Supplies in Ajman")),
    ("1e", ("1e UAQ", "Standard Rated Supplies in Umm Al Quwain")),
    ("1f", ("1f RAK", "Standard Rated Supplies in Ras Al Khaimah")),
    ("1g", ("1g Fujairah", "Standard Rated Supplies in Fujairah")),
    ("3", ("3 RCM Output", "Supplies subject to the reverse charge provisions")),
    ("4", ("4 Zero Rated", "Zero Rated Supplies")),
    ("5", ("5 Exempt", "Exempt Supplies")),
    ("6", ("6 Imports", "Goods imported into the UAE")),
    ("9", ("9 Std Rated Expenses", "Standard Rated Expenses")),
    ("10", ("10 RCM Input", "Supplies subject to the reverse charge provisions")),
    ("OOS", ("Out of Scope", "Out of scope supplies")),
])

# rows on the VAT 201 summary sheet
SUM_OFF = 4                      # rows used by the A1:A3 header + blank row above the summary
SUMROW = {k: v + SUM_OFF for k, v in {"1a": 8, "1b": 9, "1c": 10, "1d": 11, "1e": 12, "1f": 13, "1g": 14,
                                      "3": 16, "4": 17, "5": 18, "6": 19, "9": 24, "10": 25, "OOS": 32}.items()}
SUMMARY = "VAT 201 Summary"
PLSHEET = "P&L & VAT Recon"
CHKSHEET = "Checks & Exceptions"

# IFRS P&L lines
L_REV = "Revenue"
L_COS = "Cost of sales"
L_OI = "Other income / (losses)"
L_OE = "Other expenses / (losses)"
L_SD = "Selling and distribution expenses"
L_GA = "General and administrative expenses"
L_UNC = "Unclassified (map in GL_IFRS_Mapping.xlsx)"
L_FI = "Finance income"
L_FC = "Finance costs"
L_TAX = "Income tax expense"
L_BS = "Balance sheet (not in P&L)"
IFRS_LINES = [L_REV, L_COS, L_OI, L_OE, L_SD, L_GA, L_UNC, L_FI, L_FC, L_TAX, L_BS]
MOVE_ON_DEBIT = {}   # {} = an income GL with a debit balance stays in its section and shows NEGATIVE.
#                       ({L_OI: L_OE, L_FI: L_FC} would move such GLs to an expense section instead)
OUTPUT_LINES = {L_REV, L_OI, L_FI}          # income-type lines (credit natural)
OUT_SECS = [L_REV, L_OI, L_FI]
IN_SECS = [L_COS, L_OE, L_SD, L_GA, L_UNC, L_FC, L_TAX, L_BS]

RULES = [
    (L_BS, r"fixed asset|property,? plant|capital work|cwip|accumulated dep|receivable|payable|prepaid|prepayment|"
           r"accru(al|ed)|inventory|stock in hand|loan (from|to)|share capital|retained|reserve|security deposit|"
           r"advance (to|from)|right.of.use|lease liabilit|input vat|output vat|vat (receivable|payable)|"
           r"cash (in|at) hand|petty cash|bank account|current account|intercompany|due (to|from)|suspense|clearing"),
    (L_FI, r"interest income|finance income|profit on deposit|bank interest received"),
    (L_FC, r"interest expense|finance cost|finance charge|loan interest|interest on (loan|lease)|interest paid"),
    (L_TAX, r"corporate tax|income tax|tax expense|deferred tax"),
    (L_COS, r"cost of (sales|revenue|goods|services)|direct cost|\(\s*direct\s*\)|subcontract|cogs|^purchases?\b|"
            r"project cost|freight in|customs duty"),
    (L_SD, r"marketing|advertis|promotion|sales commission|selling|distribution|freight out|exhibition|sponsorship"),
    (L_OI, r"other income|misc(ellaneous)? income|gain on|discount received|scrap sale|insurance claim"),
    (L_REV, r"revenue|sales|turnover|service income|service fee|consult(ing|ancy) (fee|income)|fee income|"
            r"commission income|rental income"),
    (L_GA, r"salar|wage|staff|bonus|rent|utilit|electric|water|telephone|mobile|internet|travel|flight|hotel|"
           r"accommodation|per diem|food|hospitality|transport|conveyance|fuel|lubricant|pantry|depreciation|"
           r"amortis|professional|legal|audit|insurance|repair|maintenance|office|stationery|printing|bank charge|"
           r"subscription|platform|software|licen[cs]e|visa|training|entertainment|vehicle|cleaning|security|"
           r"courier|postage|general|admin|expense|allowance|gratuity|end of service|recruit|medical|consumable|"
           r"forex|foreign exchange|exchange (gain|loss)|variance realized|variance realised"),
]

# ----------------------------------------------------------------------------
# 3. Reading & cleaning helpers
# ----------------------------------------------------------------------------


def _norm_header(c):
    return re.sub(r"\s+", " ", str(c)).strip()


def _csv_frame(path, header_row, limit=None):
    import csv
    rows = []
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
        sample = fh.read(8192)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except Exception:
            dialect = csv.excel
        for i, row in enumerate(csv.reader(fh, dialect)):
            rows.append(row)
            if limit and i + 1 >= limit:
                break
    width = max((len(r) for r in rows), default=0)
    rows = [[(c if c not in ("", None) else None) for c in r + [None] * (width - len(r))] for r in rows]
    if header_row is None:
        return pd.DataFrame(rows, dtype=object)
    hdr = [_norm_header(c) if c is not None else "Unnamed: %d" % i for i, c in enumerate(rows[header_row - 1])]
    return pd.DataFrame(rows[header_row:], columns=hdr, dtype=object)


def read_table(path, sheet=None, header_row=1):
    if path.lower().endswith((".csv", ".txt")):
        raw = _csv_frame(path, header_row)
    else:
        raw = pd.read_excel(path, sheet_name=sheet if sheet else 0, header=header_row - 1, dtype=object)
    raw.columns = [_norm_header(c) for c in raw.columns]
    keep = [c for c in raw.columns if not (c.lower().startswith("unnamed") and raw[c].isna().all())]
    return raw[keep]


def detect_header_row(path, sheet=None):
    try:
        if path.lower().endswith((".csv", ".txt")):
            peek = _csv_frame(path, None, limit=40)
        else:
            peek = pd.read_excel(path, sheet_name=sheet if sheet else 0, header=None, nrows=40, dtype=object)
        counts = peek.notna().sum(axis=1).values
        if len(counts):
            thr = 0.6 * counts.max()
            for i, c in enumerate(counts):
                if c >= thr and c >= 3:
                    return i + 1
    except Exception:
        pass
    return 1


def best_sheet(path):
    """Sheet with the most data (Excel only)."""
    try:
        xl = pd.ExcelFile(path)
        best, size = xl.sheet_names[0], -1
        for sh in xl.sheet_names:
            n = pd.read_excel(xl, sheet_name=sh, header=None, nrows=200, dtype=object).notna().sum().sum()
            if n > size:
                best, size = sh, n
        return best, xl.sheet_names
    except Exception:
        return None, []


def to_num(s):
    if s is None:
        return None
    if not pd.api.types.is_numeric_dtype(s):
        s = (s.astype(str).str.strip().str.replace(",", "", regex=False)
             .str.replace(r"^\((.*)\)$", r"-\1", regex=True))
        s = s.where(~s.isin(["", "nan", "None", "-", "NaT", "<NA>"]), np.nan)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def txt(s):
    if s is None:
        return None
    return s.fillna("").astype(str).str.strip().replace({"nan": "", "None": "", "NaT": ""})


def clean_code(s):
    return txt(s).str.replace(r"\.0$", "", regex=True)


def norm_emirate(val, default):
    v = str(val or "").lower()
    if not v or v == "nan":
        return default
    for key, pats in (("Abu Dhabi", ("abu", "auh")), ("Dubai", ("dubai", "dxb")),
                      ("Sharjah", ("sharjah", "shj")), ("Ajman", ("ajman", "ajm")),
                      ("Umm Al Quwain", ("umm", "uaq")), ("Ras Al Khaimah", ("ras", "rak")),
                      ("Fujairah", ("fuj",))):
        if any(p in v for p in pats):
            return key
    return default


def guess_treatment(code):
    c = str(code).lower().strip()
    if c in ("", "(blank)", "nan"):
        return T_OOS
    if "rcm" in c or "reverse" in c:
        return T_RCM
    if "import" in c or re.match(r"imp\b|imp[ _-]", c):
        return T_IMPORT
    if re.search(r"(?<!\d)0\s*%", c) or "zero" in c:
        return T_ZERO
    if "exempt" in c:
        return T_EXEMPT
    if any(k in c for k in ("out of scope", "outside", "oos", "no vat", "notax", "no tax", "non vat", "n/a",
                            "not applicable")):
        return T_OOS
    if "5" in c or "standard" in c or "std" in c or "vat" in c:
        return T_STD
    return T_OOS


# ----------------------------------------------------------------------------
# 4. GL -> IFRS classification (kept in GL_IFRS_Mapping.xlsx so you fix it once)
# ----------------------------------------------------------------------------


CODE_FALLBACK = {4: L_REV, 5: L_COS, 6: L_GA, 7: L_GA}     # used only when the GL name gives no clue


def classify_gl(code, name, acct, overrides):
    if overrides.get(code):
        return overrides[code]
    for line in IFRS_LINES:
        if acct and acct.strip().lower() == line.lower():
            return line
    m = re.match(r"^(\d)", str(code or ""))
    digit = int(m.group(1)) if (m and PL_START_DIGIT) else None
    if digit is not None and digit < PL_START_DIGIT:
        return L_BS                                  # e.g. 1xxxxx assets, 2xxxxx liabilities, 3xxxxx equity
    text = ("%s %s" % (name, acct)).lower()
    for line, pat in RULES:
        if line == L_BS and digit is not None:       # code says P&L - ignore balance sheet keywords
            continue
        if re.search(pat, text):
            return line
    if digit is not None and digit in CODE_FALLBACK:
        return CODE_FALLBACK[digit]
    return L_UNC


OVR_COL = "Your override (optional)"


def _read_gl_map(path):
    """GL code -> (name, override line). Old-format files (no override column) are ignored."""
    out = OrderedDict()
    if os.path.exists(path):
        try:
            m = pd.read_excel(path, dtype=object)
            if OVR_COL not in m.columns:
                print("Old-format %s found - it will be rebuilt (put corrections in the '%s' column)." % (path, OVR_COL))
                return out
            for _, r in m.iterrows():
                code = str(r.get("GL Code", "")).strip().replace(".0", "") if pd.notna(r.get("GL Code")) else ""
                line = str(r.get(OVR_COL, "")).strip() if pd.notna(r.get(OVR_COL)) else ""
                name = str(r.get("GL Name", "")) if pd.notna(r.get("GL Name")) else ""
                if code:
                    out[code] = (name, line if line in IFRS_LINES else "")
        except Exception as e:
            print("Could not read %s (%s) - ignoring." % (path, e))
    return out


def load_gl_overrides(path=None):
    return {k: v[1] for k, v in _read_gl_map(path or GL_MAP_FILE).items() if v[1]}


def save_gl_mapping(df, path=None):
    """Writes GL code | GL name | Auto classification | Your override. Only the override column is ever
    read back, so automatic rules can improve without old guesses getting stuck."""
    path = path or GL_MAP_FILE
    existing = _read_gl_map(path)
    rows = OrderedDict()
    for code, (name, ovr) in existing.items():
        rows[code] = [name, "", ovr]
    for code, sub in df.groupby("gl_code", sort=True):
        prev_ovr = rows.get(code, ["", "", ""])[2]
        rows[code] = [sub["gl_name"].iloc[0], sub["ifrs_auto"].iloc[0], prev_ovr]
    wb = Workbook()
    ws = wb.active
    ws.title = "GL Mapping"
    ws.append(["GL Code", "GL Name", "Auto classification", OVR_COL])
    for code in sorted(rows):
        ws.append([code, rows[code][0], rows[code][1], rows[code][2] or None])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="000000")
    for col, w in zip("ABCD", (14, 46, 44, 44)):
        ws.column_dimensions[col].width = w
    dv = DataValidation(type="list", formula1='"%s"' % ",".join(IFRS_LINES), allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("D2:D%d" % (len(rows) + 1))
    ws.freeze_panes = "A2"
    try:
        wb.save(path)
    except Exception as e:
        print("Could not update %s (%s)" % (path, e))


# ----------------------------------------------------------------------------
# 5. Data preparation
# ----------------------------------------------------------------------------


def prepare(raw, cfg):
    m = cfg["cols"]

    def col(k):
        c = m.get(k)
        return raw[c] if c and c in raw.columns else None

    d = pd.DataFrame(index=raw.index)
    ent = col("entity")
    d["entity"] = txt(ent) if ent is not None else cfg["entity"]
    d.loc[d["entity"] == "", "entity"] = cfg["entity"]
    dc = col("date")
    d["date"] = pd.to_datetime(dc, errors="coerce", dayfirst=True) if dc is not None else pd.NaT
    for k in ("voucher", "party", "party_trn", "gl_name", "acct_type", "vat_code", "vat_code2"):
        d[k] = txt(col(k)) if col(k) is not None else ""
    d["gl_code"] = clean_code(col("gl_code")) if col("gl_code") is not None else ""
    em = col("emirate")
    d["emirate"] = [norm_emirate(x, cfg["default_emirate"]) for x in (txt(em) if em is not None else [""] * len(d))]
    src = txt(col("source")).str.lower() if col("source") is not None else None
    is_sales = src.str.contains("sale|revenue", regex=True) if src is not None else None

    dc_mode = cfg["amount_mode"] == "dc"
    if dc_mode:
        d["_dr"] = to_num(col("debit")) if col("debit") is not None else 0.0
        d["_cr"] = to_num(col("credit")) if col("credit") is not None else 0.0
    else:
        d["_net"] = to_num(col("net"))
    vcol = col("vat")
    d["_v"] = to_num(vcol) if vcol is not None else 0.0
    if is_sales is not None:
        d["_sales"] = is_sales

    # GL name fallback (e.g. journal lines with no GL account name)
    blank = d["gl_name"] == ""
    d.loc[blank, "gl_name"] = d.loc[blank, "party"]

    # drop blank / report-total rows
    junk = (d["gl_code"] == "") & ((d["gl_name"] == "") | ((d["voucher"] == "") & d["date"].isna()))
    info = {"rows_in_file": int(len(d)), "dropped_blank": int(junk.sum()), "dropped_period": 0}
    d = d[~junk].copy()
    d.loc[d["gl_code"] == "", "gl_code"] = "N/A"

    if cfg.get("filter_period") and d["date"].notna().any():
        end = pd.Timestamp(cfg["period_to"]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        out = d["date"].notna() & ((d["date"] < pd.Timestamp(cfg["period_from"])) | (d["date"] > end))
        info["dropped_period"] = int(out.sum())
        d = d[~out].copy()

    # IFRS classification
    overrides = load_gl_overrides()
    first = d.groupby("gl_code").agg(n=("gl_name", lambda s: next((x for x in s if x), "")),
                                     a=("acct_type", "first"))
    names = {c: (r.n or "GL %s" % c) for c, r in first.iterrows()}
    d["gl_name"] = d["gl_code"].map(names)
    gl_line = {c: classify_gl(c, r.n, r.a, overrides) for c, r in first.iterrows()}
    gl_auto = {c: classify_gl(c, r.n, r.a, {}) for c, r in first.iterrows()}
    d["ifrs"] = d["gl_code"].map(gl_line)
    d["ifrs_auto"] = d["gl_code"].map(gl_auto)

    # signs (debit-positive base)
    if dc_mode:
        signed_dr = d["_dr"] - d["_cr"]
        vat_dr = d["_v"]
    else:
        mode = cfg["sign_mode"]
        if mode == "natural":
            sales = d["_sales"] if "_sales" in d.columns else d["ifrs"].isin(OUTPUT_LINES)
            mult = np.where(sales, -1.0, 1.0)
        elif mode == "debit_positive":
            mult = 1.0
        else:
            mult = -1.0
        signed_dr = d["_net"] * mult
        vat_dr = d["_v"] * mult
    d["signed_dr"] = signed_dr
    d["amt_pl"] = -signed_dr                          # credit positive
    if vcol is not None:
        if cfg["vat_follow_sign"]:
            sgn = np.sign(d["amt_pl"])
            d["vat_pl"] = np.where(sgn != 0, d["_v"].abs() * sgn, -vat_dr)
        else:
            d["vat_pl"] = -vat_dr
    else:
        d["vat_pl"] = 0.0

    # VAT treatment
    if cfg["cols"].get("vat_code"):
        keyed = d["vat_code"].where(d["vat_code"] != "", "(blank)")
        d["treat"] = keyed.map(lambda x: cfg["vat_map"].get(x, guess_treatment(x)))
    else:
        d["treat"] = np.where(d["vat_pl"] != 0, T_STD, T_OOS)
    if vcol is None:
        d["vat_pl"] = np.where(d["treat"] == T_STD, d["amt_pl"] * VAT_RATE, 0.0)
    if cfg["import_mode"] == "rcm":
        d.loc[d["treat"] == T_IMPORT, "treat"] = T_RCM
    info["rcm_vat_calculated"] = 0
    if CALC_RCM_VAT_IF_ZERO:
        mk = (d["treat"] == T_RCM) & (d["vat_pl"] == 0)
        d.loc[mk, "vat_pl"] = d.loc[mk, "amt_pl"] * VAT_RATE
        info["rcm_vat_calculated"] = int(mk.sum())

    # side of the VAT return
    if "_sales" in d.columns:
        d["side"] = np.where(d["_sales"], "Output", "Input")
    else:
        d["side"] = np.where(d["ifrs"].isin(OUTPUT_LINES), "Output", "Input")
        bs = d["ifrs"] == L_BS
        d.loc[bs, "side"] = np.where(d.loc[bs, "amt_pl"] > 0, "Output", "Input")

    # presentation signs for the P&L (income +, expenses +, balance sheet debit +)
    mpres = np.where(d["ifrs"].isin(OUTPUT_LINES), 1.0, -1.0)
    d["pres"] = mpres * d["amt_pl"]
    d["vpres"] = mpres * d["vat_pl"]
    d = d.drop(columns=[c for c in d.columns if c.startswith("_")])
    return d, info


def explode_boxes(df, cfg):
    mode = cfg["import_mode"]
    recs = []
    for r in df.itertuples():
        t, amt, vat = r.treat, r.amt_pl, r.vat_pl
        pn, pv = -amt, -vat
        if t == T_RCM:
            recs.append(("3", r.Index, pn, pv))
            recs.append(("10", r.Index, pn, pv))
        elif t == T_IMPORT:
            if mode == "box6":
                recs.append(("6", r.Index, pn, pv))
                if IMPORT_ALSO_IN_BOX9:
                    recs.append(("9", r.Index, pn, pv))
        elif r.side == "Output":
            if t == T_STD:
                recs.append((EMIRATES[r.emirate], r.Index, amt, vat))
            elif t == T_ZERO:
                recs.append(("4", r.Index, amt, vat))
            elif t == T_EXEMPT:
                recs.append(("5", r.Index, amt, vat))
            elif t == T_OOS:
                recs.append(("OOS", r.Index, amt, vat))
        elif t == T_STD:
            recs.append(("9", r.Index, pn, pv))
    bx = pd.DataFrame(recs, columns=["box", "idx", "net", "vat"])
    keep = ["date", "voucher", "party", "party_trn", "gl_code", "gl_name", "vat_code", "treat", "ifrs"]
    return bx.merge(df[keep], left_on="idx", right_index=True, how="left")


def find_exceptions(df, cfg):
    ex = []

    def add(mask, issue, comment=None):
        for r in df[mask].itertuples():
            ex.append([issue, r.date, r.voucher, r.party, r.gl_code, r.gl_name, r.vat_code,
                       r.pres, r.vpres, comment])
    exp = df["pres"] * VAT_RATE
    stdlike = df["treat"].isin([T_STD, T_RCM])
    add(stdlike & ((df["vpres"] - exp).abs() > TOLERANCE) & (df["pres"] != 0), "VAT is not 5% of net amount")
    add(df["treat"].isin([T_ZERO, T_EXEMPT, T_OOS]) & (df["vpres"].abs() > 0.005),
        "VAT amount on a Zero / Exempt / Out-of-scope line")
    if cfg["cols"].get("vat_code2") and cfg["cols"].get("vat_code"):
        a = df["vat_code"].replace("", "(blank)")
        b = df["vat_code2"].replace("", "(blank)")
        add(a != b, "Tax group and tax code differ - confirm treatment",
            "Treated using the tax group column")
    if cfg["cols"].get("party_trn"):
        add((df["treat"] == T_STD) & (df["side"] == "Input") & (df["vpres"].abs() > 0.005) & (df["party_trn"] == ""),
            "Input VAT claimed but supplier TRN is missing")
    if cfg["import_mode"] == "not_reported":
        add(df["treat"] == T_IMPORT, "Import-tagged line is NOT reported in VAT 201",
            "Foreign supplier? RCM (Box 3 & 10) may apply")
    add(df["ifrs"] == L_UNC, "GL not classified to an IFRS P&L line", "Edit GL_IFRS_Mapping.xlsx")
    add(df["date"].isna(), "Missing / invalid date")
    add(df["gl_code"] == "N/A", "Missing GL code")
    return ex


# ----------------------------------------------------------------------------
# 5b. Trial balance preparation
# ----------------------------------------------------------------------------


def prepare_tb(raw, cfg):
    """Trial balance -> DataFrame(gl_code, gl_name, net_dr) with one row per GL (debit positive)."""
    m = cfg["tb_cols"]

    def col(k):
        c = m.get(k)
        return raw[c] if c and c in raw.columns else None

    code = clean_code(col("tb_code")) if col("tb_code") is not None else None
    if code is None:
        raise ValueError("The trial balance has no GL code column - map it under 'Advanced'.")
    name = txt(col("tb_name")) if col("tb_name") is not None else pd.Series([""] * len(raw), index=raw.index)
    if cfg["tb_mode"] == "dc":
        dr = to_num(col("tb_debit")) if col("tb_debit") is not None else 0.0
        cr = to_num(col("tb_credit")) if col("tb_credit") is not None else 0.0
        if hasattr(cr, "lt") and (cr < 0).any() and not (cr > 0).any():
            net = dr + cr                 # credit column already holds credits as negative numbers
        else:
            net = dr - cr
    else:
        net = to_num(col("tb_net"))
        if cfg["tb_sign"] == "credit_positive":
            net = -net
    d = pd.DataFrame({"gl_code": code, "gl_name": name, "net_dr": net})
    d = d[(d["gl_code"] != "") & d["gl_code"].str.match(r"^[A-Za-z0-9]")].copy()
    g = d.groupby("gl_code", sort=True).agg(gl_name=("gl_name", lambda s: next((x for x in s if x), "")),
                                            net_dr=("net_dr", "sum")).reset_index()
    g["net_raw"] = g["net_dr"]                      # balance exactly as read from the file
    g["flipped"] = False
    return g


def calibrate_tb_signs(tb, df, ifmap):
    """Check the TB sign against the VAT register separately for income GLs and for expense GLs.
    The convention expected is debit +ve / credit -ve. If a group only matches the register with the
    opposite sign, that group is flipped. Returns (tb, {"income": bool, "expense": bool})."""
    flags = {"income": False, "expense": False}
    if not TB_AUTO_SIGN:
        return tb, flags
    reg = df.groupby("gl_code")["signed_dr"].sum()
    tb = tb.copy()
    tb["_cls"] = tb["gl_code"].map(lambda c: "income" if ifmap.get(c) in OUTPUT_LINES
                                   else ("bs" if ifmap.get(c) == L_BS else "expense"))
    t = tb.set_index("gl_code")["net_dr"]
    for cls in ("income", "expense"):
        common = [c for c in tb.loc[tb["_cls"] == cls, "gl_code"] if c in reg.index and abs(reg[c]) > 1.0]
        if not common:
            continue
        err_same = sum(abs(t[c] - reg[c]) for c in common)
        err_flip = sum(abs(t[c] + reg[c]) for c in common)
        if err_flip < 0.5 * err_same:
            m = tb["_cls"] == cls
            tb.loc[m, "net_dr"] = -tb.loc[m, "net_dr"]
            tb.loc[m, "flipped"] = True
            flags[cls] = True
    return tb.drop(columns=["_cls"]), flags


def reclass_by_balance(df, gl_table, tb):
    """An 'Other income' / 'Finance income' GL that has a DEBIT balance is presented as an expense
    (Other expenses / Finance costs) so every figure on the P&L is an absolute positive number and the
    profit formulas subtract it. The balance is taken from the TB when available, else the VAT register."""
    reg = df.groupby("gl_code")["signed_dr"].sum()
    tbn = dict(zip(tb["gl_code"], tb["net_dr"])) if tb is not None else {}
    moved = {}
    for x in gl_table.itertuples():
        if x.ifrs in MOVE_ON_DEBIT:
            net = tbn[x.gl_code] if x.gl_code in tbn else float(reg.get(x.gl_code, 0.0))
            if net > 0.004:
                moved[x.gl_code] = MOVE_ON_DEBIT[x.ifrs]
    if not moved:
        return df, gl_table, moved
    gl_table = gl_table.copy()
    gl_table["ifrs"] = [moved.get(c, l) for c, l in zip(gl_table["gl_code"], gl_table["ifrs"])]
    df = df.copy()
    df["ifrs"] = [moved.get(c, l) for c, l in zip(df["gl_code"], df["ifrs"])]
    mp = np.where(df["ifrs"].isin(OUTPUT_LINES), 1.0, -1.0)
    df["pres"] = mp * df["amt_pl"]
    df["vpres"] = mp * df["vat_pl"]
    return df, gl_table, moved


def build_gl_table(df, tb):
    """All GLs of the entity: those in the VAT register plus those only in the trial balance."""
    ov = load_gl_overrides()
    rec = OrderedDict()
    for code, sub in df.groupby("gl_code", sort=True):
        rec[code] = [sub["gl_name"].iloc[0], sub["ifrs"].iloc[0], sub["ifrs_auto"].iloc[0], True]
    if tb is not None:
        for r in tb.itertuples():
            if r.gl_code not in rec:
                nm = r.gl_name or "GL %s" % r.gl_code
                rec[r.gl_code] = [nm, classify_gl(r.gl_code, nm, "", ov), classify_gl(r.gl_code, nm, "", {}), False]
    return pd.DataFrame([[k] + v for k, v in rec.items()],
                        columns=["gl_code", "gl_name", "ifrs", "ifrs_auto", "in_vat"])


# ----------------------------------------------------------------------------
# 6. Excel styling helpers
# ----------------------------------------------------------------------------
BLACK = PatternFill("solid", fgColor="111111")
REDF = PatternFill("solid", fgColor="C00000")
GREY = PatternFill("solid", fgColor="E7E6E6")
MID = PatternFill("solid", fgColor="BFBFBF")
LIGHT = PatternFill("solid", fgColor="F7F7F7")
INPUT = PatternFill("solid", fgColor="FFF8DC")
PINK = PatternFill("solid", fgColor="F8CBAD")
WHITE_B = Font(color="FFFFFF", bold=True)
BOLD = Font(bold=True)
thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
NEGATIVE_AS_MINUS = False     # False: negatives in brackets (1,234.00)   True: negatives with a minus sign -1,234.00
NUM = ('_(* #,##0.00_);_(* -#,##0.00_);_(* "-"??_);_(@_)' if NEGATIVE_AS_MINUS
       else '_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)')
DATEFMT = "dd/mm/yyyy"


def cell(ws, ref, value=None, bold=False, fill=None, font=None, fmt=None, border=True, align=None, wrap=False):
    c = ws[ref]
    if value is not None:
        c.value = value
    if font is not None:
        c.font = font
    elif bold:
        c.font = BOLD
    if fill is not None:
        c.fill = fill
    if fmt:
        c.number_format = fmt
    if border:
        c.border = BORDER
    if align or wrap:
        c.alignment = Alignment(horizontal=align, vertical="center", wrap_text=wrap)
    return c


def q(sheet):
    return "'%s'" % sheet


TRN_LEN = 15


def is_valid_trn(value):
    """UAE TRN: exactly 15 digits, numbers only."""
    return bool(re.fullmatch(r"[0-9]{%d}" % TRN_LEN, str(value or "").strip()))


def safe_name(s):
    return re.sub(r'[\\/*?:"<>|]', "_", str(s)).strip()[:60] or "Entity"


def band(ws, row, c1, c2, text, fill=None, font=None, center=False, border=False):
    """Coloured band across columns c1..c2 WITHOUT merging cells (centre = 'centre across selection')."""
    for c in range(c1, c2 + 1):
        x = ws.cell(row=row, column=c)
        if fill is not None:
            x.fill = fill
        if border:
            x.border = BORDER
        x.alignment = Alignment(horizontal="centerContinuous" if center else "left", vertical="center")
    x = ws.cell(row=row, column=c1)
    x.value = text
    if font is not None:
        x.font = font


def title_block(ws, last_col, entity, period_txt, box_line):
    """A1 = company, A2 = VAT RETURN ANNEXURE FOR THE PERIOD .., A3 = box no. and description."""
    for c in range(1, last_col + 1):
        ws.cell(row=1, column=c).fill = BLACK
        ws.cell(row=3, column=c).border = Border(bottom=Side(style="medium", color="C00000"))
    ws["A1"] = str(entity).upper()
    ws["A1"].font = Font(bold=True, color="FFFFFF", size=15)
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28
    ws["A2"] = "VAT RETURN ANNEXURE FOR THE PERIOD %s" % period_txt.upper()
    ws["A2"].font = Font(bold=True, size=12)
    ws["A3"] = str(box_line).upper()
    ws["A3"].font = Font(bold=True, size=11, color="C00000")


def page_setup(ws, landscape=True):
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True


# ----------------------------------------------------------------------------
# 7. Supporting schedule for one VAT 201 box
# ----------------------------------------------------------------------------
NETC, VATC, GROSSC = "H", "I", "J"


def write_box_sheet(ws, key, rows, entity, period_txt):
    sheet, desc = BOX_INFO[key]
    title_block(ws, 10, entity, period_txt,
                ("Box %s - %s" % (key, desc)) if key != "OOS" else "Out of scope supplies")
    hdr = ["Date", "Voucher", "Party", "Party TRN", "GL Code", "GL Name", "Tax group", "Net Amount",
           "VAT Amount", "Gross"]
    for i, h in enumerate(hdr, 1):
        cell(ws, "%s5" % get_column_letter(i), h, font=WHITE_B, fill=BLACK, align="center")
    r0 = 6
    rows = rows.sort_values(["gl_code", "date", "voucher"], na_position="last")
    r = r0
    for x in rows.itertuples():
        cell(ws, "A%d" % r, None if pd.isna(x.date) else x.date.to_pydatetime(), fmt=DATEFMT)
        cell(ws, "B%d" % r, x.voucher)
        cell(ws, "C%d" % r, x.party)
        cell(ws, "D%d" % r, x.party_trn)
        cell(ws, "E%d" % r, x.gl_code)
        cell(ws, "F%d" % r, x.gl_name)
        cell(ws, "G%d" % r, x.vat_code)
        cell(ws, "H%d" % r, float(x.net), fmt=NUM)
        cell(ws, "I%d" % r, float(x.vat), fmt=NUM)
        cell(ws, "J%d" % r, "=H%d+I%d" % (r, r), fmt=NUM)
        r += 1
    last = max(r - 1, r0)
    tr = last + 1
    cell(ws, "A%d" % tr, "TOTAL", bold=True, fill=GREY)
    for c in "BCDEFG":
        cell(ws, "%s%d" % (c, tr), None, fill=GREY)
    for c in "HIJ":
        cell(ws, "%s%d" % (c, tr), "=SUM(%s%d:%s%d)" % (c, r0, c, last), bold=True, fill=GREY, fmt=NUM)
    for col, w in zip("ABCDEFGHIJ", (12, 18, 34, 18, 11, 38, 20, 16, 16, 16)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "C00000"
    page_setup(ws)
    return tr


# ----------------------------------------------------------------------------
# 8. VAT 201 summary (FTA layout)
# ----------------------------------------------------------------------------


def write_summary(ws, entity, trn, cfg, links):
    O = SUM_OFF
    ws.sheet_properties.tabColor = "111111"
    ws.sheet_view.showGridLines = False
    for col, w in zip("ABCDE", (10, 64, 20, 20, 20)):
        ws.column_dimensions[col].width = w
    period_txt = "%s TO %s" % (cfg["period_from"].strftime("%d/%m/%Y"), cfg["period_to"].strftime("%d/%m/%Y"))
    title_block(ws, 5, entity, period_txt, "VAT 201 Return Summary - Boxes 1 to 14")

    band(ws, 1 + O, 1, 5, "TAXPAYER INFORMATION", fill=BLACK, font=Font(bold=True, color="FFFFFF", size=13), center=True)
    ws.row_dimensions[1 + O].height = 24
    cell(ws, "A%d" % (2 + O), "LE Name", bold=True, fill=GREY)
    cell(ws, "B%d" % (2 + O), entity, bold=True, align="center")
    band(ws, 2 + O, 3, 5, "From %s" % cfg["period_from"].strftime("%d/%m/%Y"), fill=GREY, font=BOLD, center=True)
    cell(ws, "A%d" % (3 + O), "TRN", bold=True, fill=GREY)
    cell(ws, "B%d" % (3 + O), trn or "<enter TRN>", bold=True, align="center")
    band(ws, 3 + O, 3, 5, "To %s" % cfg["period_to"].strftime("%d/%m/%Y"), fill=GREY, font=BOLD, center=True)
    cell(ws, "A%d" % (4 + O), "Supporting schedules are in the tabs that follow (linked by formula)",
         font=Font(italic=True, color="595959"), border=False)
    for c in "AB":
        ws["%s%d" % (c, 4 + O)].border = Border(left=thin if c == "A" else None, top=thin, right=thin if c == "B" else None)
        ws["%s%d" % (c, 5 + O)].border = Border(left=thin if c == "A" else None, bottom=thin, right=thin if c == "B" else None)
    band(ws, 4 + O, 3, 5, "VAT 201 VAT return", fill=REDF, font=WHITE_B, center=True)
    band(ws, 5 + O, 3, 5, cfg["filing_date"].strftime("%d/%m/%Y"), font=BOLD, center=True)

    def section(r, title):
        band(ws, r + O, 1, 5, title, fill=REDF, font=WHITE_B, center=True)

    def header(r):
        for c, t in zip("ABCDE", ("Sr#", "Description", "(AED) Amount", "VAT Amount (AED)", "Adjustment (AED)")):
            cell(ws, "%s%d" % (c, r + O), t, font=WHITE_B, fill=BLACK, align="center")

    def line(r, sr, desc, key):
        rr = r + O
        cell(ws, "A%d" % rr, sr, bold=True, align="center")
        cell(ws, "B%d" % rr, desc)
        if key in links:
            sh, tr = links[key]
            cell(ws, "C%d" % rr, "=%s!%s%d" % (q(sh), NETC, tr), fmt=NUM)
            cell(ws, "D%d" % rr, "=%s!%s%d" % (q(sh), VATC, tr), fmt=NUM)
        else:
            cell(ws, "C%d" % rr, 0, fmt=NUM)
            cell(ws, "D%d" % rr, 0, fmt=NUM)
        cell(ws, "E%d" % rr, 0, fmt=NUM, fill=INPUT)

    def total(r, sr, first, last):
        rr = r + O
        cell(ws, "A%d" % rr, sr, bold=True, fill=MID, align="center")
        cell(ws, "B%d" % rr, "Totals", bold=True, fill=MID, align="center")
        for c in "CDE":
            cell(ws, "%s%d" % (c, rr), "=SUM(%s%d:%s%d)" % (c, first + O, c, last + O), bold=True, fill=MID, fmt=NUM)

    section(6, "VAT on Sales and All Other Outputs")
    header(7)
    for emi, k in EMIRATES.items():
        line(SUMROW[k] - O, k, BOX_INFO[k][1], k)
    line(15, 2, "Tax Refunds provided to Tourists under the Tax (Refunds for Tourists Scheme)", "2x")
    line(16, 3, BOX_INFO["3"][1], "3")
    line(17, 4, BOX_INFO["4"][1], "4")
    line(18, 5, BOX_INFO["5"][1], "5")
    line(19, 6, BOX_INFO["6"][1], "6")
    line(20, 7, "Adjustments to goods imported into the UAE", "7x")
    total(21, 8, 8, 20)
    section(22, "VAT on Expenses and All Other Inputs")
    header(23)
    line(24, 9, BOX_INFO["9"][1], "9")
    line(25, 10, BOX_INFO["10"][1], "10")
    total(26, 11, 24, 25)
    section(27, "Net VAT Position")
    for r0, sr, desc, f in ((28, 12, "Total Value of due tax for the period", "=D%d+E%d" % (21 + O, 21 + O)),
                            (29, 13, "Total Value of recoverable tax for the period", "=D%d+E%d" % (26 + O, 26 + O)),
                            (30, 14, "Payable tax for the period (Refund)", "=C%d-C%d" % (28 + O, 29 + O))):
        rr = r0 + O
        fill = MID if r0 == 30 else None
        cell(ws, "A%d" % rr, sr, bold=True, align="center", fill=fill)
        cell(ws, "B%d" % rr, desc, bold=(r0 == 30), fill=fill)
        cell(ws, "C%d" % rr, f, bold=(r0 == 30), fmt=NUM, fill=fill)
        cell(ws, "D%d" % rr, None, fill=fill)
        cell(ws, "E%d" % rr, None, fill=fill)
    cell(ws, "A%d" % (32 + O), None)
    cell(ws, "B%d" % (32 + O), "Out of scope supplies", bold=True)
    if "OOS" in links:
        sh, tr = links["OOS"]
        cell(ws, "C%d" % (32 + O), "=%s!%s%d" % (q(sh), NETC, tr), fmt=NUM)
    else:
        cell(ws, "C%d" % (32 + O), 0, fmt=NUM)
    ws["B%d" % (34 + O)] = ("Boxes 2 and 7 and the yellow Adjustment cells are for manual input. "
                            "Box 14: positive = payable to FTA, negative = refund.")
    ws["B%d" % (34 + O)].font = Font(italic=True, size=9, color="595959")
    page_setup(ws, landscape=False)


# ----------------------------------------------------------------------------
# 8b. VAT Data sheet (the input lines; the P&L reads from it with SUMIF / SUMIFS)
# ----------------------------------------------------------------------------
DATA_SHEET = "VAT Data"
DATA_R0 = 6


def write_data_sheet(ws, df, entity, period_txt):
    title_block(ws, 12, entity, period_txt,
                "VAT Data - voucher lines used (source of the P&L SUMIFs; income +, expenses +)")
    heads = ["Date", "Voucher", "Party", "Party TRN", "GL Code", "GL Name", "IFRS line", "Tax group",
             "VAT treatment", "VAT side", "Net amount (P&L basis)", "VAT amount (P&L basis)"]
    for i, h in enumerate(heads, 1):
        cell(ws, "%s5" % get_column_letter(i), h, font=WHITE_B, fill=BLACK, align="center", wrap=True)
    ws.row_dimensions[5].height = 32
    r = DATA_R0
    for x in df.itertuples():
        cell(ws, "A%d" % r, None if pd.isna(x.date) else x.date.to_pydatetime(), fmt=DATEFMT, border=False)
        for col, val in (("B", x.voucher), ("C", x.party), ("D", x.party_trn), ("E", x.gl_code), ("F", x.gl_name),
                         ("G", x.ifrs), ("H", x.vat_code), ("I", x.treat), ("J", x.side)):
            ws["%s%d" % (col, r)] = val
        ws["K%d" % r] = float(x.pres)
        ws["L%d" % r] = float(x.vpres)
        ws["K%d" % r].number_format = NUM
        ws["L%d" % r].number_format = NUM
        r += 1
    last = max(r - 1, DATA_R0)
    for col, w in zip("ABCDEFGHIJKL", (12, 18, 34, 18, 11, 38, 30, 14, 24, 10, 20, 20)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A6"
    ws.auto_filter.ref = "A5:L%d" % last
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "808080"
    return {"sheet": DATA_SHEET, "r0": DATA_R0, "r1": last}


TB_SHEET = "TB Data"


def write_tb_sheet(ws, tb, entity, period_txt):
    title_block(ws, 8, entity, period_txt,
                "TB Data - trial balance for the period (debit +ve, credit -ve; source of 'Per TB' on the P&L tab)")
    heads = ["GL Code", "GL Name", "Debit", "Credit", "Balance used\n(Dr + / Cr -)", "Balance as read\nfrom TB file",
             "IFRS line", "Sign adjusted?"]
    for i, h in enumerate(heads, 1):
        cell(ws, "%s5" % get_column_letter(i), h, font=WHITE_B, fill=BLACK, align="center", wrap=True)
    ws.row_dimensions[5].height = 34
    r = DATA_R0
    for x in tb.itertuples():
        ws["A%d" % r] = x.gl_code
        ws["B%d" % r] = x.gl_name
        ws["C%d" % r] = float(max(x.net_dr, 0))
        ws["D%d" % r] = float(max(-x.net_dr, 0))
        ws["E%d" % r] = float(x.net_dr)
        ws["F%d" % r] = float(x.net_raw)
        ws["G%d" % r] = x.ifrs
        ws["H%d" % r] = "Yes" if x.flipped else ""
        for c in "CDEF":
            ws["%s%d" % (c, r)].number_format = NUM
        r += 1
    last = max(r - 1, DATA_R0)
    cell(ws, "A%d" % (last + 1), "TOTAL", bold=True, fill=GREY)
    cell(ws, "B%d" % (last + 1), None, fill=GREY)
    for c in "CDE":
        cell(ws, "%s%d" % (c, last + 1), "=SUM(%s%d:%s%d)" % (c, DATA_R0, c, last), bold=True, fill=GREY, fmt=NUM)
    for col, w in zip("ABCDEFGH", (12, 46, 18, 18, 20, 20, 38, 14)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A6"
    ws.auto_filter.ref = "A5:H%d" % last
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "808080"
    return {"sheet": TB_SHEET, "r0": DATA_R0, "r1": last}


# ----------------------------------------------------------------------------
# 9. IFRS P&L: trial balance vs VAT register, GL by GL
# ----------------------------------------------------------------------------


def write_pl(ws, df, gl_table, tb, entity, period_txt, cfg, data, tbdata):
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "C00000"
    has_tb = tb is not None
    present = set(df["treat"].unique())
    used = [T_STD] + [t for t in (T_ZERO, T_EXEMPT) if t in present] + [T_RCM] + \
           ([T_IMPORT] if T_IMPORT in present else []) + [T_OOS]
    imp_vat = T_IMPORT in present and df.loc[df["treat"] == T_IMPORT, "vat_pl"].abs().sum() > 0.004
    vat_t = [T_STD, T_RCM] + ([T_IMPORT] if imp_vat else [])
    if has_tb:
        BOOK, REG, DISC, C0 = "C", "D", "E", 6
        lead = [BOOK, REG, DISC]
    else:
        BOOK = DISC = None
        REG, C0 = "C", 4
        lead = [REG]
    tc = {t: get_column_letter(C0 + i) for i, t in enumerate(used)}
    TOT = get_column_letter(C0 + len(used))
    CHK = get_column_letter(C0 + len(used) + 1)
    V0 = C0 + len(used) + 2
    vc = {t: get_column_letter(V0 + i) for i, t in enumerate(vat_t)}
    VTOT = get_column_letter(V0 + len(vat_t))
    LASTI = V0 + len(vat_t)
    numcols = lead + list(tc.values()) + [TOT] + list(vc.values()) + [VTOT]
    first_tc, last_tc = tc[used[0]], tc[used[-1]]
    first_vc, last_vc = vc[vat_t[0]], vc[vat_t[-1]]

    label = {T_STD: "Standard\n5%", T_ZERO: "Zero-rated\n0%", T_EXEMPT: "Exempt", T_RCM: "RCM",
             T_IMPORT: "Import\n(review)" if cfg["import_mode"] == "not_reported" else "Imports",
             T_OOS: "Out of\nscope"}
    title_block(ws, LASTI, entity, period_txt,
                "Statement of Profit or Loss (IFRS) - trial balance vs VAT register - AED, income and expenses positive")
    if has_tb:
        band(ws, 5, 3, 5, "Trial balance vs VAT register", fill=BLACK, font=WHITE_B, center=True)
    else:
        band(ws, 5, 3, 3, "VAT register", fill=BLACK, font=WHITE_B, center=True)
    band(ws, 5, C0, C0 + len(used) + 1, "VAT register split by VAT treatment (net amounts)", fill=REDF,
         font=WHITE_B, center=True)
    band(ws, 5, V0, LASTI, "VAT amount (VAT register)", fill=BLACK, font=WHITE_B, center=True)
    heads = {"A": "GL Code", "B": "Particulars", REG: "Per VAT register\n(SUMIF of VAT Data)",
             TOT: "Total", CHK: "Check"}
    if has_tb:
        heads[BOOK] = "Per TB\n(SUMIF of TB Data)"
        heads[DISC] = "Discrepancy\n(TB - VAT reg.)"
        ws["A4"] = ("Discrepancy = Per TB - Per VAT register. Where the two have opposite signs (income with a debit "
                    "balance / expense with a credit balance) they are added instead: Per TB + Per VAT register.")
        ws["A4"].font = Font(italic=True, size=9, color="595959")
    for t, c in tc.items():
        heads[c] = label[t]
    heads[vc[T_STD]] = "VAT on\nStandard"
    heads[vc[T_RCM]] = "VAT on\nRCM"
    if T_IMPORT in vc:
        heads[vc[T_IMPORT]] = "VAT on\nImport"
    heads[VTOT] = "Total VAT"
    for c, h in heads.items():
        cell(ws, "%s6" % c, h, font=WHITE_B, fill=BLACK, align="center", wrap=True)
    ws.row_dimensions[6].height = 46

    DS = q(data["sheet"])

    def rng(col):
        return "%s!$%s$%d:$%s$%d" % (DS, col, data["r0"], col, data["r1"])

    def f_reg(rr):
        return "=SUMIF(%s,$A%d,%s)" % (rng("E"), rr, rng("K"))

    def f_amt(rr, t, vat=False):
        return '=SUMIFS(%s,%s,$A%d,%s,"%s")' % (rng("L" if vat else "K"), rng("E"), rr, rng("I"), t)

    def f_tb(rr, line):
        """TB balance is debit +ve / credit -ve. Income lines are shown as absolute numbers by negating it."""
        TS = q(tbdata["sheet"])
        a = "%s!$A$%d:$A$%d" % (TS, tbdata["r0"], tbdata["r1"])
        g = "%s!$E$%d:$E$%d" % (TS, tbdata["r0"], tbdata["r1"])
        return "=%sSUMIF(%s,$A%d,%s)" % ("-" if line in OUTPUT_LINES else "", a, rr, g)

    tbp = dict(zip(tb["gl_code"], tb["pres"])) if has_tb else {}

    def items_for(line):
        g = gl_table[gl_table["ifrs"] == line].sort_values("gl_code")
        out = []
        for x in g.itertuples():
            if line == L_BS:
                if x.in_vat:
                    out.append(x)
            elif x.in_vat or abs(tbp.get(x.gl_code, 0.0)) > 0.004:
                out.append(x)
        return out

    tot = {}
    r = 7
    ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
    sec_no = [0]

    def check(rr, fill=None, font=None):
        cell(ws, "%s%d" % (CHK, rr),
             '=IF(ROUND(%s%d-%s%d,2)=0,"%s",ROUND(%s%d-%s%d,2))' % (REG, rr, TOT, rr, TICK, REG, rr, TOT, rr),
             align="center", bold=True, fill=fill, font=font)

    def section(line, title):
        nonlocal r
        items = items_for(line)
        if not items and line != L_REV:
            return
        band(ws, r, 1, LASTI, "%s    %s" % (ROMAN[sec_no[0]], title), fill=REDF, font=WHITE_B)
        sec_no[0] += 1
        r += 1
        first = r
        for x in items:
            cell(ws, "A%d" % r, x.gl_code, align="center")
            cell(ws, "B%d" % r, x.gl_name)
            if has_tb:
                if line == L_BS:
                    cell(ws, "%s%d" % (BOOK, r), "n/a", align="center", font=Font(color="999999", italic=True))
                    cell(ws, "%s%d" % (DISC, r), None)
                else:
                    cell(ws, "%s%d" % (BOOK, r), f_tb(r, line), fmt=NUM)
                    cell(ws, "%s%d" % (DISC, r),
                         "=ROUND(IF(ROUND(%s%d,2)*ROUND(%s%d,2)<0,%s%d+%s%d,%s%d-%s%d),2)" % (
                             BOOK, r, REG, r, BOOK, r, REG, r, BOOK, r, REG, r), fmt=NUM, bold=True)
            cell(ws, "%s%d" % (REG, r), f_reg(r), fmt=NUM)
            for t in used:
                cell(ws, "%s%d" % (tc[t], r), f_amt(r, t), fmt=NUM)
            cell(ws, "%s%d" % (TOT, r), "=SUM(%s%d:%s%d)" % (first_tc, r, last_tc, r), fmt=NUM, bold=True)
            check(r)
            for t in vat_t:
                cell(ws, "%s%d" % (vc[t], r), f_amt(r, t, vat=True), fmt=NUM)
            cell(ws, "%s%d" % (VTOT, r), "=SUM(%s%d:%s%d)" % (first_vc, r, last_vc, r), fmt=NUM, bold=True)
            r += 1
        last = r - 1
        cell(ws, "A%d" % r, None, fill=GREY)
        cell(ws, "B%d" % r, "Total balance sheet GLs" if line == L_BS else
             "Total " + (title if line == L_UNC else title.lower()), bold=True, fill=GREY)
        for c in numcols:
            if line == L_BS and c in (BOOK, DISC):
                cell(ws, "%s%d" % (c, r), None, fill=GREY)
                continue
            f = "=SUM(%s%d:%s%d)" % (c, first, c, last) if last >= first else 0
            cell(ws, "%s%d" % (c, r), f, bold=True, fill=GREY, fmt=NUM)
        check(r, fill=GREY)
        tot[line] = r
        r += 2

    def sub(name, parts):
        nonlocal r
        parts = [(sg, ln) for sg, ln in parts if ln in tot]
        cell(ws, "A%d" % r, None, fill=BLACK)
        cell(ws, "B%d" % r, name, font=WHITE_B, fill=BLACK)
        for c in numcols:
            f = "=" + "".join("%s%s%d" % ("+" if sg > 0 else "-", c, tot[ln]) for sg, ln in parts) if parts else 0
            cell(ws, "%s%d" % (c, r), f, font=WHITE_B, fill=BLACK, fmt=NUM)
        check(r, fill=BLACK, font=WHITE_B)
        tot[name] = r
        r += 2

    section(L_REV, "Revenue")
    section(L_COS, "Cost of sales")
    sub("Gross profit", [(1, L_REV), (-1, L_COS)])
    section(L_OI, "Other income / (losses)")
    section(L_OE, "Other expenses / (losses)")
    section(L_SD, "Selling and distribution expenses")
    section(L_GA, "General and administrative expenses")
    section(L_UNC, "Unclassified (map in GL_IFRS_Mapping.xlsx)")
    sub("Operating profit", [(1, "Gross profit"), (1, L_OI), (-1, L_OE), (-1, L_SD), (-1, L_GA), (-1, L_UNC)])
    section(L_FI, "Finance income")
    section(L_FC, "Finance costs")
    sub("Profit before tax", [(1, "Operating profit"), (1, L_FI), (-1, L_FC)])
    section(L_TAX, "Income tax expense")
    sub("Profit for the period", [(1, "Profit before tax"), (-1, L_TAX)])

    parts = [(1, L_COS), (1, L_OE), (1, L_SD), (1, L_GA), (1, L_UNC), (1, L_FC), (1, L_TAX), (-1, L_OI), (-1, L_FI)]
    parts = [(sg, ln) for sg, ln in parts if ln in tot]
    cell(ws, "A%d" % r, None, fill=LIGHT)
    cell(ws, "B%d" % r, "Memo: total expenses incl. tax, net of other income", font=Font(italic=True), fill=LIGHT)
    for c in numcols:
        f = "=" + "".join("%s%s%d" % ("+" if sg > 0 else "-", c, tot[ln]) for sg, ln in parts) if parts else 0
        cell(ws, "%s%d" % (c, r), f, font=Font(italic=True), fill=LIGHT, fmt=NUM)
    r += 3

    if items_for(L_BS):
        ws["A%d" % r] = "Balance sheet GLs in the VAT register (e.g. accruals, capex) - not part of the P&L, shown so VAT reconciles"
        ws["A%d" % r].font = Font(italic=True, color="595959")
        r += 1
        section(L_BS, "Balance sheet (not in P&L)")

    last_data = r
    ws.conditional_formatting.add("%s7:%s%d" % (CHK, CHK, last_data),
                                  CellIsRule(operator="equal", formula=['"%s"' % TICK], font=Font(color="00A050", bold=True)))
    ws.conditional_formatting.add("%s7:%s%d" % (CHK, CHK, last_data),
                                  FormulaRule(formula=['AND(%s7<>"",%s7<>"%s")' % (CHK, CHK, TICK)],
                                              fill=PatternFill("solid", bgColor="C00000"), font=Font(color="FFFFFF", bold=True)))
    if has_tb:
        ws.conditional_formatting.add("%s7:%s%d" % (DISC, DISC, last_data),
                                      FormulaRule(formula=["AND(ISNUMBER(%s7),ABS(%s7)>=0.005)" % (DISC, DISC)],
                                                  fill=PatternFill("solid", bgColor="F8CBAD"),
                                                  font=Font(color="C00000", bold=True)))
    for c, w in {"A": 11, "B": 50}.items():
        ws.column_dimensions[c].width = w
    for i in range(3, LASTI + 1):
        ws.column_dimensions[get_column_letter(i)].width = 17
    ws.column_dimensions[CHK].width = 11
    ws.freeze_panes = "C7"
    page_setup(ws)
    return tot


# ----------------------------------------------------------------------------
# 10. Checks & exceptions sheet
# ----------------------------------------------------------------------------


def write_checks(ws, df, info, ex, entity, period_txt, extra=None):
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "FFC000"
    title_block(ws, 10, entity, period_txt, "Checks and Exceptions - lines that need your review before filing")
    r = 5
    cell(ws, "A%d" % r, "Data control", font=WHITE_B, fill=BLACK)
    cell(ws, "B%d" % r, None, fill=BLACK)
    r += 1
    for lab, val in (("Rows in VAT register", info["rows_in_file"]),
                     ("Rows ignored - blank / report total rows", info["dropped_blank"]),
                     ("Rows ignored - dated outside the return period", info["dropped_period"]),
                     ("Rows used for this entity", int(len(df))),
                     ("RCM lines where 5% VAT was calculated", info.get("rcm_vat_calculated", 0)),
                     ("Exceptions listed below", len(ex))) + tuple(extra or ()):
        cell(ws, "A%d" % r, lab)
        cell(ws, "B%d" % r, val, bold=True, align="right")
        r += 1
    r += 1
    heads = ["Issue", "Date", "Voucher", "Party", "GL Code", "GL Name", "Tax group", "Net", "VAT", "Comment"]
    for i, h in enumerate(heads, 1):
        cell(ws, "%s%d" % (get_column_letter(i), r), h, font=WHITE_B, fill=REDF, align="center")
    r0 = r + 1
    if not ex:
        ws["A%d" % r0] = "No exceptions found."
    for k, row in enumerate(ex):
        for i, v in enumerate(row, 1):
            if isinstance(v, pd.Timestamp):
                v = None if pd.isna(v) else v.to_pydatetime()
            c = ws.cell(row=r0 + k, column=i, value=v)
            c.border = BORDER
            if i == 2:
                c.number_format = DATEFMT
            if i in (8, 9):
                c.number_format = NUM
    for col, w in zip("ABCDEFGHIJ", (50, 14, 20, 34, 11, 34, 12, 16, 16, 40)):
        ws.column_dimensions[col].width = w
    if ex:
        ws.auto_filter.ref = "A%d:J%d" % (r, r0 + len(ex) - 1)


# ----------------------------------------------------------------------------
# 11. Build workbooks
# ----------------------------------------------------------------------------


def build_workbook(df_e, entity, cfg, info, out_dir, tb=None):
    period_txt = "%s to %s" % (cfg["period_from"].strftime("%d/%m/%Y"), cfg["period_to"].strftime("%d/%m/%Y"))
    gl_table = build_gl_table(df_e, tb)
    extra = []
    flags = None
    if tb is None:
        df_e, gl_table, moved = reclass_by_balance(df_e, gl_table, None)
    else:
        ifmap = dict(zip(gl_table["gl_code"], gl_table["ifrs"]))
        tb, flags = calibrate_tb_signs(tb, df_e, ifmap)
        df_e, gl_table, moved = reclass_by_balance(df_e, gl_table, tb)
        ifmap = dict(zip(gl_table["gl_code"], gl_table["ifrs"]))
        tb["ifrs"] = tb["gl_code"].map(ifmap)
        tb["pres"] = np.where(tb["ifrs"].isin(OUTPUT_LINES), -tb["net_dr"], tb["net_dr"])
        only_tb = gl_table[(~gl_table["in_vat"]) & (gl_table["ifrs"] != L_BS)]
        only_tb = [c for c in only_tb["gl_code"] if abs(dict(zip(tb["gl_code"], tb["pres"])).get(c, 0)) > 0.004]
        extra = [("GL lines in trial balance", int(len(tb))),
                 ("TB sign check - income GLs (convention: credit = negative)", "Flipped to match register" if flags["income"] else "As per TB"),
                 ("TB sign check - expense GLs (convention: debit = positive)", "Flipped to match register" if flags["expense"] else "As per TB"),
                 ("Trial balance net (Dr - Cr) - should be nil", round(float(tb["net_dr"].sum()), 2)),
                 ("P&L GLs in TB with no VAT register lines", len(only_tb))]
    if moved:
        extra.append(("Income GLs with a debit balance shown as expenses", ", ".join(sorted(moved))))
    neg = []
    for x in gl_table[gl_table["ifrs"].isin(OUTPUT_LINES)].itertuples():
        if tb is not None and x.gl_code in set(tb["gl_code"]):
            val = float(tb.loc[tb["gl_code"] == x.gl_code, "pres"].iloc[0])
        else:
            val = float(df_e.loc[df_e["gl_code"] == x.gl_code, "pres"].sum())
        if val < -0.004:
            neg.append(x.gl_code)
    if neg:
        extra.append(("Income GLs with a DEBIT balance (shown negative)", ", ".join(sorted(neg))))
    if tb is not None:
        regp = df_e.groupby("gl_code")["pres"].sum()
        tbp_ = dict(zip(tb["gl_code"], tb["pres"]))
        opp = [c for c in regp.index if c in tbp_ and round(tbp_[c], 2) * round(regp[c], 2) < 0
               and dict(zip(gl_table["gl_code"], gl_table["ifrs"])).get(c) != L_BS]
        if opp:
            extra.append(("GLs where TB and register have opposite signs (discrepancy = TB + register)",
                          ", ".join(sorted(opp))))
    wb = Workbook()
    ws_sum = wb.active
    ws_sum.title = SUMMARY
    ws_pl = wb.create_sheet(PLSHEET)
    bx = explode_boxes(df_e, cfg)
    links = {}
    for key in BOX_INFO:
        rows = bx[bx["box"] == key]
        if len(rows):
            ws = wb.create_sheet(BOX_INFO[key][0])
            links[key] = (BOX_INFO[key][0], write_box_sheet(ws, key, rows, entity, period_txt))
    ws_data = wb.create_sheet(DATA_SHEET)
    ws_tb = wb.create_sheet(TB_SHEET) if tb is not None else None
    ws_chk = wb.create_sheet(CHKSHEET)
    write_summary(ws_sum, entity, cfg["trn_map"].get(entity, cfg.get("trn", "")), cfg, links)
    data_ref = write_data_sheet(ws_data, df_e, entity, period_txt)
    tb_ref = write_tb_sheet(ws_tb, tb, entity, period_txt) if tb is not None else None
    write_pl(ws_pl, df_e, gl_table, tb, entity, period_txt, cfg, data_ref, tb_ref)
    ex = find_exceptions(df_e, cfg)
    write_checks(ws_chk, df_e, info, ex, entity, period_txt, extra)
    fname = "VAT201_%s_%s_to_%s.xlsx" % (safe_name(entity), cfg["period_from"].strftime("%Y%m%d"),
                                         cfg["period_to"].strftime("%Y%m%d"))
    path = os.path.join(out_dir, fname)
    wb.save(path)
    return path, len(ex), gl_table, flags


def run_report(raw, cfg, tb_raw=None):
    cfg.setdefault("trn_map", {})
    for t in [cfg.get("trn", "")] + list(cfg["trn_map"].values()):
        if t and not is_valid_trn(t):
            raise ValueError("TRN '%s' is invalid: it must be exactly %d digits (numbers only)." % (t, TRN_LEN))
    df, info = prepare(raw, cfg)
    if df.empty:
        raise ValueError("No rows left after cleaning / period filter. Check the dates and column mapping.")
    info["rows_used"] = int(len(df))
    os.makedirs(cfg["out_dir"], exist_ok=True)
    ents = sorted(df["entity"].unique())
    tb, tb_note = None, ""
    if tb_raw is not None:
        if len(ents) == 1:
            tb = prepare_tb(tb_raw, cfg)
        else:
            tb_note = " Trial balance ignored: the register contains several entities."
    files, n_ex, tables = [], 0, []
    for ent, sub in df.groupby("entity", sort=True):
        p, n, gt, flags = build_workbook(sub, ent, cfg, info, cfg["out_dir"], tb)
        files.append(p)
        n_ex += n
        tables.append(gt)
        if flags and (flags["income"] or flags["expense"]):
            tb_note = " TB sign adjusted for: %s (see 'Checks & Exceptions')." % " and ".join(
                k + " GLs" for k, v in flags.items() if v)
    save_gl_mapping(pd.concat(tables, ignore_index=True))
    log = ["%d register lines used (%d blank/total and %d out-of-period lines ignored); %d item(s) to review."
           % (info["rows_used"], info["dropped_blank"], info["dropped_period"], n_ex)]
    unc = pd.concat(tables)
    unc = unc[unc["ifrs"] == L_UNC]["gl_code"].nunique()
    if unc:
        log.append("%d GL(s) not classified - edit GL_IFRS_Mapping.xlsx and re-run." % unc)
    if tb is not None:
        log.append("Trial balance used (%d GLs)." % len(tb))
    return files, " ".join(log) + tb_note


# ----------------------------------------------------------------------------
# 12. User interface
# ----------------------------------------------------------------------------
GUESS = OrderedDict([
    ("gl_code", ["gl code", "account code", "account no", "account number", "acc code", "gl no", "gl account no"]),
    ("gl_name", ["gl account", "gl name", "account name", "account description", "gl description", "ledger name"]),
    ("vat_code", ["sales tax group", "vat group", "tax group", "vat code", "tax code", "vat category",
                  "tax category", "vat type", "tax type", "vat treatment"]),
    ("vat_code2", ["sales tax code", "tax code", "vat code"]),
    ("vat", ["vat amount", "tax amount", "vat aed", "vat", "tax"]),
    ("debit", ["debit", "debit amount", "dr"]),
    ("credit", ["credit", "credit amount", "cr"]),
    ("net", ["net amount", "taxable amount", "base amount", "amount (aed)", "amount aed", "aed", "amount", "net", "value"]),
    ("date", ["date of invoice", "voucher date", "posting date", "doc date", "transaction date", "invoice date", "date"]),
    ("voucher", ["voucher", "voucher no", "voucher number", "document no", "doc no", "invoice no", "invoice id",
                 "journal", "reference", "ref"]),
    ("party", ["supplier name", "vendor name", "customer name", "party name", "party", "supplier", "vendor", "customer"]),
    ("party_trn", ["supplier vat no", "supplier trn", "vendor trn", "customer trn", "party trn", "trn", "vat no",
                   "vat number", "tax registration number"]),
    ("entity", ["entity", "legal entity", "company", "le name", "branch"]),
    ("emirate", ["emirate", "place of supply", "location"]),
    ("source", ["source", "transaction type", "doc type", "document type", "type"]),
    ("acct_type", ["account type", "gl type", "category", "class", "ifrs line"]),
])
TB_GUESS = OrderedDict([
    ("tb_code", ["gl code", "account code", "account no", "account number", "acc code", "gl no", "main account",
                 "account", "code"]),
    ("tb_name", ["gl name", "account name", "account description", "gl description", "ledger name", "description",
                 "particulars", "name"]),
    ("tb_debit", ["period debit", "debit", "debit amount", "dr"]),
    ("tb_credit", ["period credit", "credit", "credit amount", "cr"]),
    ("tb_net", ["net movement", "period balance", "net balance", "closing balance", "balance", "net", "amount",
                "closing"]),
])
LABELS = OrderedDict([
    ("gl_code", "GL code"), ("gl_name", "GL name"), ("date", "Invoice / voucher date"), ("voucher", "Voucher no."),
    ("net", "Net amount"), ("vat", "VAT amount"), ("debit", "Debit (if separate)"), ("credit", "Credit (if separate)"),
    ("vat_code", "VAT treatment column"), ("vat_code2", "2nd tax column (cross-check)"),
    ("source", "Source (Purchase / Sales)"), ("party", "Supplier / customer name"),
    ("party_trn", "Supplier / customer TRN"), ("emirate", "Emirate (optional)"),
    ("entity", "Entity column (optional)"), ("acct_type", "Account type (optional)"),
])
TB_LABELS = OrderedDict([
    ("tb_code", "TB: GL code"), ("tb_name", "TB: GL name"), ("tb_debit", "TB: Debit"),
    ("tb_credit", "TB: Credit"), ("tb_net", "TB: Net balance (if one column)"),
])
SIGN_MODES = OrderedDict([
    ("Natural: Purchase +ve, Sales +ve (uses Source column)", "natural"),
    ("Debit +ve / Credit -ve", "debit_positive"),
    ("Credit +ve / Debit -ve", "credit_positive"),
])
TB_SIGNS = OrderedDict([("Debit +ve / Credit -ve (credit balances negative)", "debit_positive"),
                        ("Credit +ve / Debit -ve", "credit_positive")])


def guess_columns(cols, table=None):
    table = table or GUESS
    low = {c.lower().strip(): c for c in cols}
    used, out = set(), {}
    for key, kws in table.items():
        hit = None
        for kw in kws:
            if kw in low and low[kw] not in used:
                hit = low[kw]
                break
        if hit is None:
            for kw in kws:
                if len(kw) <= 4:
                    continue
                for lc, orig in low.items():
                    if kw in lc and orig not in used:
                        hit = orig
                        break
                if hit:
                    break
        if hit:
            used.add(hit)
        out[key] = hit
    return out


def parse_date(s):
    return dt.datetime.strptime(s.strip(), "%d/%m/%Y")


def quarter_bounds(d_min, d_max):
    qs = dt.datetime(d_min.year, 3 * ((d_min.month - 1) // 3) + 1, 1)
    m = 3 * ((d_max.month - 1) // 3) + 3
    qe = dt.datetime(d_max.year, m, 1)
    nxt = dt.datetime(qe.year + (m // 12), (m % 12) + 1, 1)
    return qs, nxt - dt.timedelta(days=1)


def clean_entity(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"(?i)\b(vat|report|register|voucher|vouchers|return|q[1-4]|20\d\d|file|data|201|tb)\b", " ", stem)
    return re.sub(r"\s+", " ", stem).strip()


PAL = dict(navy="#14213D", red="#C00000", blue="#2563EB", teal="#0F9D8A", amber="#F59E0B", purple="#7C3AED",
           green="#16A34A", bg="#EEF1F6", card="#FFFFFF", muted="#6B7280", ink="#111827", line="#E5E7EB",
           row2="#F6F8FC")
TREAT_COL = {T_STD: PAL["blue"], T_ZERO: PAL["teal"], T_EXEMPT: PAL["green"], T_RCM: PAL["purple"],
             T_IMPORT: PAL["amber"], T_OOS: "#9CA3AF"}
FONT = "Segoe UI"


class ScrollFrame(tk.Frame if tk else object):
    def __init__(self, parent, bg):
        tk.Frame.__init__(self, parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._wheel)

    def _wheel(self, e):
        try:
            self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        except Exception:
            pass


class App:
    def __init__(self, root):
        self.root = root
        root.title("VAT 201 Schedule Builder")
        root.geometry("980x900")
        root.minsize(860, 640)
        root.configure(bg=PAL["bg"])
        self.files = []          # dicts: path, raw, sheet, header, entity, trn (StringVar), tb_path, tb_raw
        self.cols = []
        self.tb_cols = []
        self.v = {k: tk.StringVar(value="(none)") for k in LABELS}
        self.tbv = {k: tk.StringVar(value="(none)") for k in TB_LABELS}
        self.tb_sign = tk.StringVar(value=list(TB_SIGNS)[0])
        self.d_from = tk.StringVar()
        self.d_to = tk.StringVar()
        self.d_due = tk.StringVar()
        self.emirate = tk.StringVar(value="Dubai")
        self.import_mode = tk.StringVar(value=list(IMPORT_MODES)[0])
        self.filter = tk.BooleanVar(value=True)
        self.follow = tk.BooleanVar(value=True)
        self.sign = tk.StringVar(value=list(SIGN_MODES)[0])
        self.sheet = tk.StringVar()
        self.hdr = tk.IntVar(value=1)
        self.outdir = tk.StringVar()
        self.status = tk.StringVar(value="Step 1: select your VAT register to begin.")
        self.map_vars = {}
        self._style()
        self._build()

    # ------------------------------------------------------------- styling
    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure("TCombobox", padding=5, fieldbackground="#FFFFFF")
        st.configure("TEntry", padding=5, fieldbackground="#FFFFFF")
        st.configure("TCheckbutton", background=PAL["card"], font=(FONT, 10))

        def btn(name, bg, hover):
            st.configure(name, background=bg, foreground="white", font=(FONT, 10, "bold"), padding=(16, 8),
                         borderwidth=0, focusthickness=0)
            st.map(name, background=[("active", hover), ("disabled", "#C9CED6")],
                   foreground=[("disabled", "#FFFFFF")])
        btn("Blue.TButton", PAL["blue"], "#1D4ED8")
        btn("Teal.TButton", PAL["teal"], "#0B7A6B")
        btn("Red.TButton", PAL["red"], "#8F0000")
        btn("Go.TButton", PAL["green"], "#12803A")
        st.configure("Go.TButton", font=(FONT, 12, "bold"), padding=(26, 11))
        btn("Ghost.TButton", "#E5E7EB", "#D1D5DB")
        st.configure("Ghost.TButton", foreground=PAL["ink"])
        st.map("Ghost.TButton", foreground=[("disabled", "#FFFFFF")])
        st.configure("Go.Horizontal.TProgressbar", troughcolor="#E5E7EB", background=PAL["green"], thickness=8,
                     borderwidth=0)

    def _card(self, parent, num, title, sub, color):
        outer = tk.Frame(parent, bg=PAL["bg"])
        outer.pack(fill="x", padx=20, pady=(14, 0))
        box = tk.Frame(outer, bg=PAL["card"], highlightbackground=PAL["line"], highlightthickness=1)
        box.pack(fill="x")
        tk.Frame(box, bg=color, height=5).pack(fill="x")
        head = tk.Frame(box, bg=PAL["card"])
        head.pack(fill="x", padx=18, pady=(12, 2))
        tk.Label(head, text=str(num), bg=color, fg="white", font=(FONT, 11, "bold"), width=3).pack(side="left")
        tk.Label(head, text="  " + title, bg=PAL["card"], fg=color, font=(FONT, 13, "bold")).pack(side="left")
        if sub:
            tk.Label(box, text=sub, bg=PAL["card"], fg=PAL["muted"], font=(FONT, 9), anchor="w",
                     justify="left").pack(fill="x", padx=18)
        body = tk.Frame(box, bg=PAL["card"])
        body.pack(fill="x", padx=18, pady=(8, 16))
        return body

    def _lbl(self, parent, text, bg=None, **kw):
        return tk.Label(parent, text=text, bg=bg or PAL["card"], fg=kw.pop("fg", PAL["ink"]),
                        font=kw.pop("font", (FONT, 10)), **kw)

    # ------------------------------------------------------------- layout
    def _build(self):
        banner = tk.Frame(self.root, bg=PAL["navy"])
        banner.pack(fill="x")
        left = tk.Frame(banner, bg=PAL["navy"])
        left.pack(side="left", padx=24, pady=14)
        tk.Label(left, text="VAT 201 Schedule Builder", bg=PAL["navy"], fg="white", font=(FONT, 20, "bold")).pack(anchor="w")
        tk.Label(left, text="VAT register  +  Trial balance   \u2192   VAT 201 schedules, IFRS P&L and reconciliation",
                 bg=PAL["navy"], fg="#9FB3D9", font=(FONT, 10)).pack(anchor="w")
        chips = tk.Frame(banner, bg=PAL["navy"])
        chips.pack(side="right", padx=24)
        for txt_, col in (("VAT register", PAL["blue"]), ("Trial balance", PAL["teal"]), ("Return", PAL["amber"]),
                          ("Treatment", PAL["purple"])):
            tk.Label(chips, text="  %s  " % txt_, bg=col, fg="white", font=(FONT, 9, "bold")).pack(side="left", padx=3)
        stripe = tk.Frame(self.root, height=4)
        stripe.pack(fill="x")
        for col in (PAL["red"], PAL["amber"], PAL["teal"], PAL["blue"], PAL["purple"]):
            tk.Frame(stripe, bg=col, height=4).pack(side="left", fill="x", expand=True)

        # footer (pinned)
        foot = tk.Frame(self.root, bg="#FFFFFF", highlightbackground=PAL["line"], highlightthickness=1)
        foot.pack(side="bottom", fill="x")
        fin = tk.Frame(foot, bg="#FFFFFF")
        fin.pack(fill="x", padx=20, pady=(10, 4))
        tk.Label(fin, text="Save to", bg="#FFFFFF", font=(FONT, 9, "bold"), fg=PAL["muted"]).grid(row=0, column=0, sticky="w")
        ttk.Entry(fin, textvariable=self.outdir, width=60).grid(row=0, column=1, padx=8, sticky="we")
        ttk.Button(fin, text="Change...", style="Ghost.TButton", command=self.browse_out).grid(row=0, column=2)
        self.btn_go = ttk.Button(fin, text="Generate VAT 201 workbooks  \u25B6", style="Go.TButton", command=self.generate)
        self.btn_go.grid(row=0, column=3, padx=(18, 0))
        fin.columnconfigure(1, weight=1)
        self.prog = ttk.Progressbar(foot, style="Go.Horizontal.TProgressbar", mode="determinate", maximum=100)
        self.prog.pack(fill="x", padx=20, pady=(4, 2))
        self.lbl_status = tk.Label(foot, textvariable=self.status, bg="#FFFFFF", fg=PAL["muted"], font=(FONT, 9, "bold"), anchor="w")
        self.lbl_status.pack(fill="x", padx=20, pady=(0, 8))

        self.sf = ScrollFrame(self.root, PAL["bg"])
        self.sf.pack(fill="both", expand=True)
        body = self.sf.inner

        # 1 - files
        c1 = self._card(body, 1, "VAT register and trial balance",
                        "Select the VAT register file(s) - one per entity. Then attach that entity's trial balance (TB) "
                        "for the period: P&L figures come from the TB, VAT fields from the register.", PAL["blue"])
        bar = tk.Frame(c1, bg=PAL["card"])
        bar.pack(fill="x")
        ttk.Button(bar, text="\U0001F4C2  Browse VAT register(s)...", style="Blue.TButton", command=self.browse).pack(side="left")
        self.lbl_detect = tk.Label(bar, text="", bg=PAL["card"], fg=PAL["green"], font=(FONT, 9, "bold"), anchor="w")
        self.lbl_detect.pack(side="left", padx=14)
        self.files_frame = tk.Frame(c1, bg=PAL["card"])
        self.files_frame.pack(fill="x", pady=(10, 0))

        # 2 - return details
        c2 = self._card(body, 2, "Return details", "Dates use dd/mm/yyyy. The period is suggested from your data.", PAL["amber"])
        g = tk.Frame(c2, bg=PAL["card"])
        g.pack(fill="x")
        for i, (lab, var) in enumerate((("Period from", self.d_from), ("Period to", self.d_to),
                                        ("Return date", self.d_due))):
            self._lbl(g, lab, font=(FONT, 10, "bold")).grid(row=0, column=i * 2, sticky="w", padx=(0 if i == 0 else 22, 6))
            ttk.Entry(g, textvariable=var, width=12).grid(row=0, column=i * 2 + 1)
        self._lbl(g, "Default emirate", font=(FONT, 10, "bold")).grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Combobox(g, textvariable=self.emirate, values=list(EMIRATES), state="readonly", width=14).grid(
            row=1, column=1, pady=(12, 0), sticky="w")
        ttk.Checkbutton(c2, text="Ignore register lines dated outside the period", variable=self.filter).pack(
            anchor="w", pady=(12, 0))

        # 3 - VAT treatment
        c3 = self._card(body, 3, "VAT treatment",
                        "How each tax code in your register is treated. Pre-filled automatically - change only if needed.",
                        PAL["purple"])
        self.map_frame = tk.Frame(c3, bg=PAL["card"])
        self.map_frame.pack(fill="x")
        self._lbl(self.map_frame, "Load a VAT register to see its tax codes.", fg=PAL["muted"]).pack(anchor="w")

        # advanced
        c4o = tk.Frame(body, bg=PAL["bg"])
        c4o.pack(fill="x", padx=20, pady=(14, 20))
        self.adv_btn = ttk.Button(c4o, text="\u2699  Show advanced: column mapping", style="Ghost.TButton", command=self.toggle_adv)
        self.adv_btn.pack(anchor="w")
        self.adv = tk.Frame(c4o, bg=PAL["card"], highlightbackground=PAL["line"], highlightthickness=1)
        self._build_adv()
        self.adv_open = False

    def _build_adv(self):
        a = tk.Frame(self.adv, bg=PAL["card"])
        a.pack(fill="x", padx=18, pady=14)
        tk.Label(a, text="VAT register columns", bg=PAL["card"], fg=PAL["blue"], font=(FONT, 11, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        self._lbl(a, "Sheet").grid(row=1, column=0, sticky="w")
        self.cb_sheet = ttk.Combobox(a, textvariable=self.sheet, state="readonly", width=22)
        self.cb_sheet.grid(row=1, column=1, sticky="w", padx=(4, 18))
        self._lbl(a, "Header row").grid(row=1, column=2, sticky="w")
        sp = ttk.Spinbox(a, from_=1, to=60, textvariable=self.hdr, width=5)
        sp.grid(row=1, column=3, sticky="w", padx=4)
        ttk.Button(a, text="Reload", style="Ghost.TButton", command=self.reload_first).grid(row=1, column=4, padx=12)
        self.cbs = {}
        for i, (k, lab) in enumerate(LABELS.items()):
            r, c = 2 + i // 2, (i % 2) * 2
            self._lbl(a, lab).grid(row=r, column=c, sticky="w", pady=3, padx=(0 if c == 0 else 18, 4))
            cb = ttk.Combobox(a, textvariable=self.v[k], state="readonly", width=26, values=["(none)"] + self.cols)
            cb.grid(row=r, column=c + 1, sticky="w", pady=3)
            self.cbs[k] = cb
        self.cbs["vat_code"].bind("<<ComboboxSelected>>", lambda e: self.build_map())
        rr = 3 + len(LABELS) // 2
        self._lbl(a, "Amount sign").grid(row=rr, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(a, textvariable=self.sign, values=list(SIGN_MODES), state="readonly", width=48).grid(
            row=rr, column=1, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Checkbutton(a, text="VAT column is unsigned (take the sign from the net amount)", variable=self.follow).grid(
            row=rr + 1, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self._lbl(a, "Lines whose tax code is 'Import'").grid(row=rr + 2, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(a, textvariable=self.import_mode, values=list(IMPORT_MODES), state="readonly", width=48).grid(
            row=rr + 2, column=1, columnspan=3, sticky="w", pady=(8, 0))
        rr += 2
        tk.Label(a, text="Trial balance columns", bg=PAL["card"], fg=PAL["teal"], font=(FONT, 11, "bold")).grid(
            row=rr + 2, column=0, columnspan=4, sticky="w", pady=(16, 6))
        self.tbcbs = {}
        for i, (k, lab) in enumerate(TB_LABELS.items()):
            r, c = rr + 3 + i // 2, (i % 2) * 2
            self._lbl(a, lab).grid(row=r, column=c, sticky="w", pady=3, padx=(0 if c == 0 else 18, 4))
            cb = ttk.Combobox(a, textvariable=self.tbv[k], state="readonly", width=26, values=["(none)"] + self.tb_cols)
            cb.grid(row=r, column=c + 1, sticky="w", pady=3)
            self.tbcbs[k] = cb
        r = rr + 3 + (len(TB_LABELS) + 1) // 2
        self._lbl(a, "TB sign (one balance column)").grid(row=r, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(a, textvariable=self.tb_sign, values=list(TB_SIGNS), state="readonly", width=46).grid(
            row=r, column=1, columnspan=3, sticky="w", pady=(8, 0))
        tk.Label(a, text="The sign is also checked against the VAT register and corrected automatically if inverted.",
                 bg=PAL["card"], fg=PAL["muted"], font=(FONT, 9, "italic")).grid(
            row=r + 1, column=0, columnspan=4, sticky="w", pady=(4, 0))

    def toggle_adv(self):
        if self.adv_open:
            self.adv.pack_forget()
            self.adv_btn.configure(text="\u2699  Show advanced: column mapping")
        else:
            self.adv.pack(fill="x", pady=(8, 0))
            self.adv_btn.configure(text="\u2699  Hide advanced: column mapping")
        self.adv_open = not self.adv_open

    # ------------------------------------------------------------- actions
    def browse(self):
        paths = filedialog.askopenfilenames(title="Select VAT register(s)",
                                            filetypes=[("Excel / CSV", "*.xlsx *.xlsm *.xls *.csv"), ("All", "*.*")])
        if paths:
            self.load_files(list(paths))

    def browse_out(self):
        p = filedialog.askdirectory(title="Output folder")
        if p:
            self.outdir.set(p)

    def _read(self, path, sheet=None, header=None):
        if sheet is None and not path.lower().endswith((".csv", ".txt")):
            sheet, _ = best_sheet(path)
        if header is None:
            header = detect_header_row(path, sheet)
        return read_table(path, sheet, header), sheet, header

    def load_files(self, paths):
        self.files = []
        errors = []
        for p in paths:
            try:
                raw, sheet, header = self._read(p)
                self.files.append({"path": p, "raw": raw, "sheet": sheet, "header": header,
                                   "entity": tk.StringVar(value=clean_entity(p) or "Entity %d" % (len(self.files) + 1)),
                                   "trn": tk.StringVar(), "tb_path": None, "tb_raw": None})
            except Exception as e:
                errors.append("%s: %s" % (os.path.basename(p), e))
        if errors:
            messagebox.showerror("Could not read file", "\n".join(errors))
        if not self.files:
            return
        first = self.files[0]
        self.cols = list(first["raw"].columns)
        self._apply_guess(first)
        if first["sheet"]:
            try:
                self.cb_sheet["values"] = pd.ExcelFile(first["path"]).sheet_names
            except Exception:
                self.cb_sheet["values"] = [first["sheet"]]
            self.sheet.set(first["sheet"])
        self.hdr.set(first["header"])
        if not self.outdir.get():
            self.outdir.set(os.path.join(os.path.dirname(first["path"]), "VAT201_Output"))
        self.show_files()
        self.suggest_dates()
        self.build_map()
        rows = sum(len(f["raw"]) for f in self.files)
        self.lbl_detect.configure(text="\u2714  %d register file(s), %d lines, %d columns detected" % (len(self.files), rows, len(self.cols)))
        self.set_status("Step 2: attach each entity's trial balance (recommended), check the dates, then generate.")

    def _apply_guess(self, first):
        g = guess_columns(self.cols)
        for k, cb in self.cbs.items():
            cb["values"] = ["(none)"] + self.cols
            self.v[k].set(g.get(k) or "(none)")
        if (g.get("debit") and g.get("credit") and not g.get("net")) or not g.get("source"):
            self.sign.set(list(SIGN_MODES)[1])
        else:
            self.sign.set(list(SIGN_MODES)[0])

    def reload_first(self):
        if not self.files:
            return
        f = self.files[0]
        try:
            raw, _, _ = self._read(f["path"], self.sheet.get() or None, int(self.hdr.get()))
        except Exception as e:
            messagebox.showerror("Cannot read file", str(e))
            return
        f["raw"], f["sheet"], f["header"] = raw, self.sheet.get(), int(self.hdr.get())
        self.cols = list(raw.columns)
        self._apply_guess(f)
        self.suggest_dates()
        self.build_map()

    def pick_tb(self, f):
        p = filedialog.askopenfilename(title="Select trial balance for %s" % f["entity"].get(),
                                       filetypes=[("Excel / CSV", "*.xlsx *.xlsm *.xls *.csv"), ("All", "*.*")])
        if p:
            self.load_tb(f, p)

    def load_tb(self, f, p):
        try:
            raw, _, _ = self._read(p)
        except Exception as e:
            messagebox.showerror("Cannot read trial balance", str(e))
            return
        f["tb_path"], f["tb_raw"] = p, raw
        self.tb_cols = list(raw.columns)
        g = guess_columns(self.tb_cols, TB_GUESS)
        for k, cb in self.tbcbs.items():
            cb["values"] = ["(none)"] + self.tb_cols
            self.tbv[k].set(g.get(k) or "(none)")
        self.show_files()
        self.set_status("Trial balance loaded for %s (%d lines)." % (f["entity"].get(), len(raw)))

    def show_files(self):
        for w in self.files_frame.winfo_children():
            w.destroy()
        hdr = tk.Frame(self.files_frame, bg=PAL["navy"])
        hdr.pack(fill="x")
        for i, (h, w) in enumerate((("Entity name", 26), ("VAT register", 28), ("Trial balance", 34),
                                    ("TRN (15 digits)", 24))):
            tk.Label(hdr, text=h, bg=PAL["navy"], fg="white", font=(FONT, 9, "bold"), width=w, anchor="w").grid(
                row=0, column=i, padx=4, pady=5, sticky="w")
        for n, f in enumerate(self.files):
            bg = PAL["card"] if n % 2 == 0 else PAL["row2"]
            row = tk.Frame(self.files_frame, bg=bg, highlightbackground=PAL["line"], highlightthickness=1)
            row.pack(fill="x")
            ttk.Entry(row, textvariable=f["entity"], width=26).grid(row=0, column=0, padx=4, pady=5, sticky="w")
            nm = os.path.basename(f["path"])
            tk.Label(row, text="\u2714 " + (nm if len(nm) < 30 else nm[:27] + "..."), bg=bg, fg=PAL["blue"],
                     font=(FONT, 9, "bold"), width=28, anchor="w").grid(row=0, column=1, padx=4)
            tbf = tk.Frame(row, bg=bg, width=34 * 7)
            tbf.grid(row=0, column=2, padx=4, sticky="w")
            if f["tb_raw"] is not None:
                tn = os.path.basename(f["tb_path"])
                tk.Label(tbf, text="\u2714 " + (tn if len(tn) < 22 else tn[:19] + "..."), bg=bg, fg=PAL["teal"],
                         font=(FONT, 9, "bold")).pack(side="left")
                ttk.Button(tbf, text="Change", style="Ghost.TButton", command=lambda f=f: self.pick_tb(f)).pack(side="left", padx=6)
            else:
                ttk.Button(tbf, text="Select TB...", style="Teal.TButton", command=lambda f=f: self.pick_tb(f)).pack(side="left")
                tk.Label(tbf, text="  none", bg=bg, fg=PAL["muted"], font=(FONT, 9)).pack(side="left")
            trnf = tk.Frame(row, bg=bg)
            trnf.grid(row=0, column=3, padx=4, pady=5, sticky="w")
            vcmd = (self.root.register(self._trn_ok), "%P")
            ttk.Entry(trnf, textvariable=f["trn"], width=18, validate="key", validatecommand=vcmd).pack(side="left")
            cnt = tk.Label(trnf, text="", bg=bg, font=(FONT, 9, "bold"), width=7)
            cnt.pack(side="left", padx=(6, 0))
            self._trn_counter(f["trn"], cnt)

    @staticmethod
    def _trn_ok(proposed):
        """Allow only digits, at most 15 of them (empty is allowed while typing)."""
        return re.fullmatch(r"[0-9]{0,%d}" % TRN_LEN, proposed) is not None

    def _trn_counter(self, var, label):
        def update(*a):
            try:
                n = len(var.get().strip())
                if n == TRN_LEN:
                    label.configure(text="%d/%d \u2714" % (n, TRN_LEN), fg=PAL["green"])
                elif n == 0:
                    label.configure(text="0/%d" % TRN_LEN, fg=PAL["muted"])
                else:
                    label.configure(text="%d/%d" % (n, TRN_LEN), fg=PAL["amber"])
            except Exception:
                pass                      # the row was rebuilt - this label no longer exists
        var.trace_add("write", update)
        update()

    def suggest_dates(self):
        dcol = self.v["date"].get()
        if not self.files or dcol == "(none)" or dcol not in self.files[0]["raw"].columns:
            return
        dmin = dmax = None
        for f in self.files:
            if dcol in f["raw"].columns:
                s = pd.to_datetime(f["raw"][dcol], errors="coerce", dayfirst=True).dropna()
                if len(s):
                    dmin = s.min() if dmin is None else min(dmin, s.min())
                    dmax = s.max() if dmax is None else max(dmax, s.max())
        if dmin is None:
            return
        qs, qe = quarter_bounds(dmin.to_pydatetime(), dmax.to_pydatetime())
        self.d_from.set(qs.strftime("%d/%m/%Y"))
        self.d_to.set(qe.strftime("%d/%m/%Y"))
        self.d_due.set((qe + dt.timedelta(days=28)).strftime("%d/%m/%Y"))

    def build_map(self):
        for w in self.map_frame.winfo_children():
            w.destroy()
        self.map_vars = {}
        vc = self.v["vat_code"].get()
        codes = set()
        if vc != "(none)":
            for f in self.files:
                if vc in f["raw"].columns:
                    s = txt(f["raw"][vc])
                    codes |= set(s.where(s != "", "(blank)"))
        if not codes:
            self._lbl(self.map_frame, "No tax-code column selected: lines with a VAT amount are treated as Standard 5%, "
                      "all others as Out of scope.", fg=PAL["muted"]).pack(anchor="w")
            return
        grid = tk.Frame(self.map_frame, bg=PAL["card"])
        grid.pack(anchor="w")
        self._lbl(grid, "Tax code in your register", fg=PAL["muted"], font=(FONT, 9, "bold")).grid(row=0, column=0, sticky="w")
        self._lbl(grid, "Treated as", fg=PAL["muted"], font=(FONT, 9, "bold")).grid(row=0, column=2, sticky="w", padx=14)
        for i, c in enumerate(sorted(codes), 1):
            self._lbl(grid, c, font=(FONT, 11, "bold"), width=22, anchor="w").grid(row=i, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=guess_treatment(c))
            chip = tk.Label(grid, text="   ", bg=TREAT_COL.get(var.get(), "#9CA3AF"))
            chip.grid(row=i, column=1, padx=(8, 0))
            ttk.Combobox(grid, textvariable=var, values=TREATMENTS, state="readonly", width=28).grid(
                row=i, column=2, padx=14, pady=4, sticky="w")
            var.trace_add("write", lambda *a, v=var, ch=chip: ch.configure(bg=TREAT_COL.get(v.get(), "#9CA3AF")))
            self.map_vars[c] = var

    def set_status(self, msg, kind="info"):
        self.status.set(msg)
        col = {"info": PAL["muted"], "ok": PAL["green"], "err": PAL["red"], "busy": PAL["blue"]}[kind]
        self.lbl_status.configure(fg=col)
        self.root.update_idletasks()

    def generate(self):
        if not self.files:
            messagebox.showwarning("VAT register", "Please select your VAT register first.")
            return
        if self.v["gl_code"].get() == "(none)":
            messagebox.showwarning("Column mapping", "The GL code column was not detected. Open 'advanced' and select it.")
            return
        dc = self.v["debit"].get() != "(none)" and self.v["credit"].get() != "(none)" and self.v["net"].get() == "(none)"
        if not dc and self.v["net"].get() == "(none)":
            messagebox.showwarning("Column mapping", "The amount column was not detected. Open 'advanced' and select it.")
            return
        try:
            pf, pt, fd = parse_date(self.d_from.get()), parse_date(self.d_to.get()), parse_date(self.d_due.get())
        except ValueError:
            messagebox.showwarning("Dates", "Please enter the three dates as dd/mm/yyyy.")
            return
        names = [f["entity"].get().strip() for f in self.files]
        if not all(names) or len(set(names)) != len(names):
            messagebox.showwarning("Entity name", "Each file needs its own, non-empty entity name.")
            return
        bad = [f["entity"].get() for f in self.files if not is_valid_trn(f["trn"].get())]
        if bad:
            messagebox.showwarning("TRN", "The TRN must be exactly %d digits (numbers only) for: %s" % (TRN_LEN, ", ".join(bad)))
            return
        no_tb = [f["entity"].get() for f in self.files if f["tb_raw"] is None]
        if no_tb and not messagebox.askyesno(
                "No trial balance",
                "No trial balance selected for: %s.\n\nTheir P&L will show VAT register amounts only (no "
                "reconciliation to books). Continue?" % ", ".join(no_tb)):
            return
        cols = {k: (None if v.get() == "(none)" else v.get()) for k, v in self.v.items()}
        tbc = {k: (None if v.get() == "(none)" else v.get()) for k, v in self.tbv.items()}
        tb_dc = bool(tbc.get("tb_debit") and tbc.get("tb_credit") and not tbc.get("tb_net"))
        base = dict(cols=cols, amount_mode="dc" if dc else "single", sign_mode=SIGN_MODES[self.sign.get()],
                    vat_follow_sign=self.follow.get(), filter_period=self.filter.get(),
                    period_from=pf, period_to=pt, filing_date=fd, default_emirate=self.emirate.get(),
                    out_dir=self.outdir.get(), import_mode=IMPORT_MODES[self.import_mode.get()],
                    vat_map={c: v.get() for c, v in self.map_vars.items()},
                    tb_cols=tbc, tb_mode="dc" if tb_dc else "single", tb_sign=TB_SIGNS[self.tb_sign.get()])
        made, notes = [], []
        self.btn_go.state(["disabled"])
        n = len(self.files)
        try:
            for i, f in enumerate(self.files, 1):
                self.prog["value"] = 100.0 * (i - 1) / n
                self.set_status("Building workbook %d of %d: %s ..." % (i, n, f["entity"].get()), "busy")
                cfg = dict(base, entity=f["entity"].get().strip(), trn=f["trn"].get().strip())
                cfg["trn_map"] = {cfg["entity"]: cfg["trn"]}
                missing = [c for k, c in cols.items() if c and c not in f["raw"].columns]
                if missing:
                    notes.append("%s skipped - columns not found: %s" % (os.path.basename(f["path"]), ", ".join(missing)))
                    continue
                tb_raw = f["tb_raw"]
                if tb_raw is not None:
                    tmiss = [c for k, c in tbc.items() if c and c not in tb_raw.columns]
                    if tmiss:
                        notes.append("%s: trial balance skipped - columns not found: %s" % (cfg["entity"], ", ".join(tmiss)))
                        tb_raw = None
                files, log = run_report(f["raw"], cfg, tb_raw)
                made += files
                notes.append("%s: %s" % (cfg["entity"], log))
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.btn_go.state(["!disabled"])
            self.set_status("Error: %s" % e, "err")
            messagebox.showerror("Error", str(e))
            return
        self.prog["value"] = 100
        self.btn_go.state(["!disabled"])
        self.set_status("\u2714  %d workbook(s) saved to %s" % (len(made), self.outdir.get()), "ok")
        if messagebox.askyesno("Done", "%d workbook(s) created.\n\n%s\n\nOpen the output folder?" % (
                len(made), "\n".join(notes))):
            try:
                if sys.platform.startswith("win"):
                    os.startfile(self.outdir.get())
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", self.outdir.get()])
                else:
                    subprocess.Popen(["xdg-open", self.outdir.get()])
            except Exception:
                pass


def main():
    if tk is None:
        print("tkinter is not available. Re-install Python from python.org (tick 'tcl/tk and IDLE').")
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
