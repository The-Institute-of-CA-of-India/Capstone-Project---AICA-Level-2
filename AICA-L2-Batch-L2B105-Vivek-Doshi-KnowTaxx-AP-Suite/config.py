"""Application configuration: ports, paths and secrets.

Environment variables (all optional):
    KTAP_HOST       bind address (default 0.0.0.0 so LAN devices can connect)
    KTAP_PORT       port (default 5000)
    KTAP_DATA_DIR   root for instance/ and data/ (default: project folder)
    KTAP_SECRET_KEY session signing key (default: generated once, stored in instance/)
    TESSERACT_CMD   full path to tesseract.exe (default: PATH and standard locations)
"""
import os
import secrets
import sys
from datetime import timedelta
from pathlib import Path

VERSION = "1.0.0"
FROZEN = getattr(sys, "frozen", False)
PROJECT_ROOT = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("KTAP_DATA_DIR") or PROJECT_ROOT)
INSTANCE_DIR = DATA_ROOT / "instance"


def _load_secret_key():
    env_key = os.environ.get("KTAP_SECRET_KEY")
    if env_key:
        return env_key
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    key_file = INSTANCE_DIR / "secret_key.txt"
    if key_file.exists():
        return key_file.read_text(encoding="ascii").strip()
    key = secrets.token_hex(32)
    key_file.write_text(key, encoding="ascii")
    return key


class Config:
    APP_NAME = "KnowTaxx AP & Expense Intelligence Suite"
    VERSION = VERSION
    HOST = os.environ.get("KTAP_HOST", "0.0.0.0")
    PORT = int(os.environ.get("KTAP_PORT", "5000"))

    SECRET_KEY = _load_secret_key()
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + (INSTANCE_DIR / "apsuite.db").as_posix()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    FILES_ROOT = str(DATA_ROOT / "data" / "files")
    BACKUP_ROOT = str(DATA_ROOT / "data" / "backups")
    CERT_ROOT = str(DATA_ROOT / "data" / "certs")
    MAX_CONTENT_LENGTH = 40 * 1024 * 1024  # one request: 40 MB
    MAX_FILE_BYTES = 20 * 1024 * 1024      # one document: 20 MB
    OCR_MAX_PDF_PAGES = 10

    # Session: 10-hour expiry
    PERMANENT_SESSION_LIFETIME = timedelta(hours=10)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_TIME_LIMIT = None  # token lives as long as the session (needed for offline sync)

    # Account lockout
    MAX_FAILED_LOGINS = 5
    LOCKOUT_MINUTES = 15

    # Public vendor registration throttle
    VENDOR_REG_LIMIT_PER_HOUR = 10

    EMAIL_LISTENER_ENABLED = True
    ITEMS_PER_PAGE = 25
    # Confidence at or above which a captured invoice stays "auto_captured"
    OCR_HIGH_CONFIDENCE = 0.8
