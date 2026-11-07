"""Case register window and due-date notifications."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..core import register

_ROW = Qt.ItemDataRole.UserRole


def _due_text(case: register.Case) -> tuple[str, QColor | None]:
    left = case.days_left
    if left is None:
        return "-", None
    if case.status == "Filed":
        return f"{left} days" if left >= 0 else "-", None
    if left < 0:
        return f"Overdue by {-left} day(s)", QColor("#B71C1C")
    if left <= 7:
        return f"{left} day(s) left", QColor("#8A5A00")
    return f"{left} days", None


class CaseEditDialog(QDialog):
    """Edit one case: client, due date, status."""

    def __init__(self, case: register.Case, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mukhota - Edit case")
        f = QFormLayout(self)
        self.txt_client = QLineEdit(case.client)
        self.dt_due = QDateEdit()
        self.dt_due.setCalendarPopup(True)
        self.dt_due.setDisplayFormat("dd/MM/yyyy")
        d = date.fromisoformat(case.due_date) if case.due_date else date.today()
        self.dt_due.setDate(QDate(d.year, d.month, d.day))
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(register.STATUSES)
        self.cmb_status.setCurrentText(case.status)
        f.addRow("Notice", QLabel(case.file_name))
        f.addRow("Client", self.txt_client)
        f.addRow("Reply due date", self.dt_due)
        f.addRow("Status", self.cmb_status)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        f.addRow(b)

    def due_iso(self) -> str:
        return self.dt_due.date().toString("yyyy-MM-dd")


class RegisterDialog(QDialog):
    """All notices with due dates and progress. Client names are stored encrypted."""

    COLS = ["Client", "Notice", "Section", "AY", "Notice date", "Due date", "Due", "Status"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mukhota - Case register")
        self.resize(1100, 600)
        self.tbl = QTableWidget(0, len(self.COLS))
        self.tbl.setHorizontalHeaderLabels(self.COLS)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl.setSortingEnabled(True)
        self.tbl.doubleClicked.connect(self.edit)
        self.summary = QLabel()
        self.summary.setObjectName("muted")

        b_edit = QPushButton("Edit")
        b_filed = QPushButton("Mark filed")
        b_folder = QPushButton("Open folder")
        b_delete = QPushButton("Remove")
        b_close = QPushButton("Close")
        for b in (b_edit, b_folder, b_delete, b_close):
            b.setObjectName("smallButton")
        b_edit.clicked.connect(self.edit)
        b_filed.clicked.connect(self.mark_filed)
        b_folder.clicked.connect(self.open_folder)
        b_delete.clicked.connect(self.remove)
        b_close.clicked.connect(self.accept)
        row = QHBoxLayout()
        for b in (b_edit, b_filed, b_folder, b_delete):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(b_close)

        lay = QVBoxLayout(self)
        lay.addWidget(self.summary)
        lay.addWidget(self.tbl, 1)
        lay.addLayout(row)
        self.reload()

    def reload(self) -> None:
        self.cases = {c.id: c for c in register.all_cases()}
        self.tbl.setSortingEnabled(False)
        self.tbl.setRowCount(0)
        for c in self.cases.values():
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            due_txt, colour = _due_text(c)
            values = [c.client or "(not yet known)", c.file_name, c.section, c.ay,
                      _dmy(c.notice_date), _dmy(c.due_date), due_txt, c.status]
            for col, v in enumerate(values):
                it = QTableWidgetItem(v)
                it.setData(_ROW, c.id)
                if col == 5:
                    it.setData(Qt.ItemDataRole.UserRole + 1, c.due_date)
                if colour is not None and col in (5, 6):
                    it.setForeground(colour)
                self.tbl.setItem(r, col, it)
        self.tbl.setSortingEnabled(True)
        soon = register.due_soon()
        self.summary.setText(
            f"{len(self.cases)} notice(s). {len(soon)} not filed and due within 7 days or overdue."
            " Double-click a row to edit the client, due date or status."
        )

    def _selected(self) -> register.Case | None:
        rows = self.tbl.selectionModel().selectedRows()
        if not rows:
            return None
        return self.cases.get(self.tbl.item(rows[0].row(), 0).data(_ROW))

    def edit(self) -> None:
        c = self._selected()
        if c is None:
            return
        dlg = CaseEditDialog(c, self)
        if dlg.exec():
            register.update(c.id, due_date=dlg.due_iso(), status=dlg.cmb_status.currentText(),
                            client=dlg.txt_client.text().strip())
            self.reload()

    def mark_filed(self) -> None:
        c = self._selected()
        if c:
            register.update(c.id, status="Filed")
            self.reload()

    def open_folder(self) -> None:
        c = self._selected()
        if c and c.folder and Path(c.folder).exists():
            os.startfile(c.folder)  # noqa: S606

    def remove(self) -> None:
        c = self._selected()
        if c and QMessageBox.question(self, "Remove", "Remove this notice from the register? Files are not deleted.") \
                == QMessageBox.StandardButton.Yes:
            register.delete(c.id)
            self.reload()


def _dmy(iso: str) -> str:
    if not iso:
        return ""
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def notify_due(tray: QSystemTrayIcon) -> int:
    """Windows notification for notices due within 7 days or overdue; returns how many."""
    soon = register.due_soon()
    if not soon or not QSystemTrayIcon.isSystemTrayAvailable():
        return len(soon)
    overdue = sum(1 for c in soon if (c.days_left or 0) < 0)
    lines = [f"{c.client or c.file_name}: s.{c.section or '?'} AY {c.ay or '?'} - due {_dmy(c.due_date)}" for c in soon[:4]]
    title = f"Mukhota: {len(soon)} repl{'y' if len(soon) == 1 else 'ies'} due soon" + (f" ({overdue} overdue)" if overdue else "")
    tray.show()
    tray.showMessage(title, "\n".join(lines), QSystemTrayIcon.MessageIcon.Warning, 15000)
    return len(soon)
