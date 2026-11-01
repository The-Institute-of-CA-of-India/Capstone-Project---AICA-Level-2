"""Application settings: where the SQLite database lives.

The settings file (dsc_config.json) is kept next to the application so the
whole folder can be copied to another PC. The DSC_MANAGER_DB environment
variable overrides it (used by the automated tests).
"""
import json
import os
import sys
import uuid

# Built as an .exe, keep settings and data next to the .exe itself (the
# program's own files are unpacked to a temporary folder each time it runs).
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DSC_MANAGER_CONFIG lets the automated tests use their own settings file.
CONFIG_PATH = os.environ.get("DSC_MANAGER_CONFIG") or os.path.join(APP_DIR, "dsc_config.json")
# The program's own files (icon): inside the .exe they are unpacked to a temporary folder.
PACKAGE_DIR = os.path.join(getattr(sys, "_MEIPASS", ""), "dsc_manager") if getattr(sys, "frozen", False) \
    else os.path.dirname(os.path.abspath(__file__))


DB_FILENAME = "dsc_manager.db"
DEFAULT_DB_PATH = os.path.join(APP_DIR, "data", DB_FILENAME)


def asset(name):
    return os.path.join(PACKAGE_DIR, "assets", name)


def load_config():
    """Return the saved settings dict, or None on first launch."""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            cfg = json.load(fh)
        return cfg if isinstance(cfg, dict) and cfg.get("db_path") else None
    except (OSError, ValueError):
        return None


def save_config(cfg):
    """Save settings, keeping any keys of the existing file that cfg does not set."""
    merged = _read_raw()
    merged.update(cfg)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2)


def _read_raw():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            cfg = json.load(fh)
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError):
        return {}


def get_setting(key, default=None):
    """A per-PC setting kept in dsc_config.json (auto-backup folder, text size, ...)."""
    return _read_raw().get(key, default)


def set_setting(key, value):
    save_config({key: value})


def token_driver_paths():
    """Extra PKCS#11 driver DLLs added by the user (per PC, so kept here, not in the database)."""
    paths = _read_raw().get("token_drivers", [])
    return [p for p in paths if isinstance(p, str)]


def set_token_driver_paths(paths):
    save_config({"token_drivers": list(paths)})


def env_db_path():
    return os.environ.get("DSC_MANAGER_DB")


def moved_db_path(path):
    """After the folder is copied to another PC the saved path no longer exists:
    return the database next to the application, if there is one, else None."""
    if os.path.isdir(os.path.dirname(path)) or not os.path.exists(DEFAULT_DB_PATH):
        return None
    return DEFAULT_DB_PATH


def check_folder_writable(folder):
    """Return None if the folder exists and is writable, else an error message."""
    if not folder:
        return "No folder selected."
    if not os.path.isdir(folder):
        return f"Folder does not exist:\n{folder}"
    probe = os.path.join(folder, f".dsc_write_test_{uuid.uuid4().hex}")
    try:
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
    except OSError as exc:
        return f"Cannot write to this folder:\n{folder}\n\n{exc}"
    return None
