"""Read a digital (text) PDF statement with pdfplumber. No AI is needed for digital PDFs."""
from __future__ import annotations

import re
from pathlib import Path

from ..money import parse_amount
from .common import ParsedLine, ParsedStatement, parse_date

_DATE = re.compile(r"^\d{2}[/-]\d{2}[/-]\d{2,4}$")
_AMT = r"([\d,]+\.\d{2}(?:\s*(?:Dr|Cr))?)"


def read_pdf(path: Path) -> ParsedStatement:
    import pdfplumber

    st = ParsedStatement(source_format="pdf")
    texts = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
            for table in page.extract_tables():
                header = None
                for row in table:
                    cells = [(c or "").replace("\n", " ").strip() for c in row]
                    if header is None and any(c.lower() == "date" for c in cells):
                        header = [c.lower() for c in cells]
                        continue
                    if header is None or not cells or not _DATE.match(cells[0]):
                        continue
                    get = lambda name: cells[header.index(name)] if name in header else ""  # noqa: E731
                    st.lines.append(ParsedLine(
                        txn_date=parse_date(get("date")), description=get("narration") or get("particulars"),
                        ref_no=get("ref no"), amount_minor=parse_amount(get("credit")) - parse_amount(get("debit")),
                        balance_minor=parse_amount(get("balance"))))
    text = "\n".join(texts)
    if m := re.search(r"Account No:\s*(\d+)", text):
        st.account_no = m.group(1)
    if m := re.search(r"Currency:\s*([A-Z]{3})", text):
        st.currency = m.group(1)
    if m := re.search(r"Period:\s*(\d{2}/\d{2}/\d{4})\s*to\s*(\d{2}/\d{2}/\d{4})", text):
        st.period_from, st.period_to = parse_date(m.group(1)), parse_date(m.group(2))
    if m := re.search(r"Opening Balance:\s*" + _AMT, text):
        st.opening_minor = parse_amount(m.group(1))
    if m := re.search(r"Closing Balance:\s*" + _AMT, text):
        st.closing_minor = parse_amount(m.group(1))
    return st
