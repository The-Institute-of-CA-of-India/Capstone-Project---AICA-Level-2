"""Mandatory audit step: prove the redacted PDF no longer contains any original value."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .. import APP_NAME, VERSION
from .allowlist import Allowlist
from .detectors import MasterEntry, detect_codes, detect_text
from .ingest import ocr_page, open_pdf_bytes, read_pdf_bytes, text_words
from .models import (
    NAME_TYPES,
    VISUAL_TYPES,
    PageInfo,
    UserFacingError,
    Word,
    intersect_area,
    rect_area,
    union_rect,
)
from .redact import sha256_bytes
from .tokens import TOKEN_RE, load_vault, normalise_name

log = logging.getLogger("mukhota.verify")
Progress = Callable[[int, str], None]

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
_TAIL_TYPES = {"AADHAAR", "BANK_AC"}
_TAIL_LABEL = re.compile(r"(?i)\ba/c\b|account|aadhaa?r|\buid\b|bank|saving|current")
_STRICT_RULE_PREFIX = ("CLIENT_MASTER",)
_TOKEN_WORD = re.compile(r"^\[?[A-Z]+(?:_[A-Z0-9]+)+\]?$|^\[[A-Z]+\]$")


@dataclass
class CheckResult:
    """One verification check."""

    name: str
    status: str
    details: list[str] = field(default_factory=list)
    leaks: list[dict[str, Any]] = field(default_factory=list)  # {"page": n, "type": t, "source": s}


@dataclass
class VerifyReport:
    """Full verification outcome; contains counts and page/type only, never values."""

    overall: str
    app_version: str
    created: str
    original_file: str
    original_sha256: str
    redacted_file: str
    redacted_sha256: str
    counts: dict[str, int]
    checks: list[CheckResult]
    report_txt: str = ""
    report_json: str = ""

    @property
    def verified(self) -> bool:
        return self.overall == PASS


def _compact(s: str) -> str:
    return re.sub(r"[\s\-./,]", "", s.lower())


def _clean(s: str) -> str:
    return TOKEN_RE.sub(" ", s)


def _find_files(redacted_pdf: Path) -> tuple[Path, Path]:
    folder = redacted_pdf.parent
    stem = redacted_pdf.stem
    base = stem[: -len("_REDACTED")] if stem.endswith("_REDACTED") else stem
    vault = folder / f"{base}.vault"
    if not vault.exists():
        found = sorted(folder.glob("*.vault"))
        vault = found[0] if found else vault
    return vault, folder / "candidates.json"


def _search_vault(entries: dict[str, Any], hay: dict[str, list[str]], cfg: dict[str, Any]) -> tuple[CheckResult, CheckResult, CheckResult]:
    """Checks 1-3: exact values in text layer, in OCR, then normalised variants and digit tails."""
    c1 = CheckResult("1. Original values absent from the text layer", PASS)
    c2 = CheckResult("2. Original values absent from OCR of every page", PASS)
    c3 = CheckResult("3. Normalised variants and digit tails absent", PASS)
    window = int(cfg["verify"]["tail_label_window"])
    ntail = int(cfg["verify"]["tail_digits"])
    skipped = 0
    for token, e in entries.items():
        value = str(e.get("value", ""))
        pii_type = e.get("pii_type", "")
        if pii_type in VISUAL_TYPES or value.startswith("visual:") or pii_type == "MANUAL" and not value.strip():
            continue
        raw = " ".join(value.lower().split())
        if len(_compact(raw)) < 4:
            skipped += 1
            continue
        comp = _compact(raw)
        nname = normalise_name(value) if pii_type in NAME_TYPES or pii_type in ("TERM", "MANUAL") else ""
        for source, pages in hay.items():
            check = c1 if source == "text layer" else c2
            for pno, text in enumerate(pages, start=1):
                low = " ".join(text.lower().split())
                if raw in low:
                    check.status = FAIL
                    check.leaks.append({"page": pno, "type": pii_type, "source": source})
                    continue
                if comp in _compact(low) or (nname and f" {nname} " in f" {normalise_name(text)} "):
                    c3.status = FAIL
                    c3.leaks.append({"page": pno, "type": pii_type, "source": source})
                    continue
                digits = re.sub(r"\D", "", value)
                if pii_type in _TAIL_TYPES and len(digits) >= ntail:
                    tail = digits[-ntail:]
                    for m in re.finditer(rf"(?<!\d){tail}(?!\d)", low):
                        ctx = low[max(0, m.start() - window): m.end() + window]
                        if _TAIL_LABEL.search(ctx):
                            c3.status = FAIL
                            c3.leaks.append({"page": pno, "type": f"{pii_type} (last {ntail} digits)", "source": source})
                        else:
                            if c3.status == PASS:
                                c3.status = WARN
                            c3.details.append(
                                f"Page {pno}: a {ntail}-digit number matching the end of a {pii_type} appears "
                                f"({source}) without an account/Aadhaar label nearby - please glance at it."
                            )
                        break
    if skipped:
        c3.details.append(f"{skipped} very short value(s) (under 4 characters) were not searched.")
    return c1, c2, c3


def _metadata_check(doc) -> CheckResult:
    c = CheckResult("5. Metadata, annotations, attachments, JavaScript and form fields are empty", PASS)
    md = doc.metadata or {}
    for key in ("author", "title", "subject", "keywords", "creator"):
        if (md.get(key) or "").strip():
            c.status = FAIL
            c.details.append(f"Metadata field '{key}' is not empty.")
    if (md.get("producer") or "") not in ("", APP_NAME):
        c.status = FAIL
        c.details.append("Producer is not 'Mukhota'.")
    if doc.get_xml_metadata().strip():
        c.status = FAIL
        c.details.append("XMP metadata is present.")
    if doc.embfile_count():
        c.status = FAIL
        c.details.append("Embedded files are present.")
    for pno, page in enumerate(doc, start=1):
        if page.first_annot:
            c.status = FAIL
            c.leaks.append({"page": pno, "type": "ANNOTATION", "source": "structure"})
        if page.first_widget:
            c.status = FAIL
            c.leaks.append({"page": pno, "type": "FORM_FIELD", "source": "structure"})
        if page.get_links():
            c.status = FAIL
            c.leaks.append({"page": pno, "type": "LINK", "source": "structure"})
    for xref in range(1, doc.xref_length()):
        try:
            obj = doc.xref_object(xref, compressed=False)
        except Exception:
            continue
        if "/JavaScript" in obj or re.search(r"/JS\b", obj):
            c.status = FAIL
            c.details.append("JavaScript was found in the file.")
            break
    return c


def _was_rejected(cand, rejected: list[dict[str, Any]]) -> bool:
    box = union_rect(cand.bboxes)
    for r in rejected:
        if r.get("page") != cand.page + 1:
            continue
        rb = tuple(r.get("bbox", (0, 0, 0, 0)))
        if intersect_area(box, rb) >= 0.5 * max(rect_area(box), 1e-6):
            return True
    return False


def _detector_check(
    text_pages: list[PageInfo],
    ocr_pages: list[PageInfo],
    doc,
    cfg,
    allow: Allowlist,
    master: list[MasterEntry],
    rejected: list[dict[str, Any]],
) -> CheckResult:
    c = CheckResult("4. Detectors re-run on the redacted PDF find no remaining PII", PASS)
    for source, pages in (("text layer", text_pages), ("OCR", ocr_pages)):
        cands, _, _ = detect_text(pages, cfg, allow, master, use_spacy=False)
        for cand in cands:
            if not re.sub(r"[^A-Za-z0-9]", "", _clean(cand.text)):
                continue
            if _was_rejected(cand, rejected):
                if c.status == PASS:
                    c.status = WARN
                c.details.append(f"Page {cand.page + 1}: {cand.pii_type} left visible because you rejected it during review.")
                continue
            strict = cand.pii_type not in NAME_TYPES or cand.rule_id.startswith(_STRICT_RULE_PREFIX)
            if strict and cand.confidence >= 0.8:
                c.status = FAIL
                c.leaks.append({"page": cand.page + 1, "type": cand.pii_type, "source": source})
            else:
                if c.status == PASS:
                    c.status = WARN
                c.details.append(f"Page {cand.page + 1}: possible {cand.pii_type} ({source}) - please review.")
    dpi = int(cfg["detection"]["visual_dpi"])
    for pno, page in enumerate(doc):
        for cand in detect_codes(page, pno, dpi):
            c.status = FAIL
            c.leaks.append({"page": pno + 1, "type": cand.pii_type, "source": "image"})
    return c


def _coverage_check(cand_meta: dict[str, Any] | None, page_count: int) -> CheckResult:
    c = CheckResult("6. Every page has a redaction or is marked 'reviewed - no PII'", PASS)
    if not cand_meta:
        c.status = FAIL
        c.details.append("candidates.json is missing, so page coverage cannot be confirmed.")
        return c
    pages = {p["page"]: p for p in cand_meta.get("pages", [])}
    for pno in range(1, page_count + 1):
        p = pages.get(pno)
        if not p or (p.get("redactions", 0) == 0 and not p.get("reviewed_no_pii")):
            c.status = FAIL
            c.leaks.append({"page": pno, "type": "UNREVIEWED_PAGE", "source": "coverage"})
    return c


def _strip_token_words(words: list[Word]) -> list[Word]:
    return [w for w in words if not _TOKEN_WORD.match(w.text)]


def verify(
    redacted_pdf: str | Path,
    cfg: dict[str, Any],
    allow: Allowlist,
    master: list[MasterEntry],
    progress: Progress | None = None,
) -> VerifyReport:
    """Run all checks, write verify_report.txt/.json next to the PDF and return the report."""
    progress = progress or (lambda _p, _m="": None)
    red_path = Path(redacted_pdf)
    data = read_pdf_bytes(red_path)
    red_sha = sha256_bytes(data)
    doc = open_pdf_bytes(data)
    vault_path, cand_path = _find_files(red_path)

    vault: dict[str, Any] = {"meta": {}, "entries": {}}
    vault_error = ""
    try:
        vault = load_vault(vault_path)
    except UserFacingError as exc:
        vault_error = str(exc)
    cand_meta = None
    if cand_path.exists():
        cand_meta = json.loads(cand_path.read_text(encoding="utf-8"))

    n = doc.page_count
    text_layer: list[str] = []
    ocr_text: list[str] = []
    text_pages: list[PageInfo] = []
    ocr_pages: list[PageInfo] = []
    dpi = int(cfg["verify"]["ocr_dpi"])
    for i, page in enumerate(doc):
        progress(int(i * 70 / n), f"Re-reading page {i + 1} of {n} (text layer and OCR)")
        text_layer.append(_clean(page.get_text("text")))
        tw = _strip_token_words(text_words(page))
        ow = _strip_token_words(ocr_page(page, dpi))
        ocr_text.append(_clean(" ".join(w.text for w in ow)))
        text_pages.append(PageInfo(i, "TEXT", page.rect.width, page.rect.height, tw))
        ocr_pages.append(PageInfo(i, "IMAGE", page.rect.width, page.rect.height, ow))

    progress(72, "Searching for original values")
    if vault_error:
        c1 = CheckResult("1. Original values absent from the text layer", FAIL, [vault_error])
        c2 = CheckResult("2. Original values absent from OCR of every page", FAIL, [vault_error])
        c3 = CheckResult("3. Normalised variants and digit tails absent", FAIL, [vault_error])
    else:
        c1, c2, c3 = _search_vault(vault.get("entries", {}), {"text layer": text_layer, "OCR": ocr_text}, cfg)
    progress(80, "Re-running detectors")
    c4 = _detector_check(text_pages, ocr_pages, doc, cfg, allow, master, (cand_meta or {}).get("rejected", []))
    progress(92, "Checking metadata and page coverage")
    c5 = _metadata_check(doc)
    c6 = _coverage_check(cand_meta, n)
    doc.close()
    checks = [c1, c2, c3, c4, c5, c6]
    overall = FAIL if any(c.status == FAIL for c in checks) else PASS

    counts: dict[str, int] = {}
    for item in (cand_meta or {}).get("items", []):
        counts[item["type"]] = counts.get(item["type"], 0) + 1
    meta = vault.get("meta", {})
    report = VerifyReport(
        overall=overall,
        app_version=f"{APP_NAME} {VERSION}",
        created=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        original_file=meta.get("original_file", "unknown"),
        original_sha256=meta.get("original_sha256", "unknown"),
        redacted_file=red_path.name,
        redacted_sha256=red_sha,
        counts=counts,
        checks=checks,
    )
    write_reports(report, red_path.parent)
    progress(100, "Verification finished")
    log.info("Verification %s: %s", overall, {c.name.split(".")[0]: c.status for c in checks})
    return report


def write_reports(report: VerifyReport, folder: Path) -> None:
    """Save verify_report.txt and verify_report.json (no values, only counts/pages/types)."""
    txt = folder / "verify_report.txt"
    js = folder / "verify_report.json"
    lines = [
        "Mukhota Verification Report",
        "=" * 27,
        f"App version        : {report.app_version}",
        f"Date-time          : {report.created}",
        f"Original file      : {report.original_file}",
        f"SHA-256 (original) : {report.original_sha256}",
        f"Redacted file      : {report.redacted_file}",
        f"SHA-256 (redacted) : {report.redacted_sha256}",
        "",
        "Items redacted by type (counts only)",
    ]
    for t, n in sorted(report.counts.items()):
        lines.append(f"  {t:<12}{n:>5}")
    if not report.counts:
        lines.append("  (none)")
    lines += ["", "Checks"]
    for c in report.checks:
        lines.append(f"  [{c.status}] {c.name}")
        for lk in c.leaks:
            lines.append(f"         - Page {lk['page']}: {lk['type']} ({lk['source']})")
        for d in c.details:
            lines.append(f"         - {d}")
    verdict = "PASS - VERIFIED, SAFE TO SHARE" if report.verified else "FAIL - VERIFICATION FAILED, DO NOT SHARE"
    lines += ["", f"OVERALL RESULT: {verdict}", ""]
    txt.write_text("\n".join(lines), encoding="utf-8")

    payload = {
        "title": "Mukhota Verification Report",
        "app_version": report.app_version,
        "created": report.created,
        "original_file": report.original_file,
        "original_sha256": report.original_sha256,
        "redacted_file": report.redacted_file,
        "redacted_sha256": report.redacted_sha256,
        "counts": report.counts,
        "checks": [asdict(c) for c in report.checks],
        "overall": report.overall,
        "verified": report.verified,
    }
    js.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report.report_txt, report.report_json = str(txt), str(js)


def is_verified(pdf_path: str | Path) -> bool:
    """True only if a PASS report next to the PDF matches the file's current SHA-256.

    Later phases must call this and refuse to upload any PDF for which it is False.
    """
    pdf = Path(pdf_path)
    report = pdf.parent / "verify_report.json"
    if not pdf.exists() or not report.exists():
        return False
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        data.get("verified") is True
        and data.get("overall") == PASS
        and data.get("redacted_file") == pdf.name
        and data.get("redacted_sha256") == sha256_bytes(pdf.read_bytes())
    )
