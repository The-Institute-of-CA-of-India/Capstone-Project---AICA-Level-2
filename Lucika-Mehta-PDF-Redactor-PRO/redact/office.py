"""Excel (.xlsx/.xls), CSV and Word (.docx) redaction."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from pathlib import Path

from . import detect as D
from .model import FileResult, FileScan, Finding, Options, Overrides

OFFICE_EXT = {".xlsx", ".xlsm", ".xls", ".csv", ".docx"}
BLOCK = "█████"


def kind_of(name: str) -> str:
    ext = Path(name).suffix.lower()
    return {".xlsx": "xlsx", ".xlsm": "xlsx", ".xls": "xls", ".csv": "csv", ".docx": "docx"}.get(ext, "")


# --------------------------------------------------------------------------
# Text units: (where, text, setter)
# --------------------------------------------------------------------------
def _cell_text(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, int) and abs(v) >= 10 ** 7:
        return str(v)
    if isinstance(v, float) and v.is_integer() and abs(v) >= 10 ** 7:
        return str(int(v))            # account numbers stored as numbers
    return None


def _load_xlsx(data: bytes, kind: str):
    import openpyxl
    if kind == "xls":
        import xlrd
        book = xlrd.open_workbook(file_contents=data)
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for sh in book.sheets():
            ws = wb.create_sheet(sh.name[:31])
            for r in range(sh.nrows):
                ws.append(sh.row_values(r))
        return wb
    return openpyxl.load_workbook(io.BytesIO(data), keep_vba=False)


def _label_prefix(v) -> str:
    """A short text cell such as 'Account Name' or 'Address:' is read as the label of the cell to its right."""
    if not isinstance(v, str):
        return ""
    t = v.strip()
    if not t or len(t) > 40 or re.search(r"\d", t) or not re.search(r"[A-Za-z]{2}", t):
        return ""
    return t.rstrip(":-. ") + ": "


def _cell_matches(t: str, prefix: str, fn):
    """Matches in a cell, read together with its label cell; positions refer to the cell itself."""
    if not prefix:
        return fn(t)
    out = []
    n = len(prefix)
    for m in fn(prefix + t):
        if m.end <= n:
            continue
        s, e = max(m.start - n, 0), m.end - n
        out.append(D.Match(s, e, m.rule, t[s:e]))
    return out


def _xlsx_units(wb):
    for ws in wb.worksheets:                      # includes hidden sheets
        for row in ws.iter_rows():
            for cell in row:
                t = _cell_text(cell.value)
                if t:
                    def setter(new, c=cell):
                        c.value = new
                    left = ws.cell(row=cell.row, column=cell.column - 1).value if cell.column > 1 else None
                    yield f"{ws.title}!{cell.coordinate}", t, setter, _label_prefix(left)


def _docx_paragraphs(doc):
    def walk_tables(tables, prefix):
        for ti, t in enumerate(tables):
            for ri, row in enumerate(t.rows):
                for ci, cell in enumerate(row.cells):
                    for pi, p in enumerate(cell.paragraphs):
                        yield f"{prefix}table {ti + 1} r{ri + 1}c{ci + 1}", p
                    yield from walk_tables(cell.tables, f"{prefix}table {ti + 1} r{ri + 1}c{ci + 1} > ")
    for i, p in enumerate(doc.paragraphs):
        yield f"paragraph {i + 1}", p
    yield from walk_tables(doc.tables, "")
    for si, sec in enumerate(doc.sections):
        for part_name in ("header", "footer", "first_page_header", "first_page_footer"):
            part = getattr(sec, part_name, None)
            if part is None:
                continue
            for i, p in enumerate(part.paragraphs):
                yield f"{part_name.replace('_', ' ')} {si + 1}", p
            yield from walk_tables(part.tables, f"{part_name} {si + 1} ")


def _rewrite_runs(paragraph, replacements):
    """replacements: [(start, end, new_text)] over the paragraph text (sorted)."""
    runs = paragraph.runs
    if not runs:
        return
    owner = []
    for ri, r in enumerate(runs):
        owner += [ri] * len(r.text)
    new = [[] for _ in runs]
    pos, k = 0, 0
    text = "".join(r.text for r in runs)
    while pos < len(text):
        if k < len(replacements) and pos == replacements[k][0]:
            s, e, rep = replacements[k]
            new[owner[s]].append(rep)
            pos, k = e, k + 1
            continue
        new[owner[pos]].append(text[pos])
        pos += 1
    for r, parts in zip(runs, new):
        r.text = "".join(parts)


def _csv_rows(data: bytes):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    dialect = csv.Sniffer().sniff(text[:4096]) if text.strip() else csv.excel
    return list(csv.reader(io.StringIO(text), dialect)), dialect


# --------------------------------------------------------------------------
# Pass 1
# --------------------------------------------------------------------------
def _texts(kind: str, data: bytes):
    if kind in ("xlsx", "xls"):
        return [(w, t, pre) for w, t, _, pre in _xlsx_units(_load_xlsx(data, kind))]
    if kind == "csv":
        rows, _ = _csv_rows(data)
        return [(f"row {i + 1} col {j + 1}", v, _label_prefix(r[j - 1]) if j else "")
                for i, r in enumerate(rows) for j, v in enumerate(r) if v]
    if kind == "docx":
        import docx
        d = docx.Document(io.BytesIO(data))
        return [(w, p.text, "") for w, p in _docx_paragraphs(d) if p.text]
    return []


def scan_office(name: str, data: bytes, opts: Options) -> FileScan:
    kind = kind_of(name)
    scan = FileScan(name=name, kind=kind, raw=data)
    try:
        units = _texts(kind, data)
    except Exception as exc:
        scan.status, scan.message = "error", f"Could not read file: {exc}"
        return scan
    sample = "\n".join(t for _, t, _ in units[:400])
    scan.profile = opts.profile if opts.profile in D.PROFILE_ADJUST else D.classify(sample)
    rules = D.effective_rules(opts.rules, scan.profile, opts.profile) - D.VISUAL_RULES
    for where, t, pre in units:
        for m in _cell_matches(t, pre, lambda x: D.find_matches(x, rules, opts)):
            scan.findings.append(Finding(0, m.rule, m.value, "cell", where=where))
    scan.page_count = 0
    return scan


# --------------------------------------------------------------------------
# Pass 2
# --------------------------------------------------------------------------
def _replacements(text, rules, opts, ctx, ov, where, findings, prefix=""):
    reps = []
    for m in _cell_matches(text, prefix, lambda x: D.all_matches(x, rules, opts, ctx, ov)):
        label = ctx.token(m.rule, m.value) if (ctx and opts.style == "label") else ""
        reps.append((m.start, m.end, f"[{label}]" if label else BLOCK))
        findings.append(Finding(0, m.rule, m.value, "cell", label, where))
    return reps


def _apply(text, reps):
    out, pos = [], 0
    for s, e, rep in reps:
        out.append(text[pos:s])
        out.append(rep)
        pos = e
    out.append(text[pos:])
    return "".join(out)


def redact_office(scan: FileScan, opts: Options, ctx=None, ov: Overrides | None = None) -> FileResult:
    ov = ov or Overrides()
    kind = scan.kind
    res = FileResult(name=scan.name, kind=kind, profile=scan.profile, message=scan.message)
    rules = D.effective_rules(opts.rules, scan.profile, opts.profile) - D.VISUAL_RULES
    data = scan.raw
    try:
        if kind in ("xlsx", "xls"):
            wb = _load_xlsx(data, kind)
            for where, t, setter, pre in list(_xlsx_units(wb)):
                reps = _replacements(t, rules, opts, ctx, ov, where, res.findings, pre)
                if reps:
                    setter(_apply(t, reps))
            for ws in wb.worksheets:
                for row in ws.iter_rows():
                    for c in row:
                        if c.comment is not None:
                            c.comment = None
            if opts.scrub_metadata:
                p = wb.properties
                for f in ("creator", "lastModifiedBy", "title", "subject", "description", "keywords", "category"):
                    setattr(p, f, None)
            buf = io.BytesIO()
            wb.save(buf)
            res.output, res.output_ext = buf.getvalue(), ".xlsx"
            res.message = (res.message + " Charts and pictures inside the workbook are not carried over.").strip()
            res.text_export = _xlsx_text(wb)
        elif kind == "csv":
            rows, dialect = _csv_rows(data)
            for i, r in enumerate(rows):
                original = list(r)
                for j, v in enumerate(r):
                    if v:
                        pre = _label_prefix(original[j - 1]) if j else ""
                        reps = _replacements(v, rules, opts, ctx, ov, f"row {i + 1} col {j + 1}", res.findings, pre)
                        if reps:
                            r[j] = _apply(v, reps)
            buf = io.StringIO()
            csv.writer(buf, dialect).writerows(rows)
            res.output, res.output_ext = buf.getvalue().encode("utf-8-sig"), ".csv"
            res.text_export = buf.getvalue()
        elif kind == "docx":
            import docx
            d = docx.Document(io.BytesIO(data))
            for where, p in list(_docx_paragraphs(d)):
                t = "".join(r.text for r in p.runs)
                if not t:
                    continue
                reps = _replacements(t, rules, opts, ctx, ov, where, res.findings)
                if reps:
                    _rewrite_runs(p, reps)
            if opts.scrub_metadata:
                cp = d.core_properties
                for f in ("author", "last_modified_by", "title", "subject", "comments", "keywords", "category"):
                    try:
                        setattr(cp, f, "")
                    except Exception:
                        pass
            buf = io.BytesIO()
            d.save(buf)
            res.output, res.output_ext = buf.getvalue(), ".docx"
            res.text_export = "\n".join(p.text for _, p in _docx_paragraphs(d) if p.text)
            res.message = (res.message + " Pictures and text boxes in Word files are not scanned.").strip()
        else:
            res.status, res.message = "error", "Unsupported file type."
            return res
    except Exception as exc:
        res.status, res.message = "error", f"Failed during redaction: {exc}"
        return res

    # residual check on the output
    try:
        out_kind = "xlsx" if kind == "xls" else kind
        res.residual = sum(
            1 for _, t, pre in _texts(out_kind, res.output)
            for m in _cell_matches(t, pre, lambda x: D.all_matches(x, rules, opts, ctx, Overrides(keep_values=ov.keep_values)))
            if not D.is_noise(m.rule, m.value))
    except Exception:
        pass
    if not res.findings:
        res.status = "no_findings"
    res.sha_out = hashlib.sha256(res.output).hexdigest()
    return res


def _xlsx_text(wb) -> str:
    parts = []
    for ws in wb.worksheets:
        parts.append(f"=== Sheet: {ws.title} ===")
        for row in ws.iter_rows(values_only=True):
            if any(v is not None for v in row):
                parts.append("\t".join("" if v is None else str(v) for v in row))
    return "\n".join(parts)
