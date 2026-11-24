"""Approval service (maker-checker). CashSense proposes; the CA approves or rejects in Telegram.

Kinds
  journal_entry  - post the proposed entry for bank-only items (charges + GST grouped by account and date)
  fuzzy_match    - confirm a near match and post the correcting entry
  risk_flag      - "Reviewed" (approve) or "Escalate" (reject)

Nothing reaches the books unless decide(..., "approve") is called for that approval.
Every proposal and decision is written to the audit log.
"""
from __future__ import annotations

import json
from collections import defaultdict

from . import config
from .db.adapter import Database
from .money import fmt_amount

CHARGE_CATS = {"bank_charges_not_booked", "gst_on_bank_charges_not_booked"}


def _next_id(db: Database, table: str, key: str, prefix: str, width: int = 4) -> int:
    nums = [int(r[key][len(prefix):]) for r in db.query(table) if str(r[key]).startswith(prefix)
            and r[key][len(prefix):].isdigit()]
    return max(nums, default=0) + 1


def _exists(db: Database, kind: str, ref: str) -> bool:
    return any(a["status"] in ("pending", "approved") for a in db.query("approvals", {"kind": kind, "ref_id": ref}))


def propose(db: Database, recon: list[dict], risk: dict | None, actor: str = "cashsense") -> list[dict]:
    now = config.now_ist().isoformat(timespec="seconds")
    created = []

    def add(kind, ref, title, payload):
        if _exists(db, kind, ref):
            return
        aid = f"AP{_next_id(db, 'approvals', 'approval_id', 'AP'):04d}"
        row = {"approval_id": aid, "kind": kind, "ref_id": ref, "title": title, "payload": json.dumps(payload),
               "status": "pending", "requested_at": now, "decided_at": None, "decided_by": None,
               "channel": None, "channel_message_id": None}
        db.insert_many("approvals", [row])
        created.append(row)

    for r in recon:
        cur = r["currency"]
        groups = defaultdict(list)
        for i in r["items"]:
            if i["category"] == "amount_mismatch":
                s = i["suggestion"]
                add("fuzzy_match", f"{i['line_id']}|{i['entry_id']}",
                    f"{r['account_id']}: books {fmt_amount(abs(s['book_amount_minor']), cur)} vs bank "
                    f"{fmt_amount(abs(s['bank_amount_minor']), cur)} - confirm match and correct books",
                    {"items": [i]})
            elif i["needs_approval"]:
                key = ("charges", i["item_date"]) if i["category"] in CHARGE_CATS else (i["category"], i["line_id"])
                groups[key].append(i)
        for (_, _), grp in groups.items():
            total = sum(i["amount_minor"] for i in grp)
            labels = ", ".join(f"{i['explanation'].split('.')[0][:60]} {fmt_amount(abs(i['amount_minor']), cur)}"
                               for i in grp)
            add("journal_entry", ",".join(sorted(i["line_id"] for i in grp)),
                f"{r['account_id']} {grp[0]['item_date']}: post entry for {fmt_amount(abs(total), cur)} ({labels})",
                {"items": grp})

    for f in (risk or {}).get("flags", []):
        ref = f"{f['flag_type']}:{','.join(f['line_ids']) or f['bill_no']}"
        add("risk_flag", ref, f"[{f['severity'].upper()}] {f['explanation']}", {"flag": f})
    if created:
        db.audit(actor, "propose_approvals", "approvals", f"{len(created)} new",
                 {"ids": [c["approval_id"] for c in created]})
    return created


def _post_entry(db: Database, s: dict, line: dict, counter: str, amount: int, narration: str, approval_id: str,
                inr: int | None) -> str:
    n = _next_id(db, "book_entries", "entry_id", "BE-J")
    entry_id = f"BE-J{n:04d}"
    fy = db.query("company")[0]["fy_start"][2:4]
    acc = db.query("bank_accounts", {"account_id": s["account_id"]})[0]
    db.insert_many("book_entries", [{
        "entry_id": entry_id, "voucher_no": f"JV/{fy}-{int(fy) + 1}/{approval_id}", "voucher_type": "JOURNAL",
        "entry_date": line["txn_date"], "account_id": s["account_id"], "currency": acc["currency"],
        "counter_ledger": counter, "party_id": line.get("party_id") or "", "narration": narration,
        "amount_minor": amount, "inr_amount_paise": inr if inr is not None else amount,
        "mode": "APPROVED-JV", "instrument_no": ""}])
    return entry_id


def _link(db: Database, account_id: str, line_id: str, entry_id: str, link_type: str, approval_id: str) -> None:
    db.insert_many("recon_links", [{"link_id": f"{approval_id}-{line_id}-{entry_id}", "account_id": account_id,
                                    "line_id": line_id, "entry_id": entry_id, "link_type": link_type,
                                    "rule": f"approved {approval_id}", "run_id": None,
                                    "created_at": config.now_ist().isoformat(timespec="seconds")}])


def decide(db: Database, approval_id: str, decision: str, actor: str) -> dict:
    rows = db.query("approvals", {"approval_id": approval_id})
    if not rows:
        return {"ok": False, "message": f"{approval_id} not found"}
    ap = rows[0]
    if ap["status"] != "pending":
        return {"ok": False, "message": f"{approval_id} already {ap['status']}"}
    if decision not in ("approve", "reject"):
        return {"ok": False, "message": "decision must be approve or reject"}
    payload = json.loads(ap["payload"])
    posted = []
    if decision == "approve" and ap["kind"] == "journal_entry":
        for i in payload["items"]:
            s = i["suggestion"]
            line = db.query("bank_lines", {"line_id": i["line_id"]})[0]
            entry = _post_entry(db, s, line, s["counter_ledger"], line["amount_minor"], s["narration"], approval_id,
                                s.get("inr_amount_paise"))
            _link(db, s["account_id"], line["line_id"], entry, "posted_from_line", approval_id)
            posted.append(entry)
    elif decision == "approve" and ap["kind"] == "fuzzy_match":
        i = payload["items"][0]
        s = i["suggestion"]
        line = db.query("bank_lines", {"line_id": i["line_id"]})[0]
        _link(db, s["account_id"], line["line_id"], s["entry_id"], "fuzzy_approved", approval_id)
        entry = _post_entry(db, s, line, s["counter_ledger"], s["correction_minor"], s["narration"], approval_id, None)
        _link(db, s["account_id"], line["line_id"], entry, "fuzzy_approved", approval_id)
        posted.append(entry)
    elif ap["kind"] == "risk_flag":
        flag_id = payload["flag"]["flag_id"]
        db.update("risk_flags", {"flag_id": flag_id}, {"status": "reviewed" if decision == "approve" else "escalated"})
    status = "approved" if decision == "approve" else "rejected"
    db.update("approvals", {"approval_id": approval_id},
              {"status": status, "decided_at": config.now_ist().isoformat(timespec="seconds"), "decided_by": actor})
    db.audit(actor, f"{decision}_{ap['kind']}", "approvals", approval_id, {"posted_entries": posted})
    verb = {"journal_entry": "Entry posted", "fuzzy_match": "Match confirmed, correction posted",
            "risk_flag": "Marked reviewed"}[ap["kind"]] if decision == "approve" else \
        ("Escalated" if ap["kind"] == "risk_flag" else "Rejected - nothing posted")
    return {"ok": True, "approval_id": approval_id, "status": status, "posted_entries": posted, "message": verb}
