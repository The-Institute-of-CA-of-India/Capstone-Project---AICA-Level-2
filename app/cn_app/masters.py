"""Security masters: download from official sites, keep dated copies, track freshness.

Each download is converted to a standard table and kept in Data/Master Data as <key>_<YYYYMMDD>.md,
then loaded into the reference list. New listings are added; securities that have
since been delisted are kept, so old holdings still show their names.
"""
from __future__ import annotations

import gzip
import http.cookiejar
import json
import urllib.request
from datetime import datetime
from pathlib import Path

from . import opening, reference

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
BSE_API = ("https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w?Group=&Scripcode=&industry="
           "&segment={seg}&status=Active")

# key, label, what it gives, url, file extension, warm-up page (cookies), extra headers
SOURCES = [
    ("bse_all", "BSE: all active securities",
     "Equity, ETFs, mutual fund units, debentures, bonds, commercial papers, preference shares: ISIN, name, symbol",
     BSE_API.format(seg="Debt"), "json", None,
     {"Referer": "https://www.bseindia.com/", "Origin": "https://www.bseindia.com"},
     "https://www.bseindia.com/corporates/List_Scrips.html"),
    ("nse_equity", "NSE: equity list", "All NSE listed companies: symbol, name, ISIN, face value",
     "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv", "csv", "https://www.nseindia.com/", {},
     "https://www.nseindia.com/market-data/securities-available-for-trading"),
    ("nse_sme", "NSE: SME (Emerge) list", "NSE SME companies",
     "https://nsearchives.nseindia.com/emerge/corporates/content/SME_EQUITY_L.csv", "csv",
     "https://www.nseindia.com/", {}, "https://www.nseindia.com/market-data/securities-available-for-trading"),
    ("nse_etf", "NSE: ETF list", "Exchange traded funds on NSE",
     "https://nsearchives.nseindia.com/content/equities/eq_etfseclist.csv", "csv", "https://www.nseindia.com/", {},
     "https://www.nseindia.com/market-data/securities-available-for-trading"),
    ("nifty_total", "Industry: Nifty Total Market", "Industry for the 750 largest companies",
     "https://www.niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv", "csv", None, {},
     "https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-total-market"),
    ("nifty_micro", "Industry: Nifty Microcap 250", "Industry for the next 250 smaller companies",
     "https://www.niftyindices.com/IndexConstituent/ind_niftymicrocap250_list.csv", "csv", None, {},
     "https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-microcap-250"),
    ("amfi", "Mutual funds: AMFI scheme list", "Every mutual fund scheme: ISIN, name, category (Equity, Debt, Hybrid...)",
     "https://portal.amfiindia.com/spages/NAVAll.txt", "txt", None, {},
     "https://www.amfiindia.com/net-asset-value/nav-download"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS master_status (
    key TEXT PRIMARY KEY, label TEXT, updated_at TEXT, records INTEGER, file TEXT, status TEXT, message TEXT);
"""


def ensure(store):
    store.db.executescript(SCHEMA)
    reference.ensure(store)


def _opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _get(opener, url, headers, timeout=60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-IN,en;q=0.9",
                                               "Accept-Encoding": "gzip", **headers})
    with opener.open(req, timeout=timeout) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return data


def _looks_right(key: str, data: bytes) -> bool:
    head = data[:3000].decode("utf-8", errors="ignore")
    if key == "bse_all":
        return head.lstrip().startswith("[") and "ISIN_NUMBER" in head
    if key == "amfi":
        return "Scheme Code" in head
    return "ISIN" in head.upper() and "<HTML" not in head.upper()


def record(store, key, label, records=0, file="", status="OK", message=""):
    ensure(store)
    store.db.execute("INSERT OR REPLACE INTO master_status(key, label, updated_at, records, file, status, message) "
                     "VALUES (?,?,?,?,?,?,?)", (key, label, datetime.now().isoformat(timespec="seconds"), records,
                                                  file, status, message))
    store.db.commit()


def update_online(store, folder: Path, keys=None, echo=print) -> list[dict]:
    """Download the chosen masters (all by default), save them dated, and load them."""
    ensure(store)
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    opener = _opener()
    warmed = set()
    for key, label, _what, url, ext, warm, headers, _page in SOURCES:
        if keys and key not in keys:
            continue
        echo(f"Downloading {label} ...")
        try:
            if warm and warm not in warmed:
                try:
                    _get(opener, warm, {}, timeout=30)
                except Exception:  # noqa: BLE001 - only to collect cookies
                    pass
                warmed.add(warm)
            data = _get(opener, url, headers)
            if key == "bse_all":       # make sure the equity and MF segments are complete as well
                rows = {x.get("ISIN_NUMBER"): x for x in json.loads(data)}
                for seg in ("Equity", "MF"):
                    try:
                        for x in json.loads(_get(opener, BSE_API.format(seg=seg), headers)):
                            rows.setdefault(x.get("ISIN_NUMBER"), x)
                    except Exception:  # noqa: BLE001
                        pass
                data = json.dumps(list(rows.values())).encode()
            if not _looks_right(key, data):
                raise ValueError("the site did not return the expected list (it may be busy; try again later)")
            raw = folder / f"{key}_{datetime.now():%Y%m%d}.{ext}"
            raw.write_bytes(data)
            path, src, n = reference.to_markdown(raw, folder, label)
            reference.import_file(path, store)
            record(store, key, label, n, path.name, "OK", src)
            store.log(label, "Master updated", f"{n:,} securities from {url}")
            echo(f"  {label}: {n:,} securities")
            out.append({"key": key, "label": label, "ok": True, "records": n})
        except Exception as exc:  # noqa: BLE001 - every failure is shown and logged
            msg = f"{type(exc).__name__}: {exc}"
            prev = store.query("SELECT records, file, updated_at FROM master_status WHERE key=?", (key,))
            store.db.execute("INSERT OR REPLACE INTO master_status(key, label, updated_at, records, file, status, "
                             "message) VALUES (?,?,?,?,?,?,?)",
                             (key, label, prev[0]["updated_at"] if prev else None, prev[0]["records"] if prev else 0,
                              prev[0]["file"] if prev else "", "Failed", msg))
            store.db.commit()
            store.log(label, "Master update failed", msg)
            echo(f"  {label}: FAILED ({msg})")
            out.append({"key": key, "label": label, "ok": False, "error": msg})
    after(store)
    return out


def import_files(store, paths, echo=print, folder=None) -> list[dict]:
    """Load master files the user downloaded or already has (any supported format).
    With `folder`, a .md copy is kept there (the user's own file is left untouched)."""
    ensure(store)
    out = []
    for p in paths:
        p = Path(p)
        try:
            if folder and not reference.mdstore.is_ours(p):
                md, _src, _n = reference.to_markdown(p, folder, keep_original=True)
                p = md
            src, n = reference.import_file(p, store)
            record(store, f"file:{p.name}", f"File: {p.name}", n, p.name, "OK", src)
            store.log(p.name, "Master imported", f"{src}: {n:,} securities")
            echo(f"{p.name}: {src}, {n:,} securities")
            out.append({"file": p.name, "ok": True, "records": n, "source": src})
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {exc}"
            store.log(p.name, "Master import failed", msg)
            echo(f"{p.name}: FAILED ({msg})")
            out.append({"file": p.name, "ok": False, "error": msg})
    after(store)
    return out


def after(store) -> dict:
    """After any master change: complete the Scrip Master and the holdings."""
    filled = reference.fill_master(store)
    resolved = opening.resolve_pending(store)
    details = opening.fill_details(store)
    return {"filled": filled, "resolved": resolved, "details": details}


def status(store) -> list[dict]:
    ensure(store)
    known = {r["key"]: r for r in store.query("SELECT * FROM master_status")}
    rows = []
    for key, label, what, url, _ext, _w, _h, page in SOURCES:
        r = known.get(key, {})
        rows.append({"key": key, "Master": label, "Gives": what, "Last updated": (r.get("updated_at") or "")[:16],
                     "Records": r.get("records") or 0, "Status": r.get("status") or "Not yet downloaded",
                     "Message": r.get("message") or "", "File": r.get("file") or "", "url": url, "page": page})
    for key, r in known.items():
        if key.startswith("file:"):
            rows.append({"key": key, "Master": r["label"], "Gives": "Imported file", "Last updated": r["updated_at"][:16],
                         "Records": r["records"], "Status": r["status"], "Message": r["message"] or "",
                         "File": r["file"], "url": "", "page": ""})
    return rows


def age_days(store) -> int | None:
    """Days since the last successful master update, online or from a file (None if never)."""
    ensure(store)
    r = store.query("SELECT MAX(updated_at) d, COUNT(*) n FROM master_status WHERE status='OK'")
    if not r or not r[0]["d"]:
        return None
    return (datetime.now() - datetime.fromisoformat(r[0]["d"])).days
