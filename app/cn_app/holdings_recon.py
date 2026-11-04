"""Holding reconciliation: holdings as per the app vs a holding statement (DP / broker / CAS).

Holding as per the app on a date = opening holdings held on that date
                                   + contract-note purchases up to that date
                                   - contract-note sales up to that date.
The statement can be Excel, CSV or PDF; its columns are recognised automatically and
can be changed by the user before matching.
"""
from __future__ import annotations

import io
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import reference
from .utils import isin_check_digit_ok

ISIN_RE = re.compile(r"\bIN[A-Z0-9]{9}\d\b")

ALIASES = {
    "isin": ["isin", "isin code", "isin no", "isin number", "isin no."],
    "symbol": ["symbol", "scrip", "script", "scrip code", "trading symbol", "security id", "nse symbol", "bse code"],
    "name": ["security name", "company name", "name of security", "security", "scrip name", "name", "instrument",
             "security description", "description", "company", "stock name", "scheme name"],
    "qty": ["quantity available", "total quantity", "total qty", "total balance", "total holding", "current balance",
            "free balance", "closing balance", "net quantity", "quantity", "qty", "balance", "holding", "holdings",
            "units", "no. of shares", "no of shares", "shares", "total"],
    "value": ["current value", "market value", "value", "valuation", "holding value", "present value", "cur. val"],
}

SOURCES = [
    ("CDSL (Easi / Easiest): holding statement", "https://web.cdslindia.com/myeasitoken/Home/Login"),
    ("NSDL (IDeAS / e-CAS)", "https://eservices.nsdl.com/"),
    ("NSDL CAS (consolidated statement)", "https://nsdlcas.nsdl.com/"),
    ("CAMS: mutual fund CAS", "https://www.camsonline.com/Investors/Statements/Consolidated-Account-Statement"),
    ("KFintech: mutual fund CAS", "https://mfs.kfintech.com/investor/General/ConsolidatedAccountStatement"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS holding_recon_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_at TEXT, person_key TEXT, person TEXT, as_on TEXT, broker TEXT,
    file TEXT, rows INTEGER, matched INTEGER, differences INTEGER, only_app INTEGER, only_statement INTEGER,
    result TEXT);
"""


def ensure(store):
    store.db.executescript(SCHEMA)


def _h(c) -> str:
    return re.sub(r"\s+", " ", str(c).strip().lower())


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip().replace(",", "").replace("₹", "")
    if s in ("", "-", "nan", "None"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        x = float(s)
    except ValueError:
        return None
    return -x if neg else x


# --------------------------------------------------------------------------- reading statements

def _frame_from_rows(rows: list[list]) -> pd.DataFrame | None:
    """Find the header row (needs an ISIN/name column and a quantity column) and build a table."""
    best, hdr = 0, None
    for i, row in enumerate(rows[:60]):
        names = [_h(x) for x in row if x is not None and str(x).strip()]
        score = sum(any(n == a or n.startswith(a) for n in names for a in al) for al in ALIASES.values())
        if score > best:
            best, hdr = score, i
    if hdr is None or best < 2:
        return None
    header = [str(x).strip() if x is not None and str(x).strip() else f"Column {j + 1}"
              for j, x in enumerate(rows[hdr])]
    seen, uniq = {}, []
    for h in header:                      # make column names unique
        seen[h] = seen.get(h, 0) + 1
        uniq.append(h if seen[h] == 1 else f"{h} ({seen[h]})")
    body = [r + [None] * (len(uniq) - len(r)) for r in rows[hdr + 1:]]
    df = pd.DataFrame([r[:len(uniq)] for r in body], columns=uniq)
    df = df.dropna(how="all")
    return df


def read_statement(path: Path) -> tuple[pd.DataFrame, str]:
    """Return (table, how it was read)."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext in (".xlsx", ".xls"):
        best = None
        for sheet, raw in pd.read_excel(path, header=None, sheet_name=None, dtype=object).items():
            df = _frame_from_rows(raw.where(raw.notna(), None).values.tolist())
            if df is not None and (best is None or len(df) > len(best[0])):
                best = (df, f"Excel sheet '{sheet}'")
        if best is None:
            raise ValueError("no table with ISIN / name and quantity columns was found in the workbook")
        return best
    if ext in (".csv", ".txt"):
        text = path.read_bytes().decode("utf-8-sig", errors="ignore")
        raw = pd.read_csv(io.StringIO(text), header=None, dtype=str, sep=None, engine="python",
                          on_bad_lines="skip")
        df = _frame_from_rows(raw.where(raw.notna(), None).values.tolist())
        if df is None:
            raise ValueError("no header row with ISIN / name and quantity columns was found in the file")
        return df, "CSV file"
    if ext == ".pdf":
        return _read_pdf(path)
    raise ValueError(f"'{ext}' files are not supported; use PDF, Excel or CSV")


def _read_pdf(path: Path, passwords=()) -> tuple[pd.DataFrame, str]:
    import pdfplumber
    from .extract import _filename_tokens

    last = None
    for pw in [""] + list(passwords) + _filename_tokens(path.name):
        try:
            pdf = pdfplumber.open(path, password=pw)
            break
        except Exception as exc:  # noqa: BLE001
            last = exc
    else:
        raise PermissionError(f"the PDF could not be opened ({type(last).__name__}); if it is password protected, "
                              "add the password in Settings > PDF passwords")
    with pdf:
        rows, lines = [], []
        for page in pdf.pages:
            for t in page.extract_tables() or []:
                rows += [[(c or "").replace("\n", " ").strip() if isinstance(c, str) else c for c in r] for r in t]
            lines += (page.extract_text() or "").splitlines()
    df = _frame_from_rows(rows) if rows else None
    if df is not None and len(df):
        return df, "PDF table"
    # no ruled table: take every text line that carries an ISIN
    recs = []
    for ln in lines:
        m = ISIN_RE.search(ln)
        if not m:
            continue
        before, after = ln[:m.start()].strip(), ln[m.end():].strip()
        nums = [x for x in re.findall(r"\(?-?[\d,]+(?:\.\d+)?\)?", after) if any(ch.isdigit() for ch in x)]
        words = re.sub(r"[\d,().-]+", " ", after).strip()
        recs.append({"ISIN": m.group(0), "Name": before or words,
                     **{f"Number {i + 1}": n for i, n in enumerate(nums[:8])}})
    if not recs:
        raise ValueError("no ISINs were found in the PDF; it may be a scanned image or a different kind of statement")
    return pd.DataFrame(recs), "PDF text lines (check the quantity column)"


def guess_columns(df: pd.DataFrame) -> dict:
    cols = list(df.columns)
    low = {c: _h(c) for c in cols}
    out = {}
    for field, al in ALIASES.items():
        for a in al:                                    # alias order is priority order
            hit = next((c for c in cols if low[c] == a), None) or \
                next((c for c in cols if low[c].startswith(a) and c not in out.values()), None)
            if hit and hit not in out.values():
                out[field] = hit
                break
    if "isin" not in out:                               # a column full of ISINs
        for c in cols:
            vals = df[c].dropna().astype(str).head(30)
            if len(vals) and (vals.str.fullmatch(r"IN[A-Z0-9]{10}").mean() > 0.6):
                out["isin"] = c
                break
    if "qty" not in out:                                # first mostly-numeric column after the ISIN
        for c in cols:
            if c in out.values():
                continue
            vals = df[c].dropna().head(30).map(_num)
            if len(vals) and vals.notna().mean() > 0.8:
                out["qty"] = c
                break
    return out


def statement_rows(store, df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """Clean statement rows: ISIN (found from name/symbol if missing), name, quantity, value."""
    out = []
    for _, r in df.iterrows():
        isin = str(r.get(mapping.get("isin"), "") or "").strip().upper() if mapping.get("isin") else ""
        m = ISIN_RE.search(isin)
        isin = m.group(0) if m else ""
        name = str(r.get(mapping.get("name"), "") or "").strip() if mapping.get("name") else ""
        sym = str(r.get(mapping.get("symbol"), "") or "").strip() if mapping.get("symbol") else ""
        qty = _num(r.get(mapping.get("qty"))) if mapping.get("qty") else None
        if qty is None and not isin:
            continue                                     # totals, notes, blank lines
        if not isin:
            isin = reference.resolve(store, sym or name)[0] or ""
        if not isin and not (sym or name):
            continue
        out.append({"isin": isin if isin and isin_check_digit_ok(isin) else isin, "symbol": sym, "name": name,
                    "qty_stmt": qty or 0.0,
                    "value_stmt": _num(r.get(mapping.get("value"))) if mapping.get("value") else None})
    st = pd.DataFrame(out, columns=["isin", "symbol", "name", "qty_stmt", "value_stmt"])
    if not len(st):
        return st
    st["key"] = st["isin"].where(st["isin"] != "", "NAME:" + st["symbol"].where(st["symbol"] != "", st["name"]))
    agg = st.groupby("key").agg(isin=("isin", "first"), symbol=("symbol", "first"), name=("name", "first"),
                                qty_stmt=("qty_stmt", "sum"), value_stmt=("value_stmt", "sum")).reset_index()
    return agg


# --------------------------------------------------------------------------- holdings as per the app

def app_holdings(store, person_key: str, as_on: str, broker: str = "") -> pd.DataFrame:
    """Quantity held per ISIN on `as_on` for a person (PAN or 'NAME:<name>')."""
    rows = []
    if person_key and not person_key.startswith("NAME:"):
        q = ("SELECT s.isin, MAX(s.symbol) symbol, SUM(CASE WHEN s.side='BUY' THEN s.qty ELSE -s.qty END) qty "
             "FROM scrips s JOIN notes n ON n.id=s.note_id WHERE n.pan=? AND n.trade_date<=?")
        args = [person_key, as_on]
        if broker:
            q += " AND n.broker=?"
            args.append(broker)
        rows += [dict(r, src="Contract notes") for r in store.query(q + " GROUP BY s.isin", tuple(args))]
    lot_where = "o.pan=?" if person_key and not person_key.startswith("NAME:") else "UPPER(o.person)=?"
    lot_arg = person_key if not person_key.startswith("NAME:") else person_key[5:]
    q = (f"SELECT COALESCE(NULLIF(o.isin,''), 'NAME:' || o.script) isin, MAX(o.script) symbol, SUM(o.qty) qty "
         f"FROM opening_lots o WHERE {lot_where} AND o.purchase_date<=? "
         "AND (o.sale_date IS NULL OR o.sale_date>?)")
    args = [lot_arg, as_on, as_on]
    if broker:
        q += " AND (o.broker='' OR o.broker IS NULL OR ? LIKE '%' || o.broker || '%' OR o.broker LIKE '%' || ? || '%')"
        args += [broker, broker.split()[0]]
    rows += [dict(r, src="Opening holdings") for r in store.query(q + " GROUP BY 1", tuple(args))]
    if not rows:
        return pd.DataFrame(columns=["key", "isin", "symbol_app", "qty_app", "sources"])
    df = pd.DataFrame(rows)
    df["key"] = df["isin"]
    agg = df.groupby("key").agg(isin=("isin", "first"), symbol_app=("symbol", "first"), qty_app=("qty", "sum"),
                                sources=("src", lambda s: ", ".join(sorted(set(s))))).reset_index()
    agg["isin"] = agg["isin"].where(~agg["isin"].str.startswith("NAME:"), "")
    return agg


# --------------------------------------------------------------------------- matching

def reconcile(store, person_key: str, as_on: str, stmt: pd.DataFrame, broker: str = "",
              include_zero: bool = False) -> pd.DataFrame:
    app = app_holdings(store, person_key, as_on, broker)
    m = pd.merge(app, stmt, on="key", how="outer", suffixes=("_app", "_stmt"))
    names = {r["isin"]: (r["symbol"], r["company_name"]) for r in store.query("SELECT isin, symbol, company_name "
                                                                               "FROM scrip_master")}
    out = []
    for _, r in m.iterrows():
        isin = (r.get("isin_app") if isinstance(r.get("isin_app"), str) and r.get("isin_app") else
                r.get("isin_stmt") if isinstance(r.get("isin_stmt"), str) else "") or ""
        qa = float(r["qty_app"]) if pd.notna(r.get("qty_app")) else 0.0
        qs = float(r["qty_stmt"]) if pd.notna(r.get("qty_stmt")) else 0.0
        in_app, in_stmt = pd.notna(r.get("qty_app")), pd.notna(r.get("qty_stmt"))
        if not include_zero and abs(qa) < 1e-9 and not in_stmt:
            continue                                     # fully sold in the app and not on the statement
        diff = round(qs - qa, 4)
        status = ("Opening holding missing" if qa < -1e-9 else
                  "Matched" if abs(diff) < 1e-6 else
                  "Only in statement" if not in_app or abs(qa) < 1e-9 else
                  "Only in app" if not in_stmt or abs(qs) < 1e-9 else "Difference")
        sym, comp = names.get(isin, ("", ""))
        out.append({"ISIN": isin, "Script": sym or (r.get("symbol_app") if isinstance(r.get("symbol_app"), str) else "")
                    or (r.get("symbol") if isinstance(r.get("symbol"), str) else ""),
                    "Name of Company": comp or (r.get("name") if isinstance(r.get("name"), str) else ""),
                    "Qty as per App": qa, "Qty as per Statement": qs, "Difference (Statement - App)": diff,
                    "Status": status,
                    "Value as per Statement": float(r["value_stmt"]) if pd.notna(r.get("value_stmt")) else None,
                    "App source": r.get("sources") if isinstance(r.get("sources"), str) else ""})
    order = {"Difference": 0, "Opening holding missing": 1, "Only in app": 2, "Only in statement": 3, "Matched": 4}
    res = pd.DataFrame(out, columns=["ISIN", "Script", "Name of Company", "Qty as per App", "Qty as per Statement",
                                     "Difference (Statement - App)", "Status", "Value as per Statement",
                                     "App source"])
    if len(res):
        res = res.sort_values(by=["Status", "Script"], key=lambda c: c.map(order) if c.name == "Status" else c)
    return res.reset_index(drop=True)


def save_run(store, person_key, person, as_on, broker, file, res: pd.DataFrame) -> int:
    ensure(store)
    c = res["Status"].value_counts().to_dict() if len(res) else {}
    cur = store.db.execute(
        "INSERT INTO holding_recon_runs(run_at, person_key, person, as_on, broker, file, rows, matched, differences, "
        "only_app, only_statement, result) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), person_key, person, as_on, broker or "All brokers", file,
         len(res), c.get("Matched", 0), c.get("Difference", 0) + c.get("Opening holding missing", 0),
         c.get("Only in app", 0), c.get("Only in statement", 0),
         res.to_json(orient="records")))
    store.db.commit()
    store.log(file, "Holding reconciliation",
              f"{person} as on {as_on}: {c.get('Matched', 0)} matched, {c.get('Difference', 0)} differ, "
              f"{c.get('Only in app', 0)} only in app, {c.get('Only in statement', 0)} only in statement")
    return cur.lastrowid


def runs(store) -> pd.DataFrame:
    ensure(store)
    r = store.query("SELECT id, run_at, person, as_on, broker, file, rows, matched, differences, only_app, "
                    "only_statement FROM holding_recon_runs ORDER BY id DESC")
    df = pd.DataFrame(r, columns=["id", "run_at", "person", "as_on", "broker", "file", "rows", "matched",
                                  "differences", "only_app", "only_statement"])
    df.columns = ["_id", "Run on", "Person", "As on Date", "Broker / DP", "Statement file", "Scripts", "Matched",
                  "Difference", "Only in App", "Only in Statement"]
    df["Run on"] = df["Run on"].str.replace("T", " ").str[:16]
    return df


def run_result(store, run_id: int) -> pd.DataFrame:
    r = store.query("SELECT result FROM holding_recon_runs WHERE id=?", (run_id,))
    return pd.DataFrame(json.loads(r[0]["result"])) if r else pd.DataFrame()
