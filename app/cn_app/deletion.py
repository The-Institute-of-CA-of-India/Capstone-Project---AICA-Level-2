"""Deleting client data: one PAN for one financial year, one PAN fully, or every PAN.

A backup is always made first, so a deletion can be undone by restoring that backup.
Masters, prices, settings, brokers, passwords and registration are never touched.
"""
from __future__ import annotations

from pathlib import Path

from . import maintenance
from .paths import Layout


def fy_of(d: str) -> str:
    y, m = int(d[:4]), int(d[5:7])
    start = y if m >= 4 else y - 1
    return f"{start}-{str(start + 1)[-2:]}"


def fy_bounds(fy: str) -> tuple[str, str]:
    start = int(fy[:4])
    return f"{start}-04-01", f"{start + 1}-03-31"


def years(store, pan: str = "") -> list[str]:
    q, a = "SELECT DISTINCT trade_date d FROM notes", ()
    if pan:
        q, a = q + " WHERE pan=?", (pan,)
    return sorted({fy_of(r["d"]) for r in store.query(q, a) if r["d"]}, reverse=True)


def _note_ids(store, pan: str, fy: str) -> list[int]:
    q, a = "SELECT id FROM notes WHERE 1=1", []
    if pan:
        q += " AND pan=?"
        a.append(pan)
    if fy:
        f, t = fy_bounds(fy)
        q += " AND trade_date BETWEEN ? AND ?"
        a += [f, t]
    return [r["id"] for r in store.query(q, tuple(a))]


def _has(store, table: str) -> bool:
    return bool(store.query("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)))


def preview(store, pan: str, fy: str, opening: bool) -> dict:
    ids = _note_ids(store, pan, fy)
    ph = ",".join("?" * len(ids)) or "NULL"
    out = {"Contract notes": len(ids),
           "Script lines": store.query(f"SELECT COUNT(*) c FROM scrips WHERE note_id IN ({ph})", tuple(ids))[0]["c"],
           "Trades": store.query(f"SELECT COUNT(*) c FROM trades WHERE note_id IN ({ph})", tuple(ids))[0]["c"]}
    if opening and _has(store, "opening_lots"):
        q, a = "SELECT COUNT(*) c FROM opening_lots WHERE source_file<>'Assumed by app'", ()
        if pan:
            q, a = q + " AND pan=?", (pan,)
        out["Opening holding lots"] = store.query(q, a)[0]["c"]
    return out


def delete(store, root: Path, pan: str, fy: str, opening: bool, files: bool, label: str) -> dict:
    """Back up, then delete. Returns {"backup": Path, "counts": {...}}."""
    L = Layout(root)
    counts = preview(store, pan, fy, opening)
    bk = maintenance.backup(store, L, f"before deleting {label}"[:60])
    ids = _note_ids(store, pan, fy)
    ph = ",".join("?" * len(ids)) or "NULL"
    sources = [r["source_file"] for r in store.query(f"SELECT source_file FROM notes WHERE id IN ({ph})", tuple(ids))]
    with store.db:
        shas = [r["source_sha256"] for r in
                store.query(f"SELECT DISTINCT source_sha256 FROM notes WHERE id IN ({ph})", tuple(ids))]
        store.db.execute(f"DELETE FROM scrips WHERE note_id IN ({ph})", tuple(ids))
        store.db.execute(f"DELETE FROM trades WHERE note_id IN ({ph})", tuple(ids))
        if _has(store, "tally_exports"):
            store.db.execute(f"DELETE FROM tally_exports WHERE note_id IN ({ph})", tuple(ids))
        store.db.execute(f"DELETE FROM notes WHERE id IN ({ph})", tuple(ids))
        for sha in shas:                         # the same file can be imported again later
            if sha and not store.query("SELECT 1 FROM notes WHERE source_sha256=? LIMIT 1", (sha,)):
                store.db.execute("DELETE FROM files WHERE sha256=?", (sha,))
        if opening and _has(store, "opening_lots"):
            if pan:
                store.db.execute("DELETE FROM opening_lots WHERE pan=?", (pan,))
            else:
                store.db.execute("DELETE FROM opening_lots")
        if not pan and not fy:
            store.db.execute("DELETE FROM tradebook")
            for t in ("holding_recon_runs", "cost_recon_runs"):
                if _has(store, t):
                    store.db.execute(f"DELETE FROM {t}")
        store.db.execute("DELETE FROM clients WHERE pan NOT IN (SELECT DISTINCT pan FROM notes WHERE pan IS NOT NULL)")
    removed = 0
    if files:
        for f in sources:
            for cand in L.notes.rglob(Path(f or "").name or "__none__"):
                try:
                    cand.unlink()
                    removed += 1
                except OSError:
                    pass
    store.log(label, "Data deleted", ", ".join(f"{k} {v}" for k, v in counts.items())
              + f"; backup {bk.name}" + (f"; {removed} file(s) removed" if files else ""))
    return {"backup": bk, "counts": counts}
