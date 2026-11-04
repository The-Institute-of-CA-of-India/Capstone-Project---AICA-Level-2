"""Cost reconciliation: FIFO cost of holdings as per the app vs investment ledger balances in Tally."""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from . import fifo, tally_link

SCHEMA = """
CREATE TABLE IF NOT EXISTS cost_recon_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, person_key TEXT, person TEXT, as_on TEXT, broker TEXT,
  source TEXT, scripts INTEGER, matched INTEGER, cost_app INTEGER, cost_tally INTEGER, result TEXT);
"""
TOLERANCE = 1.0      # rupees: costs are kept in whole rupees
COLUMNS = ["ISIN", "Script", "Name of Company", "Qty as per App", "Cost as per App", "Tally Ledger",
           "Balance as per Tally", "Difference (Tally - App)", "Status", "Oldest lot", "Shortage qty"]
ORDER = {"Difference": 0, "Opening holding missing": 1, "Ledger not found": 2, "Only in Tally": 3, "Matched": 4}


def ensure(store):
    store.db.executescript(SCHEMA)
    tally_link.ensure(store)


def saved_map(store, person_key) -> dict:
    ensure(store)
    return {r["key"]: r["ledger"] for r in store.query("SELECT key, ledger FROM tally_map WHERE person_key=?",
                                                       (person_key,))}


def reconcile(store, person_key: str, as_on: str, ledgers: pd.DataFrame, cfg: dict, broker: str = "",
              group: str = "") -> pd.DataFrame:
    """ledgers: Ledger, Group, Balance (debit positive). group: only ledgers under this Tally group count as
    investments for 'Only in Tally' (blank = every ledger that was matched or looks like an investment)."""
    ensure(store)
    hold = fifo.holdings(store, person_key, as_on, broker)
    names = {r["isin"]: (r["symbol"], r["company_name"]) for r in
             store.query("SELECT isin, symbol, company_name FROM scrip_master")}
    led_names = list(ledgers["Ledger"]) if len(ledgers) else []
    bal = dict(zip(ledgers["Ledger"], ledgers["Balance"])) if len(ledgers) else {}
    mapping = saved_map(store, person_key)
    pattern = cfg.get("investment_ledger") or "Investment in {script}"
    used, out = set(), []
    for _, h in hold.iterrows():
        sym, comp = names.get(h["isin"], ("", ""))
        sym = sym or h["symbol"] or ""
        led = mapping.get(h["key"])
        if led is None or (led and led not in bal):
            led = tally_link.auto_ledger(led_names, sym, comp, pattern)
        tb = bal.get(led) if led else None
        if led:
            used.add(led)
        cost = int(h["cost"])
        diff = None if tb is None else round(float(tb) - cost)
        status = ("Opening holding missing" if h["shortage"] > 0 else
                  "Ledger not found" if tb is None else
                  "Matched" if abs(diff) <= TOLERANCE else "Difference")
        out.append({"ISIN": h["isin"], "Script": sym, "Name of Company": comp, "Qty as per App": float(h["qty"]),
                    "Cost as per App": cost, "Tally Ledger": led or "", "Balance as per Tally": tb,
                    "Difference (Tally - App)": diff, "Status": status, "Oldest lot": h["oldest_lot"],
                    "Shortage qty": float(h["shortage"])})
    grp = (group or "").strip().lower()
    prefix = pattern.split("{")[0].strip().lower()
    for _, l in ledgers.iterrows():
        if l["Ledger"] in used or abs(float(l["Balance"] or 0)) < 0.5:
            continue
        lg = str(l.get("Group") or "").strip().lower()
        under = [x.strip().lower() for x in str(l.get("Under") or lg).split(" > ")]
        if lg:                                # Tally told us the group (and the groups above it)
            in_group = grp in under if grp else False
        else:                                 # an export without groups: go by the ledger name
            n = str(l["Ledger"]).lower()
            in_group = bool(prefix and n.startswith(prefix)) or any(w in n for w in ("investment", "shares", "equity"))
        if in_group:
            out.append({"ISIN": "", "Script": "", "Name of Company": "", "Qty as per App": 0.0, "Cost as per App": 0,
                        "Tally Ledger": l["Ledger"], "Balance as per Tally": float(l["Balance"]),
                        "Difference (Tally - App)": round(float(l["Balance"])), "Status": "Only in Tally",
                        "Oldest lot": "", "Shortage qty": 0.0})
    res = pd.DataFrame(out, columns=COLUMNS)
    if len(res):
        res = res.sort_values(by=["Status", "Script"], key=lambda c: c.map(ORDER) if c.name == "Status" else c)
    return res.reset_index(drop=True)


def save_run(store, person_key, person, as_on, broker, source, res: pd.DataFrame) -> int:
    ensure(store)
    cur = store.db.execute(
        "INSERT INTO cost_recon_runs(at, person_key, person, as_on, broker, source, scripts, matched, cost_app, "
        "cost_tally, result) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), person_key, person, as_on, broker or "All brokers", source,
         len(res), int((res["Status"] == "Matched").sum()), int(res["Cost as per App"].sum()),
         int(round(res["Balance as per Tally"].fillna(0).sum())), res.to_json(orient="records")))
    store.db.commit()
    store.log(f"{person} as on {as_on}", "Cost reconciled",
              f"{len(res)} scripts, {int((res['Status'] == 'Matched').sum())} matched ({source})")
    return cur.lastrowid


def runs(store) -> pd.DataFrame:
    ensure(store)
    rows = store.query("SELECT id _id, at Time, person Person, as_on 'As on Date', broker 'Broker', source Source, "
                       "scripts Scripts, matched Matched, cost_app 'Cost as per App', cost_tally 'Balance as per Tally' "
                       "FROM cost_recon_runs ORDER BY id DESC")
    return pd.DataFrame(rows, columns=["_id", "Time", "Person", "As on Date", "Broker", "Source", "Scripts", "Matched",
                                       "Cost as per App", "Balance as per Tally"])


def run_result(store, run_id: int) -> pd.DataFrame:
    r = store.query("SELECT result FROM cost_recon_runs WHERE id=?", (run_id,))
    return pd.DataFrame(json.loads(r[0]["result"]) if r else [], columns=COLUMNS)
