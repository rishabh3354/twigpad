# SPDX-License-Identifier: GPL-3.0-or-later
"""Help > Keyboard Shortcuts: every shortcut, grouped by menu, with a search
box. Built from the window's own actions, so it is always up to date."""
from __future__ import annotations

from typing import List, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtWidgets import (
    QAction, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout,
)
from ..i18n import N_, tr

# Shortcuts that are not menu items.
EXTRA: List[Tuple[str, str]] = [
    (N_("Make the text larger or smaller"), N_("Ctrl+Mouse Wheel")),
    (N_("Follow a link in the article"), N_("Ctrl+Click")),
    (N_("Scroll the tree without moving the selection"), "Ctrl+Up, Ctrl+Down"),
    (N_("Drop a dragged node beside another (not inside it)"), N_("Shift+Drop")),
    (N_("Right-click menu of the tree or the article"), "Shift+F10"),
]


def clean(text: str) -> str:
    """'&Save As...' -> 'Save As'."""
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&").replace("...", "").strip()


def name(action: QAction) -> str:
    return action.property("shortcut_name") or clean(action.text())


def keys(action: QAction) -> str:
    return ", ".join(s.toString(QKeySequence.NativeText) for s in action.shortcuts() if not s.isEmpty())


def collect(window) -> List[Tuple[str, List[Tuple[str, str]]]]:
    """[(group, [(what, keys), ...]), ...] in menu order."""
    groups: List[Tuple[str, List[Tuple[str, str]]]] = []
    seen = set()

    def walk(menu: QMenu, rows: List[Tuple[str, str]], prefix: str = "") -> None:
        for act in menu.actions():
            if act.menu() is not None:
                walk(act.menu(), rows, prefix + clean(act.text()) + " › ")
            elif not act.isSeparator() and keys(act) and id(act) not in seen:
                seen.add(id(act))
                rows.append((prefix + name(act), keys(act)))

    for top in window.menuBar().actions():
        if top.menu() is None:
            continue
        rows: List[Tuple[str, str]] = []
        walk(top.menu(), rows)
        if rows:
            groups.append((clean(top.text()), rows))
    others = [(name(a), keys(a)) for a in window.findChildren(QAction)
              if id(a) not in seen and keys(a) and name(a)]
    seen_rows = set()
    unique = []
    for row in others + [(tr(what), tr(keys)) for what, keys in EXTRA]:
        if row not in seen_rows:
            seen_rows.add(row)
            unique.append(row)
    groups.append((tr("Tree, Article and Mouse"), sorted(unique, key=lambda r: r[0].casefold())))
    return groups


class ShortcutsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.setWindowTitle(tr("Keyboard Shortcuts"))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Search shortcuts, for example \"node\" or \"Ctrl+S\""))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filter)
        lay.addWidget(self.search)
        self.table = QTreeWidget()
        self.table.setObjectName("shortcuts")
        self.table.setHeaderLabels([tr("Command"), tr("Shortcut")])
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setUniformRowHeights(True)
        header = self.table.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        bold = QFont(self.font())
        bold.setWeight(QFont.DemiBold)
        mono = QFont(self.font())
        mono.setWeight(QFont.Medium)
        for group, rows in collect(window):
            head = QTreeWidgetItem([group])
            head.setFont(0, bold)
            head.setFlags(Qt.ItemIsEnabled)
            head.setFirstColumnSpanned(False)
            self.table.addTopLevelItem(head)
            for what, key in rows:
                row = QTreeWidgetItem([what, key])
                row.setFont(1, mono)
                head.addChild(row)
            head.setExpanded(True)
        self.table.setItemsExpandable(False)
        self.table.setIndentation(14)
        lay.addWidget(self.table, 1)
        self.empty = QLabel(tr("No shortcut matches your search."))
        self.empty.setObjectName("hint")
        self.empty.setVisible(False)
        lay.addWidget(self.empty)
        row = QHBoxLayout()
        hint = QLabel(tr("Some shortcuts work only in the tree or only in the article."))
        hint.setObjectName("hint")
        row.addWidget(hint, 1)
        close = QPushButton(tr("Close"))
        close.setDefault(True)
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)
        self.resize(620, 640)
        self.search.setFocus()

    def apply_filter(self, text: str) -> int:
        """Hide rows that don't match; returns how many rows are shown."""
        text = text.strip().casefold()
        shown = 0
        for i in range(self.table.topLevelItemCount()):
            head = self.table.topLevelItem(i)
            visible = 0
            for j in range(head.childCount()):
                row = head.child(j)
                hit = not text or text in row.text(0).casefold() or text in row.text(1).casefold() \
                    or text in head.text(0).casefold()
                row.setHidden(not hit)
                visible += hit
            head.setHidden(visible == 0)
            shown += visible
        self.empty.setVisible(shown == 0)
        return shown
