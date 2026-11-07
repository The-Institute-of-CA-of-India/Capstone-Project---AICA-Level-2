"""Local web server for the browser front end.

Listens on 127.0.0.1 only. Every /api call must carry the one-time key created at start-up
(header ``X-Mukhota-Key``, or ``?k=`` for page images), and the Host header must be this
server's own address, so other computers and other web pages cannot use it.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import fitz

from .. import APP_NAME, FULL_TITLE, TAGLINE, VERSION
from ..core import ai, detectors, ingest, redact, register, verify
from ..core.allowlist import Allowlist
from ..core.config import resolve_path
from ..core.models import Candidate, PageInfo, UserFacingError, colour_for, mask_value
from ..gui.icon import ensure_icon
from .cases import register_folder, register_list, register_update, reminder
from .draft import Draft, open_draft, pick_folder, settings_get, settings_save

log = logging.getLogger("mukhota.web")
STATIC = Path(__file__).resolve().parent / "static"
PREVIEW_SCALE = 2.0  # page images render at 144 DPI
IDLE_SHUTDOWN = 300  # seconds without any request from the page
PACKAGE = Path(__file__).resolve().parent.parent
STARTED = time.time()
_stale = {"checked": 0.0, "value": False}


def code_updated() -> bool:
    """True once Mukhota's program files change after this engine started (it must be restarted to use them)."""
    now = time.time()
    if not _stale["value"] and now - _stale["checked"] > 15:
        _stale["checked"] = now
        try:
            _stale["value"] = any(p.stat().st_mtime > STARTED for p in PACKAGE.rglob("*.py"))
        except OSError:
            pass
    return _stale["value"]
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".png": "image/png", ".ico": "image/x-icon"}
SHORT_CHECKS = ["Text layer", "OCR re-read", "Variants & tails", "Detectors re-run", "Metadata", "Page coverage"]

_dialog_lock = threading.Lock()


def pick_file(title: str, patterns: list[tuple[str, str]]) -> Path | None:
    """Native Windows file picker, opened by the engine so the real file location is known."""
    import tkinter as tk
    from tkinter import filedialog

    with _dialog_lock:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            path = filedialog.askopenfilename(parent=root, title=title, filetypes=patterns)
        finally:
            root.destroy()
    return Path(path) if path else None


class Session:
    """Everything the desktop main window kept: the open notice, candidates, results and the running job."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.lock = threading.RLock()
        self.src_path: Path | None = None
        self.preview_doc: fitz.Document | None = None
        self.after_doc: fitz.Document | None = None
        self._after_path: Path | None = None
        self.pages: list[PageInfo] = []
        self.candidates: list[Candidate] = []
        self.last_result: redact.RedactionResult | None = None
        self.last_output_pdf: Path | None = None
        self.verified = False
        self.banner: dict[str, Any] | None = None
        self._src_sha = ""
        self.allow = Allowlist()
        self.master: list[detectors.MasterEntry] = []
        self.busy = False
        self.pct = 0
        self.msg = "Ready. Open a notice PDF to begin."
        self.events: list[dict[str, Any]] = []
        self._seq = 0
        self.draft: Draft | None = None
        self.load_lists(report=False)

    # ------------------------------------------------------------------ helpers
    def event(self, kind: str, **payload: Any) -> None:
        """Queue a message for the page (error, info); the page picks it up on its next poll."""
        self._seq += 1
        self.events.append({"seq": self._seq, "kind": kind, **payload})
        self.events = self.events[-20:]

    def load_lists(self, report: bool = True) -> None:
        try:
            self.allow = Allowlist.load(resolve_path(self.cfg, "allowlist"))
            self.master = detectors.load_client_master(resolve_path(self.cfg, "client_master"))
        except UserFacingError as exc:
            if report:
                self.event("error", title="Settings", text=str(exc))
            else:
                log.warning("Allowlist or client master could not be loaded at start-up")

    def run(self, task_name: str, fn: Callable[[Callable[[int, str], None]], Any], on_ok: Callable[[Any], None]) -> None:
        """Run ``fn(progress)`` in a background thread; ``on_ok(result)`` runs under the session lock."""
        if self.busy:
            raise UserFacingError("Mukhota is still working on the previous step. Please wait for it to finish.")
        self.busy = True
        self.pct = 0
        self.msg = f"{task_name[0].upper()}{task_name[1:]}..."

        def progress(pct: int, msg: str = "") -> None:
            self.pct = int(pct)
            if msg:
                self.msg = msg

        def work() -> None:
            try:
                result = fn(progress)
            except UserFacingError as exc:
                log.warning("%s stopped with a user-facing error (%s)", task_name, type(exc.__cause__).__name__)
                err = str(exc)
            except MemoryError:
                log.exception("%s ran out of memory", task_name)
                err = f"Your computer ran out of memory while {task_name}. Try a smaller PDF or lower the DPI in Settings."
            except Exception:
                log.exception("%s failed", task_name)
                err = f"Something went wrong while {task_name}. The details were saved to logs\\mukhota.log."
            else:
                with self.lock:
                    self.busy = False
                    try:
                        on_ok(result)
                    except Exception:
                        log.exception("Finishing %s failed", task_name)
                        self.event("error", title=APP_NAME, text="Something went wrong. The details were saved to logs\\mukhota.log.")
                return
            with self.lock:
                self.busy = False
                self.pct = 0
                self.msg = "Stopped."
                self.event("error", title=APP_NAME, text=err)

        threading.Thread(target=work, name=task_name, daemon=True).start()

    def flow(self) -> dict[str, Any]:
        """Stepper position and the next-step button (same rules as the desktop window)."""
        if self.preview_doc is None:
            return {"done": -1, "label": "Open PDF", "action": "open"}
        if not self.candidates and self.last_result is None:
            return {"done": 0, "label": "Detect PII", "action": "detect"}
        if self.last_result is None:
            return {"done": 1, "label": "Apply redaction", "action": "apply"}
        if not self.verified:
            return {"done": 2, "label": "Verify", "action": "verify"}
        return {"done": 3, "label": "Draft reply", "action": "draft"}

    def _scene_rect(self, page: fitz.Page, rect) -> list[float]:
        r = fitz.Rect(rect) * page.rotation_matrix
        r.normalize()
        s = PREVIEW_SCALE
        return [round(r.x0 * s, 1), round(r.y0 * s, 1), round(r.width * s, 1), round(r.height * s, 1)]

    def _pdf_rect(self, page: fitz.Page, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        s = PREVIEW_SCALE
        r = fitz.Rect(x / s, y / s, (x + w) / s, (y + h) / s) * page.derotation_matrix
        r.normalize()
        return (r.x0, r.y0, r.x1, r.y1)

    def state(self, since: int = 0) -> dict[str, Any]:
        doc = self.preview_doc
        pages = []
        if doc is not None:
            for p in self.pages:
                rect = doc[p.index].rect
                pages.append({"index": p.index, "kind": p.kind, "needsReview": p.needs_review,
                              "reviewed": p.reviewed_no_pii,
                              "w": round(rect.width * PREVIEW_SCALE, 1), "h": round(rect.height * PREVIEW_SCALE, 1)})
        cands = []
        for c in self.candidates:
            boxes = []
            if doc is not None and c.page < doc.page_count:
                page = doc[c.page]
                boxes = [self._scene_rect(page, b) for b in c.bboxes]
            cands.append({"cid": c.cid, "page": c.page, "type": c.pii_type, "colour": colour_for(c.pii_type),
                          "value": mask_value(c.text, c.pii_type), "conf": round(c.confidence * 100),
                          "rule": c.rule_id, "role": c.role, "accepted": c.accepted, "boxes": boxes})
        has_after = self.last_output_pdf is not None and self.last_output_pdf.exists()
        return {
            "file": {"name": self.src_path.name, "pages": doc.page_count} if doc is not None and self.src_path else None,
            "pages": pages,
            "candidates": cands,
            "flow": self.flow(),
            "busy": self.busy, "pct": self.pct, "msg": self.msg,
            "hasOutput": self.last_result is not None or self.last_output_pdf is not None,
            "hasAfter": has_after,
            "afterVersion": str(self.last_output_pdf.stat().st_mtime) if has_after else "",
            "verified": self.verified,
            "banner": self.banner,
            "draft": self.draft.public() if self.draft else None,
            "updated": code_updated(),
            "events": [e for e in self.events if e["seq"] > since],
        }

    # ------------------------------------------------------------------ open
    def open_pdf(self) -> None:
        if self.busy:
            raise UserFacingError("Mukhota is still working on the previous step. Please wait for it to finish.")
        path = pick_file("Open notice PDF", [("PDF files", "*.pdf")])  # outside the lock: the picker waits for you
        if path is None:
            return
        data = ingest.read_pdf_bytes(path)
        doc = ingest.open_pdf_bytes(data)
        with self.lock:
            if self.busy:
                doc.close()
                raise UserFacingError("Mukhota is still working on the previous step. Please wait for it to finish.")
            self._reset_for(path, doc, data)
            log.info("Opened a PDF with %d pages", doc.page_count)
            cfg = copy.deepcopy(self.cfg)

            def task(progress):
                d = ingest.open_pdf_bytes(data)
                try:
                    return ingest.analyse(d, cfg, progress)
                finally:
                    d.close()

            self.run("reading the PDF", task, self._on_ingested)

    def _reset_for(self, path: Path, doc: fitz.Document, data: bytes) -> None:
        if self.preview_doc is not None:
            self.preview_doc.close()
        self.src_path = path
        self.preview_doc = doc
        self._src_sha = redact.sha256_bytes(data)
        self.pages = []
        self.candidates = []
        self.last_result = None
        self.last_output_pdf = None
        self.verified = False
        self.banner = None

    def _on_ingested(self, pages: list[PageInfo]) -> None:
        self.pages = pages
        first_pages_text = "\n".join(" ".join(w.text for w in p.words) for p in pages[:2])
        register.record_opened(self._src_sha, self.src_path.name, first_pages_text)
        flagged = sum(p.needs_review for p in pages)
        msg = f"Loaded {len(pages)} page(s)."
        if flagged:
            msg += f" {flagged} page(s) need manual review (low OCR confidence)."
        self.pct, self.msg = 100, msg + " Click Detect PII next."

    # ------------------------------------------------------------------ detect / manual
    def detect(self) -> None:
        if not self.pages or self.src_path is None:
            return
        self.load_lists()
        data = ingest.read_pdf_bytes(self.src_path)
        pages = copy.deepcopy(self.pages)
        cfg, allow, master = copy.deepcopy(self.cfg), self.allow, self.master

        def task(progress):
            d = ingest.open_pdf_bytes(data)
            try:
                return detectors.detect_all(d, pages, cfg, allow, master, progress)
            finally:
                d.close()

        self.run("detecting PII", task, self._on_detected)

    def _on_detected(self, result: detectors.DetectionResult) -> None:
        manual = [c for c in self.candidates if c.source == "manual"]
        self.candidates = result.candidates + manual
        acc = sum(c.accepted for c in self.candidates)
        self.pct, self.msg = 100, f"Found {len(result.candidates)} item(s); {acc} pre-ticked. Review the list, then Apply redaction."
        if result.warnings:
            self.event("info", title="Detect PII", text="\n".join(result.warnings))

    def set_accepted(self, cids: list[str], on: bool) -> None:
        wanted = set(cids)
        for c in self.candidates:
            if c.cid in wanted:
                c.accepted = on

    def set_reviewed(self, index: int, on: bool) -> None:
        if 0 <= index < len(self.pages):
            self.pages[index].reviewed_no_pii = on

    def add_box(self, index: int, x: float, y: float, w: float, h: float) -> None:
        if self.preview_doc is None or not (0 <= index < len(self.pages)) or w < 2 or h < 2:
            return
        rect = self._pdf_rect(self.preview_doc[index], x, y, w, h)
        text = redact.text_under_rect(self.preview_doc, self.pages[index], rect)
        self.candidates.append(Candidate(index, [rect], text, "MANUAL", 1.0, "MANUAL_BOX", source="manual"))
        self.msg = "Box added."

    def add_term(self, term: str) -> int:
        if self.preview_doc is None or not term.strip():
            return 0
        found = redact.find_term_occurrences(self.preview_doc, self.pages, term)
        self.candidates.extend(found)
        if found:
            self.msg = f"Added {len(found)} occurrence(s) of the term."
        return len(found)

    # ------------------------------------------------------------------ apply / verify
    def apply_summary(self) -> dict[str, Any]:
        """What the confirmation question needs to say before redacting."""
        if self.src_path is None:
            return {}
        _, out_pdf, _, _ = redact.output_paths(self.src_path, self.cfg)
        return {"accepted": sum(c.accepted for c in self.candidates),
                "pending": [p.index + 1 for p in self.pages if p.needs_review and not p.reviewed_no_pii],
                "replaces": out_pdf.exists()}

    def apply(self) -> None:
        if self.src_path is None or not self.pages:
            return
        src, pages, cands, cfg = self.src_path, copy.deepcopy(self.pages), copy.deepcopy(self.candidates), copy.deepcopy(self.cfg)
        self.banner = None
        self.run("applying redactions", lambda progress: redact.apply_redactions(src, pages, cands, cfg, progress), self._on_redacted)

    def _on_redacted(self, result: redact.RedactionResult) -> None:
        self.last_result = result
        self.last_output_pdf = result.pdf_path
        self.verified = False
        self._after_path = None
        client = next((c.text for c in self.candidates if c.accepted and c.role == "assessee"), None) or next(
            (c.text for c in self.candidates if c.accepted and c.pii_type in ("ORG", "NAME")), None)
        register.advance(self._src_sha, "Redacted", client=client, folder=result.folder)
        self.pct, self.msg = 100, "Redacted PDF saved. Verifying..."
        self._start_verify(result.pdf_path)

    def verify(self) -> None:
        target = self.last_output_pdf
        if target is None or not target.exists():
            target = pick_file("Choose a redacted PDF to verify", [("Redacted PDF", "*_REDACTED.pdf"), ("PDF files", "*.pdf")])
            if target is None:
                return
        with self.lock:
            self._start_verify(target)

    def _start_verify(self, pdf: Path) -> None:
        self.load_lists()
        cfg, allow, master = copy.deepcopy(self.cfg), self.allow, self.master
        self.last_output_pdf = pdf
        self.run("verifying the redacted PDF", lambda progress: verify.verify(pdf, cfg, allow, master, progress), self._on_verified)

    def _on_verified(self, report: verify.VerifyReport) -> None:
        self.verified = report.verified
        if report.verified:
            warns = [d for c in report.checks if c.status == verify.WARN for d in c.details]
            self.banner = {
                "ok": True,
                "title": "VERIFIED — SAFE TO SHARE",
                "chips": [{"status": c.status, "name": name} for name, c in zip(SHORT_CHECKS, report.checks)],
                "details": f"Report saved as verify_report.txt and .json  ·  SHA-256 {report.redacted_sha256[:4]}…{report.redacted_sha256[-4:]}",
                "notes": warns[:6], "leaks": [],
            }
        else:
            leaks, notes = [], []
            for c in report.checks:
                if c.status != verify.FAIL:
                    continue
                leaks += [{"page": lk["page"], "text": f"{lk['type']} ({lk['source']})"} for lk in c.leaks]
                notes += c.details
            self.banner = {"ok": False, "title": "VERIFICATION FAILED — DO NOT SHARE", "chips": [],
                           "details": "", "notes": notes[:25], "leaks": leaks[:25]}
        self.pct, self.msg = 100, f"Verification {'passed' if report.verified else 'FAILED'}. Reports saved in the output folder."
        if report.verified and self.last_result is not None and self._src_sha:
            register.advance(self._src_sha, "Verified")

    # ------------------------------------------------------------------ draft reply
    def draft_open(self) -> None:
        target = self.last_output_pdf
        if target is None or not target.exists():
            target = pick_file("Choose a verified redacted PDF", [("Redacted PDF", "*_REDACTED.pdf"), ("PDF files", "*.pdf")])
            if target is None:
                return
        d = open_draft(target, self.cfg)
        with self.lock:
            self.load_lists()
            self.draft = d

    def _need_draft(self) -> Draft:
        if self.draft is None:
            raise UserFacingError("Open Draft Reply first.")
        return self.draft

    def draft_preview(self, o: dict[str, Any]) -> None:
        d, allow, master = self._need_draft(), self.allow, self.master
        o = d.normalise(o)
        self.run("reading the redacted notice", lambda p: d.prepare_task(o, allow, master, p),
                 lambda prep: (d.apply_prepared(prep, o), setattr(self, "msg", d.info), setattr(self, "pct", 100)))

    def draft_prompt(self, o: dict[str, Any]) -> None:
        d, allow, master = self._need_draft(), self.allow, self.master
        o = d.normalise(dict(o, how="prompt"))
        self.run("making the prompt", lambda p: d.prepare_task(o, allow, master, p),
                 lambda prep: (d.apply_prompt(prep, o), setattr(self, "msg", d.info), setattr(self, "pct", 100)))

    def draft_estimate(self, o: dict[str, Any]) -> None:
        d, allow, master = self._need_draft(), self.allow, self.master
        o = d.normalise(o)
        ai.ensure_ready(d.cfg, o["model"])

        def done(res: dict[str, Any]) -> None:
            q = d.apply_estimate(res, o)
            self.pct, self.msg = 100, "Waiting for your OK to send."
            self.event("draft-confirm", text=q["text"], over=q["over"])

        self.run("estimating the cost", lambda p: d.estimate_task(o, allow, master, p), done)

    def draft_send(self, o: dict[str, Any]) -> None:
        d = self._need_draft()
        o = d.normalise(o)
        self.run("drafting the reply", lambda p: d.send_task(o, p),
                 lambda res: (d.apply_draft(res, o), setattr(self, "pct", 100),
                              setattr(self, "msg", "Draft received. Edit it, fill the placeholders, then Save as Word.")))

    # ------------------------------------------------------------------ images / misc
    def page_png(self, index: int, which: str) -> bytes | None:
        doc = self.preview_doc
        if which == "after":
            if self.last_output_pdf is None or not self.last_output_pdf.exists():
                return None
            if self._after_path != self.last_output_pdf or self.after_doc is None:
                if self.after_doc is not None:
                    self.after_doc.close()
                self.after_doc = ingest.load_document(self.last_output_pdf)
                self._after_path = self.last_output_pdf
            doc = self.after_doc
        if doc is None or not (0 <= index < doc.page_count):
            return None
        pix = doc[index].get_pixmap(matrix=fitz.Matrix(PREVIEW_SCALE, PREVIEW_SCALE), alpha=False)
        return pix.tobytes("png")

    def open_output_folder(self) -> None:
        folder = None
        if self.last_result is not None:
            folder = self.last_result.folder
        elif self.last_output_pdf is not None:
            folder = self.last_output_pdf.parent
        if folder and folder.exists():
            os.startfile(str(folder))  # noqa: S606 - opens Explorer locally


class App:
    """Server plus session; shuts itself down when the page has been closed for a while."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.session = Session(cfg)
        self.key = secrets.token_urlsafe(24)
        self.last_seen = time.monotonic()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(self))
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?k={self.key}"

    def quit(self) -> None:
        threading.Thread(target=self.httpd.shutdown, daemon=True).start()

    def _watchdog(self) -> None:
        while True:
            time.sleep(20)
            if not self.session.busy and time.monotonic() - self.last_seen > IDLE_SHUTDOWN:
                log.info("Browser page closed; stopping")
                self.quit()
                return

    def serve(self, open_browser: bool = True) -> None:
        threading.Thread(target=self._watchdog, daemon=True).start()
        if open_browser:
            webbrowser.open(self.url)
        log.info("%s %s web front end started", APP_NAME, VERSION)
        self.httpd.serve_forever()
        self.httpd.server_close()


def _make_handler(app: App):
    s = app.session

    class Handler(BaseHTTPRequestHandler):
        server_version = "Mukhota"

        def log_message(self, fmt: str, *args: Any) -> None:  # keep URLs (and the key) out of the log
            pass

        # -------------------------------------------------------------- plumbing
        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in (f"127.0.0.1:{app.port}", f"localhost:{app.port}")

        def _key_ok(self, query: dict[str, list[str]]) -> bool:
            given = self.headers.get("X-Mukhota-Key") or (query.get("k") or [""])[0]
            return secrets.compare_digest(given, app.key)

        def _send(self, code: int, body: bytes, ctype: str, extra: dict[str, str] | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj: Any, code: int = 200) -> None:
            self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

        def _error(self, text: str, code: int = 400) -> None:
            self._json({"error": text}, code)

        def _guard(self) -> tuple[str, dict[str, list[str]]] | None:
            url = urlparse(self.path)
            query = parse_qs(url.query)
            if not self._host_ok():
                self._send(403, b"Forbidden", "text/plain")
                return None
            if url.path.startswith("/api/") and not self._key_ok(query):
                self._send(403, b"Forbidden", "text/plain")
                return None
            app.last_seen = time.monotonic()
            return url.path, query

        # -------------------------------------------------------------- GET
        def do_GET(self) -> None:  # noqa: N802
            g = self._guard()
            if g is None:
                return
            path, q = g
            try:
                if path == "/api/state":
                    with s.lock:
                        self._json(s.state(int((q.get("since") or ["0"])[0])))
                elif path == "/api/info":
                    self._json({"app": APP_NAME, "title": FULL_TITLE, "tagline": TAGLINE, "version": VERSION})
                elif path == "/api/page.png":
                    with s.lock:
                        png = s.page_png(int((q.get("n") or ["0"])[0]), (q.get("which") or ["orig"])[0])
                    if png is None:
                        self._send(404, b"", "text/plain")
                    else:
                        self._send(200, png, "image/png")
                else:
                    self._static(path)
            except UserFacingError as exc:
                self._error(str(exc))
            except Exception:
                log.exception("Request failed")
                self._error("Something went wrong. The details were saved to logs\\mukhota.log.", 500)

        def _static(self, path: str) -> None:
            if path == "/logo.png":
                self._send(200, ensure_icon().with_suffix(".png").read_bytes(), "image/png")
                return
            name = "index.html" if path in ("/", "") else path.lstrip("/")
            target = (STATIC / name).resolve()
            if STATIC not in target.parents or not target.is_file():
                self._send(404, b"Not found", "text/plain")
                return
            self._send(200, target.read_bytes(), CONTENT_TYPES.get(target.suffix, "application/octet-stream"))

        # -------------------------------------------------------------- POST
        def do_POST(self) -> None:  # noqa: N802
            g = self._guard()
            if g is None:
                return
            path, _ = g
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if length else {}
                self._json(self._action(path, body) or {"ok": True})
            except UserFacingError as exc:
                self._error(str(exc))
            except (ValueError, KeyError, TypeError):
                self._error("That request was not understood.")
            except Exception:
                log.exception("Request failed")
                self._error("Something went wrong. The details were saved to logs\\mukhota.log.", 500)

        def _action(self, path: str, b: dict[str, Any]) -> dict[str, Any] | None:
            if path == "/api/open":
                # The file picker blocks; keep the session lock out of it.
                s.open_pdf()
                return None
            if path == "/api/quit":
                app.quit()
                return None
            if path == "/api/draft/open":
                s.draft_open()  # may open a file picker; takes the lock itself
                return None
            if path == "/api/settings/browse":
                return {"folder": pick_folder()}
            if path.startswith("/api/register") or path == "/api/reminder":
                return self._register(path, b)
            if path.startswith("/api/draft/") or path.startswith("/api/settings"):
                with s.lock:
                    return self._draft_settings(path, b)
            with s.lock:
                if path == "/api/detect":
                    s.detect()
                elif path == "/api/accept":
                    s.set_accepted(list(b["cids"]), bool(b["on"]))
                elif path == "/api/reviewed":
                    s.set_reviewed(int(b["page"]), bool(b["on"]))
                elif path == "/api/box":
                    s.add_box(int(b["page"]), float(b["x"]), float(b["y"]), float(b["w"]), float(b["h"]))
                elif path == "/api/term":
                    return {"found": s.add_term(str(b["term"]))}
                elif path == "/api/apply-summary":
                    return s.apply_summary()
                elif path == "/api/apply":
                    s.apply()
                elif path == "/api/verify":
                    pass
                elif path == "/api/output-folder":
                    s.open_output_folder()
                else:
                    raise KeyError(path)
            if path == "/api/verify":
                # May open a file picker; keep the session lock out of it.
                s.verify()
            return None

        def _register(self, path: str, b: dict[str, Any]) -> dict[str, Any] | None:
            if path == "/api/reminder":
                return {"reminder": reminder(s.cfg)}
            if path == "/api/register":
                return register_list()
            if path == "/api/register/update":
                register_update(b)
            elif path == "/api/register/delete":
                register.delete(int(b["id"]))
            elif path == "/api/register/folder":
                register_folder(int(b["id"]))
            else:
                raise KeyError(path)
            return register_list()

        def _draft_settings(self, path: str, b: dict[str, Any]) -> dict[str, Any] | None:
            if path == "/api/settings":
                return settings_get(s.cfg)
            if path == "/api/settings/save":
                s.cfg = settings_save(s.cfg, b)
                s.load_lists()
                s.msg = "Settings saved. Run Detect PII again to apply them."
                return None
            if path == "/api/settings/remove-key":
                pid = str(b.get("provider") or "claude")
                if pid == "claude" or pid in ai.PROVIDERS:
                    ai.clear_key(pid)
                return None
            if path == "/api/draft/close":
                if s.busy and s.draft is not None:
                    raise UserFacingError("Please wait for the current step to finish.")
                s.draft = None
                return None
            d = s._need_draft()
            o = b.get("opts") or {}
            if path == "/api/draft/preview":
                s.draft_preview(o)
            elif path == "/api/draft/prompt":
                s.draft_prompt(o)
            elif path == "/api/draft/prompt-save":
                return {"msg": d.save_prompt()}
            elif path == "/api/draft/paste":
                if s.busy:
                    raise UserFacingError("Please wait for the current step to finish.")
                d.paste_answer(str(b.get("text") or ""), d.normalise(dict(o, how="prompt"))["out"])
                s.msg = d.info
            elif path == "/api/draft/estimate":
                s.draft_estimate(o)
            elif path == "/api/draft/send":
                s.draft_send(o)
            elif path == "/api/draft/facts":
                return {"ay": d.ay, "client": d.client_name, "fields": d.facts_for(str(b.get("ay", d.ay)))}
            elif path == "/api/draft/facts-save":
                d.save_facts(str(b["ay"]).strip(), {k: str(v) for k, v in b["values"].items()},
                             {str(y): dict(v) for y, v in (b.get("years") or {}).items()})
            elif path == "/api/draft/save":
                return d.save({str(k): str(v) for k, v in b["sections"].items()},
                              {str(k): str(v) for k, v in b["values"].items()}, bool(b.get("remember")))
            elif path == "/api/draft/folder":
                d.open_folder()
            else:
                raise KeyError(path)
            return None

    return Handler
