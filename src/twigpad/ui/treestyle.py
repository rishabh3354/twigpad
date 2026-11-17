# SPDX-License-Identifier: GPL-3.0-or-later
"""The classic tree look: folder icons, dotted connector lines, +/- boxes,
and a selection highlight drawn only behind the node title."""
from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PyQt5.QtWidgets import QLineEdit, QStyle, QStyledItemDelegate, QStyleOptionViewItem

ICON = 16          # folder icon size (logical pixels)
GAP = 3            # space between connector line, icon and text
TEXT_PAD = 3       # horizontal padding inside the title highlight
INDENT = 19        # width of one tree level

_folder: Optional[QIcon] = None
FOLDER_COLOR = "#f7bd46"

# Note icons: name -> (menu label, default colour).
NOTE_ICONS = {
    "": ("Folder", FOLDER_COLOR),
    "page": ("Page", "#5b6b7f"),
    "star": ("Star", "#f2b01e"),
    "flag": ("Flag", "#d83b2d"),
    "check": ("Done", "#2e9a4b"),
    "warning": ("Important", "#f0a30a"),
    "info": ("Information", "#2f6fd6"),
    "heart": ("Heart", "#e0405e"),
    "bookmark": ("Bookmark", "#7b52c7"),
    "idea": ("Idea", "#e6c229"),
}
# Colours offered for note titles and icons: name -> colour.
NOTE_COLORS = {
    "Red": "#c0392b", "Orange": "#d35400", "Yellow": "#b7950b", "Green": "#1e8449",
    "Teal": "#117a65", "Blue": "#1f5fbf", "Purple": "#7d3c98", "Grey": "#707b7c",
}
_note_icons: dict = {}


def _paint_folder(size: int, base: Optional[QColor] = None) -> QPixmap:
    """A flat, modern folder: a darker back with its tab, and a lighter front
    panel with rounded corners. ``base`` is the note colour, if it has one."""
    s = size / 16.0
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(s, s)
    p.setPen(Qt.NoPen)
    if base is None or base == QColor(FOLDER_COLOR):
        back, front, shine = QColor("#e39b22"), QColor("#f7bd46"), QColor("#fcd679")
    else:
        back, front, shine = base.darker(118), base.lighter(112), base.lighter(135)

    # back panel with the tab
    tab = QPainterPath()
    tab.moveTo(1.5, 4.2)
    tab.quadTo(1.5, 2.5, 3.2, 2.5)
    tab.lineTo(6.0, 2.5)
    tab.quadTo(6.6, 2.5, 7.0, 2.9)
    tab.lineTo(8.2, 4.0)
    tab.lineTo(12.8, 4.0)
    tab.quadTo(14.5, 4.0, 14.5, 5.7)
    tab.lineTo(14.5, 11.8)
    tab.lineTo(1.5, 11.8)
    tab.closeSubpath()
    p.setBrush(back)
    p.drawPath(tab)

    # front panel
    front_path = QPainterPath()
    front_path.addRoundedRect(QRectF(1.5, 5.6, 13.0, 8.4), 1.6, 1.6)
    grad = QLinearGradient(0, 5.6, 0, 14)
    grad.setColorAt(0.0, shine)
    grad.setColorAt(0.25, front)
    grad.setColorAt(1.0, front)
    p.setBrush(grad)
    p.drawPath(front_path)
    p.end()
    return pm


def folder_icon() -> QIcon:
    global _folder
    if _folder is None:
        _folder = QIcon()
        for size in (16, 20, 24, 32, 40, 48, 64):
            _folder.addPixmap(_paint_folder(size))
    return _folder


def _paint_glyph(kind: str, size: int, color: QColor) -> QPixmap:
    """Small flat icons for notes, drawn on a 16 x 16 grid."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 16.0, size / 16.0)
    edge = QPen(color.darker(140), 1)
    edge.setCosmetic(True)
    white = QPen(QColor("white"), 1.8)
    white.setCapStyle(Qt.RoundCap)
    white.setJoinStyle(Qt.RoundJoin)
    path = QPainterPath()
    if kind == "page":
        path.moveTo(3.5, 1.5)
        path.lineTo(10, 1.5)
        path.lineTo(13.5, 5)
        path.lineTo(13.5, 14.5)
        path.lineTo(3.5, 14.5)
        path.closeSubpath()
        p.setPen(edge)
        p.setBrush(QColor("white"))
        p.drawPath(path)
        p.setPen(QPen(color, 1))
        for y in (7, 9, 11, 13):
            p.drawLine(5, y, 12, y)
    elif kind == "star":
        import math
        for i in range(10):
            r = 7.2 if i % 2 == 0 else 3.0
            a = -math.pi / 2 + i * math.pi / 5
            x, y = 8 + r * math.cos(a), 8.6 + r * math.sin(a)
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        path.closeSubpath()
        p.setPen(edge)
        p.setBrush(color)
        p.drawPath(path)
    elif kind == "flag":
        p.setPen(QPen(QColor("#555"), 1.4))
        p.drawLine(QPointF(3, 1.5), QPointF(3, 15))
        path.moveTo(3.5, 2)
        path.cubicTo(7, 0.5, 9, 4, 14, 2.5)
        path.lineTo(14, 9)
        path.cubicTo(9, 10.5, 7, 7, 3.5, 8.5)
        path.closeSubpath()
        p.setPen(edge)
        p.setBrush(color)
        p.drawPath(path)
    elif kind in ("check", "info", "warning"):
        if kind == "warning":
            path.moveTo(8, 1.2)
            path.lineTo(15.2, 14.5)
            path.lineTo(0.8, 14.5)
            path.closeSubpath()
            p.setPen(edge)
            p.setBrush(color)
            p.drawPath(path)
            mark = QPen(QColor("#222"), 1.8)
            mark.setCapStyle(Qt.RoundCap)
            p.setPen(mark)
            p.drawLine(QPointF(8, 5.8), QPointF(8, 9.8))
            p.drawPoint(QPointF(8, 12.4))
        else:
            p.setPen(edge)
            p.setBrush(color)
            p.drawEllipse(1, 1, 14, 14)
            p.setPen(white)
            if kind == "check":
                p.drawLine(QPointF(4.4, 8.2), QPointF(7, 10.8))
                p.drawLine(QPointF(7, 10.8), QPointF(11.8, 5.4))
            else:
                p.drawLine(QPointF(8, 7.2), QPointF(8, 11.8))
                p.drawPoint(QPointF(8, 4.6))
    elif kind == "heart":
        path.moveTo(8, 14)
        path.cubicTo(1, 9, 0.5, 5, 3, 3)
        path.cubicTo(5, 1.5, 7, 2.5, 8, 4.5)
        path.cubicTo(9, 2.5, 11, 1.5, 13, 3)
        path.cubicTo(15.5, 5, 15, 9, 8, 14)
        p.setPen(edge)
        p.setBrush(color)
        p.drawPath(path)
    elif kind == "bookmark":
        path.moveTo(4, 1.5)
        path.lineTo(12, 1.5)
        path.lineTo(12, 14.5)
        path.lineTo(8, 11)
        path.lineTo(4, 14.5)
        path.closeSubpath()
        p.setPen(edge)
        p.setBrush(color)
        p.drawPath(path)
    elif kind == "idea":
        p.setPen(edge)
        p.setBrush(color)
        p.drawEllipse(QPointF(8, 6.5), 5, 5)
        p.setBrush(QColor("#9a9a9a"))
        p.setPen(QPen(QColor("#666"), 1))
        p.drawRect(QRectF(6, 11, 4, 3))
        p.drawLine(QPointF(6, 12.5), QPointF(10, 12.5))
    p.end()
    return pm


def note_icon(kind: str = "", color: str = "") -> QIcon:
    """The icon for a note: the folder or another shape, in its colour."""
    if kind not in NOTE_ICONS:
        kind = ""
    if not kind and not color:
        return folder_icon()
    key = (kind, color)
    icon = _note_icons.get(key)
    if icon is None:
        c = QColor(color) if color and QColor(color).isValid() else QColor(NOTE_ICONS[kind][1])
        icon = QIcon()
        for size in (16, 20, 24, 32, 40, 48, 64):
            icon.addPixmap(_paint_folder(size, c) if not kind else _paint_glyph(kind, size, c))
        _note_icons[key] = icon
    return icon


# ---------------------------------------------------------------- branches

def draw_branches(tree, painter: QPainter, rect: QRect, index) -> None:
    """Dotted connector lines and +/- boxes in the indentation area of a row."""
    item = tree.itemFromIndex(index)
    if item is None:
        return
    indent = tree.indentation()
    cy = rect.top() + rect.height() // 2
    from .theme import mix
    base, text = tree.palette().color(QPalette.Base), tree.palette().color(QPalette.Text)
    pen = QPen(mix(base, text, 0.45), 1)
    pen.setCosmetic(True)
    pen.setDashPattern([1, 1])
    painter.save()
    # Qt paints the row's selection colour under the branch area; the classic
    # look keeps the highlight on the title only, so clear it first.
    painter.fillRect(rect, tree.palette().color(QPalette.Base))
    painter.setRenderHint(QPainter.Antialiasing, False)
    painter.setPen(pen)

    # Chain of ancestors from the top down, to know which levels continue.
    # While focusing on a branch, the focused node is drawn as the top.
    stop = getattr(tree, "hoisted", None)
    chain = []
    it = item
    while it is not None:
        chain.append(it)
        if it is stop:
            break
        it = it.parent()
    chain.reverse()
    depth = len(chain) - 1
    right = rect.right() + 1
    left = right - (depth + 1) * indent

    def has_next(node) -> bool:
        if node is stop:
            return False
        parent = node.parent() or tree.invisibleRootItem()
        return parent.indexOfChild(node) < parent.childCount() - 1

    def has_prev(node) -> bool:
        if node is stop:
            return False
        parent = node.parent() or tree.invisibleRootItem()
        return parent.indexOfChild(node) > 0

    # Vertical lines for ancestors that have more siblings below.
    for level, ancestor in enumerate(chain[:-1]):
        if has_next(ancestor):
            cx = left + level * indent + indent // 2
            painter.drawLine(cx, rect.top(), cx, rect.bottom())

    # This row: elbow from the line above, and on down if siblings follow.
    cx = left + depth * indent + indent // 2
    top = rect.top() if (len(chain) > 1 or has_prev(item)) else cy
    bottom = rect.bottom() if has_next(item) else cy
    painter.drawLine(cx, top, cx, bottom)
    painter.drawLine(cx, cy, left + (depth + 1) * indent - 1, cy)

    # +/- box for nodes with children.
    if item.childCount() > 0:
        box = QRect(cx - 4, cy - 4, 8, 8)
        painter.setPen(QPen(mix(base, text, 0.5), 1))
        painter.setBrush(tree.palette().color(QPalette.Base))
        painter.drawRect(box)
        painter.setPen(QPen(mix(base, text, 0.9), 1))
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
        x = r.left() + 1 + self.tree.icon_px + GAP
        w = fm.horizontalAdvance(text) + 2 * TEXT_PAD
        h = fm.height() + 2
        return QRect(x, r.top() + (r.height() - h) // 2, w, h)

    def sizeHint(self, option, index) -> QSize:
        if not self.tree.classic:
            return super().sizeHint(option, index)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        fm = opt.fontMetrics
        icon = self.tree.icon_px
        return QSize(1 + icon + GAP + fm.horizontalAdvance(opt.text) + 2 * TEXT_PAD + 4,
                     max(icon + 4, fm.height() + 4))

    def paint(self, painter: QPainter, option, index) -> None:
        if not self.tree.classic:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        r = opt.rect
        painter.save()
        icon = self.tree.icon_px
        icon_rect = QRect(r.left() + 1, r.top() + (r.height() - icon) // 2, icon, icon)
        item = self.tree.itemFromIndex(index)
        kind, color = getattr(item, "icon", ""), getattr(item, "color", "")
        note_icon(kind, color).paint(painter, icon_rect)

        text_rect = self._text_rect(opt, opt.text)
        selected = bool(opt.state & QStyle.State_Selected)
        group = QPalette.Active if opt.state & QStyle.State_Active else QPalette.Inactive
        pal = opt.palette
        if selected:
            painter.fillRect(text_rect, pal.color(group, QPalette.Highlight))
            painter.setPen(pal.color(group, QPalette.HighlightedText))
        elif color and QColor(color).isValid():
            painter.setPen(QColor(color))
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

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            # Tree rows are compact: keep the rename box's padding small so the
            # title is never clipped (the themes pad text boxes generously).
            editor.setObjectName("node-title-editor")
            editor.setStyleSheet("QLineEdit#node-title-editor { padding: 0px 3px; margin: 0px; "
                                 "border-radius: 3px; }")
        return editor

    def setModelData(self, editor, model, index) -> None:
        with self.tree.recording("Rename"):   # so a rename can be undone
            super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index) -> None:
        r = option.rect
        if self.tree.classic:
            x = r.left() + 1 + self.tree.icon_px + GAP
            width = max(80, r.right() - x)
        else:
            super().updateEditorGeometry(editor, option, index)
            x, width = editor.x(), editor.width()
        # At least as tall as the text needs, centred on the row.
        h = max(r.height(), editor.sizeHint().height())
        top = r.top() + (r.height() - h) // 2
        editor.setGeometry(QRect(x, top, width, h))
