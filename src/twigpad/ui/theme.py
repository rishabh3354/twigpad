# SPDX-License-Identifier: GPL-3.0-or-later
"""Light and dark themes.

``auto`` picks light or dark to match the desktop, ``light`` and ``dark`` use
Twigpad's own colours on the Fusion style, and ``system`` leaves the
desktop's own style and colours alone.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from typing import Dict, Optional

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPalette, QPen
from PyQt5.QtWidgets import QApplication, QProxyStyle, QStyle, QStyleFactory

from ..i18n import N_

THEMES = {
    "auto": N_("&Automatic (Follow the Desktop)"),
    "light": N_("&Light"),
    "dark": N_("&Dark"),
    "system": N_("Desktop &Style"),
}

LIGHT: Dict[str, str] = {
    "window": "#f3f4f6", "base": "#ffffff", "alt": "#f7f8fa", "text": "#1d2127",
    "subtext": "#5c6470", "button": "#fafbfc", "border": "#d5d9df", "hover": "#e5e9ef",
    "pressed": "#d7dde6", "accent": "#2f6fd6", "accent_text": "#ffffff",
    "inactive_sel": "#d9e3f5", "inactive_sel_text": "#1d2127", "menu": "#ffffff",
    "tooltip_bg": "#2b3038", "tooltip_fg": "#f3f4f6", "scroll": "#c4cad2",
    "scroll_hover": "#a3abb6", "link": "#1f5fbf", "visited": "#6a3fb5",
    "disabled": "#a0a6af", "bright": "#c0392b", "danger": "#cf3b2f", "danger_hover": "#b33126",
    "footer": "#f7f8fa",
}
DARK: Dict[str, str] = {
    "window": "#202327", "base": "#181a1d", "alt": "#1d2024", "text": "#e3e6ea",
    "subtext": "#9aa3ad", "button": "#2a2e34", "border": "#363b42", "hover": "#30353c",
    "pressed": "#3a4048", "accent": "#3d7fe6", "accent_text": "#ffffff",
    "inactive_sel": "#2f3a48", "inactive_sel_text": "#e3e6ea", "menu": "#25292e",
    "tooltip_bg": "#30353c", "tooltip_fg": "#e3e6ea", "scroll": "#454b53",
    "scroll_hover": "#5c636d", "link": "#7aaefc", "visited": "#b69cf2",
    "disabled": "#666d76", "bright": "#ff7b72", "danger": "#d9453a", "danger_hover": "#e8594e",
    "footer": "#1b1e21",
}

STYLE = """
QMainWindow::separator { background: %(border)s; width: 1px; height: 1px; }
QMenuBar { background: %(window)s; border-bottom: 1px solid %(border)s; padding: 2px 3px; }
QMenuBar::item { background: transparent; padding: 4px 10px; border-radius: 5px; }
QMenuBar::item:selected { background: %(hover)s; }
QMenuBar::item:pressed { background: %(pressed)s; }
QMenu { background: %(menu)s; border: 1px solid %(border)s; padding: 5px 4px; }
QMenu::item { padding: 5px 26px 5px 28px; margin: 1px 2px; border-radius: 5px; }
QMenu::item:selected { background: %(accent)s; color: %(accent_text)s; }
QMenu::item:disabled { color: %(disabled)s; }
QMenu::separator { height: 1px; background: %(border)s; margin: 5px 10px; }
QMenu::icon { padding-left: 6px; }
QToolBar { background: %(window)s; border: none; spacing: 1px; padding: 3px 2px; }
QToolBar::separator { background: %(border)s; width: 1px; margin: 5px 4px; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 2px; }
QToolButton:hover { background: %(hover)s; border-color: %(border)s; }
QToolButton:pressed, QToolButton:checked { background: %(pressed)s; border-color: %(border)s; }
QStatusBar { background: %(window)s; border-top: 1px solid %(border)s; color: %(subtext)s; }
QStatusBar::item { border: none; }
QStatusBar QLabel { color: %(subtext)s; padding: 0 6px; }
QSplitter::handle { background: %(window)s; }
QSplitter::handle:horizontal { width: 5px; }
QSplitter::handle:vertical { height: 5px; }
QTreeView, QListView, QTextEdit, QPlainTextEdit { border: 1px solid %(border)s; }
QDockWidget::title { background: %(window)s; padding: 5px 8px; border-bottom: 1px solid %(border)s; }
QLineEdit { background: %(base)s; border: 1px solid %(border)s; border-radius: 5px; padding: 3px 6px;
            selection-background-color: %(accent)s; selection-color: %(accent_text)s; }
QLineEdit:focus { border-color: %(accent)s; }
QLineEdit:disabled { color: %(disabled)s; }
QPushButton { background: %(button)s; border: 1px solid %(border)s; border-radius: 6px;
              padding: 5px 14px; min-height: 18px; }
QPushButton:hover { background: %(hover)s; }
QPushButton:pressed { background: %(pressed)s; }
QPushButton:default { border-color: %(accent)s; }
QPushButton:disabled { color: %(disabled)s; }
QPushButton#accent { background: %(accent)s; color: %(accent_text)s; border-color: %(accent)s; }
QPushButton#accent:hover { background: %(link)s; border-color: %(link)s; }
QPushButton#danger { background: %(danger)s; color: #ffffff; border-color: %(danger)s; }
QPushButton#danger:hover { background: %(danger_hover)s; border-color: %(danger_hover)s; }
QLabel#hint { color: %(subtext)s; }
QLabel#popup-text { color: %(text)s; }
QFrame#popup-footer { background: %(footer)s; border-top: 1px solid %(border)s; }
QPlainTextEdit#popup-details { background: %(alt)s; border: 1px solid %(border)s; border-radius: 6px; }
QToolButton#popup-toggle { color: %(link)s; border: none; padding: 2px 0; margin: 0; }
QToolButton#popup-toggle:hover { background: transparent; text-decoration: underline; }
QToolTip { background: %(tooltip_bg)s; color: %(tooltip_fg)s; border: 1px solid %(border)s; padding: 4px 6px; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
QScrollBar::handle:vertical { background: %(scroll)s; min-height: 32px; border-radius: 3px; margin: 2px 3px; }
QScrollBar::handle:horizontal { background: %(scroll)s; min-width: 32px; border-radius: 3px; margin: 3px 2px; }
QScrollBar::handle:hover { background: %(scroll_hover)s; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; border: none; background: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
"""

_original: Optional[tuple] = None   # the desktop's style name and palette
current = "system"                  # the theme in use: light, dark or system
_applied: Dict[int, str] = {}


def _remember(app: QApplication) -> None:
    global _original
    if _original is None:
        _original = (app.style().objectName(), QPalette(app.palette()))


def palette_for(tokens: Dict[str, str]) -> QPalette:
    c = {k: QColor(v) for k, v in tokens.items()}
    pal = QPalette()
    roles = {
        QPalette.Window: "window", QPalette.WindowText: "text", QPalette.Base: "base",
        QPalette.AlternateBase: "alt", QPalette.Text: "text", QPalette.Button: "button",
        QPalette.ButtonText: "text", QPalette.BrightText: "bright", QPalette.Highlight: "accent",
        QPalette.HighlightedText: "accent_text", QPalette.ToolTipBase: "tooltip_bg",
        QPalette.ToolTipText: "tooltip_fg", QPalette.Link: "link", QPalette.LinkVisited: "visited",
        QPalette.PlaceholderText: "disabled", QPalette.Mid: "border", QPalette.Midlight: "hover",
        QPalette.Light: "base", QPalette.Dark: "scroll", QPalette.Shadow: "scroll_hover",
    }
    for role, key in roles.items():
        pal.setColor(role, c[key])
    pal.setColor(QPalette.Inactive, QPalette.Highlight, c["inactive_sel"])
    pal.setColor(QPalette.Inactive, QPalette.HighlightedText, c["inactive_sel_text"])
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, c["disabled"])
    pal.setColor(QPalette.Disabled, QPalette.Light, c["window"])   # no embossed disabled text
    pal.setColor(QPalette.Disabled, QPalette.Highlight, c["border"])
    return pal


@lru_cache(maxsize=1)
def desktop_prefers_dark() -> bool:
    """Whether the desktop is set to a dark style (GNOME, GTK or KDE)."""
    if os.environ.get("GTK_THEME", "").lower().endswith(":dark"):
        return True
    gsettings = shutil.which("gsettings")
    if gsettings:
        for key in ("color-scheme", "gtk-theme"):
            try:
                out = subprocess.run([gsettings, "get", "org.gnome.desktop.interface", key],
                                     capture_output=True, text=True, timeout=1).stdout.lower()
            except (OSError, subprocess.SubprocessError):
                break
            if "dark" in out:
                return True
    if _original is not None:   # e.g. a dark KDE colour scheme
        return _original[1].color(QPalette.Window).lightness() < 128
    return False


def resolve(name: str) -> str:
    if name == "auto":
        return "dark" if desktop_prefers_dark() else "light"
    return name if name in ("light", "dark") else "system"


class TwigStyle(QProxyStyle):
    """Fusion, with the tab close button drawn as a sharp X in the text colour.
    Fusion's own is a small dark picture: blurry on large screens and hard to
    see in the dark theme."""

    def __init__(self):
        super().__init__(QStyleFactory.create("Fusion"))

    def drawPrimitive(self, element, option, painter, widget=None):
        if element != QStyle.PE_IndicatorTabClose:
            super().drawPrimitive(element, option, painter, widget)
            return
        r = QRectF(option.rect)
        hover = bool(option.state & QStyle.State_MouseOver)
        ink = QColor(option.palette.color(QPalette.WindowText))
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        if hover:
            back = QColor(ink)
            back.setAlpha(45)
            painter.setPen(Qt.NoPen)
            painter.setBrush(back)
            painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 3, 3)
        else:
            ink.setAlpha(150)
        pen = QPen(ink, 1.3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        c, d = r.center(), min(r.width(), r.height()) * 0.22
        painter.drawLine(QPointF(c.x() - d, c.y() - d), QPointF(c.x() + d, c.y() + d))
        painter.drawLine(QPointF(c.x() + d, c.y() - d), QPointF(c.x() - d, c.y() + d))
        painter.restore()


def apply(name: str, app: Optional[QApplication] = None) -> str:
    """Apply a theme to the whole application; returns light, dark or system."""
    global current
    app = app or QApplication.instance()
    _remember(app)
    effective = resolve(name)
    if effective == _applied.get(id(app)):
        return effective          # already in use: restyling every widget again is slow
    _applied[id(app)] = effective
    if effective == "system":
        style = QStyleFactory.create(_original[0])
        if style is not None:
            app.setStyle(style)
        app.setPalette(_original[1])
        app.setStyleSheet("")
    else:
        tokens = DARK if effective == "dark" else LIGHT
        app.setStyle(TwigStyle())
        app.setPalette(palette_for(tokens))
        app.setStyleSheet(STYLE % tokens)
    current = effective
    return effective


def is_dark(palette: Optional[QPalette] = None) -> bool:
    pal = palette or QApplication.palette()
    return pal.color(QPalette.Base).lightness() < 128


def mix(a: QColor, b: QColor, t: float) -> QColor:
    """A colour between ``a`` (t=0) and ``b`` (t=1)."""
    return QColor(round(a.red() + (b.red() - a.red()) * t),
                  round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))
