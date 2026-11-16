"""Downloads and records: ZIPs, text/transaction extracts, combined PDF, certificate."""

from __future__ import annotations

import csv
import io
import re
import traceback
import zipfile
from pathlib import Path, PurePosixPath

import pymupdf

from . import detect as D
from . import pdf
from . import statements
from .batch import Batch
from .model import VERSION, FileResult

STATUS_TEXT = {
    "ok": "Redacted",
    "no_findings": "Nothing detected - check manually",
    "locked": "Locked - add the password",
    "error": "Error",
}


# --------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------
def output_names(b: Batch) -> dict:
    names, i = {}, 0
    for r in b.results:
        if r.output is None:
            continue
        i += 1
        if b.opts.anonymise_names:
            names[r.name] = f"Document_{i:02d}{r.output_ext}"
        else:
            p = PurePosixPath(r.name.replace("\\", "/"))
            names[r.name] = str(p.with_name(f"{p.stem}_redacted{r.output_ext}"))
    return names


# --------------------------------------------------------------------------
# Bank statement transactions (from the redacted PDF)
# --------------------------------------------------------------------------
def transactions(r: FileResult) -> list[dict]:
    """Bank transactions of a redacted PDF statement (see redact/statements.py)."""
    if r.kind != "pdf" or not r.output or r.profile in ("notice", "kyc"):
        return []
    try:
        return statements.extract(r.output, strict=r.profile != "bank")
    except Exception:
        traceback.print_exc()
        return []


def sheet_rows(r: FileResult) -> list[list]:
    """The main sheet of a redacted Excel statement, as rows (for a CSV copy)."""
    if r.kind not in ("xlsx", "xls") or not r.output:
        return []
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(r.output), read_only=True, data_only=True)
        best = []
        for ws in wb.worksheets:
            rows = [["" if v is None else v for v in row] for row in ws.iter_rows(values_only=True)]
            rows = [row for row in rows if any(str(v).strip() for v in row)]
            if len(rows) > len(best):
                best = rows
        width = max((max((i + 1 for i, v in enumerate(row) if str(v).strip()), default=0) for row in best), default=0)
        return [row[:width] for row in best]
    except Exception:
        traceback.print_exc()
        return []


def table_csv(r: FileResult) -> tuple[str, bytes] | None:
    """('_transactions.csv' or '_table.csv', data) for a statement, or None when no table is recognised."""
    tx = transactions(r)
    if tx:
        return "_transactions.csv", _csv_bytes(tx)
    if r.profile == "bank":
        rows = sheet_rows(r)
        if len(rows) > 1:
            buf = io.StringIO()
            csv.writer(buf).writerows(rows)
            return "_table.csv", buf.getvalue().encode("utf-8-sig")
    return None


# --------------------------------------------------------------------------
# Logs and key
# --------------------------------------------------------------------------
def log_rows(b: Batch, hide_names: bool = False) -> list[dict]:
    names = output_names(b)
    rows = []
    for r in b.results:
        re_check = "-"
        if r.output is not None:
            n = r.residual + r.residual_ocr
            re_check = "Clean" if n == 0 else f"{n} remain"
            if r.ocr_pages and not r.verified_scans:
                re_check += " (scans not re-checked)"
        msg = r.message.strip() if r.status not in ("locked",) else ""
        rows.append({
            "File": "" if hide_names else r.name,
            "Output": names.get(r.name, "-"),
            "Detected type": D.PROFILE_LABELS.get(r.profile, r.profile),
            "Pages": str(r.pages) if r.kind == "pdf" else "-",
            "OCR pages": str(r.ocr_pages) if r.kind == "pdf" else "-",
            "Items redacted": len(r.findings),
            "Breakdown": ", ".join(f"{D.rule_label(k)}: {v}" for k, v in r.counts.items()),
            "Re-check": re_check,
            "Status": STATUS_TEXT.get(r.status, r.status) + (f" - {msg}" if msg else ""),
        })
    return rows


def _csv_bytes(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def key_csv(b: Batch) -> bytes:
    return _csv_bytes(b.ctx.key_rows() if b.ctx else [])


# --------------------------------------------------------------------------
# Combined PDF
# --------------------------------------------------------------------------
def combined_pdf(b: Batch) -> bytes | None:
    names = output_names(b)
    out = pymupdf.open()
    toc = []
    for r in b.results:
        if r.output is None or r.kind != "pdf":
            continue
        with pymupdf.open(stream=r.output, filetype="pdf") as d:
            toc.append([1, Path(names[r.name]).stem, out.page_count + 1])
            out.insert_pdf(d)
    if out.page_count == 0:
        return None
    out.set_toc(toc)
    out.set_metadata({})
    data = out.tobytes(garbage=4, deflate=True)
    out.close()
    return data


# --------------------------------------------------------------------------
# ZIPs
# --------------------------------------------------------------------------
def ai_zip(b: Batch, text: bool = True, tables: bool = True, combined: bool = False) -> bytes:
    """Everything meant to be uploaded to the AI tool."""
    names = output_names(b)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for r in b.results:
            if r.output is None:
                continue
            n = names[r.name]
            z.writestr(n, r.output)
            stem = str(PurePosixPath(n).with_suffix(""))
            if text and r.text_export and r.kind in ("pdf", "docx"):
                z.writestr(f"AI text extracts/{stem}.txt", r.text_export)
            if tables:
                t = table_csv(r)
                if t:
                    z.writestr(f"AI text extracts/{stem}{t[0]}", t[1])
        if combined:
            c = combined_pdf(b)
            if c:
                z.writestr("All_documents_combined.pdf", c)
    return buf.getvalue()


def records_zip(b: Batch, preparer: dict | str = "") -> bytes:
    """Kept on the user's computer: certificate, log, label key. Never upload."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Redaction_certificate.pdf", certificate_pdf(b, preparer))
        z.writestr("Redaction_log.csv", _csv_bytes(log_rows(b)))
        if b.opts.style == "label" and b.ctx:
            z.writestr("Label_key_CONFIDENTIAL.csv", key_csv(b))
        z.writestr("README.txt",
                   "These records identify the client and the original values.\n"
                   "Keep them on your computer. Do not upload them to any AI tool.\n")
    return buf.getvalue()


# --------------------------------------------------------------------------
# Certificate
# --------------------------------------------------------------------------
def certificate_pdf(b: Batch, details: dict | str | None = None) -> bytes:
    from .certificate import certificate_pdf as _cert
    if isinstance(details, str):
        details = {"name": details} if details.strip() else {}
    return _cert(b, details or {})


# --------------------------------------------------------------------------
# Folder mode
# --------------------------------------------------------------------------
def collect_folder(folder: str, recursive: bool, supported: set) -> list[tuple[str, bytes]]:
    root = Path(folder).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"Folder not found: {root}")
    it = root.rglob("*") if recursive else root.glob("*")
    files = []
    for p in sorted(it):
        if p.is_file() and p.suffix.lower() in supported and not p.name.startswith("~$"):
            files.append((p.relative_to(root).as_posix(), p.read_bytes()))
    return files


def write_folder_outputs(b: Batch, folder: str, text: bool, tables: bool, combined: bool, preparer: dict | str = ""):
    root = Path(folder).expanduser()
    out_dir = root.parent / f"{root.name} - Redacted"
    rec_dir = root.parent / f"{root.name} - Redaction records (do not upload)"
    out_dir.mkdir(exist_ok=True)
    rec_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(ai_zip(b, text, tables, combined))) as z:
        for n in z.namelist():
            dest = out_dir / n
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(n))
    with zipfile.ZipFile(io.BytesIO(records_zip(b, preparer))) as z:
        for n in z.namelist():
            (rec_dir / n).write_bytes(z.read(n))
    return out_dir, rec_dir
