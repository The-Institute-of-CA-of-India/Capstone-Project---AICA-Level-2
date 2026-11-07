"""Apply redactions: text is removed (not covered), image pages are flattened, metadata scrubbed."""
from __future__ import annotations

import hashlib
import io
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import fitz
from PIL import Image, ImageDraw, ImageFont

from .. import APP_NAME, VERSION
from .config import resolve_path
from .ingest import open_pdf_bytes, pdf_to_pixel, read_pdf_bytes
from .models import (
    VISUAL_TYPES,
    Candidate,
    PageInfo,
    Rect,
    UserFacingError,
    intersect_area,
    rect_area,
    union_rect,
)
from .tokens import TokenRegistry, save_vault

log = logging.getLogger("mukhota.redact")
Progress = Callable[[int, str], None]


@dataclass
class RedactionResult:
    """Where the outputs were written and what was redacted (counts only)."""

    folder: Path
    pdf_path: Path
    vault_path: Path
    candidates_path: Path
    counts: dict[str, int] = field(default_factory=dict)
    redacted_pages: list[int] = field(default_factory=list)


def sha256_bytes(data: bytes) -> str:
    """Hex SHA-256 of bytes."""
    return hashlib.sha256(data).hexdigest()


def output_paths(src: Path, cfg: dict[str, Any]) -> tuple[Path, Path, Path, Path]:
    """Return (folder, redacted pdf, vault, candidates.json) for a source PDF."""
    root = src.parent
    if cfg["paths"].get("output_root"):
        root = resolve_path(cfg, "output_root")
    folder = root / f"{src.stem}_mukhota"
    return (
        folder,
        folder / f"{src.stem}_REDACTED.pdf",
        folder / f"{src.stem}.vault",
        folder / "candidates.json",
    )


# --------------------------------------------------------------------------- manual helpers

def text_under_rect(doc: fitz.Document, info: PageInfo, rect: Rect) -> str:
    """Text inside a drawn box (text layer, or OCR words for image pages)."""
    if info.kind == "TEXT":
        return " ".join(doc[info.index].get_textbox(fitz.Rect(rect)).split())
    words = [w.text for w in info.words if intersect_area(w.rect, rect) > 0.5 * rect_area(w.rect)]
    return " ".join(words)


def find_term_occurrences(doc: fitz.Document, pages: list[PageInfo], term: str) -> list[Candidate]:
    """Every occurrence of a typed term (case-insensitive) on every page."""
    from .models import build_page_text
    import re

    term = " ".join(term.split())
    out: list[Candidate] = []
    if not term:
        return out
    pat = re.compile(r"\s*".join(re.escape(p) for p in term.split()), re.IGNORECASE)
    for info in pages:
        if info.kind == "TEXT":
            for q in doc[info.index].search_for(term, quads=False):
                out.append(Candidate(info.index, [(q.x0, q.y0, q.x1, q.y1)], term, "TERM", 1.0, "TYPED_TERM", source="manual"))
        else:
            pt = build_page_text(info.words)
            for m in pat.finditer(pt.text):
                rects = pt.rects(info.words, m.start(), m.end())
                if rects:
                    out.append(Candidate(info.index, rects, term, "TERM", 1.0, "TYPED_TERM", source="manual"))
    return out


# --------------------------------------------------------------------------- drawing helpers

def _absorb_contained(cands: list[Candidate]) -> list[Candidate]:
    """Skip candidates fully inside a larger accepted box on the same page (already covered)."""
    keep: list[Candidate] = []
    ordered = sorted(cands, key=lambda c: -sum(rect_area(b) for b in c.bboxes))
    for c in ordered:
        inside = False
        for k in keep:
            if k.page != c.page:
                continue
            if all(any(intersect_area(b, kb) >= 0.95 * rect_area(b) for kb in k.bboxes) for b in c.bboxes):
                inside = True
                break
        if not inside:
            keep.append(c)
    return keep


def _fit_fontsize(label: str, r: fitz.Rect) -> float:
    return max(min(r.height * 0.65, r.width / (max(len(label), 1) * 0.58), 11.0), 0.0)


def _add_annots(page: fitz.Page, c: Candidate, pad: float) -> None:
    rects = [fitz.Rect(b) + (-pad, -pad, pad, pad) for b in c.bboxes]
    label_i = max(range(len(rects)), key=lambda i: rects[i].get_area())
    for i, r in enumerate(rects):
        fs = _fit_fontsize(c.token, r) if i == label_i else 0
        if fs >= 3:
            page.add_redact_annot(
                r, text=c.token, fontname="helv", fontsize=fs,
                align=fitz.TEXT_ALIGN_CENTER, fill=(0, 0, 0), text_color=(1, 1, 1),
            )
        else:
            page.add_redact_annot(r, fill=(0, 0, 0))


# MuPDF values: images 2 = blank only the covered pixels; graphics 1 = remove line art fully covered.
_REDACT_IMAGE_PIXELS = 2
_REDACT_LINE_ART_IF_COVERED = 1


def _apply_page_redactions(page: fitz.Page) -> None:
    page.apply_redactions(images=_REDACT_IMAGE_PIXELS, graphics=_REDACT_LINE_ART_IF_COVERED)


def _font(size: int):
    for name in ("segoeuib.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _redact_image_page(page: fitz.Page, items: list[Candidate], dpi: int, quality: int, pad: float) -> bytes:
    """Render the page, paint boxes and token labels, and return JPEG bytes."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    draw = ImageDraw.Draw(img)
    s = dpi / 72.0
    for c in items:
        boxes = [pdf_to_pixel(page, b, dpi) for b in c.bboxes]
        boxes = [(x0 - pad * s, y0 - pad * s, x1 + pad * s, y1 + pad * s) for x0, y0, x1, y1 in boxes]
        label_i = max(range(len(boxes)), key=lambda i: (boxes[i][2] - boxes[i][0]) * (boxes[i][3] - boxes[i][1]))
        for i, (x0, y0, x1, y1) in enumerate(boxes):
            draw.rectangle([x0, y0, x1, y1], fill=(0, 0, 0))
            if i != label_i:
                continue
            w, h = x1 - x0, y1 - y0
            size = int(h * 0.6)
            font = _font(max(size, 6))
            while size > 6 and draw.textlength(c.token, font=font) > w * 0.92:
                size -= 1
                font = _font(size)
            if size >= 6 and draw.textlength(c.token, font=font) <= w:
                draw.text(((x0 + x1) / 2, (y0 + y1) / 2), c.token, fill=(255, 255, 255), font=font, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


# --------------------------------------------------------------------------- scrubbing

def scrub_document(doc: fitz.Document) -> None:
    """Remove metadata, XMP, annotations, links, form fields, embedded files and JavaScript."""
    try:
        doc.scrub(
            attached_files=True, clean_pages=True, embedded_files=True, hidden_text=True,
            javascript=True, metadata=True, redactions=True, remove_links=True,
            reset_fields=True, reset_responses=True, thumbnails=True, xml_metadata=True,
        )
    except Exception:
        log.warning("Built-in scrub step failed; continuing with manual scrubbing")
    for page in doc:
        while page.first_annot:
            page.delete_annot(page.first_annot)
        while page.first_widget:
            page.delete_widget(page.first_widget)
        for link in page.get_links():
            page.delete_link(link)
        doc.xref_set_key(page.xref, "AA", "null")
    for name in list(doc.embfile_names()):
        doc.embfile_del(name)
    doc.set_toc([])
    cat = doc.pdf_catalog()
    for key in ("OpenAction", "AA", "Names", "AcroForm", "Metadata", "PieceInfo"):
        doc.xref_set_key(cat, key, "null")
    for xref in range(1, doc.xref_length()):
        try:
            obj = doc.xref_object(xref, compressed=False)
        except Exception:
            continue
        if "/JS" in obj or "/JavaScript" in obj:
            for key in ("JS", "AA", "OpenAction", "S"):
                doc.xref_set_key(xref, key, "null")
    doc.del_xml_metadata()
    doc.set_metadata({
        "author": "", "title": "", "subject": "", "keywords": "", "creator": "",
        "producer": APP_NAME, "creationDate": "", "modDate": "",
    })


# --------------------------------------------------------------------------- main entry

def apply_redactions(
    src_path: str | Path,
    pages: list[PageInfo],
    candidates: list[Candidate],
    cfg: dict[str, Any],
    progress: Progress | None = None,
) -> RedactionResult:
    """Write the redacted PDF, vault and candidates.json into ``<notice>_mukhota/``.

    The original PDF is only ever read.
    """
    progress = progress or (lambda _p, _m="": None)
    src = Path(src_path)
    data = read_pdf_bytes(src)
    folder, out_pdf, vault_path, cand_path = output_paths(src, cfg)
    if out_pdf.resolve() == src.resolve():
        raise UserFacingError("The output file would overwrite the original notice, so Mukhota stopped.")
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UserFacingError("Mukhota could not create the output folder next to the notice.") from exc

    doc = open_pdf_bytes(data)
    accepted = _absorb_contained([c for c in candidates if c.accepted])
    registry = TokenRegistry()
    # Candidates carrying a role (assessee, director...) claim their tokens first.
    for c in sorted(accepted, key=lambda c: (0 if c.role else 1, c.page, c.bboxes[0][1], c.bboxes[0][0])):
        value = c.text if c.text else f"visual:{c.pii_type}:p{c.page + 1}"
        c.token = registry.assign(value, c.pii_type, c.role, c.page)

    by_page: dict[int, list[Candidate]] = defaultdict(list)
    for c in accepted:
        by_page[c.page].append(c)

    red = cfg["redaction"]
    pad = float(red["padding"])
    out = fitz.open()
    n = len(pages)
    for info in pages:
        progress(int(info.index * 90 / max(n, 1)), f"Redacting page {info.index + 1} of {n}")
        page = doc[info.index]
        items = by_page.get(info.index, [])
        if info.kind == "TEXT":
            for c in items:
                _add_annots(page, c, pad)
            if items:
                _apply_page_redactions(page)
            try:
                out.insert_pdf(doc, from_page=info.index, to_page=info.index, links=False, annots=False)
            except TypeError:
                out.insert_pdf(doc, from_page=info.index, to_page=info.index, links=False)
        else:
            jpg = _redact_image_page(page, items, int(red["image_dpi"]), int(red["jpeg_quality"]), pad)
            new_page = out.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=jpg)

    progress(92, "Removing metadata, annotations and attachments")
    scrub_document(out)
    try:
        out.save(str(out_pdf), garbage=4, deflate=True, clean=True)
    except Exception as exc:
        raise UserFacingError(
            "The redacted PDF could not be saved. If it is open in a PDF viewer, close it and try again."
        ) from exc
    finally:
        out.close()
        doc.close()

    counts: dict[str, int] = {}
    for c in accepted:
        counts[c.pii_type] = counts.get(c.pii_type, 0) + 1
    redacted_pages = sorted(by_page)

    now = datetime.now().isoformat(timespec="seconds")
    save_vault(registry, vault_path, {
        "original_file": src.name,
        "original_sha256": sha256_bytes(data),
        "redacted_file": out_pdf.name,
        "created": now,
        "app_version": VERSION,
    })
    cand_json = {
        "app": APP_NAME,
        "version": VERSION,
        "created": now,
        "pages": [
            {
                "page": p.index + 1,
                "kind": p.kind,
                "redactions": len(by_page.get(p.index, [])),
                "needs_review": p.needs_review,
                "reviewed_no_pii": p.reviewed_no_pii,
            }
            for p in pages
        ],
        "items": [
            {
                "type": c.pii_type,
                "page": c.page + 1,
                "token": c.token,
                "source": c.source,
                "rule_id": c.rule_id,
                "confidence": c.confidence,
                "visual": c.pii_type in VISUAL_TYPES,
            }
            for c in sorted(accepted, key=lambda c: (c.page, c.token))
        ],
        # Boxes the user rejected (no values), so verification can tell them apart from misses.
        "rejected": [
            {"type": c.pii_type, "page": c.page + 1, "bbox": [round(v, 2) for v in union_rect(c.bboxes)]}
            for c in candidates
            if not c.accepted
        ],
    }
    cand_path.write_text(json.dumps(cand_json, indent=2), encoding="utf-8")
    progress(100, "Redaction finished")
    log.info("Redaction finished: %d items on %d pages %s", len(accepted), len(redacted_pages), counts)
    return RedactionResult(folder, out_pdf, vault_path, cand_path, counts, [p + 1 for p in redacted_pages])
