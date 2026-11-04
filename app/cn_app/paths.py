"""Folder layout of the Data folder (from v1.7).

Data
  Master Data        permanent reference lists (Import Masters), kept as .md tables
  Client Data        the app's own working data: database, CSV copy per person, logs, browser profile
  Transaction Data   imported source files: contract notes, holding statements, ledgers, P&L, Tally exports
  Reports            reports created by the app
  Temporary Data     uploads in progress and other files that can be deleted at any time
  Backup             weekly backups (zip)
"""
from __future__ import annotations

import shutil
from pathlib import Path


class Layout:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.master = self.root / "Master Data"
        self.client = self.root / "Client Data"
        self.trans = self.root / "Transaction Data"
        self.reports = self.root / "Reports"
        self.temp = self.root / "Temporary Data"
        self.backup = self.root / "Backup"
        self.db = self.client / "contract_notes.db"
        self.logs = self.temp / "Logs"
        self.uploads = self.temp / "Uploads"
        self.notes = self.trans / "Contract Notes"          # <client>/contract_notes/<year>/...
        self.portal = self.trans / "Portal Downloads"       # <broker>/<kind>/...
        self.statements = self.trans / "Holding Statements"
        self.tally = self.trans / "Tally Exports"
        self.browser = self.client / "Browser profile"

    def folders(self):
        return [self.master, self.client, self.trans, self.reports, self.temp, self.backup]

    def make(self):
        for f in self.folders():
            f.mkdir(parents=True, exist_ok=True)


def _move(src: Path, dst: Path) -> bool:
    """Move a file or merge a folder into dst. Returns True if something moved."""
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in list(src.iterdir()):
            _move(child, dst / child.name)
        try:
            src.rmdir()
        except OSError:
            pass
        return True
    if dst.exists():
        return False                # never overwrite
    shutil.move(str(src), str(dst))
    return True


def migrate(root: Path) -> list[str]:
    """Move a v1.0 - v1.6 Data folder into the new layout (once). Returns what was moved."""
    L = Layout(root)
    L.make()
    done = []
    for name in ("contract_notes.db", "contract_notes.db-wal", "contract_notes.db-shm", "passwords.txt",
                 "passwords.txt.migrated"):
        if _move(L.root / name, L.client / name):
            done.append(f"{name} -> Client Data")
    for old, new, label in (("clients", L.notes, "Transaction Data\\Contract Notes"),
                            ("Downloads", L.portal, "Transaction Data\\Portal Downloads"),
                            ("Uploads", L.uploads, "Temporary Data\\Uploads"),
                            ("Logs", L.logs, "Temporary Data\\Logs"),
                            ("Portal profile", L.browser, "Client Data\\Browser profile"),
                            ("Masters", L.master / "_to_convert", "Master Data")):
        if _move(L.root / old, new):
            done.append(f"{old} -> {label}")
    return done
