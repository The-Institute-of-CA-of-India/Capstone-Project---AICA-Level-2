"""Central configuration. Values come from environment variables or a local .env file."""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

try:  # optional dependency
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

try:
    # Use the operating system's certificate store for HTTPS, so calls work where antivirus or a
    # corporate proxy inspects TLS with its own OS-trusted root. Certificate verification stays on.
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover
    pass

IST = timezone(timedelta(hours=5, minutes=30))


def save_setting(name: str, value: str) -> None:
    """Add or update NAME=value in the local .env file (used for non-secret values such as a chat ID)."""
    env = ROOT / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == name:
            lines[i] = f"{name}={value}"
            break
    else:
        lines.append(f"{name}={value}")
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[name] = value


def setting(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def db_backend() -> str:
    return setting("CASHSENSE_DB", "sqlite").lower()


def sqlite_path() -> Path:
    p = Path(setting("CASHSENSE_SQLITE", "cashsense.db"))
    return p if p.is_absolute() else ROOT / p


def erp_backend() -> str:
    return setting("CASHSENSE_ERP", "mock").lower()


def as_of_date() -> date:
    """Demo 'today'. The sample data covers FY 2025-26, so the default is 31-Mar-2026."""
    return date.fromisoformat(setting("CASHSENSE_AS_OF", "2026-03-31"))


def now_ist() -> datetime:
    """India time, because servers usually run on UTC."""
    return datetime.now(IST)
