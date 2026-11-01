"""
validators.py - OFFLINE validation rules for PAN, GSTIN and Udyam Registration Number.

Vendor Registration & Validation App | AICA Level-2 Capstone Project
All rules here run without internet. Each check returns a CheckResult so that
the report can colour the exact field that failed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from difflib import SequenceMatcher

PASS, WARN, FAIL, NA = "PASS", "WARNING", "FAIL", "NOT PROVIDED"

# ---------------------------------------------------------------- reference data
PAN_ENTITY = {
    "P": "Individual",
    "C": "Company",
    "H": "Hindu Undivided Family (HUF)",
    "F": "Firm / LLP",
    "E": "Limited Liability Partnership (LLP)",
    "A": "Association of Persons (AOP)",
    "T": "Trust",
    "B": "Body of Individuals (BOI)",
    "L": "Local Authority",
    "J": "Artificial Juridical Person",
    "G": "Government",
}

# Declared constitution (Excel drop-down) -> allowed 4th character(s) of PAN
CONSTITUTION_TO_PAN = {
    "PROPRIETORSHIP": {"P"},
    "INDIVIDUAL": {"P"},
    "HUF": {"H"},
    "PARTNERSHIP FIRM": {"F"},
    "LLP": {"F", "E"},
    "PRIVATE LIMITED COMPANY": {"C"},
    "PUBLIC LIMITED COMPANY": {"C"},
    "ONE PERSON COMPANY": {"C"},
    "TRUST": {"T"},
    "SOCIETY": {"A", "T"},
    "AOP / BOI": {"A", "B"},
    "GOVERNMENT": {"G"},
    "LOCAL AUTHORITY": {"L"},
}

GST_STATE = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "25": "Daman and Diu", "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra",
    "28": "Andhra Pradesh (Old)", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala",
    "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman and Nicobar Islands", "36": "Telangana",
    "37": "Andhra Pradesh", "38": "Ladakh", "97": "Other Territory", "99": "Centre Jurisdiction",
}

# Udyam state codes (2 letters in UDYAM-XX-00-0000000) -> GST state code
UDYAM_STATE = {
    "JK": "01", "HP": "02", "PB": "03", "CH": "04", "UK": "05", "UT": "05", "HR": "06", "DL": "07",
    "RJ": "08", "UP": "09", "BR": "10", "SK": "11", "AR": "12", "NL": "13", "MN": "14", "MZ": "15",
    "TR": "16", "ML": "17", "AS": "18", "WB": "19", "JH": "20", "OD": "21", "OR": "21", "CG": "22",
    "CT": "22", "MP": "23", "GJ": "24", "DD": "26", "DN": "26", "MH": "27", "KR": "29", "KA": "29",
    "GA": "30", "LD": "31", "KL": "32", "TN": "33", "PY": "34", "AN": "35", "TS": "36", "TG": "36",
    "AP": "37", "LA": "38",
}

GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
RE_PAN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
RE_GSTIN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z][A-Z0-9][0-9A-Z]$")
RE_UDYAM = re.compile(r"^UDYAM-([A-Z]{2})-([0-9]{2})-([0-9]{7})$")
RE_OLD_UAM = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z][0-9]{7}$")      # old Udyog Aadhaar e.g. MH12A0012345
NAME_PREFIXES = ("M/S.", "M/S", "MS.", "MESSRS", "THE ", "SHRI ", "SMT. ", "SMT ", "MR. ", "MRS. ", "DR. ")


# ---------------------------------------------------------------- data classes
@dataclass
class CheckResult:
    department: str          # PAN / GST / UDYAM / GENERAL
    field: str               # Excel column the check relates to (used for highlighting)
    check: str               # name of the rule
    status: str              # PASS / WARNING / FAIL / NOT PROVIDED
    message: str
    stage: str = "Offline"   # Offline / Online


@dataclass
class Vendor:
    row: int
    sr_no: str
    vendor_code: str
    name: str
    constitution: str
    pan: str
    gstin: str
    udyam: str
    state: str = ""
    address: str = ""
    email: str = ""
    auth_person: str = ""
    checks: list = field(default_factory=list)
    online: dict = field(default_factory=dict)   # {"PAN": {...}, "GST": {...}, "UDYAM": {...}}

    # ---- helpers used by report / GUI
    def status_of(self, department: str, stage: str | None = None) -> str:
        rel = [c for c in self.checks if c.department == department and (stage is None or c.stage == stage)]
        if not rel:
            return ""
        for s in (FAIL, WARN):
            if any(c.status == s for c in rel):
                return s
        if all(c.status == NA for c in rel):
            return NA
        return PASS

    def field_status(self, fld: str) -> str:
        rel = [c.status for c in self.checks if c.field == fld]
        if FAIL in rel:
            return FAIL
        if WARN in rel:
            return WARN
        if rel and all(s == NA for s in rel):
            return NA
        return PASS if rel else ""

    def overall(self) -> str:
        sts = [c.status for c in self.checks]
        if FAIL in sts:
            return "REJECT / FIX"
        if WARN in sts:
            return "REVIEW"
        return "APPROVED"


# ---------------------------------------------------------------- utilities
def clean(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"\s+", " ", str(v)).strip()


def norm_name(name: str) -> str:
    n = clean(name).upper()
    for p in NAME_PREFIXES:
        if n.startswith(p):
            n = n[len(p):].strip()
    n = re.sub(r"[^A-Z0-9 ]", " ", n)
    n = re.sub(r"\b(PRIVATE|PVT|LIMITED|LTD|LLP|CO|COMPANY|AND|THE)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def name_similarity(a: str, b: str) -> float:
    a, b = norm_name(a), norm_name(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # token-set comparison handles "SHARMA RAVI" vs "RAVI SHARMA"
    ta, tb = set(a.split()), set(b.split())
    token = len(ta & tb) / max(len(ta | tb), 1)
    return max(SequenceMatcher(None, a, b).ratio(), token)


def parse_date(v) -> date | None:
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = clean(v)
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d-%b-%Y", "%d %b %Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def gstin_check_digit(first14: str) -> str:
    """GSTN mod-36 check digit (Luhn-style)."""
    total = 0
    for i, ch in enumerate(first14):
        product = GST_CHARS.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return GST_CHARS[(36 - total % 36) % 36]


# ---------------------------------------------------------------- PAN rules
def validate_pan(v: Vendor) -> list[CheckResult]:
    out, pan = [], v.pan
    R = lambda chk, st, msg, fld="PAN": out.append(CheckResult("PAN", fld, chk, st, msg))

    if not pan:
        R("PAN provided", FAIL, "PAN is mandatory for vendor registration (Sec. 206AA higher TDS if not available).")
        return out
    if len(pan) != 10:
        R("Length", FAIL, f"PAN must have 10 characters; found {len(pan)}.")
        return out
    if not RE_PAN.match(pan):
        R("Structure", FAIL, "PAN must be 5 letters + 4 digits + 1 letter (e.g. ABCPE1234F).")
        return out
    R("Structure", PASS, "Format AAAAA9999A is correct.")

    t = pan[3]
    if t not in PAN_ENTITY:
        R("Holder type (4th char)", FAIL, f"4th character '{t}' is not a valid PAN holder type.")
    else:
        R("Holder type (4th char)", PASS, f"4th character '{t}' = {PAN_ENTITY[t]}.")
        cons = v.constitution.upper()
        if cons:
            allowed = CONSTITUTION_TO_PAN.get(cons)
            if allowed is None:
                R("Constitution vs PAN", WARN, f"Constitution '{v.constitution}' not in master list; check manually.", "Constitution")
            elif t not in allowed:
                R("Constitution vs PAN", FAIL,
                  f"Declared '{v.constitution}' but PAN 4th character '{t}' indicates {PAN_ENTITY[t]}.", "Constitution")
            else:
                R("Constitution vs PAN", PASS, "Declared constitution matches PAN holder type.", "Constitution")

    # 5th character = first letter of surname (individual) / name (others)
    n = norm_name(v.name)
    if n:
        letters = {w[0] for w in n.split()}
        if pan[4] in letters:
            R("Name initial (5th char)", PASS, f"5th character '{pan[4]}' matches an initial of the vendor name.")
        else:
            R("Name initial (5th char)", WARN,
              f"5th character '{pan[4]}' does not match any word of '{v.name}'. Verify name as per PAN.", "Vendor Name")
    else:
        R("Vendor name", FAIL, "Vendor name (as per PAN) is blank.", "Vendor Name")

    return out


# ---------------------------------------------------------------- GSTIN rules
def validate_gstin(v: Vendor) -> list[CheckResult]:
    out, g = [], v.gstin
    R = lambda chk, st, msg, fld="GSTIN": out.append(CheckResult("GST", fld, chk, st, msg))

    if not g:
        R("GSTIN provided", NA, "No GSTIN - treat as unregistered vendor (RCM under Sec. 9(4) may apply).")
        return out
    if len(g) != 15:
        R("Length", FAIL, f"GSTIN must have 15 characters; found {len(g)}.")
        return out
    if not RE_GSTIN.match(g):
        R("Structure", FAIL, "GSTIN must be 2-digit state + PAN + entity no. + 'Z' + check digit.")
        return out
    R("Structure", PASS, "Format is correct.")

    st = g[:2]
    if st not in GST_STATE:
        R("State code", FAIL, f"State code '{st}' does not exist.")
    else:
        R("State code", PASS, f"State code {st} = {GST_STATE[st]}.")
        if v.state and GST_STATE[st].upper() != v.state.upper():
            R("State vs address", WARN, f"GSTIN is of {GST_STATE[st]} but vendor state given as '{v.state}'.", "State")

    if g[13] != "Z":
        R("14th character", WARN, f"14th character is '{g[13]}' (normally 'Z'); may be TDS/TCS/UIN registration.")

    exp = gstin_check_digit(g[:14])
    if g[14] != exp:
        R("Check digit", FAIL, f"Check digit should be '{exp}' but is '{g[14]}' - GSTIN is mistyped / invalid.")
    else:
        R("Check digit", PASS, "Mod-36 check digit is correct.")

    if v.pan and RE_PAN.match(v.pan):
        if g[2:12] != v.pan:
            R("PAN inside GSTIN", FAIL, f"Characters 3-12 of GSTIN ({g[2:12]}) do not match PAN {v.pan}.")
        else:
            R("PAN inside GSTIN", PASS, "Embedded PAN matches vendor PAN.")
    return out


# ---------------------------------------------------------------- Udyam rules
def validate_udyam(v: Vendor) -> list[CheckResult]:
    out, u = [], v.udyam
    R = lambda chk, st, msg, fld="Udyam No": out.append(CheckResult("UDYAM", fld, chk, st, msg))

    if not u:
        R("Udyam provided", NA, "No Udyam number - vendor treated as Non-MSME; obtain declaration.")
        return out
    if RE_OLD_UAM.match(u.replace("-", "")) and not u.startswith("UDYAM"):
        R("Structure", FAIL, "This is an old Udyog Aadhaar (UAM) number - no longer valid. Obtain Udyam Registration.")
        return out
    m = RE_UDYAM.match(u)
    if not m:
        R("Structure", FAIL, "Udyam number must be in format UDYAM-XX-00-0000000.")
        return out
    R("Structure", PASS, "Format UDYAM-XX-00-0000000 is correct.")

    sc = m.group(1)
    if sc not in UDYAM_STATE:
        R("State code", FAIL, f"State code '{sc}' in Udyam number is not valid.")
    else:
        R("State code", PASS, f"State code {sc} is valid.")
        if v.gstin and len(v.gstin) >= 2 and v.gstin[:2] in GST_STATE and UDYAM_STATE[sc] != v.gstin[:2]:
            R("State vs GSTIN", WARN,
              f"Udyam state ({sc}) differs from GSTIN state ({GST_STATE[v.gstin[:2]]}). Possible but verify.")
    if m.group(2) == "00":
        R("District code", WARN, "District code '00' - verify on certificate.")
    return out


RE_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
RE_PIN = re.compile(r"\b([1-9][0-9]{2})\s?([0-9]{3})\b")


def pincode(text: str) -> str:
    m = RE_PIN.search(text or "")
    return m.group(1) + m.group(2) if m else ""


def validate_contact(v: Vendor) -> list[CheckResult]:
    out = []
    R = lambda fld, chk, st, msg: out.append(CheckResult("GENERAL", fld, chk, st, msg))
    if not v.auth_person:
        R("Authorised Person", "Authorised person", WARN, "Name of authorised person / contact is blank.")
    else:
        R("Authorised Person", "Authorised person", PASS, "Authorised person given.")
    if not v.email:
        R("Email ID", "Email ID", WARN, "Email ID is blank - needed for PO, TDS certificates and MSME confirmations.")
    elif not RE_EMAIL.match(v.email):
        R("Email ID", "Email ID", FAIL, f"'{v.email}' is not a valid email address.")
    else:
        R("Email ID", "Email ID", PASS, "Email format is valid.")
    if not v.address:
        R("Address", "Address", WARN, "Address is blank.")
    elif not pincode(v.address):
        R("Address", "PIN code", WARN, "No 6-digit PIN code found in the address.")
    else:
        R("Address", "PIN code", PASS, f"PIN code {pincode(v.address)} found.")
    return out


def validate_duplicates(vendors: list[Vendor]) -> None:
    for key, dept, fld in (("pan", "PAN", "PAN"), ("gstin", "GST", "GSTIN"), ("udyam", "UDYAM", "Udyam No")):
        seen: dict[str, list[Vendor]] = {}
        for v in vendors:
            val = getattr(v, key)
            if val:
                seen.setdefault(val, []).append(v)
        for val, vs in seen.items():
            if len(vs) > 1:
                codes = ", ".join(x.vendor_code or str(x.row) for x in vs)
                for x in vs:
                    x.checks.append(CheckResult(dept, fld, "Duplicate in master", WARN,
                                                f"{fld} {val} appears for vendor codes: {codes}."))


def run_offline(vendors: list[Vendor]) -> None:
    for v in vendors:
        v.checks = [c for c in v.checks if c.stage != "Offline"]
        v.checks += validate_pan(v) + validate_gstin(v) + validate_udyam(v) + validate_contact(v)
    validate_duplicates(vendors)


# ---------------------------------------------------------------- MSME / 43B(h)
TRADING_NIC_2DIGIT = {"45", "46", "47"}   # Wholesale & retail trade divisions of NIC-2008


def msme_43bh_status(udyam_data: dict, invoice_date: date | None = None) -> tuple[str, str]:
    """Return (Yes/No/Review, reason) for Sec. 43B(h) of IT Act 1961 / Sec. 37(2)(g) of IT Act 2025."""
    if not udyam_data:
        return "No", "No Udyam registration on record."
    rows = udyam_data.get("enterprise_types") or []
    chosen = None
    if rows:
        chosen = rows[-1]
        if invoice_date:
            valid = [r for r in rows if parse_date(r.get("classification_date")) and
                     parse_date(r["classification_date"]) <= invoice_date]
            chosen = valid[-1] if valid else None
            if chosen is None:
                return "No", "Invoice is before the first classification date (registration is prospective)."
    etype = (chosen or {}).get("enterprise_type", udyam_data.get("enterprise_type", "")).upper()
    nic = udyam_data.get("nic_2digit", [])
    trading_only = bool(nic) and all(str(n)[:2] in TRADING_NIC_2DIGIT for n in nic)
    if "MEDIUM" in etype:
        return "No", "Medium enterprise - 43B(h) applies only to Micro & Small."
    if etype in ("MICRO", "SMALL") or "MICRO" in etype or "SMALL" in etype:
        if trading_only:
            return "Review", f"{etype.title()} but NIC codes are trading (45/46/47) - traders not covered under MSMED Act Sec. 15."
        return "Yes", f"{etype.title()} enterprise - pay within 15/45 days (Sec. 15 MSMED Act)."
    return "Review", "Enterprise type not captured - verify certificate."
