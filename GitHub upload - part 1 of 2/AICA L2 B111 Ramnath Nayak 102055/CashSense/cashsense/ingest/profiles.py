"""Bank statement profiles: format facts about each bank's statements, used to sanity-check AI readings.

Sample Kaveri Bank (photo statements) prints NEFT/RTGS/SWIFT/FX references as one letter + 14 digits
(e.g. N26032721643286). A duplicated or dropped digit changes the length, so it can be caught even
though the money columns still agree.
"""
from __future__ import annotations

import re

PROFILES = {
    "ZZKB": {"bank": "Sample Kaveri Bank (SAMPLE)", "ref_regex": re.compile(r"[-/]([NRSFI]\d{6,})$"), "ref_len": 15},
}


def ref_problem(description: str, ifsc: str) -> str | None:
    p = PROFILES.get((ifsc or "")[:4])
    if not p:
        return None
    m = p["ref_regex"].search((description or "").replace(" ", ""))
    if m and len(m.group(1)) != p["ref_len"]:
        return f"reference {m.group(1)} has {len(m.group(1))} characters, expected {p['ref_len']} - possible misread"
    return None
