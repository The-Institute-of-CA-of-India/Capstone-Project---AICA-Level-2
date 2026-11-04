"""Opening holdings: read a holdings sheet (our template or the user's own layout).

* Columns are recognised by many names (Name / Holder Name, Qty / Quantity,
  Purchase Value Rs. / Total Cost, Script / Scrip, ...). Formula cells are read
  as the values Excel last calculated.
* Names without PAN are kept as persons; PAN is filled automatically when the
  name matches a known client, or later on the Persons page.
* ISIN missing: looked up from the script name (Scrip Master and reference lists).
  Rows still without ISIN are kept with status "ISIN pending" and resolved later.
* A row that is the same purchase as a contract-note purchase (same PAN, ISIN,
  date and quantity) is skipped, so nothing is counted twice.
* Rows with a sale date are stored as "Sold" (kept for history and gains).
* Re-importing the same sheet never creates duplicates.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import persons, reference
from .utils import isin_check_digit_ok

SCHEMA = """
CREATE TABLE IF NOT EXISTS opening_lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person TEXT NOT NULL, pan TEXT, broker TEXT, purchase_date TEXT NOT NULL,
    isin TEXT, script TEXT, company_name TEXT, script_key TEXT NOT NULL,
    qty REAL NOT NULL, total_cost INTEGER NOT NULL, asset_type TEXT, mode TEXT, fmv_2018 REAL,
    sale_date TEXT, sale_value REAL, status TEXT, isin_how TEXT, remarks TEXT,
    source_file TEXT, source_row INTEGER, imported_at TEXT,
    UNIQUE (person, script_key, purchase_date, qty, total_cost, broker));
"""

ALIASES = {
    "person": ["holder name", "name", "holder", "client", "person", "account", "client name"],
    "pan": ["pan", "pan no", "pan no."],
    "broker": ["intermediary / broker", "broker", "intermediary", "dp"],
    "purchase_date": ["date of purchase", "purchase date", "buy date", "date of acquisition", "date"],
    "isin": ["isin", "isin no", "isin code", "isin number"],
    "script": ["script", "scrip", "symbol", "script name", "scrip name", "security", "security name"],
    "company_name": ["name of company", "company name", "company"],
    "qty": ["quantity", "qty", "no of shares", "no. of shares", "units", "shares"],
    "total_cost": ["total cost (rs)", "purchase value rs.", "purchase value rs", "purchase value", "total cost",
                   "cost", "amount", "purchase amount"],
    "rate": ["purchase rate rs.", "purchase rate", "rate", "buy rate", "cost per share"],
    "mode": ["mode of acquisition", "mode", "acquisition"],
    "asset_type": ["type", "asset type", "asset class"],
    "fmv_2018": ["fmv on 31-01-2018 (rs per unit)", "rate as on 01 feb 2018", "rate as on 31 jan 2018", "fmv",
                 "fmv 31-01-2018"],
    "sale_date": ["sale date", "date of sale"],
    "sale_value": ["sales value rs.", "sale value rs.", "sales value", "sale value", "sale amount"],
    "sale_rate": ["sale rate", "sale rate rs."],
    "remarks": ["remarks", "remark", "notes"],
}


def _n(s) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def ensure(store):
    cols = {r["name"] for r in store.query("PRAGMA table_info(opening_lots)")}
    if cols and "person" not in cols:             # table from version 1.0: migrate
        store.db.execute("ALTER TABLE opening_lots RENAME TO opening_lots_v1")
        store.db.commit()
    store.db.executescript(SCHEMA)
    if cols and "person" not in cols:
        for r in store.query("SELECT * FROM opening_lots_v1"):
            store.db.execute(
                "INSERT OR IGNORE INTO opening_lots(person, pan, broker, purchase_date, isin, script, company_name, "
                "script_key, qty, total_cost, mode, fmv_2018, status, remarks, source_file, imported_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["holder"] or r["pan"], r["pan"], r["broker"], r["purchase_date"], r["isin"], r["symbol"],
                 r["company_name"], r["isin"], r["qty"], r["total_cost"], r["mode"], r["fmv_2018"], "Holding",
                 r["remarks"], r["source_file"], r["imported_at"]))
        store.db.execute("DROP TABLE opening_lots_v1")
        store.db.commit()
    persons.ensure(store)
    reference.ensure(store)


def _date(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "NaT", "nan"):
        return None
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError(f"date not understood: '{s}'")


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "nan") or s.startswith("="):
        return None
    return float(s)


def _text(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() in ("nan", "nat", "none") else s


def _read(path: Path):
    raw = pd.read_excel(path, header=None, dtype=object)
    best, hdr = 0, None
    for i, row in raw.head(30).iterrows():
        names = {_n(v) for v in row.values if isinstance(v, str)}
        score = sum(any(a in names for a in al) for al in ALIASES.values())
        if score > best:
            best, hdr = score, i
    if hdr is None or best < 3:
        raise ValueError("could not find the header row (need columns such as Name, Script, Date of Purchase, Qty)")
    headers = [_n(c) for c in raw.iloc[hdr]]
    colmap = {}
    for field, al in ALIASES.items():
        for a in al:
            if a in headers and headers.index(a) not in colmap.values():
                colmap[field] = headers.index(a)
                break
    missing = [f for f in ("person", "purchase_date", "qty") if f not in colmap]
    if "script" not in colmap and "isin" not in colmap:
        missing.append("script or ISIN")
    if "total_cost" not in colmap and "rate" not in colmap:
        missing.append("purchase value or rate")
    if missing:
        raise ValueError("missing column(s): " + ", ".join(missing))
    return raw.iloc[hdr + 1:], colmap, hdr


def _learned(store, script: str, sheet_map: dict) -> str:
    """ISIN for a script name already known from this sheet or earlier holding imports."""
    k = reference.norm(script)
    if not k:
        return ""
    if k in sheet_map:
        return sheet_map[k]
    hits = {r["isin"] for r in store.query("SELECT isin, script FROM opening_lots WHERE isin IS NOT NULL AND isin<>''")
            if reference.norm(r["script"]) == k}
    return hits.pop() if len(hits) == 1 else ""


def import_opening(path: Path, store) -> dict:
    ensure(store)
    body, colmap, hdr = _read(Path(path))
    sheet_map: dict = {}
    if "isin" in colmap and "script" in colmap:          # learn script -> ISIN from rows that have both
        seen: dict = {}
        for _, r in body.iterrows():
            sc, isn = reference.norm(_text(r.iloc[colmap["script"]])), _text(r.iloc[colmap["isin"]]).upper()
            if sc and isin_check_digit_ok(isn):
                seen.setdefault(sc, set()).add(isn)
        sheet_map = {k: v.pop() for k, v in seen.items() if len(v) == 1}
    res = {"added": 0, "duplicates": 0, "in_contract_notes": 0, "isin_pending": 0, "sold": 0,
           "errors": [], "skipped": []}
    now = datetime.now().isoformat(timespec="seconds")
    for offset, (_, r) in enumerate(body.iterrows()):
        rowno = hdr + 2 + offset
        get = {f: r.iloc[i] for f, i in colmap.items()}
        if all(_text(v) == "" for v in get.values()):
            continue
        if "sample row" in _text(get.get("remarks")).lower() or _text(get.get("person")).startswith("As per"):
            continue
        try:
            person = _text(get.get("person"))
            pan_given = _text(get.get("pan")).upper()
            if not person and pan_given:
                known = store.query("SELECT name FROM clients WHERE pan=?", (pan_given,))
                person = known[0]["name"] if known else pan_given
            if not person:
                raise ValueError("name / holder is empty (and no PAN to find it)")
            pdate = _date(get.get("purchase_date"))
            if not pdate:
                raise ValueError("date of purchase is empty")
            qty = _num(get.get("qty"))
            if not qty or qty <= 0:
                raise ValueError("quantity is empty or zero")
            cost = _num(get.get("total_cost"))
            if cost is None and _num(get.get("rate")) is not None:
                cost = _num(get.get("rate")) * qty
            if cost is None:
                raise ValueError("purchase value is empty")
            cost = int(round(cost))

            pan = _text(get.get("pan")).upper()
            if pan:
                if not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", pan):
                    raise ValueError(f"PAN '{pan}' is not valid")
                persons.set_pan(store, person, pan)
            else:
                pan = persons.pan_for(store, person)

            script = _text(get.get("script"))
            isin = _text(get.get("isin")).upper()
            how = "given in sheet" if isin else ""
            if isin and not isin_check_digit_ok(isin):
                raise ValueError(f"ISIN '{isin}' is not valid")
            if not isin and script:
                isin = _learned(store, script, sheet_map)
                how = "same script elsewhere in holdings" if isin else ""
            if not isin:
                isin, how = reference.resolve(store, script or _text(get.get("company_name")))
                isin = isin or ""
            company = _text(get.get("company_name"))
            if isin and not company:
                m = store.query("SELECT company_name FROM scrip_master WHERE isin=?", (isin,)) or \
                    store.query("SELECT name AS company_name FROM ref_securities WHERE isin=?", (isin,))
                company = (m[0]["company_name"] or "") if m else ""

            # same purchase already in contract notes?
            if pan and isin:
                hit = store.query("SELECT n.cn_no FROM scrips s JOIN notes n ON n.id=s.note_id WHERE n.pan=? "
                                  "AND s.isin=? AND n.trade_date=? AND s.side='BUY' AND ABS(s.qty-?)<0.0001",
                                  (pan, isin, pdate, qty))
                if hit:
                    res["in_contract_notes"] += 1
                    res["skipped"].append(f"Row {rowno}: {person} {script or isin} {pdate} qty {qty:g} is already "
                                          f"in contract note {hit[0]['cn_no']}; not added again")
                    continue

            sale_date = _date(get.get("sale_date"))
            sale_value = _num(get.get("sale_value"))
            if sale_value is None and _num(get.get("sale_rate")) is not None:
                sale_value = _num(get.get("sale_rate")) * qty
            status = "Sold" if sale_date else ("ISIN pending" if not isin else "Holding")
            fmv = _num(get.get("fmv_2018"))
            skey = isin or reference.norm(script)
            cur = store.db.execute(
                "INSERT OR IGNORE INTO opening_lots(person, pan, broker, purchase_date, isin, script, company_name, "
                "script_key, qty, total_cost, asset_type, mode, fmv_2018, sale_date, sale_value, status, isin_how, "
                "remarks, source_file, source_row, imported_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (person, pan or None, _text(get.get("broker")), pdate, isin or None, script, company, skey, qty, cost,
                 _text(get.get("asset_type")), _text(get.get("mode")) or "Purchase", fmv, sale_date, sale_value,
                 status, how or None, _text(get.get("remarks")), Path(path).name, rowno, now))
            if cur.rowcount:
                res["added"] += 1
                res["isin_pending"] += status == "ISIN pending"
                res["sold"] += status == "Sold"
                if isin:
                    store.db.execute("INSERT OR IGNORE INTO scrip_master(isin, symbol, company_name, source, updated_at)"
                                     " VALUES (?,?,?,?,?)", (isin, script, company, "Opening holdings", now))
            else:
                res["duplicates"] += 1
        except Exception as exc:  # noqa: BLE001 - every bad row is reported to the user
            res["errors"].append(f"Row {rowno}: {exc}")
    store.db.commit()
    return res


def resolve_pending(store) -> int:
    """Try again to find ISINs for 'ISIN pending' lots (after loading reference lists)."""
    ensure(store)
    n = 0
    for lot in store.query("SELECT id, script, company_name, pan, purchase_date, qty FROM opening_lots "
                           "WHERE isin IS NULL OR isin=''"):
        isin, how = _learned(store, lot["script"], {}), "same script elsewhere in holdings"
        if not isin:
            isin, how = reference.resolve(store, lot["script"] or lot["company_name"])
        if isin:
            set_isin(store, lot["id"], isin, how)
            n += 1
    return n


def set_isin(store, lot_id: int, isin: str, how: str = "entered") -> None:
    isin = (isin or "").strip().upper()
    if isin and not isin_check_digit_ok(isin):
        raise ValueError(f"ISIN '{isin}' is not valid")
    lot = store.query("SELECT * FROM opening_lots WHERE id=?", (lot_id,))[0]
    status = "Sold" if lot["sale_date"] else ("Holding" if isin else "ISIN pending")
    name = store.query("SELECT company_name FROM scrip_master WHERE isin=?", (isin,)) or \
        store.query("SELECT name AS company_name FROM ref_securities WHERE isin=?", (isin,))
    store.db.execute("UPDATE opening_lots SET isin=?, script_key=?, status=?, isin_how=?, "
                     "company_name=COALESCE(NULLIF(company_name,''), ?) WHERE id=?",
                     (isin or None, isin or reference.norm(lot["script"]), status, how,
                      (name[0]["company_name"] if name else None), lot_id))
    if isin:
        store.db.execute("INSERT OR IGNORE INTO scrip_master(isin, symbol, company_name, source, updated_at) "
                         "VALUES (?,?,?,?,?)", (isin, lot["script"], lot["company_name"], "Opening holdings",
                                                datetime.now().isoformat(timespec="seconds")))
    store.db.commit()


def lots(store, person_key: str = "") -> pd.DataFrame:
    """Opening lots with a live check against contract notes."""
    ensure(store)
    where, args = "", ()
    if person_key.startswith("NAME:"):
        where, args = "WHERE UPPER(o.person)=?", (person_key[5:],)
    elif person_key:
        where, args = "WHERE o.pan=?", (person_key,)
    rows = store.query(
        "SELECT o.id AS ID, o.person AS 'Name', o.pan AS PAN, o.broker AS Broker, o.purchase_date AS 'Date of Purchase', "
        "o.script AS Script, o.isin AS ISIN, COALESCE(NULLIF(o.company_name,''), "
        "(SELECT m.company_name FROM scrip_master m WHERE m.isin=o.isin)) AS 'Name of Company', o.qty AS Quantity, "
        "o.total_cost AS 'Total Cost (Rs)', o.status AS Status, o.sale_date AS 'Sale Date', "
        "o.sale_value AS 'Sale Value (Rs)', o.asset_type AS Type, o.isin_how AS 'ISIN found by', "
        "(SELECT n.cn_no FROM scrips s JOIN notes n ON n.id=s.note_id WHERE n.pan=o.pan AND s.isin=o.isin "
        " AND n.trade_date=o.purchase_date AND s.side='BUY' AND ABS(s.qty-o.qty)<0.0001 LIMIT 1) AS 'Also in contract note', "
        "o.source_file AS 'Source File', o.source_row AS 'Row' "
        f"FROM opening_lots o {where} ORDER BY o.person, o.purchase_date", args)
    cols = ["ID", "Name", "PAN", "Broker", "Date of Purchase", "Script", "ISIN", "Name of Company", "Quantity",
            "Total Cost (Rs)", "Status", "Sale Date", "Sale Value (Rs)", "Type", "ISIN found by",
            "Also in contract note", "Source File", "Row"]
    return pd.DataFrame(rows, columns=cols)


def fill_details(store) -> int:
    """Fill empty script, company and holder details of holdings from the masters."""
    ensure(store)
    n = 0
    for lot in store.query("SELECT o.id, o.script, o.company_name, o.person, o.pan, o.isin, "
                           "m.symbol ms, m.company_name mc, r.symbol rs, r.name rn "
                           "FROM opening_lots o LEFT JOIN scrip_master m ON m.isin=o.isin "
                           "LEFT JOIN ref_securities r ON r.isin=o.isin WHERE o.isin IS NOT NULL"):
        upd = {}
        if not lot["script"] and (lot["ms"] or lot["rs"]):
            upd["script"] = lot["ms"] if lot["ms"] and " " not in lot["ms"] else lot["rs"] or lot["ms"]
        if not lot["company_name"] and (lot["mc"] or lot["rn"]):
            upd["company_name"] = lot["mc"] or lot["rn"]
        if upd:
            store.db.execute(f"UPDATE opening_lots SET {', '.join(k + '=?' for k in upd)} WHERE id=?",
                             (*upd.values(), lot["id"]))
            n += 1
    for lot in store.query("SELECT o.id, c.name FROM opening_lots o JOIN clients c ON c.pan=o.pan "
                           "WHERE o.person IS NULL OR o.person=''"):
        store.db.execute("UPDATE opening_lots SET person=? WHERE id=?", (lot["name"], lot["id"]))
        n += 1
    store.db.commit()
    return n


LOT_EDIT = {"Name": "person", "Broker": "broker", "Date of Purchase": "purchase_date", "Script": "script",
            "Name of Company": "company_name", "Quantity": "qty", "Total Cost (Rs)": "total_cost",
            "Sale Date": "sale_date", "Sale Value (Rs)": "sale_value"}


def update_lot(store, lot_id: int, column: str, value) -> None:
    if column == "ISIN":
        set_isin(store, lot_id, value or "", "entered")
        store.log(f"Holding {lot_id}", "Edited", f"ISIN -> {value}")
        return
    col = LOT_EDIT.get(column)
    if not col:
        raise ValueError(f"'{column}' cannot be edited")
    if col in ("purchase_date", "sale_date"):
        value = _date(value) if value else None
        if col == "purchase_date" and not value:
            raise ValueError("date of purchase cannot be empty")
    elif col in ("qty", "total_cost", "sale_value"):
        value = _num(value)
        if col != "sale_value" and (value is None or value <= 0):
            raise ValueError(f"{column} must be more than zero")
        if col == "total_cost":
            value = int(round(value))
    else:
        value = _text(value)
    store.db.execute(f"UPDATE opening_lots SET {col}=? WHERE id=?", (value, lot_id))
    if col == "sale_date":
        store.db.execute("UPDATE opening_lots SET status=CASE WHEN sale_date IS NOT NULL THEN 'Sold' "
                         "WHEN isin IS NULL OR isin='' THEN 'ISIN pending' ELSE 'Holding' END WHERE id=?", (lot_id,))
    if col == "person":
        store.db.execute("UPDATE opening_lots SET pan=? WHERE id=?", (persons.pan_for(store, value) or None, lot_id))
    store.db.commit()
    store.log(f"Holding {lot_id}", "Edited", f"{column} -> {value}")


def delete_lots(store, ids) -> int:
    for i in ids:
        r = store.query("SELECT person, script, purchase_date, qty FROM opening_lots WHERE id=?", (i,))
        store.db.execute("DELETE FROM opening_lots WHERE id=?", (i,))
        if r:
            store.log(f"Holding {i}", "Deleted", f"{r[0]['person']} {r[0]['script']} {r[0]['purchase_date']} "
                                                 f"qty {r[0]['qty']:g}")
    store.db.commit()
    return len(ids)


def log_result(store, filename: str, res: dict) -> None:
    """Write every issue of a holdings import to the Import Log."""
    store.log(filename, "Holdings imported",
              f"{res['added']} added, {res['duplicates']} already imported, {res['in_contract_notes']} in contract "
              f"notes, {res['isin_pending']} ISIN pending, {len(res['errors'])} error(s)")
    for e in res["errors"]:
        store.log(filename, "Holdings row error", e)
    for e in res["skipped"]:
        store.log(filename, "Holdings row skipped", e)
