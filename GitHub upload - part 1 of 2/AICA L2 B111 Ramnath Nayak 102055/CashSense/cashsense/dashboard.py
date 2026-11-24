"""Data for the mobile dashboard (read-only) and the cached Gemini forecast commentary."""
from __future__ import annotations

import json
from datetime import date

from .agents.forecaster import SCENARIOS, commentary, forecast_all
from .db.adapter import Database
from .money import fmt_amount, fmt_inr


def dashboard_data(db: Database, as_of: date) -> dict:
    fc = forecast_all(db, as_of)
    o = fc["base"]["opening"]
    acc = {a["account_id"]: a for a in db.query("bank_accounts", order="account_id")}
    latest = {}
    for r in db.query("recon_runs", order="created_at"):
        latest[r["account_id"]] = r
    flags = db.query("risk_flags", order="flag_id")
    names = {p["party_id"]: p["name"] for p in db.query("counterparties")}
    cached = db.get_state(f"forecast_commentary:{as_of.isoformat()}", "")
    return {
        "as_of": as_of.isoformat(),
        "kpis": {"cash": fmt_inr(o["cash_paise"]), "cc_drawn": fmt_inr(o["cc_drawn_paise"]),
                 "cc_limit": fmt_inr(o["cc_limit_paise"]), "cc_util": o["cc_drawn_paise"] / o["cc_limit_paise"],
                 "eefc": fmt_amount(o["balances_minor"].get("EF01", 0), "USD"), "eefc_inr": fmt_inr(o["eefc_inr_paise"]),
                 "net": fmt_inr(o["net_position_paise"]),
                 "open_risks": sum(f["status"] in ("open", "escalated") for f in flags),
                 "high_risks": sum(f["status"] in ("open", "escalated") and f["severity"] == "high" for f in flags),
                 "pending": len(db.query("approvals", {"status": "pending"}))},
        "accounts": [{"id": aid, "name": a["name"], "balance": fmt_amount(o["balances_minor"].get(aid, 0), a["currency"]),
                      "status": latest[aid]["status"] if aid in latest else "not run",
                      "items": json.loads(latest[aid]["summary"])["items"] if aid in latest else {}}
                     for aid, a in acc.items()],
        "scenarios": [{"code": s, "label": r["label"], "peak_util": r["summary"]["peak_utilisation"],
                       "peak_week": r["summary"]["peak_week"], "peak_drawn": fmt_inr(r["summary"]["peak_cc_drawn_paise"]),
                       "first_alert_week": r["summary"]["first_alert_week"],
                       "util": [w["cc_utilisation"] for w in r["weeks"]],
                       "net_flow_lakh": [round(w["net_flow_paise"] / 1e7, 2) for w in r["weeks"]],
                       "weeks": [{"week": w["week"], "end": w["end"], "inflow": fmt_inr(w["inflow_paise"]),
                                  "outflow": fmt_inr(-w["outflow_paise"]), "drawn": fmt_inr(w["cc_drawn_paise"]),
                                  "util": w["cc_utilisation"], "alert": w["alert"]} for w in r["weeks"]]}
                      for s, r in fc.items()],
        "risks": [{"type": f["flag_type"].replace("_", " "), "severity": f["severity"], "status": f["status"],
                   "party": names.get(f["party_id"], ""), "amount": fmt_inr(abs(f["amount_minor"] or 0)),
                   "text": (f["explanation"] or "")[:220]} for f in flags],
        "commentary": json.loads(cached) if cached else None,
    }


def refresh_commentary(db: Database, as_of: date, client) -> dict:
    res = commentary(db, forecast_all(db, as_of), client)
    res.pop("facts", None)
    if res.get("ai_used"):
        db.set_state(f"forecast_commentary:{as_of.isoformat()}", json.dumps(res))
    return res


__all__ = ["dashboard_data", "refresh_commentary", "SCENARIOS"]
