"""Persons: names used in holding sheets mapped to PAN.

A name like "Ramesh HUF" is matched automatically to a client already known from
contract notes ("RAMESH KUMAR HUF") when that match is unique. Other names stay
without PAN until the user enters it on the Persons page.
"""
from __future__ import annotations

import re
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS persons (
    name TEXT PRIMARY KEY, display_name TEXT, pan TEXT, how TEXT, updated_at TEXT);
"""


def ensure(store):
    store.db.executescript(SCHEMA)


def key(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip()).upper()


def _tokens(s: str) -> set:
    return set(re.sub(r"[^A-Z0-9 ]", " ", str(s).upper()).split())


def pan_for(store, name: str) -> str:
    """PAN for a person name (stored mapping, else unique automatic match). Records the person."""
    ensure(store)
    k = key(name)
    if not k:
        return ""
    row = store.db.execute("SELECT pan FROM persons WHERE name=?", (k,)).fetchone()
    if row is not None:
        return row["pan"] or ""
    pan, how = "", ""
    toks = _tokens(k)
    hits = [c for c in store.query("SELECT pan, name FROM clients") if toks and toks <= _tokens(c["name"])]
    if len(hits) == 1:
        pan, how = hits[0]["pan"], f"auto: {hits[0]['name']}"
    store.db.execute("INSERT OR IGNORE INTO persons(name, display_name, pan, how, updated_at) VALUES (?,?,?,?,?)",
                     (k, str(name).strip(), pan or None, how or None, datetime.now().isoformat(timespec="seconds")))
    store.db.commit()
    return pan


def set_pan(store, name: str, pan: str) -> None:
    ensure(store)
    k = key(name)
    pan = (pan or "").strip().upper() or None
    store.db.execute("INSERT INTO persons(name, display_name, pan, how, updated_at) VALUES (?,?,?,?,?) "
                     "ON CONFLICT(name) DO UPDATE SET pan=excluded.pan, how='entered', updated_at=excluded.updated_at",
                     (k, name, pan, "entered", datetime.now().isoformat(timespec="seconds")))
    store.db.execute("UPDATE opening_lots SET pan=? WHERE UPPER(person)=?", (pan, k))
    store.db.commit()


def all_people(store) -> list[dict]:
    """Every person/client: contract-note clients plus names from holding sheets."""
    ensure(store)
    out = {}
    for c in store.query("SELECT pan, name FROM clients"):
        out[c["pan"]] = {"key": c["pan"], "label": f"{c['name']} ({c['pan']})", "pan": c["pan"]}
    for p in store.query("SELECT name, display_name, pan FROM persons"):
        if p["pan"] and p["pan"] in out:
            continue
        k = p["pan"] or f"NAME:{p['name']}"
        out[k] = {"key": k, "label": f"{p['display_name']}" + (f" ({p['pan']})" if p["pan"] else " (PAN not set)"),
                  "pan": p["pan"] or ""}
    return sorted(out.values(), key=lambda x: x["label"])
