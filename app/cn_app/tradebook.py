"""Broker tradebook files (e.g. Zerodha 'tradebook-XXXX-EQ.xlsx').

A tradebook has trades but no charges, so it never creates cost records. It is
stored only to cross-check that every trade has a contract note.
"""
from __future__ import annotations

import io

import pandas as pd


def try_import(doc, store, log):
    try:
        raw = pd.read_excel(io.BytesIO(doc.data), header=None, sheet_name=0)
    except Exception:  # noqa: BLE001
        return None
    flat = raw.astype(str)
    hdr_row = next((i for i, row in flat.iterrows() if "Trade ID" in row.values and "ISIN" in row.values), None)
    if hdr_row is None:
        return None
    ucc = ""
    for _, row in flat.iterrows():
        vals = list(row.values)
        if "Client ID" in vals:
            ucc = vals[vals.index("Client ID") + 1]
            break
    df = raw.iloc[hdr_row + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[hdr_row]]
    df = df.dropna(subset=["Trade ID"])
    n = 0
    with store.db:
        for _, r in df.iterrows():
            cur = store.db.execute(
                "INSERT OR IGNORE INTO tradebook(broker, ucc, trade_id, exchange, trade_date, symbol, isin, side, qty, "
                "price, order_id, source_file) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                ("Zerodha Broking", ucc, str(int(r["Trade ID"])) if isinstance(r["Trade ID"], float) else str(r["Trade ID"]),
                 str(r["Exchange"]), str(r["Trade Date"])[:10], r["Symbol"], r["ISIN"],
                 str(r["Trade Type"]).upper(), float(r["Quantity"]), float(r["Price"]), str(r["Order ID"]), doc.origin))
            n += cur.rowcount
    log(doc.origin, "Tradebook", f"{n} new trade(s) stored for cross-check (no charges, not used for cost)")
    return n


def cross_check(store):
    """Tradebook trades with no matching contract-note trade."""
    return store.query(
        "SELECT tb.ucc, tb.trade_date, tb.exchange, tb.trade_id, tb.symbol, tb.isin, tb.side, tb.qty, tb.price, "
        "CASE WHEN t.id IS NULL THEN 'No contract note found' ELSE 'Matched' END AS status, t.cn_no "
        "FROM tradebook tb LEFT JOIN trades t ON t.trade_no = tb.trade_id AND t.exchange = tb.exchange "
        "AND t.isin = tb.isin ORDER BY tb.trade_date, tb.trade_id")
