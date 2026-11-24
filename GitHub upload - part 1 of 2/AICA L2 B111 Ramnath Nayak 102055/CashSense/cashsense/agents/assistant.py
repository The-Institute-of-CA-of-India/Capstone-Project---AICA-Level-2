"""Assistant agent: answers questions with Gemini function calling over READ-ONLY CashSense tools.
Used by Telegram (text and voice notes) and the dashboard's Ask box.

Guard-rails: tools cannot change data; the assistant cannot approve anything; every amount in the
answer must match an amount in the tool results, otherwise a warning is appended.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta

from .. import config
from ..db.adapter import Database
from ..money import fmt_amount, fmt_inr
from ..skills import load_skill
from .forecaster import SCENARIOS, forecast, unverified_amounts

TOOLS = [
    {"name": "get_cash_position", "description": "Bank balances of every account as at the as-of date, cash-credit "
     "drawn, limit and utilisation, EEFC balance in INR.", "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "get_forecast", "description": "13-week cash forecast for a scenario: peak CC drawing, utilisation, "
     "85% alert weeks and weekly figures.",
     "parameters": {"type": "OBJECT", "properties": {"scenario": {"type": "STRING", "enum": list(SCENARIOS)}},
                    "required": ["scenario"]}},
    {"name": "get_reconciliation_status", "description": "Latest bank reconciliation per account: agreed or not "
     "and the outstanding reconciling items.", "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "get_risks", "description": "Risk flags raised by the Risk Sentinel with severity and status.",
     "parameters": {"type": "OBJECT", "properties": {"status": {"type": "STRING", "enum": ["open", "all"]}}}},
    {"name": "get_pending_approvals", "description": "Approvals waiting for the CA in Telegram.",
     "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "get_receivables", "description": "Open customer invoices: totals by customer, overdue amounts.",
     "parameters": {"type": "OBJECT", "properties": {"top_n": {"type": "INTEGER"}, "overdue_only": {"type": "BOOLEAN"}}}},
    {"name": "get_payables", "description": "Open supplier bills: totals by supplier, overdue and MSME (sec 43B(h)).",
     "parameters": {"type": "OBJECT", "properties": {"msme_only": {"type": "BOOLEAN"}, "overdue_only": {"type": "BOOLEAN"}}}},
    {"name": "get_commitments", "description": "Known future payments and receipts (salary, statutory dues, rent, "
     "EMI, insurance, capex, FD maturity) between two dates.",
     "parameters": {"type": "OBJECT", "properties": {"from_date": {"type": "STRING", "description": "YYYY-MM-DD"},
                                                     "to_date": {"type": "STRING", "description": "YYYY-MM-DD"}}}},
]


class Tools:
    def __init__(self, db: Database, as_of: date | None = None):
        self.db, self.as_of = db, as_of or config.as_of_date()
        self.names = {p["party_id"]: p["name"] for p in db.query("counterparties")}
        self._fc: dict[str, dict] = {}

    def run(self, name: str, args: dict) -> dict:
        fn = getattr(self, name, None)
        if name not in {t["name"] for t in TOOLS} or fn is None:
            return {"error": f"unknown tool {name}"}
        try:
            return fn(**{k: v for k, v in (args or {}).items() if v is not None})
        except (TypeError, ValueError) as exc:
            return {"error": str(exc)}

    def _forecast(self, scenario: str) -> dict:
        if scenario not in self._fc:
            self._fc[scenario] = forecast(self.db, self.as_of, scenario)
        return self._fc[scenario]

    def get_cash_position(self) -> dict:
        o = self._forecast("base")["opening"]
        acc = {a["account_id"]: a for a in self.db.query("bank_accounts")}
        return {"as_of": o["as_of"], "accounts": [{"account": f"{aid} {acc[aid]['name']}",
                                                   "bank_balance": fmt_amount(v, acc[aid]["currency"])}
                                                  for aid, v in o["balances_minor"].items()],
                "cash_in_current_and_collections": fmt_inr(o["cash_paise"]), "cc_drawn": fmt_inr(o["cc_drawn_paise"]),
                "cc_limit": fmt_inr(o["cc_limit_paise"]), "cc_utilisation": f"{o['cc_drawn_paise'] / o['cc_limit_paise']:.0%}",
                "eefc_in_inr": fmt_inr(o["eefc_inr_paise"]), "usd_rate": o["usd_rate"],
                "net_position_excluding_eefc": fmt_inr(o["net_position_paise"])}

    def get_forecast(self, scenario: str = "base") -> dict:
        if scenario not in SCENARIOS:
            raise ValueError(f"scenario must be one of {list(SCENARIOS)}")
        r = self._forecast(scenario)
        s = r["summary"]
        return {"scenario": scenario, "label": r["label"], "period": f"{r['as_of']} to {r['end']}",
                "peak_week": s["peak_week"], "peak_cc_drawn": fmt_inr(s["peak_cc_drawn_paise"]),
                "peak_utilisation": f"{s['peak_utilisation']:.0%}", "minimum_headroom": fmt_inr(s["min_headroom_paise"]),
                "first_85pct_alert_week": s["first_alert_week"], "alert_weeks": s["alert_weeks"],
                "largest_customer": self.names.get(s["top_customer"], s["top_customer"]),
                "weeks": [{"week": w["week"], "ends": w["end"], "net_flow": fmt_inr(w["net_flow_paise"]),
                           "cc_drawn": fmt_inr(w["cc_drawn_paise"]), "utilisation": f"{w['cc_utilisation']:.0%}",
                           "alert": w["alert"]} for w in r["weeks"]],
                "assumptions": "Known receivables/payables/commitments plus same-month-last-year run rate; "
                               "surplus cash swept to CC; overdue receivables collected over weeks 1-4."}

    def get_reconciliation_status(self) -> dict:
        latest = {}
        for r in self.db.query("recon_runs", order="created_at"):
            latest[r["account_id"]] = r
        cur = {a["account_id"]: a["currency"] for a in self.db.query("bank_accounts")}
        return {"accounts": [{"account": aid, "as_of": r["as_of"], "status": r["status"],
                              "book_balance": fmt_amount(r["book_balance_minor"], cur[aid]),
                              "bank_balance": fmt_amount(r["bank_balance_minor"], cur[aid]),
                              "outstanding_items": json.loads(r["summary"])["items"]} for aid, r in sorted(latest.items())]}

    def get_risks(self, status: str = "open") -> dict:
        flags = self.db.query("risk_flags", order="flag_id")
        if status == "open":
            flags = [f for f in flags if f["status"] == "open"]
        return {"count": len(flags), "flags": [{"type": f["flag_type"], "severity": f["severity"], "status": f["status"],
                                                "party": self.names.get(f["party_id"], f["party_id"] or ""),
                                                "amount": fmt_inr(abs(f["amount_minor"] or 0)),
                                                "summary": (f["explanation"] or "")[:240]} for f in flags]}

    def get_pending_approvals(self) -> dict:
        aps = self.db.query("approvals", {"status": "pending"}, order="approval_id")
        return {"count": len(aps), "approvals": [{"id": a["approval_id"], "kind": a["kind"], "title": a["title"][:160]}
                                                 for a in aps]}

    def get_receivables(self, top_n: int = 5, overdue_only: bool = False) -> dict:
        rate = self._forecast("base")["opening"]["usd_rate"]
        tot, over = defaultdict(int), defaultdict(int)
        for r in self.db.query("ar_open"):
            inr = int(round(r["amount_minor"] * rate)) if r["currency"] == "USD" else r["amount_minor"]
            tot[r["party_id"]] += inr
            if r["due_date"] <= self.as_of.isoformat():
                over[r["party_id"]] += inr
        base = over if overdue_only else tot
        ranked = sorted(base.items(), key=lambda kv: -kv[1])[:max(1, int(top_n))]
        return {"total_open": fmt_inr(sum(tot.values())), "total_overdue": fmt_inr(sum(over.values())),
                "customers": [{"customer": self.names.get(p, p), "open": fmt_inr(tot[p]), "overdue": fmt_inr(over[p])}
                              for p, _ in ranked], "note": "USD invoices converted at the latest EEFC rate"}

    def get_payables(self, msme_only: bool = False, overdue_only: bool = False) -> dict:
        rows = []
        for b in self.db.query("ap_open", order="bill_no"):
            overdue = b["due_date"] <= self.as_of.isoformat()
            if (msme_only and not b["msme"]) or (overdue_only and not overdue):
                continue
            days = (self.as_of - date.fromisoformat(b["bill_date"])).days
            rows.append({"bill": b["bill_no"], "supplier": self.names.get(b["party_id"], b["party_id"]),
                         "amount": fmt_inr(b["amount_paise"]), "due": b["due_date"], "msme": bool(b["msme"]),
                         "days_outstanding": days, "beyond_45_days_msme": bool(b["msme"] and days > 45),
                         **({"note": b["note"]} if b["note"] else {})})
        rows.sort(key=lambda r: r["due"])
        total = sum(b["amount_paise"] for b in self.db.query("ap_open")
                    if not ((msme_only and not b["msme"]) or (overdue_only and b["due_date"] > self.as_of.isoformat())))
        beyond = [b for b in self.db.query("ap_open") if b["msme"]
                  and (self.as_of - date.fromisoformat(b["bill_date"])).days > 45]
        return {"count": len(rows), "total": fmt_inr(total), "bills": rows,
                "msme_beyond_45_days_total": fmt_inr(sum(b["amount_paise"] for b in beyond)),
                "msme_beyond_45_days_count": len(beyond)}

    def get_commitments(self, from_date: str | None = None, to_date: str | None = None) -> dict:
        lo = from_date or (self.as_of + timedelta(days=1)).isoformat()
        hi = to_date or (self.as_of + timedelta(days=91)).isoformat()
        rows = [c for c in self.db.query("commitments", order="due_date") if lo <= c["due_date"] <= hi]
        return {"from": lo, "to": hi, "items": [{"date": c["due_date"], "description": c["description"],
                                                  "amount": fmt_inr(c["amount_paise"]), "certainty": c["certainty"]}
                                                 for c in rows]}


def ask(db: Database, question: str, client, as_of: date | None = None) -> dict:
    """Answer one question. Returns answer, tools used, model and any amount warning."""
    tools = Tools(db, as_of)
    results: list[dict] = []

    def run_tool(name, args):
        out = tools.run(name, args)
        results.append(out)
        return out

    context = (f"CashSense's as-of date (treat it as today) is {tools.as_of.isoformat()}; the forecast covers the "
               f"13 weeks to {(tools.as_of + timedelta(days=91)).isoformat()}.\nQuestion: ")
    res = client.chat_with_tools(load_skill("cashsense-assistant"), context + question[:500], TOOLS, run_tool)
    bad = unverified_amounts(res["answer"], {"results": results})
    answer = res["answer"] or "Sorry, I could not find that in CashSense."
    if bad:
        answer += " (Note: one or more amounts above could not be matched to CashSense data - please verify.)"
    db.audit("assistant", "answer_question", "assistant", "", {"question": question[:200],
                                                                "tools": [c["name"] for c in res["tool_calls"]],
                                                                "unverified_amounts": bad})
    return {"question": question, "answer": answer, "tools": res["tool_calls"], "model": res["model"],
            "unverified_amounts": bad}
