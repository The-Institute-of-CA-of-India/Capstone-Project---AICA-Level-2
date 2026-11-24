"""Read a bank CSV export. Finds the header row by keywords, so it copes with metadata rows
above and summary rows below the transactions."""
from __future__ import annotations

import csv
import re
from pathlib import Path

from ..money import parse_amount
from .common import ParsedLine, ParsedStatement, parse_date

COLUMN_KEYS = {
    "txn_date": ("tran date", "txn date", "transaction date", "date"),
    "value_date": ("value date",),
    "description": ("particulars", "narration", "description", "details"),
    "ref_no": ("chq/ref", "ref no", "reference", "cheque no", "chq no"),
    "debit": ("withdrawal", "debit", "dr"),
    "credit": ("deposit", "credit", "cr"),
    "balance": ("balance",),
}


def _map_columns(header: list[str]) -> dict[str, int]:
    low = [h.strip().lower() for h in header]
    cols: dict[str, int] = {}
    for key in ("value_date", "txn_date", "description", "ref_no", "debit", "credit", "balance"):
        for i, h in enumerate(low):
            if i in cols.values():
                continue
            if any(h.startswith(k) or k in h for k in COLUMN_KEYS[key]):
                cols[key] = i
                break
    missing = {"txn_date", "description", "debit", "credit", "balance"} - set(cols)
    if missing:
        raise ValueError(f"CSV header is missing columns: {sorted(missing)}")
    return cols


def read_csv(path: Path) -> ParsedStatement:
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    st = ParsedStatement(source_format="csv")
    header_at = next((i for i, r in enumerate(rows)
                      if any("date" in c.lower() for c in r) and any("balance" in c.lower() for c in r)), None)
    if header_at is None:
        raise ValueError("No transaction header row found")
    for r in rows:
        if len(r) < 2:
            continue
        label, value = r[0].strip().lower(), r[1].strip()
        if label.startswith("account number") or label.startswith("account no"):
            st.account_no = re.sub(r"\D", "", value)
        elif label.startswith("statement period") or label.startswith("period"):
            parts = re.split(r"\s+to\s+|\s+-\s+", value)
            if len(parts) == 2:
                st.period_from, st.period_to = parse_date(parts[0]), parse_date(parts[1])
        elif label.startswith("opening balance"):
            st.opening_minor = parse_amount(value)
        elif label.startswith("closing balance"):
            st.closing_minor = parse_amount(value)
        elif label.startswith("currency"):
            st.currency = value.upper()
    cols = _map_columns(rows[header_at])
    for r in rows[header_at + 1:]:
        if not r or not any(c.strip() for c in r):
            break
        cell = lambda k: r[cols[k]].strip() if k in cols and cols[k] < len(r) else ""  # noqa: E731
        st.lines.append(ParsedLine(
            txn_date=parse_date(cell("txn_date")),
            value_date=parse_date(cell("value_date")) if cell("value_date") else None,
            description=cell("description"), ref_no=cell("ref_no"),
            amount_minor=parse_amount(cell("credit")) - parse_amount(cell("debit")),
            balance_minor=parse_amount(cell("balance"))))
    return st
