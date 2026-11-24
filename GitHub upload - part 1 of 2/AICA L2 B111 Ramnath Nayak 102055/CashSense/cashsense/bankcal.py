"""Bank working-day calendar: Sundays, 2nd/4th Saturdays and the holidays stored in the database."""
from __future__ import annotations

from datetime import date

from .db.adapter import Database


def holidays(db: Database) -> dict[date, str]:
    return {date.fromisoformat(h["holiday_date"]): h["name"] for h in db.query("bank_holidays")}


def non_working_reason(d: date, hol: dict[date, str]) -> str | None:
    if d in hol:
        return f"bank holiday ({hol[d]})"
    if d.weekday() == 6:
        return "Sunday"
    if d.weekday() == 5 and (d.day - 1) // 7 + 1 in (2, 4):
        return f"{'2nd' if (d.day - 1) // 7 == 1 else '4th'} Saturday (bank holiday)"
    return None
