"""Kotak Securities HTML contract note (one table cell per text line)."""
from __future__ import annotations

import re

from ..models import ContractNote, Trade
from ..utils import is_num, num, to_date
from .base import ParseError, lines, scrips_from_trades

BROKER = "Kotak Securities"
ISIN = re.compile(r"^IN[A-Z0-9]{10}$")


def detect(text: str) -> str | None:
    return "html" if "Kotak Securities" in text[:3000] and "CONTRACT NOTE" in text[:3000] else None


def _after(L, label, offset=0):
    for i, ln in enumerate(L):
        if ln.upper().startswith(label):
            return i
    return -1


def parse(text: str, layout: str) -> list[ContractNote]:
    L = lines(text)
    cn = ContractNote(broker=BROKER, format_name="Kotak Securities (HTML)", cn_no="", trade_date="")

    # header: labels listed first, values follow in the same order prefixed with ':'
    i = _after(L, "PAN NO")
    if i < 0:
        raise ParseError("Header block not found")
    labels, j = [], i
    while not L[j].startswith(":"):
        labels.append(L[j].upper()); j += 1
    vals = {}
    for lab in labels:
        vals[lab] = re.sub(r"\s+", "", L[j].lstrip(":")).rstrip("."); j += 1
    cn.pan = vals.get("PAN NO", "")
    cn.cn_no = vals.get("CONTRACT NOTE NO.", "")
    cn.trade_date = to_date(vals.get("TRADE DATE", ""))
    cn.settlement_no = vals.get("SETTLEMENT NO", "")
    cn.settlement_date = to_date(vals.get("SETTLEMENT DATE", "") or vals.get("TRADE DATE"))
    k = _after(L, "UCC CODE")
    cn.ucc = L[k].split(":", 1)[1].strip() if k >= 0 else ""
    k = _after(L, "TO,")
    if k >= 0:
        cn.client_name = re.sub(r"^\S+/\S+\s+", "", L[k + 1]).strip()

    # trade blocks end with the ISIN line
    for idx, ln in enumerate(L):
        if not ISIN.match(ln):
            continue
        name, side, qty, rate, brok, netrate, nettotal = L[idx - 7:idx]
        if side.upper() not in ("BUY", "SELL") or not all(is_num(x) for x in (qty, rate, brok)):
            continue
        exch = L[idx - 12] if L[idx - 12] in ("NSE", "BSE") else ""
        refs = L[idx - 11:idx - 7]
        cn.trades.append(Trade(order_no=refs[0], order_time=refs[1], trade_no=refs[2], trade_time=refs[3],
                               exchange=exch, symbol=name, isin=ln, side=side.upper(),
                               qty=abs(num(qty)), rate=num(rate), brokerage_per_unit=num(brok)))
    if not cn.trades:
        raise ParseError("No trade rows found")
    cn.scrips = scrips_from_trades(cn.trades)
    for s in cn.scrips:
        s.name_on_note = s.symbol

    def amount_after(label):
        k = _after(L, label)
        return abs(num(L[k + 1])) if k >= 0 and is_num(L[k + 1]) else 0.0

    c = cn.charges
    c["brokerage"] = amount_after("TAXABLE VALUE OF SUPPLY (BROKERAGE)")
    c["exchange"] = amount_after("TRANSACTION CHARGES + SEBI FEES+IPFT")
    c["igst"] = amount_after("IGST")
    c["cgst"] = amount_after("CGST (")
    c["sgst"] = amount_after("SGST (")
    c["stt"] = amount_after("STT")
    c["stamp"] = amount_after("STAMP DUTY (")
    cn.combined_charges = True
    cn.notes.append("Kotak prints transaction charges, SEBI fees and IPF as one combined figure (shown under Exchange)")

    k = next((n for n, ln in enumerate(L) if "Net amount" in ln and "Client" in ln), -1)
    if k < 0:
        raise ParseError("Net amount not found")
    amt = abs(num(L[k + 1]))
    cn.net_amount = -amt if "receivable" in L[k].lower() else amt
    return [cn]
