"""Helpers shared by the broker parsers."""
from __future__ import annotations

import re
from collections import OrderedDict

from ..models import ScripSide, Trade


class ParseError(Exception):
    pass


def find(pattern: str, text: str, default: str = "", flags=re.I) -> str:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else default


def need(pattern: str, text: str, what: str, flags=re.I) -> str:
    val = find(pattern, text, flags=flags)
    if not val:
        raise ParseError(f"Could not find {what}")
    return val


def scrips_from_trades(trades: list[Trade]) -> list[ScripSide]:
    """Combine fills into one row per ISIN and side (BUY and SELL stay separate)."""
    groups: "OrderedDict[tuple, ScripSide]" = OrderedDict()
    for t in trades:
        key = (t.isin, t.side)
        s = groups.get(key)
        if s is None:
            s = groups[key] = ScripSide(isin=t.isin, symbol=t.symbol, side=t.side, qty=0.0, gross=0.0)
        s.qty += t.qty
        s.gross += t.gross
        s.brokerage_direct += t.qty * t.brokerage_per_unit
        exch = set(filter(None, s.exchanges.split(", "))) | {t.exchange}
        s.exchanges = ", ".join(sorted(exch))
    for s in groups.values():
        s.gross = round(s.gross, 4)
        s.brokerage_direct = round(s.brokerage_direct, 4)
    return list(groups.values())


def lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]
