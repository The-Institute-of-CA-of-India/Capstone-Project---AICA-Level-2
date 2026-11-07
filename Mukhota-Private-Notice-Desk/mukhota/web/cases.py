"""Case register and due-date reminder for the browser front end."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

from ..core import register
from ..core.models import UserFacingError


def _dmy(iso: str) -> str:
    if not iso:
        return ""
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _due(case: register.Case) -> tuple[str, str]:
    """Due text and urgency ('overdue', 'soon' or '')."""
    left = case.days_left
    if left is None:
        return "-", ""
    if case.status == "Filed":
        return (f"{left} days" if left >= 0 else "-"), ""
    if left < 0:
        return f"Overdue by {-left} day(s)", "overdue"
    if left <= 7:
        return f"{left} day(s) left", "soon"
    return f"{left} days", ""


def register_list() -> dict[str, Any]:
    cases = []
    for c in register.all_cases():
        due_txt, urgency = _due(c)
        cases.append({"id": c.id, "client": c.client, "file": c.file_name, "section": c.section, "ay": c.ay,
                      "noticeDate": _dmy(c.notice_date), "dueIso": c.due_date, "dueDate": _dmy(c.due_date),
                      "due": due_txt, "urgency": urgency, "status": c.status,
                      "hasFolder": bool(c.folder) and Path(c.folder).exists()})
    return {"cases": cases, "soon": len(register.due_soon()), "statuses": register.STATUSES}


def register_update(b: dict[str, Any]) -> None:
    due = str(b.get("due") or "")
    if due:
        try:
            date.fromisoformat(due)
        except ValueError as exc:
            raise UserFacingError("That due date is not a valid date.") from exc
    status = str(b.get("status") or "")
    if status not in register.STATUSES:
        raise UserFacingError("Unknown status.")
    register.update(int(b["id"]), due_date=due, status=status, client=str(b.get("client") or "").strip())


def register_folder(case_id: int) -> None:
    c = next((c for c in register.all_cases() if c.id == case_id), None)
    if c and c.folder and Path(c.folder).exists():
        os.startfile(c.folder)  # noqa: S606 - opens Explorer locally


def reminder(cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Notices not filed and due within 7 days or overdue (shown once when the page opens)."""
    if not cfg.get("notifications", {}).get("due_reminders", True):
        return None
    soon = register.due_soon()
    if not soon:
        return None
    overdue = sum(1 for c in soon if (c.days_left or 0) < 0)
    lines = [f"{c.client or c.file_name}: s.{c.section or '?'} AY {c.ay or '?'} - due {_dmy(c.due_date)}" for c in soon[:4]]
    return {"count": len(soon), "overdue": overdue, "lines": lines}

