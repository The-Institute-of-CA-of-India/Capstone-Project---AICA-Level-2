"""Shared data structures (plain, picklable - they cross process boundaries)."""

from __future__ import annotations

from dataclasses import dataclass, field

VERSION = "2.3.3"
APP_NAME = "PDF Redactor PRO"
AUTHOR = "CA Lucika Mehta"
CONTACT_PHONE = "+91 90190 79090"
CONTACT_EMAIL = "orsshah@gmail.com"


@dataclass
class Options:
    rules: set = field(default_factory=set)       # rule keys selected by the user
    profile: str = "auto"                         # auto | bank | notice | kyc | other | asis
    style: str = "black"                          # black | label
    custom_terms: list = field(default_factory=list)
    keep_terms: list = field(default_factory=list)
    protect_itba_din: bool = True
    propagate: bool = True                        # redact a value everywhere in the batch
    ocr_mode: str = "auto"                        # off | auto | all
    ocr_dpi: int = 300
    ocr_langs: tuple = ("eng",)
    verify_scans: bool = True                     # re-OCR redacted scanned pages
    add_text_layer: bool = True                   # invisible OCR text on scanned pages
    passwords: list = field(default_factory=list)
    password_hints: dict = field(default_factory=dict)
    scrub_metadata: bool = True
    anonymise_names: bool = False
    workers: int = 1
    padding: float = 1.0


@dataclass
class SourceText:
    kind: str            # "text" (digital layer) or "ocr"
    text: str            # rows joined with "\n"
    boxes: list          # per character: (x0, y0, x1, y1) or None
    rows: list           # per character: row index (or -1)


@dataclass
class PageData:
    number: int                       # 0-based
    sources: list = field(default_factory=list)
    has_images: bool = False
    ocr_done: bool = False
    visual: list = field(default_factory=list)    # [(kind, (x0, y0, x1, y1))]


@dataclass
class Finding:
    page: int            # 1-based; 0 for office files
    rule: str
    value: str
    source: str          # text | ocr | visual | cell | manual
    label: str = ""      # token in labelled mode, e.g. ACCT-1
    where: str = ""      # office files: sheet!cell or paragraph
    boxes: list = field(default_factory=list)   # [(x0, y0, x1, y1)] as fractions of the displayed page

    @property
    def masked(self) -> str:
        v = self.value.strip()
        if len(v) <= 4:
            return "•" * len(v)
        keep = 2 if len(v) < 10 else 3
        return v[:keep] + "•" * (len(v) - 2 * keep) + v[-keep:]


@dataclass
class FileScan:
    """Result of pass 1 (reading + detection), reused in pass 2."""
    name: str
    kind: str = "pdf"                 # pdf | xlsx | csv | docx
    status: str = "ok"                # ok | locked | error
    message: str = ""
    profile: str = "other"
    pdf_bytes: bytes | None = None    # unlocked PDF (images converted)
    raw: bytes | None = None          # original bytes (office files)
    pages: list = field(default_factory=list)       # PageData
    findings: list = field(default_factory=list)    # Finding (with values)
    ocr_pages: int = 0
    page_count: int = 0


@dataclass
class Overrides:
    """Per-file manual touch-ups from the review screen."""
    keep_values: set = field(default_factory=set)   # un-redact these values
    terms: list = field(default_factory=list)       # extra text to redact
    boxes: list = field(default_factory=list)       # [(page0, (x0, y0, x1, y1))]


@dataclass
class FileResult:
    name: str
    kind: str = "pdf"
    status: str = "ok"                # ok | no_findings | locked | error
    message: str = ""
    profile: str = "other"
    pages: int = 0
    ocr_pages: int = 0
    findings: list = field(default_factory=list)
    residual: int = 0
    residual_ocr: int = 0
    residual_notes: list = field(default_factory=list)   # [(page, rule, masked value)]
    verified_scans: bool = False
    layout_pages: list = field(default_factory=list)       # pages where kept text moved
    kept: list = field(default_factory=list)               # Findings left visible on purpose
    output: bytes | None = None
    output_ext: str = ".pdf"
    text_export: str = ""
    transactions: list = field(default_factory=list)
    sha_in: str = ""
    sha_out: str = ""

    @property
    def counts(self) -> dict:
        out: dict = {}
        for f in self.findings:
            out[f.rule] = out.get(f.rule, 0) + 1
        return out
