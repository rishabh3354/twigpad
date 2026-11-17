# SPDX-License-Identifier: GPL-3.0-or-later
"""Fonts: a clean, readable default font, slightly larger default sizes, and
the Fonts window where the interface, tree and article fonts are chosen."""
from __future__ import annotations

from typing import Dict, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFontComboBox, QGridLayout, QLabel, QPushButton,
    QSpinBox, QVBoxLayout,
)

# Well-made, widely installed sans-serif fonts, best first. The first one that
# is installed becomes Twigpad's default; the desktop's font is the fallback.
UI_FAMILIES = ("Inter", "Inter Variable", "Noto Sans", "Cantarell", "Ubuntu", "Roboto",
               "Open Sans", "Source Sans 3", "Source Sans Pro", "Lato", "DejaVu Sans")

PANES = ("app", "tree", "editor")
PANE_NAMES = {"app": "Interface", "tree": "Tree", "editor": "Article"}
# Default sizes in points: at least these, and a little larger than the
# desktop's own font size for the tree and the article.
MIN_SIZES = {"app": 10, "tree": 11, "editor": 12}
EXTRA = {"app": 0, "tree": 1, "editor": 2}
SAMPLES = {"app": "Menus, buttons and windows",
           "tree": "Projects  ›  Ideas  ›  Reading list",
           "editor": "The quick brown fox jumps over the lazy dog. 0123456789"}

_desktop_font: Optional[QFont] = None


def desktop_font() -> QFont:
    """The desktop's font, as it was before Twigpad changed it."""
    global _desktop_font
    if _desktop_font is None:
        _desktop_font = QFont(QApplication.font())
    return QFont(_desktop_font)


def default_family() -> str:
    families = set(QFontDatabase().families())
    for name in UI_FAMILIES:
        if name in families:
            return name
    return desktop_font().family()


def default_font(which: str) -> QFont:
    desk = desktop_font()
    size = desk.pointSizeF() if desk.pointSizeF() > 0 else 10.0
    font = QFont(default_family())
    font.setPointSizeF(max(float(MIN_SIZES[which]), round(size) + EXTRA[which]))
    return font


def saved_font(settings, which: str) -> QFont:
    """The font chosen for 'app', 'tree' or 'editor', or the default."""
    desc = settings.value(f"fonts/{which}", "", type=str)
    font = QFont()
    if desc and font.fromString(desc):
        return font
    return default_font(which)


def apply_app_font(settings) -> None:
    desktop_font()   # remember the desktop's font before changing it
    font = saved_font(settings, "app")
    if QApplication.font() != font:
        QApplication.setFont(font)


class FontsDialog(QDialog):
    """Interface, tree and article fonts, with a live preview. Changes show at
    once; Cancel puts the old fonts back."""

    def __init__(self, window, focus: str = "editor"):
        super().__init__(window)
        self.win = window
        self.setWindowTitle("Fonts")
        self._old: Dict[str, str] = {w: window.settings.value(f"fonts/{w}", "", type=str) for w in PANES}
        self._old_zoom = {w: window.settings.value(f"view/{w}_zoom", None) for w in ("tree", "editor")}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(12)
        head = QLabel("<b>Choose the fonts Twigpad uses.</b> Changes show right away.")
        lay.addWidget(head)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self.family: Dict[str, QFontComboBox] = {}
        self.size: Dict[str, QSpinBox] = {}
        self.sample: Dict[str, QLabel] = {}
        for row, which in enumerate(PANES):
            label = QLabel(f"{PANE_NAMES[which]}:")
            family = QFontComboBox()
            family.setObjectName(f"font-{which}")
            size = QSpinBox()
            size.setRange(6, 48)
            size.setSuffix(" pt")
            label.setBuddy(family)
            sample = QLabel(SAMPLES[which])
            sample.setObjectName("font-sample")
            sample.setTextInteractionFlags(Qt.NoTextInteraction)
            sample.setMinimumHeight(34)
            grid.addWidget(label, row * 2, 0)
            grid.addWidget(family, row * 2, 1)
            grid.addWidget(size, row * 2, 2)
            grid.addWidget(sample, row * 2 + 1, 1, 1, 2)
            self.family[which], self.size[which], self.sample[which] = family, size, sample
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        note = QLabel("Ctrl+= and Ctrl+- still make the tree or the article larger or smaller "
                      "while you work; Ctrl+0 goes back to these sizes.")
        note.setWordWrap(True)
        note.setObjectName("hint")
        lay.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.defaults = QPushButton("Restore Defaults")
        buttons.addButton(self.defaults, QDialogButtonBox.ResetRole)
        buttons.button(QDialogButtonBox.Ok).setObjectName("accent")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.defaults.clicked.connect(self.restore_defaults)
        lay.addWidget(buttons)
        self._load()
        for which in PANES:
            self.family[which].currentFontChanged.connect(self._changed)
            self.size[which].valueChanged.connect(self._changed)
        self.family.get(focus, self.family["editor"]).setFocus()
        self.setMinimumWidth(500)

    def _load(self) -> None:
        for which in PANES:
            font = saved_font(self.win.settings, which)
            for w in (self.family[which], self.size[which]):
                w.blockSignals(True)
            self.family[which].setCurrentFont(font)
            self.size[which].setValue(round(font.pointSizeF()))
            for w in (self.family[which], self.size[which]):
                w.blockSignals(False)
            self._show_sample(which, font)

    def chosen(self, which: str) -> QFont:
        font = QFont(self.family[which].currentFont().family())
        font.setPointSize(self.size[which].value())
        return font

    def _show_sample(self, which: str, font: QFont) -> None:
        self.sample[which].setFont(font)

    def _changed(self, *_args) -> None:
        for which in PANES:
            font = self.chosen(which)
            self._show_sample(which, font)
            if font != default_font(which):
                self.win.settings.setValue(f"fonts/{which}", font.toString())
            else:
                self.win.settings.remove(f"fonts/{which}")
        for which in ("tree", "editor"):
            self.win.settings.remove(f"view/{which}_zoom")   # the chosen size, as chosen
        self.win.apply_text_sizes()

    def restore_defaults(self) -> None:
        for which in PANES:
            self.win.settings.remove(f"fonts/{which}")
        self._load()
        self._changed()

    def reject(self) -> None:
        for which, desc in self._old.items():
            if desc:
                self.win.settings.setValue(f"fonts/{which}", desc)
            else:
                self.win.settings.remove(f"fonts/{which}")
        for which, zoom in self._old_zoom.items():
            if zoom is not None:
                self.win.settings.setValue(f"view/{which}_zoom", zoom)
        self.win.apply_text_sizes()
        super().reject()

