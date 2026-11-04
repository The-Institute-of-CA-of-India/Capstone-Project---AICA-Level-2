"""PDF passwords, entered per broker in Settings and tried on every protected contract note."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pdf_passwords (
    id INTEGER PRIMARY KEY AUTOINCREMENT, broker TEXT, password TEXT NOT NULL, updated_at TEXT,
    UNIQUE (broker, password));
"""


def ensure(store, legacy_file: Path | None = None):
    store.db.executescript(SCHEMA)
    if legacy_file and legacy_file.exists():          # passwords.txt from version 1.0 - 1.3
        for line in legacy_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip():
                store.db.execute("INSERT OR IGNORE INTO pdf_passwords(broker, password, updated_at) VALUES (?,?,?)",
                                 ("Any broker", line.strip(), datetime.now().isoformat(timespec="seconds")))
        store.db.commit()
        legacy_file.rename(legacy_file.with_suffix(".txt.migrated"))


def rows(store) -> list[dict]:
    store.db.executescript(SCHEMA)
    return store.query("SELECT id, broker, password FROM pdf_passwords ORDER BY broker, id")


def save_all(store, entries: list[tuple[str, str]]) -> int:
    """Replace the list with (broker, password) pairs; empty passwords are ignored."""
    store.db.executescript(SCHEMA)
    now = datetime.now().isoformat(timespec="seconds")
    with store.db:
        store.db.execute("DELETE FROM pdf_passwords")
        n = 0
        for broker, pw in entries:
            pw = (pw or "").strip()
            if pw:
                store.db.execute("INSERT OR IGNORE INTO pdf_passwords(broker, password, updated_at) VALUES (?,?,?)",
                                 ((broker or "").strip() or "Any broker", pw, now))
                n += 1
    return n


def all_passwords(store) -> list[str]:
    """Every saved password plus each client's PAN and client codes (common broker passwords)."""
    store.db.executescript(SCHEMA)
    out = [r["password"] for r in rows(store)]
    for c in store.query("SELECT pan, ucc_list FROM clients"):
        out += [c["pan"]] + [u for u in (c["ucc_list"] or "").split(",") if u]
    seen, uniq = set(), []
    for p in out:
        if p and p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq
