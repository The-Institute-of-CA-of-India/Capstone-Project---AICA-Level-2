"""Reference security lists from official sources, used to fill missing details.

Supported files (format detected from the header row):
  * NSE  EQUITY_L.csv                 symbol, company name, ISIN, face value
  * NSE  eq_etfseclist.csv            ETF symbol, name, ISIN
  * Nifty index lists (e.g. ind_niftytotalmarket_list.csv)   company, industry, symbol, ISIN
  * BSE  list of scrips (Equity.csv)  security id, name, ISIN, industry / sector, face value
  * AMFI NAVAll.txt                   mutual fund scheme name, ISIN, scheme category
  * any CSV / Excel with an ISIN column (our own Scrip Master export included)

Nothing is overwritten that the user typed in the Scrip Master; only empty fields are filled.
"""
from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import mdstore

SOURCES = [
    ("NSE equity list (company names, ISIN, face value)",
     "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"),
    ("NSE ETF list",
     "https://nsearchives.nseindia.com/content/equities/eq_etfseclist.csv"),
    ("Nifty Total Market list (industry for about 750 companies)",
     "https://www.niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv"),
    ("BSE list of scrips (industry for all BSE companies; choose Equity, Active, then download)",
     "https://www.bseindia.com/corporates/List_Scrips.html"),
    ("AMFI mutual fund list with categories (save the page as NAVAll.txt)",
     "https://www.amfiindia.com/spages/NAVAll.txt"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS ref_securities (
    isin TEXT PRIMARY KEY, symbol TEXT, name TEXT, industry TEXT, sector TEXT,
    asset_class TEXT, sub_category TEXT, face_value REAL, source TEXT, updated_at TEXT);
CREATE INDEX IF NOT EXISTS ix_ref_symbol ON ref_securities(symbol);
"""


def ensure(store):
    store.db.executescript(SCHEMA)


def _h(c) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(c).upper())


def _clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() in ("nan", "none", "-") else s


# --------------------------------------------------------------------------- readers

def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        raw = pd.read_excel(path, header=None, dtype=str)
    else:
        data = path.read_bytes()
        text = data.decode("utf-8-sig", errors="ignore")
        raw = pd.read_csv(io.StringIO(text), header=None, dtype=str, sep=None, engine="python")
    hdr = next((i for i, row in raw.head(30).iterrows()
                if any("ISIN" in _h(v) for v in row.values if isinstance(v, str))), 0)
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [_h(c) for c in raw.iloc[hdr]]
    return df


def _pick(df, *names):
    for n in names:
        if n in df.columns:
            return n
    return None


def _amfi(path: Path) -> list[dict]:
    rows, category = [], ""
    text = path.read_bytes().decode("utf-8", errors="ignore").replace("\u00e2\u20ac\u2122", "'")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ";" not in line:
            m = re.match(r".*?Schemes?\s*\((.+)\)", line)
            if m:
                category = m.group(1).strip()
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 4 or not parts[0].isdigit():
            continue
        sub = _mf_sub(category)
        name = parts[3]
        if len(parts) >= 8:                       # Plan and Option columns (2026 layout)
            extra = " - ".join(p for p in parts[4:6] if p and p != "-" and p.lower() not in name.lower())
            name = f"{name} - {extra}" if extra else name
        for isin in (parts[1], parts[2]):
            if re.fullmatch(r"IN[A-Z0-9]{10}", isin or ""):
                rows.append({"isin": isin, "symbol": parts[0], "name": name, "asset_class": "Mutual Fund",
                             "sub_category": sub, "industry": category})
    return rows


BSE_SEGMENT = {"equity": "Equity", "mf": "Mutual Fund / ETF", "debentures and bonds": "Bond / Debenture",
               "commercial papers": "Commercial Paper", "preferenceshares": "Preference Shares",
               "preference shares": "Preference Shares"}


def _bse_json(path: Path) -> list[dict]:
    import json
    rows = []
    for x in json.loads(path.read_bytes().decode("utf-8", errors="ignore")):
        isin = (x.get("ISIN_NUMBER") or "").strip().upper()
        if not re.fullmatch(r"IN[A-Z0-9]{10}", isin):
            continue
        seg = (x.get("Segment") or "").strip()
        ac = BSE_SEGMENT.get(seg.lower(), "")
        if ac == "Equity" and isin[2] == "F":
            ac = "ETF"
        rows.append({"isin": isin, "symbol": (x.get("scrip_id") or "").strip(),
                     "name": (x.get("Issuer_Name") if seg.lower() == "equity" and isin[2] == "E"
                              else x.get("Scrip_Name")) or x.get("Scrip_Name") or "",
                     "industry": x.get("INDUSTRY") or "", "face_value": x.get("FACE_VALUE") or "",
                     "asset_class": ac, "bse_code": x.get("SCRIP_CD") or ""})
    return rows


def _mf_sub(category: str) -> str:
    c = category.lower()
    if "equity scheme" in c or "elss" in c:
        return "Equity Oriented" + (": " + category.split("-", 1)[1].strip() if "-" in category else "")
    if "debt scheme" in c:
        return "Debt Oriented" + (": " + category.split("-", 1)[1].strip() if "-" in category else "")
    if "hybrid" in c:
        return "Hybrid" + (": " + category.split("-", 1)[1].strip() if "-" in category else "")
    if "index" in c or "etf" in c:
        return "Index Fund / ETF"
    if "fund of funds" in c or "fof" in c:
        return "Fund of Funds"
    if "solution" in c:
        return "Solution Oriented"
    return category


def parse_file(path: Path) -> tuple[str, list[dict]]:
    """Return (detected source name, rows)."""
    path = Path(path)
    if mdstore.is_ours(path):
        return mdstore.read(path)
    head = path.read_bytes()[:4000].decode("utf-8", errors="ignore")
    if "Scheme Code;" in head or ("Scheme Name" in head and ";" in head):
        return "AMFI NAV list", _amfi(path)
    if head.lstrip().startswith("[") and "ISIN_NUMBER" in head:
        return "BSE list of scrips", _bse_json(path)

    df = _read_table(path)
    cols = set(df.columns)
    rows = []

    def add(**kw):
        isin = _clean(kw.get("isin")).upper()
        if re.fullmatch(r"IN[A-Z0-9]{10}", isin):
            kw["isin"] = isin
            rows.append({k: _clean(v) for k, v in kw.items()})

    if {"SYMBOL", "NAMEOFCOMPANY", "ISINNUMBER"} <= cols:
        src = "NSE equity list"
        for _, r in df.iterrows():
            series = _clean(r.get("SERIES"))
            add(isin=r["ISINNUMBER"], symbol=r["SYMBOL"], name=r["NAMEOFCOMPANY"], face_value=r.get("FACEVALUE"),
                asset_class="Equity" if series in ("EQ", "BE", "BZ", "SM", "ST", "") else "")
    elif {"SYMBOL", "ISINNUMBER"} <= cols and ("SECURITYNAME" in cols or "UNDERLYING" in cols):
        src = "NSE ETF list"
        for _, r in df.iterrows():
            add(isin=r["ISINNUMBER"], symbol=r["SYMBOL"], name=r.get("SECURITYNAME"), face_value=r.get("FACEVALUE"),
                asset_class="ETF", sub_category=_clean(r.get("UNDERLYING")))
    elif {"COMPANYNAME", "INDUSTRY", "ISINCODE"} <= cols:
        src = "Nifty index list"
        for _, r in df.iterrows():
            add(isin=r["ISINCODE"], symbol=r.get("SYMBOL"), name=r["COMPANYNAME"], industry=r["INDUSTRY"],
                asset_class="Equity")
    elif _pick(df, "ISINNO", "ISINNUMBER", "ISIN") and _pick(df, "SECURITYID", "SECURITYCODE"):
        src = "BSE list of scrips"
        isin_c = _pick(df, "ISINNO", "ISINNUMBER", "ISIN")
        ind_c = _pick(df, "INDUSTRYNEWNAME", "INDUSTRY", "ISUBGROUPNAME")
        sec_c = _pick(df, "SECTORNAME", "IGROUPNAME")
        for _, r in df.iterrows():
            instr = _clean(r.get("INSTRUMENT")).lower()
            ac = ("Equity" if instr in ("", "equity") else "Mutual Fund" if "mf" in instr or "mutual" in instr
                  else "Preference Shares" if "pref" in instr else "Bond / Debenture" if "deb" in instr or "bond" in instr
                  else instr.title())
            add(isin=r[isin_c], symbol=r.get("SECURITYID"), name=_clean(r.get("ISSUERNAME")) or r.get("SECURITYNAME"),
                industry=r.get(ind_c) if ind_c else "", sector=r.get(sec_c) if sec_c else "",
                face_value=r.get("FACEVALUE"), asset_class=ac)
    else:
        src = "Generic list"
        isin_c = _pick(df, "ISIN", "ISINNUMBER", "ISINNO", "ISINCODE")
        if not isin_c:
            raise ValueError("No ISIN column found in this file")
        sym_c = _pick(df, "SCRIPT", "SYMBOL", "SCRIP", "SECURITYID")
        name_c = _pick(df, "NAMEOFCOMPANY", "COMPANYNAME", "NAME", "SECURITYNAME", "ISSUERNAME")
        ind_c = _pick(df, "INDUSTRY", "SECTOR")
        ac_c = _pick(df, "ASSETCLASS", "INSTRUMENT")
        sc_c = _pick(df, "SUBCATEGORY", "CATEGORY")
        fv_c = _pick(df, "FACEVALUE")
        for _, r in df.iterrows():
            add(isin=r[isin_c], symbol=r.get(sym_c) if sym_c else "", name=r.get(name_c) if name_c else "",
                industry=r.get(ind_c) if ind_c else "", asset_class=r.get(ac_c) if ac_c else "",
                sub_category=r.get(sc_c) if sc_c else "", face_value=r.get(fv_c) if fv_c else "")
    return src, rows


def import_file(path: Path, store) -> tuple[str, int]:
    ensure(store)
    src, rows = parse_file(Path(path))
    now = datetime.now().isoformat(timespec="seconds")
    fields = ("symbol", "name", "industry", "sector", "asset_class", "sub_category", "face_value")
    with store.db:
        for r in rows:
            cur = store.db.execute("SELECT * FROM ref_securities WHERE isin=?", (r["isin"],)).fetchone()
            merged = dict(cur) if cur else {"isin": r["isin"]}
            for f in fields:
                v = r.get(f, "")
                if v not in ("", None):
                    if f == "face_value":
                        try:
                            v = float(v)
                        except ValueError:
                            continue
                    merged[f] = v
            merged["source"] = ", ".join(sorted(set(filter(None, (merged.get("source") or "").split(", "))) | {src}))
            merged["updated_at"] = now
            store.db.execute("INSERT OR REPLACE INTO ref_securities(isin, symbol, name, industry, sector, asset_class, "
                             "sub_category, face_value, source, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                             tuple(merged.get(k) for k in ("isin", *fields, "source", "updated_at")))
    return src, len(rows)


def counts(store) -> dict:
    ensure(store)
    r = store.query("SELECT COUNT(*) n, SUM(industry IS NOT NULL AND industry<>'') ind FROM ref_securities")[0]
    return {"total": r["n"] or 0, "with_industry": r["ind"] or 0}


def fill_master(store) -> int:
    """Fill empty Scrip Master fields from the reference list. Returns number of scrips updated."""
    ensure(store)
    n = 0
    with store.db:
        for m in store.query("SELECT m.*, r.name rn, r.industry ri, r.asset_class ra, r.sub_category rs, "
                             "r.face_value rf, r.symbol rsym FROM scrip_master m JOIN ref_securities r ON r.isin = m.isin"):
            upd = {}
            if not m["company_name"] and m["rn"]:
                upd["company_name"] = m["rn"]
            if not m["industry"] and m["ri"]:
                upd["industry"] = m["ri"]
            if not m["asset_class"] and m["ra"]:
                upd["asset_class"] = m["ra"]
            if not m["sub_category"] and m["rs"]:
                upd["sub_category"] = m["rs"]
            if not m["face_value"] and m["rf"]:
                upd["face_value"] = m["rf"]
            if m["source"] == "Opening holdings" and m["rsym"] and (" " in (m["symbol"] or "") or not m["symbol"]):
                upd["symbol"] = m["rsym"]
            if upd:
                sets = ", ".join(f"{k}=?" for k in upd)
                store.db.execute(f"UPDATE scrip_master SET {sets}, updated_at=? WHERE isin=?",
                                 (*upd.values(), datetime.now().isoformat(timespec="seconds"), m["isin"]))
                n += 1
    return n


# --------------------------------------------------------------------------- name to ISIN

_DROP = {"LTD", "LIMITED", "THE", "CO", "COMPANY", "PVT", "PRIVATE", "INC", "CORP", "CORPN", "CORPORATION"}


def norm(name: str) -> str:
    s = str(name or "").upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return " ".join(w for w in s.split() if w not in _DROP)


def resolve(store, script: str) -> tuple[str | None, str]:
    """Find the ISIN for a script/company name. Returns (isin or None, how it matched)."""
    ensure(store)
    if not script:
        return None, ""
    cands = []
    for part in [script] + [p for p in re.split(r"\s+-\s+|/", script) if p.strip() and p.strip() != script]:
        q = part.strip()
        qs = re.sub(r"[^A-Z0-9&-]", "", q.upper())
        # 1. exact symbol (reference list or our own Scrip Master)
        for sql in ("SELECT isin FROM ref_securities WHERE UPPER(symbol)=? AND isin LIKE 'INE%'",
                    "SELECT isin FROM scrip_master WHERE UPPER(symbol)=?"):
            hits = {r["isin"] for r in store.query(sql, (qs,))}
            if len(hits) == 1:
                return hits.pop(), f"symbol {qs}"
        nq = norm(q)
        if not nq:
            continue
        rows = store.query("SELECT isin, name, asset_class FROM ref_securities WHERE name IS NOT NULL AND name<>''")
        rows += store.query("SELECT isin, company_name AS name, asset_class FROM scrip_master "
                            "WHERE company_name IS NOT NULL AND company_name<>''")
        exact = {r["isin"] for r in rows if norm(r["name"]) == nq}
        if len(exact) == 1:
            return exact.pop(), "company name"
        starts = {r["isin"] for r in rows if norm(r["name"]).startswith(nq + " ") or norm(r["name"]).startswith(nq)}
        eq = {i for i in starts if i.startswith("INE")}
        if len(eq) == 1:
            cands.append((eq.pop(), "start of company name"))
    if len({c[0] for c in cands}) == 1:
        return cands[0]
    return None, ""


def to_markdown(path: Path, folder: Path, title: str = "", keep_original: bool = False) -> tuple[Path, str, int]:
    """Convert any supported master file to the standard .md table in `folder`; remove the original."""
    path = Path(path)
    src, rows = parse_file(path)
    if not rows:
        raise ValueError("no securities with a valid ISIN were found in the file")
    out = mdstore.write(Path(folder) / (path.stem + ".md"), title or src, f"{src} ({path.name})", rows)
    if not keep_original and out.resolve() != path.resolve():
        try:
            path.unlink()
        except OSError:
            pass
    return out, src, len(rows)
