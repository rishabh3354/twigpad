# SPDX-License-Identifier: GPL-3.0-or-later
"""The classic tree look: folder icons, dotted connector lines, +/- boxes,
and a selection highlight drawn only behind the node title."""
from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QRect, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PyQt5.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

ICON = 16          # folder icon size (logical pixels)
GAP = 3            # space between connector line, icon and text
TEXT_PAD = 3       # horizontal padding inside the title highlight
INDENT = 19        # width of one tree level
LINE_COLOR = QColor("#9a9a9a")
BOX_BORDER = QColor("#8a8a8a")
BOX_SIGN = QColor("#202020")

_folder: Optional[QIcon] = None


def _paint_folder(size: int) -> QPixmap:
    s = size / 16.0
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(s, s)
    outline = QPen(QColor("#a87a12"), 1)
    outline.setCosmetic(True)  # one device pixel at any size

    # back panel with the tab
    back = QPainterPath()
    back.moveTo(1.5, 3.5)
    back.lineTo(6.0, 3.5)
    back.lineTo(7.5, 5.0)
    back.lineTo(14.5, 5.0)
    back.lineTo(14.5, 13.5)
    back.lineTo(1.5, 13.5)
    back.closeSubpath()
    p.setPen(outline)
    p.setBrush(QColor("#e9b93c"))
    p.drawPath(back)

    # front flap, slightly lighter, with a soft gradient
    front = QPainterPath()
    front.moveTo(1.5, 13.5)
    front.lineTo(2.8, 7.0)
    front.lineTo(15.5, 7.0)
    front.lineTo(14.5, 13.5)
    front.closeSubpath()
    grad = QLinearGradient(0, 7, 0, 13.5)
    grad.setColorAt(0.0, QColor("#fff0a8"))
    grad.setColorAt(1.0, QColor("#f6cf55"))
    p.setBrush(grad)
    p.drawPath(front)
    p.end()
    return pm


def folder_icon() -> QIcon:
    global _folder
    if _folder is None:
        _folder = QIcon()
        for size in (16, 24, 32, 48):
            _folder.addPixmap(_paint_folder(size))
    return _folder


# ---------------------------------------------------------------- branches

def draw_branches(tree, painter: QPainter, rect: QRect, index) -> None:
    """Dotted connector lines and +/- boxes in the indentation area of a row."""
    item = tree.itemFromIndex(index)
    if item is None:
        return
    indent = tree.indentation()
    cy = rect.top() + rect.height() // 2
    pen = QPen(LINE_COLOR, 1)
    pen.setCosmetic(True)
    pen.setDashPattern([1, 1])
    painter.save()
    # Qt paints the row's selection colour under the branch area; the classic
    # look keeps the highlight on the title only, so clear it first.
    painter.fillRect(rect, tree.palette().color(QPalette.Base))
    painter.setRenderHint(QPainter.Antialiasing, False)
    painter.setPen(pen)

    # Chain of ancestors from the top down, to know which levels continue.
    chain = []
    it = item
    while it is not None:
        chain.append(it)
        it = it.parent()
    chain.reverse()
    depth = len(chain) - 1
    right = rect.right() + 1
    left = right - (depth + 1) * indent

    def has_next(node) -> bool:
        parent = node.parent() or tree.invisibleRootItem()
        return parent.indexOfChild(node) < parent.childCount() - 1

    def has_prev(node) -> bool:
        parent = node.parent() or tree.invisibleRootItem()
        return parent.indexOfChild(node) > 0

    # Vertical lines for ancestors that have more siblings below.
    for level, ancestor in enumerate(chain[:-1]):
        if has_next(ancestor):
            cx = left + level * indent + indent // 2
            painter.drawLine(cx, rect.top(), cx, rect.bottom())

    # This row: elbow from the line above, and on down if siblings follow.
    cx = left + depth * indent + indent // 2
    top = rect.top() if (item.parent() is not None or has_prev(item)) else cy
    bottom = rect.bottom() if has_next(item) else cy
    painter.drawLine(cx, top, cx, bottom)
    painter.drawLine(cx, cy, left + (depth + 1) * indent - 1, cy)

    # +/- box for nodes with children.
    if item.childCount() > 0:
        box = QRect(cx - 4, cy - 4, 8, 8)
        painter.setPen(QPen(BOX_BORDER, 1))
        painter.setBrush(tree.palette().color(QPalette.Base))
        painter.drawRect(box)
        painter.setPen(QPen(BOX_SIGN, 1))
        painter.drawLine(cx - 2, cy, cx + 2, cy)
        if not item.isExpanded():
            painter.drawLine(cx, cy - 2, cx, cy + 2)
    painter.restore()


# ---------------------------------------------------------------- delegate

class TreeDelegate(QStyledItemDelegate):
    """Draws rows in the classic style when ``tree.classic`` is on;
    otherwise behaves like the standard delegate."""

    def __init__(self, tree):
        super().__init__(tree)
        self.tree = tree

    def _text_rect(self, option, text: str) -> QRect:
        r = option.rect
        fm = option.fontMetrics
        x = r.left() + 1 + ICON + GAP
        w = fm.horizontalAdvance(text) + 2 * TEXT_PAD
        h = fm.height() + 2
        return QRect(x, r.top() + (r.height() - h) // 2, w, h)

    def sizeHint(self, option, index) -> QSize:
        if not self.tree.classic:
            return super().sizeHint(option, index)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        fm = opt.fontMetrics
        return QSize(1 + ICON + GAP + fm.horizontalAdvance(opt.text) + 2 * TEXT_PAD + 4,
                     max(ICON + 2, fm.height() + 4))

    def paint(self, painter: QPainter, option, index) -> None:
        if not self.tree.classic:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        r = opt.rect
        painter.save()
        icon_rect = QRect(r.left() + 1, r.top() + (r.height() - ICON) // 2, ICON, ICON)
        folder_icon().paint(painter, icon_rect)

        text_rect = self._text_rect(opt, opt.text)
        selected = bool(opt.state & QStyle.State_Selected)
        group = QPalette.Active if opt.state & QStyle.State_Active else QPalette.Inactive
        pal = opt.palette
        if selected:
            painter.fillRect(text_rect, pal.color(group, QPalette.Highlight))
            painter.setPen(pal.color(group, QPalette.HighlightedText))
        else:
            painter.setPen(pal.color(group, QPalette.Text))
        painter.setFont(opt.font)
        painter.drawText(text_rect.adjusted(TEXT_PAD, 0, -TEXT_PAD, 0),
                         Qt.AlignVCenter | Qt.AlignLeft | Qt.TextSingleLine, opt.text)
        if selected and opt.state & QStyle.State_HasFocus:
            focus = QPen(pal.color(group, QPalette.HighlightedText), 1, Qt.DotLine)
            painter.setPen(focus)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(text_rect.adjusted(0, 0, -1, -1))
        painter.restore()

    def updateEditorGeometry(self, editor, option, index) -> None:
        if not self.tree.classic:
            super().updateEditorGeometry(editor, option, index)
            return
        r = option.rect
        x = r.left() + 1 + ICON + GAP
        editor.setGeometry(QRect(x, r.top(), max(80, r.right() - x), r.height()))

