"""Contract notes to Tally Prime vouchers.

One voucher (Journal by default) per contract note:
  Purchase of a script   Dr  the script's ledger      net cost (charges added to cost), whole rupees
  Sale of a script       Cr  the script's ledger      FIFO cost of the shares sold
                         Cr  short / long term gain   profit (Dr when it is a loss)
  Broker                 Cr  net payable / Dr net receivable, so the voucher balances
If charges are not added to cost, purchases and sales are at gross value and all charges of the
note go to the charges ledger.
Each exported note is remembered (per Tally company), so it is never sent twice.
"""
from __future__ import annotations

import json
from datetime import datetime
from xml.sax.saxutils import escape

import pandas as pd

from . import fifo, tally_match

SCHEMA = """
CREATE TABLE IF NOT EXISTS tally_exports (company TEXT, note_id INTEGER, remote_id TEXT, at TEXT, how TEXT,
    PRIMARY KEY (company, note_id));
"""


def ensure(store):
    store.db.executescript(SCHEMA)
    tally_match.ensure(store)


def exported(store, company: str) -> dict:
    ensure(store)
    return {r["note_id"]: r["at"] for r in store.query("SELECT note_id, at FROM tally_exports WHERE company=?",
                                                       (company,))}


def mark(store, company: str, note_ids, how: str):
    now = datetime.now().isoformat(timespec="seconds")
    with store.db:
        store.db.executemany("INSERT OR REPLACE INTO tally_exports VALUES (?,?,?,?,?)",
                             [(company, n, f"CNM-{n}", now, how) for n in note_ids])


def unmark(store, company: str, note_ids):
    with store.db:
        store.db.executemany("DELETE FROM tally_exports WHERE company=? AND note_id=?", [(company, n) for n in note_ids])


def broker_ledgers(cfg: dict) -> dict:
    v = cfg.get("broker_ledgers") or {}
    return v if isinstance(v, dict) else json.loads(v)


def plan(store, pan: str | None, d_from: str | None, d_to: str | None, cfg: dict) -> list[dict]:
    """Vouchers for the contract notes of the person / period, each with its entries and any problems."""
    ensure(store)
    company = cfg.get("company", "")
    known = set(tally_match.ledgers(store, company)["name"]) if company else set()
    led = {r["key"]: r["ledger"] for _, r in tally_match.match_all(store, company, cfg.get("investment_group")
                                                                    or "Investments").iterrows() if r["ledger"]}
    bl = broker_ledgers(cfg)
    done = exported(store, company)
    q = "SELECT * FROM notes WHERE 1=1"
    args = []
    if pan:
        q += " AND pan=?"
        args.append(pan)
    if d_from:
        q += " AND trade_date>=?"
        args.append(d_from)
    if d_to:
        q += " AND trade_date<=?"
        args.append(d_to)
    notes = store.query(q + " ORDER BY trade_date, id", tuple(args))
    sale_cost = {}
    for p in {n["pan"] for n in notes if n["pan"]}:
        sale_cost.update(fifo.sales(store, p))
    names = {r["isin"]: (r["symbol"], r["company_name"]) for r in
             store.query("SELECT isin, symbol, company_name FROM scrip_master")}
    cap = bool(cfg.get("capitalise_charges", True))
    out = []
    for n in notes:
        lines = store.query("SELECT * FROM scrips WHERE note_id=? ORDER BY side, symbol", (n["id"],))
        entries, problems, words = [], [], []
        gains = {}
        charges = 0.0
        for s in lines:
            sym = names.get(s["isin"], (s["symbol"], ""))[0] or s["symbol"]
            ledger = led.get(s["isin"], "")
            if not ledger:
                problems.append({"kind": "script", "key": s["isin"], "symbol": sym,
                                 "company": names.get(s["isin"], ("", ""))[1] or "",
                                 "why": f"no Tally ledger for {sym}"})
                ledger = f"?? {sym}"
            gross = float(s["gross"] or 0)
            if s["side"] == "BUY":
                amt = int(s["net_rupees"]) if cap else int(round(gross))
                entries.append((ledger, amt))
                words.append(f"Bought {s['qty']:g} {sym} @ {gross / s['qty']:.2f}")
            else:
                proceeds = int(s["net_rupees"]) if cap else int(round(gross))
                fc = sale_cost.get((n["id"], s["isin"]), {"cost": 0, "st_cost": 0, "short": float(s["qty"])})
                cost = int(fc["cost"])
                st_cost = int(fc["st_cost"])
                lt_cost = cost - st_cost
                if fc.get("short", 0) > 1e-9:
                    problems.append({"kind": "cost", "key": s["isin"], "symbol": sym,
                                     "why": f"{sym}: {fc['short']:g} shares sold were never bought (add opening "
                                            f"holdings)"})
                entries.append((ledger, -cost))
                # split the profit in proportion to the quantity sold from short / long term lots
                qty = float(s["qty"])
                st_share = (fc.get("st_qty", 0) / qty) if qty else 0
                st_gain = int(round(proceeds * st_share)) - st_cost
                lt_gain = (proceeds - int(round(proceeds * st_share))) - lt_cost
                for gl, gv in ((cfg.get("gain_ledger_st") or "Short Term Capital Gain", st_gain),
                               (cfg.get("gain_ledger_lt") or "Long Term Capital Gain", lt_gain)):
                    if gv:
                        gains[gl] = gains.get(gl, 0) + gv
                words.append(f"Sold {s['qty']:g} {sym} @ {gross / s['qty']:.2f}")
            charges += float(s["total_charges"] or 0)
        for gl, gv in gains.items():               # profit is a credit, loss a debit
            if gv:
                entries.append((gl, -gv))
        if not cap and charges:
            entries.append((cfg.get("charges_ledger") or "Brokerage and Share Transaction Charges",
                            int(round(charges))))
        broker = bl.get(n["broker"]) or ""
        if not broker:
            problems.append({"kind": "broker", "key": n["broker"], "why": f"no Tally ledger chosen for broker "
                                                                          f"{n['broker']}"})
            broker = f"?? {n['broker']}"
        bal = -sum(a for _, a in entries)
        entries.append((broker, bal))
        for name, _ in entries:
            if company and known and not name.startswith("??") and name not in known:
                problems.append({"kind": "missing", "key": name, "why": f"ledger '{name}' is not in Tally"})
        status = ("Exported " + done[n["id"]][:10] if n["id"] in done else "Problem" if problems else "Ready")
        out.append({"note_id": n["id"], "date": n["trade_date"], "cn_no": n["cn_no"], "broker": n["broker"],
                    "client": n["client_name"], "pan": n["pan"], "entries": entries, "problems": problems,
                    "narration": f"Contract note {n['cn_no']} dated {n['trade_date']} of {n['broker']} "
                                 f"({n['client_name']}): " + "; ".join(words),
                    "status": status})
    return out


def table(vouchers: list[dict]) -> pd.DataFrame:
    rows = []
    for v in vouchers:
        for led, amt in v["entries"]:
            rows.append({"_note": v["note_id"], "Date": v["date"], "Contract Note": v["cn_no"], "Broker": v["broker"],
                         "Ledger": led, "Debit (Rs)": amt if amt > 0 else None, "Credit (Rs)": -amt if amt < 0 else None,
                         "Status": v["status"]})
    return pd.DataFrame(rows, columns=["_note", "Date", "Contract Note", "Broker", "Ledger", "Debit (Rs)",
                                       "Credit (Rs)", "Status"])


def xml(vouchers: list[dict], company: str, vtype: str = "Journal") -> str:
    parts = []
    for v in vouchers:
        d = v["date"].replace("-", "")
        led = []
        for name, amt in v["entries"]:
            if not amt:
                continue
            dr = amt > 0
            led.append("<ALLLEDGERENTRIES.LIST>"
                       f"<LEDGERNAME>{escape(name)}</LEDGERNAME>"
                       f"<ISDEEMEDPOSITIVE>{'Yes' if dr else 'No'}</ISDEEMEDPOSITIVE>"
                       f"<AMOUNT>{-amt:.2f}</AMOUNT>"
                       "</ALLLEDGERENTRIES.LIST>")
        parts.append(f'<TALLYMESSAGE xmlns:UDF="TallyUDF"><VOUCHER REMOTEID="CNM-{v["note_id"]}" '
                     f'VCHTYPE="{escape(vtype)}" ACTION="Create" OBJVIEW="Accounting Voucher View">'
                     f"<DATE>{d}</DATE><EFFECTIVEDATE>{d}</EFFECTIVEDATE>"
                     f"<VOUCHERTYPENAME>{escape(vtype)}</VOUCHERTYPENAME>"
                     f"<REFERENCE>{escape(str(v['cn_no']))}</REFERENCE>"
                     f"<NARRATION>{escape(v['narration'][:1000])}</NARRATION>"
                     f"<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>{''.join(led)}</VOUCHER></TALLYMESSAGE>")
    comp = f"<STATICVARIABLES><SVCURRENTCOMPANY>{escape(company)}</SVCURRENTCOMPANY></STATICVARIABLES>" if company else ""
    return ("<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA><REQUESTDESC>"
            f"<REPORTNAME>Vouchers</REPORTNAME>{comp}</REQUESTDESC><REQUESTDATA>{''.join(parts)}</REQUESTDATA>"
            "</IMPORTDATA></BODY></ENVELOPE>")
