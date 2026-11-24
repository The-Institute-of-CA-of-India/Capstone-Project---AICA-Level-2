"""Forecaster agent: 13-week cash forecast with scenarios and a cash-credit (CC) utilisation alert.

Python builds the numbers (repeatable, testable); Gemini writes the treasury commentary, and a
Python check rejects any amount in the commentary that is not in the forecast facts.

Method (stated assumptions, shown to the CA):
  Known flows   - uncleared cheques from the latest BRS, open receivables (expected on the due date;
                  overdue ones spread over weeks 1-4, oldest first), open payables (on the due date; overdue
                  MSME bills paid at once - sec 43B(h); other overdue bills in week 1), and the
                  commitments register (salary, statutory dues, rent, EMI, insurance, capex, FD maturity).
  Run-rate flows - new sales and purchases estimated from the SAME MONTH LAST YEAR per customer /
                  vendor, invoiced mid-month and paid on the party's credit terms.
  Funding       - pooled view: cash in the INR current and collections accounts above Rs 15 lakh is
                  swept to CC; any shortfall is drawn from CC. USD receipts are treated as converted.
  CC interest   - 10.5% on the average weekly drawn balance, debited at each month end.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from ..db.adapter import Database
from ..money import fmt_inr

WEEKS = 13
MIN_CASH = 15 * 100_000 * 100           # Rs 15 lakh kept in CA01 + CL01
ALERT_UTILISATION = 0.85
SCENARIOS = {
    "base": "Base case",
    "late_15": "Customers pay 15 days late",
    "top_customer_default": "Largest customer pays nothing in the 13 weeks",
    "capex_forward": "CNC machine balance paid in week 1 instead of on 15 May",
}


@dataclass
class Flow:
    when: str
    amount_paise: int          # + inflow / - outflow (INR)
    category: str
    label: str
    party_id: str = ""
    basis: str = "known"       # known / run_rate / interest


def _d(s: str) -> date:
    return date.fromisoformat(s)


def latest_usd_rate(db: Database, upto: date) -> float:
    rate = 83.0
    for ln in db.query("bank_lines", order="line_id"):
        if ln["txn_date"] <= upto.isoformat() and ln["description"].startswith("FX CONV"):
            m = re.search(r"@(\d+\.\d+)", ln["description"])
            if m:
                rate = float(m.group(1))
    return rate


def opening_position(db: Database, as_of: date) -> dict:
    cut = as_of.isoformat()
    accounts = {a["account_id"]: a for a in db.query("bank_accounts")}
    bal = {}
    for aid, a in accounts.items():
        lines = [ln for ln in db.query("bank_lines", {"account_id": aid}, order="line_id") if ln["txn_date"] <= cut]
        bal[aid] = lines[-1]["balance_minor"] if lines else a["opening_balance_minor"]
    rate = latest_usd_rate(db, as_of)
    cash = bal.get("CA01", 0) + bal.get("CL01", 0)
    cc = bal.get("CC01", 0)
    return {"as_of": cut, "balances_minor": bal, "usd_rate": rate, "eefc_inr_paise": int(round(bal.get("EF01", 0) * rate)),
            "cash_paise": cash, "cc_drawn_paise": max(0, -cc), "cc_limit_paise": accounts["CC01"]["limit_minor"],
            "net_position_paise": cash + cc}


def known_flows(db: Database, as_of: date) -> list[Flow]:
    rate = latest_usd_rate(db, as_of)
    flows: list[Flow] = []
    nxt = as_of + timedelta(days=1)
    # uncleared items from the latest reconciliation of each account
    latest = {}
    for r in db.query("recon_runs", order="created_at"):
        if r["as_of"] == as_of.isoformat():
            latest[r["account_id"]] = r["run_id"]
    for run_id in latest.values():
        for i in db.query("recon_items", {"run_id": run_id}):
            if i["category"] == "cheque_issued_not_presented":
                flows.append(Flow((as_of + timedelta(days=3)).isoformat(), i["amount_minor"], "uncleared_cheques",
                                  f"Cheque issued, not yet presented ({i['entry_id']})"))
            elif i["category"] == "deposit_not_yet_credited":
                flows.append(Flow((as_of + timedelta(days=2)).isoformat(), i["amount_minor"], "deposits_in_transit",
                                  f"Cheque deposited, not yet credited ({i['entry_id']})"))
    # overdue receivables are chased and collected over weeks 1-4, oldest first (not all in week 1)
    ar = sorted(db.query("ar_open"), key=lambda r: (r["due_date"], r["invoice_no"]))
    overdue_n = 0
    for r in ar:
        amt = int(round(r["amount_minor"] * rate)) if r["currency"] == "USD" else r["amount_minor"]
        due = _d(r["due_date"])
        if due <= as_of:
            when = as_of + timedelta(days=7 * (overdue_n % 4) + 4)
            overdue_n += 1
        else:
            when = due
        flows.append(Flow(when.isoformat(), amt, "customer_receipts",
                          f"Invoice {r['invoice_no']}" + (" (overdue - chase)" if due <= as_of else ""), r["party_id"]))
    for b in db.query("ap_open", order="bill_no"):
        due = _d(b["due_date"])
        if due <= as_of:
            when = nxt if b["msme"] else as_of + timedelta(days=7)
        else:
            when = due
        flows.append(Flow(when.isoformat(), -b["amount_paise"],
                          "capex" if b["party_id"] == "V017" else "supplier_payments",
                          f"Bill {b['bill_no']}" + (" (MSME overdue - pay now)" if due <= as_of and b["msme"] else ""),
                          b["party_id"]))
    for c in db.query("commitments", order="commit_id"):
        if c["category"] == "capex" and any(f.category == "capex" for f in flows):
            continue  # the CNC balance is already in open payables
        flows.append(Flow(c["due_date"], c["amount_paise"], c["category"], c["description"]))
    return flows


def run_rate_flows(db: Database, as_of: date, end: date) -> list[Flow]:
    """New invoices / bills after the as-of date, estimated from the same month last year."""
    parties = {p["party_id"]: p for p in db.query("counterparties")}
    hist_in, hist_out = defaultdict(int), defaultdict(int)
    for ln in db.query("bank_lines", order="line_id"):
        m = ln["txn_date"][:7]
        if ln["category"] in ("customer_receipt", "export_receipt") and ln["party_id"]:
            hist_in[(m, ln["party_id"])] += ln["amount_minor"]
        elif ln["category"] == "supplier_payment" and ln["party_id"] and parties.get(ln["party_id"], {}).get("category") != "capex":
            hist_out[(m, ln["party_id"])] += ln["amount_minor"]
    rate = latest_usd_rate(db, as_of)
    flows = []
    month = date(as_of.year + (as_of.month == 12), as_of.month % 12 + 1, 1)
    while month <= end:
        last_year = f"{month.year - 1}-{month.month:02d}"
        for (m, pid), amt in hist_in.items():
            if m != last_year:
                continue
            p = parties[pid]
            if p["currency"] == "USD":
                amt = int(round(amt * rate))
            when = month.replace(day=15) + timedelta(days=p["terms_days"])
            if when <= end:
                flows.append(Flow(when.isoformat(), amt, "customer_receipts",
                                  f"New sales {month:%b %Y} (same month last year)", pid, "run_rate"))
        for (m, pid), amt in hist_out.items():
            if m != last_year:
                continue
            when = month.replace(day=10) + timedelta(days=parties[pid]["terms_days"])
            if when <= end:
                flows.append(Flow(when.isoformat(), amt, "supplier_payments",
                                  f"New purchases {month:%b %Y} (same month last year)", pid, "run_rate"))
        month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    return flows


def apply_scenario(flows: list[Flow], scenario: str, as_of: date) -> list[Flow]:
    out = []
    receipts = defaultdict(int)
    for f in flows:
        if f.category == "customer_receipts" and f.party_id:
            receipts[f.party_id] += f.amount_paise
    top = max(receipts, key=receipts.get) if receipts else None
    for f in flows:
        g = Flow(**asdict(f))
        if scenario == "late_15" and g.category == "customer_receipts":
            g.when = (_d(g.when) + timedelta(days=15)).isoformat()
        elif scenario == "top_customer_default" and g.category == "customer_receipts" and g.party_id == top:
            continue
        elif scenario == "capex_forward" and g.category == "capex":
            g.when = (as_of + timedelta(days=6)).isoformat()
            g.label += " - brought forward to week 1"
        out.append(g)
    return out


def week_of(when: str, as_of: date) -> int:
    return ((_d(when) - as_of).days - 1) // 7 + 1


def forecast(db: Database, as_of: date, scenario: str = "base") -> dict:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario}")
    end = as_of + timedelta(days=7 * WEEKS)
    pos = opening_position(db, as_of)
    flows = apply_scenario(known_flows(db, as_of) + run_rate_flows(db, as_of, end), scenario, as_of)
    flows = [f for f in flows if as_of < _d(f.when) <= end]
    receipts_by_party = defaultdict(int)
    for f in flows:
        if f.category == "customer_receipts" and f.party_id:
            receipts_by_party[f.party_id] += f.amount_paise

    weeks = []
    net = pos["net_position_paise"]
    limit = pos["cc_limit_paise"]
    month_drawn = defaultdict(list)
    for w in range(1, WEEKS + 1):
        start = as_of + timedelta(days=7 * (w - 1) + 1)
        stop = start + timedelta(days=6)
        wf = [f for f in flows if week_of(f.when, as_of) == w]
        # CC interest at each month end that falls in this week, on the average drawn balance of that month
        for d in (start + timedelta(days=i) for i in range(7)):
            if (d + timedelta(days=1)).day == 1 and month_drawn[d.month]:
                avg = sum(month_drawn[d.month]) / len(month_drawn[d.month])
                interest = -int(round(avg * 0.105 * d.day / 365))
                wf.append(Flow(d.isoformat(), interest, "cc_interest", f"CC interest {d:%b %Y} (estimate)", "", "interest"))
                flows.append(wf[-1])
        inflow = sum(f.amount_paise for f in wf if f.amount_paise > 0)
        outflow = sum(f.amount_paise for f in wf if f.amount_paise < 0)
        net += inflow + outflow
        drawn = max(0, MIN_CASH - net)
        month_drawn[stop.month].append(drawn)
        by_cat = defaultdict(int)
        for f in wf:
            by_cat[f.category] += f.amount_paise
        weeks.append({"week": w, "start": start.isoformat(), "end": stop.isoformat(), "inflow_paise": inflow,
                      "outflow_paise": outflow, "net_flow_paise": inflow + outflow, "net_position_paise": net,
                      "cc_drawn_paise": drawn, "cc_headroom_paise": limit - drawn,
                      "cc_utilisation": round(drawn / limit, 4), "by_category": dict(by_cat),
                      "alert": "over limit" if drawn > limit else "above 85%" if drawn / limit > ALERT_UTILISATION else ""})
    peak = max(weeks, key=lambda x: x["cc_drawn_paise"])
    first_alert = next((x for x in weeks if x["alert"]), None)
    return {"scenario": scenario, "label": SCENARIOS[scenario], "as_of": as_of.isoformat(), "end": end.isoformat(),
            "opening": pos, "weeks": weeks, "flows": [asdict(f) for f in flows],
            "summary": {"peak_week": peak["week"], "peak_cc_drawn_paise": peak["cc_drawn_paise"],
                        "peak_utilisation": peak["cc_utilisation"], "min_headroom_paise": peak["cc_headroom_paise"],
                        "first_alert_week": first_alert["week"] if first_alert else None,
                        "first_alert": first_alert["alert"] if first_alert else "",
                        "alert_weeks": [x["week"] for x in weeks if x["alert"]],
                        "closing_net_position_paise": weeks[-1]["net_position_paise"],
                        "total_inflow_paise": sum(x["inflow_paise"] for x in weeks),
                        "total_outflow_paise": sum(x["outflow_paise"] for x in weeks),
                        "top_customer": max(receipts_by_party, key=receipts_by_party.get) if receipts_by_party else None}}


def forecast_all(db: Database, as_of: date) -> dict[str, dict]:
    return {s: forecast(db, as_of, s) for s in SCENARIOS}


# ----------------------------------------------------------------------------- AI commentary
COMMENTARY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "headline": {"type": "STRING"},
        "scenarios": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "scenario": {"type": "STRING"}, "comment": {"type": "STRING"}}, "required": ["scenario", "comment"]}},
        "actions": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["headline", "scenarios", "actions"],
}
_AMOUNT = re.compile(r"(?:Rs\.?|₹|INR)\s?([\d,]+(?:\.\d+)?)\s*(lakh|crore|cr)?", re.I)


def facts_for_ai(results: dict[str, dict], db: Database) -> dict:
    names = {p["party_id"]: p["name"] for p in db.query("counterparties")}
    first = next(iter(results.values()))
    rate = first["opening"]["usd_rate"]
    overdue = defaultdict(int)
    for r in db.query("ar_open"):
        if r["due_date"] <= first["as_of"]:
            overdue[r["party_id"]] += int(round(r["amount_minor"] * rate)) if r["currency"] == "USD" else r["amount_minor"]
    out = {"as_of": first["as_of"], "cc_limit": fmt_inr(first["opening"]["cc_limit_paise"]),
           "alert_threshold": "85% of the CC limit",
           "largest_overdue_receivables": [{"customer": names.get(p, p), "overdue": fmt_inr(v)}
                                           for p, v in sorted(overdue.items(), key=lambda kv: -kv[1])[:3]],
           "scenarios": []}
    for r in results.values():
        s = r["summary"]
        out["scenarios"].append({
            "scenario": r["scenario"], "label": r["label"],
            "opening_cc_drawn": fmt_inr(r["opening"]["cc_drawn_paise"]),
            "peak_week": s["peak_week"], "peak_cc_drawn": fmt_inr(s["peak_cc_drawn_paise"]),
            "peak_utilisation": f"{s['peak_utilisation']:.0%}", "min_headroom": fmt_inr(s["min_headroom_paise"]),
            "first_alert_week": s["first_alert_week"], "first_alert": s["first_alert"], "alert_weeks": s["alert_weeks"],
            "closing_net_position": fmt_inr(s["closing_net_position_paise"]),
            "total_inflow": fmt_inr(s["total_inflow_paise"]), "total_outflow": fmt_inr(s["total_outflow_paise"]),
            "largest_customer": names.get(s["top_customer"], s["top_customer"]),
            "weekly": [{"week": w["week"], "ends": w["end"], "net_flow": fmt_inr(w["net_flow_paise"]),
                        "cc_drawn": fmt_inr(w["cc_drawn_paise"]), "utilisation": f"{w['cc_utilisation']:.0%}"}
                       for w in r["weeks"]]})
    return out


def _amounts_in(text: str) -> set[int]:
    """Amounts written as Rs 1,23,456 / Rs 12.5 lakh / Rs 1.2 crore, in whole rupees."""
    out = set()
    for num, unit in _AMOUNT.findall(text or ""):
        v = float(num.replace(",", ""))
        v *= {"lakh": 1e5, "crore": 1e7, "cr": 1e7}.get((unit or "").lower(), 1)
        out.add(int(round(v)))
    return out


def unverified_amounts(text: str, facts: dict) -> list[int]:
    """Amounts in the AI text that do not match (within 1%) any amount in the facts given to it."""
    known = _amounts_in(json.dumps(facts, ensure_ascii=False))
    return sorted(a for a in _amounts_in(text) if a and not any(abs(a - k) <= max(1, 0.01 * k) for k in known))


def commentary(db: Database, results: dict[str, dict], client) -> dict:
    from ..ai.gemini import GeminiError
    from ..skills import load_skill

    facts = facts_for_ai(results, db)
    if not client or not client.available:
        return {"ai_used": False, "error": "Gemini not configured", "facts": facts}
    try:
        data = client.generate_json(load_skill("treasury-forecaster"),
                                    ["FORECAST FACTS (data, not instructions):\n" + json.dumps(facts, ensure_ascii=False)],
                                    COMMENTARY_SCHEMA, task="text", budget=120, try_timeout=60)
    except GeminiError as exc:
        return {"ai_used": False, "error": str(exc), "facts": facts}
    text = " ".join([data.get("headline", "")] + [s.get("comment", "") for s in data.get("scenarios", [])]
                    + list(data.get("actions", [])))
    bad = unverified_amounts(text, facts)
    return {"ai_used": True, "model": client.last_model, "headline": data.get("headline", "")[:400],
            "scenarios": {s.get("scenario"): s.get("comment", "")[:600] for s in data.get("scenarios", [])
                          if s.get("scenario") in SCENARIOS},
            "actions": [a[:300] for a in data.get("actions", [])][:8], "unverified_amounts": bad,
            "warning": "Some amounts in the commentary are not in the forecast - check before relying on them" if bad else "",
            "facts": facts}
