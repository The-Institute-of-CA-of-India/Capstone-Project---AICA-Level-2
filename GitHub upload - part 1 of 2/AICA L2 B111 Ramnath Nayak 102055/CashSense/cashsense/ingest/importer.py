"""Turn files into a verified ParsedStatement and store it, with an audit trail."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .. import config
from ..db.adapter import Database
from ..db.load import statement_line_id
from .common import ParsedStatement, validate
from .csv_reader import read_csv
from .pdf_reader import read_pdf

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png"}


class ImportRefused(Exception):
    pass


def detect_format(paths: list[Path]) -> str:
    suffixes = {Path(p).suffix.lower() for p in paths}
    if suffixes <= PHOTO_SUFFIXES:
        return "photo"
    if len(paths) == 1 and suffixes == {".csv"}:
        return "csv"
    if len(paths) == 1 and suffixes == {".pdf"}:
        return "pdf"
    raise ImportRefused(f"Unsupported file combination: {sorted(suffixes)}")


def previous_closing(db: Database, account_id: str, period: str) -> int | None:
    y, m = map(int, period.split("-"))
    prev = date(y, m, 1) - timedelta(days=1)
    rows = db.query("statement_imports", {"account_id": account_id, "period": f"{prev:%Y-%m}"})
    return rows[0]["closing_balance_minor"] if rows else None


def find_account(db: Database, account_no: str) -> dict:
    accounts = db.query("bank_accounts")
    exact = [a for a in accounts if a["account_no"] == account_no]
    if exact:
        return exact[0]
    tail = [a for a in accounts if account_no and a["account_no"].endswith(account_no[-4:])]
    if len(tail) == 1:
        return tail[0]
    raise ImportRefused(f"Statement account number {account_no!r} does not match any company bank account")


def read_statement(paths: list[Path], client=None) -> ParsedStatement:
    fmt = detect_format(paths)
    if fmt == "csv":
        return read_csv(paths[0])
    if fmt == "pdf":
        return read_pdf(paths[0])
    from .photo_reader import read_photos

    if client is None:
        from ..ai.gemini import GeminiClient

        client = GeminiClient()
    return read_photos(paths, client)


def import_statement(db: Database, st: ParsedStatement, source_files: list[str], actor: str,
                     replace: bool = False) -> dict:
    acc = find_account(db, st.account_no)
    if not st.period_from:
        raise ImportRefused("Statement period could not be read")
    period = st.period
    # re-run the checks with continuity against last month's imported closing balance
    st.issues = [i for i in st.issues if not i.startswith("Opening balance")]
    if st.source_format != "photo":
        st.issues = []
        validate(st, expected_opening=previous_closing(db, acc["account_id"], period))
    else:
        exp = previous_closing(db, acc["account_id"], period)
        if exp is not None and exp != st.opening_minor:
            st.issues.append(f"Opening balance {st.opening_minor} does not equal previous closing {exp}")
    if st.currency != acc["currency"]:
        st.issues.append(f"Statement currency {st.currency} differs from account currency {acc['currency']}")

    import_id = f"IMP-{acc['account_id']}-{period}"
    if db.query("statement_imports", {"import_id": import_id}):
        if not replace:
            raise ImportRefused(f"{acc['account_id']} {period} is already imported; use replace to re-import")
        db.delete("bank_lines", {"import_id": import_id})
        db.delete("statement_imports", {"import_id": import_id})

    db.insert_many("statement_imports", [{
        "import_id": import_id, "account_id": acc["account_id"], "period": period, "currency": st.currency,
        "source_file": ";".join(source_files), "source_format": st.source_format,
        "opening_balance_minor": st.opening_minor, "closing_balance_minor": st.closing_minor,
        "line_count": len(st.lines), "status": st.status, "issues": json.dumps(st.issues + st.repairs),
        "imported_at": config.now_ist().isoformat(timespec="seconds"), "imported_by": actor}])
    db.insert_many("bank_lines", [{
        "line_id": statement_line_id(acc["account_id"], period, i), "import_id": import_id,
        "account_id": acc["account_id"], "txn_date": ln.txn_date.isoformat(),
        "value_date": (ln.value_date or ln.txn_date).isoformat(), "description": ln.description,
        "ref_no": ln.ref_no, "amount_minor": ln.amount_minor, "balance_minor": ln.balance_minor,
        "category": None, "party_id": None, "category_confidence": None, "category_reason": None,
        "category_source": None, "review_status": None if st.status == "verified" else "statement_unverified"}
        for i, ln in enumerate(st.lines, 1)])
    result = {"import_id": import_id, "account_id": acc["account_id"], "period": period,
              "format": st.source_format, "lines": len(st.lines), "status": st.status,
              "issues": st.issues, "repairs": st.repairs, "model": st.model}
    db.audit(actor, "import_statement", "statement_imports", import_id,
             {k: v for k, v in result.items() if k != "import_id"} | {"files": source_files})
    return result
