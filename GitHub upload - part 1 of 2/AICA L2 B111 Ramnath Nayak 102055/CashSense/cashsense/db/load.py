"""Load Phase 1 data files into the database. The answer key is deliberately NOT loaded."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from ..money import to_paise
from .adapter import Database


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def statement_line_id(account_id: str, period: str, idx: int) -> str:
    return f"{account_id}-{period.replace('-', '')}-{idx:04d}"


def load_phase1(db: Database, data_dir: Path, actor: str = "system") -> dict:
    db.init_schema()
    db.reset()

    company = json.loads((data_dir / "company.json").read_text(encoding="utf-8"))
    db.insert_many("company", [company])

    accounts = _rows(data_dir / "bank_accounts.csv")
    for a in accounts:
        for k in ("opening_balance_minor", "limit_minor", "min_balance_minor"):
            a[k] = int(a[k])
        a["interest_rate"] = float(a["interest_rate"])
    db.insert_many("bank_accounts", accounts)

    parties = _rows(data_dir / "counterparties.csv")
    for p in parties:
        p["terms_days"], p["msme"] = int(p["terms_days"]), int(p["msme"])
    db.insert_many("counterparties", parties)

    holidays = [{"holiday_date": h["date"], "name": h["holiday"]} for h in _rows(data_dir / "bank_holidays.csv")]
    db.insert_many("bank_holidays", holidays)

    entries = _rows(data_dir / "book_entries.csv")
    for e in entries:
        e["amount_minor"] = to_paise(e.pop("amount"))
        e["inr_amount_paise"] = to_paise(e.pop("inr_amount"))
    db.insert_many("book_entries", entries)

    imports, lines = [], []
    for s in _rows(data_dir / "statement_index.csv"):
        import_id = f"IMP-{s['account_id']}-{s['period']}"
        imports.append({"import_id": import_id, "account_id": s["account_id"], "period": s["period"],
                        "currency": s["currency"], "source_file": s["file"], "source_format": "canonical_csv",
                        "opening_balance_minor": to_paise(s["opening"]), "closing_balance_minor": to_paise(s["closing"]),
                        "line_count": int(s["line_count"]), "status": "verified", "issues": "[]",
                        "imported_at": "", "imported_by": actor})
        for i, r in enumerate(_rows(data_dir / s["file"]), 1):
            lines.append({"line_id": statement_line_id(s["account_id"], s["period"], i), "import_id": import_id,
                          "account_id": s["account_id"], "txn_date": r["txn_date"], "value_date": r["value_date"],
                          "description": r["description"], "ref_no": r["ref_no"],
                          "amount_minor": to_paise(r["credit"]) - to_paise(r["debit"]),
                          "balance_minor": to_paise(r["balance"]), "category": None, "party_id": None,
                          "category_confidence": None, "category_reason": None, "category_source": None,
                          "review_status": None})
    db.insert_many("statement_imports", imports)
    db.insert_many("bank_lines", lines)

    ar = _rows(data_dir / "ar_open.csv")
    for r in ar:
        r["amount_minor"] = to_paise(r.pop("amount"))
    db.insert_many("ar_open", ar)
    ap = _rows(data_dir / "ap_open.csv")
    for r in ap:
        r["amount_paise"], r["msme"] = to_paise(r.pop("amount")), int(r["msme"])
    db.insert_many("ap_open", ap)
    cm = _rows(data_dir / "commitments.csv")
    for r in cm:
        r["amount_paise"] = to_paise(r.pop("amount"))
    db.insert_many("commitments", cm)

    counts = {"bank_accounts": len(accounts), "counterparties": len(parties), "bank_holidays": len(holidays),
              "book_entries": len(entries), "statement_imports": len(imports), "bank_lines": len(lines),
              "ar_open": len(ar), "ap_open": len(ap), "commitments": len(cm)}
    db.audit(actor, "load_phase1_data", "dataset", str(data_dir.name), counts)
    return counts
