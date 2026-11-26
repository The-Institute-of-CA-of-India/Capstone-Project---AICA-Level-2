"""OCR and file text extraction (provider-independent).

* Digital PDFs: text layer via PyMuPDF (no OCR needed).
* Scanned PDFs / images: Tesseract via pytesseract when the binary is installed;
  otherwise pages are reported as ``needs_ocr`` so the pipeline can use the AI vision
  provider (if configured) or route the document to manual review. Nothing is guessed.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

import pandas as pd

from config import settings

MIN_TEXT_CHARS = 25


@dataclass
class PageText:
    page_no: int  # 1-based
    text: str
    source: str  # 'pdf_text' | 'tesseract' | 'none'
    needs_ocr: bool = False


@dataclass
class TextResult:
    pages: list[PageText] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)

    @property
    def unreadable_pages(self) -> list[int]:
        return [p.page_no for p in self.pages if p.needs_ocr]


class OCRProvider:
    name = "none"

    def available(self) -> bool:
        return False

    def image_to_text(self, image_bytes: bytes) -> str:  # pragma: no cover
        raise NotImplementedError


class TesseractOCR(OCRProvider):
    name = "tesseract"

    def available(self) -> bool:
        return settings.tesseract_available

    def image_to_text(self, image_bytes: bytes) -> str:
        import pytesseract
        from PIL import Image

        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("L", "RGB"):
            img = img.convert("RGB")
        return pytesseract.image_to_string(img, lang="eng", config="--psm 6")


_ocr: OCRProvider | None = None


def get_ocr() -> OCRProvider:
    global _ocr
    if _ocr is None:
        _ocr = TesseractOCR() if settings.ocr_provider in ("auto", "tesseract") else OCRProvider()
    return _ocr


def set_ocr(provider: OCRProvider) -> None:
    global _ocr
    _ocr = provider


def pdf_page_count(data: bytes) -> int:
    import pymupdf as fitz

    with fitz.open(stream=data, filetype="pdf") as doc:
        return doc.page_count


def extract_pdf(data: bytes, page_from: int | None = None, page_to: int | None = None) -> TextResult:
    import pymupdf as fitz

    res = TextResult()
    ocr = get_ocr()
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        res.errors.append(f"Could not open PDF: {exc}")
        return res
    with doc:
        if doc.needs_pass:
            res.errors.append("PDF is password protected")
            return res
        start = (page_from or 1) - 1
        end = min(page_to or doc.page_count, doc.page_count)
        for i in range(start, end):
            page = doc.load_page(i)
            text = page.get_text("text") or ""
            if len(text.strip()) >= MIN_TEXT_CHARS:
                res.pages.append(PageText(i + 1, text, "pdf_text"))
                continue
            if ocr.available():
                try:
                    pix = page.get_pixmap(dpi=300)
                    t = ocr.image_to_text(pix.tobytes("png"))
                    res.pages.append(PageText(i + 1, t, ocr.name, needs_ocr=len(t.strip()) < MIN_TEXT_CHARS))
                    continue
                except Exception as exc:
                    res.errors.append(f"OCR failed on page {i + 1}: {exc}")
            res.pages.append(PageText(i + 1, text, "none", needs_ocr=True))
    return res


def extract_image(data: bytes) -> TextResult:
    res = TextResult()
    ocr = get_ocr()
    if not ocr.available():
        res.pages.append(PageText(1, "", "none", needs_ocr=True))
        res.errors.append("No OCR engine available for images")
        return res
    try:
        t = ocr.image_to_text(data)
        res.pages.append(PageText(1, t, ocr.name, needs_ocr=len(t.strip()) < MIN_TEXT_CHARS))
    except Exception as exc:
        res.pages.append(PageText(1, "", "none", needs_ocr=True))
        res.errors.append(f"OCR failed: {exc}")
    return res


def pdf_subset(data: bytes, page_from: int, page_to: int) -> bytes:
    import pymupdf as fitz

    with fitz.open(stream=data, filetype="pdf") as src, fitz.open() as out:
        out.insert_pdf(src, from_page=page_from - 1, to_page=page_to - 1)
        return out.tobytes()


def render_pdf_page(data: bytes, page_no: int = 1, dpi: int = 110) -> bytes | None:
    import pymupdf as fitz

    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            if page_no < 1 or page_no > doc.page_count:
                return None
            return doc.load_page(page_no - 1).get_pixmap(dpi=dpi).tobytes("png")
    except Exception:
        return None


def read_table(data: bytes, ext: str) -> pd.DataFrame:
    """Read CSV/XLSX, locating the header row (bank exports often have preamble lines)."""
    if ext == ".csv":
        import csv

        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        rows = list(csv.reader(io.StringIO(text)))
        width = max((len(r) for r in rows), default=0)
        raw = pd.DataFrame([r + [""] * (width - len(r)) for r in rows], dtype=str)  # preamble lines have fewer cells
    else:
        raw = pd.read_excel(io.BytesIO(data), header=None, dtype=str, keep_default_na=False)
    header_idx = 0
    keywords = ("date", "narration", "description", "particulars", "debit", "credit", "invoice", "gstin", "amount",
                "balance", "taxable", "withdrawal", "deposit")
    best = -1
    for i in range(min(len(raw), 30)):
        row = " ".join(str(x).lower() for x in raw.iloc[i].tolist())
        score = sum(1 for k in keywords if k in row)
        if score > best:
            best, header_idx = score, i
    df = raw.iloc[header_idx + 1:].copy()
    df.columns = [str(c).strip() or f"col{j}" for j, c in enumerate(raw.iloc[header_idx].tolist())]
    df = df[[c for c in df.columns if c]]
    df = df[(df.astype(str).apply(lambda r: "".join(r).strip(), axis=1)) != ""]
    return df.reset_index(drop=True)
