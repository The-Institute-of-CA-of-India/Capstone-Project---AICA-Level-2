"""PII detectors. Each produces :class:`Candidate` objects with page, boxes, type and confidence."""
from __future__ import annotations

import csv
import difflib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import fitz
import numpy as np

from .allowlist import Allowlist
from .ingest import pdf_to_pixel, pixel_to_pdf, render_page_array
from .models import (
    VISUAL_TYPES,
    Candidate,
    PageInfo,
    UserFacingError,
    build_page_text,
    intersect_area,
    rect_area,
    union_rect,
)
from .tokens import norm_word, normalise_name

log = logging.getLogger("mukhota.detectors")
Progress = Callable[[int, str], None]

# --------------------------------------------------------------------------- validators

_GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_checksum_ok(gstin: str) -> bool:
    """Validate the GSTIN mod-36 check character."""
    g = gstin.upper()
    if len(g) != 15 or any(c not in _GST_CHARS for c in g):
        return False
    total = 0
    for i, ch in enumerate(g[:14]):
        prod = _GST_CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += prod // 36 + prod % 36
    return _GST_CHARS[(36 - total % 36) % 36] == g[14]


_VD = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VP = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def verhoeff_ok(number: str) -> bool:
    """Validate a number with the Verhoeff checksum (used by Aadhaar)."""
    digits = re.sub(r"\D", "", number)
    if not digits:
        return False
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VD[c][_VP[i % 8][int(ch)]]
    return c == 0


# --------------------------------------------------------------------------- patterns

_PAN_BODY = r"[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]"
RE_PAN = re.compile(rf"\b{_PAN_BODY}\b")
RE_GSTIN = re.compile(rf"\b[0-9]{{2}}{_PAN_BODY}[1-9A-Z]Z[0-9A-Z]\b")
RE_TAN = re.compile(r"\b[A-Z]{4}[0-9]{5}[A-Z]\b")
RE_AADHAAR = re.compile(r"(?<![\dA-Za-z])[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?![\dA-Za-z])")
RE_AADHAAR_MASKED = re.compile(r"(?<![\w])[Xx*]{4}[ -]?[Xx*]{4}[ -]?\d{4}(?!\d)")
RE_MOBILE = re.compile(r"(?<![\d+])(?:(?:\+|00)?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
RE_LANDLINE = re.compile(r"(?<![\d+])(?:\+91[\s-]?)?\(?0\d{2,4}\)?[\s-]?\d{6,8}(?!\d)")
RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RE_IFSC = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
RE_ACCOUNT = re.compile(r"(?<![\dA-Za-z])\d{9,18}(?![\dA-Za-z])")
RE_BANK_LABEL = re.compile(r"(?i)(?:\ba/c\b|\bacct?\b|\baccount|\bbank\b|\bifsc\b|\bsavings?\b|\bcurrent\b)")
RE_CIN = re.compile(r"\b[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\b")
RE_LLPIN = re.compile(r"\b[A-Z]{3}-[0-9]{4}\b")
RE_DIN = re.compile(r"\bDIN\b\s*(?:No\.?|Number)?\s*[:.\-]?\s*(\d{8})(?![\dA-Za-z])")
RE_NOTICE_DIN_CTX = re.compile(r"(?i)document\s+identification|cbic|itba")
RE_UDYAM = re.compile(r"(?i)\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b")
RE_IEC = re.compile(r"\bIEC\b\s*(?:No\.?|Code)?\s*[:.\-]?\s*([A-Z0-9]{10})\b")
RE_PASSPORT = re.compile(r"\b[A-Z][0-9]{7}\b")
RE_PASSPORT_LABEL = re.compile(r"(?i)passport")
_RTO = (
    "AN AP AR AS BR CG CH DD DL DN GA GJ HP HR JH JK KA KL LA LD MH ML MN MP MZ NL "
    "OD OR PB PY RJ SK TN TR TS UK UP WB"
).split()
RE_VEHICLE = re.compile(rf"\b(?:{'|'.join(_RTO)})[ -]?\d{{1,2}}[ -]?[A-Z]{{1,3}}[ -]?\d{{4}}\b")
RE_PIN = re.compile(r"(?<!\d)[1-9]\d{2}\s?\d{3}(?!\d)")
RE_PIN_LABEL = re.compile(r"(?i)\bpin(?:\s*code)?\b")

_SAL = r"(?:M/s\.?|M/S\.?|Messrs\.?|Shri\.?|Smt\.?|Sh\.|Mr\.?|Mrs\.?|Ms\.?|Kumari|Kum\.|Dr\.?)"
_CAP_WORD = r"[A-Z][\w.&'\-]*"
RE_SALUTATION = re.compile(rf"\b{_SAL}\s+({_CAP_WORD}(?: (?:{_CAP_WORD}|&|and|of))" r"{0,7})")
RE_SAL_PREFIX = re.compile(rf"^\s*{_SAL}\s+")
RE_TO_LINE = re.compile(r"^\s*To\b[\s,:]*(.*)$")
RE_STOP = re.compile(
    r"(?i)^\s*(?:sub(?:ject)?\b|ref(?:erence)?\b|sir\b|madam\b|dear\b|dated?\b|notice\b|gstin\b|pan\b|"
    r"e-?mail\b|mobile\b|phone\b|tel\b|din\b|whereas\b|please\b|in\s+the\s+matter|kindly\b|this\b)"
)
RE_ORG_WORDS = re.compile(
    r"(?i)\b(?:private|pvt|limited|ltd|llp|company|co\.|corporation|traders|enterprises|industries|"
    r"associates|agencies|foundation|trust|society|sons|brothers|bros|udyog|infra|solutions|services)\b|&"
)
RE_ADDR_LABEL = re.compile(
    r"(?i)\b(?:(?:address|addr\.|principal\s+place\s+of\s+business)\s*[:\-]|residing\s+at|r/o|office\s+at)\s*"
)
RE_ADDR_HINT = re.compile(
    r"(?i)\b(?:road|rd|marg|nagar|colony|society|soc|chs|apartments?|apt|building|bldg|floor|flat|plot|"
    r"sector|lane|gali|street|chowk|peth|wadi|village|vill|taluka|tal|dist|district|near|opp|behind|midc|"
    r"estate|park|tower|house|cross|layout|block|phase|pincode|maharashtra|gujarat|karnataka|delhi|"
    r"tamil\s+nadu|telangana|kerala|rajasthan|madhya\s+pradesh|uttar\s+pradesh|west\s+bengal|bihar|goa|"
    r"punjab|haryana|odisha|mumbai|pune|thane|nagpur|nashik|bengaluru|bangalore|chennai|hyderabad|kolkata|"
    r"ahmedabad|surat)\b|\d{3}\s?\d{3}|,"
)
RE_NAME_LABEL = re.compile(
    r"(?i)\b(legal\s+name|trade\s+name|name\s+of\s+(?:the\s+)?(?:taxpayer|tax\s*payer|assessee|firm|company|"
    r"proprietor|director|partner|business|person|applicant|noticee|dealer|registered\s+person)|name)"
    r"(?:\s+of\s+business)?\s*[:\-]\s*"
)
RE_LABEL_CUT = re.compile(r"(?i)\s+(?:gstin|pan|address|date|mobile|e-?mail|phone|din|tan)\b")
RE_SIGNED_BY = re.compile(r"(?i)\b(?:digitally\s+)?signed\s+by\s*[:\-]?\s*")
RE_SIGNED_CUT = re.compile(r"(?i)\s+(?:date|reason|location|on)\b|[,;]")
RE_DESIG = re.compile(
    r"(?i)\b(?:superintendent|inspector|(?:joint|additional|deputy|assistant|principal|chief)\s+commissioner|"
    r"commissioner|income[\s-]*tax\s+officer|assessing\s+officer|ito|tax\s+recovery\s+officer|"
    r"state\s+tax\s+officer|range\s+officer)\b"
)
RE_PAREN_NAME = re.compile(r"\(([A-Z][A-Za-z. ]{2,40})\)")
RE_WARD = re.compile(
    r"(?i)\b(?:ward|circle|range|division)\s*[-:]?\s*(?:no\.?\s*)?[\dIVX]+(?:\s*\(\s*\d+\s*\))*(?:\s*,\s*[A-Z][a-z]+)?"
)
RE_SIG_LABEL = re.compile(r"(?i)signature|authori[sz]ed\s+signatory|signed\s+by|\(\s*seal\s*\)|seal\s+of")
RE_NAME_LIKE = re.compile(r"^[A-Z][A-Za-z.' ]{1,48}$")


# --------------------------------------------------------------------------- client master

@dataclass
class MasterEntry:
    """One row of client_master.csv."""

    term: str
    pii_type: str
    role: str
    compact: str = ""
    nwords: int = 1


def load_client_master(path: Path) -> list[MasterEntry]:
    """Read client_master.csv (columns: term, pii_type, role)."""
    if not path.exists():
        return []
    out: list[MasterEntry] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                term = (row.get("term") or "").strip()
                if not term:
                    continue
                words = normalise_name(term).split()
                compact = "".join(words)
                if len(compact) < 3:
                    continue
                out.append(
                    MasterEntry(
                        term,
                        (row.get("pii_type") or "NAME").strip().upper(),
                        (row.get("role") or "").strip().lower(),
                        compact,
                        max(len(words), 1),
                    )
                )
    except (OSError, csv.Error) as exc:
        raise UserFacingError("client_master.csv could not be read. Please check it in Settings.") from exc
    return out


def save_client_master(path: Path, rows: list[tuple[str, str, str]]) -> None:
    """Write client_master.csv from (term, pii_type, role) rows."""
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["term", "pii_type", "role"])
        for term, pii_type, role in rows:
            if term.strip():
                w.writerow([term.strip(), pii_type.strip().upper() or "NAME", role.strip().lower()])


# --------------------------------------------------------------------------- page context

class _PageCtx:
    """Holds a page's searchable text and collects candidates for it."""

    def __init__(self, info: PageInfo, allow: Allowlist) -> None:
        self.info = info
        self.pt = build_page_text(info.words)
        self.text = self.pt.text
        self.allow = allow
        self.out: list[Candidate] = []
        self.address_lines: set[int] = set()

    def chunk(self, start: int, end: int) -> str:
        s, e = start, end
        while s > 0 and not self.text[s - 1].isspace():
            s -= 1
        while e < len(self.text) and not self.text[e].isspace():
            e += 1
        return self.text[s:e]

    def add(
        self,
        start: int,
        end: int,
        pii_type: str,
        rule: str,
        conf: float,
        role: str = "",
        check_allow: bool = True,
    ) -> Candidate | None:
        while start < end and self.text[start].isspace():
            start += 1
        while end > start and self.text[end - 1] in " ,.;:-\n":
            end -= 1
        if end <= start:
            return None
        value = self.text[start:end]
        if check_allow and self.allow.is_allowed(value, self.chunk(start, end), self.text[max(0, start - 25):start]):
            return None
        rects = self.pt.rects(self.info.words, start, end)
        if not rects:
            return None
        wc = self.pt.min_conf(self.info.words, start, end)
        cand = Candidate(self.info.index, rects, value, pii_type, round(conf * wc, 3), rule, role=role)
        self.out.append(cand)
        return cand

    def near(self, start: int, end: int, pattern: re.Pattern, window: int = 40) -> bool:
        return bool(pattern.search(self.text[max(0, start - window): min(len(self.text), end + window)]))

    def line_text(self, li: int) -> str:
        s, e, _ = self.pt.lines[li]
        return self.text[s:e]

    def line_rect(self, li: int):
        s, e, _ = self.pt.lines[li]
        rects = self.pt.rects(self.info.words, s, e)
        return union_rect(rects) if rects else None


# --------------------------------------------------------------------------- ID detectors

def _detect_ids(ctx: _PageCtx) -> None:
    t = ctx.text
    for m in RE_GSTIN.finditer(t):
        ok = gstin_checksum_ok(m.group(0))
        ctx.add(*m.span(), "GSTIN", "GSTIN" if ok else "GSTIN_NOCHECK", 0.97 if ok else 0.65)
    for m in RE_PAN.finditer(t):
        ctx.add(*m.span(), "PAN", "PAN", 0.95)
    for m in RE_TAN.finditer(t):
        ctx.add(*m.span(), "TAN", "TAN", 0.85)
    for m in RE_AADHAAR.finditer(t):
        if verhoeff_ok(m.group(0)):
            ctx.add(*m.span(), "AADHAAR", "AADHAAR", 0.95)
        elif ctx.near(*m.span(), re.compile(r"(?i)aadhaa?r|\buid\b")):
            ctx.add(*m.span(), "AADHAAR", "AADHAAR_NOCHECK", 0.65)
    for m in RE_AADHAAR_MASKED.finditer(t):
        ctx.add(*m.span(), "AADHAAR", "AADHAAR_MASKED", 0.85)
    for m in RE_MOBILE.finditer(t):
        ctx.add(*m.span(), "MOBILE", "MOBILE", 0.9)
    for m in RE_LANDLINE.finditer(t):
        digits = re.sub(r"\D", "", m.group(0))
        if digits.startswith("91") and len(digits) > 11:
            digits = digits[2:]
        if len(digits.lstrip("0")) == 10:
            ctx.add(*m.span(), "LANDLINE", "LANDLINE", 0.75)
    for m in RE_EMAIL.finditer(t):
        ctx.add(*m.span(), "EMAIL", "EMAIL", 0.95)
    for m in RE_IFSC.finditer(t):
        ctx.add(*m.span(), "IFSC", "IFSC", 0.95)
    for m in RE_ACCOUNT.finditer(t):
        if ctx.near(*m.span(), RE_BANK_LABEL, 40):
            ctx.add(*m.span(), "BANK_AC", "BANK_AC", 0.85)
    for m in RE_CIN.finditer(t):
        ctx.add(*m.span(), "CIN", "CIN", 0.95)
    for m in RE_LLPIN.finditer(t):
        ctx.add(*m.span(), "LLPIN", "LLPIN", 0.8)
    for m in RE_DIN.finditer(t):
        if not RE_NOTICE_DIN_CTX.search(t[max(0, m.start() - 40): m.start()]):
            ctx.add(*m.span(1), "DIN", "DIRECTOR_DIN", 0.9)
    for m in RE_UDYAM.finditer(t):
        ctx.add(*m.span(), "UDYAM", "UDYAM", 0.95)
    for m in RE_IEC.finditer(t):
        ctx.add(*m.span(1), "IEC", "IEC", 0.9)
    for m in RE_PASSPORT.finditer(t):
        if RE_PASSPORT_LABEL.search(t[max(0, m.start() - 40): m.start()]):
            ctx.add(*m.span(), "PASSPORT", "PASSPORT", 0.9)
    for m in RE_VEHICLE.finditer(t):
        ctx.add(*m.span(), "VEHICLE", "VEHICLE", 0.75)


# --------------------------------------------------------------------------- names / addresses

def _name_type(text: str) -> str:
    return "ORG" if RE_ORG_WORDS.search(text) else "NAME"


def _trim_generic_tail(ctx: _PageCtx, start: int, end: int) -> int:
    """Drop trailing generic words such as 'Proprietor' or 'and' from a name span."""
    words = ctx.text[start:end].split(" ")
    while len(words) > 1 and (words[-1].lower() in {"and", "of", "&"} or ctx.allow.is_allowed(words[-1])):
        words.pop()
    return start + len(" ".join(words))


def _detect_names_addresses(ctx: _PageCtx, cfg: dict[str, Any], state: dict[str, Any]) -> None:
    t = ctx.text
    lines = ctx.pt.lines
    redact_officer = bool(cfg["detection"]["redact_officer"])

    # "To" block: first line is the addressee, following lines are the address.
    for li in range(len(lines)):
        m = RE_TO_LINE.match(ctx.line_text(li))
        if not m:
            continue
        rest = m.group(1)
        if rest and rest[0].islower():
            continue
        first = li if rest.strip() else li + 1
        block: list[int] = []
        prev = ctx.line_rect(li)
        j = first
        while j < len(lines) and len(block) < 7:
            lt = ctx.line_text(j)
            if j != li and RE_STOP.match(lt):
                break
            r = ctx.line_rect(j)
            if j != li and prev and r and (r[1] - prev[3]) > 1.8 * max(prev[3] - prev[1], 6):
                break
            block.append(j)
            prev = r
            j += 1
        name_done = False
        for k, lj in enumerate(block):
            s, e, _ = lines[lj]
            if lj == li:
                s = s + m.start(1)
            lt = t[s:e]
            sal = RE_SAL_PREFIX.match(lt)
            if sal:
                s += sal.end()
            if not name_done:
                if ctx.allow.is_allowed(t[s:e]):
                    continue  # "The Proprietor" etc. - the name is on the next line
                role = ""
                if not state["assessee_assigned"] and not state["master_has_assessee"]:
                    role = "assessee"
                    state["assessee_assigned"] = True
                ctx.add(s, e, _name_type(t[s:e]), "TO_BLOCK_NAME", 0.85, role=role)
                name_done = True
            else:
                if ctx.add(s, e, "ADDRESS", "TO_BLOCK_ADDRESS", 0.8):
                    ctx.address_lines.add(lj)

    # Salutations: M/s, Shri, Smt, Mr, Ms ...
    for m in RE_SALUTATION.finditer(t):
        s, e = m.span(1)
        e = _trim_generic_tail(ctx, s, e)
        ctx.add(s, e, _name_type(t[s:e]), "SALUTATION", 0.85)

    # "Name: ..." labels
    for li in range(len(lines)):
        s0, e0, _ = lines[li]
        lt = t[s0:e0]
        m = RE_NAME_LABEL.search(lt)
        if not m:
            continue
        s = s0 + m.end()
        cut = RE_LABEL_CUT.search(lt, m.end())
        e = s0 + cut.start() if cut else e0
        label = m.group(1).lower()
        role = ""
        if any(k in label for k in ("taxpayer", "tax payer", "assessee", "legal name", "trade name", "noticee")):
            role = "" if state["master_has_assessee"] else "assessee"
        elif "director" in label:
            role = "director"
        elif "partner" in label:
            role = "partner"
        ctx.add(s, e, _name_type(t[s:e]), "NAME_LABEL", 0.85, role=role)

    # "Address: ..." labels (rest of line plus up to two address-like lines)
    for li in range(len(lines)):
        s0, e0, _ = lines[li]
        m = RE_ADDR_LABEL.search(t[s0:e0])
        if not m:
            continue
        if ctx.add(s0 + m.end(), e0, "ADDRESS", "ADDRESS_LABEL", 0.85):
            ctx.address_lines.add(li)
        prev = ctx.line_rect(li)
        for lj in (li + 1, li + 2):
            if lj >= len(lines):
                break
            lt = ctx.line_text(lj)
            r = ctx.line_rect(lj)
            if RE_STOP.match(lt) or not RE_ADDR_HINT.search(lt):
                break
            if prev and r and (r[1] - prev[3]) > 1.8 * max(prev[3] - prev[1], 6):
                break
            if ctx.add(lines[lj][0], lines[lj][1], "ADDRESS", "ADDRESS_LABEL", 0.8):
                ctx.address_lines.add(lj)
            prev = r

    if not redact_officer:
        return

    # "Digitally signed by XYZ"
    for m in RE_SIGNED_BY.finditer(t):
        s = m.end()
        line_end = t.find("\n", s)
        line_end = len(t) if line_end < 0 else line_end
        cut = RE_SIGNED_CUT.search(t, s, line_end)
        e = cut.start() if cut else line_end
        ctx.add(s, e, "OFFICER", "SIGNED_BY", 0.8, role="officer")

    # Officer name on the line above a designation, or in brackets next to it
    for li in range(len(lines)):
        lt = ctx.line_text(li)
        if not RE_DESIG.search(lt):
            continue
        for lj in (li - 1, li):
            if lj < 0:
                continue
            s0, e0, _ = lines[lj]
            for pm in RE_PAREN_NAME.finditer(t[s0:e0]):
                if not ctx.allow.is_department(pm.group(1)):
                    ctx.add(s0 + pm.start(1), s0 + pm.end(1), "OFFICER", "OFFICER_PAREN", 0.8, role="officer")
        if li > 0:
            above = ctx.line_text(li - 1).strip().strip("()")
            if (
                RE_NAME_LIKE.match(above)
                and 1 <= len(above.split()) <= 5
                and not RE_DESIG.search(above)
                and not ctx.allow.is_department(above)
            ):
                s0, e0, _ = lines[li - 1]
                ctx.add(s0, e0, "OFFICER", "OFFICER_ABOVE_DESIG", 0.75, role="officer")
    for m in RE_WARD.finditer(t):
        ctx.add(*m.span(), "WARD", "WARD_CIRCLE", 0.75, check_allow=False)


def _detect_pin(ctx: _PageCtx) -> None:
    for li in range(len(ctx.pt.lines)):
        s0, e0, _ = ctx.pt.lines[li]
        lt = ctx.text[s0:e0]
        if li not in ctx.address_lines and not RE_PIN_LABEL.search(lt):
            continue
        for m in RE_PIN.finditer(lt):
            ctx.add(s0 + m.start(), s0 + m.end(), "PIN", "PIN_IN_ADDRESS", 0.85)


# --------------------------------------------------------------------------- client master (fuzzy)

def _detect_master(ctx: _PageCtx, master: list[MasterEntry], threshold: float) -> None:
    if not master:
        return
    toks = [(i, norm_word(w.text)) for i, w in enumerate(ctx.info.words)]
    toks = [(i, w) for i, w in toks if w and w not in {"ms", "messrs"}]
    # Use text order so windows follow reading order.
    toks.sort(key=lambda p: ctx.pt.word_spans[p[0]][0])
    for entry in master:
        found: list[tuple[float, int, int]] = []
        for size in range(max(entry.nwords - 1, 1), entry.nwords + 3):
            for a in range(0, len(toks) - size + 1):
                window = toks[a:a + size]
                comp = "".join(w for _, w in window)
                if not comp or comp[0] != entry.compact[0]:
                    continue
                if abs(len(comp) - len(entry.compact)) > max(2, int(0.25 * len(entry.compact))):
                    continue
                sm = difflib.SequenceMatcher(None, comp, entry.compact)
                if sm.real_quick_ratio() < threshold or sm.quick_ratio() < threshold:
                    continue
                r = sm.ratio()
                if r >= threshold:
                    found.append((r, window[0][0], window[-1][0]))
        used: list[tuple[int, int]] = []
        for r, wa, wb in sorted(found, reverse=True):
            s = ctx.pt.word_spans[wa][0]
            e = ctx.pt.word_spans[wb][1]
            if e <= s or any(not (e <= us or s >= ue) for us, ue in used):
                continue
            used.append((s, e))
            conf = 0.98 if r >= 0.999 else round(r * 0.95, 3)
            ctx.add(s, e, entry.pii_type, "CLIENT_MASTER", conf, role=entry.role, check_allow=False)


# --------------------------------------------------------------------------- spaCy NER

_nlp = None
_nlp_failed = False


def _get_nlp(model: str):
    global _nlp, _nlp_failed
    if _nlp is None and not _nlp_failed:
        try:
            import spacy

            _nlp = spacy.load(model)
            for pipe in ("parser", "lemmatizer", "tagger", "attribute_ruler"):
                if pipe in _nlp.pipe_names:
                    _nlp.disable_pipe(pipe)
        except Exception:
            log.exception("spaCy model could not be loaded")
            _nlp_failed = True
    return _nlp


# The small English model is noisy on Indian notices, so its hits start below the
# pre-tick threshold: they are suggestions for the user, never redacted by default.
_SPACY_MAP = {"PERSON": ("NAME", 0.55), "ORG": ("ORG", 0.5), "GPE": ("ADDRESS", 0.4)}
_SALUTATION_WORDS = {"m/s", "ms", "mr", "mrs", "shri", "smt", "messrs", "sir", "madam"}


def _detect_spacy(ctx: _PageCtx, nlp) -> None:
    if not ctx.text.strip():
        return
    doc = nlp(ctx.text)
    for ent in doc.ents:
        mapped = _SPACY_MAP.get(ent.label_)
        if not mapped:
            continue
        txt = ent.text.strip()
        letters = re.sub(r"[^A-Za-z]", "", txt)
        if len(letters) < 3 or (txt.isupper() and len(letters) <= 4):
            continue
        if not txt[0].isupper() or "/" in txt:
            continue
        if any(w.strip(".,").lower() in _SALUTATION_WORDS for w in txt.split()):
            continue
        if ctx.allow.is_department(txt):
            continue
        ctx.add(ent.start_char, ent.end_char, mapped[0], f"SPACY_{ent.label_}", mapped[1])


# --------------------------------------------------------------------------- visual regions

def _px_rect_list(points) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def detect_codes(page: fitz.Page, page_index: int, dpi: int) -> list[Candidate]:
    """QR codes and barcodes on the rendered page."""
    import cv2

    out: list[Candidate] = []
    bgr = np.ascontiguousarray(render_page_array(page, dpi)[:, :, ::-1])
    try:
        ok, _decoded, points, _ = cv2.QRCodeDetector().detectAndDecodeMulti(bgr)
    except cv2.error:
        ok, points = False, None
    qr_rects = []
    if ok and points is not None:
        for pts in points:
            x0, y0, x1, y1 = _px_rect_list(pts)
            r = pixel_to_pdf(page, x0 - 6, y0 - 6, x1 + 6, y1 + 6, dpi)
            qr_rects.append(r)
            out.append(Candidate(page_index, [r], f"visual:QR:p{page_index + 1}:{len(qr_rects)}", "QR", 0.95, "QR_CODE"))
    detector = None
    try:
        if hasattr(cv2, "barcode") and hasattr(cv2.barcode, "BarcodeDetector"):
            detector = cv2.barcode.BarcodeDetector()
        elif hasattr(cv2, "barcode_BarcodeDetector"):
            detector = cv2.barcode_BarcodeDetector()
    except cv2.error:
        detector = None
    if detector is not None:
        try:
            res = detector.detect(bgr)
            ok, points = res[0], res[1]
        except cv2.error:
            ok, points = False, None
        if ok and points is not None:
            for k, pts in enumerate(points):
                x0, y0, x1, y1 = _px_rect_list(pts)
                r = pixel_to_pdf(page, x0 - 6, y0 - 6, x1 + 6, y1 + 6, dpi)
                if any(intersect_area(r, q) > 0.3 * rect_area(r) for q in qr_rects):
                    continue
                out.append(Candidate(page_index, [r], f"visual:BARCODE:p{page_index + 1}:{k + 1}", "BARCODE", 0.8, "BARCODE"))
    return out


def _detect_signatures_stamps(page: fitz.Page, ctx: _PageCtx, dpi: int) -> list[Candidate]:
    """Heuristic signature / stamp regions (low confidence; user confirms)."""
    import cv2

    idx = ctx.info.index
    out: list[Candidate] = []
    rgb = render_page_array(page, dpi)
    h, w = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    # Mask out known words so only non-text ink is counted.
    ink = (gray < 110).astype(np.uint8)
    for word in ctx.info.words:
        x0, y0, x1, y1 = (int(v) for v in pdf_to_pixel(page, word.rect, dpi))
        ink[max(y0, 0):max(y1, 0), max(x0, 0):max(x1, 0)] = 0

    n_sig = 0
    for li in range(len(ctx.pt.lines)):
        if not RE_SIG_LABEL.search(ctx.line_text(li)):
            continue
        lr = ctx.line_rect(li)
        if not lr:
            continue
        x0, y0, x1, y1 = pdf_to_pixel(page, lr, dpi)
        s = dpi / 72.0
        rx0, rx1 = int(max(x0 - 60 * s, 0)), int(min(x1 + 60 * s, w))
        ry0, ry1 = int(max(y0 - 90 * s, 0)), int(max(y0, 0))
        region = ink[ry0:ry1, rx0:rx1]
        if region.size == 0 or region.mean() < 0.004:
            continue
        ys, xs = np.nonzero(region)
        n_sig += 1
        r = pixel_to_pdf(page, rx0 + xs.min() - 4, ry0 + ys.min() - 4, rx0 + xs.max() + 4, ry0 + ys.max() + 4, dpi)
        out.append(Candidate(idx, [r], f"visual:SIGNATURE:p{idx + 1}:{n_sig}", "SIGNATURE", 0.5, "SIGNATURE_NEAR_LABEL"))

    # Small embedded images on text pages (often scanned signatures or seals).
    if ctx.info.kind == "TEXT":
        area = page.rect.width * page.rect.height
        for k, info in enumerate(page.get_image_info()):
            r = fitz.Rect(info["bbox"])
            if 0 < r.width * r.height < 0.2 * area:
                out.append(
                    Candidate(idx, [(r.x0, r.y0, r.x1, r.y1)], f"visual:SIGNATURE:p{idx + 1}:img{k + 1}",
                              "SIGNATURE", 0.45, "SMALL_EMBEDDED_IMAGE")
                )

    # Coloured stamps / seals (blue, red, purple ink).
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    coloured = (sat > 80) & (val > 50) & (
        ((hue >= 100) & (hue <= 160)) | (hue <= 10) | (hue >= 170)
    )
    mask = cv2.dilate(coloured.astype(np.uint8) * 255, np.ones((5, 5), np.uint8), iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = (0.5 * dpi) ** 2
    n_st = 0
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        box_area = cw * ch
        if box_area < min_area or box_area > 0.25 * w * h:
            continue
        if not (0.3 <= cw / max(ch, 1) <= 3.0):
            continue
        fill = coloured[y:y + ch, x:x + cw].mean()
        if not (0.05 <= fill <= 0.85):
            continue
        n_st += 1
        r = pixel_to_pdf(page, x - 4, y - 4, x + cw + 4, y + ch + 4, dpi)
        out.append(Candidate(idx, [r], f"visual:STAMP:p{idx + 1}:{n_st}", "STAMP", 0.5, "COLOURED_STAMP"))
    return out


# --------------------------------------------------------------------------- orchestration

@dataclass
class DetectionResult:
    """Candidates found plus any plain-English warnings for the user."""

    candidates: list[Candidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _overlap_ratio(a: Candidate, b: Candidate) -> float:
    ra, rb = union_rect(a.bboxes), union_rect(b.bboxes)
    inter = intersect_area(ra, rb)
    big = max(rect_area(ra), rect_area(rb))
    return inter / big if big else 0.0


def dedupe(cands: list[Candidate]) -> list[Candidate]:
    """Drop near-identical boxes found by more than one detector (keeps the most confident)."""
    kept: list[Candidate] = []
    for c in sorted(cands, key=lambda c: -c.confidence):
        if any(k.page == c.page and _overlap_ratio(k, c) >= 0.8 for k in kept):
            continue
        kept.append(c)
    return sorted(kept, key=lambda c: (c.page, union_rect(c.bboxes)[1], union_rect(c.bboxes)[0]))


def _propagate(ctxs: list[_PageCtx], cands: list[Candidate], threshold: float) -> list[Candidate]:
    """Find further occurrences of every confident text value anywhere in the document."""
    extra: list[Candidate] = []
    seen: set[str] = set()
    for c in cands:
        if c.pii_type in VISUAL_TYPES or c.confidence < threshold or c.rule_id.startswith("SPACY"):
            continue
        key = " ".join(c.text.lower().split())
        if len(key.replace(" ", "")) < 4 or key in seen:
            continue
        seen.add(key)
        body = r"\s*".join(re.escape(p) for p in c.text.split())
        pat = re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)
        for ctx in ctxs:
            before = len(ctx.out)
            for m in pat.finditer(ctx.text):
                ctx.add(m.start(), m.end(), c.pii_type, "SAME_VALUE", round(c.confidence * 0.95, 3), role=c.role)
            extra.extend(ctx.out[before:])
    return extra


def detect_text(
    pages: list[PageInfo],
    cfg: dict[str, Any],
    allow: Allowlist,
    master: list[MasterEntry],
    use_spacy: bool = True,
    progress: Progress | None = None,
) -> tuple[list[Candidate], list[_PageCtx], list[str]]:
    """Run all text-based detectors on the given pages."""
    warnings: list[str] = []
    nlp = _get_nlp(cfg["detection"]["spacy_model"]) if use_spacy else None
    if use_spacy and nlp is None:
        warnings.append("Name detection (spaCy) is unavailable, so only rule-based name detection was used.")
    state = {
        "assessee_assigned": False,
        "master_has_assessee": any(m.role == "assessee" for m in master),
    }
    ctxs: list[_PageCtx] = []
    n = max(len(pages), 1)
    for info in pages:
        if progress:
            progress(int(info.index * 80 / n), f"Detecting PII on page {info.index + 1} of {len(pages)}")
        ctx = _PageCtx(info, allow)
        _detect_ids(ctx)
        _detect_names_addresses(ctx, cfg, state)
        _detect_pin(ctx)
        _detect_master(ctx, master, float(cfg["detection"]["fuzzy_threshold"]))
        if nlp is not None:
            _detect_spacy(ctx, nlp)
        ctxs.append(ctx)
    cands = [c for ctx in ctxs for c in ctx.out]
    return cands, ctxs, warnings


def detect_all(
    doc: fitz.Document,
    pages: list[PageInfo],
    cfg: dict[str, Any],
    allow: Allowlist,
    master: list[MasterEntry],
    progress: Progress | None = None,
) -> DetectionResult:
    """Run every detector (text, client master, NER, visual) over the document."""
    det = cfg["detection"]
    cands, ctxs, warnings = detect_text(pages, cfg, allow, master, True, progress)
    if det.get("propagate_values", True):
        cands += _propagate(ctxs, cands, float(det["accept_threshold"]))
    dpi = int(det["visual_dpi"])
    for ctx in ctxs:
        if progress:
            progress(80 + int(ctx.info.index * 20 / max(len(ctxs), 1)), f"Looking for QR codes, signatures and stamps on page {ctx.info.index + 1}")
        page = doc[ctx.info.index]
        try:
            cands += detect_codes(page, ctx.info.index, dpi)
            cands += _detect_signatures_stamps(page, ctx, dpi)
        except Exception:
            log.exception("Visual detection failed on a page")
            warnings.append(f"QR/signature/stamp detection could not run on page {ctx.info.index + 1}.")
    cands = dedupe(cands)
    threshold = float(det["accept_threshold"])
    for c in cands:
        c.accepted = c.confidence >= threshold
    counts: dict[str, int] = {}
    for c in cands:
        counts[c.pii_type] = counts.get(c.pii_type, 0) + 1
    log.info("Detection finished: %d candidates %s", len(cands), counts)
    if progress:
        progress(100, "Detection finished")
    return DetectionResult(cands, warnings)

