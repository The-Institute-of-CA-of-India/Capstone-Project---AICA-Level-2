"""PhillipCapital: ISIN-wise contract note plus separate exchange annexure PDFs."""
from __future__ import annotations

import re

from ..models import ContractNote, ScripSide, Trade
from ..utils import num, to_date
from .base import ParseError, find, lines, need

BROKER = "PhillipCapital (India)"
N = r"[-−(]?[\d,]*\.?\d+\)?"

_SUMMARY = re.compile(
    rf"^(IN[A-Z0-9]{{10}})\s+(.+?)\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})$")
_ANNEX = re.compile(
    rf"^(\d+)\s+([\d:]+)\s+(\d+)\s+([\d:]+)\s+(.+?)\s+-\s+(\w+)\s+(BUY|SELL)\s+({N})\s+({N})\s+({N})$", re.I)

_CHARGES = {
    "stt": r"Securities Transaction Tax",
    "cgst": r"CGST",
    "sgst": r"SGST",
    "igst": r"IGST",
    "exchange": r"Exchange Transaction Charges",
    "clearing": r"Clearing Charges",
    "sebi": r"SEBI turnover Fees",
    "stamp": r"Stamp Duty",
    "ipf": r"(?:IPFT|Investor Protection)",
}


def detect(text: str) -> str | None:
    head = text[:2500].upper()
    if "PHILLIPCAPITAL" not in head:
        return None
    if "CONTRACT ANNEXURE" in head:
        return "annexure"
    if "CONTRACT NOTE" in head:
        return "note"
    return None


def parse_annexure(text: str):
    """Return (ucc, cn_no, trades-without-ISIN) for linking to the main note."""
    ucc = find(r"Client Code:\s*(\S+)", text)
    cn_no = find(r"Contract No:\s*(\S+)", text)
    exch = "BSE" if "FOR BSE" in text.upper() else "NSE"
    trades = []
    for ln in lines(text.replace("&amp;", "&")):
        m = _ANNEX.match(ln)
        if m:
            g = m.groups()
            trades.append(Trade(order_no=g[0], order_time=g[1], trade_no=g[2], trade_time=g[3],
                                exchange=exch, symbol=g[4].strip(), isin="", side=g[6].upper(),
                                qty=abs(num(g[7])), rate=num(g[8])))
    return ucc, cn_no, trades


def parse(text: str, layout: str) -> list[ContractNote]:
    cn = ContractNote(broker=BROKER, format_name="PhillipCapital (Contract Note cum Tax Invoice)", cn_no="", trade_date="")
    cn.cn_no = need(r"CONTRACT NOTE NO\.\s*(\S+)", text, "contract note number")
    cn.trade_date = to_date(need(r"TRADE DATE\s+([\d/]+)", text, "trade date"))
    cn.settlement_date = to_date(find(r"SETTLEMENT DATE\.\s*([\d/]+)", text) or cn.trade_date)
    cn.settlement_no = find(r"SETTLEMENT NO\.\s*NA\s+(\d+)", text)
    cn.pan = find(r"PAN of Client\.?:\s*([A-Z]{5}\d{4}[A-Z])", text)
    cn.ucc = find(r"UCC of Client:\s*(\S+)", text)
    cn.client_name = find(r"\n([A-Z .&]+)\(" + re.escape(cn.ucc) + r"\)", text) if cn.ucc else ""

    for ln in lines(text):
        m = _SUMMARY.match(ln)
        if not m:
            continue
        g = m.groups()
        for side, qty, brok_pu, value in (("BUY", g[2], g[4], g[6]), ("SELL", g[7], g[9], g[11])):
            q = num(qty)
            if q == 0:
                continue
            after, bpu = num(value), num(brok_pu)
            gross = after - q * bpu if side == "BUY" else after + q * bpu
            cn.scrips.append(ScripSide(isin=g[0], symbol=g[1].strip(), side=side, qty=q,
                                       gross=round(gross, 4), brokerage_direct=round(q * bpu, 4),
                                       name_on_note=g[1].strip()))
    if not cn.scrips:
        raise ParseError("No ISIN rows found")

    body = text.split("Obligation Details", 1)[-1]
    for ln in lines(body):
        for key, label in _CHARGES.items():
            if re.match(label, ln, re.I):
                nums = re.findall(N, ln.split(")", 1)[-1] if "(" in ln else ln)
                if nums:
                    cn.charges[key] = abs(num(nums[-1]))
    # brokerage is inside the net rates; the note shows no separate brokerage line
    cn.charges["brokerage"] = round(sum(s.brokerage_direct for s in cn.scrips), 2)

    m = re.search(rf"\(payable by Client\) \(Rs\.\)\s*({N})", text)
    if not m:
        raise ParseError("Net amount line not found")
    cn.net_amount = -num(m.group(1))       # Phillip prints receivable as positive
    cn.notes.append("Annexure trades linked separately")
    return [cn]


def link_annexure(cn: ContractNote, trades: list[Trade]) -> None:
    """Attach annexure fills to the note, taking ISIN from the matching scrip name."""
    for t in trades:
        match = next((s for s in cn.scrips if s.side == t.side and
                      (t.symbol.upper().startswith(s.symbol.upper()[:15]) or
                       s.symbol.upper().startswith(t.symbol.upper()[:15]))), None)
        if match:
            t.isin = match.isin
            match.exchanges = ", ".join(sorted(set(filter(None, match.exchanges.split(", "))) | {t.exchange}))
            cn.trades.append(t)
    for s in cn.scrips:
        g = sum(t.gross for t in cn.trades if t.isin == s.isin and t.side == s.side)
        q = sum(t.qty for t in cn.trades if t.isin == s.isin and t.side == s.side)
        if q and abs(q - s.qty) < 1e-6:
            s.gross = round(g, 4)
    cn.notes = [n for n in cn.notes if n != "Annexure trades linked separately"]
