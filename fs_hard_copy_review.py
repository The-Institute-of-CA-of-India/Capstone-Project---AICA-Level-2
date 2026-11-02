#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FS Hard Copy Review
-------------------
Desktop tool that runs the 19-point "FS Hard Copy Review" checklist on a draft
set of financial statements + auditor's report (PDF) and saves the Word
findings report to the user's Downloads folder.

Hybrid engine:
  * Python  - PDF extraction, page classification, every arithmetic check and
              all rule-based checks.
  * AI      - (optional, configurable: Claude / ChatGPT / Gemini /
              any OpenAI-compatible endpoint) judgment points, verification of
              rule candidates and the final 19-point findings, following the
              skill text embedded below verbatim.
Without an API key the tool runs rules-only and marks judgment points that
could not be checked as "Not verifiable".
"""

from __future__ import annotations

import base64
import ctypes
import datetime as _dt
import difflib
import hashlib
import hmac
import io
import json
import os
import re
import sys
import threading
import traceback
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

APP_NAME = "FS Hard Copy Review"
APP_VERSION = "1.7.0"

# --------------------------------------------------------------------------
# Skill text (verbatim copy of the fs-hard-copy-review SKILL.md)
# --------------------------------------------------------------------------
SKILL_TEXT = r"""---
name: "fs-hard-copy-review"
description: "Run the FS Hard Copy Review checklist (19 points) on a draft set of financial statements and auditor's report (PDF) and produce the Word findings report. Use when the user asks for a hard copy review, to run the hard copy checklist, or to review FS/AR before issue."
---

# FS Hard Copy Review

The user gives a draft FS + Auditor's Report (AR) as a PDF for the auditor's draft review. Run the 19 checklist points below on it and deliver one Word report in the template described under "Output".

If the FS PDF is not attached, ask for it. Do not ask for anything else. If the user also gives the PY FS (acknowledged copy), use it for points 2 and 3; otherwise those points are "Not verifiable" (or N/A for a first period).

## Ground rules
- Report only what is actually in the document. No assumptions, no invented facts.
- Every observation quotes the exact wording found, gives the page and states the correction.
- Page references: printed page numbers (p4, p5 …). AR pages are unnumbered, so refer to them as AR p1–p3 and add their PDF page numbers.
- All arithmetic is recomputed in Python, never mentally.
- Report an item only if it falls under "Report" for its point, or is a clear error of the same kind. Items listed under "Do not report" are firm-accepted practice. They must never appear in the output, not even as a note.
- **Draft AR:** this is the auditor's draft review, so the AR signature section is expected to be incomplete. Never flag a missing signature, missing auditor name/registration number, missing place, missing AR date or the absence of a signature block. Flag only what is printed and wrong (e.g. an AR date before the period end, wrong year, visible typos).
- **No duplicates:** each finding appears under exactly one point – the most relevant one (see "Where each finding goes"). Never repeat the same finding, or a cross-reference to it ("see point 1"), under another point. The "Critical points" section may summarise findings from the table.
- **Relevance:** report under each point only items that belong to that point's scope. Anything valid that does not fit a specific point goes under point 1 (Overall reading).

## Method
1. Extract text per page with `pdftotext -layout -f N -l N` and get page size and orientation with `pdfinfo -f 1 -l N`. If pages have no text layer (scanned PDF), OCR them with `tesseract` from 200 dpi renders, and confirm every spelling/typo finding against the page image, because OCR introduces its own errors.
2. Render every page with `pdftoppm -r 80 -png` and look at each image. Visual checks (coloured text, spacing, text cut off, printed page order, headers and footers) cannot be done from text alone. Detect coloured text programmatically (pixels with large RGB channel spread).
3. Run points 1–19.
4. Build the Word report, render it to PDF, check it visually, and send it with SendUserFile.

## Where each finding goes (precedence)
| Finding | Point |
|---|---|
| AR date before period end, wrong year/date in any heading or text, period wording mismatch, incorporation/tax-period date mismatch | 7 |
| Company name spelling/format variation, including in a page header | 6 |
| Missing/incorrect company header, wrong footer note range "(1-X)" | 4 |
| Printed page numbers out of order, Contents page numbers wrong | 5 |
| Physical order of statements vs Contents, note numbering gaps/repeats, face note refs not ascending | 11 |
| Figure mismatches between statements/notes, missing note references, wrong note cross-references | 10 |
| Casting / cross-casting differences | 9 |
| Currency name, currency symbol/code, currency missing from column headers | 8 |
| Caption capitalisation, AR spacing, coloured text, inconsistent heading/numbering style | 12 |
| "Company"/"Establishment" usage and its capitalisation | 16 |
| CFS captions increase/decrease, used in/generated from | 17 |
| Related-party balances in CFS sections | 19 |
| Other CFS non-cash / large flows queries | 13 |
| Text cut off / incomplete paragraph | 15 |
| Spelling and grammar not covered by a more specific point | 18 |
| Everything else (policies, "the Group", missing notes/policies, nil lines to delete, country-name wording, contradictory disclosures, duplicated paragraphs, accounting queries) | 1 |

## The 19 checklist points

The Checklist point text below is used verbatim in column 2 of the report.

### 1. Overall reading of hard copy AR & FS
Read the AR and all notes in full. Also the home for valid findings that fit no other point.
- **Report:**
  - "the Group" in a single-company FS.
  - Accounting policies not tailored to the business (e.g. a sale-of-goods revenue policy for an IT consultancy / investment company) or inconsistent with other notes.
  - No accounting policy / note and no note reference for equity components such as Contribution from shareholder, Share premium or Statutory reserve.
  - No related party note where there are shareholder contributions, investments in other entities or related-party balances.
  - Duplicated paragraphs, incomplete lists (e.g. "the following IFRSs have been adopted" with no list), self-contradictory disclosures.
  - Note lines with nil / "-" values in all columns (e.g. investees showing nil, nil QFZP line) → to be deleted.
  - Inconsistent country wording ("UAE" vs "U.A.E" vs "U.A.E.") → harmonise.
  - Accounting/presentation queries for the reviewer (mark as "Query –").
- **Do not report:**
  - Anything about the AR signature section (see Draft AR rule).
  - AR pages without page numbers or header (firm practice).
  - Standard boilerplate risk paragraphs (e.g. a credit risk paragraph mentioning customers/receivables when there are none).
  - A balance sheet with no liabilities or no accruals.

### 2. Comparison of PY figures with Acknowledged hard copy in file
- First financial statements → N/A (confirm against the comparatives note).
- PY FS provided → compare every PY figure in the current FS (SOFP, P&L, SOCE, CFS, every note) with the CY column of the PY FS; report differences not explained by a reclassification note.
- Otherwise → Not verifiable.

### 3. Comparison of PY notes with Acknowledged hard copy in file
Same rule as point 2, applied to note wording and disclosures (e.g. note dropped, policy changed without reason, PY narrative figures differing).

### 4. Header & footer accuracy checking
- **Report:**
  - Missing or incorrect company header on statement and notes pages (other than a name spelling issue, which goes to point 6).
  - Primary statement footer "Attached notes (1-X) form an integral part…" where X does not match the last note number.
- **Do not report:** absence of header or footer on AR pages (firm practice).

### 5. Page numbers accuracy checking
- **Report:**
  - Printed page numbers out of sequence in the physical order (e.g. 4, 5, 7, 6).
  - Contents page numbers not agreeing to the pages.
- **Do not report:** unnumbered AR pages (firm practice), even though Contents shows "Auditor's Report 1 - 3".

### 6. Company name checking
Count every occurrence of the name (cover, contents, AR, headers, notes). Report only a variation in spelling or format.
- **Do not report:**
  - The "M/s." prefix.
  - That the trade licence was not provided.

### 7. Year / Date checking
- **Report:**
  - AR date earlier than the period end (only if a date is printed).
  - Wrong year in any heading (e.g. notes header "March 31, 2026" for a 2025 FS).
  - Period wording differing between the AR, P&L, SOCE, CFS and notes ("period" vs "year").
  - Incorporation date disagreeing between Note 1, the tax note and the comparatives note.
  - Date format errors (e.g. "December 31 2025").

### 8. Check accuracy of currency written throughout the report
Strictly currency only: currency name, currency symbol/code and currency in column headers.
- **Report:**
  - Currency missing from a column header.
  - Inconsistent currency name or code ("UAE Dirham" vs "U.A.E. Dirhams" vs "AED" vs "Dirham") → harmonise.
  - Amounts in a currency inconsistent with the presentation currency, or decimals where the FS use whole units.
- **Do not report here:** country-name wording or nil lines (→ point 1).

### 9. Totaling verification
Recompute every subtotal and total: SOFP, P&L, SOCE (cast and cross-cast), CFS and every note table, both years. Report only differences.

### 10. Checking of accuracy of link of various figures
Check that:
- each face-of-statement figure agrees to its note;
- net profit/loss agrees across P&L, SOCE, CFS and the SOFP reserves line;
- equity components agree across SOCE, SOFP and CFS;
- closing cash agrees across CFS, SOFP and the financial-assets note;
- tax charge, provision and effective tax rate agree between P&L, SOFP and the tax note;
- cross-references between notes are correct.

- **Report:** any mismatch, wrong note cross-references, and SOFP lines that have a note but carry no note reference (e.g. Cash and cash equivalents, Contribution from shareholder, Share premium).

### 11. Sequence accuracy (note no. / pages etc)
- **Report:**
  - Physical order of statements not matching Contents (e.g. CFS printed before SOCE → swap).
  - Gaps or repeats in note or sub-note numbering.
  - Face-of-statement note references not in ascending order.

### 12. Format of various pages (BS/PL/CFS/SOCE and notes)
- **Report:**
  - Inconsistent capitalisation of the same caption (e.g. SOCE "Share Capital" vs SOFP "Share capital").
  - Uneven blank spacing between paragraphs (e.g. in the AR).
  - Any coloured (non-black) text, such as a red AR date.
  - Inconsistent numbering style (e.g. "2.1" vs "2.2.").
- **Do not report:**
  - Landscape SOCE.
  - Bold level-2 sub-headings with non-bold level-3 sub-headings.
  - A fully justified heading with wide word spacing.

### 13. Cash flow statement verification with non cash items accuracy
Check that non-cash items (depreciation, provisions, end-of-service benefits, impairment, write-offs) are added back.
- **Report as Query:** large investing or financing flows that may be non-cash (share swap, in-kind contribution, investment acquired against share premium or related-party balances, dividend settled through related parties). These are to be verified with bank statements before signing.
- Related-party balance classification goes to point 19, not here.

### 14. Financial assets and Financial liability figure correctness
Report only where the financial instruments note disagrees with the SOFP.
- **Do not report:** investments in shares carried at cost being excluded from the financial-assets list. This is correct.

### 15. To check any paragrapgh is cut in print out and to get it corrected
This is about missing text, not page breaks. From the rendered images and text, report:
- a paragraph or sentence that ends abruptly or is incomplete;
- text, rows or columns not printed (e.g. cut off by an Excel row height/column width or print area), table rows truncated, content running off the page.
- **Do not report:** a paragraph, note or table that simply continues on the next page.

### 16. To check for Whether "Establishment" or Company has been consistently used through it.
- **Report:**
  - Use of the other term.
  - Inconsistent capitalisation (e.g. "The company manages" where "Company" is used elsewhere).

### 17. Increase/ Decrease & used in / generated from in cash flow
- **Report:**
  - A combined caption such as "Net (decrease)/increase" when the movement has the same known sign in every column shown → use "Net increase" or "Net decrease".
  - "used in" / "generated from" not matching the sign of the section total.
- **Do not report:** combined captions where CY and PY have opposite signs; "Cash and cash equivalents in the beginning" (accepted wording).

### 18. Spelling check
List every spelling or grammar error with its location → correction. Firm conventions:
- **-ise / -ize spellings are both acceptable** (recognised/recognized, realised/realized, summarised/summarized, amortised/amortized, derecognises/derecognizes, maximise/maximize, organisation/organization). Never report them, including mixed usage.
- **Statement titles in the AR** must match the statement page titles **exactly**. Example: AR "statement of cash flows" vs page title "Statement of Cash Flow" → change the AR wording to match the page title.
- **Framework name** must be identical in the AR and the basis-of-preparation note.
- **Typical errors to catch:**
  - "International Standard on Auditing (ISAs)" → "Standards"
  - missing spaces, e.g. "Accountants(IESBA"
  - "comprise of" → "comprise the statement of financial position"
  - "related disclosure" → "disclosures"
  - "investments activities" → "investment activities"
  - "A summary … are" → "is"
  - "certain financial instrument" → "instruments"
  - "Income or loss … are recognised" → "is"
  - "Revision to accounting estimates are" → "Revisions … are"
  - "its characteristics" → "their"
  - "funding … are arranged" → "is arranged"
  - "or/and" → "and/or"
  - "SHAREHOLDER'S" where there are several shareholders → "SHAREHOLDERS'"

### 19. Update balances in "due to" and "due from" related party under investing/ financing activity (if the balance is related to non Operation item)
- If the SOFP/CFS has such balances, check they are presented under investing or financing.
- If there are none → N/A.

## Output – Word report (template)

Read the docx skill's SKILL.md first and build the report with docx-js. No firm branding. Layout, top to bottom:

1. **Page:** A4 landscape, 0.5" margins, Arial, centred footer "Page X of Y".
2. **Title:** "Hard Copy Review – Findings Report" (bold, 15pt).
3. **Metadata lines (bold label: value):**
   - Client
   - Period
   - Document reviewed (file name and page count; add the PY FS file name when used)
   - Checklist applied ("Hard copy review check list – points 1 to 19")
   - Date of review
4. **Italic line:** the page-reference convention.
5. **"Critical points to correct before issue":** heading and all its bullets in red font (C00000). 3–6 bullets with the most serious Exceptions and Queries.
6. **"Checklist findings" table:**
   - Columns: SN (600) | Checklist point (3000) | Status (1500) | Findings (9300), DXA widths.
   - Header row: dark blue (1F3864) with white bold text.
   - Status cell shaded by status (see table below).
   - All 19 rows, using the checklist point text verbatim.
7. **Italic status key line below the table:** "Status key: Exception = error found, to correct; Query = reviewer to confirm; OK = no issue found; N/A = not applicable; Not verifiable = item not in file provided."

| Status | Use when | Shading |
|---|---|---|
| Exception | At least one item to be corrected | F8D7DA |
| Query | Only items for the reviewer to confirm | FFF3CD |
| OK | Nothing to report | D4EDDA |
| N/A | Point does not apply | E2E3E5 |
| Not verifiable | Material not in the file | E2E3E5 |

### Findings column rules
- **OK:** the cell contains only "No observations." Do not list the checks that passed.
- **Exception / Query:** one bullet per issue only. Each bullet quotes what was found, gives the page and states the correction. Do not include passed checks alongside. Prefix reviewer-confirmation items inside an Exception row with "Query –".
- **N/A / Not verifiable:** one short line giving the reason.
- If every candidate item on a point falls under "Do not report" or belongs to another point, the status is OK with "No observations."

File name: `Hard_Copy_Review_Findings_<Client>_<Year>.docx`. In chat, give only the critical points, briefly.

## Calibration example (from a reviewed run)

On a first-period FS (Trans Global Technologies L.L.C-FZ, period ended March 31, 2025) the reviewer classified the candidate items as follows. The expected output follows from it.

- **Point 1, Exception:**
  - "the Group"
  - goods-based revenue policy
  - no policy/note for contribution and share premium
  - no related party note
  - UAE / U.A.E wording
  - nil investee lines to delete
- **Point 6:** OK, "No observations." The M/s. prefix and the licence item were dropped.
- **Point 7, Exception:** AR dated Jan 29, 2025 (before period end); notes header 2026.
- **Point 10, Exception:** missing note references only.
- **Point 11, Exception:** SOCE printed after CFS; page order 7 before 6.
- **Point 12, Exception:**
  - "Share Capital" case
  - AR spacing
  - red AR date
- **Point 14:** OK, "No observations."
- **Point 17, Exception:** "(decrease)/increase" caption only (single period, known sign).
- **Point 18:** every grammar and spelling item was confirmed as an Exception (excluding -ise/-ize variants).
- **Points 2–3:** N/A (first period).
- **Point 19:** N/A.

On a later draft (Fwakeh Al Rabee Trading L.L.C., year ended December 31, 2025) the reviewer instructed: do not flag the missing AR signature/date (draft review); report the p13 header name "L.L.C" only under point 6, not also point 4; keep point 8 to currency wording only; do not report notes continuing on the next page under point 15; do not report recognized/realizable/amortized spellings."""

# Checklist point text used verbatim in column 2 of the report
CHECKLIST_POINTS = OrderedDict([
    (1, "Overall reading of hard copy AR & FS"),
    (2, "Comparison of PY figures with Acknowledged hard copy in file"),
    (3, "Comparison of PY notes with Acknowledged hard copy in file"),
    (4, "Header & footer accuracy checking"),
    (5, "Page numbers accuracy checking"),
    (6, "Company name checking"),
    (7, "Year / Date checking"),
    (8, "Check accuracy of currency written throughout the report"),
    (9, "Totaling verification"),
    (10, "Checking of accuracy of link of various figures"),
    (11, "Sequence accuracy (note no. / pages etc)"),
    (12, "Format of various pages (BS/PL/CFS/SOCE and notes)"),
    (13, "Cash flow statement verification with non cash items accuracy"),
    (14, "Financial assets and Financial liability figure correctness"),
    (15, "To check any paragrapgh is cut in print out and to get it corrected"),
    (16, 'To check for Whether "Establishment" or Company has been consistently used through it.'),
    (17, "Increase/ Decrease & used in / generated from in cash flow"),
    (18, "Spelling check"),
    (19, 'Update balances in "due to" and "due from" related party under investing/ financing activity (if the balance is related to non Operation item)'),
])

STATUSES = ["Exception", "Query", "OK", "N/A", "Not verifiable"]
STATUS_SHADING = {
    "Exception": "F8D7DA",
    "Query": "FFF3CD",
    "OK": "D4EDDA",
    "N/A": "E2E3E5",
    "Not verifiable": "E2E3E5",
}
STATUS_KEY_LINE = ("Status key: Exception = error found, to correct; Query = reviewer to confirm; "
                   "OK = no issue found; N/A = not applicable; Not verifiable = item not in file provided.")
NO_OBS = "No observations."
NO_AI_LINE = "Not verifiable – requires the AI review (no AI provider configured in Settings)."

# Points that the rule engine covers fully (OK when no rule finding)
RULE_COVERED_POINTS = {4, 5, 6, 7, 8, 9, 10, 11, 12, 16, 17}

# --------------------------------------------------------------------------
# Paths / settings
# --------------------------------------------------------------------------

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"


def app_data_dir() -> Path:
    if IS_MAC:
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def downloads_dir() -> Path:
    """User's Downloads folder (Windows known folder, else ~/Downloads)."""
    if sys.platform.startswith("win"):
        try:
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]

            g = GUID()
            # FOLDERID_Downloads {374DE290-123F-4565-9164-39C4925E467B}
            g.Data1, g.Data2, g.Data3 = 0x374DE290, 0x123F, 0x4565
            for i, b in enumerate([0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B]):
                g.Data4[i] = b
            ptr = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(ptr)) == 0:
                path = ptr.value
                ctypes.windll.ole32.CoTaskMemFree(ptr)
                if path:
                    return Path(path)
        except Exception:
            pass
    p = Path.home() / "Downloads"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---- secret storage (Windows DPAPI, bound to the Windows user account) ----
_ENTROPY = b"FSHardCopyReview::v1::api-keys"


def _dpapi(data: bytes, encrypt: bool) -> bytes:
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    keep = []  # keep the buffers alive for the duration of the call

    def mk(b: bytes) -> BLOB:
        buf = ctypes.create_string_buffer(b, len(b))
        keep.append(buf)
        return BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    inp, ent, out = mk(data), mk(_ENTROPY), BLOB()
    ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    fn = ctypes.windll.crypt32.CryptProtectData if encrypt else ctypes.windll.crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(inp), None, ctypes.byref(ent), None, None, 0x1, ctypes.byref(out))
    if not ok:
        raise OSError("Windows DPAPI call failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


_KEYCHAIN_SERVICE = "FS Hard Copy Review"


def protect_secret(secret: str, account: str = "default") -> str:
    raw = secret.encode("utf-8")
    if sys.platform.startswith("win"):
        return "dpapi:" + base64.b64encode(_dpapi(raw, True)).decode()
    if IS_MAC:
        # macOS: the key itself goes into the user's login Keychain; settings.json keeps only a pointer
        try:
            import keyring
            keyring.set_password(_KEYCHAIN_SERVICE, account, secret)
            return "keychain:" + account
        except Exception:
            pass
    # Non-Windows fallback (development only): machine-bound obfuscation
    key = (os.environ.get("USER", "") + str(Path.home())).encode() or b"k"
    x = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
    return "xor:" + base64.b64encode(x).decode()


def unprotect_secret(token: str) -> str:
    if not token:
        return ""
    if token.startswith("dpapi:"):
        return _dpapi(base64.b64decode(token[6:]), False).decode("utf-8")
    if token.startswith("keychain:"):
        try:
            import keyring
            return keyring.get_password(_KEYCHAIN_SERVICE, token[9:]) or ""
        except Exception:
            return ""
    if token.startswith("xor:"):
        key = (os.environ.get("USER", "") + str(Path.home())).encode() or b"k"
        x = base64.b64decode(token[4:])
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(x)).decode("utf-8")
    return ""


PROVIDERS = OrderedDict([
    ("claude", {
        "label": "Claude (Anthropic)",
        "models": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"],
        "base_url": "https://api.anthropic.com/v1",
        "base_url_editable": False,
    }),
    ("openai", {
        "label": "ChatGPT (OpenAI)",
        "models": ["gpt-6.1-sol", "gpt-6-sol", "gpt-5.6-sol"],
        "base_url": "https://api.openai.com/v1",
        "base_url_editable": False,
    }),
    ("gemini", {
        "label": "Gemini (Google)",
        "models": ["gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-2.5-pro"],
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "base_url_editable": False,
    }),
    ("custom", {
        "label": "Custom (OpenAI-compatible)",
        "models": [],
        "base_url": "",
        "base_url_editable": True,
    }),
])


class Settings:
    """Settings persisted in %APPDATA%/FS Hard Copy Review/settings.json.
    API keys are stored only in encrypted form and are never returned to the UI."""

    def __init__(self):
        self.path = app_data_dir() / "settings.json"
        self.data: dict = {"active": "", "providers": {}}
        try:
            if self.path.exists():
                self.data.update(json.loads(self.path.read_text("utf-8")))
        except Exception:
            pass
        for gone in [k for k in self.data["providers"] if k not in PROVIDERS]:
            self.data["providers"].pop(gone, None)     # providers removed from the tool (e.g. Kimi) – drop stale keys
        for pid, meta in PROVIDERS.items():
            p = self.data["providers"].setdefault(pid, {})
            p.setdefault("model", meta["models"][0] if meta["models"] else "")
            p.setdefault("base_url", meta["base_url"])
            p.setdefault("max_tokens", 32000)
            p.setdefault("parallel", 3)
            p.setdefault("reasoning", "low" if pid == "kimi" else "default")
            p.setdefault("key", "")

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), "utf-8")
        tmp.replace(self.path)

    def provider(self, pid: str) -> dict:
        return self.data["providers"][pid]

    # ---- settings password (only a salted PBKDF2 hash is stored)
    def has_lock(self) -> bool:
        lk = self.data.get("lock")
        return isinstance(lk, dict) and bool(lk.get("hash"))

    def set_lock(self, password: str):
        salt = os.urandom(16)
        it = 200_000
        h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, it)
        self.data["lock"] = {"salt": salt.hex(), "hash": h.hex(), "iter": it}

    def clear_lock(self):
        self.data.pop("lock", None)

    def check_lock(self, password: str) -> bool:
        lk = self.data.get("lock") or {}
        try:
            h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(lk["salt"]), int(lk.get("iter", 200_000)))
            return hmac.compare_digest(h.hex(), lk["hash"])
        except Exception:
            return False

    def has_key(self, pid: str) -> bool:
        return bool(self.data["providers"].get(pid, {}).get("key"))

    def set_key(self, pid: str, key: str):
        old = self.data["providers"][pid].get("key", "")
        if not key.strip() and IS_MAC and old.startswith("keychain:"):
            try:
                import keyring
                keyring.delete_password(_KEYCHAIN_SERVICE, old[9:])
            except Exception:
                pass
        self.data["providers"][pid]["key"] = protect_secret(key.strip(), pid) if key.strip() else ""

    def get_key(self, pid: str) -> str:  # internal use only (API calls)
        try:
            return unprotect_secret(self.data["providers"][pid].get("key", ""))
        except Exception:
            return ""

    @property
    def active(self) -> str:
        a = self.data.get("active", "")
        return a if a in PROVIDERS and self.has_key(a) else ""

    def ai_config(self) -> Optional[dict]:
        pid = self.active
        if not pid:
            return None
        p = self.provider(pid)
        return {"provider": pid, "model": p["model"], "base_url": p["base_url"],
                "max_tokens": int(p.get("max_tokens") or 32000), "parallel": int(p.get("parallel") or 3),
                "mode": self.data.get("mode", "fast"), "reasoning": p.get("reasoning", "default"),
                "key": self.get_key(pid)}


# --------------------------------------------------------------------------
# PDF extraction
# --------------------------------------------------------------------------
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]
MON_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
DATE_RE = re.compile(
    r"\b(?:(?P<m1>" + MON_RE + r")\s+(?P<d1>\d{1,2})(?:st|nd|rd|th)?(?P<c1>,?)\s+(?P<y1>(?:19|20)\d{2})"
    r"|(?P<d2>\d{1,2})(?:st|nd|rd|th)?\s+(?P<m2>" + MON_RE + r")(?P<c2>,?)\s+(?P<y2>(?:19|20)\d{2}))\b",
    re.I)

NUM_TOKEN = re.compile(r"^\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?$|^\(?-?\d+(?:\.\d+)?\)?$")
DASH_TOKENS = {"-", "–", "—", "--", "−", "‒", "nil", "Nil", "NIL"}
YEAR_TOKEN = re.compile(r"^(?:19|20)\d{2}$")
CURRENCY_CODE = re.compile(r"^(?:AED|Dirhams?|Dhs|USD|EUR|GBP|SAR|QAR|OMR|KWD|BHD|INR|SGD|MYR|Dhs?\.?|US\$|\$)$", re.I)

KIND_LABELS = {
    "cover": "Cover", "contents": "Contents", "ar": "Auditor's Report",
    "sofp": "Statement of financial position", "pl": "Statement of profit or loss",
    "soce": "Statement of changes in equity", "cfs": "Statement of cash flows",
    "notes": "Notes", "other": "Other",
}
STATEMENT_KINDS = ["sofp", "pl", "soce", "cfs"]


def parse_date(m: re.Match) -> Optional[_dt.date]:
    try:
        mon = (m.group("m1") or m.group("m2")).lower().rstrip(".")
        day = int(m.group("d1") or m.group("d2"))
        yr = int(m.group("y1") or m.group("y2"))
        mi = next(i for i, mm in enumerate(MONTHS) if mm.startswith(mon[:3])) + 1
        return _dt.date(yr, mi, day)
    except Exception:
        return None


def fmt_date(d: _dt.date) -> str:
    return f"{MONTHS[d.month - 1].capitalize()} {d.day}, {d.year}"


def parse_amount(tok: str) -> Optional[float]:
    t = tok.strip()
    if t in DASH_TOKENS:
        return 0.0
    if not NUM_TOKEN.match(t):
        return None
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if t.startswith("-"):
        neg, t = True, t[1:]
    try:
        v = float(t.replace(",", ""))
    except ValueError:
        return None
    return -v if neg else v


def fmt_amt(v: Optional[float]) -> str:
    if v is None:
        return "-"
    if abs(v - round(v)) < 1e-9:
        s = f"{abs(int(round(v))):,}"
    else:
        s = f"{abs(v):,.2f}"
    return f"({s})" if v < 0 else s


@dataclass
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    bold: bool
    color: tuple
    size: float


@dataclass
class Line:
    words: list
    top: float
    bottom: float

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def x0(self) -> float:
        return self.words[0].x0

    @property
    def bold(self) -> bool:
        return all(w.bold for w in self.words)

    def phrases(self, gap: float = 12.0) -> list:
        """Split line into phrases separated by a horizontal gap."""
        out, cur = [], [self.words[0]]
        for w in self.words[1:]:
            if w.x0 - cur[-1].x1 > gap:
                out.append(cur)
                cur = [w]
            else:
                cur.append(w)
        out.append(cur)
        return out


@dataclass
class Row:
    page: int               # PDF page number (1-based)
    top: float
    bottom: float
    label: str
    note_ref: Optional[str]
    values: list            # per column: float, 0.0 for dash, None if blank
    raw: list               # per column raw token
    line_above: list        # per column bool
    bold: bool
    table_id: int
    is_heading: bool = False


@dataclass
class Page:
    n: int                  # PDF page number, 1-based
    width: float
    height: float
    lines: list
    layout_text: str
    kind: str = "other"
    printed: Optional[str] = None
    title: str = ""
    ar_index: Optional[int] = None
    hlines: list = field(default_factory=list)   # (x0, x1, top)
    rows: list = field(default_factory=list)
    headers: list = field(default_factory=list)  # dicts per table header
    ocr: bool = False                            # text obtained by OCR (scanned page)

    @property
    def orientation(self) -> str:
        return "landscape" if self.width > self.height else "portrait"

    @property
    def text(self) -> str:
        return "\n".join(l.text for l in self.lines)

    def top_lines(self, frac: float = 0.22) -> list:
        return [l for l in self.lines if l.top < self.height * frac]

    @property
    def ref(self) -> str:
        if self.kind == "ar" and self.ar_index:
            return f"AR p{self.ar_index} (PDF p{self.n})"
        if self.printed:
            return f"p{self.printed}"
        if self.kind == "cover":
            return f"Cover (PDF p{self.n})"
        if self.kind == "contents":
            return f"Contents (PDF p{self.n})"
        return f"PDF p{self.n}"


def _rgb(color) -> tuple:
    try:
        if color is None:
            return (0.0, 0.0, 0.0)
        if isinstance(color, (int, float)):
            return (float(color),) * 3
        c = [float(x) for x in color if isinstance(x, (int, float))]
        if len(c) == 1:
            return (c[0],) * 3
        if len(c) == 3:
            return tuple(c)
        if len(c) == 4:
            C, M, Y, K = c
            return ((1 - C) * (1 - K), (1 - M) * (1 - K), (1 - Y) * (1 - K))
    except Exception:
        pass
    return (0.0, 0.0, 0.0)


def _edge_visible(e: dict) -> bool:
    def white(c):
        return min(_rgb(c)) >= 0.93
    stroke, fill = e.get("stroke"), e.get("fill")
    if stroke is None and fill is None:
        return True
    vis = False
    if stroke and not white(e.get("stroking_color")) and float(e.get("linewidth") or 0) > 0:
        vis = True
    if fill and not white(e.get("non_stroking_color")):
        vis = True
    return vis


def is_coloured(color) -> bool:
    r, g, b = _rgb(color)
    return max(r, g, b) - min(r, g, b) > 0.25


class ScannedPdfError(Exception):
    pass


@dataclass
class Document:
    path: str
    pages: list
    name: str = ""
    ocr_pages: list = field(default_factory=list)   # PDF page numbers read by OCR (scanned pages)

    @property
    def scanned(self) -> bool:
        return bool(self.ocr_pages)

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    def by_kind(self, kind: str) -> list:
        return [p for p in self.pages if p.kind == kind]

    def first(self, kind: str) -> Optional[Page]:
        k = self.by_kind(kind)
        return k[0] if k else None

    def page(self, n: int) -> Optional[Page]:
        return self.pages[n - 1] if 1 <= n <= len(self.pages) else None


def _group_lines(ws: list, ocr: bool = False) -> list:
    lines: list = []
    for w in sorted(ws, key=lambda w: (w.top, w.x0)):
        for ln in lines[-3:]:
            tol = max(2.5, 0.45 * (w.bottom - w.top)) if ocr else 2.5
            if abs(ln.top - w.top) <= tol:
                ln.words.append(w)
                ln.bottom = max(ln.bottom, w.bottom)
                break
        else:
            lines.append(Line([w], w.top, w.bottom))
    for ln in lines:
        ln.words.sort(key=lambda w: w.x0)
    lines.sort(key=lambda l: l.top)
    return lines


_FRAG = re.compile(r"^[(\-]?[\d,.]*\d[\d,.]*\)?$|^[(\-]?,[\d,]+\)?$")


def _merge_number_fragments(lines: list) -> list:
    """Re-join amounts split by an imprecise text layer (e.g. OCR'd PDFs: '13' + '8,210' -> '138,210')."""
    for ln in lines:
        out = []
        for w in ln.words:
            if out:
                a = out[-1]
                gap = w.x0 - a.x1
                joined = a.text + w.text
                if (0 <= gap or gap > -2) and gap < 0.45 * max(a.size or 0, w.size or 0, 8) \
                        and _FRAG.match(a.text) and _FRAG.match(w.text) and not a.text.endswith(")") \
                        and NUM_TOKEN.match(joined.replace("..", ".")) and "," in joined:
                    out[-1] = Word(joined, a.x0, w.x1, min(a.top, w.top), max(a.bottom, w.bottom),
                                   a.bold, a.color, max(a.size or 0, w.size or 0))
                    continue
            out.append(w)
        ln.words = out
    return lines


def _layout_from_lines(lines: list, char_w: float = 4.4) -> str:
    """Rebuild a column-aligned page text from positioned words (used for OCR pages)."""
    out = []
    prev_bottom = None
    for ln in lines:
        if prev_bottom is not None and ln.top - prev_bottom > 1.2 * (ln.bottom - ln.top):
            out.append("")
        row = ""
        for w in ln.words:
            col = int(w.x0 / char_w)
            if len(row) < col:
                row += " " * (col - len(row))
            elif row:
                row += " "
            row += w.text
        out.append(row.rstrip())
        prev_bottom = ln.bottom
    return "\n".join(out).strip("\n")


_OCR_ENGINE = None
_OCR_LOCK = threading.Lock()


def _ocr_engine():
    global _OCR_ENGINE
    with _OCR_LOCK:
        if _OCR_ENGINE is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except Exception as e:
                raise ScannedPdfError(
                    "This PDF is scanned and the OCR component is not installed "
                    f"({type(e).__name__}). Run run_tool.bat again so it installs the missing package "
                    "(needs Python 3.12 or older).")
            _OCR_ENGINE = RapidOCR()
        return _OCR_ENGINE


OCR_DPI = 200


def _respace(t: str) -> str:
    """The OCR model often drops spaces between English words ('Cashandbankbalances').
    Restore them with a dictionary word splitter and a few number/letter boundary rules."""
    t = re.sub(r"^(\d{1,2}\.)(?=[A-Za-z])", r"\1 ", t)                 # '5.Cash' -> '5. Cash'
    t = re.sub(r"(?<=[A-Za-z]{3})(?=\d)", " ", t)                       # 'December31' -> 'December 31'
    t = re.sub(r"(?<=\d)(?=[A-Za-z]{3})", " ", t)                       # '31December' -> '31 December'
    t = re.sub(r"\b(\d{1,2}),((?:19|20)\d{2})\b", r"\1, \2", t)          # '31,2025' -> '31, 2025'
    try:
        import wordninja
    except Exception:
        return t

    def fix(m):
        parts = wordninja.split(m.group(0)) or [m.group(0)]
        out = []
        for w in parts:
            if out and len(w) == 1 and w.islower():
                out[-1] += w                 # 'receivable s' -> 'receivables'
            else:
                out.append(w)
        return " ".join(out)
    return re.sub(r"[A-Za-z]{7,}", fix, t)


def ocr_page_words(path: str, index: int, dpi: int = OCR_DPI) -> list:
    """OCR one PDF page -> Word objects in PDF point coordinates (same space as pdfplumber)."""
    import numpy as np
    import pypdfium2 as pdfium
    eng = _ocr_engine()
    pdf = pdfium.PdfDocument(path)
    try:
        page = pdf[index]
        scale = dpi / 72.0
        img = page.render(scale=scale).to_pil().convert("RGB")
        page.close()
    finally:
        pdf.close()
    result, _ = eng(np.array(img)[:, :, ::-1].copy())
    words = []
    for item in result or []:
        try:
            box, text, score = item[0], str(item[1]), float(item[2])
        except Exception:
            continue
        text = text.strip()
        if not text or score < 0.3:
            continue
        raw_len = max(1, len(text))
        text = _respace(text)
        xs = [float(pt[0]) for pt in box]
        ys = [float(pt[1]) for pt in box]
        x0, x1, top, bottom = min(xs) / scale, max(xs) / scale, min(ys) / scale, max(ys) / scale
        n = max(raw_len, len(text))
        pos = 0
        for t in text.split():
            st = text.find(t, pos)
            en = st + len(t)
            pos = en
            words.append(Word(t, x0 + (x1 - x0) * st / n, x0 + (x1 - x0) * en / n, top, bottom,
                              False, None, bottom - top))
    return words


def extract_document(path: str, log: Callable = print, allow_ocr: bool = False,
                     progress: Optional[Callable] = None) -> Document:
    import pdfplumber
    pages = []
    ocr_pages = []
    with pdfplumber.open(path) as pdf:
        total_chars = 0
        npg = len(pdf.pages)
        for i, pg in enumerate(pdf.pages, start=1):
            # Excel/Word exports often pad numbers with space glyphs that sit on top of the first digit;
            # they split '87,378' into '8' + '7,378'. Word gaps are measured from positions, so drop them.
            try:
                pg = pg.filter(lambda o: not (o.get("object_type") == "char" and not str(o.get("text", "")).strip()))
            except Exception:
                pass
            # Words are split on position only (not on font/colour changes, which broke 'L.L.C.' into 'L.L.C' + '.');
            # the word's attributes are then taken from its characters.
            words = pg.extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False,
                                     use_text_flow=False, return_chars=True)
            for w in words:
                chs = [c for c in w.get("chars", []) if str(c.get("text", "")).strip()] or w.get("chars", [])
                if chs:
                    fonts = [str(c.get("fontname", "")) for c in chs]
                    w["fontname"] = max(set(fonts), key=fonts.count)
                    w["size"] = max(float(c.get("size") or 0) for c in chs)
                    col = next((c.get("non_stroking_color") for c in chs if is_coloured(c.get("non_stroking_color"))), None)
                    w["non_stroking_color"] = col if col is not None else chs[0].get("non_stroking_color")
            nchars = sum(len(w["text"]) for w in words)
            total_chars += nchars
            hl = []
            try:
                for e in pg.horizontal_edges:
                    if not _edge_visible(e):
                        continue          # white / invisible shapes (Word text boxes, cell fills)
                    if float(e["x1"]) - float(e["x0"]) >= 15:
                        hl.append((float(e["x0"]), float(e["x1"]), float(e["top"])))
            except Exception:
                pass
            if allow_ocr and nchars < 25:
                if progress:
                    progress(f"Reading scanned page {i} of {npg} (OCR) …")
                ws = ocr_page_words(path, i - 1)
                lines = _group_lines(ws, ocr=True)
                layout = _layout_from_lines(lines)
                ocr_pages.append(i)
                pages.append(Page(i, float(pg.width), float(pg.height), lines, layout, hlines=[], ocr=True))
                continue
            ws = [Word(w["text"], float(w["x0"]), float(w["x1"]), float(w["top"]), float(w["bottom"]),
                       "bold" in str(w.get("fontname", "")).lower() or "black" in str(w.get("fontname", "")).lower(),
                       w.get("non_stroking_color"), float(w.get("size") or 0)) for w in words]
            lines = _merge_number_fragments(_group_lines(ws))
            # a page that is one full-size picture with a text layer = a scan OCR'd by another program
            try:
                area = float(pg.width) * float(pg.height)
                scan_layer = any(float(im.get("width", 0)) * float(im.get("height", 0)) >= 0.8 * area for im in pg.images)
            except Exception:
                scan_layer = False
            try:
                layout = pg.extract_text(layout=True, x_tolerance=1.5) or ""
            except Exception:
                layout = "\n".join(l.text for l in lines)
            layout = "\n".join(s.rstrip() for s in layout.splitlines())
            layout = re.sub(r"\n{3,}", "\n\n", layout).strip("\n")
            pages.append(Page(i, float(pg.width), float(pg.height), lines, layout, hlines=hl, ocr=scan_layer))
            if scan_layer:
                ocr_pages.append(i)
        if not allow_ocr and total_chars < 50 * max(1, len(pages)) and total_chars < 400:
            raise ScannedPdfError(
                f"'{os.path.basename(path)}' has no text layer (scanned PDF). "
                "The draft FS must be the text-based PDF exported from Word/Excel.")
    doc = Document(path, pages, ocr_pages=ocr_pages)
    classify_pages(doc)
    for p in doc.pages:
        build_rows(p)
    log(f"Extracted {len(pages)} pages from {doc.filename}"
        + (f" ({len(ocr_pages)} scanned page(s) – text read by OCR)" if ocr_pages else ""))
    return doc


TITLE_PATTERNS = [
    ("contents", re.compile(r"^\s*(TABLE OF\s+)?CONTENTS?\s*$|^\s*INDEX\s*$", re.I)),
    ("ar", re.compile(r"INDEPENDENT\s+AUDITOR|AUDITOR['’]?S['’]?\s+REPORT", re.I)),
    ("sofp", re.compile(r"STATEMENT\s+OF\s+FINANCIAL\s+POSITION|BALANCE\s+SHEET", re.I)),
    ("pl", re.compile(r"STATEMENT\s+OF\s+(PROFIT\s+OR\s+LOSS|COMPREHENSIVE\s+INCOME|INCOME)|INCOME\s+STATEMENT|PROFIT\s+AND\s+LOSS\s+ACCOUNT", re.I)),
    ("soce", re.compile(r"STATEMENT\s+OF\s+CHANGES\s+IN\s+(SHAREHOLDER|OWNER|PARTNER|EQUITY)", re.I)),
    ("cfs", re.compile(r"STATEMENTS?\s+OF\s+CASH\s+FLOWS?|CASH\s+FLOWS?\s+STATEMENT", re.I)),
    ("notes", re.compile(r"NOTES\s+TO\s+THE\s+(FINANCIAL\s+STATEMENTS|ACCOUNTS)", re.I)),
]


def classify_pages(doc: Document):
    in_ar = False
    ar_count = 0
    for p in doc.pages:
        top = p.top_lines(0.25)
        kind = None
        title = ""
        for ln in top:
            t = ln.text.strip()
            if len(t) > 120:
                continue
            for k, rx in TITLE_PATTERNS:
                if rx.search(t):
                    # AR keyword only counts if it is a heading-like line
                    if k == "ar" and not (t.isupper() or ln.bold or len(t) < 45):
                        continue
                    # Statement titles must be heading-like (not running AR text)
                    if k in STATEMENT_KINDS + ["notes"] and not (t.upper() == t or ln.bold or t.istitle() or len(t) < 80):
                        continue
                    kind, title = k, t
                    break
            if kind:
                break
        if kind == "ar":
            in_ar = True
        elif kind:
            in_ar = False
        elif in_ar:
            kind = "ar"
        if kind is None:
            kind = "cover" if p.n == 1 else "other"
            # continuation pages of notes / statements without repeated title
            if p.n > 1 and doc.pages[p.n - 2].kind == "notes":
                kind = "notes"
        p.kind, p.title = kind, title
        if kind == "ar":
            ar_count += 1
            p.ar_index = ar_count
        p.printed = detect_printed_number(p)
        if kind == "ar":
            p.printed = None  # AR pages are unnumbered by firm practice


def detect_printed_number(p: Page) -> Optional[str]:
    cands = []
    for ln in p.lines:
        t = ln.text.strip()
        in_band = ln.top > p.height * 0.86 or ln.bottom < p.height * 0.07
        if not in_band:
            continue
        m = re.fullmatch(r"(?:Page\s+)?(\d{1,3})(?:\s+of\s+\d{1,3})?", t, re.I) or re.fullmatch(r"-\s*(\d{1,3})\s*-", t)
        if m:
            cands.append((ln.top, m.group(1)))
    if not cands:
        return None
    cands.sort()
    return cands[-1][1]


# ---------------- tables ----------------

def _is_amount_tok(t: str) -> bool:
    if t.endswith(")") and not t.startswith("("):     # e.g. '(refer note 8.1)' – a reference, not an amount
        return False
    return t in DASH_TOKENS or bool(NUM_TOKEN.match(t))


def build_rows(p: Page):
    if p.kind in ("cover", "contents", "ar"):
        return
    header = None
    table_id = 0
    prev_bottom = None
    for idx, ln in enumerate(p.lines):
        toks = ln.words
        right = [w for w in toks if w.x0 > p.width * 0.42]
        years = [w for w in right if YEAR_TOKEN.match(w.text)]
        curs = [w for w in right if CURRENCY_CODE.match(w.text)]
        is_hdr = (len(years) >= 1 and len(years) == len([w for w in right if not re.match(r"^(Notes?|AED|Restated|\(?Restated\)?)$", w.text, re.I)])) \
            or (len(curs) >= 2 and len(curs) == len(right))
        if is_hdr:
            cols = sorted(w.x1 for w in (years if years else curs))
            note_x = None
            for w in toks:
                if re.match(r"^Notes?$", w.text, re.I):
                    note_x = (w.x0 - 15, w.x1 + 15)
            # look one line below for currency codes aligned with the columns
            cur_line = None
            if idx + 1 < len(p.lines):
                nx = p.lines[idx + 1]
                if nx.top - ln.bottom < 16 and any(CURRENCY_CODE.match(w.text) for w in nx.words):
                    cur_line = nx
            has_currency = bool(curs) or cur_line is not None
            labels = []
            if not years:  # currency-code header (e.g. SOCE) -> labels in line(s) above
                above = [l for l in p.lines[max(0, idx - 3):idx] if ln.top - l.bottom < 40]
                for l in above:
                    for ph in l.phrases():
                        labels.append((" ".join(w.text for w in ph), (ph[0].x0 + ph[-1].x1) / 2, l))
            table_id += 1
            header = {"cols": cols, "note_x": note_x, "has_currency": has_currency, "line": ln,
                      "top": ln.top, "page": p.n, "labels": labels, "cur_only": not years,
                      "table_id": table_id, "is_year": bool(years)}
            if cur_line is not None:
                header["skip_line"] = cur_line
            p.headers.append(header)
            prev_bottom = ln.bottom
            continue
        if header is None:
            continue
        if ln.top > p.height * 0.88 or (p.printed and ln.text.strip() == p.printed and ln.top > p.height * 0.8):
            continue  # footer band / page number
        if header.get("skip_line") is ln:
            prev_bottom = ln.bottom
            continue
        cols = header["cols"]
        ncol = len(cols)
        vals: list = [None] * ncol
        raw: list = [None] * ncol
        used = set()
        for wi, w in enumerate(toks):
            if not _is_amount_tok(w.text):
                continue
            dists = [abs(w.x1 - c) for c in cols]
            ci = min(range(ncol), key=lambda i: dists[i])
            if dists[ci] <= 30 and vals[ci] is None:
                vals[ci] = parse_amount(w.text)
                raw[ci] = w.text
                used.add(wi)
        label_limit = min(cols) - 75
        first_amt_x = min((toks[wi].x0 for wi in used), default=float("inf"))
        note_ref = None
        label_words = []
        for wi, w in enumerate(toks):
            if wi in used:
                continue
            if re.fullmatch(r"\d{1,2}(?:\.\d{1,2})?(?:\s*&\s*\d{1,2})?|\d{1,2},\d{1,2}", w.text) and w.x0 > p.width * 0.35 and w.x1 < label_limit + 70:
                if header["note_x"] is None or header["note_x"][0] - 20 <= w.x0 <= header["note_x"][1] + 20:
                    note_ref = w.text
                    continue
            if w.x1 <= label_limit + 60 or (used and w.x1 < first_amt_x - 4 and not _is_amount_tok(w.text)):
                label_words.append(w)      # long captions such as '... (refer note 8.1)' run into the columns
        label = " ".join(w.text for w in label_words).strip()
        prose = [w for wi, w in enumerate(toks) if wi not in used and w not in label_words
                 and w.text != (note_ref or "\0") and not _is_amount_tok(w.text)]
        if prose:
            # running text that spans into the amount columns -> not a table row
            prev_bottom = ln.bottom
            continue
        if all(v is None for v in vals):
            # heading / text row
            if label and len(label) < 90:
                p.rows.append(Row(p.n, ln.top, ln.bottom, label, note_ref, vals, raw, [False] * ncol,
                                  ln.bold, header["table_id"], is_heading=True))
            prev_bottom = ln.bottom
            continue
        above = [False] * ncol
        for (x0, x1, top) in p.hlines:
            lo = prev_bottom if prev_bottom is not None else ln.top - 14
            if lo - 0.5 <= top <= ln.top + 1.5 and (top - lo) >= (ln.top - top) - 0.5:
                for ci, c in enumerate(cols):
                    if x0 <= c - 8 and x1 >= c - 30:
                        above[ci] = True
        p.rows.append(Row(p.n, ln.top, ln.bottom, label, note_ref, vals, raw, above,
                          ln.bold or any(w.bold for w in label_words), header["table_id"]))
        prev_bottom = ln.bottom

# --------------------------------------------------------------------------
# Rule engine
# --------------------------------------------------------------------------

@dataclass
class Finding:
    point: int
    text: str
    kind: str = "Exception"       # Exception | Query
    rule: str = ""
    rid: str = ""


@dataclass
class Facts:
    client: str = ""
    client_canonical: str = ""
    period_end: Optional[_dt.date] = None
    period_start: Optional[_dt.date] = None
    period_label: str = ""
    year: str = ""
    first_period: bool = False
    note_heads: list = field(default_factory=list)
    contents: list = field(default_factory=list)
    name_occurrences: int = 0
    page_ref_note: str = ""
    arithmetic: list = field(default_factory=list)   # dicts of python arithmetic results
    notes_unchecked: list = field(default_factory=list)
    has_related: bool = False


SUFFIX_RX = re.compile(
    r"^(?:L\.?\s?L\.?\s?C\.?(?:\s?-\s?F\.?Z\.?E?\.?)?|LLC(?:\s?-\s?FZ)?|F\.?Z\.?E\.?|FZCO|F\.?Z\.?\s?-?\s?LLC|FZC|"
    r"LTD\.?|LIMITED|P\.?J\.?S\.?C\.?|PSC|S\.?P\.?C\.?|INC\.?|CORP\.?|PLC|EST\.?|ESTABLISHMENT|FZ|SOLE\s+PROPRIETORSHIP)",
    re.I)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _clean_name(s: str) -> str:
    s = re.sub(r"^\s*M/?s\.?\s+", "", s.strip(), flags=re.I)
    s = re.sub(r"['’]s$", "", s)
    return s.strip(" ,;:()\"“”'’")


def detect_company(doc: Document) -> tuple:
    """Returns (cover_name, core_words)."""
    cands = []
    for p in doc.pages[:3]:
        for ln in p.lines:
            t = _clean_name(ln.text)
            toks = t.split()
            for i in range(1, len(toks)):
                rest = " ".join(toks[i:])
                m = SUFFIX_RX.match(rest)
                if m and len(rest) - m.end() <= 1:
                    size = max(w.size for w in ln.words)
                    cands.append((p.n == 1, size, t, toks[:i]))
                    break
    if not cands:
        st = doc.first("sofp") or doc.first("pl")
        if st and st.lines:
            t = _clean_name(st.lines[0].text)
            return t, t.split()
        return "", []
    cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
    _, _, name, core = cands[0]
    return name, core


def name_occurrences(doc: Document, core: list) -> list:
    """List of (page, line, variant_text, core_ratio, has_suffix)."""
    out = []
    n = len(core)
    if n == 0:
        return out
    core_s = " ".join(core)
    for p in doc.pages:
        for ln in p.lines:
            toks = ln.text.split()
            i = 0
            while i <= len(toks) - n:
                window = " ".join(toks[i:i + n])
                w_clean = re.sub(r"^\s*M/?s\.?", "", window, flags=re.I).strip()
                r = _sim(w_clean, core_s)
                if r >= 0.86 and _norm(w_clean)[:2] == _norm(core_s)[:2]:
                    rest = " ".join(toks[i + n:i + n + 3])
                    m = SUFFIX_RX.match(rest)
                    if m:
                        suf = rest[:m.end()]
                        variant = (w_clean + " " + suf).strip()
                    else:
                        variant = w_clean
                    variant = re.sub(r"['’]s$", "", variant).strip(" ,;:()\"“”'’")
                    out.append((p, ln, variant, r, bool(m)))
                    i += n
                else:
                    i += 1
    return out


def note_headings(doc: Document) -> list:
    heads = []
    for p in doc.by_kind("notes"):
        for ln in p.lines:
            if ln.top < p.height * 0.12 or ln.top > p.height * 0.9:
                continue
            t = ln.text.strip()
            m = re.match(r"^(\d{1,2})(\.?)\s+([A-Z(\"'][^\n]{2,100})$", t)
            if m and not re.search(r"\d{1,3},\d{3}", m.group(3)) and (ln.bold or m.group(3).upper() == m.group(3)
                                                                       or (p.ocr and len(t) < 70)) \
                    and not re.search(r"\b(?:19|20)\d{2}\b\s*$", m.group(3)):
                heads.append({"page": p, "top": ln.top, "num": int(m.group(1)), "sub": None,
                              "dot": m.group(2), "title": m.group(3).strip(), "text": t})
                continue
            m = re.match(r"^(\d{1,2})\.(\d{1,2})(\.?)\s+([A-Za-z(\"'].{2,100})$", t)
            if m and len(t) < 110 and not t.endswith(".") and (ln.bold or m.group(4)[0].isupper()):
                heads.append({"page": p, "top": ln.top, "num": int(m.group(1)), "sub": int(m.group(2)),
                              "dot": m.group(3), "title": m.group(4).strip(), "text": t})
    return heads


def note_of(heads: list, page: Page, top: float) -> Optional[int]:
    cur = None
    for h in heads:
        if h["sub"] is not None:
            continue
        if (h["page"].n, h["top"]) <= (page.n, top):
            cur = h["num"]
    return cur


def main_notes(heads: list) -> dict:
    d = {}
    for h in heads:
        if h["sub"] is None and h["num"] not in d:
            d[h["num"]] = h
    return d


def rows_of(doc: Document, kind: str) -> list:
    out = []
    for p in doc.by_kind(kind):
        out.extend(p.rows)
    return out


def find_row(rows: list, rx: str, last: bool = False) -> Optional[Row]:
    m = [r for r in rows if not r.is_heading and re.search(rx, r.label, re.I)]
    if not m:
        return None
    return m[-1] if last else m[0]


def header_of(doc: Document, row: Row) -> Optional[dict]:
    p = doc.page(row.page)
    for h in p.headers:
        if h["table_id"] == row.table_id:
            return h
    return None


def col_names(doc: Document, row: Row) -> list:
    h = header_of(doc, row)
    if not h:
        return []
    names = []
    for w in h["line"].words:
        if YEAR_TOKEN.match(w.text) and w.x0 > doc.page(row.page).width * 0.42:
            names.append(w.text)
    if len(names) == len(h["cols"]):
        return names
    if h["labels"]:
        out = []
        for c in h["cols"]:
            best = min(h["labels"], key=lambda lb: abs(lb[1] - (c - 25)))
            out.append(best[0])
        return out
    return [f"column {i + 1}" for i in range(len(h["cols"]))]


def kind_label(page: Page) -> str:
    return {"sofp": "SOFP", "pl": "P&L", "soce": "SOCE", "cfs": "CFS"}.get(page.kind, "")


def where(page: Page, extra: str = "") -> str:
    k = kind_label(page)
    return f"{page.ref}{' ' + k if k else ''}{(' ' + extra) if extra else ''}"


def _q(s: str, n: int = 90) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n - 1] + "…"


class RuleEngine:
    def __init__(self, doc: Document, py: Optional[Document], log: Callable = print):
        self.doc, self.py, self.log = doc, py, log
        self.f: list = []
        self.facts = Facts()
        self.heads = note_headings(doc)
        self.facts.note_heads = self.heads
        self.mains = main_notes(self.heads)

    def add(self, point: int, text: str, kind: str = "Exception", rule: str = ""):
        for x in self.f:
            if x.point == point and x.text == text:
                return
        self.f.append(Finding(point, text, kind, rule))

    # ---------------- facts ----------------
    def gather_facts(self):
        doc, F = self.doc, self.facts
        name, core = detect_company(doc)
        self.core = core
        occ = name_occurrences(doc, core)
        self.occ = occ
        F.name_occurrences = len(occ)
        forms = Counter(v for (_, _, v, r, has) in occ if has)
        tc = [v for v, _ in forms.most_common() if not v.isupper()]
        F.client = tc[0] if tc else (name.title() if name.isupper() else name) or "Client"
        up = Counter()
        for v, c in forms.items():
            up[re.sub(r"\s+", " ", v).upper()] += c
        top_up = up.most_common(1)[0][0] if up else ""
        F.client_canonical = next((v for v in tc if re.sub(r"\s+", " ", v).upper() == top_up), None) or \
            (forms.most_common(1)[0][0] if forms else name)
        # period end
        dates = Counter()
        starts = Counter()
        label_kind = Counter()
        for p in doc.pages:
            if p.kind not in ("cover", "sofp", "pl", "soce", "cfs", "notes"):
                continue
            for ln in p.top_lines(0.3) if p.kind != "cover" else p.lines:
                t = ln.text
                m = re.search(r"(YEAR|PERIOD)\s+ENDED\s+(.*)", t, re.I)
                if m:
                    dm = DATE_RE.search(m.group(2))
                    if dm and parse_date(dm):
                        dates[parse_date(dm)] += 2
                        label_kind[m.group(1).lower()] += 1
                m = re.search(r"\bAS\s+(?:AT|OF)\s+(.*)", t, re.I)
                if m:
                    dm = DATE_RE.search(m.group(1))
                    if dm and parse_date(dm):
                        dates[parse_date(dm)] += 1
                m = re.search(r"PERIOD\s+FROM\s+(.*?)\s+TO\s+(.*)", t, re.I)
                if m:
                    d1, d2 = DATE_RE.search(m.group(1)), DATE_RE.search(m.group(2))
                    if d1 and d2 and parse_date(d1) and parse_date(d2):
                        starts[parse_date(d1)] += 1
                        dates[parse_date(d2)] += 2
                        label_kind["period"] += 1
        if dates:
            F.period_end = dates.most_common(1)[0][0]
            F.year = str(F.period_end.year)
        if starts:
            F.period_start = starts.most_common(1)[0][0]
        if F.period_end:
            if F.period_start:
                F.period_label = f"Period from {fmt_date(F.period_start)} to {fmt_date(F.period_end)}"
            else:
                kind = "Year" if label_kind.get("year", 0) >= label_kind.get("period", 0) else "Period"
                F.period_label = f"{kind} ended {fmt_date(F.period_end)}"
        # first period
        full = "\n".join(p.text for p in doc.pages)
        single_col = all(len(h["cols"]) == 1 for k in STATEMENT_KINDS for p in doc.by_kind(k)
                         for h in p.headers if h.get("is_year")) and any(
            h.get("is_year") for k in STATEMENT_KINDS for p in doc.by_kind(k) for h in p.headers)
        F.first_period = bool(re.search(
            r"first (set of )?(audited )?financial statements|no comparative|comparative (figures|information|amounts) "
            r"(are|is|have|has) not been presented|comparatives? (are|is) not (presented|applicable)|first (financial|reporting) period",
            full, re.I)) or single_col or bool(F.period_start and re.search(r"date of incorporation|incorporat", full, re.I) and single_col)
        # contents
        cp = doc.first("contents")
        if cp:
            for ln in cp.lines:
                ph = ln.phrases(14)
                if len(ph) < 2:
                    continue
                last = " ".join(w.text for w in ph[-1])
                m = re.fullmatch(r"(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?", last)
                if not m:
                    continue
                label = " ".join(" ".join(w.text for w in x) for x in ph[:-1])
                kind = None
                for k, rx in TITLE_PATTERNS:
                    if k != "contents" and rx.search(label):
                        kind = k
                        break
                if re.search(r"auditor", label, re.I):
                    kind = "ar"
                F.contents.append({"label": label, "kind": kind, "start": int(m.group(1)),
                                   "end": int(m.group(2)) if m.group(2) else int(m.group(1))})
        ar = doc.by_kind("ar")
        if ar:
            F.page_ref_note = (f"Page references are to the printed page numbers (p4, p5 …). The Auditor's Report pages are "
                               f"unnumbered and are referred to as AR p1–p{len(ar)} (PDF pages {ar[0].n}–{ar[-1].n}).")
        else:
            F.page_ref_note = "Page references are to the printed page numbers (p4, p5 …); unnumbered pages are referred to by PDF page number."

    # ---------------- run ----------------
    def run(self) -> tuple:
        self.gather_facts()
        steps = [self.p1_overall, self.p2_py_figures, self.p4_header_footer, self.p5_11_pages_sequence,
                 self.p6_name, self.p7_dates, self.p8_currency, self.p9_casting, self.p10_links,
                 self.p12_format, self.p13_cfs_noncash, self.p16_company_term, self.p17_cfs_captions,
                 self.p18_spelling, self.p19_related]
        for s in steps:
            try:
                s()
            except Exception as e:  # never let one rule kill the run
                self.log(f"  rule {s.__name__} skipped: {e}")
        for i, x in enumerate(self.f, 1):
            x.rid = f"R{i}"
        return self.f, self.facts

    # ---------------- point 1 ----------------
    def p1_overall(self):
        doc = self.doc
        for p in doc.pages:
            for ln in p.lines:
                if re.search(r"\bthe Group\b", ln.text, re.I):
                    self.add(1, f"{p.ref}: \"{_q(ln.text)}\" refers to \"the Group\" in a single-company FS → replace with \"the Company\".", rule="the Group")
        # country wording
        variants = defaultdict(list)
        for p in doc.pages:
            for ln in p.lines:
                for m in re.finditer(r"\bU\.A\.E\.|\bU\.A\.E\b|\bUAE\b", ln.text):
                    after = ln.text[m.end():m.end() + 10]
                    if re.match(r"\s*Dirham", after, re.I):
                        continue
                    v = m.group(0)
                    variants[v].append(p.ref)
        if len(variants) > 1:
            parts = "; ".join(f"\"{v}\" ({', '.join(sorted(set(r))[:6])})" for v, r in variants.items())
            dom = max(variants, key=lambda v: len(variants[v]))
            self.add(1, f"Inconsistent country wording: {parts} → harmonise (e.g. \"{dom}\" throughout).", rule="country")
        # nil lines in notes
        for p in doc.by_kind("notes"):
            for r in p.rows:
                if r.is_heading or not r.label:
                    continue
                if all(x is not None for x in r.raw) and all(x in DASH_TOKENS for x in r.raw):
                    self.add(1, f"{p.ref} Note {note_of(self.heads, p, r.top) or ''}: line \"{_q(r.label, 60)}\" shows nil in all columns → delete the line.".replace("Note :", "notes:"), rule="nil line")
        # equity components / related party note
        sofp = rows_of(doc, "sofp")
        titles = [h["title"] for h in self.mains.values()]
        for r in sofp:
            if r.is_heading:
                continue
            if re.search(r"share premium|contribution from (the )?shareholders?|shareholders?['’]?\s+contribution|capital contribution|statutory reserve|legal reserve", r.label, re.I):
                has_note = any(_sim(r.label, t) > 0.75 or _norm(r.label) in _norm(t) or _norm(t) in _norm(r.label) for t in titles)
                if not r.note_ref and not has_note:
                    self.add(1, f"{doc.page(r.page).ref} SOFP: \"{r.label}\" has no accounting policy / note and no note reference → add a note (and policy) and reference it.", rule="equity note")
        rp_rx = r"related part|due (to|from) (a |the )?(shareholder|director|related|partner)|shareholders?['’]? current account|director['’]?s? current account|contribution from (the )?shareholder|investment in (subsidiar|associate|joint)"
        has_rp = any(re.search(rp_rx, r.label, re.I) for k in STATEMENT_KINDS for r in rows_of(doc, k) if not r.is_heading)
        has_rp_note = any(re.search(r"RELATED\s+PART", h["title"], re.I) for h in self.heads)
        if has_rp and not has_rp_note:
            self.add(1, "No related party note although the statements show related-party / shareholder balances or contributions → add a related party transactions and balances note.", rule="rp note")
        # incomplete adoption list
        for p in doc.by_kind("notes"):
            for i, ln in enumerate(p.lines):
                if re.search(r"following (new and revised |amended )?(IFRS|standards|amendments)\S*.*(have been|were) adopted", ln.text, re.I):
                    nxt = " ".join(l.text for l in p.lines[i + 1:i + 3])
                    if not re.search(r"IFRS|IAS|Amendments?|Standard", nxt):
                        self.add(1, f"{p.ref}: \"{_q(ln.text)}\" is not followed by the list of standards → add the list or delete the sentence.", rule="adoption list")
        # duplicated paragraphs (identical long lines repeated)
        seen = {}
        for p in doc.pages:
            if p.kind in ("cover", "contents"):
                continue
            for ln in p.lines:
                t = re.sub(r"\s+", " ", ln.text).strip()
                if len(t) < 70 or re.search(r"form an integral part|NOTES TO THE", t, re.I):
                    continue
                if t in seen and seen[t] != p.n:
                    pass
                elif t in seen:
                    self.add(1, f"{p.ref}: text \"{_q(t, 70)}\" appears twice → delete the duplicated paragraph.", rule="duplicate")
                seen.setdefault(t, p.n)

    # ---------------- point 2 ----------------
    def p2_py_figures(self):
        if self.facts.first_period or not self.py:
            return
        py = self.py
        py_heads = note_headings(py)
        diffs = 0
        reclass = bool(re.search(r"reclassif|restate", "\n".join(p.text for p in self.doc.pages), re.I))
        for kind in STATEMENT_KINDS + ["notes"]:
            cur_rows = [r for r in rows_of(self.doc, kind) if not r.is_heading and r.label and len(r.values) >= 2]
            py_rows = [r for r in rows_of(py, kind) if not r.is_heading and r.label]
            if not cur_rows or not py_rows:
                continue
            for r in cur_rows:
                if kind == "soce":
                    continue
                key = _norm(r.label)
                if kind == "notes":
                    nn = note_of(self.heads, self.doc.page(r.page), r.top)
                    title = main_notes(self.heads).get(nn, {}).get("title", "") if nn else ""
                    cands = [x for x in py_rows if _norm(x.label) == key and
                             _sim(main_notes(py_heads).get(note_of(py_heads, py.page(x.page), x.top), {}).get("title", ""), title) > 0.8]
                else:
                    cands = [x for x in py_rows if _norm(x.label) == key]
                if len(cands) != 1 or not key:
                    continue
                x = cands[0]
                a, b = r.values[1], x.values[0]
                if a is None or b is None:
                    continue
                if py.scanned and (abs(a - b * 1000) < 1 or abs(b - a * 1000) < 1):
                    continue          # OCR read the thousands comma as a decimal point
                if abs(a - b) >= 0.5:
                    diffs += 1
                    if py.scanned:
                        self.add(2, f"Query – {where(self.doc.page(r.page))}: \"{_q(r.label, 60)}\" PY shows {fmt_amt(a)} but the scanned "
                                    f"PY FS reads {fmt_amt(b)} ({where(py.page(x.page))}, read by OCR) → verify against the acknowledged copy.",
                                 "Query", rule="py figure (OCR)")
                        continue
                    kindtxt = "Query – " if reclass else ""
                    self.add(2, f"{kindtxt}{where(self.doc.page(r.page))}: \"{_q(r.label, 60)}\" PY shows {fmt_amt(a)} but the acknowledged PY FS shows {fmt_amt(b)} ({where(py.page(x.page))}) → agree to the acknowledged copy"
                                f"{' or confirm the reclassification note' if reclass else ''}.",
                             "Query" if reclass else "Exception", rule="py figure")
        self.facts.arithmetic.append({"type": "py_compare_rows", "differences": diffs})

    # ---------------- point 4 ----------------
    def p4_header_footer(self):
        doc = self.doc
        core = " ".join(self.core)
        for p in doc.pages:
            if p.kind not in STATEMENT_KINDS + ["notes"]:
                continue
            top = " ".join(l.text for l in p.top_lines(0.16))
            toks = top.split()
            n = len(self.core)
            found = any(_sim(" ".join(toks[i:i + n]), core) >= 0.86 for i in range(max(1, len(toks) - n + 1))) if n else True
            if not found:
                self.add(4, f"{p.ref} ({KIND_LABELS[p.kind]}): company name header missing → add \"{self.facts.client_canonical}\" header.", rule="header")
        last = max([h["num"] for h in self.heads if h["sub"] is None], default=None)
        bad_footer: dict = {}
        for p in doc.pages:
            if p.kind not in STATEMENT_KINDS:
                continue
            for ln in p.lines:
                m = re.search(r"notes?\s*(?:on pages?\s*[\d\s\-–to]+)?\(?\s*(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\s*\)?\s*(?:form|are|is)", ln.text, re.I)
                if m and last and int(m.group(2)) != last:
                    bad_footer.setdefault(m.group(0)[:40], (ln.text, []))[1].append(f"{p.ref} {kind_label(p)}")
        for key, (txt, refs) in bad_footer.items():
            self.add(4, f"Footer \"{_q(txt, 80)}\" on {', '.join(refs)} – last note is Note {last} → change to \"(1-{last})\".", rule="footer")

    # ---------------- points 5 & 11 ----------------
    def p5_11_pages_sequence(self):
        doc, F = self.doc, self.facts
        numbered = [(p, int(p.printed)) for p in doc.pages if p.printed and p.printed.isdigit()]
        # physical order of statements vs contents
        order_c = []
        for c in F.contents:
            if c["kind"] in STATEMENT_KINDS + ["notes"] and c["kind"] not in order_c:
                order_c.append(c["kind"])
        order_p = []
        for p in doc.pages:
            if p.kind in STATEMENT_KINDS + ["notes"] and p.kind not in order_p:
                order_p.append(p.kind)
        swapped_pages = set()
        if order_c and [k for k in order_p if k in order_c] != [k for k in order_c if k in order_p]:
            seq_p = [k for k in order_p if k in order_c]
            seq_c = [k for k in order_c if k in order_p]
            mis = [k for i, k in enumerate(seq_p) if seq_c[i] != k]
            desc = []
            for k in mis:
                pg = doc.first(k)
                desc.append(f"{kind_label(pg) or 'Notes'} ({pg.ref}, PDF p{pg.n})")
                swapped_pages.update(x.n for x in doc.by_kind(k))
            nums = [x for x in numbered if x[0].n in swapped_pages]
            pages_txt = ", ".join(str(n) for _, n in nums)
            self.add(11, f"Physical order differs from Contents: printed as {' → '.join(desc)}; page order {pages_txt} → reorder to follow Contents ({' → '.join(KIND_LABELS[k] for k in seq_c)}).", rule="order")
        # printed page sequence
        prev = None
        for p, n in numbered:
            if prev is not None:
                pp, pn = prev
                if n != pn + 1:
                    if p.n in swapped_pages and pp.n in swapped_pages:
                        prev = (p, n)
                        continue
                    if n <= pn:
                        self.add(5, f"Printed page numbers out of sequence: PDF p{pp.n} is p{pn} and PDF p{p.n} is p{n} → renumber / reorder.", rule="page seq")
            prev = (p, n)
        if numbered:
            nums_all = [n for _, n in numbered]
            missing = sorted(set(range(min(nums_all), max(nums_all) + 1)) - set(nums_all))
            if missing:
                self.add(5, f"Printed page number{'s' if len(missing) > 1 else ''} {', '.join('p' + str(x) for x in missing)} missing from the sequence ({', '.join(str(x) for x in nums_all)}) → renumber pages.", rule="page missing")
        for p in doc.pages:
            if p.kind in STATEMENT_KINDS + ["notes"] and not p.printed:
                self.add(5, f"PDF p{p.n} ({KIND_LABELS[p.kind]}) has no printed page number → add page number.", rule="no page no")
        # contents vs pages
        for c in F.contents:
            k = c["kind"]
            if k in (None, "ar"):
                continue
            pgs = [p for p in doc.by_kind(k) if p.printed and p.printed.isdigit()]
            if not pgs:
                continue
            s, e = int(pgs[0].printed), int(pgs[-1].printed)
            nums = sorted(int(p.printed) for p in pgs)
            s, e = nums[0], nums[-1]
            shown = f"{c['start']}" + (f" - {c['end']}" if c['end'] != c['start'] else "")
            actual = f"{s}" + (f" - {e}" if e != s else "")
            if (c["start"], c["end"]) != (s, e) and not (c["end"] == c["start"] and c["start"] == s):
                self.add(5, f"Contents: \"{_q(c['label'], 60)}\" shows page {shown} but it is printed on {('pages ' if e != s else 'page ') + actual} → correct Contents.", rule="contents")
        # note numbering gaps / repeats
        mains = [h for h in self.heads if h["sub"] is None]
        prevn = None
        seen = set()
        for h in mains:
            n = h["num"]
            if n in seen:
                self.add(11, f"{h['page'].ref}: Note {n} (\"{_q(h['title'], 40)}\") is numbered again → renumber.", rule="note repeat")
            elif prevn is not None and n > prevn + 1:
                miss = ", ".join(str(x) for x in range(prevn + 1, n))
                self.add(11, f"{h['page'].ref}: note numbering jumps from Note {prevn} to Note {n} (Note {miss} missing) → renumber notes and references.", rule="note gap")
            elif prevn is not None and n < prevn:
                self.add(11, f"{h['page'].ref}: Note {n} follows Note {prevn} → correct note sequence.", rule="note order")
            seen.add(n)
            prevn = n if prevn is None or n > prevn else prevn
        if mains and mains[0]["num"] != 1:
            self.add(11, f"Notes start at Note {mains[0]['num']} ({mains[0]['page'].ref}) → start at Note 1.", rule="note start")
        subs = defaultdict(list)
        for h in self.heads:
            if h["sub"] is not None:
                subs[h["num"]].append(h)
        for n, lst in subs.items():
            prev_s = None
            for h in lst:
                if prev_s is not None and h["sub"] == prev_s:
                    self.add(11, f"{h['page'].ref}: sub-note {n}.{h['sub']} repeated → renumber.", rule="sub repeat")
                elif prev_s is not None and h["sub"] > prev_s + 1:
                    self.add(11, f"{h['page'].ref}: sub-note numbering jumps from {n}.{prev_s} to {n}.{h['sub']} → renumber.", rule="sub gap")
                prev_s = h["sub"]
        # face note refs ascending
        for k in STATEMENT_KINDS:
            for p in doc.by_kind(k):
                refs = [r.note_ref for r in p.rows if r.note_ref]
                nums = []
                for x in refs:
                    try:
                        nums.append(float(re.split(r"[&,]", x)[0]))
                    except ValueError:
                        pass
                bad = [i for i in range(1, len(nums)) if nums[i] < nums[i - 1]]
                if bad:
                    self.add(11, f"{p.ref} {kind_label(p)}: note references not in ascending order ({', '.join(refs)}) → renumber notes to follow the face of the statement.", rule="refs order")

    # ---------------- point 6 ----------------
    def p6_name(self):
        F = self.facts
        canon = F.client_canonical
        if not canon:
            return
        cu = re.sub(r"\s+", " ", canon).upper().rstrip(".")
        groups = defaultdict(list)
        for (p, ln, v, r, has) in self.occ:
            vu = re.sub(r"\s+", " ", v).upper()
            if vu == cu + "." and not canon.endswith("."):
                continue
            if vu.rstrip(".") == cu and vu.endswith(".") == canon.upper().endswith("."):
                continue
            if not has:
                # name used without legal suffix – report only in headers/titles
                if ln.top < p.height * 0.16 and p.kind in STATEMENT_KINDS + ["notes"]:
                    groups[v + " (no legal form)"].append(p)
                continue
            if vu.rstrip(".") == cu and canon.upper().endswith(".") and not vu.endswith("."):
                # trailing dot dropped
                after = ln.text.split(v, 1)[-1][:1] if v in ln.text else ""
                if after == ".":
                    continue
            groups[v].append(p)
        for v, pages in groups.items():
            refs = []
            for p in pages:
                r = p.ref + (" header" if p.kind in STATEMENT_KINDS + ["notes"] else "")
                if r not in refs:
                    refs.append(r)
            self.add(6, f"\"{v.replace(' (no legal form)', '')}\" ({', '.join(refs[:8])}) differs from \"{canon}\" used elsewhere → change to \"{canon}\".", rule="name")

    # ---------------- point 7 ----------------
    def p7_dates(self):
        doc, F = self.doc, self.facts
        pe = F.period_end
        if not pe:
            return
        # headings with wrong date / year
        for p in doc.pages:
            if p.kind not in STATEMENT_KINDS + ["notes"]:
                continue
            first_hdr = min([h["top"] for h in p.headers], default=p.height * 0.2)
            for ln in p.top_lines(0.2):
                if ln.top >= first_hdr or re.search(r"\d{1,3},\d{3}", ln.text):
                    continue
                if not re.search(r"ENDED|AS\s+AT|AS\s+OF|\bTO\b", ln.text, re.I):
                    continue
                for m in DATE_RE.finditer(ln.text):
                    d = parse_date(m)
                    if d and d != pe and not (F.period_start and d == F.period_start):
                        self.add(7, f"{p.ref} heading: \"{_q(ln.text, 70)}\" → should read {fmt_date(pe)}.", rule="heading date")
        # AR date
        ar = doc.by_kind("ar")
        if ar:
            last = ar[-1]
            cands = []
            for ln in last.lines:
                for m in DATE_RE.finditer(ln.text):
                    d = parse_date(m)
                    if d and d != pe:
                        cands.append((ln, m.group(0), d))
            if cands:
                ln, txt, d = cands[-1]
                if d < pe:
                    self.add(7, f"{last.ref}: AR dated \"{txt}\", which is before the period end {fmt_date(pe)} → correct the AR date (after the period end).", rule="AR date")
            for p in ar:
                for ln in p.lines:
                    for m in DATE_RE.finditer(ln.text):
                        d = parse_date(m)
                        if d and (d.month, d.day) == (pe.month, pe.day) and d.year != pe.year and not re.search(r"compar|prior|previous|audited by|preceding", ln.text, re.I):
                            self.add(7, f"{p.ref}: \"{_q(ln.text, 80)}\" shows {m.group(0)} → should be {fmt_date(pe)}.", rule="AR year")
        # date format
        commas = Counter()
        for p in doc.pages:
            for m in DATE_RE.finditer(p.text):
                if m.group("m1"):
                    commas["comma" if m.group("c1") else "nocomma"] += 1
        if commas["comma"] > commas["nocomma"]:
            for p in doc.pages:
                for ln in p.lines:
                    for m in DATE_RE.finditer(ln.text):
                        if m.group("m1") and not m.group("c1"):
                            fixed = f"{m.group('m1')} {m.group('d1')}, {m.group('y1')}"
                            self.add(7, f"{p.ref}: date format \"{m.group(0)}\" → \"{fixed}\".", rule="date format")
        # period wording
        uses = defaultdict(set)
        for p in doc.pages:
            if p.kind not in ("ar", "pl", "soce", "cfs", "notes"):
                continue
            for m in re.finditer(r"\b(?:for the|then)\s+(year|period)\s+(?:then\s+)?ended\b|\b(year|period) ended\b", p.text, re.I):
                w = (m.group(1) or m.group(2)).lower()
                uses[w].add(p.ref)
        if len(uses) == 2 and not F.period_start:
            minority = min(uses, key=lambda k: len(uses[k]))
            major = "year" if minority == "period" else "period"
            self.add(7, f"Period wording inconsistent: \"{minority} ended\" used on {', '.join(sorted(uses[minority])[:8])} while \"{major} ended\" is used elsewhere → use \"{major}\" consistently.", rule="period wording")
        # incorporation date consistency
        inc = defaultdict(set)
        for p in doc.pages:
            txt = re.sub(r"\s+", " ", p.text)
            for m in re.finditer(r"(incorporat\w*|registered|date of (?:incorporation|registration)|established)", txt, re.I):
                win = txt[max(0, m.start() - 60): m.end() + 80]
                for dm in DATE_RE.finditer(win):
                    d = parse_date(dm)
                    if d and d != pe:
                        inc[d].add(p.ref)
        if len(inc) > 1:
            parts = "; ".join(f"{fmt_date(d)} ({', '.join(sorted(r))})" for d, r in inc.items())
            self.add(7, f"Query – Incorporation/registration date differs between notes: {parts} → confirm and align (Note 1, tax note, comparatives note).", "Query", rule="incorporation")

    # ---------------- point 8 ----------------
    def p8_currency(self):
        doc = self.doc
        names = defaultdict(set)
        codes = defaultdict(set)
        for p in doc.pages:
            for ln in p.lines:
                for m in re.finditer(r"\b(?:United Arab Emirates|U\.A\.E\.?|UAE)\s+Dirhams?\b|(?<![A-Za-z.]\s)(?<!E\.\s)\bDirhams?\b", ln.text):
                    names[m.group(0)].add(p.ref)
                for m in re.finditer(r"\bAED\b|\bDhs?\b\.?|\bAEDs\b", ln.text):
                    codes[m.group(0)].add(p.ref)
        if len(names) > 1:
            parts = "; ".join(f"\"{k}\" ({', '.join(sorted(v)[:6])})" for k, v in names.items())
            dom = max(names, key=lambda k: len(names[k]))
            self.add(8, f"Currency name inconsistent: {parts} → harmonise (e.g. \"{dom}\").", rule="currency name")
        if len(codes) > 1:
            parts = "; ".join(f"\"{k}\" ({', '.join(sorted(v)[:6])})" for k, v in codes.items())
            self.add(8, f"Currency code inconsistent: {parts} → use one code throughout.", rule="currency code")
        for p in doc.pages:
            for h in p.headers:
                if h.get("is_year") and not h["has_currency"]:
                    nn = note_of(self.heads, p, h["top"]) if p.kind == "notes" else None
                    loc = " ".join(x for x in (p.ref, kind_label(p), f"Note {nn}" if nn else "") if x)
                    self.add(8, f"{loc.strip()}: column header \"{_q(h['line'].text, 40)}\" has no currency → add \"AED\" under the year columns.", rule="col currency")
        dec, whole = [], 0
        for p in doc.pages:
            for r in p.rows:
                for t in r.raw:
                    if t and re.search(r"\.\d{1,2}\)?$", t):
                        dec.append((p, r, t))
                    elif t and NUM_TOKEN.match(t):
                        whole += 1
        if dec and whole > 5 * len(dec):
            for p, r, t in dec[:10]:
                self.add(8, f"{p.ref}: \"{_q(r.label, 40)}\" shows decimals ({t}) while the FS are in whole units → round.", rule="decimals")

    # ---------------- point 9 ----------------
    def p9_casting(self):
        doc = self.doc
        for p in doc.pages:
            if p.kind not in STATEMENT_KINDS + ["notes"]:
                continue
            tables = OrderedDict()
            for r in p.rows:
                tables.setdefault(r.table_id, []).append(r)
            for tid, rows in tables.items():
                hdr = next((h for h in p.headers if h["table_id"] == tid), None)
                if not hdr:
                    continue
                ncol = len(hdr["cols"])
                names = col_names(doc, rows[0])
                data = [r for r in rows if not r.is_heading]
                if not data:
                    continue
                bal_rows = [r for r in data if re.match(r"^(Balance|As at|At\s+\w+\s+\d)", r.label, re.I)]
                labels = [lb[0] for lb in hdr.get("labels", [])]
                total_col = ncol >= 3 and any(re.fullmatch(r"total", l.strip(), re.I) for l in labels)
                if p.kind == "soce" and ncol >= 3 and not labels:
                    total_col = True
                if total_col:
                    for r in data:
                        vals = [v if v is not None else 0.0 for v in r.values]
                        if r.values[-1] is None or all(not v for v in r.values[:-1]):
                            continue          # line shows only the total (e.g. a management overlay)
                        s = sum(vals[:-1])
                        if abs(s - vals[-1]) >= 0.5:
                            self._cast(p, r, names[-1] if names else "Total", vals[-1], s, "cross-cast")
                if len(bal_rows) >= 2:
                    for ci in range(ncol):
                        prev_bal, mov = None, []
                        for r in data:
                            v = r.values[ci]
                            if r in bal_rows:
                                if prev_bal is not None and v is not None and mov:
                                    exp = prev_bal + sum(mov)
                                    if abs(exp - v) >= 0.5 and not self._explained(data, r, ci, v):
                                        self._cast(p, r, names[ci] if ci < len(names) else "", v, exp, "cast")
                                prev_bal, mov = (v if v is not None else 0.0), []
                            elif v is not None:
                                mov.append(v)
                    continue
                for ci in range(ncol):
                    pending, totals_sec, details_sec, netcash = [], [], [], []
                    last_total = None
                    for r in rows:
                        if r.is_heading:
                            if not re.match(r"^total\b", r.label, re.I):
                                pending, totals_sec, details_sec = [], [], []
                                last_total = None if p.kind != "cfs" else last_total
                            continue
                        v = r.values[ci]
                        if v is None:
                            continue
                        is_total = r.line_above[ci] or bool(re.match(r"^total\b", r.label, re.I))
                        if is_total and (pending or totals_sec or last_total is not None):
                            hyps = []
                            if pending:
                                hyps.append(sum(pending))
                            if last_total is not None:
                                hyps.append(last_total + sum(pending))
                            if totals_sec:
                                hyps.append(sum(totals_sec) + sum(pending))
                            if details_sec:
                                hyps.append(sum(details_sec))
                            if netcash and re.search(r"increase|decrease|movement", r.label, re.I):
                                hyps.append(sum(netcash))
                            if hyps and not any(abs(v - h) < 0.6 for h in hyps) and not self._explained(rows, r, ci, v):
                                exp = hyps[0] if pending else (sum(totals_sec) if totals_sec else hyps[0])
                                self._cast(p, r, names[ci] if ci < len(names) else "", v, exp, "cast")
                            last_total = v
                            totals_sec.append(v)
                            pending = []
                            if re.match(r"^net cash", r.label, re.I):
                                netcash.append(v)
                        else:
                            pending.append(v)
                            details_sec.append(v)

    @staticmethod
    def _explained(rows: list, r: Row, ci: int, v: float) -> bool:
        """True when the printed figure is the sum of SOME sensible group of the figures above it in the same
        column (a contiguous run of lines, or a combination of up to 4 sub-totals). The heuristic grouping
        above can pick the wrong components; a total that genuinely casts is never reported."""
        from itertools import combinations
        idx = next((i for i, x in enumerate(rows) if x is r), len(rows))
        prev = [x for x in rows[:idx] if not x.is_heading and ci < len(x.values) and x.values[ci] is not None]
        vals = [x.values[ci] for x in prev]
        for i in range(len(vals)):
            run = 0.0
            for j in range(i, len(vals)):
                run += vals[j]
                if j > i and abs(run - v) < 0.6:
                    return True
                if j > i and abs(vals[i] - (run - vals[i]) - v) < 0.6:   # first line less the rest
                    return True
        tots = [x.values[ci] for x in prev if (ci < len(x.line_above) and x.line_above[ci])
                or re.match(r"^total\b", x.label or "", re.I)][-12:]
        for k in (2, 3, 4):
            for c in combinations(tots, k):
                if abs(sum(c) - v) < 0.6:
                    return True
        return False

    def _cast(self, p: Page, r: Row, col: str, printed: float, exp: float, how: str):
        nn = note_of(self.heads, p, r.top) if p.kind == "notes" else None
        loc = f"{p.ref} {kind_label(p) or ('Note ' + str(nn) if nn else 'notes')}".strip()
        lab = r.label or "total line"
        self.facts.arithmetic.append({"type": how, "page": p.ref, "label": lab, "column": col,
                                      "printed": printed, "recomputed": exp, "difference": printed - exp})
        self.add(9, f"{loc}: \"{_q(lab, 50)}\" ({col}) printed {fmt_amt(printed)}, {'cross-cast of the row' if how == 'cross-cast' else 'components'} add to {fmt_amt(exp)} – difference {fmt_amt(printed - exp)} → correct the total or its components.", rule=how)

    # ---------------- point 10 ----------------
    def p10_links(self):
        doc = self.doc
        mains = self.mains
        notes_rows = []
        for p in doc.by_kind("notes"):
            for r in p.rows:
                if not r.is_heading:
                    notes_rows.append((note_of(self.heads, p, r.top), p, r))
        for k in ("sofp", "pl", "cfs"):
            for r in rows_of(doc, k):
                if r.is_heading:
                    continue
                pg = doc.page(r.page)
                if r.note_ref:
                    try:
                        n = int(re.split(r"[.&,]", r.note_ref)[0])
                    except ValueError:
                        continue
                    if mains and n not in mains:
                        self.add(10, f"{pg.ref} {kind_label(pg)}: \"{_q(r.label, 50)}\" refers to Note {r.note_ref}, which does not exist → correct the note reference.", rule="ref missing note")
                        continue
                    h = mains.get(n)
                    if h:
                        better = max(mains.values(), key=lambda x: _sim(x["title"], r.label))
                        if _sim(h["title"], r.label) < 0.45 and _sim(better["title"], r.label) > 0.8 and better["num"] != n:
                            self.add(10, f"{pg.ref} {kind_label(pg)}: \"{_q(r.label, 50)}\" refers to Note {n} (\"{_q(h['title'], 40)}\") but the relevant note is Note {better['num']} (\"{_q(better['title'], 40)}\") → correct the reference.", rule="wrong ref")
                        # face vs note figures
                        nr = [x for (nn, _, x) in notes_rows if nn == n]
                        cy = r.values[0]
                        if nr and cy is not None and cy != 0:
                            match = any(any(v is not None and abs(abs(v) - abs(cy)) < 0.5 for v in x.values) for x in nr)
                            if not match:   # net of two note lines, e.g. provision for the year less reversal
                                col0 = [x.values[0] for x in nr if x.values and x.values[0] is not None]
                                match = any(abs(abs(a_ + b_) - abs(cy)) < 0.5
                                            for i_, a_ in enumerate(col0) for b_ in col0[i_ + 1:])
                            if not match:
                                txt = "\n".join(pp.text for pp in {id(p_): p_ for (nn, p_, _) in notes_rows if nn == n}.values())
                                match = fmt_amt(abs(cy)).strip("()") in txt
                            if not match:
                                tots = [x for x in nr if any(x.line_above) or not x.label or re.match(r"^total", x.label, re.I)]
                                if tots:
                                    t = tots[-1]
                                    self.add(10, f"{pg.ref} {kind_label(pg)} \"{_q(r.label, 45)}\" {fmt_amt(cy)} does not agree to Note {n} total {fmt_amt(t.values[0])} ({doc.page(t.page).ref}) → reconcile.", rule="face vs note")
                                    self.facts.arithmetic.append({"type": "link", "a": f"{pg.ref} {r.label}", "a_value": cy,
                                                                  "b": f"Note {n} total", "b_value": t.values[0]})
                elif k == "sofp" and mains and not any(r.line_above) and not re.match(r"^total", r.label, re.I):
                    for h in mains.values():
                        if _sim(h["title"], r.label) > 0.85 or (len(_norm(r.label)) > 6 and _norm(r.label) == _norm(h["title"])):
                            self.add(10, f"{pg.ref} SOFP: \"{_q(r.label, 50)}\" has no note reference although Note {h['num']} (\"{_q(h['title'], 40)}\") covers it → add note reference {h['num']}.", rule="no ref")
                            break
                    else:
                        if re.search(r"share premium|contribution from (the )?shareholder|cash and cash equivalents|statutory reserve", r.label, re.I):
                            pass
        # net profit across statements
        pl = rows_of(doc, "pl")
        pr = (find_row(pl, r"^(net\s+)?(profit|loss|\(loss\)/profit|profit/\(loss\))[^,]*for the (year|period)(?!.*before)", last=True)
              or find_row(pl, r"total comprehensive", last=True))
        soce = rows_of(doc, "soce")
        cfs = rows_of(doc, "cfs")
        if pr and pr.values[0] is not None:
            cf = find_row(cfs, r"(profit|loss)")
            if cf and cf.values[0] is not None and abs(cf.values[0] - pr.values[0]) >= 0.5:
                self._link(f"{doc.page(pr.page).ref} P&L \"{pr.label}\"", pr.values[0], f"{doc.page(cf.page).ref} CFS \"{cf.label}\"", cf.values[0])
            if cf and len(pr.values) > 1 and len(cf.values) > 1 and pr.values[1] is not None and cf.values[1] is not None and abs(cf.values[1] - pr.values[1]) >= 0.5:
                self._link(f"{doc.page(pr.page).ref} P&L \"{pr.label}\" (PY)", pr.values[1], f"{doc.page(cf.page).ref} CFS (PY)", cf.values[1])
            sp = [r for r in soce if not r.is_heading and re.search(r"(profit|loss)", r.label, re.I) and not re.match(r"^balance", r.label, re.I)]
            if sp:
                s_cy = sp[-1].values[-1]
                if s_cy is not None and abs(s_cy - pr.values[0]) >= 0.5:
                    self._link(f"{doc.page(pr.page).ref} P&L \"{pr.label}\"", pr.values[0], f"{doc.page(sp[-1].page).ref} SOCE \"{sp[-1].label}\"", s_cy)
                if len(sp) >= 2 and len(pr.values) > 1 and pr.values[1] is not None and sp[-2].values[-1] is not None and abs(sp[-2].values[-1] - pr.values[1]) >= 0.5:
                    self._link(f"{doc.page(pr.page).ref} P&L PY profit", pr.values[1], f"{doc.page(sp[-2].page).ref} SOCE PY \"{sp[-2].label}\"", sp[-2].values[-1])
        # closing cash
        sofp = rows_of(doc, "sofp")
        cc = find_row(cfs, r"cash and cash equivalents.*(end|closing)|(end|close) of the (year|period)")
        sc = find_row(sofp, r"^(cash and cash equivalents|cash (and|at) bank|bank balances?|cash in hand and at bank)")
        if cc and sc:
            for i in range(min(len(cc.values), len(sc.values))):
                a, b = cc.values[i], sc.values[i]
                if a is not None and b is not None and abs(a - b) >= 0.5:
                    self._link(f"{doc.page(cc.page).ref} CFS closing cash", a, f"{doc.page(sc.page).ref} SOFP \"{sc.label}\"", b, i)
        # equity components SOFP vs SOCE closing balance
        bal = [r for r in soce if not r.is_heading and re.match(r"^(balance|as at|at )", r.label, re.I)]
        if bal and soce:
            names = col_names(doc, bal[-1])
            for r in sofp:
                if r.is_heading or r.values[0] is None:
                    continue
                for ci, nm in enumerate(names):
                    if ci >= len(bal[-1].values):
                        break
                    if nm and (_sim(nm, r.label) > 0.85 or (_norm(nm) == "total" and _norm(r.label) in ("totalequity", "totalshareholdersequity", "netassets"))):
                        v = bal[-1].values[ci]
                        if v is not None and abs(v - r.values[0]) >= 0.5:
                            self._link(f"{doc.page(r.page).ref} SOFP \"{r.label}\"", r.values[0], f"{doc.page(bal[-1].page).ref} SOCE closing \"{nm}\"", v)
                        if len(bal) >= 2 and len(r.values) > 1 and r.values[1] is not None:
                            v2 = bal[-2].values[ci]
                            if v2 is not None and abs(v2 - r.values[1]) >= 0.5:
                                self._link(f"{doc.page(r.page).ref} SOFP \"{r.label}\" (PY)", r.values[1], f"{doc.page(bal[-2].page).ref} SOCE \"{nm}\" (PY)", v2)

    def _link(self, a: str, av: float, b: str, bv: float, col: int = 0):
        self.facts.arithmetic.append({"type": "link", "a": a, "a_value": av, "b": b, "b_value": bv})
        self.add(10, f"{a} {fmt_amt(av)} does not agree to {b} {fmt_amt(bv)} (difference {fmt_amt(av - bv)}) → reconcile.", rule="link")

    # ---------------- point 12 ----------------
    def p12_format(self):
        doc = self.doc
        # coloured text
        for p in doc.pages:
            for ln in p.lines:
                cw = [w for w in ln.words if is_coloured(w.color)]
                if cw and sum(len(w.text) for w in cw) >= 2:
                    r, g, b = _rgb(cw[0].color)
                    cname = "red" if r > 0.6 and g < 0.4 and b < 0.4 else "blue" if b > 0.6 and r < 0.4 else "green" if g > 0.5 and r < 0.4 and b < 0.5 else "coloured"
                    self.add(12, f"{p.ref}: \"{_q(' '.join(w.text for w in cw), 60)}\" printed in {cname} → change to black.", rule="colour")
        # caption capitalisation
        forms = defaultdict(lambda: defaultdict(set))
        for k in STATEMENT_KINDS:
            for p in doc.by_kind(k):
                for r in p.rows:
                    if r.label and not r.label.isupper() and 2 <= len(r.label.split()) <= 8:
                        lab = re.sub(r"\s*\(.*?\)\s*", " ", r.label).strip()
                        forms[lab.lower()][lab].add(f"{p.ref} {kind_label(p)}")
                for h in p.headers:
                    for (lb, _, _) in h.get("labels", []):
                        if not lb.isupper() and 2 <= len(lb.split()) <= 6:
                            forms[lb.lower()][lb].add(f"{p.ref} {kind_label(p)}")
        for low, vs in forms.items():
            if len(vs) > 1:
                parts = "; ".join(f"\"{v}\" ({', '.join(sorted(r)[:4])})" for v, r in vs.items())
                major = max(vs, key=lambda v: len(vs[v]))
                self.add(12, f"Caption capitalisation inconsistent: {parts} → use \"{major}\" consistently.", rule="caption case")
        # numbering style
        sub_dot = defaultdict(list)
        main_dot = defaultdict(list)
        for h in self.heads:
            (sub_dot if h["sub"] is not None else main_dot)[bool(h["dot"])].append(h)
        for dd, lab in ((sub_dot, "sub-note"), (main_dot, "note")):
            if len(dd) == 2:
                minority = min(dd, key=lambda k: len(dd[k]))
                ex = dd[minority][0]
                maj = dd[not minority][0]
                self.add(12, f"Inconsistent {lab} numbering style: \"{_q(ex['text'], 40)}\" ({ex['page'].ref}) vs \"{_q(maj['text'], 40)}\" ({maj['page'].ref}) → use one style.", rule="numbering style")
        # AR spacing
        for p in doc.by_kind("ar"):
            lines = [l for l in p.lines if p.height * 0.05 < l.top < p.height * 0.92]
            if len(lines) < 6:
                continue
            gaps = [(lines[i].top - lines[i - 1].top, i) for i in range(1, len(lines))]
            base = sorted(g for g, _ in gaps)[len(gaps) // 3]
            para = [(g, i) for g, i in gaps if g > base * 1.45]
            if len(para) >= 3:
                pg = sorted(g for g, _ in para)
                med = pg[len(pg) // 2]
                for g, i in para:
                    if g > med * 1.8 and g - med > 10:
                        self.add(12, f"{p.ref}: uneven blank spacing between \"{_q(lines[i - 1].text, 45)}\" and \"{_q(lines[i].text, 35)}\" → make paragraph spacing uniform.", rule="AR spacing")

    # ---------------- point 13 ----------------
    def p13_cfs_noncash(self):
        doc = self.doc
        cfs = [r for r in rows_of(doc, "cfs") if not r.is_heading]
        if not cfs:
            return
        alltext = "\n".join(p.text for p in doc.pages if p.kind in ("pl", "notes", "sofp"))
        has = lambda rx: any(re.search(rx, r.label, re.I) for r in cfs)
        if re.search(r"\bdepreciation\b", alltext, re.I) and any(re.search(r"property|equipment|right[- ]of[- ]use", r.label, re.I) for r in rows_of(doc, "sofp")) and not has(r"depreciation"):
            self.add(13, "CFS: depreciation is not added back in operating activities although the FS show depreciation → add back depreciation.", rule="dep add-back")
        if any(re.search(r"end[- ]of[- ]service", r.label, re.I) for r in rows_of(doc, "sofp")) and not has(r"end[- ]of[- ]service|gratuity"):
            self.add(13, "CFS: provision for employees' end-of-service benefits is not added back / paid shown → add the non-cash provision and payments.", rule="eosb add-back")

    # ---------------- point 16 ----------------
    def p16_company_term(self):
        doc = self.doc
        terms = defaultdict(list)
        lower = []
        for p in doc.pages:
            for ln in p.lines:
                for m in re.finditer(r"\b(the|The)\s+(Company|company|Establishment|establishment|COMPANY|ESTABLISHMENT)\b", ln.text):
                    w = m.group(2)
                    terms[w.lower()].append(p.ref)
                    if w[0].islower():
                        lower.append((p, ln, m.group(0)))
        if terms.get("company") and terms.get("establishment"):
            minority = min(terms, key=lambda k: len(terms[k]))
            major = "Company" if minority == "establishment" else "Establishment"
            self.add(16, f"\"{minority.capitalize()}\" used on {', '.join(sorted(set(terms[minority]))[:8])} while \"{major}\" is used elsewhere → use \"{major}\" consistently.", rule="term")
        cap = sum(1 for p in doc.pages for ln in p.lines for _ in re.finditer(r"\b(the|The)\s+(Company|Establishment)\b", ln.text))
        if cap and lower:
            seen = set()
            for p, ln, t in lower:
                key = (p.n, t)
                if key in seen:
                    continue
                seen.add(key)
                self.add(16, f"{p.ref}: \"{_q(ln.text, 70)}\" – \"{t}\" in lower case → \"{t.split()[0]} {t.split()[1].capitalize()}\".", rule="term case")

    # ---------------- point 17 ----------------
    def p17_cfs_captions(self):
        doc = self.doc
        for p in doc.by_kind("cfs"):
            for r in p.rows:
                if r.is_heading:
                    continue
                vals = [v for v in r.values if v is not None and v != 0]
                if not vals:
                    continue
                same = all(v > 0 for v in vals) or all(v < 0 for v in vals)
                if re.search(r"\(\s*decrease\s*\)\s*/\s*increase|\(\s*increase\s*\)\s*/\s*decrease|increase\s*/\s*\(\s*decrease\s*\)|decrease\s*/\s*\(?\s*increase", r.label, re.I) and same:
                    word = "increase" if vals[0] > 0 else "decrease"
                    fixed = re.sub(r"\(?\s*(decrease|increase)\s*\)?\s*/\s*\(?\s*(decrease|increase)\)?", word, r.label, flags=re.I)
                    self.add(17, f"{p.ref} CFS: \"{r.label}\" – movement is {'an' if word == 'increase' else 'a'} {word} in {'every column shown' if len(vals) > 1 else 'the period'} → \"{fixed}\".", rule="combined caption")
                    continue
                combined = re.search(r"(generated from|from)\s*/\s*\(?used in\)?|\(?used in\)?\s*/\s*(generated from|from)", r.label, re.I)
                if combined and same:
                    word = "generated from" if vals[0] > 0 else "used in"
                    self.add(17, f"{p.ref} CFS: \"{r.label}\" – same sign in every column → use \"{word}\" only.", rule="combined used/generated")
                    continue
                if re.search(r"\bused in\b", r.label, re.I) and not combined and all(v > 0 for v in vals):
                    self.add(17, f"{p.ref} CFS: \"{r.label}\" shows a net inflow ({', '.join(fmt_amt(v) for v in vals)}) → \"generated from\".", rule="used in")
                elif re.search(r"\b(generated from|from)\b", r.label, re.I) and re.match(r"^net cash", r.label, re.I) and not combined and all(v < 0 for v in vals):
                    self.add(17, f"{p.ref} CFS: \"{r.label}\" shows a net outflow ({', '.join(fmt_amt(v) for v in vals)}) → \"used in\".", rule="generated from")

    # ---------------- point 18 ----------------
    TYPICAL = [
        (r"International Standard on Auditing \(ISAs?\)", "\"International Standards on Auditing (ISAs)\""),
        (r"\bcomprises? of\b", "\"comprise\" (e.g. \"comprise the statement of financial position\")"),
        (r"\brelated disclosure\b(?!s)", "\"related disclosures\""),
        (r"\binvestments activities\b", "\"investment activities\""),
        (r"\bA summary of [^.]{0,80}? are\b", "\"… is\""),
        (r"\bcertain financial instrument\b(?!s)", "\"certain financial instruments\""),
        (r"\bIncome or loss [^.]{0,80}? are recogni[sz]ed\b", "\"… is recognised\""),
        (r"\bRevision to accounting estimates are\b", "\"Revisions to accounting estimates are\""),
        (r"\bits characteristics\b", "\"their characteristics\""),
        (r"\bfunding [^.]{0,60}? are arranged\b", "\"… is arranged\""),
        (r"\bor/and\b", "\"and/or\""),
    ]

    def p18_spelling(self):
        doc = self.doc
        for p in doc.pages:
            # join lines so phrases wrapping lines are caught; track refs per page
            txt = re.sub(r"\s+", " ", p.text)
            for rx, fix in self.TYPICAL:
                for m in re.finditer(rx, txt, re.I):
                    self.add(18, f"{p.ref}: \"{_q(m.group(0), 70)}\" → {fix}.", rule="typical")
            for m in re.finditer(r"\b([A-Za-z]{3,})\((?=[A-Z]{2,})", txt):
                self.add(18, f"{p.ref}: missing space in \"{_q(txt[m.start():m.end() + 6], 30)}\" → \"{m.group(1)} (\".", rule="space")
            for ln in p.lines:
                for ph in ln.phrases(14):
                    pt = " ".join(w.text for w in ph)
                    for m in re.finditer(r"\b([A-Za-z]{2,})\s+\1\b", pt, re.I):
                        if m.group(1).lower() in ("that", "had") or CURRENCY_CODE.match(m.group(1)):
                            continue
                        self.add(18, f"{p.ref}: repeated word \"{m.group(0)}\" → \"{m.group(1)}\".", rule="repeat")
            for m in re.finditer(r"SHAREHOLDER['’]S\b", txt):
                plural = re.search(r"\bshareholders\b", "\n".join(x.text for x in doc.pages), re.I)
                if plural:
                    self.add(18, f"{p.ref}: \"{m.group(0)}\" while there are several shareholders → \"SHAREHOLDERS'\".", rule="shareholders")
                else:
                    self.add(18, f"Query – {p.ref}: \"{m.group(0)}\" – if there is more than one shareholder → \"SHAREHOLDERS'\".", "Query", rule="shareholders")
        # AR statement titles vs page titles
        ar_txt = re.sub(r"\s+", " ", " ".join(p.text for p in doc.by_kind("ar")))
        titles = {}
        for k in STATEMENT_KINDS:
            pg = doc.first(k)
            if pg and pg.title:
                titles[k] = re.sub(r"\s+", " ", pg.title).strip()
        rx = re.compile(r"statements? of (?:financial position|profit or loss(?: and other comprehensive income)?|comprehensive income|changes in (?:shareholders?['’]?\s*|owners?['’]?\s*)?equity|cash flows?)", re.I)
        seen = set()
        for m in rx.finditer(ar_txt):
            ph = m.group(0)
            low = ph.lower()
            k = "sofp" if "position" in low else "cfs" if "cash" in low else "soce" if "equity" in low else "pl"
            t = titles.get(k)
            if not t:
                continue
            tl = re.sub(r"\s+", " ", t.lower())
            tl = re.sub(r"\s+(for the|as at|as of).*$", "", tl)
            if low.rstrip("s") != tl.rstrip("s") or (low.endswith("s") != tl.endswith("s") and "cash flow" in tl):
                if low != tl and (ph.lower(), tl) not in seen:
                    seen.add((ph.lower(), tl))
                    pg = doc.first(k)
                    self.add(18, f"AR: \"{ph}\" does not match the page title \"{t}\" ({pg.ref}) → change the AR wording to \"{t.lower() if ph[0].islower() else t.title()}\".", rule="AR titles")
        # framework name AR vs basis note
        fw = re.compile(r"International Financial Reporting Standards(?: for Small and Medium[- ]sized Entities)?(?:\s*\((?:IFRS[^)]{0,40})\))?|IFRS for SMEs|IFRS Accounting Standards", re.I)
        ar_fw = [m.group(0) for m in fw.finditer(ar_txt)]
        nt = re.sub(r"\s+", " ", " ".join(p.text for p in doc.by_kind("notes")))
        nt_fw = [m.group(0) for m in fw.finditer(nt)]
        if ar_fw and nt_fw:
            a, b = ar_fw[0], nt_fw[0]
            if re.sub(r"\s+", " ", a).lower() != re.sub(r"\s+", " ", b).lower():
                self.add(18, f"Framework name differs: AR \"{a}\" vs basis of preparation note \"{b}\" → use identical wording.", rule="framework")

    # ---------------- point 19 ----------------
    def p19_related(self):
        doc = self.doc
        rp_rx = r"related part|due (to|from)|shareholders?['’]?\s*(current )?account|director['’]?s?\s*(current )?account|partners?['’]? current account|amount due"
        sofp_rp = [r for r in rows_of(doc, "sofp") if not r.is_heading and re.search(rp_rx, r.label, re.I)]
        section = None
        cfs_rp = []
        for r in rows_of(doc, "cfs"):
            if re.search(r"operating activit", r.label, re.I):
                section = "operating"
            elif re.search(r"investing activit", r.label, re.I):
                section = "investing" if r.is_heading or not re.match(r"^net", r.label, re.I) else section
            elif re.search(r"financing activit", r.label, re.I):
                section = "financing" if r.is_heading or not re.match(r"^net", r.label, re.I) else section
            if not r.is_heading and re.search(rp_rx, r.label, re.I):
                cfs_rp.append((section, r))
        nonzero = [r for r in sofp_rp if any(v for v in r.values if v)]
        self.facts.has_related = bool(nonzero or cfs_rp)
        for sec, r in cfs_rp:
            if sec == "operating":
                self.add(19, f"Query – {doc.page(r.page).ref} CFS: \"{r.label}\" shown under operating activities → if the balance relates to a non-operating item (e.g. funding by shareholder/related party), present it under financing/investing activities.", "Query", rule="rp operating")
        if nonzero and not cfs_rp and doc.by_kind("cfs"):
            labs = ", ".join(f"\"{r.label}\"" for r in nonzero[:3])
            self.add(19, f"Query – SOFP shows {labs} but the CFS shows no related-party movement → confirm the movement and present it under investing/financing if non-operating.", "Query", rule="rp missing cfs")

# --------------------------------------------------------------------------
# Page images (for the AI visual checks)
# --------------------------------------------------------------------------

def render_pages_png(path: str, dpi: int = 80, max_pages: int = 100) -> list:
    """Render each page at `dpi` (skill: pdftoppm -r 80) -> list of base64 PNG strings."""
    import pypdfium2 as pdfium
    out = []
    pdf = pdfium.PdfDocument(path)
    try:
        for i in range(min(len(pdf), max_pages)):
            page = pdf[i]
            img = page.render(scale=dpi / 72.0).to_pil()
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG", optimize=True)
            out.append(base64.b64encode(buf.getvalue()).decode())
            page.close()
    finally:
        pdf.close()
    return out


# --------------------------------------------------------------------------
# AI providers
# --------------------------------------------------------------------------

class AIError(Exception):
    pass


def _http_error_text(r) -> str:
    try:
        j = r.json()
        if isinstance(j, dict):
            e = j.get("error", j)
            if isinstance(e, dict):
                return str(e.get("message") or e)
            return str(e)
    except Exception:
        pass
    return (r.text or "")[:500]


class Cancelled(Exception):
    pass


class AIFatal(AIError):
    """Errors that retrying or splitting the work cannot fix (bad key, unknown model)."""
    pass


def _check_cancel(cfg: dict):
    ev = cfg.get("_cancel")
    if ev is not None and ev.is_set():
        raise Cancelled("Review stopped by user.")


def _sse_events(r, cfg: dict):
    """Yield the JSON payload of each server-sent 'data:' line; checks for Stop between lines."""
    r.encoding = "utf-8"
    reg = cfg.get("_open")
    if reg is not None:
        reg.add(r)              # lets Stop close the connection even while the server is silent
    for raw in r.iter_lines(chunk_size=128, decode_unicode=True):
        _check_cancel(cfg)
        if not raw or not raw.startswith("data:"):
            continue
        d = raw[5:].strip()
        if d == "[DONE]":
            break
        try:
            yield json.loads(d)
        except ValueError:
            continue


_DBG_LOCK = threading.Lock()


def ai_debug_path() -> Path:
    return app_data_dir() / "ai_debug.log"


def _ai_debug(line: str):
    """Technical log of every AI request (timings, sizes, finish reason) – never contains keys or document text."""
    try:
        with _DBG_LOCK:
            p = ai_debug_path()
            if p.exists() and p.stat().st_size > 2_000_000:
                p.replace(p.with_suffix(".old.log"))
            with p.open("a", encoding="utf-8") as f:
                f.write(f"[{_dt.datetime.now():%Y-%m-%d %H:%M:%S}] {line}\n")
    except Exception:
        pass


class RequestLimiter:
    """Shared gate for parallel AI requests. Shrinks automatically when the provider reports that
    the account allows fewer simultaneous requests (e.g. Kimi entry tier: 1 at a time)."""

    def __init__(self, limit: int):
        self.limit = max(1, int(limit))
        self.active = 0
        self.cv = threading.Condition()

    def acquire(self, cfg: dict):
        with self.cv:
            while self.active >= self.limit:
                self.cv.wait(0.5)
                _check_cancel(cfg)
            self.active += 1

    def release(self):
        with self.cv:
            self.active = max(0, self.active - 1)
            self.cv.notify_all()

    def shrink(self, n: Optional[int] = None) -> bool:
        with self.cv:
            new = max(1, n if n else self.limit - 1)
            if new < self.limit:
                self.limit = new
                return True
            return False


# Output-token ceilings learned from provider errors, per (provider, base URL, model) – avoids repeating the error.
_MT_CAP: dict = {}
_MT_LOCK = threading.Lock()

# Seconds of silence allowed while streaming before the request is treated as stalled.
STREAM_IDLE_TIMEOUT = 300


def call_llm(cfg: dict, system: str, parts: list, max_tokens: Optional[int] = None,
             want_json: bool = True, log: Callable = print, allow_images: bool = True,
             fast: bool = False) -> str:
    """parts: [{"type": "text", "text": ...} | {"type": "image", "data": b64png}]
    All providers are called in streaming mode so the UI can show live progress and the user can stop.
    fast=True switches reasoning/thinking off (or to low) for mechanical work such as transcription."""
    import requests
    import time
    provider = cfg["provider"]
    model = cfg["model"].strip()
    key = cfg["key"]
    base = (cfg.get("base_url") or PROVIDERS[provider]["base_url"]).rstrip("/")
    mt = int(max_tokens or cfg.get("max_tokens") or 32000)
    if not model:
        raise AIError("No model name set for the selected AI provider (Settings).")
    if provider == "custom" and not base:
        raise AIError("No base URL set for the custom provider (Settings).")
    tick = cfg.get("_tick") or (lambda *_: None)
    timeout = (30, STREAM_IDLE_TIMEOUT)
    cap_key = (provider, base, model)
    mt = min(mt, _MT_CAP.get(cap_key, mt))
    m = model.lower()
    use_temp = provider != "kimi"          # Kimi K2.x / K3 fix the temperature themselves
    use_fast = fast or cfg.get("reasoning") == "low"
    use_images = allow_images and any(p["type"] == "image" for p in parts)
    last = [0.0]

    stats = {}
    beat = [time.time()]

    def report(answer_chars: int, think_chars: int):
        now = time.time()
        if not stats.get("first"):
            stats["first"] = now
        stats["answer"], stats["think"] = answer_chars, think_chars
        if now - last[0] >= 1.0:
            last[0] = now
            tick(f"receiving answer · {answer_chars:,} chars" if answer_chars
                 else f"AI is thinking · {think_chars:,} chars" if think_chars else "waiting for AI …")
        if now - beat[0] >= 60:
            beat[0] = now
            log(f"  … {label}: still working ({int(now - stats['t0'])}s) – "
                + (f"writing the answer, {answer_chars:,} chars so far" if answer_chars
                   else f"thinking, {think_chars:,} chars of reasoning so far" if think_chars else "no data yet"))

    label = PROVIDERS[provider]["label"]
    attempt = 0
    busy = conc = 0
    while True:
        attempt += 1
        _check_cancel(cfg)
        ps = [p for p in parts if use_images or p["type"] != "image"]
        lim = cfg.get("_limiter")
        if lim is not None:
            tick("waiting for a free AI slot …")
            lim.acquire(cfg)
        tick("sending request …")
        stats.clear()
        stats["t0"] = time.time()
        beat[0] = time.time()
        n_in = len(system) + sum(len(p_.get("text", "")) for p_ in ps)
        n_img = sum(1 for p_ in ps if p_["type"] == "image")
        try:
            try:
                if provider == "claude":
                    content = []
                    for p in ps:
                        if p["type"] == "text":
                            content.append({"type": "text", "text": p["text"]})
                        else:
                            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": p["data"]}})
                    body = {"model": model, "max_tokens": mt, "system": system, "stream": True,
                            "messages": [{"role": "user", "content": content}]}
                    if use_temp:
                        body["temperature"] = 0
                    r = requests.post(f"{base}/messages", json=body, stream=True, timeout=timeout,
                                      headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                               "content-type": "application/json"})
                    if r.status_code != 200:
                        raise _Http(r.status_code, _http_error_text(r))
                    text, stop, n, think = [], None, 0, 0
                    for ev in _sse_events(r, cfg):
                        t = ev.get("type")
                        if t == "content_block_delta":
                            d = ev.get("delta", {})
                            if d.get("type") == "text_delta":
                                text.append(d["text"]); n += len(d["text"])
                            elif d.get("type") == "thinking_delta":
                                think += len(d.get("thinking", ""))
                        elif t == "message_delta":
                            stop = ev.get("delta", {}).get("stop_reason") or stop
                        elif t == "error":
                            raise _Http(500, str(ev.get("error", {}).get("message", ev)))
                        report(n, think)
                    if stop == "max_tokens":
                        raise AIError("The AI response was cut off (max output tokens reached). Increase 'Max output tokens' in Settings.")
                    return "".join(text)
                if provider in ("openai", "kimi", "custom"):
                    content = []
                    for p in ps:
                        if p["type"] == "text":
                            content.append({"type": "text", "text": p["text"]})
                        else:
                            content.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + p["data"]}})
                    body = {"model": model, "stream": True,
                            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}
                    body["max_completion_tokens" if provider == "openai" else "max_tokens"] = mt
                    if use_temp:
                        body["temperature"] = 0
                    if want_json and provider == "openai":
                        body["response_format"] = {"type": "json_object"}
                    if use_fast:
                        if provider == "kimi" and m.startswith("kimi-k2"):
                            body["thinking"] = {"type": "disabled"}
                        elif provider == "kimi" and m.startswith("kimi-k3"):
                            body["reasoning_effort"] = "low"
                        elif provider == "openai" and re.match(r"^(gpt-[5-9]|o\d)", m):
                            body["reasoning_effort"] = "low"
                    r = requests.post(f"{base}/chat/completions", json=body, stream=True, timeout=timeout,
                                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
                    if r.status_code != 200:
                        raise _Http(r.status_code, _http_error_text(r))
                    text, finish, n, think = [], None, 0, 0
                    for ev in _sse_events(r, cfg):
                        if isinstance(ev, dict) and ev.get("error"):
                            e = ev["error"]
                            raise _Http(500, str(e.get("message", e) if isinstance(e, dict) else e))
                        for ch in ev.get("choices") or []:
                            d = ch.get("delta") or {}
                            rc = d.get("reasoning_content") or d.get("reasoning")
                            if isinstance(rc, str):
                                think += len(rc)
                            c = d.get("content")
                            if isinstance(c, list):
                                c = "".join(x.get("text", "") for x in c if isinstance(x, dict))
                            if c:
                                text.append(c); n += len(c)
                            finish = ch.get("finish_reason") or finish
                            if ch.get("usage"):
                                stats["usage"] = ch.get("usage")
                        if isinstance(ev, dict) and ev.get("usage"):
                            stats["usage"] = ev.get("usage")
                        stats["finish"] = finish
                        report(n, think)
                    if finish == "length":
                        if not n and think:
                            raise AIError(f"The AI used its whole output allowance ({mt:,} tokens) on reasoning and gave no "
                                          "answer. Set 'Reasoning' to 'Low – faster' in Settings (or raise 'Max output tokens').")
                        raise AIError("The AI response was cut off (max output tokens reached). Increase 'Max output tokens' in Settings.")
                    return "".join(text)
                if provider == "gemini":
                    gparts = []
                    for p in ps:
                        if p["type"] == "text":
                            gparts.append({"text": p["text"]})
                        else:
                            gparts.append({"inline_data": {"mime_type": "image/png", "data": p["data"]}})
                    gen = {"maxOutputTokens": mt}
                    if use_temp:
                        gen["temperature"] = 0
                    if want_json:
                        gen["responseMimeType"] = "application/json"
                    if use_fast:
                        if "gemini-3" in m:
                            gen["thinkingConfig"] = {"thinkingLevel": "low"}
                        elif "2.5" in m:
                            gen["thinkingConfig"] = {"thinkingBudget": 1024}
                    body = {"systemInstruction": {"parts": [{"text": system}]},
                            "contents": [{"role": "user", "parts": gparts}], "generationConfig": gen}
                    r = requests.post(f"{base}/models/{model}:streamGenerateContent?alt=sse", json=body, stream=True,
                                      timeout=timeout, headers={"x-goog-api-key": key, "Content-Type": "application/json"})
                    if r.status_code != 200:
                        raise _Http(r.status_code, _http_error_text(r))
                    text, finish, n, think, feedback = [], None, 0, 0, None
                    for ev in _sse_events(r, cfg):
                        if ev.get("error"):
                            e = ev["error"]
                            raise _Http(int(e.get("code", 500)) if isinstance(e, dict) else 500,
                                        str(e.get("message", e) if isinstance(e, dict) else e))
                        feedback = ev.get("promptFeedback") or feedback
                        for c in (ev.get("candidates") or [])[:1]:
                            for p in c.get("content", {}).get("parts", []) or []:
                                tx = p.get("text", "")
                                if p.get("thought"):
                                    think += len(tx)
                                elif tx:
                                    text.append(tx); n += len(tx)
                            finish = c.get("finishReason") or finish
                        report(n, think)
                    if not text and feedback and feedback.get("blockReason"):
                        raise AIError(f"Gemini returned no answer: {str(feedback)[:300]}")
                    if finish == "MAX_TOKENS":
                        raise AIError("The AI response was cut off (max output tokens reached). Increase 'Max output tokens' in Settings.")
                    return "".join(text)
                raise AIError(f"Unknown provider {provider}")
            finally:
                if lim is not None:
                    lim.release()
                ex_ = sys.exc_info()[1]
                t_ = time.time()
                first_ = (f"first data after {stats['first'] - stats['t0']:.0f}s" if stats.get("first")
                          else "no data received")
                _ai_debug(f"{provider}/{model} attempt {attempt}: ~{n_in // 4:,} text tokens + {n_img} images, "
                          f"max_tokens {mt:,}, reasoning {'low/off' if use_fast else 'default'} | {first_} | "
                          f"total {t_ - stats['t0']:.0f}s, reasoning {stats.get('think', 0):,} chars, answer "
                          f"{stats.get('answer', 0):,} chars, finish {stats.get('finish')}, usage {stats.get('usage')} | "
                          f"result {'OK' if ex_ is None else type(ex_).__name__ + ': ' + str(ex_)[:300]}")
        except _Http as e:
            msg = e.msg.lower()
            if e.code in (400, 422) and use_temp and "temperature" in msg:
                use_temp = False
                continue
            if e.code in (400, 422) and use_fast and re.search(r"thinking|reasoning", msg):
                use_fast = False
                continue
            if e.code in (400, 413, 422) and use_images and re.search(r"image|vision|multimodal|modalit|content type|image_url", msg):
                log("  ! The selected model does not accept page images – continuing with page text only.")
                use_images = False
                continue
            if e.code in (401, 403):
                raise AIFatal(f"The API key was rejected by {PROVIDERS[provider]['label']} ({e.code}): {e.msg[:200]}")
            if e.code == 404:
                raise AIFatal(f"Model or endpoint not found ({e.code}): {e.msg[:200]} – check the model name in Settings.")
            if e.code in (400, 422) and mt > 4096 and re.search(
                    r"max_tokens|max_completion_tokens|maxoutputtokens|max output|output tokens|token limit|context length", msg):
                lower = [int(x) for x in re.findall(r"\b(\d{4,7})\b", msg) if 1024 <= int(x) < mt]
                new = max(lower) if lower else max(4096, mt // 2)
                with _MT_LOCK:
                    known = _MT_CAP.get(cap_key)
                    if known is None or new < known:
                        _MT_CAP[cap_key] = new
                        log(f"  ! {label} · {model} accepts at most {new:,} output tokens – using that limit.")
                mt = min(new, _MT_CAP.get(cap_key, new))
                continue
            lim = cfg.get("_limiter")
            if e.code == 429 and "concurrency" in msg:
                # account-level limit on simultaneous requests: queue the parts instead of failing them
                mc = re.search(r"concurrency[^0-9]{0,20}(\d+)", msg)
                n = int(mc.group(1)) if mc else None
                if lim is not None and lim.shrink(n):
                    log(f"  ! Your {label} account allows {lim.limit} request(s) at a time – the remaining parts "
                        f"will be sent {'one by one' if lim.limit == 1 else f'{lim.limit} at a time'}.")
                conc += 1
                if conc <= 60:
                    tick("queued – account allows fewer parallel requests")
                    for _ in range(3):
                        _check_cancel(cfg)
                        time.sleep(1)
                    continue
            if e.code in (408, 429, 500, 502, 503, 504, 529) and busy < 8:
                busy += 1
                if e.code == 429 and lim is not None:
                    lim.shrink()
                wait = [10, 20, 30, 45, 60, 60, 60, 90][busy - 1]
                ma = re.search(r"after\s+(\d+)\s*sec", msg)
                if ma and e.code == 429:
                    wait = max(wait, int(ma.group(1)))
                log(f"  ! AI service busy ({e.code}{' – rate limit' if e.code == 429 else ''}) – retrying in {wait}s …"
                    + (f"\n    {label} said: {e.msg[:220]}" if busy == 1 else ""))
                tick(f"service busy – retrying in {wait}s")
                for _ in range(wait):
                    _check_cancel(cfg)
                    time.sleep(1)
                continue
            raise AIError(f"{label} error {e.code}: {e.msg[:300]}")
        except (AIError, Cancelled):
            raise
        except Exception as e:  # network / stalled stream
            _check_cancel(cfg)
            if attempt <= 2:
                what = "no data for 5 minutes" if "timeout" in type(e).__name__.lower() or "timed out" in str(e).lower() else type(e).__name__
                log(f"  ! Connection problem ({what}) – retrying …")
                for _ in range(10):
                    _check_cancel(cfg)
                    time.sleep(1)
                continue
            raise AIError(f"Could not reach {PROVIDERS[provider]['label']}: {e}")


class _Http(Exception):
    def __init__(self, code, msg):
        super().__init__(f"{code}: {msg}")
        self.code, self.msg = code, msg


def test_connection(cfg: dict) -> str:
    out = call_llm(cfg, "You are a connectivity test.", [{"type": "text", "text": "Reply with the single word OK."}],
                   max_tokens=64, want_json=False, log=lambda *_: None)
    return out.strip()[:60] or "(empty reply)"


def extract_json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    s, e = t.find("{"), t.rfind("}")
    if s < 0 or e < 0:
        raise ValueError("no JSON object in AI reply")
    blob = t[s:e + 1]
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        blob2 = re.sub(r",\s*([}\]])", r"\1", blob)
        return json.loads(blob2)


def ask_json(cfg, system, parts, log, allow_images=True, fast=False) -> dict:
    txt = call_llm(cfg, system, parts, log=log, allow_images=allow_images, fast=fast)
    try:
        return extract_json(txt)
    except Exception:
        log("  ! AI reply was not valid JSON – asking again …")
        parts2 = parts + [{"type": "text", "text": "IMPORTANT: your previous reply was not valid JSON. Return ONLY one valid JSON object, no prose, no code fences."}]
        txt = call_llm(cfg, system, parts2, log=log, allow_images=allow_images, fast=fast)
        return extract_json(txt)


# --------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------

def page_block(doc: Document, label: str, pages: Optional[list] = None) -> str:
    out = []
    for p in (doc.pages if pages is None else pages):
        out.append(f"===== {label} | PDF page {p.n} of {len(doc.pages)} | printed page: {p.printed or 'none'} | "
                   f"reference: {p.ref} | type: {KIND_LABELS.get(p.kind, p.kind)} | {p.orientation} =====")
        out.append(p.layout_text or "(no text)")
    return "\n".join(out)


STRUCTURE_SYSTEM = (
    "You transcribe the numeric tables of a set of financial statements into JSON for a Python program that "
    "recomputes every total. Do NOT add, subtract or judge anything yourself – copy figures exactly as printed. "
    "Return ONLY one JSON object."
)

STRUCTURE_INSTRUCTIONS = """Using the page texts above, return this JSON (no other text):
{
  "tables": [
    {"page": <PDF page number>, "name": "<SOFP | P&L | SOCE | CFS | Note N – title>",
     "columns": ["<column heading, e.g. 2025>", "..."],
     "rows": [{"id": "r1", "label": "<row caption exactly as printed>", "values": [<number or null>, ...]}],
     "sums": [{"total": "<row id>", "components": ["<row id>", "-<row id to subtract>", ...]}],
     "cross_sums": [{"total_column": <0-based index>, "component_columns": [<0-based indexes>]}]}
  ],
  "links": [
    {"description": "<what must agree, e.g. SOFP cash and cash equivalents vs CFS closing cash (CY)>",
     "a": {"page": <PDF page>, "label": "<caption>", "value": <number>},
     "b": {"page": <PDF page>, "label": "<caption>", "value": <number>}}
  ],
  "py_compare": [
    {"description": "<item>", "current": {"page": <PDF page of CURRENT FS>, "label": "<caption>", "value": <PY figure shown in the current FS>},
     "prior": {"page": <PDF page of PY FS>, "label": "<caption>", "value": <CY figure in the acknowledged PY FS>}}
  ]
}
Rules:
- Numbers: write as plain numbers without commas; bracketed amounts are negative; "-" or nil = 0; empty cell = null.
- "tables": include the SOFP, P&L, SOCE, CFS and every note table that has a subtotal or total. For every subtotal/total
  row add one entry in "sums" listing exactly the rows that make it up (use "-" prefix only when the printed figure must be
  subtracted although printed without brackets). For the SOCE (and any table with a Total column) add "cross_sums";
  also add "sums" for each closing balance row (= opening balance + movements).
- "links": every agreement required by checklist point 10 (face figure ↔ note total, net profit/loss across P&L, SOCE,
  CFS and SOFP reserves, equity components across SOCE/SOFP/CFS, closing cash across CFS/SOFP/financial-assets note,
  tax charge/provision between P&L, SOFP and tax note) and point 14 (financial instruments note ↔ SOFP), both years.
- "py_compare": only if an acknowledged PY FS is supplied and the current FS are not the first financial statements:
  every prior-year figure in the current FS (SOFP, P&L, SOCE, CFS, every note) paired with the same item in the
  current-year column of the PY FS. Otherwise return an empty list.
- Copy every value exactly as printed on the page you cite."""


REVIEW_SYSTEM_HEAD = """You are the reviewer executing the "FS Hard Copy Review" skill reproduced verbatim between the markers below. Follow it exactly – its ground rules, "Do not report" lists, precedence table, calibration example and findings-column rules.

=== SKILL START ===
{skill}
=== SKILL END ===

TOOL ADAPTATION (replaces only the skill's tool-specific steps):
- A desktop tool has already extracted the text of every page (given per page with the PDF page number, printed page number, the page reference to use and the page type), rendered every page of the current FS at 80 dpi (images attached in PDF page order, each preceded by its label), detected coloured text from the PDF colour data, recomputed all arithmetic in Python and run pattern rules.
- Do NOT perform arithmetic yourself. For point 9 and every number-based difference under points 2, 10 and 14 use only the PYTHON ARITHMETIC RESULTS, quoting the amounts given. Omit a listed difference only if the page text/image shows the table was misread. Do not report any other number-based difference.
- RULE CANDIDATES come from pattern rules and may include false positives. Verify each against the page text and images: keep valid ones (reword to the report style if needed and place them under the correct point per "Where each finding goes"), drop false positives and anything under "Do not report". Never duplicate a finding across points.
- Then carry out your own complete review of all 19 points (full reading of the AR and notes, judgment items, spelling and grammar, the visual checks on the images) and add every further valid finding.
- The tool builds the Word report itself: ignore the skill steps about pdftotext, pdftoppm, tesseract, docx-js, PDF rendering, SendUserFile and the chat reply.
- Page references: use the "reference" given in each page header (e.g. p4, AR p2 (PDF p4)).

Return ONLY one JSON object with this structure:
{{
  "client": "<company name exactly as on the cover, without M/s.>",
  "period": "<e.g. Year ended December 31, 2025>",
  "year": "<e.g. 2025>",
  "page_reference_note": "<the italic page-reference convention line>",
  "critical_points": ["<3-6 bullets: the most serious Exceptions and Queries>"],
  "points": [{{"sn": 1, "status": "<Exception|Query|OK|N/A|Not verifiable>", "findings": ["<one bullet per issue>"]}}, … all 19 points in order]
}}
Findings rules: OK -> ["No observations."]; N/A or Not verifiable -> one short line giving the reason; Exception/Query -> one bullet per issue quoting what was found, giving the page and stating the correction; prefix reviewer-confirmation items inside an Exception row with "Query – "."""


# --------------------------------------------------------------------------
# AI pass 1 – table transcription, split into small parallel requests
# --------------------------------------------------------------------------
# One request for the whole document produced a very long answer (tens of thousands of tokens):
# slow, and liable to be cut off at the output limit. The work is now split into parts of a few
# pages each, sent in parallel with reasoning switched off, and merged before the Python arithmetic.

PASS1_PAGES_PER_PART = 4

_NUM_RULES = """- Numbers: write as plain numbers without commas; bracketed amounts are negative; "-" or nil = 0; empty cell = null.
- Copy every value exactly as printed on the page you cite."""

TABLES_INSTRUCTIONS = """Transcribe the numeric tables that START on CURRENT FS PDF page(s) {pages} (other pages are context only).
Return this JSON (no other text):
{{
  "tables": [
    {{"page": <PDF page number where the table starts>, "name": "<SOFP | P&L | SOCE | CFS | Note N – title>",
     "columns": ["<column heading, e.g. 2025>", "..."],
     "rows": [{{"id": "r1", "label": "<row caption exactly as printed>", "values": [<number or null>, ...]}}],
     "sums": [{{"total": "<row id>", "components": ["<row id>", "-<row id to subtract>", ...]}}],
     "cross_sums": [{{"total_column": <0-based index>, "component_columns": [<0-based indexes>]}}]}}
  ]
}}
Rules:
- Include the SOFP, P&L, SOCE, CFS and every note table that has a subtotal or total. For every subtotal/total
  row add one entry in "sums" listing exactly the rows that make it up (use "-" prefix only when the printed figure must be
  subtracted although printed without brackets). For the SOCE (and any table with a Total column) add "cross_sums";
  also add "sums" for each closing balance row (= opening balance + movements).
- A table that starts on a listed page and continues on the next page: transcribe the whole table (including the
  continuation) as one table. Skip tables that started on a page not listed.
- If the listed pages have no numeric tables, return {{"tables": []}}.
""" + _NUM_RULES

LINKS_INSTRUCTIONS = """Using the CURRENT FS page texts above, list every agreement required by checklist point 10 (face figure ↔ note
total, net profit/loss across P&L, SOCE, CFS and SOFP reserves, equity components across SOCE/SOFP/CFS, closing cash
across CFS/SOFP/financial-assets note, tax charge/provision between P&L, SOFP and tax note) and point 14 (financial
instruments note ↔ SOFP), both years. Return this JSON (no other text):
{
  "links": [
    {"description": "<what must agree, e.g. SOFP cash and cash equivalents vs CFS closing cash (CY)>",
     "a": {"page": <PDF page>, "label": "<caption>", "value": <number>},
     "b": {"page": <PDF page>, "label": "<caption>", "value": <number>}}
  ]
}
Rules:
""" + _NUM_RULES

PYCMP_INSTRUCTIONS = """Every prior-year (comparative) figure printed on CURRENT FS PDF page(s) {pages} (SOFP, P&L, SOCE, CFS, notes)
must be paired with the same item in the current-year column of the acknowledged PY FS. Return this JSON (no other text):
{{
  "py_compare": [
    {{"description": "<item>", "current": {{"page": <PDF page of CURRENT FS>, "label": "<caption>", "value": <PY figure shown in the current FS>}},
     "prior": {{"page": <PDF page of PY FS>, "label": "<caption>", "value": <CY figure in the acknowledged PY FS>}}}}
  ]
}}
Rules:
- Only comparatives printed on the listed CURRENT FS pages. Skip items not found in the PY FS.
- If the listed pages carry no comparative figures, return {{"py_compare": []}}.
""" + _NUM_RULES


def _amount_count(p) -> int:
    return len(re.findall(r"\(?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?", p.layout_text or ""))


def table_pages(doc: Document) -> list:
    return [p for p in doc.pages if p.kind not in ("cover", "contents", "ar")
            and (p.kind in STATEMENT_KINDS or p.kind == "notes" or _amount_count(p) >= 3)]


def _pg_list(pages: list) -> str:
    ns = [p.n for p in pages]
    return f"{ns[0]}–{ns[-1]}" if len(ns) > 1 and ns == list(range(ns[0], ns[-1] + 1)) else ", ".join(map(str, ns))


def ai_transcribe(doc: Document, py: Optional[Document], F: Facts, cfg: dict, meta: str,
                  log: Callable, progress: Callable, prov: str) -> tuple:
    """Returns (struct, gaps) – struct as expected by python_arithmetic; gaps = {"tables"|"links"|"py": [page refs]}."""
    import concurrent.futures as cf
    import threading
    import time
    tps = table_pages(doc)
    parts_pages = [tps[i:i + PASS1_PAGES_PER_PART] for i in range(0, len(tps), PASS1_PAGES_PER_PART)]
    tasks = []   # (kind, pages, system, parts)
    for grp in parts_pages:
        ctx = list(grp)
        nxt = doc.page(grp[-1].n + 1)
        if nxt and nxt not in ctx:
            ctx.append(nxt)           # continuation of a table running over the page break
        tasks.append(("tables", grp, STRUCTURE_SYSTEM,
                      [{"type": "text", "text": meta}, {"type": "text", "text": page_block(doc, "CURRENT FS", ctx)},
                       {"type": "text", "text": TABLES_INSTRUCTIONS.format(pages=_pg_list(grp))}]))
    tasks.append(("links", tps, STRUCTURE_SYSTEM,
                  [{"type": "text", "text": meta}, {"type": "text", "text": page_block(doc, "CURRENT FS", tps)},
                   {"type": "text", "text": LINKS_INSTRUCTIONS}]))
    if py and not F.first_period:
        py_txt = page_block(py, "PY FS (acknowledged copy)", table_pages(py) or py.pages)
        for grp in parts_pages:
            tasks.append(("py", grp, STRUCTURE_SYSTEM,
                          [{"type": "text", "text": meta}, {"type": "text", "text": page_block(doc, "CURRENT FS", grp)},
                           {"type": "text", "text": py_txt},
                           {"type": "text", "text": PYCMP_INSTRUCTIONS.format(pages=_pg_list(grp))}]))
    total = len(tasks)
    workers = max(1, min(int(cfg.get("parallel") or 3), total))
    log(f"AI pass 1: {len(tps)} page(s) with figures → {total} request(s), {workers} at a time.")
    lock = threading.Lock()
    state = {"done": 0, "chars": {}}
    t0 = time.time()

    def show():
        with lock:
            d, ch = state["done"], sum(state["chars"].values())
        progress(25 + int(23 * d / total),
                 f"AI pass 1/2 – transcribing tables ({prov}) · {d} of {total} parts done"
                 + (f" · {ch:,} chars received" if ch else ""))

    limiter = RequestLimiter(workers)

    def run(i, task):
        kind, grp, system, parts = task
        c = dict(cfg, _limiter=limiter)

        def tick(s, i=i):
            mm = re.search(r"([\d,]+) chars", s)
            if mm and s.startswith("receiving"):
                with lock:
                    state["chars"][i] = int(mm.group(1).replace(",", ""))
            show()
        c["_tick"] = tick
        res = ask_json(c, system, parts, log, allow_images=False, fast=True)
        with lock:
            state["done"] += 1
        show()
        return res

    struct = {"tables": [], "links": [], "py_compare": []}
    gaps = {"tables": [], "links": [], "py": []}
    errors = []
    failed = []

    def merge(kind, r):
        key = {"tables": "tables", "links": "links", "py": "py_compare"}[kind]
        got = r.get(key) or []
        if isinstance(got, list):
            struct[key] += [x for x in got if isinstance(x, dict)]

    def where(task):
        kind, grp = task[0], task[1]
        return "cross-statement links" if kind == "links" else "pages " + ", ".join(p.ref for p in grp)
    show()
    ex = cf.ThreadPoolExecutor(max_workers=workers)
    try:
        futs = {ex.submit(run, i, t): (i, t) for i, t in enumerate(tasks)}
        for f in cf.as_completed(futs):
            i, task = futs[f]
            try:
                merge(task[0], f.result())
            except (Cancelled, AIFatal):
                raise
            except Exception as e:
                log(f"  ! AI pass 1 part failed ({task[0]}, {where(task)}): {e} – will retry it at the end.")
                failed.append((i, task))
        ex.shutdown(wait=True)
        if failed:
            limiter.shrink(1)
            log(f"Retrying {len(failed)} failed part(s) one at a time …")
            for i, task in failed:
                try:
                    merge(task[0], run(i, task))
                except (Cancelled, AIFatal):
                    raise
                except Exception as e:
                    errors.append(e)
                    log(f"  ! AI pass 1 part failed again ({task[0]}, {where(task)}): {e}")
                    gaps[task[0]] += ["all"] if task[0] == "links" else [p.ref for p in task[1]]
    except BaseException:
        ev = cfg.get("_cancel")
        if ev is not None:
            ev.set()          # stop the other running parts quickly
        ex.shutdown(wait=False, cancel_futures=True)
        raise
    if errors and len(errors) == total:
        raise errors[0] if isinstance(errors[0], AIError) else AIError(str(errors[0]))
    log(f"AI pass 1 done in {int(time.time() - t0)}s: {len(struct['tables'])} table(s), {len(struct['links'])} link(s), "
        f"{len(struct['py_compare'])} PY comparison(s).")
    return struct, gaps


def add_gap_queries(points: OrderedDict, gaps: dict):
    """Never let a failed transcription part pass silently: add a Query to the affected point."""
    def add(sn, text):
        st, fl = points[sn]
        fl = [x for x in fl if x != NO_OBS]
        if st == "Exception":
            fl.append("Query – " + text)
        else:
            st = "Query" if st in ("OK", "Query") else st
            fl = (fl if st == "Query" else []) + [text]
        points[sn] = (st, fl)
    if gaps.get("tables"):
        add(9, f"Casting of {', '.join(gaps['tables'])} could not be recomputed by the tool (AI transcription failed) – cast manually.")
    if gaps.get("links"):
        add(10, "Cross-statement links could not be recomputed by the tool (AI transcription failed) – agree manually.")
    if gaps.get("py"):
        add(2, f"Comparatives on {', '.join(gaps['py'])} could not be agreed to the PY FS by the tool (AI transcription failed) – agree manually.")


# --------------------------------------------------------------------------
# Python arithmetic over the AI-transcribed structure
# --------------------------------------------------------------------------

def page_number_set(doc: Document) -> dict:
    d = {}
    for p in doc.pages:
        s = set()
        for ln in p.lines:
            for w in ln.words:
                v = parse_amount(w.text)
                if v is not None:
                    s.add(round(abs(v), 2))
        d[p.n] = s
    return d


def _num(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return parse_amount(str(v).strip())
    except Exception:
        return None


def python_arithmetic(struct: dict, doc: Document, py: Optional[Document], log: Callable) -> list:
    nums = page_number_set(doc)
    pynums = page_number_set(py) if py else {}
    results = []
    unverified = 0

    def ok_on(page, v, numset):
        if v is None or abs(v) < 0.5:
            return True
        return round(abs(v), 2) in numset.get(page, set())

    def pref(d: Document, n) -> str:
        try:
            pg = d.page(int(n))
            return pg.ref if pg else f"PDF p{n}"
        except Exception:
            return f"PDF p{n}"

    for t in struct.get("tables", []) or []:
        try:
            page = int(t.get("page"))
        except Exception:
            continue
        rows = {r.get("id"): r for r in t.get("rows", []) if isinstance(r, dict)}
        cols = t.get("columns") or []
        name = t.get("name", "")
        for r in rows.values():
            r["_v"] = [_num(x) for x in (r.get("values") or [])]
        bad = {rid for rid, r in rows.items()
               if not all(ok_on(page, v, nums) or ok_on(page + 1, v, nums) for v in r["_v"])}
        unverified += len(bad)
        for s in t.get("sums", []) or []:
            tot = rows.get(s.get("total"))
            comps = s.get("components") or []
            if not tot or s.get("total") in bad:
                continue
            ids = [(c[1:], -1) if str(c).startswith("-") else (c, 1) for c in comps]
            if any(i not in rows or i in bad for i, _ in ids):
                continue
            for ci in range(len(tot["_v"])):
                tv = tot["_v"][ci]
                if tv is None:
                    continue
                vals = [rows[i]["_v"][ci] if ci < len(rows[i]["_v"]) else None for i, _ in ids]
                if all(v is None for v in vals):
                    continue
                exp = sum(sg * (v or 0.0) for (i, sg), v in zip(ids, vals))
                if abs(exp - tv) >= 0.5:
                    results.append({"type": "casting", "page": pref(doc, page), "table": name,
                                    "row": tot.get("label", ""), "column": cols[ci] if ci < len(cols) else f"col {ci + 1}",
                                    "printed": tv, "recomputed": exp, "difference": tv - exp})
        for cs in t.get("cross_sums", []) or []:
            try:
                tc = int(cs.get("total_column"))
                cc = [int(x) for x in cs.get("component_columns", [])]
            except Exception:
                continue
            for rid, r in rows.items():
                if rid in bad:
                    continue
                v = r["_v"]
                if tc >= len(v) or v[tc] is None:
                    continue
                comps = [v[i] for i in cc if i < len(v)]
                if all(x is None for x in comps):
                    continue
                exp = sum(x or 0.0 for x in comps)
                if abs(exp - v[tc]) >= 0.5:
                    results.append({"type": "cross-cast", "page": pref(doc, page), "table": name, "row": r.get("label", ""),
                                    "column": cols[tc] if tc < len(cols) else "Total", "printed": v[tc],
                                    "recomputed": exp, "difference": v[tc] - exp})
    for lk in struct.get("links", []) or []:
        a, b = lk.get("a") or {}, lk.get("b") or {}
        av, bv = _num(a.get("value")), _num(b.get("value"))
        if av is None or bv is None:
            continue
        try:
            if not ok_on(int(a.get("page")), av, nums) or not ok_on(int(b.get("page")), bv, nums):
                unverified += 1
                continue
        except Exception:
            continue
        if abs(av - bv) >= 0.5:
            results.append({"type": "link", "description": lk.get("description", ""),
                            "a": f"{pref(doc, a.get('page'))} \"{a.get('label', '')}\"", "a_value": av,
                            "b": f"{pref(doc, b.get('page'))} \"{b.get('label', '')}\"", "b_value": bv, "difference": av - bv})
    if py:
        for c in struct.get("py_compare", []) or []:
            cu, pr = c.get("current") or {}, c.get("prior") or {}
            cv, pv = _num(cu.get("value")), _num(pr.get("value"))
            if cv is None or pv is None:
                continue
            try:
                if not ok_on(int(cu.get("page")), cv, nums) or not ok_on(int(pr.get("page")), pv, pynums):
                    unverified += 1
                    continue
            except Exception:
                continue
            if abs(cv - pv) >= 0.5:
                results.append({"type": "py_compare", "description": c.get("description", ""),
                                "current": f"{pref(doc, cu.get('page'))} \"{cu.get('label', '')}\"", "current_value": cv,
                                "prior": f"PY FS {pref(py, pr.get('page'))} \"{pr.get('label', '')}\"", "prior_value": pv,
                                "difference": cv - pv})
    if unverified:
        log(f"  {unverified} AI-transcribed figure(s) could not be matched to the page text and were excluded.")
    return results


def arithmetic_text(items: list) -> str:
    if not items:
        return "(no differences found by Python)"
    out = []
    for i, a in enumerate(items, 1):
        t = a.get("type")
        if t in ("casting", "cast", "cross-cast"):
            out.append(f"[A{i}] {'Cross-cast' if t == 'cross-cast' else 'Casting'} difference – {a.get('page')} {a.get('table', '')} "
                       f"\"{a.get('row', a.get('label', ''))}\" ({a.get('column', '')}): printed {fmt_amt(a['printed'])}, "
                       f"recomputed {fmt_amt(a['recomputed'])}, difference {fmt_amt(a['difference'])}")
        elif t == "link":
            out.append(f"[A{i}] Link difference – {a.get('description', '')}: {a['a']} {fmt_amt(a['a_value'])} vs "
                       f"{a['b']} {fmt_amt(a['b_value'])}, difference {fmt_amt(a['a_value'] - a['b_value'])}")
        elif t == "py_compare":
            out.append(f"[A{i}] PY difference – {a.get('description', '')}: current FS {a['current']} shows "
                       f"{fmt_amt(a['current_value'])}; acknowledged {a['prior']} shows {fmt_amt(a['prior_value'])}; "
                       f"difference {fmt_amt(a['difference'])}")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Review orchestration
# --------------------------------------------------------------------------

@dataclass
class ReviewResult:
    client: str
    period: str
    year: str
    page_ref_note: str
    critical: list
    points: OrderedDict          # sn -> (status, [findings])
    doc_name: str
    doc_pages: int
    py_name: str = ""
    mode: str = "rules"
    report_path: str = ""


def _strip_bullet(s: str) -> str:
    return re.sub(r"^\s*(?:[•\-\*–·]\s+|\d+[.)]\s+)", "", str(s)).strip()


def normalise_points(raw: dict, F: Facts, has_py: bool) -> OrderedDict:
    pts = OrderedDict()
    for sn in CHECKLIST_POINTS:
        status, findings = raw.get(sn, ("OK", []))
        status = next((s for s in STATUSES if s.lower() == str(status).strip().lower()), None) or (
            "N/A" if str(status).strip().upper() in ("NA", "N.A.") else "Exception" if findings else "OK")
        findings = [_strip_bullet(x) for x in findings if _strip_bullet(x)]
        findings = [x for x in findings if x.lower().rstrip(".") != "no observations"]
        if sn in (2, 3):
            if F.first_period and status not in ("N/A",) and not findings:
                status, findings = "N/A", ["First financial statements – no comparative figures."]
            elif not has_py and not F.first_period and status in ("Exception", "Query", "OK"):
                status, findings = "Not verifiable", ["Acknowledged PY FS not provided in the file."]
        if status in ("Exception", "Query"):
            if not findings:
                status, findings = "OK", [NO_OBS]
            else:
                is_q = [bool(re.match(r"^query\s*[–—-]", x, re.I)) for x in findings]
                if all(is_q):
                    status = "Query"
                    findings = [re.sub(r"^query\s*[–—-]\s*", "", x, flags=re.I) for x in findings]
                else:
                    status = "Exception"
                    findings = [re.sub(r"^query\s*[–—-]\s*", "Query – ", x, flags=re.I) for x in findings]
        elif status == "OK":
            findings = [NO_OBS]
        else:
            findings = findings[:1] or (["Point does not apply."] if status == "N/A" else ["Item not in the file provided."])
        pts[sn] = (status, findings)
    return pts


def rules_only_points(findings: list, F: Facts, has_py: bool) -> OrderedDict:
    by = defaultdict(list)
    for x in findings:
        by[x.point].append(x)
    raw = {}
    for sn in CHECKLIST_POINTS:
        items = by.get(sn, [])
        texts = [(("Query – " + x.text) if x.kind == "Query" and not x.text.startswith("Query") else x.text) for x in items]
        if sn in (2, 3):
            if F.first_period:
                raw[sn] = ("N/A", ["First financial statements – no comparative figures."])
            elif not has_py:
                raw[sn] = ("Not verifiable", ["Acknowledged PY FS not provided in the file."])
            elif sn == 2:
                raw[sn] = ("Exception", texts) if texts else ("OK", [])
            else:
                raw[sn] = ("Not verifiable", [NO_AI_LINE])
            continue
        if sn == 19 and not F.has_related:
            raw[sn] = ("N/A", ["No \"due to\" / \"due from\" related-party balances in the SOFP or CFS."])
            continue
        if texts:
            raw[sn] = ("Exception", texts)
        elif sn in RULE_COVERED_POINTS or sn == 19:
            raw[sn] = ("OK", [])
        else:
            raw[sn] = ("Not verifiable", [NO_AI_LINE])
    return normalise_points(raw, F, has_py)


CRITICAL_PRIORITY = [7, 10, 9, 11, 2, 5, 4, 6, 1, 17, 13, 19, 14, 3, 8, 12, 16, 18, 15]


def auto_critical(points: OrderedDict, n: int = 5) -> list:
    out = []
    for sn in CRITICAL_PRIORITY:
        st, fs = points[sn]
        if st in ("Exception", "Query"):
            for f_ in fs[:1]:
                out.append(f"Point {sn} – {f_}")
        if len(out) >= n:
            break
    return out or ["No exceptions noted – no critical points."]


def run_review(draft_path: str, py_path: Optional[str], ai_cfg: Optional[dict],
               log: Callable = print, progress: Callable = lambda *_: None,
               cancel: Optional[threading.Event] = None) -> ReviewResult:
    import time
    cancel = cancel or threading.Event()
    open_responses = set()
    finished = threading.Event()
    t_start = time.time()

    def _closer():
        import socket
        while not cancel.wait(1.0):
            if finished.is_set():
                return
        for r in list(open_responses):
            try:   # shutdown() wakes a thread blocked in recv(); close() alone does not on every OS
                sock = getattr(getattr(getattr(getattr(r.raw, "_fp", None), "fp", None), "raw", None), "_sock", None)
                if sock is not None:
                    sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                r.close()
            except Exception:
                pass
    threading.Thread(target=_closer, daemon=True).start()
    try:
        return _run_review(draft_path, py_path, ai_cfg, log, progress, cancel, open_responses, t_start)
    finally:
        finished.set()


def _run_review(draft_path, py_path, ai_cfg, log, progress, cancel, open_responses, t_start) -> ReviewResult:
    import time

    def chk():
        if cancel.is_set():
            raise Cancelled("Review stopped by user.")

    def elapsed() -> str:
        return f"{int(time.time() - t_start)}s"
    gaps = {}
    progress(3, "Reading draft FS …")
    doc = extract_document(draft_path, log)
    py = None
    if py_path:
        progress(8, "Reading prior-year FS …")
        py = extract_document(py_path, log, allow_ocr=True,
                              progress=lambda m: (chk(), progress(8, f"Reading prior-year FS – {m}")))
    chk()
    progress(14, "Running checklist rules and Python arithmetic …")
    eng = RuleEngine(doc, py, log)
    findings, F = eng.run()
    log(f"[{elapsed()}] Rule engine: {len(findings)} candidate finding(s); client \"{F.client}\", {F.period_label or 'period not detected'}"
        f"{'; first financial statements' if F.first_period else ''}.")
    mode = "rules"
    if ai_cfg:
        chk()
        mode = "ai"
        ai_cfg = dict(ai_cfg, _cancel=cancel, _open=open_responses)
        prov = PROVIDERS[ai_cfg["provider"]]["label"].split(" (")[0] + " · " + ai_cfg["model"]
        texts = [{"type": "text", "text": page_block(doc, "CURRENT FS")}]
        if py:
            texts.append({"type": "text", "text": page_block(py, "PY FS (acknowledged copy)")})
        # ---- pass 1: structure for python arithmetic
        meta = (f"CURRENT FS file: {doc.filename} ({len(doc.pages)} pages). "
                + (f"PY FS file: {py.filename} ({len(py.pages)} pages). " if py else "No PY FS supplied. ")
                + ("The current FS appear to be the first financial statements." if F.first_period else ""))
        rule_arith = [a for a in F.arithmetic if a.get("type") in ("cast", "cross-cast", "link")]
        if ai_cfg.get("mode") == "thorough":
            s1, gaps = ai_transcribe(doc, py, F, ai_cfg, meta, log, progress, prov)
            chk()
            progress(50, "Recomputing all totals and links in Python …")
            arith = python_arithmetic(s1, doc, py, log)
            all_arith = arith + [a for a in rule_arith if not any(
                abs(a.get("printed", a.get("a_value", 0)) - b.get("printed", b.get("a_value", 1))) < 0.5 for b in arith)]
        else:
            all_arith = rule_arith   # Fast mode: arithmetic from the Python table parser only (no AI transcription)
        log(f"[{elapsed()}] Python arithmetic: {len(all_arith)} difference(s).")
        # ---- pass 2: full review
        progress(58, "Rendering page images …")
        imgs = render_pages_png(draft_path, 80)
        chk()
        p2 = f"AI pass 2/2 – reviewing all 19 points ({prov})"
        progress(62, p2 + " …")
        cand = "\n".join(f"[{x.rid}] Point {x.point} – {x.kind} – {x.text}" for x in findings) or "(none)"
        parts = [{"type": "text", "text": meta}] + texts + [
            {"type": "text", "text": "PYTHON ARITHMETIC RESULTS (authoritative):\n" + arithmetic_text(all_arith)},
            {"type": "text", "text": "RULE CANDIDATES (verify each):\n" + cand},
            {"type": "text", "text": f"Detected: client \"{F.client}\"; period \"{F.period_label}\"; "
                                     f"first financial statements: {F.first_period}; PY FS supplied: {bool(py)}."
                                     + (" The PY FS is a SCANNED copy read by OCR: its figures may contain OCR misreads, "
                                        "so report any PY difference as a Query asking the reviewer to verify against the "
                                        "acknowledged copy." if py and py.scanned else "")}]
        for i, b64 in enumerate(imgs, 1):
            pg = doc.page(i)
            parts.append({"type": "text", "text": f"Image of CURRENT FS PDF page {i} ({pg.ref if pg else ''}):"})
            parts.append({"type": "image", "data": b64})
        parts.append({"type": "text", "text": "Now return the JSON for all 19 points."})
        system = REVIEW_SYSTEM_HEAD.format(skill=SKILL_TEXT)
        n_chars = len(system) + sum(len(x.get("text", "")) for x in parts)
        log(f"[{elapsed()}] AI review request: ~{(n_chars // 4 + len(imgs) * 1000) // 1000}k tokens "
            f"({len(imgs)} page images) – waiting for {prov} …")
        def tick2(st):
            mm = re.search(r"receiving answer · ([\d,]+) chars", st)
            pct = 66 + min(20, int(mm.group(1).replace(",", "")) // 1500) if mm else 63
            progress(pct, f"{p2} · {st}")
        s2 = ask_json(dict(ai_cfg, _tick=tick2), system, parts, log, allow_images=True)
        chk()
        log(f"[{elapsed()}] AI review received.")
        progress(88, "Finalising findings …")
        raw = {}
        for item in s2.get("points", []) or []:
            try:
                sn = int(item.get("sn"))
            except Exception:
                continue
            if sn in CHECKLIST_POINTS:
                fl = item.get("findings") or []
                if isinstance(fl, str):
                    fl = [fl]
                raw[sn] = (item.get("status", "OK"), [str(x) for x in fl])
        missing = [sn for sn in CHECKLIST_POINTS if sn not in raw]
        if missing:
            log(f"  ! AI omitted point(s) {missing}; filled from the rule engine.")
            ro = rules_only_points(findings, F, bool(py))
            for sn in missing:
                raw[sn] = ro[sn]
        points = normalise_points(raw, F, bool(py))
        add_gap_queries(points, gaps)
        crit = [_strip_bullet(x) for x in (s2.get("critical_points") or []) if _strip_bullet(x)]
        if len(crit) < 3:
            for c in auto_critical(points, 6):
                if len(crit) >= 3:
                    break
                if c.startswith("No exceptions"):
                    break
                if not any(_sim(c, x) > 0.6 for x in crit):
                    crit.append(c)
        crit = crit[:6] or auto_critical(points)
        client = _clean_name(s2.get("client") or F.client)
        period = s2.get("period") or F.period_label
        year = str(s2.get("year") or F.year)
        prn = s2.get("page_reference_note") or F.page_ref_note
    else:
        progress(60, "Assembling rules-only findings …")
        points = rules_only_points(findings, F, bool(py))
        crit = auto_critical(points)
        client, period, year, prn = F.client, F.period_label, F.year, F.page_ref_note
    res = ReviewResult(client=client or "Client", period=period or "", year=year or "", page_ref_note=prn,
                       critical=crit, points=points, doc_name=doc.filename, doc_pages=len(doc.pages),
                       py_name=(py.filename + (" (scanned copy – read by OCR)" if py.scanned else "")) if py else "",
                       mode=mode)
    progress(93, "Building Word report …")
    res.report_path = str(build_word_report(res))
    progress(100, "Done")
    log(f"[{elapsed()}] Report saved: {res.report_path}")
    return res


# --------------------------------------------------------------------------
# Word report (template per skill "Output")
# --------------------------------------------------------------------------

def _safe(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s[:80] or "Client"


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    i = 2
    while True:
        q = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not q.exists():
            return q
        i += 1


def build_word_report(res: ReviewResult, out_dir: Optional[Path] = None) -> Path:
    from docx import Document as Docx
    from docx.enum.section import WD_ORIENT
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Emu, Inches, Mm, Pt, RGBColor

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # python-docx resolves its header/footer templates via docx/parts/../templates
        os.makedirs(os.path.join(sys._MEIPASS, "docx", "parts"), exist_ok=True)
    d = Docx()
    sec = d.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Mm(297), Mm(210)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Inches(0.5))
    sec.footer_distance = Inches(0.3)

    st = d.styles["Normal"]
    st.font.name = "Arial"
    st.font.size = Pt(10)
    rpr = st.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), "Arial")
    st.paragraph_format.space_after = Pt(3)
    for sname in ("List Bullet",):
        try:
            ls = d.styles[sname]
            ls.font.name = "Arial"
        except KeyError:
            pass

    def field(par, code):
        r = par.add_run()
        b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin"); r._r.append(b)
        r2 = par.add_run()
        t = OxmlElement("w:instrText"); t.set(qn("xml:space"), "preserve"); t.text = code; r2._r.append(t)
        r3 = par.add_run()
        e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "separate"); r3._r.append(e)
        r4 = par.add_run("1")
        r5 = par.add_run()
        e2 = OxmlElement("w:fldChar"); e2.set(qn("w:fldCharType"), "end"); r5._r.append(e2)
        for rr in (r, r2, r3, r4, r5):
            rr.font.name = "Arial"; rr.font.size = Pt(9)

    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run("Page "); r.font.size = Pt(9); r.font.name = "Arial"
    field(fp, "PAGE")
    r = fp.add_run(" of "); r.font.size = Pt(9); r.font.name = "Arial"
    field(fp, "NUMPAGES")

    # Title
    p = d.add_paragraph()
    r = p.add_run("Hard Copy Review – Findings Report")
    r.bold = True
    r.font.size = Pt(15)
    p.paragraph_format.space_after = Pt(8)

    # Metadata
    doc_line = f"{res.doc_name} ({res.doc_pages} pages)"
    if res.py_name:
        doc_line += f"; PY FS: {res.py_name}"
    today = _dt.date.today()
    for lab, val in (("Client", res.client), ("Period", res.period or "-"), ("Document reviewed", doc_line),
                     ("Checklist applied", "Hard copy review check list – points 1 to 19"),
                     ("Date of review", f"{today.day} {today.strftime('%B %Y')}")):
        p = d.add_paragraph()
        p.paragraph_format.space_after = Pt(1)
        a = p.add_run(f"{lab}: "); a.bold = True
        p.add_run(val)

    p = d.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    r = p.add_run(res.page_ref_note); r.italic = True

    # Critical points (red)
    red = RGBColor(0xC0, 0x00, 0x00)
    p = d.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    r = p.add_run("Critical points to correct before issue"); r.bold = True; r.font.size = Pt(12); r.font.color.rgb = red
    for c in res.critical:
        bp = d.add_paragraph(style="List Bullet")
        bp.paragraph_format.space_after = Pt(1)
        rr = bp.add_run(c); rr.font.color.rgb = red

    p = d.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    r = p.add_run("Checklist findings"); r.bold = True; r.font.size = Pt(12)

    widths = [600, 3000, 1500, 9300]  # DXA
    tbl = d.add_table(rows=1, cols=4)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = d.styles["Table Grid"]
    tbl.autofit = False
    tblPr = tbl._tbl.tblPr
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); tblPr.append(lay)
    tw = tblPr.find(qn("w:tblW"))
    if tw is None:
        tw = OxmlElement("w:tblW"); tblPr.append(tw)
    tw.set(qn("w:w"), str(sum(widths))); tw.set(qn("w:type"), "dxa")
    grid = tbl._tbl.tblGrid
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
        gc.set(qn("w:w"), str(w))

    def shade(cell, hexfill):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hexfill)
        tcPr.append(shd)

    def set_w(cell, w):
        cell.width = Emu(w * 635)

    hdr = tbl.rows[0]
    trPr = hdr._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader"); th.set(qn("w:val"), "true"); trPr.append(th)
    for i, (txt, w) in enumerate(zip(["SN", "Checklist point", "Status", "Findings"], widths)):
        c = hdr.cells[i]
        set_w(c, w)
        shade(c, "1F3864")
        c.paragraphs[0].text = ""
        rr = c.paragraphs[0].add_run(txt)
        rr.bold = True; rr.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF); rr.font.size = Pt(10)

    for sn, title in CHECKLIST_POINTS.items():
        status, fl = res.points[sn]
        row = tbl.add_row()
        cells = row.cells
        for c, w in zip(cells, widths):
            set_w(c, w)
        cells[0].paragraphs[0].add_run(str(sn)).font.size = Pt(9.5)
        cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cells[1].paragraphs[0].add_run(title).font.size = Pt(9.5)
        sr = cells[2].paragraphs[0].add_run(status); sr.bold = True; sr.font.size = Pt(9.5)
        shade(cells[2], STATUS_SHADING[status])
        fc = cells[3]
        if status in ("Exception", "Query"):
            first = True
            for f_ in fl:
                par = fc.paragraphs[0] if first else fc.add_paragraph()
                if first:
                    par.style = d.styles["List Bullet"]
                else:
                    par.style = d.styles["List Bullet"]
                par.paragraph_format.space_after = Pt(2)
                rr = par.add_run(f_); rr.font.size = Pt(9.5)
                first = False
        else:
            fc.paragraphs[0].add_run(fl[0] if fl else NO_OBS).font.size = Pt(9.5)
        for c in cells:
            for par in c.paragraphs:
                par.paragraph_format.space_after = Pt(2)

    p = d.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    r = p.add_run(STATUS_KEY_LINE); r.italic = True; r.font.size = Pt(9)

    out_dir = out_dir or downloads_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"Hard_Copy_Review_Findings_{_safe(res.client)}_{_safe(res.year) if res.year else 'Year'}.docx"
    path = unique_path(out_dir / fname)
    d.save(str(path))
    return path

# --------------------------------------------------------------------------
# User interface (PySide6 / Qt)
# --------------------------------------------------------------------------

QSS = """
* { font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial; font-size: 10pt; color: #1e293b; }
QMainWindow, QDialog, QWidget#Page, QScrollArea, QScrollArea > QWidget > QWidget#Page { background: #f3f5f9; }
QScrollArea { border: none; }
QFrame#Header { background: #ffffff; border: none; border-bottom: 1px solid #e2e7ef; }
QFrame#Header QLabel { background: transparent; }
QLabel { background: transparent; }
#Title { font-size: 16pt; font-weight: 700; color: #1F3864; }
#Subtitle { color: #64748b; font-size: 9.5pt; }
#Card { background: #ffffff; border: 1px solid #e2e7ef; border-radius: 10px; }
#Card[drag="true"] { border: 2px dashed #2563eb; background: #f5f8ff; }
#CardTitle { font-size: 11pt; font-weight: 600; color: #1F3864; }
#CardHint { color: #64748b; font-size: 9pt; }
#Step { background: #1F3864; color: #ffffff; border-radius: 11px; font-weight: 700; font-size: 9pt;
        min-width: 22px; max-width: 22px; min-height: 22px; max-height: 22px; qproperty-alignment: AlignCenter; }
#FileName { font-weight: 600; color: #0f172a; font-size: 10.5pt; }
#FileMeta { color: #64748b; font-size: 9pt; }
#Badge { border-radius: 9px; padding: 2px 9px; font-size: 8.5pt; font-weight: 600; }
#Chip { background: #e9f7ef; color: #146c43; border: 1px solid #c7ead5; border-radius: 13px; padding: 5px 12px; font-weight: 600; font-size: 9pt; }
#ChipOff { background: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; border-radius: 13px; padding: 5px 12px; font-weight: 600; font-size: 9pt; }
QPushButton { background: #ffffff; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 7px; padding: 7px 16px; font-weight: 600; min-height: 18px; }
QPushButton:hover { background: #f1f5f9; border-color: #94a3b8; }
QPushButton:pressed { background: #e2e8f0; }
QPushButton:disabled { color: #94a3b8; background: #f8fafc; border-color: #e2e8f0; }
QPushButton#Primary { background: #1F3864; color: #ffffff; border: none; border-radius: 8px; font-size: 11pt; padding: 12px 20px; }
QPushButton#Primary:hover { background: #2a4a82; }
QPushButton#Primary:pressed { background: #172b4d; }
QPushButton#Primary:disabled { background: #cbd5e1; color: #f8fafc; }
QPushButton#Link { background: transparent; border: none; color: #2563eb; padding: 2px 4px; }
QPushButton#Link:hover { text-decoration: underline; }
QPushButton#Danger { color: #b42318; }
QPushButton#Danger:hover { background: #fef3f2; border-color: #fda29b; }
QProgressBar { background: #e2e8f0; border: none; border-radius: 4px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #2563eb; border-radius: 4px; }
QPlainTextEdit { background: #f8fafc; color: #334155; border: 1px solid #e2e7ef; border-radius: 8px; padding: 8px;
                 font-family: Consolas, "Cascadia Mono", monospace; font-size: 9pt; selection-background-color: #bfdbfe; }
QLineEdit, QComboBox, QSpinBox { background: #ffffff; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 8px; min-height: 22px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #2563eb; }
QLineEdit:disabled { background: #f1f5f9; color: #94a3b8; }
QComboBox QAbstractItemView { background: #ffffff; color: #1e293b; selection-background-color: #e8eefb; selection-color: #1F3864; border: 1px solid #cbd5e1; }
QListWidget { background: #ffffff; border: 1px solid #e2e7ef; border-radius: 10px; padding: 6px; outline: none; }
QListWidget::item { padding: 9px 10px; border-radius: 6px; color: #1e293b; }
QListWidget::item:selected { background: #e8eefb; color: #1F3864; }
QListWidget::item:hover:!selected { background: #f1f5f9; }
QMessageBox { background: #ffffff; }
QToolTip { background: #1e293b; color: #ffffff; border: none; padding: 5px 8px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
#Crit { color: #9b1c1c; }
#SectionLabel { font-weight: 700; color: #1F3864; font-size: 10.5pt; }
#Muted { color: #64748b; font-size: 9pt; }
#Elapsed { color: #64748b; font-size: 9pt; font-family: Consolas, "Cascadia Mono", monospace; }
"""

STATUS_CHIP_COLORS = {"Exception": ("#F8D7DA", "#842029"), "Query": ("#FFF3CD", "#664d03"),
                      "OK": ("#D4EDDA", "#0f5132"), "N/A": ("#E2E3E5", "#41464b"),
                      "Not verifiable": ("#E2E3E5", "#41464b")}


def make_icon_image(size: int = 256):
    """Neutral app icon (document with a check mark) drawn with Pillow."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 256
    d.rounded_rectangle([16 * s, 16 * s, 240 * s, 240 * s], radius=48 * s, fill=(31, 56, 100, 255))
    d.rounded_rectangle([70 * s, 48 * s, 186 * s, 208 * s], radius=12 * s, fill=(255, 255, 255, 255))
    for i, y in enumerate((82, 106, 130)):
        d.rounded_rectangle([88 * s, y * s, (168 - 20 * (i == 2)) * s, (y + 9) * s], radius=4 * s, fill=(196, 205, 222, 255))
    d.ellipse([132 * s, 140 * s, 212 * s, 220 * s], fill=(46, 160, 98, 255))
    d.line([(150 * s, 181 * s), (167 * s, 197 * s), (195 * s, 164 * s)], fill=(255, 255, 255, 255), width=int(11 * s), joint="curve")
    return img


def write_icon_file(path: str):
    if path.lower().endswith(".icns"):
        make_icon_image(1024).save(path, format="ICNS")
        return
    img = make_icon_image(256)
    img.save(path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def run_gui():
    import time
    from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer
    from PySide6.QtGui import QIcon, QPixmap, QDesktopServices, QKeySequence, QPalette, QPainter
    from PySide6.QtCore import QSize, QRectF
    from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                   QPushButton, QFrame, QFileDialog, QProgressBar, QPlainTextEdit, QDialog,
                                   QListWidget, QListWidgetItem, QStackedWidget, QLineEdit, QComboBox,
                                   QSpinBox, QFormLayout, QMessageBox, QGraphicsDropShadowEffect,
                                   QScrollArea)
    from PySide6.QtGui import QColor

    def qicon() -> QIcon:
        img = make_icon_image(256)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pm = QPixmap()
        pm.loadFromData(buf.getvalue(), "PNG")
        return QIcon(pm)

    def shadow(w):
        e = QGraphicsDropShadowEffect()
        e.setBlurRadius(24)
        e.setOffset(0, 4)
        e.setColor(QColor(20, 33, 61, 28))
        w.setGraphicsEffect(e)

    # ---------- workers ----------
    class ReviewWorker(QThread):
        log = Signal(str)
        progress = Signal(int, str)
        done = Signal(object)
        failed = Signal(str, bool)
        stopped = Signal()

        def __init__(self, draft, py, ai_cfg):
            super().__init__()
            self.draft, self.py, self.ai_cfg = draft, py, ai_cfg
            self.cancel = threading.Event()

        def run(self):
            try:
                res = run_review(self.draft, self.py, self.ai_cfg, log=self.log.emit,
                                 progress=lambda p, m: self.progress.emit(int(p), m), cancel=self.cancel)
                self.done.emit(res)
            except Cancelled:
                self.stopped.emit()
            except ScannedPdfError as e:
                self.failed.emit(str(e), False)
            except AIError as e:
                self.failed.emit(str(e), True)
            except Exception as e:
                self.log.emit(traceback.format_exc())
                self.failed.emit(f"{type(e).__name__}: {e}", False)

    class TestWorker(QThread):
        done = Signal(bool, str)

        def __init__(self, cfg):
            super().__init__()
            self.cfg = cfg

        def run(self):
            try:
                self.done.emit(True, test_connection(self.cfg))
            except Exception as e:
                self.done.emit(False, str(e))

    # ---------- secure key field ----------
    class SecretField(QLineEdit):
        """Masked entry: never shows, copies, cuts or drags the key."""

        def __init__(self):
            super().__init__()
            self.setEchoMode(QLineEdit.Password)
            self.setContextMenuPolicy(Qt.NoContextMenu)
            self.setDragEnabled(False)
            self.setAcceptDrops(True)
            self.setInputMethodHints(Qt.ImhHiddenText | Qt.ImhNoPredictiveText | Qt.ImhSensitiveData)

        def keyPressEvent(self, e):
            if e.matches(QKeySequence.Copy) or e.matches(QKeySequence.Cut):
                return
            super().keyPressEvent(e)

    # ---------- on/off switch ----------
    from PySide6.QtWidgets import QAbstractButton

    class ToggleSwitch(QAbstractButton):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setCheckable(True)
            self.setCursor(Qt.PointingHandCursor)
            self.setFixedSize(46, 26)

        def sizeHint(self):
            return QSize(46, 26)

        def paintEvent(self, _):
            pnt = QPainter(self)
            pnt.setRenderHint(QPainter.Antialiasing)
            on, en = self.isChecked(), self.isEnabled()
            track = QColor("#16a34a" if on else "#cbd5e1")
            if not en:
                track = QColor("#e2e8f0")
            pnt.setPen(Qt.NoPen)
            pnt.setBrush(track)
            pnt.drawRoundedRect(QRectF(0, 0, 46, 26), 13, 13)
            pnt.setBrush(QColor("#ffffff"))
            x = 23 if on else 3
            pnt.drawEllipse(QRectF(x, 3, 20, 20))
            pnt.end()

    # ---------- settings password dialogs ----------
    class UnlockDialog(QDialog):
        """Asks for the settings password; 5 wrong attempts close the dialog."""

        def __init__(self, parent, settings: Settings):
            super().__init__(parent)
            self.s = settings
            self.tries = 0
            self.setWindowTitle("Settings locked")
            self.setMinimumWidth(420)
            lay = QVBoxLayout(self); lay.setContentsMargins(24, 22, 24, 18); lay.setSpacing(10)
            t = QLabel("🔒  Settings are locked"); t.setObjectName("CardTitle")
            h = QLabel("Enter the settings password to view or change the AI settings."); h.setObjectName("Muted")
            h.setWordWrap(True)
            self.pw = SecretField(); self.pw.setPlaceholderText("Password")
            self.err = QLabel(""); self.err.setStyleSheet("color:#b42318;font-size:9pt;")
            lay.addWidget(t); lay.addWidget(h); lay.addWidget(self.pw); lay.addWidget(self.err)
            b = QHBoxLayout(); b.addStretch()
            c = QPushButton("Cancel"); c.clicked.connect(self.reject)
            ok = QPushButton("Unlock"); ok.setObjectName("Primary"); ok.setStyleSheet("padding:8px 22px;font-size:10pt;")
            ok.setDefault(True); ok.clicked.connect(self.check)
            self.pw.returnPressed.connect(self.check)
            b.addWidget(c); b.addWidget(ok); lay.addLayout(b)

        def check(self):
            if self.s.check_lock(self.pw.text()):
                self.pw.clear()
                self.accept()
                return
            self.tries += 1
            self.pw.clear()
            if self.tries >= 5:
                QMessageBox.warning(self, APP_NAME, "Too many wrong attempts.")
                self.reject()
                return
            self.err.setText(f"Wrong password ({5 - self.tries} attempt{'s' if 5 - self.tries != 1 else ''} left).")

    class NewPasswordDialog(QDialog):
        def __init__(self, parent):
            super().__init__(parent)
            self.password = ""
            self.setWindowTitle("Settings password")
            self.setMinimumWidth(440)
            lay = QVBoxLayout(self); lay.setContentsMargins(24, 22, 24, 18); lay.setSpacing(10)
            t = QLabel("Set settings password"); t.setObjectName("CardTitle")
            h = QLabel("Anyone opening Settings will need this password. At least 6 characters. "
                       "If it is forgotten, the settings (including saved API keys) must be reset."); h.setObjectName("Muted")
            h.setWordWrap(True)
            self.p1 = SecretField(); self.p1.setPlaceholderText("New password")
            self.p2 = SecretField(); self.p2.setPlaceholderText("Confirm password")
            self.err = QLabel(""); self.err.setStyleSheet("color:#b42318;font-size:9pt;")
            for w in (t, h, self.p1, self.p2, self.err):
                lay.addWidget(w)
            b = QHBoxLayout(); b.addStretch()
            c = QPushButton("Cancel"); c.clicked.connect(self.reject)
            ok = QPushButton("Set password"); ok.setObjectName("Primary"); ok.setStyleSheet("padding:8px 22px;font-size:10pt;")
            ok.setDefault(True); ok.clicked.connect(self.check)
            b.addWidget(c); b.addWidget(ok); lay.addLayout(b)

        def check(self):
            a, b = self.p1.text(), self.p2.text()
            if len(a) < 6:
                self.err.setText("Use at least 6 characters.")
            elif a != b:
                self.err.setText("The two entries do not match.")
            else:
                self.password = a
                self.p1.clear(); self.p2.clear()
                self.accept()

    # ---------- drop card ----------
    class DropCard(QFrame):
        def __init__(self, step, title, hint, required, on_change):
            super().__init__()
            self.setObjectName("Card")
            self.setAcceptDrops(True)
            self.path = ""
            self.on_change = on_change
            self.setMinimumHeight(190)
            shadow(self)
            lay = QVBoxLayout(self)
            lay.setContentsMargins(20, 18, 20, 18)
            lay.setSpacing(6)
            top = QHBoxLayout()
            stp = QLabel(step); stp.setObjectName("Step")
            t = QLabel(title); t.setObjectName("CardTitle")
            top.addWidget(stp); top.addSpacing(4)
            badge = QLabel("Required" if required else "Optional"); badge.setObjectName("Badge")
            badge.setStyleSheet("background:#e8eefb;color:#1F3864;" if required else "background:#f1f5f9;color:#64748b;")
            top.addWidget(t); top.addStretch(); top.addWidget(badge)
            lay.addLayout(top)
            h = QLabel(hint); h.setObjectName("CardHint"); h.setWordWrap(True)
            lay.addWidget(h)
            lay.addStretch()
            self.drop = QLabel("Drop PDF here  ·  or browse")
            self.drop.setAlignment(Qt.AlignCenter)
            self.drop.setStyleSheet("border:1.5px dashed #cbd5e1;border-radius:8px;padding:16px;color:#64748b;background:#f8fafc;")
            lay.addWidget(self.drop)
            self.name = QLabel(""); self.name.setObjectName("FileName"); self.name.setWordWrap(True)
            self.meta = QLabel(""); self.meta.setObjectName("FileMeta")
            lay.addWidget(self.name); lay.addWidget(self.meta)
            self.name.hide(); self.meta.hide()
            btns = QHBoxLayout()
            self.browse = QPushButton("Browse…")
            self.browse.clicked.connect(self.pick)
            self.clear = QPushButton("Remove"); self.clear.setObjectName("Danger")
            self.clear.clicked.connect(lambda: self.set_path(""))
            self.clear.hide()
            btns.addWidget(self.browse); btns.addWidget(self.clear); btns.addStretch()
            lay.addLayout(btns)

        def pick(self):
            p, _ = QFileDialog.getOpenFileName(self, "Select PDF", str(Path.home()), "PDF files (*.pdf)")
            if p:
                self.set_path(p)

        def set_path(self, p):
            self.path = p
            if p:
                try:
                    import pypdfium2 as pdfium
                    doc = pdfium.PdfDocument(p); n = len(doc); doc.close()
                    meta = f"{n} page{'s' if n != 1 else ''} · {os.path.getsize(p) / 1024:,.0f} KB"
                except Exception:
                    meta = "Could not open this PDF"
                self.name.setText(os.path.basename(p)); self.meta.setText(meta)
                self.drop.hide(); self.name.show(); self.meta.show(); self.clear.show()
                self.browse.setText("Change…")
            else:
                self.name.hide(); self.meta.hide(); self.clear.hide(); self.drop.show()
                self.browse.setText("Browse…")
            self.on_change()

        def dragEnterEvent(self, e):
            if e.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith(".pdf") for u in e.mimeData().urls()):
                e.acceptProposedAction()
                self.setProperty("drag", "true"); self.style().unpolish(self); self.style().polish(self)

        def dragLeaveEvent(self, e):
            self.setProperty("drag", "false"); self.style().unpolish(self); self.style().polish(self)

        def dropEvent(self, e):
            self.dragLeaveEvent(e)
            for u in e.mimeData().urls():
                f = u.toLocalFile()
                if f.lower().endswith(".pdf"):
                    self.set_path(f)
                    break

    # ---------- settings dialog ----------
    class SettingsDialog(QDialog):
        def __init__(self, parent, settings: Settings):
            super().__init__(parent)
            self.s = settings
            self.setWindowTitle("AI settings")
            self.setMinimumSize(860, 640)
            self.pending_keys: dict = {}
            self.remove_keys: set = set()
            self.tests = []
            root = QVBoxLayout(self)
            root.setContentsMargins(22, 20, 22, 18)
            root.setSpacing(12)
            t = QLabel("AI provider"); t.setObjectName("Title"); t.setStyleSheet("font-size:15pt;")
            st = QLabel("The AI handles the judgment points of the checklist. Keys are "
                        + ("stored in your macOS Keychain" if IS_MAC else "encrypted with your Windows account")
                        + " and are never displayed or copyable. Without a key the tool runs rules-only.")
            st.setObjectName("Subtitle"); st.setWordWrap(True)
            root.addWidget(t); root.addWidget(st)
            body = QHBoxLayout(); body.setSpacing(14)
            self.list = QListWidget(); self.list.setFixedWidth(220)
            self.stack = QStackedWidget()
            self.widgets = {}
            for pid, meta in PROVIDERS.items():
                it = QListWidgetItem(meta["label"])
                it.setData(Qt.UserRole, pid)
                self.list.addItem(it)
                self.stack.addWidget(self._page(pid, meta))
            self.list.currentRowChanged.connect(self.stack.setCurrentIndex)
            body.addWidget(self.list); body.addWidget(self.stack, 1)
            root.addLayout(body, 1)
            act = QHBoxLayout()
            act.addWidget(QLabel("Use for reviews:"))
            self.active = QComboBox()
            self.active.setMinimumWidth(260)
            act.addWidget(self.active); act.addSpacing(18)
            act.addWidget(QLabel("Review mode:"))
            self.mode = QComboBox()
            self.mode.addItem("Fast – one AI pass (recommended)", "fast")
            self.mode.addItem("Thorough – AI also re-types every table (slow)", "thorough")
            self.mode.setCurrentIndex(max(0, self.mode.findData(self.s.data.get("mode", "fast"))))
            self.mode.setToolTip("Fast: Python casts and links the figures, then one AI request reviews all 19 points.\n"
                                 "Thorough: the AI first transcribes every table so Python can re-cast them a second way. "
                                 "Many more AI requests – much slower on accounts with low rate limits.")
            act.addWidget(self.mode); act.addStretch()
            root.addLayout(act)
            self.lock_action = None          # None | ("set", password) | ("remove",)
            lk = QHBoxLayout()
            lk.addWidget(QLabel("Settings lock:"))
            self.lock_lbl = QLabel(); self.lock_lbl.setObjectName("Muted")
            self.lock_set = QPushButton(); self.lock_set.clicked.connect(self._set_lock)
            self.lock_rm = QPushButton("Remove lock"); self.lock_rm.setObjectName("Danger")
            self.lock_rm.clicked.connect(self._remove_lock)
            lk.addWidget(self.lock_lbl); lk.addSpacing(8); lk.addWidget(self.lock_set); lk.addWidget(self.lock_rm); lk.addStretch()
            root.addLayout(lk)
            self._lock_status()
            btns = QHBoxLayout(); btns.addStretch()
            cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
            save = QPushButton("Save"); save.setObjectName("Primary"); save.setStyleSheet("padding:8px 22px;font-size:10pt;")
            save.clicked.connect(self.save)
            btns.addWidget(cancel); btns.addWidget(save)
            root.addLayout(btns)
            self._refresh_active(initial=True)
            start = list(PROVIDERS).index(self.s.active) if self.s.active else 0
            self.list.setCurrentRow(start)

        def _page(self, pid, meta):
            w = QFrame(); w.setObjectName("Card")
            f = QFormLayout(w)
            f.setContentsMargins(20, 18, 20, 18)
            f.setVerticalSpacing(12)
            f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            hdr = QLabel(meta["label"]); hdr.setObjectName("CardTitle")
            f.addRow(hdr)
            key = SecretField()
            status = QLabel(); status.setObjectName("Muted")
            rm = QPushButton("Remove saved key"); rm.setObjectName("Danger")
            key.textChanged.connect(lambda _=None, p=pid: self._refresh_active())
            rm.clicked.connect(lambda _=None, p=pid: self._remove(p))
            kb = QHBoxLayout(); kb.addWidget(key, 1); kb.addWidget(rm)
            f.addRow("API key", kb)
            f.addRow("", status)
            model = QComboBox(); model.setEditable(True)
            model.addItems(meta["models"])
            model.setCurrentText(self.s.provider(pid)["model"])
            f.addRow("Model", model)
            url = QLineEdit(self.s.provider(pid)["base_url"])
            url.setEnabled(meta["base_url_editable"])
            url.setPlaceholderText("https://…/v1")
            f.addRow("Base URL", url)
            mt = QSpinBox(); mt.setRange(1024, 2_000_000); mt.setSingleStep(1024); mt.setGroupSeparatorShown(True)
            mt.setToolTip("Upper limit on the length of each AI answer. If the model accepts less, the tool "
                          "lowers it automatically for that request.")
            mt.setValue(int(self.s.provider(pid).get("max_tokens") or 32000))
            f.addRow("Max output tokens", mt)
            par = QSpinBox(); par.setRange(1, 8)
            par.setValue(int(self.s.provider(pid).get("parallel") or 3))
            par.setToolTip("How many AI requests run at the same time while transcribing tables. "
                           "Lower it to 1 if the provider reports rate-limit (429) errors.")
            f.addRow("Parallel requests", par)
            rsn = QComboBox()
            rsn.addItem("Standard (model default)", "default")
            rsn.addItem("Low – faster (thinking off / low effort)", "low")
            rsn.setCurrentIndex(max(0, rsn.findData(self.s.provider(pid).get("reasoning", "default"))))
            rsn.setToolTip("Thinking models (GPT-5/6, Gemini 3, Claude) can spend many minutes and most of the output "
                           "allowance reasoning before answering. 'Low' answers much faster.")
            f.addRow("Reasoning", rsn)
            tb = QPushButton("Test connection")
            tres = QLabel(""); tres.setObjectName("Muted"); tres.setWordWrap(True)
            tb.clicked.connect(lambda _=None, p=pid: self._test(p))
            trow = QHBoxLayout(); trow.addWidget(tb); trow.addWidget(tres, 1)
            f.addRow("", trow)
            note = QLabel("Type the model name exactly as the provider lists it; the list shows suggestions only.")
            note.setObjectName("Muted"); note.setWordWrap(True)
            f.addRow("", note)
            self.widgets[pid] = dict(key=key, status=status, rm=rm, model=model, url=url, mt=mt, par=par, rsn=rsn, tres=tres, tb=tb)
            self._key_status(pid)
            return w

        def _locked(self) -> bool:
            if self.lock_action:
                return self.lock_action[0] == "set"
            return self.s.has_lock()

        def _lock_status(self):
            on = self._locked()
            pend = " (applies on Save)" if self.lock_action else ""
            self.lock_lbl.setText(("🔒 Password required to open Settings" if on else "Off – anyone can open Settings") + pend)
            self.lock_set.setText("Change password…" if on else "Set password…")
            self.lock_rm.setVisible(on)

        def _set_lock(self):
            d = NewPasswordDialog(self)
            if d.exec() and d.password:
                self.lock_action = ("set", d.password)
                self._lock_status()

        def _remove_lock(self):
            self.lock_action = ("remove",) if self.s.has_lock() else None
            self._lock_status()

        def _has_key(self, pid):
            w = self.widgets.get(pid)
            typed = bool(w and w["key"].text().strip())
            return typed or (self.s.has_key(pid) and pid not in self.remove_keys)

        def _key_status(self, pid):
            w = self.widgets[pid]
            saved = self.s.has_key(pid) and pid not in self.remove_keys
            w["key"].setPlaceholderText("••••••••••••  saved – type to replace" if saved else "Paste API key")
            w["status"].setText("🔒 Key saved (encrypted)" if saved else "No key saved")
            w["rm"].setVisible(saved)

        def _remove(self, pid):
            self.remove_keys.add(pid)
            self.widgets[pid]["key"].clear()
            self._key_status(pid)
            self._refresh_active()

        def _refresh_active(self, initial=False):
            cur = self.s.active if initial else self.active.currentData()
            self.active.blockSignals(True)
            self.active.clear()
            self.active.addItem("None – rules-only (no AI)", "")
            for pid, meta in PROVIDERS.items():
                if self._has_key(pid):
                    self.active.addItem(meta["label"], pid)
            idx = max(0, self.active.findData(cur or ""))
            if not cur and not initial:
                for i in range(self.active.count()):
                    if self.active.itemData(i):
                        idx = i
                        break
            self.active.setCurrentIndex(idx)
            self.active.blockSignals(False)

        def _cfg(self, pid):
            w = self.widgets[pid]
            key = w["key"].text().strip() or (self.s.get_key(pid) if pid not in self.remove_keys else "")
            return {"provider": pid, "model": w["model"].currentText().strip(), "base_url": w["url"].text().strip(),
                    "max_tokens": w["mt"].value(), "parallel": w["par"].value(), "reasoning": w["rsn"].currentData(),
                    "key": key}

        def _test(self, pid):
            cfg = self._cfg(pid)
            w = self.widgets[pid]
            if not cfg["key"]:
                w["tres"].setText("Enter an API key first.")
                return
            w["tb"].setEnabled(False)
            w["tres"].setText("Testing …")
            th = TestWorker(cfg)
            th.done.connect(lambda ok, msg, w=w: (w["tres"].setText(("✔ Connected – reply: " if ok else "✖ ") + msg),
                                                   w["tb"].setEnabled(True)))
            self.tests.append(th)
            th.start()

        def save(self):
            for pid, w in self.widgets.items():
                p = self.s.provider(pid)
                p["model"] = w["model"].currentText().strip()
                p["base_url"] = w["url"].text().strip() if PROVIDERS[pid]["base_url_editable"] else PROVIDERS[pid]["base_url"]
                p["max_tokens"] = w["mt"].value()
                p["parallel"] = w["par"].value()
                p["reasoning"] = w["rsn"].currentData() or "default"
                if pid in self.remove_keys:
                    self.s.set_key(pid, "")
                typed = w["key"].text().strip()
                if typed:
                    self.s.set_key(pid, typed)
                w["key"].clear()
            self.s.data["active"] = self.active.currentData() or ""
            self.s.data["mode"] = self.mode.currentData() or "fast"
            if self.lock_action and self.lock_action[0] == "set":
                self.s.set_lock(self.lock_action[1])
            elif self.lock_action and self.lock_action[0] == "remove":
                self.s.clear_lock()
            self.lock_action = None
            try:
                self.s.save()
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Could not save settings: {e}")
                return
            self.accept()

    # ---------- main window ----------
    class Main(QMainWindow):
        def __init__(self):
            super().__init__()
            self.settings = Settings()
            self.worker = None
            self.result = None
            self.setWindowTitle(APP_NAME)
            self.setWindowIcon(qicon())
            self.resize(980, 760)
            self.setMinimumSize(820, 640)
            scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cw = QWidget(); cw.setObjectName("Page"); scroll.setWidget(cw)
            outer_w = QWidget(); outer_w.setObjectName("Page")
            outer = QVBoxLayout(outer_w); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
            self.setCentralWidget(outer_w)
            hdr = QFrame(); hdr.setObjectName("Header")
            head = QHBoxLayout(hdr); head.setContentsMargins(28, 14, 28, 14); head.setSpacing(14)
            logo = QLabel(); logo.setPixmap(qicon().pixmap(38, 38))
            head.addWidget(logo, 0, Qt.AlignVCenter)
            outer.addWidget(hdr)
            outer.addWidget(scroll, 1)
            root = QVBoxLayout(cw)
            root.setContentsMargins(28, 22, 28, 18)
            root.setSpacing(16)

            tl = QVBoxLayout(); tl.setSpacing(1)
            t = QLabel(APP_NAME); t.setObjectName("Title")
            s = QLabel("19-point checklist on the draft FS & auditor's report · Word report saved to Downloads")
            s.setWordWrap(True)
            s.setObjectName("Subtitle")
            tl.addWidget(t); tl.addWidget(s)
            head.addLayout(tl, 1)
            self.ai_switch = ToggleSwitch()
            self.ai_switch.setToolTip("Use AI for the judgment points. Off = rules-only report (no AI request is made).")
            self.ai_switch.toggled.connect(self._ai_toggled)
            sw_lbl = QLabel("AI review"); sw_lbl.setStyleSheet("font-weight:600;color:#1e293b;")
            head.addWidget(sw_lbl, 0, Qt.AlignVCenter); head.addWidget(self.ai_switch, 0, Qt.AlignVCenter)
            head.addSpacing(6)
            self.chip = QLabel(); head.addWidget(self.chip, 0, Qt.AlignVCenter)
            sb = QPushButton("⚙  Settings"); sb.clicked.connect(self.open_settings)
            sb.setCursor(Qt.PointingHandCursor)
            head.addWidget(sb, 0, Qt.AlignVCenter)

            cards = QHBoxLayout(); cards.setSpacing(16)
            self.draft = DropCard("1", "Draft FS + Auditor's Report",
                                  "Current draft set to be reviewed (text-based PDF).", True, self.update_state)
            self.py = DropCard("2", "Prior-year FS (acknowledged copy)",
                               "Used for checklist points 2 and 3. Text-based or scanned PDF. Leave empty if not in file.", False, self.update_state)
            cards.addWidget(self.draft, 1); cards.addWidget(self.py, 1)
            root.addLayout(cards)

            self.run_btn = QPushButton("Run hard copy review"); self.run_btn.setObjectName("Primary")
            self.run_btn.setCursor(Qt.PointingHandCursor)
            self.run_btn.clicked.connect(self.start)
            root.addWidget(self.run_btn)

            self.prog_card = QFrame(); self.prog_card.setObjectName("Card"); shadow(self.prog_card)
            pl = QVBoxLayout(self.prog_card); pl.setContentsMargins(20, 16, 20, 16); pl.setSpacing(8)
            ph = QHBoxLayout()
            self.prog_lbl = QLabel("Ready"); self.prog_lbl.setObjectName("SectionLabel")
            self.prog_lbl.setWordWrap(True)
            self.toggle_log = QPushButton("Show details"); self.toggle_log.setObjectName("Link")
            self.toggle_log.clicked.connect(self._toggle_log)
            self.elapsed = QLabel(""); self.elapsed.setObjectName("Elapsed")
            self.stop_btn = QPushButton("Stop"); self.stop_btn.setObjectName("Danger")
            self.stop_btn.setCursor(Qt.PointingHandCursor)
            self.stop_btn.clicked.connect(self.stop)
            self.stop_btn.hide()
            ph.addWidget(self.prog_lbl, 1); ph.addWidget(self.elapsed); ph.addSpacing(8)
            ph.addWidget(self.stop_btn); ph.addWidget(self.toggle_log)
            pl.addLayout(ph)
            self.bar = QProgressBar(); self.bar.setRange(0, 100); self.bar.setValue(0); self.bar.setFixedHeight(8)
            self.t0 = 0.0
            self.timer = QTimer(self); self.timer.setInterval(1000)
            self.timer.timeout.connect(self._tick)
            pl.addWidget(self.bar)
            self.logbox = QPlainTextEdit(); self.logbox.setReadOnly(True); self.logbox.setMinimumHeight(150)
            self.logbox.hide()
            pl.addWidget(self.logbox)
            root.addWidget(self.prog_card)

            self.res_card = QFrame(); self.res_card.setObjectName("Card"); shadow(self.res_card)
            rl = QVBoxLayout(self.res_card); rl.setContentsMargins(20, 18, 20, 18); rl.setSpacing(10)
            rh = QHBoxLayout()
            self.res_title = QLabel("Review complete"); self.res_title.setObjectName("CardTitle"); self.res_title.setWordWrap(True)
            rh.addWidget(self.res_title, 1)
            self.open_btn = QPushButton("Open report"); self.open_btn.clicked.connect(self.open_report)
            self.folder_btn = QPushButton("Show in Finder" if IS_MAC else "Open Downloads folder"); self.folder_btn.clicked.connect(self.open_folder)
            rh.addWidget(self.open_btn); rh.addWidget(self.folder_btn)
            rl.addLayout(rh)
            self.res_file = QLabel(""); self.res_file.setObjectName("Muted"); self.res_file.setWordWrap(True)
            rl.addWidget(self.res_file)
            self.chips = QHBoxLayout(); self.chips.setSpacing(8)
            rl.addLayout(self.chips)
            cl = QLabel("Critical points to correct before issue"); cl.setObjectName("SectionLabel")
            cl.setStyleSheet("color:#C00000;")
            rl.addWidget(cl)
            self.crit = QLabel(""); self.crit.setObjectName("Crit"); self.crit.setWordWrap(True)
            self.crit.setTextInteractionFlags(Qt.TextSelectableByMouse)
            rl.addWidget(self.crit)
            self.res_card.hide()
            root.addWidget(self.res_card)
            root.addStretch()
            foot = QLabel(f"v{APP_VERSION} · Draft FS: text-based PDF · Prior-year FS: text or scanned · Page references follow the printed page numbers")
            foot.setObjectName("Muted"); foot.setAlignment(Qt.AlignCenter)
            root.addWidget(foot)
            self.update_chip()
            self.update_state()

        # ---- helpers
        def _ai_toggled(self, on):
            if getattr(self, "_sync", False):
                return
            self.settings.data["ai_enabled"] = bool(on)
            try:
                self.settings.save()
            except Exception:
                pass
            self.update_chip()

        def update_chip(self):
            cfg = self.settings.ai_config()
            self._sync = True
            self.ai_switch.setEnabled(bool(cfg))
            self.ai_switch.setChecked(bool(cfg) and self.settings.data.get("ai_enabled", True))
            self._sync = False
            if cfg and not self.ai_switch.isChecked():
                cfg = None
                self.chip.setObjectName("ChipOff")
                self.chip.setText("○  AI off – rules-only")
            elif not self.settings.ai_config():
                self.ai_switch.setToolTip("No AI provider is set up in Settings – the review runs rules-only.")
            if cfg:
                self.chip.setObjectName("Chip")
                self.chip.setText(f"●  AI: {PROVIDERS[cfg['provider']]['label'].split(' (')[0]} · {cfg['model']}"
                                  f"  ·  {'Thorough' if cfg.get('mode') == 'thorough' else 'Fast'}")
            else:
                self.chip.setObjectName("ChipOff")
                self.chip.setText("○  AI off – rules-only" if self.settings.ai_config() else "○  AI not set up – rules-only")
            self.chip.style().unpolish(self.chip); self.chip.style().polish(self.chip)

        def update_state(self):
            busy = self.worker is not None and self.worker.isRunning()
            self.run_btn.setEnabled(bool(self.draft.path) and not busy)
            self.run_btn.setText("Review running …" if busy else "Run hard copy review")
            self.draft.setEnabled(not busy); self.py.setEnabled(not busy)
            self.ai_switch.setEnabled(not busy and bool(self.settings.ai_config()))
            self.stop_btn.setVisible(busy)
            if busy:
                if not self.timer.isActive():
                    self.timer.start()
            else:
                self.timer.stop()
                self.stop_btn.setEnabled(True); self.stop_btn.setText("Stop")

        def _tick(self):
            sec = int(time.time() - self.t0)
            self.elapsed.setText(f"{sec // 60}:{sec % 60:02d}")

        def stop(self):
            if self.worker is not None and self.worker.isRunning():
                self.worker.cancel.set()
                self.stop_btn.setEnabled(False); self.stop_btn.setText("Stopping …")
                self.prog_lbl.setText("Stopping – finishing the current step …")
                self.log("Stop requested by user.")

        def stopped(self):
            self.prog_lbl.setText("Stopped by user")
            self.log("Review stopped.")
            self.update_state()

        def _toggle_log(self):
            v = not self.logbox.isVisible()
            self.logbox.setVisible(v)
            self.toggle_log.setText("Hide details" if v else "Show details")

        def log(self, msg):
            self.logbox.appendPlainText(msg)

        def open_settings(self):
            if self.settings.has_lock() and not UnlockDialog(self, self.settings).exec():
                return
            dlg = SettingsDialog(self, self.settings)
            if dlg.exec():
                self.update_chip()

        # ---- run
        def start(self, _=None, force_rules=False):
            if not self.draft.path:
                return
            if self.py.path and os.path.abspath(self.py.path) == os.path.abspath(self.draft.path):
                QMessageBox.warning(self, APP_NAME, "The prior-year FS is the same file as the draft FS.")
                return
            cfg = None if (force_rules or not self.ai_switch.isChecked()) else self.settings.ai_config()
            self.res_card.hide()
            self.logbox.clear()
            self.bar.setValue(0)
            self.log(f"Mode: {'AI – ' + PROVIDERS[cfg['provider']]['label'] + ' · ' + cfg['model'] if cfg else 'rules-only'}")
            self.worker = ReviewWorker(self.draft.path, self.py.path or None, cfg)
            self.worker.log.connect(self.log)
            self.worker.progress.connect(lambda p, m: (self.bar.setValue(p), self.prog_lbl.setText(m)))
            self.worker.done.connect(self.finished)
            self.worker.failed.connect(self.failed)
            self.worker.stopped.connect(self.stopped)
            self.worker.finished.connect(self.update_state)
            self.t0 = time.time(); self.elapsed.setText("0:00")
            self.worker.start()
            self.update_state()

        def finished(self, res: ReviewResult):
            self.result = res
            self.prog_lbl.setText("Done")
            self.bar.setValue(100)
            self.res_title.setText(f"Review complete – {res.client}" + (f" · {res.period}" if res.period else ""))
            self.res_file.setText(f"Saved to Downloads:  {os.path.basename(res.report_path)}"
                                  + ("" if res.mode == "ai" else "   (rules-only – judgment points marked Not verifiable)"))
            while self.chips.count():
                it = self.chips.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()
            cnt = Counter(st for st, _ in res.points.values())
            for st in STATUSES:
                if cnt.get(st):
                    bg, fg = STATUS_CHIP_COLORS[st]
                    c = QLabel(f"{st}  {cnt[st]}")
                    c.setStyleSheet(f"background:{bg};color:{fg};border-radius:11px;padding:4px 11px;font-weight:700;")
                    self.chips.addWidget(c)
            self.chips.addStretch()
            self.crit.setText("\n".join("•  " + c for c in res.critical))
            self.res_card.show()
            self.update_state()

        def failed(self, msg, ai_related):
            self.prog_lbl.setText("Stopped")
            self.log("ERROR: " + msg)
            self.update_state()
            if ai_related:
                b = QMessageBox(self)
                b.setIcon(QMessageBox.Warning)
                b.setWindowTitle(APP_NAME)
                b.setText("The AI review could not be completed.")
                b.setInformativeText(msg + "\n\nYou can fix the setting and run again, or produce the report rules-only now.")
                rules = b.addButton("Run rules-only", QMessageBox.AcceptRole)
                b.addButton("Close", QMessageBox.RejectRole)
                b.exec()
                if b.clickedButton() is rules:
                    self.start(force_rules=True)
            else:
                QMessageBox.critical(self, APP_NAME, msg)

        def open_report(self):
            if self.result and self.result.report_path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.result.report_path))

        def open_folder(self):
            p = self.result.report_path if self.result else ""
            if p and sys.platform.startswith("win"):
                import subprocess
                subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
            elif p and IS_MAC:
                import subprocess
                subprocess.Popen(["open", "-R", p])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(downloads_dir())))

        def closeEvent(self, e):
            if self.worker is not None and self.worker.isRunning():
                if QMessageBox.question(self, APP_NAME, "A review is running. Stop it and quit?") != QMessageBox.Yes:
                    e.ignore()
                    return
                self.worker.cancel.set()
                self.worker.wait(3000)
            e.accept()

    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FSHardCopyReview.App")
        except Exception:
            pass
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    try:  # Qt 6.8+: ignore Windows dark mode
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except Exception:
        pass
    pal = QPalette()
    for role, col in ((QPalette.Window, "#f3f5f9"), (QPalette.WindowText, "#1e293b"), (QPalette.Base, "#ffffff"),
                      (QPalette.AlternateBase, "#f8fafc"), (QPalette.Text, "#1e293b"), (QPalette.Button, "#ffffff"),
                      (QPalette.ButtonText, "#1e293b"), (QPalette.ToolTipBase, "#1e293b"), (QPalette.ToolTipText, "#ffffff"),
                      (QPalette.Highlight, "#2563eb"), (QPalette.HighlightedText, "#ffffff"),
                      (QPalette.PlaceholderText, "#94a3b8"), (QPalette.Link, "#2563eb")):
        pal.setColor(role, QColor(col))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor("#94a3b8"))
    app.setPalette(pal)
    qss = QSS
    if IS_MAC:
        # macOS draws points smaller than Windows; scale the font sizes up and use the system font
        qss = re.sub(r"(\d+(?:\.\d+)?)pt", lambda m_: f"{float(m_.group(1)) * 1.3:.1f}pt", qss)
        qss = qss.replace('font-family: "Segoe UI",', 'font-family: "-apple-system", "SF Pro Text", "Helvetica Neue", "Segoe UI",')
    app.setStyleSheet(qss)
    app.setWindowIcon(qicon())
    w = Main()
    w.show()
    return app.exec()


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main(argv: list) -> int:
    if len(argv) >= 2 and argv[1] == "--make-icon":
        write_icon_file(argv[2] if len(argv) > 2 else "app.ico")
        return 0
    if len(argv) >= 3 and argv[1] == "--cli":
        # Command-line use: --cli <draft.pdf> [py.pdf]  (uses the AI provider saved in Settings, if any)
        draft = argv[2]
        py = argv[3] if len(argv) > 3 else None
        res = run_review(draft, py, Settings().ai_config(), log=print,
                         progress=lambda p, m: print(f"[{p:3d}%] {m}"))
        print("\nCritical points:")
        for c in res.critical:
            print(" -", c)
        return 0
    def _hook(et, ev, tb):
        try:
            (app_data_dir() / "error.log").open("a", encoding="utf-8").write(
                f"\n[{_dt.datetime.now():%Y-%m-%d %H:%M:%S}]\n" + "".join(traceback.format_exception(et, ev, tb)))
        except Exception:
            pass
        sys.__excepthook__(et, ev, tb)
    sys.excepthook = _hook
    return run_gui()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
