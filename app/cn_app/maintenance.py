"""Data maintenance: folder sizes, clearing temporary and source files, CSV copies, backups."""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from .paths import Layout

DEFAULTS = {"auto_backup": True, "every_days": 7, "keep_years": 2, "include_masters": False,
            "include_transactions": False}
SCHEMA = "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT);"
SOURCE_KINDS = {     # label -> attribute of Layout
    "Contract note files": "notes",
    "Portal downloads (ledger, P&L, holdings)": "portal",
    "Holding statements": "statements",
    "Tally exports": "tally",
}


def settings(store) -> dict:
    store.db.executescript(SCHEMA)
    r = store.db.execute("SELECT value FROM app_settings WHERE key='maintenance'").fetchone()
    cfg = dict(DEFAULTS)
    if r:
        cfg.update(json.loads(r["value"]))
    return cfg


def save_settings(store, cfg: dict):
    store.db.executescript(SCHEMA)
    store.db.execute("INSERT OR REPLACE INTO app_settings VALUES ('maintenance', ?)", (json.dumps(cfg),))
    store.db.commit()


# --------------------------------------------------------------------------- sizes and clean-up

def folder_size(p: Path) -> tuple[int, int]:
    n = size = 0
    if p.exists():
        for f in p.rglob("*"):
            if f.is_file():
                n += 1
                try:
                    size += f.stat().st_size
                except OSError:
                    pass
    return n, size


def sizes(L: Layout) -> pd.DataFrame:
    rows = []
    what = {"Master Data": "Reference lists from Import Masters (.md)",
            "Client Data": "Database, CSV copy per person, browser sign-ins",
            "Transaction Data": "Imported source files: contract notes, statements, downloads",
            "Reports": "Reports you created", "Temporary Data": "Uploads in progress and logs: safe to delete",
            "Backup": "Weekly backups"}
    for f in L.folders():
        n, sz = folder_size(f)
        rows.append({"Folder": f.name, "Holds": what.get(f.name, ""), "Files": n, "Size (MB)": round(sz / 2 ** 20, 2)})
    return pd.DataFrame(rows)


def _delete_files(root: Path, before: str | None = None, keep: set | None = None) -> tuple[int, int]:
    n = freed = 0
    if not root.exists():
        return 0, 0
    cutoff = datetime.fromisoformat(before).timestamp() if before else None
    for f in sorted(root.rglob("*"), key=lambda x: -len(x.parts)):
        try:
            if f.is_file():
                if keep and f.resolve() in keep:
                    continue
                if cutoff and f.stat().st_mtime >= cutoff:
                    continue
                sz = f.stat().st_size
                f.unlink()
                n += 1
                freed += sz
            elif f.is_dir() and not any(f.iterdir()):
                f.rmdir()
        except OSError:
            continue                  # a file in use is left alone
    return n, freed


def clear_temp(L: Layout, keep: set | None = None) -> tuple[int, int]:
    return _delete_files(L.temp, keep=keep)


def delete_sources(L: Layout, kinds: list[str], before: str | None = None) -> tuple[int, int]:
    n = freed = 0
    for k in kinds:
        a, b = _delete_files(getattr(L, SOURCE_KINDS[k]), before)
        n += a
        freed += b
    return n, freed


def delete_reports(L: Layout, before: str | None = None) -> tuple[int, int]:
    return _delete_files(L.reports, before)


def compact(store):
    store.db.commit()
    store.db.execute("VACUUM")


# --------------------------------------------------------------------------- CSV copy per person

def _safe(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", s).strip(" .")[:80] or "unknown"


def write_csv(store, L: Layout) -> int:
    """Client Data\\<PAN>_<name>\\*.csv: notes, scrip-wise lines, trades and opening holdings of each person."""
    con = store.db
    people = con.execute("SELECT pan, MAX(client_name) name FROM notes WHERE pan IS NOT NULL AND pan<>'' "
                         "GROUP BY pan").fetchall()
    n = 0
    for p in people:
        folder = L.client / _safe(f"{p['pan']}_{p['name'] or ''}")
        folder.mkdir(parents=True, exist_ok=True)
        q = {
            "contract_notes.csv": ("SELECT * FROM notes WHERE pan=? ORDER BY trade_date, cn_no", (p["pan"],)),
            "scrip_lines.csv": ("SELECT n.trade_date, n.broker, n.cn_no, s.* FROM scrips s JOIN notes n ON n.id=s.note_id "
                                "WHERE n.pan=? ORDER BY n.trade_date", (p["pan"],)),
            "trades.csv": ("SELECT t.* FROM trades t JOIN notes n ON n.id=t.note_id WHERE n.pan=? "
                           "ORDER BY t.trade_date, t.id", (p["pan"],)),
        }
        try:
            con.execute("SELECT 1 FROM opening_lots LIMIT 1")
            q["opening_holdings.csv"] = ("SELECT * FROM opening_lots WHERE pan=? ORDER BY purchase_date", (p["pan"],))
        except sqlite3.Error:
            pass
        for name, (sql, args) in q.items():
            pd.read_sql_query(sql, con, params=args).to_csv(folder / name, index=False)
        n += 1
    return n


# --------------------------------------------------------------------------- backup and restore

def backups(L: Layout) -> list[Path]:
    L.backup.mkdir(parents=True, exist_ok=True)
    return sorted(L.backup.glob("Backup_*.zip"), reverse=True)


def last_backup(L: Layout) -> datetime | None:
    b = backups(L)
    return datetime.fromtimestamp(b[0].stat().st_mtime) if b else None


def due(store, L: Layout) -> bool:
    cfg = settings(store)
    lb = last_backup(L)
    return bool(cfg["auto_backup"]) and (lb is None or datetime.now() - lb >= timedelta(days=int(cfg["every_days"])))


def backup(store, L: Layout, note: str = "") -> Path:
    cfg = settings(store)
    L.backup.mkdir(parents=True, exist_ok=True)
    write_csv(store, L)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp = L.temp / f"backup_{stamp}.db"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    store.db.commit()
    dst = sqlite3.connect(tmp)
    with dst:
        store.db.backup(dst)                  # consistent copy even while the app is running
    dst.close()
    out = L.backup / f"Backup_{stamp}{('_' + _safe(note)) if note else ''}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tmp, "Client Data/contract_notes.db")
        for f in L.client.rglob("*"):
            if f.is_file() and L.browser not in f.parents and not f.name.startswith("contract_notes.db"):
                z.write(f, Path("Client Data") / f.relative_to(L.client))
        extra = ([L.master] if cfg["include_masters"] else []) + ([L.trans] if cfg["include_transactions"] else [])
        for root in extra:
            for f in root.rglob("*"):
                if f.is_file():
                    z.write(f, Path(root.name) / f.relative_to(root))
        z.writestr("backup.json", json.dumps({"created": datetime.now().isoformat(timespec="seconds"),
                                              "note": note, "masters": cfg["include_masters"],
                                              "transactions": cfg["include_transactions"]}))
    tmp.unlink(missing_ok=True)
    prune(store, L)
    store.log(out.name, "Backup created", f"{out.stat().st_size / 2 ** 20:.1f} MB")
    return out


def prune(store, L: Layout) -> int:
    years = float(settings(store)["keep_years"])
    cutoff = datetime.now() - timedelta(days=365 * years)
    n = 0
    for b in backups(L)[1:]:                 # the newest backup is always kept
        if datetime.fromtimestamp(b.stat().st_mtime) < cutoff:
            b.unlink(missing_ok=True)
            n += 1
    return n


def restore(store, L: Layout, zip_path: Path) -> Path:
    """Put a backup back. A safety backup of the present data is made first."""
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path) as z:
        if "Client Data/contract_notes.db" not in z.namelist():
            raise ValueError("this zip is not an Investor Manager backup (no database inside)")
    safety = backup(store, L, "before restore")
    work = L.temp / f"restore_{datetime.now():%Y%m%d_%H%M%S}"
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(work)
    src = sqlite3.connect(work / "Client Data" / "contract_notes.db")
    with store.db:
        src.backup(store.db)                 # replaces the live database contents in place
    src.close()
    for f in (work / "Client Data").rglob("*"):
        if f.is_file() and not f.name.startswith("contract_notes.db"):
            dst = L.client / f.relative_to(work / "Client Data")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
    for name in ("Master Data", "Transaction Data"):
        if (work / name).exists():
            shutil.copytree(work / name, L.root / name, dirs_exist_ok=True)
    shutil.rmtree(work, ignore_errors=True)
    store.log(zip_path.name, "Backup restored", f"safety copy of the previous data: {safety.name}")
    return safety
