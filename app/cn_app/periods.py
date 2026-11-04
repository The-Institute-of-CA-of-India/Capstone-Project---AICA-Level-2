"""Period selection: financial-year presets and custom ranges.

A period key is one of:
    "all"                      everything
    "FY2025"                   01-04-2025 to 31-03-2026
    "C:2025-04-01:2025-09-30"  custom range (ISO dates)
"""
from __future__ import annotations

from datetime import date


def fy_of(d: date) -> int:
    return d.year if d.month >= 4 else d.year - 1


def label(key: str) -> str:
    if not key or key == "all":
        return "All periods"
    if key.startswith("FY"):
        y = int(key[2:])
        return f"FY {y}-{str(y + 1)[2:]}"
    if key.startswith("C:"):
        _, a, b = key.split(":")
        return f"{_dmy(a)} to {_dmy(b)}"
    return key


def _dmy(iso: str) -> str:
    return f"{iso[8:10]}-{iso[5:7]}-{iso[:4]}" if iso and len(iso) == 10 else iso


def bounds(key: str) -> tuple[str | None, str | None]:
    """(from, to) as ISO strings, or (None, None) for all periods."""
    if not key or key == "all":
        return None, None
    if key.startswith("FY"):
        y = int(key[2:])
        return f"{y}-04-01", f"{y + 1}-03-31"
    if key.startswith("C:"):
        _, a, b = key.split(":")
        return a or None, b or None
    return None, None


def options(first_iso: str | None = None) -> dict:
    """Presets from the first financial year with data up to the current one, newest first."""
    today = date.today()
    last = fy_of(today)
    first = last - 3
    if first_iso:
        try:
            first = min(first, fy_of(date.fromisoformat(first_iso[:10])))
        except ValueError:
            pass
    opts = {"all": "All periods"}
    for y in range(last, first - 1, -1):
        opts[f"FY{y}"] = label(f"FY{y}")
    return opts


def in_period(iso: str, frm: str | None, to: str | None) -> bool:
    if not iso:
        return True
    return (frm is None or iso >= frm) and (to is None or iso <= to)
