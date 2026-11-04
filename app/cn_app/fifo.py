"""FIFO lots: quantity and cost of holdings as on a date.

Purchase lots come from opening holdings (date of purchase, quantity, total cost) and
contract-note purchases (net cost in rupees, charges included). Sales consume the
oldest lots first. On the same date, sales are applied before that day's purchases,
because an investor sells from shares already held (as agreed for this project).
Costs are kept in whole rupees as per the project rule; the cost of a partly sold lot
is split in proportion to quantity.
"""
from __future__ import annotations

from collections import defaultdict, deque

import pandas as pd


def _events(store, person_key: str, as_on: str, broker: str = ""):
    ev = []
    if person_key and not person_key.startswith("NAME:"):
        q = ("SELECT n.trade_date d, s.isin, s.symbol, s.side, s.qty, s.net_rupees cost, n.cn_no ref, n.broker, "
             "n.id note_id "
             "FROM scrips s JOIN notes n ON n.id=s.note_id WHERE n.pan=? AND n.trade_date<=?")
        args = [person_key, as_on]
        if broker:
            q += " AND n.broker=?"
            args.append(broker)
        for r in store.query(q, tuple(args)):
            ev.append({**r, "src": "Contract note"})
    where, arg = (("UPPER(o.person)=?", person_key[5:]) if person_key.startswith("NAME:") else ("o.pan=?", person_key))
    q = (f"SELECT o.purchase_date d, COALESCE(NULLIF(o.isin,''), 'NAME:' || o.script) isin, o.script symbol,"
         f" o.qty, o.total_cost cost, o.sale_date, o.sale_value, o.broker FROM opening_lots o "
         f"WHERE {where} AND o.purchase_date<=?")
    args = [arg, as_on]
    if broker:
        q += " AND (o.broker='' OR o.broker IS NULL OR ? LIKE '%' || o.broker || '%' OR o.broker LIKE '%' || ? || '%')"
        args += [broker, broker.split()[0]]
    for r in store.query(q, tuple(args)):
        ev.append({"d": r["d"], "isin": r["isin"], "symbol": r["symbol"], "side": "BUY", "qty": r["qty"],
                   "cost": r["cost"], "ref": "Opening holding", "broker": r["broker"], "src": "Opening holding"})
        if r["sale_date"] and r["sale_date"] <= as_on:     # sold lot recorded in the holdings sheet
            ev.append({"d": r["sale_date"], "isin": r["isin"], "symbol": r["symbol"], "side": "SELL",
                       "qty": r["qty"], "cost": r["sale_value"] or 0, "ref": "Sale in holdings sheet",
                       "broker": r["broker"], "src": "Opening holding"})
    ev.sort(key=lambda e: (e["d"], 0 if e["side"] == "SELL" else 1))
    return ev


def holdings(store, person_key: str, as_on: str, broker: str = "") -> pd.DataFrame:
    """Per ISIN: quantity held, FIFO cost of that quantity, and any shortage (sold more than bought)."""
    lots = defaultdict(deque)          # isin -> deque of [date, qty, cost]
    short = defaultdict(float)
    sym = {}
    for e in _events(store, person_key, as_on, broker):
        k = e["isin"]
        sym.setdefault(k, e["symbol"])
        if e["side"] == "BUY":
            lots[k].append([e["d"], float(e["qty"]), float(e["cost"] or 0)])
            continue
        need = float(e["qty"])
        while need > 1e-9 and lots[k]:
            lot = lots[k][0]
            take = min(need, lot[1])
            part = lot[2] * take / lot[1] if lot[1] else 0.0
            lot[1] -= take
            lot[2] -= part
            need -= take
            if lot[1] <= 1e-9:
                lots[k].popleft()
        if need > 1e-9:
            short[k] += need
    out = []
    for k in set(lots) | set(short):
        q = sum(l[1] for l in lots[k])
        c = sum(l[2] for l in lots[k])
        if q <= 1e-9 and not short[k]:
            continue
        out.append({"key": k, "isin": "" if k.startswith("NAME:") else k, "symbol": sym.get(k, ""),
                    "qty": round(q, 4), "cost": int(round(c)), "shortage": round(short[k], 4),
                    "oldest_lot": min((l[0] for l in lots[k]), default="")})
    return pd.DataFrame(out, columns=["key", "isin", "symbol", "qty", "cost", "shortage", "oldest_lot"])


def _lt(bought: str, sold: str, months: int = 12) -> bool:
    """Long term if held for more than `months` months (listed shares and equity funds: 12)."""
    from datetime import date
    b, s_ = date.fromisoformat(bought), date.fromisoformat(sold)
    y, m = divmod(b.month - 1 + months, 12)
    try:
        limit = b.replace(year=b.year + y, month=m + 1)
    except ValueError:
        limit = b.replace(year=b.year + y, month=m + 1, day=28)
    return s_ > limit


def sales(store, person_key: str, as_on: str = "9999-12-31") -> dict:
    """FIFO cost of every sale: {(note_id, isin): {"cost", "st_cost", "lt_cost", "st_qty", "lt_qty", "short"}}.
    Costs in whole rupees; a partly used lot's cost is split by quantity."""
    lots = defaultdict(deque)
    out = {}
    for e in _events(store, person_key, as_on):
        k = e["isin"]
        if e["side"] == "BUY":
            lots[k].append([e["d"], float(e["qty"]), float(e["cost"] or 0)])
            continue
        need, rec = float(e["qty"]), {"cost": 0.0, "st_cost": 0.0, "lt_cost": 0.0, "st_qty": 0.0, "lt_qty": 0.0,
                                     "short": 0.0}
        while need > 1e-9 and lots[k]:
            lot = lots[k][0]
            take = min(need, lot[1])
            part = lot[2] * take / lot[1] if lot[1] else 0.0
            lot[1] -= take
            lot[2] -= part
            need -= take
            kind = "lt" if _lt(lot[0], e["d"]) else "st"
            rec[f"{kind}_cost"] += part
            rec[f"{kind}_qty"] += take
            rec["cost"] += part
            if lot[1] <= 1e-9:
                lots[k].popleft()
        rec["short"] = need
        key = (e.get("note_id"), k)
        if key in out:                       # the same script twice in one note (should not happen): add up
            for f in rec:
                out[key][f] += rec[f]
        else:
            out[key] = rec
    for rec in out.values():
        for f in ("cost", "st_cost", "lt_cost"):
            rec[f] = int(round(rec[f]))
    return out
