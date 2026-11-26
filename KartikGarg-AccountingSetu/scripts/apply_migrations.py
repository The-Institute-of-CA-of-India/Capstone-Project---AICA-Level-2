"""Apply database/migrations/*.sql to the Supabase Postgres in SUPABASE_DB_URL (idempotent, tracked).

    python -m scripts.apply_migrations          # apply pending migrations
    python -m scripts.apply_migrations --check  # only list existing public tables (read-only)

Safety: refuses to run unless the connection's project ref matches EXPECTED_PROJECT_REF (if set) and
the target has no unexpected tables in the public schema.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import BASE_DIR, settings  # noqa: E402

MIGRATIONS = sorted((BASE_DIR / "database" / "migrations").glob("*.sql"))


def connect():
    import pg8000.native

    u = urlparse(settings.supabase_db_url)
    return pg8000.native.Connection(user=unquote(u.username), password=unquote(u.password or ""), host=u.hostname,
                                    port=u.port or 5432, database=(u.path or "/postgres").lstrip("/"), ssl_context=True)


def main():
    if not settings.supabase_db_url:
        raise SystemExit("SUPABASE_DB_URL is not set")
    user = unquote(urlparse(settings.supabase_db_url).username or "")
    expected = os.getenv("EXPECTED_PROJECT_REF", "")
    if expected and not user.endswith("." + expected):
        raise SystemExit(f"Refusing: connection user {user} is not project {expected}")
    conn = connect()
    tables = [r[0] for r in conn.run("select table_name from information_schema.tables where table_schema='public' order by 1")]
    print(f"Connected as {user}. public tables: {tables or 'none'}")
    if "--check" in sys.argv:
        return
    import re

    ours = set()
    for f in MIGRATIONS:  # every migration that creates a table counts as "ours", not just 001
        ours |= set(re.findall(r"create table if not exists (\w+)", f.read_text(encoding="utf-8")))
    foreign = [t for t in tables if t not in ours and t != "schema_migrations"]
    if foreign:
        raise SystemExit(f"Refusing: target has tables not created by Accounting Setu: {foreign}")
    if "schema_migrations" not in tables and tables:
        raise SystemExit("Refusing: tables exist but no migration history")
    conn.run("create table if not exists schema_migrations (name text primary key, applied_at timestamptz default now())")
    done = {r[0] for r in conn.run("select name from schema_migrations")}
    for f in MIGRATIONS:
        if f.name in done:
            print(f"skip   {f.name}")
            continue
        conn.run("begin")
        try:
            conn.execute_simple(f.read_text(encoding="utf-8"))
            conn.run("insert into schema_migrations(name) values (:n)", n=f.name)
            conn.run("commit")
            print(f"applied {f.name}")
        except Exception:
            conn.run("rollback")
            raise
    n = conn.run("select count(*) from information_schema.tables where table_schema='public'")[0][0]
    print(f"done — {n} tables in public schema")


if __name__ == "__main__":
    main()
