#!/usr/bin/env python3
"""
ATS CV Filter
Desktop (PyQt6) edition of the ATS CV Shortlisting system.

Uses the existing Python screening engine (ats_engine.py) for weighted,
deterministic CV matching, and adds a colourful desktop interface for:
  - Vacancy & weighted criteria management (weights must total 100%)
  - High-volume CV ingestion (files / whole folders) with SHA-256 duplicate detection
  - Screening, ranking and strict threshold-based shortlisting
  - HR approval sign-off, Excel report export and ZIP download of shortlisted CVs
"""

import os
import sys
import io
import json
import uuid
import shutil
import hashlib
import zipfile
import html
import urllib.parse
from datetime import datetime

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate, QTime, QDateTime, QTimer, QUrl
from PyQt6.QtGui import QColor, QBrush, QFont, QTextDocument, QPageLayout, QPageSize, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QStackedWidget, QListWidget, QListWidgetItem, QLineEdit,
    QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QFileDialog, QMessageBox,
    QProgressBar, QDialog, QScrollArea, QFormLayout, QButtonGroup, QSizePolicy, QInputDialog,
    QDateTimeEdit, QSplitter,
)

import ats_engine

APP_NAME = "ATS CV Filter"
APP_VERSION = "1.0"
SUPPORTED_EXTS = (".pdf", ".docx", ".txt", ".md")


# --------------------------------------------------------------------------- #
#  Paths & storage
# --------------------------------------------------------------------------- #

def resource_dir():
    """Folder holding bundled read-only files (PyInstaller extracts to _MEIPASS)."""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def app_dir():
    """Writable folder next to the .exe (or next to this script)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DATA_DIR = os.path.join(app_dir(), "app_data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
VACANCIES_FILE = os.path.join(DATA_DIR, "vacancies.json")
SAMPLE_DIR = os.path.join(resource_dir(), "data", "sample_cvs")
SEED_VACANCIES = os.path.join(resource_dir(), "data", "vacancies.json")


def ensure_storage():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    if not os.path.exists(VACANCIES_FILE):
        if os.path.exists(SEED_VACANCIES):
            shutil.copyfile(SEED_VACANCIES, VACANCIES_FILE)
        else:
            with open(VACANCIES_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)


def load_vacancies():
    try:
        with open(VACANCIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_vacancies(vacancies):
    tmp = VACANCIES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(vacancies, f, indent=2)
    os.replace(tmp, VACANCIES_FILE)


def default_criteria():
    return {
        "threshold": 90,
        "top_n": 10,
        "weights": {"qualifications": 25, "skills": 35, "experience": 25, "mandatory": 15},
        "qualifications": [],
        "skills": [],
        "experience": {"required_years": 3, "domains": []},
        "mandatory": [],
    }


# --------------------------------------------------------------------------- #
#  Document text extraction
# --------------------------------------------------------------------------- #

def extract_text(path, raw):
    """Returns (text, is_ocr_scanned)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md", ".csv"):
        return raw.decode("utf-8", errors="ignore"), False
    if ext == ".docx":
        return ats_engine.extract_text_from_docx(raw), False
    if ext == ".pdf":
        text = ""
        parsed = False
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
            parsed = True
        except Exception:
            text = ""
        # The raw-stream fallback is only for PDFs pypdf cannot open. A PDF that opens but has no
        # text is a scanned image: running the fallback on its image data can take minutes per file.
        if not parsed and len(raw) <= 5 * 1024 * 1024:
            text = ats_engine.extract_text_from_raw_pdf(raw) or text
        # A PDF with no usable text layer is treated as a scanned image
        return text, len(text.strip()) < 40
    return "", False


def collect_cv_files(folder):
    found = []
    for root, _dirs, files in os.walk(folder):
        for name in files:
            if name.lower().endswith(SUPPORTED_EXTS):
                found.append(os.path.join(root, name))
    return sorted(found)


class IngestWorker(QThread):
    """Reads, hashes, stores and parses CVs off the UI thread."""
    progress = pyqtSignal(int, int, str)
    loaded = pyqtSignal(dict)   # one CV record, as soon as it is read
    done = pyqtSignal(list)

    def __init__(self, paths, known_hashes):
        super().__init__()
        self.paths = paths
        self.known_hashes = dict(known_hashes)  # hash -> filename

    def run(self):
        records = []
        total = len(self.paths)
        for i, path in enumerate(self.paths, 1):
            filename = os.path.basename(path)
            self.progress.emit(i, total, filename)
            try:
                with open(path, "rb") as f:
                    raw = f.read()
            except OSError:
                continue
            file_hash = hashlib.sha256(raw).hexdigest()
            saved_path = os.path.join(UPLOAD_DIR, f"{file_hash[:12]}_{filename}")
            if not os.path.exists(saved_path):
                try:
                    with open(saved_path, "wb") as f:
                        f.write(raw)
                except OSError:
                    saved_path = path
            text, scanned = extract_text(path, raw)
            duplicate_of = self.known_hashes.get(file_hash)
            if duplicate_of is None:
                self.known_hashes[file_hash] = filename
            records.append({
                "id": f"cv-{uuid.uuid4().hex[:10]}",
                "filename": filename,
                "savedPath": saved_path,
                "fileHash": file_hash,
                "fileSize": len(raw),
                "text": text,
                "is_ocr_scanned": scanned,
                "unreadable": len(text.strip()) < 40,
                "is_duplicate": duplicate_of is not None,
                "duplicate_of": duplicate_of,
            })
            self.loaded.emit(records[-1])
        self.done.emit(records)


# --------------------------------------------------------------------------- #
#  Styling
# --------------------------------------------------------------------------- #

PALETTE = {
    "purple": "#7b2ff7",
    "pink": "#f107a3",
    "orange": "#ff8a00",
    "teal": "#00c9a7",
    "blue": "#2d8cff",
    "red": "#ff4d6d",
    "yellow": "#ffc93c",
    "ink": "#1f2041",
    "muted": "#6b6f8e",
    "bg": "#f3f5ff",
}

STATUS_COLORS = {
    "Shortlisted": "#00b894",
    "Qualified (Exceeds Top N Limit)": "#2d8cff",
    "Under Threshold": "#ff8a00",
    "Disqualified (Mandatory Not Met)": "#ff4d6d",
    "Needs HR Review (Unreadable)": "#9b59ff",
}

DECISION_COLORS = {"Approved": "#00b894", "Rejected": "#ff4d6d", "Pending": "#ff8a00"}

# --------------------------------------------------------------------------- #
#  Interview pipeline (after HR approval)
# --------------------------------------------------------------------------- #

INVITE_STATUSES = ["Not invited", "Invited", "Confirmed", "Rescheduled", "Declined"]
INTERVIEW_MODES = ["In person", "Video call", "Phone"]
INTERVIEW_OUTCOMES = ["Pending", "Pass", "Fail", "On hold", "No show"]
FINAL_DECISIONS = ["Pending", "Offer", "Hold", "Reject"]
MGMT_STATUSES = ["Pending", "Approved", "Rejected"]

PIPELINE_FIELDS = {
    "invite": {"status": "Not invited", "date": "", "mode": "In person", "location": "", "interviewer": ""},
    "l1": {"date": "", "interviewer": "", "outcome": "Pending", "score": 0, "feedback": ""},
    "l2": {"date": "", "interviewer": "", "outcome": "Pending", "score": 0, "feedback": ""},
    "final": {"decision": "Pending", "salary": "", "joining": "", "notes": ""},
    "mgmt": {"status": "Pending", "approver": "", "date": "", "comments": ""},
}

PIPELINE_SECTION_NAMES = {
    "invite": "Call for interview", "l1": "Level 1 interview", "l2": "Level 2 interview",
    "final": "Final decision", "mgmt": "Management approval",
}


def pipeline_of(cand):
    """Returns the candidate's pipeline record, filling in any missing fields."""
    p = cand.setdefault("pipeline", {})
    for section, fields in PIPELINE_FIELDS.items():
        sec = p.setdefault(section, {})
        for key, default in fields.items():
            sec.setdefault(key, default)
    p.setdefault("log", [])
    return p


def pipeline_stage(p):
    """(label, colour) describing where a candidate is in the interview pipeline."""
    inv, l1, l2, fin, mg = p["invite"], p["l1"], p["l2"], p["final"], p["mgmt"]
    if mg["status"] == "Approved":
        return "Hired - management approved", "#00b894"
    if mg["status"] == "Rejected":
        return "Offer rejected by management", "#ff4d6d"
    if fin["decision"] == "Offer":
        return "Offer - awaiting management approval", "#2d8cff"
    if fin["decision"] == "Reject":
        return "Not selected (final decision)", "#ff4d6d"
    if fin["decision"] == "Hold":
        return "Final decision on hold", "#ff8a00"
    if l2["outcome"] == "Pass":
        return "Awaiting final decision", "#7b2ff7"
    if l2["outcome"] in ("Fail", "No show"):
        return f"Not selected at Level 2 ({l2['outcome']})", "#ff4d6d"
    if l2["outcome"] == "On hold":
        return "Level 2 on hold", "#ff8a00"
    if l1["outcome"] == "Pass":
        return ("Level 2 scheduled" if l2["date"] else "Awaiting Level 2 interview"), "#7b2ff7"
    if l1["outcome"] in ("Fail", "No show"):
        return f"Not selected at Level 1 ({l1['outcome']})", "#ff4d6d"
    if l1["outcome"] == "On hold":
        return "Level 1 on hold", "#ff8a00"
    if inv["status"] == "Declined":
        return "Declined interview", "#ff4d6d"
    if inv["status"] in ("Invited", "Confirmed", "Rescheduled"):
        return f"Interview {inv['status'].lower()}", "#2d8cff"
    return "To be called for interview", "#6b6f8e"


_NO_DATE = QDateTime(QDate(2000, 1, 1), QTime(0, 0))


class OptionalDateEdit(QDateTimeEdit):
    """Date picker that can be left empty ("Not set"); its calendar opens on today rather than the year 2000."""

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self.dateTime() == _NO_DATE:
            today = QDate.currentDate()
            self.calendarWidget().setCurrentPage(today.year(), today.month())


def make_date_edit(with_time=True):
    w = OptionalDateEdit()
    w.setCalendarPopup(True)
    w.setDisplayFormat("dd MMM yyyy  HH:mm" if with_time else "dd MMM yyyy")
    w.setMinimumDateTime(_NO_DATE)
    w.setSpecialValueText("Not set")
    w.setDateTime(_NO_DATE)
    w.setProperty("with_time", with_time)
    w.setToolTip("Leave as 'Not set' if there is no date yet")
    return w


def date_edit_value(w):
    if w.dateTime() == _NO_DATE:
        return ""
    return w.dateTime().toString("yyyy-MM-dd HH:mm" if w.property("with_time") else "yyyy-MM-dd")


def set_date_edit(w, value):
    dt = QDateTime()
    if value:
        dt = QDateTime.fromString(value, "yyyy-MM-dd HH:mm")
        if not dt.isValid():
            dt = QDateTime(QDate.fromString(value, "yyyy-MM-dd"), QTime(0, 0))
    w.setDateTime(dt if dt.isValid() else _NO_DATE)


STYLESHEET = """
QMainWindow, #Central { background: #f3f5ff; }
QWidget { font-family: 'Segoe UI'; font-size: 13px; color: #1f2041; }

#Header {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #7b2ff7, stop:0.5 #f107a3, stop:1 #ff8a00);
}
#AppTitle { color: white; font-size: 22px; font-weight: 800; }
#AppSubtitle { color: rgba(255,255,255,0.88); font-size: 12px; }
#Header QLabel#VacLabel { color: white; font-weight: 700; }
#Header QComboBox {
    background: rgba(255,255,255,0.95); border: none; border-radius: 8px;
    padding: 6px 10px; min-width: 260px; font-weight: 600;
}

#Sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #24124f, stop:1 #3a1c71);
}
#Sidebar QPushButton {
    color: #e9e6ff; text-align: left; padding: 13px 18px; border: none;
    border-radius: 12px; font-size: 14px; font-weight: 600; background: transparent;
}
#Sidebar QPushButton:hover { background: rgba(255,255,255,0.12); }
#Sidebar QPushButton:checked {
    color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f107a3, stop:1 #ff8a00);
}
#SideFooter { color: rgba(255,255,255,0.6); font-size: 11px; }

#Card {
    background: white; border: 1px solid #e4e7fb; border-radius: 16px;
}
#PageTitle { font-size: 22px; font-weight: 800; color: #24124f; }
#PageHint { color: #6b6f8e; }
#SectionTitle { font-size: 15px; font-weight: 700; color: #3a1c71; }

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7b2ff7, stop:1 #2d8cff);
    color: white; border: none; border-radius: 10px; padding: 9px 16px; font-weight: 700;
}
QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6a1fe6, stop:1 #1f7aeb); }
QPushButton:disabled { background: #c9cbe0; color: #f4f4f8; }
QPushButton[kind="success"] { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b894, stop:1 #00d2d3); }
QPushButton[kind="warning"] { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff8a00, stop:1 #ffc93c); }
QPushButton[kind="danger"]  { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff4d6d, stop:1 #ff758f); }
QPushButton[kind="pink"]    { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f107a3, stop:1 #ff5fa2); }

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #fafbff; border: 1.5px solid #dfe3f8; border-radius: 9px; padding: 6px 8px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QComboBox:focus { border: 1.5px solid #7b2ff7; background: white; }

QListWidget {
    background: #fafbff; border: 1.5px solid #dfe3f8; border-radius: 10px; padding: 4px;
}
QListWidget::item { padding: 10px; border-radius: 8px; margin: 2px; }
QListWidget::item:selected {
    color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7b2ff7, stop:1 #f107a3);
}

QTableWidget {
    background: white; border: 1px solid #e4e7fb; border-radius: 10px;
    gridline-color: #eef0fb; alternate-background-color: #f7f8ff;
    selection-background-color: #e5d9ff; selection-color: #1f2041;
}
QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3a1c71, stop:1 #7b2ff7);
    color: white; font-weight: 700; padding: 8px; border: none;
}

QProgressBar {
    background: #eceefe; border: none; border-radius: 8px; height: 16px;
    text-align: center; color: #1f2041; font-weight: 700;
}
QProgressBar::chunk {
    border-radius: 8px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00c9a7, stop:1 #2d8cff);
}
QScrollArea { border: none; background: transparent; }
#PageScroll, #Page { background: #f3f5ff; }
QDialog, QMessageBox { background: #f3f5ff; }
QComboBox QAbstractItemView {
    background: white; color: #1f2041; selection-background-color: #e5d9ff; selection-color: #1f2041;
}
"""


def light_palette():
    """Fixed light palette so Windows dark mode cannot turn page backgrounds dark."""
    from PyQt6.QtGui import QPalette
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: "#f3f5ff",
        QPalette.ColorRole.WindowText: "#1f2041",
        QPalette.ColorRole.Base: "#ffffff",
        QPalette.ColorRole.AlternateBase: "#f7f8ff",
        QPalette.ColorRole.Text: "#1f2041",
        QPalette.ColorRole.Button: "#ffffff",
        QPalette.ColorRole.ButtonText: "#1f2041",
        QPalette.ColorRole.Highlight: "#7b2ff7",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: "#ffffff",
        QPalette.ColorRole.ToolTipText: "#1f2041",
        QPalette.ColorRole.PlaceholderText: "#9aa0c3",
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    return pal


def make_button(text, kind=None):
    # "&" marks a keyboard shortcut in Qt button text; "&&" shows a literal ampersand
    btn = QPushButton(text.replace("&", "&&"))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if kind:
        btn.setProperty("kind", kind)
    return btn


def make_card():
    card = QFrame()
    card.setObjectName("Card")
    return card


def page_header(title, hint):
    box = QVBoxLayout()
    t = QLabel(title)
    t.setObjectName("PageTitle")
    h = QLabel(hint)
    h.setObjectName("PageHint")
    h.setWordWrap(True)
    box.addWidget(t)
    box.addWidget(h)
    return box


def section_title(text):
    lbl = QLabel(text)
    lbl.setObjectName("SectionTitle")
    return lbl


class StatCard(QFrame):
    def __init__(self, title, color_a, color_b, icon):
        super().__init__()
        self.setMinimumHeight(118)
        self.setStyleSheet(f"""
            QFrame {{
                border-radius: 18px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {color_a}, stop:1 {color_b});
            }}
            QLabel {{ color: white; background: transparent; }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        top = QHBoxLayout()
        t = QLabel(title)
        t.setStyleSheet("font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.92);")
        ic = QLabel(icon)
        ic.setStyleSheet("font-size: 24px;")
        top.addWidget(t)
        top.addStretch()
        top.addWidget(ic)
        self.value = QLabel("0")
        self.value.setStyleSheet("font-size: 32px; font-weight: 800;")
        self.caption = QLabel("")
        self.caption.setStyleSheet("font-size: 11px; color: rgba(255,255,255,0.85);")
        lay.addLayout(top)
        lay.addWidget(self.value)
        lay.addWidget(self.caption)

    def set(self, value, caption=""):
        self.value.setText(str(value))
        self.caption.setText(caption)


# --------------------------------------------------------------------------- #
#  Candidate detail dialog
# --------------------------------------------------------------------------- #

class CandidateDialog(QDialog):
    def __init__(self, cand, weights, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Candidate Evaluation - {cand.get('name', '')}")
        self.resize(760, 680)
        self.setStyleSheet(STYLESHEET + "QDialog { background: #f3f5ff; }")

        outer = QVBoxLayout(self)
        status = cand.get("status", "")
        color = STATUS_COLORS.get(status, PALETTE["purple"])

        banner = QFrame()
        banner.setStyleSheet(f"""
            QFrame {{ border-radius: 16px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {color}, stop:1 #7b2ff7); }}
            QLabel {{ color: white; background: transparent; }}
        """)
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(20, 16, 20, 16)
        left = QVBoxLayout()
        name = QLabel(f"#{cand.get('rank', '-')}  {cand.get('name', 'Candidate')}")
        name.setStyleSheet("font-size: 20px; font-weight: 800;")
        meta = QLabel(f"{cand.get('email', '')}   |   {cand.get('phone', '')}\n{cand.get('filename', '')}")
        meta.setStyleSheet("font-size: 12px;")
        st = QLabel(status)
        st.setStyleSheet("font-size: 13px; font-weight: 700;")
        left.addWidget(name)
        left.addWidget(meta)
        left.addWidget(st)
        pct = QLabel(f"{cand.get('matching_percentage', 0):.1f}%")
        pct.setStyleSheet("font-size: 40px; font-weight: 900;")
        bl.addLayout(left, 1)
        bl.addWidget(pct)
        outer.addWidget(banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)

        scores_card = make_card()
        sl = QGridLayout(scores_card)
        sl.setContentsMargins(16, 14, 16, 14)
        sl.addWidget(section_title("Weighted Category Scores"), 0, 0, 1, 3)
        colors = {"qualifications": "#7b2ff7", "skills": "#2d8cff", "experience": "#00b894", "mandatory": "#f107a3"}
        scores = cand.get("category_scores", {})
        for row, key in enumerate(["qualifications", "skills", "experience", "mandatory"], 1):
            lbl = QLabel(f"{key.title()}  (weight {weights.get(key, 0)}%)")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(round(scores.get(key, 0))))
            bar.setFormat(f"{scores.get(key, 0):.1f}%")
            bar.setStyleSheet(f"QProgressBar::chunk {{ border-radius: 8px; background: {colors[key]}; }}")
            sl.addWidget(lbl, row, 0)
            sl.addWidget(bar, row, 1, 1, 2)
        lay.addWidget(scores_card)

        def list_card(title, items, color, empty="None"):
            card = make_card()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 14, 16, 14)
            t = section_title(title)
            t.setStyleSheet(f"color: {color};")
            cl.addWidget(t)
            text = "\n".join(f"• {i}" for i in items) if items else empty
            body_lbl = QLabel(text)
            body_lbl.setWordWrap(True)
            body_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            cl.addWidget(body_lbl)
            return card

        lay.addWidget(list_card("Strengths", cand.get("strengths", []), "#00b894"))
        lay.addWidget(list_card("Gaps / Missing Requirements", cand.get("missing_requirements", []), "#ff4d6d"))
        lay.addWidget(list_card("Verbatim Evidence from CV", cand.get("evidence", []), "#2d8cff"))
        lay.addWidget(list_card("Flags for HR", cand.get("flags", []), "#ff8a00", "No flags raised"))
        lay.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        close = make_button("Close")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        outer.addLayout(row)


# --------------------------------------------------------------------------- #
#  Main window
# --------------------------------------------------------------------------- #

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ensure_storage()
        self.vacancies = load_vacancies()
        self.cv_pool = []          # ingested CV records for the current session
        self.worker = None
        self.editing_id = None     # vacancy id shown in the criteria form

        self.setWindowTitle(APP_NAME)
        self.resize(1380, 860)
        self.setMinimumSize(1100, 700)

        central = QWidget()
        central.setObjectName("Central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.stack.addWidget(self._wrap(self._build_dashboard()))
        self.stack.addWidget(self._wrap(self._build_vacancy_page()))
        self.stack.addWidget(self._wrap(self._build_upload_page()))
        self.stack.addWidget(self._wrap(self._build_results_page()))
        self.stack.addWidget(self._wrap(self._build_approval_page()))
        self.stack.addWidget(self._wrap(self._build_pipeline_page()))
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)

        self.refresh_vacancy_selectors()
        self.select_page(0)

    # ---------------- layout helpers ---------------- #

    def _wrap(self, widget):
        widget.setObjectName("Page")
        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    def _build_header(self):
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(86)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(26, 10, 26, 10)
        logo = QLabel("\U0001F50E")
        logo.setStyleSheet("font-size: 38px; background: transparent;")
        titles = QVBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("AppTitle")
        sub = QLabel("Automated CV screening  •  Weighted criteria  •  Unbiased shortlisting  •  HR sign-off  •  Interview pipeline")
        sub.setObjectName("AppSubtitle")
        titles.addWidget(title)
        titles.addWidget(sub)
        lay.addWidget(logo)
        lay.addSpacing(8)
        lay.addLayout(titles)
        lay.addStretch()
        vl = QLabel("Active vacancy:")
        vl.setObjectName("VacLabel")
        self.active_combo = QComboBox()
        self.active_combo.currentIndexChanged.connect(self.on_active_vacancy_changed)
        lay.addWidget(vl)
        lay.addWidget(self.active_combo)
        return header

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(250)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(14, 22, 14, 18)
        lay.setSpacing(8)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        items = [
            ("\U0001F4CA   Dashboard", 0),
            ("\U0001F4DD   Vacancies & Criteria", 1),
            ("\U0001F4C2   CV Upload Center", 2),
            ("\U0001F3AF   Screening & Shortlist", 3),
            ("✅   HR Approval & Export", 4),
            ("\U0001F5D3   Interview Pipeline", 5),
        ]
        for text, idx in items:
            btn = QPushButton(text.replace("&", "&&"))
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=idx: self.select_page(i))
            self.nav_group.addButton(btn, idx)
            lay.addWidget(btn)
        lay.addStretch()
        foot = QLabel(f"v{APP_VERSION}\nFinal hiring decisions remain\nwith the HR manager.")
        foot.setObjectName("SideFooter")
        lay.addWidget(foot)
        return side

    def select_page(self, idx):
        self.stack.setCurrentIndex(idx)
        btn = self.nav_group.button(idx)
        if btn:
            btn.setChecked(True)
        if idx == 0:
            self.refresh_dashboard()
        elif idx == 3:
            self.refresh_results()
        elif idx == 4:
            self.refresh_approval()
        elif idx == 5:
            self.refresh_pipeline()

    # ---------------- vacancy helpers ---------------- #

    def active_vacancy(self):
        vid = self.active_combo.currentData()
        return next((v for v in self.vacancies if v.get("id") == vid), None)

    def refresh_vacancy_selectors(self, select_id=None):
        current = select_id or self.active_combo.currentData()
        self.active_combo.blockSignals(True)
        self.active_combo.clear()
        for v in self.vacancies:
            self.active_combo.addItem(f"{v.get('title', 'Untitled')}  ({v.get('department', '')})", v.get("id"))
        idx = self.active_combo.findData(current)
        self.active_combo.setCurrentIndex(idx if idx >= 0 else (0 if self.vacancies else -1))
        self.active_combo.blockSignals(False)

        self.vac_list.blockSignals(True)
        self.vac_list.clear()
        status_icon = {"Active": "\U0001F7E2", "Draft": "\U0001F7E1", "Archived": "⚪"}
        for v in self.vacancies:
            item = QListWidgetItem(f"{status_icon.get(v.get('status'), '')}  {v.get('title', 'Untitled')}\n      {v.get('department', '')}")
            item.setData(Qt.ItemDataRole.UserRole, v.get("id"))
            self.vac_list.addItem(item)
        self.vac_list.blockSignals(False)

        target = self.editing_id or self.active_combo.currentData()
        for i in range(self.vac_list.count()):
            if self.vac_list.item(i).data(Qt.ItemDataRole.UserRole) == target:
                self.vac_list.setCurrentRow(i)
                break
        else:
            if self.vac_list.count():
                self.vac_list.setCurrentRow(0)
        self.on_active_vacancy_changed()

    def on_active_vacancy_changed(self, *_):
        page = self.stack.currentIndex() if hasattr(self, "stack") else -1
        if page == 0:
            self.refresh_dashboard()
        elif page == 3:
            self.refresh_results()
        elif page == 4:
            self.refresh_approval()
        elif page == 5:
            self.refresh_pipeline()
        if hasattr(self, "upload_vac_label"):
            v = self.active_vacancy()
            self.upload_vac_label.setText(f"Screening against: {v['title']}" if v else "No vacancy selected")

    # ================= Dashboard ================= #

    def _build_dashboard(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(18)
        lay.addLayout(page_header("Dashboard", "Live overview of vacancies, CV intake and shortlisting outcomes."))

        grid = QGridLayout()
        grid.setSpacing(16)
        self.stat_vac = StatCard("Vacancies", "#7b2ff7", "#b06ab3", "\U0001F4BC")
        self.stat_cvs = StatCard("CVs Loaded (session)", "#2d8cff", "#00c9a7", "\U0001F4C4")
        self.stat_short = StatCard("Shortlisted (active)", "#00b894", "#55efc4", "⭐")
        self.stat_flags = StatCard("Needs HR Review", "#ff8a00", "#f107a3", "⚠️")
        for i, card in enumerate([self.stat_vac, self.stat_cvs, self.stat_short, self.stat_flags]):
            grid.addWidget(card, 0, i)
        lay.addLayout(grid)

        card = make_card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.addWidget(section_title("Vacancy Screening History"))
        self.dash_table = QTableWidget(0, 6)
        self.dash_table.setHorizontalHeaderLabels(
            ["Vacancy", "Department", "Status", "Evaluated", "Shortlisted", "Last Screened"])
        self._setup_table(self.dash_table)
        self.dash_table.setMinimumHeight(260)
        cl.addWidget(self.dash_table)
        lay.addWidget(card)

        steps = make_card()
        sl = QVBoxLayout(steps)
        sl.setContentsMargins(18, 16, 18, 16)
        sl.addWidget(section_title("How it works"))
        guide = QLabel(
            "<b style='color:#7b2ff7'>1. Vacancies & Criteria</b> &mdash; define the job and weight the 4 categories (must total 100%).<br>"
            "<b style='color:#2d8cff'>2. CV Upload Center</b> &mdash; add CV files or entire folders (PDF, DOCX, TXT). Duplicates are detected by SHA-256.<br>"
            "<b style='color:#00b894'>3. Screening & Shortlist</b> &mdash; run the engine; only candidates meeting the threshold AND all mandatory requirements are shortlisted.<br>"
            "<b style='color:#f107a3'>4. HR Approval & Export</b> &mdash; sign off, export the Excel report and download shortlisted CVs as a ZIP.")
        guide.setWordWrap(True)
        guide.setTextFormat(Qt.TextFormat.RichText)
        sl.addWidget(guide)
        lay.addWidget(steps)
        lay.addStretch()
        return w

    def refresh_dashboard(self):
        active = self.active_vacancy()
        results = (active or {}).get("results") or {}
        cands = results.get("ranked_candidates", [])
        self.stat_vac.set(len(self.vacancies),
                          f"{sum(1 for v in self.vacancies if v.get('status') == 'Active')} active")
        self.stat_cvs.set(len(self.cv_pool),
                          f"{sum(1 for c in self.cv_pool if c['is_duplicate'])} duplicates detected")
        self.stat_short.set(results.get("qualifying_count", 0),
                            f"of top {results.get('top_n_cap', '-')} at ≥{results.get('threshold_applied', '-')}%"
                            if results else "Run a screening to see results")
        self.stat_flags.set(sum(1 for c in cands if c.get("unreadable") or c.get("is_duplicate")),
                            "Unreadable / duplicate CVs")

        self.dash_table.setRowCount(len(self.vacancies))
        for r, v in enumerate(self.vacancies):
            res = v.get("results") or {}
            vals = [v.get("title", ""), v.get("department", ""), v.get("status", ""),
                    str(res.get("total_evaluated", "-")), str(res.get("qualifying_count", "-")),
                    self._fmt_date(v.get("lastScreenedAt") or res.get("processed_at"))]
            for c, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if c == 2:
                    col = {"Active": "#00b894", "Draft": "#ff8a00", "Archived": "#6b6f8e"}.get(val, "#1f2041")
                    item.setForeground(QBrush(QColor(col)))
                    item.setFont(self._bold())
                self.dash_table.setItem(r, c, item)

    # ================= Vacancies & Criteria ================= #

    def _build_vacancy_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)
        lay.addLayout(page_header(
            "Vacancies & Weighted Criteria",
            "Create or edit a vacancy. One item per line in each list. Missing any mandatory requirement disqualifies a candidate."))

        row = QHBoxLayout()
        row.setSpacing(16)

        # Left: list of vacancies
        left = make_card()
        left.setFixedWidth(300)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(14, 14, 14, 14)
        ll.addWidget(section_title("Saved Vacancies"))
        self.vac_list = QListWidget()
        self.vac_list.currentItemChanged.connect(self.on_vac_list_changed)
        ll.addWidget(self.vac_list, 1)
        new_btn = make_button("➕  New Vacancy", "success")
        new_btn.clicked.connect(self.new_vacancy)
        del_btn = make_button("\U0001F5D1  Delete Vacancy", "danger")
        del_btn.clicked.connect(self.delete_vacancy)
        ll.addWidget(new_btn)
        ll.addWidget(del_btn)
        row.addWidget(left)

        # Right: form
        right = make_card()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(18, 16, 18, 16)
        rl.setSpacing(10)

        rl.addWidget(section_title("Job Details"))
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.f_title = QLineEdit()
        self.f_dept = QLineEdit()
        self.f_status = QComboBox()
        self.f_status.addItems(["Active", "Draft", "Archived"])
        form.addRow("Job title:", self.f_title)
        form.addRow("Department:", self.f_dept)
        form.addRow("Status:", self.f_status)
        rl.addLayout(form)

        jd_row = QHBoxLayout()
        jd_row.addWidget(QLabel("Job description:"))
        jd_row.addStretch()
        imp = make_button("\U0001F4E5  Import JD (.txt/.docx/.pdf)", "pink")
        imp.clicked.connect(self.import_jd)
        jd_row.addWidget(imp)
        rl.addLayout(jd_row)
        self.f_desc = QPlainTextEdit()
        self.f_desc.setMinimumHeight(110)
        rl.addWidget(self.f_desc)

        rl.addWidget(section_title("Category Weights (must total 100%)"))
        wrow = QHBoxLayout()
        self.w_spins = {}
        wcolors = {"qualifications": "#7b2ff7", "skills": "#2d8cff", "experience": "#00b894", "mandatory": "#f107a3"}
        for key in ["qualifications", "skills", "experience", "mandatory"]:
            box = QVBoxLayout()
            lbl = QLabel(key.title())
            lbl.setStyleSheet(f"color: {wcolors[key]}; font-weight: 700;")
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setSuffix(" %")
            spin.valueChanged.connect(self.update_weight_total)
            self.w_spins[key] = spin
            box.addWidget(lbl)
            box.addWidget(spin)
            wrow.addLayout(box)
        self.weight_total = QLabel()
        self.weight_total.setMinimumWidth(150)
        self.weight_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrow.addWidget(self.weight_total)
        rl.addLayout(wrow)

        rl.addWidget(section_title("Shortlisting Rules"))
        rules = QHBoxLayout()
        self.f_threshold = QDoubleSpinBox()
        self.f_threshold.setRange(0, 100)
        self.f_threshold.setDecimals(1)
        self.f_threshold.setSuffix(" %")
        self.f_topn = QSpinBox()
        self.f_topn.setRange(1, 1000)
        self.f_years = QSpinBox()
        self.f_years.setRange(0, 45)
        self.f_years.setSuffix(" years")
        for label, wid in [("Minimum match threshold:", self.f_threshold),
                           ("Target shortlist cap (Top N):", self.f_topn),
                           ("Required experience:", self.f_years)]:
            rules.addWidget(QLabel(label))
            rules.addWidget(wid)
            rules.addSpacing(10)
        rules.addStretch()
        rl.addLayout(rules)

        grid = QGridLayout()
        grid.setSpacing(10)
        self.f_quals = QPlainTextEdit()
        self.f_skills = QPlainTextEdit()
        self.f_domains = QPlainTextEdit()
        self.f_mandatory = QPlainTextEdit()
        for i, (label, wid, color) in enumerate([
            ("\U0001F393 Qualifications", self.f_quals, "#7b2ff7"),
            ("\U0001F6E0 Skills", self.f_skills, "#2d8cff"),
            ("\U0001F4C8 Experience Domains", self.f_domains, "#00b894"),
            ("⛔ Mandatory Requirements (dealbreakers)", self.f_mandatory, "#ff4d6d"),
        ]):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {color}; font-weight: 700;")
            wid.setMinimumHeight(110)
            wid.setPlaceholderText("One item per line")
            grid.addWidget(lbl, (i // 2) * 2, i % 2)
            grid.addWidget(wid, (i // 2) * 2 + 1, i % 2)
        rl.addLayout(grid)

        save_row = QHBoxLayout()
        save_row.addStretch()
        save = make_button("\U0001F4BE  Save Vacancy", "success")
        save.clicked.connect(self.save_vacancy)
        use = make_button("\U0001F3AF  Save & Set Active")
        use.clicked.connect(lambda: self.save_vacancy(set_active=True))
        save_row.addWidget(save)
        save_row.addWidget(use)
        rl.addLayout(save_row)

        row.addWidget(right, 1)
        lay.addLayout(row, 1)
        return w

    def update_weight_total(self):
        total = sum(s.value() for s in self.w_spins.values())
        ok = total == 100
        color = "#00b894" if ok else "#ff4d6d"
        mark = "✔" if ok else "✖"
        self.weight_total.setText(f"Total: {total}%  {mark}")
        self.weight_total.setStyleSheet(
            f"color: white; background: {color}; border-radius: 10px; padding: 10px; font-weight: 800;")

    def fill_form(self, vac):
        crit = vac.get("criteria") or default_criteria()
        weights = crit.get("weights", {})
        self.f_title.setText(vac.get("title", ""))
        self.f_dept.setText(vac.get("department", ""))
        self.f_status.setCurrentText(vac.get("status", "Active"))
        self.f_desc.setPlainText(vac.get("description", ""))
        for key, spin in self.w_spins.items():
            spin.setValue(int(weights.get(key, 0)))
        self.f_threshold.setValue(float(crit.get("threshold", 90)))
        self.f_topn.setValue(int(crit.get("top_n", 10)))
        exp = crit.get("experience", {})
        self.f_years.setValue(int(exp.get("required_years", 3)))
        self.f_quals.setPlainText("\n".join(crit.get("qualifications", [])))
        self.f_skills.setPlainText("\n".join(crit.get("skills", [])))
        self.f_domains.setPlainText("\n".join(exp.get("domains", [])))
        self.f_mandatory.setPlainText("\n".join(crit.get("mandatory", [])))
        self.update_weight_total()

    def on_vac_list_changed(self, current, _prev=None):
        if not current:
            return
        vid = current.data(Qt.ItemDataRole.UserRole)
        vac = next((v for v in self.vacancies if v.get("id") == vid), None)
        if vac:
            self.editing_id = vid
            self.fill_form(vac)

    def new_vacancy(self):
        self.editing_id = None
        self.vac_list.clearSelection()
        self.fill_form({"title": "", "department": "", "status": "Draft", "description": "",
                        "criteria": default_criteria()})
        self.f_title.setFocus()

    @staticmethod
    def _lines(edit):
        return [l.strip() for l in edit.toPlainText().splitlines() if l.strip()]

    def save_vacancy(self, set_active=False):
        title = self.f_title.text().strip()
        if not title:
            QMessageBox.warning(self, APP_NAME, "Please enter a job title.")
            return
        total = sum(s.value() for s in self.w_spins.values())
        if total != 100:
            QMessageBox.warning(self, APP_NAME,
                                f"Category weights must total exactly 100% (currently {total}%).")
            return
        criteria = {
            "threshold": self.f_threshold.value(),
            "top_n": self.f_topn.value(),
            "weights": {k: s.value() for k, s in self.w_spins.items()},
            "qualifications": self._lines(self.f_quals),
            "skills": self._lines(self.f_skills),
            "experience": {"required_years": self.f_years.value(), "domains": self._lines(self.f_domains)},
            "mandatory": self._lines(self.f_mandatory),
        }
        now = datetime.now().isoformat()
        vac = next((v for v in self.vacancies if v.get("id") == self.editing_id), None)
        if vac is None:
            vac = {"id": f"vac-{uuid.uuid4().hex[:10]}", "createdAt": now, "results": None}
            self.vacancies.append(vac)
        vac.update({
            "title": title,
            "department": self.f_dept.text().strip(),
            "status": self.f_status.currentText(),
            "description": self.f_desc.toPlainText(),
            "criteria": criteria,
            "updatedAt": now,
        })
        self.editing_id = vac["id"]
        save_vacancies(self.vacancies)
        self.refresh_vacancy_selectors(select_id=vac["id"] if set_active else None)
        QMessageBox.information(self, APP_NAME, f"Vacancy “{title}” saved.")

    def delete_vacancy(self):
        item = self.vac_list.currentItem()
        if not item:
            return
        vid = item.data(Qt.ItemDataRole.UserRole)
        vac = next((v for v in self.vacancies if v.get("id") == vid), None)
        if not vac:
            return
        if QMessageBox.question(self, APP_NAME, f"Delete vacancy “{vac.get('title')}” and its screening history?") \
                != QMessageBox.StandardButton.Yes:
            return
        self.vacancies = [v for v in self.vacancies if v.get("id") != vid]
        self.editing_id = None
        save_vacancies(self.vacancies)
        self.refresh_vacancy_selectors()

    def import_jd(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import job description", "",
                                              "Documents (*.txt *.docx *.pdf *.md)")
        if not path:
            return
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as e:
            QMessageBox.critical(self, APP_NAME, f"Could not read file:\n{e}")
            return
        text, _ = extract_text(path, raw)
        if not text.strip():
            QMessageBox.warning(self, APP_NAME, "No readable text was found in that document.")
            return
        self.f_desc.setPlainText(text.strip())
        if not self.f_title.text().strip():
            self.f_title.setText(os.path.splitext(os.path.basename(path))[0].replace("_", " "))

    # ================= CV Upload Center ================= #

    def _build_upload_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)
        lay.addLayout(page_header(
            "CV Upload Center",
            "Add individual CVs or whole folders (hundreds or thousands of files). Files are copied to protected "
            "storage, hashed with SHA-256 for duplicate detection, and scanned PDFs are flagged for HR review."))

        actions = make_card()
        al = QHBoxLayout(actions)
        al.setContentsMargins(16, 14, 16, 14)
        b_files = make_button("\U0001F4C4  Add CV Files")
        b_files.clicked.connect(self.add_files)
        b_folder = make_button("\U0001F4C1  Add Folder", "pink")
        b_folder.clicked.connect(self.add_folder)
        b_sample = make_button("✨  Load Sample Candidate Batch", "warning")
        b_sample.clicked.connect(self.load_samples)
        b_clear = make_button("\U0001F9F9  Clear Batch", "danger")
        b_clear.clicked.connect(self.clear_pool)
        for b in (b_files, b_folder, b_sample, b_clear):
            al.addWidget(b)
        al.addStretch()
        self.upload_vac_label = QLabel()
        self.upload_vac_label.setStyleSheet("font-weight: 700; color: #7b2ff7;")
        al.addWidget(self.upload_vac_label)
        lay.addWidget(actions)

        self.ingest_bar = QProgressBar()
        self.ingest_bar.setVisible(False)
        lay.addWidget(self.ingest_bar)

        chips = QHBoxLayout()
        self.chip_total = self._chip("#2d8cff")
        self.chip_ok = self._chip("#00b894")
        self.chip_ocr = self._chip("#ff8a00")
        self.chip_dup = self._chip("#f107a3")
        for c in (self.chip_total, self.chip_ok, self.chip_ocr, self.chip_dup):
            chips.addWidget(c)
        chips.addStretch()
        lay.addLayout(chips)

        card = make_card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.addWidget(section_title("Current Batch"))
        self.pool_table = QTableWidget(0, 5)
        self.pool_table.setHorizontalHeaderLabels(["File", "Size", "SHA-256", "Text Extracted", "Status"])
        self._setup_table(self.pool_table)
        self.pool_table.setMinimumHeight(360)
        cl.addWidget(self.pool_table)

        go = QHBoxLayout()
        go.addStretch()
        run = make_button("\U0001F680  Run Screening Now", "success")
        run.setMinimumHeight(44)
        run.clicked.connect(self.run_screening)
        go.addWidget(run)
        cl.addLayout(go)
        lay.addWidget(card, 1)
        self.refresh_pool()
        return w

    def _chip(self, color):
        lbl = QLabel()
        lbl.setStyleSheet(f"background: {color}; color: white; border-radius: 12px; padding: 6px 14px; font-weight: 700;")
        return lbl

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select CV files", "",
                                                "CV documents (*.pdf *.docx *.txt *.md)")
        if paths:
            self.start_ingest(paths)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select a folder containing CVs")
        if not folder:
            return
        paths = collect_cv_files(folder)
        if not paths:
            QMessageBox.information(self, APP_NAME, "No PDF, DOCX or TXT files were found in that folder.")
            return
        self.start_ingest(paths)

    def load_samples(self):
        if not os.path.isdir(SAMPLE_DIR):
            QMessageBox.warning(self, APP_NAME, f"Sample folder not found:\n{SAMPLE_DIR}")
            return
        self.start_ingest(collect_cv_files(SAMPLE_DIR))

    def clear_pool(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, APP_NAME, "Please wait for the current upload to finish.")
            return
        self.cv_pool = []
        self.refresh_pool()

    def start_ingest(self, paths):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, APP_NAME, "Please wait for the current upload to finish.")
            return
        known = {c["fileHash"]: c["filename"] for c in self.cv_pool}
        self.worker = IngestWorker(paths, known)
        self.worker.progress.connect(self.on_ingest_progress)
        self.worker.loaded.connect(self.on_cv_loaded)
        self.worker.done.connect(self.on_ingest_done)
        self.ingest_bar.setVisible(True)
        self.ingest_bar.setRange(0, len(paths))
        self.ingest_bar.setValue(0)
        self.worker.start()

    def on_ingest_progress(self, i, total, name):
        self.ingest_bar.setValue(i)
        self.ingest_bar.setFormat(f"Processing {i}/{total}: {name}")

    def on_cv_loaded(self, record):
        self.cv_pool.append(record)
        # Redraw the list in batches so thousands of CVs don't slow the window down
        if len(self.cv_pool) % 10 == 0:
            self.refresh_pool()

    def on_ingest_done(self, records):
        have = {c["id"] for c in self.cv_pool}
        self.cv_pool.extend(r for r in records if r["id"] not in have)
        self.ingest_bar.setVisible(False)
        self.refresh_pool()

    def refresh_pool(self):
        pool = self.cv_pool
        self.chip_total.setText(f"\U0001F4C4 {len(pool)} CVs")
        self.chip_ok.setText(f"✔ {sum(1 for c in pool if not c['unreadable'])} readable")
        self.chip_ocr.setText(f"\U0001F50D {sum(1 for c in pool if c['unreadable'] or c['is_ocr_scanned'])} scanned / unreadable")
        self.chip_dup.setText(f"♻ {sum(1 for c in pool if c['is_duplicate'])} duplicates")

        self.pool_table.setRowCount(len(pool))
        for r, c in enumerate(pool):
            if c["is_duplicate"]:
                status, color = f"Duplicate of {c['duplicate_of']}", "#f107a3"
            elif c["unreadable"]:
                status, color = "Unreadable / scanned - HR review", "#ff8a00"
            else:
                status, color = "Ready", "#00b894"
            vals = [c["filename"], self._fmt_size(c["fileSize"]), c["fileHash"][:16] + "…",
                    f"{len(c['text'].strip()):,} chars", status]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if col == 4:
                    item.setForeground(QBrush(QColor(color)))
                    item.setFont(self._bold())
                self.pool_table.setItem(r, col, item)
        if hasattr(self, "stat_cvs"):
            self.refresh_dashboard()

    # ================= Screening ================= #

    def run_screening(self):
        vac = self.active_vacancy()
        if not vac:
            QMessageBox.warning(self, APP_NAME, "Create and select a vacancy first.")
            return
        if not self.cv_pool:
            QMessageBox.warning(self, APP_NAME, "Add some CVs (or load the sample batch) before screening.")
            return
        crit = vac.get("criteria") or default_criteria()
        if sum(crit.get("weights", {}).values()) != 100:
            QMessageBox.warning(self, APP_NAME, "This vacancy's weights do not total 100%. Fix them first.")
            return
        if QMessageBox.question(
                self, APP_NAME,
                f"Screen {len(self.cv_pool)} CVs against:\n\n{vac.get('title')}  ({vac.get('department', '')})\n\n"
                "To use a different vacancy, choose it in the Active vacancy box at the top right.") \
                != QMessageBox.StandardButton.Yes:
            return

        payload = {
            "criteria": crit,
            "cvs": [{"id": c["id"], "filename": c["filename"], "text": c["text"],
                     "file_hash": c["fileHash"], "is_ocr_scanned": c["is_ocr_scanned"]} for c in self.cv_pool],
        }
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = ats_engine.process_screening_batch(payload)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, APP_NAME, f"Screening failed:\n{e}")
            return
        QApplication.restoreOverrideCursor()

        paths = {c["id"]: c["savedPath"] for c in self.cv_pool}
        for cand in result["ranked_candidates"]:
            cand["savedPath"] = paths.get(cand["id"], "")
            cand["hr_approved"] = False
        vac["results"] = result
        vac["lastScreenedAt"] = result.get("processed_at")
        save_vacancies(self.vacancies)
        self.select_page(3)

    def _build_results_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)
        lay.addLayout(page_header(
            "Screening & Shortlist",
            "Candidates ranked by weighted match. Only those meeting the threshold AND every mandatory requirement "
            "are shortlisted - the threshold is never lowered. Double-click a row for full evidence."))

        self.summary_banner = QLabel()
        self.summary_banner.setWordWrap(True)
        lay.addWidget(self.summary_banner)

        tools = QHBoxLayout()
        tools.addWidget(QLabel("Show:"))
        self.res_filter = QComboBox()
        self.res_filter.addItems(["All candidates", "Shortlisted only", "Disqualified", "Needs HR review"])
        self.res_filter.currentIndexChanged.connect(self.refresh_results)
        tools.addWidget(self.res_filter)
        self.res_search = QLineEdit()
        self.res_search.setPlaceholderText("\U0001F50E Search candidate name or file…")
        self.res_search.textChanged.connect(self.refresh_results)
        tools.addWidget(self.res_search, 1)
        view = make_button("\U0001F441  View Details")
        view.clicked.connect(self.open_selected_candidate)
        dl = make_button("⬇  Save Original CV", "pink")
        dl.clicked.connect(self.download_selected_cv)
        rerun = make_button("\U0001F501  Re-run Screening", "warning")
        rerun.clicked.connect(self.run_screening)
        for b in (view, dl, rerun):
            tools.addWidget(b)
        lay.addLayout(tools)

        card = make_card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 12)
        self.res_table = QTableWidget(0, 10)
        self.res_table.setHorizontalHeaderLabels(
            ["Rank", "Candidate", "Match %", "Qualif.", "Skills", "Experience", "Mandatory", "Years", "Status", "Flags"])
        self._setup_table(self.res_table)
        self.res_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.res_table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        self.res_table.setMinimumHeight(420)
        self.res_table.cellDoubleClicked.connect(lambda *_: self.open_selected_candidate())
        cl.addWidget(self.res_table)
        lay.addWidget(card, 1)

        self.dup_label = QLabel()
        self.dup_label.setWordWrap(True)
        lay.addWidget(self.dup_label)
        return w

    def _filtered_candidates(self):
        vac = self.active_vacancy()
        cands = ((vac or {}).get("results") or {}).get("ranked_candidates", [])
        mode = self.res_filter.currentIndex()
        if mode == 1:
            cands = [c for c in cands if c.get("shortlisted")]
        elif mode == 2:
            cands = [c for c in cands if not c.get("mandatory_met") and not c.get("unreadable")]
        elif mode == 3:
            cands = [c for c in cands if c.get("unreadable") or c.get("is_duplicate")]
        q = self.res_search.text().strip().lower()
        if q:
            cands = [c for c in cands if q in c.get("name", "").lower() or q in c.get("filename", "").lower()]
        return cands

    def refresh_results(self, *_):
        vac = self.active_vacancy()
        res = (vac or {}).get("results")
        if not res:
            self.summary_banner.setText("No screening has been run for this vacancy yet. Go to the CV Upload Center and click “Run Screening Now”.")
            self.summary_banner.setStyleSheet(self._banner_style("#6b6f8e", "#9aa0c3"))
            self.res_table.setRowCount(0)
            self.dup_label.setText("")
            return

        q, cap, thr = res.get("qualifying_count", 0), res.get("top_n_cap", 10), res.get("threshold_applied", 90)
        total = res.get("total_evaluated", 0)
        if q >= cap:
            msg = f"⭐  {q} candidates shortlisted (cap {cap}) out of {total} evaluated at ≥{thr}% match."
            style = self._banner_style("#00b894", "#00c9a7")
        elif q > 0:
            msg = (f"⭐  Only {q} of {total} candidates qualify for the top-{cap} shortlist at ≥{thr}%. "
                   f"Integrity guarantee: the threshold has NOT been lowered to fill the shortlist.")
            style = self._banner_style("#ff8a00", "#f107a3")
        else:
            msg = (f"⚠  No candidate out of {total} met the ≥{thr}% threshold and all mandatory requirements. "
                   f"The threshold has NOT been lowered.")
            style = self._banner_style("#ff4d6d", "#f107a3")
        self.summary_banner.setText(msg + f"\nScreened: {self._fmt_date(res.get('processed_at'))}")
        self.summary_banner.setStyleSheet(style)

        cands = self._filtered_candidates()
        self.res_table.setRowCount(len(cands))
        for r, c in enumerate(cands):
            sc = c.get("category_scores", {})
            pct = c.get("matching_percentage", 0)
            vals = [str(c.get("rank", "")), c.get("name", ""), f"{pct:.1f}%",
                    f"{sc.get('qualifications', 0):.0f}", f"{sc.get('skills', 0):.0f}",
                    f"{sc.get('experience', 0):.0f}", f"{sc.get('mandatory', 0):.0f}",
                    str(c.get("years_experience", "-")), c.get("status", ""), "; ".join(c.get("flags", []))]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, c.get("id"))
                if col == 2:
                    item.setBackground(QBrush(QColor(self._pct_color(pct))))
                    item.setForeground(QBrush(QColor("white")))
                    item.setFont(self._bold())
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif col == 8:
                    item.setForeground(QBrush(QColor(STATUS_COLORS.get(val, "#1f2041"))))
                    item.setFont(self._bold())
                elif col in (0, 3, 4, 5, 6, 7):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.res_table.setItem(r, col, item)

        dups = res.get("duplicates") or []
        if dups:
            self.dup_label.setText("♻  Duplicate submissions detected: " + "; ".join(
                f"{d['duplicate_file']} = {d['original_file']}" for d in dups))
            self.dup_label.setStyleSheet("color: #f107a3; font-weight: 700;")
        else:
            self.dup_label.setText("")

    def _selected_candidate(self):
        row = self.res_table.currentRow()
        if row < 0:
            QMessageBox.information(self, APP_NAME, "Select a candidate in the table first.")
            return None
        cid = self.res_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        vac = self.active_vacancy()
        return next((c for c in vac["results"]["ranked_candidates"] if c.get("id") == cid), None)

    def open_selected_candidate(self):
        cand = self._selected_candidate()
        if cand:
            weights = self.active_vacancy()["criteria"].get("weights", {})
            CandidateDialog(cand, weights, self).exec()

    def download_selected_cv(self):
        cand = self._selected_candidate()
        if not cand:
            return
        src = cand.get("savedPath", "")
        if not src or not os.path.exists(src):
            QMessageBox.warning(self, APP_NAME, "The original CV file is no longer available in storage.")
            return
        dest, _ = QFileDialog.getSaveFileName(self, "Save original CV", cand.get("filename", "cv"))
        if dest:
            shutil.copyfile(src, dest)
            QMessageBox.information(self, APP_NAME, f"Saved to:\n{dest}")

    # ================= HR Approval & Export ================= #

    def _build_approval_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)
        lay.addLayout(page_header(
            "HR Approval & Export",
            "Tick candidates in the proposed shortlist and approve or reject them, then complete the sign-off with "
            "audit notes. Exports include approved candidates only. Final hiring decisions remain with the HR manager."))

        self.appr_status = QLabel()
        self.appr_status.setWordWrap(True)
        lay.addWidget(self.appr_status)

        name_card = make_card()
        nml = QHBoxLayout(name_card)
        nml.setContentsMargins(16, 12, 16, 12)
        nml.addWidget(section_title("HR manager:"))
        self.appr_name = QLineEdit()
        self.appr_name.setPlaceholderText("Your name - recorded against every decision (required)")
        nml.addWidget(self.appr_name, 1)
        lay.addWidget(name_card)

        card = make_card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.addWidget(section_title("Proposed Shortlist"))
        hint = QLabel("Change one candidate with the HR Decision dropdown in their row, or tick several rows and click "
                      "Approve Selected / Reject Selected. Double-click a Reason / Comment cell to type a comment.")
        hint.setObjectName("PageHint")
        hint.setWordWrap(True)
        cl.addWidget(hint)
        self.appr_table = QTableWidget(0, 9)
        self.appr_table.setHorizontalHeaderLabels(
            ["Select", "Rank", "Candidate", "Email", "Phone", "Match %", "HR Decision", "Reason / Comment", "Decided by"])
        self._setup_table(self.appr_table)
        self.appr_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked
                                        | QAbstractItemView.EditTrigger.SelectedClicked
                                        | QAbstractItemView.EditTrigger.EditKeyPressed)
        header = self.appr_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for col in (0, 1, 5, 8):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.appr_table.setColumnWidth(6, 130)
        self.appr_table.verticalHeader().setDefaultSectionSize(38)
        self.appr_table.setMinimumHeight(300)
        # Clicking on a row's details ticks / unticks it
        self.appr_table.cellClicked.connect(self.toggle_approval_row)
        self.appr_table.itemChanged.connect(self.on_approval_item_changed)
        cl.addWidget(self.appr_table)

        sel_row = QHBoxLayout()
        b_all = make_button("☑  Select All")
        b_all.clicked.connect(lambda: self.set_all_approval_checks(True))
        b_none = make_button("☐  Clear Selection", "warning")
        b_none.clicked.connect(lambda: self.set_all_approval_checks(False))
        b_ok = make_button("✅  Approve Selected", "success")
        b_ok.clicked.connect(lambda: self.decide_selected("Approved"))
        b_no = make_button("❌  Reject Selected", "danger")
        b_no.clicked.connect(lambda: self.decide_selected("Rejected"))
        self.appr_sel_label = QLabel()
        self.appr_sel_label.setStyleSheet("font-weight: 700; color: #7b2ff7;")
        for b in (b_all, b_none):
            sel_row.addWidget(b)
        sel_row.addWidget(self.appr_sel_label)
        sel_row.addStretch()
        sel_row.addWidget(b_ok)
        sel_row.addWidget(b_no)
        cl.addLayout(sel_row)
        lay.addWidget(card)

        notes_card = make_card()
        nl = QVBoxLayout(notes_card)
        nl.setContentsMargins(16, 14, 16, 14)
        nl.addWidget(section_title("HR Sign-off Notes (audit log)"))
        self.appr_notes = QTextEdit()
        self.appr_notes.setPlaceholderText("e.g. Reviewed evidence for all shortlisted candidates; proceed to interviews.")
        self.appr_notes.setFixedHeight(90)
        nl.addWidget(self.appr_notes)
        approve = make_button("\U0001F58A  Complete Sign-off", "success")
        approve.clicked.connect(self.approve_shortlist)
        nl.addWidget(approve, alignment=Qt.AlignmentFlag.AlignRight)
        lay.addWidget(notes_card)

        exp_card = make_card()
        el = QHBoxLayout(exp_card)
        el.setContentsMargins(16, 14, 16, 14)
        x = make_button("\U0001F4CA  Export Excel Report (.xlsx)")
        x.clicked.connect(self.export_excel)
        z = make_button("\U0001F5DC  Download Approved CVs (.zip)", "pink")
        z.clicked.connect(self.export_zip)
        p = make_button("\U0001F5A8  Print Audit Trail", "warning")
        p.clicked.connect(self.print_audit)
        f = make_button("\U0001F4C4  Save Audit Trail (PDF)", "success")
        f.clicked.connect(self.save_audit_pdf)
        for b in (x, z, p, f):
            el.addWidget(b)
        el.addStretch()
        lay.addWidget(exp_card)
        lay.addStretch()
        return w

    @staticmethod
    def _decision(cand):
        """HR decision for a shortlisted candidate: Approved, Rejected or Pending."""
        return cand.get("hr_decision") or ("Approved" if cand.get("hr_approved") else "Pending")

    def _shortlist(self):
        vac = self.active_vacancy()
        res = (vac or {}).get("results") or {}
        return vac, res, [c for c in res.get("ranked_candidates", []) if c.get("shortlisted")]

    def refresh_approval(self):
        _vac, res, short = self._shortlist()
        appr = res.get("hr_approval")
        counts = {d: sum(1 for c in short if self._decision(c) == d) for d in ("Approved", "Rejected", "Pending")}
        tally = f"{counts['Approved']} approved, {counts['Rejected']} rejected, {counts['Pending']} pending"
        if not res:
            self.appr_status.setText("Run a screening for this vacancy first.")
            self.appr_status.setStyleSheet(self._banner_style("#6b6f8e", "#9aa0c3"))
        elif appr:
            self.appr_status.setText(
                f"✅  Sign-off completed by {appr.get('approved_by', 'HR')} on {self._fmt_date(appr.get('approved_at'))}: "
                f"{appr.get('approved_count', 0)} approved, {appr.get('rejected_count', 0)} rejected.\n"
                f"Notes: {appr.get('notes') or '-'}")
            self.appr_status.setStyleSheet(self._banner_style("#00b894", "#2d8cff"))
        elif not short:
            self.appr_status.setText(
                f"⚠  No candidates met the shortlist rules (≥{res.get('threshold_applied', '-')}% match and every "
                f"mandatory requirement) out of {res.get('total_evaluated', 0)} evaluated - nothing to approve.")
            self.appr_status.setStyleSheet(self._banner_style("#ff4d6d", "#f107a3"))
        elif counts["Pending"]:
            self.appr_status.setText(f"⏳  Awaiting HR decisions - {tally}.")
            self.appr_status.setStyleSheet(self._banner_style("#ff8a00", "#ffc93c"))
        else:
            self.appr_status.setText(f"\U0001F58A  All candidates decided ({tally}). Click Complete Sign-off to finish.")
            self.appr_status.setStyleSheet(self._banner_style("#2d8cff", "#7b2ff7"))

        self.appr_table.blockSignals(True)
        self.appr_table.clearSpans()
        if not short:
            self.appr_table.setRowCount(1)
            self.appr_table.setSpan(0, 0, 1, self.appr_table.columnCount())
            msg = ("No shortlisted candidates yet. Check the Screening & Shortlist page, or adjust the "
                   "vacancy criteria and re-run the screening." if res else
                   "Load CVs in the CV Upload Center and click Run Screening Now.")
            item = QTableWidgetItem(msg)
            item.setForeground(QBrush(QColor(PALETTE["muted"])))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.appr_table.setItem(0, 0, item)
            self.appr_table.blockSignals(False)
            self.update_selection_label()
            return
        self.appr_table.setRowCount(len(short))
        read_only = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        for r, c in enumerate(short):
            decision = self._decision(c)
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check.setCheckState(Qt.CheckState.Unchecked)
            check.setData(Qt.ItemDataRole.UserRole, c.get("id"))
            self.appr_table.setItem(r, 0, check)
            decided = (f"{c.get('hr_decided_by', 'HR')}  {self._fmt_date(c.get('hr_decided_at'))}"
                       if decision != "Pending" and c.get("hr_decided_at") else "")
            vals = [str(c.get("rank", "")), c.get("name", ""), c.get("email", ""), c.get("phone", ""),
                    f"{c.get('matching_percentage', 0):.1f}%", "", c.get("hr_reason", ""), decided]
            for col, val in enumerate(vals, 1):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, c.get("id"))
                if col == 7:
                    item.setToolTip("Double-click to type a reason or comment")
                else:
                    item.setFlags(read_only)
                self.appr_table.setItem(r, col, item)
            self.appr_table.setCellWidget(r, 6, self._decision_combo(c.get("id"), decision))
        self.appr_table.blockSignals(False)
        self.update_selection_label()

    def _decision_combo(self, cid, decision):
        color = DECISION_COLORS[decision]
        combo = QComboBox()
        combo.addItems(["Pending", "Approved", "Rejected"])
        combo.setCurrentText(decision)
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        combo.setStyleSheet(
            f"QComboBox {{ color: white; background: {color}; border: none; border-radius: 8px;"
            f" padding: 4px 10px; margin: 3px; font-weight: 700; }}")
        combo.currentTextChanged.connect(lambda value, cid=cid: self.on_decision_combo(cid, value))
        return combo

    def on_decision_combo(self, cid, value):
        _vac, _res, short = self._shortlist()
        cand = next((c for c in short if c.get("id") == cid), None)
        if cand is None or value == self._decision(cand):
            return
        reason = None
        if value == "Rejected":
            reason, ok = QInputDialog.getText(
                self, APP_NAME, f"Reason for rejecting {cand.get('name')} (recorded in the audit trail):",
                text=cand.get("hr_reason", ""))
            reason = reason.strip()
            if ok and not reason:
                QMessageBox.warning(self, APP_NAME, "A reason is required to reject a candidate.")
            if not ok or not reason:
                QTimer.singleShot(0, self.refresh_approval)
                return
        self._apply_decision([cand], value, reason)
        # The combo that sent this signal is replaced during refresh, so rebuild after it returns
        QTimer.singleShot(0, self.refresh_approval)

    def on_approval_item_changed(self, item):
        self.update_selection_label()
        if item.column() != 7:
            return
        _vac, _res, short = self._shortlist()
        cand = next((c for c in short if c.get("id") == item.data(Qt.ItemDataRole.UserRole)), None)
        if cand is None:
            return
        text = item.text().strip()
        if text == cand.get("hr_reason", ""):
            return
        if not text and self._decision(cand) == "Rejected":
            QMessageBox.warning(self, APP_NAME, "A rejected candidate must keep a reason.")
            QTimer.singleShot(0, self.refresh_approval)
            return
        cand["hr_reason"] = text
        self._log(cand, "hr_log", f"Comment updated: {text or '(cleared)'}",
                  self.appr_name.text().strip() or "HR")
        save_vacancies(self.vacancies)

    @staticmethod
    def _log(cand, key, text, by):
        cand.setdefault(key, []).append({"at": datetime.now().isoformat(), "by": by, "text": text})

    def _apply_decision(self, cands, decision, reason=None):
        """Records an HR decision for the given candidates. reason=None keeps each existing comment."""
        _vac, res, _short = self._shortlist()
        name = self.appr_name.text().strip()
        if not name:
            QMessageBox.warning(self, APP_NAME, "Enter your name in the HR manager box first.")
            self.appr_name.setFocus()
            return False
        now = datetime.now().isoformat()
        for c in cands:
            c["hr_decision"] = decision
            c["hr_approved"] = decision == "Approved"
            if reason is not None:
                c["hr_reason"] = reason
            if decision == "Pending":
                c.pop("hr_decided_by", None)
                c.pop("hr_decided_at", None)
            else:
                c["hr_decided_by"] = name
                c["hr_decided_at"] = now
            self._log(c, "hr_log", f"HR decision: {decision}" + (f" - {reason}" if reason else ""), name)
        reopened = res.pop("hr_approval", None) is not None
        save_vacancies(self.vacancies)
        if reopened:
            QMessageBox.information(self, APP_NAME,
                                    "Decisions changed after sign-off, so the sign-off has been reopened. "
                                    "Click Complete Sign-off again when you are done.")
        return True

    def _checked_ids(self):
        ids = []
        for r in range(self.appr_table.rowCount()):
            item = self.appr_table.item(r, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) and item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def update_selection_label(self):
        n = len(self._checked_ids())
        self.appr_sel_label.setText(f"{n} selected" if n else "")

    def toggle_approval_row(self, row, col):
        item = self.appr_table.item(row, 0)
        if not item or not item.data(Qt.ItemDataRole.UserRole):
            return
        if col > 5:  # decision dropdown and comment cells have their own behaviour
            return
        if col != 0:  # a click on the checkbox itself already toggled it
            item.setCheckState(Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked
                               else Qt.CheckState.Checked)
        self.update_selection_label()

    def set_all_approval_checks(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for r in range(self.appr_table.rowCount()):
            item = self.appr_table.item(r, 0)
            if item and item.data(Qt.ItemDataRole.UserRole):
                item.setCheckState(state)
        self.update_selection_label()

    def decide_selected(self, decision):
        _vac, res, short = self._shortlist()
        ids = set(self._checked_ids())
        if not ids:
            QMessageBox.information(self, APP_NAME, "Tick one or more candidates in the Proposed Shortlist first.")
            return
        if not self.appr_name.text().strip():
            QMessageBox.warning(self, APP_NAME, "Enter your name in the HR manager box first.")
            self.appr_name.setFocus()
            return
        reason = None
        if decision == "Rejected":
            reason, ok = QInputDialog.getText(
                self, APP_NAME, f"Reason for rejecting {len(ids)} candidate(s) (recorded in the audit trail):")
            reason = reason.strip()
            if not ok:
                return
            if not reason:
                QMessageBox.warning(self, APP_NAME, "A reason is required to reject a candidate.")
                return
        if self._apply_decision([c for c in short if c.get("id") in ids], decision, reason):
            self.refresh_approval()

    def approve_shortlist(self):
        """Completes the HR sign-off once every shortlisted candidate is approved or rejected."""
        _vac, res, short = self._shortlist()
        if not res:
            QMessageBox.warning(self, APP_NAME, "Run a screening first.")
            return
        if not short:
            QMessageBox.warning(self, APP_NAME, "There are no shortlisted candidates to sign off.")
            return
        name = self.appr_name.text().strip()
        if not name:
            QMessageBox.warning(self, APP_NAME, "Enter your name in the HR manager box first.")
            self.appr_name.setFocus()
            return
        pending = [c for c in short if self._decision(c) == "Pending"]
        if pending:
            QMessageBox.warning(self, APP_NAME,
                                f"{len(pending)} candidate(s) are still Pending. Approve or reject every "
                                f"candidate before completing the sign-off.")
            return
        notes = self.appr_notes.toPlainText().strip()
        for c in short:
            c["hr_notes"] = notes
        approved = sum(1 for c in short if self._decision(c) == "Approved")
        res["hr_approval"] = {
            "approved_count": approved,
            "rejected_count": len(short) - approved,
            "approved_at": datetime.now().isoformat(),
            "approved_by": name,
            "notes": notes,
        }
        save_vacancies(self.vacancies)
        self.refresh_approval()
        QMessageBox.information(self, APP_NAME,
                                f"Sign-off completed: {approved} approved, {len(short) - approved} rejected.")

    def export_excel(self):
        vac = self.active_vacancy()
        res = (vac or {}).get("results")
        if not res:
            QMessageBox.warning(self, APP_NAME, "Run a screening first.")
            return
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment
        except ImportError:
            QMessageBox.critical(self, APP_NAME, "openpyxl is not installed. Run install_and_build.bat.")
            return
        default = f"Shortlist_{vac['title'].replace(' ', '_')}_{datetime.now():%Y%m%d}.xlsx"
        dest, _ = QFileDialog.getSaveFileName(self, "Save Excel report", default, "Excel workbook (*.xlsx)")
        if not dest:
            return

        wb = Workbook()
        header_fill = PatternFill("solid", fgColor="7B2FF7")
        header_font = Font(bold=True, color="FFFFFF")
        status_fills = {k: PatternFill("solid", fgColor=v.lstrip("#")) for k, v in STATUS_COLORS.items()}

        def write_sheet(ws, headers, rows, widths):
            ws.append(headers)
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            for row in rows:
                ws.append(row)
            for i, width in enumerate(widths, 1):
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width
            ws.freeze_panes = "A2"

        ws1 = wb.active
        ws1.title = "Approved Candidates"
        short = [c for c in res["ranked_candidates"] if c.get("shortlisted")]
        approved = [c for c in short if self._decision(c) == "Approved"]
        write_sheet(ws1,
                    ["Rank", "Candidate", "Email", "Phone", "Match %", "Qualifications", "Skills",
                     "Experience", "Mandatory", "Years Exp.", "Strengths", "Approved By", "Approved At", "HR Notes"],
                    [[c.get("rank"), c.get("name"), c.get("email"), c.get("phone"), c.get("matching_percentage"),
                      c["category_scores"].get("qualifications"), c["category_scores"].get("skills"),
                      c["category_scores"].get("experience"), c["category_scores"].get("mandatory"),
                      c.get("years_experience"), "\n".join(c.get("strengths", [])),
                      c.get("hr_decided_by", ""), self._fmt_date(c.get("hr_decided_at")), c.get("hr_notes", "")]
                     for c in approved],
                    [7, 24, 30, 20, 10, 14, 10, 12, 12, 10, 50, 20, 20, 40])
        if not approved:
            ws1.append(["", "No candidates approved yet - approve candidates on the HR Approval & Export page."])

        ws2 = wb.create_sheet("Full Audit Trail")
        write_sheet(ws2,
                    ["Rank", "Candidate", "File", "Match %", "Status", "HR Decision", "Reason / Comment",
                     "Decided By", "Decided At", "Mandatory Met", "Duplicate", "Unreadable",
                     "Missing Requirements", "Evidence", "Flags", "SHA-256"],
                    [[c.get("rank"), c.get("name"), c.get("filename"), c.get("matching_percentage"),
                      c.get("status"), self._decision(c) if c.get("shortlisted") else "-",
                      c.get("hr_reason", ""), c.get("hr_decided_by", ""),
                      self._fmt_date(c.get("hr_decided_at")) if c.get("hr_decided_at") else "",
                      "Yes" if c.get("mandatory_met") else "No",
                      "Yes" if c.get("is_duplicate") else "No", "Yes" if c.get("unreadable") else "No",
                      "\n".join(c.get("missing_requirements", [])), "\n".join(c.get("evidence", [])),
                      "\n".join(c.get("flags", [])), c.get("file_hash", "")] for c in res["ranked_candidates"]],
                    [7, 24, 40, 10, 32, 13, 36, 20, 20, 14, 11, 11, 50, 60, 40, 66])
        decision_fills = {"Approved": PatternFill("solid", fgColor="00B894"),
                          "Rejected": PatternFill("solid", fgColor="FF4D6D"),
                          "Pending": PatternFill("solid", fgColor="FF8A00")}
        for row in ws2.iter_rows(min_row=2):
            for idx, fills in ((4, status_fills), (5, decision_fills)):
                fill = fills.get(row[idx].value)
                if fill:
                    row[idx].fill = fill
                    row[idx].font = Font(bold=True, color="FFFFFF")
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)

        ws_pipe = wb.create_sheet("Interview Pipeline")
        pipe_rows = []
        for c in approved:
            p = pipeline_of(c)
            inv, l1, l2, fin, mg = p["invite"], p["l1"], p["l2"], p["final"], p["mgmt"]
            pipe_rows.append([
                c.get("rank"), c.get("name"), c.get("email"), pipeline_stage(p)[0],
                inv["status"], inv["date"], inv["mode"], inv["location"], inv["interviewer"],
                l1["date"], l1["interviewer"], l1["outcome"], l1["score"] or "", l1["feedback"],
                l2["date"], l2["interviewer"], l2["outcome"], l2["score"] or "", l2["feedback"],
                fin["decision"], fin["salary"], fin["joining"], fin["notes"],
                mg["status"], mg["approver"], mg["date"], mg["comments"]])
        write_sheet(ws_pipe,
                    ["Rank", "Candidate", "Email", "Current Stage",
                     "Invite Status", "Interview Date", "Format", "Location / Link", "Interviewer",
                     "L1 Date", "L1 Interviewer", "L1 Outcome", "L1 Score", "L1 Feedback",
                     "L2 Date", "L2 Interviewer", "L2 Outcome", "L2 Score", "L2 Feedback",
                     "Final Decision", "Salary", "Joining Date", "Final Notes",
                     "Mgmt Approval", "Approved By", "Approval Date", "Mgmt Comments"],
                    pipe_rows,
                    [7, 24, 28, 34, 13, 17, 11, 24, 18, 17, 18, 11, 9, 40, 17, 18, 11, 9, 40,
                     14, 18, 13, 36, 14, 20, 17, 36])
        for row in ws_pipe.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)

        ws3 = wb.create_sheet("Screening Summary")
        crit = vac.get("criteria", {})
        for row in [
            ["Application", APP_NAME],
            ["Vacancy", vac.get("title")],
            ["Department", vac.get("department")],
            ["Screened at", res.get("processed_at")],
            ["Threshold applied (%)", res.get("threshold_applied")],
            ["Top-N cap", res.get("top_n_cap")],
            ["Total evaluated", res.get("total_evaluated")],
            ["Qualifying / shortlisted", res.get("qualifying_count")],
            ["HR approved / rejected / pending",
             " / ".join(str(sum(1 for c in short if self._decision(c) == d))
                        for d in ("Approved", "Rejected", "Pending"))],
            ["Weights", json.dumps(crit.get("weights", {}))],
            ["HR approval", json.dumps(res.get("hr_approval") or "Pending")],
        ]:
            ws3.append(row)
        for cell in ws3["A"]:
            cell.font = Font(bold=True, color="7B2FF7")
        ws3.column_dimensions["A"].width = 26
        ws3.column_dimensions["B"].width = 80

        try:
            wb.save(dest)
        except OSError as e:
            QMessageBox.critical(self, APP_NAME, f"Could not save the workbook:\n{e}")
            return
        QMessageBox.information(self, APP_NAME, f"Excel report saved to:\n{dest}")

    def export_zip(self):
        vac = self.active_vacancy()
        res = (vac or {}).get("results")
        short = [c for c in (res or {}).get("ranked_candidates", []) if c.get("shortlisted")]
        approved = [c for c in short if self._decision(c) == "Approved"]
        if not approved:
            QMessageBox.warning(self, APP_NAME,
                                "No candidates are approved yet. Tick candidates and click Approve Selected first.")
            return
        default = f"Approved_CVs_{vac['title'].replace(' ', '_')}_{datetime.now():%Y%m%d}.zip"
        dest, _ = QFileDialog.getSaveFileName(self, "Save ZIP archive", default, "ZIP archive (*.zip)")
        if not dest:
            return
        appr = res.get("hr_approval")
        manifest = [
            f"{APP_NAME} - APPROVED SHORTLIST MANIFEST",
            f"Vacancy: {vac.get('title')} ({vac.get('department')})",
            f"Generated: {datetime.now():%Y-%m-%d %H:%M}",
            f"Threshold: >= {res.get('threshold_applied')}%   Cap: {res.get('top_n_cap')}",
            f"HR sign-off: {'Completed by ' + appr.get('approved_by', 'HR') + ' on ' + self._fmt_date(appr.get('approved_at')) if appr else 'NOT YET COMPLETED'}",
            "",
            "APPROVED:",
        ]
        missing = []
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            for c in approved:
                safe = "".join(ch if ch.isalnum() else "_" for ch in c.get("name", "Candidate"))
                src = c.get("savedPath", "")
                if src and os.path.exists(src):
                    ext = os.path.splitext(src)[1]
                    zf.write(src, f"Rank_{c.get('rank')}_{safe}{ext}")
                else:
                    missing.append(c.get("filename"))
                manifest.append(f"#{c.get('rank')}  {c.get('name')}  {c.get('matching_percentage')}%  "
                                f"{c.get('filename')}  sha256={c.get('file_hash', '')}")
            rejected = [c for c in short if self._decision(c) == "Rejected"]
            pending = [c for c in short if self._decision(c) == "Pending"]
            if rejected:
                manifest += ["", "REJECTED (CVs not included):"] + [
                    f"#{c.get('rank')}  {c.get('name')}  - {c.get('hr_reason', '')} (by {c.get('hr_decided_by', 'HR')})"
                    for c in rejected]
            if pending:
                manifest += ["", "PENDING (CVs not included):"] + [f"#{c.get('rank')}  {c.get('name')}" for c in pending]
            if missing:
                manifest += ["", "Original files no longer in storage:"] + missing
            zf.writestr("SHORTLIST_MANIFEST.txt", "\n".join(manifest))
        QMessageBox.information(self, APP_NAME, f"ZIP archive saved to:\n{dest}")

    # ================= Audit trail (print / PDF) ================= #

    def _audit_html(self, vac, res, short):
        e = lambda v: html.escape(str(v if v is not None else ""))
        crit = vac.get("criteria", {})
        appr = res.get("hr_approval")
        printed_by = self.appr_name.text().strip() or "-"

        def table(headers, rows, widths=None):
            head = "".join(f"<th bgcolor='#3a1c71' align='left'><font color='white'>{e(h)}</font></th>" for h in headers)
            body = []
            for i, row in enumerate(rows):
                bg = "#f3f0ff" if i % 2 else "#ffffff"
                body.append(f"<tr bgcolor='{bg}'>" + "".join(f"<td valign='top'>{cell}</td>" for cell in row) + "</tr>")
            if not rows:
                body.append(f"<tr><td colspan='{len(headers)}'><i>None</i></td></tr>")
            return ("<table border='1' cellspacing='0' cellpadding='4' width='100%' "
                    "style='border-collapse: collapse; border-color: #c9c3e6;'>"
                    f"<tr>{head}</tr>{''.join(body)}</table>")

        def colored(text, color):
            return f"<font color='{color}'><b>{e(text)}</b></font>"

        parts = [
            "<h2><font color='#7b2ff7'>ATS CV Filter - Recruitment Audit Trail</font></h2>",
            table(["Item", "Detail"], [
                ["Vacancy", e(f"{vac.get('title')} ({vac.get('department', '')})")],
                ["Printed", e(f"{datetime.now():%d %b %Y, %H:%M} by {printed_by}")],
                ["Screening run", e(self._fmt_date(res.get("processed_at")))],
                ["Rules", e(f"Match >= {res.get('threshold_applied')}%, all mandatory requirements, cap {res.get('top_n_cap')}")],
                ["Weights", e(", ".join(f"{k.title()} {v}%" for k, v in crit.get("weights", {}).items()))],
                ["CVs evaluated / shortlisted", e(f"{res.get('total_evaluated', 0)} / {res.get('qualifying_count', 0)}")],
                ["HR sign-off", e(f"Completed by {appr.get('approved_by')} on {self._fmt_date(appr.get('approved_at'))} - "
                                  f"{appr.get('approved_count', 0)} approved, {appr.get('rejected_count', 0)} rejected. "
                                  f"Notes: {appr.get('notes') or '-'}") if appr else colored("Not yet completed", "#ff8a00")],
            ]),
            "<h3><font color='#3a1c71'>1. HR shortlist decisions</font></h3>",
            table(["Rank", "Candidate", "Email", "Match %", "HR Decision", "Reason / Comment", "Decided by"], [
                [e(c.get("rank")), e(c.get("name")), e(c.get("email")), e(f"{c.get('matching_percentage', 0):.1f}%"),
                 colored(self._decision(c), DECISION_COLORS[self._decision(c)]), e(c.get("hr_reason", "")),
                 e(f"{c.get('hr_decided_by', '')} {self._fmt_date(c.get('hr_decided_at')) if c.get('hr_decided_at') else ''}")]
                for c in short]),
        ]

        approved = [c for c in short if self._decision(c) == "Approved"]
        rows = []
        for c in approved:
            p = pipeline_of(c)
            stage, color = pipeline_stage(p)
            inv, l1, l2, fin, mg = p["invite"], p["l1"], p["l2"], p["final"], p["mgmt"]
            interview = lambda s: e(f"{s['outcome']}" + (f", score {s['score']}/10" if s["score"] else "")
                                    + (f", {s['date']}" if s["date"] else "")
                                    + (f", by {s['interviewer']}" if s["interviewer"] else ""))
            rows.append([
                e(c.get("name")), colored(stage, color),
                e(f"{inv['status']}" + (f", {inv['date']}" if inv["date"] else "") + f", {inv['mode']}"),
                interview(l1), interview(l2),
                e(fin["decision"] + (f", salary {fin['salary']}" if fin["salary"] else "")
                  + (f", joining {fin['joining']}" if fin["joining"] else "")),
                e(mg["status"] + (f" by {mg['approver']}" if mg["approver"] else "")
                  + (f", {mg['date']}" if mg["date"] else "")),
            ])
        parts += ["<h3><font color='#3a1c71'>2. Interview pipeline (approved candidates)</font></h3>",
                  table(["Candidate", "Current stage", "Call for interview", "Level 1", "Level 2",
                         "Final decision", "Management approval"], rows)]

        events = []
        for c in short:
            for entry in c.get("hr_log", []) + c.get("pipeline", {}).get("log", []):
                events.append((entry.get("at", ""), entry.get("by", ""), c.get("name", ""), entry.get("text", "")))
        events.sort()
        parts += ["<h3><font color='#3a1c71'>3. Activity log</font></h3>",
                  table(["When", "By", "Candidate", "Action"],
                        [[e(self._fmt_date(a)), e(b), e(n), e(t)] for a, b, n, t in events])]

        parts += ["<h3><font color='#3a1c71'>4. Full screening results</font></h3>",
                  table(["Rank", "Candidate", "File", "Match %", "Screening status", "Flags"], [
                      [e(c.get("rank")), e(c.get("name")), e(c.get("filename")),
                       e(f"{c.get('matching_percentage', 0):.1f}%"),
                       colored(c.get("status", ""), STATUS_COLORS.get(c.get("status"), "#1f2041")),
                       e("; ".join(c.get("flags", [])))]
                      for c in res.get("ranked_candidates", [])]),
                  "<p><font color='#6b6f8e'>Generated by ATS CV Filter. Final hiring decisions remain with "
                  "the HR manager and management.</font></p>"]
        return "<html><body style='font-family: Segoe UI; font-size: 8pt;'>" + "".join(parts) + "</body></html>"

    def _audit_document(self):
        vac, res, short = self._shortlist()
        if not res:
            QMessageBox.warning(self, APP_NAME, "Run a screening for this vacancy first.")
            return None
        doc = QTextDocument()
        doc.setDefaultFont(QFont("Segoe UI", 8))
        doc.setHtml(self._audit_html(vac, res, short))
        return doc

    @staticmethod
    def _audit_printer(pdf_path=None):
        from PyQt6.QtPrintSupport import QPrinter
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        if pdf_path:
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(pdf_path)
        return printer

    def print_audit(self):
        doc = self._audit_document()
        if doc is None:
            return
        from PyQt6.QtPrintSupport import QPrintPreviewDialog
        dlg = QPrintPreviewDialog(self._audit_printer(), self)
        dlg.setWindowTitle("Audit Trail - Print Preview")
        dlg.paintRequested.connect(doc.print)
        dlg.resize(1150, 820)
        dlg.exec()

    def save_audit_pdf(self):
        vac = self.active_vacancy()
        doc = self._audit_document()
        if doc is None:
            return
        default = f"Audit_Trail_{vac['title'].replace(' ', '_')}_{datetime.now():%Y%m%d}.pdf"
        dest, _ = QFileDialog.getSaveFileName(self, "Save audit trail as PDF", default, "PDF document (*.pdf)")
        if not dest:
            return
        doc.print(self._audit_printer(dest))
        if not os.path.exists(dest):
            QMessageBox.critical(self, APP_NAME, "The PDF could not be written. Check the folder is not read-only.")
            return
        QMessageBox.information(self, APP_NAME, f"Audit trail saved to:\n{dest}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(dest))

    # ================= Interview Pipeline ================= #

    def _build_pipeline_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addLayout(page_header(
            "Interview Pipeline",
            "Track every HR-approved candidate through: Call for interview, Level 1 interview, Level 2 interview, "
            "Final decision and Management approval. Each stage unlocks when the previous one is passed."))

        chips = QHBoxLayout()
        self.pipe_chips = {}
        for key, label, color in [("call", "To call", "#6b6f8e"), ("interview", "Interviewing", "#2d8cff"),
                                  ("decision", "Awaiting decision", "#7b2ff7"), ("offer", "Offer / mgmt", "#f107a3"),
                                  ("hired", "Hired", "#00b894"), ("out", "Not selected", "#ff4d6d")]:
            chip = self._chip(color)
            chip.setProperty("label", label)
            self.pipe_chips[key] = chip
            chips.addWidget(chip)
        chips.addStretch()
        lay.addLayout(chips)

        user_card = make_card()
        ul = QHBoxLayout(user_card)
        ul.setContentsMargins(16, 10, 16, 10)
        ul.addWidget(section_title("Updated by:"))
        self.pipe_user = QLineEdit()
        self.pipe_user.setPlaceholderText("Your name - recorded in the activity log (required to save)")
        ul.addWidget(self.pipe_user, 1)
        lay.addWidget(user_card)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)

        left = make_card()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(14, 12, 14, 12)
        ll.addWidget(section_title("Approved Candidates"))
        self.pipe_table = QTableWidget(0, 4)
        self.pipe_table.setHorizontalHeaderLabels(["Rank", "Candidate", "Match %", "Current stage"])
        self._setup_table(self.pipe_table)
        self.pipe_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.pipe_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.pipe_table.setMinimumWidth(460)
        self.pipe_table.itemSelectionChanged.connect(self.on_pipeline_selected)
        ll.addWidget(self.pipe_table, 1)
        split.addWidget(left)

        right = make_card()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 12, 16, 12)
        rl.setSpacing(10)
        self.pipe_title = QLabel("Select a candidate")
        self.pipe_title.setObjectName("PageTitle")
        self.pipe_title.setStyleSheet("font-size: 18px;")
        self.pipe_stage = QLabel()
        rl.addWidget(self.pipe_title)
        rl.addWidget(self.pipe_stage)

        self.pipe_w = {}
        self.pipe_cards = {}

        # 1. Call for interview
        card, form = self._stage_card("1. Call for Interview", "#2d8cff", "invite")
        wi = self.pipe_w["invite"] = {
            "status": QComboBox(), "date": make_date_edit(), "mode": QComboBox(),
            "location": QLineEdit(), "interviewer": QLineEdit()}
        wi["status"].addItems(INVITE_STATUSES)
        wi["mode"].addItems(INTERVIEW_MODES)
        wi["location"].setPlaceholderText("Office address or video link")
        form.addRow("Status:", wi["status"])
        form.addRow("Date and time:", wi["date"])
        form.addRow("Format:", wi["mode"])
        form.addRow("Location / link:", wi["location"])
        form.addRow("Interviewer:", wi["interviewer"])
        inv_btns = QHBoxLayout()
        b_copy = make_button("\U0001F4CB  Copy Invitation Text")
        b_copy.clicked.connect(self.copy_invitation)
        b_mail = make_button("✉  Open Email Draft", "pink")
        b_mail.clicked.connect(self.email_invitation)
        inv_btns.addWidget(b_copy)
        inv_btns.addWidget(b_mail)
        inv_btns.addStretch()
        form.addRow("", inv_btns)
        rl.addWidget(card)

        # 2 & 3. Interviews
        for key, title, color in [("l1", "2. Interview Update (Level 1)", "#7b2ff7"),
                                  ("l2", "3. Level 2 Interview", "#f107a3")]:
            card, form = self._stage_card(title, color, key)
            ws = self.pipe_w[key] = {"date": make_date_edit(), "interviewer": QLineEdit(),
                                     "outcome": QComboBox(), "score": QSpinBox(), "feedback": QPlainTextEdit()}
            ws["outcome"].addItems(INTERVIEW_OUTCOMES)
            ws["score"].setRange(0, 10)
            ws["score"].setSpecialValueText("Not scored")
            ws["score"].setSuffix(" / 10")
            ws["feedback"].setFixedHeight(64)
            ws["feedback"].setPlaceholderText("Interview feedback")
            form.addRow("Date and time:", ws["date"])
            form.addRow("Interviewer(s):", ws["interviewer"])
            form.addRow("Outcome:", ws["outcome"])
            form.addRow("Score:", ws["score"])
            form.addRow("Feedback:", ws["feedback"])
            rl.addWidget(card)

        # 4. Final decision
        card, form = self._stage_card("4. Final Decision", "#ff8a00", "final")
        wf = self.pipe_w["final"] = {"decision": QComboBox(), "salary": QLineEdit(),
                                     "joining": make_date_edit(with_time=False), "notes": QPlainTextEdit()}
        wf["decision"].addItems(FINAL_DECISIONS)
        wf["salary"].setPlaceholderText("e.g. AED 35,000 per month")
        wf["notes"].setFixedHeight(56)
        form.addRow("Decision:", wf["decision"])
        form.addRow("Offered salary:", wf["salary"])
        form.addRow("Joining date:", wf["joining"])
        form.addRow("Notes:", wf["notes"])
        rl.addWidget(card)

        # 5. Management approval
        card, form = self._stage_card("5. Management Approval", "#00b894", "mgmt")
        wm = self.pipe_w["mgmt"] = {"status": QComboBox(), "approver": QLineEdit(),
                                    "date": make_date_edit(), "comments": QPlainTextEdit()}
        wm["status"].addItems(MGMT_STATUSES)
        wm["approver"].setPlaceholderText("Approving manager / director")
        wm["comments"].setFixedHeight(56)
        form.addRow("Status:", wm["status"])
        form.addRow("Approved by:", wm["approver"])
        form.addRow("Date:", wm["date"])
        form.addRow("Comments:", wm["comments"])
        rl.addWidget(card)

        for section in ("invite", "l1", "l2", "final"):
            key = {"invite": "status", "l1": "outcome", "l2": "outcome", "final": "decision"}[section]
            self.pipe_w[section][key].currentTextChanged.connect(self.update_pipeline_locks)

        save_row = QHBoxLayout()
        save_row.addStretch()
        self.pipe_save = make_button("\U0001F4BE  Save Candidate Progress", "success")
        self.pipe_save.setMinimumHeight(42)
        self.pipe_save.clicked.connect(self.save_pipeline)
        save_row.addWidget(self.pipe_save)
        rl.addLayout(save_row)

        rl.addWidget(section_title("Activity log"))
        self.pipe_log = QPlainTextEdit()
        self.pipe_log.setReadOnly(True)
        self.pipe_log.setFixedHeight(110)
        rl.addWidget(self.pipe_log)

        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        lay.addWidget(split, 1)

        bottom = QHBoxLayout()
        p = make_button("\U0001F5A8  Print Audit Trail", "warning")
        p.clicked.connect(self.print_audit)
        f = make_button("\U0001F4C4  Save Audit Trail (PDF)", "success")
        f.clicked.connect(self.save_audit_pdf)
        x = make_button("\U0001F4CA  Export Excel Report (.xlsx)")
        x.clicked.connect(self.export_excel)
        for b in (p, f, x):
            bottom.addWidget(b)
        bottom.addStretch()
        lay.addLayout(bottom)
        self.pipe_current_id = None
        self._set_pipeline_form_enabled(False)
        return w

    def _stage_card(self, title, color, key):
        card = QFrame()
        card.setObjectName("StageCard")
        card.setStyleSheet(f"#StageCard {{ background: #fafbff; border: 1.5px solid #e4e7fb;"
                           f" border-left: 6px solid {color}; border-radius: 12px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        t = QLabel(title)
        t.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {color}; background: transparent;")
        lay.addWidget(t)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addLayout(form)
        self.pipe_cards[key] = card
        return card, form

    def _approved_candidates(self):
        _vac, _res, short = self._shortlist()
        return [c for c in short if self._decision(c) == "Approved"]

    def refresh_pipeline(self):
        cands = self._approved_candidates()
        counts = dict.fromkeys(self.pipe_chips, 0)
        for c in cands:
            label, _ = pipeline_stage(pipeline_of(c))
            if label.startswith("Hired"):
                counts["hired"] += 1
            elif label.startswith(("Not selected", "Declined", "Offer rejected")):
                counts["out"] += 1
            elif label.startswith("Offer"):
                counts["offer"] += 1
            elif label.startswith(("Awaiting final", "Final decision")):
                counts["decision"] += 1
            elif label.startswith("To be called"):
                counts["call"] += 1
            else:
                counts["interview"] += 1
        for key, chip in self.pipe_chips.items():
            chip.setText(f"{chip.property('label')}: {counts[key]}")

        keep = self.pipe_current_id
        self.pipe_table.blockSignals(True)
        self.pipe_table.clearSpans()
        if not cands:
            self.pipe_table.setRowCount(1)
            self.pipe_table.setSpan(0, 0, 1, 4)
            item = QTableWidgetItem("No HR-approved candidates yet. Approve candidates on the HR Approval & Export page.")
            item.setForeground(QBrush(QColor(PALETTE["muted"])))
            self.pipe_table.setItem(0, 0, item)
            self.pipe_table.blockSignals(False)
            self.pipe_current_id = None
            self.pipe_title.setText("Select a candidate")
            self.pipe_stage.setText("")
            self.pipe_log.setPlainText("")
            self._set_pipeline_form_enabled(False)
            return
        self.pipe_table.setRowCount(len(cands))
        select_row = 0
        for r, c in enumerate(cands):
            label, color = pipeline_stage(pipeline_of(c))
            vals = [str(c.get("rank", "")), c.get("name", ""), f"{c.get('matching_percentage', 0):.1f}%", label]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, c.get("id"))
                if col == 3:
                    item.setForeground(QBrush(QColor(color)))
                    item.setFont(self._bold())
                self.pipe_table.setItem(r, col, item)
            if c.get("id") == keep:
                select_row = r
        self.pipe_table.blockSignals(False)
        self.pipe_table.selectRow(select_row)
        self.on_pipeline_selected()

    def _pipeline_candidate(self):
        return next((c for c in self._approved_candidates() if c.get("id") == self.pipe_current_id), None)

    def on_pipeline_selected(self):
        row = self.pipe_table.currentRow()
        item = self.pipe_table.item(row, 0) if row >= 0 else None
        cid = item.data(Qt.ItemDataRole.UserRole) if item else None
        cand = next((c for c in self._approved_candidates() if c.get("id") == cid), None)
        if cand is None:
            return
        self.pipe_current_id = cid
        p = pipeline_of(cand)
        for section, widgets in self.pipe_w.items():
            for key, wdg in widgets.items():
                value = p[section][key]
                wdg.blockSignals(True)
                if isinstance(wdg, QComboBox):
                    wdg.setCurrentText(value)
                elif isinstance(wdg, QDateTimeEdit):
                    set_date_edit(wdg, value)
                elif isinstance(wdg, QSpinBox):
                    wdg.setValue(int(value or 0))
                elif isinstance(wdg, QPlainTextEdit):
                    wdg.setPlainText(value)
                else:
                    wdg.setText(value)
                wdg.blockSignals(False)
        self.pipe_title.setText(f"#{cand.get('rank')}  {cand.get('name')}   ·   {cand.get('email')}")
        self._show_pipeline_stage(p)
        self.pipe_log.setPlainText("\n".join(
            f"{self._fmt_date(e.get('at'))}  |  {e.get('by')}  |  {e.get('text')}"
            for e in cand.get("hr_log", []) + p["log"]) or "No activity yet.")
        self._set_pipeline_form_enabled(True)
        self.update_pipeline_locks()

    def _show_pipeline_stage(self, p):
        label, color = pipeline_stage(p)
        self.pipe_stage.setText(f"Current stage: {label}")
        self.pipe_stage.setStyleSheet(f"color: white; background: {color}; border-radius: 10px;"
                                      f" padding: 6px 12px; font-weight: 700;")

    def _pipeline_form_values(self):
        values = {}
        for section, widgets in self.pipe_w.items():
            sec = values[section] = {}
            for key, wdg in widgets.items():
                if isinstance(wdg, QComboBox):
                    sec[key] = wdg.currentText()
                elif isinstance(wdg, QDateTimeEdit):
                    sec[key] = date_edit_value(wdg)
                elif isinstance(wdg, QSpinBox):
                    sec[key] = wdg.value()
                elif isinstance(wdg, QPlainTextEdit):
                    sec[key] = wdg.toPlainText().strip()
                else:
                    sec[key] = wdg.text().strip()
        return values

    def _set_pipeline_form_enabled(self, enabled):
        for card in self.pipe_cards.values():
            card.setEnabled(enabled)
        self.pipe_save.setEnabled(enabled)

    def update_pipeline_locks(self, *_):
        """Each stage unlocks only when the previous stage has been passed."""
        if self.pipe_current_id is None:
            return
        v = self._pipeline_form_values()
        unlocked = {
            "invite": True,
            "l1": v["invite"]["status"] in ("Invited", "Confirmed", "Rescheduled"),
            "l2": v["l1"]["outcome"] == "Pass",
            "final": v["l2"]["outcome"] == "Pass",
            "mgmt": v["final"]["decision"] == "Offer",
        }
        for key, card in self.pipe_cards.items():
            card.setEnabled(unlocked[key])
            card.setToolTip("" if unlocked[key] else "Complete the previous stage to unlock this one")

    def save_pipeline(self):
        cand = self._pipeline_candidate()
        if cand is None:
            return
        user = self.pipe_user.text().strip()
        if not user:
            QMessageBox.warning(self, APP_NAME, "Enter your name in the Updated by box first.")
            self.pipe_user.setFocus()
            return
        p = pipeline_of(cand)
        new = self._pipeline_form_values()
        changes = []
        for section, fields in new.items():
            for key, value in fields.items():
                old = p[section][key]
                if value != old:
                    shown = (value if key not in ("feedback", "notes", "comments")
                             else (value[:60] + ("..." if len(value) > 60 else "")))
                    changes.append(f"{PIPELINE_SECTION_NAMES[section]}: {key} -> {shown or '(cleared)'}")
                    p[section][key] = value
        if not changes:
            QMessageBox.information(self, APP_NAME, "No changes to save.")
            return
        now = datetime.now().isoformat()
        for text in changes:
            p["log"].append({"at": now, "by": user, "text": text})
        save_vacancies(self.vacancies)
        self.refresh_pipeline()
        label, _ = pipeline_stage(p)
        QMessageBox.information(self, APP_NAME, f"Saved {len(changes)} change(s).\nCurrent stage: {label}")

    def _invitation_text(self, cand):
        vac = self.active_vacancy()
        inv = self._pipeline_form_values()["invite"]
        when = "to be confirmed"
        if inv["date"]:
            when = QDateTime.fromString(inv["date"], "yyyy-MM-dd HH:mm").toString("dddd, d MMMM yyyy 'at' h:mm AP")
        sender = self.pipe_user.text().strip() or "HR Team"
        subject = f"Interview invitation - {vac.get('title')}"
        body = (f"Dear {cand.get('name')},\n\n"
                f"Thank you for applying for the position of {vac.get('title')} ({vac.get('department', '')}). "
                f"We are pleased to invite you to an interview.\n\n"
                f"Date and time: {when}\n"
                f"Format: {inv['mode']}\n"
                f"Location / link: {inv['location'] or 'to be confirmed'}\n"
                f"Interviewer: {inv['interviewer'] or 'HR team'}\n\n"
                f"Please reply to confirm your availability.\n\n"
                f"Kind regards,\n{sender}")
        return subject, body

    def copy_invitation(self):
        cand = self._pipeline_candidate()
        if cand is None:
            return
        subject, body = self._invitation_text(cand)
        QApplication.clipboard().setText(f"Subject: {subject}\n\n{body}")
        QMessageBox.information(self, APP_NAME, "Invitation copied. Paste it into your email or message.")

    def email_invitation(self):
        cand = self._pipeline_candidate()
        if cand is None:
            return
        email = cand.get("email", "")
        if "@" not in email:
            QMessageBox.warning(self, APP_NAME, "This candidate has no email address in their CV. "
                                                "Use Copy Invitation Text instead.")
            return
        subject, body = self._invitation_text(cand)
        url = (f"mailto:{email}?subject={urllib.parse.quote(subject)}"
               f"&body={urllib.parse.quote(body)}")
        if not QDesktopServices.openUrl(QUrl(url)):
            QMessageBox.warning(self, APP_NAME, "No email program is set up on this computer. "
                                                "Use Copy Invitation Text instead.")

    # ---------------- small utilities ---------------- #

    def _setup_table(self, table):
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    @staticmethod
    def _bold():
        f = QFont()
        f.setBold(True)
        return f

    @staticmethod
    def _pct_color(pct):
        if pct >= 90:
            return "#00b894"
        if pct >= 75:
            return "#2d8cff"
        if pct >= 50:
            return "#ff8a00"
        return "#ff4d6d"

    @staticmethod
    def _banner_style(a, b):
        return (f"color: white; font-size: 14px; font-weight: 700; padding: 14px 18px; border-radius: 14px;"
                f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {a}, stop:1 {b});")

    @staticmethod
    def _fmt_date(iso):
        if not iso:
            return "-"
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M")
        except ValueError:
            return iso

    @staticmethod
    def _fmt_size(n):
        for unit in ("B", "KB", "MB"):
            if n < 1024:
                return f"{n:.0f} {unit}"
            n /= 1024
        return f"{n:.1f} GB"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except AttributeError:
        pass  # Qt older than 6.8
    app.setPalette(light_palette())
    app.setStyleSheet(STYLESHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
