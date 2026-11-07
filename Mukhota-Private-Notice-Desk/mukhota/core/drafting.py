"""Draft Reply pipeline: verified-PDF gate -> tokenised facts -> Claude -> local token restore -> files."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .. import VERSION
from .allowlist import Allowlist
from .config import APP_ROOT
from .detectors import MasterEntry, detect_text
from .ingest import ocr_page, open_pdf_bytes, read_pdf_bytes
from .models import VISUAL_TYPES, PageInfo, UserFacingError, Word
from .tokens import TOKEN_RE, TokenRegistry, load_vault, save_vault
from .verify import _find_files, is_verified

log = logging.getLogger("mukhota.drafting")
Progress = Callable[[int, str], None]

PROMPTS_DIR = APP_ROOT / "prompts"
INPUT_MODES = {"both": "Redacted PDF + text", "pdf": "Redacted PDF only", "text": "Text only"}
# Sections the user can ask for, in output order. An output mode is the ticked keys joined by "+",
# e.g. "reply+advisory" or "advisory".
OUTPUTS = {"reply": "Draft reply", "advisory": "Advisory", "law": "Law research note"}
HOW_MODES = {"send": "Send to AI", "prompt": "Make a prompt (any AI chat)"}
NOTICE_TYPES = ["Income-tax", "GST", "Other"]
MARKERS = {"framing": "<<<FRAMING>>>", "reply": "<<<REPLY>>>", "advisory": "<<<ADVISORY>>>", "law": "<<<LAW_NOTE>>>"}
# Optional add-on (off unless ticked): an issue-framing section before the others, by the six-box method.
# "framing" joins the output mode like a section, e.g. "framing+reply+advisory".
FRAMING = "framing"
SECTION_ORDER = [FRAMING, *OUTPUTS]
SIX_BOXES = {
    "issue": ("Issue", "What exactly is alleged?"),
    "period": ("Period", "Which year / month / tax period is involved?"),
    "provision": ("Provision", "Which section, rule or circular appears relevant?"),
    "gap": ("Fact gap", "What is not yet clear?"),
    "evidence": ("Evidence", "What documents can prove or disprove the position?"),
    "objective": ("Objective", "What should the output help me do?"),
}


@dataclass
class DraftJob:
    """A verified redacted notice ready for drafting."""

    pdf_path: Path
    folder: Path
    base: str
    pdf_bytes: bytes
    registry: TokenRegistry
    vault_meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class DraftOutput:
    """Sections of Claude's answer, as tokens and restored."""

    tokens: dict[str, str]
    restored: dict[str, str]
    unrestored: list[str]


def prepare(pdf_path: str | Path) -> DraftJob:
    """Load a redacted PDF for drafting; refuses anything without a matching PASS report."""
    pdf = Path(pdf_path)
    if not is_verified(pdf):
        raise UserFacingError(
            "Draft Reply only works on a redacted PDF that passed verification and has not changed since. "
            "Run Verify first."
        )
    vault_path, _ = _find_files(pdf)
    vault = load_vault(vault_path)
    stem = pdf.stem
    base = stem[: -len("_REDACTED")] if stem.endswith("_REDACTED") else stem
    registry = TokenRegistry.from_vault(vault)
    # Tokens made from typed facts live in the draft vault; reuse them (needed to restore a pasted answer
    # for a prompt made earlier), unless the notice was redacted again since.
    draft_vault = pdf.parent / f"{base}_draft.vault"
    if draft_vault.exists() and draft_vault.stat().st_mtime >= vault_path.stat().st_mtime:
        try:
            registry = TokenRegistry.from_vault(load_vault(draft_vault))
        except UserFacingError:
            log.warning("Draft vault could not be read; using the redaction vault")
    return DraftJob(pdf, pdf.parent, base, read_pdf_bytes(pdf), registry, vault.get("meta", {}))


def outputs_of(output_mode: str) -> list[str]:
    """Ticked sections in output order; refuses an empty choice."""
    keys = [k for k in SECTION_ORDER if k in output_mode.split("+")]
    if not any(k in OUTPUTS for k in keys):
        raise UserFacingError("Tick at least one of Draft reply, Advisory or Law research note.")
    return keys


def with_six_box(facts: str, boxes: dict[str, str]) -> str:
    """Facts plus the six-box inputs; blank boxes are left for the AI to complete from the notice."""
    lines = [f"{label}: {str(boxes.get(k) or '').strip() or '(blank - complete from the notice)'}"
             for k, (label, _) in SIX_BOXES.items()]
    block = "Six-box framing - my inputs:\n" + "\n".join(lines)
    return f"{facts.strip()}\n\n{block}" if facts.strip() else block


_AY_RE = re.compile(r"(?i)(?:assessment\s+year|a\.?\s?y\.?)\s*[:\-]?\s*(20\d{2})\s*[-–/]\s*(?:20)?(\d{2})")


def detect_ay(job: DraftJob) -> str:
    """Assessment year printed on the notice (e.g. '2024-25'), or '' if none is found."""
    doc = open_pdf_bytes(job.pdf_bytes)
    try:
        text = "\n".join(doc[i].get_text("text") for i in range(min(doc.page_count, 2)))
    finally:
        doc.close()
    m = _AY_RE.search(text)
    return f"{m.group(1)}-{m.group(2)}" if m else ""


def extract_text(job: DraftJob, cfg: dict[str, Any], progress: Progress | None = None) -> str:
    """Text of the redacted PDF; pages without a text layer are read with OCR."""
    doc = open_pdf_bytes(job.pdf_bytes)
    out: list[str] = []
    try:
        n = doc.page_count
        for i, page in enumerate(doc):
            if progress:
                progress(int(i * 100 / n), f"Reading page {i + 1} of {n}")
            text = page.get_text("text").strip()
            if len(text) < 20:
                lines: dict[Any, list[str]] = {}
                for w in ocr_page(page, int(cfg["ocr"]["dpi"])):
                    lines.setdefault(w.line_key, []).append(w.text)
                text = "\n".join(" ".join(ws) for ws in lines.values())
            out.append(f"--- Page {i + 1} ---\n{text}")
    finally:
        doc.close()
    return "\n\n".join(out)


def tokenise_facts(
    text: str, job: DraftJob, cfg: dict[str, Any], allow: Allowlist, master: list[MasterEntry]
) -> tuple[str, list[str]]:
    """Replace known values with their tokens and new PII with new tokens; returns (safe text, notes)."""
    safe = text
    # 1. Values already in the vault get their existing tokens.
    for e in sorted(job.registry.entries(), key=lambda e: -len(e.value)):
        if e.pii_type in VISUAL_TYPES or e.value.startswith("visual:") or len(e.value.strip()) < 3:
            continue
        body = r"\s*".join(re.escape(p) for p in e.value.split())
        safe = re.sub(rf"(?<!\w){body}(?!\w)", e.token, safe, flags=re.IGNORECASE)

    # 2. Detectors on the remaining text; anything new gets a fresh token.
    words: list[Word] = []
    for li, line in enumerate(safe.splitlines()):
        for wi, tok in enumerate(line.split()):
            words.append(Word(tok, (wi, li, wi + 1, li + 1), 1.0, (0, li)))
    cands, _, _ = detect_text([PageInfo(0, "TEXT", 0, 0, words)], cfg, allow, master, use_spacy=False)
    counts: dict[str, int] = {}
    for c in sorted(cands, key=lambda c: -len(c.text)):
        if not re.sub(r"[^A-Za-z0-9]", "", TOKEN_RE.sub("", c.text)):
            continue
        token = job.registry.assign(c.text, c.pii_type, c.role)
        body = r"\s*".join(re.escape(p) for p in c.text.split())
        safe, n = re.subn(rf"(?<!\w){body}(?!\w)", token, safe)
        if n:
            counts[c.pii_type] = counts.get(c.pii_type, 0) + 1
    notes = [f"{n} new {t} value(s) replaced with tokens" for t, n in sorted(counts.items())]
    return safe, notes


def _read_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise UserFacingError(f"The prompt file prompts\\{name} is missing.") from exc


def system_prompt() -> str:
    """Shared drafting rules (prompts/reply_system.md)."""
    return _read_prompt("reply_system.md")


def user_instructions(notice_type: str, output_mode: str, input_mode: str, facts: str) -> str:
    """Per-request instructions: the ticked sections, notice type, what was attached, and the tokenised facts."""
    keys = outputs_of(output_mode)
    names = {"framing": "an issue framing (six-box method)", "reply": "the reply to be filed", "advisory": "an internal advisory note", "law": "a law research note"}
    task = "Task: prepare " + " and ".join(names[k] for k in keys) + " for this notice."
    if "reply" not in keys:
        task += " Do NOT draft a reply."
    mode_text = (
        f"{task}\n\nOutput exactly {len(keys)} section{'s' if len(keys) > 1 else ''}, each starting with its marker "
        f"on a line of its own, in this order:\n\n"
        + "\n".join(_read_prompt(f"section_{k}.md").strip() + "\n" for k in keys)
    )
    attached = {
        "both": "the redacted notice as a PDF and its extracted text",
        "pdf": "the redacted notice as a PDF",
        "text": "the extracted text of the redacted notice",
    }[input_mode]
    return (
        f"{mode_text}\n\n"
        f"Notice type: {notice_type}\n"
        f"Attached: {attached}.\n\n"
        f"<facts_and_instructions>\n{facts.strip() or '(none provided)'}\n</facts_and_instructions>"
    )


def split_sections(text: str, output_mode: str) -> dict[str, str]:
    """Split the model's answer at the section markers."""
    keys = outputs_of(output_mode)
    positions = sorted((text.find(MARKERS[k]), k) for k in keys if MARKERS[k] in text)
    out = {k: "" for k in keys}
    if not positions:
        out[next(k for k in keys if k in OUTPUTS)] = text.strip()
        return out
    for i, (pos, key) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        out[key] = text[pos + len(MARKERS[key]):end].strip()
    return out


def finalise(text: str, job: DraftJob, output_mode: str) -> DraftOutput:
    """Restore tokens locally and list any token that could not be restored."""
    sections = split_sections(text, output_mode)
    mapping = {e.token: e.value for e in job.registry.entries() if not e.value.startswith("visual:")}
    restored: dict[str, str] = {}
    unrestored: set[str] = set()
    for key, body in sections.items():
        r = body
        for token in sorted(mapping, key=len, reverse=True):
            r = r.replace(token, mapping[token])
        restored[key] = r
        unrestored.update(TOKEN_RE.findall(r))
    return DraftOutput(sections, restored, sorted(unrestored))


PLACEHOLDER_RE = re.compile(r"\[\[[^\[\]]+\]\]")


def find_placeholders(out: DraftOutput) -> list[str]:
    """Unique [[TO CONFIRM: ...]] / [[ATTACH: ...]] placeholders, in order of first appearance."""
    seen: dict[str, None] = {}
    for body in out.restored.values():
        for m in PLACEHOLDER_RE.finditer(body):
            seen.setdefault(m.group(0), None)
    return list(seen)


def fill_placeholders(out: DraftOutput, values: dict[str, str]) -> DraftOutput:
    """Copy of ``out`` with every placeholder that has a non-blank value replaced (local only)."""
    filled = {}
    for key, body in out.restored.items():
        for ph, val in values.items():
            if val.strip():
                body = body.replace(ph, val.strip())
        filled[key] = body
    return DraftOutput(out.tokens, filled, out.unrestored)


def save_outputs(job: DraftJob, out: DraftOutput, output_mode: str,
                 original: DraftOutput | None = None) -> list[Path]:
    """Write the token draft (.txt), Word files with real values, the extended vault, and a
    changes file listing your manual edits against Claude's draft (when ``original`` is given)."""
    import difflib

    from .docx_writer import write_document

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    paths: list[Path] = []
    if original is not None:
        diffs = []
        for key, edited in out.restored.items():
            before = original.restored.get(key, "").splitlines()
            after = edited.splitlines()
            if before != after:
                diffs.append(f"===== {key.upper()} =====")
                diffs.extend(difflib.unified_diff(before, after, "Claude draft", "Your edited version", lineterm="", n=1))
        if diffs:
            changes = job.folder / f"{job.base}_CHANGES_{stamp}.txt"
            changes.write_text("\n".join(diffs) + "\n", encoding="utf-8")
            paths.append(changes)
    token_txt = job.folder / f"{job.base}_DRAFT_tokens_{stamp}.txt"
    token_txt.write_text(
        "\n\n".join(f"{MARKERS[k]}\n{v}" for k, v in out.tokens.items()), encoding="utf-8"
    )
    paths.append(token_txt)
    names = {"framing": ("FRAMING", "Issue Framing - six-box method (internal)"), "reply": ("REPLY", "Reply"), "advisory": ("ADVISORY", "Internal Advisory - not for submission"),
             "law": ("LAW_NOTE", "Law Research Note")}
    for key in outputs_of(output_mode):
        suffix, title = names[key]
        body = out.restored.get(key, "")
        if not body:
            continue
        p = job.folder / f"{job.base}_{suffix}_{stamp}.docx"
        write_document(body, p, title if key != "reply" else None)
        paths.append(p)
    _save_draft_vault(job)
    log.info("Draft outputs saved: %d file(s), mode=%s", len(paths), output_mode)
    return paths


def _save_draft_vault(job: DraftJob) -> None:
    save_vault(job.registry, job.folder / f"{job.base}_draft.vault", {
        "redacted_file": job.pdf_path.name, "created": datetime.now().isoformat(timespec="seconds"),
        "app_version": VERSION, "purpose": "Draft Reply tokens (notice + typed facts)",
    })


def chat_prompt(system: str, notice_text: str | None, user_text: str) -> str:
    """One self-contained prompt to paste into any AI chat (tokens only; the notice goes in as text)."""
    parts = [system.strip()]
    if notice_text:
        parts.append(f"<notice_text>\n{notice_text}\n</notice_text>")
    parts.append(user_text.strip())
    parts.append("Reply with the requested sections only, each starting with its marker exactly as shown, "
                 "and keep every token such as [ASSESSEE] or [PAN_1] unchanged.")
    return "\n\n".join(parts) + "\n"


def save_prompt(job: DraftJob, text: str) -> Path:
    """Save the chat prompt next to the redacted notice, plus the vault needed to restore the answer later."""
    p = job.folder / f"{job.base}_PROMPT_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    try:
        p.write_text(text, encoding="utf-8")
        _save_draft_vault(job)
    except OSError as exc:
        raise UserFacingError("The prompt could not be saved in the output folder.") from exc
    log.info("Chat prompt saved")
    return p
