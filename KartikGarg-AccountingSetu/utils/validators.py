"""Deterministic validators for GST / invoice data."""
from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

from utils.helpers import D, ZERO, to_date

GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
INVOICE_NO_RE = re.compile(r"^[A-Za-z0-9/\-]{1,16}$")  # CGST Rule 46(b): max 16 chars, / and - allowed

STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand",
    "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur", "15": "Mizoram", "16": "Tripura",
    "17": "Meghalaya", "18": "Assam", "19": "West Bengal", "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh",
    "23": "Madhya Pradesh", "24": "Gujarat", "25": "Daman and Diu", "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra", "28": "Andhra Pradesh (Old)", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep",
    "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman and Nicobar Islands", "36": "Telangana",
    "37": "Andhra Pradesh", "38": "Ladakh", "97": "Other Territory", "96": "Other Country",
}
VALID_GST_RATES = {Decimal(x) for x in ("0", "0.1", "0.25", "1", "1.5", "3", "5", "6", "7.5", "12", "18", "28", "40")}


def gstin_checksum(gstin14: str) -> str:
    total = 0
    for i, ch in enumerate(gstin14):
        val = GSTIN_CHARS.index(ch)
        prod = val * (1 if i % 2 == 0 else 2)
        total += prod // 36 + prod % 36
    return GSTIN_CHARS[(36 - total % 36) % 36]


def validate_gstin(gstin: str | None) -> tuple[bool, str]:
    if not gstin:
        return False, "GSTIN missing"
    g = gstin.strip().upper()
    if len(g) != 15:
        return False, "GSTIN must be 15 characters"
    if not GSTIN_RE.match(g):
        return False, "GSTIN format invalid"
    if g[:2] not in STATE_CODES:
        return False, f"Invalid state code {g[:2]}"
    if gstin_checksum(g[:14]) != g[14]:
        return False, "GSTIN checksum digit invalid"
    return True, "ok"


def make_gstin(state_code: str, pan: str, entity: str = "1") -> str:
    """Build a checksum-valid GSTIN (used for test data and the demo seed)."""
    base = f"{state_code}{pan}{entity}Z"
    return base + gstin_checksum(base)


def validate_pan(pan: str | None) -> bool:
    return bool(pan) and bool(PAN_RE.match(pan.strip().upper()))


def validate_invoice_no(no: str | None) -> tuple[bool, str]:
    if not no or not str(no).strip():
        return False, "Invoice number missing"
    if not INVOICE_NO_RE.match(str(no).strip()):
        return False, "Invoice number must be ≤16 characters using letters, digits, '/' or '-' (Rule 46)"
    return True, "ok"


def validate_invoice_date(value, period_start: dt.date | None = None, period_end: dt.date | None = None) -> tuple[bool, str]:
    d = to_date(value)
    if d is None:
        return False, "Invoice date missing or unreadable"
    if d > dt.date.today():
        return False, "Invoice date is in the future"
    if d < dt.date(2017, 7, 1):
        return False, "Invoice date is before GST (1 Jul 2017)"
    if period_start and period_end and not (period_start <= d <= period_end):
        return True, "Invoice date outside the submission month (check period)"
    return True, "ok"


def is_interstate(supplier_state: str | None, place_of_supply: str | None) -> bool | None:
    if not supplier_state or not place_of_supply:
        return None
    return supplier_state[:2] != place_of_supply[:2]


def validate_tax_amounts(data: dict, tolerance: Decimal = Decimal("1.00")) -> list[dict]:
    """Return a list of issues {field, severity, message} for the amount fields of an invoice."""
    issues: list[dict] = []
    taxable = D(data.get("taxable_value"), None)
    cgst, sgst, igst = D(data.get("cgst")), D(data.get("sgst")), D(data.get("igst"))
    cess, disc, ro = D(data.get("cess")), D(data.get("discount")), D(data.get("round_off"))
    total = D(data.get("total"), None)
    if taxable is None:
        issues.append({"field": "taxable_value", "severity": "error", "message": "Taxable value missing"})
    elif taxable < 0:
        issues.append({"field": "taxable_value", "severity": "error", "message": "Taxable value is negative"})
    if total is None:
        issues.append({"field": "total", "severity": "error", "message": "Invoice total missing"})
    if igst and (cgst or sgst):
        issues.append({"field": "igst", "severity": "error", "message": "Both IGST and CGST/SGST charged on one invoice"})
    if abs(cgst - sgst) > Decimal("0.05"):
        issues.append({"field": "sgst", "severity": "error", "message": f"CGST ({cgst}) and SGST ({sgst}) differ"})
    if taxable and taxable > 0:
        tax = igst if igst else cgst + sgst
        rate = (tax * 100 / taxable).quantize(Decimal("0.01"))
        nearest = min(VALID_GST_RATES, key=lambda r: abs(r - rate))
        if tax and abs(nearest - rate) > Decimal("0.6"):
            issues.append({"field": "igst" if igst else "cgst", "severity": "warning",
                           "message": f"Effective GST rate {rate}% is not a standard rate"})
        # Mixed-rate invoices legitimately produce non-standard blended rates; only a warning.
        data["_effective_rate"] = str(nearest if abs(nearest - rate) <= Decimal("0.6") else rate)
    if taxable is not None and total is not None:
        expected = taxable + cgst + sgst + igst + cess + ro
        if abs(expected - total) > tolerance:
            # Some invoices show taxable before discount: try again with discount.
            if abs(expected - disc - total) > tolerance:
                issues.append({"field": "total", "severity": "error",
                               "message": f"Total {total} ≠ taxable + taxes + round-off ({expected})"})
    if abs(ro) > Decimal("1.00"):
        issues.append({"field": "round_off", "severity": "warning", "message": f"Round-off {ro} exceeds ₹1"})
    return issues


def gstin_state(gstin: str | None) -> str | None:
    if gstin and len(gstin) >= 2 and gstin[:2].isdigit():
        return gstin[:2]
    return None


def parse_place_of_supply(value: str | None) -> str | None:
    """'07-Delhi' / 'Delhi (07)' / 'Maharashtra' -> '07'/'27'."""
    if not value:
        return None
    m = re.search(r"\b(\d{2})\b", str(value))
    if m and m.group(1) in STATE_CODES:
        return m.group(1)
    v = str(value).strip().lower()
    for code, name in STATE_CODES.items():
        if name.lower() == v or (len(v) > 4 and name.lower().startswith(v)):
            return code
    return None


ZERO_DEC = ZERO
