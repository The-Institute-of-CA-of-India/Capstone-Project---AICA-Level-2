"""Export to Tally: settings and a preview of the vouchers that will be created.

Phase 3 will write Tally Prime XML (import via Gateway of Tally > Import > Vouchers).
Purchases are previewed now. Sales need FIFO cost and gain (Phase 2) first.
"""
from __future__ import annotations

import json

import pandas as pd

DEFAULTS = {
    "company": "",
    "voucher_type": "Journal",
    "investment_ledger": "Investment in {script}",
    "investment_group": "Investments",
    "broker_ledger": "{broker}",
    "gain_ledger_st": "Short Term Capital Gain",
    "gain_ledger_lt": "Long Term Capital Gain",
    "capitalise_charges": True,
    "charges_ledger": "Brokerage and Share Transaction Charges",
    "broker_ledgers": {},
    "tally_url": "http://localhost:9000",
}

SCHEMA = "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT);"


def load(store) -> dict:
    store.db.executescript(SCHEMA)
    row = store.db.execute("SELECT value FROM app_settings WHERE key='tally'").fetchone()
    cfg = dict(DEFAULTS)
    if row:
        cfg.update(json.loads(row["value"]))
    return cfg


def save(store, cfg: dict) -> None:
    store.db.executescript(SCHEMA)
    store.db.execute("INSERT OR REPLACE INTO app_settings(key, value) VALUES ('tally', ?)", (json.dumps(cfg),))
    store.db.commit()


def preview(scrips: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """One voucher per contract note purchase row: Dr investment, Cr broker (net cost in rupees)."""
    if not len(scrips):
        return pd.DataFrame()
    out = []
    for _, r in scrips.iterrows():
        script = r["Name of Company"] or r["Script"]
        inv = cfg["investment_ledger"].format(script=script, symbol=r["Script"], isin=r["ISIN"])
        brk = cfg["broker_ledger"].format(broker=r["Broker"], ucc=r["UCC"])
        buy = r["Side"] == "BUY"
        out.append({
            "Date": r["Trade Date"], "Voucher Type": cfg["voucher_type"], "Client": r["Client / Account"],
            "Debit Ledger": inv if buy else brk, "Credit Ledger": brk if buy else inv,
            "Amount (Rs)": r["Net Cost / Proceeds (Rs)"],
            "Narration": f"{'Bought' if buy else 'Sold'} {r['Quantity']:g} {r['Script']} @ {r['Avg Gross Rate']:.2f} "
                         f"CN {r['Contract Note No']}",
            "Status": "Ready" if buy else "Needs FIFO cost and gain (Phase 2)",
        })
    return pd.DataFrame(out)
