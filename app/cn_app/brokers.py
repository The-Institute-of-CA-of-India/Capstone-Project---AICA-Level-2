"""Broker list used by every drop-down (passwords, portal logins, reconciliations)."""
from __future__ import annotations

from datetime import datetime

DEFAULTS = ["IIFL Capital Services", "Zerodha Broking", "PhillipCapital (India)", "Kotak Securities",
            "ICICI Securities", "HDFC Securities", "Angel One", "Motilal Oswal", "Inventure Growth", "Upstox",
            "Groww", "Sharekhan", "Axis Securities", "5paisa", "SBI Securities", "Nuvama Wealth", "Dhan"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS brokers (name TEXT PRIMARY KEY, added_by TEXT, added_at TEXT);
"""


def ensure(store):
    store.db.executescript(SCHEMA)
    if not store.query("SELECT 1 FROM brokers LIMIT 1"):
        now = datetime.now().isoformat(timespec="seconds")
        store.db.executemany("INSERT OR IGNORE INTO brokers VALUES (?,?,?)", [(b, "built-in", now) for b in DEFAULTS])
        store.db.commit()


def names(store) -> list[str]:
    ensure(store)
    have = {r["name"] for r in store.query("SELECT name FROM brokers")}
    have |= {r["broker"] for r in store.query("SELECT DISTINCT broker FROM notes")}
    return sorted(have, key=str.lower)


def add(store, name: str) -> str:
    name = " ".join((name or "").split())
    if len(name) < 2:
        raise ValueError("enter the broker's name")
    ensure(store)
    if any(n.lower() == name.lower() for n in names(store)):
        raise ValueError(f"'{name}' is already in the list")
    store.db.execute("INSERT INTO brokers VALUES (?,?,?)", (name, "user", datetime.now().isoformat(timespec="seconds")))
    store.db.commit()
    store.log(name, "Broker added", "added to the broker list")
    return name


def remove(store, name: str) -> None:
    store.db.execute("DELETE FROM brokers WHERE name=? AND added_by='user'", (name,))
    store.db.commit()
