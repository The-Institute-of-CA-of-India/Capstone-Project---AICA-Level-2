"""Grandfathering values for capital gains (kept for Phase 2).

* Fair market value on 31-Jan-2018 (section 112A / 55(2)(ac)): highest price on BSE / NSE that day
  (or the last traded day before it) for listed equity shares and equity-oriented fund units
  quoted on an exchange, and the NAV for unlisted equity-oriented fund units.
* Price on 01-Apr-2001 (and 01-Apr-1981): for assets bought before 2001, FMV on 1-4-2001 may be
  taken as cost (section 55(2)(b)).

The sheet uses short exchange names ("ZYDUS WELL", "3MINDIA"), so each held script is matched
by name; a match can be chosen by hand and is remembered.
"""
from __future__ import annotations


from datetime import datetime
from pathlib import Path

import pandas as pd

from . import mdstore, reference

SCHEMA = """
CREATE TABLE IF NOT EXISTS fmv_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, name TEXT, fund TEXT, exchange TEXT,
    value_date TEXT, price REAL, price_1981 REAL, norm TEXT, source TEXT, imported_at TEXT);
CREATE INDEX IF NOT EXISTS ix_fmv_norm ON fmv_values(norm);
CREATE TABLE IF NOT EXISTS fmv_map (isin TEXT PRIMARY KEY, fmv_id INTEGER, how TEXT);
"""
KINDS = {"EQ2018": "Equity share: highest price on 31-Jan-2018",
         "EOF2018": "Equity-oriented fund quoted on exchange: highest price on 31-Jan-2018",
         "NAV2018": "Equity-oriented fund NAV on 31-Jan-2018",
         "P2001": "Price on 01-Apr-2001 (and 01-Apr-1981)",
         "GOLD2001": "Gold / silver on 01-Apr-2001"}


def ensure(store):
    store.db.executescript(SCHEMA)


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _date(v) -> str:
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.strftime("%Y-%m-%d")
    try:
        return pd.to_datetime(str(v), dayfirst=True).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def parse(path: Path) -> list[dict]:
    x = pd.ExcelFile(path)
    rows = []
    for sh in x.sheet_names:
        df = x.parse(sh, header=None, dtype=object)
        title = " ".join(str(v) for v in df.head(3).values.ravel() if isinstance(v, str)).upper()
        low = sh.lower()
        if "net asset value" in low or "NET ASSET VALUE" in title:
            for _, r in df.iterrows():
                nav = _num(r.iloc[2])
                if nav is not None and isinstance(r.iloc[1], str):
                    rows.append({"kind": "NAV2018", "name": r.iloc[1].strip(), "fund": str(r.iloc[0] or "").strip(),
                                 "exchange": "", "value_date": "2018-01-31", "price": nav, "price_1981": None})
        elif "1981" in low or "2001" in low:
            if "gold" in low or "silver" in low:
                for _, r in df.iterrows():
                    p01 = _num(r.iloc[2])
                    if p01 is not None and isinstance(r.iloc[0], str):
                        rows.append({"kind": "GOLD2001", "name": r.iloc[0].strip(), "fund": "", "exchange": "",
                                     "value_date": "2001-04-01", "price": p01, "price_1981": _num(r.iloc[1])})
                continue
            for _, r in df.iterrows():
                p01 = _num(r.iloc[3])
                if p01 is not None and isinstance(r.iloc[0], str):
                    rows.append({"kind": "P2001", "name": r.iloc[0].strip(), "fund": "",
                                 "exchange": str(r.iloc[1] or "").strip(), "value_date": "2001-04-01", "price": p01,
                                 "price_1981": _num(r.iloc[2])})
        elif "quotation" in low or "MARKET QUOTATION" in title:
            kind = "EOF2018" if ("eof" in low or "MUTUAL" in title) else "EQ2018"
            for _, r in df.iterrows():
                p = _num(r.iloc[1])
                if p is not None and r.iloc[0] is not None and str(r.iloc[0]).strip():
                    rows.append({"kind": kind, "name": str(r.iloc[0]).strip(), "fund": "",
                                 "exchange": str(r.iloc[3] or "").strip(), "value_date": _date(r.iloc[2]) or "2018-01-31",
                                 "price": p, "price_1981": None})
    if not rows:
        raise ValueError("no grandfathering values found: expected sheets like 'Market Quotation_Equity', "
                         "'Net Asset Value_EOF' and 'Share price on 1-4-1981 or 2001'")
    return rows


def import_file(store, path: Path, master_folder: Path | None = None) -> dict:
    ensure(store)
    rows = parse(path)
    now = datetime.now().isoformat(timespec="seconds")
    with store.db:
        store.db.execute("DELETE FROM fmv_values")         # a new sheet replaces the old one
        store.db.executemany(
            "INSERT INTO fmv_values(kind, name, fund, exchange, value_date, price, price_1981, norm, source, "
            "imported_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(r["kind"], r["name"], r["fund"], r["exchange"], r["value_date"], r["price"], r["price_1981"],
              reference.norm(r["name"]), Path(path).name, now) for r in rows])
    if master_folder:
        df = pd.DataFrame(rows).rename(columns={"kind": "Kind", "name": "Name", "fund": "Fund house",
                                                "exchange": "Exchange", "value_date": "Value date",
                                                "price": "Price (Rs)", "price_1981": "Price 01-Apr-1981"})
        mdstore.write_table(Path(master_folder) / "Grandfathering_FMV.md", "Grandfathering values (FMV)",
                            Path(path).name, df)
    counts = pd.Series([r["kind"] for r in rows]).value_counts().to_dict()
    store.log(Path(path).name, "Grandfathering FMV imported",
              ", ".join(f"{KINDS[k].split(':')[0]} {v}" for k, v in counts.items()))
    return counts


def counts(store) -> dict:
    ensure(store)
    return {r["kind"]: r["n"] for r in store.query("SELECT kind, COUNT(*) n FROM fmv_values GROUP BY kind")}


def _tokens_match(short: str, full: str) -> bool:
    a, b = short.split(), full.split()
    return bool(a) and len(a) <= len(b) and all(y.startswith(x) for x, y in zip(a, b))


def match(store, isin: str, symbol: str, company: str, kinds=("EQ2018", "EOF2018", "NAV2018"),
          rows=None) -> dict | None:
    """FMV row for a script: a saved choice first, then symbol / name matching (unique matches only)."""
    ensure(store)
    m = store.query("SELECT v.* , fm.how FROM fmv_map fm JOIN fmv_values v ON v.id=fm.fmv_id WHERE fm.isin=?", (isin,))
    if m:
        return dict(m[0])
    if rows is None:
        ph = ",".join("?" * len(kinds))
        rows = store.query(f"SELECT * FROM fmv_values WHERE kind IN ({ph})", tuple(kinds))
    ns, nc = reference.norm(symbol).replace(" ", ""), reference.norm(company)
    for how, test in (("symbol", lambda r: r["norm"].replace(" ", "") == ns and ns),
                      ("company name", lambda r: r["norm"] == nc and nc),
                      ("short name", lambda r: nc and _tokens_match(r["norm"], nc))):
        hits = [r for r in rows if test(r)]
        if len({(h["name"], h["price"]) for h in hits}) == 1:
            return {**dict(hits[0]), "how": how}
    return None


def set_map(store, isin: str, fmv_id: int | None):
    ensure(store)
    if fmv_id:
        store.db.execute("INSERT OR REPLACE INTO fmv_map VALUES (?,?,?)", (isin, int(fmv_id), "chosen by you"))
    else:
        store.db.execute("DELETE FROM fmv_map WHERE isin=?", (isin,))
    store.db.commit()


def held_scripts(store) -> pd.DataFrame:
    """Every script in the app with its matched FMV on 31-Jan-2018."""
    ensure(store)
    rows = store.query(
        "SELECT x.isin, MAX(x.symbol) symbol, COALESCE(NULLIF(m.company_name,''), "
        "(SELECT f.name FROM ref_securities f WHERE f.isin=x.isin), '') company FROM ("
        " SELECT s.isin, s.symbol FROM scrips s UNION ALL SELECT o.isin, o.script FROM opening_lots o) x "
        "LEFT JOIN scrip_master m ON m.isin=x.isin WHERE x.isin LIKE 'IN%' GROUP BY x.isin ORDER BY 2")
    out = []
    fmv_rows = store.query("SELECT * FROM fmv_values WHERE kind IN ('EQ2018','EOF2018','NAV2018')")
    for r in rows:
        f = match(store, r["isin"], r["symbol"] or "", r["company"] or "", rows=fmv_rows)
        out.append({"ISIN": r["isin"], "Script": r["symbol"], "Name of Company": r["company"],
                    "FMV 31-Jan-2018 (Rs)": f["price"] if f else None, "Name in sheet": f["name"] if f else "",
                    "Quote date": f["value_date"] if f else "", "Exchange": f["exchange"] if f else "",
                    "Matched by": f["how"] if f else "not found", "_fmv_id": f["id"] if f else None})
    return pd.DataFrame(out, columns=["ISIN", "Script", "Name of Company", "FMV 31-Jan-2018 (Rs)", "Name in sheet",
                                      "Quote date", "Exchange", "Matched by", "_fmv_id"])


def search(store, text: str, limit=30) -> list[dict]:
    ensure(store)
    q = f"%{reference.norm(text)}%"
    return [dict(r) for r in store.query(
        "SELECT id, kind, name, exchange, value_date, price FROM fmv_values WHERE kind IN ('EQ2018','EOF2018','NAV2018') "
        "AND norm LIKE ? ORDER BY name LIMIT ?", (q, limit))]



