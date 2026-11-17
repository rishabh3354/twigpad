# SPDX-License-Identifier: GPL-3.0-or-later
"""Toolbar icons. Desktop theme icons are used when present; otherwise small
icons are drawn here so the app looks the same inside a snap or AppImage."""
from __future__ import annotations

import os

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QApplication, QStyle

from .. import APP_ID, DESKTOP_ID

SIZE = 32
RESOURCES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")


def other_app_icon(file_name: str) -> QIcon:
    """The icon of another app by the same developer (bundled in resources/apps)."""
    return QIcon(os.path.join(RESOURCES, "apps", file_name))


def app_icon() -> QIcon:
    """The application icon: the installed theme icon if any, else the bundled SVG."""
    return QIcon.fromTheme(DESKTOP_ID, QIcon(os.path.join(RESOURCES, f"{APP_ID}.svg")))


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


def _letter(text: str, bold: bool, italic: bool) -> QIcon:
    from PyQt5.QtGui import QFont
    pm, p = _canvas()
    font = QFont("Serif")
    font.setPixelSize(26)
    font.setBold(bold)
    font.setItalic(italic)
    p.setFont(font)
    p.setPen(_ink())
    p.drawText(QRectF(0, 0, SIZE, SIZE), Qt.AlignCenter, text)
    p.end()
    return QIcon(pm)


def bold() -> QIcon:
    return _letter("B", True, False)


def italic() -> QIcon:
    return _letter("I", False, True)


def cut() -> QIcon:
    pm, p = _canvas()
    p.setPen(QPen(_ink(), 2.2, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(9, 3), QPointF(21, 21))     # blades
    p.drawLine(QPointF(23, 3), QPointF(11, 21))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(9, 25), 4.5, 4.5)         # handles
    p.drawEllipse(QPointF(23, 25), 4.5, 4.5)
    p.end()
    return QIcon(pm)


def copy() -> QIcon:
    pm, p = _canvas()
    _page(p, QRectF(4, 3, 16, 20))
    _page(p, QRectF(12, 9, 16, 20))
    p.setPen(QPen(_ink(), 1.5))
    for y in (15, 19, 23):
        p.drawLine(QPointF(15, y), QPointF(25, y))
    p.end()
    return QIcon(pm)


def paste() -> QIcon:
    pm, p = _canvas()
    p.setPen(QPen(_ink(), 2))
    p.setBrush(QColor("#c9a46a"))
    p.drawRoundedRect(QRectF(5, 5, 22, 25), 2, 2)  # clipboard
    p.setBrush(QApplication.palette().base())
    p.drawRoundedRect(QRectF(11, 2, 10, 6), 2, 2)  # clip
    _page(p, QRectF(9, 11, 14, 15))
    p.end()
    return QIcon(pm)


def themed_drawn(name: str, drawn) -> QIcon:
    """The desktop theme's icon, or one drawn here."""
    return QIcon.fromTheme(name) if QIcon.hasThemeIcon(name) else drawn()


# ---------------------------------------------------------------- tree-notes buttons
# Drawn in the classic style: yellow folders with a red marker for where the
# new node goes, yellow move arrows, and small two-pane window pictures.

RED = QColor("#d8402b")


def _folder(p: QPainter, x: float, y: float, size: int = 18) -> None:
    from .treestyle import _paint_folder
    p.drawPixmap(int(x), int(y), _paint_folder(size))


def _marker(p: QPainter, rect: QRectF) -> None:
    p.setPen(QPen(RED.darker(130), 1))
    p.setBrush(RED)
    p.drawRect(rect)


def node_child() -> QIcon:
    pm, p = _canvas()
    _folder(p, 1, 1)
    p.setPen(QPen(_ink(), 1.5, Qt.DotLine))
    p.drawLine(QPointF(8, 18), QPointF(8, 25))
    p.drawLine(QPointF(8, 25), QPointF(15, 25))
    _marker(p, QRectF(16, 20, 13, 9))
    p.end()
    return QIcon(pm)


def node_before() -> QIcon:
    pm, p = _canvas()
    _marker(p, QRectF(3, 2, 22, 7))
    _folder(p, 3, 12)
    p.end()
    return QIcon(pm)


def node_after() -> QIcon:
    pm, p = _canvas()
    _folder(p, 3, 1)
    _marker(p, QRectF(3, 22, 22, 7))
    p.end()
    return QIcon(pm)


def node_delete() -> QIcon:
    pm, p = _canvas()
    _folder(p, 1, 3, 22)
    p.setPen(QPen(RED, 3.2, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(17, 17), QPointF(28, 28))
    p.drawLine(QPointF(28, 17), QPointF(17, 28))
    p.end()
    return QIcon(pm)


def node_rename() -> QIcon:
    from PyQt5.QtGui import QFont
    pm, p = _canvas()
    font = QFont("Sans")
    font.setPixelSize(13)
    font.setBold(True)
    p.setFont(font)
    p.setPen(_ink())
    p.drawText(QRectF(0, 4, SIZE, 16), Qt.AlignCenter, "abc")
    p.setPen(QPen(RED, 2))
    p.drawLine(QPointF(4, 24), QPointF(28, 24))   # the title being edited
    p.drawLine(QPointF(25, 20), QPointF(25, 28))  # text cursor
    p.end()
    return QIcon(pm)


def _window(tree: bool, article: bool) -> QIcon:
    pm, p = _canvas()
    frame = QRectF(3, 4, 26, 24)
    p.setPen(QPen(_ink(), 1.6))
    p.setBrush(QApplication.palette().base())
    p.drawRect(frame)
    p.setBrush(QColor("#2f6fd6"))
    p.drawRect(QRectF(3, 4, 26, 4))            # title bar
    split = 13 if tree and article else (29 if tree else 3)
    if tree and article:
        p.drawLine(QPointF(split, 8), QPointF(split, 28))
    line = QPen(_ink(), 1.3)
    p.setPen(line)
    if tree:
        right = split - 2 if article else 26
        for i, y in enumerate((12, 16, 20, 24)):
            x = 6 + (3 if i in (1, 2) else 0)
            p.drawLine(QPointF(x, y), QPointF(min(right, x + (6 if article else 12)), y))
    if article:
        left = split + 3 if tree else 6
        for y in (12, 15, 18, 21, 24):
            p.drawLine(QPointF(left, y), QPointF(26, y))
    p.end()
    return QIcon(pm)


def view_both() -> QIcon:
    return _window(True, True)


def view_tree() -> QIcon:
    return _window(True, False)


def view_article() -> QIcon:
    return _window(False, True)


def _arrow(direction: str, color: str = "#f2c418") -> QIcon:
    from PyQt5.QtGui import QPainterPath, QTransform
    pm, p = _canvas()
    path = QPainterPath()   # pointing up, on a 32 x 32 grid
    for i, (x, y) in enumerate(((16, 3), (28, 15), (21, 15), (21, 29), (11, 29), (11, 15), (4, 15))):
        path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
    path.closeSubpath()
    angle = {"up": 0, "right": 90, "down": 180, "left": 270}[direction]
    path = QTransform().translate(16, 16).rotate(angle).translate(-16, -16).map(path)
    p.setPen(QPen(QColor(color).darker(170), 1.4))
    p.setBrush(QColor(color))
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def move_up() -> QIcon:
    return _arrow("up")


def move_down() -> QIcon:
    return _arrow("down")


def move_left() -> QIcon:
    return _arrow("left")


def move_right() -> QIcon:
    return _arrow("right")


def _double(outward: bool) -> QIcon:
    from PyQt5.QtGui import QPainterPath
    pm, p = _canvas()
    color = QColor("#1fb5c9")
    p.setPen(QPen(color.darker(160), 1.3))
    p.setBrush(color)
    for top in (True, False):
        path = QPainterPath()
        if outward:   # arrow heads point away from the middle
            tip, base = (2, 13) if top else (30, 19)
        else:         # arrow heads meet in the middle
            tip, base = (14, 3) if top else (18, 29)
        path.moveTo(16, tip)
        path.lineTo(28, base)
        path.lineTo(4, base)
        path.closeSubpath()
        p.drawPath(path)
    p.end()
    return QIcon(pm)


def expand_branch() -> QIcon:
    return _double(True)


def collapse_branch() -> QIcon:
    return _double(False)


def wrench() -> QIcon:
    pm, p = _canvas()
    p.setPen(QPen(QColor("#555b63"), 5, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(9, 23), QPointF(20, 12))           # handle
    p.setPen(QPen(QColor("#555b63"), 2.5))
    p.setBrush(QColor("#8c939c"))
    p.drawEllipse(QPointF(22, 10), 6.5, 6.5)              # head
    p.setPen(Qt.NoPen)
    p.setBrush(Qt.transparent)
    p.setCompositionMode(QPainter.CompositionMode_Clear)
    p.drawRect(QRectF(22, 2, 5, 7))                        # jaw opening
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.setPen(QPen(QColor("#b5651d"), 6, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(5, 27), QPointF(10, 22))           # grip
    p.end()
    return QIcon(pm)


def globe() -> QIcon:
    pm, p = _canvas()
    p.setPen(QPen(QColor("#1d5fa8"), 1.5))
    p.setBrush(QColor("#3c8fe0"))
    p.drawEllipse(QPointF(16, 16), 13, 13)
    p.setBrush(QColor("#3fae49"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(11, 12), 6, 5)                  # land
    p.drawEllipse(QPointF(20, 21), 5, 6)
    p.setPen(QPen(QColor(255, 255, 255, 150), 1))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(16, 16), 6, 13)                 # meridian
    p.drawLine(QPointF(3, 16), QPointF(29, 16))           # equator
    p.end()
    return QIcon(pm)


def cross() -> QIcon:
    """Delete (text): a plain X in the text colour."""
    pm, p = _canvas()
    p.setPen(QPen(_ink(), 3.4, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(8, 8), QPointF(24, 24))
    p.drawLine(QPointF(24, 8), QPointF(8, 24))
    p.end()
    return QIcon(pm)
