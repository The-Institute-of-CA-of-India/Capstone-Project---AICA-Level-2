"""Turn input files (PDF, HTML, Excel, images, ZIP archives) into text documents.

ZIP files are opened recursively in memory. Password-protected PDFs are tried
with: no password, the passwords supplied by the user, and tokens taken from the
file name (IIFL protects notes with the client code, which is also the first
word of its file names).
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .utils import bytes_sha256

SUPPORTED = {".pdf", ".htm", ".html", ".xlsx", ".xls", ".csv", ".jpg", ".jpeg", ".png", ".zip"}


@dataclass
class Document:
    name: str            # file name (inside archive if any)
    origin: str          # path shown to user, e.g. archive.zip > inner.pdf
    ext: str
    data: bytes
    sha256: str
    text: str = ""
    kind: str = ""       # pdf / html / excel / image
    error: str = ""
    password_used: str = ""


def iter_documents(paths, log):
    """Yield Document objects for every supported file under the given paths."""
    for p in paths:
        p = Path(p)
        files = sorted(p.rglob("*")) if p.is_dir() else [p]
        for f in files:
            if f.is_file() and f.suffix.lower() in SUPPORTED:
                yield from _from_bytes(f.name, str(f), f.read_bytes(), log)


def _from_bytes(name, origin, data, log):
    ext = Path(name).suffix.lower()
    if ext == ".zip":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    inner = Path(info.filename).name
                    if Path(inner).suffix.lower() in SUPPORTED:
                        yield from _from_bytes(inner, f"{origin} > {info.filename}", zf.read(info), log)
        except zipfile.BadZipFile as exc:
            log(origin, "Error", f"Bad zip file: {exc}")
        return
    yield Document(name=name, origin=origin, ext=ext, data=data, sha256=bytes_sha256(data))


# --------------------------------------------------------------------------- text extraction

def _filename_tokens(name: str):
    stem = Path(name).stem
    return [t for t in re.split(r"[\s_\-]+", stem) if len(t) >= 4 and not t.isdigit()]


def extract_text(doc: Document, passwords):
    try:
        if doc.ext == ".pdf":
            _pdf_text(doc, passwords)
        elif doc.ext in (".htm", ".html"):
            _html_text(doc)
        elif doc.ext in (".xlsx", ".xls", ".csv"):
            doc.kind = "excel"   # read by the Excel importers directly
        elif doc.ext in (".jpg", ".jpeg", ".png"):
            _image_text(doc)
    except Exception as exc:  # noqa: BLE001 - report every failure to the import log
        doc.error = f"{type(exc).__name__}: {exc}"
    return doc


def _pdf_text(doc: Document, passwords):
    import pdfplumber
    from pdfminer.pdfdocument import PDFPasswordIncorrect

    doc.kind = "pdf"
    if not doc.data.lstrip()[:5].startswith(b"%PDF"):
        raise ValueError("this is not a real PDF file (it may be damaged or only partly downloaded)")
    encrypted = b"/Encrypt" in doc.data
    candidates = [""] + (list(passwords) + _filename_tokens(doc.name) if encrypted else [])
    last_error = None
    tried = set()
    for pw in candidates:
        for variant in {pw, pw.upper(), pw.lower()}:
            if variant in tried:
                continue
            tried.add(variant)
            try:
                with pdfplumber.open(io.BytesIO(doc.data), password=variant) as pdf:
                    pages = [(pg.extract_text() or "") for pg in pdf.pages]
                doc.text = "\n".join(f"<<PAGE {i + 1}>>\n{t}" for i, t in enumerate(pages))
                doc.password_used = variant
                if not doc.text.replace("<<PAGE", "").strip(">0123456789\n "):
                    _ocr_pdf(doc, variant)
                return
            except PDFPasswordIncorrect:
                continue
            except Exception as exc:  # pdfminer wraps password errors differently by version
                if encrypted and ("password" in str(exc).lower() or type(exc).__name__ == "PdfminerException"):
                    continue
                last_error = exc
                break
    if encrypted:
        raise PermissionError("the PDF is password protected and none of the known passwords opened it")
    raise ValueError(f"the PDF is damaged and could not be opened ({type(last_error).__name__ if last_error else 'unknown'})")


def _tesseract():
    """Point pytesseract at the bundled Tesseract (CNM_TESSERACT) when present."""
    import os
    import pytesseract
    cmd = os.environ.get("CNM_TESSERACT")
    if cmd and os.path.exists(cmd):
        pytesseract.pytesseract.tesseract_cmd = cmd
    return pytesseract


def _ocr_pdf(doc: Document, password):
    """Scanned PDF: render pages and OCR them."""
    import pypdfium2 as pdfium
    pytesseract = _tesseract()

    pdf = pdfium.PdfDocument(doc.data, password=password or None)
    texts = []
    for i in range(len(pdf)):
        img = pdf[i].render(scale=2.5).to_pil()
        texts.append(f"<<PAGE {i + 1}>>\n" + pytesseract.image_to_string(img))
    doc.text = "\n".join(texts)
    doc.kind = "pdf-ocr"


def _html_text(doc: Document):
    from bs4 import BeautifulSoup

    doc.kind = "html"
    html = doc.data.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    lines = [ln.strip() for ln in soup.get_text("\n").splitlines()]
    doc.text = "\n".join(ln for ln in lines if ln)


def _image_text(doc: Document):
    from PIL import Image

    pytesseract = _tesseract()
    doc.kind = "image"
    doc.text = pytesseract.image_to_string(Image.open(io.BytesIO(doc.data)))
