"""The do-not-redact allowlist (allowlist.yaml)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import UserFacingError

_PUNCT_EDGE = ".,;:()[]{}\"'"


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w&/ ]", " ", text.lower()).split())


@dataclass
class Allowlist:
    """Patterns and words that must never be redacted."""

    patterns: list[re.Pattern] = field(default_factory=list)
    context_patterns: list[re.Pattern] = field(default_factory=list)
    department_patterns: list[re.Pattern] = field(default_factory=list)
    words: set[str] = field(default_factory=set)

    @classmethod
    def from_dict(cls, data: dict) -> "Allowlist":
        """Build from parsed YAML; raises UserFacingError on a bad regex."""
        def compile_all(key: str) -> list[re.Pattern]:
            out = []
            for p in data.get(key) or []:
                try:
                    out.append(re.compile(str(p)))
                except re.error as exc:
                    raise UserFacingError(
                        f"The allowlist entry under '{key}' is not a valid pattern: {p}"
                    ) from exc
            return out

        words = {_norm(str(w)) for w in (data.get("words") or []) if str(w).strip()}
        return cls(
            compile_all("patterns"),
            compile_all("context_patterns"),
            compile_all("department_patterns"),
            words,
        )

    @classmethod
    def load(cls, path: Path) -> "Allowlist":
        """Load allowlist.yaml (missing file = empty allowlist)."""
        if not path.exists():
            return cls()
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise UserFacingError("allowlist.yaml could not be read. Please fix it in Settings.") from exc
        return cls.from_dict(data)

    def is_allowed(self, text: str, chunk: str = "", before: str = "") -> bool:
        """True if ``text`` must be left visible.

        ``chunk`` is the whitespace-delimited token containing the match (so a
        number inside a notice DIN is protected) and ``before`` is the text
        immediately preceding it (for labels such as "Document Identification Number").
        """
        t = text.strip()
        if not t:
            return True
        if any(p.fullmatch(t) for p in self.patterns):
            return True
        c = chunk.strip().strip(_PUNCT_EDGE)
        if c and c != t and any(p.fullmatch(c) for p in self.patterns):
            return True
        if before and any(p.search(before) for p in self.context_patterns):
            return True
        n = _norm(t)
        return n in self.words or n.removeprefix("the ") in self.words

    def is_department(self, text: str) -> bool:
        """True for department / government body names (used for low-confidence name hits)."""
        return any(p.search(text) for p in self.department_patterns)
