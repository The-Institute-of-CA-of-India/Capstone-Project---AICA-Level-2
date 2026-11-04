"""Tally masters kept in the app, and matching scripts to Tally ledgers by name.

Tally ledger names are written by people: "Tata Tech", "Jio Finance", "Allied Digital Services",
"Axis Bank Shares". Scripts in the app are symbols (TATATECH, JIOFIN, ADSL, AXISBANK) with the
company name from the masters. Each script gets a score against every investment ledger:

  100  saved by you (a match you chose is always used)
   98  same name (company name or symbol, ignoring Ltd / Limited / Shares / punctuation)
   94  the symbol is made of the beginnings of the ledger's words (TATA+TECH, JIO+FIN, PITTIE+ENG)
   90  the ledger's words are the beginnings of the company name's words (ZYDUS WELL -> ZYDUS WELLNESS)
   88  initials (ADSL -> Allied Digital Services Limited)
  <85  overall similarity of the letters

The best ledger is used when it scores 80 or more and is clearly ahead of the next one;
otherwise the script is shown as "Not matched" and you choose, or create the ledger.
"""
from __future__ import annotations

import difflib
import re
from collections import Counter
from datetime import datetime

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS tally_ledgers (company TEXT, name TEXT, parent TEXT, under TEXT, imported_at TEXT,
    PRIMARY KEY (company, name, parent));
CREATE TABLE IF NOT EXISTS tally_ledger_map (company TEXT, key TEXT, ledger TEXT, PRIMARY KEY (company, key));
"""
DROP = {"LTD", "LIMITED", "THE", "CO", "COMPANY", "PVT", "PRIVATE", "INC", "CORP", "CORPN", "CORPORATION",
        "SHARES", "SHARE", "EQUITY", "EQ", "INVESTMENT", "INVESTMENTS", "IN", "OF", "A/C", "AC", "ACCOUNT",
        "STOCK", "STOCKS", "SCRIP", "INDIA"}
ACCEPT, MARGIN = 80, 4


def ensure(store):
    store.db.executescript(SCHEMA)


def words(s: str) -> list[str]:
    s = str(s or "").upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return [w for w in s.split() if w not in DROP]


def _prefix_split(sym: str, toks: list[str]) -> bool:
    """Can `sym` be written as beginnings of the tokens, in order (every token used, at least 1 letter each)?"""
    if not toks:
        return False

    def go(i: int, j: int) -> bool:
        if j == len(toks):
            return i == len(sym)
        t = toks[j]
        for k in range(min(len(t), len(sym) - i), 0, -1):
            if sym[i:i + k] == t[:k] and go(i + k, j + 1):
                return True
        return False
    return len(sym) >= 3 and go(0, 0)


def score(ledger: str, symbol: str, company: str) -> tuple[int, str]:
    lw, cw = words(ledger), words(company)
    lc, sc, cc = "".join(lw), re.sub(r"[^A-Z0-9]", "", (symbol or "").upper()), "".join(cw)
    if not lc:
        return 0, ""
    if (cc and lc == cc) or (sc and lc == sc):
        return 98, "same name"
    if sc and _prefix_split(sc, lw):
        return 94, "symbol = start of ledger words"
    if sc and len(sc) >= 4 and len(lw) == 2 and lw[0] == sc:
        return 86, "symbol = first word of ledger"
    if cc and len(lc) >= 6 and cc.startswith(lc) and len(lc) >= 0.7 * len(cc):
        return 92, "ledger = company name, shortened"
    if cw and len(lw) <= len(cw) and all(c.startswith(w) for w, c in zip(lw, cw)) and len(lc) >= 3:
        if len(lw) >= 2 or len(cw) == 1:
            return 90, "ledger = start of company name"
        return 76, "first word of company name"
    if sc and len(sc) >= 3 and cw and "".join(w[0] for w in cw) == sc:
        if "".join(w[0] for w in lw) == sc:
            return 88, "initials"
    if sc and len(sc) >= 3 and len(lw) >= 2 and "".join(w[0] for w in lw) == sc:
        return 88, "initials"
    best = max(difflib.SequenceMatcher(None, lc, x).ratio() for x in (cc, sc) if x) if (cc or sc) else 0
    return int(best * 84), "similar letters"


def save_ledgers(store, company: str, df: pd.DataFrame) -> int:
    ensure(store)
    now = datetime.now().isoformat(timespec="seconds")
    with store.db:
        store.db.execute("DELETE FROM tally_ledgers WHERE company=?", (company,))
        store.db.executemany("INSERT OR REPLACE INTO tally_ledgers VALUES (?,?,?,?,?)",
                             [(company, r["Ledger"], r.get("Group", "") or "", r.get("Under", "") or "", now)
                              for _, r in df.iterrows()])
    store.log(company, "Tally masters imported", f"{len(df)} ledgers")
    return len(df)


def companies(store) -> list[str]:
    ensure(store)
    return [r["company"] for r in store.query("SELECT DISTINCT company FROM tally_ledgers ORDER BY company")]


def ledgers(store, company: str) -> pd.DataFrame:
    ensure(store)
    rows = store.query("SELECT name, parent, under, imported_at FROM tally_ledgers WHERE company=? ORDER BY name",
                       (company,))
    return pd.DataFrame(rows, columns=["name", "parent", "under", "imported_at"])


def investment_ledgers(store, company: str, group: str = "Investments") -> list[str]:
    """Ledgers under the investment group at any depth (e.g. Investments > Shares Investments)."""
    df = ledgers(store, company)
    g = group.strip().lower()
    return [r["name"] for _, r in df.iterrows()
            if g in [x.strip().lower() for x in (r["under"] or r["parent"] or "").split(" > ")]]


def share_group(store, company: str, group: str = "Investments") -> str:
    """Where the share ledgers live: the commonest parent of the investment ledgers (else the group itself)."""
    df = ledgers(store, company)
    inv = set(investment_ledgers(store, company, group))
    parents = Counter(r["parent"] for _, r in df.iterrows() if r["name"] in inv and r["parent"])
    return parents.most_common(1)[0][0] if parents else group


def set_map(store, company: str, key: str, ledger: str | None):
    ensure(store)
    if ledger:
        store.db.execute("INSERT OR REPLACE INTO tally_ledger_map VALUES (?,?,?)", (company, key, ledger))
    else:
        store.db.execute("DELETE FROM tally_ledger_map WHERE company=? AND key=?", (company, key))
    store.db.commit()


def scripts(store) -> pd.DataFrame:
    """Every script in the app (contract notes and opening holdings) with symbol and company name."""
    rows = store.query(
        "SELECT y.key, y.isin, y.symbol, COALESCE(NULLIF(m.company_name,''), "
        "(SELECT f.name FROM ref_securities f WHERE f.isin=y.isin), y.cname, '') company FROM ("
        " SELECT x.key, MAX(x.isin) isin, MAX(x.symbol) symbol, MAX(x.cname) cname FROM ("
        "  SELECT s.isin key, s.isin, s.symbol, '' cname FROM scrips s"
        "  UNION ALL SELECT COALESCE(NULLIF(o.isin,''), 'NAME:' || o.script), o.isin, o.script, o.company_name"
        "  FROM opening_lots o) x GROUP BY x.key) y LEFT JOIN scrip_master m ON m.isin=y.isin ORDER BY y.symbol")
    return pd.DataFrame(rows, columns=["key", "isin", "symbol", "company"])


def match_all(store, company: str, group: str = "Investments") -> pd.DataFrame:
    """Script -> ledger with score; saved choices first."""
    ensure(store)
    inv = investment_ledgers(store, company, group)
    saved = {r["key"]: r["ledger"] for r in store.query("SELECT key, ledger FROM tally_ledger_map WHERE company=?",
                                                         (company,))}
    allnames = set(ledgers(store, company)["name"])
    out = []
    for _, s in scripts(store).iterrows():
        if s["key"] in saved and saved[s["key"]] in allnames:
            out.append({**s, "ledger": saved[s["key"]], "score": 100, "how": "chosen by you", "second": ""})
            continue
        ranked = sorted(((*score(l, s["symbol"], s["company"]), l) for l in inv), reverse=True)
        top = ranked[0] if ranked else (0, "", "")
        nxt = ranked[1] if len(ranked) > 1 else (0, "", "")
        ok = top[0] >= ACCEPT and top[0] - nxt[0] >= MARGIN
        out.append({**s, "ledger": top[2] if ok else "", "score": top[0], "how": top[1] if ok else "not matched",
                    "second": top[2] if not ok and top[0] >= 60 else ""})
    return pd.DataFrame(out, columns=["key", "isin", "symbol", "company", "ledger", "score", "how", "second"])


def suggest_name(symbol: str, company: str) -> str:
    """A ledger name in the style of the user's ledgers: the company name without Ltd / Limited."""
    name = company or symbol
    name = re.sub(r"\b(LIMITED|LTD\.?|PVT\.?|PRIVATE)\b", "", name, flags=re.I).strip(" .,-")
    return " ".join(w if w.isupper() and len(w) <= 4 else w.title() for w in name.split()) or symbol


def best_ledger(store, company: str, wanted: str, group: str = "") -> str:
    """For broker / gain ledgers: an existing ledger whose name matches best ('' if none is close)."""
    df = ledgers(store, company)
    if group:
        df = df[df["under"].str.lower().str.contains(group.lower(), na=False) | (df["parent"].str.lower() == group.lower())]
    ranked = sorted(((score(n, wanted, wanted)[0], n) for n in df["name"]), reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] >= ACCEPT else ""
