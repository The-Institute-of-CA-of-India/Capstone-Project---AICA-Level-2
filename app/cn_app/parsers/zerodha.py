"""Zerodha Broking: one PDF may hold several contract notes (e.g. a yearly download)."""
from __future__ import annotations

import re

from ..models import ContractNote, ScripSide, Trade
from ..utils import num, to_date
from .base import ParseError, find, lines, need, scrips_from_trades

BROKER = "Zerodha Broking"
N = r"[-−(]?[\d,]*\.?\d+\)?"

_SUMMARY = re.compile(
    rf"^(IN[A-Z0-9]{{10}})\s+(\S+)\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})$")
_TRADE = re.compile(
    rf"^(\d+)\s+([\d:]+)\s+(\d+)\s+([\d:]+)\s+(\S+?)-(\w+)/(IN[A-Z0-9]{{10}})\s+(B|S)\s+(NSE|BSE)\s+({N})\s+({N})\s+({N})\s+({N})")

_CHARGES = {
    "brokerage": r"Taxable value of Supply \(Brokerage\)",
    "exchange": r"Exchange transaction charges",   # includes IPF for NSE
    "clearing": r"Clearing charges",
    "cgst": r"CGST \(",
    "sgst": r"SGST \(",
    "igst": r"IGST \(",
    "stt": r"Securities transaction tax",
    "sebi": r"SEBI turnover fees",
    "stamp": r"Stamp duty",
}


def detect(text: str) -> str | None:
    return "zerodha" if "Zerodha Broking Limited" in text[:1500] else None


def _last_number(line: str) -> float:
    tail = line.split("(₹)")[-1]          # skip the label and its footnote digit
    tail = re.sub(r"^\s*\d(?=\s|$)", "", tail)  # footnote like '(₹)4 (19.32)'
    nums = re.findall(N, tail)
    return num(nums[-1]) if nums else 0.0


def parse(text: str, layout: str) -> list[ContractNote]:
    chunks = re.split(r"(?=CONTRACT NOTE CUM TAX INVOICE)", text)
    notes = [_parse_one(c) for c in chunks if "Contract Note No" in c]
    if not notes:
        raise ParseError("No Zerodha contract note found")
    return notes


def _parse_one(text: str) -> ContractNote:
    cn = ContractNote(broker=BROKER, format_name="Zerodha (Contract Note cum Tax Invoice)", cn_no="", trade_date="")
    cn.cn_no = need(r"Contract Note No:\s*(\S+)", text, "contract note number")
    cn.trade_date = to_date(need(r"Trade Date:\s*([\d/]+)", text, "trade date"))
    cn.settlement_date = to_date(find(r"Settlement Date:\s*([\d/]+)", text) or cn.trade_date)
    cn.settlement_no = find(r"Settlement No:\s*(\S+)", text)
    cn.pan = find(r"PAN:\s*([A-Z]{5}\d{4}[A-Z])", text)
    cn.ucc = find(r"UCC:\s*(\S+)", text)
    cn.client_name = find(r"Dear (.+?),", text)
    cn.combined_charges = False
    cn.notes.append("Zerodha exchange transaction charges include IPF")

    summary = []
    for ln in lines(text):
        m = _SUMMARY.match(ln)
        if m:
            summary.append(m.groups())
            continue
        m = _TRADE.match(ln)
        if m:
            g = m.groups()
            cn.trades.append(Trade(order_no=g[0], order_time=g[1], trade_no=g[2], trade_time=g[3],
                                   exchange=g[8], symbol=g[4], isin=g[6],
                                   side="BUY" if g[7] == "B" else "SELL", qty=abs(num(g[9])),
                                   rate=num(g[11]), brokerage_per_unit=num(g[10])))
    if not summary:
        raise ParseError(f"{cn.cn_no}: no ISIN summary rows")

    by_trades = {(s.isin, s.side): s for s in scrips_from_trades(cn.trades)}
    for g in summary:
        for side, qty, brok_pu, value in (("BUY", g[2], g[4], g[6]), ("SELL", g[7], g[9], g[11])):
            q = num(qty)
            if q == 0:
                continue
            after = num(value)
            t = by_trades.get((g[0], side))
            if t and abs(t.qty - q) < 1e-6:
                gross, exch = t.gross, t.exchanges
            else:
                gross = after - q * num(brok_pu) if side == "BUY" else after + q * num(brok_pu)
                exch = ""
            brok = (after - gross) if side == "BUY" else (gross - after)
            cn.scrips.append(ScripSide(isin=g[0], symbol=g[1], side=side, qty=q, gross=round(gross, 4),
                                       brokerage_direct=round(max(brok, 0.0), 4), exchanges=exch))

    for ln in lines(text):
        for key, label in _CHARGES.items():
            if re.match(label, ln, re.I):
                cn.charges[key] = abs(_last_number(ln))
        if ln.lower().startswith("net amount receivable/(payable by client)"):
            cn.net_amount = -_last_number(ln)   # brackets = payable -> positive in our convention
    return cn
