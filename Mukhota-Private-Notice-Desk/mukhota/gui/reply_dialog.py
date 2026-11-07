"""Draft Reply dialog: choose what to send and what to get back, preview, send, save as Word."""
from __future__ import annotations

import copy
import os
import re
from typing import Any

from PyQt6.QtCore import QElapsedTimer, Qt, QTimer
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import ai, ai_client, client_facts, drafting, law_library, register, usage
from ..core.allowlist import Allowlist
from ..core.detectors import MasterEntry
from ..core.models import UserFacingError
from .dialogs import show_error, show_info
from .workers import TaskWorker


def _radios(options: dict[str, str], default: str) -> tuple[QWidget, QButtonGroup, dict[int, str]]:
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    group = QButtonGroup(box)
    ids: dict[int, str] = {}
    for i, (key, label) in enumerate(options.items()):
        rb = QRadioButton(label)
        rb.setChecked(key == default)
        group.addButton(rb, i)
        ids[i] = key
        lay.addWidget(rb)
    lay.addStretch(1)
    return box, group, ids


class FactsDialog(QDialog):
    """Edit one client's facts sheet (kept encrypted on this computer, never sent to any AI provider)."""

    def __init__(self, name: str, data: dict[str, Any], ay: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mukhota - Client facts")
        self.resize(620, 560)
        self.data = copy.deepcopy(data)
        self.ay = ay
        form = QFormLayout()
        self.txt_ay = QLineEdit(ay)
        self.txt_ay.setPlaceholderText("e.g. 2024-25")
        self.txt_ay.editingFinished.connect(self._reload_year)
        form.addRow(QLabel(f"<b>{name}</b>"))
        form.addRow("Assessment year (for year-wise facts)", self.txt_ay)
        self.edits: dict[str, QLineEdit] = {}
        for key, label, per_year, _ in client_facts.FIELDS:
            e = QLineEdit(client_facts.get(self.data, key, ay))
            self.edits[key] = e
            form.addRow(label + ("  (this AY)" if per_year else ""), e)
        note = QLabel("Used only to fill [[TO CONFIRM]] placeholders on this computer. Never sent to any AI provider.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(note)
        lay.addWidget(buttons)

    def _store(self) -> None:
        for key, e in self.edits.items():
            client_facts.put(self.data, key, self.ay, e.text().strip())

    def _reload_year(self) -> None:
        new_ay = self.txt_ay.text().strip()
        if new_ay == self.ay:
            return
        self._store()
        self.ay = new_ay
        for key in client_facts.YEAR_FIELDS:
            self.edits[key].setText(client_facts.get(self.data, key, self.ay))

    def _accept(self) -> None:
        self._reload_year()
        self._store()
        self.accept()


class ReplyDialog(QDialog):
    """Sends only tokenised content of a verified PDF; restores tokens locally."""

    def __init__(self, job: drafting.DraftJob, cfg: dict[str, Any], allow: Allowlist,
                 master: list[MasterEntry], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mukhota - Draft Reply")
        self.resize(1000, 760)
        self.job, self.cfg, self.allow, self.master = job, cfg, allow, master
        self._notice_text: str | None = None
        self._safe_facts = ""
        self._previewed_key: tuple | None = None
        self._output: drafting.DraftOutput | None = None
        self._output_mode = "reply"
        self._running = False
        self._worker: TaskWorker | None = None
        self._views: dict[str, QPlainTextEdit] = {}
        self._facts_key = ""
        self._facts: dict[str, Any] = {"name": "", "common": {}, "years": {}}
        self._client_name = ""
        self._ay = ""
        try:
            self._ay = drafting.detect_ay(job)
            self._facts_key, self._client_name = client_facts.client_key(job.registry)
            self._facts = client_facts.load(self._facts_key)
        except UserFacingError:
            self._facts_key = ""

        form = QFormLayout()
        self.cmb_model = QComboBox()
        self._choices = {c["id"]: c for c in ai.choices(cfg)}
        for c in self._choices.values():
            self.cmb_model.addItem(c["label"] + ("" if c["ready"] else "  (no key saved)"), c["id"])
        idx = self.cmb_model.findData(ai.current(cfg))
        self.cmb_model.setCurrentIndex(max(idx, 0))
        self.cmb_type = QComboBox()
        self.cmb_type.addItems(drafting.NOTICE_TYPES)
        out_box = QWidget()
        out_lay = QHBoxLayout(out_box)
        out_lay.setContentsMargins(0, 0, 0, 0)
        self.chk_out: dict[str, QCheckBox] = {}
        for key, label in drafting.OUTPUTS.items():
            chk = QCheckBox(label)
            chk.setChecked(key in ("reply", "advisory"))
            chk.toggled.connect(lambda on, c=chk: (not on and not any(x.isChecked() for x in self.chk_out.values()))
                                and c.setChecked(True))  # at least one stays ticked
            self.chk_out[key] = chk
            out_lay.addWidget(chk)
        out_lay.addStretch(1)
        how_box, self.grp_how, self.how_ids = _radios(drafting.HOW_MODES, "send")
        in_box, self.grp_in, self.in_ids = _radios(drafting.INPUT_MODES, "both")
        self.lbl_prompt = QLabel(
            "No API, no key, no cost. Mukhota makes a prompt with tokens only (no real names) to paste into ChatGPT, "
            "Claude.ai, Gemini, DeepSeek or any AI chat. Then paste the AI's answer in the 'Paste AI answer' tab to "
            "restore real values and save the Word files.")
        self.lbl_prompt.setWordWrap(True)
        self.lbl_prompt.setObjectName("muted")
        self.chk_web = QCheckBox("Let the model search the web to confirm law and case citations (small extra cost)")
        self.chk_web.setChecked(True)
        self._web_wanted = True
        self.chk_web.toggled.connect(lambda on: self.chk_web.isEnabled() and setattr(self, "_web_wanted", on))
        self.lbl_caps = QLabel(ai.NO_PDF_WEB)
        self.lbl_caps.setObjectName("muted")
        self.lbl_caps.setWordWrap(True)
        n_lib = law_library.file_count()
        self.chk_lib = QCheckBox(f"Use my law library ({n_lib} file{'s' if n_lib != 1 else ''} in law_library\\)")
        self.chk_lib.setChecked(n_lib > 0 and bool(cfg.get("law_library", {}).get("enabled", True)))
        self.chk_lib.setEnabled(n_lib > 0)
        self._lib_block = ""
        form.addRow("What do you want back", out_box)
        form.addRow("How to get it", how_box)
        form.addRow("Model", self.cmb_model)
        form.addRow("What to send", in_box)
        form.addRow("", self.lbl_caps)
        form.addRow("", self.chk_web)
        form.addRow("", self.lbl_prompt)
        form.addRow("Notice type", self.cmb_type)
        form.addRow("", self.chk_lib)
        self._form = form
        self._send_rows = [self.cmb_model, in_box, self.lbl_caps, self.chk_web]

        self.txt_facts = QPlainTextEdit()
        self.txt_facts.setPlaceholderText(
            "Facts, explanations and instructions for the reply (optional). Names, PANs, account numbers etc. "
            "typed here are replaced with tokens before anything is sent."
        )
        self.txt_facts.setMaximumHeight(140)

        # Optional add-on: six-box issue framing (off unless ticked).
        self.chk_frame = QCheckBox("Frame the issues first (six-box method, optional add-on) - fill any box you know, "
                                   "leave the rest blank for the AI; adds an 'Issue framing' tab")
        self.six_box = QWidget()
        grid = QGridLayout(self.six_box)
        grid.setContentsMargins(0, 0, 0, 0)
        self.box_edits: dict[str, QLineEdit] = {}
        for i, (key, (label, hint)) in enumerate(drafting.SIX_BOXES.items()):
            edit = QLineEdit()
            edit.setPlaceholderText(hint)
            self.box_edits[key] = edit
            grid.addWidget(QLabel(label), i // 2, (i % 2) * 2)
            grid.addWidget(edit, i // 2, (i % 2) * 2 + 1)
        self.six_box.setVisible(False)
        self.chk_frame.toggled.connect(self.six_box.setVisible)

        self.tabs = QTabWidget()
        self.txt_sent = QPlainTextEdit()
        self.txt_sent.setReadOnly(True)
        self.tabs.addTab(self.txt_sent, "What will be sent")

        self.paste_box = QWidget()
        pl = QVBoxLayout(self.paste_box)
        hint = QLabel("Paste the AI chat's whole answer here. Mukhota puts the real names back on this computer; "
                      "nothing is sent anywhere.")
        hint.setWordWrap(True)
        self.txt_paste = QPlainTextEdit()
        self.txt_paste.setPlaceholderText("<<<REPLY>>> ...")
        self.b_use_paste = QPushButton("Use this answer")
        self.b_use_paste.clicked.connect(self.use_paste)
        pl.addWidget(hint)
        pl.addWidget(self.txt_paste, 1)
        pl.addWidget(self.b_use_paste)
        self._prompt_text = ""
        self._prompt_mode = ""

        # Status bar: what is happening now, always in view at the top.
        self.status_bar = QFrame()
        self.status_bar.setObjectName("draftStatus")
        self.lbl_state = QLabel()
        self.lbl_state.setObjectName("statusChip")
        self.lbl_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_info = QLabel(f"Verified file: {job.pdf_path.name}")
        self.lbl_info.setObjectName("statusText")
        self.lbl_info.setWordWrap(True)
        self.lbl_time = QLabel()
        self.lbl_time.setObjectName("statusTime")
        self.progress = QProgressBar()
        self.progress.setObjectName("statusProgress")
        self.progress.setRange(0, 100)
        self.progress.setFixedWidth(260)
        sbl = QHBoxLayout(self.status_bar)
        sbl.setContentsMargins(12, 8, 12, 8)
        sbl.setSpacing(12)
        sbl.addWidget(self.lbl_state)
        sbl.addWidget(self.lbl_info, 1)
        sbl.addWidget(self.lbl_time)
        sbl.addWidget(self.progress)
        self._clock = QElapsedTimer()
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._show_elapsed)
        self._status("idle")

        self.b_preview = QPushButton("Preview what will be sent")
        self.b_send = QPushButton("Send")
        self.b_save = QPushButton("Save as Word")
        self.b_facts = QPushButton("Client facts...")
        self.b_folder = QPushButton("Open folder")
        self.b_close = QPushButton("Close")
        self.b_make = QPushButton("Make prompt")
        self.b_copy = QPushButton("Copy prompt")
        self.b_save_prompt = QPushButton("Save prompt as .txt")
        self.b_make.clicked.connect(lambda: self.preview(make_prompt=True))
        self.b_copy.clicked.connect(self.copy_prompt)
        self.b_save_prompt.clicked.connect(self.save_prompt)
        self.b_copy.setEnabled(False)
        self.b_save_prompt.setEnabled(False)
        for b in (self.b_preview, self.b_facts, self.b_folder, self.b_close, self.b_copy, self.b_save_prompt):
            b.setObjectName("smallButton")
        self.b_save.setEnabled(False)
        self.b_facts.setEnabled(bool(self._facts_key))
        self.b_facts.setToolTip("Status, auditor, turnover, filing dates... for this client, used to fill placeholders locally")
        self.b_facts.clicked.connect(self.edit_facts)
        self.b_preview.clicked.connect(lambda: self.preview())
        self.b_send.clicked.connect(self.send)
        self.b_save.clicked.connect(self.save)
        self.b_folder.clicked.connect(lambda: os.startfile(str(self.job.folder)))  # noqa: S606
        self.b_close.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addWidget(self.b_preview)
        buttons.addWidget(self.b_send)
        buttons.addWidget(self.b_make)
        buttons.addWidget(self.b_copy)
        buttons.addWidget(self.b_save_prompt)
        buttons.addStretch(1)
        buttons.addWidget(self.b_facts)
        buttons.addWidget(self.b_save)
        buttons.addWidget(self.b_folder)
        buttons.addWidget(self.b_close)

        lay = QVBoxLayout(self)
        lay.addWidget(self.status_bar)
        lay.addLayout(form)
        lay.addWidget(QLabel("Facts and instructions"))
        lay.addWidget(self.txt_facts)
        lay.addWidget(self.chk_frame)
        lay.addWidget(self.six_box)
        lay.addWidget(self.tabs, 1)
        lay.addLayout(buttons)
        self.cmb_model.currentIndexChanged.connect(self._apply_caps)
        self._apply_caps()
        self.grp_how.idToggled.connect(lambda _i, on: on and self._apply_how())
        self._apply_how()

    def _prompt_mode_on(self) -> bool:
        return self.how_ids[self.grp_how.checkedId()] == "prompt"

    def _apply_how(self) -> None:
        """Send to AI, or make a prompt for any AI chat (no API)."""
        prompt = self._prompt_mode_on()
        for w in self._send_rows:
            self._form.setRowVisible(w, not prompt)
        if not prompt:
            self._apply_caps()
        self._form.setRowVisible(self.lbl_prompt, prompt)
        for b in (self.b_preview, self.b_send):
            b.setVisible(not prompt)
        for b in (self.b_make, self.b_copy, self.b_save_prompt):
            b.setVisible(prompt)
        idx = self.tabs.indexOf(self.paste_box)
        if prompt and idx < 0:
            self.tabs.insertTab(1, self.paste_box, "Paste AI answer")
        elif not prompt and idx >= 0:
            self.tabs.removeTab(idx)
        self.tabs.setTabText(0, "Prompt to copy" if prompt else "What will be sent")

    # ------------------------------------------------------------------ helpers
    def _choice(self) -> str:
        return self.cmb_model.currentData()

    def _apply_caps(self) -> None:
        """PDF and web search only where the chosen model's provider can take them."""
        c = self._choices.get(self._choice(), {"pdf": True, "web": True})
        for i, key in self.in_ids.items():
            self.grp_in.button(i).setEnabled(c["pdf"] or key == "text")
        if not c["pdf"] and self.in_ids[self.grp_in.checkedId()] != "text":
            self.grp_in.button(next(i for i, k in self.in_ids.items() if k == "text")).setChecked(True)
        self.chk_web.setEnabled(c["web"])
        self.chk_web.blockSignals(True)
        self.chk_web.setChecked(c["web"] and self._web_wanted)
        self.chk_web.blockSignals(False)
        self.lbl_caps.setVisible(not (c["pdf"] and c["web"]))

    def _send_cfg(self) -> dict[str, Any]:
        cfg = copy.deepcopy(self.cfg)
        cfg["ai"]["model"] = self._choice()
        return cfg
    def _modes(self) -> tuple[str, str]:
        out = "+".join(k for k, c in self.chk_out.items() if c.isChecked())
        if self.chk_frame.isChecked():
            out = f"{drafting.FRAMING}+{out}"
        in_mode = "text" if self._prompt_mode_on() else self.in_ids[self.grp_in.checkedId()]
        return out, in_mode

    def _facts_text(self) -> str:
        """Typed facts, plus the six-box inputs when the add-on is ticked."""
        facts = self.txt_facts.toPlainText()
        if self.chk_frame.isChecked():
            return drafting.with_six_box(facts, {k: e.text() for k, e in self.box_edits.items()})
        return facts

    def _key(self) -> tuple:
        out_mode, in_mode = self._modes()
        return (self._facts_text(), out_mode, in_mode, self.cmb_type.currentText(), self.chk_web.isChecked(),
                self.chk_lib.isChecked(), self._choice(), self._prompt_mode_on())

    def _user_text(self, out_mode: str, in_mode: str) -> str:
        instructions = drafting.user_instructions(self.cmb_type.currentText(), out_mode, in_mode, self._safe_facts)
        if self.chk_lib.isChecked() and self._lib_block:
            return self._lib_block + "\n\n" + instructions
        return instructions

    def _status(self, state: str) -> None:
        """Colour the status bar for idle, busy, done or error."""
        self.lbl_state.setText({"idle": "READY", "busy": "WORKING…", "done": "DONE", "error": "FAILED"}[state])
        for w in (self.status_bar, self.lbl_state):
            w.setProperty("state", state)
            w.style().unpolish(w)
            w.style().polish(w)
        if state == "busy":
            self._clock.start()
            self._show_elapsed()
            self._tick.start()
        else:
            self._tick.stop()

    def _show_elapsed(self) -> None:
        s = self._clock.elapsed() // 1000
        self.lbl_time.setText(f"{s // 60}:{s % 60:02d}")

    def _set_busy(self, busy: bool) -> None:
        self._running = busy
        for b in (self.b_preview, self.b_send, self.b_close, self.b_make, self.b_use_paste):
            b.setEnabled(not busy)
        self.b_save.setEnabled(not busy and self._output is not None)
        for b in (self.b_copy, self.b_save_prompt):
            b.setEnabled(not busy and bool(self._prompt_text))

    def _run(self, name: str, fn, on_ok) -> None:
        if self._running:
            return
        outcome: dict[str, Any] = {}
        w = TaskWorker(name, fn, self)
        w.progress.connect(lambda p, m: (self.progress.setValue(p), self.lbl_info.setText(m) if m else None))
        w.succeeded.connect(lambda r: outcome.__setitem__("ok", r))
        w.failed.connect(lambda m: outcome.__setitem__("err", m))

        def done() -> None:
            self._set_busy(False)
            if "err" in outcome:
                self.progress.setValue(0)
                self.lbl_info.setText("Stopped: " + outcome["err"].splitlines()[0])
                self._status("error")
                show_error(self, "Draft Reply", outcome["err"])
            elif "ok" in outcome:
                self.progress.setValue(100)
                self._status("done")
                on_ok(outcome["ok"])

        w.finished.connect(done)
        self._worker = w
        self._set_busy(True)
        self.progress.setValue(0)
        self._status("busy")
        w.start()

    # ------------------------------------------------------------------ preview
    def preview(self, then_send: bool = False, make_prompt: bool = False) -> None:
        try:
            self._safe_facts, notes = drafting.tokenise_facts(
                self._facts_text(), self.job, self.cfg, self.allow, self.master
            )
        except UserFacingError as exc:
            show_error(self, "Draft Reply", str(exc))
            return
        _, in_mode = self._modes()
        use_lib = self.chk_lib.isChecked()
        need_text = (in_mode in ("both", "text") or use_lib) and self._notice_text is None
        cfg = copy.deepcopy(self.cfg)
        lib_cfg = cfg.get("law_library", {})

        def task(progress):
            text = drafting.extract_text(self.job, cfg, progress) if need_text else self._notice_text
            excerpts = []
            if use_lib and text:
                progress(90, "Searching your law library")
                excerpts = law_library.search(law_library.query_terms(text), int(lib_cfg.get("max_excerpts", 8)),
                                              int(lib_cfg.get("max_chars", 14000)))
            return text, excerpts

        def shown(result) -> None:
            self._notice_text, excerpts = result
            self._lib_block = ""
            if excerpts:
                # Library files are the user's own, but tokenise them too in case old replies were saved there.
                self._lib_block, lib_notes = drafting.tokenise_facts(
                    law_library.as_block(excerpts), self.job, self.cfg, self.allow, self.master)
                notes.extend(f"library: {n}" for n in lib_notes)
                notes.append(f"{len(excerpts)} law library excerpt(s) included")
            elif use_lib:
                notes.append("no matching law library excerpts")
            self._show_preview(notes)
            if make_prompt:
                self._show_prompt(notes)
            if then_send:
                self._confirm_and_send()

        self._run("reading the redacted notice", task, shown)

    def _show_preview(self, notes: list[str]) -> None:
        out_mode, in_mode = self._modes()
        parts = []
        if in_mode in ("both", "pdf"):
            parts.append(f"[Attached PDF: {self.job.pdf_path.name} - the verified redacted file]")
        if in_mode in ("both", "text"):
            parts.append("=== Notice text ===\n" + (self._notice_text or ""))
        parts.append("=== Instructions, law library excerpts and your facts (tokenised) ===\n"
                     + self._user_text(out_mode, in_mode))
        self.txt_sent.setPlainText("\n\n".join(parts))
        self.tabs.setCurrentIndex(0)
        self._previewed_key = self._key()
        msg = "Preview ready. Check that nothing personal is visible, then click Send."
        if notes:
            msg += "  Facts: " + "; ".join(notes) + "."
        self.lbl_info.setText(msg)

    # ------------------------------------------------------------------ prompt for any AI chat
    def _show_prompt(self, notes: list[str]) -> None:
        out_mode, in_mode = self._modes()
        self._prompt_text = drafting.chat_prompt(drafting.system_prompt(), self._notice_text,
                                                 self._user_text(out_mode, in_mode))
        self._prompt_mode = out_mode
        self.txt_sent.setPlainText(self._prompt_text)
        self.tabs.setCurrentIndex(0)
        msg = ("Prompt ready. Copy it into any AI chat (it holds tokens only, no real names). Then paste the AI's "
               "answer in the 'Paste AI answer' tab to restore real values.")
        if notes:
            msg += "  Facts: " + "; ".join(notes) + "."
        self.lbl_info.setText(msg)
        for b in (self.b_copy, self.b_save_prompt):
            b.setEnabled(True)

    def copy_prompt(self) -> None:
        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._prompt_text)
        self.lbl_info.setText("Prompt copied. Paste it into your AI chat, then paste its answer in the "
                              "'Paste AI answer' tab.")

    def save_prompt(self) -> None:
        try:
            path = drafting.save_prompt(self.job, self._prompt_text)
        except UserFacingError as exc:
            show_error(self, "Save prompt", str(exc))
            return
        show_info(self, "Prompt saved", f"Saved in the output folder as {path.name}.")

    def use_paste(self) -> None:
        text = self.txt_paste.toPlainText()
        if not text.strip():
            show_error(self, "Paste AI answer", "Paste the AI's answer first.")
            return
        out_mode = self._prompt_mode or self._modes()[0]
        info = "Answer pasted and real values restored on this computer. You can edit the text before saving."
        if not any(m in text for m in drafting.MARKERS.values()):
            info += (" The answer has no section markers, so all of it is in the first tab; move any advisory "
                     "part out by hand before saving.")
        self._show_answer(text, out_mode, info)

    # ------------------------------------------------------------------ send
    def send(self) -> None:
        try:
            ai.ensure_ready(self._send_cfg(), self._choice())
        except UserFacingError as exc:
            show_error(self, "Draft Reply", str(exc))
            return
        if self._previewed_key != self._key():
            self.preview(then_send=True)
            return
        self._confirm_and_send()

    def _confirm_and_send(self) -> None:
        out_mode, in_mode = self._modes()
        pdf = self.job.pdf_bytes if in_mode in ("both", "pdf") else None
        text = self._notice_text if in_mode in ("both", "text") else None
        content = ai_client.build_content(pdf, self.job.pdf_path.name, text, self._user_text(out_mode, in_mode))
        system = drafting.system_prompt()
        cfg, web = self._send_cfg(), self.chk_web.isChecked()
        choice = self._choice()

        def counted(input_tokens: int) -> None:
            p_in, p_out, p_search = ai.prices(cfg, choice)
            web_max = int(cfg["ai"]["web_search_max_uses"]) if web else 0
            typical, worst = usage.estimate(p_in, p_out, input_tokens, out_mode, web_max, p_search)
            spent = usage.month_spend()
            limit = float(cfg["ai"].get("monthly_limit_usd", 0) or 0)
            msg = (f"Send the content shown in 'What will be sent' to {ai.label(choice, cfg)}?\n\n"
                   f"It contains tokens only. Real names and numbers stay on this computer.\n\n"
                   f"Estimated cost: about ${typical:.2f} (at most ${worst:.2f}).\n"
                   f"Spent this month: ${spent:.2f}" + (f" of your ${limit:.2f} limit." if limit else "."))
            over = bool(limit) and spent + typical > limit
            if over:
                msg += "\n\nWARNING: this draft would take you over your monthly limit."
            if choice.startswith(ai.PREFIX) and not (p_in or p_out):
                msg += "\n\nNote: no prices are set for this provider in Settings, so the estimate shows $0."
            default = QMessageBox.StandardButton.No if over else QMessageBox.StandardButton.Yes
            if QMessageBox.question(self, "Send for drafting", msg,
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    default) != QMessageBox.StandardButton.Yes:
                self.lbl_info.setText("Not sent.")
                self.progress.setValue(0)
                self._status("idle")
                return
            self._output_mode = out_mode
            self._run("drafting the reply",
                      lambda progress: ai.draft_reply(system, content, cfg, web, progress), self._on_draft)

        self._run("estimating the cost",
                  lambda progress: ai.count_input_tokens(system, content, cfg, web), counted)

    def _on_draft(self, result: ai_client.DraftResult) -> None:
        usage.record(result.cost_usd)
        info = (f"Draft received from {result.model}. About ${result.cost_usd:.2f} "
                f"({result.input_tokens:,} in / {result.output_tokens:,} out tokens, {result.searches} web searches); "
                f"${usage.month_spend():.2f} spent this month. You can edit the text in the tabs before saving.")
        if result.notes:
            info += " " + " ".join(result.notes)
        self._show_answer(result.text, self._output_mode, info)

    def _show_answer(self, text: str, out_mode: str, info: str) -> None:
        """Restore tokens locally and show one editable tab per section, then the placeholders."""
        self._output_mode = "+".join(drafting.outputs_of(out_mode))
        self._output = drafting.finalise(text, self.job, self._output_mode)
        keep = {self.txt_sent, self.paste_box}
        for i in reversed(range(self.tabs.count())):
            if self.tabs.widget(i) not in keep:
                self.tabs.removeTab(i)
        titles = {"framing": "Issue framing (editable)", "reply": "Reply (editable)", "advisory": "Advisory (editable)", "law": "Law note (editable)"}
        self._views = {}
        first = -1
        for key, body in self._output.restored.items():
            view = QPlainTextEdit()
            view.setPlainText(body)
            view.setPlaceholderText("(The model did not return this section.)")
            idx = self.tabs.addTab(view, titles[key])
            first = idx if first < 0 else first
            self._views[key] = view
        self._add_placeholder_tab()
        self.tabs.setCurrentIndex(max(first, 0))
        if self._output.unrestored:
            info += (" WARNING: these tokens could not be restored and are left as-is: "
                     + ", ".join(self._output.unrestored))
        self.lbl_info.setText(info)
        self.b_save.setEnabled(True)

    # ------------------------------------------------------------------ placeholders
    def _add_placeholder_tab(self) -> None:
        """Table of [[...]] placeholders; values typed here stay on this computer."""
        placeholders = drafting.find_placeholders(self._output)
        known = client_facts.suggestions(placeholders, self._facts, self._ay) if self._facts_key else {}
        self.tbl_ph = QTableWidget(len(placeholders), 2)
        self.tbl_ph.setHorizontalHeaderLabels(["Placeholder in the draft", "Your value (leave blank to keep it)"])
        self.tbl_ph.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_ph.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_ph.verticalHeader().setVisible(False)
        for r, ph in enumerate(placeholders):
            item = QTableWidgetItem(ph)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl_ph.setItem(r, 0, item)
            # Enclosure lines read naturally as their own description, so pre-fill those.
            attach = re.match(r"\[\[\s*ATTACH\s*:\s*(.+?)\s*\]\]$", ph, re.IGNORECASE)
            value = known.get(ph) or (attach.group(1)[:1].upper() + attach.group(1)[1:] if attach else "")
            self.tbl_ph.setItem(r, 1, QTableWidgetItem(value))
        box = QWidget()
        lay = QVBoxLayout(box)
        intro = QLabel(
            "Fill in the facts the model did not have. These values are used only on this computer, when "
            "saving the Word files; they are never sent to any AI provider. Blank rows stay as [[...]] in the files."
            + (f"<br><b>{len(known)} value(s) pre-filled from this client's facts sheet.</b>" if known else "")
        )
        intro.setWordWrap(True)
        lay.addWidget(intro)
        lay.addWidget(self.tbl_ph)
        self.chk_remember = QCheckBox("Remember the values I type here in this client's facts sheet"
                                      + (f" (AY {self._ay})" if self._ay else ""))
        self.chk_remember.setChecked(bool(self._facts_key))
        self.chk_remember.setEnabled(bool(self._facts_key))
        lay.addWidget(self.chk_remember)
        self.tabs.addTab(box, f"Fill placeholders ({len(placeholders)})")

    def edit_facts(self) -> None:
        dlg = FactsDialog(self._client_name, self._facts, self._ay, self)
        if dlg.exec():
            self._facts = dlg.data
            self._ay = dlg.ay
            self._facts["name"] = self._client_name
            try:
                client_facts.save(self._facts_key, self._facts)
            except OSError:
                show_error(self, "Client facts", "The facts sheet could not be saved.")
                return
            if self._output is not None:
                for r, value in client_facts.suggestions(
                    [self.tbl_ph.item(i, 0).text() for i in range(self.tbl_ph.rowCount())], self._facts, self._ay
                ).items():
                    for i in range(self.tbl_ph.rowCount()):
                        cell = self.tbl_ph.item(i, 1)
                        if self.tbl_ph.item(i, 0).text() == r and not (cell and cell.text().strip()):
                            self.tbl_ph.setItem(i, 1, QTableWidgetItem(value))

    def _placeholder_values(self) -> dict[str, str]:
        values = {}
        for r in range(self.tbl_ph.rowCount()):
            cell = self.tbl_ph.item(r, 1)
            values[self.tbl_ph.item(r, 0).text()] = cell.text() if cell else ""
        return values

    # ------------------------------------------------------------------ save
    def save(self) -> None:
        if self._output is None:
            return
        values = self._placeholder_values()
        edited = drafting.DraftOutput(
            self._output.tokens, {k: v.toPlainText() for k, v in self._views.items()}, self._output.unrestored
        )
        filled = drafting.fill_placeholders(edited, values)
        for key, view in self._views.items():
            view.setPlainText(filled.restored.get(key, ""))
        try:
            paths = drafting.save_outputs(self.job, filled, self._output_mode, original=self._output)
        except UserFacingError as exc:
            show_error(self, "Save", str(exc))
            return
        learned = 0
        if self._facts_key and self.chk_remember.isChecked():
            learned = client_facts.learn(self._facts, values, self._ay)
            if learned:
                self._facts["name"] = self._client_name
                client_facts.save(self._facts_key, self._facts)
        if self.job.vault_meta.get("original_sha256"):
            register.advance(self.job.vault_meta["original_sha256"], "Drafted")
        msg = "Saved in the output folder:\n\n" + "\n".join(p.name for p in paths)
        if learned:
            msg += f"\n\n{learned} value(s) remembered in this client's facts sheet."
        show_info(self, "Saved", msg)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._running:
            event.ignore()
            return
        event.accept()
