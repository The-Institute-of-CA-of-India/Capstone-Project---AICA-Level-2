"""Settings, About, splash screen and friendly message dialogs."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplashScreen,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import FULL_TITLE, TAGLINE, VERSION
from ..core.allowlist import Allowlist
from ..core.config import resolve_path, save_config
from ..core.detectors import load_client_master, save_client_master
from ..core.models import UserFacingError

INDIGO = "#283593"
TEAL = "#009688"


def show_error(parent, title: str, message: str) -> None:
    """Plain-English error dialog (never a traceback)."""
    QMessageBox.warning(parent, title, message)


def show_info(parent, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)


def make_splash(icon_png: Path) -> QSplashScreen:
    """Splash screen: mask icon, name, tagline and version on the brand gradient."""
    w, h = 560, 320
    pm = QPixmap(w, h)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor(INDIGO))
    g.setColorAt(1, QColor(TEAL))
    p.fillRect(pm.rect(), g)
    icon = QPixmap(str(icon_png))
    if not icon.isNull():
        p.drawPixmap(40, 90, 140, 140, icon)
    p.setPen(QColor("white"))
    p.setFont(QFont("Segoe UI", 40, QFont.Weight.Bold))
    p.drawText(QRectF(200, 80, 340, 70), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Mukhota")
    p.setFont(QFont("Segoe UI", 14))
    p.drawText(QRectF(204, 150, 340, 30), Qt.AlignmentFlag.AlignLeft, "Private Notice Desk")
    p.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
    p.drawText(QRectF(204, 185, 340, 30), Qt.AlignmentFlag.AlignLeft, TAGLINE)
    p.setFont(QFont("Segoe UI", 10))
    p.drawText(QRectF(204, 270, 340, 24), Qt.AlignmentFlag.AlignLeft, f"Version {VERSION}  •  100% offline")
    p.end()
    splash = QSplashScreen(pm)
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    return splash


def show_about(parent, icon: QIcon) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle("About Mukhota")
    box.setIconPixmap(icon.pixmap(96, 96))
    box.setText(f"<h2>{FULL_TITLE}</h2><p><b>{TAGLINE}</b></p><p>Version {VERSION}</p>")
    box.setInformativeText(
        "Redacts PII from tax notices before they are shared.\n"
        "Works fully offline: no network calls, no telemetry, no auto-update.\n"
        "Originals are never modified."
    )
    box.exec()


class SettingsDialog(QDialog):
    """Edit config.yaml options, allowlist.yaml and client_master.csv."""

    def __init__(self, cfg: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mukhota - Settings")
        self.resize(760, 560)
        self.cfg = copy.deepcopy(cfg)
        self.allow_path = resolve_path(cfg, "allowlist")
        self.master_path = resolve_path(cfg, "client_master")

        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._allowlist_tab(), "Do-not-redact list")
        tabs.addTab(self._master_tab(), "Client master list")
        tabs.addTab(self._api_tab(), "AI providers")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addWidget(buttons)

    # ------------------------------------------------------------------ tabs
    def _general_tab(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self.chk_officer = QCheckBox("Redact officer name and ward/circle as role tokens")
        self.chk_officer.setChecked(bool(self.cfg["detection"]["redact_officer"]))
        self.chk_propagate = QCheckBox("Also find every other occurrence of each detected value")
        self.chk_propagate.setChecked(bool(self.cfg["detection"].get("propagate_values", True)))
        self.spn_accept = QDoubleSpinBox()
        self.spn_accept.setRange(0.0, 1.0)
        self.spn_accept.setSingleStep(0.05)
        self.spn_accept.setValue(float(self.cfg["detection"]["accept_threshold"]))
        self.spn_lowconf = QDoubleSpinBox()
        self.spn_lowconf.setRange(0.3, 1.0)
        self.spn_lowconf.setSingleStep(0.05)
        self.spn_lowconf.setValue(float(self.cfg["ocr"]["low_confidence_threshold"]))
        self.spn_dpi = QSpinBox()
        self.spn_dpi.setRange(150, 600)
        self.spn_dpi.setSingleStep(50)
        self.spn_dpi.setValue(int(self.cfg["ocr"]["dpi"]))
        self.txt_out = QLineEdit(self.cfg["paths"].get("output_root", ""))
        self.txt_out.setPlaceholderText("Empty = next to the original notice")
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse_out)
        row = QHBoxLayout()
        row.addWidget(self.txt_out, 1)
        row.addWidget(browse)
        f.addRow(self.chk_officer)
        f.addRow(self.chk_propagate)
        f.addRow("Pre-tick items with confidence at least", self.spn_accept)
        f.addRow("Flag OCR pages for manual review below", self.spn_lowconf)
        f.addRow("OCR resolution (DPI)", self.spn_dpi)
        f.addRow("Output folder", row)
        return w

    def _allowlist_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel(
            "Items matching these patterns or words are never redacted (sections, AY/FY, dates, amounts, "
            "notice DIN, form names, department names...). Patterns are regular expressions."
        ))
        self.txt_allow = QPlainTextEdit()
        self.txt_allow.setFont(QFont("Consolas", 10))
        self.txt_allow.setPlainText(self.allow_path.read_text(encoding="utf-8") if self.allow_path.exists() else "")
        lay.addWidget(self.txt_allow)
        return w

    def _master_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel(
            "Known client names, directors, partners, addresses and IDs. Matching ignores case, spacing, "
            "M/s, Pvt/Private and Ltd/Limited. Role 'assessee' becomes [ASSESSEE]; 'director' becomes [DIRECTOR_1]..."
        ))
        self.tbl = QTableWidget(0, 3)
        self.tbl.setHorizontalHeaderLabels(["Term", "PII type (NAME, ORG, ADDRESS, PAN...)", "Role"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        try:
            for e in load_client_master(self.master_path):
                self._add_row(e.term, e.pii_type, e.role)
        except UserFacingError as exc:
            show_error(self, "Client master list", str(exc))
        btns = QHBoxLayout()
        add = QPushButton("Add row")
        rem = QPushButton("Remove selected")
        add.clicked.connect(lambda: self._add_row("", "NAME", ""))
        rem.clicked.connect(self._remove_rows)
        btns.addWidget(add)
        btns.addWidget(rem)
        btns.addStretch(1)
        lay.addWidget(self.tbl)
        lay.addLayout(btns)
        return w

    def _api_tab(self) -> QWidget:
        from ..core import ai, ai_client, usage

        outer = QWidget()
        scroll_lay = QVBoxLayout(outer)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_lay.addWidget(scroll)
        w = QWidget()
        scroll.setWidget(w)
        f = QFormLayout(w)

        self.cmb_model = QComboBox()
        self.spn_search = QSpinBox()
        self.spn_search.setRange(0, 20)
        self.spn_search.setValue(int(self.cfg["ai"]["web_search_max_uses"]))
        self.spn_limit = QDoubleSpinBox()
        self.spn_limit.setRange(0, 10000)
        self.spn_limit.setDecimals(2)
        self.spn_limit.setPrefix("$ ")
        self.spn_limit.setSpecialValueText("No limit")
        self.spn_limit.setValue(float(self.cfg["ai"].get("monthly_limit_usd", 0) or 0))
        f.addRow("Default model for Draft Reply", self.cmb_model)
        f.addRow("Maximum web searches per draft", self.spn_search)
        f.addRow("Monthly spending limit", self.spn_limit)
        f.addRow("", QLabel(f"Spent this month: ${usage.month_spend():.2f}"))

        f.addRow(QLabel("<b>Claude (Anthropic)</b>"))
        self.lbl_key = QLabel()
        self.txt_key = QLineEdit()
        self.txt_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_key.setPlaceholderText("Paste a new API key to save or replace it")
        remove = QPushButton("Remove saved key")
        remove.clicked.connect(self._remove_key)
        self.cmb_effort = QComboBox()
        self.cmb_effort.addItems(["low", "medium", "high", "xhigh", "max"])
        self.cmb_effort.setCurrentText(str(self.cfg["ai"]["effort"]))
        f.addRow("Saved key", self.lbl_key)
        f.addRow("API key", self.txt_key)
        f.addRow("", remove)
        f.addRow("Effort (higher = more thorough, costlier)", self.cmb_effort)

        # Other providers: edited one at a time, kept in self._prov until Save.
        f.addRow(QLabel("<b>Other providers</b>"))
        self._prov = {pid: dict(ai.provider_cfg(self.cfg, pid), key="") for pid in ai.PROVIDERS}
        self._prov_shown = ""
        self.cmb_prov = QComboBox()
        for pid, p in ai.PROVIDERS.items():
            self.cmb_prov.addItem(p.label, pid)
        self.lbl_caps = QLabel()
        self.lbl_caps.setWordWrap(True)
        self.lbl_caps.setObjectName("muted")
        self.txt_purl = QLineEdit()
        self.txt_pmodel = QLineEdit()
        self.lbl_pkey = QLabel()
        self.txt_pkey = QLineEdit()
        self.txt_pkey.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_pkey.setPlaceholderText("Paste this provider's API key to save or replace it")
        self.b_premove = QPushButton("Remove this provider's key")
        self.b_premove.clicked.connect(self._remove_provider_key)
        self.spn_pin, self.spn_pout, self.spn_psearch = QDoubleSpinBox(), QDoubleSpinBox(), QDoubleSpinBox()
        for s, dec in ((self.spn_pin, 2), (self.spn_pout, 2), (self.spn_psearch, 3)):
            s.setRange(0, 1000)
            s.setDecimals(dec)
            s.setPrefix("$ ")
        self.spn_pmax = QSpinBox()
        self.spn_pmax.setRange(0, 1_000_000)
        self.spn_pmax.setSingleStep(1000)
        self.spn_pmax.setSpecialValueText("Provider default")
        f.addRow("Provider", self.cmb_prov)
        f.addRow("", self.lbl_caps)
        f.addRow("Server address", self.txt_purl)
        f.addRow("Model name", self.txt_pmodel)
        f.addRow("Saved key", self.lbl_pkey)
        f.addRow("API key", self.txt_pkey)
        f.addRow("", self.b_premove)
        f.addRow("Price per million input tokens", self.spn_pin)
        f.addRow("Price per million output tokens", self.spn_pout)
        f.addRow("Price per web search", self.spn_psearch)
        f.addRow("Max output tokens", self.spn_pmax)
        note = QLabel(
            "A provider appears in Draft Reply once it has a model name. Keys are kept in Windows Credential "
            "Manager, not in any file. Only Draft Reply uses the network, only for a verified redacted PDF, "
            "and only to the provider you choose."
        )
        note.setWordWrap(True)
        f.addRow(note)
        self.cmb_prov.currentIndexChanged.connect(lambda _i: self._show_provider(self.cmb_prov.currentData()))
        self.txt_pmodel.editingFinished.connect(self._fill_default_models)
        self.txt_purl.editingFinished.connect(self._fill_default_models)
        self._show_provider(self.cmb_prov.currentData())
        self._fill_default_models(ai.current(self.cfg))
        self._refresh_key_label()
        return outer

    def _store_provider(self) -> None:
        pid = self._prov_shown
        if not pid:
            return
        pc = self._prov[pid]
        pc.update(base_url=self.txt_purl.text().strip(), model=self.txt_pmodel.text().strip(),
                  price_in=self.spn_pin.value(), price_out=self.spn_pout.value(),
                  price_search=self.spn_psearch.value(), max_tokens=self.spn_pmax.value(), key=self.txt_pkey.text())

    def _show_provider(self, pid: str) -> None:
        from ..core import ai

        self._store_provider()
        self._prov_shown = pid
        p, pc = ai.PROVIDERS[pid], self._prov[pid]
        self.txt_purl.setText(pc.get("base_url", ""))
        self.txt_purl.setReadOnly(not p.url_editable)
        self.txt_purl.setPlaceholderText("https://... (http:// only for this computer)" if p.url_editable else "")
        self.txt_pmodel.setText(pc.get("model", ""))
        self.txt_pmodel.setPlaceholderText(f"e.g. {p.example_model}" if p.example_model else "Model name")
        self.txt_pkey.setText(pc.get("key", ""))
        self.spn_pin.setValue(float(pc.get("price_in") or 0))
        self.spn_pout.setValue(float(pc.get("price_out") or 0))
        self.spn_psearch.setValue(float(pc.get("price_search") or 0))
        self.spn_psearch.setEnabled(p.web)
        self.spn_pmax.setValue(int(pc.get("max_tokens") or 0))
        saved = ai.key_saved(pid)
        self.lbl_pkey.setText("No key needed" if not p.needs_key else "A key is saved" if saved else "No key saved")
        self.txt_pkey.setEnabled(p.needs_key or saved)
        self.b_premove.setEnabled(saved)
        self.lbl_caps.setText("Reads the redacted PDF and can search the web, like Claude." if p.pdf and p.web
                              else ai.NO_PDF_WEB)

    def _fill_default_models(self, selected: str | None = None) -> None:
        from ..core import ai, ai_client

        self._store_provider()
        keep = selected or self.cmb_model.currentData()
        self.cmb_model.clear()
        for model_id, info in ai_client.MODELS.items():
            self.cmb_model.addItem(f"{info.label}  (${info.price_in:g} / ${info.price_out:g} per M tokens)", model_id)
        for pid, pc in self._prov.items():
            if pc.get("model") and pc.get("base_url"):
                self.cmb_model.addItem(f"{ai.PROVIDERS[pid].label} - {pc['model']}", ai.PREFIX + pid)
        self.cmb_model.setCurrentIndex(max(self.cmb_model.findData(keep), 0))

    def _refresh_key_label(self) -> None:
        from ..core import ai_client

        self.lbl_key.setText("A key is saved" if ai_client.has_api_key() else "No key saved")

    def _remove_key(self) -> None:
        from ..core import ai_client

        ai_client.clear_api_key()
        self._refresh_key_label()

    def _remove_provider_key(self) -> None:
        from ..core import ai

        pid = self._prov_shown
        if QMessageBox.question(self, "Remove saved key",
                                f"Remove the saved {ai.PROVIDERS[pid].label} API key from Windows Credential Manager?") \
                == QMessageBox.StandardButton.Yes:
            ai.clear_key(pid)
            self._prov[pid]["key"] = ""
            self._prov_shown = ""
            self._show_provider(pid)

    # ------------------------------------------------------------------ helpers
    def _add_row(self, term: str, pii_type: str, role: str) -> None:
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        for col, v in enumerate((term, pii_type, role)):
            self.tbl.setItem(r, col, QTableWidgetItem(v))

    def _remove_rows(self) -> None:
        for r in sorted({i.row() for i in self.tbl.selectedIndexes()}, reverse=True):
            self.tbl.removeRow(r)

    def _browse_out(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if d:
            self.txt_out.setText(d)

    def _save(self) -> None:
        text = self.txt_allow.toPlainText()
        try:
            data = yaml.safe_load(text) or {}
            if not isinstance(data, dict):
                raise UserFacingError("The do-not-redact list must contain 'patterns', 'context_patterns' and 'words' sections.")
            Allowlist.from_dict(data)
        except yaml.YAMLError:
            show_error(self, "Do-not-redact list", "The do-not-redact list is not valid YAML. Please check indentation and quotes.")
            return
        except UserFacingError as exc:
            show_error(self, "Do-not-redact list", str(exc))
            return
        from ..core import ai

        self._store_provider()
        keys = []
        try:
            for pid, pc in self._prov.items():
                if ai.PROVIDERS[pid].url_editable and pc.get("base_url"):
                    pc["base_url"] = ai.check_url(pc["base_url"])
                pc["model"] = ai.check_model(pc.get("model", ""))
        except UserFacingError as exc:
            show_error(self, "AI providers", str(exc))
            return
        for pid, pc in self._prov.items():
            key = pc.pop("key", "")
            if key.strip():
                keys.append((pid, key))
            self.cfg.setdefault("providers", {})[pid] = {
                "base_url": pc.get("base_url", ""), "model": pc.get("model", ""),
                "price_in": round(float(pc.get("price_in") or 0), 4), "price_out": round(float(pc.get("price_out") or 0), 4),
                "price_search": round(float(pc.get("price_search") or 0), 4), "max_tokens": int(pc.get("max_tokens") or 0)}
            pc["key"] = key
        rows = []
        for r in range(self.tbl.rowCount()):
            vals = [(self.tbl.item(r, c).text() if self.tbl.item(r, c) else "") for c in range(3)]
            rows.append((vals[0], vals[1], vals[2]))
        try:
            self.allow_path.write_text(text, encoding="utf-8")
            save_client_master(self.master_path, rows)
            self.cfg["detection"]["redact_officer"] = self.chk_officer.isChecked()
            self.cfg["detection"]["propagate_values"] = self.chk_propagate.isChecked()
            self.cfg["detection"]["accept_threshold"] = round(self.spn_accept.value(), 2)
            self.cfg["ocr"]["low_confidence_threshold"] = round(self.spn_lowconf.value(), 2)
            self.cfg["ocr"]["dpi"] = self.spn_dpi.value()
            self.cfg["paths"]["output_root"] = self.txt_out.text().strip()
            self.cfg["ai"]["effort"] = self.cmb_effort.currentText()
            self.cfg["ai"]["model"] = self.cmb_model.currentData()
            self.cfg["ai"]["monthly_limit_usd"] = round(self.spn_limit.value(), 2)
            self.cfg["ai"]["web_search_max_uses"] = self.spn_search.value()
            save_config(self.cfg)
            if self.txt_key.text().strip():
                from ..core import ai_client

                ai_client.set_api_key(self.txt_key.text())
            for pid, key in keys:
                ai.set_key(pid, key)
        except OSError:
            show_error(self, "Settings", "Settings could not be saved. Check that the Mukhota folder is not read-only.")
            return
        except UserFacingError as exc:
            show_error(self, "Settings", str(exc))
            return
        self.accept()
