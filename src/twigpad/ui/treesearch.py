# SPDX-License-Identifier: GPL-3.0-or-later
"""The Tree Search window: search the titles and articles of the whole tree
(or the selected subtree) and list every node that matches, with its path."""
from __future__ import annotations

from typing import List, NamedTuple, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QRadioButton, QSpinBox, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from .. import search
from ..i18n import N_, ntr, tr

NODE, ARTICLE, BOTH = N_("Node"), N_("Article"), N_("Article+Node")   # shown translated


class Hit(NamedTuple):
    item: object
    location: str      # Node, Article or Article+Node
    path: str


def node_path(item) -> str:
    titles = []
    while item is not None:
        titles.append(item.title)
        item = item.parent()
    return "/".join(reversed(titles))


def search_items(items, text: str, titles: bool = True, articles: bool = True) -> List[Hit]:
    """Every node whose title and/or article contains ``text`` (ignoring case)."""
    pattern = search.compile_pattern(text)
    hits = []
    for item in items:
        in_title = titles and pattern.search(item.title) is not None
        in_article = articles and pattern.search(item.body) is not None
        if in_title or in_article:
            location = BOTH if in_title and in_article else (NODE if in_title else ARTICLE)
            hits.append(Hit(item, location, node_path(item)))
    return hits


class TreeSearchDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle(tr("Tree Search"))
        self.hits: List[Hit] = []
        self.subtree_root = None

        # --- search text, Find, hide option
        self.text_edit = QLineEdit()
        self.find_btn = QPushButton(tr("&Find"))
        self.hide_box = QCheckBox(tr("&Hide search window after item is double clicked"))
        left = QGridLayout()
        label = QLabel(tr("<b>Search text:</b>"))
        label.setBuddy(self.text_edit)
        left.addWidget(label, 0, 0, 1, 2)
        left.addWidget(self.text_edit, 1, 0)
        left.addWidget(self.find_btn, 1, 1)
        left.addWidget(self.hide_box, 2, 0, 1, 2)
        left.setColumnStretch(0, 1)
        left.setRowStretch(3, 1)   # keep the search box at the top, as in the classic window

        # --- what to search, maximum rows
        self.total_radio = QRadioButton(tr("&Total tree"))
        self.subtree_radio = QRadioButton(tr("S&ubtree"))
        self.nodes_box = QCheckBox(tr("&Nodes"))
        self.articles_box = QCheckBox(tr("&Articles"))
        group = QGroupBox(tr("What to search:"))
        g = QGridLayout(group)
        g.addWidget(self.total_radio, 0, 0)
        g.addWidget(self.subtree_radio, 1, 0)
        g.addWidget(self.nodes_box, 0, 1)
        g.addWidget(self.articles_box, 1, 1)
        g.setHorizontalSpacing(28)
        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 100000)
        rows = QHBoxLayout()
        rows_label = QLabel(tr("Maximum number of\nrows in search result"))
        rows_label.setBuddy(self.max_spin)
        rows.addWidget(rows_label)
        rows.addWidget(self.max_spin)
        rows.addStretch(1)
        right = QVBoxLayout()
        right.addWidget(group)
        right.addLayout(rows)

        top = QHBoxLayout()
        top.addLayout(left, 1)
        top.addSpacing(24)
        top.addLayout(right)

        # --- results
        self.count_label = QLabel()
        self.results = QTreeWidget()
        self.results.setHeaderLabels([tr("Nr."), tr("Node"), tr("Location"), tr("Path")])
        self.results.setRootIsDecorated(False)
        self.results.setUniformRowHeights(True)
        self.results.setSelectionMode(QAbstractItemView.SingleSelection)
        self.results.setAllColumnsShowFocus(True)
        header = self.results.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Interactive)
        fm = self.results.fontMetrics()
        widths = (fm.horizontalAdvance(tr("Nr.")) + 26, 200, fm.horizontalAdvance(tr(BOTH)) + 24)
        for col, width in enumerate(widths):
            self.results.setColumnWidth(col, width)

        # --- bottom
        self.search_article_btn = QPushButton(tr("&Search Article"))
        self.search_article_btn.setToolTip(tr("Find the search text in the article of the selected result"))
        self.close_btn = QPushButton(tr("Close"))
        bottom = QHBoxLayout()
        bottom.addWidget(QLabel(tr("Double-click a search result item to select the\n"
                                "corresponding tree node (or press enter).")))
        bottom.addStretch(1)
        bottom.addWidget(self.search_article_btn)
        bottom.addWidget(self.close_btn)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.count_label)
        lay.addWidget(self.results, 1)
        lay.addLayout(bottom)

        for btn in (self.find_btn, self.search_article_btn, self.close_btn):
            btn.setAutoDefault(False)   # Enter is handled in keyPressEvent
        self.find_btn.clicked.connect(self.run_search)
        self.close_btn.clicked.connect(self.close)
        self.search_article_btn.clicked.connect(self.search_article)
        self.results.itemDoubleClicked.connect(lambda *_: self.open_selected())
        self.results.currentItemChanged.connect(lambda *_: self._update_buttons())
        for box in (self.nodes_box, self.articles_box):
            box.toggled.connect(self._update_buttons)
        self.text_edit.textChanged.connect(self._update_buttons)
        self.resize(780, 540)
        self._load_options()
        self._update_buttons()

    # ------------------------------------------------------------ options

    def _load_options(self) -> None:
        s = self.win.settings
        self.hide_box.setChecked(s.value("treesearch/hide_after_open", True, type=bool))
        self.nodes_box.setChecked(s.value("treesearch/nodes", True, type=bool))
        self.articles_box.setChecked(s.value("treesearch/articles", True, type=bool))
        self.max_spin.setValue(s.value("treesearch/max_rows", 200, type=int))
        self.total_radio.setChecked(True)

    def _save_options(self) -> None:
        s = self.win.settings
        s.setValue("treesearch/hide_after_open", self.hide_box.isChecked())
        s.setValue("treesearch/nodes", self.nodes_box.isChecked())
        s.setValue("treesearch/articles", self.articles_box.isChecked())
        s.setValue("treesearch/max_rows", self.max_spin.value())

    def _update_buttons(self, *_args) -> None:
        self.find_btn.setEnabled(bool(self.text_edit.text())
                                 and (self.nodes_box.isChecked() or self.articles_box.isChecked()))
        hit = self.current_hit()
        self.search_article_btn.setEnabled(hit is not None and hit.location != NODE)

    # ------------------------------------------------------------ showing

    def show_dialog(self) -> None:
        self.subtree_root = self.win.tree.currentItem()
        selected = self.win.editor.textCursor().selectedText()
        if selected and " " not in selected and len(selected) < 100:
            self.text_edit.setText(selected)
        self.show()
        self.raise_()
        self.activateWindow()
        self.text_edit.setFocus()
        self.text_edit.selectAll()

    def clear(self) -> None:
        """Forget the results (another file was opened)."""
        self.hits = []
        self.results.clear()
        self.count_label.clear()
        self._update_buttons()

    # ------------------------------------------------------------ search

    def _items(self) -> list:
        tree = self.win.tree
        root = self.subtree_root
        if self.subtree_radio.isChecked() and root is not None and root in tree.all_items():
            return tree.all_items_under(root)
        return tree.all_items()

    def run_search(self) -> int:
        text = self.text_edit.text()
        if not text or not (self.nodes_box.isChecked() or self.articles_box.isChecked()):
            return 0
        self._save_options()
        self.win._commit_editor()
        found = search_items(self._items(), text, self.nodes_box.isChecked(), self.articles_box.isChecked())
        limit = self.max_spin.value()
        self.hits = found[:limit]
        self.results.clear()
        rows = []
        for n, hit in enumerate(self.hits, 1):
            row = QTreeWidgetItem([str(n), hit.item.title, tr(hit.location), hit.path])
            row.setToolTip(3, hit.path)
            rows.append(row)
        self.results.addTopLevelItems(rows)
        total = len(found)
        text = ntr("{n} item found", "{n} items found", total).format(n=total)
        if total > limit:
            text += " " + tr("(showing the first {limit})").format(limit=limit)
        self.count_label.setText(f"<b>{text}</b>")
        if rows:
            self.results.setCurrentItem(rows[0])
            self.results.setFocus()
        self._update_buttons()
        return total

    def current_hit(self) -> Optional[Hit]:
        row = self.results.currentItem()
        if row is None:
            return None
        i = self.results.indexOfTopLevelItem(row)
        return self.hits[i] if 0 <= i < len(self.hits) else None

    def _select(self, hit: Hit) -> bool:
        if hit.item not in self.win.tree.all_items():   # deleted since the search
            return False
        self.win.tree.setCurrentItem(hit.item)
        self.win.tree.scrollToItem(hit.item)
        return True

    def open_selected(self) -> bool:
        """Select the node of the chosen result in the tree."""
        hit = self.current_hit()
        if hit is None or not self._select(hit):
            return False
        if hit.location != NODE:
            self._highlight_in_article(from_start=True)
        if self.hide_box.isChecked():
            self.hide()
            self.win.activateWindow()
            self.win.tree.setFocus()
        return True

    def search_article(self) -> bool:
        """Select the next place in the result's article that has the search text."""
        hit = self.current_hit()
        if hit is None or hit.location == NODE or not self._select(hit):
            return False
        return self._highlight_in_article(from_start=False)

    def _highlight_in_article(self, from_start: bool) -> bool:
        editor = self.win.editor
        pattern = search.compile_pattern(self.text_edit.text())
        body = editor.toPlainText()
        cursor = editor.textCursor()
        start = 0 if from_start else search.from_qt(body, cursor.selectionEnd())
        m = pattern.search(body, start) or pattern.search(body)
        if m is None:
            return False
        cursor.setPosition(search.to_qt(body, m.start()))
        cursor.setPosition(search.to_qt(body, m.end()), QTextCursor.KeepAnchor)
        editor.setTextCursor(cursor)
        editor.ensureCursorVisible()
        return True

    # ------------------------------------------------------------ keys

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.results.hasFocus() and self.results.currentItem() is not None:
                self.open_selected()
            elif self.find_btn.isEnabled():
                self.run_search()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self._save_options()
        super().closeEvent(event)
