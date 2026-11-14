"""
Where things live, both when running from source and as an installed program.

Installed (PyInstaller) builds unpack read-only resources into sys._MEIPASS;
anything the program writes goes to the user's own application-data folder,
so settings survive updates and the program folder never needs to be writable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .model import APP_NAME

FROZEN = bool(getattr(sys, "frozen", False))
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
SOURCE_DIR = Path(__file__).resolve().parents[1]


def static_dir() -> Path:
    return BUNDLE_DIR / "static"


def data_dir() -> Path:
    """Per-user folder for settings and logs (never contains client documents)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    d = base / APP_NAME
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = SOURCE_DIR
    return d


def cache_dir() -> Path:
    """Per-user, non-roaming folder for the app window's browser profile (never client documents)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / APP_NAME
        try:
            base.mkdir(parents=True, exist_ok=True)
            return base
        except OSError:
            pass
    return data_dir()


def bundled_tessdata() -> Path | None:
    """OCR language data shipped inside the installed program, if any."""
    for cand in (BUNDLE_DIR / "tessdata", SOURCE_DIR / "packaging" / "tessdata"):
        if (cand / "eng.traineddata").exists():
            return cand
    return None


def config_file() -> Path:
    return data_dir() / "settings.json"
