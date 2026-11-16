"""
PDF engine: reading (pass 1) and true redaction (pass 2).

Pass 1 reads every page once (text layer and, where needed, OCR), detects
identifiers and visual items, and keeps the page text in a FileScan so that
pass 2 can redact without reading or OCR-ing again.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import re
import shutil
from pathlib import Path

import pymupdf

from . import detect as D
from .model import FileResult, FileScan, Finding, Options, Overrides, PageData, SourceText

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

# --------------------------------------------------------------------------
# OCR (Tesseract)
# --------------------------------------------------------------------------
_TESSDATA_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tessdata",
    r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tessdata"),
    os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tessdata"),
    "/opt/homebrew/share/tessdata",
    "/usr/local/share/tessdata",
    "/usr/share/tesseract-ocr/5/tessdata",
    "/usr/share/tesseract-ocr/4.00/tessdata",
    "/usr/share/tessdata",
]


def find_tessdata() -> str | None:
    env = os.environ.get("TESSDATA_PREFIX")
    if env and Path(env, "eng.traineddata").exists():
        return env
    from .paths import bundled_tessdata        # shipped with the installed program
    bt = bundled_tessdata()
    if bt is not None:
        return str(bt)
    for c in _TESSDATA_CANDIDATES:
        if c and Path(c, "eng.traineddata").exists():
            return c
    exe = shutil.which("tesseract")
    if exe:
        guess = Path(exe).resolve().parent.parent / "share" / "tessdata"
        if (guess / "eng.traineddata").exists():
            return str(guess)
        guess = Path(exe).resolve().parent / "tessdata"          # Windows layout
        if (guess / "eng.traineddata").exists():
            return str(guess)
    try:
        t = pymupdf.get_tessdata()
        if t and Path(t, "eng.traineddata").exists():
            return t
    except Exception:
        pass
    return None


def ocr_languages() -> list[str]:
    """Installed Tesseract languages relevant here (eng, hin, mar)."""
    t = find_tessdata()
    if not t:
        return []
    return [l for l in ("eng", "hin", "mar") if Path(t, f"{l}.traineddata").exists()]


def _ocr_textpage(page, opts: Options, tessdata: str, dpi: int | None = None):
    langs = [l for l in opts.ocr_langs if Path(tessdata, f"{l}.traineddata").exists()] or ["eng"]
    return page.get_textpage_ocr(flags=pymupdf.TEXT_PRESERVE_WHITESPACE, language="+".join(langs),
                                 dpi=dpi or opts.ocr_dpi, full=True, tessdata=tessdata)


_OCR_TOKEN = re.compile(r"\S+")
_OCR_DIGIT_FIX = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1"})


def ocr_normalise(text: str) -> str:
    """Fix common OCR confusions inside mostly-numeric tokens (same length)."""
    def fix(m):
        tok = m.group(0)
        alnum = [c for c in tok if c.isalnum()]
        letters = [c for c in alnum if c.isalpha()]
        # only when every letter is a look-alike of a digit ("32O1456" -> "3201456");
        # "SBIN0004567" keeps its letters
        if alnum and letters and all(c in "OoIl" for c in letters) and \
                sum(c.isdigit() for c in alnum) / len(alnum) >= 0.6:
            return tok.translate(_OCR_DIGIT_FIX)
        return tok
    return _OCR_TOKEN.sub(fix, text)


# --------------------------------------------------------------------------
# Text with character positions, rebuilt into visual rows
# --------------------------------------------------------------------------
def _fragments(textpage) -> list[tuple[str, list]]:
    data = textpage.extractRAWDICT()
    frags = []
    for block in data.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            chars, boxes, prev = [], [], None
            for span in line.get("spans", []):
                size = span.get("size", 10) or 10
                for ch in span.get("chars", []):
                    c = ch.get("c", "")
                    r = tuple(ch["bbox"])
                    if prev is not None and c != " " and chars and chars[-1] != " ":
                        if r[0] - prev[2] > size * 0.30:
                            chars.append(" ")
                            boxes.append(None)
                    chars.append(c)
                    boxes.append(r if r[2] > r[0] and r[3] > r[1] else None)
                    prev = r
            if chars:
                frags.append(("".join(chars), boxes))
    return frags


def _rows(frags) -> list[tuple[str, list]]:
    items = []
    for text, boxes in frags:
        real = [b for b in boxes if b is not None]
        if not real:
            continue
        bb = (min(b[0] for b in real), min(b[1] for b in real), max(b[2] for b in real), max(b[3] for b in real))
        items.append((bb, text, boxes))
    items.sort(key=lambda f: (f[0][1], f[0][0]))
    rows: list[dict] = []
    for bb, text, boxes in items:
        h = max(bb[3] - bb[1], 1.0)
        target = None
        for row in rows[-8:]:
            ov = min(row["y1"], bb[3]) - max(row["y0"], bb[1])
            if ov > 0.5 * min(h, row["y1"] - row["y0"]):
                target = row
                break
        if target is None:
            target = {"y0": bb[1], "y1": bb[3], "items": []}
            rows.append(target)
        target["items"].append((bb, text, boxes))
        target["y0"], target["y1"] = min(target["y0"], bb[1]), max(target["y1"], bb[3])
    rows.sort(key=lambda r: r["y0"])
    out = []
    for row in rows:
        parts, bparts, prev = [], [], None
        for bb, text, boxes in sorted(row["items"], key=lambda f: f[0][0]):
            if prev is not None:
                gap = bb[0] - prev[2]
                sep = " " if gap < 1.5 * max(bb[3] - bb[1], prev[3] - prev[1]) else "   "
                parts.append(sep)
                bparts.extend([None] * len(sep))
            parts.append(text)
            bparts.extend(boxes)
            prev = bb
        out.append(("".join(parts), bparts))
    return out


def source_from_textpage(textpage, kind: str) -> SourceText:
    rows = _rows(_fragments(textpage))
    text_parts, boxes, row_ids = [], [], []
    for i, (t, b) in enumerate(rows):
        if i:
            text_parts.append("\n")
            boxes.append(None)
            row_ids.append(-1)
        text_parts.append(t)
        boxes.extend(b)
        row_ids.extend([i] * len(t))
    text = "".join(text_parts)
    if kind == "ocr":
        text = ocr_normalise(text)
    return SourceText(kind=kind, text=text, boxes=boxes, rows=row_ids)


def _has_text(page) -> bool:
    return len(re.sub(r"\s", "", page.get_text("text"))) >= 25


def _image_areas(page) -> list:
    try:
        return [pymupdf.Rect(i["bbox"]) for i in page.get_image_info() if pymupdf.Rect(i["bbox"]).get_area() > 400]
    except Exception:
        return []


# --------------------------------------------------------------------------
# Visual detectors (QR codes / barcodes, photographs, signatures)
# --------------------------------------------------------------------------
def _page_image(page, dpi: int):
    import numpy as np
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    return img, dpi / 72.0


def _px_to_page(page, x0, y0, x1, y1, zoom) -> pymupdf.Rect:
    r = pymupdf.Rect(x0 / zoom, y0 / zoom, x1 / zoom, y1 / zoom) * page.derotation_matrix
    r.normalize()
    return r


def detect_codes(page) -> list:
    try:
        import cv2
        import numpy as np
    except Exception:
        return []
    out = []
    for dpi in (110, 200):
        img, zoom = _page_image(page, dpi)
        polys = []
        for det in (getattr(cv2, "QRCodeDetectorAruco", None), cv2.QRCodeDetector):
            if det is None:
                continue
            try:
                ok, pts = det().detectMulti(img)
                if ok and pts is not None:
                    polys += list(pts)
            except Exception:
                pass
        try:
            ok, pts = cv2.barcode.BarcodeDetector().detect(img)[:2]
            if ok and pts is not None:
                polys += list(pts)
        except Exception:
            pass
        for p in polys:
            p = np.asarray(p).reshape(-1, 2)
            x0, y0 = p.min(axis=0)
            x1, y1 = p.max(axis=0)
            w, h = x1 - x0, y1 - y0
            if w < 15 or h < 8:
                continue
            r = _px_to_page(page, x0 - w * 0.08, y0 - h * 0.08, x1 + w * 0.08, y1 + h * 0.08, zoom)
            if not any(r.intersects(o) for o in out):
                out.append(r)
        if out:
            break
    return out


def detect_photos(page) -> list:
    try:
        import cv2
    except Exception:
        return []
    areas = _image_areas(page)
    if not areas:
        return []
    page_area = abs(page.rect)
    img, zoom = _page_image(page, 150)
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    loose = casc.detectMultiScale(img, scaleFactor=1.08, minNeighbors=5, minSize=(30, 30))
    strict = casc.detectMultiScale(img, scaleFactor=1.08, minNeighbors=9, minSize=(40, 40))
    strict = [tuple(f) for f in strict] if len(strict) else []
    out = []
    for f in (loose if len(loose) else []):
        x, y, w, h = f
        r = _px_to_page(page, x - 0.45 * w, y - 0.55 * h, x + 1.45 * w, y + 1.9 * h, zoom)
        face = _px_to_page(page, x, y, x + w, y + h, zoom)
        host = [a for a in areas if a.contains(face) or a.intersects(face)]
        if not host:
            continue
        # a face on a full-page scan must pass the stricter test (text can look like a face)
        if all(abs(a) > 0.5 * page_area for a in host) and tuple(f) not in strict:
            continue
        small = [a for a in host if abs(a) < 0.3 * page_area]
        if small:
            # a photo embedded as its own image (e-Aadhaar, PAN card copy): cover all of it
            r = pymupdf.Rect(small[0])
        r &= pymupdf.Rect(page.mediabox)
        if not any(r.intersects(o) for o in out):
            out.append(r)
    return out


_SIG_LABEL = re.compile(r"(?i)\b(?:signature|signatory|sign\.)(?:\s+of\s+[A-Za-z ]{2,25})?\s*:?")


def detect_signatures(page, sources: list) -> list:
    out = []
    for src in sources:
        for m in _SIG_LABEL.finditer(src.text):
            if re.search(r"(?i)digitally\s+signed|not\s+verified", src.text[max(0, m.start() - 40):m.end() + 20]):
                continue
            bs = [b for b in src.boxes[m.start():m.end()] if b]
            if not bs:
                continue
            x0, y0 = min(b[0] for b in bs), min(b[1] for b in bs)
            x1, y1 = max(b[2] for b in bs), max(b[3] for b in bs)
            w, h = max(x1 - x0, 60), y1 - y0
            above = pymupdf.Rect(x0 - w * 0.5, y0 - 4 * h, x1 + w * 0.5, y0 - 1)
            out.append(above)
            if src.text[m.end() - 1:m.end()] == ":":
                out.append(pymupdf.Rect(x1 + 2, y0 - h, x1 + 190, y1 + h))
    return out


# --------------------------------------------------------------------------
# Opening and unlocking
# --------------------------------------------------------------------------
def open_any(name: str, data: bytes):
    ext = Path(name).suffix.lower()
    if ext in IMAGE_EXT:
        img = pymupdf.open(stream=data, filetype=ext.lstrip("."))
        pdf_bytes = img.convert_to_pdf()
        img.close()
        return pymupdf.open(stream=pdf_bytes, filetype="pdf"), pdf_bytes
    return pymupdf.open(stream=data, filetype="pdf"), data


def unlock(doc, src: bytes, candidates: list) -> str | None:
    """
    Returns the working password ("" when not locked), or None.
    A failed authenticate() can undo an earlier success, and reading
    doc.needs_pass afterwards re-locks the document, so candidates are
    probed on throw-away copies and only the winner is applied.
    """
    if not doc.needs_pass:
        return ""
    for pw in candidates:
        probe = pymupdf.open(stream=src, filetype="pdf")
        ok = probe.authenticate(pw)
        probe.close()
        if ok and doc.authenticate(pw):
            return pw
    return None


# --------------------------------------------------------------------------
# Pass 1 - read and detect
# --------------------------------------------------------------------------
def scan_pdf(name: str, data: bytes, opts: Options, candidates: list) -> FileScan:
    scan = FileScan(name=name, kind="pdf")
    try:
        doc, src = open_any(name, data)
    except Exception as exc:
        scan.status, scan.message = "error", f"Could not open file: {exc}"
        return scan
    was_locked = bool(doc.needs_pass) or bool(doc.metadata.get("encryption"))
    pw = unlock(doc, src, candidates)
    if pw is None:
        scan.status, scan.message = "locked", "Password-protected; none of the passwords worked."
        doc.close()
        return scan
    if was_locked:
        src = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_NONE)
        doc.close()
        doc = pymupdf.open(stream=src, filetype="pdf")
        if pw:
            scan.message = "Unlocked with a supplied password."
    scan.pdf_bytes = src
    scan.page_count = doc.page_count

    tessdata = find_tessdata() if opts.ocr_mode != "off" else None
    sample_text = []
    try:
        for page in doc:
            pd = PageData(number=page.number)
            pd.has_images = bool(_image_areas(page))
            pd.sources.append(source_from_textpage(page.get_textpage(flags=pymupdf.TEXT_PRESERVE_WHITESPACE), "text"))
            need = False
            if tessdata and opts.ocr_mode == "auto":
                need = pd.has_images and not _has_text(page)
            elif tessdata and opts.ocr_mode == "all":
                need = pd.has_images
            if need:
                try:
                    pd.sources.append(source_from_textpage(_ocr_textpage(page, opts, tessdata), "ocr"))
                    pd.ocr_done = True
                    scan.ocr_pages += 1
                except Exception as exc:
                    scan.message += f" OCR failed on page {page.number + 1}: {exc}."
            if page.number < 6:
                sample_text += [s.text for s in pd.sources]
            scan.pages.append(pd)

        scan.profile = opts.profile if opts.profile in D.PROFILE_ADJUST else D.classify("\n".join(sample_text))
        rules = D.effective_rules(opts.rules, scan.profile, opts.profile)

        for page, pd in zip(doc, scan.pages):
            seen = set()
            for src_t in pd.sources:
                for m in D.find_matches(src_t.text, rules, opts, src_t.boxes):
                    k = (D.norm_key(m.rule, m.value), m.rule)
                    if src_t.kind == "ocr" and k in seen:
                        continue
                    seen.add(k)
                    scan.findings.append(Finding(pd.number + 1, m.rule, m.value, src_t.kind))
            vis = []
            if "QR" in rules:
                vis += [("QR", r) for r in detect_codes(page)]
            if "PHOTO" in rules and pd.has_images:
                vis += [("PHOTO", r) for r in detect_photos(page)]
            if "SIGNATURE" in rules:
                vis += [("SIGNATURE", r) for r in detect_signatures(page, pd.sources)]
            for i, (kind, r) in enumerate(vis):
                pd.visual.append((kind, tuple(r)))
                scan.findings.append(Finding(pd.number + 1, kind, f"{kind.lower()} p{pd.number + 1}-{i + 1}", "visual"))
    except Exception as exc:
        scan.status, scan.message = "error", f"Failed while reading: {exc}"
    finally:
        doc.close()
    return scan


# --------------------------------------------------------------------------
# Pass 2 - redact
# --------------------------------------------------------------------------
def _match_rects(src: SourceText, s: int, e: int, pad: float, grow: bool):
    """One (removal, cover) pair per visual row covered by [s, e)."""
    by_row: dict = {}
    for i in range(s, min(e, len(src.boxes))):
        b = src.boxes[i]
        if b is None:
            continue
        by_row.setdefault(src.rows[i], []).append(b)
    out = []
    for bs in by_row.values():
        x0, y0 = min(b[0] for b in bs), min(b[1] for b in bs)
        x1, y1 = max(b[2] for b in bs), max(b[3] for b in bs)
        h, w = y1 - y0, x1 - x0
        dx = min(0.6, w * 0.05)
        removal = pymupdf.Rect(x0 + dx, y0 + h * 0.15, x1 - dx, y1 - h * 0.15)
        if grow:   # OCR boxes hug the glyphs: grow so no slivers stay in the image
            cover = pymupdf.Rect(x0 - pad - 1, y0 - h * 0.22, x1 + pad + 1, y1 + h * 0.15)
        else:
            cover = pymupdf.Rect(x0 - pad, y0, x1 + pad, y1)
        out.append((removal, cover))
    return out


def _all_matches(src: SourceText, rules, opts, ctx, ov: Overrides):
    return D.all_matches(src.text, rules, opts, ctx, ov, src.boxes)


def _draw_label(page, rect: pymupdf.Rect, label: str):
    """White label on the black box; real text, so AI tools read it."""
    if not label or rect.width < 4 or rect.height < 3:
        return
    text = f"[{label}]"
    w_unit = pymupdf.get_text_length(text, fontname="helv", fontsize=1)
    fs = min(rect.height * 0.78, (rect.width - 1) / max(w_unit, 0.1))
    fs = max(fs, 2.5)
    rot = page.rotation
    if rot in (90, 270):
        fs = min(rect.width * 0.78, (rect.height - 1) / max(w_unit, 0.1))
        fs = max(fs, 2.5)
    if rot == 0:
        p = pymupdf.Point(rect.x0 + 0.5, rect.y1 - (rect.height - fs) / 2 - fs * 0.2)
    elif rot == 90:
        p = pymupdf.Point(rect.x0 + (rect.width - fs) / 2 + fs * 0.2, rect.y0 + 0.5)
    elif rot == 180:
        p = pymupdf.Point(rect.x1 - 0.5, rect.y0 + (rect.height - fs) / 2 + fs * 0.2)
    else:
        p = pymupdf.Point(rect.x1 - (rect.width - fs) / 2 - fs * 0.2, rect.y1 - 0.5)
    try:
        page.insert_text(p, text, fontsize=fs, fontname="helv", color=(1, 1, 1), rotate=rot)
    except Exception:
        pass


def _invisible_words(page, textpage, covers: list):
    """Add an invisible text layer from OCR words (skipping redacted areas)."""
    rot = page.rotation
    for x0, y0, x1, y1, word, *_ in textpage.extractWORDS():
        r = pymupdf.Rect(x0, y0, x1, y1)
        if any(r.intersects(c) for c in covers) or not word.strip():
            continue
        h = (y1 - y0) if rot in (0, 180) else (x1 - x0)
        span = (x1 - x0) if rot in (0, 180) else (y1 - y0)
        w_unit = pymupdf.get_text_length(word, fontname="helv", fontsize=1) or 1
        fs = max(min(h * 0.95, span / w_unit), 2)
        pt = {0: (x0, y1 - h * 0.2), 90: (x0 + h * 0.2, y0), 180: (x1, y0 + h * 0.2), 270: (x1 - h * 0.2, y1)}[rot]
        try:
            page.insert_text(pt, word, fontsize=fs, fontname="helv", render_mode=3, rotate=rot)
        except Exception:
            pass


def _text_moved(before, after) -> bool:
    """Safety check: text that was not redacted must stay where it was."""
    pos: dict = {}
    for w in after:
        pos.setdefault((w[4], round(w[1])), []).append(w[0])
    moved = 0
    for w in before:
        xs = pos.get((w[4], round(w[1])))
        if xs and min(abs(x - w[0]) for x in xs) > 0.75:
            moved += 1
    return moved > 0


def redact_pdf(scan: FileScan, opts: Options, ctx=None, ov: Overrides | None = None) -> FileResult:
    ov = ov or Overrides()
    res = FileResult(name=scan.name, kind="pdf", profile=scan.profile, pages=scan.page_count,
                     ocr_pages=scan.ocr_pages, message=scan.message.strip())
    rules = D.effective_rules(opts.rules, scan.profile, opts.profile)
    tessdata = find_tessdata()
    doc = pymupdf.open(stream=scan.pdf_bytes, filetype="pdf")
    label_mode = opts.style == "label"
    try:
        for pd in scan.pages:
            page = doc[pd.number]
            # only a scanned page (a picture covering most of the page) needs boxes grown past the text:
            # on digital pages with decorative images, growing would cut into the neighbouring lines
            imgs = _image_areas(page) if pd.has_images else []
            parea = page.rect.get_area() or 1
            grow_all = any((r & page.rect).get_area() >= 0.5 * parea for r in imgs)
            items = []                 # (removal, cover, label, rule, value, source)
            for src in pd.sources:
                for m in _all_matches(src, rules, opts, ctx, ov):
                    label = ctx.token(m.rule, m.value) if (ctx and label_mode) else ""
                    for removal, cover in _match_rects(src, m.start, m.end, opts.padding,
                                                       grow=(src.kind == "ocr" or grow_all)):
                        items.append((removal, cover, label, m.rule, m.value, src.kind))
            for i, (kind, r) in enumerate(pd.visual):
                val = f"{kind.lower()} p{pd.number + 1}-{i + 1}"
                if D.keep_key(val) in {D.keep_key(k) for k in ov.keep_values}:
                    continue
                label = ctx.token(kind, val) if (ctx and label_mode) else ""
                items.append((pymupdf.Rect(r), pymupdf.Rect(r), label, kind, val, "visual"))
            for j, (p0, r) in enumerate(ov.boxes):
                if p0 == pd.number:
                    items.append((pymupdf.Rect(r), pymupdf.Rect(r), "REDACTED" if label_mode else "",
                                  "MANUAL", f"box p{p0 + 1}-{j + 1}", "manual"))

            # report: one finding per (rule, value, row)
            pw, ph = page.rect.width, page.rect.height
            rot = page.rotation_matrix
            # values the reviewer chose to leave visible: keep their position for the viewer
            keep_file = {D.keep_key(k) for k in ov.keep_values}
            keep_batch = {D.keep_key(k) for k in opts.keep_terms if k.strip()}
            if keep_file or keep_batch:
                plain = dataclasses.replace(opts, keep_terms=[])
                for src in pd.sources:
                    for m in _all_matches(src, rules, plain, ctx, Overrides(terms=ov.terms)):
                        kk = D.keep_key(m.value)
                        if kk not in keep_file and kk not in keep_batch:
                            continue
                        bxs = []
                        for _, cover in _match_rects(src, m.start, m.end, opts.padding, False):
                            vr = pymupdf.Rect(cover) * rot
                            vr.normalize()
                            bxs.append((vr.x0 / pw, vr.y0 / ph, vr.x1 / pw, vr.y1 / ph))
                        res.kept.append(Finding(pd.number + 1, m.rule, m.value, src.kind,
                                                where="file" if kk in keep_file else "batch", boxes=bxs))
                for i, (kind, r) in enumerate(pd.visual):
                    val = f"{kind.lower()} p{pd.number + 1}-{i + 1}"
                    if D.keep_key(val) in keep_file:
                        vr = pymupdf.Rect(r) * rot
                        vr.normalize()
                        res.kept.append(Finding(pd.number + 1, kind, val, "visual", where="file",
                                                boxes=[(vr.x0 / pw, vr.y0 / ph, vr.x1 / pw, vr.y1 / ph)]))
            seen: dict = {}
            for removal, cover, label, rule, value, kind in items:
                vr = pymupdf.Rect(cover) * rot          # into the displayed (rotated) page
                vr.normalize()
                nb = (round(vr.x0 / pw, 5), round(vr.y0 / ph, 5), round(vr.x1 / pw, 5), round(vr.y1 / ph, 5))
                key = (rule, D.keep_key(value), round(cover.y0 / 4))
                if key in seen:
                    seen[key].boxes.append(nb)
                    continue
                f = Finding(pd.number + 1, rule, value, kind, label, boxes=[nb])
                seen[key] = f
                res.findings.append(f)

            if items:
                used = []
                pixel_only = []
                for removal, cover, label, rule, value, kind in items:
                    # where images sit under the box, blank the full cover area
                    use = cover if (grow_all or kind in ("visual", "manual")) else removal
                    page.add_redact_annot(use, fill=(0, 0, 0))
                    used.append(pymupdf.Rect(use))
                    if use is removal and any(cover.intersects(r) for r in imgs):
                        pixel_only.append(cover)
                kept_before = [w for w in page.get_text("words")
                               if not any(pymupdf.Rect(w[:4]).intersects(u) for u in used)]
                page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                                      graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                                      text=pymupdf.PDF_REDACT_TEXT_REMOVE)
                if pixel_only:
                    # text was removed with the tight box; also blank any picture pixels under the full box,
                    # without touching the text of neighbouring lines
                    for r in pixel_only:
                        page.add_redact_annot(r, fill=(0, 0, 0))
                    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                                          graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                                          text=pymupdf.PDF_REDACT_TEXT_NONE)
                if _text_moved(kept_before, page.get_text("words")):
                    res.layout_pages.append(pd.number + 1)
                shape = page.new_shape()
                for _, cover, *__ in items:
                    shape.draw_rect(cover)
                shape.finish(color=None, fill=(0, 0, 0), width=0)
                shape.commit()
                if label_mode:
                    drawn = []
                    for _, cover, label, *__ in items:
                        if label and not any(cover == d for d in drawn):
                            _draw_label(page, cover, label)
                            drawn.append(cover)

            # scanned pages: verify by OCR-ing the redacted page, add text layer
            if pd.ocr_done and tessdata and (opts.verify_scans or opts.add_text_layer):
                try:
                    tp = _ocr_textpage(page, opts, tessdata)
                    covers = [c for _, c, *__ in items]
                    if opts.verify_scans:
                        src2 = source_from_textpage(tp, "ocr")
                        grown = [pymupdf.Rect(c) + (-2, -2, 2, 2) for c in covers]
                        for m in _all_matches(src2, rules - D.VISUAL_RULES, opts, ctx, Overrides(keep_values=ov.keep_values)):
                            bs = [pymupdf.Rect(b) for b in src2.boxes[m.start:m.end] if b]
                            inside = sum(1 for b in bs if any(b.intersects(c) for c in grown))
                            if bs and inside >= 0.5 * len(bs):
                                continue          # OCR of the label text inside a box
                            if D.is_noise(m.rule, m.value):
                                continue          # OCR noise read as a name/address
                            res.residual_ocr += 1
                            res.residual_notes.append((pd.number + 1, m.rule, Finding(0, m.rule, m.value, "ocr").masked))
                        res.verified_scans = True
                    if opts.add_text_layer:
                        _invisible_words(page, tp, covers)
                except Exception as exc:
                    res.message += f" Scan check failed on page {pd.number + 1}: {exc}."

        if opts.scrub_metadata:
            doc.scrub(attached_files=True, embedded_files=True, javascript=True, metadata=True,
                      xml_metadata=True, remove_links=True, reset_fields=True, reset_responses=True,
                      thumbnails=True, hidden_text=False, redactions=False, clean_pages=True)
            doc.set_metadata({})
        out = doc.tobytes(garbage=4, deflate=True, clean=True)
    except Exception as exc:
        res.status, res.message = "error", f"Failed during redaction: {exc}"
        doc.close()
        return res
    doc.close()

    if res.layout_pages:
        res.message += (" Text shifted after redaction on page(s) "
                        + ", ".join(map(str, res.layout_pages)) + " - check the layout before sharing.")
    res.output = out
    res.residual, notes = residual_text(out, rules, opts, ctx, ov)
    res.residual_notes += notes
    res.text_export = text_export(out)
    if not res.findings:
        res.status = "no_findings"
    res.sha_out = hashlib.sha256(out).hexdigest()
    return res


def residual_text(pdf_bytes: bytes, rules, opts, ctx, ov):
    """Identifiers still present in the text layer of the redacted file."""
    n, notes = 0, []
    keep_ov = Overrides(keep_values=ov.keep_values if ov else set())
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as d:
        for page in d:
            src = source_from_textpage(page.get_textpage(flags=pymupdf.TEXT_PRESERVE_WHITESPACE), "text")
            for m in _all_matches(src, rules - D.VISUAL_RULES, opts, ctx, keep_ov):
                if D.is_noise(m.rule, m.value):
                    continue
                n += 1
                notes.append((page.number + 1, m.rule, Finding(0, m.rule, m.value, "text").masked))
    return n, notes


def text_export(pdf_bytes: bytes) -> str:
    parts = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as d:
        for page in d:
            src = source_from_textpage(page.get_textpage(flags=pymupdf.TEXT_PRESERVE_WHITESPACE), "text")
            parts.append(f"=== Page {page.number + 1} ===\n{src.text.strip()}\n")
    return "\n".join(parts)


def page_rows(pdf_bytes: bytes):
    """[(page_no, row_text, char_boxes)] for transaction parsing."""
    out = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as d:
        for page in d:
            for t, b in _rows(_fragments(page.get_textpage(flags=pymupdf.TEXT_PRESERVE_WHITESPACE))):
                out.append((page.number + 1, t, b))
    return out


def render_page(pdf_bytes: bytes, page_no: int, dpi: int = 110, candidates=None) -> bytes | None:
    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as d:
            if d.needs_pass and unlock(d, pdf_bytes, candidates or []) is None:
                return None
            if page_no >= d.page_count:
                return None
            return d[page_no].get_pixmap(dpi=dpi).tobytes("png")
    except Exception:
        return None


def page_geometry(pdf_bytes: bytes, page_no: int):
    """(rotated width, rotated height, derotation matrix) for touch-up boxes."""
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as d:
        p = d[page_no]
        return p.rect.width, p.rect.height, tuple(p.derotation_matrix)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def self_test() -> bool:
    """True when the installed PDF library redacts without moving neighbouring text."""
    try:
        d = pymupdf.open()
        p = d.new_page()
        p.insert_text((36, 100), "X32014567891234Y", fontsize=10, fontname="cour")
        before = [w for w in p.get_text("words")]
        chars = [c for b in p.get_text("rawdict")["blocks"] for l in b.get("lines", [])
                 for s in l["spans"] for c in s["chars"]]
        r = pymupdf.Rect(chars[1]["bbox"]) | pymupdf.Rect(chars[14]["bbox"])
        p.add_redact_annot(r + (0.6, 1, -0.6, -1))
        p.apply_redactions()
        y_before = chars[-1]["origin"][0]
        after = [c for b in p.get_text("rawdict")["blocks"] for l in b.get("lines", [])
                 for s in l["spans"] for c in s["chars"]]
        return bool(before) and abs(after[-1]["origin"][0] - y_before) < 0.5 and \
            "3201" not in p.get_text()
    except Exception:
        return False


def view_to_page_rect(pdf_bytes: bytes, page_no: int, box) -> tuple:
    """A box drawn on the displayed page (fractions 0-1) -> unrotated page coordinates."""
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as d:
        p = d[page_no]
        w, h = p.rect.width, p.rect.height
        r = pymupdf.Rect(box[0] * w, box[1] * h, box[2] * w, box[3] * h) * p.derotation_matrix
        r.normalize()
        return tuple(r)


def page_to_view_box(pdf_bytes: bytes, page_no: int, rect) -> tuple:
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as d:
        p = d[page_no]
        r = pymupdf.Rect(rect) * p.rotation_matrix
        r.normalize()
        return (r.x0 / p.rect.width, r.y0 / p.rect.height, r.x1 / p.rect.width, r.y1 / p.rect.height)


def page_sizes(pdf_bytes: bytes) -> list:
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as d:
        return [(p.rect.width, p.rect.height) for p in d]


def text_in_box(pdf_bytes: bytes, page_no: int, box) -> str:
    """Words of the ORIGINAL page that fall inside a box drawn on the displayed page."""
    rect = pymupdf.Rect(view_to_page_rect(pdf_bytes, page_no, box))
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as d:
        words = d[page_no].get_text("words")
    picked = []
    for w in words:
        r = pymupdf.Rect(w[:4])
        inter = r & rect
        if not inter.is_empty and inter.get_area() >= 0.5 * max(r.get_area(), 0.01):
            picked.append((round(w[1] / 3), w[0], w[4]))
    picked.sort()
    return " ".join(w[2] for w in picked).strip()
