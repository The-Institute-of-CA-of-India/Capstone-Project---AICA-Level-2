"""Case register: one row per notice with its due date and progress (local SQLite, names encrypted)."""
from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .config import APP_ROOT
from .tokens import get_or_create_key

log = logging.getLogger("mukhota.register")
DB_PATH = APP_ROOT / "register.db"
STATUSES = ["Opened", "Redacted", "Verified", "Drafted", "Filed"]

_SECTION = re.compile(r"(?i)\b(?:u/s\.?|under\s+section|section|sec\.)\s*(\d{1,3}[A-Z]{0,3}(?:\(\w{1,4}\))*)")
_AY = re.compile(r"(?i)(?:assessment\s+year|a\.?\s?y\.?)\s*[:\-]?\s*(20\d{2})\s*[-–/]\s*(?:20)?(\d{2})")
_DATE = r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})"
_NOTICE_DATE = re.compile(rf"(?i)\bdate[d]?\s*[:\-]?\s*{_DATE}")
_DUE = [
    re.compile(rf"(?i)by\s+(?:the\s+)?\d{{1,2}}[:.]\d{{2}}\s*(?:AM|PM|hrs)?\s*(?:of|on)\s+{_DATE}"),
    re.compile(rf"(?i)(?:on\s+or\s+before|latest\s+by|not\s+later\s+than|due\s+date\s*[:\-]?)\s*{_DATE}"),
    re.compile(rf"(?i)(?:submit|file|furnish)[^.]{{0,120}}?\bby\s+{_DATE}"),
]


@dataclass
class Case:
    """One register row (client and paths decrypted)."""

    id: int
    client: str
    file_name: str
    section: str
    ay: str
    notice_date: str
    due_date: str  # ISO yyyy-mm-dd or ""
    status: str
    folder: str
    updated: str

    @property
    def days_left(self) -> int | None:
        if not self.due_date:
            return None
        return (date.fromisoformat(self.due_date) - date.today()).days


def _iso(d: str, m: str, y: str) -> str:
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return ""


def extract_details(text: str) -> dict[str, str]:
    """Section, AY, notice date and reply due date read from the notice text (best effort)."""
    out = {"section": "", "ay": "", "notice_date": "", "due_date": ""}
    if m := _SECTION.search(text):
        out["section"] = m.group(1)
    if m := _AY.search(text):
        out["ay"] = f"{m.group(1)}-{m.group(2)}"
    if m := _NOTICE_DATE.search(text):
        out["notice_date"] = _iso(*m.groups())
    for pat in _DUE:
        if m := pat.search(text):
            out["due_date"] = _iso(*m.groups()[-3:])
            break
    return out


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.execute(
        "CREATE TABLE IF NOT EXISTS cases (id INTEGER PRIMARY KEY, src_sha TEXT UNIQUE, client BLOB, file BLOB, "
        "section TEXT, ay TEXT, notice_date TEXT, due_date TEXT, status TEXT, folder BLOB, updated TEXT)"
    )
    return c


def _enc(s: str) -> bytes:
    return Fernet(get_or_create_key()).encrypt(s.encode("utf-8"))


def _dec(b: bytes | None) -> str:
    if not b:
        return ""
    try:
        return Fernet(get_or_create_key()).decrypt(b).decode("utf-8")
    except InvalidToken:
        return "(locked)"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def record_opened(src_sha: str, file_name: str, text: str) -> None:
    """Add a notice when it is first opened (existing rows keep their status)."""
    d = extract_details(text)
    try:
        with _conn() as c:
            row = c.execute("SELECT id FROM cases WHERE src_sha=?", (src_sha,)).fetchone()
            if row:
                return
            c.execute(
                "INSERT INTO cases (src_sha, client, file, section, ay, notice_date, due_date, status, folder, updated) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (src_sha, _enc(""), _enc(file_name), d["section"], d["ay"], d["notice_date"], d["due_date"],
                 "Opened", _enc(""), _now()),
            )
        log.info("Register: notice added (section %s, AY %s, due date %s)", d["section"] or "?", d["ay"] or "?",
                 "found" if d["due_date"] else "not found")
    except sqlite3.Error:
        log.exception("Register update failed")


def advance(src_sha: str, status: str, client: str | None = None, folder: Path | None = None) -> None:
    """Move a notice forward to ``status`` (never backwards) and optionally set client / folder."""
    try:
        with _conn() as c:
            row = c.execute("SELECT status FROM cases WHERE src_sha=?", (src_sha,)).fetchone()
            if not row:
                return
            if STATUSES.index(status) > STATUSES.index(row[0]):
                c.execute("UPDATE cases SET status=?, updated=? WHERE src_sha=?", (status, _now(), src_sha))
            if client:
                c.execute("UPDATE cases SET client=? WHERE src_sha=?", (_enc(client), src_sha))
            if folder:
                c.execute("UPDATE cases SET folder=? WHERE src_sha=?", (_enc(str(folder)), src_sha))
    except sqlite3.Error:
        log.exception("Register update failed")


def all_cases() -> list[Case]:
    """Every notice, soonest due first (no due date last)."""
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT id, client, file, section, ay, notice_date, due_date, status, folder, updated FROM cases"
            ).fetchall()
    except sqlite3.Error:
        log.exception("Register read failed")
        return []
    cases = [Case(r[0], _dec(r[1]), _dec(r[2]), r[3] or "", r[4] or "", r[5] or "", r[6] or "", r[7], _dec(r[8]), r[9])
             for r in rows]
    return sorted(cases, key=lambda k: (k.due_date == "", k.due_date))


def update(case_id: int, *, due_date: str | None = None, status: str | None = None, client: str | None = None) -> None:
    """Manual edits from the register window."""
    with _conn() as c:
        if due_date is not None:
            c.execute("UPDATE cases SET due_date=?, updated=? WHERE id=?", (due_date, _now(), case_id))
        if status is not None:
            c.execute("UPDATE cases SET status=?, updated=? WHERE id=?", (status, _now(), case_id))
        if client is not None:
            c.execute("UPDATE cases SET client=?, updated=? WHERE id=?", (_enc(client), _now(), case_id))


def delete(case_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM cases WHERE id=?", (case_id,))


def due_soon(days: int = 7) -> list[Case]:
    """Open (not filed) notices due within ``days`` days or overdue."""
    return [k for k in all_cases() if k.status != "Filed" and k.days_left is not None and k.days_left <= days]
