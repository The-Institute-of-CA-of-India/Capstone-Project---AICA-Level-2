"""Small shared helpers: money, dates, periods, financial years."""
from __future__ import annotations

import calendar
import datetime as dt
import hashlib
import re
import secrets
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def D(value: Any, default: Decimal | None = ZERO) -> Decimal | None:
    """Convert anything (str/int/Decimal/None/'1,23,456.00') to a 2-dp Decimal. Never uses float maths."""
    if value is None or value == "":
        return default
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, bool):
        return default
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, float):
        d = Decimal(repr(value))  # repr is the shortest round-tripping string
    else:
        s = str(value).strip().replace(",", "").replace("₹", "").replace("Rs.", "").replace("INR", "").strip()
        neg = False
        if s.endswith("-") or (s.startswith("(") and s.endswith(")")):
            neg, s = True, s.strip("()-")
        if s.lower().endswith(("dr", "cr")):
            s = s[:-2].strip()
        try:
            d = Decimal(s)
        except (InvalidOperation, ValueError):
            return default
        if neg:
            d = -d
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


def money(value: Any) -> str:
    """Indian-style grouping: 12,34,567.89"""
    d = D(value) or ZERO
    neg = d < 0
    d = abs(d)
    whole, frac = f"{d:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{'-' if neg else ''}{whole}.{frac}"


def to_date(value: Any) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    s = str(value).strip()
    if "T" in s:
        s = s.split("T")[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d-%b-%Y", "%d %b %Y",
                "%d-%b-%y", "%d %B %Y", "%b %d, %Y", "%d %b, %Y", "%d-%B-%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def fy_label_for(date: dt.date, start_month: int = 4) -> str:
    start_year = date.year if date.month >= start_month else date.year - 1
    if start_month == 1:
        return str(start_year)
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def fy_bounds(label: str, start_month: int = 4) -> tuple[dt.date, dt.date]:
    start_year = int(label[:4])
    start = dt.date(start_year, start_month, 1)
    end_year = start_year + 1 if start_month != 1 else start_year
    end_month = start_month - 1 if start_month != 1 else 12
    return start, month_end(end_year, end_month)


def fy_months(label: str, start_month: int = 4) -> list[tuple[int, int]]:
    start, _ = fy_bounds(label, start_month)
    out, y, m = [], start.year, start.month
    for _ in range(12):
        out.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def month_end(year: int, month: int) -> dt.date:
    return dt.date(year, month, calendar.monthrange(year, month)[1])


def month_bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    return dt.date(year, month, 1), month_end(year, month)


def month_label(year: int, month: int) -> str:
    return f"{calendar.month_abbr[month]} {year}"


def prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def gst_period(year: int, month: int) -> str:
    return f"{month:02d}{year}"


def parse_gst_period(period: str) -> tuple[int, int]:
    return int(period[2:]), int(period[:2])


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def normalize_invoice_no(no: str | None) -> str:
    """Normalise invoice numbers for matching: uppercase, strip separators and leading zeros."""
    if not no:
        return ""
    s = re.sub(r"[^A-Za-z0-9]", "", str(no)).upper()
    return s.lstrip("0") or s


def normalize_name(name: str | None) -> str:
    if not name:
        return ""
    s = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    for w in (" pvt", " private", " ltd", " limited", " llp", " and", " co ", " the "):
        s = s.replace(w, " ")
    return " ".join(s.split())


def name_similarity(a: str | None, b: str | None) -> float:
    """Token-overlap similarity 0..1 (deterministic, no external deps)."""
    ta, tb = set(normalize_name(a).split()), set(normalize_name(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def is_past(value: Any) -> bool:
    """True if a timestamp (ISO string or datetime, from either backend) is in the past."""
    if value is None or value == "":
        return True
    v = value if isinstance(value, dt.datetime) else dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if v.tzinfo is None:
        v = v.replace(tzinfo=dt.timezone.utc)
    return v < dt.datetime.now(dt.timezone.utc)
