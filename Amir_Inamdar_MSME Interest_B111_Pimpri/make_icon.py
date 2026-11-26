#!/usr/bin/env python3
"""Create msme.ico (multi-size Windows icon) using PyQt5 only - no extra packages.

Usage:  python make_icon.py
"""
import sys

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter
from PyQt5.QtWidgets import QApplication


def draw(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#1F4E78"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.18, size * 0.18)
    p.setPen(QColor("white"))
    font = QFont("Segoe UI", max(6, int(size * 0.55)))
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRectF(0, -size * 0.04, size, size), Qt.AlignCenter, "₹")
    p.end()
    return img


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Qt's ICO writer stores one image per file; 256 px scales well on Windows.
    ok = draw(256).save("msme.ico", "ICO")
    print("msme.ico created" if ok else "Could not write msme.ico (build without --icon)")
