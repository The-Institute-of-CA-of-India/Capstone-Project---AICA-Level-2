"""Small shared helpers: number parsing, dates, hashing, ISIN decoding."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

# --------------------------------------------------------------------------- numbers

_NUM_RE = re.compile(r"^\(?[-−]?[\d,]*\.?\d+\)?$")


def num(text) -> float:
    """Parse '1,79,250.00', '(595497.05)', '−610673.05', '-' into float.

    Brackets and the unicode minus both mean negative. A lone '-' is zero.
    """
    if text is None:
        return 0.0
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).strip().replace("−", "-").replace("`", "").replace("₹", "")
    if s in ("", "-", "--"):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "")
    val = float(s)
    return -val if neg else val


def is_num(text: str) -> bool:
    s = str(text).strip().replace("−", "-")
    return s == "-" or bool(_NUM_RE.match(s))


def r2(x: float) -> float:
    """Round half up to 2 decimals (accounting rounding, not banker's)."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# --------------------------------------------------------------------------- dates

_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%b %d %Y", "%d %b %Y", "%Y-%m-%d", "%d-%b-%Y")


def to_date(text: str) -> str:
    """Return ISO date string (YYYY-MM-DD) from the common contract-note formats."""
    s = re.sub(r"\s+", " ", str(text).strip())
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date: {text!r}")


# --------------------------------------------------------------------------- hashing

def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- ISIN

ISSUER_TYPES = {
    "E": "Companies, Statutory Corporations, Banking Companies",
    "F": "Mutual Funds",
    "A": "Central Government Securities",
    "B": "State Government Securities",
    "C": "Municipal Corporations",
    "D": "Union Territories",
    "9": "Special Rights Equity / Specialised Instruments",
}

SECURITY_TYPES = {
    "01": "Equity Shares (or Mutual Fund Units)",
    "02": "Postal Savings Scheme",
    "03": "Preference Shares",
    "04": "Bonds",
    "05": "Deep Discount Bonds",
    "06": "Floating Rate Bonds",
    "07": "Commercial Papers",
    "08": "Unsecured Debentures",
    "09": "Regular Return Bonds",
    "10": "Certificates of Deposit",
    "11": "Securitized Instruments",
    "12": "Debentures",
    "13": "Units",
    "14": "Government Securities (G-Sec) / Commercial Papers",
    "15": "Warrants",
    "16": "Commodities",
    "17": "RBI Relief Bonds / NSC (VII issue)",
}

ISIN_RE = re.compile(r"\bIN[A-Z0-9]{10}\b")


def isin_check_digit_ok(isin: str) -> bool:
    """Validate the 12th character (Luhn on the letter-expanded string)."""
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", isin or ""):
        return False
    digits = "".join(str(int(c, 36)) for c in isin[:-1])
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10 == int(isin[-1])


def decode_isin(isin: str) -> dict:
    isin = (isin or "").strip().upper()
    out = {"Country": "", "Issuer Code": "", "Issuer Type": "",
           "Security Type Code": "", "Security Type": "", "ISIN Valid": ""}
    if len(isin) != 12:
        return out
    out["Country"] = "India" if isin.startswith("IN") else isin[:2]
    out["Issuer Code"] = isin[2]
    out["Issuer Type"] = ISSUER_TYPES.get(isin[2], "")
    out["Security Type Code"] = isin[7:9]
    out["Security Type"] = SECURITY_TYPES.get(isin[7:9], "")
    out["ISIN Valid"] = "Yes" if isin_check_digit_ok(isin) else "Check"
    return out


def default_asset_class(isin: str) -> str:
    """First guess of asset class; the Scrip Master overrides it."""
    if len(isin) != 12:
        return ""
    issuer, code = isin[2], isin[7:9]
    if issuer == "F":
        return "Mutual Fund / ETF"
    if issuer in "AB":
        return "Government Security"
    if code == "01":
        return "Equity"
    if code == "03":
        return "Preference Shares"
    if code in ("04", "05", "06", "09", "12", "08"):
        return "Bond / Debenture"
    if code == "15":
        return "Warrants"
    return SECURITY_TYPES.get(code, "Other")
