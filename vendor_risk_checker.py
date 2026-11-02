"""
VENDOR MASTER RISK CHECKER
AICA Level 2 - Capstone Project

What it does
  1. Reads a vendor master (.xlsx or .csv) and, optionally, an employee master.
  2. Runs 14 rule-based checks: duplicates, PAN / GSTIN / IFSC format,
     missing details and vendor-employee matches.
  3. Sends only a summary of the exceptions to Google Gemini (no PAN, GSTIN
     or bank numbers leave your computer), which drafts an audit observation.
  4. Saves an Excel report plus a text file with the exact prompt and AI reply.

How to run
  Open this file in IDLE and press F5. Required libraries install themselves
  the first time. If that fails, run this once in Command Prompt:
      pip install openpyxl google-genai

Gemini API key
  Create one free at https://aistudio.google.com (Get API key), then paste it
  into the app. Optional: save it as environment variable GEMINI_API_KEY and
  the app will pick it up automatically.
"""

import os
import sys
import subprocess
import importlib

# ============================================================== AUTO-INSTALL
REQUIRED_PACKAGES = {"openpyxl": "openpyxl", "google.genai": "google-genai"}


def _pip_python():
    """IDLE on Windows runs under pythonw.exe; pip runs better with python.exe."""
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        candidate = exe[: -len("pythonw.exe")] + "python.exe"
        if os.path.exists(candidate):
            return candidate
    return exe


def ensure_packages():
    if getattr(sys, "frozen", False):          # running as a packaged .exe
        return
    missing = []
    for module, package in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(package)
    if not missing:
        return
    print("Installing required libraries:", ", ".join(missing))
    print("This happens only once and can take a minute...")
    cmd = [_pip_python(), "-m", "pip", "install", "--quiet", *missing]
    try:
        subprocess.check_call(cmd)
    except Exception:
        try:
            subprocess.check_call(cmd + ["--user"])
            import site
            user_site = site.getusersitepackages()
            if user_site not in sys.path:
                sys.path.append(user_site)
        except Exception:
            print("\nAutomatic install failed. Open Command Prompt and run:")
            print("    pip install openpyxl google-genai")
    importlib.invalidate_caches()
    try:
        importlib.import_module("openpyxl")
    except ImportError:
        raise SystemExit("openpyxl is required. Run:  pip install openpyxl google-genai")
    print("Ready.\n")


ensure_packages()

import csv
import re
import queue
import threading
import datetime as dt
from collections import defaultdict, Counter

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.formatting.rule import CellIsRule
from openpyxl.utils import get_column_letter

# ============================================================== SETTINGS
# Gemini models tried in order; the first one that works is used.
GEMINI_MODELS = ["gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash"]
MAX_SAMPLES_TO_AI = 20

# Column headings expected in your files (matching ignores case, spaces, dots).
# If your file uses different headings, change the text on the right.
VENDOR_COLUMNS = {
    "code": "Vendor Code",
    "name": "Vendor Name",
    "pan": "PAN",
    "gstin": "GSTIN",
    "bank": "Bank Account No",
    "ifsc": "IFSC",
    "address": "Address",
}
EMPLOYEE_COLUMNS = {
    "code": "Emp Code",
    "name": "Employee Name",
    "pan": "PAN",
    "bank": "Bank Account No",
    "address": "Address",
}

# (check name, risk rating, what it means)
CHECKS = [
    ("Duplicate PAN", "High",
     "Same legal entity set up more than once; risk of duplicate payments."),
    ("Duplicate GSTIN", "High",
     "Same GST registration used under more than one vendor code."),
    ("Duplicate bank account", "High",
     "Different vendor codes paid into one account; possible fictitious vendor or diversion of funds."),
    ("Duplicate vendor name", "Medium",
     "Same name (ignoring Pvt/Ltd and punctuation) under more than one vendor code."),
    ("GSTIN does not match PAN", "High",
     "PAN inside the GSTIN differs from the vendor PAN; GSTIN may be wrong or fake, input tax credit at risk."),
    ("Invalid PAN format", "Medium",
     "PAN is not in the format AAAAA9999A."),
    ("Invalid GSTIN format", "Medium",
     "GSTIN is not a valid 15-character GST number."),
    ("Invalid IFSC format", "Low",
     "IFSC is not in the format AAAA0XXXXXX; payments may fail or go astray."),
    ("Missing PAN", "Medium",
     "Vendor identity not verified; TDS at a higher rate (Sec 206AA) may apply."),
    ("Missing bank details", "Medium",
     "Bank account or IFSC is blank; payment details cannot be verified."),
    ("Missing address", "Low",
     "Vendor address is not recorded."),
    ("Bank account matches employee", "High",
     "Vendor is paid into an employee's bank account; possible conflict of interest or fraud."),
    ("PAN matches employee", "High",
     "An employee is set up as a vendor."),
    ("Address matches employee", "Medium",
     "Vendor shares an address with an employee; possible undisclosed related party."),
]
RISK_OF = {name: risk for name, risk, _ in CHECKS}
RISK_ORDER = {"High": 0, "Medium": 1, "Low": 2}

PAN_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")
GSTIN_RE = re.compile(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]")
IFSC_RE = re.compile(r"[A-Z]{4}0[A-Z0-9]{6}")

MISSING_TOKENS = {"", "NAN", "NONE", "NULL", "NA", "N/A", "-", "NIL"}
NAME_STOP_WORDS = {"pvt", "private", "ltd", "limited", "llp", "co", "company",
                   "the", "ms", "and"}

PROMPT_TEMPLATE = """You are a senior internal auditor in India reviewing a company's vendor master.
An automated tool has run data checks on the vendor master. The results are below.

Write an audit observation for the Audit Committee using exactly these headings:
Observation
Risk and Impact
Likely Root Cause
Recommendations
Priority Actions for Management

Rules:
- Use only the facts given below. Do not invent figures, vendor codes or names.
- Mention the vendor codes that need urgent attention.
- Keep it under 350 words, in plain text (no markdown symbols such as * or #).
- Write in a professional tone suitable for an internal audit report.

REVIEW RESULTS
Vendors reviewed: {total_vendors}
Vendors with at least one exception: {flagged_vendors}
Total exceptions: {total} (High: {high}, Medium: {medium}, Low: {low})
Employee master compared: {employee_compared}

Exceptions by check:
{check_lines}

Sample exceptions (vendor code | check | detail):
{sample_lines}
"""


# ============================================================== READING FILES
def cell_text(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def clean_id(v):
    """PAN / GSTIN / IFSC / bank account: upper case, no spaces."""
    s = re.sub(r"\s+", "", cell_text(v)).upper()
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return "" if s in MISSING_TOKENS else s


def clean_text(v):
    s = cell_text(v)
    return "" if s.upper() in MISSING_TOKENS else s


def name_key(name):
    s = re.sub(r"[^a-z0-9 ]", "", name.lower().replace("&", " and "))
    return " ".join(w for w in s.split() if w not in NAME_STOP_WORDS)


def address_key(address):
    key = re.sub(r"[^a-z0-9]", "", address.lower())
    return key if len(key) >= 10 else ""      # ignore very short addresses


def _norm_heading(h):
    return re.sub(r"[^a-z0-9]", "", cell_text(h).lower())


def read_table(path, wanted, label):
    """Returns (records, header_row, data_rows, column_positions)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = [list(r) for r in csv.reader(f)]
    elif ext in (".xlsx", ".xlsm"):
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
    else:
        raise ValueError(f"{label}: please use an .xlsx or .csv file "
                         f"(got '{ext or 'no extension'}').")

    targets = {key: _norm_heading(h) for key, h in wanted.items()}
    header_idx = None
    for i, row in enumerate(rows[:20]):
        present = {_norm_heading(c) for c in row}
        if all(t in present for t in targets.values()):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(
            f"{label}: could not find the expected column headings on the first sheet.\n"
            f"Expected: {', '.join(wanted.values())}\n"
            "If your headings differ, edit VENDOR_COLUMNS / EMPLOYEE_COLUMNS "
            "at the top of the script.")

    header = [cell_text(c) for c in rows[header_idx]]
    norm_header = [_norm_heading(c) for c in rows[header_idx]]
    pos = {key: norm_header.index(t) for key, t in targets.items()}

    records, data_rows = [], []
    for row in rows[header_idx + 1:]:
        if not any(cell_text(c) for c in row):
            continue
        row = list(row) + [None] * (len(header) - len(row))
        records.append({key: row[p] for key, p in pos.items()})
        data_rows.append([cell_text(c) for c in row[:len(header)]])
    return records, header, data_rows, pos


# ============================================================== CHECKS
def prepare(records, has_gst_ifsc=True):
    for i, r in enumerate(records, start=1):
        r["code"] = clean_text(r.get("code")) or f"Row {i}"
        r["name"] = clean_text(r.get("name"))
        r["pan"] = clean_id(r.get("pan"))
        r["bank"] = clean_id(r.get("bank"))
        r["address"] = clean_text(r.get("address"))
        if has_gst_ifsc:
            r["gstin"] = clean_id(r.get("gstin"))
            r["ifsc"] = clean_id(r.get("ifsc"))


def run_checks(vendors, employees):
    exceptions = []

    def add(v, check, detail):
        exceptions.append({"code": v["code"], "name": v["name"],
                           "check": check, "risk": RISK_OF[check], "detail": detail})

    # 1. Duplicates within the vendor master
    duplicate_tests = [
        ("Duplicate PAN", "PAN", lambda v: v["pan"]),
        ("Duplicate GSTIN", "GSTIN", lambda v: v["gstin"]),
        ("Duplicate bank account", "bank account", lambda v: v["bank"]),
        ("Duplicate vendor name", "name", lambda v: name_key(v["name"])),
    ]
    for check, label, key_fn in duplicate_tests:
        groups = defaultdict(list)
        for v in vendors:
            k = key_fn(v)
            if k:
                groups[k].append(v)
        for members in groups.values():
            if len(members) < 2:
                continue
            codes = [m["code"] for m in members]
            for m in members:
                others = [c for c in codes if c != m["code"]]
                if others:
                    add(m, check, f"Same {label} as {', '.join(others)}")
                else:
                    add(m, check, f"Same {label} appears in another row with the same vendor code")

    # 2. Format and completeness
    for v in vendors:
        pan_ok = bool(v["pan"]) and bool(PAN_RE.fullmatch(v["pan"]))
        if not v["pan"]:
            add(v, "Missing PAN", "PAN is blank")
        elif not pan_ok:
            add(v, "Invalid PAN format", "PAN is not in the format AAAAA9999A")

        if v["gstin"]:
            if not GSTIN_RE.fullmatch(v["gstin"]):
                add(v, "Invalid GSTIN format", "GSTIN is not a valid 15-character GST number")
            elif pan_ok and v["gstin"][2:12] != v["pan"]:
                add(v, "GSTIN does not match PAN",
                    "Characters 3 to 12 of the GSTIN differ from the vendor PAN")

        if v["ifsc"] and not IFSC_RE.fullmatch(v["ifsc"]):
            add(v, "Invalid IFSC format", "IFSC is not in the format AAAA0XXXXXX")

        blank = [lbl for lbl, val in (("bank account", v["bank"]), ("IFSC", v["ifsc"])) if not val]
        if blank:
            add(v, "Missing bank details", "Blank: " + ", ".join(blank))

        if not v["address"]:
            add(v, "Missing address", "Address is blank")

    # 3. Vendor vs employee master
    if employees:
        emp_bank, emp_pan, emp_addr = defaultdict(list), defaultdict(list), defaultdict(list)
        for e in employees:
            if e["bank"]:
                emp_bank[e["bank"]].append(e["code"])
            if e["pan"]:
                emp_pan[e["pan"]].append(e["code"])
            ak = address_key(e["address"])
            if ak:
                emp_addr[ak].append(e["code"])
        for v in vendors:
            if v["bank"] in emp_bank:
                add(v, "Bank account matches employee",
                    f"Same bank account as employee {', '.join(emp_bank[v['bank']])}")
            if v["pan"] in emp_pan:
                add(v, "PAN matches employee",
                    f"Same PAN as employee {', '.join(emp_pan[v['pan']])}")
            ak = address_key(v["address"])
            if ak in emp_addr:
                add(v, "Address matches employee",
                    f"Same address as employee {', '.join(emp_addr[ak])}")

    exceptions.sort(key=lambda e: (RISK_ORDER[e["risk"]], e["check"], e["code"]))
    return exceptions


def summarise(vendors, exceptions):
    by_check = Counter(e["check"] for e in exceptions)
    by_risk = Counter(e["risk"] for e in exceptions)
    return {
        "total_vendors": len(vendors),
        "flagged_vendors": len({e["code"] for e in exceptions}),
        "total": len(exceptions),
        "high": by_risk["High"], "medium": by_risk["Medium"], "low": by_risk["Low"],
        "by_check": by_check,
    }


# ============================================================== AI STEP
def build_prompt(stats, exceptions, employee_compared):
    check_lines = "\n".join(
        f"- {name} ({risk} risk): {stats['by_check'][name]}"
        for name, risk, _ in CHECKS if stats["by_check"][name]) or "- None"
    sample_lines = "\n".join(
        f"{e['code']} | {e['check']} | {e['detail']}"
        for e in exceptions[:MAX_SAMPLES_TO_AI]) or "None"
    return PROMPT_TEMPLATE.format(
        employee_compared="Yes" if employee_compared else "No",
        check_lines=check_lines, sample_lines=sample_lines,
        **{k: stats[k] for k in ("total_vendors", "flagged_vendors", "total",
                                 "high", "medium", "low")})


def clean_ai_text(text):
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[*\u2022]\s+", "- ", text, flags=re.M)
    return text.strip()


def ask_gemini(prompt, api_key, log):
    try:
        from google import genai
    except ImportError:
        raise RuntimeError("Gemini library not installed. Run:  pip install google-genai")
    try:
        from google.genai import types
        client = genai.Client(api_key=api_key,
                              http_options=types.HttpOptions(timeout=90000))
    except Exception:
        client = genai.Client(api_key=api_key)

    last_error = None
    for model in GEMINI_MODELS:
        try:
            log(f"  Trying model {model} ...")
            response = client.models.generate_content(model=model, contents=prompt)
            text = (response.text or "").strip()
            if text:
                return clean_ai_text(text), model
            last_error = "empty response"
        except Exception as e:
            last_error = e
            msg = str(e)
            log(f"  {model} did not work: {msg[:150]}")
            if "API_KEY_INVALID" in msg or "API key not valid" in msg:
                raise RuntimeError("The Gemini API key is not valid.") from e
    raise RuntimeError(f"No Gemini model responded ({str(last_error)[:150]})")


def rule_based_summary(stats, exceptions):
    lines = ["Observation",
             f"An automated review of {stats['total_vendors']} vendor records identified "
             f"{stats['total']} exceptions across {stats['flagged_vendors']} vendors "
             f"({stats['high']} high, {stats['medium']} medium and {stats['low']} low risk)."]
    if not exceptions:
        lines.append("No exceptions were found for the checks performed.")
        return "\n".join(lines)
    lines += ["", "Key Findings"]
    for name, risk, meaning in CHECKS:
        if stats["by_check"][name]:
            lines.append(f"- {name}: {stats['by_check'][name]} ({risk} risk). {meaning}")
    high_codes = sorted({e["code"] for e in exceptions if e["risk"] == "High"})
    lines += ["", "Recommendations"]
    if high_codes:
        lines.append("- Investigate high-risk vendors first: " + ", ".join(high_codes) + ".")
    lines += [
        "- Block or merge duplicate vendor codes after confirming with purchase and accounts teams.",
        "- Obtain and verify PAN, GSTIN and bank details (cancelled cheque) for incomplete records.",
        "- Enforce maker-checker approval and system validations for vendor creation and bank detail changes.",
        "- Repeat this review periodically, for example every quarter.",
    ]
    return "\n".join(lines)


# ============================================================== EXCEL REPORT
HEADER_FILL = PatternFill("solid", start_color="1F4E78")
RISK_STYLE = {
    "High": (PatternFill("solid", start_color="FFC7CE"), "9C0006"),
    "Medium": (PatternFill("solid", start_color="FFEB9C"), "9C5700"),
    "Low": (PatternFill("solid", start_color="C6EFCE"), "006100"),
}


def _header(ws, row, headings):
    for c, h in enumerate(headings, start=1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def _risk_cell(cell, risk):
    fill, colour = RISK_STYLE[risk]
    cell.fill = fill
    cell.font = Font(bold=True, color=colour)


def _widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _arial(wb):
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                f = cell.font
                cell.font = Font(name="Arial", size=f.size or 10, bold=f.bold,
                                 italic=f.italic, color=f.color)


def write_report(path, vendor_path, employee_path, header, data_rows, code_pos,
                 vendors, exceptions, ai_text, ai_source):
    wb = Workbook()

    # ---------- Exceptions
    ex = wb.active
    ex.title = "Exceptions"
    _header(ex, 1, ["Vendor Code", "Vendor Name", "Check", "Risk", "Detail", "Auditor Remarks"])
    for r, e in enumerate(exceptions, start=2):
        ex.cell(row=r, column=1, value=e["code"])
        ex.cell(row=r, column=2, value=e["name"])
        ex.cell(row=r, column=3, value=e["check"])
        _risk_cell(ex.cell(row=r, column=4, value=e["risk"]), e["risk"])
        ex.cell(row=r, column=5, value=e["detail"])
    _widths(ex, [13, 34, 30, 10, 48, 30])
    ex.freeze_panes = "A2"
    ex.auto_filter.ref = f"A1:F{max(2, len(exceptions) + 1)}"

    # ---------- Vendor_Review (original data + issue count)
    vr = wb.create_sheet("Vendor_Review")
    n_cols = len(header)
    count_col = n_cols + 1
    count_letter = get_column_letter(count_col)
    code_letter = get_column_letter(code_pos + 1)
    _header(vr, 1, header + ["Issues Count", "Issues"])
    issues_by_code = defaultdict(list)
    for e in exceptions:
        issues_by_code[e["code"]].append(e["check"])
    for r, (row_vals, v) in enumerate(zip(data_rows, vendors), start=2):
        row_vals = list(row_vals)
        row_vals[code_pos] = v["code"]
        for c, val in enumerate(row_vals, start=1):
            vr.cell(row=r, column=c, value=val)
        vr.cell(row=r, column=count_col,
                value=f'=COUNTIF(Exceptions!$A:$A,{code_letter}{r})')
        vr.cell(row=r, column=count_col + 1,
                value="; ".join(dict.fromkeys(issues_by_code.get(v["code"], []))))
    last = len(vendors) + 1
    if len(vendors):
        vr.conditional_formatting.add(
            f"{count_letter}2:{count_letter}{last}",
            CellIsRule(operator="greaterThan", formula=["0"],
                       fill=PatternFill("solid", start_color="FFC7CE"),
                       font=Font(bold=True, color="9C0006")))
    _widths(vr, [16] * n_cols + [13, 55])
    vr.freeze_panes = "B2"
    vr.auto_filter.ref = f"A1:{get_column_letter(count_col + 1)}{max(2, last)}"

    # ---------- AI_Observation
    ai = wb.create_sheet("AI_Observation")
    ai["A1"] = "Draft Audit Observation"
    ai["A1"].font = Font(bold=True, size=14)
    ai["A2"] = ai_source
    ai["A2"].font = Font(italic=True, color="595959")
    ai["A3"] = "Draft only: verify against the Exceptions sheet before using in a report."
    ai["A3"].font = Font(italic=True, color="9C0006")
    r = 5
    for line in ai_text.splitlines():
        cell = ai.cell(row=r, column=1, value=line)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        stripped = line.strip()
        if stripped and len(stripped) < 45 and not stripped.endswith(".") \
                and not stripped.startswith("-"):
            cell.font = Font(bold=True, color="1F4E78")
        r += 1
    ai.column_dimensions["A"].width = 120

    # ---------- Summary (first sheet)
    sm = wb.create_sheet("Summary", 0)
    sm["A1"] = "Vendor Master Risk Review"
    sm["A1"].font = Font(bold=True, size=14)
    info = [
        ("Vendor master", os.path.basename(vendor_path)),
        ("Employee master", os.path.basename(employee_path) if employee_path else "Not provided"),
        ("Run on", dt.datetime.now().strftime("%d-%b-%Y %H:%M")),
        ("Audit observation", ai_source),
    ]
    for i, (k, v) in enumerate(info, start=2):
        sm.cell(row=i, column=1, value=k).font = Font(bold=True)
        sm.cell(row=i, column=2, value=v)

    top = 7
    _header(sm, top, ["Check", "Risk", "What it means", "Exceptions"])
    first = top + 1
    for i, (name, risk, meaning) in enumerate(CHECKS):
        row = first + i
        sm.cell(row=row, column=1, value=name)
        _risk_cell(sm.cell(row=row, column=2, value=risk), risk)
        sm.cell(row=row, column=3, value=meaning).alignment = Alignment(wrap_text=True, vertical="top")
        sm.cell(row=row, column=4, value=f"=COUNTIF(Exceptions!$C:$C,A{row})")
    end = first + len(CHECKS) - 1
    tot = end + 1
    sm.cell(row=tot, column=1, value="Total exceptions").font = Font(bold=True)
    sm.cell(row=tot, column=4, value=f"=SUM(D{first}:D{end})").font = Font(bold=True)

    k = tot + 2
    key_figures = [
        ("Vendors reviewed", f"=COUNTA(Vendor_Review!${count_letter}:${count_letter})-1"),
        ("Vendors with at least one exception", f'=COUNTIF(Vendor_Review!${count_letter}:${count_letter},">0")'),
        ("High risk exceptions", '=COUNTIF(Exceptions!$D:$D,"High")'),
        ("Medium risk exceptions", '=COUNTIF(Exceptions!$D:$D,"Medium")'),
        ("Low risk exceptions", '=COUNTIF(Exceptions!$D:$D,"Low")'),
    ]
    _header(sm, k, ["Key figures", "", "", "Count"])
    for i, (label, formula) in enumerate(key_figures, start=1):
        sm.cell(row=k + i, column=1, value=label)
        sm.cell(row=k + i, column=4, value=formula)
    note = k + len(key_figures) + 2
    sm.cell(row=note, column=1,
            value="Counts are live formulas: if you delete a cleared exception from the "
                  "Exceptions sheet, this summary updates automatically.").font = Font(italic=True, color="595959")
    _widths(sm, [36, 12, 70, 12])

    _arial(wb)
    wb.calculation.fullCalcOnLoad = True
    wb.save(path)


# ============================================================== MAIN PROCESS
def run_review(vendor_path, employee_path, api_key, use_ai, log):
    log(f"Reading vendor master: {os.path.basename(vendor_path)}")
    vendors, header, data_rows, pos = read_table(vendor_path, VENDOR_COLUMNS, "Vendor master")
    prepare(vendors)
    log(f"  {len(vendors)} vendors found.")
    if not vendors:
        raise ValueError("The vendor master has headings but no data rows.")

    employees = []
    if employee_path:
        log(f"Reading employee master: {os.path.basename(employee_path)}")
        employees, *_ = read_table(employee_path, EMPLOYEE_COLUMNS, "Employee master")
        prepare(employees, has_gst_ifsc=False)
        log(f"  {len(employees)} employees found.")
    else:
        log("No employee master selected: vendor-employee checks skipped.")

    log("\nRunning checks...")
    exceptions = run_checks(vendors, employees)
    stats = summarise(vendors, exceptions)
    for name, risk, _ in CHECKS:
        if stats["by_check"][name]:
            log(f"  {name:<32}{stats['by_check'][name]:>4}   {risk}")
    log(f"Total: {stats['total']} exceptions across {stats['flagged_vendors']} of "
        f"{stats['total_vendors']} vendors (High {stats['high']}, "
        f"Medium {stats['medium']}, Low {stats['low']}).\n")

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.dirname(os.path.abspath(vendor_path))
    ai_text, ai_source = None, "Rule-based summary (AI not used)"

    if use_ai:
        prompt = build_prompt(stats, exceptions, bool(employees))
        reply = ""
        if not api_key:
            log("No Gemini API key entered: using rule-based summary.")
        else:
            log("Sending exception summary to Gemini (no PAN, GSTIN or bank numbers are sent)...")
            try:
                ai_text, model = ask_gemini(prompt, api_key, log)
                ai_source = f"Drafted by Google Gemini ({model})"
                reply = ai_text
                log("  AI observation received.")
            except Exception as e:
                log(f"  AI step failed: {str(e)[:200]}")
                log("  Using rule-based summary instead.")
                ai_source = "Rule-based summary (AI call failed)"
        prompt_path = os.path.join(out_dir, f"AI_Prompt_and_Response_{stamp}.txt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write("=== PROMPT SENT TO GEMINI ===\n\n" + prompt)
            f.write("\n\n=== RESPONSE ===\n\n" + (reply or "(no AI response - " + ai_source + ")"))
        log(f"Prompt saved: {prompt_path}")

    if ai_text is None:
        ai_text = rule_based_summary(stats, exceptions)

    report_path = os.path.join(out_dir, f"Vendor_Risk_Report_{stamp}.xlsx")
    write_report(report_path, vendor_path, employee_path, header, data_rows,
                 pos["code"], vendors, exceptions, ai_text, ai_source)
    log(f"Report saved: {report_path}")
    return report_path


# ============================================================== WINDOW
class App:
    def __init__(self, root):
        self.root = root
        root.title("Vendor Master Risk Checker")
        root.geometry("820x600")
        root.minsize(680, 480)
        self.q = queue.Queue()
        self.report_path = None

        frm = ttk.Frame(root, padding=14)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Vendor Master Risk Checker",
                  font=("Segoe UI", 16, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frm, text="AICA Level 2 Capstone  |  Rule-based checks + Gemini audit observation",
                  foreground="#555555").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.vendor_var = tk.StringVar()
        self.emp_var = tk.StringVar()
        self.key_var = tk.StringVar(value=os.environ.get("GEMINI_API_KEY", ""))
        self.ai_var = tk.BooleanVar(value=True)

        self._file_row(frm, 2, "Vendor master file:", self.vendor_var)
        self._file_row(frm, 3, "Employee master (optional):", self.emp_var)
        ttk.Label(frm, text="Gemini API key:").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.key_var, show="*").grid(row=4, column=1, sticky="we", pady=4)
        ttk.Checkbutton(frm, text="Use AI to draft the audit observation",
                        variable=self.ai_var).grid(row=5, column=1, sticky="w")

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=3, sticky="w", pady=12)
        self.run_btn = ttk.Button(btns, text="Run Checks", command=self.start)
        self.run_btn.pack(side="left")
        self.open_btn = ttk.Button(btns, text="Open Report", command=self.open_report,
                                   state="disabled")
        self.open_btn.pack(side="left", padx=8)

        self.log_box = ScrolledText(frm, height=16, font=("Consolas", 10), state="disabled")
        self.log_box.grid(row=7, column=0, columnspan=3, sticky="nsew")
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(7, weight=1)
        self.root.after(100, self.poll)

    def _file_row(self, frm, row, label, var):
        ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=var).grid(row=row, column=1, sticky="we", pady=4, padx=(0, 6))
        ttk.Button(frm, text="Browse...",
                   command=lambda: self._browse(var)).grid(row=row, column=2, pady=4)

    def _browse(self, var):
        path = filedialog.askopenfilename(
            filetypes=[("Excel or CSV", "*.xlsx *.xlsm *.csv"), ("All files", "*.*")])
        if path:
            var.set(path)

    def log(self, text):
        self.q.put(("log", text))

    def _write(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def start(self):
        vendor = self.vendor_var.get().strip()
        emp = self.emp_var.get().strip()
        if not vendor or not os.path.exists(vendor):
            messagebox.showwarning("Vendor file", "Please select the vendor master file.")
            return
        if emp and not os.path.exists(emp):
            messagebox.showwarning("Employee file", "The employee master file was not found.")
            return
        use_ai = self.ai_var.get()
        key = self.key_var.get().strip()
        if use_ai and not key:
            if not messagebox.askyesno("No API key",
                                       "No Gemini API key entered.\n\n"
                                       "Continue with a rule-based summary instead of AI?"):
                return
        self.run_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        threading.Thread(target=self._worker, args=(vendor, emp or None, key, use_ai),
                         daemon=True).start()

    def _worker(self, vendor, emp, key, use_ai):
        try:
            path = run_review(vendor, emp, key, use_ai, self.log)
            self.q.put(("done", path))
        except Exception as e:
            self.q.put(("error", str(e)))

    def poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self._write(payload)
                elif kind == "done":
                    self.report_path = payload
                    self.run_btn.configure(state="normal")
                    self.open_btn.configure(state="normal")
                    self._write("\nDone. Click 'Open Report' to view the results.")
                elif kind == "error":
                    self.run_btn.configure(state="normal")
                    self._write("\nERROR: " + payload)
                    messagebox.showerror("Error", payload)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def open_report(self):
        if not self.report_path:
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(self.report_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.report_path])
            else:
                subprocess.Popen(["xdg-open", self.report_path])
        except Exception as e:
            messagebox.showerror("Open Report", f"Could not open the report:\n{e}")


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista" if sys.platform.startswith("win") else "clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
