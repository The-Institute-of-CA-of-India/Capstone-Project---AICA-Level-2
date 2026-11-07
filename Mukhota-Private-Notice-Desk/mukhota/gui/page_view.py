"""Centre page preview: every page stacked in one scroll, colour-coded boxes, zoom, and Draw Box mode."""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsView

GAP = 24.0  # space between pages, in page-image pixels


class PageView(QGraphicsView):
    """Shows all pages of a document; pages are rendered when they scroll into view.

    ``boxDrawn`` gives the page index and the rectangle in that page's own image coordinates.
    ``pageChanged`` fires when another page becomes the one being read.
    """

    boxDrawn = pyqtSignal(int, QRectF)
    pageChanged = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("pageView")
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#E4E6F2"))
        self._pages: list[QRectF] = []
        self._loaded: set[int] = set()
        self._loader: Callable[[int], QImage] | None = None
        self._current = -1
        self._overlays: list = []
        self._draw_mode = False
        self._origin: QPointF | None = None
        self._draw_page = -1
        self._rubber: QGraphicsRectItem | None = None
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    # ------------------------------------------------------------------ content
    def set_document(self, sizes: list[tuple[float, float]], loader: Callable[[int], QImage]) -> None:
        """Lay out one white sheet per page; ``loader(i)`` renders page ``i`` when it is first seen."""
        self.clear_page()
        self._loader = loader
        width = max((w for w, _ in sizes), default=0)
        font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        y = 0.0
        for i, (w, h) in enumerate(sizes):
            rect = QRectF((width - w) / 2, y, w, h)
            sheet = self._scene.addRect(rect, QPen(QColor("#D5D8E6")), QBrush(QColor("white")))
            sheet.setZValue(-1)
            tag = self._scene.addSimpleText(f"{i + 1} / {len(sizes)}", font)
            tag.setBrush(QColor("#1E2563"))
            tag.setPos(rect.right() - tag.boundingRect().width() - 12, rect.top() + 8)
            tag.setZValue(3)
            self._pages.append(rect)
            y += h + GAP
        self._scene.setSceneRect(QRectF(0, 0, width, max(0.0, y - GAP)))
        QTimer.singleShot(0, self._on_scroll)

    def clear_page(self) -> None:
        self._scene.clear()
        self._pages, self._loaded, self._overlays = [], set(), []
        self._loader, self._rubber, self._current = None, None, -1

    def page_rect(self, index: int) -> QRectF:
        return self._pages[index]

    def scroll_to_page(self, index: int) -> None:
        """Bring the top of page ``index`` to the top of the view."""
        if not (0 <= index < len(self._pages)):
            return
        seen = self.mapToScene(self.viewport().rect()).boundingRect()
        rect = self._pages[index]
        self.centerOn(QPointF(seen.center().x(), rect.top() + seen.height() / 2 - GAP / 2))

    def set_overlays(self, boxes: list[tuple[QRectF, str, bool, bool, str]]) -> None:
        """Draw boxes in scene coordinates: (rect, hex colour, accepted, selected, tooltip)."""
        for item in self._overlays:
            self._scene.removeItem(item)
        self._overlays = []
        for rect, colour, accepted, selected, tip in boxes:
            # Ticked: soft fill with a solid underline. Unticked: dashed underline only.
            c = QColor(colour)
            fill = QColor(c)
            fill.setAlpha(55 if accepted else 0)
            outline = QPen(c, 2.5) if selected else QPen(Qt.PenStyle.NoPen)
            box = self._scene.addRect(rect, outline, QBrush(fill))
            box.setZValue(2 if selected else 1)
            box.setToolTip(tip)
            under = QPen(c, 3 if accepted else 2.5)
            if not accepted:
                under.setStyle(Qt.PenStyle.DashLine)
            line = self._scene.addLine(rect.left(), rect.bottom(), rect.right(), rect.bottom(), under)
            line.setZValue(2)
            self._overlays += [box, line]

    def _page_at(self, point: QPointF) -> int:
        return next((i for i, r in enumerate(self._pages) if r.contains(point)), -1)

    def _on_scroll(self, *_args) -> None:
        """Render pages near the view, and report which page is being read."""
        if not self._pages or self._loader is None:
            return
        seen = self.mapToScene(self.viewport().rect()).boundingRect()
        near = seen.adjusted(0, -seen.height(), 0, seen.height())
        for i, rect in enumerate(self._pages):
            if i not in self._loaded and rect.intersects(near):
                item = self._scene.addPixmap(QPixmap.fromImage(self._loader(i)))
                item.setPos(rect.topLeft())
                item.setZValue(0)
                self._loaded.add(i)
        mark = seen.top() + seen.height() / 3
        current = 0
        for i, rect in enumerate(self._pages):
            if rect.top() <= mark:
                current = i
        if current != self._current:
            self._current = current
            self.pageChanged.emit(current)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._on_scroll()

    # ------------------------------------------------------------------ zoom
    def zoom_in(self) -> None:
        self.scale(1.25, 1.25)
        self._on_scroll()

    def zoom_out(self) -> None:
        self.scale(0.8, 0.8)
        self._on_scroll()

    def fit_width(self) -> None:
        if not self._pages:
            return
        self.resetTransform()
        w = self.sceneRect().width()
        if w > 0:
            f = (self.viewport().width() - 24) / w
            self.scale(f, f)
        self._on_scroll()

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_in() if event.angleDelta().y() > 0 else self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    # ------------------------------------------------------------------ draw mode
    def set_draw_mode(self, on: bool) -> None:
        self._draw_mode = on
        self.setDragMode(QGraphicsView.DragMode.NoDrag if on else QGraphicsView.DragMode.ScrollHandDrag)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if on else Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._draw_mode and event.button() == Qt.MouseButton.LeftButton:
            point = self.mapToScene(event.position().toPoint())
            page = self._page_at(point)
            if page >= 0:
                self._origin, self._draw_page = point, page
                pen = QPen(QColor("#3949AB"), 2, Qt.PenStyle.DashLine)
                self._rubber = self._scene.addRect(QRectF(point, point), pen, QBrush(QColor(57, 73, 171, 50)))
                self._rubber.setZValue(5)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._rubber is not None and self._origin is not None:
            cur = self.mapToScene(event.position().toPoint())
            self._rubber.setRect(QRectF(self._origin, cur).normalized().intersected(self._pages[self._draw_page]))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._rubber is not None:
            page_rect = self._pages[self._draw_page]
            rect = self._rubber.rect().intersected(page_rect)
            self._scene.removeItem(self._rubber)
            self._rubber = None
            self._origin = None
            if rect.width() > 4 and rect.height() > 4:
                self.boxDrawn.emit(self._draw_page, rect.translated(-page_rect.topLeft()))
            event.accept()
            return
        super().mouseReleaseEvent(event)
