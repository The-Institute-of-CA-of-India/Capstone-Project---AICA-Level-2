"""
Batch orchestration.

Pass 1 reads every file (in parallel) and detects identifiers.
Between the passes the batch context assigns consistent labels (ACCT-1 …)
and collects every value found, so that pass 2 can black it out wherever it
appears in any file of the batch.
Pass 2 redacts every file (in parallel).
"""

from __future__ import annotations

import hashlib
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import detect as D
from . import office, pdf
from .model import FileResult, FileScan, Options, Overrides

SUPPORTED_EXT = {".pdf"} | pdf.IMAGE_EXT | office.OFFICE_EXT


def default_workers() -> int:
    return max(1, min(6, (os.cpu_count() or 2) - 1))


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------
def _parse_dates(lines):
    out = []
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        m = re.fullmatch(r"(\d{1,2})[./\-\s](\d{1,2})[./\-\s](\d{2,4})", s) or re.fullmatch(r"(\d{2})(\d{2})(\d{4})", s)
        if m:
            d, mo, y = m.groups()
        else:
            m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
            if not m:
                continue
            y, mo, d = m.groups()
        if len(y) == 2:
            y = ("19" if int(y) > 30 else "20") + y
        out.append((d.zfill(2), mo.zfill(2), y))
    return out


def password_candidates(passwords: list, hints: dict) -> list[str]:
    """
    Typed passwords first, then common formats built from client details:
    PAN, PAN + date of birth/incorporation (DDMMYYYY) as used for 26AS, AIS,
    ITR-V and intimations, and name/mobile + date combinations used by banks.
    """
    out: list[str] = []

    def add(v):
        for x in (v, v.upper(), v.lower()):
            if x and x not in out:
                out.append(x)

    for p in passwords:
        add(p.strip())
    pans = [p.strip() for p in hints.get("pans", []) if p.strip()]
    names = [re.sub(r"[^A-Za-z ]", "", n).strip() for n in hints.get("names", []) if n.strip()]
    mobiles = [D.digits(m)[-10:] for m in hints.get("mobiles", []) if len(D.digits(m)) >= 10]
    ids = [i.strip() for i in hints.get("ids", []) if i.strip()]
    dates = _parse_dates(hints.get("dates", []))
    for pan in pans:
        add(pan)
    for d, m, y in dates:
        ddmmyyyy, ddmmyy, ddmm = d + m + y, d + m + y[2:], d + m
        for pan in pans:
            add(pan.lower() + ddmmyyyy)
        for n in names:
            first = n.split()[0] if n.split() else ""
            n4 = first[:4]
            for nn in {n4, first}:
                if len(nn) >= 3:
                    for suffix in (ddmm, ddmmyy, ddmmyyyy):
                        add(nn.lower() + suffix)
                        add(nn.upper() + suffix)
                        add(nn.capitalize() + suffix)
        for mob in mobiles:
            for tail in (mob[-4:], mob[-5:]):
                add(tail + ddmmyy)
                add(tail + ddmm)
        add(ddmmyyyy)
        add(ddmmyy)
    for mob in mobiles:
        add(mob)
    for i in ids:
        add(i)
    return out


# --------------------------------------------------------------------------
# Batch context: consistent labels + values to propagate
# --------------------------------------------------------------------------
@dataclass
class BatchContext:
    tokens: dict = field(default_factory=dict)      # norm key -> label
    entries: dict = field(default_factory=dict)     # norm key -> info
    patterns: list = field(default_factory=list)    # [(rule, value, compiled regex)]
    counters: dict = field(default_factory=dict)

    def _new(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}-{self.counters[prefix]}"

    def token(self, rule: str, value: str) -> str:
        if rule in D.VISUAL_RULES:
            return D.CATEGORY[rule][1]
        if rule == "MANUAL" and value.startswith("box "):
            return "REDACTED"
        key = D.norm_key(rule, value)
        tok = self.tokens.get(key)
        if tok is None:
            tok = self._new(D.CATEGORY.get(rule, ("name", "TERM", 9))[1])
            self.tokens[key] = tok
            self.entries[key] = {"rule": rule, "values": {value}, "files": set(), "label": tok}
        return tok

    def key_rows(self) -> list[dict]:
        rows = []
        for key, info in self.entries.items():
            rows.append({
                "Label": info["label"],
                "Type": D.rule_label(info["rule"]),
                "Original value(s)": " | ".join(sorted(info["values"]))[:500],
                "Files": len(info["files"]),
            })
        rows.sort(key=lambda r: (r["Label"].split("-")[0], int(r["Label"].split("-")[-1])
                                 if r["Label"].split("-")[-1].isdigit() else 0))
        return rows


def build_context(scans: list[FileScan], opts: Options) -> BatchContext:
    ctx = BatchContext()
    grouped: dict = {}
    order = []
    for scan in scans:
        for f in scan.findings:
            if f.rule in D.VISUAL_RULES:
                continue
            key = D.norm_key(f.rule, f.value)
            if not key[1]:
                continue
            if key not in grouped:
                grouped[key] = {"rules": set(), "values": set(), "files": set()}
                order.append(key)
            g = grouped[key]
            g["rules"].add(f.rule)
            g["values"].add(f.value.strip())
            g["files"].add(scan.name)

    # masked numbers (XXXX7788) take the label of the one full number ending alike
    alias = {}
    nums = [k for k in order if k[0] == "num"]
    for k in order:
        if k[0] != "masked":
            continue
        tail = re.search(r"(\d{3,6})$", k[1])
        if tail:
            hits = [n for n in nums if n[1].endswith(tail.group(1))]
            if len(hits) == 1:
                alias[k] = hits[0]

    for key in order:
        if key in alias:
            continue
        g = grouped[key]
        best = min(g["rules"], key=lambda r: D.CATEGORY.get(r, ("", "", 9))[2])
        label = ctx._new(D.CATEGORY.get(best, ("name", "TERM", 9))[1])
        ctx.tokens[key] = label
        ctx.entries[key] = {"rule": best, "values": set(g["values"]), "files": set(g["files"]), "label": label}
        if opts.propagate:
            for v in sorted(g["values"], key=len, reverse=True)[:4]:
                rx = D.propagation_pattern(best, v)
                if rx is not None:
                    ctx.patterns.append((best, v, rx))
    for k, target in alias.items():
        ctx.tokens[k] = ctx.tokens[target]
        ctx.entries[target]["values"] |= grouped[k]["values"]
    return ctx


# --------------------------------------------------------------------------
# Workers (module-level so that they can run in other processes)
# --------------------------------------------------------------------------
def _scan_job(name: str, data: bytes, opts: Options, candidates: list) -> FileScan:
    ext = Path(name).suffix.lower()
    if ext in office.OFFICE_EXT:
        s = office.scan_office(name, data, opts)
    else:
        s = pdf.scan_pdf(name, data, opts, candidates)
    return s


def _redact_job(scan: FileScan, opts: Options, ctx: BatchContext, ov: Overrides | None) -> FileResult:
    if scan.status != "ok":
        return FileResult(name=scan.name, kind=scan.kind, status=scan.status, message=scan.message,
                          profile=scan.profile)
    if scan.kind == "pdf":
        return pdf.redact_pdf(scan, opts, ctx, ov)
    return office.redact_office(scan, opts, ctx, ov)


def _run_parallel(jobs, fn, workers, on_done):
    """jobs: list of argument tuples. Returns results in job order."""
    results = [None] * len(jobs)
    if workers > 1 and len(jobs) > 1:
        try:
            import multiprocessing as mp
            with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as ex:
                futs = {ex.submit(fn, *args): i for i, args in enumerate(jobs)}
                for fut in as_completed(futs):
                    i = futs[fut]
                    results[i] = fut.result()
                    on_done(i, results[i])
            return results
        except Exception:
            results = [None] * len(jobs)          # fall back to one process
    for i, args in enumerate(jobs):
        results[i] = fn(*args)
        on_done(i, results[i])
    return results


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
@dataclass
class Batch:
    opts: Options
    scans: list = field(default_factory=list)
    ctx: BatchContext | None = None
    results: list = field(default_factory=list)
    overrides: dict = field(default_factory=dict)
    originals: dict = field(default_factory=dict)
    started: str = ""
    finished: str = ""


def unique_names(files: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    seen: dict = {}
    out = []
    for name, data in files:
        n = name
        if n in seen:
            seen[name] += 1
            stem, ext = os.path.splitext(name)
            n = f"{stem} ({seen[name]}){ext}"
        else:
            seen[name] = 0
        out.append((n, data))
    return out


def run_batch(files: list[tuple[str, bytes]], opts: Options, progress=None) -> Batch:
    """files: [(name, bytes)]. progress(stage, done, total, name)."""
    progress = progress or (lambda *a: None)
    files = [(n, d) for n, d in unique_names(files) if Path(n).suffix.lower() in SUPPORTED_EXT]
    b = Batch(opts=opts, started=datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
    b.originals = {n: d for n, d in files}
    candidates = password_candidates(opts.passwords, opts.password_hints)
    total = len(files)
    done = [0]

    def tick(stage):
        def f(i, res):
            done[0] += 1
            progress(stage, done[0], total, files[i][0])
        return f

    b.scans = _run_parallel([(n, d, opts, candidates) for n, d in files], _scan_job, opts.workers, tick("Reading"))
    b.ctx = build_context(b.scans, opts)
    done[0] = 0
    b.results = _run_parallel([(s, opts, b.ctx, None) for s in b.scans], _redact_job, opts.workers, tick("Redacting"))
    for r, (n, d) in zip(b.results, files):
        r.sha_in = hashlib.sha256(d).hexdigest()
    b.finished = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    return b


def redo_file(b: Batch, name: str, ov: Overrides) -> FileResult:
    """Re-run pass 2 for one file with manual touch-ups (labels stay consistent)."""
    i = next(i for i, s in enumerate(b.scans) if s.name == name)
    b.overrides[name] = ov
    res = _redact_job(b.scans[i], b.opts, b.ctx, ov)
    res.sha_in = b.results[i].sha_in
    b.results[i] = res
    return res


def redo_all(b: Batch, progress=None) -> None:
    """Re-run pass 2 for every file (after a batch-wide word or keep-value change)."""
    progress = progress or (lambda *a: None)
    for t in b.opts.custom_terms:              # register labels first so workers agree
        if t.strip():
            b.ctx.token("CUSTOM", t)
    jobs = [(s, b.opts, b.ctx, b.overrides.get(s.name)) for s in b.scans]
    done = [0]

    def tick(i, res):
        done[0] += 1
        progress("Re-applying", done[0], len(jobs), b.scans[i].name)

    new = _run_parallel(jobs, _redact_job, b.opts.workers, tick)
    for i, r in enumerate(new):
        r.sha_in = b.results[i].sha_in
    b.results = new
