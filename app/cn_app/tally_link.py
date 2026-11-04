"""Tally Prime: ledger balances as on a date, read live (XML over HTTP) or from an exported file.

Live reading needs Tally Prime open with a company loaded and its connectivity set to
act as Server/Both on port 9000 (F1 > Settings > Connectivity).
"""
from __future__ import annotations

import io
import re
import socket
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pandas as pd

from . import reference

URL = "http://localhost:9000"


def _post(xml: str, url: str = URL, timeout=90) -> str:
    # 127.0.0.1 rather than "localhost": Windows may try IPv6 first, which Tally does not listen on
    url = (url or URL).replace("//localhost", "//127.0.0.1")
    req = urllib.request.Request(url, data=xml.encode("utf-8"), headers={"Content-Type": "text/xml;charset=utf-8"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))     # Tally is local: no proxy
    try:
        with opener.open(req, timeout=timeout) as r:
            raw = r.read()
    except (TimeoutError, socket.timeout) as exc:
        raise ConnectionError(f"Tally is running but did not reply within {timeout} seconds. Tally is busy or is "
                              "waiting for you: press Esc on any open report or message in Tally (or restart "
                              "Tally), then try again") from exc
    except ConnectionRefusedError as exc:
        raise ConnectionError(f"nothing is answering at {url}: Tally Prime is closed, or Connectivity is not set "
                              "to act as Both on port 9000 (F1 Help > Settings > Connectivity)") from exc
    except OSError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise ConnectionError(f"Tally is running but did not reply within {timeout} seconds. Tally is busy or "
                                  "is waiting for you: press Esc on any open report or message in Tally (or "
                                  "restart Tally), then try again") from exc
        if isinstance(reason, ConnectionRefusedError):
            raise ConnectionError(f"nothing is answering at {url}: Tally Prime is closed, or Connectivity is not "
                                  "set to act as Both on port 9000 (F1 Help > Settings > Connectivity)") from exc
        raise ConnectionError(f"Tally could not be reached at {url}: {reason}") from exc
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _clean(xml_text: str) -> str:
    # Tally sometimes sends control characters and bare ampersand entities that strict XML parsers reject
    xml_text = re.sub(r"&#(?:[0-8]|1[1-2]|1[4-9]|2[0-9]|3[01]);", "", xml_text)
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", xml_text)


def companies(url: str = URL) -> list[str]:
    xml = ("<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE>"
           "<ID>CNMCompanies</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
           "</STATICVARIABLES><TDL><TDLMESSAGE><COLLECTION NAME='CNMCompanies' ISMODIFY='No'><TYPE>Company</TYPE>"
           "<FETCH>Name</FETCH></COLLECTION></TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>")
    root = ET.fromstring(_clean(_post(xml, url)))
    return [c.get("NAME") or (c.findtext("NAME") or "") for c in root.iter("COMPANY")]


def ledgers(company: str, as_on: str, url: str = URL, balances: bool = True) -> pd.DataFrame:
    """All ledgers with parent group (and, if asked, closing balance as on the date, debit positive).
    Without balances the request is light and quick (used to import the ledger names)."""
    comp = f"<SVCURRENTCOMPANY>{_esc(company)}</SVCURRENTCOMPANY>" if company else ""
    dates = f"<SVTODATE>{date.fromisoformat(as_on).strftime('%Y%m%d')}</SVTODATE>" if balances else ""
    fetch = "Name, Parent, ClosingBalance" if balances else "Name, Parent"
    xml = ("<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE>"
           "<ID>CNMLedgers</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
           f"{comp}{dates}</STATICVARIABLES>"
           "<TDL><TDLMESSAGE><COLLECTION NAME='CNMLedgers' ISMODIFY='No'><TYPE>Ledger</TYPE>"
           f"<FETCH>{fetch}</FETCH></COLLECTION></TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>")
    df = parse_ledger_xml(_post(xml, url))
    try:                                   # full group chain, so sub-groups of Investments count too
        gxml = xml.replace("CNMLedgers", "CNMGroups").replace("<TYPE>Ledger</TYPE>", "<TYPE>Group</TYPE>") \
            .replace(f"<FETCH>{fetch}</FETCH>", "<FETCH>Name, Parent</FETCH>").replace(dates, "")
        root = ET.fromstring(_clean(_post(gxml, url)))
        parent = {(g.get("NAME") or g.findtext("NAME") or "").strip(): (g.findtext("PARENT") or "").strip()
                  for g in root.iter("GROUP")}
        df["Under"] = [" > ".join(_chain(g, parent)) for g in df["Group"]]
    except Exception:  # noqa: BLE001
        df["Under"] = df["Group"]
    return df


def _chain(g: str, parent: dict) -> list[str]:
    out, seen = [], set()
    while g and g not in seen:
        out.append(g)
        seen.add(g)
        g = parent.get(g, "")
    return out


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_ledger_xml(text: str) -> pd.DataFrame:
    root = ET.fromstring(_clean(text))
    rows = []
    for led in root.iter("LEDGER"):
        name = led.get("NAME") or led.findtext("NAME") or ""
        parent = (led.findtext("PARENT") or "").strip()
        bal = _amount(led.findtext("CLOSINGBALANCE"))
        rows.append({"Ledger": name.strip(), "Group": parent, "Balance": bal})
    return pd.DataFrame(rows, columns=["Ledger", "Group", "Balance"])


def _amount(v) -> float:
    """Tally XML amounts: negative = debit, positive = credit. Return debit as positive."""
    if v is None:
        return 0.0
    s = str(v).replace(",", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return 0.0
    x = float(m.group(0))
    if s.endswith("Cr"):
        return -abs(x)
    if s.endswith("Dr"):
        return abs(x)
    return -x


def ledgers_from_file(path: Path) -> pd.DataFrame:
    """A Tally report exported to Excel / CSV (Trial Balance, Group Summary or Ledger list)."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        raw = pd.read_excel(path, header=None, dtype=object)
    elif path.suffix.lower() == ".xml":
        return parse_ledger_xml(path.read_bytes().decode("utf-8", errors="ignore"))
    else:
        raw = pd.read_csv(io.StringIO(path.read_bytes().decode("utf-8-sig", errors="ignore")), header=None,
                          dtype=str, sep=None, engine="python", on_bad_lines="skip")
    raw = raw.where(raw.notna(), None)
    rows = []
    for _, r in raw.iterrows():
        vals = list(r.values)
        name = next((str(v).strip() for v in vals if isinstance(v, str) and re.search(r"[A-Za-z]", v)), "")
        nums = [v for v in vals if _num(v) is not None]
        if not name or not nums or name.lower() in ("particulars", "grand total", "total"):
            continue
        # Trial balance style: Debit and Credit columns -> balance = debit - credit
        if len(nums) >= 2:
            dr, cr = _num(nums[-2]) or 0.0, _num(nums[-1]) or 0.0
            bal = dr - cr
        else:
            bal = _num(nums[0])
            if isinstance(nums[0], str) and nums[0].strip().endswith("Cr"):
                bal = -abs(bal)
        rows.append({"Ledger": name, "Group": "", "Balance": bal})
    if not rows:
        raise ValueError("no ledger names with amounts were found; export Tally's Trial Balance or Group Summary "
                         "(with closing balances) to Excel and upload that")
    return pd.DataFrame(rows, columns=["Ledger", "Group", "Balance"])


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return None if pd.isna(v) else float(v)
    s = str(v).replace(",", "").replace("Dr", "").replace("Cr", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


# --------------------------------------------------------------------------- matching ledgers to scripts

SCHEMA = """
CREATE TABLE IF NOT EXISTS tally_map (person_key TEXT, key TEXT, ledger TEXT, PRIMARY KEY (person_key, key));
"""


def ensure(store):
    store.db.executescript(SCHEMA)


def set_map(store, person_key, key, ledger):
    ensure(store)
    store.db.execute("INSERT OR REPLACE INTO tally_map VALUES (?,?,?)", (person_key, key, ledger or ""))
    store.db.commit()


def auto_ledger(ledger_names: list[str], symbol: str, company: str, pattern: str) -> str:
    """Best ledger for a script: the configured pattern first, then company / symbol name inside the ledger name."""
    by_norm = {reference.norm(n): n for n in ledger_names}
    for cand in (pattern.format(script=company or symbol, symbol=symbol, isin=""), company, symbol):
        if cand and reference.norm(cand) in by_norm:
            return by_norm[reference.norm(cand)]
    keys = [k for k in (reference.norm(company), reference.norm(symbol)) if k and len(k) >= 3]
    hits = [n for nn, n in by_norm.items() for k in keys if k in nn]
    hits = list(dict.fromkeys(hits))
    return hits[0] if len(hits) == 1 else ""


# --------------------------------------------------------------------------- writing to Tally

def parse_response(text: str) -> dict:
    """Counts and error lines from Tally's import reply."""
    def num(tag):
        m = re.search(rf"<{tag}>\s*(-?\d+)\s*</{tag}>", text or "")
        return int(m.group(1)) if m else 0
    import html as _html
    errs = [_html.unescape(re.sub(r"\s+", " ", e).strip()) for e in re.findall(r"<LINEERROR>(.*?)</LINEERROR>", text or "", re.S)]
    return {"created": num("CREATED"), "altered": num("ALTERED"), "errors": num("ERRORS") + (0 if num("ERRORS") else
            len(errs)), "exceptions": num("EXCEPTIONS"), "lines": errs, "raw": (text or "")[:2000]}


def _import_envelope(report: str, company: str, body: str) -> str:
    comp = f"<STATICVARIABLES><SVCURRENTCOMPANY>{_esc(company)}</SVCURRENTCOMPANY></STATICVARIABLES>" if company else ""
    return ("<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA><REQUESTDESC>"
            f"<REPORTNAME>{report}</REPORTNAME>{comp}</REQUESTDESC><REQUESTDATA>{body}</REQUESTDATA></IMPORTDATA>"
            "</BODY></ENVELOPE>")


def ledger_xml(name: str, parent: str, company: str = "") -> str:
    body = (f'<TALLYMESSAGE xmlns:UDF="TallyUDF"><LEDGER NAME="{_esc(name)}" ACTION="Create">'
            f"<NAME.LIST><NAME>{_esc(name)}</NAME></NAME.LIST><PARENT>{_esc(parent)}</PARENT>"
            "<ISBILLWISEON>No</ISBILLWISEON><AFFECTSSTOCK>No</AFFECTSSTOCK></LEDGER></TALLYMESSAGE>")
    return _import_envelope("All Masters", company, body)


def create_ledger(name: str, parent: str, company: str = "", url: str = URL) -> dict:
    res = parse_response(_post(ledger_xml(name, parent, company), url))
    if res["errors"] or not (res["created"] or res["altered"]):
        raise ValueError("Tally did not create the ledger: " + ("; ".join(res["lines"]) or res["raw"][:300]))
    return res


def import_vouchers(xml: str, url: str = URL) -> dict:
    return parse_response(_post(xml, url, timeout=120))
