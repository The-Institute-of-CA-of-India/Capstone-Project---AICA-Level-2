"""Measure the agents against the answer keys (used by the CLI and tests; never by the agents)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .ingest.common import ParsedStatement
from .money import to_paise


def _squash(text: str) -> str:
    return "".join((text or "").split()).upper()


def compare_lines(st: ParsedStatement, expected: dict) -> dict:
    """Line-by-line comparison. Photos are not expected to carry a separate reference column."""
    photo = expected["format"] == "photo"
    rows, exact = [], 0
    exp_lines = expected["lines"]
    for i in range(max(len(exp_lines), len(st.lines))):
        e = exp_lines[i] if i < len(exp_lines) else None
        g = st.lines[i] if i < len(st.lines) else None
        checks = {}
        if e and g:
            checks = {
                "date": g.txn_date.isoformat() == e["txn_date"],
                "description": _squash(g.description) == _squash(e["description"]) if photo
                else g.description == e["description"],
                "amount": g.amount_minor == to_paise(e["credit"]) - to_paise(e["debit"]),
                "balance": g.balance_minor == to_paise(e["balance"]),
            }
            if not photo:
                checks["ref_no"] = g.ref_no == e["ref_no"]
        ok = bool(checks) and all(checks.values())
        exact += ok
        rows.append({"n": i + 1, "expected": e["description"] if e else "(none)",
                     "read": g.description if g else "(missing)",
                     "expected_amount": (to_paise(e["credit"]) - to_paise(e["debit"])) / 100 if e else None,
                     "read_amount": g.amount_minor / 100 if g else None, "ok": ok,
                     "failed": [k for k, v in checks.items() if not v]})
    return {"expected_lines": len(exp_lines), "read_lines": len(st.lines), "exact_lines": exact,
            "opening_ok": st.opening_minor == int(expected["opening"]),
            "closing_ok": st.closing_minor == int(expected["closing"]),
            "account_ok": st.account_no == expected["account_no"], "rows": rows}


def load_truth(p2_dir: Path) -> dict[str, dict]:
    with (p2_dir / "answer_key" / "categories_truth.csv").open(newline="", encoding="utf-8") as fh:
        return {r["line_id"]: r for r in csv.DictReader(fh)}


def score_categories(results: list[dict], truth: dict[str, dict]) -> dict:
    n = len(results)
    cat_ok = sum(truth[r["line_id"]]["category"] == r["category"] for r in results)
    party_ok = sum(truth[r["line_id"]]["party_id"] == (r["party_id"] or "") for r in results)
    by_cat: dict[str, list[int]] = {}
    for r in results:
        t = truth[r["line_id"]]["category"]
        by_cat.setdefault(t, [0, 0])
        by_cat[t][0] += 1
        by_cat[t][1] += t == r["category"]
    return {"lines": n, "category_correct": cat_ok, "party_correct": party_ok,
            "category_accuracy": round(cat_ok / n, 4) if n else None,
            "party_accuracy": round(party_ok / n, 4) if n else None,
            "by_category": {k: {"lines": v[0], "correct": v[1]} for k, v in sorted(by_cat.items())}}


def load_expected(p2_dir: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((p2_dir / "answer_key" / "expected").glob("*.json"))]
