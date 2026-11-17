# SPDX-License-Identifier: GPL-3.0-or-later
"""Twigpad's message windows: a coloured badge, a short bold heading, the
explanation, optional details, and buttons that say what they do ("Delete",
"Don't Save") instead of Yes and No. They follow the light and dark themes."""
from __future__ import annotations

from typing import Callable, Optional, Sequence, Tuple

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from . import iconset
from ..i18n import tr

INFO, QUESTION, WARNING, ERROR, SUCCESS = "info", "question", "warning", "error", "success"
_ACCENT = {INFO: "blue", QUESTION: "blue", WARNING: "amber", ERROR: "red", SUCCESS: "green"}

# Button roles: the primary button is filled with the accent colour, a danger
# button is red, cancel closes the window like Escape.
PRIMARY, DANGER, NORMAL, CANCEL = "primary", "danger", "normal", "cancel"
Button = Tuple[str, str, str]   # (key, label, role)

# Tests set this to a function that gets the dialog and returns a button key
# (or None) instead of showing the window.
auto_answer: Optional[Callable[["MessageDialog"], Optional[str]]] = None


def _accent(kind: str) -> QColor:
    dark = QApplication.palette().color(QPalette.Base).lightness() < 128
    colors = iconset.DARK_ACCENTS if dark else iconset.LIGHT_ACCENTS
    return QColor(colors[_ACCENT.get(kind, "blue")])


def badge(kind: str, size: int = 44) -> QPixmap:
    """A soft round badge with a symbol: i, ?, !, x or a tick."""
    ratio = QApplication.instance().devicePixelRatio() if QApplication.instance() else 1.0
    pm = QPixmap(int(size * ratio), int(size * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.transparent)
    color = _accent(kind)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    soft = QColor(color)
    soft.setAlphaF(0.16)
    p.setPen(Qt.NoPen)
    p.setBrush(soft)
    p.drawEllipse(QRectF(0, 0, size, size))
    s = size / 24.0   # draw on a 24 grid, like the toolbar icons
    pen = QPen(color, 2.2 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    dot = None
    if kind in (INFO,):
        path.moveTo(12 * s, 11 * s)
        path.lineTo(12 * s, 17 * s)
        dot = (12, 7.5)
    elif kind == WARNING:
        path.moveTo(12 * s, 6.5 * s)
        path.lineTo(12 * s, 13 * s)
        dot = (12, 17.3)
    elif kind == ERROR:
        path.moveTo(8.5 * s, 8.5 * s)
        path.lineTo(15.5 * s, 15.5 * s)
        path.moveTo(15.5 * s, 8.5 * s)
        path.lineTo(8.5 * s, 15.5 * s)
    elif kind == SUCCESS:
        path.moveTo(7.5 * s, 12.5 * s)
        path.lineTo(10.6 * s, 15.5 * s)
        path.lineTo(16.5 * s, 8.8 * s)
    else:   # question
        path.moveTo(9.3 * s, 9.6 * s)
        path.cubicTo(9.3 * s, 5.9 * s, 15 * s, 5.9 * s, 15 * s, 9.6 * s)
        path.cubicTo(15 * s, 11.6 * s, 12 * s, 11.9 * s, 12 * s, 14 * s)
        dot = (12, 17.5)
    p.drawPath(path)
    if dot:
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawEllipse(QRectF((dot[0] - 1.35) * s, (dot[1] - 1.35) * s, 2.7 * s, 2.7 * s))
    p.end()
    return pm


class MessageDialog(QDialog):
    """One message window. ``exec_choice()`` returns the key of the button
    that was pressed, or None when the window was closed or cancelled."""

    def __init__(self, parent: Optional[QWidget], kind: str, title: str, text: str = "",
                 buttons: Sequence[Button] = (("ok", "OK", PRIMARY),), default: Optional[str] = None,
                 details: str = "", rich: bool = False, window_title: str = ""):
        super().__init__(parent)
        from .. import APP_NAME
        self.setObjectName("popup")
        self.kind = kind
        self.choice: Optional[str] = None
        self.setWindowTitle(window_title or APP_NAME)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(22, 22, 24, 18)
        body.setSpacing(16)
        icon = QLabel()
        icon.setPixmap(badge(kind))
        icon.setAlignment(Qt.AlignTop)
        icon.setFixedWidth(46)
        body.addWidget(icon, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("popup-title")
        f = QFont(self.font())
        f.setPointSizeF(f.pointSizeF() * 1.22 if f.pointSizeF() > 0 else 12)
        f.setWeight(QFont.DemiBold)
        self.title_label.setFont(f)
        self.title_label.setWordWrap(True)
        self.title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        col.addWidget(self.title_label)
        self.text_label = QLabel(text)
        self.text_label.setObjectName("popup-text")
        self.text_label.setTextFormat(Qt.RichText if rich else Qt.PlainText)
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self.text_label.setOpenExternalLinks(True)
        self.text_label.setVisible(bool(text))
        self.text_label.setMinimumWidth(320)
        self.text_label.setMaximumWidth(460)
        self.text_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        col.addWidget(self.text_label)
        self.extra = QVBoxLayout()
        self.extra.setSpacing(6)
        col.addLayout(self.extra)
        self.details: Optional[QPlainTextEdit] = None
        if details:
            toggle = QToolButton()
            toggle.setObjectName("popup-toggle")
            toggle.setText(tr("Show Details"))
            toggle.setCursor(Qt.PointingHandCursor)
            self.details = QPlainTextEdit(details)
            self.details.setObjectName("popup-details")
            self.details.setReadOnly(True)
            self.details.setMinimumHeight(110)
            self.details.setVisible(False)

            def flip():
                show = not self.details.isVisible()
                self.details.setVisible(show)
                toggle.setText(tr("Hide Details") if show else tr("Show Details"))
                self.adjustSize()
            toggle.clicked.connect(flip)
            col.addWidget(toggle, 0, Qt.AlignLeft)
            col.addWidget(self.details)
        col.addStretch(1)
        body.addLayout(col, 1)
        outer.addLayout(body, 1)

        footer = QFrame()
        footer.setObjectName("popup-footer")
        row = QHBoxLayout(footer)
        row.setContentsMargins(18, 12, 18, 12)
        row.setSpacing(8)
        self.buttons = {}
        # With three buttons or more, a first "normal" button (such as Don't
        # Save) stands apart on the left; the others are on the right.
        left_one = len(buttons) > 2 and buttons[0][2] == NORMAL
        if not left_one:
            row.addStretch(1)
        for i, (key, label, role) in enumerate(buttons):
            btn = QPushButton(label)
            btn.setAutoDefault(False)
            btn.setMinimumWidth(88)
            if role == PRIMARY:
                btn.setObjectName("accent")
            elif role == DANGER:
                btn.setObjectName("danger")
            btn.clicked.connect(lambda _c=False, k=key: self._choose(k))
            row.addWidget(btn)
            if i == 0 and left_one:
                row.addStretch(1)
            self.buttons[key] = btn
        self._cancel_key = next((k for k, _l, r in buttons if r == CANCEL), None)
        if default is None:
            default = next((k for k, _l, r in buttons if r == PRIMARY), buttons[-1][0] if buttons else None)
        self.default_key = default
        if default in self.buttons:
            self.buttons[default].setDefault(True)
            self.buttons[default].setFocus()
        outer.addWidget(footer)
        self.setSizeGripEnabled(False)

    def add_widget(self, widget: QWidget) -> None:
        """Something extra under the text, such as a text box or a list."""
        self.extra.addWidget(widget)

    def _choose(self, key: str) -> None:
        self.choice = key
        if key == self._cancel_key:
            self.reject()
        else:
            self.accept()

    def reject(self) -> None:
        if self.choice is None:
            self.choice = self._cancel_key
        super().reject()

    def exec_choice(self) -> Optional[str]:
        if auto_answer is not None:
            self.choice = auto_answer(self)
            return self.choice
        self.adjustSize()
        self.exec_()
        return self.choice


def show(parent, kind: str, title: str, text: str = "", buttons: Sequence[Button] = (("ok", "OK", PRIMARY),),
         default: Optional[str] = None, details: str = "", rich: bool = False) -> Optional[str]:
    return MessageDialog(parent, kind, title, text, buttons, default, details, rich).exec_choice()


def info(parent, title: str, text: str = "", details: str = "", rich: bool = False) -> None:
    show(parent, INFO, title, text, details=details, rich=rich)


def success(parent, title: str, text: str = "", details: str = "") -> None:
    show(parent, SUCCESS, title, text, details=details)


def warning(parent, title: str, text: str = "", details: str = "") -> None:
    show(parent, WARNING, title, text, details=details)


def error(parent, title: str, text: str = "", details: str = "") -> None:
    show(parent, ERROR, title, text, details=details)


def confirm(parent, title: str, text: str = "", ok: str = "", cancel: str = "",
            danger: bool = False, kind: str = QUESTION, default_ok: bool = True) -> bool:
    """Two buttons; True when the user pressed ``ok``."""
    buttons = (("cancel", cancel or tr("Cancel"), CANCEL), ("ok", ok or tr("OK"), DANGER if danger else PRIMARY))
    return show(parent, kind, title, text, buttons, "ok" if default_ok else "cancel") == "ok"


def get_text(parent, title: str, text: str = "", value: str = "", password: bool = False,
             ok: str = "", placeholder: str = "", kind: str = QUESTION) -> Optional[str]:
    """Ask for one line of text (None when cancelled)."""
    dlg = MessageDialog(parent, kind, title, text, (("cancel", tr("Cancel"), CANCEL), ("ok", ok or tr("OK"), PRIMARY)))
    edit = QLineEdit(value)
    edit.setObjectName("popup-input")
    edit.setPlaceholderText(placeholder)
    edit.setMinimumWidth(300)
    if password:
        edit.setEchoMode(QLineEdit.Password)
    dlg.add_widget(edit)
    dlg.buttons["ok"].setDefault(True)
    edit.returnPressed.connect(lambda: dlg._choose("ok"))
    dlg.input = edit
    edit.setFocus()
    return edit.text() if dlg.exec_choice() == "ok" else None
