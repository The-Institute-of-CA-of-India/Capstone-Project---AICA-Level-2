"""Word output: Bookman Old Style, justified paragraphs, simple Markdown-style headings, lists and tables."""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt

from .models import UserFacingError

FONT = "Bookman Old Style"
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_TABLE_SEP = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")


def _set_font(run, size: float | None = None, bold: bool | None = None) -> None:
    run.font.name = FONT
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), FONT)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold


def _add_inline(par, text: str, size: float = 11, bold: bool = False) -> None:
    """Add text, honouring **bold** spans."""
    pos = 0
    for m in _BOLD.finditer(text):
        if m.start() > pos:
            _set_font(par.add_run(text[pos:m.start()]), size, bold)
        _set_font(par.add_run(m.group(1)), size, True)
        pos = m.end()
    if pos < len(text):
        _set_font(par.add_run(text[pos:]), size, bold)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def write_document(text: str, path: Path, title: str | None = None) -> None:
    """Write ``text`` to a .docx file."""
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(11)
    if title:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_inline(p, title, 14, True)

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        # Markdown table
        if stripped.startswith("|") and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1].strip()):
            header = _cells(stripped)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            table = doc.add_table(rows=1 + len(rows), cols=len(header))
            table.style = "Table Grid"
            for r, row in enumerate([header] + rows):
                for c in range(len(header)):
                    cell = table.cell(r, c)
                    cell.text = ""
                    _add_inline(cell.paragraphs[0], row[c] if c < len(row) else "", 10, r == 0)
            doc.add_paragraph()
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            level = len(heading.group(1))
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
            _add_inline(p, heading.group(2).replace("**", ""), {1: 14, 2: 12.5, 3: 11.5}.get(level, 11), True)
        elif re.match(r"^[-*•]\s+", stripped):
            p = doc.add_paragraph(style="List Bullet")
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            _add_inline(p, re.sub(r"^[-*•]\s+", "", stripped))
        else:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            _add_inline(p, stripped)
        i += 1
    try:
        doc.save(str(path))
    except OSError as exc:
        raise UserFacingError("The Word file could not be saved. If it is open in Word, close it and try again.") from exc
