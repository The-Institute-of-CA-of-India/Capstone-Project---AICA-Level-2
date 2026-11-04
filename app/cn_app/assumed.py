"""Assumed past purchases (for developing and testing the app).

Project rule: a script sold that was neither bought in a contract note nor shown in the
opening holdings was bought in the past. For each such sale the app adds an opening lot
marked "Assumed" so FIFO cost and gains can be worked out:
  quantity   = the quantity short at that sale (so the lot is at least the sale)
  date       = 3 years before the sale (long term; earlier than 31-Jan-2018 for older sales,
               so grandfathering is exercised too)
  total cost = 80% of the net sale proceeds of that quantity (a modest assumed gain)
Assumed lots are clearly marked and can be removed in one click, or replaced by uploading
the real opening holdings.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import date, datetime

from . import fifo, opening

MARK = "Assumed by app"
COST_SHARE = 0.80
YEARS_BEFORE = 3


def shortfalls(store, pan: str) -> list[dict]:
    """Each sale that finds too few shares in hand: date, isin, symbol, qty short, proceeds per unit."""
    lots = defaultdict(deque)
    out = []
    for e in fifo._events(store, pan, "9999-12-31"):
        k = e["isin"]
        if e["side"] == "BUY":
            lots[k].append([float(e["qty"])])
            continue
        need = float(e["qty"])
        while need > 1e-9 and lots[k]:
            take = min(need, lots[k][0][0])
            lots[k][0][0] -= take
            need -= take
            if lots[k][0][0] <= 1e-9:
                lots[k].popleft()
        if need > 1e-9:
            per_unit = float(e["cost"] or 0) / float(e["qty"]) if e["qty"] else 0.0
            out.append({"date": e["d"], "isin": k, "symbol": e["symbol"], "qty": need, "per_unit": per_unit,
                        "broker": e.get("broker") or "", "ref": e.get("ref") or ""})
    return out


def _back(d: str, years: int) -> str:
    x = date.fromisoformat(d)
    try:
        return x.replace(year=x.year - years).isoformat()
    except ValueError:                       # 29 Feb
        return x.replace(year=x.year - years, day=28).isoformat()


def add_for(store, pan: str) -> int:
    opening.ensure(store)
    name = store.query("SELECT MAX(client_name) n FROM notes WHERE pan=?", (pan,))
    person = (name[0]["n"] if name and name[0]["n"] else pan)
    comp = {r["isin"]: r["company_name"] for r in store.query("SELECT isin, company_name FROM scrip_master")}
    now = datetime.now().isoformat(timespec="seconds")
    n = 0
    for s in shortfalls(store, pan):
        isin = "" if s["isin"].startswith("NAME:") else s["isin"]
        cost = int(round(s["qty"] * s["per_unit"] * COST_SHARE))
        cur = store.db.execute(
            "INSERT OR IGNORE INTO opening_lots(person, pan, broker, purchase_date, isin, script, company_name, "
            "script_key, qty, total_cost, asset_type, mode, fmv_2018, sale_date, sale_value, status, isin_how, "
            "remarks, source_file, source_row, imported_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (person, pan, s["broker"], _back(s["date"], YEARS_BEFORE), isin or None, s["symbol"], comp.get(isin, ""),
             isin or s["isin"], s["qty"], cost, "Equity", "Assumed", None, None, None, "Assumed", None,
             f"Assumed past purchase for the sale on {s['date']} (contract note {s['ref']}): "
             f"{int(COST_SHARE * 100)}% of sale proceeds, dated {YEARS_BEFORE} years earlier",
             MARK, None, now))
        n += cur.rowcount
    store.db.commit()
    if n:
        store.log(person, "Assumed purchases added", f"{n} lot(s) for sales without a purchase")
    return n


def add_all(store) -> int:
    return sum(add_for(store, r["pan"]) for r in
               store.query("SELECT DISTINCT pan FROM notes WHERE pan IS NOT NULL AND pan<>''"))


def remove(store, pan: str = "") -> int:
    opening.ensure(store)
    q, args = "DELETE FROM opening_lots WHERE source_file=?", [MARK]
    if pan:
        q += " AND pan=?"
        args.append(pan)
    n = store.db.execute(q, tuple(args)).rowcount
    store.db.commit()
    if n:
        store.log(pan or "All persons", "Assumed purchases removed", f"{n} lot(s)")
    return n


def count(store, pan: str = "") -> int:
    opening.ensure(store)
    q, args = "SELECT COUNT(*) c FROM opening_lots WHERE source_file=?", [MARK]
    if pan:
        q += " AND pan=?"
        args.append(pan)
    return store.query(q, tuple(args))[0]["c"]


def enabled(store) -> bool:
    store.db.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)")
    r = store.db.execute("SELECT value FROM app_settings WHERE key='assumed_purchases'").fetchone()
    return (r["value"] if r else "1") == "1"


def set_enabled(store, on: bool):
    store.db.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)")
    store.db.execute("INSERT OR REPLACE INTO app_settings VALUES ('assumed_purchases', ?)", ("1" if on else "0",))
    store.db.commit()


def refresh(store) -> int:
    """Rebuild assumed lots after any import, so real purchases / holdings always take their place."""
    opening.ensure(store)
    store.db.execute("DELETE FROM opening_lots WHERE source_file=?", (MARK,))
    store.db.commit()
    return add_all(store) if enabled(store) else 0
