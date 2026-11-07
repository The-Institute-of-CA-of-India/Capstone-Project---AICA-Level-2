"""Logging to mukhota.log with a formatter that masks anything that looks like PII."""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_SCRUB_PATTERNS = [
    re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b"),  # GSTIN
    re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),  # PAN
    re.compile(r"\b[A-Z]{4}\d{5}[A-Z]\b"),  # TAN
    re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}"),  # e-mail
    re.compile(r"(?<!\d)\d[\d \-]{7,20}\d(?!\d)"),  # long digit runs: Aadhaar, phone, account
]
_PATH = re.compile(r"[A-Za-z]:[\\/][^'\"\n<>|]*")


def _mask_path(m: re.Match) -> str:
    p = m.group(0)
    low = p.lower()
    # Code paths are useful for debugging; user document paths may hold client names.
    if "site-packages" in low or "\\mukhota\\mukhota\\" in low or "\\python3" in low or "\\lib\\" in low:
        return p
    return "<path>"


def scrub(text: str) -> str:
    """Mask PII-like substrings and user file paths."""
    text = _PATH.sub(_mask_path, text)
    for pat in _SCRUB_PATTERNS:
        text = pat.sub("<masked>", text)
    return text


class ScrubbingFormatter(logging.Formatter):
    """Formatter that scrubs the formatted record, including tracebacks (the timestamp is kept)."""

    def format(self, record: logging.LogRecord) -> str:
        return f"{self.formatTime(record)} {scrub(super().format(record))}"


def setup_logging(log_dir: Path) -> Path:
    """Configure the root ``mukhota`` logger; returns the log file path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "mukhota.log"
    handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(ScrubbingFormatter("%(levelname)-7s %(name)s: %(message)s"))
    logger = logging.getLogger("mukhota")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return log_file
