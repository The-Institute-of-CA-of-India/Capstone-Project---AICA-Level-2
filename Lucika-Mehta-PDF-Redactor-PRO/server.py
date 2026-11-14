"""
PDF Redactor PRO - local server.

    python server.py            (opens http://127.0.0.1:8501 in the browser)

Listens on 127.0.0.1 only: nothing on the network can reach it and no file
leaves this computer.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import traceback
import webbrowser
from collections import OrderedDict
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from redact import batch as B
from redact import detect as D
from redact import outputs as O
from redact import pdf as P
from redact.model import APP_NAME, AUTHOR, CONTACT_EMAIL, CONTACT_PHONE, VERSION, Options, Overrides

from redact import paths as PATHS

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = PATHS.static_dir()
app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

CONFIG_FILE = PATHS.config_file()       # per-user, survives updates, never contains client data
_LEGACY_CONFIG = APP_DIR / "local_settings.json"
if not CONFIG_FILE.exists() and _LEGACY_CONFIG.exists():
    try:
        CONFIG_FILE.write_text(_LEGACY_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        pass


def _load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(cfg: dict) -> None:
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass


_CFG = _load_config()
if _CFG.get("tessdata") and Path(_CFG["tessdata"], "eng.traineddata").exists():
    os.environ["TESSDATA_PREFIX"] = _CFG["tessdata"]

LOCK = threading.RLock()
STATE: dict = {"batch": None, "folder": None, "job": {"running": False}}
_RENDER: OrderedDict = OrderedDict()
_ENV: dict = {}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def env(refresh: bool = False) -> dict:
    if not _ENV or refresh:
        _ENV.update(self_test=_ENV.get("self_test", None) if refresh else P.self_test(),
                    langs=P.ocr_languages(), ocr=P.find_tessdata() is not None, tessdata=P.find_tessdata() or "")
        if _ENV["self_test"] is None:
            _ENV["self_test"] = P.self_test()
    return _ENV


def batch() -> B.Batch:
    b = STATE["batch"]
    if b is None:
        raise HTTPException(404, "No batch yet")
    return b


def options_from(d: dict) -> Options:
    o = Options()
    o.rules = set(d.get("rules", D.DEFAULT_RULES))
    for k in ("profile", "style", "ocr_mode"):
        if d.get(k):
            setattr(o, k, d[k])
    for k in ("protect_itba_din", "propagate", "verify_scans", "add_text_layer", "scrub_metadata", "anonymise_names"):
        if k in d:
            setattr(o, k, bool(d[k]))
    o.custom_terms = [t.strip() for t in d.get("custom_terms", []) if t.strip()]
    o.keep_terms = [t.strip() for t in d.get("keep_terms", []) if t.strip()]
    o.passwords = [t.strip() for t in d.get("passwords", []) if t.strip()]
    o.password_hints = {k: [x for x in v if str(x).strip()] for k, v in d.get("password_hints", {}).items()}
    o.ocr_dpi = int(d.get("ocr_dpi", 300))
    o.ocr_langs = tuple(d.get("ocr_langs") or ["eng"])
    o.workers = max(1, min(int(d.get("workers", B.default_workers())), os.cpu_count() or 1))
    return o


def _job(fn, *args):
    """Run a long task in the background; progress is polled by the page."""
    job = {"running": True, "stage": "Starting", "done": 0, "total": 0, "name": "", "error": None}
    STATE["job"] = job

    def progress(stage, done, total, name):
        job.update(stage=stage, done=done, total=total, name=name)

    def run():
        try:
            fn(progress, *args)
        except Exception as exc:          # surfaced to the page
            job["error"] = f"{exc}"
            traceback.print_exc()
        finally:
            job["running"] = False
            _RENDER.clear()
    threading.Thread(target=run, daemon=True).start()


def _recheck(r) -> dict:
    if r.output is None:
        return {"state": "none", "text": "-"}
    n = r.residual + r.residual_ocr
    if n:
        return {"state": "warn", "text": f"{n} remain"}
    if r.layout_pages:
        return {"state": "warn", "text": "Layout moved"}
    return {"state": "ok", "text": "Clean"}


def _display(f) -> str:
    """Masked value for the panel; image items get a plain description."""
    if f.rule in D.VISUAL_RULES:
        m = __import__("re").search(r"p(\d+)-(\d+)", f.value)
        return f"{D.rule_short(f.rule)} on page {m.group(1)}" if m else D.rule_short(f.rule)
    return f.masked


def _group(rule: str) -> str:
    r = D.RULES_BY_KEY.get(rule)
    if rule in ("TO_NAME", "TO_ADDR"):
        return "names"
    return r.group if r else "custom"


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/meta")
def meta():
    e = env()
    return {
        "version": VERSION, "app": APP_NAME, "author": AUTHOR,
        "contact": {"phone": CONTACT_PHONE, "email": CONTACT_EMAIL},
        "self_test": e["self_test"], "ocr": e["ocr"], "langs": e["langs"] or ["eng"], "tessdata": e["tessdata"],
        "platform": os.name,
        "cpus": os.cpu_count() or 1, "default_workers": B.default_workers(),
        "groups": [{"key": g, "label": l} for g, l in D.GROUP_LABELS.items()],
        "rules": [{"key": r.key, "label": r.label, "group": r.group, "default": r.default_on} for r in D.RULES],
        "profiles": D.PROFILE_LABELS,
        "extensions": sorted(B.SUPPORTED_EXT),
        "has_batch": STATE["batch"] is not None,
        "mode": os.environ.get("REDACTOR_MODE", "browser"), "frozen": PATHS.FROZEN,
    }


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------
@app.post("/api/run")
async def run_files(files: list[UploadFile] = File(...), options: str = Form("{}")):
    if STATE["job"].get("running"):
        raise HTTPException(409, "A batch is already running")
    opts = options_from(json.loads(options))
    data = [(f.filename, await f.read()) for f in files]

    def work(progress):
        b = B.run_batch(data, opts, progress)
        with LOCK:
            STATE["batch"], STATE["folder"] = b, None
    _job(work)
    return {"ok": True, "files": len(data)}


@app.post("/api/run-folder")
def run_folder(payload: dict = Body(...)):
    if STATE["job"].get("running"):
        raise HTTPException(409, "A batch is already running")
    folder = payload.get("folder", "").strip().strip('"')
    try:
        found = O.collect_folder(folder, bool(payload.get("subfolders", True)), B.SUPPORTED_EXT)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    if not found:
        raise HTTPException(400, "No supported files were found in that folder.")
    opts = options_from(payload.get("options", {}))

    def work(progress):
        b = B.run_batch(found, opts, progress)
        with LOCK:
            STATE["batch"], STATE["folder"] = b, folder
    _job(work)
    return {"ok": True, "files": len(found)}


@app.post("/api/ocr/check")
def ocr_check(payload: dict = Body(default={})):
    """Re-detect Tesseract (after installing it), optionally from a folder the user names."""
    folder = (payload or {}).get("folder", "").strip().strip('"')
    if folder:
        cands = [Path(folder), Path(folder) / "tessdata", Path(folder).parent / "tessdata"]
        hit = next((c for c in cands if (c / "eng.traineddata").exists()), None)
        if hit is None:
            raise HTTPException(400, "No Tesseract language data (eng.traineddata) was found in that folder. "
                                     "Choose the Tesseract-OCR installation folder.")
        os.environ["TESSDATA_PREFIX"] = str(hit)
        _CFG["tessdata"] = str(hit)
        _save_config(_CFG)
    e = env(refresh=True)
    return {"ocr": e["ocr"], "langs": e["langs"] or ["eng"], "tessdata": e["tessdata"]}


LAST_PING = [0.0]          # last time an open window checked in (used to stop when every window is closed)


@app.post("/api/ping")
def ping():
    LAST_PING[0] = time.time()
    return {"ok": True}


@app.post("/api/quit")
def quit_app():
    """Used by the browser fallback (no app window): stops the program."""
    threading.Timer(0.4, lambda: os._exit(0)).start()
    return {"ok": True}


@app.get("/api/progress")
def progress():
    return STATE["job"]


@app.post("/api/reset")
def reset():
    with LOCK:
        STATE["batch"], STATE["folder"] = None, None
        _RENDER.clear()
    return {"ok": True}


# --------------------------------------------------------------------------
# Batch and files
# --------------------------------------------------------------------------
@app.get("/api/batch")
def batch_summary():
    b = batch()
    names = O.output_names(b)
    files = []
    for i, r in enumerate(b.results):
        files.append({
            "index": i, "name": r.name, "kind": r.kind, "output": names.get(r.name),
            "profile": r.profile, "profile_label": D.PROFILE_LABELS.get(r.profile, r.profile),
            "pages": r.pages, "ocr_pages": r.ocr_pages, "items": len(r.findings),
            "status": r.status, "status_text": O.STATUS_TEXT.get(r.status, r.status),
            "message": r.message.strip(), "recheck": _recheck(r),
            "edited": r.name in b.overrides,
        })
    return {
        "files": files, "folder": STATE["folder"], "style": b.opts.style,
        "started": b.started, "finished": b.finished,
        "totals": {
            "files": len(files), "redacted": sum(1 for r in b.results if r.output is not None),
            "pages": sum(r.pages for r in b.results), "items": sum(len(r.findings) for r in b.results),
            "attention": sum(1 for f in files if f["status"] != "ok" or f["recheck"]["state"] == "warn"),
        },
        "batch_terms": b.opts.custom_terms, "batch_keep": b.opts.keep_terms,
    }


@app.get("/api/file/{i}")
def file_detail(i: int):
    b = batch()
    if not 0 <= i < len(b.results):
        raise HTTPException(404)
    r, s = b.results[i], b.scans[i]
    ov = b.overrides.get(r.name, Overrides())
    agg: "OrderedDict" = OrderedDict()

    def add(f, state):
        k = (f.rule, f.value, state)
        if k not in agg:
            agg[k] = {"rule": f.rule, "type": D.rule_label(f.rule), "short": D.rule_short(f.rule),
                      "group": _group(f.rule), "label": f.label,
                      "value": f.value, "masked": _display(f), "state": state, "pages": [], "boxes": [],
                      "where": []}
        a = agg[k]
        if f.page and f.page not in a["pages"]:
            a["pages"].append(f.page)
        a["boxes"] += [{"page": f.page, "box": list(bx)} for bx in f.boxes]
        if f.where and f.where not in ("file", "batch") and len(a["where"]) < 5:
            a["where"].append(f.where)

    for f in r.findings:
        if f.rule == "MANUAL" and f.value.startswith("box "):
            continue
        add(f, "redacted")
    for f in r.kept:
        add(f, "kept-batch" if f.where == "batch" else "kept-file")
    if r.kind != "pdf":                        # office: kept values are not re-detected
        for v in ov.keep_values:
            if not any(a["value"] == v for a in agg.values()):
                f = next((x for x in s.findings if x.value == v), None)
                if f:
                    add(f, "kept-file")
    findings = list(agg.values())
    for n, f in enumerate(findings):
        f["id"] = n

    manual = []
    if r.kind == "pdf" and s.pdf_bytes:
        for j, (p0, rect) in enumerate(ov.boxes):
            manual.append({"id": j, "page": p0 + 1, "box": list(P.page_to_view_box(s.pdf_bytes, p0, rect))})

    sizes = P.page_sizes(s.pdf_bytes) if (r.kind == "pdf" and s.pdf_bytes) else []
    return {
        "index": i, "name": r.name, "kind": r.kind, "profile_label": D.PROFILE_LABELS.get(r.profile, r.profile),
        "pages": r.pages, "page_sizes": sizes, "ocr_pages": r.ocr_pages, "status": r.status,
        "status_text": O.STATUS_TEXT.get(r.status, r.status), "message": r.message.strip(),
        "recheck": _recheck(r),
        "residual": [{"page": p, "type": D.rule_label(k), "masked": v} for p, k, v in r.residual_notes],
        "layout_pages": r.layout_pages, "findings": findings, "manual": manual, "terms": ov.terms,
        "text": r.text_export[:30000] if r.kind != "pdf" else "", "sha_in": r.sha_in, "sha_out": r.sha_out,
        "output": O.output_names(b).get(r.name),
    }


@app.get("/api/file/{i}/page/{p}")
def page_image(i: int, p: int, which: str = "redacted", dpi: int = 110):
    b = batch()
    r, s = b.results[i], b.scans[i]
    src = r.output if which == "redacted" else s.pdf_bytes
    if r.kind != "pdf" or not src:
        raise HTTPException(404)
    dpi = max(50, min(dpi, 300))
    key = (i, p, which, dpi, len(src), r.sha_out)
    png = _RENDER.get(key)
    if png is None:
        png = P.render_page(src, p - 1, dpi)
        if png is None:
            raise HTTPException(404)
        _RENDER[key] = png
        if len(_RENDER) > 120:
            _RENDER.popitem(last=False)
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.post("/api/file/{i}/apply")
def apply_file(i: int, payload: dict = Body(...)):
    """Manual touch-ups for one file: values to keep visible, words and boxes to add."""
    b = batch()
    r, s = b.results[i], b.scans[i]
    boxes = []
    for bx in payload.get("boxes", []):
        p0 = int(bx["page"]) - 1
        if r.kind == "pdf" and s.pdf_bytes:
            boxes.append((p0, P.view_to_page_rect(s.pdf_bytes, p0, bx["box"])))
    ov = Overrides(keep_values=set(payload.get("keep_values", [])),
                   terms=[t.strip() for t in payload.get("terms", []) if t.strip()],
                   boxes=boxes)
    with LOCK:
        if not ov.keep_values and not ov.terms and not ov.boxes:
            b.overrides.pop(r.name, None)
            res = B._redact_job(b.scans[i], b.opts, b.ctx, None)
            res.sha_in = r.sha_in
            b.results[i] = res
        else:
            B.redo_file(b, r.name, ov)
        _RENDER.clear()
    return file_detail(i)


@app.post("/api/file/{i}/text-in-box")
def text_in_box(i: int, payload: dict = Body(...)):
    b = batch()
    s = b.scans[i]
    if s.kind != "pdf" or not s.pdf_bytes:
        return {"text": ""}
    p0 = int(payload["page"]) - 1
    text = P.text_in_box(s.pdf_bytes, p0, payload["box"])
    if not text and any(src.kind == "ocr" for src in s.pages[p0].sources):
        # scanned page: use the OCR text read in pass 1
        import pymupdf
        rect = pymupdf.Rect(P.view_to_page_rect(s.pdf_bytes, p0, payload["box"]))
        src = next(x for x in s.pages[p0].sources if x.kind == "ocr")
        chars = [c for c, bx in zip(src.text, src.boxes) if bx and pymupdf.Rect(bx).intersects(rect)]
        text = " ".join("".join(chars).split())
    return {"text": text[:200]}


@app.post("/api/batch/update")
def batch_update(payload: dict = Body(...)):
    """Batch-wide words to redact / values to keep visible in every file."""
    b = batch()
    if STATE["job"].get("running"):
        raise HTTPException(409, "Busy")
    with LOCK:
        for t in payload.get("add_terms", []):
            if t.strip() and t.strip() not in b.opts.custom_terms:
                b.opts.custom_terms.append(t.strip())
        for t in payload.get("remove_terms", []):
            if t in b.opts.custom_terms:
                b.opts.custom_terms.remove(t)
        for t in payload.get("add_keep", []):
            if t.strip() and t.strip() not in b.opts.keep_terms:
                b.opts.keep_terms.append(t.strip())
        for t in payload.get("remove_keep", []):
            if t in b.opts.keep_terms:
                b.opts.keep_terms.remove(t)

    def work(progress):
        with LOCK:
            B.redo_all(b, progress)
    _job(work)
    return {"ok": True}


# --------------------------------------------------------------------------
# Downloads
# --------------------------------------------------------------------------
def _zip_response(data: bytes, name: str):
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/download/ai")
def download_ai(text: int = 1, tables: int = 1, combined: int = 0):
    return _zip_response(O.ai_zip(batch(), bool(text), bool(tables), bool(combined)), "redacted_files.zip")


@app.get("/api/download/records")
def download_records(client: str = "", ai_tool: str = ""):
    return _zip_response(O.records_zip(batch(), {"client": client, "ai_tool": ai_tool}), "redaction_records_KEEP_LOCAL.zip")


@app.get("/api/download/certificate")
def download_certificate(client: str = "", ai_tool: str = ""):
    data = O.certificate_pdf(batch(), {"client": client, "ai_tool": ai_tool})
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="Redaction_certificate.pdf"'})


def _file_item(b, i: int, kind: str):
    """(filename, bytes, media type) for one downloadable output of file i, or None."""
    r = b.results[i]
    if r.output is None:
        return None
    base = Path(O.output_names(b)[r.name]).name
    stem = Path(base).stem
    if kind == "file":
        media = {".pdf": "application/pdf", ".csv": "text/csv"}.get(r.output_ext, "application/octet-stream")
        return base, r.output, media
    if kind == "text" and r.text_export and r.kind in ("pdf", "docx"):
        return f"{stem}.txt", r.text_export.encode("utf-8"), "text/plain; charset=utf-8"
    if kind == "tables":
        t = O.table_csv(r)
        if t:
            return f"{stem}{t[0]}", t[1], "text/csv; charset=utf-8"
    return None


@app.get("/api/file/{i}/download")
def download_file(i: int, kind: str = "file"):
    item = _file_item(batch(), i, kind)
    if item is None:
        raise HTTPException(404, "Nothing to download for this file.")
    name, data, media = item
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/download/plan")
def download_plan(text: int = 1, tables: int = 1, combined: int = 0):
    """One redacted file -> its own file(s) directly; several -> one ZIP."""
    b = batch()
    done = [i for i, r in enumerate(b.results) if r.output is not None]
    if not done:
        raise HTTPException(400, "No redacted files to download.")
    if len(done) > 1:
        notes = []
        if tables:
            n = sum(1 for i in done if O.table_csv(b.results[i]))
            notes.append(f"Transaction tables (CSV) made for {n} of {len(done)} files." if n
                         else "No bank transaction table was recognised, so no CSV was made.")
        return {"mode": "zip", "count": len(done), "notes": notes,
                "items": [{"name": "redacted_files.zip",
                           "url": f"/api/download/ai?text={text}&tables={tables}&combined={combined}"}]}
    i = done[0]
    kinds = ["file"] + (["text"] if text else []) + (["tables"] if tables else [])
    items = []
    notes = []
    for k in kinds:
        it = _file_item(b, i, k)
        if it:
            items.append({"name": it[0], "url": f"/api/file/{i}/download?kind={k}"})
        elif k == "tables":
            notes.append("No bank transaction table was recognised in this file, so no CSV was made.")
    return {"mode": "files", "count": 1, "items": items, "notes": notes}


@app.post("/api/folder/save")
def folder_save(payload: dict = Body(...)):
    b = batch()
    if not STATE["folder"]:
        raise HTTPException(400, "This batch did not come from a folder.")
    out_dir, rec_dir = O.write_folder_outputs(b, STATE["folder"], bool(payload.get("text", True)),
                                              bool(payload.get("tables", True)), bool(payload.get("combined", False)),
                                              {"client": payload.get("client", ""), "ai_tool": payload.get("ai_tool", "")})
    return {"out": str(out_dir), "records": str(rec_dir)}


@app.exception_handler(Exception)
def on_error(request, exc):
    traceback.print_exc()
    return JSONResponse({"detail": str(exc)}, status_code=500)


# --------------------------------------------------------------------------
def _free_port(preferred: int) -> int:
    for port in [preferred] + list(range(preferred + 1, preferred + 50)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


def main():
    import uvicorn
    port = _free_port(int(os.environ.get("REDACTOR_PORT", 8501)))
    url = f"http://127.0.0.1:{port}"
    print(f"\n  PDF Redactor PRO v{VERSION} is running at {url}\n  Keep this window open while you work; close it to stop.\n")
    if not os.environ.get("REDACTOR_NO_BROWSER"):
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
