"""Database access layer.

Two interchangeable backends share one SQL dialect subset:

* ``SQLiteDatabase``   – local/dev/test backend. Tenant isolation is enforced by the
  service layer (services/tenancy.py) because SQLite has no RLS.
* ``PostgresDatabase`` – Supabase Postgres. Every transaction executed on behalf of a
  logged-in user runs as the ``authenticated`` role with ``request.jwt.claims`` set, so
  the RLS policies in database/migrations/002_rls.sql are enforced by Postgres itself
  *in addition to* the service-layer checks.

SQL is written with ``?`` placeholders and translated for pg8000 (``%s``).
"""
from __future__ import annotations

import contextvars
import datetime as dt
import json
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Iterator

from config import BASE_DIR, settings

MIGRATIONS_DIR = BASE_DIR / "database" / "migrations"

# Set by auth layer for the duration of a request: the authenticated user id (or None for system tasks)
current_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_user_id", default=None)

NO_ID_TABLES = {"platform_settings"}

JSON_COLUMNS = {
    "features", "value", "context", "settings", "permissions", "snapshot", "review_flags", "log", "data",
    "field_confidence", "validation", "reasons", "warnings", "summary", "details", "voucher_ids",
    "before_data", "after_data",
}


@contextmanager
def system_identity():
    """Run a block WITHOUT the per-user RLS identity. Only for privileged server-side steps whose authorization
    has already been checked in Python (e.g. creating a login profile after require_firm/require_client)."""
    previous = current_user_id.get()
    token = current_user_id.set(None)
    db = _db
    in_tx = isinstance(db, PostgresDatabase) and getattr(db._local, "depth", 0) > 0
    if in_tx:
        db._conn().cursor().execute("reset role")  # leave 'authenticated' for this privileged step only
    try:
        yield
    finally:
        current_user_id.reset(token)
        if in_tx and previous:
            db._apply_identity(db._conn().cursor())  # back to the user's RLS identity


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _adapt(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _normalize_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, uuid.UUID):
            v = str(v)
        elif k in JSON_COLUMNS and isinstance(v, str):
            try:
                v = json.loads(v)
            except (ValueError, TypeError):
                pass
        out[k] = v
    return out


def pg_to_sqlite(sql: str) -> str:
    """Translate the documented PostgreSQL subset used in 001_schema.sql to SQLite."""
    sql = re.sub(r"\bnumeric\(\d+,\s*\d+\)", "TEXT", sql, flags=re.I)
    sql = re.sub(r"\btimestamptz\b", "TEXT", sql, flags=re.I)
    sql = re.sub(r"\bjsonb\b", "TEXT", sql, flags=re.I)
    sql = re.sub(r"\buuid\b", "TEXT", sql, flags=re.I)
    sql = re.sub(r"\bboolean\b", "INTEGER", sql, flags=re.I)
    sql = re.sub(r"default now\(\)", "default CURRENT_TIMESTAMP", sql, flags=re.I)
    sql = re.sub(r"default true\b", "default 1", sql, flags=re.I)
    sql = re.sub(r"default false\b", "default 0", sql, flags=re.I)
    return sql


class DatabaseError(Exception):
    pass


class IntegrityError(DatabaseError):
    pass


class BaseDatabase:
    dialect = "base"

    # ---- to implement ----
    def _execute(self, sql: str, params: tuple) -> Any:  # pragma: no cover
        raise NotImplementedError

    @contextmanager
    def transaction(self) -> Iterator[None]:  # pragma: no cover
        raise NotImplementedError

    # ---- helpers ----
    def fetchall(self, sql: str, params: Iterable = ()) -> list[dict]:
        cur = self._execute(sql, tuple(_adapt(p) for p in params))
        cols = [c[0] for c in cur.description] if cur.description else []
        return [_normalize_row(dict(zip(cols, r))) for r in cur.fetchall()]

    def fetchone(self, sql: str, params: Iterable = ()) -> dict | None:
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: Iterable = ()) -> Any:
        row = self.fetchone(sql, params)
        if not row:
            return None
        return next(iter(row.values()))

    def execute(self, sql: str, params: Iterable = ()) -> None:
        self._execute(sql, tuple(_adapt(p) for p in params))

    def insert(self, table: str, values: dict) -> str:
        values = dict(values)
        if table not in NO_ID_TABLES:
            values.setdefault("id", new_id())
        cols = list(values.keys())
        sql = f"insert into {table} ({', '.join(cols)}) values ({', '.join('?' for _ in cols)})"
        self.execute(sql, [values[c] for c in cols])
        return values.get("id")

    def update(self, table: str, row_id: str, values: dict, key: str = "id") -> None:
        if not values:
            return
        sets = ", ".join(f"{c} = ?" for c in values)
        self.execute(f"update {table} set {sets} where {key} = ?", [*values.values(), row_id])

    def get(self, table: str, row_id: str) -> dict | None:
        return self.fetchone(f"select * from {table} where id = ?", [row_id])


class SQLiteDatabase(BaseDatabase):
    dialect = "sqlite"

    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.execute("pragma foreign_keys = on")
        self._conn.execute("pragma journal_mode = wal") if self.path != ":memory:" else None
        self._lock = threading.RLock()
        self._depth = 0

    def _execute(self, sql: str, params: tuple):
        with self._lock:
            try:
                return self._conn.execute(sql, params)
            except sqlite3.IntegrityError as exc:
                raise IntegrityError(str(exc)) from exc
            except sqlite3.Error as exc:
                raise DatabaseError(f"{exc} | SQL: {sql[:200]}") from exc

    @contextmanager
    def transaction(self):
        with self._lock:
            outer = self._depth == 0
            sp = f"sp{self._depth}"
            self._conn.execute("begin" if outer else f"savepoint {sp}")
            self._depth += 1
            try:
                yield
            except BaseException:
                self._depth -= 1
                self._conn.execute("rollback" if outer else f"rollback to {sp}")
                if not outer:
                    self._conn.execute(f"release {sp}")
                raise
            else:
                self._depth -= 1
                self._conn.execute("commit" if outer else f"release {sp}")

    # Columns added by later migrations (005+). SQLite lacks "add column if not exists", so they are added here.
    EXTRA_COLUMNS = {
        "firms": {"serial_no": "TEXT", "client_code": "TEXT", "client_code_updated_at": "TEXT"},
        "clients": {"contact_person": "TEXT", "aadhaar_masked": "TEXT", "signup_source": "TEXT NOT NULL DEFAULT 'firm'",
                   "tan": "TEXT", "is_tds_deductor": "INTEGER NOT NULL DEFAULT 0"},
        "invoices": {"tds_section": "TEXT", "tds_rate": "TEXT NOT NULL DEFAULT '0.00'", "tds_amount": "TEXT NOT NULL DEFAULT '0.00'",
                    "tds_status": "TEXT NOT NULL DEFAULT 'not_applicable'"},
    }
    EXTRA_TABLES_SQL = """
        create table if not exists tds_returns (
            id TEXT primary key, firm_id TEXT not null, client_id TEXT not null, return_type TEXT not null default '26Q',
            quarter TEXT not null, rules_version TEXT not null, status TEXT not null default 'draft',
            data TEXT not null default '{}', warnings TEXT not null default '[]', external_ack_no TEXT,
            prepared_by TEXT, approved_by TEXT, approved_at TEXT, created_at TEXT not null default CURRENT_TIMESTAMP,
            unique (client_id, return_type, quarter)
        );
    """

    def migrate(self) -> None:
        sql = (MIGRATIONS_DIR / "001_schema.sql").read_text(encoding="utf-8")  # 002-004 are Supabase-only
        with self._lock:
            self._conn.executescript(pg_to_sqlite(sql))
            for table, cols in self.EXTRA_COLUMNS.items():
                have = {r[1] for r in self._conn.execute(f"pragma table_info({table})")}
                for col, decl in cols.items():
                    if col not in have:
                        self._conn.execute(f"alter table {table} add column {col} {decl}")
            self._conn.executescript(self.EXTRA_TABLES_SQL)
            self._conn.execute("create unique index if not exists uq_firms_serial on firms(serial_no) where serial_no is not null")
            self._conn.execute("create unique index if not exists uq_firms_client_code on firms(client_code) where client_code is not null")


class PostgresDatabase(BaseDatabase):
    """Supabase Postgres via pg8000 (pure Python driver).

    The connection role must be able to ``SET ROLE authenticated`` (true for the Supabase
    ``postgres`` role). Queries for a logged-in user run with RLS; system tasks
    (registration bootstrap, audit) run without a user id and rely on service-layer checks.
    """

    dialect = "postgres"

    def __init__(self, dsn: str):
        import pg8000.dbapi  # noqa: F401  (import check)
        from urllib.parse import urlparse, unquote

        u = urlparse(dsn)
        self._params = dict(
            user=unquote(u.username or "postgres"), password=unquote(u.password or ""),
            host=u.hostname, port=u.port or 5432, database=(u.path or "/postgres").lstrip("/") or "postgres",
            ssl_context=True,
        )
        self._local = threading.local()

    def _conn(self):
        import pg8000.dbapi

        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = pg8000.dbapi.connect(**self._params)
            self._local.conn = conn
            self._local.depth = 0
        return conn

    @staticmethod
    def _translate(sql: str) -> str:
        return sql.replace("?", "%s")

    def _apply_identity(self, cur) -> None:
        uid = current_user_id.get()
        if uid:
            cur.execute("set local role authenticated")
            claims = json.dumps({"sub": uid, "role": "authenticated"})
            cur.execute("select set_config('request.jwt.claims', %s, true)", (claims,))

    def _execute(self, sql: str, params: tuple):
        import pg8000.dbapi

        conn = self._conn()
        cur = conn.cursor()
        try:
            if self._local.depth == 0:
                self._apply_identity(cur)
                cur.execute(self._translate(sql), params)
                conn.commit()
            else:
                cur.execute(self._translate(sql), params)
            return cur
        except pg8000.dbapi.IntegrityError as exc:
            if self._local.depth == 0:
                conn.rollback()
            raise IntegrityError(str(exc)) from exc
        except pg8000.dbapi.Error as exc:
            if self._local.depth == 0:
                conn.rollback()
            raise DatabaseError(str(exc)) from exc

    @contextmanager
    def transaction(self):
        conn = self._conn()
        outer = self._local.depth == 0
        if outer:
            self._apply_identity(conn.cursor())
        self._local.depth += 1
        try:
            yield
        except BaseException:
            self._local.depth -= 1
            if outer:
                conn.rollback()
            raise
        else:
            self._local.depth -= 1
            if outer:
                conn.commit()

    def migrate(self) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("create table if not exists schema_migrations (name text primary key, applied_at timestamptz default now())")
        conn.commit()
        for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
            cur.execute("select 1 from schema_migrations where name = %s", (f.name,))
            if cur.fetchone():
                continue
            cur.execute(f.read_text(encoding="utf-8"))
            cur.execute("insert into schema_migrations(name) values (%s)", (f.name,))
            conn.commit()


_db: BaseDatabase | None = None
_db_lock = threading.Lock()


def get_db() -> BaseDatabase:
    global _db
    with _db_lock:
        if _db is None:
            if settings.backend == "supabase":
                if not settings.supabase_db_url:
                    raise DatabaseError("DATA_BACKEND=supabase but SUPABASE_DB_URL is not set. See README.")
                _db = PostgresDatabase(settings.supabase_db_url)
            else:
                _db = SQLiteDatabase(settings.sqlite_path)
                _db.migrate()
        return _db


def set_db(db: BaseDatabase) -> None:
    """Used by tests to inject an isolated database."""
    global _db
    _db = db
