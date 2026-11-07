"""Right panel: candidate list with tick boxes, filter chips and Select all / Clear all."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.models import Candidate, colour_for, mask_value

_CID = Qt.ItemDataRole.UserRole


class CandidatePanel(QFrame):
    """Shows candidates; edits ``Candidate.accepted`` in place and emits ``changed``."""

    changed = pyqtSignal()
    activated = pyqtSignal(str)  # cid

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._cands: dict[str, Candidate] = {}
        self._active_types: set[str] = set()
        self._chips: dict[str, QPushButton] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)
        title = QLabel("Detected items")
        title.setObjectName("cardTitle")
        self.summary = QLabel("Open a PDF and click Detect PII.")
        self.summary.setObjectName("muted")
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(title)
        lay.addWidget(self.summary)

        self._chip_host = QWidget()
        self._chip_grid = QGridLayout(self._chip_host)
        self._chip_grid.setContentsMargins(0, 0, 0, 0)
        self._chip_grid.setSpacing(6)
        lay.addWidget(self._chip_host)

        row = QHBoxLayout()
        self.btn_all = QPushButton("Select all")
        self.btn_none = QPushButton("Clear all")
        for b in (self.btn_all, self.btn_none):
            b.setObjectName("smallButton")
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.btn_all.clicked.connect(lambda: self._set_visible_checked(True))
        self.btn_none.clicked.connect(lambda: self._set_visible_checked(False))

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["", "Type", "Value", "Page", "Conf."])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.currentCellChanged.connect(self._on_current_changed)
        lay.addWidget(self.table, 1)

    # ------------------------------------------------------------------ public
    def set_candidates(self, cands: list[Candidate]) -> None:
        """Rebuild the table and chips for the given candidates."""
        self._cands = {c.cid: c for c in cands}
        types = sorted({c.pii_type for c in cands})
        self._active_types = set(types)
        self._rebuild_chips(types)
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for c in sorted(cands, key=lambda c: (c.page, c.pii_type)):
            r = self.table.rowCount()
            self.table.insertRow(r)
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            chk.setCheckState(Qt.CheckState.Checked if c.accepted else Qt.CheckState.Unchecked)
            chk.setData(_CID, c.cid)
            typ = QTableWidgetItem(f"● {c.pii_type}")
            typ.setForeground(QColor(colour_for(c.pii_type)))
            val = QTableWidgetItem(mask_value(c.text, c.pii_type))
            val.setToolTip(f"Rule: {c.rule_id}" + (f" | Role: {c.role}" if c.role else ""))
            page = QTableWidgetItem(str(c.page + 1))
            page.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            conf = QTableWidgetItem(f"{c.confidence:.0%}")
            conf.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            for col, item in enumerate((chk, typ, val, page, conf)):
                if col:
                    item.setData(_CID, c.cid)
                self.table.setItem(r, col, item)
        self.table.blockSignals(False)
        self._apply_filter()
        self._update_summary()

    # ------------------------------------------------------------------ internals
    def _rebuild_chips(self, types: list[str]) -> None:
        while self._chip_grid.count():
            w = self._chip_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._chips = {}
        for i, t in enumerate(types):
            b = QPushButton(t)
            b.setCheckable(True)
            b.setChecked(True)
            b.setObjectName("chip")
            col = colour_for(t)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton#chip {{ background: white; border: 2px solid {col}; color: {col}; }}"
                f"QPushButton#chip:checked {{ background: {col}; color: white; }}"
            )
            b.toggled.connect(lambda on, t=t: self._toggle_type(t, on))
            self._chip_grid.addWidget(b, i // 4, i % 4)
            self._chips[t] = b

    def _toggle_type(self, t: str, on: bool) -> None:
        if on:
            self._active_types.add(t)
        else:
            self._active_types.discard(t)
        self._apply_filter()

    def _apply_filter(self) -> None:
        for r in range(self.table.rowCount()):
            cid = self.table.item(r, 0).data(_CID)
            c = self._cands.get(cid)
            self.table.setRowHidden(r, c is None or c.pii_type not in self._active_types)

    def _set_visible_checked(self, on: bool) -> None:
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            if self.table.isRowHidden(r):
                continue
            item = self.table.item(r, 0)
            item.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
            c = self._cands.get(item.data(_CID))
            if c:
                c.accepted = on
        self.table.blockSignals(False)
        self._update_summary()
        self.changed.emit()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        c = self._cands.get(item.data(_CID))
        if c:
            c.accepted = item.checkState() == Qt.CheckState.Checked
            self._update_summary()
            self.changed.emit()

    def _on_current_changed(self, row: int, _col: int, _prow: int, _pcol: int) -> None:
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item:
            self.activated.emit(item.data(_CID))

    def _update_summary(self) -> None:
        total = len(self._cands)
        acc = sum(1 for c in self._cands.values() if c.accepted)
        if total:
            self.summary.setText(
                f"<span style='font-size:20pt; font-weight:800; color:#2E3A8C'>{acc}</span>"
                f"&nbsp;&nbsp;of {total} items will be redacted"
            )
        else:
            self.summary.setText("Click <b>Detect PII</b> to scan this notice.")
