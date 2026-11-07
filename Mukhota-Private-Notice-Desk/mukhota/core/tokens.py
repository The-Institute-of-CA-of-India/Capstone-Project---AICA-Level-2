"""Stable role tokens ([PAN_1], [ASSESSEE] ...) and the encrypted token vault."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .models import VISUAL_TYPES, UserFacingError

log = logging.getLogger("mukhota.tokens")

KEYRING_SERVICE = "Mukhota"
KEYRING_USER = "vault-master"

TOKEN_PREFIX: dict[str, str] = {
    "PAN": "PAN", "TAN": "TAN", "GSTIN": "GSTIN", "AADHAAR": "AADHAAR",
    "MOBILE": "MOBILE", "LANDLINE": "PHONE", "EMAIL": "EMAIL",
    "BANK_AC": "BANK_AC", "IFSC": "IFSC", "CIN": "CIN", "LLPIN": "LLPIN",
    "DIN": "DIN", "UDYAM": "UDYAM", "IEC": "IEC", "PASSPORT": "PASSPORT",
    "VEHICLE": "VEHICLE", "PIN": "PIN", "NAME": "NAME", "ORG": "ORG",
    "ADDRESS": "ADDRESS", "OFFICER": "OFFICER", "WARD": "WARD",
    "QR": "QR", "BARCODE": "BARCODE", "SIGNATURE": "SIGNATURE", "STAMP": "STAMP",
    "MANUAL": "REDACTED", "TERM": "TERM",
}
ID_TYPES = {
    "PAN", "TAN", "GSTIN", "AADHAAR", "BANK_AC", "IFSC", "CIN", "LLPIN", "DIN",
    "UDYAM", "IEC", "PASSPORT", "VEHICLE", "PIN",
}
TOKEN_RE = re.compile(r"\[[A-Z]+(?:_[A-Z]+)*(?:_\d+)?\]")

_SYNONYMS = {
    "pvt": "private", "ltd": "limited", "co": "company", "corp": "corporation",
    "corpn": "corporation", "&": "and", "intl": "international", "bros": "brothers",
    "mfg": "manufacturing", "inds": "industries", "ent": "enterprises",
}
_TITLES = {"ms", "messrs", "shri", "smt", "sh", "mr", "mrs", "kumari", "kum", "dr", "sri", "shree"}


def norm_word(word: str) -> str:
    """Lower-case a word, strip punctuation and apply Pvt/Ltd style synonyms."""
    w = re.sub(r"[^\w&]", "", word.lower())
    return _SYNONYMS.get(w, w)


def normalise_name(text: str) -> str:
    """Normalise a name for matching: case, spacing, titles (M/s, Shri...) and synonyms."""
    words = [norm_word(w) for w in text.replace("/", "").split()]
    return " ".join(w for w in words if w and w not in _TITLES)


def normalise(value: str, pii_type: str) -> str:
    """Canonical form used to decide whether two values are 'the same'."""
    v = value.strip()
    if pii_type in ID_TYPES:
        return re.sub(r"[\s\-./]", "", v).upper()
    if pii_type == "MOBILE":
        digits = re.sub(r"\D", "", v)
        return digits[-10:]
    if pii_type == "LANDLINE":
        return re.sub(r"\D", "", v).lstrip("0")
    if pii_type == "EMAIL":
        return v.lower()
    if pii_type in VISUAL_TYPES or pii_type == "MANUAL":
        return v
    return normalise_name(v)


@dataclass
class VaultEntry:
    """One original value and where it appeared."""

    token: str
    value: str
    pii_type: str
    pages: set[int] = field(default_factory=set)


class TokenRegistry:
    """Assigns one stable token per unique (normalised) value."""

    def __init__(self) -> None:
        self._by_key: dict[str, VaultEntry] = {}
        self._counters: dict[str, int] = {}

    def _next(self, prefix: str) -> str:
        n = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = n
        if prefix == "ASSESSEE":
            return "[ASSESSEE]" if n == 1 else f"[ASSESSEE_{n}]"
        return f"[{prefix}_{n}]"

    def assign(self, value: str, pii_type: str, role: str = "", page: int = 0) -> str:
        """Return the token for ``value``, creating one if it is new."""
        key = normalise(value, pii_type) or value
        entry = self._by_key.get(key)
        if entry is None:
            prefix = re.sub(r"[^A-Z]", "_", role.upper()).strip("_") if role else TOKEN_PREFIX.get(pii_type, "REDACTED")
            entry = VaultEntry(self._next(prefix), value, pii_type)
            self._by_key[key] = entry
        entry.pages.add(page + 1)
        return entry.token

    def entries(self) -> list[VaultEntry]:
        """All vault entries in token order of creation."""
        return list(self._by_key.values())

    @classmethod
    def from_vault(cls, vault: dict[str, Any]) -> "TokenRegistry":
        """Rebuild a registry from a loaded vault so new tokens continue its numbering."""
        reg = cls()
        for token, e in vault.get("entries", {}).items():
            value, pii_type = str(e["value"]), e.get("pii_type", "")
            entry = VaultEntry(token, value, pii_type, set(e.get("pages", [])))
            reg._by_key[normalise(value, pii_type) or value] = entry
            m = re.fullmatch(r"\[([A-Z_]+?)(?:_(\d+))?\]", token)
            if m:
                n = int(m.group(2) or 1)
                reg._counters[m.group(1)] = max(reg._counters.get(m.group(1), 0), n)
        return reg


def get_or_create_key() -> bytes:
    """Fetch the Fernet key from Windows Credential Manager, creating it on first use."""
    try:
        import keyring

        stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
        if stored:
            return stored.encode("ascii")
        key = Fernet.generate_key()
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key.decode("ascii"))
        log.info("Created a new vault key in Windows Credential Manager")
        return key
    except Exception as exc:
        raise UserFacingError(
            "Mukhota could not access Windows Credential Manager to protect the token vault."
        ) from exc


def save_vault(registry: TokenRegistry, path: Path, meta: dict[str, Any]) -> None:
    """Encrypt the token map with Fernet and write ``<name>.vault``."""
    payload = {
        "app": "Mukhota",
        "meta": meta,
        "entries": {
            e.token: {"value": e.value, "pii_type": e.pii_type, "pages": sorted(e.pages)}
            for e in registry.entries()
        },
    }
    token = Fernet(get_or_create_key()).encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    path.write_bytes(token)
    log.info("Vault saved with %d tokens", len(payload["entries"]))


def load_vault(path: Path) -> dict[str, Any]:
    """Decrypt a vault file: ``{"meta": {...}, "entries": {token: {...}}}``."""
    try:
        raw = Fernet(get_or_create_key()).decrypt(Path(path).read_bytes())
    except InvalidToken as exc:
        raise UserFacingError(
            "This vault cannot be opened with the key on this computer (it was made on another Windows login)."
        ) from exc
    except OSError as exc:
        raise UserFacingError("The vault file could not be read.") from exc
    return json.loads(raw.decode("utf-8"))
