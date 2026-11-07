"""Open a notice PDF, classify pages as TEXT or IMAGE, and OCR image pages.

OCR boxes are mapped back to unrotated PDF coordinates so the same rectangles
work for detection, preview and redaction.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable

import fitz  # PyMuPDF
import numpy as np

from .models import PageInfo, Rect, UserFacingError, Word

log = logging.getLogger("mukhota.ingest")
Progress = Callable[[int, str], None]

_ocr_engine = None
_ocr_lock = threading.Lock()


def _noop(_pct: int, _msg: str = "") -> None:
    pass


def get_ocr():
    """Return the shared RapidOCR engine (created on first use)."""
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except Exception as exc:  # pragma: no cover - install problem
            log.exception("RapidOCR import failed")
            raise UserFacingError(
                "The OCR engine is not installed correctly. Please run install.bat again."
            ) from exc
        _ocr_engine = RapidOCR()
    return _ocr_engine


def open_pdf_bytes(data: bytes) -> fitz.Document:
    """Open PDF bytes in memory (the file on disk is never touched)."""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise UserFacingError("This file does not look like a valid PDF.") from exc
    if doc.needs_pass:
        raise UserFacingError(
            "This PDF is password-protected. Please remove the password and open it again."
        )
    if doc.page_count == 0:
        raise UserFacingError("This PDF has no pages.")
    return doc


def read_pdf_bytes(path: str | Path) -> bytes:
    """Read a PDF file into memory with a friendly error on failure."""
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise UserFacingError(
            "Mukhota could not read this file. Check that it exists and is not open in another program."
        ) from exc


def load_document(path: str | Path) -> fitz.Document:
    """Open a PDF from disk as an in-memory copy."""
    return open_pdf_bytes(read_pdf_bytes(path))


def classify_page(page: fitz.Page, cfg: dict[str, Any]) -> str:
    """Return ``"TEXT"`` for pages with a usable text layer, else ``"IMAGE"``.

    A page mostly covered by images is treated as IMAGE even if it carries a
    (scanner-made) hidden text layer, so that layer is never trusted or kept.
    """
    text = page.get_text("text").strip()
    if len(text) < cfg["ingest"]["min_text_chars"]:
        return "IMAGE"
    area = page.rect.width * page.rect.height
    covered = 0.0
    for info in page.get_image_info():
        r = fitz.Rect(info["bbox"])
        covered += max(r.width, 0) * max(r.height, 0)
    if area and min(covered / area, 1.0) >= cfg["ingest"]["image_coverage_ratio"]:
        return "IMAGE"
    return "TEXT"


def render_page_array(page: fitz.Page, dpi: int) -> np.ndarray:
    """Render a page (as displayed, i.e. rotated) to an RGB numpy array."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)
    arr = arr[:, : pix.width * pix.n].reshape(pix.height, pix.width, pix.n)
    if pix.n == 1:
        arr = np.repeat(arr, 3, axis=2)
    return np.ascontiguousarray(arr[:, :, :3])


def pixel_to_pdf(page: fitz.Page, x0: float, y0: float, x1: float, y1: float, dpi: int) -> Rect:
    """Convert a pixel box on the rendered page to an unrotated PDF rectangle."""
    s = 72.0 / dpi
    r = fitz.Rect(x0 * s, y0 * s, x1 * s, y1 * s) * page.derotation_matrix
    r.normalize()
    return (r.x0, r.y0, r.x1, r.y1)


def pdf_to_pixel(page: fitz.Page, rect: Rect, dpi: int) -> tuple[float, float, float, float]:
    """Convert an unrotated PDF rectangle to a pixel box on the rendered page."""
    r = fitz.Rect(rect) * page.rotation_matrix
    r.normalize()
    s = dpi / 72.0
    return (r.x0 * s, r.y0 * s, r.x1 * s, r.y1 * s)


def text_words(page: fitz.Page) -> list[Word]:
    """Words from the PDF text layer (confidence 1.0)."""
    out: list[Word] = []
    for w in page.get_text("words", sort=True):
        x0, y0, x1, y1, txt, block, line = w[0], w[1], w[2], w[3], w[4], w[5], w[6]
        if txt.strip():
            out.append(Word(txt, (x0, y0, x1, y1), 1.0, (block, line)))
    return out


def ocr_page(page: fitz.Page, dpi: int) -> list[Word]:
    """OCR a page with RapidOCR; each text line is split into word boxes.

    RapidOCR reports boxes per text line, so word boxes are apportioned by
    character position along the line. Redaction adds padding to absorb the
    small error this introduces.
    """
    img = render_page_array(page, dpi)[:, :, ::-1]  # RGB -> BGR
    engine = get_ocr()
    with _ocr_lock:
        result, _ = engine(np.ascontiguousarray(img))
    words: list[Word] = []
    for li, item in enumerate(result or []):
        box, text = item[0], str(item[1])
        try:
            score = float(item[2])
        except (TypeError, ValueError):
            score = 0.0
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        total = len(text)
        if not text.strip() or total == 0:
            continue
        pos = 0
        for tok in text.split():
            i = text.index(tok, pos)
            j = i + len(tok)
            pos = j
            wx0 = x0 + (x1 - x0) * i / total
            wx1 = x0 + (x1 - x0) * j / total
            words.append(Word(tok, pixel_to_pdf(page, wx0, y0, wx1, y1, dpi), score, ("ocr", li)))
    return words


def _avg_conf(words: list[Word]) -> float | None:
    total = sum(len(w.text) for w in words)
    if not total:
        return None
    return sum(w.conf * len(w.text) for w in words) / total


def analyse(doc: fitz.Document, cfg: dict[str, Any], progress: Progress = _noop) -> list[PageInfo]:
    """Classify every page and collect its words (text layer or OCR)."""
    pages: list[PageInfo] = []
    n = doc.page_count
    dpi = int(cfg["ocr"]["dpi"])
    threshold = float(cfg["ocr"]["low_confidence_threshold"])
    for i, page in enumerate(doc):
        progress(int(i * 100 / n), f"Reading page {i + 1} of {n}")
        kind = classify_page(page, cfg)
        if kind == "TEXT":
            info = PageInfo(i, kind, page.rect.width, page.rect.height, text_words(page))
        else:
            progress(int(i * 100 / n), f"Running OCR on page {i + 1} of {n}")
            words = ocr_page(page, dpi)
            avg = _avg_conf(words)
            needs = avg is None or avg < threshold
            info = PageInfo(i, kind, page.rect.width, page.rect.height, words, avg, needs)
        pages.append(info)
    progress(100, "Pages read")
    log.info(
        "Analysed %d pages: %d text, %d image, %d flagged for manual review",
        n,
        sum(p.kind == "TEXT" for p in pages),
        sum(p.kind == "IMAGE" for p in pages),
        sum(p.needs_review for p in pages),
    )
    return pages
