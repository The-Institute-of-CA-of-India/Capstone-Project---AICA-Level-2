"""IIFL Capital Services: old 'CONTRACT NOTE' layout and new 'CONTRACT NOTE CUM TAX INVOICE' layout."""
from __future__ import annotations

import re

from ..models import ContractNote, ScripSide, Trade
from ..utils import num, to_date
from .base import ParseError, find, lines, need, scrips_from_trades

BROKER = "IIFL Capital Services"
N = r"[-−(]?[\d,]*\.?\d+\)?"


def detect(text: str) -> str | None:
    if "IIFL" not in text[:3000]:
        return None
    if "CONTRACT NOTE CUM TAX INVOICE" in text[:600]:
        return "new"
    if re.search(r"^CONTRACT NOTE$", text[:3000], re.M):
        return "old"
    return None


def parse(text: str, layout: str) -> list[ContractNote]:
    return [_parse_old(text) if layout == "old" else _parse_new(text)]


# --------------------------------------------------------------------------- common header

def _header(text: str, fmt: str) -> ContractNote:
    cn = ContractNote(broker=BROKER, format_name=fmt, cn_no="", trade_date="")
    cn.pan = find(r"PAN (?:of Client|No\.?:)\s*([A-Z]{5}\d{4}[A-Z])", text)
    cn.ucc = find(r"UCC(?: / Trading Back office code| Code:)\s*([A-Z0-9]+)", text)
    cn.cn_no = need(r"Contract Note No\.?\s*([A-Z0-9]+)", text, "contract note number")
    return cn


# --------------------------------------------------------------------------- old layout

_OLD_TRADE = re.compile(
    rf"^(\d+)\s+([\d:]+)\s+(\d+)\s+([\d:]+)\s+(.+?)\s+-\s+(IN[A-Z0-9]{{10}})\s+(NSE|BSE)\s+-\s+(Buy|Sell)\s+"
    rf"({N})\s+({N})\s+(-|{N})\s+({N})\s+({N})$", re.I)


def _parse_old(text: str) -> ContractNote:
    cn = _header(text, "IIFL old (Contract Note)")
    cn.client_name = find(r"Name of the Client\s+(.+?)\s+Trade Date", text)
    cn.trade_date = to_date(need(r"Trade Date\s+([\d/]+)", text, "trade date"))
    cn.settlement_date = to_date(find(r"Settlement Date\s+([\d/]+)", text) or need(r"Trade Date\s+([\d/]+)", text, "date"))
    cn.settlement_no = find(r"Clearing Settlement No\.\s*([A-Z0-9]+)", text)

    stt_by_isin, last_isin = {}, None
    for ln in lines(text):
        m = _OLD_TRADE.match(ln)
        if m:
            g = m.groups()
            qty = abs(num(g[8]))
            cn.trades.append(Trade(order_no=g[0], order_time=g[1], trade_no=g[2], trade_time=g[3],
                                   exchange=g[6].upper(), symbol=g[4].strip(), isin=g[5],
                                   side=g[7].upper(), qty=qty, rate=num(g[9]),
                                   brokerage_per_unit=num(g[10])))
            last_isin = g[5]
            continue
        m = re.match(rf"STT Total ::\s*({N})", ln)
        if m and last_isin:
            stt_by_isin[last_isin] = stt_by_isin.get(last_isin, 0.0) + num(m.group(1))

    if not cn.trades:
        raise ParseError("No trade lines found")
    cn.scrips = scrips_from_trades(cn.trades)
    for s in cn.scrips:
        s.stt_hint = stt_by_isin.get(s.isin)

    c = cn.charges
    c["brokerage"] = num(find(rf"Taxable value of supply -\(Brokerage\)\s*({N})", text))
    c["exchange"] = num(find(rf"Taxable value of supply -\(Exchange Transaction Charges\)\s*({N})", text))
    c["clearing"] = num(find(rf"Taxable value of supply -\(Clearing Charge\)\s*({N})", text))
    c["sebi"] = num(find(rf"Taxable value of supply -\(SEBI Turnover Fees\)\s*({N})", text))
    c["ipf"] = num(find(rf"Investor Protection Fund\s*({N})", text))
    m = re.search(rf"GST Amount\(Rs\.\)\s*({N})\s+({N})\s+({N})", text)
    if m:  # header order on the note is SGST, CGST, IGST
        c["sgst"], c["cgst"], c["igst"] = (num(x) for x in m.groups())
    c["stamp"] = num(find(rf"Stamp Duty Rs\.\s*({N})", text))
    c["stt"] = num(find(rf"Security Transaction Tax Rs\.\s*({N})", text))

    m = re.search(rf"Net amount (payable|receivable) by Client - Rs\.\s*({N})\s*(Dr|Cr)?", text, re.I)
    if not m:
        raise ParseError("Net amount line not found")
    amt = abs(num(m.group(2)))
    cn.net_amount = amt if (m.group(3) or "").upper() == "DR" or m.group(1).lower() == "payable" else -amt
    return cn


# --------------------------------------------------------------------------- new layout

_NEW_SUMMARY = re.compile(
    rf"^(IN[A-Z0-9]{{10}})\s+(\S+)\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})$")
_NEW_TRADE = re.compile(
    rf"^(\d+)\s+([\d:]+)\s+(\d+)\s+([\d:]+)\s+(.+?)\s+(NSE|BSE)-(BUY|SELL)\s+({N})\s+({N})\s+({N})(?:\s+.*)?$", re.I)

_NEW_CHARGES = {
    "brokerage": r"Brokerage-\(Taxable value of supply\)3?",
    "exchange": r"Exchange Transaction Charges-\(Taxable value\s+(?:of supply\)3?\s*)?",
    "clearing": r"Clearing Charge-\(Taxable value of supply\)3?",
    "sebi": r"SEBI Turnover Fees-\(Taxable value of supply\)3?",
    "ipf": r"Investor Protection Fund-\(Taxable value of\s+(?:supply\)3?\s*)?",
    "sgst": r"SGST\*\s*\(9%\)",
    "cgst": r"CGST\*\s*\(9%\)",
    "igst": r"IGST\*\s*\(18%\)",
    "stamp": r"Stamp Duty",
    "stt": r"Security Transaction Tax",
}


def _charge(text: str, label: str) -> float:
    # value may sit on the same line or after a wrapped label line
    m = re.search(rf"{label}\s*({N})\s+({N})", text)
    return num(m.group(2)) if m else 0.0


def _parse_new(text: str) -> ContractNote:
    cn = _header(text, "IIFL new (Contract Note cum Tax Invoice)")
    cn.trade_date = to_date(need(r"TRADE DATE\s+([A-Za-z]{3} \d{1,2} \d{4}|[\d/]+)", text, "trade date"))
    cn.settlement_date = to_date(find(r"Settlement Date\s+([\d/]+)", text) or cn.trade_date)
    cn.settlement_no = find(r"Settlement No\s+([A-Z0-9]+)", text)
    m = re.search(r"TRADE DATE.*\n(.+)\n", text)
    cn.client_name = m.group(1).strip() if m else ""

    summary = {}
    for ln in lines(text):
        m = _NEW_SUMMARY.match(ln)
        if m:
            g = m.groups()
            summary[g[1]] = g
    if not summary:
        raise ParseError("No ISIN summary rows found")

    # annexure trade lines (symbol only; ISIN comes from the summary)
    for ln in lines(text):
        m = _NEW_TRADE.match(ln)
        if not m:
            continue
        g = m.groups()
        sym = g[4].strip()
        if sym not in summary:
            continue
        cn.trades.append(Trade(order_no=g[0].lstrip("*"), order_time=g[1], trade_no=g[2], trade_time=g[3],
                               exchange=g[5].upper(), symbol=sym, isin=summary[sym][0],
                               side=g[6].upper(), qty=abs(num(g[7])), rate=num(g[8])))

    by_trades = {(s.isin, s.side): s for s in scrips_from_trades(cn.trades)}
    for sym, g in summary.items():
        isin = g[0]
        for side, qty, wap, brok_pu, value in (("BUY", g[2], g[3], g[4], g[6]), ("SELL", g[7], g[8], g[9], g[11])):
            q = num(qty)
            if q == 0:
                continue
            after = num(value)
            t = by_trades.get((isin, side))
            if t and abs(t.qty - q) < 1e-6:
                gross, exch = t.gross, t.exchanges
            else:  # annexure missing: rebuild gross from value after brokerage
                gross, exch = after - q * num(brok_pu) if side == "BUY" else after + q * num(brok_pu), ""
                cn.notes.append(f"{sym} {side}: annexure trades not matched, gross derived from summary")
            brok = (after - gross) if side == "BUY" else (gross - after)
            cn.scrips.append(ScripSide(isin=isin, symbol=sym, side=side, qty=q, gross=round(gross, 4),
                                       brokerage_direct=round(max(brok, 0.0), 4), exchanges=exch))

    for key, label in _NEW_CHARGES.items():
        cn.charges[key] = _charge(text, label)

    m = re.search(rf"Net Amount (Payable|Receivable) by Client\s+({N})\s*(Dr|Cr)", text, re.I)
    if not m:
        raise ParseError("Net amount line not found")
    amt = abs(num(m.group(2)))
    cn.net_amount = amt if m.group(3).upper() == "DR" else -amt
    return cn
