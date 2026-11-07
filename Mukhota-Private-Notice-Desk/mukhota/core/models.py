"""Shared data structures for Mukhota (no GUI dependencies).

All rectangles are PDF points in the *unrotated* page coordinate space,
stored as plain ``(x0, y0, x1, y1)`` tuples so they serialise cleanly.
"""
from __future__ import annotations

import bisect
import uuid
from dataclasses import dataclass, field

Rect = tuple[float, float, float, float]


class UserFacingError(Exception):
    """An error whose message is plain English, contains no PII and can be shown to the user."""


# Colour per PII type, used identically by the preview and the candidate list.
PII_COLOURS: dict[str, str] = {
    "PAN": "#F57C00",
    "TAN": "#FB8C00",
    "GSTIN": "#8E24AA",
    "AADHAAR": "#E53935",
    "MOBILE": "#1E88E5",
    "LANDLINE": "#1E88E5",
    "EMAIL": "#1E88E5",
    "BANK_AC": "#43A047",
    "IFSC": "#43A047",
    "NAME": "#D81B60",
    "ORG": "#D81B60",
    "ADDRESS": "#D81B60",
    "PIN": "#D81B60",
    "OFFICER": "#D81B60",
    "WARD": "#D81B60",
    "QR": "#757575",
    "BARCODE": "#757575",
    "SIGNATURE": "#757575",
    "STAMP": "#757575",
    "CIN": "#6D4C41",
    "LLPIN": "#6D4C41",
    "DIN": "#6D4C41",
    "UDYAM": "#6D4C41",
    "IEC": "#6D4C41",
    "PASSPORT": "#6D4C41",
    "VEHICLE": "#6D4C41",
    "MANUAL": "#3949AB",
    "TERM": "#3949AB",
}
DEFAULT_COLOUR = "#546E7A"

VISUAL_TYPES = {"QR", "BARCODE", "SIGNATURE", "STAMP"}
NAME_TYPES = {"NAME", "ORG", "ADDRESS", "PIN", "OFFICER", "WARD"}


def colour_for(pii_type: str) -> str:
    """Return the hex colour for a PII type."""
    return PII_COLOURS.get(pii_type, DEFAULT_COLOUR)


@dataclass
class Word:
    """A word on a page, from the text layer or from OCR."""

    text: str
    rect: Rect
    conf: float = 1.0
    line_key: tuple = (0, 0)


@dataclass
class PageInfo:
    """Per-page analysis result produced by :mod:`mukhota.core.ingest`."""

    index: int
    kind: str  # "TEXT" or "IMAGE"
    width: float
    height: float
    words: list[Word] = field(default_factory=list)
    avg_conf: float | None = None
    needs_review: bool = False
    reviewed_no_pii: bool = False


@dataclass
class Candidate:
    """One detected (or manually added) item to redact."""

    page: int
    bboxes: list[Rect]
    text: str
    pii_type: str
    confidence: float
    rule_id: str
    source: str = "auto"  # "auto" or "manual"
    accepted: bool = True
    role: str = ""
    token: str = ""
    cid: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class PageText:
    """Page words joined into searchable text, with offsets back to the words."""

    text: str
    word_spans: list[tuple[int, int]]  # (start, end) per word index
    lines: list[tuple[int, int, list[int]]]  # (start, end, word indexes) per line
    _order: list[int] = field(default_factory=list)  # word indexes sorted by start offset
    _starts: list[int] = field(default_factory=list)  # start offsets aligned with _order

    def word_indexes(self, start: int, end: int) -> list[int]:
        """Indexes of words overlapping the character span [start, end)."""
        out: list[int] = []
        k = max(bisect.bisect_right(self._starts, start) - 1, 0)
        while k < len(self._order) and self._starts[k] < end:
            i = self._order[k]
            if self.word_spans[i][1] > start:
                out.append(i)
            k += 1
        return out

    def rects(self, words: list[Word], start: int, end: int) -> list[Rect]:
        """Rectangles covering the span, one merged rectangle per text line."""
        per_line: dict[tuple, list[float]] = {}
        order: list[tuple] = []
        for i in self.word_indexes(start, end):
            ws, we = self.word_spans[i]
            w = words[i]
            x0, y0, x1, y1 = w.rect
            n = max(we - ws, 1)
            a = max(start, ws) - ws
            b = min(end, we) - ws
            sx0 = x0 + (x1 - x0) * a / n
            sx1 = x0 + (x1 - x0) * b / n
            key = w.line_key
            if key not in per_line:
                per_line[key] = [sx0, y0, sx1, y1]
                order.append(key)
            else:
                r = per_line[key]
                per_line[key] = [min(r[0], sx0), min(r[1], y0), max(r[2], sx1), max(r[3], y1)]
        return [tuple(per_line[k]) for k in order]  # type: ignore[misc]

    def min_conf(self, words: list[Word], start: int, end: int) -> float:
        """Lowest word confidence within the span (1.0 for text-layer words)."""
        idx = self.word_indexes(start, end)
        return min((words[i].conf for i in idx), default=1.0)


def build_page_text(words: list[Word]) -> PageText:
    """Join words into lines (single spaces) and lines into text (newlines)."""
    groups: dict[tuple, list[int]] = {}
    order: list[tuple] = []
    for i, w in enumerate(words):
        if w.line_key not in groups:
            groups[w.line_key] = []
            order.append(w.line_key)
        groups[w.line_key].append(i)

    parts: list[str] = []
    spans: list[tuple[int, int]] = [(0, 0)] * len(words)
    lines: list[tuple[int, int, list[int]]] = []
    pos = 0
    for li, key in enumerate(order):
        if li > 0:
            parts.append("\n")
            pos += 1
        line_start = pos
        for j, wi in enumerate(groups[key]):
            if j > 0:
                parts.append(" ")
                pos += 1
            t = words[wi].text
            spans[wi] = (pos, pos + len(t))
            parts.append(t)
            pos += len(t)
        lines.append((line_start, pos, groups[key]))

    order_idx = sorted(range(len(words)), key=lambda i: spans[i][0])
    return PageText("".join(parts), spans, lines, order_idx, [spans[i][0] for i in order_idx])


def union_rect(rects: list[Rect]) -> Rect:
    """Bounding rectangle of several rectangles."""
    return (
        min(r[0] for r in rects),
        min(r[1] for r in rects),
        max(r[2] for r in rects),
        max(r[3] for r in rects),
    )


def rect_area(r: Rect) -> float:
    """Area of a rectangle (0 if degenerate)."""
    return max(r[2] - r[0], 0.0) * max(r[3] - r[1], 0.0)


def intersect_area(a: Rect, b: Rect) -> float:
    """Area of the intersection of two rectangles."""
    return rect_area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))


def mask_value(text: str, pii_type: str) -> str:
    """Partially mask a value for display, e.g. ``ABCPX****K``."""
    t = " ".join(text.split())
    if pii_type in VISUAL_TYPES:
        return f"<{pii_type.lower()} region>"
    if pii_type == "MANUAL":
        return "<drawn box>"
    if pii_type == "EMAIL" and "@" in t:
        return t[:2] + "***@***"
    if len(t) <= 4:
        return "*" * len(t)
    if pii_type in NAME_TYPES or pii_type == "TERM":
        return t[:2] + "****" + (t[-1] if len(t) > 6 else "")
    keep_head = max(1, min(5, len(t) // 2 - 1))
    return t[:keep_head] + "****" + t[-1]
