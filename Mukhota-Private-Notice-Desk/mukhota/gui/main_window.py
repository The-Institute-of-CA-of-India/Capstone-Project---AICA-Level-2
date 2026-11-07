"""Mukhota main window: header, toolbar, page preview, candidate list, banner and status bar."""
from __future__ import annotations

import copy
import logging
import os
from pathlib import Path
from typing import Any

import fitz
from PyQt6.QtCore import QByteArray, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, FULL_TITLE, TAGLINE
from ..core import detectors, drafting, ingest, redact, register, verify
from ..core.allowlist import Allowlist
from ..core.config import resolve_path
from ..core.models import Candidate, PageInfo, UserFacingError, colour_for, mask_value
from .candidate_panel import CandidatePanel
from .dialogs import SettingsDialog, show_about, show_error, show_info
from .page_view import PageView
from .reply_dialog import ReplyDialog
from .work_dialogs import RegisterDialog, notify_due
from .workers import TaskWorker

log = logging.getLogger("mukhota.gui")
PREVIEW_SCALE = 2.0  # preview renders at 144 DPI


# Line icons on a 24-unit grid, matching the HTML design (no image files).
ICON_PATHS = {
    "open": "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    "detect": "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-5-5",
    "draw": "M4 4h16v16H4zM8 8h8v8H8z",
    "term": "M4 7h16M4 12h10M4 17h7M17 15v6M14 18h6",
    "apply": "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z",
    "verify": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM8 12l3 3 5-6",
    "reply": "M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13h8M8 17h5",
    "folder": "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM12 11v5M9.5 13.5h5",
    "register": "M9 3h6v3H9zM7 4.5H5V21h14V4.5h-2M8 11h8M8 15h8M8 18.5h5",
    "settings": "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1",
    "about": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v6M12 7.5v.5",
}


def _line_pixmap(path: str, colour: str, size: int) -> QPixmap:
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
           f'stroke="{colour}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="{path}"/></svg>')
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(p, QRectF(0, 0, size, size))
    p.end()
    return pm


def line_icon(name: str, size: int = 60) -> QIcon:
    """Toolbar line icon: indigo normally, white when checked (teal button), grey when disabled."""
    path = ICON_PATHS[name]
    icon = QIcon()
    icon.addPixmap(_line_pixmap(path, "#2E3A8C", size), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_line_pixmap(path, "#FFFFFF", size), QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(_line_pixmap(path, "#A9AECB", size), QIcon.Mode.Disabled, QIcon.State.Off)
    return icon


def _page_sizes(doc: fitz.Document) -> list[tuple[float, float]]:
    """Each page's size in preview pixels (rotation applied)."""
    return [(page.rect.width * PREVIEW_SCALE, page.rect.height * PREVIEW_SCALE) for page in doc]


def _page_loader(doc: fitz.Document):
    """Renders one page of ``doc`` for the preview, when it scrolls into view."""
    def load(index: int) -> QImage:
        pix = doc[index].get_pixmap(matrix=fitz.Matrix(PREVIEW_SCALE, PREVIEW_SCALE), alpha=False)
        return QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
    return load


def _repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)


class HeaderBar(QWidget):
    """Deep-indigo header: logo and name, open file pill, offline badge, tagline."""

    def __init__(self, icon: QIcon, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("header")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(44)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 3, 16, 3)
        lay.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(icon.pixmap(30, 30))
        names = QVBoxLayout()
        names.setSpacing(0)
        name = QLabel(APP_NAME)
        name.setObjectName("headerTitle")
        sub = QLabel("Private Notice Desk")
        sub.setObjectName("headerSub")
        names.addWidget(name)
        names.addWidget(sub)
        self.file_pill = QLabel("No notice open")
        self.file_pill.setObjectName("filePill")
        self.net_badge = QLabel("●  Offline")
        self.net_badge.setObjectName("netBadge")
        self.net_badge.setToolTip("Redaction and verification never use the network. Only Draft Reply contacts the Claude API.")
        tag = QLabel(TAGLINE.upper())
        tag.setObjectName("headerTag")
        lay.addWidget(logo)
        lay.addLayout(names)
        lay.addSpacing(12)
        lay.addWidget(self.file_pill)
        lay.addStretch(1)
        lay.addWidget(self.net_badge)
        lay.addSpacing(8)
        lay.addWidget(tag)

    def set_file(self, name: str, pages: int) -> None:
        self.file_pill.setText(f"{name}  ·  {pages} page{'s' if pages != 1 else ''}")


class StepBar(QFrame):
    """Progress stepper (Open → Detect & review → Redact → Verify → Draft reply) with the next-step button."""

    STEPS = ["Open", "Detect & review", "Redact", "Verify", "Draft reply"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("stepBar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 3, 16, 3)
        lay.setSpacing(8)
        self._dots: list[QLabel] = []
        self._texts: list[QLabel] = []
        for i, label in enumerate(self.STEPS):
            dot = QLabel(str(i + 1))
            dot.setObjectName("stepDot")
            text = QLabel(label)
            text.setObjectName("stepText")
            lay.addWidget(dot)
            lay.addWidget(text)
            if i < len(self.STEPS) - 1:
                line = QFrame()
                line.setObjectName("stepLine")
                lay.addSpacing(4)
                lay.addWidget(line)
                lay.addSpacing(4)
            self._dots.append(dot)
            self._texts.append(text)
        lay.addStretch(1)
        self.primary = QPushButton("Open PDF")
        self.primary.setObjectName("primaryButton")
        self.primary.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.primary)

    def set_done(self, done_upto: int) -> None:
        """Steps 0..done_upto are complete; the next one is current."""
        for i, (dot, text) in enumerate(zip(self._dots, self._texts)):
            state = "done" if i <= done_upto else "current" if i == done_upto + 1 else "todo"
            dot.setText("✓" if state == "done" else str(i + 1))
            for w in (dot, text):
                w.setProperty("state", state)
                _repolish(w)


class MainWindow(QMainWindow):
    """The single Mukhota window."""

    def __init__(self, cfg: dict[str, Any], icon: QIcon) -> None:
        super().__init__()
        self.cfg = cfg
        self.icon = icon
        self.setWindowTitle(FULL_TITLE)
        self.setWindowIcon(icon)
        self.resize(1440, 900)

        self.src_path: Path | None = None
        self.preview_doc: fitz.Document | None = None
        self.pages: list[PageInfo] = []
        self.candidates: list[Candidate] = []
        self.current = 0
        self.selected_cid = ""
        self.last_result: redact.RedactionResult | None = None
        self.last_output_pdf: Path | None = None
        self._worker: TaskWorker | None = None
        self._running = False
        self.allow = Allowlist()
        self.master: list[detectors.MasterEntry] = []
        self._load_lists(show=False)

        self._verified = False
        self._primary_action = None
        self._src_sha = ""
        self.after_doc: fitz.Document | None = None
        self._after_path: Path | None = None

        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.header = HeaderBar(icon)
        outer.addWidget(self.header)
        self.stepbar = StepBar()
        self.stepbar.primary.clicked.connect(lambda: self._primary_action and self._primary_action())
        outer.addWidget(self.stepbar)

        body = QHBoxLayout()
        body.setContentsMargins(10, 8, 10, 6)
        body.setSpacing(10)
        body.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_centre())
        self.panel = CandidatePanel()
        self.panel.changed.connect(self._refresh_overlays)
        self.panel.activated.connect(self._jump_to_candidate)
        self.side_tabs = QTabWidget()
        self.side_tabs.addTab(self.panel, "Detected items")
        self.side_tabs.addTab(self._build_draft_tab(), "Draft reply")
        splitter.addWidget(self.side_tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([860, 470])
        body.addWidget(splitter, 1)
        outer.addLayout(body, 1)
        self.setCentralWidget(root)

        sb = QStatusBar()
        self.status_label = QLabel("Ready. Open a notice PDF to begin.")
        self.progress = QProgressBar()
        self.progress.setFixedWidth(280)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        sb.addWidget(self.status_label, 1)
        sb.addPermanentWidget(self.progress)
        self.setStatusBar(sb)
        self._update_enabled()

    # ================================================================== layout
    def _build_toolbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("toolbar")
        bar.setFixedWidth(200)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(10, 12, 10, 12)
        lay.setSpacing(6)

        def btn(text: str, icon: str, slot, checkable: bool = False) -> QPushButton:
            # One row per tool: icon on the left, label beside it (no wrapping or clipping).
            b = QPushButton(text)
            b.setIcon(line_icon(icon))
            b.setIconSize(QSize(20, 20))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setCheckable(checkable)
            b.setObjectName("toolButton")
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.setMinimumHeight(40)
            if checkable:
                b.toggled.connect(slot)
            else:
                b.clicked.connect(slot)
            lay.addWidget(b)
            return b

        self.b_open = btn("Open PDF", "open", self.open_pdf)
        self.b_detect = btn("Detect PII", "detect", self.detect_pii)
        self.b_draw = btn("Draw Box", "draw", self.toggle_draw, checkable=True)
        self.b_term = btn("Add Term", "term", self.add_term)
        self.b_apply = btn("Apply Redaction", "apply", self.apply_redaction)
        self.b_verify = btn("Verify", "verify", self.run_verify)
        self.b_reply = btn("Draft Reply", "reply", self.draft_reply)
        self.b_folder = btn("Output Folder", "folder", self.open_output_folder)
        self.b_register = btn("Case Register", "register", self.open_register)
        lay.addStretch(1)
        self.b_settings = btn("Settings", "settings", self.open_settings)
        self.b_about = btn("About", "about", lambda: show_about(self, self.icon))
        return bar

    def _build_centre(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(5)

        self.banner = QFrame()
        self.banner.setObjectName("bannerPass")
        bl = QVBoxLayout(self.banner)
        bl.setContentsMargins(10, 3, 10, 4)
        bl.setSpacing(3)
        top = QHBoxLayout()
        self.banner_title = QLabel("")
        self.banner_title.setObjectName("bannerTitle")
        close = QPushButton("✕")
        close.setObjectName("bannerClose")
        close.setFixedSize(22, 22)
        close.clicked.connect(self.banner.hide)
        top.addWidget(self.banner_title, 1)
        top.addWidget(close)
        self.banner_details = QLabel("")
        self.banner_details.setObjectName("bannerDetails")
        self.banner_details.setWordWrap(True)
        self.banner_details.setTextFormat(Qt.TextFormat.RichText)
        self.banner_details.linkActivated.connect(self._banner_link)
        self.banner_chips = QHBoxLayout()
        self.banner_chips.setSpacing(6)
        bl.addLayout(top)
        bl.addLayout(self.banner_chips)
        bl.addWidget(self.banner_details)
        self.banner.hide()
        lay.addWidget(self.banner)

        nav = QHBoxLayout()
        self.b_prev = QPushButton("◀")
        self.b_next = QPushButton("▶")
        for b in (self.b_prev, self.b_next):
            b.setObjectName("navButton")
            b.setFixedWidth(40)
        self.page_combo = QComboBox()
        self.page_combo.setMinimumWidth(230)
        self.page_combo.currentIndexChanged.connect(self._on_page_combo)
        self.b_prev.clicked.connect(lambda: self.show_page(self.current - 1))
        self.b_next.clicked.connect(lambda: self.show_page(self.current + 1))
        self.review_badge = QLabel("Manual review required")
        self.review_badge.setObjectName("reviewBadge")
        self.review_badge.hide()
        self.kind_label = QLabel("")
        self.kind_label.setObjectName("kindBadge")
        self.chk_reviewed = QCheckBox("Reviewed – no PII")
        self.chk_reviewed.toggled.connect(self._on_reviewed)
        self.b_zoom_out = QPushButton("−")
        self.b_zoom_in = QPushButton("+")
        self.b_fit = QPushButton("Fit width")
        for b in (self.b_zoom_out, self.b_zoom_in):
            b.setObjectName("navButton")
            b.setFixedWidth(40)
        self.b_fit.setObjectName("navButton")
        self.b_compare = QPushButton("Side by side")
        self.b_compare.setObjectName("navButton")
        self.b_compare.setCheckable(True)
        self.b_compare.setToolTip("Show the original and the redacted copy next to each other")
        self.b_compare.toggled.connect(self._toggle_compare)
        nav.addWidget(self.b_prev)
        nav.addWidget(self.page_combo)
        nav.addWidget(self.b_next)
        nav.addSpacing(8)
        nav.addWidget(self.kind_label)
        nav.addWidget(self.review_badge)
        nav.addStretch(1)
        nav.addWidget(self.chk_reviewed)
        nav.addSpacing(8)
        nav.addWidget(self.b_compare)
        nav.addWidget(self.b_zoom_out)
        nav.addWidget(self.b_zoom_in)
        nav.addWidget(self.b_fit)
        lay.addLayout(nav)

        self.view = PageView()
        self.view.boxDrawn.connect(self._on_box_drawn)
        self.view.pageChanged.connect(self._on_page_scrolled)
        self.view_after = PageView()
        self.view_after.setToolTip("Redacted copy")
        self.view_after.hide()
        for v in (self.view, self.view_after):
            self.b_zoom_in.clicked.connect(v.zoom_in)
            self.b_zoom_out.clicked.connect(v.zoom_out)
        self.b_fit.clicked.connect(self.view.fit_width)
        # The redacted copy always uses the original's exact zoom, so both columns stay level.
        self.b_fit.clicked.connect(lambda: self.view_after.setTransform(self.view.transform()))
        # Keep both panes scrolled to the same place in side-by-side mode.
        for a, b in ((self.view, self.view_after), (self.view_after, self.view)):
            a.verticalScrollBar().valueChanged.connect(b.verticalScrollBar().setValue)
            a.horizontalScrollBar().valueChanged.connect(b.horizontalScrollBar().setValue)
        well = QFrame()
        well.setObjectName("paperWell")
        wl = QHBoxLayout(well)
        wl.setContentsMargins(4, 4, 4, 4)
        wl.addWidget(self.view)
        wl.addWidget(self.view_after)
        lay.addWidget(well, 1)
        return card

    def _build_draft_tab(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        title = QLabel("Draft reply with AI")
        title.setObjectName("cardTitle")
        lay.addWidget(title)
        self.draft_lock = QFrame()
        self.draft_lock.setObjectName("lockNote")
        ll = QHBoxLayout(self.draft_lock)
        ll.setContentsMargins(14, 12, 14, 12)
        lock_text = QLabel(
            "Draft Reply works only on a <b>verified</b> redacted PDF. Detect, redact and verify first; "
            "then only tokens such as [ASSESSEE] leave this computer."
        )
        lock_text.setWordWrap(True)
        ll.addWidget(lock_text)
        lay.addWidget(self.draft_lock)
        info = QLabel(
            "In the Draft Reply window you choose:<br>"
            "• <b>Model</b>: Claude (Opus, Sonnet, Haiku) or another provider set up in Settings > AI providers<br>"
            "• <b>What you want back</b>: Reply + Advisory, or Law research only<br>"
            "• <b>What to send</b>: redacted PDF + text, PDF only, or text only<br><br>"
            "You see exactly what will be sent before anything leaves this computer. "
            "Placeholders such as [[TO CONFIRM]] are filled locally before saving the Word files."
        )
        info.setWordWrap(True)
        info.setObjectName("muted")
        lay.addWidget(info)
        self.b_open_draft = QPushButton("Open Draft Reply")
        self.b_open_draft.setObjectName("tealButton")
        self.b_open_draft.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_open_draft.clicked.connect(self.draft_reply)
        lay.addWidget(self.b_open_draft)
        lay.addStretch(1)
        return card

    def _refresh_flow(self) -> None:
        """Move the stepper and the next-step button to match the current state."""
        if self.preview_doc is None:
            done, label, action = -1, "Open PDF", self.open_pdf
        elif not self.candidates and self.last_result is None:
            done, label, action = 0, "Detect PII", self.detect_pii
        elif self.last_result is None:
            done, label, action = 1, "Apply redaction", self.apply_redaction
        elif not self._verified:
            done, label, action = 2, "Verify", self.run_verify
        else:
            done, label, action = 3, "Draft reply", self.draft_reply
        self.stepbar.set_done(done)
        self.stepbar.primary.setText(label)
        self.stepbar.primary.setEnabled(not self._busy() and (self.preview_doc is not None or done == -1))
        self._primary_action = action
        self.draft_lock.setVisible(not self._verified)

    # ================================================================== state helpers
    def _load_lists(self, show: bool = True) -> None:
        try:
            self.allow = Allowlist.load(resolve_path(self.cfg, "allowlist"))
            self.master = detectors.load_client_master(resolve_path(self.cfg, "client_master"))
        except UserFacingError as exc:
            if show:
                show_error(self, "Settings", str(exc))
            else:
                log.warning("Allowlist or client master could not be loaded at start-up")

    def _busy(self) -> bool:
        return self._running

    def _update_enabled(self) -> None:
        busy = self._busy()
        has_doc = self.preview_doc is not None
        for b in (self.b_detect, self.b_draw, self.b_term, self.b_apply):
            b.setEnabled(has_doc and not busy)
        self.b_open.setEnabled(not busy)
        self.b_verify.setEnabled(not busy)
        self.b_reply.setEnabled(not busy)
        self.b_settings.setEnabled(not busy)
        self.b_folder.setEnabled(self.last_result is not None or self.last_output_pdf is not None)
        for b in (self.b_prev, self.b_next, self.b_zoom_in, self.b_zoom_out, self.b_fit, self.page_combo, self.chk_reviewed):
            b.setEnabled(has_doc)
        self.b_open_draft.setEnabled(not busy)
        self.b_compare.setEnabled(has_doc and self.last_output_pdf is not None and self.last_output_pdf.exists())
        self._refresh_flow()

    def _set_status(self, pct: int, msg: str) -> None:
        self.progress.setValue(pct)
        if msg:
            self.status_label.setText(msg)

    def _run(self, task_name: str, fn, on_ok) -> None:
        """Start ``fn`` in a worker thread; ``on_ok(result)`` runs after the thread has finished."""
        if self._busy():
            return
        outcome: dict[str, Any] = {}
        worker = TaskWorker(task_name, fn, self)
        worker.progress.connect(self._set_status)
        worker.succeeded.connect(lambda res: outcome.__setitem__("ok", res))
        worker.failed.connect(lambda msg: outcome.__setitem__("err", msg))

        def done() -> None:
            self._running = False
            self._update_enabled()
            if "err" in outcome:
                self._on_failed(outcome["err"])
            elif "ok" in outcome:
                on_ok(outcome["ok"])

        worker.finished.connect(done)
        self._worker = worker
        self._running = True
        self._set_status(0, f"{task_name[0].upper()}{task_name[1:]}...")
        worker.start()
        self._update_enabled()

    def _on_failed(self, message: str) -> None:
        self._set_status(0, "Stopped.")
        show_error(self, APP_NAME, message)

    # ================================================================== Open PDF
    def open_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open notice PDF", "", "PDF files (*.pdf)")
        if not path:
            return
        try:
            data = ingest.read_pdf_bytes(path)
            doc = ingest.open_pdf_bytes(data)
        except UserFacingError as exc:
            show_error(self, "Open PDF", str(exc))
            return
        self._reset_for(Path(path), doc, data)
        log.info("Opened a PDF with %d pages", doc.page_count)
        cfg = copy.deepcopy(self.cfg)

        def task(progress):
            d = ingest.open_pdf_bytes(data)
            try:
                return ingest.analyse(d, cfg, progress)
            finally:
                d.close()

        self._run("reading the PDF", task, self._on_ingested)

    def _reset_for(self, path: Path, doc: fitz.Document, data: bytes) -> None:
        """Make ``doc`` the open notice and clear everything from the previous one."""
        if self.preview_doc is not None:
            self.preview_doc.close()
        self.src_path = path
        self.preview_doc = doc
        self._src_sha = redact.sha256_bytes(data)
        self.pages = []
        self.candidates = []
        self.last_result = None
        self.last_output_pdf = None
        self._verified = False
        self.b_compare.setChecked(False)
        self.banner.hide()
        self.panel.set_candidates([])
        self.side_tabs.setCurrentIndex(0)
        self.b_draw.setChecked(False)
        self.view.clear_page()
        self.view_after.clear_page()
        self.header.set_file(path.name, doc.page_count)

    def _on_ingested(self, pages: list[PageInfo]) -> None:
        self.pages = pages
        first_pages_text = "\n".join(" ".join(w.text for w in p.words) for p in pages[:2])
        register.record_opened(self._src_sha, self.src_path.name, first_pages_text)
        self.current = 0
        self._rebuild_page_combo()
        self.view.set_document(_page_sizes(self.preview_doc), _page_loader(self.preview_doc))
        self.view.fit_width()
        self._update_nav(0)
        self._refresh_overlays()
        flagged = sum(p.needs_review for p in pages)
        msg = f"Loaded {len(pages)} page(s)."
        if flagged:
            msg += f" {flagged} page(s) need manual review (low OCR confidence)."
        self._set_status(100, msg + " Click Detect PII next.")

    def _rebuild_page_combo(self) -> None:
        self.page_combo.blockSignals(True)
        self.page_combo.clear()
        for p in self.pages:
            label = f"Page {p.index + 1}  ({p.kind.lower()})"
            if p.needs_review and not p.reviewed_no_pii:
                label += "  ⚠ Manual review required"
            elif p.reviewed_no_pii:
                label += "  ✔ reviewed"
            self.page_combo.addItem(label)
            if p.needs_review and not p.reviewed_no_pii:
                self.page_combo.setItemData(p.index, QColor("#C62828"), Qt.ItemDataRole.ForegroundRole)
        self.page_combo.setCurrentIndex(self.current if self.current < len(self.pages) else 0)
        self.page_combo.blockSignals(False)

    # ================================================================== preview
    def show_page(self, index: int) -> None:
        """Jump to a page (all pages are in one scroll)."""
        if self.preview_doc is None or not self.pages:
            return
        index = max(0, min(index, len(self.pages) - 1))
        self.current = index
        self._update_nav(index)
        self.view.scroll_to_page(index)

    def _on_page_scrolled(self, index: int) -> None:
        if self.pages and index < len(self.pages):
            self.current = index
            self._update_nav(index)

    def _update_nav(self, index: int) -> None:
        """Page box, type badge and review tick follow the page being read."""
        info = self.pages[index]
        self.page_combo.blockSignals(True)
        self.page_combo.setCurrentIndex(index)
        self.page_combo.blockSignals(False)
        self.kind_label.setText("Scanned page (OCR)" if info.kind == "IMAGE" else "Text page")
        self.review_badge.setVisible(info.needs_review and not info.reviewed_no_pii)
        self.chk_reviewed.blockSignals(True)
        self.chk_reviewed.setChecked(info.reviewed_no_pii)
        self.chk_reviewed.blockSignals(False)

    def _toggle_compare(self, on: bool) -> None:
        if on and (self.last_output_pdf is None or not self.last_output_pdf.exists()):
            self.b_compare.setChecked(False)
            return
        self.view_after.setVisible(on)
        if not on:
            return
        if self._after_path != self.last_output_pdf:
            if self.after_doc is not None:
                self.after_doc.close()
            try:
                self.after_doc = ingest.load_document(self.last_output_pdf)
                self._after_path = self.last_output_pdf
            except UserFacingError as exc:
                show_error(self, "Side by side", str(exc))
                self.b_compare.setChecked(False)
                return
        self.view_after.set_document(_page_sizes(self.after_doc), _page_loader(self.after_doc))
        self.view.fit_width()
        self.view_after.setTransform(self.view.transform())
        self.view.scroll_to_page(self.current)
        self.view_after.verticalScrollBar().setValue(self.view.verticalScrollBar().value())

    def _pdf_to_scene(self, index: int, rect) -> QRectF:
        """A PDF rectangle on page ``index`` in the stacked view's coordinates."""
        page = self.preview_doc[index]
        r = fitz.Rect(rect) * page.rotation_matrix
        r.normalize()
        s = PREVIEW_SCALE
        top_left = self.view.page_rect(index).topLeft()
        return QRectF(top_left.x() + r.x0 * s, top_left.y() + r.y0 * s, r.width * s, r.height * s)

    def _scene_to_pdf(self, page: fitz.Page, rect: QRectF):
        s = PREVIEW_SCALE
        r = fitz.Rect(rect.left() / s, rect.top() / s, rect.right() / s, rect.bottom() / s) * page.derotation_matrix
        r.normalize()
        return (r.x0, r.y0, r.x1, r.y1)

    def _refresh_overlays(self) -> None:
        if self.preview_doc is None or not self.pages:
            return
        boxes = []
        for c in self.candidates:
            if not (0 <= c.page < len(self.pages)):
                continue
            tip = f"{c.pii_type}: {mask_value(c.text, c.pii_type)}  ({c.confidence:.0%})"
            for b in c.bboxes:
                boxes.append((self._pdf_to_scene(c.page, b), colour_for(c.pii_type), c.accepted, c.cid == self.selected_cid, tip))
        self.view.set_overlays(boxes)

    def _on_page_combo(self, idx: int) -> None:
        if idx >= 0:
            self.show_page(idx)

    def _on_reviewed(self, on: bool) -> None:
        if not self.pages:
            return
        self.pages[self.current].reviewed_no_pii = on
        self.review_badge.setVisible(self.pages[self.current].needs_review and not on)
        self._rebuild_page_combo()

    def _jump_to_candidate(self, cid: str) -> None:
        self.selected_cid = cid
        c = next((c for c in self.candidates if c.cid == cid), None)
        if c is None:
            return
        self.current = c.page
        self._update_nav(c.page)
        self._refresh_overlays()
        self.view.centerOn(self._pdf_to_scene(c.page, c.bboxes[0]).center())

    # ================================================================== Detect PII
    def detect_pii(self) -> None:
        if not self.pages or self.src_path is None:
            return
        self._load_lists(show=True)
        data = ingest.read_pdf_bytes(self.src_path)
        pages = copy.deepcopy(self.pages)
        cfg, allow, master = copy.deepcopy(self.cfg), self.allow, self.master

        def task(progress):
            d = ingest.open_pdf_bytes(data)
            try:
                return detectors.detect_all(d, pages, cfg, allow, master, progress)
            finally:
                d.close()

        self._run("detecting PII", task, self._on_detected)

    def _on_detected(self, result: detectors.DetectionResult) -> None:
        manual = [c for c in self.candidates if c.source == "manual"]
        self.candidates = result.candidates + manual
        self.panel.set_candidates(self.candidates)
        self._refresh_overlays()
        self.side_tabs.setCurrentIndex(0)
        self._update_enabled()
        acc = sum(c.accepted for c in self.candidates)
        self._set_status(100, f"Found {len(result.candidates)} item(s); {acc} pre-ticked. Review the list, then Apply redaction.")
        if result.warnings:
            show_info(self, "Detect PII", "\n".join(result.warnings))

    # ================================================================== manual
    def toggle_draw(self, on: bool) -> None:
        self.view.set_draw_mode(on)
        self._set_status(self.progress.value(), "Draw Box: drag a rectangle on the page to redact it." if on else "Draw Box off.")

    def _on_box_drawn(self, index: int, rect: QRectF) -> None:
        if self.preview_doc is None:
            return
        pdf_rect = self._scene_to_pdf(self.preview_doc[index], rect)
        text = redact.text_under_rect(self.preview_doc, self.pages[index], pdf_rect)
        c = Candidate(index, [pdf_rect], text, "MANUAL", 1.0, "MANUAL_BOX", source="manual")
        self.candidates.append(c)
        self.panel.set_candidates(self.candidates)
        self._refresh_overlays()
        self._set_status(self.progress.value(), "Box added.")

    def add_term(self) -> None:
        if self.preview_doc is None:
            return
        term, ok = QInputDialog.getText(self, "Add Term", "Word or phrase to redact everywhere in this notice:")
        if not ok or not term.strip():
            return
        found = redact.find_term_occurrences(self.preview_doc, self.pages, term)
        if not found:
            show_info(self, "Add Term", "That term was not found in this notice.")
            return
        self.candidates.extend(found)
        self.panel.set_candidates(self.candidates)
        self._refresh_overlays()
        self._set_status(self.progress.value(), f"Added {len(found)} occurrence(s) of the term.")

    # ================================================================== Apply / Verify
    def apply_redaction(self) -> None:
        if self.src_path is None or not self.pages:
            return
        accepted = sum(c.accepted for c in self.candidates)
        pending = [p.index + 1 for p in self.pages if p.needs_review and not p.reviewed_no_pii]
        msg = f"Redact {accepted} ticked item(s) and create a new redacted PDF?\n\nThe original notice will not be changed."
        if pending:
            msg += f"\n\nPages flagged for manual review and not yet marked reviewed: {', '.join(map(str, pending))}."
        folder, out_pdf, _, _ = redact.output_paths(self.src_path, self.cfg)
        if out_pdf.exists():
            msg += "\n\nAn earlier redacted copy in the output folder will be replaced."
        if QMessageBox.question(self, "Apply Redaction", msg) != QMessageBox.StandardButton.Yes:
            return
        src, pages, cands, cfg = self.src_path, copy.deepcopy(self.pages), copy.deepcopy(self.candidates), copy.deepcopy(self.cfg)
        self.banner.hide()
        self._run("applying redactions", lambda progress: redact.apply_redactions(src, pages, cands, cfg, progress), self._on_redacted)

    def _on_redacted(self, result: redact.RedactionResult) -> None:
        self.last_result = result
        self.last_output_pdf = result.pdf_path
        self._verified = False
        self._after_path = None
        client = next((c.text for c in self.candidates if c.accepted and c.role == "assessee"), None) or next(
            (c.text for c in self.candidates if c.accepted and c.pii_type in ("ORG", "NAME")), None)
        register.advance(self._src_sha, "Redacted", client=client, folder=result.folder)
        self._set_status(100, "Redacted PDF saved. Verifying...")
        self._update_enabled()
        self._start_verify(result.pdf_path)

    def run_verify(self) -> None:
        target = self.last_output_pdf
        if target is None or not target.exists():
            path, _ = QFileDialog.getOpenFileName(self, "Choose a redacted PDF to verify", "", "Redacted PDF (*_REDACTED.pdf);;PDF files (*.pdf)")
            if not path:
                return
            target = Path(path)
        self._start_verify(target)

    def _start_verify(self, pdf: Path) -> None:
        self._load_lists(show=True)
        cfg, allow, master = copy.deepcopy(self.cfg), self.allow, self.master
        self.last_output_pdf = pdf
        self._run("verifying the redacted PDF", lambda progress: verify.verify(pdf, cfg, allow, master, progress), self._on_verified)

    def _on_verified(self, report: verify.VerifyReport) -> None:
        self._verified = report.verified
        self._update_enabled()
        while self.banner_chips.count():
            w = self.banner_chips.takeAt(0).widget()
            if w:
                w.deleteLater()
        if report.verified:
            self.banner.setObjectName("bannerPass")
            self.banner_title.setText("✔  VERIFIED — SAFE TO SHARE")
            short = ["Text layer", "OCR re-read", "Variants & tails", "Detectors re-run", "Metadata", "Page coverage"]
            for name, c in zip(short, report.checks):
                chip = QLabel(f"{c.status} · {name}")
                chip.setObjectName("checkChip")
                chip.setProperty("state", c.status)
                self.banner_chips.addWidget(chip)
            self.banner_chips.addStretch(1)
            warns = [d for c in report.checks if c.status == verify.WARN for d in c.details]
            details = f"Report saved as verify_report.txt and .json  ·  SHA-256 {report.redacted_sha256[:4]}…{report.redacted_sha256[-4:]}"
            if warns:
                details += "<br><b>Notes:</b> " + "<br>".join(warns[:6])
            self.banner_details.setText(details)
        else:
            self.banner.setObjectName("bannerFail")
            self.banner_title.setText("✖  VERIFICATION FAILED - DO NOT SHARE")
            items = []
            for c in report.checks:
                if c.status != verify.FAIL:
                    continue
                for lk in c.leaks:
                    items.append(f"<a href='page:{lk['page']}'>Page {lk['page']}</a> – {lk['type']} ({lk['source']})")
                items += c.details
            self.banner_details.setText("<br>".join(items[:25]) + ("<br>..." if len(items) > 25 else ""))
        _repolish(self.banner)
        for child in self.banner.findChildren(QLabel):
            _repolish(child)
        self.banner.show()
        self._set_status(100, f"Verification {'passed' if report.verified else 'FAILED'}. Reports saved in the output folder.")
        if report.verified and self.last_result is not None and self._src_sha:
            register.advance(self._src_sha, "Verified")
        if self.b_compare.isChecked():
            self._toggle_compare(True)

    def _banner_link(self, link: str) -> None:
        if link.startswith("page:") and self.preview_doc is not None:
            try:
                self.show_page(int(link.split(":", 1)[1]) - 1)
            except ValueError:
                pass
        elif link.startswith("page:"):
            show_info(self, "Verify", "Open the original notice to view its pages.")

    # ================================================================== Draft Reply
    def draft_reply(self) -> None:
        target = self.last_output_pdf
        if target is None or not target.exists():
            path, _ = QFileDialog.getOpenFileName(
                self, "Choose a verified redacted PDF", "", "Redacted PDF (*_REDACTED.pdf);;PDF files (*.pdf)"
            )
            if not path:
                return
            target = Path(path)
        try:
            job = drafting.prepare(target)
        except UserFacingError as exc:
            show_error(self, "Draft Reply", str(exc))
            return
        self._load_lists(show=True)
        ReplyDialog(job, copy.deepcopy(self.cfg), self.allow, self.master, self).exec()

    # ================================================================== register
    def open_register(self) -> None:
        RegisterDialog(self).exec()

    def check_due(self) -> None:
        """Start-up reminder: Windows notification and status line for replies due within 7 days."""
        if not self.cfg.get("notifications", {}).get("due_reminders", True):
            return
        self._tray = QSystemTrayIcon(self.icon, self)
        self._tray.setToolTip(FULL_TITLE)
        self._tray.messageClicked.connect(self.open_register)
        n = notify_due(self._tray)
        if n:
            self._set_status(0, f"{n} reply/replies due within 7 days or overdue. See Case Register.")

    # ================================================================== misc
    def open_output_folder(self) -> None:
        folder = None
        if self.last_result is not None:
            folder = self.last_result.folder
        elif self.last_output_pdf is not None:
            folder = self.last_output_pdf.parent
        if folder and folder.exists():
            os.startfile(str(folder))  # noqa: S606 - opens Explorer locally

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec():
            self.cfg = dlg.cfg
            self._load_lists(show=True)
            self._set_status(self.progress.value(), "Settings saved. Run Detect PII again to apply them.")

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._busy():
            if QMessageBox.question(self, APP_NAME, "Work is still running. Quit anyway?") != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._worker.terminate()
            self._worker.wait(2000)
        if self.preview_doc is not None:
            self.preview_doc.close()
        event.accept()
