"""Local SQLite store. Unique constraints make duplicate records impossible.

Duplicate protection works at three levels:
  1. file      : SHA-256 of every imported file
  2. note      : (broker, client code/PAN, contract note number)
  3. trade     : (broker, contract note, exchange, trade number, side)
The same database file can later move to PostgreSQL through SQLAlchemy without
changing the parsers.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import CHARGE_KEYS, CHARGE_LABELS, ContractNote

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS clients (
    pan TEXT PRIMARY KEY, name TEXT, ucc_list TEXT, folder TEXT, created_at TEXT);

CREATE TABLE IF NOT EXISTS files (
    sha256 TEXT PRIMARY KEY, name TEXT, origin TEXT, kind TEXT, status TEXT, imported_at TEXT);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    broker TEXT NOT NULL, client_key TEXT NOT NULL, cn_no TEXT NOT NULL,
    format TEXT, trade_date TEXT, settlement_date TEXT, settlement_no TEXT,
    client_name TEXT, pan TEXT, ucc TEXT, source_file TEXT, source_sha256 TEXT,
    {", ".join(f"{k} REAL" for k in CHARGE_KEYS)},
    net_amount REAL, recon_diff REAL, combined_charges INTEGER, remarks TEXT, imported_at TEXT,
    UNIQUE (broker, client_key, cn_no));

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT, note_id INTEGER REFERENCES notes(id),
    broker TEXT, cn_no TEXT, exchange TEXT, order_no TEXT, order_time TEXT,
    line_no INTEGER, trade_no TEXT, trade_time TEXT, symbol TEXT, isin TEXT, side TEXT,
    qty REAL, rate REAL, brokerage_per_unit REAL, trade_date TEXT,
    UNIQUE (note_id, line_no));
CREATE INDEX IF NOT EXISTS ix_trade_no ON trades(broker, exchange, trade_no, trade_date);

CREATE TABLE IF NOT EXISTS scrips (
    id INTEGER PRIMARY KEY AUTOINCREMENT, note_id INTEGER REFERENCES notes(id),
    isin TEXT, symbol TEXT, name_on_note TEXT, side TEXT, qty REAL, gross REAL, exchanges TEXT,
    {", ".join(f"a_{k} REAL" for k in CHARGE_KEYS)},
    total_charges REAL, net_exact REAL, net_rupees INTEGER, rounding REAL, basis TEXT,
    UNIQUE (note_id, isin, side));

CREATE TABLE IF NOT EXISTS scrip_master (
    isin TEXT PRIMARY KEY, symbol TEXT, company_name TEXT, industry TEXT,
    asset_class TEXT, sub_category TEXT, face_value REAL, source TEXT, updated_at TEXT);

CREATE TABLE IF NOT EXISTS tradebook (
    id INTEGER PRIMARY KEY AUTOINCREMENT, broker TEXT, ucc TEXT, trade_id TEXT, exchange TEXT,
    trade_date TEXT, symbol TEXT, isin TEXT, side TEXT, qty REAL, price REAL, order_id TEXT,
    source_file TEXT, UNIQUE (broker, exchange, trade_id));

CREATE TABLE IF NOT EXISTS import_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, source TEXT, status TEXT, message TEXT);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # ---------------------------------------------------------------- log
    def log(self, source: str, status: str, message: str = "") -> None:
        self.db.execute("INSERT INTO import_log(at, source, status, message) VALUES (?,?,?,?)",
                        (now(), source, status, message))
        self.db.commit()

    # ---------------------------------------------------------------- files
    def file_seen(self, sha: str):
        return self.db.execute("SELECT * FROM files WHERE sha256=?", (sha,)).fetchone()

    def add_file(self, sha, name, origin, kind, status):
        self.db.execute("INSERT OR IGNORE INTO files VALUES (?,?,?,?,?,?)", (sha, name, origin, kind, status, now()))
        self.db.commit()

    # ---------------------------------------------------------------- clients
    def ensure_client(self, pan: str, name: str, ucc: str, folder: str) -> None:
        row = self.db.execute("SELECT ucc_list FROM clients WHERE pan=?", (pan,)).fetchone()
        if row:
            uccs = set(filter(None, row["ucc_list"].split(","))) | {ucc}
            self.db.execute("UPDATE clients SET ucc_list=? WHERE pan=?", (",".join(sorted(uccs)), pan))
        else:
            self.db.execute("INSERT INTO clients VALUES (?,?,?,?,?)", (pan, name, ucc, folder, now()))
        self.db.commit()

    # ---------------------------------------------------------------- notes
    def note_exists(self, cn: ContractNote):
        b, ck, no = cn.key()
        return self.db.execute("SELECT id, source_file FROM notes WHERE broker=? AND client_key=? AND cn_no=?",
                               (cn.broker, ck, cn.cn_no)).fetchone()

    def trades_already_held(self, cn: ContractNote) -> int:
        n = 0
        for t in cn.trades:
            if not str(t.trade_no).strip().isdigit():
                continue
            n += self.db.execute("SELECT 1 FROM trades WHERE broker=? AND exchange=? AND trade_no=? AND side=? "
                                 "AND isin=? AND trade_date=?",
                                 (cn.broker, t.exchange, t.trade_no, t.side, t.isin, cn.trade_date)).fetchone() is not None
        return n

    def save_note(self, cn: ContractNote) -> int:
        cols = ["broker", "client_key", "cn_no", "format", "trade_date", "settlement_date", "settlement_no",
                "client_name", "pan", "ucc", "source_file", "source_sha256", *CHARGE_KEYS,
                "net_amount", "recon_diff", "combined_charges", "remarks", "imported_at"]
        vals = [cn.broker, cn.key()[1], cn.cn_no, cn.format_name, cn.trade_date, cn.settlement_date,
                cn.settlement_no, cn.client_name, cn.pan, cn.ucc, cn.source_file, cn.source_hash,
                *[cn.charges[k] for k in CHARGE_KEYS], cn.net_amount, cn.recon_diff,
                int(cn.combined_charges), "; ".join(cn.notes), now()]
        with self.db:
            cur = self.db.execute(f"INSERT INTO notes({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
            nid = cur.lastrowid
            for line_no, t in enumerate(cn.trades, 1):
                self.db.execute("INSERT INTO trades(note_id, broker, cn_no, exchange, order_no, order_time, line_no, "
                                "trade_no, trade_time, symbol, isin, side, qty, rate, brokerage_per_unit, trade_date) "
                                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (nid, cn.broker, cn.cn_no, t.exchange, t.order_no, t.order_time, line_no,
                                 t.trade_no if str(t.trade_no).strip().isdigit() else None,
                                 t.trade_time, t.symbol, t.isin, t.side, t.qty, t.rate, t.brokerage_per_unit, cn.trade_date))
            for s in cn.scrips:
                self.db.execute(
                    f"INSERT INTO scrips(note_id, isin, symbol, name_on_note, side, qty, gross, exchanges, "
                    f"{','.join('a_' + k for k in CHARGE_KEYS)}, total_charges, net_exact, net_rupees, rounding, basis) "
                    f"VALUES ({','.join('?' * (8 + len(CHARGE_KEYS) + 5))})",
                    (nid, s.isin, s.symbol, s.name_on_note, s.side, s.qty, s.gross, s.exchanges,
                     *[s.alloc[k] for k in CHARGE_KEYS], s.alloc["total"], s.alloc["net_exact"],
                     s.alloc["net_rupees"], s.alloc["rounding"], json.dumps(s.basis)))
                self.db.execute("INSERT OR IGNORE INTO scrip_master(isin, symbol, company_name, source, updated_at) "
                                "VALUES (?,?,?,?,?)", (s.isin, s.symbol, s.name_on_note or "", "Contract note", now()))
        return nid

    # ---------------------------------------------------------------- master
    def upsert_master(self, rows: list[dict], source: str) -> int:
        n = 0
        with self.db:
            for r in rows:
                isin = (r.get("isin") or "").strip().upper()
                if len(isin) != 12:
                    continue
                cur = self.db.execute("SELECT * FROM scrip_master WHERE isin=?", (isin,)).fetchone()
                merged = dict(cur) if cur else {"isin": isin}
                for k in ("symbol", "company_name", "industry", "asset_class", "sub_category", "face_value"):
                    if r.get(k) not in (None, ""):
                        merged[k] = r[k]
                merged["source"], merged["updated_at"] = source, now()
                self.db.execute("INSERT OR REPLACE INTO scrip_master(isin, symbol, company_name, industry, asset_class, "
                                "sub_category, face_value, source, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                                tuple(merged.get(k) for k in ("isin", "symbol", "company_name", "industry", "asset_class",
                                                              "sub_category", "face_value", "source", "updated_at")))
                n += 1
        return n

    def query(self, sql: str, args=()):
        return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    # ---------------------------------------------------------------- delete / edit
    def delete_notes(self, note_ids) -> list[str]:
        """Delete contract notes with their trades and script rows. The source file can then be imported again."""
        done = []
        with self.db:
            for nid in note_ids:
                n = self.db.execute("SELECT cn_no, broker, source_sha256 FROM notes WHERE id=?", (nid,)).fetchone()
                if not n:
                    continue
                self.db.execute("DELETE FROM trades WHERE note_id=?", (nid,))
                self.db.execute("DELETE FROM scrips WHERE note_id=?", (nid,))
                self.db.execute("DELETE FROM notes WHERE id=?", (nid,))
                left = self.db.execute("SELECT COUNT(*) FROM notes WHERE source_sha256=?", (n["source_sha256"],)).fetchone()[0]
                if not left:
                    self.db.execute("DELETE FROM files WHERE sha256=?", (n["source_sha256"],))
                done.append(f"{n['broker']} {n['cn_no']}")
        for d in done:
            self.log(d, "Deleted", "contract note deleted by user")
        return done

    def delete_scrip_rows(self, row_ids) -> int:
        with self.db:
            notes = {r["note_id"] for r in self.query(
                f"SELECT note_id FROM scrips WHERE id IN ({','.join('?' * len(row_ids))})", tuple(row_ids))}
            for rid in row_ids:
                r = self.db.execute("SELECT s.isin, s.side, n.cn_no, n.id nid FROM scrips s JOIN notes n "
                                    "ON n.id=s.note_id WHERE s.id=?", (rid,)).fetchone()
                if r:
                    self.db.execute("DELETE FROM trades WHERE note_id=? AND isin=? AND side=?", (r["nid"], r["isin"], r["side"]))
                    self.db.execute("DELETE FROM scrips WHERE id=?", (rid,))
                    self.log(r["cn_no"], "Deleted item", f"{r['isin']} {r['side']} removed by user")
        for nid in notes:
            self.recompute_note(nid, "items deleted")
        return len(row_ids)

    EDITABLE = {"Quantity": "qty", "Gross Value": "gross", "ISIN": "isin", "Script": "symbol",
                **{label: f"a_{key}" for key, label in CHARGE_LABELS.items()}}

    def update_scrip(self, row_id: int, column: str, value) -> None:
        col = self.EDITABLE.get(column)
        if not col:
            raise ValueError(f"'{column}' cannot be edited here")
        if col in ("isin", "symbol"):
            value = str(value or "").strip().upper()
            if col == "isin":
                from .utils import isin_check_digit_ok
                if not isin_check_digit_ok(value):
                    raise ValueError(f"ISIN '{value}' is not valid")
        else:
            value = float(str(value).replace(",", ""))
            if value < 0:
                raise ValueError("value cannot be negative")
        old = self.db.execute(f"SELECT {col} v, note_id FROM scrips WHERE id=?", (row_id,)).fetchone()
        self.db.execute(f"UPDATE scrips SET {col}=? WHERE id=?", (value, row_id))
        self.db.commit()
        cn = self.db.execute("SELECT cn_no FROM notes WHERE id=?", (old["note_id"],)).fetchone()["cn_no"]
        self.log(cn, "Edited", f"{column}: {old['v']} -> {value}")
        self.recompute_note(old["note_id"], f"{column} edited")

    def update_note(self, note_id: int, field: str, value: str) -> None:
        allowed = {"trade_date", "settlement_date"}
        if field not in allowed:
            raise ValueError("only dates can be edited on the note")
        from datetime import date
        date.fromisoformat(value)
        old = self.db.execute(f"SELECT {field} v, cn_no FROM notes WHERE id=?", (note_id,)).fetchone()
        self.db.execute(f"UPDATE notes SET {field}=? WHERE id=?", (value, note_id))
        if field == "trade_date":
            self.db.execute("UPDATE trades SET trade_date=? WHERE note_id=?", (value, note_id))
        self.db.commit()
        self.log(old["cn_no"], "Edited", f"{field}: {old['v']} -> {value}")
        self.recompute_note(note_id, f"{field} edited")

    def recompute_note(self, note_id: int, why: str) -> None:
        """After a manual change: re-total the row, the note's charges and the reconciliation."""
        import math
        rows = self.query("SELECT * FROM scrips WHERE note_id=?", (note_id,))
        totals = {k: 0.0 for k in CHARGE_KEYS}
        signed_sum = 0.0
        for r in rows:
            tot = round(sum(r[f"a_{k}"] or 0 for k in CHARGE_KEYS), 2)
            net = round(r["gross"] + tot if r["side"] == "BUY" else r["gross"] - tot, 2)
            rup = int(math.floor(abs(net) + 0.5)) * (1 if net >= 0 else -1)
            self.db.execute("UPDATE scrips SET total_charges=?, net_exact=?, net_rupees=?, rounding=? WHERE id=?",
                            (tot, net, rup, round(rup - net, 2), r["id"]))
            for k in CHARGE_KEYS:
                totals[k] += r[f"a_{k}"] or 0
            signed_sum += net if r["side"] == "BUY" else -net
        note = self.db.execute("SELECT net_amount, remarks FROM notes WHERE id=?", (note_id,)).fetchone()
        stamp = datetime.now().strftime("%d-%m-%Y %H:%M")
        remarks = (note["remarks"] or "")
        remarks = (remarks + "; " if remarks else "") + f"Edited manually {stamp} ({why})"
        self.db.execute(f"UPDATE notes SET {', '.join(k + '=?' for k in CHARGE_KEYS)}, recon_diff=?, remarks=? WHERE id=?",
                        (*[round(totals[k], 2) for k in CHARGE_KEYS], round(signed_sum - note["net_amount"], 2),
                         remarks[-1000:], note_id))
        self.db.commit()

