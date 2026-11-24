"""Money helpers. All amounts are stored as integer paise to avoid rounding errors."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def rupees(value) -> int:
    """Convert a rupee amount (int, float, str or Decimal) to integer paise."""
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_paise(text: str) -> int:
    """Parse a rupee string such as '1,23,456.78' or '' into paise."""
    text = (text or "").strip().replace(",", "")
    return rupees(text) if text else 0


def paise_to_str(p: int) -> str:
    """Plain decimal string, e.g. -12345 -> '-123.45'."""
    sign = "-" if p < 0 else ""
    p = abs(p)
    return f"{sign}{p // 100}.{p % 100:02d}"


def fmt_num(minor: int, currency: str = "INR") -> str:
    """Number only, no symbol: Indian grouping for INR (1,23,456.78), western for others (123,456.78)."""
    if currency == "INR":
        return fmt_inr(minor).replace("Rs ", "")
    sign = "-" if minor < 0 else ""
    return f"{sign}{abs(minor) / 100:,.2f}"


def parse_amount(text: str) -> int:
    """Parse '1,23,456.78', '123,456.78 Dr', '(500.00)' etc. into signed minor units.
    'Dr' or brackets make the value negative."""
    t = (text or "").strip().upper()
    if not t:
        return 0
    neg = t.endswith("DR") or (t.startswith("(") and t.endswith(")"))
    t = t.replace("DR", "").replace("CR", "").strip("() ").replace(",", "").replace(" ", "")
    v = rupees(t)
    return -v if neg else v


def fmt_amount(minor: int, currency: str = "INR") -> str:
    """Format minor units in the account's currency."""
    if currency == "INR":
        return fmt_inr(minor)
    sign = "-" if minor < 0 else ""
    return f"{sign}{currency} {abs(minor) / 100:,.2f}"


def fmt_inr(p: int) -> str:
    """Indian grouping, e.g. 1234567800 -> 'Rs 1,23,45,678.00'."""
    sign = "-" if p < 0 else ""
    p = abs(p)
    whole = str(p // 100)
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}Rs {whole}.{p % 100:02d}"
