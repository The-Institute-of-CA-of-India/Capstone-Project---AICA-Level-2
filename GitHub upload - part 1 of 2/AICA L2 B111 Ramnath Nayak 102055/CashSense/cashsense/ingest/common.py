"""Common statement model and the Python checks that every reading must pass."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

DATE_FORMATS = ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d %b %Y", "%d/%m/%y", "%d-%m-%y")


def parse_date(text: str) -> date:
    text = (text or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date: {text!r}")


@dataclass
class ParsedLine:
    txn_date: date
    description: str
    amount_minor: int          # + credit / - debit
    balance_minor: int         # signed: negative = Dr
    ref_no: str = ""
    value_date: date | None = None
    legible: bool = True


@dataclass
class ParsedStatement:
    source_format: str
    account_no: str = ""
    period_from: date | None = None
    period_to: date | None = None
    currency: str = "INR"
    opening_minor: int | None = None
    closing_minor: int | None = None
    lines: list[ParsedLine] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    repairs: list[str] = field(default_factory=list)
    model: str = ""

    @property
    def status(self) -> str:
        return "verified" if not self.issues else "needs_review"

    @property
    def period(self) -> str:
        return f"{self.period_from:%Y-%m}" if self.period_from else ""


def validate(st: ParsedStatement, expected_opening: int | None = None, repair: bool = False) -> ParsedStatement:
    """Check the running balance, closing balance, dates and continuity.

    With repair=True (used for AI readings of photos) a single misread value is corrected only
    when the printed balances on both sides prove the correction; every repair is recorded.
    """
    if st.opening_minor is None:
        st.issues.append("Opening balance not found")
        return st
    if not st.period_from or not st.period_to:
        st.issues.append("Statement period not found")
    if expected_opening is not None and expected_opening != st.opening_minor:
        st.issues.append(f"Opening balance {st.opening_minor} does not equal previous closing {expected_opening}")

    prev = st.opening_minor
    lines = st.lines
    for i, ln in enumerate(lines):
        n = i + 1
        if prev + ln.amount_minor != ln.balance_minor and repair:
            nxt = lines[i + 1] if i + 1 < len(lines) else None
            after_ok = (lambda bal: (nxt.balance_minor == bal + nxt.amount_minor) if nxt
                        else (st.closing_minor is None or bal == st.closing_minor))
            if prev - ln.amount_minor == ln.balance_minor:
                st.repairs.append(f"Line {n}: debit/credit side corrected (proved by running balance)")
                ln.amount_minor = -ln.amount_minor
            elif after_ok(prev + ln.amount_minor):
                st.repairs.append(f"Line {n}: balance corrected from {ln.balance_minor} to "
                                  f"{prev + ln.amount_minor} (proved by next line)")
                ln.balance_minor = prev + ln.amount_minor
            elif after_ok(ln.balance_minor) and (ln.balance_minor - prev) * ln.amount_minor > 0:
                st.repairs.append(f"Line {n}: amount corrected from {abs(ln.amount_minor)} to "
                                  f"{abs(ln.balance_minor - prev)} (proved by balances)")
                ln.amount_minor = ln.balance_minor - prev
        if prev + ln.amount_minor != ln.balance_minor:
            st.issues.append(f"Line {n}: running balance does not agree ({prev} + {ln.amount_minor} != {ln.balance_minor})")
        if ln.amount_minor == 0:
            st.issues.append(f"Line {n}: zero amount")
        if not ln.legible:
            st.issues.append(f"Line {n}: marked unreadable by the reader")
        if st.period_from and st.period_to and not (st.period_from <= ln.txn_date <= st.period_to):
            st.issues.append(f"Line {n}: date {ln.txn_date} outside statement period")
        if i and ln.txn_date < lines[i - 1].txn_date:
            st.issues.append(f"Line {n}: date out of order")
        prev = ln.balance_minor

    if st.closing_minor is not None and prev != st.closing_minor:
        st.issues.append(f"Closing balance {st.closing_minor} does not equal last running balance {prev}")
    if st.closing_minor is None:
        st.issues.append("Closing balance not found")
    return st
