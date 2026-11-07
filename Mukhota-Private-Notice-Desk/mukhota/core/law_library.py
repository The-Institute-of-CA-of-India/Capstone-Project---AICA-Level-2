"""Your own law library (law_library/*.pdf|.txt|.md): indexed locally, searched per notice (BM25)."""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

from .config import APP_ROOT

log = logging.getLogger("mukhota.library")
LIB_DIR = APP_ROOT / "law_library"
INDEX_PATH = LIB_DIR / ".index.json"
EXTS = {".pdf", ".txt", ".md"}
CHUNK_CHARS = 1200

_STOP = set("""a an the and or of to in on for by with as at from is are was were be been being this that these those it its
which who whom whose shall may can will would should under any such other than not no nor if then there their they them
he she his her you your we our us i me my sir madam dated date notice also all said same upon into within without
further hereby herein thereof whereas per vide being made make page said section sub clause act rule""".split())
_SECTION = re.compile(r"(?i)\b(?:u/s\.?|under\s+section|section|sec\.|rule)\s*(\d{1,3}[a-z]{0,3})")


@dataclass
class Excerpt:
    """One passage from a library file."""

    source: str
    page: int
    text: str
    score: float


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP and len(t) > 1]


def _files() -> list[Path]:
    if not LIB_DIR.exists():
        return []
    return sorted(p for p in LIB_DIR.rglob("*")
                  if p.suffix.lower() in EXTS and p.is_file() and p.name.lower() != "readme.txt")


def file_count() -> int:
    return len(_files())


def _signature(files: list[Path]) -> dict[str, list[float]]:
    return {str(p.relative_to(LIB_DIR)): [p.stat().st_mtime, p.stat().st_size] for p in files}


def _pages(path: Path) -> list[str]:
    if path.suffix.lower() == ".pdf":
        with fitz.open(path) as doc:
            return [page.get_text("text") for page in doc]
    return [path.read_text(encoding="utf-8", errors="replace")]


def _chunks(text: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out, cur = [], ""
    for p in paras:
        if len(cur) + len(p) > CHUNK_CHARS and cur:
            out.append(cur)
            cur = ""
        cur = (cur + "\n" + p).strip() if cur else p
        while len(cur) > CHUNK_CHARS * 1.5:
            out.append(cur[:CHUNK_CHARS])
            cur = cur[CHUNK_CHARS:]
    if cur:
        out.append(cur)
    return out


def load_index() -> dict[str, Any]:
    """The index, rebuilt automatically when files are added, changed or removed."""
    files = _files()
    sig = _signature(files)
    if INDEX_PATH.exists():
        try:
            idx = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            if idx.get("signature") == sig:
                return idx
        except (OSError, json.JSONDecodeError):
            pass
    chunks: list[dict[str, Any]] = []
    unreadable = 0
    for path in files:
        try:
            for pno, text in enumerate(_pages(path), start=1):
                for c in _chunks(text):
                    chunks.append({"src": str(path.relative_to(LIB_DIR)), "page": pno, "text": c})
        except Exception:
            unreadable += 1
            log.warning("A law library file could not be read")
    idx = {"signature": sig, "chunks": chunks, "unreadable": unreadable}
    try:
        INDEX_PATH.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    except OSError:
        log.warning("Law library index could not be saved")
    log.info("Law library indexed: %d files, %d passages", len(files), len(chunks))
    return idx


def query_terms(notice_text: str) -> list[str]:
    """Section numbers (weighted up) plus the notice's most frequent content words."""
    sections = [s.lower() for s in _SECTION.findall(notice_text)]
    common = [w for w, _ in Counter(_tokens(notice_text)).most_common(30) if not w.isdigit()]
    return sections * 3 + common


def search(terms: list[str], k: int = 8, max_chars: int = 14000) -> list[Excerpt]:
    """Top passages by BM25."""
    idx = load_index()
    chunks = idx["chunks"]
    if not chunks or not terms:
        return []
    docs = [Counter(_tokens(c["text"])) for c in chunks]
    n = len(docs)
    avg = sum(sum(d.values()) for d in docs) / n
    q = Counter(terms)
    df = {t: sum(1 for d in docs if t in d) for t in q}
    scores = []
    for i, d in enumerate(docs):
        length = sum(d.values()) or 1
        s = 0.0
        for t, qw in q.items():
            f = d.get(t, 0)
            if not f:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += qw * idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * length / avg))
        if s > 0:
            scores.append((s, i))
    out, used = [], 0
    for s, i in sorted(scores, reverse=True)[:k]:
        c = chunks[i]
        if used + len(c["text"]) > max_chars:
            break
        used += len(c["text"])
        out.append(Excerpt(c["src"], c["page"], c["text"], round(s, 2)))
    return out


def as_block(excerpts: list[Excerpt]) -> str:
    """Excerpts formatted for the request, each with its source for citation."""
    if not excerpts:
        return ""
    parts = [f"[L{i}] Source: {e.source}, page {e.page}\n{e.text}" for i, e in enumerate(excerpts, start=1)]
    return "<law_library>\n" + "\n\n".join(parts) + "\n</law_library>"
