"""Loading and saving ``config.yaml``. All paths are resolved relative to the app folder."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config.yaml"

DEFAULTS: dict[str, Any] = {
    "ocr": {"dpi": 300, "low_confidence_threshold": 0.80},
    "ingest": {"min_text_chars": 30, "image_coverage_ratio": 0.80},
    "detection": {
        "accept_threshold": 0.60,
        "redact_officer": True,
        "spacy_model": "en_core_web_sm",
        "fuzzy_threshold": 0.88,
        "visual_dpi": 150,
        "propagate_values": True,
    },
    "redaction": {"image_dpi": 300, "jpeg_quality": 85, "padding": 1.5},
    "verify": {"ocr_dpi": 300, "tail_digits": 4, "tail_label_window": 40},
    "ai": {"model": "claude-opus-5-5", "effort": "medium", "max_tokens": 48000, "web_search_max_uses": 6,
           "monthly_limit_usd": 0},
    # Other AI providers for Draft Reply (keys live in Windows Credential Manager, not here).
    "providers": {
        pid: {"base_url": url, "model": "", "price_in": 0.0, "price_out": 0.0, "price_search": 0.0, "max_tokens": 0}
        for pid, url in (
            ("openai", "https://api.openai.com/v1"),
            ("gemini", "https://generativelanguage.googleapis.com"),
            ("deepseek", "https://api.deepseek.com"),
            ("mistral", "https://api.mistral.ai/v1"),
            ("groq", "https://api.groq.com/openai/v1"),
            ("openrouter", "https://openrouter.ai/api/v1"),
            ("ollama", "http://localhost:11434/v1"),
            ("lmstudio", "http://localhost:1234/v1"),
            ("custom", ""),
        )
    },
    "notifications": {"due_reminders": True},
    "law_library": {"enabled": True, "max_excerpts": 8, "max_chars": 14000},
    "paths": {
        "allowlist": "allowlist.yaml",
        "client_master": "client_master.csv",
        "log_dir": "logs",
        "output_root": "",
    },
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Read config.yaml merged over built-in defaults (missing file = defaults)."""
    data: dict[str, Any] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    return _merge(DEFAULTS, data)


def save_config(cfg: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    """Write the settings back to config.yaml."""
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False, allow_unicode=True)


def resolve_path(cfg: dict[str, Any], key: str) -> Path:
    """Resolve a ``paths`` entry; relative paths are taken from the app folder."""
    p = Path(cfg["paths"][key])
    return p if p.is_absolute() else APP_ROOT / p
