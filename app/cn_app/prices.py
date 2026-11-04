"""Market prices: official closing prices (NSE + BSE bhavcopy, AMFI NAV) and live prices (Yahoo Finance).

Prices are kept per ISIN and date (price_history), so holdings can be valued on any date for
which prices were imported. Only securities the app knows (contract notes, opening holdings,
scrip master) are stored, which keeps the table small.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import date, datetime, timedelta

import pandas as pd

from . import fifo
from .masters import UA, _get, _opener

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    isin TEXT, price_date TEXT, close REAL, prev_close REAL, source TEXT, updated_at TEXT,
    PRIMARY KEY (isin, price_date));
"""
NSE_BHAV = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d}_F_0000.csv.zip"
BSE_BHAV = "https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{d}_F_0000.CSV"
AMFI_NAV = "https://portal.amfiindia.com/spages/NAVAll.txt"
YAHOO_SPARK = "https://query1.finance.yahoo.com/v8/finance/spark?symbols={s}&range=1d&interval=1d"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{s}?range=5d&interval=1d"


def ensure(store):
    store.db.executescript(SCHEMA)


def known_isins(store) -> set[str]:
    s = {r["isin"] for r in store.query("SELECT DISTINCT isin FROM scrips WHERE isin LIKE 'IN%'")}
    s |= {r["isin"] for r in store.query("SELECT isin FROM scrip_master WHERE isin LIKE 'IN%'")}
    try:
        s |= {r["isin"] for r in store.query("SELECT DISTINCT isin FROM opening_lots WHERE isin LIKE 'IN%'")}
    except Exception:  # noqa: BLE001
        pass
    return s


def last_trading_day(d: date | None = None) -> date:
    d = d or date.today()
    if datetime.now().hour < 19 and d == date.today():     # today's bhavcopy is out in the evening
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _save(store, rows: list[tuple], source: str) -> int:
    """rows: (isin, date, close, prev_close)"""
    ensure(store)
    keep = known_isins(store)
    now = datetime.now().isoformat(timespec="seconds")
    n = 0
    with store.db:
        for isin, d, close, prev in rows:
            if isin in keep and close:
                store.db.execute("INSERT OR REPLACE INTO price_history VALUES (?,?,?,?,?,?)",
                                 (isin, d, float(close), float(prev) if prev else None, source, now))
                n += 1
    return n


def _udiff(text: str, exchange: str) -> list[tuple]:
    df = pd.read_csv(io.StringIO(text), dtype=str)
    df = df[df["ISIN"].fillna("").str.match(r"^IN[A-Z0-9]{10}$")]
    return [(r["ISIN"], r["TradDt"][:10], r["ClsPric"], r.get("PrvsClsgPric")) for _, r in df.iterrows()]


def closing_prices(store, d: date, echo=print) -> dict:
    """NSE and BSE bhavcopy for the date (NSE wins where both have the ISIN), plus AMFI NAVs."""
    res = {"date": d.isoformat(), "nse": 0, "bse": 0, "amfi": 0, "errors": []}
    op = _opener()
    ds = d.strftime("%Y%m%d")
    try:
        data = _get(op, BSE_BHAV.format(d=ds), {"Referer": "https://www.bseindia.com/"})
        if b"ISIN" not in data[:2000]:
            raise ValueError("no BSE bhavcopy for this date (holiday, or not yet published)")
        res["bse"] = _save(store, _udiff(data.decode("utf-8", errors="ignore"), "BSE"), "BSE bhavcopy")
        echo(f"BSE: {res['bse']} prices")
    except Exception as exc:  # noqa: BLE001
        res["errors"].append(f"BSE: {exc}")
    try:
        try:
            _get(op, "https://www.nseindia.com/", {}, timeout=30)       # cookies
        except Exception:  # noqa: BLE001
            pass
        data = _get(op, NSE_BHAV.format(d=ds), {"Referer": "https://www.nseindia.com/"})
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            text = z.read(z.namelist()[0]).decode("utf-8", errors="ignore")
        res["nse"] = _save(store, _udiff(text, "NSE"), "NSE bhavcopy")
        echo(f"NSE: {res['nse']} prices")
    except zipfile.BadZipFile:
        res["errors"].append("NSE: no bhavcopy for this date (holiday, or not yet published)")
    except Exception as exc:  # noqa: BLE001
        res["errors"].append(f"NSE: {exc}")
    try:
        res["amfi"] = amfi_navs(store, op)
        echo(f"AMFI: {res['amfi']} NAVs")
    except Exception as exc:  # noqa: BLE001
        res["errors"].append(f"AMFI: {exc}")
    store.log(d.isoformat(), "Closing prices imported",
              f"NSE {res['nse']}, BSE {res['bse']}, AMFI {res['amfi']}" + (f"; {'; '.join(res['errors'])}"
                                                                          if res["errors"] else ""))
    return res


def amfi_navs(store, op=None) -> int:
    text = _get(op or _opener(), AMFI_NAV, {}).decode("utf-8", errors="ignore")
    rows = []
    for line in text.splitlines():
        p = line.split(";")
        if len(p) >= 6 and re.fullmatch(r"\d+", p[0].strip()):
            try:
                nav = float(p[4])
                d = datetime.strptime(p[5].strip(), "%d-%b-%Y").date().isoformat()
            except ValueError:
                continue
            for isin in (p[1].strip(), p[2].strip()):
                if re.fullmatch(r"IN[A-Z0-9]{10}", isin):
                    rows.append((isin, d, nav, None))
    return _save(store, rows, "AMFI NAV")


def _yahoo_json(url: str):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def live_prices(store, isins: list[str] | None = None, echo=print) -> dict:
    """Latest prices from Yahoo Finance for the given ISINs (default: everything held)."""
    ensure(store)
    sym = {r["isin"]: r["symbol"] for r in store.query("SELECT isin, symbol FROM scrip_master WHERE symbol<>''")}
    if isins is None:
        isins = sorted({r["isin"] for r in store.query(
            "SELECT DISTINCT s.isin FROM scrips s WHERE s.isin LIKE 'IN%'")} | known_isins(store) & set(sym))
    todo = {i: re.sub(r"[^A-Z0-9&_-]", "", (sym.get(i) or "").upper()) for i in isins}
    todo = {i: s for i, s in todo.items() if s and not s.isdigit()}
    got, rows, failed = {}, [], []
    items = list(todo.items())
    for k in range(0, len(items), 20):
        chunk = items[k:k + 20]
        try:
            j = _yahoo_json(YAHOO_SPARK.format(s=",".join(f"{s}.NS" for _, s in chunk)))
        except Exception as exc:  # noqa: BLE001
            j = {}
            echo(f"Yahoo: {exc}")
        for isin, s in chunk:
            v = j.get(f"{s}.NS") or {}
            price = v.get("fulldayPrice") or (v.get("close") or [None])[-1]
            if price:
                ts = (v.get("timestamp") or [None])[-1]
                d = datetime.fromtimestamp(ts).date().isoformat() if ts else date.today().isoformat()
                rows.append((isin, d, price, v.get("chartPreviousClose")))
                got[isin] = price
    for isin, s in items:                       # not on NSE: try BSE
        if isin in got:
            continue
        try:
            m = _yahoo_json(YAHOO_CHART.format(s=f"{s}.BO"))["chart"]["result"][0]["meta"]
            if m.get("regularMarketPrice"):
                d = datetime.fromtimestamp(m.get("regularMarketTime") or 0).date().isoformat()
                rows.append((isin, d, m["regularMarketPrice"], m.get("chartPreviousClose")))
                got[isin] = m["regularMarketPrice"]
                continue
        except Exception:  # noqa: BLE001
            pass
        failed.append(s)
    n = _save(store, rows, "Yahoo Finance")
    store.log("Yahoo Finance", "Live prices imported", f"{n} prices" + (f"; not found: {', '.join(failed[:30])}"
                                                                         if failed else ""))
    echo(f"Yahoo Finance: {n} prices, {len(failed)} not found")
    return {"prices": n, "not_found": failed}


def latest(store, as_on: str | None = None) -> pd.DataFrame:
    ensure(store)
    as_on = as_on or "9999-12-31"
    rows = store.query("SELECT p.isin, p.price_date, p.close, p.prev_close, p.source FROM price_history p "
                       "JOIN (SELECT isin, MAX(price_date) d FROM price_history WHERE price_date<=? GROUP BY isin) x "
                       "ON x.isin=p.isin AND x.d=p.price_date", (as_on,))
    return pd.DataFrame(rows, columns=["isin", "price_date", "close", "prev_close", "source"])


def valuation(store, person_key: str, as_on: str) -> pd.DataFrame:
    """Holdings on the date (FIFO cost) with market value and unrealised gain / loss, script-wise.
    person_key '' = every person (PAN from contract notes or holdings, or a name without PAN)."""
    from . import persons
    cols = ["ISIN", "Script", "Name of Company", "Asset Class", "Industry", "Quantity", "Avg Cost / Unit",
            "Cost (Rs)", "Market Price", "Price Date", "Market Value (Rs)", "Gain / Loss (Rs)", "Gain / Loss %",
            "Day Change %", "Weight %", "Holding Since", "Price Source"]
    keys = [person_key] if person_key else [p["key"] for p in persons.all_people(store)]
    frames = [fifo.holdings(store, k, as_on) for k in keys]
    frames = [f for f in frames if len(f)]
    if not frames:
        return pd.DataFrame(columns=cols)
    h = pd.concat(frames)
    h = h[h["qty"] > 1e-9].groupby("key", as_index=False).agg(isin=("isin", "first"), symbol=("symbol", "first"),
                                                              qty=("qty", "sum"), cost=("cost", "sum"),
                                                              since=("oldest_lot", "min"))
    px = latest(store, as_on).set_index("isin")
    info = {r["isin"]: r for r in store.query(
        "SELECT m.isin, m.symbol, COALESCE(NULLIF(m.company_name,''), (SELECT f.name FROM ref_securities f "
        "WHERE f.isin=m.isin), '') company_name, COALESCE(NULLIF(m.asset_class,''), (SELECT f.asset_class FROM "
        "ref_securities f WHERE f.isin=m.isin), '') asset_class, COALESCE(NULLIF(m.industry,''), (SELECT f.industry "
        "FROM ref_securities f WHERE f.isin=m.isin), '') industry FROM scrip_master m")}
    out = []
    for _, r in h.iterrows():
        m = info.get(r["isin"]) or {}
        p = px.loc[r["isin"]] if r["isin"] and r["isin"] in px.index else None
        price = float(p["close"]) if p is not None else None
        mv = int(round(price * r["qty"])) if price else None
        gain = mv - int(r["cost"]) if mv is not None else None
        out.append({"ISIN": r["isin"], "Script": (m["symbol"] if m else "") or r["symbol"],
                    "Name of Company": m["company_name"] if m else "", "Asset Class": m["asset_class"] if m else "",
                    "Industry": m["industry"] if m else "", "Quantity": float(r["qty"]),
                    "Avg Cost / Unit": round(r["cost"] / r["qty"], 2) if r["qty"] else None,
                    "Cost (Rs)": int(r["cost"]), "Market Price": price,
                    "Price Date": p["price_date"] if p is not None else "", "Market Value (Rs)": mv,
                    "Gain / Loss (Rs)": gain,
                    "Gain / Loss %": round(gain * 100 / r["cost"], 2) if gain is not None and r["cost"] else None,
                    "Day Change %": round((price / float(p["prev_close"]) - 1) * 100, 2)
                    if p is not None and p["prev_close"] and price else None,
                    "Weight %": None, "Holding Since": r["since"] or "", "Price Source": p["source"] if p is not None else "no price yet"})
    df = pd.DataFrame(out, columns=cols)
    base = df["Market Value (Rs)"].fillna(df["Cost (Rs)"])
    df["Weight %"] = (base * 100 / base.sum()).round(2) if base.sum() else None
    return df.sort_values("Cost (Rs)", ascending=False).reset_index(drop=True)


def prices_stale(store, days: int = 1) -> bool:
    ensure(store)
    r = store.query("SELECT MAX(updated_at) u FROM price_history")
    if not r or not r[0]["u"]:
        return True
    return (datetime.now() - datetime.fromisoformat(r[0]["u"])).days >= days or \
        datetime.fromisoformat(r[0]["u"]).date() < date.today()
