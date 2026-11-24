"""Load agent instructions from skills/<name>/SKILL.md (the same files ship in the Claude plugin)."""
from __future__ import annotations

from functools import lru_cache

from .config import ROOT


@lru_cache(maxsize=None)
def load_skill(name: str) -> str:
    text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.strip()
