"""Daily briefing payload, sent to the Google Apps Script web app (which logs it to a Sheet, emails it and
runs the reminder schedulers). Uses APPS_SCRIPT_URL and APPS_SCRIPT_SECRET from .env."""
from __future__ import annotations

import json
import secrets
from datetime import date

import requests

from . import config
from .agents.forecaster import forecast_all
from .db.adapter import Database
from .money import fmt_amount, fmt_inr


def secret() -> str:
    s = config.setting("APPS_SCRIPT_SECRET")
    if not s:
        s = secrets.token_urlsafe(24)
        config.save_setting("APPS_SCRIPT_SECRET", s)
    return s


def build(db: Database, as_of: date) -> dict:
    fc = forecast_all(db, as_of)
    o = fc["base"]["opening"]
    worst = max(fc.values(), key=lambda r: r["summary"]["peak_utilisation"])
    latest = {}
    for r in db.query("recon_runs", order="created_at"):
        if r["as_of"] == as_of.isoformat():
            latest[r["account_id"]] = r
    cur = {a["account_id"]: a["currency"] for a in db.query("bank_accounts")}
    flags = [f for f in db.query("risk_flags", order="flag_id") if f["status"] in ("open", "escalated")]
    cached = db.get_state(f"forecast_commentary:{as_of.isoformat()}", "")
    comm = json.loads(cached) if cached else {}
    return {
        "as_of": as_of.isoformat(), "cash": fmt_inr(o["cash_paise"]), "cc_drawn": fmt_inr(o["cc_drawn_paise"]),
        "cc_use_today": f"{o['cc_drawn_paise'] / o['cc_limit_paise']:.0%}",
        "worst_scenario": worst["label"], "worst_peak_use": f"{worst['summary']['peak_utilisation']:.0%}",
        "first_alert_week": worst["summary"]["first_alert_week"],
        "scenarios": [{"label": r["label"], "peak_use": f"{r['summary']['peak_utilisation']:.0%}",
                       "peak_week": r["summary"]["peak_week"], "first_alert_week": r["summary"]["first_alert_week"]}
                      for r in fc.values()],
        "reconciliations": [{"account_id": aid, "status": r["status"],
                             "bank": fmt_amount(r["bank_balance_minor"], cur[aid])} for aid, r in sorted(latest.items())],
        "all_brs_agreed": bool(latest) and all(r["status"] == "agreed" for r in latest.values()),
        "open_risks": len(flags), "high_risks": sum(f["severity"] == "high" for f in flags),
        "risks": [{"severity": f["severity"], "text": (f["explanation"] or "")[:200]} for f in flags[:6]],
        "pending_approvals": len(db.query("approvals", {"status": "pending"})),
        "headline": comm.get("headline", ""), "actions": comm.get("actions", [])[:5],
    }


def send(briefing: dict, ping: bool = False, send_email: bool = True) -> dict:
    url = config.setting("APPS_SCRIPT_URL")
    if not url:
        return {"ok": False, "error": "APPS_SCRIPT_URL not set in .env"}
    try:
        r = requests.post(url, json={"secret": secret(), "briefing": briefing, "ping": ping, "send_email": send_email},
                          timeout=60, allow_redirects=True)
        return r.json()
    except (requests.RequestException, ValueError) as exc:
        return {"ok": False, "error": f"Apps Script not reachable ({type(exc).__name__})"}
