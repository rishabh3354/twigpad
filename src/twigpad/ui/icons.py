# SPDX-License-Identifier: GPL-3.0-or-later
"""Toolbar icons. Desktop theme icons are used when present; otherwise small
icons are drawn here so the app looks the same inside a snap or AppImage."""
from __future__ import annotations

import os

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QApplication, QStyle

from .. import APP_ID

SIZE = 32
RESOURCES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")


def app_icon() -> QIcon:
    """The application icon: the installed theme icon if any, else the bundled SVG."""
    return QIcon.fromTheme(APP_ID, QIcon(os.path.join(RESOURCES, f"{APP_ID}.svg")))


def _canvas():
    pm = QPixmap(SIZE, SIZE)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    return pm, p


def _ink() -> QColor:
    return QApplication.palette().windowText().color()


def _page(p: QPainter, rect: QRectF) -> None:
    p.setPen(QPen(_ink(), 2))
    p.setBrush(QApplication.palette().base())
    p.drawRoundedRect(rect, 2, 2)


def _plus(p: QPainter, cx: float, cy: float, r: float = 6) -> None:
    p.setPen(QPen(QColor("#2e8b3d"), 3.5, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
    p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))


def add_sibling() -> QIcon:
    pm, p = _canvas()
    _page(p, QRectF(3, 4, 18, 9))
    _page(p, QRectF(3, 19, 18, 9))
    _plus(p, 25, 23.5)
    p.end()
    return QIcon(pm)


def add_child() -> QIcon:
    pm, p = _canvas()
    _page(p, QRectF(2, 3, 18, 9))
    p.setPen(QPen(_ink(), 2))
    p.drawLine(QPointF(7, 12), QPointF(7, 23))
    p.drawLine(QPointF(7, 23), QPointF(11, 23))
    _page(p, QRectF(11, 18, 13, 10))
    _plus(p, 25, 9)
    p.end()
    return QIcon(pm)


def themed(name: str, fallback: QStyle.StandardPixmap) -> QIcon:
    return QIcon.fromTheme(name, QApplication.style().standardIcon(fallback))
