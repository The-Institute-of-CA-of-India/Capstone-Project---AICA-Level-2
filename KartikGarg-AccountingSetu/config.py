"""Central configuration for Accounting Setu.

All secrets come from environment variables (optionally loaded from a local .env file).
Nothing secret is hardcoded here.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional dependency
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

BASE_DIR = Path(__file__).resolve().parent


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    app_name: str = "Accounting Setu"
    tagline: str = "From Documents to Complete Accounting."
    environment: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))

    # --- Backend selection -------------------------------------------------
    # "local"    -> SQLite + local private file storage (no external services)
    # "supabase" -> Supabase Postgres (RLS enforced) + Supabase Auth + Storage
    backend: str = field(default_factory=lambda: os.getenv("DATA_BACKEND", "local").lower())

    # Local backend
    sqlite_path: Path = field(
        default_factory=lambda: Path(os.getenv("SQLITE_PATH", str(BASE_DIR / "data" / "accounting_setu.db")))
    )
    storage_dir: Path = field(
        default_factory=lambda: Path(os.getenv("LOCAL_STORAGE_DIR", str(BASE_DIR / "data" / "storage")))
    )

    # Supabase backend
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_anon_key: str = field(default_factory=lambda: os.getenv("SUPABASE_ANON_KEY", ""))
    # Server-side only. Never sent to the browser. Used only for bootstrap tasks.
    supabase_service_role_key: str = field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))
    supabase_db_url: str = field(default_factory=lambda: os.getenv("SUPABASE_DB_URL", ""))
    supabase_bucket: str = field(default_factory=lambda: os.getenv("SUPABASE_STORAGE_BUCKET", "documents"))

    # --- AI / OCR providers ------------------------------------------------
    ai_provider: str = field(default_factory=lambda: os.getenv("AI_PROVIDER", "auto").lower())  # auto|anthropic|local
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5"))
    ocr_provider: str = field(default_factory=lambda: os.getenv("OCR_PROVIDER", "auto").lower())  # auto|tesseract|ai|none
    tesseract_cmd: str = field(default_factory=lambda: os.getenv("TESSERACT_CMD", ""))

    # --- Uploads -------------------------------------------------------------
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_MB", "25")))
    allowed_extensions: tuple = (".jpg", ".jpeg", ".png", ".pdf", ".xlsx", ".csv")

    # --- Email (optional) ------------------------------------------------------
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    smtp_from: str = field(default_factory=lambda: os.getenv("SMTP_FROM", ""))
    app_base_url: str = field(default_factory=lambda: os.getenv("APP_BASE_URL", "http://localhost:8501"))

    # --- Platform bootstrap ----------------------------------------------------
    super_admin_email: str = field(default_factory=lambda: os.getenv("SUPER_ADMIN_EMAIL", ""))
    super_admin_password: str = field(default_factory=lambda: os.getenv("SUPER_ADMIN_PASSWORD", ""))
    session_timeout_minutes: int = field(default_factory=lambda: int(os.getenv("SESSION_TIMEOUT_MINUTES", "60")))
    load_demo_data: bool = field(default_factory=lambda: _bool("LOAD_DEMO_DATA", False))

    # GST rules version used by default (rules are versioned in services/gst_rules.py)
    gst_rules_version: str = field(default_factory=lambda: os.getenv("GST_RULES_VERSION", "2025.1"))

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def anthropic_enabled(self) -> bool:
        return bool(self.anthropic_api_key) and self.ai_provider in {"auto", "anthropic"}

    @property
    def tesseract_available(self) -> bool:
        if self.tesseract_cmd and Path(self.tesseract_cmd).exists():
            return True
        return shutil.which("tesseract") is not None

    def missing_configuration(self) -> list[str]:
        """Human-readable list of configuration that is missing for the selected backend."""
        missing: list[str] = []
        if self.backend == "supabase":
            for key, val in {
                "SUPABASE_URL": self.supabase_url,
                "SUPABASE_ANON_KEY": self.supabase_anon_key,
                "SUPABASE_DB_URL": self.supabase_db_url,
            }.items():
                if not val:
                    missing.append(key)
        if not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY (optional: AI extraction falls back to local rule-based parser)")
        if not self.tesseract_available:
            missing.append("Tesseract OCR binary (optional: scanned PDFs/images go to manual review without it)")
        return missing


settings = Settings()
