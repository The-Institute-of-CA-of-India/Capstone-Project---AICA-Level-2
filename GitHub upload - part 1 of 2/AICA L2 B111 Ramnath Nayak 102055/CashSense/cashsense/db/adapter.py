"""Database adapter. The app talks only to this interface, so the backend can be a local
SQLite file (development) or Supabase (hosted Postgres) without code changes."""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from .. import config

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
TABLES = ("company", "bank_accounts", "counterparties", "bank_holidays", "book_entries", "statement_imports",
          "bank_lines", "ar_open", "ap_open", "commitments", "recon_links", "recon_runs", "recon_items",
          "risk_flags", "approvals", "app_state", "audit_log")
# delete children before parents
CLEAR_ORDER = ("recon_links", "recon_items", "recon_runs", "risk_flags", "approvals", "app_state",
               "bank_lines", "statement_imports", "book_entries", "ar_open", "ap_open", "commitments",
               "bank_holidays", "counterparties", "bank_accounts", "company", "audit_log")
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _check_table(table: str) -> str:
    if table not in TABLES:
        raise ValueError(f"Unknown table: {table}")
    return table


def _check_cols(cols) -> list[str]:
    cols = list(cols)
    for c in cols:
        if not _IDENT.match(c):
            raise ValueError(f"Invalid column name: {c}")
    return cols


class Database(ABC):
    @abstractmethod
    def init_schema(self) -> None: ...

    @abstractmethod
    def insert_many(self, table: str, rows: list[dict]) -> int: ...

    @abstractmethod
    def query(self, table: str, filters: dict | None = None, order: str | None = None) -> list[dict]: ...

    @abstractmethod
    def clear(self, table: str) -> None: ...

    @abstractmethod
    def update(self, table: str, key: dict, values: dict) -> int: ...

    @abstractmethod
    def delete(self, table: str, filters: dict) -> None: ...

    def reset(self) -> None:
        """Empty every table except the audit log (schema must already exist)."""
        for t in CLEAR_ORDER:
            if t != "audit_log":
                self.clear(t)

    def get_state(self, key: str, default: str = "") -> str:
        rows = self.query("app_state", {"state_key": key})
        return rows[0]["state_value"] if rows else default

    def set_state(self, key: str, value: str) -> None:
        if self.query("app_state", {"state_key": key}):
            self.update("app_state", {"state_key": key}, {"state_value": value})
        else:
            self.insert_many("app_state", [{"state_key": key, "state_value": value}])

    def audit(self, actor: str, action: str, entity: str = "", entity_id: str = "", details: dict | None = None):
        self.insert_many("audit_log", [{
            "log_id": uuid.uuid4().hex, "ts": config.now_ist().isoformat(timespec="seconds"), "actor": actor,
            "action": action, "entity": entity, "entity_id": entity_id,
            "details": json.dumps(details or {}, default=str)}])


class SQLiteDatabase(Database):
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        self.conn.commit()

    def insert_many(self, table: str, rows: list[dict]) -> int:
        if not rows:
            return 0
        cols = _check_cols(rows[0].keys())
        sql = f"INSERT INTO {_check_table(table)} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
        self.conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
        self.conn.commit()
        return len(rows)

    def query(self, table: str, filters: dict | None = None, order: str | None = None) -> list[dict]:
        sql, args = f"SELECT * FROM {_check_table(table)}", []
        if filters:
            cols = _check_cols(filters.keys())
            sql += " WHERE " + " AND ".join(f"{c} = ?" for c in cols)
            args = [filters[c] for c in cols]
        if order:
            _check_cols([order])
            sql += f" ORDER BY {order}"
        return [dict(r) for r in self.conn.execute(sql, args)]

    def clear(self, table: str) -> None:
        self.conn.execute(f"DELETE FROM {_check_table(table)}")
        self.conn.commit()

    def update(self, table: str, key: dict, values: dict) -> int:
        kcols, vcols = _check_cols(key.keys()), _check_cols(values.keys())
        sql = (f"UPDATE {_check_table(table)} SET {', '.join(f'{c} = ?' for c in vcols)} "
               f"WHERE {' AND '.join(f'{c} = ?' for c in kcols)}")
        cur = self.conn.execute(sql, [values[c] for c in vcols] + [key[c] for c in kcols])
        self.conn.commit()
        return cur.rowcount

    def delete(self, table: str, filters: dict) -> None:
        if not filters:
            raise ValueError("delete needs at least one filter")
        cols = _check_cols(filters.keys())
        self.conn.execute(f"DELETE FROM {_check_table(table)} WHERE {' AND '.join(f'{c} = ?' for c in cols)}",
                          [filters[c] for c in cols])
        self.conn.commit()

    def reset(self) -> None:
        """SQLite is a disposable local copy: drop and recreate every table except the audit log,
        so schema changes always apply."""
        for t in CLEAR_ORDER:
            if t != "audit_log":
                self.conn.execute(f"DROP TABLE IF EXISTS {t}")
        self.conn.commit()
        self.init_schema()

    def sql(self, statement: str, args: tuple = ()) -> list[dict]:
        """Read-only SQL for reports and tests (SQLite only)."""
        if not statement.lstrip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT statements are allowed")
        return [dict(r) for r in self.conn.execute(statement, args)]

    def close(self) -> None:
        self.conn.close()


class SupabaseError(RuntimeError):
    pass


class SupabaseDatabase(Database):
    """Supabase (hosted Postgres) via its REST API (PostgREST), server-side only, with the secret key.
    Row Level Security is enabled on every table with no policies, so the public (anon / publishable) key
    cannot read anything; the secret key used here bypasses RLS. Reads are cached for a few seconds and
    the cache of a table is cleared on every write to it."""

    CACHE_SECONDS = 20

    def __init__(self, url: str, key: str, session=None):
        import requests

        if not url or not key:
            raise ValueError("Set SUPABASE_URL and SUPABASE_KEY in .env")
        url = url.strip().rstrip("/")
        url = url[: -len("/rest/v1")] if url.endswith("/rest/v1") else url   # accept the REST URL form too
        self.base = url + "/rest/v1"
        self.headers = {"apikey": key, "Content-Type": "application/json"}
        if key.startswith("eyJ"):                    # legacy JWT keys also go in the Authorization header
            self.headers["Authorization"] = f"Bearer {key}"
        self.http = session or requests.Session()
        self._cache: dict[tuple, tuple[float, list]] = {}

    def _check(self, r, what: str):
        if r.status_code >= 400:
            try:
                detail = r.json().get("message", "")
            except ValueError:
                detail = r.text[:200]
            raise SupabaseError(f"Supabase {what} failed (HTTP {r.status_code}): {detail}")
        return r

    def _invalidate(self, table: str) -> None:
        self._cache = {k: v for k, v in self._cache.items() if k[0] != table}

    def init_schema(self) -> None:
        """Schema is created once by running db/supabase_setup.sql in the Supabase SQL editor; here we only check."""
        import time as _t

        r = self.http.get(f"{self.base}/company", params={"select": "company_id", "limit": 1},
                          headers=self.headers, timeout=30)
        if r.status_code == 404 or (r.status_code >= 400 and "does not exist" in r.text):
            raise SupabaseError("Tables not found - run cashsense/db/supabase_setup.sql in the Supabase SQL editor")
        self._check(r, "schema check")
        _ = _t

    def insert_many(self, table: str, rows: list[dict]) -> int:
        _check_table(table)
        for i in range(0, len(rows), 500):
            r = self.http.post(f"{self.base}/{table}", headers={**self.headers, "Prefer": "return=minimal"},
                               json=rows[i:i + 500], timeout=60)
            self._check(r, f"insert into {table}")
        self._invalidate(table)
        return len(rows)

    def query(self, table: str, filters: dict | None = None, order: str | None = None) -> list[dict]:
        import time as _t

        key = (table, tuple(sorted((filters or {}).items())), order)
        hit = self._cache.get(key)
        if hit and _t.monotonic() - hit[0] < self.CACHE_SECONDS:
            return [dict(r) for r in hit[1]]
        params = {"select": "*"}
        for c in _check_cols((filters or {}).keys()):
            params[c] = f"eq.{filters[c]}"
        params["order"] = (_check_cols([order])[0] if order else self.PRIMARY_KEYS[_check_table(table)]) + ".asc"
        out, offset = [], 0
        while True:
            r = self.http.get(f"{self.base}/{table}", params={**params, "limit": 1000, "offset": offset},
                              headers=self.headers, timeout=60)
            batch = self._check(r, f"read {table}").json()
            out.extend(batch)
            if len(batch) < 1000:
                break
            offset += 1000
        self._cache[key] = (_t.monotonic(), out)
        return [dict(r) for r in out]

    PRIMARY_KEYS = {"company": "company_id", "bank_accounts": "account_id", "counterparties": "party_id",
                    "bank_holidays": "holiday_date", "book_entries": "entry_id", "statement_imports": "import_id",
                    "bank_lines": "line_id", "ar_open": "invoice_no", "ap_open": "bill_no",
                    "commitments": "commit_id", "recon_links": "link_id", "recon_runs": "run_id",
                    "recon_items": "item_id", "risk_flags": "flag_id", "approvals": "approval_id",
                    "app_state": "state_key", "audit_log": "log_id"}

    def clear(self, table: str) -> None:
        r = self.http.delete(f"{self.base}/{_check_table(table)}", params={self.PRIMARY_KEYS[table]: "not.is.null"},
                             headers=self.headers, timeout=60)
        self._check(r, f"clear {table}")
        self._invalidate(table)

    def delete(self, table: str, filters: dict) -> None:
        if not filters:
            raise ValueError("delete needs at least one filter")
        params = {c: f"eq.{filters[c]}" for c in _check_cols(filters.keys())}
        r = self.http.delete(f"{self.base}/{_check_table(table)}", params=params, headers=self.headers, timeout=60)
        self._check(r, f"delete from {table}")
        self._invalidate(table)

    def update(self, table: str, key: dict, values: dict) -> int:
        params = {c: f"eq.{key[c]}" for c in _check_cols(key.keys())}
        _check_cols(values.keys())
        r = self.http.patch(f"{self.base}/{_check_table(table)}", params=params, json=values,
                            headers={**self.headers, "Prefer": "return=representation"}, timeout=60)
        self._invalidate(table)
        return len(self._check(r, f"update {table}").json())


def supabase_setup_sql() -> str:
    """schema.sql plus Row Level Security on every table (no policies: only the secret key can read/write)."""
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    rls = "\n".join(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;" for t in TABLES)
    return ("-- CashSense: run once in Supabase > SQL Editor > New query > Run\n" + sql +
            "\n-- Row Level Security: no policies, so the public key can read nothing.\n" + rls + "\n")


def copy_database(src: Database, dst: Database, progress=print) -> dict:
    """Copy every table from one backend to another (e.g. local SQLite -> Supabase), parents first."""
    counts = {}
    for t in CLEAR_ORDER:
        dst.clear(t)
    for t in reversed(CLEAR_ORDER):
        rows = src.query(t)
        dst.insert_many(t, rows)
        counts[t] = len(rows)
        progress(f"  {t}: {len(rows)} rows")
    return counts


def get_database() -> Database:
    if config.db_backend() == "supabase":
        return SupabaseDatabase(config.setting("SUPABASE_URL"), config.setting("SUPABASE_KEY"))
    return SQLiteDatabase(config.sqlite_path())
