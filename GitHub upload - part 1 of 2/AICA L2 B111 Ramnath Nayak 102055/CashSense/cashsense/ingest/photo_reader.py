"""Read photographed statement pages with Gemini vision, then verify the reading in Python."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ..ai.gemini import GeminiClient, Image
from ..skills import load_skill
from .common import ParsedLine, ParsedStatement, parse_date, validate

_NUM = {"type": "NUMBER", "nullable": True}
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "bank_name": {"type": "STRING"},
        "account_number": {"type": "STRING"},
        "period_from": {"type": "STRING", "description": "YYYY-MM-DD"},
        "period_to": {"type": "STRING", "description": "YYYY-MM-DD"},
        "currency": {"type": "STRING"},
        "opening_balance": {"type": "NUMBER"},
        "opening_balance_side": {"type": "STRING", "enum": ["CR", "DR"]},
        "closing_balance": {"type": "NUMBER"},
        "closing_balance_side": {"type": "STRING", "enum": ["CR", "DR"]},
        "lines": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "date": {"type": "STRING", "description": "YYYY-MM-DD"},
            "description": {"type": "STRING"},
            "ref_no": {"type": "STRING"},
            "debit": _NUM, "credit": _NUM,
            "balance": {"type": "NUMBER"},
            "balance_side": {"type": "STRING", "enum": ["CR", "DR"]},
            "legible": {"type": "BOOLEAN"},
        }, "required": ["date", "description", "balance", "balance_side", "legible"]}},
    },
    "required": ["account_number", "period_from", "period_to", "opening_balance", "opening_balance_side",
                 "closing_balance", "closing_balance_side", "lines"],
}


def _minor(x) -> int:
    if x in (None, ""):
        return 0
    return int((Decimal(str(round(float(x), 2))) * 100).to_integral_value())


def _signed(x, side) -> int:
    v = abs(_minor(x))
    return -v if str(side).upper() == "DR" else v


def from_ai(data: dict, model: str = "") -> ParsedStatement:
    """Convert the AI's JSON into a ParsedStatement. Unknown fields are ignored."""
    st = ParsedStatement(source_format="photo", model=model)
    try:
        st.account_no = "".join(ch for ch in str(data.get("account_number", "")) if ch.isdigit())
        st.period_from = parse_date(data["period_from"]) if data.get("period_from") else None
        st.period_to = parse_date(data["period_to"]) if data.get("period_to") else None
        st.currency = (data.get("currency") or "INR").upper()[:3]
        if data.get("opening_balance") is not None:
            st.opening_minor = _signed(data["opening_balance"], data.get("opening_balance_side", "CR"))
        if data.get("closing_balance") is not None:
            st.closing_minor = _signed(data["closing_balance"], data.get("closing_balance_side", "CR"))
    except (ValueError, TypeError) as exc:
        st.issues.append(f"Header unreadable: {exc}")
    for i, ln in enumerate(data.get("lines") or [], 1):
        try:
            debit, credit = abs(_minor(ln.get("debit"))), abs(_minor(ln.get("credit")))
            if debit and credit:
                st.issues.append(f"Line {i}: both debit and credit given")
            st.lines.append(ParsedLine(
                txn_date=parse_date(ln["date"]), description=" ".join(str(ln.get("description", "")).split()),
                ref_no=str(ln.get("ref_no") or ""), amount_minor=credit - debit,
                balance_minor=_signed(ln.get("balance"), ln.get("balance_side", "CR")),
                legible=bool(ln.get("legible", True))))
        except (ValueError, TypeError, KeyError) as exc:
            st.issues.append(f"Line {i}: unreadable ({exc})")
    return st


def _key(ln: ParsedLine) -> tuple:
    return (ln.txn_date, "".join(ln.description.split()).upper(), ln.amount_minor, ln.balance_minor)


def _ref_ok(ln: ParsedLine, ifsc: str) -> bool:
    from .profiles import ref_problem

    return ref_problem(ln.description, ifsc) is None


def consensus(readings: list[ParsedStatement], ifsc: str = "") -> ParsedStatement:
    """Combine independent readings line by line: a value is accepted when at least two readings agree.
    Lines without a majority are marked for human review."""
    base = readings[0]
    st = ParsedStatement(source_format="photo", account_no=base.account_no, period_from=base.period_from,
                         period_to=base.period_to, currency=base.currency, opening_minor=base.opening_minor,
                         closing_minor=base.closing_minor, model=", ".join(sorted({r.model for r in readings if r.model})))
    for field in ("account_no", "period_from", "period_to", "opening_minor", "closing_minor"):
        values = [getattr(r, field) for r in readings]
        best = max(set(values), key=values.count)
        if values.count(best) < 2:
            st.issues.append(f"Readings disagree on {field.replace('_minor', '')}")
        setattr(st, field, best)
    counts = [len(r.lines) for r in readings]
    n = max(set(counts), key=counts.count)
    if counts.count(n) < 2:
        st.issues.append(f"Readings disagree on the number of lines {counts}")
    for i in range(n):
        cands = [r.lines[i] for r in readings if len(r.lines) == n]
        valid = [c for c in cands if _ref_ok(c, ifsc)]
        if valid and len(valid) < len(cands):      # prefer readings whose reference has the bank's format
            cands = valid + [c for c in cands if c not in valid]
        keys = [_key(c) for c in cands]
        best = max(set(keys), key=keys.count)
        line = cands[keys.index(best)]
        if keys.count(best) < 2:
            line.legible = False
            st.issues.append(f"Line {i + 1}: independent readings disagree - check the photo")
        st.lines.append(line)
    if len(readings) > 2 or any("disagree" in x for x in st.issues):
        st.repairs.append(f"Consensus of {len(readings)} readings used")
    return st


def read_photos(paths: list[Path], client: GeminiClient, expected_opening: int | None = None,
                reads: int = 2, ifsc: str = "ZZKB") -> ParsedStatement:
    """Read the pages twice (independently); if the readings differ anywhere, read a third time and take
    the majority per line. Then run the Python checks (balances, dates, continuity)."""
    parts = [f"These {len(paths)} image(s) are consecutive pages of one bank statement. "
             "Read every transaction line on every page in order."]
    for p in paths:
        mime = "image/png" if Path(p).suffix.lower() == ".png" else "image/jpeg"
        parts.append(Image(Path(p).read_bytes(), mime))

    def one_read() -> ParsedStatement:
        data = client.generate_json(load_skill("statement-reader"), parts, SCHEMA, task="vision",
                                    try_timeout=90, budget=180)
        return from_ai(data, client.last_model)

    readings = [one_read() for _ in range(max(1, reads))]
    if reads == 1:
        st = readings[0]
    else:
        same = all(len(r.lines) == len(readings[0].lines) and [_key(x) for x in r.lines] ==
                   [_key(x) for x in readings[0].lines] for r in readings[1:])
        bad_refs = any(not _ref_ok(ln, ifsc) for ln in readings[0].lines)
        if not same or bad_refs:
            readings.append(one_read())
            st = consensus(readings, ifsc)
        else:
            st = readings[0]
            st.model = ", ".join(sorted({r.model for r in readings if r.model}))
    from .profiles import ref_problem

    for i, ln in enumerate(st.lines, 1):
        problem = ref_problem(ln.description, ifsc)
        if problem:
            st.issues.append(f"Line {i}: {problem}")
    return validate(st, expected_opening=expected_opening, repair=True)
