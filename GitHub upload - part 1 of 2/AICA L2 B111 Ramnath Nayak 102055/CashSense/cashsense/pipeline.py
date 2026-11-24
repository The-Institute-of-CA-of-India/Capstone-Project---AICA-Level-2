"""End-to-end runs used by the API, the CLI and n8n: statement intake and the daily treasury run."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from . import config
from .db.adapter import Database
from .money import fmt_amount

INBOX = config.DATA_DIR / "inbox"


def month_end(period: str) -> date:
    y, m = map(int, period.split("-"))
    return date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)


def accounts(db: Database) -> list[str]:
    return [a["account_id"] for a in db.query("bank_accounts", order="account_id")]


def run_daily(db: Database, as_of: date, client=None, use_browser: bool = True, actor: str = "daily_run") -> dict:
    """Reconcile every account, scan for risks (with browser verification), explain with Gemini,
    and propose approvals. Sending to Telegram is done by the caller (notify.py)."""
    from .agents.explainer import explain
    from .agents.reconciler import reconcile
    from .agents.risk import scan
    from .approvals import propose

    recon = [reconcile(db, a, as_of, actor=actor) for a in accounts(db)]
    browser_note = ""
    if use_browser:
        try:
            from .agents.browser_verify import BankVerifier

            with BankVerifier() as v:
                risk = scan(db, as_of, verifier=v, actor=actor)
        except Exception as exc:  # browser unavailable: still scan, note it
            browser_note = f"Browser verification unavailable ({type(exc).__name__}); rules-only risk scan"
            risk = scan(db, as_of, verifier=None, actor=actor)
    else:
        risk = scan(db, as_of, verifier=None, actor=actor)
    report = explain(db, recon, risk, client)
    created = propose(db, recon, risk, actor=actor)
    open_flags = [f for f in risk["flags"] if f["status"] == "open"]
    return {
        "as_of": as_of.isoformat(),
        "reconciliations": [{"account_id": r["account_id"], "status": r["status"],
                             "book": fmt_amount(r["book_balance_minor"], r["currency"]),
                             "bank": fmt_amount(r["bank_balance_minor"], r["currency"]),
                             "items": r["summary"]["items"], "timing_only": r["summary"]["timing_only"],
                             "auto_matched_now": r["summary"]["auto_matched_now"]} for r in recon],
        "risk_flags": len(risk["flags"]), "open_risk_flags": len(open_flags),
        "high_risks": sum(f["severity"] == "high" and f["status"] == "open" for f in risk["flags"]),
        "verifications": len(risk["verifications"]),
        "verification_mismatches": [v for v in risk["verifications"] if not v["name_match"]],
        "verification_results": risk["verifications"],
        "run_ids": [r["run_id"] for r in recon],
        "new_approvals": len(created),
        "pending_approvals": len(db.query("approvals", {"status": "pending"})),
        "ai": {k: v for k, v in report.items() if k != "commentary"}, "commentary": report["commentary"],
        "browser_note": browser_note,
    }


def intake(db: Database, paths: list[Path], client=None, actor: str = "intake") -> dict:
    """Read, verify and import a statement, categorise it with AI, then reconcile that account."""
    from .agents.categoriser import categorise
    from .agents.reconciler import reconcile
    from .ingest.importer import ImportRefused, find_account, import_statement, read_statement

    st = read_statement(paths, client)
    acc = find_account(db, st.account_no)
    existing = db.query("statement_imports", {"account_id": acc["account_id"], "period": st.period})
    if existing and existing[0]["source_format"] != "canonical_csv":
        raise ImportRefused(f"{acc['account_id']} {st.period} was already imported from "
                            f"{existing[0]['source_format']} on {existing[0]['imported_at']}")
    res = import_statement(db, st, [str(p) for p in paths], actor=actor, replace=bool(existing))
    lines = db.query("bank_lines", {"import_id": res["import_id"]}, order="line_id")
    cat = categorise(db, lines, client, use_ai=client is not None and client.available, actor=actor)
    rec = reconcile(db, acc["account_id"], month_end(st.period), actor=actor)
    return {"import": res, "categorised": {k: v for k, v in cat.items() if k != "results"},
            "reconciliation": {"status": rec["status"], "items": rec["summary"]["items"]}}


def safe_inbox_path(name: str) -> Path:
    """Only files inside data/inbox may be imported through the API."""
    p = (INBOX / name).resolve() if not Path(name).is_absolute() else Path(name).resolve()
    if INBOX.resolve() not in p.parents:
        raise ValueError("File must be inside data/inbox")
    return p


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, default=str)
