"""Export a Power BI-ready star schema (CSV) plus DAX measures. Amounts are in rupees (not paise)."""
from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

from .agents.forecaster import SCENARIOS, forecast_all, latest_usd_rate
from .db.adapter import Database

MEASURES = """// CashSense DAX measures - paste into a new table or the fact tables (Modeling > New measure)
Inflow = SUM ( fact_forecast_week[inflow] )
Outflow = SUM ( fact_forecast_week[outflow] )
Net Flow = SUM ( fact_forecast_week[net_flow] )
CC Drawn = SUM ( fact_forecast_week[cc_drawn] )
CC Limit = 20000000
CC Utilisation = DIVIDE ( [CC Drawn], [CC Limit] )
Peak CC Utilisation = MAXX ( VALUES ( fact_forecast_week[week] ), [CC Utilisation] )
Weeks Above 85% = COUNTROWS ( FILTER ( fact_forecast_week, fact_forecast_week[cc_utilisation] > 0.85 ) )
Bank Lines = COUNTROWS ( fact_bank_line )
Lines For Review = CALCULATE ( [Bank Lines], fact_bank_line[review_status] = "review" )
Open Risks = CALCULATE ( COUNTROWS ( fact_risk ), fact_risk[status] IN { "open", "escalated" } )
High Risks = CALCULATE ( [Open Risks], fact_risk[severity] = "high" )
Unreconciled Amount = SUM ( fact_recon_item[adjust_inr] )
"""


def _write(path: Path, header: list[str], rows: list[list]) -> int:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return len(rows)


def export(db: Database, as_of: date, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rate = latest_usd_rate(db, as_of)
    acc = {a["account_id"]: a for a in db.query("bank_accounts")}
    r = lambda p: round(p / 100, 2)  # noqa: E731
    counts = {}
    counts["dim_account"] = _write(out_dir / "dim_account.csv", ["account_id", "name", "type", "currency", "bank"],
                                   [[a["account_id"], a["name"], a["account_type"], a["currency"], a["bank_name"]]
                                    for a in acc.values()])
    counts["dim_party"] = _write(out_dir / "dim_party.csv", ["party_id", "name", "type", "category", "msme", "terms_days"],
                                 [[p["party_id"], p["name"], p["party_type"], p["category"], p["msme"], p["terms_days"]]
                                  for p in db.query("counterparties")])
    start, end = date(2025, 4, 1), as_of + timedelta(days=91)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    counts["dim_date"] = _write(out_dir / "dim_date.csv", ["date", "year", "month", "month_name", "fy", "is_forecast"],
                                [[d.isoformat(), d.year, d.month, d.strftime("%b %Y"),
                                  f"FY {d.year - (d.month < 4)}-{(d.year - (d.month < 4) + 1) % 100:02d}", int(d > as_of)]
                                 for d in days])
    counts["fact_bank_line"] = _write(
        out_dir / "fact_bank_line.csv",
        ["line_id", "account_id", "date", "description", "amount", "currency", "amount_inr", "category", "party_id",
         "review_status"],
        [[ln["line_id"], ln["account_id"], ln["txn_date"], ln["description"], r(ln["amount_minor"]),
          acc[ln["account_id"]]["currency"],
          r(ln["amount_minor"] * (rate if acc[ln["account_id"]]["currency"] == "USD" else 1)),
          ln["category"] or "", ln["party_id"] or "", ln["review_status"] or ""]
         for ln in db.query("bank_lines", order="line_id")])
    fc = forecast_all(db, as_of)
    counts["fact_forecast_week"] = _write(
        out_dir / "fact_forecast_week.csv",
        ["scenario", "scenario_label", "week", "week_start", "week_end", "inflow", "outflow", "net_flow",
         "net_position", "cc_drawn", "cc_headroom", "cc_utilisation", "alert"],
        [[s, SCENARIOS[s], w["week"], w["start"], w["end"], r(w["inflow_paise"]), r(-w["outflow_paise"]),
          r(w["net_flow_paise"]), r(w["net_position_paise"]), r(w["cc_drawn_paise"]), r(w["cc_headroom_paise"]),
          w["cc_utilisation"], w["alert"]] for s, res in fc.items() for w in res["weeks"]])
    counts["fact_forecast_flow"] = _write(
        out_dir / "fact_forecast_flow.csv", ["scenario", "date", "category", "label", "party_id", "basis", "amount"],
        [[s, f["when"], f["category"], f["label"], f["party_id"], f["basis"], r(f["amount_paise"])]
         for s, res in fc.items() for f in res["flows"]])
    latest = {}
    for run in db.query("recon_runs", order="created_at"):
        latest[run["account_id"]] = run["run_id"]
    items = [i for rid in latest.values() for i in db.query("recon_items", {"run_id": rid})]
    counts["fact_recon_item"] = _write(
        out_dir / "fact_recon_item.csv", ["account_id", "category", "side", "date", "amount", "adjust_inr", "explanation"],
        [[i["account_id"], i["category"], i["side"], i["item_date"], r(i["amount_minor"]),
          r(i["adjust_minor"] * (rate if acc[i["account_id"]]["currency"] == "USD" else 1)), i["explanation"]]
         for i in items])
    counts["fact_risk"] = _write(
        out_dir / "fact_risk.csv", ["flag_id", "type", "severity", "status", "account_id", "party_id", "date", "amount",
                                    "explanation", "action"],
        [[f["flag_id"], f["flag_type"], f["severity"], f["status"], f["account_id"] or "", f["party_id"] or "",
          f["flag_date"], r(abs(f["amount_minor"] or 0)), f["explanation"], f["action"]]
         for f in db.query("risk_flags", order="flag_id")])
    (out_dir / "measures.dax").write_text(MEASURES, encoding="utf-8")
    (out_dir / "export_info.json").write_text(json.dumps({"as_of": as_of.isoformat(), "usd_rate": rate,
                                                          "tables": counts}, indent=1), encoding="utf-8")
    return counts
