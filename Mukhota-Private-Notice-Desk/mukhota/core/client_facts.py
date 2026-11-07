"""Per-client facts sheet (status, auditor, turnover, filing dates...), encrypted, used only on this computer.

Facts fill [[TO CONFIRM: ...]] placeholders locally; they are never sent to Claude.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .config import APP_ROOT
from .models import UserFacingError
from .tokens import TokenRegistry, get_or_create_key, normalise

log = logging.getLogger("mukhota.facts")
FACTS_DIR = APP_ROOT / "clients"

# (key, label, per-assessment-year?, placeholder keywords - the longest match wins)
FIELDS: list[tuple[str, str, bool, list[str]]] = [
    ("status", "Status (company / firm / LLP / individual...)", False, ["status"]),
    ("business", "Nature of business or profession", False, ["nature of business", "business", "profession"]),
    ("auditor", "Auditor (name, firm, membership no. / FRN)", False, ["auditor", "frn", "membership"]),
    ("signatory", "Authorised signatory name", False, ["authorised signatory", "signatory"]),
    ("designation", "Signatory designation", False, ["designation"]),
    ("place", "Place", False, ["place"]),
    ("turnover", "Turnover as per audited accounts (Rs.)", True, ["turnover", "gross receipts", "total sales"]),
    ("audit_form", "Audit report form (3CA-3CD / 3CB-3CD)", True, ["3ca-3cd / 3cb-3cd", "form no", "3ca", "3cb"]),
    ("audit_date", "Date audit report signed", True, ["date of signing"]),
    ("upload_date", "Date audit report uploaded", True, ["date of uploading", "uploading", "uploaded"]),
    ("audit_ack", "Audit report acknowledgement no.", True, ["acknowledgement number", "acknowledgement no"]),
    ("itr_date", "Date of filing ITR", True, ["date of filing itr", "filing itr", "itr filed", "filing of return"]),
    ("itr_ack", "ITR acknowledgement no.", True, ["itr acknowledgement number", "itr acknowledgement"]),
]
YEAR_FIELDS = {k for k, _, per_year, _ in FIELDS if per_year}


def client_key(registry: TokenRegistry) -> tuple[str, str]:
    """(file key, display name) for the assessee of a notice: PAN, else GSTIN, else assessee name."""
    entries = registry.entries()
    for wanted in ("PAN", "GSTIN"):
        for e in entries:
            if e.pii_type == wanted:
                name = next((x.value for x in entries if x.token.startswith("[ASSESSEE")), e.value)
                return wanted + ":" + normalise(e.value, wanted), name
    for e in entries:
        if e.token.startswith("[ASSESSEE"):
            return "NAME:" + normalise(e.value, e.pii_type), e.value
    raise UserFacingError("This notice has no PAN, GSTIN or assessee name in its vault, so no facts sheet can be linked.")


def _path(key: str) -> Path:
    return FACTS_DIR / (hashlib.sha256(key.encode("utf-8")).hexdigest()[:20] + ".facts")


def load(key: str) -> dict[str, Any]:
    """Facts for a client: {"name", "common": {...}, "years": {"2024-25": {...}}}."""
    p = _path(key)
    if not p.exists():
        return {"name": "", "common": {}, "years": {}}
    try:
        return json.loads(Fernet(get_or_create_key()).decrypt(p.read_bytes()).decode("utf-8"))
    except (InvalidToken, OSError, json.JSONDecodeError) as exc:
        raise UserFacingError("This client's facts sheet could not be opened on this Windows login.") from exc


def save(key: str, data: dict[str, Any]) -> None:
    """Encrypt and write the facts sheet."""
    FACTS_DIR.mkdir(parents=True, exist_ok=True)
    blob = Fernet(get_or_create_key()).encrypt(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    _path(key).write_bytes(blob)
    log.info("Facts sheet saved (%d common, %d year sets)", len(data.get("common", {})), len(data.get("years", {})))


def get(data: dict[str, Any], field: str, ay: str) -> str:
    if field in YEAR_FIELDS:
        return str(data.get("years", {}).get(ay, {}).get(field, ""))
    return str(data.get("common", {}).get(field, ""))


def put(data: dict[str, Any], field: str, ay: str, value: str) -> None:
    if field in YEAR_FIELDS:
        data.setdefault("years", {}).setdefault(ay, {})[field] = value
    else:
        data.setdefault("common", {})[field] = value


def field_for_placeholder(placeholder: str) -> str | None:
    """The facts field a [[TO CONFIRM: ...]] placeholder asks for, by its most specific keyword."""
    text = placeholder.lower()
    if not text.startswith("[[to confirm"):
        return None
    best, best_len = None, 0
    for key, _, _, words in FIELDS:
        for w in words:
            if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", text) and len(w) > best_len:
                best, best_len = key, len(w)
    return best


def suggestions(placeholders: list[str], data: dict[str, Any], ay: str) -> dict[str, str]:
    """Placeholder -> saved value, for placeholders the facts sheet can answer."""
    out = {}
    for ph in placeholders:
        f = field_for_placeholder(ph)
        if f and get(data, f, ay):
            out[ph] = get(data, f, ay)
    return out


def learn(data: dict[str, Any], values: dict[str, str], ay: str) -> int:
    """Store typed placeholder answers back into the sheet; returns how many fields changed."""
    changed = 0
    for ph, val in values.items():
        f = field_for_placeholder(ph)
        if f and val.strip() and get(data, f, ay) != val.strip():
            put(data, f, ay, val.strip())
            changed += 1
    return changed
